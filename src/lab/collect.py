"""下載官方文件：LangChain／LangGraph／Deep Agents（langchain-ai/docs repo）與 Claude Agent SDK（code.claude.com）。"""
from __future__ import annotations

import io
import re
import tarfile
import urllib.request
from datetime import date

from lab.common import CORPUS, DOCS_JSON, FRAMEWORKS, save_json, sha256

LC_TARBALL = "https://codeload.github.com/langchain-ai/docs/tar.gz/main"
LC_FRAMEWORKS = {"deepagents", "langchain", "langgraph"}
SDK_INDEX = "https://code.claude.com/docs/llms.txt"
SDK_LINK = re.compile(r"\((https://code\.claude\.com/docs/en/agent-sdk/[a-z0-9/-]+\.md)\)")
# Agent SDK 每頁開頭都有一段固定的「Documentation Index」引言，把它去掉
DOC_INDEX_BANNER = re.compile(r"\A(?:> .*\n)+\n?")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "retrieval-lab"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def title_of(body: str, fallback: str) -> str:
    """標題：優先用 frontmatter 的 title，其次用第一個 # 標題。"""
    fm = re.match(r"---\n(.*?)\n---", body, re.S)
    if fm and (m := re.search(r"^title:\s*(.+)$", fm.group(1), re.M)):
        return m.group(1).strip().strip("\"'")
    if m := re.search(r"^# (.+)$", body, re.M):
        return m.group(1).strip()
    return fallback


def clean_body(body: str) -> str:
    """換行統一成 LF、去掉頭尾空白並以換行結尾。git 的 autocrlf 才不會事後改動內文，讓 sha 對不上。"""
    return body.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"


def langchain_pages(wanted: set[str]) -> list[tuple[str, str, str]]:
    """回傳 (框架, 頁面路徑, 內文)。"""
    pages = []
    with tarfile.open(fileobj=io.BytesIO(fetch(LC_TARBALL)), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")   # docs-main/src/oss/<框架>/.../<頁>.mdx
            if (member.isfile() and member.name.endswith(".mdx") and len(parts) > 4
                    and parts[1:3] == ["src", "oss"] and parts[3] in wanted):
                slug = "/".join(parts[4:])[: -len(".mdx")]
                pages.append((parts[3], slug, tar.extractfile(member).read().decode("utf-8")))
    return pages


def sdk_pages() -> list[tuple[str, str, str]]:
    urls = sorted(set(SDK_LINK.findall(fetch(SDK_INDEX).decode("utf-8"))))
    pages = []
    for url in urls:
        body = DOC_INDEX_BANNER.sub("", fetch(url).decode("utf-8"), count=1)
        pages.append(("agent-sdk", url.split("/agent-sdk/", 1)[1][: -len(".md")], body))
    return pages


def collect(only: list[str] | None = None, force: bool = False) -> None:
    if DOCS_JSON.exists() and not force:
        raise SystemExit("world/docs.json 已經存在。要重新下載請加 --force（舊結果會因 world_id 不同，自動不納入統計）")
    wanted = set(only or FRAMEWORKS)
    pages: list[tuple[str, str, str]] = []
    if wanted & LC_FRAMEWORKS:
        print("下載 langchain-ai/docs …")
        pages += langchain_pages(wanted & LC_FRAMEWORKS)
    if "agent-sdk" in wanted:
        print("下載 Claude Agent SDK 文件 …")
        pages += sdk_pages()
    pages.sort(key=lambda p: (p[0], p[1]))
    if CORPUS.exists():
        for old in CORPUS.rglob("*.md"):
            old.unlink()
    docs = []
    for category, slug, body in pages:
        doc_id = f"{category}/{slug}"
        body = clean_body(body)
        path = CORPUS / f"{doc_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        docs.append({"id": doc_id, "title": title_of(body, slug), "category": category, "slug": slug,
                     "chars": len(body), "sha": sha256(body)})
    save_json(DOCS_JSON, {"collected_at": date.today().isoformat(), "docs": docs})
    counts = {f: sum(1 for d in docs if d["category"] == f) for f in sorted(wanted)}
    print(f"完成：{len(docs)} 頁（" + "、".join(f"{f} {n}" for f, n in counts.items()) + "）")
