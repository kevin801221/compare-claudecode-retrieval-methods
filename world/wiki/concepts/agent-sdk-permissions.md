# Agent SDK Permissions & Evaluation Order

別名：Agent SDK 權限管理、權限評估順序、Permission Modes、allowedTools、disallowedTools、bypassPermissions、acceptEdits、dontAsk
框架：agent-sdk

## 摘要
Claude Agent SDK 透過六階段權限評估流程（Hooks → Deny rules → Ask rules → Permission mode → Allow rules → `canUseTool` callback）控管所有工具呼叫。開發者可結合宣告式的 `allowedTools` / `disallowedTools`（及路徑規則）、六種全域 `permissionMode`（`default`、`dontAsk`、`acceptEdits`、`bypassPermissions`、`plan`、`auto`）與執行期回呼，精確定義哪些操作可自動放行、哪些必須阻擋或交由人工審核。

## 重點
### 六階段權限評估順序 (`permissions.md`)
當 Claude 請求呼叫工具時，Claude Code 嚴格依下列六個步驟評估：
1. **Hooks（步驟 1）**：
   - 執行註冊的 hooks。Hook 可直接拒絕（deny）呼叫或放行。
   - **注意**：即使 `PreToolUse` hook 回傳 `allow`，**仍不會跳過步驟 2（Deny rules）與步驟 3（Ask rules）**；且回傳 `allow` 無法核准目標被識別為關鍵路徑（critical path，如 `rm -rf ~`）的 `rm` 或 `rmdir` 指令。
2. **Deny rules（步驟 2）**：
   - 檢查 `disallowed_tools` / `disallowedTools` 或設定檔中的 deny 規則。一旦吻合即直接拒絕，不會呼叫 `canUseTool`，且**即使在 `bypassPermissions` 模式下或 hook 已回傳 `allow` 時依然強制拒絕**。
3. **Ask rules（步驟 3）**：
   - 檢查 `settings.json` 中的 `ask` 規則。若吻合，呼叫會直接轉交 `canUseTool` callback 確認（即使在 `bypassPermissions` 模式下亦同）。
   - **強制要求互動或審核的工具（即使有 allow 規則吻合或處於 `bypassPermissions` 模式，仍在此步驟轉交 `canUseTool`；若在 `dontAsk` 模式下則一律拒絕）**：
     - `AskUserQuestion` 以及伺服器端設定了 `_meta["anthropic/requiresUserInteraction"]` 的 MCP 工具（該 MCP 標註需 Claude Code **v2.1.199**+）。
     - 組織管理員設為 `ask` 的 `claude.ai` connector 工具（callback 會收到原因 `"Your organization requires approval for this tool"`）。
     - 在 TypeScript SDK 中將自訂工具的 `permission_policy` 設為 `always_ask` 時，任何 allow 規則（含 `allowedTools`）皆無法自動核准它；在 `dontAsk` 模式下會被拒絕，而在 `auto`、`plan` 或 `bypassPermissions` 模式下則可能於進入 callback 前被核准。
4. **Permission mode（步驟 4）**：套用目前生效的 `permissionMode` / `permission_mode`（詳見下方六種模式說明）。在 `default` 與 `dontAsk` 模式下，呼叫會繼續進入步驟 5。
5. **Allow rules（步驟 5）**：
   - 檢查 `allowed_tools` / `allowedTools` 與 `settings.json` 的 allow 規則，以及工具本身在 `default` 模式下無須核准即可執行的操作（如工作目錄內的檔案讀取、唯讀 Bash 指令、`Agent` 工具呼叫）。
   - **Allow 規則永遠無法核准的操作**：被識別出的關鍵路徑刪除（critical-path removals）、被標記為 `Dangerous rm operation not ruled out` 的指令（無法被 `Bash` 或 `Bash(*)` 規則核准，在 `auto` 模式下預設直接拒絕而不呼叫 callback），以及從網路路徑讀取檔案（network paths）。
6. **`canUseTool` callback（步驟 6）**：
   - 若前述步驟皆未做出最終決定，則呼叫 `canUseTool` callback。
   - 在 `dontAsk` 模式下會跳過此步驟並直接拒絕（除非已安裝的 plugin mod 核准了部分呼叫）。
   - 在 TypeScript SDK 中，若設定 `permissionPrompts: 'none'`（需 Claude Code **v2.1.259**+），此步驟不會呼叫 `canUseTool`；此時 `PermissionRequest` hook 仍有機會做出決定，否則 Claude Code 會直接拒絕該呼叫。

### `CLAUDE_SDK_CAN_USE_TOOL_SHADOWED` 警告（TypeScript）
- 當傳入 `canUseTool` callback 但設定會導致評估流程在進入 callback 前就自動核准呼叫時，TypeScript SDK 會在建構 query 時發出一次 Node.js process warning，代碼為 `CLAUDE_SDK_CAN_USE_TOOL_SHADOWED`（可透過 `process.on('warning', ...)` 監聽）：
  1. 設定了 `permissionMode: 'bypassPermissions'`（警告開頭為 `canUseTool will not be invoked: permissionMode 'bypassPermissions'`）。
  2. `allowedTools` 中包含純工具名稱項目（如 `"Read"`，警告會列出 `canUseTool will not be invoked for:`；帶有 specifier 如 `Bash(ls *)` 或設定為 `acceptEdits` 模式不會觸發此警告）。
- 若要檢查已被 allow 規則、`acceptEdits` 或 `bypassPermissions` 自動核准的呼叫，應將檢查邏輯放在 `PreToolUse` hook 中。

### Allow 與 Deny 規則語法與路徑樣式
- **`allowed_tools` / `allowedTools` 與 `disallowed_tools` / `disallowedTools` 差異**：
  - 將工具裸名（如 `"Bash"`）放入 `disallowed_tools` 會直接從請求中**移除該工具定義**；若放入帶範圍的規則（如 `"Bash(rm *)"`），`Bash` 工具仍存在，但符合 `rm *` 字面寫法的呼叫在所有模式下皆被拒絕（注意 `/bin/rm` 不符合 `rm *`）。
  - **萬用字元（Globs）規則**：
    - Deny 規則支援任意工具名稱 glob：`"*"` 匹配所有工具，`"mcp__*"` 匹配所有伺服器的 MCP 工具。
    - Allow 規則**僅支援在固定的 `mcp__<server>__` 前綴之後使用 glob**（server 區段不得含 glob），例如 `mcp__puppeteer__*` 或 `mcp__github__get_*`。未錨定特定伺服器的 `allowed_tools=["*"]` 或 `allowed_tools=["mcp__*"]` 會被忽略且不會自動核准任何工具。
  - **警告**：`allowed_tools` 僅負責預先核准列出的工具，**不會限制 `bypassPermissions` 模式的範圍**（在 `bypassPermissions` 下設定 `allowed_tools=["Read"]` 仍會自動核准 `Bash`、`Write`、`Edit`；若要封鎖特定工具必須使用 `disallowed_tools`）。
- **路徑規則（Path patterns）**：
  - `Edit(path)` 規則統管所有寫入檔案的內建工具（包含 `Edit`、`Write` 與 `NotebookEdit`）以及如 `tee` 與 `> file` 轉向等 Bash 寫入；若寫成 `Write(path)` 或 `NotebookEdit(path)` **將不會匹配任何呼叫且完全無效**。
  - **`//path`（雙斜線開頭）**：代表磁碟上的**絕對路徑**（例如 `Edit(//secrets/**)` 封鎖 `/secrets` 下的寫入）。
  - **`/path`（單斜線開頭）**：代表**工作目錄（working directory）內的相對路徑**（例如 `Edit(/secrets/**)` 匹配 `<cwd>/secrets/**`）。

### 六種 Permission Modes 詳解
在 Claude Code **v2.1.302** 或更新版本中，若未指定 `permissionMode` 且設定檔中無 `permissions.defaultMode`，工作階段預設以 `default` 模式啟動。可於啟動時設定，或在 streaming 期間呼叫 `set_permission_mode()` / `setPermissionMode()` 動態切換：
1. **`default`**：標準權限行為，無模式層級的自動核准；需要核准且未匹配 allow 規則的呼叫會進入 `canUseTool`（若未提供 callback 則拒絕）。
2. **`dontAsk`**：將所有會觸發提示的呼叫直接轉為拒絕（不呼叫 `canUseTool`）。即使匹配 allow 規則或 `PreToolUse` hook 回傳 `allow`，下列五類呼叫在 `dontAsk` 下仍一律被拒絕：組織設為 `ask` 的 connector 工具、需使用者互動的工具（`AskUserQuestion` 與標註 `_meta["anthropic/requiresUserInteraction"]` 的 MCP 工具）、標記為 `always_ask` 的自訂工具、從網路路徑讀取（network paths）、識別出的關鍵路徑刪除（critical-path removals）。
3. **`acceptEdits`**：在工作目錄及透過 `add_dirs` / `additionalDirectories` 加入的目錄內，自動核准 `Edit`、`Write`、`NotebookEdit` 檔案編輯，以及檔案系統指令 `mkdir`、`touch`、`rm`、`rmdir`、`mv`、`cp`、`sed`。但若目標在範圍外、寫入受保護路徑（protected path）、刪除關鍵路徑（critical path），或執行帶有選項/glob/`timeout 5`/`LANG=C` 前綴的 `touch`，則不會自動核准。
4. **`bypassPermissions`**：跳過權限提示自動核准工具呼叫（在 TypeScript SDK 中需同時設定 `allowDangerouslySkipPermissions: true`）。在 Linux 與 macOS 上，若在受認可的沙盒外以 `root` 或 `sudo` 執行，Claude Code 會在第一回合開始前拒絕啟動並失敗。Deny 規則、`ask` 規則、hooks，以及組織 `ask` connector 工具、使用者互動工具、關鍵路徑刪除、標記為 `Dangerous rm operation not ruled out` 的指令與（雲端工作階段外的）`always_ask` 自訂工具仍會攔截或進入 `canUseTool`（其中 `decisionReason` 以 `Dangerous rm` 開頭）。
5. **`plan`**：探索與規劃模式。以檔案工具對受保護路徑以外進行的編輯，**即使匹配 allow 規則或 `PreToolUse` hook 回傳 `allow`（或在 TypeScript 中設定了 `allowDangerouslySkipPermissions: true`），仍會強制送往 `canUseTool` callback**；`AskUserQuestion` 同樣強制進入 callback。
   - **規劃期間的 Auto mode 分類器審查（預設開啟）**：當 auto mode 可用時，未匹配 allow 規則的非唯讀 Shell 指令、非預審文件網域的 `WebFetch`、`WebSearch`，以及標記為唯讀的 MCP 工具呼叫，預設會送交 auto mode classifier 審查而非 `canUseTool`（唯讀 shell 指令如 `ls` 與預審文件網域的 `WebFetch` 則直接執行）。可在 `settings` 將 `useAutoModeDuringPlan` 設為 `false` 關閉審查，使這些呼叫回到 `canUseTool`。
   - 若之後想透過 `setPermissionMode()` 從 `plan` 切換至 `bypassPermissions`，TypeScript SDK 必須在啟動時就預先設好 `allowDangerouslySkipPermissions: true`。
6. **`auto`**：由模型分類器審查 shell 指令與網路請求等動作。若在工作階段執行期間透過 `set_model()`、`setModel()` 或 `applyFlagSettings()` 切換至不支援 auto mode 的模型（需 Claude Code **v2.1.299**+），工作階段會自動降級為 `"default"` 模式，並發出 `subtype: "status"` 且 `permissionMode: "default"` 的 `system` 訊息（TypeScript 型別為 `SDKStatusMessage`）。之後即使切回支援的模型，也必須再次明確呼叫 `set_permission_mode("auto")` / `setPermissionMode("auto")` 才會恢復 auto mode；若在不支援的模型下呼叫則會報錯 `Cannot set permission mode to auto: auto mode unavailable for this model`。

### Subagent 權限繼承規則
- 當主工作階段處於 `plan`、`acceptEdits`、`auto` 或 `bypassPermissions` 模式時，subagent 會繼承主工作階段的模式（特別是當主工作階段在 `plan` 模式時，即使 subagent 的 `AgentDefinition` 設定了 `permissionMode: "acceptEdits"`，該 subagent 仍強制在 `plan` 模式下執行，其 `Edit` 與 `Write` 呼叫仍會送交 `canUseTool`）。
- 唯有在主工作階段處於 `default` 或 `dontAsk` 模式時，subagent 才會套用其 `AgentDefinition` 上設定的 `permissionMode`；但即便如此，Claude Code **永遠不會套用 subagent 上設定的 `"bypassPermissions"` 值**（需 Claude Code **v2.1.267**+），且 `"auto"` 僅在對該 subagent 可用時才會套用。

## 相關頁面
- [[concepts/claude-agent-sdk-overview]]
- [[concepts/agent-sdk-agent-loop]]
- [[guides/agent-sdk-user-input]]
- [[concepts/agent-sdk-hooks]]
- [[concepts/agent-sdk-subagents]]

## 出處
- docs/agent-sdk/permissions.md
