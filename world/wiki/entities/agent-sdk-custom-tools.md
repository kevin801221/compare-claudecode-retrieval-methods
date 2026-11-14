# Agent SDK Custom Tools (`@tool` / `tool()` & `createSdkMcpServer`)

別名：Agent SDK 自訂工具、In-process MCP Server、@tool、tool()、create_sdk_mcp_server、createSdkMcpServer、ToolAnnotations、readOnlyHint
框架：agent-sdk

## 摘要
Agent SDK 允許開發者透過 Python 的 `@tool` 裝飾器或 TypeScript 的 `tool()` 輔助函式定義自訂工具，並以 `create_sdk_mcp_server` / `createSdkMcpServer` 包裝為執行於應用程式處理程序內（in-process）的 MCP 伺服器。自訂工具以 `mcp__{server_name}__{tool_name}` 命名規則註冊至 `mcpServers`，支援文字、Base64 圖片、資源與結構化資料回傳，以及透過 `ToolAnnotations` 控制平行執行與權限策略。

## 重點
### 定義與註冊自訂工具 (`custom-tools.md`)
- **工具四要素（傳入 Python `@tool` 或 TypeScript `tool()`）**：
  1. **Name**：供 Claude 呼叫的唯一識別名稱（如 `"get_temperature"`）。
  2. **Description**：工具用途說明，供 Claude 判斷何時呼叫。
  3. **Input schema**：
     - **TypeScript**：使用 Zod schema（如 `{ latitude: z.number().describe("..."), hours: z.number().int().min(1).max(24).optional() }`），handler 的 `args` 會自動推導型別。
     - **Python**：可傳入將參數名稱映射至型別的簡易 dict（如 `{"latitude": float}` 或搭配 `Annotated[float, "Latitude coordinate"]` 提供欄位說明，簡易 dict 的所有鍵皆為必填），或傳入完整的 **JSON Schema dict**（當需要設定選用欄位、預設值、`enum`、`minimum`/`maximum` 或巢狀物件時必須使用完整 JSON Schema dict，選用欄位不放入 `"required"` 並在 handler 中以 `args.get()` 讀取，或使用 `TypedDict` 類別）。
  4. **Handler**：非同步函式（`async def` / `async (args) => ...`），接收驗證後的參數並回傳結果物件。
- **包裝為處理程序內 MCP 伺服器**：
  - Python：`create_sdk_mcp_server(name="weather", version="1.0.0", tools=[get_temperature])`。
  - TypeScript：`createSdkMcpServer({ name: "weather", version: "1.0.0", tools: [getTemperature] })`。
  - 此伺服器直接在應用程式處理程序內（in-process）執行，不會衍生額外子處理程序。
- **完整工具命名規則（Tool naming convention）**：
  - 傳給 `query()` 時，將伺服器掛載於 `mcp_servers={"weather": weather_server}`（Python）或 `mcpServers: { weather: weatherServer }`（TypeScript）。
  - 工具的完整名稱（fully qualified name）固定為 **`mcp__{server_name}__{tool_name}`**（例如 `"mcp__weather__get_temperature"`），其中 `{server_name}` 為在 `mcpServers` 中設定的 key；若 key 含有 `.` 或空白等字元，在撰寫 `{server_name}` 時須替換為底線 `_`。
  - 可在 `allowed_tools` / `allowedTools` 單獨列出工具完整名稱，或使用萬用字元 `"mcp__weather__*"` 一次預先核准該伺服器的所有工具。
- **與 Tool Search 的互動**：
  - Tool search 預設開啟，會延遲載入 SDK MCP 工具的完整 schema（Claude 一開始僅看到精簡名稱清單，按需透過 `ToolSearch` 載入）。
  - 在 TypeScript 中，若要讓特定工具或伺服器的完整 schema 保留在初始提示詞中，可在 `tool()` 的 `extras` 參數或 `createSdkMcpServer()` 的 options 中設定 `alwaysLoad: true`。

### 工具標註（`ToolAnnotations`）與平行執行
- 在 TypeScript 中作為 `tool()` 的第五個參數 `{ annotations: { ... } }` 傳入；在 Python 中透過 `@tool(..., annotations=ToolAnnotations(...))` 傳入。所有欄位皆為布林值（僅作為中繼資料，不具強制力）：
  - **`readOnlyHint`**（預設 `false`）：表示工具不會修改環境。設為 `true` 時，允許 Claude 將此工具與其他唯讀工具**平行（in parallel）批次呼叫**（自訂工具預設為循序執行）。
  - **`destructiveHint`**（預設 `true`）：表示工具可能執行破壞性更新。若將工具標記為 `always_ask`，必須明確將此欄位設為 `true`。
  - **`idempotentHint`**（預設 `false`）：以相同參數重複呼叫不會產生額外副作用。
  - **`openWorldHint`**（預設 `true`）：工具會存取處理程序以外的外部系統。

### 存取控制與特定工具強制審核（`permission_policy`）
- **可用性（Availability）與權限（Permission）雙層控制**：
  - `tools: ["Read", "Grep"]`：僅保留列出的內建工具，移除未列出的內建工具，但**不影響 MCP 工具**。
  - `tools: []`：移除所有內建工具，讓 Claude 只能使用 MCP 工具。
  - `disallowedTools` / `disallowed_tools`：傳入內建工具裸名（如 `"Bash"`）會將其從上下文移除；傳入範圍規則（如 `"Bash(rm *)"`）則保留工具並拒絕匹配的呼叫。
- **`permission_policy: "always_ask"` / `"always_deny"`（僅限 TypeScript，需 Agent SDK v0.3.301+）**：
  - 在 `createSdkMcpServer()` **回傳的設定物件**上覆寫 `tools` 陣列（而非傳給 `createSdkMcpServer()` 的參數），例如：`mcpServers: { weather: { ...weatherServer, tools: [{ name: "get_temperature", permission_policy: "always_ask" as const }] } }`。
  - 設為 `"always_ask"` 後，即使該工具已列在 `allowedTools` 中，呼叫仍不會被自動核准，而是強制進入 `canUseTool` 回呼；設為 `"always_deny"` 則直接封鎖該工具。
  - **在 `auto` 或 `plan` 模式下的注意事項**：對於標記為 `always_ask` 的呼叫，未設定的 `destructiveHint` 會被視為 `false`（而非預設的 `true`），這可能導致 auto mode 分類器在進入 `canUseTool` 前就先核准呼叫；因此若使用 `auto` 或 `plan` 模式，必須在工具的 annotations 中**明確設定 `destructiveHint: true`**。

### 錯誤處理、多模態內容與結構化資料回傳
- **錯誤處理（`isError` / `is_error`）**：
  - Handler 拋出未捕捉的例外不會中斷 agent loop，in-process MCP 伺服器會攔截並將原始例外字串轉為錯誤結果回傳給 Claude。
  - 若要自行組織更具指導性的錯誤訊息，應在 handler 內捕捉錯誤並回傳包含 `"is_error": True`（Python）或 `isError: true`（TypeScript）的物件。
- **回傳區塊型別（`content` 陣列）**：
  - 支援 `"text"`、`"image"`、`"audio"`、`"resource"` 與 `"resource_link"` 區塊。
  - **Images（`"image"`）**：必須將圖片位元組進行純 Base64 編碼放入 `data`（不含 `data:image/...;base64,` 前綴，且無 URL 欄位）並提供必填的 `mimeType`。`image/png`、`image/jpeg`、`image/gif`、`image/webp` 會作為視覺輸入送達 Claude；其他圖片格式會儲存至磁碟並改傳檔案路徑文字給 Claude。
  - **Audio（`"audio"`）**：在 TypeScript 中會儲存至磁碟並傳送檔案路徑文字給 Claude；在 **Python 中則會從工具結果丟棄 audio 區塊並記錄警告**。
  - **Resources（`"resource"`）**：包含 `resource: { uri, text | blob, mimeType? }`（SDK 不會主動去讀取 `uri` 指向的路徑，實際內容須內嵌於 `text` 或 Base64 編碼的 `blob` 中）。在 **Python 中會丟棄二進位 `blob` 資源並記錄警告**（僅 TypeScript 支援 `resource.blob`）。
  - **Resource links（`"resource_link"`）**：Claude 會收到包含名稱、URI 與描述的文字區塊。在 TypeScript 中，應用程式還可從 user message 的 `tool_use_result` 讀取 `resourceLinks`；在 Python 中則在 CLI 看到結果前就已攤平為文字，因此 in-process 工具不會產生 Python 的 `resourceLinks` 鍵。
- **回傳結構化資料（`structuredContent`）**：
  - 在 TypeScript 的 `tool()` handler 回傳物件上設定 `structuredContent`（JSON 物件）時，Claude 會收到該 JSON 以及 `content` 中的圖片與資源區塊，而 **`content` 中的 `text` 區塊則不會送達 Claude**。
  - **Python 限制**：Python 的 `@tool` 裝飾器僅轉發 handler 回傳 dict 中的 `content` 與 `is_error`；若要在 Python 中回傳 `structuredContent`，必須改用獨立處理程序的外部 MCP 伺服器（standalone MCP server）。

## 相關頁面
- [[concepts/agent-sdk-mcp]]
- [[concepts/agent-sdk-permissions]]
- [[guides/agent-sdk-user-input]]
- [[concepts/agent-sdk-agent-loop]]

## 出處
- docs/agent-sdk/custom-tools.md
