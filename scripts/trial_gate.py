"""試題閘門（設計第 16 節）：每題四組各跑 2 次，加上閉卷 1 次。
結果寫到 results/trial_rows.jsonl，不進正式的 results.jsonl。可以續跑。用法：uv run python scripts/trial_gate.py"""
from __future__ import annotations

import json
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path

from lab.common import (CLOSED, CONDS, MAPPING, RESULTS, WORLD, is_under_home, leaking_ancestors, load_bodies,
                        load_json, load_world, stage_root)
from lab.run import CLOSED_PROMPT, PREFLIGHT_PROMPT, PROMPT, _call, _record, ask_cmd, aux_files, preflight
from lab.trace import isolation_problems, parse_stream
from lab.world import check_questions

MODEL, EFFORT, TIMEOUT, WID = "haiku", "medium", 180, "trial"   # 和正式評測相同的參數
QUESTIONS, OUT = WORLD / "trial_questions.json", RESULTS / "trial_rows.jsonl"


def main() -> None:
    qs = load_json(QUESTIONS)
    world = load_world() | {"questions": qs}
    if problems := check_questions(world, load_bodies(world))[0]:
        raise SystemExit("試題還有問題：\n" + "\n".join(problems))
    maps = load_json(MAPPING)
    preflight(maps, MODEL, EFFORT)
    done = {(r["round"], r["cond"], r["qid"]) for r in map(json.loads, OUT.read_text(encoding="utf-8").splitlines())
            if r["status"] == "ok"} if OUT.exists() else set()
    with tempfile.TemporaryDirectory() as tmp:
        if is_under_home(Path(tmp)) or leaking_ancestors(Path(tmp)):
            raise SystemExit(f"暫存資料夾不適合當閉卷環境：{tmp}")
        out, _ = _call(ask_cmd(PREFLIGHT_PROMPT, MODEL, EFFORT, tools=""), tmp, 180)
        if problems := isolation_problems(parse_stream(out), {"StructuredOutput"}):
            raise SystemExit("閉卷檢查失敗：\n" + "\n".join(problems))

        def ask(rnd: int, cond: str, q: dict) -> dict:
            cdir = stage_root() / cond
            out, err = _call(ask_cmd(PROMPT.format(question=q["question"]), MODEL, EFFORT), cdir, TIMEOUT)
            return _record(WID, MODEL, EFFORT, rnd, cond, q["id"], out, err, [str(cdir), str(cdir.resolve())],
                           set(maps[cond].values()), aux_files(cdir))

        def closed(q: dict) -> dict:
            out, err = _call(ask_cmd(CLOSED_PROMPT.format(question=q["question"]), MODEL, EFFORT, tools=""), tmp, TIMEOUT)
            return _record(WID, MODEL, EFFORT, 1, CLOSED, q["id"], out, err, [tmp], set())

        jobs = [partial(ask, rnd, c, q) for rnd in (1, 2) for c in CONDS for q in qs if (rnd, c, q["id"]) not in done]
        jobs += [partial(closed, q) for q in qs if (1, CLOSED, q["id"]) not in done]
        print(f"試題 {len(qs)} 題，要跑 {len(jobs)} 次")
        with ThreadPoolExecutor(4) as pool, OUT.open("a", encoding="utf-8") as f:
            for i, fut in enumerate(as_completed([pool.submit(j) for j in jobs]), 1):
                row = fut.result()
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                print(f"  [{i}/{len(jobs)}] {row['cond']} r{row['round']} {row['qid']} {row['status']}")


if __name__ == "__main__":
    main()
