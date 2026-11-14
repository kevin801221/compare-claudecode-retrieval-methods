# Deep Agents Memory & Skills

別名：長期記憶與技能、Memory、Skills、`AGENTS.md`、`SKILL.md`、`MemoryMiddleware`、`SkillsMiddleware`、Progressive Disclosure、Agent Skills Specification、`pinned_skills`
框架：deepagents

## 摘要
Deep Agents 以虛擬檔案系統為基礎實現一等公民的長期記憶（Memory）與技能（Skills）。記憶透過 `memory` 參數與 `MemoryMiddleware` 在代理啟動時載入 `AGENTS.md` 等檔案，提供跨對話的持續背景知識與偏好；技能則遵循 Agent Skills 規範（`SKILL.md`），透過 `skills` 參數與 `SkillsMiddleware` 實施三階段漸進式揭露（Progressive Disclosure），並支援技能專屬工具（`metadata.include_tools`）、動態重新載入與技能釘選（Pinning）。

## 重點
### Memory（長期記憶）架構與範圍設計
- **運作流程**：
  1. 建立代理時將檔案路徑清單傳入 `memory=`（如 `memory=["/memories/AGENTS.md"]`），由配置的 backend 控制儲存位置與存取權。
  2. 代理於啟動時將記憶檔載入系統提示。
  3. 代理在學到新資訊時，可透過內建 `edit_file` 工具於對話期間（預設 hot path）更新記憶檔，或透過背景整合代理（background consolidation）在對話之間更新。
- **記憶的六大維度（Dimensions）**：
  - **Duration（持續時間）**：Short-term（單一對話內，透過 checkpointer 儲存於 state）或 Long-term（跨對話，透過 store 持久化）。
  - **Information type（資訊類型）**：Episodic（過去經驗與完整對話過程）、Procedural（程序性技能與指令，即 `skills`）、Semantic（事實與偏好，如 `AGENTS.md`）。
  - **Scope（範圍）**：User（單一使用者）、Agent（整個代理共享）、Organization（全組織共享）。
  - **Update strategy（更新策略）**：During conversation（預設 hot path）或 Between conversations（background consolidation）。
  - **Retrieval（檢索方式）**：Loaded into prompt（預設）或 On demand（如 skills）。
  - **Agent permissions（權限）**：Read-write（預設）或 Read-only（組織政策與共享知識庫）。
- **三種範圍模式（Scoped Memory，搭配 `CompositeBackend` 與 `StoreBackend`）**：
  - **Agent-scoped memory**：命名空間設為 `lambda rt: (rt.server_info.assistant_id,)`（Python，需 `deepagents>=0.5.0`；舊版為 `get_config()["metadata"]["assistant_id"]`）或 `(rt) => [rt.serverInfo.assistantId]`（JS，需 `deepagents>=1.9.0`；舊版為 `getConfig().metadata.assistantId`）。所有使用者的對話皆讀寫同一份記憶檔，讓代理隨時間演化出持久人格與累積知識。
  - **User-scoped memory**：命名空間設為 `lambda rt: (rt.server_info.user.identity,)`（Python）/ `(rt) => [rt.serverInfo.user.identity]`（JS）。每位使用者擁有獨立隔離的記憶與偏好。若在同一部署中有多個代理，可組合為 `(rt.server_info.assistant_id, rt.server_info.user.identity)`。
  - **Organization-level memory**：命名空間設為 `lambda rt: (rt.context.org_id,)`（Python）/ `(rt) => [rt.context.orgId]`（JS）。通常設為**唯讀（Read-only）**（由應用程式碼透過 `client.store.put_item` / `client.store.putItem` 寫入，並以 `FilesystemPermission` 拒絕代理寫入），防止跨使用者的間接提示注入（prompt injection）。
  - **預置 Store 資料注意事項**：`CompositeBackend` 在轉發檔案操作前會**剝除路由前綴（route prefix）**。因此使用 `store.put` 結合 `create_file_data()`（Python `from deepagents.backends.utils import create_file_data` / JS `createFileData`）預置資料時，必須使用相對於該後端的鍵（如 `"/AGENTS.md"`、 `"/preferences.md"`、 `"/langgraph-docs/SKILL.md"`），而非代理端看到的 `"/memories/AGENTS.md"` 或 `"/skills/..."`。
- **情節記憶（Episodic Memory）與背景記憶整合（Background Consolidation / Sleep Time Compute）**：
  - **Episodic Memory**：將歷史對話執行緒搜尋封裝為自訂 `@tool`（如 `search_past_conversations`），從 `runtime.server_info.user.identity` 取得 `user_id`，再呼叫 `client.threads.search(metadata={"user_id": user_id}, limit=5)` 與 `client.threads.get_history(thread_id=...)` 檢索過往解決問題的完整過程。
  - **Background Consolidation**：為降低對話期間的多工延遲或避免對同一檔案並行寫入造成的 last-write-wins 衝突，可在 `langgraph.json` 中额外部署一個 `consolidation_agent`，並透過 `client.crons.create(assistant_id="consolidation_agent", schedule="0 */6 * * *", ...)` 定期執行（所有 cron 排程均以 **UTC** 解析）。**注意**：cron 的執行間隔（如每 6 小時 `0 */6 * * *`）必須與工具內的回溯時間窗（如 `timedelta(hours=6)`）保持同步，以免重複處理或漏失記憶。

### Skills（技能）架構、漸進式揭露與 Agent Skills 規範
- **版本需求**：JS 需 `deepagents>=1.7.0`。
- **目錄結構與來源路徑規則**：
  - 每個技能為一個獨立子目錄，內含必填的 `SKILL.md` 及選填的資源目錄：`scripts/`（可執行腳本）、`references/`（按需讀取的補充參考文件，如 `REFERENCE.md`、`FORMS.md`）、`assets/`（靜態範本、圖片、查找表或 schema）。
  - **Python vs. JS `skills` 路徑層級差異**：在 Python 中，`skills` 陣列中的每個路徑**必須指向包含技能子目錄的父容器目錄**（若直接指向含有 `SKILL.md` 的技能目錄本身則不會載入且不報錯）；在 JS 中，來源路徑可指向父容器目錄，也可直接指向含有 `SKILL.md` 的技能目錄。
  - **來源覆寫順序（Precedence / Last one wins）**：當多個技能來源包含同名技能時，在 `skills` 清單中**排在後面（later）的來源會覆寫前面的來源**。SDK 不會自動掃描 `~/.deepagents/...` 或 `~/.agents/...`；若要在 SDK 中模擬 Deep Agents Code 的優先順序，需依由低至高順序明確傳入：
    1. `"<user-home>/.deepagents/{agent}/skills/"`
    2. `"<user-home>/.agents/skills/"`
    3. `"<project-root>/.deepagents/skills/"`
    4. `"<project-root>/.agents/skills/"`
- **三階段漸進式揭露（Three-level Progressive Disclosure）**：
  1. **Level 1 — Metadata（Discovery，由 `SkillsMiddleware` 於啟動時處理）**：掃描設定的技能路徑，解析每個 `SKILL.md` 的 YAML frontmatter，僅將 `name` 與 `description` 注入系統提示。
  2. **Level 2 — Instructions（Read，由 `SkillsMiddleware` / 代理觸發時處理）**：當任務匹配技能描述時，代理透過 `read_file` 讀取完整的 `SKILL.md` 本體指令。
  3. **Level 3 — Resources（Execute，由 LLM 按需處理）**：啟動後，代理僅在 `SKILL.md` 指令明確提及時才讀取或執行 `scripts/`、`references/`、`assets/` 下的支援檔案（建議引用保持一層深度，避免深層巢狀引用鏈）。
- **`SKILL.md` Frontmatter 欄位與大小限制（Agent Skills Specification）**：
  - `name`（必填）：小寫英數字元與連字號（hyphens），長度 **1–64 字元**，且**必須與父目錄名稱完全一致**。
  - `description`（必填）：說明技能用途與啟用時機，上限 **1,024 字元**（啟動探索階段代理唯一能看到的資訊）。
  - `license`（選填）：授權條款名稱或隨附授權檔案參照。
  - `compatibility`（選填）：環境需求（系統套件、網路存取等），上限 **500 字元**。
  - `metadata`（選填）：任意鍵值對（Deep Agents 擴充功能會讀取 `metadata.include_tools`）。
  - `allowed-tools`（選填，Experimental）：以空白分隔的預先核准工具清單。
  - **大小與行數限制**：在 Deep Agents 中，**`SKILL.md` 檔案大小必須小於 10 MB**（超過 10 MB 的檔案在探索階段會被直接跳過）。此外規範建議將 `SKILL.md` 本體控制在 **5,000 tokens** 與 **500 行**以內，可使用 `skills-ref` 驗證工具檢查格式。

### 技能專屬工具（Skill Tools，`metadata.include_tools`）
- **版本需求**：Python 需 `deepagents>=0.7.22`；JS 需 `deepagents>=1.15.0`。
- **設定方式**：
  - 在 `SKILL.md` 的 frontmatter 中，於 `metadata.include_tools` 下以**空白分隔字串（space-separated string）**列出工具名稱（注意：**YAML 列表格式無法匹配任何工具**）。
  - 建立自訂的 `SkillsMiddleware(backend=..., sources=[...], tools=[...])`（Python）或 `createSkillsMiddleware({ backend, sources, tools })`（JS）並傳入 `middleware` 參數（工具傳給 middleware 的 `tools` 而非代理的 `tools`）。
- **閘門控管規則（Gating rules）**：
  - 技能工具受閘門控管：在代理讀取該技能的 `SKILL.md`（或釘選該技能）之前，該工具完全隱藏，即使模型猜中工具名稱與參數並嘗試呼叫也會以未知工具失敗。
  - 一旦對話摘要壓縮（summarization）將該次 `SKILL.md` 的讀取紀錄從對話歷史中移除，該技能工具會再次變為不可用，直到代理重新讀取該技能為止。
  - 若技能列出的工具已經存在於代理自身的 `tools`（包含內建工具如 `edit_file`），Deep Agents 會優先使用代理自身的工具。
- **執行階段工具解析器（Runtime Tool Resolver）與可搜尋延遲工具**：
  - `SkillsMiddleware` / `createSkillsMiddleware` 的 `tools` 參數可傳入一個解析器函式（JS 型別為 `SkillToolResolver` 或 `SkillToolResolver<TContext>`，支援 async），接收 `(tool_name, runtime)` 並動態回傳一個或多個真實工具（例如將單一名稱 `"linear"` 展開為 Linear MCP server 的所有工具，或依 `runtime.context` 中的使用者身分回傳不同工具）。解析器會在代理讀取技能後的每次模型呼叫與每次技能工具呼叫前執行，應保持快速。
  - **結合 Provider Tool Search**：若將工具標記為 `extras={"defer_loading": True}`（Python）/ `extras: { defer_loading: true }`（JS）並傳入代理自身的 `tools`（搭配 `ProviderToolSearchMiddleware` / `providerToolSearchMiddleware`），則在讀取技能前模型可透過搜尋找到並呼叫它（不受閘門阻擋），而在讀取技能後則會直接顯現無須搜尋。

### 重新載入技能（Reload Skills）與釘選技能（Pin Skills）
- **重新載入技能（Reload skills，Python 需 `deepagents>=0.7.16`；JS 需 `deepagents>=1.14.0`）**：
  - 當配置了 checkpointer（如部署於 LangSmith Agent Server）時，技能每個執行緒僅載入一次並快取於 `skills_metadata` 狀態中。
  - 若要在執行緒中途重新載入新增、編輯或刪除的技能，需將儲存的元資料重設為 Python `None` 或 JS `null`（透過 `invoke({"messages": ..., "skills_metadata": None})`、`update_state` 或在 custom middleware hook 中重設；注意 Python 應在 `after_agent` 而非 `after_model` 重設，JS 則在每次模型呼叫前生效）。**切勿設為空陣列 `[]`**，因為空陣列代表「已載入且無任何技能」，會導致該執行緒後續完全看不到任何技能。
- **釘選技能（Pin skills，Python 需 `deepagents>=0.7.23`；JS 需 `deepagents>=1.15.0`）**：
  - 當使用者透過斜線指令（如 `/langgraph-docs`）或選單直接指定技能時，可在執行輸入中傳入 `pinned_skills=["langgraph-docs"]`（Python）或 `pinnedSkills: ["langgraph-docs"]`（JS；在 JS custom middleware 中可宣告 `pinnedSkillsValue` 狀態）。
  - 在下次模型呼叫前，`SkillsMiddleware` 會依序讀取每個指定技能的 `SKILL.md`（去除 frontmatter），並包裝為 `<skill name="..." path="...">...</skill>` 格式的 `HumanMessage` 附加至對話中（同時啟用該技能的 `include_tools`）。
  - 該訊息會設定 `additional_kwargs["lc_source"] = "pinned_skill"`，並將技能的 `name`、`path` 與 `description` 放入 `additional_kwargs["skill"]` 供前端 UI 顯示為標籤。

### 搭配沙盒執行技能腳本（Execute Code with Skills）
- 代理雖可從任何 backend 讀取腳本，但**執行腳本需要 shell 存取權（僅 sandbox backends 提供）**。
- 當技能檔案儲存在隔離沙盒容器外部的 backend 時，可撰寫自訂 middleware：在 `before_agent` 中從 backend 讀取技能檔案並透過 `upload_files` / `uploadFiles` 上傳至沙盒；在 `after_agent` 中從沙盒透過 `download_files` / `downloadFiles` 下載更新或新建的技能檔案並寫回 backend。

## 相關頁面
- [[concepts/deepagents-overview]]
- [[guides/deepagents-customization]]
- [[concepts/deepagents-backends-and-sandboxes]]
- [[concepts/deepagents-subagents]]
- [[concepts/deepagents-context-engineering]]
- [[concepts/agent-sdk-skills-and-plugins]]
- [[concepts/agent-sdk-memory]]

## 出處
- docs/deepagents/memory.md
- docs/deepagents/skills.md
