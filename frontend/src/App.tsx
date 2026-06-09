import { useEffect, useMemo, useState, Suspense, lazy } from "react";
import {
  LayoutDashboard, Globe, Tags, Database, Clock, BarChart3, Cpu, FileText, Settings, FolderTree, Bell, History,
} from "lucide-react";

import { fetchDashboard } from "./api";
import type { DashboardData } from "./types";
import { ErrorBoundary } from "./components/ErrorBoundary";

// ── Lazy-loaded page components (code-split per view) ──────────────────

const DashboardPage = lazy(() => import("./components/DashboardPage").then(m => ({ default: m.DashboardPage })));
const TopicsPage = lazy(() => import("./components/TopicsPage").then(m => ({ default: m.TopicsPage })));
const SourcesPage = lazy(() => import("./components/SourcesPage").then(m => ({ default: m.SourcesPage })));
const ItemsPage = lazy(() => import("./components/ItemsPage").then(m => ({ default: m.ItemsPage })));
const TagsPage = lazy(() => import("./components/TagsPage").then(m => ({ default: m.TagsPage })));
const SchedulesPage = lazy(() => import("./components/SchedulesPage").then(m => ({ default: m.SchedulesPage })));
const ModelConfigPage = lazy(() => import("./components/ModelConfigPage").then(m => ({ default: m.ModelConfigPage })));
const SettingsPage = lazy(() => import("./components/SettingsPage").then(m => ({ default: m.SettingsPage })));
const HistoryPage = lazy(() => import("./components/HistoryPage").then(m => ({ default: m.HistoryPage })));
const CategoriesPage = lazy(() => import("./components/CategoriesPage").then(m => ({ default: m.CategoriesPage })));
const ReportsPage = lazy(() => import("./components/ReportsPage").then(m => ({ default: m.ReportsPage })));
const NotificationsPage = lazy(() => import("./components/NotificationsPage").then(m => ({ default: m.NotificationsPage })));

// ── Loading fallback ───────────────────────────────────────────────────

function PageLoader() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "80px 0" }}>
      <div className="page-loader">
        <div className="page-loader-spinner" />
        <span style={{ color: "var(--ink-muted)", fontSize: "0.85rem" }}>加载中...</span>
      </div>
    </div>
  );
}

type ViewId = "dashboard" | "categories" | "topics" | "sources" | "items" | "tags" | "schedules" | "models" | "reports" | "history" | "settings" | "notifications";

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
  { id: "history", label: "采集历史", icon: History },
  { id: "notifications", label: "通知管理", icon: Bell },
  { id: "settings", label: "系统配置", icon: Settings },
];

/** Time-of-day greeting in Chinese */
function greeting(): string {
  const h = new Date().getHours();
  if (h < 6) return "夜深了";
  if (h < 12) return "上午好";
  if (h < 18) return "下午好";
  return "晚上好";
}

/** Radar-scan logo — 3 concentric arcs + a pulse dot, clean line-art style */
function AppLogo() {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Radar arcs — opening toward top-right */}
      <path d="M20 4 A16 16 0 0 1 35.3 12.7" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" opacity="0.9" />
      <path d="M20 9 A11 11 0 0 1 30 15" stroke="#3b82f6" strokeWidth="1.8" strokeLinecap="round" opacity="0.65" />
      <path d="M20 14 A6 6 0 0 1 24.5 17.5" stroke="#3b82f6" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
      {/* Pulse dot at leading edge */}
      <circle cx="35.3" cy="12.7" r="2.5" fill="#22c55e" opacity="0.9">
        <animate attributeName="opacity" values="0.9;0.3;0.9" dur="2s" repeatCount="indefinite" />
      </circle>
      {/* Subtle center dot */}
      <circle cx="20" cy="20" r="2" fill="#3b82f6" opacity="0.5" />
    </svg>
  );
}

export function App() {
  const [view, setView] = useState<ViewId>("dashboard");
  const [dashData, setDashData] = useState<DashboardData | null>(null);

  const activeDef = useMemo(() => views.find((v) => v.id === view) ?? views[0], [view]);

  // Fetch dashboard summary for the dynamic greeting
  useEffect(() => {
    let cancelled = false;
    fetchDashboard().then((d) => { if (!cancelled) setDashData(d); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const itemsToday = dashData?.summary?.items_today ?? 0;

  return (
    <div className="app-shell">
      <aside className="side-rail">
        <div className="brand">
          <AppLogo />
          <span className="brand-name">GatherInfo</span>
          <span className="brand-sub">global trade intelligence</span>
        </div>
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
          <div className="header-greeting">
            <span className="greeting-text">{greeting()}，今日已采集 <strong>{itemsToday.toLocaleString()}</strong> 条新情报</span>
          </div>
          <div className="header-actions">
            <button
              type="button"
              className="btn-icon header-action-btn"
              title="刷新仪表盘"
              onClick={() => { setView("dashboard"); }}
            >
              <LayoutDashboard size={18} />
            </button>
          </div>
        </header>
        <section className="view-frame">
           <ErrorBoundary key={view}>
             <Suspense fallback={<PageLoader />}>
               {view === "dashboard" && <DashboardPage />}
               {view === "categories" && <CategoriesPage />}
               {view === "topics" && <TopicsPage />}
               {view === "sources" && <SourcesPage />}
               {view === "items" && <ItemsPage />}
               {view === "tags" && <TagsPage />}
               {view === "reports" && <ReportsPage />}
               {view === "models" && <ModelConfigPage />}
               {view === "history" && <HistoryPage />}
               {view === "notifications" && <NotificationsPage />}
               {view === "settings" && <SettingsPage />}
               {view === "schedules" && <SchedulesPage />}
             </Suspense>
           </ErrorBoundary>
        </section>
      </main>
    </div>
  );
}
