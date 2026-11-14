# LangChain Multi-Agent Subagents and Supervisor Pattern

別名：子代理與監督者模式、Subagents Pattern、Supervisor Architecture、Agent-as-a-Tool、階層式代理編排
框架：langchain

## 摘要
在 **Subagents（子代理）** 架構中，一個中央主代理（Main agent，常稱為 **Supervisor**）透過將子代理包裝為工具（Tools）進行調用與協調。預設情況下子代理為無狀態（Stateless），所有對話記憶由主代理維護，藉此讓每次子代理調用都在乾淨的上下文視窗中執行，達成強大的上下文隔離（Context isolation）並防止主對話上下文膨脹。開發者亦可透過 `ToolRuntime`（Python）或 `getCurrentTaskInput`（TypeScript）自訂傳入子代理的上下文，或搭配 `HumanInTheLoopMiddleware` 與頂層 Checkpointer 在子代理工具呼叫上實作人工審核（HITL）。

## 重點
- **核心特性與與 Router 的差異**：
  - **Centralized control（集中控制）**：所有路由皆經過主代理。
  - **No direct user interaction（無直接使用者互動）**：子代理將結果回傳給主代理而非直接對使用者說話（但可在子代理內部使用 `interrupt` 暫停執行並收集使用者輸入）。
  - **Subagents via tools（透過工具調用）** 與 **Parallel execution（平行執行）**：主代理可在單一輪次（Single turn）中同時調用多個子代理。
  - **Supervisor vs. Router**：Supervisor 是完整的代理，會維護跨多輪的對話上下文並動態決定調用哪些子代理；Router 則通常是單一分類步驟，分發任務給代理而不維護持續的對話狀態。
  - `langgraph-supervisor` 套件已不再積極維護（No longer actively maintained），官方建議從 `create_supervisor` 遷移至 Subagents 模式。
- **同步與非同步執行（Sync vs. Async）**：
  - **Synchronous（預設，阻塞式）**：主代理等待每個子代理完成後才繼續。適用於主代理下一步依賴子代理結果、任務有順序依賴，或子代理失敗應阻斷回應的情境。缺點是長任務會凍結對話。
  - **Asynchronous（背景執行，非指 Python `async`/`await`）**：當子代理工作獨立、不需阻塞主對話時使用。採用 **Three-tool pattern（三工具模式）**：
    1. **Start job**（如 `run_agent("legal_reviewer", task)`）：啟動背景任務並立即回傳 `job_id`（如 `"job_123"`）。
    2. **Check status**（如 `check_status(job_id)`）：回傳當前狀態（`pending`、`running`、`completed`、`failed`）。
    3. **Get result**（如 `get_result(job_id)`）：取回完成後的結果。當背景工作完成時，應用程式可推播通知，點擊後發送如 `"Check job_123 and summarize the results."` 的 `HumanMessage`。
- **工具暴露模式（Tool patterns）**：
  - **Tool per agent（每代理一工具）**：將每個子代理各自包裝為獨立 `@tool`（如 `@tool("subagent_name", description="subagent_description")`），可精細控制各子代理的輸入與輸出。Python 取 `result["messages"][-1].content`（或 `.text`），TypeScript 取 `result.messages.at(-1)?.content`（或 `.text`）。
  - **Single dispatch tool（單一分發工具）**：使用單一參數化工具 `task(agent_name: str, description: str) -> str`（TypeScript 為 `task({ agentName, description })`）從註冊字典 `SUBAGENTS = {"research": research_agent, "writer": writer_agent}` 調用短暫（Ephemeral）子代理。遵循慣例優於組態（Convention over configuration），適合跨團隊分散開發、擴充新代理而不修改協調器，或單純為了**上下文隔離**而調用與主代理具備相同能力的子代理。
- **上下文工程（Context engineering）**：
  - **1. Subagent specs（子代理規格與探索機制）**：
    - 透過清晰的 **Name**（動作導向，如 `research_agent`、`code_reviewer`）與具體的 **Description** 引導主代理路由。
    - 在 Single dispatch tool 模式下有三種揭露可用子代理的方式：
      - **System prompt enumeration**：直接在主代理 `system_prompt` 列出代理清單，適合小型靜態清單（`< 10` 個代理）。
      - **Enum constraint**：在 Python 使用 `class AgentName(str, Enum):` 限制 `task(agent_name: AgentName, description: str)` 的參數型別，適合 `< 10` 個代理且追求型別安全與 Schema 驗證。
      - **Tool-based discovery**：提供額外探索工具如 `list_agents(query: str = "") -> str` 按需搜尋註冊表（Progressive disclosure），適合大型（`> 10` 個代理）或動態變動的註冊表。
  - **2. Subagent inputs（子代理輸入：Isolated vs. Forked）**：
    - **Isolated mode（預設，Deep Agents 中為 `mode: "isolated"`）**：僅傳入任務描述 `query`，完全隔離但會重新推導父代理已做過的事。
    - **Forked mode（Deep Agents 中為 `mode: "fork"`）**：將父代理的完整訊息歷史（及系統提示詞）傳入子代理，適合接續父代理已開始的工作（如繼續 PR review 或修 bug）。
    - 實作方式：
      - Python：定義 `class CustomState(AgentState): example_state_key: str`，在工具參數注入 `runtime: ToolRuntime[None, CustomState]`，從 `runtime.state["messages"]` 與 `runtime.state["example_state_key"]` 讀取狀態並傳入 `subagent1.invoke(...)`。
      - TypeScript：呼叫 `const state = getCurrentTaskInput<AgentState>()`（或 `getCurrentTaskInput<BuiltInState>(config)`）讀取 `state.messages` 與 `state.exampleStateKey`。
  - **3. Subagent outputs（子代理輸出控制）**：
    - **Prompt the sub-agent**：在子代理系統提示詞中明確要求最終訊息必須包含所有關鍵結果（常見失敗模式：子代理執行了工具呼叫卻未將結果寫入最終訊息，導致只看最後一則訊息的 Supervisor 遺失資訊）。
    - **Format in code（程式碼格式化或回傳 `Command`）**：可回傳 `json.dumps({...})` 結構化字串，或回傳 LangGraph `Command` 同時更新主代理的多個狀態鍵：
      - Python：工具參數加入 `tool_call_id: Annotated[str, InjectedToolCallId]`，回傳 `Command(update={"example_state_key": result["example_state_key"], "messages": [ToolMessage(content=result["messages"][-1].content, tool_call_id=tool_call_id)]})`。
      - TypeScript：工具第二參數接收 `config`，回傳 `new Command({ update: { exampleStateKey: result.exampleStateKey, messages: [new ToolMessage({ content: result.messages.at(-1)?.text, tool_call_id: config.toolCall?.id! })] } })`。
- **Checkpointing 與狀態檢視限制**：
  - 預設子代理使用 **inherited checkpointer（繼承檢查點）** 模式：每次調用從全新狀態開始、支援 interrupts，且可安全地平行執行。若需子代理跨調用維持自身持久對話歷史，編譯時需設定 `checkpointer=True`（continuations 模式）。
  - **靜態探索限制**：由於子代理是在工具函式（Tool functions）內部被呼叫，LangGraph 無法靜態探索（Statically discover）它們，因此使用 `get_state` 搭配 `subgraphs` 將**不會**回傳子代理狀態。若需在 interrupt 期間讀取巢狀圖狀態，應改在自訂圖的節點函式（Node function）內呼叫子代理。
- **Personal Assistant 實戰教學（Calendar + Email + HITL）**：
  - **三層式架構**：底層為需要精確格式的 API 工具（`create_calendar_event`、`get_available_time_slots`、`send_email`）；中層為理解自然語言並轉換為結構化 API 呼叫的專業子代理（`calendar_agent`、`email_agent`）；頂層為包裝子代理為高階工具（`schedule_event`、`manage_email`）並負責跨領域協調的 `supervisor_agent`。
  - **串流檢視（`stream_events` v3）**：
    - Python：`stream = supervisor_agent.stream_events({"messages": [...]}, version="v3")`，搭配 `for kind, item in stream.interleave("messages", "tool_calls"):` 處理 `item.text`、`item.tool_name`、`item.input`、`item.output`。
    - TypeScript：`const stream = await supervisorAgent.streamEvents({ messages: [...] }, { version: "v3" })`，並以 `for await (const message of stream.messages)` 與 `for await (const call of stream.toolCalls)` 平行消費。
  - **整合 Human-in-the-Loop（人工審核）**：
    - 在子代理上掛載 Middleware：Python 使用 `from langchain.agents.middleware import HumanInTheLoopMiddleware`（設定 `interrupt_on={"create_calendar_event": True}` 與 `description_prefix="Calendar event pending approval"`，以及 `interrupt_on={"send_email": True}` 與 `description_prefix="Outbound email pending approval"`）；TypeScript 使用 `import { humanInTheLoopMiddleware } from "langchain"`（設定 `interruptOn` 與 `descriptionPrefix`）。
    - **Checkpointer 僅加在頂層 Supervisor**：Python 在 `supervisor_agent` 設定 `checkpointer=InMemorySaver()`（來自 `langgraph.checkpoint.memory`）；TypeScript 設定 `checkpointer: new MemorySaver()`（來自 `@langchain/langgraph`）。
    - **攔截與恢復（Interrupt & Resume）**：
      - 執行時傳入 `config = {"configurable": {"thread_id": "6"}}`。若 `stream.interrupted` 為真，遍歷 `stream.interrupts`：Python 取 `interrupt_.id` 與 `interrupt_.value["action_requests"]`；TypeScript 取 `interrupt.interruptId` 與 `interrupt.payload.actionRequests`。
      - 由於每次執行的 Interrupt ID 都會改變，需先比對 `action_request["name"]`（如 `"send_email"`），再以 Interrupt ID 為鍵建立 `resume` 字典：核准為 `{"decisions": [{"type": "approve"}]}`，修改為 `{"decisions": [{"type": "edit", "edited_action": {"name": ..., "args": ...}}]}`（TypeScript 鍵名為 `editedAction`）。
      - 最後將 `Command(resume=resume)`（TypeScript 為 `new Command({ resume })`）與相同 `config` 傳入 `supervisor_agent.stream_events(...)` 恢復執行。

## 相關頁面
- [[concepts/langchain-multi-agent-overview]]
- [[concepts/langchain-multi-agent-handoffs]]
- [[concepts/langchain-multi-agent-router-and-skills]]

## 出處
- docs/langchain/multi-agent/subagents.md
- docs/langchain/multi-agent/subagents-personal-assistant.md
