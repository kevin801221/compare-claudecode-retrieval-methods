# LangChain Frontend Generative UI Spectrum and UI Library Integrations

別名：LangChain 生成式 UI 與前端整合、受控與宣告式及開放式生成式 UI、json-render 與 A2UI 與 MCP Apps、AI Elements 與 assistant-ui 與 CopilotKit 與 OpenUI 整合、Generative UI and Integrations
框架：langchain

## 摘要
生成式 UI（Generative UI）讓代理輸出超越純文字氣泡，直接驅動表單、卡片、儀表板與互動控制項。LangChain 依「誰負責編寫介面」將生成式 UI 劃分為受控（Controlled）、宣告式（Declarative，`json-render` 與 `A2UI`）與開放式（Open-ended，沙盒化 `MCP Apps`）三大光譜，並提供與四大主流 React UI 及生成式框架（`CopilotKit`、`AI Elements`、`assistant-ui`、`OpenUI`）的深度整合模式。

## 重點

### 1. 生成式 UI 光譜總覽（`generative-ui-overview.md`）
- **核心定義與光譜權衡**：生成式 UI 光譜由「**誰負責編寫介面（Who authors the interface?）**」決定。從左到右，可預測性（Predictability）、無障礙性（Accessibility）、視覺一致性與單一功能的工程成本逐漸降低，而代理的表達範圍（Expressive range）與自主性則逐漸提高：
  1. **Controlled（受控生成式 UI）**：開發者編寫所有元件，代理僅決定要渲染哪個元件並傳入資料（邊界為你的元件庫）。適合高流量、品牌關鍵且版面必須精確的核心表面（如機票、訂位確認單、表單）。
  2. **Declarative（宣告式生成式 UI）**：代理發出結構化規格（UI spec），前端從預先註冊的元件目錄（Catalog）組裝介面（邊界為註冊目錄）。適合次要互動、內部工具與儀表板等長尾場景（Long tail）。代表技術為 `json-render` 與透過 CopilotKit 整合的 Google `A2UI`。
  3. **Open-ended（開放式生成式 UI）**：代理擁有畫布，介面完全在應用程式外部建立（如由第三方 MCP 伺服器提供）並在隔離沙盒中渲染（邊界為沙盒與提示詞）。無需編寫前端程式碼即可擴充能力，適合一次性視覺化與第三方工具，但最不具決定性且必須嚴格沙盒隔離。
- **混合架構原則**：實務產品不應只選單一方法，而應在同一個工作階段中混合使用：核心高流量流程用 **Controlled**、長尾組合版面用 **Declarative**、第三方外部工具嵌入用 **Open-ended**。此光譜同樣適用於行動裝置、Slack 或 Email 等非聊天表面。

### 2. 受控生成式 UI（Controlled Generative UI，`controlled-generative-ui.md`）
- **核心特性**：代理永不產生標記語言（Markup），僅從開發者預先建置並測試過的固定元件集合中選擇。涵蓋以下四種技術（由代理選擇完整介面到前端反應代理內部狀態）：
  1. **Components as tools（將元件作為工具）**：像暴露工具一樣向代理暴露具有名稱、描述與型別化屬性（Props）的 UI 元件，代理選擇元件並提供資料，前端將其映射至真實元件實作（CopilotKit 文件稱此模式為 `components as tools`）。
  2. **Tool-call rendering（工具呼叫渲染）**：將工具呼叫的執行中（Pending）、完成（Complete）與失敗（Failed）生命週期階段轉為專用載入卡、結果卡與錯誤卡（透過 `stream.toolCalls`）。
  3. **State rendering（狀態渲染）**：將元件綁定至訊息列表以外的持久化型別狀態（`todos`、管線輸出、引用、沙盒檔案、指標、自訂商業物件）或單一結構化輸出（Structured output）酬載。
  4. **Reasoning（推理渲染）**：將具備延伸思考能力模型的推理區塊（Reasoning tokens）渲染於獨立的可收合區塊中。

### 3. 宣告式生成式 UI（Declarative Generative UI，`declarative-generative-ui.md`）
- **使用 `json-render` 實作宣告式 UI**：
  - **相關套件**：`@json-render/core`（匯出 `defineCatalog`）、`@json-render/react/schema`（匯出 `schema`）、`@json-render/react` 與 `@json-render/vue`（匯出 `defineRegistry`、`Renderer`、`JSONUIProvider`）。
  - **步驟一：定義元件目錄（`defineCatalog`）**：宣告 AI 可使用的元件、描述與 Zod 屬性 Schema：
    ```ts
    const catalog = defineCatalog(schema, {
      components: {
        Card: {
          description: "A card container with optional title and padding",
          props: z.object({
            title: z.string().optional(),
            padding: z.enum(["sm", "md", "lg"]).optional(),
          }),
        },
        Stack: {
          description: "Layout children vertically or horizontally with consistent spacing",
          props: z.object({
            direction: z.enum(["vertical", "horizontal"]).optional(),
            gap: z.enum(["sm", "md", "lg"]).optional(),
          }),
        },
        TextInput: {
          description: "A text input field with optional label and placeholder",
          props: z.object({
            label: z.string().optional(),
            placeholder: z.string().optional(),
            type: z.enum(["text", "email", "password", "number", "textarea"]).optional(),
          }),
        },
        Button: {
          description: "A clickable button with label and style variants",
          props: z.object({
            label: z.string(),
            variant: z.enum(["primary", "secondary", "ghost", "link"]).optional(),
            fullWidth: z.boolean().optional(),
          }),
        },
      },
      actions: {},
    });
    ```
  - **步驟二：建立元件註冊表（`defineRegistry`）**：將目錄中的元件名稱映射至 React JSX 或 Vue `h(...)` 實作（`const { registry } = defineRegistry(catalog, { components: { Card, Stack, TextInput, Button } });`）。
  - **步驟三：連接 `useStream` 並提取規格**：代理透過結構化輸出回傳規格，前端（`assistantId: "generative_ui"`）從 `const aiMessage = stream.messages.find(AIMessage.isInstance); const rawSpec = aiMessage?.tool_calls?.[0]?.args;` 讀取。
  - **步驟四：漸進式串流過濾與渲染**：
    - 串流期間元素逐一抵達，可能暫時缺少 `type` 或 `props`。必須先確認 `rawSpec?.root` 與 `rawSpec?.elements[rawSpec.root]` 具備有效 `type` 且 `props != null`，並過濾出所有 `el?.type && el?.props != null` 的 `safeElements`。
    - 渲染時**必須**以 `<JSONUIProvider registry={registry}>` 包裹 `<Renderer spec={spec} registry={registry} loading={stream.isLoading} />`（`JSONUIProvider` 提供內部狀態、可見度、驗證與動作 Context；`loading={true}` 指示 `Renderer` 靜默跳過尚未抵達的子節點）。
  - **JSON 規格格式（Spec Format）**：扁平 JSON 物件，包含指向根元素 ID 的 `"root"`（如 `"login-card"`）與包含所有元件的 `"elements"` 映射表；每個元素包含 `"type"`、`"props"` 與子元素 ID 陣列 `"children"`（如 `["email-input", "password-input", "submit-btn"]`，葉節點之 `children` 為 `[]`）。
- **替代宣告式規格：Google `A2UI`（透過 CopilotKit 整合）**：
  - Google 的串流優先宣告式生成式 UI 規格，分為兩種變體：
    - **Dynamic schema（動態 Schema）**：由次要模型根據對話生成包含 Schema、資料與版面配置的完整介面，具最大彈性。
    - **Fixed schema（固定 Schema）**：在前端預先定義元件樹，代理僅將資料串流填入其中，渲染最快且最可預測。

### 4. 開放式生成式 UI（Open-ended Generative UI，`open-ended-generative-ui.md`）
- **核心概念與 MCP Apps**：
  - 介面由應用程式外部的第三方（如 Model Context Protocol 伺服器）編寫，不由你或代理撰寫元件。
  - **MCP Apps**：將 MCP 從提供工具與資源延伸至互動式介面——MCP 伺服器直接交付互動式 UI，前端通常在對話中的 `iframe` 內直接渲染該畫面。伺服器擁有元件、資料與互動邏輯，而宿主應用程式僅提供外框與代理連線。
- **沙盒與安全性（Sandboxing and Safety）**：
  - 必須將第三方介面視為不可信任（Untrusted），放置於受限制的沙盒化環境（如 sandboxed `iframe`）中執行，限制其存取宿主頁面或使用者敏感資料的能力。

### 5. 前端 UI 函式庫整合比較（`integrations/overview.md`）
- **四大整合方案定位對照表**：
  - **CopilotKit**：最適用於「完整聊天執行期 + 結構化生成式 UI」；採用 CopilotKit 聊天外殼與自訂訊息渲染器；透過自訂後端端點、代理 Context 與渲染器客製化；由執行期管理聊天串流與結構化助理酬載；代理輸出結構化回應與選用 Markdown。
  - **AI Elements**：最適用於「包含豐富訊息型別的聊天」；採用可組合的 `shadcn/ui` 元件；直接編輯專案內的原始碼檔案；支援元件級漸進式渲染；使用 `Tool` / `ToolHeader` / `ToolOutput` 渲染工具呼叫；直接相容任何 `stream.messages`。
  - **assistant-ui**：最適用於「極簡設定的全功能聊天」；採用無頭插槽（Headless slots）加預設主題；透過覆寫元件插槽客製化；內建執行緒管理；透過訊息插槽自訂工具呼叫；透過轉接器連接任何 `stream.messages`。
  - **OpenUI**：最適用於「自動生成的儀表板與分析報告」；採用預建元件庫搭配宣告式 DSL；透過 CSS 自訂屬性（Custom properties）調整主題；支援提升（Hoisting，外殼立即出現、資料逐步填入）；工具呼叫直接內嵌於生成的 UI 中；代理輸出 `openui-lang` 程式碼文字。

### 6. AI Elements 整合（`integrations/ai-elements.md`）
- **安裝與架構**：
  - 執行 `npm install @langchain/react` 與 `npx ai-elements@latest add conversation message prompt-input tool reasoning suggestion`。
  - CLI 會以 `shadcn/ui` 註冊表風格將可自由修改的元件原始碼直接加入專案的 `@/components/ai-elements/` 目錄下。
- **核心元件與 `useStream` 綁定（`assistantId: "ai_elements"`）**：
  - **滾動容器**：`<Conversation className="flex-1"><ConversationContent>...</ConversationContent><ConversationScrollButton /></Conversation>` 自動管理新訊息滾動。
  - **訊息渲染**：以 `HumanMessage.isInstance(msg)` 與 `AIMessage.isInstance(msg)` 進行型別窄化（勿用 `msg.getType()`）。使用者訊息渲染為 `<Message from="user"><MessageContent>{msg.text}</MessageContent></Message>`；AI 回應使用 `<Message from="assistant"><MessageContent><MessageResponse>{getTextContent(msg)}</MessageResponse></MessageContent></Message>`（`MessageResponse` 專門處理串流中的部分 Token）。
  - **推理與工具區塊**：
    - `<Reasoning><ReasoningTrigger /><ReasoningContent>{getReasoningText(msg)}</ReasoningContent></Reasoning>`（提取 `msg.contentBlocks.find((block) => block.type === "reasoning")?.reasoning ?? ""`）。
    - 將 `msg.tool_calls ?? []` 映射為 `{ id: tc.id, name: tc.name, args: tc.args, state: "input-available" as const }`，並以 `<Tool key={tc.id} defaultOpen><ToolHeader type={`tool-${tc.name}`} state={tc.state} /><ToolContent><ToolInput input={tc.args} />{tc.output && <ToolOutput output={tc.output} errorText={undefined} />}</ToolContent></Tool>` 渲染。
  - **輸入框**：`<PromptInput onSubmit={({ text }) => stream.submit({ messages: [{ type: "human", content: text }] })}><PromptInputBody><PromptInputTextarea placeholder="Ask me something..." /></PromptInputBody><PromptInputFooter><PromptInputSubmit status={stream.isLoading ? "streaming" : "ready"} /></PromptInputFooter></PromptInput>`。

### 7. assistant-ui 整合（`integrations/assistant-ui.md`）
- **安裝與執行期橋接**：
  - 安裝：`bun add @assistant-ui/react @assistant-ui/react-markdown`。
  - 使用 `@assistant-ui/react` 的 `useExternalStoreRuntime<ThreadMessageLike>` 將 `useStream`（`assistantId: "claude"`）橋接至 `<AssistantRuntimeProvider runtime={runtime}><Thread /></AssistantRuntimeProvider>`：
    ```tsx
    const runtime = useExternalStoreRuntime<ThreadMessageLike>({
      messages,
      onNew,
      onCancel: () => stream.stop(),
      convertMessage: (m) => m,
    });
    ```
  - `onNew` 回呼：從 `message: AppendMessage` 過濾出 `c.type === "text"` 的內容合併後呼叫 `await stream.submit({ messages: [{ type: "human", content: text }] })`。
- **訊息格式轉換（`toThreadMessages(messages: BaseMessage[]): ThreadMessageLike[]`）**：
  - 務必使用 `useMemo` 快取轉換結果：
    - `HumanMessage.isInstance(msg)`：轉為 `{ role: "user", content: [{ type: "text", text: msg.text }] }`。
    - `AIMessage.isInstance(msg)`：建立 `parts` 陣列，依序加入推理區塊 `{ type: "reasoning", text: reasoning }`、工具呼叫 `{ type: "tool-call", toolCallId: tc.id ?? "", toolName: tc.name, args: tc.args }` 與文字回應 `{ type: "text", text }`，回傳 `{ role: "assistant", content: parts }`。
    - `ToolMessage.isInstance(msg)`：尋找前一則 `role === "assistant"` 訊息中 `part.type === "tool-call" && part.toolCallId === msg.tool_call_id` 的項目，將 `msg.text` 掛載至 `(part as { result?: string }).result = msg.text`。
- **插槽客製化與進階功能**：
  - 使用 `<Thread.Root><ThreadMessages components={{ UserMessage: MyUserMessage, AssistantMessage: MyAssistantMessage, ToolFallback: MyToolCard }} /><Composer /></Thread.Root>` 覆寫特定元件插槽。
  - 支援以 `CompositeAttachmentAdapter` 搭配 `SimpleImageAttachmentAdapter` 處理圖片上傳，並支援 `MessageBranch` 分支切換（可搭配 `useMessageMetadata` 與 `forkFrom`）。

### 8. CopilotKit 與 Hashbrown 及 Channels 整合（`integrations/copilotkit.md`）
- **架構與 AG-UI 協定**：
  - 讓 LangGraph 圖、LangChain `create_agent` / `createAgent` 或 Deep Agents `create_deep_agent` 透過 **Agent UI（AG-UI）** 協定與 React 前端通訊，並結合 **Hashbrown**（`@hashbrownai/core`、`@hashbrownai/react`）將結構化 JSON 回應渲染為動態 React 元件樹。
- **JavaScript / TypeScript 後端部署設定**：
  - 安裝：`bun add @copilotkit/runtime hono`。
  - 在 `langgraph.json` 中同時設定 `"graphs": { "copilotkit_shadify": "./src/agents/copilotkit-shadify.ts:agent" }` 與自訂 HTTP 應用程式 `"http": { "app": "./src/api/app.ts:app" }`。
  - 在 Hono 路由中，使用 `@copilotkit/runtime/v2` 的 `CopilotRuntime` 與 `createCopilotEndpointSingleRoute({ runtime, basePath: "/api/copilotkit" })`，並繼承 `@copilotkit/runtime/langgraph` 的 `LangGraphAgent` 建立 `BridgedLangGraphAgent`（覆寫 `prepareRunAgentInput` 將 `{ description, value }` 陣列格式的 `context` 正規化為鍵值物件，並覆寫 `getAssistant` 以 `graphId` 搜尋助理）。
  - 在代理端建立 `structuredOutputMiddleware`（`createMiddleware` 搭配 `name: "CopilotKitStructuredOutput"` 與 `wrapModelCall`），從 `runtime.context?.output_schema` 或 `runtime.configurable?.output_schema` 讀取前端傳來的 JSON Schema（若缺少頂層 `title` 與 `description` 則補上預設值 `"CopilotKitStructuredOutput"`），並透過 `"langchain"` 的 `toolStrategy(schema, { toolMessageContent: "Structured UI response generated." })` 設定為 `responseFormat`。
- **Python 後端與雙程序架構（AG-UI FastAPI Bridge + Node CopilotKit Runtime）**：
  - Python 套件安裝：`uv add copilotkit ag-ui-langgraph fastapi uvicorn`（搭配 Deep Agents 則安裝 `uv add deepagents copilotkit langchain-openai`）。
  - **Python 伺服器端四大核心元件**：
    1. `CopilotKitMiddleware`（來自 `copilotkit`）：加入 `create_agent` 或 `create_deep_agent` 的 `middleware` 列表中，負責整合 AG-UI 狀態、前端工具呼叫與 Context。
    2. `CopilotKitState`（來自 `copilotkit`）：繼承 `class AgentState(CopilotKitState): pass` 並傳入 `state_schema=AgentState`，使 `copilotkit` 狀態切片成為圖狀態的一部分。
    3. `LangGraphAGUIAgent`（來自 `copilotkit`）：包裝編譯後的圖與名稱、描述。**檢查點重要限制**：切勿在 `langgraph.json` 的 `graphs` 所列出的 `agent` 本身上直接設定 `checkpointer`（否則 `langgraph dev` 會拒絕載入）；必須僅在傳給 FastAPI 路由的副本上附加檢查點：`graph=agent.copy(update={"checkpointer": MemorySaver()})`（正式環境應替換為持久化 Checkpointer）。
    4. `add_langgraph_fastapi_endpoint(app=app, agent=LangGraphAGUIAgent(...), path="/")`（來自 `ag_ui_langgraph`）：在 `main.py` 中將 AG-UI 橋接器掛載至 `FastAPI()` 實例，並在 `langgraph.json` 設定 `"http": { "app": "./main.py:app" }`。
  - **Python 結構化輸出中介軟體（`src/middleware.py`）**：使用 `@before_agent def normalize_context(state, runtime)` 將 `state["copilotkit"]["context"]` 中的項目呼叫 `.model_dump()` 正規化；使用 `@wrap_model_call async def apply_structured_output_schema(request, handler)` 讀取 `output_schema`，補齊 OpenAI 必填的頂層 `"title": "CopilotKitStructuredOutput"` 與 `"description"`，並呼叫 `request.override(response_format=ProviderStrategy(schema=schema, strict=True))`（`ProviderStrategy` 來自 `langchain.agents.structured_output`）。
  - **獨立 Node CopilotKit Runtime 伺服器**：因為 FastAPI 路由講的是 AG-UI 協定而非 CopilotKit Runtime 協定（若前端 `runtimeUrl` 直接指向 FastAPI 會導致 `runtime_info_fetch_failed` 錯誤），必須額外啟動一個小型 Node 伺服器（安裝已知相容組合 `bun add @copilotkit/runtime@1.73.3 @ag-ui/client@0.0.59`），使用 `@ag-ui/client` 的 `new HttpAgent({ url: agentUrl })`、`@copilotkit/runtime/v2` 的 `CopilotRuntime` 與 `@copilotkit/runtime/v2/node` 的 `createCopilotNodeListener({ runtime, basePath: "/api/copilotkit", cors: true })` 監聽 `4000` 連接埠。
- **前端應用程式與 Hashbrown 動態元件註冊**：
  - 前端安裝：`bun add @copilotkit/react-core @copilotkit/react-ui @hashbrownai/core @hashbrownai/react`。
  - 以 `<CopilotKit runtimeUrl={import.meta.env.VITE_RUNTIME_URL ?? "/api/copilotkit"}>` 包裹應用程式，在頁面內呼叫 `@copilotkit/react-core/v2` 的 `useAgentContext({ description: "output_schema", value: s.toJsonSchema(chatKit.schema) })` 將 UI Schema 傳給後端，並渲染 `<CopilotChat {...chatTheme} />`。
  - 在 `useChatKit()` 中使用 `@hashbrownai/react` 的 `useUiKit({ components: [...] })`、`exposeMarkdown()` 與 `exposeComponent(Component, { name, description, props, children })`（搭配 `@hashbrownai/core` 的 `s.string`、`s.number`、`s.array`、`s.streaming.string`；`children` 可設為 `"any"`、`"text"` 或 `false`）定義允許代理使用的元件（如 `card`、`row`、`column`、`chart`、`code_block`、`button`）。
  - 在 `CustomMessageRenderer`（接收 `@copilotkit/react-ui` 的 `RenderMessageProps`）中，針對 `message.role === "assistant"`（型別為 `@ag-ui/core` 的 `AssistantMessage`）呼叫 `@hashbrownai/react` 的 `const { value } = useJsonParser(message.content ?? "", kit.schema)` 解析並以 `{kit.render(value)}` 渲染為 React 元件。
- **CopilotKit Channels（Slack、Teams 等通訊平台整合）**：
  - 透過託管的 **CopilotKit Intelligence** 閘道將同一個 LangChain 代理連接至 Slack（已正式推出 GA）、Microsoft Teams（受控整合目標）或直接使用 Teams、Discord、Telegram、WhatsApp 轉接器，平台憑證保存在 Intelligence 中（提供 `CHANNEL_CODE` 與 `INTELLIGENCE_API_KEY`），且回覆會自動轉為原生 Slack Block Kit。
  - **版本與環境要求**：必須同時安裝精確測試配對 `@copilotkit/channels@0.6.1` 與 `@copilotkit/runtime@1.65.0`（`--save-exact`），並執行於 **Node.js 22+** 長時間運作主機（使用 `NodeNext` TypeScript 設定）。
  - Channels 監聽器不透過 FastAPI 橋接路由，而是直接使用 `@copilotkit/runtime/langgraph` 的 `LangGraphAgent`（勿用 `HttpAgent`）連接部署的圖 API，並依執行緒（Thread）隔離每次對話的代理實例。

### 9. OpenUI 與 Deep Agents 平行儀表板整合（`integrations/openui.md`）
- **核心概念與 `openui-lang` 格式**：
  - OpenUI 讓模型輸出名為 **`openui-lang`** 的宣告式賦值程式語言（而非 JSON），每行皆為變數賦值，並以 `root` 作為入口點（例如 `root = Stack([header, execSummary, kpis, marketSection])`、`CardHeader`、`MarkDownRenderer`、`Card`、`TextContent`、`Col`、`Table`、`Series`、`BarChart`、`Button`、`Buttons`）。
  - **提升（Hoisting）**：模型在第一行先寫 `root = Stack([...])`，讓頁面外殼結構立即呈現，隨後各區塊隨變數定義逐一填入。
- **安裝與環境需求**：
  - 執行 `npm install @langchain/react @openuidev/react-ui @openuidev/react-headless @openuidev/react-lang`。
  - 需求：**React 19+** 與 `zustand`。必須匯入樣式 `@import "@openuidev/react-ui/components.css";` 與 `@import "@openuidev/react-ui/styles/index.css";`。
- **系統提示詞生成、注入與渲染**：
  - 在模組載入階段（切勿在元件每次渲染時）呼叫 `@openuidev/react-ui/genui-lib` 的 `openuiLibrary.prompt({ ...openuiPromptOptions, preamble: "...", additionalRules: [...] })` 產生數 KB 的完整語法參考。
  - 僅在新執行緒的第一則訊息（`const isNewThread = stream.messages.length === 0;`）前置注入 `{ type: "system", content: SYSTEM_PROMPT }`。
  - 使用 `@openuidev/react-lang` 的 `<Renderer response={text} library={openuiLibrary} isStreaming={isLoading && i === lastAiIdx} onAction={handleAction} />` 渲染。當使用者點擊帶有 `{ type: "continue_conversation" }` 的後續查詢按鈕時，`onAction` 會收到 `event.type === BuiltinActionType.ContinueConversation`，即可將 `event.humanFriendlyMessage` 送回 `onSubmit`。
- **漸進式渲染五大工具函式（解決串流閃爍與圖表崩潰）**：
  1. `stripCodeFence(text)`：移除模型可能誤加的 Markdown 程式碼區塊圍欄。
  2. `sanitizeIdentifiers(text)`：`openui-lang` 解析器僅接受 `camelCase` 變數名稱，此函式在不影響字串常值內容的前提下將所有 `snake_case` 變數名轉為 `camelCase`。
  3. `truncateAtOpenString(text)` 與 `closeOrTruncateOpenString(text)`：若串流文字停在未閉合字串中間，截斷至最後一個安全換行處；但若該未完成行為 `TextContent(` 敘述，則自動補上閉合 `' )'` 讓文字內容能逐 Token 即時顯示。
  4. `countCompleteStatements(text)` 與 `useStableText(raw, isStreaming)`：計算以 `)` 或 `]` 結尾的完整賦值敘述數量，僅在有新完整敘述抵達（或 `TextContent` 更新）時才更新傳給 `Renderer` 的文字，消除數百次無效重解析。
  5. `chartDataRefsResolved(text)` 與 `buildProgressiveRoot(text)`：確認所有圖表元件（`BarChart`、`LineChart`、`AreaChart`、`RadarChart`、`HorizontalBarChart`、`PieChart`、`RadialChart`、`SingleStackedBarChart`、`ScatterChart`）引用的資料變數皆已定義後才提交快照（防止 Recharts 因 `.map() on null` 崩潰）；若模型尚未寫出 `root = ...`，則自動從未被其他表達式引用的頂層變數合成 `root = Stack([topLevelVars], "column", "l")`。
- **結合 Deep Agents 建構平行串流儀表板（Parallel Dashboard）**：
  - 在伺服器與客戶端共用 `@openuidev/react-ui` 的 `openuiChatLibrary` 與 `openuiChatPromptOptions`。
  - 使用 `"deepagents"` 的 `createDeepAgent` 建立只負責路由的協調者（如 `COORDINATOR_MODEL = "openai:gpt-5.4-mini"`），在**單一訊息**中同時發出多個平行 `task()` 呼叫委派給各領域面板子代理（`SubAgent[]`，如 `"stripe-panel"`、`"posthog-panel"`、`"github-panel"`、`"calendar-panel"`，使用 `PANEL_MODEL = "openai:gpt-6.1-sol"` 與共用的 `PANEL_SYSTEM_PROMPT`）。
  - 在前端（`assistantId: "dashboard"`）透過單一 `useStream` 連線探索頂層子代理：`const panels = [...stream.subagents.values()].filter((snapshot) => snapshot.parentId === null);`（型別為 `@langchain/langgraph-sdk/stream` 的 `SubagentDiscoverySnapshot`）。
  - 為每個面板渲染經過 `memo` 包裝的 `<Panel>` 元件，並在內部呼叫 `@langchain/react` 的 `const messages = useMessages(stream, snapshot);` 將訊息範圍限定於該子代理，使各面板獨立串流且互不觸發重渲染。

## 相關頁面
- [[guides/langchain-frontend-streaming-and-tools]]
- [[guides/langchain-frontend-hitl-and-state-management]]
- [[concepts/langchain-agents]]
- [[concepts/langchain-structured-output]]

## 出處
- docs/langchain/frontend/generative-ui-overview.md
- docs/langchain/frontend/controlled-generative-ui.md
- docs/langchain/frontend/declarative-generative-ui.md
- docs/langchain/frontend/open-ended-generative-ui.md
- docs/langchain/frontend/integrations/overview.md
- docs/langchain/frontend/integrations/ai-elements.md
- docs/langchain/frontend/integrations/assistant-ui.md
- docs/langchain/frontend/integrations/copilotkit.md
- docs/langchain/frontend/integrations/openui.md
