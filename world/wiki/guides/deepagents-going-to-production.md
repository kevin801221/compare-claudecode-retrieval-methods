# Deep Agents Going to Production

別名：Deep Agents 正式環境部署、Deep Agents 上線指南、Production Deployment、Managed Deep Agents、LangSmith Agent Server
框架：deepagents

## 摘要
本指南涵蓋將 Deep Agent 從本機原型部署至正式環境（Production）的核心考量，包含使用 Managed Deep Agents 或自訂 LangSmith Agent Server 的部署配置（`langgraph.json`）、執行參數（`thread_id` 與 `context`）、多租戶（Multi-tenancy）身分驗證與授權、非同步（Async）與持久化執行（Durability）。此外，詳述透過虛擬檔案系統與 `StoreBackend` 進行跨對話記憶（Memory）範圍界定、隔離執行環境（Filesystem 與 Sandboxes 的 Thread-scoped 及 Assistant-scoped 生命週期與憑證注入）、防護欄（Permissions、Fault tolerance、`PIIMiddleware` / `piiMiddleware`）以及透過 `@langchain/react` 的 `useStream` 連接前端 UI。

## 重點
- **核心部署原語（Production Primitives）**：
  - **Thread**：單一對話（single conversation）。預設情況下，訊息歷史與暫存檔案（scratch files）皆限定在該 thread 範圍內，不會跨對話保留。
  - **User**：與代理互動的使用者。記憶與檔案可設為使用者私有或跨使用者共享。身分識別與授權來自 auth layer。
  - **Assistant**：已配置的代理實例（configured agent instance）。記憶與檔案可綁定至單一 assistant 或跨所有 assistant 共享。
- **LangSmith Agent Server 與 Managed Deep Agents**：
  - 推薦上線路徑為 **Managed Deep Agents**：CLI-first 託管執行環境，在 LangSmith Cloud 與 Bring Your Own Cloud (BYOC) 上提供 public beta（BYOC 需使用 Managed Deep Agents CLI 與 SDK `v0.10` 或更新版本）。
  - 自訂 **LangSmith Agent Server**：適用於需要自訂應用程式碼、自訂路由（custom routes）、進階驗證的團隊。自動配置 threads、runs、store 與 checkpointer，內建 authentication、webhooks、cron jobs、observability，並可透過 MCP 或 A2A 暴露代理。
  - LangSmith Cloud 部署會自動將追蹤（traces）傳送至與部署同名的專案；建議搭配設定 LangSmith Engine 以監控 traces、偵測問題並提出修復建議。
- **`langgraph.json` 設定檔**：
  - 位於專案根目錄，供 LangGraph CLI（`langgraph dev` 本機開發）與 Agent Server（`langgraph deploy` 正式部署）建置與執行應用程式：
    - `dependencies`：要安裝的套件陣列，如 `["."]` 會將當前目錄作為套件安裝（讀取 `requirements.txt`、`pyproject.toml` 或 `package.json`）。
    - `graphs`：將 graph ID 映射至程式碼位置，格式為 `"<id>": "./<file>:<variable>"`。Python 範例為 `"agent": "./agent.py:agent"`；JavaScript/TypeScript 範例為 `"agent": "./src/agent.ts:agent"`。
    - `env`：指向包含環境變數（API keys、secrets）的 `.env` 檔案路徑（如 `".env"`），於建置時設定並在執行期可用。
- **呼叫代理（Invoking the agent）**：
  - 正式環境每次呼叫應攜帶兩個獨立的執行期參數：
    - `thread_id`（透過 `config={"configurable": {"thread_id": ...}}` 傳遞）：對話的穩定識別碼，供 checkpointer 持久化與恢復訊息歷史。產生新的 `thread_id` 即可開啟全新對話。
    - `context`：執行期供工具與 middleware 讀取的單次執行資料（per-run data），如 `user_id`（JS 為 `userId`）、API keys、feature flags 或 session metadata。透過 `context_schema` 定義結構，並由 `runtime.context` 存取。
  - **LangGraph SDK 呼叫範例**：
    - Python：從 `langgraph_sdk` 匯入 `get_client`，呼叫 `client = get_client(url="<DEPLOYMENT_URL>", api_key="<LANGSMITH_API_KEY>")`，建立 `thread = await client.threads.create()`，並使用 `client.runs.stream(thread["thread_id"], "agent", input={"messages": [{"role": "user", "content": "Plan a 3-day trip to Tokyo"}]}, context={"user_id": "user-123"}, stream_mode="updates")`。
    - TypeScript：從 `"@langchain/langgraph-sdk"` 匯入 `Client`，呼叫 `new Client({ apiUrl: "<DEPLOYMENT_URL>", apiKey: "<LANGSMITH_API_KEY>" })`，建立 `thread = await client.threads.create()`，並使用 `client.runs.stream(thread.thread_id, "agent", { input: { messages: [...] }, context: { userId: "user-123" }, streamMode: "updates" })`。
- **多租戶（Multi-tenancy）、RBAC 與外部憑證（End-user credentials）**：
  - **使用者身分與存取控制（User identity and access control）**：LangSmith Agent Server 支援 custom authentication 與 authorization handlers。Authorization handlers 在驗證成功後執行，可標記資源擁有權 metadata（如 `owner: user_id`）、回傳過濾器讓使用者僅見自身資源，或以 HTTP 403 拒絕未授權操作。
  - **角色基礎存取控制（RBAC）**：管理工作區成員權限（與終端使用者授權分離）：
    - `Workspace Admin`：完整權限，包含設定與成員管理。
    - `Workspace Editor`：可建立與修改資源，但無法刪除 runs 或管理成員。
    - `Workspace Viewer`：唯讀存取權限（Read-only access）。
    - Enterprise 方案支援自訂細粒度權限角色。
  - **OAuth via Agent Auth**：提供託管 OAuth 2.0 流程。首次使用時代理會中斷（interrupts）執行並提供 OAuth 同意 URL，認證後自動恢復並儲存與刷新 token：
    - Python：使用 `from langchain_auth import Client` 與 `from langchain.tools import tool, ToolRuntime`，在工具內呼叫 `await auth_client.authenticate(provider="github", scopes=["repo", "read:org"], user_id=runtime.server_info.user.identity)`，透過 `auth_result.token` 取得憑證。
    - TypeScript：使用 `import { Client } from "@langchain/auth"`，呼叫 `await authClient.authenticate({ provider: "github", scopes: ["repo", "read:org"], userId: runtime.serverInfo.user.identity })`，透過 `authResult.token` 取得憑證。
- **非同步（Async）與持久化（Durability）**：
  - **Async 慣例**：LangChain 的非同步方法皆以 `a` 為前綴（如 `ainvoke`、`abefore_agent`、`astream`）。在正式環境應建立 async tools（避免同步工具在獨立執行緒執行的開銷）、使用 async middleware hooks（如 `abefore_agent` 而非 `before_agent`），並在建立 sandboxes 或連接 MCP servers 的 graph factories 中使用 async。
  - **Durability**：基於 LangGraph persistence 層在每一步驟記錄 checkpoint。若遭遇故障、逾時或 human-in-the-loop 中斷，可從最後記錄的狀態恢復，不會遺失子代理已完成的工作。支援無限期中斷（Indefinite interrupts）、時間旅行重播（Time travel）與敏感操作稽核軌跡。
- **記憶範圍與配置（Memory Scoping & Configuration）**：
  - Deep Agents 將記憶存為虛擬檔案系統中的檔案。預設僅限單一 thread；若要跨 thread 共享，需使用 `CompositeBackend` 將預設設為 `StateBackend()`，並將特定路徑（如 `"/memories/"`）路由至寫入 LangGraph Store 的 `StoreBackend`。
  - **版本需求**：使用 `rt.server_info` 與 `rt.execution_info`（Python）需 `deepagents>=0.5.0`；使用 `rt.serverInfo` 與 `rt.executionInfo`（JS/TS）需 `deepagents>=1.9.0`。
  - **四種 Namespace 範圍模式**：
    - **User（推薦預設，綁定特定 Assistant 與 User）**：Python 為 `namespace=lambda rt: (rt.server_info.assistant_id, rt.server_info.user.identity)`；TS 為 `namespace: (rt) => [rt.serverInfo.assistantId, rt.serverInfo.user.identity]`。
    - **Assistant（同一個 Assistant 的所有使用者共享）**：Python 為 `namespace=lambda rt: (rt.server_info.assistant_id,)`；TS 為 `namespace: (rt) => [rt.serverInfo.assistantId]`。
    - **User（跨所有 Assistant 的全域使用者設定）**：Python 為 `namespace=lambda rt: (rt.server_info.user.identity,)`；TS 為 `namespace: (rt) => [rt.serverInfo.user.identity]`。
    - **Organization（全組織跨所有使用者與 Assistant 共享）**：Python 為 `namespace=lambda rt: (rt.context.org_id,)`；TS 為 `namespace: (rt) => [rt.context.orgId]`。
  - **Prompt Injection 警告**：共享記憶（Assistant、User 或 Organization 範圍）可能成為 prompt injection 攻擊途徑。若組織級策略（如 `(org_id)`）需供全員讀取，應限制僅能由應用程式碼寫入，並透過 permissions 或 backend policy hooks 禁止代理由對話中寫入共享路徑。
- **執行環境（Execution environment）：Filesystem 與 Sandboxes**：
  - **Filesystem Backends**（僅需讀寫檔案時使用）：
    - `StateBackend`（預設）：Thread-scoped 暫存空間，每步皆會寫入 checkpoint，應避免寫入大型檔案。
    - `StoreBackend`：Cross-thread 跨對話儲存，搭配 namespace factory 使用。
    - `CompositeBackend`：混合預設暫存空間與特定跨對話路由（如 `"/memories/"`）。
    - `ContextHubBackend`（僅 Python）：將持久化檔案存於 LangSmith Hub repo（`owner/name` 或 `name`），無需另外配置 LangGraph store。
    - **禁止在正式部署使用 `FilesystemBackend` 與 `LocalShellBackend`**，因為它們會直接存取主機（host）。
  - **Sandboxes 生命週期（Lifecycle）**：
    - 提供隔離容器與 `execute` 工具執行 shell 指令。
    - **Thread-scoped（最常見）**：Sandbox ID 存於 Thread metadata，每次對話皆為全新環境，同一個 thread 的後續訊息共用同一 sandbox（如已安裝的 `pandas` 會保留），新 thread 則從乾淨狀態開始，於 TTL 到期時自動清理。
    - **Assistant-scoped**：Sandbox ID 存於 Assistant config，該 assistant 的所有對話共用同一 sandbox（保留 cloned repo、已安裝套件與建置產物）。需設定 TTL、定期快照重置（snapshots）或清理邏輯，避免磁碟與記憶體無限增長。
    - **Async Graph Factory 注意事項**：因為建立或查找 sandbox 需要執行期的 `thread_id` 或 `assistant_id`，`agent` 變數必須定義為接收 `RunnableConfig` 的 async function（從 `config["configurable"]` 讀取 `thread_id` 或 `assistant_id`），Graph factories 不會收到完整的 `Runtime`（沒有 `server_info` 或 `execution_info`）。
  - **跨 Sandbox 邊界傳輸檔案（File transfers & `SandboxSyncMiddleware`）**：
    - 使用 `upload_files()`（TS 為 `uploadFiles()`）在代理執行前植入檔案，並用 `download_files()`（TS 為 `downloadFiles()`）在結束後取回產物。
    - 自訂同步 Middleware 範例（`SandboxSyncMiddleware` / `createSandboxSyncMiddleware`）：結合 `LangSmithSandbox`（來自 `deepagents.backends.langsmith` 或 `"deepagents"`）與 ` SandboxClient`（來自 `langsmith.sandbox` 或 `"langsmith/sandbox"`）。在 `abefore_agent` / `beforeAgent` 中從 `runtime.store` 搜尋 `("skills", user_id)` 與 `("memories", user_id)`，經過 `_safe_filename` / `safeFilename`（拒絕包含 `".."`、`"*"` 或 `"?"` 的 key）驗證後上傳至 `/skills/{name}` 與 `/memories/{name}`；在 `aafter_agent` / `afterAgent` 中下載 `/memories/{item.key}` 並寫回 store。
  - **Sandbox 機密管理（Managing secrets）**：
    - **Auth proxy（推薦）**：透過 sandbox auth proxy 攔截從 sandbox 發出的請求並自動注入認證標頭，使 API keys 絕不進入 sandbox 程式碼、環境變數或日誌。配置格式為 `proxy_config.rules`，包含 `name`（如 `"openai-api"`、`"anthropic-api"`）、`match_hosts`（如 `["api.openai.com"]`、`["api.anthropic.com"]`）與 `inject_headers`（如 `"Authorization": "Bearer ${OPENAI_API_KEY}"`、`"x-api-key": "${ANTHROPIC_API_KEY}"`），其中 `${SECRET_KEY}` 會解析自 LangSmith workspace settings 的 secrets。
    - **Workspace secrets**：供 Agent Server 本身（而非 sandbox 內程式碼）使用的金鑰，存於 LangSmith workspace secrets 作為執行期環境變數。切勿透過環境變數或檔案上傳將機密傳入 sandbox。
- **防護欄（Guardrails）**：
  - **Permissions**：宣告式 allow/deny 檔案與目錄讀寫規則，依宣告順序評估，第一條匹配的規則生效（first matching rule wins）。
  - **Fault tolerance**：速率限制、重試、備援與錯誤處理。
  - **Data privacy（PII 偵測與處理）**：
    - Python：從 `langchain.agents.middleware` 匯入 `PIIMiddleware`，例如 `PIIMiddleware("email", strategy="redact", apply_to_input=True)` 與 `PIIMiddleware("credit_card", strategy="mask", apply_to_input=True)`。
    - TypeScript：從 `"langchain"` 匯入 `piiMiddleware`，例如 `piiMiddleware("email", { strategy: "redact", applyToInput: true })` 與 `piiMiddleware("credit_card", { strategy: "mask", applyToInput: true })`。
    - 支援策略（Strategies）：`redact`（替換為如 `[REDACTED_EMAIL]`）、`mask`（部分遮罩如 `****-****-****-1234`）、`hash`（決定性雜湊）與 `block`（拋出錯誤），亦支援自訂偵測器。
- **前端整合（Frontend）**：
  - 使用 `@langchain/react`（亦支援 Vue、Svelte、Angular）的 `useStream` hook 即時串流訊息、子代理進度與自訂狀態。
  - 本機開發指向 `http://localhost:2024`；正式環境設定 `apiUrl: "https://your-deployment.langsmith.dev"` 與 `assistantId: "agent"`。
  - 針對會衍生大量子代理的深層工作流，呼叫 `stream.submit` 時應啟用 `streamSubgraphs: true` 並設定高遞迴上限 `config: { recursionLimit: 10000 }` 以避免長執行被截斷。

## 相關頁面
- [[concepts/deepagents-backends]]
- [[concepts/deepagents-sandboxes]]
- [[concepts/deepagents-memory]]
- [[concepts/deepagents-permissions]]
- [[guides/deepagents-frontend]]

## 出處
- docs/deepagents/going-to-production.md
