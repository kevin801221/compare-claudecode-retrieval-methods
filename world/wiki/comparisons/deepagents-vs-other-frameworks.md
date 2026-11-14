# Deep Agents vs. Claude Agent SDK

別名：Deep Agents 與其他框架比較、Deep Agents vs Claude Agent SDK、Agent Harness 比較
框架：deepagents

## 摘要
Deep Agents 與 Claude Agent SDK 皆為用於建構自訂代理的 agent harness，但在執行環境架構、多租戶（multi-tenancy）支援、部署模式與模型供應商耦合度上採取了不同取捨。Deep Agents 支援任意模型供應商、可插拔的執行後端（sandbox 內部或外部遠端呼叫），並提供開箱即用的多租戶與 Agent Server 部署（Managed Deep Agents 或自託管 SDK）；而 Claude Agent SDK 則專注於 Anthropic 生態系，將代理綁定於執行所在的本地端 sandbox，且需自行建置伺服器、驗證與多租戶隔離層。

## 重點
### 總覽比較表（At a glance）
- **實際生產環境採用案例**：Deep Agents 在生產環境中被 OpenSWE 與 LangSmith Fleet 所使用（比較基準撰寫日期為 2026 年 4 月 16 日）。
- **Where the agent runs（代理執行位置）**：
  - **Deep Agents**：可在 sandbox 內部執行，或在 sandbox 外部透過遠端執行指令（將 sandbox 作為工具使用）。
  - **Claude Agent SDK**：僅能在 sandbox 內部執行（不過 Anthropic 的託管產品 Claude managed agents 則採用了分離式 decoupled 模型）。
- **Execution backend（執行後端）**：
  - **Deep Agents**：在 SDK 中可插拔（本地端、虛擬檔案系統、遠端 sandbox 或自訂後端）；Managed Deep Agents 則使用專案中宣告的單一代管 sandbox，由 LangSmith 自動建立、建立快照（snapshot）並在閒置時停止。
  - **Claude Agent SDK**：所運行之 sandbox 的本地端檔案系統。
- **Model provider（模型供應商）**：
  - **Deep Agents**：任意供應商（Anthropic、OpenAI、Google 及 100+ 家其他供應商），可獨立選擇模型供應商、執行後端與部署目標。
  - **Claude Agent SDK**：僅限 Claude（Anthropic、Bedrock、Vertex、Azure）。
- **Per-provider/model tuning（依供應商/模型微調）**：
  - **Deep Agents**：支援 Harness profiles（beta），可按供應商或特定模型註冊宣告式的系統提示、工具、middleware 與子代理微調組合。
  - **Claude Agent SDK**：需在每個模型呼叫點的程式碼中手動設定。
- **Deployment（部署方式）**：
  - **Deep Agents**：預設為 Managed Deep Agents（在 LangSmith 上透過 `mda deploy` 部署），或透過 `langgraph build` 建置獨立 Docker image 自行託管。且 SDK 與 Managed 兩模式間的 tools、middleware 與 subagents 程式碼可原封不動直接遷移（Managed 執行階段會接管 backend、store 與 checkpointer，而指令、skills 與 memory 則存放於專案檔案與 Context Hub）。
  - **Claude Agent SDK**：自行託管（Self-host），需自行建置 HTTP/WebSocket 或 SSE 伺服器、驗證（auth）與串流層。Claude Agent SDK 與 Claude managed agents 是兩個獨立產品，針對 SDK 撰寫的程式碼無法直接部署至 Claude managed agents。
- **Multi-tenancy（多租戶隔離）**：
  - **Deep Agents**：內建支援——可依每個使用者（per user）或每個助理（per assistant）設定 sandbox，具備範圍隔離的對話執行緒（scoped threads）、執行歷史與 RBAC（角色存取控制）。若使用 LangSmith Sandbox，還內建 auth proxy；Managed Deep Agents 更進一步提供代管的呼叫端身分識別（identity）與執行 OAuth 的連線（connections），讓終端使用者授權自己的帳號。
  - **Claude Agent SDK**：需自行建置 API 包裝層來為每位使用者啟動、追蹤並銷毀專屬 sandbox。
- **Production Agent Server（生產環境代理伺服器）**：
  - **Deep Agents**：內建 Agent Server，提供串流端點、執行緒管理、執行歷史、webhooks、驗證（authentication），而在 Managed Deep Agents 中還提供 MCP endpoint。
  - **Claude Agent SDK**：需自行開發、維運與保護伺服器。
- **License（授權條款）**：
  - **Deep Agents**：MIT。
  - **Claude Agent SDK**：MIT（但 Claude Code 本身為專有閉源軟體 proprietary）。
- **No-code 平台對比**：若需要跨任意模型供應商的無程式碼（no-code）代管代理平台，可使用 LangSmith Fleet；而 Claude managed agents 僅限於 Anthropic 生態系。

## 相關頁面
- [[concepts/deepagents-overview]]
- [[concepts/deepagents-backends-and-sandboxes]]
- [[guides/deepagents-customization]]

## 出處
- docs/deepagents/comparison.md
