# Deep Agents Customization Guide

別名：Deep Agents 客製化指南、`create_deep_agent` 參數、`createDeepAgent` 參數、Deep Agents Stack、Middleware 執行順序
框架：deepagents

## 摘要
`create_deep_agent`（Python）與 `createDeepAgent`（TypeScript/JavaScript）是組裝 Deep Agents 的核心建構函式，在 LangChain 的 `create_agent` / `createAgent` 之上預先組裝了一套固定順序的 middleware 堆疊（Deep Agents stack）。開發者可透過參數自訂模型、系統提示、工具、記憶、技能、檔案系統後端、權限、子代理、結構化輸出與人類介入審批（HITL），並能透過匹配 `.name` 原地替換內建 middleware 或插入自訂 middleware。

## 重點
### `create_deep_agent` / `createDeepAgent` 參數對照
- **`model`**（Python `model=` / JS `model`）：指定使用的模型（`provider:model` 字串或已初始化的模型實例）。聊天模型會自動以指數退避（exponential backoff）重試暫時性 API 失敗（可調整 `max_retries` / `timeout`）。
- **`system_prompt`**（Python `system_prompt=` / JS `systemPrompt`）：自訂代理指令。除了字串外，主代理也接受帶有結構化內容區塊（content blocks）的 `SystemMessage`（子代理字典規格中的 `system_prompt` 則維持為字串）。
  - **宣告式子代理（Declarative subagents）提示解析**：先針對子代理自身的模型解析 profile overlays，再將解析後 profile 的 `base_system_prompt` 或 `system_prompt_suffix` 套用至子代理定義的 `system_prompt`。若 profile 僅有 `system_prompt_suffix` 則附加於後；若設定了 `base_system_prompt` 則直接完全取代。
  - **General-purpose 子代理提示解析順序**：`general_purpose_subagent.system_prompt`（若有設定）-> `HarnessProfile.base_system_prompt`（若有設定）-> SDK general-purpose 預設提示，最後再疊加上 profile 的 `system_prompt_suffix`。當兩者皆設定時，以 `general_purpose_subagent` 專屬設定優先。
- **`tools`**（Python `tools=` / JS `tools`）：代理可呼叫的領域工具（含自訂函式、LangChain 工具與 MCP 工具）。
- **`memory`**（Python `memory=` / JS `memory`）：啟動時載入的 `AGENTS.md` 檔案路徑清單（需先將檔案加入對應 backend）。
- **`skills`**（Python `skills=` / JS `skills`）：用於按需載入領域知識的技能目錄路徑（需先將檔案加入對應 backend）。
- **`backend`**（Python `backend=` / JS `backend`）：虛擬檔案系統後端，預設為 `StateBackend`。支援 `StateBackend`、`FilesystemBackend`、`LocalShellBackend`、`StoreBackend`（部署至 LangSmith Agent Server 時應省略 `store` 參數，由平台自動配置）、`ContextHubBackend`、`CompositeBackend` 以及各類 Sandbox 後端。
- **`permissions`**（Python `permissions=` / JS `permissions`）：檔案系統的路徑級別存取控制規則。
- **`subagents`**（Python `subagents=` / JS `subagents`）：用於委派任務的自訂子代理清單。
- **`middleware`**（Python `middleware=` / JS `middleware`）：合併至 Deep Agents stack 的額外 middleware。若傳入實例的 `.name` 與內建 middleware 項目相同，會**原地取代（replace in place）**該內建項目；否則會插入於 `PatchToolCallsMiddleware`（及 `AsyncSubAgentMiddleware`）之後、profile extras / skills / prompt caching / memory 之前。
- **`interrupt_on`**（Python `interrupt_on=` / JS `interruptOn`）：在工具呼叫前暫停以等待人類審批（Human-in-the-loop）。
- **`response_format`**（Python `response_format=` / JS `responseFormat`）：結構化輸出 schema。
  - Python：驗證後的結構化資料會存放在代理 state 的 `'structured_response'` 鍵中。
  - JS：可將 schema 包裝於 `langchain` 的 `toolStrategy()` 或 `providerStrategy()` 中，結果會存放在代理 state 的 `'structuredResponse'` 鍵中。
- **`state_schema`**（Python `state_schema=`）：自訂圖形狀態（graph state）schema。
- **`context_schema`**（Python `context_schema=` / JS `contextSchema`）：單次執行的執行階段上下文（runtime context）schema（如 user IDs、API keys、feature flags）。
- **`profiles`**（Python）：可重用的單一模型預設設定組合（`HarnessProfile`），可包含 `base_system_prompt`、`system_prompt_suffix`、工具描述覆寫、排除的工具或 middleware、額外注入的 middleware，以及對自動加入的 general-purpose 子代理的修改。

### Deep Agents Middleware Stack 完整執行順序
- **Bare stack（僅傳入 `model` 時的預設堆疊）**：
  - **Python 順序**：
    1. `FilesystemMiddleware`
    2. `SubAgentMiddleware`（預設自動加入 `general-purpose` 子代理，除非被 harness profile 停用）
    3. `SummarizationMiddleware`
    4. `PatchToolCallsMiddleware`
    5. **Prompt caching** middleware（始終註冊，在不支援的模型上為 no-op）
    6. **Harness profile extras**（若解析出的模型 profile 有定義）
    7. `UnsupportedContentMiddleware`
    8. `ModelRefusalMiddleware`
    9. **Excluded-tool filtering**（若解析出的模型 profile 有定義）
  - **JavaScript 順序**（注意第 7–9 項順序與 Python 略有不同）：
    1. `FilesystemMiddleware`
    2. `SubAgentMiddleware`
    3. `SummarizationMiddleware`
    4. `PatchToolCallsMiddleware`
    5. **Prompt caching** middleware
    6. **Harness profile extras**
    7. `modelRefusalMiddleware`
    8. **Excluded-tool filtering**
    9. `UnsupportedContentMiddleware`
- **Full stack（完整組裝順序，由先至後 1–14）**：
  1. `FilesystemMiddleware`：處理檔案讀寫與目錄瀏覽；若傳入 `permissions`，檔案系統權限強制檢查會包含在此處以評估代理呼叫的每個工具。
  2. `SubAgentMiddleware`：僅在至少有一個同步子代理可用時包含（預設因 `general-purpose` 子代理而包含）。
  3. `SummarizationMiddleware`：當對話過長時壓縮訊息歷史（透過 Python `create_summarization_middleware` / JS `createSummarizationMiddleware`）。此外 `deepagents` 亦提供 Python `create_summarization_tool_middleware`（讓代理在任務間隔等適當時機主動觸發摘要）。
  4. `PatchToolCallsMiddleware`：當執行從中斷恢復或收到格式錯誤的工具呼叫參數時，修復訊息歷史中懸空的工具呼叫（dangling tool calls）。在 Anthropic prompt caching 與後續堆疊**之前**執行。
  5. `AsyncSubAgentMiddleware`：僅在設定了 async subagents 時包含。
  6. **Your middleware argument**（使用者傳入的 `middleware`）：名稱未匹配內建項目者會插入在此處（位於 Patch 之後、其餘堆疊之前）。
  7. **Harness profile extras**：來自解析後模型 profile 的供應商特定 middleware。
  8. `SkillsMiddleware`：僅在傳入 `skills`（或 JS 傳入 `createSkillsMiddleware` 實例）時包含。在使用者 middleware 之後、prompt caching 正前方執行，因此能看到摘要後的對話與實際呼叫的模型。
  9. **Prompt caching**（`AnthropicPromptCachingMiddleware` 與 `BedrockPromptCachingMiddleware`）：Python 中兩者始終註冊並在非支援模型上忽略（`unsupported_model_behavior="ignore"`）；JS 中則分別針對 Anthropic 模型與 Amazon Bedrock Converse 模型自動加入。在 Patch 與使用者 middleware 之後執行，確保快取前綴與實際傳送給模型的內容一致。
  10. `MemoryMiddleware`：僅在傳入 `memory` 時包含。**刻意置於 profile extras 與 prompt caching middleware 之後**，使注入記憶的更新較不易讓快取前綴失效（invalidate cache prefix）。
  11. `HumanInTheLoopMiddleware`：僅在傳入 `interrupt_on` / `interruptOn` 時包含。
  12. **Python 第 12–14 項**：12. `UnsupportedContentMiddleware`（將請求中不支援的多模態內容改寫為文字佔位符） -> 13. `ModelRefusalMiddleware`（當模型拒絕時引發 `ModelRefusalError`，位於使用者 middleware 之後，讓使用者傳入的 `ModelFallbackMiddleware` 能先在下一個模型上重試） -> 14. **Excluded-tool filtering**。
  - **JavaScript 第 12–14 項**：12. `modelRefusalMiddleware`（拋出 `ModelRefusalError`，可搭配 `modelFallbackMiddleware`） -> 13. **Excluded-tool filtering** -> 14. `UnsupportedContentMiddleware`。
- **Synchronous subagent stack（同步子代理堆疊）**：
  - 內建的 `general-purpose` 子代理與每個宣告式同步 `SubAgent` 圖形皆使用相同的堆疊結構（包含 filesystem、summarization、Patch、profile extras、skills、Anthropic 與 Bedrock caching、選用的 permissions），**唯一差別是子代理圖形內部沒有 `SubAgentMiddleware`**（僅父代理暴露 `task` 工具）。若宣告式子代理設定了 `interrupt_on` / `interruptOn`，會轉發給子代理的 `create_agent` / `createAgent`。

### 自訂與覆寫 Middleware 注意事項
- **嚴禁在初始化後變動實例屬性（Do not mutate attributes after initialization）**：由於子代理、平行工具與不同執行緒的平行呼叫會同時執行，在 hook（如 `before_agent` / `beforeAgent`）中直接修改 `self.x` 或共享變數（或 JS 中直接修改 `state.x`）會導致 race conditions。跨 hook 追蹤數值必須使用以 thread 為範圍的 graph state。
- **覆寫預設 Middleware 實例（需 `deepagents>=0.7`）**：
  - 傳入 `.name` 與內建項目匹配的實例會**完全取代（replace，而非合併 merge）**預設實例，因此替換實例必須完整設定所需參數（例如覆寫 `FilesystemMiddleware` 時必須手動傳入 `backend` 與 `permissions`，因為它不會自動繼承傳給 `create_deep_agent()` 的 `backend=` 與 `permissions=`）。
  - 自動加入的 `general-purpose` 子代理會從主代理繼承預設 middleware 的覆寫；但透過 `subagents=` 定義的宣告式子代理**不會繼承**，必須在該子代理自身的 `middleware` 欄位中直接傳入覆寫實例。
- **常見 Middleware 覆寫範例**：
  - **調整摘要觸發閾值**：覆寫 `SummarizationMiddleware(model=model, backend=backend, trigger=("tokens", 100000), keep=("messages", 20))`（`trigger` 亦支援 `("fraction", ...)` 或以 OR 語義組合的列表）。
  - **使用較便宜的模型產生摘要（需 `deepagents>=0.7.26`）**：在 `SummarizationMiddleware` 設定 `summarizer="anthropic:claude-haiku-5-5"`（或傳入 `BaseChatModel`、`Runnable`、callable；若傳入 `Runnable` 或 callable 則不使用 `summary_prompt`），而主 `model` 仍負責提供 profile 與計算 token。
  - **更新 Prompt Cache TTL**：覆寫 `AnthropicPromptCachingMiddleware(ttl="1h")` 以將預設的 `5m` TTL 延長至 1 小時。
  - **自訂或隱藏技能目錄系統提示**：覆寫 `SkillsMiddleware(backend=backend, sources=[...], system_prompt=custom_skills_prompt)`，範本中**必須包含 `{skills_locations}`、`{skills_list}` 與 `{skills_load_warnings}` 三個插槽**，缺少任一插槽會在建構時引發 `ValueError`（此時請勿再傳入 `skills=` 給 `create_deep_agent`）。若設定 `system_prompt=None` 則完全不在系統提示附加技能目錄區塊，但技能仍會保留在 `state["skills_metadata"]` 中。
  - **將二進位檔案內容卸載出檢查點歷史（JS 範例，需 `deepagents>=1.14.2`）**：使用 `createFilesystemMiddleware({ backend, offloadBinaryContent: true })`，將二進位 `read_file` 負載與行內 `HumanMessage` 媒體儲存於 backend 的 `/blobs` 下（若 `/blobs` 路由至 `StateBackend` 則無效，需搭配 sandbox 或 `FilesystemBackend`）。

## 相關頁面
- [[concepts/deepagents-overview]]
- [[concepts/deepagents-subagents]]
- [[concepts/deepagents-backends-and-sandboxes]]
- [[concepts/deepagents-memory-and-skills]]
- [[concepts/deepagents-context-engineering]]
- [[concepts/deepagents-human-in-the-loop]]

## 出處
- docs/deepagents/customization.md
