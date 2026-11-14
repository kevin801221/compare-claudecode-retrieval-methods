# LLM Wiki 建置任務（給 Antigravity）

請依照 Andrej Karpathy 的 LLM Wiki 做法（https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f），把 `docs/` 裡 213 頁官方技術文件「編譯」成一份互相連結的 Markdown wiki，寫進 `wiki/`。

這份 wiki 之後會成為另一個 AI（Claude Code）查資料的入口。它的用法是：
1. 先讀 `wiki/index.md`。
2. 順著連結找到相關頁面。
3. 依頁面上的出處，打開原始文件確認答案。

## 規則（很重要）

1. **只根據 `docs/` 裡的內容。** 不要上網查，也不要用你自己原本就知道的知識補充。文件沒寫的，就不要寫。
2. **不要修改 `docs/`。** 所有產出都只寫進 `wiki/`。
3. **名稱和數值一律逐字照抄。** 類別、函式、參數、環境變數、指令、預設值、版本號，都要跟原文一模一樣，大小寫和符號也要保留。
4. **每一頁都要標出處。** 寫相對於這個資料夾的路徑，例如 `docs/langgraph/persistence.md`。
5. **中英對照。** 頁面標題用官方的英文名稱，另外列出繁體中文的說法、同義詞和口語說法，因為之後的使用者會用中文提問。
6. **不要寫出任何本機路徑**，例如 `/Users/...`。

## 文件

| 資料夾 | 內容 | 頁數 |
|---|---|---|
| `docs/agent-sdk/` | Claude Agent SDK | 32 |
| `docs/deepagents/` | Deep Agents | 58 |
| `docs/langchain/` | LangChain | 79 |
| `docs/langgraph/` | LangGraph | 44 |

`docs/agent-sdk/typescript.md`（約 33 萬字元）和 `docs/agent-sdk/python.md`（約 17 萬字元）是很長的 API 參考，請分段讀完。

## wiki 的結構

```
wiki/
├── index.md       # 目錄（必要）
├── log.md         # 建置紀錄
├── concepts/      # 概念：agent loop、checkpointing、human-in-the-loop、memory…
├── entities/      # 具體的 API：類別、函式、選項、環境變數、CLI 參數…
├── guides/        # 操作步驟：設定、部署、除錯
├── versions/      # 版本差異、遷移、deprecated 說明
└── comparisons/   # 跨框架或跨語言的比較，例如 Python vs TypeScript、各框架的同類功能
```

### 每一頁的格式

```markdown
# <英文標題>

別名：<繁中說法>、<同義詞>、<口語說法>、<英文縮寫>
框架：langgraph（可以列多個）

## 摘要
<2–4 句繁體中文>

## 重點
- <事實。名稱、參數、預設值、限制都逐字照抄>

## 相關頁面
- [[concepts/checkpointing]]
- [[entities/interrupt]]

## 出處
- docs/langgraph/persistence.md
```

- **連結格式：** 用 `[[分類/檔名]]`，它對應到 `wiki/分類/檔名.md`。請多建立有意義的連結，這些連結就是知識圖譜。
- **跨框架的同一概念：** 例如 LangGraph 的 checkpointer 和 Agent SDK 的 file checkpointing，兩邊要互相連結，並在 `comparisons/` 寫一頁比較。
- **版本差異或矛盾：** 文件之間有版本差異或互相矛盾時，寫進 `versions/`，並分別註明出處。
- **頁數：** 寧可頁數少、內容扎實，也不要大量只有一兩行的空頁。總共幾百頁就夠了。

### `wiki/index.md`

依分類列出每一頁，一頁一行：

```markdown
## 概念
- [[concepts/checkpointing]] — 讓執行狀態可以存檔、回溯與恢復。關鍵詞：checkpointer、檢查點、存檔、恢復、回溯
```

### `wiki/log.md`

每讀完一份文件就加一行，格式固定：

```markdown
## [2026-11-14] ingest | docs/langgraph/persistence.md
```

## 完成前的自我檢查

在這個資料夾裡執行下面三段指令，三段都**不應該有任何輸出**：

```bash
# 1. 每一頁（index.md、log.md 除外）都有「## 出處」
find wiki -name '*.md' ! -name index.md ! -name log.md | while read f; do grep -q '^## 出處' "$f" || echo "缺出處：$f"; done
# 2. 出處列出的檔案都存在
grep -rhoE 'docs/[a-z-]+/[A-Za-z0-9_/.-]+\.md' wiki | sort -u | while read p; do [ -f "$p" ] || echo "出處不存在：$p"; done
# 3. 每一份文件都至少被一頁引用
comm -23 <(find docs -name '*.md' | sort) <(grep -rhoE 'docs/[a-z-]+/[A-Za-z0-9_/.-]+\.md' wiki | sort -u)
```

## 完成後請回報

- wiki 的總頁數，以及各分類的頁數。
- 這次建置大約用了多少 token、花了多少時間（如果介面上看得到）。
