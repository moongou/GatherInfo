type StatusVariant = "pending" | "running" | "completed" | "failed" | "partial" | "raw" | "tagged" | "enriched" | "archived" | "discarded" | "active" | "inactive";

const STATUS_MAP: Record<StatusVariant, { label: string; className: string }> = {
  pending:     { label: "等待中", className: "chip chip--amber" },
  running:     { label: "执行中", className: "chip chip--blue" },
  completed:   { label: "已完成", className: "chip chip--green" },
  failed:      { label: "失败",   className: "chip chip--red" },
  partial:     { label: "部分完成", className: "chip" },
  raw:         { label: "原始",   className: "chip" },
  tagged:      { label: "已标签", className: "chip chip--blue" },
  enriched:    { label: "已增强", className: "chip chip--green" },
  archived:    { label: "已归档", className: "chip" },
  discarded:   { label: "已丢弃", className: "chip chip--red" },
  active:      { label: "启用",   className: "chip chip--green" },
  inactive:    { label: "停用",   className: "chip chip--pink" },
};

interface StatusBadgeProps {
  status: StatusVariant;
  /** Optional override label */
  label?: string;
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const config = STATUS_MAP[status] ?? { label: status, className: "chip" };
  return <span className={`chip ${config.className}`}>{label ?? config.label}</span>;
}
