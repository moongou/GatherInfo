import { useMemo, useState } from "react";
import {
  LayoutDashboard, Globe, Tags, Database, Clock, BarChart3, Cpu, FileText, Settings, FolderTree,
} from "lucide-react";

import { DashboardPage } from "./components/DashboardPage";
import { TopicsPage } from "./components/TopicsPage";
import { SourcesPage } from "./components/SourcesPage";
import { ItemsPage } from "./components/ItemsPage";
import { TagsPage } from "./components/TagsPage";
import { SchedulesPage } from "./components/SchedulesPage";
import { ModelConfigPage } from "./components/ModelConfigPage";
import { SettingsPage } from "./components/SettingsPage";
import { HistoryPage } from "./components/HistoryPage";
import { CategoriesPage } from "./components/CategoriesPage";
import { ReportsPage } from "./components/ReportsPage";
import { ErrorBoundary } from "./components/ErrorBoundary";

type ViewId = "dashboard" | "categories" | "topics" | "sources" | "items" | "tags" | "schedules" | "models" | "reports" | "history" | "settings";

interface ViewDef {
  id: ViewId;
  label: string;
  icon: typeof LayoutDashboard;
}

const views: ViewDef[] = [
  { id: "dashboard", label: "仪表盘", icon: LayoutDashboard },
  { id: "categories", label: "采集类别", icon: FolderTree },
  { id: "topics", label: "主题管理", icon: BarChart3 },
  { id: "sources", label: "信息源", icon: Globe },
  { id: "items", label: "采集条目", icon: Database },
  { id: "tags", label: "标签系统", icon: Tags },
  { id: "reports", label: "智能报告", icon: FileText },
  { id: "models", label: "模型配置", icon: Cpu },
  { id: "schedules", label: "周期调度", icon: Clock },
  { id: "history", label: "采集历史", icon: Clock },
  { id: "settings", label: "系统配置", icon: Settings },
];

export function App() {
  const [view, setView] = useState<ViewId>("dashboard");

  const activeDef = useMemo(() => views.find((v) => v.id === view) ?? views[0], [view]);

  return (
    <div className="app-shell">
      <aside className="side-rail">
        <div className="brand">GatherInfo<div style={{ fontSize: "0.62rem", fontWeight: 400, color: "var(--ink-muted)", letterSpacing: "0.04em", marginTop: 2 }}>全球信息采集监控平台</div></div>
        <nav>
          {views.map((v) => {
            const Icon = v.icon;
            const isActive = view === v.id;
            return (
              <button
                key={v.id}
                type="button"
                className={`nav-btn${isActive ? " nav-btn--active" : ""}`}
                onClick={() => setView(v.id)}
                title={v.label}
              >
                <Icon size={18} />
                <span>{v.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
      <main className="workspace">
        <header className="workspace-header">
          <h1>GatherInfo</h1>
          <span className="subtitle">主题驱动·多源采集·智能报告</span>
        </header>
        <section className="view-frame">
           <ErrorBoundary key={view}>
             {view === "dashboard" && <DashboardPage />}
             {view === "categories" && <CategoriesPage />}
             {view === "topics" && <TopicsPage />}
             {view === "sources" && <SourcesPage />}
             {view === "items" && <ItemsPage />}
             {view === "tags" && <TagsPage />}
             {view === "reports" && <ReportsPage />}
             {view === "models" && <ModelConfigPage />}
             {view === "history" && <HistoryPage />}
             {view === "settings" && <SettingsPage />}
             {view === "schedules" && <SchedulesPage />}
           </ErrorBoundary>
        </section>
      </main>
    </div>
  );
}
