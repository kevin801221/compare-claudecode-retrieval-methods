# Claude Agent SDK: Python vs TypeScript Comparison

別名：Agent SDK Python 與 TypeScript 比較、`claude-agent-sdk` vs `@anthropic-ai/claude-agent-sdk`、Python 與 TypeScript SDK 差異對照
框架：agent-sdk

## 摘要
本頁比較 Claude Agent SDK 在 Python（`claude-agent-sdk`）與 TypeScript（`@anthropic-ai/claude-agent-sdk`）兩個官方語言版本間的架構設計、命名慣例、核心 API、多輪對話與預熱機制、In-Process MCP 工具定義、Hook 攔截事件、沙盒預設行為及錯誤處理差異。兩者底層皆驅動相同的 Claude Code 原生二進位檔與控制協定，但在語言慣例與進階控制介面上存在重要區別。

## 重點

### 1. 套件安裝、打包與入口點差異
| 面向 | Python (`claude-agent-sdk`) | TypeScript (`@anthropic-ai/claude-agent-sdk`) |
| :- | :- | :- |
| **安裝指令** | `pip install claude-agent-sdk`（在 Debian/Ubuntu/Homebrew Python 下需先建立 `.venv` 虛擬環境以避免 `externally-managed-environment` 錯誤） | `npm install @anthropic-ai/claude-agent-sdk` |
| **內建 CLI 二進位檔** | 隨套件提供；可透過 `ClaudeAgentOptions.cli_path` 指定自訂路徑 | 透過 optional dependency（如 `@anthropic-ai/claude-agent-sdk-darwin-arm64`）打包；SDK 版本追蹤 CLI patch 版本（如 SDK `v0.3.191` 對應 CLI `v2.1.191`）；可透過 `Options.pathToClaudeCodeExecutable` 指定 |
| **單一執行檔與 Bundler 支援** | 無專屬 bundler 入口 | 提供 `@anthropic-ai/claude-agent-sdk/extract` 的 `extractFromBunfs()` 支援 `bun build --compile`；提供 `@anthropic-ai/claude-agent-sdk/core` 輕量入口點（將 `zod` 與 `@modelcontextprotocol/sdk` 改由 `peerDependencies` 載入，排除 `InMemorySessionStore` 與部分 Session 輔助函式） |

---

### 2. 命名慣例與執行期型別系統
- **命名風格（`snake_case` vs `camelCase`）**：
  - **Python SDK**：函式、方法與 `ClaudeAgentOptions` 欄位主要採用 `snake_case`（如 `allowed_tools`、`permission_mode`、`can_use_tool`、`create_sdk_mcp_server`、`list_sessions`）。**重要例外**：
    1. `AgentDefinition`（`@dataclass`）的所有多字欄位皆使用 **camelCase**（`disallowedTools`、`mcpServers`、`initialPrompt`、`maxTurns`、`permissionMode`），傳入 `snake_case` 會在建構時拋出 `TypeError`。
    2. `ModelUsage`、`SandboxSettings`、`SandboxNetworkConfig`、`McpStatusResponse`、`ContextUsageResponse`、`HookSpecificOutput` 及 `UserMessage.tool_use_result` 中的工具輸出皆保留 CLI 原生的 **camelCase** 鍵名。
  - **TypeScript SDK**：所有函式、`Options` 屬性、`Query` 方法與設定介面全面採用 **camelCase**（如 `allowedTools`、`permissionMode`、`canUseTool`、`createSdkMcpServer`、`listSessions`）；僅訊息串流載荷（`SDKMessage`）與 `BaseHookInput` 等貼近底層 wire protocol 的欄位維持 `snake_case`（如 `session_id`、`parent_tool_use_id`、`total_cost_usd`）。
- **執行期物件表示法**：
  - **Python SDK** 混用 `@dataclass`（如 `ClaudeAgentOptions`、`AgentDefinition`、`ResultMessage`、`ToolPermissionContext`、`PermissionResultAllow`、`HookMatcher`，支援 `.attr` 屬性存取）與 `TypedDict`（如 `ThinkingConfig`、`McpStdioServerConfig`、`SyncHookJSONOutput`、`SandboxSettings`，執行期為一般 `dict`，**必須使用 `["key"]` 存取**，用 `.attr` 會拋出 `AttributeError`）。
  - **TypeScript SDK** 所有選項、訊息與工具輸出皆為純 JavaScript 物件（搭配 TypeScript `type` / `interface` 靜態型別宣告，工具輸入/輸出型別另由 `@anthropic-ai/claude-agent-sdk/sdk-tools` 匯出 `ToolInputSchemas` 與 `ToolOutputSchemas`）。

---

### 3. 核心查詢、多輪對話與程序預熱架構
| 功能 | Python (`claude-agent-sdk`) | TypeScript (`@anthropic-ai/claude-agent-sdk`) |
| :- | :- | :- |
| **單次與串流查詢** | `query(*, prompt, options, transport) -> AsyncIterator[Message]`（單純回傳訊息非同步迭代器，不具備控制方法，不支援 `interrupt()`） | `query({ prompt, options }) -> Query`（回傳 `Query` 介面，本身即為 `AsyncGenerator<SDKMessage, void>` 且直接掛載 26 個執行期控制方法） |
| **多輪對話與執行期控制** | 使用專屬類別 `ClaudeSDKClient`（支援 `async with`、`connect()`、`query()`、`receive_response()`、`receive_messages()`、`interrupt()`、`set_model()`、`set_permission_mode()` 等） | 直接在 `query()` 回傳的 `Query` 物件上操作（傳入 `AsyncIterable<SDKUserMessage>` 作為 `prompt` 或呼叫 `q.streamInput(stream)`）。實驗性的 V2 Session API（`unstable_v2_createSession`、`unstable_v2_resumeSession`、`unstable_v2_prompt`、`SDKSession`）已於 `v0.3.142` 移除 |
| **CLI 子程序預熱（Pre-warm）** | 無內建預熱頂層函式 | 提供 `startup()`（回傳 `Promise<WarmQuery>`，在已知 `cwd` 下預先啟動子程序並完成 `initialize` 交握）與 `prewarm()`（*Alpha*，回傳 `Promise<SpareProcess>`，在未知 Session 資料夾前預先啟動備用程序，後續以 `spare.claim({ prompt, options })` 綁定） |
| **自訂通訊 / 程序孵化** | 繼承抽象基底類別 `Transport`（實作 `connect`、`write`、`read_messages`、`close`、`is_ready`、`end_input`）並傳入 `query()` 或 `ClaudeSDKClient` | 在 `Options.spawnClaudeCodeProcess` 傳入 `(options: SpawnOptions) => SpawnedProcess` 自訂程序孵化函式（Node `ChildProcess` 原生相容） |

---

### 4. 設定選項（`ClaudeAgentOptions` vs `Options`）與執行期動態設定差異
- **環境變數（`env`）合併行為（關鍵陷阱）**：
  - **Python `ClaudeAgentOptions.env`**：預設 `{}`，會**疊加（merge）**在繼承的父程序環境變數之上。
  - **TypeScript `Options.env`**：預設 `process.env`，一旦設定會**完全取代（replace）**子程序環境而非合併，因此必須寫成 `{ ...process.env, YOUR_VAR: 'value' }` 才不會遺失 `PATH` 等系統環境變數。
- **取消與中斷機制**：
  - **Python**：透過 `ClaudeSDKClient.interrupt()` 發送中斷訊號（中斷後舊訊息與 `ResultMessage` 仍留在緩衝區，需先呼叫 `receive_response()` 排空）。`ToolPermissionContext.signal` 與 `HookContext["signal"]` 目前為保留欄位（`None`）。
  - **TypeScript**：同時支援 `Options.abortController`（`AbortController`，並將 `AbortSignal` 傳入 `CanUseTool`、`HookCallback`、`onElicitation` 與 `SpawnOptions`）以及串流輸入模式下的 `Query.interrupt()`（在支援 `interrupt_receipt_v1` 的 CLI 上會回傳 `SDKControlInterruptResponse`，列出 `still_queued` 訊息 UUID）。
- **沙盒無法啟動時的預設行為（`sandbox.failIfUnavailable`）**：
  - **Python**：當 `sandbox={"enabled": True}` 但系統缺少 `bubblewrap`/`socat` 等沙盒依賴時，**預設退回無沙盒執行**並在 stderr 發出警告；需明確在 `sandbox` dict 中傳入 `"failIfUnavailable": True` 才會停止並報錯。
  - **TypeScript**：`SandboxSettings.failIfUnavailable` **預設為 `true`**，沙盒無法啟動時會直接停止並回傳 `subtype: "error_during_execution"`（`startup_failure_reason: "sandbox_required_unavailable"`）；需設為 `false` 才會退回無沙盒執行。
- **系統提示（`system_prompt` vs `systemPrompt`）**：
  - **Python**：支援 `SystemPromptFile`（`{"type": "file", "path": "..."}`，對應 `--system-prompt-file`，可避開 Linux 128 KB / Windows 32 KB 命令列參數長度限制）。
  - **TypeScript**：支援傳入字串陣列 `string[]` 並在靜態與動態區段間插入 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 常數以快取自訂提示的靜態部分。
- **TypeScript 專屬的執行期與靜態設定控制方法**：
  - `Query.applyFlagSettings(settings)`：TypeScript 專屬（Python SDK 無對應方法），可在 Session 執行中動態將 `model`、`effortLevel`、`ultracode`、`permissions`、`hooks`、`skillOverrides`、`fastMode`、`agent` 淺層合併至 flag-settings 層，或傳入 `null` 重設。
  - `Query.updateSettings(source, settings)`：將 `outputStyle` 寫入 `"localSettings"` 或將 `effortLevel` 寫入 `"userSettings"`。
  - `resolveSettings(options?)`（*Alpha*）：不啟動 CLI 直接在記憶體中執行設定合併引擎並回傳 `{ effective, provenance, sources }`。
  - `Query` 額外方法：`reinitialize()`、`supportedCommands()`、`supportedModels()`、`supportedAgents()`、`accountInfo()`、`readFile()`、`reloadPlugins()`（支援 `holdOnCacheImpact` 與 `addPlugins`）、`reloadSkills()`、`reloadOutputStyles()`、`seedReadState()`、`setMcpServers()`、`setMcpPermissionModeOverride()`、`readMcpResource()`、`backgroundTasks()`。

---

### 5. In-Process MCP 工具與伺服器定義差異
| 面向 | Python (`@tool` + `create_sdk_mcp_server`) | TypeScript (`tool` + `createSdkMcpServer`) |
| :- | :- | :- |
| **工具定義語法** | 裝飾器 `@tool(name, description, input_schema, annotations=None)`，回傳 `SdkMcpTool` dataclass | 函式 `tool(name, description, inputSchema, handler, extras?)`，回傳 `SdkMcpToolDefinition<Schema>` |
| **Input Schema 格式** | 支援 3 種格式：1. 簡單型別映射（如 `{"text": str}`）、2. JSON Schema `dict`、3. `TypedDict` 類別（支援 `NotRequired` 與 `Annotated[type, "desc"]`） | 使用 **Zod Schema**（`Schema extends AnyZodRawShape`，同時支援 Zod 3 與 Zod 4），自動推導 `handler` 的 `args` 型別 |
| **工具附加選項** | `ToolAnnotations` 擴充支援 `maxResultSizeChars`（上限 `500,000`，以 `_meta["anthropic/maxResultSizeChars"]` 傳送） | `extras` 支援 `{ annotations?: ToolAnnotations; searchHint?: string; alwaysLoad?: boolean }`（支援 Tool Search 提示與跳過延遲載入） |
| **Server 建立參數** | `create_sdk_mcp_server(name, version="1.0.0", tools=None) -> McpSdkServerConfig` | `createSdkMcpServer({ name, version?, instructions?, tools?, alwaysLoad?, timeout? }) -> McpSdkServerConfigWithInstance`（額外支援伺服器級 `instructions`、`alwaysLoad` 與 `>= 1000` ms 的 `timeout`） |
| **In-Process 工具權限政策** | 透過 `allowed_tools` / `disallowed_tools` 與 `can_use_tool` 控制 | 除了 `allowedTools` 外，可在 `McpSdkServerConfigWithInstance.tools` 附加 `McpServerToolPolicy[]`（設定單一工具為 `always_ask` 或 `always_deny`，需 SDK `v0.3.301+`） |

---

### 6. Session 管理函式（同步 vs 非同步）
- **Python SDK**：所有 Session 管理函式皆為**同步函式（Synchronous）**，直接回傳結果或拋出 `ValueError` / `FileNotFoundError`：
  - `list_sessions(directory=None, limit=None, offset=0, include_worktrees=True) -> list[SDKSessionInfo]`（額外支援 `offset` 參數）
  - `get_session_messages(session_id, directory=None, limit=None, offset=0) -> list[SessionMessage]`
  - `get_session_info(session_id, directory=None) -> SDKSessionInfo | None`
  - `rename_session(session_id, title, directory=None) -> None`
  - `tag_session(session_id, tag, directory=None) -> None`
  - `fork_session(session_id, directory=None, up_to_message_id=None, title=None) -> ForkSessionResult`
- **TypeScript SDK**：所有 Session 管理函式皆為**非同步函式（回傳 `Promise`）**，選項以單一 `options` 物件傳入（目錄參數名為 `dir` 而非 `directory`）：
  - `listSessions(options?: { dir?, limit?, includeWorktrees? }): Promise<SDKSessionInfo[]>`
  - `getSessionMessages(sessionId, options?: { dir?, limit?, offset?, includeSystemMessages? }): Promise<SessionMessage[]>`（額外支援 `includeSystemMessages: boolean` 以包含 `"system"` 角色訊息）
  - `getSessionInfo(sessionId, options?: { dir? }): Promise<SDKSessionInfo | undefined>`
  - `renameSession(sessionId, title, options?: { dir? }): Promise<void>`
  - `tagSession(sessionId, tag, options?: { dir? }): Promise<void>`
  - `forkSession(sessionId, options?: { dir?, upToMessageId?, title? }): Promise<ForkSessionResult>`

---

### 7. 訊息、Hook 事件與錯誤處理差異
- **訊息型別涵蓋度**：
  - **Python `Message` 聯集**：定義 7 個頂層類別（`UserMessage`、`AssistantMessage`、`SystemMessage`、`ResultMessage`、`StreamEvent`、`RateLimitEvent`、`ConversationResetMessage`）加上 3 個 `SystemMessage` 子類別（`TaskStartedMessage`、`TaskProgressMessage`、`TaskNotificationMessage`）；其餘所有系統事件皆以通用的 `SystemMessage(subtype, data)` 呈現，從 `message.data` 字典讀取欄位。
  - **TypeScript `SDKMessage` 聯集**：為全部 40 種訊息定義了精確的具名 TypeScript 型別（如 `SDKCompactBoundaryMessage`、`SDKHookStartedMessage`、`SDKToolProgressMessage`、`SDKTaskUpdatedMessage`、`SDKBackgroundTasksChangedMessage`、`SDKThinkingTokensMessage`、`SDKSessionStateChangedMessage`、`SDKPermissionDeniedMessage`、`SDKPromptSuggestionMessage` 等）。
- **Hook 事件與輸出鍵名**：
  - **Python `HookEvent`**：型別定義列出 10 種事件（`PreToolUse`、`PostToolUse`、`PostToolUseFailure`、`UserPromptSubmit`、`Stop`、`SubagentStop`、`PreCompact`、`Notification`、`SubagentStart`、`PermissionRequest`）。因 `continue` 與 `async` 為 Python 保留字，`SyncHookJSONOutput` 與 `AsyncHookJSONOutput` 分別使用 `continue_` 與 `async_` 鍵名（SDK 再轉換為 `"continue"` 與 `"async"` 傳給 CLI）。
  - **TypeScript `HookEvent`**：型別定義完整列出 33 種事件（額外涵蓋 `PostToolBatch`、`UserPromptExpansion`、`SessionStart`、`SessionEnd`、`StopFailure`、`PostCompact`、`PreModelSwitch`、`PostModelSwitch`、`PermissionDenied`、`Setup`、`TeammateIdle`、`TaskCreated`、`TaskCompleted`、`Elicitation`、`ElicitationResult`、`ConfigChange`、`DirectoryAdded`、`WorktreeCreate`、`WorktreeRemove`、`InstructionsLoaded`、`CwdChanged`、`FileChanged`、`MessageDisplay`），且 `SyncHookJSONOutput` 與 `AsyncHookJSONOutput` 直接使用 `continue` 與 `async` 屬性。
- **例外與錯誤類別**：
  - **Python**：提供完整的例外階層：`ClaudeSDKError` -> `CLIConnectionError`（含 `CLINotFoundError`）、`ProcessError`（含 `ResultError`，提供結構化的 `subtype`、`errors`、`result`、`api_error_status`、`terminal_reason`、`session_id`、`data`）、`CLIJSONDecodeError`。
  - **TypeScript**：僅匯出單一錯誤類別 `AbortError extends Error`；其他如 CLI 程序退出或啟動失敗皆以一般 `Error` 拒絕 Promise，並以錯誤訊息字串區分原因。

## 相關頁面
- [[entities/agent-sdk-python-functions-and-client]]
- [[entities/agent-sdk-python-options-and-types]]
- [[entities/agent-sdk-python-messages-hooks-and-errors]]
- [[entities/agent-sdk-typescript-functions-and-query]]
- [[entities/agent-sdk-typescript-options-and-types]]
- [[entities/agent-sdk-typescript-messages-and-hooks]]
- [[entities/agent-sdk-builtin-tools]]

## 出處
- docs/agent-sdk/overview.md
- docs/agent-sdk/python.md
- docs/agent-sdk/typescript.md
- docs/agent-sdk/typescript-v2-preview.md
