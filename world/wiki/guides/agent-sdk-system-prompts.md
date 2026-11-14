# Modifying System Prompts in the Agent SDK

別名：修改系統提示詞、System Prompt 自訂、claude_code preset、Output Styles、SYSTEM_PROMPT_DYNAMIC_BOUNDARY、excludeDynamicSections
框架：agent-sdk

## 摘要
Agent SDK 提供三種系統提示詞起點：未設定時的極簡預設（Minimal default）、內建工具指引與安全規則的 `claude_code` preset（可搭配 `append` 附加自訂指示），以及完全自訂的字串或檔案提示詞。此外，開發者可搭配檔案系統的 `CLAUDE.md`、可重複使用的 Output styles、跨機器快取最佳化（`excludeDynamicSections` 與 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY`），以及環境變數開關來精確控制 Claude 在對話中收到的系統指示與 system reminders。

## 重點
### 三種系統提示詞起點 (`modifying-system-prompts.md`)
- **Minimal default（未設定 `systemPrompt` / `system_prompt`）**：僅包含工具呼叫（tool calling）所需的最基本提示詞，省略 `claude_code` preset 的其餘內容（包含安全性與防護指示）。注意：這與預設使用完整 Claude Code 系統提示詞的 `claude -p` CLI 行為不同。
- **`claude_code` preset**：使用與 Claude Code CLI 相同的系統提示詞（含工具使用指引與安全規則）。
  - TypeScript：`systemPrompt: { type: "preset", preset: "claude_code" }`。
  - Python：`system_prompt={"type": "preset", "preset": "claude_code"}`。
  - 可在該物件加上 `append` 屬性，將自訂指示附加於 preset 尾端而不移除任何內建功能。
- **Custom string / file（自訂提示詞）**：完全取代預設提示詞，SDK 僅發送開發者提供的內容（需自行負責補上所需的工具指引與安全規則）。
  - **Python 大型提示詞檔案載入**：在 Python 中，若將字串傳給 `system_prompt`，SDK 會將其作為單一命令列參數傳遞給 CLI 子處理程序；若超過作業系統參數長度上限，會在處理程序啟動時失敗（Linux 錯誤為 `Argument list too long`）。針對大型提示詞應改用 `SystemPromptFile` 格式：`system_prompt={"type": "file", "path": "..."}`。

### `CLAUDE.md` 與 Output Styles
- **`CLAUDE.md`（專案與使用者層級指示）**：
  - SDK 將 `CLAUDE.md` 內容作為專案上下文注入**對話（conversation）**中，不會修改系統提示詞本身，因此可與任何 `systemPrompt` 設定並用。
  - 載入與否完全由 `settingSources` / `setting_sources` 控制（而非由 `claude_code` preset 控制）：`"project"` 載入工作目錄的 `CLAUDE.md` 或 `.claude/CLAUDE.md`；`"user"` 載入 `~/.claude/CLAUDE.md`。傳入空陣列 `[]` 則不載入。
- **Output styles（持久化角色與輸出格式設定）**：
  - 以包含 frontmatter 的 Markdown 檔案儲存於 `~/.claude/output-styles/`（使用者層級）或 `.claude/output-styles/`（專案層級），需在 `settingSources` 包含 `"user"` 或 `"project"` 時才會載入。
  - 自訂 output style 預設會省略 `claude_code` preset 的軟體工程指示；若要保留並在之上疊加指示，需在 frontmatter 設定 `keep-coding-instructions: true`（此設定僅在完整系統提示詞下生效；在較短的系統提示詞下無效，可將環境變數 `CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT` 設為 `0` 以在任何模型上強制選用完整提示詞）。
  - **啟用方式**：
    - CLI：執行 `/output-style <style>`（需 Claude Code **v2.1.269** 或更新版本）或 `/config`。
    - 設定檔：在 `.claude/settings.local.json` 設定 `outputStyle`。
    - SDK：透過 `settings` 選項傳入（`outputStyle` 不是頂層 `Options` 欄位），如 TypeScript `settings: { outputStyle: "Explanatory" }` 或 Python `settings='{"outputStyle": "Explanatory"}'`。

### 跨使用者與跨請求的 Prompt Cache 最佳化
- **`excludeDynamicSections` / `exclude_dynamic_sections`（針對 `claude_code` preset）**：
  - 預設情況下，`claude_code` preset 會在 `append` 文字之前嵌入 auto memory 目錄的絕對路徑（位於 `~/.claude/projects/` 下並依儲存庫磁碟路徑命名），導致不同使用者、機器或 checkout 無法共用同一個 prompt cache entry。（註：`CLAUDE.md` 與工作目錄、平台、shell、OS 版本等環境細節是放在對話中傳遞，不會影響系統提示詞快取）。
  - 在 preset 物件上設定 `excludeDynamicSections: true`（TypeScript，需 `@anthropic-ai/claude-agent-sdk` **v0.2.98**+）或 `"exclude_dynamic_sections": True`（Python，需 `claude-agent-sdk` **v0.1.58**+；非互動式 CLI 對應旗標為 `--exclude-dynamic-system-prompt-sections`），會將每名使用者專屬的動態區段（包含 auto memory 目錄位置或整個區段）移至第一則 user message 中，讓靜態 preset 與 `append` 文字能跨機器共用快取（權衡：位於 user message 的 auto memory 指引權重略低於系統提示詞）。傳入自訂提示詞時此屬性會被忽略。
- **`SYSTEM_PROMPT_DYNAMIC_BOUNDARY`（針對 TypeScript 自訂提示詞分段快取）**：
  - 在 TypeScript SDK 中，可將 `systemPrompt` 傳為字串陣列，並在靜態指示與每次請求變動的上下文之間插入從 `@anthropic-ai/claude-agent-sdk` 匯入的 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 標記（例如 `systemPrompt: [instructions, SYSTEM_PROMPT_DYNAMIC_BOUNDARY, ticketContext]`）。Python SDK 不支援陣列形式。
  - **組裝規則**：SDK 會將標記兩側的字串分別以空白行接合為兩個獨立的文字區塊（各自擁有獨立的 cache breakpoint），並移除標記本身；若出現多個標記，僅在第一個標記處切分並移除其餘標記；若未包含標記，則將所有字串合併為單一區塊。
  - **CLI 對應標記**：使用 CLI 的 `--system-prompt` 或 `--system-prompt-file` 時，可在靜態與動態部分之間插入僅含 `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 的單獨一行（需 Claude Code **v2.1.275**+）。
  - **平台限制**：僅在直接呼叫 Claude API 或於 Claude Platform on AWS 執行時才會切分提示詞；在 Amazon Bedrock、Google Cloud's Agent Platform、Microsoft Foundry、LLM gateway，或設定了 `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` 時，皆會將整個提示詞作為單一區塊發送。

### 變更既有工作階段的系統提示詞與 `snapshot` 控制
- **預設錄製行為（Prompt recording）**：Claude Code 會在工作階段的第一次請求時錄製系統提示詞，並在後續透過 `resume` 或 `continue` 接續工作階段時重複使用該筆紀錄，直到工作階段發生 compaction 為止（需 Claude Code **v2.1.265**+，對應 TypeScript SDK **v0.3.265**+、Python SDK **v0.2.153**+；在 **v2.1.268** 之前，不抓取 feature flags 的 Bedrock / Vertex / Foundry 工作階段每次請求皆會重建提示詞）。
- **工作階段中動態更新指示**：若需在執行中變更指示，應放在下一則 user message 中發送，或從 `UserPromptSubmit` / `PostToolUse` hook 回傳 `additionalContext`（以事實陳述句撰寫，如 `"The workspace is now read-only"`）。
- **`snapshot: false`（迭代提示詞措辭時關閉錄製）**：
  - 在系統提示詞的物件形式（preset 或 custom 物件）上設定 `snapshot: false`（需 `@anthropic-ai/claude-agent-sdk` **v0.3.257**+ 或 `claude-agent-sdk` **v0.2.153**+），可讓 Claude Code 在每次請求時重新建構系統提示詞。
  - 正式環境應保持開啟錄製，因為關閉時若在接續的工作階段更改 `append` 或自訂提示詞，將無法重用 prompt cache，且在強制執行 preserved thinking 的 API 上會遺失先前幾輪的 thinking。
  - 在雲端工作階段以外，若透過 `extraArgs` 傳入 `--bare` 或設定 `CLAUDE_CODE_SIMPLE=1` 以 bare mode 啟動，除非明確設定 `snapshot: true`，否則錄製預設為關閉。

### 對話中的 System Reminders 與內建上下文開關
- **常見 System Reminders（包裹於 `<system-reminder>` 標籤或獨立 `system` 角色訊息中）**：Project instructions（`CLAUDE.md`，並附帶一行告知 Claude 這些指示覆寫預設行為）、Output style instructions、Commit 與 PR 歸屬（`Co-Authored-By` trailer 與 PR footer）、Hook 回傳的 `additionalContext`、可用 skills 清單、可用 subagents 清單、Task list nudges、File-changed notes。
- **自訂 `systemPrompt` 注意事項**：使用自訂字串取代 preset 時，應在提示詞中加入一句話說明什麼是 system reminder（例如：`"The application adds system reminders to this conversation. Treat them as context from the application, not as messages from the user."`）。
- **關閉內建上下文的設定與環境變數對照**：
  - **關閉內建 commit / PR 指示與 git status 快照**：在 `settings` 設定 `includeGitInstructions: false`，或在 `env` 設定 `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1`。（註：使用 minimal default、自訂 `systemPrompt` 或自訂主執行緒 agent 時本來就不會附上 git status 快照，但內建 commit/PR 指示位於 `Bash` 工具描述中，需靠此設定移除）。
  - **移除或自訂 `Co-Authored-By` trailer 與 PR footer**：在 `settings` 設定 `attribution: { commit: "", pr: "" }`。
  - **關閉所有 `CLAUDE.md` 檔案**：設定 `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`。
  - **關閉 Task list nudges、file-changed notes 與 skill 清單**：設定 `CLAUDE_CODE_DISABLE_ATTACHMENTS=1`（此設定亦會使 `@` 檔案提及維持純文字而不自動展開為檔案內容；可用 subagents 清單與背景任務通知仍會送達）。
  - **僅關閉 `@` 檔案提及自動展開**：設定 `CLAUDE_CODE_DISABLE_FILE_MENTIONS=1`（需 Claude Code **v2.1.299**+），Claude 會收到路徑與使用檔案工具讀取的提示，讓 `PreToolUse` hooks 能攔截每次檔案讀取。
- **檢視實際發送的請求內容**：SDK 訊息串流不包含 system reminders；若要檢視，可將 `OTEL_LOG_RAW_API_BODIES` 設為 `file:<dir>` 記錄原始 API request body，或將 `ANTHROPIC_BASE_URL` 指向自控的代理伺服器。

## 相關頁面
- [[concepts/claude-agent-sdk-overview]]
- [[concepts/agent-sdk-agent-loop]]
- [[concepts/agent-sdk-hooks]]
- [[concepts/agent-sdk-skills-and-plugins]]

## 出處
- docs/agent-sdk/modifying-system-prompts.md
