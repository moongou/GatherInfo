"""Tag schemas."""
from pydantic import BaseModel, Field
from .common import IsoDT


class TagUpdateIn(BaseModel):
    id: str | None = None
    namespace: str | None = None
    value: str | None = None
    label: str | None = None
    color: str | None = None


class TagUpdateSchema(BaseModel):
    namespace: str | None = None
    value: str | None = None
    label: str | None = None
    color: str | None = None


class TagOut(BaseModel):
    id: str
    namespace: str = "default"
    value: str
    label: str | None = None
    color: str | None = None
    item_count: int = 0
    last_seen_at: IsoDT = None
    model_config = {"from_attributes": True}


class TagMergeRequest(BaseModel):
    source_tag_id: str
    target_tag_id: str


class TagMergeResult(BaseModel):
    target_tag_id: str
    moved_items: int
    deleted_tag_id: str
