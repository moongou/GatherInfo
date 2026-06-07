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
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <h1>GatherInfo</h1>
            <span className="subtitle">主题驱动·多源采集·智能报告</span>
          </div>
          <div className="app-logo" style={{
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            width: 36, height: 36, borderRadius: 10,
            background: "linear-gradient(135deg, rgba(59,130,246,0.18), rgba(34,197,94,0.10))",
            border: "1px solid rgba(59,130,246,0.25)",
            position: "relative", overflow: "hidden"
          }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="9" stroke="#3b82f6" strokeWidth="1.5" opacity="0.7"/>
              <ellipse cx="12" cy="12" rx="7" ry="2.5" stroke="#3b82f6" strokeWidth="0.8" opacity="0.5"/>
              <ellipse cx="12" cy="9" rx="6" ry="1.5" stroke="#3b82f6" strokeWidth="0.6" opacity="0.3"/>
              <ellipse cx="12" cy="15" rx="6" ry="1.5" stroke="#3b82f6" strokeWidth="0.6" opacity="0.3"/>
              <line x1="12" y1="3" x2="12" y2="21" stroke="#3b82f6" strokeWidth="0.8" opacity="0.4"/>
              <text x="12" y="16" textAnchor="middle" fontSize="11" fontWeight="700" fill="#3b82f6" fontFamily="Inter, sans-serif" letterSpacing="0.5">g</text>
              <circle cx="20" cy="7" r="1.5" fill="#22c55e" opacity="0.8"/>
              <circle cx="19" cy="18" r="1" fill="#22c55e" opacity="0.5"/>
              <circle cx="5" cy="17" r="1.2" fill="#22c55e" opacity="0.6"/>
              <circle cx="4" cy="8" r="0.8" fill="#22c55e" opacity="0.4"/>
              <path d="M12 3 A9 9 0 0 1 20.5 7.5" stroke="#22c55e" strokeWidth="1.2" strokeLinecap="round" opacity="0.6"/>
            </svg>
          </div>
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
