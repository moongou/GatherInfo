import { ExternalLink, X } from "lucide-react";
import type { CollectedItem, Source } from "../types";

interface ItemDetailModalProps {
  item: CollectedItem;
  sources: Source[];
  onClose: () => void;
}

export function ItemDetailModal({ item, sources, onClose }: ItemDetailModalProps) {
  const sourceName =
    sources.find((s) => s.id === item.source_id)?.name || item.source_id;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal reading-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="reading-modal-header">
          <div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, lineHeight: 1.4 }}>
              {item.title}
            </h3>
            <div
              className="reading-modal-meta"
              style={{
                display: "flex",
                gap: 8,
                flexWrap: "wrap",
                marginTop: 8,
              }}
            >
              {item.source_id && (
                <span className="chip">来源: {sourceName}</span>
              )}
              {item.language && <span className="chip">{item.language}</span>}
              {item.category && (
                <span className="chip chip--blue">{item.category}</span>
              )}
              {item.published_at && (
                <span className="text-muted small">
                  发布: {new Date(item.published_at).toLocaleString("zh")}
                </span>
              )}
              {item.collected_at && (
                <span className="text-muted small">
                  采集: {new Date(item.collected_at).toLocaleString("zh")}
                </span>
              )}
              {item.tags?.map((t) => (
                <span
                  key={t.id}
                  className="chip chip--pink"
                  title={`${t.namespace}:${t.value}`}
                >
                  {t.value}
                </span>
              ))}
            </div>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onClose}
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="reading-modal-body">
          {item.summary && (
            <div className="reading-summary">
              <strong>摘要</strong>
              <p>{item.summary}</p>
            </div>
          )}

          {item.url && (
            <div className="reading-url">
              <strong>原文链接</strong>
              <a href={item.url} target="_blank" rel="noopener noreferrer">
                {item.url} <ExternalLink size={12} />
              </a>
            </div>
          )}

          <div className="reading-content">
            {(item as any).content ? (
              <div
                style={{
                  whiteSpace: "pre-wrap",
                  fontSize: "0.9rem",
                  lineHeight: 1.8,
                }}
              >
                {(item as any).content}
              </div>
            ) : (
              <p
                className="text-muted"
                style={{
                  fontStyle: "italic",
                  padding: 20,
                  textAlign: "center",
                }}
              >
                暂无详细内容，当前仅显示摘要信息。
              </p>
            )}
          </div>

          <div className="reading-modal-footer">
            <div className="text-muted small">
              质量评分: {item.quality_score.toFixed(2)} | 相关性:{" "}
              {item.relevance_score.toFixed(2)} | 状态: {item.status}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
