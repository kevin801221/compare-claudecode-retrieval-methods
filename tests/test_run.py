import json

from lab.run import ANSWER_SCHEMA, aux_files, ask_cmd, done_keys


def test_aux_files_lists_wiki_pages(tmp_path):
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "index.md").write_text("x")
    (tmp_path / "wiki" / "concepts" / "hooks.md").write_text("x")
    assert aux_files(tmp_path) == {"index_used": {"INDEX.md"},
                                   "wiki_used": {"wiki/index.md", "wiki/concepts/hooks.md"}}
    assert aux_files(tmp_path / "沒有wiki的組")["wiki_used"] == set()


def test_ask_cmd_has_isolation_flags():
    cmd = ask_cmd("問題", "haiku", "medium")
    assert cmd[:3] == ["claude", "-p", "問題"]
    for flag in ["--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence", "--verbose",
                 "--include-hook-events"]:
        assert flag in cmd
    assert cmd[cmd.index("--setting-sources") + 1] == "project"
    assert cmd[cmd.index("--tools") + 1] == "Read,Grep,Glob"
    assert cmd[cmd.index("--effort") + 1] == "medium"
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == ANSWER_SCHEMA
    closed = ask_cmd("問題", "haiku", "medium", tools="")
    assert closed[closed.index("--tools") + 1] == ""


def test_done_keys_filters_world_model_effort_status():
    base = {"world_id": "w", "model": "haiku", "effort": "medium", "round": 1, "cond": "A-messy"}
    rows = [
        base | {"qid": "Q01", "status": "ok"},
        base | {"qid": "Q02", "status": "error"},
        base | {"qid": "Q03", "status": "ok", "world_id": "old"},
        base | {"qid": "Q04", "status": "ok", "model": "sonnet"},
        base | {"qid": "Q05", "status": "ok", "effort": "low"},
    ]
    assert done_keys(rows, "w", "haiku", "medium") == {(1, "A-messy", "Q01")}
