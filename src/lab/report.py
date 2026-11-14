"""統計：results.jsonl → results/report.md、results.csv、dashboard.json。"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from statistics import mean

from lab.common import (CLOSED, COND_LABELS, CONDS, MAPPING, QTYPE_LABELS, QTYPES, RESULTS, load_json,
                        load_world, read_rows, save_json, stage_root, world_id)
from lab.score import answer_correct, score

METRICS = [("correct", "答對率"), ("hallucinated", "幻覺率"), ("retrieved", "檢索命中率"),
           ("citation_hit", "引用命中率"), ("index_used", "讀了索引"), ("wiki_used", "讀了 wiki")]
EFFICIENCY = [("tool_calls", "平均工具呼叫"), ("files_read_n", "平均讀檔數"),
              ("duration_s", "平均秒數"), ("cost_usd", "平均花費 USD")]
PAIRS = [("A-messy", "C-indexed"), ("B-organized", "C-indexed"), ("A-messy", "B-organized"),
         ("B-organized", "D-wiki"), ("C-indexed", "D-wiki")]
CSV_FIELDS = ["model", "effort", "round", "cond", "qid", "type", "correct", "hallucinated", "stale",
              "retrieved", "read_gold", "citation_hit", "citation_precision", "index_used", "wiki_used", "tool_calls",
              "files_read_n", "duration_s", "cost_usd", "found", "answer"]


def _avg(values) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return mean(vals) if vals else None


def scored_rows(rows: list[dict], questions: dict[str, dict], maps: dict) -> list[dict]:
    return [{**r, **score(r, questions[r["qid"]], maps[r["cond"]]), "type": questions[r["qid"]]["type"],
             "files_read_n": len(r["files_read"]), "duration_s": (r["duration_ms"] or 0) / 1000}
            for r in rows]


def closed_rows_scored(rows: list[dict], questions: dict[str, dict]) -> list[dict]:
    return [{**r, "type": questions[r["qid"]]["type"], "correct": answer_correct(r, questions[r["qid"]]),
             "files_read_n": 0, "duration_s": (r["duration_ms"] or 0) / 1000} for r in rows]


def memorized_qids(questions: dict[str, dict], closed_rows: list[dict]) -> set[str] | None:
    """閉卷就答對的可回答題。還沒跑閉卷對照時回傳 None。"""
    if not closed_rows:
        return None
    return {r["qid"] for r in closed_rows
            if questions[r["qid"]]["answerable"] and answer_correct(r, questions[r["qid"]])}


def aggregate(rows: list[dict]) -> dict:
    """rows：已評分、status=ok 的列。回傳主表、題型表、逐題答對比例、多數決與成對比較。"""
    rounds = sorted({r["round"] for r in rows})
    keys = [k for k, _ in METRICS + EFFICIENCY]
    summary: dict[str, dict] = {}
    for cond in CONDS:
        per_round = []
        for rnd in rounds:
            rr = [r for r in rows if r["cond"] == cond and r["round"] == rnd]
            if rr:
                per_round.append({k: _avg([r.get(k) for r in rr]) for k in keys})
        summary[cond] = {}
        for k in keys:
            vals = [p[k] for p in per_round if p[k] is not None]
            summary[cond][k] = {"mean": mean(vals) if vals else None,
                                "min": min(vals, default=None), "max": max(vals, default=None)}
    outcomes: dict[str, dict[str, list[bool]]] = {}
    qtype: dict[str, str] = {}
    for r in rows:
        outcomes.setdefault(r["qid"], {}).setdefault(r["cond"], []).append(bool(r["correct"]))
        qtype[r["qid"]] = r["type"]
    props = {qid: {c: mean(map(float, v)) for c, v in conds.items()} for qid, conds in outcomes.items()}
    majority = {qid: {c: None if p == 0.5 else p > 0.5 for c, p in conds.items()}
                for qid, conds in props.items()}
    by_type = {c: {t: _avg([props[q][c] for q in props if qtype[q] == t and c in props[q]]) for t in QTYPES}
               for c in CONDS}
    paired = []
    for x, y in PAIRS:
        both = [q for q in majority if majority[q].get(x) is not None and majority[q].get(y) is not None]
        paired.append({"x": x, "y": y, "n": len(both),
                       "x_only": sum(1 for q in both if majority[q][x] and not majority[q][y]),
                       "y_only": sum(1 for q in both if majority[q][y] and not majority[q][x])})
    return {"rounds": rounds, "n_questions": len(props), "summary": summary, "by_type": by_type,
            "per_question": props, "majority": majority, "paired": paired}


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def _num(v: float | None, digits: int = 1) -> str:
    return "—" if v is None else f"{v:.{digits}f}"


def _summary_table(agg: dict, errors: dict[str, int]) -> list[str]:
    cols = METRICS + EFFICIENCY
    lines = ["| 組別 | " + " | ".join(label for _, label in cols) + " | 錯誤筆數 |",
             "|" + "---|" * (len(cols) + 2)]
    for cond in CONDS:
        s = agg["summary"][cond]
        cells = [f"{_pct(s[k]['mean'])}（{_pct(s[k]['min'])}–{_pct(s[k]['max'])}）" for k, _ in METRICS]
        cells += [_num(s[k]["mean"], 4 if k == "cost_usd" else 1) for k, _ in EFFICIENCY]
        lines.append(f"| {COND_LABELS[cond]} | " + " | ".join(cells) + f" | {errors.get(cond, 0)} |")
    return lines


def render_markdown(agg: dict, need: dict | None, memo: dict | None, model: str, effort: str,
                    errors: dict[str, int]) -> str:
    """memo：{"answerable": 可回答題數, "memorized": 閉卷答對題數}；還沒跑閉卷時是 None。"""
    lines = ["# Retrieval Lab 結果", "",
             f"- 模型：{model}（effort {effort}）",
             f"- 題數 n = {agg['n_questions']}，輪數 {len(agg['rounds'])}",
             f"- 產生時間：{datetime.now():%Y-%m-%d %H:%M}"]
    if memo is None:
        lines.append("- 閉卷對照：還沒執行（uv run lab closed）")
    else:
        lines.append(f"- 閉卷對照：{memo['answerable']} 題可回答題中，有 {memo['memorized']} 題不給文件也答對")
    lines += ["", "## 總表：全部題目（各輪平均，括號內為各輪最低–最高）", "", *_summary_table(agg, errors)]
    if need is not None:
        lines += ["", f"## 總表：需要查文件的題目（排除憑記憶答對的題目，n = {need['n_questions']}）", "",
                  *_summary_table(need, errors)]
    lines += ["", "## 各題型答對率", "",
              "| 組別 | " + " | ".join(QTYPE_LABELS[t] for t in QTYPES) + " |",
              "|" + "---|" * (len(QTYPES) + 1)]
    for cond in CONDS:
        cells = [_pct(agg["by_type"][cond][t]) for t in QTYPES]
        lines.append(f"| {COND_LABELS[cond]} | " + " | ".join(cells) + " |")
    lines += ["", "## 成對比較（每題取多輪多數決）", "",
              "| 比較 | 只有前者答對 | 只有後者答對 | 可比較題數 |", "|---|---|---|---|"]
    for p in agg["paired"]:
        lines.append(f"| {COND_LABELS[p['x']]} vs {COND_LABELS[p['y']]} | {p['x_only']} | {p['y_only']} | {p['n']} |")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:   # utf-8-sig：用 Excel 開啟時中文不會變亂碼
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["round"], r["cond"], r["qid"])))


def _clean(text: str) -> str:
    """去掉 stage 路徑和家目錄路徑，避免把本機資訊放上網頁。"""
    for cond in CONDS:
        text = text.replace(f"{stage_root()}/{cond}/", "")
    return text.replace(str(stage_root()), "").replace(str(Path.home()), "~")


def dashboard(agg: dict, need: dict | None, memorized: set[str] | None, rows: list[dict], closed: list[dict],
              world: dict, maps: dict, model: str, effort: str) -> dict:
    closed_by_q = {r["qid"]: r for r in closed}
    questions = []
    for q in world["questions"]:
        results = {cond: [{"round": r["round"], "answer": _clean(r["answer"]), "found": r["found"],
                           "correct": r["correct"], "retrieved": r["retrieved"],
                           "index_used": r.get("index_used"), "wiki_used": r.get("wiki_used"),
                           "files_read": r["files_read"],
                           "files_grep": r["files_grep_content"], "tool_calls": r["tool_calls"],
                           "duration_s": round(r["duration_s"], 1)}
                          for r in sorted(rows, key=lambda r: r["round"])
                          if r["qid"] == q["id"] and r["cond"] == cond]
                   for cond in CONDS}
        c = closed_by_q.get(q["id"])
        questions.append({"id": q["id"], "type": q["type"], "question": q["question"],
                          "gold_answer": "、".join(q["must_include"]) or "（文件中沒有，應該回答找不到）",
                          "gold_files": {cond: [maps[cond][d] for d in q["gold_docs"]] for cond in CONDS},
                          "memorized": memorized is not None and q["id"] in memorized,
                          "closed": None if c is None else {"answer": _clean(c["answer"]), "found": c["found"],
                                                            "correct": c["correct"]},
                          "results": results})
    return {"generated_at": datetime.now().isoformat(timespec="minutes"), "model": model, "effort": effort,
            "claude_versions": sorted({r["claude_version"] for r in rows if r.get("claude_version")}),
            "n_questions": agg["n_questions"], "rounds": agg["rounds"],
            "memorized_count": None if memorized is None else len(memorized),
            "conds": [{"id": c, "label": COND_LABELS[c]} for c in CONDS],
            "qtypes": [{"id": t, "label": QTYPE_LABELS[t]} for t in QTYPES],
            "summary": agg["summary"], "summary_need_docs": need["summary"] if need else None,
            "n_need_docs": need["n_questions"] if need else None,
            "by_type": agg["by_type"], "paired": agg["paired"], "questions": questions}


def report(model: str = "haiku", effort: str = "medium") -> None:
    world, maps, wid = load_world(), load_json(MAPPING), world_id()
    questions = {q["id"]: q for q in world["questions"]}
    rows = [r for r in read_rows() if r["world_id"] == wid and r["model"] == model and r["effort"] == effort]
    main = [r for r in rows if r["cond"] in CONDS]
    ok = [r for r in main if r["status"] == "ok"]
    if not ok:
        raise SystemExit("還沒有可用的結果，請先執行 lab run")
    ok_keys = {(r["round"], r["cond"], r["qid"]) for r in ok}
    errors = {c: len({(r["round"], r["qid"]) for r in main if r["cond"] == c and r["status"] != "ok"
                      and (r["round"], r["cond"], r["qid"]) not in ok_keys}) for c in CONDS}
    closed = closed_rows_scored([r for r in rows if r["cond"] == CLOSED and r["status"] == "ok"], questions)
    memorized = memorized_qids(questions, closed)
    scored = scored_rows(ok, questions, maps)
    agg = aggregate(scored)
    need = None if memorized is None else aggregate([r for r in scored if r["qid"] not in memorized])
    memo = None if memorized is None else {"answerable": sum(1 for q in questions.values() if q["answerable"]),
                                           "memorized": len(memorized)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    text = render_markdown(agg, need, memo, model, effort, errors)
    (RESULTS / "report.md").write_text(text, encoding="utf-8")
    write_csv(RESULTS / "results.csv", scored + closed)
    save_json(RESULTS / "dashboard.json", dashboard(agg, need, memorized, scored, closed, world, maps, model, effort))
    print(text)
