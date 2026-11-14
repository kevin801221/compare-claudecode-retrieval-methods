# LangGraph Overview, Quickstart, Design Thinking, and Workflows vs Agents

別名：LangGraph 概覽與工作流模式、Graph API 設計流程、Workflows 與 Agents、LangGraph 快速入門、Orchestrator-Worker 與 Evaluator-Optimizer
框架：langgraph

## 摘要
LangGraph 是針對長時間執行、具狀態代理程式（stateful agents）的低階編排框架與執行期（runtime），透過共享狀態（state）、節點（nodes）與邊（edges）定義工作流，並可在同一張圖中混用確定性步驟與 LLM 驅動步驟。本頁涵蓋 LangGraph 核心定位與安裝、計算機代理程式快速入門（Quickstart）、Graph API 的五步驟設計方法論（Thinking in the Graph API），以及常見的工作流與代理程式架構模式（Prompt chaining、Parallelization、Routing、Orchestrator-worker、Evaluator-optimizer 與 Agents）。

## 重點

### 核心定位與產品生態系（`overview.md`）
- **框架定義**：LangGraph 是低階編排框架與執行期，專注於持久化執行（durable execution / persistence）、串流（streaming）、人類介入（human-in-the-loop / interrupts）與短期／長期記憶（memory），不強制規定提示詞（prompts）或代理程式架構。不強制依賴 LangChain 即可獨立運作。
- **LangChain 產品矩陣分工**：
  - `Deep Agents`：建立在 LangGraph 之上的代理程式框架（agent harness），提供規劃（planning）、子代理（subagents）、檔案系統工具與上下文管理。
  - `LangChain`：提供模型（models）、工具（tools）與代理迴圈的抽象與整合。
  - `LangGraph`：編排執行期（orchestration runtime），負責持久化執行、串流、human-in-the-loop 與狀態持久化。
  - `LangSmith`：跨框架的追蹤（tracing）、評估（evaluation）、提示詞與部署平台（含 `LangSmith Agent Server` 與 `LangSmith Observability`）。
  - `LangSmith Engine`：偵測 LangGraph 代理追蹤紀錄中的問題並提出修復建議（可直接從 Engine 分頁開啟 Pull Request）。
  - `LangSmith Fleet`：無程式碼（no-code）代理建構器，用於範本、整合與例行自動化。
- **安裝指令**：
  - Python：`pip install -U langgraph` 或 `uv add langgraph`。
  - TypeScript/JavaScript：`npm install @langchain/langgraph @langchain/core`（支援 `npm`、`pnpm`、`yarn`、`bun`）。
- **最小圖形（Minimal Graph）Python 與 TypeScript 對照**：
  - Python：從 `langgraph.graph` 匯入 `StateGraph`、`MessagesState`、`START`、`END`。建立 `graph = StateGraph(MessagesState)`，呼叫 `graph.add_node(mock_llm)`、`graph.add_edge(START, "mock_llm")`、`graph.add_edge("mock_llm", END)`，再以 `graph = graph.compile()` 編譯並呼叫 `graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})`。
  - TypeScript/JavaScript：從 `"@langchain/langgraph"` 匯入 `StateSchema`、`MessagesValue`、`type GraphNode`、`StateGraph`、`START`、`END`。以 `const State = new StateSchema({ messages: MessagesValue })` 定義狀態，節點型別標註為 `GraphNode<typeof State>`，透過鏈式呼叫 `new StateGraph(State).addNode("mock_llm", mockLlm).addEdge(START, "mock_llm").addEdge("mock_llm", END).compile()` 並以 `await graph.invoke(...)` 執行。

### 快速入門：計算機代理程式（`quickstart.md`）
- **套件與環境變數**：
  - Python 安裝：`pip install -U langgraph langchain langchain-anthropic` 或 `uv add langgraph langchain langchain-anthropic`。
  - TypeScript/JavaScript 安裝：`npm install @langchain/langgraph @langchain/core @langchain/anthropic langchain zod`。
  - 環境變數：模型金鑰 `ANTHROPIC_API_KEY`；選用 LangSmith 追蹤需設定 `LANGSMITH_TRACING=true` 與 `LANGSMITH_API_KEY="your-langsmith-api-key"`。
- **步驟 1：定義工具與模型（Tools and Model）**：
  - 模型初始化：Python 使用 `from langchain.chat_models import init_chat_model`，呼叫 `init_chat_model("claude-sonnet-4-6", temperature=0)`；TypeScript 使用 `import { ChatAnthropic } from "@langchain/anthropic"`，呼叫 `new ChatAnthropic({ model: "claude-sonnet-4-6", temperature: 0 })`。
  - 工具定義：定義 `add`、`multiply`、`divide` 三個工具。Python 使用 `from langchain.tools import tool` 的 `@tool` 裝飾器；TypeScript 使用 `import { tool } from "@langchain/core/tools"` 搭配 `zod` 的 `z.object({ a: z.number(), b: z.number() })` schema。
  - 綁定工具：Python 使用 `model_with_tools = model.bind_tools(tools)` 並建立 `tools_by_name = {tool.name: tool for tool in tools}`；TypeScript 使用 `const modelWithTools = model.bindTools(tools)` 與 `toolsByName`。
- **步驟 2：定義狀態（State）**：
  - Python：繼承 `TypedDict` 定義 `MessagesState`，包含 `messages: Annotated[list[AnyMessage], operator.add]`（使用 `operator.add` 將新訊息附加至列表而非覆寫）與 `llm_calls: int`。
  - TypeScript：使用 `new StateSchema({ messages: MessagesValue, llmCalls: new ReducedValue(z.number().default(0), { reducer: (x, y) => x + y }) })`（需從 `"zod/v4"` 匯入 `z`）。
- **步驟 3 & 4：定義模型節點與工具節點（Model Node & Tool Node）**：
  - 模型節點（`llm_call` / `llmCall`）：將 `SystemMessage("You are a helpful assistant tasked with performing arithmetic on a set of inputs.")` 與 `state["messages"]` 傳入 `model_with_tools.invoke(...)`。Python 回傳 `{"messages": [...], "llm_calls": state.get('llm_calls', 0) + 1}`；TypeScript 因 `llmCalls` 具有累加 reducer，僅需回傳 `{ messages: [response], llmCalls: 1 }`。
  - 工具節點（`tool_node` / `toolNode`）：讀取最後一則訊息的 `tool_calls`。Python 遍歷 `state["messages"][-1].tool_calls`，以 `tools_by_name[tool_call["name"]].invoke(tool_call["args"])` 執行並封裝為 `ToolMessage(content=observation, tool_call_id=tool_call["id"])`；TypeScript 先檢查 `AIMessage.isInstance(lastMessage)`，再遍歷 `lastMessage.tool_calls ?? []`，以 `await tool.invoke(toolCall)` 取得 `ToolMessage`。
- **步驟 5 & 6：定義結束條件與建構編譯圖形（End Logic & Compile）**：
  - 條件邊函式（`should_continue` / `shouldContinue`）：Python 型別標註為 `def should_continue(state: MessagesState) -> Literal["tool_node", END]:`，若 `last_message.tool_calls` 為真則回傳 `"tool_node"`，否則回傳 `END`；TypeScript 型別標註為 `ConditionalEdgeRouter<{ InputSchema: typeof MessagesState; Nodes: "toolNode" }>`，檢查 `lastMessage.tool_calls?.length` 回傳 `"toolNode"` 或 `END`。
  - 連接與編譯：加入邊 `START -> llm_call`、條件邊 `add_conditional_edges("llm_call", should_continue, ["tool_node", END])`（TypeScript 為 `.addConditionalEdges("llmCall", shouldContinue, ["toolNode", END])`）、以及迴圈邊 `tool_node -> llm_call`，最後呼叫 `.compile()`。

### Graph API 五步驟設計思維（`thinking-in-graph-api.md`）
- **步驟 1：將工作流拆解為離散步驟（Map out your workflow as discrete steps）**：
  - 每個步驟對應一個節點（node）。固定轉移使用實線固定邊（fixed edges），執行期於節點內動態決定的路由則使用 `Command`（虛線）。
  - 客服信件代理範例節點：`Read Email`、`Classify Intent`、`Doc Search`、`Bug Track`、`Draft Reply`、`Human Review`、`Send Reply`。
- **步驟 2：識別每個步驟的工作類型（Identify what each step needs to do）**：
  - **LLM steps（LLM 步驟）**：理解、分析、生成文字或推理決策（如 `Classify intent`、`Draft reply`），需區分靜態上下文（prompt）與動態上下文（from state）。
  - **Data steps（資料步驟）**：從外部來源檢索資訊（如 `Document search`），建議啟用指數退避（exponential backoff）的重試策略（retry strategy），並可考慮快取常見查詢。
  - **Action steps（動作步驟）**：執行外部動作（如 `Send reply`、`Bug track`），需配置網路與暫時性錯誤的重試策略；`Send reply` 每次發送皆為獨立動作故不應快取（Should not cache）。
  - **User input steps（使用者輸入步驟）**：需要人類介入（如 `Human review`），於高緊急度、帳務或複雜問題時觸發，預期輸入包含核准布林值與選用的修改後回覆。
- **步驟 3：設計共享狀態（Design your state）**：
  - **納入 State 的原則**：需要跨步驟持久化的資料（原始信件與寄件者、分類結果、檢索結果或工單上下文、草稿回覆、除錯與復原用的執行中繼資料）。
  - **不納入 State 的原則**：可從現有狀態推導出的資料（於需要時即時計算）。
  - **保持狀態為原始資料（Keep state raw, format prompts on demand）**：在狀態中儲存原始資料而非格式化後的提示詞字串，在節點內部才格式化提示詞。這讓不同節點能以不同方式格式化同一份資料、修改提示詞範本時不必更動狀態 schema，且除錯時能清楚檢視每個節點收到的原始資料。
- **步驟 4：建構節點與錯誤處理策略（Build your nodes & Handle errors）**：
  - 節點錯誤分類與處理策略對照表：
    - **Transient errors（暫時性錯誤，如網路問題、速率限制）**：由系統自動修復（System automatic），在節點上配置 Retry policy。
    - **LLM-recoverable errors（LLM 可修復錯誤，如工具失敗、解析問題）**：由 LLM 修復，將錯誤存入 state 並路由回模型節點。
    - **User-fixable errors（使用者可修復錯誤，如缺少資訊、指示不清）**：由人類修復（Human），呼叫 `interrupt()` 暫停執行。
    - **Recoverable failure after retries（重試耗盡後可復原的失敗）**：由開發者定義，使用 `error_handler`（Python）／`errorHandler`（TypeScript）在重試耗盡後執行補償分支（compensation branch）。
    - **Unexpected errors（非預期錯誤）**：由開發者修復，直接讓執行失敗（Fail the run）以利修正程式碼錯誤。
- **步驟 5：串接圖形與暫停／恢復（Wire it together & Resume）**：
  - 當節點回傳 `Command` 進行路由時：Python 在節點回傳型別標註 `Command[Literal[...]]` 宣告合法目標節點；TypeScript 則在呼叫 `addNode` 時傳入 `ends` 參數告知 LangGraph 合法目的地。
  - 使用 `interrupt()` 必須在 `compile()` 時傳入 checkpointer。當執行遇到 `interrupt()` 時會暫停並儲存狀態；透過 `Command(resume=...)` 搭配相同的 `thread_id` 恢復執行時，**該節點會從頭重新執行（re-runs from the start）**，此時 `interrupt()` 會直接回傳 resume 的值，因此 `interrupt()` 之前的工作必須保持冪等（idempotent）。
- **節點粒度權衡（Node granularity trade-offs）**：
  - LangGraph 在**節點邊界（node boundaries）**建立檢查點（checkpoints）。節點越小，檢查點越密集，發生失敗或中斷恢復時需重做的重複工作越少。
  - 拆分為獨立節點的優勢：隔離外部服務（重試範圍僅限於該 API 呼叫）、可觀測性（Visibility，可在進入下一步前檢視結構化分類結果）、為不同失敗模式配置各自的 retry policy、更容易進行單元測試與重用。
  - 預設情況下檢查點會在背景非同步寫入（async durability mode），因此增加節點數量不一定會降低執行速度。

### 工作流與代理程式模式（`workflows-agents.md`）
- **核心差異**：
  - **Workflows（工作流）**：具有預先決定好的程式碼路徑（predetermined code paths），按特定順序運作。
  - **Agents（代理程式）**：具動態性，自行決定處理流程與工具使用方式，在連續回饋迴圈中運作。
- **LLM 擴充基礎（LLMs and augmentations）**：
  - 結構化輸出（Structured output）：Python 使用 Pydantic `BaseModel` 搭配 `llm.with_structured_output(SearchQuery)`；TypeScript 使用 `zod` schema 搭配 `llm.withStructuredOutput(SearchQuery)`。
  - 工具綁定（Tool calling）：Python 使用 `llm.bind_tools([multiply])`；TypeScript 使用 `llm.bindTools([multiply])`。
- **模式 1：Prompt chaining（提示詞串接）**：
  - 每個 LLM 呼叫處理前一個呼叫的輸出，適用於可拆解為較小、可驗證步驟的任務（如文件多語翻譯、驗證生成內容的一致性）。
  - 範例結構：`START -> generate_joke`，接著透過條件邊閘門函式 `check_punchline`（檢查笑話是否包含 `"?"` 或 `"!"`）分流為 `"Pass"` 或 `"Fail"`，後續串接 `improve_joke -> polish_joke -> END`。
  - 視覺化方法：`chain.get_graph().draw_mermaid_png()`。
- **模式 2：Parallelization（平行化）**：
  - 多個 LLM 同時處理任務：可將獨立子任務拆開平行執行以提升速度，或將同一任務重複執行多次以檢查不同輸出並提升信心（例如同時檢查關鍵字與格式錯誤，或多維度評分）。
  - 範例結構：從 `START` 同時連接三條固定邊至 `call_llm_1`、`call_llm_2`、`call_llm_3`，三個節點再各自連接固定邊至匯聚節點 `aggregator`，最後由 `aggregator` 連至 `END`。
- **模式 3：Routing（路由分流）**：
  - 先處裡輸入再將其導向特定上下文的專屬流程（如根據產品問題類型導向定價、退款、退貨流程）。
  - 範例結構：使用 `llm.with_structured_output(Route)`（`step: Literal["poem", "story", "joke"]`）作為 `llm_call_router` 節點，將決策寫入 `state["decision"]`，再由條件邊函式 `route_decision` 路由至 `llm_call_1`、`llm_call_2` 或 `llm_call_3`。
- **模式 4：Orchestrator-worker（編排器－工作者）**：
  - 編排器（Orchestrator）負責將任務拆解為子任務、委派給工作者（Workers）、最後將工作者輸出合成為最終結果（Synthesizer）。適用於無法像平行化那樣預先定義子任務數量的情境（如跨未知數量的檔案撰寫程式碼或更新多個函式庫文件）。
  - **`Send` API 動態建立工作者**：
    - 匯入：Python 為 `from langgraph.types import Send`；TypeScript 為 `import { Send } from "@langchain/langgraph"`。
    - 狀態設計：主圖狀態 `State` 與工作者狀態 `WorkerState` 各自獨立，但共享帶有累加 reducer 的鍵 `completed_sections: Annotated[list, operator.add]`（TypeScript 為 `completedSections: new ReducedValue(z.array(z.string()).default(() => []), { reducer: (a, b) => a.concat(b) })`），讓所有平行執行的工作者將結果寫入同一個共享鍵。
    - 派發邏輯：條件邊函式 `assign_workers` 回傳 `[Send("llm_call", {"section": s}) for s in state["sections"]]`（TypeScript 為 `state.sections.map((section) => new Send("llmCall", { section }))`），之後由 `llm_call` 連接固定邊至 `synthesizer` 進行彙整。
- **模式 5：Evaluator-optimizer（評估器－最佳化器）**：
  - 一個 LLM 呼叫負責產生回應（`llm_call_generator`），另一個使用結構化輸出的 LLM（`llm_call_evaluator`，回傳 `grade: Literal["funny", "not funny"]` 與 `feedback: str`）或 human-in-the-loop 評估回應。若需改進（`"Rejected + Feedback"`），則攜帶 `feedback` 路由回生成節點重新產生，直到符合標準（`"Accepted"` -> `END`）。
- **模式 6：Agents（自主代理程式）與 `ToolNode`**：
  - 由模型節點（`llm_call`）與工具執行節點（`tool_node`）構成迴圈，透過 `should_continue` 檢查 `last_message.tool_calls` 決定繼續呼叫工具或結束（`END` / `"__end__"`）。可呼叫 `agent.get_graph(xray=True).draw_mermaid_png()` 展開檢視內部圖結構。
  - **預建 `ToolNode`**：
    - 匯入：Python 為 `from langgraph.prebuilt import ToolNode`；TypeScript 為 `import { ToolNode } from "@langchain/langgraph/prebuilt"`。
    - 功能：自動處理平行工具執行（parallel tool execution）、錯誤處理（error handling）與狀態注入（state injection）。
    - **從工具內存取圖形狀態與執行期上下文（Access graph state and context from tools）**：`ToolNode` 執行的工具第一個參數為模型產生的參數；若需讀取非模型產生的圖形端資料（state 與 run-scoped context），Python 使用注入的 `ToolRuntime` 參數，JavaScript/TypeScript 則從工具的第二個參數（型別為 `ToolRuntime`）讀取。
    - **手動呼叫 `ToolNode` 的注意事項**：工具只能存取傳遞給 `ToolNode` 的狀態值。當 `ToolNode` 直接作為 `StateGraph` 節點時會收到完整圖狀態；若在其他節點內手動呼叫 `tool_node.invoke(state)`（或 JS 的 `toolNode.invoke(state, config)`），必須傳入完整 `state` 才能讓工具讀取自訂狀態欄位（若只傳入 `{"messages": state["messages"]}` 則工具只能存取 `messages`）。

## 相關頁面
- [[concepts/langgraph-graph-api-state-and-nodes]]
- [[concepts/langgraph-control-flow-send-and-command]]
- [[concepts/langgraph-functional-api-and-pregel]]
- [[entities/langgraph-error-codes]]

## 出處
- docs/langgraph/overview.md
- docs/langgraph/quickstart.md
- docs/langgraph/thinking-in-graph-api.md
- docs/langgraph/workflows-agents.md
