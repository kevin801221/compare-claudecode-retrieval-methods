# LangGraph Graph API: State, Reducers, Nodes, and Visualization

別名：Graph API 狀態與節點配置、StateGraph、Reducers、Overwrite、MessagesState、Node Caching、RetryPolicy、TimeoutPolicy、圖形視覺化
框架：langgraph

## 摘要
LangGraph 的 Graph API 將代理工作流建模為由共享狀態（`State`）、節點（`Nodes`）與邊（`Edges`）組成的圖形，並以類似 Google Pregel 的離散超步（super-steps）訊息傳遞機制執行。本頁涵蓋 `StateGraph` 建構與編譯、狀態 Schema（`TypedDict`、`dataclass`、Pydantic `BaseModel`、TypeScript `StateSchema` 與替代定義法）、通道與 Reducers（含 `add_messages`、`MessagesValue`、`Overwrite`）、多重／私有 Schema 與串流可見性、節點配置（執行期上下文、重試、逾時、錯誤處理器、全圖預設值、`execution_info`、`server_info`、優雅停機 `drain_requested`、節點快取 `CachePolicy`）、圖形遷移相容性，以及 Mermaid／PNG 圖形視覺化。

## 重點

### 圖形核心架構與超步（`graph-api.md`、`use-graph-api.md`）
- **三大核心組件**：
  1. `State`：應用程式的共享快照（通常為具備型別的 schema），資料儲存在具名的槽位「通道（channels）」中。
  2. `Nodes`：讀取狀態、執行工作並回傳局部狀態更新（partial updates）的同步或非同步函式（請直接回傳更新，切勿原地修改 mutating state）。
  3. `Edges`：決定下一個執行節點的固定或條件轉移函式。
- **超步執行模型（Super-steps）**：
  - 平行執行的節點共享同一個 super-step；依序執行的節點位於不同的 super-steps。
  - 當節點在進入邊（incoming edge）收到輸入時變為活躍（active）；一個 super-step 結束後，沒有待處理訊息的節點變為非活躍（inactive）。
  - 當所有節點皆為 inactive 且沒有傳輸中的訊息時，整次執行結束。
- **編譯與建構檢查表（`StateGraph.compile` & Build Checklist）**：
  - `StateGraph` 是主要的圖形建構器，必須先呼叫 `.compile()` 檢查圖形結構（例如是否有孤立節點 orphaned nodes）並掛載 checkpointers 或 breakpoints，才能呼叫 `invoke` 或 `stream`。
  - 建構決策五步驟：1. 定義共享狀態（Schema、Reducers、私有或輸入輸出 Schema） -> 2. 選擇控制流（Sequence、Branch、Parallel、Loop 與 recursion limit） -> 3. 決定是否需要 `Send`（map-reduce 動態平行展開）或 `Command`（同時更新狀態與路由、從 interrupt 恢復、或從工具內更新狀態） -> 4. 配置節點選項（Retries、Timeouts、Error handlers、Node defaults、Caching、Runtime context） -> 5. 視覺化圖形。

### 狀態定義、Reducers 與 `Overwrite`（`graph-api.md`、`graph-api-state.md`）
- **Python 狀態定義方式**：
  - 支援 `TypedDict`、`dataclass`（適合需要預設值時）或 Pydantic `BaseModel`（適合需要輸入驗證時）。考量效能建議優先使用 `TypedDict` 或 `dataclass`。
  - **限制**：LangChain 的 `create_agent` 狀態 schema **必須**是 `TypedDict`，不支援 Pydantic models。
  - **Pydantic `BaseModel` 已知限制**：
    - 圖形的輸出**不是** Pydantic model 實例（而是字典）。
    - 執行期驗證（Runtime validation）**僅發生在進入圖形第一個節點的輸入上**，後續節點或輸出不會進行驗證。
    - Pydantic 的驗證錯誤追蹤（error trace）不會顯示錯誤發生在哪一個節點。
    - Pydantic 遞迴驗證可能較慢；若在狀態 schema 中使用 LangChain 訊息型別，請使用 `AnyMessage`（而非 `BaseMessage`）以確保跨網路傳輸時的正常序列化與反序列化；同時須注意 Pydantic 的執行期型別強制轉型（Runtime Type Coercion）。
- **TypeScript/JavaScript 狀態定義方式**：
  - 優先使用 `StateSchema` 類別（支援 Standard Schema 如 Zod v3 / v4），其欄位可為：
    1. **Standard schema**（如 `z.string()`）：對應 last-value channel，更新時直接覆寫。
    2. **`ReducedValue`**：自訂 reducer（常搭配平行更新），語法為 `new ReducedValue(valueSchema, { reducer: (left, right) => ... })`。
    3. **`MessagesValue`**：內建訊息感知（message-aware）reducer 的訊息列表欄位。TypeScript 沒有獨立的 `MessagesState` 預建類別，直接在 `StateSchema` 的 `messages` 欄位放上 `MessagesValue` 即可。
    4. **`UntrackedValue`**：暫態（transient）資料，在單次執行期間保存但**絕不寫入 checkpoints**，恢復執行（resume）時會重置，適合資料庫連線或快取。預設 `guard: true`（同一 super-step 多次寫入會拋出錯誤）；設為 `guard: false` 時則由最後寫入者獲勝（last write wins）。切勿將跨 interrupts 或 time travel 所需的資料放入 `UntrackedValue`。
  - **TypeScript 型別工具（Type utilities）**：
    - `GraphNode`：標註節點函式型別（可選配 `Command` 目標節點）。
    - `State.Node`：`StateSchema` 實例上的 `GraphNode<typeof State>` 簡寫。
    - `ConditionalEdgeRouter`：標註回傳節點名稱或 `END` 的條件邊路由函式。
    - `StateSchema.State` / `StateSchema.Update`：提取完整狀態與局部更新型別。
  - **TypeScript 替代與舊版狀態定義方式（Alternative state definitions）**：
    - **Channels API（底層控制，從 `@langchain/langgraph/channels` 匯入）**：
      - `LastValue`：儲存最新值（覆寫欄位）；物件簡寫中傳入 `null` 即建立 `LastValue`。
      - `BinaryOperatorAggregate`：使用 reducer 函式合併值（計數器、列表）；物件簡寫中傳入 `{ reducer, default }` 即建立此通道。
      - `Topic`：將所有值收集為序列（事件流、稽核日誌）。
      - `EphemeralValue`：在 supersteps 之間重置的值（暫時性計算狀態）。
    - **`Annotation.Root`**：宣告式定義狀態與 reducers 的舊版（Legacy）語法。
    - **Zod v3 + `.langgraph` 插件**：使用 `z.object()` 搭配 `.langgraph.reducer()` 與 `.langgraph.metadata()`（Legacy，僅限 Zod v3）。
    - **Zod v4 + registry**：使用 LangGraph registry 將中繼資料附加至 schema 欄位（Legacy，僅限 Zod v4）。
- **Reducers 運作機制**：
  - 二元函式簽章：Python 為 `new_value = reducer(left=current_state[key], right=node_update[key])`，透過 `Annotated[type, reducer_func]`（如 `Annotated[list, operator.add]`）綁定；TypeScript 為 `const newValue = reducer(currentState[key], nodeUpdate[key])`，透過 `ReducedValue` 綁定。
  - **預設 Reducer**：未指定時預設將 `left` 替換為 `right`（last-write-wins）。
  - **訊息狀態與 `add_messages` / `MessagesState`**：
    - 單純的 `operator.add` 只能附加新訊息，無法在 human-in-the-loop 修改時依 ID 原地更新既有訊息。
    - Python 使用內建 `add_messages` reducer（或直接繼承預建的 `MessagesState`），支援依 ID 更新既有訊息、刪除訊息，以及將 `{"type": "human", "content": "message"}` 或 `{"role": "user", "content": "..."}` 等簡寫格式自動反序列化為 LangChain 訊息物件（如 `HumanMessage`）。
    - TypeScript 使用 `MessagesValue`，同樣支援依 ID 更新、刪除與 `{ role: "human", content: "message" }` 反序列化。
- **重置 Reducer 欄位與 `Overwrite`（Bypass reducers）**：
  - 使用合併型（merging）reducer 時，回傳空列表 `[]` **不會**清空欄位（因為空列表與舊列表合併後仍保留舊資料）。
  - 若要繞過 reducer 直接覆寫或清空欄位，使用 `Overwrite`（Python 從 `langgraph.types` 匯入 `Overwrite`；TypeScript 匯入 `Overwrite`），或使用特殊 JSON 鍵 `{"__overwrite__": value}`。
  - **平行寫入限制**：當節點在同一個 super-step 平行執行時，同一個狀態鍵**最多只能有一個節點**使用 `Overwrite`；若多個節點在同一 super-step 對同一鍵使用 `Overwrite`，會拋出 `InvalidUpdateError`。此外，`Overwrite` 會丟棄同一 super-step 中其他節點對該鍵寫入的一般更新，最終只保留 `Overwrite` 的值。

### 多重 Schema、私有狀態與串流可見性（`graph-api-state.md`）
- **輸入與輸出 Schema（Input and Output Schemas）**：
  - 可在建構 `StateGraph` 時分開指定内部完整狀態、輸入 schema（驗證傳入 `invoke` 的輸入）與輸出 schema（過濾內部資料，使 `invoke` 只回傳輸出 schema 包含的欄位）。
- **私有節點狀態（Pass private state between nodes）**：
  - 節點可定義並讀寫不在主圖輸入／輸出 schema 中的私有狀態 schema（例如 `node_1` 回傳 `private_data`，`node_2` 以私有 schema 作為輸入型別讀取 `private_data`，而 `node_3` 只看得到公開整體狀態）。節點可以寫入圖形狀態中的任何通道，即使該通道不在該節點宣告的輸入 schema 中。
- **私有通道與串流（Private channels and streaming）**：
  - 輸入、輸出與私有 schema 僅限制節點讀取的內容與 `invoke` 的回傳值，**預設不會在串流（streaming）中隱藏私有通道**！
  - 當使用 `graph.stream(..., stream_mode="values")`（JS 為 `streamMode: "values"`）或事件串流 `stream_events` / `streamEvents`（`version="v3"`）的 `stream.values` 投影時，預設會發出**所有**狀態通道（包含私有通道）。
  - 若要限制串流輸出的通道（例如只輸出公開 schema），需在 `graph.stream` 傳入 `output_keys`（Python）或 `outputKeys`（TypeScript）；若只需每個步驟中節點實際產生的通道更新而非完整累積狀態，請改用 `stream_mode="updates"`（JS 為 `streamMode: "updates"`）。

### 節點運作、重執行冪等性與工作單位選擇（`graph-api.md`）
- **節點簽章與封裝**：
  - Python 節點可接收三個參數：1. `state`（圖形狀態）、2. `config`（`RunnableConfig`，含 `thread_id`、`tags` 等）、3. `runtime`（`Runtime` 物件，含 runtime context、`store`、`stream_writer`、`execution_info` 等）。以 `add_node` 加入。
  - TypeScript 節點可接收：1. `state`、2. `config`（`RunnableConfig` / `LangGraphRunnableConfig`）。以 `addNode` 加入。
  - 底層會將函式包裝為 `RunnableLambda` 以支援批次處理、非同步與追蹤。若省略節點名稱，預設使用函式名稱。
  - 特殊虛擬節點：`START`（標記接收使用者輸入後首先執行的節點）與 `END`（標記終止邊）。
- **重執行與冪等性（Re-execution and idempotency）**：
  - Checkpointer 在 **super-step 邊界**儲存檢查點，而非節點函式執行中途。發生 interrupt 或 retry 後，受影響的節點會**從函式開頭重新執行**，暫停前的副作用（side effects）會再次執行。
  - 若節點內部呼叫了 Functional API 的 `@task` 或 `interrupt()`，恢復執行時已完成之 task 的結果會從 checkpointer 還原；切勿在恢復點之前改變 task 或 interrupt 的呼叫順序。
- **工作單位選擇對照表（Choose the unit of work）**：
  - **Plain function inside a node（節點內的一般函式）**：無獨立 checkpoint；節點重跑時跟著重跑；適用於步驟後無路由分叉、且可接受隨節點一起重跑的工作。
  - **Task（`@task`）**：不產生新的圖形 checkpoint（結果儲存在當前 entrypoint 或父節點 checkpoint 中）；外層節點從頭重播時，已完成的 tasks 直接回傳快取結果；適用於具副作用或昂貴、在 resume 時不可重複執行的步驟。
  - **Subgraph（子圖）**：具狀態模式下擁有獨立 checkpoint（儲存在父 thread 的 namespace 下；若以 `checkpointer=False` 編譯則無子圖 checkpoints）；恢復時從子圖內部中斷或失敗的節點繼續；適用於擁有獨立路由／狀態 schema 或被多個父圖重用的單元。
  - **Graph node（圖形節點）**：所屬 super-step 結束後產生 checkpoint；恢復時從該節點開始，前面的節點不會重跑；適用於步驟後有路由分叉，或需要 interrupt、resume、time travel 邊界時。

### 節點配置：執行期上下文、重試、逾時、錯誤處理與快取（`graph-api-nodes.md`）
- **執行期配置（Runtime configuration / context）**：
  - 在不將依賴項（如模型名稱、系統提示詞、資料庫連線）放入狀態的情況下傳遞至節點：定義配置 schema -> 加入節點或條件邊函式簽章 -> 呼叫圖形時傳入。
- **重試策略（Retry policies）**：
  - Python：傳入 `retry_policy=RetryPolicy(...)` 給 `add_node`。預設 `retry_on` 使用 `default_retry_on`，會重試除了以下例外之外的所有錯誤：`ValueError`、`TypeError`、`ArithmeticError`、`ImportError`、`LookupError`、`NameError`、`SyntaxError`、`RuntimeError`、`ReferenceError`、`StopIteration`、`StopAsyncIteration`、`OSError`。針對 `requests` 與 `httpx` 等 HTTP 函式庫例外，預設僅重試 `5xx` 狀態碼。
  - TypeScript：傳入 `retryPolicy` 給 `addNode`（傳入空物件 `{}` 即使用內建預設值；未設定 `retryPolicy` 則不重試）。若省略 `retryOn`，預設會重試除了以下之外的所有錯誤：取消與中止錯誤（`error.name === "AbortError"`，或 `error.message` 以 `"Cancel"` 或 `"AbortError"` 開頭）、`GraphValueError`（依 `error.name` 比對）、連線中止（`error.code === "ECONNABORTED"`）、HTTP 客戶端錯誤狀態碼 `400, 401, 402, 403, 404, 405, 406, 407, 409`、以及 OpenAI 配額錯誤（`error.error?.code === "insufficient_quota"`）。
- **節點逾時（Node timeouts）**：
  - 版本需求：Python 需 `langgraph>=1.2`；TypeScript 需 `@langchain/langgraph` v1.4.0 以上。
  - Python：在 `add_node` 傳入 `timeout`（秒數 float/int、`datetime.timedelta` 或可分別設定執行與閒置限制的 `TimeoutPolicy`）。**僅適用於 async 節點**；在同步（sync）節點上設定 `timeout` 會在編譯時期（compile time）失敗。逾時會拋出 `NodeTimeoutError`（它**不是**內建 `TimeoutError`／`OSError` 的子類別，因此若有設定 `retry_policy`，預設會將其視為可重試！）。每次重試都會獨立重置計時器，且逾時的嘗試不會提交已緩衝的寫入（buffered writes）。可透過 `runtime.heartbeat()` 刷新閒置逾時。
  - TypeScript：在 `addNode` 傳入 `timeout`（毫秒數 number 或 `TimeoutPolicy`）。逾時會拋出 `NodeTimeoutError`、清除該次失敗嘗試的寫入，並交由 retry policy 決定是否重試。
- **節點錯誤處理器（Handle node errors）**：
  - 版本需求：Python 需 `langgraph>=1.2`；TypeScript 需 `@langchain/langgraph` v1.4.0 以上。
  - 在節點失敗且所有重試耗盡後執行：Python 傳入 `error_handler` 給 `add_node`；TypeScript 傳入 `errorHandler` 給 `StateGraph` 上的 `addNode`（基礎 `Graph` 類別不支援）。處理器接收當前狀態與具型別的 `NodeError`，並可回傳 `Command` 路由至補償／復原分支。
- **全圖節點預設值（Graph-wide node defaults）**：
  - 版本需求：Python 需 `langgraph>=1.2`；TypeScript 需 `@langchain/langgraph` v1.4.0 以上。
  - 使用 `set_node_defaults`（Python）或 `setNodeDefaults`（TypeScript）一次性為圖中所有節點設定 `retry_policy` / `retryPolicy`、`timeout`、`cache_policy` / `cachePolicy` 或 `error_handler` / `errorHandler`。
  - **優先順序與適用範圍**：在 `compile` 時套用，單一節點上的設定永遠優先（Per-node values always win）。`retry_policy` 與 `timeout` 預設值適用於所有節點（包含 error-handler 節點）；`cache_policy` 與 `error_handler` 預設值**僅適用於一般節點**（錯誤處理器不會捕捉自己，且快取錯誤處理器結果並不安全）。預設值**不會**被子圖（subgraphs）繼承。
- **存取執行資訊（Execution info）**：
  - Python 透過 `runtime.execution_info`、TypeScript 透過節點第二個參數 `config.executionInfo`（型別 `LangGraphRunnableConfig`）讀取（即使未設 retry policy，節點任務準備好後即會設定，`node_attempt` / `nodeAttempt` 預設為 `1`）：
    - `thread_id` / `threadId`（`str | None` / `string | undefined`）：無 checkpointer 時為 `None`。
    - `run_id` / `runId`（`str | None` / `string | undefined`）：config 未提供時為 `None`。
    - `checkpoint_id` / `checkpointId`（`str` / `string`）
    - `checkpoint_ns` / `checkpointNs`（`str` / `string`）
    - `task_id` / `taskId`（`str` / `string`）
    - `node_attempt` / `nodeAttempt`（`int` / `number`）：1-indexed 執行嘗試次數（首次為 `1`，第一次重試為 `2`）。
    - `node_first_attempt_time` / `nodeFirstAttemptTime`：首次嘗試開始的 Unix 時間戳（Python 為秒 `float | None`；TypeScript 為毫秒 `number | undefined`），跨重試保持不變。
- **存取伺服器資訊（Server info）**：
  - 當運行於 LangSmith Agent Server 時可用（本地開發或測試時為 `None` / `undefined`）：
  - Python（需 `langgraph>=1.1.5`）透過 `runtime.server_info` 存取：`assistant_id`（`str`）、`graph_id`（`str`）、`user`（`BaseUser | None`）。
  - TypeScript（需 `@langchain/langgraph` v1.2.8 以上）透過 `config.serverInfo` 存取：`assistantId`（`string`）、`graphId`（`string`）、`user`（`Record<string, unknown> | undefined`）。
- **存取優雅停機排空狀態（Drain state）**：
  - 當請求優雅停機（graceful shutdown，呼叫 `RunControl.request_drain()` / `requestDrain`）時，可在節點內檢查以跳過昂貴工作：
  - Python（需 `langgraph>=1.2`）：`runtime.drain_requested`（`bool`）與 `runtime.drain_reason`（`str | None`）。
  - TypeScript：`runtime.control?.drainRequested`（`boolean`）與 `runtime.control?.drainReason`（`string | undefined`）。
- **節點快取（Add node caching）**：
  - 啟用方式：1. 在 `compile(cache=...)` 時傳入快取實例（如 `InMemoryCache`，Python 另提供 `SqliteCache`）；2. 在節點掛載 `CachePolicy`。
  - `CachePolicy` 參數：`key_func`（Python，預設使用 pickle 對輸入進行雜湊）／`keyFunc`（TypeScript），以及 `ttl`（存活秒數，省略時永不過期）。

### 圖形遷移與遞迴限制（`graph-api.md`）
- **圖形遷移（Graph migrations）**：
  - **拓樸變更（Nodes & Edges）**：已結束的執行緒（Finished threads）可自由新增、移除或重新命名節點與邊；處於中斷暫停的執行緒（Interrupted threads）可變更邊與新增節點，但**不可重新命名或移除執行緒即將進入的節點**（否則 resume 時依名稱查找節點會失敗）。
  - **狀態 Schema 變更**：新增或移除鍵具前後向相容性；重新命名鍵會丟失既有執行緒中該鍵已儲存的值；對既有鍵進行不相容的型別變更（如縮小型別範圍或將舊檢查點省略的欄位設為必填）會破壞舊執行緒狀態。
- **遞迴限制（Recursion limit）**：
  - 限制單次執行可運行的最大 super-steps 數量，超過時拋出 `GraphRecursionError`。
  - **Python 預設值**：自 `1.1.4` 版起預設為 `10,007` super-steps；在 `1.0.6` 至 `1.1.3` 版之間預設為 `10,000` steps（注意：舊文件或部分錯誤訊息可能提及 `25`，但 `graph-api.md` 明載最新預設值演進）。可透過環境變數 `LANGGRAPH_DEFAULT_RECURSION_LIMIT` 覆寫，或在頂層 config 鍵傳入 `recursion_limit`（切勿放在 `configurable` 底下）。
  - **TypeScript/JavaScript 預設值**：預設為 `25` super-steps。在頂層 config 鍵傳入 `recursionLimit`（切勿放在 `configurable` 底下）。

### 圖形視覺化（`graph-api-visualize.md`）
- **取得可繪製圖形物件**：Python 呼叫 `app.get_graph()`；TypeScript 呼叫 `await app.getGraphAsync()`。
- **輸出 Mermaid 語法字串**：呼叫 `draw_mermaid()`（Python）或 `drawMermaid()`（TypeScript）。
- **輸出 PNG 圖片**：
  - **Mermaid.ink API（預設，不需額外套件）**：Python 呼叫 `app.get_graph().draw_mermaid_png()`；TypeScript 呼叫 `await drawableGraph.drawMermaidPng()` 並轉為 `Uint8Array` 寫入檔案。
  - **Mermaid + Pyppeteer（Python）**：需安裝 `pip install pyppeteer`，在 Jupyter 中執行 `nest_asyncio.apply()`，從 `langchain_core.runnables.graph` 匯入 `CurveStyle`、`MermaidDrawMethod`、`NodeStyles`，呼叫 `draw_mermaid_png(curve_style=CurveStyle.LINEAR, node_colors=NodeStyles(first="#ffdfba", last="#baffc9", default="#fad7de"), wrap_label_n_words=9, output_file_path=None, draw_method=MermaidDrawMethod.PYPPETEER, background_color="white", padding=10)`。
  - **Graphviz（Python）**：需安裝 `pip install pygraphviz` 與系統 Graphviz 執行檔。

## 相關頁面
- [[concepts/langgraph-overview-and-workflows]]
- [[concepts/langgraph-control-flow-send-and-command]]
- [[concepts/langgraph-functional-api-and-pregel]]
- [[entities/langgraph-error-codes]]

## 出處
- docs/langgraph/graph-api.md
- docs/langgraph/use-graph-api.md
- docs/langgraph/graph-api-state.md
- docs/langgraph/graph-api-nodes.md
- docs/langgraph/graph-api-visualize.md
