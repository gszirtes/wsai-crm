import React, { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Plus, Pencil, Trash2, FolderKanban, Clock } from "lucide-react";
import api from "../api";
import { useAuth, can } from "../auth";
import { Button, Input, Select, Field, Modal, Badge, EmptyState, Spinner, Textarea, Pagination } from "../components/common";

const STATUSES = ["planning", "active", "on_hold", "completed", "cancelled"];
const PRIORITIES = ["low", "medium", "high"];
const PAGE_SIZE = 12;
const empty = { name: "", description: "", status: "planning", priority: "medium", budget: 0, estimated_hours: 0, hourly_rate: 0, currency: "EUR", company_id: "" };

export default function Projects() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const writable = can.write(user);
  const [items, setItems] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [status, setStatus] = useState("");
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const load = useCallback(() => {
    api.get("/projects", { params: { status, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE } })
      .then((r) => { setItems(r.data); setTotal(parseInt(r.headers["x-total-count"] || "0", 10)); });
  }, [status, page]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [status]);
  useEffect(() => { api.get("/companies").then((r) => setCompanies(r.data)); }, []);

  const openNew = () => { setForm(empty); setEditing(null); setModal(true); };
  const openEdit = (p) => { setForm({ ...empty, ...p, company_id: p.company_id || "" }); setEditing(p.id); setModal(true); };
  const save = async () => {
    const payload = { ...form, budget: parseFloat(form.budget) || 0, estimated_hours: parseFloat(form.estimated_hours) || 0, hourly_rate: parseFloat(form.hourly_rate) || 0, company_id: form.company_id || null };
    if (editing) await api.put(`/projects/${editing}`, payload);
    else await api.post("/projects", payload);
    setModal(false); load();
  };
  const del = async (id) => {
    if (!window.confirm(t("common.confirmDelete"))) return;
    await api.delete(`/projects/${id}`); load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const eur = (n) => "€" + new Intl.NumberFormat().format(n || 0);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{t("project.title")}</h1>
        <div className="flex items-center gap-2">
          <Select data-testid="project-status-filter" value={status} onChange={(e) => setStatus(e.target.value)} className="w-36 hidden sm:block">
            <option value="">{t("common.all")}</option>
            {STATUSES.map((s) => <option key={s} value={s}>{t(`statuses.${s}`)}</option>)}
          </Select>
          {writable && <Button onClick={openNew} data-testid="add-project-btn"><Plus size={16} /><span className="hidden sm:inline">{t("project.newProject")}</span></Button>}
        </div>
      </div>

      {!items ? <Spinner /> : items.length === 0 ? (
        <EmptyState title={t("common.noResults")} action={writable && <Button onClick={openNew}><Plus size={16} />{t("project.newProject")}</Button>} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 stagger">
          {items.map((p) => (
            <div key={p.id} data-testid={`project-card-${p.id}`} onClick={() => navigate(`/projects/${p.id}`)} className="border border-border rounded-sm p-5 hover:-translate-y-px transition-transform duration-200 cursor-pointer">
              <div className="flex items-start justify-between gap-2">
                <div className="w-10 h-10 rounded-sm bg-primary/15 text-primary flex items-center justify-center shrink-0"><FolderKanban size={18} /></div>
                <div className="flex items-center gap-2 flex-wrap justify-end">
                  <Badge value={p.health} label={t(`health.${p.health}`)} />
                  <Badge value={p.priority} label={t(`statuses.${p.priority}`)} />
                  <Badge value={p.status} label={t(`statuses.${p.status}`)} />
                </div>
              </div>
              <div className="font-display font-bold text-lg mt-3">{p.name}</div>
              {p.description && <p className="text-sm text-muted mt-1 line-clamp-2">{p.description}</p>}
              <div className="flex items-center justify-between mt-4 text-sm">
                <span className="text-muted flex items-center gap-1"><Clock size={13} />{p.logged_hours || 0}h / {p.estimated_hours || 0}h</span>
                <span className="font-medium">{eur(p.budget)}</span>
              </div>
              {writable && (
                <div className="flex gap-1 mt-3 pt-3 border-t border-border">
                  <button onClick={(e) => { e.stopPropagation(); openEdit(p); }} data-testid={`edit-project-${p.id}`} className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-sm text-xs text-muted hover:bg-surface transition-colors"><Pencil size={13} />{t("common.edit")}</button>
                  <button onClick={(e) => { e.stopPropagation(); del(p.id); }} data-testid={`delete-project-${p.id}`} className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-sm text-xs text-muted hover:text-danger hover:bg-danger/10 transition-colors"><Trash2 size={13} />{t("common.delete")}</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {items && items.length > 0 && (
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
      )}

      <Modal open={modal} onClose={() => setModal(false)} title={editing ? t("project.editProject") : t("project.newProject")}
        footer={<>
          <Button variant="ghost" onClick={() => setModal(false)}>{t("common.cancel")}</Button>
          <Button onClick={save} data-testid="save-project-btn">{t("common.save")}</Button>
        </>}>
        <Field label={t("project.name")}><Input data-testid="project-name" value={form.name} onChange={set("name")} /></Field>
        <Field label={t("project.description")}><Textarea rows={3} value={form.description || ""} onChange={set("description")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("project.status")}>
            <Select value={form.status} onChange={set("status")}>{STATUSES.map((s) => <option key={s} value={s}>{t(`statuses.${s}`)}</option>)}</Select>
          </Field>
          <Field label={t("project.priority")}>
            <Select value={form.priority} onChange={set("priority")}>{PRIORITIES.map((s) => <option key={s} value={s}>{t(`statuses.${s}`)}</option>)}</Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("project.budget")}><Input type="number" value={form.budget} onChange={set("budget")} /></Field>
          <Field label={t("project.company")}>
            <Select value={form.company_id || ""} onChange={set("company_id")}>
              <option value="">—</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("time.estimated") + " (" + t("time.hours").toLowerCase() + ")"}><Input data-testid="project-estimated-hours" type="number" value={form.estimated_hours} onChange={set("estimated_hours")} /></Field>
          <Field label={t("time.rate")}><Input data-testid="project-hourly-rate" type="number" value={form.hourly_rate} onChange={set("hourly_rate")} /></Field>
        </div>
      </Modal>
    </div>
  );
}
