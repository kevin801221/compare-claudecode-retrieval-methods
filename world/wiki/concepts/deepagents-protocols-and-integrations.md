# Deep Agents Protocols and Integrations: ACP, AG-UI, A2A, and Changelogs

別名：Agent Client Protocol、ACP、deepagents-acp、Agent User Interaction Protocol、AG-UI、@ag-ui/langgraph、Agent2Agent、A2A、協定與整合、Changelogs
框架：deepagents

## 摘要
本頁說明 Deep Agents 與外部系統通訊的標準協定與發行紀錄：**ACP（Agent Client Protocol）** 透過 `deepagents-acp` 套件以 stdio 模式將代理連接至程式碼編輯器與 IDE（如 Zed、JetBrains IDEs、VS Code、Neovim 與 Toad）；**AG-UI（Agent User Interaction Protocol）** 透過 `@ag-ui/langgraph` 的 `LangGraphAgent` 將 LangGraph 伺服器上的代理轉換為型別化事件串流以驅動前端介面；**A2A（Agent2Agent）** 提供跨代理間的通訊整合；並收錄 Python 與 JavaScript SDK 的官方 Changelog 參照。

## 重點

### 1. Deep Agents 四大協定分工對照
- **AG-UI（Agent User Interaction Protocol）**：連接代理後端（agentic backend）與面向使用者的前端應用程式（user-facing frontend）。
- **ACP（Agent Client Protocol）**：連接編碼代理（coding agents）與程式碼編輯器及 IDEs（如 Zed、JetBrains）。
- **MCP（Model Context Protocol）**：讓 Deep Agent 呼叫由外部伺服器託管的工具（tools）。
- **A2A（Agent2Agent）**：連接 Deep Agent 與其他代理（`docs/deepagents/a2a.md` 定義 `title: A2A server`、`sidebarTitle: A2A with LangSmith`，對應路徑為 `url: "/langsmith/server-a2a"`）。

### 2. Agent Client Protocol (`ACP` / `deepagents-acp`)
- **運作機制與安裝**：
  - 以 `stdio` 模式啟動 ACP 伺服器（從 `stdin` 讀取請求，向 `stdout` 寫入回應），通常由編輯器等 ACP 客戶端作為子程序啟動。
  - 安裝指令：Python 使用 `pip install deepagents-acp` 或 `uv add deepagents-acp`（內附包含檔案系統與 shell 的範例編碼代理 `libs/acp/examples/demo_agent.py`）；JavaScript/TypeScript 使用 `npm install deepagents-acp`（或 `yarn add` / `pnpm add`），亦可直接免寫程式執行 CLI `npx deepagents-acp`。
  - **ACP Agent Registry**：Deep Agents 已上架至 ACP Agent Registry，支援在 Zed 與 JetBrains IDEs 中一鍵探索與安裝。
- **編輯器與客戶端整合（Clients）**：
  - 支援客戶端包含 **Zed**、**JetBrains IDEs**、**Visual Studio Code**（透過 `vscode-acp` 擴充套件）、**Neovim**（透過相容 ACP 的外掛）以及本機開發工具 **Toad**。
  - **Zed 設定方式**：
    - **Python**：Clone `deepagents` 儲存庫後進入 `deepagents/libs/acp`，執行 `uv sync --all-groups` 與 `chmod +x run_demo_agent.sh`，在 `.env` 設定 `ANTHROPIC_API_KEY`，並於 Zed 的 `settings.json` 加入 `"agent_servers": { "DeepAgents": { "type": "custom", "command": "/your/absolute/path/to/deepagents/libs/acp/run_demo_agent.sh" } }`。
    - **JavaScript / TypeScript**：在 Zed 設定檔（Linux 為 `~/.config/zed/settings.json`，macOS 為 `~/Library/Application Support/Zed/settings.json`）設定 `agent.profiles`，將 `"command"` 設為 `"npx"`，`"args"` 設為 `["deepagents-acp"]`（可附加 `"--name"`, `"my-assistant"`, `"--skills"`, `"./skills"`, `"--debug"`），或指向自訂 TS 腳本 `"args": ["tsx", "./server.ts"]`，並在 `"env"` 中傳入 `"ANTHROPIC_API_KEY"`。
  - **Toad（Python 本機開發管理）**：執行 `uv tool install -U batrachian-toad`，接著以 `toad acp "python path/to/your_server.py" .` 或 `toad acp "uv run python path/to/your_server.py" .` 啟動。
- **CLI 參數與環境變數參考（`npx deepagents-acp [options]`）**：
  - `--name <name>`（簡寫 `-n`）：代理名稱（預設：`"deepagents"`）。
  - `--description <desc>`（簡寫 `-d`）：代理描述。
  - `--model <model>`（簡寫 `-m`）：LLM 模型（預設：`"claude-sonnet-4-5-20250929"`）。
  - `--workspace <path>`（簡寫 `-w`）：工作區根目錄（預設：`cwd`）。
  - `--skills <paths>`（簡寫 `-s`）：以逗號分隔的技能路徑。
  - `--memory <paths>`：以逗號分隔的 `AGENTS.md` 路徑。
  - `--debug`：啟用輸出至 `stderr` 的除錯日誌。
  - `--help`（`-h`）、`--version`（`-v`）。
  - **環境變數**：`ANTHROPIC_API_KEY`（Anthropic/Claude 模型必填）、`OPENAI_API_KEY`（OpenAI 模型金鑰）、`DEBUG`（設為 `"true"` 啟用除錯日誌）、`WORKSPACE_ROOT`（`--workspace` 旗標的替代方案）。
- **TypeScript 程式化 API（`startServer` 與 `DeepAgentsServer`）**：
  - **伺服器選項（Server options）**：
    - `agents`（型別 `DeepAgentConfig | DeepAgentConfig[]`，必填）：單一或多個代理配置（注意：如 Zed 等部分客戶端目前無切換多代理的 UI，此時建議為每個代理啟動獨立伺服器實例）。
    - `serverName`（型別 `string`，預設 `"deepagents-acp"`）：ACP 伺服器名稱。
    - `serverVersion`（型別 `string`，預設 `"0.0.1"`）：伺服器版本。
    - `workspaceRoot`（型別 `string`，預設 `process.cwd()`）：工作區根目錄。
    - `debug`（型別 `boolean`，預設 `false`）：啟用除錯日誌。
  - **代理配置（`DeepAgentConfig`）**：
    - `name`（`string`，必填）：唯一代理名稱。
    - `description`（`string`）：代理描述。
    - `model`（`string`，預設 `"claude-sonnet-4-5-20250929"`）：LLM 模型。
    - `tools`（`StructuredTool[]`）：自訂 LangChain 工具。
    - `systemPrompt`（`string`）：自訂系統提示詞。
    - `middleware`（`AgentMiddleware[]`）：附加至 Deep Agents 堆疊的自訂 middleware。
    - `backend`（`AnyBackendProtocol`）：檔案系統 backend。
    - `skills`（`string[]`）：技能來源路徑（如 `["./skills/", "~/.deepagents/skills/"]`）。
    - `memory`（`string[]`）：記憶來源路徑（如 `["./.deepagents/AGENTS.md"]`）。
    - `interruptOn`（`Record<string, boolean | InterruptOnConfig>`）：執行前需在 IDE 內經過使用者允許或拒絕（支援記憶該 session 決定）的敏感工具（HITL）。
    - `commands`（`Array<{ name, description, input? }>`）：自訂斜線指令。伺服器預設會向 IDE 註冊 5 個內建斜線指令：`/plan`、`/agent`、`/ask`、`/clear` 與 `/status`。

### 3. Agent User Interaction Protocol (`AG-UI` / `@ag-ui/langgraph`)
- **架構與啟動流程**：
  - 將透過 `create_deep_agent`（Python）或 `createDeepAgent`（TS）建立的代理註冊於專案根目錄的 `langgraph.json`（例如設定 graph ID `"deep_agent": "./agent.py:agent"` 或 `"./agent.ts:agent"`）。
  - 安裝套件：Python 安裝 `pip install deepagents "langgraph-cli[inmem]"` 並執行 `langgraph dev`；JS 安裝 `npm install @ag-ui/langgraph deepagents @langchain/langgraph-cli` 並執行 `npx @langchain/langgraph-cli dev`，將代理暴露於 `http://localhost:2024`。
  - 使用 TypeScript 轉接器 `@ag-ui/langgraph` 的 `LangGraphAgent` 連接執行中的 Agent Server（無論底層圖是由 Python 或 TypeScript 撰寫皆可驅動；Python 亦可搭配 CopilotKit FastAPI bridge）。
- **`LangGraphAgent` 程式化 API**：
  - 建構：`new LangGraphAgent({ graphId: "deep_agent", deploymentUrl: "http://localhost:2024", initialMessages?: [...], emitInterruptOutcome?: boolean })`。
  - 核心方法：
    - `runAgent(parameters?, subscriber?)`：執行代理並將 AG-UI 事件串流至 `subscriber` 的 `on…Event` 回呼（如 `onTextMessageContentEvent`、`onToolCallStartEvent`、`onStateSnapshotEvent`、`onRunFinishedEvent`），於執行完成時 resolve。
    - `subscribe(subscriber)`：掛載跨每次執行持續接收事件的持久化訂閱者。
    - `abortRun()`：取消進行中的執行。
    - 訊息初始化：可於建構子傳入 `initialMessages`，或在執行前呼叫 `addMessage`、`setMessages`。
- **AG-UI 事件映射表（Typed Event Stream）**：
  - **Run lifecycle（執行生命週期）**：`RUN_STARTED`、`RUN_FINISHED`、`RUN_ERROR`。
  - **Graph node progress（節點進度）**：`STEP_STARTED`、`STEP_FINISHED`。
  - **Assistant text（助理文字串流）**：`TEXT_MESSAGE_START`、`TEXT_MESSAGE_CONTENT`、`TEXT_MESSAGE_END`。
  - **Tool calls（工具呼叫）**：`TOOL_CALL_START`、`TOOL_CALL_ARGS`、`TOOL_CALL_END`、`TOOL_CALL_RESULT`。
  - **Reasoning（推理過程）**：`REASONING_START`、`REASONING_MESSAGE_CONTENT`、`REASONING_END`。
  - **Shared state（共享狀態：todos、subagents、自訂鍵值）**：`STATE_SNAPSHOT`（完整基準快照）與 `STATE_DELTA`（基於 JSON Patch RFC 6902 的增量變更，免除每步重傳完整狀態）。
  - **Conversation history（對話歷史）**：`MESSAGES_SNAPSHOT`。
- **Human-in-the-Loop 中斷與恢復（Interrupt & Resume）**：
  - 預設情況下，當代理暫停等待人工輸入時，`@ag-ui/langgraph` 會在發出 `RUN_FINISHED` 的同時發出舊版 `on_interrupt` 自訂事件。
  - 若在建構 `LangGraphAgent` 時設定 `emitInterruptOutcome: true`，則會在 `RUN_FINISHED` 上收到結構化的 AG-UI interrupt 結果（`outcome.type === "interrupt"`）。
  - 恢復執行時，於下次輸入傳遞標準 AG-UI `resume` 欄位：`{ threadId: "t1", runId: "r2", messages: [], resume: [{ interruptId: "int-abc", status: "resolved", payload: { approved: true } }] }`。

### 4. Changelogs（發行紀錄參照）
- **Python Changelog**（`docs/deepagents/changelog-py.md`）：指向 `https://docs.langchain.com/oss/python/releases/changelog`（設定 `noindex: true`）。
- **JavaScript Changelog**（`docs/deepagents/changelog-js.md`）：指向 `https://docs.langchain.com/oss/javascript/releases/changelog`（設定 `noindex: true`）。

## 相關頁面
- [[concepts/deepagents-overview]]
- [[concepts/deepagents-human-in-the-loop]]
- [[guides/deepagents-going-to-production]]
- [[guides/deepagents-frontend]]

## 出處
- docs/deepagents/a2a.md
- docs/deepagents/acp.md
- docs/deepagents/ag-ui.md
- docs/deepagents/changelog-py.md
- docs/deepagents/changelog-js.md
