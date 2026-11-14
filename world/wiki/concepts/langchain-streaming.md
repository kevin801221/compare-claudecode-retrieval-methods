# LangChain Streaming and Event Streaming

別名：LangChain 串流與事件串流、`stream()`、`astream()`、`stream_mode`、`streamMode`、`stream_events`、`streamEvents`、`StreamPart`、`version="v2"`、`version="v3"`
框架：langchain

## 摘要
LangChain 提供兩套互補的串流介面：其一是基於底層 LangGraph Pregel 的 `stream()` / `astream()`（支援 `updates`、`messages`、`custom` 等 `stream_mode` 以及統一結構的 `version="v2"` `StreamPart` 格式）；其二是 LangChain v1.3 引入、推薦新應用程式採用的高階型別化投影 API **Event Streaming**（透過 `stream_events(..., version="v3")` / `streamEvents(..., { version: "v3" })` 提供 `.messages`、`.tool_calls` / `.toolCalls`、`.values`、`.subagents`、`.subgraphs`、`.extensions` 與 `.output` 等獨立串流投影）。

## 重點

### 低階串流模式（`stream()` / `astream()` 與 `stream_mode` / `streamMode`）
- **支援的三大核心 `stream_mode`（Python 傳入 `stream_mode=...`，JS/TS 傳入 `{ streamMode: ... }`）**：
  1. **`"updates"`（代理步驟進度 Agent progress）**：在每個代理步驟（node）完成後發出狀態更新。例如單次工具呼叫會依序發出：`model` 節點更新（含帶 `tool_calls` 的 `AIMessage`）→ `tools` 節點更新（含 `ToolMessage`）→ `model` 節點更新（最終 `AIMessage`）。
  2. **`"messages"`（LLM Tokens 與中繼資料）**：從任何呼叫 LLM 的圖節點串流產出 `(token, metadata)` 元組，其中 `token` 為 `AIMessageChunk`（含 `.text`、`.tool_call_chunks`、`.content_blocks` / `.contentBlocks`），`metadata` 包含節點名稱 `metadata["langgraph_node"]` 與代理名稱 `metadata.get("lc_agent_name")`。
  3. **`"custom"`（自訂更新 Custom updates）**：從工具或節點內部透過串流寫入器發送自訂訊號：
     - Python：使用 `from langgraph.config import get_stream_writer` 取得 `writer = get_stream_writer()`（或從 `ToolRuntime` 取得 `runtime.stream_writer`）並呼叫 `writer(...)`。
     - JS/TS：從工具的第二個參數 `config: LangGraphRunnableConfig`（或 `ToolRuntime`）呼叫 `config.writer?.(...)`。
     - 限制：使用 stream writer 的工具必須在 LangGraph 執行上下文內呼叫。
- **多重串流模式（Stream multiple modes）**：可傳入列表如 `stream_mode=["updates", "messages", "custom"]`（Python）或 `{ streamMode: ["updates", "messages", "custom"] }`（JS/TS）。在 v1 預設格式下會產出 `(mode, chunk)` / `[streamMode, chunk]` 元組。
- **Python `version="v2"` 統一串流格式（需 LangGraph 1.1+）**：
  - 在 `agent.stream(..., version="v2")` 或 `astream(..., version="v2")` 下，無論指定單一或多個 `stream_mode`，每個產出的 chunk 皆為統一結構的 **`StreamPart`** 字典，包含三個鍵：
    - `chunk["type"]`：串流模式名稱（如 `"updates"`、`"messages"`、`"custom"`）。
    - `chunk["ns"]`：命名空間元組。
    - `chunk["data"]`：該模式的實際資料 payload。
  - 在 `agent.invoke(..., version="v2")` 下，會回傳 **`GraphOutput`** 物件，具備 `.value`（最終狀態 dict、Pydantic model 或 dataclass）與 `.interrupts`（`Interrupt` 物件元組）兩個屬性。

### 常見串流實戰模式（Common Streaming Patterns）
- **串流思考/推理 Tokens（Streaming thinking / reasoning tokens）**：
  - 使用 `stream_mode="messages"`，在 `token.content_blocks`（Python）或 `token.contentBlocks`（JS/TS）中過濾 `block["type"] == "reasoning"`，即可跨供應商（自動正規化 Anthropic `thinking` 與 OpenAI `reasoning` summaries）即時印出 `block["reasoning"]`。
- **同時串流工具呼叫片段與完成訊息（Streaming tool calls & Completed messages）**：
  - 結合 `stream_mode=["messages", "updates"]`：由 `"messages"` 模式接收 `AIMessageChunk.tool_call_chunks` 增量片段；由 `"updates"` 模式接收 `"model"` 與 `"tools"` 節點完成後的完整 `AIMessage.tool_calls` 與 `ToolMessage`。
  - 若完成訊息未記錄在 state 中（例如在 `@after_agent` 護欄 middleware 內額外呼叫 `safety_model`），可透過 `get_stream_writer()` 將結果發送至 `"custom"` 模式，或在迴圈中用 `full_message = token if full_message is None else full_message + token` 累加，並在 `token.chunk_position == "last"` 時讀取 `full_message.tool_calls`。
- **搭配 Human-in-the-loop（中斷與恢復串流）**：
  - 代理配置 `HumanInTheLoopMiddleware(interrupt_on={"get_weather": True})` 與 `checkpointer=InMemorySaver()`。
  - 在 `"updates"` 模式中檢查 `if source == "__interrupt__":`，從 `interrupt.value["action_requests"]` 讀取待審核請求，組裝 `decisions = {interrupt.id: {"decisions": [{"type": "edit", "edited_action": {"name": ..., "args": ...}}, {"type": "approve"}]}}`（決策順序必須與 `action_requests` 順序一致），最後以 `agent.stream(Command(resume=decisions), config=config, ...)` 恢復串流。
- **從子代理串流（Streaming from sub-agents）**：
  - 為每個 `create_agent` 設定唯一的 `name`（如 `name="supervisor"`、`name="weather_agent"`），並在呼叫外層 `agent.stream(..., subgraphs=True)` 時啟用 `subgraphs=True`（JS 若將 `createAgent` 包裝為父 `StateGraph` 的節點，需傳入 `agent.graph` 並設定 `subgraphs: true`），即可在 `"messages"` 模式透過 `metadata.get("lc_agent_name")` 辨識當前發話的代理。
- **停用特定模型的串流（Disable streaming）**：
  - 初始化模型時設定 `streaming=False`（Python） / `streaming: false`（JS/TS）；若該模型整合不支援 `streaming` 參數，則使用基礎類別皆支援的 `disable_streaming=True`（Python） / `disableStreaming: true`（JS/TS）。

### Event Streaming 高階型別化投影 API（`version="v3"`，LangChain v1.3+）
- **核心呼叫方式**：
  - Python：同步呼叫 `stream = agent.stream_events(input, version="v3")` 或非同步呼叫 `stream = await agent.astream_events(input, version="v3")`。
  - JS/TS：呼叫 `const stream = await agent.streamEvents(input, { version: "v3" })`。
- **所有支援的型別化投影（Typed Projections，Python vs. JS/TS）**：
  1. **`stream.messages`**：每次 LLM 呼叫產出一個訊息串流物件（Python 為 `ChatModelStream`），具備 `message.node`（節點名稱）與以下子屬性：
     - `message.text`：文字增量 deltas；在 Python 同步投影中可直接呼叫 `str(message.text)` 排空取得最終完整文字，在非同步或 JS/TS 中可 `await message.text`。
     - `message.reasoning`：模型推理增量 deltas。
     - `message.tool_calls`（Python） / `message.toolCalls`（JS/TS）：串流工具呼叫參數片段 `tool_call_chunk`（在 `langchain-core>=1.6.13` 中每個 chunk 的 `args` 僅包含新增的片段，舊版則包含累積至今的參數）；在 Python 中呼叫 `message.tool_calls.get()` 可取得最終解析完成的工具呼叫列表。
     - `message.output`：模型呼叫完成後的最終 `AIMessage` 物件（Python 可從 `message.output.usage_metadata` 讀取 token 用量）。
     - `message.usage`（**僅 JS/TS 提供**）：`await message.usage` 直接取得 token usage metadata。
  2. **`stream.tool_calls`（Python） / `stream.toolCalls`（JS/TS）**：工具執行生命週期串流。每個 `call` 暴露：
     - Python：`call.tool_name`、`call.input`、`call.output_deltas`（輸出增量）、`call.output`（最終輸出）、`call.error`（錯誤資訊）。
     - JS/TS：`call.name`、`call.input`、`await call.output`、`await call.error`。
  3. **`stream.subagents` vs. `stream.subgraphs`**：
     - **`stream.subagents`**：專門呈現具名（設定了 `name=`）之 `create_agent` / `createAgent` 子代理執行，自動過濾掉普通 `StateGraph` 子圖。每個 `subagent` handle 具備 `.name`、`.cause`（觸發該子代理的工具呼叫）、`.messages`、`.tool_calls` / `.toolCalls`、`.output`，以及 Python 的 `.values` 或 JS/TS 的巢狀 `.subagents`。
     - **`stream.subgraphs`**：涵蓋所有巢狀圖（包含子代理與普通 `StateGraph` 子圖；普通子圖在 `.compile(name=...)` 設定的名稱會顯示於 `subagent.graph_name`）。
  4. **`stream.values` 與 `stream.output`**：
     - `stream.values`：代理狀態快照（state snapshots）串流。
     - `stream.output`（JS/TS 為 `await stream.output`）：代理最終狀態（final agent state）。
  5. **同時消費多個投影（Multiple projections）与原始事件（Raw events）**：
     - Python 非同步：使用 `await agent.astream_events(input, version="v3")` 搭配 `await asyncio.gather(consume_messages(), consume_tool_calls())`。
     - Python 同步：使用 `for name, item in stream.interleave("messages", "tool_calls", "values"):` 交錯讀取。
     - JS/TS：使用 `await Promise.all([ ... ])` 並行消費多個 `for await` 迴圈。
     - 原始協定事件（Raw protocol events）：直接迭代 `for event in stream:`（Python）或 `for await (const event of stream)`（JS/TS），可存取 `event["method"]`、`event["params"]["namespace"]`、`event["params"]["data"]`。
  6. **自訂轉換器投影（`stream.extensions` 與 Middleware 註冊）**：
     - 可在呼叫時傳入 `transformers=[ToolActivityTransformer]`，並從 `stream.extensions["tool_activity"]`（Python）或 `stream.extensions.toolActivity`（JS/TS）讀取。
     - **在 Middleware 註冊轉換器工廠**（Python 需 `langchain>=1.3.2`，在 `AgentMiddleware` 子類別設定 `transformers = (ToolActivityTransformer,)`，工廠簽章為 `Callable[[tuple[str, ...]], StreamTransformer]`，接收 `scope` 元組；JS/TS 需 `langchain@1.4.3+`，在 `createMiddleware` 傳入 `streamTransformers: [toolActivityTransformer]`，工廠簽章為零參數 `() => StreamTransformer<any>`）。
     - **編譯期轉換器執行順序**：1. 內建 `ToolCallTransformer` → 2. Middleware 註冊的工廠（依 middleware 順序）→ 3. `create_agent` / `createAgent` 呼叫端傳入的 `transformers` / `streamTransformers`。
     - **PII 即時串流遮罩**：內建 `PIIMiddleware("email", strategy="redact", apply_to_output=True)` 即利用此機制註冊轉換器，在文字 deltas、工具呼叫參數、工具輸出與狀態快照離開執行期前即時抹除敏感個資，彌補單靠 `after_model` 狀態級遮罩會讓原始 PII 外洩至即時串流讀取端的空窗。

## 相關頁面
- [[concepts/langchain-overview-and-architecture]]
- [[concepts/langchain-agents-and-runtime]]
- [[entities/langchain-models]]
- [[entities/langchain-messages]]
- [[entities/langchain-tools]]

## 出處
- docs/langchain/streaming.md
- docs/langchain/event-streaming.md
