# LangChain Multi-Agent Overview and Custom Workflows

別名：多代理架構總覽與自訂工作流、Multi-Agent Patterns、Custom Workflow、StateGraph 多代理編排、Multi-agent Architecture
框架：langchain

## 摘要
LangChain 的多代理（Multi-agent）系統透過協調多個專業化元件來處理複雜的工作流程，核心目的在於解決上下文管理（Context management）、分散式開發（Distributed development）與平行化執行（Parallelization）三大需求。系統提供五大主要架構模式：**Subagents**（主代理將子代理作為工具調用）、**Handoffs**（依狀態變數動態切換代理或調整工具與提示詞）、**Skills**（單一代理按需載入專業提示詞與知識）、**Router**（路由步驟分類輸入並分發至專業代理後綜合結果），以及使用 LangGraph `StateGraph` 混合確定性邏輯與代理行為的 **Custom workflow**。

## 重點
- **為何需要多代理（Why multi-agent）**：
  - **Context management（上下文管理）**：提供專業知識而不塞爆模型的上下文視窗（Context window），透過模式選擇性地浮現相關資訊。當上下文工程（Context engineering）決定每個代理看見哪些資訊時，系統品質取決於確保各代理能存取其任務所需的正確資料。
  - **Distributed development（分散式開發）**：允許不同團隊獨立開發與維護能力，並以清晰邊界組合成更大的系統。
  - **Parallelization（平行化）**：為子任務衍生專業工作者（Workers）並同時執行以加快結果。
  - 適用時機：單一代理擁有過多工具（Tools）導致決策品質下降、任務需要大量上下文的專業知識（長提示詞與領域專用工具），或需要強制執行「滿足特定條件後才解鎖能力」的序列限制。
  - 內建高階支援：可使用 Managed Deep Agents（內建 subagents、skills、planning、virtual filesystem 與 context management 的託管環境），或自行託管 Deep Agents／執行自訂 Agent Server。
- **五大核心模式（Patterns）**：
  - **Subagents**：由主代理（Main agent）將子代理當作工具協調；所有路由皆經過主代理，由主代理決定何時與如何調用各子代理。
  - **Handoffs**：行為隨狀態（State）動態改變；工具呼叫會更新狀態變數，進而觸發路由或組態變更，切換代理或調整當前代理的工具與提示詞。
  - **Skills**：按需載入專業提示詞與知識；單一代理保持控制權，並視需要從 skills 載入上下文。
  - **Router**：路由步驟對輸入進行分類，並將其導向一個或多個專業代理，最後將結果綜合（Synthesize）為合併回應。
  - **Custom workflow**：使用 LangGraph 建構客製化執行流程，混合確定性邏輯（Deterministic logic）與代理行為（Agentic behavior），並可將其他模式作為節點嵌入工作流中。
  - 模式可自由混用：例如 Subagents 架構可調用觸發 Custom workflows 或 Router agents 的工具，子代理本身也可使用 Skills 模式按需載入上下文。
- **模式能力評估比較（Choosing a pattern）**：
  - **Subagents**：Distributed development ⭐⭐⭐⭐⭐、Parallelization ⭐⭐⭐⭐⭐、Multi-hop（串聯呼叫多個子代理）⭐⭐⭐⭐⭐、Direct user interaction（與使用者直接對話）⭐。
  - **Handoffs**：Distributed development `-`、Parallelization `-`、Multi-hop ⭐⭐⭐⭐⭐、Direct user interaction ⭐⭐⭐⭐⭐。
  - **Skills**：Distributed development ⭐⭐⭐⭐⭐、Parallelization ⭐⭐⭐、Multi-hop ⭐⭐⭐⭐⭐、Direct user interaction ⭐⭐⭐⭐⭐。
  - **Router**：Distributed development ⭐⭐⭐、Parallelization ⭐⭐⭐⭐⭐、Multi-hop `-`、Direct user interaction ⭐⭐⭐。
- **效能與成本比較（Performance comparison）**：
  - 關鍵指標為 **Model calls**（LLM 調用次數，越多代表延遲越高與 API 成本越高）與 **Tokens processed**（所有呼叫的總上下文視窗使用量）。
  - **場景一：One-shot request（單次請求，例如 `"Buy coffee"`，呼叫 `buy_coffee` 工具）**：
    - **Subagents**：`4` 次模型呼叫（結果需流回主代理，多出 1 次呼叫以換取集中控制）。
    - **Handoffs**：`3` 次模型呼叫（最佳契合 ✅）。
    - **Skills**：`3` 次模型呼叫（最佳契合 ✅）。
    - **Router**：`3` 次模型呼叫（最佳契合 ✅）。
  - **場景二：Repeat request（重複請求，Turn 1 `"Buy coffee"`、Turn 2 `"Buy coffee again"`）**：
    - **Subagents**：Turn 2 為 `4` 次呼叫，兩輪總計 `8` 次（`4+4`）。因設計上為無狀態（Stateless by design），每次調用子代理皆從頭開始，提供強上下文隔離但重複完整流程。
    - **Handoffs**：Turn 2 為 `2` 次呼叫，兩輪總計 `5` 次（`3+2`，最佳契合 ✅）。Coffee agent 從第 1 輪保持活躍（狀態持續），省去 handoff 直接呼叫 `buy_coffee`（第 1 呼）並回應使用者（第 2 呼），節省 1 次呼叫。
    - **Skills**：Turn 2 為 `2` 次呼叫，兩輪總計 `5` 次（`3+2`，最佳契合 ✅）。Skill 上下文已載入於對話歷史中，無需重新載入，直接呼叫 `buy_coffee`（第 1 呼）並回應（第 2 呼），節省 1 次呼叫。
    - **Router**：Turn 2 為 `3` 次呼叫，兩輪總計 `6` 次（`3+3`）。Router 為無狀態，每次請求皆需 1 次 LLM 路由呼叫，但可透過包裝成有狀態代理中的工具來最佳化。
    - 關鍵洞見：有狀態模式（Handoffs、Skills）在重複請求上可節省 40-50% 的呼叫次數。
  - **場景三：Multi-domain（跨領域請求，例如 `"Compare Python, JavaScript, and Rust for web development"`，每個語言代理／技能含約 2000 tokens 文件）**：
    - **Subagents**：`5` 次模型呼叫、總計 `~9K` tokens（最佳契合 ✅）。平行執行，每個子代理在隔離環境中僅處理相關上下文，比 Skills 少處理 67% tokens。
    - **Handoffs**：`7+` 次模型呼叫、總計 `~14K+` tokens。必須循序執行（Sequential），無法平行研究三種語言，且不斷增長的對話歷史會增加額外負擔。
    - **Skills**：`3` 次模型呼叫、總計 `~15K` tokens。載入後，後續每次呼叫都必須處理全部 6K tokens 的技能文件（上下文累積）。
    - **Router**：`5` 次模型呼叫、總計 `~9K` tokens（最佳契合 ✅）。使用 LLM 進行明確路由步驟後平行調用各代理。
  - **最佳化目標對照表（Optimize for）**：
    - Single requests：Handoffs、Skills、Router。
    - Repeat requests：Handoffs、Skills。
    - Parallel execution：Subagents、Router。
    - Large-context domains：Subagents、Router。
    - Simple, focused tasks：Skills。
- **自訂工作流（Custom workflow）實作細節**：
  - 使用 LangGraph 的 `StateGraph`、`START`、`END` 定義完全受控的圖結構，支援循序步驟（Sequential steps）、條件分支（Conditional branches）、迴圈（Loops）與平行執行（Parallel execution）。
  - **基本代理節點包裝**：
    - Python：由 `from langchain.agents import create_agent` 與 `from langgraph.graph import StateGraph, START, END` 建立 `agent = create_agent(model="openai:gpt-6.1-sol", tools=[...])`，在節點函式 `def agent_node(state: State) -> dict:` 中呼叫 `result = agent.invoke({"messages": [{"role": "user", "content": state["query"]}]})` 並回傳 `{"answer": result["messages"][-1].content}`，接著透過 `StateGraph(State).add_node("agent", agent_node).add_edge(START, "agent").add_edge("agent", END).compile()` 編譯。
    - TypeScript：由 `import { createAgent } from "langchain"` 與 `import { StateGraph, START, END, StateSchema, MessagesValue } from "@langchain/langgraph"` 建立 `AgentState = new StateSchema({ messages: MessagesValue, query: z.string() })` 與 `agentNode: GraphNode<typeof AgentState>`，呼叫 `await agent.invoke(...)` 後回傳 `{ answer: result.messages.at(-1)?.content }`，再用 `.addNode("agent", agentNode).addEdge(START, "agent").addEdge("agent", END).compile()` 編譯。
  - **Custom RAG Pipeline 範例（WNBA 統計助手）**：
    - 展示三種節點類型：**Model node（`rewrite`）**使用結構化輸出改寫查詢、**Deterministic node（`retrieve`）**執行向量相似度搜尋（無 LLM 參與）、**Agent node（`agent`）**對檢索到的上下文進行推理並可透過工具 `get_latest_news` 抓取最新消息。
    - 狀態定義：Python 為 `class State(TypedDict): question: str; rewritten_query: str; documents: list[str]; answer: str`；TypeScript 為 `Annotation.Root({ question: Annotation<string>(), rewrittenQuery: Annotation<string>(), documents: Annotation<string[]>(), answer: Annotation<string>() })`。
    - 向量庫與檢索器：Python 使用 `OpenAIEmbeddings()` 與 `InMemoryVectorStore(embeddings)`、`vector_store.as_retriever(search_kwargs={"k": 5})`（正式環境建議改用 Valkey、Databricks Vector Search 或 MongoDB Atlas）；TypeScript 使用 `MemoryVectorStore.fromTexts(..., embeddings)` from `"@langchain/classic/vectorstores/memory"` 與 `vectorStore.asRetriever({ k: 5 })`（正式環境建議改用 Weaviate、Pinecone 或 MongoDB Atlas）。
    - 節點串接：`START -> "rewrite" -> "retrieve" -> "agent" -> END`。在 `call_agent` / `callAgent` 中，最終回答透過 `response["messages"][-1].content_blocks`（Python）或 `response.messages.at(-1)?.contentBlocks`（TypeScript）提取。

## 相關頁面
- [[concepts/langchain-multi-agent-subagents]]
- [[concepts/langchain-multi-agent-handoffs]]
- [[concepts/langchain-multi-agent-router-and-skills]]
- [[guides/langchain-observability-and-deployment]]

## 出處
- docs/langchain/multi-agent/index.md
- docs/langchain/multi-agent/custom-workflow.md
