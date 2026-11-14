# LangChain Built-in Middleware Reference

別名：內建中介軟體、預建中介軟體、Prebuilt Middleware、Built-in Middleware、Provider-agnostic Middleware
框架：langchain

## 摘要
LangChain 提供一系列可直接用於正式環境的內建中介軟體（Prebuilt / Built-in Middleware），涵蓋錯誤處理與重試（`ToolErrorMiddleware`、`ToolRetryMiddleware`、`ModelRetryMiddleware`）、模型備援與拒答處理（`ModelFallbackMiddleware`、`ModelRefusalMiddleware`）、上下文壓縮（`SummarizationMiddleware`、`ContextEditingMiddleware`）、人機迴圈（`HumanInTheLoopMiddleware`）、呼叫次數限制（`ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`）、安全與敏感資料防護（`PIIMiddleware`、`AutoModeMiddleware`）、工具與模型路由（`LLMToolSelectorMiddleware`、`ModelRouterMiddleware`、`ProviderToolSearchMiddleware`）、任務規劃與外部環境（`TodoListMiddleware`、`ShellToolMiddleware`、`FilesystemMiddleware`、`SubAgentMiddleware`、`RubricMiddleware`、`FilesystemFileSearchMiddleware`、`LLMToolEmulator`）以及供應商專屬中介軟體。

## 重點

### 一、錯誤處理、重試與模型備援（Error Handling, Retries & Fallbacks）
1. **Tool error（僅 Python：`ToolErrorMiddleware`，需 `langchain>=1.3.14`）**：
   - 攔截工具執行期間拋出的例外，將其轉換為 `ToolMessage(status="error")` 讓模型檢視並修正參數重試，避免代理直接崩潰或洩漏原始例外細節。
   - **重要組合規則**：本身不自動重試；若需搭配 `ToolRetryMiddleware`，應將 `ToolRetryMiddleware(..., on_failure="error")` 放在 `middleware` 清單的**內層（較後面的位置）**，讓重試耗盡後拋出的例外傳遞給外層的 `ToolErrorMiddleware`。
   - **設定參數**：
     - `on_error`（`Callable[[Exception, ToolCallRequest], str | list[ContentBlock] | None]`）：同步錯誤處理器（當未提供 `aon_error` 時亦用於非同步路徑）。回傳 `str` 或內容區塊列表時轉為錯誤 `ToolMessage`；回傳 `None` 時讓例外繼續向上拋出。
     - `aon_error`（`Callable[[Exception, ToolCallRequest], Awaitable[str | list[ContentBlock] | None]]`）：選用的非同步處理器（僅非同步時可單獨傳入 `aon_error` 而不傳 `on_error`）。
     - `tools`（`list[BaseTool | str]`，預設 `None` 套用至所有工具）。
2. **Tool retry（Python：`ToolRetryMiddleware` / JS：`toolRetryMiddleware`）**：
   - 以指數退避（Exponential backoff）自動重試失敗的工具呼叫。
   - **設定參數對照**：
     | Python 參數 | TypeScript/JS 參數 | 型別 | 預設值 | 說明 |
     | :--- | :--- | :--- | :--- | :--- |
     | `max_retries` | `maxRetries` | `number` | `2` | 初次呼叫後的最大重試次數（預設共嘗試 3 次） |
     | `tools` | `tools` | `list[BaseTool \| str]` / `(ClientTool \| ServerTool \| string)[]` | `None` / `undefined` | 套用重試的工具實例或名稱清單（未指定則套用全部） |
     | `retry_on` | `retryOn` | 例外 tuple 或 callable | `default_retry_on` / `(error) => getRetryable(error) ?? true` | Python `langchain>=1.3.16` 與 JS `langchain>=1.5.9` 預設不重試標記為 non-retryable 的錯誤，其餘錯誤皆重試 |
     | `on_failure` | `onFailure` | `'continue' \| 'error' \| callable` | `'continue'` | 重試耗盡行為：`'continue'`（回傳含錯誤的 `ToolMessage`）、`'error'`（重新拋出例外）、或自訂格式化函式。已棄用值：`'return_message'`（改用 `'continue'`）、`'raise'`（改用 `'error'`） |
     | `backoff_factor` | `backoffFactor` | `number` | `2.0` | 指數退避乘數：`initial_delay * (backoff_factor ** retry_number)`；設為 `0.0` 為固定延遲 |
     | `initial_delay` | `initialDelayMs` | `number` | `1.0` (秒) / `1000` (毫秒) | 第一次重試前的初始延遲時間 |
     | `max_delay` | `maxDelayMs` | `number` | `60.0` (秒) / `60000` (毫秒) | 延遲時間上限 |
     | `jitter` | `jitter` | `boolean` | `True` / `true` | 是否加入 `±25%` 隨機抖動以避免羊群效應（thundering herd） |
   - **JS 標記錯誤是否可重試（需 `@langchain/core>=1.2.8` 與 `langchain>=1.5.9`）**：
     - 從 `@langchain/core/errors` 匯入 `stampRetryable(error, boolean)` 與 `getRetryable(error)`（回傳 `true`、`false` 或 `undefined`）。
     - 聊天模型整合已自動將以下錯誤標記為不可重試（第一次失敗即終止）：Authentication failures、Permission denied、Unknown model、Context window overflow、Invalid tool results、Payload too large、Exhausted quota、Cancelled calls。Rate limits、timeouts 與 server errors 則維持可重試。
3. **Model retry（Python：`ModelRetryMiddleware` / JS：`modelRetryMiddleware`）**：
   - 以指數退避自動重試失敗的模型 API 呼叫。
   - 參數與 `ToolRetryMiddleware` 相同（不含 `tools` 參數）：`max_retries`/`maxRetries`（預設 `2`）、`retry_on`/`retryOn`、`on_failure`/`onFailure`（預設 `'continue'`，耗盡時回傳含錯誤細節的 `AIMessage`；`'error'` 則拋出例外；或傳入自訂函式）、`backoff_factor`/`backoffFactor`（預設 `2.0`）、`initial_delay`（預設 `1.0` 秒）/`initialDelayMs`（預設 `1000` 毫秒）、`max_delay`（預設 `60.0` 秒）/`maxDelayMs`（預設 `60000` 毫秒）、`jitter`（預設 `True`/`true`）。
4. **Model fallback（Python：`ModelFallbackMiddleware` / JS：`modelFallbackMiddleware`）**：
   - 當主要模型失敗時，依序自動切換至備援模型。
   - Python：`ModelFallbackMiddleware(first_model: str | BaseChatModel, *additional_models: str | BaseChatModel)`（如 `ModelFallbackMiddleware("gpt-5.4-mini", "claude-sonnet-4-6")`）。
   - TypeScript/JavaScript：`modelFallbackMiddleware(...models: string[])`。
5. **Model refusal（Python：`ModelRefusalMiddleware`，需 `langchain>=1.4.9` / JS：`modelRefusalMiddleware`，需 `langchain>=1.6.4`）**：
   - 當模型回應包含 `refusal` 內容區塊（OpenAI、Anthropic、Gemini 皆會產生）或在結構化 `response_format` / `responseFormat` 下因拒答而解析失敗時，拋出 `ModelRefusalError`（Python：`from langchain_core.exceptions import ModelRefusalError`；JS：`import { ModelRefusalError } from "@langchain/core/errors"`，可用 `ModelRefusalError.isInstance(error)` 檢查），避免將拒答當成正常最終回答結束。不會偵測模型以一般純文字撰寫的拒答；串流時模型在拒答前送出的文字可能會先抵達客戶端。
   - **堆疊順序規則**：必須將 `ModelRefusalMiddleware` 放在 `ModelFallbackMiddleware` **之後（內層）**，讓備援中介軟體捕捉 `ModelRefusalError` 並改用下一個模型重試。`ModelRetryMiddleware` 不會重試拒答（在 JS 中因 `modelRetryMiddleware` 預設 `onFailure: "continue"` 會把錯誤轉成最終回答，應將其放在 `modelRefusalMiddleware` 之後或設為 `onFailure: "error"`）。若所有備援模型皆拒答且想優雅回覆使用者，可在 `ModelFallbackMiddleware` **之前（最外層）**加上自訂 `wrap_model_call` 攔截 `ModelRefusalError` 並回傳 `AIMessage`。

---

### 二、上下文壓縮與管理（Summarization & Context Editing）
6. **Summarization（Python：`SummarizationMiddleware` / JS：`summarizationMiddleware`）**：
   - 當對話接近 token 門檻時，使用指定模型壓縮舊訊息並永久替換 state 中的歷史，保留近期訊息（僅壓縮文字，不會縮放或壓縮圖片/音訊/影片 payload；被保留的近期訊息仍含原始多模態區塊，被摘要的舊多模態訊息僅轉為文字摘要）。
   - **設定參數**：
     - `model`（`string | BaseChatModel`，必填）：產生摘要的模型（如 `"gpt-5.4-mini"`）。
     - `trigger`：觸發條件。支援三種門檻指標：`fraction`（模型上下文比例 `0`–`1`，需 `langchain>=1.1` / `langchain@1.1.0` 的模型 profile `max_input_tokens` / `maxInputTokens`）、`tokens`（絕對 token 數）、`messages`（訊息數）。
       - Python：可為單一 `ContextSize` tuple 如 `("tokens", 4000)` 或 `("fraction", 0.8)`、單一 `TriggerClause` dict 如 `{"tokens": 4000, "messages": 10}`（AND 邏輯），或兩者混合的 `list`（OR 邏輯）。
       - JS：單一物件 `{ tokens: 4000, messages: 10 }`（AND 邏輯）或物件陣列 `[{ tokens: 3000 }, { messages: 6 }]`（OR 邏輯）。
     - `keep`：保留多少近期上下文（僅能指定一種指標）。Python 預設 `('messages', 20)`；JS 預設 `{ messages: 20 }`。
     - `token_counter` / `tokenCounter`（選用函式，預設採字元數估算）。
     - `summary_prompt` / `summaryPrompt`（選用字串，需含 `{messages}` 佔位符）。
     - `trim_tokens_to_summarize` / `trimTokensToSummarize`（`number`，預設 `4000`）：送入摘要前的最大 token 數上限。
     - `summaryPrefix`（JS 選用字串；Python 的 `summary_prefix` 已棄用）。
     - 已棄用參數：`max_tokens_before_summary` / `maxTokensBeforeSummary`、`messages_to_keep` / `messagesToKeep`。
7. **Context editing（Python：`ContextEditingMiddleware` 與 `ClearToolUsesEdit` / JS：`contextEditingMiddleware` 與 `ClearToolUsesEdit`）**：
   - 當對話超過 token 上限時，清除較舊的工具呼叫輸出以節省 token，並保留最近 N 筆工具結果。
   - **`ContextEditingMiddleware` 參數**：
     - `edits`：預設 `[ClearToolUsesEdit()]` / `[new ClearToolUsesEdit()]`。
     - `token_count_method`（僅 Python，預設 `'approximate'`，可設為 `'model'`）。
   - **`ClearToolUsesEdit` 參數**：
     - `trigger`（Python） / `triggerTokens`（JS）：預設 `100000`。觸發清除的 token 數量。
     - `clear_at_least` / `clearAtLeast`：預設 `0`（最少需回收的 token 數，`0` 表示視需要清除）。
     - `keep`：預設 `3`（保留最近幾筆工具結果不清除）。
     - `clear_tool_inputs` / `clearToolInputs`：預設 `False` / `false`（設為 `True` 時，連同 AI 訊息上的原始工具呼叫參數一併替換為空物件）。
     - `exclude_tools` / `excludeTools`：預設 `()` / `[]`（排除不清除的工具名稱清單）。
     - `placeholder`：預設 `"[cleared]"`（替換被清除工具輸出的佔位文字）。

---

### 三、人機迴圈、呼叫限制與安全防護（HITL, Call Limits & Guardrails）
8. **Human-in-the-loop（Python：`HumanInTheLoopMiddleware` / JS：`humanInTheLoopMiddleware`）**：
   - 在工具執行前暫停代理，等待人類核准（`approve`）、編輯（`edit`）或拒絕（`reject`）。**必須搭配 checkpointer 使用**。
   - 預設每個模型回合（model turn）暫停一次；可設定 `interrupt_mode="per_call"`（Python）或 `interruptMode: "per_call"`（JS）改為每次工具呼叫獨立暫停並依 interrupt ID 回覆。
   - 透過 `interrupt_on` / `interruptOn` 設定各工具的審核規則（如 `{"your_send_email_tool": {"allowed_decisions": ["approve", "edit", "reject"]}, "your_read_email_tool": False}`）。
9. **Model call limit（Python：`ModelCallLimitMiddleware` / JS：`modelCallLimitMiddleware`）**：
   - 限制模型呼叫次數以防止無窮迴圈或失控成本。
   - **設定參數**：
     - `thread_limit` / `threadLimit`（`number`，跨整個執行緒的累計呼叫上限，需搭配 checkpointer，預設無限制）。
     - `run_limit` / `runLimit`（`number`，單次 `invoke` 執行的呼叫上限，預設無限制）。
     - `exit_behavior` / `exitBehavior`（`string`，預設 `'end'` 優雅終止；或 `'error'` 拋出例外）。
10. **Tool call limit（Python：`ToolCallLimitMiddleware` / JS：`toolCallLimitMiddleware`）**：
    - 限制全部工具（全域）或特定工具的呼叫次數（可堆疊多個實例分別限制全域與個別工具）。
    - **設定參數**：
      - `tool_name` / `toolName`（`string`，選用；未指定則套用至全域所有工具）。
      - `thread_limit` / `threadLimit`（`number`，跨執行緒上限，需 checkpointer）與 `run_limit` / `runLimit`（`number`，單次執行上限）——**兩者至少必須指定其一**。
      - `exit_behavior` / `exitBehavior`（預設 `'continue'`）：
        - `'continue'`（預設）：以錯誤訊息阻擋超額的工具呼叫，讓其他工具與模型繼續執行。
        - `'error'`：立即拋出 `ToolCallLimitExceededError` 例外中止執行。
        - `'end'`：立即以一則 `ToolMessage` 與 AI 訊息終止執行（僅適用於限制單一工具且無其他待執行工具呼叫時；若有其他待執行工具，Python 會拋出 `NotImplementedError`，JS 會拋出錯誤）。
11. **PII detection（Python：`PIIMiddleware` / JS：`piiMiddleware`）**：
    - 偵測並處理對話中的個人識別資訊（PII）。
    - **設定參數**：
      - `pii_type` / `piiType`（`string`，必填）：內建類型（`email`、`credit_card`、`ip`、`mac_address`、`url`）或自訂類型名稱。
      - `strategy`（`string`，預設 `'redact'`）：`'block'`（偵測到時拋出例外）、`'redact'`（替換為 `[REDACTED_{PII_TYPE}]` / `[REDACTED_TYPE]`）、`'mask'`（部分遮罩如 `****-****-****-1234`）、`'hash'`（替換為決定性雜湊如 `<email_hash:a1b2c3d4>`）。
      - `detector`：自訂偵測器，支援三種形式：(1) Regex 字串（如 `r"sk-[a-zA-Z0-9]{32}"`）、(2) 編譯過的正規表示式（Python `re.compile(...)` / JS `RegExp` 物件）、(3) 自訂偵測函式。
        - **Python 與 JS 的 `PIIMatch` 結構差異**：Python 自訂函式回傳 `list[PIIMatch]`，元素為 `{"type": "ssn", "value": ssn, "start": match.start(), "end": match.end()}`；JS 自訂函式回傳 `PIIMatch[]`，元素為 `{ text: ssn, start: ..., end: ... }`。
      - `apply_to_input` / `applyToInput`（`boolean`，預設 `True` / `true`）：在模型呼叫前檢查使用者訊息。
      - `apply_to_output` / `applyToOutput`（`boolean`，預設 `False` / `false`）：在模型呼叫後檢查 AI 訊息。在 Python `langchain>=1.3.2` 中，啟用 `apply_to_output=True` 亦會透過註冊的串流轉換器遮罩即時串流輸出（text deltas、tool-call args、tool outputs、state snapshots），該轉換器會扣留每個區塊最後 **128 個字元**以偵測跨 delta 邊界的匹配（自訂偵測器匹配長度應控制在 128 字元以內）。
      - `apply_to_tool_results` / `applyToToolResults`（`boolean`，預設 `False` / `false`）：檢查工具執行結果訊息。
12. **Auto mode（僅 Python：`AutoModeMiddleware`，Beta，需 `langchain>=1.5.0`）**：
    - 在執行指定的工具前，呼叫決策模型（如 `from langchain_typesafe import TypeSafeClassifier`）評估該工具呼叫是否具風險或未經使用者授權。
    - 若風險機率達到 **`0.5` 以上（`>= 0.5`）**，則阻擋執行並回傳錯誤 `ToolMessage`；未列在 `tools` 中的工具則直接執行不分類。

---

### 四、工具選擇、路由、規劃與外部環境（Routing, Planning, Shell, Filesystem & Testing）
13. **To-do list（Python：`TodoListMiddleware` / JS：`todoListMiddleware`）**：
    - 自動為代理掛載 `write_todos` 工具與系統提示詞，支援複雜多步驟任務規劃與進度追蹤。
    - Python 可選設定：`system_prompt`（`string`）、`tool_description`（`string`）；JS 無額外設定參數（使用預設值）。
14. **LLM tool selector（Python：`LLMToolSelectorMiddleware` / JS：`llmToolSelectorMiddleware`）**：
    - 在呼叫主模型前，先用較小或指定的 LLM 搭配結構化輸出選出與當前查詢最相關的工具（適合擁有 10+ 工具的代理）。
    - **設定參數**：`model`（預設使用代理的主模型）、`system_prompt` / `systemPrompt`、`max_tools` / `maxTools`（最多選幾個工具，預設無上限）、`always_include` / `alwaysInclude`（永遠包含且**不計入 `max_tools` 額度**的工具名稱清單）。
15. **Model router（僅 Python：`ModelRouterMiddleware` 與 `ModelChoice`，Beta，需 `langchain>=1.5.0`）**：
    - 在代理執行開始前，使用決策模型（`classifier=TypeSafeClassifier()`）根據最新的人類訊息從命名的 `choices`（字典，值為 `ModelChoice(model="...", criteria="...")`）與 `instructions` 中選出最適合的模型，將選擇結果存入狀態欄位 `model_route`，並在該次執行的所有模型呼叫中使用該模型。
16. **Provider tool search（Python：`ProviderToolSearchMiddleware` / JS：`providerToolSearchMiddleware`）**：
    - 將指定工具延遲載入，隱藏在模型供應商的伺服器端工具搜尋（Server-side tool search）背後，由模型按需檢索，避免一次傳送所有工具 schema 造成上下文膨脹。
    - **支援模型限制**：僅支援 Anthropic（Claude Sonnet 4+ / Opus 4+ / Haiku 4.5+）或 OpenAI（gpt-5.5+），其他供應商會拋出 `ValueError` / Error。
    - **設定方式**：透過 `searchable_tools` / `searchableTools` 傳入工具名稱或實例清單；或直接在建立工具時設定 `@tool(extras={"defer_loading": True})`（Python）或 `extras: { defer_loading: true }`（JS）。
17. **Shell tool（僅 Python：`ShellToolMiddleware`）**：
    - 為代理提供持久化的 shell 工作階段以依序執行系統指令。**目前限制：不支援與 HITL 中斷（interrupts）同時使用**。
    - **設定參數**：
      - `workspace_root`（`str | Path | None`）：工作目錄；未指定時會在代理啟動時建立暫存目錄並於結束時刪除。
      - `startup_commands`、`shutdown_commands`（啟動後與關閉前依序執行的指令）。
      - `execution_policy`（`BaseExecutionPolicy | None`）：
        - `HostExecutionPolicy()`（預設）：完整主機存取權。
        - `DockerExecutionPolicy(image="python:3.11-slim", command_timeout=60.0)`：每次執行啟動獨立 Docker 容器隔離。
        - `CodexSandboxExecutionPolicy`：重用 Codex CLI 沙箱限制 syscall 與檔案系統。
      - `redaction_rules`：傳入 `RedactionRule(pii_type="...", detector=r"...")` 清單，於指令執行後遮罩輸出。
      - `tool_description`、`shell_command`（預設 `"/bin/bash"`）、`env`（環境變數映射）。
18. **Filesystem middleware（Python：`from deepagents.middleware.filesystem import FilesystemMiddleware` / JS：`import { createFilesystemMiddleware } from "deepagents"`）**：
    - 提供 4 個檔案系統工具：`ls`、`read_file`、`write_file`、`edit_file`（`create_deep_agent` / `createDeepAgent` 已預設內建）。
    - 參數：`backend`（預設 `StateBackend`，儲存在短期圖形狀態）、`system_prompt` / `systemPrompt`、`custom_tool_descriptions` / `customToolDescriptions`、`tools`（Python 允許白名單限制暴露的工具）。
    - **跨執行緒長期儲存**：從 `deepagents.backends`（JS 為 `"deepagents"`）匯入 `CompositeBackend`、`StateBackend`、`StoreBackend`，設定 `CompositeBackend(default=StateBackend(), routes={"/memories/": StoreBackend()})`（JS 為 `new CompositeBackend(new StateBackend(), { "/memories/": new StoreBackend() })`），使 `/memories/` 前綴的檔案持久化至 LangGraph `store`。
19. **Subagent middleware（Python：`SubAgentMiddleware` / JS：Deep Agents subagent middleware）**：
    - 透過 `task` 工具將複雜任務委派給子代理以隔離上下文。子代理可透過宣告式設定（指定 `name`、`description`、`model`、`tools`、`system_prompt`、`middleware`）或直接傳入預先編譯的 LangGraph 圖形。`create_deep_agent` / JS 預設提供 `general-purpose` 子代理。
20. **Rubric grading（僅 Python：`RubricMiddleware`，需 `deepagents>=0.6.5`）**：
    - 以 LLM-as-a-judge 根據評分標準（Rubric）讓代理自我評估並反覆迭代，直到滿足標準或達到最大迭代上限。
21. **File search（僅 Python：`FilesystemFileSearchMiddleware`）**：
    - 在指定目錄上提供 `glob_search`（支援 `**/*.py` 等模式，依修改時間排序）與 `grep_search`（支援完整 regex、`include` 檔案過濾、以及三種輸出模式：`files_with_matches`、`content`、`count`）兩個工具。
    - **設定參數**：`root_path`（`str`，必填）、`use_ripgrep`（`bool`，預設 `True`，若無 ripgrep 則自動退回 Python regex）、`max_file_size_mb`（`int`，預設 `10` MB）。
22. **LLM tool emulator（Python：`LLMToolEmulator` / JS：`toolEmulatorMiddleware`）**：
    - 使用 LLM 模擬工具執行並產生合理回應，用於測試與原型開發而不實際執行外部工具。
    - **設定參數**：`tools`（預設 `None` / `undefined` 會模擬**所有**工具；傳入空陣列 `[]` 則不模擬任何工具；傳入工具名稱或實例陣列則僅模擬指定工具）、`model`（預設使用代理的主模型）。

---

### 五、供應商專屬中介軟體（Provider-specific Middleware）
- **Anthropic**：提供 Claude 模型專屬的 Prompt caching（`AnthropicPromptCachingMiddleware` / `anthropicPromptCachingMiddleware`）、bash tool、text editor、memory 與 file search 中介軟體。
- **AWS**：提供 Amazon Bedrock 模型的 Prompt caching 中介軟體。
- **OpenAI**（Python）：提供 OpenAI 模型的 Content moderation 中介軟體。

## 相關頁面
- [[concepts/langchain-middleware]]
- [[concepts/langchain-memory-and-context-engineering]]
- [[concepts/langchain-human-in-the-loop-and-guardrails]]
- [[guides/langchain-rag-sql-voice-and-deep-agent]]

## 出處
- docs/langchain/middleware/built-in.md
