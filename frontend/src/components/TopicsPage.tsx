import { useEffect, useState, useCallback } from "react";
import { Plus, RefreshCw, Trash2, Edit3, Globe, Target, FileText, BrainCircuit } from "lucide-react";
import { fetchTopics, createTopic, deleteTopic, updateTopic, collectTopic, generateReport, fetchModels, fetchSources, fetchCategories } from "../api";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import type { Topic, CollectResult, ModelConfig, Source } from "../types";
import { TopicForm } from "./TopicForm";

/** Humanize a 5-field cron expression into a Chinese description (best-effort). */
function humanizeCron(cron: string | null): string {
  if (!cron) return "未设置";
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return cron;
  const [min, hour, dom, , dow] = parts;
  const hh = hour.padStart(2, "0");
  const mm = min.padStart(2, "0");
  if (dom === "*" && dow === "*") return `每日 ${hh}:${mm}`;
  if (dom === "*" && dow !== "*") {
    const days = ["日", "一", "二", "三", "四", "五", "六"];
    const d = days[Number(dow)] ?? dow;
    return `每周${d} ${hh}:${mm}`;
  }
  if (dom !== "*" && dow === "*") return `每月${dom}日 ${hh}:${mm}`;
  return cron;
}

export function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Topic | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [collecting, setCollecting] = useState<string | null>(null);
  const [collectMsg, setCollectMsg] = useState<string | null>(null);
  const [generating, setGenerating] = useState<string | null>(null);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [categories, setCategories] = useState<{id:string;name:string}[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<{id: string; message: string} | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, ms, srcs, cats] = await Promise.all([
        fetchTopics(),
        fetchModels().catch(() => []),
        fetchSources().catch(() => []),
        fetchCategories().catch(() => []),
      ]);
      setTopics(t);
      setModels(ms);
      setSources(srcs);
      setCategories(cats);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleDelete = (id: string) => {
    setConfirmDelete({ id, message: `删除主题 "${id}"？` });
  };

  const executeDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    try {
      await deleteTopic(id);
      setTopics((prev) => prev.filter((t) => t.id !== id));
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
    setConfirmDelete(null);
  };

  const handleCollect = async (id: string) => {
    setCollecting(id);
    setCollectMsg(null);
    try {
      const results: CollectResult[] = await collectTopic(id);
      const total = results.reduce((s, r) => s + r.items_new, 0);
      const fails = results.filter((r) => r.errors?.length).length;
      setCollectMsg(`采集完成: ${total} 条新增${fails > 0 ? `, ${fails} 源失败` : ""}`);
      await load();
    } catch (e) {
      setCollectMsg(`采集失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setCollecting(null);
  };

  const handleGenerateReport = async (topicId: string, topicName: string) => {
    setGenerating(topicId);
    try {
      const topic = topics.find((t) => t.id === topicId);
      const defaultModel = models.find((m) => m.is_default);
      const report = await generateReport(topicId, {
        modelId: defaultModel?.id,
      });
      alert(`报告已生成: ${report.title}${report.status === "completed" ? "" : " (" + report.status + ")"}`);
    } catch (e) {
      alert(`报告生成失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setGenerating(null);
  };

  if (loading) return <div className="loading">加载主题...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>采集主题</h2>
          <p className="text-muted">主题定义采集的关键词、信息源和自动标签规则</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={14} /> 新建主题
        </button>
      </div>

      {collectMsg && (
        <div className="toast" onClick={() => setCollectMsg(null)}>
          {collectMsg}
        </div>
      )}

      <div className="card-list">
        {topics.map((t) => (
          <article key={t.id} className="card-item">
            <div className="card-item-header">
              <div>
                <h4>{t.name}</h4>
                <span className="text-muted">{t.id}</span>
                {t.description && <p className="text-muted small">{t.description}</p>}
              </div>
              <div className="card-item-actions">
                <span className={`badge ${t.is_active ? "badge--green" : "badge--gray"}`}>
                  {t.is_active ? "活跃" : "停用"}
                </span>
                {t.is_scheduled && (
                  <span className="badge badge--blue">定时: {t.schedule_cron}</span>
                )}
              </div>
            </div>

            <div className="card-item-meta">
              <div>
                <strong>关键词:</strong>{" "}
                {(t.keywords ?? []).map((kw) => (
                  <span key={kw} className="chip">{kw}</span>
                ))}
              </div>
              <div>
                <strong>信息源:</strong>{" "}
                {t.source_names?.length
                  ? t.source_names.map((nm) => (
                      <span key={nm} className="chip chip--blue">{nm}</span>
                    ))
                  : (t.source_ids?.length
                      ? t.source_ids.map((s) => (
                          <span key={s} className="chip chip--blue">{s}</span>
                        ))
                      : <span className="text-muted">所有活跃信息源</span>)}
              </div>
              {t.target_urls?.length ? (
                <div>
                  <strong><Target size={12} /> 目标URL:</strong>{" "}
                  {t.target_urls.map((u) => (
                    <span key={u} className="chip chip--green" title={u}>{u.slice(0, 50)}{u.length > 50 ? "..." : ""}</span>
                  ))}
                </div>
              ) : null}
              <div>
                <strong>自动标签规则:</strong>{" "}
                {t.auto_tag_rules?.length
                  ? t.auto_tag_rules.map((r) => (
                      <span key={r.tag} className="chip chip--pink">{r.keyword} → {r.tag}</span>
                    ))
                  : <span className="text-muted">无</span>}
              {(t as any).description_prompt && (
                <div className="text-muted small" style={{ marginTop: 4 }}>
                  <strong>描述提示:</strong> {(t as any).description_prompt}
                </div>
              )}
              </div>
              <div className="text-muted small">
                采集周期: {t.is_scheduled ? humanizeCron(t.schedule_cron) : "手动"}
                {" · "}自动报告: {t.auto_report
                  ? <span className="badge badge--green">开启</span>
                  : <span className="text-muted">关闭</span>}
              </div>
              <div className="text-muted small">
                累计采集: {t.total_items_collected} 条
                {t.last_run_at && <> · 最后运行: {new Date(t.last_run_at).toLocaleString("zh")}</>}
              </div>
            </div>

            <div className="card-item-footer">
              <button type="button" className="btn btn-sm btn-primary" onClick={() => handleCollect(t.id)} disabled={collecting === t.id}>
                <RefreshCw size={12} className={collecting === t.id ? "spin" : ""} />
                {collecting === t.id ? "采集中..." : "立即采集"}
              </button>
              <button type="button" className="btn btn-sm btn-secondary" onClick={() => handleGenerateReport(t.id, t.name)}
                disabled={generating === t.id} title={models.length === 0 ? "请先在模型配置页面添加AI模型" : "生成智能分析报告"}>
                <BrainCircuit size={12} className={generating === t.id ? "spin" : ""} />
                {generating === t.id ? "生成中..." : "生成报告"}
              </button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(t)}>
                <Edit3 size={12} /> 编辑
              </button>
              <button type="button" className="btn btn-sm btn-danger" onClick={() => handleDelete(t.id)}>
                <Trash2 size={12} /> 删除
              </button>
            </div>
          </article>
        ))}
        {topics.length === 0 && (
          <div className="empty">暂无主题。点击"新建主题"创建第一个采集主题。</div>
        )}
      </div>

      {/* Create / Edit modal */}
      {(showCreate || editing) && (
        <TopicForm
          topic={editing}
          sources={sources}
          models={models}
          categories={categories}
          onSave={async (data) => {
            if (editing) {
              await updateTopic(editing.id, data);
            } else {
              await createTopic(data as Topic);
            }
            setShowCreate(false);
            setEditing(null);
            await load();
          }}
          onClose={() => { setShowCreate(false); setEditing(null); }}
        />
      )}
    </div>
  );
}

// ── Topic form ───────────────────────────────────────────────────────────────

