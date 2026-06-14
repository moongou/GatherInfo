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
| **测试** | 258 个测试用例，`cd backend && .venv/bin/python -m pytest tests/ -v` |

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

# Docker
docker-compose up
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
        NotificationConfig (通知) ──> fire-and-forget on collection complete
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
| `notification_configs` | 通知配置 | name, channel (webhook/email), config_json, is_active, trigger_on |

### SourceChannel 枚举
`official` · `rss` · `commercial` · `web_scrape` · `api_search` · `json_api` · `social` · `deepweb` · `manual`

### JobStatus 枚举
`pending` · `running` · `completed` · `failed` · `partial`

### ItemStatus 枚举
`raw` → `tagged` → `enriched` → `archived` · `discarded`

---

## 后端架构

### 路由拆分（原 `collection_routes.py` 2227 行已拆为 12 个模块）

```
backend/app/
  main.py                      # FastAPI 应用工厂、CORS、限流中间件、lifespan 调度器
  models.py                    # SQLAlchemy ORM 模型再导出中心 (51行)
  _models_enums.py             # SourceChannel / JobStatus / ItemStatus 枚举 (31行)
  _models_sources.py           # SourceConfig + Category 模型 (71行)
  _models_items.py             # Tag / item_tags / CollectionRun / CollectedItem (156行)
  _models_config.py            # Topic / ScheduleConfig / ModelConfig / Report / SystemConfig (168行)
  database.py                  # 引擎/会话工厂/备份/一致性检查

  routes/
    __init__.py                # register_all_routers(app)
    _helpers.py                # 公共工具（分页/punctuation_norm 等）
    _seed_data.py              # 默认数据定义：主题/模型/标签/关键词模板 (130行)
    _seed_sources.py           # 默认信息源定义：91个信息源配置 (479行, 83已配置 + 8待API Key)
    topics.py                  # 主题 CRUD + 采集触发
    sources.py                 # 信息源 CRUD + 验证
    items.py                   # 条目查询/详情/删除/批量操作 + 全文搜索
    models.py                  # 模型配置 CRUD + 测试连接 + 自动发现
    reports.py                 # 报告生成/查看/删除/批量
    tags.py                    # 标签 CRUD + 合并
    settings.py                # 系统配置 + 配置导入导出
    schedules.py               # 全局调度管理
    notifications.py           # 通知配置 CRUD + 测试发送
    export_routes.py           # 条目导出（CSV/JSON/XLSX）
    search_tools.py            # 搜索工具管理
    seed.py                    # 种子数据 API

  services/
    source_service.py           # 信息源业务逻辑 (60行)
    topic_service.py            # 主题业务逻辑 (76行)
    item_service.py             # 条目查询/过滤/删除 (84行)
    tag_service.py              # 标签 CRUD + 合并 (127行)
    report_service.py           # 报告生成编排 (94行)

  connectors/
    __init__.py                # 注册所有内置连接器
    base.py                    # BaseCollector / FetchItem / CollectResult / ConnectorRegistry
    _helpers.py                # 共享工具函数：result() / detect_lang() / infer_category() / build_tags() / extract_title() / extract_body()
    tavily_search.py           # Tavily Web Search API（默认搜索引擎）
    search_engines.py          # 搜索分发器 + Baidu/Bing/360 委托 + TargetedScrapeCollector
    rss_collector.py           # RSS/Atom 订阅源采集
    web_scrape.py              # 结构化网页抓取（CSS 选择器 + BS4）
    official_api.py            # WTO ePing / EUR-Lex / 中国海关 / MOFCOM / UN Comtrade
    json_api.py                # 通用 JSON API 直连（NewsAPI 等）

  engine.py                    # 采集引擎：编排/去重/持久化/自动打标签/批次
  report_engine.py             # 智能报告生成：prompt → LLM → 持久化 (270行)
  llm_client.py                # LLM 调用客户端：call_llm / auto_summary / translate (175行)
  report_export.py             # 报告导出（MD/HTML/DOCX/PDF）
  scheduler.py                 # APScheduler：主题调度 + 自动报告触发
  fts_search.py                # SQLite FTS5 全文搜索
  notification_models.py       # 通知模型 + NotificationSender
  services.py                  # 配置导出/导入
  seed_demo_data.py            # 默认演示数据
  data.py                      # Demo 数据加载
  schemas.py                   # 旧的 Pydantic 模型
  models_additions.py          # 运行时 Schema 迁移
  stats_routes.py              # 仪表盘统计

  _schemas/
    common.py                  # 共享 Schema（IsoDT, StatsOut 等）
    source.py                  # SourceCreate/Update/Out
    topic.py                   # TopicCreate/Update/Out
    collection.py              # CollectRequest, RunOut, Item schemas, Batch
    tag.py                     # TagUpdate, TagMerge
    model.py                   # ModelConfig schemas
    report.py                  # Report schemas
    search.py                  # SearchToolConfig schemas

  collection_schemas.py        # 向后兼容再导出模块（69行）
```

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
  → 触发通知发送（fire-and-forget）
```

### 内容质量与结构化入库
- 采集条目入库前先走 `app/content_parser.py` 做本地解析：正文归一化、摘要兜底、国家/年份/数字等轻量实体提取，并写入 `entities` 与 `raw_metadata.content_analysis`。
- 空白内容、模板导航、版权/登录等少量无实质文本不入库，避免污染报告与搜索结果。
- 主题采集默认遵循用户配置的 `collect_window_days` 时间窗口；已知 `published_at` 超出窗口但仍满足关键词相关性的条目会保留，并自动打 `system:超限采集` 标签。
- 关键词过滤规则：1-2 个关键词至少匹配 1 个；3 个及以上关键词至少匹配 2 个，减少单关键词误收。

---

## 前端架构

### 组件结构（25 组件，~5000 行）

| 组件 | 行数 | 功能 |
|---|---|---|
| `App.tsx` | 81 | 导航框架（11 个菜单项）、侧边栏、视图路由 |
| `TopicsPage.tsx` | 252 | 主题管理主页 |
| `TopicForm.tsx` | 380 | 主题编辑表单 |
| `TopicCard.tsx` | 122 | 主题卡片展示 |
| `KeywordTemplatePicker.tsx` | 105 | 关键词模板选择器 |
| `ItemsPage.tsx` | 348 | 采集条目浏览：搜索/过滤/分页 |
| `ItemFilterBar.tsx` | 110 | 条目过滤工具栏 |
| `ItemDetailModal.tsx` | 125 | 条目详情弹窗 |
| `SourcesPage.tsx` | 295 | 信息源管理 |
| `ModelConfigPage.tsx` | 255 | AI 模型配置 |
| `ModelForm.tsx` | 171 | 模型编辑表单 |
| `SchedulesPage.tsx` | 383 | 周期调度管理 |
| `ReportsPage.tsx` | 292 | 智能报告管理 |
| `ReportCard.tsx` | 97 | 报告卡片 |
| `ReportBatchPanel.tsx` | 215 | 批量报告生成面板 |
| `ReportViewerModal.tsx` | 44 | 报告查看弹窗 |
| `TagsPage.tsx` | 378 | 标签系统 |
| `TagMergeDialog.tsx` | 120 | 标签合并对话框 |
| `CategoriesPage.tsx` | 141 | 分类管理 |
| `NotificationsPage.tsx` | 292 | 通知配置管理 |
| `SettingsPage.tsx` | 250 | 系统配置 |
| `DashboardPage.tsx` | 246 | 仪表盘概览 |
| `HistoryPage.tsx` | 250 | 采集历史 |
| `EChart.tsx` | 44 | ECharts React 封装 |
| `ErrorBoundary.tsx` | 47 | React 错误边界 |

### 共享组件 (`components/shared/`)

| 组件 | 行数 | 功能 |
|---|---|---|
| `Modal.tsx` | 48 | 通用弹窗 |
| `ConfirmDialog.tsx` | 68 | 确认对话框 |
| `EmptyState.tsx` | 27 | 空状态占位 |
| `StatusBadge.tsx` | 57 | 状态标签（pending/running/completed/failed） |
| `MultiSelect.tsx` | 111 | 多选下拉组件 |
| `RenderMarkdown.tsx` | 57 | Markdown 渲染 |

### 公共 Hooks (`hooks/`)

| Hook | 行数 | 功能 |
|---|---|---|
| `useApi.ts` | 77 | 通用 async 请求 hook（loading/error/data） |
| `useDebounce.ts` | 11 | 输入防抖 |
| `usePagination.ts` | 35 | 分页状态 |

### 核心文件

| 文件 | 行数 | 用途 |
|---|---|---|
| `api.ts` | 322 | **API 客户端**：40+ 个接口的 `get/post/put/del` 封装 |
| `types.ts` | 379 | TypeScript 类型定义 |
| `styles.css` | ~370 | 设计系统 CSS 变量 + 全组件样式（深色主题） |
| `templates.ts` | 98 | 关键词模板 + 描述提示词模板 |

### 设计系统

- **深色主题**：CSS 变量体系（`--ink`, `--surface`, `--accent`, `--line` 等）
- **间距**：4px 步进（4/8/12/16/24/32/48）
- **圆角**：`--radius: 8px`
- **字体**：Inter → SF Pro Display → PingFang SC → system-ui
- **响应式**：768px 断点切换侧边栏宽度 + 简化布局

---

## API 概览

所有 API 前缀为 `/api/v1`。

### 信息源
| 方法 | 路径 | 功能 |
|---|---|---|
| GET/POST | `/sources` | 列表/创建 |
| GET/PUT/DELETE | `/sources/{id}` | 获取/更新/删除 |
| POST | `/sources/{id}/validate` | 测试连接 |

### 主题
| 方法 | 路径 | 功能 |
|---|---|---|
| GET/POST | `/topics` | 列表/创建 |
| GET/PUT/DELETE | `/topics/{id}` | 获取/更新/删除 |
| POST | `/topics/{id}/collect` | 单主题采集 |

### 条目
| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/items` | 列表（支持 topic/source/tag/language/q/run_id） |
| GET | `/items/{id}` | 单条详情 |
| GET | `/items/ids` | 匹配条目的 ID 列表（全选用） |
| POST | `/items/batch-delete` | 批量删除 |
| GET | `/items/search` | 全文搜索（FTS5, title:/content: 语法） |
| GET | `/items/export` | 导出 CSV/JSON/XLSX |

### 采集
| 方法 | 路径 | 功能 |
|---|---|---|
| POST | `/collect` | 执行采集（按 topic_id 或 source_id） |
| GET | `/runs` | 采集执行记录 |
| GET | `/runs/batches` | 按 batch_id 分组 |
| GET | `/runs/active` | 当前活跃任务 |

### 模型
| 方法 | 路径 | 功能 |
|---|---|---|
| GET/POST | `/models` | 列表/创建 |
| GET/PUT/DELETE | `/models/{id}` | 获取/更新/删除 |
| POST | `/models/{id}/test` | 测试连接 |
| POST | `/models/{id}/list-models` | 列出可用模型 |
| POST | `/models/auto-discover` | 自动发现本地模型 |

### 报告
| 方法 | 路径 | 功能 |
|---|---|---|
| GET/POST | `/reports` | 列表/生成 |
| GET/DELETE | `/reports/{id}` | 查看/删除 |
| POST | `/reports/batch-generate` | 批量生成 |
| POST | `/reports/{id}/export` | 导出文件 |
| GET | `/reports/{id}/download` | 下载文件 |

### 标签
| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/tags` | 标签列表（支持 namespace 过滤） |
| POST | `/tags/merge` | 标签合并 |

### 通知
| 方法 | 路径 | 功能 |
|---|---|---|
| GET/POST | `/notifications` | 列表/创建 |
| PUT/DELETE | `/notifications/{id}` | 更新/删除 |
| POST | `/notifications/{id}/test` | 测试发送 |
| PUT | `/notifications/{id}/toggle` | 启用/禁用 |

### 系统
| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/settings` | 系统设置 |
| PUT | `/settings` | 更新设置 |
| POST | `/settings/export` | 导出配置 |
| POST | `/settings/import` | 导入配置 |
| GET/POST | `/seed` | 种子数据 |
| GET | `/stats/dashboard` | 仪表盘统计 |

---

## 调度系统

### 主题级别调度（推荐方式）
在主题编辑表单中设置：
1. Cron 表达式 → 执行频率（如 `0 8 * * *` = 每日 8 点）
2. 采集时间范围（天数）→ 限制发布时间窗口
3. 自动报告 → 采集完成后自动生成分析报告

### 全局调度（SchedulesPage）
绑定多个主题 + 信息源 + Cron 表达式。

### 自动报告触发
- 手动采集后触发（`POST /collect` 返回前 fire-and-forget）
- 定时调度触发（`scheduler._run_topic()` 中同步 await）
- 智能报告 prompt 先构造“信息集合摘要”（分类分布、来源分布、超限采集数量、关键证据），再附详细条目，要求模型先形成判断再综合成有观点、有层次、有论据的报告。

---

## 重要约定与陷阱

### 端口一致性
- **后端始终用 8109**：`scripts/dev.sh`、`vite.config.ts`、`startup.py`、`run_backend.py` 必须一致

### 数据不可变
- 前端 state 更新必须用展开运算符（`{...obj, key: val}`）

### 研发约束
- 函数 ≤50 行，文件 ≤400 行（极限 800）
- 嵌套 ≤3 层
- TDD 循环（RED → GREEN → IMPROVE），覆盖率 ≥80%
- 提交格式：`<type>: <描述>`（feat/fix/refactor/docs/test/chore/perf/ci）
- API 中英文标点容错（中文逗号/冒号统一归一化为英文）

### 其他注意
- SQLite 不支持并发写入（FastAPI 单进程已足够）
- `uvicorn` 的 `--factory` 标志因为 `create_app` 是工厂函数
- `.dev-pids` 文件用于 Dev Dashboard 停止时清理子进程
- `models_additions.py` 在每个 `init_db()` 时运行，自动添加缺失列
- 报告渲染依赖 WeasyPrint（PDF）/ Pandoc（DOCX），缺失时不阻塞
- 全文搜索使用 SQLite FTS5，`fts_search.py` 提供 `init_fts()` 和 `search_items()`
- `_schemas/` 下划线前缀用于避免与旧 `schemas.py` 冲突
- 通知系统采用 fire-and-forget 模式，不阻塞采集流程
