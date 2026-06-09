"""Data export utilities — CSV, JSON, XLSX helpers for collected items."""
import csv
import io
import json
import logging
from datetime import datetime, timezone

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


def _item_tags_dict(item) -> list[dict]:
    """Extract tags from an item as list of dicts."""
    if not item.tags:
        return []
    return [{"id": t.id, "namespace": t.namespace, "value": t.value, "label": t.label}
            for t in item.tags]


def _format_dt(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _export_csv(items):
    """Generate CSV with UTF-8 BOM for Excel compatibility."""
    output = io.StringIO()
    output.write("\ufeff")  # BOM
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "id", "title", "content", "summary", "url", "source_id",
        "language", "category", "tags", "quality_score", "relevance_score",
        "collected_at", "published_at"
    ])

    for item in items:
        tags_str = "; ".join(
            f"{t.namespace}:{t.value}" for t in (item.tags or [])
        )
        writer.writerow([
            item.id,
            item.title,
            (item.content or "")[:500],
            item.summary or "",
            item.url or "",
            item.source_id,
            item.language or "",
            item.category or "",
            tags_str,
            item.quality_score or 0,
            item.relevance_score or 0,
            _format_dt(item.collected_at) or "",
            _format_dt(item.published_at) or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=gatherinfo_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        },
    )


def _export_json(items):
    """Generate JSON export."""
    data = []
    for item in items:
        data.append({
            "id": item.id,
            "title": item.title,
            "content": item.content,
            "summary": item.summary,
            "url": item.url,
            "source_id": item.source_id,
            "language": item.language,
            "category": item.category,
            "tags": _item_tags_dict(item),
            "quality_score": item.quality_score,
            "relevance_score": item.relevance_score,
            "collected_at": _format_dt(item.collected_at),
            "published_at": _format_dt(item.published_at),
        })

    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    return StreamingResponse(
        iter([json_bytes]),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=gatherinfo_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        },
    )


def _export_xlsx(items):
    """Generate XLSX using openpyxl if available, fallback to CSV."""
    try:
        import openpyxl
    except ImportError:
        # Fallback to CSV with warning header
        logger.warning("openpyxl not installed, falling back to CSV export")
        return _export_csv(items)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Collected Items"

    # Header
    headers = [
        "ID", "Title", "Content", "Summary", "URL", "Source",
        "Language", "Category", "Tags", "Quality", "Relevance",
        "Collected At", "Published At"
    ]
    ws.append(headers)

    for item in items:
        tags_str = "; ".join(
            f"{t.namespace}:{t.value}" for t in (item.tags or [])
        )
        ws.append([
            item.id,
            item.title,
            (item.content or "")[:500],
            item.summary or "",
            item.url or "",
            item.source_id,
            item.language or "",
            item.category or "",
            tags_str,
            item.quality_score or 0,
            item.relevance_score or 0,
            _format_dt(item.collected_at),
            _format_dt(item.published_at),
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=gatherinfo_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
        },
    )
