"""題目檢查：check_questions 是純函式，check() 是 lab check 指令。規則見設計第 4.4、4.6 節。"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from lab.common import (MULTI_DOC_TYPES, QTYPE_LABELS, QTYPES, UNANSWERABLE_TYPES, load_bodies, load_json,
                        load_world, norm)

FIELDS = ["id", "type", "question", "must_include", "must_not_include", "gold_docs", "probe_terms", "answerable"]
CONTRAST = {"version": "舊的寫法", "confusable": "另一個框架或語言的寫法"}   # 這些題型要填 must_not_include


def check_questions(world: dict, bodies: dict[str, str]) -> tuple[list[str], list[str]]:
    """回傳 (問題, 提醒)。有「問題」就不能開跑；「提醒」要在審題時看過。"""
    docs = {d["id"] for d in world["docs"]}
    normed = {doc_id: norm(body) for doc_id, body in bodies.items()}
    problems: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for q in world["questions"]:
        qid = str(q.get("id", "?"))
        if missing := [k for k in FIELDS if k not in q]:
            problems.append(f"{qid}：缺少欄位 {', '.join(missing)}")
            continue
        if qid in seen:
            problems.append(f"{qid}：id 重複")
        seen.add(qid)
        if q["type"] not in QTYPES:
            problems.append(f"{qid}：未知題型 {q['type']}")
            continue
        if q["answerable"] != (q["type"] not in UNANSWERABLE_TYPES):
            problems.append(f"{qid}：answerable 與題型不符")
        if unknown := [d for d in q["gold_docs"] if d not in docs]:
            problems.append(f"{qid}：找不到文件 {', '.join(unknown)}")
            continue
        tokens = [norm(t) for t in q["must_include"]]
        label = QTYPE_LABELS[q["type"]]
        if q["type"] in UNANSWERABLE_TYPES:
            if q["gold_docs"] or q["must_include"]:
                problems.append(f"{qid}：題庫裡沒有的題目，gold_docs 和 must_include 要留空")
            if len(q["probe_terms"]) != 2:
                problems.append(f"{qid}：probe_terms 要剛好 2 個")
            else:
                entity, attr = (norm(t) for t in q["probe_terms"])
                if q["type"] == "near_miss" and not any(entity in b for b in normed.values()):
                    problems.append(f"{qid}：近似陷阱題的主題「{q['probe_terms'][0]}」要出現在文件裡")
                both = [d for d, b in normed.items() if entity in b and attr in b]
                if both:
                    warnings.append(f"{qid}：「{q['probe_terms'][0]}」和「{q['probe_terms'][1]}」同時出現在 "
                                    f"{', '.join(both[:5])}，請確認這些文件真的沒有回答這題")
            continue
        if not tokens:
            problems.append(f"{qid}：缺少答案字串")
            continue
        if q["type"] in MULTI_DOC_TYPES:
            if len(q["gold_docs"]) < 2:
                problems.append(f"{qid}：{label}題至少要 2 份 gold 文件")
            if q["type"] == "aggregate" and (nums := [raw for raw in q["must_include"] if raw.strip().isdigit()]):
                problems.append(f"{qid}：彙整題的答案字串只放項目名稱，不要放個數（{'、'.join(nums)}）")
            for token, raw in zip(tokens, q["must_include"]):
                if not any(token in normed[d] for d in q["gold_docs"]):
                    problems.append(f"{qid}：答案「{raw}」不在任何 gold 文件裡")
            for d in q["gold_docs"]:
                if not any(token in normed[d] for token in tokens):
                    problems.append(f"{qid}：gold 文件 {d} 沒有任何答案字串")
            continue
        if not q["gold_docs"]:
            problems.append(f"{qid}：缺少 gold 文件")
            continue
        for d in q["gold_docs"]:
            if not all(token in normed[d] for token in tokens):
                problems.append(f"{qid}：gold 文件 {d} 沒有完整答案")
        extra = [d for d, b in normed.items() if d not in q["gold_docs"] and all(t in b for t in tokens)]
        if extra:
            problems.append(f"{qid}：完整答案也出現在 {', '.join(extra[:5])}，請加進 gold_docs 或換一個答案字串")
        if q["type"] in CONTRAST and not q["must_not_include"]:
            problems.append(f"{qid}：{label}題要有 must_not_include（{CONTRAST[q['type']]}）")
        if q["type"] == "confusable":   # 兩種寫法都寫出來會被判錯，所以不能互為子字串，另一種寫法也要真的存在
            for raw in q["must_not_include"]:
                other = norm(raw)
                if any(other in t or t in other for t in tokens):
                    problems.append(f"{qid}：「{raw}」和答案字串互為子字串，程式會誤判")
                if not any(other in b for b in normed.values()):
                    problems.append(f"{qid}：另一種寫法「{raw}」不在任何文件裡")
    return problems, warnings


def check(path: Path | None = None) -> None:
    """lab check：印出題目統計、提醒和問題；有問題時以非 0 結束。path：改檢查另一個題目檔（例如試題）。"""
    world = load_world()
    if path is not None:
        world["questions"] = load_json(path)
    if not world["questions"]:
        raise SystemExit(f"{path or 'world/questions.json'} 還沒有題目，請先依照 docs/codex-questions.md 出題")
    problems, warnings = check_questions(world, load_bodies(world))
    counts = Counter(q.get("type") for q in world["questions"])
    print(f"文件 {len(world['docs'])} 份，題目 {len(world['questions'])} 題："
          + "、".join(f"{QTYPE_LABELS.get(t, t)} {n}" for t, n in counts.items()))
    for w in warnings:
        print(f"  提醒：{w}")
    for p in problems:
        print(f"  問題：{p}")
    if problems:
        raise SystemExit(f"有 {len(problems)} 個問題要修正")
    print("沒有問題" + (f"（有 {len(warnings)} 個提醒，審題時請一併確認）" if warnings else ""))
