# LangGraph Custom Agentic RAG and SQL Agent

別名：自訂檢索增強生成代理人、代理式 RAG、混合式 RAG、自訂 SQL 代理人、Agentic RAG、Hybrid RAG、Custom RAG Agent、Custom SQL Agent
框架：langgraph

## 摘要
當內建的高階代理人抽象（如 `create_agent`）無法滿足細粒度控制需求時，可直接使用 LangGraph 的 `StateGraph` 建構自訂代理人工作流。在 **Agentic RAG（代理式檢索增強生成）** 中，代理人透過 `generate_query_or_respond` 決定要直接回覆使用者或呼叫檢索工具 `retrieve_blog_posts`，並以條件邊 `grade_documents` 評估檢索文件相關性，自動在生成答案（`generate_answer`）與重寫問題重試（`rewrite_question`）之間路由；在 **Custom SQL Agent（自訂 SQL 資料庫代理人）** 中，則透過專屬節點強制執行「列出資料表 → 取得結構描述（Schema）→ 生成查詢 → 檢查查詢 → 執行查詢」的流程，並可結合 `interrupt` 與 `Command` 實作執行 SQL 前的人類審核（Human-in-the-loop）。

## 重點

### 1. 自訂 Agentic RAG（檢索增強生成代理人）
- **核心設計理念**：不同於固定「先檢索後生成（retrieve-then-generate）」的傳統管線，Agentic RAG 由模型在第一個節點自行決定是否需要檢索（僅在問題需要外部知識時才呼叫檢索工具），並在檢索結果不相關時自動改寫查詢重新檢索，避免憑空捏造（hallucinate）答案。
- **安裝套件與可觀測性設定**：
  - Python：`pip install -U langgraph langchain langchain-openai langchain-text-splitters beautifulsoup4 requests`
  - TypeScript / JavaScript：`npm install @langchain/langgraph @langchain/openai @langchain/textsplitters cheerio`（亦支援 `pnpm`、`yarn`、`bun`）。
  - LangSmith 追蹤環境變數：`export LANGSMITH_TRACING="true"` 與 `export LANGSMITH_API_KEY="..."`（正式環境可搭配 LangSmith Engine 監控 traces、偵測問題並提出修復建議）。
- **文件前處理與檢索工具建立**：
  1. **擷取與切分文件（Fetch & Split）**：以 Lilian Weng 部落格（`https://lilianweng.github.io/`）的三篇文章為例，在 Python 使用 `requests` 與 `BeautifulSoup`、在 JS 使用 `fetch` 與 `cheerio` 抓取網頁內容，再將文件切分為較小的 chunks。
  2. **建立向量庫與檢索工具（Retriever Tool）**：使用記憶體內向量庫（in-memory vector store）與 OpenAI embeddings 建立索引，並將檢索器封裝為名為 `retrieve_blog_posts` 的工具（Python 使用 `@tool` 裝飾器定義；JS 使用 LangChain 內建的 `createRetrieverTool`）。
- **圖狀態與節點架構（Python vs JS/TS 名稱對照）**：
  - **共享狀態（State）**：Python 使用 `MessagesState`；JS/TS 使用 `MessagesAnnotation`，皆在狀態中維護 `messages` 聊天訊息列表（`HumanMessage`、`AIMessage`、`ToolMessage`）。
  - **決策與查詢生成節點（Python：`generate_query_or_respond` / JS：`generateQueryOrRespond`）**：
    - 將 `retriever_tool` 透過 `.bind_tools`（Python）或 `.bindTools`（JS）綁定至聊天模型，並傳入目前的 `messages`。
    - 若使用者輸入簡單問候（如 `"hello!"`），模型回傳不含工具呼叫（`tool_calls: []`）的 `AIMessage`（`"Hello! How can I help you today?"`），流程直接結束並回覆使用者。
    - 若使用者詢問需語意搜尋的問題（如 `"What does Lilian Weng say about types of reward hacking?"`），模型回傳帶有 `tool_calls`（呼叫 `retrieve_blog_posts`，參數如 `args: {"query": "types of reward hacking"}`）的 `AIMessage`，交由檢索工具節點執行並產出 `ToolMessage`。
  - **文件相關性評分條件邊函式（Python：`grade_documents` / JS：`gradeDocuments`）**：
    - 作為**條件邊（conditional edge）路由函式**而非一般節點，在檢索工具完成後根據當前狀態判斷檢索到的文件是否與問題相關。
    - Python（`grade_documents`）：使用綁定結構化輸出 Schema `GradeDocuments` 的模型進行評分，根據結果回傳下一個節點名稱 `"generate_answer"`（相關）或 `"rewrite_question"`（不相關）。
    - JS/TS（`gradeDocuments`）：使用綁定 Zod 結構化輸出的模型（若結構化剖析失敗則退回純文字 yes/no 判斷），根據結果回傳下一個節點名稱 `"generate"`（相關）或 `"rewrite"`（不相關）。
  - **問題改寫節點（Python：`rewrite_question` / JS：`rewrite`）**：
    - 當 `grade_documents` / `gradeDocuments` 判定檢索結果不相關（例如測試時傳入 `ToolMessage(content="meow")`）時觸發。
    - 要求模型改寫原始使用者問題以形成更清晰的搜尋查詢（例如改寫為 `"What are the different types of reward hacking described by Lilian Weng, and how does she explain them?"`），接著將控制權路由回 `generate_query_or_respond` / `generateQueryOrRespond` 重新發起檢索迴圈。
  - **答案生成節點（Python：`generate_answer` / JS：`generate`）**：
    - 當評分器接受檢索文件時觸發。結合原始使用者問題與帶有檢索上下文的 `ToolMessage`，要求模型嚴格根據提供的內容生成最終回覆。
- **完整 Agentic RAG 圖拓撲流程**：
  - `START` → `generate_query_or_respond`（JS：`generateQueryOrRespond`）。
  - 條件邊 1（檢查是否有 `tool_calls`）：若無 `tool_calls` → `END`（直接回覆）；若有 `tool_calls` → 執行 `retriever_tool` 檢索工具節點。
  - 條件邊 2（執行 `grade_documents` / `gradeDocuments`）：若文件相關 → `generate_answer`（JS：`generate`）→ `END`；若文件不相關 → `rewrite_question`（JS：`rewrite`）→ 回到 `generate_query_or_respond`（JS：`generateQueryOrRespond`）。

### 2. 自訂 SQL Agent（SQL 資料庫問答代理人）
- **安全性警告與為何使用自訂 LangGraph 圖**：
  - **風險控制**：建構 SQL 問答系統需要執行模型生成的 SQL 查詢，存在固有風險；資料庫連線權限必須盡可能限縮至代理人所需的最小範圍，並在執行前加入應用層驗證。
  - **超越系統提示詞的強制控制**：高階預建 SQL 代理人僅依賴系統提示詞（system prompt）約束行為（例如提示它「務必先呼叫列出資料表工具」、「執行前務必呼叫查詢檢查工具」）；改用 LangGraph `StateGraph` 將各步驟拆為專屬節點，可：(1) 在特定階段強制要求模型執行指定的工具呼叫（force tool-calls），以及 (2) 為每個步驟量身打造專屬提示詞。
- **安裝套件與範例資料庫配置**：
  - Python：`pip install langchain langgraph`（搭配 Python 內建 `sqlite3` 模組）。
  - TypeScript / JavaScript：`npm i langchain @langchain/core @langchain/langgraph @langchain/openai sqlite3 zod`。
  - **Chinook 範例資料庫（`Chinook.db`）**：託管於公開 GCS 儲存桶的 SQLite 數位媒體商店範例資料庫（Dialect 為 `sqlite`），包含 11 張資料表：`Album`、`Artist`、`Customer`、`Employee`、`Genre`、`Invoice`、`InvoiceLine`、`MediaType`、`Playlist`、`PlaylistTrack`、`Track`。
- **3 個核心 SQL 資料庫工具（使用 `@tool` 封裝）**：
  1. `sql_db_list_tables`：輸入為空字串，輸出為資料庫中所有資料表的逗號分隔清單。
  2. `sql_db_schema`：輸入為逗號分隔的資料表名稱清單（例如 `"Genre, Track"`），輸出為這些資料表的 `CREATE TABLE` DDL 結構描述與前 3 筆範例資料列（呼叫前須先透過 `sql_db_list_tables` 確認資料表存在）。
  3. `sql_db_query`：輸入為完整且正確的 SQL 查詢，輸出為資料庫執行結果；若查詢有誤則回傳錯誤訊息（若遇到 `Unknown column 'xxxx' in 'field list'`，應使用 `sql_db_schema` 查詢正確欄位後重寫並檢查查詢）。
- **專屬節點步驟與工作流組裝**：
  1. **列出資料表（Listing DB tables）**：啟動時自動產生或執行 `sql_db_list_tables` 工具呼叫，取得可用資料表清單。
  2. **呼叫取得結構描述工具（Calling the "get schema" tool）**：強制模型根據使用者問題呼叫 `sql_db_schema` 工具以調閱相關資料表結構。
  3. **生成查詢（Generating a query）**：模型根據已取得的 Schema 生成帶有 `sql_db_query` 工具呼叫的 SQL 語句，若已有查詢結果則直接生成給使用者的最終自然語言回答。
  4. **檢查查詢（Checking the query）**：在實際對資料庫執行查詢前，透過專屬提示詞由模型檢查生成的 SQL 查詢是否有常見錯誤並輸出修正後的 `sql_db_query` 呼叫。
  5. **執行查詢與迴圈路由**：條件邊設於查詢生成步驟後——若模型產出了工具呼叫（`tool_calls`），則路由至查詢檢查與執行節點，執行完畢後再將 `ToolMessage` 結果送回生成查詢節點；若無 `tool_calls`，代表模型已完成最終回答，路由至 `END`。
- **人類介入審核（Human-in-the-loop Review）**：
  - 可以人類審核取代程式化檢查：使用 LangGraph 的 `interrupt` 函式包裝 `sql_db_query` 工具節點，並在編譯圖時傳入 checkpointer（持久化層，暂停與恢復執行之必要條件）。
  - 當代理人準備執行 SQL 時，圖會暫停並發出中斷負載：
    - `{"action": "sql_db_query", "args": {"query": "SELECT ..."}, "description": "Please review the tool call"}`
  - 使用者可透過傳入 `Command(resume=...)` 來核准（accept）該工具呼叫、直接修改其查詢參數（edit arguments），或提供回饋文字讓模型重新調整查詢。

## 相關頁面
- [[concepts/langgraph-streaming]]
- [[guides/langgraph-deployment-and-studio]]
- [[versions/langgraph-backward-compatibility-and-changelogs]]

## 出處
- docs/langgraph/agentic-rag.md
- docs/langgraph/sql-agent.md
