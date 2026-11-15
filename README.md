# Claude Code 檢索方式比較（Retrieval Lab）

同一批官方技術文件用四種方式整理，讓 Claude Code 只靠這些文件回答同一組題目，比較四種整理方式的答對率和花費。

## 結果

| 組別 | 整理方式 | 答對率 | 每題花費 | 花費（B = 1） | 每題輸入 token | 每題秒數 | 每題工具呼叫 |
|---|---|---:|---:|---:|---:|---:|---:|
| A 雜亂 | 檔名打亂，全部放在同一層 | 100% | $0.0036 | 1.1 | 55,294 | 8.8 | 4.3 |
| B 整理 | 依框架分資料夾 | 100% | $0.0033 | 1.0 | 45,586 | 7.5 | 3.5 |
| C 索引 | B 再加一份 INDEX.md | 99.1% | $0.0076 | 2.3 | 112,595 | 9.4 | 3.9 |
| D wiki | B 再加 LLM wiki（88 頁） | 100% | $0.0091 | 2.8 | 152,970 | 11.1 | 5.2 |

數值是 3 輪的平均；花費是換算成 API 價格的估計。A、C 各有 1 次沒交出符合格式的答案，不計入上表。

- **答對率分不出高下。** 四組都是 99–100%，連檔名打亂的 A 組也一樣。另外加試的 18 題更難題型（彙整、易混淆、近似陷阱，每組 2 輪）也沒有拉開差距：A 組答錯 2 次，都是同一題，那題指定了 `langchain/errors/` 資料夾，而 A 組沒有資料夾；C 組有 1 次沒交出符合格式的答案；其他都答對。
- **索引和 wiki 讓每題變貴。** C 的花費是 B 的 2.3 倍，D 是 2.8 倍，而且幾乎每一題都比 B 貴：C 在 119 題次中有 118 次，D 是 120 題次全部。C、D 的指引要求每題先讀一份約 2.7 萬字元的入口檔（`INDEX.md` 或 `wiki/index.md`），讀進來之後，每次呼叫模型都會帶著它。D 的 wiki 另外花了約 91 分鐘建置。
- **wiki 很少被當成路標。** wiki 頁面列出的 302 個出處都指得到真實檔案，但 D 組 96 次作答中，只有 1 次是照 wiki 的出處直接打開正解文件；79 次是先 Grep 整個資料夾才找到。
- **雜亂和整理的花費差不多。** A 平均是 B 的 1.1 倍，但逐題比，A 比較貴 67 次、比較便宜 52 次，差距不穩定。比較穩定的差別是工具呼叫次數：A 比較多 60 次、比較少 24 次、一樣 35 次。

逐題比較的數字可以用 `uv run python scripts/paired_compare.py` 重算。

## 適用範圍

這些結果只適用於這次的條件：213 份文件、Claude Code 2.1.325 搭配 Haiku（effort medium）、只開放 Read／Grep／Glob、每題都開新的 session、題目由 Codex 出。文件多很多、同一個 session 連問很多題、換成別的模型，這次都沒有測。

## 實驗設計

- **文件：** 2026-11-14 下載的官方原文：LangChain 79 頁、LangGraph 44 頁、Deep Agents 58 頁、Claude Agent SDK 32 頁。
- **四組：** 四組的文件內容逐字相同，只差整理方式。C 的 `INDEX.md` 由 Sonnet 在沒看過題目的情況下寫成。D 的 wiki 由 Antigravity 建置，`wiki/index.md` 由程式依各頁摘要產生。C、D 的入口檔都控制在 28,000 字元內，Read 一次就讀得完。
- **題目：** 40 題，由 Codex 出：直接查找、換句話說、新舊版本、跨文件，以及文件裡沒有答案的題目。
- **評分：** 全部由程式判斷。答案要包含指定的字串；文件裡沒有答案的題目，要回答找不到。
- **閉卷對照：** 不給文件，每題問一次。32 題有答案的題目中，Haiku 不查文件就答對 9 題。
- **規模：** 3 輪，加上閉卷對照與試題，共 682 次呼叫，約 3.89 美元。

完整的設計、過程紀錄與結果在 [docs/superpowers/specs/2026-11-14-retrieval-lab-design.md](docs/superpowers/specs/2026-11-14-retrieval-lab-design.md)。

## 重跑

需要 [uv](https://docs.astral.sh/uv/)，以及已登入的 Claude Code（`claude` 指令可以用）。

```bash
uv sync
uv run lab collect --missing   # 補下載 Claude Agent SDK 那 32 頁，並比對是否和當初的版本相同
uv run lab check               # 檢查題目
uv run lab build               # 建立 A/B/C/D 四組實驗資料夾
uv run lab closed              # 閉卷對照
uv run lab run --rounds 3      # 跑評測，中斷後可以續跑
uv run lab report              # 產生 results/report.md、results.csv、dashboard.json
uv run python scripts/export_dashboard.py   # 產生 results/dash/ 的資料集
uv run pytest
```

- 實驗資料夾預設放在 `/Users/Shared/retrieval-lab-stage`，必須在家目錄外，可以用環境變數 `LAB_STAGE` 換位置。
- 每一輪的呼叫次數是「題數 × 4 組」，會消耗額度。
- 想改用最新版文件，執行 `uv run lab collect --force` 重新下載全部文件。舊結果會因為 world_id 不同，自動不納入統計。

## 文件與授權

- `world/corpus/` 只附 LangChain、LangGraph、Deep Agents 的 181 頁原文。它們來自 MIT 授權的 [langchain-ai/docs](https://github.com/langchain-ai/docs)，授權全文見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
- Claude Agent SDK 的 32 頁來自 code.claude.com，沒有公開授權，所以不放進 repo，請用 `uv run lab collect --missing` 下載。commit 訊息裡的「213 頁」包含這 32 頁。
- `world/wiki/` 和 `world/index_rows.json` 是模型依全部 213 頁寫的摘要。wiki 的 API 參考頁裡，有部分型別定義和程式碼範例和原文相同。

## 檔案

| 路徑 | 內容 |
|---|---|
| `world/questions.json` | 40 題與標準答案 |
| `world/trial_questions.json` | 18 題更難題型的試題 |
| `world/docs.json` | 文件清單，含每份文件的 sha256 |
| `world/wiki/` | D 組的 LLM wiki |
| `world/index_rows.json` | C 組 `INDEX.md` 的原始資料 |
| `results/results.jsonl` | 每次作答的紀錄 |
| `results/report.md`、`results/results.csv` | 統計表與逐筆結果 |
| `results/dash/` | 結果網頁用的資料集，每個檔案都附上產生它的程式 |
| `src/lab/` | 實驗程式（`uv run lab --help`） |
| `scripts/` | 試題測試、網頁資料集與逐題比較 |
