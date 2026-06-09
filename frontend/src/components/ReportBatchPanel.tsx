import { useState } from "react";
import { BrainCircuit } from "lucide-react";
import { fetchBatches, generateReport, batchGenerateReports } from "../api";
import type { Report, Topic, ModelConfig } from "../types";

interface Props {
  topics: Topic[];
  models: ModelConfig[];
  ollamaModels: Record<string, string[]>;
  generating: boolean;
  onGeneratingChange: (v: boolean) => void;
  onGenerated: () => void;
  genMsg: string | null;
  onGenMsg: (msg: string | null) => void;
}

type BatchSourceMode = "all" | "selected";

export function ReportBatchPanel({
  topics, models, ollamaModels, generating,
  onGeneratingChange, onGenerated, genMsg, onGenMsg,
}: Props) {
  const [batchTopicIds, setBatchTopicIds] = useState<string[]>([]);
  const [batchSourceMode, setBatchSourceMode] = useState<BatchSourceMode>("all");
  const [topicBatchMeta, setTopicBatchMeta] = useState<
    Record<string, Record<string, { label: string; run_id: string }>>
  >({});
  const [topicBatchSelections, setTopicBatchSelections] = useState<Record<string, string[]>>({});
  const [batchSubMode, setBatchSubMode] = useState<"per_batch" | "combined">("per_batch");
  const [batchModel, setBatchModel] = useState("");

  const parseModel = (v: string) => {
    if (!v) return { modelId: undefined, modelNameOverride: undefined };
    const idx = v.indexOf("@@");
    return idx !== -1
      ? { modelId: v.slice(0, idx) as string | undefined, modelNameOverride: v.slice(idx + 2) as string | undefined }
      : { modelId: v as string | undefined, modelNameOverride: undefined };
  };

  const toggleTopic = (id: string) =>
    setBatchTopicIds((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  const loadMeta = async (tids: string[]) => {
    const meta: Record<string, Record<string, { label: string; run_id: string }>> = {};
    for (const tid of tids) {
      try {
        const bs = await fetchBatches(tid, 10);
        const map: Record<string, { label: string; run_id: string }> = {};
        for (const b of bs) {
          const lid = b.runs?.[0]?.id || "";
          if (lid) map[b.batch_id] = { label: b.batch_label || tid, run_id: lid };
        }
        if (Object.keys(map).length) meta[tid] = map;
      } catch {}
    }
    setTopicBatchMeta(meta);
  };

  const handleGenerate = async () => {
    if (!batchTopicIds.length) return;
    onGeneratingChange(true);
    onGenMsg(null);
    try {
      if (batchSourceMode === "all") {
        const results = await Promise.all(batchTopicIds.map((tid) => generateReport(tid, {})));
        const ok = results.filter((r: Report) => r.status !== "failed").length;
        const failed = results.length - ok;
        onGenMsg(`批量生成完成：成功 ${ok} 份${failed > 0 ? `，失败 ${failed} 份` : ""}`);
      } else if (batchSubMode === "per_batch") {
        const { modelId, modelNameOverride } = parseModel(batchModel);
        const tasks: Promise<Report>[] = [];
        for (const tid of batchTopicIds) {
          for (const bid of topicBatchSelections[tid] || []) {
            const t = topicBatchMeta[tid]?.[bid];
            if (t?.run_id) tasks.push(generateReport(tid, { modelId, modelNameOverride, collectionRunId: t.run_id }));
          }
        }
        if (!tasks.length) { onGenMsg("未选择任何批次"); onGeneratingChange(false); return; }
        const results = await Promise.all(tasks);
        const ok = results.filter((r) => r.status !== "failed").length;
        onGenMsg(`按批生成完成：成功 ${ok} 份，失败 ${results.length - ok} 份`);
      } else {
        const { modelId, modelNameOverride } = parseModel(batchModel);
        const runIdsPerTopic = batchTopicIds.map((tid) =>
          (topicBatchSelections[tid] || []).map((bid) => topicBatchMeta[tid]?.[bid]?.run_id).filter(Boolean) as string[]
        );
        const res = await batchGenerateReports(batchTopicIds, modelId, undefined, modelNameOverride, runIdsPerTopic);
        onGenMsg(`批量生成完成：成功 ${res.results.length} 份，失败 ${res.failed} 份`);
      }
      setBatchTopicIds([]);
      setTopicBatchSelections({});
      onGenerated();
    } catch (e) { onGenMsg(`生成失败: ${e instanceof Error ? e.message : "未知错误"}`); }
    onGeneratingChange(false);
  };

  const activeModels = models.filter((m) => m.is_active);

  // Styles as plain objects for brevity
  const s = {
    section: { marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--line-light)" },
    row: { marginBottom: 10, display: "flex", gap: 16, alignItems: "center", fontSize: "0.82rem" } as React.CSSProperties,
    radio: { display: "flex", alignItems: "center", gap: 4, cursor: "pointer" } as React.CSSProperties,
    accent: { accentColor: "var(--accent)" },
    h3: { fontSize: "0.85rem", fontWeight: 600, marginBottom: 8 },
    list: { display: "flex", flexDirection: "column" as const, gap: 8 },
  };

  return (
    <div style={s.section}>
      <h3 style={s.h3}>批量生成 (多主题)</h3>

      <div style={s.row}>
        <label style={s.radio}>
          <input type="radio" name="bs" checked={batchSourceMode === "all"} onChange={() => setBatchSourceMode("all")} style={s.accent} />
          所选主题的全部信息
        </label>
        <label style={s.radio}>
          <input type="radio" name="bs" checked={batchSourceMode === "selected"} onChange={async () => {
            setBatchSourceMode("selected");
            await loadMeta(batchTopicIds.length ? batchTopicIds : topics.map((t) => t.id));
          }} style={s.accent} />
          仅使用指定批次
        </label>
      </div>

      {batchSourceMode === "selected" && (
        <div style={{ marginBottom: 10, display: "flex", gap: 12, alignItems: "center", fontSize: "0.8rem" }}>
          <span className="text-muted">生成方式:</span>
          {(["per_batch", "combined"] as const).map((m) => (
            <label key={m} style={s.radio}>
              <input type="radio" name="bsm" checked={batchSubMode === m} onChange={() => setBatchSubMode(m)} style={s.accent} />
              {m === "per_batch" ? "按批次分别生成" : "合并为一份报告"}
            </label>
          ))}
          <span className="text-muted small">
            {batchSubMode === "per_batch" ? "每个选中批次各生成一份" : "同主题批次合并为一份"}
          </span>
        </div>
      )}

      <div style={s.list}>
        {topics.map((t) => (
          <div key={t.id}>
            <label style={{ ...s.radio, fontSize: "0.85rem", padding: "4px 0" }}>
              <input type="checkbox" checked={batchTopicIds.includes(t.id)} onChange={() => {
                toggleTopic(t.id);
                if (batchSourceMode === "selected") {
                  fetchBatches(t.id, 10).then((bs) => {
                    const map: Record<string, { label: string; run_id: string }> = {};
                    for (const b of bs) {
                      const lid = b.runs?.[0]?.id || "";
                      if (lid) map[b.batch_id] = { label: b.batch_label || t.id, run_id: lid };
                    }
                    setTopicBatchMeta((prev) => ({ ...prev, [t.id]: map }));
                  }).catch(() => {});
                }
              }} style={s.accent} />
              <span>{t.name}<span className="text-muted small" style={{ marginLeft: 6 }}>({t.total_items_collected} 条)</span></span>
            </label>
            {batchSourceMode === "selected" && batchTopicIds.includes(t.id) && topicBatchMeta[t.id] && (
              <div style={{ marginLeft: 24, marginBottom: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
                {Object.entries(topicBatchMeta[t.id]).map(([bid, meta]) => {
                  const sel = (topicBatchSelections[t.id] || []).includes(bid);
                  return (
                    <label key={bid} style={{
                      display: "flex", alignItems: "center", gap: 3, fontSize: "0.75rem", cursor: "pointer",
                      padding: "2px 6px", borderRadius: 4,
                      background: sel ? "var(--accent-bg)" : "var(--surface)",
                      border: "1px solid var(--line)",
                    }}>
                      <input type="checkbox" checked={sel} onChange={() => {
                        setTopicBatchSelections((prev) => {
                          const cur = prev[t.id] || [];
                          return { ...prev, [t.id]: cur.includes(bid) ? cur.filter((x) => x !== bid) : [...cur, bid] };
                        });
                      }} style={{ accentColor: "var(--accent)", width: 12, height: 12 }} />
                      {meta.label}
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
        {activeModels.length > 0 && (
          <div className="gen-field" style={{ minWidth: 200 }}>
            <label className="gen-label">AI 模型</label>
            <select value={batchModel} onChange={(e) => setBatchModel(e.target.value)} style={{ flex: 1 }}>
              <option value="">默认模型</option>
              {activeModels.flatMap((m) => {
                const avail = ollamaModels[m.id];
                if (m.provider === "ollama" && avail?.length) {
                  return avail.map((mn) => <option key={`${m.id}@@${mn}`} value={`${m.id}@@${mn}`}>{m.name} / {mn}</option>);
                }
                return <option key={m.id} value={m.id}>{m.name} ({m.provider}/{m.model_name})</option>;
              })}
            </select>
          </div>
        )}
        <button type="button" className="btn btn-primary" onClick={handleGenerate}
          disabled={generating || !batchTopicIds.length}>
          <BrainCircuit size={14} className={generating ? "spin" : ""} />
          {generating ? "生成中..." : `批量生成 (${batchTopicIds.length})`}
        </button>
      </div>

      {genMsg && <div className="toast" style={{ marginTop: 12 }} onClick={() => onGenMsg(null)}>{genMsg}</div>}
      {!models.length && <div className="text-red small" style={{ marginTop: 8 }}>尚未配置 AI 模型。请先在"模型配置"页面添加一个模型。</div>}
    </div>
  );
}
