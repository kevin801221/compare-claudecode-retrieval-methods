# LangGraph Persistence and Checkpointers

別名：持久化與檢查點、Checkpointer、狀態快照、StateSnapshot、Thread 狀態管理、短期記憶持久化
框架：langgraph

## 摘要
LangGraph 的持久化層（Persistence）由兩個互補系統組成：**Checkpointers** 負責在每個 super-step 邊界將單一執行緒（Thread）的圖狀態儲存為檢查點（Checkpoint），提供對話延續、Human-in-the-loop 中斷恢復、時光旅行（Time Travel）與容錯恢復（Fault Tolerance）等短期記憶功能；**Stores** 則負責儲存圖狀態以外的跨執行緒鍵值資料（長期記憶）。所有 Checkpointer 皆實作 `BaseCheckpointSaver` 介面，支援記憶體、SQLite、PostgreSQL、MongoDB、Redis 與 Azure Cosmos DB 等後端，並支援 `JsonPlusSerializer` 序列化、`EncryptedSerializer` 加密以及三種持久性模式（`"exit"`、`"async"`、`"sync"`）。

## 重點

### Persistence 架構：Checkpointer vs. Store
- **編譯綁定**：
  - Python：`from langgraph.checkpoint.memory import InMemorySaver`、`from langgraph.store.memory import InMemoryStore`，呼叫 `builder.compile(checkpointer=checkpointer, store=store)`。
  - TypeScript/JavaScript：`import { MemorySaver, InMemoryStore } from "@langchain/langgraph"`，呼叫 `builder.compile({ checkpointer, store })`。
  - **Agent Server**：使用 LangSmith Agent Server 時無需手動實作或設定 checkpointer 與 store，伺服器會自動處理底層持久化基礎設施。
- **Checkpointer 與 Store 對比**：
  - **Checkpointer**：持久化圖狀態快照（Graph state snapshots），作用範圍為單一執行緒（Single thread），屬於短期、執行緒範圍記憶（Short-term, thread-scoped memory），透過在 graph config 傳入 `thread_id` 存取，適用於對話延續、human-in-the-loop、time travel 與 fault tolerance。
  - **Store**：持久化應用程式定義的鍵值資料（Application-defined key-value data），作用範圍跨執行緒（Across threads），屬於長期、跨執行緒記憶（Long-term, cross-thread memory），由節點或應用程式碼直接讀寫項目，適用於使用者偏好、事實與共享知識。

### 核心概念：Threads、Super-steps 與 Checkpoints
- **Threads（執行緒）**：
  - 每個由 checkpointer 儲存的 checkpoint 都會綁定一個唯一識別碼 `thread_id`（作為儲存與檢索的主鍵）。
  - 執行綁定 checkpointer 的圖時，**必須**在 config 的 `configurable` 中指定 `thread_id`：`{"configurable": {"thread_id": "1"}}`（若缺少則無法儲存狀態或從 `interrupt` 恢復）。
- **延續既有 Thread 的四種呼叫模式**：
  - **提交新輸入（Submit new input）**：`graph.invoke(input, config)`（JS：`await graph.invoke(input, config)`）。透過狀態定義的 reducers 將新輸入套用至既有已儲存狀態（不會清空 thread；若需空白狀態請換新的 `thread_id`），並從圖的 entry point 開始執行。
  - **錯誤後繼續執行（Continue after an error）**：`graph.invoke(None, config)`（JS：`await graph.invoke(null, config)`）。不傳入 `checkpoint_id`，載入最新 checkpoint 並重試未完成的工作；若最新 checkpoint 無未完成工作，則直接回傳已儲存結果而不重新執行節點。
  - **回覆 `interrupt()`**：`graph.invoke(Command(resume=answer), config)`（JS：`await graph.invoke(new Command({ resume: answer }), config)`）。提供 interrupt 的回傳值，被中斷的節點會從該節點開頭重新開始執行。
  - **重播歷史（Replay history）**：`graph.invoke(None, snapshot.config)`（JS：`await graph.invoke(null, snapshot.config)`）。使用來自 `get_state_history()` / `getStateHistory()` 的特定 `snapshot.config`（含 `checkpoint_id`），跳過該 checkpoint 之前的節點，重新執行該 checkpoint 之後的所有節點（包含 LLM 呼叫、API 請求與 `interrupt()`）。
- **Checkpoints 與 Super-steps**：
  - LangGraph 在每個 **super-step**（所有排定於該步驟的節點平行或單一執行的單一 tick）邊界建立一個完整狀態快照，以 `StateSnapshot` 物件表示。
  - 以循序圖 `START -> node_a -> node_b -> END` 為例，單次 `invoke({"foo": "", "bar": []}, config)` 會產生 **4 個 checkpoints**：
    1. 初始空白輸入 checkpoint：`next=('__start__',)`，`metadata={'source': 'input', 'writes': {'foo': ''}, 'step': -1}`，`parent_config=None`。
    2. 使用者輸入套用後的 checkpoint：`values={'foo': '', 'bar': []}`，`next=('node_a',)`（JS 為 `['nodeA']`），`metadata={'source': 'loop', 'writes': None, 'step': 0}`。
    3. `node_a` 輸出後的 checkpoint：`values={'foo': 'a', 'bar': ['a']}`，`next=('node_b',)`（JS 為 `['nodeB']`），`metadata={'source': 'loop', 'writes': {'node_a': {'foo': 'a', 'bar': ['a']}}, 'step': 1}`。
    4. `node_b` 輸出後的最終 checkpoint：`values={'foo': 'b', 'bar': ['a', 'b']}`，`next=()`（JS 為 `[]`），`metadata={'source': 'loop', 'writes': {'node_b': {'foo': 'b', 'bar': ['b']}}, 'step': 2}`。
  - **Pending writes（節點／Task 層級寫入）**：在同一個 super-step 內，當個別節點執行完成時，其輸出會立即以 task 紀錄寫入 checkpointer 的 `checkpoint_writes`（或 `writes`）資料表並關聯至進行中的 checkpoint。若同一 super-step 的其他平行節點失敗，恢復執行時已成功節點的寫入不會重新計算。注意：Time travel 只能從 super-step 邊界的完整 `StateSnapshot` 恢復，無法從個別 task write 恢復。
- **Checkpoint Namespace (`checkpoint_ns`)**：
  - 識別該 checkpoint 所屬的圖或子圖（subgraph）：
    - `""`（空字串）：代表根圖（parent/root graph）。
    - `"node_name:uuid"`：代表作為該節點名稱被呼叫的子圖；若為巢狀子圖，則以 `|` 串接（例如 `"outer_node:uuid|inner_node:uuid"`）。
  - 節點內讀取方式：Python 為 `config["configurable"]["checkpoint_ns"]`；JS/TS 為 `config.configurable?.checkpoint_ns`。

### 檢視與更新狀態 API (`get_state`、`get_state_history`、`update_state`)
- **取得狀態 (`get_state` / `getState`)**：
  - Python：`graph.get_state(config)`；JS/TS：`await graph.getState(config)`。
  - 僅傳入 `{"configurable": {"thread_id": "1"}}` 時回傳最新 `StateSnapshot`；若同時指定 `"checkpoint_id"` 則回傳該特定 checkpoint 的 `StateSnapshot`。
- **`StateSnapshot` 欄位結構**：
  - `values`（Python：`dict`；JS/TS：`object`）：該 checkpoint 的各狀態通道（state channel）數值。
  - `next`（Python：`tuple[str, ...]`，完成時為 `()`；JS/TS：`string[]`，完成時為 `[]`）：下一步準備執行的節點名稱清單。
  - `config`（Python：`dict`；JS/TS：`object`）：包含 `configurable` 內的 `thread_id`、`checkpoint_ns` 與 `checkpoint_id`。
  - `metadata`（Python：`dict`；JS/TS：`object`）：執行元資料，包含 `source`（值為 `"input"`、`"loop"` 或 `"update"`）、`writes`（該步節點輸出）與 `step`（super-step 計數器，從 `-1` 開始）。
  - `created_at`（Python，`str`）／ `createdAt`（JS/TS，`string`）：建立時間的 ISO 8601 時間戳記字串。
  - `parent_config`（Python，`dict | None`）／ `parentConfig`（JS/TS，`object | null`）：前一個 checkpoint 的 config；第一個 checkpoint 為 `None` / `null`。
  - `tasks`（Python：`tuple[PregelTask, ...]`；JS/TS：`PregelTask[]`）：該步驟要執行的任務清單。每個 `PregelTask` 包含 `id`、`name`、`error`、`interrupts`，以及在設定 `subgraphs=True`（JS：`subgraphs: true`）時額外包含的 `state`（子圖快照）。
- **取得狀態歷史 (`get_state_history` / `getStateHistory`)**：
  - Python：`list(graph.get_state_history(config))`；JS/TS：`for await (const state of graph.getStateHistory(config))`。
  - 回傳依時間倒序排列（**最新的一筆排在第一個**）的 `StateSnapshot` 序列。
  - 常見篩選條件：
    - 特定節點執行前：`s.next == ("node_b",)`（JS：`s.next.includes("nodeB")`）。
    - 依步數：`s.metadata["step"] == 2`。
    - 找出由 `update_state` 建立的分叉：`s.metadata["source"] == "update"`。
    - 找出發生中斷的 checkpoint：`s.tasks and any(t.interrupts for t in s.tasks)`。
- **列出所有 Threads（跨執行緒查詢）**：
  - Python：呼叫 `checkpointer.list(None)`（非同步使用 `checkpointer.alist(None)`）。**必須傳入 `None` 而非 `{}`**，因為 `SqliteSaver` 會將任何非 `None` 的 config 視為 thread 篩選器並在缺少 `thread_id` 時拋出例外。
  - JS/TS：呼叫 `graph.getStateHistory({})` 或 `checkpointer.list({})`（在 `configurable` 中省略 `thread_id`）。
  - 兩者皆適用於 `InMemorySaver` / `MemorySaver`、`SqliteSaver` 與 `PostgresSaver`，且每筆回傳為單一 `CheckpointTuple`（而非每個 thread 一筆），需自行依 `thread_id` 分組。
- **修改狀態 (`update_state` / `updateState`)**：
  - Python：`graph.update_state(config, values, as_node=...)`；JS/TS：`await graph.updateState(config, values, asNode)`。
  - 不會覆寫既有 checkpoint，而是建立一個 `metadata["source"] == "update"` 的新 checkpoint。
  - 更新值會經過狀態通道定義的 reducer 函式處理（具 reducer 的通道會累加而非直接覆蓋）。
  - 可選參數 `as_node`（Python）／ `asNode`（JS/TS）用來指定此更新視為由哪個節點發出，進而決定下一個要執行的節點。

### 持久性模式（Durability Modes）
呼叫圖執行方法時可透過 `durability` 參數指定（例如 Python `graph.stream({"input": "test"}, durability="sync")` 或 JS `await graph.stream({ input: "test" }, { durability: "sync" })`），由低到高共三種：
- `"exit"`：僅在圖執行結束時（正常完成、發生錯誤或觸發 human-in-the-loop interrupt）才將變更持久化。長執行圖效能最佳，但不儲存中間狀態，若執行期間程序崩潰則無法恢復，且新 thread 在執行結束前不會留下任何紀錄。
- `"async"`：在下一步驟開始執行的同時，以非同步方式持久化變更。效能與持久性兼具，但在第一個使用者節點執行前僅開始寫入 input checkpoint 而不等待完成，程序崩潰時仍有極小機率遺失最近的 checkpoint。
- `"sync"`：
  - **Python**：在下一步驟開始前**同步**完成寫入；對新 thread 而言，會在第一個使用者節點執行前確保提交 input checkpoint（step `-1`）與 step `0` checkpoint。
  - **TypeScript/JavaScript**：在執行期間排程寫入，並僅在整個 run 結束時 `await` 所有未完成的 checkpointer promises；中間步驟與第一個使用者節點仍可能在寫入完成前先執行（在啟動邊界的可見性等同 `"async"`），但可確保呼叫端在所有寫入落盤後才收到回傳結果。
- **崩潰邊界注意事項**：在任何模式下，若在第一個 checkpoint 完成持久化前崩潰，該 thread 將與從未被呼叫過的 thread 無法區分：`get_tuple()` 回傳 `None`（JS `getTuple()` 回傳 `undefined`），且呼叫 `invoke(None, config)` 會拋出 `EmptyInputError`。若需區分「從未受理」與「已受理但遺失」，需在呼叫 `invoke` 前於外部資料庫記錄 outbox row。

### 檢查點儲存最佳化：`DeltaChannel`（Python Beta）
- 預設情況下，LangGraph 會在每個 super-step 寫入所有狀態通道的完整累積值。
- `DeltaChannel`（需 `langgraph>=1.2`，目前為 beta）是僅在 checkpoint blob 中儲存哨兵值（`MISSING`）與增量差異（incremental deltas）的 reducer 通道，使諸如 `messages` 等累加型通道的每個步驟儲存複雜度從 $O(N)$ 降為 $O(1)$。
- 載入時，LangGraph 會呼叫 `saver.get_delta_channel_history(config=config, channels=[...])`（或非同步 `aget_delta_channel_history`），沿著 `parent_config` 祖先鏈向上回溯至最近的 `_DeltaSnapshot`（msgpack ext code `7`），回傳 `{"writes": [...], "seed": ...}`（`writes` 由舊到新排列），再由執行期呼叫 `channel.from_checkpoint(seed)` 與 `channel.replay_writes(writes)` 重建狀態。
- 若在啟用 `DeltaChannel` 的儲存上實作 `prune`、`delete_for_runs` 或 `copy_thread`，必須保留或完整複製回溯至最近一個 `_DeltaSnapshot` 所需的所有祖先 `writes` 紀錄，否則通道會被靜默重建為空值。

### Checkpointer 套件、介面與自訂實作
- **官方 Checkpointer 套件清單**：
  - **Python**：
    - `langgraph-checkpoint`（內建於 LangGraph）：提供基底介面 `BaseCheckpointSaver`、`SerializerProtocol` 與記憶體實作 `InMemorySaver`（位於 `langgraph.checkpoint.memory`）。
    - `langgraph-checkpoint-sqlite`：`SqliteSaver` / `AsyncSqliteSaver`（適用於本地開發與實驗）。
    - `langgraph-checkpoint-postgres`：`PostgresSaver` / `AsyncPostgresSaver`（LangSmith 採用，適用於正式環境；首次使用需呼叫 `checkpointer.setup()` 建立資料表與索引）。
    - `langgraph-checkpoint-mongodb`：`MongoDBSaver` / `AsyncMongoDBSaver`。
    - `langchain-azure-cosmosdb`：`CosmosDBSaverSync` / `CosmosDBSaver`（支援同步／非同步與 Microsoft Entra ID 驗證）。
  - **TypeScript/JavaScript**：
    - `@langchain/langgraph-checkpoint`（內建於 LangGraph）：提供 `BaseCheckpointSaver`、`SerializerProtocol` 與 `MemorySaver`（亦可從 `@langchain/langgraph` 匯入）。
    - `@langchain/langgraph-checkpoint-sqlite`：`SqliteSaver`。
    - `@langchain/langgraph-checkpoint-postgres`：`PostgresSaver`。
    - `@langchain/langgraph-checkpoint-mongodb`：`MongoDBSaver` 與長期記憶儲存 `MongoDBStore`。
    - `@langchain/langgraph-checkpoint-redis`：`RedisSaver`。
- **`BaseCheckpointSaver` 介面方法**：
  - **五個必備核心方法**（缺少任一會拋出 `NotImplementedError`）：
    1. `.put` / `.aput(config, checkpoint, metadata, new_versions) -> RunnableConfig`：儲存單筆 checkpoint，需使用 `self.serde.dumps_typed(checkpoint)` 序列化、完整保留 `metadata` 所有未知欄位（如 `counters_since_delta_snapshot`），並將輸入 `config["configurable"].get("checkpoint_id")` 存為 `parent_checkpoint_id`。
    2. `.put_writes` / `.aput_writes(config, writes, task_id, task_path="") -> None`（JS 為 `.putWrites`）：儲存中間節點寫入，需匯入 `from langgraph.checkpoint.base import WRITES_IDX_MAP` 將特殊通道（如 `__error__`、`__interrupt__`）映射至保留的負數索引以避免碰撞。
    3. `.get_tuple` / `.aget_tuple(config) -> CheckpointTuple | None`（JS 為 `.getTuple`）：當 `config` 未指定 `checkpoint_id` 時回傳該 `thread_id` + `checkpoint_ns` 最新一筆（因 `checkpoint_id` 為字典序可排序的 ULID，可用 `ORDER BY checkpoint_id DESC LIMIT 1`）；當指定 `checkpoint_id` 時必須精確回傳該筆（Time travel 與 `DeltaChannel` 皆依賴此精確查找）。
    4. `.list` / `.alist(config, *, filter=None, before=None, limit=None) -> Iterator[CheckpointTuple] | AsyncIterator[CheckpointTuple]`：依時間由新到舊列出符合條件的 `CheckpointTuple`，支援 `before` 與 `limit`。
    5. `.delete_thread` / `.adelete_thread(thread_id: str) -> None`：刪除該 thread 的所有 checkpoints 與 writes 資料列。
  - **進階選用方法**（Agent Server 啟動時會自動偵測）：`adelete_for_runs`（支援 rollback multitask 策略）、`acopy_thread`（高效率執行緒分叉）、`aprune`（歷史修剪）、`aget_delta_channel_history`（高效率 `DeltaChannel` 重建）。
  - **相容性測試套件**：安裝 `langgraph-checkpoint-conformance`，使用 `@checkpointer_test(name="...")` 與 `await validate(my_checkpointer)` 及 `report.passed_all_base()` 驗證實作。

### 序列化與加密（Serializer & Encryption，Python）
- **預設序列化器 `JsonPlusSerializer`**：
  - 位於 `langgraph.checkpoint.serde.jsonplus`，實作 `SerializerProtocol`。底層使用 `ormsgpack` 與 JSON，原生支援 LangChain/LangGraph 物件、Pydantic v2 models、dataclasses、numpy arrays、datetimes、enums 與 `_DeltaSnapshot`。
  - **Pickle Fallback**：對於 msgpack 不支援的物件（如 Pandas DataFrames），可啟用 `JsonPlusSerializer(pickle_fallback=True)` 並傳入 `InMemorySaver(serde=JsonPlusSerializer(pickle_fallback=True))`。
- **狀態加密 `EncryptedSerializer`**：
  - 位於 `langgraph.checkpoint.serde.encrypted`。透過 `EncryptedSerializer.from_pycryptodome_aes()` 建立實例，預設會從環境變數 `LANGGRAPH_AES_KEY` 讀取 AES 金鑰（或直接傳入 `key` 參數），再傳給任何 checkpointer 的 `serde` 參數（例如 `SqliteSaver(..., serde=serde)` 或 `PostgresSaver.from_conn_string(..., serde=serde)`）。
  - 在 LangSmith 上執行時，只要設定 `LANGGRAPH_AES_KEY` 環境變數即會自動啟用加密。亦可實作 `CipherProtocol` 自訂加密演算法。

### 常見問題排除（Troubleshooting）
- **`PostgresSaver` 的 `thread_id` 過長錯誤**：`PostgresSaver` / `AsyncPostgresSaver` 儲存 `thread_id` 的欄位長度有限，請保持 `thread_id` 在 **255 個字元以內**（例如使用 `from langchain_core.utils.uuid import uuid7; str(uuid7())[:255]`）。
- **`MemorySaver` / `InMemorySaver` 重啟後遺失資料**：因為儲存在 RAM 中，正式環境請改用 `PostgresSaver` 或本地開發改用 `SqliteSaver`。
- **Checkpoints 無限增長**：長對話累積大量 checkpoints 會增加延遲與儲存成本，建議定期修剪（prune）舊 checkpoints、設定保留策略或使用 `DeltaChannel`。
- **父圖無法立即看到子圖狀態更新**：因為每個子圖各自管理獨立的 `checkpoint_ns`，若需跨圖共享資料，請使用 `Store` 或設定子圖寫入父圖 checkpoint。

## 相關頁面
- [[concepts/langgraph-memory-and-stores]]
- [[concepts/langgraph-interrupts-and-time-travel]]
- [[concepts/langgraph-subgraphs-and-fault-tolerance]]

## 出處
- docs/langgraph/persistence.md
- docs/langgraph/checkpointers.md
