"""試題閘門的統計（設計第 16 節）：各題型 × 各組的答錯次數，以及需要逐筆人工判讀的作答。
用法：uv run python scripts/trial_report.py [--detail]"""
from __future__ import annotations

import json
import sys

from lab.common import CLOSED, CONDS, COND_LABELS, MAPPING, QTYPE_LABELS, RESULTS, WORLD, load_json, norm
from lab.score import answer_correct, score

TYPES = ["aggregate", "confusable", "near_miss"]


def main(detail: bool) -> None:
    qs = {q["id"]: q for q in load_json(WORLD / "trial_questions.json")}
    maps = load_json(MAPPING)
    rows = [json.loads(line) for line in (RESULTS / "trial_rows.jsonl").read_text(encoding="utf-8").splitlines()]
    latest = {(r["round"], r["cond"], r["qid"]): r for r in rows}   # 續跑時以最後一筆為準
    scored = []
    for r in latest.values():
        q = qs[r["qid"]]
        if r["status"] != "ok":   # 逾時或其他錯誤：算答錯
            s = {"correct": False, "hallucinated": None, "retrieved": None}
        elif r["cond"] == CLOSED:
            s = {"correct": answer_correct(r, q), "hallucinated": None, "retrieved": None}
        else:
            s = score(r, q, maps[r["cond"]])
        scored.append({**r, **s, "type": q["type"]})

    print("## 各題型答錯次數（每格 = 答錯 / 作答次數；閉卷每題 1 次）\n")
    print("| 題型 | " + " | ".join(COND_LABELS[c] for c in CONDS + [CLOSED]) + " |")
    print("|---|" + "---|" * (len(CONDS) + 1))
    for t in TYPES:
        cells = []
        for c in CONDS + [CLOSED]:
            rr = [r for r in scored if r["type"] == t and r["cond"] == c]
            wrong = sum(not r["correct"] for r in rr)
            errs = sum(r["status"] != "ok" for r in rr)
            cells.append(f"{wrong}/{len(rr)}" + (f"（含錯誤 {errs}）" if errs else ""))
        print(f"| {QTYPE_LABELS[t]} | " + " | ".join(cells) + " |")

    print("\n## 逐題答錯次數（四組各 2 次）\n")
    for qid, q in sorted(qs.items()):
        per = {c: sum(not r["correct"] for r in scored if r["qid"] == qid and r["cond"] == c) for c in CONDS}
        cl = next((r for r in scored if r["qid"] == qid and r["cond"] == CLOSED), None)
        print(f"- {qid} {QTYPE_LABELS[q['type']]}：" + "、".join(f"{c[0]} {n}" for c, n in per.items())
              + f"；閉卷{'答對' if cl and cl['correct'] else '答錯'}")

    if not detail:
        return
    print("\n## 需要逐筆人工判讀的作答\n")
    for r in sorted(scored, key=lambda r: (r["qid"], r["cond"], r["round"])):
        q = qs[r["qid"]]
        if r["cond"] == CLOSED:
            continue
        answer = norm(r.get("answer") or "")
        both = q["type"] == "confusable" and all(norm(t) in answer for t in q["must_include"]) \
            and any(norm(t) in answer for t in q["must_not_include"])
        flag = (q["type"] == "near_miss" and r.get("found")) or both \
            or (q["type"] == "aggregate" and not r["correct"]) or r["status"] != "ok"
        if not flag:
            continue
        missing = [t for t in q["must_include"] if norm(t) not in answer]
        print(f"### {r['qid']} {r['cond']} r{r['round']}（{QTYPE_LABELS[q['type']]}）"
              f"{' 兩種寫法都有' if both else ''}{' found=true' if q['type'] == 'near_miss' and r.get('found') else ''}"
              f"{' 錯誤：' + str(r.get('error')) if r['status'] != 'ok' else ''}")
        if missing and q["answerable"]:
            print(f"缺少：{missing}")
        print(f"sources：{r.get('sources')}")
        print((r.get("answer") or "").strip() + "\n")


if __name__ == "__main__":
    main("--detail" in sys.argv)
