# Deep Agents Frontend: Overview, Todo List, Subagent Streaming, and Sandbox UI

別名：Deep Agents 前端整合、Frontend UI Patterns、useStream、injectStream、Todo List UI、Subagent Streaming、SubagentDiscoverySnapshot、Sandbox IDE UI
框架：deepagents

## 摘要
本指南涵蓋使用 LangChain v1 前端 SDK（`@langchain/react`、`@langchain/vue`、`@langchain/svelte`、`@langchain/angular`）為 Deep Agents 建構即時互動式 UI 的核心架構與三大設計模式。透過 `useStream`（Angular 為 `injectStream`），前端可將主協調器訊息（`stream.messages`）、任務規劃進度（`stream.values.todos`）、子代理探索快照（`stream.subagents` 搭配選擇器 `useMessages` 與 `useToolCalls`），以及基於自訂 `http.app` API 伺服器（FastAPI / Hono）的即時 Sandbox 檔案樹與 Diff 檢視器整合為類 IDE 或任務看板體驗。

## 重點

### 1. 前端架構總覽（Frontend Overview）
- **Coordinator-Worker 串流架構與 v1 前端 SDK**：
  - 支援框架套件：`@langchain/react`、`@langchain/vue`、`@langchain/svelte`（皆提供 `useStream<typeof agent>`）以及 `@langchain/angular`（提供 `injectStream<typeof agent>`）。
  - 連線基本設定：`useStream<typeof agent>({ apiUrl: "http://localhost:2024", assistantId: "agent" })`。
- **`useStream` 暴露的五大結構化投影（Projections）**：
  - `stream.messages`：主協調器（coordinator）的對話歷史與最終綜合回答。
  - `stream.subagents`：專家子代理（specialist workers）的即時探索快照集合（儲存為 `Map`，可透過 `[...stream.subagents.values()]` 轉為陣列），包含狀態與任務 metadata。
  - `stream.values`：共享狀態（Shared state），例如 `stream.values?.todos`、計畫、報告章節、sandbox metadata 或代理寫入的任何自訂狀態鍵值。
  - **Tool-call state**：將檔案系統、搜尋、瀏覽器或領域專屬工具渲染為帶有進度與結果的 UI 卡片。
  - **Interrupts**：在不遺失執行狀態的前提下，暫停委派的工作以等待使用者核准（human-in-the-loop）或補充輸入。

### 2. 即時待辦清單模式（Todo List Pattern）
- **運作機制與後端配置**：
  - 任務規劃為選用功能（opt-in）：必須在建立代理時啟用 `TodoListMiddleware`（為代理新增 `write_todos` 工具並持久化任務進度）；若未掛載 `TodoListMiddleware`，前端將不會出現 `stream.values.todos`。
  - 狀態轉換流程：使用者送出請求 -> 代理建立計畫並寫入 `todos` 狀態 -> 每個 `Todo` 項目（含 `status` 與 `content` 欄位）依序經歷 `"pending"` → `"in_progress"` → `"completed"` -> `stream.values.todos` 即時響應式更新並觸發 UI 重新渲染。
- **四大前端框架讀取 `todos` 語法對照（以 `assistantId: "deep_agent_todo_list"` 為例）**：
  - **React（`@langchain/react`）**：`const stream = useStream<typeof myAgent>(...); const todos = stream.values?.todos ?? [];`
  - **Vue（`@langchain/vue`）**：`const stream = useStream<typeof myAgent>(...); const todos = computed(() => stream.values.value?.todos ?? []);`（訊息為 `stream.messages.value`）
  - **Svelte（`@langchain/svelte`）**：`const stream = useStream<typeof myAgent>(...); const todos = $derived(stream.values?.todos ?? []);`
  - **Angular（`@langchain/angular`）**：`stream = injectStream<typeof myAgent>(...); todos = computed(() => this.stream.values()?.todos ?? []);`（訊息為 `stream.messages()`）
- **元件設計、進度計算與最佳實踐**：
  - **進度指標計算**：
    - `completed = todos.filter((t) => t.status === "completed").length`
    - `inProgress = todos.filter((t) => t.status === "in_progress").length`
    - `pending = todos.filter((t) => t.status === "pending").length`
    - `percentage = todos.length ? Math.round((completed / todos.length) * 100) : 0`
  - **視覺狀態樣式（`TodoItem`）**：`pending` 使用圖示 `"○"`（灰色）、`in_progress` 使用圖示 `"◉"`（琥珀色搭配 `animate-pulse` 動畫）、`completed` 使用圖示 `"✓"`（綠色搭配刪除線 `line-through`）。
  - **空狀態與載入處理**：當 `todos.length === 0 && !isLoading` 時回傳 `null`（不佔用版面）；當 `todos.length === 0 && isLoading` 時顯示旋轉圖示 `"⟳"` 與 `"Agent is creating a plan..."`。
  - **最佳實踐**：將待辦清單置於顯眼處（如頂部面板或常駐側邊欄）、為狀態轉換加上 CSS 動畫、同時僅突顯（pulse）第一個 `in_progress` 項目、摺疊或淡化已完成項目、顯示完成百分比，並直接依賴 `stream.values` 響應式更新（切勿自行加入輪詢 polling 邏輯）。

### 3. 子代理即時串流模式（Subagent Streaming Pattern）
- **基於選擇器的子代理串流架構（Selector-based Subagent Streams）**：
  - 根串流 `stream.messages` **僅包含主協調器的訊息**，避免將所有工作者的輸出 token 混雜在同一對話串中。
  - `stream.subagents` 儲存每個子代理的輕量級探索紀錄 `SubagentDiscoverySnapshot`（包含 `id`、`name`、`status` 如 `"running"` 或 `"complete"`、以及最終 `output`）。
  - **重要特性**：`SubagentDiscoverySnapshot` 本身**不包含**子代理串流中的訊息或工具呼叫。必須將 `stream` 與 `subagent` 快照傳給選擇器 hooks（從 `@langchain/react` 匯入 `useMessages(stream, subagent)` 與 `useToolCalls(stream, subagent)`，搭配型別 `AnyStream` 與 `SubagentDiscoverySnapshot`），唯有當對應的 `SubagentCard` 掛載時才會訂閱該子代理的命名空間串流。
- **依 Tool-Call ID 關聯主協調器訊息與子代理卡片**：
  - 建立索引：`const subagents = [...stream.subagents.values()]; const subagentsByCallId = new Map(subagents.map((s) => [s.id, s]));`
  - 在渲染 `stream.messages` 時，透過 `AIMessage.isInstance(msg)` 檢查主協調器的 `msg.tool_calls`，並以 `subagentsByCallId.get(tc.id ?? "")` 找出該輪委派所產生的所有子代理（`turnSubagents`），將 `<SubagentCard>` 直接渲染於發起委派的 AI 訊息下方（亦可同時結合右側全域側邊欄顯示所有 `stream.subagents` 與整體完成度 `SubagentProgress`）。
- **`SubagentCard` 元件與遞迴上限設定**：
  - 在 `SubagentCard` 中：透過 `const messages = useMessages(stream, subagent)` 與 `const toolCalls = useToolCalls(stream, subagent)` 取得即時狀態；取最後一則 AI 訊息文字 `messages.filter(AIMessage.isInstance).at(-1)?.text ?? subagent.output ?? ""` 作為顯示內容，並在 `subagent.status === "running"` 時顯示閃爍游標。
  - **遞迴上限（Recursion Limit）**：Deep Agents 預設將遞迴上限設為 `10,000`（足以應付大多數多專家委派架構）；若有特殊深層自訂工作流，可於呼叫 `stream.submit({ messages: [{ type: "human", content: text }] }, { config: { recursion_limit: 100 } })` 時透過 `config.recursion_limit` 覆寫。

### 4. Sandbox 類 IDE 介面模式（Sandbox IDE Pattern）
- **三層式架構與自動工具注入**：
  1. **配備 Sandbox Backend 的 Deep Agent**：自動從沙箱獲得檔案系統與執行工具——Python 自動獲得 `read_file`、`write_file`、`edit_file`、`delete`、`execute`；JavaScript 自動獲得 `read_file`、`write_file`、`edit_file`、`execute`。
  2. **自訂檔案瀏覽 API 伺服器（Custom API Server）**：透過 `langgraph.json` 的 `http.app` 欄位掛載於同一個 Agent Server 主機（本機 `langgraph dev` 為 `http://localhost:2024`）。Python 使用 **FastAPI**（`"http": { "app": "./src/api/server.py:app" }`）；JavaScript 使用 **Hono**（`"http": { "app": "./src/api/app.ts:app" }`，搭配 `"node_version": "22"`）。**注意**：`http.app` 中定義的自訂路由優先權高於預設 LangGraph 路由，應避免意外覆蓋 `/threads` 或 `/runs`。
  3. **三欄式前端（Three-panel frontend）**：結合檔案樹側邊欄（File tree）、程式碼與差異檢視器（Code/diff viewer）以及對話面板（Chat panel）。
- **跨代理與 API 伺服器的 Thread-scoped Sandbox 共用機制**：
  - 將 `sandbox_id` 儲存於 LangGraph thread 的 `metadata.sandbox_id` 中作為單一真實來源（無需記憶體內快取）。
  - 代理（定義為 async graph factory）與自訂 API 路由皆呼叫同一個共用函式：Python 為 `get_or_create_sandbox_for_thread(thread_id)`，JavaScript 為 `getOrCreateSandboxForThread(threadId)`。當頁面載入呼叫 `POST /threads` 取得 `threadId` 後，若 `threads.get(threadId)` 尚無 `metadata.sandbox_id`，即建立沙箱並呼叫 `threads.update(threadId, metadata.sandbox_id)`，否則直接連線既有沙箱。
  - 專案初始化技巧：上傳 `package.json` 等初始檔案後，可先執行 `sandbox.execute("cd /app && npm install")` 讓依賴套件在第一輪對話前準備就緒。
- **自訂檔案瀏覽 API 端點規格**：
  - `GET /sandbox/:threadId/tree`（Python 為 `/sandbox/{thread_id}/tree`，選填查詢參數 `filePath` 預設為 `"/app"`）：在沙箱內執行 `find '/app' -printf '%y\t%s\t%p\n' 2>/dev/null | sort`（Python 使用 `await sandbox.aexecute(...)`，JS 使用 `await sandbox.execute(...)`），解析並回傳 `{ path: rootPath, entries: [{ name, type: "directory" | "file", path, size }], sandboxId: sandbox.id }`。前端取得後應過濾掉包含 `"node_modules"` 的路徑。
  - `GET /sandbox/:threadId/file`（Python 為 `/sandbox/{thread_id}/file`，必填查詢參數 `filePath`）：呼叫 `await sandbox.adownload_files([filePath])`（Python）或 `await sandbox.downloadFiles([filePath])`（JS）下載並解碼檔案內容，回傳 `{ path: filePath, content }`（找不到或出錯時回傳 HTTP 404）。
- **前端 Thread 持久化、即時檔案同步與 Diff 渲染**：
  - **SessionStorage 持久化**：將 `threadId` 存於 `sessionStorage` 的 `"sandbox-thread-id"`（`THREAD_KEY`）鍵值中，並傳入 `useStream({ apiUrl: AGENT_URL, assistantId: "deep_agent_ide", threadId, onThreadId: updateThreadId })`；首次掛載若無 `threadId` 則呼叫 `stream.client.threads.create().then((t) => updateThreadId(t.thread_id))`，確保重新整理頁面後仍連回同一個沙箱。
  - **即時檔案同步（Real-time file sync）**：監聽 `stream.messages` 中的 `AIMessage` 工具呼叫與對應完成的 `ToolMessage`（以 `processedIds` 集合記錄已處理的 `msg.id ?? msg.tool_call_id`）。鎖定變更檔案的工具集合 `FILE_MUTATING_TOOLS = new Set(["write_file", "edit_file", "execute"])`（Python 亦包含 `"delete"`）：當 `write_file` 或 `edit_file` 完成時呼叫 `refreshSingleFile(call.args.path ?? call.args.file_path)` 僅刷新該檔案；當 `execute` 完成時呼叫 `refreshTreeAndFiles()` 刷新整個檔案樹與所有檔案。
  - **四大框架 Diff 檢視套件對照**：
    - **React**：使用 `@pierre/diffs` 的 `parseDiffFromFile({ name: fileName, contents: original }, { name: fileName, contents: current })` 搭配 `@pierre/diffs/react` 的 `<FileDiff fileDiff={diff} options={{ theme: "github-dark", diffStyle: "unified", diffIndicators: "bars" }} />`。
    - **Vue**：使用 `@git-diff-view/vue` 的 `<DiffView>` 搭配 `@git-diff-view/file` 的 `generateDiffFile`。
    - **Svelte**：使用 `@git-diff-view/svelte` 的 `<DiffView>` 搭配 `@git-diff-view/file` 的 `generateDiffFile`。
    - **Angular**：使用 `ngx-diff` 的 `<ngx-unified-diff>` 搭配 `[before]` 與 `[after]`。

## 相關頁面
- [[guides/deepagents-going-to-production]]
- [[concepts/deepagents-sandboxes]]
- [[concepts/deepagents-subagents]]
- [[concepts/deepagents-protocols-and-integrations]]

## 出處
- docs/deepagents/frontend/overview.md
- docs/deepagents/frontend/todo-list.md
- docs/deepagents/frontend/subagent-streaming.md
- docs/deepagents/frontend/sandbox.md
