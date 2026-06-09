"""Shared base types, stats, system config schemas."""
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field


def _iso(v: Any) -> str | None:
    if v is None: return None
    if isinstance(v, datetime): return v.isoformat()
    return str(v) if v else None

IsoDT = Annotated[str | None, BeforeValidator(_iso)]


class StatsOut(BaseModel):
    total_sources: int = 0
    active_sources: int = 0
    total_topics: int = 0
    active_topics: int = 0
    total_items: int = 0
    items_today: int = 0
    total_tags: int = 0
    total_schedules: int = 0
    last_collection_at: IsoDT = None


class TagStatsOut(BaseModel):
    tag_id: str
    namespace: str
    value: str
    item_count: int = 0
    last_seen_at: IsoDT = None
    categories: dict = {}
    languages: dict = {}
    sources: dict = {}


class ConnectorInfo(BaseModel):
    channel: str
    description: str
    default_base_url: str | None = None
    default_api_endpoint: str | None = None
    required_fields: list[str] = []
    optional_fields: list[str] = []
    homepage_hint: str | None = None
    supports_pagination: bool = False
    support_level: str = "basic"  # full / partial / basic
    model_config = {"from_attributes": True}


class SystemConfigOut(BaseModel):
    report_title_format: str = "{topic}_情报报告_{date}"
    report_output_dir: str | None = None
    report_dir_pattern: str = "%Y-%m-%d"
    report_formats: list[str] = ["md", "html", "docx", "pdf"]
    model_config = {"from_attributes": True}


class SystemConfigUpdate(BaseModel):
    report_title_format: str | None = Field(default=None, min_length=1, max_length=200)
    report_output_dir: str | None = None
    report_dir_pattern: str | None = Field(default=None, min_length=1, max_length=50)
    report_formats: list[str] | None = Field(default=None, min_length=1, max_length=10)
