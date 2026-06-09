import { useState } from "react";
import { GitMerge, ArrowRight } from "lucide-react";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import type { Tag } from "../types";

interface Props {
  tags: Tag[];
  onMerge: (sourceId: string, targetId: string) => Promise<void>;
  onClose: () => void;
}

export function TagMergeDialog({ tags, onMerge, onClose }: Props) {
  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [merging, setMerging] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const sourceTag = tags.find((t) => t.id === sourceId);
  const targetTag = tags.find((t) => t.id === targetId);

  const handleMerge = async () => {
    if (!sourceId || !targetId) { setMsg("请选择源标签和目标标签"); return; }
    if (sourceId === targetId) { setMsg("源标签和目标标签不能相同"); return; }
    setShowConfirm(true);
  };

  const executeMerge = async () => {
    setShowConfirm(false);
    setMerging(true);
    setMsg(null);
    try {
      await onMerge(sourceId, targetId);
      setMsg("合并完成");
      setTimeout(onClose, 800);
    } catch (e) {
      setMsg(`合并失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setMerging(false);
  };

  const nsLabel = (ns: string) =>
    ({ category: "类别", region: "区域", commodity: "商品", country: "国家", product: "产品", event: "事件", regulation: "法规", sector: "行业" } as Record<string, string>)[ns] ?? ns;

  const tagLabel = (t: Tag) => t.label || t.value;

  return (
    <>
      <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 520, maxWidth: "95vw" }}>
        <h3><GitMerge size={16} style={{ verticalAlign: "middle", marginRight: 6 }} />合并标签</h3>
        <p className="text-muted small" style={{ marginBottom: 16 }}>
          源标签的所有条目关联将转移到目标标签，随后源标签被删除。
        </p>

        <div className="merge-row">
          <div style={{ flex: 1 }}>
            <label className="form-label">源标签（将被删除）</label>
            <select value={sourceId} onChange={(e) => setSourceId(e.target.value)} className="form-select">
              <option value="">选择源标签...</option>
              {tags.map((t) => (
                <option key={t.id} value={t.id} disabled={t.id === targetId}>
                  [{nsLabel(t.namespace)}] {tagLabel(t)} ({t.item_count}条)
                </option>
              ))}
            </select>
          </div>
          <ArrowRight size={20} style={{ marginTop: 22, color: "var(--muted)" }} />
          <div style={{ flex: 1 }}>
            <label className="form-label">目标标签（保留）</label>
            <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="form-select">
              <option value="">选择目标标签...</option>
              {tags.map((t) => (
                <option key={t.id} value={t.id} disabled={t.id === sourceId}>
                  [{nsLabel(t.namespace)}] {tagLabel(t)} ({t.item_count}条)
                </option>
              ))}
            </select>
          </div>
        </div>

        {sourceTag && targetTag && sourceId !== targetId && (
          <div className="merge-preview" style={{ marginTop: 16, padding: 12, background: "var(--surface)", borderRadius: "var(--radius)", fontSize: "0.82rem" }}>
            <p className="text-muted" style={{ margin: 0 }}>
              <strong>{tagLabel(sourceTag)}</strong> ({sourceTag.item_count}条) 
              {" → "}
              <strong>{tagLabel(targetTag)}</strong> ({targetTag.item_count}+{sourceTag.item_count}条)
            </p>
          </div>
        )}

        {msg && (
          <div className={`toast ${msg.includes("失败") ? "toast--error" : ""}`} style={{ marginTop: 8 }}>
            {msg}
          </div>
        )}

        <div className="modal-actions" style={{ marginTop: 16 }}>
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" disabled={merging || !sourceId || !targetId || sourceId === targetId} onClick={handleMerge}>
            {merging ? "合并中..." : "确认合并"}
          </button>
        </div>
      </div>
    </div>

        <ConfirmDialog
        open={showConfirm}
        title="确认合并"
        message={`将标签 "${sourceTag?.value}" 合并到 "${targetTag?.value}"？
源标签的所有条目关系将转移，随后源标签被删除。`}
        variant="danger"
        confirmLabel="确认合并"
        onClose={() => setShowConfirm(false)}
        onConfirm={executeMerge}
        loading={merging}
      />
    </>
  );
}
