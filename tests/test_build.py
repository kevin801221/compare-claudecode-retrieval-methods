import json

import pytest

from lab.build import CLAUDE_MD, CLAUDE_MD_WIKI, SETTINGS, digest, layout, render_index, stage_problems

DOCS = {"docs": [
    {"id": "langgraph/persistence", "title": "Persistence", "category": "langgraph", "slug": "persistence"},
    {"id": "agent-sdk/hooks", "title": "Hooks|SDK", "category": "agent-sdk", "slug": "hooks"},
    {"id": "langchain/frontend/overview", "title": "Frontend", "category": "langchain", "slug": "frontend/overview"},
]}


def test_layout():
    maps = layout(DOCS)
    assert sorted(maps["A-messy"].values()) == ["docs/doc_001.md", "docs/doc_002.md", "docs/doc_003.md"]
    assert maps["B-organized"]["langchain/frontend/overview"] == "docs/langchain/frontend/overview.md"
    assert maps["C-indexed"] == maps["B-organized"] == maps["D-wiki"]
    assert layout(DOCS) == maps   # 固定種子，可以重現


def test_layout_rejects_duplicate_paths():
    dup = {"docs": DOCS["docs"] + [{"id": "x", "title": "x", "category": "langgraph", "slug": "persistence"}]}
    with pytest.raises(ValueError):
        layout(dup)


def test_render_index_escapes_pipes_and_sorts_by_path():
    paths = layout(DOCS)["C-indexed"]
    rows = {d["id"]: {"summary": "摘要|有直線", "keywords": ["checkpointer", "檢查點"]} for d in DOCS["docs"]}
    lines = render_index(DOCS, paths, rows).splitlines()
    assert lines[0] == "# 文件索引"
    assert [line.split(" | ")[0][2:] for line in lines[4:]] == sorted(paths.values())
    text = "\n".join(lines)
    assert "Hooks／SDK" in text and "摘要／有直線" in text and "checkpointer、檢查點" in text


def test_digest_keeps_headings_and_limits_length():
    body = "# Title\n" + "內容" * 3000 + "\n## Hooks\n### Timeout\n"
    text = digest(body, limit=3000)
    assert len(text) <= 3000 and "## Hooks" in text and "### Timeout" in text


def _write_stage(root, maps, bodies):
    for cond, paths in maps.items():
        for doc_id, rel in paths.items():
            f = root / cond / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(bodies[doc_id], encoding="utf-8")
        (root / cond / ".claude").mkdir(parents=True, exist_ok=True)
        (root / cond / ".claude" / "settings.json").write_text(json.dumps(SETTINGS), encoding="utf-8")
    (root / "C-indexed" / "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    (root / "C-indexed" / "INDEX.md").write_text("x")
    (root / "D-wiki" / "CLAUDE.md").write_text(CLAUDE_MD_WIKI, encoding="utf-8")
    (root / "D-wiki" / "wiki").mkdir()
    (root / "D-wiki" / "wiki" / "index.md").write_text("目錄\n", encoding="utf-8")


WIKI = {"index.md": "目錄\n"}


def test_stage_problems_detects_differences(tmp_path):
    maps = layout(DOCS)
    bodies = {d["id"]: f"{d['id']}\n" for d in DOCS["docs"]}
    _write_stage(tmp_path, maps, bodies)
    clean = [p for p in stage_problems(tmp_path, maps, bodies, WIKI) if "家目錄" not in p and "上層" not in p]
    assert clean == []
    (tmp_path / "A-messy" / maps["A-messy"]["agent-sdk/hooks"]).write_text("改過\n", encoding="utf-8")
    (tmp_path / "B-organized" / "CLAUDE.md").write_text("x")
    (tmp_path / "D-wiki" / "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")       # 放錯成 C 組的指引
    (tmp_path / "D-wiki" / "wiki" / "index.md").write_text("被改過\n", encoding="utf-8")
    problems = stage_problems(tmp_path, maps, bodies, WIKI)
    assert any("A-messy" in p and "內文" in p for p in problems)
    assert any("B-organized" in p and "CLAUDE.md" in p for p in problems)
    assert any("D-wiki" in p and "CLAUDE.md 內容" in p for p in problems)
    assert any("D-wiki" in p and "wiki/" in p for p in problems)
