import { ConfirmDialog } from "./shared/ConfirmDialog";
import { useEffect, useState, useCallback } from "react";
import { Plus, Trash2, Edit3, FolderTree } from "lucide-react";

interface Category {
  id: string; name: string; description: string | null;
  created_at: string | null; updated_at: string | null;
}

const BASE = "/api/v1";

export function CategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<{id: string; message: string} | null>(null);
  const [editing, setEditing] = useState<Category | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${BASE}/categories`);
      if (!resp.ok) throw new Error(await resp.text());
      setCategories(await resp.json());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleDelete = (id: string) => {
    setConfirmDelete({ id, message: `删除类别 "${id}"？关联的主题将变为未分类。` });
  };

  const executeDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    try {
      const resp = await fetch(`${BASE}/categories/${id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await resp.text());
      setCategories((p) => p.filter((c) => c.id !== id));
    } catch (e) { alert(e instanceof Error ? e.message : "删除失败"); }
    setConfirmDelete(null);
  };

  if (loading) return <div className="loading">加载类别...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>采集类别</h2>
          <p className="text-muted">树状结构顶层：类别 → 主题 → 批次 → 条目</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={14} /> 新建类别
        </button>
      </div>

      <div className="card-list">
        {categories.map((cat) => (
          <article key={cat.id} className="card-item card-item--compact">
            <div className="card-item-header">
              <div className="card-item-title">
                <h4><FolderTree size={14} style={{ opacity: 0.5, marginRight: 6 }} />{cat.name}</h4>
                <span className="text-muted small">{cat.id}</span>
              </div>
              <div className="card-item-actions">
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(cat)}>
                  <Edit3 size={12} /> 编辑
                </button>
                <button type="button" className="btn btn-sm btn-danger" onClick={() => handleDelete(cat.id)}>
                  <Trash2 size={12} /> 删除
                </button>
              </div>
            </div>
            {cat.description && (
              <div className="card-item-meta card-item-meta--compact">
                <span className="meta-inline text-muted">{cat.description}</span>
              </div>
            )}
          </article>
        ))}
        {categories.length === 0 && (
          <div className="empty"><FolderTree size={24} style={{ opacity: 0.3, margin: "0 auto 8px" }} /><p>暂无类别。点击"新建类别"创建第一个采集类别。</p></div>
        )}
      </div>

      {(showCreate || editing) && (
        <CategoryForm
          category={editing}
          onSave={async (data) => {
            const isNew = !editing;
            const resp = isNew
              ? await fetch(`${BASE}/categories`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) })
              : await fetch(`${BASE}/categories/${editing.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
            if (!resp.ok) { alert(await resp.text()); return; }
            setShowCreate(false); setEditing(null); await load();
          }}
          onClose={() => { setShowCreate(false); setEditing(null); }}
        />
      )}
    </div>
  );
}

function CategoryForm({ category, onSave, onClose }: {
  category: Category | null; onSave: (data: { id: string; name: string; description?: string }) => Promise<void>; onClose: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const [id, setId] = useState(category?.id ?? "");
  const [name, setName] = useState(category?.name ?? "");
  const [desc, setDesc] = useState(category?.description ?? "");

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{category ? "编辑类别" : "新建类别"}</h3>
        <div className="form-grid">
          <label>ID <input value={id} onChange={(e) => setId(e.target.value)} disabled={!!category} placeholder="trade-policy" /></label>
          <label>名称 <input value={name} onChange={(e) => setName(e.target.value)} placeholder="贸易政策" /></label>
          <label className="span-2">描述 <input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="贸易政策、关税调整、自贸协定" /></label>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" onClick={async () => {
            setSaving(true); try { await onSave({ id, name, description: desc || undefined }); }
            catch (e) { alert("保存失败"); } setSaving(false);
          }} disabled={saving || !id || !name}>
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
