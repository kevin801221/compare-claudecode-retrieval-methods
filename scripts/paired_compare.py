"""逐題比較各組和 B 組的花費、輸入 token、工具呼叫：同一輪同一題，哪一組用得比較多。
README 的「幾乎每一題都比較貴」「A、B 互有高低」出自這裡。
用法：uv run python scripts/paired_compare.py（公開 repo 少了 7 頁 wiki，要加 LAB_WORLD_ID=1b2014a0e3f6，見 README）"""
from collections import defaultdict

from lab.common import COND_LABELS, CONDS, read_rows, world_id

BASE = "B-organized"
wid = world_id()
pairs = defaultdict(dict)   # (輪, 題) → {組別: 作答紀錄}
for r in read_rows():
    if r["world_id"] == wid and r["model"] == "haiku" and r["effort"] == "medium" and r["status"] == "ok" \
            and r["cond"] in CONDS:
        pairs[r["round"], r["qid"]][r["cond"]] = r

for cond in CONDS:
    if cond == BASE:
        continue
    both = [p for p in pairs.values() if cond in p and BASE in p]
    for key in ("cost_usd", "input_tokens", "tool_calls"):
        more = sum(p[cond][key] > p[BASE][key] for p in both)
        less = sum(p[cond][key] < p[BASE][key] for p in both)
        print(f"{COND_LABELS[cond]} 對 {COND_LABELS[BASE]}｜{key}：{len(both)} 題次，"
              f"比較多 {more}、比較少 {less}、一樣 {len(both) - more - less}")
