# LangGraph Control Flow: Edges, Branches, Loops, Send, and Command

別名：LangGraph 控制流、Edges 與 Conditional Edges、Parallel Branches、Defer 延遲執行、Loops 與 Recursion Limit、RemainingSteps、Send API、Command API
框架：langgraph

## 摘要
LangGraph 的控制流決定工作如何在節點之間傳遞，支援序列（sequences）、平行分支（parallel branches）、條件分支（conditional branching）、迴圈（loops）、Map-Reduce 動態展開（`Send`）以及將狀態更新與路由合而為一的 `Command`。本頁詳述固定邊與條件邊、不等長平行分支的延遲執行（`defer` 與列表起點邊的差異）、超步交易性與最大並行數限制、迴圈終止與遞迴步數管理（`GraphRecursionError`、`RemainingSteps`），以及 `Send` 與 `Command` 在節點、子圖、工具與中斷恢復中的完整行為規範。

## 重點

### 序列與邊的種類（`graph-api-control-flow.md`、`graph-api.md`）
- **四種邊的型態**：
  1. **Normal edges（一般固定邊）**：使用 `add_edge`（Python）或 `addEdge`（TypeScript），永遠從來源節點走向目標節點。
  2. **Conditional edges（條件邊）**：使用 `add_conditional_edges`（Python）或 `addConditionalEdges`（TypeScript），在來源節點執行完後呼叫路由函式（routing function）決定下一個（或多個）目標節點。路由函式接收當前狀態，可回傳單一節點名稱、`END`、節點名稱列表（平行 fan-out）或 `Send` 物件列表；亦可傳入字典將路由函式的回傳值映射至目標節點名稱。
  3. **Entry point（進入點）**：從虛擬節點 `START`（或 `"__start__"`）連接固定邊至第一個執行的節點。
  4. **Conditional entry point（條件進入點）**：從 `START` 呼叫 `add_conditional_edges` / `addConditionalEdges`，根據自訂邏輯動態決定起始節點。
- **序列簡寫（Python `add_sequence`）**：
  - Python（自 `langgraph>=0.2.46` 起）提供 `.add_sequence([step_1, step_2, step_3])` 簡寫，可自動依序新增節點與固定邊，再接上 `builder.add_edge(START, "step_1")`。
- **靜態邊與動態路由不可混用警告**：
  - 對於同一個節點，請只使用靜態邊（`add_edge` / `addEdge`）**或**動態路由（條件邊／`Command`），切勿同時混用。在回傳 `Command` 的節點（或呼叫回傳 `Command` 工具的節點）上若同時定義了靜態邊，兩條路徑都會被執行！

### 平行分支、例外處理與延遲執行（`graph-api-control-flow.md`）
- **平行執行與狀態合併順序**：
  - 當一個節點有多條連出邊時，所有目標節點會在下一個 super-step 中**平行（concurrently）執行**。
  - 若平行分支同時寫入同一個狀態鍵，必須為該鍵配置 reducer（如 `operator.add` 或 `ReducedValue`）以累加值。
  - **排序注意事項**：來自同一個平行 super-step 的更新順序**不保證一致**；若需要固定且可預測的順序，應將各分支輸出寫入獨立欄位並附上排序依據的值，之後再排序合併。
- **超步交易性（Transactional Supersteps）與平行例外處理**：
  - 平行分支所在的 super-step 具備**交易性（transactional）**：若同一個 super-step 中的**任何一個分支拋出未捕捉例外**，該 super-step 中**所有分支的狀態更新都不會被套用**！
  - 若搭配 checkpointer，在已完成的先前 super-step 中成功執行的節點結果已儲存，恢復執行時不會重跑；若在節點上配置 `RetryPolicy`，則**只有失敗的分支會進行重試**，同一個 super-step 中已成功的兄弟分支（siblings）不會重跑。
- **最大並行數限制（Max concurrency）**：
  - 在呼叫圖形時，於頂層 config 鍵（切勿放在 `configurable` 下）傳入 `max_concurrency`（Python，`RunnableConfig`）或 `maxConcurrency`（TypeScript，`LangGraphRunnableConfig`）以限制同時執行的平行任務上限。
- **不等長分支的匯聚與延遲執行（Defer node execution）**：
  - 當平行分支的步數長度不同時（例如分支 B 有 `b -> b_2` 兩步，而分支 C 只有 `c` 一步，兩者皆連向匯聚節點 `d`），LangGraph 提供三種不同的連接與等待行為：
    1. **Separate edges（分開呼叫 `add_edge("b_2", "d")` 與 `add_edge("c", "d")` 且無 `defer`）**：每當任何一條進入分支在某個 super-step 完成時，`d` 就會執行一次。當分支等長時 `d` 只跑一次；但**當分支不等長時，`d` 會被執行超過一次**！
    2. **A list of start nodes（列表形式起點邊：`add_edge(["b_2", "c"], "d")`）**：這**不是**兩次獨立 `add_edge` 的語法糖！它會等待列表中的**所有**節點都完成後，才執行 `d` 一次。**關鍵陷阱**：如果列表中有任何一個節點從未執行（例如前方的條件邊沒有選中該分支），則 **`d` 永遠不會執行，且不會拋出任何錯誤**（已完成分支的狀態更新仍會留在圖狀態中，但 `d` 不會消費它們）。僅適用於所有分支永遠都會執行的情況。
    3. **Separate edges with `defer=True` / `{ defer: true }`（在 `add_node("d", d, defer=True)` 或 `addNode("d", d, { defer: true })` 設定延遲）**：會將節點 `d` 推遲到**整張圖中沒有任何待處理任務（pending tasks）**時才執行一次，無論前方的 fan-out 選中了全部分支或僅選中部分分支皆能正常運作。（註：直接指定給該節點的 `Send` 仍會獨立觸發執行）。

### 迴圈、遞迴限制與計數器存取（`graph-api-control-flow.md`）
- **迴圈與終止條件**：
  - 迴圈通常透過條件邊在滿足終止條件時路由至 `END`（或 `"__end__"`）來停止（類似 ReAct agent 在模型節點與工具節點間交替執行）。
- **設定遞迴限制（Impose a recursion limit）**：
  - 在 `invoke` / `stream` 的頂層 config 中傳入 `{"recursion_limit": N}`（Python）或 `{ recursionLimit: N }`（TypeScript）。
  - 注意單位是 **super-steps**（例如 `A -> B -> (C, D 平行) -> A`，一圈共包含 3 個節點階段，設定 limit 為 4 時走完一圈回到 A 即達 4 個 super-steps，下一步觸發 `GraphRecursionError`）。
- **存取執行步數中繼資料與 `RemainingSteps`**：
  - 節點可從執行中繼資料讀取當前步數 `langgraph_step`，相關中繼資料鍵還包含：`langgraph_node`、`langgraph_triggers`、`langgraph_path`、`langgraph_checkpoint_ns`。
  - **主動式（Proactive）vs 被動式（Reactive）遞迴處理**：
    - **Proactive（`RemainingSteps`，僅限 Python）**：Python 專屬的受管值（managed value，標註於 State 中如 `remaining_steps: RemainingSteps`），代表距離觸發 recursion limit 還剩下多少步。可在達到限制前於圖形內部透過條件邊主動路由至收尾完成路徑（例如 `if state["remaining_steps"] <= 2: return END`）。**TypeScript 沒有對應 `RemainingSteps` 的功能**。
    - **Reactive（捕捉 `GraphRecursionError`）**：在達到限制後由圖形外部的 `try` / `except`（或 `try` / `catch`）捕捉例外，此時圖形執行已停止。
- **非同步執行（Async）**：
  - Python：將節點改為 `async def`、內部使用 `await`，並以 `.ainvoke` 或 `.astream` 呼叫。
  - TypeScript：節點與 `graph.invoke` / `graph.stream` 原生即為 async，直接在呼叫端 `await` 即可，沒有獨立的 `.ainvoke` API。

### 使用 `Send` 進行 Map-Reduce 動態展開（`graph-api-send-command.md`、`graph-api.md`）
- **核心用途與與一般邊的差異**：
  - 一般邊（Normal / Conditional edges）只能選擇下一個要執行的節點，且被選中的節點接收的都是相同的共享圖形狀態（shared graph state），拓樸在建構時即固定。
  - 當需要在執行期根據動態數量的清單項目，對每個項目各執行一次同一個節點、且**每次呼叫傳入各自獨立的輸入狀態**時（即 Map-Reduce 或 Orchestrator-Worker 模式），必須從**條件邊函式**回傳一個或多個 `Send` 物件。
- **`Send` 語法與狀態隔離**：
  - Python：`Send(node_name, arg_dict)`（如 `[Send("generate_joke", {"subject": s}) for s in state["subjects"]]`）。
  - TypeScript：`new Send(nodeName, argObject)`（如 `state.subjects.map((subject) => new Send("generateJoke", { subject }))`）。
  - 工作者節點（worker node）**不會**收到完整的共享圖形狀態，而是只收到 `Send` 第二個參數傳入的字典／物件（因此工作者的輸入 schema 可以包含不在主圖整體狀態中的鍵，如 `subject`）。當所有平行工作者將結果寫回主圖共享狀態鍵（如 `jokes`）時，主圖該鍵必須配置 reducer（如 `operator.add`）以合併所有工作者的輸出。

### 使用 `Command` 結合狀態更新與動態路由（`graph-api-send-command.md`、`graph-api.md`）
- **何時使用 `Command` vs Conditional Edges**：
  - 若只需要路由而不需要更新狀態，優先使用條件邊（conditional edges）。
  - 當單一步驟必須**同時更新狀態並決定下一個節點**、從 `interrupt()` 恢復執行、或從工具（tool）內部更新圖形狀態／路由時，使用 `Command`。
- **`Command` 四大參數與三大使用位置**：
  - 四大屬性：
    - `update`：狀態更新字典／物件（等同一般節點的回傳值）。
    - `goto`：下一個目標節點名稱（或名稱列表）。
    - `graph`：從子圖導航至父圖時設為 `Command.PARENT`。
    - `resume`：在 `interrupt()` 後恢復執行時傳入的值。
  - **位置 1：從節點回傳（Return from nodes）**：
    - Python：回傳 `Command(update={...}, goto="node_b")`。**必須**在節點函式回傳型別標註所有可能的目的地，例如 `def node_a(state: State) -> Command[Literal["node_b", "node_c"]]:`，這是圖形視覺化渲染與驗證合法邊所必需的宣告。
    - TypeScript：回傳 `new Command({ update: {...}, goto: "nodeB" })`。**必須**在 `addNode` 時傳入 `ends` 選項（如 `.addNode("nodeA", nodeA, { ends: ["nodeB", "nodeC"] })`）以宣告合法目的地供圖形渲染。
  - **位置 2：從子圖導航至父圖節點（Navigate to a node in a parent graph）**：
    - 在子圖節點內回傳 `Command(update={...}, goto="node_b", graph=Command.PARENT)`（TypeScript 為 `new Command({ update: {...}, goto: "nodeB", graph: Command.PARENT })`）。
    - **跨圖狀態更新限制**：當子圖節點透過 `Command.PARENT` 更新一個**同時存在於父圖與子圖 state schema 的狀態鍵**時，**必須在父圖（parent graph）為該鍵定義 reducer**！
  - **位置 3：在工具內部使用（Use inside tools）**：
    - 工具可回傳 `Command(update={...})` 在對話回合中直接寫入圖形狀態（如寫入查詢到的客戶資訊 `user_info`）。
    - **工具回傳 `Command` 的強制規定**：在 `Command.update` 中**必須包含 `messages`（或儲存對話歷史的狀態鍵），且該列表中必須包含一則對應 `tool_call_id` 的 `ToolMessage`**！因為 LLM 供應商強制要求帶有 tool calls 的 AI 訊息後面必須緊接著工具結果訊息。建議搭配預建的 `ToolNode` 使用（會自動將工具回傳的 `Command` 傳播至圖狀態；若使用自訂工具節點則需自行處理傳播）。
  - **位置 4：作為 `invoke` 或 `stream` 的輸入以恢復中斷（Resume after an interrupt）**：
    - `Command(resume=...)`（JS 為 `new Command({ resume: ... })`）是**唯一**應作為 `invoke()` / `stream()` 輸入的 `Command` 模式（恢復時可選配同時傳入 `update=...`）。
    - **反模式警告**：切勿單獨傳入 `Command(update={"messages": [...]})` 來延續下一輪對話！因為任何作為輸入的 `Command` 都會從**最新的 checkpoint** 恢復執行，而**不是從 `START` 重新開始**，這會導致已結束的 thread 看起來像卡住一樣。要開始新的一輪對話，請直接傳入一般字典／物件 `graph.invoke({"messages": [...]}, config)`。

## 相關頁面
- [[concepts/langgraph-overview-and-workflows]]
- [[concepts/langgraph-graph-api-state-and-nodes]]
- [[concepts/langgraph-functional-api-and-pregel]]
- [[entities/langgraph-error-codes]]

## 出處
- docs/langgraph/graph-api-control-flow.md
- docs/langgraph/graph-api-send-command.md
- docs/langgraph/graph-api.md
