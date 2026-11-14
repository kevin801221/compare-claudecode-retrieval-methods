# LangChain Models

別名：LangChain 模型、聊天模型、Chat Models、`init_chat_model`、`initChatModel`、`BaseChatModel`、Model Profiles
框架：langchain

## 摘要
LangChain 提供跨供應商的標準化聊天模型介面（Chat Models），作為代理（Agents）的推理引擎或獨立（Standalone）呼叫使用，全面支援文字生成、工具呼叫（Tool calling）、結構化輸出（Structured output）、多模態（Multimodality）與多步推理（Reasoning）。開發者可透過 `init_chat_model`（Python）與 `initChatModel`（JavaScript/TypeScript）以統一的 `"provider:model"` 字串初始化各家模型，並無縫切換供應商、設定重試與速率限制、檢視模型能力輪廓（Model profiles）或在執行期動態路由模型。

## 重點

### 模型初始化與標準參數（Initialization & Parameters）
- **統一初始化函式**：
  - Python：`from langchain.chat_models import init_chat_model`，呼叫 `init_chat_model(model, **kwargs)`。
  - JS/TS：`import { initChatModel } from "langchain"`，呼叫 `await initChatModel(model, options)`。
- **標準配置參數（Python vs. JS/TS）**：
  - `model`（`string`，必填）：模型名稱，或以 `"{model_provider}:{model}"` 格式同時指定供應商與模型（如 `"openai:o1"`、`"openai:gpt-6.1-sol"`、`"claude-sonnet-4-6"`、`"google_genai:gemini-4-hydrogen"` / JS `"google:gemini-4-hydrogen"`）。亦可單獨傳入 `model_provider`（Python） / `modelProvider`（JS/TS）。
  - `api_key`（Python） / `apiKey`（JS/TS）（`string`）：驗證金鑰，通常透過環境變數設定或明確傳入。
  - `temperature`（`number`）：控制輸出的隨機性，數值越高越具創造力，越低越具確定性。
  - `max_tokens`（Python） / `maxTokens`（JS/TS）（`number`）：限制回應生成的最大 token 數量。
  - `timeout`（`number`）：等待模型回應的最大時間，在 Python 中單位為**秒（seconds）**（如 `timeout=120`），在 JS/TS 中單位常設為**毫秒（milliseconds）**（如 `timeout: 120_000`，部分快速設定亦見 `300`）。
  - `max_retries`（Python） / `maxRetries`（JS/TS）（`number`，預設值為 `6`）：連線韌性（Connection resilience）重試次數上限。使用帶抖動的指數退避（exponential backoff with jitter），會自動重試網路錯誤、速率限制（HTTP `429`）與伺服器錯誤（HTTP `5xx`）；**不會**重試客戶端錯誤如 `401`（unauthorized）或 `404`。針對不穩定網路上的長時間運行代理，建議調高至 `10`–`15`。在支援的供應商上，若使用了 model retry middleware，該 middleware 會接管所包裹呼叫的重試，此參數不再適用於那些呼叫。
- **供應商專屬參數**：例如 `ChatOpenAI` 支援 `use_responses_api` 控制使用 OpenAI Responses API 或 Completions API。

### 三大呼叫方法（Invocation Methods）
1. **`invoke()` / `ainvoke()`**：
   - 接收單一字串（自動轉換為 `HumanMessage`）、訊息物件列表（`SystemMessage`、`HumanMessage`、`AIMessage`）或 OpenAI 格式的字典列表（`[{"role": "system"|"user"|"assistant", "content": "..."}]`），完整生成後回傳單一 `AIMessage`（注意：舊版文字補全 LLMs 直接回傳字串，聊天模型類別名稱皆以 `"Chat"` 開頭，如 `ChatOpenAI`，回傳 `AIMessage`）。
2. **`stream()` / `astream()`**：
   - 回傳迭代器，逐步產出 `AIMessageChunk` 物件。可讀取 `chunk.text` 或遍歷 `chunk.content_blocks`（Python） / `chunk.contentBlocks`（JS/TS）處理 `"reasoning"`、`"tool_call_chunk"`、`"text"` 等區塊。
   - **Chunk 累加**：Python 可用加法運算子 `full = chunk if full is None else full + chunk`；JS/TS 可用 `full = full ? full.concat(chunk) : chunk`，組合成完整的 `AIMessageChunk`（行為等同 `invoke()` 回傳的 `AIMessage`）。
   - **語意事件串流**：Python 使用 `model.astream_events("Hello")`、JS/TS 使用 `await model.streamEvents("Hello")`，可過濾 `"on_chat_model_start"`（含 `event["data"]["input"]`）、`"on_chat_model_stream"`（含 `event["data"]["chunk"].text`）與 `"on_chat_model_end"`（含完整 `event["data"]["output"].text`）。
   - **Auto-streaming（自動串流）**：在 LangGraph 代理等串流上下文中，即使節點內部呼叫非串流的 `model.invoke()`，LangChain 也會自動切換至內部串流模式並觸發 `on_llm_new_token` 回呼事件，讓外層 `stream()` 與 `astream_events()` / `streamEvents()` 即時獲得逐 token 輸出。
3. **`batch()` / `abatch()` 與 `batch_as_completed()`**：
   - 在客戶端平行發送多個獨立請求（注意：這與 OpenAI 或 Anthropic 伺服器端的 Batch API 不同）。
   - `model.batch([...])` 會在整個批次完成後依序回傳所有結果；Python 另提供 `model.batch_as_completed([...])`，會在單一輸入完成時立即產出結果（可能亂序到達，附帶輸入索引以供重組順序）。
   - 可透過 `RunnableConfig` 的 `max_concurrency`（Python：`config={'max_concurrency': 5}`）或 `maxConcurrency`（JS/TS：`{ maxConcurrency: 5 }`）限制最大平行呼叫數。

### 工具呼叫（Tool Calling / Function Calling）
- **綁定工具**：Python 使用 `model.bind_tools([tool_1, ...])`；JS/TS 使用 `model.bindTools([tool_1, ...])`。模型回應的 `AIMessage.tool_calls` 會包含工具呼叫請求（每個元素含 `name`、`args`、`id`）。獨立使用模型時需自行執行工具並將結果封裝為含對應 `tool_call_id` 的 `ToolMessage` 回傳給模型；使用代理時則由代理迴圈自動處理。
- **強制呼叫工具（`tool_choice` / `toolChoice`）**：
  - 強制使用任意工具：Python `model.bind_tools([tool_1], tool_choice="any")` / JS `model.bindTools([tool_1], { toolChoice: "any" })`。
  - 強制使用指定工具：Python `model.bind_tools([tool_1], tool_choice="tool_1")` / JS `model.bindTools([tool_1], { toolChoice: "tool_1" })`。
- **平行工具呼叫（Parallel tool calls）**：多數模型預設啟用平行呼叫；OpenAI 與 Anthropic 等供應商支援在 `bind_tools` 時傳入 `parallel_tool_calls=False` 將其停用。
- **串流工具呼叫（Streaming tool calls）**：串流時透過 `chunk.tool_call_chunks` 逐步接收 `ToolCallChunk`（含 `name`、`id`、片段 JSON 字串 `args` 與 `index`），透過 `+`（Python）或 `.concat()`（JS/TS）累加後即可在 `gathered.tool_calls` 取得完整解析後的參數。

### 模型層級結構化輸出與拒絕處理（Structured Output & Model Refusal）
- **方法**：Python 呼叫 `model.with_structured_output(schema, ...)`；JS/TS 呼叫 `model.withStructuredOutput(schema, ...)`。
- **支援的 Schema 型別**：
  - Python：Pydantic `BaseModel`（自動驗證並回傳實例）、`TypedDict`（回傳 dict，需手動驗證）、JSON Schema dict（搭配 `method="json_schema"`，回傳 dict，需手動驗證）。支援巢狀結構。
  - JS/TS：Zod schema（自動透過 Zod parse 驗證）、JSON Schema（搭配 `{ method: "jsonSchema" }`，需手動驗證）、以及任何實作 **Standard Schema** 規範的函式庫（如 Valibot 搭配 `toStandardJsonSchema`，執行期透過 `~standard.validate()` 自動驗證）。
- **關鍵參數**：
  - `method`：Python 為 `'json_schema'`、`'function_calling'`、`'json_mode'`；JS/TS 為 `'jsonSchema'`、`'functionCalling'`、`'jsonMode'`。
  - `include_raw=True`（Python） / `{ includeRaw: true }`（JS/TS）：回傳字典包含 `"raw"`（原始 `AIMessage`，可用於讀取 token 用量等 metadata）、`"parsed"`（解析後的物件）與 `"parsing_error"`（Python，無錯誤時為 `None`）。
- **模型拒絕處理（Handle a model refusal）**：
  - 當供應商（OpenAI、Anthropic、Gemini）因安全政策回報明確拒絕時，一般模型呼叫會回傳含 `refusal` 內容區塊的訊息；而 `with_structured_output` / `withStructuredOutput` 會拋出 `ModelRefusalError`（Python 匯入自 `langchain_core.exceptions`，透過 `error.raw_message` 取得原始訊息；JS/TS 匯入自 `"@langchain/core/errors"`，可用 `ModelRefusalError.isInstance(error)` 判斷並由 `error.rawMessage` 取得原始訊息）。
  - 若設定 `include_raw=True`（Python），不會拋出例外，而是將 `ModelRefusalError` 放入 `response["parsing_error"]`；在 JS/TS 中設定 `includeRaw: true` 時不會拋出例外（`parsed: null`，可檢查 `response.raw.contentBlocks` 中 `type === "refusal"` 的區塊；但若 Gemini 因封鎖提示詞而未回傳任何訊息，`@langchain/google` 無論是否設定 `includeRaw` 都會拋出 `ModelRefusalError.isInstance` 為 `true` 的錯誤）。
  - **版本需求**：Python 需 `langchain-core>=1.7.5`、`langchain-openai>=1.7.4`、`langchain-google-genai>=4.4.3`（舊版對 Responses API 拒絕會拋出一般 `ValueError` 而非 `OpenAIRefusalError`）；JS/TS 需 `@langchain/core>=1.3.7`、`@langchain/openai>=1.8.3`、`@langchain/anthropic>=1.6.3`、`@langchain/google>=0.2.14`。

### 進階主題（Advanced Topics）
- **Model Profiles（模型能力輪廓，Beta 功能，需 `langchain>=1.1`）**：
  - 透過 `model.profile` 存取模型支援的功能字典：Python 欄位為 snake_case（如 `"max_input_tokens"`、`"image_inputs"`、`"reasoning_output"`、`"tool_calling"`、`"structured_output"`、`"reasoning_effort_levels"`、`"reasoning_effort_default"`）；JS/TS 欄位為 camelCase（如 `maxInputTokens`、`imageInputs`、`reasoningOutput`、`toolCalling`、`structuredOutput`）。
  - 資料來源主要由開源專案 **models.dev** 提供，並結合各整合套件的擴充設定（Python 為 `langchain_<package>/data/profile_augmentations.toml`，可透過 CLI 工具 `langchain-model-profiles` 的 `langchain-profiles refresh --provider <provider> --data-dir <data_dir>` 更新至 `_profiles.py`；JS/TS 為 `langchain-<package>/profiles.toml`）。
  - 亦可在初始化時傳入自訂 `profile=custom_profile` 覆寫，或在 Python 中使用 `model.model_copy(update={"profile": new_profile})` 避免變異共享狀態。
- **多模態（Multimodal）與推理（Reasoning）**：
  - 多模態模型可接收並產出圖片等非文字區塊（如 `response.content_blocks` 含 `{"type": "image", "base64": "...", "mime_type": "image/jpeg"}`）。
  - 推理模型輸出的思考過程可由 `content_blocks` / `contentBlocks` 中過濾 `type == "reasoning"` 取得。
  - **標準 `reasoning_effort` 參數（Python）**：支援於模型初始化或 `invoke` 時傳入 `reasoning_effort="high"`（或 `'low'`、`'medium'` 等），支援的類別包括 `ChatOpenAI`、`ChatAnthropic`（原生別名 `effort`）、`ChatFireworks`、`ChatXAI`、`ChatGoogleGenerativeAI`（原生別名 `thinking_level`）與 `ChatBedrockConverse`。版本需求：`langchain-core>=1.5.2`，以及 `langchain-anthropic>=1.5.3`、`langchain-openai>=1.4.1`、`langchain-fireworks>=1.5.2`、`langchain-xai>=1.3.0`、`langchain-google-genai>=4.3.1` 或 `langchain-aws>=1.7.0`。
- **本地模型（Local Models）與提示詞快取（Prompt Caching）**：
  - 本地模型推薦透過 **Ollama** 執行。
  - 提示詞快取分三層：1. 隱式供應商快取（OpenAI、Gemini 自動生效）；2. 供應商顯式控制（`ChatOpenAI` 的 `prompt_cache_key`、Anthropic 內容區塊 `cache_control`、Gemini、AWS Bedrock `cachePoint`）；3. LangChain middleware（Python 的 `AnthropicPromptCachingMiddleware`、`BedrockPromptCachingMiddleware`）。快取命中會反映在回應的 `usage_metadata` 中。
- **伺服器端工具呼叫（Server-side tool use）**：
  - 部分供應商支援在單一對話輪次由伺服器端執行內建工具（如 `model.bind_tools([{"type": "web_search"}])`），回應的 `content_blocks` 會包含 `"server_tool_call"`、`"server_tool_result"` 以及附帶 `"citation"` annotations 的 `"text"` 區塊，無需客戶端回傳 `ToolMessage`。
- **標準模型例外類別（Model Exceptions，Python `langchain_core.exceptions`）**：
  - 同時繼承自 LangChain 基礎例外與供應商 SDK 例外，每個類別皆具 `is_retryable` 屬性供 retry middleware 判斷：
    - 不可重試（not retryable）：`ModelAuthenticationError`、`ModelPermissionDeniedError`、`ModelInvalidRequestError`、`ModelNotFoundError`、`ContextOverflowError`。
    - 可重試（retryable）：`ModelRateLimitError`、`ModelAPIError`、`ModelConnectionError`、`ModelTimeoutError`。
- **速率限制（Rate Limiting，Python）**：
  - 使用執行緒安全的 `from langchain.rate_limiters import InMemoryRateLimiter`，配置 `requests_per_second`（如 `0.1`）、`check_every_n_seconds`（如 `0.1`）、`max_bucket_size`（如 `10`），並於初始化模型時傳入 `rate_limiter=rate_limiter`（僅限制單位時間請求次數，無法依請求大小限制）。
- **Base URL、Proxy、Logprobs 與 Token Usage 追蹤**：
  - OpenAI 相容 API（如 Together AI、vLLM）可在 `init_chat_model` 設定 `base_url`（JS 為 `baseUrl`）與 `api_key`；但 OpenRouter 與 LiteLLM 應優先使用專用套件 `ChatOpenRouter`（`langchain-openrouter`）與 `ChatLiteLLM` / `ChatLiteLLMRouter`（`langchain-litellm`）。HTTP Proxy 可在 `ChatOpenAI` 設定 `openai_proxy="http://proxy.example.com:8080"`。
  - 設定 `logprobs=True` 後可從 `response.response_metadata["logprobs"]` 讀取對數機率。
  - Python 跨模型累計 token 用量：使用 `from langchain_core.callbacks import UsageMetadataCallbackHandler`（傳入 `config={"callbacks": [callback]}` 後讀取 `callback.usage_metadata`）或 context manager `from langchain_core.callbacks import get_usage_metadata_callback`（`with get_usage_metadata_callback() as cb:` 讀取 `cb.usage_metadata`）。
- **執行期配置（`RunnableConfig`）、可配置模型（Configurable Models）與動態模型選擇（Dynamic Model Selection）**：
  - `RunnableConfig` 支援欄位：`run_name` / `runName`（不繼承至子呼叫）、`tags`（繼承至子呼叫）、`metadata`（繼承至子呼叫）、`max_concurrency` / `maxConcurrency`、`callbacks`、`recursion_limit`。
  - **Configurable Models（Python）**：呼叫 `init_chat_model(temperature=0)` 不指定模型時，預設 `'model'` 與 `'model_provider'` 為可配置欄位；亦可明確指定 `configurable_fields=("model", "model_provider", "temperature", "max_tokens")` 與 `config_prefix="first"`，在 `invoke` 時透過 `config={"configurable": {"first_model": "claude-sonnet-4-6", ...}}` 動態切換，且支援預先呼叫 `.bind_tools()` 或 `.with_structured_output()`。
  - **Dynamic Model Selection（在 Agent 中動態切換模型）**：透過 middleware 的 `@wrap_model_call`（Python，呼叫 `handler(request.override(model=model))`）或 `wrapModelCall`（JS/TS，呼叫 `handler({ ...request, model })`）依對話狀態（如 `len(request.state["messages"]) > 10`）動態切換模型。注意：使用結構化輸出時，**不支援**預先呼叫過 `bind_tools` 的 pre-bound models。

## 相關頁面
- [[concepts/langchain-overview-and-architecture]]
- [[concepts/langchain-agents-and-runtime]]
- [[entities/langchain-messages]]
- [[entities/langchain-tools]]
- [[concepts/langchain-structured-output]]
- [[concepts/langchain-streaming]]
- [[entities/langchain-error-codes]]

## 出處
- docs/langchain/models.md
