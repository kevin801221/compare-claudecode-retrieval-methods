# 出題任務 v2：更難的試題（給 Codex）

第 1 輪的 40 題，四組全部答對。受測的 Claude Code（Haiku）會把中文描述轉成英文 regex，用 Grep 一兩步就找到答案。這次要出**三種新題型的試題**，看哪一種能讓它答錯。試題只用來決定要不要採用這個題型，不會進正式題庫。

- 文件：`world/corpus/<id>.md`，清單和 id 在 `world/docs.json`。
- 輸出：`world/trial_questions.json`（JSON 陣列）。**不要修改 `world/questions.json`。**
- 檢查：執行 `.venv/bin/lab check --file world/trial_questions.json`，一直修到沒有任何「問題」為止。

## 只能看的檔案

只用 `world/corpus/` 和 `world/docs.json` 出題。

不要打開 `world/wiki/`、`world/index_rows.json`、`results/`、`runs/`、`build/`。那些是受測各組的輔助資料和評測結果，看了會讓題目偏向或偏離某一組。也不要沿用 `world/questions.json` 裡的題目。

## 題數

18 題，id 用 T01–T18。三種題型各 6 題，四個框架（agent-sdk、deepagents、langchain、langgraph）都要出到。

## 格式與共通規則

格式和共通規則跟 `docs/codex-questions.md` 相同：題目用繁體中文；`must_include` 要逐字出現在文件裡，而且短而獨特；每寫一題都用 grep 確認答案出現在哪些文件。不同的地方只有 `type`，改用下面三種。

## 題型

### `aggregate`：彙整

- 題目要求「全部列出」一組範圍明確的項目，項目 3–8 個。例如某個資料夾下每一頁各說明一個錯誤代碼或一種元件。
- **一項一份文件最好。** 答案如果集中在同一份文件的一張清單，Grep 一次就全拿到了，不要出這種題。
- 範圍要寫清楚，讓答案是一個封閉的集合，不會因為解讀不同而列出另一組項目。
- 題目不能點名任何一個項目，也不要透露總數。
- `must_include`：所有項目的名稱，逐字照抄。**不要放個數。**
- `gold_docs`：每個項目所在的文件，至少 2 份。
- 判分：答案要包含所有項目才算對，多列不扣分。

### `confusable`：易混淆

- 同一個概念，在兩個框架或兩種語言（Python／TypeScript）的寫法不同，例如選項名稱、參數名稱、預設值、匯入路徑。
- 題目明確指定其中一個框架或語言。
- `must_include`：被問的那一邊的寫法。`gold_docs`：完整答案出現的所有文件。
- `must_not_include`：另一邊對應的寫法，必須真的出現在文件裡。兩個字串不能互為子字串，例如 `Saver` 和 `InMemorySaver` 不行。
- 判分：答案要寫出被問的那一邊，而且不能出現另一邊的寫法。兩種都寫出來會被判錯。

### `near_miss`：近似陷阱

- 文件對這個主題有很多說明，但題目問的那個具體細節**文件裡沒有**，例如某個參數、預設值、上限、版本、步驟或指令。
- 措辭要像這個細節真的存在，例如問一個聽起來合理、但文件沒有的設定的預設值。
- 不要問明顯不存在的東西，例如其他程式語言的 SDK。那是舊題型 `unanswerable`。
- 出題前用 grep 確認：主題詞出現在很多文件裡；細節詞完全沒有出現，或只出現在無關的地方。
- `answerable` 設為 `false`，`gold_docs` 和 `must_include` 留空，`probe_terms` 放 [主題詞, 細節詞]。
- 判分：回答找不到才算對；拼湊出一個答案就算幻覺。

## 完成條件

- `.venv/bin/lab check --file world/trial_questions.json` 顯示「沒有問題」。
- 「提醒」可以保留，但要在最後的回覆裡逐一說明為什麼可以接受。
- 在回覆裡，每一題用一句話說明你為什麼認為它會比第 1 輪難。
