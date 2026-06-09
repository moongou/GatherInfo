"""
Web scraper connector for GatherInfo.
"""
import logging
import re
import asyncio
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)
from app.connectors._helpers import detect_lang, infer_category, build_tags

logger = logging.getLogger(__name__)


@register_collector("web_scrape")
class WebScrapeCollector(BaseCollector):
    channel = "web_scrape"

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        if not self.config.base_url:
            logger.warning("base_url not configured for source %s", self.config.id)
            return self._error("base_url not configured")

        cfg = self.config
        ac = cfg.auth_config or {}
        urls = _build_urls(cfg.base_url, ac.get("max_pages", 5))

        items: list[FetchItem] = []
        errors: list[str] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(
            timeout=cfg.timeout_seconds,
            headers=_scrape_headers(),
            follow_redirects=True,
        ) as client:
            for url in urls:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "lxml")

                    item_sel = ac.get("item_selector", "article, .news-item, .list-item, li, tr")
                    for el in soup.select(item_sel):
                        if len(items) >= max_items:
                            break

                        title_el = el.select_one("a[href], h2 a, h3 a, .title a, h1, h2, h3, .title")
                        title = title_el.get_text(strip=True) if title_el else ""
                        if not title or len(title) < 4:
                            continue

                        link_el = el.select_one("a[href]")
                        href = link_el.get("href", "") if link_el else ""
                        if href and not href.startswith("http"):
                            href = urljoin(cfg.base_url, href)

                        if href in seen:
                            continue
                        seen.add(href)

                        date_el = el.select_one("time, .date, .pub-date, span.date, [datetime]")
                        published = None
                        if date_el:
                            dt_text = date_el.get("datetime", "") or date_el.get_text(strip=True)
                            published = _parse_date(dt_text)

                        if not _matches(title, "", keywords):
                            continue

                        content = ""
                        if href and ac.get("fetch_detail", True):
                            try:
                                detail_resp = await client.get(href)
                                detail_soup = BeautifulSoup(detail_resp.text, "lxml")
                                content_sel = ac.get(
                                    "content_selector",
                                    "article, .content, .article-content, #content, main")
                                content_el = detail_soup.select_one(content_sel)
                                if content_el:
                                    for t in content_el.select("script, style, nav, .nav"):
                                        t.decompose()
                                    content = content_el.get_text(
                                        separator="\n", strip=True)[:5000]
                                await asyncio.sleep(
                                    1.0 / cfg.rate_limit_rps if cfg.rate_limit_rps else 1.0)
                            except Exception:
                                pass

                        items.append(FetchItem(
                            title=title, content=content, url=href,
                            summary=(content or title)[:500],
                            published_at=published,
                            language=detect_lang(f"{title} {content}"),
                            category=infer_category(title, content),
                            suggested_tags=build_tags(title, content),
                            quality_score=0.7,
                            relevance_score=0.6,
                            raw_metadata={"source_url": href or cfg.base_url},
                        ))

                    await asyncio.sleep(
                        1.0 / cfg.rate_limit_rps if cfg.rate_limit_rps else 1.0)

                except Exception as exc:
                    msg = f"{url[:60]}: {exc}"
                    errors.append(msg)
                    logger.error("Web scrape error for source %s url %s: %s",
                                 self.config.id, url[:80], exc)

        status = JobStatus.COMPLETED if not errors else JobStatus.PARTIAL
        if not items and errors:
            status = JobStatus.FAILED

        logger.info("WebScrape: %d items, %d errors for source %s",
                     len(items), len(errors), self.config.id)
        return CollectResult(
            run_id=self._new_run_id(), source_id=cfg.id,
            status=status, items=items, items_new=len(items),
            items_failed=len(errors), error_log=errors if errors else None,
        )

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(
            run_id=self._new_run_id(), source_id=self.config.id,
            status=JobStatus.FAILED, items=[], error_log=[msg],
        )


# ── helpers ──────────────────────────────────────────────────────────────────

def _scrape_headers() -> dict:
    return {
        "User-Agent": "GatherInfo/0.3 (Global Monitor; contact@example.com)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def _build_urls(base: str, max_pages: int) -> list[str]:
    urls = [base]
    for i in range(2, max_pages + 1):
        urls.append(f"{base.rstrip('/')}/page/{i}")
        urls.append(f"{base.rstrip('/')}?page={i}")
    return urls


def _matches(title: str, content: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = f"{title} {content}".lower()
    return any(kw.lower() in text for kw in keywords)


_CN_PATTERNS = [
    (r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", None),
    (r"(\d{4})年(\d{1,2})月(\d{1,2})日", None),
]


def _parse_date(text: str) -> str | None:
    if not text:
        return None
    for pat, _ in _CN_PATTERNS:
        m = re.search(pat, text)
        if m:
            try:
                parts = [int(x) for x in m.groups()]
                return datetime(parts[0], parts[1], parts[2], tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass
    return None
