# Deep Agents Code (`dcode`) CLI Reference & Interactive Guide

別名：Deep Agents Code、dcode、deepagents-code、Deep Agents 終端機編碼代理、Deep Agents CLI、指令參考、互動模式與斜線指令
框架：deepagents

## 摘要
Deep Agents Code（指令名稱為 `dcode`，套件名稱 `deepagents-code`）是建構於 Deep Agents SDK 之上的開源終端機編碼代理（terminal coding agent），支援切換不同模型供應商與模型、跨對話持久化記憶（persistent memory）、自訂技能（skills）、遠端沙盒（remote sandboxes）、目標與評分標準（goals and rubrics）、子代理（subagents）、上下文壓縮（context compaction）、MCP 工具、LangSmith 追蹤（tracing）與人機迴路核准控制（human-in-the-loop approval controls）。它同時提供豐富的 TUI 互動模式（包含斜線指令、鍵盤快捷鍵、`!command` shell 執行、`@filename` 檔案注入与 `@@query` 執行緒引用）以及適合腳本與 CI/CD 管線的非互動模式（`-n` / `--non-interactive` 與 stdin 管線輸入）與管理子指令（`tools`、`agents`、`skills`、`threads`、`mcp`、`config`、`auth`、`doctor`、`update`、`uninstall`）。

## 重點

### 安裝與平台支援
- **安裝與啟動指令**：
  ```bash
  curl -LsSf https://langch.in/dcode | bash
  dcode
  ```
- **預先安裝選用擴充套件（extras）**：在初次安裝 CLI 時可設定環境變數 `DEEPAGENTS_CODE_EXTRAS`（例如 `DEEPAGENTS_CODE_EXTRAS="groq,fireworks"`）。
- **選用擴充套件安裝與移除**：
  - 安裝：`dcode --install <NAME>`（例如 `dcode --install groq`、`dcode --install fireworks`、`dcode --install ollama`、`dcode --install quickjs`、`dcode --install daytona`、`dcode --install all-sandboxes`）。加上 `--package` 可透過 `uv --with` 將 `NAME` 視為自訂供應商套件安裝（而非內建 extra），加上 `--yes` 可跳過確認提示。
  - 移除：`dcode uninstall <NAME>`、`dcode --uninstall <NAME>`，或在互動工作階段中執行 `/uninstall <NAME>`。移除會在保留直譯器、發佈通道（release channel）、其他 extras 與 `--package` 已安裝套件的前提下，重建不含該 extra 的 `uv` 工具安裝環境。
- **平台支援限制**：Deep Agents Code 官方不支援 Windows；Windows 使用者可嘗試在 Windows Subsystem for Linux（WSL）下執行。
- **網路搜尋憑證**：內建網頁搜尋使用 Tavily（`https://tavily.com`），可透過 `/auth` 新增 API 金鑰。
- **版本更新紀錄（Changelog）**：位於 `https://github.com/langchain-ai/deepagents/blob/main/libs/code/CHANGELOG.md`（互動模式亦可執行 `/changelog` 在瀏覽器開啟）。

### 模型選擇與推論參數
- **啟動時模型解析優先順序（未傳入 `--model` 時）**：
  1. **`--model`（`-M`）旗標**：若有提供則最優先（格式為 `provider:model`，如 `anthropic:claude-opus-4-8`、`openai:gpt-6.1-sol`、`fireworks:accounts/fireworks/models/deepseek-v4-pro`，或在供應商明確時直接傳入裸模型名稱如 `gpt-6.1-sol`）。
  2. **`~/.deepagents/config.toml` 中的 `[models].default`**。
  3. **`~/.deepagents/config.toml` 中的 `[models].recent`**（在工作階段中切換模型時自動寫入）。
  4. **環境變數自動偵測（Environment auto-detection）**：依序檢查第一個可用的憑證：`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GOOGLE_API_KEY`、`GOOGLE_CLOUD_PROJECT`（Gemini Enterprise Agent Platform）。其他供應商（如 Groq 或 Fireworks）不參與啟動自動偵測，但仍可透過 `--model` 或已儲存的預設值使用。
- **設定、檢視或清除預設模型**：
  - 設定預設模型：`dcode --default-model anthropic:claude-opus-4-8`（或在互動 `/model` 選擇器中按 `Ctrl+S`，或設定 `config.toml` 的 `[models].default`）。
  - 檢視目前預設模型：`dcode --default-model`（不帶參數）。
  - 清除預設模型：`dcode --clear-default-model`。
- **設定推理強度（Reasoning effort）**：
  - 使用 `/effort` 開啟選擇器檢視當前模型支援的層級，或直接執行 `/effort <level>`。
  - 選擇結果會依 `provider:model` 儲存於 `~/.deepagents/config.toml` 供後續工作階段使用；執行 `/effort clear` 可移除當前模型的已存偏好與工作階段覆寫（設定檔中的模型參數仍可提供 effort 值）。
  - 當代理正在執行任務時開啟 `/effort` 或點擊頁尾（footer）的 effort 標籤，所選設定會等待當前任務完成後才生效，不會改變進行中的模型請求；若在生效前切換了模型，請為新模型重新開啟選擇器。
  - 對於 `thinking.type` 設為 `between_tools` 的 Anthropic 模型，可用層級為該模型所支援的 `low`、`medium`、`high` 子集。
- **選擇摘要壓縮模型（Summarization model）**：
  - 用於自動上下文壓縮（automatic context compaction）、`/offload` 與 `/compact`，不影響主代理模型。
  - 啟動旗標：`dcode --summarization-model openai:gpt-5.6-sol`。
  - 互動指令：`/offload model`（開啟選擇器）、`/offload model openai:gpt-5.6-sol`（直接切換）、`/offload model clear`（恢復使用主代理模型）。
  - 解析順序：`--summarization-model` → `config.toml` 的 `[models].summarization_default` → 主代理模型。
- **模型參數與 Profile 覆寫**：
  - `--model-params JSON`：傳入額外建構子 kwargs（JSON 字串），僅在當前工作階段生效並覆寫 `config.toml` 的供應商參數，例如：`dcode --model openai:gpt-6.1-sol --model-params '{"reasoning": {"effort": "high"}}'` 或 `dcode --model anthropic:claude-opus-4-8 --model-params '{"thinking": {"type": "enabled", "budget_tokens": 10000}, "max_tokens": 16000}'`。
  - `--profile-override JSON`：覆寫 model profile 欄位（例如 `'{"max_input_tokens": 4096}'`），會合併在設定檔 profile 覆寫之上，並在工作階段中途透過 `/model` 熱切換時持續保留。
  - `--max-retries N`：覆寫暫時性模型錯誤後的重試次數，預設為 `5`，設為 `0` 可停用重試（亦可於 `config.toml` 的 `[retries]` 區段設定）。

### 互動模式（Interactive Mode）：斜線指令（Slash Commands）完整清單
- `/model`：切換模型或開啟互動式模型選擇器（在選擇器內按 `Ctrl+S` 可釘選預設模型）。
- `/effort`：設定當前模型的推理強度（reasoning effort），支援 `/effort <level>` 與 `/effort clear`。
- `/agents`：無需重新啟動即可在預先設定的代理之間熱切換（hot-swap）。
- `/auth`：管理模型供應商與外部服務（如 Tavily 網頁搜尋、LangSmith）的儲存 API 金鑰與憑證。
- `/goal <objective>`：根據可衡量的目標起草驗收標準（acceptance criteria）。
- `/rubric`：設定明確的評分驗收標準（grading acceptance criteria）。
- `/remember [context]`：檢視對話並更新記憶（memory）與技能（skills），可選擇性傳入額外背景脈絡。
- `/skill:<name> [args]`：在工作階段中途直接依名稱呼叫技能；代理伺服器會在第一次模型呼叫前解析該技能並載入其 `SKILL.md` 指示。
- `/skill-creator [task]`：建立有效代理技能的引導工具。
- `/offload`（別名 `/compact`）：將舊訊息卸載至儲存空間並以摘要佔位符取代，以釋放上下文視窗空間；需要時代理可從卸載檔案取回完整歷史。支援子指令 `/offload model [MODEL|clear]`。
- `/context`：開啟彩色編碼的上下文視窗使用量報告（顯示模型上限、已用 token、剩餘空間，以及對話與系統提示詞加工具之間的佔比；區分供應商回報總數與本地對話估算值）。
- `/context-doctor`：稽核注入工作階段的上下文及其預估 token 成本（拆解為 `System prompt (base)`、`AGENTS.md memory`、`Skills index`、`Built-in tool schemas`、各 `MCP` 伺服器工具 schema、`TOTAL injected before conversation`、`Conversation history`、`Provider-reported context` 與 `Unattributed / estimation delta`，約以每 4 個字元估算 1 個 token）。
- `/tools`：列出當前代理可呼叫的內建工具（如 `read_file`、`write_file`、`execute`、`web_search`、`task`）與各 MCP 伺服器的工具；不可用的 MCP 伺服器（如 `needs login`）會列於獨立表格。
- `/extensions`：列出已載入的 Python 擴充套件（Python extensions）註冊項目（含 kind、name、scope、source path、載入錯誤，以及圖綁定變更是否需要 `/restart`）。需設定 `DEEPAGENTS_CODE_EXPERIMENTAL=1`。
- `/cost`：顯示當前執行緒的預估花費（美元 USD），依類型（Assistant、Subagents，並涵蓋 offloading、Auto classification、rubric grading）與模型統計，跨恢復或切換執行緒時持續保留，價格採用 `genai-prices` 目錄（未涵蓋模型可新增自訂價格覆寫）。相同數字也會顯示於狀態列。
- `/btw [question]`：在不中斷主任務的情況下詢問關於當前對話的旁支問題（side question）；回答顯示於暫時對話框而非主對話中，按 `Esc` 關閉。
- `/tokens`：在對話紀錄中顯示當前上下文視窗的純文字 token 使用明細。
- `/clear`：開啟全新的對話執行緒（fresh thread）。
- `/force-clear`：以全新執行緒復原卡住的工作階段（stuck session）。
- `/copy`：將最新一則助理解析訊息複製到剪貼簿。
- `/prompts`：搜尋、預覽、複製並重用先前提交過的提示詞。
- `/rename [name]`：為當前執行緒命名（傳入 `<name>` 可設定 1 至 50 個可列印字元的名稱；省略名稱則由 LLM 產生可編輯的建議名稱）。
- `/threads`：瀏覽並恢復先前的對話執行緒。
- `/mcp [login <server> | reconnect]`：顯示作用中的 MCP 伺服器與工具；`login <server>` 為指定伺服器執行 OAuth 流程，`reconnect` 載入延遲登入（deferred logins）。
- `/plugins`：管理外掛程式與市集（plugins and marketplaces）。
- `/notifications`：設定啟動警告偏好。
- `/reload`：在不重啟的情況下重新讀取 `.env` 檔案、重新整理設定、重新探索技能（含外掛技能）與重新載入 MCP 設定，同時保留對話狀態。
- `/theme`：開啟互動式佈景主題選擇器以切換配色主題（包含內建主題與使用者自訂主題）。
- `/scrollbar`：顯示或隱藏聊天捲軸。
- `/line-numbers`：在新 diff 中顯示或隱藏檔案相對行號。
- `/update`：在工作階段內檢查並安裝 Deep Agents Code 更新（自動偵測 `uv`、Homebrew、`pip` 安裝方式並執行對應升級指令）。
- `/auto-update`：切換自動更新開關。
- `/install`：安裝選用的整合擴充套件（optional integration）。
- `/uninstall <name>`：在工作階段內移除已安裝的選用擴充套件。
- `/trace`：印出當前執行緒的 LangSmith 追蹤 URL 並在瀏覽器中開啟。
- `/editor`：在外部編輯器（依序檢查 `$VISUAL` → `$EDITOR` → macOS/Linux 預設 `vi` 或 Windows 預設 `notepad`）中開啟當前提示詞；GUI 編輯器（VS Code、Cursor、Zed 等）會自動注入 `--wait` 旗標。
- `/restart`：重新啟動代理伺服器（agent server）。
- `/timestamps`：切換訊息時間戳記頁尾（timestamp footers）。
- `/changelog`：在瀏覽器中開啟 Deep Agents Code 更新日誌。
- `/docs`：在瀏覽器中開啟官方文件。
- `/feedback`：傳送意見回饋或回報問題。
- `/version`（別名 `/about`）：顯示已安裝的 `deepagents-code` 與 SDK 版本。
- `/help`：顯示說明與可用指令。
- `/quit`：結束並退出 Deep Agents Code。

### 互動模式：Shell 模式、快捷鍵與特殊語法
- **Shell 指令模式**：在輸入框輸入 `!` 即可進入 shell 模式並直接執行命令（例如 `git status`、`npm test`、`ls -la`）。
- **一般鍵盤快捷鍵**：
  - `Enter`：提交提示詞。
  - `Shift+Enter`、`Ctrl+J`、`Alt+Enter` 或 `Ctrl+Enter`：插入換行。
  - `@filename`：自動補全檔案名稱並將檔案內容注入提示詞。
  - `@@query`：依初始提示詞、執行緒 ID、代理、分支或工作目錄搜尋近期執行緒，選擇後插入 `@@(thread:<thread-id>)` 引用供代理檢視。開啟建議時按 `Ctrl+R` 可在完整執行緒選擇器中以相同條件瀏覽所有執行緒；在完整選擇器中按 `Ctrl+C` 可複製所選執行緒 ID。
  - `Shift+Tab`：循環切換核准模式（Approval modes，在互動模式中於 Manual 與 Auto 之間切換）。
  - `Ctrl+G`：在外部編輯器開啟當前提示詞（等同 `/editor`）。
  - `Ctrl+T`：當存在子代理面板（subagent panel）時展開或收合該面板。
  - `Ctrl+N`：當通知面板開啟時檢視待處理通知。
  - `Ctrl+O`：展開或收合最近一次的工具輸出（或重新展開已收合的推理過程列）。
  - `Ctrl+R`：開啟本機儲存提示詞歷史的行內搜尋（inline prompt history search）。
  - `Escape`：中斷當前操作（或關閉 `/btw` 暫時對話框）。
  - `Ctrl+C`：中斷或退出。
  - `Ctrl+D`：退出。
- **提示詞文字編輯快捷鍵（Readline 風格）**：
  - `Ctrl+A` 或 `Home`：游標移至行首。
  - `Ctrl+E` 或 `End`：游標移至行尾。
  - `Ctrl+U`：刪除游標處至行首的文字。
  - `Ctrl+K`：刪除游標處至行尾的文字。
  - `Ctrl+W` 或 `Ctrl+Backspace`：向左刪除一個單字。
  - `Ctrl+Left` / `Ctrl+Right`（或 macOS `Option+Left` / `Option+Right` 傳送 `Esc+b` / `Esc+f`）：游標向左／向右移動一個單字。
  - **macOS 終端機 `Cmd` 鍵映射注意事項**：Ghostty 預設會將 `Cmd+Left`、`Cmd+Right`、`Cmd+Delete` 轉為 `Ctrl+A`、`Ctrl+E`、`Ctrl+U`；iTerm2 需手動在 `Settings > Profiles > Keys > Key Mappings` 設定 `Send Text with vim special chars` 為 `\x01`、`\x05`、`\x15`；Terminal.app 無內建映射介面，請直接使用 `Ctrl` 快捷鍵。

### 非互動模式（Non-Interactive Mode）與管線輸入（Piping）
- **觸發方式**：
  - 使用 `-n` / `--non-interactive TEXT` 執行單一任務後退出（每次執行皆開啟全新執行緒，不跨次保留對話歷史，但記憶、技能與設定檔等檔案狀態會持久保留）。
  - 透過 stdin 管線輸入（如 `echo "Explain this code" | dcode` 或 `git diff | dcode --skill code-review -n 'summarize changes'`）時會自動進入非互動模式；亦可傳入 `--stdin` 明確指定由 stdin 讀取（若 stdin 不可用或為 TTY 會明確報錯）。
  - 當管線輸入與 `-n` 或 `-m` 結合時，管線內容會排在前面，接著才是旗標傳入的文字。
  - **管線輸入大小上限**：最大 `10 MiB`。
- **輸出控制與推理顯示**：
  - `-q` / `--quiet`：僅將代理的最終回應輸出至 stdout（適合導向檔案或串接其他指令，需搭配 `-n` 或管線 stdin）。
  - `--no-stream`：緩衝完整回應後一次寫入 stdout，而非串流輸出（需搭配 `-n` 或管線 stdin）。
  - **供應商可見推理（Provider-visible reasoning）**：互動模式預設顯示（串流至獨立列並在階段結束時收合，可按 `Ctrl+O` 展開）；非互動模式預設隱藏（若啟用則輸出至 stderr，使 stdout 保持可管線化）。可設環境變數 `DEEPAGENTS_CODE_SHOW_REASONING=0` 在兩種模式皆隱藏，或傳入 `--show-reasoning` 在單次啟動強制顯示。
- **回合數與時間上限（CI/CD 保護）**：
  - `--max-turns N`：限制非互動模式的代理回合數上限（`N` 必須為正整數）。超過預算時以結束代碼 **`124`**（與 GNU `timeout` 相同）退出；若未搭配 `-n` 或管線 stdin 則以結束代碼 **`2`** 退出。
  - `--timeout SECONDS`：限制非互動模式的硬性牆上時鐘（wall-clock）秒數上限。與 `--max-turns` 同時使用時，先達到的限制會取消代理並以結束代碼 **`124`** 退出；若未搭配 `-n` 或管線 stdin 則以結束代碼 **`2`** 退出。
  - `--recursion-limit N`：設定 LangGraph 圖步驟預算（每回合最大節點呼叫次數）；未設定時套用 LangSmith Agent Server 預設值。
- **啟動指令（Startup command）**：
  - `--startup-cmd CMD`：在啟動時、第一個提示詞提交前執行的 shell 指令（可搭配互動模式 `-m` 或非互動模式 `-n`）。
  - 輸出會顯示在紀錄（transcript）供使用者參考，但**不會**加入代理的訊息歷史中（若要將指令輸出交給代理，請改用 stdin 管線）。
  - 非零結束代碼與逾時僅會發出警告而不會中止工作階段；非互動模式對 `--startup-cmd` 套用 **60 秒**逾時限制。

### 檔案系統工具限制與 Shell 許可清單
- **`--allow-fs-tools LIST`**：限制暴露給主代理與同步子代理（synchronous subagents）的檔案系統工具子集（預設為 `all`；不影響非同步子代理或非檔案系統工具）。
  - 有效工具名稱：`ls`、`read_file`、`write_file`、`edit_file`、`delete`、`glob`、`grep`、`execute`。
  - 明確指定清單時**必須包含 `read_file`**。
- **`-S` / `--shell-allow-list LIST`**（或環境變數 `DEEPAGENTS_CODE_SHELL_ALLOW_LIST`）：控制透過 `execute` 工具允許執行的 shell 指令，同時適用於互動與非互動模式（非互動模式預設停用 shell 執行）。可傳入逗號分隔指令清單（如 `"pytest,git,make"`）、`recommended`（安全的唯讀預設清單）或 `all`（允許任意指令，無人工確認）。
- **`--allow-fs-tools` 與 `-S` 的交互關係**：
  - `--allow-fs-tools` 包含 `execute` 且設定 `-S`：允許的指令可執行（互動模式會確認，非互動模式自動核准）。
  - `--allow-fs-tools` 包含 `execute` 但未設定 `-S`：`execute` 工具存在，但無預先核准的指令。
  - `--allow-fs-tools` 不含 `execute`（無論 `-S` 是否設定）：無任何 shell 存取權（因 `execute` 工具不存在）。

### 命令行旗標（Command-Line Options）完整速查表
- `-a`, `--agent NAME`：使用具獨立記憶、技能與 `~/.deepagents/<agent_name>/AGENTS.md` 的具名代理。覆寫 `config.toml` 的 `[agents].recent` 與 `[agents].default`。預設值：`agent`（若設有 `[agents].recent` 則為最近使用的代理）。
- `-M`, `--model MODEL`：指定模型（`provider:model`）。
- `--summarization-model MODEL`：指定上下文壓縮摘要模型，覆寫 `[models].summarization_default`，預設為主代理模型。
- `--model-params JSON`：以 JSON 字串傳入額外模型建構參數。
- `--max-retries N`：覆寫暫時性模型錯誤重試次數（預設 `5`，`0` 為停用）。
- `--default-model [MODEL]`：設定預設模型（省略 `MODEL` 則檢視當前預設值）。
- `--clear-default-model`：清除預設模型。
- `-r`, `--resume [ID]`：恢復對話工作階段（不帶 ID 恢復最近一次執行緒，帶 `<ID>` 恢復指定執行緒；會略過代理選擇旗標並還原該執行緒原本的代理）。
- `-m`, `--message TEXT`：互動模式啟動時自動提交的初始提示詞。
- `--skill NAME`：啟動時立即呼叫指定技能（搭配 `--quiet` 或 `--no-stream` 時必須同時使用 `-n`）。
- `--startup-cmd CMD`：啟動時在首個提示詞前執行的 shell 指令（非互動模式逾時 60 秒）。
- `--rubric TEXT|@PATH`：傳入評分驗收標準文字或 `@path` 檔案路徑（需搭配 `-n` 或管線 stdin）。
- `--rubric-model MODEL`：指定 rubric 評分器使用的模型，預設為主代理模型（需搭配 `-n` 或管線 stdin）。
- `--rubric-max-iterations N`：每次 rubric 嘗試的評分迭代上限（需搭配 `-n` 或管線 stdin）。
- `-n`, `--non-interactive TEXT`：非互動模式執行單一任務並退出。
- `--recursion-limit N`：設定每回合 LangGraph 最大節點呼叫次數。
- `--max-turns N`：非互動模式最大代理回合數（超限退出碼 `124`，未搭配 `-n`/stdin 退出碼 `2`）。
- `--timeout SECONDS`：非互動模式硬性秒數上限（超限退出碼 `124`，未搭配 `-n`/stdin 退出碼 `2`）。
- `-q`, `--quiet`：純淨輸出，僅將回應寫入 stdout（需搭配 `-n` 或管線 stdin）。
- `--no-stream`：緩衝完整回應後一次寫入 stdout（需搭配 `-n` 或管線 stdin）。
- `--show-reasoning`：顯示供應商可見推理（互動模式顯示於紀錄，非互動模式輸出至 stderr）。
- `--stdin`：明確從 stdin 讀取輸入。
- `-y`, `--auto-approve`：啟用分類器驅動的 Auto 核准模式（僅限互動式本機工作階段）。
- `--auto-classifier-model MODEL`：指定 Auto 分類器審查受控工具呼叫所使用的模型（`provider:model`），覆寫 `DEEPAGENTS_CODE_AUTO_CLASSIFIER_MODEL` 與 `config.toml` 的 `[models].auto_classifier`（僅限互動式 TUI）。
- `--yolo`：在單次本機風險確認後，不經審查直接執行受控動作（僅限互動模式）。
- `-S`, `--shell-allow-list LIST`：設定自動核准的 shell 指令清單、`recommended` 或 `all`。
- `--allow-fs-tools LIST`：限制暴露的檔案系統工具清單（預設 `all`）。
- `--json`：讓支援的管理子指令輸出機器可讀的 JSON，外層格式固定為 `{"schema_version": 1, "command": "...", "data": ...}`。
- `--sandbox [TYPE]`：指定遠端沙盒類型：`none`（預設）、`langsmith`、`agentcore`、`daytona`、`modal`、`runloop`、`vercel` 或第三方供應商。不帶值傳入 `--sandbox` 時使用 `config.toml` 的 `[sandboxes].default`（裸旗標請放在命令列最後，以免吞掉下一個參數）。
- `--sandbox-id ID`：重用既有沙盒（略過建立與清理）。
- `--sandbox-snapshot-name NAME`：使用或建立指定的沙盒快照名稱（支援 `langsmith`、`daytona`、`runloop` 及宣告支援快照的供應商）。
- `--sandbox-setup PATH`：沙盒建立後執行的設定腳本路徑。
- `--mcp-config PATH`：新增最高優先順序的明確 MCP 設定檔（與自動探索設定合併；與 `--no-mcp` 互斥）。
- `--no-tracing`：停用本次工作階段的 LangSmith 代理追蹤。
- `--no-mcp`：完全停用 MCP 工具載入（與 `--mcp-config` 互斥）。
- `--trust-project-mcp`：在本次執行中直接信任專案級 MCP 伺服器而不提示（但被使用者策略明確拒絕的伺服器仍維持停用）。
- `-e`, `--extension PATH`：為本次執行載入 Python 擴充套件檔案或目錄（可重複指定多次；需 `DEEPAGENTS_CODE_EXPERIMENTAL=1` 且啟用擴充探索 `[extensions].enabled` / `DEEPAGENTS_CODE_EXTENSIONS`）。
- `--trust-project-extensions`：在本次執行中信任專案級 `.deepagents/extensions/` Python 擴充套件（需 `DEEPAGENTS_CODE_EXPERIMENTAL=1`）。
- `--interpreter`：當設定檔停用 JS 直譯器（`js_eval`）中介軟體時，在主代理上強制啟用（`js_eval` 預設為啟用）。
- `--interpreter-tools VALUE`：設定 `js_eval` 的程式化工具呼叫（PTC）許可清單：`safe`（預設，唯讀的 `read_file`/`glob`/`grep` 預設集）、`all` 或逗號分隔工具名稱。
- `--profile-override JSON`：以 JSON 字串覆寫模型 profile 欄位。
- `--acp`：以 stdio 上的 ACP 伺服器模式執行，不啟動互動式 UI。
- `--update`：檢查並安裝更新後退出。
- `--auto-update`：切換自動更新開關後退出。
- `--install NAME`：安裝選用 extra（或搭配 `--package`、`--yes`）後退出。
- `--uninstall NAME`：移除選用 extra 後退出（`dcode uninstall NAME` 的別名）。
- `-v`, `--version`：顯示版本。
- `-h`, `--help`：顯示說明。

### CLI 管理子指令（CLI Management Subcommands）
所有管理子指令皆支援 `--json`；具破壞性的子指令（`agents reset`、`skills delete`、`threads delete`）皆支援 `--dry-run`（JSON 模式下回傳包含 `dry_run: true` 的相同外層結構）：
- **說明與診斷**：
  - `dcode help`：顯示說明。
  - `dcode doctor`：不啟動工作階段直接執行診斷，摘要安裝方式、相依套件版本、更新狀態、追蹤設定與資料目錄健康狀態。
  - `dcode update`：檢查並安裝 Deep Agents Code 更新。
  - `dcode uninstall NAME`：移除單一已安裝的選用 extra。
- **工具與代理管理**：
  - `dcode tools list [--json]`：列出已設定代理可用的工具（頂層工具塑形旗標如 `--allow-fs-tools`、`--no-mcp`、`--mcp-config`、`--trust-project-mcp` 必須放在 `tools list` 之前）。
  - `dcode agents list`（別名 `ls`）：列出所有代理。
  - `dcode agents reset --agent NAME [--target SOURCE] [--dry-run]`：清除代理記憶並重設為預設值，或透過 `--target SOURCE` 從另一個代理複製記憶。
- **技能管理（Skills）**：
  - `dcode skills list [--project]`（別名 `ls`）：列出所有技能。
  - `dcode skills create NAME [--project]`：建立含範本 `SKILL.md` 的新技能（具冪等性 idempotent，重複建立既有技能僅印出提示訊息而不報錯）。
  - `dcode skills info NAME [--project]`：顯示技能詳細資訊。
  - `dcode skills delete NAME [--project] [-f] [--dry-run]`：刪除技能及其內容。
- **執行緒管理（Threads）**：
  - `dcode threads list [--agent NAME] [--limit N]`（別名 `ls`）：列出工作階段（含執行緒名稱，自動命名由首次模型呼叫後的獨立 LLM 呼叫產生，受 `[threads].rename_model` 與 `[threads].auto_rename` 控制）。預設上限 `100`（可由環境變數 `DEEPAGENTS_CODE_RECENT_THREADS` 修改預設值，或用短旗標 `-n` 代表 `--limit`）。支援附加旗標：`--sort {created,updated}`、`--branch TEXT`、`--cwd [PATH]`（裸旗標使用當前目錄）、`-v`/`--verbose`（顯示所有欄位含分支、建立時間與初始提示詞）、`-r`/`--relative`（相對時間戳記）。
  - `dcode threads delete ID [--dry-run]`：刪除指定工作階段。
- **MCP 管理**：
  - `dcode mcp login [NAME] [--mcp-config PATH]`：對標記為 `auth: "oauth"` 的伺服器執行 OAuth 登入流程；省略 `NAME` 則列出需要登入的 OAuth 伺服器。
  - `dcode mcp config`：顯示 MCP 設定檔探索路徑。
- **設定檔檢視（`dcode config`）**：
  - `dcode config show`：顯示每個設定選項的有效值及其解析來源（供應商憑證僅顯示已設定或未設定，絕不印出金鑰內容）。
  - `dcode config list`（別名 `ls`）：列出所有可用設定選項及其型別、預設值與可設定位置。
  - `dcode config get KEY`：顯示單一選項的有效值與來源（例如 `dcode config get interpreter.memory_limit_mb`）。
  - `dcode config path`：顯示設定檔位置以及各檔案是否存在。
- **憑證管理（`dcode auth`）**：讀寫與 `/auth` 相同的 `auth.json` 儲存區：
  - `dcode auth list`：列出已知供應商及各憑證的解析來源。
  - `dcode auth status <provider>`：顯示單一供應商的憑證來源。
  - `dcode auth set <provider> [--from-env ENV_VAR]`：由 stdin 管線（如 `echo "$ANTHROPIC_API_KEY" | dcode auth set anthropic`）或 `--from-env` 儲存供應商 API 金鑰（為避免金鑰寫入 shell 歷史，若在互動終端機中既未管線輸入也未加 `--from-env` 會拒絕執行；不支援使用瀏覽器登入的 `openai_codex`）。
  - `dcode auth remove <provider>`：移除已儲存的供應商憑證。
  - `dcode auth path`：顯示憑證儲存區路徑。

### LangSmith 追蹤（Tracing）設定與分流
- **啟用與設定**：可透過 `/auth` 加入 LangSmith API 金鑰（下次啟動生效），或在 `~/.deepagents/.env` 設定：
  - `LANGSMITH_TRACING=true`
  - `LANGSMITH_API_KEY=lsv2_...`
  - `DEEPAGENTS_CODE_LANGSMITH_PROJECT="<coding-agent-tracer-session-name>"`（設定為 coding agent environment 的 `tracer_session_name`）。
- **停用代理追蹤**：單次啟動傳入 `dcode --no-tracing`，或永久設定 `DEEPAGENTS_CODE_LANGSMITH_TRACING=false`（會覆寫 `LANGSMITH_TRACING=true` 等其他啟用設定；shell 匯出優先於 `.env`）。
- **區分編碼代理追蹤（Agent traces）與 Shell 指令追蹤（Shell-command traces）**：
  - `DEEPAGENTS_CODE_LANGSMITH_PROJECT`（及 `DEEPAGENTS_CODE_LANGSMITH_API_KEY`）專屬於 Deep Agents Code 本身的模型呼叫、工具呼叫、編排與中介軟體追蹤。
  - 專案目錄 `.env` 中的 `LANGSMITH_PROJECT` 則控制代理在 shell 中執行的測試、腳本或本地 LangGraph 代理所發出的追蹤。
- **複製追蹤至第二個環境（Replica）**：設定 `DEEPAGENTS_CODE_LANGSMITH_REPLICA_PROJECTS="<replica-tracer-session-name>"`，啟用追蹤時每次執行會同時寫入主要目的地與 replica 目的地（例如個人工作區與團隊共享工作區）。

## 相關頁面
- [[guides/deepagents-code-configuration-and-providers]]
- [[concepts/deepagents-code-approval-and-hooks]]
- [[concepts/deepagents-code-extensibility]]

## 出處
- docs/deepagents/code/overview.md
- docs/deepagents/code/quickstart.md
- docs/deepagents/code/cli-reference.md
- docs/deepagents/code/changelog.md
