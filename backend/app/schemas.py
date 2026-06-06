from typing import Literal

from pydantic import BaseModel, Field

RiskDomain = Literal["tbt_sps", "smuggling", "policy", "supply_chain", "biosecurity"]
RiskLevel = Literal["low", "medium", "high", "critical"]
SourceChannel = Literal["official", "rss", "commercial", "social", "deepweb", "media"]


class Metric(BaseModel):
    label: str
    value: str
    delta: str
    trend: Literal["up", "down", "flat"]
    unit: str


class Provenance(BaseModel):
    source_id: str
    source_name: str
    source_url: str
    collected_at: str
    legal_basis: str
    processing_chain: list[str]
    quality_score: float = Field(ge=0, le=1)


class RiskRegion(BaseModel):
    id: str
    country: str
    region: str
    latitude: float
    longitude: float
    risk_score: int = Field(ge=0, le=100)
    domain: RiskDomain
    level: RiskLevel
    drivers: list[str]
    affected_products: list[str]
    provenance: Provenance


class TimelineEvent(BaseModel):
    id: str
    occurred_at: str
    title: str
    country: str
    domain: RiskDomain
    severity: RiskLevel
    summary: str
    related_entities: list[str]


class SourceStatus(BaseModel):
    id: str
    name: str
    channel: SourceChannel
    coverage: str
    languages: list[str]
    status: Literal["healthy", "degraded", "authorization_required", "paused"]
    latency_minutes: int
    last_sync_at: str
    compliance_note: str


class OverviewResponse(BaseModel):
    generated_at: str
    metrics: list[Metric]
    risk_regions: list[RiskRegion]
    timeline: list[TimelineEvent]
    source_status: list[SourceStatus]
    executive_brief: str


class RiskListResponse(BaseModel):
    items: list[RiskRegion]


class GraphNode(BaseModel):
    id: str
    label: str
    kind: Literal["country", "agency", "product", "company", "port", "measure", "event"]
    risk_score: int = Field(ge=0, le=100)
    description: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    confidence: float = Field(ge=0, le=1)


class KnowledgeGraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    inference_paths: list[str]


class QueryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=600)
    focus: Literal["all", "tbt_sps", "smuggling", "policy"] = "all"


class QueryCitation(BaseModel):
    title: str
    source_url: str
    collected_at: str
    quote: str


class QueryResponse(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=1)
    citations: list[QueryCitation]
    recommended_actions: list[str]


class ScenarioRequest(BaseModel):
    region: str = Field(min_length=2, max_length=80)
    product: str = Field(min_length=2, max_length=80)
    assumption: str = Field(min_length=4, max_length=400)
    horizon_months: int = Field(default=12, ge=3, le=18)


class ForecastPoint(BaseModel):
    month: str
    barrier_probability: int = Field(ge=0, le=100)
    smuggling_pressure: int = Field(ge=0, le=100)
    expected_trade_impact: int = Field(ge=-100, le=100)


class ScenarioResponse(BaseModel):
    narrative: str
    assumptions: list[str]
    forecast: list[ForecastPoint]
    playbook: list[str]


class ReportSection(BaseModel):
    title: str
    severity: RiskLevel
    body: str
    evidence_count: int


class ReportResponse(BaseModel):
    title: str
    generated_at: str
    sections: list[ReportSection]
    analyst_checks: list[str]


class CollectionJobRequest(BaseModel):
    source_id: str = Field(min_length=2, max_length=80)
    objective: str = Field(min_length=4, max_length=300)
    authorized_by: str = Field(min_length=2, max_length=80)


class CollectionJobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "rejected"]
    audit_message: str
    next_review_step: str


class AuditRecord(BaseModel):
    id: str
    artifact: str
    source_id: str
    algorithm_version: str
    action: str
    actor: str
    timestamp: str
    decision: str


class AuditResponse(BaseModel):
    records: list[AuditRecord]
