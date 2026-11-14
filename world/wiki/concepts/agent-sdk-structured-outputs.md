# Agent SDK Structured Outputs

別名：結構化輸出、JSON Schema 輸出、Structured Outputs、Pydantic 整合、Zod 整合、StructuredOutput 工具
框架：agent-sdk

## 摘要
Structured Outputs（結構化輸出）允許開發者透過 JSON Schema（可直接手寫，或由 TypeScript 的 Zod、Python 的 Pydantic 產生）定義代理人最終必須回傳的資料結構。代理人在執行過程中仍可自由呼叫任意工具（如 `Grep`、`Bash` 等）完成多步驟任務，最後 SDK 會針對輸出的 JSON 進行 Schema 驗證；若驗證不符則自動重新提示（Re-prompt）代理人修正，驗證成功後將強型別結構化資料寫入最終結果訊息的 `ResultMessage.structured_output` 欄位。

## 重點

### 設定方式與 JSON Schema 規範
- **選項名稱與格式**：
  - TypeScript：在 `query()` 的 `options` 設定 `outputFormat: { type: "json_schema", schema: schema }`。
  - Python：在 `ClaudeAgentOptions` 設定 `output_format={"type": "json_schema", "schema": schema}`。
- **JSON Schema 版本與支援特性**：
  - SDK 使用 **JSON Schema draft-07** 驗證 Schema，若傳入宣告較新版本的 Schema 會被拒絕。
  - 支援所有基本型別（`object`、`array`、`string`、`number`、`boolean`、`null`）、`enum`、`const`、`required`、巢狀物件與 `$ref` 定義。
  - **無效 Schema 行為變更（`v2.1.205`）**：若傳入的 Schema 不是合法的 JSON Schema，執行會在啟動時直接失敗並報錯指出問題所在（在 Claude Code `v2.1.205` 之前，無效的 Schema 會被靜默忽略並回傳非結構化文字）。
  - **`format` 關鍵字行為變更（`v2.1.205`）**：例如 `"format": "email"` 會被視為註解（Annotation）接受，但 SDK 驗證器**不會強制驗證其格式**（在 `v2.1.205` 之前，任何包含 `format` 的 Schema 都會被視為無效）。

### 與 Zod（TypeScript）及 Pydantic（Python）整合
- **TypeScript + Zod**：
  - 由於 Zod 預設產出 draft 2020-12，呼叫 `z.toJSONSchema()` 時**必須指定 `{ target: "draft-7" }`**：
    `const schema = z.toJSONSchema(FeaturePlan, { target: "draft-7" });`
  - 收到結果後，可使用 `FeaturePlan.safeParse(message.structured_output)` 進行解析與型別推導（`z.infer<typeof FeaturePlan>`）。
- **Python + Pydantic**：
  - 繼承 `pydantic.BaseModel` 定義模型（如 `class FeaturePlan(BaseModel):`）。
  - 使用 `FeaturePlan.model_json_schema()` 產生 JSON Schema 並傳入 `output_format={"type": "json_schema", "schema": FeaturePlan.model_json_schema()}`。
  - 收到結果後，使用 `FeaturePlan.model_validate(message.structured_output)` 轉換為具完整型別提示的 Pydantic 實例。

### 內部運作機制：辨識 `StructuredOutput` 工具呼叫
- 當設定 `outputFormat` / `output_format` 時，Claude Code 會在工作階段中自動注入一個名為 `StructuredOutput` 的內部工具（會列在系統初始化訊息 `system init` 的 `tools` 陣列中），代理人透過呼叫此工具來提交結構化答案。
- 每次呼叫在訊息串流中會呈現為兩個區塊：
  1. 名為 `StructuredOutput` 的 `tool_use` 區塊，其 `input` 即為代理人針對 Schema 產生的物件。
  2. 內容為 `Structured output provided successfully` 的 `tool_result` 區塊。
- **驗證失敗自動重試**：當物件不符合 Schema 時，`tool_result` 會改為帶有 `is_error: true`，且代理人會再次呼叫 `StructuredOutput`；因此單一查詢的訊息串流中可能會出現多次 `StructuredOutput` 呼叫。
- **最佳實踐**：
  - 務必從最終結果訊息的 `structured_output` 欄位讀取已驗證的資料，**不要**直接從中途的 `tool_use` 區塊讀取（同理，啟用 `include_partial_messages` 時，串流中的 `input_json_delta` 也是未驗證的片段）。
  - 若應用程式會在 UI 顯示或記錄工具呼叫，請跳過名稱為 `StructuredOutput` 的 `tool_use` 區塊，並記下其 `id` 以一併過濾掉對應 `tool_use_id` 的 `tool_result` 區塊（因為 `tool_result` 區塊沒有工具名稱，只有 `tool_use_id`）。

### 錯誤處理與結果檢查（Error Handling）
- **結果 Subtype 對照**：
  - `success`：執行結束且未觸發錯誤 subtype。
  - `error_max_structured_output_retries`：經過多次嘗試後仍無有效結構化輸出。觸發原因有二：
    1. Schema 驗證持續失敗達到重試上限（Schema 過於複雜、必填欄位無法從任務取得、或提示詞模糊）。
    2. **模型退回（Model fallback）撤回**：即使沒有發生驗證失敗，若中途發生自動模型退回（Automatic model fallback）撤回了已完成的輸出，且後續重試未能補上，也會以 `error_max_structured_output_retries` 結束。除錯 Schema 前應先檢查錯誤結果訊息上的 `errors` 清單以區分這兩種原因。
- **完整成功檢查條件**：
  - 僅檢查 `subtype == "success"` 並不代表一定有正確的結構化輸出！必須同時確認三個條件：
    - TypeScript：`msg.type === "result" && msg.subtype === "success" && !msg.is_error && msg.structured_output`
    - Python：`isinstance(message, ResultMessage) and message.subtype == "success" and not message.is_error and message.structured_output`
  - **為何需要檢查 `! is_error`**：若最後一次模型請求發生 API 錯誤或模型拒絕回答（Refusal），`is_error` 會為 `true`，此時切勿使用該結果上的 `structured_output`。
  - **為何 `structured_output` 可能為空（`None` / `undefined`）**：即使 `subtype` 為 `"success"`，`structured_output` 仍可能缺席（詳見疑難排解指南中關於舊版 CLI 或提前結束的情況）。
  - **單次 `query()` 例外捕捉**：當結果為 `error_max_structured_output_retries` 時，單次 `query()` 會在產出該錯誤結果訊息後拋出例外，務必在迴圈外加上 `try / catch` 或 `try / except`。

## 相關頁面
- [[concepts/agent-sdk-streaming]]
- [[guides/agent-sdk-cost-and-todo-tracking]]
- [[guides/agent-sdk-observability-and-troubleshooting]]

## 出處
- docs/agent-sdk/structured-outputs.md
