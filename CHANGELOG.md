# Changelog

## [0.4.0] — 2026-06-07

### 新增功能
- **采集历史独立页面**：`HistoryPage` 组件，活跃任务实时追踪 + 已完成批次展开查看
- **批量删除条目**：ItemsPage 复选 + 全选（跨页调用 `GET /items/ids`），工具栏删除
- **信息批次标签**：`batch_label`（主题名\_时间戳），ItemsPage 批次筛选下拉
- **关键词模板推荐**：`recommendTemplates()` 根据输入关键词自动匹配 ★推荐模板
- **信息源多选下拉**：MultiSelect 组件替代 checkbox 网格，节省显示空间
- **搜索连接器分发器**：`SearchEngineDispatcher` 支持 Baidu / Bing / 360 搜索
- **采集历史 API**：`GET /runs/batches`（批次分组）、`GET /runs/active`（活跃任务）
- **条目 ID 查询 API**：`GET /items/ids` 返回匹配筛选条件的所有条目 ID
- **模型设为默认**：卡片底部一键「设为默认」按钮，默认模型排最前

### Bug 修复
- **Bad Gateway 502**：`scripts/dev.sh` 后端端口 8108 与 Vite proxy 目标 8109 不匹配 → 统一为 8109
- **采集窗口不生效**：`engine.py` 传递 `window_start` 参数，Tavily 解析 `published_date` 字段
- **关键词不相关条目入库**：`_persist_items()` 新增关键字匹配过滤，不匹配则跳过
- **自动报告未触发**：手动采集后 fire-and-forget 触发 auto_report
- **报告引用无链接**：报告提示词包含原文 URL，RenderMarkdown 支持 markdown 链接语法

### 重构
- `settings.py` 采集历史移出 → 独立 `HistoryPage.tsx`
- `App.tsx` 导航新增「采集历史」菜单
- SettingsPage 导入/导出从大卡片缩为紧凑按钮行
- 报告设置输入框文字加深（`--ink-muted` 调整）

### 数据库迁移
- `collection_runs` 新增列：`batch_id VARCHAR(80)`
- `topics` 新增列：`schedule_cron VARCHAR(100)`, `next_run_at TIMESTAMP`

### 配置变更
- `scripts/dev.sh`：后端端口 8108 → 8109
- `Dev Dashboard`：GatherInfo 项目新增 `stop_cmd` 强制清理 8109+5178 端口
- `.gitignore`：新增 `data/gather.db*`、`logs/`、`.dev-pids`、`AGENTS.md`、`save_memory.md`、`VERSION`、`CHANGELOG.md`

## [0.3.0] — Previous release
- API versioning, OpenAPI docs, error boundary, rate limiting
