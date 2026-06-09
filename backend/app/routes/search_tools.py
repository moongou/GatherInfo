"""Auto-generated route module."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db

logger = logging.getLogger(__name__)
from app.collection_schemas import (
    SearchToolConfigCreate, SearchToolConfigOut, SearchToolConfigUpdate,
)
from app.models import SearchToolConfig

router = APIRouter(prefix="/api/v1", tags=["search-tools"])



@router.get("/search-tools", response_model=list[SearchToolConfigOut])
def list_search_tools(db: Session = Depends(get_db)):
    return db.query(SearchToolConfig).order_by(SearchToolConfig.created_at.desc()).all()


@router.post("/search-tools", response_model=SearchToolConfigOut, status_code=201)
def create_search_tool(data: SearchToolConfigCreate, db: Session = Depends(get_db)):
    if db.query(SearchToolConfig).filter(SearchToolConfig.id == data.id).first():
        raise HTTPException(400, f"Search tool '{data.id}' exists")
    st = SearchToolConfig(**data.model_dump())
    db.add(st)
    db.commit()
    db.refresh(st)
    return st


@router.put("/search-tools/{tool_id}", response_model=SearchToolConfigOut)
def update_search_tool(tool_id: str, data: SearchToolConfigUpdate, db: Session = Depends(get_db)):
    st = db.query(SearchToolConfig).filter(SearchToolConfig.id == tool_id).first()
    if not st:
        raise HTTPException(404)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(st, k, v)
    db.commit()
    db.refresh(st)
    return st


@router.delete("/search-tools/{tool_id}")
def delete_search_tool(tool_id: str, db: Session = Depends(get_db)):
    st = db.query(SearchToolConfig).filter(SearchToolConfig.id == tool_id).first()
    if not st:
        raise HTTPException(404)
    db.delete(st)
    db.commit()
    return {"ok": True}


