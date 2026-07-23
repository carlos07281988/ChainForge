# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""WebSearch + Grounding Tool — built-in web search capability.

Inspired by Google ADK's built-in WebSearch tool and MS Agent Framework's
Bing/Google grounding. Provides a unified interface for web search with
configurable backends (DuckDuckGo, SerpAPI, Bing, or custom).

Usage:
    from chainforge.tools.websearch import web_search

    # With DuckDuckGo (free, no API key needed)
    result = await web_search("latest AI news")

    # With SerpAPI
    result = await web_search("latest AI news", backend="serpapi", api_key="...")
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from chainforge.core.tool import tool


def _duckduckgo_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search using DuckDuckGo's HTML interface (no API key needed)."""
    encoded = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/129.0.0.0 Safari/537.36",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [{"title": "Search Error", "snippet": f"Failed to search: {e}", "url": ""}]

    results: list[dict[str, str]] = []
    import re

    # Extract result blocks
    blocks = re.findall(
        r'<a[^>]*class="result__a"[^>]*>(.*?)</a>.*?'
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    )

    for title_html, snippet_html in blocks[:max_results]:
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_html).strip()
        # Extract URL
        url_match = re.search(r'href="(.*?)"', title_html)
        url = urllib.parse.unquote(url_match.group(1)) if url_match else ""
        # DuckDuckGo redirect URLs
        if "//duckduckgo.com/l/" in url:
            url = urllib.parse.unquote(url.split("uddg=")[-1]) if "uddg=" in url else url

        results.append({"title": title, "snippet": snippet, "url": url})

    # Fallback if regex fails
    if not results:
        snippets = re.findall(
            r'class="result__body"[^>]*>.*?<a[^>]*href="(.*?)".*?>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</a>',
            html, re.DOTALL,
        )
        for url, title_html, snippet_html in snippets[:max_results]:
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            snippet = re.sub(r"<[^>]+>", "", snippet_html).strip()
            results.append({"title": title, "snippet": snippet, "url": url.strip()})

    return results


def _serpapi_search(query: str, api_key: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search using SerpAPI (requires API key)."""
    params = urllib.parse.urlencode({
        "q": query, "api_key": api_key, "num": max_results,
        "engine": "google", "source": "web",
    })
    url = f"https://serpapi.com/search?{params}"

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return [{"title": "Search Error", "snippet": f"SerpAPI failed: {e}", "url": ""}]

    results: list[dict[str, str]] = []
    for item in data.get("organic_results", [])[:max_results]:
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "url": item.get("link", ""),
        })
    return results


def _bing_search(query: str, api_key: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search using Bing Web Search API v7."""
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    params = urllib.parse.urlencode({"q": query, "count": max_results, "mkt": "en-US"})
    url = f"https://api.bing.microsoft.com/v7.0/search?{params}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return [{"title": "Search Error", "snippet": f"Bing API failed: {e}", "url": ""}]

    results: list[dict[str, str]] = []
    for item in data.get("webPages", {}).get("value", [])[:max_results]:
        results.append({
            "title": item.get("name", ""),
            "snippet": item.get("snippet", ""),
            "url": item.get("url", ""),
        })
    return results


@tool(name="web_search", description="Search the web for information. Uses DuckDuckGo by default (free). "
       "For SerpAPI or Bing, set backend='serpapi'/'bing' and provide api_key.")
async def web_search(query: str, max_results: int = 5,
                      backend: str = "duckduckgo",
                      api_key: str | None = None) -> str:
    """Search the web and return results with titles, snippets, and URLs.

    Args:
        query: The search query.
        max_results: Maximum number of results (1-10).
        backend: Search backend: 'duckduckgo' (free), 'serpapi', or 'bing'.
        api_key: API key for SerpAPI or Bing (not needed for DuckDuckGo).

    Returns:
        Formatted search results with title, snippet, and URL for each result.
    """
    max_results = max(1, min(10, max_results))

    if backend == "serpapi":
        if not api_key:
            import os
            api_key = os.environ.get("SERPAPI_API_KEY", "")
        if not api_key:
            return "Error: SerpAPI requires an API key. Set SERPAPI_API_KEY env var or pass api_key."
        results = _serpapi_search(query, api_key, max_results)
    elif backend == "bing":
        if not api_key:
            import os
            api_key = os.environ.get("BING_API_KEY", "")
        if not api_key:
            return "Error: Bing API requires an API key. Set BING_API_KEY env var or pass api_key."
        results = _bing_search(query, api_key, max_results)
    else:
        results = _duckduckgo_search(query, max_results)

    if not results:
        return "No results found."

    parts: list[str] = []
    for i, r in enumerate(results, 1):
        parts.append(f"{i}. {r.get('title', 'Untitled')}")
        if r.get("snippet"):
            parts.append(f"   {r['snippet']}")
        if r.get("url"):
            parts.append(f"   Source: {r['url']}")
        parts.append("")

    return "\n".join(parts).strip()


@tool(name="web_fetch", description="Fetch and extract text content from a URL.")
async def web_fetch(url: str, max_chars: int = 5000) -> str:
    """Fetch a URL and return its visible text content.

    Args:
        url: The URL to fetch.
        max_chars: Maximum characters to return (default 5000).

    Returns:
        Visible text content from the page.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                   "AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Error fetching URL: {e}"

    # Basic HTML-to-text extraction
    import re
    # Remove scripts and styles
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    # Replace block tags with newlines
    html = re.sub(r"</?(?:p|div|h[1-6]|li|br|tr|blockquote)[^>]*>", "\n", html)
    # Remove remaining tags
    text = re.sub(r"<[^>]+>", "", html)
    # Decode HTML entities
    text = urllib.parse.unquote(text)
    # Collapse whitespace
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = text.strip()

    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n...[truncated]"

    return text or "No readable content found."


# ── Convenience toolkit ────────────────────────────────────────────────────


def web_search_toolkit() -> list:
    """Return the web search and fetch tools as a list for Agent configuration."""
    return [web_search, web_fetch]
