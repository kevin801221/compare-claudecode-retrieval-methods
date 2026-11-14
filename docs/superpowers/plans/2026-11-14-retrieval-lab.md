# Retrieval Lab 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目標：** 做出一套可以重複執行的評測工具。用同一批虛構文件、同一套題目，比較 A 雜亂／B 整理／C 索引三種資料整理方式，對 Claude Code 檢索與回答準確度的影響，並產生統計表。

**架構：** 整條流程是 `generate → build → run → report`，每一步都是一個 `uv run lab <子指令>`。
- 文件和題目先由 `claude -p`（Sonnet）依「事實表」生成。
- 三組實驗資料夾建在家目錄外的 stage 資料夾。
- 評測時，每一題在每一組裡各跑一次 `claude -p`（Haiku），只開 Read、Grep、Glob 三個工具。從 stream-json 的工具呼叫紀錄判斷 Claude 實際找到了哪些檔案，再用程式比對答案評分，不用 LLM 評審。

**技術：** Python 3.12 以上（uv 管理）、只用標準函式庫、pytest、Claude Code CLI 2.1.325。

**設計文件：** `docs/superpowers/specs/2026-11-14-retrieval-lab-design.md`（以下簡稱「設計」）。

---

## 已實測確認的事實（寫程式時直接依據這些）

**隔離參數：** `--strict-mcp-config --setting-sources project --disable-slash-commands --no-session-persistence`
- cwd 在家目錄外時，不會載入使用者的 CLAUDE.md、AGENTS.md、hooks、MCP。
- cwd 在家目錄內時，`~/AGENTS.md` 和 `~/.claude/CLAUDE.md` 會被當成上層資料夾的指示載入。

**stream-json（需要搭配 `--verbose`）的事件格式：**

| 事件 | 格式 |
|---|---|
| init | `{"type":"system","subtype":"init","tools":[...],"mcp_servers":[],"skills":[],"slash_commands":[],"model":"claude-haiku-5-5","claude_code_version":"2.1.325",...}` |
| 工具呼叫 | `{"type":"assistant","message":{"content":[{"type":"tool_use","id":...,"name":...,"input":{...}}]}}` |
| 工具結果 | `{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":...,"content":"文字","is_error":...}]},"tool_use_result":<結構化結果>}` |
| 結束 | `{"type":"result","subtype":"success","is_error":false,"num_turns":6,"duration_ms":5290,"total_cost_usd":0.0017,"usage":{"input_tokens":..,"cache_creation_input_tokens":..,"cache_read_input_tokens":..,"output_tokens":..},"structured_output":{...}}` |

**各工具的 `tool_use_result`：**

| 工具 | 結構 |
|---|---|
| Glob | `{"filenames":[...]}` |
| Grep 內文模式（`output_mode: "content"`） | `{"mode":"content","content":"docs/產品/XR-7-規格書.md:2:電池容量 4200 mAh。","filenames":[]}` |
| Grep 檔名模式 | `{"mode":"files_with_matches","filenames":[...]}` |
| Read | `{"type":"text","file":{"filePath":"docs/...","content":"..."}}` |

**其他：**
- `--json-schema` 可以和工具並用。模型會透過 `StructuredOutput` 工具回答，結果放在 result 事件的 `structured_output`。
- `--output-format json --tools ""` 也可以用，輸出是單一的 result 物件。
- Haiku 支援 `--effort`，本計畫固定用 `medium`。
- `/Users/Shared` 可以寫入，它和所有上層資料夾都沒有 CLAUDE.md 或 AGENTS.md。
- init 事件的 `memory_paths` 只列出 auto memory 目錄，**不能**用來確認 CLAUDE.md 有沒有載入。改用行為證據：端到端實測時，C 組的第一個動作就是照 CLAUDE.md 指引去讀 `INDEX.md`。報表會記錄每組「讀了索引」的比例。
- 端到端實測（3 份文件、2 題）時，有些呼叫只看 Grep 內文結果就作答，完全沒有 Read。所以檢索命中必須把 Grep 內文結果算進去。

## 共通規則

- **Commit：** 作者用 repo 已設定好的 `kevin801221 <kevin801221@users.noreply.github.com>`。commit 訊息**不加** Claude 署名（使用者規則），也不 push。
- **指令位置：** 所有指令都在 `~/test-dir-1/retrieval-lab/` 下執行。
- **Python：** 一律用 `uv run ...`，不直接呼叫 `python3`。

## 檔案結構

| 檔案 | 職責 |
|---|---|
| `pyproject.toml` | uv 專案設定；console script `lab` |
| `.gitignore` | 排除 `runs/`、`.venv/` 等 |
| `README.md` | 使用說明 |
| `src/lab/__init__.py` | 套件標記 |
| `src/lab/cli.py` | 子指令分派：generate／build／run／report |
| `src/lab/common.py` | 路徑、常數、正規化、讀寫 JSON、家目錄檢查、生成用的 `claude_json()` |
| `src/lab/trace.py` | 解析 stream-json、找出碰過的檔案、隔離檢查、整理成一列結果（純函式） |
| `src/lab/score.py` | 評分（純函式） |
| `src/lab/generate.py` | 事實表規劃、內文撰寫、驗證與自動修正 |
| `src/lab/build.py` | 三組版面、盲建索引、寫入 stage、stage 檢查 |
| `src/lab/run.py` | 開跑前檢查、逐題呼叫、續跑、寫入 results.jsonl |
| `src/lab/report.py` | 彙整、產生 report.md、results.csv、dashboard.json |
| `tests/test_*.py` | 每個純函式模組各一個測試檔 |

---

### Task 1：專案骨架

**Files:**
- Create: `pyproject.toml`、`.gitignore`、`README.md`、`src/lab/__init__.py`、`src/lab/cli.py`

- [ ] **Step 1：建立 `pyproject.toml`**

```toml
[project]
name = "retrieval-lab"
version = "0.1.0"
description = "比較資料整理方式對 Claude Code 檢索與回答準確度的影響"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
lab = "lab.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/lab"]

[dependency-groups]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2：建立 `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
runs/
```

- [ ] **Step 3：建立 `src/lab/__init__.py`**

```python
"""Retrieval Lab：比較資料整理方式對 Claude Code 檢索準確度的影響。"""
```

- [ ] **Step 4：建立 `src/lab/cli.py`**

各子指令用延遲 import，所以後面的模組還沒寫好時，`--help` 也能正常執行。

```python
"""指令列入口：uv run lab <generate|build|run|report>。"""
from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lab", description="比較資料整理方式對 Claude Code 檢索準確度的影響")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="產生事實表與文件（一次性）")
    g.add_argument("--pilot", action="store_true", help="試跑規模：20 份文件、10 題")
    g.add_argument("--model", default="sonnet")
    g.add_argument("--force", action="store_true", help="覆寫既有的 world/")

    b = sub.add_parser("build", help="建立 A/B/C 三組實驗資料夾")
    b.add_argument("--model", default="sonnet", help="盲建索引用的模型")

    r = sub.add_parser("run", help="跑評測（可續跑）")
    r.add_argument("--rounds", type=int, required=True, help="跑到第幾輪為止；已完成的會跳過")
    r.add_argument("--model", default="haiku")
    r.add_argument("--effort", default="medium")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--timeout", type=int, default=180)

    p = sub.add_parser("report", help="產生統計表與網頁資料")
    p.add_argument("--model", default="haiku")
    p.add_argument("--effort", default="medium")

    args = parser.parse_args(argv)
    if args.cmd == "generate":
        from lab.generate import generate
        generate(pilot=args.pilot, model=args.model, force=args.force)
    elif args.cmd == "build":
        from lab.build import build
        build(model=args.model)
    elif args.cmd == "run":
        from lab.run import run
        run(rounds=args.rounds, model=args.model, effort=args.effort,
            workers=args.workers, timeout=args.timeout)
    elif args.cmd == "report":
        from lab.report import report
        report(model=args.model, effort=args.effort)
```

- [ ] **Step 5：建立 `README.md`**

````markdown
# Retrieval Lab

比較三種資料整理方式（A 雜亂／B 整理／C 索引）對 Claude Code 檢索與回答準確度的影響。
設計見 `docs/superpowers/specs/2026-11-14-retrieval-lab-design.md`。

## 需求

- uv，以及已登入的 Claude Code（`claude` 指令可以用）
- 實驗資料夾預設放在 `/Users/Shared/retrieval-lab-stage`。它必須在家目錄外，可以用環境變數 `LAB_STAGE` 換位置。

## 使用

```bash
uv sync
uv run lab generate --pilot      # 試跑規模：20 份文件、10 題（正式版拿掉 --pilot、加上 --force）
uv run lab build                 # 盲建索引，並建立 A/B/C 三組
uv run lab run --rounds 1        # 跑評測，可以續跑；--rounds 3 會補跑到第 3 輪
uv run lab report                # 產生 results/report.md、results.csv、dashboard.json
uv run pytest                    # 執行測試
```

## 注意

- 每一輪的呼叫次數是「題數 × 3 組」，會消耗額度。
- `runs/` 是原始紀錄，裡面有本機路徑，所以不進 git。
````

- [ ] **Step 6：安裝並確認指令可以執行**

Run: `uv sync && uv run lab --help`
Expected：最後幾行包含 `usage: lab [-h] {generate,build,run,report} ...`

- [ ] **Step 7：Commit**

```bash
git add pyproject.toml uv.lock .gitignore README.md src/lab/__init__.py src/lab/cli.py
git commit -m "chore: 建立 retrieval-lab 專案骨架"
```

---

### Task 2：共用模組 `common.py`

**Files:**
- Create: `src/lab/common.py`
- Test: `tests/test_common.py`

- [ ] **Step 1：寫測試**

```python
from lab.common import is_under_home, leaking_ancestors, norm


def test_norm_fullwidth_spaces_commas():
    assert norm("４，２００ mAh") == "4200mah"
    assert norm("NT$ 1,200 元") == "nt$1200元"


def test_is_under_home(tmp_path):
    home = tmp_path / "home"
    (home / "proj").mkdir(parents=True)
    assert is_under_home(home / "proj", home)
    assert is_under_home(home, home)
    assert not is_under_home(tmp_path / "elsewhere", home)


def test_leaking_ancestors(tmp_path):
    (tmp_path / "a" / "b" / ".claude").mkdir(parents=True)
    (tmp_path / "a" / "AGENTS.md").write_text("x")
    (tmp_path / "a" / "b" / ".claude" / "CLAUDE.md").write_text("x")
    found = leaking_ancestors(tmp_path / "a" / "b")
    assert tmp_path.resolve() / "a" / "AGENTS.md" in found
    assert tmp_path.resolve() / "a" / "b" / ".claude" / "CLAUDE.md" in found
```

- [ ] **Step 2：確認測試失敗**

Run: `uv run pytest tests/test_common.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.common'`

- [ ] **Step 3：實作 `src/lab/common.py`**

```python
"""共用設定與小工具。"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "world"
FACTS = WORLD / "facts.json"
CORPUS = WORLD / "corpus"
INDEX_CACHE = WORLD / "index_rows.json"
MAPPING = ROOT / "build" / "mapping.json"
RESULTS = ROOT / "results"
RESULTS_JSONL = RESULTS / "results.jsonl"
RUNS = ROOT / "runs"

CONDS = ["A-messy", "B-organized", "C-indexed"]
COND_LABELS = {"A-messy": "A 雜亂", "B-organized": "B 整理", "C-indexed": "C 索引"}
CATEGORIES = ["產品", "人資", "客服", "工程", "會議紀錄"]
QTYPES = ["lookup", "paraphrase", "version", "multi_doc", "unanswerable"]
QTYPE_LABELS = {"lookup": "直接查找", "paraphrase": "換句話說", "version": "新舊版本",
                "multi_doc": "跨文件", "unanswerable": "題庫裡沒有"}

# 不載入使用者設定、MCP、技能，也不留對話紀錄（設計第 3 節）
ISOLATION = ["--strict-mcp-config", "--setting-sources", "project",
             "--disable-slash-commands", "--no-session-persistence"]
# Claude Code 會從工作目錄往上層找、並當成指示載入的檔案
INSTRUCTION_FILES = ["CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", ".claude/CLAUDE.md"]


def stage_root() -> Path:
    return Path(os.environ.get("LAB_STAGE", "/Users/Shared/retrieval-lab-stage"))


def norm(s: str) -> str:
    """全形轉半形、轉小寫、去掉空白與逗號，用於答案比對。"""
    s = unicodedata.normalize("NFKC", s).lower()
    return "".join(ch for ch in s if not ch.isspace() and ch != ",")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def world_id() -> str:
    """事實表內容的指紋：換一套題目就換一個 id，舊結果自動不納入統計。"""
    return sha256(FACTS.read_text(encoding="utf-8"))[:12]


def read_rows() -> list[dict]:
    """讀取 results/results.jsonl 的所有列。"""
    if not RESULTS_JSONL.exists():
        return []
    lines = RESULTS_JSONL.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def is_under_home(path: Path, home: Path | None = None) -> bool:
    home = (home or Path.home()).resolve()
    p = path.resolve()
    return p == home or home in p.parents


def leaking_ancestors(path: Path) -> list[Path]:
    """path 本身與所有上層資料夾裡，會被 Claude Code 當成指示載入的檔案。"""
    p = path.resolve()
    return [d / name for d in (p, *p.parents) for name in INSTRUCTION_FILES if (d / name).exists()]


def claude_json(prompt: str, schema: dict, model: str, timeout: int = 900) -> dict:
    """生成用的結構化呼叫：不開任何工具，在家目錄外的暫存資料夾執行。"""
    with tempfile.TemporaryDirectory() as tmp:
        if is_under_home(Path(tmp)):
            raise RuntimeError(f"暫存資料夾在家目錄底下（{tmp}），請把 TMPDIR 設到家目錄外")
        proc = subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--output-format", "json", "--tools", "",
             "--json-schema", json.dumps(schema, ensure_ascii=False), *ISOLATION],
            cwd=tmp, capture_output=True, text=True, timeout=timeout,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p 失敗（exit {proc.returncode}）：{proc.stderr[-500:]}")
    out = json.loads(proc.stdout)
    if out.get("is_error") or not isinstance(out.get("structured_output"), dict):
        raise RuntimeError(f"claude -p 沒有回傳結構化結果：{str(out.get('result'))[:500]}")
    return out["structured_output"]
```

- [ ] **Step 4：確認測試通過**

Run: `uv run pytest tests/test_common.py -v`
Expected：3 passed

- [ ] **Step 5：Commit**

```bash
git add src/lab/common.py tests/test_common.py
git commit -m "feat: 共用設定、正規化與家目錄檢查"
```

---

### Task 3：解析 stream-json（`trace.py`）

**Files:**
- Create: `src/lab/trace.py`
- Test: `tests/test_trace.py`

- [ ] **Step 1：寫測試**

假資料的格式照「已實測確認的事實」一節。

```python
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
    assert grep == ["docs/產品/XR-7-規格書.md"]      # Glob 與檔名模式不算


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
    assert row["index_used"] is False


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
```

- [ ] **Step 2：確認測試失敗**

Run: `uv run pytest tests/test_trace.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.trace'`

- [ ] **Step 3：實作 `src/lab/trace.py`**

```python
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
    """回傳 (Read 過的檔案, 出現在 Grep 內文結果中的檔案)。只算 known 裡的文件；Glob 與檔名清單不算。"""
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


def isolation_problems(trace: dict) -> list[str]:
    """檢查這次呼叫是否乾淨：只有預期的工具，沒有 MCP、技能、slash commands、hook。"""
    init = trace["init"]
    if not init:
        return ["沒有 init 事件（claude 可能沒有正常啟動）"]
    problems = []
    tools = set(init.get("tools") or [])
    if tools != EXPECTED_TOOLS:
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


def summarize(trace: dict, roots: list[str], known: set[str]) -> dict:
    """把一次呼叫整理成 results.jsonl 的一列（不含 round、cond 等識別欄位）。"""
    res = trace["result"] or {}
    init = trace["init"] or {}
    usage = res.get("usage") or {}
    out = res.get("structured_output")
    ok = res.get("subtype") == "success" and not res.get("is_error") and isinstance(out, dict)
    out = out if isinstance(out, dict) else {}
    read, grep = touched_files(trace["calls"], roots, known)
    idx_read, idx_grep = touched_files(trace["calls"], roots, {"INDEX.md"})
    return {
        "status": "ok" if ok else "error",
        "error": None if ok else str(res.get("result") or res.get("subtype") or "沒有 result 事件")[:300],
        "answer": str(out.get("answer", "")),
        "sources": [relpath(str(s), roots) for s in out.get("sources") or []],
        "found": bool(out.get("found", False)),
        "files_read": read,
        "files_grep_content": grep,
        "index_used": bool(idx_read or idx_grep),
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
```

- [ ] **Step 4：確認測試通過**

Run: `uv run pytest tests/test_trace.py -v`
Expected：8 passed

- [ ] **Step 5：Commit**

```bash
git add src/lab/trace.py tests/test_trace.py
git commit -m "feat: 解析 stream-json，從工具紀錄判斷碰過哪些檔案"
```

---

### Task 4：評分（`score.py`）

**Files:**
- Create: `src/lab/score.py`
- Test: `tests/test_score.py`

- [ ] **Step 1：寫測試**

```python
from lab.score import score

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


def test_version_new_value_with_old_mentioned_is_correct():
    s = score(row("2025 版 1200 元，2024 版是 1000 元"), q("version", ["1200"], ["1000"]), PATHS)
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
```

- [ ] **Step 2：確認測試失敗**

Run: `uv run pytest tests/test_score.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.score'`

- [ ] **Step 3：實作 `src/lab/score.py`**

```python
"""評分（純函式）：程式比對，不用 LLM 評審。定義見設計第 7 節。"""
from __future__ import annotations

from lab.common import norm

NON_DOCS = {"INDEX.md", "CLAUDE.md"}   # 索引和指引不是文件，不計入引用比率


def score(row: dict, q: dict, paths: dict[str, str]) -> dict:
    """row：results.jsonl 的一列；q：題目；paths：該組的 doc_id → 相對路徑。不適用的指標回傳 None。"""
    if not q["answerable"]:
        return {"correct": not row["found"], "hallucinated": row["found"], "stale": None,
                "retrieved": None, "read_gold": None, "citation_hit": None, "citation_precision": None}
    answer = norm(row["answer"])
    gold = {paths[d] for d in q["gold_docs"]}
    read = set(row["files_read"])
    sources = set(row["sources"]) - NON_DOCS
    has_new = all(norm(t) in answer for t in q["must_include"])
    stale = None
    if q["type"] == "version":
        stale = (not has_new) and any(norm(t) in answer for t in q["must_not_include"])
    return {
        "correct": row["found"] and has_new,
        "hallucinated": bool(stale),
        "stale": stale,
        "retrieved": gold <= read | set(row["files_grep_content"]),
        "read_gold": gold <= read,
        "citation_hit": gold <= sources,
        "citation_precision": len(sources & gold) / len(sources) if sources else 0.0,
    }
```

- [ ] **Step 4：確認測試通過**

Run: `uv run pytest tests/test_score.py -v`
Expected：9 passed

- [ ] **Step 5：Commit**

```bash
git add src/lab/score.py tests/test_score.py
git commit -m "feat: 以程式比對評分（答對、幻覺、檢索命中、引用）"
```

---

### Task 5：事實表的組裝與驗證（`generate.py` 的純函式部分）

**Files:**
- Create: `src/lab/generate.py`
- Test: `tests/test_generate.py`

- [ ] **Step 1：寫測試**

```python
from lab.generate import PATH_TRACE, answer_leaks, assemble, check_item, fix_slugs, validate


def spec(title, category="產品", slug="s", facts=("事實",)):
    return {"title": title, "category": category, "slug": slug, "date": "2025-01-01",
            "facts": list(facts), "brief": "b"}


def item(gold=(), extra=(), must=(), must_not=(), probe=()):
    return {"question": "問？", "gold": list(gold), "extra": list(extra), "must_include": list(must),
            "must_not_include": list(must_not), "probe_terms": list(probe)}


def test_check_item_rules():
    assert check_item("lookup", item(gold=[spec("a")], must=["1"])) is None
    assert check_item("lookup", item(gold=[], must=["1"])) is not None
    assert check_item("version", item(gold=[spec("新")], extra=[spec("舊")], must=["2"], must_not=["1"])) is None
    assert check_item("version", item(gold=[spec("新")], must=["2"], must_not=["1"])) is not None
    assert check_item("multi_doc", item(gold=[spec("a"), spec("b")], must=["1", "2"])) is None
    assert check_item("unanswerable", item(extra=[spec("a")], probe=["LK-9", "重量"])) is None
    assert check_item("unanswerable", item(probe=["LK-9"])) is not None


def test_fix_slugs_sanitizes_and_dedupes():
    docs = [{"id": "D001", "category": "人資", "slug": "出差 補助/辦法（2025）"},
            {"id": "D002", "category": "人資", "slug": "出差 補助/辦法（2025）"},
            {"id": "D003", "category": "客服", "slug": "出差 補助/辦法（2025）"}]
    fix_slugs(docs)
    assert [d["slug"] for d in docs] == ["出差-補助-辦法-2025", "出差-補助-辦法-2025-2", "出差-補助-辦法-2025"]


def make_facts():
    planned = {
        "lookup": [item(gold=[spec("XR-7 規格書", slug="XR-7-規格書", facts=["電池容量 4200 mAh"])], must=["4200"])],
        "version": [item(gold=[spec("補助 2025", category="人資", slug="補助-2025", facts=["每日 1200 元"])],
                         extra=[spec("補助 2024", category="人資", slug="補助-2024", facts=["每日 1000 元"])],
                         must=["1200"], must_not=["1000"])],
        "unanswerable": [item(extra=[spec("LK-9 介紹", slug="LK-9-介紹", facts=["LK-9 支援指紋"])],
                              probe=["LK-9", "重量"])],
    }
    return assemble(planned, [spec("週會", category="會議紀錄", slug="週會") | {"role": "filler"}], pilot=True)


def test_assemble_ids_and_fields():
    facts = make_facts()
    assert [d["id"] for d in facts["docs"]] == ["D001", "D002", "D003", "D004", "D005"]
    q1, q2, q3 = facts["questions"]
    assert (q1["id"], q1["gold_docs"], q1["answerable"]) == ("Q01", ["D001"], True)
    assert (q2["type"], q2["gold_docs"], q2["extra_docs"]) == ("version", ["D002"], ["D003"])
    assert (q3["answerable"], q3["gold_docs"], q3["extra_docs"], q3["probe_terms"]) == (False, [], ["D004"], ["LK-9", "重量"])
    assert facts["docs"][4]["role"] == "filler"


GOOD = {"D001": "# XR-7 規格書\n電池容量 4,200 mAh。", "D002": "# 補助 2025\n每日 1200 元。",
        "D003": "# 補助 2024\n每日 1000 元。", "D004": "# LK-9 介紹\nLK-9 支援指紋。", "D005": "# 週會\n討論事項。"}


def test_validate_passes_on_good_bodies():
    assert validate(make_facts(), GOOD) == []


def test_validate_flags_each_problem():
    facts = make_facts()
    bad = GOOD | {"D001": "# XR-7\n容量未定。",
                  "D002": "# 補助 2025\n由 1000 元調高為 1200 元。",
                  "D005": "# 週會\nLK-9 重量 3 公斤，見 docs/x.md"}
    problems = validate(facts, bad)
    kinds = {(p["doc"], p["kind"]) for p in problems}
    assert ("D001", "missing_answer") in kinds
    assert ("D002", "old_value_in_new") in kinds
    assert ("D005", "path_trace") in kinds
    assert ("D005", "unanswerable_leak") in kinds
    assert {p["doc"]: p["avoid"] for p in problems if p["avoid"]} == {"D002": "1000", "D005": "重量"}


def test_answer_leaks_lists_non_gold_docs_with_answer():
    facts = make_facts()
    assert answer_leaks(facts, GOOD) == []
    assert answer_leaks(facts, GOOD | {"D005": "# 週會\nXR-7 電池 4200 mAh。"}) == [("Q01", "4200", "D005")]


def test_path_trace_pattern():
    assert PATH_TRACE.search("請見 doc_012")
    assert PATH_TRACE.search("README.md")
    assert not PATH_TRACE.search("一般內容 2025")
```

- [ ] **Step 2：確認測試失敗**

Run: `uv run pytest tests/test_generate.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.generate'`

- [ ] **Step 3：實作 `src/lab/generate.py`（純函式部分）**

```python
"""事實表 → 文件。先規劃題目與文件規格，再分批寫內文，最後用程式驗證答案確實寫在文件裡。"""
from __future__ import annotations

import re

from lab.common import QTYPES, norm

WORLD_BRIEF = """虛構公司「雲杉科技」（Yunshan Tech）：台灣的智慧家電公司，2019 年成立，總部在新竹。
產品線：空氣清淨機 XR 系列（XR-3、XR-5、XR-7）、掃地機器人 RB 系列（RB-10、RB-20）、
除濕機 DH 系列（DH-12、DH-16）、智慧插座 SP-1、智慧門鎖 LK-9，以及手機 App「雲杉家」。
部門：產品部、人資部、客服部、工程部、業務部。"""

PATH_TRACE = re.compile(r"\.md\b|docs/|doc_\d+", re.IGNORECASE)


def check_item(qtype: str, item: dict) -> str | None:
    """檢查規劃出來的一題是否符合題型結構；不符合時回傳原因。"""
    n_gold, n_extra = len(item["gold"]), len(item["extra"])
    if qtype in ("lookup", "paraphrase") and (n_gold != 1 or not item["must_include"]):
        return "需要 1 份 gold 和至少 1 個答案字串"
    if qtype == "version" and (n_gold != 1 or n_extra < 1 or not item["must_include"]
                               or not item["must_not_include"]):
        return "需要新版 gold、舊版 extra，以及新舊數值"
    if qtype == "multi_doc" and (n_gold != 2 or len(item["must_include"]) < 2):
        return "需要 2 份 gold 和至少 2 個答案字串"
    if qtype == "unanswerable" and (n_gold != 0 or len(item["probe_terms"]) != 2):
        return "gold 要留空，probe_terms 要剛好 2 個"
    return None


def fix_slugs(docs: list[dict]) -> None:
    """把 slug 改成安全的檔名，並確保同一個類別內不重複。"""
    seen: set[tuple[str, str]] = set()
    for d in docs:
        base = re.sub(r"[^\w\-]+", "-", d["slug"]).strip("-")[:60] or d["id"]
        slug, n = base, 2
        while (d["category"], slug) in seen:
            slug, n = f"{base}-{n}", n + 1
        seen.add((d["category"], slug))
        d["slug"] = slug


def assemble(planned: dict[str, list[dict]], fillers: list[dict], pilot: bool) -> dict:
    """把規劃結果組成 facts.json，配發 D001、Q01 這類 id。"""
    docs: list[dict] = []
    questions: list[dict] = []

    def add(spec: dict, role: str) -> str:
        doc_id = f"D{len(docs) + 1:03d}"
        docs.append({"id": doc_id, "title": spec["title"].strip(), "category": spec["category"],
                     "slug": spec["slug"], "date": spec["date"], "role": role,
                     "facts": spec["facts"], "brief": spec["brief"], "avoid": []})
        return doc_id

    for qtype in QTYPES:
        for item in planned.get(qtype, []):
            answerable = qtype != "unanswerable"
            gold = [add(s, "gold" if answerable else "distractor") for s in item["gold"]]
            extra = [add(s, "distractor") for s in item["extra"]]
            questions.append({
                "id": f"Q{len(questions) + 1:02d}",
                "type": qtype,
                "question": item["question"].strip(),
                "must_include": item["must_include"] if answerable else [],
                "must_not_include": item["must_not_include"] if qtype == "version" else [],
                "gold_docs": gold if answerable else [],
                "extra_docs": extra,
                "probe_terms": item["probe_terms"] if qtype == "unanswerable" else [],
                "answerable": answerable,
            })
    for spec in fillers:
        add(spec, spec.get("role", "filler"))
    fix_slugs(docs)
    return {"version": 1, "pilot": pilot, "world": WORLD_BRIEF, "docs": docs, "questions": questions}


def _owner(q: dict, token: str, docs: dict[str, dict]) -> str:
    """答案字串應該寫在哪一份 gold 文件：依 facts 判斷，找不到就用第一份。"""
    for doc_id in q["gold_docs"]:
        if norm(token) in norm(" ".join(docs[doc_id]["facts"])):
            return doc_id
    return q["gold_docs"][0]


def validate(facts: dict, bodies: dict[str, str]) -> list[dict]:
    """回傳問題清單。每個問題含 doc（該重寫哪份文件；None 表示無法自動修）、kind、detail、avoid（重寫時要避開的字）。"""
    docs = {d["id"]: d for d in facts["docs"]}
    normed = {doc_id: norm(bodies.get(doc_id, "")) for doc_id in docs}
    problems: list[dict] = []

    def add(doc: str | None, kind: str, detail: str, avoid: str | None = None) -> None:
        problems.append({"doc": doc, "kind": kind, "detail": detail, "avoid": avoid})

    for doc_id in docs:
        body = bodies.get(doc_id, "")
        if not body.strip():
            add(doc_id, "missing_body", "沒有內文")
        elif m := PATH_TRACE.search(body):
            add(doc_id, "path_trace", f"出現路徑痕跡「{m.group(0)}」")
    for q in facts["questions"]:
        for token in q["must_include"]:
            owner = _owner(q, token, docs)
            if norm(token) not in normed[owner]:
                add(owner, "missing_answer", f"{q['id']} 缺少答案「{token}」")
        if q["type"] == "multi_doc":
            for doc_id in q["gold_docs"]:
                if not any(norm(t) in normed[doc_id] for t in q["must_include"]):
                    add(doc_id, "multi_doc_unused", f"{q['id']} 這份文件沒有任何答案字串")
        if q["type"] == "version":
            new, old = q["gold_docs"][0], q["extra_docs"][0]
            for token in q["must_not_include"]:
                if norm(token) in normed[new]:
                    add(new, "old_value_in_new", f"{q['id']} 新版出現舊值「{token}」", avoid=token)
                if norm(token) not in normed[old]:
                    add(old, "old_value_missing", f"{q['id']} 舊版缺少舊值「{token}」")
        if q["type"] == "unanswerable":
            entity, attr = q["probe_terms"]
            if not any(norm(entity) in b for b in normed.values()):
                add(q["extra_docs"][0] if q["extra_docs"] else None, "entity_absent",
                    f"{q['id']} 沒有任何文件提到「{entity}」")
            for doc_id, b in normed.items():
                if norm(entity) in b and norm(attr) in b:
                    add(doc_id, "unanswerable_leak", f"{q['id']} 文件同時提到「{entity}」和「{attr}」", avoid=attr)
    return problems


def answer_leaks(facts: dict, bodies: dict[str, str]) -> list[tuple[str, str, str]]:
    """審題用：列出「不是 gold、卻也含有答案字串」的文件，格式為 (qid, 答案字串, doc_id)。"""
    leaks = []
    for q in facts["questions"]:
        for token in q["must_include"]:
            for doc_id, body in bodies.items():
                if doc_id not in q["gold_docs"] and norm(token) in norm(body):
                    leaks.append((q["id"], token, doc_id))
    return leaks
```

- [ ] **Step 4：確認測試通過**

Run: `uv run pytest tests/test_generate.py -v`
Expected：7 passed

- [ ] **Step 5：Commit**

```bash
git add src/lab/generate.py tests/test_generate.py
git commit -m "feat: 事實表組裝與驗證"
```

---

### Task 6：呼叫 Claude 生成（`generate.py` 的生成部分）

**Files:**
- Modify: `src/lab/generate.py`（換掉 import 區塊，並在檔案最後加上程式）

- [ ] **Step 1：把 `src/lab/generate.py` 開頭的 import 區塊換成以下內容**

```python
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from lab.common import CATEGORIES, CORPUS, FACTS, QTYPES, claude_json, norm, save_json
```

- [ ] **Step 2：在 `src/lab/generate.py` 最後加上以下程式**

```python
SIZES = {True: {"docs": 20, "per_type": 2}, False: {"docs": 200, "per_type": 8}}

DOC_SPEC = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "category": {"type": "string", "enum": CATEGORIES},
        "slug": {"type": "string"},
        "date": {"type": "string"},
        "facts": {"type": "array", "items": {"type": "string"}},
        "brief": {"type": "string"},
    },
    "required": ["title", "category", "slug", "date", "facts", "brief"],
}

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "must_include": {"type": "array", "items": {"type": "string"}},
            "must_not_include": {"type": "array", "items": {"type": "string"}},
            "probe_terms": {"type": "array", "items": {"type": "string"}},
            "gold": {"type": "array", "items": DOC_SPEC},
            "extra": {"type": "array", "items": DOC_SPEC},
        },
        "required": ["question", "must_include", "must_not_include", "probe_terms", "gold", "extra"],
    }}},
    "required": ["items"],
}

FILLER_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {**DOC_SPEC["properties"], "role": {"type": "string", "enum": ["distractor", "filler"]}},
        "required": [*DOC_SPEC["required"], "role"],
    }}},
    "required": ["items"],
}

BODY_SCHEMA = {
    "type": "object",
    "properties": {"docs": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "body": {"type": "string"}},
        "required": ["id", "body"],
    }}},
    "required": ["docs"],
}

COMMON_RULES = f"""規則：
- 全部使用繁體中文，可以夾雜少量英文術語。
- 答案字串（must_include、must_not_include）要簡短明確，而且盡量在整個題庫中獨一無二：型號、3 位數以上的數字、日期或人名，例如「4200」「NT$1680」「RB-20」「2025-03-01」「林怡君」。避免只有 1–2 位數的純數字。
- 答案字串不要帶單位或多餘的文字（寫「4200」，不要寫「4200 mAh」）。
- 每個答案字串都要逐字出現在對應文件的 facts 裡。
- category 只能是：{"、".join(CATEGORIES)}。
- slug 只能用中文、英文、數字和連字號，可以帶年份，例如「XR-7-規格書」「出差補助辦法-2025」。
- date 格式為 YYYY-MM-DD，介於 2023-01-01 和 2025-12-31 之間。
- facts 寫成完整句子；brief 用一句話說明文件類型與寫作重點。"""

TYPE_RULES = {
    "lookup": "直接查找題：題目用詞與文件一致。gold 放 1 份文件；must_include 放 1–2 個答案字串；"
              "must_not_include、probe_terms、extra 留空。",
    "paraphrase": "換句話說題：題目刻意不用文件裡的關鍵詞，改用同義詞、口語說法或另一種語言"
                  "（例如文件寫「退貨」，題目問「退費」；文件寫「SLA」，題目寫「服務等級協議」）。"
                  "在 brief 寫明文件必須使用的原始用詞。gold 放 1 份文件；must_include 放 1–2 個答案字串；"
                  "must_not_include、probe_terms、extra 留空。",
    "version": "新舊版本題：同一主題有新舊兩版文件（例如 2024 版與 2025 版），關鍵數值不同。"
               "gold 放新版文件；extra 放舊版文件；兩份的 date 不同，新版較晚。"
               "must_include 放新版數值；must_not_include 放舊版數值。題目不要提到年份或版本。probe_terms 留空。",
    "multi_doc": "跨文件題：題目同時問兩件事，這兩件事分別只寫在兩份不同的文件裡"
                 "（例如 XR-7 的電池容量寫在規格書，保固月數寫在保固政策）。"
                 "gold 放這 2 份文件；must_include 放 2 個答案字串，兩份文件各提供 1 個。"
                 "must_not_include、probe_terms、extra 留空。",
    "unanswerable": "題庫裡沒有的題：問一個確實存在的實體（產品、制度、部門），從來沒有被任何文件記載的屬性"
                    "（例如某產品的重量）。gold 留空；extra 放 1 份與該實體相關、但完全不提該屬性的文件；"
                    "must_include、must_not_include 留空；probe_terms 放 2 個字串：[實體名稱, 屬性關鍵詞]，"
                    "例如 [\"LK-9\", \"重量\"]。",
}


def _ask_questions(qtype: str, n: int, used: list[str], model: str) -> list[dict]:
    prompt = (f"{WORLD_BRIEF}\n\n請為檢索測驗設計 {n} 道題目，以及回答所需的文件規格。\n"
              f"{TYPE_RULES[qtype]}\n{COMMON_RULES}\n"
              f"- 不要重複以下已經用過的標題或答案：{'；'.join(used) or '（無）'}")
    return claude_json(prompt, QUESTION_SCHEMA, model)["items"]


def plan_questions(qtype: str, n: int, used: list[str], model: str) -> list[dict]:
    """規劃 n 題；結構不符的題目丟掉重問，最多 3 次。會把用過的標題與答案加進 used。"""
    items: list[dict] = []
    for _ in range(3):
        for item in _ask_questions(qtype, n - len(items), used, model):
            if len(items) < n and check_item(qtype, item) is None:
                items.append(item)
                used += [s["title"] for s in item["gold"] + item["extra"]] + item["must_include"]
        if len(items) == n:
            return items
    raise RuntimeError(f"{qtype} 題型規劃失敗：只拿到 {len(items)}/{n} 題")


def plan_fillers(n: int, draft: dict, model: str, batch: int = 24) -> list[dict]:
    """規劃 n 份背景文件（干擾文件與一般文件），不能包含能回答任何題目的資訊。"""
    titles = [d["title"] for d in draft["docs"]]
    guarded = "；".join(q["question"] for q in draft["questions"])
    probes = "；".join("＋".join(q["probe_terms"]) for q in draft["questions"] if q["probe_terms"]) or "（無）"
    items: list[dict] = []
    for _ in range(n // batch + 5):
        if len(items) >= n:
            break
        k = min(batch, n - len(items))
        prompt = (f"{WORLD_BRIEF}\n\n請產生 {k} 份背景文件的規格（不用寫內文）。\n"
                  "約一半是干擾文件（role=distractor）：主題跟既有文件相近，例如同系列的其他型號、"
                  "其他年份的類似規章，但數值必須不同。\n"
                  "另一半是一般文件（role=filler）：會議紀錄、公告、作業流程等。\n"
                  f"{COMMON_RULES}\n"
                  f"- 這些文件都不能包含能回答下列問題的資訊：{guarded}\n"
                  f"- 不能同時提到以下實體與屬性的組合：{probes}\n"
                  f"- 不要和既有標題重複：{'；'.join(titles + [i['title'] for i in items])}")
        items += claude_json(prompt, FILLER_SCHEMA, model)["items"][:k]
    if len(items) < n:
        raise RuntimeError(f"背景文件規劃失敗：只拿到 {len(items)}/{n} 份")
    return items


def _write_batch(batch: list[dict], model: str) -> dict[str, str]:
    specs = "\n\n".join(
        f"id：{d['id']}\n標題：{d['title']}\n類別：{d['category']}\n日期：{d['date']}\n"
        f"必須寫入的事實：{'；'.join(d['facts']) or '（無）'}\n寫作重點：{d['brief']}\n"
        f"禁止出現的字詞：{'、'.join(d['avoid']) or '（無）'}"
        for d in batch)
    prompt = (f"{WORLD_BRIEF}\n\n請依照下列規格，替每一份文件寫出完整內文。\n"
              "- 每份 300–700 字，繁體中文 Markdown。第一行是「# 標題」，第二行是「日期：YYYY-MM-DD」。\n"
              "- 「必須寫入的事實」中的數字、型號、日期、人名，都要原樣出現在內文裡。\n"
              "- 可以加入合理的細節，但不能寫出與這些事實矛盾的數值。\n"
              "- 不要提到任何檔名或路徑（例如 .md、docs/）。\n"
              "- 「禁止出現的字詞」一個都不能出現。\n"
              f"- 回傳時 id 照抄。\n\n{specs}")
    out = claude_json(prompt, BODY_SCHEMA, model)
    wanted = {d["id"] for d in batch}
    return {d["id"]: d["body"] for d in out["docs"] if d["id"] in wanted}


def write_bodies(docs: list[dict], model: str, batch: int = 5, workers: int = 4) -> dict[str, str]:
    """分批平行撰寫內文；某一批失敗時不中斷，交給驗證步驟重試。"""
    def safe(part: list[dict]) -> dict[str, str]:
        try:
            return _write_batch(part, model)
        except Exception as e:  # noqa: BLE001
            print(f"  批次失敗（{', '.join(d['id'] for d in part)}）：{e}")
            return {}

    bodies: dict[str, str] = {}
    with ThreadPoolExecutor(workers) as pool:
        for result in pool.map(safe, [docs[i:i + batch] for i in range(0, len(docs), batch)]):
            bodies.update(result)
    return bodies


def _apply_fixes(facts: dict, problems: list[dict]) -> set[str]:
    """把要避開的字記到文件規格上，回傳要重寫的文件 id。"""
    docs = {d["id"]: d for d in facts["docs"]}
    redo: set[str] = set()
    for p in problems:
        if p["doc"] in docs:
            redo.add(p["doc"])
            if p["avoid"] and p["avoid"] not in docs[p["doc"]]["avoid"]:
                docs[p["doc"]]["avoid"].append(p["avoid"])
    return redo


def save_world(facts: dict, bodies: dict[str, str]) -> None:
    save_json(FACTS, facts)
    CORPUS.mkdir(parents=True, exist_ok=True)
    for old in CORPUS.glob("*.md"):
        old.unlink()
    for d in facts["docs"]:
        if d["id"] in bodies:
            (CORPUS / f"{d['id']}.md").write_text(bodies[d["id"]].strip() + "\n", encoding="utf-8")


def generate(pilot: bool, model: str = "sonnet", force: bool = False) -> None:
    if FACTS.exists() and not force:
        raise SystemExit("world/facts.json 已經存在。要重新生成請加 --force（舊結果會因 world_id 不同，自動不納入統計）")
    size = SIZES[pilot]
    used: list[str] = []
    planned: dict[str, list[dict]] = {}
    for qtype in QTYPES:
        print(f"規劃題目：{qtype} × {size['per_type']} …")
        planned[qtype] = plan_questions(qtype, size["per_type"], used, model)
    draft = assemble(planned, [], pilot)
    n_fill = size["docs"] - len(draft["docs"])
    print(f"規劃背景文件 × {max(n_fill, 0)} …")
    facts = assemble(planned, plan_fillers(n_fill, draft, model) if n_fill > 0 else [], pilot)
    print(f"撰寫 {len(facts['docs'])} 份文件 …")
    bodies = write_bodies(facts["docs"], model)
    problems = validate(facts, bodies)
    for attempt in (1, 2):
        if not problems:
            break
        redo = _apply_fixes(facts, problems)
        print(f"第 {attempt} 次修正：重寫 {len(redo)} 份文件")
        bodies.update(write_bodies([d for d in facts["docs"] if d["id"] in redo], model))
        problems = validate(facts, bodies)
    save_world(facts, bodies)
    if problems:
        for p in problems:
            print(f"  ✗ {p['doc']} {p['kind']}：{p['detail']}")
        raise SystemExit(f"還有 {len(problems)} 個問題。可以手動修改 world/ 後執行 lab build，或加 --force 重新生成")
    print(f"完成：{len(facts['docs'])} 份文件、{len(facts['questions'])} 題，寫入 {FACTS.parent}")
```

- [ ] **Step 3：確認既有測試仍然通過**

Run: `uv run pytest -v`
Expected：27 passed（common 3 + trace 8 + score 9 + generate 7）

- [ ] **Step 4：煙霧測試（真的呼叫一次 Haiku，花費約幾美分）**

確認 `--json-schema` 能接受巢狀 schema，並回傳一題結構正確的題目。

Run:
```bash
uv run python -c "
from lab.generate import plan_questions
items = plan_questions('lookup', 1, [], 'haiku')
print(items[0]['question'], items[0]['must_include'], items[0]['gold'][0]['title'])
"
```
Expected：印出一行題目、答案字串清單和文件標題，沒有 traceback。如果出現 `RuntimeError: claude -p 沒有回傳結構化結果`，先把 stdout 印出來檢查，再調整 schema。

- [ ] **Step 5：Commit**

```bash
git add src/lab/generate.py
git commit -m "feat: 用 claude -p 規劃題目、背景文件並撰寫內文"
```

---

### Task 7：三組實驗資料夾（`build.py`）

**Files:**
- Create: `src/lab/build.py`
- Test: `tests/test_build.py`

- [ ] **Step 1：寫測試**

```python
import json

import pytest

from lab.build import SETTINGS, layout, render_index, stage_problems

FACTS = {"docs": [
    {"id": "D001", "title": "XR-7 規格書", "category": "產品", "slug": "XR-7-規格書"},
    {"id": "D002", "title": "補助|2025", "category": "人資", "slug": "補助-2025"},
    {"id": "D003", "title": "週會", "category": "會議紀錄", "slug": "週會"},
]}


def test_layout():
    maps = layout(FACTS)
    assert sorted(maps["A-messy"].values()) == ["docs/doc_001.md", "docs/doc_002.md", "docs/doc_003.md"]
    assert maps["B-organized"]["D002"] == "docs/人資/補助-2025.md"
    assert maps["C-indexed"] == maps["B-organized"]
    assert layout(FACTS) == maps   # 固定種子，可以重現


def test_layout_rejects_duplicate_paths():
    dup = {"docs": FACTS["docs"] + [{"id": "D004", "title": "x", "category": "產品", "slug": "XR-7-規格書"}]}
    with pytest.raises(ValueError):
        layout(dup)


def test_render_index_escapes_pipes_and_sorts_by_path():
    paths = layout(FACTS)["C-indexed"]
    rows = {d["id"]: {"summary": "摘要|有直線", "keywords": ["補助", "per diem"]} for d in FACTS["docs"]}
    lines = render_index(FACTS, paths, rows).splitlines()
    assert lines[0] == "# 文件索引"
    assert [line.split(" | ")[0][2:] for line in lines[4:]] == sorted(paths.values())
    text = "\n".join(lines)
    assert "補助／2025" in text and "摘要／有直線" in text and "補助、per diem" in text


def _write_stage(root, maps, bodies):
    for cond, paths in maps.items():
        for doc_id, rel in paths.items():
            f = root / cond / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(bodies[doc_id], encoding="utf-8")
        (root / cond / ".claude").mkdir(parents=True, exist_ok=True)
        (root / cond / ".claude" / "settings.json").write_text(json.dumps(SETTINGS), encoding="utf-8")
    (root / "C-indexed" / "CLAUDE.md").write_text("x")
    (root / "C-indexed" / "INDEX.md").write_text("x")


def test_stage_problems_detects_differences(tmp_path):
    maps = layout(FACTS)
    bodies = {"D001": "a\n", "D002": "b\n", "D003": "c\n"}
    _write_stage(tmp_path, maps, bodies)
    clean = [p for p in stage_problems(tmp_path, maps, bodies) if "家目錄" not in p and "上層" not in p]
    assert clean == []
    (tmp_path / "A-messy" / maps["A-messy"]["D001"]).write_text("改過\n", encoding="utf-8")
    (tmp_path / "B-organized" / "CLAUDE.md").write_text("x")
    problems = stage_problems(tmp_path, maps, bodies)
    assert any("A-messy" in p and "內文" in p for p in problems)
    assert any("B-organized" in p and "CLAUDE.md" in p for p in problems)
```

- [ ] **Step 2：確認測試失敗**

Run: `uv run pytest tests/test_build.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.build'`

- [ ] **Step 3：實作 `src/lab/build.py`**

```python
"""文件 → A/B/C 三個 Claude Code 專案（放在家目錄外的 stage 資料夾）。"""
from __future__ import annotations

import json
import random
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lab.common import (CONDS, CORPUS, FACTS, INDEX_CACHE, MAPPING, claude_json, is_under_home,
                        leaking_ancestors, load_json, save_json, sha256, stage_root)
from lab.generate import validate

SETTINGS = {"permissions": {"deny": ["Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"]}}

CLAUDE_MD = """# 資料查找指引
- 先讀 INDEX.md，依關鍵字找出候選文件，再打開文件確認內容。
- 同一主題有多個版本時，以日期最新的為準。
"""

INDEX_PROMPT = """你是文件管理員。請替下面每一份文件寫一列索引：
- summary：一句話（30 字以內）說明文件內容。
- keywords：5–10 個關鍵字，包含文件中的重要名詞，以及讀者可能改用的同義詞、口語說法和中英文對照。
- path：原樣照抄文件標籤上的 path。
只根據文件內容撰寫，不要編造。

"""

INDEX_SCHEMA = {
    "type": "object",
    "properties": {"rows": {"type": "array", "items": {
        "type": "object",
        "properties": {"path": {"type": "string"}, "summary": {"type": "string"},
                       "keywords": {"type": "array", "items": {"type": "string"}}},
        "required": ["path", "summary", "keywords"],
    }}},
    "required": ["rows"],
}


def layout(facts: dict, seed: int = 42) -> dict[str, dict[str, str]]:
    """每一組的 doc_id → 相對路徑。A 用固定種子打亂編號；B、C 用類別資料夾＋slug。"""
    ids = [d["id"] for d in facts["docs"]]
    shuffled = ids[:]
    random.Random(seed).shuffle(shuffled)
    messy = {doc_id: f"docs/doc_{i:03d}.md" for i, doc_id in enumerate(shuffled, 1)}
    organized = {d["id"]: f"docs/{d['category']}/{d['slug']}.md" for d in facts["docs"]}
    if len(set(organized.values())) != len(organized):
        raise ValueError("B 組有重複的檔案路徑，請檢查 slug")
    return {"A-messy": messy, "B-organized": organized, "C-indexed": dict(organized)}


def _cell(text: str) -> str:
    return text.replace("|", "／").replace("\n", " ").strip()


def render_index(facts: dict, paths: dict[str, str], rows: dict[str, dict]) -> str:
    lines = ["# 文件索引", "", "| 路徑 | 標題 | 摘要 | 關鍵字 |", "|---|---|---|---|"]
    for d in sorted(facts["docs"], key=lambda d: paths[d["id"]]):
        r = rows[d["id"]]
        lines.append(f"| {paths[d['id']]} | {_cell(d['title'])} | {_cell(r['summary'])} | "
                     f"{_cell('、'.join(r['keywords']))} |")
    return "\n".join(lines) + "\n"


def index_rows(facts: dict, bodies: dict[str, str], paths: dict[str, str], model: str,
               batch: int = 10, workers: int = 4) -> dict[str, dict]:
    """盲建索引：每一批只給文件內容，完全不給題目。結果快取在 world/index_rows.json。"""
    cache = load_json(INDEX_CACHE) if INDEX_CACHE.exists() else {}

    def stale(doc_id: str) -> bool:
        return cache.get(doc_id, {}).get("sha") != sha256(bodies[doc_id])

    todo = [d["id"] for d in facts["docs"] if stale(d["id"])]
    lock = threading.Lock()

    def work(ids: list[str]) -> None:
        docs = "\n\n".join(f'<document path="{paths[i]}">\n{bodies[i]}\n</document>' for i in ids)
        try:
            out = claude_json(INDEX_PROMPT + docs, INDEX_SCHEMA, model)
        except Exception as e:  # noqa: BLE001
            print(f"  索引批次失敗（{', '.join(ids)}）：{e}")
            return
        by_path = {r["path"]: r for r in out["rows"]}
        with lock:
            for i in ids:
                if r := by_path.get(paths[i]):
                    cache[i] = {"sha": sha256(bodies[i]), "summary": r["summary"], "keywords": r["keywords"]}
            save_json(INDEX_CACHE, cache)

    if todo:
        print(f"盲建索引：{len(todo)} 份文件 …")
        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(work, [todo[i:i + batch] for i in range(0, len(todo), batch)]))
    missing = [d["id"] for d in facts["docs"] if stale(d["id"])]
    if missing:
        raise SystemExit(f"這些文件沒有索引，請重跑 lab build：{', '.join(missing)}")
    return cache


def load_bodies(facts: dict) -> dict[str, str]:
    return {d["id"]: (CORPUS / f"{d['id']}.md").read_text(encoding="utf-8") for d in facts["docs"]}


def stage_problems(root: Path, maps: dict, bodies: dict[str, str]) -> list[str]:
    """檢查 stage：位置、上層指示檔、三組內文逐字相同、設定一致、只有 C 有 CLAUDE.md 和 INDEX.md。"""
    problems = []
    if is_under_home(root):
        problems.append(f"stage 資料夾在家目錄底下：{root}")
    problems += [f"上層資料夾有指示檔：{p}" for p in leaking_ancestors(root)]
    for cond in CONDS:
        cdir = root / cond
        settings = cdir / ".claude" / "settings.json"
        if not settings.exists() or json.loads(settings.read_text(encoding="utf-8")) != SETTINGS:
            problems.append(f"{cond} 的 .claude/settings.json 不符")
        for name in ("CLAUDE.md", "INDEX.md"):
            if (cdir / name).exists() != (cond == "C-indexed"):
                problems.append(f"{cond} 的 {name} 狀態不符")
        for doc_id, rel in maps[cond].items():
            f = cdir / rel
            if not f.exists() or sha256(f.read_text(encoding="utf-8")) != sha256(bodies[doc_id]):
                problems.append(f"{cond}/{rel} 內文與標準正文不同")
    return problems


def build(model: str = "sonnet") -> None:
    facts = load_json(FACTS)
    bodies = load_bodies(facts)
    if problems := validate(facts, bodies):
        raise SystemExit("事實表驗證失敗：\n" + "\n".join(f"- {p['doc']} {p['kind']}：{p['detail']}" for p in problems))
    root = stage_root()
    if is_under_home(root):
        raise SystemExit(f"stage 資料夾不能在家目錄底下：{root}（用 LAB_STAGE 換位置）")
    maps = layout(facts)
    rows = index_rows(facts, bodies, maps["C-indexed"], model)
    for cond in CONDS:
        cdir = root / cond
        if cdir.exists():
            shutil.rmtree(cdir)
        for doc_id, rel in maps[cond].items():
            target = cdir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(bodies[doc_id], encoding="utf-8")
        save_json(cdir / ".claude" / "settings.json", SETTINGS)
    (root / "C-indexed" / "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    (root / "C-indexed" / "INDEX.md").write_text(render_index(facts, maps["C-indexed"], rows), encoding="utf-8")
    save_json(MAPPING, maps)
    if problems := stage_problems(root, maps, bodies):
        raise SystemExit("建置後檢查失敗：\n" + "\n".join(f"- {p}" for p in problems))
    print(f"完成：{root}（{len(facts['docs'])} 份文件 × 3 組）")
```

- [ ] **Step 4：確認測試通過**

Run: `uv run pytest tests/test_build.py -v`
Expected：4 passed

- [ ] **Step 5：Commit**

```bash
git add src/lab/build.py tests/test_build.py
git commit -m "feat: 建立三組實驗資料夾並盲建索引"
```

---

### Task 8：評測執行（`run.py`）

**Files:**
- Create: `src/lab/run.py`
- Test: `tests/test_run.py`

- [ ] **Step 1：寫測試**

```python
import json

from lab.run import ANSWER_SCHEMA, ask_cmd, done_keys


def test_ask_cmd_has_isolation_flags():
    cmd = ask_cmd("問題", "haiku", "medium")
    assert cmd[:3] == ["claude", "-p", "問題"]
    for flag in ["--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence", "--verbose"]:
        assert flag in cmd
    assert cmd[cmd.index("--setting-sources") + 1] == "project"
    assert cmd[cmd.index("--tools") + 1] == "Read,Grep,Glob"
    assert cmd[cmd.index("--effort") + 1] == "medium"
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == ANSWER_SCHEMA


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
```

- [ ] **Step 2：確認測試失敗**

Run: `uv run pytest tests/test_run.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.run'`

- [ ] **Step 3：實作 `src/lab/run.py`**

```python
"""跑評測：每一題在每一組的資料夾裡執行一次 claude -p，結果附加到 results/results.jsonl。"""
from __future__ import annotations

import json
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from lab.build import load_bodies, stage_problems
from lab.common import (CONDS, FACTS, ISOLATION, MAPPING, RESULTS_JSONL, RUNS, load_json, read_rows,
                        stage_root, world_id)
from lab.trace import isolation_problems, parse_stream, summarize

PROMPT = """你是公司內部的資料查詢助理。請只根據目前資料夾裡的文件回答下面的問題，不要憑自己的知識。
如果文件中找不到答案，found 填 false，answer 說明找不到。
sources 列出你實際用來回答的文件路徑（相對於目前資料夾）。
數字請用阿拉伯數字。

問題：{question}"""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"},
                   "sources": {"type": "array", "items": {"type": "string"}},
                   "found": {"type": "boolean"}},
    "required": ["answer", "sources", "found"],
}

PREFLIGHT_PROMPT = "這是連線檢查：不要使用任何工具，直接回答 answer=ok、sources 留空、found=false。"


def ask_cmd(prompt: str, model: str, effort: str) -> list[str]:
    return ["claude", "-p", prompt, "--model", model, "--effort", effort,
            "--tools", "Read,Grep,Glob", "--output-format", "stream-json", "--verbose",
            "--json-schema", json.dumps(ANSWER_SCHEMA, ensure_ascii=False), *ISOLATION]


def done_keys(rows: list[dict], wid: str, model: str, effort: str) -> set[tuple[int, str, str]]:
    """已經成功跑完的 (round, cond, qid)，續跑時跳過。"""
    return {(r["round"], r["cond"], r["qid"]) for r in rows
            if r["world_id"] == wid and r["model"] == model and r["effort"] == effort and r["status"] == "ok"}


def preflight(maps: dict, model: str, effort: str) -> None:
    """開跑前檢查（設計第 6.2 節）。每組各用一次檢查呼叫確認隔離。任何一項不通過就整輪中止。"""
    root = stage_root()
    problems = stage_problems(root, maps, load_bodies(load_json(FACTS)))
    for cond in CONDS:
        proc = subprocess.run(ask_cmd(PREFLIGHT_PROMPT, model, effort), cwd=root / cond,
                              capture_output=True, text=True, timeout=180)
        problems += [f"{cond}：{p}" for p in isolation_problems(parse_stream(proc.stdout))]
    if problems:
        raise SystemExit("開跑前檢查失敗：\n" + "\n".join(f"- {p}" for p in problems))
    print("開跑前檢查通過")


def ask_one(rnd: int, cond: str, q: dict, paths: dict[str, str], model: str, effort: str,
            timeout: int, wid: str) -> dict:
    cdir = stage_root() / cond
    raw = RUNS / wid / f"{model}-{effort}" / f"r{rnd}" / cond / f"{q['id']}.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    error = None
    try:
        proc = subprocess.run(ask_cmd(PROMPT.format(question=q["question"]), model, effort),
                              cwd=cdir, capture_output=True, text=True, timeout=timeout)
        out = proc.stdout
        if proc.returncode != 0:
            error = f"exit {proc.returncode}：{proc.stderr[-300:]}"
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        error = f"逾時（{timeout} 秒）"
    raw.write_text(out, encoding="utf-8")
    row = summarize(parse_stream(out), [str(cdir), str(cdir.resolve())], set(paths.values()))
    if error:
        row["status"], row["error"] = "error", error
    return {"world_id": wid, "model": model, "effort": effort, "round": rnd, "cond": cond,
            "qid": q["id"], "ts": datetime.now().isoformat(timespec="seconds"), **row}


def run(rounds: int, model: str = "haiku", effort: str = "medium", workers: int = 4, timeout: int = 180) -> None:
    facts, maps, wid = load_json(FACTS), load_json(MAPPING), world_id()
    preflight(maps, model, effort)
    done = done_keys(read_rows(), wid, model, effort)
    RESULTS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    for rnd in range(1, rounds + 1):
        tasks = [(cond, q) for cond in CONDS for q in facts["questions"] if (rnd, cond, q["id"]) not in done]
        if not tasks:
            print(f"第 {rnd} 輪已經完成，跳過")
            continue
        random.Random(rnd).shuffle(tasks)
        print(f"第 {rnd} 輪：{len(tasks)} 次呼叫")
        with ThreadPoolExecutor(workers) as pool:
            futures = [pool.submit(ask_one, rnd, cond, q, maps[cond], model, effort, timeout, wid)
                       for cond, q in tasks]
            for i, fut in enumerate(as_completed(futures), 1):
                row = fut.result()
                with RESULTS_JSONL.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                mark = "✓" if row["status"] == "ok" else f"✗ {row['error']}"
                print(f"  [{i}/{len(tasks)}] {row['cond']} {row['qid']} {mark}")
```

- [ ] **Step 4：確認測試通過**

Run: `uv run pytest tests/test_run.py -v`
Expected：2 passed

- [ ] **Step 5：Commit**

```bash
git add src/lab/run.py tests/test_run.py
git commit -m "feat: 評測執行（開跑前檢查、平行呼叫、可續跑）"
```

---

### Task 9：統計與網頁資料（`report.py`）

**Files:**
- Create: `src/lab/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1：寫測試**

```python
from lab.report import aggregate


def r(cond, qid, rnd, correct, qtype="lookup", **kw):
    base = {"cond": cond, "qid": qid, "round": rnd, "type": qtype, "correct": correct, "hallucinated": False,
            "retrieved": correct, "citation_hit": correct, "tool_calls": 2, "files_read_n": 1,
            "duration_s": 3.0, "cost_usd": 0.01, "index_used": False}
    return base | kw


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
```

- [ ] **Step 2：確認測試失敗**

Run: `uv run pytest tests/test_report.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.report'`

- [ ] **Step 3：實作 `src/lab/report.py`**

```python
"""統計：results.jsonl → results/report.md、results.csv、dashboard.json。"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from statistics import mean

from lab.common import (COND_LABELS, CONDS, FACTS, MAPPING, QTYPE_LABELS, QTYPES, RESULTS, load_json,
                        read_rows, save_json, stage_root, world_id)
from lab.score import score

METRICS = [("correct", "答對率"), ("hallucinated", "幻覺率"), ("retrieved", "檢索命中率"),
           ("citation_hit", "引用命中率"), ("index_used", "讀了索引")]
EFFICIENCY = [("tool_calls", "平均工具呼叫"), ("files_read_n", "平均讀檔數"),
              ("duration_s", "平均秒數"), ("cost_usd", "平均花費 USD")]
PAIRS = [("A-messy", "C-indexed"), ("B-organized", "C-indexed"), ("A-messy", "B-organized")]
CSV_FIELDS = ["model", "effort", "round", "cond", "qid", "type", "correct", "hallucinated", "stale",
              "retrieved", "read_gold", "citation_hit", "citation_precision", "index_used", "tool_calls",
              "files_read_n", "duration_s", "cost_usd", "found", "answer"]


def _avg(values) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return mean(vals) if vals else None


def scored_rows(rows: list[dict], questions: dict[str, dict], maps: dict) -> list[dict]:
    return [{**r, **score(r, questions[r["qid"]], maps[r["cond"]]), "type": questions[r["qid"]]["type"],
             "files_read_n": len(r["files_read"]), "duration_s": (r["duration_ms"] or 0) / 1000}
            for r in rows]


def aggregate(rows: list[dict]) -> dict:
    """rows：已評分且 status=ok 的列。回傳主表、題型表、逐題答對比例、多數決與成對比較。"""
    rounds = sorted({r["round"] for r in rows})
    keys = [k for k, _ in METRICS + EFFICIENCY]
    summary: dict[str, dict] = {}
    for cond in CONDS:
        per_round = []
        for rnd in rounds:
            rr = [r for r in rows if r["cond"] == cond and r["round"] == rnd]
            if rr:
                per_round.append({k: _avg([r.get(k) for r in rr]) for k in keys})
        summary[cond] = {}
        for k in keys:
            vals = [p[k] for p in per_round if p[k] is not None]
            summary[cond][k] = {"mean": mean(vals) if vals else None,
                                "min": min(vals, default=None), "max": max(vals, default=None)}
    outcomes: dict[str, dict[str, list[bool]]] = {}
    qtype: dict[str, str] = {}
    for r in rows:
        outcomes.setdefault(r["qid"], {}).setdefault(r["cond"], []).append(bool(r["correct"]))
        qtype[r["qid"]] = r["type"]
    props = {qid: {c: mean(map(float, v)) for c, v in conds.items()} for qid, conds in outcomes.items()}
    majority = {qid: {c: None if p == 0.5 else p > 0.5 for c, p in conds.items()}
                for qid, conds in props.items()}
    by_type = {c: {t: _avg([props[q][c] for q in props if qtype[q] == t and c in props[q]]) for t in QTYPES}
               for c in CONDS}
    paired = []
    for x, y in PAIRS:
        both = [q for q in majority if majority[q].get(x) is not None and majority[q].get(y) is not None]
        paired.append({"x": x, "y": y, "n": len(both),
                       "x_only": sum(1 for q in both if majority[q][x] and not majority[q][y]),
                       "y_only": sum(1 for q in both if majority[q][y] and not majority[q][x])})
    return {"rounds": rounds, "n_questions": len(props), "summary": summary, "by_type": by_type,
            "per_question": props, "majority": majority, "paired": paired}


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def _num(v: float | None, digits: int = 1) -> str:
    return "—" if v is None else f"{v:.{digits}f}"


def render_markdown(agg: dict, model: str, effort: str, errors: dict[str, int]) -> str:
    cols = METRICS + EFFICIENCY
    lines = ["# Retrieval Lab 結果", "",
             f"- 模型：{model}（effort {effort}）",
             f"- 題數 n = {agg['n_questions']}，輪數 {len(agg['rounds'])}",
             f"- 產生時間：{datetime.now():%Y-%m-%d %H:%M}", "",
             "## 總表（各輪平均，括號內為各輪最低–最高）", "",
             "| 組別 | " + " | ".join(label for _, label in cols) + " | 錯誤筆數 |",
             "|" + "---|" * (len(cols) + 2)]
    for cond in CONDS:
        s = agg["summary"][cond]
        cells = [f"{_pct(s[k]['mean'])}（{_pct(s[k]['min'])}–{_pct(s[k]['max'])}）" for k, _ in METRICS]
        cells += [_num(s[k]["mean"], 4 if k == "cost_usd" else 1) for k, _ in EFFICIENCY]
        lines.append(f"| {COND_LABELS[cond]} | " + " | ".join(cells) + f" | {errors.get(cond, 0)} |")
    lines += ["", "## 各題型答對率", "",
              "| 組別 | " + " | ".join(QTYPE_LABELS[t] for t in QTYPES) + " |",
              "|" + "---|" * (len(QTYPES) + 1)]
    for cond in CONDS:
        cells = [_pct(agg["by_type"][cond][t]) for t in QTYPES]
        lines.append(f"| {COND_LABELS[cond]} | " + " | ".join(cells) + " |")
    lines += ["", "## 成對比較（每題取多輪多數決）", "",
              "| 比較 | 只有前者答對 | 只有後者答對 | 可比較題數 |", "|---|---|---|---|"]
    for p in agg["paired"]:
        lines.append(f"| {COND_LABELS[p['x']]} vs {COND_LABELS[p['y']]} | {p['x_only']} | {p['y_only']} | {p['n']} |")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:   # utf-8-sig：用 Excel 開啟時中文不會變亂碼
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["round"], r["cond"], r["qid"])))


def _clean(text: str) -> str:
    """去掉 stage 路徑和家目錄路徑，避免把本機資訊放上網頁。"""
    for cond in CONDS:
        text = text.replace(f"{stage_root()}/{cond}/", "")
    return text.replace(str(stage_root()), "").replace(str(Path.home()), "~")


def dashboard(agg: dict, rows: list[dict], facts: dict, maps: dict, model: str, effort: str) -> dict:
    questions = []
    for q in facts["questions"]:
        results = {cond: [{"round": r["round"], "answer": _clean(r["answer"]), "found": r["found"],
                           "correct": r["correct"], "retrieved": r["retrieved"],
                           "index_used": r.get("index_used"), "files_read": r["files_read"],
                           "files_grep": r["files_grep_content"], "tool_calls": r["tool_calls"],
                           "duration_s": round(r["duration_s"], 1)}
                          for r in sorted(rows, key=lambda r: r["round"])
                          if r["qid"] == q["id"] and r["cond"] == cond]
                   for cond in CONDS}
        questions.append({"id": q["id"], "type": q["type"], "question": q["question"],
                          "gold_answer": "、".join(q["must_include"]) or "（文件中沒有，應該回答找不到）",
                          "gold_files": {cond: [maps[cond][d] for d in q["gold_docs"]] for cond in CONDS},
                          "results": results})
    return {"generated_at": datetime.now().isoformat(timespec="minutes"), "model": model, "effort": effort,
            "claude_versions": sorted({r["claude_version"] for r in rows if r.get("claude_version")}),
            "n_questions": agg["n_questions"], "rounds": agg["rounds"],
            "conds": [{"id": c, "label": COND_LABELS[c]} for c in CONDS],
            "qtypes": [{"id": t, "label": QTYPE_LABELS[t]} for t in QTYPES],
            "summary": agg["summary"], "by_type": agg["by_type"], "paired": agg["paired"],
            "questions": questions}


def report(model: str = "haiku", effort: str = "medium") -> None:
    facts, maps, wid = load_json(FACTS), load_json(MAPPING), world_id()
    rows = [r for r in read_rows() if r["world_id"] == wid and r["model"] == model and r["effort"] == effort]
    ok = [r for r in rows if r["status"] == "ok"]
    if not ok:
        raise SystemExit("還沒有可用的結果，請先執行 lab run")
    ok_keys = {(r["round"], r["cond"], r["qid"]) for r in ok}
    errors = {c: len({(r["round"], r["qid"]) for r in rows if r["cond"] == c and r["status"] != "ok"
                      and (r["round"], r["cond"], r["qid"]) not in ok_keys}) for c in CONDS}
    scored = scored_rows(ok, {q["id"]: q for q in facts["questions"]}, maps)
    agg = aggregate(scored)
    RESULTS.mkdir(parents=True, exist_ok=True)
    text = render_markdown(agg, model, effort, errors)
    (RESULTS / "report.md").write_text(text, encoding="utf-8")
    write_csv(RESULTS / "results.csv", scored)
    save_json(RESULTS / "dashboard.json", dashboard(agg, scored, facts, maps, model, effort))
    print(text)
```

- [ ] **Step 4：確認全部測試通過**

Run: `uv run pytest -v`
Expected：35 passed（common 3 + trace 8 + score 9 + generate 7 + build 4 + run 2 + report 2）

- [ ] **Step 5：Commit**

```bash
git add src/lab/report.py tests/test_report.py
git commit -m "feat: 統計報表、CSV 與網頁資料"
```

---

### Task 10：試跑——生成與審題

這一步會實際呼叫 Sonnet，約十幾次。

- [ ] **Step 1：生成試跑規模的世界**

Run: `uv run lab generate --pilot`
Expected：最後一行是 `完成：20 份文件、10 題，寫入 …/world`

如果結尾是 `還有 N 個問題`：
- 問題少，就手動修改 `world/corpus/Dxxx.md` 或 `world/facts.json`。
- 問題多，就執行 `uv run lab generate --pilot --force` 重新生成。

- [ ] **Step 2：列出題目給使用者審閱**

Run:
```bash
jq -r '.questions[] | "\(.id)｜\(.type)｜\(.question)｜答案：\(.must_include | join("、"))｜舊值：\(.must_not_include | join("、"))｜探測：\(.probe_terms | join("＋"))"' world/facts.json
```

再列出「答案字串也出現在非 gold 文件」的情況。這種情況下，Claude 可能從別份文件答對，檢索命中卻記為未命中：

```bash
uv run python -c "
from lab.build import load_bodies
from lab.common import FACTS, load_json
from lab.generate import answer_leaks
facts = load_json(FACTS)
for qid, token, doc in answer_leaks(facts, load_bodies(facts)):
    print(f'{qid}：答案「{token}」也出現在非 gold 文件 {doc}')
"
```
Expected：沒有輸出最理想。有輸出的話，審題時一併請使用者決定：改答案字串、改那份文件，或接受（例如只是巧合出現同一個數字）。

- [ ] **Step 3：停下來，請使用者審題**

把 10 題和答案外洩清單貼給使用者，請他確認題目是否合理、答案是否明確。依照意見修改 `world/facts.json`；有改到答案的話，也要同步修改對應的 `world/corpus/` 文件。

使用者同意後才進入下一步。

- [ ] **Step 4：Commit**

```bash
git add world
git commit -m "data: 試跑用的虛構世界（20 份文件、10 題）"
```

---

### Task 11：試跑——建置、評測、校正

- [ ] **Step 1：建置三組**

Run: `uv run lab build`
Expected：`完成：/Users/Shared/retrieval-lab-stage（20 份文件 × 3 組）`

- [ ] **Step 2：抽查 stage 的內容**

Run:
```bash
find /Users/Shared/retrieval-lab-stage -path '*/docs/*' -name '*.md' | wc -l
head -8 /Users/Shared/retrieval-lab-stage/C-indexed/INDEX.md
ls /Users/Shared/retrieval-lab-stage/A-messy/docs | head -3
```
Expected：
- 第一行輸出 `60`。
- INDEX.md 的表頭是 `| 路徑 | 標題 | 摘要 | 關鍵字 |`，關鍵字欄有同義詞。
- A 組的檔名是 `doc_001.md` 這種格式。

- [ ] **Step 3：Commit 建置產物**

```bash
git add build/mapping.json world/index_rows.json
git commit -m "data: 試跑的檔案對照表與盲建索引"
```

- [ ] **Step 4：跑 1 輪**

Run: `uv run lab run --rounds 1`
Expected：
- 先印出 `開跑前檢查通過`，接著是 30 行 `[i/30] … ✓`。
- 若出現 `✗`，重跑同一個指令就會只補跑失敗的題目。
- 若開跑前檢查失敗，依訊息修正（多半是 stage 位置或上層有指示檔），**不要**跳過檢查。

- [ ] **Step 5：產生報表**

Run: `uv run lab report`
Expected：印出三張表（總表、各題型答對率、成對比較），並寫出 `results/report.md`、`results/results.csv`、`results/dashboard.json`。

- [ ] **Step 6：人工抽查評分**

Run:
```bash
jq -r '.questions[] | .question as $q | .gold_answer as $g | .results | to_entries[] | .key as $c | .value[] | "\($c)｜\($q)｜標準：\($g)｜回答：\(.answer)｜判定：\(.correct)"' results/dashboard.json | head -30
```
至少逐筆看 10 筆，確認「判定」跟人的判斷一致。

如果有判錯的情況（例如答案用了不同寫法），先在 `tests/test_score.py` 加一個會失敗的測試重現它，再修改 `score.py` 或 `common.norm`，讓測試通過，然後重新執行 `uv run lab report`。

接著列出 C 組「答對、但沒碰過 gold 文件」的紀錄，看看 Claude 是不是直接從 INDEX.md 的摘要拿到答案。這種情況會讓 C 組的檢索命中率看起來偏低：

```bash
jq -r '.questions[] | .id as $id | .results["C-indexed"][] | select(.correct and .retrieved == false) | "\($id) 第 \(.round) 輪：答對但沒碰過 gold 文件（讀了索引：\(.index_used)）"' results/dashboard.json
```

- [ ] **Step 7：校正用量估算**

Run:
```bash
uv run python -c "
import csv
rows = list(csv.DictReader(open('results/results.csv', encoding='utf-8-sig')))
n = len(rows)
print('呼叫數', n)
print('平均花費 USD', sum(float(r['cost_usd'] or 0) for r in rows) / n)
print('平均秒數', sum(float(r['duration_s']) for r in rows) / n)
"
```
用實測數字更新設計文件：
- **第 12 節：** 換成實測的每次花費、時間，以及正式版一輪（120 次）的估算。
- **第 14 節：** 把已確認的項目標成「已確認」。內容包括：`--effort medium` 可用、Grep 內文格式、`/Users/Shared` 可寫入，以及開跑前檢查改用「每組一次專用的檢查呼叫」實作。

- [ ] **Step 8：停下來，向使用者回報試跑結果**

試跑只用來確認**流程和評分正確**，不用來判斷難度。20 份文件時 Grep 幾乎什麼都找得到，三組很可能都接近滿分，但這不代表 200 份時也一樣。難度留到 Task 12，用正式版第 1 輪判斷。

回報內容：
- 總表與題型表，並說明在試跑規模下接近滿分是預期中的事。
- 抽查結果，以及 Step 6 找到的評分問題與修正。
- C 組「答對但沒碰過 gold 文件」的筆數（Step 6 第二個指令）。
- 實測用量，以及正式版預估的時間和花費。

使用者同意後才進入正式版。

- [ ] **Step 9：Commit**

```bash
git add results docs/superpowers/specs/2026-11-14-retrieval-lab-design.md
git commit -m "data: 試跑結果與用量校正"
```

---

### Task 12：正式版

- [ ] **Step 1：生成正式規模的世界**

這一步約 70 次 Sonnet 呼叫。

Run: `uv run lab generate --force`
Expected：`完成：200 份文件、40 題，寫入 …/world`

舊的試跑結果會因為 world_id 不同，自動不納入統計。試跑資料仍保留在 git 歷史裡。

- [ ] **Step 2：列出 40 題，停下來請使用者審題**

指令同 Task 10 Step 2（題目清單和答案外洩清單兩個都要跑）。使用者同意後才繼續。

- [ ] **Step 3：建置並 commit**

Run: `uv run lab build`
Expected：`完成：/Users/Shared/retrieval-lab-stage（200 份文件 × 3 組）`

```bash
git add world build/mapping.json
git commit -m "data: 正式版虛構世界（200 份文件、40 題）與盲建索引"
```

- [ ] **Step 4：先跑第 1 輪**

120 次呼叫。

Run: `uv run lab run --rounds 1 && uv run lab report`
Expected：先印出 `開跑前檢查通過`，接著 120 行，最後印出報表。中斷的話，重跑同一個指令即可續跑。

- [ ] **Step 5：停下來，用第 1 輪判斷難度**

把總表、題型表，以及 C 組「答對但沒碰過 gold 文件」的筆數（指令同 Task 11 Step 6）回報給使用者。

如果三組在多數題型都是 100%（天花板效應）或都是 0%，向使用者提出**對三組一視同仁**的調整，例如題目改得更口語、增加干擾文件。不可以針對某一組調整。

調整就等於換一個新世界，要回到 Step 1 重新生成。舊的第 1 輪會因為 world_id 不同，自動不納入統計。

使用者同意維持現狀後才繼續。

- [ ] **Step 6：補跑第 2、3 輪，產生報表並 commit**

240 次呼叫。

Run: `uv run lab run --rounds 3 && uv run lab report`
Expected：第 1 輪顯示「已經完成，跳過」，接著跑第 2、3 輪，最後印出報表。

```bash
git add results
git commit -m "data: 正式版 3 輪評測結果"
```

---

### Task 13：互動網頁

**這一步在 Claude Code session 裡用 Artifact 工具完成，不是 Python 程式。**

- [ ] **Step 1：發布前做隱私檢查**

Run: `grep -c '/Users/' results/dashboard.json`
Expected：`0`。不是 0 的話，先修正 `report._clean` 再重產報表。

- [ ] **Step 2：建立網頁**

1. 呼叫 Artifact `quickstart`，intent 設為 `other`（呈現資料的儀表板）。
2. 如果結果指示使用 Dashboard 型別，就照該型別的說明建立；否則手寫一頁 HTML，並先載入 `artifact-design` 和 `dataviz` 技能。
3. 資料一律來自 `results/dashboard.json`。

頁面內容依設計第 9 節：

| 區塊 | 內容 |
|---|---|
| 總覽 | 三組的答對率、檢索命中率、幻覺率長條圖（`summary.<cond>.<metric>.mean`，誤差範圍用 min–max）；效率數字（平均工具呼叫、讀檔數、秒數）；C 組讀了索引的比例 |
| 題型 × 組別熱度表 | `by_type` |
| 成對比較 | `paired`，標出可比較題數 n |
| 逐題展開 | 依題型篩選，每題顯示題目、標準答案、三組各輪的回答、讀過的檔案、對錯 |
| 頁尾 | 模型、effort、輪數、題數、Claude Code 版本、產生時間 |

- [ ] **Step 3：發布並回報**

發布後把連結給使用者，並提醒兩件事：
- 頁面預設只有本人看得到，要給同學看需要從 Share 選單分享。
- 之後跑了新的輪數，執行 `uv run lab report` 後請 Claude 重新發布，連結不會變。
