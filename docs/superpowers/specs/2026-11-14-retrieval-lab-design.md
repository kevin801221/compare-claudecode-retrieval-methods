# Retrieval Lab 設計文件

- 日期：2026-11-14（v2：改用官方技術文件）
- 狀態：設計已確認
- 適用版本：Claude Code 2.1.325（探測時的版本）

## 1. 目標

用數字讓同學看到：**資料的整理方式，會怎麼影響 Claude Code 的檢索與回答準確度。**

做法是一個 A/B 實驗：用同一批文件、同一套題目，比較三種整理方式，結果用互動網頁呈現。

文件採用真正有用的官方技術文件：LangChain、LangGraph、Deep Agents、Claude Agent SDK。實驗做完後，整理好的 C 組資料夾本身就是一個可以日常使用的文件庫。

### 不做的事（v1）

- 不建向量資料庫，也不做 RAG。這次測的就是 Claude Code 內建的 Grep／Glob／Read 檢索。
- 不用 LLM 當評審，全部由程式比對。
- 不做自動排程，一律手動觸發。
- 不把「比較模型」當主實驗。主實驗固定一個模型，換模型只當作選配的額外一輪。

## 2. 已確認的決策

| 項目 | 決定 |
|---|---|
| 目的 | 比較三種整理方式（A/B 實驗） |
| 文件 | 官方原文 213 頁：LangChain、LangGraph、Deep Agents、Claude Agent SDK（第 4.1 節） |
| 題目 | 由 Codex 出題（和作答的 Claude 不同家），再由程式驗證、使用者審題 |
| 對照組 | 閉卷：不給文件問一次，找出「憑記憶就答得出來」的題目 |
| 實驗組 | A 雜亂／B 整理／C 索引／D LLM wiki（第 5、14 節；D 組在 2026-11-14 追加） |
| 觸發方式 | 手動一鍵執行，結果會累積 |
| 呈現方式 | claude.ai 互動網頁，外加本機的 `report.md` 和 `results.csv` |
| 答題方式 | `claude -p` headless 模式，由 Python 腳本呼叫（uv 管理） |
| 評分方式 | 程式比對，不用 LLM 評審 |
| 主模型 | Haiku（可以用 `--model` 參數更換） |
| 執行方式 | 在同一個 Claude Code session 內直接執行 |

## 3. 探測結果（2026-11-14）

評測呼叫使用的參數：

```
claude -p <prompt> --model haiku --effort medium --tools Read,Grep,Glob \
  --strict-mcp-config --setting-sources project --disable-slash-commands \
  --no-session-persistence --output-format stream-json --verbose \
  --include-hook-events --json-schema <schema>      （stdin 接 /dev/null）
```

| 觀察 | 結論 |
|---|---|
| 工作目錄在家目錄底下時，模型讀得到 `~/AGENTS.md` 和 `~/.claude/CLAUDE.md` 的內容 | **實驗資料夾必須放在家目錄外** |
| 工作目錄在家目錄外時，那兩個檔案都不會載入；沒有任何 hook 事件；`mcp_servers` 為空；工具只有 Glob、Grep、Read、StructuredOutput | 隔離有效 |
| 專案自己的 `CLAUDE.md` 有載入；C 組的第一個動作就是去讀 `INDEX.md` | C 組的指引確實生效 |
| 讀取工作目錄以外的檔案會被權限拒絕 | 看不到隔壁組，也看不到答案卷 |
| stream-json 預設不輸出 hook 事件，加上 `--include-hook-events` 才會出現 | 開跑前檢查必須加這個參數，才查得到 hook |
| 專案 `.claude/settings.json` 裡的 hooks，在未信任的工作區也會執行；`permissions.allow` 則會被忽略 | 本設計不依賴 `allow` 規則；工具範圍改由 `--tools` 限制 |
| stdin 不是終端機時，`claude -p` 會先等 3 秒 | 所有呼叫的 stdin 都接 `/dev/null` |
| 有些呼叫只看 Grep 的內文結果就作答，完全沒有 Read | 「檢索命中」必須把 Grep 內文結果也算進去 |
| Haiku 回答一題小文件的題目，約 5 秒、$0.0012–0.0017 | 官方文件長得多，實際用量以試跑結果校正 |

## 4. 文件與題目

### 4.1 文件來源

| 框架 | 頁數 | 來源 | 授權 |
|---|---|---|---|
| Claude Agent SDK | 32 | `code.claude.com/docs/llms.txt` 列出的 `agent-sdk/*.md` | Anthropic 官方文件 |
| Deep Agents | 58 | `langchain-ai/docs` repo 的 `src/oss/deepagents/**/*.mdx` | MIT |
| LangChain | 79 | 同上，`src/oss/langchain/` | MIT |
| LangGraph | 44 | 同上，`src/oss/langgraph/` | MIT |

- **規模：** LangChain 系列的頁面平均約 1.9 萬字元。Agent SDK 的 API 參考頁最長：TypeScript 版約 33 萬字元，Python 版約 17 萬字元。全部合計約 470 萬字元。
- **處理方式：** 內文原樣保留，只去掉 Agent SDK 每頁開頭固定的「Documentation Index」引言。
- **文件內的連結：** 原樣保留。B、C 組的檔名跟連結對得上，A 組對不上，這本身就是「整理方式」的一部分。
- **著作權：** `world/corpus/` 只供個人學習。repo 不公開推送，網頁上也不放文件原文。

### 4.2 `world/docs.json`

由 `lab collect` 產生：

```json
{
  "collected_at": "2026-11-14",
  "docs": [
    {"id": "langgraph/persistence", "title": "Persistence", "category": "langgraph",
     "slug": "persistence", "chars": 23456, "sha": "..."}
  ]
}
```

- `id` 就是「框架/頁面路徑」，內文存在 `world/corpus/<id>.md`。
- `sha` 是內文的 sha256，用來確認文件有沒有變動。

### 4.3 `world/questions.json`

由 Codex 撰寫，格式是 JSON 陣列：

```json
[
  {"id": "Q01", "type": "lookup", "question": "Agent SDK 的 hook 預設逾時是多少毫秒？",
   "must_include": ["60000"], "must_not_include": [], "gold_docs": ["agent-sdk/hooks"],
   "probe_terms": [], "answerable": true}
]
```

`type` 的值：`lookup`、`paraphrase`、`version`、`multi_doc`、`unanswerable`。

### 4.4 出題規則

**共通規則：**
- 題目用繁體中文問，文件是英文。可以保留必要的英文專有名詞，但不能整句照抄文件。
- 答案字串必須逐字出現在文件中，而且要短而獨特，例如類別名、函式名、參數名、預設值、版本號。
- 優先問「要查文件才知道」的細節，避免問一般常識。

**各題型：**

| 題型 | 規則 | `gold_docs` 的意思 |
|---|---|---|
| `lookup` 直接查找 | 題目直接點出要查的東西 | 完整答案出現的**所有**文件，找到其中**任一**份就算命中 |
| `paraphrase` 換句話說 | 題目刻意不用文件裡的關鍵英文詞，改用中文描述 | 同上 |
| `version` 新舊版本 | 問新舊 API 或設定的差異（遷移指南、deprecated 說明）。`must_include` 放新寫法，`must_not_include` 放舊寫法 | 同上 |
| `multi_doc` 跨文件 | 題目同時問兩件事，分別只寫在兩份文件中 | 這兩份文件，**全部**都要找到才算命中 |
| `unanswerable` 題庫裡沒有 | 合理、但這些文件完全沒有回答的問題。`probe_terms` 放 [實體, 屬性] | 留空 |

### 4.5 規模

| 階段 | 文件 | 題數 |
|---|---|---|
| 試跑 | 只用 Agent SDK 的 32 頁 | 10 題，每種題型 2 題 |
| 正式 | 全部 213 頁 | 40 題，每種題型 8 題，四個框架都要出到題 |

文件 id 以路徑為準，所以試跑的題目換到正式版仍然有效，可以直接沿用。

### 4.6 出題與驗證

1. Codex 依照 `docs/codex-questions.md` 出題，寫入 `world/questions.json`。
2. `lab check` 檢查題目，結果分兩類：
   - **問題**（會擋下，不能開跑）：
     - 欄位缺漏、id 重複、題型不明、`answerable` 跟題型不符。
     - 引用了不存在的文件。
     - 答案沒有出現在 gold 文件中。
     - 非跨文件題的完整答案也出現在沒列出的文件裡（要把那份補進 `gold_docs`，或換一個答案字串）。
     - 跨文件題少於 2 份文件，或其中一份文件不含任何答案字串。
     - 新舊版本題缺少 `must_not_include`。
     - 題庫裡沒有的題，卻填了 gold 或答案；或 `probe_terms` 不是剛好 2 個。
   - **提醒**（不會擋下，審題時要看）：題庫裡沒有的題，它的實體和屬性同時出現在某份文件中。
3. 使用者審題：看題目清單和所有提醒，同意後才開跑。

## 5. 三組實驗資料夾（build）

- **位置：** 預設是 `/Users/Shared/retrieval-lab-stage/`，可以用環境變數 `LAB_STAGE` 覆寫。建置時會確認它不在 `$HOME` 底下。

| 組別 | 資料夾 | 內容 |
|---|---|---|
| A 雜亂 | `A-messy/` | `docs/doc_001.md` 到 `doc_213.md`，用固定種子打亂順序，全部放同一層 |
| B 整理 | `B-organized/` | `docs/<框架>/<頁面路徑>.md`，例如 `docs/langgraph/persistence.md` |
| C 索引 | `C-indexed/` | B 的內容，再加上 `INDEX.md` 和 `CLAUDE.md` |
| D LLM wiki | `D-wiki/` | B 的內容，再加上 Antigravity 產出的 `wiki/` 和 `CLAUDE.md`（見第 14 節） |

- **三組共通：**
  - `.claude/settings.json` 完全相同：deny 了 Bash、Edit、Write、NotebookEdit、WebFetch、WebSearch。
  - 文件內文逐字相同，建置時用 sha256 檢查。
  - 檔案對照表 `build/mapping.json` 放在 repo，不放進 stage。
- **`INDEX.md` 盲建：**
  - 用獨立的 `claude -p` 呼叫產生（Sonnet），**完全不給題目**。
  - 每頁只提供開頭 1500 字元加上所有標題行，上限 3000 字元，不放整頁。
  - 每頁一列：相對路徑、標題、一句繁中摘要、8–12 個關鍵字（英文名詞，以及對應的繁中說法和同義詞）。
  - 結果快取在 `world/index_rows.json`。
- **C 組的 `CLAUDE.md` 固定內容：**

```markdown
# 資料查找指引
- 先讀 INDEX.md，依關鍵字找出候選文件，再打開文件確認內容。
- 同一主題有多個版本時，以日期最新的為準。
```

## 6. 執行

### 6.1 評測（`lab run`）

- **工作目錄：** `<stage>/<組別>`，參數見第 3 節。
- **答案格式：** `{answer: string, sources: string[], found: boolean}`。
- **提示詞（三組相同）：**

```
你是公司內部的資料查詢助理。請只根據目前資料夾裡的文件回答下面的問題，不要憑自己的知識。
如果文件中找不到答案，found 填 false，answer 說明找不到。
sources 列出你實際用來回答的文件路徑（相對於目前資料夾）。
數字請用阿拉伯數字。

問題：{question}
```

### 6.2 閉卷對照（`lab closed`）

- 在家目錄外的空暫存資料夾執行，`--tools ""`（不開任何工具），每題只問 1 次。
- 提示詞：

```
請不要查任何資料，直接憑你自己的知識回答下面的問題。
如果你不知道或不確定，found 填 false，answer 說明不知道。
sources 留空。數字請用阿拉伯數字。

問題：{question}
```

- 可回答題在閉卷時答對，就標記為「憑記憶可答」。

### 6.3 開跑前檢查

任何一項不通過，整輪就中止。

1. 題目通過 `lab check`，沒有任何「問題」。
2. stage 根目錄不在 `$HOME` 底下，且所有上層資料夾都沒有 `CLAUDE.md`、`CLAUDE.local.md`、`AGENTS.md`、`.claude/CLAUDE.md`。
3. 三組的內文 sha256 一致；設定檔相同；只有 C 組有 `CLAUDE.md` 和 `INDEX.md`。
4. 每組先做一次檢查呼叫，init 事件必須符合：
   - 工具只有 {Glob, Grep, Read, StructuredOutput}；閉卷組只有 {StructuredOutput}。
   - 沒有 MCP、技能、slash commands。
   - 整次呼叫沒有任何 hook 事件。

### 6.4 排程、續跑與紀錄

- **排程：** 每輪的任務是「題目 × 組別」，用輪次當種子打亂順序，三組交錯執行。預設同時跑 4 題，每題逾時 180 秒。
- **錯誤處理：** 逾時或出錯記為 `status=error`，不算答錯，也不計入任何比率的分母。
- **續跑：** `results.jsonl` 裡已經有 `status=ok` 的 (round, cond, qid) 會跳過。閉卷組的 cond 是 `Z-closed`，round 固定為 1。
- **原始紀錄：** 存在 `runs/`，不進 git。
- **結果：** 每次呼叫在 `results/results.jsonl` 附加一列。

## 7. 評分（`score.py`，純函式）

**正規化** `norm(s)`：NFKC、轉小寫、去掉所有空白和逗號。

| 指標 | 定義 |
|---|---|
| `correct` 答對 | 可回答題：`found=true`，而且所有 `must_include` 都出現在答案裡。不可回答題：`found=false` |
| `retrieved` 檢索命中 | gold 文件出現在「Read 過的檔案」或「Grep 內文結果中的檔案」裡。跨文件題要全部 gold 都出現，其他題型任一份即可。Glob 結果和只列檔名的 Grep 結果都不算 |
| `read_gold` | 同上，但只算 Read 過的檔案 |
| `citation_hit` 引用命中 | 同上，改看模型回報的 `sources`。`INDEX.md`、`CLAUDE.md` 不算文件 |
| `citation_precision` | \|sources ∩ gold\| / \|sources\| |
| `stale` 答到舊版 | 新舊版本題：`must_include` 沒有全部出現，而且出現了任一個 `must_not_include` |
| `hallucinated` 幻覺 | 不可回答題卻 `found=true`；或 `stale=true` |
| `index_used` 讀了索引 | Read 過 `INDEX.md`，或它出現在 Grep 內文結果中 |

- 同時提到新舊版本（例如「現在用 X，以前是 Y」）只要新寫法有出現，就算答對。
- C 組可能只看 `INDEX.md` 的摘要就答對，沒碰 gold 文件。所以報表一併列出 `index_used`，試跑時也要列出這類紀錄。

## 8. 統計（report）

- **主表（每組一列）：** 答對率、幻覺率、檢索命中率、引用命中率、讀了索引、平均工具呼叫數、平均讀檔數、平均秒數、平均花費、錯誤筆數。每個數字都是「各輪比率的平均」，旁邊附上各輪的最低到最高。
- **主表會出兩張：**
  1. 全部題目。
  2. 需要查文件的題目，也就是排除閉卷答對的題目。
- **閉卷結果：** 可回答題中有幾題「憑記憶可答」。
- **題型 × 組別：** 答對率。
- **成對比較：** 每題取多輪多數決，平手記為「不穩定」，比較 A vs C、B vs C、A vs B。
- **輸出檔案：** `results/report.md`、`results/results.csv`（含閉卷列）、`results/dashboard.json`。
- **網頁資料：** 只放題目、標準答案、各組回答、相對檔名、指標、是否憑記憶可答。不放絕對路徑、session ID、原始紀錄或文件原文。

## 9. 互動網頁

- **形式：** claude.ai 網頁（Artifact），資料來自 `dashboard.json`。發布時先用 Artifact quickstart 判斷用哪種型別。
- **內容：**
  - 總覽：三組長條圖，可以切換「全部題目」和「需要查文件的題目」。
  - 閉卷結果。
  - 題型熱度表。
  - 成對比較。
  - 逐題展開。
- **更新：** 跑完新的輪數後，重新發布即可，網址不變。
- **分享：** 頁面預設只有本人看得到，要從 Share 選單分享出去。

## 10. 專案結構

```
~/test-dir-1/retrieval-lab/
├── pyproject.toml            # uv 管理；console script：lab
├── README.md
├── .gitignore                # runs/、.venv/、__pycache__/
├── docs/
│   ├── codex-questions.md    # 給 Codex 的出題說明
│   └── superpowers/          # 設計與計畫
├── world/
│   ├── docs.json             # lab collect 產生
│   ├── corpus/<框架>/<頁面>.md
│   ├── questions.json        # Codex 產生
│   └── index_rows.json       # 盲建索引的快取
├── build/mapping.json
├── src/lab/
│   ├── cli.py                # collect / check / build / closed / run / report
│   ├── common.py
│   ├── collect.py            # 下載官方文件
│   ├── world.py              # 題目檢查
│   ├── trace.py              # 解析 stream-json
│   ├── score.py
│   ├── build.py
│   ├── run.py                # 評測與閉卷對照
│   └── report.py
├── tests/
├── results/
└── runs/                     # 原始紀錄（不進 git）
```

Git 使用獨立的 repo。作者是 `kevin801221 <kevin801221@users.noreply.github.com>`，不加 Claude 署名，不 push。

## 11. 執行順序

1. `lab collect --only agent-sdk` → Codex 出 10 題 → `lab check` → 使用者審題。
2. `lab build` → `lab closed` → `lab run --rounds 1` → `lab report`。
   - **試跑只確認流程和評分是否正確**，三件事要看：
     - 人工抽查 10 筆評分。
     - C 組有沒有「答對但沒碰 gold 文件」的情況。
     - 實際用量。
3. 正式版：
   1. `lab collect --force`（213 頁）→ Codex 出 40 題（可以沿用試跑的題目）→ `lab check` → 審題。
   2. `lab build` → `lab closed` → 先跑第 1 輪 → 報表。
4. **用正式版第 1 輪判斷難度。** 如果多數題型三組都是 100% 或都是 0%，就三組一視同仁地調整題目，然後重新出題。舊結果因為 world_id 不同，會自動不納入統計。
5. 難度合適之後，補跑第 2、3 輪 → `report` → 發布網頁。

## 12. 用量估算（2026-11-14 試跑實測：Agent SDK 32 頁、10 題、Haiku）

| 組別 | 每次平均花費 | 平均秒數 | 平均輸入 token |
|---|---|---|---|
| A 雜亂 | $0.0041 | 8.5 | 6.8 萬 |
| B 整理 | $0.0028 | 6.7 | 3.6 萬 |
| C 索引 | $0.0048 | 8.7 | 6.7 萬 |
| 閉卷 | $0.0009 | 4.3 | 0.5 萬 |

- 這次試跑總共花了：評測 30 次 $0.118，閉卷 10 次 $0.009，盲建索引 4 批，約 12 秒。
- 這些花費都是換算成 API 價格的估計；訂閱方案實際上是扣額度。
- **正式版預估（213 頁、40 題）：**
  - 每輪 120 次，約 $0.5–1；同時跑 4 題，約 5 分鐘。
  - 3 輪加閉卷，合計約 $2–3。
  - 盲建索引約 22 批 Sonnet 呼叫。
- **注意：** C 組的 `INDEX.md` 會隨文件數變大（213 列），每題先讀索引的成本也會跟著增加。這是正式版要觀察的取捨。

## 13. 風險與限制

- **憑記憶作答：** Claude 可能讀過這些文件的舊版。對策：
  - 用閉卷對照組找出這類題目，主表另外列出「需要查文件的題目」。
  - 檢索命中和效率指標看的是工具呼叫紀錄，不受記憶影響。
  - 出題優先問細節。
- **可能沒差：** A 組的答對率可能和 C 組相近。所以效率、題型拆解、閉卷後的子集，都要跟答對率一樣當成主要結果來看；如果真的沒差，就照實呈現。
- **C 組混了兩個變因：** 索引和 `CLAUDE.md` 指引同時存在，無法分開歸因。
- **文件會更新：** `docs.json` 記錄了下載日期和每頁的 sha。重新下載等於換一個世界。
- **模型代表性：** 只用 Haiku 測，結果不一定能套到 Sonnet 或 Opus。可以選配加跑一輪 `--model sonnet`。
- **樣本小：** n = 40，不宣稱統計顯著，報表會標出 n 並附上成對比較。
- **版本漂移：** Claude Code 升級可能改變結果，所以每一列都記錄 `claude_version`。

## 14. D 組：LLM wiki（2026-11-14 追加）

**目的：** 回答「花大量 token 做前處理，值不值得？」這個問題。D 組照 Karpathy 的 LLM Wiki 做法（2026-04 的 gist），把 213 頁文件「編譯」成一份互相連結的 Markdown wiki。C 組則是便宜的一頁一行索引，兩組形成對比。

### 怎麼產生

前處理交給 Antigravity，任務說明在 `docs/antigravity-wiki.md`。

- **盲建：** 用 `lab wiki-export <資料夾>` 在 repo 外建立工作資料夾。裡面只有文件的唯讀副本和任務說明，**沒有題目和結果**。repo 裡的位置會被擋下。
- **規則：**
  - 只根據 `docs/` 撰寫，不上網、不憑記憶。
  - 名稱與數值逐字照抄。
  - 每頁都要有「## 出處」，並附中英對照的別名。
  - 不能出現本機路徑。
- **結構：**
  - `wiki/index.md`：目錄，每頁一行，附摘要和關鍵詞。
  - `wiki/log.md`：建置紀錄。
  - 頁面分成 `concepts/`、`entities/`、`guides/`、`versions/`、`comparisons/`，頁面之間用 `[[分類/檔名]]` 連結。
- **匯入與檢查：**
  1. `lab wiki-import <資料夾>`：只匯入 `.md`，換行統一成 LF，存到 `world/wiki/`。
  2. `lab wiki-check`：
     - **問題**（必須修正）：缺少 `index.md`、頁面缺少「## 出處」、出處指向不存在的文件、出現本機路徑。
     - **提醒**：連結指向不存在的頁面，或有文件沒被任何頁面引用。

### D 組資料夾

- **內容：** B 組的原始文件、`wiki/`，再加上下面這份 `CLAUDE.md`：

```markdown
# 資料查找指引
- 先讀 wiki/index.md 找出相關頁面，再順著頁面裡的 [[連結]] 往下找（[[分類/檔名]] 對應 wiki/分類/檔名.md）。
- 回答前，依頁面「## 出處」打開 docs/ 裡的原始文件確認內容。
- 同一主題有多個版本時，以日期最新的為準。
```

- **建置時的檢查：** `world/wiki/` 必須存在，而且沒有「問題」。stage 檢查會確認以下幾點：
  - 各組只有該有的額外檔案。
  - C、D 兩組的 `CLAUDE.md` 內容正確。
  - D 組的 `wiki/` 跟 `world/wiki/` 完全相同。
- **world_id：** 納入 wiki 內容，換一份 wiki 就等於換一個世界。

### 評分與統計

- **新指標 `wiki_used`：** 有 Read 過任一 wiki 頁面，或 wiki 頁面出現在 Grep 內文結果中。
- **引用比率：** 計算時排除 `wiki/` 開頭的來源，因為 wiki 頁面不算文件。
- **成對比較：** 新增 B vs D、C vs D。
- **一次性前處理成本：** Antigravity 用掉的 token 和時間，由使用者記錄，列在報表裡，跟「每題的成本」並列。
- **每輪呼叫數：** 改為 40 題 × 4 組 = 160 次。

### 限制

- **兩個變因混在一起：** D 組的 wiki 由 Gemini 投入大量 token 產生，C 組的索引由 Sonnet 用少量 token 產生。所以 C 和 D 的差異同時反映了「做法」和「投入」，無法拆開。
- **wiki 本身可能寫錯：** wiki 由 LLM 撰寫。如果 D 組因此答錯或產生幻覺，這也算是實驗結果的一部分。原始文件仍然在 D 組裡，可以讓 Claude 核對。
