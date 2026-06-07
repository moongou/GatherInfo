"""
Pydantic schemas for GatherInfo management API.
"""
from datetime import datetime
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, Field


# ── Datetime coercion ────────────────────────────────────────────────────────

def _iso(v: Any) -> str | None:
    if v is None: return None
    if isinstance(v, datetime): return v.isoformat()
    return str(v) if v else None

IsoDT = Annotated[str | None, BeforeValidator(_iso)]


# ── Source ───────────────────────────────────────────────────────────────────

class SourceCreate(BaseModel):
    id: str | None = Field(default=None, max_length=80, description="留空则由后端从 name 自动生成")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    channel: str = Field(description="official | rss | commercial | web_scrape | api_search | social | deepweb | manual")
    is_active: bool = True
    base_url: str | None = None
    api_endpoint: str | None = None
    homepage_url: str | None = None
    api_key_ref: str | None = None
    api_key: str | None = None
    auth_config: dict | None = None
    rate_limit_rps: float = Field(default=1.0, gt=0)
    max_retries: int = Field(default=3, ge=0)
    timeout_seconds: int = Field(default=30, gt=0)
    max_items_per_run: int = Field(default=100, gt=0)
    default_keywords: list[str] | None = None
    default_categories: list[str] | None = None
    languages: list[str] | None = None
    country_focus: list[str] | None = None
    legal_basis: str | None = None
    compliance_note: str | None = None


class SourceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    base_url: str | None = None
    api_endpoint: str | None = None
    homepage_url: str | None = None
    api_key_ref: str | None = None
    api_key: str | None = None
    auth_config: dict | None = None
    rate_limit_rps: float | None = None
    default_keywords: list[str] | None = None
    default_categories: list[str] | None = None
    languages: list[str] | None = None


class SourceOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    channel: str
    is_active: bool
    base_url: str | None = None
    api_endpoint: str | None = None
    homepage_url: str | None = None
    api_key: str | None = None
    default_keywords: list | None = None
    default_categories: list | None = None
    languages: list | None = None
    country_focus: list | None = None
    last_sync_at: IsoDT = None
    last_error: str | None = None
    items_collected: int = 0
    created_at: IsoDT = None
    updated_at: IsoDT = None
    model_config = {"from_attributes": True}


# ── Topic ────────────────────────────────────────────────────────────────────

class TopicCreate(BaseModel):
    id: str | None = Field(default=None, max_length=80, description="留空则由后端从 name 自动生成")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category_id: str | None = None
    keywords: list[str] = Field(default_factory=list, max_length=50)
    synonyms: list[str] | None = None
    exclude_keywords: list[str] | None = None
    categories: list[str] | None = None
    focus_countries: list[str] | None = None
    focus_languages: list[str] | None = None
    source_ids: list[str] | None = None
    target_urls: list[str] | None = None
    auto_tag_rules: list[dict] | None = None
    schedule_cron: str | None = None
    is_scheduled: bool = False
    is_active: bool = True
    auto_report: bool = False
    auto_report_model_id: str | None = None
    keyword_tags: list[dict] | None = None
    description_prompt: str | None = None
    collect_window_days: int = Field(default=7, ge=0, le=365)


class TopicUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category_id: str | None = None
    keywords: list[str] | None = None
    synonyms: list[str] | None = None
    categories: list[str] | None = None
    source_ids: list[str] | None = None
    target_urls: list[str] | None = None
    auto_tag_rules: list[dict] | None = None
    schedule_cron: str | None = None
    is_scheduled: bool | None = None
    is_active: bool | None = None
    auto_report: bool | None = None
    auto_report_model_id: str | None = None
    keyword_tags: list[dict] | None = None
    description_prompt: str | None = None
    collect_window_days: int | None = None


class TopicOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    category_id: str | None = None
    category_name: str | None = None
    keywords: list = []
    synonyms: list | None = None
    categories: list | None = None
    focus_countries: list | None = None
    focus_languages: list | None = None
    source_ids: list | None = None
    target_urls: list | None = None
    auto_tag_rules: list | None = None
    is_scheduled: bool = False
    schedule_cron: str | None = None
    is_active: bool = True
    auto_report: bool = False
    auto_report_model_id: str | None = None
    keyword_tags: list | None = None
    description_prompt: str | None = None
    collect_window_days: int = 7
    last_collection_run_id: str | None = None
    total_items_collected: int = 0
    source_names: list[str] = []
    last_run_at: IsoDT = None
    next_run_at: IsoDT = None
    created_at: IsoDT = None
    updated_at: IsoDT = None
    model_config = {"from_attributes": True}


# ── Schedule ─────────────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    id: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    source_ids: list[str] | None = None
    topic_ids: list[str] | None = None
    keywords: list[str] | None = None
    cron_expression: str = Field(description="Standard 5-field cron")
    timezone: str = "Asia/Shanghai"
    is_active: bool = True
    max_items_per_run: int = Field(default=100, gt=0)


class ScheduleOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    source_ids: list | None = None
    topic_ids: list | None = None
    cron_expression: str
    is_active: bool
    last_run_at: IsoDT = None
    next_run_at: IsoDT = None
    run_count: int = 0
    last_status: str | None = None
    model_config = {"from_attributes": True}


# ── Collection ───────────────────────────────────────────────────────────────

class CollectRequest(BaseModel):
    topic_id: str | None = Field(default=None, max_length=80)
    source_id: str | None = Field(default=None, max_length=80)
    keywords: list[str] | None = Field(default=None, min_length=1, max_length=50)


class RunOut(BaseModel):
    id: str
    source_id: str
    topic_id: str | None = None
    status: str
    items_found: int = 0
    items_new: int = 0
    items_failed: int = 0
    started_at: IsoDT = None
    completed_at: IsoDT = None
    duration_ms: int | None = None
    window_start: IsoDT = None
    window_end: IsoDT = None
    error_log: list | None = None
    model_config = {"from_attributes": True}


class CollectResultOut(BaseModel):
    run: RunOut
    total_items: int
    items_new: int
    errors: list[str] | None = None


# ── Item ─────────────────────────────────────────────────────────────────────

class ItemOut(BaseModel):
    id: str
    source_id: str
    run_id: str | None = None
    title: str
    content: str | None = None
    summary: str | None = None
    url: str | None = None
    language: str | None = None
    category: str | None = None
    tags: list[dict] = []   # [{id, namespace, value, label}]
    entities: dict | None = None
    quality_score: float = 0.0
    relevance_score: float = 0.0
    status: str = "raw"
    collected_at: IsoDT = None
    published_at: IsoDT = None
    model_config = {"from_attributes": True}


class ItemListOut(BaseModel):
    items: list[ItemOut]
    total: int
    page: int
    page_size: int


# ── Tag ──────────────────────────────────────────────────────────────────────

class TagUpdateIn(BaseModel):
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
    namespace: str
    value: str
    label: str | None = None
    color: str | None = None
    item_count: int = 0
    last_seen_at: IsoDT = None
    model_config = {"from_attributes": True}


# ── Stats ────────────────────────────────────────────────────────────────────

class StatsOut(BaseModel):
    total_sources: int
    active_sources: int
    total_topics: int
    active_topics: int
    total_items: int
    items_today: int
    total_tags: int
    total_schedules: int
    last_collection_at: IsoDT = None


class TagStatsOut(BaseModel):
    """Statistics grouped by tag."""
    tag_id: str
    namespace: str
    value: str
    item_count: int
    last_seen_at: IsoDT = None
    categories: dict[str, int] = {}     # category → count
    languages: dict[str, int] = {}      # language → count
    sources: dict[str, int] = {}        # source_id → count


# ── Connector Info ───────────────────────────────────────────────────────────

class ConnectorInfo(BaseModel):
    channel: str
    description: str
    default_base_url: str | None = None
    default_api_endpoint: str | None = None
    required_fields: list[str] = []        # fields the user must fill for this channel
    optional_fields: list[str] = []        # fields that are optional
    homepage_hint: str | None = None       # where to buy/subscribe the service


# ═══════════════════════════════════════════════════════════════════════════════
# Model Configuration
# ═══════════════════════════════════════════════════════════════════════════════

class ModelConfigCreate(BaseModel):
    id: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    provider: str = Field(description="ollama | openai | lmstudio | cc_switch | custom")
    base_url: str | None = None
    api_key: str | None = None
    model_name: str = Field(default="", description="Model name on the server")
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    is_default: bool = False
    is_active: bool = True
    description: str | None = None


class ModelConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    description: str | None = None


class ModelConfigOut(BaseModel):
    id: str
    name: str
    provider: str
    base_url: str | None = None
    api_key: str | None = None
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    is_default: bool = False
    is_active: bool = True
    description: str | None = None
    created_at: IsoDT = None
    updated_at: IsoDT = None
    model_config = {"from_attributes": True}


class ModelTestResult(BaseModel):
    success: bool
    message: str
    response_preview: str | None = None
    duration_ms: int | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Reports
# ═══════════════════════════════════════════════════════════════════════════════

class ReportOut(BaseModel):
    id: str
    topic_id: str
    title: str
    content: str | None = None
    summary: str | None = None
    status: str = "pending"
    model_id: str | None = None
    tokens_used: int = 0
    item_count: int = 0
    item_ids: list | None = None
    error_log: str | None = None
    collection_run_id: str | None = None
    date_range_start: IsoDT = None
    date_range_end: IsoDT = None
    output_files: dict | None = None
    output_dir: str | None = None
    generated_at: IsoDT = None
    created_at: IsoDT = None
    model_config = {"from_attributes": True}


class ReportListOut(BaseModel):
    reports: list[ReportOut]
    total: int


class ReportGenerateRequest(BaseModel):
    topic_id: str = Field(min_length=2, max_length=80)
    model_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    collection_run_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    model_name_override: str | None = None


class BatchGenerateRequest(BaseModel):
    topic_ids: list[str] = Field(min_length=1, max_length=20)
    model_id: str | None = None
    collection_run_ids: list[str] | None = None
    model_name_override: str | None = None  # aligned with topic_ids by index


class BatchGenerateResult(BaseModel):
    results: list[ReportOut]
    failed: int


# ═══════════════════════════════════════════════════════════════════════════════
# Search Tool Config
# ═══════════════════════════════════════════════════════════════════════════════

class SearchToolConfigCreate(BaseModel):
    id: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    tool_type: str = Field(description="tavily | rss | web_scrape | official_api | social | custom")
    is_active: bool = True
    config_json: dict | None = None
    api_key_ref: str | None = None
    is_default: bool = False


class SearchToolConfigUpdate(BaseModel):
    name: str | None = None
    tool_type: str | None = None
    is_active: bool | None = None
    config_json: dict | None = None
    api_key_ref: str | None = None
    is_default: bool | None = None


class SearchToolConfigOut(BaseModel):
    id: str
    name: str
    tool_type: str
    is_active: bool = True
    config_json: dict | None = None
    api_key_ref: str | None = None
    is_default: bool = False
    created_at: IsoDT = None
    updated_at: IsoDT = None
    model_config = {"from_attributes": True}


class ListModelsResult(BaseModel):
    success: bool
    message: str
    models: list[str] = []
    provider_type: str = ""
    current_model: str = ""


# ═════════════════════════════════════════════════════════════════════════
# Tag Merge
# ═════════════════════════════════════════════════════════════════════════

class TagMergeRequest(BaseModel):
    source_tag_id: str
    target_tag_id: str


class TagMergeResult(BaseModel):
    target_tag_id: str
    moved_items: int
    deleted_tag_id: str


# ═════════════════════════════════════════════════════════════════════════
# Model Auto-Discover
# ═════════════════════════════════════════════════════════════════════════

class DiscoveredProvider(BaseModel):
    provider: str
    base_url: str
    models: list[str] = []
    reachable: bool = True
    note: str | None = None


class AutoDiscoverResult(BaseModel):
    providers: list[DiscoveredProvider] = []


# ═════════════════════════════════════════════════════════════════════════
# System Config (报告设置等全局配置)
# ═════════════════════════════════════════════════════════════════════════


class ItemDeleteRequest(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=500)


# ════════════════════════════════════════════════════════════════════════
# Category (采集类别 — 主题的上层分类)
# ════════════════════════════════════════════════════════════════════════

class CategoryCreate(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None

class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

class CategoryOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: IsoDT = None
    updated_at: IsoDT = None
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



# ════════════════════════════════════════════════════════════════════════
# Collection Batch / History
# ════════════════════════════════════════════════════════════════════════

class BatchRunOut(BaseModel):
    """A single collection run within a batch."""
    id: str
    source_id: str
    topic_id: str | None = None
    status: str
    items_new: int = 0
    items_found: int = 0
    items_failed: int = 0
    started_at: IsoDT = None
    completed_at: IsoDT = None
    duration_ms: int | None = None
    error_log: list | None = None
    source_name: str | None = None


class BatchOut(BaseModel):
    """A batch = collection runs sharing the same batch_id."""
    batch_id: str
    topic_id: str | None = None
    topic_name: str | None = None
    batch_label: str | None = None
    status: str
    total_items: int = 0
    total_new: int = 0
    started_at: IsoDT = None
    completed_at: IsoDT = None
    source_count: int = 0
    runs: list[BatchRunOut] = []


class ActiveRunOut(BaseModel):
    """Currently executing collection run, shown on the history UI."""
    id: str
    source_id: str
    source_name: str | None = None
    topic_id: str | None = None
    topic_name: str | None = None
    status: str
    keywords_used: list[str] = []
    items_found: int = 0
    items_new: int = 0
    started_at: IsoDT = None
    duration_seconds: int | None = None
    batch_id: str | None = None
