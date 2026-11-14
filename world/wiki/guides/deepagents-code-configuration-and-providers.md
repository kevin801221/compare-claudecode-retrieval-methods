# Deep Agents Code Configuration, `config.toml`, Model Providers & Credentials

別名：Deep Agents Code 設定與供應商、config.toml、managed_config.toml、模型供應商設定、API 金鑰與憑證管理、環境變數參考、DEEPAGENTS_HOME
框架：deepagents

## 摘要
Deep Agents Code（`dcode`）採用分層設定架構（tiered configuration），支援透過管理員策略檔 `managed_config.toml`、`DEEPAGENTS_CODE_` 前綴環境變數、標準環境變數、`~/.deepagents/config.toml`、專案與全域 `.env` 檔案，以及互動式 `/auth`（或命令列 `dcode auth`）憑證管理員進行全方位設定。其模型供應商系統相容於所有支援工具呼叫（tool calling）的 LangChain `BaseChatModel`，內建支援 OpenAI（含 ChatGPT 訂閱登入的 `openai_codex`）、Anthropic、Google Gemini、Gemini Enterprise Agent Platform（Vertex AI）、AWS Bedrock、Ollama、Groq、Fireworks、Baseten、OpenRouter、LiteLLM 等 25 種以上供應商，並提供端點與金鑰配對解析、模型參數與 Profile 覆寫、冷快取與花費警告、QuickJS 直譯器限制以及企業車隊管理（Managed Configuration）機制。

## 重點

### 設定解析優先順序（Configuration Precedence）與檢視指令
- **一般設定選項（General options，如直譯器限制、更新設定、佈景主題與 `config.toml` 各欄位）解析順序（由高至低）**：
  1. 管理員擁有的 `managed_config.toml`
  2. `DEEPAGENTS_CODE_` 前綴環境變數
  3. 標準（Canonical）環境變數（若適用）
  4. `~/.deepagents/config.toml`
  5. 內建預設值（Built-in default）
- **設定檢視指令（`dcode config`）**：
  - `dcode config`（或 `dcode config show`）：顯示每個設定項目的當前值與來源（供應商憑證與機密僅顯示 `configured` / `not configured`，絕不印出實際值）。
  - `dcode config get <key>`：顯示單一設定的值與來源（如 `dcode config get interpreter.memory_limit_mb`、`dcode config get runtime.recursion_limit`）。
  - `dcode config list`（別名 `ls`）：列出所有可用設定選項。
  - `dcode config path`：顯示 `managed_config.toml`、`config.toml`、專案與全域 `.env`、`hooks.json` 與受管狀態檔的路徑及各檔案是否存在。
  - 加上 `--verbose` 可顯示描述、預設值與可定義位置；結合 `--verbose --json` 可包含接受的型別與完整參考資訊。

### 環境變數與 `.env` 載入規則
- **`.env` 檔案載入順序**：
  1. 啟動時從當前工作目錄向上搜尋最近的專案 `.env`（找到的第一個 `.env` 勝出）。
  2. 全域 `~/.deepagents/.env`（作為所有專案的後備）。
  - 專案 `.env` 優先於全域 `~/.deepagents/.env`，但**兩者皆不會覆寫 shell 中已匯出的環境變數**。
- **略過專案 `.env`**：設定 `[startup] read_project_dotenv = false` 或環境變數 `DEEPAGENTS_CODE_READ_PROJECT_DOTENV=0`（此設定在讀取任何專案 `.env` 前解析，因此專案 `.env` 無法自行開啟或關閉此開關）。
- **禁止在 `.env`（專案與全域皆同）中設定的高風險環境變數**：
  - Profile 與信任根目錄：`DEEPAGENTS_HOME`、`DEEPAGENTS_HOME_IS_DEFAULT`、`DEEPAGENTS_CODE_READ_PROJECT_DOTENV`、`DEEPAGENTS_INHERITED_PYTHONPATH`
  - 動態連結器預載／稽核：`DYLD_INSERT_LIBRARIES`、`DYLD_LIBRARY_PATH`、`LD_AUDIT`、`LD_LIBRARY_PATH`、`LD_PRELOAD`
  - 直譯器啟動／路徑：`NODE_OPTIONS`、`PATH`、`PYTHONEXECUTABLE`、`PYTHONHOME`、`PYTHONPATH`、`PYTHONSTARTUP`
  - Shell 啟動掛鉤：`BASH_ENV`、`ENV`、`BASHOPTS`、`SHELLOPTS`、`CDPATH`、`GLOBIGNORE`
  - 憑證提示劫持：`GIT_ASKPASS`、`SSH_ASKPASS`
  - Git 設定／執行注入：`GIT_DIR`、`GIT_WORK_TREE`、`GIT_OBJECT_DIRECTORY`、`GIT_EXEC_PATH`、`GIT_EDITOR`、`GIT_PAGER`、`GIT_SSH`、`GIT_SSH_COMMAND`，以及前綴家族 `GIT_CONFIG_COUNT`、`GIT_CONFIG_KEY_*`、`GIT_CONFIG_VALUE_*`、`GIT_CONFIG_PARAMETERS`、`GIT_CONFIG_SYSTEM`、`GIT_CONFIG_GLOBAL`
  - Windows 程序變數：`COMSPEC`、`SYSTEMROOT`、`WINDIR`
- **僅禁止在專案 `.env` 中設定的變數（須改設於 shell 或全域 `~/.deepagents/.env`）**：
  - `DEEPAGENTS_CODE_DANGEROUSLY_ENABLE_PROJECT_MCP_SERVERS`、`DEEPAGENTS_CODE_DISABLED_PROJECT_MCP_SERVERS`、`DEEPAGENTS_CODE_AUTO_CLASSIFIER_MODEL`、`DEEPAGENTS_CODE_AUTO_CLASSIFIER_TIMEOUT`、`DEEPAGENTS_CODE_FORKED_SUBAGENTS`、`LANGGRAPH_DEFAULT_RECURSION_LIMIT`、`TERM_PROGRAM`。
- **`DEEPAGENTS_CODE_` 前綴覆寫機制**：
  - 對於 Deep Agents Code 讀取的任何環境變數（包含第三方 API 金鑰），皆會先檢查 `DEEPAGENTS_CODE_{NAME}`，再回退至 `{NAME}`。
  - 例如設 `DEEPAGENTS_CODE_OPENAI_API_KEY=sk-cli-only` 可僅供 `dcode` 使用而不影響其他工具；設為空字串 `DEEPAGENTS_CODE_ANTHROPIC_API_KEY=` 則可讓 `dcode` 忽略 shell 匯出的金鑰。

### `DEEPAGENTS_CODE_*` 與安裝環境變數完整參考
- **安裝腳本環境變數（搭配 `curl -LsSf https://langch.in/dcode | ... bash`；支援以 root 身分在 macOS MDM 如 Kandji、Jamf 下執行，當 `id -u` 為 `0` 時會透過 `/dev/console` 或使用者目錄掃描解析真實主控台使用者的 `HOME` 並 `chown` 回目標使用者）**：
  - `DEEPAGENTS_CODE_VERSION`（`string`）：指定安裝的確切版本（如 `"0.1.16"` 或 `"0.1.0rc1"`），與 `DEEPAGENTS_CODE_PRERELEASE` 互斥。
  - `DEEPAGENTS_CODE_PRERELEASE`（`string`）：`uv` 預發佈策略（`disallow`、`allow`、`if-necessary`、`explicit`、`if-necessary-or-explicit`），與 `DEEPAGENTS_CODE_VERSION` 互斥。
  - `DEEPAGENTS_CODE_EXTRAS`（`string`）：逗號分隔的預安裝 extras（如 `"ollama,groq"` 或 `"daytona"`）。
  - `DEEPAGENTS_CODE_PYTHON`（`string`，預設 `"3.13"`）：安裝使用的 Python 版本。
  - `DEEPAGENTS_CODE_SKIP_OPTIONAL`（`string`）：設為 `1` 略過選用工具檢查。
  - `DEEPAGENTS_CODE_VERBOSE`（`string`）：設為 `1` 顯示 `uv` 原始 stderr 與詳細狀態列。
  - `UV_BIN`（`string`）：指定 `uv` 執行檔路徑（未設定時自動偵測）。
- **執行階段環境變數**：
  - `DEEPAGENTS_HOME`（`string`）：自訂使用者設定檔與信任根目錄（預設 `~/.deepagents`）。僅接受絕對路徑或 `~/` 開頭路徑（拒絕相對路徑、`~user`、根目錄 `/`、家目錄本身、非目錄、不可讀目錄或無效符號連結），且**必須在啟動前的繼承 shell 環境中設定**（不可寫在 `.env`）。注意：跨 CLI 共享的 `~/.agents/skills/` 仍從啟動時的家目錄解析，不隨 `DEEPAGENTS_HOME` 移動。
  - `DEEPAGENTS_CODE_AUTO_UPDATE`（`string`）：切換自動更新（預設啟用；設為 `0`、`false`、`no`、`off` 或空值可停用，覆寫 `[update].auto_update`）。
  - `DEEPAGENTS_CODE_NO_UPDATE_CHECK`（`string`）：設為 `1` 停用自動檢查更新（同時阻止啟動時自動安裝更新，對應 `[update].check = false`）。
  - `DEEPAGENTS_CODE_PRICES_AUTO_UPDATE`（`string`，預設 `"true"`）：背景每小時從上游更新模型價格目錄（覆寫 `[update].prices_auto_update`）。
  - `DEEPAGENTS_CODE_AUTO_CLASSIFIER_TIMEOUT`（`integer`）：Auto 模式分類器審查每批受控動作的秒數上限，有效範圍 `1`–`300`，超出範圍或非整數回退至預設值 `20`（覆寫 `[models].auto_classifier_timeout`）。
  - `DEEPAGENTS_CODE_DEBUG`（`string`）：啟用詳細除錯日誌（接受不分大小寫的 `1`/`true`/`yes`/`on`），關閉時保留該工作階段的伺服器日誌檔並將路徑印至 stderr。
  - `DEEPAGENTS_CODE_DEBUG_FILE`（`string`，預設 `"/tmp/deepagents_debug.log"`）：除錯日誌檔案路徑。
  - `DEEPAGENTS_CODE_EXPERIMENTAL`（`string`）：設為 `1`（或真值）啟用實驗性功能（如 Python 擴充套件、Auto 核准模式）。
  - `DEEPAGENTS_CODE_EXTENSIONS`（`string`，預設 `"true"`）：啟用或停用所有來源的 Python 擴充套件探索（覆寫 `[extensions].enabled`，仍需 `DEEPAGENTS_CODE_EXPERIMENTAL=1`）。
  - `DEEPAGENTS_CODE_EXTENSIONS_TRUST`（`string`，預設 `"ask"`）：設定專案擴充套件預設信任策略為 `ask`、`always` 或 `never`（覆寫 `[extensions].trust`）。
  - `DEEPAGENTS_CODE_DISABLED_PROJECT_MCP_SERVERS`（`string`，需 `deepagents-code>=0.1.40`）：逗號分隔、永遠拒絕的專案 MCP 伺服器名稱清單（與 `[mcp].disabled_project_servers` 合併，優先於已儲存核准與 `--trust-project-mcp`）。
  - `DEEPAGENTS_CODE_DANGEROUSLY_ENABLE_PROJECT_MCP_SERVERS`（`string`，需 `deepagents-code>=0.1.40`，取代舊版被忽略的 `DEEPAGENTS_CODE_ENABLED_PROJECT_MCP_SERVERS`）：逗號分隔、依名稱預先核准任何專案中同名 MCP 伺服器的跨程序逃生閥（設定時會取代該程序的已存核准）。
  - `DEEPAGENTS_CODE_COLLAPSE_PASTES`（`string`，預設 `"true"`）：將聊天輸入框的大型貼上內容收合為精簡佔位符（覆寫 `[ui].collapse_pastes`）。
  - `DEEPAGENTS_CODE_EXTRA_SKILLS_DIRS`（`string`）：冒號分隔路徑清單，加入技能目錄邊界許可清單（覆寫 `[skills].extra_allowed_dirs`）。
  - `DEEPAGENTS_CODE_FORKED_SUBAGENTS`（`string`，預設 `"true"`）：讓內建 `general-purpose` 子代理繼承父對話與系統提示詞；設為假值則改用隔離模式（忽略專案 `.env` 中的設定）。
  - `DEEPAGENTS_CODE_GIT_ATTRIBUTION`（`string`，預設 `"true"`）：啟用唯讀 Git 檢查以在 LangSmith 追蹤標記代理修改的儲存庫與分支（覆寫 `[tracing].git_attribution`）。
  - `DEEPAGENTS_CODE_HISTORY_RETENTION_DAYS`（`integer`，預設 `30`）：`/offload` 產生的 `~/.deepagents/conversation_history/*.md` 歷史歸檔保留天數，`0` 停用啟動清理（覆寫 `[history].retention_days`）。
  - `DEEPAGENTS_CODE_LANGSMITH_PROJECT`（`string`）：設定 Deep Agents Code 自身追蹤的目標環境 `tracer_session_name`。
  - `DEEPAGENTS_CODE_LANGSMITH_REDACT`（`string`，預設 `"true"`）：切換客戶端 LangSmith 追蹤輸入／輸出的機密遮罩（覆寫 `[tracing].langsmith_redact`；當啟用遮罩但無法設定遮罩時，該次執行會自動停用追蹤）。
  - `DEEPAGENTS_CODE_LANGSMITH_REPLICA_PROJECTS`（`string`）：將追蹤同步複製寫入第二個代理環境的 `tracer_session_name`。
  - `DEEPAGENTS_CODE_LANGSMITH_TRACING`（`string`）：設為 `false` 強制停用 LangSmith 代理追蹤（覆寫 `LANGSMITH_TRACING=true`）。
  - `DEEPAGENTS_CODE_MEMORY_AUTO_SAVE`（`string`，預設 `"true"`）：是否讓代理主動儲存學習內容至記憶（覆寫 `[memory].auto_save`）。
  - `DEEPAGENTS_CODE_MCP_TOOL_TIMEOUT`（`number`，預設 `120`）：MCP 工具呼叫最大秒數，有效範圍 `1`–`900`（覆寫 `[mcp].tool_timeout`）。
  - `DEEPAGENTS_CODE_OLLAMA_DISCOVERY`（`string`）：設為 `0` 可停用 `langchain-ollama` 自動探索本機已拉取模型的功能。
  - `DEEPAGENTS_CODE_ONBOARDING`（`string`）：覆寫首次執行導覽流程（真值強制每次啟動開啟，假值完全隱藏以利 CI 或預佈建機器）。
  - `DEEPAGENTS_CODE_READ_PROJECT_DOTENV`（`string`，預設 `"true"`）：是否載入專案 `.env`（覆寫 `[startup].read_project_dotenv`）。
  - `DEEPAGENTS_CODE_RECENT_THREADS`（`integer`，預設 `100`）：執行緒清單載入與顯示的最大筆數（小於 `1` 夾限為 `1`）。
  - `DEEPAGENTS_CODE_RECURSION_LIMIT`（`integer`）：每回合 LangGraph 圖最大節點呼叫次數（覆寫 `[runtime].recursion_limit`）。
  - `LANGGRAPH_DEFAULT_RECURSION_LIMIT`（`integer`）：當無 Deep Agents recursion limit 來源生效時繼承的上游 LangGraph 步數預算（忽略專案 `.env`）。
  - `DEEPAGENTS_CODE_SHELL_ALLOW_LIST`（`string`）：逗號分隔的允許 shell 指令清單（或 `recommended` / `all`）。
  - `DEEPAGENTS_CODE_SHOW_REASONING`（`string`）：設為 `1` 顯示或 `0` 隱藏供應商可見推理（覆寫 `[ui].show_reasoning`）。
  - `DEEPAGENTS_CODE_SHOW_USAGE_STATS`（`string`，預設 `"true"`）：工作階段結束時是否顯示使用量統計（覆寫 `[ui].show_usage_stats`）。
  - `DEEPAGENTS_CODE_THEME`（`string`）：強制指定 UI 佈景主題（優先順序最高）。
  - `DEEPAGENTS_CODE_USER_ID`（`string`）：在 LangSmith 追蹤 metadata 中附加使用者識別碼。

### `~/.deepagents/config.toml` 完整區段與欄位規格
- **`[models]` 區段**：
  - `default`（`string`）：長期預設模型（如 `"ollama:qwen3:4b"`），優先於 `recent`；可由 `/model --default --clear` 移除。
  - `recent`（`string`）：最近一次透過 `/model` 切換的模型（自動寫入）。
  - `summarization_default`（`string`）：用於自動上下文壓縮、`/offload` 與 `/compact` 的專屬摘要模型（如 `"openai:gpt-5.6-sol"`）。解析順序：`--summarization-model` → `[models].summarization_default` → 主代理模型。
  - `auto_classifier`（`string`）：Auto 核准模式分類器使用的模型（如 `"openai:gpt-5.6-luna"`）。未設定時，Anthropic 預設選 Claude Sonnet、Google 預設選 Gemini Flash、OpenAI 預設選 GPT Luna，其他供應商則繼承主代理模型。
  - `auto_classifier_timeout`（`integer`，預設 `20`，範圍 `1`–`300`）：Auto 分類器審查每批動作的逾時秒數；逾時未完成的批次會以 `classifier_unavailable` 拒絕，連續逾時會回退至手動核准 UI。
  - `allowed`（`string[]`）：限制可使用的模型清單，支援精確區分大小寫的 `"provider:model"`（Bedrock 須包含版本冒號如 `"bedrock:anthropic.claude-3-5-sonnet-20241022-v2:0"`）或萬用字元 `"provider:*"`。未設定時允許所有模型；空陣列 `[]` 則封鎖所有模型。
- **`[models.providers.<name>]` 區段**：
  - `display_name`（`string`）：在 `/auth` UI 顯示的人類可讀名稱。
  - `api_key_url`（`string`）：在 `/auth` 輸入金鑰前顯示的申請金鑰網址（非機密）。
  - `models`（`string[]`）：加入 `/model` 互動切換器的模型名稱清單（會繞過 profile 的 `tool_calling` 等過濾條件強制顯示；但注意若啟用了 `[models].allowed`，仍須將模型加入 `allowed` 才可使用）。
  - `api_key_env`（`string`）：存放 API 金鑰的環境變數名稱（如 `"OPENAI_API_KEY"`）。切勿將 `api_key` 直接放進 `params`。
  - `base_url`（`string`）：覆寫供應商預設端點（例如 Ollama 預設為 `http://localhost:11434`）。若同時設定 `base_url` 與 `base_url_env`，靜態的 `base_url` 優先勝出。
  - `base_url_env`（`string`）：存放供應商 `base_url` 的環境變數名稱（如 `"MYPROVIDER_BASE_URL"`），支援與金鑰配對解析。
  - `class_path`（`string`）：用於任意自訂供應商（Arbitrary providers），格式為 `"module.path:ClassName"`（必須繼承自 LangChain `BaseChatModel`）。需透過 `dcode --install <pkg> --package`（或工作階段內 `/install <pkg> --package --force`）將套件安裝至 `dcode` 環境；切換至 `my_custom:my-model-v1` 時會以 `MyChatModel(model="my-model-v1", ...)` 實例化。套件亦可透過 `<package>.data._profiles` 中的 `_PROFILES` 字典提供 model profiles。
  - `enabled`（`boolean`，預設 `true`）：設為 `false` 可將自動探索到的供應商從 `/model` 選擇器中隱藏（仍可透過 `--model` 或 `/model provider:model` 直接指定）。
  - `[models.providers.<name>.params]` 與 `[models.providers.<name>.params."<model>"]`：轉發給模型建構子的額外參數（shallow merge 淺層合併，模型子表覆寫供應商層級同名鍵）。優先順序：`--model-params`（或 `/model --model-params`）> `config.toml` 模型子表 > `config.toml` 供應商表。注意：OpenAI 供應商預設使用 Responses API，若連接僅支援 Chat Completions API 的 OpenAI 相容閘道，必須設定 `[models.providers.openai.params] use_responses_api = false`。
  - `[models.providers.<name>.profile]` 與 `[models.providers.<name>.profile."<model>"]`：進階覆寫執行階段 `ModelProfile` 欄位（如 `tool_calling = true`、`max_input_tokens = 128000`）。若自訂模型未設定 `max_input_tokens`，自動摘要壓縮會回退至約 `170,000` tokens 的固定觸發門檻。優先順序：`--profile-override` > `config.toml` profile > 模型內建預設值。
- **`[agents]` 區段**：
  - `default`（`string`）：長期預設代理（在 `/agents` 選擇器按 `Ctrl+S` 釘選或取消）。
  - `recent`（`string`）：最近一次在 `/agents` 按 `Enter` 切換的代理（自動寫入）。優先順序：`-r`/`--resume`（還原執行緒原代理）> `-a`/`--agent` > `[agents].default` > `[agents].recent`。
- **`[retries]` 與 `[retries.<provider>]` 區段**：
  - `max_retries`（`integer`，預設 `5`，`>= 0`）：模型節點遇到暫時性錯誤的重試次數（`0` 為停用）。優先順序：`--max-retries N` > `[retries.<provider>].max_retries` > `[retries].max_retries` > 預設值 `5`。
  - `param`（`string`，僅限自訂供應商 `[retries.<provider>]`）：指定供應商 SDK 建構子中控制重試次數的參數名稱（合法 Python 識別字如 `"max_retries"` 或 `"retries"`），供 `dcode` 將供應商 SDK 內部重試關閉，由模型節點中介軟體統一控管重試預算。
- **`[startup]` 區段**：
  - `mode`（`string`，預設 `"manual"`）：互動工作階段預設核准模式，可設為 `"manual"`、`"auto"`（需 `DEEPAGENTS_CODE_EXPERIMENTAL=1`）或 `"yolo"`（需單次風險確認）。
  - `yolo_switcher`（`boolean`）：控制是否允許在 `Shift+Tab` 循環中切換至 YOLO（管理員可於 `managed_config.toml` 設為 `false`）。
  - `read_project_dotenv`（`boolean`，預設 `true`）：啟動時是否讀取專案 `.env`。
- **`[warnings]` 區段**：
  - `session_cost_threshold_usd`（`number`，預設 `50`）：單一執行緒累計預估花費超過此美元門檻時發出一次警告並建議 `/offload` 或 `/clear`；設為 `0` 或負數可停用。
  - `cache_prompt`（`string`，預設 `"expiry"`）：控制 Anthropic 與 OpenAI 模型的冷提示詞快取（Cold prompt-cache）到期提示行為：
    - `"expiry"`（預設）：當頁尾快取保留計時器歸零且應用程式閒置時彈出提示（按 `Enter` 使用摘要模型開啟包含摘要、原執行緒 ID 與紀錄檔路徑的新執行緒；按 `Esc` 留在原執行緒且保留草稿不送出）。
    - `"send"`：等到快取過期後使用者實際送出訊息時才彈出相同提示（舊版 `warnings.cache_expiry_prompt = false` 若未明確設定 `cache_prompt` 會自動映射為 `"send"`）。
    - `"off"`：停用所有快取到期提示與發送時快取成本確認（不影響 `session_cost_threshold_usd`）。
  - `cold_cache_min_delta_usd`（`number`，預設 `0.50`）：當切換模型、端點、快取設定或快取年齡未知時，觸發「發送時額外快取成本確認（send-time cost confirmation）」的最小預估價差（美元）；設為 `0` 或負數僅停用發送時確認而不停用到期提示。確認對話框提供四個選項：`Send anyway`、`Send and do not warn again this session`、`Send and never warn again`（可由 `/notifications` 重新啟用）、`Do not send (keep draft)`。
  - `trusted_cache_endpoints`（`string[]`）：宣告會原封不動轉發快取設定並遵守官方保留時間的受信任閘道主機名稱清單（如 `["smith.langchain.com"]`，採精確主機名稱比對，`example.com` 不涵蓋 `gw.example.com`；透過 LangSmith LLM Gateway 進行跨格式路由如 OpenAI 格式轉 Anthropic 模型時，即使受信任仍會保持靜默）。
- **`[ui]` 與 `[themes.*]` 與 `[terminal]` 區段**：
  - `[ui] theme`（`string`，預設 `"langchain"`）：儲存的配色主題名稱。
  - `[ui.terminal_themes]`（`table`）：依終端機的 `TERM_PROGRAM`（如 `"Apple_Terminal"`、`"iTerm.app"`、`"WezTerm"`、`"vscode"`、`"ghostty"`）自動套用對應主題（在 `/theme` 選擇器按 `T` 可將當前高亮主題綁定至目前終端機）。主題解析順序：`DEEPAGENTS_CODE_THEME` → `[ui.terminal_themes]` → `[ui] theme` → 內建預設 `"langchain"`。
  - `[themes.<name>]`：定義使用者自訂主題（必填 `label` 字串，`dark` 布林預設 `false`，可選填 `primary`、`warning`、`background` 等色碼）或覆寫內建主題色碼（`[themes.<builtin-name>]` 僅讀取色彩欄位，`/reload` 即生效）。
  - `[ui] show_reasoning`（`boolean`）：統一設定互動與非互動模式是否顯示供應商可見推理（優先順序：`--show-reasoning` > `DEEPAGENTS_CODE_SHOW_REASONING` > `[ui].show_reasoning`）。
  - `[ui] show_diff_line_numbers`（`boolean`，預設 `true`）：在紀錄與核准 diff 中顯示檔案相對行號（可由 `/line-numbers` 切換並儲存）。
  - `[ui] show_usage_stats`（`boolean`，預設 `true`）：工作階段結束時顯示使用量統計。
  - `[ui] collapse_pastes`（`boolean`，預設 `true`）：收合聊天輸入框的大型貼上文字。
  - `[terminal] tab_title`（`string`，預設 `"{app_name} - {thread_name}"`）：自訂互動模式終端機分頁標題範本，支援佔位符 `{app_name}`、`{thread_name}`、`{cwd}`、`{branch}`（修改後需重啟 `dcode`）。
- **`[threads]`、`[memory]`、`[history]`、`[skills]` 區段**：
  - `[threads] auto_rename`（`boolean`，預設 `true`）：首次助理回應完成後自動為執行緒命名。
  - `[threads] rename_model`（`string`）：指定自動命名與無參數 `/rename` 使用的模型（留空則使用對話模型）。
  - `[threads] compact_on_resume_threshold`（`integer`，預設 `400000`）：恢復執行緒時若上下文超過此 token 門檻，會在下一則訊息前主動詢問是否壓縮；設為 `0` 停用詢問。
  - `[threads] max_resume_age`（`string`）：限制可恢復執行緒的最大滾動年齡，格式為正整數加時間單位後綴 `s`（秒）、`m`（分）、`h`（時）、`d`（日）或 `w`（週），例如 `"7d"`。
  - `[threads] resume_after`（`string`）：限制僅能恢復晚於指定 ISO 8601 日期（視為 UTC 午夜）或含時區時間戳記（如 `"2025-06-01T00:00:00Z"`）的執行緒。與 `max_resume_age` 同時設定時取較晚（較嚴格）的時間點；若執行緒缺少或具無效時間戳記則一律封鎖恢復。
  - `[memory] auto_save`（`boolean`，預設 `true`）：是否自動將學習內容寫入記憶。
  - `[history] retention_days`（`integer`，預設 `30`）：`/offload` 歷史歸檔保留天數（`0` 為停用清理）。
  - `[skills] extra_allowed_dirs`（`string[]`）：加入技能符號連結目標的邊界許可清單（支援 `~` 展開，不會新增技能探索路徑）。
- **`[interpreter]` 區段（內建 QuickJS REPL `js_eval` 工具設定）**：
  - `enable_interpreter`（`boolean`，預設 `true`）：是否在本機工作階段的主代理掛載 `js_eval` 中介軟體（停用時可由 `--interpreter` 單次啟用）。
  - `timeout_seconds`（`number`，預設 `5.0`）：每次 `js_eval` 呼叫的牆上時鐘逾時秒數。
  - `memory_limit_mb`（`integer`，預設 `64`）：工作階段共享的 QuickJS 堆積記憶體上限（MB）。
  - `max_ptc_calls`（`integer`，預設 `256`）：每次 `js_eval` 呼叫允許的最大 `tools.*` 宿主橋接呼叫次數。
  - `max_result_chars`（`integer`，預設 `4000`）：`js_eval` 結果與擷取 stdout 截斷前的最大字元數。
  - `ptc`（`string | boolean | string[]`，預設 `"safe"`）：程式化工具呼叫（Programmatic Tool Calling）許可清單：
    - `"safe"`（預設）：僅開放唯讀預設集 `read_file`、`glob`、`grep`。
    - `"all"`：開放所有宿主工具（因 PTC 呼叫會繞過核准提示，除非全域已停用核准，否則**必須同時設定 `ptc_acknowledge_unsafe = true`**）。
    - 工具名稱陣列（如 `["safe", "web_search"]`，其中 `"safe"` 會展開為唯讀預設集，陣列內不可包含 `"all"`）。
    - `false` 或 `[]`：禁止從 REPL 呼叫任何工具（純直譯器模式；注意不接受布林值 `true`）。
  - `ptc_acknowledge_unsafe`（`boolean`，預設 `false`）：確認理解 `ptc = "all"` 會繞過核准提示。
- **`[extensions]`、`[mcp]`、`[tracing]`、`[runtime]`、`[update]` 區段**：
  - `[extensions] enabled`（`boolean`，預設 `true`）、`trust`（`string`，預設 `"ask"`，可為 `"ask"`/`"always"`/`"never"`）、`extra_paths`（`string[]`，預設 `[]`，相對路徑由 profile 目錄解析）。
  - `[mcp] tool_timeout`（`number`，預設 `120`，範圍 `1`–`900`）：MCP 工具呼叫逾時秒數。
  - `[tracing] langsmith_redact`（`boolean`，預設 `true`）：客戶端 LangSmith 追蹤機密遮罩；`git_attribution`（`boolean`，預設 `true`）：唯讀 Git 儲存庫與分支標記檢查。
  - `[runtime] recursion_limit`（`integer`，設定檔與環境變數有效範圍為 `25`–`100000`，CLI `--recursion-limit` 則接受 `>= 1`）：每回合 LangGraph 節點呼叫上限（不影響獨立的 `goal_rubric` 遞迴限制）。解析順序：`managed_config.toml` → `--recursion-limit` → `DEEPAGENTS_CODE_RECURSION_LIMIT` → `[runtime].recursion_limit` → `LANGGRAPH_DEFAULT_RECURSION_LIMIT` → Agent Server 預設值。
  - `[update] auto_update`（`boolean`，預設 `true`）、`check`（`boolean`，預設 `true`）、`prices_auto_update`（`boolean`，預設 `true`）。自訂模型價格可寫入 `~/.deepagents/prices.json`（採用 `genai-prices` provider-array schema，包含 `id`、`name`、`api_pattern`、`models[].prices.input_mtok` 與 `output_mtok`，單位為每百萬 token 美元，僅在 `genai-prices` 未收錄該模型時生效，修改後需重啟）。

### 管理員受管設定（Managed Configuration：`managed_config.toml`）
- **各作業系統固定路徑**：
  - macOS：`/Library/Application Support/dcode/managed_config.toml`
  - Linux：`/etc/dcode/managed_config.toml`
  - Windows：`<ProgramData>\dcode\managed_config.toml`（透過系統登錄檔查詢 ProgramData 而非 `%ProgramData%` 環境變數；若登錄檔不可用則檢查 `C:\ProgramData\dcode\managed_config.toml`，若仍找不到檔案則為了防止繞過管理員策略，所有使用設定的指令會直接停止執行）。
- **遠端載入策略（Remote policy）**：
  - 可在本地 `managed_config.toml` 中僅設定 `[managed_config] source = "https://config.example.com/dcode-policy.toml"`（不可混寫其他本地策略，遠端檔案亦不可再指向另一個 `source`）。
  - 遠端 URL 規範：必須使用 HTTPS、不含憑證或查詢參數、長度不超過 `2,048` 個 ASCII 字元、不跟隨重新導向、不使用 proxy 環境變數、不寫入磁碟；伺服器必須在 **5 秒**內回傳 HTTP `200`、無壓縮、大小不超過 `1 MiB` 的非空 UTF-8 TOML 檔案（管理員應保護 `SSL_CERT_FILE` 與 `SSL_CERT_DIR` 不被使用者竄改）。
- **失敗關閉（Fail-closed）與結束代碼 `78`**：
  - 當無法讀取／解析 `managed_config.toml`、無法下載遠端策略，或下列關鍵安全設定值無效時，Deep Agents Code 會拒絕啟動並以結束代碼 **`78`** 退出（執行中工作階段若更新失敗則維持前一次有效策略）：
    `interpreter.enable_interpreter`、`interpreter.ptc`、`interpreter.ptc_acknowledge_unsafe`、`models.allowed`、`models.auto_classifier`、`runtime.recursion_limit`、`sandboxes.default`、`shell.allow_list`、`skills.extra_allowed_dirs`、`startup.mode`、`startup.yolo_switcher`、`tracing.langsmith_redact`。
  - 注意：`[sandboxes].default` 僅在使用者傳入 `--sandbox` 時選擇預設後端，並不會強制所有未帶 `--sandbox` 的啟動進入沙盒。

### 內建模型供應商對照表（Provider Reference）
OpenAI、Anthropic 與 Google Gemini 預設內建；其餘供應商可透過 `/install <extra>` 或 `dcode --install <extra>` 安裝：
- **OpenAI**：套件 `langchain-openai`｜憑證變數 `OPENAI_API_KEY`｜支援 Model profiles ✅
- **OpenAI (Codex)**（供應商名稱 `openai_codex`）：套件 `langchain-openai`｜無需 API 金鑰，透過 `/auth` 選擇 `openai_codex` 啟動 ChatGPT 瀏覽器 OAuth 登入（Token 存於 `~/.deepagents/.state/chatgpt-auth.json`）｜支援 Model profiles ✅
- **Azure OpenAI**：套件 `langchain-openai`｜憑證變數 `AZURE_OPENAI_API_KEY`｜支援 Model profiles ✅
- **Anthropic**：套件 `langchain-anthropic`｜憑證變數 `ANTHROPIC_API_KEY`｜支援 Model profiles ✅
- **Google Gemini API**（`google_genai`）：套件 `langchain-google-genai`｜憑證變數 `GOOGLE_API_KEY`｜支援 Model profiles ✅
- **Gemini Enterprise Agent Platform**（`google_vertexai`）：套件 `langchain-google-genai`｜憑證變數 `GOOGLE_CLOUD_PROJECT`｜支援 Model profiles ✅
- **Gemini Enterprise Agent Platform (Anthropic)**（`google_anthropic_vertex`）：套件 `langchain-google-vertexai`（需 `/install vertex` 並執行 `gcloud auth application-default login` 設定 ADC）｜憑證變數 `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`（如 `"global"`，模型格式如 `google_anthropic_vertex:claude-sonnet-4-6`）｜支援 Model profiles ✅
- **Baseten**：套件 `langchain-baseten`｜憑證變數 `BASETEN_API_KEY`（如 `baseten:moonshotai/Kimi-K2.7-Code`）｜支援 Model profiles ✅
- **AWS Bedrock** / **AWS Bedrock Converse**：套件 `langchain-aws`｜憑證變數 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`｜支援 Model profiles ✅
- **Hugging Face**：套件 `langchain-huggingface`｜憑證變數 `HUGGINGFACEHUB_API_TOKEN`｜支援 Model profiles ✅
- **Ollama**：套件 `langchain-ollama`｜憑證變數 `OLLAMA_API_KEY`（僅雲端選用，本機免金鑰；本機 daemon 可達時會自動探索已拉取模型）｜無內建 Model profiles ❌
- **Groq**：套件 `langchain-groq`｜憑證變數 `GROQ_API_KEY`（如 `groq:openai/gpt-oss-120b`）｜支援 Model profiles ✅
- **Cohere**：套件 `langchain-cohere`｜憑證變數 `COHERE_API_KEY`｜無內建 Model profiles ❌
- **Fireworks**：套件 `langchain-fireworks`｜憑證變數 `FIREWORKS_API_KEY`（如 `fireworks:accounts/fireworks/models/deepseek-v4-pro`）｜支援 Model profiles ✅
- **Together**：套件 `langchain-together`｜憑證變數 `TOGETHER_API_KEY`｜無內建 Model profiles ❌
- **Meta**：套件 `langchain-meta`｜憑證變數 `MODEL_API_KEY`｜支援 Model profiles ✅
- **Mistral AI**：套件 `langchain-mistralai`｜憑證變數 `MISTRAL_API_KEY`｜支援 Model profiles ✅
- **DeepSeek**：套件 `langchain-deepseek`｜憑證變數 `DEEPSEEK_API_KEY`｜支援 Model profiles ✅
- **IBM (watsonx.ai)**：套件 `langchain-ibm`｜憑證變數 `WATSONX_APIKEY`｜無內建 Model profiles ❌
- **Nvidia**：套件 `langchain-nvidia-ai-endpoints`｜憑證變數 `NVIDIA_API_KEY`（端點可設 `NVIDIA_BASE_URL` 或 `dcode auth set nvidia --base-url URL`，模型如 `nvidia:nvidia/nemotron-3.5-super-vl-120b-a12b`）｜支援 Model profiles ✅
- **xAI**：套件 `langchain-xai`｜憑證變數 `XAI_API_KEY`｜支援 Model profiles ✅
- **Perplexity**：套件 `langchain-perplexity`｜憑證變數 `PERPLEXITY_API_KEY`（或 `PPLX_API_KEY`）｜支援 Model profiles ✅
- **OpenRouter**：套件 `langchain-openrouter`｜憑證變數 `OPENROUTER_API_KEY`（格式 `openrouter:<model>`）｜支援 Model profiles ✅
- **LiteLLM**：套件 `langchain-litellm`｜依上游供應商設定環境變數（格式 `litellm:<model>`）｜無內建 Model profiles ❌

### 憑證（API Keys）與端點（`base_url`）配對解析順序
- **API 金鑰解析優先順序（Key resolution order，由高至低）**：
  1. **`DEEPAGENTS_CODE_` 前綴環境變數**（例如 `DEEPAGENTS_CODE_OPENAI_API_KEY`）：最高優先權，可用於單次執行覆寫已儲存金鑰。
  2. **應用程式儲存金鑰（App-stored key，`[stored]`）**：透過 `/auth` 或 `dcode auth set` 儲存於 `~/.deepagents/.state/auth.json` 的金鑰。**注意：已儲存金鑰優先於未加前綴的一般環境變數**（避免機器上供其他工具共用的 `OPENAI_API_KEY` 意外污染 `dcode`）。
  3. **一般供應商環境變數（Plain provider env var，`[env: VARNAME]`）**：例如來自 shell 或 `.env` 的 `OPENAI_API_KEY`（包含 Tavily 的 `TAVILY_API_KEY` / `DEEPAGENTS_CODE_TAVILY_API_KEY`）。
- **`base_url` 端點解析優先順序（由高至低）**：
  1. `config.toml` 中該供應商的靜態 `base_url`。
  2. `DEEPAGENTS_CODE_` 前綴的端點環境變數（如 `DEEPAGENTS_CODE_OPENAI_BASE_URL`）。
  3. 一般端點環境變數（如 `OPENAI_BASE_URL`、`ANTHROPIC_BASE_URL`、`GOOGLE_GEMINI_BASE_URL` 或 `base_url_env` 宣告的變數）。
  4. 透過 `/auth` 隨憑證一併儲存的端點（若在 `/auth` 儲存金鑰時將 base URL 留空，會一併清除環境中已匯出的閘道端點如 `OPENAI_BASE_URL`，確保個人金鑰直接連往官方預設端點而非被閘道拒絕）。
  5. 供應商 SDK 內建預設端點。

### 資料目錄結構與優先順序規則（Data Locations & Precedence）
- **核心儲存位置**：
  - `~/.deepagents/.state/sessions.db`：SQLite 對話檢查點資料庫（刪除 `rm ~/.deepagents/.state/sessions.db*` 會永久清除所有對話歷史）。
  - `~/.deepagents/.state/history.jsonl`：命令輸入歷史。
  - `~/.deepagents/.state/auth.json`：API 金鑰儲存區。
  - `~/.deepagents/.state/chatgpt-auth.json`：`openai_codex` 的 ChatGPT OAuth token。
  - `~/.deepagents/.state/mcp-tokens`：MCP OAuth tokens。
  - `~/.deepagents/.state/onboarding_complete`：首次導覽完成標記。
  - 移除應用程式二進位檔：`uv tool uninstall deepagents-code`；清除所有個人資料：`rm -rf ~/.deepagents`。
- **同名項目優先順序規則**：
  - **Skills（高優先權完全覆蓋低優先權，不合併；由低至高）**：
    1. `~/.deepagents/{agent}/skills/`（使用者 Deep Agents 專屬）
    2. `~/.agents/skills/`（使用者跨工具共享）
    3. `.deepagents/skills/`（專案 Deep Agents 專屬）
    4. `.agents/skills/`（專案跨工具共享，**最高優先**）
  - **Subagents（高優先權完全覆蓋低優先權；由低至高）**：
    1. `~/.deepagents/{agent}/agents/`（使用者層級）
    2. `.deepagents/agents/`（專案層級，**最高優先**）
  - **Instructions（所有來源依序串接合併，不覆蓋）**：
    1. 套件內建 `default_agent_prompt.md`（唯讀基礎提示詞）
    2. `~/.deepagents/{agent}/AGENTS.md`（使用者自訂）
    3. `.deepagents/AGENTS.md`（專案偏好位置）
    4. 專案根目錄 `AGENTS.md`

## 相關頁面
- [[entities/deepagents-code-cli-reference]]
- [[concepts/deepagents-code-approval-and-hooks]]
- [[concepts/deepagents-code-extensibility]]

## 出處
- docs/deepagents/code/configuration.md
- docs/deepagents/code/config-file.md
- docs/deepagents/code/providers.md
- docs/deepagents/code/credentials.md
