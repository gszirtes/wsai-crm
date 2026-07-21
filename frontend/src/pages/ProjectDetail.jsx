import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Clock, Plus, Trash2, Activity as ActIcon, Building2, User } from "lucide-react";
import api from "../api";
import { useAuth, can } from "../auth";
import { Button, Input, Field, Badge, Spinner, Modal } from "../components/common";
import VisibilityMembers from "../components/VisibilityMembers";

function Bar({ value, max, color = "bg-primary" }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="h-2 rounded-sm bg-border overflow-hidden">
      <div className={`h-full ${color} transition-[width] duration-500`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function ProjectDetail() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const writable = can.write(user);
  const [data, setData] = useState(null);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({ hours: "", description: "", billable: true });

  const load = useCallback(() => {
    api.get(`/projects/${id}/detail`).then((r) => setData(r.data)).catch(() => navigate("/projects"));
  }, [id, navigate]);
  useEffect(() => { load(); }, [load]);

  if (!data) return <Spinner />;
  const p = data.project;
  const eur = (n) => (n == null ? "—" : "€" + new Intl.NumberFormat().format(n));

  const addTime = async () => {
    await api.post(`/projects/${id}/time`, {
      hours: parseFloat(form.hours) || 0,
      description: form.description,
      billable: form.billable,
    });
    setModal(false); setForm({ hours: "", description: "", billable: true }); load();
  };
  const delTime = async (eid) => {
    if (!window.confirm(t("common.confirmDelete"))) return;
    await api.delete(`/projects/${id}/time/${eid}`); load();
  };

  const remaining = Math.max(0, (p.estimated_hours || 0) - data.logged_hours);
  const overBudget = p.estimated_hours > 0 && data.logged_hours > p.estimated_hours;

  return (
    <div className="space-y-6">
      <button onClick={() => navigate("/projects")} data-testid="detail-back" className="flex items-center gap-1 text-sm text-muted hover:text-txt transition-colors">
        <ArrowLeft size={16} /> {t("detail.back")}
      </button>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{p.name}</h1>
          <div className="flex items-center gap-3 mt-2 text-sm text-muted">
            {data.company_name && <span className="flex items-center gap-1"><Building2 size={14} />{data.company_name}</span>}
            {data.contact_name && <span className="flex items-center gap-1"><User size={14} />{data.contact_name}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge value={p.priority} label={t(`statuses.${p.priority}`)} />
          <Badge value={p.status} label={t(`statuses.${p.status}`)} />
          <Badge value={data.health} label={t(`health.${data.health}`)} />
        </div>
      </div>

      {p.description && <p className="text-sm text-muted max-w-2xl">{p.description}</p>}

      {/* Time & effort */}
      <div className="border border-border rounded-sm p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-display font-bold flex items-center gap-2"><Clock size={18} className="text-primary" />{t("time.title")}</h3>
          {writable && <Button onClick={() => setModal(true)} data-testid="log-time-btn"><Plus size={16} />{t("time.addTime")}</Button>}
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
          <div data-testid="time-logged">
            <div className="text-xs uppercase tracking-[0.15em] text-muted">{t("time.logged")}</div>
            <div className="font-display text-2xl font-bold mt-1">{data.logged_hours}h</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.15em] text-muted">{t("time.estimated")}</div>
            <div className="font-display text-2xl font-bold mt-1">{p.estimated_hours || 0}h</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.15em] text-muted">{t("time.remaining")}</div>
            <div className={`font-display text-2xl font-bold mt-1 ${overBudget ? "text-danger" : ""}`}>{overBudget ? "-" : ""}{overBudget ? (data.logged_hours - p.estimated_hours) : remaining}h</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.15em] text-muted">{t("time.amount")}</div>
            <div className="font-display text-2xl font-bold mt-1">{eur(data.billable_amount)}</div>
          </div>
        </div>
        <Bar value={data.logged_hours} max={p.estimated_hours || data.logged_hours || 1} color={overBudget ? "bg-danger" : "bg-primary"} />

        <div className="mt-5 divide-y divide-border">
          {data.time_entries.length === 0 ? (
            <p className="text-sm text-muted py-3">{t("time.noEntries")}</p>
          ) : data.time_entries.map((e) => (
            <div key={e.id} data-testid={`time-entry-${e.id}`} className="flex items-center gap-3 py-3">
              <div className="w-10 text-center font-display font-bold">{e.hours}h</div>
              <div className="min-w-0 flex-1">
                <div className="text-sm truncate">{e.description || "—"}</div>
                <div className="text-xs text-muted">{e.user_name} · {e.entry_date ? new Date(e.entry_date).toLocaleDateString() : ""}{e.billable ? " · " + t("time.billable") : ""}</div>
              </div>
              {writable && <button onClick={() => delTime(e.id)} className="p-1.5 rounded-sm text-muted hover:text-danger transition-colors"><Trash2 size={14} /></button>}
            </div>
          ))}
        </div>
      </div>

      {/* Activity timeline */}
      <div className="border border-border rounded-sm p-6">
        <h3 className="font-display font-bold flex items-center gap-2 mb-4"><ActIcon size={18} className="text-glow" />{t("detail.timeline")}</h3>
        {data.activities.length === 0 ? (
          <p className="text-sm text-muted">{t("detail.noActivities")}</p>
        ) : (
          <div className="space-y-3">
            {data.activities.map((a) => (
              <div key={a.id} className="flex items-start gap-3">
                <span className="mt-1.5 w-2 h-2 rounded-full bg-primary shrink-0" />
                <div>
                  <div className="text-sm">{a.subject}</div>
                  <div className="text-xs text-muted">{t(`statuses.${a.type}`)}{a.completed ? " · ✓" : ""}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <VisibilityMembers entityType="project" entityId={id} visibility={p.visibility} ownerId={p.owner_id}
        writable={writable} onVisibilityChange={load} />

      <Modal open={modal} onClose={() => setModal(false)} title={t("time.logHours")}
        footer={<>
          <Button variant="ghost" onClick={() => setModal(false)}>{t("common.cancel")}</Button>
          <Button onClick={addTime} data-testid="save-time-btn">{t("common.save")}</Button>
        </>}>
        <Field label={t("time.hours")}><Input data-testid="time-hours" type="number" step="0.25" value={form.hours} onChange={(e) => setForm({ ...form, hours: e.target.value })} /></Field>
        <Field label={t("activity.description")}><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.billable} onChange={(e) => setForm({ ...form, billable: e.target.checked })} /> {t("time.billable")}
        </label>
      </Modal>
    </div>
  );
}
