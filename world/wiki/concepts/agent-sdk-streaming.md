# Agent SDK Streaming Output and Input Modes

別名：即時串流輸出、串流輸入模式、單一訊息模式、Streaming Output、Streaming Input Mode、Single Message Mode、StreamEvent、SDKPartialAssistantMessage
框架：agent-sdk

## 摘要
Claude Agent SDK 的串流機制分為「輸出串流（Output Streaming）」與「輸入模式（Input Modes）」兩大面向。在輸出串流方面，預設 SDK 僅在每個非空白內容區塊完成後產出完整的 `AssistantMessage`，若啟用 `include_partial_messages` / `includePartialMessages`，則會額外即時產出包裝原始 Claude API 事件的 `StreamEvent`（Python）/ `SDKPartialAssistantMessage`（TypeScript）。在輸入模式方面，SDK 支援建議使用的「串流輸入模式（Streaming Input Mode，持久互動式工作階段，支援圖片上傳、訊息佇列與中斷）」與「單一訊息輸入模式（Single Message Input，適合無狀態單次查詢）」。

## 重點

### 即時輸出串流（Output Streaming，`streaming-output.md`）
- **啟用方式**：
  - Python：在 `ClaudeAgentOptions` 設定 `include_partial_messages=True`。
  - TypeScript：在 `Options` 設定 `includePartialMessages: true`。
- **串流事件型別與結構**：
  - Python：`StreamEvent`（從 `claude_agent_sdk.types` 匯入），透過 `isinstance(message, StreamEvent)` 判斷並存取 `message.event` 字典。
  - TypeScript：`SDKPartialAssistantMessage`，其判別欄位為 `message.type === "stream_event"`，並存取 `message.event`。
  - **注意**：兩者皆僅包含原始 Claude API 串流事件（增量片段），**不包含累積後的完整文字或 JSON**，應用程式必須自行擷取並累加。
  - **`parent_tool_use_id` 與子代理人限制**：在 `StreamEvent` / `SDKPartialAssistantMessage` 上，`parent_tool_use_id` 永遠為 `None`（Python）或 `null`（TypeScript）。串流事件僅針對主工作階段（Main session）發出，**不會轉發子代理人的 token 級別增量事件**；若需將輸出歸因於子代理人，必須使用帶有 `parent_tool_use_id` 的完整訊息（Complete messages）。
  - **`user_message_uuid` 欄位**：Claude Code 會在回合的第一個非 ping 串流事件（以及該回合所回答的訊息改變時）設定 `user_message_uuid`，但 Python 的 `StreamEvent` 不會暴露此欄位（僅 TypeScript 支援）。

### 原始 Claude API 事件類型與處理
`message.event` 內常見的 `type` 包括：
- `message_start`：新訊息開始。
- `content_block_start`：新內容區塊（文字或工具呼叫）開始。若為工具呼叫，`event.content_block.type` 為 `"tool_use"`，可從 `event.content_block.name` 取得工具名稱。
- `content_block_delta`：內容增量更新，依 `event.delta.type` 區分：
  - `"text_delta"`：文字片段，位於 `event.delta.text`。
  - `"input_json_delta"`：工具呼叫的 JSON 輸入片段，位於 `event.delta.partial_json`。
- `content_block_stop`：單一內容區塊結束。
- `message_delta`：訊息層級更新（如 stop reason、usage）。
- `message_stop`：整則訊息結束。

### 訊息抵達順序與區塊拆分（Message flow）
- **每個內容區塊各產出一個 `AssistantMessage`**：當回應同時包含一個文字區塊與一個工具呼叫時，Claude Code 會在每個非空區塊完成時分別發出一個 `AssistantMessage`（共兩個 `AssistantMessage` 物件），兩者各自僅攜帶該區塊，但共用相同的訊息 ID（TypeScript 為 `message.message.id`，Python 為 `message.message_id`）。
- **啟用 Partial Messages 時的完整事件順序**：
  1. `StreamEvent (message_start)`
  2. `StreamEvent (content_block_start)` — text block
  3. `StreamEvent (content_block_delta)` — text chunks...
  4. `AssistantMessage` — 完整的 text block（注意：**在該區塊的 `content_block_stop` 之前抵達**）
  5. `StreamEvent (content_block_stop)`
  6. `StreamEvent (content_block_start)` — `tool_use` block
  7. `StreamEvent (content_block_delta)` — tool input chunks...
  8. `AssistantMessage` — 完整的 `tool_use` block（同樣在 `content_block_stop` 之前抵達）
  9. `StreamEvent (content_block_stop)`
  10. `StreamEvent (message_delta)`
  11. `StreamEvent (message_stop)`
  12. （工具執行，接著下一回合的串流事件...）
  13. `ResultMessage` — 最終結果
- **未啟用 Partial Messages 時**：會收到除 `StreamEvent` 以外的所有訊息型別，包含 `SystemMessage`（工作階段初始化）、`AssistantMessage`、`ResultMessage`，以及對話歷史壓縮邊界訊息（TypeScript 為 `SDKCompactBoundaryMessage`；Python 為 `subtype == "compact_boundary"` 的 `SystemMessage`）。

### 處理中途截斷的串流（Handle a stream that's cut off）
- 當串流在訊息中途被截斷（原因包含：回合被中斷、連線中斷、或退回非串流請求），在回合結束前**仍會收到該訊息的 `message_stop`**（自 Claude Code `v2.1.290` 起保證；TypeScript Agent SDK 自 `v0.3.290` 起、Python Agent SDK 自 `v0.2.164` 起內建 `v2.1.290` 以上版本。在 `v2.1.290` 之前截斷的串流可能不發送 `message_stop` 即結束回合，導致 UI 停留在進行中狀態）。
- 在截斷訊息的 `message_stop` 之前，`content_block_stop` 與 `message_delta` 可能會缺失：
  - **`content_block_stop`**：對開啟中的一般區塊仍會送達，但**若開啟中的區塊是工具呼叫（tool call）則不會送達**；若在工具呼叫區塊尚未關閉前就收到 `message_stop`，必須將該工具呼叫的輸入視為不完整（incomplete）。
  - **`message_delta`**：主動中斷回合時會送達，但在連線中斷或退回非串流時可能缺失，因此切勿在截斷訊息上等待 `message_delta`。
- **輸出串流的已知限制（Structured Output）**：啟用 Partial Messages 時，結構化輸出的 JSON 會以 `StructuredOutput` 工具呼叫的未驗證 `input_json_delta` 片段形式串流進來，只有通過驗證的最終結果才會寫入 `ResultMessage.structured_output`。

### 兩種輸入模式對照（`streaming-vs-single-mode.md`）
1. **串流輸入模式（Streaming Input Mode，推薦首選）**
   - **定位**：持久、互動式的工作階段（Long-lived process），提供對代理人能力的完整存取。
   - **核心能力與優勢**：
     - **圖片上傳（Image uploads）**：可直接在訊息的 `content` 陣列中附加圖片區塊（`{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": ...}}`）進行視覺分析。若圖片區塊缺少 `source` 或 `source` 不是物件，SDK 不會報錯，Claude Code 會改送一段文字提示（如 `[Image could not be processed: image block has no source object]`）給 Claude 並繼續工作階段。
     - **訊息佇列與中斷（Queued messages & Real-time interruption）**：傳送多則依序處理的訊息，並支援中途即時中斷。
     - **工具整合（Tool integration）**：在工作階段期間完整存取所有工具與自訂 MCP 伺服器。
     - **即時回饋（Real-time feedback）**與**自然的多輪脈絡保持（Context persistence）**。
   - **實作方式與語言差異**：
     - **TypeScript**：定義 `async function* generateMessages(): AsyncGenerator<SDKUserMessage>`，每次 `yield { type: "user", message: { role: "user", content: ... }, parent_tool_use_id: null }`，並將 `prompt: generateMessages()` 傳入 `query()`。`for await` 迴圈會依序印出每個完成的回應。
     - **Python**：使用 `ClaudeSDKClient`，定義 `async def message_generator():` 產生 `{"type": "user", "message": {"role": "user", "content": ...}}` 字典，呼叫 `await client.query(message_generator())` 後搭配 `async for message in client.receive_response():`。注意：Python 的 `receive_response()` 迴圈會在收到**第一個結果訊息（ResultMessage）**時結束；若要讀取多則訊息的所有回應，應對每則訊息分別使用一組 `query()` 與 `receive_response()` 配對。
   - **產生器拋出例外的診斷注意（Generator Exceptions）**：
     - **TypeScript**：若訊息產生器（Generator）內部拋出錯誤（例如讀取不存在的圖檔），串流結束時顯示的錯誤訊息會是 `Claude Code process aborted by user` 而非原始錯誤（且前方可能有一長行壓縮過的 SDK 原始碼），看到此訊息應優先檢查 Generator 內部程式碼。
     - **Python**：Generator 內部的例外僅會以 `debug` 等級記錄日誌，且工作階段會無聲卡住（Stall without raising）；若串流工作階段無輸出卡住，應啟用 debug logging 並檢查 Generator。
2. **單一訊息輸入模式（Single Message Input）**
   - **適用情境**：只需要單次（One-shot）回應、不需要圖片附件或工作階段中控制方法、或在無狀態環境（如 AWS Lambda 函式）中執行。
   - **不支援的功能（警告）**：
     - 不支援在訊息中直接附加圖片（Direct image attachments）
     - 不支援動態訊息佇列（Dynamic message queueing）
     - 不支援即時中斷（Real-time interruption）
     - 不支援自然的多輪對話（需改靠 `continue: true` / `continue_conversation=True` 或 `resume` 跨呼叫接續）
   - **錯誤拋出行為**：當單次 `query()` 查詢以錯誤結果（如 `error_max_turns`）結束時，SDK 會在產出最終結果訊息（`ResultMessage`）之後**拋出例外**（Python 註解稱為 `ResultError`），因此若後續程式碼需繼續執行，必須以 `try / catch`（TypeScript）或 `try / except`（Python）包覆迭代迴圈。

## 相關頁面
- [[concepts/agent-sdk-sessions]]
- [[concepts/agent-sdk-structured-outputs]]
- [[concepts/agent-sdk-permissions]]
- [[guides/agent-sdk-observability-and-troubleshooting]]

## 出處
- docs/agent-sdk/streaming-output.md
- docs/agent-sdk/streaming-vs-single-mode.md
