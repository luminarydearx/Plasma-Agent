"""Web and network tools for PlasmaAgent."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


async def web_search(query: str, max_results: int = 5) -> ToolResult:
    try:
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=max_results)]
        
        if not results:
            return ToolResult(True, "No results found", {"results": []})
        
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")[:200],
            })
        
        output = "\n".join(f"{i}. {r['title']}\n   {r['url']}" for i, r in enumerate(formatted, 1))
        return ToolResult(True, output, {"results": formatted})
    except ImportError:
        return ToolResult(False, "duckduckgo-search not installed. Run: pip install duckduckgo-search")
    except Exception as e:
        return ToolResult(False, f"Search failed: {e}")


async def youtube_search(query: str, max_results: int = 5) -> ToolResult:
    try:
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(f"site:youtube.com {query}", max_results=max_results)]
        
        if not results:
            return ToolResult(True, "No YouTube results found", {"results": []})
        
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append({
                "number": i,
                "title": r.get("title", ""),
                "url": r.get("href", ""),
            })
        
        output = "\n".join(f"{r['number']}. {r['title']}\n   {r['url']}" for r in formatted)
        return ToolResult(True, output, {"results": formatted})
    except ImportError:
        return ToolResult(False, "duckduckgo-search not installed. Run: pip install duckduckgo-search")
    except Exception as e:
        return ToolResult(False, f"YouTube search failed: {e}")


async def web_scrape(url: str, max_chars: int = 10000) -> ToolResult:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            html = response.read().decode("utf-8", errors="ignore")
        
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<[^>]+>", " ", html)
        html = re.sub(r"\s+", " ", html).strip()
        
        if len(html) > max_chars:
            html = html[:max_chars] + "..."
        
        return ToolResult(True, html, {"url": url, "chars": len(html)})
    except Exception as e:
        return ToolResult(False, f"Failed to scrape {url}: {e}")


async def download_file(url: str, save_path: str = "") -> ToolResult:
    try:
        if not save_path:
            downloads = Path.home() / "Downloads"
            downloads.mkdir(exist_ok=True)
            filename = url.split("/")[-1].split("?")[0] or "download"
            save_path = str(downloads / filename)
        
        target = Path(save_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
        
        target.write_bytes(data)
        
        return ToolResult(
            True,
            f"Downloaded {len(data)} bytes to {target}",
            {"path": str(target), "size": len(data)},
        )
    except Exception as e:
        return ToolResult(False, f"Download failed: {e}")
