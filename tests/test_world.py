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


def test_new_types_pass():
    problems, warnings = check(
        q(id="Q05", type="aggregate", must_include=["PreToolUse", "InMemorySaver"],
          gold_docs=["sdk/hooks", "lg/persistence"]),
        q(id="Q06", type="confusable", must_include=["create_agent"], must_not_include=["PreToolUse"],
          gold_docs=["lg/persistence"]),
        q(id="Q07", type="near_miss", must_include=[], gold_docs=[], probe_terms=["checkpointer", "TTL"],
          answerable=False),
    )
    assert problems == [] and warnings == []


def test_new_type_problems():
    problems, _ = check(
        q(id="Q01", type="aggregate", must_include=["60000"], gold_docs=["sdk/hooks"]),               # 彙整只有 1 份
        q(id="Q02", type="aggregate", must_include=["PreToolUse", "3"], gold_docs=["sdk/hooks", "lg/persistence"]),
        q(id="Q03", type="confusable", must_include=["create_agent"], gold_docs=["lg/persistence"]),   # 沒有另一種寫法
        q(id="Q04", type="confusable", must_include=["InMemorySaver"], must_not_include=["Saver"],
          gold_docs=["lg/persistence"]),                                                              # 互為子字串
        q(id="Q05", type="confusable", must_include=["create_agent"], must_not_include=["useAgent"],
          gold_docs=["lg/persistence"]),                                                              # 文件裡沒有
        q(id="Q06", type="near_miss", must_include=[], gold_docs=[], probe_terms=["Ruby", "Rails"],
          answerable=False),                                                                          # 主題不在文件裡
    )
    text = "\n".join(problems)
    for expected in ["Q01：彙整題至少要 2 份", "Q02：彙整題的答案字串只放項目名稱", "Q03：易混淆題要有 must_not_include",
                     "Q04：「Saver」和答案字串互為子字串", "Q05：另一種寫法「useAgent」不在任何文件裡",
                     "Q06：近似陷阱題的主題「Ruby」要出現在文件裡"]:
        assert expected in text
