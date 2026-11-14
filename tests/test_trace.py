import json

from lab.trace import isolation_problems, parse_stream, summarize, touched_files

ROOT = "/Users/Shared/retrieval-lab-stage/B-organized"
KNOWN = {"docs/產品/XR-7-規格書.md", "docs/人資/出差補助辦法-2025.md", "docs/會議紀錄/週會-0301.md"}


def ev(**kw) -> str:
    return json.dumps(kw, ensure_ascii=False)


def tool_use(i, name, inp):
    return ev(type="assistant", message={"content": [{"type": "tool_use", "id": i, "name": name, "input": inp}]})


def tool_result(i, payload, text="", is_error=False):
    return ev(type="user", tool_use_result=payload,
              message={"content": [{"type": "tool_result", "tool_use_id": i, "content": text, "is_error": is_error}]})


INIT = ev(type="system", subtype="init", model="claude-haiku-5-5", claude_code_version="2.1.325",
          tools=["Glob", "Grep", "Read", "StructuredOutput"], mcp_servers=[], skills=[], slash_commands=[])

RESULT = ev(type="result", subtype="success", is_error=False, num_turns=6, duration_ms=5290,
            total_cost_usd=0.0017,
            usage={"input_tokens": 10, "cache_creation_input_tokens": 100,
                   "cache_read_input_tokens": 1000, "output_tokens": 50},
            structured_output={"answer": "4200 mAh", "found": True,
                               "sources": [f"{ROOT}/docs/產品/XR-7-規格書.md"]})

STREAM = "\n".join([
    INIT,
    tool_use("t1", "Glob", {"pattern": "docs/**/*.md"}),
    tool_result("t1", {"filenames": sorted(KNOWN)}),
    tool_use("t2", "Grep", {"pattern": "4200", "output_mode": "content"}),
    tool_result("t2", {"mode": "content", "content": "docs/產品/XR-7-規格書.md:2:電池容量 4200 mAh。", "filenames": []}),
    tool_use("t3", "Grep", {"pattern": "補助", "output_mode": "files_with_matches"}),
    tool_result("t3", {"mode": "files_with_matches", "filenames": ["docs/人資/出差補助辦法-2025.md"]}),
    tool_use("t4", "Read", {"file_path": f"{ROOT}/docs/會議紀錄/週會-0301.md"}),
    tool_result("t4", {"type": "text", "file": {"filePath": f"{ROOT}/docs/會議紀錄/週會-0301.md"}}),
    tool_use("t5", "Read", {"file_path": "docs/不存在.md"}),
    tool_result("t5", None, "File does not exist.", is_error=True),
    tool_use("t6", "StructuredOutput", {"answer": "4200 mAh"}),
    tool_result("t6", "Structured output provided successfully"),
    "這一行不是 JSON",
    RESULT,
])


def test_parse_stream_collects_calls_in_order():
    trace = parse_stream(STREAM)
    assert [c["name"] for c in trace["calls"]] == ["Glob", "Grep", "Grep", "Read", "Read", "StructuredOutput"]
    assert trace["calls"][4]["is_error"] is True
    assert trace["init"]["model"] == "claude-haiku-5-5"
    assert trace["result"]["num_turns"] == 6


def test_touched_files_counts_read_and_grep_content_only():
    read, grep = touched_files(parse_stream(STREAM)["calls"], [ROOT], KNOWN)
    assert read == ["docs/會議紀錄/週會-0301.md"]   # 失敗的 Read 不算
    assert grep == ["docs/產品/XR-7-規格書.md"]      # Glob 與只列檔名的 Grep 不算


def test_grep_content_with_absolute_paths_and_context_lines():
    calls = parse_stream("\n".join([
        tool_use("g", "Grep", {"pattern": "x", "output_mode": "content", "path": ROOT}),
        tool_result("g", {"mode": "content", "content":
                          f"{ROOT}/docs/人資/出差補助辦法-2025.md-3-前後文\n{ROOT}/docs/人資/出差補助辦法-2025.md:4:命中"}),
    ]))["calls"]
    assert touched_files(calls, [ROOT], KNOWN)[1] == ["docs/人資/出差補助辦法-2025.md"]


def test_grep_on_single_file_counts_that_file():
    calls = parse_stream("\n".join([
        tool_use("g", "Grep", {"pattern": "4200", "output_mode": "content", "path": "docs/產品/XR-7-規格書.md"}),
        tool_result("g", {"mode": "content", "content": "2:電池容量 4200 mAh。"}),
    ]))["calls"]
    assert touched_files(calls, [ROOT], KNOWN)[1] == ["docs/產品/XR-7-規格書.md"]


def test_summarize_ok_row():
    row = summarize(parse_stream(STREAM), [ROOT], KNOWN)
    assert row["status"] == "ok"
    assert row["answer"] == "4200 mAh" and row["found"] is True
    assert row["sources"] == ["docs/產品/XR-7-規格書.md"]   # 絕對路徑轉成相對路徑
    assert row["tool_calls"] == 5                             # StructuredOutput 不算
    assert row["input_tokens"] == 1110 and row["output_tokens"] == 50
    assert row["claude_version"] == "2.1.325"
    assert row["index_used"] is False and row["wiki_used"] is False


def test_wiki_used_flag():
    stream = "\n".join([INIT, tool_use("w", "Read", {"file_path": f"{ROOT}/wiki/index.md"}),
                        tool_result("w", {"type": "text"}), RESULT])
    aux = {"index_used": {"INDEX.md"}, "wiki_used": {"wiki/index.md", "wiki/concepts/hooks.md"}}
    row = summarize(parse_stream(stream), [ROOT], KNOWN, aux)
    assert row["wiki_used"] is True and row["index_used"] is False and row["files_read"] == []


def test_summarize_without_result_is_error():
    row = summarize(parse_stream(INIT), [ROOT], KNOWN)
    assert row["status"] == "error" and row["answer"] == ""


def test_index_used_when_index_read():
    stream = "\n".join([INIT, tool_use("i", "Read", {"file_path": f"{ROOT}/INDEX.md"}),
                        tool_result("i", {"type": "text"}), RESULT])
    row = summarize(parse_stream(stream), [ROOT], KNOWN)
    assert row["index_used"] is True and row["files_read"] == []   # INDEX.md 不算文件


def test_isolation_problems():
    assert isolation_problems(parse_stream(INIT)) == []
    leaky = ev(type="system", subtype="init", tools=["Bash", "Read"], mcp_servers=[{"name": "x"}],
               skills=["s"], slash_commands=[])
    hook = ev(type="system", subtype="hook_response")
    assert len(isolation_problems(parse_stream(leaky + "\n" + hook))) == 4
    assert isolation_problems(parse_stream("")) == ["沒有 init 事件（claude 可能沒有正常啟動）"]


def test_isolation_expected_tools_for_closed_book():
    closed_init = ev(type="system", subtype="init", tools=["StructuredOutput"], mcp_servers=[], skills=[],
                     slash_commands=[])
    assert isolation_problems(parse_stream(closed_init), {"StructuredOutput"}) == []
    assert isolation_problems(parse_stream(closed_init)) != []   # 預設期待的是三個檢索工具
