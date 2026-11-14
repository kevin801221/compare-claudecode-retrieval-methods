# LangChain Multi-Agent Router and Skills Patterns

別名：路由器與技能模式、Router Pattern、Skills Pattern、Progressive Disclosure、漸進式揭露、Send API 平行路由
框架：langchain

## 摘要
**Router（路由器）** 與 **Skills（技能）** 是兩種互補的多領域知識管理架構：**Router** 透過專用分類步驟將輸入拆解為針對不同垂直領域（Verticals）的子問題，利用 LangGraph `Command`（單一代理）或 `Send` API（多代理平行扇出）分發至獨立代理，並透過狀態 Reducer 收集結果後綜合（Synthesize）為單一答案；**Skills** 則採用漸進式揭露（Progressive disclosure），讓單一代理在系統提示詞中僅看見輕量級技能描述，並在需要時透過 `load_skill` 工具按需載入完整的資料庫 Schema、業務邏輯或參考資源。

## 重點
- **Router 模式（Router Architecture）核心機制**：
  - **三階段流程**：**Decompose / Classify**（分析查詢並產生針對各知識源的子問題）→ **Route**（透過 `Command` 路由至單一代理，或透過 `Send` 平行扇出至 0 個或多個專業代理）→ **Synthesize**（等待所有平行分支完成後，將結果無冗餘地合併為連貫回答並標註來源差異）。
  - **Single-agent vs. Multi-agent 平行路由**：
    - 單一代理：路由函式回傳 `Command(goto=active_agent)`（Python）或 `new Command({ goto: classification.agent })`（TypeScript）。
    - 多重代理平行扇出：路由函式回傳 `[Send(c["agent"], {"query": c["query"]}) for c in classifications]`（Python）或 `classifications.map((c) => new Send(c.agent, { query: c.query }))`（TypeScript）。
  - **Stateless vs. Stateful Routers**：
    - **Stateless（無狀態，預設）**：每次請求獨立路由，不保留跨呼叫記憶。
    - **Stateful（有狀態，多輪對話）**：
      - **Tool wrapper（工具包裝法，推薦首選）**：將無狀態 Router `workflow.invoke({"query": query})` 包裝為工具（如 `search_docs` 或 `search_knowledge_base`），交由掛載 `checkpointer=InMemorySaver()`（TypeScript 為 `new MemorySaver()`）的 `conversational_agent` 呼叫，由對話代理負責記憶與上下文。
      - **Full persistence（完整持久化）**：直接在 Router 層級儲存訊息歷史，但跨輪切換不同語氣／提示詞的代理容易導致對話不連貫，官方建議多輪對話優先改用 Handoffs 或 Subagents。
- **Multi-Source Knowledge Base Router 實戰教學（GitHub + Notion + Slack）**：
  - **狀態 Schema 設計**：
    - `AgentInput`：傳給各子代理的精簡狀態 `{"query": str}`（不傳入完整 `RouterState`）。
    - `AgentOutput`：子代理回傳格式 `{"source": str, "result": str}`。
    - `Classification`：單一路由決策 `{"source": Literal["github", "notion", "slack"], "query": str}`。
    - `RouterState`：
      - Python：`query: str`、`classifications: list[Classification]`、`results: Annotated[list[AgentOutput], operator.add]`（使用 `operator.add` reducer 收集平行結果）、`final_answer: str`。
      - TypeScript：`new StateSchema({ query: z.string(), classifications: z.array(z.object({ source: z.enum(["github", "notion", "slack"]), query: z.string() })), results: new ReducedValue(z.array(AgentOutput).default(() => []), { reducer: (current, update) => current.concat(update) }), finalAnswer: z.string() })`。
  - **三大垂直領域工具與代理（模型使用 `openai:gpt-6.1-sol`）**：
    - `github_agent`：工具為 `search_code(query: str, repo: str = "main")`、`search_issues(query: str)`、`search_prs(query: str)`。
    - `notion_agent`：工具為 `search_notion(query: str)`、`get_page(page_id: str)`。
    - `slack_agent`：工具為 `search_slack(query: str)`、`get_thread(thread_id: str)`。
  - **工作流節點與編譯（分類與綜合模型使用 `openai:gpt-5.4-mini`）**：
    - `classify_query`：使用 `router_llm.with_structured_output(ClassificationResult)`（TypeScript 為 `routerLlm.withStructuredOutput(ClassificationResultSchema)`）僅回傳與查詢相關的知識源及客製化子問題（不相關的來源直接省略）。
    - `route_to_agents`：透過 `add_conditional_edges("classify", route_to_agents, ["github", "notion", "slack"])` 將每個分類映射為 `Send(c["source"], {"query": c["query"]})`。
    - `query_github` / `query_notion` / `query_slack`：調用對應代理並回傳 `{"results": [{"source": "...", "result": result["messages"][-1].content}]}`。
    - `synthesize_results`：若 `state["results"]` 為空則回傳 `"No results found from any knowledge source."`，否則將所有結果格式化為 `**From {Source}:**\n{result}` 後交由 `router_llm` 綜合出 `final_answer`。
- **Skills 模式（Skills Architecture）與漸進式揭露（Progressive Disclosure）**：
  - **概念與演進**：概念同於 Agent Skills、Jeremy Howard 提出的 `llms.txt`、Anthropic 的三層式架構（metadata → core content → detailed resources）以及 Claude Code 的檔案系統技能目錄。可視為一種以工具瀏覽／直接查找作為檢索單元的 RAG。
  - **五大特徵**：Prompt-driven specialization（以專業提示詞定義）、Progressive disclosure（依需求載入）、Team distribution（跨團隊獨立維護）、Lightweight composition（比完整子代理更輕量，單一代理維持單一對話執行緒）、Reference awareness（提示詞可指向腳本、範本或其他檔案資產位置，讓代理在需要時才讀入記憶體）。
  - **進階擴充模式**：
    - **Dynamic tool registration（動態工具註冊）**：結合狀態管理，在載入特定技能（如 `"database_admin"`）時一併解鎖或註冊專屬工具（如 backup、restore、migrate）。
    - **Hierarchical skills（階層式技能）**：技能呈樹狀結構（如載入 `"data_science"` 後揭露子技能 `"pandas_expert"`、`"visualization"`、`"statistical_analysis"`）。
  - **實作變體與技能大小準則（Size considerations）**：
    - **Storage backends**：In-memory（記憶體資料結構，最快但更新需重新部署）、File system（目錄與檔案，透過 `read_file` 探索）、Remote storage（S3、資料庫、Notion 或 API）。
    - **Skill discovery**：System prompt listing、File-based、Registry-based、Dynamic lookup。
    - **Loading strategies**：Single load（單次工具呼叫載入完整內容）、Paginated（分頁載入）、Search-based（grep/read 搜尋特定段落）、Hierarchical（先載入總覽再深入子章節）。
    - **Token 大小經驗法則**：**Small skills**（`< 1K` tokens／約 750 字）可直接放入系統提示詞並搭配 Prompt caching；**Medium skills**（`1-10K` tokens／約 750–7.5K 字）適合使用單次按需載入（本教學做法）；**Large skills**（`> 10K` tokens／約 7.5K 字，或佔上下文視窗 `> 5-10%`）應採用分頁、搜尋或階層式探索。亦可結合動態 Few-shot prompting 按需載入 2-3 個相關範例查詢。
- **SQL Assistant 實戰教學（按需載入 Schema 與強制工具順序限制）**：
  - **資料結構（`Skill`）**：包含 `name: str`、`description: str`（1-2 句簡短描述，注入系統提示詞）、`content: str`（完整資料表 Schema、Business Logic 與 Example Query；TypeScript 使用 `import { context } from "langchain"` 模板字串定義）。教學定義了 `"sales_analytics"`（含 `customers`、`orders`、`order_items` 表）與 `"inventory_management"`（含 `products`、`warehouses`、`inventory`、`stock_movements` 表）。
  - **載入工具（`load_skill`）**：比對 `skill_name`，找到時回傳 `f"Loaded skill: {skill_name}\n\n{skill['content']}"`；找不到時回傳 `f"Skill '{skill_name}' not found. Available skills: {available}"`。
  - **自訂中介軟體（`SkillMiddleware` / `skillMiddleware`）**：
    - Python：繼承 `AgentMiddleware`，定義類別變數 `tools = [load_skill]`，在 `__init__` 組裝 `- **{skill['name']}**: {skill['description']}` 清單（正式環境建議改在 `before_agent` hook 載入以支援動態刷新），並於 `wrap_model_call` 將 `\n\n## Available Skills\n\n...` 附加至 `request.system_message.content_blocks` 後呼叫 `request.override(system_message=new_system_message)`。
    - TypeScript：使用 `createMiddleware({ name: "skillMiddleware", tools: [loadSkill], wrapModelCall: async (request, handler) => handler({ ...request, systemPrompt: request.systemPrompt + skillsAddendum }) })`。
  - **搭配自訂狀態強制執行工具約束（Enforce tool constraints）**：
    - 定義狀態：Python 為 `class CustomState(AgentState): skills_loaded: NotRequired[list[str]]`；TypeScript 為 `const CustomState = new StateSchema({ skillsLoaded: z.array(z.string()).optional() })`。
    - 修改 `load_skill` 回傳 `Command(update={"messages": [ToolMessage(content=skill_content, tool_call_id=runtime.tool_call_id)], "skills_loaded": [skill_name]})`（TypeScript 更新 `skillsLoaded: [skillName]`）。
    - 建立受限工具 `write_sql_query(query: str, vertical: str, runtime: ToolRuntime) -> str`：檢查 `vertical not in runtime.state.get("skills_loaded", [])`（TypeScript 為 `!skillsLoaded.includes(vertical)`），若尚未載入對應技能則回傳錯誤訊息 `"Error: You must load the '{vertical}' skill first to understand the database schema before writing queries. Use load_skill('{vertical}') to load the schema."`，並於 `SkillMiddleware(AgentMiddleware[CustomState])` 設定 `state_schema = CustomState` 與 `tools = [load_skill, write_sql_query]`。

## 相關頁面
- [[concepts/langchain-multi-agent-overview]]
- [[concepts/langchain-multi-agent-subagents]]
- [[concepts/langchain-multi-agent-handoffs]]

## 出處
- docs/langchain/multi-agent/router.md
- docs/langchain/multi-agent/router-knowledge-base.md
- docs/langchain/multi-agent/skills.md
- docs/langchain/multi-agent/skills-sql-assistant.md
