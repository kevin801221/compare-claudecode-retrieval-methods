# Agent SDK Hooks

別名：Agent SDK Hooks 攔截與控制、生命週期回呼、HookMatcher、HookCallback、PreToolUse、PostToolUse、hookSpecificOutput
框架：agent-sdk

## 摘要
Agent SDK 的 Hooks 機制讓開發者在代理執行的關鍵生命週期節點（如工具呼叫前後、提示詞送出、Subagent 啟動與結束、上下文壓縮前、工作階段啟停等）註冊回呼函式或載入設定檔 shell 指令，以阻擋危險操作、修改工具輸入或輸出、注入額外上下文、記錄稽核軌跡或發送外部通知。

## 重點
### 運作流程與設定結構 (`hooks.md`)
- **五步驟運作流程**：
  1. **事件觸發（An event fires）**：SDK 在特定執行點觸發事件（如 `PreToolUse`、`PostToolUse`、`Stop` 等）。
  2. **收集已註冊 Hooks**：收集 `options.hooks` 中的程式化回呼，以及當對應 `settingSources` / `setting_sources` 啟用時來自設定檔（如 `.claude/settings.json`）的 shell command hooks。
  3. **Matcher 篩選**：若設定了 `matcher` 規則（如 `"Write|Edit"` 或 `"^mcp__"`），SDK 會比對事件目標（工具類 hook 比對工具名稱，`Notification` 比對通知類型，`Stop` 則完全忽略 matcher）；未設定 `matcher` 時對該事件的所有發生皆會執行。注意：matcher 僅比對工具名稱而非檔案路徑等參數（例如 `Write|Edit` 不會攔截透過 `Bash` 寫入 `.env` 的指令）。
  4. **平行執行回呼函式**：同一事件匹配到的多個 hooks 會**平行（in parallel）**執行，完成順序不固定，各 hook 應獨立運作。
  5. **回傳決策與優先順序**：當多個 `PreToolUse` hooks 回傳不同決策時，優先順序（由最嚴格到最寬鬆）為：**`deny` > `defer` > `ask` > `allow`**。

### 可用 Hook 事件與跨語言支援對照表
| Hook Event | Python SDK | TypeScript SDK | 觸發時機與重要行為 |
| :- | :-: | :-: | :- |
| `PreToolUse` | Yes | Yes | 工具呼叫請求前（可阻擋、修改輸入或延遲） |
| `PostToolUse` | Yes | Yes | 工具執行成功回傳結果後 |
| `PostToolUseFailure` | Yes | Yes | 工具執行失敗時 |
| `PostToolBatch` | No | Yes | 整批工具呼叫全數完成後、下一次模型呼叫前觸發一次 |
| `UserPromptSubmit` | Yes | Yes | 提示詞送出時（包含 Claude Code 自行發起的回合） |
| `UserPromptExpansion` | No | Yes | 使用者輸入的指令或 MCP prompt 展開為提示詞送達 Claude 前（Claude 自行呼叫 skill 時不觸發） |
| `MessageDisplay` | No | Yes | 包含文字的 assistant 訊息完成時（每則訊息一次，可遮罩或重排顯示文字而不變更對話紀錄） |
| `Stop` | Yes | Yes | 代理執行停止時 |
| `StopFailure` | No | Yes | 回合因 API 錯誤而非正常停止結束時 |
| `SubagentStart` | Yes | Yes | Subagent 初始化時 |
| `SubagentStop` | Yes | Yes | Subagent 完成時 |
| `PreCompact` | Yes | Yes | 對話壓縮（compaction）請求前 |
| `PostCompact` | No | Yes | 對話壓縮完成後 |
| `PreModelSwitch` | No | Yes | 請求切換模型、實際切換發生前（可阻擋） |
| `PostModelSwitch` | No | Yes | 工作階段模型變更後（包含自動 fallback） |
| `PermissionRequest` | Yes | Yes | 工具呼叫需要權限決策時 |
| `PermissionDenied` | No | Yes | Auto mode 拒絕工具呼叫時（含無分類器裁決的拒絕；針對無裁決拒絕 Claude Code 會忽略 `retry: true`） |
| `SessionStart` | No | Yes | 工作階段初始化時（Python 僅支援透過 `settings.json` 定義 shell command hook） |
| `SessionEnd` | No | Yes | 工作階段終止時（Python 僅支援透過 `settings.json` 定義 shell command hook） |
| `Notification` | Yes | Yes | 代理狀態訊息（SDK 工作階段中會在 `canUseTool` 等待約 6 秒時觸發 `permission_prompt`〔需 TS SDK **v0.3.233**+ / Python SDK **v0.2.139**+〕、`elicitation_complete`、`elicitation_response` 與 mod 呼叫 `$.ui.notify` 的 `plugin_notification`；不觸發 `idle_prompt`、`auth_success`、`elicitation_dialog`） |
| `Setup` | No | Yes | 工作階段設定／維護時 |
| `TeammateIdle` | No | Yes | Teammate 進入閒置狀態時 |
| `TaskCreated` | No | Yes | 透過 `TaskCreate` 工具建立任務時 |
| `TaskCompleted` | No | Yes | 任務標記為完成時 |
| `Elicitation` | No | Yes | MCP 伺服器在任務中途請求使用者輸入時 |
| `ElicitationResult` | No | Yes | 使用者回應 MCP elicitation 後、回傳給伺服器前 |
| `ConfigChange` | No | Yes | 設定檔變更時 |
| `InstructionsLoaded` | No | Yes | `CLAUDE.md` 或 rules 檔案載入上下文時 |
| `WorktreeCreate` | No | Yes | 建立 Git worktree 時 |
| `WorktreeRemove` | No | Yes | 移除由 `WorktreeCreate` hook 建立的 worktree 時 |
| `CwdChanged` | No | Yes | 工作階段期間工作目錄變更時 |
| `FileChanged` | No | Yes | 受監看的檔案被修改、建立或刪除時 |
| `DirectoryAdded` | No | Yes | 工作階段期間新增工作目錄時 |

### Matcher 設定選項（`HookMatcher`）
- `matcher`（`string`，預設 `undefined`）：支援完整字串、以 `|` 分隔的多重名稱（如 `"Write|Edit|NotebookEdit"`）或正規表示式（如 `"^mcp__"`）。MCP 工具名稱格式為 `mcp__<server>__<action>`。在 Claude Code **v2.1.314**+ 中，設定 `'Bash'` matcher 的 `PreToolUse` 與 `PermissionRequest` hooks 也會針對 Monitor 指令執行（可拒絕但不可核准）。
- `hooks`（`HookCallback[]`，必填）：匹配成功時執行的回呼函式陣列。
- `timeout`（`number`，選用）：逾時秒數。
- `onFailure`（TypeScript）/ `on_failure`（Python）：型別為 `"continue" | "block"`（需 TS SDK **v0.3.317**+ 或 Python SDK **v0.2.177**+）。

### 回呼函式輸入與輸出規格
- **三個輸入參數 `(input_data, tool_use_id, context)`**：
  1. `input_data` / `input`：所有事件皆包含 `session_id`、`cwd` 與 `hook_event_name`。在 subagent 內觸發時會填入 `agent_id` 與 `agent_type`（TypeScript 中位於基底 `HookInput` 上供所有事件讀取；Python 中在 `PreToolUse`、`PostToolUse`、`PostToolUseFailure`、`PermissionRequest` 為選用欄位，在 `SubagentStart` 與 `SubagentStop` 為必填欄位；`SubagentStop` 另包含 `agent_transcript_path` 與 `stop_hook_active`）。
  2. `tool_use_id` / `toolUseID`（`str | None` / `string | undefined`）：關聯同一次工具呼叫的 `PreToolUse` 與 `PostToolUse` 事件。
  3. `context`：在 TypeScript 中包含 `{ signal: AbortSignal }` 供逾時取消；在 Python 中保留供未來使用。
- **回傳輸出欄位（回傳 `{}` 代表不變更並放行）**：
  - **頂層欄位（Top-level fields）**：
    - `systemMessage`：顯示給使用者的訊息（不送給模型）。在 Claude Code **v2.1.227**+ 中，會依事件決定是否作為 `SDKInformationalMessage` 出現在訊息串流中（在 **v2.1.227** 之前僅 `SessionStart` 與 `Setup` 會出現在串流中，其餘事件需開啟 `includeHookEvents` / `include_hook_events` 才會出現在生命週期事件中）。
    - `continue`（TypeScript）/ `continue_`（Python）：布林值，決定代理在此 hook 之後是否繼續執行。
  - **`hookSpecificOutput` 欄位**：
    - `hookEventName`：必須註明事件名稱（如 `"PreToolUse"`）。
    - **`PreToolUse` 專用**：
      - `permissionDecision`：`"allow"`、`"deny"`、`"ask"` 或 `"defer"`。若回傳 `"defer"`，該回合會以 `stop_reason` 為 `"tool_deferred"` 的結果訊息結束，以便稍後接續執行。
      - `permissionDecisionReason`：向模型說明允許或拒絕的原因。
      - `updatedInput`：替換後的工具輸入參數物件（必須位於 `hookSpecificOutput` 內且不可就地修改原物件）。可搭配 `'allow'` 自動核准、搭配 `'ask'` 交由使用者確認，或省略 `permissionDecision` 讓修改後的輸入進入一般權限流程；**若搭配 `'defer'` 則 `updatedInput` 會被忽略**。
    - **`PostToolUse` 專用**：
      - `additionalContext`：將額外上下文附加至工具結果送給模型。
      - `updatedToolOutput`：在 Claude 看到結果前直接替換內建工具或 MCP 工具的輸出（舊欄位 `updatedMCPToolOutput` 僅能替換 MCP 工具輸出）。
      - `classifierContext`（僅限 TypeScript，需 TS SDK **v0.3.236**+）：提供給 auto mode 權限分類器的簡短結果註記（僅限同步回傳）。
- **非同步輸出（Asynchronous output）**：
  - 當 hook 僅執行日誌記錄或發送 webhook 等副作用而不需影響代理行為時，可回傳 `{"async_": True, "asyncTimeout": 30000}`（Python）或 `{ async: true, asyncTimeout: 30000 }`（TypeScript），讓代理立即繼續執行而不等待背景任務完成。

### 錯誤處理（`onFailure`）與逾時行為（Timeouts）
- **回呼失敗與 `onFailure: "block"` / `on_failure="block"`**：
  - 預設情況下，若回呼拋出例外、回傳驗證失敗的格式或未回傳任何值（例如漏寫 `return`），動作仍會繼續進行，且應用程式會收到 `tag` 為 `hook_callback_failed` 的 `SDKInformationalMessage`（Python 從 `SystemMessage.data` 讀取 `tag`）。
  - 在 matcher 設定 `onFailure: "block"` / `on_failure="block"`（需 TS SDK **v0.3.317**+ / Python SDK **v0.2.177**+）時，失敗或無回傳值會阻擋該動作，工具結果會包含 `failed; blocking because onFailure is "block"` 且隱藏原始錯誤文字。
  - **例外事件**：`Stop`、`SubagentStop`、`TaskCompleted` 與 `TeammateIdle` 會忽略 `"block"`；`PermissionRequest` 僅在比 `canUseTool` 更早回傳時才會阻擋；`PostToolUse` 因工具已執行完畢，會將失敗作為回饋送給 Claude；`PreCompact`、`Elicitation` 與 `WorktreeCreate` 在設定 `"block"` 時連逾時也會一併阻擋。
  - 若底層 Claude Code 不支援此選項（錯誤含 `does not honor`）或工作階段已在執行中而未註冊 hooks（錯誤含 `did not register your hooks`），查詢會在啟動時直接失敗。
- **預設逾時秒數與各事件逾時後行為**：
  - **預設逾時**：多數事件為 **600 秒**；`UserPromptSubmit`、`PreModelSwitch` 與 `PostModelSwitch` 為 **30 秒**；`MessageDisplay` 為 **10 秒**；`SessionEnd` 在關閉期間預設為 **1.5 秒**。
  - **各事件逾時處置**：
    - `PreToolUse`：阻擋該工具呼叫並告知 Claude hook 逾時（在 **v2.1.210** 之前會誤報為使用者拒絕而導致無人值守的工作階段停滯）。若在 `PreToolUse` pending 期間中斷 query，Claude Code 會取消該工具呼叫（需 **v2.1.208**+）。
    - `PostToolUse` / `PostToolUseFailure`：保留工具結果並繼續回合。
    - `UserPromptSubmit` / `UserPromptExpansion`：阻擋該提示詞並附上 hook 名稱與逾時訊息，工作階段繼續（在 **v2.1.208** 之前會以 `error_during_execution` 結束查詢）。
    - `Stop` / `SubagentStop`：視為未回傳決策（等同允許停止），同事件其他 hooks 的決策仍有效（需 Claude Code **v2.1.273**+；在此之前會丟棄同事件所有其他 hooks 的決策）。
    - `SessionStart`：視為無輸出，保留其他 `SessionStart` hooks 的輸出繼續執行。（主工作階段中 `Stop` 或 `SessionStart` 首次逾時時，會額外發出一筆 `SDKInformationalMessage`）。
    - `PreModelSwitch`：阻擋模型切換。

## 相關頁面
- [[concepts/claude-agent-sdk-overview]]
- [[concepts/agent-sdk-agent-loop]]
- [[concepts/agent-sdk-permissions]]
- [[guides/agent-sdk-user-input]]
- [[concepts/agent-sdk-subagents]]

## 出處
- docs/agent-sdk/hooks.md
