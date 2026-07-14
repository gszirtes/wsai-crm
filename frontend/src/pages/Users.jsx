import React, { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Plus, Pencil, Trash2, Shield } from "lucide-react";
import api from "../api";
import { useAuth } from "../auth";
import { Button, Input, Select, Field, Modal, Badge, Spinner } from "../components/common";

const ROLES = ["admin", "manager", "user", "guest"];
const empty = { name: "", email: "", password: "", role: "user" };

export default function UsersPage() {
  const { t } = useTranslation();
  const { user: me } = useAuth();
  const [items, setItems] = useState(null);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => { api.get("/users").then((r) => setItems(r.data)); }, []);
  useEffect(() => { load(); }, [load]);

  const openNew = () => { setForm(empty); setEditing(null); setError(""); setModal(true); };
  const openEdit = (u) => { setForm({ name: u.name, email: u.email, password: "", role: u.role, active: u.active }); setEditing(u.id); setError(""); setModal(true); };

  const save = async () => {
    setError("");
    try {
      if (editing) {
        const payload = { name: form.name, role: form.role, active: form.active };
        if (form.password) payload.password = form.password;
        await api.put(`/users/${editing}`, payload);
      } else {
        await api.post("/users", form);
      }
      setModal(false); load();
    } catch (e) {
      setError(e.response?.data?.detail || "Error");
    }
  };
  const del = async (id) => {
    if (!window.confirm(t("common.confirmDelete"))) return;
    await api.delete(`/users/${id}`); load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const ROLE_COLOR = { admin: "high", manager: "negotiation", user: "qualified", guest: "lead" };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2"><Shield size={22} className="text-primary" />{t("users.title")}</h1>
        <Button onClick={openNew} data-testid="add-user-btn"><Plus size={16} /><span className="hidden sm:inline">{t("users.newUser")}</span></Button>
      </div>

      {!items ? <Spinner /> : (
        <div className="border border-border rounded-sm overflow-hidden stagger">
          {items.map((u) => (
            <div key={u.id} data-testid={`user-row-${u.id}`} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-0 hover:bg-surface/60 transition-colors">
              <div className="w-9 h-9 rounded-sm bg-primary/15 text-primary flex items-center justify-center text-sm font-bold shrink-0">{u.name?.[0]?.toUpperCase()}</div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium truncate">{u.name} {u.id === me.id && <span className="text-xs text-muted">(you)</span>}</div>
                <div className="text-xs text-muted truncate">{u.email}</div>
              </div>
              {!u.active && <Badge value="lost" label={t("users.disabled")} />}
              <Badge value={ROLE_COLOR[u.role]} label={t(`roles.${u.role}`)} />
              <div className="flex gap-1 shrink-0">
                <button onClick={() => openEdit(u)} data-testid={`edit-user-${u.id}`} className="p-1.5 rounded-sm hover:bg-border/60 text-muted transition-colors"><Pencil size={14} /></button>
                {u.id !== me.id && <button onClick={() => del(u.id)} data-testid={`delete-user-${u.id}`} className="p-1.5 rounded-sm hover:bg-danger/15 text-muted hover:text-danger transition-colors"><Trash2 size={14} /></button>}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={modal} onClose={() => setModal(false)} title={editing ? t("users.editUser") : t("users.newUser")}
        footer={<>
          <Button variant="ghost" onClick={() => setModal(false)}>{t("common.cancel")}</Button>
          <Button onClick={save} data-testid="save-user-btn">{t("common.save")}</Button>
        </>}>
        <Field label={t("users.name")}><Input data-testid="user-name" value={form.name} onChange={set("name")} /></Field>
        <Field label={t("users.email")}><Input data-testid="user-email" type="email" value={form.email} onChange={set("email")} disabled={!!editing} /></Field>
        <Field label={t("users.password") + (editing ? " (optional)" : "")}><Input data-testid="user-password" type="password" value={form.password} onChange={set("password")} /></Field>
        <Field label={t("users.role")}>
          <Select data-testid="user-role" value={form.role} onChange={set("role")}>{ROLES.map((r) => <option key={r} value={r}>{t(`roles.${r}`)}</option>)}</Select>
        </Field>
        {editing && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.active !== false} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
            {t("users.active")}
          </label>
        )}
        {error && <div className="text-sm text-danger">{error}</div>}
      </Modal>
    </div>
  );
}
