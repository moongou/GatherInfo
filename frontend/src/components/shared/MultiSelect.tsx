import { useEffect, useRef, useState } from "react";

interface MultiSelectProps {
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (ids: string[]) => void;
  placeholder: string;
}

export function MultiSelect({
  options,
  selected,
  onChange,
  placeholder,
}: MultiSelectProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const allSelected =
    options.length > 0 && options.every((o) => selected.includes(o.value));
  const toggleAll = () => {
    onChange(allSelected ? [] : options.map((o) => o.value));
  };
  const toggle = (value: string) => {
    onChange(
      selected.includes(value)
        ? selected.filter((s) => s !== value)
        : [...selected, value],
    );
  };

  return (
    <div className="multi-select-wrapper" ref={ref}>
      <button
        type="button"
        className="multi-select-trigger"
        onClick={() => setOpen(!open)}
      >
        <span className={selected.length === 0 ? "placeholder" : ""}>
          {placeholder}
        </span>
        <ChevronDownIcon open={open} />
      </button>
      {open && (
        <div className="multi-select-dropdown">
          {options.length > 0 && (
            <label className="multi-select-option multi-select-all">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleAll}
              />
              <strong>{allSelected ? "取消全选" : "全选"}</strong>
            </label>
          )}
          {options.map((o) => (
            <label key={o.value} className="multi-select-option">
              <input
                type="checkbox"
                checked={selected.includes(o.value)}
                onChange={() => toggle(o.value)}
              />
              {o.label}
            </label>
          ))}
          {options.length === 0 && (
            <div
              className="multi-select-option"
              style={{ color: "var(--ink-muted)", cursor: "default" }}
            >
              暂无活跃信息源
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ChevronDownIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        transform: open ? "rotate(180deg)" : "",
        transition: "transform 0.15s",
        flexShrink: 0,
        color: "var(--ink-muted)",
      }}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
