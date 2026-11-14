from lab.score import answer_correct, score

PATHS = {"D1": "docs/a.md", "D2": "docs/b.md", "D3": "docs/old.md"}


def row(answer="", found=True, read=(), grep=(), sources=()):
    return {"answer": answer, "found": found, "files_read": list(read),
            "files_grep_content": list(grep), "sources": list(sources)}


def q(qtype, must=(), must_not=(), gold=("D1",), answerable=True):
    return {"type": qtype, "must_include": list(must), "must_not_include": list(must_not),
            "gold_docs": list(gold) if answerable else [], "answerable": answerable}


def test_lookup_correct_with_normalization():
    s = score(row("容量是 ４，２００ mAh", read=["docs/a.md"], sources=["docs/a.md"]), q("lookup", ["4200"]), PATHS)
    assert s["correct"] and s["retrieved"] and s["read_gold"] and s["citation_hit"]
    assert s["citation_precision"] == 1.0 and s["hallucinated"] is False and s["stale"] is None


def test_found_false_is_not_correct_even_if_text_matches():
    assert score(row("可能是 4200", found=False), q("lookup", ["4200"]), PATHS)["correct"] is False


def test_retrieved_via_grep_content_but_not_read():
    s = score(row("4200", grep=["docs/a.md"]), q("lookup", ["4200"]), PATHS)
    assert s["retrieved"] is True and s["read_gold"] is False


def test_citation_precision_partial():
    s = score(row("4200", read=["docs/a.md"], sources=["docs/a.md", "docs/b.md"]), q("lookup", ["4200"]), PATHS)
    assert s["citation_hit"] is True and s["citation_precision"] == 0.5


def test_index_in_sources_does_not_lower_precision():
    s = score(row("4200", read=["docs/a.md"], sources=["INDEX.md", "docs/a.md"]), q("lookup", ["4200"]), PATHS)
    assert s["citation_precision"] == 1.0


def test_any_gold_doc_counts_for_lookup():
    s = score(row("4200", read=["docs/b.md"], sources=["docs/b.md"]), q("lookup", ["4200"], gold=("D1", "D2")), PATHS)
    assert s["retrieved"] is True and s["citation_hit"] is True


def test_version_new_value_with_old_mentioned_is_correct():
    s = score(row("現在用 1200，以前是 1000"), q("version", ["1200"], ["1000"]), PATHS)
    assert s["correct"] is True and s["stale"] is False and s["hallucinated"] is False


def test_version_old_value_only_is_stale():
    s = score(row("每日補助 1000 元"), q("version", ["1200"], ["1000"]), PATHS)
    assert s["correct"] is False and s["stale"] is True and s["hallucinated"] is True


def test_multi_doc_needs_all_tokens_and_docs():
    question = q("multi_doc", ["4200", "24"], gold=("D1", "D2"))
    partial = score(row("4200 mAh", read=["docs/a.md"]), question, PATHS)
    assert partial["correct"] is False and partial["retrieved"] is False
    full = score(row("4200 mAh，保固 24 個月", read=["docs/a.md", "docs/b.md"]), question, PATHS)
    assert full["correct"] is True and full["retrieved"] is True


def test_unanswerable():
    question = q("unanswerable", answerable=False)
    good = score(row("找不到", found=False), question, PATHS)
    assert good["correct"] is True and good["hallucinated"] is False and good["retrieved"] is None
    bad = score(row("重量 3 公斤", found=True), question, PATHS)
    assert bad["correct"] is False and bad["hallucinated"] is True


def test_answer_correct_for_closed_book():
    assert answer_correct(row("4200 mAh"), q("lookup", ["4200"])) is True
    assert answer_correct(row("不知道", found=False), q("lookup", ["4200"])) is False
    assert answer_correct(row("不知道", found=False), q("unanswerable", answerable=False)) is True
