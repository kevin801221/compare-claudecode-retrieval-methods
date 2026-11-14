# 出題任務（給 Codex）

你要替一個「檢索評測」出題。之後會有另一個 AI 只靠這些文件回答你的題目，再由程式比對答案。

- 文件：`world/corpus/<id>.md`（英文官方文件）。清單和 id 在 `world/docs.json`。
- 輸出：把題目寫進 `world/questions.json`（JSON 陣列）。
- 檢查：執行 `.venv/bin/lab check`，一直修到沒有任何「問題」為止。

## 題數

- 試跑：10 題，每種題型 2 題。目前只有 agent-sdk 的文件。
- 正式：40 題，每種題型 8 題。agent-sdk、deepagents、langchain、langgraph 四個框架都要出到題，試跑的題目可以沿用。

## 每一題的格式

```json
{"id": "Q01", "type": "lookup", "question": "…", "must_include": ["…"], "must_not_include": [],
 "gold_docs": ["agent-sdk/hooks"], "probe_terms": [], "answerable": true}
```

## 共通規則

1. 題目用繁體中文，寫成台灣工程師平常會問的問題。可以保留必要的英文專有名詞（產品、類別、函式名稱），但不要整句照抄文件。
2. `must_include` 是程式判分用的答案字串，必須逐字出現在文件裡，而且要短而獨特，例如類別或函式名稱、參數名稱、預設值、版本號、指令。不要用 `True`、`None`、`100` 這種到處都有的字。
3. 優先問「要查文件才知道」的細節，例如參數名稱、預設值、限制、錯誤訊息、較新的功能。不要問一般常識，或任何人都知道的概念。
4. 每寫一題，就用 `grep -rlF "<答案字串>" world/corpus` 查它出現在哪些文件。

## 題型

| type | 怎麼出 | gold_docs |
|---|---|---|
| `lookup` | 題目直接點出要查的東西 | 完整答案出現的**所有**文件 |
| `paraphrase` | 刻意不提文件裡的關鍵英文詞，改用中文描述（例如不說 interrupt，而說「讓流程暫停、等人確認後再繼續」） | 同上 |
| `version` | 新舊 API 或設定的差異（遷移指南、deprecated 說明）。`must_include` 放現在該用的寫法，`must_not_include` 放舊寫法 | 同上 |
| `multi_doc` | 題目同時問兩件事，答案分別只在兩份不同的文件裡。`must_include` 每份文件各提供至少 1 個 | 這兩份文件 |
| `unanswerable` | 合理、但這些文件**完全沒有回答**的問題，出題前先 grep 確認。`gold_docs` 和 `must_include` 留空，`answerable` 設為 `false`，`probe_terms` 放 [實體, 屬性]，例如 `["Agent SDK", "Ruby"]` | 留空 |

其他欄位的規則：
- 除了 `unanswerable`，其他題型的 `answerable` 都是 `true`。
- `must_not_include` 只有 `version` 要填，其他留空。
- `probe_terms` 只有 `unanswerable` 要填，其他留空。

## 完成條件

`.venv/bin/lab check` 顯示「沒有問題」。「提醒」可以保留，但要在最後的回覆裡逐一說明為什麼可以接受。
