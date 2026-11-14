# Agent SDK File Checkpointing

別名：檔案檢查點、檔案還原、Rewind Files、File Checkpointing、時光機還原、檔案快照
框架：agent-sdk

## 摘要
File Checkpointing（檔案檢查點）會在代理工作階段期間追蹤透過 `Write`、`Edit` 與 `NotebookEdit` 工具所做的檔案修改，並在修改前建立檔案備份，讓開發者能將磁碟上的檔案還原（Rewind）至先前任一提示詞回合（Turn）開始時的狀態。每個啟動新回合的使用者提示詞都是一個檢查點，並以該 `UserMessage` 的 `uuid` 作為還原點識別碼。注意：檔案還原僅將磁碟上的檔案恢復至先前狀態，**不會**倒退對話歷史與脈絡（對話紀錄維持原狀）。

## 重點

### 追蹤範圍與運作原理
- **受追蹤的工具**：僅追蹤主對話中透過 `Write`、`Edit`、`NotebookEdit` 三個工具進行的檔案修改與建立。
- **不追蹤的操作（警告與限制）**：
  - **Bash 指令修改**：`rewindFiles()` / `rewind_files()` **不會**復原 `sed -i` 或其他 Bash 指令對檔案所做的變更（除非主對話先前已經透過 `Write` 或 `Edit` 等工具修改過該檔案）。
  - **子代理人（Subagent）編輯**：子代理人的檔案修改不被追蹤，**唯一例外**是在前景（foreground）執行的 `context: fork` 技能（Skill）。還原時僅會復原主對話也編輯過的檔案，其餘子代理人變更需使用 git 還原。
  - **同工作階段綁定（Same session）**：檢查點綁定於建立它們的工作階段。
  - **僅限檔案內容（File content only）**：建立、搬移或刪除目錄（Directories）的操作不會被還原。
  - **僅限本機檔案（Local files）**：遠端或網路檔案不被追蹤，且與外部 `SessionStore` 不相容（同時啟用會在啟動時拋出錯誤）。
- **還原行為與連結跳過機制（`skippedLinks`）**：
  - 還原至某檢查點時，Claude Code 會刪除在該檢查點之後建立的檔案，並將修改過的檔案內容還原至該時間點的狀態。
  - 自 Claude Code `v2.1.216` 起（`v2.1.216` 之前會直接穿透連結寫入或刪除），還原時會自動跳過符號連結（symlink）、硬連結（hard link）或其他非一般檔案（non-regular file），也會跳過父目錄解析結果已與建立檢查點時不同的路徑，或無法安全讀取備份的檔案。
  - TypeScript 的 `RewindFilesResult` 會在 `skippedLinks` 欄位中統計所有被跳過的路徑數量。

### 啟用與實作三步驟
1. **步驟一：啟用檢查點與接收使用者訊息 UUID**
   - Python（`ClaudeAgentOptions`）：
     - `enable_file_checkpointing=True`：啟用檔案變更追蹤與備份。
     - `extra_args={"replay-user-messages": None}`：**必要設定**，使回應串流中包含使用者訊息及其檢查點 `uuid`。
     - 範例中通常搭配 `permission_mode="acceptEdits"` 以自動核准檔案編輯。
   - TypeScript（`Options`）：
     - `enableFileCheckpointing: true`
     - `extraArgs: { "replay-user-messages": null }`
     - 可搭配 `permissionMode: "acceptEdits" as const`。
2. **步驟二：從回應串流擷取檢查點 UUID 與 Session ID**
   - 設定 `replay-user-messages` 後，每個啟動回合的使用者提示詞訊息都會帶有 `message.uuid` 作為檢查點。
   - **重要區分**：攜帶工具執行結果（Tool results）的使用者訊息雖然也有 `uuid`，但**不是檢查點**！
     - 若只擷取第一個使用者訊息（`if not checkpoint_id:`），直接讀取第一個 `UserMessage` 的 `message.uuid` 即可（還原至該點會將所有受追蹤檔案恢復為初始狀態）。
     - 若在多輪對話中更新最新安全檢查點或記錄多個還原點，必須過濾掉工具結果訊息：
       - Python：`isinstance(message, UserMessage) and message.uuid and message.tool_use_result is None and message.parent_tool_use_id is None`
       - TypeScript：`message.type === "user" && "isReplay" in message && message.isReplay && message.uuid`
   - 擷取 `message.session_id`：若打算在回應串流結束後才執行還原，必須保存 `session_id`；若在同一個回應串流迴圈處理期間立即呼叫 `rewindFiles()` / `rewind_files()`（例如偵測到風險或驗證失敗時立即還原並 `break`），則無需保存 `session_id`。
3. **步驟三：執行檔案還原（Rewind files）**
   - **串流進行中立即還原（Checkpoint before risky operations）**：在回應迭代迴圈內直接呼叫 `await client.rewind_files(safe_checkpoint)`（Python）或 `await response.rewindFiles(safeCheckpoint)`（TypeScript），隨後 `break` 離開迴圈。
   - **串流結束後事後還原（Resume with empty prompt）**：
     - 因為串流迴圈結束時與 CLI 子行程的連線即關閉，必須使用 `resume=session_id`（Python）/ `resume: sessionId`（TypeScript）**並同樣開啟 `enable_file_checkpointing=True` / `enableFileCheckpointing: true`** 重新啟動查詢。
     - 傳入**空字串提示詞 `""`**（`await client.query("")` 或 `query({ prompt: "", options: { ...opts, resume: sessionId } })`）以開啟連線，在回應迴圈收到第一則訊息時呼叫 `await client.rewind_files(checkpoint_id)` / `await rewindQuery.rewindFiles(checkpointId)` 並立即 `break`。
   - **透過 CLI 直接還原**：
     - 若已安裝 Claude Code CLI（`claude` 執行檔）並擁有 `session-id` 與 `checkpoint-uuid`，可在終端機直接執行：
       `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING=true claude -p --resume <session-id> --rewind-files <checkpoint-uuid>`
     - 注意：`--rewind-files` 旗標不會顯示在 `claude --help` 輸出中，但 CLI 支援此參數；還原成功時會印出 `Files rewound to state at message <checkpoint-uuid>` 並直接退出而不發送提示詞。裸執行 CLI 時必須顯式設定環境變數 `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING=true`（SDK 在設定 `enable_file_checkpointing` / `enableFileCheckpointing` 時會在內部自動設定該環境變數）。

### 常見錯誤與疑難排解（Troubleshooting）
- **無法識別 `enableFileCheckpointing` 或 `rewindFiles()`**：SDK 版本過舊，請升級至最新版（Python：`pip install --upgrade claude-agent-sdk`；TypeScript：`npm install @anthropic-ai/claude-agent-sdk@latest`）。
- **使用者訊息沒有 `uuid`（`message.uuid` 為 `undefined` 或遺失）**：未設定 `replay-user-messages`，請在選項加入 `extra_args={"replay-user-messages": None}`（Python）或 `extraArgs: { 'replay-user-messages': null }`（TypeScript）。
- **`"No file checkpoint found for this message"` 錯誤**：
  - 原因：原始工作階段未啟用 `enable_file_checkpointing` / `enableFileCheckpointing`；或工作階段尚未完整結束就嘗試 `resume` 並還原；或誤拿了攜帶工具結果（tool result）的使用者訊息 UUID 當作檢查點。
- **`"File rewinding is not enabled"` 錯誤**：
  - 原因：執行非互動式還原時未啟用檢查點（例如裸執行 `claude -p --rewind-files` 未設 `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING=true`，或在 `resume` 執行還原的 SDK 選項中漏設 `enable_file_checkpointing=True` / `enableFileCheckpointing: true`）。
- **`"ProcessTransport is not ready for writing"` 錯誤**：
  - 原因：在回應串流迴圈已經迭代結束、CLI 行程連線已關閉之後，才對舊的 client / query 物件呼叫 `rewindFiles()` / `rewind_files()`。解決方式為搭配 `resume` 與空提示詞 `""` 開啟新查詢並在迴圈內呼叫還原。

## 相關頁面
- [[concepts/agent-sdk-sessions]]
- [[concepts/agent-sdk-permissions]]
- [[guides/agent-sdk-observability-and-troubleshooting]]

## 出處
- docs/agent-sdk/file-checkpointing.md
