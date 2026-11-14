# LangGraph Functional API and Pregel Runtime

別名：Functional API 與 Pregel 執行期、@entrypoint 與 @task、Bulk Synchronous Parallel (BSP)、PregelNode、Channels、DeltaChannel、entrypoint.final
框架：langgraph

## 摘要
LangGraph 提供兩大高階 API——Graph API（`StateGraph`）與 Functional API（`@entrypoint`／`@task`），兩者在編譯或建立後皆會產生底層的 `Pregel` 執行期實例。Functional API 讓開發者以原生程式語言控制流（`if`/`else`、迴圈與一般函式呼叫）包裝既有程式碼或其他框架（如 Claude Agent SDK、Strands、CrewAI、AutoGen）並獲得持久化、短期記憶、human-in-the-loop 與串流能力；而 `Pregel` 則依據 Google Pregel 演算法與整體同步平行（Bulk Synchronous Parallel, BSP）模型，結合 Actors（`PregelNode`）與各種 Channels（`LastValue`、`Topic`、`BinaryOperatorAggregate`、`DeltaChannel`、`EphemeralValue`）按三階段超步執行。

## 重點

### Functional API 概覽與適用時機（`functional-api.md`）
- **Functional API vs Graph API 選擇與差異**：
  - 建立全新的 LangGraph 代理與工作流時，優先使用 **Graph API**；若已有既有程式碼或使用其他代理框架（Claude Agent SDK、Strands、CrewAI、AutoGen 等）並希望在不改寫為圖形的情況下部署至 LangSmith Agent Server，則使用 **Functional API**。
  - 相較於 Graph API，Functional API 使用一般語言控制流（`if` / `else`、迴圈、函式呼叫）、將變數作用域限制在 entrypoint 與 tasks 內而非共享 `State` schema、將 task 結果儲存在 entrypoint checkpoint 上（而非每個 super-step 之後），且**沒有靜態圖形視覺化（no static graph visualization）**。
- **兩大核心建構塊**：
  - **`@entrypoint`（Python，來自 `langgraph.func`）／`entrypoint`（TypeScript，來自 `@langchain/langgraph` 或 `@langchain/langgraph/func`）**：標記工作流起點，管理長時執行、中斷（interrupts）與檢查點（checkpointing），回傳一個 `Pregel` 實例。
  - **`@task`（Python，來自 `langgraph.func`）／`task`（TypeScript，來自 `@langchain/langgraph`）**：標記離散的工作單元（如 API 呼叫或副作用步驟）。Python 呼叫 task 會立即回傳 future-like 物件（同步以 `.result()` 解析，非同步以 `await` 解析）；TypeScript 呼叫 `task("name", async (...) => ...)` 定義的函式會回傳 `Promise`，於 entrypoint 內以 `await` 等待。

### `@entrypoint` 定義、執行、短期記憶與注入參數（`functional-api.md`）
- **輸入限制與序列化**：
  - `entrypoint` 函式**必須只接收單一位置參數（a single positional argument）**作為工作流輸入（若需傳遞多個值，請封裝為字典 dict 或物件 object）。
  - 當配置了 `checkpointer` 時，`entrypoint` 的**輸入（inputs）與輸出（outputs）都必須是 JSON-serializable**（使用基本型別如 dict/object、list/array、string、number、boolean，否則執行期會拋出錯誤）。
- **執行與錯誤／中斷後恢復（Run and resume）**：
  - Python 呼叫 `invoke` 或 `ainvoke`；TypeScript 呼叫 `invoke`。
  - 從 `interrupt` 恢復時，傳入 `Command(resume=...)`；從**錯誤（error）**後恢復同一個 `thread_id` 時，Python 傳入 `None`，TypeScript 傳入 `null`。
- **短期記憶（Short-term memory）與 `entrypoint.final`**：
  - 當 `entrypoint` 配置了 `checkpointer` 時，同一 `thread_id` 的連續呼叫會將狀態儲存在 checkpoints 中。
  - **Python**：在函式簽章加入 keyword-only 參數 `previous`（首次執行時為 `None`，後續為同 thread 上一次儲存的值）。
  - **TypeScript**：在 entrypoint 內部呼叫 `getPreviousState()`（首次執行時為 `undefined`）。
  - 若要讓函式回傳給呼叫端的值與儲存至下一次 `previous` 的值不同，使用 `entrypoint.final`（`entrypoint.final(value=..., save=...)`）。
- **可注入參數與輔助工具（Injectable parameters）**：
  - **Python**（必須使用正確的參數名稱與型別標註）：
    - `previous`：同 thread 前一次呼叫儲存的回傳值（需 checkpointer）。
    - `config`：`RunnableConfig` 執行期配置物件。
    - `store`：`BaseStore` 長期記憶實例（亦可透過 `runtime.store` 存取）。
    - `writer`：`StreamWriter` 自訂串流寫入器（亦可透過 `runtime.stream_writer` 存取）。
    - `runtime`：`Runtime` 物件（包含 context、`store`、`stream_writer`）。
  - **TypeScript**（`entrypoint` 函式可接收第二個參數 `config: LangGraphRunnableConfig`，或呼叫內部 helper）：
    - `getPreviousState`：取得同 thread 前一次呼叫的儲存值。
    - `config`：`LangGraphRunnableConfig` 物件。
    - `config.store`：長期記憶 store 實例。
    - `config.writer`：自訂串流 writer。

### `@task` 定義、執行與恢復確定性規則（`functional-api.md`）
- **Task 的兩大特性与限制**：
  1. **並行執行（Concurrent execution）**：呼叫 task 會立即啟動執行，entrypoint 只有在呼叫 `.result()` 或 `await` 等待結果時才會阻塞，因此多個獨立 tasks 可重疊並行執行。
  2. **檢查點保存（Checkpointing）**：Task 的**輸出（outputs）必須是 JSON-serializable**，其結果會被儲存以便在 resume 時直接還原而不重新計算。
  - **呼叫位置限制**：只能在 **entrypoint**、另一個 **task** 或 **Graph API node** 內部呼叫 task，**切勿**從工作流外部的一般應用程式碼直接呼叫 task。
- **重播機制、確定性（Determinism）與冪等性（Idempotency）**：
  - **重播起點（Replay from start）**：從 `interrupt` 恢復執行時，**不會**從當初停下的那一行程式碼繼續，而是**從 `entrypoint` 的最開頭重新執行（replays forward）**！在重播過程中，LangGraph 會從 checkpointer 直接還原已完成的 **task** 與 **subgraph** 結果，而非重新計算它們。
  - **常見陷阱 1：副作用（Side effects）未放入 Task**：若在 `entrypoint` 主體內直接寫檔案或發送 API（未包成 `@task`），在 `interrupt` 後 resume 重播時，該副作用會**被重複執行第二次**！必須將所有副作用封裝進 `@task` 中。
  - **常見陷阱 2：非確定性控制流（Non-deterministic control flow）**：若在 `entrypoint` 主體內直接讀取系統時間（如 `time.time()`、`Date.now()`）或產生亂數，並據此進行 `if` / `else` 分支判斷，在 resume 重播時可能拿到不同的時間／亂數而走進不同分支！此外，當有多個 `interrupt` 呼叫時，LangGraph 是**依照索引順序（by index）**將 resume 值對應給每個 `interrupt`；若重播時分支改變導致 `interrupt` 順序變動，resume 值就會綁定到錯誤的 `interrupt` 上。因此，必須將讀取時鐘與亂數等非確定性操作封裝進 `@task` 中，確保重播時還原完全相同的時間戳與分支。
  - **未完成 Task 的冪等性**：已完成的 task 在 resume 時會還原結果；但若某個 task 已經啟動卻在完成前中斷或失敗，恢復時仍會再次執行，因此 task 內部的外部寫入應使用冪等鍵（idempotency keys）或先讀後寫檢查。

### Pregel 執行期架構與三階段模型（`pregel.md`）
- **核心概念**：
  - `Pregel` 實作了 LangGraph 的執行期，命名源自 Google 的 Pregel 大規模圖形平行計算演算法。編譯 `StateGraph` 或建立 `@entrypoint` / `entrypoint` 都會產生一個 `Pregel` 實例。
  - Pregel 將 **Actors**（即實作 LangChain Runnable 介面的 `PregelNode`）與 **Channels** 結合在單一應用程式中，依據 **Pregel Algorithm / Bulk Synchronous Parallel (BSP)** 模型按多個步驟（steps）推進。
- **每個步驟的三個階段（Three phases per step）**：
  1. **Plan（規劃階段）**：決定在此步驟中要執行哪些 **actors**。例如在第一步選擇訂閱了特殊 **input** channels 的 actors；在後續步驟中，選擇訂閱了「在前一步驟中被更新的 channels」的 actors。
  2. **Execution（執行階段）**：平行執行所有被選中的 **actors**，直到全部完成、或其中一個失敗、或達到 timeout 為止。**在此階段期間，通道的更新對其他 actors 是不可見的（invisible），直到下一個步驟才可見**。
  3. **Update（更新階段）**：使用此步驟中各 **actors** 寫入的值來更新 channels。
  - 重複上述三階段，直到沒有任何 **actors** 被選中執行，或達到最大步數限制（maximum number of steps）為止。

### Channels 通道類型與 `DeltaChannel`（`pregel.md`）
- **標準通道類型**（Python 來自 `langgraph.channels`；TypeScript 來自 `@langchain/langgraph/channels`）：
  1. **`LastValue`**：預設通道類型，只儲存最後寫入的值並覆寫前值（Python：`LastValue(int)`；TS：`new LastValue<number>()`）。用於輸入／輸出值或跨步傳遞資料。
  2. **`Topic`**：可配置的 PubSub 通道，適用於在 actors 之間傳送多個值或跨步累積輸出。可配置去重（deduplicate）或以 `accumulate=True`（TS：`new Topic<string>({ accumulate: true })`）跨步累積所有寫入的值。當設為 `accumulate=False`（預設）且在某一步驟未收到新值（例如寫入空列表 `[]`）時，`Topic` 會在步驟間清空，可用於終止迴圈（Cycle）。
  3. **`BinaryOperatorAggregate`**：透過對當前值與每次新更新套用二元運算子來維護持久聚合值（Python：`BinaryOperatorAggregate(int, operator.add)` 或 `BinaryOperatorAggregate(str, operator=reducer)`；TS：`new BinaryOperatorAggregate<number>({ operator: (a, b) => a + b })`）。其 reducer 是在**寫入時（at write time）**被呼叫，並將合併後的值序列化進 checkpoint。
  4. **`EphemeralValue`**：暫態通道（Python：`EphemeralValue(str)`；TS：`new EphemeralValue<string>()`），在步驟間不保留持久狀態。
- **`DeltaChannel`（僅限 Python，需 `langgraph>=1.2`，目前為 Beta）**：
  - **用途**：在每個步驟只儲存增量差值（incremental delta）而非完整累積值。適用於寫入頻繁且隨時間大幅增長的通道（如長對話的訊息列表，當發現某通道的 checkpoint 大小隨 thread 長度呈線性成長時即可採用），避免每次 checkpoint 都重新序列化完整列表。
  - **語法**：`messages: Annotated[list[str], DeltaChannel(my_reducer, snapshot_frequency=5)]`（從 `langgraph.channels` 匯入 `DeltaChannel`）。
  - **批次 Reducer 規範（Bulk reducer requirement）**：
    - 傳給 `DeltaChannel` 的 `reducer` 是 **bulk reducer**，簽章為 `(state: list[str], writes: Sequence[list[str]]) -> list[str]`，在單次呼叫中接收當前狀態與該步驟所有寫入的**序列（sequence）**（不同於一般 `Annotated` 每次更新成對呼叫一次的二元 reducer）。
    - **必須滿足結合律（Associative / batching-invariant）**：`reducer(reducer(state, [xs]), [ys]) == reducer(state, [xs, ys])`，否則狀態重建結果會隨批次分組方式而異。
    - **在重建時執行而非寫入時執行（Runs on reconstruction, not on write）**：序列化進 checkpoint 的是原始的單步寫入（raw per-step writes），reducer 只有在讀取通道值、下一步驟的 actors 存取、或重播歷史而需要實體化（materialized）時才會被呼叫！因此設計 bulk reducer 有三大鐵則：
      1. **必須是 `(state, writes)` 的純函式（pure function）**：任何副作用、亂數或讀取時鐘（如 `uuid.uuid4()`、`datetime.now()`）在每次重建時都會重新執行並產生不同結果。
      2. **不可依賴對輸入 `writes` 的原地修改（mutations）會被持久化**：在 reducer 內為沒有 ID 的項目賦予 ID 只會存在於當次重建的值中，底層儲存的 write 仍是未修改的原貌。
      3. **在寫入通道前（upstream）就附加 ID 與穩定中繼資料**。
  - **使用 `snapshot_frequency` 限制讀取延遲（Bounded read latency）**：
    - 若無快照，讀取 `DeltaChannel` 需重播完整寫入歷史，時間複雜度為 `O(N)`（N 為步數）。
    - 設定 `snapshot_frequency=K` 會每 K 個 pregel steps 寫入一次完整快照，將讀取深度上限控制在最多 K 步。預設為 `None`（完全不寫快照，適合極少讀取或短執行緒）。
  - **版本相容性與降級限制（Version compatibility and rollbacks）**：
    - 不建議將既有已持久化的通道從 `DeltaChannel` 改為非 delta 通道（反之亦然），否則既有 thread 會無法正確重建狀態。
    - **不支援降級（Rolling back is not supported）**：`langgraph>=1.2` 的 delta channel checkpoint 格式無法被舊版讀取；若需降級，必須先使用 `delta-channel-dump` 復原腳本遷移受影響的 threads 或將其丟棄。

### 直接使用底層 Pregel API 與檢視編譯結構（`pregel.md`）
- **使用 `NodeBuilder` 與 `Pregel` 直接建構應用程式**：
  - 匯入：Python 為 `from langgraph.pregel import Pregel, NodeBuilder`；TypeScript 為 `import { Pregel, NodeBuilder } from "@langchain/langgraph/pregel"`。
  - `NodeBuilder` 鏈式方法：
    - 訂閱單一通道（直接傳入該通道值）：`.subscribe_only("a")`（Python）／`.subscribeOnly("a")`（TypeScript）。
    - 訂閱通道（以字典／物件 `{ b: ... }` 形式傳入）：`.subscribe_to("b")`（Python）／`.subscribeTo("b")`（TypeScript）。
    - 定義執行邏輯：`.do(fn)`。
    - 指定寫入通道：`.write_to("b", "c")`（Python）／`.writeTo("b", "c")`（TypeScript）。
  - 實例化 `Pregel`：傳入 `nodes`、`channels`、`input_channels` / `inputChannels`、`output_channels` / `outputChannels`。
- **檢視高階 API 編譯後的底層 `nodes` 與 `channels`**：
  - 在 `StateGraph.compile()` 產生的 `graph` 上印出 `graph.nodes` 與 `graph.channels`：除了使用者定義的節點與 `LastValue` 狀態通道外，還會自動建立 `__start__` 節點與各節點的 `EphemeralValue` 觸發／分支通道（如 `'branch:__start__:__self__:write_essay'`、`'start:write_essay'`）。
  - 在 `@entrypoint` 產生的物件上印出 `.nodes` 與 `.channels`：包含一個同名 `PregelNode`，以及三個內建通道：`__start__`（`EphemeralValue`）、`__end__`（`LastValue`）與 `__previous__`（`LastValue`）。

## 相關頁面
- [[concepts/langgraph-overview-and-workflows]]
- [[concepts/langgraph-graph-api-state-and-nodes]]
- [[concepts/langgraph-control-flow-send-and-command]]
- [[entities/langgraph-error-codes]]

## 出處
- docs/langgraph/functional-api.md
- docs/langgraph/pregel.md
