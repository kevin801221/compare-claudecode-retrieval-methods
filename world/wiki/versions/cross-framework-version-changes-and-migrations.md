# Cross-Framework Version Changes, Deprecations, and Discrepancies

別名：跨框架版本變更與棄用及差異總覽、版本差異與矛盾、Deprecated APIs、Migration Summary、v0.1.0 與 v1.0 變更
框架：agent-sdk、deepagents、langchain、langgraph

## 摘要
本頁彙整 `docs/` 四大框架文件中記載的所有重大版本遷移（Migration）、破壞性變更（Breaking Changes）、已棄用（Deprecated / Removed）API、預覽版功能（V2 Preview），以及不同文件或跨語言（Python vs TypeScript/JavaScript）之間的版本差異與名稱矛盾。

## 重點

### 1. Claude Agent SDK：品牌更名、v0.1.0 破壞性變更與工具更名
- **套件與類別更名（Claude Code SDK → Claude Agent SDK）**（出處：`docs/agent-sdk/migration-guide.md`）：
  - TypeScript 套件：`@anthropic-ai/claude-code` → `@anthropic-ai/claude-agent-sdk`。
  - Python 套件：`claude-code-sdk` → `claude-agent-sdk`（模組匯入：`from claude_code_sdk import ...` → `from claude_agent_sdk import ...`）。
  - Python 選項類別：`ClaudeCodeOptions` → `ClaudeAgentOptions`。
- **v0.1.0 兩大預設行為破壞性變更（Breaking Changes）**（出處：`docs/agent-sdk/migration-guide.md`）：
  1. **`systemPrompt` / `system_prompt` 預設改為空**：舊版預設使用 Claude Code 系統提示詞；v0.1.0 起預設為空（最小化系統提示詞）。若需舊版行為，必須顯式設定 `system_prompt={"type": "preset", "preset": "claude_code"}`（TS：`systemPrompt: { type: "preset", preset: "claude_code" }`）。
  2. **`settingSources` / `setting_sources` 預設改為空陣列 `[]`**：舊版自動載入 `~/.claude/settings.json`、`.claude/settings.json` 與 `CLAUDE.md`；v0.1.0 起預設不讀取任何檔案系統設定。若需載入必須顯式傳入 `setting_sources=["user", "project", "local"]`。
- **內建工具更名與 Python vs TypeScript 差異**（出處：`docs/agent-sdk/python.md`、`docs/agent-sdk/typescript.md`、`docs/agent-sdk/subagents.md`）：
  - **`Task` → `Agent`**：Claude Code CLI `v2.1.63` 將子代理工具由 `Task` 更名為 `Agent`；目前為向後相容，`Task` 仍保留於 `LEGACY_TOOL_NAME_ALIASES` 中作為有效別名。
  - **`BashOutput` / `TaskOutput` 的跨文件與跨語言差異**：
    - 在 `docs/agent-sdk/typescript.md` 中，`TaskOutput`（舊別名 `BashOutput`）仍列為內建工具（對應 `TaskOutputInput` / `TaskOutput`）。
    - 在 `docs/agent-sdk/python.md` 中明確記載：`TaskOutput`（及 `BashOutput`）**已移除（Removed）**，改由 `Monitor` 工具串流背景事件，或直接讀取背景任務輸出的檔案路徑。
  - **`KillBash` / `KillShell` → `TaskStop`**：停止背景任務的工具統一更名為 `TaskStop`（`KillBash` 與 `KillShell` 為相容舊稱）。
- **Python 與 TypeScript Hook 事件支援差異**（出處：`docs/agent-sdk/hooks.md`、`docs/agent-sdk/python.md`、`docs/agent-sdk/typescript.md`）：
  - `docs/agent-sdk/hooks.md` 概念頁列出兩語言支援對照表時，標註 `SessionStart` 與 `SessionEnd` 僅 TypeScript 支援；但在 `docs/agent-sdk/python.md` 的 `HookEvent` 型別定義中，`Literal` 實際包含了 `"SessionStart"` 與 `"SessionEnd"`（共 12 個事件），且定義了 `SessionStartHookSpecificOutput`。
  - TypeScript 的 `HookEvent` 則定義了 21 個事件（比 Python 多出 `Setup`、`TeammateIdle`、`TaskCompleted`、`Elicitation`、`ElicitationResult`、`ConfigChange`、`WorktreeCreate`、`WorktreeRemove`、`InstructionsLoaded` 共 9 個事件）。
- **TypeScript SDK V2 Preview（不穩定預覽 API）**（出處：`docs/agent-sdk/typescript-v2-preview.md`）：
  - 新增 `unstable_v2_createSession()`、`unstable_v2_resumeSession()`、`unstable_v2_prompt()`，以 `session.send()` 與 `session.stream()` 取代 V1 的 `AsyncGenerator` 輸入串流，但目前 `SDKSessionOptions` 僅支援部分選項且尚未支援 `forkSession` 與檔案檢查點 API。

### 2. LangChain 與 LangGraph v1.0：架構重整、棄用與環境需求
- **`create_react_agent` 遷移至 `create_agent` / `createAgent`**（出處：`docs/langgraph/backward-compatibility.md`、`docs/langchain/agents.md`）：
  - LangGraph 過去在 `langgraph.prebuilt`（JS：`@langchain/langgraph/prebuilt`）提供的 `create_react_agent` 已被 LangChain v1 的 `langchain.agents.create_agent`（JS：`"langchain"` 的 `createAgent`）取代，新增了完整的 `AgentMiddleware` 管線、標準化 `response_format`（`ProviderStrategy` / `ToolStrategy`）與 `Runtime` 上下文。
  - `langgraph.prebuilt` 中的 `ToolNode`、`tools_condition`、`InjectedState`、`InjectedStore` 仍維持向後相容支援。
- **Streaming `version="v2"` 統一輸出格式**（出處：`docs/langchain/streaming.md`、`docs/langgraph/streaming.md`）：
  - Python `graph.stream(..., version="v2")` 引入統一的 `StreamPart` 字典格式（固定包含 `type`、`ns`、`data` 三個鍵），取代舊版依 `stream_mode` 是否為列表與是否開啟 `subgraphs=True` 而變動長度的 tuple 回傳格式；呼叫 `invoke(..., version="v2")` 則回傳 `GraphOutput` 物件（包含 `.value` 與 `.interrupts`）。
- **執行環境版本限制**：
  - **LangChain / LangGraph JS v1.0**：要求 **Node.js 20+**（不再支援已 EOL 的 Node.js 18）。
  - **LangGraph Python 非同步串流**：在 **Python < 3.11** 環境中，由於 `asyncio` 尚未支援自動傳遞 `contextvars`，在節點內呼叫非同步 LLM 或工具時必須**顯式傳入 `config`**（例如 `await llm.ainvoke(messages, config)`），否則 `astream_events` 與 `stream_mode="messages"` 無法捕捉事件；Python 3.11+ 則自動傳遞。

### 3. Deep Agents 版本特性與套件結構
- **`RubricMiddleware` 版本需求**（出處：`docs/deepagents/rubric.md`）：要求 `deepagents>=0.6.5`（Python 與 JavaScript 皆同）。
- **可選擴充套件（Extras）**：
  - QuickJS 程式碼直譯器（`CodeInterpreterMiddleware`）需安裝 `deepagents[interpreter]`（Python）或 `@langchain/deepagents` 搭配 `quickjs-emscripten`（JS）。
  - 遠端沙盒與 CLI 擴充透過 `deepagents` CLI 的 `--with` 或各沙盒套件（`langchain-modal`、`langchain-daytona`、`langchain-runloop`、`langchain-e2b`、`langsmith`）安裝。

## 相關頁面
- [[versions/agent-sdk-migration-and-v2-preview]]
- [[versions/langgraph-backward-compatibility-and-changelogs]]
- [[comparisons/agent-sdk-python-vs-typescript]]
- [[concepts/langchain-overview-and-architecture]]
- [[concepts/langgraph-streaming]]

## 出處
- docs/agent-sdk/migration-guide.md
- docs/agent-sdk/typescript-v2-preview.md
- docs/agent-sdk/hooks.md
- docs/agent-sdk/subagents.md
- docs/agent-sdk/python.md
- docs/agent-sdk/typescript.md
- docs/langchain/overview.md
- docs/langchain/agents.md
- docs/langchain/streaming.md
- docs/langgraph/backward-compatibility.md
- docs/langgraph/streaming.md
- docs/langgraph/event-streaming.md
- docs/deepagents/rubric.md
- docs/deepagents/interpreters.md
