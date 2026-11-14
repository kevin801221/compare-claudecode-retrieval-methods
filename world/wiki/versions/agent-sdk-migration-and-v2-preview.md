# Agent SDK Migration Guide and TypeScript V2 Session API

別名：SDK 遷移指南、V2 Session API、Claude Code SDK 改名、v0.1.0 破壞性變更、Migration Guide、TypeScript V2 Preview、unstable_v2_createSession
框架：agent-sdk

## 摘要
原名「Claude Code SDK」的開發套件已正式更名為 **Claude Agent SDK**（套件名稱分別改為 `@anthropic-ai/claude-agent-sdk` 與 `claude-agent-sdk`），並在 `v0.1.0` 引入破壞性變更（包含將 Python 的 `ClaudeCodeOptions` 更名為 `ClaudeAgentOptions`，以及預設不再自動套用 Claude Code 的系統提示詞）。此外，本頁收錄了 TypeScript SDK 曾於 `0.2.x` 推出、並於 `0.3.142` 移除的實驗性 V2 Session API（`unstable_v2_createSession`、`unstable_v2_resumeSession`、`unstable_v2_prompt`）之完整參考與向 V1 `query()` 遷移的方式。

## 重點

### 從 Claude Code SDK 遷移至 Claude Agent SDK（`migration-guide.md`）
- **套件與文件變更對照**：
  - **TypeScript / JavaScript 套件名稱**：從 `@anthropic-ai/claude-code` 改為 `@anthropic-ai/claude-agent-sdk`。
    - 遷移步驟：執行 `npm uninstall @anthropic-ai/claude-code` 與 `npm install @anthropic-ai/claude-agent-sdk`，更新所有 `import { query, tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk"`，並將 `package.json` 中的依賴與版本範圍更新（例如從 `"^0.0.42"` 更新至 `"^0.3.0"`）。
  - **Python 套件名稱與模組匯入**：套件從 `claude-code-sdk` 改為 `claude-agent-sdk`；匯入模組從 `claude_code_sdk` 改為 `claude_agent_sdk`。
    - 遷移步驟：執行 `pip uninstall -y claude-code-sdk`（若未安裝會顯示 `WARNING: Skipping claude-code-sdk as it is not installed.`）與 `pip install claude-agent-sdk`，並更新 `requirements.txt` 或 `pyproject.toml`。
  - 若是從 OpenAI Agents SDK 遷移，官方於 Claude Cookbook 提供專屬遷移教學（`claude-agent-sdk-04-migrating-from-openai-agents-sdk`）。

### `v0.1.0` 破壞性變更（Breaking Changes）
1. **Python 選項類別更名：`ClaudeCodeOptions` → `ClaudeAgentOptions`**
   - 舊版：`from claude_code_sdk import query, ClaudeCodeOptions`
   - 新版：`from claude_agent_sdk import query, ClaudeAgentOptions`
2. **預設不再使用 Claude Code 系統提示詞（System prompt no longer default）**
   - 舊版（`v0.0.x`）：預設使用 Claude Code 的完整系統提示詞。
   - 新版（`v0.1.0` 起）：預設改用極簡系統提示詞（Minimal system prompt）。
   - **恢復舊版行為的設定方式**：必須顯式指定 `"claude_code"` preset：
     - TypeScript：`options: { systemPrompt: { type: "preset", preset: "claude_code" } }`（或傳入自訂字串 `systemPrompt: "You are a helpful coding assistant"`）。
     - Python：`ClaudeAgentOptions(system_prompt={"type": "preset", "preset": "claude_code"})`（或傳入自訂字串 `system_prompt="You are a helpful coding assistant"`）。
3. **檔案系統設定來源預設值（`settingSources` / `setting_sources`）的變更與撤回**：
   - 歷史演進：在 `v0.1.0` 曾短暫改為預設不載入任何檔案系統設定，但隨後已撤回（Reverted），因此升級時無需修改即可維持載入行為。
   - **目前預設行為**：省略 `settingSources` 時會與 CLI 一致，載入 `user`、`project` 與 `local` 檔案系統設定（包含 `~/.claude/settings.json`、`.claude/settings.json`、`.claude/settings.local.json`、`CLAUDE.md` 檔案與自訂 commands）。
   - **環境隔離設定**：在 CI/CD、已部署應用、測試環境與多租戶系統中，若要隔離本機設定，應顯式傳入空陣列 `settingSources: []`（TypeScript）或 `setting_sources=[]`（Python）。
   - **Python 版本注意**：Python SDK `0.1.59` 及更早版本將空串列 `[]` 視為與省略選項相同，因此依賴 `setting_sources=[]` 前務必升級至 `0.1.59` 之後的版本。

### TypeScript SDK V2 Session API（已於 `0.3.142` 移除，`typescript-v2-preview.md`）
- **移除狀態與版本邊界**：
  - V2 Session API 已不再支援。**TypeScript Agent SDK `0.3.142`** 移除了 `unstable_v2_createSession`、`unstable_v2_resumeSession`、`unstable_v2_prompt` 函式，以及 `SDKSession` 與 `SDKSessionOptions` 型別。
  - 包含 V2 介面的最後一個版本分支為 **Agent SDK `0.2.x`**（套件版本號從 `0.2.x` 直接跳升至 `0.3.142`）。若維護舊有 V2 程式碼需鎖定版本：`npm install @anthropic-ai/claude-agent-sdk@0.2`。
  - **遷移至 V1 `query()` 的替代方案**：改用 `query()` API 與工作階段選項；多輪對話可傳入 `AsyncIterable<SDKUserMessage>` 或使用 `options.resume` / `options.continue`。
- **V2 設計理念與核心介面**：
  - V2 旨在消除 V1 多輪對話需要編寫 async generator（`async function*`）並協調 `yield` 時機的複雜度，將每個回合拆分為明確的 `send()`（發送訊息）與 `stream()`（串流接收回應）兩步驟。
- **V2 API 簽章與方法參考**：
  1. `unstable_v2_createSession(options: { model: string; ... }): SDKSession`：建立新的多輪對話工作階段。
  2. `unstable_v2_resumeSession(sessionId: string, options: { model: string; ... }): SDKSession`：依 `sessionId` 恢復既有工作階段（可從 `session.stream()` 產出的任一 `SDKMessage` 上的 `msg.session_id` 取得 ID）。
  3. `unstable_v2_prompt(prompt: string, options: { model: string; ... }): Promise<SDKResultMessage>`：單輪查詢（One-shot prompt）的便利函式，直接回傳 `SDKResultMessage`（如檢查 `result.subtype === "success"` 並讀取 `result.result`）。
  4. `SDKSession` 介面成員：
     - `readonly sessionId: string`
     - `send(message: string | SDKUserMessage): Promise<void>`
     - `stream(): AsyncGenerator<SDKMessage, void>`
     - `close(): void`
- **資源清理（Cleanup）**：
  - 自動清理（需 **TypeScript 5.2+** Explicit Resource Management）：使用 `await using session = unstable_v2_createSession({ model: "claude-opus-4-7" });`，離開區塊時自動關閉工作階段。
  - 手動清理：呼叫 `session.close()`。
- **V2 不支援的功能（需使用 V1 `query()` SDK）**：
  - 工作階段分叉（`forkSession` 選項）。
  - 部分進階串流輸入模式（Advanced streaming input patterns）。

## 相關頁面
- [[concepts/agent-sdk-sessions]]
- [[concepts/agent-sdk-streaming]]
- [[guides/agent-sdk-hosting-and-security]]

## 出處
- docs/agent-sdk/migration-guide.md
- docs/agent-sdk/typescript-v2-preview.md
