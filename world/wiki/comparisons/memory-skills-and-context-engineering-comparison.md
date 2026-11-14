# Memory, Skills, and Context Engineering Comparison Across Frameworks

別名：跨框架記憶與技能及上下文工程比較、Memory 比較、Skills 比較、CLAUDE.md vs AGENTS.md、SKILL.md 規格比較、Compaction vs SummarizationMiddleware
框架：agent-sdk、deepagents、langchain、langgraph

## 摘要
面對長對話與龐大工具集帶來的上下文視窗（Context Window）限制，四個框架分別發展出專案記憶檔（`CLAUDE.md` vs `AGENTS.md`）、漸進式揭露技能（`SKILL.md`）、按需工具載入（Tool Search vs `LLMToolSelectorMiddleware`）以及自動上下文壓縮（Auto-Compaction vs `SummarizationMiddleware` 與大型工具輸出卸載）。本頁完整比較各框架在記憶、技能與上下文工程上的設計與具體閾值。

## 重點

### 1. 記憶、技能與上下文管理跨框架總覽對照
| 維度 | Claude Agent SDK (`agent-sdk`) | Deep Agents (`deepagents`) | LangChain (`langchain`) | LangGraph (`langgraph`) |
|---|---|---|---|---|
| **持久指令 / 記憶檔** | `CLAUDE.md` 或 `.claude/CLAUDE.md`（使用者級為 `~/.claude/CLAUDE.md`），需設定 `setting_sources=["project", "user"]` 才會載入 | `AGENTS.md`（透過 `create_deep_agent(memory=["..."])` 由 `MemoryMiddleware` 永遠載入至 `<agent_memory>`）＋ `/memories/`（`StoreBackend`） | 透過 `checkpointer`（短期）與 `BaseStore`（長期），並在 `@dynamic_prompt` 或工具中讀寫 | `BaseCheckpointSaver`（執行緒狀態通道）與 `BaseStore`（跨執行緒命名空間文件與向量檢索） |
| **技能（Skills）機制** | `.claude/skills/<name>/SKILL.md`（需設定 `setting_sources` 並允許 `Skill` 工具） | 遵循 Agent Skills 規格之 `SKILL.md`（透過 `skills=["..."]` 由 `SkillsMiddleware` 掃描 frontmatter，代理以 `read_file` 按需讀取全文） | Multi-Agent Skills 模式（自訂 `load_skill` 工具按需回傳專業提示詞或透過 Middleware 動態解鎖工具） | 由上層框架（Deep Agents / LangChain）實作 |
| **上下文壓縮（Compaction / Summarization）** | CLI 內建自動 Compaction（接近上下文上限時自動摘要舊訊息，觸發 `PreCompact` Hook 與 `SDKCompactBoundaryMessage`），或傳入 `/compact` | 內建 `SummarizationMiddleware`（達模型視窗 **85%** 或 **170,000 tokens** 時觸發，保留最近 **10%** 或 **6 則訊息**，並將舊檔案寫入參數截斷） | 內建 `SummarizationMiddleware`（預設 `fraction=0.85`、保留 `fraction=0.10`）、`ContextEditingMiddleware`（`ClearToolUsesEdit` 預設 100,000 tokens 觸發）與 `trim_messages` | 使用 `trim_messages`、`RemoveMessage(id=...)`（或 `REMOVE_ALL_MESSAGES`）與 `SummarizationNode`（`langmem`） |
| **大型工具輸出處理** | MCP 工具輸出受 `MAX_MCP_OUTPUT_TOKENS`（預設 25,000 tokens 警告）控制；大型檔案透過 `Read` 的 `offset`/`limit` 分段讀取 | `FilesystemMiddleware` 自動將超過 **20,000 tokens** 的工具結果卸載（Offload）寫入檔案系統，僅在上下文保留路徑與前 **10 行**預覽 | 可透過 `ContextEditingMiddleware` 清除舊工具結果，或使用自訂 `@wrap_tool_call` 截斷 | 由節點或 State Reducer 控制 |
| **工具數量擴展（Tool Scaling）** | 內建 `ToolSearch` 工具與 `ENABLE_TOOL_SEARCH` 環境變數（預設 `auto`，當 MCP 工具描述超過上下文 **10%** 時改為按需搜尋載入） | 可搭配 `LLMToolSelectorMiddleware`、Skills 漸進式揭露或 `CodeInterpreterMiddleware`（PTC） | 內建 `LLMToolSelectorMiddleware`（先用輕量模型篩選最多 `max_tools` 個相關工具再呼叫主模型） | 透過 Router 子圖或動態綁定工具實現 |

### 2. `CLAUDE.md`（Claude Agent SDK）vs `AGENTS.md`（Deep Agents）
- **Claude Agent SDK 的 `CLAUDE.md`**：
  - SDK v0.1.0 起預設 `setting_sources` / `settingSources` 為空陣列 `[]`（不載入任何檔案系統設定）。
  - 必須顯式設定 `setting_sources=["project"]`（或包含 `"user"`、`"local"`）才會讀取專案根目錄的 `CLAUDE.md` / `.claude/CLAUDE.md`、`.claude/CLAUDE.local.md` 與 `~/.claude/CLAUDE.md`。
- **Deep Agents 的 `AGENTS.md`**：
  - 傳入 `create_deep_agent(memory=["/path/to/AGENTS.md"])` 後，`MemoryMiddleware` 會在每次執行時從配置的 `backend` 讀取所有指定檔案，包裹於 `<agent_memory>` 標籤中注入系統提示詞，並附加何時與如何透過 `edit_file` / `write_file` 更新記憶的指示。
  - 在 Deep Agents Code CLI 中，會自動探索全域 `~/.deepagents/<agent>/AGENTS.md`、從 Git 根目錄到當前目錄的所有 `AGENTS.md` 與 `.deepagents/AGENTS.md`（以符號連結抗重複，且支援自動記憶 `/remember`）。

### 3. `SKILL.md` 技能系統在 Claude Agent SDK 與 Deep Agents 的異同
- **共同點**：兩者均使用包含 YAML Frontmatter（`name`、`description` 等）的 `SKILL.md` 檔案，並採用**漸進式揭露（Progressive Disclosure）**——啟動時僅將技能名稱與 `description` 注入系統提示詞，待任務符合描述時才載入完整 `SKILL.md` 內容與同目錄下的參考腳本/文件。
- **差異點**：
  - **Claude Agent SDK**：技能固定存放於 `.claude/skills/<skill-name>/SKILL.md` 或 `~/.claude/skills/<skill-name>/SKILL.md`；必須在 `setting_sources` 包含 `"project"` / `"user"` 且在 `allowed_tools` 包含 `"Skill"`，由模型呼叫 `Skill` 工具載入。
  - **Deep Agents SDK**：技能路徑可任意指定（`skills=["/skills/user/", "/skills/project/"]`），儲存在任何 `BackendProtocol`（記憶體、資料庫、本地磁碟或遠端沙盒）中；遵循 Agent Skills 規格（`name` 最長 64 字元小寫英數連字號且須與目錄同名、`description` 最長 1024 字元、`SKILL.md` 檔案須小於 10MB），後列來源覆蓋前列同名技能（Last-one-wins），模型直接使用內建的 `read_file` 工具讀取 `SKILL.md` 全文。

### 4. Deep Agents 與 LangChain 的自動上下文壓縮細節
- **Deep Agents 三階段上下文管理**：
  1. **大型工具結果即時卸載（Offloading）**：當任何工具回傳結果超過 **20,000 tokens** 時，自動將完整內容存入虛擬檔案系統並替換為檔案路徑與前 **10 行**預覽（`read_file` 預設每次讀取 **100 行**，單次上限 **100,000 字元**；多模態圖片/音訊/影片/PDF 區塊永不卸載）。
  2. **舊檔案寫入參數截斷（Argument Truncation）**：當上下文達到模型視窗的 **85%**（若模型無 profile 則為 **170,000 tokens**）時，先將較舊訊息中 `write_file` 與 `edit_file` 工具呼叫的大型參數截斷。
  3. **對話歷史摘要（Summarization）**：若截斷後仍超過 **85%**（或 170,000 tokens），`SummarizationMiddleware` 會將完整歷史備份至檔案系統 `/conversation_history/{thread_id}.md`，並將舊訊息壓縮為摘要，僅保留最近 **10%** 的 token（或無 profile 時保留最近 **6 則訊息**）。

## 相關頁面
- [[guides/agent-sdk-system-prompts]]
- [[concepts/agent-sdk-skills-and-plugins]]
- [[concepts/agent-sdk-mcp]]
- [[concepts/deepagents-memory-and-skills]]
- [[concepts/deepagents-context-engineering]]
- [[concepts/langchain-memory-and-context-engineering]]
- [[entities/langchain-builtin-middleware]]
- [[concepts/langgraph-memory-and-stores]]

## 出處
- docs/agent-sdk/modifying-system-prompts.md
- docs/agent-sdk/skills.md
- docs/agent-sdk/tool-search.md
- docs/agent-sdk/agent-loop.md
- docs/deepagents/memory.md
- docs/deepagents/skills.md
- docs/deepagents/context-engineering.md
- docs/deepagents/code/memory-and-skills.md
- docs/langchain/short-term-memory.md
- docs/langchain/long-term-memory.md
- docs/langchain/context-engineering.md
- docs/langchain/middleware/built-in.md
- docs/langgraph/stores.md
- docs/langgraph/add-memory.md
