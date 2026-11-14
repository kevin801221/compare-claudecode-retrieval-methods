# Deep Agents Code Approval Modes, Hooks & Remote Sandboxes

別名：Deep Agents Code 核准模式與掛鉤、Manual/Auto/YOLO 核准模式、hooks.json 生命週期掛鉤、遠端沙盒、Remote Sandboxes、PreToolUse/PostToolUse
框架：deepagents

## 摘要
Deep Agents Code（`dcode`）提供三層安全與執行控制機制：其一為人機迴路核准模式（Approval modes，包含預設的 `Manual`、結合窄確定性規則與 LLM 分類器的 `Auto`，以及無須審查的 `YOLO`）；其二為生命週期命令掛鉤（Hooks，透過 `~/.deepagents/hooks.json`、`.deepagents/hooks.json` 或外掛程式攔截 `PreToolUse`、`PostToolUse`、`PermissionRequest`、`Stop` 等 11 種事件，並以退出碼 `0` 或 `2` 及 JSON stdout 控制允許、拒絕或注入上下文）；其三為遠端沙盒（Remote sandboxes，支援 `langsmith`、`agentcore`、`daytona`、`modal`、`runloop`、`vercel`、第三方 `e2b` 及 `config.toml` 自訂沙盒供應商，將代理工具呼叫導向遠端環境執行）。

## 重點

### 人機迴路核准模式（Approval Modes：`Manual` / `Auto` / `YOLO`）
- **受控動作（Gated actions）與免提示唯讀工具**：
  - 唯讀工具（`ls`、`read_file`、`glob`、`grep`）永遠不需提示即可執行。
  - 受控動作預設需經核准，包括：編輯或刪除檔案（`write_file`、`edit_file`、`delete`）、執行 shell 指令（`execute`）、發起網路請求（`web_search`、`fetch_url`）、委派工作給子代理（`task`）。
- **三種核准模式比較**：
  - **`Manual`（預設）**：在每個受控動作執行前皆向使用者請求確認（設定檔值 `"manual"`）。
  - **`Auto`**：自動核准例行動作，對不確定動作交由分類器模型審查，並在多次拒絕或失敗後回退給使用者人工確認（啟動旗標 `dcode -y` / `--auto-approve`，或設定檔 `[startup] mode = "auto"`；注意設定檔說明指出 `mode = "auto"` 需搭配 `DEEPAGENTS_CODE_EXPERIMENTAL=1`）。
  - **`YOLO`**：完全不經審查直接執行所有受控動作（啟動旗標 `dcode --yolo`，或設定檔 `[startup] mode = "yolo"`；首次啟用需接受單次本機風險確認並持久化紀錄）。
- **切換與跨工作階段記憶**：
  - 在互動模式中按 `Shift+Tab` 可循環切換 `YOLO → Manual → Auto → YOLO`；若設定 `[startup] yolo_switcher = false`，則會從 `Shift+Tab` 循環中移除 `YOLO`。
  - 當未指定旗標或啟動設定時，`dcode` 會自動恢復上次選擇的 `Manual` 或 `Auto` 模式；但 `YOLO` 永遠必須明確指定才會啟用。
- **適用範圍限制**：
  - `Auto` 與 `YOLO` 僅適用於互動模式；在非互動模式（`-n` 或管線 stdin）下，`-y`/`--auto-approve` 與 `--yolo` 會被忽略（非互動模式使用失敗關閉的 MCP 路由與 `--shell-allow-list`）。
  - `Auto` **僅限於互動式且未使用遠端沙盒（unsandboxed）的工作階段**；一旦使用遠端 `--sandbox`，系統會強制將 `Auto` 轉為 `Manual`。`YOLO` 則無論是否使用沙盒皆須經過風險確認。
- **`Auto` 模式的兩階段決策流程**：
  1. **第一階段（窄確定性允許，Narrow deterministic allow）**：例行動作（如寫入一般原始碼檔 `src/parser.py` 或唯讀 Git 指令 `git status`）不呼叫分類器直接執行；敏感目標（如 `.github/workflows/ci.yml`）或具變更性的指令（如 `git commit`）則進入第二階段。
  2. **第二階段（模型分類器審查）**：建立結構化決策批次（structured decision batch），由分類器模型對照使用者請求評估影響。若分類器判定 `Allow` 則執行；若判定 `Deny` 且未達總拒絕門檻則回傳清理過的錯誤結果供代理修正計畫；若分類器不可用或逾時（預設 `20` 秒，可由 `DEEPAGENTS_CODE_AUTO_CLASSIFIER_TIMEOUT` 或 `[models].auto_classifier_timeout` 設為 `1`–`300` 秒）則回傳精簡不可用結果（`classifier_unavailable`）；若達到總拒絕門檻或連續失敗，則開啟人工核准 UI（使用者可選擇 `Approve`、`Reject` 或 `Switch to Manual` 永久切回手動模式）。
  - **副作用前重新驗證**：決策計畫綁定於執行緒、模式、批次與確切的受控呼叫；若在分類器審查期間使用者切回 `Manual`，先前的 `Auto` 決策不會靜默執行，而是改開核准 UI。
  - **Auto 範圍限制**：父代理層級的 Auto 審查**不涵蓋**委派子代理（delegated subagents）內部執行的動作，也不涵蓋明確設定的廣域 `js_eval` 扇出（fan-out）；MCP 的唯讀工具標註（`readOnlyHint`）在 Auto 模式下會被信任。
- **Auto 分類器模型選擇與優先順序**：
  - **各主模型供應商的內建低延遲預設分類器模型**：
    - Anthropic：`anthropic:claude-sonnet-5-5`
    - Google AI：`google_genai:gemini-4-hydrogen`
    - Google Vertex AI：`google_vertexai:gemini-4-hydrogen`
    - OpenAI：`openai:gpt-5.6-luna`
    - OpenAI Codex：`openai_codex:gpt-5.6-luna`
    - 其他供應商：繼承主代理模型。
  - **分類器模型解析優先順序（由高至低）**：
    1. 互動工作階段指令 `/auto model <provider:model>`（立即對當前工作階段生效；執行 `/auto model` 開啟選擇器；執行 `/auto model clear` 會跳過供應商預設值，直接改為繼承主代理模型）。
    2. 啟動旗標 `--auto-classifier-model MODEL`（僅限互動式 TUI 工作階段；傳入空值同樣改為繼承主代理模型）。
    3. 環境變數 `DEEPAGENTS_CODE_AUTO_CLASSIFIER_MODEL`（禁止在專案 `.env` 中設定，僅能設於 shell 或 `~/.deepagents/.env`）。
    4. `~/.deepagents/config.toml` 中的 `[models].auto_classifier`。
    5. 上述供應商內建預設分類器模型（Provider default）。
    6. 繼承主代理模型（Inherit）。

### 生命週期掛鉤（Hooks：`hooks.json`）
- **設定檔位置與載入優先順序（由高至低）**：
  1. **專案掛鉤**：`{project_root}/.deepagents/hooks.json`（須先取得工作區信任 workspace trust）。
  2. **使用者掛鉤**：`~/.deepagents/hooks.json`。
  3. **已啟用外掛程式（Plugins）貢獻的掛鉤**：來自外掛的 `hooks/hooks.json`、manifest 的 `hooks` 路徑或行內物件。
  - 所有符合條件的處理器（handlers）會**並行執行（run concurrently）**，完成後再依上述優先順序合併結果（高優先權決定哪個裁決勝出，但低優先權處理器仍會執行且其副作用仍會發生）。
  - 掛鉤設定在啟動時建立快照（snapshot），工作階段期間編輯 `hooks.json` 或啟用／停用外掛需執行 `/reload`（伺服器端事件若由新外掛引入則於 `/reload` 或下次啟動生效）。
- **專案掛鉤信任機制（Trust project hooks）**：
  - 互動模式遇到未受信任的 `.deepagents/hooks.json` 時會彈出提示：同意後會將該專案根目錄的信任決定持久化儲存於 `~/.deepagents/.state/hooks_trust.json`；拒絕則該工作階段略過專案掛鉤；按 `Esc` 或 `Ctrl+D` 取消則中止啟動。
  - 非互動／Headless／CI 模式絕不彈出提示，必須傳入 `--trust-project-hooks` 才會在該次執行載入專案掛鉤。
- **外掛掛鉤路徑變數**：
  - `${CLAUDE_PLUGIN_ROOT}`、`${PLUGIN_ROOT}`：已安裝外掛目錄。
  - `${CLAUDE_PLUGIN_DATA}`、`${PLUGIN_DATA}`：外掛可寫入的資料目錄。
  - `${CLAUDE_PROJECT_DIR}`：專案根目錄。
  - 在 `command` 字串中應使用雙引號包裹變數以防空白字元問題，或優先改用免經過 shell 的 `argv` 陣列欄位（`dcode` 會在啟動前展開變數）。
- **Handler 欄位規格**：
  - `type`（`string`，必填）：僅支援 `"command"`（若設定不支援的型別或 `"async": true` 會產生設定錯誤）。
  - `command`（`string`，必填）：要執行的 shell 命令（支援管線、重導向、glob 與環境變數展開；當同時設定 `argv` 時，不會透過 shell 執行此字串）。
  - `argv`（`list[string]`，選填）：不經 shell 直接執行的執行檔與參數陣列。
  - `timeout`（`number`，選填）：單一處理器逾時秒數，預設為 **`600` 秒**，唯獨 `UserPromptSubmit` 預設為 **`30` 秒**（逾時視為非阻斷錯誤）。
  - `statusMessage`（`string`，選填）：處理器執行期間在 UI 顯示的暫時訊息（未設定時顯示 `Running <event> hook`）。
- **Handler 執行環境與機密剝離**：
  - 在 payload 的 `cwd` 目錄啟動，並繼承工作階段環境變數，但**自動剝離所有名稱包含 `KEY`、`TOKEN`、`SECRET`、`PASSWORD` 或 `APIKEY` 的環境變數**（若處理器需要憑證，必須自行從檔案或秘密管理員讀取）。
- **Matchers（比對器）語法**：
  - 省略、空字串或 `"*"`：比對該事件的所有值。
  - 單純名稱（如 `"Bash"`）：精確比對。
  - 以 `|` 或 `,` 分隔（如 `"Edit|Write"` 或 `"startup|resume"`）：精確比對任一選項。
  - 其他字串（如 `"mcp__.*"`）：視為不加錨點的正規表示式（unanchored regular expression；編譯錯誤會使該群組失效並在啟動前顯示設定診斷）。
  - **`UserPromptSubmit` 與 `Stop` 無比對欄位**：這兩個事件必須省略 `matcher` 或設為 `"*"`，設為其他任何值在載入時會被拒絕。

### 11 種 Hook 事件、Payload 與輸出控制規格
- **事件完整對照表**：
  - `SessionStart`｜擁有者：Client｜Exit code `2` 效果：Diagnostic｜比對欄位：`source`（`startup`、`resume`、`clear`、`compact`）｜專屬欄位：`source`, `model`（可用時）
  - `UserPromptSubmit`｜擁有者：Client｜Exit code `2` 效果：Block prompt（阻斷提示詞）｜比對欄位：none｜專屬欄位：`prompt`
  - `SessionEnd`｜擁有者：Client｜Exit code `2` 效果：Diagnostic｜比對欄位：`reason`（`clear`、`resume`、`prompt_input_exit`、`other`）｜專屬欄位：`reason`
  - `PermissionRequest`｜擁有者：Client｜Exit code `2` 效果：Deny（拒絕權限請求）｜比對欄位：`tool_name`｜專屬欄位：`tool_name`, `tool_input`, `permission_suggestions`（目前為空）
  - `Notification`｜擁有者：Client｜Exit code `2` 效果：Diagnostic｜比對欄位：`notification_type`（例如設為 `"cache_expiring"` 可在提示詞快取到期前最後 60 秒內收到單次提醒）｜專屬欄位：`message`, `notification_type`, `title`（可用時）
  - `PreToolUse`｜擁有者：Server｜Exit code `2` 效果：Deny（在權限提示與工具執行前阻斷工具）｜比對欄位：`tool_name`｜專屬欄位：`tool_name`, `tool_input`, `tool_use_id`
  - `PostToolUse`｜擁有者：Server｜Exit code `2` 效果：Feedback｜比對欄位：`tool_name`｜專屬欄位：`tool_name`, `tool_input`, `tool_response`, `tool_use_id`, `duration_ms`（可用時）
  - `PreCompact`｜擁有者：Server｜Exit code `2` 效果：Block compaction（阻斷上下文壓縮）｜比對欄位：`trigger`（`manual`、`auto`）｜專屬欄位：`trigger`, `custom_instructions`
  - `Stop`｜擁有者：Server｜Exit code `2` 效果：Continue turn（強制代理繼續回合）｜比對欄位：none｜專屬欄位：`stop_hook_active`, `last_assistant_message`, `background_tasks`, `session_crons`
  - `SubagentStart`｜擁有者：Server｜Exit code `2` 效果：Diagnostic｜比對欄位：`agent_type`｜專屬欄位：`agent_id`, `agent_type`
  - `SubagentStop`｜擁有者：Server｜Exit code `2` 效果：Add context｜比對欄位：`agent_type`｜專屬欄位：`stop_hook_active`, `agent_id`, `agent_type`, `agent_transcript_path`, `last_assistant_message`, `background_tasks`, `session_crons`
- **stdin JSON 共通欄位（Common payload envelope）**：
  - `session_id`、`transcript_path`（指向 `~/.deepagents/transcripts` 下的 JSONL 對話投影檔，執行前自動刷新）、`cwd`、`hook_event_name`、`prompt_id`、`permission_mode`（`default`、`plan`、`acceptEdits`、`auto`、`dontAsk`、`bypassPermissions`）、`effort`（如 `{"level": "medium"}`，層級包含 `none`/`low`/`medium`/`high`/`xhigh`/`max`）、`agent_id`、`agent_type`。
- **Hook 公開工具名稱映射（Public tool names）**：
  - `Bash`（輸入欄位：`command`、選填毫秒數 `timeout`）
  - `Write`（輸入欄位：`file_path`, `content`）
  - `Edit`（輸入欄位：`file_path`, `old_string`, `new_string`, `replace_all`）
  - `Read`（輸入欄位：`file_path`, `limit`, `offset`）
  - `Glob`（輸入欄位：`pattern`, `path`）
  - `Grep`（輸入欄位：`pattern`, `path`, `glob`, `output_mode`, `head_limit`）
  - `LS`（輸入欄位：`path`）
  - `mcp__<server>__<tool>`（工具專屬 JSON）
- **結束代碼（Exit codes）與輸出解析**：
  - **Exit code `0`**：成功。若 stdout 為純 JSON 則解析並套用；若為非 JSON 純文字，在 `SessionStart` 與 `UserPromptSubmit` 會成為模型的額外上下文（additional context），在其他事件則產生診斷訊息。
  - **Exit code `2`**：觸發該事件的阻斷或回饋路徑（忽略 stdout JSON，改以 **stderr** 作為主要回饋通道）。
  - **其他非零結束代碼**：非阻斷錯誤，記錄診斷後繼續執行。
  - stdout 與 stderr 各自最多保留 **`100,000` bytes**。
- **JSON 輸出結構與裁決優先順序**：
  - 通用頂層欄位：`continue`（`bool`，設為 `false` 標記停止，以設定順序第一個 `stopReason` 為準）、`stopReason`、`suppressOutput`（僅隱藏該處理器自身的 `systemMessage`）、`systemMessage`、`terminalSequence`、`hookSpecificOutput`。
  - **`PreToolUse` 裁決**：在 `hookSpecificOutput` 回傳 `"permissionDecision": "allow" | "ask" | "deny"` 與 `"permissionDecisionReason"`。多處理器合併優先順序為 **`deny > ask > allow`**（`deny` 在權限提示前直接短路阻斷並將原因回饋給模型；`ask` 強制彈出權限提示；`allow` 抑制一般提示但不覆寫其他處理器的 `deny` 或 `ask`）。
  - **`PermissionRequest` 裁決**：在 `hookSpecificOutput.decision` 回傳 `{"behavior": "allow" | "deny", "message": "..."}`（任何 `deny` 優先勝出；無 `deny` 且至少一個 `allow` 則允許；無裁決則顯示一般權限提示）。
  - **`Stop` 延續回合**：在頂層回傳 `{"decision": "block", "reason": "..."}`（或透過 `Stop.hookSpecificOutput.additionalContext`）強制代理帶著回饋繼續工作。腳本應檢查 payload 的 `stop_hook_active` 避免無限迴圈，且系統強制實施最多連續 **8 次**延續的硬性上限（hard cap of eight consecutive continuations）。
  - **上下文注入**：`SessionStart`、`UserPromptSubmit`（亦支援 `suppressOriginalPrompt`）、`SubagentStart`、`PostToolUse`、`SubagentStop` 皆可透過 `hookSpecificOutput.additionalContext` 為模型附加脈絡。
  - **已解析但不套用的相容性欄位（僅發送診斷並忽略變更）**：`SessionStart` 的 `initialUserMessage`/`sessionTitle`/`watchPaths`/`reloadSkills`、`UserPromptSubmit.sessionTitle`、`PreToolUse.updatedInput`、`PreToolUse.defer`（絕不視為 allow）、`PostToolUse` 的 `updatedToolOutput`/`updatedMCPToolOutput`、`PermissionRequest.updatedInput`、`PermissionRequest.updatedPermissions`、`SubagentStop` 的 block（已完成子代理無法恢復，僅注入上下文）。

### 遠端沙盒（Remote Sandboxes）
- **架構模式（Sandbox as tool）**：`dcode` 主程序（LLM 迴圈、記憶、工具分派）仍在本機執行，但所有代理工具呼叫（`read_file`、`write_file`、`execute` 等）皆導向遠端沙盒而非本機檔案系統。
- **內建與第三方沙盒供應商總覽**：
  - **LangSmith**（`--sandbox langsmith`）：預設內建免額外安裝｜憑證：`LANGSMITH_API_KEY`｜預設工作目錄：`/root`｜支援快照（`--sandbox-snapshot-name`）✅
  - **AgentCore**（`--sandbox agentcore`）：安裝 `/install agentcore` 或 `dcode --install agentcore`｜憑證：`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`、`AWS_REGION`（及選用 STS `AWS_SESSION_TOKEN`）｜預設工作目錄：`/tmp`
  - **Daytona**（`--sandbox daytona`）：安裝 `/install daytona` 或 `dcode --install daytona`｜憑證：`DAYTONA_API_KEY`｜預設工作目錄：`/home/daytona`｜支援快照 ✅
  - **Modal**（`--sandbox modal`）：安裝 `/install modal` 或 `dcode --install modal`｜憑證：執行 `modal setup`｜預設工作目錄：`/workspace`
  - **Runloop**（`--sandbox runloop`）：安裝 `/install runloop` 或 `dcode --install runloop`｜憑證：`RUNLOOP_API_KEY`｜預設工作目錄：`/home/user`｜支援快照 ✅
  - **Vercel**（`--sandbox vercel`）：安裝 `/install vercel` 或 `dcode --install vercel`｜憑證：`VERCEL_TOKEN`、`VERCEL_PROJECT_ID`、`VERCEL_TEAM_ID`（在 Vercel 上執行時自動使用 OIDC 憑證）｜預設工作目錄：`/vercel/sandbox`
  - **E2B（第三方套件）**（`--sandbox e2b`）：透過套件模式安裝 `/install langchain-e2b --package` 或 `dcode --install langchain-e2b --package`（不包含在 `all-sandboxes` extra 中）｜憑證：`E2B_API_KEY`｜預設工作目錄：`/home/user`
  - 一次安裝所有內建沙盒 extras：`/install all-sandboxes` 或 `dcode --install all-sandboxes`。
- **沙盒啟動旗標與設定腳本**：
  - `--sandbox [TYPE]`：指定沙盒供應商（預設 `none`；不帶值傳入 `--sandbox` 則使用 `config.toml` 的 `[sandboxes].default`，裸旗標必須放在命令列最後）。
  - `--sandbox-id ID`：依 ID 重用既有沙盒，略過建立與清理（不可與 `--sandbox-snapshot-name` 混用）。
  - `--sandbox-snapshot-name NAME`：使用或建立沙盒快照（支援 `langsmith`、`daytona`、`runloop` 及宣告支援快照的第三方供應商；不可與 `--sandbox-id` 混用）。
  - `--sandbox-setup PATH`：沙盒建立後於沙盒內執行的初始化 shell 腳本；`dcode` 會使用本機環境變數（如 `.env` 中的機密）自動展開腳本內的 `${VAR}` 變數引用。
- **可插拔沙盒供應商探索與優先順序**：
  - **優先順序（同名時由高至低）**：**Config-declared providers（`config.toml`） > Third-party entry points（Python 套件） > Built-in providers（內建）**。
  - **第三方 Entry-Point 供應商**：實作 `deepagents_code.integrations.sandbox_provider` 的 `SandboxProvider` 子類別（定義 `metadata` 回傳 `SandboxProviderMetadata(name, working_dir, install=SandboxInstallHint(...), supports_sandbox_id, supports_snapshot_name)`，並實作 `get_or_create` 與 `delete`），於 `pyproject.toml` 註冊 `[project.entry-points."deepagents_code.sandbox_providers"]`（未覆寫 `metadata` 時預設工作目錄為 `/workspace` 且不支援快照）。
  - **`config.toml` 宣告供應商（`[sandboxes]` 與 `[sandboxes.providers.<name>]`）**：
    - `[sandboxes] default = "<name>"`：執行無值 `dcode --sandbox` 時使用的預設供應商。
    - `class_path`（`string`，必填）：`"module.path:ClassName"` 格式。
    - `working_dir`（`string`，預設 `"/workspace"`）：沙盒內預設工作目錄。
    - `package`（`string`，選填）：缺少相依套件時於錯誤訊息中建議安裝的套件名稱。
    - `supports_sandbox_id`（`boolean`，預設 `true`）：是否允許 `--sandbox-id`。
    - `supports_snapshot_name`（`boolean`，預設 `false`）：是否允許 `--sandbox-snapshot-name`。
    - `[sandboxes.providers.<name>.params]`（`object`，選填）：轉發給 `get_or_create()` 的額外關鍵字參數（如 `region = "us-east-1"`）。

## 相關頁面
- [[entities/deepagents-code-cli-reference]]
- [[guides/deepagents-code-configuration-and-providers]]
- [[concepts/deepagents-code-extensibility]]

## 出處
- docs/deepagents/code/approval-modes.md
- docs/deepagents/code/hooks.md
- docs/deepagents/code/remote-sandboxes.md
