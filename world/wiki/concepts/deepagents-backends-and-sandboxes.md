# Deep Agents Backends, Sandboxes & Permissions

別名：檔案系統後端與沙盒、`BackendProtocol`、`SandboxBackendProtocol`、`StateBackend`、`FilesystemBackend`、`StoreBackend`、`LocalShellBackend`、`ContextHubBackend`、`CompositeBackend`、`BaseSandbox`、`FilesystemPermission`
框架：deepagents

## 摘要
Deep Agents 透過可插拔的後端協定（`BackendProtocol` / `BackendProtocolV2`）為代理提供虛擬檔案系統工具（`ls`、`read_file`、`write_file`、`edit_file`、`delete`、`glob`、`grep`），並在實作 `SandboxBackendProtocol`（或 `LocalShellBackend`）時額外啟用 `execute` shell 工具。開發者可組合執行緒範圍的 `StateBackend`、本地磁碟 `FilesystemBackend`、跨執行緒持久化的 `StoreBackend`、LangSmith `ContextHubBackend`、多路由 `CompositeBackend` 與遠端隔離沙盒（Sandboxes），並搭配宣告式 `FilesystemPermission` 規則或後端政策鉤子（policy hooks）進行細粒度存取控制。

## 重點
### 內建檔案系統後端（Built-in Backends）
- **`StateBackend`（預設後端）**：
  - 將檔案儲存於當前執行緒（thread）的 LangGraph agent state 中，透過 checkpointer 跨回合持久化，但**不跨執行緒共享**。
  - 在同一執行緒內由 supervisor 與所有 subagents 共享（子代理寫入的檔案在子代理結束後仍保留在 state 中供主代理與其他子代理存取）。
  - 注意：必須在圖形執行期間使用；在圖形執行外直接呼叫 `state_backend.upload_files(...)` 等方法直到圖形執行時才會生效。
- **`FilesystemBackend`（本地磁碟）**：
  - 直接讀寫指定絕對路徑 `root_dir`（Python `root_dir=` / JS `rootDir`）下的實體檔案，支援安全路徑解析、防止不安全的 symlink 穿越，並可使用 ripgrep 加速 `grep`。
  - **安全性設定 `virtual_mode=True`（Python）/ `virtualMode: true`（JS）**：**務必啟用**以將路徑限制並正規化於 `root_dir` 下（阻擋 `..`、`~` 及根目錄外的絕對路徑）。預設值 `virtual_mode=False` 即使設定了 `root_dir` 也**不提供任何安全隔離**。
  - **最佳實踐（搭配 `CompositeBackend`）**：Deep Agents 會自動將卸載的大型工具結果（寫入 `/large_tool_results/`）與對話歷史（寫入 `/conversation_history/`）寫入預設後端；應將 `StateBackend()` 設為 `CompositeBackend` 的 `default`，並僅將 `/workspace/` 等路由指向 `FilesystemBackend`，避免內部暫存產物污染專案目錄。
- **`LocalShellBackend`（本地端 Shell）**：
  - 繼承 `FilesystemBackend` 並額外提供在主機直接執行 shell 指令的 `execute` 工具（底層使用 `subprocess.run(shell=True)`，無任何沙盒隔離，`virtual_mode=True` 在啟用 shell 存取時無法提供安全保護）。
  - 支援參數：`root_dir`（作為工作目錄）、`timeout`（預設 `120` 秒）、`max_output_bytes`（預設 `100,000` bytes）、`env`（如 `{"PATH": "/usr/bin:/bin"}`）與 `inherit_env`。
- **`StoreBackend`（LangGraph Store 跨執行緒持久化）**：
  - 將檔案儲存於執行階段提供的 LangGraph `BaseStore`（如 Redis、Postgres 或雲端實作；部署至 LangSmith Agent Server 時平台會自動配置 store，應省略 `store` 參數）。
  - **Namespace factories（命名空間工廠，`namespace` 參數）**：
    - 簽名：`NamespaceFactory = Callable[[Runtime], tuple[str, ...]]`（Python 將於 `v0.5.0`、JS 將於 `v1.9.0` 強制要求設定 `namespace`；未提供時的舊版預設行為是使用 LangGraph config metadata 中的 `assistant_id`，導致同一 assistant 的所有使用者共享儲存空間）。
    - 傳入的 LangGraph `Runtime`（Python 需 `deepagents>=0.5.2`，JS 需 `deepagents>=1.9.1`；舊版 `BackendContext` 的 `.runtime` 與 `.state` 存取器已棄用並將於 `deepagents>=0.7` 移除）提供：
      - `rt.context`：使用者透過 context schema 傳入的上下文（如 `user_id`）。
      - `rt.server_info`（Python，需 `>=0.5.0`）/ `rt.serverInfo`（JS，需 `>=1.9.0`）：Agent Server 元資料（含 `rt.server_info.user.identity`、`rt.server_info.assistant_id` / `rt.serverInfo.assistantId`、graph ID）。
      - `rt.execution_info`（Python，需 `>=0.5.0`）/ `rt.executionInfo`（JS，需 `>=1.9.0`）：執行識別資訊（含 `rt.execution_info.thread_id` / `rt.executionInfo.threadId`、run ID、checkpoint ID）。
    - 命名空間字元限制：僅允許英數字元、連字號（`-`）、底線（`_`）、點（`.`）、`@`、`+`、冒號（`:`）與波浪號（`~`）；**拒絕萬用字元（`*`、`?`）**以防止 glob injection。
- **`ContextHubBackend`（LangSmith Context Hub）**：
  - 將代理的檔案系統持久化於 LangSmith Context Hub repo（建構時傳入 `owner/name` 或 `name` 格式，需設定環境變數 `LANGSMITH_API_KEY`）。
  - **Repo 結構**：將 _agent repo_（含 `AGENTS.md`、`tools.json` 等）掛載於檔案系統根目錄 `/`，並將連結的 _skill repos_ 掛載為 `/skills/` 下的子目錄。
  - **運作與限制**：首次使用時延遲拉取（lazy pull）repo 樹狀結構並從記憶體快取提供讀取；寫入與編輯會持久化為樂觀父提交（optimistic `parent_commit`）的 Hub commits 並更新快取（若發生衝突需重新 pull 並重試；若 repo 不存在則首次成功寫入可建立 repo）。`upload_files()` 僅接受 UTF-8 文字，非 UTF-8 檔案會依路徑以 `invalid_path` 拒絕。
- **`CompositeBackend`（多路徑路由器）**：
  - 依路徑前綴（path prefix）將檔案操作路由至不同後端（Python：`CompositeBackend(default=StateBackend(), routes={"/memories/": ...})`；JS：`new CompositeBackend(new StateBackend(), { "/memories/": ... })`）。
  - **最長前綴優先（Longer prefixes win）**：例如 `"/memories/projects/"` 會覆寫 `"/memories/"`。`ls`、`glob`、`grep` 會自動彙整各路由結果並保留原始路徑前綴。
- **自舊版 Backend Factories 遷移（Deprecated）**：
  - 自 Python `deepagents` `0.5.0` 與 JS `1.9.0` 起，傳遞工廠函式（如 `backend=lambda rt: StateBackend(rt)` 或 `backend: (config) => new StateBackend(config)`）已棄用；後端現在會透過 LangGraph 的 `get_config()`、`get_store()` 與 `get_runtime()` 在內部解析上下文，應直接傳入建構好的實例（如 `backend=StateBackend()`）。同时 `WriteResult` / `EditResult` 上的 `files_update`（Python）/ `filesUpdate`（JS）欄位亦已棄用，改由後端內部處理狀態寫入。

### 二進位與多模態檔案處理、二進位內容卸載（Offload Binary Content）
- **二進位內容卸載（Offload binary content，Opt-in）**：
  - 將二進位 `read_file` 負載與使用者訊息中的行內媒體（inline media）儲存於後端而非以 base64 留在訊息歷史中，以縮小 checkpoint 體積。
  - **啟用方式**：Python（需 `deepagents>=0.7.21`）在 `FilesystemMiddleware` 設定 `offload_binary_content=True`；JS（需 `deepagents>=1.14.2`）在 `createFilesystemMiddleware` 設定 `offloadBinaryContent: true`。
  - **儲存路徑**：預設以內容雜湊儲存於 `/blobs/<sha256>`（Python 若在 middleware 設定 `artifacts_root` 則改存於該根目錄下）。注意：**當 `/blobs` 路徑路由至 `StateBackend` 時卸載無效**，必須使用將 blobs 存於圖形狀態外的後端（如 sandbox 或 `FilesystemBackend`）。
- **TypeScript/JS V2 多模態與 `FileData` 格式（需 `deepagents>=1.9.0`）**：
  - V2 後端讀取二進位檔案時，`read()` 回傳的 `ReadResult` 其 `content` 為 `Uint8Array` 且附帶對應 `mimeType`（文字檔則回傳 `string` 與 `"text/plain"` 等）：
    - Images（`.png`, `.jpg`/`.jpeg`, `.gif`, `.webp`, `.svg`, `.heic`, `.heif`）：`image/png`, `image/jpeg`, `image/gif`, `image/webp`, `image/svg+xml`, `image/heic`, `image/heif`
    - Audio（`.mp3`, `.wav`, `.aiff`, `.aac`, `.ogg`, `.flac`）：`audio/mpeg`, `audio/wav`, `audio/aiff`, `audio/aac`, `audio/ogg`, `audio/flac`
    - Video（`.mp4`, `.webm`, `.mpeg`/`.mpg`, `.mov`, `.avi`, `.flv`, `.wmv`, `.3gpp`）：`video/mp4`, `video/webm`, `video/mpeg`, `video/quicktime`, `video/x-msvideo`, `video/x-flv`, `video/x-ms-wmv`, `video/3gpp`
    - Documents（`.pdf`, `.ppt`, `.pptx`）：`application/pdf`, `application/vnd.ms-powerpoint`, `application/vnd.openxmlformats-officedocument.presentationml.presentation`
  - **`FileData` 結構**：v2 格式為 `{ content: string | Uint8Array, mimeType: string, created_at: string, modified_at: string }`；舊版 v1 格式為 `{ content: string[], created_at: string, modified_at: string }`（滾動部署期間若需向下相容可傳入 `new StoreBackend({ fileFormat: "v1" })`）。

### Backend Protocol 協定參考與自訂後端
- **錯誤處理原則**：所有協定方法在失敗時**必須回傳帶有 `error` 欄位的結構化 Result 物件，嚴禁拋出例外（do not raise/throw exceptions）**。
- **Python `BackendProtocol` 方法與型別**：
  - `ls(path: str) -> LsResult(error, entries)`：`entries` 為 `list[FileInfo]`（含必填 `path` 及選填 `is_dir`, `size`, `modified_at`，依 `path` 排序）。
  - `read(file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult(error, file_data)`：檔案不存在時回傳 `ReadResult(error="Error: File '/x' not found")`；成功時 `file_data` 為 `FileData` dict（含 `content`, `encoding` `"utf-8"` 或 `"base64"`, `created_at`, `modified_at`）。
  - `write(file_path: str, content: str) -> WriteResult(error, path, files_update)`：僅限建立新檔（Create-only），衝突時回傳 `error`。
  - `edit(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult(error, path, files_update, occurrences)`：除非 `replace_all=True`，否則強制要求 `old_string` 唯一；成功時包含替換次數 `occurrences`。
  - `glob(pattern: str, path: str | None = None) -> GlobResult(error, matches)`：`matches` 為 `list[FileInfo]`。
  - `grep(pattern: str, path: str | None = None, glob: str | None = None) -> GrepResult(error, matches)`：`matches` 為 `list[GrepMatch]`（含 `path`, `line`, `text`）。
  - `delete(file_path: str) -> DeleteResult`（選填）：若後端未實作刪除，該工具會在請求時自動對模型隱藏。
- **TypeScript/JS `BackendProtocolV2` 方法與 V1 轉接**：
  - 必填方法：`ls(path) -> Promise<LsResult>`、`read(filePath, offset?, limit?) -> Promise<ReadResult>`（文字檔預設 `offset` 0、`limit` 500）、`readRaw(filePath) -> Promise<ReadRawResult>`、`grep(pattern, path?, glob?) -> Promise<GrepResult>`、`glob(pattern, path?) -> Promise<GlobResult>`、`write(filePath, content) -> Promise<WriteResult>`、`edit(filePath, oldString, newString, replaceAll?) -> Promise<EditResult>`。
  - 選填方法（供 sandbox 後端使用）：`uploadFiles(files: Array<[string, Uint8Array]>) -> FileUploadResponse[]`、`downloadFiles(paths: string[]) -> FileDownloadResponse[]`。
  - `SandboxBackendProtocolV2` 擴充欄位與方法：`execute(command: string) -> ExecuteResponse` 與 `readonly id: string`。
  - V1 轉 V2 方法重新命名對照：`lsInfo` -> `ls`、`grepRaw` -> `grep`、`globInfo` -> `glob`。框架會透過 `adaptBackendProtocol()` 與 `adaptSandboxProtocol()` 自動在執行階段轉接 V1 後端。
- **Policy Hooks（後端政策鉤子）**：若需超越路徑規則的自訂驗證（如速率限制、稽核日誌、內容檢查），可繼承特定後端（如 `class GuardedBackend(FilesystemBackend)`）或實作通用包裝器（如 `class PolicyWrapper(BackendProtocol)`）攔截 `write` 與 `edit`。

### 沙盒後端（Sandboxes）
- **架構與 `BaseSandbox`**：
  - 沙盒供應商只需實作唯一的 `execute()` 方法（執行 shell 指令並回傳合併的 stdout/stderr、exit code 及超長截斷提示；若輸出過大，結果會自動存成檔案並指示代理用 `read_file` 分段讀取）。
  - 其餘所有檔案系統操作（`read`, `write`, `edit`, `delete`, `ls`, `glob`, `grep`）皆由基底類別 `BaseSandbox` 建構腳本並透過 `execute()` 在沙盒內執行。
  - 每次模型呼叫時，harness 會檢查後端是否實作 `SandboxBackendProtocol` / `SandboxBackendProtocolV2`；若是才暴露 `execute` 工具。
- **支援的沙盒供應商與類別**：
  - **LangSmith Sandboxes**（第一方代管沙盒，支援 snapshots、service URLs 與 auth proxy）
  - **AgentCore**：套件 `langchain-agentcore-codeinterpreter`，類別 `AgentCoreSandbox(interpreter=CodeInterpreter(region="us-west-2"))`
  - **Databricks**：套件 `'databricks-langchain[deepagents]>=0.22.0'`，類別 `DatabricksSandbox(client, "sandboxes/my-sandbox")`
  - **Daytona**：套件 `langchain-daytona`，類別 `DaytonaSandbox(sandbox=Daytona().create())`
  - **E2B**：套件 `langchain-e2b`，類別 `E2BSandbox(sandbox=Sandbox.create())`
  - **Modal**：套件 `langchain_modal`，類別 `ModalSandbox(sandbox=modal.Sandbox.create(app=app))`（支援 `blockNetwork: true` 阻斷網路）
  - **NVIDIA OpenShell**：套件 `langchain-nvidia-openshell`，類別 `OpenShellSandbox(sandbox=sandbox)`
  - **Runloop**：套件 `langchain-runloop`，類別 `RunloopSandbox(devbox=client.devbox.create())`
  - **Vercel**：套件 `langchain-vercel-sandbox`，類別 `VercelSandbox(sandbox=Sandbox.create(runtime="python3.13"))`
  - （此外 Deep Agents Code CLI 內建 `--sandbox`、`--sandbox-id`、`--sandbox-setup` 旗標支援）。
- **兩種整合模式與生命週期範圍（Lifecycle & Scoping）**：
  - **整合模式**：1. **Agent in sandbox pattern**（將 `deepagents-code` 封裝進 Docker/VM 映像檔在沙盒內運行，優點是貼近本地開發，缺點是 API keys 必須放在沙盒內且更新需重建映像檔）；2. **Sandbox as tool pattern**（推薦，代理在主機/伺服器執行並透過 API 遠端呼叫沙盒工具，API keys 留在沙盒外、沙盒故障不影響代理狀態，僅需承擔網路延遲）。
  - **生命週期範圍**：1. **Thread-scoped（預設）**：每個對話執行緒擁有獨立沙盒，建議設定 TTL 自動回收閒置環境；2. **Assistant-scoped**：同一 assistant 下所有執行緒共用單一沙盒，需搭配 TTL、snapshots 或清理邏輯防止磁碟與記憶體無限增長。
- **雙平面檔案存取（Two planes of file access）**：
  1. **Agent filesystem tools**（`read_file`, `write_file` 等）：由 LLM 在執行期間透過 `execute()` 呼叫。
  2. **File transfer APIs**：由應用程式碼呼叫供應商原生檔案傳輸 API，用於執行前預置（seed）檔案與執行後取回產物（artifacts）——Python 為 `upload_files([(path, b"...")])`（路徑須為絕對路徑，內容為 `bytes`）與 `download_files(["/path"])`（回傳含 `.path`, `.content`, `.error` 的結果清單）；JS 為 `uploadFiles`（內容為 `Uint8Array`）與 `downloadFiles`。
- **沙盒安全準則**：沙盒無法防範**上下文注入（Context injection）**與未封鎖網路下的**網路外洩（Network exfiltration）**。**絕對不要將機密（API keys、tokens、資料庫憑證）放入沙盒內**；應將機密保留在沙盒外部主機環境執行的自訂工具中，或使用能自動附加認證標頭的網路代理（network proxy）。

### 檔案系統權限（Filesystem Permissions）
- **版本需求與適用範圍**：
  - Python 需 `deepagents>=0.5.2`；JS 需 `deepagents>=1.9.1`。
  - **僅適用於內建檔案系統工具**（Python：`ls`, `read_file`, `glob`, `grep`, `write_file`, `edit_file`, `delete`；JS：`ls`, `read_file`, `glob`, `grep`, `write_file`, `edit_file`）。不涵蓋自訂工具、MCP 工具，且**不適用於支援任意 shell 指令執行的 sandbox backends**。
- **`FilesystemPermission` 規則結構與評估語義**：
  - `operations`：Python `list["read" | "write"]` / JS `("read" | "write")[]`。`"read"` 涵蓋 `ls`, `read_file`, `glob`, `grep`；`"write"` 涵蓋 `write_file`, `edit_file`（及 Python 的 `delete`）。
  - `paths`：Python `list[str]` / JS `string[]`。Glob 模式清單（如 `["/workspace/**"]`），支援 `**` 遞迴匹配與 `{a,b}` 交替匹配。在 JS 中路徑必須為絕對路徑（以 `/` 開頭）且不可包含 `..` 或 `~`，否則在建構代理時會拋出錯誤。
  - `mode`：Python 為 `"allow" | "deny" | "interrupt"`（預設 `"allow"`，其中 `"interrupt"` 需 `deepagents>=0.6.8`）；JS 為 `"allow" | "deny"`（預設 `"allow"`）。
  - **First-match-wins（先匹配者勝出）與預設允許**：依宣告順序由上而下評估，第一個 `operations` 與 `paths` 皆匹配的規則決定結果；若無任何規則匹配，**預設允許（allowed）**該操作。因此應將具體的窄規則放在廣泛的規則之前。
- **Python `mode="interrupt"` 與 `delete` 權限檢查細節**：
  - 當寫入工具匹配 `mode="interrupt"` 規則時，會自動觸發 HITL interrupt 供人工審批（approve / edit / reject）。建議將 interrupt 模式錨定於具體前導路徑（如 `/secrets/**` 而非 `/**/secrets`），因為批次工具（`ls`, `glob`, `grep`, 目錄 `delete`）只要搜尋子樹可能與規則前綴重疊就會保守觸發中斷。
  - **刪除目錄 vs. 刪除單一檔案**：刪除目錄（含現存空目錄）採取全有或全無（all-or-nothing）保守檢查，會檢查目標與所有子孫路徑的 `write` 權限，只要任一被拒絕就拒絕整個操作；刪除一般檔案（需 `deepagents>=0.7.3`）則與 `write_file` / `edit_file` 相同採取精確匹配與 first-match-wins 評估。
- **子代理權限與 `CompositeBackend` 限制**：
  - 子代理預設繼承父代理的 `permissions`；若在子代理規格中設定 `permissions`，會**完全取代**父代理規則（在 JS 中設定空陣列 `permissions: []` 可明確賦予子代理無限制存取權）。
  - 當使用以 sandbox 為 `default` 的 `CompositeBackend` 時，**每一條權限路徑都必須限定在已知的非沙盒路由前綴（route prefix）之下**；若權限路徑包含任何路由之外的路徑，Python 會引發 `NotImplementedError`，JS 則會在建構時拋出錯誤。

## 相關頁面
- [[concepts/deepagents-overview]]
- [[guides/deepagents-customization]]
- [[concepts/deepagents-human-in-the-loop]]
- [[concepts/deepagents-memory-and-skills]]
- [[concepts/agent-sdk-permissions]]

## 出處
- docs/deepagents/backends.md
- docs/deepagents/sandboxes.md
- docs/deepagents/permissions.md
