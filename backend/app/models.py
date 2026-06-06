"""
Data models for GatherInfo — a general-purpose global information monitor.

Architecture:
    SourceConfig  ──< CollectionRun  ──< CollectedItem  >── Tag
    Topic ──< CollectionRun

Every collected item is tagged, categorized, and linked to its source and topic.
Topics drive collection: each topic has keywords, sources, and optional schedules.
"""
import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Enum as SAEnum,
    Integer,
    Float,
    JSON,
    Boolean,
    ForeignKey,
    Table,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────────────────

class SourceChannel(str, enum.Enum):
    OFFICIAL = "official"
    RSS = "rss"
    COMMERCIAL = "commercial"
    WEB_SCRAPE = "web_scrape"
    API_SEARCH = "api_search"
    JSON_API = "json_api"
    SOCIAL = "social"
    DEEP_WEB = "deepweb"
    MANUAL = "manual"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ItemStatus(str, enum.Enum):
    RAW = "raw"
    TAGGED = "tagged"
    ENRICHED = "enriched"
    ARCHIVED = "archived"
    DISCARDED = "discarded"


# ── Item ↔ Tag (many-to-many) ────────────────────────────────────────────────

item_tags = Table(
    "item_tags",
    Base.metadata,
    Column("item_id", String(120), ForeignKey("collected_items.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(80), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    """
    标签表 — 系统中最核心的结构化维度。

    每个标签有:
      - namespace: 标签命名空间 (e.g. "country", "product", "event_type", "regulation")
      - value: 标签值 (e.g. "CN", "锂电池", "anti_dumping")
      - color / icon: 可选可视化标记

    标签通过 item_tags 多对多关联到 CollectedItem。
    """
    __tablename__ = "tags"

    id = Column(String(80), primary_key=True)          # e.g. "country:CN", "product:battery"
    namespace = Column(String(50), nullable=False, index=True)
    value = Column(String(200), nullable=False)
    label = Column(String(200), nullable=True)          # 显示用标签
    color = Column(String(20), nullable=True)
    icon = Column(String(40), nullable=True)
    extra = Column(JSON, nullable=True)

    # Stats
    item_count = Column(Integer, default=0)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Backref
    items = relationship("CollectedItem", secondary=item_tags, back_populates="tags", lazy="selectin")

    def __repr__(self):
        return f"<Tag {self.id}>"


# ── Source Configuration ─────────────────────────────────────────────────────

class SourceConfig(Base):
    """
    可配置的信息源。每个信息源对应一种采集渠道和配置。

    支持渠道：
      - official: 官方API (WTO ePing, EUR-Lex, 中国海关, 商务部)
      - rss: RSS/Atom订阅
      - web_scrape: 结构化网页抓取
      - api_search: Web搜索API (Tavily)
      - commercial: 商业数据API
      - social: 社交媒体
      - deepweb: 深网/暗网 (需授权)
      - manual: 手动录入
    """
    __tablename__ = "source_configs"

    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    channel = Column(SAEnum(SourceChannel), nullable=False)
    is_active = Column(Boolean, default=True)

    # Connection
    base_url = Column(String(800), nullable=True)
    api_endpoint = Column(String(800), nullable=True)
    homepage_url = Column(String(800), nullable=True)    # 信息源官网主页 (方便购买/订阅服务)
    api_key_ref = Column(String(200), nullable=True)   # env var name
    api_key = Column(String(500), nullable=True)         # direct API key (stored in DB)
    auth_config = Column(JSON, nullable=True)            # custom headers, selectors, etc.

    # Behavior
    rate_limit_rps = Column(Float, default=1.0)
    max_retries = Column(Integer, default=3)
    timeout_seconds = Column(Integer, default=30)
    max_items_per_run = Column(Integer, default=100)

    # Content targeting (default keywords; overridden by topic-level keywords)
    default_keywords = Column(JSON, nullable=True)
    default_categories = Column(JSON, nullable=True)
    languages = Column(JSON, nullable=True)
    country_focus = Column(JSON, nullable=True)

    # Compliance
    legal_basis = Column(Text, nullable=True)
    compliance_note = Column(Text, nullable=True)

    # State
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    items_collected = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    runs = relationship("CollectionRun", back_populates="source", cascade="all, delete-orphan")
    items = relationship("CollectedItem", back_populates="source", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SourceConfig id={self.id} channel={self.channel}>"


# ── Topic ────────────────────────────────────────────────────────────────────

class Topic(Base):
    """
    采集主题 — 系统的核心驱动概念。

    每个主题定义了:
      - 搜索关键词 (多语言)
      - 关联的信息源 (空=全部活跃源)
      - 可选周期调度
      - 自动打标签规则

    用户创建主题 → 系统按主题跨源采集 → 信息打标签入库 → 统计分析。
    """
    __tablename__ = "topics"

    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Search configuration
    keywords = Column(JSON, nullable=False, default=list)
    synonyms = Column(JSON, nullable=True, default=list)
    exclude_keywords = Column(JSON, nullable=True, default=list)

    # Enhanced topic fields (v0.3)
    keyword_tags = Column(JSON, nullable=True)
    description_prompt = Column(Text, nullable=True)

    # Scope
    categories = Column(JSON, nullable=True)               # 范畴分类
    focus_countries = Column(JSON, nullable=True)
    focus_languages = Column(JSON, nullable=True)
    source_ids = Column(JSON, nullable=True)                # 限定信息源

    # Targeted crawling: specific URLs to scrape for this topic
    target_urls = Column(JSON, nullable=True)               # e.g. ["https://example.com/page1", ...]

    # Auto-tagging: rules to apply tags based on content matches
    # e.g. [{"keyword": "锂电池", "tag": "product:battery"}, {"keyword": "反倾销", "tag": "event:anti_dumping"}]
    auto_tag_rules = Column(JSON, nullable=True)

    # Schedule
    schedule_cron = Column(String(100), nullable=True)
    is_scheduled = Column(Boolean, default=False)
    next_run_at = Column(DateTime(timezone=True), nullable=True)

    # Collection time window: filter collected items by their published_at within
    # the last N days (relative to each collection run). Default 7 days.
    collect_window_days = Column(Integer, default=7)

    # Auto-report: generate a report automatically after each collection run
    auto_report = Column(Boolean, default=False)
    auto_report_model_id = Column(String(80), nullable=True)
    last_collection_run_id = Column(String(80), nullable=True)

    # State
    is_active = Column(Boolean, default=True)
    total_items_collected = Column(Integer, default=0)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    runs = relationship("CollectionRun", back_populates="topic")

    def __repr__(self):
        return f"<Topic id={self.id} name={self.name}>"


# ── Collection Run ───────────────────────────────────────────────────────────

class CollectionRun(Base):
    """每次采集的执行记录。"""
    __tablename__ = "collection_runs"

    id = Column(String(80), primary_key=True)
    source_id = Column(String(80), ForeignKey("source_configs.id"), nullable=False)
    topic_id = Column(String(80), ForeignKey("topics.id"), nullable=True)
    job_id = Column(String(80), nullable=True, index=True)

    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING)
    keywords_used = Column(JSON, nullable=True)

    # Metrics
    items_found = Column(Integer, default=0)
    items_new = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Information time window applied during this run (by item published_at)
    window_start = Column(DateTime(timezone=True), nullable=True)
    window_end = Column(DateTime(timezone=True), nullable=True)

    # Diagnostics
    error_log = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    source = relationship("SourceConfig", back_populates="runs")
    topic = relationship("Topic", back_populates="runs")

    def __repr__(self):
        return f"<CollectionRun id={self.id} source={self.source_id} status={self.status}>"


# ── Collected Item ───────────────────────────────────────────────────────────

class CollectedItem(Base):
    """
    采集到的单条信息 — 系统的核心数据实体。

    每条信息有:
      - 来源溯源 (source, run, URL)
      - 内容 (title, content, summary)
      - 语言
      - 发布时间
      - 标签 (多对多 Tag)
      - 结构化维度 (categories, entities, hs_codes if applicable)
      - 质量评分
      - 状态流转 (raw → tagged → enriched → archived)
    """
    __tablename__ = "collected_items"

    id = Column(String(120), primary_key=True)
    source_id = Column(String(80), ForeignKey("source_configs.id"), nullable=False)
    run_id = Column(String(80), nullable=True, index=True)
    topic_id = Column(String(80), nullable=True, index=True)

    # Content
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True, index=True)
    summary = Column(Text, nullable=True)
    url = Column(String(2000), nullable=True)
    language = Column(String(10), nullable=True)

    # Classification (high-level category buckets)
    category = Column(String(100), nullable=True)

    # Entities extracted (products, companies, countries, people, events, etc.)
    entities = Column(JSON, nullable=True)

    # Quality
    status = Column(SAEnum(ItemStatus), default=ItemStatus.RAW)
    quality_score = Column(Float, default=0.0)
    relevance_score = Column(Float, default=0.0)

    # Provenance
    published_at = Column(DateTime(timezone=True), nullable=True)
    collected_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    raw_metadata = Column(JSON, nullable=True)

    # Compliance
    authorization_level = Column(String(20), default="public")

    # Relationships
    source = relationship("SourceConfig", back_populates="items")
    tags = relationship("Tag", secondary=item_tags, back_populates="items", lazy="selectin")

    def tags_from_metadata(self) -> list[str]:
        """Extract tag IDs from raw_metadata harvested by connectors."""
        tags = []
        md = self.raw_metadata or {}
        # Direct suggested_tags
        for t in (md.get("suggested_tags") or []):
            tags.append(t)
        # Tavily: category hints
        if md.get("engine") == "tavily":
            # Infer topics from title/content
            pass
        return tags

    def __repr__(self):
        return f"<CollectedItem id={self.id} title={self.title[:60] if self.title else ''}>"


# ── Schedule Config ──────────────────────────────────────────────────────────

class ScheduleConfig(Base):
    """
    全局调度配置。可绑定多个 topic_ids 和 source_ids 按 cron 表达式周期执行。
    """
    __tablename__ = "schedule_configs"

    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    source_ids = Column(JSON, nullable=True)
    topic_ids = Column(JSON, nullable=True)
    keywords = Column(JSON, nullable=True)

    cron_expression = Column(String(100), nullable=False)
    timezone = Column(String(50), default="Asia/Shanghai")
    is_active = Column(Boolean, default=True)

    max_items_per_run = Column(Integer, default=100)

    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    run_count = Column(Integer, default=0)
    last_status = Column(SAEnum(JobStatus), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<ScheduleConfig id={self.id} cron={self.cron_expression}>"


# ═══════════════════════════════════════════════════════════════════════════════
# Model Configuration (v0.3)
# ═══════════════════════════════════════════════════════════════════════════════

class ModelConfig(Base):
    """
    AI model configuration for text processing (report generation, summarization).
    Supports local models (Ollama, LM Studio) and remote APIs (OpenAI-compatible).

    provider values: ollama | openai | lmstudio | cc_switch | custom
        - cc_switch is treated as OpenAI-compatible (/v1/chat/completions).
    """
    __tablename__ = "model_configs"

    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    provider = Column(String(50), nullable=False)  # ollama | openai | lmstudio | cc_switch | custom
    base_url = Column(String(500), nullable=True)
    api_key = Column(String(500), nullable=True)
    model_name = Column(String(200), nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)
    top_p = Column(Float, default=0.9)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<ModelConfig id={self.id} provider={self.provider} model={self.model_name}>"


# ═══════════════════════════════════════════════════════════════════════════════
# Report (v0.3)
# ═══════════════════════════════════════════════════════════════════════════════

class Report(Base):
    """
    Auto-generated report from collected items under a topic.
    Uses a configured LLM to synthesize collected information into a structured report.
    """
    __tablename__ = "reports"

    id = Column(String(80), primary_key=True)
    topic_id = Column(String(80), ForeignKey("topics.id"), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    model_id = Column(String(80), nullable=True)
    tokens_used = Column(Integer, default=0)
    item_count = Column(Integer, default=0)
    item_ids = Column(JSON, nullable=True)
    error_log = Column(Text, nullable=True)

    # Scope: optionally tie a report to a specific collection run / date window
    collection_run_id = Column(String(80), nullable=True)
    date_range_start = Column(DateTime(timezone=True), nullable=True)
    date_range_end = Column(DateTime(timezone=True), nullable=True)

    # Exported files: {"md": "/abs/path.md", "html": ..., "docx": ..., "pdf": ...}
    output_files = Column(JSON, nullable=True)
    output_dir = Column(String(800), nullable=True)

    generated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    def __repr__(self):
        return f"<Report id={self.id} topic={self.topic_id} status={self.status}>"


# ═══════════════════════════════════════════════════════════════════════════════
# Search Tool Config (v0.3)
# ═══════════════════════════════════════════════════════════════════════════════

class SearchToolConfig(Base):
    """
    Configurable search/collection tool definitions.
    Allows users to configure API keys and parameters for Tavily, RSS, etc.
    """
    __tablename__ = "search_tool_configs"

    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    tool_type = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    config_json = Column(JSON, nullable=True)
    api_key_ref = Column(String(200), nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<SearchToolConfig id={self.id} type={self.tool_type}>"


# ═══════════════════════════════════════════════════════════════════════════════
# System Config (v0.4) — single-row global settings
# ═══════════════════════════════════════════════════════════════════════════════

class SystemConfig(Base):
    """
    全局系统配置 (单行表, id 固定为 "global")。
    主要用于报告生成的标题格式、文件存放目录与导出格式。
    """
    __tablename__ = "system_config"

    id = Column(String(20), primary_key=True, default="global")

    # Report generation settings
    report_title_format = Column(String(300), default="{topic}_情报报告_{date}")
    report_output_dir = Column(String(800), nullable=True)        # absolute root dir; None => <data>/reports
    report_dir_pattern = Column(String(100), default="%Y-%m-%d")  # date-based subfolder pattern
    report_formats = Column(JSON, default=lambda: ["md", "html", "docx", "pdf"])

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<SystemConfig id={self.id}>"
