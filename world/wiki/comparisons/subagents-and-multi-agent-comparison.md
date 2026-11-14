# Subagents and Multi-Agent Orchestration Comparison Across Frameworks

別名：跨框架子代理與多代理比較、Subagents 比較、Multi-Agent 架構對照、Agent Tool vs SubAgentMiddleware vs StateGraph Subgraphs
框架：agent-sdk、deepagents、langchain、langgraph

## 摘要
四個框架都提供將複雜任務拆解給多個代理（Subagents / Multi-Agent）的機制，以實現上下文隔離（Context Isolation）與職責分工：Claude Agent SDK 透過 `agents` 選項定義 `AgentDefinition` 並由內建 `Agent`（舊稱 `Task`）工具派發；Deep Agents 內建 `SubAgentMiddleware` 與 `AsyncSubAgentMiddleware`，支援宣告式 `SubAgent`、預編譯圖 `CompiledSubAgent`、遠端非同步子代理與動態建立子代理；LangChain 歸納出 Subagents、Handoffs、Skills 與 Router 四大多代理模式；LangGraph 則提供底層的 Subgraphs、`Command` 跨圖跳轉與 `Send` 平行 Map-Reduce 原語。

## 重點

### 1. 各框架子代理與多代理機制對照表
| 維度 | Claude Agent SDK (`agent-sdk`) | Deep Agents (`deepagents`) | LangChain (`langchain`) | LangGraph (`langgraph`) |
|---|---|---|---|---|
| **核心定義介面** | `AgentDefinition`（配置於 `options.agents`） | `SubAgent`、`CompiledSubAgent`、`AsyncSubAgent`（配置於 `create_deep_agent(subagents=[...])`） | 將 `create_agent` 包裝為 `@tool`、使用 `Command` 交接或搭配 LangGraph 路由 | `StateGraph` 子圖（作為節點直接掛載，或在節點函式內呼叫） |
| **預設內建子代理** | 內建一般用途子代理（當 `allowed_tools` 包含 `Agent` / `Task` 時可用） | 自動內建 `general-purpose` 子代理（繼承主代理模型、工具與檔案系統後端） | 無預設子代理（由開發者自行組合） | 無預設子代理（底層圖編排框架） |
| **派發工具名稱** | `Agent`（v2.1.63 自 `Task` 更名，`Task` 保留為相容別名） | 同步：`task(name, description)`<br>非同步：`start_async_task` 等 5 個工具 | 開發者自訂 `@tool` 名稱（如 `schedule_event`）或統一派發工具 | 透過圖邊（Edges）、`Command(goto=...)` 或 `Send(node, arg)` 觸發 |
| **巢狀子代理限制** | **禁止子代理再產生子代理**（不可在子代理的 `tools` 中加入 `Agent` / `Task`） | 預設子代理不自動包含 `SubAgentMiddleware`，但可透過自訂 `CompiledSubAgent` 組合 | 視工具包裝層級而定，可自由組合多層 | 支援多層巢狀子圖（Subgraphs） |
| **上下文隔離與回傳** | 子代理使用全新對話上下文（不繼承父代理對話歷史），僅將最終文字結果回傳給父代理；轉錄檔獨立存於 `~/.claude/projects/<encoded-cwd>/<session-id>/subagents/agent-<agentId>.jsonl` | 子代理擁有獨立的 `messages` 列表，透過共享的 `BackendProtocol`（如 `/workspace/`）交換大型檔案，僅回傳最終摘要訊息給主代理 | Subagents 模式隔離上下文並回傳 `ToolMessage` 或 `Command`；Handoffs 模式共享或轉換 `AgentState` | 支援「共享狀態鍵（Shared state keys）」或「完全獨立 Schema 並在節點內手動轉換輸入輸出」 |

### 2. Claude Agent SDK 子代理細節
- **`AgentDefinition` 欄位**：
  - `description`（`str`，必填）：自然語言描述何時應呼叫此子代理。
  - `prompt`（`str`，必填）：子代理的系統提示詞。
  - `tools`（`list[str]` / `string[]`，選填）：允許的工具名稱列表；若省略則繼承所有可用工具（不含 `Agent`）。
  - `model`（`'sonnet' | 'opus' | 'haiku' | 'inherit'` 或完整模型 ID，選填）：若省略或設為 `'inherit'` 則使用主代理模型。
  - TypeScript 額外支援欄位：`disallowedTools`、`skills`、`memory`（`'user' | 'project' | 'local'`）、`mcpServers`、`initialPrompt`、`maxTurns`、`background`、`effort`、`permissionMode`。
- **繼承規則**：子代理會接收自身的 `AgentDefinition.prompt` 加上環境基本資訊（如工作目錄），但**不會**繼承父代理的系統提示詞（除非透過 `CLAUDE.md` 且啟用 `settingSources`）或父代理的對話歷史。
- **串流訊息識別**：來自子代理執行期間的所有訊息皆帶有 `parent_tool_use_id` 欄位，對應觸發該子代理的 `Agent` / `Task` 工具呼叫區塊 ID；生命週期可透過 `SubagentStart` 與 `SubagentStop` Hook 攔截。

### 3. Deep Agents 子代理模式（同步、非同步、動態與 CLI）
- **宣告式 `SubAgent` 與預編譯 `CompiledSubAgent`**：
  - `SubAgent` 支援欄位：`name`（必填）、`description`（必填）、`system_prompt`（必填）、`tools`（必填）、`model`（選填，預設繼承主代理）、`middleware`、`interrupt_on`、`skills`（僅由顯式設定決定，**不會**從主代理繼承 `skills`；但 `general-purpose` 子代理會繼承主代理的 `skills`）。
  - `CompiledSubAgent`：透過 `runnable` 欄位直接掛載任何自訂的 LangGraph 編譯圖。
- **非同步子代理（`AsyncSubAgent` / `AsyncSubAgentMiddleware`）**：
  - 連接部署於 LangGraph Server / LangSmith Deployment 的遠端圖（配置 `name`、`description`、`graph_id`、`url`、`headers`），適合耗時數分鐘至數小時的背景研究或編碼任務。
  - 自動注入 5 個專用工具：`start_async_task`、`check_async_task`、`update_async_task`、`cancel_async_task`、`list_async_tasks`，並將任務狀態保存於圖狀態的 `async_tasks` 通道中。
- **動態子代理（Dynamic Subagents）**：
  - 在 `CodeInterpreterMiddleware`（Programmatic Tool Calling）或 Deep Agents Code CLI（設定 `DEEPAGENTS_CODE_FORKED_SUBAGENTS=1`）中，主代理可呼叫 `task(name, description, prompt=..., tools=..., model=...)` 在執行期動態建立專職子代理，並以 `(name, tools)` 作為快取鍵重用實例。

### 4. LangChain 四大多代理架構模式與 LangGraph 子圖
- **LangChain 四大模式**：
  1. **Subagents（子代理作為工具）**：由中心主代理（Supervisor）將子代理視為工具呼叫，掌控所有路由與使用者互動；可透過 `ToolRuntime` 傳遞 `state` 與 `context`，並回傳 `Command(update={...})` 更新額外狀態。
  2. **Handoffs（控制權交接）**：透過更新狀態欄位（如 `current_step` 或 `active_agent`）搭配 Middleware 動態切換系統提示詞與工具，或使用 `Command(goto="target_agent", graph=Command.PARENT)` 直接將後續對話主導權交給另一個代理。
  3. **Skills（技能漸進式揭露）**：單一代理在執行期透過 `load_skill` 工具按需載入領域專業提示詞或動態解鎖工具，每次使用者輸入僅需 1–2 次 LLM 呼叫。
  4. **Router（路由器）**：先由分類器將查詢路由至一個或多個領域代理（搭配 LangGraph `Send` 平行執行），最後合成結果。
- **LangGraph 子圖持久化模式（`checkpointer` 參數）**：
  - `checkpointer=None`（預設）：若父圖有 checkpointer，子圖自動支援單次呼叫內的中斷（`interrupt()`）與狀態檢查，但不跨多次呼叫保留子圖內部記憶。
  - `checkpointer=True`：子圖跨多次呼叫保留獨立的持久化對話狀態（注意：若在同一節點函式內呼叫兩個皆設定 `checkpointer=True` 的子圖，會觸發 `MULTIPLE_SUBGRAPHS` 錯誤）。
  - `checkpointer=False`：子圖完全無狀態，不寫入檢查點且不支援子圖內 `interrupt()`。

## 相關頁面
- [[concepts/agent-sdk-subagents]]
- [[concepts/deepagents-subagents]]
- [[concepts/deepagents-code-extensibility]]
- [[concepts/langchain-multi-agent-overview]]
- [[concepts/langchain-multi-agent-subagents]]
- [[concepts/langchain-multi-agent-handoffs]]
- [[concepts/langchain-multi-agent-router-and-skills]]
- [[concepts/langgraph-subgraphs-and-fault-tolerance]]

## 出處
- docs/agent-sdk/subagents.md
- docs/agent-sdk/python.md
- docs/agent-sdk/typescript.md
- docs/deepagents/subagents.md
- docs/deepagents/async-subagents.md
- docs/deepagents/dynamic-subagents.md
- docs/deepagents/code/subagents.md
- docs/langchain/multi-agent/index.md
- docs/langchain/multi-agent/subagents.md
- docs/langchain/multi-agent/handoffs.md
- docs/langchain/multi-agent/router.md
- docs/langchain/multi-agent/skills.md
- docs/langgraph/use-subgraphs.md
- docs/langgraph/errors/MULTIPLE_SUBGRAPHS.md
