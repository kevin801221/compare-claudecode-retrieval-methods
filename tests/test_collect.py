from lab.collect import DOC_INDEX_BANNER, SDK_LINK, clean_body, title_of


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
