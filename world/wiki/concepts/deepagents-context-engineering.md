# Deep Agents Context Engineering

別名：上下文工程、Context Engineering、`SummarizationMiddleware`、Context Offloading、Context Compression、`DeepAgentState`、`compact_conversation`、`create_summarization_tool_middleware`
框架：deepagents

## 摘要
Deep Agents 的上下文工程（Context Engineering）涵蓋五種上下文機制：啟動時的靜態輸入上下文（Input context）、單次執行的執行階段上下文（Runtime context）、自動與按需的上下文壓縮（Context compression，包含卸載與摘要）、透過子代理進行的上下文隔離（Context isolation），以及跨對話持久化的長期記憶（Long-term memory）。每個由 `create_deep_agent` / `createDeepAgent` 建立的代理皆內建大型工具輸入/結果卸載（20,000 tokens 閾值）與 `SummarizationMiddleware`（85% 上下文視窗或 170,000 tokens 觸發閾值），確保長時執行的任務不會超出模型上下文視窗限制。

## 重點
### 五大上下文類型與組裝後系統提示（Complete System Prompt）
- **五大上下文類型（Types of context）**：
  1. **Input context**：啟動時進入代理系統提示的內容（system prompt、memory、skills、tool prompts），靜態且每次執行套用。
  2. **Runtime context**：呼叫時傳入的靜態設定（user metadata、API keys、connections、feature flags），單次執行有效並自動傳播至所有 subagents。
  3. **Context compression**：內建的內容卸載（offloading）與摘要（summarization），在接近視窗上限時自動觸發。
  4. **Context isolation**：使用 subagents 隔離繁重工作，僅將最終結果回傳給主代理。
  5. **Long-term memory**：透過虛擬檔案系統（如 `CompositeBackend` 路由 `/memories/` 至 `StoreBackend`）跨執行緒與對話持久化資訊。
- **完整系統提示組裝順序（Complete system prompt，由 1 至 8）**：
  1. Custom `system_prompt`（若有提供）
  2. Base agent prompt（內建基礎代理提示）
  3. Memory prompt：`AGENTS.md` 內容 + 記憶使用指南（僅在提供 `memory` 時包含）
  4. Skills prompt：技能位置 + 各技能 frontmatter 資訊清單 + 使用方式（僅在提供 `skills` 時包含）
  5. Virtual filesystem prompt：檔案系統工具（`ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`）及 `execute` 工具（若為 sandbox backend）說明文件
  6. Subagent prompt：`task` 工具委派使用指南
  7. User-provided middleware prompts（若提供了自訂 middleware）
  8. Human-in-the-loop prompt（當設定了 `interrupt_on` 時包含）
  - （註：Deep Agents Code 另包含 Local context prompt 提供當前目錄與專案資訊）。
- **動態系統提示與工具描述微調**：
  - `system_prompt`（Python）/ `systemPrompt`（JS）參數預設為靜態；若需依 `request.runtime.context` 或 `request.runtime.store` 動態改變系統提示，Python 可使用 `@dynamic_prompt` 裝飾器，JS 可使用 `dynamicSystemPromptMiddleware`（若僅有工具本身需讀取 context 或 store，工具可直接從注入的 `ToolRuntime` / `runtime` 讀取，無須額外加 middleware）。
  - 若要針對特定模型覆寫工具描述或排除不使用的內建工具以縮減基礎提示大小，可使用 `HarnessProfile` 的 `tool_description_overrides` 與 `excluded_tools`。

### Runtime Context 與自訂狀態結構（Custom State Schema）
- **Runtime Context（`context_schema` / `contextSchema`）**：
  - Python：以 `dataclasses.dataclass` 或 `typing.TypedDict` 定義並傳給 `context_schema`，呼叫 `invoke` / `ainvoke` 時透過 `context=` 參數傳入，在工具內透過 `ToolRuntime` 的 `runtime.context` 讀取。
  - JS：以 Zod 物件 schema（如 `z.object({ ... })`）定義並傳給 `contextSchema`，呼叫時於 options 的 `context` 欄位傳入，在工具處理器中從 `runtime.context` 讀取。
  - 自動傳播至所有子代理。
- **Custom State Schema（`state_schema`，僅 Python，需 `deepagents>=0.6.6`）**：
  - 當代理或 middleware 需要追蹤跨越模型呼叫與工具呼叫的可變狀態（如計數器、旗標、累積值）、在工具與 middleware 間共享資料，或隨執行緒一起透過 checkpointer 保存時使用。
  - **必須繼承 `DeepAgentState`**，以保留 `messages` 欄位上內建的 `DeltaChannel` reducer（確保對話變長時 checkpoint 大小呈線性成長）。
  - 傳給 `subagents=` 的宣告式 `SubAgent` 字典規格在編譯為 `task` 工具時會**自動繼承父代理的 `state_schema`**；但預先編譯的 `CompiledSubAgent` 與遠端 `AsyncSubAgent` 不會自動繼承（若有需要須在編譯時使用相容 schema）。

### 上下文壓縮：自動卸載（Offloading）
- 每次 `create_deep_agent` 呼叫皆內建自動內容卸載，預設 token 閾值為 **20,000 tokens**，分為兩種情況：
  1. **Tool call inputs 超過 20,000 tokens**：檔案寫入與編輯操作（`write_file` / `edit_file`）會在對話歷史留下包含完整檔案內容的工具呼叫參數。當工作階段上下文超過模型可用視窗的 **85%** 時，Deep Agents 會自動截斷較舊的工具呼叫參數，替換為指向磁碟/檔案系統上該檔案的指標（pointer）。
  2. **Tool call results 超過 20,000 tokens**：當工具回傳結果超過 20,000 tokens 時，Deep Agents 會將完整回應卸載寫入配置的 backend（例如 `/large_tool_results/` 下），並在訊息中替換為**檔案路徑參照（file path reference）以及前 10 行預覽（preview of the first 10 lines）**，讓代理後續按需使用 `read_file` 或 `grep` 檢索。
- （注意：內建上下文壓縮不會縮放圖片尺寸、降低圖片解析度或產生視覺嵌入）。

### 上下文壓縮：自動與按需摘要（Summarization）
- **`SummarizationMiddleware` 雙軌機制（JS 需 `deepagents>=1.6.0` 以支援 `wrapModelCall` 摘要、精確 token 計算與 `ContextOverflowError` 自動回退）**：
  1. **In-context summary**：由 LLM 產生包含工作階段意圖（session intent）、已建立產物（artifacts created）與下一步驟（next steps）的結構化摘要，取代代理工作記憶中的舊對話歷史。
  2. **Filesystem preservation**：將原始對話訊息的文字渲染版本寫入檔案系統（如 `/conversation_history/`）作為標準紀錄（canonical record），使代理仍能透過檔案搜尋找回細節。
  - 在 Python 中，摘要僅修改發送給模型的請求訊息，**不會刪除或改寫持久化的 `state["messages"]` 歷史**，以支援重播（replay）與評估（evaluation）。
- **預設觸發閾值與保留規則（Configuration）**：
  - **觸發點（Trigger）**：達到模型 profile（`max_input_tokens`）的 **85%** 時觸發。
  - **保留量（Keep）**：保留最近 **10%** 的 tokens 作為近期上下文。
  - **無模型 profile 時的回退預設值（Fallback）**：當模型 profile 不可用時，回退為在 **170,000 tokens** 時觸發，並保留最近 **6 則訊息（6 messages kept）**。
  - **`ContextOverflowError` 緊急回退**：若任何模型呼叫引發標準 `ContextOverflowError`，Deep Agents 會立即回退執行摘要，並以「摘要 + 保留的近期訊息」自動重試。
  - **使用較便宜模型摘要（Python 需 `deepagents>=0.7.26`）**：覆寫 `SummarizationMiddleware` 時可傳入 `summarizer=` 指定另一模型或自訂 callable（主 `model` 仍負責提供 profile 與計算 token）。
- **過濾串流中的摘要 Tokens**：
  - 當使用 `stream_mode="messages"` / `streamMode: "messages"` 串流時，輸出預設會包含摘要步驟產生的 tokens；可透過檢查 metadata 中的 `metadata.get("lc_source") == "summarization"`（Python）或 `metadata?.lcSource === "summarization"`（JS）將其過濾忽略。
- **按需壓縮工具 `compact_conversation`（On-demand compaction tool，僅 Python）**：
  - 若希望代理能在任務轉換之間等適當時機主動觸發對話壓縮（而不必等到 85% 閾值），可將 `create_summarization_tool_middleware(model, backend)`（對應 `SummarizationToolMiddleware`）傳入 `create_deep_agent` 的 `middleware` 參數。
  - 這會為代理新增 `compact_conversation` 工具（插入於 `PatchToolCallsMiddleware` 之後），且**不會停用**原本在 85% 上下文上限觸發的自動摘要，兩者共用相同的摘要引擎與狀態。

## 相關頁面
- [[concepts/deepagents-overview]]
- [[guides/deepagents-customization]]
- [[concepts/deepagents-memory-and-skills]]
- [[concepts/deepagents-subagents]]
- [[concepts/deepagents-backends-and-sandboxes]]
- [[concepts/deepagents-streaming-and-fault-tolerance]]

## 出處
- docs/deepagents/context-engineering.md
