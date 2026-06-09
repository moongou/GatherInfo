"""Source business logic."""
import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import SourceConfig

logger = logging.getLogger(__name__)


def create_source(db: Session, data: dict) -> SourceConfig:
    """Create a new source config with auto-generated ID if not provided."""
    from uuid import uuid4
    source_id = data.get("id") or f"src-{uuid4().hex[:8]}"
    if db.query(SourceConfig).filter(SourceConfig.id == source_id).first():
        raise HTTPException(400, f"Source '{source_id}' already exists")
    cfg = SourceConfig(id=source_id, **{k: v for k, v in data.items() if k != "id"})
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def update_source(db: Session, source_id: str, data: dict) -> SourceConfig:
    """Update an existing source config."""
    cfg = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if not cfg:
        raise HTTPException(404, f"Source not found: {source_id}")
    for k, v in data.items():
        setattr(cfg, k, v)
    db.commit()
    db.refresh(cfg)
    return cfg


def delete_source(db: Session, source_id: str) -> None:
    """Delete a source config."""
    cfg = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if not cfg:
        raise HTTPException(404, f"Source not found: {source_id}")
    db.delete(cfg)
    db.commit()


def list_sources(db: Session, channel: str | None = None, is_active: bool | None = None):
    """List sources with optional filters."""
    q = db.query(SourceConfig)
    if channel:
        q = q.filter(SourceConfig.channel == channel)
    if is_active is not None:
        q = q.filter(SourceConfig.is_active == is_active)
    return q.order_by(SourceConfig.name).all()


def get_source(db: Session, source_id: str) -> SourceConfig:
    """Get a single source by ID."""
    cfg = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if not cfg:
        raise HTTPException(404, f"Source not found: {source_id}")
    return cfg
