import { useState, useEffect, useCallback } from "react";
import { Bell, Plus, Trash2, Send, ToggleLeft, ToggleRight, RefreshCw, Edit3 } from "lucide-react";
import {
  fetchNotifications, createNotification, updateNotification,
  deleteNotification, testNotification,
} from "../api";
import type { NotificationConfig } from "../types";
import { Modal } from "./shared/Modal";
import { EmptyState } from "./shared/EmptyState";
import { StatusBadge } from "./shared/StatusBadge";
import { ConfirmDialog } from "./shared/ConfirmDialog";

const NEW_NOTIF: Partial<NotificationConfig> = {
  name: "",
  channel: "webhook",
  webhook_url: "",
  email_to: "",
  trigger_on_new: true,
  trigger_on_failure: false,
  is_active: true,
};

export function NotificationsPage() {
  const [items, setItems] = useState<NotificationConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Partial<NotificationConfig> | null>(null);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{id: string; message: string} | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await fetchNotifications());
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const openNew = () => { setEditing({ ...NEW_NOTIF }); setModalOpen(true); };
  const openEdit = (item: NotificationConfig) => {
    setEditing({ ...item }); setModalOpen(true);
  };

  const save = async () => {
    if (!editing?.name?.trim()) return;
    if (editing.channel === "webhook" && !editing.webhook_url?.trim()) return;
    if (editing.channel === "email" && !editing.email_to?.trim()) return;

    setSaving(true);
    try {
      if (editing.id) {
        await updateNotification(editing.id, editing);
      } else {
        await createNotification({
          name: editing.name!,
          channel: editing.channel!,
          webhook_url: editing.webhook_url ?? null,
          email_to: editing.email_to ?? null,
          trigger_on_new: editing.trigger_on_new ?? true,
          trigger_on_failure: editing.trigger_on_failure ?? false,
          is_active: editing.is_active ?? true,
        });
      }
      setModalOpen(false);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "保存失败");
    }
    setSaving(false);
  };

  const handleDelete = (id: string) => {
    setConfirmDelete({ id, message: "确定要删除这个通知配置吗？" });
  };

  const executeDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    try {
      await deleteNotification(id);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
    setConfirmDelete(null);
  };

  const handleTest = async (id: string) => {
    setTestingId(id);
    setTestResult(null);
    try {
      const r = await testNotification(id);
      setTestResult(r.success ? `✅ 测试成功: ${r.message}` : `❌ 测试失败: ${r.message}`);
    } catch (e) {
      setTestResult(`❌ 测试异常: ${e instanceof Error ? e.message : String(e)}`);
    }
    setTestingId(null);
  };

  const handleToggleActive = async (item: NotificationConfig) => {
    try {
      await updateNotification(item.id, { is_active: !item.is_active });
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "更新失败");
    }
  };

  if (loading) return <div className="loading">加载通知配置...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>通知管理</h2>
          <p className="text-muted">配置采集完成后的 Webhook 或 Email 通知。</p>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button type="button" className="btn btn-ghost btn-sm" onClick={load}>
            <RefreshCw size={12} />
          </button>
          <button type="button" className="btn btn-primary btn-sm" onClick={openNew}>
            <Plus size={12} /> 新增通知
          </button>
        </div>
      </div>

      {testResult && (
        <div className={`notif-test-banner ${testResult.startsWith("✅") ? "notif-test-ok" : "notif-test-err"}`}>
          {testResult}
          <button type="button" className="btn-close-text" onClick={() => setTestResult(null)} style={{ marginLeft: 12 }}>✕</button>
        </div>
      )}

      {items.length === 0 ? (
        <EmptyState icon={<Bell size={36} style={{ opacity: 0.3 }} />} title="暂无通知配置" description="点击「新增通知」添加 Webhook 或 Email 通知规则" />
      ) : (
        <div className="notification-list">
          {items.map((item) => (
            <article key={item.id} className={`notif-card ${item.is_active ? "" : "notif--inactive"}`}>
              <div className="notif-main">
                <div className="notif-header">
                  <Bell size={16} style={{ color: "var(--accent)" }} />
                  <strong>{item.name}</strong>
                  <StatusBadge status={item.is_active ? "active" : "inactive"} />
                  <span className="chip chip--blue" style={{ fontSize: 11 }}>
                    {item.channel === "webhook" ? "Webhook" : "Email"}
                  </span>
                </div>
                <div className="notif-detail">
                  {item.channel === "webhook" && item.webhook_url && (
                    <code>{item.webhook_url}</code>
                  )}
                  {item.channel === "email" && item.email_to && (
                    <span>收件人: {item.email_to}</span>
                  )}
                </div>
                <div className="notif-triggers">
                  {item.trigger_on_new && <span className="chip chip--green">新条目时触发</span>}
                  {item.trigger_on_failure && <span className="chip chip--red">失败时触发</span>}
                  {item.last_sent_at && (
                    <span className="text-muted" style={{ fontSize: 11 }}>
                      上次发送: {new Date(item.last_sent_at).toLocaleString("zh")}
                    </span>
                  )}
                </div>
              </div>
              <div className="notif-actions">
                <button type="button" className="btn-icon" title="测试发送" onClick={() => handleTest(item.id)} disabled={testingId === item.id}>
                  <Send size={14} className={testingId === item.id ? "spin" : ""} />
                </button>
                <button type="button" className="btn-icon" title={item.is_active ? "停用" : "启用"} onClick={() => handleToggleActive(item)}>
                  {item.is_active ? <ToggleRight size={16} style={{ color: "var(--green)" }} /> : <ToggleLeft size={16} />}
                </button>
                <button type="button" className="btn-icon" title="编辑" onClick={() => openEdit(item)}>
                  <Edit3 size={14} />
                </button>
                <button type="button" className="btn-icon btn-icon--danger" title="删除" onClick={() => handleDelete(item.id)}>
                  <Trash2 size={14} />
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Create / Edit Modal */}
      {modalOpen && editing && (
        <Modal
          open={modalOpen}
          title={editing.id ? "编辑通知" : "新增通知"}
          onClose={() => setModalOpen(false)}
        >
          <div className="form-group">
            <label className="form-label">名称</label>
            <input
              type="text"
              className="input"
              placeholder="例如：新情报微信通知"
              value={editing.name ?? ""}
              onChange={(e) => setEditing({ ...editing, name: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">通知渠道</label>
            <div className="segmented-control">
              <button
                type="button"
                className={`seg-btn ${editing.channel === "webhook" ? "seg-btn--active" : ""}`}
                onClick={() => setEditing({ ...editing, channel: "webhook" })}
              >Webhook</button>
              <button
                type="button"
                className={`seg-btn ${editing.channel === "email" ? "seg-btn--active" : ""}`}
                onClick={() => setEditing({ ...editing, channel: "email" })}
              >Email</button>
            </div>
          </div>
          {editing.channel === "webhook" ? (
            <div className="form-group">
              <label className="form-label">Webhook URL</label>
              <input
                type="url"
                className="input"
                placeholder="https://hooks.example.com/..."
                value={editing.webhook_url ?? ""}
                onChange={(e) => setEditing({ ...editing, webhook_url: e.target.value })}
              />
            </div>
          ) : (
            <div className="form-group">
              <label className="form-label">收件邮箱</label>
              <input
                type="email"
                className="input"
                placeholder="user@example.com"
                value={editing.email_to ?? ""}
                onChange={(e) => setEditing({ ...editing, email_to: e.target.value })}
              />
            </div>
          )}
          <div className="form-group">
            <label className="form-label">触发条件</label>
            <div style={{ display: "flex", gap: 12, flexDirection: "column", marginTop: 4 }}>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={editing.trigger_on_new ?? true}
                  onChange={(e) => setEditing({ ...editing, trigger_on_new: e.target.checked })}
                />
                采集到新条目时触发
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={editing.trigger_on_failure ?? false}
                  onChange={(e) => setEditing({ ...editing, trigger_on_failure: e.target.checked })}
                />
                采集失败时触发
              </label>
            </div>
          </div>
          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={editing.is_active ?? true}
                onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })}
              />
              启用此通知
            </label>
          </div>
          <div className="modal-footer-row" style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
            <button type="button" className="btn btn-ghost" onClick={() => setModalOpen(false)}>取消</button>
            <button type="button" className="btn btn-primary" onClick={save} disabled={saving}>
              {saving ? "保存中..." : "保存"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
