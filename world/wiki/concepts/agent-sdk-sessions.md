# Agent SDK Sessions and External Session Storage

別名：工作階段與對話持久化、Sessions、Session Storage、SessionStore、恢復對話、分叉工作階段、JSONL Transcripts
框架：agent-sdk

## 摘要
Agent SDK 的工作階段（Session）會自動將代理人的對話歷史（包含使用者提示詞、每次工具呼叫、每個工具執行結果與每次回應）寫入磁碟的 JSONL 紀錄檔（Transcript），讓後續執行能帶著完整脈絡（已讀取的檔案、已執行的分析與決策）繼續、恢復或分叉對話。工作階段僅持久化「對話歷史」而不包含檔案系統快照（還原檔案變更需搭配 File Checkpointing）。若需在無狀態環境、Serverless 或多主機部署間共享工作階段，可透過 `SessionStore` 介面將對話紀錄雙寫鏡像（Mirror）至外部物件儲存（如 S3）、鍵值儲存（如 Redis）或資料庫（如 Postgres）。

## 重點

### 工作階段策略選擇（Choose an approach）
- **單次任務（One-shot task，單一提示詞無後續追問）**：直接呼叫單一 `query()` 即可；在單一 `query()` 呼叫內，代理人會自行執行所需的多個回合（Turns），且權限提示與 `AskUserQuestion` 皆在迴圈內處理（不會結束該次呼叫）。
- **單一行程內的多輪對話（Multi-turn chat in one process）**：Python 使用 `ClaudeSDKClient`；TypeScript 在後續 `query()` 設 `continue: true`。SDK 會自動追蹤工作階段，無需手動處理 ID。
- **行程重啟後接續上次進度（Pick up where you left off after a process restart）**：Python 設定 `continue_conversation=True`；TypeScript 設定 `continue: true`。自動恢復當前目錄中最近一次的工作階段，無需提供 ID。
- **恢復特定歷史工作階段（Resume a specific past session）**：擷取 Session ID 並傳給 `resume` 選項（適用於多使用者應用程式每位使用者一個工作階段，或非最近一次的工作階段）。
- **嘗試替代方案同時保留原對話（Try an alternative approach）**：分叉（Fork）工作階段（`fork_session=True` / `forkSession: true`）。
- **無狀態任務、不寫入磁碟（Stateless task）**：
  - TypeScript：設定 `persistSession: false`（僅存在於記憶體中，呼叫結束即釋放；Python SDK 無此對應選項）。
  - Python：在 `env` 選項中設定環境變數 `CLAUDE_CODE_SKIP_PROMPT_HISTORY` 以抑制對話紀錄（Transcript）寫入磁碟。

### Continue、Resume 與 Fork 選項對照
這些選項設定於 `query()` 的設定物件（Python 為 `ClaudeAgentOptions`，TypeScript 為 `Options`）：
- **Continue（`continue_conversation=True` / `continue: true`）**：自動尋找當前目錄中最近一次的工作階段並繼續附加內容，無需追蹤 ID，適合同時僅執行單一對話的應用。
- **Resume（`resume=session_id` / `resume: sessionId`）**：指定特定 Session ID 接續既有工作階段並附加內容。常見用途：
  - 在已完成分析的任務上追問後續實作，無需重新讀取檔案。
  - 從 `error_max_turns` 或 `error_max_budget_usd` 限制中恢復（在單次 `query()` 中 SDK 會在產出錯誤結果訊息後拋出例外，需先 `try/except` 或 `try/catch` 捕捉錯誤並擷取 `session_id`，再提高上限並用 `resume` 恢復）。
  - 行程重啟後還原對話。
- **Fork（`resume=session_id, fork_session=True` / `resume: sessionId, forkSession: true`）**：建立一個全新的工作階段，起點為原始工作階段歷史紀錄的複本，並從該點分岔（Diverge）。
  - 分叉後的工作階段會取得全新的獨立 `session_id`（與原始 `session_id` 不同），原始工作階段的 ID 與歷史紀錄保持不變，兩者可各自獨立 `resume`。
  - **注意**：Fork 僅分叉對話歷史，不會分叉檔案系統。若分叉後的代理人修改了檔案，這些變更在同目錄下對所有工作階段皆為真實可見；若需連同檔案變更還原，請搭配 File Checkpointing。

### 自動工作階段管理與 ID 擷取
- **Python `ClaudeSDKClient`**：
  - 在內部自動管理 Session ID。透過 `async with ClaudeSDKClient(options=options) as client:`（或手動呼叫 `connect()` 與 `disconnect()`），每次呼叫 `await client.query(...)` 並以 `async for message in client.receive_response():` 迭代回應，第二次呼叫 `client.query(...)` 會自動延續同一個工作階段脈絡。
- **TypeScript `continue: true`**：
  - TypeScript SDK 沒有像 Python `ClaudeSDKClient` 這樣保存狀態的 Client 物件，而是在後續每次 `query()` 的 `options` 傳入 `continue: true`。
  - 實驗性的 V2 Session API（提供 `createSession()` 與 `send` / `stream` 模式）已於 TypeScript Agent SDK `0.3.142` 移除，應改用 `query()` 與上述工作階段選項。
- **擷取 Session ID（`session_id`）**：
  - 可從結果訊息（Python 的 `ResultMessage.session_id`、TypeScript 的 `SDKResultMessage` 即 `message.type === "result"` 的 `message.session_id`）讀取，無論成功或錯誤結果皆包含此欄位（但若發生連線或子行程啟動失敗則不會產出結果訊息，`session_id` 維持 `None` / `undefined`）。
  - 在初始化系統訊息中亦可提早取得：TypeScript 為 `message.type === "system" && message.subtype === "init"` 上的直接欄位 `message.session_id`；Python 則巢狀於 `SystemMessage.data` 內。

### 本機儲存路徑、目錄編碼規則與跨目錄查找
- **預設儲存位置**：`~/.claude/projects/<encoded-cwd>/*.jsonl`（即 `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`）。
- **環境變數覆寫**：
  - 若設定 `CLAUDE_CONFIG_DIR` 環境變數，則儲存在 `$CLAUDE_CONFIG_DIR/projects/` 下。
  - 若除了 `CLAUDE_CONFIG_DIR` 外還設定了 `CLAUDE_CODE_PROJECT_DIR_NAME`，則會改用該名稱作為 `projects/` 下的子目錄名稱（同時影響 `SessionStore` 的 `projectKey` 以及 `resume` / `continue` 查找鍵；需 TypeScript Agent SDK `v0.3.234` 以上或 Python Agent SDK `v0.2.140` 以上）。注意：在 TypeScript 中，獨立輔助函式如 `listSessions` 與 `deleteSession` 不接受 `env` 參數而是直接讀取宿主行程環境變數，因此也必須在宿主行程環境中設定 `CLAUDE_CONFIG_DIR` 與相同的 `CLAUDE_CODE_PROJECT_DIR_NAME`。
- **目錄編碼規則（`<encoded-cwd>`）**：
  - 將絕對工作目錄路徑中的每一個非英數字元（non-alphanumeric character）替換為 `-`。
  - 當轉換後的名稱超過 `200` 個字元時，Claude Code 會截斷名稱並在後方附加雜湊值（Hash），因此列舉 `projects/` 時應比對轉換後名稱的前 `200` 個字元。
- **跨目錄查找（Cross-directory lookup）與版本行為**：
  - 可從任何工作目錄透過 `resume` 恢復工作階段：Claude Code 會搜尋當前專案目錄以外的位置來尋找該 Session ID（但該 JSONL 檔案仍必須存在於同一台機器上）。
  - 在 Claude Code `v2.1.223` 之前，查找範圍僅限於當前專案目錄及其 git worktrees（封裝舊版 CLI 的 SDK 版本仍維持此舊行為）。

### 本機與 Store 工作階段管理輔助函式
- **列舉與讀取訊息**：
  - TypeScript：`listSessions()`、`getSessionMessages()`、`listSubagents()`、`getSubagentMessages()`。
  - Python（本機檔案）：`list_sessions()`、`get_session_messages()`。
  - Python（針對 `SessionStore`）：`list_sessions_from_store()`、`get_session_messages_from_store()`、`list_subagents_from_store()`、`get_subagent_messages_from_store()`。
- **查詢單一資訊、重新命名、標籤、刪除與分叉**：
  - TypeScript（皆支援在參數物件中傳入 `{ sessionStore }` 改對 Store 操作，以及 `query()` 與 `startup()`）：`getSessionInfo()`、`renameSession()`、`tagSession()`、`deleteSession()`、`forkSession()`。
  - Python（本機檔案）：`get_session_info()`、`rename_session()`、`tag_session()`。
  - Python（針對 `SessionStore`，無 `startup()` 對應函式）：`get_session_info_from_store()`、`rename_session_via_store()`、`tag_session_via_store()`、`delete_session_via_store()`、`fork_session_via_store()`。

### 外部儲存介面：`SessionStore`（`session-storage.md`）
- **匯出型別**：由 `@anthropic-ai/claude-agent-sdk`（TypeScript）與 `claude_agent_sdk`（Python）匯出 `SessionStore`、`SessionKey`、`SessionStoreEntry`、`SessionSummaryEntry`，以及內建供開發測試使用的 `InMemorySessionStore`。
- **`SessionKey` 結構**：
  - TypeScript：`{ projectKey: string; sessionId: string; subpath?: string }`。
  - Python（`TypedDict`）：`project_key: str`、`session_id: str`、`subpath: NotRequired[str]`。
  - `projectKey` / `project_key` 為工作目錄的穩定檔案系統安全編碼；`sessionId` / `session_id` 為工作階段 UUID；`subpath` 在條目屬於子代理人對話紀錄（例如 `"subagents/agent-<id>"`）或 Sidecar 檔案時設定，若為 `undefined` 則代表主對話紀錄。
- **`SessionStore` 方法契約（2 個必要、4 個選用）**：
  1. `append(key, entries)`（**必要**）：在每批對話紀錄條目寫入本機磁碟後呼叫。`entries` 為 `SessionStoreEntry`（`{ type: string; ... }` JSON-safe 物件，對應本機 JSONL 每行一個物件）。
  2. `load(key)`（**必要**）：當設定 `resume` 或 `continue: true` 解析最新 Store 工作階段時在子行程啟動前呼叫，以及當 `listSessions` 缺少 `listSessionSummaries` 而退回逐一載入時呼叫。若工作階段不存在應回傳 `null` / `None`；回傳的條目陣列順序必須與 `append` 時相同且內容 deep-equal（不要求 byte-equal，允許如二進位 JSON 欄位重排物件鍵順序）。
  3. `listSessions(projectKey)` / `list_sessions(project_key)`（選用）：回傳 `{ sessionId: string; mtime: number }[]`（Python 為 `list[SessionStoreListEntry]`）。由 `listSessions({ sessionStore })` 及搭配 `continue: true` 的 `query()` / `startup()` 呼叫。若未實作，`continue: true` 會拋出錯誤，且 `listSessions({ sessionStore })` 除非有實作 `listSessionSummaries` 否則也會拋出錯誤。
  4. `listSessionSummaries(projectKey)` / `list_session_summaries(project_key)`（選用）：回傳 `SessionSummaryEntry[]`（包含 `sessionId` / `session_id`、`mtime: number / int`、`data: Record<string, unknown> / dict[str, Any]`），讓 `listSessions({ sessionStore })` 能以單次呼叫讀取所有工作階段中繼資料。若未實作，列舉時會退回呼叫 `listSessions` 再對每個工作階段呼叫 `load`。
     - 實作方式：在 `append` 內對每個批次呼叫匯出的純函式 `foldSessionSummary`（TypeScript）/ `fold_session_summary`（Python）來建構摘要條目。必須跳過含有 `subpath` 的批次（子代理人紀錄不得計入主工作階段摘要）。Fold 函式不會設定 `mtime`，必須在持久化時蓋上時間戳（TypeScript 透過 `options.mtime` 參數，Python 則覆寫回傳條目上的 `mtime` 欄位），且該 `mtime` 必須與 `listSessions` 回傳的 `mtime` 共用時鐘來源。因同一工作階段可能發生並行 `append` 競爭 Sidecar，需使用交易（Transaction）、Compare-and-Swap（CAS）或每工作階段鎖（Per-session lock）序列化 read-fold-write 流程。
  5. `delete(key)`（選用）：由 `deleteSession({ sessionStore })` 呼叫。刪除主鍵（無 `subpath`）時，**必須連動刪除（Cascade）該工作階段的所有子鍵（subkeys）並移除其 summary 條目**，使其不再出現於 `listSessionSummaries`。若未實作則刪除為 no-op（適合 append-only 後端）。
  6. `listSubkeys(key)` / `list_subkeys(key)`（選用）：在 `resume` 期間用於探索子代理人紀錄（以及供 `listSubagents({ sessionStore })` 使用；`getSubagentMessages({ sessionStore })` 有實作時會使用，未實作則直接退回讀取 subpath）。若未實作，`resume` 時僅會還原主對話紀錄。

### 雙寫架構（Dual-write architecture）與行為細節
- **本機優先雙寫**：Claude Code 子行程永遠先把每批紀錄寫入本機磁碟，SDK 再轉發給 `store.append()`。
  - **全新工作階段，或 `resume` 時 Store 內無該工作階段資料**：本機設定目錄下的紀錄檔在執行結束後會保留，Store 也會收到一份複本。若不希望全新工作階段在本機留下檔案，可在 `options.env` 將 `CLAUDE_CONFIG_DIR` 設為新的私有暫存目錄（TypeScript 注意 `env` 會取代整個子行程環境，需一併展開 `...process.env`）。
  - **從 Store 恢復的執行（Resumed from the store）**：SDK 在啟動子行程前先向 Store 查詢（`resume` 查指定 ID；`continue: true` / `continue_conversation=True` 查 Store 中最新的工作階段），將取得的紀錄寫入暫存設定目錄並把 `CLAUDE_CONFIG_DIR` 指向該處，執行結束時**自動刪除該暫存目錄與本機紀錄檔**，因此 Store 保存唯一持久複本。
- **暫存設定目錄的憑證複製差異**：
  - 當使用私有暫存 `CLAUDE_CONFIG_DIR` 時，若使用 claude.ai 登入或使用者 `settings.json` 中的 `apiKeyHelper`，全新工作階段可能會因找不到憑證而出現 `Not logged in` 錯誤；解決方式為在 `env` 設定長效 Token `CLAUDE_CODE_OAUTH_TOKEN`（由 `claude setup-token` 產生，僅能發送模型請求，無法使用 claude.ai connectors）、設定 `ANTHROPIC_API_KEY`，或手動將設定檔複製至暫存目錄。
  - 當從 Store 恢復（SDK 自動建立暫存目錄）時，SDK 會從真實設定目錄複製種子檔案：
    - **TypeScript**：複製憑證（credentials）、`.claude.json` 與使用者的 `settings.json`，並從 `settings.json` 移除在暫存目錄下會異常的鍵：`enabledPlugins`、`extraKnownMarketplaces`、其別名 `additionalMarketplaces`（`v0.3.232` 起才移除別名；`v0.3.222` 之前僅複製 credentials 與 `.claude.json`），以及檔案 `env` 區塊內的任何 `CLAUDE_CONFIG_DIR`。因此設定在 `settings.json` 的 `apiKeyHelper` 在 TypeScript 從 Store 恢復時可正常運作。
    - **Python**：僅複製憑證（credentials）與 `.claude.json`，**不複製使用者 `settings.json`**，因此透過使用者 `settings.json` 的 `apiKeyHelper` 驗證的應用程式在從 Store 恢復時會以 `Not logged in` 失敗（但設定在 managed 或 project settings 中的 `apiKeyHelper` 仍可運作，因為其路徑不受 `CLAUDE_CONFIG_DIR` 影響）。
- **當 Store 查無該工作階段時的退回行為**：
  - SDK 改在真實設定目錄下執行：`resume` 在兩種語言皆將 ID 傳給子行程以恢復本機紀錄；`continue: true`（TypeScript）會開啟全新工作階段；`continue_conversation=True`（Python）則會接續本機最新的工作階段。
- **與 `SessionStore` 衝突的選項（啟動時直接拋出錯誤）**：
  1. TypeScript 的 `persistSession: false`（關閉了雙寫鏡像依賴的本機寫入）。
  2. 檔案檢查點 `enableFileCheckpointing`（TypeScript）/ `enable_file_checkpointing`（Python）（檔案備份直接寫入本機磁碟，不會鏡像至 Store）。
- **Best-effort 鏡像寫入與重試去重**：
  - 若 `append()` 失敗（reject），SDK 會以短暫 backoff 重試最多 2 次（總計最多 **3 次嘗試**）；但若呼叫逾時（timeout）則**不會重試**（因原請求仍可能成功寫入）。
  - 由於重試可能重複送出已寫入的條目，實作 `append()` 時應依據 `entry.uuid` 進行去重（Deduplicate），並保留所有沒有 `uuid` 的條目。
  - 若 3 次皆失敗，SDK 會記錄錯誤、在回應串流中發出 `{ type: "system", subtype: "mirror_error" }` 訊息、丟棄該批次並繼續執行查詢（不會中斷代理人）。應監控 `mirror_error` 以偵測資料遺失（特別是從 Store 恢復的執行在結束後會刪除本機複本）。
- **其他重要語意**：
  - **`getSessionMessages` 回傳壓縮後鏈結**：`getSessionMessages({ sessionStore })` 回傳代理人恢復時實際看到的訊息鏈（Post-compaction chain）；自動壓縮（Auto-compaction）後早期回合會被摘要取代（例如 Store 存有 503 筆原始條目，可能僅回傳 18 則訊息）。若需完整原始歷史與中繼資料，請直接呼叫 `store.load(key)`。
  - **`forkSession` 非位元組複製**：`forkSession({ sessionStore })` 會讀取來源條目、改寫每個 `sessionId` 欄位並重新映射訊息 UUID 後，再以新鍵呼叫 `append`（不可在 Adapter 層使用 `CopyObject` 等捷徑，否則內部仍會指向舊 Session ID）。
  - **資料保留（Retention）**：SDK 絕不會主動刪除 Store 內的資料；Store 的過期與清理完全由 Adapter 端負責。本機 `CLAUDE_CONFIG_DIR` 下的紀錄則獨立由 `cleanupPeriodDays` 設定定期清理。
- **官方參考實作與相容性測試套件（Conformance Suite）**：
  - 兩語言儲存庫於 `examples/session-stores/`（TypeScript）與 `examples/session_stores/`（Python）提供三種參考實作：**S3**（物件儲存，每次 `append()` 寫一個 part 檔，`load()` 列出排序並串接）、**Redis**（鍵值儲存，每個紀錄一個 list 搭配排序索引）、**Postgres**（關聯式/文件資料庫，每筆條目一列 JSON 並依插入分配的鍵排序）。
  - 驗證自訂 Adapter：TypeScript 可複製 `examples/session-stores/shared/conformance.ts`；Python 內建於套件 `claude_agent_sdk.testing` 的 `run_session_store_conformance`，搭配 `pytest`（`@pytest.mark.anyio`）傳入零參數工廠函式或類別進行合約驗證。

## 相關頁面
- [[concepts/agent-sdk-file-checkpointing]]
- [[concepts/agent-sdk-streaming]]
- [[guides/agent-sdk-hosting-and-security]]
- [[versions/agent-sdk-migration-and-v2-preview]]

## 出處
- docs/agent-sdk/sessions.md
- docs/agent-sdk/session-storage.md
