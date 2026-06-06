# GatherInfo — 全球信息采集监控平台

## 项目概述

GatherInfo 是一个主题驱动的多源信息采集、标签化入库、统计分析与智能报告生成平台。

| 维度 | 详情 |
|---|---|
| **目标用户** | 跨境贸易情报分析师、海关合规人员 |
| **前端** | React + TypeScript + Vite (rolldown)，端口 5178 |
| **后端** | Python FastAPI + SQLAlchemy 2.0，端口 8109 |
| **数据库** | SQLite（`data/gather.db`），WAL 模式 |
| **启动方式** | `npm run dev` → `scripts/dev.sh` → 同时启动前后端 |
| **Dev Dashboard** | `localhost:9999` 管理所有本地服务 |

---

## 技术栈

### 前端
- `@vitejs/plugin-react` + Vite (rolldown) 构建
- React 18 + TypeScript
- ECharts（仪表盘图表）
- Lucide React（图标库）
- 无路由库：通过 App.tsx 中 `ViewId` 状态驱动视图切换

### 后端
- FastAPI（`app/main.py` 的 `create_app()` 工厂）
- SQLAlchemy 2.0 ORM + SQLite (WAL)
- APScheduler（周期调度）
- httpx（异步 HTTP 客户端）
- BeautifulSoup4（网页解析）
- Pydantic v2（API 校验）

---

## 启动与端口

```bash
# 开发启动
npm run dev
# → backend/.venv/bin/python -m uvicorn ... --port 8109
# → npm run dev (vite) ... --port 5178

# Vite 开发服务器
# 前端: http://localhost:5178
# proxy: /api/* → http://127.0.0.1:8109
# proxy: /health → http://127.0.0.1:8109

# 生产构建
npm run build    # 在 frontend/dist/ 输出
```

### 其他启动方式
- `python3 startup.py` — 通过 `subprocess` 拉起前后端
- `python3 run_backend.py` — 仅启动后端（8109 端口）
- Dev Dashboard (`localhost:9999`) — 启停按钮管理全部服务

---

## 数据模型（SQLAlchemy）

### 核心实体

```
SourceConfig (信息源) ──< CollectionRun (采集执行) ──< CollectedItem (采集条目) >── Tag (标签)
        Topic (主题)    ──< CollectionRun
```

### 表结构

| 表名 | 用途 | 关键字段 |
|---|---|---|
| `topics` | 采集主题定义 | id, name, keywords, source_ids, schedule_cron, collect_window_days, auto_report, auto_tag_rules, keyword_tags, description_prompt |
| `source_configs` | 信息源配置 | id, name, channel (枚举), base_url, api_key, auth_config, rate_limit_rps |
| `collection_runs` | 每次采集的执行记录 | source_id, topic_id, status, items_new, batch_id, window_start/end, error_log |
| `collected_items` | 采集到的单条信息 | source_id, run_id, topic_id, title, content, url, language, category, tags (M:N), quality_score |
| `tags` | 标签系统 | id, namespace, value, color, item_count (M:N 关联 CollectedItem) |
| `reports` | 自动生成的报告 | topic_id, title, content, status, model_id, item_ids, collection_run_id |
| `model_configs` | AI 模型配置 | id, provider, base_url, api_key, model_name, is_default |
| `schedule_configs` | 全局调度配置 | cron_expression, source_ids, topic_ids |
| `system_config` | 单行全局设置 | report_title_format, report_output_dir, report_formats |

### SourceChannel 枚举
`official` · `rss` · `commercial` · `web_scrape` · `api_search` · `json_api` · `social` · `deepweb` · `manual`

### JobStatus 枚举
`pending` · `running` · `completed` · `failed` · `partial`

### ItemStatus 枚举
`raw` → `tagged` → `enriched` → `archived` · `discarded`

---

## 后端架构

### 文件结构（17 文件，5998 行）

| 文件 | 行数 | 职责 |
|---|---|---|
| `main.py` | 261 | FastAPI 应用工厂、CORS、限流中间件、lifespan 调度器启动 |
| `collection_routes.py` | 2227 | **全部 API 路由**：源/主题/采集/条目/标签/模型/报告/设置 |
| `collection_schemas.py` | 568 | Pydantic 请求/响应模型（TopicCreate, TopicOut, BatchOut 等） |
| `engine.py` | 289 | **采集引擎**：采集编排、去重持久化、自动打标签、批次分组 |
| `report_engine.py` | 329 | 智能报告生成：构建提示词 → 调用 LLM → 持久化 + 导出 |
| `report_export.py` | 244 | 报告导出（MD/HTML/DOCX/PDF） |
| `scheduler.py` | 126 | APScheduler 集成：主题调度 + 自动报告触发 |
| `stats_routes.py` | 136 | 仪表盘统计、每日趋势、分类/语言/来源分布 |
| `models.py` | 516 | SQLAlchemy ORM 模型定义 |
| `models_additions.py` | 153 | 运行时 Schema 迁移（`ALTER TABLE ADD COLUMN`） |
| `database.py` | 115 | SQLAlchemy 引擎、会话工厂、DB 备份 + 一致性检查 |
| `services.py` | 216 | 配置导出/导入（全部模型的 JSON 序列化） |
| `seed_demo_data.py` | 351 | 默认数据：自带 16 个信息源 + 2 个主题 + 关键词模板 |
| `data.py` | 287 | Demo 数据加载 |
| `schemas.py` | 179 | 旧的 Pydantic 模型（部分被 collection_schemas 取代） |

### 采集引擎流程（engine.py）

```
collect_topic(topic_id)
  → 解析 Topic（keywords, source_ids, collect_window_days）
  → 生成 batch_id（同次执行的所有来源共享）
  → 并行调用 collect_from_source() 每个关联来源
    → 创建 CollectionRun
    → ConnectorRegistry.create(source) → connector.fetch(keywords)
    → _persist_items() → 关键词过滤 + 窗口过滤 + 去重入库
  → _apply_auto_tags() → 根据 auto_tag_rules 自动打标签
  → 更新 Topic.last_run_at / total_items_collected
  → 触发自动报告（如 auto_report=True）
```

### 连接器系统（8 文件）

| 文件 | 注册频道 | 用途 |
|---|---|---|
| `base.py` | — | 抽象基类 `BaseCollector`、`FetchItem`、`CollectResult`、`ConnectorRegistry` |
| `tavily_search.py` | `api_search` | **Tavily Web Search API** (默认搜索引擎, 生产主力) |
| `rss_collector.py` | `rss` | RSS/Atom 订阅源采集 |
| `web_scrape.py` | `web_scrape` | 结构化网页抓取（CSS 选择器 + BS4 解析） |
| `official_api.py` | `official` | 官方 API：WTO ePing / EUR-Lex / 中国海关 / MOFCOM / UN Comtrade |
| `search_engines.py` | `api_search` | **搜索分发器**：根据 auth_config.search_type 路由到 Baidu/Bing/360/Tavily |
| `json_api.py` | `json_api` | 通用 JSON API 直连（NewsAPI 等） |

---

## 前端架构

### 组件结构（13 组件，3263 行）

| 组件 | 行数 | 功能 |
|---|---|---|
| `App.tsx` | 81 | 导航框架（9 个菜单项）、侧边栏、视图路由 |
| `TopicsPage.tsx` | 499 | **主题管理**：CRUD + 关键词模板推荐 + 多选信息源下拉 + 采集/报告 |
| `ModelConfigPage.tsx` | 402 | AI 模型配置：添加/编辑/测试/自动发现/设为默认 |
| `ItemsPage.tsx` | 363 | 采集条目浏览：搜索/过滤/分页/全文阅读/批量选择删除 |
| `SchedulesPage.tsx` | 375 | 周期调度管理：频率选择器/Cron 预览/主题绑定 |
| `ReportsPage.tsx` | 360 | 智能报告：生成/查看/导出/批量生成/Markdown 渲染 |
| `TagsPage.tsx` | 364 | 标签系统：按命名空间管理/统计/合并/M:N 关联 |
| `SettingsPage.tsx` | 254 | 系统配置：配置导出/导入/报告设置 |
| `SourcesPage.tsx` | 261 | 信息源管理：CRUD/连接验证/渠道选择 |
| `HistoryPage.tsx` | 134 | 采集历史：活跃任务实时追踪 + 已完成批次展开查看 |
| `DashboardPage.tsx` | 160 | 仪表盘概览：ECharts 统计图表 |
| `EChart.tsx` | 44 | ECharts React 封装 |
| `ErrorBoundary.tsx` | 47 | React 错误边界 |

### 核心文件

| 文件 | 行数 | 用途 |
|---|---|---|
| `api.ts` | ~220 | **API 客户端**：全部 35+ 个接口的 `get/post/put/del` 封装 |
| `types.ts` | ~200 | TypeScript 类型定义：Source, Topic, BatchOut, ActiveRunOut 等 |
| `styles.css` | ~370 | 设计系统 CSS 变量 + 全组件样式（深色主题） |
| `templates.ts` | 98 | 关键词模板 + 描述提示词模板（10+5 个预设） |

### 设计系统

- **深色主题**：CSS 变量体系（`--ink`, `--surface`, `--accent`, `--line` 等）
- **间距**：4px 步进（4/8/12/16/24/32/48）
- **圆角**：`--radius: 8px`
- **字体**：Inter → SF Pro Display → PingFang SC → system-ui
- **响应式**：768px 断点切换侧边栏宽度 + 简化布局

---

## API 概览

所有 API 前缀为 `/api/v1`。

### 核心资源路由

| 方法 | 路径 | 功能 |
|---|---|---|
| GET/POST | `/sources` | 列表/创建信息源 |
| GET/PUT/DELETE | `/sources/{id}` | 获取/更新/删除 |
| POST | `/sources/{id}/validate` | 测试连接 |
| GET/POST | `/topics` | 列表/创建主题 |
| GET/PUT/DELETE | `/topics/{id}` | 获取/更新/删除 |
| POST | `/collect` | 执行采集（按 topic_id 或 source_id） |
| GET | `/items` | 条目列表（支持 topic/source/tag/language/q/run_id 过滤） |
| GET | `/items/{id}` | 单条详情 |
| GET | `/items/ids` | 匹配条目的 ID 列表（用于全选） |
| POST | `/items/batch-delete` | 批量删除 |
| GET | `/runs` | 采集执行记录 |
| GET | `/runs/batches` | 按 batch_id 分组的批次历史 |
| GET | `/runs/active` | 当前正在执行的任务 |
| GET/POST | `/models` | AI 模型 CRUD |
| POST | `/models/{id}/test` | 测试连接 |
| POST | `/models/{id}/list-models` | 列出可用模型 |
| POST | `/models/auto-discover` | 自动发现本地模型服务 |
| GET/POST | `/reports` | 报告列表/生成 |
| GET/DELETE | `/reports/{id}` | 查看/删除报告 |
| POST | `/reports/batch-generate` | 批量生成 |
| POST | `/reports/{id}/export` | 导出文件 |
| GET | `/reports/{id}/download` | 下载文件 |
| GET | `/tags` | 标签列表 |
| POST | `/tags/merge` | 标签合并 |
| GET | `/settings` | 系统设置 |
| GET | `/stats/dashboard` | 仪表盘统计 |

---

## 调度系统

### 主题级别调度（推荐方式）
在主题编辑表单中：
1. Cron 表达式 → 设定执行频率（如 `0 8 * * *` = 每日 8 点）
2. 采集时间范围（天数）→ 限制发布时间窗口
3. 自动报告 → 采集完成后自动生成分析报告

调度名称自动生成格式：`主题名_频率_信息`

### 全局调度（SchedulesPage）
传统方式：绑定多个主题 + 信息源 + Cron 表达式，更灵活但更复杂。

### 自动报告触发
- 手动采集后触发（`POST /collect` 返回前 fire-and-forget）
- 定时调度触发（`scheduler._run_topic()` 中同步 await）

---

## 重要约定与陷阱

### 端口一致性
- **后端始终用 8109**：`scripts/dev.sh`、`vite.config.ts`、`startup.py`、`run_backend.py` 必须一致
- 之前 dev.sh 使用 8108 导致 Vite proxy 502 Bad Gateway（已修复）

### 数据不可变
- 前端 state 更新必须用展开运算符（`{...obj, key: val}`）
- 直接修改 `obj.name = x` 会导致不可预测的 bug

### 研发约束
- 函数 ≤50 行，文件 ≤400 行（极限 800）
- 嵌套 ≤3 层
- TDD 循环（RED → GREEN → IMPROVE），覆盖率 ≥80%
- 提交格式：`<type>: <描述>`（feat/fix/refactor/docs/test/chore/perf/ci）
- API 中英文标点容错（中文逗号/冒号统一归一化为英文）
- `apply_patch` 格式要求首行 `*** Begin Patch`

### 其他注意
- SQLite 不支持并发写入（FastAPI 单进程已足够）
- `uvicorn` 的 `--factory` 标志因为 `create_app` 是工厂函数
- `.dev-pids` 文件用于 Dev Dashboard 停止时清理子进程
- `models_additions.py` 在每个 `init_db()` 时运行，自动添加缺失列
- 报告渲染依赖 WeasyPrint（PDF）/ Pandoc（DOCX），缺失时不阻塞
