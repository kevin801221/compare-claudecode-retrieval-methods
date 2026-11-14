# Deep Agents Overview, Quickstart, Models & Tools

別名：Deep Agents 總覽、Deep Agents 架構、Agent Harness、Managed Deep Agents、Deep Agents SDK、`create_deep_agent`、`createDeepAgent`
框架：deepagents

## 摘要
Deep Agents 是建構於 LangChain 與 LangGraph 之上的代理測試與執行框架（agent harness），專為複雜、多步驟的任務設計，提供任務規劃、虛擬檔案系統、子代理（subagent）委派與長期記憶。使用者可選擇使用全代管的 Managed Deep Agents（於 LangSmith 上運行），或使用開源的 Deep Agents SDK（`deepagents` 套件）自行託管並連接任意支援工具呼叫（tool calling）的 LangChain 聊天模型與 MCP 伺服器。

## 重點
### 執行模式與核心能力
- **兩種執行方式**：
  - **Managed Deep Agents**：於 LangSmith 上運行的代管部署基礎設施，由 LangSmith 負責管理 harness、Agent Server、sandboxes 與排程（schedules）。
  - **Deep Agents SDK**：開源獨立函式庫（Python PyPI `deepagents` / JavaScript npm `deepagents`），建構於 LangChain 核心組件（Python `create_agent` / JS `createAgent`）與 LangGraph 執行階段之上，支援自訂 `backend`、`store`、`checkpointer` 或自建 Agent Server。
- **四大核心能力類別（Core capabilities）**：
  1. **Execution environment（執行環境）**：包含四層——Tools（自訂函式、API、資料庫、MCP）、Virtual filesystem（可插拔後端支援的檔案工具）、Filesystem permissions（宣告式路徑讀寫權限控制）、Code execution（透過 sandbox backend 的 `execute` 工具執行 shell 指令，或透過 QuickJS runtime interpreter 的 `eval` 工具執行 JavaScript）。
  2. **Context management（上下文管理）**：包含四層——Skills（遵循 Agent Skills 標準的 `SKILL.md` 漸進式載入）、Memory（啟動時由 `memory` 參數載入的 `AGENTS.md` 持久記憶）、Summarization and context offloading（自動壓縮對話歷史與大型工具結果，分為 Input context、Compression、Isolation、Long-term memory 四部分）、Prompt caching（針對 Anthropic 模型或 Amazon Bedrock 的 Claude / Nova 模型自動對靜態系統提示、記憶與技能內容啟用快取）。
  3. **Delegation（委派）**：包含兩層——Task planning（自 v0.7 起改為 opt-in，需將 `TodoListMiddleware` 傳入 `middleware` 參數以啟用 `write_todos` 工具，追蹤 `'pending'`、`'in_progress'`、`'completed'` 狀態）、Subagents（內建 `task` 工具建立隔離 `mode: "isolated"` 或繼承歷史 `mode: "fork"` 的同步子代理，以及支援平行執行與中途中斷操控的 async subagents）。
  4. **Steering（引導與控制）**：透過 `interrupt_on`（Python）/ `interruptOn`（JS）整合 LangGraph interrupts，在敏感工具呼叫前暫停等待人類審批（例如 `interrupt_on={"edit_file": True}`）。

### 內建 Harness 工具與虛擬檔案系統
- **內建工具清單（Built-in harness tools）**：
  - `ls`：列出目錄中的檔案及元資料（大小、修改時間）。
  - `read_file`：讀取檔案內容（含行號，支援大檔案 `offset`/`limit` 分頁，並支援對非文字檔案回傳多模態內容區塊）。
  - `write_file`：建立新檔案（Python 說明為建立新檔案或覆寫既有檔案；JS 說明為建立新檔案）。
  - `edit_file`：在檔案中執行精確字串替換（支援全域替換模式 global replace mode）。
  - `delete`（僅 Python 列出，需要 `deepagents>=0.7`）：刪除檔案，或遞迴刪除目錄及其內容；若後端不支援刪除，該工具會自動對模型隱藏。
  - `glob`：依模式尋找檔案（例如 `**/*.py`）。
  - `grep`：搜尋檔案內容，支援多種輸出模式（僅檔案、含前後文的內容、或計數）。
  - `execute`：在環境中執行 shell 指令（僅在使用實作 `SandboxBackendProtocolV2` 的 sandbox backends 時可用）。
  - `task`：產生子代理（subagent）以處理委派任務。
  - `write_todos`（Opt-in）：將 `TodoListMiddleware` 傳入 `middleware` 時啟用的結構化任務規劃工具。
- **支援的多模態檔案副檔名（`read_file` 與自訂工具回傳）**：
  - **Image**：`.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.heic`、`.heif`
  - **Video**：`.mp4`、`.mpeg`、`.mov`、`.avi`、`.flv`、`.mpg`、`.webm`、`.wmv`、`.3gpp`
  - **Audio**：`.wav`、`.mp3`、`.aiff`、`.aac`、`.ogg`、`.flac`
  - **File**：`.pdf`、`.ppt`、`.pptx`
- **隱藏或限制預設檔案系統工具**：
  - 若要完全隱藏檔案系統工具，需透過 `register_harness_profile` 註冊設定了 `excluded_tools=frozenset({"ls", "read_file", "write_file", "edit_file", "delete", "glob", "grep"})` 的 `HarnessProfile`。**禁止**透過 `excluded_middleware` 移除 `FilesystemMiddleware` 本身（會被拒絕，因其為 Deep Agents stack 的必要基礎架構）。
  - 若要限制僅開放部分檔案系統工具（需 `deepagents>=0.7`），可在 `middleware=[FilesystemMiddleware(backend=backend, tools=["read_file", "ls", "glob", "grep"])]` 中傳入 `tools` allowlist。**`read_file` 必須始終包含在 `tools` 列表中**，若省略會在建立代理時引發 `ValueError`。自訂的 `FilesystemMiddleware` 實例會取代主代理的預設實例，且 `general-purpose` 子代理會繼承相同限制；宣告式子代理（declarative subagents）則不會繼承，需在該子代理自身的 `middleware` 欄位中單獨傳入 `FilesystemMiddleware(tools=...)`。

### 快速開始（Quickstart）與環境設定
- **套件安裝**：
  - Python：`pip install deepagents` 或 `uv add deepagents`（若使用 Tavily 搜尋則額外安裝 `tavily-python`）。
  - TypeScript/JavaScript：`npm install deepagents langchain @langchain/core`（若使用 Tavily 則安裝 `@langchain/tavily`）。
- **API 金鑰與環境變數**：
  - 供應商金鑰：`GOOGLE_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`OPENROUTER_API_KEY`、`FIREWORKS_API_KEY`、`BASETEN_API_KEY`、`OLLAMA_API_KEY` 或 `<PROVIDER>_API_KEY`。
  - 搜尋工具：Google、OpenAI 與 Anthropic 皆提供伺服器端執行的內建網頁搜尋工具（provider search tool dict），無須額外套件或 API key；其他供應商則設定 `TAVILY_API_KEY` 並使用 Tavily。
  - LangSmith 追蹤環境變數：`LANGSMITH_AGENT_ID="<your-agent-id>"`、`LANGSMITH_AGENT_ENVIRONMENT="local"`、`LANGSMITH_TRACING=true`、`LANGSMITH_API_KEY="your-langsmith-api-key"`。

### 模型設定（Models）
- **模型字串格式**：使用 `provider:model` 格式傳遞給 `create_deep_agent`（Python）或 `createDeepAgent`（JS），底層透過 `init_chat_model`（Python）/ `initChatModel`（JS）解析。
  - Python 範例：`google_genai:gemini-4-hydrogen`、`openai:gpt-5.4`、`anthropic:claude-sonnet-4-6`、`openai:gpt-6.1-sol`、`baseten:zai-org/GLM-5.2`。
  - JS 範例：`google:gemini-4-hydrogen`、`openai:gpt-5.4`、`anthropic:claude-sonnet-4-6`。
- **通過 Deep Agents eval suite 的推薦模型（Suggested models）**：
  - **Google**：`gemini-3.1-pro-preview`、`gemini-4-hydrogen`
  - **OpenAI**：`gpt-5.5`、`gpt-5.4`
  - **Anthropic**：`claude-opus-4-8`、`claude-opus-4-7`、`claude-opus-4-6`
  - **Open-weight**（可透過 Baseten、Fireworks、OpenRouter、Ollama 使用）：`GLM-5.2`、`Kimi-K2.7 Code`、`MiniMax-M3`
- **ProviderProfile**：封裝模型初始化參數，僅在傳入 `provider:model` 字串時生效（傳入已透過 `init_chat_model` 初始化的實例時不生效）。支援兩個層級並可共存：
  - **Provider level**：如 `"openai"`，套用至該供應商所有模型。
  - **Model level**：如 `"openai:gpt-5.4"`，僅套用至該特定模型，並覆疊（merge）於對應的 provider-level profile 之上。
- **OpenAI 與 Responses API 預設行為**：
  - 當傳入 `openai:...` 模型字串時，Deep Agents 會使用內建的 OpenAI provider profile **預設啟用 Responses API**。
  - 若要改用 Chat Completions，需在 Python 傳入 `init_chat_model("openai:gpt-6.1-sol", use_responses_api=False)`（或透過 provider profile 的 `init_kwargs` 設定；JS 則設定 `useResponsesApi`）。
  - 若要保留 Responses API 但停用資料保留（`store=False`）並同時接收加密推理輸出，可設定 `init_chat_model("openai:gpt-6.1-sol", use_responses_api=True, store=False, include=["reasoning.encrypted_content"])`。
- **執行階段動態切換模型（Select a model at runtime）**：透過 runtime context 傳入使用者的模型選擇，並使用 `@wrap_model_call` 裝飾器定義 `wrap_model_call` middleware，在每次呼叫時動態覆寫模型而無需重建代理。

### 自訂工具與 MCP 整合（Tools & MCP）
- **自訂工具**：可將一般函式（plain functions）、LangChain `@tool` 裝飾的函式、`StructuredTool` 或 tool dicts 直接傳入 `tools=` 參數；Deep Agents 會自動從函式簽名與 docstring 推論工具 schema。
- **MCP（Model Context Protocol）支援**：
  - Python：安裝 `pip install "langchain[mcp]"` 或 `uv add "langchain[mcp]"`，載入 MCP server 工具後直接傳給 `create_deep_agent`。
  - JavaScript：安裝 `npm install @langchain/mcp-adapters`。

## 相關頁面
- [[guides/deepagents-customization]]
- [[comparisons/deepagents-vs-other-frameworks]]
- [[concepts/deepagents-subagents]]
- [[concepts/deepagents-backends-and-sandboxes]]
- [[concepts/deepagents-memory-and-skills]]
- [[concepts/deepagents-context-engineering]]
- [[concepts/deepagents-human-in-the-loop]]
- [[concepts/deepagents-streaming-and-fault-tolerance]]

## 出處
- docs/deepagents/overview.md
- docs/deepagents/quickstart.md
- docs/deepagents/models.md
- docs/deepagents/tools.md
- docs/deepagents/mcp.md
