"""
Tavily Search connector for GatherInfo.
"""
import logging
import os
import asyncio

import httpx

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)
from app.connectors._helpers import detect_lang, infer_category, build_tags, result

logger = logging.getLogger(__name__)


@register_collector("api_search")
class TavilyCollector(BaseCollector):
    channel = "api_search"
    BASE_URL = "https://api.tavily.com/search"

    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("TAVILY_API_KEY", "")

    async def validate(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.BASE_URL, json={
                    "api_key": self.api_key, "query": "test", "max_results": 1,
                })
                return resp.status_code == 200
        except Exception:
            return False

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        if not self.api_key:
            logger.warning("TAVILY_API_KEY not set for source %s", self.config.id)
            return CollectResult(
                run_id=self._new_run_id(), source_id=self.config.id,
                status=JobStatus.FAILED, items=[],
                error_log=["TAVILY_API_KEY not set"],
            )

        queries = keywords or self.config.default_keywords or ["global trade news"]
        items: list[FetchItem] = []
        errors: list[str] = []
        per_query = min(20, max_items // max(1, len(queries)))

        include_domains = _build_domain_filter(self.config.default_categories)
        include_domains_param = include_domains if include_domains else None

        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            limits=httpx.Limits(max_connections=3),
        ) as client:
            for query in queries:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.post(self.BASE_URL, json={
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "max_results": per_query,
                        "include_answer": False,
                        "include_raw_content": False,
                        "include_domains": include_domains_param,
                    })
                    if resp.status_code == 429:
                        errors.append(f"Rate limited: {query}")
                        logger.warning("Tavily rate limited for query: %s", query[:60])
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                    for r in data.get("results", []):
                        title = r.get("title", "")
                        content = r.get("content", "")
                        url = r.get("url", "")

                        pub_date = r.get("published_date", None)
                        if pub_date and isinstance(pub_date, str):
                            try:
                                from datetime import timezone, datetime
                                dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                                pub_date = dt.isoformat()
                            except (ValueError, TypeError):
                                pub_date = None

                        items.append(FetchItem(
                            title=title,
                            content=content,
                            url=url,
                            published_at=pub_date,
                            summary=content[:500] if content else None,
                            language=detect_lang(f"{url} {content}"),
                            category=infer_category(title, content),
                            suggested_tags=build_tags(title, content),
                            quality_score=r.get("score", 0.5),
                            relevance_score=r.get("score", 0.5),
                            raw_metadata={"engine": "tavily", "query": query,
                                          "score": r.get("score")},
                        ))

                    await asyncio.sleep(
                        1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0)

                except Exception as exc:
                    msg = f"Query '{query[:40]}': {exc}"
                    errors.append(msg)
                    logger.error("Tavily fetch error for source %s: %s", self.config.id, exc)

        logger.info("Tavily: %d items, %d errors for source %s",
                     len(items), len(errors), self.config.id)
        return result(self._new_run_id(), self.config.id, items, errors)


def _build_domain_filter(categories: list | None) -> list[str] | None:
    if not categories:
        return None
    domain_map = {
        "trade": ["wto.org", "trade.ec.europa.eu", "customs.gov.cn", "mofcom.gov.cn"],
        "regulation": ["eur-lex.europa.eu", "federalregister.gov", "gov.cn"],
        "china_official": ["gov.cn", "customs.gov.cn", "mofcom.gov.cn"],
        "finance": ["reuters.com", "bloomberg.com", "ft.com"],
    }
    domains = []
    for cat in categories:
        domains.extend(domain_map.get(cat, []))
    return list(set(domains)) if domains else None
