"""
Baidu, 360, and general web search API connectors.

Configuration per source:
  auth_config: {
    "type": "baidu_custom" | "baidu_index" | "360_search" | "bing_search" | "google_custom",
    "api_key": "xxx",           # optional, falls back to env var
    "cx": "xxx",                # custom search engine ID (Google CSE)
    "region": "cn" | "us",      # search region
    "market": "zh-CN" | "en-US",
  }

Environment variables expected:
  BAIDU_API_KEY         → Baidu Custom Search API
  BAIDU_CX              → Baidu search engine ID
  GOOGLE_API_KEY        → Google Custom Search
  GOOGLE_CX             → Google CSE engine ID
  BING_API_KEY          → Bing Search API
  BAIDU_INDEX_API_KEY   → Baidu Index API (trend data)
"""
import os
import asyncio
from urllib.parse import urlencode

import httpx

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)


@register_collector("api_search")
class SearchEngineDispatcher(BaseCollector):
    """Dispatches to the appropriate search engine based on auth_config.type.

    Supports: tavily (default), baidu, bing, 360.
    The type is read from auth_config.get("search_type", "tavily").
    """
    channel = "api_search"

    def __init__(self, config: SourceConfig):
        super().__init__(config)
        ac = config.auth_config or {}
        self._search_type = ac.get("search_type", "tavily")
        self._delegate = self._build_delegate(ac, config)

    def _build_delegate(self, ac: dict, config: SourceConfig):
        st = self._search_type
        if st == "baidu":
            return BaiduDelegate(config, ac)
        elif st == "bing":
            return BingDelegate(config, ac)
        elif st == "360":
            return Search360Delegate(config, ac)
        else:
            from app.connectors.tavily_search import TavilyCollector
            return TavilyCollector(config)

    async def validate(self) -> bool:
        return await self._delegate.validate()

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        return await self._delegate.fetch(keywords, max_items)


class BaiduDelegate(BaseCollector):
    """
    Baidu Custom Search API.
    """
    channel = "api_search"
    BASE = "https://api.baidu.com/search/customsearch/v1"

    def __init__(self, config: SourceConfig, ac: dict):
        super().__init__(config)
        self.api_key = ac.get("api_key", "") or os.getenv("BAIDU_API_KEY", "")
        self.cx = ac.get("cx", "") or os.getenv("BAIDU_CX", "")
        self.region = ac.get("region", "cn")

    async def validate(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                resp = await c.get(self.BASE, params={
                    "access_token": self.api_key, "cx": self.cx,
                    "q": "test", "num": 1,
                })
                return resp.status_code == 200
        except Exception:
            return False

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        if not self.api_key:
            return self._error("BAIDU_API_KEY not set")
        if not self.cx:
            return self._error("BAIDU_CX (search engine ID) not set")

        items: list[FetchItem] = []
        errors: list[str] = []
        per_query = min(10, max_items // max(1, len(keywords)))

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            for query in keywords:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.get(self.BASE, params={
                        "access_token": self.api_key,
                        "cx": self.cx, "q": query,
                        "num": per_query, "lr": "zh-CN",
                    })
                    if resp.status_code == 429:
                        errors.append(f"Rate limited: {query}")
                        await asyncio.sleep(2)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    for r in data.get("items", data.get("results", [])):
                        title = r.get("title", "")
                        items.append(FetchItem(
                            title=title,
                            content=r.get("snippet", r.get("content", "")),
                            url=r.get("link", r.get("url", "")),
                            summary=r.get("snippet", "")[:500],
                            language="zh",
                            category=_infer_cat(title, r.get("snippet", "")),
                            suggested_tags=_build_tags(title, r.get("snippet", "")),
                            raw_metadata={"engine": "baidu", "query": query, "region": self.region},
                        ))
                    await asyncio.sleep(1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0)
                except Exception as exc:
                    errors.append(f"Baidu '{query[:30]}': {exc}")

        return _result(self._new_run_id(), self.config.id, items, errors)

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(run_id=self._new_run_id(), source_id=self.config.id,
                             status=JobStatus.FAILED, items=[], error_log=[msg])


@register_collector("api_search_360")
class Search360Collector(BaseCollector):
    """
    360 Search API (好搜).

    360 provides a web search API similar to Baidu's.
    Requires: 360_API_KEY (or API_TOKEN in auth_config).
    """
    channel = "api_search"
    BASE = "https://openapi.so.com/search"

    def __init__(self, config: SourceConfig):
        super().__init__(config)
        ac = config.auth_config or {}
        self.api_key = ac.get("api_key", "") or os.getenv("SO360_API_KEY", "")

    async def validate(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                resp = await c.get(self.BASE, params={
                    "key": self.api_key, "q": "test", "num": 1,
                })
                return resp.status_code == 200
        except Exception:
            return False

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        if not self.api_key:
            return self._error("SO360_API_KEY not set")

        items: list[FetchItem] = []
        errors: list[str] = []
        per_query = min(10, max_items // max(1, len(keywords)))

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            for query in keywords:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.get(self.BASE, params={
                        "key": self.api_key, "q": query, "num": per_query,
                    })
                    if resp.status_code == 429:
                        errors.append(f"360 rate limit: {query}")
                        await asyncio.sleep(2)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    for r in data.get("items", data.get("results", [])):
                        title = r.get("title", "")
                        items.append(FetchItem(
                            title=title,
                            content=r.get("summary", r.get("content", "")),
                            url=r.get("url", r.get("link", "")),
                            summary=r.get("summary", "")[:500],
                            language="zh",
                            category=_infer_cat(title, r.get("summary", "")),
                            suggested_tags=_build_tags(title, r.get("summary", "")),
                            raw_metadata={"engine": "360"},
                        ))
                    await asyncio.sleep(1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0)
                except Exception as exc:
                    errors.append(f"360 '{query[:30]}': {exc}")

        return _result(self._new_run_id(), self.config.id, items, errors)

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(run_id=self._new_run_id(), source_id=self.config.id,
                             status=JobStatus.FAILED, items=[], error_log=[msg])


class BingDelegate(BaseCollector):
    """
    Microsoft Bing Web Search API.
    """
    channel = "api_search"
    BASE = "https://api.bing.microsoft.com/v7.0/search"

    def __init__(self, config: SourceConfig, ac: dict):
        super().__init__(config)
        self.api_key = ac.get("api_key", "") or os.getenv("BING_API_KEY", "")
        self.market = ac.get("market", "zh-CN")

    async def validate(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                resp = await c.get(self.BASE, params={"q": "test", "count": 1},
                                   headers={"Ocp-Apim-Subscription-Key": self.api_key})
                return resp.status_code == 200
        except Exception:
            return False

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        if not self.api_key:
            return self._error("BING_API_KEY not set")

        items: list[FetchItem] = []
        errors: list[str] = []
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        count = min(50, max_items)

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            for query in keywords:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.get(self.BASE, params={
                        "q": query, "count": count, "mkt": self.market,
                    }, headers=headers)
                    if resp.status_code == 429:
                        errors.append(f"Bing rate limit: {query}")
                        await asyncio.sleep(2)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    for page in data.get("webPages", {}).get("value", []):
                        items.append(FetchItem(
                            title=page.get("name", ""),
                            content=page.get("snippet", page.get("summary", "")),
                            url=page.get("url", ""),
                            summary=page.get("snippet", "")[:500],
                            language=_detect_lang(page.get("url", ""), page.get("snippet", "")),
                            raw_metadata={"engine": "bing"},
                        ))
                    await asyncio.sleep(1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0)
                except Exception as exc:
                    errors.append(f"Bing '{query[:30]}': {exc}")

        return _result(self._new_run_id(), self.config.id, items, errors)

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(run_id=self._new_run_id(), source_id=self.config.id,
                             status=JobStatus.FAILED, items=[], error_log=[msg])


class TargetedScrapeCollector(BaseCollector):
    """
    Targeted URL scraping — collect from specific URLs defined in the topic.

    The topic's `target_urls` field drives which URLs to scrape.
    Each URL is fetched, parsed with BS4, and relevant content is extracted.
    """
    channel = "web_scrape"

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        if not keywords:
            return self._error("No target URLs specified (pass as keywords)")

        items: list[FetchItem] = []
        errors: list[str] = []
        ac = self.config.auth_config or {}
        content_sel = ac.get("content_selector", "article, .content, main, .article-content, #content")

        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": "GatherInfo/0.4"},
            follow_redirects=True,
        ) as client:
            for url in keywords:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    title = _extract_title(soup)
                    body = _extract_body(soup, content_sel)
                    items.append(FetchItem(
                        title=title or url,
                        content=body[:5000],
                        url=url,
                        summary=body[:500],
                        language=_detect_lang(url, body),
                        suggested_tags=_build_tags(title or "", body),
                        raw_metadata={"engine": "targeted_scrape"},
                    ))
                    await asyncio.sleep(1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0)
                except Exception as exc:
                    errors.append(f"{url[:60]}: {exc}")

        return _result(self._new_run_id(), self.config.id, items, errors)

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(run_id=self._new_run_id(), source_id=self.config.id,
                             status=JobStatus.FAILED, items=[], error_log=[msg])


# ── Shared helpers ───────────────────────────────────────────────────────────

def _result(run_id: str, source_id: str, items: list[FetchItem], errors: list[str]) -> CollectResult:
    st = JobStatus.COMPLETED
    if not items and errors:
        st = JobStatus.FAILED
    elif errors:
        st = JobStatus.PARTIAL
    return CollectResult(run_id=run_id, source_id=source_id, status=st,
                         items=items, items_new=len(items), items_failed=len(errors),
                         error_log=errors if errors else None)


def _infer_cat(title: str, content: str) -> str | None:
    text = f"{title} {content}"[:500].lower()
    for kws, cat in [
        (["关税", "tariff", "税率", "duty"], "tariff"),
        (["法规", "regulation", "政策", "law"], "regulation"),
        (["贸易", "trade", "export", "进口", "出口"], "trade"),
        (["技术", "technology", "ai", "芯片", "半导体"], "technology"),
        (["能源", "energy", "oil", "solar", "光伏"], "energy"),
    ]:
        if any(k in text for k in kws):
            return cat
    return "general"


def _build_tags(title: str, content: str) -> list[str]:
    text = f"{title} {content}"[:1000].lower()
    tags = []
    tag_map = {
        "product:battery": ["电池", "battery", "锂电"],
        "product:solar": ["光伏", "solar"],
        "product:semiconductor": ["芯片", "半导体", "semiconductor"],
        "product:ev": ["电动汽车", "新能源车", "电动"],
        "product:steel": ["钢", "steel"],
        "country:cn": ["中国", "china"],
        "country:us": ["美国", "united states"],
        "country:eu": ["欧盟", "european union"],
        "event:tariff": ["关税", "tariff", "税率"],
        "event:regulation": ["法规", "regulation", "政策"],
        "event:sanction": ["制裁", "sanction"],
    }
    for tid, kws in tag_map.items():
        if any(k in text for k in kws):
            tags.append(tid)
    return tags[:8]


def _detect_lang(url: str, text: str) -> str:
    import re
    combined = f"{url} {text}"[:500]
    cjk = len(re.findall(r'[一-鿿]', combined))
    return "zh" if cjk > 3 else "en"


def _extract_title(soup) -> str:
    for sel in ["h1", "title", "meta[property='og:title']", ".article-title"]:
        el = soup.select_one(sel)
        if el:
            return el.get("content", "") or el.get_text(strip=True)
    return ""


def _extract_body(soup, content_sel: str) -> str:
    for tag in soup.select("script, style, nav, footer, .ad, .sidebar"):
        tag.decompose()
    el = soup.select_one(content_sel) if content_sel else None
    if el:
        return el.get_text(separator="\n", strip=True)[:5000]
    return soup.get_text(separator="\n", strip=True)[:5000]
