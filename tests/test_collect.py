import json

import pytest

from lab import collect as col
from lab.collect import DOC_INDEX_BANNER, SDK_LINK, clean_body, title_of
from lab.common import sha256


def test_clean_body_normalizes_newlines():
    # 原始文件偶爾用 CRLF；git 的 autocrlf 之後會改動它，內文和 docs.json 的 sha 就對不上
    assert clean_body("\r\n# T\r\nline\r\n\r\n") == "# T\nline\n"


def test_title_of():
    assert title_of("---\ntitle: Persistence\ndescription: x\n---\n# Other", "s") == "Persistence"
    assert title_of("# Agent SDK overview\n\ntext", "s") == "Agent SDK overview"
    assert title_of("沒有標題", "fallback") == "fallback"


def test_sdk_banner_and_links():
    body = "> ## Documentation Index\n> Fetch the index at: x\n> Use this file.\n\n# Hooks\n內容\n"
    assert DOC_INDEX_BANNER.sub("", body, count=1) == "# Hooks\n內容\n"
    index = ("- [Hooks](https://code.claude.com/docs/en/agent-sdk/hooks.md): x\n"
             "- [Headless](https://code.claude.com/docs/en/headless.md): y\n")
    assert SDK_LINK.findall(index) == ["https://code.claude.com/docs/en/agent-sdk/hooks.md"]


def test_collect_missing_fetches_only_missing_sdk_pages(tmp_path, monkeypatch):
    # 公開 repo 沒附 Agent SDK 全文：只補缺的頁面，不動 docs.json 和其他文件，並回報和當初 sha 不同的頁面
    corpus, docs_json = tmp_path / "corpus", tmp_path / "docs.json"
    (corpus / "langchain").mkdir(parents=True)
    (corpus / "langchain" / "a.md").write_text("# A\n", encoding="utf-8")
    docs = [{"id": "langchain/a", "category": "langchain", "slug": "a", "sha": sha256("# A\n")},
            {"id": "agent-sdk/hooks", "category": "agent-sdk", "slug": "hooks", "sha": sha256("# Hooks\n")},
            {"id": "agent-sdk/old", "category": "agent-sdk", "slug": "old", "sha": "官方之後改過"}]
    docs_json.write_text(json.dumps({"collected_at": "2026-11-14", "docs": docs}), encoding="utf-8")
    fetched = []

    def fake_fetch(url):
        fetched.append(url)
        return f"> ## Documentation Index\n> x\n\n# {url.rsplit('/', 1)[1][:-3].title()}\n".encode()

    monkeypatch.setattr(col, "CORPUS", corpus)
    monkeypatch.setattr(col, "DOCS_JSON", docs_json)
    monkeypatch.setattr(col, "fetch", fake_fetch)
    assert col.collect_missing() == ["agent-sdk/old"]
    assert fetched == ["https://code.claude.com/docs/en/agent-sdk/hooks.md",
                       "https://code.claude.com/docs/en/agent-sdk/old.md"]
    assert (corpus / "agent-sdk" / "hooks.md").read_text(encoding="utf-8") == "# Hooks\n"
    assert json.loads(docs_json.read_text(encoding="utf-8"))["docs"] == docs


def test_collect_missing_refuses_other_frameworks(tmp_path, monkeypatch):
    docs_json = tmp_path / "docs.json"
    docs_json.write_text(json.dumps({"collected_at": "2026-11-14", "docs": [
        {"id": "langchain/a", "category": "langchain", "slug": "a", "sha": "x"}]}), encoding="utf-8")
    monkeypatch.setattr(col, "CORPUS", tmp_path / "corpus")
    monkeypatch.setattr(col, "DOCS_JSON", docs_json)
    with pytest.raises(SystemExit):
        col.collect_missing()
