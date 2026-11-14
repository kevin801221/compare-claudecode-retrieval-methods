# LangChain Messages and Content Blocks

別名：LangChain 訊息與內容區塊、`SystemMessage`、`HumanMessage`、`AIMessage`、`AIMessageChunk`、`ToolMessage`、`content_blocks`、`contentBlocks`
框架：langchain

## 摘要
Messages（訊息）是 LangChain 中模型上下文的基本單位，承載對話的角色（Role）、內容（Content）與中繼資料（Metadata）。LangChain v1 在保留原有彈性 `content` 屬性的同時，引入了跨供應商標準化的 `content_blocks`（Python）與 `contentBlocks`（JavaScript/TypeScript）屬性，將文字、多步推理（reasoning）、模型拒絕（refusal）、多模態資料（圖片、音訊、影片、PDF 檔案）、工具呼叫與伺服器端工具執行結果統一為型別安全的區塊結構。

## 重點

### 訊息輸入形式與四大核心訊息類別（Message Types）
- **三種提示輸入方式**：
  1. **Text prompts（純字串）**：如 `model.invoke("Write a haiku...")`，相當於單一 `HumanMessage` 的簡寫，適合無需保留對話歷史的單次獨立請求。
  2. **Message prompts（訊息物件列表）**：匯入自 `langchain.messages`（Python）或 `"langchain"` / `"@langchain/core/messages"`（JS/TS），適合多輪對話、多模態內容與系統指令。
  3. **Dictionary / Object format（OpenAI Chat Completions 字典格式）**：如 `{"role": "system" | "user" | "assistant" | "tool", "content": "..."}`。
- **四大訊息類別與屬性**：
  1. **`SystemMessage`**：設定模型初始行為準則、語氣與角色設定。
  2. **`HumanMessage`**：代表使用者輸入，支援文字與多模態內容。可附加中繼資料欄位：`content`、`name`（選用，用於識別不同使用者，供應商支援度不一）、`id`（選用，用於追蹤的唯一識別碼）。
  3. **`AIMessage`（串流時為 `AIMessageChunk`）**：代表模型生成的回應，亦可手動建立並插入對話歷史中。核心屬性（Python vs. JS/TS）：
     - `text`（`string`）：訊息的純文字內容。
     - `content`（Python `string | dict[]` / JS `string | ContentBlock[]`）：原始內容（相容供應商原生格式）。
     - `content_blocks`（Python `ContentBlock[]`） / `contentBlocks`（JS `ContentBlock.Standard[]`）：延遲解析（lazily parsed）的跨供應商標準化內容區塊列表。
     - `tool_calls`（`dict[] | None` / `ToolCall[] | None`）：模型發出的工具呼叫列表（每個含 `name`、`args`、`id`）；無工具呼叫時為空。
     - `id`（`string`）：由 LangChain 自動產生或供應商回傳的唯一訊息 ID。
     - `usage_metadata`（`UsageMetadata | None`）：Token 用量統計，包含 `input_tokens`、`output_tokens`、`total_tokens`、`input_token_details`（如 `audio`、`cache_read`、`cache_creation`）與 `output_token_details`（如 `audio`、`reasoning`）。
     - `response_metadata`（`ResponseMetadata | None`）：供應商回傳的原始中繼資料（如 `model_provider`、`model_name`、`finish_reason`、`logprobs` 等）。
     - **串流區塊合併**：多個 `AIMessageChunk` 可透過 Python 的 `+` 運算子（`full_message + chunk`）或 JS/TS 的 `.concat()`（`finalChunk.concat(chunk)`）合併為完整訊息。
  4. **`ToolMessage`**：將單一工具執行的結果回傳給模型。核心屬性：
     - `content`（`string` 或多模態區塊列表，必填）：送給模型閱讀的工具輸出結果。
     - `tool_call_id`（`string`，必填）：必須嚴格對應前一個 `AIMessage.tool_calls` 中的 `id`。
     - `name`（`string`，必填）：被呼叫的工具名稱。
     - `artifact`（`dict`）：**不會**發送給模型、僅供應用程式下游程式碼存取的附加資料（例如 RAG 檢索工具可將文字放入 `content` 供模型參考，並將 `{"document_id": "doc_123", "page": 0}` 放入 `artifact` 供前端渲染）。

### 訊息內容與標準內容區塊（`content` vs. `content_blocks` / `contentBlocks`）
- **三種 `content` 輸入格式**：建立訊息時可直接傳入：1. 純字串；2. 供應商原生格式區塊列表（如 OpenAI 的 `{"type": "image_url", ...}`）；3. 標準內容區塊列表（Python 可傳入 `HumanMessage(content_blocks=[...])`，JS/TS 可傳入 `new HumanMessage({ contentBlocks: [...] })`，會自動填充底層 `content` 並提供型別安全）。
- **跨供應商自動正規化**：讀取 `message.content_blocks`（Python）或 `message.contentBlocks`（JS/TS）時，會自動將各供應商原生區塊轉換為標準格式。例如：
  - Anthropic 原生的 `{"type": "thinking", "thinking": "...", "signature": "WaUjzkyp..."}` 會被解析為 `{"type": "reasoning", "reasoning": "...", "extras": {"signature": "WaUjzkyp..."}}`。
  - OpenAI 原生的 `{"type": "reasoning", "id": "rs_abc123", "summary": [{"type": "summary_text", "text": "summary 1"}, ...]}` 會被展開為多個 `{"type": "reasoning", "id": "rs_abc123", "reasoning": "summary 1"}` 區塊。
- **序列化標準內容區塊（`LC_OUTPUT_VERSION=v1`）**：若外部應用程式需要直接從 `message.content` 讀取標準化內容區塊，可設定環境變數 `LC_OUTPUT_VERSION=v1`，或在初始化模型時傳入 `output_version="v1"`（Python） / `{ outputVersion: "v1" }`（JS/TS）。

### 標準內容區塊完整型別參考（Content Block Reference）
在 JS/TS 中可透過 `import { ContentBlock } from "langchain"` 引用各子型別。以下列出所有標準區塊及其 Python 與 JS/TS 欄位差異：
1. **Core（核心區塊）**：
   - **`TextContentBlock` / `ContentBlock.Text`**：`type: "text"`（必填）、`text: string`（必填）、`annotations: object[] | Citation[]`（選用，如含 `start_index`、`end_index`、`title`、`url`、`type: "citation"`）、`extras: object`（選用）。
   - **`ReasoningContentBlock` / `ContentBlock.Reasoning`**：`type: "reasoning"`（必填）、`reasoning: string`、`extras: object`（選用，如簽章 `signature`）。
   - **`RefusalContentBlock` / `ContentBlock.Refusal`**：代表供應商明確回報的拒絕（如 OpenAI `refusal` part、Anthropic `stop_reason="refusal"`、Gemini 安全阻擋；不包含模型以普通文字寫出的拒絕，需 Python `langchain-core>=1.7.5` 或 JS `@langchain/core>=1.3.7`）。欄位：`type: "refusal"`（必填）、`refusal: string`（必填，無訊息時為空字串 `""`）、`extras: object`（選用，如 Anthropic 的 `category` 或 Gemini 的 `finish_reason` / `finishReason` / `block_reason`）。
2. **Multimodal（多模態區塊：圖片、音訊、影片、檔案、純文字文件）**：
   - **`ImageContentBlock` / `ContentBlock.Multimodal.Image`**（`type: "image"`）、**`AudioContentBlock` / `ContentBlock.Multimodal.Audio`**（`type: "audio"`）、**`VideoContentBlock` / `ContentBlock.Multimodal.Video`**（`type: "video"`）、**`FileContentBlock` / `ContentBlock.Multimodal.File`**（`type: "file"`，如 PDF）：
     - **Python 欄位**：`type`（必填）、`url`（字串 URL）、`base64`（Base64 編碼字串）、`id` 或輸入時的 `file_id`（供應商 Files API 管理的檔案 ID，如 `"file-abc123"`）、`mime_type`（如 `"image/jpeg"`、`"application/pdf"`、`"audio/wav"`、`"video/mp4"`，使用 `base64` 時必填）、以及額外鍵值（可直接放在頂層或放入 `"extras": {"key": value}`，如 OpenAI PDF 需要的檔名）。
     - **JS/TS 標準型別欄位**：`type`（必填）、`url`、`data`（Base64 編碼字串）、`fileId`（外部檔案系統 ID）、`mimeType`（使用 base64 時必填）。（註：JS/TS 傳統 `HumanMessage.content` 亦支援傳入 `source_type: "url" | "base64" | "id"` 搭配 `url` / `data` / `id` 與 `mime_type`）。
   - **`PlainTextContentBlock` / `ContentBlock.Multimodal.PlainText`**：用於 `.txt`、`.md` 文件文字，欄位為 `type: "text-plain"`（必填）、`text: string`、`mime_type`（Python） / `mimeType`（JS，如 `"text/plain"`、`"text/markdown"`），JS 另具選用欄位 `title: string`。
3. **Tool Calling（客戶端工具呼叫區塊）**：
   - **`ToolCall` / `ContentBlock.Tools.ToolCall`**：`type: "tool_call"`（必填）、`name: string`（必填）、`args: object`（必填）、`id: string`（必填）。
   - **`ToolCallChunk` / `ContentBlock.Tools.ToolCallChunk`**：`type: "tool_call_chunk"`（必填）、`name: string`、`args: string`（片段 JSON 字串）、`id: string`、`index: number | string`（在串流中的位置）。
   - **`InvalidToolCall` / `ContentBlock.Tools.InvalidToolCall`**：用於捕捉 JSON 解析失敗或格式錯誤的工具呼叫，欄位為 `type: "invalid_tool_call"`（必填）、`name: string`、`args: object | string`、`error: string`（錯誤描述）。
4. **Server-Side Tool Execution（伺服器端工具執行區塊）**：
   - **`ServerToolCall` / `ContentBlock.Tools.ServerToolCall`**：`type: "server_tool_call"`（必填）、`id: string`（必填）、`name: string`（必填）、`args: string | object`（必填）。
   - **`ServerToolCallChunk` / `ContentBlock.Tools.ServerToolCallChunk`**：`type: "server_tool_call_chunk"`（必填）、`id: string`、`name: string`、`args: string`、`index: number | string`。
   - **`ServerToolResult` / `ContentBlock.Tools.ServerToolResult`**：`type: "server_tool_result"`（必填）、`tool_call_id: string`（必填，對應 `ServerToolCall` 的 `id`）、`id: string`（選用）、`status: "success" | "error"`（必填）、`output`（工具執行輸出）。
5. **Provider-Specific Escape Hatch（供應商特定區塊）**：
   - **`NonStandardContentBlock` / `ContentBlock.NonStandard`**：`type: "non_standard"`（必填）、`value: object`（必填，存放實驗性或供應商獨有結構）。當 `langchain-core` 新增標準區塊型別時，符合的 payload 會自動從 `non_standard` 移入新型別。

### 訊息序列化與安全警告（Serialization）
- 訊息物件可序列化為純物件以儲存至資料庫，並反序列化回訊息實例以恢復對話狀態。
- **重大安全警告（Security Warning）**：反序列化使用的 `load()` 函式在 Python 與 JS/TS 中都會實例化物件並觸發建構子副作用（side effects）。**絕對不可（Never）對來自不受信任、未經驗證或使用者直接提供的輸入呼叫 `load()`**，僅能反序列化來自受控來源（如自有資料庫）的資料。

## 相關頁面
- [[concepts/langchain-overview-and-architecture]]
- [[concepts/langchain-agents-and-runtime]]
- [[entities/langchain-models]]
- [[entities/langchain-tools]]
- [[concepts/langchain-streaming]]
- [[entities/langchain-error-codes]]

## 出處
- docs/langchain/messages.md
