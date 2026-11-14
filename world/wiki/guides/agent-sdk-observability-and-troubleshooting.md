# Agent SDK Observability, Troubleshooting, and Examples

別名：可觀測性與疑難排解、OpenTelemetry 追蹤、OTLP 匯出、CLI 錯誤排解、範例專案、Observability、Troubleshooting、Examples
框架：agent-sdk

## 摘要
Claude Agent SDK 透過內建於 Claude Code CLI 子行程的 OpenTelemetry 檢測機制，將指標（Metrics）、結構化日誌事件（Log events）與追蹤（Traces）直接以 OTLP 協定匯出至可觀測性後端，並自動傳遞 W3C `TRACEPARENT` 與 `TRACESTATE` 將代理人執行嵌入應用程式追蹤鏈。此外，本頁整理了 CLI 啟動失敗（`CLINotFoundError`、`CLIConnectionError`）、子行程異常退出（`ProcessError`、`ResultError`）、結構化輸出為 `None` 的疑難排解對照表，以及官方 `claude-agent-sdk-demos` 範例庫與 Claude Cookbook 教學資源。

## 重點

### OpenTelemetry 可觀測性架構與訊號（`observability.md`）
- **運作架構**：Agent SDK 將 Claude Code CLI 作為子行程執行並透過本地 pipe 通訊。SDK 本身不產生遙測資料，而是透過環境變數（宿主行程環境變數或 `ClaudeAgentOptions.env` / `options.env`）將設定傳遞給 CLI 子行程，由 CLI 直接匯出至 Collector。注意：在 TypeScript 中 `options.env` 會完全取代繼承的環境，務必展開 `...process.env`。
- **啟用總開關**：預設關閉，必須設定 `CLAUDE_CODE_ENABLE_TELEMETRY=1` 並至少選擇一個訊號匯出器（Exporter）。
- **三種獨立 OpenTelemetry 訊號**：
  1. **Metrics（指標）**：Token、成本、工作階段、程式碼行數與工具決策的計數器。啟用變數：`OTEL_METRICS_EXPORTER`（如 `"otlp"`）。
  2. **Log events（日誌事件）**：每個提示詞、API 請求、API 錯誤與工具結果的結構化紀錄。啟用變數：`OTEL_LOGS_EXPORTER`（如 `"otlp"`）。
  3. **Traces（追蹤，Beta）**：每次互動、模型請求、工具呼叫與 Hook 的 Span。啟用變數：`OTEL_TRACES_EXPORTER`（如 `"otlp"`）**加上** `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`。
- **標準 OTLP 傳輸設定與重要限制**：
  - `OTEL_EXPORTER_OTLP_PROTOCOL`（如 `"http/protobuf"`）、`OTEL_EXPORTER_OTLP_ENDPOINT`（如 `"http://collector.example.com:4318"`）、`OTEL_EXPORTER_OTLP_HEADERS`（如 `"Authorization=Bearer your-token"`）。
  - **禁止使用 `console` Exporter**：`console` 匯出器會將遙測資料寫入標準輸出（stdout），而 SDK 使用 stdout 作為訊息通道；透過 SDK 執行時切勿將 Exporter 設為 `console`（本機除錯請改指向本地 OpenTelemetry Collector）。
  - **匯出錯誤診斷**：CLI 預設對匯出錯誤靜默失敗（不影響代理人執行）；若要將 Exporter 錯誤輸出至 stderr 並透過 SDK 的 `stderr` 回呼讀取，可設定 `CLAUDE_CODE_OTEL_DIAG_STDERR=1`（需 Claude Code `v2.1.179` 以上）。
- **短時間呼叫的批次刷新間隔（Export Intervals）**：
  - 預設匯出間隔：Metrics 每 **60 秒**（60000 ms），Traces 與 Logs 每 **5 秒**（5000 ms）。正常退出時會嘗試在短暫逾時內 flush，若行程被強制終止或 Collector 回應過慢則緩衝區資料可能遺失。
  - 短任務可調降毫秒間隔環境變數：`OTEL_METRIC_EXPORT_INTERVAL="1000"`、`OTEL_LOGS_EXPORT_INTERVAL="1000"`、`OTEL_TRACES_EXPORT_INTERVAL="1000"`。

### 代理人追蹤 Span 結構與 W3C Context 傳遞
- **四大核心 Span 名稱（需設 `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`）**：
  1. `claude_code.interaction`：包覆單一代理人迴圈回合（從接收提示詞到產出回應），為下述三個 Span 的父 Span。
  2. `claude_code.llm_request`：包覆每次 Claude API 呼叫，屬性含模型名稱、延遲與 Token 計數。
  3. `claude_code.tool`：包覆每次工具呼叫，並包含等待使用者權限的子 Span `claude_code.tool.blocked_on_user` 與實際執行的子 Span `claude_code.tool.execution`。當透過 Agent 工具啟動子代理人時，子代理人的 `llm_request` 與 `tool` Span 會巢狀掛在父代理人的 `claude_code.tool` Span 之下，形成單一完整委派鏈。
  4. `claude_code.hook`：包覆每次 Hook 執行（需額外啟用詳細 Beta 追蹤：`ENABLE_BETA_TRACING_DETAILED=1` 與 `BETA_TRACING_ENDPOINT`）。
- **`session.id` 屬性**：Span 預設帶有 `session.id` 屬性，方便將同工作階段的多次 `query()` 串成同一時間軸；若將 `OTEL_METRICS_INCLUDE_SESSION_ID` 設為 falsy 值則會省略該屬性。
- **W3C Trace Context 自動傳遞（`TRACEPARENT` / `TRACESTATE`）**：
  - 當應用程式在活動中的 OpenTelemetry Span 內呼叫 `query()` 時，SDK 會自動將 `TRACEPARENT` 與 `TRACESTATE` 注入子行程環境，使 `claude_code.interaction` 成為應用程式 Span 的子 Span（若在 `options.env` 手動設定 `TRACEPARENT` 則跳過自動注入；互動式 CLI 會忽略傳入的 `TRACEPARENT`，僅 Agent SDK 與 `claude -p` 支援）。
  - 自 Claude Code `v2.1.212` 起，設有 `TRACEPARENT` 時發出的 OTLP 事件日誌紀錄也會帶有相同的 `trace_id` 與 `span_id`。
  - CLI 還會將 `TRACEPARENT` 轉發給它執行的每個 Bash 與 PowerShell 指令，使指令內部發出的 Span 自動掛在 `claude_code.tool.execution` 之下。

### 服務標籤、終端使用者歸因與敏感資料控制
- **自訂服務名稱與資源屬性**：
  - CLI 預設回報 `service.name` 為 `claude-code`。可透過 `OTEL_SERVICE_NAME`（如 `"support-triage-agent"`）與 `OTEL_RESOURCE_ATTRIBUTES`（如 `"service.version=1.4.0,deployment.environment=production"`）覆寫。
- **終端使用者歸因（End-user Attribution）與 SIEM 稽核**：
  - 在多租戶應用中，可於每次 `query()` 將經過 URL 百分比編碼（Python `urllib.parse.quote` / TypeScript `encodeURIComponent`，因 `OTEL_RESOURCE_ATTRIBUTES` 保留逗號、空白與等號）的使用者與租戶 ID 注入：`OTEL_RESOURCE_ATTRIBUTES="enduser.id=...,tenant.id=..."`。
  - 結合以下 `claude_code.` 前綴的安全日誌事件即可建立每使用者 SIEM 稽核軌跡：`claude_code.tool_decision`、`claude_code.tool_result`、`claude_code.mcp_server_connection`、`claude_code.permission_mode_changed`。
- **敏感內容記錄開關（預設僅記錄結構化資訊，不記錄內容）**：
  - `OTEL_LOG_USER_PROMPTS=1`：在 `claude_code.user_prompt` 事件與 `claude_code.interaction` Span 上記錄提示詞文字。
  - `OTEL_LOG_TOOL_DETAILS=1`：在 `claude_code.tool_result` 事件上記錄工具輸入參數（檔案路徑、Shell 指令、搜尋條件），在成本與 Token 指標上記錄真實的 agent、skill、plugin 與 MCP server 名稱，並在 `claude_code.tool_decision` 事件上以 `classifier_category` 記錄 auto mode 分類器阻擋呼叫時引用的內建規則。
  - `OTEL_LOG_TOOL_CONTENT=1`：在 `claude_code.tool` 上附加 `tool.output` Span Event（需啟用 Tracing），包含檔案內容、Bash 輸出，以及 MCP 工具、`WebFetch`、`WebSearch` 的回傳結果（後三者需 Claude Code `v2.1.283` 以上）。預設在 **60 KB** 處截斷，可透過 `CLAUDE_CODE_OTEL_CONTENT_MAX_LENGTH` 調整（需 `v2.1.214` 以上）。
  - `OTEL_LOG_RAW_API_BODIES`：將完整 Anthropic Messages API 請求與回應 JSON 作為 `claude_code.api_request_body` 與 `claude_code.api_response_body` 日誌事件輸出（包含完整對話歷史，但會遮罩 extended-thinking 內容）。設為 `1` 為行內輸出（預設 60 KB 截斷，可由 `CLAUDE_CODE_OTEL_CONTENT_MAX_LENGTH` 調整，需 `v2.1.214` 以上）；設為 `file:<dir>` 則將未截斷內容寫入磁碟並在事件中附上 `body_ref` 路徑。

### 疑難排解指南（`troubleshooting.md`）
- **跨功能症狀導覽**：
  - Skills 找不到、`Invalid skill name` → 參閱 Skills 疑難排解。
  - MCP Server 顯示 `failed`、工具未呼叫、連線逾時、輸出超過最大允許 Token → 參閱 MCP 疑難排解。
  - Plugin 未載入、Subagents 未委派、File Checkpointing 錯誤、Hooks 未觸發或遞迴迴圈、容器部署失敗、`Not logged in` / `Invalid API key` / `429` → 參閱各對應頁面。
- **CLI 啟動錯誤（CLI Startup）**：
  1. **`CLINotFoundError: Claude Code not found`（Python）與 TypeScript 找不到二進位檔**：
     - Python：顯示 `Claude Code not found at: /your/configured/path`。若設定了 `ClaudeAgentOptions(cli_path=...)` 請確認檔案存在且為 `claude` 執行檔；若依賴 `PATH`，請確認應用程式執行環境（如 IDE 或服務管理員）的 `PATH` 中可執行 `claude --version`。
     - TypeScript：
       - `Native CLI binary for <platform>-<arch> not found`：遺失隨附的平台套件（通常因安裝時略過 optional dependencies），請不跳過選用依賴重新安裝 `@anthropic-ai/claude-agent-sdk`，或將 `pathToClaudeCodeExecutable` 指向原生安裝路徑（若為 `bun build --compile` 單一執行檔則需參考專屬編譯設定）。
       - `Claude Code native binary not found at <path>` 或 `Claude Code executable not found at <path>. Is options.pathToClaudeCodeExecutable set?`：確認路徑檔案存在且有讀取/執行權限。
  2. **`CLIConnectionError: Refusing to execute batch script`（Windows Python SDK 安全防護，自 `claude-agent-sdk` `0.2.124` 起）**：
     - 原因：在 Windows 上當 Python SDK 解析到的 CLI 路徑為 `.bat` 或 `.cmd` 批次檔（如 npm 安裝產生的 `claude.cmd` shim）時，因 Windows 會透過 `cmd.exe /c` 重新解析整行指令而存在參數注入（Command Injection）風險，SDK 故意拒絕執行。
     - 觸發情境：手動將 `ClaudeAgentOptions(cli_path=...)` 指向 `.bat`/`.cmd`；或在無隨附 `claude.exe` 的平台（如 ARM64 Windows 從原始碼安裝）且 `PATH` 上只有 npm shim。
     - 解決方法：移除指向 `.cmd` 的 `cli_path`、在 PowerShell 原生安裝 Claude Code（`irm https://claude.ai/install.ps1 | iex`），或在 x64 Windows 安裝內建 `claude.exe` 的 `claude-agent-sdk` wheel。
  3. **`CLIConnectionError: Failed to start Claude Code`（檔案存在但無法啟動）**：
     - 錯誤訊息對照：Python 為 `Failed to start Claude Code: <detail>`；TypeScript 為 `Claude Code executable at <path> exists but failed to launch`、`Claude Code native binary at <path> exists but failed to launch`（附帶 libc 建議）或 `Failed to spawn Claude Code process: <detail>`。
     - 原因與解決：路徑指向文字檔、目錄、缺少執行權限（`chmod +x`），或容器映像檔中的隨附二進位檔與容器架構/libc 不符（應在容器建置階段重新安裝 SDK）。
  4. **`CLIConnectionError: Not connected`（Python）**：
     - 訊息：`Not connected. Call connect() first.`。在呼叫 `ClaudeSDKClient` 其他方法前未先呼叫 `await client.connect()`，或未使用 `async with ClaudeSDKClient() as client:`。
- **CLI 行程異常退出（CLI Process Exit）**：
  1. **`ProcessError: Command failed with exit code`（Python）**：
     - 訊息固定為 `Command failed with exit code 1 (exit code: 1)` 與 `Error output: Check stderr output for details`（例外的 `stderr` 屬性也是這串固定文字，`exit_code` 屬性則帶有退出碼）。要取得真實 stderr 內容，必須在 `ClaudeAgentOptions` 傳入 `stderr` callback。
     - 繼承關係：當 CLI 未回報錯誤結果即退出時拋出裸 `ProcessError`；當 CLI 有回報錯誤結果時則拋出其子類別 `ResultError`（自 `claude-agent-sdk` `0.2.140` 起；`0.2.140` 之前拋出一般 `Exception`）。捕捉時應將 `except ResultError` 放在 `except ProcessError` 之前。
  2. **`Claude Code process exited with code N`（TypeScript）**：
     - 以一般 `Error` 拒絕 `for await` 迴圈，訊息為 `Claude Code process exited with code 1. stderr: <tail of the CLI's stderr>`（若被訊號終止則為 `Claude Code process terminated by signal <name>`）。可傳入 `stderr` callback 擷取完整錯誤流。
  3. **`Claude Code returned an error result`**：
     - 兩語言在 CLI 退出前回報錯誤結果時皆顯示 `Claude Code returned an error result: <the CLI's own error report>`。Python 拋出 `ResultError`（其 `data` 屬性包含完整錯誤結果物件）；TypeScript 以一般 `Error` 拒絕迴圈。
- **結構化輸出異常：`structured_output` 為 `None` / `undefined` 但 `subtype` 為 `"success"`**：
  - 應用程式必須將此情況視為失敗，並檢查兩種常見原因：
    1. **Claude 拒絕回答（Refusal）**：檢查結果訊息的 `stop_reason` 是否為 `"refusal"`。
    2. **Schema 存在無法滿足的矛盾限制**：例如字串的 `minLength` 大於 `maxLength`；應先簡化 Schema 直到驗證通過，再逐一加回限制條件。

### 官方範例與學習資源（`examples.md`）
- **最小化入門專案**：
  - Agent SDK Quickstart（修復範例檔案 Bug 的第一個代理人）。
  - `claude-agent-sdk-demos` 儲存庫中的 `hello-world`（最小 TypeScript 專案範本）。
- **完整示範應用與參考實作**：
  - `claude-agent-sdk-demos`（GitHub `anthropics/claude-agent-sdk-demos`）：涵蓋從電子郵件用戶端到多代理人研究系統的本地開發範例。
  - **Claude for commerce reference implementation**：使用 Python SDK 建構購物代理人（Shopping agent）或商家代理人（Merchant agent）的完整參考專案。
- **Claude Cookbook Python 系列教材**：
  - 由淺入深的 Python Notebook 系列，從單行研究代理人（`claude-agent-sdk-00-the-one-liner-research-agent`）一路推進至複雜的多代理人系統。

## 相關頁面
- [[concepts/agent-sdk-structured-outputs]]
- [[guides/agent-sdk-cost-and-todo-tracking]]
- [[guides/agent-sdk-hosting-and-security]]

## 出處
- docs/agent-sdk/observability.md
- docs/agent-sdk/troubleshooting.md
- docs/agent-sdk/examples.md
