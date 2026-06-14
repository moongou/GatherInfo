"""Local content quality checks and lightweight structure extraction."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.connectors.base import FetchItem


NOISE_TOKENS = {
    "首页", "登录", "注册", "版权", "菜单", "导航", "更多", "返回", "搜索",
    "home", "login", "register", "copyright", "menu", "navigation",
    "subscribe", "cookie", "privacy", "terms",
}

COUNTRY_PATTERNS = {
    "United States": ("United States", "U.S.", "US ", "USA", "美国"),
    "China": ("China", "Chinese", "中国", "中方"),
    "European Union": ("European Union", "EU ", "欧盟"),
    "Japan": ("Japan", "日本"),
    "Canada": ("Canada", "加拿大"),
    "Mexico": ("Mexico", "墨西哥"),
}


@dataclass(frozen=True)
class ParsedContent:
    content: str
    summary: str
    entities: dict[str, Any]
    metadata: dict[str, Any]
    is_meaningful: bool


def parse_fetch_item(item: FetchItem) -> ParsedContent:
    """Normalize content and extract enough structure for local persistence."""
    title = _normalize_text(item.title)
    content = _normalize_text(item.content or item.summary or "")
    summary = _normalize_text(item.summary or _make_summary(content or title))
    combined = " ".join(part for part in (title, summary, content) if part)
    substantive_tokens = _substantive_tokens(combined)
    is_meaningful = _is_meaningful(title, content, substantive_tokens)
    entities = _merge_entities(item.entities, _extract_entities(combined))
    metadata = _merge_metadata(item.raw_metadata, combined, substantive_tokens)
    return ParsedContent(
        content=content,
        summary=summary,
        entities=entities,
        metadata=metadata,
        is_meaningful=is_meaningful,
    )


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", str(value))
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _make_summary(text: str, limit: int = 220) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].strip() + "..."


def _substantive_tokens(text: str) -> list[str]:
    raw_tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    return [token for token in raw_tokens if token and token not in NOISE_TOKENS]


def _is_meaningful(title: str, content: str, tokens: list[str]) -> bool:
    if not title and not content:
        return False
    title_tokens = _substantive_tokens(title)
    has_meaningful_title = any(len(token) >= 3 for token in title_tokens)
    if has_meaningful_title:
        return True
    if len(tokens) >= 3:
        return True
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", f"{title}{content}")
    return len(cjk_chars) >= 8 and len(tokens) >= 2


def _extract_entities(text: str) -> dict[str, Any]:
    countries = [
        name for name, patterns in COUNTRY_PATTERNS.items()
        if any(pattern in text for pattern in patterns)
    ]
    years = sorted(set(re.findall(r"\b(?:19|20)\d{2}\b", text)))
    numbers = re.findall(r"\b\d+(?:\.\d+)?%?\b", text)[:20]
    return {
        "countries": countries,
        "years": years,
        "numbers": numbers,
    }


def _merge_entities(existing: dict | None, extracted: dict[str, Any]) -> dict[str, Any]:
    base = existing if isinstance(existing, dict) else {}
    return {
        **base,
        "countries": list(dict.fromkeys([*(base.get("countries") or []), *extracted["countries"]])),
        "years": list(dict.fromkeys([*(base.get("years") or []), *extracted["years"]])),
        "numbers": list(dict.fromkeys([*(base.get("numbers") or []), *extracted["numbers"]])),
    }


def _merge_metadata(
    existing: dict | None, text: str, tokens: list[str],
) -> dict[str, Any]:
    base = existing if isinstance(existing, dict) else {}
    return {
        **base,
        "content_analysis": {
            "char_count": len(text),
            "word_count": len(tokens),
            "unique_word_count": len(set(tokens)),
        },
    }
