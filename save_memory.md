
---

## Session: 2026-06-07

### 解决的问题

#### 1. Bad Gateway 502 — 端口不匹配
- **根因**：`scripts/dev.sh` 后端端口写死 8108，但 `vite.config.ts` 的 proxy 目标为 8109
- **修复**：dev.sh 两处端口 8108 → 8109（与 vite.config.ts / startup.py / run_backend.py 对齐）

#### 2. 采集引擎核心修复
- **关键词相关性过滤**：`engine.py` `_persist_items()` 新增关键字匹配，不匹配任何关键词的条目跳过入库
- **采集窗口强制执行**：窗口参数向下传递，`collect_window_days` 设置生效
- **批次分组**：每次 `collect_topic()` 生成共享 `batch_id`，同一次执行的所有来源共享一批
- **Tavily 发布支持**：解析 Tavily 响应中的 `published_date` 字段，用于窗口过滤
- **搜索连接器重构**：`search_engines.py` 改为 `SearchEngineDispatcher`，通过 `auth_config.search_type` 路由到 Tavily/Baidu/Bing/360

#### 3. 自动报告修复
- 手动采集（`POST /collect`）后触发 auto_report（fire-and-forget）
- 调度采集（`scheduler._run_topic`）中原有逻辑触发

#### 4. 模型配置增强
- 模型列表排序：默认模型排最前
- 每个非默认模型卡片新增「设为默认」按钮

#### 5. 采集历史独立页面
- 新建 `HistoryPage.tsx` 组件
- App.tsx 导航新增「采集历史」菜单项
- 活跃任务实时追踪（10s 轮询）+ 已完成批次展开查看
- SettingsPage 中的采集历史区域移除

#### 6. 新功能
- **采集历史管理**：`GET /runs/batches`、`GET /runs/active` 两个新 API
- **批量删除条目**：`POST /items/batch-delete` + ItemsPage 复选 + 全选（跨页）
- **条目 ID 查询**：`GET /items/ids` 返回匹配筛选条件的所有 ID（用于全选）
- **信息批次标签**：`batch_label` 字段（主题名\_时间戳），ItemsPage 新增批次筛选下拉
- **信息源多选下拉**：TopicsPage 表单中用 MultiSelect 组件替代 checkbox 网格
- **关键词模板推荐**：`recommendTemplates()` 根据输入关键词打分，★推荐标记
- **报告 URL 链接**：报告提示词包含原文 URL，RenderMarkdown 支持 `[text](url)` markdown 链接
- **Dev Dashboard**：GatherInfo 项目配置添加 `stop_cmd`（强制清理 8109+5178 端口）
- **设置页面重设计**：导入/导出从大卡片缩为一行按钮；报告设置文字加深

### 修改的文件

**Backend (8 files)**
- `scripts/dev.sh` — 8108→8109
- `backend/app/engine.py` — 关键词过滤、窗口强制、batch_id、窗口参数传递
- `backend/app/models_additions.py` — batch_id/schedule_cron/next_run_at 列迁移
- `backend/app/collection_routes.py` — batches/active/ids/batch-delete 端点、auto-report 触发
- `backend/app/collection_schemas.py` — BatchOut/BatchRunOut/ActiveRunOut/ItemDeleteRequest
- `backend/app/report_engine.py` — URL 字段加入上下文、prompt 指引链接引用
- `backend/app/connectors/tavily_search.py` — 解析 published_date
- `backend/app/connectors/search_engines.py` — SearchEngineDispatcher 分发器

**Frontend (9 files)**
- `frontend/src/App.tsx` — 新增 HistoryPage 导航
- `frontend/src/styles.css` — 响应式宽度、MultiSelect、历史卡片、文字加深
- `frontend/src/api.ts` — fetchItemIds/fetchBatches/fetchActiveRuns/batchDeleteItems
- `frontend/src/types.ts` — BatchRunOut/BatchOut/ActiveRunOut 类型
- `frontend/src/components/SettingsPage.tsx` — 移除历史、缩小导入/导出、清洗
- `frontend/src/components/TopicsPage.tsx` — MultiSelect、模板推荐
- `frontend/src/components/ItemsPage.tsx` — 全选、批次筛选、来源计数
- `frontend/src/components/ModelConfigPage.tsx` — 排序、设为默认按钮
- `frontend/src/components/HistoryPage.tsx` — 新建组件
- `frontend/src/components/ReportsPage.tsx` — markdown 链接渲染

**Dev Dashboard**
- `dev-dashboard/server.py` — GatherInfo 配置更新 + stop_cmd

### 数据库模式变更
- `collection_runs` 新增列：`batch_id` VARCHAR(80)
- `topics` 新增列：`schedule_cron` VARCHAR(100), `next_run_at` TIMESTAMP

### 掌握的关键知识
- 采集引擎：Topic → keywords → sources → connectors → FetchItem → 过滤 → 去重 → 持久化 → 自动打标签
- 批次模型：一次 `collect_topic` = 一个 `batch_id` → 多个 `CollectionRun`（每个来源一条）→ 多条 `CollectedItem`
- 前端视图切换：`App.tsx` 的 `ViewId` 联合类型驱动，无路由库
- 连接器注册：`@register_collector(channel)` 装饰器，`ConnectorRegistry.create(config)` 按频道名查找
- 启动顺序：dev.sh 先起后端（8109）→ 再起前端（5178），watchdog 循环保活
- 自动报告：两种触发路径（手动采集 fire-and-forget / 调度采集同步 await）
