# LangGraph Interrupts and Time Travel

別名：中斷與時光旅行、Human-in-the-loop、HITL、動態中斷、interrupt()、Command(resume=...)、狀態重播與分叉、Replay and Fork、靜態中斷點
框架：langgraph

## 摘要
LangGraph 透過 Checkpointer 支援兩項核心控制流機制：**Interrupts（中斷）** 允許在節點或工具函式內部任意位置呼叫 `interrupt()` 動態暫停圖執行、將 JSON 可序列化的負載回傳給呼叫端，並於收到 `Command(resume=...)` 後從該節點開頭重新執行以完成 Human-in-the-loop（HITL）審批、編輯與輸入驗證；**Time Travel（時光旅行）** 則允許透過 `get_state_history` 檢索歷史 Checkpoint，並以 `invoke(None, snapshot.config)` 重播（Replay）後續節點，或透過 `update_state` 建立狀態修改後的執行分叉（Fork）。

## 重點

### 動態中斷 (`interrupt()` 與 `Command(resume=...)`)
- **啟用三要素**：
  1. 編譯圖時必須綁定 **Checkpointer**（如開發用 `InMemorySaver` / `MemorySaver` 或正式環境資料庫 Checkpointer）。
  2. 呼叫圖時必須在 `config` 的 `configurable` 中傳入 **`thread_id`**（作為持久化游標）。
  3. 在節點或工具內呼叫 `interrupt(payload)`（Python：`from langgraph.types import interrupt`；JS/TS：`import { interrupt } from "@langchain/langgraph"`），`payload` 必須為 JSON 可序列化值。
- **`interrupt()` 執行與恢復機制（5 步驟）**：
  1. **拋出特殊例外暫停**：呼叫 `interrupt()` 時，LangGraph 會拋出專用內部例外並由 runtime 攔截，立即中止當前節點執行。
  2. **儲存狀態**：透過 Checkpointer 儲存當前圖狀態。
  3. **向呼叫端回傳中斷負載**：
     - **Python `graph.stream_events(..., version="v3")`（推薦）**：中斷負載會出現在 `stream.interrupts`、`stream.interrupted` 為 `True`，最終輸出位於 `stream.output`。
     - **預設 `graph.invoke(...)`**：中斷負載會出現在回傳字典的 `result["__interrupt__"]`（JS/TS 為 `result.__interrupt__` 或使用 `import { INTERRUPT, isInterrupted } from "@langchain/langgraph"` 檢查 `isInterrupted(result)` 與 `result[INTERRUPT]`）。
  4. **無限期等待**：圖保持暫停直到收到外部輸入。
  5. **透過 `Command` 恢復執行**：
     - Python：呼叫 `graph.invoke(Command(resume=...), config)` 或 `graph.stream_events(Command(resume=...), config=config, version="v3")`（`from langgraph.types import Command`）。
     - JS/TS：呼叫 `await graph.invoke(new Command({ resume: ... }), config)`（`import { Command } from "@langchain/langgraph"`）。
     - 恢復時必須使用**相同的 `thread_id`**。**被中斷的節點會從該節點函式的最開頭重新執行**（`interrupt()` 之前的程式碼會再次執行），而 `Command` 中的 `resume` 值會直接成為該次 `interrupt()` 呼叫的回傳值。
- **`Command` 作為輸入的限制警告**：
  - `Command(resume=...)`（JS：`new Command({ resume: ... })`）是**唯一**可作為 `invoke()` / `stream()` / `stream_events()` 輸入的 `Command` 模式。
  - `Command` 的其他參數（`update`、`goto`、`graph`）僅供**節點函式回傳**使用；切勿在多輪對話中將 `Command(update=...)` 作為圖的輸入。

### 定義中斷回應結構 (`response_schema` / `responseSchema`)
- **Python（需 `langgraph>=1.2.12`）**：
  - 呼叫 `interrupt(payload, response_schema=Decision)`，其中 `Decision` 可為 Pydantic `BaseModel` 子類別、`typing_extensions.TypedDict` 或 `dataclass`。
  - LangGraph 會將型別轉為 JSON Schema 並附加於 `Interrupt.response_schema`（例如 `result["__interrupt__"][0].response_schema == Decision.model_json_schema()`）。
  - 恢復時，Pydantic 驗證與型別轉換規則會自動套用，`interrupt()` 會回傳驗證後的實例（如 `Decision` 物件、`TypedDict` 字典或 `dataclass` 實例）。若輸入不合法則拋出 `pydantic.ValidationError`，可用相同 `thread_id` 重新傳入修正後的 `Command(resume=...)`。
  - 若傳入純 JSON Schema `dict` 作為 `response_schema`，LangGraph 會原樣公開該字典但**不會**在執行期驗證 `resume` 值；若省略 `response_schema`，其值為 `None`。
- **TypeScript/JavaScript（需 `@langchain/langgraph>=1.4.16`）**：
  - 呼叫 `interrupt(payload, { responseSchema: Decision })`，其中 `Decision` 為 Zod schema（如 `z.object({ approved: z.boolean(), note: z.string().default("") })`）。
  - 轉換後的 JSON Schema 位於 `result.__interrupt__?.[0].response_schema`。恢復時回傳 Zod 解析後的值（含預設值），驗證失敗則拋出 `ZodError`。若傳入純 JSON Schema 物件則僅公開而不驗證；省略時不包含 `response_schema` 欄位。
- **LangSmith Studio 整合**：當設定 `response_schema` 時，Studio 會自動將中斷表單渲染為具型別的 UI 輸入欄位（如開關、文字框、數字輸入），而非原始 JSON 編輯器。

### 常見 Human-in-the-Loop (HITL) 設計模式
- **1. 搭配 Event Streaming (`stream_events` v3) 處理中斷**：
  - 在迴圈中呼叫 `graph.stream_events(input_or_command, config=config, version="v3")`（JS：`graph.streamEvents(..., { ...config, version: "v3" })`）：
    - `stream.messages`：逐 token 串流 AI 訊息（子圖訊息位於 `stream.subgraphs[*].messages`）。
    - `stream.values`：取得每步完成後的完整狀態快照。
    - `stream.interrupted` 與 `stream.interrupts`：檢查是否暫停並讀取中斷負載，接著以 `Command(resume=...)` 再次呼叫直到 `stream.interrupted` 為 `False`。
- **2. 處理多個平行中斷（Handling Multiple Interrupts）**：
  - 當平行分支（fan-out）中的多個節點同時呼叫 `interrupt()` 時，可在單次呼叫中將每個中斷的 `id` 映射至對應的恢復值：
    - Python：`Command(resume={i.id: f"answer for {i.value}" for i in interrupted_result["__interrupt__"]})`。
    - JS/TS：建立 `resumeMap[i.id] = ...`，再呼叫 `await graph.invoke(new Command({ resume: resumeMap }), config)`。
- **3. 審批工作流（Approve or Reject）**：
  - 節點內呼叫 `is_approved = interrupt({"question": ..., "details": ...})`，並根據結果直接回傳 `Command(goto="proceed")` 或 `Command(goto="cancel")`（Python 節點回傳型別標註為 `Command[Literal["proceed", "cancel"]]`；JS 在 `addNode` 第三個參數宣告 `{ ends: ['proceed', 'cancel'] }`）。
- **4. 審閱與編輯狀態（Review and Edit State）**：
  - 節點呼叫 `edited_content = interrupt({"instruction": "Review and edit", "content": state["generated_text"]})`，並將 `{"generated_text": edited_content}` 寫回狀態。
- **5. 工具內部中斷（Interrupts in Tools）**：
  - 直接在 `@tool` 裝飾的工具函式（Python `from langchain.tools import tool`；JS `import { tool } from "@langchain/core/tools"`）內部呼叫 `interrupt(...)`。當 LLM 透過 `ToolNode` 或自訂工具節點呼叫該工具時會自動暫停，允許人類批准、覆寫工具參數（如收件人或主旨）或取消執行。
- **6. 驗證人類輸入（Validating Human Input）**：
  - **禁止在單一節點內使用 `while True` 搭配 `interrupt()`**：因為每次 resume 都會從節點開頭重跑，`while True` 迴圈會導致第 1 次 resume 重播 1 次、第 2 次重播 2 次，依此類推。
  - **正確模式**：在狀態中儲存提問訊息（如 `pending_question`），節點每次執行**只呼叫一次 `interrupt(question)`**；若輸入無效則更新 `pending_question` 並回傳，再透過 `add_conditional_edges`（JS：`addConditionalEdges`）路由回同一個節點重新觸發中斷。

### Interrupts 四大鐵則與子圖重跑行為（Rules of Interrupts）
1. **切勿將 `interrupt()` 包在無差別的 `try/except`（或 `try/catch`）中**：
   - `interrupt()` 依賴拋出特殊例外來暫停圖執行。若使用 `except Exception:` 或 bare `try/catch` 攔截，中斷例外會被吞掉而無法暫停。
   - 應將 `interrupt()` 移出 `try` 區塊、僅捕捉明確的特定例外（如 `except NetworkException:`），或在 JS `catch` 中將非預期例外重新 `throw`。
2. **切勿在同一個節點內重新排序、條件跳過或非決定性地迴圈呼叫 `interrupt()`**：
   - 當單一節點包含多個 `interrupt()` 時，LangGraph 在該 task 內部是**嚴格依據索引位置（strictly index-based）**配對 resume 值清單。
   - 若使用 `if state.get("needs_age"): interrupt(...)` 條件跳過，或針對長度可能變動的清單跑 `for` 迴圈呼叫 `interrupt()`，恢復執行時會發生索引錯位（index mismatch）。
3. **切勿在 `interrupt()` 傳入不可序列化的複雜物件**：
   - 切勿傳入函式（functions）、自訂類別實例（class instances）等無法 JSON 序列化的物件；僅傳入基本型別、陣列或純資料字典。
4. **`interrupt()` 之前的副作用（Side Effects）必須具備冪等性（Idempotency）**：
   - 因為恢復執行時節點會從頭重跑，`interrupt()` 之前的任何操作都會再次執行。
   - 切勿在 `interrupt()` 之前執行 `db.create_audit_log(...)` 或 `db.append_to_history(...)` 等非冪等寫入（會產生重複紀錄）。應改用冪等操作（如 `db.upsert_user`）、將副作用移至 `interrupt()` 之後，或拆分為下游獨立節點。
5. **在節點內以函式呼叫子圖（Subgraphs called as functions）的重跑規則**：
   - 當父圖節點 `node_in_parent_graph` 以函式方式呼叫 `subgraph.invoke(some_input)`，且子圖內部節點 `node_in_subgraph` 觸發 `interrupt()` 時，恢復執行會使**父圖節點從頭重新執行**（`subgraph.invoke` 之前的程式碼會重跑），且**子圖內部被中斷的節點也會從頭重新執行**。

### 靜態中斷點（Static Interrupts / Breakpoints，除錯專用）
- 靜態中斷可在特定節點執行前或執行後暫停，僅建議用於除錯與單步測試（Human-in-the-loop 請使用動態 `interrupt()`）。必須搭配 Checkpointer 使用。
- **編譯期設定**：
  - Python：`builder.compile(interrupt_before=["node_a"], interrupt_after=["node_b", "node_c"], checkpointer=checkpointer)`。
  - JS/TS：`builder.compile({ interruptBefore: ["node_a"], interruptAfter: ["node_b", "node_c"], checkpointer })`。
- **執行期設定**：
  - Python：`graph.invoke(inputs, interrupt_before=["node_a"], interrupt_after=["node_b", "node_c"], config=config)`。
  - JS/TS：`await graph.invoke(inputs, { interruptBefore: ["node_a"], interruptAfter: ["node_b", "node_c"], configurable: { thread_id: "some_thread" } })`。
- **從斷點恢復**：傳入 `None`（JS 為 `null`）再次呼叫 `graph.invoke(None, config=config)`，圖會繼續執行直到下一個斷點。亦可在 LangSmith Studio UI 中直接設定靜態中斷點。

### 時光旅行（Time Travel：Replay 與 Fork）
- **1. 重播（Replay）**：
  - 流程：先呼叫 `list(graph.get_state_history(config))`（JS：`graph.getStateHistory(config)`，依時間倒序排列）找到目標 `StateSnapshot`（例如 `before_joke = next(s for s in history if s.next == ("write_joke",))`），再呼叫 `graph.invoke(None, before_joke.config)`（JS：`await graph.invoke(null, beforeJoke.config)`）。
  - 行為：該 checkpoint **之前**的節點不會重新執行（直接使用已儲存結果）；該 checkpoint **之後**的節點會**真正重新執行**（並非讀取快取，所有 LLM 呼叫、API 請求與 `interrupt()` 都會再次觸發並可能產生不同結果）。若對最後一個已完成 checkpoint（`next` 為空）執行 replay 則為無操作（no-op）。
- **2. 分叉（Fork）**：
  - 流程：找到歷史 checkpoint 後，先呼叫 `fork_config = graph.update_state(before_joke.config, values={"topic": "chickens"})`（JS：`const forkConfig = await graph.updateState(beforeJoke.config, { topic: "chickens" })`）建立帶有修改後狀態的新分支 checkpoint，接著呼叫 `graph.invoke(None, fork_config)`（JS：`await graph.invoke(null, forkConfig)`）從該分叉繼續執行。
  - **非回滾保證**：`update_state` **不會**回滾（roll back）或覆蓋原始執行緒，原始歷史紀錄保持完整，而是從指定時間點長出新的 checkpoint 分支。
- **3. 指定 `as_node` / `asNode` 控制分叉來源節點**：
  - 呼叫 `update_state` 時，更新值會套用目標節點的 writers 與 reducers，並將該節點記錄為產生此更新的節點，後續從該節點的後繼節點（successors）繼續執行。
  - 預設情況下 LangGraph 會根據 checkpoint 的版本歷史自動推斷 `as_node`。以下三種情境必須明確傳入 `as_node="node_name"`（JS：`{ asNode: "nodeName" }`）：
    1. **平行分支（Parallel branches）**：同一步驟有多個節點更新狀態，LangGraph 無法判斷最後一個節點是誰（否則會拋出 `InvalidUpdateError`）。
    2. **無執行歷史（No execution history）**：在全新的空白 thread 上預先設定初始狀態（常見於單元測試）。
    3. **跳過節點（Skipping nodes）**：將 `as_node` 設為較後面的節點，讓圖認為該節點已執行完畢並直接從其後繼節點開始。
- **4. Time Travel 搭配 Interrupts 與 Subgraphs**：
  - **多重中斷之間的分叉**：若圖有多個順序中斷（如 `ask_name -> ask_age`），可從兩個中斷之間的 checkpoint（`s.next == ("ask_age",)`）進行 fork，即可保留 `ask_name` 已回答的結果，僅重新觸發 `ask_age` 的 `interrupt()`。
  - **子圖的 Time Travel 粒度**：
    - **繼承父圖 Checkpointer（預設 `subgraph_builder.compile()`）**：父圖將整個子圖視為**單一 super-step**，只會在父圖層級產生一個 checkpoint。無法跳到子圖內部兩個節點（如 `step_a` 與 `step_b`）之間，只能從子圖執行前重跑整個子圖。
    - **子圖自有 Checkpointer（`subgraph_builder.compile(checkpointer=True)` / `{ checkpointer: true }`）**：子圖會在內部每個步驟建立自己的 checkpoint 歷史。可呼叫 `parent_state = graph.get_state(config, subgraphs=True)`（JS：`await graph.getState(config, { subgraphs: true })`），取得 `sub_config = parent_state.tasks[0].state.config`，再呼叫 `fork_config = graph.update_state(sub_config, {"value": ["forked"]})` 與 `graph.invoke(None, fork_config)`，即可精確從子圖內部的 `step_a` 與 `step_b` 之間分叉（保留 `step_a` 結果並僅重跑 `step_b`）。

## 相關頁面
- [[concepts/langgraph-persistence-and-checkpointers]]
- [[concepts/langgraph-memory-and-stores]]
- [[concepts/langgraph-subgraphs-and-fault-tolerance]]

## 出處
- docs/langgraph/interrupts.md
- docs/langgraph/use-time-travel.md
