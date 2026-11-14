# LangChain RAG, SQL Agent, Voice Agent, and Deep Agent Guides

別名：語意搜尋與知識庫、SQL 資料庫代理、語音代理、從零打造 Deep Agent、Semantic Search、RAG、SQL Agent、Voice Agent、Sandwich Architecture、Deep Agent from Scratch
框架：langchain

## 摘要
本頁彙整 LangChain 四大實戰應用架構指南：(1) 使用 `Document`、`RecursiveCharacterTextSplitter`、`Embeddings`、`VectorStore` 與 `VectorStoreRetriever` 建構 PDF 語意搜尋引擎與知識庫（RAG 基礎）；(2) 結合資料庫查詢與驗證工具及 `HumanInTheLoopMiddleware` 建構具備自我除錯與人工審批能力的 SQL Agent；(3) 採用「STT（AssemblyAI）→ LangChain Agent → TTS（Cartesia）」三明治串流架構（Sandwich Architecture）建構次秒級延遲（sub-700ms）的雙向 WebSocket 語音代理；(4) 使用 `create_agent` 逐步掛載 `LangSmithSandbox`、`FilesystemMiddleware`、`SummarizationMiddleware`、`SkillsMiddleware`、`TodoListMiddleware` 與 `SubAgentMiddleware`，從零組裝出與 `create_deep_agent` 等價的資料分析 Deep Agent。

## 重點

### 一、語意搜尋引擎與知識庫（Semantic Search / Knowledge Base & Retrieval）
- **文件路由備註**：`docs/langchain/retrieval.md` 為重新導向頁面（`url: "/oss/deepagents/retrieval"`，`noindex: true`）。
- **`Document` 抽象結構**（Python：`from langchain_core.documents import Document` / JS：`import { Document } from "@langchain/core/documents"`）：
  - 包含三個屬性：`page_content`（Python） / `pageContent`（JS，字串內容）、`metadata`（任意詮釋資料字典，如 `source`、`page`、`start_index`）、`id`（選用的字串識別碼）。
- **PDF 載入與文件切分（Load & Split）**：
  - PDF 解析套件：Python 安裝 `pypdf`（使用 `pypdf.PdfReader(file_path)` 與 `page.extract_text()`，或使用整合套件 `PyPDFLoader`）；JS 安裝 `pdf-parse`（使用 `new PDFParse({ data: new Uint8Array(readFileSync(filePath)) })`、`.getText()` 與 `.destroy()`）。範例使用 107 頁的 Nike 2023 10-K 財報（`nke-10k-2023.pdf`）。
  - 文字切分器：使用通用文字推薦的 `RecursiveCharacterTextSplitter`（Python：`from langchain_text_splitters import RecursiveCharacterTextSplitter`；JS：`import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters"`）。
  - 設定 `chunk_size=1000` / `chunkSize: 1000`、`chunk_overlap=200` / `chunkOverlap: 200`；Python 可額外設定 `add_start_index=True`，在每個切分後 chunk 的 `metadata` 中保留其在原始文件中的字元偏移量 `start_index`（107 頁 PDF 切分為 516 個 chunks）。呼叫 `text_splitter.split_documents(docs)` / `await textSplitter.splitDocuments(docs)`。
- **向量嵌入（Embeddings）與向量資料庫（VectorStore）**：
  - 產生嵌入向量：Python 呼叫 `embeddings.embed_query(text)`；JS 呼叫 `await embeddings.embedQuery(text)`（範例產生長度 `1536` 的數值向量）。
  - 建立索引：Python 呼叫 `ids = vector_store.add_documents(documents=all_splits)`；JS 呼叫 `await vectorStore.addDocuments(allSplits)`。
  - **VectorStore 查詢方法對照**：
    | 查詢方式 | Python 方法 | TypeScript/JS 方法 |
    | :--- | :--- | :--- |
    | 同步/基本字串相似度搜尋 | `vector_store.similarity_search(query, k=...)` | `await vectorStore.similaritySearch(query)` |
    | 非同步字串相似度搜尋 | `await vector_store.asimilarity_search(query)` | `await vectorStore.similaritySearch(query)` |
    | 附帶相似度/距離分數搜尋 | `vector_store.similarity_search_with_score(query)` | `await vectorStore.similaritySearchWithScore(query)` |
    | 以嵌入向量直接搜尋 | `vector_store.similarity_search_by_vector(embedding)` | `await vectorStore.similaritySearchVectorWithScore(embedding, 1)` |
    | 最大邊際相關性（MMR）搜尋 | `vector_store.max_marginal_relevance_search(...)` | `await vectorStore.maxMarginalRelevanceSearch(...)` |
- **檢索器（Retrievers）**：
  - `VectorStore` 本身**不是** `Runnable` 的子類別；而 `Retriever` 則是標準 `Runnable`，支援同步與非同步的 `invoke` 與 `batch`。
  - **方式一（`@chain` 包裝）**：在 Python 中使用 `from langchain_core.runnables import chain` 的 `@chain` 裝飾器包裝 `vector_store.similarity_search(query, k=1)`。
  - **方式二（`as_retriever` / `asRetriever`）**：
    - Python：`retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 1})` 回傳 `VectorStoreRetriever`。`search_type` 支援三種模式：`"similarity"`（預設）、`"mmr"`（最大邊際相關性）、`"similarity_score_threshold"`（依相似度分數門檻過濾）。
    - TypeScript/JavaScript：`const retriever = vectorStore.asRetriever({ searchType: "mmr", searchKwargs: { fetchK: 1 } })`。

---

### 二、SQL 資料庫問答代理（SQL Agent）
- **八階段執行流程**：
  1. 取得資料庫中可用的資料表與結構（schemas）。
  2. 決定哪些資料表與問題相關。
  3. 取得相關資料表的詳細 schema 與範例資料列。
  4. 根據問題與 schema 產生 SQL 查詢。
  5. 使用 LLM 再次檢查（double-check）查詢是否有常見錯誤。
  6. 執行查詢並回傳結果。
  7. 若資料庫引擎回報錯誤，根據錯誤訊息修正查詢並重試直到成功。
  8. 根據查詢結果組織最終回答。
- **範例資料庫與工具組**：
  - 使用 SQLite 的 `Chinook.db` 數位媒體商店範例資料庫（`sqlite` 方言，包含 11 張表：`Album`、`Artist`、`Customer`、`Employee`、`Genre`、`Invoice`、`InvoiceLine`、`MediaType`、`Playlist`、`PlaylistTrack`、`Track`）。
  - **Python 四大資料庫工具**：
    - `sql_db_list_tables`：輸入空字串，輸出逗號分隔的所有資料表名稱。
    - `sql_db_schema`：輸入逗號分隔的資料表名稱，輸出其 `CREATE TABLE` schema 與前 3 筆範例資料列（呼叫前須先確認資料表存在）。
    - `sql_db_query_checker`：在執行查詢前，務必先用此工具雙重檢查 SQL 語法是否正確。
    - `sql_db_query`：執行詳細且正確的 SQL 查詢並回傳結果；若出錯會回傳錯誤訊息讓模型改寫重試（若遇到 `Unknown column 'xxxx' in 'field list'` 則應改呼叫 `sql_db_schema`）。
  - **TypeScript/JavaScript 工具與安全檢查**：使用 `sqlite3` 套件，先透過 `_safe_sql` 函式檢查並消毒 LLM 產生的 SQL 指令，再透過 `execute_sql` 工具執行。
- **LangGraph Studio 本地開發與人機迴圈（HITL）審批**：
  - **Studio 設定**：Python 安裝 `pip install -U langgraph-cli[inmem]>=0.4.0`，JS 安裝 `npm i -g @langchain/langgraph-cli@latest`，並設定 `langgraph.json`（定義 `"graphs": { "agent": "./sql_agent.py:agent", "graph": "./sql_agent_langgraph.py:graph" }` / JS 對應 `.ts` 檔案）。
  - **HITL 審批保護**：由於執行模型產生的 SQL 具潛在風險，除了將資料庫連線權限縮到最小外，可掛載 `HumanInTheLoopMiddleware`（JS：`humanInTheLoopMiddleware`）並搭配 `checkpointer`，針對 `sql_db_query`（Python）或 `execute_sql`（JS）工具設定中斷。代理在執行 SQL 前會暫停並印出待審核的 `query` 參數，待人類透過 `Command` 核准後才實際查詢資料庫。

---

### 三、語音代理架構（Voice Agent）
- **語音代理三大核心任務**：**Listen**（擷取音訊並轉錄）、**Think**（理解意圖、推理與規劃）、**Speak**（合成音訊並串流回傳）。
- **兩大主流架構比較**：
  | 架構名稱 | 資料流 | 優點（Pros） | 缺點（Cons） |
  | :--- | :--- | :--- | :--- |
  | **1. STT > Agent > TTS（The "Sandwich" 三明治架構）** | `User Audio -> Speech-to-Text -> LangChain Agent -> Text-to-Speech -> Audio Output` | 完全掌控各元件（可隨時替換 STT/TTS 供應商）、可使用最新文字模態模型能力、元件邊界清晰透明；搭配適當供應商可達 **sub-700ms** 延遲 | 需協調多個服務、管線管理較複雜、語音轉文字過程會流失語氣與情緒資訊 |
  | **2. Speech-to-Speech（S2S 端到端語音架構）** | `User Audio -> Multimodal Model -> Audio Output` | 架構簡單元件少、簡單互動延遲較低、原生處理音訊可保留語氣與細節 | 模型選擇少且易被供應商綁定（lock-in）、功能可能落後文字模型、透明度與可控性較低 |
- **三明治架構（`voice-sandwich-demo`）三階段非同步串流實作**：
  - 客戶端（瀏覽器）擷取麥克風音訊編碼為 PCM，透過雙向 WebSocket 即時串流至後端，並接收播放合成語音。後端利用 Python `AsyncIterator`（非同步產生器）或 JS `AsyncGenerator`（搭配 `writableIterator`）實現全管線邊收邊處理：
  1. **階段一：Speech-to-Text（AssemblyAI，`stt_stream` / `sttStream`）**：
     - 採用 **Producer-Consumer 模式**：Producer 背景任務（`asyncio.create_task(send_audio())`）持續將音訊 chunk 送往 `AssemblyAISTT(sample_rate=16000)`；Consumer 同時從 `stt.receive_events()` 接收轉錄事件。
     - `AssemblyAISTT` 使用環境變數 `ASSEMBLYAI_API_KEY`，連線至 `wss://streaming.assemblyai.com/v3/ws?sample_rate=16000&format_turns=true`（帶 `Authorization` header）。
     - 當收到 `message["type"] == "Turn"` 時：若 `turn_is_formatted` 為假，發出部分轉錄事件 `stt_chunk`（`STTChunkEvent`）；若 `turn_is_formatted` 為真，發出最終格式化轉錄事件 `stt_output`（`STTOutputEvent`）。
  2. **階段二：LangChain Agent（`agent_stream` / `agentStream`）**：
     - 建立具有三明治點餐工具（`add_to_order` / `addToOrder`、`confirm_order` / `confirmOrder`）與 `InMemorySaver` / `MemorySaver` 的代理（Python 範例模型 `"google_genai:gemini-4-hydrogen"`，JS 範例模型 `"claude-haiku-4-5"`）。**系統提示詞特別規定：不可使用表情符號（emojis）、特殊字元或 markdown**，因為回應會直接交由 TTS 引擎朗讀。
     - 使用 `uuid7()`（Python：`from langchain_core.utils.uuid import uuid7`；JS：`import { uuid7 } from "langsmith"`）產生唯一 `thread_id`。
     - 原封不動穿透（yield）所有上游事件；當遇到 `event.type == "stt_output"` 時，呼叫 `await agent.astream_events({"messages": [HumanMessage(content=event.transcript)]}, {"configurable": {"thread_id": thread_id}}, version="v3")`（JS 為 `agent.streamEvents(..., { configurable: { thread_id: threadId }, version: "v3" })`），遍歷 `stream.messages` 與 `message.text` 並即時發出 `agent_chunk`（`AgentChunkEvent`）。
  3. **階段三：Text-to-Speech（Cartesia，`tts_stream` / `ttsStream`）**：
     - 並行合併兩個非同步串流（Python 使用 `merge_async_iters(process_upstream(), tts.receive_events())`）：一邊穿透上游事件並在收到 `event.type == "agent_chunk"` 時呼叫 `await tts.send_text(event.text)`，另一邊同時接收合成音訊 chunk。
     - `CartesiaTTS` 使用環境變數 `CARTESIA_API_KEY`，預設參數：`voice_id="f6ff7c0c-e396-40a9-a70b-f7607edb6937"`、`model_id="sonic-3"`、`sample_rate=24000`、`encoding="pcm_s16le"`，連線至 `wss://api.cartesia.ai/tts/websocket?api_key=...&cartesia_version=...`，每次傳送帶上 `context_id`（格式 `ctx_{timestamp}_{counter}`），並將回傳 JSON 的 `"data"` 欄位進行 Base64 解碼後發出 `tts_chunk`（`TTSChunkEvent`）。
  - **組合完整管線**：
    - Python：使用 `from langchain_core.runnables import RunnableGenerator` 串接 `pipeline = RunnableGenerator(stt_stream) | RunnableGenerator(agent_stream) | RunnableGenerator(tts_stream)`，在 FastAPI `@app.websocket("/ws")` 端點中呼叫 `output_stream = pipeline.atransform(websocket_audio_stream())`，遇到 `event.type == "tts_chunk"` 即呼叫 `await websocket.send_bytes(event.audio)`。
    - TypeScript/JavaScript：在 Hono `upgradeWebSocket` 中串接 `ttsStream(agentStream(sttStream(inputStream)))`。

---

### 四、從零打造資料分析 Deep Agent（Deep Agent from Scratch）
- **核心設計理念**：`create_deep_agent`（JS：`createDeepAgent`）預設內建規劃、檔案系統與子代理等完整裝備（harness）。若需細粒度客製化，可安裝 `pip install deepagents langsmith`（JS：`npm install deepagents langsmith`），從基礎的 `create_agent` / `createAgent` 出發，分 5 個步驟逐一組裝出完全相同的架構：
  | 步驟 | 未加入前的問題 | 加入的元件 |
  | :--- | :--- | :--- |
  | **1. Minimal agent** | — | 基礎迴圈：`create_agent` + 模型，無檔案與程式執行能力 |
  | **2. Sandbox + filesystem** | 無法讀取 CSV 或執行 Python | `LangSmithSandbox` 隔離沙箱後端 + `FilesystemMiddleware` |
  | **3. Summarization** | 多次繪圖、讀檔與腳本除錯會塞爆上下文視窗 | `SummarizationMiddleware` 自動壓縮舊對話歷史 |
  | **4. Skills** | 將所有領域規則寫入 system prompt 會浪費大量 token | `SkillsMiddleware` 透過漸進式揭露（Progressive Disclosure）按需載入專業技能檔 |
  | **5. Subagent** | 圖表反覆修改與除錯會佔據主執行緒上下文 | `TodoListMiddleware` + `SubAgentMiddleware` 平行委派給獨立的 `visualizer` 子代理 |
- **各步驟關鍵技術細節**：
  - **LangSmith 沙箱與檔案系統（Step 2）**：
    - `LangSmithSandbox` 透過 `SandboxClient` 配置雲端隔離沙箱，**必須設定環境變數 `LANGSMITH_API_KEY`**（以及 `LANGSMITH_TRACING=true` 與模型供應商 API key 如 `GOOGLE_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`OPENROUTER_API_KEY`、`FIREWORKS_API_KEY`、`BASETEN_API_KEY`、`OLLAMA_API_KEY`）。若需從自訂映像檔啟動，Python 可在 `create_sandbox()` 傳入 `snapshot_name` 或 `snapshot_id`；JS 可在 `LangSmithSandbox.create()` 傳入 `snapshotId`。
    - `FilesystemMiddleware` 提供 `read_file`、`write_file`、`edit_file`、`delete`（Python）、`glob`、`grep` 工具；且因為 `LangSmithSandbox` 實作了 sandbox protocol，`FilesystemMiddleware` **會自動額外掛載 `execute` 工具**供代理執行 shell 指令（如安裝套件與執行 Python 腳本）。
    - **上傳檔案路徑限制**：沙箱檔案系統與本機隔離，呼叫代理前必須先上傳檔案（如 `sales.csv`）。在 `LangSmithSandbox` 中，**上傳路徑必須是絕對 POSIX 路徑（例如 `/sales.csv`）**；若使用相對路徑（如 `sales.csv`）會以 `invalid_path` 被拒絕且不會寫入沙箱。
  - **技能漸進式揭露（Step 4，`SkillsMiddleware`）**：
    - 建立技能檔案（如 `skills/pandas-patterns/SKILL.md`），以 YAML frontmatter 定義 `name: pandas-patterns` 與 `description: ...`，內文撰寫資料載入（`pd.read_csv()`、`df.info()`、`df.describe()`）、視覺化（`matplotlib`、`seaborn`、`plt.savefig("output.png", dpi=150, bbox_inches="tight")`）與報告（`report.md`）規範。
    - 代理啟動時僅在上下文看到輕量的技能 metadata，只有當任務需要時才會按需讀取完整 `SKILL.md`。注意：搭配 `LangSmithSandbox` 時，技能路徑是解析在**沙箱檔案系統**上，因此必須先將本機 `skills/` 目錄上傳至沙箱，再設定 `SkillsMiddleware`。
  - **平行視覺化子代理（Step 5，`TodoListMiddleware` + `SubAgentMiddleware`）**：
    - 加入 `TodoListMiddleware` 與 `SubAgentMiddleware`，定義名為 `visualizer` 的子代理。主代理負責分析與規劃，並透過 `task` 工具將繪圖工作平行委派給在獨立上下文視窗中運行的 `visualizer` 子代理，主代理僅接收最終簡短結果。

## 相關頁面
- [[entities/langchain-builtin-middleware]]
- [[concepts/langchain-middleware]]
- [[concepts/langchain-human-in-the-loop-and-guardrails]]
- [[concepts/langchain-memory-and-context-engineering]]

## 出處
- docs/langchain/retrieval.md
- docs/langchain/knowledge-base.md
- docs/langchain/sql-agent.md
- docs/langchain/voice-agent.md
- docs/langchain/deep-agent-from-scratch.md
