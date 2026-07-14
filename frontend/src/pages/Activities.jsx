import React, { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Plus, Pencil, Trash2, Phone, Mail, Users, CheckSquare, StickyNote, Check } from "lucide-react";
import api from "../api";
import { useAuth, can } from "../auth";
import { Button, Input, Select, Field, Modal, Badge, EmptyState, Spinner, Textarea } from "../components/common";

const TYPES = ["task", "call", "email", "meeting", "note"];
const TYPE_ICONS = { call: Phone, email: Mail, meeting: Users, task: CheckSquare, note: StickyNote };
const empty = { type: "task", subject: "", description: "", due_date: "", contact_id: "" };

export default function Activities() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const writable = can.write(user);
  const [items, setItems] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [filter, setFilter] = useState("");
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(null);

  const load = useCallback(() => {
    api.get("/activities", { params: { completed: filter } }).then((r) => setItems(r.data));
  }, [filter]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/contacts").then((r) => setContacts(r.data)); }, []);

  const openNew = () => { setForm(empty); setEditing(null); setModal(true); };
  const openEdit = (a) => {
    setForm({ ...empty, ...a, contact_id: a.contact_id || "", due_date: a.due_date ? a.due_date.slice(0, 10) : "" });
    setEditing(a.id); setModal(true);
  };
  const save = async () => {
    const payload = { ...form, contact_id: form.contact_id || null, due_date: form.due_date || null };
    if (editing) await api.put(`/activities/${editing}`, payload);
    else await api.post("/activities", payload);
    setModal(false); load();
  };
  const toggle = async (id) => { await api.patch(`/activities/${id}/toggle`); load(); };
  const del = async (id) => {
    if (!window.confirm(t("common.confirmDelete"))) return;
    await api.delete(`/activities/${id}`); load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{t("activity.title")}</h1>
        <div className="flex items-center gap-2">
          <Select data-testid="activity-filter" value={filter} onChange={(e) => setFilter(e.target.value)} className="w-36 hidden sm:block">
            <option value="">{t("common.all")}</option>
            <option value="false">{t("dashboard.openTasks")}</option>
            <option value="true">{t("activity.completed")}</option>
          </Select>
          {writable && <Button onClick={openNew} data-testid="add-activity-btn"><Plus size={16} /><span className="hidden sm:inline">{t("activity.newActivity")}</span></Button>}
        </div>
      </div>

      {!items ? <Spinner /> : items.length === 0 ? (
        <EmptyState title={t("common.noResults")} action={writable && <Button onClick={openNew}><Plus size={16} />{t("activity.newActivity")}</Button>} />
      ) : (
        <div className="border border-border rounded-sm overflow-hidden stagger">
          {items.map((a) => {
            const Icon = TYPE_ICONS[a.type] || CheckSquare;
            return (
              <div key={a.id} data-testid={`activity-row-${a.id}`} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-0 hover:bg-surface/60 transition-colors">
                {writable ? (
                  <button onClick={() => toggle(a.id)} data-testid={`toggle-activity-${a.id}`}
                    className={`w-5 h-5 rounded-sm border flex items-center justify-center shrink-0 transition-colors ${a.completed ? "bg-success border-success text-white" : "border-border hover:border-primary"}`}>
                    {a.completed && <Check size={13} />}
                  </button>
                ) : (
                  <span className={`w-5 h-5 rounded-sm border flex items-center justify-center shrink-0 ${a.completed ? "bg-success border-success text-white" : "border-border"}`}>{a.completed && <Check size={13} />}</span>
                )}
                <Icon size={16} className="text-muted shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className={`text-sm font-medium truncate ${a.completed ? "line-through text-muted" : ""}`}>{a.subject}</div>
                  {a.description && <div className="text-xs text-muted truncate">{a.description}</div>}
                </div>
                <Badge value={a.type} label={t(`statuses.${a.type}`)} className="hidden sm:inline-flex" />
                {a.due_date && <span className="text-xs text-muted shrink-0">{new Date(a.due_date).toLocaleDateString()}</span>}
                {writable && (
                  <div className="flex gap-1 shrink-0">
                    <button onClick={() => openEdit(a)} className="p-1.5 rounded-sm hover:bg-border/60 text-muted transition-colors"><Pencil size={14} /></button>
                    <button onClick={() => del(a.id)} className="p-1.5 rounded-sm hover:bg-danger/15 text-muted hover:text-danger transition-colors"><Trash2 size={14} /></button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <Modal open={modal} onClose={() => setModal(false)} title={editing ? t("activity.editActivity") : t("activity.newActivity")}
        footer={<>
          <Button variant="ghost" onClick={() => setModal(false)}>{t("common.cancel")}</Button>
          <Button onClick={save} data-testid="save-activity-btn">{t("common.save")}</Button>
        </>}>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("activity.type")}>
            <Select value={form.type} onChange={set("type")}>{TYPES.map((s) => <option key={s} value={s}>{t(`statuses.${s}`)}</option>)}</Select>
          </Field>
          <Field label={t("activity.dueDate")}><Input type="date" value={form.due_date || ""} onChange={set("due_date")} /></Field>
        </div>
        <Field label={t("activity.subject")}><Input data-testid="activity-subject" value={form.subject} onChange={set("subject")} /></Field>
        <Field label={t("activity.description")}><Textarea rows={3} value={form.description || ""} onChange={set("description")} /></Field>
        <Field label={t("contact.title")}>
          <Select value={form.contact_id || ""} onChange={set("contact_id")}>
            <option value="">—</option>
            {contacts.map((c) => <option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>)}
          </Select>
        </Field>
      </Modal>
    </div>
  );
}
