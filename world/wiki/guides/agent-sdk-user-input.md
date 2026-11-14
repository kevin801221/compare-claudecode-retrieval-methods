# Handling Approvals and User Input

別名：處理工具核准與使用者輸入、canUseTool、can_use_tool、AskUserQuestion、PermissionResultAllow、PermissionResultDeny、澄清問題
框架：agent-sdk

## 摘要
當 Claude 需要執行未預先核准的工具或透過 `AskUserQuestion` 工具向使用者提出澄清問題時，Agent SDK 會觸發 `canUseTool`（TypeScript）/ `can_use_tool`（Python）回呼並暫停執行，直到應用程式回傳允許（可附帶修改後的 `updatedInput` 或持久化規則 `updatedPermissions`）或拒絕決策。

## 重點
### `canUseTool` / `can_use_tool` 回呼機制 (`user-input.md`)
- **觸發時機**：
  1. **工具需要核准（Tool needs approval）**：Claude 嘗試呼叫未被權限規則或權限模式自動核准的工具（如 `"Bash"`、`"Write"`）。
  2. **Claude 提出澄清問題（Clarifying questions）**：Claude 呼叫 `"AskUserQuestion"` 工具（在 `plan` 模式下尤為常見）。
- **暫停與延遲（Defer）機制**：`canUseTool` 回呼可以無限期掛起，代理迴圈會保持暫停直到回呼回傳結果。若使用者回應時間可能超過處理程序適合維持執行的時間，應改為註冊回傳 `defer` 決策的 `PreToolUse` hook，讓處理程序得以結束並在稍後從持久化的工作階段接續（resume）。也可以搭配 `PermissionRequest` hook 在等待核准時發送外部通知（如 Slack、Email、推播）。
- **回呼函式簽章與三個參數**：
  - Python：`async def can_use_tool(tool_name: str, input_data: dict, context: ToolPermissionContext) -> PermissionResultAllow | PermissionResultDeny`（從 `claude_agent_sdk.types` 匯入型別）。
  - TypeScript：`CanUseTool = async (toolName, input, options) => Promise<PermissionResult>`。
  - **三個參數說明**：
    1. `toolName` / `tool_name`：工具名稱字串（如 `"Bash"`、`"Write"`、`"Edit"`、`"AskUserQuestion"`）。
    2. `input` / `input_data`：傳遞給工具的參數字典（例如 `Bash` 包含 `command`、`description`、`timeout`；`Write` 包含 `file_path`、`content`；`Edit` 包含 `file_path`、`old_string`、`new_string`；`Read` 包含 `file_path`、`offset`、`limit`）。
    3. `options`（TypeScript）/ `context`（Python，`ToolPermissionContext`）：包含選用的 `suggestions`（建議的 `PermissionUpdate` 陣列，用於避免重複詢問）與取消訊號（TypeScript 中 `signal` 為 `AbortSignal`；Python 中 signal 欄位保留供未來使用）。
- **Python 串流保持開啟之必要 Workaround**：在 Python SDK 中使用 `can_use_tool` 時，需將 `prompt` 作為 async generator（如 `prompt_stream()`）傳入，並在 `hooks` 中註冊一個針對 `"PreToolUse"` 的 dummy hook（例如 `HookMatcher(matcher=None, hooks=[dummy_hook])`，其中 `dummy_hook` 回傳 `{"continue_": True}`）以保持串流開啟供 `can_use_tool` 通訊。

### 回應工具請求的六種模式與回傳型別
- **允許（Allow）與拒絕（Deny）回傳格式**：
  - **Python Allow**：`PermissionResultAllow(updated_input=..., updated_permissions=...)`。
  - **TypeScript Allow**：`{ behavior: "allow", updatedInput: ..., updatedPermissions: ... }`。
  - **Python Deny**：`PermissionResultDeny(message="...")`。
  - **TypeScript Deny**：`{ behavior: "deny", message: "..." }`。
  - *歷史版本注意*：在 Claude Code **v2.1.207** 之前，若 allow 結果省略了 `updatedInput` / `updated_input`，Claude Code 會視為驗證錯誤並拒絕該工具呼叫。
- **六種回應策略**：
  1. **Approve（原樣核准）**：將原始 `input` / `input_data` 傳入 `updatedInput` / `updated_input`。
  2. **Approve with changes（修改輸入後核准）**：在 `updatedInput` / `updated_input` 傳入修改後的參數物件（例如將 `/tmp` 替換為 `/tmp/sandbox`），工具會以修改後的參數執行，且 Claude 不會被告知參數曾遭修改。
  3. **Approve and remember（核准並記住規則）**：從第三個參數的 `suggestions` 陣列中篩選出建議項目（例如篩選 `s.destination == "localSettings"`，會將規則寫入 `.claude/settings.local.json`），並透過 `updated_permissions`（Python，需 `claude-agent-sdk` **0.1.80**+）或 `updatedPermissions`（TypeScript）回傳。在 TypeScript 中，若 `options` 帶有 `suppressAlwaysAllowRule: true`（需 Agent SDK **v0.3.268**+，Python `context` 不含此欄位），應隱藏「永遠允許」選項。
  4. **Reject（直接拒絕）**：回傳 deny 並附上 `message` 說明原因。
  5. **Suggest alternative（拒絕並建議替代方案）**：在 deny 的 `message` 中提供具體替代指示（例如要求改用壓縮封存取代刪除檔案）。
  6. **Redirect entirely（完全轉向）**：透過 streaming input 直接發送全新指令以略過當前工具請求。

### 處理 `AskUserQuestion` 澄清問題
- **啟用與攔截**：
  - `AskUserQuestion` 預設可用；但若在 options 中明確指定了 `tools` 陣列（例如限制唯讀工具 `["Read", "Glob", "Grep", "AskUserQuestion"]`），**必須將 `"AskUserQuestion"` 加入 `tools` 陣列中**，否則 Claude 無法提問。
  - 在 `canUseTool` 中檢查 `toolName === "AskUserQuestion"` / `tool_name == "AskUserQuestion"`。
- **問題輸入結構（Question format）**：
  - `input.questions` 為包含 **1 到 4 個問題**的陣列，每個問題物件包含：
    - `question`：顯示給使用者的完整問題文字。
    - `header`：問題的簡短標籤（最長 **12 個字元**）。
    - `options`：包含 **2 到 4 個選項**的陣列，每個選項具有 `label` 與 `description`（TypeScript 另支援選用的 `preview`）。
    - `multiSelect`：布林值，為 `true` 時允許複選。
- **選項視覺預覽（Option previews，僅限 TypeScript）**：
  - 在 query options 設定 `toolConfig: { askUserQuestion: { previewFormat: "markdown" | "html" } }` 可讓 Claude 在適合視覺比較的選項上生成 `preview` 欄位（未設定時預設不生成，且在不需比較的選項上可能為 `undefined`）：
    - `"markdown"`：包含 ASCII art 與 fenced code blocks。
    - `"html"`：包含帶樣式的 `<div>` 片段（SDK 會在執行 callback 前拒絕含有 `<script>`、`</style>`/`<style>` 與 `<!DOCTYPE>` 的內容）。
- **回答回傳結構（Response format）**：
  - 回傳 Allow 結果，並在 `updatedInput` / `updated_input` 中包含：
    - `questions`：**必須原樣傳回原始的 `input.questions` 陣列**供工具處理。
    - `answers`：以每個問題的完整 `question` 文字為 key、使用者所選選項的 `label` 為 value 的字典。若為 `multiSelect` 複選題，value 可傳入字串陣列（如 `["Introduction", "Conclusion"]`）或以 `", "` 接合的字串（如 `"Introduction, Conclusion"`）；若支援自訂自由文字輸入（如「Other」選項），直接將使用者輸入的文字作為該題的 value（不要填入 `"Other"` 字樣）。
    - `response`（選用）：當 UI 允許使用者關閉問題卡片並輸入不針對特定題目的自由格式整體回覆時設定；設定後 Claude 會收到 `"The user responded: …"` 而非逐題答案清單。
- **限制（Limitations）**：
  - **Subagents 不支援**：透過 `Agent` 工具衍生的 subagents 目前無法使用 `AskUserQuestion`。
  - **數量上限**：每次 `AskUserQuestion` 呼叫支援 **1–4 個問題**，每個問題 **2–4 個選項**。

## 相關頁面
- [[concepts/agent-sdk-permissions]]
- [[concepts/agent-sdk-hooks]]
- [[entities/agent-sdk-custom-tools]]
- [[concepts/agent-sdk-agent-loop]]

## 出處
- docs/agent-sdk/user-input.md
