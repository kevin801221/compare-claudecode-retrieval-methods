# Agent Loop & Message Lifecycle

別名：Agent Loop 運作原理、代理迴圈、Turn 生命週期、訊息型別、Context Compaction、Effort Level
框架：agent-sdk

## 摘要
Agent SDK 執行與 Claude Code 相同的自主代理迴圈（agent loop）：接收提示詞、由 Claude 評估並呼叫工具、收集工具執行結果回饋給 Claude，並不斷重複直到產生不含工具呼叫的最終文字回應。開發者可透過訊息串流監控進度，並利用 `maxTurns`、`maxBudgetUsd`、`effort` 與自動上下文壓縮（compaction）精確控制迴圈的成本、推理深度與終止條件。

## 重點
### 迴圈步驟與回合（Turns）定義 (`agent-loop.md`)
- **五階段生命週期**：
  1. **Receive prompt**：接收 prompt、system prompt、工具定義與對話歷史，首先產出 `subtype` 為 `"init"` 的 `SystemMessage`。
  2. **Evaluate and respond**：Claude 評估狀態並回應文字或工具呼叫請求，SDK 為每個內容區塊（如 `TextBlock` 或 `ToolUseBlock`）產出一個 `AssistantMessage`。
  3. **Execute tools**：SDK 執行請求的工具並收集結果，產出包含工具結果的 `UserMessage` 回饋給 Claude（可透過 hooks 在執行前攔截、修改或阻擋）。
  4. **Repeat**：重複步驟 2 與 3，直到 Claude 產出不含任何工具呼叫的回應。
  5. **Return result**：產出最後一個純文字的 `AssistantMessage`，接著產出包含最終文字、token 用量、花費與 `session_id` 的 `ResultMessage`。
- **Turn（回合）的定義與計算**：
  - 一個 turn 代表迴圈的一次傳遞（Claude 產生輸出，若有工具呼叫則由 SDK 自動執行並將結果送回，期間不將控制權交還給呼叫端程式碼）。
  - 設定 `max_turns` / `maxTurns` 時，必須將**每個包含工具呼叫的回合**加上**最後一個純文字回應的回合（+1）**一併計入。若缺少最後這一個額外回合，執行會以 `subtype` 為 `error_max_turns` 的 `ResultMessage` 結束且無最終文字回應。

### 五大核心訊息型別（Message Types）
- **`SystemMessage`**：工作階段生命週期事件，由 `subtype` 區分：
  - `"init"`：包含該次執行的工作階段中繼資料（session metadata）。若有 `SessionStart` 或 `Setup` hook 在啟動期間執行，其 hook 生命週期訊息會在 `"init"` 訊息**之前**抵達。在 TypeScript 中，`session_id` 直接位於 init `SystemMessage` 欄位上；在 Python 中則巢狀於 `SystemMessage.data` 內。
  - `"compact_boundary"`：在自動或手動壓縮（compaction）完成後觸發。
  - `"informational"`：來自迴圈的純文字狀態橫幅。
  - `"worker_shutting_down"`：主機正在結束或 Remote Control 已斷線。
  - **TypeScript 與 Python 差異**：在 TypeScript 中，除了 `"init"` 以外的每個 subtype 在 `SDKMessage` 聯集型別中皆為獨立型別（例如 `SDKCompactBoundaryMessage`），而非 `SDKSystemMessage` 的子型別。
- **`AssistantMessage`**：Claude 回應中的每個內容區塊（包含最後的純文字回應）各發出一筆，同一回應的多筆訊息共用同一個 message ID。
  - 在 Python 中以 `isinstance(message, AssistantMessage)` 判斷，內容區塊位於 `message.content`（型別如 `TextBlock`、`ToolUseBlock`）。
  - 在 TypeScript 中以 `message.type === "assistant"` 判斷，原始 API 訊息被包裝在 `.message` 欄位下，因此內容區塊位於 `message.message.content`（透過 `block.type === "text"` 或 `block.type === "tool_use"` 判斷）。
- **`UserMessage`**：每次工具執行完畢後發出（帶有送回給 Claude 的工具結果內容），或在迴圈進行中串流傳入使用者輸入時發出。在 TypeScript 中同樣將原始訊息包裝於 `message.message`。
- **`StreamEvent`**：僅在啟用部分訊息（Python 為 `include_partial_messages`，TypeScript 為 `includePartialMessages`）時發出，包含原始 API 串流事件（文字 deltas、工具輸入 chunks）。
- **`ResultMessage`**：標記代理迴圈結束。少數尾部系統事件（如 `prompt_suggestion`）可能會在 `ResultMessage` **之後**抵達，因此應將串流迭代至自然結束，不要在收到 `ResultMessage` 時直接 `break`。

### 工具執行與平行化（Tool Execution & Parallelism）
- **內建工具分類**：
  - **File operations**：`Read`、`Edit`、`Write`。
  - **Search**：`Glob`、`Grep`。
  - **Execution**：`Bash`。
  - **Web**：`WebSearch`、`WebFetch`。
  - **Discovery**：`ToolSearch`（動態按需尋找並載入工具，而非預先全部載入）。
  - **Orchestration**：`Agent`、`Skill`、`AskUserQuestion`、`TaskCreate`、`TaskUpdate`（在預設不提供任務追蹤工具的模型上，需主動 opt in 才會提供 `TaskCreate` 與 `TaskUpdate`）。
- **平行與循序執行規則**：
  - 當 Claude 在單一回合請求多個工具呼叫時，**唯讀工具**（如 `Read`、`Glob`、`Grep` 及標記為唯讀的 MCP 工具）可**並行（concurrently）**執行。
  - **會修改狀態的工具**（如 `Edit`、`Write`、`Bash`）會**循序（sequentially）**執行以避免衝突。
  - **自訂工具（Custom tools）**預設為循序執行；若要啟用平行執行，必須在其 annotations 中設定 `readOnlyHint`（Python 與 TypeScript SDK 皆使用此來自 MCP SDK 的欄位名稱）。

### 回合上限、預算上限與推理深度（Turns, Budget & Effort）
- **`max_turns` / `maxTurns` 與 `max_budget_usd` / `maxBudgetUsd`**：
  - 預設皆為無限制（No limit）。達到上限時回傳 `subtype` 為 `error_max_turns` 或 `error_max_budget_usd` 的 `ResultMessage`。
  - **Subagent 花費計入總預算**：預算上限涵蓋所有 subagents 的花費。一旦總花費達到上限，嘗試衍生新的 subagent 會失敗並回傳 `Budget limit reached`，且 Claude Code 會停止所有仍在背景執行的 subagents（此強制停止行為需要 Claude Code **v2.1.217** 或更新版本）。
  - **Streaming input 佇列行為**：當某回合因達到 `maxTurns` 而結束時，仍在佇列中的訊息不會被併入該回合最後一次模型呼叫，而是啟動新回合作為起點，且 `maxTurns` 計數會針對該新訊息重新計算。預算總額則會跨訊息持續累加，一旦達到 `maxBudgetUsd`，同一對話的後續訊息皆會以 `error_max_budget_usd` 結束；發送 `/clear` 可重設預算計數。
  - **Budget headroom（預算緩衝空間）**：Claude Code 是在收到模型回應後才根據 API 回傳的 token 用量計算花費並與上限比對。因此，觸發上限的那一次模型回應仍會完成並計入 `total_cost_usd`，加上當下仍在執行中的 subagents 在停止前產生的花費，最終總花費可能會超過設定上限。
- **Effort level（`effort` 選項）**：
  - 控制每次回應的推理深度，共有五個等級：
    - `"low"`：極簡推理、快速回應（適合檔案查找、列出目錄）。
    - `"medium"`：平衡推理（適合例行編輯、標準任務）。
    - `"high"`：深入分析（適合重構、除錯）。
    - `"xhigh"`：擴展推理深度（適合支援該等級之模型上的程式編寫與代理任務）。
    - `"max"`：最大推理深度（適合需要深度分析的多步驟問題）。
  - 可在頂層 `query()` options 設定整個工作階段的 `effort`，或在 `AgentDefinition` 的 `effort` 欄位為個別 subagent 覆寫。
  - Extended thinking 會在輸出中產生 `thinking` 區塊，可透過 `ThinkingConfig` 上的 `display` 欄位控制是否接收其文字內容。

### 上下文視窗與自動壓縮（Context Window & Automatic Compaction）
- **上下文累積與快取**：同一工作階段內跨回合不會重設上下文。跨回合維持不變的前綴內容（system prompt、工具定義、`CLAUDE.md`）會自動進行 prompt caching。
- **各來源的上下文消耗**：
  - **System prompt**：每次請求固定載入。
  - **`CLAUDE.md` 檔案**：工作階段啟動時透過 `settingSources` 載入，每次請求包含完整內容（有 prompt cache）。
  - **Tool definitions**：核心內建工具（如 `Bash`、`Read`、`Edit`）每次請求載入；MCP 工具與其他內建工具預設由 tool search 延遲並按需載入（若關閉 tool search 或觸發 fallback 則會在每次請求預先載入所有 schema）。
  - **Conversation history**：隨回合累積（prompts、responses、tool inputs、tool outputs）。
  - **Skill descriptions**：工作階段啟動時載入簡短摘要，完整內容僅在被呼叫時載入。
- **自動壓縮（Automatic compaction）**：
  - 當上下文視窗接近上限時，SDK 會自動摘要舊歷史並保留近期對話與關鍵決策，同時在串流中發出 `type: "system"` 且 `subtype: "compact_boundary"` 的訊息（Python 為 `SystemMessage`，TypeScript 為 `SDKCompactBoundaryMessage`）。
  - 早期對話中的具體指示可能在壓縮後被摘要取代，因此持久性規則應寫在 `CLAUDE.md` 中（每次請求皆會重新注入）。
  - **自訂壓縮行為的三種方式**：
    1. 在 `CLAUDE.md` 中加入摘要指示段落（標題名稱不限，compactor 會依語意識別需保留的項目）。
    2. 註冊 `PreCompact` hook（接收 `trigger` 欄位，值為 `"manual"` 或 `"auto"`），在壓縮前執行如完整對話紀錄封存等邏輯。
    3. 將 `"/compact"` 作為 prompt 字串傳送以手動觸發壓縮。

### 結果處理與錯誤行為（`ResultMessage`）
- **`ResultMessage.subtype` 的五種可能值**：
  - `"success"`：正常完成任務，**唯有此 subtype 具備 `result` 欄位**（存放最終文字輸出）。
  - `"error_max_turns"`：完成前達到 `maxTurns` 上限（無 `result` 欄位）。
  - `"error_max_budget_usd"`：完成前達到 `maxBudgetUsd` 上限（無 `result` 欄位）。
  - `"error_during_execution"`：執行期間發生錯誤中斷（如請求被取消或工作階段崩潰，無 `result` 欄位）。
  - `"error_max_structured_output_retries"`：在設定的重試上限內未產出通過驗證的結構化輸出，或模型 fallback 撤回了已完成的輸出且重試未成功（無 `result` 欄位）。
- **成本、用量與 `stop_reason` 欄位**：
  - 所有 result subtypes 皆帶有 `total_cost_usd`、`usage`、`num_turns` 與 `session_id`。在 Python 中，`total_cost_usd`、`usage` 與 `model_usage` 的型別皆為 optional（可能為 `None`）。
  - `usage` 僅涵蓋主代理迴圈（main agent loop）；若需包含所有 subagents 的完整樹狀 token 與花費統計，應讀取 `modelUsage`（TypeScript）或 `model_usage`（Python）。
  - 若工作階段崩潰（session crash），最終產出的 `error_during_execution` 結果其花費欄位可能歸零、`stop_reason` 為 `null`，且子處理程序隨後結束。
  - `stop_reason`（TypeScript 為 `string | null`，Python 為 `str | None`）表示最後一回合模型停止生成的原因，常見值包含 `"end_turn"`、`"max_tokens"` 與 `"refusal"`（模型拒絕請求）。
- **Single-shot `query()` 錯誤拋出行為**：當單次 `query()` 以錯誤結果結束時，SDK 會在 yield 出最後的 `ResultMessage` **之後拋出例外（raises/throws an error）**（例如包含 `Reached maximum number of turns`），且底層 Claude Code 處理程序以非零退出碼結束。呼叫端必須以 `try...except` / `try...catch` 包裹迴圈才能繼續執行後續程式。

## 相關頁面
- [[concepts/claude-agent-sdk-overview]]
- [[guides/agent-sdk-quickstart]]
- [[concepts/agent-sdk-permissions]]
- [[concepts/agent-sdk-hooks]]
- [[concepts/agent-sdk-subagents]]

## 出處
- docs/agent-sdk/agent-loop.md
