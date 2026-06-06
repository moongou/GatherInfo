import { useEffect, useState, useCallback } from "react";
import {
  RefreshCw, TrendingUp, Globe, Database, Tags, AlertCircle,
} from "lucide-react";
import { fetchDashboard, collectTopic } from "../api";
import type { DashboardData } from "../types";
import { EChart } from "./EChart";
import type { EChartsOption } from "echarts";

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fetchDashboard());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const triggerCollect = async (topicId: string) => {
    setRefreshing(topicId);
    try {
      const results = await collectTopic(topicId);
      const total = results.reduce((s, r) => s + r.items_new, 0);
      if (total > 0) await load();
    } catch { /* ignore */ }
    setRefreshing(null);
  };

  if (loading) return <div className="loading">加载仪表盘...</div>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return null;

  const { summary, top_tags, source_health, daily_trend, categories } = data;

  const statCards = [
    { label: "总条目", value: summary.total_items, icon: Database, color: "#3b82f6" },
    { label: "今日采集", value: summary.items_today, icon: TrendingUp, color: "#22c55e" },
    { label: "活跃信息源", value: summary.active_sources, icon: Globe, color: "#f59e0b" },
    { label: "主题数", value: summary.total_topics, icon: Tags, color: "#8b5cf6" },
    { label: "标签数", value: summary.total_tags, color: "#ec4899" },
    { label: "本周新增", value: summary.items_this_week, icon: RefreshCw, color: "#06b6d4" },
  ];

  const trendOption: EChartsOption = {
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: daily_trend.map((d) => d.date.slice(5)), axisLabel: { fontSize: 11 } },
    yAxis: { type: "value" },
    series: [{
      name: "采集条目", type: "line", data: daily_trend.map((d) => d.count),
      smooth: true, symbol: "circle", symbolSize: 6,
      lineStyle: { color: "#3b82f6", width: 2 },
      itemStyle: { color: "#3b82f6" },
      areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [{ offset: 0, color: "rgba(59,130,246,0.3)" }, { offset: 1, color: "rgba(59,130,246,0.01)" }] } },
    }],
    grid: { left: 40, right: 20, top: 10, bottom: 30 },
  };

  const catChartOption: EChartsOption = {
    tooltip: { trigger: "item" },
    series: [{
      type: "pie", radius: ["50%", "80%"], center: ["50%", "55%"],
      data: categories.slice(0, 8).map((c) => ({ name: c.category, value: c.count })),
      label: { fontSize: 11 }, emphasis: { label: { fontSize: 14, fontWeight: "bold" } },
      itemStyle: { borderRadius: 4, borderColor: "#111827", borderWidth: 2 },
    }],
  };

  return (
    <div className="dashboard">
      {/* Stat cards */}
      <div className="stat-grid">
        {statCards.map((sc) => {
          const Icon = sc.icon;
          return (
            <article key={sc.label} className="stat-card">
              <div className="stat-card-header">
                <span style={{ color: sc.color }}>{Icon ? <Icon size={16} /> : null}</span>
                <span className="stat-label">{sc.label}</span>
              </div>
              <strong className="stat-value">{sc.value.toLocaleString()}</strong>
            </article>
          );
        })}
      </div>

      {/* Charts row */}
      <div className="chart-row">
        <div className="chart-card">
          <h3>每日采集趋势</h3>
          <EChart option={trendOption} style={{ height: 220 }} />
        </div>
        <div className="chart-card">
          <h3>分类分布</h3>
          <EChart option={catChartOption} style={{ height: 220 }} />
        </div>
      </div>

      {/* Top tags */}
      <div className="panel">
        <h3>热门标签</h3>
        <div className="tag-cloud">
          {top_tags.slice(0, 20).map((t) => (
            <span key={t.id} className="tag-chip" title={t.namespace}>
              {t.value}
              <em>{t.count}</em>
            </span>
          ))}
        </div>
      </div>

      {/* Source health */}
      <div className="panel">
        <h3>信息源状态</h3>
        <div className="source-grid">
          {source_health.map((s) => (
            <div key={s.id} className="source-row">
              <div className="source-name">
                <span className={`dot ${s.is_active ? "dot--green" : "dot--gray"}`} />
                {s.name}
              </div>
              <div className="source-meta">
                <span>{s.items_collected} 条</span>
                {s.last_sync_at && (
                  <span className="text-muted">最后同步: {new Date(s.last_sync_at).toLocaleString("zh")}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick collect */}
      <div className="panel">
        <h3>快速采集</h3>
        <div className="quick-collect">
          <button type="button" className="btn btn-primary" onClick={() => triggerCollect("global-trade")} disabled={refreshing === "global-trade"}>
            <RefreshCw size={14} className={refreshing === "global-trade" ? "spin" : ""} />
            {refreshing === "global-trade" ? "采集中..." : "采集 · 全球贸易政策"}
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => triggerCollect("tech-regulations")} disabled={refreshing === "tech-regulations"}>
            <RefreshCw size={14} className={refreshing === "tech-regulations" ? "spin" : ""} />
            {refreshing === "tech-regulations" ? "采集中..." : "采集 · 技术性贸易措施"}
          </button>
        </div>
      </div>
    </div>
  );
}
