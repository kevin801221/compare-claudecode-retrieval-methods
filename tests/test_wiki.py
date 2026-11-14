from lab.wiki import check_wiki

DOC_PATHS = {"docs/langgraph/persistence.md", "docs/agent-sdk/hooks.md", "docs/langchain/models.md"}

PAGE = """# Checkpointing

別名：檢查點、存檔
框架：langgraph

## 摘要
讓執行狀態可以存檔與恢復。

## 相關頁面
- [[entities/hooks]]

## 出處
- docs/langgraph/persistence.md
"""

HOOKS = PAGE.replace("# Checkpointing", "# Hooks").replace("docs/langgraph/persistence.md", "docs/agent-sdk/hooks.md")


def test_good_wiki_passes_with_coverage_warning():
    files = {"index.md": "- [[concepts/checkpointing]]\n", "log.md": "## [2026-11-14] ingest | docs/langgraph/persistence.md\n",
             "concepts/checkpointing.md": PAGE, "entities/hooks.md": HOOKS}
    problems, warnings, stats = check_wiki(files, DOC_PATHS)
    assert problems == []
    assert len(warnings) == 1 and "docs/langchain/models.md" in warnings[0]   # 沒被引用的文件只算提醒
    assert stats["pages"] == 2 and stats["by_category"] == {"concepts": 1, "entities": 1}
    assert stats["cited_docs"] == 2 and stats["links"] == 3   # index.md 的連結也算


def test_problems_and_broken_links():
    files = {"concepts/a.md": "# A\n- [[concepts/missing]]\n",                       # 沒有 index.md、沒有出處
             "concepts/b.md": PAGE.replace("docs/langgraph/persistence.md", "docs/langgraph/nope.md"),
             "concepts/c.md": PAGE + "\n見 /Users/someone/notes.md\n"}
    problems, warnings, _ = check_wiki(files, DOC_PATHS)
    text = "\n".join(problems)
    for expected in ["缺少 index.md", "concepts/a.md：缺少「## 出處」", "出處不存在 docs/langgraph/nope.md",
                     "concepts/c.md：出現本機路徑"]:
        assert expected in text
    assert any("[[concepts/missing]]" in w for w in warnings)
