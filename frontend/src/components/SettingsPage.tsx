import { useState, useRef, useEffect, useCallback } from "react";
import { Download, Upload, AlertTriangle, CheckCircle, X, Save } from "lucide-react";
import { exportConfig, importConfig, fetchSettings, updateSettings } from "../api";
import type { SystemConfig } from "../types";

const ALL_FORMATS = ["md", "html", "docx", "pdf"];

export function SettingsPage() {
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [resultMsg, setResultMsg] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<any[]>([]);
  const [importMode, setImportMode] = useState("skip");
  const [showConflictDetail, setShowConflictDetail] = useState<any | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Report settings
  const [settings, setSettings] = useState<SystemConfig | null>(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState<string | null>(null);

  const loadSettings = useCallback(async () => {
    try {
      const s = await fetchSettings();
      setSettings(s);
    } catch {
      /* ignore */
    }
  }, []);
  useEffect(() => { void loadSettings(); }, [loadSettings]);

  const toggleFormat = (fmt: string) => {
    setSettings((prev) => {
      if (!prev) return prev;
      const has = prev.report_formats.includes(fmt);
      const next = has ? prev.report_formats.filter((f) => f !== fmt) : [...prev.report_formats, fmt];
      return { ...prev, report_formats: next };
    });
  };

  const handleSaveSettings = async () => {
    if (!settings) return;
    setSavingSettings(true);
    setSettingsMsg(null);
    try {
      const saved = await updateSettings(settings);
      setSettings(saved);
      setSettingsMsg("报告设置已保存");
    } catch (e) {
      setSettingsMsg(`保存失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setSavingSettings(false);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const config = await exportConfig();
      const blob = new Blob([JSON.stringify(config, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `gatherinfo-config-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setResultMsg(`Configuration exported: ${Object.values(config).reduce((s: number, v: any) => s + (Array.isArray(v) ? v.length : 0), 0)} items`);
    } catch (e) {
      setResultMsg(`Export failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    }
    setExporting(false);
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      data.mode = importMode;
      const result = await importConfig(data);
      const total = Object.values(result.imported).reduce((s: number, v: any) => s + (v as number), 0);
      setResultMsg(`Imported: ${total} items. Conflicts: ${result.conflict_count}`);
      setConflicts(result.conflicts || []);
    } catch (e) {
      setResultMsg(`Import failed: ${e instanceof Error ? e.message : "Invalid JSON"}`);
    }
    setImporting(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>系统配置</h2>
          <p className="text-muted">导出当前配置备份，或从备份文件导入配置。</p>
        </div>
      </div>

      {resultMsg && (
        <div className="toast" onClick={() => setResultMsg(null)} style={{ marginBottom: 16 }}>
          {resultMsg}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Export */}
        <div className="card-item" style={{ padding: 24 }}>
          <div style={{ textAlign: "center", marginBottom: 16 }}>
            <Download size={32} style={{ opacity: 0.5, marginBottom: 8 }} />
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 4 }}>导出配置</h3>
            <p className="text-muted small">将所有模型配置、主题、信息源、标签、调度导出为 JSON 文件</p>
          </div>
          <div style={{ display: "flex", justifyContent: "center" }}>
            <button type="button" className="btn btn-primary" onClick={handleExport} disabled={exporting}>
              <Download size={14} /> {exporting ? "导出中..." : "下载配置文件"}
            </button>
          </div>
        </div>

        {/* Import */}
        <div className="card-item" style={{ padding: 24 }}>
          <div style={{ textAlign: "center", marginBottom: 16 }}>
            <Upload size={32} style={{ opacity: 0.5, marginBottom: 8 }} />
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 4 }}>导入配置</h3>
            <p className="text-muted small">从 JSON 备份文件恢复配置</p>
          </div>
          <div style={{ marginBottom: 12 }}>
            <label className="text-muted small" style={{ display: "block", marginBottom: 4 }}>冲突处理方式</label>
            <select value={importMode} onChange={(e) => setImportMode(e.target.value)} style={{ width: "100%", padding: "8px 10px", background: "var(--surface-elevated)", border: "1px solid var(--line)", borderRadius: "var(--radius)", fontSize: "0.85rem" }}>
              <option value="skip">跳过已有项目</option>
              <option value="overwrite">覆盖已有项目</option>
              <option value="append">追加（创建新条目）</option>
            </select>
          </div>
          <div style={{ display: "flex", justifyContent: "center" }}>
            <input ref={fileRef} type="file" accept=".json" onChange={handleImport} style={{ display: "none" }} />
            <button type="button" className="btn btn-primary" onClick={() => fileRef.current?.click()} disabled={importing}>
              <Upload size={14} /> {importing ? "导入中..." : "选择文件导入"}
            </button>
          </div>
        </div>
      </div>

      {/* Report settings */}
      {settings && (
        <div className="panel" style={{ marginTop: 16 }}>
          <h3>报告设置</h3>
          <p className="text-muted small" style={{ marginBottom: 12 }}>
            配置生成报告的标题格式、输出目录与导出格式。标题可用 {"{topic}"} 与 {"{date}"} 占位符。
          </p>
          <div className="form-group">
            <label className="text-muted small">标题格式</label>
            <input
              type="text"
              title="报告标题格式"
              value={settings.report_title_format}
              onChange={(e) => setSettings((p) => (p ? { ...p, report_title_format: e.target.value } : p))}
            />
          </div>
          <div className="form-group">
            <label className="text-muted small">输出目录（留空使用默认 data/reports）</label>
            <input
              type="text"
              value={settings.report_output_dir ?? ""}
              placeholder="data/reports"
              onChange={(e) => setSettings((p) => (p ? { ...p, report_output_dir: e.target.value || null } : p))}
            />
          </div>
          <div className="form-group">
            <label className="text-muted small">目录日期模式（strftime，如 %Y-%m-%d）</label>
            <input
              type="text"
              title="目录日期模式"
              value={settings.report_dir_pattern}
              onChange={(e) => setSettings((p) => (p ? { ...p, report_dir_pattern: e.target.value } : p))}
            />
          </div>
          <div className="form-group">
            <label className="text-muted small" style={{ display: "block", marginBottom: 6 }}>导出格式</label>
            <div className="checkbox-grid">
              {ALL_FORMATS.map((fmt) => (
                <label key={fmt} className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={settings.report_formats.includes(fmt)}
                    onChange={() => toggleFormat(fmt)}
                  />
                  {fmt.toUpperCase()}
                </label>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8 }}>
            <button type="button" className="btn btn-primary" onClick={handleSaveSettings} disabled={savingSettings}>
              <Save size={14} /> {savingSettings ? "保存中..." : "保存报告设置"}
            </button>
            {settingsMsg && <span className="text-muted small">{settingsMsg}</span>}
          </div>
        </div>
      )}

      {/* Conflicts */}
      {conflicts.length > 0 && (
        <div className="panel" style={{ marginTop: 16 }}>
          <h3>冲突项目 ({conflicts.length})</h3>
          <div className="tag-stats-table">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>名称</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {conflicts.slice(0, 20).map((c) => (
                  <tr key={c.id}>
                    <td><code>{c.id}</code></td>
                    <td>{c.name}</td>
                    <td>{c.identical ? <span className="chip chip--green">完全相同</span> : <span className="chip chip--blue">不同</span>}</td>
                    <td>
                      <button type="button" className="btn btn-sm btn-ghost" onClick={() => setShowConflictDetail(c)}>
                        <AlertTriangle size={12} /> 查看差异
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Conflict detail modal */}
      {showConflictDetail && (
        <div className="modal-overlay" onClick={() => setShowConflictDetail(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 600 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3>冲突详情: {showConflictDetail.name}</h3>
              <button type="button" className="btn-icon" onClick={() => setShowConflictDetail(null)}>
                <X size={16} />
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, fontSize: "0.82rem" }}>
              <div>
                <strong className="text-muted">现有配置</strong>
                <pre style={{ background: "var(--surface-elevated)", padding: 12, borderRadius: "var(--radius)", marginTop: 4, fontSize: "0.75rem", maxHeight: 300, overflow: "auto" }}>
                  {JSON.stringify(showConflictDetail.existing || {}, null, 2)}
                </pre>
              </div>
              <div>
                <strong className="text-muted">导入配置</strong>
                <pre style={{ background: "var(--surface-elevated)", padding: 12, borderRadius: "var(--radius)", marginTop: 4, fontSize: "0.75rem", maxHeight: 300, overflow: "auto" }}>
                  {JSON.stringify(showConflictDetail.incoming, null, 2)}
                </pre>
              </div>
            </div>
            <div style={{ marginTop: 16, textAlign: "center" }}>
              <span className={`chip ${showConflictDetail.identical ? "chip--green" : "chip--blue"}`}>
                {showConflictDetail.identical ? "完全相同" : "配置不同"}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
