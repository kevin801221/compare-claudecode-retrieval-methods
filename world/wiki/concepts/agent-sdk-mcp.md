# Agent SDK MCP & Tool Search

別名：Agent SDK MCP 伺服器與工具搜尋、Model Context Protocol、mcpServers、mcp_servers、.mcp.json、ENABLE_TOOL_SEARCH、MAX_MCP_OUTPUT_TOKENS
框架：agent-sdk

## 摘要
Agent SDK 支援透過 Model Context Protocol (MCP) 連接本地 `stdio` 子處理程序、遠端 `http` / `sse` 伺服器以及處理程序內的 SDK MCP 伺服器，並可透過程式碼 `mcpServers` / `mcp_servers` 或專案根目錄 `.mcp.json` 設定。針對大型工具集，SDK 預設啟用 Tool Search（由 `ENABLE_TOOL_SEARCH` 控制），按需探索並載入工具定義以節省上下文視窗並提升工具選擇準確度。

## 重點
### 設定與傳輸協定（Transport Types）(`mcp.md`)
- **兩種設定途徑**：
  1. **程式碼設定**：傳入 `query()` 的 `mcpServers`（TypeScript）或 `mcp_servers`（Python）選項。
  2. **設定檔 `.mcp.json`**：放置於專案根目錄，當 `settingSources` / `setting_sources` 包含 `"project"`（預設啟用）時自動載入；支援在 `env` 或 `headers` 中使用 `${VAR_NAME}` 語法於執行期展開環境變數。
- **三種傳輸類型**：
  1. **stdio servers**：本地子處理程序，透過 `command`（如 `"npx"`）、`args`（字串陣列）與選用的 `env` 設定。
  2. **HTTP / SSE servers**：遠端伺服器，設定 `type: "http"` 或 `type: "sse"`、`url` 與選用的 `headers`（如 `Authorization: "Bearer ..."`）。在 `.mcp.json` 等 JSON 設定檔中支援 `"streamable-http"` 作為 `"http"` 的別名，但 SDK 的 `McpHttpServerConfig` 型別僅宣告 `"http"`，因此在程式碼中傳遞時必須寫 `"http"`。
  3. **In-process SDK MCP servers**：使用 `createSdkMcpServer` / `create_sdk_mcp_server` 在應用程式處理程序內執行（收到 `initialize` 控制請求時立即開始連線）。

### 工具命名慣例與權限核准
- **命名格式**：`mcp__<server-name>__<tool-name>`，其中 `<server-name>` 的 `.` 與空白等字元會被替換為 `_`（例如 key 為 `"my.server"` 的 `list_issues` 工具完整名稱為 `mcp__my_server__list_issues`）。若伺服器由 plugin 提供，`<server-name>` 會採用以 `plugin_` 開頭的 plugin-scoped 格式。
- **權限設定建議**：MCP 工具預設需要明確核准才能呼叫。`permissionMode: "acceptEdits"` **不會**自動核准 MCP 工具；應優先在 `allowedTools` / `allowed_tools` 中使用特定工具名稱（如 `"mcp__db__query"`）或伺服器萬用字元（如 `"mcp__github__*"`）進行預先核准，避免使用過度寬鬆的 `"bypassPermissions"`。
- **探索可用工具**：可從 `system` `init` 訊息的 `tools` 陣列（Python 為 `message.data.get("tools", [])`）篩選以 `"mcp__"` 開頭的名稱。

### 連線時序與等待上限（Connection Timing）
- **`options.mcpServers` 中各類伺服器的第一回合（first-turn）等待行為**：
  - **stdio 伺服器，或無快取工具清單的 HTTP/SSE 伺服器**：會延遲第一回合直到連線完成，等待上限為 `MCP_TIMEOUT`（預設 **30 秒**，逾時則連線失敗）。
  - **具備快取工具清單的遠端伺服器**（當 MCP discovery cache 開啟且先前連線曾儲存清單時）：不延遲第一回合，第一回合即可見快取工具，並延遲至首次呼叫工具時才實際連線。
  - **In-process SDK 伺服器**：延遲第一回合直到連線並列出工具，每次嘗試上限為 `MCP_TIMEOUT`（預設 30 秒）。
  - 若設定了 `permissionPromptToolName`，不論該伺服器定義於何處，第一回合永遠會等待該伺服器連線（上限為 `MCP_TIMEOUT`）。
- **來自設定檔（`.mcp.json`）或 Plugins 之 `pending` 伺服器的第一回合等待規則**：
  1. 若 `options.mcpServers` 包含任何 stdio、HTTP 或 SSE 伺服器：第一回合會一併等待設定檔與 plugin 伺服器，最長達 `MCP_TIMEOUT`。
  2. 否則，若 `ANTHROPIC_BASE_URL` 指向 gateway 且未設定 `ENABLE_TOOL_SEARCH`：第一回合對所有 pending 的設定檔與 plugin 伺服器最多等待 **2 秒**。
  3. 否則，當 Tool Search 開啟（預設）時：第一回合僅對設定了 `alwaysLoad: true` 或被點名（**Named servers**，即在 `allowedTools`、`settings` 的 `permissions.allow` 規則，或於 prompt-submission / tool-use / permission / subagent / task / elicitation / worktree 事件上的 `mcp_tool` hook 中指名其工具，需 Claude Code **v2.1.284**+）的 pending 伺服器最多等待 **2 秒**；其餘伺服器在背景繼續連線。
  4. 否則，當 Tool Search 關閉時：第一回合對所有 pending 的設定檔與 plugin 伺服器最多等待 **2 秒**。
- **自訂第一回合與啟動等待時間的環境變數**：
  - `CLAUDE_CODE_MCP_STARTUP_WAIT_MS`（需 Claude Code **v2.1.274**+）：以毫秒自訂第一回合等待上限（同時覆寫設定檔/plugin 伺服器與 `options.mcpServers` 中 stdio/HTTP/SSE 伺服器的 `MCP_TIMEOUT`）。但以下三種等待不受影響（即使設為 `"0"`）：`permissionPromptToolName` 伺服器（上限 `MCP_TIMEOUT`）、In-process SDK 伺服器（每次嘗試上限 `MCP_TIMEOUT`）、仍在連線中的 Named server（至少等待至 **2 秒**，設低於 `2000` 不會縮短其等待）。
  - `MCP_CONNECTION_NONBLOCKING=0`：讓啟動階段（發送 `init` 訊息前）等待整批連線，預設上限 **5 秒**，可透過 `MCP_CONNECT_TIMEOUT_MS`（毫秒）調整上限；伺服器設定 `alwaysLoad: true` 時也會在啟動階段等待至同一上限。
  - `MCP_TOOL_TIMEOUT`：調整單一執行中工具呼叫的逾時上限（在 TypeScript 中亦可將 `timeout` 傳給 `createSdkMcpServer()` 設定單一 SDK MCP 伺服器的工具呼叫逾時）。

### OAuth2 認證、狀態檢查與錯誤處理
- **五種伺服器狀態（位於 `init` 訊息的 `mcp_servers` 陣列）**：`"pending"`、`"connected"`、`"failed"`、`"needs-auth"`、`"disabled"`。（注意：`"pending"` 不代表失敗，可能是尚未連上、使用快取清單或逾時）。
- **OAuth 2.1 與憑證狀態**：SDK 不會自動開啟瀏覽器執行互動式 OAuth 流程。當缺少有效 token 時會回報 `"needs-auth"`；若無法讀取憑證儲存區（錯誤開頭為 `Couldn't read the stored credentials` 或 `A request to MCP server`，需 Claude Code **v2.1.307**+，在此之前 macOS 鑰匙圈鎖定時會回報 `needs-auth`）則回報 `"failed"`。應用程式應自行完成 OAuth 流程後將 access token 放入 `headers`。
- **連線中斷與重連**：遠端伺服器在工作階段中途斷線時會退回 `"pending"` 並自動嘗試重連；連續 **5 次**重連失敗後會變為 `"failed"`（或 `"needs-auth"`），但背景仍會針對暫時性錯誤持續重試。可隨時呼叫 `mcpServerStatus()`（TypeScript）/ `ClaudeSDKClient.get_mcp_status()`（Python）查詢最新狀態，或呼叫 `reconnectMcpServer()`（TypeScript）/ `ClaudeSDKClient.reconnect_mcp_server()`（Python）手動觸發重連。
- **Schema 轉換警告（TypeScript）**：當 SDK MCP 伺服器上某工具的輸入 schema 無法轉為 JSON Schema 時，`createSdkMcpServer()` 會在列出工具時排除該工具，並發出代碼為 `CLAUDE_SDK_MCP_TOOL_SCHEMA_UNCONVERTIBLE` 的 Node.js process warning（需 TS SDK **v0.3.286**+；在此之前單一工具轉換失敗會導致整個伺服器的工具清單全部失敗且無警告）。
- **MCP 輸出大小上限（`MAX_MCP_OUTPUT_TOKENS`）**：
  - 當成功回傳且不含圖片的工具結果超過 **25,000 tokens** 時，Claude Code 會將輸出存入檔案，並將工具結果替換為帶有該檔案路徑的錯誤訊息，讓代理分段讀取。可透過環境變數 `MAX_MCP_OUTPUT_TOKENS` 調整此 token 上限。
  - 除非工具宣告了 `anthropic/maxResultSizeChars` 標註，否則長度超過 **50,000 字元（characters）**的純文字成功結果不論 token 上限為何，一律會被寫入檔案。

### Tool Search 動態工具載入 (`tool-search.md`)
- **解決痛點與運作方式**：當載入超過 30–50 個工具時，不僅工具定義會消耗大量上下文（50 個工具約佔 10–20K tokens），工具選擇準確度也會下降。Tool Search 預設開啟，會將工具定義從初始上下文隱藏，僅提供摘要清單；當需要時由代理搜尋目錄，每次搜尋預設載入最多 **5 個**最相關的工具至上下文，並維持可用直到探索訊息被 compact 為止（目錄上限支援最多 **10,000 個工具**）。若工具總數少於約 10 個，直接預先載入通常較快（因 Tool Search 每次搜尋需多一次往返）。
- **模型與平台支援限制**：
  - **標準支援模型**：Opus 4、Sonnet 4、Haiku 4.5 及更新模型。較舊模型會強制預先載入所有工具定義，無法以 `ENABLE_TOOL_SEARCH` 覆寫。
  - **Google Cloud's Agent Platform**：Claude Opus 4.5、Sonnet 4.5、Haiku 4.5 及更新模型預設開啟；較早期的 Agent Platform 模型因伺服器端拒絕必要的 beta header，會強制預先載入（在 Claude Code **v2.1.221** 之前所有 Agent Platform 模型預設皆關閉）。
  - **Microsoft Foundry（Azure 託管部署）**：伺服器端拒絕 Tool Search，SDK 偵測到拒絕後會自動退回預先載入，`ENABLE_TOOL_SEARCH` 無法覆寫。
  - **`ANTHROPIC_BASE_URL` Gateway**：在 Claude Code **v2.1.304**+ 預設開啟（在此之前除非明確設定 `ENABLE_TOOL_SEARCH` 為 `true`、`auto` 或 `auto:N`，否則預設關閉）。
- **`ENABLE_TOOL_SEARCH` 環境變數五種設定值**：
  - `(unset)`（未設定）：預設開啟 Tool Search（在早於 Opus 4 / Sonnet 4 的模型、較早期 Agent Platform 模型與 Azure 上的 Microsoft Foundry 部署會 fallback 為預先載入）。
  - `true`：開啟 Tool Search（fallback 條件與未設定相同）。
  - `auto`：預設關閉並預先載入，直到**可延遲（deferrable）的工具定義總量達到模型上下文視窗的 10%** 時自動啟用（啟用後即使後續低於 10% 仍可在同一對話中保持開啟）。計入閾值的項目包含：所有未標記 `alwaysLoad` 的遠端與 SDK MCP 工具，加上按需載入的內建工具（核心內建工具如 `Bash`、`Read`、`Edit` 一律預先載入且不計入閾值；plugin 中的 mod 亦可改變工具是否延遲）。
  - `auto:N`：與 `auto` 相同，但自訂觸發百分比 `N`（例如 `auto:5` 代表達上下文視窗 5% 時啟用）。
  - `false`：關閉 Tool Search，每回合皆將所有工具定義載入上下文。（另外，若透過 `disallowedTools` 排除 `ToolSearch` 工具，也會關閉 Tool Search）。
- **強制關閉條件**：
  - 設定 `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` 會強制關閉 Tool Search，無法透過自行設定 `ENABLE_TOOL_SEARCH` 覆寫（但在 Claude Code **v2.1.227**+ 中，組織可透過 managed settings 在此變數下維持開啟）。
  - 在啟用 **HIPAA 組態**的工作階段中，Tool Search 一律關閉，無論 `ENABLE_TOOL_SEARCH` 或 managed settings 皆無法開啟。

## 相關頁面
- [[entities/agent-sdk-custom-tools]]
- [[concepts/agent-sdk-permissions]]
- [[concepts/agent-sdk-agent-loop]]
- [[concepts/claude-agent-sdk-overview]]
- [[concepts/agent-sdk-skills-and-plugins]]

## 出處
- docs/agent-sdk/mcp.md
- docs/agent-sdk/tool-search.md
