# LangChain Frontend Streaming, Messages, and Tool Execution

別名：LangChain 前端串流與工具呼叫、useStream 與 injectStream 指南、Markdown 與推理 Token 渲染、無頭工具與結構化輸出、Frontend Streaming and Tools
框架：langchain

## 摘要
LangChain 前端 SDK（`@langchain/react`、`@langchain/vue`、`@langchain/svelte`、`@langchain/angular`）透過 `useStream` 與 `injectStream` 連接 `createAgent` / `create_agent` 編譯出的 LangGraph 串流 API，將訊息、工具呼叫生命週期、中斷（Interrupts）、檢查點歷史（Checkpoints）與自訂狀態（Typed State）暴露為各框架原生的響應式狀態。本指南涵蓋基礎串流架構與型別推論、即時 Markdown 解析與 XSS 清理、推理模型思考區塊（`contentBlocks`）提取、工具呼叫卡片（`AssembledToolCall`）與客戶端無頭工具（Headless Tools `.implement(...)`），以及從工具參數提取結構化輸出（Structured Output）進行漸進式 UI 渲染的完整模式。

## 重點

### 1. 前端串流架構與跨框架 SDK（`overview.md`）
- **核心架構**：後端由 `createAgent`（JavaScript/TypeScript，來自 `"langchain"`，搭配 `@langchain/langgraph` 的 `new MemorySaver()`）或 `create_agent`（Python，來自 `langchain.agents`，搭配 `langgraph.checkpoint.memory` 的 `MemorySaver()`）編譯為具備串流 API 的 LangGraph 圖；前端透過 `useStream()` / `injectStream()` 訂閱 `stream` 並透過 `submit` 發送輸入。
- **v1 前端 SDK 套件與匯入方式**：
  - **React**：`import { useStream } from "@langchain/react";`
  - **Vue**：`import { useStream } from "@langchain/vue";`
  - **Svelte**：`import { useStream } from "@langchain/svelte";`
  - **Angular**：`import { injectStream } from "@langchain/angular";`（在部分元件範例中亦支援 `import { useStream } from "@langchain/angular";`）
- **核心執行期能力（Runtime Semantics）**：
  - **Durable threads（持久化執行緒）**：重新整理頁面、切換裝置或重新加入執行中的任務而不遺失對話狀態。
  - **Typed agent state（具型別代理狀態）**：透過 `stream.values` 渲染訊息以外的任意狀態鍵（如 `todos: Todo[]`、管線輸出、引用、沙盒檔案、指標或自訂商業物件）。
  - **Tool-call lifecycle（工具呼叫生命週期）**：透過 `stream.toolCalls` 將執行中、完成與失敗的工具呼叫渲染為專用 UI 卡片而非原始 JSON。
  - **Interrupts（中斷）**：透過 `stream.interrupt` 暫停執行以進行人工審批、編輯或補充資訊，並從確切停止點恢復執行。
  - **Checkpoints（檢查點）**：從持久化的狀態快照建構編輯、重試、分支、稽核與時間旅行（Time-travel）流程。
  - **Nested execution（巢狀執行）**：視覺化 Deep Agents、子代理（Subagents）與圖節點，不會將所有事件壓平為單一難以閱讀的串流。
  - **Framework-native reactivity（框架原生響應式）**：在 React（Hooks）、Vue（Composables，透過 `.value` 存取）、Svelte（Stores / Runes）與 Angular（Signals，透過 `()` 呼叫存取）中使用相同協定。
- **TypeScript 型別推論（Type Inference）**：
  - **Python 後端**：手動定義與代理狀態 Schema 相符的 TypeScript 介面（如 `import type { BaseMessage, Todo } from "langchain"; interface AgentState { messages: BaseMessage[]; todos: Todo[]; }`），並傳入 `useStream<AgentState>({ apiUrl: "http://localhost:2024", assistantId: "agent" })`。`assistantId` 應使用 `langgraph.json` 中的圖名稱（Graph name）。
  - **JS/TS 後端**：直接匯入代理定義並傳入 `typeof myAgent`（`import type { myAgent } from "./agent"; const stream = useStream<typeof myAgent>({ apiUrl: "http://localhost:2024", assistantId: "agent" });`），TypeScript 會自動從編譯後的圖推論包含自訂狀態鍵在內的完整狀態 Schema。
- **前端模式選擇指南**：
  - 讓使用者了解代理正在做什麼：結合 `Tool calling` 與 `Reasoning tokens`。
  - 安全地審批敏感操作：使用 `Human-in-the-loop`。
  - 在任務執行期間發送新工作：使用 `Message queues`。
  - 離開並稍後返回長時間執行的任務：使用 `Join & rejoin streams`。
  - 從較早的對話輪次編輯或重試：使用 `Branching chat` 與 `Time travel`。
  - 將狀態渲染為應用程式而非單純聊天：使用 `Structured output`、`Generative UI` 與 `Deep Agents frontend patterns`。

### 2. 即時 Markdown 訊息渲染與清理（`markdown-messages.md`）
- **渲染管線三階段**：
  1. **Receive（接收）**：`useStream` 將串流 Token 即時累積至每個 AI 訊息的 `msg.text` 屬性中並響應式更新。
  2. **Parse（解析）**：Markdown 解析器在每次更新時將原始文字轉為 HTML 或 React 元素樹（對於 5 KB 的對話訊息耗時 `< 5ms`；`marked` 解析速度約 `~1 MB/s`）。
  3. **Render（渲染）**：將解析結果寫入 DOM。React 使用 Virtual DOM diffing；Vue、Svelte 與 Angular 則搭配經過清理（Sanitized）的 HTML 使用 `v-html`、`{@html}` 或 `[innerHTML]`。
- **跨框架訊息迭代與型別窄化**：
  - 使用 `"langchain"` 匯出的 `AIMessage.isInstance(msg)` 與 `HumanMessage.isInstance(msg)` 判斷訊息型別。
  - **React**：`stream.messages.map((msg) => ...)`
  - **Vue**：`<template v-for="msg in stream.messages.value" :key="msg.id">`
  - **Svelte**：`{#each stream.messages as msg (msg.id)}`
  - **Angular**：`@for (msg of stream.messages(); track msg.id)`
- **各框架推薦套件與實作細節**：
  - **React**：使用 `react-markdown` 搭配 `remark-gfm`（`<ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>`）。因為直接產出 React 元素且不涉及 `dangerouslySetInnerHTML`，**不需要**額外使用 `dompurify` 進行 HTML 清理。
  - **Vue / Svelte / Angular**：使用 `marked` 搭配 `dompurify`。設定 `marked.setOptions({ gfm: true, breaks: true })`，並將輸出透過 `DOMPurify.sanitize(marked.parse(text) as string)` 清理後再綁定至 `v-html="html"`（Vue）、`{@html html}`（Svelte，搭配 `$props()` 與 `$derived.by`）或 `[innerHTML]="html()"`（Angular，搭配 `signal("")` 與 `computed`）。
- **安全性與效能最佳實踐**：
  - **防範 XSS**：使用原始 HTML 注入時必須透過 `dompurify` 移除 `<script>` 標籤、`onclick` 屬性與 `javascript:` URL。
  - **啟用 GFM 與換行**：設定 `gfm: true` 支援表格、刪除線、任務清單與自動連結；設定 `breaks: true` 讓 LLM 常見的單一換行符號轉為 `<br>`。
  - **超長回應優化**：對於超過 `50 KB` 的極長回應，可使用 `requestAnimationFrame` 將更新節流至 60fps，或採用增量解析（Incremental parsing）。

### 3. 推理模型思考區塊渲染（`reasoning-tokens.md`）
- **內容區塊結構（`contentBlocks`）**：支援進階思考（如 OpenAI GPT-5、Anthropic Claude Extended Thinking）的模型會在 `AIMessage` 的 `msg.contentBlocks` 陣列中依產生順序傳遞兩類結構化區塊：
  - **Reasoning block**：`{ type: "reasoning", reasoning: "Let me think about this step by step..." }`
  - **Text block**：`{ type: "text", text: "The answer is 42." }`
- **提取與合併邏輯（`extractBlocks`）**：
  - 單一訊息可能包含多個推理區塊（例如模型暫停推理、產出部分文字後再次推理），因此需過濾後合併：
    - `reasoning`: `msg.contentBlocks.filter((b) => b.type === "reasoning").map((b) => b.reasoning).join("")`
    - `text`: `msg.contentBlocks.filter((b) => b.type === "text").map((b) => b.text).join("")`
- **串流階段判斷（Phase Detection）**：
  - 判斷是否為最後一則正在串流的訊息：`isStreaming = stream.isLoading && i === stream.messages.length - 1`（Vue 為 `stream.isLoading.value && i === stream.messages.value.length - 1`；Angular 為 `stream.isLoading() && $index === stream.messages().length - 1`）。
  - 在 `AIResponse` 元件中區分兩階段：
    - `isReasoningPhase = isStreaming && !hasText`：將此旗標傳給 `ThinkingBubble` 的 `isStreaming` 屬性，顯示思考中旋轉圖示與 `"Thinking..."` 標籤。
    - `isTextPhase = isStreaming && hasText`：在最終文字氣泡末端顯示閃爍游標 `▊`。
- **`ThinkingBubble` 設計與邊界情況處理**：
  - 預設收合（`useState(false)`），收合且非串流時顯示字元數（`Thought process (${charCount} chars)`）與前 `120` 字元的截斷預覽（`previewLength = 120`），切換按鈕應加上 `aria-expanded` 與 `aria-controls` 無障礙屬性。
  - **無推理區塊**：標準聊天模型僅回傳 `text` 區塊，`hasReasoning` 為 `false` 時不渲染 `ThinkingBubble`。
  - **空白推理區塊**：部分模型會產生空白佔位區塊，應以 `b.type === "reasoning" && b.reasoning.trim().length > 0` 過濾。
  - **多輪交錯（Interleaving）**：若需保留「推理 → 文字 → 推理」的交錯順序，應直接依序迭代 `message.contentBlocks.forEach((block) => ...)` 而非按型別分組。

### 4. 工具呼叫生命週期與型別安全卡片（`tool-calling.md`）
- **工具呼叫流程與 `stream.toolCalls`**：當 LangGraph 代理需要外部資料時，會在 `AIMessage` 中發出包含 `name`、`args`、`id` 的工具呼叫，執行完成後回傳 `ToolMessage`。`useStream` 將整個生命週期整合為單一響應式陣列 `stream.toolCalls`（Vue 為 `stream.toolCalls.value`，Angular 為 `stream.toolCalls()`）。
- **`AssembledToolCall` 介面定義**：
  ```ts
  interface AssembledToolCall<
    TName extends string = string,
    TInput = unknown,
    TOutput = unknown,
  > {
    name: TName;
    callId: string;
    id: string;
    namespace: string[];
    input: TInput;
    args: TInput;
    output: TOutput | null;
    status: "running" | "finished" | "error";
    error: string | undefined;
  }
  ```
  - **欄位說明**：`name` 為工具名稱（如 `"get_weather"`、`"calculator"`、`"web_search"`）；`callId`（與別名 `id`）對應 `AIMessage.tool_calls` 中的唯一 ID；`namespace` 為發出呼叫的命名空間陣列；`input`（與別名 `args`）為傳入工具的結構化參數；`output` 在執行中或錯誤時為 `null`，成功後為工具輸出；`status` 為 `"running"`、`"finished"` 或 `"error"`；`error` 為失敗時的錯誤資訊。
- **依訊息過濾與就地更新（In-place Updates）**：
  - 在單一 `AIMessage` 下渲染對應的工具卡片時，透過比對 `callId` 過濾：`toolCalls.filter((tc) => message.tool_calls?.find((t) => t.id === tc.callId))`。
  - 工具呼叫為**就地更新**：同一個 `callId` 會從 `"running"` 轉換為 `"finished"` 或 `"error"`。代理平行呼叫多個工具時，`toolCalls` 會同時有多筆 `status: "running"` 並各自獨立完成。
- **`ToolCallFromTool` 型別安全推論**：
  - 若工具使用 `@langchain/core/tools` 的 `tool(...)` 與 Zod `schema` 定義，可使用 `type WeatherToolCall = ToolCallFromTool<typeof getWeather>;` 取得編譯期型別安全的 `input` 與 `args`（例如 `{ location: string }`）。

### 5. 客戶端無頭工具（Headless Tools，`headless-tools.md`）
- **核心概念**：將工具的 Schema 定義與瀏覽器端實作分離，讓代理呼叫必須在客戶端執行的瀏覽器或裝置 API（如 IndexedDB、`localStorage`、`navigator.geolocation`、剪貼簿、相機、Canvas、檔案選擇器或前端記憶體狀態），同時讓隱私資料留在本地裝置。
- **後端與共用工具註冊**：
  - **Python 後端**：在伺服器端使用 `@tool("memory_put", description=..., args_schema=MemoryPutInput)`（接收 `runtime: ToolRuntime`）定義工具，並在函式內立即呼叫 `langgraph.types.interrupt` 將執行權交還前端：
    ```python
    return interrupt({
        "type": "tool",
        "tool_call": {
            "id": runtime.tool_call_id,
            "name": tool_name,
            "args": args,
        },
    })
    ```
    接著在前端 `tools.ts` 中使用 `"langchain"` 的 `tool({ name, description, schema })` 鏡像相同的工具名稱與參數 Schema（如 `memory_put`、`memory_get`、`geolocation_get`）。
  - **JS/TS 後端**：在共用的 `tools.ts` 中以 `tool({ name, description, schema: z.object(...) })` 定義僅含 Schema 的工具，同時供後端 `createAgent({ model: "openai:gpt-6.1-sol", tools: [memoryPut, memoryGet, geolocationGet], checkpointer: new MemorySaver() })` 與前端匯入使用。
- **前端 `.implement(...)` 與 `useStream({ tools })` 綁定**：
  - 在僅限客戶端載入的模組（`impl.ts`）中，對每個工具定義呼叫 `.implement(async (args) => { ... })` 附加瀏覽器實作（例如讀寫 `localStorage` 或呼叫 `navigator.geolocation.getCurrentPosition`）。回傳值必須為 **JSON 可序列化（JSON-serializable）** 物件，不可回傳 DOM 節點或檔案控制代碼。
  - 將實作後的工具陣列傳入 `useStream` 的 `tools` 選項：
    ```ts
    const stream = useStream<AgentState>({
      apiUrl: AGENT_URL,
      assistantId: "headless_tools",
      tools: [memoryPut, memoryGet, geolocationGet],
    });
    ```
  - 當代理發出匹配的工具呼叫時，`useStream` 會自動在客戶端執行對應實作，並以工具回傳結果自動恢復（Resume）被中斷的執行。
  - 在 UI 中渲染時，可從 `@langchain/react` 匯入 `type { ToolCallWithResult, DefaultToolCall }`，並以 `message.tool_calls?.some((call) => call.id === tc.call.id)` 關聯至觸發該呼叫的 `AIMessage`，或搭配 `onTool` 回呼展示狀態。

### 6. 結構化輸出渲染與漸進式串流（`structured-output.md`）
- **運作機制**：代理不回傳自由格式純文字，而是呼叫一個專門的「結構化輸出」工具，將符合預先定義 Schema（如包含 `problem`、`steps: { explanation: string; latex: string }[]`、`finalAnswer`、`finalAnswerLatex` 的 `MathSolution`）的結構化資料放在最後一則 `AIMessage` 的 `tool_calls[0].args` 中。
- **提取與防禦性檢查（`extractStructuredOutput`）**：
  - 串流期間 `tool_calls?.[0]?.args` 可能尚未完整產生或僅包含部分欄位。提取函式應支援 `requiredFields: string[]` 參數，確認關鍵欄位皆非 `undefined` 後才回傳完整型別物件：
    ```ts
    function extractStructuredOutput<T>(
      messages: any[],
      requiredFields: string[] = [],
    ): T | null {
      const aiMessages = messages.filter(AIMessage.isInstance);
      if (aiMessages.length === 0) return null;
      const lastAI = aiMessages[aiMessages.length - 1];
      const toolCall = lastAI.tool_calls?.[0];
      if (!toolCall?.args) return null;
      const args = toolCall.args as Record<string, unknown>;
      const hasRequired = requiredFields.every((field) => args[field] !== undefined);
      if (requiredFields.length > 0 && !hasRequired) return null;
      return args as T;
    }
    ```
- **漸進式渲染（Progressive Rendering）**：
  - 無需等待整個物件產生完畢，可提取 `extractStructuredOutput<Partial<MathSolution>>(messages)`，依照 Schema 由上而下的欄位生成順序（例如先顯示 `partial.problem`，接著逐項渲染 `partial.steps`，最後顯示 `partial.finalAnswer`）即時呈現畫面。
  - **設計建議**：盡量保持 Schema 扁平（避免深層巢狀導致部分串流解析困難），並為富文本欄位（如 LaTeX `finalAnswerLatex`）提供純文字備援欄位（`finalAnswer`）。

## 相關頁面
- [[guides/langchain-frontend-hitl-and-state-management]]
- [[guides/langchain-frontend-generative-ui-and-integrations]]
- [[concepts/langchain-streaming]]
- [[concepts/langchain-tools]]
- [[concepts/langchain-structured-output]]

## 出處
- docs/langchain/frontend/overview.md
- docs/langchain/frontend/markdown-messages.md
- docs/langchain/frontend/reasoning-tokens.md
- docs/langchain/frontend/tool-calling.md
- docs/langchain/frontend/headless-tools.md
- docs/langchain/frontend/structured-output.md
