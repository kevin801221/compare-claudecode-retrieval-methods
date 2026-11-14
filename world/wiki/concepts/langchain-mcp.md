# LangChain Model Context Protocol (MCP) Integration

別名：模型上下文協定整合、MCP 伺服器連接、Model Context Protocol、MCPAdapter、FastMCP、langchain-mcp-adapters
框架：langchain

## 摘要
LangChain 透過 `MCPAdapter` 將採用 Model Context Protocol（MCP）的本地或遠端伺服器工具整合進代理（`create_agent` / `createAgent`）。Python 版（`langchain.mcp`，需 `langchain[mcp]>=1.4.0`，底層基於 FastMCP）與 TypeScript/JavaScript 版（`@langchain/mcp-adapters@^2.0.0`）皆支援 `stdio`、Streamable HTTP 與舊版 `sse` 傳輸、多伺服器聚合與隔離、工具探索快取、新舊協定世代（Modern `2026-07-28` vs. Legacy）自動協商、多模態與結構化產物（`MCPToolArtifact`）、中斷驅動的伺服器端詢問（Elicitation），以及 Bearer Token、OAuth 2.1 與多租戶逐使用者認證（Per-user Authentication）。

## 重點

### 一、套件安裝、版本與公用文件伺服器
- **Python 安裝與版本**：
  - 安裝指令：`pip install "langchain[mcp]"` 或 `uv add "langchain[mcp]"`（會自動安裝 FastMCP）。
  - `langchain.mcp` 命名空間需 `langchain[mcp]>=1.4.0`，目前為 Beta 階段（每個處理序首次匯入時會發出一次 `LangChainBetaWarning`；舊版為 `langchain-mcp-adapters`）。
- **TypeScript/JavaScript 安裝與版本**：
  - 安裝指令：`npm install @langchain/mcp-adapters@^2.0.0 @langchain/core @langchain/langgraph`（需 2.0 以上版本；若需匯入 SDK 型別或傳輸類別，可額外安裝 `@modelcontextprotocol/client` `>=2.2.0`）。
- **LangChain 官方文件公用 MCP 伺服器**：
  - 公開 HTTP 端點：`https://docs.langchain.com/mcp`（免 API key）。
  - 提供 3 個工具：`search_docs_by_lang_chain`、`query_docs_filesystem_docs_by_lang_chain`（支援透過虛擬檔案系統執行 `rg`、`head`、`cat` 等指令）、`submit_feedback`（在 JS 中 `MCPAdapter` 預設會加上伺服器名稱前綴，如 `docs_search_docs_by_lang_chain`）。

---

### 二、傳輸協定（Transports）與目標設定
- **Python `MCPAdapter` 目標（Target）自動推論**：
  1. **`http` / `https` URL（`str`）**：透過 Streamable HTTP 連線。
     - **安全性警告**：字串型別的 target **必須**是 `http` 或 `https` URL。因為 FastMCP 解析字串時會先測試是否為檔案系統路徑再測試是否為 URL（若傳入現存 `.py` 或 `.js` 檔名會被當成子處理序啟動），故 `MCPAdapter` 會拒絕任何不符合 URL 格式的字串。
  2. **腳本路徑（`Path` 物件）**：以子處理序透過 `stdio` 啟動。
  3. **傳輸物件（`StreamableTransport`）**：預先設定好的 FastMCP 傳輸物件。
  4. **In-process `FastMCP` 伺服器實例**：直接在記憶體內連線，不經子處理序或 socket。
  5. **`MCPConfig` 字典（`{"mcpServers": {...}}`）**：單一 adapter 背後聚合多個伺服器。
  6. **預建的 `fastmcp.Client` 實例**：完全控制傳輸、回應快取與協定協商。
- **TypeScript/JavaScript `MCPAdapter` 的 `servers` 定義**：
  - 傳入具名伺服器映射物件，同一 adapter 可同時連接 `stdio` 與遠端 HTTP 伺服器：
    1. **stdio**：提供 `command` 與 `args`（啟動為子處理序）。
    2. **Streamable HTTP**：提供 `url`（URL 伺服器的預設傳輸，`transport: "http"` 可省略）。
    3. **SSE**：提供 `url` 並設定 `transport: "sse"`（僅用於舊版 SSE 伺服器）。

---

### 三、連線生命週期、多伺服器、部署擴展與協定世代（Connections）
- **連線生命週期（Connection Lifecycle）**：
  - **Python**：`MCPAdapter` 為非同步上下文管理器（`async with MCPAdapter(...) as adapter:`）。在區塊內呼叫 `await adapter.list_tools()` 探索工具；回傳的工具是**可重入的（reentrant）**，本身持有 client，因此在 `async with` 區塊結束後仍可由代理正常呼叫。預設每次工具呼叫會開啟一個獨立 session 並在呼叫結束時釋放（避免長時執行的代理佔用閒置連線）；若希望同一次代理執行期間跨多次工具呼叫維持同一 session，則在呼叫代理時保持 `async with` 開啟。
  - **TypeScript/JavaScript**：建構 `new MCPAdapter(...)` 時僅驗證設定而不連線；呼叫 `listTools()`、`listToolsets()`、`getClient()` 或資源方法（`listResources()`、`listResourceTemplates()`、`readResource()`）時才建立連線。在代理使用工具期間必須保持 adapter 開啟，結束時於 `finally` 呼叫 `await adapter.close()`（會中止進行中工作、關閉連線並清除快取；關閉後舊工具實例即失效，需重新呼叫 `listTools()` 取得新工具）。
- **多伺服器配置（Multiple Servers）**：
  - **Python**：
    - `MCPConfig`（單一聚合連線）：將所有工具加上設定鍵前綴以防撞名，但整個伺服器群（fleet）**共用單一協商出的協定世代**（只要加入一台舊版伺服器，全部伺服器都會降級為 legacy era）。
    - `ClientGroup`（獨立連線）：每個成員各自維持獨立的協定世代、認證（`auth`）與處理器，能讓現代與舊版伺服器並存，同樣會自動為工具名稱加上命名空間前綴。
  - **TypeScript/JavaScript**：
    - `servers` 中的每個項目皆有獨立連線、認證與協定 `mode`。`listToolsets()` 依伺服器名稱分組回傳；`listTools()` 回傳單一陣列（可傳入伺服器名稱或陣列篩選，但探索時仍會聯絡所有已設定的伺服器）。
    - 預設將工具名稱加上伺服器前綴（如 `calendar_search`）；可設 `prefixToolNameWithServerName: false` 保留原名（若有重複名稱則 `listTools()` 會拋出錯誤）。注意 OpenAI 限制工具名稱最多 **64 字元**、Anthropic 最多 **128 字元**且僅允許 `^[a-zA-Z0-9_-]+$`。
    - 頂層設定的 `defaultToolTimeout`（毫秒）會套用至所有伺服器並優先於個別伺服器的 `defaultToolTimeout`。
- **部署擴展（Scale a Deployment）與錯誤重連**：
  - **Python**：在 `langgraph dev`（註冊於 `langgraph.json`）中使用 graph factory 為每次執行探索最新工具目錄（注意：factory 參數與回傳值的型別註解必須在執行期可被 `typing.get_type_hints()` 解析，不可只放在 `TYPE_CHECKING` 內）。可搭配 `httpx_client_factory` 共用單一 HTTP 連線池 `_POOL`，或用 context manager factory 與 `execution_runtime` 管理資源。
  - **TypeScript/JavaScript**：在模組層級建立共用 `MCPAdapter`，在應用程式關閉時才 `close()`。預設探索失敗會拋出錯誤；可設 `onConnectionError: "ignore"` 或傳入回呼函式略過失敗伺服器（非認證錯誤的伺服器在後續探索會持續被略過，即使指定 `cacheMode: "refresh"`，需呼叫 `close()` 才能重置；認證錯誤則會在下次探索時重試）。`stdio` 支援 `restart` 設定；HTTP/SSE 在 `mode: "legacy"` 下支援 `reconnect` 設定。現代無狀態（sessionless）MCP 伺服器若部署多個副本，必須共用同一個 `requestState` 簽章金鑰。
- **快取（Caching）**：
  - Python `await adapter.list_tools(cache_mode=...)` 與 JS `await adapter.listTools([], { cacheMode: ... })` 皆支援三種模式：
    - `"use"`（預設）：在伺服器 TTL 提示（JS 為 `ttlMs`）有效期間內使用快取，否則重新抓取並存入。
    - `"refresh"`：強制向伺服器重新抓取並更新快取。
    - `"bypass"`：完全略過快取（不讀也不寫）。
- **協定世代（Protocol Eras）**：
  - **Legacy era**：以 `initialize` 交握開始連線。
  - **Modern era**（協定版本 `2026-07-28` 及以後）：透過探測伺服器的 `server/discover` 端點探索能力（無狀態）。
  - 在 JS 中，伺服器 `mode` 預設為 `"auto"`（先嘗試現代協定，若 Streamable HTTP 回傳 `404` 或 `405` 則自動退回嘗試相同 URL 及將結尾 `/mcp` 替換為 `/sse` 的 SSE 連線），亦可強制設為 `"modern"` 或 `"legacy"`（在 `"legacy"` 下任何 `4xx` 皆會退回 SSE，除非設定 `automaticSSEFallback: false`）。注意 `setLoggingLevel()` 僅限 legacy 使用（現代協定會拋出錯誤，應改在伺服器設定 `logLevel`）。

---

### 四、MCP 工具輸出、詮釋資料、HITL 與伺服器詢問（Elicitation）
- **工具輸出處理（Handle Tool Outputs）**：
  - **多模態內容（Multimodal content）**：自動轉換為 LangChain 標準內容區塊（如 `image` 區塊）。
  - **結構化內容（Structured content）**：不會混入給模型看的純文字，而是附加在 `ToolMessage.artifact` 上：
    - Python：`artifact` 為 `MCPToolArtifact` 實例，透過 `.structured_content` 讀取伺服器的 `structuredContent`（若無則 `artifact` 為 `None`）。
    - TypeScript/JavaScript：`artifact` 為 MCP 結果項目陣列，結構化內容位於 `type: "mcp_structured_content"` 項目的 `data` 欄位。
  - **錯誤處理（Errors）**：當 MCP 工具回傳 `isError=True` / `isError: true` 時，adapter 會轉為 `status="error"` 的 `ToolMessage` 讓模型讀取並自我修正。傳輸或 session 失敗在 Python 會直接拋出例外；在 JS 若於 `createAgent` 內執行也會被預設錯誤處理轉為錯誤 `ToolMessage`（但若直接以一般參數呼叫 JS 工具，則 `isError: true` 會拋出含 `error.result` 的 `ToolException`）。
- **工具詮釋資料（Tool Metadata）與搭配 HITL**：
  - Python：儲存在 `tool.metadata["mcp"]`，包含 `tool.annotations`（如 `destructive_hint`、`read_only_hint`）、`tool._meta` 與 `server`（`name`、`version`）。
  - TypeScript/JavaScript：儲存在 `tool.metadata.annotations`（如 `destructiveHint`、`readOnlyHint`）。
  - **動態人機迴圈審批**：可在探索工具時讀取 `destructive_hint` / `destructiveHint`，並搭配 `HumanInTheLoopMiddleware` 的 `when` 述詞同時檢查工具註記與參數（Python：`request.tool_call["args"]`；JS：`request.toolCall.args`）。**JS 重要警告**：`interruptOn` 的鍵名必須是包含伺服器前綴的完整工具名稱（如 `crm_delete_file`），否則永遠不會匹配。
- **工具執行期間的伺服器請求：Elicitation（中斷驅動詢問）**：
  - 當現代 MCP 伺服器在工具執行中途需要使用者輸入（回傳 `InputRequiredResult`）時，`MCPAdapter` 會觸發 LangGraph `interrupt` 暫停執行（代理必須配置 `checkpointer` 與 `thread_id`；若無 checkpointer，JS 會回傳錯誤 `ToolMessage`）。
  - **重要注意事項**：Resume 恢復執行時會**從頭重新執行該工具（reruns the tool from the beginning）**，因此在伺服器要求輸入前的任何操作都必須具備冪等性（避免重複產生副作用）。
  - **三種回覆動作（Actions）**：`accept`（提供符合 schema 的表單 `content`，或確認完成 URL 互動）、`decline`（拒絕提供資訊）、`cancel`（取消互動）。
  - **Python Elicitation**：預設啟用（型別位於 `langchain.mcp.elicitation`），使用 `Command(resume={"responses": {key: answer}})` 恢復。
  - **TypeScript/JavaScript Elicitation**：現代伺服器預設啟用（可設 `elicitation: false` 停用；legacy 伺服器則需在 `mode: "legacy"` 下設定 `onElicitation` 處理器）。每個中斷值為 `MCPElicitationInterrupt`（含 `type: "mcp_elicitation"`、`server`、不含前綴的原始 `tool` 名稱、`arguments` 與 `requests`）。**必須使用 `createMCPElicitationResume(q, answers)` 建構 resume 值**（若同時有多個中斷，需將所有 `createMCPElicitationResume` 回傳物件以 `Object.assign({}, ...)` 合併後傳給 `new Command({ resume })`）。
  - **不支援 Sampling 與 Roots**：現代無狀態協定沒有即時反向通道（back-channel），因此若伺服器請求 `sampling` 或 `roots`，Python 會直接拋出錯誤，JS 會拋出 `ToolException`（在 `createAgent` 中轉為錯誤 `ToolMessage`）。

---

### 五、MCP 認證機制（Authentication）
- **Python 認證（委託 `fastmcp.Client`）**：
  1. **Bearer Token**：`Client("https://...", auth="<token>")`（自動加上 `Authorization: Bearer <token>` 標頭；`auth` 亦接受任何 `httpx.Auth`）。
  2. **OAuth 2.1**：`Client("https://...", auth="oauth")` 自動執行探索、動態客戶端註冊（Dynamic Client Registration）、瀏覽器重導向與 token 交換。預設 token 存在記憶體中；若需跨執行持久化，可傳入 `from fastmcp.client.auth import OAuth`：`OAuth(mcp_url="...", token_storage=...)`。
  3. **Per-server 認證**：使用 `ClientGroup`，為每個 `Client` 設定各自的 `auth`。
  4. **Per-user 認證**：在 LangSmith Agent Server 透過自訂認證處理器解析呼叫者身分，再於 graph factory 內讀取身分並為該使用者建立專屬 token（`token_for`），同時必須依驗證後的使用者身分隔離回應快取。
- **TypeScript/JavaScript 認證（`@langchain/mcp-adapters` 2.0+）**：
  1. **靜態 Header 與動態 `AuthProvider`**：
     - 靜態 API key：在伺服器設定 `headers: { Authorization: "Bearer ..." }`。
     - 動態輪替 Token：設定 `authProvider: { token: async () => tokenStore.current(), onUnauthorized: async () => { ... } }`。`token()` 在每次請求前執行；`onUnauthorized()` 在收到 HTTP 401 時於重試前執行（注意：在 SSE 下每次重連被拒都會無上限重複呼叫 `onUnauthorized`，因此當無新 token 時**必須拋出 `UnauthorizedError`**）。
  2. **OAuth 2.1（`OAuthClientProvider`）**：
     - 實作 `OAuthClientProvider`（設定 `redirectUrl`、`state`、`redirectToAuthorization`、`invalidateCredentials()` 等），搭配 `@modelcontextprotocol/client` 的 `StreamableHTTPClientTransport`（SSE 則用 `SSEClientTransport`；機器對機器無使用者情境則用 `ClientCredentialsProvider`）在 callback 路由中驗證並原子性消耗 `pendingState` 後呼叫 `await transport.finishAuth(params)` 完成交換。
  3. **認證錯誤處理（Authentication Errors）**：
     - 連線因憑證被拒時會拋出 `MCPClientError`，其 `.cause` 鏈（1 至 3 層內）會包含 `UnauthorizedError`（需登入或無 `onUnauthorized`）、`SdkHttpError`（`status: 401`）或 `SseError`（`code: 401`）。工具呼叫期間憑證被拒則拋出 `ToolException`。
  4. **Header 優先順序與安全警告**：
     - 一旦 `authProvider` 取得 token，就會覆蓋設定的 `Authorization` 標頭；在此之前則發送靜態標頭。**安全警告**：SDK 會將靜態 `Authorization` 標頭一併轉發給授權伺服器的探索、註冊與 token 端點，因此切勿將機密 API key 與位於不同來源（Origin）的 OAuth 授權伺服器混用。
  5. **Per-user 認證（方法層級覆寫）**：
     - 在 `listTools(["crm"], { authProvider: providerFor(userId) })`、`listToolsets()`、`getClient()` 或資源方法的 options 中傳入 `authProvider` 或 `headers`。
     - **四項規則**：(1) 方法層級的 `authProvider` / `headers` 會套用至該 adapter 內的所有 HTTP/SSE 伺服器（多使用者不同憑證時應使用單一伺服器 adapter）；(2) 伺服器層級設定的同名 header（不分大小寫）優先於方法層級 header，而 provider token 又優先於兩者；(3) 每個不同的 provider 物件實例會開啟獨立連線直到 `close()`，因此每個使用者應重用同一個 provider 物件（如存入 `Map<string, AuthProvider>`）；(4) 工具目錄快取會自動依 provider 物件與 headers 隔離。

## 相關頁面
- [[concepts/langchain-human-in-the-loop-and-guardrails]]
- [[concepts/langchain-middleware]]
- [[entities/langchain-builtin-middleware]]

## 出處
- docs/langchain/mcp/index.md
- docs/langchain/mcp/connections.md
- docs/langchain/mcp/tools.md
- docs/langchain/mcp/auth.md
