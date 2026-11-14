# LangGraph Error Codes Reference

別名：LangGraph 錯誤代碼與疑難排解、GRAPH_RECURSION_LIMIT、INVALID_CHAT_HISTORY、INVALID_CONCURRENT_GRAPH_UPDATE、INVALID_GRAPH_NODE_RETURN_VALUE、MISSING_CHECKPOINTER、MULTIPLE_SUBGRAPHS
框架：langgraph

## 摘要
本頁彙整 LangGraph 執行與編譯期間常見的六個錯誤代碼（`GRAPH_RECURSION_LIMIT`、`INVALID_CHAT_HISTORY`、`INVALID_CONCURRENT_GRAPH_UPDATE`、`INVALID_GRAPH_NODE_RETURN_VALUE`、`MISSING_CHECKPOINTER` 與 `MULTIPLE_SUBGRAPHS`），詳列其觸發情境、根本原因，以及在 Python 與 TypeScript/JavaScript 中的具體修復方式與程式碼範例。

## 重點

### `GRAPH_RECURSION_LIMIT`（`errors/GRAPH_RECURSION_LIMIT.md`）
- **觸發原因**：
  - `StateGraph` 在到達停止條件（stop condition）前已達到最大允許步數（maximum number of steps）。
  - 常見於無窮迴圈（例如 `add_edge("a", "b")` 與 `add_edge("b", "a")` 互相循環而無終止條件），但複雜圖形也可能自然達到預設限制。
- **疑難排解與修復**：
  - 若非預期多次迭代，請檢查圖形邏輯是否存在無限循環（cycle）。
  - 若為合法複雜圖形，可在呼叫 `invoke` 時於 `config` 物件傳入更高的遞迴限制：
    - Python：`graph.invoke({...}, {"recursion_limit": 1000})`
    - TypeScript/JavaScript：`await graph.invoke({...}, { recursionLimit: 1000 })`

### `INVALID_CHAT_HISTORY`（`errors/INVALID_CHAT_HISTORY.md`）
- **觸發原因**：
  - 在預建的 `create_agent`（Python）／`createAgent`（TypeScript）中，當 `call_model`（Python）／`callModel`（TypeScript）圖形節點收到格式錯誤（malformed）的訊息列表時拋出。
  - 具體而言，當訊息列表中存在帶有 `tool_calls` 的 `AIMessage`（LLM 請求呼叫工具），但後續**沒有對應的 `ToolMessage`**（回傳給 LLM 的工具執行結果）時即屬格式錯誤。
  - 常見的兩種成因：
    1. 呼叫圖形時手動傳入了格式錯誤的訊息列表，例如 `graph.invoke({'messages': [AIMessage(..., tool_calls=[...])]})`（JS：`graph.invoke({messages: [new AIMessage({..., tool_calls: [...]})]})`）。
    2. 圖形在收到來自 `tools` 節點的更新（即 `ToolMessage` 列表）之前發生了中斷（interrupt）——例如在 `create_agent` / `createAgent` 設定了 `interrupt_before = ['tools']` / `interruptBefore: ['tools']`，或是其中一個工具拋出未被 `ToolNode`（`"tools"`）處理的錯誤——而開發者接著以非 `None` / `null` 且非 `ToolMessage` 的輸入（例如 `HumanMessage`）再次呼叫了 `graph.invoke({'messages': [HumanMessage(...)]}, config)`。
- **疑難排解與修復**：
  1. 切勿以格式錯誤的訊息列表呼叫圖形。
  2. 若因手動設定或錯誤導致中斷，可採取以下兩種方式之一：
     - **方式 A（提供 `ToolMessage` 從頭執行）**：提供對應既有 tool calls 的 `ToolMessage` 物件並呼叫 `graph.invoke({'messages': [ToolMessage(...)]})`（JS：`graph.invoke({messages: [new ToolMessage(...)]})`）。**注意**：這會將訊息附加至歷史紀錄並**從 `START` 節點重新執行圖形**。
     - **方式 B（手動更新狀態並從中斷處恢復）**：
       1. 取得最新訊息列表：Python 呼叫 `graph.get_state(config)`；TypeScript 呼叫 `graph.getState(config)`。
       2. 修改訊息列表：移除 `AIMessage` 中未回答的 `tool_calls`，**或者**補上帶有對應 `tool_call_id`（Python）／`toolCallId`（TypeScript）的 `ToolMessage` 物件。
       3. 寫回修改後的訊息列表：Python 呼叫 `graph.update_state(config, {'messages': ...})`；TypeScript 呼叫 `graph.updateState(config, {messages: ...})`。
       4. 恢復圖形執行：Python 呼叫 `graph.invoke(None, config)`；TypeScript 呼叫 `graph.invoke(null, config)`。

### `INVALID_CONCURRENT_GRAPH_UPDATE`（`errors/INVALID_CONCURRENT_GRAPH_UPDATE.md`）
- **觸發原因**：
  - `StateGraph` 在同一個步驟（single step）中（例如使用 fanout 或從 `START` 同時連向 `node` 與 `other_node` 進行平行執行），有多個節點同時針對**不支援並行更新（未定義 reducer）**的同一個狀態屬性（如 `some_key: str` / `someKey: z.string()`）回傳了更新值，導致內部狀態不知如何合併而拋出錯誤。
- **疑難排解與修復**：
  - 若圖形會平行執行多個節點並寫入同一狀態鍵，必須為該狀態鍵定義合併多個值的 **reducer**：
    - **Python**：使用 `typing.Annotated` 與 `operator.add`，例如 `some_key: Annotated[list, operator.add]`。
    - **TypeScript/JavaScript**：使用 `StateSchema` 搭配 `ReducedValue`，例如：
      ```typescript
      const State = new StateSchema({
        someKey: new ReducedValue(
          z.array(z.string()).default(() => []),
          {
            inputSchema: z.array(z.string()),
            reducer: (existing, update) => existing.concat(update),
          }
        ),
      });
      ```

### `INVALID_GRAPH_NODE_RETURN_VALUE`（`errors/INVALID_GRAPH_NODE_RETURN_VALUE.md`）
- **觸發原因**：
  - `StateGraph` 從節點收到了非字典（Python non-dict）或非物件（TypeScript non-object）的回傳值。
  - 例如節點回傳了列表／陣列 `return ["whoops"]`，呼叫 `invoke` 時會拋出：
    - Python：`InvalidUpdateError: Expected dict, got ['whoops']`
    - TypeScript：`InvalidUpdateError: Expected object, got ['whoops']`
- **疑難排解與修復**：
  - 圖形中的節點**必須**回傳包含一個或多個已在 state 中定義之鍵的 `dict`（Python）或 `object`（TypeScript）。若節點內有複雜分支邏輯，請確保所有程式碼路徑（all code paths）皆回傳合法的狀態字典／物件。

### `MISSING_CHECKPOINTER`（`errors/MISSING_CHECKPOINTER.md`）
- **觸發原因**：
  - 嘗試使用 LangGraph 內建的持久化（persistence）功能，但在呼叫 `StateGraph` 的 `compile()` 方法或定義 `@entrypoint` / `entrypoint` 時漏傳了 `checkpointer`。
- **疑難排解與修復**：
  - 初始化並傳入 checkpointer（例如 `InMemorySaver`）：
    - **Python**：
      - Graph API：`from langgraph.checkpoint.memory import InMemorySaver` -> `checkpointer = InMemorySaver()` -> `graph = StateGraph(...).compile(checkpointer=checkpointer)`
      - Functional API：`@entrypoint(checkpointer=checkpointer)`
    - **TypeScript/JavaScript**：
      - Graph API：`import { InMemorySaver, StateGraph } from "@langchain/langgraph"` -> `const checkpointer = new InMemorySaver()` -> `const graph = new StateGraph(...).compile({ checkpointer })`
      - Functional API：`const workflow = entrypoint({ checkpointer, name: "workflow" }, async (messages: string[]) => { ... })`
  - 或者直接使用託管的 LangGraph API（自動處理所有持久化基礎設施，無需手動配置 checkpointers）。

### `MULTIPLE_SUBGRAPHS`（`errors/MULTIPLE_SUBGRAPHS.md`）
- **觸發原因**：
  - 當在**同一個節點內部多次呼叫子圖（call a subgraph inside a node multiple times）**，且該子圖在編譯時設定了 `checkpointer=True`（Python）／`checkpointer: true`（TypeScript）（即 continuations mode）時觸發。
- **疑難排解與修復（依需求三選一）**：
  1. **不需要 interrupts（Don't need interrupts?）**：設定 `checkpointer=False`（Python：`subgraph_builder.compile(checkpointer=False)`）／`checkpointer: false`（TypeScript：`subgraphBuilder.compile({ checkpointer: false })`）完全停用子圖檢查點。
  2. **需要 interrupts 但不需要跨呼叫持久化（Need interrupts but not cross-invocation persistence?）**：省略 `checkpointer` 參數以使用預設的繼承模式（Python：`subgraph_builder.compile()`；TypeScript：`subgraphBuilder.compile()`）。每次呼叫都會獲得獨立的唯一 namespace，因此支援平行執行；子圖每次都會全新啟動但可使用 `interrupt()`。
  3. **需要跨呼叫持久化（Need cross-invocation persistence?）**：保留 `checkpointer=True` / `checkpointer: true`。LangGraph 會為每次呼叫分配基於位置的 namespace 後綴（`calling_node`、`calling_node|1` 等）以避免衝突；若需要穩定、基於名稱的 namespaces，請將每個子圖包裝在具有唯一節點名稱的獨立節點中。

## 相關頁面
- [[concepts/langgraph-overview-and-workflows]]
- [[concepts/langgraph-graph-api-state-and-nodes]]
- [[concepts/langgraph-control-flow-send-and-command]]
- [[concepts/langgraph-functional-api-and-pregel]]

## 出處
- docs/langgraph/errors/GRAPH_RECURSION_LIMIT.md
- docs/langgraph/errors/INVALID_CHAT_HISTORY.md
- docs/langgraph/errors/INVALID_CONCURRENT_GRAPH_UPDATE.md
- docs/langgraph/errors/INVALID_GRAPH_NODE_RETURN_VALUE.md
- docs/langgraph/errors/MISSING_CHECKPOINTER.md
- docs/langgraph/errors/MULTIPLE_SUBGRAPHS.md
