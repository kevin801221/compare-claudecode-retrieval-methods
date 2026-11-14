# LangChain Structured Output

別名：LangChain 結構化輸出、`response_format`、`responseFormat`、`ProviderStrategy`、`ToolStrategy`、`providerStrategy`、`toolStrategy`、`OutputFixingParser`
框架：langchain

## 摘要
結構化輸出（Structured output）讓 LangChain 代理能以可預測、經過驗證的格式（如 Pydantic 模型、Dataclass、TypedDict、Zod schema、Standard Schema 或 JSON Schema）回傳資料，並自動存入代理最終狀態的 `structured_response`（Python）或 `structuredResponse`（JavaScript/TypeScript）欄位中。`create_agent` / `createAgent` 支援透過 `ProviderStrategy`（供應商原生結構化輸出）與 `ToolStrategy`（工具呼叫結構化輸出與自動錯誤重試）兩種策略強制執行 schema，並可搭配 `ModelRefusalMiddleware` 處理模型拒絕。

## 重點

### `create_agent` / `createAgent` 的 `response_format` 與自動策略選擇
- **狀態回傳鍵值**：
  - Python：結構化資料存放於代理最終 state 的 `result["structured_response"]`。
  - JS/TS：結構化資料存放於代理最終 state 的 `result.structuredResponse`。
- **Python `response_format` 簽章與行為**：
  - 型別：`Union[ToolStrategy[StructuredResponseT], ProviderStrategy[StructuredResponseT], type[StructuredResponseT], None]`。
  - 當直接傳入 schema 型別（`type[StructuredResponseT]`，如 Pydantic `BaseModel`、Dataclass、`TypedDict`）時，LangChain 會讀取模型的 `profile`（需 `langchain>=1.1`，檢查 `"structured_output": True`，若同時使用工具則模型還須支援工具與結構化輸出同時使用）自動選擇策略：
    - 若模型與供應商支援原生結構化輸出（如 OpenAI、Anthropic Claude、xAI Grok、Gemini），自動選用 **`ProviderStrategy`**。
    - 其他所有模型則自動退回選用 **`ToolStrategy`**。
  - **重要限制**：在 Python 中，若使用 **JSON Schema 字典（dict）**，**必須**明確包裹在 `ProviderStrategy(...)` 或 `ToolStrategy(...)` 中，直接傳入 `response_format` 不會被自動偵測。
- **JS/TS `responseFormat` 簽章與行為**：
  - 型別：`ResponseFormat | ResponseFormat[]`，其中 `ResponseFormat` 可為 `ZodSchema`、`StandardSchema`（如 Valibot 搭配 `toStandardJsonSchema`）或 `Record<string, unknown>`（JSON Schema）。
  - 可直接傳入 schema，或從 `"langchain"` 匯入 `providerStrategy(schema)` 與 `toolStrategy(schema, options)` 明確指定策略。

### 供應商原生策略（`ProviderStrategy` / `providerStrategy`）
- **Python `ProviderStrategy`（`from langchain.agents.structured_output import ProviderStrategy`）**：
  - 簽章：`class ProviderStrategy(Generic[SchemaT]): schema: type[SchemaT]; strict: bool | None = None`。
  - `schema`（必填）支援型別與回傳值：
    - **Pydantic models**（`BaseModel` 子類別）：具欄位驗證，回傳驗證後的 Pydantic 實例。
    - **Dataclasses**（Python `@dataclass`）：回傳 `dict`。
    - **TypedDict**：回傳 `dict`。
    - **JSON Schema**（`dict`）：必須包含頂層 `title` 與 `description` 鍵，回傳 `dict`。
  - `strict`（`bool | None`，預設為 `None`，需 `langchain>=1.2`）：啟用嚴格 schema 遵循（OpenAI 與 xAI 等供應商支援）。
- **JS/TS `providerStrategy`（`import { providerStrategy } from "langchain"`）**：
  - 簽章：`function providerStrategy<StructuredResponseT>(schema: ZodSchema<StructuredResponseT> | SerializableSchema | JsonSchemaFormat): ProviderStrategy<StructuredResponseT>`。
  - 支援 Zod Schema、Standard Schema 與 JSON Schema 物件。

### 工具呼叫策略（`ToolStrategy` / `toolStrategy`）
- **適用場景**：適用於不支援原生結構化輸出的模型，或需要聯合型別（Union types）、自訂工具歷史訊息、以及自動驗證錯誤重試機制的場景。
- **Python `ToolStrategy`（`from langchain.agents.structured_output import ToolStrategy`）**：
  - 簽章：`class ToolStrategy(Generic[SchemaT]): schema: type[SchemaT]; tool_message_content: str | None; handle_errors: Union[bool, str, type[Exception], tuple[type[Exception], ...], Callable[[Exception], str]]`。
  - `schema`（必填）：除支援 Pydantic、Dataclasses、TypedDict、JSON Schema（需含 `title` 與 `description`）外，還支援 **Union types**（如 `Union[ProductReview, CustomerComplaint]`，模型會依上下文選擇最合適的 schema）。
  - `tool_message_content`（`str | None`）：自訂生成結構化輸出時寫入對話歷史之 `ToolMessage` 的文字內容（未設定時預設為 `"Returning structured response: {...}"`）。
  - `handle_errors`（預設為 `True`）：控制結構化輸出驗證失敗或同時呼叫多個輸出工具時的錯誤處理與自動重試行為：
    - `True`：捕捉所有錯誤，將預設錯誤訊息放入 `ToolMessage` 並提示模型重試。
    - `str`：捕捉所有錯誤，始終使用該固定自訂字串作為 `ToolMessage` 內容提示模型重試。
    - `type[Exception]`（如 `ValueError`）：僅在拋出該特定例外型別時以預設訊息重試，其他例外直接拋出。
    - `tuple[type[Exception], ...]`（如 `(ValueError, TypeError)`）：僅在拋出指定例外元組中的型別時重試，其他例外直接拋出。
    - `Callable[[Exception], str]`：自訂錯誤處理函式，可針對 `StructuredOutputValidationError` 與 `MultipleStructuredOutputsError`（皆匯入自 `langchain.agents.structured_output`）回傳不同提示文字。
    - `False`：不重試，直接向上拋出所有例外。
- **JS/TS `toolStrategy`（`import { toolStrategy } from "langchain"`）**：
  - 簽章：`function toolStrategy<StructuredResponseT>(responseFormat: JsonSchemaFormat | ZodSchema<StructuredResponseT> | SerializableSchema | (ZodSchema<StructuredResponseT> | SerializableSchema | JsonSchemaFormat)[], options?: ToolStrategyOptions): ToolStrategy<StructuredResponseT>`（支援傳入陣列如 `[ProductReview, CustomerComplaint]` 表示 Union Types）。
  - `options.toolMessageContent`：自訂 `ToolMessage` 內容字串。
  - `options.handleError`（文件中亦稱 `handleErrors`，預設為 `true`）：
    - `true`：捕捉所有錯誤並以預設錯誤模板重試。
    - `false`：不重試，直接拋出所有錯誤。
    - `string`：以固定自訂錯誤訊息字串重試。
    - `(error: ToolStrategyError) => string | Promise<string>`：自訂錯誤處理函式（例如檢查 `error instanceof ToolInputParsingException`，匯入自 `"@langchain/core/tools"`），回傳重試提示字串或拋出錯誤。

### 內建自動重試錯誤情境（Error Handling Scenarios）
1. **多重結構化輸出錯誤（`MultipleStructuredOutputsError`）**：當模型在單一輪次錯誤地同時呼叫多個結構化輸出工具（如同時呼叫 `ContactInfo` 與 `EventDetails`），代理會在對應的每個 `ToolMessage` 中回傳 `"Error: Model incorrectly returned multiple structured responses (ContactInfo, EventDetails) when only one is expected.\n Please fix your mistakes."`，要求模型修正為單一呼叫。
2. **Schema 驗證錯誤（`StructuredOutputValidationError`）**：當欄位違反限制（如 `ge=1, le=5` 卻輸入 `10`），代理會在 `ToolMessage` 回傳詳細的欄位驗證失敗訊息（`"Error: Failed to parse structured output for tool '...': ... Please fix your mistakes."`），引導模型重新生成合規數值。
3. **模型拒絕（Model Refusal in Agents）**：
   - 當模型拒絕回答而未產生結構化輸出時：使用 `ProviderStrategy` / `providerStrategy` 會拋出 `StructuredOutputValidationError`（Python）或 `StructuredOutputParsingError`（JS/TS）；使用 `ToolStrategy` / `toolStrategy` 則會在沒有 `structured_response` / `structuredResponse` 的情況下結束。
   - 若希望無論哪種策略都統一拋出 `ModelRefusalError`，可在代理中加入 **`ModelRefusalMiddleware`**（Python：`from langchain.agents.middleware import ModelRefusalMiddleware`，需 `langchain>=1.4.9`）或 **`modelRefusalMiddleware`**（JS/TS：`import { modelRefusalMiddleware } from "langchain"`，需 `langchain>=1.6.4`）。

### 在 LCEL Chains 中處理輸出解析錯誤（Handle Parsing Errors in Chains）
- 使用管道運算子（Python `prompt | model | parser` 或 JS `prompt.pipe(model).pipe(parser)`）組合的傳統 Chains 沒有內建重試機制，處理方式有二：
  1. **優先使用模型層級結構化輸出**：改用 `model.with_structured_output(...)`（Python）或 `model.withStructuredOutput(...)`（JS/TS）。
  2. **使用 `OutputFixingParser`（需安裝 `langchain-classic` / `@langchain/classic`）**：
     - Python：從 `langchain_classic.output_parsers` 匯入 `OutputFixingParser`，搭配 `PydanticOutputParser`（自 `langchain_core.output_parsers`），呼叫 `OutputFixingParser.from_llm(parser=base_parser, llm=model, max_retries=3)`。當初次解析失敗時，會將錯誤輸出、格式指令與錯誤訊息送給模型修正（不含原始 prompt；若修正需要原始 prompt 上下文，應改用 `langchain-classic` 的 `RetryOutputParser` 並呼叫 `parse_with_prompt(completion, prompt_value)`，但無法直接作為 `|` 鏈的最後一步）。
     - JS/TS：從 `"@langchain/classic/output_parsers"` 匯入 `OutputFixingParser`，搭配 `StructuredOutputParser.fromZodSchema(...)`（自 `"@langchain/core/output_parsers"`），呼叫 `OutputFixingParser.fromLLM(model, baseParser)`。注意：`OutputFixingParser` 僅會重試拋出 `OutputParserException` 的解析器（例如 `JsonOutputParser` 在無效 JSON 時會拋出原生 `SyntaxError`，不會被攔截重試）。

## 相關頁面
- [[concepts/langchain-overview-and-architecture]]
- [[concepts/langchain-agents-and-runtime]]
- [[entities/langchain-models]]
- [[entities/langchain-messages]]
- [[entities/langchain-tools]]
- [[entities/langchain-error-codes]]

## 出處
- docs/langchain/structured-output.md
