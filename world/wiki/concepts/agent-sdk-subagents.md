# Agent SDK Subagents

別名：Agent SDK 子代理、Subagents、AgentDefinition、agents 選項、Agent 工具、parent_tool_use_id、子代理繼承與限制
框架：agent-sdk

## 摘要
Subagents 是由主代理透過 `Agent` 工具衍生的獨立代理實例，具備獨立上下文視窗、平行執行能力、專屬系統提示詞與受限工具集。開發者可透過 `query()` 的 `agents` 參數（使用 `AgentDefinition`）以程式碼定義子代理，並透過環境變數與預算選項限制子代理的衍生深度、並行數量與總花費。

## 重點
### 建立 Subagents 的三種方式 (`subagents.md`)
1. **程式化定義（Programmatic definition，推薦）**：在 `query()` options 的 `agents` 參數傳入映射字典（名稱對 `AgentDefinition`），並在主代理的 `allowedTools` / `allowed_tools` 中加入 `"Agent"`。程式化定義的代理優先權高於同名的檔案系統代理。
2. **檔案系統定義（Filesystem-based）**：在 `~/.claude/agents/` 或 `.claude/agents/` 目錄下建立 Markdown 檔案。Claude Code 會動態監看既存目錄的變更（但若是在工作階段啟動後才新建的 `agents` 目錄、使用了 `--disable-slash-commands` 旗標，或位於透過 `add_dirs` / `additionalDirectories` / `--add-dir` 加入的目錄下，則不會動態監看，需重啟工作階段）。
3. **內建通用代理（Built-in `general-purpose`）**：當 Claude 呼叫 `Agent` 工具而未指定 `subagent_type` 時，預設會衍生內建的 `general-purpose` 子代理。若在環境變數設定 `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1`，會移除此預設行為，未帶 `subagent_type` 的呼叫將以 `subagent_type is required` 失敗。

### `AgentDefinition` 欄位完整規格
在 Python SDK 中，`AgentDefinition` 的多字詞欄位名稱（如 `disallowedTools`、`mcpServers`、`initialPrompt`、`maxTurns`、`permissionMode`）**維持 camelCase 拼寫**以符合底層傳輸格式，而非使用 snake_case：
- **`description`**（`string`，**必填**）：自然語言描述，供 Claude 判斷何時自動委派任務給此子代理。
- **`prompt`**（`string`，**必填**）：定義子代理角色與行為的系統提示詞。
- **`tools`**（`string[]`，選用）：允許使用的工具名稱陣列；省略時繼承所有對 subagents 可用的工具。未列出的工具完全不會出現在子代理的工作階段中（請注意：`AskUserQuestion` 目前不支援在 subagents 中使用）。
- **`disallowedTools`**（`string[]`，選用）：從子代理工具集中移除的工具名稱陣列。支援 MCP 伺服器層級樣式：`mcp__server` 或 `mcp__server__*` 移除該伺服器所有工具，`mcp__*` 移除所有伺服器的 MCP 工具。
- **`model`**（`string`，選用）：模型覆寫，接受別名（`'fable'`、`'opus'`、`'sonnet'`、`'haiku'`、`'inherit'`）或完整 model ID。`'inherit'` 會沿用衍生此子代理之父代理的模型。
- **`skills`**（`string[]`，選用）：啟動時預先載入（preload）至子代理上下文的技能名稱清單，最多預載清單中**前 32 個不重複名稱**；未列出的技能仍可透過 `Skill` 工具按需呼叫。
- **`memory`**（`'user' | 'project' | 'local'`，選用）：子代理的記憶來源。
- **`mcpServers`**（`(string | object)[]`，選用）：依名稱或行內設定提供給此子代理的 MCP 伺服器。
- **`initialPrompt`**（`string`，選用）：當此代理作為主執行緒代理（main thread agent）執行時自動送出的第一回合使用者提示詞；作為 subagent 呼叫時會被忽略。
- **`maxTurns`**（`number`，選用）：子代理停止前的最大回合數。達到上限時，Claude Code 會在 `Agent` 工具結果中將其輸出標記為 partial（需 Claude Code **v2.1.246**+），之後可接續（resume）該子代理。
- **`autoCompactWindow`**（`number`，選用，**僅限 TypeScript**，需 TS SDK **v0.3.296**+，Python `AgentDefinition` 無此欄位）：將此代理作為 subagent 執行時的自動壓縮視窗調低至 `100000` 到 `1000000` tokens 之間。
- **`background`**（`boolean`，選用）：設為 `true` 時，呼叫時一律作為非阻塞的背景任務執行。（預設情況下，子代理在背景執行並回傳 `status: "async_launched"`，報告於後續回合送達；若 Claude 下一步動作需要該報告，則會阻塞等待並回傳 `status: "completed"`）。
- **`omitClaudeMd`**（`boolean`，選用，**僅限 TypeScript**，需 TS SDK **v0.3.271**+，Python `AgentDefinition` 無此欄位）：設為 `true` 時，將 user、project 與 local 的 `CLAUDE.md` 排除在子代理初始上下文之外（managed policy 檔案仍會載入；作為主執行緒代理執行時忽略）。
- **`effort`**（`'low' | 'medium' | 'high' | 'xhigh' | 'max' | number`，選用）：子代理的推理深度。
- **`permissionMode`**（`PermissionMode`，選用）：子代理的工具權限模式（受父工作階段權限繼承規則規範）。

### 上下文繼承規則、Fork 子代理與輸出掃描機制
- **非 Fork 子代理的上下文內容**：
  - **會接收**：自身的系統提示詞（`AgentDefinition.prompt`）與 `Agent` 工具傳入的 prompt 字串（父代理唯一傳遞的內容）、透過 `settingSources` 載入的專案 `CLAUDE.md`（除非設定了 `omitClaudeMd: true`）、繼承或篩選後的工具定義、主工作階段的 extended thinking 設定，以及（若子代理擁有 `SendMessage` 工具）第一回合自動附上的其他執行中具名代理清單。
  - **不會接收**：父代理的對話歷史或工具結果、父代理的系統提示詞、未列在 `AgentDefinition.skills` 中的預載技能內容。
- **Forked subagents（`subagent_type: "fork"`）**：
  - 從 Claude Code **v2.1.302** 起，Claude 無須額外設定即可呼叫 `subagent_type: "fork"` 的 `Agent` 工具，複製父代理目前的完整對話歷史（因此不會收到 `SendMessage` 的其他代理清單）。
  - 若要禁止 Claude 啟動 fork 子代理，可在 `disallowed_tools` / `disallowedTools` 中加入 `"Agent(fork)"`（其他子代理仍可正常執行）。
- **子代理最終輸出的安全性掃描（Subagent output scanning，v2.1.210+）**：
  - 在父代理讀取子代理的最終訊息前，Claude Code 會掃描具指令形態的樣式（絕不刪除或改寫文字，僅做原地中和或加註）：
    1. **Control-tag imitation（模仿控制標籤）**：如 `<system-reminder>`，會在開頭 `<` 後插入反斜線 `\` 原地中和，並在訊息開頭加上 `[harness: ...]` 標記行。
    2. **Permission-configuration mentions（提及權限設定）**：如 `.claude/settings.json`、`bypassPermissions`、`--dangerously-skip-permissions`，保留原文並在訊息開頭加上 `[harness: ...]` 標記行。
    3. **Turn markers（回合標記）**：以 `Human:` 或 `Assistant:` 開頭的行，會在冒號 `:` 前插入反斜線 `\`（不加 `[harness: ...]` 標記行）。

### 偵測呼叫與接續執行（Detect & Resume Subagents）
- **偵測子代理呼叫與內部訊息**：
  - 檢查 `AssistantMessage` 中的 `ToolUseBlock`，比對 `block.name` 是否為 `"Agent"` 或 `"Task"`（在 `tool_use` 區塊中現稱為 `"Agent"`，但在 `system:init` 的 `tools` 清單中以及 Claude Code **v2.1.63** 之前的 `tool_use` 區塊中稱為 `"Task"`，建議同時比對兩者），並讀取 `block.input.get("subagent_type")`。
  - 來自子代理內部執行上下文的訊息皆帶有非空的 `parent_tool_use_id` 欄位。在 TypeScript SDK（**v0.3.292**+）中，子代理產生的每則 assistant 與 user 訊息還帶有 `agent_id` 欄位（對應任務事件 `SDKTaskStartedMessage` 的 `task_id`，且在接續執行時保持不變）。
- **接續執行子代理（Resume subagents）**：
  - 當子代理完成時，`Agent` 工具結果的文字區塊會包含 `agentId: <id>`（注意：內建的 `Explore` 與 `Plan` 子代理為單次執行，不會回傳 `agentId`；需接續時應使用自訂子代理或 `general-purpose`）。
  - 接續三步驟：(1) 從第一次查詢擷取 `session_id`；(2) 從 `ToolResultBlock` 文字以正規表示式 `r"agentId:\s*([\w-]+)"` 擷取 `agentId`；(3) 在第二次 `query()` 傳入相同的 `agents` 定義與 `resume=session_id`，並在 prompt 中寫明 `Resume agent <agent_id> ...`。

### 限制衍生深度、並行數與花費（Depth, Concurrency & Spend Caps）
在整合 Claude Code **v2.1.219**+ 的 TypeScript SDK **v0.3.219**+ 與 Python SDK **v0.2.127**+ 中，支援以下三大上限（對比早期模型更傾向委派子代理的 **Claude Opus 5** 尤為重要；在使用 `claude_code` preset 且模型為 Opus 5 時，Claude Code 會在系統提示詞加上除非被要求否則不要呼叫 `Agent` 工具的指示，自訂 `systemPrompt` 則無此行）：
1. **衍生深度（`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`）**：透過 `env` 設定，預設為 `"3"`（主代理之下最多 3 層子代理）。設為 `"1"` 可禁止子代理再衍生自己的子代理（最底層子代理將無法衍生並自行完成任務）。
2. **並行數量（`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`）**：透過 `env` 設定，預設為 `"20"`（同時執行的子代理上限）。達到上限時拒絕衍生並回傳 `Concurrent subagent limit reached` 作為工具結果，直到執行中數量降回上限以下（啟用 `ultracode` 的工作階段永遠不會被拒絕）。
3. **總花費上限（`maxBudgetUsd` / `max_budget_usd`）**：預設無限制，將主代理與所有子代理的 API 請求花費一併計入。達到上限時會：(1) 拒絕衍生新子代理並回傳 `Budget limit reached`；(2) 停止仍在背景執行的子代理；(3) 以 `error_max_budget_usd` 結束查詢。
- **大規模動態工作流程（`Workflow` 工具）**：若需在單次執行中協調數十至數百個代理，可使用將編排邏輯移至對話上下文外之腳本執行的 `Workflow` 工具（僅限 TypeScript Agent SDK **v0.3.149**+，可將 `"Workflow"` 加入 `allowedTools` 自動核准）。

## 相關頁面
- [[concepts/claude-agent-sdk-overview]]
- [[concepts/agent-sdk-agent-loop]]
- [[concepts/agent-sdk-permissions]]
- [[concepts/agent-sdk-hooks]]
- [[concepts/agent-sdk-skills-and-plugins]]

## 出處
- docs/agent-sdk/subagents.md
