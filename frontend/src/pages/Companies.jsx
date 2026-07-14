import React, { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Plus, Search, Pencil, Trash2, Globe, Building2 } from "lucide-react";
import api from "../api";
import { useAuth, can } from "../auth";
import { Button, Input, Field, Modal, EmptyState, Spinner, Textarea } from "../components/common";

const empty = { name: "", industry: "", website: "", phone: "", email: "", address: "", size: "", notes: "" };

export default function Companies() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const writable = can.write(user);
  const [items, setItems] = useState(null);
  const [search, setSearch] = useState("");
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(null);

  const load = useCallback(() => {
    api.get("/companies", { params: { search } }).then((r) => setItems(r.data));
  }, [search]);
  useEffect(() => { load(); }, [load]);

  const openNew = () => { setForm(empty); setEditing(null); setModal(true); };
  const openEdit = (c) => { setForm({ ...empty, ...c }); setEditing(c.id); setModal(true); };
  const save = async () => {
    if (editing) await api.put(`/companies/${editing}`, form);
    else await api.post("/companies", form);
    setModal(false); load();
  };
  const del = async (id) => {
    if (!window.confirm(t("common.confirmDelete"))) return;
    await api.delete(`/companies/${id}`); load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{t("company.title")}</h1>
        {writable && <Button onClick={openNew} data-testid="add-company-btn"><Plus size={16} /><span className="hidden sm:inline">{t("company.newCompany")}</span></Button>}
      </div>

      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <Input data-testid="company-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t("common.search")} className="pl-9" />
      </div>

      {!items ? <Spinner /> : items.length === 0 ? (
        <EmptyState title={t("common.noResults")} action={writable && <Button onClick={openNew}><Plus size={16} />{t("company.newCompany")}</Button>} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger">
          {items.map((c) => (
            <div key={c.id} data-testid={`company-card-${c.id}`} className="border border-border rounded-sm p-5 hover:-translate-y-px transition-transform duration-200">
              <div className="flex items-start justify-between">
                <div className="w-10 h-10 rounded-sm bg-glow/15 text-glow flex items-center justify-center shrink-0"><Building2 size={18} /></div>
                {writable && (
                  <div className="flex gap-1">
                    <button onClick={() => openEdit(c)} data-testid={`edit-company-${c.id}`} className="p-1.5 rounded-sm hover:bg-border/60 text-muted transition-colors"><Pencil size={14} /></button>
                    <button onClick={() => del(c.id)} data-testid={`delete-company-${c.id}`} className="p-1.5 rounded-sm hover:bg-danger/15 text-muted hover:text-danger transition-colors"><Trash2 size={14} /></button>
                  </div>
                )}
              </div>
              <div className="font-display font-bold text-lg mt-3 truncate">{c.name}</div>
              <div className="text-sm text-muted">{c.industry || "—"}{c.size && ` · ${c.size}`}</div>
              {c.website && (
                <a href={`https://${c.website.replace(/^https?:\/\//, "")}`} target="_blank" rel="noreferrer" className="text-xs text-primary flex items-center gap-1 mt-2 hover:underline">
                  <Globe size={12} /> {c.website}
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      <Modal open={modal} onClose={() => setModal(false)} title={editing ? t("company.editCompany") : t("company.newCompany")}
        footer={<>
          <Button variant="ghost" onClick={() => setModal(false)}>{t("common.cancel")}</Button>
          <Button onClick={save} data-testid="save-company-btn">{t("common.save")}</Button>
        </>}>
        <Field label={t("company.name")}><Input data-testid="company-name" value={form.name} onChange={set("name")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("company.industry")}><Input value={form.industry || ""} onChange={set("industry")} /></Field>
          <Field label={t("company.size")}><Input value={form.size || ""} onChange={set("size")} /></Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("company.website")}><Input value={form.website || ""} onChange={set("website")} /></Field>
          <Field label={t("company.phone")}><Input value={form.phone || ""} onChange={set("phone")} /></Field>
        </div>
        <Field label={t("company.email")}><Input type="email" value={form.email || ""} onChange={set("email")} /></Field>
        <Field label={t("company.address")}><Input value={form.address || ""} onChange={set("address")} /></Field>
        <Field label={t("company.notes")}><Textarea rows={3} value={form.notes || ""} onChange={set("notes")} /></Field>
      </Modal>
    </div>
  );
}
