# LangChain Multi-Agent Handoffs and State Machine Pattern

別名：代理移交與狀態機模式、Handoffs Pattern、State Machine Pattern、Agent Transfer、狀態驅動路由
框架：langchain

## 摘要
在 **Handoffs（移交）** 架構（亦稱為 **State Machine Pattern**）中，代理的行為會根據跨輪次持久化的狀態變數（如 `current_step` 或 `active_agent`）動態改變。核心機制是由工具（Tools）回傳 LangGraph `Command` 物件來更新狀態變數，系統再依據該變數調整當前代理的組態（透過單一代理搭配 `@wrap_model_call`／`createMiddleware` 動態覆寫系統提示詞與可用工具）或路由至不同的子圖代理節點（搭配 `Command.PARENT` 與 `goto`）。此模式讓每個狀態都能直接與使用者對話，特別適合客服等需強制執行序列限制（先收集保固狀態、再分類問題、最後提供解決方案）的多階段對話流程。

## 重點
- **核心特性與適用情境**：
  - **名詞來源**：Handoffs 一詞源自 OpenAI，指利用工具呼叫（如 `transfer_to_sales_agent`）在代理或狀態之間轉移控制權。
  - **四大特徵**：State-driven behavior（由 `current_step` 或 `active_agent` 驅動行為）、Tool-based transitions（工具更新狀態變數以切換狀態）、Direct user interaction（每個狀態組態直接處理使用者訊息）、Persistent state（透過 Checkpointer 讓狀態跨對話輪次留存）。
  - **為何必須包含 `ToolMessage`**：當 LLM 呼叫工具時，預期會收到對應回應；每次 handoff 工具更新 `messages` 時，都必須附上帶有相符 `tool_call_id`（Python 為 `runtime.tool_call_id`；TypeScript 為 `config.toolCallId` 或 `runtime.toolCallId`）的 `ToolMessage`，否則對話歷史將格式錯誤（Malformed）。
- **兩種實作途徑比較（Implementation approaches）**：
  - **1. Single agent with middleware（單一代理搭配中介軟體，大多數情境首選）**：
    - 單一代理透過 Middleware 攔截每次模型呼叫，根據 `current_step` 動態調整系統提示詞與可用工具。
    - **Python 實作**：
      - 定義狀態：`class SupportState(AgentState): current_step: str = "triage"; warranty_status: str | None = None`。
      - 工具回傳 `Command(update={"messages": [ToolMessage(content=..., tool_call_id=runtime.tool_call_id)], "warranty_status": status, "current_step": "specialist"})`。
      - 使用 `@wrap_model_call` 裝飾器定義 `apply_step_config(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse`，由 `step = request.state.get("current_step", "triage")` 取得當前步驟，再呼叫 `request = request.override(system_prompt=config["prompt"].format(**request.state), tools=config["tools"])` 並回傳 `handler(request)`。
      - 建立代理：`create_agent(model, tools=[...], state_schema=SupportState, middleware=[apply_step_config], checkpointer=InMemorySaver())`。
    - **TypeScript 實作**：
      - 定義狀態：`const SupportState = new StateSchema({ currentStep: z.string().default("triage"), warrantyStatus: z.string().optional() })`。
      - 工具回傳 `new Command({ update: { messages: [new ToolMessage({ content: ..., tool_call_id: config.toolCallId })], warrantyStatus: status, currentStep: "specialist" } })`。
      - 使用 `createMiddleware({ name: "applyStepConfig", stateSchema: SupportState, wrapModelCall: async (request, handler) => { ... return handler({ ...request, systemPrompt: config.prompt, tools: config.tools }); } })`。
      - 建立代理：`createAgent({ model, tools: [...], middleware: [applyStepConfig], checkpointer: new MemorySaver() })`。
  - **2. Multiple agent subgraphs（多重代理子圖，僅在節點本身是含反思或檢索的複雜圖時使用）**：
    - 不同代理作為 `StateGraph` 中的獨立節點（如 `"sales_agent"` 與 `"support_agent"`），狀態 schema 為 `class MultiAgentState(AgentState): active_agent: NotRequired[str]`（TypeScript 為 `new StateSchema({ messages: MessagesValue, activeAgent: z.string().optional() })`）。
    - **跨子圖跳轉（`Command.PARENT`）**：Handoff 工具（如 `transfer_to_sales`、`transfer_to_support`）回傳 `Command(goto="sales_agent", update={"active_agent": "sales_agent", "messages": [last_ai_message, transfer_message]}, graph=Command.PARENT)`。
    - **上下文工程（Context engineering）關鍵規則**：在子圖移交時，不能把子代理全部內部對話歷史塞給父圖（會造成接收端混淆與 Token 浪費），但**必須成對傳遞兩則訊息**：
      1. 觸發此次 handoff 工具呼叫的 `last_ai_message`（從 `reversed(runtime.state["messages"])` 找到的最後一則 `AIMessage`，或無平行工具呼叫時的 `runtime.state["messages"][-1]`）。
      2. 帶有對應 `tool_call_id` 的人工 `ToolMessage`（`transfer_message`）。
      - 當結束回合將控制權交還使用者時，最終訊息必須是 `AIMessage`（且無 `tool_calls`）。
    - **圖路由設計**：
      - `route_initial(state: MultiAgentState)`：從 `START` 根據 `state.get("active_agent") or "sales_agent"` 進行初始條件路由。
      - `route_after_agent(state: MultiAgentState)`：檢查 `messages[-1]`，若為 `isinstance(last_msg, AIMessage) and not last_msg.tool_calls`（TypeScript 為 `lastMsg instanceof AIMessage && !lastMsg.tool_calls?.length`），則回傳 `"__end__"` / `END`；否則路由至 `state.get("active_agent", "sales_agent")`。
- **Customer Support 狀態機實戰教學（三階段客服工作流）**：
  - **工作流階段（`SupportStep`）**：
    1. `"warranty_collector"`（預設起始步驟）：向客戶問候並詢問設備是否在保固內，僅開放工具 `[record_warranty_status]`，`requires: []`。
    2. `"issue_classifier"`：注入已知 `{warranty_status}`，詢問問題描述並判斷為硬體（物理損壞、零件破裂）或軟體（應用程式崩潰、效能問題），僅開放工具 `[record_issue_type]`，`requires: ["warranty_status"]`（TypeScript 為 `["warrantyStatus"]`）。
    3. `"resolution_specialist"`：注入 `{warranty_status}` 與 `{issue_type}`，軟體問題呼叫 `provide_solution` 提供排錯步驟；硬體問題若在保固內（`in_warranty`）呼叫 `provide_solution` 說明保固維修流程，若過保（`out_of_warranty`）則呼叫 `escalate_to_human` 轉交人工處理付費維修選項。開放工具 `[provide_solution, escalate_to_human]`，`requires: ["warranty_status", "issue_type"]`（TypeScript 為 `["warrantyStatus", "issueType"]`）。
  - **狀態 Schema 與工具型別限制**：
    - Python：`SupportStep = Literal["warranty_collector", "issue_classifier", "resolution_specialist"]`；`warranty_status: NotRequired[Literal["in_warranty", "out_of_warranty"]]`；`issue_type: NotRequired[Literal["hardware", "software"]]`。
    - TypeScript：`SupportStepSchema = z.enum(["warranty_collector", "issue_classifier", "resolution_specialist"])`；`WarrantyStatusSchema = z.enum(["in_warranty", "out_of_warranty"])`；`IssueTypeSchema = z.enum(["hardware", "software"])`。
  - **相依性檢查（Dependency Validation）**：在 `apply_step_config` / `applyStepMiddleware` 中遍歷 `STEP_CONFIG[current_step]["requires"]`，若 `request.state.get(key) is None`（TypeScript 為 `request.state[key] === undefined`），拋出 `ValueError(f"{key} must be set before reaching {current_step}")` / `new Error(...)`。
  - **壓縮對話歷史（Manage message history）**：隨著步驟推進，訊息歷史不斷增長，可在 `middleware` 陣列中串接 `SummarizationMiddleware`：
    - Python：`SummarizationMiddleware(model="gpt-5.4-mini", trigger=("tokens", 4000), keep=("messages", 10))`。
    - TypeScript：`new SummarizationMiddleware({ model: "gpt-5.4-mini", trigger: { tokens: 4000 }, keep: { messages: 10 } })`。
  - **退回上一步驟修正資訊（Go back tools）**：
    - 定義 `go_back_to_warranty() -> Command`（回傳 `Command(update={"current_step": "warranty_collector"})`）與 `go_back_to_classification() -> Command`（回傳 `Command(update={"current_step": "issue_classifier"})`），並將這兩個工具加入 `STEP_CONFIG["resolution_specialist"]["tools"]` 中，讓使用者說出 `"Actually, I made a mistake - my device is out of warranty"` 時能自動退回重啟保固驗證步驟。

## 相關頁面
- [[concepts/langchain-multi-agent-overview]]
- [[concepts/langchain-multi-agent-subagents]]
- [[concepts/langchain-multi-agent-router-and-skills]]

## 出處
- docs/langchain/multi-agent/handoffs.md
- docs/langchain/multi-agent/handoffs-customer-support.md
