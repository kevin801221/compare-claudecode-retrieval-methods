# Deep Agents Streaming, Event Streaming & Fault Tolerance

別名：串流與容錯機制、Streaming、Event Streaming、Fault Tolerance、`subgraphs=True`、`stream.subagents`、`ModelRetryMiddleware`、`ToolRetryMiddleware`、`ToolErrorMiddleware`、`ModelFallbackMiddleware`、`ModelRefusalMiddleware`、`ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`
框架：deepagents

## 摘要
Deep Agents 建構於 LangGraph 串流與中斷基礎設施之上，支援透過傳統 `subgraphs=True` 與命名空間（namespaces）串流子代理進度，並在 v0.6 引入強型別投影的 Event Streaming API（`stream_events` / `streamEvents` 與 `stream.subagents`），讓開發者能獨立消費協調器與各層子代理的訊息、工具呼叫與狀態。在容錯方面，Deep Agents 提供速率限制、呼叫次數上限、指數退避重試、備援模型切換、模型拒絕攔截（`ModelRefusalError`）與工具錯誤轉換（`ToolErrorMiddleware`）等完整的韌性防護。

## 重點
### 傳統 LangGraph 子圖串流（Subgraph Streaming）
- **啟用子代理事件串流**：在呼叫 `.stream()` 時設定 `subgraphs=True`（Python）/ `subgraphs: true`（JS，文件中亦稱為 `stream_subgraphs`），即可接收來自子代理執行過程的事件。
- **命名空間（Namespaces）結構**：啟用 `subgraphs` 後，每個串流事件皆包含識別來源代理階層的 `namespace` tuple：
  - `()`（空 tuple）：主代理（Main agent）。
  - `("tools:abc123",)`：由主代理呼叫 ID 為 `abc123` 的 `task` 工具所產生的子代理。
  - `("tools:abc123", "model_request:def456")`：該子代理內部的 `model_request` 節點。
- **串流模式（`stream_mode` / `streamMode`）**：
  - `"updates"`：追蹤每個步驟（如 `model_request`、`tools`）完成的進度，以及偵測包含 `"__interrupt__"` 的 HITL 中斷事件。
  - `"messages"`：即時串流來自主要代理與各子代理的 LLM tokens 與 tool call chunks（附帶識別來源代理的 metadata）。
  - `"custom"`：從子代理工具內部發送自訂進度訊號——Python 在工具內呼叫 `get_stream_writer()` 取得 writer；JS 在工具內使用 `config.writer`。
- **串流區塊形狀（Stream chunk shapes）**：
  - 當設定 `subgraphs=True` 時：單一模式（如 `stream_mode="updates"`）產生 `(namespace, data)`；多重模式（如 `stream_mode=["updates", "messages", "custom"]`）產生 `(namespace, mode, data)`。
  - 當未設定 `subgraphs` 時：單一模式直接產生 `data`；多重模式產生 `(mode, data)`。
  - （註：LangGraph 1.1+ 亦支援統一的 `version="v2"` `StreamPart` dict 格式，而目前 Deep Agents 範例預設使用 tuple 格式；React 前端則可搭配 `useStream` hook）。

### 事件串流（Event Streaming，Beta，v0.6+ 推薦）
- **核心概念（`stream_events` / `astream_events` / `streamEvents`）**：
  - Deep Agents v0.6 引入的強型別投影（typed-projection）API（Python 非同步範例使用 `await agent.astream_events(input, version="v3")`）。
  - 透過 `stream.subagents` 為每次委派的 `task` 呼叫提供一個專屬的輕量級 stream handle：先探索子代理任務，僅在存取該 handle 上的特定投影（如 `.messages`）時才開啟對應串流。
  - **`stream.subagents` vs. `stream.subgraphs`**：`stream.subgraphs` 暴露底層圖形執行節點結構，而 `stream.subagents` 隱藏內部圖形節點、直接暴露產品層級的 Deep Agents 子代理任務委派，適合面向使用者的 UI。
- **Subagent Stream Handle 欄位對照（Python vs. TypeScript/JS）**：
  - 共通欄位：
    - `name`：子代理名稱（取自協調器呼叫 `task` 工具時選擇的 `subagent_type`）。
    - `messages`：該子代理發出的訊息串流。
    - `values`：狀態值串流。
    - `subagents`：巢狀子代理（nested subagent）呼叫串流（支援遞迴觀察多層子代理）。
    - `output`：最終子代理狀態或委派任務完成訊號。
  - **Python 專屬/命名（snake_case）**：
    - `tool_calls`：限定於該子代理的工具呼叫串流。
    - `path`：該子代理串流的命名空間路徑（namespace path）。
    - `status`：生命週期狀態，如 `started`、`completed`、`failed` 或 `interrupted`。
  - **TypeScript/JS 專屬/命名（camelCase）**：
    - `toolCalls`：限定於該子代理的工具呼叫串流。
    - `taskInput`：解析為傳給 `task` 工具之提示詞的 Promise。
- **並行消費（Concurrent Consumption）**：
  - 由於協調器與子代理輸出經常交錯（interleave），在 Python 非同步程式碼中可使用 `asyncio.gather(consume_coordinator(), consume_subagents())` 並行消費 `stream.messages` 與 `stream.subagents`；在 Python 同步程式碼中則使用 `stream.interleave(...)`。
  - 若需要跨協調器與所有子代理的精確到達順序（exact arrival order），可直接迭代底層原始協定事件（raw protocol events）並透過 `namespace` 辨識來源。

### 容錯機制與錯誤處理策略（Fault Tolerance）
- **七大錯誤處理策略對照**：
  1. **Transient errors（網路逾時、速率限制）**：由系統自動以指數退避重試 -> Python `ModelRetryMiddleware`、`ToolRetryMiddleware` / JS `modelRetryMiddleware`、`toolRetryMiddleware`。
  2. **LLM-recoverable errors（工具失敗、解析錯誤，僅 Python）**：轉換為錯誤 `ToolMessage` 讓模型調整重試 -> Python `ToolErrorMiddleware`（需 `langchain>=1.3.14`；JS SDK 尚未提供 `ToolErrorMiddleware`）。
  3. **Model refusals（模型因安全政策等拒絕）**：先透過備援模型重試，皆拒絕時拋出錯誤 -> Python `ModelFallbackMiddleware`、`ModelRefusalMiddleware` / JS `modelFallbackMiddleware`、`modelRefusalMiddleware`。
  4. **User-fixable errors（缺少資訊、指令不明確）**：暫停等待人類輸入 -> `interrupt()` / Human-in-the-loop（`interrupt_on` / `interruptOn`）。
  5. **Provider outage（供應商完全中斷）**：自動切換至替代模型 -> Python `ModelFallbackMiddleware` / JS `modelFallbackMiddleware`。
  6. **Excessive calls（失控迴圈）**：限制每次執行或每個執行緒的模型與工具呼叫次數 -> Python `ModelCallLimitMiddleware`、`ToolCallLimitMiddleware` / JS `modelCallLimitMiddleware`、`toolCallLimitMiddleware`。
  7. **Unexpected errors（非預期錯誤）**：不掛載攔截 middleware，直接讓例外向上傳播（bubble up）以便除錯。
- **速率限制（Rate Limiting）與呼叫次數上限（Call Limits）**：
  - **Provider rate limiting（Python）**：使用 `from langchain.rate_limiters import InMemoryRateLimiter`（設定如 `requests_per_second=0.1`、`check_every_n_seconds=0.1`、`max_bucket_size=10`），並於 `init_chat_model(..., rate_limiter=rate_limiter)` 初始化模型時傳入。
  - **Call limits**：
    - Python：`ModelCallLimitMiddleware(run_limit=50)`、`ToolCallLimitMiddleware(run_limit=200)`（亦支援跨整個對話執行緒的 `thread_limit`，需配置 checkpointer）。
    - JS：`modelCallLimitMiddleware({ runLimit: 50 })`、`toolCallLimitMiddleware({ runLimit: 200 })`。
- **自動重試（Retries）**：
  - Python：`ModelRetryMiddleware(max_retries=3, backoff_factor=2.0, initial_delay=1.0)`（會自動尊重 `ModelAuthenticationError`、`ModelRateLimitError`、`ModelTimeoutError` 等標準模型例外上的 `is_retryable` 旗標）；`ToolRetryMiddleware(max_retries=2, tools=["search", "fetch_url"], retry_on=(TimeoutError, ConnectionError))`。
  - JS：`modelRetryMiddleware({ maxRetries: 3, backoffFactor: 2.0, initialDelayMs: 1000 })`；`toolRetryMiddleware({ maxRetries: 2, tools: ["search", "fetch_url"], retryOn: [TimeoutError, TypeError] })`。
  - 最佳實踐：應透過 `tools=[...]` 將 `ToolRetryMiddleware` 限定於呼叫外部 API 的特定工具（如網頁搜尋），而非對 `read_file` 等本地檔案系統工具無差別重試。
- **備援模型（Fallbacks）與模型拒絕（Model Refusals）**：
  - **備援切換**：傳入 `ModelFallbackMiddleware("gpt-6.1-sol")`（Python）/ `modelFallbackMiddleware("gpt-6.1-sol")`（JS）。
  - **模型拒絕處理（Python 需 `deepagents>=0.7.33`；JS 需 `deepagents>=1.16.4`）**：
    - 當模型因安全政策等拒絕請求時（即使 HTTP 回應成功），內建於 Deep Agents stack 尾端的 `ModelRefusalMiddleware` / `modelRefusalMiddleware` 會引發/拋出 `ModelRefusalError`。
    - 由於 `ModelRefusalMiddleware` 在使用者傳入的 `middleware` **之後**執行，因此傳入的 `ModelFallbackMiddleware` / `modelFallbackMiddleware` 會先攔截拒絕並在下一個備援模型上重試；唯有當所有備援模型皆拒絕時才會向外拋出 `ModelRefusalError`（被拒絕的回覆不會存入執行緒，方便應用程式捕捉後提示使用者並繼續對話）。
    - **重要限制**：模型層級的 `with_fallbacks`（Python）/ `withFallbacks`（JS）**無法捕捉模型拒絕**，因為拒絕是在模型呼叫正常回傳後才由 middleware 偵測出來的，必須使用 `ModelFallbackMiddleware` / `modelFallbackMiddleware`。
- **工具錯誤處理（`ToolErrorMiddleware`，僅 Python，需 `langchain>=1.3.14`）**：
  - 預設情況下工具拋出例外會直接中止代理執行。透過 `ToolErrorMiddleware(on_error)`（其中 `def on_error(exc: Exception, request: ToolCallRequest) -> str | None:`），可針對已知且可恢復的例外（如 `ValueError`、`KeyError`）回傳錯誤字串（自動轉為 `ToolMessage` 交給模型修正參數重試），並對未知的非預期錯誤回傳 `None` 讓例外正常向上傳播並中止執行。

## 相關頁面
- [[concepts/deepagents-overview]]
- [[guides/deepagents-customization]]
- [[concepts/deepagents-subagents]]
- [[concepts/deepagents-human-in-the-loop]]
- [[concepts/deepagents-context-engineering]]

## 出處
- docs/deepagents/streaming.md
- docs/deepagents/event-streaming.md
- docs/deepagents/fault-tolerance.md
