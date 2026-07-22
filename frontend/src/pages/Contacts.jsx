import React, { useEffect, useState, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Plus, Search, Pencil, Trash2, Mail, Phone, Download, Upload } from "lucide-react";
import api from "../api";
import { useAuth, can } from "../auth";
import { Button, Input, Select, Field, Modal, Badge, EmptyState, Spinner, Textarea, Toast } from "../components/common";

const STATUSES = ["lead", "prospect", "customer", "inactive"];
const REFERRER_TAG = "referrer";
const empty = { first_name: "", last_name: "", email: "", phone: "", title: "", status: "lead", company_id: "", notes: "" };

export default function Contacts() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const writable = can.write(user);
  const [items, setItems] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [referrersOnly, setReferrersOnly] = useState(false);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(null);
  const [toast, setToast] = useState(null);

  const load = useCallback(() => {
    api.get("/contacts", { params: { search, status } }).then((r) => setItems(r.data));
  }, [search, status]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/companies").then((r) => setCompanies(r.data)); }, []);

  const openNew = () => { setForm(empty); setEditing(null); setModal(true); };
  const openEdit = (c) => {
    setForm({ ...empty, ...c, company_id: c.company_id || "" });
    setEditing(c.id); setModal(true);
  };

  const save = async () => {
    const payload = { ...form, company_id: form.company_id || null };
    if (editing) await api.put(`/contacts/${editing}`, payload);
    else await api.post("/contacts", payload);
    setModal(false); load();
  };

  const del = async (id) => {
    if (!window.confirm(t("common.confirmDelete"))) return;
    await api.delete(`/contacts/${id}`); load();
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const visibleItems = (items || []).filter((c) => !referrersOnly || (c.tags || []).includes(REFERRER_TAG));

  const exportCsv = () => {
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/export/contacts.csv`;
    window.open(url, "_blank");
  };
  const importCsv = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    const r = await api.post("/import/contacts", fd, { headers: { "Content-Type": "multipart/form-data" } });
    const errs = r.data.errors?.length || 0;
    setToast({
      message: `${r.data.created} ${t("io.importDone")}${errs ? ` · ${errs} ${t("io.errors")}` : ""}`,
      type: errs ? "info" : "success",
    });
    setTimeout(() => setToast(null), 4000);
    e.target.value = "";
    load();
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{t("contact.title")}</h1>
        <div className="flex items-center gap-2">
          <button onClick={exportCsv} data-testid="export-contacts-btn" title={t("io.export")} className="p-2.5 rounded-sm border border-border text-muted hover:bg-surface transition-colors"><Download size={16} /></button>
          {writable && <>
            <input ref={fileRef} type="file" accept=".csv" onChange={importCsv} className="hidden" data-testid="import-contacts-input" />
            <button onClick={() => fileRef.current?.click()} data-testid="import-contacts-btn" title={t("io.import")} className="p-2.5 rounded-sm border border-border text-muted hover:bg-surface transition-colors"><Upload size={16} /></button>
            <Button onClick={openNew} data-testid="add-contact-btn"><Plus size={16} /><span className="hidden sm:inline">{t("contact.newContact")}</span></Button>
          </>}
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <Input data-testid="contact-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t("common.search")} className="pl-9" />
        </div>
        <Select data-testid="contact-status-filter" value={status} onChange={(e) => setStatus(e.target.value)} className="sm:w-48">
          <option value="">{t("common.all")}</option>
          {STATUSES.map((s) => <option key={s} value={s}>{t(`statuses.${s}`)}</option>)}
        </Select>
        <Button variant={referrersOnly ? "primary" : "subtle"} className="py-1.5 px-3 text-xs whitespace-nowrap"
          onClick={() => setReferrersOnly(!referrersOnly)} data-testid="referrers-only-filter">
          {t("contact.referrersOnly")}
        </Button>
      </div>

      {!items ? <Spinner /> : visibleItems.length === 0 ? (
        <EmptyState title={t("common.noResults")} action={writable && <Button onClick={openNew}><Plus size={16} />{t("contact.newContact")}</Button>} />
      ) : (
        <div className="border border-border rounded-sm overflow-hidden stagger">
          {visibleItems.map((c) => (
            <div key={c.id} data-testid={`contact-row-${c.id}`} onClick={() => navigate(`/contacts/${c.id}`)} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-0 hover:bg-surface/60 transition-colors cursor-pointer">
              <div className="w-9 h-9 rounded-sm bg-primary/15 text-primary flex items-center justify-center text-sm font-bold shrink-0">
                {c.first_name?.[0]?.toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium truncate">
                  {c.first_name} {c.last_name} {c.title && <span className="text-muted font-normal">· {c.title}</span>}
                </div>
                <div className="text-xs text-muted truncate flex items-center gap-3">
                  {c.company_name && <span>{c.company_name}</span>}
                  {c.email && <span className="hidden sm:flex items-center gap-1"><Mail size={11} />{c.email}</span>}
                  {c.phone && <span className="hidden sm:flex items-center gap-1"><Phone size={11} />{c.phone}</span>}
                </div>
              </div>
              <Badge value={c.status} label={t(`statuses.${c.status}`)} />
              {(c.tags || []).includes(REFERRER_TAG) && <Badge value="won" label={t("contact.regularReferrer")} />}
              {writable && (
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={(e) => { e.stopPropagation(); openEdit(c); }} data-testid={`edit-contact-${c.id}`} className="p-1.5 rounded-sm hover:bg-border/60 text-muted transition-colors"><Pencil size={14} /></button>
                  <button onClick={(e) => { e.stopPropagation(); del(c.id); }} data-testid={`delete-contact-${c.id}`} className="p-1.5 rounded-sm hover:bg-danger/15 text-muted hover:text-danger transition-colors"><Trash2 size={14} /></button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <Modal open={modal} onClose={() => setModal(false)} title={editing ? t("contact.editContact") : t("contact.newContact")}
        footer={<>
          <Button variant="ghost" onClick={() => setModal(false)}>{t("common.cancel")}</Button>
          <Button onClick={save} data-testid="save-contact-btn">{t("common.save")}</Button>
        </>}>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("contact.first_name")}><Input data-testid="contact-first-name" value={form.first_name} onChange={set("first_name")} /></Field>
          <Field label={t("contact.last_name")}><Input value={form.last_name || ""} onChange={set("last_name")} /></Field>
        </div>
        <Field label={t("contact.email")}><Input type="email" value={form.email || ""} onChange={set("email")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("contact.phone")}><Input value={form.phone || ""} onChange={set("phone")} /></Field>
          <Field label={t("contact.jobtitle")}><Input value={form.title || ""} onChange={set("title")} /></Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("contact.status")}>
            <Select value={form.status} onChange={set("status")}>
              {STATUSES.map((s) => <option key={s} value={s}>{t(`statuses.${s}`)}</option>)}
            </Select>
          </Field>
          <Field label={t("contact.company")}>
            <Select value={form.company_id || ""} onChange={set("company_id")}>
              <option value="">—</option>
              {companies.map((co) => <option key={co.id} value={co.id}>{co.name}</option>)}
            </Select>
          </Field>
        </div>
        <Field label={t("contact.notes")}><Textarea rows={3} value={form.notes || ""} onChange={set("notes")} /></Field>
      </Modal>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
