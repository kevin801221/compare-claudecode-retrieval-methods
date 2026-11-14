# LangGraph Memory and Stores

別名：記憶與儲存、長期記憶、短期記憶、BaseStore、InMemoryStore、對話歷史管理、訊息修剪與摘要
框架：langgraph

## 摘要
LangGraph 將代理記憶分為兩大層級：**短期記憶（Short-term memory）** 透過 Checkpointer 將狀態持久化於單一 `thread_id` 內以支援多輪對話，並透過 `trim_messages`、`RemoveMessage` 與 `SummarizationNode` 控制上下文視窗長度；**長期記憶（Long-term memory）** 則透過實作 `BaseStore` 介面的 Store（如 `InMemoryStore`、`PostgresStore`、`MongoDBStore`、`RedisStore`、`OracleStore`）將跨執行緒的使用者偏好或知識依 `namespace` 與 `key` 儲存為 JSON 項目（`Item`），並支援基於 Embedding 的語意搜尋（Semantic Search）。

## 重點

### 短期記憶 vs. 長期記憶架構
- **短期記憶（Short-term memory）**：
  - 屬於執行緒層級的持久化（Thread-level persistence），作為圖狀態（例如 `MessagesState`）的一部分，跨多輪互動保留對話上下文。
  - 啟用方式：編譯圖時傳入 `checkpointer`（如 `InMemorySaver` / `MemorySaver`、`PostgresSaver`、`MongoDBSaver`、`RedisSaver`、`OracleSaver`），並在執行時傳入 `{"configurable": {"thread_id": "1"}}`。
  - **子圖傳遞**：若父圖包含子圖，只需在編譯父圖時提供 `checkpointer`，LangGraph 會自動將其傳遞至子圖；若需子圖獨立維持跨呼叫的狀態，可在子圖編譯時設定 `subgraph_builder.compile(checkpointer=True)`（JS：`{ checkpointer: true }`）。
- **長期記憶（Long-term memory）**：
  - 跨對話執行緒（Cross-thread）儲存特定使用者或應用程式層級的鍵值資料。
  - 啟用方式：編譯圖時傳入 `store`（`builder.compile(checkpointer=checkpointer, store=store)` 或 JS `builder.compile({ checkpointer, store })`）。
  - 使用 LangSmith Agent Server（本地 Studio 或託管環境）時，預設已內建底層 Store，無需在 `compile` 時手動傳入。

### Store 核心概念與基本操作 (`BaseStore` & `Item`)
- **命名空間（Namespaces）與鍵值**：
  - 每筆記憶皆歸屬於一個長度不限的字串元組 `namespace`（Python 為 `tuple[str, ...]`，如 `(user_id, "memories")` 或 `("memories", user_id)`；JS/TS 為字串陣列 `[userId, "memories"]`）。
  - **寫入 (`store.put` / `store.aput`)**：`store.put(namespace_for_memory, memory_id, memory)`（JS：`await memoryStore.put(namespaceForMemory, memoryId, memory)`）。其中 `memory_id` 為唯一識別字串（如 `str(uuid7())`），`memory` 為可 JSON 序列化的 `dict`（如 `{"food_preference": "I like pizza"}`）。
- **`Item` 物件結構**：
  - `store.get` 與 `store.search` 回傳的每筆記憶皆為 `Item` 實例（Python 可呼叫 `.dict()` 轉為字典）：
    - `value`（`dict` / `object`）：記憶內容字典。
    - `key`（`str`）：該命名空間內的唯一鍵。
    - `namespace`（`tuple[str, ...]`）：命名空間（轉為 JSON 時可能序列化為陣列 `['1', 'memories']`）。
    - `created_at`（Python）／ `createdAt`（JS/TS）：建立時間的 ISO 8601 時間戳記。
    - `updated_at`（Python）／ `updatedAt`（JS/TS）：最後更新時間的 ISO 8601 時間戳記。
    - `score`（`float | None`）：當使用語意查詢 `query` 時附帶的相似度分數。
- **列出與搜尋命名空間項目 (`store.search` / `store.list_namespaces`)**：
  - 呼叫 `store.search(namespace_prefix)`（非同步為 `store.asearch`）且不傳入 `query` 與 `filter` 時，會列舉該前綴下的項目，預設 `limit=10`。
  - **三項關鍵行為限制**：
    1. **前綴比對（Prefix matching）**：`namespace_prefix` 採前綴比對而非精確比對，傳入 `("alice",)` 會同時回傳 `("alice",)`、`("alice", "memories")` 與 `("alice", "preferences")` 下的所有項目。
    2. **超出 `limit` 靜默截斷**：超過 `limit` 的結果會直接被截斷且無溢位提示，大量資料需調高 `limit` 或搭配 `offset` 分頁。
    3. **預設排序依後端而異**：`PostgresStore` 與 `AsyncPostgresStore` 預設依 `updated_at` 降冪排列（最新更新在前）；`InMemoryStore` 則依插入順序排列（最新插入在最後 `memories[-1]`）。若順序重要，請在客戶端針對 `item.updated_at` 自行排序。
  - **探索既有命名空間**：使用 `store.list_namespaces(*, prefix=None, suffix=None, max_depth=None, limit=100, offset=0)`（非同步 `store.alist_namespaces`，JS 為 `store.listNamespaces`）。

### 語意搜尋（Semantic Search）
- **啟用方式**：初始化 Store 時傳入 `index` 設定：
  - **Python**：
    ```python
    from langchain.embeddings import init_embeddings
    store = InMemoryStore(
        index={
            "embed": init_embeddings("openai:text-embedding-3-small"),
            "dims": 1536,
            "fields": ["food_preference", "$"]  # 預設要嵌入的欄位，"$" 代表整個字典
        }
    )
    ```
  - **TypeScript/JavaScript**：
    ```typescript
    const store = new InMemoryStore({
      index: {
        embeddings: new OpenAIEmbeddings({ model: "text-embedding-3-small" }),
        dims: 1536,
        fields: ["food_preference", "$"],
      },
    });
    ```
- **查詢與分數過濾**：
  - Python：`memories = store.search(namespace_for_memory, query="What does the user like to eat?", limit=3)`。
  - JS/TS：`const memories = await store.search(namespaceForMemory, { query: "What does the user like to eat?", limit: 3 })`。
  - 可透過 `item.score is not None and item.score > 0.2` 過濾低相似度結果。
- **單筆寫入的欄位索引控制 (`index` 參數)**：
  - 僅嵌入特定欄位：`store.put(namespace, key, value, index=["food_preference"])`（JS：`{ index: ["food_preference"] }`）。
  - 停用該筆嵌入（仍可透過 key 或前綴檢索，但不可語意搜尋）：`store.put(namespace, key, value, index=False)`（JS：`{ index: false }`）。
- **LangSmith / `langgraph.json` 語意搜尋設定**：
  - 在 Studio 或託管環境啟用語意搜尋，需在 `langgraph.json` 設定：
    ```json
    {
      "store": {
        "index": {
          "embed": "openai:text-embeddings-3-small",
          "dims": 1536,
          "fields": ["$"]
        }
      }
    }
    ```

### 在圖節點中存取 Store 與生產環境後端
- **透過 `Runtime` 注入存取**：
  - **Python**：在 `StateGraph(MessagesState, context_schema=Context)` 定義 `Context`，節點簽章加上 `runtime: Runtime[Context]`（`from langgraph.runtime import Runtime`），透過 `runtime.context.user_id` 取得使用者 ID，並呼叫 `await runtime.store.asearch(...)` 或 `await runtime.store.aput(...)`（同步節點呼叫 `runtime.store.search` / `runtime.store.put`；亦可在節點簽章使用關鍵字參數 `*, store: BaseStore`）。執行圖時傳入 `context=Context(user_id="1")`。
  - **TypeScript/JavaScript**：節點函式 `(state, runtime) => { ... }` 讀取 `runtime.context?.userId`（或 `user_id`），並呼叫 `await runtime.store?.search(...)` 與 `await runtime.store?.put(...)`。執行圖時傳入 `{ configurable: { thread_id: "1" }, context: { userId: "1" } }`。
- **正式環境 Store 與 Checkpointer 資料庫後端**：
  - **PostgreSQL**：套件 `langgraph-checkpoint-postgres`（JS：`@langchain/langgraph-checkpoint-postgres`）。
    - Python：`from langgraph.store.postgres import PostgresStore`、`from langgraph.store.postgres.aio import AsyncPostgresStore`（搭配 `PostgresSaver` / `AsyncPostgresSaver`）。使用 `PostgresStore.from_conn_string(DB_URI)`，首次使用需呼叫 `store.setup()`（非同步為 `await store.setup()`）。
    - JS/TS：`import { PostgresStore } from "@langchain/langgraph-checkpoint-postgres/store"`，呼叫 `PostgresStore.fromConnString(DB_URI)` 與 `await store.setup()`。
  - **MongoDB**：
    - Python：套件 `langgraph-store-mongodb` 與 `langgraph-checkpoint-mongodb`。匯入 `from langgraph.store.mongodb import MongoDBStore, create_vector_index_config`。語意搜尋需要 MongoDB Atlas 或具備 `mongot` 的 Vector Search（`$vectorSearch`），透過 `index_config = create_vector_index_config(embed=embed, dims=2, fields=["data"])` 與 `MongoDBStore.from_conn_string(MONGODB_ATLAS_URI, index_config=index_config, auto_index_timeout=120)` 建立。
    - JS/TS：套件 `@langchain/langgraph-checkpoint-mongodb`。呼叫 `await MongoDBStore.fromConnString(MONGODB_URI, { dbName: "langgraph", collectionName: "store", ... })`。支援兩種向量搜尋模式：
      1. **Manual embedding**：傳入 `embeddings: new OpenAIEmbeddings(...)` 與 `indexConfig: { name: "store_vector_index", dims: 1536, embeddingKey: "text" }`。
      2. **Auto embedding（需 MongoDB Atlas）**：不需傳入 `embeddings` 實例，由 MongoDB 伺服器端透過 Voyage AI 自動嵌入，設定 `indexConfig: { name: "store_vector_index", path: "value.content", model: "voyage-4" }`。
  - **Redis（Python）**：套件 `langgraph-checkpoint-redis`。匯入 `from langgraph.store.redis import RedisStore` 或 `from langgraph.store.redis.aio import AsyncRedisStore`（搭配 `RedisSaver` / `AsyncRedisSaver`）。首次使用需呼叫 `store.setup()`（非同步 `await store.setup()`；注意 `AsyncRedisSaver` 的初始化方法名稱為 `await checkpointer.asetup()`，同步版為 `checkpointer.setup()`）。
  - **Oracle AI Database（Python）**：套件 `langgraph-oracledb`。匯入 `from langgraph_oracledb.store.oracle import OracleStore, AsyncOracleStore` 與 `from langgraph_oracledb.checkpoint.oracle import OracleSaver, AsyncOracleSaver`。連線字串格式如 `"user/password@localhost:1521/FREEPDB1"`，語意搜尋需 Oracle AI Vector Search，首次使用需呼叫 `store.setup()` 與 `checkpointer.setup()`。
- **自訂 Store (`BaseStore` 合約，Python)**：
  - 繼承 `from langgraph.store.base import BaseStore` 並實作 **5 個必備非同步方法**（建議同時實作對應的同步方法 `put`、`get`、`delete`、`search`、`list_namespaces`）：
    - `aput(namespace, key, value, index=None)`
    - `aget(namespace, key)`（時間複雜度應為 $O(1)$，找不到時回傳 `None`）
    - `adelete(namespace, key)`
    - `asearch(namespace_prefix, *, query=None, filter=None, limit=10, offset=0)`（若後端不支援向量搜尋但傳入了 `query`，應拋出 `NotImplementedError`）
    - `alist_namespaces(*, prefix=None, suffix=None, max_depth=None, limit=100, offset=0)`

### 短期記憶管理策略（Managing Short-Term Memory）
當對話變長時，將所有持久化訊息傳給 LLM 會超出上下文視窗，LangGraph 提供四種標準處理方式：
- **1. 修剪訊息 (`trim_messages` / `trimMessages`)**：
  - 在呼叫 LLM 前依 token 數量截取訊息清單，**不會從圖狀態中刪除訊息**。
  - **Python**：
    ```python
    from langchain_core.messages.utils import trim_messages, count_tokens_approximately
    messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=128,
        start_on="human",
        end_on=("human", "tool"),
    )
    ```
  - **TypeScript/JavaScript**：
    ```typescript
    import { trimMessages } from "@langchain/core/messages";
    const messages = trimMessages(state.messages, {
      strategy: "last",
      maxTokens: 128,
      startOn: "human",
      endOn: ["human", "tool"],
      tokenCounter: model,
    });
    ```
- **2. 永久刪除狀態中的訊息 (`RemoveMessage` & `REMOVE_ALL_MESSAGES`)**：
  - 狀態通道必須使用 `add_messages` reducer（Python，如 `MessagesState`）或 `messagesStateReducer`（JS/TS，如 `MessagesValue`）。
  - **刪除特定訊息**：
    - Python：`from langchain.messages import RemoveMessage`，節點回傳 `{"messages": [RemoveMessage(id=m.id) for m in messages[:2]]}`。
    - JS/TS：`import { RemoveMessage } from "@langchain/core/messages"`，節點回傳 `{ messages: messages.slice(0, 2).map((m) => new RemoveMessage({ id: m.id })) }`。
  - **刪除全部訊息（Python）**：`from langgraph.graph.message import REMOVE_ALL_MESSAGES`，節點回傳 `{"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}`。
  - **序列合法性警告**：刪除訊息後必須確保剩餘歷史符合 LLM 供應商規範（例如部分模型要求第一則必須是 `user` 訊息，且帶有 tool calls 的 `assistant` 訊息後方必須緊接對應的 `tool` 結果訊息）。
- **3. 摘要歷史訊息 (`SummarizationNode` 或自訂摘要節點)**：
  - **自訂摘要節點**：在 `State(MessagesState)` 新增 `summary: str` 欄位（JS：`summary: z.string().default("")`）。當訊息累積超過閾值（如 `len(messages) > 6`）時，由摘要節點要求模型產生或延伸既有摘要，並回傳 `{"summary": response.content, "messages": [RemoveMessage(id=m.id) for m in state["messages"][:-2]]}` 刪除舊訊息。
  - **使用 `langmem` 的 `SummarizationNode`（Python）**：
    - 匯入：`from langmem.short_term import SummarizationNode, RunningSummary`。
    - 狀態定義：主圖狀態包含 `context: dict[str, RunningSummary]`；模型節點接收專用輸入狀態 `class LLMInputState(TypedDict): summarized_messages: list[AnyMessage]; context: dict[str, RunningSummary]`。
    - 節點設定：
      ```python
      summarization_node = SummarizationNode(
          token_counter=count_tokens_approximately,
          model=summarization_model,
          max_tokens=256,
          max_tokens_before_summary=256,
          max_summary_tokens=128,
      )
      ```
    - 讀取摘要內容：`final_response["context"]["running_summary"].summary`。
- **4. 管理與刪除 Checkpoints**：
  - **檢視執行緒狀態**：透過 Graph API `graph.get_state(config)`（JS：`await graph.getState(config)`）取得 `StateSnapshot`，或透過 Checkpointer API `checkpointer.get_tuple(config)` 取得 `CheckpointTuple`（內含 `checkpoint` 的 `v`、`ts`、`id`、`channel_versions`、`versions_seen`、`channel_values` 以及 `pending_writes`）。
  - **檢視執行緒歷史**：透過 `list(graph.get_state_history(config))`（JS：`graph.getStateHistory(config)`）或 `list(checkpointer.list(config))`。
  - **刪除執行緒所有 Checkpoints**：Python 呼叫 `checkpointer.delete_thread(thread_id)`；JS/TS 呼叫 `await checkpointer.deleteThread(threadId)`。

## 相關頁面
- [[concepts/langgraph-persistence-and-checkpointers]]
- [[concepts/langgraph-interrupts-and-time-travel]]
- [[concepts/langgraph-subgraphs-and-fault-tolerance]]

## 出處
- docs/langgraph/stores.md
- docs/langgraph/add-memory.md
