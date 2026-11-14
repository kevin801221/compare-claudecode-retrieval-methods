"""評分（純函式）：程式比對，不用 LLM 評審。定義見設計第 7 節。"""
from __future__ import annotations

from lab.common import norm

NON_DOCS = {"INDEX.md", "CLAUDE.md"}   # 索引和指引不是文件，不計入引用


def answer_correct(row: dict, q: dict) -> bool:
    """可回答題：found 而且所有答案字串都出現；不可回答題：found=false。閉卷組也用這個判斷。"""
    if not q["answerable"]:
        return not row["found"]
    answer = norm(row["answer"])
    return row["found"] and all(norm(t) in answer for t in q["must_include"])


def score(row: dict, q: dict, paths: dict[str, str]) -> dict:
    """row：results.jsonl 的一列；q：題目；paths：該組的 doc_id → 相對路徑。不適用的指標回傳 None。"""
    if not q["answerable"]:
        return {"correct": not row["found"], "hallucinated": row["found"], "stale": None,
                "retrieved": None, "read_gold": None, "citation_hit": None, "citation_precision": None}
    answer = norm(row["answer"])
    gold = {paths[d] for d in q["gold_docs"]}
    need_all = q["type"] == "multi_doc"   # 跨文件題要全部找到；其他題型找到任一份就算

    def hit(files: set[str]) -> bool:
        return gold <= files if need_all else bool(gold & files)

    read = set(row["files_read"])
    sources = {s for s in row["sources"] if s not in NON_DOCS and not s.startswith("wiki/")}   # wiki 頁面也不是文件
    has_new = all(norm(t) in answer for t in q["must_include"])
    stale = None
    if q["type"] == "version":
        stale = (not has_new) and any(norm(t) in answer for t in q["must_not_include"])
    return {
        "correct": row["found"] and has_new,
        "hallucinated": bool(stale),
        "stale": stale,
        "retrieved": hit(read | set(row["files_grep_content"])),
        "read_gold": hit(read),
        "citation_hit": hit(sources),
        "citation_precision": len(sources & gold) / len(sources) if sources else 0.0,
    }
