# Agent SDK Quickstart

別名：Agent SDK 快速開始、安裝與設定指南、Quickstart、基礎代理建置
框架：agent-sdk

## 摘要
本指南說明如何在 Python（使用 `uv` 或 `pip`）與 TypeScript（使用 `npm` 與 `tsx`）環境中安裝 Claude Agent SDK、設定 API 金鑰或雲端供應商認證，並透過 `query()` 函式建立一個能自動讀取程式碼、找出錯誤並修復檔案的自主 AI 代理。

## 重點
### 環境需求與安裝 (`quickstart.md`)
- **系統需求**：**Node.js 18.14+** 或 **Python 3.10+**，以及一個 Anthropic 帳號。
- **TypeScript 安裝步驟**：
  - 新專案：`npm init -y`、`npm pkg set type=module`（在 `package.json` 設定 `"type": "module"` 以支援頂層 `await`）、`npm install @anthropic-ai/claude-agent-sdk`、`npm install --save-dev tsx`。
  - 既有專案：若專案使用 CommonJS，可將腳本命名為 `agent.mts` 而非 `agent.ts`，讓 `tsx` 將其視為 ES module 以支援頂層 `await`，並使用 `npx tsx agent.mts` 執行。
- **Python 安裝步驟**：
  - 使用 `uv`：執行 `uv init` 與 `uv add claude-agent-sdk`，並以 `uv run agent.py` 執行。
  - 使用 `pip`：建立虛擬環境（macOS/Linux 為 `python3 -m venv .venv` 並 `source .venv/bin/activate`；Windows 為 `py -m venv .venv` 並 `.venv\Scripts\Activate.ps1`，若遇 PowerShell 執行原則阻擋可先執行 `Set-ExecutionPolicy -Scope Process RemoteSigned`），接著執行 `pip install claude-agent-sdk`。
- **內建 Claude Code 二進位檔（Bundled binary）注意事項**：
  - Python 與 TypeScript SDK 預設皆內建原生的 Claude Code binary，多數安裝無須另外安裝 Claude Code。
  - **例外情況 1（Python）**：若 `pip` 安裝的是原始碼發行版（source distribution）而非平台專屬 wheel（例如在 ARM64 Windows 上），則不會內建 binary。此時需原生安裝 Claude Code，Python SDK 會在 `PATH` 上尋找執行檔。
  - **例外情況 2（TypeScript）**：TypeScript SDK 透過 npm optional dependencies 安裝 binary；若安裝時略過選用相依套件（例如 `npm ci --omit=optional`），將不會取得 binary。需在不略過 optional dependencies 的情況下重新安裝，或原生安裝 Claude Code 並將 `pathToClaudeCodeExecutable` 設為其執行檔路徑。

### API 金鑰與第三方雲端供應商認證
- **標準 API Key 認證**：
  - 在執行代理的 shell 中設定環境變數 `ANTHROPIC_API_KEY`（macOS/Linux：`export ANTHROPIC_API_KEY=your-api-key`；Windows PowerShell：`$env:ANTHROPIC_API_KEY = "your-api-key"`）。
  - SDK 會從執行處理程序的環境變數讀取金鑰，**不會自動載入 `.env` 檔案**（若放在 `.env` 中，需在呼叫 SDK 前自行使用如 `dotenv` 套件載入）。若未正確設定，會出現 `Not logged in` 或 `Invalid API key` 等認證錯誤。
- **第三方 API 供應商環境變數**：
  - **Amazon Bedrock**：設定 `CLAUDE_CODE_USE_BEDROCK=1` 並設定 AWS 憑證。
  - **Claude Platform on AWS**：設定 `CLAUDE_CODE_USE_ANTHROPIC_AWS=1` 與 `ANTHROPIC_AWS_WORKSPACE_ID`，並設定 AWS 憑證。
  - **Google Cloud's Agent Platform (Vertex AI)**：設定 `CLAUDE_CODE_USE_VERTEX=1` 並設定 Google Cloud 憑證。
  - **Microsoft Foundry**：設定 `CLAUDE_CODE_USE_FOUNDRY=1` 並設定 Azure 憑證。
- **禁止提供 claude.ai 登入**：除非事先獲得核准，第三方開發者不得在基於 Claude Agent SDK 建構的產品中提供 `claude.ai` 登入或速率限制。

### 建構與執行基礎代理
- **核心入口函式 `query`**：
  - Python：從 `claude_agent_sdk` 匯入 `query`、`ClaudeAgentOptions`、`AssistantMessage`、`ResultMessage`，使用 `async for message in query(prompt=..., options=ClaudeAgentOptions(...)):` 迭代非同步訊息串流。
  - TypeScript：從 `@anthropic-ai/claude-agent-sdk` 匯入 `query`，使用 `for await (const message of query({ prompt: ..., options: { ... } }))` 迭代訊息串流。
- **常用 Options 組合範例**：
  - 預先核准工具與自動接受檔案編輯：Python 設定 `allowed_tools=["Read", "Edit", "Glob"]` 與 `permission_mode="acceptEdits"`；TypeScript 設定 `allowedTools: ["Read", "Edit", "Glob"]` 與 `permissionMode: "acceptEdits"`。
  - 加入網頁搜尋：在 `allowed_tools` / `allowedTools` 加入 `"WebSearch"`。
  - 加入終端機指令執行：在 `allowed_tools` / `allowedTools` 加入 `"Bash"`。
  - 自訂系統提示詞：設定 `system_prompt`（Python）或 `systemPrompt`（TypeScript）。
- **訊息過濾與輸出**：
  - 在 Python 中檢查 `isinstance(message, AssistantMessage)` 並走訪 `message.content`，若 `block` 具有 `"text"` 屬性則印出 `block.text`（推理文字），若具有 `"name"` 屬性則印出 `block.name`（呼叫的工具名稱）；當 `isinstance(message, ResultMessage)` 時印出 `message.subtype`（正常完成時為 `Done: success`）。
  - 在 TypeScript 中檢查 `message.type === "assistant"` 並走訪 `message.message.content`（檢查 `"text" in block` 或 `"name" in block`），以及檢查 `message.type === "result"` 印出 `message.subtype`。
- **工具組合與能力對照**：
  - 唯讀分析（Read-only analysis）：`Read`、`Glob`、`Grep`。
  - 分析並修改程式碼（Analyze and modify code）：`Read`、`Edit`、`Glob`。
  - 完整自動化（Full automation）：`Read`、`Edit`、`Bash`、`Glob`、`Grep`。
  - 若要將內建工具嚴格限制在上述集合內，應傳給 `tools` 參數；若傳給 `allowedTools` / `allowed_tools`，則是預先核准這些工具，代理仍可呼叫其他工具（受 `permissionMode` 規範）。

## 相關頁面
- [[concepts/claude-agent-sdk-overview]]
- [[concepts/agent-sdk-agent-loop]]
- [[concepts/agent-sdk-permissions]]

## 出處
- docs/agent-sdk/quickstart.md
