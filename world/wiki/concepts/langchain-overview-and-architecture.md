# LangChain Overview, Philosophy, and Component Architecture

別名：LangChain 概覽與架構、LangChain 設計哲學、LangChain 安裝與快速入門、Agent = Model + Harness、`create_agent`、`createAgent`、`langchain-classic`、`@langchain/classic`
框架：langchain

## 摘要
LangChain 以「**Agent = Model + Harness**」為核心概念，提供精簡且高度可配置的代理框架（Harness）`create_agent`（Python）與 `createAgent`（JavaScript/TypeScript），讓開發者透過模型、提示詞（prompt）、工具（tools）與中介軟體（middleware）組合出符合需求的 AI 代理。LangChain 建構於低階編排框架 LangGraph 之上，具備持久化執行（durable execution）、短期與長期記憶、人機協作（human-in-the-loop）與串流等能力，並能與 LangSmith 及開源電池內建框架 Deep Agents（`deepagents`）無縫整合。

## 重點

### 核心定位與架構層級（LangChain vs. LangGraph vs. Deep Agents vs. LangSmith）
- **核心公式**：`Agent = Model + Harness`。Harness 指模型迴圈（model loop）外圍的一切配置，包含 prompt、tools 以及控制行為的 middleware。
- **LangChain（`create_agent` / `createAgent`）**：提供最小化、高度可客製化的代理 harness，適合需要精細控制架構、針對特定應用場景與資料量身打造的開發者。
- **Deep Agents（`deepagents` 套件，函式 `create_deep_agent` / `createDeepAgent`）**：建構於 LangChain agents 與 LangGraph 之上的開源「內建電池（batteries-included）」代理 harness，預先整合任務規劃工具（如內建 `write_todos`）、具備可插拔後端的虛擬檔案系統（in-memory、disk、LangGraph store、sandboxes，含 `grep`、`read_file` 等檔案工具，大檔案輸出會自動存至如 `/large_tool_results/...`）、子代理生成（subagent spawning，用於隔離上下文）與上下文壓縮（context compression）。若不想自行管理基礎設施，可使用託管版 **Managed Deep Agents**；若需自託管，可使用 **Deep Agents SDK** 或自架 **Agent Server**。
- **LangGraph**：低階編排框架（low-level orchestration framework），適合結合確定性（deterministic）與代理式（agentic）工作流的進階需求。
- **LangSmith**：可觀測性（observability）與評估（evals）平台，用於追蹤（trace）、除錯與評估由上述任何框架建構的代理。設定環境變數 `LANGSMITH_TRACING=true` 與 API key 即可啟用；另推薦搭配 **LangSmith Engine** 自動監控 traces、偵測問題並提出修復建議。

### 設計哲學與演進歷史（Philosophy & History）
- **兩大核心焦點**：
  1. **讓開發者能使用最先進的模型（Build with the best models）**：標準化不同供應商的 API、模型參數與訊息格式，避免供應商鎖定（vendor lock-in）。
  2. **讓模型能輕鬆編排與外部資料及運算互動的複雜流程（Orchestrate complex flows）**：提供工具（tools）定義與非結構化資料解析存取。
- **版本演進時間軸**：
  - **2022-10-24（`v0.0.1`）**：於 ChatGPT 發布前一個月以 Python 套件推出，包含兩大元件：LLM 抽象層與「Chains」（預定計算步驟，如 RAG 檢索後生成）。名稱源自 "Language" 與 "Chains"。
  - **2022-12**：加入首批基於 ReAct 論文（Reasoning and Acting）的通用型代理，透過 LLM 產生代表工具呼叫的 JSON 並解析執行。
  - **2023-01**：OpenAI 推出 `Chat Completion` API（輸入與輸出從字串演進為訊息列表 `list of messages`），LangChain 隨之更新；同年 1 月發布 JavaScript 版本。
  - **2023-02**：成立 **LangChain Inc.**，目標為「make intelligent agents ubiquitous」。
  - **2023-03**：OpenAI 推出 `function calling` API，LangChain 將其設為工具呼叫的首選方式（取代純 JSON 解析）。
  - **2023-06**：發布閉源平台 **LangSmith**，提供可觀測性與評估。
  - **2024-01（`v0.1.0`）**：發布首個非 `0.0.x` 版本，強化生產環境穩定性。
  - **2024-02**：開源發布 **LangGraph**，補齊低階編排層，加入串流（streaming）、持久化執行（durable execution）、短期記憶（short-term memory）、人機協作（human-in-the-loop）等功能。
  - **2024-06**：超過 700 個整合項目；整合套件從核心套件拆分至獨立供應商套件或社群套件（Python 為 `langchain-community`，JS 為 `@langchain/community`）。
  - **2024-10**：LangGraph 成為建構超過單次 LLM 呼叫之 AI 應用的首選方式；舊版多數 chains 與 agents 標記為棄用（deprecated）。
  - **2025-04**：模型 API 邁向多模態（multimodal），更新 `langchain-core`（Python）與 `@langchain/core`（JS）訊息格式以標準化檔案、圖片、影片等輸入。
  - **2025-10-20（`v1.0.0`）**：LangChain 1.0 發布兩大變革：
    1. 全面重構 `langchain` 中的所有 chains 與 agents，統一替換為建構於 LangGraph 之上的單一高階代理抽象（即原本在 LangGraph 中建立的 ReAct 介面代理）。若仍需使用舊版 chains/agents 且不升級，可安裝 `langchain-classic`（Python）或 `@langchain/classic`（JS）。
    2. 標準化訊息內容格式（Standard message content format）：將推理區塊（reasoning blocks）、引用（citations）、伺服器端工具呼叫（server-side tool calls）等跨供應商標準化。
  - **2026-03-15（`v0.5.3`）**：開源發布建構於 LangGraph 之上的 **Deep Agents**。

### 元件生態系與架構（Component Architecture）
- **五層連接流程**：
  1. **Input processing（輸入處理）**：`Text input` → `Document loaders` → `Text splitters` → `Documents`。
  2. **Embedding & storage（嵌入與儲存）**：`Documents` → `Embedding models` → `Vectors` → `Vector stores`。
  3. **Retrieval（檢索）**：`User Query` → `Embedding models` → `Query vector` → `Retrievers` ↔ `Vector stores` → `Relevant context`。
  4. **Generation（生成）**：`Relevant context` 傳入 `Chat models`，`Chat models` ↔ `Tools`（產生 `Tool results` 回傳給模型）→ 輸出 `AI response`。
  5. **Orchestration（編排）**：`Agents` 負責協調 `Chat models`、`Tools`、`Retrievers` 與 `Memory`。
- **七大元件分類表**：
  - **Models**：AI 推理與生成（Chat models、LLMs、Embedding models），用於文字生成、推理、語意理解。
  - **Tools**：外部能力（APIs、databases 等），用於網頁搜尋、資料存取、計算。
  - **Agents**：編排與推理（ReAct agents、tool calling agents），用於非確定性工作流、決策。
  - **Memory**：上下文保存（Message history、custom state），用於多輪對話、具狀態互動。
  - **Retrievers**：資訊存取（Vector retrievers、web retrievers），用於 RAG、知識庫搜尋。
  - **Document processing**：資料擷取（Loaders、splitters、transformers），用於 PDF 處理、網頁爬蟲。
  - **Vector Stores**：語意搜尋（Chroma、Pinecone、FAISS），用於相似度搜尋、嵌入向量儲存。
- **三大常見設計模式**：
  - **RAG（Retrieval-Augmented generation）**：`User question` → `Retriever` → `Relevant docs` + `User question` → `Chat model` → `Informed response`。
  - **Agent with tools**：`User request` → `Agent` → 判斷 `Need tool?`（若 Yes：`Call tool` → `Tool result` → 回到 `Agent`；若 No：輸出 `Final answer`）。
  - **Multi-agent system**：`Complex Task` → `Supervisor agent` 分派給 `Specialist agent 1` 與 `Specialist agent 2` → 彙整 `Results` 回到 `Supervisor agent` → 輸出 `Coordinated response`。

### 安裝與環境需求（Installation）
- **Python 安裝與版本要求**：
  - 最低需求：**Python 3.10+**（Quickstart 範例推薦釘選 Python 3.11+：`uv python pin 3.11`）。
  - 核心套件安裝：`pip install -U langchain` 或 `uv add langchain`。
  - 獨立供應商整合套件範例：
    - OpenAI：`pip install -U langchain-openai`、`uv add langchain-openai` 或 `pip install -qU langchain "langchain[openai]"`
    - Anthropic：`pip install -U langchain-anthropic`、`uv add langchain-anthropic` 或 `pip install -qU langchain "langchain[anthropic]"`
    - Google Gemini：`pip install -qU langchain "langchain[google-genai]"`
    - OpenRouter：`pip install -qU langchain langchain-openrouter`
    - Fireworks：`pip install -qU langchain langchain-fireworks`
    - Baseten：`pip install -qU langchain langchain-baseten`
    - Ollama：`pip install -qU langchain langchain-ollama`
    - AWS Bedrock：`pip install -qU langchain langchain-aws`
    - HuggingFace：`pip install -qU langchain "langchain[huggingface]"`
- **JavaScript / TypeScript 安裝與版本要求**：
  - 執行環境需求：**Node.js 22+** 或 **Bun v1.0.0+**。
  - 核心套件安裝：`npm install langchain @langchain/core`（或搭配 `pnpm add`、`yarn add`、`bun add`；使用工具 schema 時常搭配安裝 `zod`）。
  - 獨立供應商整合套件範例：`@langchain/openai`、`@langchain/anthropic`、`@langchain/google`、`@langchain/openrouter`、`@langchain/ollama`、`@langchain/aws`。

### 快速入門與供應商設定（Quickstart）
- **各供應商環境變數（API Keys）**：
  - OpenAI：`OPENAI_API_KEY`
  - Google Gemini：`GOOGLE_API_KEY`
  - Claude (Anthropic)：`ANTHROPIC_API_KEY`
  - OpenRouter：`OPENROUTER_API_KEY`
  - Fireworks：`FIREWORKS_API_KEY`
  - Baseten：`BASETEN_API_KEY`
  - Ollama：`OLLAMA_API_KEY`（雲端託管推論使用；本地端則需啟動 Ollama 服務）
  - Azure OpenAI：`AZURE_OPENAI_API_KEY`、`AZURE_OPENAI_ENDPOINT`、`AZURE_OPENAI_DEPLOYMENT_NAME`
  - AWS Bedrock：`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`、`AWS_REGION`（例如 `"us-east-1"`）
  - HuggingFace：`HUGGINGFACEHUB_API_TOKEN`（例如 `"hf_..."`）
  - `.env` 載入方式：Python 使用 `python-dotenv`（`load_dotenv()`）；JS/TS 使用 `dotenv`（`import "dotenv/config"`）。若使用 LangSmith LLM Gateway，則將 gateway key 作為 API key。
- **跨供應商基本代理建立（Model Strings 對照）**：
  - Python 從 `langchain.agents` 匯入 `create_agent(model=..., tools=..., system_prompt=...)`，呼叫 `agent.invoke({"messages": [{"role": "user", "content": "..."}]})`，透過 `result["messages"][-1].content_blocks` 讀取最終訊息區塊。
  - JS/TS 從 `"langchain"` 匯入 `createAgent` 與 `tool`（或從 `"@langchain/core/tools"` 匯入 `tool`），呼叫 `createAgent({ model: ..., tools: [...], systemPrompt: ... })`，透過 `agentResult.messages[agentResult.messages.length - 1]!.contentBlocks` 讀取。
  - 文件範例中的模型識別字串（Python vs JS/TS）：
    - OpenAI：Python `"openai:gpt-6.1-sol"` / JS `"gpt-6.1-sol"`
    - Google Gemini：Python `"google_genai:gemini-2.5-flash-lite"`（或 `init_chat_model("gemini-3.1-pro-preview", model_provider="google-genai")`） / JS `"google:gemini-2.5-flash-lite"`（或 `initChatModel("gemini-3.1-pro-preview", { modelProvider: "google" })`）
    - Anthropic：`"claude-sonnet-4-6"`
    - OpenRouter：`"openrouter:anthropic/claude-sonnet-4-6"`
    - Fireworks：`"fireworks:accounts/fireworks/models/qwen3p5-397b-a17b"`
    - Baseten：`"baseten:zai-org/GLM-5.2"`
    - Ollama：`"ollama:devstral-2"`
    - Azure OpenAI：`"azure_openai:gpt-6.1-sol"`（Python `init_chat_model` 需傳入 `azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]`）
    - AWS Bedrock：Python `"bedrock_converse:us.anthropic.claude-sonnet-4-6"`（US 跨區推論設定檔，全球路由可用 `global.anthropic.claude-sonnet-4-6`） / JS `"bedrock:gpt-6.1-sol"`
    - HuggingFace：Python `"huggingface:microsoft/Phi-3-mini-4k-instruct"`
- **進階 Quickstart 實戰要點**：
  - **工具定義**：Python 使用 `@tool` 裝飾器；JS/TS 使用 `tool(fn, { name, description, schema })`，其中 `schema` 可為 Zod schema（具執行期驗證）或原始 JSON Schema 物件（注意：JSON Schema 在執行期**不會**進行驗證）。
  - **短期記憶（Memory / Checkpointer）**：Python 使用 `from langgraph.checkpoint.memory import InMemorySaver`；JS/TS 使用 `import { MemorySaver } from "@langchain/langgraph"`，傳入 `checkpointer` 參數並在 `invoke` 時指定 `config={"configurable": {"thread_id": "..."}}`（Python）或 `{ configurable: { thread_id: "..." } }`（JS）。
  - **LangSmith Agent Tracing 環境變數**：`LANGSMITH_AGENT_ID`、`LANGSMITH_AGENT_ENVIRONMENT`（如 `"local"`）、`LANGSMITH_TRACING="true"`、`LANGSMITH_API_KEY`。

### 學習資源與支援管道（Get Help）
- **學習資源**：**Chat LangChain**（`https://chat.langchain.com/`，即時文件問答）、**API Reference**（`https://reference.langchain.com/python/`）。
- **社群與專業支援**：**Community Forum**（`https://forum.langchain.com/`）、**Community Slack**（`https://www.langchain.com/join-community`）、企業專用 **Support portal**（`https://support.langchain.com/`）、即時狀態頁 **LangSmith status**（`https://global.status.smith.langchain.com/gcp-us`）。
- **貢獻與社群連結**：Contributing Guide（`/oss/contributing/overview`）、X/Twitter（`https://x.com/langchain`）、LinkedIn（`https://www.linkedin.com/company/langchain/`）。
- **AI 編碼助手輔助**：可安裝 **LangChain Docs MCP servers** 與 **LangChain Skills**（`https://github.com/langchain-ai/langchain-skills`）。

## 相關頁面
- [[concepts/langchain-agents-and-runtime]]
- [[entities/langchain-models]]
- [[entities/langchain-messages]]
- [[entities/langchain-tools]]
- [[concepts/langchain-structured-output]]
- [[concepts/langchain-streaming]]
- [[entities/langchain-error-codes]]

## 出處
- docs/langchain/overview.md
- docs/langchain/philosophy.md
- docs/langchain/component-architecture.md
- docs/langchain/install.md
- docs/langchain/quickstart.md
- docs/langchain/get-help.md
