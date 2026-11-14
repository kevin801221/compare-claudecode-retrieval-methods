# LangChain, LangGraph, and Deep Agents: Python vs TypeScript/JavaScript Comparison

別名：LangChain 生態系 Python 與 TypeScript 差異比較、Python vs JS/TS 對照表、create_agent vs createAgent、StateGraph Python vs TypeScript、create_deep_agent vs createDeepAgent
框架：deepagents、langchain、langgraph

## 摘要
LangChain、LangGraph 與 Deep Agents 皆同步提供 Python 與 TypeScript/JavaScript（Node.js 20+）SDK。兩者在核心概念、架構與執行語意上完全對齊，但在套件命名、命名慣例（`snake_case` vs `camelCase`）、型別系統與狀態 Schema 定義（`TypedDict` / `Pydantic` / `Annotated` vs `Zod` / `StateSchema` / `ReducedValue`）、裝飾器 vs 高階函式，以及部分執行期細節上存在明確差異。

## 重點

### 1. 套件名稱與安裝對照表
| 功能模組 | Python 套件 | TypeScript / JavaScript 套件 |
|---|---|---|
| **LangChain 核心與代理** | `langchain`、`langchain-core` | `langchain`、`@langchain/core` |
| **LangGraph 核心** | `langgraph` | `@langchain/langgraph` |
| **Deep Agents SDK** | `deepagents`（含直譯器：`deepagents[interpreter]`） | `deepagents` 或 `@langchain/deepagents` |
| **MCP 轉接器** | `langchain-mcp-adapters` | `@langchain/mcp-adapters` |
| **Checkpointer（SQLite / Postgres）** | `langgraph-checkpoint-sqlite`、`langgraph-checkpoint-postgres` | `@langchain/langgraph-checkpoint-sqlite`、`@langchain/langgraph-checkpoint-postgres` |
| **LangGraph CLI / Server SDK** | `langgraph-cli[inmem]`、`langgraph-sdk` | `@langchain/langgraph-cli`、`@langchain/langgraph-sdk` |
| **評估（Evals）** | `agentevals`、`langsmith` | `agentevals`、`langsmith` |

### 2. 核心工廠函式與 API 命名對照
| 概念 / 功能 | Python API (`snake_case`) | TypeScript / JavaScript API (`camelCase`) |
|---|---|---|
| **建立標準代理** | `from langchain.agents import create_agent` | `import { createAgent } from "langchain"` |
| **建立 Deep Agent** | `from deepagents import create_deep_agent` | `import { createDeepAgent } from "deepagents"` |
| **初始化模型** | `init_chat_model("anthropic:claude-sonnet-4-6")` | `await initChatModel("anthropic:claude-sonnet-4-6")`（注意：JS 為非同步） |
| **定義工具** | `@tool` 裝飾器（`from langchain.tools import tool`） | `tool(fn, { name, description, schema })`（`import { tool } from "langchain"`） |
| **系統提示詞參數** | `system_prompt="..."` | `systemPrompt: "..."` |
| **結構化輸出設定** | `response_format=ProviderStrategy(...)` / `ToolStrategy(...)` | `responseFormat: providerStrategy(...)` / `toolStrategy(...)` |
| **結構化輸出結果讀取** | `result["structured_response"]` | `result.structuredResponse` |
| **狀態與上下文 Schema** | `state_schema=...`, `context_schema=...` | `stateSchema: ...`, `contextSchema: ...` |
| **訊息內容區塊** | `message.content_blocks` | `message.contentBlocks` |
| **取得串流寫入器** | `get_stream_writer()` 或 `runtime.stream_writer` | `config.writer` 或 `runtime.writer` |

### 3. LangGraph 狀態（State）與 Reducer 定義差異
- **Python 狀態定義**：
  - 支援 `TypedDict`、`dataclass` 或 Pydantic `BaseModel`。
  - 使用 `typing.Annotated[Type, reducer_fn]` 指定通道的 Reducer（例如 `messages: Annotated[list[AnyMessage], add_messages]` 或 `items: Annotated[list[str], operator.add]`），或直接繼承 `MessagesState`。
  - 繞過 Reducer 直接覆寫通道值：使用 `Overwrite(value)`（或 `{"key": Overwrite(new_val)}`）。
- **TypeScript / JavaScript 狀態定義**：
  - 使用 Zod Schema 搭配 `@langchain/langgraph` 的 `StateSchema`（或 `Annotation.Root`）與 `MessagesValue` / `MessagesAnnotation`。
  - 使用 `new ReducedValue(z.array(z.string()), { reducer: (a, b) => a.concat(b) })` 定義具備 Reducer 的欄位；使用 `new UntrackedValue(...)` 定義不寫入檢查點的暫存欄位。
  - 繞過 Reducer 直接覆寫：使用 `new Overwrite(value)`。

### 4. LangChain Middleware 定義與內建類別/函式對照
- **自訂 Middleware**：
  - **Python**：使用裝飾器 `@before_agent`、`@before_model`、`@after_model`、`@after_agent`、`@wrap_model_call`、`@wrap_tool_call`、`@dynamic_prompt`，或繼承 `AgentMiddleware` 類別；跳轉控制回傳 `{"jump_to": "tools" | "model" | "end"}`。
  - **TypeScript**：使用 `createMiddleware({ name, stateSchema, contextSchema, beforeAgent, beforeModel, afterModel, afterAgent, wrapModelCall, wrapToolCall })`；跳轉控制回傳 `{ jumpTo: "tools" | "model" | "end" }`。
- **內建 Middleware 命名規則**：
  - Python 採用 `PascalCase` 類別（如 `SummarizationMiddleware(...)`、`HumanInTheLoopMiddleware(...)`、`PIIMiddleware(...)`、`ModelFallbackMiddleware(...)`、`TodoListMiddleware(...)`）。
  - TypeScript 採用 `camelCase` 工廠函式（如 `summarizationMiddleware(...)`、`humanInTheLoopMiddleware(...)`、`piiMiddleware(...)`、`modelFallbackMiddleware(...)`、`todoListMiddleware(...)`）。

### 5. Functional API 與執行期細節差異
- **Functional API（`@entrypoint` / `@task`）**：
  - **Python**：使用裝飾器 `@entrypoint(checkpointer=..., store=...)` 與 `@task(retry_policy=..., cache_policy=...)`；在函式參數中透過 `previous: Any = None` 存取上一輪儲存值，透過 `entrypoint.final(value=..., save=...)` 分離回傳值與檢查點保存值。
  - **TypeScript**：使用高階函式 `entrypoint({ name, checkpointer, store }, async (input, config) => ...)` 與 `task({ name, retry }, async (...) => ...)`；透過 `getPreviousState<T>()` 讀取上一輪狀態。
- **非同步與串流差異**：
  - **Python**：同時具備同步（`invoke`、`stream`、`batch`、`get_state`、`update_state`）與非同步（`ainvoke`、`astream`、`abatch`、`aget_state`、`aupdate_state`）方法；在 Python < 3.11 下進行非同步串流時，節點內部呼叫子 Runnable 必須顯式傳遞 `config`。
  - **TypeScript**：全面採用 `async/await`（`await graph.invoke(...)`、`await graph.stream(...)`、`await graph.getState(...)`、`await graph.updateState(...)`），且額外支援在工具中使用 `async function*` 產生器搭配 `streamMode: "tools"` 即時產出工具進度（前端透過 `useStream` 的 `toolProgress` 接收）。

## 相關頁面
- [[concepts/langchain-overview-and-architecture]]
- [[concepts/langchain-middleware]]
- [[entities/langchain-builtin-middleware]]
- [[concepts/langgraph-graph-api-state-and-nodes]]
- [[concepts/langgraph-functional-api-and-pregel]]
- [[concepts/deepagents-overview]]
- [[comparisons/agent-sdk-python-vs-typescript]]

## 出處
- docs/langchain/overview.md
- docs/langchain/agents.md
- docs/langchain/models.md
- docs/langchain/tools.md
- docs/langchain/structured-output.md
- docs/langchain/middleware/overview.md
- docs/langchain/middleware/built-in.md
- docs/langchain/middleware/custom.md
- docs/langgraph/graph-api-state.md
- docs/langgraph/functional-api.md
- docs/langgraph/streaming.md
- docs/deepagents/overview.md
- docs/deepagents/customization.md
