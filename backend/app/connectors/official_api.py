"""
Official API connector — WTO ePing, EUR-Lex, China Customs, UN Comtrade.
"""
import os
import asyncio
from urllib.parse import urljoin

import httpx

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)


@register_collector("official")
class OfficialAPICollector(BaseCollector):
    channel = "official"

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        ac = self.config.auth_config or {}
        atype = ac.get("type", "generic")

        handlers = {
            "wto_eping": self._fetch_wto_eping,
            "eurlex": self._fetch_eurlex,
            "cn_customs": self._fetch_cn_customs,
            "cn_mofcom": self._fetch_cn_mofcom,
            "un_comtrade": self._fetch_un_comtrade,
            "generic": self._fetch_generic,
        }
        return await handlers.get(atype, self._fetch_generic)(keywords, max_items)

    # ── WTO ePing ────────────────────────────────────────────────────────

    async def _fetch_wto_eping(self, keywords: list[str], max_items: int) -> CollectResult:
        items: list[FetchItem] = []
        errors: list[str] = []

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            try:
                resp = await client.get(
                    "https://eping.wto.org/api/v1/notifications",
                    params={"size": min(max_items, 50), "sort": "notificationDate,desc",
                            "keyword": " ".join(keywords) if keywords else None},
                )
                resp.raise_for_status()
                data = resp.json()
                for n in data.get("content", data.get("notifications", [])):
                    items.append(FetchItem(
                        title=n.get("title", "") or n.get("description", "")[:200],
                        content=n.get("description", ""),
                        url=f"https://eping.wto.org/en/Notification/{n.get('id', '')}",
                        published_at=n.get("notificationDate"),
                        language="en", category="tbt_sps",
                        suggested_tags=["channel:wto_eping"],
                        quality_score=0.9,
                        raw_metadata={"api": "wto_eping", "id": n.get("id")},
                    ))
            except Exception as exc:
                errors.append(str(exc))

        return _result(self._new_run_id(), self.config.id, items, errors)

    # ── EUR-Lex ──────────────────────────────────────────────────────────

    async def _fetch_eurlex(self, keywords: list[str], max_items: int) -> CollectResult:
        items: list[FetchItem] = []
        errors: list[str] = []

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            try:
                resp = await client.get(
                    "https://eur-lex.europa.eu/search.html",
                    params={
                        "type": "advanced", "DTS_SUBDOM": "LEGISLATION",
                        "q": " ".join(keywords), "pageSize": min(max_items, 20), "lang": "en",
                    },
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 200 and "application/json" in resp.headers.get("Content-Type", ""):
                    for doc in resp.json().get("documents", resp.json().get("results", [])):
                        if isinstance(doc, dict):
                            items.append(FetchItem(
                                title=doc.get("title", ""),
                                url=f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri={doc.get('uri', '')}",
                                content=doc.get("description", ""),
                                published_at=doc.get("date"),
                                language="en", category="regulation",
                                suggested_tags=["channel:eurlex"],
                                quality_score=0.85,
                            ))
            except Exception as exc:
                errors.append(str(exc))

        return _result(self._new_run_id(), self.config.id, items, errors)

    # ── China Customs ────────────────────────────────────────────────────

    async def _fetch_cn_customs(self, keywords: list[str], max_items: int) -> CollectResult:
        items: list[FetchItem] = []
        errors: list[str] = []
        ac = self.config.auth_config or {}

        urls = [
            "http://www.customs.gov.cn/customs/302249/302266/index.html",
            "http://www.customs.gov.cn/customs/302249/zfxxgk/zfxxgkml34/index.html",
        ]

        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"},
        ) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    sel = ac.get("item_selector", "a[href]")
                    for link in soup.select(sel)[:max_items]:
                        text = link.get_text(strip=True)
                        href = link.get("href", "")
                        if len(text) < 6:
                            continue
                        full_url = urljoin(url, href) if href else ""
                        items.append(FetchItem(
                            title=text, url=full_url, content=text,
                            language="zh", category="regulation",
                            suggested_tags=["source:cn_customs", "country:cn"],
                            quality_score=0.8,
                            raw_metadata={"source": "cn_customs"},
                        ))
                except Exception as exc:
                    errors.append(f"cn_customs: {str(exc)[:80]}")
                await asyncio.sleep(0.5)

        return _result(self._new_run_id(), self.config.id, items, errors)

    # ── China MOFCOM ─────────────────────────────────────────────────────

    async def _fetch_cn_mofcom(self, keywords: list[str], max_items: int) -> CollectResult:
        items: list[FetchItem] = []
        errors: list[str] = []

        urls = [
            "http://www.mofcom.gov.cn/article/zwgk/bnjg/",
        ]

        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"},
        ) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    for link in soup.select("a[href]")[:max_items]:
                        text = link.get_text(strip=True)
                        href = link.get("href", "")
                        if len(text) < 8:
                            continue
                        items.append(FetchItem(
                            title=text, url=urljoin(url, href) if href else "",
                            content=text, language="zh", category="policy",
                            suggested_tags=["source:cn_mofcom", "country:cn"],
                            quality_score=0.8,
                            raw_metadata={"source": "cn_mofcom"},
                        ))
                except Exception as exc:
                    errors.append(f"cn_mofcom: {str(exc)[:80]}")
                await asyncio.sleep(0.5)

        return _result(self._new_run_id(), self.config.id, items, errors)

    # ── UN Comtrade ──────────────────────────────────────────────────────

    async def _fetch_un_comtrade(self, keywords: list[str], max_items: int) -> CollectResult:
        apikey = os.getenv("COMTRADE_API_KEY", "")
        if not apikey:
            return _result(self._new_run_id(), self.config.id, [], ["COMTRADE_API_KEY not set"])

        items: list[FetchItem] = []
        errors: list[str] = []

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            try:
                resp = await client.get(
                    "https://comtradeapi.un.org/data/v1/get/C/A/HS",
                    params={"subscription-key": apikey, "reporterCode": "all",
                            "period": "2025,2026", "maxRecords": min(max_items, 50)},
                )
                resp.raise_for_status()
                for rec in resp.json().get("data", [])[:max_items]:
                    items.append(FetchItem(
                        title=f"HS {rec.get('cmdCode', '')} - {rec.get('cmdDesc', '')}",
                        content=str(rec), language="en", category="trade_data",
                        suggested_tags=[f"hs:{rec.get('cmdCode', '')}"],
                        quality_score=0.75,
                        raw_metadata={"api": "un_comtrade", "record": rec},
                    ))
            except Exception as exc:
                errors.append(str(exc))

        return _result(self._new_run_id(), self.config.id, items, errors)

    # ── Generic REST ─────────────────────────────────────────────────────

    async def _fetch_generic(self, keywords: list[str], max_items: int) -> CollectResult:
        if not self.config.api_endpoint:
            return _result(self._new_run_id(), self.config.id, [], ["api_endpoint not configured"])

        items: list[FetchItem] = []
        errors: list[str] = []

        headers = {"Accept": "application/json"}
        api_key = os.getenv(self.config.api_key_ref or "", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            try:
                resp = await client.get(
                    self.config.api_endpoint,
                    params={"q": " ".join(keywords)} if keywords else {},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                results = data if isinstance(data, list) else data.get("results", data.get("data", []))
                for r in results[:max_items]:
                    if isinstance(r, dict):
                        items.append(FetchItem(
                            title=r.get("title", r.get("name", str(r)[:100])),
                            content=str(r), url=r.get("url", r.get("link", "")),
                            published_at=r.get("date", r.get("published", "")),
                            raw_metadata={"api": "generic", "record": r},
                        ))
            except Exception as exc:
                errors.append(str(exc))

        return _result(self._new_run_id(), self.config.id, items, errors)


def _result(run_id: str, source_id: str, items: list[FetchItem], errors: list[str]) -> CollectResult:
    status = JobStatus.COMPLETED
    if not items and errors:
        status = JobStatus.FAILED
    elif errors:
        status = JobStatus.PARTIAL
    return CollectResult(
        run_id=run_id, source_id=source_id, status=status,
        items=items, items_new=len(items), items_failed=len(errors),
        error_log=errors if errors else None,
    )
