# Deep Agents Code Extensibility: MCP, Memory, Skills, Subagents, Plugins, Extensions & Goals

別名：Deep Agents Code 擴充機制、MCP 工具與信任模型、AGENTS.md 記憶與技能、自訂子代理、Plugins 外掛與市集、Python Extensions 擴充套件、Goals 與 Rubrics 目標評分
框架：deepagents

## 摘要
Deep Agents Code（`dcode`）提供六大模組化擴充與品質控管機制：透過 Model Context Protocol（`.mcp.json`）整合外部 stdio/SSE/HTTP 工具與 OAuth 驗證；透過自動記憶（`memories/*.md`）、`AGENTS.md` 與符合 Agent Skills 規範的 `SKILL.md` 管理長期偏好與領域工作流；透過 Markdown frontmatter 定義自訂同步子代理（subagents）或以程式碼直譯器執行 `task()` 動態子代理；透過相容 Claude/Codex 規範的外掛與市集（Plugins & Marketplaces）打包發佈功能；透過實驗性 `ExtensionAPI`（Python extensions）直接向代理伺服器註冊工具、LangChain 中介軟體與虛擬儲存路由；以及透過目標（`/goal`）與評分標準（`/rubric`）建立自動化品質驗收迴圈。

## 重點

### MCP 工具（Model Context Protocol Tools：`.mcp.json`）
- **自動探索路徑與優先順序（由低至高）**：
  1. `~/.deepagents/.mcp.json`（使用者層級，適用於所有專案，永遠受信任）
  2. `<project>/.deepagents/.mcp.json`（專案層級 `.deepagents` 子目錄）
  3. `<project>/.mcp.json`（專案根目錄，最高優先，相容於 Claude Code）
  - 專案根目錄為向上尋找最近包含 `.git` 的父目錄，若無則為當前工作目錄。
  - 多個設定檔會依 `mcpServers` 下的伺服器名稱合併；**同名伺服器由高優先順序定義整個取代低優先順序物件**（內部欄位不做深層合併）。
  - 啟動旗標：`--mcp-config PATH`（加入最高優先順序的明確設定檔）與 `--no-mcp`（完全停用 MCP），兩者互斥。
- **伺服器名稱與傳輸類型（Transport types）**：
  - 伺服器名稱必須符合正規表示式 **`[A-Za-z0-9_-]+`**（因名稱會作為 OAuth token 檔案的磁碟檔名，包含路徑分隔符或 shell 特殊字元會在載入時被拒絕）。
  - `type` 欄位亦可寫為 `transport`。
  - **`stdio`（預設）**：子程序透過 stdin/stdout 通訊。必填 `command`（`string`），選填 `args`（`string[]`）、`env`（`object`）、`cwd`（`string`）。已核准的專案伺服器與 `--mcp-config` 伺服器預設在工作階段當前工作目錄啟動；使用者層級與外掛伺服器則繼承後端程序目錄（皆可由 `cwd` 覆寫）。
  - **`sse`**：必填 `type: "sse"` 與 `url`（`string`），選填 `headers`（`object`）、`auth: "oauth"`。
  - **`http`**：必填 `type: "http"`（亦接受別名 `streamable_http` 與 `streamable-http`）與 `url`（`string`），選填 `headers`（`object`）、`auth: "oauth"`。
  - 官方 LangChain MCP 伺服器範例：`docs-langchain`（`https://docs.langchain.com/mcp`）、`reference-langchain`（`https://reference.langchain.com/mcp`）與 LangSmith Remote MCP（`https://api.smith.langchain.com/mcp`，搭配 `"auth": "oauth"`）。
- **環境變數內插與逾時控制**：
  - `command`、`args`、`env`、`url`、`headers` 中的字串支援父 shell 環境變數引用 `${VAR}` 與預設值語法 `${VAR:-default}`。
  - **工具呼叫逾時**：預設 `120` 秒，可於 `config.toml` 設定 `[mcp].tool_timeout`（範圍 `1`–`900` 秒）或環境變數 `DEEPAGENTS_CODE_MCP_TOOL_TIMEOUT`（逾時不保證遠端伺服器已取消操作，重試具副作用工具前應先確認狀態）。
- **工具過濾（Tool filtering）與 Auto 模式唯讀標註**：
  - `allowedTools`（`string[]`）：僅保留列出的工具，丟棄其餘工具。
  - `disabledTools`（`string[]`）：丟棄列出的工具，保留其餘工具。
  - 同一伺服器同時設定 `allowedTools` 與 `disabledTools`、或將任一欄位設為空陣列 `[]` 皆會在載入時被拒絕。比對規則支援字面名稱或 Python `fnmatch` glob 樣式（含 `*`、`?`、`[`），同時比對裸工具名與 `{server}_{tool}` 前綴名（未匹配任何工具僅記錄警告而不報錯）。
  - **Auto 核准模式下的唯讀標註豁免**：當 MCP 工具的 `ToolAnnotations` 同時滿足 (1) `readOnlyHint` 為字面布林值 `true`、(2) `destructiveHint` 未提供、`null` 或 `false`、(3) 所有提供的標準提示（`readOnlyHint`、`destructiveHint`、`idempotentHint`、`openWorldHint`）皆為布林值或 `null` 時，在 Auto 模式下可免除分類器審查直接執行；未通過者進入 Auto 分類器批次、Manual 核准 UI，或在無 UI 的 Headless 模式下被拒絕。
- **OAuth 登入流程与 Token 儲存**：
  - 在 `http` 或 `sse` 伺服器設定 `"auth": "oauth"`（與 `Authorization` 標頭互斥，且不可用於 `stdio`）。
  - 執行 `dcode mcp login` 列出尚無 token 的 OAuth 伺服器，或執行 `dcode mcp login <server> [--mcp-config PATH]`（互動模式亦可執行 `/mcp login <server>` 或在 `/mcp` 選擇伺服器按 `Enter` 重新驗證；`/mcp reconnect` 則載入延遲登入）。
  - 依伺服器主機採用三種流程：(1) 標準相容伺服器：執行 Dynamic Client Registration 與瀏覽器 Authorization Code + PKCE 並貼回重導向 URL；(2) Slack（`slack.com`、`*.slack.com`）：預先載入 Slack 公開 client 並提示選填 team ID（如 `T01234567`）；(3) GitHub（`api.githubcopilot.com`）：採用 RFC 8628 Device Authorization Grant 印出驗證 URL 與 user code 並輪詢完成。
  - **Token 儲存路徑**：`~/.deepagents/.state/mcp-tokens/<server>-<sha256-16(url)>.json`（`<sha256-16(url)>` 為伺服器 URL 之 SHA-256 前 16 個十六進位字元；目錄權限 `0700`、檔案權限 `0600`，以暫存檔加 `rename` 原子寫入）。
  - **伺服器三種啟動後狀態**：`ok`（已連線且工具可用）、`unauthenticated`（需執行 `dcode mcp login <server>`）、`error`（連線或探索失敗，單一伺服器失敗不會中止整體啟動）。
- **專案層級信任模型（Project-level trust，需 `deepagents-code>=0.1.40`）**：
  - 專案級 MCP 伺服器（無論 `stdio` 或遠端 `http`/`sse`，因遠端可能觸發 SSRF 或透過 `${VAR}` 外洩機密）預設皆採**預設拒絕（default-deny）**。
  - **互動模式**：啟動時顯示每個 `stdio` 指令與遠端 URL 並詢問：`Allow once`（僅本次工作階段啟用）、`Allow for this project — until changed`（啟用並將所選伺服器寫入 `~/.deepagents/config.toml` 的 `[mcp].enabled_project_server_approvals`，綁定 `{ project_root = "~/myproject", name = "...", fingerprint = "sha256:..." }`，一旦指令、URL 或標頭變更即需重新核准；舊版扁平的 `[mcp].enabled_project_servers` 已被忽略），或選擇工作階段拒絕／跨所有專案永久拒絕。
  - **非互動模式（`-n`）**：未獲已存核准或環境變數核准的專案伺服器會被靜默略過，除非傳入 `--trust-project-mcp`（同樣地，`dcode mcp login` 也會略過未受信任的專案設定檔）。
  - **進階拒絕與核准策略**：
    - 永久拒絕清單：`config.toml` 的 `[mcp].disabled_project_servers` 或環境變數 `DEEPAGENTS_CODE_DISABLED_PROJECT_MCP_SERVERS`（優先權高於已儲存核准與 `--trust-project-mcp`）。
    - 跨專案名稱預核准逃生閥：`DEEPAGENTS_CODE_DANGEROUSLY_ENABLE_PROJECT_MCP_SERVERS`（逗號分隔伺服器名稱，設定時會取代該程序的已存核准；舊版 `DEEPAGENTS_CODE_ENABLED_PROJECT_MCP_SERVERS` 在 `>=0.1.40` 已忽略）。

### 記憶（Memory）與技能（Skills）
- **自動記憶（Automatic memory）**：
  - 代理依循「記憶優先協定（memory-first protocol）」：(1) **Research**（任務開始前先搜尋記憶）、(2) **Response**（執行中不確定時查詢記憶）、(3) **Learning**（自動將新學到的慣例存供未來工作階段使用）。
  - 儲存位置：`~/.deepagents/<agent_name>/memories/` 下的主題式 Markdown 檔案（如 `api-conventions.md`、`database-schema.md`）。
  - 可透過 `[memory] auto_save = false` 或 `DEEPAGENTS_CODE_MEMORY_AUTO_SAVE=0` 停用自動寫入（仍會讀取既有記憶，且仍可執行 `/remember [context]` 手動觸發更新記憶與技能）。
- **`AGENTS.md` 持久上下文檔案**：
  - **全域**：`~/.deepagents/<agent_name>/AGENTS.md`（每次工作階段皆載入，適合個人風格、通用格式與跨專案工具習慣）。
  - **專案**：Git 專案根目錄下的 `.deepagents/AGENTS.md`（及根目錄 `AGENTS.md`，用於專案架構、編碼規範、測試與部署流程）。
  - 若在 `.deepagents/` 中新增額外結構化知識檔案，**必須在 `AGENTS.md` 中引用它們**，代理才會知道它們的存在並在需要時按需讀寫（額外檔案不會在啟動時直接載入）。
- **技能（Skills：遵循 Agent Skills 規範 `SKILL.md`）**：
  - 啟動時僅讀取各 `SKILL.md` frontmatter 的 `name` 與 `description`；當任務符合描述或使用者明確呼叫時才讀取完整 `SKILL.md`（執行 `/reload` 可重新探索）。
  - **建立與管理指令**：`dcode skills create <NAME> [--project]`、`dcode skills list [--project]`、`dcode skills info <NAME> [--project]`、`dcode skills delete <NAME> [--project] [-f] [--dry-run]`。
  - **安裝社群技能（Vercel Skills CLI）**：
    - 全域安裝（符號連結至預設 `agent` 的 `~/.deepagents/agent/skills/`）：`npx skills add vercel-labs/agent-skills --skill web-design-guidelines -a deepagents -g -y`（若使用自訂名稱代理，需改用專案安裝或手動符號連結至 `~/.deepagents/{your-agent}/skills/`）。
    - 列出已安裝技能：`npx skills ls -a deepagents -g`。
  - **技能探索目錄清單**：
    - `~/.deepagents/<agent_name>/skills/`
    - `~/.agents/skills/`
    - `.deepagents/skills/`
    - `.agents/skills/`
    - `~/.claude/skills/`（experimental）
    - `.claude/skills/`（experimental）
  - **呼叫技能**：互動模式中輸入 `/skill:<name> [args]`；啟動時傳入 `dcode --skill <name> [-m '...'] [-n '...'] [-q]`（搭配 `--quiet` 或 `--no-stream` 必須同時使用 `-n`；Headless 執行時若技能符號連結解析超出受信任根目錄且未列入 `[skills].extra_allowed_dirs`，該回合會被拒絕）。

### 自訂與動態子代理（Subagents）
- **自訂同步子代理（Custom synchronous subagents）**：
  - 目前終端使用者在 Deep Agents Code 中尚無法使用非同步子代理（Async subagents are not available to end-users in Deep Agents Code at this time）。
  - **定義路徑与優先順序**：專案級 `.deepagents/agents/{subagent-name}/AGENTS.md` 優先覆蓋使用者級 `~/.deepagents/{agent}/agents/{subagent-name}/AGENTS.md`。
  - **檔案格式**：YAML frontmatter 加上作為 `system_prompt` 的 Markdown 本體。Frontmatter 必填 `name` 與 `description`，選填 `model`（`provider:model-name` 格式，如 `anthropic:claude-haiku-5-5`；省略則繼承主代理模型）。注意：`tools`、`middleware`、`interrupt_on`、`skills` 目前無法透過 `AGENTS.md` frontmatter 設定，自訂子代理固定繼承主代理的工具集（若建立名為 `general-purpose` 的子代理即可覆寫內建通用子代理）。
- **延續父對話脈絡（Forked subagents）**：
  - 內建的 `general-purpose` 子代理預設會繼承父代理的對話歷史與系統提示詞。
  - 若要改以隔離模式（isolated mode）執行，請在 shell 或全域 `~/.deepagents/.env` 設定 `export DEEPAGENTS_CODE_FORKED_SUBAGENTS=false`（忽略專案 `.env`）。
- **動態子代理（Dynamic subagents）**：
  - `dcode` 預設啟用程式碼直譯器，因此當使用者要求執行「workflow」（例如 `"Run a workflow to review every file in src/ for SQL injection."`）時，代理會撰寫呼叫內建 `task()` 全域函式的編排腳本並在直譯器中執行，同時在 UI 的動態子代理面板（dynamic subagents panel，可按 `Ctrl+T` 展開／收合）中依分派階段即時顯示（亦支援透過 ACP 如 Zed 使用）。

### 外掛程式與市集（Plugins & Marketplaces）
- **管理方式**：
  - **互動式**：執行 `/plugins` 開啟外掛管理員。在 **Marketplaces** 分頁可新增市集來源：(1) GitHub `owner/repo[@branch-or-tag]`、(2) HTTPS Git URL `[#branch-or-tag]`、(3) 提供 marketplace JSON 的 HTTPS URL、(4) 本機目錄或 JSON 檔案。安裝、啟用、停用或移除外掛後，執行 `/reload` 即可啟用技能、MCP 伺服器與掛鉤；但包含 **Python extensions** 的外掛變更必須執行 `/restart`（或重開工作階段）以重建代理圖。
  - **命令列（外掛 ID 格式為 `plugin-name@marketplace-name`）**：
    - `dcode plugin marketplace add <source>`
    - `dcode plugin marketplace list [--json]`
    - `dcode plugin marketplace remove <marketplace-name>`（會一併移除其外掛與受管快取，但保留本機原始目錄或檔案）
    - `dcode plugin list [--json]`
    - `dcode plugin install <plugin-name>@<marketplace-name>`
    - `dcode plugin enable <plugin-name>@<marketplace-name>`
    - `dcode plugin disable <plugin-name>@<marketplace-name>`
    - `dcode plugin uninstall <plugin-name>@<marketplace-name>`
- **外掛自動更新**：
  - 預設在首次提示詞提交後於背景自動更新已啟用且在 `plugin.json` 中宣告 `{"extensions": {"com.langchain.deepagents.code": {"autoUpdate": true}}}` 的外掛（更新後需 `/reload` 生效）。
  - 全域停用外掛自動更新：`config.toml` 設定 `[plugins].auto_update = false` 或環境變數 `DEEPAGENTS_CODE_PLUGIN_AUTO_UPDATE=false`。
- **呼叫外掛技能（Namespaced skills）**：
  - 完整語法：`/skill:plugin-name@marketplace-name:skill-name [args]`（互動自動補全亦支援簡寫 `/plugin-name:skill-name`；巢狀技能目錄如 `skills/review/security/SKILL.md` 會展開為 `/skill:quality@acme-tools:review:security`）。
- **外掛與市集目錄結構規格**：
  - **外掛清單檔（Manifest）**：位於 `.claude-plugin/plugin.json` 或 `.codex-plugin/plugin.json`（若組件皆位於預設路徑 `skills/` 或根目錄單一 `SKILL.md`、根目錄 `.mcp.json`、`hooks/hooks.json`，則 manifest 為選填）。Manifest 必填 `name`，選填 `version`、`skills`、`mcpServers`、`hooks`（路徑必須以 `./` 開頭、留在外掛根目錄內且不含 `..`）以及實驗性 Python 擴充 `extensions["com.langchain.deepagents.code"].pythonExtensions`（宣告 `pythonExtensions` 時必填非空的 `version`）。
  - **市集目錄檔（Marketplace catalog）**：存放於市集根目錄的 `.claude-plugin/marketplace.json`、`.agents/plugins/marketplace.json` 或 `.agents/plugins/api_marketplace.json`。包含 `name`、選填 `metadata.pluginRoot` 與 `plugins` 陣列（每項必填 `name` 與 `source`，選填 `description`、`author`；`source` 可為 `./` 相對路徑，或外部 Git 物件 `{"source": "github", "repo": "...", "ref": "..."}`、`{"source": "url", ...}`、`{"source": "git-subdir", "url": "https://...", "path": "./...", "ref": "..."}`）。

### Python 擴充套件（Python Extensions：需 `DEEPAGENTS_CODE_EXPERIMENTAL=1`）
- **進入點與 `ExtensionAPI`**：
  - 擴充檔案必須定義非同步函式 `async def extension(d: ExtensionAPI) -> None:`（設定過程具交易性 transactional：若匯入或初始化失敗，會自動清除該擴充的部分註冊並記錄於 `/extensions` 與除錯日誌，不影響後續擴充載入）。
  - **`ExtensionAPI` 唯讀屬性**：`d.cwd`（工作目錄）、`d.mode`（`"interactive"` 或 `"headless"`）、`d.has_ui`（`bool`）、`d.path`（擴充進入點檔案路徑）。
  - **`ExtensionAPI` 註冊方法**：
    - `d.register_middleware(class_or_instance)`：註冊 LangChain `AgentMiddleware` 實例或具無參數建構子的類別（修改後需 `/reload`）。
    - `d.register_tool(function_or_tool)`：註冊一般可呼叫函式（自動由型別簽章與 docstring 推論 schema）或 `BaseTool`（工作階段啟動後註冊的工具會在下一次模型請求生效；注意擴充工具不會自動加入人工核准映射表，敏感操作須自行透過中介軟體控管）。
    - `d.register_backend_route(prefix, backend)`：將 `BackendProtocol`（如 `StoreBackend`）掛載於小寫且前後皆有斜線的絕對虛擬路徑（如 `"/memories/"` 或 `"/company/knowledge/"`；禁止與內部產物或對話歷史路徑重疊，且沙盒代理拒絕直接掛載 `FilesystemBackend` 以防洩露宿主檔案系統；虛擬路由僅供模型檔案工具存取，shell `execute` 無法存取；修改後需 `/reload`）。
    - `d.on_shutdown(callback)`：註冊同步或非同步的冪等清理回呼，於代理伺服器停止時釋放資源。
  - **同名衝突規則**：擴充工具與中介軟體可覆寫內建同名項目；但在多個擴充套件之間，**第一個註冊該名稱或路由前綴的擴充勝出（first registration wins）**。
- **6 大擴充來源載入順序（依序載入並忽略重複路徑）**：
  1. `~/.deepagents/extensions/` 下的 Python 檔案
  2. `config.toml` 的 `[extensions].extra_paths` 中的檔案與目錄
  3. 命令列 `-e` / `--extension PATH` 傳入的檔案與目錄（目錄掃描包含直接的 `*.py` 以及含 `__init__.py` 或 `extension.py` 的直接子目錄）
  4. 已啟用且具版本號的外掛程式（`pythonExtensions`，變更時需 `/restart`）
  5. Python entry-point 群組 `dcode.extensions`
  6. 已受信任的專案擴充目錄 `<project>/.deepagents/extensions/`（互動模式預設詢問 `ask`，Headless/CI 需加 `--trust-project-extensions` 或設定 `[extensions].trust` / `DEEPAGENTS_CODE_EXTENSIONS_TRUST` 為 `"always"` / `"never"`）

### 目標與評分標準（Goals & Rubrics）
- **Goals（目標驅動，由代理起草驗收標準）**：
  - 使用 `/goal <objective>` 讓代理先起草驗收標準（acceptance criteria），確認後跨回合持續有效並於輸入框上方顯示目標面板（狀態：`active`、`paused`、`blocked`、`completed`），直到任務完成並獲核准後自動清除。
  - **各核准模式下的標準審查行為**：`Manual` 永遠開啟行內審查；`Auto` 預設開啟審查，但可在 `~/.deepagents/config.toml` 設定 `goals.auto_accept_criteria = true` 自動套用；`YOLO` 不經審查直接套用。
  - **完整 `/goal` 子指令**：
    - `/goal <objective>`：由目標起草驗收標準。
    - `/goal amend <feedback>`：在不取消當前任務的情況下提議修正目標與標準並進入行內審查。
    - `/goal pause`：暫停目標（後續提示詞不受該目標驅動或評分）。
    - `/goal resume`：重新啟用已暫停的目標。
    - `/goal show`：檢視當前目標、狀態與標準。
    - `/goal clear`：移除當前目標。
    - `/goal model [provider:model|clear]`：設定或清除目標評分模型。
    - `/goal max-iterations <N|clear>`：設定或清除最大評分迭代次數。
- **Rubrics（已知驗收標準的品質閘門）**：
  - **互動模式子指令**：
    - `/rubric set <criteria>`：設定跨回合持續生效的黏著式（sticky）評分標準。
    - `/rubric next <criteria>`：設定僅對下一回合提交任務生效的單次品質閘門。
    - `/rubric file <path>`：從檔案載入評分標準。
    - `/rubric show`：檢視作用中的 rubric。
    - `/rubric clear`：清除作用中的 rubric。
    - `/rubric model <provider:model>`：設定 rubric 評分器模型。
  - **非互動模式旗標（需搭配 `-n` 或管線 stdin）**：
    - `--rubric TEXT|@PATH`（如 `--rubric "tests pass; no unrelated files changed"` 或 `--rubric @acceptance.md`）
    - `--rubric-model MODEL`
    - `--rubric-max-iterations N`

## 相關頁面
- [[entities/deepagents-code-cli-reference]]
- [[guides/deepagents-code-configuration-and-providers]]
- [[concepts/deepagents-code-approval-and-hooks]]

## 出處
- docs/deepagents/code/mcp-tools.md
- docs/deepagents/code/memory-and-skills.md
- docs/deepagents/code/subagents.md
- docs/deepagents/code/plugins.md
- docs/deepagents/code/extensions.md
- docs/deepagents/code/goals-and-rubrics.md
