# LangGraph Backward Compatibility and Changelogs

別名：LangGraph 向後相容性、圖遷移、生產環境更新、執行中執行緒、技術相容性、商業邏輯相容性、非確定性限制、更新日誌、Backward Compatibility、Graph Migrations、Changelog
框架：langgraph

## 摘要
不同於將執行實例綁定至啟動時程式碼版本的傳統工作流引擎，LangGraph 會將最新部署的圖程式碼立即套用至**所有**執行緒（包含新啟動的執行緒與從既有檢查點恢復的執行中執行緒 in-flight threads）。因此，任何正式環境的圖改動都相當於針對既有持久化狀態（checkpoints）的向後相容 API 變更。開發者必須依序防範三大相容性問題：**技術相容性（Technical compatibility）**、**商業邏輯相容性（Business compatibility）** 與僅適用於 Functional API 及節點內 `@task` / `interrupt` 的**非確定性（Non-determinism）**。

## 重點

### 1. LangGraph 的部署套用模型與三大相容性類別
- **立即套用最新圖程式碼**：當你部署更新後，LangGraph 會直接以最新版圖程式碼載入既有執行緒已持久化於 checkpointer 中的狀態（State）。這讓錯誤修復能直接生效於進行中的對話與代理人，但也代表每次改動都必須考慮如何與舊版程式碼啟動的執行緒互動。
- **三大相容性問題類別（依遭遇頻率排序）**：
  1. **技術相容性（Technical compatibility）**：最常見；新程式碼必須仍能載入既有 State 並正常分派執行。
  2. **商業邏輯相容性（Business compatibility）**：次常見；即便新程式碼在技術上能執行，既有的執行中執行緒仍應維持舊版商業流程，而不被溯及既往套用新流程。
  3. **非確定性（Non-determinism）**：僅適用於 **Functional API（`@entrypoint` / `@task`）** 以及在 Graph API 節點內部使用 **tasks** 或 `interrupt` 的情況。

### 2. 技術相容性（Technical Compatibility）與圖遷移規則
- **運作機制（API 契約）**：當執行緒恢復（resume）時，LangGraph 會反序列化已儲存的狀態，依「儲存的節點名稱」將狀態分派給該節點，並預期節點回傳符合當前狀態 Schema 的值。恢復執行的起點永遠是「當初停止執行之節點的開頭」。
- **常見的技術相容性破壞（Breaking Changes）**：
  - **重新命名或移除節點（Renaming or removing a node）**：若有任何執行緒正暫停在該節點（例如停在 `interrupt`）或正準備透過已建立檢查點的條件邊進入該舊名稱節點，恢復執行時 LangGraph 將找不到該節點名稱而導致執行失敗。
  - **重新命名或移除 State 鍵（Renaming or removing a State key）**：舊檢查點仍包含該鍵，或下游節點仍會讀取該鍵。
  - **收緊 State 欄位限制（Tightening a State field）**：例如將 `Optional` 欄位改為必填（required）、縮小欄位的型別範圍，或新增沒有預設值的必填欄位，會導致既有檢查點無法通過新 Schema 驗證。
- **安全的拓撲變更**：
  - **邊的拓撲（Edge topology）本身不會被持久化在檢查點中**。只要節點仍然存在，在既有節點之間新增、移除或重新路由邊（edges），對執行中的執行緒而言完全是安全的。唯一會破壞已中斷執行緒的拓撲變更只有「重新命名或移除節點」。
- **推薦的向後相容演進模式**：
  - **新增選填欄位**：
    - Python：將新狀態欄位宣告為 `NotRequired`（如 `from typing import NotRequired`，`summary: NotRequired[str]`）或 `Optional[...] = None`，確保舊檢查點仍能通過驗證。
    - JS/TS：將新狀態欄位標記為選填（如 Zod 的 `z.string().optional()` 或 `.nullish()`）。
  - **將移除視為棄用（Treat removals as deprecations）**：即使已沒有任何節點讀取某個欄位，仍應在狀態 Schema 上保留該欄位定義至少一個排空週期（drain cycle），讓既有檢查點能繼續載入。
  - **透過「先新增、後移除（Add-then-remove）」進行改名**：先將新欄位或新節點與舊欄位／舊節點並存，在棄用期間進行雙寫（dual-write）或同時路由至兩者，確認沒有任何執行中執行緒依賴舊名稱後，再將舊名稱移除。
  - **保持節點函式對未知鍵的容忍度**：Python 的 `TypedDict` 在執行期會忽略多餘的鍵，因此舊版程式碼留下的狀態不會引發錯誤（除非節點明確去讀取一個已不存在的鍵）。
  - **在預備環境（Staging）抽樣檢查**：正式上線前，利用時間旅行（time travel）與 `graph.get_state`（Python）／`graph.getState`（JS）在 staging 部署中針對既有執行緒進行抽測。
- **偵測執行中的執行緒（Detecting in-flight threads）**：
  - LangGraph 本身不維護跨執行緒狀態的搜尋索引，需依執行環境採用以下三種方式確認舊版節點或欄位是否仍有活動：
    1. **部署於 LangSmith Agent Server 時**：使用 Agent Server 的執行緒搜尋功能依 `status` 欄位過濾（支援 `idle`、`busy`、`interrupted`、`error` 四種狀態），可批次查詢所有處於 `interrupted` 或 `busy` 的執行緒（並可搭配 metadata 過濾）。
    2. **任何執行環境（LangSmith Tracing）**：透過 LangSmith 追蹤監控正式環境中哪些節點仍在被進入與離開，這是最可靠判斷某節點或狀態欄位是否已不再被任何活躍路徑觸及的訊號。
    3. **已知特定 `thread_id` 時**：直接呼叫 `graph.get_state(config)`（Python）／`graph.getState(config)`（JS）檢視最新檢查點（包含目前暫停於哪個節點與待處理的 interrupts），以及呼叫 `graph.get_state_history(config)`（Python）／`graph.getStateHistory(config)`（JS）檢視該執行緒完整的時間序列檢查點歷史。

### 3. 商業邏輯相容性（Business Compatibility）
- **問題場景**：有時變更在技術上完全合法（所有舊檢查點皆能載入、所有節點名稱皆存在），但新圖的「商業語意」已改變。例如原本流程為 `intake → triage → respond`，現在要在 `triage` 與 `respond` 之間插入新的 `policy_check` 節點：已經通過 `triage` 的舊執行緒應直接前往 `respond`（維持舊流程），而新啟動的執行緒才應走包含 `policy_check` 的新流程。
- **推薦模式：在執行緒啟動時記錄行為版本（Behavioral Version）並以條件邊分流**：
  1. 在 `State` 中新增選填版本欄位：`flow_version: NotRequired[int]`。
  2. **必須在執行緒最開頭的起始節點**（如 `intake`）為新執行緒蓋上當前版本戳記：`return {"flow_version": state.get("flow_version", 2)}`（從 `intake` 之後恢復的既有執行緒則會保留原本已儲存的值，或沒有該欄位）。若在分支點之後才設定版本號則無法生效。
  3. 在分流點（如 `triage` 之後）定義條件邊路由函式 `after_triage(state: State) -> str`：檢查 `if state.get("flow_version", 1) >= 2: return "policy_check"`，否則 `return "respond"`（未記錄 `flow_version` 的 v1 舊執行緒預設退回 `1`，從而跳過 `policy_check`）。
  4. 待所有 v1 執行緒皆執行完畢後，即可安全移除 `flow_version` 欄位與條件邊。

### 4. 非確定性限制（Non-determinism，Functional API 與 `@task`）
- **Graph API 與 Functional API 的重播差異**：
  - 一般的 **Graph API 節點**在恢復執行時，會從該節點函式的開頭重新執行（因此應將副作用設計為冪等 idempotent，但只要節點內未使用 `tasks` 或 `interrupt`，就不必維持呼叫順序）。
  - **Functional API 的 `@entrypoint`** 則會編譯為單一節點，當執行恢復時，會**從 `@entrypoint` 函式開頭重新重播（replay）**，並利用已快取的 `@task` 結果跳過已完成的工作。
- **會破壞 `@entrypoint` 重播模型的兩類變更**：
  1. **在恢復點（resume point）之前新增、移除或重新排序 `@task` 呼叫或 `interrupt` 呼叫**：因為 LangGraph 是依照重播時的「呼叫位置順序（position in the replay）」來配對已快取的結果與 resume 值，改變順序會導致錯誤的快取值被配對到不同的呼叫上。
  2. **在 `@task` 外部引入非確定性操作**：例如在 `@entrypoint` 主體內直接寫入 `time.time()`、`random.random()` 或網路呼叫，重播時會產生與第一次執行不同的值，進而改變控制流。
- **修改有執行中實例之 `@entrypoint` 的安全做法**：
  - 等待所有執行中的 runs 排空（drain）後再部署變更。
  - 將任何新增的邏輯封裝在全新的 `@task` 中，使其結果獨立建立檢查點。
  - 在 `langgraph.json` 中以**新的圖名稱（graph name）**註冊新的 `@entrypoint`，並將新執行緒路由至新圖名稱。

### 5. 更新日誌（Changelogs）
- **LangGraph Python 更新日誌**：官方發布紀錄位於 `https://docs.langchain.com/oss/python/releases/changelog`（對應文件檔 `docs/langgraph/changelog-py.md`）。
- **LangGraph JavaScript / TypeScript 更新日誌**：官方發布紀錄位於 `https://docs.langchain.com/oss/javascript/releases/changelog`（對應文件檔 `docs/langgraph/changelog-js.md`）。

## 相關頁面
- [[concepts/langgraph-streaming]]
- [[guides/langgraph-agentic-rag-and-sql-agent]]
- [[guides/langgraph-deployment-and-studio]]

## 出處
- docs/langgraph/backward-compatibility.md
- docs/langgraph/changelog-py.md
- docs/langgraph/changelog-js.md
