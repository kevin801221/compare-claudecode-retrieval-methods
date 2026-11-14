# Deep Agents Human-in-the-Loop (HITL)

別名：人類介入審批、Human-in-the-loop、HITL、`interrupt_on`、`interruptOn`、`InterruptOnConfig`、`HumanInTheLoopMiddleware`、`allowed_decisions`、`Command(resume=...)`
框架：deepagents

## 摘要
Deep Agents 透過整合 LangGraph 的 interrupt 機制與 `HumanInTheLoopMiddleware`，讓代理在執行敏感工具或寫入受保護的檔案路徑前暫停並交由人類審批。開發者可透過 `interrupt_on`（Python）/ `interruptOn`（JS）針對個別工具設定審批選項（`approve`、`edit`、`reject` 及 Python 的 `respond`）或條件式攔截（`when` predicate），並在審批後透過 `Command(resume={"decisions": [...]})` 於同一 `thread_id` 恢復執行。

## 重點
### 基本設定與 `interrupt_on` / `interruptOn`
- **架構機制**：當在 `create_deep_agent` 設定 `interrupt_on`（Python）或在 `createDeepAgent` 設定 `interruptOn`（JS）時，系統會將 `HumanInTheLoopMiddleware` 加入 Deep Agents stack；若執行在工具回傳結果前被取消或中斷，同一堆疊中的 `PatchToolCallsMiddleware` 會自動修復訊息歷史中懸空的工具呼叫。
- **必要前提**：Human-in-the-loop **必須配置 checkpointer**（如 `MemorySaver()` 或 `InMemorySaver()`）以在中斷與恢復之間持久化代理狀態，且恢復時**必須使用包含相同 `thread_id` 的 `config`**（`{"configurable": {"thread_id": ...}}`）。
- **工具映射值選項**：
  - `True` / `true`：啟用預設中斷行為——Python 預設允許 `approve`、`edit`、`reject` 與 `respond` 四種決策；JS 預設允許 `approve`、`edit` 與 `reject` 三種決策。
  - `False` / `false`：停用該工具的中斷。
  - `InterruptOnConfig`（字典/物件）：透過 `allowed_decisions`（Python）/ `allowedDecisions`（JS）自訂允許的決策清單（例如高風險工具 `["approve", "edit", "reject"]`、中風險 `["approve", "reject"]`、強制批准 `["approve"]`）。

### 決策型別（Decision Types）與語義
- **`"approve"`**：原封不動批准並執行工具呼叫，格式為 `{"type": "approve"}`。
- **`"edit"`**：在執行前修改工具參數（建議保守修改，大幅改動可能導致模型重新評估策略並重複執行工具）：
  - Python 格式：`{"type": "edit", "edited_action": {"name": action_request["name"], "args": {...}}}`（必須包含工具名稱 `name`）。
  - JS 格式：`{ type: "edit", editedAction: { name: actionRequest.name, args: {...} } }`。
- **`"reject"`**：拒絕提議的操作並跳過工具執行，向代理回傳拒絕回饋訊息：
  - 格式：`{"type": "reject", "message": "..."}`（若省略 `message`，預設回饋會告知模型工具未執行，且除非使用者要求否則不要重試相同工具呼叫；針對具副作用的工具建議提供明確領域指示，告知代理應放棄操作、詢問後續問題或改採安全替代方案）。
- **`"respond"`（僅 Python）**：當人類直接扮演該工具（例如回答 `ask_user` 提示）時使用。**切勿使用 `respond` 來拒絕具副作用（side-effecting）的工具**，因為其訊息可能會被模型視為成功的工具執行結果。

### 條件式中斷（Conditional Interrupts，僅 Python）
- **版本需求**：需 `langchain>=1.3.3`。
- 在工具的 `InterruptOnConfig` 中加入選填的 `when` predicate（接收 `ToolCallRequest` 物件並回傳 `bool`）。
- 當 `when` 回傳 `False` 時，該次呼叫會自動批准並直接執行，不會被加入中斷批次（interrupt batch）；當回傳 `True`（或未設定 `when`）時則正常暫停等待審閱。

### 處理中斷、批次工具呼叫與串流（Handling & Streaming）
- **擷取中斷資訊**：
  - 呼叫 `agent.invoke(..., config=config)` 後，檢查 `result.get("__interrupt__")`（Python）或 `result.__interrupt__`（JS）。
  - 從 `result["__interrupt__"][0].value` 取出：
    - Python：`action_requests`（每個項目含 `name` 與 `args`）與 `review_configs`（每個項目含 `action_name` 與 `allowed_decisions`）。
    - JS：`actionRequests`（含 `name` 與 `args`）與 `reviewConfigs`（含 `actionName` 與 `allowedDecisions`）。
- **多個工具呼叫的批次處理（Multiple tool calls）**：
  - 當代理在單一回合呼叫多個需要審批的工具時，所有中斷會被合併為單一批次（batch）。
  - 恢復時傳入的 `decisions` 陣列長度和順序**必須嚴格對齊 `action_requests` / `actionRequests` 的順序**（一對一依序對應）。
- **恢復執行（Resume）**：
  - Python：`agent.invoke(Command(resume={"decisions": decisions}), config=config)`。
  - JS：`await agent.invoke(new Command({ resume: { decisions } }), config)`。
  - （註：若同時有多個平行分支的中斷待處理，則改為將每個 interrupt ID 映射至其 resume 值）。
- **結合串流處理中斷（Handle interrupts with streaming）**：
  - 使用 `.stream()` 並設定 `stream_mode=["messages", "updates"]`（Python）/ `streamMode: ["messages", "updates"]`（JS）：`"messages"` 模式負責即時串流 LLM tokens，而 `"updates"` 模式則會在發生中斷時於 `data["__interrupt__"][0]`（Python）/ `data.__interrupt__[0]`（JS）傳遞中斷負載。
  - 收集完人類決策後，將 `Command(resume={"decisions": decisions})` 作為下一輪 `.stream()` 的輸入繼續串流。

### 子代理中斷與檔案系統權限中斷
- **子代理工具呼叫中斷（Interrupts on tool calls）**：
  - 每個子代理可在自身規格中設定 `interrupt_on` / `interruptOn`，**覆寫（override）主代理的預設設定**（例如主代理設定 `"read_file": False`，而特定子代理覆寫為 `"read_file": True`）。
  - 子代理觸發中斷時，同樣會浮現於父代理結果或父代理 `updates` 串流的 `__interrupt__` 中（僅為了接收中斷**不需要**開啟 `subgraphs=True`；只有當需要同時串流子代理的 tokens 與進度事件時才需啟用 `subgraphs=True`）。
- **工具內部直接呼叫 `interrupt()`（Interrupts within tool calls）**：
  - 子代理（包括使用 `create_agent` 建立並封裝於 `CompiledSubAgent` 的子代理）的工具函式內部可直接呼叫 `langgraph.types.interrupt(...)`（Python）/ `@langchain/langgraph` 的 `interrupt(...)`（JS）暫停執行並等待自訂格式的 `Command(resume={...})` 回傳值（如 `{"approved": True}`）。
- **檔案系統權限中斷（Filesystem permission interrupts，Python 需 `deepagents>=0.6.8`）**：
  - 在 `permissions` 清單中設定 `FilesystemPermission(operations=["write"], paths=["/secrets/**"], mode="interrupt")`。
  - 當代理對匹配路徑呼叫 `write_file`、`edit_file` 或 `delete` 時，會引發與一般工具相同的 HITL 中斷（以該檔案系統工具名稱作為 `action_name`），並自動與任何傳入的 `interrupt_on` 設定合併，使用完全相同的 `Command(resume={"decisions": [...]})` 流程恢復。

## 相關頁面
- [[concepts/deepagents-overview]]
- [[guides/deepagents-customization]]
- [[concepts/deepagents-backends-and-sandboxes]]
- [[concepts/deepagents-subagents]]
- [[concepts/deepagents-streaming-and-fault-tolerance]]

## 出處
- docs/deepagents/human-in-the-loop.md
