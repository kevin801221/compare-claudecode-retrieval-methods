# LangChain Human-in-the-Loop and Guardrails

別名：人機迴圈與護欄、人工審核與安全防護、HITL、Human-in-the-Loop、Guardrails、PII 偵測、工具呼叫審批
框架：langchain

## 摘要
LangChain 透過 `HumanInTheLoopMiddleware`（JS：`humanInTheLoopMiddleware`）與護欄（Guardrails）機制，為代理工具呼叫與內容輸入/輸出提供安全性與合規控制。人機迴圈（HITL）支援在工具執行前發出 `interrupt` 並將狀態持久化至 checkpointer，提供 `approve`、`edit`、`reject` 與 `respond` 四種人類決策以及批次（`batched`）與逐次呼叫（`per_call`）兩種中斷模式；護欄則結合決定性規則（Deterministic，如正規表示式、關鍵字過濾、PII 偵測）與模型評估（Model-based，如 LLM 安全分類器）在代理生命週期各階段進行多層次防禦。

## 重點

### 一、人機迴圈（Human-in-the-Loop, HITL）核心概念與決策類型
- **運作機制**：
  - 當模型提出需要審核的工具呼叫（如寫入檔案、執行 SQL、發送外部郵件）時，`HumanInTheLoopMiddleware` 會比對政策並呼叫 `interrupt` 暫停執行。
  - **強制依賴 Checkpointer 與 `thread_id`**：必須在建立代理時設定 `checkpointer`（測試用 `InMemorySaver` / `MemorySaver`；正式環境用 `AsyncPostgresSaver` 或 `MongoDBSaver`），並在呼叫時傳入 `config={"configurable": {"thread_id": "some_id"}}` 以跨中斷保存與恢復狀態。
- **四種內建中斷決策類型（Interrupt Decision Types）**：
  1. **`approve`**：原封不動核准工具呼叫並立即執行。
  2. **`edit`**：在執行前修改工具名稱或參數（建議保守修改參數，避免大幅改動導致模型重新評估策略並重複呼叫工具）。模型會在收到工具結果前看到一段提示（可透過 `edit_notice` / `editNotice` 自訂，或設為 `None` / `null` 移除），告知是由人類審核員替換了該次呼叫。
  3. **`reject`**：拒絕執行該工具呼叫並附上選用的回饋訊息（`message`）。工具不會被執行，系統會合成一則錯誤狀態的 `ToolMessage` 回傳給模型（若省略 `message`，預設訊息會告知模型工具未執行且除非使用者要求否則不要重試）。
  4. **`respond`**：略過工具實際執行，直接以人類的必填回覆（`message`）作為成功的 `ToolMessage` 結果回傳給模型。**僅適用於「詢問使用者（ask_user）」類型的佔位工具**；切勿用 `respond` 來拒絕具副作用的工具（否則模型會誤以為工具已成功執行）。

---

### 二、`HumanInTheLoopMiddleware` 設定參數與條件式中斷
- **頂層設定參數對照**：
  | Python 參數 | TypeScript/JS 參數 | 型別 | 預設值 | 說明 |
  | :--- | :--- | :--- | :--- | :--- |
  | `interrupt_on` | `interruptOn` | `dict` / `object` | 必填 | 工具名稱至審核設定的映射。值可為 `True`/`true`（允許全部 4 種決策）、`False`/`false`（自動核准不中斷）或 `InterruptOnConfig` 物件 |
  | `description_prefix` | `descriptionPrefix` | `string` | `"Tool execution requires approval"` | 動作請求說明的前綴字串 |
  | `interrupt_mode` | `interruptMode` | `string` | `"batched"` | 暫停模式：`"batched"`（每模型回合產生單一中斷，以有序陣列回覆）或 `"per_call"`（每個受控工具呼叫獨立產生中斷，以 interrupt ID 回覆；Python 需 `langchain>=1.4.6`，JS 需 `langchain>=1.5.18` 且 `createAgent` 預設 `version="v2"`） |
  | `edit_notice` | `editNotice` | `string \| None` / `string \| null` | 預設提示字串 | 當審核員以 `edit` 替換呼叫時，加在工具結果前的提示文字；傳入 `None`/`null` 則不加 |
- **`InterruptOnConfig` 個別工具設定選項**：
  - `allowed_decisions`（Python） / `allowedDecisions`（JS）：允許的決策陣列，可包含 `'approve'`、`'edit'`、`'reject'`、`'respond'`（在 `guardrails.md` 的 JS 範例中亦展示了 `{ allowAccept: true, allowEdit: true, allowRespond: true }` 寫法）。
  - `description`（`string | callable`）：自訂靜態說明字串或動態產生說明的函式（會覆寫 `description_prefix`）。
  - `when`（`callable`，條件式中斷，Python 需 `langchain>=1.3.3`，JS 需 `langchain>=1.4.6`）：接收 `ToolCallRequest` 並回傳 `True`/`true`（中斷審核）或 `False`/`false`（自動核准直接執行）的述詞函式。
    - 範例：檢查 `request.tool_call["args"].get("path", "")`（JS：`request.toolCall.args.path`）是否寫入 `"/workspace/"` 以外路徑，或檢查 SQL `query` 是否非唯讀 `SELECT`。
    - **恢復執行時的重新評估規則**：代理 resume 時 `when` 述詞會再次執行，對相同呼叫必須回傳相同結果。若 resume 時回傳 `False`，工具會直接執行並忽略審核員的決定（包含 `reject`）；在 `"batched"` 模式下若僅部分呼叫的 `when` 結果改變，會拋出 `ValueError` / Error。

---

### 三、兩種中斷模式詳解：Per-call Mode vs. Batched Mode
1. **逐次呼叫模式（`"per_call"` mode，新代理推薦使用，預計於下一主版本成為預設）**：
   - **執行生命週期**：`after_model` / `afterModel` 鉤子不做任何事；審核發生在工具呼叫啟動時（位於 tool-call middleware 鏈內部）。不需要審核的工具（如 `read_data`）會立即執行，需要審核的工具則各自發出獨立的 `interrupt`。
   - **中斷結構與 `response_schema`**：
     - 每個中斷的值皆包含 `type: "tool_approval"`（JS 提供 `isToolApprovalInterrupt` 型別守衛函式）、`tool_call_id`、`name` 與 `args`。
     - 每個中斷附帶 `response_schema`（JSON Schema），依該工具允許的決策列出各分支（`type` 的 `const` 為 `"approve"`、`"edit"`、`"reject"` 或 `"respond"`；若僅允許單一決策則無 `oneOf`）。
     - 在 `"edit"` 分支中：Python 與 JS 皆使用 `edited_action: { name: "...", args: { ... } }`，`edited_action.name` 必須維持原工具名稱，`args` 必須符合工具參數 schema（在 JS 中，`z.object` 會丟棄未宣告參數，`z.looseObject` 則會保留）。
   - **依 Interrupt ID 恢復與錯誤驗證**：
     - 透過以 interrupt ID 為鍵的字典/物件傳入決策，可一次回覆全部或逐一回覆（未回覆的中斷維持 pending）。
     - **驗證機制**：LangGraph 在儲存回覆前會比對 `response_schema`。若回覆無效，Python 會拋出 `ValidationError`，JS 會拋出包裹 Zod 錯誤（位於 `.cause`）的 `MiddlewareError`，且不會儲存任何狀態，可針對同一 interrupt ID 重新發送修正後的回覆（註：Python 若工具為原始 JSON schema 而非 Pydantic 模型，或 JS 非 Zod v4 object schema，則不在儲存時驗證 `args`）。
     - **警告**：若一次同時送出多個回覆且其中一個無效，其他有效回覆對應的工具可能會先執行，但其 interrupt 仍顯示為 pending，若再次回覆會導致這些工具執行兩次。
   - **與其他工具 Middleware 的排序規則**：
     - 必須將 `HumanInTheLoopMiddleware` / `humanInTheLoopMiddleware` 放在 `ToolRetryMiddleware` 與 `ToolErrorMiddleware` **之前（外層）**，否則重試時會再次詢問人類審核員，且無效的審核回覆會被當成工具錯誤重試或回傳給模型。
     - 排在 `HumanInTheLoopMiddleware` 之前的 middleware 在 resume 時會重新執行到暫停點，因此呼叫 `handler` 前不可有副作用。
2. **批次模式（`"batched"` mode，目前預設）**：
   - **執行生命週期**：在 `after_model` / `afterModel` 鉤子中檢查模型回應的所有工具呼叫。若有任何呼叫需審核，建立包含 `action_requests` / `actionRequests`（每個元素含 `name`、`args`、`description`）與 `review_configs` / `reviewConfigs`（每個元素含 `action_name`/`actionName`、`allowed_decisions`/`allowedDecisions`）的 `HITLRequest` 並觸發單一 `interrupt`。
   - **讀取中斷與恢復執行（`HITLResponse`）**：
     - Python：呼叫 `agent.invoke(..., config=config, version="v2")` 回傳 `GraphOutput`，由 `result.interrupts` 讀取中斷；以 `Command(resume={"decisions": [...]})` 恢復。
     - TypeScript/JavaScript：呼叫 `await agent.invoke(..., config)`，由 `result.__interrupt__` 讀取中斷；以 `new Command({ resume: { decisions: [...] } })` 恢復。
     - **決策順序與欄位差異**：`decisions` 陣列順序必須嚴格對應 `action_requests` 中的動作順序。在批次模式的 `edit` 決策中，Python 使用 `"edited_action": {"name": "...", "args": {...}}`，而 JS 使用駝峰命名 `editedAction: { name: "...", args: {...} }`。
- **串流搭配人機迴圈（Streaming with HITL）**：
  - 使用 `agent.stream_events(..., config=config, version="v3")`（Python）或 `await agent.streamEvents(..., { ...config, version: "v3" })`（JS）。
  - 透過 `for message in stream.messages:` 與 `for token in message.text:` 串流輸出 token；迴圈結束後檢查 `if stream.interrupted:` 並印出 `stream.interrupts`（在 JS per-call 模式下，`stream.interrupts` 每個項目將中斷值放在 `payload` 且不含 `response_schema`，以 `interruptId` 為鍵恢復）。

---

### 四、護欄（Guardrails）架構與實作模式
- **兩大互補護欄方法**：
  1. **決定性護欄（Deterministic guardrails）**：使用正規表示式、關鍵字比對或明確規則檢查。速度快、可預測、成本低，但可能漏掉語意層面的微妙違規。
  2. **模型導向護欄（Model-based guardrails）**：使用 LLM 或分類器以語意理解評估內容。能捕捉規則遺漏的細微問題，但速度較慢且成本較高。
- **內建護欄：PII 偵測（`PIIMiddleware` / `piiMiddleware`）**：
  - 內建 5 種 PII 類型：`email`、`credit_card`（經過 Luhn 演算法驗證）、`ip`、`mac_address`、`url`；亦支援透過 `detector` 傳入自訂 regex 或函式（如偵測 API key `r"sk-[a-zA-Z0-9]{32}"`）。
  - 4 種處理策略（`strategy`，預設 `"redact"`）：
    - `redact`：替換為 `[REDACTED_{PII_TYPE}]`（如 `[REDACTED_EMAIL]`）。
    - `mask`：部分遮罩（保留末 4 碼，如 `****-****-****-1234`）。
    - `hash`：替換為決定性雜湊（如 `a8f5f167...`）。
    - `block`：偵測到時直接拋出例外阻擋。
  - 套用階段：`apply_to_input` / `applyToInput`（預設 `True`）、`apply_to_output` / `applyToOutput`（預設 `False`；Python `langchain>=1.3.2` 啟用時會透過串流轉換器扣留最後 128 字元以遮罩跨 delta 的串流輸出）、`apply_to_tool_results` / `applyToToolResults`（預設 `False`）。
- **自訂護欄（Custom Guardrails）**：
  - **代理啟動前護欄（Before agent guardrails）**：
    - 使用 `before_agent` / `@before_agent(can_jump_to=["end"])`（Python）或 `beforeAgent: { canJumpTo: ['end'], hook: ... }`（JS），在每次呼叫開始時檢查第一則人類訊息（如比對禁用關鍵字 `banned_keywords = ["hack", "exploit", "malware"]`），若違規直接回傳拒絕訊息與 `"jump_to": "end"` / `jumpTo: "end"` 短路中止，完全不呼叫主模型。
  - **代理完成後護欄（After agent guardrails）**：
    - 使用 `after_agent` / `@after_agent(can_jump_to=["end"])`（Python）或 `afterAgent: { canJumpTo: ['end'], hook: ... }`（JS），在回傳最終結果給使用者前，用輕量模型（如 `init_chat_model("gpt-5.4-mini")` / `initChatModel("gpt-5.4-mini")`）評估最後一則 `AIMessage` 是否 `'SAFE'` 或 `'UNSAFE'`；若包含 `"UNSAFE"`，則將回應替換為安全拒絕訊息。
- **多層防禦堆疊（Combining Multiple Guardrails）**：
  - 可在 `middleware` 陣列中依序堆疊多層護欄：
    1. **Layer 1（Before agent）**：`ContentFilterMiddleware` 決定性輸入過濾。
    2. **Layer 2（Before & After model）**：兩個 `PIIMiddleware` 分別設定 `apply_to_input=True` 與 `apply_to_output=True` 保護輸入與輸出隱私。
    3. **Layer 3（Tool execution gate）**：`HumanInTheLoopMiddleware` 對敏感工具要求人類審批。
    4. **Layer 4（After agent）**：`SafetyGuardrailMiddleware` 對最終輸出進行模型安全審查。

## 相關頁面
- [[concepts/langchain-middleware]]
- [[entities/langchain-builtin-middleware]]
- [[concepts/langchain-memory-and-context-engineering]]
- [[guides/langchain-rag-sql-voice-and-deep-agent]]

## 出處
- docs/langchain/human-in-the-loop.md
- docs/langchain/guardrails.md
