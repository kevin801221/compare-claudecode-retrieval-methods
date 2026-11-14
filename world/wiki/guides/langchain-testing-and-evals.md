# LangChain Agent Testing and Evaluations

別名：代理測試與評估指南、Unit Testing、Integration Testing、AgentEvals、Trajectory Evaluation、VCR HTTP 錄製重播
框架：langchain

## 摘要
LangChain 代理應用程式的測試策略分為三個層次：**Unit tests（單元測試）** 使用記憶體內假模型（Python 的 `GenericFakeChatModel`、`FakeListChatModel`；TypeScript 的 `fakeModel`）與 `InMemorySaver` 在無 API 呼叫下確定性地驗證邏輯；**Integration tests（整合測試）** 透過真實網路呼叫驗證元件整合、憑證與回應結構（搭配 Vitest `langchainMatchers` 或 `vcrpy`／`pytest-recording` 錄製重播）；**Evals（評估）** 則使用 `agentevals` 套件與 LangSmith，透過確定性軌跡比對（`strict`、`unordered`、`subset`、`superset`）或 LLM-as-judge 評估代理的執行軌跡（Trajectory）。

## 重點
- **三大測試層次總覽（Test Overview）**：
  - **Unit tests**：使用記憶體內假物件（In-memory fakes）隔離測試小型、確定性的代理邏輯，快速、免費且不需 API 金鑰。
  - **Integration tests**：發起真實網路呼叫，確認元件協同運作、憑證與 Schema 對齊且延遲可接受。
  - **Evals**：利用評估器（Evaluators）對代理的執行軌跡（訊息與工具呼叫序列）進行確定性比對或 LLM 裁判評分，適合在變更提示詞、工具或模型時捕捉退化（Regressions）。
- **單元測試（Unit Testing）——Python**：
  - **`GenericFakeChatModel`**（來自 `langchain_core.language_models.fake_chat_models`）：接收 `AIMessage` 或字串的迭代器 `messages=iter([...])`，每次調用依序回傳一個項目，支援一般與串流用法。
    - 由於 `GenericFakeChatModel` 未實作 `create_agent` 傳入工具時會呼叫的 `bind_tools`，測試工具呼叫迴圈時需繼承並覆寫：`class FakeToolCallingModel(GenericFakeChatModel): def bind_tools(self, tools, **kwargs): return self`。
    - 搭配 `@pytest.fixture` 共用時，必須維持預設的 `function` scope（不可用 `module` 或 `session` scope，否則迭代器耗盡後後續測試會失敗）。
  - **`FakeListChatModel`**（來自 `langchain_core.language_models`）：接收字串清單 `responses=["Paris", "The Eiffel Tower"]`，僅需純文字回應時不必建構 `AIMessage`；當調用次數超過清單長度時會自動從頭循環。
  - **持久化多輪測試**：使用 `from langgraph.checkpoint.memory import InMemorySaver` 並在 `create_agent(..., checkpointer=InMemorySaver())` 搭配 `config={"configurable": {"thread_id": "session-1"}}` 模擬多輪狀態互動。
- **單元測試（Unit Testing）——TypeScript / JavaScript（`fakeModel`）**：
  - `import { fakeModel } from "langchain"`：建構器風格（Builder-style）的假模型，繼承自 `BaseChatModel`。
  - **佇列回應與工具呼叫**：
    - `.respond(new AIMessage("..."))`：依序排入每次 `invoke()` 消耗的回應；若調用次數超過佇列長度，會拋出 `"no response queued for invocation N"`。
    - `.respondWithTools([{ name: "get_weather", args: { city: "SF" }, id: "call_1" }])`：排入工具呼叫回應的簡寫法（`id` 為選填，省略時自動產生唯一 ID），可與 `.respond()` 自由混用。
  - **模擬錯誤與動態工廠函式**：
    - 特定輪次拋錯：`.respond(new Error("rate limit exceeded"))`。
    - 每次呼叫皆拋錯：`.alwaysThrow(new Error("service unavailable"))`。
    - 動態回應：`.respond((messages) => { const last = messages[messages.length - 1].text; return new AIMessage(...); })`（亦可回傳 `new Error(...)`；每個函式僅消耗一次）。
  - **結構化輸出與呼叫斷言（Spy / Mock）**：
    - `.structuredResponse({ temperature: 72, unit: "fahrenheit" })`：設定 `.withStructuredOutput(...)` 的固定回傳值（忽略傳入的 Zod schema）。
    - 呼叫紀錄：透過 `model.callCount` 與 `model.calls[i].messages` 斷言模型收到的輸入（即使拋出錯誤也會記錄）。
    - 自動支援 `model.bindTools(tools)`：綁定後的模型與原模型共用相同的回應佇列與呼叫紀錄。
- **整合測試（Integration Testing）**：
  - **分離單元與整合測試**：
    - Python：使用 `@pytest.mark.integration` 標記，並在 `pytest.ini` 或 `pyproject.toml` 設定 `addopts = -m "not integration"`，執行時明確下達 `pytest -m integration`。
    - TypeScript：命名為 `*.int.test.ts`，在 `vitest.config.ts` 判斷 `env.mode === "int"`（設定 `testTimeout: 100_000`、`include: ["**/*.int.test.ts"]`、`setupFiles: ["dotenv/config"]`；預設模式 `testTimeout: 30_000` 並排除 `**/*.int.test.ts`），執行 `npm run test:integration`（`vitest --mode int`）。
  - **API 金鑰管理**：從 `.env` 載入（Python 用 `python-dotenv` 的 `load_dotenv()` 與 `conftest.py` `@pytest.fixture(autouse=True)` 檢查 `os.environ.get("OPENAI_API_KEY")` 否則 `pytest.skip(...)`；TypeScript 用 `setupFiles: ["dotenv/config"]` 與 `test.skipIf(!process.env.OPENAI_API_KEY)`）。
  - **針對結構而非內容進行斷言（Assert on structure, not content）**：檢查訊息型別、工具呼叫名稱、參數結構與訊息數量。
  - **TypeScript 自訂 Vitest Matchers（`@langchain/core/testing`）**：
    - 在 `vitest.setup.ts` 執行 `import { langchainMatchers } from "@langchain/core/testing"; expect.extend(langchainMatchers);`。
    - 10 個內建 Matchers：
      1. `toBeHumanMessage(expected?)`：檢查是否為 `HumanMessage`（可選比對字串內容或物件欄位）。
      2. `toBeAIMessage(expected?)`：檢查是否為 `AIMessage`（如 `expect(lastMessage).toBeAIMessage({ name: "weather-bot" })`）。
      3. `toBeSystemMessage(expected?)`：檢查是否為 `SystemMessage`。
      4. `toBeToolMessage(expected?)`：檢查是否為 `ToolMessage`（如比對 `{ tool_call_id: "call_1" }`）。
      5. `toHaveToolCalls(expected)`：檢查 `AIMessage` 是否包含指定工具呼叫（不計順序，Order-independent）。
      6. `toHaveToolCallCount(n)`：檢查 `AIMessage` 的工具呼叫數量是否恰好為 `n`。
      7. `toContainToolCall(expected)`：檢查 `AIMessage` 是否至少包含一個相符的工具呼叫（支援 `.not`）。
      8. `toHaveToolMessages(expected)`：檢查訊息陣列是否依序包含指定的 `ToolMessage` 實例。
      9. `toHaveBeenInterrupted(value?)`：檢查結果是否含有 LangGraph `__interrupt__` 欄位及選填 payload 值。
      10. `toHaveStructuredResponse(expected?)`：檢查結果是否含有 `structuredResponse` 欄位及選填屬性。
  - **降低成本與延遲 + HTTP 錄製重播（VCR）**：
    - 使用較小模型（如 `gemini-3.1-flash-lite`）、限制輸出 토큰 數、縮小測試範圍。
    - Python 可使用 `vcrpy` 與 `pytest-recording`：在 `conftest.py` 定義 `@pytest.fixture(scope="session") def vcr_config():` 過濾 `filter_headers`（`authorization`、`x-api-key`）與 `filter_query_parameters`（`api_key`、`key`），設定 `addopts = --record-mode=once`，並在測試加上 `@pytest.mark.vcr()`，首次執行會將 HTTP 互動錄製至 `tests/cassettes/` 的 YAML 檔案，後續執行直接重播（若修改提示詞或工具則必須刪除舊 cassette 重新錄製）。
- **代理軌跡評估（Agent Evals with `agentevals` & LangSmith）**：
  - 安裝：`pip install -U agentevals` / `uv add agentevals`（Python）或 `npm install agentevals @langchain/core`（TypeScript）。
  - **1. 軌跡比對評估器（Trajectory Match Evaluator）**：
    - Python：`from agentevals.trajectory.match import create_trajectory_match_evaluator`（非同步版為 `create_async_trajectory_match_evaluator`），參數為 `trajectory_match_mode`。
    - TypeScript：`import { createTrajectoryMatchEvaluator } from "agentevals"`，參數為 `trajectoryMatchMode`。
    - **四種比對模式（Modes）**：
      - `"strict"`：訊息結構與工具呼叫順序必須完全一致（訊息文字內容可不同），適合強制特定操作順序（如授權前必須先查政策）。評估結果回傳 `{'key': 'trajectory_strict_match', 'score': True, 'comment': None}`。
      - `"unordered"`：包含相同的訊息結構與工具呼叫，但工具呼叫順序不限（如同時查詢城市天氣與活動）。
      - `"subset"`：代理僅呼叫參考軌跡中的工具（不可呼叫額外工具），確保不超出預期範圍。
      - `"superset"`：代理至少呼叫了參考軌跡中的工具（允許額外工具呼叫），驗證最低必要動作。
    - 參數比對客製化：可透過 `tool_args_match_mode` / `tool_args_match_overrides`（Python）或 `toolArgsMatchMode` / `toolArgsMatchOverrides`（TypeScript）自訂工具參數相等性判定（預設要求相同工具且相同參數）。
  - **2. LLM 裁判評估器（LLM-as-Judge Evaluator）**：
    - Python：`from agentevals.trajectory.llm import create_trajectory_llm_as_judge, TRAJECTORY_ACCURACY_PROMPT, TRAJECTORY_ACCURACY_PROMPT_WITH_REFERENCE`（非同步版為 `create_async_trajectory_llm_as_judge`）。
    - TypeScript：`import { createTrajectoryLLMAsJudge, TRAJECTORY_ACCURACY_PROMPT, TRAJECTORY_ACCURACY_PROMPT_WITH_REFERENCE } from "agentevals"`。
    - 無參考軌跡時使用 `prompt=TRAJECTORY_ACCURACY_PROMPT` 並傳入 `outputs=result["messages"]`；有參考軌跡時使用 `prompt=TRAJECTORY_ACCURACY_PROMPT_WITH_REFERENCE` 並額外傳入 `reference_outputs=reference_trajectory`（TypeScript 為 `referenceOutputs`）。模型範例為 `model="openai:gpt-5.4-mini"`。
  - **在 LangSmith 中執行評估**：
    - 需設定環境變數 `LANGSMITH_API_KEY` 與 `LANGSMITH_TRACING="true"`。
    - **Test Runner 整合**：Python 使用 `from langsmith import testing as t` 與 `@pytest.mark.langsmith`，呼叫 `t.log_inputs({})`、`t.log_outputs(...)`、`t.log_reference_outputs(...)` 並以 `pytest test_trajectory.py --langsmith-output` 執行；TypeScript 使用 `import * as ls from "langsmith/vitest"`（或 `"langsmith/jest"`），透過 `ls.describe`、`ls.test`、`ls.logOutputs` 並以 `vitest run test_trajectory.eval.ts` 執行。
    - **`evaluate` 函式搭配 LangSmith Dataset**（Dataset schema 須包含 `input: {"messages": [...]}` 與 `output: {"messages": [...]}`）：Python 使用 `from langsmith import Client; client.evaluate(run_agent, data="your_dataset_name", evaluators=[trajectory_evaluator])`；TypeScript 使用 `import { evaluate } from "langsmith/evaluation"; await evaluate(runAgent, { data: "your_dataset_name", evaluators: [trajectoryEvaluator] })`。

## 相關頁面
- [[guides/langchain-observability-and-deployment]]
- [[concepts/langchain-multi-agent-overview]]

## 出處
- docs/langchain/test/index.md
- docs/langchain/test/unit-testing.md
- docs/langchain/test/integration-testing.md
- docs/langchain/test/evals.md
