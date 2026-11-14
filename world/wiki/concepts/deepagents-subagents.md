# Deep Agents Subagents (Sync, Async & Dynamic)

別名：子代理、Subagents、`SubAgent`、`CompiledSubAgent`、`AsyncSubAgent`、Forked Subagents、Dynamic Subagents、`SubAgentMiddleware`、`AsyncSubAgentMiddleware`、`task` tool
框架：deepagents

## 摘要
Deep Agents 支援透過子代理（subagents）進行上下文隔離（context quarantine）與任務委派，避免多步驟任務的中間工具結果塞滿主代理的上下文視窗。系統提供三種子代理協調模式：同步子代理（透過 `SubAgentMiddleware` 與 `task` 工具阻塞等待最終報告，支援 `"isolated"` 與 `"fork"` 兩種上下文模式）、非同步子代理（透過 `AsyncSubAgentMiddleware` 在 Agent Protocol 伺服器背景執行並支援通知、狀態查詢、中途更新與取消），以及動態子代理（透過 QuickJS 程式碼直譯器中的全域 `task()` 函式以迴圈與平行批次進行程式化調度）。

## 重點
### 同步子代理（Synchronous Subagents）與預設行為
- **內建 `general-purpose` 子代理**：
  - Deep Agents 預設會自動加入一個名為 `general-purpose` 的同步子代理（除非已在 `subagents` 中提供同名同步子代理）。
  - 特性：使用專屬預設系統提示（並套用 profile overlays）、擁有與主代理相同的所有工具與模型（除非覆寫），且**當主代理設定了 `skills` 時會自動繼承主代理的技能**。
  - **取代方式**：在 `subagents` 清單中傳入 `name="general-purpose"`（Python）/ `name: "general-purpose"`（JS）的規格即可完全取代預設實例。
  - **重新命名或修改提示**：在啟用的 harness profile 上設定 `general_purpose_subagent=GeneralPurposeSubagentProfile(...)`。
  - **完全停用同步子代理（移除 `task` 工具）**：1. 在啟用的 harness profile 上設定 `general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)`；2. 不在 `create_deep_agent` 的 `subagents=` 傳入任何同步子代理。此時 Deep Agents 不會掛載 `SubAgentMiddleware` 與 `task` 工具。（切勿在 `excluded_middleware` 中排除 `SubAgentMiddleware`，否則會引發 `ValueError`）。
- **`SubAgent`（字典格式規格欄位，Python vs. JS）**：
  - `name`（`str` / `string`，必填）：唯一識別碼，主代理呼叫 `task()` 時使用，並寫入 `AIMessage` 與串流元資料的 `lc_agent_name` 鍵。
  - `description`（`str` / `string`，必填）：具體且具行動導向的功能描述，供主代理決定何時委派。
  - `system_prompt`（Python `str`）/ `systemPrompt`（JS `string`）：在預設 `mode: "isolated"` 下為**必填**（不從主代理繼承）；在 `mode: "fork"` 下則應省略（若設定則會附加在繼承的父代理提示之後）。
  - `mode`（`"isolated"` | `"fork"`，選填）：預設為 `"isolated"`（僅看見委派任務描述）；設為 `"fork"` 則繼承父代理的有效對話歷史與狀態。
  - `tools`（Python `list[Callable]` / JS `StructuredTool[]`，選填）：預設繼承主代理的工具；一旦指定則**完全覆寫（replaces entirely）**繼承的工具清單（檔案系統與其他 middleware 工具會另外附加）。
  - `model`（Python `str` | `BaseChatModel` / JS `LanguageModelLike | string`，選填）：預設繼承主代理模型，可傳入 `'provider:model'` 字串（如 `'openai:gpt-6.1-sol'`）或模型物件。
  - `middleware`（Python `list[Middleware]` / JS `AgentMiddleware[]`，選填）：在 `"isolated"` 模式下不繼承主代理的自訂 middleware，會合併至 synchronous subagent stack。
  - `interrupt_on`（Python `dict[str, bool | InterruptOnConfig]`）/ `interruptOn`（JS `Record<string, boolean | InterruptOnConfig>`，選填）：預設繼承主代理的 HITL 設定，子代理設定值會覆寫預設值（需要 checkpointer）。
  - `skills`（Python `list[str]` / JS `string[]`，選填）：技能來源目錄路徑清單（如 `["/skills/researcher/"]`）。**自訂子代理預設不繼承主代理的 `skills`**（僅 `general-purpose` 會繼承）。設定後該子代理會執行各自獨立的 `SkillsMiddleware` 實例，技能狀態在父子代理間雙向完全隔離。
  - `response_format`（Python `ResponseFormat`，需 `deepagents>=0.5.3`）/ `responseFormat`（JS `ResponseFormat`，需 `deepagents>=1.8.4`）：結構化輸出 schema（Python 支援 Pydantic models、`ToolStrategy(...)`、`ProviderStrategy(...)` 或 raw schema；JS 支援 Zod schemas、JSON schema 物件、`toolStrategy(...)`、`providerStrategy(...)`）。完成時結構化回應會序列化為 JSON 作為 `ToolMessage` 內容回傳給父代理。
  - `permissions`（Python `list[FilesystemPermission]` / JS `FilesystemPermission[]`，選填）：預設繼承主代理權限；設定後會**完全取代（replaces entirely）**父代理的權限規則。
- **`CompiledSubAgent`（預編譯 LangGraph 圖形規格）**：
  - 欄位：`name`（`str`，必填）、`description`（`str`，必填）、`runnable`（`Runnable`，必填，必須先呼叫 `.compile()` 編譯，且自訂 LangGraph 圖形的 state 必須包含 `"messages"` 鍵）、`mode`（`"isolated"` | `"fork"`，選填，預設 `"isolated"`；即使設為 `"fork"`，已編譯圖形仍保留其自身的系統提示）。

### Forked Subagents（`mode: "fork"`，Beta）
- **版本需求**：Python 需 `deepagents>=0.7.13`；JS 需 `deepagents>=1.13.3`。
- **運作機制**：
  - 接收父代理當下的有效對話歷史（若父代理已壓縮歷史，則接收壓縮後的上下文，而非複製持久化 checkpoint 歷史）加上委派任務描述。
  - Deep Agents 會移除父代理最後一筆呼叫 `task` 的 tool call（Python 參數為 `subagent_type` 與 `description`；JS 為 `subagentType` 與 `description`），並改為附加一則帶有延續前導文（continuation preamble）的 `HumanMessage`：`"Continuing as the subagent that was just invoked. <task description>"`。
  - **無法再呼叫其他子代理**（不可使用 `task` 工具，必須自行完成工作）。
- **繼承與限制**：
  - 繼承父代理的 `skills`；在 fork 模式下**禁止設定 `skills`**（提供時會被拒絕）。
  - 在 Python 中會繼承傳給父代理 `create_deep_agent` 的自訂 `middleware`（同名 `.name` 會原地取代，其餘加入堆疊）。
  - 若要修改 fork 的系統提示而不影響父代理，可在 Python 使用 `wrap_model_call` hook 讀取 `request.system_message` 並呼叫 `request.override(system_message=...)`；但應避免改寫共享的繼承前綴（例如在前綴前插入文字）或變更工具定義，否則會破壞跨供應商的 Prompt Cache 重用。

### 模型拒絕處理（Model Refusals）
- **版本需求**：Python 需 `deepagents>=0.7.33`；JS 需 `deepagents>=1.16.4`。
- 當子代理（含同步、非同步與結構化輸出子代理）的最後一則訊息為 `refusal` 內容區塊、引發/拋出 `ModelRefusalError` 或因拒絕導致結構化輸出解析失敗時，不會使整個執行失敗或回傳空結果，而是向父代理回傳一段簡短結果（且不回傳子代理在拒絕前變更的任何 state）：
  `The subagent stopped because a model refused the request. Retrying the same request is unlikely to succeed; rephrase it or continue without it.`（針對 Anthropic 模型還會附上類別，如 `Category: cyber.`）。
- 主代理自身若發生模型拒絕，則會因堆疊中的 `ModelRefusalMiddleware` / `modelRefusalMiddleware` 引發 `ModelRefusalError`（可透過傳入 `ModelFallbackMiddleware` / `modelFallbackMiddleware` 先攔截並切換備援模型重試）。

### 上下文傳遞、串流與 LangSmith 追蹤
- **Runtime Context 傳遞**：父代理 `invoke` / `ainvoke` 傳入的 `runtime.context` 會自動傳播至所有子代理；若需為特定子代理傳遞專屬設定，可使用命名空間鍵（如 `researcher:max_depth`）或在 context 型別上定義獨立欄位。工具內部也可結合讀取 `runtime.context` 與 `runtime.config` metadata 中的 `lc_agent_name` 來區分是哪個代理發起呼叫。
- **進度串流**：透過 `stream_events`（Python）/ `streamEvents`（JS）並迭代 `stream.subagents`，每個子代理 handle 暴露 `.name`、`.messages`、`.tool_calls` 與 `.output`。
- **LangSmith 過濾**：所有由子代理或協調器執行的 run 都會在 metadata 的 `lc_agent_name` 鍵記錄代理名稱（如 `{'lc_agent_name': 'research-agent'}`）。在 LangSmith SDK 中可使用 `filter='has(metadata, \'{"lc_agent_name": "research-agent"}\')'` 或 `filter="has(metadata, 'lc_agent_name')"` 進行查詢。

### 非同步子代理（Async Subagents）
- **核心架構與與同步子代理差異**：
  - 執行於實作 **Agent Protocol** 的伺服器（如 LangSmith Agent Server 或自託管伺服器；Managed Deep Agents 中可設定 `async: true`）。
  - 具備狀態（Stateful，在專屬伺服器 thread 上跨互動維持狀態）、平行且非阻塞（Parallel and non-blocking），啟動後立即回傳 task ID（即該子代理的 thread ID）。
- **`AsyncSubAgent` 規格欄位（Python vs. JS）**：
  - `name`（`str` / `string`，必填）：唯一識別碼。
  - `description`（`str` / `string`，必填）：子代理功能描述。
  - `graph_id`（Python `str`）/ `graphId`（JS `string`，必填）：Agent Protocol 伺服器上的 graph ID（或 assistant ID），在 LangGraph 部署中須匹配 `langgraph.json` 中註冊的圖形名稱。
  - `url`（`str` / `string`，選填）：省略時，Python 使用行程內的 **ASGI transport**（零網路延遲、無須額外驗證）；JS 則連線至同一 Agent Server 部署提供的位址（Agent Server `0.18.0` 以上或 `langgraph dev` 支援，其他環境預設為 `http://localhost:8123`）。設定 `url` 時則切換為 **HTTP transport** 連往遠端伺服器（LangGraph 部署使用環境變數 `LANGSMITH_API_KEY` 或 `LANGGRAPH_API_KEY` 驗證）。
  - `headers`（Python `dict[str, str]` / JS `Record<string, string>`，選填）：自訂遠端伺服器請求標頭。
  - `mode`（`"isolated" | "fork"`，選填）：預設為 `"isolated"`；`"fork"`（Experimental，JS 需 `deepagents>=1.16.0`）會在啟動時傳送父代理有效對話歷史的快照（snapshot）與任務描述作為新 thread 的執行輸入（若 JS 父代理啟用 `offloadBinaryContent`，fork 模式僅傳送媒體參照，子代理必須是共享同一 backend 的 deep agent 才能讀取該媒體）。
  - `update_strategy`（Python，需 `deepagents>=0.7.30`）/ `updateStrategy`（JS，需 `deepagents>=1.16.0`）：值為 `"interrupt" | "enqueue"`，預設為 `"interrupt"`（中斷前一次執行並以完整歷史加新指令重啟，task ID 不變）；設為 `"enqueue"` 則將新執行排隊於當前執行之後（狀態為 `pending` 直到開始，若當前執行在後續開始前暫停等待輸入，該等待請求會被丟棄並直接啟動後續執行）。
  - `webhook`（`str` / `string`，選填，Python 需 `deepagents>=0.7.30`，JS 需 `deepagents>=1.16.0`）：當子代理執行完成時由 Agent Server 呼叫的應用程式 URL（包含 thread ID、run ID、status，以及 metadata 中的 `parent_thread_id` 與 `subagent_name`）。
  - `notify_parent`（Python `bool`，預設 `True`，需 `deepagents>=0.7.30`）/ `notifyParent`（JS `boolean`，預設 `true`，需 `deepagents>=1.16.0`）：子代理完成或失敗時是否喚醒閒置中的 supervisor。
- **`AsyncSubAgentMiddleware` 提供的 5 個工具**：
  1. `start_async_task`：啟動背景任務並立即回傳 Task ID（同時在子代理 thread 上設定 `metadata={"parent_thread_id": ...}`，Python 需 `deepagents>=0.7.26`、JS 需 `deepagents>=1.16.0`）。
  2. `check_async_task`：查詢任務目前狀態，並回傳結果、錯誤或正在等待使用者輸入的待處理中斷（pending interrupts）。
  3. `update_async_task`：向任務傳送新追蹤指令。
  4. `cancel_async_task`：在伺服器呼叫 `runs.cancel()` 並將任務標記為 `"cancelled"`。
  5. `list_async_tasks`：列出所有追蹤中任務及其即時狀態（非終端狀態會平行向伺服器查詢；終端狀態 `success`、`error`、`timeout`、`cancelled`、`interrupted` 則使用快取狀態，不回傳結果內容）。
- **狀態保存、通知機制與 `waiting` 狀態**：
  - **專屬狀態通道**：任務元資料保存在 supervisor 圖形的專用狀態通道——Python 為 `async_tasks`（記錄 task ID、agent name、thread ID、run ID、status，以及 `created_at`、`last_checked_at`、`last_updated_at`）；JS 為 `asyncTasks`（時戳為 `createdAt`、`checkedAt`、`updatedAt`）。這確保對話歷史經過多次摘要壓縮（summarization）後也不會遺失 task IDs。
  - **主動通知（Task notifications，Python 需 `deepagents>=0.7.26`、metadata 需 `>=0.7.33`；JS 需 `deepagents>=1.16.0`、metadata 需 `>=1.16.2`）**：在 Agent Server 上，子代理完成、失敗或需要輸入時會主動通知 supervisor（無須輪詢）。當兩個代理位於同一部署（single deployment）且子代理本身也是 deep agent 時，完成或失敗會啟動新 run 喚醒閒置的 supervisor（等待輸入 `waiting` 則不會喚醒閒置 supervisor，會在下次執行時收到）。通知以 `HumanMessage` 傳入（支援圖片等多模態媒體），其 metadata 的 `source` 為 `"async_subagent"`，`data` 為 `TaskEvent`（含 `task_id`、`agent_name`、`status`、`run_id`），可透過 Python `get_notification_metadata` 或 JS `getNotificationMetadata` 讀取。
  - **處理等待輸入（`waiting` status，Python 需 `deepagents>=0.7.26`；JS 需 `deepagents>=1.16.0`）**：當子代理因 `interrupt()` 或 HITL 暫停時，`check_async_task` 與 `list_async_tasks` 會回報狀態為 `waiting`（僅 `check_async_task` 會附上 pending interrupts）。**Supervisor 無法代使用者回答或批准**，應用程式必須直接對子代理自身的 thread（thread ID 即 task ID）回覆 resume。
  - **本地開發 Worker Pool 配置**：使用 `langgraph dev` 時，每個活躍執行（含 supervisor 與各個活躍子代理）各佔用一個 worker slot，應使用 `langgraph dev --n-jobs-per-worker 10` 擴充容量以避免子代理排隊卡住。

### 動態子代理（Dynamic Subagents，Beta）
- **套件需求與啟用方式**：
  - Python：需 Python 3.11+ 與 `langchain-quickjs>=0.2.0`，安裝 `pip install -U "deepagents[quickjs]"` 或 `uv add "deepagents[quickjs]"`，並在 `middleware` 加入 `CodeInterpreterMiddleware`。
  - TypeScript/JavaScript：安裝 `npm install deepagents @langchain/quickjs`，並使用 `createCodeInterpreterMiddleware`。
  - 當代理同時具備 subagents 與 interpreter middleware 時，動態子代理分派預設為啟用；若要停用並強制只走一般 `task` 工具路徑，可傳入 Python `CodeInterpreterMiddleware(subagents=False)` 或 JS `createCodeInterpreterMiddleware({ subagents: false })`。
  - 亦可直接使用內建啟用 code interpreter 的 LangChain 終端機編碼代理 `dcode`（安裝：`curl -LsSf https://langch.in/dcode | bash`）。
- **運作機制與觸發方式**：
  - 直譯器環境會暴露內建的 `task()` 全域函式，接受三個輸入參數：`description`（子代理提示）、`subagentType`（要執行的子代理名稱）、`responseSchema`（選填，結構化輸出 schema，解析後直接為強型別 JS 物件，無須再呼叫 `JSON.parse`）。
  - **觸發關鍵字 `"workflow"`**：直譯器系統提示將 `"workflow"` 視為透過直譯器組織工作並從程式碼呼叫 `task()` 的信號。在提示詞中加入 `"workflow"` 即可明確引導代理進行程式碼扇出（fan-out）調度。
  - 支援遞迴語言模型（Recursive Language Models, RLM）工作流（在 Python 預設 `mode="thread"` 下可跨回合持久化直譯器變數），並可搭配程式化工具呼叫（Programmatic Tool Calling, PTC，預設關閉，需在 interpreter middleware 的 allowlist 中明確啟用如 `glob` 等工具以透過 `tools.*` 呼叫）。
- **六大常見動態編排模式（Patterns）**：
  1. **Classify and act**：先分類項目，再依類別分派給不同專長的子代理（如工單分流）。
  2. **Fan-out and synthesize**：平行將相同工作分派至大量項目（如結合 PTC `glob` 審查目錄下所有檔案），再於程式碼中彙整結果。
  3. **Adversarial verification**：兩階段模式——第一階段由 workers 產出發現（findings），第二階段將每項發現交由多個獨立 verifiers 進行多數決投票（majority vote），降低誤報。
  4. **Generate and filter**：由多個生成器子代理平行產生獨立解法，再於程式碼中評分、過濾並選出最佳結果。
  5. **Tournament**：由裁判（judge）子代理進行兩兩單淘汰對決（head-to-head elimination rounds）選出最終勝者。
  6. **Loop until done**：執行探索迴圈並與已發現項目去重，直到不再出現新結果為止（適用於死碼偵測、相依性稽核等未知範圍的全面清查）。
- **安全與審批注意事項**：由於 `task()` 是從已經在執行中的 `eval` 工具呼叫內部發起分派，不會經過父代理正常工具呼叫路徑，因此**父代理上的 `interrupt_on` / `interruptOn` 審批工作流不會針對每次 `task()` 分派強制執行**；若需在動態子代理編排執行前進行人工審批，必須對 `eval` 工具本身設定 gate（審批攔截）。

## 相關頁面
- [[concepts/deepagents-overview]]
- [[guides/deepagents-customization]]
- [[concepts/deepagents-human-in-the-loop]]
- [[concepts/deepagents-streaming-and-fault-tolerance]]
- [[concepts/agent-sdk-subagents]]

## 出處
- docs/deepagents/subagents.md
- docs/deepagents/async-subagents.md
- docs/deepagents/dynamic-subagents.md
