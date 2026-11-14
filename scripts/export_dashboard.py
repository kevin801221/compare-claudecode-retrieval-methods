"""匯出 Retrieval Lab 網頁用的資料集到 results/dash/*.json。每個檔案是 {rows, meta}，meta 附上這支程式本身。
用法：uv run python scripts/export_dashboard.py"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean, median

from lab.common import (CLOSED, COND_LABELS, CONDS, INDEX_BUDGET, MAPPING, QTYPE_LABELS, RESULTS, RUNS, WORLD, load_json,
                        load_world, read_rows, stage_root, world_id)
from lab.report import aggregate, closed_rows_scored, memorized_qids, scored_rows
from lab.score import answer_correct, score
from lab.trace import parse_stream, relpath, touched_files

MODEL, EFFORT = "haiku", "medium"
OUT = RESULTS / "dash"
CODE = Path(__file__).read_text(encoding="utf-8")
ENTRY = {"INDEX.md", "wiki/index.md"}
# 入口檔截斷：2026-11-14 用 Read 工具實測（設計文件第 15 節），瘦身前後各讀一次，記錄第一次 Read 看到的行數
ENTRY_FILES = [
    {"cond": "C-indexed", "label": "C 索引", "file": "INDEX.md", "total_lines": 218, "visible_before": 141,
     "visible_after": 218, "chars_before": 53349, "hidden_before": "langchain 後段 32 筆、langgraph 全部 44 筆"},
    {"cond": "D-wiki", "label": "D wiki", "file": "wiki/index.md", "total_lines": 100, "visible_before": 84,
     "visible_after": 100, "chars_before": 37661, "hidden_before": "versions、comparisons 兩整類"},
]


def pct(v: float | None) -> float | None:
    return None if v is None else round(v * 100, 1)


def write(name: str, rows: list[dict], inputs: str, note: str | None = None) -> None:
    meta = [{"label": "export_dashboard.py", "value": CODE, "type": "code", "lang": "python"},
            {"label": "輸入", "value": inputs}] + ([{"label": "說明", "value": note}] if note else [])
    (OUT / f"{name}.json").write_text(json.dumps({"rows": rows, "meta": meta}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")


def first_gold(row: dict, q: dict, paths: dict[str, str]) -> tuple[str, int | None]:
    """第一次碰到正解文件的是哪一步、靠什麼找到。回傳 (分類, 第幾次工具呼叫)。"""
    cond = row["cond"]
    raw = (RUNS / row["world_id"] / f"{MODEL}-{EFFORT}" / f"r{row['round']}" / cond / f"{row['qid']}.jsonl")
    calls = parse_stream(raw.read_text(encoding="utf-8"))["calls"]
    root = stage_root() / cond
    roots, known = [str(root), str(root.resolve())], set(paths.values())
    gold = {paths[d] for d in q["gold_docs"]}
    seen = {"grep": "", "entry": ""}   # 之前的工具輸出：Grep/Glob 的、入口檔與 wiki 頁的

    def led_by(path: str) -> str:
        by_grep, by_entry = path in seen["grep"], path in seen["entry"]
        return "兩者都列過" if by_grep and by_entry else "入口檔／wiki 帶路" if by_entry \
            else "Grep 結果帶路" if by_grep else "其他"

    for i, c in enumerate(calls, 1):
        read, grep = touched_files([c], roots, known)
        if hit := gold & set(grep):
            target = str(c["input"].get("path", "") or ".").rstrip("/")
            target = "." if target in [x.rstrip("/") for x in roots] else relpath(target, roots).rstrip("/") or "."
            if target in known:
                return led_by(target), i
            return ("Grep 搜全部" if target in (".", "docs") else "Grep 限定資料夾"), i
        if hit := gold & set(read):
            return led_by(next(iter(hit))), i
        if c["name"] in ("Grep", "Glob"):
            seen["grep"] += c["text"]
        elif c["name"] == "Read" and (p := relpath(str(c["input"].get("file_path", "")), roots)) \
                and (p in ENTRY or p.startswith("wiki/")):
            seen["entry"] += c["text"]
    return "沒碰到正解", None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    world, maps, wid = load_world(), load_json(MAPPING), world_id()
    questions = {q["id"]: q for q in world["questions"]}
    rows = [r for r in read_rows() if r["world_id"] == wid and r["model"] == MODEL and r["effort"] == EFFORT]
    ok = [r for r in rows if r["cond"] in CONDS and r["status"] == "ok"]
    closed = closed_rows_scored([r for r in rows if r["cond"] == CLOSED and r["status"] == "ok"], questions)
    memorized = memorized_qids(questions, closed) or set()
    scored = scored_rows(ok, questions, maps)
    agg = aggregate(scored)
    inputs = "results/results.jsonl、runs/（原始紀錄）、world/questions.json、build/mapping.json"

    paths_by: dict[str, Counter] = {c: Counter() for c in CONDS}
    steps: dict[str, list[int]] = {c: [] for c in CONDS}
    for r in ok:
        q = questions[r["qid"]]
        if q["answerable"]:
            how, step = first_gold(r, q, maps[r["cond"]])
            paths_by[r["cond"]][how] += 1
            if step:
                steps[r["cond"]].append(step)

    summary = []
    for c in CONDS:
        s, rr = agg["summary"][c], [r for r in scored if r["cond"] == c]
        summary.append({"cond": c, "label": COND_LABELS[c], "answers": len(rr),
                        "correct_pct": pct(s["correct"]["mean"]), "correct_min_pct": pct(s["correct"]["min"]),
                        "correct_max_pct": pct(s["correct"]["max"]), "hallucinated_pct": pct(s["hallucinated"]["mean"]),
                        "retrieved_pct": pct(s["retrieved"]["mean"]), "citation_pct": pct(s["citation_hit"]["mean"]),
                        "tool_calls": round(s["tool_calls"]["mean"], 2), "files_read": round(s["files_read_n"]["mean"], 2),
                        "seconds": round(s["duration_s"]["mean"], 1), "cost_usd": round(s["cost_usd"]["mean"], 4),
                        "input_tokens": round(mean(r["input_tokens"] for r in rr)),
                        "steps_to_gold": median(steps[c]),
                        "errors": len({(r["round"], r["qid"]) for r in rows if r["cond"] == c and r["status"] != "ok"}
                                      - {(r["round"], r["qid"]) for r in rr})})
    base = next(r for r in summary if r["cond"] == "B-organized")
    for r in summary:
        r["cost_vs_b"] = round(r["cost_usd"] / base["cost_usd"], 1)
        r["tokens_vs_b"] = round(r["input_tokens"] / base["input_tokens"], 1)
    write("summary", summary, inputs, "每組各輪的平均再平均；花費是換算成 API 價格的估計。steps_to_gold 是第一次碰到正解文件的工具呼叫序號（中位數）。errors 是沒交出符合格式答案的作答次數，不計入其他欄位。")

    write("by_type", [{"type": t, "type_label": QTYPE_LABELS[t], **{c: pct(agg["by_type"][c][t]) for c in CONDS}}
                      for t in agg["types"]], inputs, "各題先算多輪的答對比例，再對同題型的題目取平均；單位是 %。")

    order = ["Grep 搜全部", "Grep 限定資料夾", "Grep 結果帶路", "入口檔／wiki 帶路", "兩者都列過", "其他", "沒碰到正解"]
    write("first_gold", [{"cond": c, "label": COND_LABELS[c], "how": h, "answers": paths_by[c][h]}
                         for c in CONDS for h in order if paths_by[c][h]], inputs,
          "只算可回答題。依第一次碰到正解文件的那一步分類：Grep 的搜尋範圍，或之前哪種輸出列過這份文件的路徑。")

    for e in ENTRY_FILES:   # 瘦身後的字元數：直接量各組資料夾裡的入口檔
        e["chars_after"] = len((stage_root() / e["cond"] / e["file"]).read_text(encoding="utf-8"))
    write("entry_files", ENTRY_FILES, "設計文件第 15 節（Read 工具實測）；瘦身後字元數量自各組資料夾",
          "瘦身規則：入口檔不超過 28,000 字元；不放標題，關鍵字只取前 n 個。")

    trial_qs = {q["id"]: q for q in load_json(WORLD / "trial_questions.json")}
    latest = {(r["round"], r["cond"], r["qid"]): r
              for r in map(json.loads, (RESULTS / "trial_rows.jsonl").read_text(encoding="utf-8").splitlines())}
    gate = Counter()
    tries = Counter()
    for r in latest.values():
        q = trial_qs[r["qid"]]
        right = r["status"] == "ok" and (answer_correct(r, q) if r["cond"] == CLOSED
                                         else score(r, q, maps[r["cond"]])["correct"])
        tries[q["type"], r["cond"]] += 1
        gate[q["type"], r["cond"]] += not right
    write("gate", [{"type": t, "type_label": QTYPE_LABELS[t], "attempts": tries[t, CONDS[0]],
                    "closed_attempts": tries[t, CLOSED], **{c: gate[t, c] for c in CONDS + [CLOSED]}}
                   for t in ["aggregate", "confusable", "near_miss"]],
          "results/trial_rows.jsonl、world/trial_questions.json", "逾時或出錯算答錯。")

    write("questions", [{"qid": qid, "type_label": QTYPE_LABELS[q["type"]], "question": q["question"],
                         "gold": "、".join(q["must_include"]) or "（文件中沒有，應回答找不到）",
                         "closed": "答對" if qid in memorized else "答錯" if q["answerable"] else "—",
                         **{c: f"{sum(r['correct'] for r in scored if r['qid'] == qid and r['cond'] == c)}/"
                               f"{sum(1 for r in scored if r['qid'] == qid and r['cond'] == c)}" for c in CONDS}}
                        for qid, q in sorted(questions.items())], inputs)

    total = rows + [r for r in map(json.loads, (RESULTS / "trial_rows.jsonl").read_text(encoding="utf-8").splitlines())]
    write("facts", [{"docs": len(world["docs"]), "questions": len(questions),
                     "answerable": sum(q["answerable"] for q in questions.values()), "rounds": len(agg["rounds"]),
                     "memorized": len(memorized), "calls": len(total),
                     "cost_total": round(sum(r.get("cost_usd") or 0 for r in total), 2),
                     "wiki_pages": 88, "wiki_minutes": 91, "read_cap_chars": 33000, "index_budget": INDEX_BUDGET,
                     "keywords_kept": 3,
                     "claude_version": "、".join(sorted({r["claude_version"] for r in ok if r.get("claude_version")}))}],
          inputs + "、results/trial_rows.jsonl", "wiki 頁數與建置時間來自 Antigravity 產出的檔案時間（設計文件第 14 節）。read_cap_chars 是 Read 工具實測的截斷點（約 3.3 萬字元，設計文件第 15 節）；keywords_kept 是瘦身後每筆保留的關鍵字數。")
    print(f"完成：{OUT}（{len(list(OUT.glob('*.json')))} 個檔案），作答 {len(ok)} 筆，輪數 {agg['rounds']}")


if __name__ == "__main__":
    main()
