import { useEffect, useState, useCallback } from "react";
import { Plus, RefreshCw, Trash2, Edit3, Globe, Target, FileText, BrainCircuit } from "lucide-react";
import { fetchTopics, createTopic, deleteTopic, updateTopic, collectTopic, generateReport, fetchModels, fetchSources } from "../api";
import type { Topic, CollectResult, ModelConfig, Source } from "../types";
import { DESCRIPTION_PROMPT_TEMPLATES, KEYWORD_WEIGHT_TEMPLATES } from "../templates";

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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, ms, srcs] = await Promise.all([
        fetchTopics(),
        fetchModels().catch(() => []),
        fetchSources().catch(() => []),
      ]);
      setTopics(t);
      setModels(ms);
      setSources(srcs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleDelete = async (id: string) => {
    if (!confirm(`删除主题 "${id}"？`)) return;
    try {
      await deleteTopic(id);
      setTopics((prev) => prev.filter((t) => t.id !== id));
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
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
        // Auto-associate the latest collection batch when available.
        collectionRunId: topic?.last_collection_run_id ?? undefined,
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

type TopicFormProps = {
  topic: Topic | null;   // null = create mode
  sources: Source[];
  models: ModelConfig[];
  onSave: (data: Partial<Topic>) => Promise<void>;
  onClose: () => void;
};

function TopicForm({ topic, sources, models, onSave, onClose }: TopicFormProps) {
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState(topic?.name ?? "");
  const [desc, setDesc] = useState(topic?.description ?? "");
  const [keywords, setKeywords] = useState((topic?.keywords ?? []).join(", "));
  const [keywordTags, setKeywordTags] = useState(
    ((topic as any)?.keyword_tags ?? []).map((kt: any) => `${kt.keyword}:${kt.weight}`).join("\n")
  );
  const [descriptionPrompt, setDescriptionPrompt] = useState((topic as any)?.description_prompt ?? "");
  const [collectWindowDays, setCollectWindowDays] = useState<number>((topic as any)?.collect_window_days ?? 7);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>(topic?.source_ids ?? []);
  const [targetUrls, setTargetUrls] = useState((topic?.target_urls ?? []).join("\n"));
  const [cron, setCron] = useState(topic?.schedule_cron ?? "");
  const [autoReport, setAutoReport] = useState(topic?.auto_report ?? false);
  const [autoReportModelId, setAutoReportModelId] = useState(
    topic?.auto_report_model_id ?? models.find((m) => m.is_default)?.id ?? ""
  );
  const [autoTags, setAutoTags] = useState(
    (topic?.auto_tag_rules ?? []).map((r) => `${r.keyword}:${r.tag}`).join(", ")
  );

  const toggleSource = (sid: string) => {
    setSelectedSourceIds((prev) =>
      prev.includes(sid) ? prev.filter((s) => s !== sid) : [...prev, sid]
    );
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({
        name,
        description: desc || null,
        keywords: keywords.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
        keyword_tags: keywordTags ? keywordTags.split(/\r?\n/).map((s: string) => {
          const [kw, w] = s.split(/[:：]/);
          return { keyword: kw?.trim() || "", weight: parseFloat(w?.trim() || "1") || 1 };
        }).filter((r: { keyword: string; weight: number }) => r.keyword) : null,
        description_prompt: descriptionPrompt || null,
        source_ids: selectedSourceIds.length ? selectedSourceIds : null,
        collect_window_days: Number.isFinite(collectWindowDays) ? collectWindowDays : 7,
        target_urls: targetUrls ? targetUrls.split(/\r?\n/).map((s) => s.trim()).filter(Boolean) : null,
        schedule_cron: cron || null,
        is_scheduled: !!cron,
        auto_report: autoReport,
        auto_report_model_id: autoReport ? (autoReportModelId || null) : null,
        auto_tag_rules: autoTags ? autoTags.split(/[,，]/).map((s) => {
          const [kw, tag] = s.trim().split(/[:：]/);
          return { keyword: kw?.trim() ?? "", tag: tag?.trim() ?? "" };
        }).filter((r) => r.keyword && r.tag) : null,
      });
    } catch (e) {
      alert(e instanceof Error ? e.message : "保存失败");
    }
    setSaving(false);
  };

  const activeSources = sources.filter((s) => s.is_active);
  const allSelected = activeSources.length > 0 && activeSources.every((s) => selectedSourceIds.includes(s.id));
  const toggleSelectAll = () => {
    setSelectedSourceIds(allSelected ? [] : activeSources.map((s) => s.id));
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{topic ? "编辑主题" : "新建主题"}</h3>
        <div className="form-grid">
          {topic && (
            <label>ID <span className="chip">{topic.id}</span></label>
          )}
          <label>名称 <input value={name} onChange={(e) => setName(e.target.value)} placeholder="我的采集主题" /></label>
          <label className="span-2">描述 <input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="简要描述..." /></label>
          <label className="span-2">关键词 (逗号分隔) <input value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="贸易政策, 关税, RCEP" /></label>

          <label className="span-2">绑定信息源 (不选=所有活跃信息源)
            <div className="checkbox-grid">
              {activeSources.length === 0 && <span className="text-muted small">暂无活跃信息源</span>}
              {activeSources.length > 0 && (
                <label className="checkbox-item checkbox-item--all">
                  <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} />
                  {" "}<strong>{allSelected ? "取消全选" : "全选"}</strong>
                </label>
              )}
              {activeSources.map((s) => (
                <label key={s.id} className="checkbox-item">
                  <input type="checkbox" checked={selectedSourceIds.includes(s.id)} onChange={() => toggleSource(s.id)} />
                  {" "}{s.name}
                </label>
              ))}
            </div>
          </label>

          <label>Cron表达式 <input value={cron} onChange={(e) => setCron(e.target.value)} placeholder="0 8 * * * (每日8点)" /></label>

          <label>采集时间范围 (天数)
            <input type="number" min={0} value={collectWindowDays}
              onChange={(e) => setCollectWindowDays(parseInt(e.target.value, 10) || 0)}
              placeholder="7" />
            <span className="text-muted small">只采集发布时间在该天数内的信息，0=不限制</span>
          </label>

          <label className="span-2">自动报告
            <div className="checkbox-item">
              <input type="checkbox" checked={autoReport} onChange={(e) => setAutoReport(e.target.checked)} />
              {" "}采集完成后自动生成报告
            </div>
            {autoReport && (
              <select value={autoReportModelId} onChange={(e) => setAutoReportModelId(e.target.value)}>
                <option value="">(使用默认模型)</option>
                {models.filter((m) => m.is_active).map((m) => (
                  <option key={m.id} value={m.id}>{m.name}{m.is_default ? " ★" : ""}</option>
                ))}
              </select>
            )}
          </label>

          <label className="span-2">加权关键词 (每行一个, keyword:权重)
            <div className="template-row">
              <select className="template-select" value="" onChange={(e) => {
                const tpl = KEYWORD_WEIGHT_TEMPLATES.find((t) => t.label === e.target.value);
                if (tpl) setKeywordTags((prev: string) => (prev.trim() ? prev.trimEnd() + "\n" + tpl.value : tpl.value));
              }}>
                <option value="">插入模板...</option>
                {KEYWORD_WEIGHT_TEMPLATES.map((t) => (
                  <option key={t.label} value={t.label}>{t.label}</option>
                ))}
              </select>
            </div>
            <textarea rows={3} value={keywordTags} onChange={(e) => setKeywordTags(e.target.value)}
              placeholder="关税:1.0&#10;贸易壁垒:0.8&#10;供应链:0.6" />
            <span className="text-muted small">权重范围 0.1~1.0，越高表示关键词越重要</span>
          </label>

          <label className="span-2">描述提示词
            <div className="template-row">
              <select className="template-select" value="" onChange={(e) => {
                const tpl = DESCRIPTION_PROMPT_TEMPLATES.find((t) => t.label === e.target.value);
                if (tpl) setDescriptionPrompt(tpl.value);
              }}>
                <option value="">选择模板...</option>
                {DESCRIPTION_PROMPT_TEMPLATES.map((t) => (
                  <option key={t.label} value={t.label}>{t.label}</option>
                ))}
              </select>
            </div>
            <textarea rows={3} value={descriptionPrompt} onChange={(e) => setDescriptionPrompt(e.target.value)}
              placeholder="例如：监控全球主要经济体的贸易政策变化、关税调整、贸易协定进展，重点关注影响中国出口的措施" />
            <span className="text-muted small">用自然语言描述这个主题的关注重点和需求，AI 报告生成时会参考此描述</span>
          </label>

          <label className="span-2">目标URL (每行一个) <textarea rows={2} value={targetUrls} onChange={(e) => setTargetUrls(e.target.value)} placeholder="https://example.com/page&#10;https://example.com/other" /></label>
          <label className="span-2">自动标签 (keyword:tag, 逗号分隔) <input value={autoTags} onChange={(e) => setAutoTags(e.target.value)} placeholder="关税:event:tariff, 电池:product:battery" /></label>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saving || !name}>
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
