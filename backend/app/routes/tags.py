"""Tags CRUD, merge, stats."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.collection_schemas import (
    TagMergeRequest, TagMergeResult, TagOut, TagStatsOut, TagUpdateIn,
)
from app.database import get_db
from app.services.tag_service import (
    list_tags as _list_tags,
    update_tag as _update_tag,
    delete_tag as _delete_tag,
    merge_tags as _merge_tags,
    tag_stats as _tag_stats,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["tags"])


@router.get("/tags", response_model=list[TagOut])
def list_tags(
    namespace: str | None = None,
    sort_by: str = "item_count",
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return _list_tags(db, namespace=namespace, sort_by=sort_by, limit=limit)


@router.get("/tags/stats", response_model=list[TagStatsOut])
def tag_stats(limit: int = 50, db: Session = Depends(get_db)):
    return _tag_stats(db, limit=limit)


@router.put("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: str, data: TagUpdateIn, db: Session = Depends(get_db)):
    return _update_tag(db, tag_id, data.model_dump(exclude_unset=True))


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: str, db: Session = Depends(get_db)):
    _delete_tag(db, tag_id)
    return {"ok": True}


@router.post("/tags/merge", response_model=TagMergeResult)
def merge_tags(data: TagMergeRequest, db: Session = Depends(get_db)):
    result = _merge_tags(db, data.source_tag_id, data.target_tag_id)
    return TagMergeResult(
        target_tag_id=result["target_tag_id"],
        moved_items=result["moved_items"],
        deleted_tag_id=result["deleted_tag_id"],
    )
