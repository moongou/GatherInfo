# 架构说明

## 分层映射

| 方案层 | 原型落地 | 生产扩展 |
| --- | --- | --- |
| 感知采集层 | `/api/sources`、授权门禁、合规说明 | Scrapy/Playwright、RSS、授权商业 API、隔离探针 |
| 数据处理层 | `data.py` 合成数据、provenance、质量分 | Kafka/Flink、dbt、Airbyte、数据血缘与 MDM |
| 智能分析层 | `IntelligenceService` 风险融合、问答、推演 | 私有 LLM、向量库、Neo4j、图学习、时序模型 |
| 业务服务层 | FastAPI REST endpoints | 微服务拆分、消息总线、任务调度、权限中台 |
| 应用交互层 | React 指挥驾驶舱 | 多角色门户、移动端、WebSocket 实时流、地图引擎 |

## 合规设计

- 公开源与授权源分开建模。
- 深网/暗网入口默认拒绝执行, 必须提供授权与隔离沙箱编号。
- 商业数据只输出派生指标和脱敏线索。
- 每条风险对象携带 `provenance` 与处理链路。
- 审计 API 暴露算法版本、动作、主体、时间与决策。

## 后续服务拆分建议

1. `collector-service`: 信源配置、调度、抓取、原文存储。
2. `fusion-service`: 清洗、去重、翻译、NER/RE/EE、质量评分。
3. `graph-service`: Neo4j 写入、路径推理、GraphQL 查询。
4. `rag-service`: 文档检索、引用生成、LLM 答案合成。
5. `forecast-service`: 风险预测、贸易影响测算、沙盘推演。
6. `report-service`: 日报、专题报告、签发工作流。
