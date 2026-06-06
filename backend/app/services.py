from datetime import datetime, timezone
from uuid import uuid4

from app.data import (
    AUDIT_RECORDS,
    GENERATED_AT,
    GRAPH_EDGES,
    GRAPH_NODES,
    METRICS,
    REPORT_SECTIONS,
    RISK_REGIONS,
    SOURCE_STATUS,
    TIMELINE,
)
from app.schemas import (
    AuditResponse,
    CollectionJobRequest,
    CollectionJobResponse,
    ForecastPoint,
    KnowledgeGraphResponse,
    OverviewResponse,
    QueryCitation,
    QueryRequest,
    QueryResponse,
    ReportResponse,
    RiskDomain,
    RiskListResponse,
    ScenarioRequest,
    ScenarioResponse,
    SourceStatus,
)


class IntelligenceService:
    def get_overview(self) -> OverviewResponse:
        return OverviewResponse(
            generated_at=GENERATED_AT,
            metrics=METRICS,
            risk_regions=RISK_REGIONS,
            timeline=TIMELINE,
            source_status=SOURCE_STATUS,
            executive_brief=(
                "欧盟电池合规、东盟农残限量与东非异常转运构成今日三条主风险轴。"
                "建议将锂电池、冷链食品和高税差消费品列入本周联动核查清单。"
            ),
        )

    def list_risks(self, domain: RiskDomain | None = None, minimum_score: int = 0) -> RiskListResponse:
        filtered = [
            item
            for item in RISK_REGIONS
            if item.risk_score >= minimum_score and (domain is None or item.domain == domain)
        ]
        return RiskListResponse(items=filtered)

    def list_sources(self) -> list[SourceStatus]:
        return SOURCE_STATUS

    def get_knowledge_graph(self) -> KnowledgeGraphResponse:
        return KnowledgeGraphResponse(
            nodes=GRAPH_NODES,
            edges=GRAPH_EDGES,
            inference_paths=[
                "欧盟委员会 -> 碳足迹申报 -> 锂电池 -> 高货值出口企业合规成本上升",
                "蒙巴萨港 -> 异常转运事件簇 -> 高税差商品 -> 需要舱单与价格申报交叉核查",
                "东盟重点成员 -> 水产品抽检加密 -> 冷链追溯缺口 -> 退运概率抬升",
            ],
        )

    def answer_query(self, request: QueryRequest) -> QueryResponse:
        normalized_query = request.query.lower()
        battery_focus = any(token in normalized_query for token in ["电池", "battery", "碳足迹", "欧盟"])
        smuggling_focus = any(token in normalized_query for token in ["走私", "航线", "口岸", "线索", "东非"])

        if smuggling_focus or request.focus == "smuggling":
            return QueryResponse(
                answer=(
                    "近 7 天走私风险主要集中在东非转运走廊。AIS 派生指标显示异常停靠、"
                    "低报价格聚类与高风险货代复用同时出现, 但当前仍属于脱敏线索, "
                    "需要与舱单、税则价格库和历史查发案例进一步交叉验证。"
                ),
                confidence=0.78,
                citations=[
                    QueryCitation(
                        title="授权 AIS 异常流派生摘要",
                        source_url="contract://licensed-ais-provider/anomaly-feed",
                        collected_at="2026-06-01T08:52:00+08:00",
                        quote="部分箱量绕行非惯常港口, 与历史查发案例存在路线重合。",
                    )
                ],
                recommended_actions=[
                    "对高风险货代与异常转运港口建立 14 天观察名单。",
                    "用价格申报、舱单和历史查发口径进行三表交叉核验。",
                    "保持线索脱敏流转, 未经授权不得回溯个人或私密通信标识。",
                ],
            )

        if battery_focus or request.focus == "tbt_sps":
            return QueryResponse(
                answer=(
                    "欧盟电池法规配套解释出现收紧信号, 重点落在碳足迹申报、回收含量、"
                    "供应链尽调和合格评定证明。对锂电池、新能源汽车零部件和储能系统出口企业, "
                    "短期风险是证明材料口径不一致导致清关延迟, 中期风险是供应商数据链缺口。"
                ),
                confidence=0.86,
                citations=[
                    QueryCitation(
                        title="欧盟官方公报与配套问答",
                        source_url="https://eur-lex.europa.eu/oj/direct-access.html",
                        collected_at="2026-06-01T08:40:00+08:00",
                        quote="碳足迹、回收含量与供应链尽调字段出现口径收紧迹象。",
                    ),
                    QueryCitation(
                        title="WTO ePing SPS/TBT notification feed",
                        source_url="https://eping.wto.org/",
                        collected_at="2026-06-01T08:55:00+08:00",
                        quote="通报模式显示低碳与可追溯要求持续扩散。",
                    ),
                ],
                recommended_actions=[
                    "建立锂电池出口企业碳足迹证明材料差距清单。",
                    "联动标准、商协会和重点企业准备 WTO/TBT 评议意见。",
                    "将供应链尽调字段纳入下一轮企业合规问卷。",
                ],
            )

        return QueryResponse(
            answer=(
                "当前综合态势呈现三条风险轴: 技贸措施向低碳与生物安全集中, "
                "执法线索向异常转运和价格瞒报聚集, 政策摩擦向原产地与供应链审查延伸。"
            ),
            confidence=0.81,
            citations=[
                QueryCitation(
                    title="今日跨境贸易监管风险融合快照",
                    source_url="internal://fusion-foundry/daily-snapshot/2026-06-01",
                    collected_at=GENERATED_AT,
                    quote="欧盟电池合规、东盟农残限量与东非异常转运构成今日三条主风险轴。",
                )
            ],
            recommended_actions=[
                "先处理 critical 与 high 风险事项, 将 medium 线索纳入连续观察。",
                "所有对外简报保留来源引用、算法版本和人工复核记录。",
            ],
        )

    def simulate_scenario(self, request: ScenarioRequest) -> ScenarioResponse:
        months = [f"M+{index}" for index in range(1, request.horizon_months + 1)]
        product_pressure = 9 if any(token in request.product for token in ["电池", "光伏", "水产"]) else 5
        region_pressure = 8 if request.region in ["欧盟", "北美", "东盟"] else 5
        assumption_pressure = 10 if any(token in request.assumption for token in ["破裂", "制裁", "升级", "冲突"]) else 4

        forecast = [
            ForecastPoint(
                month=month,
                barrier_probability=min(96, 36 + index * 3 + region_pressure + product_pressure),
                smuggling_pressure=min(92, 28 + index * 2 + assumption_pressure),
                expected_trade_impact=max(-48, -8 - index * 2 - product_pressure),
            )
            for index, month in enumerate(months)
        ]

        return ScenarioResponse(
            narrative=(
                f"在'{request.assumption}'假设下, {request.region} 对 {request.product} 的监管强度"
                "预计呈阶梯式上升。前 3 个月以审查口径变化为主, 6 个月后可能传导至"
                "企业成本、通关时效和替代转运路径。"
            ),
            assumptions=[
                "通报密度、政治经济事件与历史相似案例共同驱动概率曲线。",
                "贸易影响为方向性指数, 未替代正式经济损失测算。",
                "模型输出需要分析师结合最新政策文本复核。",
            ],
            forecast=forecast,
            playbook=[
                "建立重点企业材料补正与标准差距台账。",
                "准备双边磋商、WTO/TBT 或 SPS 委员会评议材料。",
                "同步监测替代口岸与第三国转口异常, 防止监管套利。",
            ],
        )

    def get_report(self) -> ReportResponse:
        return ReportResponse(
            title="全球跨境贸易监管情报日报",
            generated_at=GENERATED_AT,
            sections=REPORT_SECTIONS,
            analyst_checks=[
                "核对 critical 风险来源 URL 与算法版本。",
                "对经济影响测算使用最新出口结构数据复算。",
                "涉及行动线索的内容仅在授权范围内分发。",
            ],
        )

    def request_collection_job(self, request: CollectionJobRequest) -> CollectionJobResponse:
        restricted_source = request.source_id == "restricted-deepweb-gate"
        if restricted_source:
            return CollectionJobResponse(
                job_id=f"job-{uuid4().hex[:8]}",
                status="rejected",
                audit_message="深网/暗网源默认拒绝执行, 需补齐书面授权、隔离沙箱编号与审批记录。",
                next_review_step="提交法律授权编号、任务范围、最小化采集清单和脱敏策略。",
            )

        return CollectionJobResponse(
            job_id=f"job-{uuid4().hex[:8]}",
            status="queued",
            audit_message=f"任务由 {request.authorized_by} 提交, 已记录目标与来源口径。",
            next_review_step="等待调度器执行公开或授权源增量同步。",
        )

    def get_audit_records(self) -> AuditResponse:
        return AuditResponse(records=AUDIT_RECORDS)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
