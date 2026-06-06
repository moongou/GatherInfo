import { useEffect, useState, useCallback } from "react";
import { Plus, Trash2, Edit3, CheckCircle, XCircle, Zap, Cpu, List, Radar } from "lucide-react";
import { fetchModels, createModel, updateModel, deleteModel, testModel, listAvailableModels, autoDiscoverModels } from "../api";
import type { ModelConfig, ModelTestResult, ListModelsResult } from "../types";

export function ModelConfigPage() {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<ModelConfig | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, ModelTestResult>>({});
  const [listResults, setListResults] = useState<Record<string, ListModelsResult>>({});
  const [listing, setListing] = useState<string | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [discoverMsg, setDiscoverMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setModels(await fetchModels());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleDelete = async (id: string) => {
    if (!confirm(`删除模型 "${id}"？`)) return;
    try { await deleteModel(id); setModels((p) => p.filter((m) => m.id !== id)); }
    catch (e) { alert(e instanceof Error ? e.message : "删除失败"); }
  };

  const handleTest = async (id: string) => {
    setTesting(id);
    try {
      const result = await testModel(id);
      setTestResults((p) => ({ ...p, [id]: result }));
    } catch (e) {
      setTestResults((p) => ({ ...p, [id]: { success: false, message: String(e), response_preview: null, duration_ms: null } }));
    }
    setTesting(null);
  };

  const handleListModels = async (id: string) => {
    setListing(id);
    try {
      const result = await listAvailableModels(id);
      setListResults((p) => ({ ...p, [id]: result }));
    } catch (e) {
      setListResults((p) => ({ ...p, [id]: { success: false, message: String(e), models: [], provider_type: "", current_model: "" } }));
    }
    setListing(null);
  };

  const handleAutoDiscover = async () => {
    setDiscovering(true);
    setDiscoverMsg(null);
    try {
      const res = await autoDiscoverModels();
      const reachable = res.providers.filter((p) => p.reachable);
      if (reachable.length === 0) {
        setDiscoverMsg("未发现本地可用的模型服务 (Ollama / LM Studio / CC Switch)。");
      } else {
        const parts = reachable.map((p) => `${p.provider} (${p.models.length} 个模型)`);
        setDiscoverMsg(`发现可用服务：${parts.join("、")}。可点击“添加模型”手动配置。`);
      }
    } catch (e) {
      setDiscoverMsg(`自动发现失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setDiscovering(false);
  };

  if (loading) return <div className="loading">加载模型配置...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  const providerIcons: Record<string, string> = {
    ollama: "🦙",
    openai: "🤖",
    lmstudio: "💻",
    cc_switch: "🔀",
    custom: "🔧",
  };
  const providerNames: Record<string, string> = {
    ollama: "Ollama",
    openai: "OpenAI 兼容",
    lmstudio: "LM Studio",
    cc_switch: "CC Switch",
    custom: "自定义",
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>模型配置</h2>
          <p className="text-muted">
            配置 AI 模型用于信息处理、报告自动生成和摘要。支持本地模型和云端 API。
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={14} /> 添加模型
        </button>
      </div>

      <div className="toolbar-row">
        <button type="button" className="btn btn-secondary" onClick={handleAutoDiscover} disabled={discovering}>
          <Radar size={14} className={discovering ? "spin" : ""} />
          {discovering ? "发现中..." : "自动发现"}
        </button>
        {discoverMsg && <div className="toast" onClick={() => setDiscoverMsg(null)}>{discoverMsg}</div>}
      </div>

      {models.length === 0 && (
        <div className="card-item" style={{ padding: 32, textAlign: "center" }}>
          <Cpu size={32} className="text-muted" style={{ margin: "0 auto 12px", opacity: 0.5 }} />
          <p className="text-muted">还未配置任何 AI 模型。</p>
          <p className="text-muted small" style={{ marginTop: 4 }}>
            添加一个 Ollama / OpenAI 兼容 / LM Studio 模型，即可使用报告生成功能。
          </p>
        </div>
      )}

      <div className="card-list">
        {models.map((m) => {
          const test = testResults[m.id];
          return (
            <article key={m.id} className="card-item">
              <div className="card-item-header">
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 24 }}>{providerIcons[m.provider] || "🔧"}</span>
                  <div>
                    <h4 style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      {m.name}
                      {m.is_default && <span className="chip chip--green">默认</span>}
                    </h4>
                    <span className="text-muted small">
                      {providerNames[m.provider] || m.provider} · {m.model_name || m.id}
                    </span>
                  </div>
                </div>
                <div className="card-item-actions">
                  <span className={`badge ${m.is_active ? "badge--green" : "badge--gray"}`}>
                    {m.is_active ? "活跃" : "停用"}
                  </span>
                  <span className="chip">{m.provider}</span>
                </div>
              </div>

              <div className="card-item-meta">
                <div className="model-params">
                  <span className="param-chip">温度 {m.temperature}</span>
                  <span className="param-chip">最大令牌 {m.max_tokens}</span>
                  <span className="param-chip">Top-P {m.top_p}</span>
                </div>
                <div className="text-muted small">
                  <strong>地址:</strong> {m.base_url || "(默认)"}
                  {m.api_key ? <span> · <strong>API Key:</strong> 已配置</span> : null}
                </div>
                {m.description && <div className="text-muted small">{m.description}</div>}

                {test && (
                  <div className={`model-test-result ${test.success ? "test-pass" : "test-fail"}`}>
                    <span>{test.success ? "✅" : "❌"}</span>
                    <span>{test.message}</span>
                    {test.response_preview && <span className="text-muted small"> · 响应: {test.response_preview}</span>}
                    {test.duration_ms != null && <span className="text-muted small"> · {test.duration_ms}ms</span>}
                  </div>
                )}
                {listResults[m.id] && listResults[m.id].models.length > 0 && (
                  <div className="available-models" style={{ marginTop: 8 }}>
                    <strong className="text-muted small" style={{ display: "block", marginBottom: 6 }}>{listResults[m.id].message}</strong>
                    <div className="chip-row" style={{ marginBottom: 0 }}>
                      {listResults[m.id].models.map((mod) => (
                        <button key={mod} type="button" className={`chip ${m.model_name === mod ? "chip--blue" : ""}`}
                          onClick={() => {
                            setEditing({ ...m, model_name: mod } as ModelConfig);
                          }}
                          title="点击选择此模型">
                          {mod}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="card-item-footer">
                <button type="button" className="btn btn-sm btn-secondary" onClick={() => handleTest(m.id)} disabled={testing === m.id}>
                  <Zap size={12} /> {testing === m.id ? "测试中..." : "测试连接"}
                </button>
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => handleListModels(m.id)} disabled={listing === m.id}>
                  <List size={12} /> {listing === m.id ? "查询中..." : "查询模型"}
                </button>
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(m)}>
                  <Edit3 size={12} /> 编辑
                </button>
                <button type="button" className="btn btn-sm btn-danger" onClick={() => handleDelete(m.id)}>
                  <Trash2 size={12} /> 删除
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {(showCreate || editing) && (
        <ModelForm
          model={editing}
          onSave={async (data) => {
            if (editing) { await updateModel(editing.id, data); }
            else { await createModel(data as ModelConfig); }
            setShowCreate(false); setEditing(null); await load();
          }}
          onClose={() => { setShowCreate(false); setEditing(null); }}
        />
      )}
    </div>
  );
}

// ── Model Form ──────────────────────────────────────────────────────

type ModelFormProps = {
  model: ModelConfig | null;
  onSave: (data: Partial<ModelConfig>) => Promise<void>;
  onClose: () => void;
};

const PROVIDERS: { value: string; label: string; desc: string; group: string }[] = [
  // Local
  { value: "ollama", label: "Ollama（本地）", desc: "http://localhost:11434", group: "本地模型" },
  { value: "cc_switch", label: "CC Switch / OpenClaw", desc: "本机统一模型通道代理", group: "本地模型" },
  { value: "lmstudio", label: "LM Studio（本地）", desc: "http://localhost:1234", group: "本地模型" },
  // Chinese providers
  { value: "openai", label: "DeepSeek (深度求索)", desc: "api.deepseek.com", group: "国内大模型 API" },
  { value: "openai", label: "通义千问 (Qwen/阿里云)", desc: "dashscope.aliyuncs.com", group: "国内大模型 API" },
  { value: "openai", label: "智谱 GLM (智谱AI)", desc: "open.bigmodel.cn", group: "国内大模型 API" },
  { value: "openai", label: "月之暗面 (Moonshot)", desc: "api.moonshot.cn", group: "国内大模型 API" },
  { value: "openai", label: "文心一言 (百度)", desc: "aip.baidubce.com", group: "国内大模型 API" },
  // Standard
  { value: "openai", label: "OpenAI 兼容 API", desc: "标准 OpenAI 格式", group: "标准 API" },
  { value: "custom", label: "自定义 API", desc: "任意兼容格式", group: "标准 API" },
];

function ModelForm({ model, onSave, onClose }: ModelFormProps) {
  const [saving, setSaving] = useState(false);
  const [id, setId] = useState(model?.id ?? "");
  const [name, setName] = useState(model?.name ?? "");
  const [provider, setProvider] = useState(model?.provider ?? "ollama");
  const [baseUrl, setBaseUrl] = useState(model?.base_url ?? "");
  const [apiKey, setApiKey] = useState(model?.api_key ?? "");
  const [modelName, setModelName] = useState(model?.model_name ?? "");
  const [temperature, setTemperature] = useState(String(model?.temperature ?? 0.7));
  const [maxTokens, setMaxTokens] = useState(String(model?.max_tokens ?? 4096));
  const [topP, setTopP] = useState(String(model?.top_p ?? 0.9));
  const [isDefault, setIsDefault] = useState(model?.is_default ?? false);
  const [description, setDescription] = useState(model?.description ?? "");

  const handleProviderChange = (p: string) => {
    setProvider(p);
    if (!model) {
      if (p === "ollama") setBaseUrl("http://localhost:11434");
      if (p === "cc_switch") { setBaseUrl("http://localhost:8080"); setModelName("openclaw-channel"); }
      if (p === "lmstudio") setBaseUrl("http://localhost:1234");
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 640 }}>
        <h3>{model ? "编辑模型" : "添加 AI 模型"}</h3>

        <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <label>ID
            <input value={id} onChange={(e) => setId(e.target.value)} disabled={!!model} placeholder="my-llm" />
          </label>
          <label>名称
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="我的本地大模型" />
          </label>

          <label className="span-2">提供商
            {(() => {
              const groups: Record<string, typeof PROVIDERS> = {};
              PROVIDERS.forEach((p) => {
                if (!groups[p.group]) groups[p.group] = [];
                groups[p.group].push(p);
              });
              return Object.entries(groups).map(([groupName, provs]) => (
                <div key={groupName} style={{ marginBottom: 8 }}>
                  <div className="text-muted small" style={{ marginBottom: 4, fontWeight: 600 }}>{groupName}</div>
                  <div className="provider-selector">
                    {provs.map((p) => (
                      <button
                        key={p.label}
                        type="button"
                        className={`provider-option ${provider === p.value && (p.label.includes(baseUrl) || !baseUrl) ? "provider-option--active" : ""}`}
                        onClick={() => {
                          handleProviderChange(p.value);
                          // Quick-fill for Chinese providers
                          if (p.label.includes("DeepSeek")) { setBaseUrl("https://api.deepseek.com/v1"); setModelName("deepseek-chat"); }
                          else if (p.label.includes("通义千问")) { setBaseUrl("https://dashscope.aliyuncs.com/compatible-mode/v1"); setModelName("qwen-plus"); }
                          else if (p.label.includes("GLM")) { setBaseUrl("https://open.bigmodel.cn/api/paas/v4"); setModelName("glm-4-flash"); }
                          else if (p.label.includes("月之暗面")) { setBaseUrl("https://api.moonshot.cn/v1"); setModelName("moonshot-v1-8k"); }
                          else if (p.label.includes("文心一言")) { setBaseUrl("https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat"); setModelName("ernie-4.0-8k"); }
                          else if (p.value === "cc_switch") { setBaseUrl("http://localhost:8080"); setModelName("openclaw-channel"); }
                          else if (p.value === "ollama") { setBaseUrl("http://localhost:11434"); setModelName("llama3.1"); }
                          else if (p.value === "lmstudio") { setBaseUrl("http://localhost:1234"); setModelName(""); }

                        }}
                      >
                        <strong>{p.label}</strong>
                        <span className="text-muted small">{p.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ));
            })()}
          </label>

          <label className="span-2">API 地址
            <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={provider === "ollama" ? "http://localhost:11434" : "http://localhost:1234/v1"} />
          </label>

          <label>模型名称
            <input value={modelName} onChange={(e) => setModelName(e.target.value)}
              placeholder={provider === "ollama" ? "llama3.1" : "gpt-4o-mini"} />
          </label>
          <label>API Key {provider !== "ollama" ? <span className="text-red">*</span> : null}
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
              placeholder={provider === "ollama" ? "可留空" : "sk-..."} />
          </label>

          <label>温度 (temperature)
            <div className="slider-with-input">
              <input type="range" min="0" max="2" step="0.05" value={temperature}
                onChange={(e) => setTemperature(e.target.value)} />
              <span className="slider-val">{temperature}</span>
            </div>
          </label>
          <label>Top-P
            <div className="slider-with-input">
              <input type="range" min="0" max="1" step="0.05" value={topP}
                onChange={(e) => setTopP(e.target.value)} />
              <span className="slider-val">{topP}</span>
            </div>
          </label>

          <label>最大令牌 (max_tokens)
            <div className="slider-with-input">
              <input type="range" min="256" max="32768" step="256" value={maxTokens}
                onChange={(e) => setMaxTokens(e.target.value)} />
              <span className="slider-val">{parseInt(maxTokens).toLocaleString()}</span>
            </div>
          </label>
          <label className="checkbox-label">
            <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
            <span>设为默认模型</span>
          </label>

          <label className="span-2">描述
            <input value={description} onChange={(e) => setDescription(e.target.value)}
              placeholder="例如：本地运行的 Qwen2.5 7B 模型，用于报告生成" />
          </label>
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" onClick={async () => {
            setSaving(true);
            try {
              await onSave({
                id, name, provider, description: description || null,
                base_url: baseUrl || null, api_key: apiKey || null,
                model_name: modelName, is_default: isDefault,
                temperature: parseFloat(temperature), max_tokens: parseInt(maxTokens), top_p: parseFloat(topP),
              });
            } catch (e) { alert(e instanceof Error ? e.message : "保存失败"); }
            setSaving(false);
          }} disabled={saving || !id || !name}>
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
