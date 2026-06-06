"""
Collection Engine — the central orchestrator.

Flow:
    Topic → keywords → sources → connectors → FetchItems
    → dedup → persist (with topic_id) → auto-tag → return stats
"""
import asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.connectors.base import ConnectorRegistry, CollectResult, FetchItem
from app.models import (
    CollectionRun, CollectedItem, ItemStatus,
    JobStatus, SourceConfig, Tag, Topic,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CollectionEngine:
    def __init__(self, db: Session):
        self.db = db

    # ── Single source collection ────────────────────────────────────────

    async def collect_from_source(
        self, source_id: str, keywords: list[str], topic_id: str | None = None,
        window_start: "datetime | None" = None, window_end: "datetime | None" = None,
        batch_id: str | None = None,
    ) -> CollectResult:
        """Collect from one source with given keywords.

        When window_start is provided, items with a known published_at older than
        window_start are skipped (items without published_at are always kept).
        """
        source = self.db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
        if not source:
            raise ValueError(f"Source not found: {source_id}")
        if not source.is_active:
            return CollectResult(
                run_id="", source_id=source_id, status=JobStatus.FAILED,
                items=[], error_log=["Source is not active"],
            )

        run = CollectionRun(
            id=f"run-{uuid4().hex[:12]}",
            source_id=source.id,
            topic_id=topic_id,
            job_id=f"job-{uuid4().hex[:8]}",
            status=JobStatus.PENDING,
            keywords_used=keywords,
            window_start=window_start,
            window_end=window_end,
        )
        run.batch_id = batch_id
        run.status = JobStatus.RUNNING
        run.started_at = utc_now()
        self.db.add(run)
        self.db.commit()

        try:
            connector = ConnectorRegistry.create(source)
        except ValueError as exc:
            run.status = JobStatus.FAILED
            run.error_log = [str(exc)]
            self.db.commit()
            return CollectResult(run_id=run.id, source_id=source.id,
                                 status=JobStatus.FAILED, items=[], error_log=[str(exc)])

        result = await connector.execute(run, keywords)
        self._persist_items(result.items, source.id, run.id, topic_id, window_start, keywords)
        self._update_source(source, len(result.items))
        self.db.commit()
        return result

    # ── Topic-driven collection ─────────────────────────────────────────

    async def collect_topic(self, topic_id: str) -> list[CollectResult]:
        """Collect from all sources relevant to a topic."""
        topic = self.db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise ValueError(f"Topic not found: {topic_id}")

        sources = self._resolve_sources(topic)
        source_ids = [s.id for s in sources]
        keywords = topic.keywords if isinstance(topic.keywords, list) else [topic.keywords]

        # Compute the publication time window from the topic configuration.
        # window_days <= 0 disables filtering (collect everything).
        window_days = getattr(topic, "collect_window_days", None) or 0
        window_end = utc_now()
        window_start = window_end - timedelta(days=window_days) if window_days > 0 else None

        # Generate a shared batch_id for all runs in this topic collection
        from uuid import uuid4
        batch_id = f"batch-{uuid4().hex[:12]}"

        # Parallel collection — topic_id flows through into runs and items
        tasks = [
            self.collect_from_source(sid, keywords, topic.id, window_start, window_end, batch_id)
            for sid in source_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final: list[CollectResult] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                final.append(CollectResult(
                    run_id="", source_id=source_ids[i] if i < len(source_ids) else "?",
                    status=JobStatus.FAILED, items=[], error_log=[str(r)],
                ))
            else:
                final.append(r)

        # Auto-tag
        if topic.auto_tag_rules:
            self._apply_auto_tags(topic.id, topic.auto_tag_rules)
        self._apply_suggested_tags(topic.id)

        # Update topic
        topic.last_run_at = utc_now()
        topic.total_items_collected += sum(r.items_new for r in final)
        # Track the most recent collection run id (first successful run)
        run_id = next((r.run_id for r in final if getattr(r, "run_id", None)), None)
        if run_id:
            topic.last_collection_run_id = run_id
        self.db.commit()

        return final

    # ── Scheduled collection ────────────────────────────────────────────

    async def execute_schedule(self, schedule_id: str) -> list[CollectResult]:
        from app.models import ScheduleConfig
        schedule = self.db.query(ScheduleConfig).filter(ScheduleConfig.id == schedule_id).first()
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")

        all_results: list[CollectResult] = []
        for tid in (schedule.topic_ids or []):
            all_results.extend(await self.collect_topic(tid))
        for sid in (schedule.source_ids or []):
            all_results.append(await self.collect_from_source(sid, schedule.keywords or []))

        schedule.last_run_at = utc_now()
        schedule.run_count += 1
        schedule.last_status = (
            JobStatus.FAILED if all(r.status == JobStatus.FAILED for r in all_results)
            else JobStatus.COMPLETED
        )
        self.db.commit()
        return all_results

    # ── Tag system ──────────────────────────────────────────────────────

    def ensure_tag(self, tag_id: str, namespace: str, value: str, label: str | None = None) -> Tag:
        tag = self.db.query(Tag).filter(Tag.id == tag_id).first()
        if not tag:
            tag = Tag(id=tag_id, namespace=namespace, value=value, label=label or value)
            self.db.add(tag)
            self.db.flush()
        tag.last_seen_at = utc_now()
        return tag

    def tag_item(self, item_id: str, tag_id: str) -> bool:
        item = self.db.query(CollectedItem).filter(CollectedItem.id == item_id).first()
        tag = self.db.query(Tag).filter(Tag.id == tag_id).first()
        if not item or not tag:
            return False
        if tag not in item.tags:
            item.tags.append(tag)
            tag.item_count += 1
            if item.status == ItemStatus.RAW:
                item.status = ItemStatus.TAGGED
            return True
        return False

    def _apply_auto_tags(self, topic_id: str, rules: list[dict]) -> int:
        items = self.db.query(CollectedItem).filter(CollectedItem.topic_id == topic_id).all()
        applied = 0
        for item in items:
            text = f"{item.title} {item.content or ''}".lower()
            for rule in rules:
                if rule.get("keyword", "").lower() in text:
                    tag_id = rule.get("tag", "")
                    if tag_id:
                        ns = tag_id.split(":", 1)[0] if ":" in tag_id else "general"
                        val = tag_id.split(":", 1)[1] if ":" in tag_id else tag_id
                        self.ensure_tag(tag_id, ns, val)
                        if self.tag_item(item.id, tag_id):
                            applied += 1
        self.db.commit()
        return applied

    def _apply_suggested_tags(self, topic_id: str):
        items = self.db.query(CollectedItem).filter(
            CollectedItem.topic_id == topic_id,
        ).all()
        for item in items:
            metadata = item.raw_metadata or {}
            # Ingest suggested_tags from Tavily's connector
            suggested = metadata.get("suggested_tags", [])
            if not suggested:
                # Try from the raw Tavily output
                suggested = item.tags_from_metadata()

            for tag_id in suggested:
                parts = tag_id.split(":", 1)
                ns, val = (parts[0], parts[1]) if len(parts) == 2 else ("general", parts[0])
                self.ensure_tag(tag_id, ns, val)
                self.tag_item(item.id, tag_id)

            # Always apply a category tag if item has a category
            if item.category:
                tag_id = f"category:{item.category}"
                self.ensure_tag(tag_id, "category", item.category)
                self.tag_item(item.id, tag_id)
        self.db.commit()

    # ── Internals ───────────────────────────────────────────────────────

    def _resolve_sources(self, topic: Topic) -> list[SourceConfig]:
        if topic.source_ids:
            return self.db.query(SourceConfig).filter(
                SourceConfig.id.in_(topic.source_ids),
                SourceConfig.is_active == True,
            ).all()
        return self.db.query(SourceConfig).filter(SourceConfig.is_active == True).all()

    def _persist_items(self, items: list[FetchItem], source_id: str, run_id: str,
                       topic_id: str | None = None, window_start: "datetime | None" = None,
                       keywords: list[str] | None = None):
        for fi in items:
            # Skip items whose known publication date is older than the window.
            # Items without a published_at are always kept (date unknown).
            if window_start is not None and fi.published_at is not None:
                pub = fi.published_at
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if pub < window_start:
                    continue

            # Keyword relevance filtering: skip items that don't match the keyword combination
            # Keywords work together as a topic definition, not individually.
            if keywords:
                text = f"{fi.title} {fi.content or ''} {fi.summary or ''}"
                matched_kws = [kw for kw in keywords if kw and kw.lower() in text.lower()]
                total_kw = len([kw for kw in keywords if kw])
                required = max(1, 2 if total_kw >= 3 else total_kw)
                if len(matched_kws) < required:
                    continue
            item_id = fi.item_id(source_id)
            try:
                existing = self.db.query(CollectedItem).filter(CollectedItem.id == item_id).first()
                if existing:
                    if fi.content and fi.content != existing.content:
                        existing.content = fi.content
                    if topic_id and not existing.topic_id:
                        existing.topic_id = topic_id
                    existing.updated_at = utc_now()
                else:
                    self.db.add(CollectedItem(
                        id=item_id, source_id=source_id, run_id=run_id,
                        topic_id=topic_id,
                        title=fi.title, content=fi.content,
                        content_hash=_hash(fi.content or fi.title),
                        summary=fi.summary, url=fi.url,
                        language=fi.language, category=fi.category,
                        entities=fi.entities,
                        quality_score=fi.quality_score,
                        relevance_score=fi.relevance_score,
                        published_at=fi.published_at,
                        collected_at=utc_now(),
                        raw_metadata=fi.raw_metadata,
                        status=ItemStatus.RAW,
                    ))
                self.db.flush()
            except Exception:
                self.db.rollback()
        self.db.commit()

    def _update_source(self, source: SourceConfig, items_found: int):
        source.last_sync_at = utc_now()
        source.items_collected += items_found


def _hash(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()
