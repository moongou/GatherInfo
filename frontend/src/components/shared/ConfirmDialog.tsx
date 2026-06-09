import { AlertTriangle } from "lucide-react";
import { Modal } from "./Modal";

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title?: string;
  message: string;
  /** Visual treatment: "danger" shows red accent, "default" is neutral. */
  variant?: "default" | "danger";
  confirmLabel?: string;
  cancelLabel?: string;
  loading?: boolean;
}

/**
 * Reusable confirmation dialog built on Modal.
 * Use instead of window.confirm() for a consistent UI.
 */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title = "确认操作",
  message,
  variant = "default",
  confirmLabel = "确认",
  cancelLabel = "取消",
  loading = false,
}: ConfirmDialogProps) {
  const isDanger = variant === "danger";

  return (
    <Modal open={open} onClose={onClose} title={title} width={420}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        {isDanger && (
          <AlertTriangle size={20} style={{ color: "var(--red)", flexShrink: 0, marginTop: 2 }} />
        )}
        <p style={{ margin: 0, lineHeight: 1.6, color: "var(--ink-muted)" }}>
          {message}
        </p>
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          gap: 8,
          marginTop: 20,
          paddingTop: 16,
          borderTop: "1px solid var(--line)",
        }}
      >
        <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
          {cancelLabel}
        </button>
        <button
          type="button"
          className={`btn ${isDanger ? "btn-danger" : "btn-primary"}`}
          onClick={onConfirm}
          disabled={loading}
        >
          {loading ? "处理中..." : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
