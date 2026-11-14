"""評測：每題在每一組的資料夾裡執行一次 claude -p；閉卷組則在空資料夾、不開工具。結果附加到 results/results.jsonl。"""
from __future__ import annotations

import json
import random
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from functools import partial
from pathlib import Path

from lab.build import stage_problems
from lab.common import (CLOSED, CONDS, ISOLATION, MAPPING, RESULTS_JSONL, RUNS, is_under_home, leaking_ancestors,
                        load_bodies, load_json, load_world, read_rows, stage_root, world_id)
from lab.trace import isolation_problems, parse_stream, summarize
from lab.world import check_questions

PROMPT = """你是公司內部的資料查詢助理。請只根據目前資料夾裡的文件回答下面的問題，不要憑自己的知識。
如果文件中找不到答案，found 填 false，answer 說明找不到。
sources 列出你實際用來回答的文件路徑（相對於目前資料夾）。
數字請用阿拉伯數字。

問題：{question}"""

CLOSED_PROMPT = """請不要查任何資料，直接憑你自己的知識回答下面的問題。
如果你不知道或不確定，found 填 false，answer 說明不知道。
sources 留空。數字請用阿拉伯數字。

問題：{question}"""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"},
                   "sources": {"type": "array", "items": {"type": "string"}},
                   "found": {"type": "boolean"}},
    "required": ["answer", "sources", "found"],
}

PREFLIGHT_PROMPT = "這是連線檢查：不要使用任何工具，直接回答 answer=ok、sources 留空、found=false。"


def ask_cmd(prompt: str, model: str, effort: str, tools: str = "Read,Grep,Glob") -> list[str]:
    return ["claude", "-p", prompt, "--model", model, "--effort", effort, "--tools", tools,
            "--output-format", "stream-json", "--verbose", "--include-hook-events",
            "--json-schema", json.dumps(ANSWER_SCHEMA, ensure_ascii=False), *ISOLATION]


def done_keys(rows: list[dict], wid: str, model: str, effort: str) -> set[tuple[int, str, str]]:
    """已經成功跑完的 (round, cond, qid)，續跑時跳過。"""
    return {(r["round"], r["cond"], r["qid"]) for r in rows
            if r["world_id"] == wid and r["model"] == model and r["effort"] == effort and r["status"] == "ok"}


def _call(cmd: list[str], cwd: Path | str, timeout: int) -> tuple[str, str | None]:
    """執行一次 claude -p，回傳 (stdout, 錯誤訊息；沒有錯誤時是 None)。"""
    try:
        proc = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return out, f"逾時（{timeout} 秒）"
    return proc.stdout, (f"exit {proc.returncode}：{proc.stderr[-300:]}" if proc.returncode else None)


def _record(wid: str, model: str, effort: str, rnd: int, cond: str, qid: str, out: str, error: str | None,
            roots: list[str], known: set[str]) -> dict:
    """存下原始紀錄，並整理成 results.jsonl 的一列。"""
    raw = RUNS / wid / f"{model}-{effort}" / f"r{rnd}" / cond / f"{qid}.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(out, encoding="utf-8")
    row = summarize(parse_stream(out), roots, known)
    if error:
        row["status"], row["error"] = "error", error
    return {"world_id": wid, "model": model, "effort": effort, "round": rnd, "cond": cond, "qid": qid,
            "ts": datetime.now().isoformat(timespec="seconds"), **row}


def _execute(jobs: list, workers: int) -> None:
    """平行執行 jobs（每個都會回傳一列結果），邊完成邊寫入 results.jsonl。"""
    RESULTS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(job) for job in jobs]
        for i, fut in enumerate(as_completed(futures), 1):
            row = fut.result()
            with RESULTS_JSONL.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            mark = "✓" if row["status"] == "ok" else f"✗ {row['error']}"
            print(f"  [{i}/{len(jobs)}] {row['cond']} {row['qid']} {mark}")


def _questions() -> list[dict]:
    """取得題目；沒有題目，或沒通過 lab check，就停下來。"""
    world = load_world()
    if not world["questions"]:
        raise SystemExit("還沒有題目，請先依照 docs/codex-questions.md 出題")
    problems, _ = check_questions(world, load_bodies(world))
    if problems:
        raise SystemExit(f"題目還有 {len(problems)} 個問題，請先執行 uv run lab check")
    return world["questions"]


def preflight(maps: dict, model: str, effort: str) -> None:
    """開跑前檢查（設計第 6.3 節）：stage 狀態，以及每組一次檢查呼叫。"""
    root = stage_root()
    problems = stage_problems(root, maps, load_bodies(load_world()))
    for cond in CONDS:
        out, _ = _call(ask_cmd(PREFLIGHT_PROMPT, model, effort), root / cond, 180)
        problems += [f"{cond}：{p}" for p in isolation_problems(parse_stream(out))]
    if problems:
        raise SystemExit("開跑前檢查失敗：\n" + "\n".join(f"- {p}" for p in problems))
    print("開跑前檢查通過")


def ask_one(rnd: int, cond: str, q: dict, paths: dict[str, str], model: str, effort: str,
            timeout: int, wid: str) -> dict:
    cdir = stage_root() / cond
    out, error = _call(ask_cmd(PROMPT.format(question=q["question"]), model, effort), cdir, timeout)
    return _record(wid, model, effort, rnd, cond, q["id"], out, error,
                   [str(cdir), str(cdir.resolve())], set(paths.values()))


def run(rounds: int, model: str = "haiku", effort: str = "medium", workers: int = 4, timeout: int = 180) -> None:
    questions, maps, wid = _questions(), load_json(MAPPING), world_id()
    preflight(maps, model, effort)
    done = done_keys(read_rows(), wid, model, effort)
    for rnd in range(1, rounds + 1):
        tasks = [(cond, q) for cond in CONDS for q in questions if (rnd, cond, q["id"]) not in done]
        if not tasks:
            print(f"第 {rnd} 輪已經完成，跳過")
            continue
        random.Random(rnd).shuffle(tasks)
        print(f"第 {rnd} 輪：{len(tasks)} 次呼叫")
        _execute([partial(ask_one, rnd, cond, q, maps[cond], model, effort, timeout, wid) for cond, q in tasks],
                 workers)


def run_closed(model: str = "haiku", effort: str = "medium", workers: int = 4, timeout: int = 180) -> None:
    """閉卷對照：每題在空資料夾裡、不開工具問一次，找出憑記憶就答得出來的題目。"""
    questions, wid = _questions(), world_id()
    done = done_keys(read_rows(), wid, model, effort)
    todo = [q for q in questions if (1, CLOSED, q["id"]) not in done]
    if not todo:
        print("閉卷對照已經完成")
        return
    with tempfile.TemporaryDirectory() as tmp:
        if is_under_home(Path(tmp)) or leaking_ancestors(Path(tmp)):
            raise SystemExit(f"暫存資料夾不適合當閉卷環境：{tmp}")
        out, _ = _call(ask_cmd(PREFLIGHT_PROMPT, model, effort, tools=""), tmp, 180)
        if problems := isolation_problems(parse_stream(out), {"StructuredOutput"}):
            raise SystemExit("閉卷檢查失敗：\n" + "\n".join(f"- {p}" for p in problems))
        print(f"閉卷對照：{len(todo)} 題")

        def job(q: dict) -> dict:
            out, error = _call(ask_cmd(CLOSED_PROMPT.format(question=q["question"]), model, effort, tools=""),
                               tmp, timeout)
            return _record(wid, model, effort, 1, CLOSED, q["id"], out, error, [tmp], set())

        _execute([partial(job, q) for q in todo], workers)
