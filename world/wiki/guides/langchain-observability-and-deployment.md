# LangChain Observability, Studio, UI, and Deployment

別名：可觀測性與部署指南、LangSmith Observability、LangSmith Cloud Deployment、LangSmith Studio、Agent Chat UI、LangChain Academy
框架：langchain

## 摘要
LangChain 透過 `create_agent`（Python）與 `createAgent`（TypeScript）建構的代理原生支援 **LangSmith Observability** 追蹤，只需設定環境變數即可自動記錄從使用者輸入、工具呼叫到最終回應的完整執行軌跡（Traces）。在開發、互動與正式環境部署階段，生態系提供 **LangSmith Studio** 進行本地視覺化偵錯、**Agent Chat UI** 渲染對話與工具呼叫及中斷執行緒，以及 **LangSmith Cloud**（或基於 Agent Streaming Protocol 的各大 JavaScript 平台）託管具備持久化狀態與背景執行能力的長時運行代理。

## 重點
- **LangSmith 可觀測性與追蹤（LangSmith Observability & Tracing）**：
  - **自動追蹤支援**：所有使用 `create_agent`（Python）或 `createAgent`（TypeScript）建立的 LangChain 代理皆自動支援 LangSmith 追蹤，無須修改或額外撰寫任何程式碼（Zero extra code needed）。
  - **Traces（軌跡）內容**：記錄代理執行的每一個步驟，包含初始使用者輸入、所有工具呼叫（Tool calls）、模型互動（Model interactions）、產生的提示詞、決策點以及最終回應。
  - **啟用追蹤的環境變數**：
    - `LANGSMITH_AGENT_ID="<your-agent-id>"`
    - `LANGSMITH_AGENT_ENVIRONMENT="local"`
    - `LANGSMITH_TRACING=true`（或 `"true"`）
    - `LANGSMITH_API_KEY=<your-api-key>`（需先於 `smith.langchain.com` 註冊帳號並建立 API key）
  - **Quickstart 範例**：使用 `model="gpt-6.1-sol"` 與工具 `[send_email, search_web]`（TypeScript 為 `[sendEmail, searchWeb]`）建立代理後直接呼叫 `agent.invoke({"messages": [{"role": "user", "content": "Search for the latest AI news and email a summary to john@example.com"}]})`，所有步驟即會自動記錄至設定的目標專案。
- **部署架構（Deployment）**：
  - **LangSmith Cloud**：提供全託管基礎設施（Fully managed infrastructure），專為具備持久化狀態（Persistent state）與背景執行（Background execution）的有狀態、長時運行代理（Stateful, long-running agents）設計，由 LangSmith 處理基礎設施、擴縮容與維運。
    - **前置條件與流程**：需具備 GitHub 帳號與 LangSmith 帳號；應用程式程式碼必須存放於 GitHub 儲存庫（支援公開與私有儲存庫），先依循本地伺服器設定指南確保應用程式與 LangGraph 相容，再將程式碼推送至 GitHub 進行部署。
  - **其他 LangSmith Agent Server 部署選項**：除了 Cloud 之外，亦支援 **hybrid（混合雲）**、**standalone servers（獨立伺服器）** 以及 **self-hosted with control plane（帶控制平面的自託管）**。
  - **JavaScript 框架與平台部署**：在 TypeScript/JavaScript 環境中，可使用相同的 **Agent Streaming Protocol** 將代理部署至 Next.js、SvelteKit、Nuxt、Cloudflare Workers 與 Deno Deploy。
- **LangSmith Studio 與本地開發**：
  - 提供本地伺服器設定與視覺化介面（Python 與 JavaScript 皆支援），方便在部署至正式環境前於本地端互動測試與檢視 LangGraph 相容的代理圖結構。
- **Agent Chat UI（代理對話前端介面）**：
  - 可連接至本地端（Local，如 LangSmith Studio）與已部署（Deployed）的代理伺服器。
  - **連線設定三要素**：
    1. **Graph ID**：輸入圖名稱（位於專案 `langgraph.json` 檔案中的 `graphs` 欄位下）。
    2. **Deployment URL**：Agent server 的端點網址（本地開發預設為 `http://localhost:2024`，或已部署代理的 URL）。
    3. **LangSmith API key (optional)**：加入 LangSmith API key（若使用本地 Agent server 則非必填）。
  - **核心功能**：設定完成後，Agent Chat UI 會自動抓取並顯示代理中所有被中斷的執行緒（Interrupted threads），且開箱即用支援渲染工具呼叫（Tool calls）與工具結果訊息（Tool result messages），並支援透過設定隱藏特定聊天訊息（Hiding Messages in the Chat）。
- **學習資源與版本更新日誌（Academy & Changelogs）**：
  - **LangChain Academy**：官方課程與學習平台，網址為 `https://academy.langchain.com/`。
  - **Python Changelog**：發布與更新紀錄位於 `https://docs.langchain.com/oss/python/releases/changelog`。
  - **JavaScript Changelog**：發布與更新紀錄位於 `https://docs.langchain.com/oss/javascript/releases/changelog`。

## 相關頁面
- [[guides/langchain-testing-and-evals]]
- [[concepts/langchain-multi-agent-overview]]

## 出處
- docs/langchain/observability.md
- docs/langchain/deploy.md
- docs/langchain/studio.md
- docs/langchain/ui.md
- docs/langchain/academy.md
- docs/langchain/changelog-py.md
- docs/langchain/changelog-js.md
