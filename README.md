# GatherInfo — 全球贸易情报采集监控平台

<p align="center">
  <strong>主题驱动 · 多源采集 · 智能报告 · 标签化入库</strong>
</p>

GatherInfo 是一个面向跨境贸易情报分析师与海关合规人员的全栈信息采集监控平台。支持 RSS、网页抓取、官方 API、搜索引擎、JSON API 等 9 种渠道，覆盖全球 83 个免费信息源，内置全文搜索、智能报告生成、周期调度与通知系统。

---

## 功能概览

### 核心闭环

```
定义主题(关键词+信源) → 周期/手动采集 → 去重入库 → 自动打标签 → 智能报告 → 导出分发
```

| 模块 | 能力 |
|------|------|
| **仪表盘** | 统计概览、采集趋势图、分类分布饼图、信源采集量柱状图、热门标签云、快速采集卡片 |
| **信息源管理** | 83 个预配置免费源（RSS/官方/网页）+ 9 种渠道类型，支持连接验证、搜索、分类筛选 |
| **主题管理** | CRUD + 关键词模板推荐 + 多选信源绑定 + Cron 周期调度 + 自动标签规则 + 自动报告 |
| **条目浏览** | 全文检索(FTS5)、标签/信源/语言/分类过滤、分页浏览、批量选择删除、CSV/JSON/XLSX 导出 |
| **标签系统** | 命名空间管理、M:N 关联、标签合并、统计分析 |
| **智能报告** | 调用 LLM 生成分析报告，支持 Markdown/HTML/DOCX/PDF 导出，批量生成 |
| **采集历史** | 批次视图、活跃任务实时追踪、展开查看详情、错误日志 |
| **周期调度** | 全局调度 + 主题级别 Cron，灵活绑定信源和主题 |
| **通知系统** | Webhook / Email 通知，fire-and-forget 模式 |
| **配置管理** | 系统设置、模型配置、配置导出/导入 |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | React 18 + TypeScript + Vite (Rolldown) + ECharts + Lucide Icons |
| **后端** | Python FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| **数据库** | SQLite (WAL 模式)，内置 FTS5 全文搜索 |
| **采集** | httpx (异步 HTTP) + BeautifulSoup4 (网页解析) |
| **调度** | APScheduler (Cron 表达式) |
| **AI** | 多模型支持 (OpenAI / Ollama / 自定义)，LLM 客户端可扩展 |
| **报告** | WeasyPrint (PDF) / Pandoc (DOCX)，缺失时不阻塞 |
| **容器化** | Dockerfile.backend + Dockerfile.frontend + docker-compose.yml |

---

## 快速启动

### 环境要求

- Python 3.12+
- Node.js 22+
- npm 10+

### 一键启动

```bash
cd GatherInfo

# 首次运行：安装依赖
npm --prefix frontend install
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt

# 启动前后端开发服务器
npm run dev
```

- 前端: http://localhost:5178
- 后端 API: http://localhost:8109
- API 文档: http://localhost:8109/docs
- Dev Dashboard: http://localhost:9999

### Docker 部署

```bash
docker-compose up
```

---

## 信息源管理

### 渠道类型

| 渠道 | 标识 | 说明 | 是否需要 API Key |
|------|------|------|:---:|
| 官方 API | `official` | WTO ePing, EU EUR-Lex 等 | 否 |
| RSS/Atom | `rss` | RSS 订阅源采集 | 否 |
| 网页抓取 | `web_scrape` | CSS 选择器 + BS4 解析 | 否 |
| Web 搜索 | `api_search` | Tavily / Baidu / Bing | **是** |
| JSON API | `json_api` | NewsAPI, UN Comtrade 等 | **是** |
| 商业数据库 | `commercial` | 授权商业数据 | **是** |
| 社交媒体 | `social` | 社媒监控 | **是** |
| 深网 | `deepweb` | 深网数据源 | **是** |
| 手动录入 | `manual` | 人工添加 | 否 |

### 源配置状态

当前系统预置 **92 个信息源**：
- ✅ **83 个已配置**，可直接使用（RSS / 网页抓取 / 官方 API）
- ⏳ **9 个待配置**，需填入 API Key 后激活

### 已覆盖的全球免费信源（部分）

**国际组织与协定：** WTO、UNCTAD、OECD、IMF、World Bank、IISD、ADB、ASEAN、PIIE、CSIS、Global Trade Alert、EAEU

**主要经济体海关与贸易机构：**
US (CBP/USTR/USITC/BIS/OFAC) · EU (Trade/Customs/EUR-Lex) · UK · Canada · Australia · New Zealand · Singapore · 香港 · 日本 METI · Korea

**新兴市场海关：** India DGFT · Brazil MDIC · South Africa SARS · Turkey · Vietnam · Indonesia · Mexico · Thailand · Philippines · Malaysia · Chile · Argentina · Nigeria · Kenya · Egypt · Colombia · Peru · Pakistan · Bangladesh · Sri Lanka

**中国监管：** 海关总署 · 商务部 · 自由贸易区服务网

---

## 项目架构

```
GatherInfo/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 应用工厂 + CORS + 限流
│   │   ├── database.py             # SQLAlchemy 引擎/会话/备份
│   │   ├── models.py               # ORM 模型导出中心
│   │   ├── engine.py               # 采集引擎编排
│   │   ├── scheduler.py            # APScheduler 调度集成
│   │   ├── report_engine.py        # 智能报告生成
│   │   ├── llm_client.py           # LLM 调用客户端
│   │   ├── fts_search.py           # SQLite FTS5 全文搜索
│   │   ├── stats_routes.py         # 仪表盘统计 API
│   │   ├── notification_models.py  # 通知模型与发送
│   │   ├── routes/                 # 15 个路由模块
│   │   │   ├── topics.py           # 主题 CRUD + 采集
│   │   │   ├── sources.py          # 信息源 CRUD
│   │   │   ├── items.py            # 条目查询/搜索/导出
│   │   │   ├── tags.py             # 标签管理
│   │   │   ├── reports.py          # 报告生成/导出
│   │   │   ├── models.py           # 模型配置
│   │   │   ├── schedules.py        # 调度管理
│   │   │   ├── settings.py         # 系统配置
│   │   │   ├── notifications.py    # 通知配置
│   │   │   ├── export_routes.py    # 数据导出
│   │   │   ├── search_tools.py     # 搜索工具
│   │   │   ├── seed.py             # 种子数据 API
│   │   │   └── _seed_sources.py    # 92 个预置信息源
│   │   ├── services/               # 业务逻辑层
│   │   │   ├── source_service.py
│   │   │   ├── topic_service.py
│   │   │   ├── item_service.py
│   │   │   ├── tag_service.py
│   │   │   └── report_service.py
│   │   └── connectors/             # 连接器系统
│   │       ├── base.py             # 抽象基类 + 注册表
│   │       ├── rss_collector.py    # RSS/Atom
│   │       ├── web_scrape.py       # 网页抓取
│   │       ├── tavily_search.py    # Tavily 搜索
│   │       ├── search_engines.py   # 搜索分发器
│   │       ├── official_api.py     # 官方 API
│   │       └── json_api.py         # JSON API 直连
│   └── tests/                      # 258 个测试用例 (17 文件)
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # 导航框架 + 视图路由
│   │   ├── api.ts                  # API 客户端 (40+ 接口)
│   │   ├── types.ts                # TypeScript 类型定义
│   │   ├── styles.css              # 设计系统 (深色主题)
│   │   ├── hooks/                  # 公共 Hooks
│   │   │   ├── useApi.ts           # 通用 async 请求
│   │   │   ├── useDebounce.ts      # 输入防抖
│   │   │   └── usePagination.ts    # 分页状态
│   │   └── components/             # 25 个页面组件
│   │       ├── shared/             # 6 个共享组件
│   │       │   ├── Modal.tsx
│   │       │   ├── ConfirmDialog.tsx
│   │       │   ├── EmptyState.tsx
│   │       │   ├── StatusBadge.tsx
│   │       │   ├── MultiSelect.tsx
│   │       │   └── RenderMarkdown.tsx
│   │       ├── DashboardPage.tsx
│   │       ├── TopicsPage.tsx
│   │       ├── SourcesPage.tsx
│   │       ├── ItemsPage.tsx
│   │       ├── TagsPage.tsx
│   │       ├── ReportsPage.tsx
│   │       ├── SchedulesPage.tsx
│   │       ├── SettingsPage.tsx
│   │       ├── ModelConfigPage.tsx
│   │       ├── HistoryPage.tsx
│   │       ├── NotificationsPage.tsx
│   │       ├── CategoriesPage.tsx
│   │       └── ... (子组件)
│   └── vite.config.ts
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── scripts/
│   └── dev.sh                     # 开发启动脚本
└── data/
    └── gather.db                  # SQLite 数据库
```

---

## API 文档

所有 API 前缀为 `/api/v1`。启动后端后可访问 `http://localhost:8109/docs` 查看交互式 Swagger 文档。

### 核心端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/sources` | 信息源列表/创建 |
| GET/PUT/DELETE | `/sources/{id}` | 信息源详情/更新/删除 |
| POST | `/sources/{id}/validate` | 测试信息源连接 |
| GET/POST | `/topics` | 主题列表/创建 |
| GET/PUT/DELETE | `/topics/{id}` | 主题详情/更新/删除 |
| POST | `/topics/{id}/collect` | 触发主题采集 |
| POST | `/collect` | 通用采集触发 |
| GET | `/items` | 条目列表 (支持过滤/搜索/分页) |
| GET | `/items/{id}` | 条目详情 |
| GET | `/items/ids` | 匹配条目的 ID 列表 |
| POST | `/items/batch-delete` | 批量删除条目 |
| GET | `/items/export` | 导出条目 (CSV/JSON/XLSX) |
| GET | `/runs` | 采集执行记录 |
| GET | `/runs/batches` | 按批次分组查看 |
| GET | `/runs/active` | 当前活跃采集任务 |
| GET | `/tags` | 标签列表 |
| POST | `/tags/merge` | 标签合并 |
| GET/POST | `/reports` | 报告列表/生成 |
| POST | `/reports/batch-generate` | 批量生成报告 |
| POST | `/reports/{id}/export` | 导出报告文件 |
| GET/POST | `/models` | AI 模型配置 |
| POST | `/models/{id}/test` | 测试模型连接 |
| GET/POST | `/notifications` | 通知配置 |
| GET | `/stats/dashboard` | 仪表盘一站式统计 |
| GET | `/settings` | 系统设置 |

---

## 开发指南

### 命令速查

```bash
# 类型检查
npm run typecheck

# 生产构建
npm run build

# 后端测试 (258 个用例)
cd backend && .venv/bin/python -m pytest tests/ -v

# 单个测试文件
cd backend && .venv/bin/python -m pytest tests/test_tags.py -v

# 代码格式化 (Python)
cd backend && .venv/bin/black app/ tests/

# 代码格式化 (前端)
cd frontend && npx prettier --write src/
```

### 研发约束

- 函数 ≤ 50 行，文件 ≤ 400 行
- 嵌套 ≤ 3 层
- TDD 循环 (RED → GREEN → IMPROVE)
- 数据不可变：始终创建新对象/数组
- 提交格式：`<type>: <简述>` (feat/fix/refactor/docs/test/chore/perf/ci)

### 设计系统

- **深色主题**：CSS 变量体系 (`--ink`, `--surface`, `--accent`, `--line` 等)
- **间距**：4px 步进 (4/8/12/16/24/32/48)
- **圆角**：`--radius: 8px`
- **字体**：Inter → SF Pro Display → PingFang SC → system-ui
- **图标**：Lucide React
- **图表**：ECharts

---

## 质量指标

| 指标 | 数值 |
|------|------|
| 后端测试用例 | 258 个，通过率 100% |
| TypeScript 类型检查 | 零错误 |
| 生产构建 | ✓ ~170ms |
| 后端模块 | 45 文件，~7000 行 |
| 前端组件 | 25 组件 + 6 共享 + 3 Hooks，~5400 行 |
| 信息源 | 92 个 (83 已配置 + 9 待 API Key) |
| API 端点 | 50+ |
| 覆盖渠道 | 9 种 |

---

## 待配置信息源

以下信息源需要填入 API Key 后方可激活：

| 信息源 | 获取地址 |
|--------|----------|
| NewsAPI | https://newsapi.org/register |
| Tavily Search | https://tavily.com |
| UN Comtrade | https://comtradeapi.un.org |
| Trading Economics | https://tradingeconomics.com |
| Inoreader | https://www.inoreader.com |
| Feedly | https://feedly.com |
| 百度搜索 | https://ai.baidu.com |
| Bing Search | https://azure.microsoft.com |
| Search1API | https://search1api.com |

---

## License

MIT
