# LangGraph Subgraphs and Fault Tolerance

別名：子圖與容錯機制、Subgraphs、Fault Tolerance、RetryPolicy、TimeoutPolicy、NodeTimeoutError、NodeError、error_handler、set_node_defaults、RunControl、GraphDrained、優雅關機
框架：langgraph

## 摘要
LangGraph 支援將編譯後的圖作為**子圖（Subgraphs）**嵌入父圖，提供「在節點內呼叫子圖（不共享狀態鍵）」與「將子圖直接加入為節點（共享狀態鍵）」兩種通訊模式，並透過 `compile(checkpointer=None | True | False)` 控制子圖為單次呼叫隔離（Per-invocation）、跨呼叫累積（Per-thread）或無狀態（Stateless）。在**容錯機制（Fault Tolerance）**方面，LangGraph 提供可組合的節點重試（`RetryPolicy`）、執行與閒置逾時（`TimeoutPolicy` / `NodeTimeoutError`）、錯誤補償處理器（`error_handler` / `NodeError`）、全圖預設值（`set_node_defaults`）以及基於 `RunControl` 與 `GraphDrained` 的跨 super-step 優雅關機（Graceful Shutdown）。

## 重點

### 子圖通訊模式（Subgraph Communication Patterns）
- **1. 在節點函式內呼叫子圖（Call a subgraph inside a node）**：
  - **適用情境**：父圖與子圖擁有**完全不同的狀態結構（無共享狀態鍵）**，或需要在傳遞前後轉換狀態（例如在多代理系統中為每個子代理保留私有訊息歷史）。
  - **實作方式**：撰寫包裝節點函式，手動將 `ParentState` 轉換為 `SubgraphState` 後呼叫 `subgraph.invoke({"bar": state["foo"]})`（JS：`await subgraph.invoke({ bar: state.foo })`），再將回傳值轉回父圖狀態格式。支援多層巢狀（如 `parent -> child -> grandchild`）。
- **2. 將編譯後的子圖直接加入為節點（Add a subgraph as a node）**：
  - **適用情境**：父圖與子圖**共享一或多個狀態鍵**（如共享 `messages` 或 `foo`；子圖的 `SubgraphState` 仍可額外定義父圖不可見的私有鍵如 `bar`）。
  - **實作方式**：不需撰寫包裝函式，直接呼叫 `builder.add_node("node_1", subgraph)`（JS：`builder.addNode("node1", subgraph)`），子圖會自動讀寫父圖對應的狀態通道。

### 子圖持久化模式（Subgraph Persistence：`checkpointer=`）
父圖必須先編譯綁定 Checkpointer，子圖才能使用中斷、狀態檢視與跨輪記憶。子圖透過 `subgraph_builder.compile(checkpointer=...)`（或 `create_agent(..., checkpointer=...)`）支援三種模式：

| 功能特性 | Per-invocation（預設） | Per-thread | Stateless |
| --- | --- | --- | --- |
| `checkpointer=` 參數值 | `None`（預設省略） | `True`（JS：`true`） | `False`（JS：`false`） |
| 支援 `interrupt()` (HITL) | ✅ | ✅ | ❌ |
| 跨呼叫多輪記憶（Multi-turn memory） | ❌（每次呼叫全新狀態） | ✅（同一 thread 累積狀態） | ❌ |
| 單節點多次呼叫（不同子圖） | ✅ | ⚠️（需命名空間隔離） | ✅ |
| 單節點多次／平行呼叫（同一子圖） | ✅ | ❌（命名空間衝突） | ✅ |
| 狀態檢視 (`subgraphs=True`) | ⚠️（僅限當前中斷中的呼叫） | ✅（可檢視累積狀態） | ❌ |

- **Per-invocation（`checkpointer=None`，預設推薦）**：
  - 每次呼叫子圖皆從全新狀態開始（不記憶前次呼叫），但在單次呼叫期間會繼承父圖 Checkpointer 以支援 `interrupt()` 與持久化恢復。
  - 每次呼叫會自動分配獨立的 checkpoint namespace，因此同一個子圖可在單一回合被平行或多次呼叫而不發生衝突。
- **Per-thread（`checkpointer=True`）**：
  - 子圖在同一 `thread_id` 的多次呼叫間會累積對話歷史與狀態（例如研究助理或持續追蹤已編輯檔案的程式助理）。
  - **禁止平行呼叫同一子圖**：若 LLM 同時平行呼叫同一個 `checkpointer=True` 的子代理工具，兩次呼叫會寫入相同 checkpoint namespace 導致衝突。使用 `create_agent` 時，必須加上 `ToolCallLimitMiddleware(tool_name="ask_fruit_expert", run_limit=1)`（Python `from langchain.agents.middleware import ToolCallLimitMiddleware`；JS `import { toolCallLimitMiddleware } from "langchain"`，傳入 `toolCallLimitMiddleware({ toolName: "ask_fruit_expert", runLimit: 1 })`）限制單次執行最多呼叫 1 次。
  - **多個不同 Per-thread 子圖的命名空間隔離（Namespace Isolation）**：若在節點或工具內以 `.invoke()` 呼叫多個不同子圖，LangGraph 預設依呼叫順序分配 namespace（重排順序會導致載入錯亂）。解決方案是將每個 `create_agent` 包裝在具有唯一節點名稱 `name` 的 `StateGraph(MessagesState).add_node(name, agent).add_edge("__start__", name).compile()` 中以固定 namespace。（直接透過 `add_node` 加入父圖的子圖已自動具備基於節點名稱的穩定 namespace。）
- **Stateless（`checkpointer=False`）**：
  - 如同普通函式呼叫般執行，無任何 checkpoint 開銷，但不支援 `interrupt()`、無法檢視子圖狀態，且程序崩潰時無法從中斷點恢復。

### 檢視與串流子圖狀態（Viewing & Streaming Subgraphs）
- **檢視子圖狀態 (`get_state` + `subgraphs=True`)**：
  - Python：`subgraph_state = graph.get_state(config, subgraphs=True).tasks[0].state`。
  - JS/TS：`const subgraphState = (await graph.getState(config, { subgraphs: true })).tasks[0].state`。
  - **靜態探索限制**：僅當 LangGraph 可**靜態探索（statically discover）**子圖時有效（即子圖是透過 `add_node` 加入或在節點函式內直接呼叫）。若子圖被隱藏在 `@tool` 工具函式內部呼叫，則無法透過 `get_state(..., subgraphs=True)` 檢視子圖狀態（但工具內子圖的 `interrupt()` 仍會正常向上傳遞至頂層父圖）。
- **串流子圖輸出 (`stream_events` v3)**：
  - **Python**：呼叫 `stream = graph.stream_events({"foo": "foo"}, version="v3")`，遍歷 `for subgraph in stream.subgraphs:` 可直接讀取 `subgraph.graph_name`、`subgraph.path`、`subgraph.messages` 與 `subgraph.values`；若需底層協定事件，可傳入 `transformers=[UpdatesTransformer]`（`from langgraph.stream import UpdatesTransformer`）並檢查 `event["method"] == "updates"` 的 `event["params"]["namespace"]`（如 `['node_2:uuid']`）與 `event["params"]["data"]`。
  - **TypeScript/JavaScript**：呼叫 `await graph.streamEvents({ foo: "foo" }, { subgraphs: true, version: "v3" })`，並迭代 `stream.values` 或 `stream.messages`。

---

### 容錯機制執行順序（Fault Tolerance Composition Order）
當節點執行發生異常時，LangGraph 的三層容錯機制依固定順序運作（per-node timeouts、error handlers、`set_node_defaults` 與 `RunControl` 需 Python `langgraph>=1.2` 或 JS `@langchain/langgraph>=1.4.0`）：
1. **執行節點（Run node）**：若發生任何例外（包含逾時拋出的 `NodeTimeoutError`），先丟棄該次失敗嘗試的所有圖狀態寫入。
2. **重試策略（`retry_policy` / `retryPolicy`）**：判斷例外是否符合重試條件且尚有剩餘次數；若是則重新從頭執行節點。
3. **錯誤處理器（`error_handler` / `errorHandler`）**：僅在重試次數耗盡（或未設定重試／例外不可重試）後觸發，接收 `NodeError` 並可透過 `Command` 更新狀態與轉移路由；若未設定處理器，例外才向上拋出使圖執行失敗。

### 1. 節點重試（Retries：`RetryPolicy`）
- **設定方式**：
  - Python：`from langgraph.types import RetryPolicy, default_retry_on`，於 `builder.add_node("call_api", call_api, retry_policy=RetryPolicy(max_attempts=3))` 設定。
  - JS/TS：於 `.addNode("callApi", callApi, { retryPolicy: { maxAttempts: 3 } })` 設定。
- **`RetryPolicy` 參數對照表**：

| Python 參數 | JS/TS 參數 | 型別（Py / JS） | 預設值（Py / JS） | 說明 |
| --- | --- | --- | --- | --- |
| `max_attempts` | `maxAttempts` | `int` / `number` | `3` / `3` | 最大嘗試次數（含首次執行） |
| `initial_interval` | `initialInterval` | `float` / `number` | `0.5` (秒) / `500` (毫秒) | 首次重試前的等待時間 |
| `backoff_factor` | `backoffFactor` | `float` / `number` | `2.0` / `2.0` | 每次重試後間隔時間的乘數 |
| `max_interval` | `maxInterval` | `float` / `number` | `128.0` (秒) / `128000` (毫秒) | 重試間隔上限 |
| `jitter` | `jitter` | `bool` / `boolean` | `True` / `true` | 是否加入隨機抖動（jitter） |
| `retry_on` | `retryOn` | `type[Exception] \| Sequence[...] \| Callable` / `(error: unknown) => boolean` | `default_retry_on` / 內建處理器 | 決定哪些例外可重試（JS 無匯出 `defaultRetryOn` 函式） |
| （無） | `logWarning` | — / `boolean` | — / `true` | 重試時是否記錄警告日誌（僅 JS/TS） |

- **預設可重試與排除的例外清單**：
  - **Python (`default_retry_on`)**：重試所有例外，**但排除以下內建例外及其子類別**：`ValueError`、`TypeError`、`ArithmeticError`、`ImportError`、`LookupError`、`NameError`、`SyntaxError`、`RuntimeError`、`ReferenceError`、`StopIteration`、`StopAsyncIteration`、`OSError`。對於 `requests` 與 `httpx` 等 HTTP 函式庫例外，僅重試 **5xx** 狀態碼。`NodeTimeoutError` 預設可重試。
  - **TypeScript/JavaScript**：必須顯式設定 `retryPolicy`（即使傳入 `{}`）才會啟用重試。預設處理器會重試所有錯誤，**但排除**：取消與中止錯誤（`error.name === "AbortError"` 或 `error.message` 以 `"Cancel"` / `"AbortError"` 開頭）、`GraphValueError`、連線中止（`error.code === "ECONNABORTED"`）、HTTP 客戶端錯誤狀態碼 `400, 401, 402, 403, 404, 405, 406, 407, 409`（`408` 與 `5xx` 可重試）、OpenAI 配額不足錯誤（`error.error?.code === "insufficient_quota"`）。此外，圖控制流錯誤（如 `GraphInterrupt`、`Command` 路由）與已中止的 run signal 會直接繞過 `retryOn` 不重試。
- **在節點內讀取重試狀態 (`runtime.execution_info` / `runtime.executionInfo`)**：
  - Python `runtime.execution_info` 欄位：`node_attempt`（`int`，從 `1` 開始計數，首次重試為 `2`）、`node_first_attempt_time`（`float | None`，首次嘗試啟動的 Unix 秒數時間戳，跨重試維持不變）、`thread_id`（`str | None`）、`run_id`（`str | None`）、`checkpoint_id`（`str`）、`task_id`（`str`）。
  - JS/TS `runtime.executionInfo` 欄位：`nodeAttempt`（`number`）、`nodeFirstAttemptTime`（`number | undefined`，毫秒）、`threadId`、`runId`、`checkpointId`、`checkpointNs`、`taskId`。
- **重試邊界與冪等性金鑰（Idempotency Key）設計**：
  - 重試會從頭重跑整個節點函式（提供 **at-least-once** 語意）。
  - 呼叫外部付款或寫入 API 時，**冪等性金鑰必須在副作用發生前就已持久化**：應直接從已持久化的狀態衍生（如 `idempotency_key = f"charge:{state['order_id']}"`），或在前一個獨立節點（如 `reserve_key`）搭配 `durability="sync"` 先生成並存入 checkpoint，切勿在同一個執行付款的節點內臨時呼叫 `uuid4()` 產生金鑰。若外部服務已提交但回應遺失，應將缺少本地狀態視為「結果未知（unknown）」，先向外部服務查詢狀態再決定補償。

### 2. 節點逾時（Timeouts：`TimeoutPolicy` 與 `NodeTimeoutError`）
- **設定方式與限制**：
  - **Python**：`add_node` 傳入秒數 `timeout=60`、`timeout=timedelta(minutes=2)` 或 `from langgraph.types import TimeoutPolicy; TimeoutPolicy(run_timeout=120, idle_timeout=30, refresh_on="auto" | "heartbeat")`。**重要限制：Python 的節點 `timeout` 僅支援 `async` 非同步節點**；同步節點設定 `timeout` 會在 `compile()` 時直接報錯拒絕（阻塞 I/O 請在 `async def` 節點內用 `asyncio.to_thread` 包裝）。
  - **TypeScript/JavaScript**：`addNode` 傳入毫秒數 `{ timeout: 60_000 }` 或 `{ timeout: { runTimeout: 120_000, idleTimeout: 30_000, refreshOn: "auto" | "heartbeat" } }`。
- **兩種逾時計時器（可同時設定，先觸發者取消該次嘗試）**：
  - **`run_timeout` / `runTimeout`**：單次嘗試的硬性總牆鐘時間上限（wall-clock cap），無論節點是否有進度都不會重置。
  - **`idle_timeout` / `idleTimeout`**：無進度閒置時間上限，只要節點發出進度訊號就會重置計時器：
    - 預設 `refresh_on="auto"`（JS：`refreshOn: "auto"`）會在以下任一事件發生時自動重置：透過 `CONFIG_KEY_SEND` 寫入狀態、產生串流輸出／呼叫 `runtime.writer`、排程子任務（child-task scheduling）、節點或其子孫發出的任何 LangChain callback 事件（LLM token、tool call、chain start/end 等）。
    - 嚴格心跳模式 `refresh_on="heartbeat"`（JS：`refreshOn: "heartbeat"`）：僅在節點明確呼叫 `runtime.heartbeat()`（JS：`runtime.heartbeat?.()`）時才重置閒置計時器（在未設定 idle timeout 的節點中呼叫 `runtime.heartbeat()` 為安全的無操作 no-op）。
- **`NodeTimeoutError` 例外屬性**：
  - 逾時觸發時拋出 `NodeTimeoutError`（預設可被 `RetryPolicy` 重試，且每次新嘗試會重置計時器並清除前次未完成寫入）：
    - Python：`node` (`str`)、`elapsed` (`float`，秒)、`kind` (`Literal["idle", "run"]`)、`idle_timeout` (`float | None`)、`run_timeout` (`float | None`)。
    - JS/TS（可用 `isNodeTimeoutError(error)` 進行型別縮小）：`node` (`string`)、`elapsed` (`number`，毫秒)、`kind` (`"idle" | "run"`)、`timeout` (`number`，觸發的毫秒值)、`idleTimeout` (`number | undefined`)、`runTimeout` (`number | undefined`)。
- **搭配 `Send` 的動態逾時**：
  - 在 map-reduce 動態派發時，可於 `Send("process_item", {"item": item}, timeout=TimeoutPolicy(idle_timeout=15))`（JS：`new Send("processItem", { item }, { timeout: { idleTimeout: 15_000 } })`）個別覆寫目標節點的靜態逾時設定。

### 3. 錯誤處理器（Error Handling：`error_handler` 與 `NodeError`）
- **運作機制**：當節點拋出例外且所有重試皆耗盡（或無對應重試策略）時執行，常用於 Saga 補償流程。每個節點最多只能設定一個 error handler；若 handler 本身又拋出例外，則直接向上冒泡。
- **設定與 `NodeError` 結構**：
  - **Python**：`add_node(..., error_handler=payment_error_handler)`。匯入 `from langgraph.errors import NodeError`（frozen dataclass，含 `node: str` 與 `error: BaseException` 兩個欄位）。處理器簽章支援依型別標註自動注入：`(state: State, error: NodeError) -> State | Command`、`(state)`、`(state, runtime)` 或 `(state, error: NodeError, config: RunnableConfig)`。
  - **TypeScript/JavaScript**：僅支援在 `StateGraph.addNode` 設定 `{ errorHandler: paymentErrorHandler }`（基礎 `Graph` 類別與 Functional API 的 `task` / `entrypoint` 不支援）。匯入 `import { NodeError } from "@langchain/langgraph"`（含 `node: string` 與 `error: Error`）。
- **關鍵行為保證**：
  - **恢復安全性（Resume-safe）**：失敗來源資訊會被寫入 checkpoint；若在節點失敗後、handler 完成前程序崩潰或中斷，從 checkpoint 恢復時 handler 會收到完全相同的 `NodeError` 上下文。
  - **與 `interrupt()` 互不干擾**：節點內呼叫 `interrupt()` 走的是 `GraphBubbleUp` 機制，**絕不會**觸發 `retry_policy` 或 `error_handler`。
  - **子圖例外傳遞**：若父節點包裝了子圖且子圖拋出未處理例外，該例外會傳遞至父節點的 `error_handler`（存於 `error.error`）。

### 4. 全圖節點預設值（Graph Defaults：`set_node_defaults` / `setNodeDefaults`）
- **用法**：在 `StateGraph` 上呼叫 `.set_node_defaults(retry_policy=..., error_handler=..., timeout=..., cache_policy=...)`（JS：`.setNodeDefaults({ retryPolicy, errorHandler, timeout, cachePolicy })`），一次性為圖中所有節點設定預設策略。
- **優先順序與作用範圍**：
  - 在 `add_node` / `addNode` 直接傳入的個別節點參數**永遠優先覆蓋** `set_node_defaults`（於 `compile()` 時解析，因此 `set_node_defaults` 與 `add_node` 的呼叫順序不影響結果）。
  - 父圖設定的 `set_node_defaults` **不會**被子圖繼承，每個圖各自維護預設值。
- **套用矩陣（Applicability Matrix）**：
  - 一般節點（Regular nodes）：完整套用 `retry_policy`、`timeout`、`error_handler` 與 `cache_policy`。
  - 錯誤處理器節點（Error-handler nodes）：**會套用** `retry_policy`（✅）與 `timeout`（✅），但**不會套用** `error_handler`（❌，避免處理器捕捉自己造成無限迴圈）與 `cache_policy`（❌，快取錯誤處理結果不安全）。

### 5. 優雅關機（Graceful Shutdown：`RunControl` 與 `GraphDrained`）
- **運作機制**：協作式關機（Cooperative drain）允許外部監控或 `SIGTERM` 訊號通知正在執行的圖在**當前 super-step 完成後**安全停止並寫入可恢復的 checkpoint，絕不會強制中斷正在執行中的節點或重試迴圈。
- **設定與呼叫方式**：
  - **Python**：
    ```python
    import signal
    from langgraph.runtime import RunControl
    from langgraph.errors import GraphDrained

    control = RunControl()
    signal.signal(signal.SIGTERM, lambda *_: control.request_drain("sigterm"))
    try:
        result = graph.invoke(inputs, config, control=control)
    except GraphDrained as e:
        print(f"Drained: {e.reason}")
    ```
  - **TypeScript/JavaScript**：
    ```typescript
    import { RunControl, GraphDrained } from "@langchain/langgraph";
    const control = new RunControl();
    process.on("SIGTERM", () => control.requestDrain("sigterm"));
    try {
      const result = await graph.invoke(inputs, { ...config, control });
    } catch (e) {
      if (e instanceof GraphDrained) console.log(`Drained: ${e.reason}`);
    }
    ```
- **Drain 邊界行為與恢復**：
  - **執行中節點／重試中節點**：當前節點與其 retry 迴圈會執行到完成或耗盡，drain 在下一個 super-step 邊界才生效。
  - **尚有後續 super-steps**：儲存可恢復的 checkpoint 並拋出 `GraphDrained(reason)`（若由子圖觸發，`GraphDrained` 會向上冒泡並在父圖的下一個 super-step 邊界停止父圖）。
  - **剛好在同一個 tick 自然結束**：正常回傳結果而不拋出例外，可檢查 `control.drain_requested`（JS：`control.drainRequested`）區分是否曾收到 drain 請求。
  - **在節點內提前感知 Drain 狀態**：節點可讀取 `runtime.drain_requested` 與 `runtime.drain_reason`（Python）或 `runtime.control?.drainRequested` 與 `runtime.control?.drainReason`（JS/TS）以跳過昂貴計算。
  - **從 Drain 恢復執行**：使用相同 `thread_id` 呼叫 `graph.invoke(None, config)`（JS：`await graph.invoke(null, config)`）。注意：`request_drain()` / `requestDrain()` 不會強制取消進行中的 asyncio task，若需硬性上限請搭配 task cancellation 或 `AbortSignal`。

## 相關頁面
- [[concepts/langgraph-persistence-and-checkpointers]]
- [[concepts/langgraph-memory-and-stores]]
- [[concepts/langgraph-interrupts-and-time-travel]]

## 出處
- docs/langgraph/use-subgraphs.md
- docs/langgraph/fault-tolerance.md
