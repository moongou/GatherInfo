# 全球跨境贸易监管与风险情报智能感知平台

这是一个可运行的全栈高保真原型，覆盖跨境贸易监管情报平台的核心闭环：多源感知、风险融合、知识图谱、智能问答、沙盘推演、自动简报与全链路审计。

## 已落地能力

- **指挥驾驶舱**：全球风险热力点、TBT/SPS 指标、走私异常信号、事件时间轴、信源健康度。
- **情报工作台**：RaQ 风格自然语言问答，返回结构化答案、置信度、引用来源与下一步建议。
- **风险知识图谱**：以国家、机构、商品、企业、港口、措施、事件为节点，展示风险传导路径。
- **沙盘推演**：围绕地区、商品与政策假设生成 6-12 个月影响曲线和应对动作。
- **自动简报**：生成每日情报简报结构，包含战略态势、技贸措施、执法线索和模型解释。
- **合规与审计**：每条样例情报携带来源、口径、采集时间、处理链路和授权状态。

## 安全边界

本原型不实现验证码绕过、未授权暗网采集、规避访问控制或对第三方平台条款的绕行。相关模块以合规门禁、授权字段、审计流水和隔离接口形式呈现，便于后续在合法授权环境中接入真实探针。

## 技术栈

- 后端：FastAPI + Pydantic 服务层架构
- 前端：React + TypeScript + Vite + ECharts + Lucide Icons
- 数据：合成演示数据，所有指标与来源均有 provenance 字段，便于替换为真实湖仓、图数据库和全文索引

## 快速启动

```bash
cd /Users/m4max/VS-CODE-PROJECT/GatherInfo

/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt

npm --prefix frontend install
npm run dev
```

访问前端：`http://127.0.0.1:5178`

后端 API：`http://127.0.0.1:8108/docs`

## 验证命令

```bash
npm run typecheck
npm run build
npm run test:backend
```

## 真实生产化扩展路径

1. 将 `backend/app/data.py` 的合成数据替换为 Kafka/Flink/Airbyte 摄入后的湖仓查询。
2. 将 `IntelligenceService` 拆分为采集、翻译、抽取、图谱、检索、报告等独立微服务。
3. 用 Neo4j、Elasticsearch/OpenSearch、ClickHouse、MinIO 接管图谱、全文、分析与原文存储。
4. 将 `/api/intel/query` 接入私有化 LLM 与向量检索，并保留引用来源与推理路径。
5. 对深网/暗网与商业数据库接入启用审批、隔离、审计、脱敏和只读导出策略。

## 全球信息采集子系统 (v0.2)

### 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                    Collection Engine                          │
│  (编排层: 调度、去重、持久化、统计)                              │
├──────────┬──────────┬──────────┬──────────┬───────────────────┤
│  官方API  │   RSS    │ 网页抓取   │   搜索    │   商业API         │
│ (WTO,EU, │ (Feeds)  │ (BS4)    │ (Tavily)  │  (授权接入)         │
│  中国海关, │          │           │           │                    │
│  商务部)  │          │           │           │                    │
└──────────┴──────────┴──────────┴──────────┴───────────────────┘
         │          │          │          │
         └──────────┴──────────┴──────────┘
                    │
         ┌──────────▼──────────┐
         │    SQLite / PG       │
         │  (来源、主题、条目、HS) │
         └─────────────────────┘
```

### 核心能力

| 能力 | 说明 |
|------|------|
| **可配置信息源** | 支持 official / rss / web_scrape / api_search / commercial / social / deepweb / manual 等8种渠道 |
| **主题采集** | 设定主题（如 "中国HS编码"、"TBT/SPS通报"），关联关键词和信息源，一次性跨源并行采集 |
| **周期调度** | 标准5字段Cron表达式，按信息源或主题设置定时采集任务 |
| **去重存储** | SHA-256内容哈希，按 source+title+url 生成的确定性ID去重 |
| **HS Code专表** | 独立的 `hs_codes` 表，记录HS编码、中英文描述、税率、监管机构等 |
| **合规审计** | 每次采集Run记录 status、耗时、错误日志；来源配置记录 legal_basis / compliance_note |

### 已配置的中国和国际数据源

| 信息源ID | 名称 | 渠道 | 聚焦 |
|----------|------|------|------|
| `cn-customs` | 中国海关总署 (GACC) | web_scrape | 公告、政策、HS编码 |
| `cn-mofcom` | 中国商务部 (MOFCOM) | web_scrape | 贸易政策、反倾销、出口管制 |
| `cn-aqsiq` | 海关商品检验 (AQSIR) | web_scrape | TBT/SPS、检验检疫标准 |
| `wto-eping` | WTO ePing TBT/SPS | official | TBT/SPS通报 |
| `eu-eurlex` | EU EUR-Lex | official | 欧盟法规、指令 |
| `un-comtrade` | UN Comtrade | official | 国际贸易统计数据 |
| `tavily-global-trade` | Tavily全球搜索 | api_search | 中文+英文网络搜索 |
| `wto-rss` | WTO官方新闻 | rss | RSS订阅 |
| `hs-codes-CN` | 中国HS编码全量 | web_scrape | HS编码详细页面 |

### 预置采集主题

| 主题ID | 名称 | 调度 | 关键词数 |
|--------|------|------|----------|
| `hs-codes-cn` | 中国HS编码全量信息 | 周日 03:00 | 6 |
| `tbt-sps-china` | TBT/SPS技术性贸易措施 | 每日 08:00 | 10 |
| `trade-barriers-cn` | 贸易壁垒与反倾销动态 | 工作日 09:00 | 8 |
| `customs-clearance` | 海关清关与商品归类 | 工作日 10:00 | 7 |

### 快速开始

```bash
# 设置环境变量
export TAVILY_API_KEY=tvly-dev-xxx
export COMTRADE_API_KEY=xxx  # 可选

# 启动服务
cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --port 8108

# 初始化默认信息源和主题
curl -X POST http://127.0.0.1:8108/api/collection/seed-defaults

# 手动触发采集
curl -X POST http://127.0.0.1:8108/api/collection/run \
  -H "Content-Type: application/json" \
  -d '{"topic_id": "hs-codes-cn"}'

# 查看结果
curl http://127.0.0.1:8108/api/collection/items

# 搜索HS编码
curl -X POST http://127.0.0.1:8108/api/collection/hs-codes/search \
  -H "Content-Type: application/json" \
  -d '{"query": "锂电池"}'

# 查看采集统计
curl http://127.0.0.1:8108/api/collection/stats
```

### API 端点一览

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/collection/sources` | 列出信息源 |
| POST | `/api/collection/sources` | 注册信息源 |
| POST | `/api/collection/sources/{id}/validate` | 验证连接 |
| GET | `/api/collection/topics` | 列出主题 |
| POST | `/api/collection/topics` | 创建主题 |
| GET | `/api/collection/schedules` | 列出调度 |
| POST | `/api/collection/schedules` | 创建调度 |
| POST | `/api/collection/run` | 手动触发采集 |
| GET | `/api/collection/items` | 查询采集条目 |
| GET | `/api/collection/hs-codes` | 查询HS编码 |
| POST | `/api/collection/hs-codes/search` | HS编码搜索 |
| POST | `/api/collection/hs-codes/collect` | 触发HS采集 |
| GET | `/api/collection/connectors` | 列出可用连接器 |
| GET | `/api/collection/stats` | 统计信息 |

### 新增文件

backend/app/
├── database.py              # SQLAlchemy引擎和会话管理
├── models.py                # ORM模型: SourceConfig, Topic, ScheduleConfig, CollectedItem, HSCode
├── collection_schemas.py    # Pydantic schema for management API
├── collection_routes.py     # REST API 路由
├── engine.py                # 采集引擎 (编排层)
├── scheduler.py             # APScheduler 集成
└── connectors/
    ├── __init__.py
    ├── base.py              # BaseCollector + ConnectorRegistry
    ├── tavily_search.py     # Tavily Web搜索连接器
    ├── rss_collector.py     # RSS/Atom feed连接器
    ├── web_scrape.py        # 网页抓取 (BS4) 连接器
    └── official_api.py      # 官方API连接器 (WTO, EU, 海关, 商务部)
