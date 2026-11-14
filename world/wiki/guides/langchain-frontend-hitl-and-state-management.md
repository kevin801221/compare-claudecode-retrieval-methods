# LangChain Frontend Human-in-the-Loop, Checkpoints, and Stream Management

別名：LangChain 前端人類介入與狀態管理、HITL 審批與自訂中斷表單、時間旅行與分支對話、訊息佇列與串流重連、Frontend HITL and State Management
框架：langchain

## 摘要
LangChain 前端 SDK 建立在 LangGraph 的中斷（Interrupts）、持久化檢查點（Checkpoints）與執行緒（Threads）機制之上，讓前端不僅能顯示對話，更能作為長時間執行代理的控制平面。本指南涵蓋 Human-in-the-Loop（HITL）審批流程與工具內自訂中斷表單（`stream.interrupt`、`stream.respond`）、基於檢查點的時間旅行（Time Travel `getHistory` 與 `forkFrom`）與分支對話（Branching Chat `useMessageMetadata`）、依序處理多筆輸入的訊息佇列（Message Queues `useSubmissionQueue` / `injectSubmissionQueue`），以及不中斷後端執行的串流離開與重連（Join & Rejoin `stream.disconnect()`）。

## 重點

### 1. Human-in-the-Loop（HITL）人工審批與自訂表單（`human-in-the-loop.md`）
- **中斷與恢復生命週期**：
  - 本指南預設使用批次中斷模式（Batched interrupt mode；若需每次工具呼叫單獨暫停，Python 設定 `interrupt_mode="per_call"`，JS 設定 `interruptMode: "per_call"`）。
  - 當代理觸發中斷時，執行會暫停並發出中斷酬載，前端透過 `stream.interrupt`（Vue 為 `stream.interrupt.value`，Angular 為 `stream.interrupt()`）讀取待審批狀態。
  - 使用者做出決定後，呼叫 `stream.submit(null, { command: { resume: response } })` 將 `HITLResponse`（由 `"langchain"` 匯入）傳回後端，代理從確切停止點繼續執行，且 `stream.interrupt` 重設為 `null`。由於檢查點持久化，重新整理頁面不會遺失待審批的中斷狀態。
- **`HITLRequest`、`ActionRequest` 與 `ReviewConfig` 結構**：
  ```ts
  interface HITLRequest {
    actionRequests: ActionRequest[];
    reviewConfigs: ReviewConfig[];
  }
  interface ActionRequest {
    name: string;
    args: Record<string, unknown>;
    description?: string;
  }
  interface ReviewConfig {
    allowedDecisions: ("approve" | "reject" | "edit" | "respond")[];
  }
  ```
- **四種決策型別（`HITLResponse.decisions`）**：
  1. **Approve（核准）**：`{ decisions: [{ type: "approve" }] }`。代理照原樣執行待處理工具。
  2. **Reject（拒絕）**：`{ decisions: [{ type: "reject", message: "The email tone is too aggressive. Do not send it." }] }`。工具不會執行，代理會收到拒絕原因並決定下一步。若省略 `message`，後端會使用預設訊息告知模型工具未執行且除非使用者要求否則不要重試相同呼叫。
  3. **Edit（編輯）**：`{ decisions: [{ type: "edit", editedAction: { name: actionRequest.name, args: { ...actionRequest.args, subject: "Updated subject line", body: "Revised email body with softer language." } } }] }`。修改工具參數後交由代理執行。
  4. **Respond（直接回覆）**：`{ decisions: [{ type: "respond", message: "Blue." }] }`。適用於 `ask_user` 等專門收集使用者輸入的佔位工具，`message` 會直接作為成功的工具回傳結果且不執行工具本身（切勿用來拒絕操作，因為模型會將其視為成功結果）。
- **多筆待審批動作處理（Multiple Pending Actions）**：
  - 當 `request.actionRequests` 包含多筆動作時，UI 可為每筆動作渲染獨立卡片（搭配對應索引的 `request.reviewConfigs[i]`），並在收集完所有決策（`Object.keys(decisions).length === request.actionRequests.length`）後，組合成單一 `HITLResponse`（`decisions: request.actionRequests.map((_, i) => decisions[i])`）一次送出。
- **自訂中斷表單（Custom Interrupt Forms，`hitl-interrupt-forms`）**：
  - 若通用的核准／拒絕按鈕不敷使用（如訂機票、退款審批、內容審核需要各自專屬的欄位與驗證），可在工具內部直接呼叫 `@langchain/langgraph` 的泛型 `interrupt<InterruptCard, ReviewDecision>(value)`：
    - `FormField`：`{ name: string; label: string; type: "select" | "checkbox" | "textarea" | "currency"; options?: string[]; default?: unknown; }`
    - `ReviewDecision`：`{ approved: boolean; values?: Record<string, unknown>; }`
    - `InterruptCard`：`{ formType: "flight-booking" | "refund-approval" | "content-review"; tool: string; title: string; context: Record<string, unknown>; fields: FormField[]; resolved?: boolean; decision?: ReviewDecision; }`
  - 前端（`assistantId: "hitl_interrupt_forms"`）透過 `const card = stream.interrupt?.value as InterruptCard | undefined;` 讀取表單規格並依 `card.formType` 渲染對應表單。
  - **使用 `stream.respond(decision, { update })` 將已決策卡片保留在畫面上**：
    - 一般中斷在解決瞬間 `stream.interrupt` 會清空，導致表單卡片在慢速工具執行期間消失。
    - 透過 `stream.respond` 可在同一個 Super-step 中同時恢復中斷並將唯讀卡片寫入訊息歷史（對應 LangGraph 的 `Command(resume, update)`，僅產生單一檢查點且無需額外狀態寫入）：
      ```ts
      const resolvedCard = { ...card, resolved: true, decision };
      const cardMessage = new AIMessage({
        content: `Review ${decision.approved ? "approved" : "declined"}.`,
        response_metadata: { cards: resolvedCard },
      });
      stream.respond(decision, { update: { messages: [cardMessage] } });
      ```
    - `respond(response, { update })` 會**樂觀地（Optimistically）**套用更新，卡片立即渲染為唯讀狀態，待後端回傳相同 ID 的訊息時自動調和（Reconcile），不會閃爍且重新整理頁面後依然保留在對話紀錄中（透過 `(msg.response_metadata as { cards?: InterruptCard })?.cards` 讀取並以 `<InterruptForm card={card} readOnly />` 渲染）。

### 2. 時間旅行與檢查點導覽（Time Travel，`time-travel.md`）
- **檢查點機制與 `ThreadState` 結構**：
  - LangGraph 在每個 Super-step 邊界持久化代理狀態（同一 Super-step 中平行執行的節點共用同一個檢查點邊界）。每個狀態快照為一個 `ThreadState` 物件，包含：
    - `checkpoint`：檢查點識別碼（含 `checkpoint_id` 與命名空間）。
    - `created_at`：快照建立時間。
    - `parent_checkpoint`：此路徑中的上一個檢查點。
    - `values`：該時間點的完整代理狀態（`messages` 與自訂狀態鍵）。
    - `tasks`：排定在下一步執行的圖節點任務（含 `t.interrupts`）。
    - `next`：執行計畫中即將執行的節點名稱陣列（如 `cp.next?.join(", ") || "Complete"`）。
  - 呼叫 `stream.client.threads.getHistory(threadId)` 會依**由新到舊（Newest first）**順序回傳檢查點，預設上限（Limit）為 `10` 筆。由於歷史可能包含多條分支路徑，應使用 `parent_checkpoint` 追蹤祖系關係，而非假設陣列相鄰元素為父子關係。
- **`useStream` 設定與歷史載入（`assistantId: "time_travel"`）**：
  - 在前端維護 `threadId` 狀態並綁定至 `useStream({ apiUrl, assistantId: "time_travel", threadId, onThreadId })`（Svelte 傳入 getter `threadId: () => threadId`，Angular 傳入 Signal `threadId: this.threadId`）。
  - 當 `threadId` 存在且 `!stream.isLoading` 時，呼叫 `stream.client.threads.getHistory(threadId)` 更新時間軸清單。
- **從任意檢查點恢復執行（`forkFrom`）**：
  - 呼叫 `stream.submit(undefined, { forkFrom: cp.checkpoint.checkpoint_id })`。
  - SDK 會將 `undefined` 或 `null` 輸入轉為 `null` 發送，代表不提供新輸入而直接從所選檢查點繼續執行（注意：傳入空物件 `{}` 會被視為提供新輸入，而非延續訊號；若該檢查點沒有 `next` 節點，則無待處理工作可重播）。
  - 從檢查點恢復會在同一執行緒中建立新的執行路徑，原始檢查點仍保留在歷史中。**警告**：重播檢查點可能會再次執行下游工具與 API 呼叫，且不會撤銷先前已發生的外部副作用（如已發出的郵件或資料庫寫入）。
- **檢查點中繼資料轉換（`formatCheckpoints`）**：
  - 可提取 `id: cp.checkpoint?.checkpoint_id`、`nextLabel: cp.next?.join(", ") || "Complete"`、`messageCount: (cp.values?.messages as unknown[])?.length ?? 0`、`hasInterrupts: cp.tasks?.some((t) => t.interrupts?.length) ?? false` 與 `nextNodes: cp.next ?? []`，並在時間軸上針對 `hasInterrupt` 為 `true` 的檢查點標示 `"Interrupt"` 徽章。

### 3. 分支對話：訊息編輯與重新生成（Branching Chat，`branching-chat.md`）
- **核心概念與 `useMessageMetadata`**：
  - 分支對話將對話視為檢查點時間軸，每則訊息皆帶有指向「該訊息建立前一個檢查點」的中繼資料。
  - 在渲染單一訊息的元件中呼叫 `@langchain/react` 的 `useMessageMetadata(stream, message.id)` 取得 `MessageMetadata`，並讀取 `const checkpointId = metadata?.parentCheckpointId;` 作為分叉點（Fork point）。
- **編輯使用者訊息（Edit a message）**：
  - 取得該 `HumanMessage` 的 `metadata.parentCheckpointId`，並以更新後的訊息內容搭配 `forkFrom` 送出：
    ```ts
    stream.submit(
      { messages: [{ type: "human", content: newText }] },
      { forkFrom: metadata.parentCheckpointId }
    );
    ```
  - 代理會從分叉點以新訊息重新執行，原對話路徑仍保存在執行緒歷史中。
- **重新生成 AI 回應（Regenerate a response）**：
  - 取得該 `AIMessage` 的 `metadata.parentCheckpointId`，並傳入 `undefined` 輸入與 `forkFrom`：
    ```ts
    stream.submit(undefined, {
      forkFrom: metadata.parentCheckpointId,
    });
    ```
  - SDK 將 `undefined` 轉為 `null`，讓代理在不改變輸入的情況下從父檢查點重新產生回應（適合利用溫度參數產生不同回答）。串流進行中（`stream.isLoading` 為 `true`）時應停用編輯與重新生成按鈕。

### 4. 訊息佇列管理（Message Queues，`message-queues.md`）
- **運作機制與 `multitaskStrategy: "enqueue"`**：
  - 允許使用者在代理仍在處理當前請求時連續發送多則訊息。當需要在執行中排隊等待時，於提交時傳入 `multitaskStrategy: "enqueue"`，待當前執行完成後會自動依序派發下一筆佇列訊息。
- **各框架佇列輔助函式（Submission Queue Helpers）**：
  - **React**：`import { useStream, useSubmissionQueue } from "@langchain/react"; const queue = useSubmissionQueue(stream);`
  - **Vue**：`import { useStream, useSubmissionQueue } from "@langchain/vue"; const queue = useSubmissionQueue(stream);`（透過 `queue.size.value` 與 `queue.entries.value` 讀取）
  - **Svelte**：`import { useStream, useSubmissionQueue } from "@langchain/svelte"; const queue = useSubmissionQueue(stream);`（透過 `queue.size` 與 `queue.entries` 讀取）
  - **Angular**：`import { injectStream, injectSubmissionQueue } from "@langchain/angular"; queue = injectSubmissionQueue(this.stream);`（透過 `queue.size()` 與 `queue.entries()` 讀取）
- **佇列介面與 `SubmissionQueueEntry` 欄位**：
  - `queue.entries`（`SubmissionQueueEntry[]`）：所有待處理的佇列項目陣列。
  - `queue.size`（`number`）：目前佇列中的項目數量。
  - `queue.cancel(id)`（`(id: string) => Promise<void>`）：依 ID 取消特定佇列項目。
  - `queue.clear()`（`() => Promise<void>`）：一次取消並清空所有佇列項目。
  - 每筆 `SubmissionQueueEntry` 包含：`id`（`string`，唯一識別碼）、`values`（`object`，提交的輸入值，如 `entry.values?.messages?.at(-1)?.content`）、`options`（`object`，提交時傳入的額外選項）、`createdAt`（`string`，建立時間的 ISO 時間戳記）。
  - **取消限制**：`queue.cancel(id)` 與 `queue.clear()` 僅影響**尚未開始處理**的排隊訊息；若訊息已開始執行，從佇列取消無效，必須呼叫 `stream.stop()` 中斷當前執行。
- **使用 `onCreated` 串聯後續提交與開啟新執行緒**：
  - 可在 `stream.submit(input, { onCreated(run) { console.log("Run created:", run.runId); stream.submit(...); } })` 的 `onCreated` 回呼中程式化地連續送出後續訊息，後續訊息會自動排入佇列。
  - 若要開啟全新對話執行緒，只需將傳給 `useStream` 的響應式 `threadId` 設為 `null`（`setThreadId(null)`），下一次呼叫 `submit` 時即會建立新執行緒。

### 5. 串流離開與重新加入（Join & Rejoin Streams，`join-rejoin.md`）
- **核心概念與應用場景**：
  - 打破傳統串流 API 客戶端與伺服器的緊密耦合，允許客戶端斷開連線而不停止伺服器端的代理執行，稍後再重新連接並無縫接續進度（適用於網路切換、頁面導覽離開、行動裝置背景化、數分鐘長任務以及跨裝置接力）。
- **關鍵設定與 `stream.disconnect()` vs `stream.stop()`**：
  - **持久化 `threadId`**：透過 `onThreadId(id)` 將新建立的執行緒 ID 存入持久儲存（如 `sessionStorage.setItem("activeThreadId", id)`），並在元件初始化時讀取（`sessionStorage.getItem("activeThreadId")`）。
  - **斷開連線（Disconnect）**：呼叫 `await stream.disconnect()`（等同於 `await stream.stop({ cancel: false })`）。呼叫後 `stream.isLoading` 變為 `false`，畫面保留斷線前已收到的訊息，而代理在伺服器端繼續執行。
  - **重要區別**：切勿在離開頁面時呼叫預設的 `stream.stop()`！`stream.stop()`（或 `client.runs.cancel`）預設會同時斷開客戶端連線**並取消伺服器端正在執行的任務**，僅應綁定在使用者明確點擊的「停止／取消」按鈕上。
  - **重新加入（Rejoin）**：以儲存的相同 `threadId` 重新掛載（Remount）串流消費元件（例如在 React/Vue/Svelte/Angular 中遞增外層容器的 `mountKey`）。重新掛載後會自動補齊斷線期間產生的所有訊息；若代理仍在執行，即時串流會繼續且 `stream.isLoading` 為 `true`；若代理已完成，則立即收到最終狀態。可搭配瀏覽器 Page Visibility API 在使用者切回分頁時自動重連。

## 相關頁面
- [[guides/langchain-frontend-streaming-and-tools]]
- [[guides/langchain-frontend-generative-ui-and-integrations]]
- [[concepts/langchain-human-in-the-loop]]
- [[concepts/langchain-short-term-memory]]

## 出處
- docs/langchain/frontend/human-in-the-loop.md
- docs/langchain/frontend/time-travel.md
- docs/langchain/frontend/branching-chat.md
- docs/langchain/frontend/message-queues.md
- docs/langchain/frontend/join-rejoin.md
