# LangGraph Application Structure, Local Server, Studio, Deployment, Observability, and Testing

別名：LangGraph 專案結構、本地開發伺服器、LangSmith Studio、Agent Chat UI、部署與可觀測性、單元測試、langgraph.json、langgraph dev
框架：langgraph

## 摘要
LangGraph 應用程式由一個或多個圖（Graphs）、設定檔 `langgraph.json`、依賴管理檔（`requirements.txt`、`pyproject.toml` 或 `package.json`）與 `.env` 環境變數檔組成。開發階段可透過 LangGraph CLI（`langgraph dev` 或 `npx @langchain/langgraph-cli dev`）在本地啟動預設連接埠 `2024` 的記憶體內 Agent Server，並連接 **LangSmith Studio** 與 **Agent Chat UI** 進行即時視覺化除錯與熱重載；測試階段可利用 `pytest` 或 `vitest` 搭配 `MemorySaver`、`compiled_graph.nodes["..."].invoke()` 及 `update_state(..., as_node=...)` 進行單節點或局部路徑測試；生產階段則支援部署至 **LangSmith Cloud**（或 Hybrid、Standalone Server、Self-Hosted with Control Plane 與各式 JS 平台），並透過 `langsmith` 的 `tracing_context`、`LangChainTracer` 與 `create_anonymizer` 實現選擇性追蹤與敏感資料遮罩。

## 重點

### 1. 應用程式結構（Application Structure）與 `langgraph.json` 設定檔
- **四大核心組成**：
  1. **設定檔（`langgraph.json`）**：預設放置於當前工作目錄，定義應用程式的 `dependencies`、`graphs`、`env`、`node_version`、`dockerfile_lines` 等設定。
  2. **圖（Graphs）**：實作應用邏輯的編譯後圖物件（如 `StateGraph.compile()`、`create_agent()` / `createAgent()`）或回傳圖的工廠函式。
  3. **依賴宣告檔（Dependencies）**：Python 使用 `requirements.txt` 或 `pyproject.toml`；TypeScript/JavaScript 使用 `package.json`。
  4. **環境變數（Environment Variables）**：本地開發透過 `.env` 檔案載入；正式部署則於部署環境中配置。
- **標準目錄結構範例**：
  - Python：`my-app/` 下包含 `my_agent/`（內含 `__init__.py`、`agent.py` 及 `utils/__init__.py`、`utils/tools.py`、`utils/nodes.py`、`utils/state.py`）、`.env`、`requirements.txt`（或 `pyproject.toml`）與 `langgraph.json`。
  - JS/TS：`my-app/` 下包含 `src/`（內含 `agent.ts` 及 `utils/tools.ts`、`utils/nodes.ts`、`utils/state.ts`）、`package.json`、`.env` 與 `langgraph.json`。
- **`langgraph.json` 關鍵欄位與語法**：
  - `"dependencies"`：陣列，指定執行所需的套件或本地路徑，例如 Python 的 `["langchain_openai", "./your_package"]` 或 `["."]`，JS 的 `["."]`。
  - `"graphs"`：映射物件，鍵為唯一的圖／助理名稱（Graph ID / Assistant ID），值為 `"<檔案路徑>:<變數或函式名稱>"`，例如 `"my_agent": "./your_package/your_file.py:agent"`、`"agent": "./src/agent.py:agent"` 或 `"agent": "./src/agent.ts:agent"`。
  - `"env"`：可為指向 `.env` 檔案的路徑字串（如 `"./.env"` 或 `".env"`），或直接內嵌鍵值對物件（如 `{"OPENAI_API_KEY": "secret-key"}`）。
  - `"node_version"`（JS/TS）：指定 Node.js 版本，例如 `"24"`。
  - `"dockerfile_lines"`：陣列，用於在建置容器映像時附加額外的系統二進位檔或底層函式庫安裝指令。

### 2. 本地伺服器（Local Server）與 LangGraph CLI
- **安裝 LangGraph CLI**：
  - Python（**強制要求 Python >= 3.11**）：`pip install -U "langgraph-cli[inmem]"` 或 `uv add "langgraph-cli[inmem]"`。
  - JS/TS：`npm install --save-dev @langchain/langgraph-cli`。
- **從範本建立專案或自動產生設定檔**：
  - Python：執行 `langgraph new path/to/your/app --template new-langgraph-project-python`（若不帶 `--template` 參數直接執行 `langgraph new`，會顯示互動式選單供挑選範本），接著進入目錄執行 `pip install -e .` 或 `uv sync` 以可編輯模式安裝依賴。
  - JS/TS：執行 `npm create langgraph`（使用 `new-langgraph-project-js` 範本）並執行 `npm install`。
  - **既有 JS 專案自動掃描（`npm create langgraph config`）**：自動掃描專案中的 `createAgent()`、`StateGraph.compile()` 或 `workflow.compile()` 模式，將所有具 `export` 關鍵字匯出的代理人寫入 `langgraph.json`（未 `export` 的代理人會發出警告）。
- **啟動本地開發伺服器（In-Memory Mode）**：
  - Python：`langgraph dev`
  - JS/TS：`npx @langchain/langgraph-cli dev`
  - **預設端點輸出**：
    - API 端點：`http://127.0.0.1:2024`（或 `http://localhost:2024`）
    - Studio UI：`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`（若自訂主機或連接埠，修改 URL 中的 `baseUrl` 查詢參數即可，例如 `?baseUrl=http://myhost:3000`）
    - API Docs：`http://127.0.0.1:2024/docs`
  - **Safari 瀏覽器相容性（`--tunnel` 旗標）**：Safari 會阻擋對 `localhost` 的連線；執行 `langgraph dev --tunnel` 可建立安全通道，並在 Studio UI 點擊 **Connect to a local server** 將 tunnel URL 加入允許來源。

### 3. LangSmith Studio 與 Agent Chat UI
- **LangSmith Studio**：
  - 免費的本地視覺化開發與除錯介面，支援**熱重載（hot-reloading）**——修改程式碼中的提示詞或工具簽名會立即反映在 Studio 中，且可從對話執行緒（thread）的任意步驟重新執行（re-run）而不必從頭開始。
  - **環境變數設定（`.env`）**：
    - `LANGSMITH_API_KEY=lsv2...`
    - `LANGSMITH_AGENT_ID="<your-agent-id>"`
    - `LANGSMITH_AGENT_ENVIRONMENT="local"`
    - 若不希望任何資料離開本地伺服器上傳至 LangSmith，可在 `.env` 中設定 `LANGSMITH_TRACING=false`。
- **Agent Chat UI**：
  - 開箱即用的聊天前端介面，支援連線至本地（`http://localhost:2024`）或已部署的 Agent Server，內建工具呼叫（tool calls）與工具結果訊息的渲染，並會自動抓取及顯示任何處於中斷狀態（interrupted）的執行緒。
  - 啟動後需配置三項參數：
    1. **Graph ID**：在 `langgraph.json` 的 `graphs` 下定義的圖名稱。
    2. **Deployment URL**：Agent Server 端點（例如本地 `http://localhost:2024` 或正式部署 URL）。
    3. **LangSmith API key (optional)**：連接本地 Agent Server 時非必填。

### 4. 部署（Deployment）與 LangGraph SDK 呼叫方式
- **部署選項**：
  - **LangSmith Agent Server 託管方案**：包含 **LangSmith Cloud**（從公開或私有 GitHub 儲存庫全託管部署，於 LangSmith 左側欄點選 **Agent Servers** → **+ Agent Server** → 連結 GitHub 帳號並選擇 repo → 點擊 **Submit**，約 15 分鐘完成部署）、**Hybrid（混合雲）**、**Standalone Servers（獨立伺服器）** 與 **Self-Hosted with Control Plane（附控制平面的自託管）**。
  - **JavaScript 框架與平台**：支援透過相同的 Agent Streaming Protocol 部署至 Next.js、SvelteKit、Nuxt、Cloudflare Workers 與 Deno Deploy。
- **使用 SDK 與 REST API 測試（Threadless Run 範例）**：
  - **Python SDK（`pip install langgraph-sdk`）**：
    - 非同步：`from langgraph_sdk import get_client` 建立 `client = get_client(url="http://localhost:2024")`（雲端部署則加傳 `api_key="your-langsmith-api-key"`）。
    - 同步：`from langgraph_sdk import get_sync_client` 建立 `client = get_sync_client(url=..., api_key=...)`。
    - 串流呼叫：`client.runs.stream(None, "agent", input={"messages": [{"role": "human", "content": "What is LangGraph?"}]}, stream_mode="messages-tuple")`（或 `stream_mode="updates"`），迭代讀取 `chunk.event` 與 `chunk.data`。第一個參數傳入 `None` 代表無執行緒（Threadless）執行。
  - **JavaScript / TypeScript SDK（`npm install @langchain/langgraph-sdk`）**：
    - `import { Client } from "@langchain/langgraph-sdk"`，建立 `const client = new Client({ apiUrl: "http://localhost:2024", apiKey: "..." })`。
    - 呼叫 `client.runs.stream(null, "agent", { input: { messages: [{ role: "user", content: "What is LangGraph?" }] }, streamMode: "messages-tuple" })`（或 `"messages"`），以 `for await (const chunk of streamResponse)` 讀取 `chunk.event` 與 `chunk.data`。
  - **REST API（`curl`）**：
    - 對 `<DEPLOYMENT_URL>/runs/stream` 發送 `POST` 請求，標頭帶 `Content-Type: application/json` 與（雲端部署時）`X-Api-Key: <LANGSMITH API KEY>`，Body JSON 包含 `"assistant_id": "agent"`、`"input": {"messages": [...]}` 與 `"stream_mode": "messages-tuple"`（或 `"updates"`）。

### 5. LangSmith 可觀測性（Observability）與敏感資料遮罩
- **全域啟用追蹤環境變數**：
  - `LANGSMITH_AGENT_ID="<your-agent-id>"`
  - `LANGSMITH_AGENT_ENVIRONMENT="local"`
  - `LANGSMITH_TRACING=true`
  - `LANGSMITH_API_KEY=<your-api-key>`
  - 在專案制工作區（Project-based workspaces）或自託管 LangSmith 中，改設 `LANGSMITH_PROJECT` 指定追蹤專案名稱（若整合套件在 agent-based 工作區中要求 `project_name`，可使用環境的 `tracer_session_name` 作為相容值）。
- **選擇性追蹤（Trace Selectively）**：
  - Python：匯入 `import langsmith as ls`，使用上下文管理器 `with ls.tracing_context(enabled=True):` 包裹特定 `agent.invoke(...)` 呼叫。
  - JS/TS：匯入 `import { LangChainTracer } from "@langchain/core/tracers/tracer_langchain"`，建立 `const tracer = new LangChainTracer()` 並於呼叫時傳入 `await agent.invoke(input, { callbacks: [tracer] })`。
- **附加自訂 Metadata 與 Tags**：
  - 可在 `agent.invoke(input, config={"tags": ["production", "email-assistant", "v1.0"], "metadata": {"user_id": "user_123", "session_id": "session_456", "environment": "production"}})` 中傳遞；Python 的 `ls.tracing_context(enabled=True, tags=[...], metadata={...})` 亦直接接受 `tags` 與 `metadata` 參數。
- **使用 Anonymizer 遮罩敏感資料（防止 PII 寫入 Traces）**：
  - Python：從 `langsmith.anonymizer` 匯入 `create_anonymizer`，從 `langsmith` 匯入 `Client`，從 `langchain_core.tracers.langchain` 匯入 `LangChainTracer`。建立規則如 `anonymizer = create_anonymizer([{"pattern": r"\b\d{3}-?\d{2}-?\d{4}\b", "replace": "<ssn>"}])`，傳入 `tracer_client = Client(anonymizer=anonymizer)` 與 `tracer = LangChainTracer(client=tracer_client)`，最後在編譯圖後綁定：`graph = StateGraph(MessagesState)...compile().with_config({'callbacks': [tracer]})`。
  - JS/TS：從 `"langsmith/anonymizer"` 匯入 `createAnonymizer`，從 `"langsmith"` 匯入 `Client`，從 `"@langchain/core/tracers/tracer_langchain"` 匯入 `LangChainTracer`，最後呼叫 `.compile().withConfig({ callbacks: [tracer] })`。

### 6. 測試自訂圖與節點（Testing）
- **測試框架**：Python 使用 `pytest`（`pip install -U pytest`）；JS/TS 使用 `vitest`（`npm install -D vitest`）。
- **模式一：每次測試重新建立圖與記憶體內 Checkpointer**：
  - 建立工廠函式 `create_graph()` / `createGraph()` 回傳未編譯的 `StateGraph`，在每個測試函式內實例化全新的 `MemorySaver()`（或 `InMemorySaver`）並呼叫 `graph.compile(checkpointer=checkpointer)`，再以 `compiled_graph.invoke({"my_key": "initial_value"}, config={"configurable": {"thread_id": "1"}})` 驗證端到端狀態演進。
- **模式二：單獨測試個別節點（`compiled_graph.nodes`）**：
  - 編譯後的圖透過 `compiled_graph.nodes` 暴露各個節點的參照。可直接呼叫 `compiled_graph.nodes["node1"].invoke({"my_key": "initial_value"})`（Python）或 `await compiledGraph.nodes['node1'].invoke({ my_key: 'initial_value' })`（JS）進行單節點單元測試。**注意：此方式會完全略過編譯時傳入的任何 checkpointer**。
- **模式三：局部路徑執行測試（Partial Execution）**：
  - 在不將大型圖重構為子圖的前提下，可利用持久化機制模擬「在指定區段起點前暫停、並在指定區段終點後再次暫停」來測試中間區段（例如在 `node1 -> node2 -> node3 -> node4` 中僅執行 `node2` 與 `node3`）：
    1. 使用 `MemorySaver()`（或 `InMemorySaver`）編譯圖。
    2. 呼叫更新狀態方法，將 `as_node`（Python）或第三個參數 `asNode`（JS）設為目標起點**前一個**節點的名稱（如 `"node1"`），寫入模擬狀態：
       - Python：`compiled_graph.update_state(config={"configurable": {"thread_id": "1"}}, values={"my_key": "initial_value"}, as_node="node1")`
       - JS/TS：`await compiledGraph.updateState({ configurable: { thread_id: '1' } }, { my_key: 'initial_value' }, 'node1')`
    3. 以相同的 `thread_id`、輸入傳入 `None`（Python）或 `null`（JS）恢復執行，並指定在目標終點節點後中斷：
       - Python：`compiled_graph.invoke(None, config={"configurable": {"thread_id": "1"}}, interrupt_after="node3")`
       - JS/TS：`await compiledGraph.invoke(null, { configurable: { thread_id: '1' }, interruptAfter: ['node3'] })`（注意文檔說明文字亦提及 `interruptBefore`，程式碼範例則使用 `interruptAfter: ['node3']` 以在 `node3` 結束後停止，使 `node4` 不執行）。

### 7. 生產環境企業案例（Case Studies）
- 公開採用 LangGraph 的企業與應用場景涵蓋：
  - **程式碼生成與開發者生產力（Code generation / Developer productivity / DevOps）**：GitLab（Duo workflow）、Replit、Uber、LinkedIn（亦用於 Text-to-SQL 與搜尋探索）、Qodo、Inconvo、Vodafone（亦用於內部搜尋）、Cisco Outshift（DevOps）。
  - **領域專屬 Copilot 與金融／醫療／法律／房地產應用**：BlackRock、J.P. Morgan、Klarna、Rakuten、Komodo Health、City of Hope、OpenRecovery、Vizient、Definely（法律）、AppFolio（房地產）、Rexera（房地產）、Elastic、Tradestack、Unify。
  - **客戶支援（Customer support）**：Cisco CX、Cisco TAC、Infor、Minimal、Prosper。
  - **搜尋、研究摘要與資料擷取（Search / Research & summarization / Data extraction）**：Exa、Harmonic、Abu Dhabi Government（搜尋）；Athena Intelligence、Morningstar、11x（研究與外展）；Captide、WebToon（資料擷取）。
  - **自動化與嵌入式 GenAI 產品體驗**：AirTop（瀏覽器自動化）、C.H. Robinson（物流自動化）、Docent Pro、Modern Treasury、Monday、Pigment。

## 相關頁面
- [[concepts/langgraph-streaming]]
- [[guides/langgraph-agentic-rag-and-sql-agent]]
- [[versions/langgraph-backward-compatibility-and-changelogs]]

## 出處
- docs/langgraph/application-structure.md
- docs/langgraph/local-server.md
- docs/langgraph/deploy.md
- docs/langgraph/studio.md
- docs/langgraph/ui.md
- docs/langgraph/observability.md
- docs/langgraph/test.md
- docs/langgraph/case-studies.md
