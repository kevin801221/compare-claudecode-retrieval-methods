from lab.report import aggregate, memorized_qids


def r(cond, qid, rnd, correct, qtype="lookup", **kw):
    base = {"cond": cond, "qid": qid, "round": rnd, "type": qtype, "correct": correct, "hallucinated": False,
            "retrieved": correct, "citation_hit": correct, "tool_calls": 2, "files_read_n": 1,
            "duration_s": 3.0, "cost_usd": 0.01, "index_used": False, "wiki_used": False}
    return base | kw


def test_d_group_has_wiki_metric_and_pairs():
    rows = [r("C-indexed", "Q1", 1, False), r("D-wiki", "Q1", 1, True, wiki_used=True)]
    agg = aggregate(rows)
    assert agg["summary"]["D-wiki"]["wiki_used"]["mean"] == 1.0
    pair = next(p for p in agg["paired"] if (p["x"], p["y"]) == ("C-indexed", "D-wiki"))
    assert (pair["x_only"], pair["y_only"], pair["n"]) == (0, 1, 1)


def test_aggregate_rates_majority_and_pairs():
    rows = []
    for rnd in (1, 2, 3):
        rows += [r("A-messy", "Q1", rnd, rnd == 1), r("C-indexed", "Q1", rnd, True),
                 r("A-messy", "Q2", rnd, True), r("C-indexed", "Q2", rnd, False),
                 r("B-organized", "Q1", rnd, True), r("B-organized", "Q2", rnd, True)]
    rows.append(r("A-messy", "Q3", 1, True, qtype="unanswerable", retrieved=None, citation_hit=None))
    agg = aggregate(rows)
    assert agg["rounds"] == [1, 2, 3] and agg["n_questions"] == 3
    a = agg["summary"]["A-messy"]["correct"]
    assert round(a["mean"], 3) == round((1.0 + 0.5 + 0.5) / 3, 3)   # 第 1 輪 3/3，第 2、3 輪 1/2
    assert a["min"] == 0.5 and a["max"] == 1.0
    assert agg["majority"]["Q1"]["A-messy"] is False and agg["majority"]["Q1"]["C-indexed"] is True
    pair = next(p for p in agg["paired"] if (p["x"], p["y"]) == ("A-messy", "C-indexed"))
    assert (pair["x_only"], pair["y_only"], pair["n"]) == (1, 1, 2)   # Q2 只有 A 對，Q1 只有 C 對
    assert agg["by_type"]["A-messy"]["unanswerable"] == 1.0
    assert agg["summary"]["A-messy"]["retrieved"]["mean"] is not None


def test_majority_tie_is_unstable():
    rows = [r("A-messy", "Q1", 1, True), r("A-messy", "Q1", 2, False)]
    assert aggregate(rows)["majority"]["Q1"]["A-messy"] is None


def test_memorized_qids():
    questions = {"Q1": {"type": "lookup", "answerable": True, "must_include": ["4200"]},
                 "Q2": {"type": "lookup", "answerable": True, "must_include": ["999"]},
                 "Q3": {"type": "unanswerable", "answerable": False, "must_include": []}}
    closed = [{"qid": "Q1", "answer": "4200", "found": True}, {"qid": "Q2", "answer": "不知道", "found": False},
              {"qid": "Q3", "answer": "不知道", "found": False}]
    assert memorized_qids(questions, closed) == {"Q1"}   # 不可回答題不算「憑記憶」
    assert memorized_qids(questions, []) is None
