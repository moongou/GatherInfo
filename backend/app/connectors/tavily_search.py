"""
Tavily Search connector for GatherInfo.
"""
import os
import asyncio

import httpx

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)


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
            return CollectResult(
                run_id=self._new_run_id(), source_id=self.config.id,
                status=JobStatus.FAILED, items=[], error_log=["TAVILY_API_KEY not set"],
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
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                    for r in data.get("results", []):
                        title = r.get("title", "")
                        content = r.get("content", "")
                        url = r.get("url", "")

                        items.append(FetchItem(
                            title=title,
                            content=content,
                            url=url,
                            summary=content[:500] if content else None,
                            language=_detect_lang(url, content),
                            category=_infer_category(title, content),
                            suggested_tags=_build_tags(title, content),
                            quality_score=r.get("score", 0.5),
                            relevance_score=r.get("score", 0.5),
                            raw_metadata={"engine": "tavily", "query": query, "score": r.get("score")},
                        ))

                    await asyncio.sleep(1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0)

                except Exception as exc:
                    errors.append(f"Query '{query[:40]}': {exc}")

        status = JobStatus.COMPLETED
        if errors and not items:
            status = JobStatus.FAILED
        elif errors:
            status = JobStatus.PARTIAL

        return CollectResult(
            run_id=self._new_run_id(), source_id=self.config.id,
            status=status, items=items, items_new=len(items),
            items_failed=len(errors), error_log=errors if errors else None,
        )


# ── helpers ──────────────────────────────────────────────────────────────────

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


def _detect_lang(url: str, content: str) -> str:
    combined = f"{url} {content}"[:500].lower()
    cn_indicators = [".cn/", "gov.cn", "中国", "国家", "海关", "商务部", "编码", "通知"]
    if any(ind.lower() in combined for ind in cn_indicators):
        return "zh"
    return "en"


def _infer_category(title: str, content: str) -> str | None:
    text = f"{title} {content}"[:500].lower()
    cat_keywords = {
        "tariff": ["tariff", "duty", "customs", "关税", "海关", "税则"],
        "regulation": ["regulation", "law", "policy", "directive", "法规", "政策", "公告"],
        "trade": ["trade", "export", "import", "贸易", "出口", "进口"],
        "technology": ["ai", "semiconductor", "chip", "人工智能", "芯片", "半导体"],
        "energy": ["energy", "oil", "gas", "solar", "能源", "石油", "光伏"],
        "agriculture": ["agriculture", "food", "grain", "农业", "食品", "粮食"],
        "finance": ["stock", "bond", "rate", "央行", "利率", "金融"],
        "security": ["sanction", "control", "sanction", "制裁", "管制", "出口管制"],
    }
    for cat, kws in cat_keywords.items():
        if any(kw in text for kw in kws):
            return cat
    return "general"


def _build_tags(title: str, content: str) -> list[str]:
    """Best-effort tag extraction from text."""
    text = f"{title} {content}"[:1000].lower()
    tags = []
    tag_map = {
        "product:battery": ["电池", "battery"],
        "product:solar": ["光伏", "solar panel", "太阳能"],
        "product:ev": ["电动汽车", "新能源车", "electric vehicle"],
        "product:semiconductor": ["芯片", "半导体", "semiconductor"],
        "product:steel": ["钢", "steel"],
        "product:agriculture": ["农产", "agricultur"],
        "product:seafood": ["水产", "seafood", "鱼"],
        "country:cn": ["中国", "china", "beijing"],
        "country:us": ["美国", "united states", "washington"],
        "country:eu": ["欧盟", "european union", "brussels"],
        "event:trade_dispute": ["争端", "dispute", "制裁", "sanction"],
        "event:regulation_change": ["修订", "调整", "新规", "amendment", "new regulation"],
        "event:tariff_change": ["关税调整", "tariff change", "税率"],
    }
    for tag_id, kws in tag_map.items():
        if any(kw.lower() in text for kw in kws):
            tags.append(tag_id)
    return tags[:8]
