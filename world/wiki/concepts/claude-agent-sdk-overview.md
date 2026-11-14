# Claude Agent SDK Overview & Configuration

別名：Claude Agent SDK 概覽與設定、Agent SDK 架構與功能載入、Options、ClaudeAgentOptions、settingSources、setting_sources
框架：agent-sdk

## 摘要
Claude Agent SDK 將驅動 Claude Code 的工具、agent loop 與上下文管理封裝為 Python 與 TypeScript 函式庫，供開發者在自有處理程序中建構與執行 AI 代理。代理工作階段可透過 `Options`（TypeScript）或 `ClaudeAgentOptions`（Python）設定模型、環境變數、工作目錄、回合與預算上限，並透過 `settingSources` / `setting_sources` 控制是否載入檔案系統上的 `CLAUDE.md`、skills、hooks 與權限設定。

## 重點
### 工具與平台比較 (`overview.md`)
- **Agent SDK**：在自有 Python 或 TypeScript 應用程式的處理程序中嵌入 Claude Code 代理，內建 Claude Code 二進位執行檔與功能（built-in tools、permissions、sessions、hooks、subagents、MCP、skills、commands、memory、plugins）。
- **Claude Code CLI**：終端機互動式介面，適合日常互動開發或單次任務；若需從 Python 或 TypeScript 以外的語言驅動相同的 agent loop，可將 CLI 作為子處理程序執行並傳入 `-p` 旗標與 `--output-format json`。
- **Client SDK**：直接從各語言呼叫 Claude API，需自行撰寫 tool loop 或使用 Client SDK 的 beta `tool runner`。
- **Managed Agents**：由 Anthropic 託管的 agent harness，在 Anthropic 管理的雲端沙盒或自架沙盒（self-hosted sandbox）中執行工作階段，可透過各語言 SDK、`ant` CLI 或 REST API 呼叫。
- **第三方認證限制**：除非事先獲得核准，Anthropic 不允許第三方開發者在其產品（包含基於 Claude Agent SDK 建構的代理）中提供 `claude.ai` 登入或速率限制（rate limits），必須改用 API key 認證方式。
- **品牌規範（Branding guidelines）**：
  - 允許使用：`"Claude Agent"`（下拉選單首選）、`"Claude"`（位於已標示為 `"Agents"` 的選單內時）、`"{YourAgentName} Powered by Claude"`。
  - 禁止使用：`"Claude Code"`、`"Claude Code Agent"`，或模仿 Claude Code 的 ASCII 藝術與視覺元素。
- **授權條款**：受 Anthropic's Commercial Terms of Service 規範（特定元件或相依套件若有獨立 LICENSE 檔案則依其規定）。

### 工作階段設定 (`configuration.md`)
- **Options 物件**：每次呼叫 `query()` 皆可傳入選用的設定物件（TypeScript 為 `Options`，Python 為 `ClaudeAgentOptions`），不傳入時使用 SDK 預設值。
- **模型選擇（Model & Fallback）**：
  - `model`：指定模型別名（model alias）或完整模型名稱；未設定時依序由設定檔、環境變數或 Claude Code 預設模型決定。
  - `fallbackModel`（TypeScript）/ `fallback_model`（Python）：指定主要模型過載或無法使用時的備援模型（支援單一模型或逗號分隔的模型清單）。每次使用者回合（user turn）開始時會重試主要模型，恢復正常後即切回。在 TypeScript 中，若 `fallbackModel` 與 `model` 相同會在啟動時拋出錯誤。
  - Messages API 的請求參數 `temperature`、`top_p` 與 `max_tokens` 在兩種語言的 options 物件中皆無對應欄位；需改用 `effort` 或預算上限（`maxBudgetUsd` / `max_budget_usd`），或直接呼叫 Messages API。
- **環境變數（`env`）**：
  - TypeScript：`env` 會**取代（replaces）**子處理程序的環境變數；若要保留 `PATH`、`HOME`、`ANTHROPIC_API_KEY` 等繼承變數，需使用 `{ ...process.env, ... }` 展開。
  - Python：`env` 會**合併覆寫（merges over）**繼承的環境變數，自訂值優先於繼承值。
  - 未設定 `env` 時，兩種語言的子處理程序皆繼承目前處理程序的環境變數。可透過 `env` 傳入如 `ANTHROPIC_BASE_URL` 等變數來設定 Claude Code。
- **工作目錄（`cwd` 與額外目錄）**：
  - `cwd`：設定工作階段執行的目錄（預設為目前處理程序的工作目錄）。兩種 SDK 皆無 `cwd` 的動態 setter；若需更換目錄，必須以新的 `cwd` 啟動另一個工作階段。
  - `cwd` 決定專案設定與 hooks（`<cwd>/.claude/settings.json`，無父目錄 fallback）、session skills 探索位置，以及工作階段儲存（session storage）歸屬的專案。
  - 若要讓工具存取工作目錄以外的檔案，可使用 `additionalDirectories`（TypeScript）或 `add_dirs`（Python），SDK 會將其作為 `--add-dir` 傳遞給 Claude Code。
- **回合數與花費上限（`maxTurns` 與 `maxBudgetUsd` 對 `0` 的處理差異）**：
  - `maxTurns` / `max_turns`：傳入 `0` 代表無回合限制（等同於未設定）。
  - `maxBudgetUsd` / `max_budget_usd`：傳入 `0` 時 CLI 會在啟動時拒絕並視為無效金額，工作階段不會執行。
- **工作階段中動態變更設定（Mid-session configuration）**：
  - 僅在使用 streaming input 啟動工作階段時支援。在 TypeScript 中呼叫 `query()` 回傳物件上的方法；在 Python 中則呼叫 `ClaudeSDKClient` 上的方法（因為 Python 的 `query()` 僅回傳無控制方法的純 iterator）。
  - `setModel()` / `set_model()`：切換模型。不帶參數呼叫時會切換回 Claude Code 的預設模型（而非最初在 options 傳入的 `model`）。若工作階段處於 `auto` 模式且切換至不支援 `auto` 模式的模型，會自動退回 `default` 模式。注意：每個模型有獨立的 prompt cache，切換模型後的下一次請求會以新模型的費率重新計算完整對話（uncached）。
  - `setPermissionMode()` / `set_permission_mode()`：動態切換權限模式。
  - TypeScript 專屬方法：
    - `applyFlagSettings()`：於執行期套用設定檔鍵值（如 `await session.applyFlagSettings({ effortLevel: "high" })`），接受的是 settings file keys 而非 options 欄位。
    - `updateSettings()`：將單一白名單鍵值寫入設定檔。傳入 `"localSettings"`（如 `await session.updateSettings("localSettings", { outputStyle: "Explanatory" })`）會寫入專案 local 設定檔，於下一個請求生效並保留給後續載入 `local` 設定的工作階段；傳入 `"userSettings"` 僅接受寫入 `effortLevel` 鍵，作為目前模型的預設 effort level，不會改變正在執行中的工作階段之 effort。
- **功能設定欄位對照表（TypeScript / Python）**：
  - `permissionMode` / `permission_mode`：無須核准即可執行的權限模式。
  - `allowedTools` / `allowed_tools`：預先核准的工具清單（未列出的工具仍可呼叫，由 permission mode 決定是否放行）。
  - `canUseTool` / `can_use_tool`：工具呼叫核准回呼函式。
  - `systemPrompt` / `system_prompt`：代理的系統提示詞。
  - `settingSources` / `setting_sources`：控制載入哪些檔案系統設定來源。
  - `settings`：載入設定檔路徑或行內 JSON 字串（TypeScript 亦接受 settings 物件）；其優先順序高於 user、project 與 local 檔案系統設定，僅次於 managed policy settings。
  - `mcpServers` / `mcp_servers`：外部 MCP 工具伺服器。
  - `agents` / `agents`：Subagent 定義。
  - `hooks` / `hooks`：生命週期攔截回呼。
  - `skills` / `skills`：控制載入哪些 skills。
  - `plugins` / `plugins`：控制載入哪些 plugins。
  - `outputFormat` / `output_format`：結構化輸出 schema。
  - `resume` / `resume`：接續已儲存的工作階段。
  - `forkSession` / `fork_session`：分支（fork）工作階段。
  - `sessionStore` / `session_store`：外部工作階段持久化介面。
  - `enableFileCheckpointing` / `enable_file_checkpointing`：可倒帶（rewindable）的檔案編輯檢查點。
  - `effort` / `effort`：控制 Claude 回應投入的推理程度。
  - `sandbox` / `sandbox`：工具執行的沙盒行為設定。

### 檔案系統設定與 Claude Code 功能整合 (`claude-code-features.md`)
- **`settingSources` / `setting_sources` 預設行為**：省略此選項時，`query()` 載入與 Claude Code CLI 相同的檔案系統設定，等同於傳入 `["user", "project", "local"]`。傳入空陣列 `[]` 可停用 user、project 與 local 設定，僅保留以程式碼設定的選項。
- **三種 `SettingSource` 來源與載入路徑**：
  - `"project"`：
    - 從 `<cwd>/.claude/` 載入專案 `settings.json` 與 hooks（不會往父目錄尋找）。
    - 從 `<cwd>` 及所有父目錄載入 `CLAUDE.md` 與 `.claude/rules/*.md`；子目錄中的 `CLAUDE.md` 則在需要時動態載入（on demand）。
    - 從 `<cwd>` 及直到儲存庫根目錄（repository root）的所有父目錄，以及透過 `additionalDirectories` / `add_dirs`（即 `--add-dir`）傳入之各目錄下的 `.claude/skills/`、`.claude/commands/`、`.claude/agents/` 載入專案 skills、commands 與 subagents。
  - `"user"`：從 `~/.claude/` 載入使用者 `settings.json`、`CLAUDE.md` 與 `~/.claude/rules/*.md`；從 `~/.claude/skills/`、`~/.claude/commands/`、`~/.claude/agents/` 載入使用者 skills、commands 與 subagents。
  - `"local"`：從 `<cwd>/.claude/`（若 `<cwd>` 位於 git 儲存庫內，亦可能從儲存庫根目錄載入）載入 `settings.local.json`；從 `<cwd>` 及所有父目錄載入 `CLAUDE.local.md`。
- **不受 `settingSources` 控制的輸入項目（即使傳入 `settingSources: []` 仍會讀取）**：
  - **Managed policy settings**：端點管理政策（MDM plist、登錄檔政策或 managed settings 檔案）以及符合認證條件（組織 OAuth 登入、直接設定的 API key 或 `user_oauth` Anthropic profile）時從伺服器端拉取的 Server-managed settings。無法從 SDK 停用伺服器端政策。
  - **`~/.claude.json` 全域設定**：永遠會被讀取；可透過在 `env` 設定 `CLAUDE_CONFIG_DIR` 變更位置。
  - **Auto memory（`~/.claude/projects/<project>/memory/`）**：工作階段啟動時載入至系統提示詞，代理透過標準的 `Write` 與 `Edit` 工具寫入新記憶；可在 settings 中設為 `autoMemoryEnabled: false` 或在 `env` 中設定 `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` 停用。
  - **claude.ai MCP connectors**：當工作階段使用 `claude.ai` 登入認證時載入（若 `CLAUDE_CODE_OAUTH_TOKEN` 存放的是由 `claude setup-token` 產生的長效 token 則不會載入，因該 token 僅能發送模型請求）。傳入 `mcpServers: {}` 無法抑制此連線；需在 settings 設定 `strictMcpConfig: true`、`disableClaudeAiConnectors: true`，或在 `env` 設定 `ENABLE_CLAUDEAI_MCP_SERVERS=false`。
  - **`~/.claude/settings.json` 中的 `sandbox.credentials` `deny` 項目與 `credentials.files` `mask` 項目**：當 command sandbox 執行時，即使排除 user 設定仍會套用這些限制以縮小沙盒指令可存取的範圍；需直接從 `~/.claude/settings.json` 移除。
- **多租戶隔離（Multi-tenant isolation）警告**：預設 `query()` 選項不足以隔離多租戶。部署多租戶時，應讓每個租戶在獨立的檔案系統中執行，並設定 `settingSources: []` 以及在 `env` 加入 `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`。
- **`CLAUDE.md` 與規則合併原則**：所有層級（Project root、Project rules、Project parent/child dirs、Local、User、User rules）皆為累加（additive）載入，無硬性優先順序覆寫規則；若有衝突，應在較具體的檔案中明確聲明優先權。
- **Skills 載入機制**：Skills 必須以檔案系統實體（`.claude/skills/<name>/SKILL.md`）建立，SDK 無註冊 skills 的程式碼 API。省略 `skills` 選項時會啟用探索到的 user 與 project skills 並開放 `Skill` 工具；可將 `skills` 設為 `"all"`、技能名稱陣列或 `[]`。設定 `skills` 時 SDK 會自動將 `"Skill"` 加入 `allowedTools`；但若同時明確傳入 `tools` 清單，則必須手動將 `"Skill"` 包含進 `tools` 中。
- **Hooks 雙軌機制**：
  - **Filesystem hooks（`settings.json`）**：支援 `"command"`、`"http"`、`"mcp_tool"`、`"prompt"` 與 `"agent"` 類型，會在主代理及所有衍生 subagents 中觸發。
  - **Programmatic hooks（`query()` 中的回呼函式）**：在應用程式處理程序內執行，同樣會在 subagents 內觸發，回呼的第一個參數（`HookInput`）帶有 `agent_id` 與 `agent_type` 欄位可識別觸發來源。回傳 `{}` 代表允許執行；若要阻擋，需回傳包含 `hookSpecificOutput`（內含 `hookEventName: "PreToolUse"`、`permissionDecision: "deny"` 與 `permissionDecisionReason`）的物件。
- **Agent teams 差異**：Agent teams 屬於 CLI 功能（由一個工作階段擔任 team lead 協調多個獨立 teammates），無法直接透過 SDK options 設定。

## 相關頁面
- [[guides/agent-sdk-quickstart]]
- [[concepts/agent-sdk-agent-loop]]
- [[guides/agent-sdk-system-prompts]]
- [[concepts/agent-sdk-permissions]]
- [[concepts/agent-sdk-hooks]]
- [[concepts/agent-sdk-skills-and-plugins]]
- [[concepts/agent-sdk-subagents]]
- [[concepts/agent-sdk-mcp]]

## 出處
- docs/agent-sdk/overview.md
- docs/agent-sdk/configuration.md
- docs/agent-sdk/claude-code-features.md
