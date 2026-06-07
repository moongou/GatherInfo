"""
Report Engine — Generates comprehensive reports from collected items using an LLM.

Architecture:
    Topic → CollectedItem[] → Build prompt → LLM call → Report (persisted)

Supports:
    - Local models via Ollama API
    - OpenAI-compatible APIs
    - LM Studio local inference
"""

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


async def generate_report(
    topic_id: str,
    model_id: str | None = None,
    title_override: str | None = None,
    collection_run_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> Report:
    """
    Main entry point: generate a report for a topic using the specified (or default) model.

    Scope:
        - collection_run_id: only include items from that specific collection run
        - date_from / date_to (ISO strings): restrict items by published/collected window
        - otherwise: all items for the topic
    """
    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise ValueError(f"Topic not found: {topic_id}")

        # Resolve model
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
                raise ValueError("No default active model configured. Add a model in 模型配置 first.")

        # Parse optional date window
        dt_from = _parse_iso(date_from)
        dt_to = _parse_iso(date_to)

        # Fetch items for this topic (optionally scoped)
        q = db.query(CollectedItem).filter(CollectedItem.topic_id == topic_id)
        if collection_run_id:
            q = q.filter(CollectedItem.run_id == collection_run_id)
        if dt_from:
            q = q.filter(CollectedItem.collected_at >= dt_from)
        if dt_to:
            q = q.filter(CollectedItem.collected_at <= dt_to)
        items = q.order_by(CollectedItem.published_at.desc()).all()
        if not items:
            raise ValueError(f"No collected items found for topic '{topic.name}'")

        # Derive the actual data time range from items
        collected_times = [it.collected_at for it in items if it.collected_at]
        range_start = dt_from or (min(collected_times) if collected_times else None)
        range_end = dt_to or (max(collected_times) if collected_times else None)

        # Build context
        item_context = _build_item_context(items)

        # Translate non-Chinese items to Chinese for better report quality
        if model and item_context:
            try:
                non_zh = [it for it in item_context if it.get('language', '') not in ('zh', 'zh-CN', 'cn')]
                if non_zh and len(non_zh) <= 50:
                    logger.info("Translating %d non-Chinese items for report %s", len(non_zh), report.id)
                    translated = await _translate_items(model, non_zh, topic)
                    if translated:
                        for t in translated:
                            for orig in item_context:
                                if orig.get('id') == t.get('id'):
                                    orig['title'] = t.get('title', orig['title'])
                                    if t.get('summary'):
                                        orig['summary'] = t.get('summary', orig['summary'])
                                    if t.get('content'):
                                        orig['content'] = t.get('content', orig['content'])
            except Exception as exc:
                logger.warning("Translation step failed (non-blocking): %s", exc)

        prompt = _build_report_prompt(topic, item_context, range_start, range_end)

        # Create report record
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

        # Call the LLM
        try:
            result = await _call_llm(model, prompt)
            report.content = result.get("content", "")
            report.summary = result.get("summary", "")
            report.tokens_used = result.get("tokens_used", 0)
            report.status = "completed"
            report.generated_at = datetime.now(timezone.utc)
            # Export to disk (MD/HTML/DOCX/PDF) per SystemConfig. Best-effort.
            _export_report_files(db, report, topic)
        except Exception as exc:
            report.status = "failed"
            report.error_log = str(exc)
            logger.error("Report generation failed: %s", exc)

        db.commit()
        db.refresh(report)
        return report

    except ValueError as exc:
        report = Report(
            id=f"rpt-{uuid4().hex[:12]}",
            topic_id=topic_id,
            title=title_override or "报告生成失败",
            status="failed",
            error_log=str(exc),
        )
        db.add(report)
        db.commit()
        return report
    except Exception as exc:
        logger.exception("Unexpected error generating report")
        report = db.query(Report).order_by(Report.created_at.desc()).first()
        raise
    finally:
        db.close()



async def _translate_items(model: ModelConfig, items: list[dict], topic: Topic) -> list[dict]:
    """Translate non-Chinese item titles and summaries to Chinese."""
    lines = []
    for it in items:
        lines.append("[ID:" + str(it.get("id","")) + "] TITLE: " + str(it.get("title","")))
        if it.get("summary"):
            lines.append("SUMMARY: " + str(it.get("summary","")))
        if it.get("content"):
            lines.append("CONTENT: " + str(it.get("content",""))[:500])
        lines.append("---")
    text = "\n".join(lines)
    prompt = (
        "You are a professional translator. Translate each item below into Chinese.\n"
        + "Keep [ID:xxx] markers unchanged. Keep the original format.\n"
        + "Each item is separated by ---.\n\n"
        + "Original content:\n" + text + "\n\n"
        + "Translated items:"
    )
    try:
        result = await _call_llm(model, prompt)
        output = result.get("content", "")
        translated = []
        blocks = output.split("---")
        for i, it in enumerate(items):
            block = blocks[i] if i < len(blocks) else ""
            new_title = str(it.get("title", ""))
            new_summary = str(it.get("summary", "")) if it.get("summary") else ""
            for line in block.split("\n"):
                line = line.strip()
                if line.startswith("TITLE:"):
                    new_title = line[6:].strip()
                elif line.startswith("SUMMARY:"):
                    new_summary = line[8:].strip()
            translated.append({"id": it.get("id", ""), "title": new_title, "summary": new_summary, "content": ""})
        return translated
    except Exception:
        return []


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO date/datetime string into a tz-aware datetime, or None."""
    if not value:
        return None
    try:
        s = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _export_report_files(db: Session, report: Report, topic: Topic | None) -> None:
    """Render the completed report to disk (best-effort; never raises)."""
    try:
        from app.report_export import export_report
        from app.models import SystemConfig
        system = db.query(SystemConfig).filter(SystemConfig.id == "global").first()
        export_report(report, system, topic)
    except Exception as exc:  # noqa: BLE001 — export must never break generation
        logger.warning("report export skipped: %s", exc)


def _build_item_context(items: list[CollectedItem]) -> list[dict]:
    """Convert CollectedItem list to a structured context dict list."""
    ctx = []
    for it in items:
        tags = [{"namespace": t.namespace, "value": t.value} for t in (it.tags or [])]
        ctx.append({
            "id": it.id,
            "title": it.title,
            "summary": it.summary or "",
            "content": (it.content or "")[:2000],  # Truncate to fit context
            "url": it.url or "",
            "source": it.source_id,
            "language": it.language or "unknown",
            "category": it.category or "unknown",
            "tags": tags,
            "published_at": it.published_at.isoformat() if it.published_at else "",
            "relevance_score": it.relevance_score or 0.0,
        })
    return ctx


def _build_report_prompt(
    topic: Topic,
    items: list[dict],
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> str:
    """Build a structured prompt for the LLM to generate a comprehensive report."""

    item_lines = []
    for i, item in enumerate(items, 1):
        tags_str = ", ".join(f"{t['namespace']}:{t['value']}" for t in item["tags"]) if item["tags"] else "-"
        item_lines.append(f"""
[{i}] {item['title']}
    来源: {item['source']} | 语言: {item['language']} | 分类: {item['category']}
    标签: {tags_str}
    相关性: {item['relevance_score']}
    摘要: {item.get('summary', '')}
    内容: {item.get('content', '')[:500]}
""")

    items_text = "".join(item_lines)

    # Build keyword_tags summary
    keyword_info = ""
    if topic.keyword_tags:
        try:
            kws = json.loads(topic.keyword_tags) if isinstance(topic.keyword_tags, str) else topic.keyword_tags
            lines = [f"  - {kw.get('keyword', '')} (权重: {kw.get('weight', 1.0)})" for kw in kws if kw.get('keyword')]
            if lines:
                keyword_info = "关键词及权重:\n" + "\n".join(lines)
        except (json.JSONDecodeError, TypeError):
            pass

    range_info = ""
    if range_start or range_end:
        start_str = range_start.strftime("%Y-%m-%d") if range_start else "(不限)"
        end_str = range_end.strftime("%Y-%m-%d") if range_end else "(不限)"
        range_info = f"\n数据时间范围: {start_str} 至 {end_str}"

    prompt = f"""你是一位专业的跨境贸易与监管情报分析师。请根据以下采集到的信息，生成一份结构化综合分析报告。

【重要规则 - 必须遵守】
⚠️ 禁止虚构：本报告必须严格基于下方【详细条目】中的数据。不得捏造任何事实、数据、引文或观点。
⚠️ 每一条结论都必须引用对应的条目编号作为证据，格式为 [参见条目N](条目原文链接)。
⚠️ 如果某个方向的证据不足，请明确说明"当前采集数据中未找到相关证据"。
⚠️ 如果采集数据为空或不足以支撑报告框架，请在报告中如实反映数据局限性。
⚠️ 所有观点必须有来源。没有来源的观点将视为无效。

【主题信息】
主题名称: {topic.name}
主题描述: {topic.description or '(无)'}
{keyword_info}

【采集数据概览】
共 {len(items)} 条信息条目，跨越不同来源、语言和分类。{range_info}

【详细条目】{items_text}

【报告要求】
请按照以下结构生成中文报告（约 1500-3000 字）：

1. **执行摘要**（Executive Summary）- 200字以内的核心结论
2. **关键发现**（Key Findings）- 列出最重要的 3-5 个发现
3. **数据概览**（Data Overview）- 来源分布、分类统计、时间趋势
4. **详细分析**（Detailed Analysis）- 按主题或类别深入分析关键条目
5. **趋势研判**（Trend Assessment）- 对重要信号的趋势判断
6. **建议行动**（Recommended Actions）- 基于发现的可操作建议

格式要求：
- 使用 Markdown 格式
- 每个部分以 "## " 标题开头
- 关键数据点和引用标注对应条目编号，如 [参见条目1]
- 语言：中文
- 引用条目时标注编号，编号可点击查看原文，如 [参见条目1](条目原文链接)

请回复两份内容，以 ===SEPARATOR=== 分隔：
第一部分：报告全文
第二部分：150字以内的摘要
"""
    return prompt


async def _call_llm(model: ModelConfig, prompt: str) -> dict[str, Any]:
    """Call the LLM and return parsed result."""
    base_url = model.base_url or "http://localhost:11434"
    model_name = model.model_name

    if model.provider == "ollama":
        url = f"{base_url.rstrip('/')}/api/chat"
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "你是一位专业的跨境贸易与监管情报分析师。你只能使用下面提供的采集数据进行报告撰写。禁止虚构任何事实、数据或引用。每个观点必须有对应的条目编号和来源URL作为依据。如果采集数据不足以支持某个观点，请明确指出数据不足。如果采集数据为空，请如实报告无数据可用。"},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": model.temperature or 0.7,
                "num_predict": model.max_tokens or 4096,
            },
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            full = data.get("message", {}).get("content", "")

    elif model.provider in ("openai", "lmstudio", "custom", "cc_switch"):
        base = base_url.rstrip("/")
        url = f"{base}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if model.api_key:
            headers["Authorization"] = f"Bearer {model.api_key}"
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "你是一位专业的跨境贸易与监管情报分析师。你只能使用下面提供的采集数据进行报告撰写。禁止虚构任何事实、数据或引用。每个观点必须有对应的条目编号和来源URL作为依据。如果采集数据不足以支持某个观点，请明确指出数据不足。如果采集数据为空，请如实报告无数据可用。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": model.temperature or 0.7,
            "max_tokens": model.max_tokens or 4096,
            "top_p": model.top_p or 0.9,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            full = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    else:
        raise ValueError(f"Unsupported provider: {model.provider}")

    # Parse separator
    parts = full.split("===SEPARATOR===")
    content = parts[0].strip() if parts else full
    summary = parts[1].strip() if len(parts) > 1 else _auto_summary(content)

    return {
        "content": content,
        "summary": summary,
        "tokens_used": len(full.split()),
    }


def _auto_summary(text: str) -> str:
    """Fallback: first 200 chars as summary."""
    return text[:200] + ("..." if len(text) > 200 else "")
