import { useEffect, useState, useCallback } from "react";
import { Plus, Trash2, Edit3, CheckCircle, Eye, ExternalLink } from "lucide-react";
import { fetchSources, createSource, deleteSource, updateSource, validateSource, fetchConnectors } from "../api";
import type { Source, ConnectorInfo } from "../types";

export function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Source | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [initialLoad, setInitialLoad] = useState(true);

  const load = useCallback(async () => {
    try {
      const [srcs, cs] = await Promise.all([fetchSources(), fetchConnectors()]);
      setSources(srcs);
      setConnectors(cs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
      setInitialLoad(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleDelete = async (id: string) => {
    if (!confirm(`删除信息源 "${id}"？这将同时删除其采集的所有条目。`)) return;
    try { await deleteSource(id); setSources((p) => p.filter((s) => s.id !== id)); }
    catch (e) { alert(e instanceof Error ? e.message : "删除失败"); }
  };

  const handleValidate = async (id: string) => {
    try {
      const r = await validateSource(id);
      alert(r.valid ? "连接成功" : `连接失败: ${r.error ?? "未知错误"}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "验证失败");
    }
  };

  if (initialLoad) return <div className="loading">加载信息源...</div>;
  if (loading) return null;

  return (
    <div className="page">
      {error && <div className="error-banner">{error} <button type="button" className="btn btn-sm btn-ghost" onClick={() => setError(null)} style={{ marginLeft: 8 }}>×</button></div>}
      <div className="page-header">
        <div>
          <h2>信息源管理</h2>
          <p className="text-muted">管理采集渠道：搜索API、网页抓取、RSS、官方API、通用JSON API等</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={14} /> 新建信息源
        </button>
      </div>

      <div className="connector-list">
        <h4>可用连接器</h4>
        <div className="chip-row">
          {connectors.map((c) => (
            <span key={c.channel} className="chip chip--blue" title={c.description}>{c.channel}</span>
          ))}
        </div>
      </div>

      <div className="card-list">
        {sources.map((s) => (
          <article key={s.id} className="card-item card-item--compact">
            <div className="card-item-header">
              <div className="card-item-title">
                <h4>
                  {s.name}
                  {s.homepage_url && (
                    <a href={s.homepage_url} target="_blank" rel="noreferrer" className="source-home-link" title={`打开官网 / 购买服务: ${s.homepage_url}`}>
                      <ExternalLink size={12} /> 官网
                    </a>
                  )}
                </h4>
                <span className="text-muted small">{s.id} · {s.channel}</span>
              </div>
              <div className="card-item-actions">
                <span className={`badge ${s.is_active ? "badge--green" : "badge--gray"}`}>
                  {s.is_active ? "活跃" : "停用"}
                </span>
              </div>
            </div>
            <div className="card-item-meta card-item-meta--compact">
              <span className="meta-inline"><strong>地址:</strong> <code>{s.base_url || s.api_endpoint || "-"}</code></span>
              <span className="meta-inline"><strong>语言:</strong> {(s.languages ?? []).join(", ") || "any"}</span>
              <span className="meta-inline"><strong>关键词:</strong> {(s.default_keywords ?? []).join(", ") || "无"}</span>
              <span className="meta-inline text-muted">采集 {s.items_collected} 条{s.last_error && <span className="text-red"> · 错误: {s.last_error}</span>}</span>
            </div>
            <div className="card-item-footer">
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => handleValidate(s.id)}>
                <CheckCircle size={12} /> 验证连接
              </button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(s)}>
                <Edit3 size={12} /> 编辑
              </button>
              <button type="button" className="btn btn-sm btn-danger" onClick={() => handleDelete(s.id)}>
                <Trash2 size={12} /> 删除
              </button>
            </div>
          </article>
        ))}
      </div>

      {(showCreate || editing) && (
        <SourceForm
          key={editing?.id ?? "create"}
          source={editing}
          connectors={connectors}
          onSave={async (data) => {
            if (editing) { await updateSource(editing.id, data); }
            else { await createSource(data as Source); }
            setShowCreate(false); setEditing(null); await load();
          }}
          onClose={() => { setShowCreate(false); setEditing(null); }}
        />
      )}
    </div>
  );
}

// ── Source form ──────────────────────────────────────────────────────────────

type SourceFormProps = {
  source: Source | null;
  connectors: ConnectorInfo[];
  onSave: (data: Partial<Source>) => Promise<void>;
  onClose: () => void;
};

function SourceForm({ source, connectors, onSave, onClose }: SourceFormProps) {
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState(source?.name ?? "");
  const [desc, setDesc] = useState(source?.description ?? "");
  const [channel, setChannel] = useState(source?.channel ?? connectors[0]?.channel ?? "api_search");
  const [baseUrl, setBaseUrl] = useState(source?.base_url ?? "");
  const [apiEndpoint, setApiEndpoint] = useState(source?.api_endpoint ?? "");
  const [homepageUrl, setHomepageUrl] = useState(source?.homepage_url ?? "");
  const [kw, setKw] = useState((source?.default_keywords ?? []).join(", "));
  const [langs, setLangs] = useState((source?.languages ?? []).join(", "));
  const [rps, setRps] = useState(source?.rate_limit_rps != null ? String(source.rate_limit_rps) : "1.0");
  const [showKey, setShowKey] = useState(false);
  const [apiKey, setApiKey] = useState(source?.api_key ?? "");
  const [authConfig, setAuthConfig] = useState(
    source?.auth_config ? JSON.stringify(source.auth_config, null, 2) : ""
  );
  const [authConfigError, setAuthConfigError] = useState<string | null>(null);

  const meta = connectors.find((c) => c.channel === channel);
  const required = meta?.required_fields ?? [];
  const optional = meta?.optional_fields ?? [];
  const isUsed = (f: string) => required.includes(f) || optional.includes(f);
  // Placeholder: required→提示填写, optional→可留空, otherwise→不需填写
  const ph = (f: string, hint: string) =>
    required.includes(f) ? hint : optional.includes(f) ? `(可选) ${hint}` : "不需填写";

  // Auto-fill connection defaults when the channel changes (only for empty/new sources).
  const handleChannelChange = (next: string) => {
    setChannel(next);
    const m = connectors.find((c) => c.channel === next);
    if (!m) return;
    if (!source) {
      if (m.default_base_url != null) setBaseUrl(m.default_base_url || "");
      if (m.default_api_endpoint != null) setApiEndpoint(m.default_api_endpoint || "");
      if (m.homepage_hint && !homepageUrl) setHomepageUrl(m.homepage_hint);
    }
  };

  // Tolerant split: accept both English/Chinese commas
  const splitList = (v: string) => v.split(/[,，]/).map((s) => s.trim()).filter(Boolean);

  const handleSave = async () => {
    let parsedAuth: Record<string, unknown> | null = null;
    if (authConfig.trim()) {
      try { parsedAuth = JSON.parse(authConfig); setAuthConfigError(null); }
      catch { setAuthConfigError("auth_config 不是合法 JSON"); return; }
    }
    setSaving(true);
    try {
      await onSave({
        name, description: desc || null,
        channel, is_active: true,
        base_url: baseUrl || null,
        api_endpoint: apiEndpoint || null,
        homepage_url: homepageUrl || null,
        default_keywords: kw ? splitList(kw) : null,
        api_key: apiKey || null,
        auth_config: parsedAuth,
        languages: langs ? splitList(langs) : null,
        rate_limit_rps: parseFloat(rps) || 1,
      });
    } catch (e) { alert(e instanceof Error ? e.message : "保存失败"); }
    setSaving(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal--source" onClick={(e) => e.stopPropagation()}>
        <h3>{source ? "编辑信息源" : "新建信息源"}</h3>
        <div className="form-grid">
          {source && (
            <label>ID <span className="chip chip--inline">{source.id}</span></label>
          )}
          <label>名称 <input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>渠道
            <select value={channel} onChange={(e) => handleChannelChange(e.target.value)}>
              {connectors.map((c) => <option key={c.channel} value={c.channel}>{c.channel} — {c.description}</option>)}
            </select>
            {meta && (
              <span className="text-muted small">
                必填: {required.length ? required.join(", ") : "无"}
                {optional.length > 0 && <> · 可选: {optional.join(", ")}</>}
              </span>
            )}
          </label>
          <label>速率 (req/s) <input type="number" step="0.1" value={rps} onChange={(e) => setRps(e.target.value)} /></label>
          <label>API Key
            <div className="input-with-icon">
              <input type={showKey ? "text" : "password"} value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                placeholder={ph("api_key", "sk-...")} disabled={!isUsed("api_key")} />
              <button type="button" className="btn-icon" onClick={() => setShowKey(!showKey)}><Eye size={14} /></button>
            </div>
            <span className="text-muted small">{isUsed("api_key") ? "留空则使用环境变量" : "该渠道不需要 API Key"}</span>
          </label>
          <label className="span-2">描述 <input value={desc} onChange={(e) => setDesc(e.target.value)} /></label>
          <label>Base URL <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={ph("base_url", "http://...")} disabled={!isUsed("base_url")} /></label>
          <label>API Endpoint <input value={apiEndpoint} onChange={(e) => setApiEndpoint(e.target.value)}
            placeholder={ph("api_endpoint", "/search")} disabled={!isUsed("api_endpoint")} /></label>
          <label className="span-2">官网主页 (方便购买/订阅服务)
            <input value={homepageUrl} onChange={(e) => setHomepageUrl(e.target.value)} placeholder="https://..." />
          </label>
          <label>关键词 (逗号分隔，中英文逗号均可) <input value={kw} onChange={(e) => setKw(e.target.value)} /></label>
          <label>语言 (逗号分隔) <input value={langs} onChange={(e) => setLangs(e.target.value)} placeholder="zh, en" /></label>
          {isUsed("auth_config") && (
            <label className="span-2">高级配置 auth_config (JSON：认证方式、字段映射等)
              <textarea className="auth-config-editor" value={authConfig} rows={8}
                onChange={(e) => setAuthConfig(e.target.value)}
                placeholder={'{\n  "method": "GET",\n  "auth": "query",\n  "auth_param": "apiKey",\n  "keyword_param": "q",\n  "items_path": "articles",\n  "fields": { "title": "title", "url": "url" }\n}'} />
              {authConfigError && <span className="text-red small">{authConfigError}</span>}
            </label>
          )}
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
