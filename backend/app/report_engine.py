"""
Report Engine — Generates comprehensive reports from collected items using an LLM.

Architecture:
    Topic → CollectedItem[] → Build prompt → LLM call → Report (persisted)

Supports:
    - Local models via Ollama API
    - OpenAI-compatible APIs
    - LM Studio local inference
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import CollectedItem, Topic, ModelConfig, Report

logger = logging.getLogger(__name__)

# Re-export LLM client functions for backward compatibility
from app.llm_client import call_llm as _call_llm, auto_summary as _auto_summary, translate_item_context as _translate_item_context  # noqa: E501


async def generate_report(
    topic_id: str,
    model_id: str | None = None,
    title_override: str | None = None,
    collection_run_id: str | None = None,
    collection_run_ids: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    model_name_override: str | None = None,
) -> Report:
    """Main entry point: generate a report for a topic using the specified model."""
    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise ValueError(f"Topic not found: {topic_id}")

        model = None
        if model_id:
            model = db.query(ModelConfig).filter(
                ModelConfig.id == model_id, ModelConfig.is_active == True
            ).first()
            if not model:
                raise ValueError(f"Model not found or inactive: {model_id}")
        else:
            model = db.query(ModelConfig).filter(
                ModelConfig.is_default == True, ModelConfig.is_active == True
            ).first()
            if not model:
                raise ValueError("No default active model configured.")

        dt_from = _parse_iso(date_from)
        dt_to = _parse_iso(date_to)

        q = db.query(CollectedItem).filter(CollectedItem.topic_id == topic_id)
        if collection_run_ids:
            q = q.filter(CollectedItem.run_id.in_(collection_run_ids))
        elif collection_run_id:
            q = q.filter(CollectedItem.run_id == collection_run_id)
        if dt_from:
            q = q.filter(CollectedItem.collected_at >= dt_from)
        if dt_to:
            q = q.filter(CollectedItem.collected_at <= dt_to)
        items = q.order_by(CollectedItem.published_at.desc()).all()
        if not items:
            raise ValueError(f"No collected items found for topic '{topic.name}'")

        collected_times = [it.collected_at for it in items if it.collected_at]
        range_start = dt_from or (min(collected_times) if collected_times else None)
        range_end = dt_to or (max(collected_times) if collected_times else None)

        item_context = _build_item_context(items)

        # Translate non-Chinese items to Chinese
        if model and item_context:
            try:
                non_zh = [
                    it for it in item_context
                    if it.get('language', '') not in ('zh', 'zh-CN', 'cn')
                ]
                if non_zh and len(non_zh) <= 50:
                    logger.info("Translating %d non-Chinese items for topic %s",
                                len(non_zh), topic_id)
                    await _translate_item_context(model, non_zh)
            except Exception as exc:
                logger.warning("Translation step failed (non-blocking): %s", exc,
                               exc_info=True)

        prompt = _build_report_prompt(topic, item_context, range_start, range_end)

        report = Report(
            id=f"rpt-{uuid4().hex[:12]}",
            topic_id=topic_id,
            title=title_override or f"{topic.name} 综合分析报告",
            status="generating",
            model_id=model.id,
            item_count=len(items),
            item_ids=[it.id for it in items],
            collection_run_id=collection_run_id,
            date_range_start=range_start,
            date_range_end=range_end,
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        try:
            llm_result = await _call_llm(model, prompt)
            report.content = llm_result["content"]
            report.summary = llm_result["summary"]
            report.tokens_used = llm_result["tokens_used"]
            report.status = "completed"
        except Exception as exc:
            logger.error("LLM call failed for report %s: %s", report.id, exc)
            report.status = "failed"
            report.error_log = str(exc)

        db.commit()
        db.refresh(report)

        try:
            _export_report_files(db, report, topic)
        except Exception as exc:
            logger.warning("Export step failed for report %s: %s", report.id, exc)

        return report
    finally:
        db.close()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        s = value.strip()
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _export_report_files(db: Session, report: Report, topic: Topic | None) -> None:
    try:
        from app.report_export import export_report
        export_report(report, db, topic)
    except ImportError:
        logger.warning("report_export module not available, skipping export")


def _build_item_context(items: list[CollectedItem]) -> list[dict]:
    """Build structured item context dict from ORM objects for prompt building."""
    context = []
    for idx, it in enumerate(items, 1):
        context.append({
            "id": it.id,
            "index": idx,
            "title": it.title or "",
            "content": (it.content or "")[:2000],
            "summary": it.summary or "",
            "url": it.url or "",
            "language": it.language or "unknown",
            "category": it.category or "unknown",
            "source": it.source_id or "",
            "tags": [{"namespace": t.namespace, "value": t.value}
                     for t in it.tags] if it.tags else [],
            "published_at": it.published_at.isoformat() if it.published_at else "",
            "quality_score": it.quality_score or 0.0,
            "relevance_score": it.relevance_score or 0.0,
        })
    return context


def _build_report_prompt(
    topic: Topic,
    items: list[dict],
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> str:
    """Build the LLM prompt from topic metadata and item context."""
    # Keywords with weights
    kw_info = ""
    if getattr(topic, 'keyword_tags', None):
        try:
            kw_tags = json.loads(topic.keyword_tags) if isinstance(
                topic.keyword_tags, str) else topic.keyword_tags
            if kw_tags:
                kw_lines = [f"- {t['keyword']}（权重: {t['weight']}）"
                           for t in kw_tags]
                kw_info = "关键词及权重:\n" + "\n".join(kw_lines) + "\n"
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    # Date range
    range_info = ""
    if range_start:
        start_str = range_start.strftime("%Y-%m-%d")
        end_str = range_end.strftime("%Y-%m-%d") if range_end else "(不限)"
        range_info = f"数据时间范围: {start_str} ~ {end_str}\n"

    # Items text — use enumerate for robust indexing
    items_text_parts = []
    for idx, it in enumerate(items, 1):
        title = it.get("title", "")
        source = it.get("source", "")
        url = it.get("url", "")
        category = it.get("category", "unknown")
        summary = it.get("summary", "")
        content = it.get("content", "")
        index = it.get("index", idx)
        parts = [
            f"## 条目 {index}",
            f"- 标题: {title}",
            f"- 来源: {source}",
            f"- URL: {url}",
            f"- 分类: {category}",
        ]
        if summary:
            parts.append(f"- 内容摘要: {summary}")
        if content:
            parts.append(f"\n{content[:2000]}")
        items_text_parts.append("\n".join(parts))
    items_text = "\n\n".join(items_text_parts)

    prompt = f"""你是一位专业的跨境贸易监管与风险情报分析师。
请基于以下采集数据，为用户生成一份专业的综合分析报告。

【主题信息】
主题名称: {topic.name}
主题描述: {topic.description or '(无)'}
{kw_info}
{range_info}
【采集数据】
共 {len(items)} 条信息条目。

【详细条目】

{items_text}

【报告要求】
请按照以下结构生成中文报告（约 1500-3000 字）：

1. **执行摘要** — 200字以内的核心结论
2. **关键发现** — 列出最重要的 3-5 个发现
3. **数据概览** — 来源分布、分类统计、时间趋势
4. **详细分析** — 按主题或类别深入分析关键条目
5. **趋势研判** — 对重要信号的趋势判断
6. **建议行动** — 基于发现的可操作建议

格式要求：
- 使用 Markdown 格式，每个部分以 "## " 标题开头
- 引用条目时标注编号，如 [参见条目1]
- 语言：中文

请回复两份内容，以 ===SEPARATOR=== 分隔：
第一部分：报告全文
第二部分：150字以内的摘要
"""
    return prompt
