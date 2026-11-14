# Agent SDK Skills, Commands, and Plugins

別名：Agent SDK 技能、指令與外掛、Skills、Plugins、SKILL.md、slash_commands、reloadPlugins、.claude-plugin/plugin.json
框架：agent-sdk

## 摘要
Agent SDK 支援透過檔案系統探索並按需載入 `SKILL.md` 技能、在提示詞中以 `/<name>` 派發內建或自訂斜線指令（如 `/compact`、`/clear`），以及透過 `plugins` 選項從本地目錄載入整合了 skills、agents、hooks 與 MCP 伺服器的外掛套件（並自動套用 `plugin-name:skill-name` 命名空間）。

## 重點
### Skills 探索、設定與驗證 (`skills.md`)
- **檔案系統定義與探索路徑**：
  - Skills 必須建立為包含 YAML frontmatter（如 `name`、`description`、`when_to_use`、`user-invocable`、`allowed-tools`）與 Markdown 內容的 `.claude/skills/<name>/SKILL.md` 檔案，SDK **不提供程式化註冊 skill 的 API**。
  - 探索受 `settingSources` / `setting_sources` 控制：
    - `"user"`：載入個人技能 `~/.claude/skills/`（及舊版 `~/.claude/commands/`）。
    - `"project"`：載入 `<cwd>/.claude/skills/`、`<cwd>` 往上直到儲存庫根目錄的所有父目錄下的 `.claude/skills/`，以及透過 `additionalDirectories`（TypeScript）/ `add_dirs`（Python）傳入之各目錄下的 `<dir>/.claude/skills/`（及對應的 `.claude/commands/`）。
- **`skills` 選項控制與 `Skill` 工具**：
  - 省略 `skills` 選項時：預設啟用所有探索到的技能並開放 `Skill` 工具（與 CLI 行為一致）。
  - `skills: "all"`：允許 Claude 呼叫所有探索到的技能（不可使用萬用字元 `*`）。
  - `skills: ["pdf", "docx"]`：僅允許列出的精確技能名稱（模型看不到未列出的技能，`Skill` 工具也會拒絕呼叫並回傳 `Skill <name> is not in this session's skills allowlist`，但磁碟檔案仍可透過 `Read` 或 `Bash` 讀取，且不影響以 `/<name>` 直接派發指令）。
  - `skills: []`：禁止模型主動呼叫任何技能。
  - 設定 `skills` 時，SDK 會自動將 `"Skill"` 加入 `allowedTools`；但若同時明確傳入 `tools` 清單，**必須手動將 `"Skill"` 列入 `tools`**。
- **技能名稱格式與衝突解決規則**：
  - 自有技能使用目錄名稱；Plugin 技能使用 `plugin:skill`；當透過 `additionalDirectories` / `add_dirs` 加入的目錄中存在與企業、個人、專案或更早加入之目錄同名的技能時，會自動加上目錄前綴（例如依序加入 `../api` 與 `../web` 且皆含 `verify` 時，名稱分別為 `verify` 與 `web:verify`，需 Claude Code **v2.1.309**+）。
  - **無效技能名稱驗證（Invalid skill name error）**：若 `skills` 清單包含空字串（報錯 `Skill names must be non-empty strings`）、括號、逗號、控制字元、前後空白，或萬用字元（如 `*` 或 `docs:*`，報錯 `wildcard-suffix names are not allowed; list each skill by its exact name`），`query()` 會在啟動處理程序前直接拒絕並拋出 `Error`（TypeScript，需 **v0.3.221**+）或 `ValueError`（Python，需 **v0.2.129**+）。
- **確認已載入技能與權限預審**：
  - 檢查 `system` `init` 訊息中的 `skills` 陣列（包含定義了 `description` 或 `when_to_use` 的自訂技能與內建 bundled skills，如 `code-review` 與 `verify`；若 `.claude/commands/` 檔案與 bundled skill 同名，會遮蔽 bundled skill）。設定了 `user-invocable: false` 的技能仍可供 Claude 呼叫，但不會出現在 `init` 的 `skills` 與 `slash_commands` 陣列中。
  - 可透過技能 frontmatter 的 `allowed-tools` 或查詢的 `allowedTools` / `allowed_tools` 預先核准技能所需的工具；但若組織在 managed settings 中設定了 `allowManagedPermissionRulesOnly`，Claude Code 會同時忽略這兩者。

### 工作階段中的斜線指令（Commands）
- **四種指令來源**：Built-in commands（如 `/compact`、`/clear`）、Bundled skills（如 `/code-review`）、自訂 `SKILL.md` 技能、以及舊版 `.claude/commands/*.md` 平面檔案。可從 `system/init` 訊息的 `slash_commands` 欄位查詢可用指令（需要互動式終端機的指令如 `/theme`、`/terminal-setup` 不會列出）。
- **以名稱派發指令（`/<name>`）的行為**：
  - 直接將 `/<name>` 作為 prompt 字串傳送即可執行，不受 `skills` 白名單限制。
  - 若 `/<name>` 不匹配任何工作階段指令或內建指令：查詢不會失敗，Claude Code 會將其作為一般訊息送交模型並附註該指令未執行（消耗一個 model turn；在 Claude Code **v2.1.274** 之前則是不消耗 model turn 直接回傳 `Unknown command: /<name>`）。
  - 若 `/<name>` 匹配在目前環境不可用的內建指令（如 `/theme`）：不消耗 model turn，直接回傳 `/theme isn't available in this environment.`。
- **`/compact` 與 `/clear` 實務用法**：
  - `/compact`：壓縮既有對話歷史（需在已有先前對話的工作階段中使用，例如搭配 `continue: true` / `continue_conversation=True` 或 streaming input）。成功執行壓縮時會發出 `subtype: "compact_boundary"` 的 `SystemMessage`，內含 `compact_metadata.pre_tokens` 與 `compact_metadata.trigger`（值為 `"manual"`）。若對話訊息不足以壓縮，仍會以 `success` 結束（結果文字如 `Not enough messages to compact.`）且不會發出 `compact_boundary` 訊息。
  - `/clear`：在 streaming input 模式下將對話重設為空白上下文（舊對話仍保留於磁碟，可透過 `resume` 帶入 session ID 找回），同時重設累計預算。

### Plugins 外掛載入與管理 (`plugins.md`)
- **載入本地外掛（`plugins` 選項）**：
  - 傳入 `{ type: "local", path: "..." }` 物件陣列（`type` 唯一合法值為 `"local"`；若外掛來自 marketplace 或遠端儲存庫，須先下載至本地；CLI 安裝的外掛位於 `~/.claude/plugins/`）。
  - `path` 可為相對於 `cwd` 的相對路徑或絕對路徑，且必須指向外掛根目錄（即 `skills/`、`agents/`、`hooks/`、`commands/` 或 `.claude-plugin/` 的父目錄）。
  - **注意**：SDK **不會展開波浪號路徑（如 `~/plugins`）**；若指定的路徑不存在，SDK 會直接略過該外掛並繼續執行工作階段，不會拋出例外。
- **在執行中的工作階段重新載入或動態新增外掛**：
  - **重新載入既有外掛**：在 TypeScript 中呼叫 `Query` 物件上的 `reloadPlugins()`；在 Python 中則無對應方法，需將 `"/reload-plugins"` 作為 prompt 字串傳送。
  - **動態新增外掛目錄（僅限 TypeScript，需 TS SDK v0.3.301+）**：呼叫 `await q.reloadPlugins({ addPlugins: [{ type: "local", path: "/absolute/path/..." }] })`，其中 `path` 必須為絕對路徑，回傳結果的 `result.plugins` 會列出目前載入的所有外掛。
- **驗證與命名空間（Namespacing）**：
  - 在 `system` `init` 訊息中檢查 `plugins`（格式為 `[{ name, path }]`）、`skills` 與 `slash_commands`；若載入失敗，可檢查 `init` 訊息上的 `plugin_errors` 欄位。
  - 外掛提供的技能與指令會自動冠上外掛名稱前綴以避免衝突，格式為 **`plugin-name:skill-name`**（例如在 `init` 中顯示為 `"my-plugin:greet"`，直接呼叫時發送 `"/my-plugin:greet"`）。
- **Plugin 目錄結構（`.claude-plugin/plugin.json`）**：
  - `.claude-plugin/plugin.json` manifest 檔案為選用（省略時 Claude Code 會自動依目錄結構探索元件）。
  - 支援的子目錄與檔案：`skills/<skill-name>/SKILL.md`（推薦）、`commands/*.md`（舊版平面檔案）、`agents/*.md`、`hooks/hooks.json` 以及 `.mcp.json`。

## 相關頁面
- [[concepts/claude-agent-sdk-overview]]
- [[concepts/agent-sdk-agent-loop]]
- [[concepts/agent-sdk-subagents]]
- [[concepts/agent-sdk-hooks]]
- [[concepts/agent-sdk-mcp]]

## 出處
- docs/agent-sdk/skills.md
- docs/agent-sdk/plugins.md
