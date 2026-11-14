# LangChain Error Codes

別名：LangChain 錯誤碼、LangChain 常見錯誤與排解、`INVALID_PROMPT_INPUT`、`INVALID_TOOL_RESULTS`、`MESSAGE_COERCION_FAILURE`、`MODEL_AUTHENTICATION`、`MODEL_NOT_FOUND`、`MODEL_RATE_LIMIT`、`OUTPUT_PARSING_FAILURE`
框架：langchain

## 摘要
LangChain 定義了一系列標準錯誤碼（Error Codes），涵蓋提示詞模板變數缺失或未跳脫大括號、工具呼叫回應訊息數量或 ID 不匹配、訊息格式強制轉型失敗、模型驗證失敗、找不到模型名稱、觸發供應商速率限制以及輸出解析器失敗等七大常見執行期錯誤。理解各錯誤碼的觸發條件、語言適用範圍（Python 與 `langchainjs`）及排解步驟，有助於快速定位並修復代理與模型呼叫問題。

## 重點

### 1. `INVALID_PROMPT_INPUT`
- **觸發原因**：當提示詞模板（`PromptTemplate` 等）收到缺失（missing）或無效（invalid）的輸入變數時發生。
- **常見意外觸發情境**：在提示詞模板中直接嵌入未跳脫的 JSON 物件（例如在 `PromptTemplate.fromTemplate(...)` 中寫入 `{\n  "firstName": "John",\n  "lastName": "Doe"\n}`），模板會將單層大括號 `{...}` 誤判為額外的輸入變數名稱。
- **排解方式（Troubleshooting）**：
  1. 檢查提示詞模板語法，使用 f-string 格式時務必正確跳脫大括號：在 f-strings 中以雙大括號 `{{` 與 `}}` 表示單一字面大括號；以四個大括號 `{{{{` 表示雙層大括號。
  2. 使用 `MessagesPlaceholder` 元件時，確認傳入的是訊息陣列或 message-like 物件；若使用簡寫元組（shorthand tuples），需將變數名稱包裹在大括號中，如 `["placeholder", "{messages}"]`。
  3. 使用 LangSmith 或日誌（logging）檢查實際傳入模板的輸入值是否符合預期。
  4. 若從 LangChain Prompt Hub（`https://smith.langchain.com/prompts`）載入提示詞，先以範例輸入獨立測試該提示詞。

### 2. `INVALID_TOOL_RESULTS`
- **適用範圍**：目前僅用於 `langchainjs`（JavaScript/TypeScript）。
- **觸發原因**：在工具呼叫過程中，傳遞給模型的 `ToolMessage` 物件出現不匹配（mismatched）、數量不足（insufficient）或數量過多（excessive）時發生。基本協定要求：帶有 `tool_calls` 的助理訊息（`AIMessage`）之後，**必須**緊接著對應每一個 `tool_call_id` 的 `ToolMessage`（一對一精確對應）。
- **三大常見成因**：
  1. **Insufficient responses（回應不足）**：模型在單一 `AIMessage` 中請求執行 2 個工具呼叫（`responseMessage.tool_calls` 長度為 2），但僅在對話歷史中附加了 1 個 `ToolMessage`。
  2. **Duplicate responses（重複回應）**：針對同一個 `tool_call_id` 提供了多個 `ToolMessage` 物件，或包含無法匹配的 ID。
  3. **Orphaned tool messages（孤立的工具訊息）**：在沒有前置包含 `tool_calls` 之 `AIMessage` 的情況下，單獨發送 `ToolMessage`。
- **排解方式（Troubleshooting）**：
  1. **Count matching pairs**：確保前一個 `AIMessage` 中的每一個 tool call 都有且僅有一個對應的 `ToolMessage`。
  2. **Verify IDs**：確認每個 `ToolMessage.tool_call_id` 皆與實際的 tool call `id` 完全相符。

### 3. `MESSAGE_COERCION_FAILURE`
- **觸發原因**：當傳入 LangChain 模組的訊息物件不符合預期的訊息格式（無法強制轉型為訊息物件）時發生。
- **Python 接受的合法格式（`MessageLikeRepresentation`）**：
  - 定義為 `Union[Union[BaseMessagePromptTemplate, BaseMessage, BaseChatPromptTemplate], tuple[Union[str, type], Union[str, list[dict], list[object]]], str]`（來自 `langchain_core.prompts.chat`）。
  - 包含：LangChain 訊息類別實例（`BaseMessage`）、OpenAI 風格的訊息字典（必須同時包含 `'role'` 與 `'content'` 鍵，如 `{"role": "user", "content": "Hello world!"}`）、元組（tuples），以及純字串（會自動轉為 `HumanMessage`）。
  - **錯誤範例**：傳入 `{"role": "HumanMessage", "random_field": "random value"}` 給 `ChatAnthropic(model="claude-sonnet-4-6").invoke([...])`，會拋出 `ValueError: Message dict must contain 'role' and 'content' keys, got {'role': 'HumanMessage', 'random_field': 'random value'}`。
- **排解方式（Troubleshooting）**：
  1. 確保傳入聊天模型的所有輸入皆為 LangChain 訊息類別陣列或受支援的 message-like 格式。
  2. 確認訊息在傳遞過程中未被意外字串化（stringification）或破壞結構。
  3. 檢查堆疊追蹤（stack trace）並在傳入模型前印出訊息物件結構。

### 4. `MODEL_AUTHENTICATION`
- **適用範圍**：目前僅用於 `langchainjs`（JavaScript/TypeScript）。
- **觸發原因**：模型供應商拒絕存取服務，通常源於驗證憑證（authentication credentials）或 API keys 無效、缺失或設定錯誤。
- **排解方式（Troubleshooting）**：
  1. 確認 API key 或驗證憑證正確且有效。
  2. 若使用環境變數驗證，確認：變數名稱拼寫完全正確、已賦予非空值，且 `dotenv` 等第三方套件未干擾載入。
  3. 若使用 Proxy 或非標準端點（custom endpoint），確認自訂供應商是否要求不同的驗證機制。
  4. 可透過在建構模型時明確傳入憑證以繞過環境變數問題：Python 使用 `ChatOpenAI(api_key="YOUR_KEY_HERE")`；JS/TS 使用 `new ChatOpenAI({ apiKey: "YOUR_KEY_HERE" })`。

### 5. `MODEL_NOT_FOUND`
- **適用範圍**：目前僅用於 `langchainjs`（JavaScript/TypeScript）。
- **觸發原因**：指定的模型名稱（model name）不被模型供應商承認。通常源於模型識別字串拼寫錯誤，或程式碼與供應商 API 之間的 Proxy 服務／模型包裝器限制或竄改了允許的模型名稱。
- **排解方式（Troubleshooting）**：
  1. **Verify the model identifier**：再次檢查傳入的模型字串拼寫與格式是否正確。
  2. **Check proxy/wrapper configurations**：若使用 Proxy 或替代主機，確認其允許的模型清單未受限制或變更。

### 6. `MODEL_RATE_LIMIT`
- **適用範圍**：目前僅用於 `langchainjs`（JavaScript/TypeScript）。
- **觸發原因**：在特定時間區間內超過了模型供應商允許的最大請求數量（rate limit），導致請求被暫時封鎖（限制通常會在時間視窗重置後解除）。
- **排解方式（Troubleshooting）**：
  1. **Implement Rate Limiting**：部署速率限制器（如 Python 的 `InMemoryRateLimiter` 傳入 `rate_limiter` 參數）以調節發送請求的頻率。
  2. **Implement Response Caching**：啟用模型回應快取（response caching）以減少重複查詢造成的冗餘請求。
  3. **Use Multiple Providers**：若應用架構允許，將請求分散至多個模型供應商。
  4. **Contact Your Provider**：聯繫模型供應商申請提高速率限制配額。

### 7. `OUTPUT_PARSING_FAILURE`
- **觸發原因**：輸出解析器（output parser，見 `langchain-core/output_parsers`）無法按預期格式解析模型的輸出結果（注意：部分舊版預建 LangChain agents 與 chains 內部會隱式使用 output parsers，因此即使程式碼未明確實例化解析器也可能遇到此錯誤）。
- **排解方式（Troubleshooting）**：
  1. 優先改用工具呼叫（tool calling）或原生結構化輸出（structured output）技術，避免依賴純文字 output parser。
  2. 在提示詞（prompt）中加入更精確的格式指令（formatting instructions）。
  3. 若正在使用較小或能力較弱的模型，嘗試換用能力更強的模型（或是搭配 [[concepts/langchain-structured-output]] 中介紹的 `OutputFixingParser`）。

## 相關頁面
- [[concepts/langchain-overview-and-architecture]]
- [[entities/langchain-models]]
- [[entities/langchain-messages]]
- [[entities/langchain-tools]]
- [[concepts/langchain-structured-output]]

## 出處
- docs/langchain/errors/INVALID_PROMPT_INPUT.md
- docs/langchain/errors/INVALID_TOOL_RESULTS.md
- docs/langchain/errors/MESSAGE_COERCION_FAILURE.md
- docs/langchain/errors/MODEL_AUTHENTICATION.md
- docs/langchain/errors/MODEL_NOT_FOUND.md
- docs/langchain/errors/MODEL_RATE_LIMIT.md
- docs/langchain/errors/OUTPUT_PARSING_FAILURE.md
