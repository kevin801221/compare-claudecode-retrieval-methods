# LangChain Agents and Runtime

別名：LangChain 代理與執行期環境、`create_agent`、`createAgent`、`AgentState`、`Runtime`、`ToolRuntime`、Agent Harness
框架：langchain

## 摘要
LangChain 的代理（Agent）是一個在迴圈中持續呼叫工具直到完成任務的模型，其外圍由提示詞、工具與中介軟體（middleware）構成的 Harness 加以塑形。`create_agent`（Python）與 `createAgent`（JavaScript/TypeScript）底層運作於 LangGraph 執行期（Runtime）之上，透過 `AgentState` 管理對話歷史與自訂狀態，並透過 `Runtime` 物件將靜態 `context`、長期記憶 `store`、串流寫入器 `stream_writer`、執行資訊 `execution_info` 與伺服器資訊 `server_info` 注入工具與中介軟體中。

## 重點

### Agent 核心迴圈與 `create_agent` / `createAgent` 核心元件
- **代理定義**：代理是在迴圈中呼叫工具直到給定任務完成的模型（An agent is a model calling tools in a loop until a given task is complete）。Harness 的職責是在正確的時間將正確的上下文提供給模型。
- **核心參數與元件（Python vs. JavaScript/TypeScript）**：
  - **`model`**：可傳入模型識別字串（格式為 `"provider:model"`，如 `"openai:gpt-6.1-sol"`、`"gpt-5-nano"`）或已初始化的模型實例（如 `init_chat_model` 回傳物件）。
  - **`tools`**：提供給代理的工具清單。Python 支援傳入任何 Python callable、LangChain tool 或 tool dict；JS/TS 支援傳入 `tool()` 建立的工具或定義。
  - **`system_prompt`（Python） / `systemPrompt`（JS/TS）**：接收字串（`str` / `string`）或 `SystemMessage` 物件，用於定義代理的角色與行為準則。若需在執行期動態產生提示詞，應使用 middleware（例如 Python 的 `@dynamic_prompt` 或 JS/TS 的 `beforeModel`）。
  - **`response_format`（Python） / `responseFormat`（JS/TS）**：指定代理回傳驗證過的結構化輸出 schema（詳見 [[concepts/langchain-structured-output]]）。
  - **`state_schema`（Python）**：傳入繼承自 `AgentState` 的子類別以擴充自訂狀態欄位。在 JS/TS 中，則是在 middleware 上使用 `stateSchema`（搭配 `StateSchema` 或 Zod 物件）定義自訂狀態欄位。
  - **`context_schema`（Python） / `contextSchema`（JS/TS）**：定義執行期注入之 `Runtime.context` 的資料結構（Python 常使用 `@dataclass` 類別，JS/TS 常使用 `z.object({...})`）。
  - **`checkpointer`**：用於持久化對話歷史與支援跨輪次記憶（如 Python 的 `InMemorySaver()`、JS/TS 的 `new MemorySaver()`；部署於 LangSmith Agent Server 時會自動配置 checkpointer）。
  - **`store`**：傳入 `BaseStore` 實例（如 `InMemoryStore`）以啟用跨對話的長期記憶。
  - **`middleware`**：傳入中介軟體清單以擴充 harness 能力。
  - **`name`**：選用的代理識別名稱字串，特別適用於將代理作為子圖（subgraph）嵌入多代理系統（multi-agent systems）或在串流中透過 `lc_agent_name` 區分來源。

### 代理狀態（`AgentState`）
- **內建欄位**：
  - `messages`：Python 型別為 `list[BaseMessage]`（或 `AnyMessage`），JS/TS 型別為 `BaseMessage[]`。存放當前對話執行緒（thread）的完整對話歷史，採 **Append-only（僅追加）** 模式，新訊息只會被附加而不會直接覆寫舊訊息。
- **與 Middleware 的關係**：`AgentState` 同時也是所有節點式（node-style）middleware 鉤子（Python 的 `before_model`、`after_model`；JS/TS 的 `beforeModel`、`afterModel` 等）的輸入型別簽章。鉤子接收當前 state，並可回傳包含更新欄位的 dict / object 以合併回狀態中。

### 代理呼叫（Invocation）：`thread_id` 與 `context`
- **呼叫機制**：呼叫 `agent.invoke(...)` 時，底層會向代理的 LangGraph `State` 發送更新。
- **`thread_id` vs. `context` 的職責區分**：
  - **`thread_id`**：透過 `config={"configurable": {"thread_id": "..."}}`（Python）或 `{ configurable: { thread_id: "..." } }`（JS/TS）傳入，用於界定**對話（conversation）範圍**（訊息歷史與 checkpoints），需要搭配 `checkpointer` 才能持久化。
  - **`context`**：在 `invoke` 時與 `config` 並列傳入（Python 為 `agent.invoke(input, context=Context(...), config=...)`，JS/TS 為 `await agent.invoke(input, { context: {...}, configurable: {...} })`），用於攜帶**單次執行（per-run）**的靜態配置（如使用者 ID、資料庫連線、API keys、feature flags），供工具與 middleware 在執行期透過 `runtime.context` 讀取。

### Harness 六大擴充能力與內建 Middleware 生態系
- `create_agent` 透過 middleware 支援六大生產級能力領域（`create_deep_agent` 已預設組裝檔案系統、摘要、子代理與提示詞快取）：
  1. **Execution environment（執行環境）**：賦予代理工作區，包含工具呼叫、跨輪次讀寫檔案的檔案系統（`FilesystemMiddleware`，需安裝 `deepagents`）、Sandboxes 與程式碼執行（Interpreters）。
  2. **Context management（上下文管理）**：解決固定上下文視窗溢位問題，包含在溢位前壓縮歷史的 `SummarizationMiddleware`、啟動時載入持久化指令的 `MemoryMiddleware`（兩者皆可從 `deepagents` 匯入）、按需載入領域知識的 Skills 與 Prompt caching。
  3. **Planning and delegation（規劃與委派）**：透過待辦清單（Todo lists）與子代理（Subagents，各自在隔離的上下文中平行執行）拆解超出單一上下文視窗的複雜任務。
  4. **Fault tolerance（容錯機制）**：在基礎設施層處理速率限制、模型逾時與暫時性 API 錯誤，包含 Python 的 `ModelRetryMiddleware`、`ToolRetryMiddleware` 與 JS/TS 的 `modelRetryMiddleware`、`toolRetryMiddleware`。
  5. **Guardrails（護欄）**：在資料流經代理迴圈時進行確定性的合規與內容策略攔截，例如 Python 的 `PIIMiddleware` 與 JS/TS 的 `piiMiddleware`。
  6. **Steering（人工引導 / Human-in-the-loop）**：在破壞性寫入或高成本 API 呼叫前暫停代理，等待人類批准（approve）、編輯（edit）或拒絕（reject）後再繼續執行，使用 Python 的 `HumanInTheLoopMiddleware` 或 JS/TS 的 `humanInTheLoopMiddleware`。

### 執行期物件（`Runtime` 與 `ToolRuntime`）
- **五大核心屬性**：`create_agent` / `createAgent` 底層運行於 LangGraph Runtime，暴露 `Runtime` 物件（在工具內透過 `ToolRuntime` 存取），包含以下 5 項資訊：
  1. **Context（`runtime.context`）**：單次代理呼叫的靜態資訊（如 `user_id`、資料庫連線或其他依賴注入項目），結構由 `context_schema` / `contextSchema` 定義。
  2. **Store（`runtime.store`）**：`BaseStore` 實例，用於跨對話的長期記憶（long-term memory），以 `(namespace, key)` 模式存取（例如 Python `runtime.store.get(("users",), user_id)`、JS/TS `await runtime.store?.get(["users"], userName)`）。
  3. **Stream writer（Python 為 `runtime.stream_writer` / JS 為 `config.writer`）**：用於在 `"custom"` 串流模式下發送即時自訂進度更新。
  4. **Execution info（Python 為 `runtime.execution_info` / JS 為 `runtime.executionInfo`）**：當前執行的身分與重試資訊，包含：
     - Python：`info.thread_id`、`info.run_id`、`info.node_attempt`
     - JS/TS：`info.threadId`、`info.runId`、`info.nodeAttempt`
  5. **Server info（Python 為 `runtime.server_info` / JS 為 `runtime.serverInfo`）**：當運行於 LangSmith Agent Server 時提供的伺服器端中繼資料；在本地端開發或非 Agent Server 環境下，Python 為 `None`、JS/TS 為 `null`。包含：
     - Python：`server.assistant_id`、`server.graph_id`、`server.user`（含 `server.user.identity`）
     - JS/TS：`server.assistantId`、`server.graphId`、`server.user`（含 `server.user.identity`）
- **版本需求**：存取 `execution_info` / `executionInfo` 與 `server_info` / `serverInfo` 需要：
  - Python：`deepagents>=0.5.0` 或 `langgraph>=1.1.5`
  - JS/TS：`deepagents>=1.9.0` 或 `@langchain/langgraph>=1.2.8`

### 在 Tools 與 Middleware 中存取 `Runtime`
- **在 Tools 內存取**：
  - Python：從 `langchain.tools` 匯入 `tool, ToolRuntime`，在工具函式簽章加入 `runtime: ToolRuntime[Context]`（或 `runtime: ToolRuntime`）。`ToolNode` 會在執行期自動注入，且 `runtime` 參數**不會**暴露給模型的工具 schema。此外還可存取 `runtime.state`、`runtime.config`、`runtime.tool_call_id`。
  - JS/TS：從 `"@langchain/core/tools"` 或 `"langchain"` 匯入 `ToolRuntime`，在 `tool(async (input, runtime: ToolRuntime<any, typeof contextSchema>) => { ... }, { ... })` 的第二個參數存取 `runtime.context`、`runtime.store`、`runtime.executionInfo`、`runtime.serverInfo`、`runtime.toolCallId`。
- **在 Middleware 內存取**：
  - Python：從 `langgraph.runtime` 匯入 `Runtime`，從 `langchain.agents.middleware` 匯入 `dynamic_prompt, ModelRequest, before_model, after_model`。
    - **Node-style hooks（如 `@before_model`、`@after_model`）**：簽章為 `(state: AgentState, runtime: Runtime[Context]) -> dict | None`，直接透過第二個參數 `runtime` 存取 `runtime.context`、`runtime.execution_info`、`runtime.server_info`。
    - **Wrap-style hooks（如 `@dynamic_prompt`、`@wrap_model_call`）**：接收 `request: ModelRequest` 參數，透過 `request.runtime`（例如 `request.runtime.context.user_name`）存取 `Runtime` 物件。
  - JS/TS：從 `"langchain"` 匯入 `createMiddleware, SystemMessage`，在 `createMiddleware({ name, contextSchema, beforeModel: (state, runtime) => { ... }, afterModel: (state, runtime) => { ... } })` 中直接透過第二個參數 `runtime` 存取 `runtime.context`、`runtime.executionInfo`、`runtime.serverInfo`；在 `wrapModelCall: (request, handler) => { ... }` 中則透過 `request.runtime` 存取。

## 相關頁面
- [[concepts/langchain-overview-and-architecture]]
- [[entities/langchain-models]]
- [[entities/langchain-messages]]
- [[entities/langchain-tools]]
- [[concepts/langchain-structured-output]]
- [[concepts/langchain-streaming]]

## 出處
- docs/langchain/agents.md
- docs/langchain/runtime.md
