# Human-in-the-Loop, Permissions, Hooks, and Middleware Comparison

別名：跨框架人工審批與權限及攔截器比較、HITL 比較、Permissions vs interrupt_on vs interrupt()、Hooks vs Middleware 比較
框架：agent-sdk、deepagents、langchain、langgraph

## 摘要
為了控制代理行為並攔截高風險操作，四個框架分別採用了「子程序 IPC 回呼與 Hook 管線（Claude Agent SDK）」與「基於圖檢查點的持久化中斷 `interrupt()` 與洋蔥式 Middleware（LangGraph / LangChain / Deep Agents）」兩大技術路線。本頁完整對照各框架的權限評估順序、人工審批（Human-in-the-Loop）API、輸入修改機制以及生命週期 Hook 與 Middleware 的差異。

## 重點

### 1. 人工審批（HITL）與權限控制跨框架對照
| 維度 | Claude Agent SDK (`agent-sdk`) | Deep Agents (`deepagents`) | LangChain (`langchain`) | LangGraph (`langgraph`) |
|---|---|---|---|---|
| **暫停與恢復機制** | 執行期記憶體內非同步回呼（`canUseTool` / `can_use_tool` 與 `PreToolUse` / `PermissionRequest` Hook），子程序保持連線等待回傳 | 基於 LangGraph Checkpointer 的持久化中斷（`interrupt_on`），程式可完全退出，待使用者決定後以 `Command(resume=...)` 恢復 | `HumanInTheLoopMiddleware`（設定 `interrupt_on`），底層使用 LangGraph 持久化中斷與 `Command(resume={"decisions": [...]})` | 底層 `interrupt(payload)` 函式與靜態斷點 `interrupt_before` / `interrupt_after`，以 `Command(resume=value)` 恢復 |
| **權限模式（Permission Modes）** | `default`、`acceptEdits`、`bypassPermissions`、`plan`、`dontAsk`、`auto`（僅 TS） | SDK：`interrupt_on` + `FilesystemPermission`；CLI：`Manual`、`Auto`（兩階段分類器）、`YOLO` | 依工具配置 `InterruptOnConfig`（`allowed_decisions`: `["approve", "edit", "reject"]`） | 由節點或工具內的 `interrupt()` 邏輯自行定義 |
| **審批決策類型** | `PermissionResultAllow`（可附帶 `updated_input` / `updatedInput` 與 `updated_permissions`）或 `PermissionResultDeny`（附帶 `message` 與 `interrupt`） | `{"type": "approve"}`、`{"type": "edit", "edited_action": {"name": ..., "args": ...}}`、`{"type": "reject", "message": ...}` | 同 Deep Agents（均基於 `HumanInTheLoopMiddleware` 之 `HITLRequest` / `HITLResponse`） | 任意可 JSON 序列化的回傳值（`resume` 值直接成為 `interrupt()` 的回傳值） |
| **向使用者提問工具** | 內建 `AskUserQuestion` 工具（支援 1–4 個問題、2–4 個選項、單選與 `multiSelect`） | 可透過自訂中斷工具或 CLI 互動模式提問 | 可在工具內呼叫 `interrupt()` 觸發前端自訂表單（如 `InterruptCard`） | 在節點或工具內直接呼叫 `answer = interrupt(question)` |

### 2. Claude Agent SDK：五層權限評估順序与 Hook 系統
- **權限評估固定順序（Evaluation Order）**：
  1. **Hooks（`PreToolUse`）**：最先執行，可回傳 `permissionDecision: "allow" | "deny" | "ask"` 或透過 `updatedInput` 修改參數。
  2. **Deny rules（`disallowed_tools` / `disallowedTools` 與 ` settings.json` deny 規則）**：若命中拒絕規則，即使設定了 `bypassPermissions` 也會被阻擋。
  3. **Permission mode（`permission_mode` / `permissionMode`）**：`bypassPermissions` 允許所有其餘工具；`acceptEdits` 自動核准檔案編輯與檔案系統操作；`dontAsk` 將所有未預先允許的工具直接拒絕；`plan` 禁止執行任何修改；`auto`（TS）使用模型分類器審核。
  4. **Allow rules（`allowed_tools` / `allowedTools`）**：若命中白名單則直接放行。
  5. **`canUseTool` / `can_use_tool` 回呼**：若上述皆未決議，呼叫開發者提供的非同步函式做最終裁決。
- **Hook 事件與執行順序**：
  - Python 支援 12 種事件（`PreToolUse`、`PostToolUse`、`PostToolUseFailure`、`UserPromptSubmit`、`Stop`、`SubagentStart`、`SubagentStop`、`PreCompact`、`PermissionRequest`、`SessionStart`、`SessionEnd`、`Notification`），TypeScript 額外支援至 21 種事件（含 `Setup`、`TeammateIdle`、`TaskCompleted`、`Elicitation`、`ElicitationResult`、`ConfigChange`、`WorktreeCreate`、`WorktreeRemove`、`InstructionsLoaded`）。
  - 當多個 Hook 同時對同一工具裁決時，優先順序為：**`deny` > `ask` > `allow`**。

### 3. LangChain 與 Deep Agents：洋蔥式 Middleware vs Hook 指令碼
- **LangChain / Deep Agents SDK 的 `AgentMiddleware` 架構**：
  - **Node-style hooks（依序執行）**：`before_agent` → `before_model` →（模型呼叫）→ `after_model`（**逆序執行**）→ `after_agent`（**逆序執行**）。可回傳狀態更新字典或包含 `jump_to: "tools" | "model" | "end"` 的跳轉指令。
  - **Wrap-style hooks（洋蔥式包裹）**：`wrap_model_call` 與 `wrap_tool_call`，第一個註冊的 Middleware 位於最外層，可修改 `ModelRequest`（動態替換 `model`、`system_prompt`、`tools`、`messages`、`response_format`）、實作重試/降級（Fallback）、快取或直接短路回傳。
- **Deep Agents檔案系統權限（`FilesystemPermission`）**：
  - 針對內建檔案工具（`ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`）提供宣告式規則：`FilesystemPermission(operations=["read", "write"], paths=["/workspace/**", "/memories/**"], mode="allow" | "deny")`。
  - 採用 **First-match-wins（先命中者優先）** 原則；若所有規則皆未命中，預設允許（Default allow）。子代理會繼承父代理的 `FilesystemPermission` 並將自訂規則前置（Prepend）。
- **Deep Agents Code CLI 的 `hooks.json` 機制**：
  - 在 CLI 設定檔中定義外部命令 Hook（支援 11 種事件如 `PreToolUse`、`PostToolUse`、`UserPromptSubmit`、`Stop` 等），透過 stdin 接收 JSON 並以退出碼控制行為：退出碼 `0` 為允許（可由 stdout 輸出 JSON 修改決策），退出碼 `2` 為阻擋並將 stderr 回饋給模型。

### 4. LangGraph `interrupt()` 的決定論（Determinism）規則
- 與 Claude Agent SDK 的記憶體內回呼不同，LangGraph 的 `interrupt()` 透過拋出特殊例外暫停節點，並在收到 `Command(resume=...)` 時**從該節點函式的開頭重新執行**，直到再次遇見 `interrupt()` 時直接回傳 `resume` 值。
- 因此在 LangGraph / LangChain / Deep Agents 的節點或工具中使用 `interrupt()` 時，必須遵守三項鐵律：
  1. **不可用裸 `try...except Exception` 捕捉 `interrupt()`**（否則會吞掉中斷訊號）。
  2. **`interrupt()` 之前的副作用（如 API 寫入、隨機數產生）必須是冪等的或拆分為獨立的前置節點**。
  3. **同一節點內有多個 `interrupt()` 時，呼叫順序必須固定**（依索引順序匹配 `resume` 值）。

## 相關頁面
- [[concepts/agent-sdk-permissions]]
- [[guides/agent-sdk-user-input]]
- [[concepts/agent-sdk-hooks]]
- [[concepts/deepagents-human-in-the-loop]]
- [[concepts/deepagents-backends-and-sandboxes]]
- [[concepts/deepagents-code-approval-and-hooks]]
- [[concepts/langchain-middleware]]
- [[entities/langchain-builtin-middleware]]
- [[concepts/langchain-human-in-the-loop-and-guardrails]]
- [[concepts/langgraph-interrupts-and-time-travel]]

## 出處
- docs/agent-sdk/permissions.md
- docs/agent-sdk/user-input.md
- docs/agent-sdk/hooks.md
- docs/deepagents/human-in-the-loop.md
- docs/deepagents/permissions.md
- docs/deepagents/code/approval-modes.md
- docs/deepagents/code/hooks.md
- docs/langchain/middleware/overview.md
- docs/langchain/middleware/custom.md
- docs/langchain/middleware/built-in.md
- docs/langchain/human-in-the-loop.md
- docs/langgraph/interrupts.md
