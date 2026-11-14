# LangGraph Streaming and Event Streaming

別名：LangGraph 串流、串流模式、事件串流、前端圖執行視覺化、自訂串流通道、Stream Modes、Event Streaming、StreamPart、StreamTransformer、StreamChannel
框架：langgraph

## 摘要
LangGraph 提供兩層串流架構：底層的 **Streaming（串流模式 API）** 直接從 Pregel 執行引擎發出原始圖執行事件（如 `values`、`updates`、`messages`、`custom`、`checkpoints`、`tasks`、`debug` 與 JS 的 `tools`），並支援以 `version="v2"` 輸出統一的 `StreamPart` 格式；高層的 **Event Streaming（事件串流 API，LangGraph v1.2+ 推薦）** 則透過 `stream_events(..., version="v3")` / `streamEvents(..., { version: "v3" })` 將底層事件正規化為 `ProtocolEvent`，經由 `StreamTransformer` 轉換後提供型別化的投影（如 `stream.messages`、`stream.values`、`stream.subgraphs`、`stream.output`、`stream.extensions`）。在前端整合上，可搭配 `@langchain/react`、`@langchain/vue`、`@langchain/svelte`、`@langchain/angular` 的 `useStream`、`useMessages`、`useExtension` 與 `useChannel` 即時渲染多節點執行進度卡片與自訂伺服端通道資料。

## 重點

### 1. 底層串流 API（`stream` / `astream`）與 `version="v2"` 統一格式
- **核心呼叫方法**：
  - Python：編譯後的圖（`Pregel` / `CompiledStateGraph`）暴露同步 `graph.stream(inputs, stream_mode=..., version="v2", subgraphs=..., config=...)` 與非同步 `graph.astream(...)` 方法。
  - TypeScript / JavaScript：暴露 `await graph.stream(inputs, { streamMode: ..., subgraphs: ... })`，以 `for await (const chunk of ...)` 迭代。
- **`version="v2"` 統一輸出格式（Python，需 LangGraph 1.1+）**：
  - 不論指定單一或多個 `stream_mode`、是否啟用 `subgraphs=True`，每個產出的 chunk 皆為統一結構的 `StreamPart` 字典：
    - `"type"`：`"values" | "updates" | "messages" | "custom" | "checkpoints" | "tasks" | "debug"`
    - `"ns"`：`tuple[str, ...]`，命名空間元組；根圖（root graph）為 `()`，子圖（subgraph）事件則填入路徑如 `("node_name:<task_id>",)`。
    - `"data"`：各串流模式對應的實際負載（payload）。
  - 可從 `langgraph.types` 匯入對應的 `TypedDict` 型別：`StreamPart`（以 `part["type"]` 區分的 disjoint union，支援編輯器與型別檢查器的型別縮小 type narrowing）、`ValuesStreamPart`、`UpdatesStreamPart`、`MessagesStreamPart`、`CustomStreamPart`、`CheckpointStreamPart`、`TasksStreamPart`、`DebugStreamPart`。
  - **v1（預設）與 v2 差異對照**：
    - 單一串流模式：v1 回傳原始資料（dict）；v2 回傳含 `type`、`ns`、`data` 的 `StreamPart` dict。
    - 多重串流模式：v1 回傳 `(mode, data)` 元組（JS 為 `[mode, chunk]`）；v2 維持相同 `StreamPart` dict，透過 `chunk["type"]` 分流。
    - 子圖串流（`subgraphs=True`）：v1 回傳 `(namespace, data)` 元組（JS 為 `[namespace, data]`）；v2 維持相同 `StreamPart` dict，透過 `chunk["ns"]` 檢查。
    - 多重模式 + 子圖：v1 回傳 `(namespace, mode, data)` 三元組；v2 維持相同 `StreamPart` dict。
    - `invoke()` / `ainvoke()` 回傳型別：傳入 `version="v2"` 時回傳 `langgraph.types.GraphOutput` 物件，具備 `.value`（輸出的 dict、Pydantic model 或 dataclass）與 `.interrupts`（`tuple[Interrupt, ...]`，無中斷時為空元組）屬性；若搭配非 `"values"` 的 `stream_mode`（如 `invoke(..., stream_mode="updates", version="v2")`），則回傳 `list[StreamPart]` 而非 `list[tuple]`。v1 則是將中斷資訊嵌在回傳狀態字典的 `"__interrupt__"` 鍵中（在 `GraphOutput` 上使用 `result["key"]` 或 `result["__interrupt__"]` 等字典存取方式已被標記為 deprecated）。
    - 中斷位置（stream）：v1 位於狀態字典的 `__interrupt__` 鍵；v2 位於 `values` stream part 上的 `interrupts` 欄位。
    - Pydantic 與 dataclass 狀態自動轉型：當圖的狀態定義為 Pydantic `BaseModel` 或 `@dataclass` 時，v2 的 `values` 模式會自動將 `chunk["data"]` 強制轉型（coerce）為該 model 或 dataclass 的實例，而非 v1 的普通 dict。

### 2. 所有 `stream_mode` 模式詳解
- **`values`（圖狀態完整快照）**：在圖執行的每一步（step）結束後，串流輸出完整的狀態值（`ValuesStreamPart`）。
- **`updates`（圖狀態增量更新）**：在圖執行的每一步結束後，僅串流輸出節點回傳的狀態更新（`UpdatesStreamPart`），格式為 `{"node_name": {"key": "value"}}`；同一步驟內若有多個更新會分別串流。
- **`messages`（LLM Token 串流與中繼資料）**：
  - 從圖中任何位置（包含節點、工具、子圖或 tasks）逐 token 串流大型語言模型（LLM）輸出（`MessagesStreamPart`）。即使節點內使用 `model.invoke()` 而非 `.stream()`，同樣會發出 message 事件。
  - 輸出負載為二元組 `(message_chunk, metadata)`（Python）或 `[message_chunk, metadata]`（JS/TS），其中 `message_chunk` 為 LLM 產出的 token 或訊息片段，`metadata` 為包含圖節點與 LLM 呼叫細節的字典。
  - **依標籤過濾（Filter by tags）**：初始化模型時設定 `tags=['joke']`，即可在串流時以 `metadata["tags"] == ["joke"]`（Python）或 `metadata.tags?.includes("joke")`（JS）過濾特定 LLM 呼叫的 token。
  - **排除特定 LLM 呼叫（`nostream` 標籤）**：為模型加上 `nostream` tag 可將該 LLM 呼叫完全排除在 `messages` 串流之外（模型仍會正常執行並產出結果，適合內部結構化輸出或已透過自訂通道串流、避免重複輸出的場景）。
  - **依節點過濾（Filter by node）**：檢查 `metadata["langgraph_node"] == "some_node_name"`（Python）或 `metadata.langgraph_node === "some_node_name"`（JS）以僅接收特定節點的 LLM token。
  - **停用特定聊天模型的串流**：若混合使用支援與不支援串流的模型，可在初始化模型時設定 `streaming=False`（Python）或 `streaming: false`（JS）；若該模型整合不支援 `streaming` 參數，可使用基礎類別皆提供的 `disable_streaming=True`（Python）或 `disableStreaming: true`（JS）。
- **`custom`（自訂資料與任意 LLM 串流）**：
  - Python：在節點或 `@tool` 函式內呼叫 `from langgraph.config import get_stream_writer` 取得 `writer = get_stream_writer()`，再呼叫 `writer({"custom_key": ...})` 發出任意自訂資料（`CustomStreamPart`）。
  - TypeScript / JavaScript：在節點或 `tool` 的第二個參數 `config: LangGraphRunnableConfig` 中呼叫 `config.writer({...})` 發出資料。
  - 呼叫 `.stream()` / `.astream()` 時需包含 `"custom"`（例如 `stream_mode="custom"` 或 `stream_mode=["updates", "custom"]`）。
  - **整合任意非 LangChain LLM API**：可在節點或工具內使用原生 SDK（如 `AsyncOpenAI` 的 `chat.completions.create(..., stream=True)`）迭代產出片段，並透過 `writer(chunk)` / `config.writer(chunk)` 搭配 `stream_mode="custom"` 即時串流。
- **`tools`（工具生命週期與進度事件，JS/TS 專屬模式）**：
  - 發出四種工具執行事件：`on_tool_start`（欄位：`name`, `input`, `toolCallId`）、`on_tool_event`（欄位：`name`, `data`, `toolCallId`）、`on_tool_end`（欄位：`name`, `output`, `toolCallId`）、`on_tool_error`（欄位：`name`, `error`, `toolCallId`）。
  - 若要發出 `on_tool_event` 中途進度，需將 `tool(...)` 的執行函式定義為非同步產生器（`async function* (input)`）：每次 `yield` 會向串流發出一筆 `on_tool_event`，最終的 `return` 值則會成為工具結果（`ToolMessage.content`）。回傳一般 `Promise` 的既有工具完全相容（僅發出 `on_tool_start` 與 `on_tool_end`）。
  - 在 React 中搭配 `@langchain/langgraph-sdk/react` 的 `useStream({ assistantId: "...", streamMode: ["values", "tools"] })`，可直接讀取響應式的 `stream.toolProgress` 陣列，每個 `ToolProgress` 物件包含 `name`、`state`（`"starting" | "running" | "completed" | "error"`）、`toolCallId`、`input`、`data`（最新 `on_tool_event` 資料）、`result`（`on_tool_end` 最終結果）、`error`（`on_tool_error` 錯誤）。
- **`checkpoints`（檢查點事件，Python）**：
  - 隨圖執行發出檢查點事件（`CheckpointStreamPart`），每個事件的格式與 `get_state()` 的輸出完全相同。**必須**在編譯圖時配置 checkpointer（如 `MemorySaver()`）。
- **`tasks`（任務啟停事件，Python）**：
  - 隨圖執行發出任務開始與結束事件（`TasksStreamPart`），包含正在執行的節點資訊、執行結果與任何錯誤。**必須**在編譯圖時配置 checkpointer。
- **`debug`（除錯完整資訊）**：
  - 串流圖執行期間最詳盡的資訊（`DebugStreamPart`），包含節點名稱與完整狀態；在 Python 中它結合了 `checkpoints` 與 `tasks` 事件並附加上額外 metadata。

### 3. 子圖串流（Subgraph Outputs）與 Python < 3.11 非同步限制
- **啟用子圖串流**：
  - 在父圖呼叫 `.stream()` 時設定 `subgraphs=True`（Python）或 `subgraphs: true`（JS/TS），即可同時串流父圖與所有子圖的輸出。
  - 命名空間格式為從父節點到子節點的路徑元組，例如 `("parent_node:<task_id>", "child_node:<task_id>")`（Python）或 `["parent_node:<task_id>", "child_node:<task_id>"]`（JS）。
  - **`create_agent` / `createAgent` 子圖注意事項**：此規則適用於包含 `"messages"` 在內的所有 `stream_mode`。在 Python 中，`langchain.agents.create_agent` 回傳已編譯的圖（compiled graph），將其作為節點加入父圖時即成為子圖，若未設定 `subgraphs=True`，父圖的 `stream_mode="messages"` 將**不會**發出內部代理人的 LLM token chunks；在 JS/TS 中，`langchain` 的 `createAgent` 回傳 `ReactAgent` 包裝物件，將其加入父圖節點時需傳入 `agent.graph`（`.addNode("agent", agent.graph)`），並設定 `subgraphs: true`，此時訊息區段為 `[namespace, [token, metadata]]`。
- **Python < 3.11 的 Async 限制與手動傳遞**：
  - 在 Python 3.11 之前，`asyncio.create_task` 不支援 `context` 參數，導致 LangGraph 無法自動傳播上下文變數（contextvars），對非同步串流有以下兩項強制要求：
    1. **必須手動傳遞 `RunnableConfig`**：在 async 節點函式簽名中接收 `config`（`async def call_model(state, config):`），並明確傳入非同步 LLM 呼叫如 `await model.ainvoke(..., config)`，否則回呼（callbacks）不會自動傳播。
    2. **不可在 async 節點或工具中使用 `get_stream_writer()`**：必須改在 async 節點或工具的函式簽名中宣告 `writer: StreamWriter` 參數（從 `langgraph.types` 匯入 `StreamWriter`，例如 `async def generate_joke(state: State, writer: StreamWriter):`），由 LangGraph 自動注入。

### 4. 事件串流（Event Streaming，`version="v3"`）架構與型別化投影
- **核心入口（LangGraph v1.2+ 推薦的同行程串流模型）**：
  - Python：同步呼叫 `stream = graph.stream_events(input, version="v3")` 或非同步 `stream = await graph.astream_events(input, version="v3")`。
  - TypeScript / JavaScript：`const stream = await graph.streamEvents(input, { version: "v3" })`。
  - 若要對部署在 Agent Server 後方的圖進行串流，應使用 LangSmith Streaming API。底層線級（wire-level）事件與指令格式定義於 Agent Protocol 儲存庫（PyPI 套件為 `langchain-protocol`，npm 套件為 `@langchain/protocol`）。
- **兩層式架構流程**：
  - `Pregel engine`（執行圖步驟）→ 發出 `Raw Pregel events`（`updates`, `values`, `messages`, `custom`, `checkpoints`, `tasks`, `debug`）→ 送往 `Event router`（正規化事件並路由至轉換器管線）→ 依序流經 `Stream transformers`（內建如 `ValuesTransformer`、`MessagesTransformer` 與自訂轉換器）→ 產出 `Event Stream`（提供給應用程式碼的投影事件）。
- **Run Stream 暴露的 8 種型別化投影（Projections）**：
  - `stream`：直接迭代每一筆底層 `ProtocolEvent` 協定事件。
  - `stream.messages`：串流聊天模型訊息與 token 增量。
    - Python 中 `message.text` 在同步程式碼中為可迭代物件（逐 token 輸出），也可呼叫 `str(message.text)` 取得完整文字；`message.output.usage_metadata` 取得用量；`message.node` 取得節點名稱；`message.reasoning` 暴露推理增量；`message.tool_calls` 暴露工具呼叫區段（含 `id`、`name` 與新增的 `args` 部分）。
    - JS/TS 中 `message.text` 同時為 async iterable 與 promise-like 值（可 `for await` 逐 token 迭代或 `await message.text` 取得完整文字），用量透過 `await message.usage` 取得。
  - `stream.values`：迭代每一步驟後的完整狀態快照（state snapshots）。
  - `stream.output`：等待並取得最終輸出狀態（Python 直接讀取 `stream.output`，JS 為 `await stream.output`）。
  - `stream.subgraphs`：自動探索並觀測巢狀子圖執行，無須手動剖析命名空間字串。每個子圖具備 `subgraph.graph_name`（Python）或 `subgraph.name`（JS，即編譯圖或 `create_agent(name=...)` 的名稱）、`subgraph.path` 與 `subgraph.messages`。
  - `stream.interrupts`：檢查人類介入迴圈（human-in-the-loop）的中斷負載。
  - `stream.interrupted`：布林值，檢查執行是否因等待人類輸入而暫停。暫停後可再次呼叫 `graph.stream_events(Command(resume={"decisions": [{"type": "approve"}]}), version="v3")`（需編譯時配置 checkpointer 與帶 `thread_id` 的 config）以恢復執行。
  - `stream.extensions`：消費自訂 `StreamTransformer` 註冊的擴充投影。
- **多投影並行消費**：
  - 讀取 `stream.messages` 不會消耗掉 `stream.values`、`stream.subgraphs` 或 `stream.output` 所需的事件。
  - Python 非同步：搭配 `await graph.astream_events(input, version="v3")` 與 `await asyncio.gather(consume_messages(), consume_subgraphs())`。
  - Python 同步：呼叫 `for name, item in stream.interleave("values", "messages", "subgraphs"):` 以嚴格的到達順序交錯消費多個投影。
  - JS/TS：使用 `await Promise.all([...])` 並行啟動多個 `for await` 迴圈。

### 5. `ProtocolEvent` 結構與事件通道（Channels）
- **`ProtocolEvent` 與 `ProtocolEventParams` 結構**：
  - `seq`：`int` / `number`，在單次執行內嚴格遞增的序號，用於事件排序。
  - `method`：`str` / `string`，通道名稱（channel name）。
  - `params`（`ProtocolEventParams`）：
    - `namespace`：`list[str]` / `string[]`，從根圖到發出事件之作用域的 `"<name>:<runtime_id>"` 路徑片段陣列；根圖為空陣列 `[]`（例如巢狀子圖內的工具呼叫為 `["researcher:6f4d", "tools:91ac"]`，冒號前為穩定的圖或節點名稱，冒號後為單次呼叫的 runtime ID）。
    - `timestamp`：`int` / `number`，牆鐘毫秒時間戳（可能漂移，切勿依賴此欄位排序）。
    - `node`（JS/TS 選填）：`string | undefined`，發出此事件的圖節點名稱。
    - `data`：`Any` / `unknown`，通道專屬的負載，形狀取決於 `method`。
- **10 種協定通道（Channels / `method` 值）**：
  - `values`：完整圖狀態快照。
  - `updates`：各節點的狀態增量（deltas）。
  - `messages`：以內容區塊（content-block）為中心的聊天模型輸出。`data` 的 `event` 欄位依序為 `message-start`、`content-block-start`、`content-block-delta`、`content-block-finish`、`message-finish`（可含 token usage）。每個區塊具明確邊界（前一個區塊 finish 後下一個才 start）。`content-block-delta` 的 `delta.type` 包含：
    - `text-delta`：將 `text` 附加至區塊的 `text`。
    - `reasoning-delta`：將 `reasoning` 附加至區塊的 `reasoning`。
    - `data-delta`：將 `data` 附加至區塊的 `base64`。
    - `tool-call-delta`：將 `args` 附加至區塊的 `args`。
    - `block-delta`：將 `fields` 中的每個鍵設定至區塊上，取代先前的值。
  - `tools`：工具執行事件，`data` 的 `event` 欄位為 `tool-started`、`tool-output-delta`、`tool-finished`、`tool-error`，以 tool call ID 與 `messages` 通道上的工具呼叫內容區塊關聯。
  - `lifecycle`：追蹤根執行、子圖與子代理人的狀態變更，`data` 的 `event` 欄位為 `started`、`running`、`completed`、`failed`、`interrupted`，並可包含選填的 `graph_name`、`error` 與 `cause`（描述子作用域啟動原因，如父工具呼叫、fan-out send 或邊轉換）。
  - `checkpoints`：供分支（branching）與時間旅行（time travel）使用的輕量級檢查點信封。
  - `input`：人類介入迴圈的輸入請求與回應。
  - `tasks`：Pregel 任務建立與結果事件。
  - `custom`：圖程式碼透過 `get_stream_writer()` 發出的使用者自訂負載。
  - `custom:<name>`：應用程式定義的 `StreamTransformer` 具名 `StreamChannel` 輸出。

### 6. 自訂投影：`StreamTransformer` 與 `StreamChannel`
- **版本需求**：Python 需 `langgraph>=1.2`（從 `langgraph.stream` 匯入 `ProtocolEvent, StreamChannel, StreamTransformer`）；JS/TS 需 `@langchain/langgraph>=1.3.1`（從 `@langchain/langgraph` 匯入）。
- **`StreamTransformer` 介面與生命週期**：
  - `required_stream_modes`（Python 類別屬性）：如 `("custom",)`、`("tools",)`、`("messages",)`。執行期會取所有已註冊轉換器之 `required_stream_modes` 的聯集作為底層 `.stream()` 的 `stream_mode` 參數；**沒有任何轉換器要求的模式絕不會被發出**。合法值為 `"messages"`, `"tools"`, `"custom"`, `"values"`, `"updates"`, `"checkpoints"`, `"tasks"`, `"debug"`。
  - `init(self) -> dict` / `init(): TProjection`：建立並回傳投影物件，掛載於 `stream.extensions` 下。
  - `process(self, event: ProtocolEvent) -> bool`：按註冊順序觀測每一筆協定事件（亦可就地修改 `event["params"]["data"]`，例如抹除 PII 個資）。回傳 `True` 保留該事件；僅在刻意要抑制（suppress）原始事件使其不進入 run stream 時回傳 `False`。
  - `finalize(self) -> None`：在串流成功結束時關閉或解析非 `StreamChannel` 的投影（如 Promise）。
  - `fail(self, err: BaseException) -> None`：在執行失敗時將錯誤傳播給非 `StreamChannel` 的投影。
- **`StreamChannel` 具名與匿名通道**：
  - **匿名通道（`StreamChannel()` / `new StreamChannel<T>()`）**：僅作為旁路投影（side-channel projection）暴露於 `stream.extensions`，不會流入主協定事件流，適合存放 Promise、async iterables、類別實例等不可序列化的同行程控制代碼。
  - **具名通道（`StreamChannel("name")` / `new StreamChannel<T>("name")` / `StreamChannel.remote<T>("name")`）**：除了暴露於 `stream.extensions` 外，每次呼叫 `.push(payload)` 皆會同時轉發為一筆 `method` 為 `"custom:<name>"` 的協定事件進入主事件流（因此負載必須可序列化），並可跨網路傳送至前端客戶端。
  - 通道生命週期由 stream handler 管理：只要 `init()` 回傳了 `StreamChannel`，執行結束時 handler 會自動關閉或將其標記為失敗，轉換器只需呼叫 `.push(...)`。
- **註冊方式與內建轉換器**：
  - 呼叫時註冊：`graph.stream_events(input, version="v3", transformers=[...])` 或 `graph.streamEvents(input, { version: "v3", transformers: [...] })`。
  - 編譯時註冊：`builder.compile(transformers=[...])` 或在建立代理人時透過 `create_agent(..., transformers=[...])`（Python）與 `createAgent({ ..., streamTransformers: [...] })`（JS）。
  - **內建 `ToolCallTransformer`（Python）**：從 `langgraph.prebuilt` 匯入 `ToolCallTransformer` 並註冊後，可在一般 `StateGraph` 的事件串流上直接使用 `stream.tool_calls` 迭代讀取 `tool_call.tool_name` 與 `tool_call.input`。

### 7. 前端整合：圖執行視覺化（Graph Execution Cards）與自訂串流通道
- **前端框架 SDK 支援**：v1 前端 SDK 套件包含 `@langchain/react`、`@langchain/vue`、`@langchain/svelte`（提供 `useStream`、`useMessages`、`useExtension`、`useChannel`、`useToolCalls`、`useValues`）以及 `@langchain/angular`（提供 `injectStream`、`injectExtension`、`injectChannel`）。
- **動態探索圖節點（`stream.subgraphs` 與 `SubgraphDiscoverySnapshot`）**：
  - 前端無須寫死（hardcode）節點清單或假設節點名稱與狀態鍵名一致：呼叫 `[...stream.subgraphs.values()]`（Vue 為 `[...stream.subgraphs.value.values()]`，Angular 為 `[...this.stream.subgraphs().values()]`）即可自動取得當前執行緒觀測到的所有節點快照 `SubgraphDiscoverySnapshot`。因條件分支而跳過的節點不會出現在 `stream.subgraphs` 中。
  - 每個 `SubgraphDiscoverySnapshot` 包含：
    - `node.id`：節點唯一識別碼。
    - `node.nodeName`：節點名稱（如 `"classify"`、`"research"`、`"analyze"`、`"synthesize"`）。
    - `node.status`：節點目前狀態，型別為 `"pending" | "running" | "complete" | "error"`。
- **路由節點專屬串流內容（`useMessages(stream, node)`）**：
  - 將 `stream` 與 `node`（`SubgraphDiscoverySnapshot`）傳入 `useMessages(stream, node)`，即可開啟針對該節點命名空間的作用域訂閱（元件卸載時自動釋放訂閱），並透過 `messages.find(AIMessage.isInstance)?.text` 讀取該節點的即時串流或最終訊息內容，支援平行圖路徑而不必猜測訊息順序；若需讀取完整圖狀態欄位（如最終的 `synthesis` 欄位），則使用 `stream.values`。
- **前端讀取自訂通道（`useExtension` vs `useChannel`）**：
  - **`useExtension<T>(stream, "channel-name", target?)`**（Angular 為 `injectExtension`）：
    - 訂閱 `custom:<name>` 通道（**傳入裸通道名稱**如 `"redaction-stats"`，不加 `custom:` 前綴）。
    - 回傳轉換器推送的**最新一筆已解包（unwrapped）且具型別的負載**（`T | undefined`，在收到第一筆資料前為 `undefined`；Vue 為 `Ref`、Angular 為 signal）。第三個選填參數 `target` 可將訂閱限定於特定節點命名空間。適合即時統計計數器、進度百分比或狀態徽章。
  - **`useChannel(stream, ["custom:channel-name"], target?, options?)`**（Angular 為 `injectChannel`）：
    - 原始事件的逃生門（escape hatch），可同時訂閱一個或多個通道（**必須傳入完整通道 ID** 陣列，如 `["custom:redaction-stats"]`）。
    - 回傳有界緩衝區的原始協定事件陣列 `Event[]`，需自行從 `event.params?.data` 解包負載。
    - `options` 參數支援：`bufferSize`（預設為 `"default"`，亦可傳入數字如 `200` 設定最大緩衝事件數，超過上限時丟棄最舊事件）與 `replay`（預設為 `true`，掛載時重播該通道先前已見過的事件，而非僅接收後續即時事件）。適合事件日誌、稽核軌跡（audit trail）或需要歷史紀錄的場景。

## 相關頁面
- [[guides/langgraph-agentic-rag-and-sql-agent]]
- [[guides/langgraph-deployment-and-studio]]
- [[versions/langgraph-backward-compatibility-and-changelogs]]

## 出處
- docs/langgraph/streaming.md
- docs/langgraph/event-streaming.md
- docs/langgraph/frontend/graph-execution.md
- docs/langgraph/frontend/custom-stream-channels.md
