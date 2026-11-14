"""解析 claude -p 的 stream-json 輸出（純函式）。"""
from __future__ import annotations

import json

EXPECTED_TOOLS = {"Glob", "Grep", "Read", "StructuredOutput"}


def parse_stream(text: str) -> dict:
    """回傳 {init, result, calls, hook_events}。calls 依呼叫順序排列，每個含 name、input、payload、text、is_error。"""
    init, result, hooks = None, None, 0
    calls: dict[str, dict] = {}
    for line in text.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = ev.get("type")
        if kind == "system":
            sub = ev.get("subtype", "")
            if sub == "init":
                init = ev
            elif "hook" in sub:
                hooks += 1
        elif kind == "assistant":
            for block in ev.get("message", {}).get("content") or []:
                if block.get("type") == "tool_use":
                    calls[block["id"]] = {"name": block["name"], "input": block.get("input") or {},
                                          "payload": None, "text": "", "is_error": False}
        elif kind == "user":
            content = ev.get("message", {}).get("content")
            for block in content if isinstance(content, list) else []:
                if block.get("type") != "tool_result" or block.get("tool_use_id") not in calls:
                    continue
                call = calls[block["tool_use_id"]]
                call["payload"] = ev.get("tool_use_result")
                call["text"] = _text_of(block.get("content"))
                call["is_error"] = bool(block.get("is_error"))
        elif kind == "result":
            result = ev
    return {"init": init, "result": result, "calls": list(calls.values()), "hook_events": hooks}


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def relpath(path: str, roots: list[str]) -> str:
    """把絕對路徑或 ./ 開頭的路徑，轉成相對於組別根目錄的路徑。"""
    p = path.strip()
    for root in roots:
        prefix = root.rstrip("/") + "/"
        if p.startswith(prefix):
            p = p[len(prefix):]
            break
    return p.removeprefix("./")


def touched_files(calls: list[dict], roots: list[str], known: set[str]) -> tuple[list[str], list[str]]:
    """回傳 (Read 過的檔案, 出現在 Grep 內文結果中的檔案)。只算 known 裡的檔案；Glob 與只列檔名的結果不算。"""
    read: list[str] = []
    grep: list[str] = []
    for call in calls:
        if call["is_error"]:
            continue
        if call["name"] == "Read":
            p = relpath(str(call["input"].get("file_path", "")), roots)
            if p in known and p not in read:
                read.append(p)
        elif call["name"] == "Grep" and call["input"].get("output_mode") == "content":
            payload = call["payload"] if isinstance(call["payload"], dict) else {}
            text = payload.get("content") or call["text"]
            target = relpath(str(call["input"].get("path", "")), roots)
            if target in known and text.strip():   # 只搜單一檔案時，輸出可能不帶檔名
                hits = [target]
            else:
                hits = []
                for line in text.splitlines():
                    rel_line = relpath(line, roots)
                    hits += [p for p in known if rel_line.startswith((p + ":", p + "-"))]
            for p in hits:
                if p not in grep:
                    grep.append(p)
    return read, grep


def isolation_problems(trace: dict, expected: set[str] = EXPECTED_TOOLS) -> list[str]:
    """檢查這次呼叫是否乾淨：只有預期的工具，沒有 MCP、技能、slash commands、hook。"""
    init = trace["init"]
    if not init:
        return ["沒有 init 事件（claude 可能沒有正常啟動）"]
    problems = []
    tools = set(init.get("tools") or [])
    if tools != expected:
        problems.append(f"工具不符：{sorted(tools)}")
    if init.get("mcp_servers"):
        problems.append("載入了 MCP 伺服器")
    if init.get("skills"):
        problems.append("載入了技能")
    if init.get("slash_commands"):
        problems.append("載入了 slash commands")
    if trace["hook_events"]:
        problems.append(f"有 {trace['hook_events']} 個 hook 事件")
    return problems


def summarize(trace: dict, roots: list[str], known: set[str], aux: dict[str, set[str]] | None = None) -> dict:
    """把一次呼叫整理成 results.jsonl 的一列（不含 round、cond 等識別欄位）。

    aux：旗標名稱 → 輔助檔案（不是文件，例如 C 組的 INDEX.md、D 組的 wiki 頁面），碰過任一個就設為 True。
    """
    res = trace["result"] or {}
    init = trace["init"] or {}
    usage = res.get("usage") or {}
    out = res.get("structured_output")
    ok = res.get("subtype") == "success" and not res.get("is_error") and isinstance(out, dict)
    out = out if isinstance(out, dict) else {}
    read, grep = touched_files(trace["calls"], roots, known)
    aux = {"index_used": {"INDEX.md"}, "wiki_used": set()} if aux is None else aux
    flags = {name: any(touched_files(trace["calls"], roots, files)) for name, files in aux.items()}
    return {
        "status": "ok" if ok else "error",
        "error": None if ok else str(res.get("result") or res.get("subtype") or "沒有 result 事件")[:300],
        "answer": str(out.get("answer", "")),
        "sources": [relpath(str(s), roots) for s in out.get("sources") or []],
        "found": bool(out.get("found", False)),
        "files_read": read,
        "files_grep_content": grep,
        **flags,
        "tool_calls": sum(1 for c in trace["calls"] if c["name"] != "StructuredOutput"),
        "turns": res.get("num_turns"),
        "duration_ms": res.get("duration_ms"),
        "cost_usd": res.get("total_cost_usd"),
        "input_tokens": sum(usage.get(k) or 0 for k in
                            ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
        "output_tokens": usage.get("output_tokens"),
        "model_id": init.get("model"),
        "claude_version": init.get("claude_code_version"),
        "hook_events": trace["hook_events"],
    }
