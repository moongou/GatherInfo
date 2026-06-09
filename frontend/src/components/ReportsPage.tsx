import { useEffect, useState, useCallback } from "react";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import { FileText, Trash2, Eye, Download, BrainCircuit } from "lucide-react";
import { fetchReports, fetchTopics, fetchModels, generateReport, deleteReport, fetchBatches, exportReport, downloadReportUrl, listAvailableModels } from "../api";
import type { Report, Topic, ModelConfig } from "../types";
import { ReportViewerModal } from "./ReportViewerModal";
import { ReportBatchPanel } from "./ReportBatchPanel";

export function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [ollamaModels, setOllamaModels] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTopic, setSelectedTopic] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [generating, setGenerating] = useState(false);
  const [genMsg, setGenMsg] = useState<string | null>(null);
  const [viewing, setViewing] = useState<Report | null>(null);
  const [batchOptions, setBatchOptions] = useState<{batch_id: string; label: string; run_id: string}[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{id: string; message: string} | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, t, m] = await Promise.all([
        fetchReports(selectedTopic || undefined),
        fetchTopics(),
        fetchModels(),
      ]);
      setReports(r.reports);
      setTopics(t);
      setModels(m);
      setError(null);
      setOllamaModels({});
      const ollamaConfigs = m.filter(mdl => mdl.provider === 'ollama' && mdl.is_active);
      if (ollamaConfigs.length > 0) {
        const results: Record<string, string[]> = {};
        await Promise.all(ollamaConfigs.map(async (mdl) => {
          try {
            const res = await listAvailableModels(mdl.id);
            if (res.success && res.models.length > 0) results[mdl.id] = res.models;
          } catch {}
        }));
        setOllamaModels(results);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "失败");
    }
    setLoading(false);
  }, [selectedTopic]);

  useEffect(() => { void load(); }, [load]);

  const parseModelSelection = (value: string): { modelId: string | undefined; modelNameOverride: string | undefined } => {
    if (!value) return { modelId: undefined, modelNameOverride: undefined };
    const idx = value.indexOf("@@");
    if (idx !== -1) return { modelId: value.slice(0, idx), modelNameOverride: value.slice(idx + 2) };
    return { modelId: value, modelNameOverride: undefined };
  };

  useEffect(() => {
    setSelectedBatchId("");
    if (!selectedTopic) { setBatchOptions([]); return; }
    let active = true;
    fetchBatches(selectedTopic, 20)
      .then((bs) => {
        if (!active) return;
        setBatchOptions(bs.map((b) => ({
          batch_id: b.batch_id,
          label: b.batch_label || b.topic_name || "采集",
          run_id: b.runs?.[0]?.id || "",
        })));
      })
      .catch(() => { if (active) setBatchOptions([]); });
    return () => { active = false; };
  }, [selectedTopic]);

  const handleGenerate = async () => {
    if (!selectedTopic) { alert("请先选择一个主题"); return; }
    setGenerating(true);
    setGenMsg(null);
    try {
      const { modelId, modelNameOverride } = parseModelSelection(selectedModel);
      const report = await generateReport(selectedTopic, {
        modelId,
        modelNameOverride,
        collectionRunId: selectedBatchId
          ? (batchOptions.find(b => b.batch_id === selectedBatchId)?.run_id || undefined)
          : undefined,
      });
      setGenMsg(`报告生成${report.status === "completed" ? "完成" : report.status === "failed" ? "失败" : "中"}：${report.title}`);
      await load();
    } catch (e) {
      setGenMsg(`生成失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setGenerating(false);
  };

  const handleDelete = (id: string) => {
    setDeleteTarget({ id, message: "删除此报告？" });
  };

  const executeDelete = async () => {
    if (!deleteTarget) return;
    const id = deleteTarget.id;
    try { await deleteReport(id); setReports((p) => p.filter((r) => r.id !== id)); }
    catch (e) { alert(e instanceof Error ? e.message : "删除失败"); }
    setDeleteTarget(null);
  };

  const [exportingId, setExportingId] = useState<string | null>(null);
  const handleExport = async (id: string) => {
    setExportingId(id);
    try {
      const updated = await exportReport(id);
      setReports((p) => p.map((r) => (r.id === id ? updated : r)));
    } catch (e) {
      alert(e instanceof Error ? e.message : "导出失败");
    }
    setExportingId(null);
  };

  if (loading) return <div className="loading">加载报告列表...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  const defaultModel = models.find((m) => m.is_default);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>智能报告</h2>
          <p className="text-muted">基于采集到的信息，使用 AI 模型自动生成综合分析报告。</p>
        </div>
      </div>

      {/* Single report generation */}
      <div className="gen-controls" style={{ background: "var(--surface-card)", border: "1px solid var(--line)", borderRadius: "var(--radius)", padding: 20, marginBottom: 16 }}>
        <h3 style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: 12 }}>生成新报告</h3>
        <div className="gen-controls-row">
          <div className="gen-field">
            <label className="gen-label">选择主题</label>
            <select value={selectedTopic} onChange={(e) => setSelectedTopic(e.target.value)} style={{ flex: 1 }}>
              <option value="">-- 请选择 --</option>
              {topics.map((t) => (
                <option key={t.id} value={t.id}>{t.name} ({t.total_items_collected} 条)</option>
              ))}
            </select>
          </div>
          <div className="gen-field">
            <label className="gen-label">AI 模型</label>
            <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} style={{ flex: 1 }}>
              <option value="">{defaultModel ? `默认: ${defaultModel.name}` : "-- 默认模型 --"}</option>
              {models.filter((m) => m.is_active).flatMap((m) => {
                const avail = ollamaModels[m.id];
                if (m.provider === 'ollama' && avail && avail.length > 0) {
                  return avail.map((modelName) => (
                    <option key={`${m.id}@@${modelName}`} value={`${m.id}@@${modelName}`}>
                      {m.name} / {modelName}{m.is_default ? " ⭐" : ""}
                    </option>
                  ));
                }
                return (
                  <option key={m.id} value={m.id}>{m.name} ({m.provider}/{m.model_name}){m.is_default ? " ⭐" : ""}</option>
                );
              })}
            </select>
          </div>
          <button type="button" className="btn btn-primary" onClick={handleGenerate} disabled={generating || !selectedTopic} style={{ alignSelf: "flex-end" }}>
            <BrainCircuit size={14} className={generating ? "spin" : ""} />
            {generating ? "生成中..." : "立即生成报告"}
          </button>
        </div>

        {/* Collection period scope */}
        <div className="gen-controls-row" style={{ marginTop: 12 }}>
          <div className="gen-field">
            <label className="gen-label" htmlFor="rpt-batch">采集批次</label>
            <select id="rpt-batch" value={selectedBatchId} onChange={(e) => setSelectedBatchId(e.target.value)} disabled={!selectedTopic} style={{ flex: 1 }}>
              <option value="">全部批次</option>
              {batchOptions.map((b) => (
                <option key={b.batch_id} value={b.batch_id}>{b.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Batch generation panel */}
        <ReportBatchPanel
          topics={topics}
          models={models}
          ollamaModels={ollamaModels}
          generating={generating}
          onGeneratingChange={setGenerating}
          onGenerated={load}
          genMsg={genMsg}
          onGenMsg={setGenMsg}
        />

        {models.length === 0 && (
          <div className="text-red small" style={{ marginTop: 8 }}>
            尚未配置 AI 模型。请先在"模型配置"页面添加一个模型。
          </div>
        )}
      </div>

      {/* Report list */}
      <div className="card-list">
        {reports.length === 0 ? (
          <div className="empty">
            <FileText size={24} style={{ opacity: 0.3, margin: "0 auto 8px" }} />
            <p>暂无报告。</p>
            <p className="text-muted small">选择一个主题，点击"立即生成报告"创建第一份智能分析报告。</p>
          </div>
        ) : reports.map((r) => (
          <article key={r.id} className="card-item">
            <div className="card-item-header">
              <div>
                <h4>{r.title}</h4>
                <span className="text-muted small">
                  {topics.find((t) => t.id === r.topic_id)?.name || r.topic_id}
                  {r.model_id && ` · 模型: ${models.find((m) => m.id === r.model_id)?.name || r.model_id}`}
                </span>
              </div>
              <div className="card-item-actions">
                <span className={`badge ${
                  r.status === "completed" ? "badge--green" :
                  r.status === "failed" ? "badge--gray" :
                  r.status === "generating" ? "badge--blue" : ""
                }`}>
                  {r.status === "completed" ? "已完成" :
                   r.status === "failed" ? "失败" :
                   r.status === "generating" ? "生成中" : "待处理"}
                </span>
              </div>
            </div>
            <div className="card-item-meta">
              <div className="text-muted small">
                {r.generated_at && <>生成于 {new Date(r.generated_at).toLocaleString("zh")}</>}
                {r.item_count > 0 && <> · 基于 {r.item_count} 条采集信息</>}
                {r.tokens_used > 0 && <> · 约 {r.tokens_used} tokens</>}
              </div>
              {r.summary && (
                <div className="report-summary-preview" style={{ fontSize: "0.82rem", color: "var(--ink-muted)", lineHeight: 1.5, marginTop: 4 }}>
                  {r.summary.slice(0, 200)}{r.summary.length > 200 ? "..." : ""}
                </div>
              )}
              {r.status === "failed" && r.error_log && (
                <div className="text-red small" style={{ marginTop: 4 }}>错误: {r.error_log}</div>
              )}
            </div>
            <div className="card-item-footer">
              <button type="button" className="btn btn-sm btn-primary" onClick={() => setViewing(r)} disabled={r.status !== "completed"}>
                <Eye size={12} /> 查看报告
              </button>
              {r.status === "completed" && r.output_files && Object.keys(r.output_files).length > 0 ? (
                Object.keys(r.output_files).map((fmt) => (
                  <a key={fmt} className="btn btn-sm btn-ghost" href={downloadReportUrl(r.id, fmt)} download>
                    <Download size={12} /> {fmt.toUpperCase()}
                  </a>
                ))
              ) : (
                r.status === "completed" && (
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => handleExport(r.id)} disabled={exportingId === r.id}>
                    <Download size={12} /> {exportingId === r.id ? "导出中…" : "导出文件"}
                  </button>
                )
              )}
              <button type="button" className="btn btn-sm btn-danger" onClick={() => handleDelete(r.id)}>
                <Trash2 size={12} /> 删除
              </button>
            </div>
          </article>
        ))}
      </div>

      {viewing && <ReportViewerModal report={viewing} onClose={() => setViewing(null)} />}

      <ConfirmDialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={executeDelete}
        title="删除报告"
        message={deleteTarget?.message || ""}
        variant="danger"
      />
    </div>
  );
}
