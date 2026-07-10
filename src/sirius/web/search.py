from __future__ import annotations

from html.parser import HTMLParser

import httpx

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Sirius/0.1 personal assistant"


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Free web search via DuckDuckGo (no API key required)."""
    try:
        from ddgs import DDGS
    except ImportError:  # older package name
        from duckduckgo_search import DDGS

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return [
        {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
        for r in results
    ]


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "head", "nav", "footer"}

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self._chunks.append(data.strip())

    def text(self) -> str:
        return "\n".join(self._chunks)


def fetch_url(url: str, max_chars: int = 6000) -> str:
    """Fetch a web page and return its readable text content."""
    response = httpx.get(
        url, headers={"User-Agent": _UA}, timeout=30, follow_redirects=True
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        return f"Unsupported content type: {content_type}"
    parser = _TextExtractor()
    parser.feed(response.text)
    text = parser.text()
    return text[:max_chars] + ("\n[... truncated]" if len(text) > max_chars else "")
