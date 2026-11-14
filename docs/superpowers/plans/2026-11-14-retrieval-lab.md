# Retrieval Lab 實作計畫（v2：官方文件版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目標：** 做出可重複執行的評測工具。用 221 頁官方文件（LangChain、LangGraph、Deep Agents、Claude Agent SDK）和 Codex 出的 40 道題目，比較三種資料整理方式對 Claude Code 檢索與回答準確度的影響：A 雜亂、B 整理、C 索引。另外加上閉卷對照組，排除憑記憶就能答對的題目。

**架構：** 每一步都是一個 `uv run lab <子指令>`，順序如下：

`collect → (Codex 出題) → check → build → closed → run → report`

- 三組實驗資料夾建在家目錄外的 stage 資料夾。
- 每一題在每一組各跑一次 `claude -p`（Haiku），只開 Read、Grep、Glob 三個工具。
- 從 stream-json 的工具紀錄判斷 Claude 找到了哪些文件。
- 用程式比對答案評分，不用 LLM 評審。

**技術：** Python 3.12+（uv）、只用標準函式庫、pytest、Claude Code CLI 2.1.325、Codex CLI 0.169.0（出題）。

**設計文件：** `docs/superpowers/specs/2026-11-14-retrieval-lab-design.md`（以下稱「設計」）。

---

## 已實測確認的事實

### 隔離與執行環境

- 隔離參數是 `--strict-mcp-config --setting-sources project --disable-slash-commands --no-session-persistence`。
  - 工作目錄在家目錄外時，不會載入使用者的 CLAUDE.md、AGENTS.md、hooks 和 MCP。
  - 工作目錄在家目錄內時，`~/AGENTS.md` 和 `~/.claude/CLAUDE.md` 會被當成上層指示載入。
- 專案 `.claude/settings.json` 的 hooks 在未信任的工作區也會執行，但 `permissions.allow` 會被忽略。
- `claude -p` 的 stdin 不是終端機時，會先等 3 秒，所以所有呼叫都要加 `stdin=subprocess.DEVNULL`。
- `/Users/Shared` 可以寫入，它的上層資料夾都沒有 CLAUDE.md 或 AGENTS.md。

### stream-json 格式（要搭配 `--verbose`）

| 事件 | 格式 |
|---|---|
| init | `{"type":"system","subtype":"init","tools":[...],"mcp_servers":[],"skills":[],"slash_commands":[],"model":"claude-haiku-5-5","claude_code_version":"2.1.325",...}` |
| 工具呼叫 | `{"type":"assistant","message":{"content":[{"type":"tool_use","id":...,"name":...,"input":{...}}]}}` |
| 工具結果 | `{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":...,"content":"文字","is_error":...}]},"tool_use_result":<結構化結果>}` |
| 結束 | `{"type":"result","subtype":"success","num_turns":..,"duration_ms":..,"total_cost_usd":..,"usage":{...},"structured_output":{...}}` |
| hook | 預設**不會**輸出。加 `--include-hook-events` 後會出現 `{"type":"system","subtype":"hook_started"/"hook_response",...}` |

各工具的 `tool_use_result`：

| 工具 | 結構 |
|---|---|
| Glob | `{"filenames":[...]}` |
| Grep（內文模式） | `{"mode":"content","content":"path:2:..."}` |
| Grep（只列檔名） | `{"mode":"files_with_matches","filenames":[...]}` |
| Read | `{"type":"text","file":{"filePath":...}}` |

### 評測行為

- `--json-schema` 可以跟工具並用，結果放在 `result.structured_output`。
- `--tools ""` 也能用，這時 init 的工具只剩 `StructuredOutput`。
- Haiku 支援 `--effort`，本計畫固定用 `medium`。
- init 的 `memory_paths` 只有 auto memory 目錄，不能拿來確認 CLAUDE.md 有沒有載入。行為上的證據是：C 組的第一個動作就是讀 `INDEX.md`。
- 有些呼叫只看 Grep 的內文結果就作答，完全沒有 Read。

### 文件來源

- `https://codeload.github.com/langchain-ai/docs/tar.gz/main`：MIT 授權，路徑是 `docs-main/src/oss/{langchain,langgraph,deepagents}/**/*.mdx`，共 79、44、58 頁。
  - 頁面平均約 1.9 萬字元，最長約 11 萬字元。
  - 開頭有 frontmatter（`title:`）。
- `https://code.claude.com/docs/llms.txt`：列出 40 個 `https://code.claude.com/docs/en/agent-sdk/<頁>.md`。
  - 每頁開頭有一段固定的 `> ## Documentation Index` 引言。

## 共通規則

- **Commit：** 作者用 repo 已設定的 `kevin801221 <kevin801221@users.noreply.github.com>`，訊息**不加** Claude 署名，也不 push。
- **指令：** 都在 `~/test-dir-1/retrieval-lab/` 底下執行。Python 一律用 `uv run`。

## 檔案結構

| 檔案 | 職責 |
|---|---|
| `pyproject.toml`、`.gitignore`、`README.md` | 專案設定與說明 |
| `docs/codex-questions.md` | 給 Codex 的出題說明 |
| `src/lab/cli.py` | 子指令分派 |
| `src/lab/common.py` | 路徑、常數、正規化、讀取世界資料、家目錄檢查、`claude_json()` |
| `src/lab/collect.py` | 下載官方文件 |
| `src/lab/world.py` | 檢查題目（`check_questions` 是純函式），以及 `lab check` |
| `src/lab/trace.py` | 解析 stream-json、找出碰過的檔案、隔離檢查（純函式） |
| `src/lab/score.py` | 評分（純函式） |
| `src/lab/build.py` | 三組版面、盲建索引、寫入 stage、檢查 stage |
| `src/lab/run.py` | 評測與閉卷對照 |
| `src/lab/report.py` | 彙整、輸出 report.md、results.csv、dashboard.json |
| `tests/test_*.py` | 每個純函式模組一個測試檔 |

---

### Task 1：專案骨架

**Files:**
- Create：`pyproject.toml`、`.gitignore`、`README.md`、`src/lab/__init__.py`、`src/lab/cli.py`

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

這個檔案會 import `lab.common`，所以 `lab --help` 要等 Task 2 完成後才能執行。

```python
"""指令列入口：uv run lab <collect|check|build|closed|run|report>。"""
from __future__ import annotations

import argparse

from lab.common import FRAMEWORKS


def _model_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--model", default="haiku")
    p.add_argument("--effort", default="medium")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=int, default=180)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lab", description="比較資料整理方式對 Claude Code 檢索準確度的影響")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="下載官方文件到 world/")
    c.add_argument("--only", nargs="+", choices=FRAMEWORKS, help="只下載部分框架（試跑用 agent-sdk）")
    c.add_argument("--force", action="store_true", help="覆寫既有的 world/docs.json")

    sub.add_parser("check", help="檢查 world/questions.json 的題目")

    b = sub.add_parser("build", help="建立 A/B/C 三組實驗資料夾")
    b.add_argument("--model", default="sonnet", help="盲建索引用的模型")

    _model_args(sub.add_parser("closed", help="閉卷對照：不給文件，每題問一次"))

    r = sub.add_parser("run", help="跑評測（可以續跑）")
    r.add_argument("--rounds", type=int, required=True, help="跑到第幾輪為止；已經完成的會跳過")
    _model_args(r)

    p = sub.add_parser("report", help="產生統計表與網頁資料")
    p.add_argument("--model", default="haiku")
    p.add_argument("--effort", default="medium")

    args = parser.parse_args(argv)
    if args.cmd == "collect":
        from lab.collect import collect
        collect(only=args.only, force=args.force)
    elif args.cmd == "check":
        from lab.world import check
        check()
    elif args.cmd == "build":
        from lab.build import build
        build(model=args.model)
    elif args.cmd == "closed":
        from lab.run import run_closed
        run_closed(model=args.model, effort=args.effort, workers=args.workers, timeout=args.timeout)
    elif args.cmd == "run":
        from lab.run import run
        run(rounds=args.rounds, model=args.model, effort=args.effort, workers=args.workers,
            timeout=args.timeout)
    elif args.cmd == "report":
        from lab.report import report
        report(model=args.model, effort=args.effort)
```

- [ ] **Step 5：建立 `README.md`**

````markdown
# Retrieval Lab

比較三種資料整理方式（A 雜亂／B 整理／C 索引）對 Claude Code 檢索與回答準確度的影響。
文件使用官方原文：LangChain、LangGraph、Deep Agents、Claude Agent SDK。
設計見 `docs/superpowers/specs/2026-11-14-retrieval-lab-design.md`。

## 需求

- uv，以及已登入的 Claude Code（`claude` 指令可以用）
- 出題用 Codex，說明在 `docs/codex-questions.md`
- 實驗資料夾預設放在 `/Users/Shared/retrieval-lab-stage`。它必須在家目錄外，可以用環境變數 `LAB_STAGE` 換位置。

## 使用

```bash
uv sync
uv run lab collect --only agent-sdk   # 下載文件（正式版用 uv run lab collect --force）
codex exec --full-auto "請依照 docs/codex-questions.md 出題（試跑：10 題）"
uv run lab check                      # 檢查題目
uv run lab build                      # 盲建索引，建立 A/B/C 三組
uv run lab closed                     # 閉卷對照：每題問一次，不給文件
uv run lab run --rounds 1             # 跑評測，可以續跑
uv run lab report                     # 產生 results/report.md、results.csv、dashboard.json
uv run pytest                         # 執行測試
```

## 注意

- 每一輪的呼叫次數是「題數 × 3 組」，會消耗額度。
- `world/corpus/` 是官方文件的複本，只供個人學習，repo 不要公開推送。
- `runs/` 是原始紀錄，裡面有本機路徑，所以不進 git。
````

- [ ] **Step 6：安裝**

Run：`uv sync`
Expected：建立 `.venv` 和 `uv.lock`，沒有錯誤訊息。

- [ ] **Step 7：Commit**

```bash
git add pyproject.toml uv.lock .gitignore README.md src/lab/__init__.py src/lab/cli.py
git commit -m "chore: 建立 retrieval-lab 專案骨架"
```

---

### Task 2：共用模組 `common.py`

**Files:**
- Create：`src/lab/common.py`
- Test：`tests/test_common.py`

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

Run：`uv run pytest tests/test_common.py -v`
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
DOCS_JSON = WORLD / "docs.json"
QUESTIONS_JSON = WORLD / "questions.json"
CORPUS = WORLD / "corpus"
INDEX_CACHE = WORLD / "index_rows.json"
MAPPING = ROOT / "build" / "mapping.json"
RESULTS = ROOT / "results"
RESULTS_JSONL = RESULTS / "results.jsonl"
RUNS = ROOT / "runs"

CONDS = ["A-messy", "B-organized", "C-indexed"]
CLOSED = "Z-closed"
COND_LABELS = {"A-messy": "A 雜亂", "B-organized": "B 整理", "C-indexed": "C 索引", CLOSED: "閉卷"}
FRAMEWORKS = ["agent-sdk", "deepagents", "langchain", "langgraph"]
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


def load_world() -> dict:
    """回傳 {"docs": [...], "questions": [...]}；還沒出題時 questions 是空清單。"""
    docs = load_json(DOCS_JSON)["docs"]
    questions = load_json(QUESTIONS_JSON) if QUESTIONS_JSON.exists() else []
    return {"docs": docs, "questions": questions}


def load_bodies(world: dict) -> dict[str, str]:
    return {d["id"]: (CORPUS / f"{d['id']}.md").read_text(encoding="utf-8") for d in world["docs"]}


def world_id() -> str:
    """文件清單加上題目的指紋：換文件或換題目，就換一個 id，舊結果自動不納入統計。"""
    questions = QUESTIONS_JSON.read_text(encoding="utf-8") if QUESTIONS_JSON.exists() else ""
    return sha256(DOCS_JSON.read_text(encoding="utf-8") + questions)[:12]


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
    """一次性的結構化呼叫（盲建索引用）：不開任何工具，在家目錄外的暫存資料夾執行。"""
    with tempfile.TemporaryDirectory() as tmp:
        if is_under_home(Path(tmp)):
            raise RuntimeError(f"暫存資料夾在家目錄底下（{tmp}），請把 TMPDIR 設到家目錄外")
        proc = subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--output-format", "json", "--tools", "",
             "--json-schema", json.dumps(schema, ensure_ascii=False), *ISOLATION],
            cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p 失敗（exit {proc.returncode}）：{proc.stderr[-500:]}")
    out = json.loads(proc.stdout)
    if out.get("is_error") or not isinstance(out.get("structured_output"), dict):
        raise RuntimeError(f"claude -p 沒有回傳結構化結果：{str(out.get('result'))[:500]}")
    return out["structured_output"]
```

- [ ] **Step 4：確認測試通過，指令也能執行**

Run：`uv run pytest tests/test_common.py -v && uv run lab --help`
Expected：
- 3 passed
- 印出 `usage: lab [-h] {collect,check,build,closed,run,report} ...`

- [ ] **Step 5：Commit**

```bash
git add src/lab/common.py tests/test_common.py
git commit -m "feat: 共用設定、正規化、世界資料讀取與家目錄檢查"
```

---

### Task 3：解析 stream-json（`trace.py`）

**Files:**
- Create：`src/lab/trace.py`
- Test：`tests/test_trace.py`

- [ ] **Step 1：寫測試**

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


def test_isolation_expected_tools_for_closed_book():
    closed_init = ev(type="system", subtype="init", tools=["StructuredOutput"], mcp_servers=[], skills=[],
                     slash_commands=[])
    assert isolation_problems(parse_stream(closed_init), {"StructuredOutput"}) == []
    assert isolation_problems(parse_stream(closed_init)) != []   # 預設期待的是三個檢索工具
```

- [ ] **Step 2：確認測試失敗**

Run：`uv run pytest tests/test_trace.py -v`
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

Run：`uv run pytest tests/test_trace.py -v`
Expected：9 passed

- [ ] **Step 5：Commit**

```bash
git add src/lab/trace.py tests/test_trace.py
git commit -m "feat: 解析 stream-json，從工具紀錄判斷碰過哪些檔案"
```

---

### Task 4：評分（`score.py`）

**Files:**
- Create：`src/lab/score.py`
- Test：`tests/test_score.py`

- [ ] **Step 1：寫測試**

```python
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
```

- [ ] **Step 2：確認測試失敗**

Run：`uv run pytest tests/test_score.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.score'`

- [ ] **Step 3：實作 `src/lab/score.py`**

```python
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
    sources = set(row["sources"]) - NON_DOCS
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
```

- [ ] **Step 4：確認測試通過**

Run：`uv run pytest tests/test_score.py -v`
Expected：11 passed

- [ ] **Step 5：Commit**

```bash
git add src/lab/score.py tests/test_score.py
git commit -m "feat: 以程式比對評分（答對、幻覺、檢索命中、引用、閉卷）"
```

---

### Task 5：題目檢查（`world.py`）與 Codex 出題說明

**Files:**
- Create：`src/lab/world.py`、`docs/codex-questions.md`
- Test：`tests/test_world.py`

- [ ] **Step 1：寫測試**

```python
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
```

- [ ] **Step 2：確認測試失敗**

Run：`uv run pytest tests/test_world.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.world'`

- [ ] **Step 3：實作 `src/lab/world.py`**

```python
"""題目檢查：check_questions 是純函式，check() 是 lab check 指令。規則見設計第 4.4、4.6 節。"""
from __future__ import annotations

from collections import Counter

from lab.common import QTYPE_LABELS, QTYPES, load_bodies, load_world, norm

FIELDS = ["id", "type", "question", "must_include", "must_not_include", "gold_docs", "probe_terms", "answerable"]


def check_questions(world: dict, bodies: dict[str, str]) -> tuple[list[str], list[str]]:
    """回傳 (問題, 提醒)。有「問題」就不能開跑；「提醒」要在審題時看過。"""
    docs = {d["id"] for d in world["docs"]}
    normed = {doc_id: norm(body) for doc_id, body in bodies.items()}
    problems: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for q in world["questions"]:
        qid = str(q.get("id", "?"))
        if missing := [k for k in FIELDS if k not in q]:
            problems.append(f"{qid}：缺少欄位 {', '.join(missing)}")
            continue
        if qid in seen:
            problems.append(f"{qid}：id 重複")
        seen.add(qid)
        if q["type"] not in QTYPES:
            problems.append(f"{qid}：未知題型 {q['type']}")
            continue
        if q["answerable"] != (q["type"] != "unanswerable"):
            problems.append(f"{qid}：answerable 與題型不符")
        if unknown := [d for d in q["gold_docs"] if d not in docs]:
            problems.append(f"{qid}：找不到文件 {', '.join(unknown)}")
            continue
        tokens = [norm(t) for t in q["must_include"]]
        if q["type"] == "unanswerable":
            if q["gold_docs"] or q["must_include"]:
                problems.append(f"{qid}：題庫裡沒有的題目，gold_docs 和 must_include 要留空")
            if len(q["probe_terms"]) != 2:
                problems.append(f"{qid}：probe_terms 要剛好 2 個")
            else:
                entity, attr = (norm(t) for t in q["probe_terms"])
                both = [d for d, b in normed.items() if entity in b and attr in b]
                if both:
                    warnings.append(f"{qid}：「{q['probe_terms'][0]}」和「{q['probe_terms'][1]}」同時出現在 "
                                    f"{', '.join(both[:5])}，請確認這些文件真的沒有回答這題")
            continue
        if not tokens:
            problems.append(f"{qid}：缺少答案字串")
            continue
        if q["type"] == "multi_doc":
            if len(q["gold_docs"]) < 2:
                problems.append(f"{qid}：跨文件題至少要 2 份 gold 文件")
            for token, raw in zip(tokens, q["must_include"]):
                if not any(token in normed[d] for d in q["gold_docs"]):
                    problems.append(f"{qid}：答案「{raw}」不在任何 gold 文件裡")
            for d in q["gold_docs"]:
                if not any(token in normed[d] for token in tokens):
                    problems.append(f"{qid}：gold 文件 {d} 沒有任何答案字串")
            continue
        if not q["gold_docs"]:
            problems.append(f"{qid}：缺少 gold 文件")
            continue
        for d in q["gold_docs"]:
            if not all(token in normed[d] for token in tokens):
                problems.append(f"{qid}：gold 文件 {d} 沒有完整答案")
        extra = [d for d, b in normed.items() if d not in q["gold_docs"] and all(t in b for t in tokens)]
        if extra:
            problems.append(f"{qid}：完整答案也出現在 {', '.join(extra[:5])}，請加進 gold_docs 或換一個答案字串")
        if q["type"] == "version" and not q["must_not_include"]:
            problems.append(f"{qid}：新舊版本題要有 must_not_include（舊的寫法）")
    return problems, warnings


def check() -> None:
    """lab check：印出題目統計、提醒和問題；有問題時以非 0 結束。"""
    world = load_world()
    if not world["questions"]:
        raise SystemExit("world/questions.json 還沒有題目，請先依照 docs/codex-questions.md 出題")
    problems, warnings = check_questions(world, load_bodies(world))
    counts = Counter(q.get("type") for q in world["questions"])
    print(f"文件 {len(world['docs'])} 份，題目 {len(world['questions'])} 題："
          + "、".join(f"{QTYPE_LABELS.get(t, t)} {n}" for t, n in counts.items()))
    for w in warnings:
        print(f"  提醒：{w}")
    for p in problems:
        print(f"  問題：{p}")
    if problems:
        raise SystemExit(f"有 {len(problems)} 個問題要修正")
    print("沒有問題" + (f"（有 {len(warnings)} 個提醒，審題時請一併確認）" if warnings else ""))
```

- [ ] **Step 4：建立 `docs/codex-questions.md`**

````markdown
# 出題任務（給 Codex）

你要替一個「檢索評測」出題。之後會有另一個 AI 只靠這些文件回答你的題目，再由程式比對答案。

- 文件：`world/corpus/<id>.md`（英文官方文件）。清單和 id 在 `world/docs.json`。
- 輸出：把題目寫進 `world/questions.json`（JSON 陣列）。
- 檢查：執行 `.venv/bin/lab check`，一直修到沒有任何「問題」為止。

## 題數

- 試跑：10 題，每種題型 2 題。目前只有 agent-sdk 的文件。
- 正式：40 題，每種題型 8 題。agent-sdk、deepagents、langchain、langgraph 四個框架都要出到題，試跑的題目可以沿用。

## 每一題的格式

```json
{"id": "Q01", "type": "lookup", "question": "…", "must_include": ["…"], "must_not_include": [],
 "gold_docs": ["agent-sdk/hooks"], "probe_terms": [], "answerable": true}
```

## 共通規則

1. 題目用繁體中文，寫成台灣工程師平常會問的問題。可以保留必要的英文專有名詞（產品、類別、函式名稱），但不要整句照抄文件。
2. `must_include` 是程式判分用的答案字串，必須逐字出現在文件裡，而且要短而獨特，例如類別或函式名稱、參數名稱、預設值、版本號、指令。不要用 `True`、`None`、`100` 這種到處都有的字。
3. 優先問「要查文件才知道」的細節，例如參數名稱、預設值、限制、錯誤訊息、較新的功能。不要問一般常識，或任何人都知道的概念。
4. 每寫一題，就用 `grep -rlF "<答案字串>" world/corpus` 查它出現在哪些文件。

## 題型

| type | 怎麼出 | gold_docs |
|---|---|---|
| `lookup` | 題目直接點出要查的東西 | 完整答案出現的**所有**文件 |
| `paraphrase` | 刻意不提文件裡的關鍵英文詞，改用中文描述（例如不說 interrupt，而說「讓流程暫停、等人確認後再繼續」） | 同上 |
| `version` | 新舊 API 或設定的差異（遷移指南、deprecated 說明）。`must_include` 放現在該用的寫法，`must_not_include` 放舊寫法 | 同上 |
| `multi_doc` | 題目同時問兩件事，答案分別只在兩份不同的文件裡。`must_include` 每份文件各提供至少 1 個 | 這兩份文件 |
| `unanswerable` | 合理、但這些文件**完全沒有回答**的問題，出題前先 grep 確認。`gold_docs` 和 `must_include` 留空，`answerable` 設為 `false`，`probe_terms` 放 [實體, 屬性]，例如 `["Agent SDK", "Ruby"]` | 留空 |

其他欄位的規則：
- 除了 `unanswerable`，其他題型的 `answerable` 都是 `true`。
- `must_not_include` 只有 `version` 要填，其他留空。
- `probe_terms` 只有 `unanswerable` 要填，其他留空。

## 完成條件

`.venv/bin/lab check` 顯示「沒有問題」。「提醒」可以保留，但要在最後的回覆裡逐一說明為什麼可以接受。
````

- [ ] **Step 5：確認測試通過**

Run：`uv run pytest tests/test_world.py -v`
Expected：3 passed

- [ ] **Step 6：Commit**

```bash
git add src/lab/world.py tests/test_world.py docs/codex-questions.md
git commit -m "feat: 題目檢查與 Codex 出題說明"
```

---

### Task 6：下載官方文件（`collect.py`）

**Files:**
- Create：`src/lab/collect.py`
- Test：`tests/test_collect.py`

- [ ] **Step 1：寫測試**

```python
from lab.collect import DOC_INDEX_BANNER, SDK_LINK, title_of


def test_title_of():
    assert title_of("---\ntitle: Persistence\ndescription: x\n---\n# Other", "s") == "Persistence"
    assert title_of("# Agent SDK overview\n\ntext", "s") == "Agent SDK overview"
    assert title_of("沒有標題", "fallback") == "fallback"


def test_sdk_banner_and_links():
    body = "> ## Documentation Index\n> Fetch the index at: x\n> Use this file.\n\n# Hooks\n內容\n"
    assert DOC_INDEX_BANNER.sub("", body, count=1) == "# Hooks\n內容\n"
    index = ("- [Hooks](https://code.claude.com/docs/en/agent-sdk/hooks.md): x\n"
             "- [Headless](https://code.claude.com/docs/en/headless.md): y\n")
    assert SDK_LINK.findall(index) == ["https://code.claude.com/docs/en/agent-sdk/hooks.md"]
```

- [ ] **Step 2：確認測試失敗**

Run：`uv run pytest tests/test_collect.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.collect'`

- [ ] **Step 3：實作 `src/lab/collect.py`**

```python
"""下載官方文件：LangChain／LangGraph／Deep Agents（langchain-ai/docs repo）與 Claude Agent SDK（code.claude.com）。"""
from __future__ import annotations

import io
import re
import tarfile
import urllib.request
from datetime import date

from lab.common import CORPUS, DOCS_JSON, FRAMEWORKS, save_json, sha256

LC_TARBALL = "https://codeload.github.com/langchain-ai/docs/tar.gz/main"
LC_FRAMEWORKS = {"deepagents", "langchain", "langgraph"}
SDK_INDEX = "https://code.claude.com/docs/llms.txt"
SDK_LINK = re.compile(r"\((https://code\.claude\.com/docs/en/agent-sdk/[a-z0-9/-]+\.md)\)")
# Agent SDK 每頁開頭都有一段固定的「Documentation Index」引言，把它去掉
DOC_INDEX_BANNER = re.compile(r"\A(?:> .*\n)+\n?")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "retrieval-lab"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def title_of(body: str, fallback: str) -> str:
    """標題：優先用 frontmatter 的 title，其次用第一個 # 標題。"""
    fm = re.match(r"---\n(.*?)\n---", body, re.S)
    if fm and (m := re.search(r"^title:\s*(.+)$", fm.group(1), re.M)):
        return m.group(1).strip().strip("\"'")
    if m := re.search(r"^# (.+)$", body, re.M):
        return m.group(1).strip()
    return fallback


def langchain_pages(wanted: set[str]) -> list[tuple[str, str, str]]:
    """回傳 (框架, 頁面路徑, 內文)。"""
    pages = []
    with tarfile.open(fileobj=io.BytesIO(fetch(LC_TARBALL)), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")   # docs-main/src/oss/<框架>/.../<頁>.mdx
            if (member.isfile() and member.name.endswith(".mdx") and len(parts) > 4
                    and parts[1:3] == ["src", "oss"] and parts[3] in wanted):
                slug = "/".join(parts[4:])[: -len(".mdx")]
                pages.append((parts[3], slug, tar.extractfile(member).read().decode("utf-8")))
    return pages


def sdk_pages() -> list[tuple[str, str, str]]:
    urls = sorted(set(SDK_LINK.findall(fetch(SDK_INDEX).decode("utf-8"))))
    pages = []
    for url in urls:
        body = DOC_INDEX_BANNER.sub("", fetch(url).decode("utf-8"), count=1)
        pages.append(("agent-sdk", url.split("/agent-sdk/", 1)[1][: -len(".md")], body))
    return pages


def collect(only: list[str] | None = None, force: bool = False) -> None:
    if DOCS_JSON.exists() and not force:
        raise SystemExit("world/docs.json 已經存在。要重新下載請加 --force（舊結果會因 world_id 不同，自動不納入統計）")
    wanted = set(only or FRAMEWORKS)
    pages: list[tuple[str, str, str]] = []
    if wanted & LC_FRAMEWORKS:
        print("下載 langchain-ai/docs …")
        pages += langchain_pages(wanted & LC_FRAMEWORKS)
    if "agent-sdk" in wanted:
        print("下載 Claude Agent SDK 文件 …")
        pages += sdk_pages()
    pages.sort(key=lambda p: (p[0], p[1]))
    if CORPUS.exists():
        for old in CORPUS.rglob("*.md"):
            old.unlink()
    docs = []
    for category, slug, body in pages:
        doc_id = f"{category}/{slug}"
        body = body.strip() + "\n"
        path = CORPUS / f"{doc_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        docs.append({"id": doc_id, "title": title_of(body, slug), "category": category, "slug": slug,
                     "chars": len(body), "sha": sha256(body)})
    save_json(DOCS_JSON, {"collected_at": date.today().isoformat(), "docs": docs})
    counts = {f: sum(1 for d in docs if d["category"] == f) for f in sorted(wanted)}
    print(f"完成：{len(docs)} 頁（" + "、".join(f"{f} {n}" for f, n in counts.items()) + "）")
```

- [ ] **Step 4：確認測試通過**

Run：`uv run pytest tests/test_collect.py -v`
Expected：2 passed

- [ ] **Step 5：下載試跑用的文件（實際連網）**

Run：`uv run lab collect --only agent-sdk && head -c 400 world/corpus/agent-sdk/overview.md`
Expected：
- 印出 `完成：40 頁（agent-sdk 40）`。
- overview.md 第一行是 `# Agent SDK overview`，前面沒有 `> ## Documentation Index` 引言。

- [ ] **Step 6：Commit**

```bash
git add src/lab/collect.py tests/test_collect.py world/docs.json world/corpus
git commit -m "feat: 下載官方文件；收錄試跑用的 Agent SDK 文件（40 頁）"
```

---

### Task 7：三組實驗資料夾（`build.py`）

**Files:**
- Create：`src/lab/build.py`
- Test：`tests/test_build.py`

- [ ] **Step 1：寫測試**

```python
import json

import pytest

from lab.build import SETTINGS, digest, layout, render_index, stage_problems

DOCS = {"docs": [
    {"id": "langgraph/persistence", "title": "Persistence", "category": "langgraph", "slug": "persistence"},
    {"id": "agent-sdk/hooks", "title": "Hooks|SDK", "category": "agent-sdk", "slug": "hooks"},
    {"id": "langchain/frontend/overview", "title": "Frontend", "category": "langchain", "slug": "frontend/overview"},
]}


def test_layout():
    maps = layout(DOCS)
    assert sorted(maps["A-messy"].values()) == ["docs/doc_001.md", "docs/doc_002.md", "docs/doc_003.md"]
    assert maps["B-organized"]["langchain/frontend/overview"] == "docs/langchain/frontend/overview.md"
    assert maps["C-indexed"] == maps["B-organized"]
    assert layout(DOCS) == maps   # 固定種子，可以重現


def test_layout_rejects_duplicate_paths():
    dup = {"docs": DOCS["docs"] + [{"id": "x", "title": "x", "category": "langgraph", "slug": "persistence"}]}
    with pytest.raises(ValueError):
        layout(dup)


def test_render_index_escapes_pipes_and_sorts_by_path():
    paths = layout(DOCS)["C-indexed"]
    rows = {d["id"]: {"summary": "摘要|有直線", "keywords": ["checkpointer", "檢查點"]} for d in DOCS["docs"]}
    lines = render_index(DOCS, paths, rows).splitlines()
    assert lines[0] == "# 文件索引"
    assert [line.split(" | ")[0][2:] for line in lines[4:]] == sorted(paths.values())
    text = "\n".join(lines)
    assert "Hooks／SDK" in text and "摘要／有直線" in text and "checkpointer、檢查點" in text


def test_digest_keeps_headings_and_limits_length():
    body = "# Title\n" + "內容" * 3000 + "\n## Hooks\n### Timeout\n"
    text = digest(body, limit=3000)
    assert len(text) <= 3000 and "## Hooks" in text and "### Timeout" in text


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
    maps = layout(DOCS)
    bodies = {d["id"]: f"{d['id']}\n" for d in DOCS["docs"]}
    _write_stage(tmp_path, maps, bodies)
    clean = [p for p in stage_problems(tmp_path, maps, bodies) if "家目錄" not in p and "上層" not in p]
    assert clean == []
    (tmp_path / "A-messy" / maps["A-messy"]["agent-sdk/hooks"]).write_text("改過\n", encoding="utf-8")
    (tmp_path / "B-organized" / "CLAUDE.md").write_text("x")
    problems = stage_problems(tmp_path, maps, bodies)
    assert any("A-messy" in p and "內文" in p for p in problems)
    assert any("B-organized" in p and "CLAUDE.md" in p for p in problems)
```

- [ ] **Step 2：確認測試失敗**

Run：`uv run pytest tests/test_build.py -v`
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

from lab.common import (CONDS, INDEX_CACHE, MAPPING, claude_json, is_under_home, leaking_ancestors,
                        load_bodies, load_json, load_world, save_json, sha256, stage_root)

SETTINGS = {"permissions": {"deny": ["Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"]}}

CLAUDE_MD = """# 資料查找指引
- 先讀 INDEX.md，依關鍵字找出候選文件，再打開文件確認內容。
- 同一主題有多個版本時，以日期最新的為準。
"""

INDEX_PROMPT = """你是技術文件管理員。下面每一份文件只附上開頭和所有標題。請替每份文件寫一列索引：
- summary：一句繁體中文（40 字以內），說明這份文件在講什麼。
- keywords：8–12 個關鍵字，包含文件裡重要的英文名詞（類別、函式、參數、功能名稱），以及對應的繁體中文說法、同義詞和口語說法。
- path：原樣照抄文件標籤上的 path。
只根據提供的內容撰寫，不要編造。

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


def layout(world: dict, seed: int = 42) -> dict[str, dict[str, str]]:
    """每一組的 doc_id → 相對路徑。A 用固定種子打亂編號；B、C 用「框架/頁面路徑」。"""
    ids = [d["id"] for d in world["docs"]]
    shuffled = ids[:]
    random.Random(seed).shuffle(shuffled)
    messy = {doc_id: f"docs/doc_{i:03d}.md" for i, doc_id in enumerate(shuffled, 1)}
    organized = {d["id"]: f"docs/{d['category']}/{d['slug']}.md" for d in world["docs"]}
    if len(set(organized.values())) != len(organized):
        raise ValueError("B 組有重複的檔案路徑")
    return {"A-messy": messy, "B-organized": organized, "C-indexed": dict(organized)}


def _cell(text: str) -> str:
    return text.replace("|", "／").replace("\n", " ").strip()


def render_index(world: dict, paths: dict[str, str], rows: dict[str, dict]) -> str:
    lines = ["# 文件索引", "", "| 路徑 | 標題 | 摘要 | 關鍵字 |", "|---|---|---|---|"]
    for d in sorted(world["docs"], key=lambda d: paths[d["id"]]):
        r = rows[d["id"]]
        lines.append(f"| {paths[d['id']]} | {_cell(d['title'])} | {_cell(r['summary'])} | "
                     f"{_cell('、'.join(r['keywords']))} |")
    return "\n".join(lines) + "\n"


def digest(body: str, limit: int = 3000) -> str:
    """索引用的材料：開頭 1500 字元，加上所有標題行。整頁太長，不直接丟給模型。"""
    heads = [line for line in body.splitlines() if line.startswith("#")]
    return (body[:1500] + "\n…\n" + "\n".join(heads))[:limit]


def index_rows(world: dict, bodies: dict[str, str], paths: dict[str, str], model: str,
               batch: int = 10, workers: int = 4) -> dict[str, dict]:
    """盲建索引：每一批只給文件的開頭和標題，完全不給題目。結果快取在 world/index_rows.json。"""
    cache = load_json(INDEX_CACHE) if INDEX_CACHE.exists() else {}

    def stale(doc_id: str) -> bool:
        return cache.get(doc_id, {}).get("sha") != sha256(bodies[doc_id])

    todo = [d["id"] for d in world["docs"] if stale(d["id"])]
    lock = threading.Lock()

    def work(ids: list[str]) -> None:
        docs = "\n\n".join(f'<document path="{paths[i]}">\n{digest(bodies[i])}\n</document>' for i in ids)
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
    missing = [d["id"] for d in world["docs"] if stale(d["id"])]
    if missing:
        raise SystemExit(f"這些文件沒有索引，請重跑 lab build：{', '.join(missing)}")
    return cache


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
    world = load_world()
    bodies = load_bodies(world)
    root = stage_root()
    if is_under_home(root):
        raise SystemExit(f"stage 資料夾不能在家目錄底下：{root}（用 LAB_STAGE 換位置）")
    maps = layout(world)
    rows = index_rows(world, bodies, maps["C-indexed"], model)
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
    (root / "C-indexed" / "INDEX.md").write_text(render_index(world, maps["C-indexed"], rows), encoding="utf-8")
    save_json(MAPPING, maps)
    if problems := stage_problems(root, maps, bodies):
        raise SystemExit("建置後檢查失敗：\n" + "\n".join(f"- {p}" for p in problems))
    print(f"完成：{root}（{len(world['docs'])} 份文件 × 3 組）")
```

- [ ] **Step 4：確認測試通過**

Run：`uv run pytest tests/test_build.py -v`
Expected：5 passed

- [ ] **Step 5：Commit**

```bash
git add src/lab/build.py tests/test_build.py
git commit -m "feat: 建立三組實驗資料夾並盲建索引"
```

---

### Task 8：評測與閉卷對照（`run.py`）

**Files:**
- Create：`src/lab/run.py`
- Test：`tests/test_run.py`

- [ ] **Step 1：寫測試**

```python
import json

from lab.run import ANSWER_SCHEMA, ask_cmd, done_keys


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
```

- [ ] **Step 2：確認測試失敗**

Run：`uv run pytest tests/test_run.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.run'`

- [ ] **Step 3：實作 `src/lab/run.py`**

```python
"""評測：每題在每一組的資料夾裡執行一次 claude -p；閉卷組則在空資料夾、不開工具。結果附加到 results/results.jsonl。"""
from __future__ import annotations

import json
import random
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from functools import partial
from pathlib import Path

from lab.build import stage_problems
from lab.common import (CLOSED, CONDS, ISOLATION, MAPPING, RESULTS_JSONL, RUNS, is_under_home, leaking_ancestors,
                        load_bodies, load_json, load_world, read_rows, stage_root, world_id)
from lab.trace import isolation_problems, parse_stream, summarize
from lab.world import check_questions

PROMPT = """你是公司內部的資料查詢助理。請只根據目前資料夾裡的文件回答下面的問題，不要憑自己的知識。
如果文件中找不到答案，found 填 false，answer 說明找不到。
sources 列出你實際用來回答的文件路徑（相對於目前資料夾）。
數字請用阿拉伯數字。

問題：{question}"""

CLOSED_PROMPT = """請不要查任何資料，直接憑你自己的知識回答下面的問題。
如果你不知道或不確定，found 填 false，answer 說明不知道。
sources 留空。數字請用阿拉伯數字。

問題：{question}"""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"},
                   "sources": {"type": "array", "items": {"type": "string"}},
                   "found": {"type": "boolean"}},
    "required": ["answer", "sources", "found"],
}

PREFLIGHT_PROMPT = "這是連線檢查：不要使用任何工具，直接回答 answer=ok、sources 留空、found=false。"


def ask_cmd(prompt: str, model: str, effort: str, tools: str = "Read,Grep,Glob") -> list[str]:
    return ["claude", "-p", prompt, "--model", model, "--effort", effort, "--tools", tools,
            "--output-format", "stream-json", "--verbose", "--include-hook-events",
            "--json-schema", json.dumps(ANSWER_SCHEMA, ensure_ascii=False), *ISOLATION]


def done_keys(rows: list[dict], wid: str, model: str, effort: str) -> set[tuple[int, str, str]]:
    """已經成功跑完的 (round, cond, qid)，續跑時跳過。"""
    return {(r["round"], r["cond"], r["qid"]) for r in rows
            if r["world_id"] == wid and r["model"] == model and r["effort"] == effort and r["status"] == "ok"}


def _call(cmd: list[str], cwd: Path | str, timeout: int) -> tuple[str, str | None]:
    """執行一次 claude -p，回傳 (stdout, 錯誤訊息；沒有錯誤時是 None)。"""
    try:
        proc = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return out, f"逾時（{timeout} 秒）"
    return proc.stdout, (f"exit {proc.returncode}：{proc.stderr[-300:]}" if proc.returncode else None)


def _record(wid: str, model: str, effort: str, rnd: int, cond: str, qid: str, out: str, error: str | None,
            roots: list[str], known: set[str]) -> dict:
    """存下原始紀錄，並整理成 results.jsonl 的一列。"""
    raw = RUNS / wid / f"{model}-{effort}" / f"r{rnd}" / cond / f"{qid}.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(out, encoding="utf-8")
    row = summarize(parse_stream(out), roots, known)
    if error:
        row["status"], row["error"] = "error", error
    return {"world_id": wid, "model": model, "effort": effort, "round": rnd, "cond": cond, "qid": qid,
            "ts": datetime.now().isoformat(timespec="seconds"), **row}


def _execute(jobs: list, workers: int) -> None:
    """平行執行 jobs（每個都會回傳一列結果），邊完成邊寫入 results.jsonl。"""
    RESULTS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(job) for job in jobs]
        for i, fut in enumerate(as_completed(futures), 1):
            row = fut.result()
            with RESULTS_JSONL.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            mark = "✓" if row["status"] == "ok" else f"✗ {row['error']}"
            print(f"  [{i}/{len(jobs)}] {row['cond']} {row['qid']} {mark}")


def _questions() -> list[dict]:
    """取得題目；沒有題目，或沒通過 lab check，就停下來。"""
    world = load_world()
    if not world["questions"]:
        raise SystemExit("還沒有題目，請先依照 docs/codex-questions.md 出題")
    problems, _ = check_questions(world, load_bodies(world))
    if problems:
        raise SystemExit(f"題目還有 {len(problems)} 個問題，請先執行 uv run lab check")
    return world["questions"]


def preflight(maps: dict, model: str, effort: str) -> None:
    """開跑前檢查（設計第 6.3 節）：stage 狀態，以及每組一次檢查呼叫。"""
    root = stage_root()
    problems = stage_problems(root, maps, load_bodies(load_world()))
    for cond in CONDS:
        out, _ = _call(ask_cmd(PREFLIGHT_PROMPT, model, effort), root / cond, 180)
        problems += [f"{cond}：{p}" for p in isolation_problems(parse_stream(out))]
    if problems:
        raise SystemExit("開跑前檢查失敗：\n" + "\n".join(f"- {p}" for p in problems))
    print("開跑前檢查通過")


def ask_one(rnd: int, cond: str, q: dict, paths: dict[str, str], model: str, effort: str,
            timeout: int, wid: str) -> dict:
    cdir = stage_root() / cond
    out, error = _call(ask_cmd(PROMPT.format(question=q["question"]), model, effort), cdir, timeout)
    return _record(wid, model, effort, rnd, cond, q["id"], out, error,
                   [str(cdir), str(cdir.resolve())], set(paths.values()))


def run(rounds: int, model: str = "haiku", effort: str = "medium", workers: int = 4, timeout: int = 180) -> None:
    questions, maps, wid = _questions(), load_json(MAPPING), world_id()
    preflight(maps, model, effort)
    done = done_keys(read_rows(), wid, model, effort)
    for rnd in range(1, rounds + 1):
        tasks = [(cond, q) for cond in CONDS for q in questions if (rnd, cond, q["id"]) not in done]
        if not tasks:
            print(f"第 {rnd} 輪已經完成，跳過")
            continue
        random.Random(rnd).shuffle(tasks)
        print(f"第 {rnd} 輪：{len(tasks)} 次呼叫")
        _execute([partial(ask_one, rnd, cond, q, maps[cond], model, effort, timeout, wid) for cond, q in tasks],
                 workers)


def run_closed(model: str = "haiku", effort: str = "medium", workers: int = 4, timeout: int = 180) -> None:
    """閉卷對照：每題在空資料夾裡、不開工具問一次，找出憑記憶就答得出來的題目。"""
    questions, wid = _questions(), world_id()
    done = done_keys(read_rows(), wid, model, effort)
    todo = [q for q in questions if (1, CLOSED, q["id"]) not in done]
    if not todo:
        print("閉卷對照已經完成")
        return
    with tempfile.TemporaryDirectory() as tmp:
        if is_under_home(Path(tmp)) or leaking_ancestors(Path(tmp)):
            raise SystemExit(f"暫存資料夾不適合當閉卷環境：{tmp}")
        out, _ = _call(ask_cmd(PREFLIGHT_PROMPT, model, effort, tools=""), tmp, 180)
        if problems := isolation_problems(parse_stream(out), {"StructuredOutput"}):
            raise SystemExit("閉卷檢查失敗：\n" + "\n".join(f"- {p}" for p in problems))
        print(f"閉卷對照：{len(todo)} 題")

        def job(q: dict) -> dict:
            out, error = _call(ask_cmd(CLOSED_PROMPT.format(question=q["question"]), model, effort, tools=""),
                               tmp, timeout)
            return _record(wid, model, effort, 1, CLOSED, q["id"], out, error, [tmp], set())

        _execute([partial(job, q) for q in todo], workers)
```

- [ ] **Step 4：確認測試通過**

Run：`uv run pytest tests/test_run.py -v`
Expected：2 passed

- [ ] **Step 5：Commit**

```bash
git add src/lab/run.py tests/test_run.py
git commit -m "feat: 評測與閉卷對照（開跑前檢查、平行呼叫、可續跑）"
```

---

### Task 9：統計與網頁資料（`report.py`）

**Files:**
- Create：`src/lab/report.py`
- Test：`tests/test_report.py`

- [ ] **Step 1：寫測試**

```python
from lab.report import aggregate, memorized_qids


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


def test_memorized_qids():
    questions = {"Q1": {"type": "lookup", "answerable": True, "must_include": ["4200"]},
                 "Q2": {"type": "lookup", "answerable": True, "must_include": ["999"]},
                 "Q3": {"type": "unanswerable", "answerable": False, "must_include": []}}
    closed = [{"qid": "Q1", "answer": "4200", "found": True}, {"qid": "Q2", "answer": "不知道", "found": False},
              {"qid": "Q3", "answer": "不知道", "found": False}]
    assert memorized_qids(questions, closed) == {"Q1"}   # 不可回答題不算「憑記憶」
    assert memorized_qids(questions, []) is None
```

- [ ] **Step 2：確認測試失敗**

Run：`uv run pytest tests/test_report.py -v`
Expected：FAIL，`ModuleNotFoundError: No module named 'lab.report'`

- [ ] **Step 3：實作 `src/lab/report.py`**

```python
"""統計：results.jsonl → results/report.md、results.csv、dashboard.json。"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from statistics import mean

from lab.common import (CLOSED, COND_LABELS, CONDS, MAPPING, QTYPE_LABELS, QTYPES, RESULTS, load_json,
                        load_world, read_rows, save_json, stage_root, world_id)
from lab.score import answer_correct, score

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


def closed_rows_scored(rows: list[dict], questions: dict[str, dict]) -> list[dict]:
    return [{**r, "type": questions[r["qid"]]["type"], "correct": answer_correct(r, questions[r["qid"]]),
             "files_read_n": 0, "duration_s": (r["duration_ms"] or 0) / 1000} for r in rows]


def memorized_qids(questions: dict[str, dict], closed_rows: list[dict]) -> set[str] | None:
    """閉卷就答對的可回答題。還沒跑閉卷對照時回傳 None。"""
    if not closed_rows:
        return None
    return {r["qid"] for r in closed_rows
            if questions[r["qid"]]["answerable"] and answer_correct(r, questions[r["qid"]])}


def aggregate(rows: list[dict]) -> dict:
    """rows：已評分、status=ok 的列。回傳主表、題型表、逐題答對比例、多數決與成對比較。"""
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


def _summary_table(agg: dict, errors: dict[str, int]) -> list[str]:
    cols = METRICS + EFFICIENCY
    lines = ["| 組別 | " + " | ".join(label for _, label in cols) + " | 錯誤筆數 |",
             "|" + "---|" * (len(cols) + 2)]
    for cond in CONDS:
        s = agg["summary"][cond]
        cells = [f"{_pct(s[k]['mean'])}（{_pct(s[k]['min'])}–{_pct(s[k]['max'])}）" for k, _ in METRICS]
        cells += [_num(s[k]["mean"], 4 if k == "cost_usd" else 1) for k, _ in EFFICIENCY]
        lines.append(f"| {COND_LABELS[cond]} | " + " | ".join(cells) + f" | {errors.get(cond, 0)} |")
    return lines


def render_markdown(agg: dict, need: dict | None, memo: dict | None, model: str, effort: str,
                    errors: dict[str, int]) -> str:
    """memo：{"answerable": 可回答題數, "memorized": 閉卷答對題數}；還沒跑閉卷時是 None。"""
    lines = ["# Retrieval Lab 結果", "",
             f"- 模型：{model}（effort {effort}）",
             f"- 題數 n = {agg['n_questions']}，輪數 {len(agg['rounds'])}",
             f"- 產生時間：{datetime.now():%Y-%m-%d %H:%M}"]
    if memo is None:
        lines.append("- 閉卷對照：還沒執行（uv run lab closed）")
    else:
        lines.append(f"- 閉卷對照：{memo['answerable']} 題可回答題中，有 {memo['memorized']} 題不給文件也答對")
    lines += ["", "## 總表：全部題目（各輪平均，括號內為各輪最低–最高）", "", *_summary_table(agg, errors)]
    if need is not None:
        lines += ["", f"## 總表：需要查文件的題目（排除憑記憶答對的題目，n = {need['n_questions']}）", "",
                  *_summary_table(need, errors)]
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


def dashboard(agg: dict, need: dict | None, memorized: set[str] | None, rows: list[dict], closed: list[dict],
              world: dict, maps: dict, model: str, effort: str) -> dict:
    closed_by_q = {r["qid"]: r for r in closed}
    questions = []
    for q in world["questions"]:
        results = {cond: [{"round": r["round"], "answer": _clean(r["answer"]), "found": r["found"],
                           "correct": r["correct"], "retrieved": r["retrieved"],
                           "index_used": r.get("index_used"), "files_read": r["files_read"],
                           "files_grep": r["files_grep_content"], "tool_calls": r["tool_calls"],
                           "duration_s": round(r["duration_s"], 1)}
                          for r in sorted(rows, key=lambda r: r["round"])
                          if r["qid"] == q["id"] and r["cond"] == cond]
                   for cond in CONDS}
        c = closed_by_q.get(q["id"])
        questions.append({"id": q["id"], "type": q["type"], "question": q["question"],
                          "gold_answer": "、".join(q["must_include"]) or "（文件中沒有，應該回答找不到）",
                          "gold_files": {cond: [maps[cond][d] for d in q["gold_docs"]] for cond in CONDS},
                          "memorized": memorized is not None and q["id"] in memorized,
                          "closed": None if c is None else {"answer": _clean(c["answer"]), "found": c["found"],
                                                            "correct": c["correct"]},
                          "results": results})
    return {"generated_at": datetime.now().isoformat(timespec="minutes"), "model": model, "effort": effort,
            "claude_versions": sorted({r["claude_version"] for r in rows if r.get("claude_version")}),
            "n_questions": agg["n_questions"], "rounds": agg["rounds"],
            "memorized_count": None if memorized is None else len(memorized),
            "conds": [{"id": c, "label": COND_LABELS[c]} for c in CONDS],
            "qtypes": [{"id": t, "label": QTYPE_LABELS[t]} for t in QTYPES],
            "summary": agg["summary"], "summary_need_docs": need["summary"] if need else None,
            "n_need_docs": need["n_questions"] if need else None,
            "by_type": agg["by_type"], "paired": agg["paired"], "questions": questions}


def report(model: str = "haiku", effort: str = "medium") -> None:
    world, maps, wid = load_world(), load_json(MAPPING), world_id()
    questions = {q["id"]: q for q in world["questions"]}
    rows = [r for r in read_rows() if r["world_id"] == wid and r["model"] == model and r["effort"] == effort]
    main = [r for r in rows if r["cond"] in CONDS]
    ok = [r for r in main if r["status"] == "ok"]
    if not ok:
        raise SystemExit("還沒有可用的結果，請先執行 lab run")
    ok_keys = {(r["round"], r["cond"], r["qid"]) for r in ok}
    errors = {c: len({(r["round"], r["qid"]) for r in main if r["cond"] == c and r["status"] != "ok"
                      and (r["round"], r["cond"], r["qid"]) not in ok_keys}) for c in CONDS}
    closed = closed_rows_scored([r for r in rows if r["cond"] == CLOSED and r["status"] == "ok"], questions)
    memorized = memorized_qids(questions, closed)
    scored = scored_rows(ok, questions, maps)
    agg = aggregate(scored)
    need = None if memorized is None else aggregate([r for r in scored if r["qid"] not in memorized])
    memo = None if memorized is None else {"answerable": sum(1 for q in questions.values() if q["answerable"]),
                                           "memorized": len(memorized)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    text = render_markdown(agg, need, memo, model, effort, errors)
    (RESULTS / "report.md").write_text(text, encoding="utf-8")
    write_csv(RESULTS / "results.csv", scored + closed)
    save_json(RESULTS / "dashboard.json", dashboard(agg, need, memorized, scored, closed, world, maps, model, effort))
    print(text)
```

- [ ] **Step 4：確認全部測試通過**

Run：`uv run pytest -v`
Expected：38 passed（common 3、trace 9、score 11、world 3、collect 2、build 5、run 2、report 3）

- [ ] **Step 5：Commit**

```bash
git add src/lab/report.py tests/test_report.py
git commit -m "feat: 統計報表、閉卷子集、CSV 與網頁資料"
```

---

### Task 10：試跑——Codex 出題與審題

- [ ] **Step 1：停下來，請使用者決定由誰執行 Codex**

Codex 會使用使用者的 OpenAI 帳號額度，所以要先問使用者：
- 自己執行 Codex，或
- 授權 Claude 執行以下指令：

```bash
codex exec --full-auto "請依照 docs/codex-questions.md 出題。這次是試跑：出 10 題，每種題型 2 題。"
```

- [ ] **Step 2：檢查題目**

Run：`uv run lab check`
Expected：第一行是 `文件 40 份，題目 10 題：…`，最後一行是 `沒有問題`，或 `沒有問題（有 N 個提醒…）`。
如果有「問題」，就把輸出交回給 Codex 修正，修完重新檢查。

- [ ] **Step 3：列出題目**

Run:
```bash
jq -r '.[] | "\(.id)｜\(.type)｜\(.question)｜答案：\(.must_include | join("、"))｜舊寫法：\(.must_not_include | join("、"))｜gold：\(.gold_docs | join(", "))｜探測：\(.probe_terms | join("＋"))"' world/questions.json
```

- [ ] **Step 4：停下來，請使用者審題**

把題目清單和 `lab check` 印出的所有提醒交給使用者，請他確認題目是否合理、答案是否明確。使用者同意後才繼續。

- [ ] **Step 5：Commit**

```bash
git add world/questions.json
git commit -m "data: 試跑題目（Codex 出題，10 題）"
```

---

### Task 11：試跑——建置、閉卷、評測、校正

- [ ] **Step 1：建置三組**

Run：`uv run lab build`
Expected：`完成：/Users/Shared/retrieval-lab-stage（40 份文件 × 3 組）`

- [ ] **Step 2：抽查 stage 內容**

Run:
```bash
find /Users/Shared/retrieval-lab-stage -path '*/docs/*' -name '*.md' | wc -l
head -8 /Users/Shared/retrieval-lab-stage/C-indexed/INDEX.md
```
Expected：
- 第一個指令輸出 `120`。
- INDEX.md 的關鍵字欄位同時有英文名詞和繁中說法。

- [ ] **Step 3：Commit 建置產物**

```bash
git add build/mapping.json world/index_rows.json
git commit -m "data: 試跑的檔案對照表與盲建索引"
```

- [ ] **Step 4：閉卷對照**

Run：`uv run lab closed`
Expected：`閉卷對照：10 題`，接著是 10 行 `✓`。

- [ ] **Step 5：跑 1 輪並產生報表**

Run：`uv run lab run --rounds 1 && uv run lab report`
Expected：
- 先出現 `開跑前檢查通過`，接著是 30 行 `✓`。
- 報表包含：閉卷對照那一行、兩張總表、題型表、成對比較。
- 如果有 `✗`，重跑同一個指令會只補跑失敗的部分。

- [ ] **Step 6：人工抽查評分**

Run:
```bash
jq -r '.questions[] | .question as $q | .gold_answer as $g | .memorized as $m | .results | to_entries[] | .key as $c | .value[] | "\($c)｜\($q)｜標準：\($g)｜回答：\(.answer)｜判定：\(.correct)｜憑記憶：\($m)"' results/dashboard.json | head -30
```
逐筆看至少 10 筆，確認判定跟人的判斷一致。

如果發現判錯，先在 `tests/test_score.py` 加一個會失敗的測試把它重現，再修改 `score.py` 或 `common.norm`，最後重新執行 `uv run lab report`。

接著列出 C 組「答對、但沒碰 gold 文件」的紀錄：

```bash
jq -r '.questions[] | .id as $id | .results["C-indexed"][] | select(.correct and .retrieved == false) | "\($id) 第 \(.round) 輪：答對但沒碰 gold 文件（讀了索引：\(.index_used)）"' results/dashboard.json
```

- [ ] **Step 7：校正用量**

Run:
```bash
uv run python -c "
import csv
rows = [r for r in csv.DictReader(open('results/results.csv', encoding='utf-8-sig')) if r['cond'] != 'Z-closed']
n = len(rows)
print('評測呼叫', n, '平均花費 USD', round(sum(float(r['cost_usd'] or 0) for r in rows) / n, 4),
      '平均秒數', round(sum(float(r['duration_s']) for r in rows) / n, 1))
"
```
用實測數字更新設計第 12 節：寫入每次呼叫的平均花費和秒數，以及正式版的預估值。

- [ ] **Step 8：停下來，向使用者回報試跑結果**

回報內容：
- 總表兩張、題型表。
- 閉卷的結果。
- 抽查結果，以及 C 組「答對但沒碰 gold」的筆數。
- 實際用量，以及正式版預估要花的時間和費用。

試跑只用來驗證流程和評分，不用來判斷難度。使用者同意後才進入正式版。

- [ ] **Step 9：Commit**

```bash
git add results docs/superpowers/specs/2026-11-14-retrieval-lab-design.md
git commit -m "data: 試跑結果與用量校正"
```

---

### Task 12：正式版

- [ ] **Step 1：下載全部文件**

Run：`uv run lab collect --force`
Expected：`完成：221 頁（agent-sdk 40、deepagents 58、langchain 79、langgraph 44）`
頁數可能因為官方更新而略有不同；如果有不同，照實記錄。

- [ ] **Step 2：Codex 出 40 題**

同 Task 10 Step 1，指令改成：

```bash
codex exec --full-auto "請依照 docs/codex-questions.md 出題。這次是正式版：40 題，每種題型 8 題，四個框架都要有，試跑的題目可以沿用。"
```

接著執行 `uv run lab check`，修到沒有問題為止。

- [ ] **Step 3：停下來，請使用者審題**

用 Task 10 Step 3 的指令列出題目，連同所有提醒一起交給使用者。使用者同意後才繼續。

- [ ] **Step 4：建置並 commit**

Run：`uv run lab build`
Expected：`完成：/Users/Shared/retrieval-lab-stage（221 份文件 × 3 組）`

```bash
git add world build/mapping.json
git commit -m "data: 正式版文件（221 頁）、題目（40 題）與盲建索引"
```

- [ ] **Step 5：閉卷對照，並跑第 1 輪**

共 40 + 120 次呼叫。

Run：`uv run lab closed && uv run lab run --rounds 1 && uv run lab report`

- [ ] **Step 6：停下來，用第 1 輪判斷難度**

回報給使用者：
- 兩張總表、題型表、閉卷結果。
- C 組「答對但沒碰 gold」的筆數（用 Task 11 Step 6 的指令）。

如果多數題型三組都是 100% 或都是 0%，就提出**三組一視同仁**的調整，例如請 Codex 改題，然後回到 Step 2。舊結果會因為 world_id 不同，自動不納入統計。

使用者同意維持現狀後才繼續。

- [ ] **Step 7：補跑第 2、3 輪，產生報表並 commit**

共 240 次呼叫。

Run：`uv run lab run --rounds 3 && uv run lab report`
Expected：第 1 輪顯示「已經完成，跳過」，接著跑第 2、3 輪。

```bash
git add results
git commit -m "data: 正式版 3 輪評測結果"
```

---

### Task 13：互動網頁

這一步是在 Claude Code session 裡用 Artifact 工具完成，不是 Python 程式。

- [ ] **Step 1：隱私檢查**

Run：`grep -cE '/Users/|/private/' results/dashboard.json`
Expected：`0`

- [ ] **Step 2：建立網頁**

1. 呼叫 Artifact `quickstart`，intent 用 `other`（呈現資料的儀表板）。
2. 結果如果指示使用 Dashboard 型別，就照它的說明建立；否則手寫 HTML，並先載入 `artifact-design` 和 `dataviz` 技能。
3. 資料一律來自 `results/dashboard.json`。

頁面內容（依設計第 9 節）：

| 區塊 | 內容 |
|---|---|
| 總覽 | 三組的答對率、檢索命中率、幻覺率長條圖。誤差用 min–max 呈現，可切換「全部題目」（`summary`）和「需要查文件的題目」（`summary_need_docs`）。另外顯示效率數字和 C 組讀了索引的比例 |
| 閉卷 | `memorized_count` / 可回答題數，說明這些題目為什麼要另外看 |
| 題型 × 組別熱度表 | `by_type` |
| 成對比較 | `paired`，標出 n |
| 逐題展開 | 可以依題型篩選。每題顯示題目、標準答案、是否憑記憶可答、閉卷回答、三組各輪的回答、讀過的檔案、對錯 |
| 頁尾 | 模型、effort、輪數、題數、Claude Code 版本、產生時間、文件來源與下載日期 |

- [ ] **Step 3：發布並回報**

把連結給使用者，並提醒兩件事：
- 頁面要從 Share 選單分享，同學才看得到。
- 之後重新執行 `uv run lab report` 時，再請 Claude 重新發布即可，連結不變。
