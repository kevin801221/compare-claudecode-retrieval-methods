# Agent SDK Cost, Usage, and Todo Tracking

別名：成本與用量追蹤、待辦事項追蹤、Cost Tracking、Todo Tracking、Token Usage、Prompt Caching、ModelUsage、TaskCreate、TaskUpdate、TodoWrite
框架：agent-sdk

## 摘要
Claude Agent SDK 提供細緻的 Token 用量與成本估算欄位（如 `total_cost_usd`、`usage`、`modelUsage` / `model_usage`）及提示詞快取（Prompt Caching）TTL 控制，協助開發者在單次查詢、串流輸入模式、平行工具呼叫與子代理人執行時正確計算用量。此外，SDK 透過內建任務追蹤工具（`TaskCreate`、`TaskGet`、`TaskUpdate`、`TaskList` 及舊式 `TodoWrite`）將代理人的多步驟工作狀態以結構化工具呼叫暴露於訊息串流中，方便應用程式記錄任務日誌或即時渲染進度。

## 重點

### 成本與 Token 用量追蹤（`cost-tracking.md`）
- **用戶端估算性質與資料駐留加價（Data Residency Pricing）**：
  - `total_cost_usd` 與 `costUSD` 是**用戶端估算值（Client-side estimates）**，並非權威帳單數據（由建置時內建的價格表或 `modelPricing` 設定表在本地計算，可能因定價變動、SDK 不認識新模型或特殊計費規則而有偏差，切勿直接向終端使用者收費或觸發財務決策）。
  - **資料駐留定價規則**：當回應的 `usage` 報告 `inference_geo: "us"` 時，SDK 會將該回應的 Token 牌價乘以 `1.1`（如網頁搜尋等按次收費項目不乘以 1.1；需 TypeScript Agent SDK `v0.3.239` 以上或 Python Agent SDK `v0.2.144` 以上）。
- **TypeScript 與 Python 欄位對照**：
  - **單步（Per-step，每個 `AssistantMessage`）**：
    - TypeScript：巢狀於 `BetaMessage`（`message.message.id`、`message.message.usage`）。
    - Python：直接位於 `AssistantMessage` dataclass 上（`message.message_id`、`message.usage`）。
  - **結果訊息（`SDKResultMessage` / `ResultMessage`）**：
    - 總估計成本：兩者皆為 `total_cost_usd`（Python 中型別為 Optional，讀取前應確認非 `None`）。
    - 單一模型拆分：TypeScript 為 `message.modelUsage`；Python 為 `message.model_usage`。
    - 累積用量：`message.usage`（包含 `input_tokens`、`output_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`）。
- **三個層級的計算範圍與子代理人（Subagents）納入規則**：
  - `ResultMessage` 上的三個欄位對子代理人活動的計算方式不同（若有巢狀子代理人，請使用 `modelUsage` / `model_usage` 統計整棵樹的 Token）：
    1. `usage`：**不包含子代理人（Excluded）**，僅計算頂層主代理人迴圈（Top-level agent loop）。
    2. `total_cost_usd`：**包含子代理人（Included）**，將子代理人請求與頂層迴圈一併計入。
    3. `modelUsage` / `model_usage`：**包含子代理人（Included）**，按模型名稱拆分統計頂層迴圈與子代理人請求。
  - 在單一訊息輸入模式（Single message input mode）中，若最終回合結束時背景子代理人仍在執行，Claude Code 會等待其完成（受退出時背景任務上限約束）才發出結果訊息，等待期間的消耗皆計入 `total_cost_usd`、`duration_api_ms` 與 `modelUsage` / `model_usage`。
- **平行工具呼叫去重與 `output_tokens` 佔位符陷阱**：
  - **依訊息 ID 去重（Deduplicate by ID）**：當 Claude 在單一 API 回應中平行使用多個工具時，會產出多個共用相同 ID（`message.message.id` / `message.message_id`）且帶有完全相同 `usage` 物件的 `AssistantMessage`。累計單步 `input_tokens` 時必須以 `Set` 記錄看過的訊息 ID 並跳過重複 ID（若僅統計主迴圈還需確認 `!message.parent_tool_use_id`）。
  - **單步 `output_tokens` 為佔位符（Placeholder）**：`AssistantMessage` 上的 `output_tokens` 只是 API 在 `message_start` 時回報的初始計數（尚未生成回應前的數字），同一 API 回應產出的所有 `AssistantMessage` 都帶著這個相同的佔位符。**真實的輸出 Token 數量必須從最終 `ResultMessage` 的 `usage.output_tokens` 或 `modelUsage` 讀取**。
- **`modelUsage` / `model_usage` 欄位細節**：
  - 映射模型名稱至該模型的用量物件（TypeScript 屬性包含 `costUSD`、`inputTokens`、`outputTokens`、`cacheReadInputTokens`、`cacheCreationInputTokens`、`costBasis`）。
  - `costBasis`（需 Claude Code `v2.1.246` 以上）：標示最新請求使用的價格表來源，可能值為 `"list"`（牌價）、`"managed"`（`modelPricing` 表）或 `"unknown"`（未匹配模型 ID）。
- **串流輸入模式（Streaming Input Mode）下的成本計算與 `/clear` 重置**：
  - 在串流輸入模式中，單一 `query()` 承載多個使用者回合，**每個回合都會發出一個結果訊息**：
    - `usage`：僅涵蓋該單一回合（且僅限主迴圈）。
    - `total_cost_usd` 與 `modelUsage` / `model_usage`：攜帶整個呼叫目前為止的累計總額（加上恢復工作階段時還原的歷史花費）。若從未發送 `/clear`、`/reset` 或 `/new`，**直接讀取最後一個結果訊息即為總花費，切勿將各回合結果相加**。
  - 當應用程式發送 `/clear`、`/reset` 或 `/new` 時，累計總額會歸零重新計算（`maxBudgetUsd` / `max_budget_usd` 僅計算當前呼叫自身的花費，不包含 `resume` 還原的歷史花費，且 `/clear` 會重新計算預算）：
    - `/clear` 該回合自身的結果僅包含重置後的消耗，並帶有新的 `session_id`。
    - 計算整次呼叫總額的方式：**將每次 `/clear` 之前最後一個結果訊息的金額，加上整次呼叫最終結果訊息的金額**。
    - 每次重置時 SDK 會在串流中發出重置訊息：TypeScript 為 `SDKConversationResetMessage`，Python 為 `ConversationResetMessage`（注意：Python SDK `v0.2.137` 之前迭代器會丟棄此訊息，舊版需自行統計發送 `/clear` 的次數）。
- **跨多次 `query()` 呼叫與錯誤/崩潰恢復**：
  - **獨立呼叫（無 `resume` 或 `continue`）**：各自反映單次呼叫成本，需自行相加。
  - **恢復同一工作階段（`resume` / `continue`）**：自 Claude Code `v2.1.277` 起，正常退出時會將工作階段總花費存入 Transcript，並在後續 `resume` 或 `fork` 時還原；因此恢復後的結果訊息已包含先前花費，直接讀取最新結果即可，相加會重複計算（`v2.1.277` 之前透過 SDK 或 `claude -p` 恢復時總額會從 0 開始）。
  - **失敗對話與崩潰恢復（Session Crash）**：
    - `error_max_budget_usd`：結果的 `usage` 會漏掉跨越預算門檻的那次最後回應，但 `total_cost_usd` 與 `modelUsage` 有將其包含在內。
    - 當 Claude Code 行程崩潰並發出最終 `error_during_execution` 時，該結果上的 `usage`、`total_cost_usd`、`modelUsage` 可能全被歸零（Zeroed）。恢復步驟：(1) 若有崩潰前一回合的結果訊息（串流輸入模式且非第一回合、前一回合非 `/clear`），使用該結果的累計總額；(2) 否則退回將已收到的 `AssistantMessage` 按唯一訊息 ID 去重加總 `usage`，可救回主迴圈的 `input_tokens` 與快取 Token（子代理人用量、`output_tokens` 與美金成本無法以此方式救回）。
- **提示詞快取（Prompt Caching）與 1 小時 TTL 控制**：
  - SDK 自動啟用提示詞快取，`usage` 提供 `cache_creation_input_tokens`（建立新快取，費率較標準輸入高）與 `cache_read_input_tokens`（讀取既有快取，費率較低）。
  - 使用 API Key、Amazon Bedrock（`CLAUDE_CODE_USE_BEDROCK="1"`）、Google Cloud Agent Platform、Microsoft Foundry 或 Claude Platform on AWS 時，主對話快取預設為 **5 分鐘 TTL**（Claude 訂閱方案在內含額度內預設享有主對話 1 小時 TTL，當開始消耗額外 usage credits 時會降為 5 分鐘 TTL）。
  - **環境變數與設定優先順序**：
    - `ENABLE_PROMPT_CACHING_1H="1"`：同時對「主對話（Main conversation）」與「其他所有請求（如子代理人）」兩個時間桶（Bucket）請求 1 小時 TTL。
    - 若要分別設定兩個 Bucket（可設為 `"5m"` 或 `"1h"`，且**優先權高於 `ENABLE_PROMPT_CACHING_1H`**）：
      - 主對話：環境變數 `CLAUDE_CODE_PROMPT_CACHE_TTL` 或設定檔 `promptCacheTtl`。
      - 子代理人與其他請求：環境變數 `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` 或設定檔 `subagentPromptCacheTtl`。

### 待辦事項與任務追蹤（`todo-tracking.md`）
- **模型預設可用性（Model Availability，Claude Code `v2.1.268` / TypeScript SDK `v0.3.268` 起）**：
  - 任務追蹤工具預設**僅在 Claude Opus 4.7、Claude Sonnet 4.6、Claude Haiku 4.5 及更早的模型上提供**（較新的模型無需書面待辦清單即可追蹤多步驟工作）。
  - 在其他所有模型（包含 Claude Code 不認識的模型 ID）上，除非主動啟用（Opt-in），否則不會提供以下工具，串流中也不會出現其 `tool_use` 區塊：
    - `TodoWrite`
    - `TaskCreate`、`TaskGet`、`TaskUpdate`、`TaskList`
  - 在工具可用的環境中，Claude Code 預設提供四個 Task 工具（`TaskCreate`、`TaskGet`、`TaskUpdate`、`TaskList`）；若設定環境變數 `CLAUDE_CODE_ENABLE_TASKS=0`，則改為提供 `TodoWrite`。
- **強制啟用（Opt-in）任務工具的三種方式**：
  1. 在 `allowedTools`（TypeScript）/ `allowed_tools`（Python）中列出其中一個工具名稱。
  2. 在 `tools` 選項中列出這些工具（注意 `tools` 會將內建工具限制為清單內指定的集合，需連同其他要用的內建工具一起列出）。
  3. 在 `options.env` 設定 `"CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"`（TypeScript 需一併展開 `...process.env` 以保留繼承的環境變數；Python 的 `env` 則會自動疊加在繼承的環境變數之上）。
- **Todo 生命週期與四種狀態（Status）**：
  1. **Created（已建立）**：辨識出任務時透過 `TaskCreate` 新增，初始狀態為 `"pending"`。
  2. **Activated（進行中）**：開始執行該項工作時透過 `TaskUpdate` 設為 `"in_progress"`。
  3. **Completed（已完成）**：任務成功完成時透過 `TaskUpdate` 設為 `"completed"`。
  4. **Removed（已刪除）**：不再需要的待辦事項，會在 `TaskUpdate` 呼叫中設定 `status: "deleted"` 將其移除。
- **與背景任務系統訊息的區別**：
  - `SDKTaskNotificationMessage`（TypeScript）/ `TaskNotificationMessage`（Python）等系統訊息報告的是背景指令或背景子代理人；而待辦事項（Todo）活動則是透過 `AssistantMessage` 內的 `tool_use` 區塊呈現。
- **串流欄位防禦性讀取與 `tool_use_result` 配對技巧**：
  - **防禦性讀取鍵名**：串流中的 `tool_use` `input` 是模型輸出的原始格式；Claude Code 在執行前會自動修復相近但拼錯的鍵名（將 `id` 或 `task_id` 映射到 `taskId`，將 `active_form` 映射到 `activeForm`），但**這項修復不會反映在串流訊息中**。因此解析 `TaskCreate` 與 `TaskUpdate` 的 `input` 時應同時檢查：
    - 任務 ID：`input.taskId ?? input.id ?? input.task_id`
    - 進行中顯示文字：`input.activeForm ?? input.active_form`（當狀態為 `"in_progress"` 且有設定 `activeForm` 時，UI 應優先顯示 `activeForm` 取代 `subject`）。
  - **從 `UserMessage.tool_use_result` 取得分配的 Task ID**：
    - `TaskCreate` 的 `input` 內沒有任務 ID（只有 `subject` 與選用的 `activeForm`）。
    - 分配到的任務 ID 會在後續攜帶 `tool_result` 區塊的 `UserMessage` 上，透過 `message.tool_use_result` 欄位回傳（TypeScript 型別為 `TaskCreateOutput`，結構為 `{ task: { id: string, subject: string } }`；Python 為相同結構的 dict）。
    - 實作即時進度追蹤器（`TaskTracker`）時，應先在收到 `TaskCreate` 的 `tool_use` 時以 `block.id` 為鍵暫存 `{ subject, activeForm }`，等收到對應 `block.tool_use_id` 的 `tool_result`（且 `!block.is_error`）時，從 `message.tool_use_result.task.id` 取出正式任務 ID 並將狀態設為 `"pending"`。

## 相關頁面
- [[concepts/agent-sdk-streaming]]
- [[concepts/agent-sdk-sessions]]
- [[guides/agent-sdk-observability-and-troubleshooting]]

## 出處
- docs/agent-sdk/cost-tracking.md
- docs/agent-sdk/todo-tracking.md
