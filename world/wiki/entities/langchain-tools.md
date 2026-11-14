# LangChain Tools

別名：LangChain 工具、`@tool`、`tool()`、`ToolRuntime`、`ToolNode`、`HeadlessTool`、`MCPAdapter`、Dynamic Tools
框架：langchain

## 摘要
Tools（工具）是具備明確輸入與輸出 schema 的可呼叫函式，讓 LangChain 代理能擷取即時資料、執行程式碼、查詢外部資料庫並改變環境狀態。LangChain 支援透過 `@tool` 裝飾器（Python）與 `tool()` 函式（JavaScript/TypeScript）定義工具，並提供 `ToolRuntime` 進行依賴注入以存取短期狀態（State）、執行期配置（Context）、長期記憶（Store）與串流寫入器，同時支援回傳 `Command` 更新狀態、`return_direct` 短路返回、動態工具篩選與註冊、瀏覽器端執行的 Headless tools 以及 Model Context Protocol（MCP）工具整合。

## 重點

### 基本工具定義與進階 Schema 設定（Creating Tools）
- **命名規範建議**：工具名稱應優先採用 `snake_case`（例如 `web_search` 而非 `Web Search`），僅使用英數字元、底線（`_`）與連字號（`-`），避免部分模型供應商因空白或特殊字元而拒絕請求或報錯。
- **Python 工具定義（`from langchain.tools import tool`）**：
  - 使用 `@tool` 裝飾器將函式轉為工具，預設以函式名稱作為工具名稱、函式的 docstring 作為工具描述（description）。**必須（Required）**提供參數的型別提示（Type hints）以定義輸入 schema。
  - **自訂名稱與描述**：`@tool("web_search")` 可覆寫工具名稱；`@tool("calculator", description="Performs arithmetic calculations...")` 可覆寫描述。
  - **進階 Schema（`args_schema`）**：可傳入 Pydantic `BaseModel` 子類別（支援 `Field(default=..., description=...)` 與 `Literal`）或 JSON Schema dict（如 `@tool(args_schema=WeatherInput)` 或 `@tool(args_schema=weather_schema)`）。
- **JavaScript / TypeScript 工具定義（`import { tool } from "langchain"` 或 `"@langchain/core/tools"`）**：
  - 呼叫 `tool(fn, { name, description, schema })`，其中 `schema` 通常使用 Zod（`z.object({...})`）或 JSON Schema 物件定義。
- **保留參數名稱（Reserved Argument Names）**：
  - **`config`**：保留供內部傳遞 `RunnableConfig` 使用。
  - **`runtime`**：保留供 `ToolRuntime` 參數注入使用。
  - 使用者自訂工具參數**不可**命名為 `config` 或 `runtime`，否則會導致執行期錯誤。

### 存取執行期上下文与記憶（Access Context via `ToolRuntime`）
- **注入機制與遷移指南**：
  - 在 Python 工具函式簽章中加入 `runtime: ToolRuntime`（或泛型 `runtime: ToolRuntime[Context]`），`ToolNode` 會在呼叫時自動注入，且 `runtime` 參數會對模型的工具 schema 隱藏。
  - **舊版注入模式遷移**：舊版使用的 `InjectedState`、`InjectedStore`、`get_runtime()`、`InjectedToolCallId` 均建議遷移為統一的 `ToolRuntime` 介面（例如以 `runtime.state["messages"]` 取代 `state: InjectedState`）。
- **`ToolRuntime` 提供的八大資源（Python vs. JS/TS）**：
  1. **State（短期記憶）**：透過 `runtime.state` 讀取當前對話的 `messages` 與自訂狀態欄位（如 `runtime.state.get("user_preferences", {})`）。
  2. **Context（單次呼叫靜態設定）**：Python 透過 `runtime.context`、JS/TS 透過 `runtime.context`（或 `config`）讀取不可變配置（如 `user_id`、session info）。
  3. **Store（跨對話長期記憶）**：Python 透過 `runtime.store`、JS/TS 透過 `config.store`（或 `runtime.store`）存取 `BaseStore`（開發用 `InMemoryStore`，生產環境用 `PostgresStore`、`MongoDBStore`、`RedisStore`），以 `store.get(("users",), user_id)` / `store.put(("users",), user_id, {...})` 讀寫。
  4. **Stream Writer（即時串流輸出）**：Python 透過 `runtime.stream_writer`、JS/TS 透過 `config.writer` 在 `"custom"` 串流模式下發送進度訊息（注意：使用此功能的工具必須在 LangGraph 執行上下文內呼叫）。
  5. **Execution Info（執行身分與重試資訊）**：Python `runtime.execution_info`（含 `thread_id`、`run_id`、`node_attempt`）；JS/TS `runtime.executionInfo`（含 `threadId`、`runId`、`nodeAttempt`）。需 Python `deepagents>=0.5.0`（或 `langgraph>=1.1.5`）、JS/TS `deepagents>=1.9.0`（或 `@langchain/langgraph>=1.2.8`）。
  6. **Server Info（Agent Server 中繼資料）**：Python `runtime.server_info`（含 `assistant_id`、`graph_id`、`user.identity`；非 Agent Server 時為 `None`）；JS/TS `runtime.serverInfo`（含 `assistantId`、`graphId`、`user.identity`；非 Agent Server 時為 `null`）。版本需求同 Execution Info。
  7. **Config**：`RunnableConfig`（含 callbacks、tags、metadata）。
  8. **Tool Call ID**：Python `runtime.tool_call_id` / JS/TS `runtime.toolCallId`，當前工具呼叫的唯一識別碼。

### 工具回傳值型別與執行控制（Tool Return Values & Control Flow）
- **五種工具回傳模式**：
  1. **回傳 `string`**：自動轉換為 `ToolMessage` 交給模型閱讀，不直接修改圖狀態。
  2. **回傳 `object`（如 Python `dict`）**：自動序列化為工具輸出供模型讀取結構化欄位，不直接修改圖狀態。
  3. **回傳多模態內容（Multimodal content）**：回傳標準內容區塊列表（如 `[{"type": "text", "text": "..."}, {"type": "image", "url": "https://example.com/page.png"}]`），自動轉為具多模態 `content` 的 `ToolMessage`（MCP 工具回傳圖片或混合內容時亦同）。
  4. **回傳 `Command` 更新狀態**：當工具需要修改圖狀態（state）時，回傳 `Command(update={...})`。若目標為當前圖（`graph` 未設定或為 `None`），`Command.update` 的 `messages` 中**必須**包含一個 `tool_call_id` 與 `runtime.tool_call_id`（JS 為 `runtime.toolCallId`）相符的 `ToolMessage`，否則 `ToolNode` 會拋出 `ValueError`。若多個平行工具同時更新同一狀態欄位，應為該欄位定義 reducer。
  5. **直接回傳（`return_direct=True`）**：短路（short-circuit）代理迴圈，工具輸出封裝為 `ToolMessage` 後立即作為最終回應返回呼叫端，不再經過額外的模型呼叫。
     - **平行工具呼叫限制（Mixed parallel calls）**：若模型在同一步驟平行呼叫多個工具，所有工具都會先執行完畢；唯有當該批次中**每一個**被呼叫的工具都設定了 `return_direct=True` 時，代理才會直接路由至 `END` 結束；若混有任何未設定 `return_direct=True` 的工具，代理**不會**提前結束，而是將所有 `ToolMessage` 送回模型進行推理。
     - **`return_direct=True` 搭配 `Command`**：更新當前圖時同樣必須在 `Command.update` 包含對應 `tool_call_id` 的 `ToolMessage`；唯有設定 `graph=Command.PARENT` 寫入父圖並離開當前圖時，才免除此限制。

### 動態工具選擇與註冊（Dynamic Tool Selection）
- **模式一：過濾預先註冊的工具（Filtering pre-registered tools）**：
  - 適用於所有可能工具在編譯/啟動時已知，需依對話狀態（State，如 `state.get("authenticated")` 或訊息數量）、長期記憶（Store，如使用者 feature flags）或執行期上下文（Runtime Context，如 `user_role == "admin" | "editor" | "viewer"`）動態篩選的情況。
  - 實作方式：在 middleware 使用 `@wrap_model_call`（Python，呼叫 `handler(request.override(tools=tools))`）或 `wrapModelCall`（JS/TS，呼叫 `handler({ ...request, tools: filteredTools })`）覆寫當次請求可見的工具列表。
- **模式二：執行期動態註冊工具（Runtime tool registration）**：
  - 適用於執行期才發現或生成的工具（如從 MCP server 或遠端註冊表載入）。必須同時實作**兩個** middleware 鉤子：
    1. `wrap_model_call` / `wrapModelCall`：將動態工具加入 `request.tools` 供模型看見。
    2. `wrap_tool_call` / `wrapToolCall`：攔截對該動態工具名稱的呼叫，透過 `request.override(tool=calculate_tip)`（Python）或 `handler({ ...request, tool: calculateTip })`（JS/TS）指定實際執行的工具實例（若缺少此鉤子，代理將不知道如何執行未在初始清單中的工具）。

### 無頭工具（Headless Tools）與 MCP 工具整合
- **Headless Tools（客戶端/瀏覽器端執行工具）**：
  - 適用場景：依賴客戶端環境、裝置或 UI 的操作（如瀏覽器 Geolocation、IndexedDB、Clipboard、Canvas 2D、檔案選擇器、Battery API）、資料隱私留存本地、降低伺服器來回延遲。
  - **運作機制（Interrupt / Resume Handshake）**：
    - **Python**：呼叫 `tool(name=..., description=..., args_schema=...)` 僅傳入名稱、描述與 schema 而不提供函式實作時，會回傳 `HeadlessTool`（Python 端無 `.implement()` API）。註冊至 `create_agent` 後，當模型呼叫該工具時，圖會暫停並發出結構為 `{"type": "tool", "tool_call": {"id", "name", "args"}}` 的 interrupt payload，待外部環境執行完畢後再 resume。
    - **JS/TS**：在共享模組以 `tool({ name, description, schema })` 定義僅含驗證與 metadata 的工具並註冊至伺服器端 `createAgent`；在前端模組對該定義呼叫 `.implement(async (args) => { ... })` 建立含 `execute` 函式的實作，並傳入前端串流 hook（如 `useStream`）的 `tools` 選項（可搭配 `onTool` 回呼監聽 `start`、`success`、`error` 事件）。
- **Model Context Protocol（MCP）工具**：
  - **Python**：使用 `from langchain.mcp import MCPAdapter`（需安裝 `langchain[mcp]>=1.4.0`，目前為 beta），透過 `async with MCPAdapter("https://example.com/mcp") as adapter: tools = await adapter.list_tools()` 取得工具並傳入 `create_agent`。
  - **JS/TS**：透過 `@langchain/mcp-adapters` 套件探索並轉換 MCP 伺服器工具。

## 相關頁面
- [[concepts/langchain-overview-and-architecture]]
- [[concepts/langchain-agents-and-runtime]]
- [[entities/langchain-models]]
- [[entities/langchain-messages]]
- [[concepts/langchain-structured-output]]
- [[concepts/langchain-streaming]]
- [[entities/langchain-error-codes]]

## 出處
- docs/langchain/tools.md
