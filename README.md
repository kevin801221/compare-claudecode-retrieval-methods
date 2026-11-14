# Retrieval Lab

比較三種資料整理方式（A 雜亂／B 整理／C 索引）對 Claude Code 檢索與回答準確度的影響。
文件使用官方原文：LangChain、LangGraph、Deep Agents、Claude Agent SDK。
設計見 `docs/superpowers/specs/2026-11-14-retrieval-lab-design.md`。

## 需求

- uv，以及已登入的 Claude Code（`claude` 指令可以用）
- 出題用 Codex，說明在 `docs/codex-questions.md`
- 實驗資料夾預設放在 `/Users/Shared/retrieval-lab-stage`。它必須在家目錄外，可以用環境變數 `LAB_STAGE` 換位置。

## 使用

```bash
uv sync
uv run lab collect --only agent-sdk   # 下載文件（正式版用 uv run lab collect --force）
codex exec --full-auto "請依照 docs/codex-questions.md 出題（試跑：10 題）"
uv run lab check                      # 檢查題目
uv run lab build                      # 盲建索引，建立 A/B/C 三組
uv run lab closed                     # 閉卷對照：每題問一次，不給文件
uv run lab run --rounds 1             # 跑評測，可以續跑
uv run lab report                     # 產生 results/report.md、results.csv、dashboard.json
uv run pytest                         # 執行測試
```

## 注意

- 每一輪的呼叫次數是「題數 × 3 組」，會消耗額度。
- `world/corpus/` 是官方文件的複本，只供個人學習，repo 不要公開推送。
- `runs/` 是原始紀錄，裡面有本機路徑，所以不進 git。
