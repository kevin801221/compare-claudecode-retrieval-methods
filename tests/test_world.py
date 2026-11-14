from lab.world import check_questions

DOCS = [{"id": "sdk/hooks"}, {"id": "sdk/sessions"}, {"id": "lg/persistence"}]
BODIES = {"sdk/hooks": "Use PreToolUse hooks. Default timeout 60000 ms.",
          "sdk/sessions": "Resume with the resume option. Sessions persist.",
          "lg/persistence": "Use InMemorySaver as checkpointer. create_react_agent is deprecated; use create_agent."}


def q(**kw):
    base = {"id": "Q01", "type": "lookup", "question": "？", "must_include": ["60000"], "must_not_include": [],
            "gold_docs": ["sdk/hooks"], "probe_terms": [], "answerable": True}
    return base | kw


def check(*questions):
    return check_questions({"docs": DOCS, "questions": list(questions)}, BODIES)


def test_good_questions_pass():
    problems, warnings = check(
        q(),
        q(id="Q02", type="version", must_include=["create_agent"], must_not_include=["create_react_agent"],
          gold_docs=["lg/persistence"]),
        q(id="Q03", type="multi_doc", must_include=["60000", "InMemorySaver"], gold_docs=["sdk/hooks", "lg/persistence"]),
        q(id="Q04", type="unanswerable", must_include=[], gold_docs=[], probe_terms=["Agent SDK", "Ruby"],
          answerable=False),
    )
    assert problems == [] and warnings == []


def test_problems_are_reported():
    problems, _ = check(
        q(must_include=["99999"]),                                                   # 答案不在 gold 文件
        q(),                                                                          # id 重複
        q(id="Q03", gold_docs=["nope"]),                                              # 文件不存在
        q(id="Q04", type="multi_doc", must_include=["60000"], gold_docs=["sdk/hooks"]),  # 跨文件只有 1 份
        q(id="Q05", type="version", must_include=["create_agent"], gold_docs=["lg/persistence"]),  # 沒有舊寫法
        q(id="Q06", must_include=["persist"], gold_docs=["sdk/hooks"]),              # 答案其實在別份文件
    )
    text = "\n".join(problems)
    for expected in ["沒有完整答案", "id 重複", "找不到文件", "至少要 2 份", "must_not_include",
                     "完整答案也出現在 sdk/sessions"]:
        assert expected in text


def test_unanswerable_warning_when_terms_cooccur():
    _, warnings = check(q(type="unanswerable", must_include=[], gold_docs=[], probe_terms=["hooks", "timeout"],
                          answerable=False))
    assert warnings and "sdk/hooks" in warnings[0]
