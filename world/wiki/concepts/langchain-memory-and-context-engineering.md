# LangChain Memory and Context Engineering

別名：短期記憶與長期記憶、上下文工程、Short-term Memory、Long-term Memory、Context Engineering、對話歷史管理、Agent State 與 Store
框架：langchain

## 摘要
LangChain 將代理（Agent）的記憶分為單一對話執行緒（Thread）內的短期記憶（Short-term memory，透過 `checkpointer` 與 `AgentState` 管理）以及跨對話執行緒與工作階段的長期記憶（Long-term memory，透過 LangGraph `store` 以 `namespace` 與 `key` 儲存 JSON 文件）。上下文工程（Context Engineering）則是透過中介軟體（Middleware）與工具（Tools），針對單次呼叫的暫態模型上下文（Model Context：System Prompt、Messages、Tools、Model、Response Format）、持久化的工具上下文（Tool Context）與生命週期上下文（Life-cycle Context），從執行期上下文（Runtime Context）、短期狀態（State）與長期儲存（Store）三大資料來源動態讀寫與塑造傳遞給 LLM 的資訊。

## 重點

### 一、短期記憶（Short-term Memory）
- **基本原理與啟用方式**：
  - 短期記憶讓應用程式在單一 `thread`（對話執行緒）內記住先前的互動，作為代理狀態（State）的一部分管理。當代理被呼叫或完成一個步驟（如工具呼叫）時更新狀態，並在每個步驟開始時讀取狀態。
  - 建立代理時必須傳入 `checkpointer` 參數給 `create_agent`（Python）或 `createAgent`（TypeScript/JavaScript）。
  - 呼叫時需在設定中傳遞 `{"configurable": {"thread_id": "1"}}`（型別為 `RunnableConfig`）。
- **記憶後端（Checkpointers）**：
  - 記憶體內儲存：Python 使用 `from langgraph.checkpoint.memory import InMemorySaver`；TypeScript/JavaScript 使用 `import { MemorySaver } from "@langchain/langgraph"`。
  - 正式環境（Production）PostgreSQL 儲存：
    - Python 安裝：`pip install -U langgraph-checkpoint-postgres "psycopg[binary]"` 或 `uv add langgraph-checkpoint-postgres "psycopg[binary]"`（預設安裝 Psycopg 3 不含 extras，建議加上 `psycopg[binary]`）。使用 `from langgraph.checkpoint.postgres import PostgresSaver`，透過 `with PostgresSaver.from_conn_string(DB_URI) as checkpointer:` 並呼叫 `checkpointer.setup()` 自動建立資料表（範例連線字串：`DB_URI = "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable"`）。
    - TypeScript/JavaScript：使用 `import { PostgresSaver } from "@langchain/langgraph-checkpoint-postgres"`，呼叫 `PostgresSaver.fromConnString(DB_URI)`。
- **自訂代理記憶狀態（Customizing Agent Memory）**：
  - **Python**：預設使用 `AgentState`（包含由 `add_messages` reducer 管理的 `messages` 欄位）。可繼承 `AgentState` 新增欄位（如 `user_id: str`、`preferences: dict`），並透過 `create_agent(..., state_schema=CustomAgentState)` 傳入。
  - **TypeScript/JavaScript**：使用 `import { StateSchema } from "@langchain/langgraph"` 定義自訂狀態（如 `new StateSchema({ userId: z.string(), preferences: z.record(z.string(), z.any()) })`，亦支援一般 Zod 物件）。可將 `stateSchema: CustomState` 傳給 `createMiddleware({ name: "StateExtension", stateSchema: CustomState })` 或直接傳給 `createAgent({ ..., stateSchema: CustomState })`。
- **管理長對話歷史的四大常見模式**：
  1. **修剪訊息（Trim messages）**：
     - 透過計算訊息歷史的 token 數量並在接近上限時截斷（指定 `max_tokens` / `maxTokens` 與 `strategy`）。
     - Python 可在 `@before_model` 中介軟體裝飾器函式 `(state: AgentState, runtime: Runtime) -> dict[str, Any] | None` 中切片保留首則與最近訊息，並回傳 `{"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *new_messages]}`。
     - TypeScript/JavaScript 可在 `createMiddleware` 的 `beforeModel` 鉤子中使用內建 `trimMessages(state.messages, { maxTokens: 384, strategy: "last", startOn: "human", endOn: ["human", "tool"], tokenCounter: (msgs) => msgs.length })`，並搭配 `new RemoveMessage({ id: REMOVE_ALL_MESSAGES })` 回傳。
  2. **刪除訊息（Delete messages）**：
     - 永久從 LangGraph state 刪除特定或全部訊息。需要狀態鍵綁定訊息 reducer（Python 的 `add_messages`，預設 `AgentState` 已內建；JS 的 `messagesStateReducer`，如 `MessagesValue`）。
     - 刪除特定訊息：Python 使用 `from langchain.messages import RemoveMessage`，回傳 `{"messages": [RemoveMessage(id=m.id) for m in messages[:2]]}`；JS 使用 `import { RemoveMessage } from "@langchain/core/messages"`，回傳 `messages.slice(0, 2).map((m) => new RemoveMessage({ id: m.id }))`。
     - 刪除全部訊息：使用 `from langgraph.graph.message import REMOVE_ALL_MESSAGES`（JS 為 `import { REMOVE_ALL_MESSAGES } from "@langchain/langgraph"`），回傳 `[RemoveMessage(id=REMOVE_ALL_MESSAGES)]`。
     - **重要限制與警告**：刪除訊息時必須確保剩餘的訊息歷史符合 LLM 供應商規範——部分供應商要求訊息歷史必須以 `user` 訊息開頭；多數供應商要求包含工具呼叫的 `assistant` 訊息後面必須緊跟對應的 `tool` 結果訊息。可搭配 `@after_model` / `afterModel` 在模型回應後刪除舊訊息或過濾含敏感字詞（如 `"password"`、`"secret"`、`"confidential"`）的訊息。
  3. **摘要訊息（Summarize messages）**：
     - 使用獨立的聊天模型將較早的對話歷史濃縮並永久替換為摘要訊息，避免單純截斷造成的資訊流失。
     - Python 使用 `from langchain.agents.middleware import SummarizationMiddleware`：例如 `SummarizationMiddleware(model="gpt-5.4-mini", trigger=("tokens", 4000), keep=("messages", 20))`（`trigger` 亦支援 `{"tokens": 4000}`）。
     - TypeScript/JavaScript 使用 `import { summarizationMiddleware } from "langchain"`：例如 `summarizationMiddleware({ model: "gpt-5.4-mini", trigger: { tokens: 4000 }, keep: { messages: 20 } })`。
  4. **自訂策略（Custom strategies）**：例如自訂訊息過濾邏輯。
- **在工具與中介軟體中存取短期記憶**：
  - **在工具中讀取狀態（Read short-term memory in a tool）**：
    - Python：工具函式接收 `runtime: ToolRuntime` 參數（此參數對模型隱藏，不會出現在工具 schema 中），透過 `runtime.state["user_id"]` 讀取。
    - TypeScript/JavaScript：工具函式第二個參數為 `config: ToolRuntime<typeof CustomState.State>`，透過 `config.state.userId` 讀取。
  - **從工具中寫入狀態（Write short-term memory from tools）**：
    - 工具回傳 `Command`（`from langgraph.types import Command` / `import { Command } from "@langchain/langgraph"`）以直接更新狀態。
    - Python：`ToolRuntime[CustomContext, CustomState]`，回傳 `Command(update={"user_name": name, "messages": [ToolMessage("Successfully looked up user information", tool_call_id=runtime.tool_call_id)]})`。
    - TypeScript/JavaScript：回傳 `new Command({ update: { userName: name, messages: [new ToolMessage({ content: "...", tool_call_id: config.toolCall?.id ?? "" })] } })`。
  - **在提示詞與模型前後鉤子存取**：
    - 動態提示詞：Python 使用 `@dynamic_prompt` 裝飾器接收 `request: ModelRequest`（讀取 `request.runtime.context` 或 `request.state`）；JS 使用 `dynamicSystemPromptMiddleware<ContextSchema>((state, config) => ...)`。
    - 模型呼叫前：`@before_model` / `beforeModel`（執行流程：`__start__ -> before_model -> model -> tools -> before_model`）。
    - 模型呼叫後：`@after_model` / `afterModel`（執行流程：`__start__ -> model -> after_model -> tools / __end__`）。

---

### 二、長期記憶（Long-term Memory）
- **核心架構**：
  - 跨不同對話與工作階段持久化儲存與召回資料，建立在 LangGraph stores（`store`）之上。
  - 每筆記憶以 JSON 文件形式儲存在自訂的 `namespace`（類似資料夾的階層式結構，常包含 user ID、org ID 或標籤，如 `("preferences",)` 或 `["preferences"]`）與獨立的 `key`（類似檔名，如 `user_id`）下，並支援跨命名空間的內容過濾搜尋。
- **設定與讀寫方式**：
  - 建立儲存實例（如 `from langgraph.store.memory import InMemoryStore` 或 PostgreSQL store，需安裝 `langgraph-checkpoint-postgres "psycopg[binary]"` / `@langchain/langgraph-checkpoint-postgres`；亦支援 Redis、MongoDB 等後端）並透過 `create_agent(..., store=...)` 傳入。
  - 在工具或中介軟體中透過 `runtime.store`（或 `request.runtime.store`）存取：
    - 讀取：`store.get(("preferences",), user_id)`（Python）或 `await store.get(["preferences"], userId)`（JS），透過回傳物件的 `.value` 取得字典/物件內容。
    - 寫入：`store.put(("preferences",), user_id, prefs)`（Python）或 `await store.put(["preferences"], userId, prefs)`（JS）。

---

### 三、上下文工程（Context Engineering）分類架構
- **代理失敗的兩大原因**：
  1. 底層 LLM 能力不足。
  2. 沒有傳遞「正確」的上下文給 LLM（最常見的原因）。上下文工程即是以正確格式提供正確資訊與工具。
- **三大上下文控制維度（Transient vs. Persistent）**：
  | Context Type | 控制內容 | 暫態或持久（Transient or Persistent） |
  | :--- | :--- | :--- |
  | **Model Context** | 進入模型呼叫的內容（instructions、message history、tools、model、response format） | **Transient**（僅影響單次 LLM 呼叫，不改變儲存在 state 的內容） |
  | **Tool Context** | 工具可存取與產生的內容（對 state、store、runtime context 的讀寫） | **Persistent**（永久改變狀態或儲存） |
  | **Life-cycle Context** | 模型與工具呼叫之間發生的跨領域邏輯（summarization、guardrails、logging、跳轉步驟） | **Persistent**（永久寫入 state） |
- **三大資料來源（Data Sources）**：
  | Data Source | 別稱（Also Known As） | 作用範圍（Scope） | 範例 |
  | :--- | :--- | :--- | :--- |
  | **Runtime Context** | Static configuration | Conversation-scoped | User ID、API keys、database connections、permissions、environment settings |
  | **State** | Short-term memory | Conversation-scoped | Current messages、uploaded files、authentication status、tool results |
  | **Store** | Long-term memory | Cross-conversation | User preferences、extracted insights、memories、historical data |

---

### 四、模型上下文（Model Context）的五大控制項與實作細節
所有模型上下文控制項皆可從 **State**、**Store** 或 **Runtime Context** 讀取資料：
1. **System Prompt（系統提示詞）**：
   - Python 使用 `@dynamic_prompt` 裝飾器函式 `(request: ModelRequest) -> str`（其中 `request.messages` 是 `request.state["messages"]` 的捷徑；`request.runtime.store` 存取長期記憶；`request.runtime.context` 存取靜態設定，需在 `create_agent` 指定 `context_schema`）。
   - TypeScript/JavaScript 使用 `dynamicSystemPromptMiddleware<Context>((state, runtime) => ...)`（支援同步與 `async` 函式）。
2. **Messages（訊息歷史）**：
   - 使用 `@wrap_model_call`（Python）或 `createMiddleware({ wrapModelCall: (request, handler) => ... })`（JS）進行**暫態（Transient）**訊息注入（例如注入 `uploaded_files` 摘要、`writing_style` 範例、或依據 `user_jurisdiction` / `industry` / `compliance_frameworks` 如 `"GDPR"`、`"HIPAA"`、`"finance"` 注入合規規則到訊息末尾）。
   - Python 使用 `request = request.override(messages=messages)` 後呼叫 `return handler(request)`；JS 使用 `request = { ...request, messages }` 後呼叫 `return handler(request)`。
   - 若需從 `wrap_model_call` 進行**持久化（Persistent）**狀態更新：Python 可回傳包含 `Command` 的 `ExtendedModelResponse`；JS 可直接從 `wrapModelCall` 回傳 `Command`；或改用 `before_model`、`after_model`、`wrap_tool_call` 等生命週期鉤子。
3. **Tools（工具定義與動態篩選）**：
   - **定義工具**：Python 使用 `@tool(parse_docstring=True)` 自動解析 Google 風格 docstring 的 `Args:` 作為參數說明；JS 使用 `@langchain/core/tools` 的 `tool(fn, { name, description, schema: z.object({...}) })`。
   - **動態選擇工具（Selecting tools）**：在 `@wrap_model_call` / `wrapModelCall` 中過濾 `request.tools`（例如未認證 `!is_authenticated` 時僅保留 `t.name.startswith("public_")`，對話初期 `message_count < 5` 時排除 `"advanced_search"`，依 Store 中的 `enabled_tools` 過濾，或依 Runtime Context 的 `user_role` 為 `"admin"`、`"editor"`、`"viewer"` 過濾 `"delete_data"` 與 `"read_"` 工具），並透過 `request.override(tools=tools)`（Python）或 `handler({ ...request, tools: filteredTools })`（JS）覆寫。
4. **Model（動態模型選擇）**：
   - 先在 middleware 外部透過 `init_chat_model`（Python：`from langchain.chat_models import init_chat_model`）或 `initChatModel`（JS：`import { initChatModel } from "langchain"`）初始化模型實例（如 `"claude-sonnet-4-6"`、`"gpt-6.1-sol"`、`"gpt-5.4-mini"`）。
   - 在 `@wrap_model_call` / `wrapModelCall` 中依對話長度（如 `message_count > 20`、`> 10`）、Store 中的 `preferred_model`、或 Runtime Context 的 `cost_tier`（`"premium"` / `"budget"`）與 `environment`（`"production"`），呼叫 `request.override(model=model)`（Python）或 `handler({ ...request, model })`（JS）動態切換模型。
5. **Response Format（結構化輸出格式）**：
   - 當提供 schema 作為 response format 時，代理會執行模型與工具呼叫迴圈直到不再呼叫工具，最後將最終回應強制轉換為指定結構（Python 使用 Pydantic `BaseModel` 與 `Field`；JS 使用 Zod `z.object`）。
   - 在 `@wrap_model_call` / `wrapModelCall` 中可依對話階段（如 `message_count < 3` 使用 `SimpleResponse`，否則使用含 `reasoning` 與 `confidence` 的 `DetailedResponse`）、Store 中的 `response_style`（`"verbose"` vs `"concise"`）、或 Runtime Context 的角色與環境（`AdminResponse` vs `UserResponse`），透過 `request.override(response_format=...)`（Python）或 `handler({ ...request, responseFormat })`（JS）動態切換輸出結構。

---

### 五、工具上下文（Tool Context）與生命週期上下文（Life-cycle Context）
- **工具讀取（Tool Reads）**：透過 `runtime: ToolRuntime`（或 `ToolRuntime[Context]`）讀取 `runtime.state`（如檢查 `authenticated`）、`runtime.store`（如 `store.get(("preferences",), user_id)`）與 `runtime.context`（如讀取 `user_id`、`api_key`、`db_connection`）。
- **工具寫入（Tool Writes）**：
  - 寫入 State：回傳 `Command(update={"authenticated": True})`（Python）或 `new Command({ update: { authenticated: true } })`（JS）。
  - 寫入 Store：呼叫 `runtime.store.put(("preferences",), user_id, prefs)` 跨工作階段持久化儲存。
- **生命週期上下文與最佳實踐**：
  - 利用 middleware 在核心代理步驟之間攔截資料流以更新上下文或跳轉生命週期步驟（如 `SummarizationMiddleware` 永久替換舊訊息為摘要）。
  - 最佳實踐：從靜態提示詞與工具開始（Start simple）、逐步增量測試（Test incrementally）、監控模型呼叫與 token 耗用及延遲（Monitor performance）、優先使用內建 middleware（如 `SummarizationMiddleware`、`LLMToolSelectorMiddleware`）、記錄上下文策略、並明確區分暫態（Model context）與持久化（Life-cycle context）更新。

## 相關頁面
- [[concepts/langchain-middleware]]
- [[entities/langchain-builtin-middleware]]
- [[concepts/langchain-human-in-the-loop-and-guardrails]]

## 出處
- docs/langchain/short-term-memory.md
- docs/langchain/long-term-memory.md
- docs/langchain/context-engineering.md
