# Deep Agents Profiles, Multimodality, Grading Rubrics, and Interpreters

別名：Harness Profiles、Provider Profiles、多模態輸入輸出、Multimodal、評分準則、RubricMiddleware、LLM-as-a-judge、程式碼直譯器、Interpreters、QuickJS、Programmatic Tool Calling、PTC
框架：deepagents

## 摘要
本頁彙整 Deep Agents 的四大進階執行期與配置機制：**Profiles**（透過 `HarnessProfile` / `HarnessProfileOptions` 與 Python 專屬的 `ProviderProfile` 封裝針對特定模型或供應商的提示詞、工具與 Middleware 預設值）、**Multimodality**（透過標準內容區塊與內建 `read_file` 工具處理圖片、音訊、影片與文件，以及上下文壓縮對多模態內容的影響）、**Grading Rubrics**（透過 `RubricMiddleware` 在執行期實作 LLM-as-a-judge 自我評估與迭代修正迴圈），以及 **Interpreters**（基於 WebAssembly 隔離的 QuickJS 記憶體內 JavaScript 執行環境 `eval`，支援 Programmatic Tool Calling (PTC) 與動態子代理 `task()` 調度）。

## 重點

### 1. Profiles（Harness Profiles 與 Provider Profiles）
- **架構定位（Beta）**：
  - **Harness profiles**：針對特定模型（`provider:model`）或供應商（`provider`）自訂 Deep Agents harness（調整系統提示詞、覆寫工具描述、排除工具或 middleware、新增 middleware、配置通用子代理）。在選擇匹配模型時由 `create_deep_agent`（Python）或 `createDeepAgent`（TS）自動套用。
  - **Provider profiles（僅 Python）**：透過 `ProviderProfile` 定義建立模型時的預設參數（如 `temperature`、`timeout`），僅在傳入 `provider:model` 字串給 `create_deep_agent` 時生效，不影響 harness。TypeScript SDK 僅支援 harness profiles。
- **`HarnessProfile`（Python）與 `HarnessProfileOptions`（TypeScript）欄位對照**：
  - `base_system_prompt` (`string`) / `baseSystemPrompt` (`string`)：設定 profile 的基礎指令。對主代理（main agent）而言，會接在呼叫端傳入的系統指令之後（預設不附加基礎指令）；對宣告式子代理（declarative subagents）則會取代其原有的 system prompt。
  - `system_prompt_suffix` (`string`) / `systemPromptSuffix` (`string`)：附加在呼叫端指令與 `base_system_prompt` 之後的文字，同時套用於主代理、宣告式子代理與自動新增的通用子代理（general-purpose subagent）。呼叫端的 `system_prompt=` / `systemPrompt` 永遠位於最前端，而 suffix 永遠位於最末端；每個子代理也會針對其自身的模型重新執行 profile 解析。
  - `tool_description_overrides` (`Mapping[str, str]`) / `toolDescriptionOverrides` (`Record<string, string>`)：以工具名稱為 key 覆寫個別工具的描述。
  - `excluded_tools` (`frozenset[str]`) / `excludedTools` (`string[]`)：以工具名稱字串匹配的注入後過濾器（post-injection filter），可同時移除使用者傳入與 harness middleware 新增的工具。
  - `excluded_middleware` (`frozenset[type[AgentMiddleware] | str]`) / `excludedMiddleware` (`string[]`)：從 Deep Agents 堆疊中移除特定 middleware。Python 接受 middleware 類別、匹配 `AgentMiddleware.name` 的純字串（如 `"SummarizationMiddleware"`），或 `module:Class` 匯入參照（如 `"my_pkg.middleware:TelemetryMiddleware"`，採用延遲載入，僅限受信任本機配置）；TS 則比對 `.name` 屬性。**禁止排除必要底層架構**：將 `FilesystemMiddleware`、`SubAgentMiddleware` 或內部 permission middleware 列入會拋出錯誤（Python 拋出 `ValueError`，TS 在建構時 throw）；若僅想對模型隱藏其工具，應改用 `excluded_tools` / `excludedTools`。
  - `extra_middleware` (`Sequence[AgentMiddleware] | Callable[[], Sequence[AgentMiddleware]]`) / `extraMiddleware` (`AgentMiddleware[] | (() => AgentMiddleware[])`)：附加在使用者 middleware 之後的額外 middleware（可為靜態序列或零參數工廠函式）。
  - `general_purpose_subagent` (`GeneralPurposeSubagentProfile`) / `generalPurposeSubagent` (`GeneralPurposeSubagentConfig`，含 `enabled`、`description`、`systemPrompt`)：停用、重新命名或修改通用子代理的提示詞。當此處的 `system_prompt` 與 `base_system_prompt` 同時設定時，以通用子代理專屬的 prompt 優先。若要完全移除 `task` 工具，請設定 `general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)` 且不在 `subagents=` 傳入任何同步子代理（此時 `SubAgentMiddleware` 與 `task` 工具不會被掛載；非同步子代理不受影響）。
- **預先建構模型實例的查找順序（Lookup order）**：
  - Python：1. 精確匹配 `provider:identifier`；2. 僅比對 identifier（僅當 identifier 本身已包含 `:` 時）；3. 回報的 provider 預設值，若 provider 未知則使用 identifier 前綴的預設值（精確匹配優先於 provider 預設值）。
  - TypeScript：1. 若 identifier 無冒號，查找 `provider:identifier` 並退回該 provider 預設值；2. 若含冒號，直接查找並退回前綴預設值；3. 皆無匹配時使用回報的 provider 預設值。
- **註冊鍵值（Registration keys）與合併語意（Merge semantics）**：
  - 支援 **Provider-level**（如 `"openai"`）與 **Model-level**（如 `"openai:gpt-6-astra"`）。在 Python 中僅第一個冒號分隔 provider 與模型 ID（如 `my_provider:my-model:tag` 的模型 ID 為 `my-model:tag`）；TypeScript 不支援模型 ID 內含額外冒號。不提供匹配所有供應商的萬用字元（wildcard key）。
  - 同一鍵值重複註冊或 Model-level 繼承 Provider-level 時採累加合併：
    - `base_system_prompt` / `baseSystemPrompt`、`system_prompt_suffix` / `systemPromptSuffix`：有設定新值時以新值為準，否則繼承。
    - `tool_description_overrides` / `toolDescriptionOverrides`：依 key 合併字典，重複 key 以新值為準。
    - `excluded_tools` / `excludedTools`、`excluded_middleware` / `excludedMiddleware`：集合聯集（Set union）。
    - `extra_middleware` / `extraMiddleware`：Python 依具體型別（concrete type）合併，TS 依名稱（name）合併；同型別/同名的新實例會原位替換舊實例，新項目則附加在後。
    - `general_purpose_subagent` / `generalPurposeSubagent`：逐欄位合併（未設定欄位繼承）。
- **`ProviderProfile` 欄位與合併語意（僅 Python）**：
  - `init_kwargs` (`Mapping[str, Any]`)：轉發給 `init_chat_model` 的靜態初始化參數（依 key 合併，新值優先）。
  - `pre_init` (`Callable[[str], None]`)：建構前執行的副作用函式，如憑證檢查（多個函式會依序串聯執行：舊的先跑，再跑新的）。
  - `init_kwargs_factory` (`Callable[[], dict[str, Any]]`)：從執行期狀態（如環境變數標頭）動態產生 kwargs 的工廠函式（每次建構模型時串聯執行並合併輸出）。
- **設定檔載入與套件外掛註冊**：
  - Python 使用 `HarnessProfileConfig`（提供 `to_dict`、`from_dict` 與 `HarnessProfileConfig.from_harness_profile(...)`）處理 YAML/JSON 序列化，可直接傳給 `register_harness_profile`。若 `extra_middleware` 非空，或 middleware 類別定義於 `__main__` 或函式作用域內，匯出時會拋出 `ValueError`。
  - TypeScript 使用 `parseHarnessProfileConfig` 解析 camelCase 物件並交由 `registerHarnessProfile` 註冊；反向序列化使用 `serializeProfile`（若 `extraMiddleware` 非空會拋出錯誤）。
  - Python 支援透過 `pyproject.toml` 的 `importlib.metadata` entry points（群組 `"deepagents.harness_profiles"` 與 `"deepagents.provider_profiles"`）自動載入外掛，載入順序為：**內建（built-ins）優先 -> entry-point 外掛 -> 使用者程式碼直接呼叫的 `register_*_profile`**。

### 2. Multimodality（多模態輸入與輸出）
- **多模態輸入與內建 `read_file` 工具**：
  - 使用者訊息可透過 LangChain 標準內容區塊（standard content blocks）傳入多模態內容。
  - 內建 `read_file` 工具在讀取支援的多模態檔案時，會直接回傳標準內容區塊而非純文字：
    - **Image**：`.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.heic`、`.heif`
    - **Video**：`.mp4`、`.mpeg`、`.mov`、`.avi`、`.flv`、`.mpg`、`.webm`、`.wmv`、`.3gpp`
    - **Audio**：`.wav`、`.mp3`、`.aiff`、`.aac`、`.ogg`、`.flac`
    - **File**：`.pdf`、`.ppt`、`.pptx`
- **自訂工具多模態輸出**：
  - 自訂工具回傳值會轉為 `ToolMessage`，可透過訊息上的 `content_blocks` 存取正規化表示法。建議將大型二進位產物（如圖片、截圖）存入 backend，並在工具中僅回傳簡短文字描述加上檔案路徑或 URL。
- **上下文壓縮（Context compression）對多模態內容的行為**：
  - **Offloading（卸載）**：僅計算文字 token。非文字區塊（包含圖片）在替換訊息中會被保留而不會被壓縮；僅包含圖片的訊息不會因為圖片大小而被卸載。
  - **Summarization（摘要）**：將較舊的訊息壓縮為純文字摘要。該範圍內的圖片、音訊、影片與檔案區塊**不會**被帶入後續的活動上下文中（模型僅能看到摘要器針對它們寫下的文字描述；低於保留門檻的近期訊息則維持不變，且原始對話仍會以文字形式寫入檔案系統）。針對重度圖片檢視任務，建議委派給 subagents 處理並回傳精簡文字結果。

### 3. Grading Rubrics（`RubricMiddleware`）
- **機制與版本需求**：
  - `RubricMiddleware` 需要 `deepagents>=0.6.5`（Python）。將離線評估常見的 **LLM-as-a-judge** 模式引入執行期：當 Deep Agent 完成推理產生輸出後，由專屬的評分模型（grader sub-agent）根據傳入的 `rubric` 審查對話紀錄（transcript）並回傳判定結果。
- **`RubricMiddleware` 建構參數**：
  - `model`（必填，預設 `None`）：評分模型，接受 `"provider:model-id"` 字串或 `BaseChatModel` 實例（通常選用比主代理更小或更便宜的模型）。
  - `system_prompt`（選填，預設為內建評分提示詞）：自訂評分指令。
  - `tools`（選填，預設 `None`）：供評分器收集證據的工具清單（例如執行測試套件的 `run_test_suite`、計算 token、讀取檔案）；未提供時僅根據 transcript 推理。
  - `max_iterations`（選填，預設 `3`）：單次 rubric 嘗試的最大評分迭代次數（必須為正整數）。
  - `on_evaluation`（選填，預設 `None`）：每次評分迭代結束後呼叫的回呼函式，接收一個 `RubricEvaluation` 字典（回呼內的例外會被記錄並抑制，不可用於拋出例外來中斷代理控制流）。
- **呼叫與五種判定狀態（Rubric verdicts）**：
  - 在呼叫 `invoke()` 或 `stream_events(..., version="v3")`（搭配 `CustomTransformer`）時於輸入狀態傳入 `rubric` 字串啟動迴圈；若輸入狀態未提供 `rubric`，middleware 不會執行。
  - 判定結果（Status）：
    - `satisfied`：所有準則皆通過，結束執行（不迴圈）。
    - `needs_revision`：至少一項準則未通過；若迭代次數小於 `max_iterations`，將逐項回饋（per-criterion feedback）注入對話並讓主代理重新執行。
    - `max_iterations_reached`：評分器仍要求修改但已達 `max_iterations` 上限，結束執行。注意：達到上限時，`on_evaluation` 回呼收到的 `result` 仍為 `"needs_revision"`，而最終狀態 `"max_iterations_reached"` 會記錄在私有狀態 `_rubric_status`（亦可結合 `_rubric_evaluations` 最後一筆與 `_rubric_iterations` 判斷）。
    - `failed`：評分器判定 rubric 格式錯誤或無法根據 transcript 評估，結束執行。
    - `grader_error`：評分器自身發生例外（如供應商逾時、缺少憑證、結構化回應格式錯誤），結束執行（此時 `criteria` 為空陣列）。
- **串流事件與 `RubricEvaluation` 結構**：
  - `stream.custom` 發出的自訂事件：`rubric_evaluation_start`（含 `type`、`grading_run_id`、`iteration`）與 `rubric_evaluation_end`（含 `type`、`grading_run_id`、`iteration`、`result`、`explanation`、`criteria`）。
  - `RubricEvaluation` 字典欄位：`grading_run_id` (`str`)、`iteration` (`int`，從 0 開始)、`result` (`str`)、`explanation` (`str`)、`criteria` (`list`，每項為 `{name, passed: true}` 或含具體修改建議的 `{name, passed: false, gap}`）。
  - **跨呼叫持久化**：掛載 checkpointer 並傳入相同 `thread_id` 時，同一個 `rubric` 會跨多次 `invoke()` / `stream_events()` 持續生效直到傳入新 `rubric`；`KeyboardInterrupt` 與 `asyncio.CancelledError` 會直接向外拋出，並可在下次以相同 rubric 呼叫時恢復進行中的評分。

### 4. Interpreters（程式碼直譯器與 PTC）
- **架構定位與安裝需求（Beta）**：
  - 在代理迴圈內提供可程式化的**記憶體內（in-memory）** JavaScript 工作區（基於 QuickJS），讓代理撰寫程式碼來組合工具、保存中間狀態並進行決定性資料轉換（排序、分組、解析、聚合），僅將最終結果回傳給模型上下文。別於針對作業系統環境執行 shell 指令與安裝套件的 Sandboxes。
  - Python：需安裝 `"deepagents[quickjs]"`（要求 `langchain-quickjs>=0.3.0` 且 Python 3.11+），使用 `CodeInterpreterMiddleware`。底層透過 `quickjs-rs` 編譯為 WebAssembly 並在主機程序的 `wasmtime` 上執行（每個 LangGraph thread 擁有獨立的 WebAssembly 實例）。
  - TypeScript：需安裝 `@langchain/quickjs`，使用 `createCodeInterpreterMiddleware`。底層透過 `QuickJS-Emscripten` 於 WASM 沙箱中執行。
- **預設隔離與兩大外部橋接機制**：
  - Middleware 會為代理新增 `eval` 工具，支援頂層 `await`（Top-level `await`），預設擷取 `console.log`、`console.warn`、`console.error` 並回傳最後一個運算式的結果。預設無權存取主機檔案系統、網路、shell、套件管理器或系統時鐘（wall-clock/datetime）。
  - **Programmatic tool calling (PTC)**：預設關閉，透過 `ptc` 允許清單（allowlist）啟用。啟用後將允許的工具暴露於全域 `tools` 命名空間下作為非同步函式，工具名稱會自動轉為 camelCase（例如 `web_search` 變為 `await tools.webSearch(...)`）。**安全與審批限制**：PTC 呼叫經由直譯器橋接執行，不走一般工具呼叫路徑，因此不會針對每次 PTC 呼叫強制執行 `interrupt_on`（Python）/ `interruptOn`（TS）人工審批流程。
  - **Dynamic subagents（動態子代理）**：當代理配置有子代理時預設開啟（`subagents=True` / `subagents: true`），在直譯器內暴露全域 `task()` 函式，支援從程式碼進行平行扇出（Fan-out and synthesize）、獨立驗證（Verification）與遞迴工作流（Recursive workflows）。
- **持久化模式（Persistence，Python `CodeInterpreterMiddleware` 的 `mode` 參數）**：
  - `"thread"`（預設）：跨多次 `eval` 呼叫與跨對話輪次（turns）保留狀態。每輪結束後將 QuickJS 記憶體狀態序列化為快照（snapshot）存入 graph state，並於下一輪開始前還原（不需 checkpointer 即可跨輪保留；若掛載 checkpointer 則可支援持久化 threads 與 time travel）。**限制**：快照僅保留可序列化資料，函式與類別等不可序列化物件在還原後無法存取，呼叫時會拋出如 `Value for 'fn' was not restored because it is not serializable (type: function).` 的錯誤；還原快照不會撤銷 PTC 工具已對外部世界產生的副作用。
  - `"turn"`：僅在單一代理輪次內的多個 `eval` 呼叫間保留狀態，下一輪重置。
  - `"call"`：每次 `eval` 呼叫皆在全新的 REPL 中執行。
- **配置參數對照表（`CodeInterpreterMiddleware` vs `createCodeInterpreterMiddleware`）**：
  - 記憶體上限：Python `memory_limit`（預設 `64 * 1024 * 1024` 即 64 MB）/ TS `memoryLimitBytes`（預設 `64 * 1024 * 1024`），TS 另有 `maxStackSizeBytes`（預設 `320 * 1024`）。
  - 執行逾時：Python `timeout`（預設 `5.0` 秒）/ TS `executionTimeoutMs`（預設 `5000` 毫秒，負數代表停用逾時）。
  - 工具名稱與輸出控制：Python `tool_name`（預設 `"eval"`）、`capture_console`（預設 `True`）、`max_result_chars`（預設 `4000`）/ TS `toolName`（預設 `"eval"`）、`captureConsole`（預設 `true`）、`maxResultChars`（預設 `4000`）、`systemPrompt`（預設 `null`）。
  - PTC 與子代理控制：Python `ptc`（預設 `None`）、`max_ptc_calls`（預設 `256`，僅在受信任環境可設為 `None`）、`subagents`（預設 `True`）、`mode`（預設 `"thread"`）、`max_snapshot_bytes`（預設 `None`，同 `memory_limit`）/ TS `ptc`（預設省略）、`maxPtcCalls`（預設 `256`）、`subagents`（預設 `true`）。

## 相關頁面
- [[concepts/deepagents-overview]]
- [[concepts/deepagents-customization]]
- [[concepts/deepagents-context-engineering]]
- [[concepts/deepagents-subagents]]
- [[concepts/deepagents-sandboxes]]

## 出處
- docs/deepagents/profiles.md
- docs/deepagents/multimodal.md
- docs/deepagents/rubric.md
- docs/deepagents/interpreters.md
