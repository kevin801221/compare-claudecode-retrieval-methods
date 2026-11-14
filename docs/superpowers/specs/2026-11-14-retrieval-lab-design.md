# Retrieval Lab 設計文件

- 日期：2026-11-14
- 狀態：設計已確認，待審閱
- 適用版本：Claude Code 2.1.325（探測時的版本）

## 1. 目標

用數字讓同學看到：**資料的整理方式，會怎麼影響 Claude Code 的檢索與回答準確度**。

做法是一個 A/B 實驗：用同一批虛構文件、同一套題目，比較三種整理方式。結果用互動網頁呈現。

### 不做的事（v1）

- 不建向量資料庫，也不做 RAG。這次測的就是 Claude Code 內建的 Grep／Glob／Read 檢索。
- 不用 LLM 當評審，全部由程式比對。
- 不做自動排程（手動觸發）。之後需要再加 launchd。
- 不把「比較模型」當主實驗。主實驗固定一個模型；換模型只當作選配的額外一輪。

## 2. 已確認的決策

| 項目 | 決定 |
|---|---|
| 目的 | 比較整理方式（A/B 實驗） |
| 資料 | Claude 生成的虛構公司文件，答案只存在檔案中，模型無法憑記憶作答 |
| 實驗組 | A 雜亂／B 整理／C 索引（定義見第 5 節） |
| 觸發方式 | 手動一鍵跑，結果累積 |
| 呈現方式 | claude.ai 互動網頁，並在本機產生 `report.md` 和 `results.csv` |
| 答題方式 | `claude -p` headless，由 Python 腳本（uv 管理）呼叫 |
| 評分方式 | 程式比對，不用 LLM 評審 |
| 主模型 | Haiku（可用 `--model` 參數更換） |

## 3. 探測結果（2026-11-14）

使用的參數：

```
claude -p <prompt> --model haiku --tools Read,Grep,Glob --strict-mcp-config \
  --setting-sources project --disable-slash-commands --no-session-persistence \
  --output-format stream-json --verbose --json-schema <schema>
```

| 觀察 | 結論 |
|---|---|
| cwd 在家目錄底下時，模型看得到 `~/AGENTS.md` 和 `~/.claude/CLAUDE.md` 的內容 | 上層資料夾的指示檔會被當成專案指示載入，**實驗資料夾必須放在家目錄外** |
| cwd 在家目錄外時，上述兩個檔案都沒有載入；沒有 hook 事件；`mcp_servers` 是空的；工具只有 Glob、Grep、Read、StructuredOutput | 隔離有效 |
| 專案的 `CLAUDE.md` 有載入 | C 組的指引會生效 |
| 讀取 cwd 外的檔案被權限拒絕（`-p` 模式自動拒絕） | 看不到隔壁組或答案卷 |
| `--json-schema` 可以跟工具並用，結果在 `result.structured_output` | 可以直接拿來產生結構化答案 |
| `.claude/settings.json` 的 `permissions.allow` 因為「工作區未信任」被忽略（stderr 警告） | 本設計不依賴 allow：cwd 內的讀取預設就允許，工具範圍改由 `--tools` 限制 |
| 內建 plugin（`cc-plugin-agents-md` 等）仍會載入，但沒有增加工具 | 可以接受 |
| 模型可能只看 Grep 的內文結果就作答，沒有 Read 檔案 | 檢索指標必須把 Grep 的內文結果也算進去（見第 7 節） |
| Haiku 回答簡單題約 5 秒、$0.002–0.003 | 作為用量估算的起點 |

## 4. 虛構世界與事實表

### 4.1 世界設定

虛構公司「雲杉科技」，賣智慧家電。文件分五類，同時也是 B／C 組的資料夾名稱：`產品`、`人資`、`客服`、`工程`、`會議紀錄`。全部以繁體中文撰寫，內文夾雜少量英文術語。

### 4.2 `world/facts.json`

事實表先產生，文件和題目都從它而來：

```json
{
  "world": {"company": "雲杉科技", "description": "..."},
  "docs": [
    {
      "id": "D001",
      "title": "XR-7 智慧空氣清淨機規格書",
      "category": "產品",
      "slug": "XR-7-規格書",
      "date": "2025-03-01",
      "role": "gold",
      "facts": ["電池容量 4200 mAh"],
      "brief": "給生成器的寫作指示"
    }
  ],
  "questions": [
    {
      "id": "Q01",
      "type": "lookup",
      "question": "XR-7 的電池容量是多少？",
      "must_include": ["4200"],
      "must_not_include": [],
      "gold_docs": ["D001"],
      "answerable": true
    }
  ]
}
```

- `role`：`gold` 是含有答案的文件；`distractor` 是主題相近、但數值不同的干擾文件；`filler` 是一般背景文件。
- `type` 的值：`lookup`、`paraphrase`、`version`、`multi_doc`、`unanswerable`。

### 4.3 規模

| | 文件數 | 題數 | 每種題型 |
|---|---|---|---|
| 試跑 | 20 | 10 | 2 |
| 正式 | 200 | 40 | 8 |

### 4.4 題型規則

| 題型 | 規則 |
|---|---|
| `lookup` 直接查找 | 題目用詞跟文件一致 |
| `paraphrase` 換句話說 | 題目刻意改用同義詞或另一種語言（例：文件寫「退貨」，題目問「退費」；文件寫「SLA」，題目問「服務等級協議」） |
| `version` 新舊版本 | 新舊兩版文件都存在，日期不同。`must_include` 填新版數值，`must_not_include` 填舊版數值 |
| `multi_doc` 跨文件 | `gold_docs` 有 2 份，`must_include` 包含兩份文件各自的事實 |
| `unanswerable` 題庫裡沒有 | 問的是一個存在的實體、但從未被任何文件記載的屬性。`answerable=false`，`gold_docs` 和 `must_include` 都留空 |

### 4.5 寫作規則

- `must_include` 一律是短而明確的字串：型號、阿拉伯數字、日期。文件裡要逐字寫出。
- 文件內容不提到其他文件的檔名或路徑，因為各組的檔名不同。

### 4.6 生成與驗證

- **生成方式：** `facts.json` 用一次 `claude -p` 呼叫產生，模型用 Sonnet，之後再人工審閱題目。文件依 `facts.json` 分批（每批約 5 份）用 Sonnet 生成。兩者都只生成一次，生成後存進 git。
- **驗證**（程式執行，失敗就重新生成該份文件）：
  - 每題的每個 `must_include`，正規化後都出現在至少一份 `gold_docs` 中；`multi_doc` 題的事實要分別出現在對應的文件中。
  - `version` 題：`must_not_include` 出現在舊版文件中，不出現在新版文件中。
  - 所有文件都不含檔案路徑的痕跡：`.md`、`docs/`、`doc_` 加數字，都視為違規。

## 5. 三組實驗資料夾（build）

**位置：** 預設放在 `/Users/Shared/retrieval-lab-stage/`，可用環境變數 `LAB_STAGE` 覆寫。建置時檢查它必須在 `$HOME` 之外。

| 組別 | 資料夾 | 內容 |
|---|---|---|
| A 雜亂 | `A-messy/` | `docs/doc_001.md` 到 `doc_200.md`，編號依固定種子打亂，全部放同一層 |
| B 整理 | `B-organized/` | `docs/<category>/<slug>.md`，例如 `docs/人資/出差補助辦法-2025.md` |
| C 索引 | `C-indexed/` | B 的全部內容，加上 `INDEX.md` 和 `CLAUDE.md` |

**三組共通的規則：**
- `.claude/settings.json` 三組完全相同：`deny` 列出 Bash、Edit、Write、NotebookEdit、WebFetch、WebSearch。
- 每份文件的正文三組逐字相同，建置時用 sha256 檢查。
- 檔案對照表 `build/mapping.json`（`{組別: {doc_id: 相對路徑}}`）放在 repo 裡，**不放進 stage 資料夾**。

**C 組的 `INDEX.md` 必須盲建：**
- 由獨立的 `claude -p` 呼叫產生，它**只讀文件，完全看不到題目**。
- 每份文件一列：相對路徑｜標題｜一句摘要｜關鍵字（含同義詞、中英文）。
- 結果快取在 `world/index_rows.json`，重新建置時不會再生成一次。

**C 組的 `CLAUDE.md` 固定是以下內容：**

```markdown
# 資料查找指引
- 先讀 INDEX.md，依關鍵字找出候選文件，再打開文件確認內容。
- 同一主題有多個版本時，以日期最新的為準。
```

## 6. 執行（run）

### 6.1 每次呼叫

cwd 設為 `<stage>/<組別>`：

```
claude -p <PROMPT> --model <model> --tools Read,Grep,Glob --strict-mcp-config \
  --setting-sources project --disable-slash-commands --no-session-persistence \
  --output-format stream-json --verbose --json-schema <ANSWER_SCHEMA>
```

**答案格式：** `ANSWER_SCHEMA` 規定 `{answer: string, sources: string[], found: boolean}`，三個欄位都是必填。

**提示詞模板**（三組完全相同）：

```
你是公司內部的資料查詢助理。請只根據目前資料夾裡的文件回答下面的問題，不要憑自己的知識。
如果文件中找不到答案，found 填 false，answer 說明找不到。
sources 列出你實際用來回答的文件路徑（相對於目前資料夾）。
數字請用阿拉伯數字。

問題：{question}
```

### 6.2 每輪開跑前的檢查

任何一項不通過，整輪中止。

1. stage 根目錄不在 `$HOME` 底下，而且它的所有上層資料夾都沒有 `CLAUDE.md`、`CLAUDE.local.md`、`AGENTS.md`、`.claude/CLAUDE.md`。
2. 三組的文件正文 sha256 一致。
3. 每組第一次呼叫時檢查 init 事件：`tools` 只能是 {Glob, Grep, Read, StructuredOutput}、`mcp_servers` 為空、沒有 skills 和 slash commands、整次呼叫沒有 hook 事件。

### 6.3 排程與續跑

- 每輪的任務是「題目 × 組別」，用輪次編號當種子打亂順序，讓三組交錯執行。
- 預設同時跑 4 題（`--workers` 可調），每題 180 秒逾時。
- 逾時或錯誤記為 `status=error`。這類結果不算答錯，也不計入任何比率的分母，在報表中另外列出筆數。
- 續跑：`results.jsonl` 裡已經有 `status=ok` 的 (round, cond, qid) 會跳過。

### 6.4 紀錄

- **原始紀錄：** stream-json 寫到 `runs/<round>/<cond>/<qid>.jsonl`，加入 `.gitignore`，因為裡面有絕對路徑。
- **結果：** 每次呼叫在 `results/results.jsonl` 附加一列，欄位如下：
  - 識別：`round`、`cond`、`qid`、`model`（取自 init 事件的實際模型 ID）、`claude_version`、`ts`、`status`
  - 回答：`answer`、`sources`、`found`
  - 檢索：`files_read`、`files_grep_content`
  - 效率：`tool_calls`、`turns`、`duration_ms`、`cost_usd`、`input_tokens`、`output_tokens`

## 7. 評分（`score.py`，純函式）

**正規化** `norm(s)`：先做 NFKC（全形轉半形），轉小寫，再去掉所有空白和逗號。

**路徑對應：** Read 的 `file_path` 和 Grep 內文結果中的路徑，轉成相對於組別根目錄的路徑，再用 `mapping.json` 換成 doc_id。

| 指標 | 定義 | 適用範圍 |
|---|---|---|
| `retrieved` 檢索命中 | 全部 `gold_docs` 都出現在「Read 過的檔案」和「Grep 內文模式結果中的檔案」的聯集裡。Glob 和 `files_with_matches` 的檔名清單不算 | 可回答題 |
| `read_gold` | 全部 `gold_docs` 都被 Read 過 | 可回答題 |
| `citation_hit` 引用命中 | 全部 `gold_docs` 都在模型回報的 `sources` 裡 | 可回答題 |
| `citation_precision` | \|sources ∩ gold\| / \|sources\| | 可回答題 |
| `correct` 答對 | 可回答題：`found=true`，而且所有 `must_include` 都在 `norm(answer)` 中。不可回答題：`found=false` | 全部 |
| `stale` 答到舊版 | `must_include` 沒有全部出現，而且有任一個 `must_not_include` 出現 | `version` 題 |
| `hallucinated` 幻覺 | 不可回答題卻 `found=true`；或可回答題 `stale=true` | 全部 |
| `index_used` 讀了索引 | 有 Read 過 `INDEX.md`，或 `INDEX.md` 出現在 Grep 內文結果中 | 全部（A、B 沒有索引，恆為否） |

- 可回答題的答案同時提到新舊版本（例如「2025 版 1200 元，2024 版是 1000 元」）時，只要新版數值有出現，就算答對，不扣分。
- 計算引用比率時，`sources` 裡的 `INDEX.md` 和 `CLAUDE.md` 不算，因為它們不是文件。
- C 組可能直接從 `INDEX.md` 的摘要拿到答案：答對了，但沒碰過 gold 文件，檢索命中率會因此偏低。所以報表會一併列出「讀了索引」的比例。試跑時也要列出這類紀錄，確認發生的頻率。
- 測試寫在 `tests/test_score.py`：用手寫的 stream 事件和答案，涵蓋五種題型，以及 Grep 內文、Glob、`files_with_matches` 三種情況。

## 8. 統計（report）

- **每題 × 每組：** 跨輪的答對比例。另外取多數決作為該題的對錯；平手記為「不穩定」。
- **主表（每組一列）：**
  - 答對率、幻覺率、檢索命中率、引用命中率、讀了索引的比例、平均工具呼叫數、平均讀檔數、平均秒數、平均花費。
  - 每個數字都是各輪比率的平均，旁邊附上各輪的最低到最高。
  - 標示題數 n 和錯誤筆數。
- **題型 × 組別：** 答對率。
- **成對比較：** 用多數決結果，分別比較 A vs C、B vs C、A vs B，各列出「X 對 Y 錯」和「Y 對 X 錯」的題數。
- **輸出檔案：** `results/report.md`、`results/results.csv`、`results/dashboard.json`。
- **網頁資料的隱私：** `dashboard.json` 只包含題目、標準答案、各組回答、相對檔名和各項指標。不包含絕對路徑、session ID、原始對話紀錄或帳號資訊。

## 9. 互動網頁

- 以 claude.ai 網頁（Artifact）發布，資料來自 `dashboard.json`。發布時先用 Artifact quickstart 判斷適合的型別。
- **頁面內容：**
  - 總覽：三組的答對率、檢索命中率、幻覺率長條圖，以及效率。
  - 題型 × 組別熱度表。
  - 成對比較。
  - 逐題展開：題目、標準答案、三組回答、讀過的檔案、對錯。
- **更新：** 使用者跑完新的輪數後，請 Claude 用最新的 `dashboard.json` 重新發布，網址不變。
- **分享：** 頁面預設只有本人能看，給同學看需要從 Share 選單分享。

## 10. 專案結構

```
~/test-dir-1/retrieval-lab/
├── pyproject.toml            # uv 管理，console script：lab
├── README.md
├── .gitignore                # runs/、.venv/、__pycache__/
├── docs/superpowers/specs/   # 本文件
├── world/
│   ├── facts.json
│   ├── index_rows.json       # 盲建索引的快取
│   └── corpus/<doc_id>.md    # 標準正文（三組共用）
├── build/mapping.json
├── src/lab/
│   ├── cli.py                # 子指令：generate / build / run / report
│   ├── generate.py
│   ├── build.py
│   ├── run.py
│   ├── score.py
│   └── report.py
├── tests/test_score.py
├── results/                  # results.jsonl、results.csv、report.md、dashboard.json
└── runs/                     # 原始紀錄（不進 git）
```

**指令：**
- `uv run lab generate [--pilot]`
- `uv run lab build`
- `uv run lab run --rounds N [--model haiku] [--workers 4]`
- `uv run lab report`

**Git：** 獨立的 repo，作者設為 `kevin801221 <kevin801221@users.noreply.github.com>`，不加 Claude 署名，不 push。

## 11. 執行順序

1. `generate --pilot`：產生 20 份文件、10 題，請使用者審閱題目，並一併檢查答案字串是否也出現在非 gold 文件中。
2. 驗證通過後，執行 `build`，再跑開跑前檢查。
3. 試跑 1 輪（30 次呼叫），然後產生報表。**試跑只確認流程和評分正確**，不判斷難度：20 份文件時 Grep 幾乎什麼都找得到，接近滿分是預期中的事。要確認三件事：
   - 人工抽查 10 題的評分是否正確。
   - C 組有沒有「答對但沒碰過 gold 文件」的情況（直接從 INDEX.md 拿到答案）。
   - 每次呼叫的實際用量和時間，用來校正第 12 節的估算。
4. 正式版：`generate`（200 份文件、40 題）→ 審題 → `build` → 先跑第 1 輪並產生報表。
5. **用正式版第 1 輪判斷難度。** 如果多數題型三組都是 100% 或都是 0%，就**統一調整**題目用詞或文件雜訊，三組一視同仁，不針對任何一組調整。調整後要重新生成，舊的第 1 輪會自動不納入統計。
6. 難度合適後，補跑第 2、3 輪 → `report` → 發布網頁。

## 12. 用量估算（試跑後校正）

- **每輪：** 40 題 × 3 組 = 120 次呼叫。Haiku 粗估每次 $0.01–0.03，一輪約 $1–4（訂閱方案是扣額度，這是換算成 API 價格的估計）。同時跑 4 題，約 10–20 分鐘。
- **一次性生成：** 事實表 1 次、文件約 40 次、索引約 20 次，都用 Sonnet。

## 13. 風險與限制

- **可能沒差：** Grep 搜的是內文，A 組的答對率可能跟 C 組相近。所以效率欄位和題型拆解跟答對率一樣重要。如果結果是「整理沒差」，照實呈現。
- **C 組混合了兩個變因：** 索引和 `CLAUDE.md` 指引同時存在，無法分開歸因。要分開，需要第四組。
- **模型代表性：** Haiku 的結果不一定能推到 Sonnet 或 Opus，可以選配加跑一輪 `--model sonnet` 對照。
- **樣本小：** n = 40，不宣稱統計顯著。報表會標出 n，並附上成對比較。
- **版本漂移：** Claude Code 升級可能改變結果，所以每列都記錄 `claude_version`。
- **文件由 Claude 生成：** 文件風格可能對 Claude 比較友善，但三組受到的影響相同，不影響組間比較。

## 14. 實作時要確認的事

- Haiku 是否支援 `--effort`。支援的話就固定一個值，並記錄下來。
- Grep 內文模式的 tool_result 格式（`path:line:text`），用來寫路徑抽取和測試。
- `/Users/Shared` 是否可寫入。不行的話改用其他家目錄外的位置，並更新預設值。
- `permissions.deny` 在未信任的工作區是否生效。不生效也不影響，因為工具已經由 `--tools` 限制。
