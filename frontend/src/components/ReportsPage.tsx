import { useEffect, useState, useCallback } from "react";
import { FileText, Trash2, RefreshCw, Eye, Download, BrainCircuit } from "lucide-react";
import { fetchReports, fetchTopics, fetchModels, generateReport, deleteReport, fetchBatches, batchGenerateReports, exportReport, downloadReportUrl, listAvailableModels } from "../api";
import type { Report, Topic, ModelConfig } from "../types";

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
  // Collection period controls
  const [batchOptions, setBatchOptions] = useState<{batch_id: string; label: string; run_id: string}[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState("");
  // Batch generation
  const [batchTopicIds, setBatchTopicIds] = useState<string[]>([]);
  // Batch source: 'all' = all data, 'selected' = specific batches
  const [batchSourceMode, setBatchSourceMode] = useState<'all' | 'selected'>('all');
  // Per-topic batch data: {topic_id: {batch_id: {label, run_id}}}
  const [topicBatchMeta, setTopicBatchMeta] = useState<Record<string, Record<string, {label: string; run_id: string}>>>({});
  // Selected batch_ids per topic: {topic_id: string[]}
  const [topicBatchSelections, setTopicBatchSelections] = useState<Record<string, string[]>>({});
  const [batchSubMode, setBatchSubMode] = useState<'per_batch' | 'combined'>('per_batch');

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
      // For each Ollama model, fetch its locally available models
      setOllamaModels({});
      const ollamaConfigs = m.filter(mdl => mdl.provider === 'ollama' && mdl.is_active);
      if (ollamaConfigs.length > 0) {
        const results: Record<string, string[]> = {};
        await Promise.all(ollamaConfigs.map(async (mdl) => {
          try {
            const res = await listAvailableModels(mdl.id);
            if (res.success && res.models.length > 0) {
              results[mdl.id] = res.models;
            }
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
    if (idx !== -1) {
      return { modelId: value.slice(0, idx), modelNameOverride: value.slice(idx + 2) };
    }
    return { modelId: value, modelNameOverride: undefined };
  };

  // Load batches whenever the selected topic changes.
  useEffect(() => {
    setSelectedBatchId("");
    if (!selectedTopic) { setBatchOptions([]); return; }
    let active = true;
    fetchBatches(selectedTopic, 20)
      .then((bs) => {
        if (!active) return;
        const opts = bs.map((b) => ({
          batch_id: b.batch_id,
          label: b.batch_label || b.topic_name || "采集",
          run_id: b.runs?.[0]?.id || "",
        }));
        setBatchOptions(opts);
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
        collectionRunId: selectedBatchId ? (batchOptions.find(b=>b.batch_id===selectedBatchId)?.run_id || undefined) : undefined,
      });
      setGenMsg(`报告生成${report.status === "completed" ? "完成" : report.status === "failed" ? "失败" : "中"}：${report.title}`);
      await load();
    } catch (e) {
      setGenMsg(`生成失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setGenerating(false);
  };

  const toggleBatchTopic = (id: string) => {
    setBatchTopicIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleDelete = async (id: string) => {
    if (!confirm(`删除此报告？`)) return;
    try { await deleteReport(id); setReports((p) => p.filter((r) => r.id !== id)); }
    catch (e) { alert(e instanceof Error ? e.message : "删除失败"); }
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
          <p className="text-muted">
            基于采集到的信息，使用 AI 模型自动生成综合分析报告。
          </p>
        </div>
      </div>

      {/* Generate controls */}
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
          <button type="button" className="btn btn-primary" onClick={handleGenerate} disabled={generating || !selectedTopic} style={{ alignSelf: "flex-end" }}>
            <BrainCircuit size={14} className={generating ? "spin" : ""} />
            {generating ? "生成中..." : "立即生成报告"}
          </button>
        </div>

        {/* Batch generation */}
        <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--line-light)" }}>
          <h3 style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: 8 }}>批量生成 (多主题)</h3>
          <div style={{ marginBottom: 10, display: "flex", gap: 16, alignItems: "center", fontSize: "0.82rem" }}>
            <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
              <input type="radio" name="batch-source" checked={batchSourceMode === 'all'} onChange={() => setBatchSourceMode('all')} style={{ accentColor: "var(--accent)" }} />
              所选主题的全部信息
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
              <input type="radio" name="batch-source" checked={batchSourceMode === 'selected'} onChange={async () => {
                setBatchSourceMode('selected');
                // Load batches for all currently selected topics
                const meta: Record<string, Record<string, {label:string;run_id:string}>> = {};
                for (const tid of batchTopicIds.length ? batchTopicIds : topics.map(t=>t.id)) {
                  try {
                    const bs = await fetchBatches(tid, 10);
                    const map: Record<string, {label:string;run_id:string}> = {};
                    for (const b of bs) {
                      const lid = b.runs?.[0]?.id || "";
                      if (lid) map[b.batch_id] = {label: b.batch_label || tid, run_id: lid};
                    }
                    if (Object.keys(map).length) meta[tid] = map;
                  } catch {}
                }
                setTopicBatchMeta(meta);
              }} style={{ accentColor: "var(--accent)" }} />
              仅使用指定批次
            </label>
          </div>
          {batchSourceMode === 'selected' && (
            <div style={{ marginBottom: 10, display: "flex", gap: 12, alignItems: "center", fontSize: "0.8rem" }}>
              <span className="text-muted">生成方式:</span>
              <label style={{ display: "flex", alignItems: "center", gap: 3, cursor: "pointer" }}>
                <input type="radio" name="batch-sub-mode" checked={batchSubMode === 'per_batch'} onChange={() => setBatchSubMode('per_batch')} style={{ accentColor: "var(--accent)" }} />
                按批次分别生成
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 3, cursor: "pointer" }}>
                <input type="radio" name="batch-sub-mode" checked={batchSubMode === 'combined'} onChange={() => setBatchSubMode('combined')} style={{ accentColor: "var(--accent)" }} />
                合并为一份报告
              </label>
              <span className="text-muted small">{batchSubMode === 'per_batch' ? "每个选中批次各生成一份报告" : "同一主题的所有选中批次合并为一份"}</span>
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {topics.map((t) => (
              <div key={t.id}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: "0.85rem", padding: "4px 0" }}>
                  <input type="checkbox" checked={batchTopicIds.includes(t.id)} onChange={() => {
                    toggleBatchTopic(t.id);
                    if (batchSourceMode === 'selected') {
                      // Load batches for this topic
                      fetchBatches(t.id, 10).then(bs => {
                        const map: Record<string, {label:string;run_id:string}> = {};
                        for (const b of bs) {
                          const lid = b.runs?.[0]?.id || "";
                          if (lid) map[b.batch_id] = {label: b.batch_label || t.id, run_id: lid};
                        }
                        setTopicBatchMeta(prev => ({...prev, [t.id]: map}));
                      }).catch(() => {});
                    }
                  }} style={{ accentColor: "var(--accent)" }} />
                  <strong>{t.name}</strong>
                  <span className="text-muted small">({t.total_items_collected} 条)</span>
                </label>
                {batchTopicIds.includes(t.id) && batchSourceMode === 'selected' && topicBatchMeta[t.id] && (
                  <div style={{ marginLeft: 26, marginBottom: 4 }}>
                    {Object.entries(topicBatchMeta[t.id]).map(([bid, info]) => (
                      <label key={bid} style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer", fontSize: "0.78rem", padding: "2px 0", color: "var(--ink)" }}>
                        <input type="checkbox" checked={(topicBatchSelections[t.id] || []).includes(bid)}
                          onChange={() => {
                            setTopicBatchSelections(prev => {
                              const cur = prev[t.id] || [];
                              const next = cur.includes(bid) ? cur.filter(x => x !== bid) : [...cur, bid];
                              return {...prev, [t.id]: next};
                            });
                          }} style={{ accentColor: "var(--accent)" }} />
                        {info.label}
                      </label>
                    ))}
                    {Object.keys(topicBatchMeta[t.id]).length === 0 && (
                      <span className="text-muted small" style={{ marginLeft: 4 }}>暂无批次数据</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          <button type="button" className="btn btn-secondary" style={{ marginTop: 10 }} onClick={async () => {
            if (batchTopicIds.length === 0) { alert("请至少选择一个主题"); return; }
            setGenerating(true);
            setGenMsg(null);
            const { modelId: batchModelId, modelNameOverride: batchModelName } = parseModelSelection(selectedModel);
            try {
              if (batchSourceMode === 'all') {
                // All data mode: one report per topic
                const res = await batchGenerateReports(batchTopicIds, batchModelId || undefined, undefined, batchModelName);
                setGenMsg(`批量生成完成：成功 ${res.results.length} 份，失败 ${res.failed} 份`);
              } else if (batchSourceMode === 'selected' && batchSubMode === 'combined') {
                // Selected batches combined: each topic gets one report with all selected run_ids
                const runIdsList = batchTopicIds.map(tid => {
                  const sels = topicBatchSelections[tid] || [];
                  return sels.map(bid => topicBatchMeta[tid]?.[bid]?.run_id).filter(Boolean) as string[];
                });
                // Only include topics that have at least one selected batch
                const activeTopics = batchTopicIds.filter((_, i) => runIdsList[i].length > 0);
                const activeRunIdsList = runIdsList.filter(r => r.length > 0);
                if (activeTopics.length === 0) { alert("请为至少一个主题选择批次"); setGenerating(false); return; }
                const res = await batchGenerateReports(activeTopics, batchModelId || undefined, undefined, batchModelName, activeRunIdsList);
                setGenMsg(`合并生成完成：成功 ${res.results.length} 份，失败 ${res.failed} 份`);
              } else {
                // Per-batch mode: one report per (topic, selected_batch)
                const tasks: { topicId: string; runId: string | undefined; label: string }[] = [];
                for (const tid of batchTopicIds) {
                  const sels = topicBatchSelections[tid] || [];
                  const meta = topicBatchMeta[tid] || {};
                  if (sels.length === 0) {
                    // No batches selected for this topic — generate one report for all data
                    tasks.push({ topicId: tid, runId: undefined, label: tid });
                  } else {
                    for (const bid of sels) {
                      tasks.push({ topicId: tid, runId: meta[bid]?.run_id, label: meta[bid]?.label || tid });
                    }
                  }
                }
                if (tasks.length === 0) { alert("请至少选择一个批次"); setGenerating(false); return; }
                const results = await Promise.all(tasks.map(t => generateReport(t.topicId, {
                  modelId: batchModelId || undefined,
                  modelNameOverride: batchModelName,
                  collectionRunId: t.runId || undefined,
                })));
                const successCount = results.filter(r => r.status !== "failed").length;
                const failCount = results.filter(r => r.status === "failed").length;
                setGenMsg(`按批生成完成：成功 ${successCount} 份，失败 ${failCount} 份`);
              }
              setBatchTopicIds([]);
              setTopicBatchSelections({});
              await load();
            } catch (e) {
              setGenMsg(`生成失败: ${e instanceof Error ? e.message : "未知错误"}`);
            }
            setGenerating(false);
          }} disabled={generating || batchTopicIds.length === 0}>
            <BrainCircuit size={14} className={generating ? "spin" : ""} />
            {generating ? "生成中..." : `批量生成 (${batchTopicIds.length})`}
          </button>
        </div>

        {genMsg && <div className="toast" style={{ marginTop: 12 }} onClick={() => setGenMsg(null)}>{genMsg}</div>}
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

      {/* Report viewer modal */}
      {viewing && (
        <div className="modal-overlay" onClick={() => setViewing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 800, maxWidth: "95vw" }}>
            <div className="modal-header-with-actions">
              <h3>{viewing.title}</h3>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => {
                  const blob = new Blob([viewing.content || ""], { type: "text/markdown" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url; a.download = `${viewing.title}.md`; a.click();
                  URL.revokeObjectURL(url);
                }}>
                  <Download size={12} /> 下载
                </button>
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => setViewing(null)}>关闭</button>
              </div>
            </div>
            <div className="report-meta" style={{ fontSize: "0.8rem", color: "var(--ink-muted)", marginBottom: 16, padding: "8px 0", borderBottom: "1px solid var(--line-light)" }}>
              基于 {viewing.item_count} 条采集信息
              {viewing.generated_at && <> · {new Date(viewing.generated_at).toLocaleString("zh")}</>}
              {viewing.tokens_used > 0 && <> · 使用 {viewing.tokens_used} tokens</>}
            </div>
            <div className="report-content" style={{ fontSize: "0.85rem", lineHeight: 1.7, maxHeight: "60vh", overflowY: "auto" }}>
              {viewing.content ? (
                <RenderMarkdown content={viewing.content} />
              ) : (
                <p className="text-muted">（暂无内容）</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function RenderMarkdown({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements = [];
  let inCode = false;
  let codeBlock: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("```")) {
      if (inCode) {
        elements.push(<pre key={i} className="md-code-block"><code>{codeBlock.join("\n")}</code></pre>);
        codeBlock = [];
        inCode = false;
      } else {
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeBlock.push(line);
      continue;
    }

    if (line.startsWith("## ")) {
      elements.push(<h4 key={i} style={{ margin: "16px 0 8px", fontSize: "1rem", fontWeight: 700, color: "var(--accent)" }}>{line.slice(3)}</h4>);
    } else if (line.startsWith("### ")) {
      elements.push(<h5 key={i} style={{ margin: "12px 0 6px", fontSize: "0.9rem", fontWeight: 600 }}>{line.slice(4)}</h5>);
    } else if (line.startsWith("**") && line.endsWith("**")) {
      elements.push(<p key={i} style={{ fontWeight: 600, margin: "8px 0 4px" }}>{line.replace(/\*\*/g, "")}</p>);
    } else if (line.match(/^\d\.\s/)) {
      elements.push(<p key={i} style={{ margin: "2px 0", paddingLeft: 12 }}>{line}</p>);
    } else if (line.startsWith("- ")) {
      elements.push(<p key={i} style={{ margin: "2px 0", paddingLeft: 12, color: "var(--ink-muted)" }}>{line}</p>);
    } else if (line.trim() === "") {
      elements.push(<div key={i} style={{ height: 4 }} />);
    } else {
      const rendered = line
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\[参见条目(\d+)\]/g, '<span style="color:var(--accent);font-size:0.8em">[参见条目$1]</span>');
      elements.push(<p key={i} style={{ margin: "4px 0" }} dangerouslySetInnerHTML={{ __html: rendered }} />);
    }
  }

  return <>{elements}</>;
}
