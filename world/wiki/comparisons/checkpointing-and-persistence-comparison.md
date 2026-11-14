# Checkpointing, Persistence, and Time Travel Comparison Across Frameworks

別名：跨框架檢查點與持久化比較、Checkpointing 比較、狀態存檔與回溯比較、Session Storage vs Checkpointer vs BackendProtocol、Time Travel 比較
框架：agent-sdk、deepagents、langchain、langgraph

## 摘要
四個框架皆支援執行狀態的持久化與回溯，但設計層級與儲存標的截然不同：Claude Agent SDK 分離了「對話工作階段 JSONL 轉錄檔（Session Storage）」與「磁碟檔案系統快照（File Checkpointing）」；LangGraph 則在圖執行的每個 Super-step 邊界透過 `BaseCheckpointSaver` 將完整圖狀態（State Channels、待執行節點與中斷狀態）寫入資料庫；LangChain 直接建構於 LangGraph 的 `checkpointer`（短期對話記憶）與 `BaseStore`（跨執行緒長期記憶）之上；Deep Agents 則進一步結合 LangGraph 持久化與可插拔的檔案系統後端（`BackendProtocol`）。

## 重點

### 1. 各框架持久化與檢查點機制總覽對照
| 維度 | Claude Agent SDK (`agent-sdk`) | LangGraph (`langgraph`) | LangChain (`langchain`) | Deep Agents (`deepagents`) |
|---|---|---|---|---|
| **核心儲存標的** | 1. 對話轉錄檔（JSONL）<br>2. 受追蹤工具修改之磁碟檔案備份 | 圖狀態快照（`StateSnapshot`：包含所有狀態通道值、下一節點、中斷與待寫入資料） | `AgentState`（含 `messages` 與自訂狀態欄位）及跨執行緒 `BaseStore` 文件 | 圖狀態（`messages`、`todos`、`files`）＋虛擬或實體檔案系統（`BackendProtocol`） |
| **啟用參數** | 對話預設自動存檔；檔案檢查點需設定 `enable_file_checkpointing=True` / `enableFileCheckpointing: true` 並設定環境變數 `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING=1` | `graph.compile(checkpointer=...)` 與執行時傳入 `config={"configurable": {"thread_id": "..."}}` | `create_agent(..., checkpointer=..., store=...)` 並於執行時傳入 `thread_id` | `create_deep_agent(..., checkpointer=..., store=..., backend=...)` |
| **預設儲存位置 / 實作** | 本地端 `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl` | 需顯式提供 `InMemorySaver`、`SqliteSaver`、`PostgresSaver` 等（LangGraph Server 部署時自動託管） | 需顯式提供 `InMemorySaver` / `PostgresSaver` 等 | 預設使用 `StateBackend`（存在圖狀態內）；可配置 `StoreBackend`、`FilesystemBackend`、`CompositeBackend` |
| **回溯（Rewind / Time Travel）標的** | `rewind_files(user_message_id)` / `rewindFiles(userMessageId)`：**僅還原磁碟上的檔案內容**，不會回退對話訊息；回退對話需用 `resume` + `fork_session` | 透過 `get_state_history(config)` 取得歷史 `checkpoint_id`，以 `update_state()` 或傳入舊 `checkpoint_id` 重新 `invoke`/`stream` **分叉圖狀態與對話** | 同 LangGraph（前端 SDK 支援 `stream.history`、`useMessageMetadata` 與 `forkFrom`） | 同 LangGraph，且若使用 `StateBackend`，虛擬檔案系統 `/workspace` 會隨圖狀態檢查點一併回溯 |

### 2. Claude Agent SDK：Session Storage 與 File Checkpointing 雙軌機制
- **工作階段持久化（Session Persistence）**：
  - 每次查詢預設將完整訊息寫入 `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`（`<encoded-cwd>` 將工作目錄絕對路徑中所有非英數字元替換為 `-`）。
  - 接續與分叉：使用 `continue_conversation=True`（TS：`continue: true`）接續最近一次對話；使用 `resume="<session-id>"` 接續指定工作階段；搭配 `fork_session=True`（TS：`forkSession: true`）或呼叫 `fork_session()` / `forkSession()` 從既有歷史分叉出新 `session_id`，保留原工作階段不變。
  - 查詢歷史 API：`list_sessions()` / `listSessions()`、`get_session_info()` / `getSessionInfo()`、`get_session_messages()` / `getSessionMessages()`。
- **檔案檢查點（File Checkpointing）**：
  - 僅追蹤透過 `Write`、`Edit`、`NotebookEdit` 三個內建工具所做的檔案修改（**不追蹤** `Bash` 指令如 `echo >`、`rm`、`mv`、`cp` 所做的變動，亦不追蹤遠端系統或外部程序變動）。
  - Python 啟用步驟：設定環境變數 `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING=1`，在 `ClaudeAgentOptions` 中傳入 `enable_file_checkpointing=True` 以及 `extra_args={"replay-user-messages": None}`（以便在回應串流中收到帶有 `uuid` 的 `UserMessage` 作為檢查點 ID）。
  - TypeScript 啟用步驟：設定 `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING=1` 並在 `Options` 設定 `enableFileCheckpointing: true`。
  - 呼叫還原：必須在活躍的串流工作階段內呼叫 `await client.rewind_files(checkpoint_id)`（Python）或 `await response.rewindFiles(checkpointId)`（TypeScript）；若工作階段已結束，可先以 `resume=session_id` 搭配空提示詞重開連線後再呼叫還原。

### 3. LangGraph 與 LangChain：`BaseCheckpointSaver` 與 Super-step 檢查點
- **檢查點建立時機**：LangGraph 在輸入處理後及每一個 **Super-step（超步）** 邊界自動儲存一個 `Checkpoint`。同一 Super-step 中平行執行的節點共享同一個檢查點邊界。
- **檢查點識別與結構**：
  - 由 `thread_id`（必填，代表對話或執行緒）、`checkpoint_ns`（子圖命名空間，根圖為 `""`）與 `checkpoint_id`（單一檢查點 UUID）唯一識別。
  - `StateSnapshot`（TS 為 `ThreadState`）包含：`values`（當前狀態通道值）、`next`（下一輪待執行節點元組）、`config`、`metadata`（含 `source`、`writes`、`step`）、`created_at`、`parent_config`（上一檢查點設定）與 `tasks`（含節點名稱、錯誤與 `interrupts`）。
- **容錯待寫入（Pending Writes / Fault Tolerance）**：若同一 Super-step 中節點 A 成功但平行節點 B 失敗，checkpointer 會透過 `put_writes` 記錄節點 A 的暫存寫入；從該檢查點恢復時，節點 A **不會重新執行**，僅重跑失敗的節點 B。
- **持久化耐用度模式（Durability Modes）**：支援 `"exit"`（僅在圖結束、錯誤或中斷時寫入檢查點，效能最佳）、`"async"`（預設，進入下一步同時非同步寫入檢查點）與 `"sync"`（每步同步等待檢查點寫入完成後才繼續，耐用度最高）。
- **官方 Checkpointer 實作**：`InMemorySaver`（別名 `MemorySaver`）、`SqliteSaver` / `AsyncSqliteSaver`（`langgraph-checkpoint-sqlite`）、`PostgresSaver` / `AsyncPostgresSaver`（`langgraph-checkpoint-postgres` / `@langchain/langgraph-checkpoint-postgres`，首次使用須呼叫 `.setup()` 建立資料表）、`CosmosDBSaver`，並支援 `EncryptedSerializer.from_pycryptodome_aes()`（搭配環境變數 `LANGGRAPH_AES_KEY`）加密狀態。

### 4. Deep Agents：`BackendProtocol` 檔案系統持久化與路由
- Deep Agents 除了繼承 LangGraph 的 `checkpointer` 與 `store` 外，針對檔案操作工具（`ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`）提供四種可組合的儲存後端：
  1. **`StateBackend`（預設）**：將檔案存入 LangGraph 的代理狀態（`state["files"]`）中。搭配 `checkpointer` 時具備單一 `thread_id` 內的持久化與時間旅行能力，但無法跨執行緒共享。
  2. **`StoreBackend`**：將檔案存入 LangGraph 的 `BaseStore`（如 `InMemoryStore` 或 `PostgresStore`），可透過 `namespace` 工廠函式（如依 `user_id` 或 `assistant_id` 隔離）實現跨執行緒（Cross-thread）持久化。
  3. **`FilesystemBackend`**：直接讀寫本地磁碟目錄（建議設定 `virtual_mode=True` 將路徑限制於 `root_dir` 內並阻擋路徑穿越）。
  4. **`CompositeBackend`**：依路徑前綴將不同目錄路由至不同後端（例如預設走 `StateBackend` 作為單次任務暫存 `/workspace/`，而將 `/memories/` 路由至 `StoreBackend` 作為跨對話長期記憶）。

## 相關頁面
- [[concepts/agent-sdk-file-checkpointing]]
- [[concepts/agent-sdk-sessions]]
- [[concepts/langgraph-persistence-and-checkpointers]]
- [[concepts/langgraph-interrupts-and-time-travel]]
- [[concepts/langchain-memory-and-context-engineering]]
- [[concepts/deepagents-backends-and-sandboxes]]
- [[guides/langchain-frontend-hitl-and-state-management]]

## 出處
- docs/agent-sdk/file-checkpointing.md
- docs/agent-sdk/sessions.md
- docs/agent-sdk/session-storage.md
- docs/langgraph/persistence.md
- docs/langgraph/checkpointers.md
- docs/langgraph/use-time-travel.md
- docs/langgraph/fault-tolerance.md
- docs/langchain/short-term-memory.md
- docs/langchain/long-term-memory.md
- docs/deepagents/backends.md
- docs/deepagents/going-to-production.md
