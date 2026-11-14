"""題目檢查：check_questions 是純函式，check() 是 lab check 指令。規則見設計第 4.4、4.6 節。"""
from __future__ import annotations

from collections import Counter

from lab.common import QTYPE_LABELS, QTYPES, load_bodies, load_world, norm

FIELDS = ["id", "type", "question", "must_include", "must_not_include", "gold_docs", "probe_terms", "answerable"]


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
        if q["answerable"] != (q["type"] != "unanswerable"):
            problems.append(f"{qid}：answerable 與題型不符")
        if unknown := [d for d in q["gold_docs"] if d not in docs]:
            problems.append(f"{qid}：找不到文件 {', '.join(unknown)}")
            continue
        tokens = [norm(t) for t in q["must_include"]]
        if q["type"] == "unanswerable":
            if q["gold_docs"] or q["must_include"]:
                problems.append(f"{qid}：題庫裡沒有的題目，gold_docs 和 must_include 要留空")
            if len(q["probe_terms"]) != 2:
                problems.append(f"{qid}：probe_terms 要剛好 2 個")
            else:
                entity, attr = (norm(t) for t in q["probe_terms"])
                both = [d for d, b in normed.items() if entity in b and attr in b]
                if both:
                    warnings.append(f"{qid}：「{q['probe_terms'][0]}」和「{q['probe_terms'][1]}」同時出現在 "
                                    f"{', '.join(both[:5])}，請確認這些文件真的沒有回答這題")
            continue
        if not tokens:
            problems.append(f"{qid}：缺少答案字串")
            continue
        if q["type"] == "multi_doc":
            if len(q["gold_docs"]) < 2:
                problems.append(f"{qid}：跨文件題至少要 2 份 gold 文件")
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
        if q["type"] == "version" and not q["must_not_include"]:
            problems.append(f"{qid}：新舊版本題要有 must_not_include（舊的寫法）")
    return problems, warnings


def check() -> None:
    """lab check：印出題目統計、提醒和問題；有問題時以非 0 結束。"""
    world = load_world()
    if not world["questions"]:
        raise SystemExit("world/questions.json 還沒有題目，請先依照 docs/codex-questions.md 出題")
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
