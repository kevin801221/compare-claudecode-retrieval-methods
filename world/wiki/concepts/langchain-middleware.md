# LangChain Middleware Architecture and Custom Middleware

別名：中介軟體架構、自訂中介軟體、Agent Middleware、Middleware Hooks、洋蔥模型、Node-style Hooks、Wrap-style Hooks
框架：langchain

## 摘要
LangChain 的中介軟體（Middleware）提供在代理執行迴圈（Agent Loop）各個階段攔截、轉換與控制資料流的能力，可用於日誌追蹤、動態提示詞與工具篩選、重試與降級（Fallback）、速率限制、護欄（Guardrails）及 PII 偵測。中介軟體並非獨立的執行環境，而是直接編譯在 `create_agent` / `createAgent` 回傳的 LangGraph 圖形內（可作為子圖節點嵌入更大的 `StateGraph`），並提供依序執行的節點式鉤子（Node-style hooks）與洋蔥式包裹呼叫的包裹式鉤子（Wrap-style hooks）。

## 重點

### 一、基本用法與 LangGraph 工作流整合
- **掛載方式**：
  - Python：在 `create_agent(model="gpt-6.1-sol", tools=[...], middleware=[...])` 的 `middleware` 清單中傳入中介軟體實例或裝飾器函式。
  - TypeScript/JavaScript：在 `createAgent({ model: "gpt-6.1-sol", tools: [...], middleware: [...] })` 中傳入。
- **嵌入 LangGraph `StateGraph`**：
  - 中介軟體直接運行於 `create_agent` 編譯出的 LangGraph 內部。可將整個代理透過 `.add_node("email_agent", email_agent)`（Python）或 `.addNode("emailAgent", emailAgent)`（JS）放入更大的 `StateGraph(AgentState)` 中（例如先經過 `"classify"` 節點與條件邊 `route` 再進入代理）。
  - 所有的 HITL 中斷（`HumanInTheLoopMiddleware` 會比對每個工具的 `.name` 屬性）、摘要、PII 遮罩、重試與自訂鉤子都會隨該代理節點一併運作。

---

### 二、兩大鉤子類型（Node-style vs. Wrap-style Hooks）
1. **節點式鉤子（Node-style hooks）**：在特定執行時間點**依序（Sequentially）**執行，適用於日誌記錄、驗證與狀態更新。
   | Python Hook 名稱 | TypeScript/JS Hook 名稱 | 執行時機（When it runs） |
   | :--- | :--- | :--- |
   | `before_agent` | `beforeAgent` | 代理開始前（每次 invocation 執行一次） |
   | `before_model` | `beforeModel` | 每次模型呼叫前 |
   | `after_model` | `afterModel` | 每次模型回應後 |
   | `after_agent` | `afterAgent` | 代理完成後（每次 invocation 執行一次） |
2. **包裹式鉤子（Wrap-style hooks）**：圍繞每次模型或工具呼叫執行（洋蔥模型），由開發者決定 `handler` 被呼叫 0 次（短路/快取）、1 次（正常流程）或多次（重試邏輯），適用於重試、快取與請求/回應轉換。
   | Python Hook 名稱 | TypeScript/JS Hook 名稱 | 執行時機（When it runs） |
   | :--- | :--- | :--- |
   | `wrap_model_call` | `wrapModelCall` | 包裹每次模型呼叫 |
   | `wrap_tool_call` | `wrapToolCall` | 包裹每次工具呼叫 |

---

### 三、多重中介軟體的執行順序（Execution Order / Onion Model）
當設定 `middleware=[middleware1, middleware2, middleware3]` 時，完整執行順序如下：
1. **代理啟動前（`before_agent` 正序：由第一個到最後一個）**：
   - (1) `middleware1.before_agent()` → (2) `middleware2.before_agent()` → (3) `middleware3.before_agent()`
2. **進入代理迴圈，模型呼叫前（`before_model` 正序：由第一個到最後一個）**：
   - (4) `middleware1.before_model()` → (5) `middleware2.before_model()` → (6) `middleware3.before_model()`
3. **包裹模型呼叫（`wrap_model_call` 巢狀包裹：第一個包裹後面全部）**：
   - (7) `middleware1.wrap_model_call()` → `middleware2.wrap_model_call()` → `middleware3.wrap_model_call()` → `model`
4. **模型回應後（`after_model` 逆序：由最後一個回到第一個）**：
   - (8) `middleware3.after_model()` → (9) `middleware2.after_model()` → (10) `middleware1.after_model()`
5. **代理迴圈結束後（`after_agent` 逆序：由最後一個回到第一個）**：
   - (11) `middleware3.after_agent()` → (12) `middleware2.after_agent()` → (13) `middleware1.after_agent()`
- **三大核心規則**：
  - `before_*` 鉤子：First to last（正序）。
  - `after_*` 鉤子：Last to first（逆序）。
  - `wrap_*` 鉤子：Nested（第一個 middleware 在最外層包裹後續所有 middleware）。

---

### 四、建立自訂中介軟體的方式（Decorator vs. Class / `createMiddleware`）
- **Python 裝飾器模式（Decorator-based middleware）**：
  - 適合單一鉤子、無複雜設定與快速原型開發。
  - 從 `langchain.agents.middleware` 匯入裝飾器：
    - Node-style：`@before_agent`、`@before_model`、`@after_model`、`@after_agent`（函式簽名為 `(state: AgentState, runtime: Runtime) -> dict[str, Any] | None`）。
    - Wrap-style：`@wrap_model_call`（簽名為 `(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse`）、`@wrap_tool_call`。
    - 便利裝飾器：`@dynamic_prompt`（動態產生系統提示詞）。
- **Python 類別模式（Class-based middleware）**：
  - 繼承 `from langchain.agents.middleware import AgentMiddleware`（或泛型 `AgentMiddleware[CustomState]`）。
  - 適合同時定義同步與非同步實作（例如 `before_model` 與 `abefore_model`、`after_model` 與 `aafter_model`）、單一 middleware 包含多個鉤子、或需要 `__init__` 複雜初始化設定。
  - 編譯期可宣告三個類別屬性（Class attributes）：
    1. `state_schema`：擴充代理狀態欄位。
    2. `tools`：註冊隨附於該 middleware 的額外工具（如 `TodoListMiddleware` 的 `write_todos`）。
    3. `transformers`：註冊範圍感知（scope-aware）的串流轉換器工廠 tuple（需 `langchain>=1.3.2`）。
- **TypeScript/JavaScript `createMiddleware` 函式**：
  - 使用 `import { createMiddleware } from "langchain"`，傳入設定物件 `{ name: "...", stateSchema, contextSchema, tools, streamTransformers, beforeAgent, beforeModel, afterModel, afterAgent, wrapModelCall, wrapToolCall }`。

---

### 五、狀態更新機制與多重合成規則（State Updates & Composition）
- **Node-style hooks 狀態更新**：
  - 直接回傳 `dict` / 物件（如 `return {"model_call_count": state.get("model_call_count", 0) + 1}`），由圖形的 reducers 合併至代理狀態；若無需更新則回傳 `None` / `undefined`。
- **Wrap-style hooks 狀態更新**：
  - **工具呼叫（`wrap_tool_call` / `wrapToolCall`）**：Python 與 JS 皆直接回傳 `Command`。
  - **模型呼叫（`wrap_model_call` / `wrapModelCall`）**：
    - **Python**：必須回傳 `ExtendedModelResponse(model_response=response, command=Command(update={"last_model_call_tokens": 150}))`（從 `langchain.agents.middleware` 匯入 `ExtendedModelResponse`，從 `langgraph.types` 匯入 `Command`）。
    - **TypeScript/JavaScript**：直接從 `wrapModelCall` 回傳 `new Command({ update: { lastModelCallTokens: 150 } })`。
- **多層 `wrap_model_call` 狀態更新合成規則（Composition）**：
  - **透過 Reducers 套用**：每個 `Command` 都是獨立的狀態更新；對於 `messages` 等使用累加 reducer 的欄位，內外層新增的訊息會累加（Additive）。
  - **衝突時外層勝出（Outer wins on conflicts）**：對於無累加或採用覆寫語意（last-wins）的欄位，更新順序為「先內層（Inner）後外層（Outer）」，因此最外層（列表排在最前面）的 middleware 寫入值會覆蓋內層的值。
  - **重試安全（Retry-safe）**：若外層 middleware 實作重試邏輯並多次呼叫 `handler()`，先前失敗或被捨棄呼叫所產生的 `Command` 會被丟棄。
  - **JS 專屬訊息流穿透行為**：在 JS 中，若某層回傳的 `Command` 未修改 `messages`，框架對訊息流將其視為 pass-through（no-op），外層 `handler` 仍會收到前一層產生的 `AIMessage`。

---

### 六、自訂狀態（Custom State Schema）、私有欄位與自訂上下文（Custom Context）
- **擴充 State Schema**：
  - Python：定義繼承 `AgentState` 的類別（可搭配 `from typing_extensions import NotRequired`），透過 `@before_model(state_schema=CustomState)` 或類別屬性 `state_schema = CustomState` 指定。
  - TypeScript/JavaScript：使用 `new StateSchema({...})` 或 `z.object({...})` 傳給 `createMiddleware({ stateSchema: ... })`。
  - **JS 私有狀態欄位（Private State Fields）**：在 JS 的 `StateSchema` 中，以底線 `_` 開頭的欄位（如 `_internalFlag: z.boolean().default(false)`）視為私有欄位，在代理執行期間各 hook 皆可讀寫，但**不會包含在 `agent.invoke()` 的最終回傳結果中**（`result._internalFlag` 為 `undefined`）；未以底線開頭的公開欄位（如 `publicCounter`）則會回傳。
- **自訂執行期上下文（Custom Context）**：
  - 唯讀且不跨 invocation 持久化，適合傳遞 `userId`、`tenantId`、`apiKey` 等單次請求詮釋資料。
  - 在 JS 中將 Zod `contextSchema` 傳給 `createMiddleware` 與 `createAgent`，透過 `request.runtime.context` 讀取。若 `contextSchema` 包含必填欄位（未使用 `.optional()` 或 `.default()`），TypeScript 會在 `agent.invoke()` 時強制要求傳入 `{ context: { ... } }`。

---

### 七、代理生命週期跳轉（Agent Jumps）
- 可在節點式鉤子中提早結束或改變流程走向，需回傳包含 `"jump_to"`（Python）或 `jumpTo`（JS）的字典/物件。
- **三個合法的跳轉目標（Jump Targets）**：
  1. `'end'`：跳轉至代理執行結尾（或第一個 `after_agent` 鉤子）。
  2. `'tools'`：跳轉至工具執行節點（`tools` node）。
  3. `'model'`：跳轉至模型節點（或第一個 `before_model` 鉤子）。
- **強制宣告 `can_jump_to` / `canJumpTo`**：
  - Python：必須在裝飾器加上 `@before_model(can_jump_to=["end"])` 或使用 `@hook_config(can_jump_to=["end"])`（從 `langchain.agents.middleware` 匯入 `hook_config`）。
  - TypeScript/JavaScript：必須使用物件形式定義鉤子：`beforeModel: { canJumpTo: ["end"], hook: (state) => { return { messages: [...], jumpTo: "end" as const }; } }`。

---

### 八、自訂串流轉換器（Custom Stream Transformers）與追蹤策略（Configure Tracing）
- **自訂串流轉換器（Stream Transformers）**：
  - 用於將即時代理串流事件投影至自訂型別擴充通道（如計數器、旁路產物、串流遮罩）。編譯時內建的 `ToolCallTransformer` 永遠排在最前面，接著是 middleware 註冊的轉換器，呼叫端直接傳入的排在最後。
  - Python（需 `langchain>=1.3.2`）：在 `AgentMiddleware` 子類別設定 `transformers = (ToolActivityTransformer,)`，每個工廠型別為 `Callable[[tuple[str, ...]], StreamTransformer]`，接收 `scope` tuple（根圖為 `()`，子圖為非空 tuple）。
  - TypeScript/JavaScript（需 `langchain@1.4.3` 以上）：在 `createMiddleware` 設定 `streamTransformers: [toolActivityTransformer]`，工廠型別為無參數 `() => StreamTransformer<any>`。
- **設定追蹤策略（Configure Tracing，Python `langchain>=1.3.15`）**：
  - 預設每個 middleware hook span 都會記錄輸入與輸出。可透過 `from langchain.agents.middleware import AgentMiddleware, TracePolicy, omit_payload, configure_trace_policy` 調整。
  - 在單一 middleware 類別設定 `trace_policy = TracePolicy(process_inputs=omit_payload)`（`TracePolicy` 支援 `process_inputs` 與 `process_outputs` 可呼叫物件，`omit_payload` 會完全省略該 payload）。
  - 全域預設設定：`configure_trace_policy(TracePolicy(process_inputs=omit_payload))`（傳入 `None` 可清除全域設定；個別 middleware 的 `trace_policy` 優先於全域設定）。

---

### 九、常見實作範例（動態提示詞、Anthropic 快取、動態工具與模型）
- **動態修改 System Prompt 與 Anthropic Prompt Caching**：
  - `ModelRequest.system_message`（Python）與 `ModelRequest.systemMessage`（JS）**永遠是 `SystemMessage` 物件**（即使 `create_agent` 初始化時傳入的是字串 `system_prompt`）。
  - Python：建議透過 `list(request.system_message.content_blocks)` 取得內容區塊列表並附加新區塊（如 `{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}`），再建立新的 `SystemMessage(content=new_content)` 並呼叫 `request.override(system_message=new_system_message)`。
  - TypeScript/JavaScript：使用 `request.systemMessage.concat(...)`（可傳入字串或含 `cache_control: { type: "ephemeral", ttl: "5m" }` 內容區塊的 `new SystemMessage({...})`）以保留其他 middleware 建立的結構與快取控制詮釋資料。
- **動態篩選工具（Dynamically selecting tools）**：所有可能用到的工具都必須先在 `create_agent(tools=all_tools)` 中預先註冊，再於 `wrap_model_call` 中透過 `request.override(tools=relevant_tools)`（Python）或 `handler({ ...request, tools: relevantTools })`（JS）篩選子集。

## 相關頁面
- [[entities/langchain-builtin-middleware]]
- [[concepts/langchain-memory-and-context-engineering]]
- [[concepts/langchain-human-in-the-loop-and-guardrails]]

## 出處
- docs/langchain/middleware/overview.md
- docs/langchain/middleware/custom.md
