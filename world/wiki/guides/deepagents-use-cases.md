# Deep Agents Use Cases: Browser Use, Content Builder, Data Analysis, Deep Research, and OpenWiki

別名：Deep Agents 應用案例、Browser Use、瀏覽器自動化、Stagehand、agent-browser、Content Builder、內容生成代理、Data Analysis、資料分析代理、Deep Research、深度研究代理、OpenWiki
框架：deepagents

## 摘要
本指南彙整 Deep Agents 的五大實戰應用架構與端到端實作：**Browser Use**（透過 Stagehand v4、Playwright MCP 或 `agent-browser` CLI 操控本機 Chrome 或遠端 Browserbase 進行網頁操作與 LangSmith Sandbox 端到端 UI 測試）、**Content Builder**（結合品牌語氣指令、Skills、Tavily 搜尋子代理與 Gemini `gemini-2.5-flash-image` 生圖工具的內容創作代理）、**Data Analysis**（在 7 種 Sandbox 後端中執行 Python 資料分析、產生視覺化圖表並透過 `TodoListMiddleware` 追蹤進度與發送 Slack 報告）、**Deep Research**（利用 `TodoListMiddleware` 與平行上下文隔离子代理進行多步驟網路深度研究），以及 **OpenWiki**（透過 `AGENTS.md` 供編碼代理探索的儲存庫 Wiki 生成與維護工具）。

## 重點

### 1. Browser Use（瀏覽器操作與端到端 UI 測試）
- **雙核心組件架構**：
  - **Browser（瀏覽器執行環境）**：
    - **Local**：在開發機或 sandbox 內執行的 Chrome / Chromium，可連線自身的 `localhost`，無需第三方帳號，由使用者自行安裝與更新。
    - **Remote**：由 Browserbase 等雲端供應商提供的隔離瀏覽器，需 API key，無法存取本機或 sandbox 內的 `localhost`。
  - **Browser tools（瀏覽器控制工具）**：推薦使用 **Stagehand v4**，或選用 **Playwright MCP**（透過 MCP adapter 執行 `npx @playwright/mcp@latest`）與 Vercel Labs 的 **agent-browser** CLI。
- **Stagehand 三大核心工具**：
  - `snapshot`：讀取當前頁面的無障礙樹（accessibility tree）並為互動元素標記 ID（元素 ID 僅在當前頁面的最新 snapshot 中有效，導航或頁面變更後必須重新執行 `snapshot`）。
  - `run`：在頁面上批次執行 snapshot 動作（`click`、`hover`、`fill`、`type`、`press`、`select`），或執行使用 Playwright 風格 `page`、`context`、`browser` 物件的 JavaScript。
  - `screenshot`：將渲染後的頁面擷取為 PNG 或 JPEG。
- **Stagehand + Browserbase 整合方式（Python vs JavaScript）**：
  - **Python（原生 `StagehandMiddleware`）**：
    - 環境需求：Python 3.11+、LangChain 1.4.7+、Stagehand 4.3.0+。安裝套件：`pip install langchain-stagehand deepagents langchain-openai`，設定環境變數 `OPENAI_API_KEY` 與 `BROWSERBASE_API_KEY`。
    - 實作：從 `langchain_stagehand` 匯入 `StagehandMiddleware`，從 `stagehand` 匯入 `Stagehand, browserbase`。呼叫 `browser = await browserbase.launch(api_key=os.environ["BROWSERBASE_API_KEY"])` 與 `stagehand = await Stagehand.create(browser=browser)`，將 `middleware=[StagehandMiddleware(stagehand=stagehand)]` 傳入 `create_deep_agent(model="openai:gpt-6.1-sol", ...)`。因為工具為非同步，需使用 `await agent.ainvoke(...)` 或 `astream`，並在 `finally` 區塊呼叫 `await browser.close()`（不需額外 MCP server 或自訂 browser system prompt）。
  - **JavaScript / TypeScript（透過 Python MCP Server 與 `MCPAdapter`）**：
    - 原生 `langchain-stagehand` 僅限 Python；JS 需使用 `uv` 同步 `stagehand/packages/integrations/deepagents`（`uv sync --locked`），並安裝 `npm install deepagents @langchain/mcp-adapters@^2.0.1 @langchain/openai`。
    - 建立 `new MCPAdapter({ servers: { browser: { mode: "legacy", command: "uv", args: ["run", "--project", STAGEHAND_DIR, "--locked", "stagehand-deepagents-mcp"], env: serverEnv } } })`，其中 `serverEnv` 轉發 `STAGEHAND_*` 與 `BROWSERBASE_*` 變數並設定 `serverEnv.STAGEHAND_BROWSER = "browserbase"`。
    - 預設工具名稱會加上伺服器前綴：`browser_snapshot`、`browser_run`、`browser_screenshot`（若設 `prefixToolNameWithServerName: false` 則為 `run`、`snapshot`、`screenshot`）。執行期間必須保持 adapter 開啟，結束後於 `finally` 呼叫 `await adapter.close()`。
  - **上下文優化提示**：由於 `snapshot` 輸出可能很長，建議將瀏覽器工具交給 subagent，由主代理委派瀏覽器任務以保持主上下文整潔。
- **瀏覽器狀態範圍（Browser Scope）**：
  - **Thread scope**：每個對話一個獨立瀏覽器（適合使用測試帳號驗證應用程式變更，同一對話內可重用分頁與登入狀態）。
  - **User scope**：在同一位已驗證使用者的多個對話間重用登入狀態與 cookies（必須使用驗證層確認的真實身分，切勿跨無關使用者共用瀏覽器 session）。
  - 瀏覽器狀態**不屬於** LangGraph checkpoint 的一部分；關閉或替換瀏覽器會遺失登入狀態。Managed Deep Agents 可自動管理 thread 與 user scope。
- **在 LangSmith Sandbox 中使用 Chrome 與 `agent-browser` 進行端到端 QA 測試**：
  - **準備 Snapshot**：在含應用程式、Node.js 與 `curl` 的沙箱中執行 `npm install -g agent-browser@latest` 與 `agent-browser install --with-deps`（需以執行瀏覽器的同一使用者身分安裝），擷取為 snapshot 並設定環境變數 `LANGSMITH_API_KEY`、`OPENAI_API_KEY`、`QA_SNAPSHOT_ID`、`QA_START_COMMAND="cd /app && npm run dev -- --host 0.0.0.0 --port 3000"`。
  - **執行 QA 測試流程**：
    - Python 安裝 `pip install deepagents langsmith langchain-openai`；TS 安裝 `npm install deepagents@^1.15.1 langsmith@^0.9.0 @langchain/openai ws`。
    - 透過 `SandboxClient()` 建立沙箱（`client.create_sandbox(snapshot_id=os.environ["QA_SNAPSHOT_ID"])` / `await client.createSandbox(process.env.QA_SNAPSHOT_ID!)`）並封裝為 `LangSmithSandbox`。
    - 非阻塞啟動應用程式：`sandbox.run(..., wait=False, timeout=0, idle_timeout=-1)`（TS 為 `{ wait: false, timeout: 0, idleTimeout: -1 }`）。
    - 透過 `backend.execute` 執行 `curl --fail --retry 20 --retry-connrefused --retry-delay 1 --retry-max-time 30 http://127.0.0.1:3000` 等待服務就緒，再執行 `agent-browser --session qa --args "--no-sandbox" open http://127.0.0.1:3000`（在 root 執行的沙箱映像中以 `--no-sandbox` 停用 Chrome 內部沙箱，由外層 LangSmith sandbox 提供隔離）。
    - 代理透過 `execute` 執行 `agent-browser --session qa`（如 `snapshot -i` 檢視控制項）並將截圖存至 `/tmp/qa.png`。在清理沙箱前（Python 呼叫 `client.delete_sandbox(sandbox.name)` 與 `client.close()`；TS 呼叫 `await backend.close()` 自動刪除沙箱），使用 `backend.download_files(["/tmp/qa.png"])` / `backend.downloadFiles(["/tmp/qa.png"])` 將截圖下載回主機。

### 2. Content Builder（內容寫作與生圖代理）
- **核心功能與環境需求**：
  - 載入品牌語氣規範與寫作工作流（Skills），將網路研究委派給配備 `web_search`（Tavily）的 `researcher` 子代理，撰寫部落格或社群貼文，並使用 Google Gemini `gemini-2.5-flash-image` 產生封面與社群配圖。
  - 環境需求：Python 3.11+ 或 Node.js 18+；環境變數 `ANTHROPIC_API_KEY`、`GOOGLE_API_KEY`（即使對話模型選用 Claude，Gemini 生圖仍必備此金鑰）、`TAVILY_API_KEY`、`LANGSMITH_API_KEY`。
- **兩條實作路徑對照**：
  - **Managed Deep Agents 路徑**：
    - 初始化：`uvx --from managed-deepagents mda init content-builder`（Python）或 `npx managed-deepagents init content-builder`（JS）。
    - 依賴套件：Python `uv add tavily-python google-genai pillow`；JS `npm install tavily @google/generative-ai zod`。
    - 結構配置：在 `tools/content.py` 或 `tools/content.ts` 定義搜尋與生圖工具；在 `instructions.md` 撰寫常駐品牌語氣與研究規範（部署時會同步至 Context Hub）；在 `skills/blog-post/SKILL.md` 與 `skills/social-media/SKILL.md` 建立技能（Managed Deep Agents 會自動探索 `skills/`，無需傳遞 `skills=` 參數）；在 `agent.py` / `agent.ts` 配置生圖工具與行內 `researcher` 子代理。
    - 執行與部署：`uv run mda dev` / `npx mda dev`（在 LangSmith Studio 開啟，本機開發期間圖片會寫入專案目錄下）；部署使用 `uv run mda deploy` / `npx mda deploy`。
  - **Deep Agents SDK 路徑**：
    - 依賴套件：Python `pip install deepagents google-genai pillow pyyaml rich tavily-python langchain`（上游範例建議鎖定版本區間如 `>=0.3.5,<0.4.0`）；JS `npm install deepagents @langchain/core @langchain/anthropic @google/generative-ai tavily zod tsx`。
    - 結構配置：在專案根目錄建立 `AGENTS.md`（透過 `memory` 參數載入為系統提示詞）；建立 `skills/blog-post/SKILL.md` 與 `skills/social-media/SKILL.md`（指示先呼叫 `researcher` 子代理，將 markdown 寫入 `blogs/`、`linkedin/` 或 `tweets/`，並呼叫 `generate_cover` 或 `generate_social_image`）。
    - 子代理與腳本（`content_writer.py` / `content_writer.ts`）：Python 透過 `subagents.yaml` 宣告 `researcher` 子代理並由 `load_subagents` 解析工具名稱；JS 則在 `createDeepAgent` 內傳入行內子代理定義。皆搭配指向範例目錄的 `FilesystemBackend`。
    - 輸出位置差異：JS 執行成功後產物直接寫在專案根目錄下（如 `blogs/prompt-engineering/post.md`、`blogs/prompt-engineering/hero.png`、`research/prompt-engineering.md`）；Python 範例則會將產物寫入系統暫存目錄（macOS 與 Linux 通常位於 `/tmp/` 下）。

### 3. Data Analysis（資料分析與視覺化代理）
- **核心流程與架構**：
  - 接收 CSV 檔案（如 `./data/sales_data.csv`，在沙箱內位於 `/root/data/sales_data.csv`），透過選用的 `TodoListMiddleware`（`from langchain.agents.middleware import TodoListMiddleware`）啟用 `write_todos` 規劃分析步驟，在沙箱內撰寫並執行 Python 腳本（如使用 `pandas`、`matplotlib`、`seaborn` 建立 `/root/analyze_sales.py` 並輸出 6 宮格儀表板 `/root/sales_analysis_plot.png`），最後透過自訂工具 `slack_send_message` 將報告與圖表發送至 Slack。
  - **安全實踐**：避免將 Slack token 等機密放入沙箱內；`slack_send_message` 工具在主機端管理憑證，僅透過 `backend.download_files` 從沙箱下載產生的圖表後再透過 `slack-sdk` 上傳。
- **支援的 7 種執行環境 Backend 配置（Python）**：
  - **LangSmith**：安裝 `langsmith`，使用 `LangSmithSandbox`。
  - **Local shell**：提供無限制的本機檔案系統與 shell 存取，僅限受控開發測試環境使用。
  - **AgentCore**：安裝 `langchain-agentcore-codeinterpreter`，匯入 `from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter` 與 `from langchain_agentcore_codeinterpreter import AgentCoreSandbox`，呼叫 `interpreter = CodeInterpreter(region="us-west-2")`、`interpreter.start()`，並建立 `backend = AgentCoreSandbox(interpreter=interpreter)`。
  - **Daytona**：安裝 `langchain-daytona`，匯入 `from daytona import Daytona` 與 `from langchain_daytona import DaytonaSandbox`，呼叫 `sandbox = Daytona().create()` 與 `backend = DaytonaSandbox(sandbox=sandbox)`。
  - **E2B**：安裝 `langchain-e2b`，匯入 `from e2b import Sandbox` 與 `from langchain_e2b import E2BSandbox`，呼叫 `e2b_sandbox = Sandbox.create()` 與 `backend = E2BSandbox(sandbox=e2b_sandbox)`。
  - **Modal**：匯入 `import modal` 與 `from langchain_modal import ModalSandbox`，呼叫 `app = modal.App.lookup("your-app")`、`modal_sandbox = modal.Sandbox.create(app=app)` 與 `backend = ModalSandbox(sandbox=modal_sandbox)`。
  - **Runloop**：安裝 `langchain-runloop`，匯入 `from runloop_api_client import RunloopSDK` 與 `from langchain_runloop import RunloopSandbox`，呼叫 `client = RunloopSDK(bearer_token=api_key)`、`devbox = client.devbox.create()` 與 `backend = RunloopSandbox(devbox=devbox)`。
- **呼叫與串流**：結合 checkpointer 與 `TodoListMiddleware` 建立代理後，使用 `agent.stream_events({"messages": [input_message]}, config, version="v3")` 串流執行過程。

### 4. Deep Research（多步驟深度研究代理）
- **核心流程與工具設計**：
  - 主協調器（orchestrator）使用 `TodoListMiddleware`（`write_todos`）拆解研究問題，將具體子任務委派給擁有獨立上下文的研究子代理（research sub-agent），最後綜合各子代理的發現並附上引用來源產出完整報告。
  - 自訂搜尋工具 `tavily_search`：先透過 Tavily 探索相關 URL，再抓取完整網頁內文（Python 安裝 `tavily-python httpx markdownify` 抓取並轉為 Markdown；JS 直接使用內建 `fetch` API 呼叫 Tavily HTTP endpoint），讓子代理能分析完整原始內容而非僅依賴摘要。
- **Managed Deep Agents 與 SDK 路徑配置**：
  - **Managed Deep Agents**：以 `uvx --from managed-deepagents mda init deep-research` 或 `npx managed-deepagents init deep-research` 初始化；搜尋工具放於 `tools/search.py` 或 `tools/search.ts`；主協調器指令寫入 `instructions.md`；在 `agent.py` / `agent.ts` 中配置模型（支援 Claude 與 Gemini）、研究子代理、`TodoListMiddleware` 以及必填的 `name` 欄位（MDA 將其作為 LangGraph assistant ID 與預設部署名稱）。
  - **Deep Agents SDK**：在 `agent.py`（安裝 `deepagents tavily-python httpx markdownify langchain-core` 及 `langchain-anthropic` 或 `langchain-google-genai`）或 `agent.ts`（安裝 `deepagents langchain @langchain/core zod tsx` 及 `@langchain/anthropic` 或 `@langchain/google`）同一檔案內定義 `tavily_search` 以及三個提示詞常數：`RESEARCH_WORKFLOW_INSTRUCTIONS`、`RESEARCHER_INSTRUCTIONS`、`SUBAGENT_DELEGATION_INSTRUCTIONS`，並掛載 `TodoListMiddleware` 呼叫 `create_deep_agent` / `createDeepAgent`。支援同步執行或串流更新（Stream updates）。

### 5. OpenWiki
- **功能定位**：OpenWiki（文件路徑轉址至 `/oss/openwiki/overview`）用於自動生成與維護程式碼儲存庫的 Wiki，使編碼代理（coding agents）能夠透過專案中的 `AGENTS.md` 探索並理解儲存庫知識結構。

## 相關頁面
- [[concepts/deepagents-overview]]
- [[concepts/deepagents-sandboxes]]
- [[concepts/deepagents-subagents]]
- [[concepts/deepagents-skills]]
- [[guides/deepagents-going-to-production]]

## 出處
- docs/deepagents/browser-use.md
- docs/deepagents/content-builder.md
- docs/deepagents/data-analysis.md
- docs/deepagents/deep-research.md
- docs/deepagents/openwiki.md
