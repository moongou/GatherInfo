"""
GatherInfo management API — sources, topics, schedules, collection, items, tags, stats.
"""
import asyncio
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

import httpx
from pydantic import BaseModel
from app.collection_schemas import (
    AutoDiscoverResult, BatchGenerateRequest, BatchGenerateResult,
    CollectRequest, CollectResultOut, ConnectorInfo, DiscoveredProvider,
    ItemListOut, ItemOut,
    ListModelsResult, ModelConfigCreate, ModelConfigOut, ModelConfigUpdate, ModelTestResult,
    ReportGenerateRequest, ReportListOut, ReportOut,
    RunOut, ScheduleCreate, ScheduleOut, SearchToolConfigCreate,
    SearchToolConfigOut, SearchToolConfigUpdate,
    SourceCreate, SourceOut, SourceUpdate,
    StatsOut, TagMergeRequest, TagMergeResult, TagOut, TagStatsOut, TagUpdateIn,
    SystemConfigOut, SystemConfigUpdate,
    TopicCreate, TopicOut, TopicUpdate,
)
from app.database import get_db
from app.engine import CollectionEngine
from app.models import (
    CollectedItem, CollectionRun, ItemStatus,
    ModelConfig, Report, ScheduleConfig, SearchToolConfig,
    SourceConfig, SystemConfig, Tag, Topic, item_tags,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["management"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_punct(text: str | None) -> str:
    """容错：将中文逗号/冒号归一化为英文，便于后续拆分。"""
    if not text:
        return ""
    return text.replace("，", ",").replace("：", ":")


def _normalize_topic_payload(payload: dict) -> dict:
    """容错：归一化 topic 关键词/标签里残留的中文标点，并按逗号拆分关键词。"""
    kws = payload.get("keywords")
    if isinstance(kws, list):
        normalized: list[str] = []
        for k in kws:
            if isinstance(k, str):
                for part in _normalize_punct(k).split(","):
                    part = part.strip()
                    if part and part not in normalized:
                        normalized.append(part)
            else:
                normalized.append(k)
        payload["keywords"] = normalized
    rules = payload.get("auto_tag_rules")
    if isinstance(rules, list):
        for r in rules:
            if isinstance(r, dict):
                if isinstance(r.get("keyword"), str):
                    r["keyword"] = _normalize_punct(r["keyword"])
                if isinstance(r.get("tag"), str):
                    r["tag"] = _normalize_punct(r["tag"])
    kts = payload.get("keyword_tags")
    if isinstance(kts, list):
        expanded: list = []
        for kt in kts:
            if isinstance(kt, dict) and isinstance(kt.get("keyword"), str):
                parts = [p.strip() for p in _normalize_punct(kt["keyword"]).split(",") if p.strip()]
                if len(parts) <= 1:
                    kt["keyword"] = parts[0] if parts else ""
                    expanded.append(kt)
                else:
                    for part in parts:
                        expanded.append({**kt, "keyword": part})
            else:
                expanded.append(kt)
        payload["keyword_tags"] = expanded
    return payload


# Per-channel default connection metadata to power source auto-config in the UI.
# required_fields/optional_fields drive which inputs to show vs. mark "不需填写".
CHANNEL_DEFAULTS: dict[str, dict] = {
    "api_search": {
        "description": "Web 搜索 (Tavily API)",
        "default_base_url": "https://api.tavily.com",
        "default_api_endpoint": "/search",
        "required_fields": ["api_key"],
        "optional_fields": ["base_url", "api_endpoint"],
        "homepage_hint": "https://tavily.com",
    },
    "json_api": {
        "description": "通用 JSON API 直连 (NewsAPI / UN Comtrade / World Bank / Inoreader / Feedly 等)",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url"],
        "optional_fields": ["api_endpoint", "api_key", "auth_config"],
        "homepage_hint": "https://newsapi.org",
    },
    "rss": {
        "description": "RSS/Atom 订阅源",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url"],
        "optional_fields": [],
        "homepage_hint": None,
    },
    "web_scrape": {
        "description": "结构化页面抓取 (CSS 选择器)",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url"],
        "optional_fields": ["auth_config"],
        "homepage_hint": None,
    },
    "official": {
        "description": "官方 API (WTO / EU / 中国海关 / 商务部 / UN Comtrade)",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url"],
        "optional_fields": ["api_endpoint", "auth_config"],
        "homepage_hint": None,
    },
    "commercial": {
        "description": "商业/授权数据 API",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url", "api_key"],
        "optional_fields": ["api_endpoint"],
        "homepage_hint": None,
    },
    "social": {
        "description": "社交媒体监测",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["api_key"],
        "optional_fields": ["base_url"],
        "homepage_hint": None,
    },
    "deepweb": {
        "description": "深网/暗网 (需授权)",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url"],
        "optional_fields": ["auth_config", "api_key"],
        "homepage_hint": None,
    },
    "manual": {
        "description": "手动录入",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": [],
        "optional_fields": [],
        "homepage_hint": None,
    },
}


def _slugify(text: str, max_len: int = 40) -> str:
    """Generate a URL/ID-friendly slug from arbitrary text (incl. CJK)."""
    if not text:
        return ""
    # Transliterate accents; keep CJK as-is (NFKC) then strip to ascii word chars
    normalized = unicodedata.normalize("NFKC", text).strip().lower()
    # Replace whitespace/underscores with hyphen
    slug = re.sub(r"[\s_]+", "-", normalized)
    # Keep ascii alphanumerics and hyphen only; drop the rest (CJK chars removed)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:max_len]


def _gen_id(name: str, prefix_max: int = 40, exists_fn=None) -> str:
    """Build a unique-ish id from name: slug + short hash; fall back to hash-only."""
    base = _slugify(name, prefix_max)
    suffix = uuid4().hex[:6]
    candidate = f"{base}-{suffix}" if base else f"item-{suffix}"
    if exists_fn:
        while exists_fn(candidate):
            candidate = f"{base}-{uuid4().hex[:6]}" if base else f"item-{uuid4().hex[:6]}"
    return candidate


def _item_tags(item: CollectedItem) -> list[dict]:
    return [{"id": t.id, "namespace": t.namespace, "value": t.value, "label": t.label}
            for t in (item.tags or [])]


def _source_names(db: Session, source_ids) -> list[str]:
    if not source_ids:
        return []
    rows = db.query(SourceConfig.id, SourceConfig.name).filter(SourceConfig.id.in_(source_ids)).all()
    name_map = {sid: name for sid, name in rows}
    return [name_map.get(sid, sid) for sid in source_ids]


def _topic_out(db: Session, t: Topic) -> TopicOut:
    out = TopicOut.model_validate(t)
    out.source_names = _source_names(db, t.source_ids)
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Sources
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/sources", response_model=list[SourceOut])
def list_sources(channel: str | None = None, is_active: bool | None = None, db: Session = Depends(get_db)):
    q = db.query(SourceConfig)
    if channel: q = q.filter(SourceConfig.channel == channel)
    if is_active is not None: q = q.filter(SourceConfig.is_active == is_active)
    return q.all()


@router.post("/sources", response_model=SourceOut, status_code=201)
def create_source(data: SourceCreate, db: Session = Depends(get_db)):
    payload = data.model_dump()
    src_id = payload.get("id")
    if not src_id:
        src_id = _gen_id(
            data.name,
            exists_fn=lambda c: db.query(SourceConfig).filter(SourceConfig.id == c).first() is not None,
        )
    elif db.query(SourceConfig).filter(SourceConfig.id == src_id).first():
        raise HTTPException(400, f"信息源 '{src_id}' 已存在")
    payload["id"] = src_id
    try:
        src = SourceConfig(**payload)
        db.add(src); db.commit(); db.refresh(src)
    except Exception as exc:
        db.rollback()
        logger.error("create_source failed: %s", exc)
        raise HTTPException(500, f"创建信息源失败: {exc}")
    return src


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(source_id: str, db: Session = Depends(get_db)):
    src = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if not src: raise HTTPException(404)
    return src


@router.put("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: str, data: SourceUpdate, db: Session = Depends(get_db)):
    src = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if not src: raise HTTPException(404)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(src, k, v)
    db.commit(); db.refresh(src)
    return src


@router.delete("/sources/{source_id}")
def delete_source(source_id: str, db: Session = Depends(get_db)):
    src = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if not src: raise HTTPException(404)
    db.delete(src); db.commit()
    return {"ok": True}


@router.post("/sources/{source_id}/validate")
async def validate_source(source_id: str, db: Session = Depends(get_db)):
    src = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if not src: raise HTTPException(404)
    from app.connectors.base import ConnectorRegistry
    try:
        ok = await ConnectorRegistry.create(src).validate()
    except Exception as exc:
        ok = False
    return {"source_id": source_id, "valid": ok, "error": None if ok else str(exc)}


# ═══════════════════════════════════════════════════════════════════════════════
# Topics
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/topics", response_model=list[TopicOut])
def list_topics(is_active: bool | None = None, db: Session = Depends(get_db)):
    q = db.query(Topic)
    if is_active is not None: q = q.filter(Topic.is_active == is_active)
    return [_topic_out(db, t) for t in q.all()]


@router.post("/topics", response_model=TopicOut, status_code=201)
def create_topic(data: TopicCreate, db: Session = Depends(get_db)):
    payload = _normalize_topic_payload(data.model_dump())
    topic_id = payload.get("id")
    if not topic_id:
        topic_id = _gen_id(
            data.name,
            exists_fn=lambda c: db.query(Topic).filter(Topic.id == c).first() is not None,
        )
    elif db.query(Topic).filter(Topic.id == topic_id).first():
        raise HTTPException(400, f"主题 '{topic_id}' 已存在")
    payload["id"] = topic_id
    try:
        t = Topic(**payload)
        db.add(t); db.commit(); db.refresh(t)
    except Exception as exc:
        db.rollback()
        logger.error("create_topic failed: %s", exc)
        raise HTTPException(500, f"创建主题失败: {exc}")
    return _topic_out(db, t)


@router.get("/topics/{topic_id}", response_model=TopicOut)
def get_topic(topic_id: str, db: Session = Depends(get_db)):
    t = db.query(Topic).filter(Topic.id == topic_id).first()
    if not t: raise HTTPException(404)
    return _topic_out(db, t)


@router.put("/topics/{topic_id}", response_model=TopicOut)
def update_topic(topic_id: str, data: TopicUpdate, db: Session = Depends(get_db)):
    t = db.query(Topic).filter(Topic.id == topic_id).first()
    if not t: raise HTTPException(404)
    try:
        for k, v in _normalize_topic_payload(data.model_dump(exclude_unset=True)).items():
            setattr(t, k, v)
        db.commit(); db.refresh(t)
    except Exception as exc:
        db.rollback()
        logger.error("update_topic failed: %s", exc)
        raise HTTPException(500, f"更新主题失败: {exc}")
    return _topic_out(db, t)


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: str, db: Session = Depends(get_db)):
    t = db.query(Topic).filter(Topic.id == topic_id).first()
    if not t: raise HTTPException(404)
    db.delete(t); db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Schedules
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/schedules", response_model=list[ScheduleOut])
def list_schedules(db: Session = Depends(get_db)):
    return db.query(ScheduleConfig).all()


@router.post("/schedules", response_model=ScheduleOut, status_code=201)
async def create_schedule(data: ScheduleCreate, db: Session = Depends(get_db)):
    if db.query(ScheduleConfig).filter(ScheduleConfig.id == data.id).first():
        raise HTTPException(400, f"Schedule '{data.id}' exists")
    s = ScheduleConfig(**data.model_dump())
    db.add(s); db.commit(); db.refresh(s)

    from app.scheduler import scheduler_instance
    if scheduler_instance:
        await scheduler_instance.add_schedule(s)
    return s


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, db: Session = Depends(get_db)):
    s = db.query(ScheduleConfig).filter(ScheduleConfig.id == schedule_id).first()
    if not s: raise HTTPException(404)
    db.delete(s); db.commit()
    from app.scheduler import scheduler_instance
    if scheduler_instance:
        await scheduler_instance.remove_schedule(schedule_id)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Collection
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/collect", response_model=list[CollectResultOut])
async def run_collection(data: CollectRequest, db: Session = Depends(get_db)):
    engine = CollectionEngine(db)

    if data.topic_id:
        try:
            results = await engine.collect_topic(data.topic_id)
        except ValueError as e:
            raise HTTPException(400, str(e))
    elif data.source_id:
        keywords = data.keywords or []
        r = await engine.collect_from_source(data.source_id, keywords)
        results = [r]
    else:
        raise HTTPException(400, "Specify topic_id or source_id")

    out = []
    for r in results:
        run = db.query(CollectionRun).filter(CollectionRun.id == r.run_id).first()
        out.append(CollectResultOut(
            run=RunOut.model_validate(run) if run else RunOut(
                id=r.run_id, source_id=r.source_id, status=r.status.value or "unknown",
                items_found=len(r.items), items_new=r.items_new, items_failed=r.items_failed,
                error_log=r.error_log,
            ),
            total_items=len(r.items), items_new=r.items_new,
            errors=r.error_log,
        ))
    return out


@router.post("/schedules/{schedule_id}/run-now", response_model=list[CollectResultOut])
async def run_schedule_now(schedule_id: str, db: Session = Depends(get_db)):
    engine = CollectionEngine(db)
    results = await engine.execute_schedule(schedule_id)
    out = []
    for r in results:
        run = db.query(CollectionRun).filter(CollectionRun.id == r.run_id).first()
        out.append(CollectResultOut(
            run=RunOut.model_validate(run) if run else RunOut(
                id=r.run_id, source_id=r.source_id, status=r.status.value or "unknown",
            ),
            total_items=len(r.items), items_new=r.items_new,
            errors=r.error_log,
        ))
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Items
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/runs", response_model=list[RunOut])
def list_runs(
    topic_id: str | None = None,
    source_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List recent collection runs (optionally scoped by topic/source)."""
    q = db.query(CollectionRun)
    if topic_id:
        q = q.filter(CollectionRun.topic_id == topic_id)
    if source_id:
        q = q.filter(CollectionRun.source_id == source_id)
    return q.order_by(CollectionRun.created_at.desc()).limit(limit).all()

@router.get("/items", response_model=ItemListOut)
def list_items(
    topic_id: str | None = None,
    source_id: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    language: str | None = None,
    q: str | None = Query(default=None, description="Full-text search in title/content"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(CollectedItem)

    if topic_id:
        query = query.filter(CollectedItem.topic_id == topic_id)
    if source_id:
        query = query.filter(CollectedItem.source_id == source_id)
    if category:
        query = query.filter(CollectedItem.category == category)
    if status:
        query = query.filter(CollectedItem.status == status)
    if language:
        query = query.filter(CollectedItem.language == language)
    if q:
        query = query.filter(
            (CollectedItem.title.ilike(f"%{q}%")) |
            (CollectedItem.content.ilike(f"%{q}%"))
        )

    # Tag filter: join through item_tags
    if tag:
        query = query.filter(
            CollectedItem.tags.any(Tag.id == tag)
        )

    total = query.count()
    items = (
        query.order_by(CollectedItem.collected_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ItemListOut(
        items=[ItemOut(
            id=it.id,
            source_id=it.source_id,
            title=it.title,
            content=it.content,
            summary=it.summary,
            url=it.url,
            language=it.language,
            category=it.category,
            tags=_item_tags(it),
            entities=it.entities,
            quality_score=it.quality_score or 0,
            relevance_score=it.relevance_score or 0,
            status=it.status.value if it.status else "raw",
            collected_at=it.collected_at,
            published_at=it.published_at,
        ) for it in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: str, db: Session = Depends(get_db)):
    it = db.query(CollectedItem).filter(CollectedItem.id == item_id).first()
    if not it: raise HTTPException(404)
    return ItemOut(
        id=it.id, source_id=it.source_id, title=it.title,
        content=it.content, summary=it.summary, url=it.url,
        language=it.language, category=it.category, tags=_item_tags(it),
        entities=it.entities, quality_score=it.quality_score or 0,
        relevance_score=it.relevance_score or 0,
        status=it.status.value if it.status else "raw",
        collected_at=it.collected_at, published_at=it.published_at,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Tags
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/tags", response_model=list[TagOut])
def list_tags(
    namespace: str | None = None,
    sort_by: str = "item_count",
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = db.query(Tag)
    if namespace: q = q.filter(Tag.namespace == namespace)
    if sort_by == "item_count":
        q = q.order_by(Tag.item_count.desc())
    elif sort_by == "recent":
        q = q.order_by(Tag.last_seen_at.desc().nullslast())
    else:
        q = q.order_by(Tag.value.asc())
    return q.limit(limit).all()


@router.get("/tags/stats", response_model=list[TagStatsOut])
def tag_stats(db: Session = Depends(get_db)):
    """Per-tag statistics: item counts, category/language/source breakdown."""
    tags = db.query(Tag).order_by(Tag.item_count.desc()).limit(50).all()
    result = []
    for tag in tags:
        items = tag.items
        cats: dict[str, int] = {}
        langs: dict[str, int] = {}
        srcs: dict[str, int] = {}
        for it in items:
            if it.category:
                cats[it.category] = cats.get(it.category, 0) + 1
            if it.language:
                langs[it.language] = langs.get(it.language, 0) + 1
            if it.source_id:
                srcs[it.source_id] = srcs.get(it.source_id, 0) + 1
        result.append(TagStatsOut(
            tag_id=tag.id, namespace=tag.namespace, value=tag.value,
            item_count=tag.item_count, last_seen_at=tag.last_seen_at,
            categories=cats, languages=langs, sources=srcs,
        ))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    last = db.query(CollectedItem).order_by(CollectedItem.collected_at.desc()).first()
    return StatsOut(
        total_sources=db.query(SourceConfig).count(),
        active_sources=db.query(SourceConfig).filter(SourceConfig.is_active == True).count(),
        total_topics=db.query(Topic).count(),
        active_topics=db.query(Topic).filter(Topic.is_active == True).count(),
        total_items=db.query(CollectedItem).count(),
        items_today=db.query(CollectedItem).filter(CollectedItem.collected_at >= today).count(),
        total_tags=db.query(Tag).count(),
        total_schedules=db.query(ScheduleConfig).filter(ScheduleConfig.is_active == True).count(),
        last_collection_at=last.collected_at if last else None,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Connectors
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/connectors", response_model=list[ConnectorInfo])
def list_connectors():
    from app.connectors.base import ConnectorRegistry
    out = []
    for ch in ConnectorRegistry.available_channels():
        meta = CHANNEL_DEFAULTS.get(ch, {})
        out.append(ConnectorInfo(
            channel=ch,
            description=meta.get("description", ""),
            default_base_url=meta.get("default_base_url") or None,
            default_api_endpoint=meta.get("default_api_endpoint") or None,
            required_fields=meta.get("required_fields", []),
            optional_fields=meta.get("optional_fields", []),
            homepage_hint=meta.get("homepage_hint"),
        ))
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Seed defaults
# ═══════════════════════════════════════════════════════════════════════════════

# ── Tag Management ────────────────────────────────────────────────────────

@router.put("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: str, data: TagUpdateIn, db: Session = Depends(get_db)):
    t = db.query(Tag).filter(Tag.id == tag_id).first()
    if not t: raise HTTPException(404)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit(); db.refresh(t)
    return t


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: str, db: Session = Depends(get_db)):
    t = db.query(Tag).filter(Tag.id == tag_id).first()
    if not t: raise HTTPException(404)
    db.delete(t); db.commit()
    return {"ok": True}


@router.post("/tags/merge", response_model=TagMergeResult)
def merge_tags(data: TagMergeRequest, db: Session = Depends(get_db)):
    """Merge source_tag into target_tag: move all item associations, then delete source."""
    if data.source_tag_id == data.target_tag_id:
        raise HTTPException(400, "源标签与目标标签不能相同")
    source = db.query(Tag).filter(Tag.id == data.source_tag_id).first()
    target = db.query(Tag).filter(Tag.id == data.target_tag_id).first()
    if not source:
        raise HTTPException(404, f"源标签不存在: {data.source_tag_id}")
    if not target:
        raise HTTPException(404, f"目标标签不存在: {data.target_tag_id}")

    try:
        # Item ids already linked to target (to avoid duplicate PK on insert)
        target_item_ids = {
            row[0] for row in db.query(item_tags.c.item_id)
            .filter(item_tags.c.tag_id == target.id).all()
        }
        source_links = db.query(item_tags.c.item_id).filter(item_tags.c.tag_id == source.id).all()
        moved = 0
        for (item_id,) in source_links:
            if item_id in target_item_ids:
                continue
            db.execute(item_tags.insert().values(item_id=item_id, tag_id=target.id))
            target_item_ids.add(item_id)
            moved += 1
        # Remove all source associations + the source tag itself
        db.execute(item_tags.delete().where(item_tags.c.tag_id == source.id))
        deleted_id = source.id
        db.delete(source)
        # Recompute target item_count
        target.item_count = db.query(item_tags.c.item_id).filter(item_tags.c.tag_id == target.id).count()
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("merge_tags failed: %s", exc)
        raise HTTPException(500, f"标签合并失败: {exc}")

    return TagMergeResult(target_tag_id=target.id, moved_items=moved, deleted_tag_id=deleted_id)


@router.post("/seed-defaults")
def seed_defaults(db: Session = Depends(get_db)):
    created_sources = 0
    for cfg in _default_sources():
        if not db.query(SourceConfig).filter(SourceConfig.id == cfg["id"]).first():
            db.add(SourceConfig(**cfg))
            created_sources += 1

    created_topics = 0
    for cfg in _default_topics():
        if not db.query(Topic).filter(Topic.id == cfg["id"]).first():
            t = Topic(**cfg)
            # Add enhanced fields
            t.keyword_tags = _default_keyword_tags(cfg["id"])
            t.description_prompt = _default_description_prompt(cfg["id"])
            db.add(t)
            created_topics += 1

    created_models = 0
    for cfg in _default_models():
        if not db.query(ModelConfig).filter(ModelConfig.id == cfg["id"]).first():
            db.add(ModelConfig(**cfg))
            created_models += 1

    created_tools = 0
    for cfg in _default_search_tools():
        if not db.query(SearchToolConfig).filter(SearchToolConfig.id == cfg["id"]).first():
            db.add(SearchToolConfig(**cfg))
            created_tools += 1

    created_tags = 0
    for cfg in _default_tags():
        if not db.query(Tag).filter(Tag.id == cfg["id"]).first():
            db.add(Tag(**cfg))
            created_tags += 1

    db.commit()
    return {
        "sources_created": created_sources,
        "topics_created": created_topics,
        "models_created": created_models,
        "search_tools_created": created_tools,
        "tags_created": created_tags,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Export / Import
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/config/export")
def export_config(db: Session = Depends(get_db)):
    """Export all configuration as JSON."""
    sources = [{"id": s.id, "name": s.name, "channel": s.channel, "is_active": s.is_active,
                "base_url": s.base_url, "api_endpoint": s.api_endpoint,
                "default_keywords": s.default_keywords, "languages": s.languages} for s in db.query(SourceConfig).all()]
    topics_data = []
    for t in db.query(Topic).all():
        td = {"id": t.id, "name": t.name, "description": t.description,
              "keywords": t.keywords, "keyword_tags": t.keyword_tags,
              "description_prompt": t.description_prompt, "source_ids": t.source_ids,
              "target_urls": t.target_urls, "auto_tag_rules": t.auto_tag_rules,
              "schedule_cron": t.schedule_cron, "is_scheduled": t.is_scheduled, "is_active": t.is_active}
        topics_data.append(td)
    models_data = [{"id": m.id, "name": m.name, "provider": m.provider, "base_url": m.base_url,
                     "model_name": m.model_name, "temperature": m.temperature,
                     "max_tokens": m.max_tokens, "top_p": m.top_p,
                     "is_default": m.is_default, "is_active": m.is_active,
                     "description": m.description} for m in db.query(ModelConfig).all()]
    tags_data = [{"id": tg.id, "namespace": tg.namespace, "value": tg.value,
                  "label": tg.label, "color": tg.color} for tg in db.query(Tag).all()]
    schedules_data = [{"id": s.id, "name": s.name, "cron_expression": s.cron_expression,
                       "source_ids": s.source_ids, "topic_ids": s.topic_ids,
                       "is_active": s.is_active} for s in db.query(ScheduleConfig).all()]
    tools_data = [{"id": st.id, "name": st.name, "tool_type": st.tool_type,
                   "is_active": st.is_active, "config_json": st.config_json} for st in db.query(SearchToolConfig).all()]

    return {
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources, "topics": topics_data,
        "models": models_data, "tags": tags_data,
        "schedules": schedules_data, "search_tools": tools_data,
    }


class ImportConflict(BaseModel):
    id: str
    name: str
    existing: dict | None = None
    incoming: dict
    identical: bool = False


@router.post("/config/import")
def import_config(data: dict, db: Session = Depends(get_db)):
    """Import configuration. Expects sections: sources, topics, models, tags, schedules, search_tools."""
    imported = {"sources": 0, "topics": 0, "models": 0, "tags": 0, "schedules": 0, "search_tools": 0}
    conflicts = []
    mode = data.get("mode", "skip")  # skip | overwrite | append

    for item in data.get("sources", []):
        existing = db.query(SourceConfig).filter(SourceConfig.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["name"], existing={"name": existing.name}, incoming=item, identical=existing.name == item.get("name")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            db.add(SourceConfig(**{k: v for k, v in item.items() if hasattr(SourceConfig, k)}))
        imported["sources"] += 1

    for item in data.get("topics", []):
        existing = db.query(Topic).filter(Topic.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["name"], existing={"name": existing.name}, incoming=item, identical=existing.name == item.get("name")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            t = Topic(**{k: v for k, v in item.items() if hasattr(Topic, k)})
            db.add(t)
        imported["topics"] += 1

    for item in data.get("models", []):
        existing = db.query(ModelConfig).filter(ModelConfig.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["name"], existing={"name": existing.name}, incoming=item, identical=existing.name == item.get("name")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            db.add(ModelConfig(**{k: v for k, v in item.items() if hasattr(ModelConfig, k)}))
        imported["models"] += 1

    for item in data.get("tags", []):
        existing = db.query(Tag).filter(Tag.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["value"], existing={"value": existing.value}, incoming=item, identical=existing.value == item.get("value")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            db.add(Tag(**{k: v for k, v in item.items() if hasattr(Tag, k)}))
        imported["tags"] += 1

    for item in data.get("schedules", []):
        existing = db.query(ScheduleConfig).filter(ScheduleConfig.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["name"], existing={"name": existing.name}, incoming=item, identical=existing.name == item.get("name")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            db.add(ScheduleConfig(**{k: v for k, v in item.items() if hasattr(ScheduleConfig, k)}))
        imported["schedules"] += 1

    for item in data.get("search_tools", []):
        existing = db.query(SearchToolConfig).filter(SearchToolConfig.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["name"], existing={"name": existing.name}, incoming=item, identical=existing.name == item.get("name")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            db.add(SearchToolConfig(**{k: v for k, v in item.items() if hasattr(SearchToolConfig, k)}))
        imported["search_tools"] += 1

    db.commit()
    return {"imported": imported, "conflicts": conflicts, "conflict_count": len(conflicts)}


def _default_keyword_tags(topic_id: str) -> list[dict] | None:
    mapping = {
        "global-trade": [
            {"keyword": "关税", "weight": 1.0},
            {"keyword": "贸易政策", "weight": 0.9},
            {"keyword": "tarrif", "weight": 0.9},
            {"keyword": "trade", "weight": 0.8},
            {"keyword": "RCEP", "weight": 0.7},
            {"keyword": "FTA", "weight": 0.7},
        ],
        "tech-regulations": [
            {"keyword": "电池", "weight": 1.0, "tag_id": "product:battery"},
            {"keyword": "光伏", "weight": 0.9, "tag_id": "product:solar"},
            {"keyword": "碳足迹", "weight": 0.9},
            {"keyword": "TBT", "weight": 0.8},
            {"keyword": "SPS", "weight": 0.8},
            {"keyword": "新能源汽车", "weight": 0.8},
        ],
    }
    return mapping.get(topic_id)


def _default_description_prompt(topic_id: str) -> str | None:
    mapping = {
        "global-trade": "监控全球主要经济体的贸易政策变化、关税调整和贸易协定进展。重点关注影响中国出口的措施，包括美国对华关税政策、欧盟贸易防御工具、RCEP实施进展和CPTPP扩员动向。需要采集来自官方公告、权威媒体和贸易分析机构的信息。",
        "tech-regulations": "跟踪全球技术性贸易措施的最新动态，包括TBT/SPS通报、产品标准更新、合格评定要求、碳足迹和可持续发展法规。重点关注电池、光伏、新能源汽车、半导体等战略性行业，覆盖欧盟、美国、东盟和中国等主要市场。",
    }
    return mapping.get(topic_id)


def _default_tags() -> list[dict]:
    """默认标签：label=中文显示名，value=英文代码（采集匹配用英文）。

    id 统一为 "{namespace}:{value}"，与 auto_tag_rules 的 tag 写法一致。
    """
    raw = [
        # namespace, value(英文), label(中文), color
        ("category", "trade_policy", "贸易政策", "#2563eb"),
        ("category", "tariff", "关税税则", "#1d4ed8"),
        ("category", "smuggling", "走私缉私", "#dc2626"),
        ("category", "enforcement", "海关执法", "#b91c1c"),
        ("category", "commodity_price", "大宗价格", "#f59e0b"),
        ("category", "trade_remedy", "贸易救济", "#7c3aed"),
        ("category", "export_control", "出口管制", "#9333ea"),
        ("category", "supply_chain", "供应链", "#0891b2"),
        ("category", "compliance", "海关合规", "#0d9488"),
        ("category", "ip_protection", "知识产权", "#db2777"),
        ("region", "china", "中国", "#ef4444"),
        ("region", "usa", "美国", "#3b82f6"),
        ("region", "eu", "欧盟", "#6366f1"),
        ("region", "asean", "东盟", "#10b981"),
        ("region", "global", "全球", "#64748b"),
        ("commodity", "crude_oil", "原油", "#78350f"),
        ("commodity", "metals", "金属", "#92400e"),
        ("commodity", "grain", "粮食", "#ca8a04"),
        ("commodity", "precious_metals", "贵金属", "#eab308"),
    ]
    return [
        {"id": f"{ns}:{val}", "namespace": ns, "value": val, "label": label, "color": color}
        for (ns, val, label, color) in raw
    ]


def _default_models() -> list[dict]:
    return [
        # ── Local models ──────────────────────────────────────────────
        {
            "id": "ollama-default",
            "name": "本地 Ollama",
            "provider": "ollama",
            "base_url": "http://localhost:11434",
            "model_name": "qwen3-coder-next:latest",
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 0.9,
            "is_default": False,
            "is_active": True,
            "description": "本地运行的 Ollama 模型（llama3.1），无需 API Key，完全离线",
        },

        {
            "id": "cc-switch-deepseek",
            "name": "CC Switch (DeepSeek V4 Flash)",
            "provider": "cc_switch",
            "base_url": "http://127.0.0.1:15721",
            "model_name": "deepseek-v4-flash",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "is_default": True,
            "is_active": True,
            "description": "CC Switch 代理 → DeepSeek V4 Flash，高效的中英文推理模型",
        },
        # ── Chinese LLM providers ─────────────────────────────────────
        {
            "id": "deepseek-api",
            "name": "DeepSeek 深度求索",
            "provider": "openai",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "",
            "model_name": "deepseek-chat",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "is_default": False,
            "is_active": True,
            "description": "DeepSeek API（深度求索），性价比极高的国产大模型，支持中英文",
        },
        {
            "id": "qwen-api",
            "name": "通义千问 (Qwen)",
            "provider": "openai",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "",
            "model_name": "qwen-plus",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "is_default": False,
            "is_active": True,
            "description": "阿里云通义千问 API，支持 qwen-max / qwen-plus / qwen-turbo 等模型",
        },
        {
            "id": "baidu-ernie",
            "name": "文心一言 (ERNIE)",
            "provider": "openai",
            "base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
            "api_key": "",
            "model_name": "ernie-4.0-8k",
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 0.9,
            "is_default": False,
            "is_active": True,
            "description": "百度文心一言 API，ERNIE 4.0 旗舰模型，中文能力出色",
        },
        {
            "id": "zhipu-glm",
            "name": "智谱 GLM",
            "provider": "openai",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "api_key": "",
            "model_name": "glm-4-plus",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "is_default": False,
            "is_active": True,
            "description": "智谱 AI GLM-4 系列 API，支持 glm-4-plus / glm-4-air 等模型",
        },
        {
            "id": "moonshot-api",
            "name": "月之暗面 (Moonshot)",
            "provider": "openai",
            "base_url": "https://api.moonshot.cn/v1",
            "api_key": "",
            "model_name": "moonshot-v1-8k",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "is_default": False,
            "is_active": True,
            "description": "月之暗面 Moonshot API，长上下文窗口，适合处理大量采集信息",
        },
        # ── Cloud fallback ────────────────────────────────────────────
        {
            "id": "openai-fallback",
            "name": "OpenAI 兼容 API",
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "model_name": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 0.9,
            "is_default": False,
            "is_active": False,
            "description": "OpenAI 兼容 API（备用），需要填写 API Key",
        },
    ]


def _default_search_tools() -> list[dict]:
    return [
        {
            "id": "tavily-search",
            "name": "Tavily Web Search",
            "tool_type": "tavily",
            "is_active": True,
            "config_json": {"rate_limit": 0.5, "max_results": 10, "include_answer": True, "languages": ["zh", "en"]},
            "api_key_ref": "TAVILY_API_KEY",
            "is_default": True,
        },
        {
            "id": "rss-feeds",
            "name": "RSS 新闻订阅",
            "tool_type": "rss",
            "is_active": True,
            "config_json": {"timeout": 30, "max_items_per_feed": 20, "feeds": [
                "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
                "http://www.chinadaily.com.cn/rss/world_rss.xml",
                "https://feedx.net/rss/cn-top.xml"
            ]},
            "is_default": False,
        },
        {
            "id": "web-scraper",
            "name": "网页抓取器",
            "tool_type": "web_scrape",
            "is_active": True,
            "config_json": {"timeout": 30, "max_pages": 5, "user_agent": "Mozilla/5.0 GatherInfo/1.0"},
            "is_default": False,
        },
        {
            "id": "weibo-monitor",
            "name": "微博监控",
            "tool_type": "social",
            "is_active": True,
            "config_json": {"platform": "weibo", "keywords": [], "max_results": 20},
            "api_key_ref": "WEIBO_API_KEY",
            "is_default": False,
        },
        {
            "id": "patent-search",
            "name": "专利数据库",
            "tool_type": "official_api",
            "is_active": True,
            "config_json": {"databases": ["cnipa", "wipo", "uspto"], "max_results": 10},
            "is_default": False,
        },
    ]


def _default_sources() -> list[dict]:
    return [
        # ── 信息聚合中枢 / API 直连 ────────────────────────────────────────
        {
            "id": "tavily",
            "name": "Tavily Web Search",
            "description": "Global web search via Tavily API. Supports Chinese + English queries.",
            "channel": "api_search",
            "is_active": True,
            "homepage_url": "https://tavily.com",
            "default_keywords": ["最新动态"],
            "default_categories": ["general"],
            "languages": ["zh", "en"],
            "rate_limit_rps": 0.5,
            "timeout_seconds": 60,
            "max_items_per_run": 100,
            "legal_basis": "公开信息搜索",
        },
        {
            "id": "newsapi",
            "name": "NewsAPI 全球新闻聚合",
            "description": "聚合全球 8 万+ 新闻源标题与链接，可编程关键词检索（免费版 100 次/天）。需在官网注册 API Key。",
            "channel": "json_api",
            "is_active": False,
            "homepage_url": "https://newsapi.org",
            "base_url": "https://newsapi.org/v2",
            "api_endpoint": "everything",
            "default_keywords": ["customs", "smuggling", "tariff"],
            "languages": ["en"],
            "rate_limit_rps": 0.2,
            "auth_config": {
                "method": "GET", "auth": "query", "auth_param": "apiKey",
                "keyword_param": "q", "keyword_join": " OR ",
                "query": {"language": "en", "sortBy": "publishedAt", "pageSize": 50},
                "items_path": "articles",
                "fields": {"title": "title", "content": "content", "summary": "description",
                           "url": "url", "published_at": "publishedAt"},
            },
            "legal_basis": "公开新闻聚合 API",
        },
        {
            "id": "inoreader",
            "name": "Inoreader 情报中枢",
            "description": "核心 RSS 情报中枢：订阅所有源、关键词监控、自动翻译。可用其 Stream API 拉取聚合内容（需 OAuth/AppKey）。",
            "channel": "json_api",
            "is_active": False,
            "homepage_url": "https://www.inoreader.com",
            "base_url": "https://www.inoreader.com/reader/api/0",
            "api_endpoint": "stream/contents",
            "languages": ["zh", "en"],
            "rate_limit_rps": 0.2,
            "auth_config": {
                "method": "GET", "auth": "bearer",
                "items_path": "items",
                "fields": {"title": "title", "content": "summary.content",
                           "url": "canonical.0.href", "published_at": "published"},
            },
            "legal_basis": "用户自有订阅内容",
        },
        {
            "id": "feedly",
            "name": "Feedly 情报源",
            "description": "团队共享 RSS 情报源，界面友好、第三方联动强。可用 Feedly Streams API 拉取（需 OAuth Token）。",
            "channel": "json_api",
            "is_active": False,
            "homepage_url": "https://feedly.com",
            "base_url": "https://cloud.feedly.com/v3",
            "api_endpoint": "streams/contents",
            "languages": ["zh", "en"],
            "rate_limit_rps": 0.2,
            "auth_config": {
                "method": "GET", "auth": "bearer",
                "items_path": "items",
                "fields": {"title": "title", "content": "content.content",
                           "url": "alternate.0.href", "published_at": "published"},
            },
            "legal_basis": "用户自有订阅内容",
        },
        {
            "id": "google-alerts",
            "name": "Google Alerts 快速雷达",
            "description": "监控网络上新出现的关键词（如“中国 走私 查获”）。在 Google Alerts 中将提醒输出为 RSS feed，再把该 feed 链接填入 base_url。",
            "channel": "rss",
            "is_active": False,
            "homepage_url": "https://www.google.com/alerts",
            "base_url": "",
            "default_keywords": ["走私", "查获", "tariff", "sanction"],
            "languages": ["zh", "en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "公开新闻提醒",
        },
        {
            "id": "rss-app",
            "name": "RSS.app 生成源",
            "description": "为没有 RSS 的关键网页生成专属 RSS。生成后把 feed 链接填入 base_url 即可纳入采集。",
            "channel": "rss",
            "is_active": False,
            "homepage_url": "https://rss.app",
            "base_url": "",
            "languages": ["zh", "en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "公开网页转 RSS",
        },

        # ── 1. 全球贸易信息与贸易政策 ─────────────────────────────────────
        {
            "id": "un-comtrade",
            "name": "UN Comtrade 全球贸易数据库",
            "description": "全球最权威的官方商品贸易统计数据。新版公共 API 需订阅 Key（免费档可申请）。",
            "channel": "json_api",
            "is_active": False,
            "homepage_url": "https://comtradeplus.un.org/",
            "base_url": "https://comtradeapi.un.org",
            "api_endpoint": "data/v1/get/C/A/HS",
            "default_categories": ["trade"],
            "languages": ["en"],
            "rate_limit_rps": 0.2,
            "auth_config": {
                "method": "GET", "auth": "header", "auth_param": "Ocp-Apim-Subscription-Key",
                "items_path": "data",
                "fields": {"title": "cmdDesc", "content": "partnerDesc", "published_at": "period"},
            },
            "legal_basis": "联合国公开统计数据",
        },
        {
            "id": "itc-trademap",
            "name": "ITC Trade Map 贸易地图",
            "description": "贸易竞争力、需求市场、关税数据可视化。需在官网免费注册账号后访问。",
            "channel": "manual",
            "is_active": False,
            "homepage_url": "https://www.trademap.org/",
            "default_categories": ["trade"],
            "languages": ["en"],
            "legal_basis": "ITC 公开数据（需注册）",
        },
        {
            "id": "worldbank-open-data",
            "name": "World Bank Open Data",
            "description": "各国关税、物流绩效、经济指标数据。提供免费公开 JSON API。",
            "channel": "json_api",
            "is_active": False,
            "homepage_url": "https://data.worldbank.org/",
            "base_url": "https://api.worldbank.org/v2",
            "api_endpoint": "country/all/indicator/TM.TAX.MRCH.WM.AR.ZS",
            "default_categories": ["trade", "economy"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "auth_config": {
                "method": "GET", "auth": "none",
                "query": {"format": "json", "per_page": "50"},
                "items_path": "1",
                "fields": {"title": "indicator.value", "content": "value",
                           "published_at": "date", "category": "country.value"},
            },
            "legal_basis": "世界银行公开数据",
        },
        {
            "id": "wto-docs",
            "name": "WTO Documents Online",
            "description": "WTO 所有通报、争端解决、贸易政策审议文件。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://docs.wto.org/",
            "base_url": "https://www.wto.org/english/news_e/news_e.htm",
            "default_keywords": ["notification", "dispute", "trade policy"],
            "default_categories": ["regulation", "trade"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "WTO 公开文件",
        },
        {
            "id": "wto-eping",
            "name": "WTO ePing Notifications",
            "description": "WTO TBT/SPS 通报 - 技术性贸易措施",
            "channel": "official",
            "is_active": True,
            "homepage_url": "https://eping.wto.org/",
            "api_endpoint": "https://eping.wto.org/api/v1/notifications",
            "default_categories": ["tbt_sps", "regulation"],
            "languages": ["en"],
            "rate_limit_rps": 1.0,
            "auth_config": {"type": "wto_eping"},
            "legal_basis": "WTO公开数据",
        },
        {
            "id": "wto-rtais",
            "name": "RTA Exchange (WTO RTAIS)",
            "description": "全球自贸协定文本和优惠关税信息。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://rtais.wto.org/",
            "base_url": "https://rtais.wto.org/UI/PublicAllRTAList.aspx",
            "default_categories": ["fta", "trade"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "WTO 公开数据",
        },
        {
            "id": "cn-fta",
            "name": "中国自由贸易区服务网",
            "description": "中国签订的所有 FTA 协定税率及原产地规则。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "http://fta.mofcom.gov.cn/",
            "base_url": "http://fta.mofcom.gov.cn/",
            "default_keywords": ["自贸协定", "原产地", "税率"],
            "default_categories": ["fta", "trade"],
            "languages": ["zh"],
            "country_focus": ["CN"],
            "rate_limit_rps": 0.5,
            "legal_basis": "公开政府信息",
        },
        {
            "id": "ustr",
            "name": "USTR 美国贸易代表办公室",
            "description": "301 调查、排除清单、美国贸易政策优先级。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://ustr.gov/",
            "base_url": "https://ustr.gov/about-us/policy-offices/press-office/press-releases",
            "default_keywords": ["Section 301", "tariff", "exclusion"],
            "default_categories": ["policy", "trade"],
            "languages": ["en"],
            "country_focus": ["US"],
            "rate_limit_rps": 0.5,
            "legal_basis": "美国公开政府信息",
        },
        {
            "id": "eu-trade-helpdesk",
            "name": "EU Trade Helpdesk / Access2Markets",
            "description": "欧盟关税、进口要求、优惠安排查询。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://trade.ec.europa.eu/access-to-markets/en/home",
            "base_url": "https://trade.ec.europa.eu/access-to-markets/en/news",
            "default_categories": ["regulation", "trade"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "欧盟公开信息",
        },
        {
            "id": "cn-customs",
            "name": "海关总署公告",
            "description": "中国海关总署：政策法规、商品编码调整、进出口监管公告",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "http://www.customs.gov.cn/",
            "base_url": "http://www.customs.gov.cn/customs/302249/302266/index.html",
            "default_keywords": ["进出口", "关税", "商品编码", "监管", "公告"],
            "default_categories": ["regulation", "trade"],
            "languages": ["zh"],
            "country_focus": ["CN"],
            "rate_limit_rps": 0.5,
            "auth_config": {"type": "cn_customs"},
            "legal_basis": "公开政府信息",
        },
        {
            "id": "cn-mofcom",
            "name": "商务部公告",
            "description": "中国商务部：贸易政策、贸易救济调查、出口管制",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "http://www.mofcom.gov.cn/",
            "base_url": "http://www.mofcom.gov.cn/article/zwgk/bnjg/",
            "default_keywords": ["贸易壁垒", "反倾销", "出口管制", "公告"],
            "default_categories": ["policy", "trade"],
            "languages": ["zh"],
            "country_focus": ["CN"],
            "rate_limit_rps": 0.5,
            "auth_config": {"type": "cn_mofcom"},
            "legal_basis": "公开政府信息",
        },
        {
            "id": "eu-eurlex",
            "name": "EU EUR-Lex",
            "description": "欧盟官方法规、指令、决定",
            "channel": "official",
            "is_active": True,
            "homepage_url": "https://eur-lex.europa.eu/",
            "default_categories": ["regulation"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "auth_config": {"type": "eurlex"},
            "legal_basis": "欧盟公开法律文件",
        },

        # ── 2. 全球走私、违规与执法信息 ──────────────────────────────────
        {
            "id": "wco",
            "name": "WCO 世界海关组织",
            "description": "海关执法行动、海关现代化、风险指标框架。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://www.wcoomd.org/",
            "base_url": "https://www.wcoomd.org/en/media/newsroom.aspx",
            "default_keywords": ["enforcement", "seizure", "customs"],
            "default_categories": ["enforcement", "customs"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "WCO 公开信息",
        },
        {
            "id": "wco-news-feed",
            "name": "WCO News Feed",
            "description": "世界海关组织全球海关动态，可订阅 RSS。请填入实际 RSS 链接到 base_url。",
            "channel": "rss",
            "is_active": False,
            "homepage_url": "https://www.wcoomd.org/en/media/wco-news.aspx",
            "base_url": "",
            "default_categories": ["customs", "enforcement"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "WCO 公开 RSS",
        },
        {
            "id": "unodc",
            "name": "UNODC 联合国毒罪办",
            "description": "全球毒品、野生动植物、人口走私趋势报告。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://www.unodc.org/",
            "base_url": "https://www.unodc.org/unodc/en/press/index.html",
            "default_keywords": ["smuggling", "trafficking", "seizure"],
            "default_categories": ["enforcement", "crime"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "联合国公开信息",
        },
        {
            "id": "wipo-lex",
            "name": "WIPO Lex 知识产权法律库",
            "description": "全球知识产权法律及执法案例数据库。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://www.wipo.int/wipolex/en/",
            "base_url": "https://www.wipo.int/pressroom/en/",
            "default_keywords": ["counterfeit", "IP enforcement"],
            "default_categories": ["ip", "enforcement"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "WIPO 公开数据",
        },
        {
            "id": "interpol-news",
            "name": "INTERPOL News",
            "description": "跨国犯罪行动、红色通缉令相关新闻。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://www.interpol.int/News-and-Events",
            "base_url": "https://www.interpol.int/en/News-and-Events/News",
            "default_keywords": ["smuggling", "trafficking", "seizure"],
            "default_categories": ["enforcement", "crime"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "INTERPOL 公开新闻",
        },
        {
            "id": "cbp-newsroom",
            "name": "CBP Newsroom 美国海关查获",
            "description": "毒品、假货、违禁品查获典型案例。CBP 提供 RSS，亦可直接抓取页面。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://www.cbp.gov/newsroom",
            "base_url": "https://www.cbp.gov/newsroom/national-media-release",
            "default_keywords": ["seizure", "smuggling", "counterfeit"],
            "default_categories": ["enforcement", "customs"],
            "languages": ["en"],
            "country_focus": ["US"],
            "rate_limit_rps": 0.5,
            "legal_basis": "美国公开政府信息",
        },
        {
            "id": "olaf",
            "name": "OLAF 欧盟反欺诈办公室",
            "description": "香烟、纺织品等走私案件查处。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://anti-fraud.ec.europa.eu/index_en",
            "base_url": "https://anti-fraud.ec.europa.eu/media-corner/news_en",
            "default_keywords": ["smuggling", "cigarettes", "fraud"],
            "default_categories": ["enforcement", "fraud"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "欧盟公开信息",
        },
        {
            "id": "sp-global-mi",
            "name": "S&P Global Market Intelligence",
            "description": "海事、贸易合规风险、制裁名单（部分付费）。需订阅账号。",
            "channel": "manual",
            "is_active": False,
            "homepage_url": "https://www.spglobal.com/marketintelligence/",
            "default_categories": ["risk", "compliance"],
            "languages": ["en"],
            "legal_basis": "商业数据（需订阅）",
        },

        # ── 3. 重要商品价格信息 ─────────────────────────────────────────
        {
            "id": "imf-commodity-prices",
            "name": "IMF Primary Commodity Prices",
            "description": "免费、权威的全球能源、农产品、金属价格表。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://www.imf.org/en/Research/commodity-prices",
            "base_url": "https://www.imf.org/en/Research/commodity-prices",
            "default_categories": ["price", "commodity"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "IMF 公开数据",
        },
        {
            "id": "fao-food-price-index",
            "name": "FAO Food Price Index",
            "description": "全球谷物、肉类、植物油等价格与供需简报。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://www.fao.org/worldfoodsituation/foodpricesindex/en/",
            "base_url": "https://www.fao.org/worldfoodsituation/foodpricesindex/en/",
            "default_categories": ["price", "food"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "FAO 公开数据",
        },
        {
            "id": "trading-economics",
            "name": "Trading Economics",
            "description": "覆盖 30 万+ 经济指标，含多国商品现货价。提供 API（需 Key）。",
            "channel": "json_api",
            "is_active": False,
            "homepage_url": "https://tradingeconomics.com/",
            "base_url": "https://api.tradingeconomics.com",
            "api_endpoint": "markets/commodities",
            "default_categories": ["price", "commodity"],
            "languages": ["en"],
            "rate_limit_rps": 0.2,
            "auth_config": {
                "method": "GET", "auth": "query", "auth_param": "c",
                "query": {"f": "json"},
                "items_path": "",
                "fields": {"title": "Name", "content": "Last", "category": "Group"},
            },
            "legal_basis": "商业数据 API（需 Key）",
        },
        {
            "id": "worldbank-commodity-markets",
            "name": "World Bank Commodity Markets",
            "description": "年度及季度《大宗商品市场展望》(Pink Sheet) 报告。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://www.worldbank.org/en/research/commodity-markets",
            "base_url": "https://www.worldbank.org/en/research/commodity-markets",
            "default_categories": ["price", "commodity"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "世界银行公开数据",
        },
        {
            "id": "lbma-prices",
            "name": "London Bullion Market (LBMA)",
            "description": "每日黄金、白银定盘价。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://www.lbma.org.uk/prices-and-data/precious-metal-prices",
            "base_url": "https://www.lbma.org.uk/prices-and-data/precious-metal-prices",
            "default_categories": ["price", "metal"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "LBMA 公开定价",
        },
        {
            "id": "opec-basket",
            "name": "OPEC Basket Price",
            "description": "欧佩克一篮子原油参考价格。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://www.opec.org/opec_web/en/data_graphs/40.htm",
            "base_url": "https://www.opec.org/opec_web/en/data_graphs/40.htm",
            "default_categories": ["price", "energy"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "OPEC 公开数据",
        },
        {
            "id": "cme-group",
            "name": "CME Group",
            "description": "全球最大交易所，能源、金属、农产品期货。实时数据多为付费。",
            "channel": "web_scrape",
            "is_active": False,
            "homepage_url": "https://www.cmegroup.com/",
            "base_url": "https://www.cmegroup.com/markets/agriculture.html",
            "default_categories": ["price", "futures"],
            "languages": ["en"],
            "rate_limit_rps": 0.3,
            "legal_basis": "交易所公开/付费数据",
        },
        {
            "id": "baltic-exchange",
            "name": "Baltic Exchange 波罗的海交易所",
            "description": "干散货、油轮运费指数（贸易景气度关键指标）。",
            "channel": "web_scrape",
            "is_active": True,
            "homepage_url": "https://www.balticexchange.com/",
            "base_url": "https://www.balticexchange.com/en/data-services/market-information0.html",
            "default_categories": ["price", "shipping"],
            "languages": ["en"],
            "rate_limit_rps": 0.5,
            "legal_basis": "公开运费指数",
        },
    ]


def _default_topics() -> list[dict]:
    # Note: keyword_tags and description_prompt are added by _default_keyword_tags / _default_description_prompt
    # in seed_defaults separately. This dict only contains the original ORM fields.
    return [
        {
            "id": "global-trade",
            "name": "全球贸易政策动态",
            "description": "监控全球主要经济体的贸易政策变化、关税调整、贸易协定进展",
            "keywords": ["贸易政策", "关税", "自贸协定", "trade policy", "tariff", "FTA", "RCEP", "CPTPP"],
            "categories": ["trade", "policy"],
            "focus_countries": ["CN", "US", "EU", "JP", "KR", "ASEAN"],
            "focus_languages": ["zh", "en"],
            "auto_tag_rules": [
                {"keyword": "关税", "tag": "event:tariff"},
                {"keyword": "反倾销", "tag": "event:anti_dumping"},
                {"keyword": "RCEP", "tag": "agreement:rcep"},
                {"keyword": "出口管制", "tag": "event:export_control"},
            ],
            "schedule_cron": "0 8 * * *",
            "is_scheduled": True,
        },
        {
            "id": "tech-regulations",
            "name": "技术性贸易措施",
            "description": "TBT/SPS通报、标准更新、合格评定、碳足迹、供应链法规",
            "keywords": ["TBT", "SPS", "技术法规", "标准", "合格评定", "碳足迹", "供应链", "电池", "光伏", "新能源汽车"],
            "categories": ["regulation", "technology"],
            "focus_languages": ["zh", "en"],
            "source_ids": ["wto-eping", "eu-eurlex", "tavily"],
            "auto_tag_rules": [
                {"keyword": "电池", "tag": "product:battery"},
                {"keyword": "光伏", "tag": "product:solar"},
                {"keyword": "芯片", "tag": "product:semiconductor"},
                {"keyword": "碳足迹", "tag": "event:carbon_footprint"},
                {"keyword": "新能源", "tag": "sector:new_energy"},
            ],
            "schedule_cron": "0 9 * * *",
            "is_scheduled": True,
        },
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Model Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/models", response_model=list[ModelConfigOut])
def list_models(db: Session = Depends(get_db)):
    return db.query(ModelConfig).order_by(ModelConfig.is_default.desc(), ModelConfig.created_at.desc()).all()


@router.post("/models", response_model=ModelConfigOut, status_code=201)
def create_model(data: ModelConfigCreate, db: Session = Depends(get_db)):
    if db.query(ModelConfig).filter(ModelConfig.id == data.id).first():
        raise HTTPException(400, f"Model '{data.id}' exists")
    if data.is_default:
        db.query(ModelConfig).filter(ModelConfig.is_default == True).update({"is_default": False})
    m = ModelConfig(**data.model_dump())
    db.add(m); db.commit(); db.refresh(m)
    return m


@router.get("/models/{model_id}", response_model=ModelConfigOut)
def get_model(model_id: str, db: Session = Depends(get_db)):
    m = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
    if not m: raise HTTPException(404)
    return m


@router.put("/models/{model_id}", response_model=ModelConfigOut)
def update_model(model_id: str, data: ModelConfigUpdate, db: Session = Depends(get_db)):
    m = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
    if not m: raise HTTPException(404)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("is_default"):
        db.query(ModelConfig).filter(ModelConfig.id != model_id, ModelConfig.is_default == True).update({"is_default": False})
    for k, v in payload.items():
        setattr(m, k, v)
    db.commit(); db.refresh(m)
    return m


@router.delete("/models/{model_id}")
def delete_model(model_id: str, db: Session = Depends(get_db)):
    m = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
    if not m: raise HTTPException(404)
    db.delete(m); db.commit()
    return {"ok": True}


@router.post("/models/{model_id}/test", response_model=ModelTestResult)
async def test_model(model_id: str, db: Session = Depends(get_db)):
    m = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
    if not m: raise HTTPException(404)
    import time
    start = time.monotonic()
    try:
        base = (m.base_url or "http://localhost:11434").rstrip("/")
        model_name = m.model_name or ""

        if m.provider == "ollama":
            # Step 1: Check connectivity via /api/tags
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get(f"{base}/api/tags")
                    if r.status_code != 200:
                        return ModelTestResult(success=False, message=f"Ollama unreachable: {r.status_code}", duration_ms=int((time.monotonic()-start)*1000))
                    tags_data = r.json()
                    avail = [mod.get("name", "") for mod in tags_data.get("models", [])]
            except Exception as exc:
                return ModelTestResult(success=False, message=f"Ollama connection failed: {exc}", duration_ms=int((time.monotonic()-start)*1000))

            # Step 2: Find a valid model
            test_model = model_name
            if test_model not in avail and test_model.split(":")[0] not in " ".join(avail):
                # Pick first available model
                test_model = avail[0] if avail else model_name
                message = f"Model '{model_name}' not found. Using '{test_model}' instead."
            else:
                message = f"Ollama OK. Found {len(avail)} models."

            # Step 3: Try a quick chat
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    r = await client.post(f"{base}/api/chat", json={
                        "model": test_model, "messages": [{"role": "user", "content": "Reply exactly: OK"}],
                        "stream": False
                    })
                    if r.status_code == 200:
                        data = r.json()
                        reply = data.get("message", {}).get("content", "")[:100]
                        dur = int((time.monotonic() - start) * 1000)
                        return ModelTestResult(success=True, message=message, response_preview=reply, duration_ms=dur)
                    else:
                        return ModelTestResult(success=False, message=f"Ollama model error: {r.text[:100]}", duration_ms=int((time.monotonic()-start)*1000))
            except Exception as exc:
                return ModelTestResult(success=False, message=f"Ollama inference failed: {exc}", duration_ms=int((time.monotonic()-start)*1000))

        # Non-Ollama providers: use _call_llm
        from app.report_engine import _call_llm
        result = await _call_llm(m, "Please reply with exactly: connection ok. This is a test message.")
        dur = int((time.monotonic() - start) * 1000)
        preview = (result.get("content", "") or "")[:200]
        return ModelTestResult(success=True, message="Model connection test passed", response_preview=preview, duration_ms=dur)

    except Exception as exc:
        dur = int((time.monotonic() - start) * 1000)
        return ModelTestResult(success=False, message=str(exc), duration_ms=dur)


@router.post("/models/{model_id}/list-models", response_model=ListModelsResult)
async def list_available_models(model_id: str, db: Session = Depends(get_db)):
    m = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
    if not m:
        raise HTTPException(404)
    import time, httpx
    start = time.monotonic()
    try:
        models_list = []
        base = (m.base_url or '').rstrip('/')

        if m.provider == 'ollama':
            url = f"{base}/api/tags" if base else "http://localhost:11434/api/tags"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                for mod in data.get('models', []):
                    models_list.append(mod.get('name', ''))

        elif m.provider == 'cc_switch':
            models_list = ['deepseek-v4-flash', 'deepseek-v4-pro']

        elif m.provider in ('openai', 'lmstudio', 'custom'):
            url = f"{base}/v1/models" if base else "http://localhost:11434/v1/models"
            try:
                headers = {}
                if m.api_key:
                    headers['Authorization'] = f"Bearer {m.api_key}"
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    for mod in data.get('data', data.get('models', [])):
                        if isinstance(mod, dict):
                            models_list.append(mod.get('id', mod.get('name', '')))
                        elif isinstance(mod, str):
                            models_list.append(mod)
            except Exception:
                models_list = []

        dur = int((time.monotonic() - start) * 1000)
        msg = f"Found {len(models_list)} models" if models_list else "No models found"
        return ListModelsResult(success=len(models_list) > 0, message=msg,
                                models=models_list, provider_type=m.provider,
                                current_model=m.model_name or '')

    except Exception as exc:
        dur = int((time.monotonic() - start) * 1000)
        return ListModelsResult(success=False, message=f"Error: {exc}",
                                models=[], provider_type=m.provider or '',
                                current_model=m.model_name or '')


@router.post("/models/auto-discover", response_model=AutoDiscoverResult)
async def auto_discover_models(db: Session = Depends(get_db)):
    """Probe common local model servers and return any reachable providers + models."""
    probes = [
        ("ollama", "http://localhost:11434", "/api/tags"),
        ("lmstudio", "http://localhost:1234", "/v1/models"),
        ("cc_switch", "http://localhost:8080", "/v1/models"),
    ]
    discovered: list[DiscoveredProvider] = []

    async def _probe(provider: str, base: str, path: str):
        url = f"{base}{path}"
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None
                data = resp.json()
        except Exception:
            return None

        models: list[str] = []
        if provider == "ollama":
            models = [mod.get("name", "") for mod in data.get("models", []) if mod.get("name")]
        else:  # OpenAI-compatible
            for mod in data.get("data", data.get("models", [])):
                if isinstance(mod, dict):
                    models.append(mod.get("id", mod.get("name", "")))
                elif isinstance(mod, str):
                    models.append(mod)
            models = [m for m in models if m]
        note = f"{provider} 已连接" + (f"（{len(models)} 个模型）" if models else "")
        return DiscoveredProvider(provider=provider, base_url=base, models=models, reachable=True, note=note)

    results = await asyncio.gather(*[_probe(p, b, path) for p, b, path in probes])
    for r in results:
        if r is not None:
            discovered.append(r)
    return AutoDiscoverResult(providers=discovered)



# ═══════════════════════════════════════════════════════════════════════════════
# Reports
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/reports", response_model=ReportListOut)
def list_reports(topic_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Report)
    if topic_id:
        q = q.filter(Report.topic_id == topic_id)
    total = q.count()
    reports = q.order_by(Report.created_at.desc()).limit(50).all()
    return ReportListOut(reports=reports, total=total)


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: str, db: Session = Depends(get_db)):
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r: raise HTTPException(404)
    return r


@router.post("/reports/generate", response_model=ReportOut)
async def generate_report(data: ReportGenerateRequest, db: Session = Depends(get_db)):
    from app.report_engine import generate_report as gen
    try:
        report = await gen(
            topic_id=data.topic_id,
            model_id=data.model_id,
            title_override=data.title,
            collection_run_id=data.collection_run_id,
            date_from=data.date_from,
            date_to=data.date_to,
        )
        return report
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Report generation failed: {e}")


@router.post("/reports/batch-generate", response_model=BatchGenerateResult)
async def batch_generate_reports(data: BatchGenerateRequest, db: Session = Depends(get_db)):
    """Generate reports for multiple topics in parallel."""
    from app.report_engine import generate_report as gen
    if not data.topic_ids:
        raise HTTPException(400, "topic_ids 不能为空")

    run_ids = data.collection_run_ids or []

    async def _one(idx: int, tid: str):
        run_id = run_ids[idx] if idx < len(run_ids) else None
        return await gen(topic_id=tid, model_id=data.model_id, collection_run_id=run_id)

    tasks = [_one(i, tid) for i, tid in enumerate(data.topic_ids)]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[ReportOut] = []
    failed = 0
    for r in raw:
        if isinstance(r, Exception):
            failed += 1
            logger.error("batch report failed: %s", r)
            continue
        if getattr(r, "status", "") == "failed":
            failed += 1
        results.append(ReportOut.model_validate(r))
    return BatchGenerateResult(results=results, failed=failed)


@router.delete("/reports/{report_id}")
def delete_report(report_id: str, db: Session = Depends(get_db)):
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r: raise HTTPException(404)
    db.delete(r); db.commit()
    return {"ok": True}


@router.post("/reports/{report_id}/export", response_model=ReportOut)
def export_report_files(report_id: str, db: Session = Depends(get_db)):
    """Re-render an existing completed report to disk (MD/HTML/DOCX/PDF)."""
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise HTTPException(404)
    if not (r.content or "").strip():
        raise HTTPException(400, "报告内容为空，无法导出")
    from app.report_export import export_report as _export
    system = _get_system_config(db)
    topic = db.query(Topic).filter(Topic.id == r.topic_id).first()
    try:
        _export(r, system, topic)
        db.commit(); db.refresh(r)
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"导出失败: {exc}")
    return r


@router.get("/reports/{report_id}/download")
def download_report(report_id: str, format: str = Query("pdf"), db: Session = Depends(get_db)):
    """Download a previously-exported report file in the given format."""
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise HTTPException(404)
    files = r.output_files or {}
    path = files.get(format)
    if not path or not os.path.isfile(path):
        raise HTTPException(404, f"未找到 {format} 格式文件，请先导出")
    media = {
        "md": "text/markdown", "html": "text/html",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }.get(format, "application/octet-stream")
    return FileResponse(path, media_type=media, filename=os.path.basename(path))


# ═══════════════════════════════════════════════════════════════════════════════
# System Settings (报告设置等全局配置)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_system_config(db: Session) -> SystemConfig:
    cfg = db.query(SystemConfig).filter(SystemConfig.id == "global").first()
    if not cfg:
        cfg = SystemConfig(id="global")
        db.add(cfg); db.commit(); db.refresh(cfg)
    return cfg


@router.get("/settings", response_model=SystemConfigOut)
def get_settings(db: Session = Depends(get_db)):
    return _get_system_config(db)


@router.put("/settings", response_model=SystemConfigOut)
def update_settings(data: SystemConfigUpdate, db: Session = Depends(get_db)):
    cfg = _get_system_config(db)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cfg, k, v)
    db.commit(); db.refresh(cfg)
    return cfg


# ═══════════════════════════════════════════════════════════════════════════════
# Search Tool Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/search-tools", response_model=list[SearchToolConfigOut])
def list_search_tools(db: Session = Depends(get_db)):
    return db.query(SearchToolConfig).order_by(SearchToolConfig.created_at.desc()).all()


@router.post("/search-tools", response_model=SearchToolConfigOut, status_code=201)
def create_search_tool(data: SearchToolConfigCreate, db: Session = Depends(get_db)):
    if db.query(SearchToolConfig).filter(SearchToolConfig.id == data.id).first():
        raise HTTPException(400, f"Search tool '{data.id}' exists")
    st = SearchToolConfig(**data.model_dump())
    db.add(st); db.commit(); db.refresh(st)
    return st


@router.put("/search-tools/{tool_id}", response_model=SearchToolConfigOut)
def update_search_tool(tool_id: str, data: SearchToolConfigUpdate, db: Session = Depends(get_db)):
    st = db.query(SearchToolConfig).filter(SearchToolConfig.id == tool_id).first()
    if not st: raise HTTPException(404)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(st, k, v)
    db.commit(); db.refresh(st)
    return st


@router.delete("/search-tools/{tool_id}")
def delete_search_tool(tool_id: str, db: Session = Depends(get_db)):
    st = db.query(SearchToolConfig).filter(SearchToolConfig.id == tool_id).first()
    if not st: raise HTTPException(404)
    db.delete(st); db.commit()
    return {"ok": True}
