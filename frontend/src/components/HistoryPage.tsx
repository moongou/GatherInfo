import { useEffect, useState, useCallback } from "react";
import { Clock, RefreshCw, ChevronDown, ChevronRight, CheckCircle, AlertTriangle, Trash2 } from "lucide-react";
import { fetchActiveRuns, fetchBatches } from "../api";
import type { ActiveRunOut, BatchOut } from "../types";

export function HistoryPage() {
  const [activeRuns, setActiveRuns] = useState<ActiveRunOut[]>([]);
  const [batches, setBatches] = useState<BatchOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedBatch, setExpandedBatch] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ar, b] = await Promise.all([
        fetchActiveRuns().catch(() => []),
        fetchBatches(undefined, 30).catch(() => []),
      ]);
      setActiveRuns(ar);
      setBatches(b);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>采集历史</h2>
          <p className="text-muted">查看正在执行和已完成的采集任务。</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={load} disabled={loading}>
          <RefreshCw size={14} className={loading ? "spin" : ""} />
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? <div className="loading">加载中...</div> : (
        <div className="collection-history">
          {/* Active runs */}
          {activeRuns.length > 0 && (
            <div className="history-active-section">
              <h3><span className="pulse-dot" /> 正在执行 ({activeRuns.length})</h3>
              {activeRuns.map((run) => (
                <div key={run.id} className="active-run-card">
                  <div className="run-info">
                    <h4>{run.topic_name || run.source_name || run.source_id}</h4>
                    <p>
                      {run.source_name && <>来源: {run.source_name} · </>}
                      {run.keywords_used?.length > 0 && <>关键词: {run.keywords_used.slice(0, 3).join(", ")}{run.keywords_used.length > 3 ? "..." : ""} · </>}
                      {run.started_at && <>开始: {new Date(run.started_at).toLocaleTimeString("zh")}</>}
                      {run.duration_seconds != null && <> · 已耗时: {Math.floor(run.duration_seconds / 60)}分{run.duration_seconds % 60}秒</>}
                    </p>
                  </div>
                  <div className="run-status">
                    {run.items_found > 0 && <span className="chip chip--blue">{run.items_found} 条</span>}
                    <span className="chip chip--green" style={{ marginLeft: 4 }}>
                      {run.status === "running" ? "采集中" : "等待中"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeRuns.length === 0 && (
            <div className="history-empty">
              <Clock size={20} style={{ opacity: 0.3, marginBottom: 4 }} />
              <p>当前无正在执行的采集任务</p>
            </div>
          )}

          {/* Completed batches */}
          {batches.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <h3 style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: 12 }}>
                已完成批次 ({batches.length})
              </h3>
              {batches.map((batch) => (
                <div key={batch.batch_id} className="history-batch-card">
                  <div className="batch-header" onClick={() => setExpandedBatch(expandedBatch === batch.batch_id ? null : batch.batch_id)}>
                    <div>
                      <h4 style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        {batch.batch_label || batch.topic_name || "多源采集"}
                        <span className={`badge ${batch.status === "completed" ? "badge--green" : batch.status === "failed" ? "badge--gray" : "badge--blue"}`}>
                          {batch.status === "completed" ? "完成" : batch.status === "failed" ? "失败" : batch.status === "running" ? "运行中" : "部分完成"}
                        </span>
                      </h4>
                      <div className="batch-meta">
                        {batch.started_at && <span>{new Date(batch.started_at).toLocaleString("zh")}</span>}
                      </div>
                    </div>
                    <div className="batch-meta">
                      <span>新增 {batch.total_new} 条 · {batch.source_count} 源</span>
                      {expandedBatch === batch.batch_id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </div>
                  </div>
                  {expandedBatch === batch.batch_id && (
                    <div className="batch-detail">
                      {batch.runs.map((r) => (
                        <div key={r.id} className="batch-source-row">
                          <span className="source-name">{r.source_name || r.source_id}</span>
                          <span className="source-stats">
                            {r.status === "completed" ? <CheckCircle size={12} style={{ color: "var(--green)", verticalAlign: "middle", marginRight: 4 }} /> :
                             r.status === "failed" ? <AlertTriangle size={12} style={{ color: "var(--red)", verticalAlign: "middle", marginRight: 4 }} /> : null}
                            新增 {r.items_new} / 共 {r.items_found} 条
                            {r.duration_ms != null && <> · {(r.duration_ms / 1000).toFixed(1)}秒</>}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {batches.length === 0 && (
            <div className="history-empty" style={{ marginTop: 20 }}>
              <p>暂无采集历史</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
