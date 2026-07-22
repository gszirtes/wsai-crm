import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Clock, Plus, Pencil, Trash2, Activity as ActIcon, Building2, User, Milestone as MilestoneIcon, MessageCircle } from "lucide-react";
import api, { formatApiError } from "../api";
import { useAuth, can } from "../auth";
import { Button, Input, Field, Select, Badge, Spinner, Modal } from "../components/common";
import VisibilityMembers from "../components/VisibilityMembers";
import { formatMoney } from "../format";

const WORK_STATUSES = ["in_progress", "client_review", "accepted"];
const PAYMENT_STATUSES = ["not_due", "invoiceable", "invoiced", "paid"];
const emptyMilestone = { name: "", due_date: "", mode: "percentage", amount: "", percentage: "" };

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
  const [milestones, setMilestones] = useState(null);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({ hours: "", description: "", billable: true });
  const [msModal, setMsModal] = useState(false);
  const [msForm, setMsForm] = useState(emptyMilestone);
  const [editingMs, setEditingMs] = useState(null);
  const [msError, setMsError] = useState("");
  const [contacts, setContacts] = useState([]);
  const [fuForm, setFuForm] = useState({ satisfaction_score: "", hasReferral: false, referred_contact_id: "" });
  const [fuError, setFuError] = useState("");

  const load = useCallback(() => {
    api.get(`/projects/${id}/detail`).then((r) => setData(r.data)).catch(() => navigate("/projects"));
    api.get(`/projects/${id}/milestones`).then((r) => setMilestones(r.data));
  }, [id, navigate]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/contacts").then((r) => setContacts(r.data)); }, []);

  if (!data) return <Spinner />;
  const p = data.project;

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

  const openNewMs = () => { setMsForm(emptyMilestone); setEditingMs(null); setMsError(""); setMsModal(true); };
  const openEditMs = (m) => {
    setMsForm({
      name: m.name, due_date: m.due_date ? m.due_date.slice(0, 10) : "",
      mode: m.percentage != null ? "percentage" : "amount",
      amount: m.amount ?? "", percentage: m.percentage ?? "",
    });
    setEditingMs(m.id); setMsError(""); setMsModal(true);
  };
  const saveMs = async () => {
    const activeValue = msForm.mode === "amount" ? msForm.amount : msForm.percentage;
    if (activeValue === "" || activeValue == null) {
      setMsError(t("milestone.valueRequired"));
      return;
    }
    const payload = {
      name: msForm.name,
      due_date: msForm.due_date || null,
      amount: msForm.mode === "amount" ? parseFloat(msForm.amount) || 0 : null,
      percentage: msForm.mode === "percentage" ? parseFloat(msForm.percentage) || 0 : null,
    };
    try {
      if (editingMs) await api.put(`/projects/${id}/milestones/${editingMs}`, payload);
      else await api.post(`/projects/${id}/milestones`, payload);
      setMsModal(false); setMsError(""); load();
    } catch (e) {
      console.error("Milestone save failed:", e);
      setMsError(formatApiError(e.response?.data?.detail) || e.message);
    }
  };
  const delMs = async (mid) => {
    if (!window.confirm(t("common.confirmDelete"))) return;
    try {
      await api.delete(`/projects/${id}/milestones/${mid}`); load();
    } catch (e) {
      console.error("Milestone delete failed:", e);
      setMsError(formatApiError(e.response?.data?.detail) || e.message);
    }
  };
  const setMsStatus = async (mid, patch) => {
    try {
      await api.patch(`/projects/${id}/milestones/${mid}/status`, patch);
      load();
    } catch (e) {
      console.error("Milestone status change failed:", e);
      setMsError(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const completeFollowUp = async () => {
    const payload = {
      satisfaction_score: fuForm.satisfaction_score ? parseInt(fuForm.satisfaction_score, 10) : null,
      referred_contact_id: fuForm.hasReferral && fuForm.referred_contact_id ? fuForm.referred_contact_id : null,
    };
    try {
      await api.post(`/projects/${id}/follow-up`, payload);
      setFuForm({ satisfaction_score: "", hasReferral: false, referred_contact_id: "" });
      setFuError("");
      load();
    } catch (e) {
      console.error("Follow-up completion failed:", e);
      setFuError(formatApiError(e.response?.data?.detail) || e.message);
    }
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

      {(p.closed_at || p.satisfaction_score != null) && (
        <div className="flex items-center gap-4 text-xs text-muted">
          {p.closed_at && <span>{t("project.closedAt")}: {new Date(p.closed_at).toLocaleDateString()}</span>}
          {p.satisfaction_score != null && <span data-testid="satisfaction-score">{t("followup.satisfaction")}: {p.satisfaction_score}/5</span>}
        </div>
      )}

      {data.pending_follow_up && (
        <div className="border border-amber-500/40 rounded-sm p-6" data-testid="follow-up-card">
          <h3 className="font-display font-bold flex items-center gap-2 mb-1"><MessageCircle size={18} className="text-amber-500" />{t("followup.title")}</h3>
          <p className="text-sm text-muted mb-4">{t("followup.hint")}</p>
          {writable ? (
            <>
              {fuError && <p className="text-sm text-danger mb-3">{fuError}</p>}
              <Field label={t("followup.satisfaction")}>
                <Select data-testid="followup-satisfaction" value={fuForm.satisfaction_score}
                  onChange={(e) => setFuForm({ ...fuForm, satisfaction_score: e.target.value })}>
                  <option value="">—</option>
                  {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                </Select>
              </Field>
              <label className="flex items-center gap-2 text-sm mt-3">
                <input type="checkbox" data-testid="followup-has-referral" checked={fuForm.hasReferral}
                  onChange={(e) => setFuForm({ ...fuForm, hasReferral: e.target.checked })} />
                {t("followup.hasReferral")}
              </label>
              {fuForm.hasReferral && (
                <Field label={t("followup.referredContact")}>
                  <Select data-testid="followup-referred-contact" value={fuForm.referred_contact_id}
                    onChange={(e) => setFuForm({ ...fuForm, referred_contact_id: e.target.value })}>
                    <option value="">—</option>
                    {contacts.map((c) => <option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>)}
                  </Select>
                </Field>
              )}
              <Button onClick={completeFollowUp} data-testid="complete-followup-btn" className="mt-4">{t("followup.complete")}</Button>
            </>
          ) : (
            <p className="text-sm text-muted">{t("followup.readOnlyHint")}</p>
          )}
        </div>
      )}

      {/* Milestones (client-facing billing view -- shown before the internal hourly figures, per plan 4.5) */}
      <div className="border border-border rounded-sm p-6" data-testid="milestones-panel">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold flex items-center gap-2"><MilestoneIcon size={18} className="text-primary" />{t("milestone.title")}</h3>
          {writable && <Button onClick={openNewMs} data-testid="add-milestone-btn"><Plus size={16} />{t("milestone.add")}</Button>}
        </div>
        {msError && <p className="text-sm text-danger mb-3" data-testid="milestone-error">{msError}</p>}
        {milestones?.budget_mismatch && (
          <p className="text-xs text-amber-600 mb-3" data-testid="milestone-mismatch-warning">{t("milestone.budgetMismatch")}</p>
        )}
        {milestones?.total_amount != null && (
          <p className="text-xs text-muted mb-3">
            {t("milestone.totalVsBudget", { total: formatMoney(milestones.total_amount, p.currency), budget: formatMoney(milestones.budget, p.currency) })}
          </p>
        )}
        <div className="divide-y divide-border">
          {!milestones || milestones.milestones.length === 0 ? (
            <p className="text-sm text-muted py-3">{t("milestone.none")}</p>
          ) : milestones.milestones.map((m) => (
            <div key={m.id} data-testid={`milestone-${m.id}`} className="py-3 flex items-center gap-3 flex-wrap">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium truncate">{m.name}</div>
                <div className="text-xs text-muted">
                  {m.percentage != null ? `${m.percentage}%` : formatMoney(m.amount, p.currency)}
                  {m.due_date && ` · ${new Date(m.due_date).toLocaleDateString()}`}
                </div>
              </div>
              {writable ? (
                <>
                  <Select value={m.work_status} onChange={(e) => setMsStatus(m.id, { work_status: e.target.value })}
                    data-testid={`ms-work-status-${m.id}`} className="!w-auto text-xs">
                    {WORK_STATUSES.map((s) => <option key={s} value={s}>{t(`milestone.workStatus_${s}`)}</option>)}
                  </Select>
                  <Select value={m.payment_status} onChange={(e) => setMsStatus(m.id, { payment_status: e.target.value })}
                    data-testid={`ms-payment-status-${m.id}`} className="!w-auto text-xs">
                    {PAYMENT_STATUSES.map((s) => <option key={s} value={s}>{t(`milestone.paymentStatus_${s}`)}</option>)}
                  </Select>
                  <button onClick={() => openEditMs(m)} className="p-1.5 rounded-sm hover:bg-border/60 text-muted transition-colors"><Pencil size={14} /></button>
                  <button onClick={() => delMs(m.id)} className="p-1.5 rounded-sm hover:bg-danger/15 text-muted hover:text-danger transition-colors"><Trash2 size={14} /></button>
                </>
              ) : (
                <>
                  <Badge value={m.work_status} label={t(`milestone.workStatus_${m.work_status}`)} />
                  <Badge value={m.payment_status} label={t(`milestone.paymentStatus_${m.payment_status}`)} />
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Time & effort */}
      <div className="border border-border rounded-sm p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="font-display font-bold flex items-center gap-2"><Clock size={18} className="text-primary" />{t("time.title")}</h3>
            <p className="text-xs text-muted mt-1">{t("time.internalHint")}</p>
          </div>
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
            <div className="font-display text-2xl font-bold mt-1">{formatMoney(data.billable_amount, p.currency)}</div>
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

      <Modal open={msModal} onClose={() => setMsModal(false)} title={editingMs ? t("milestone.edit") : t("milestone.add")}
        footer={<>
          <Button variant="ghost" onClick={() => setMsModal(false)}>{t("common.cancel")}</Button>
          <Button onClick={saveMs} data-testid="save-milestone-btn">{t("common.save")}</Button>
        </>}>
        <Field label={t("milestone.name")}><Input data-testid="milestone-name" value={msForm.name} onChange={(e) => setMsForm({ ...msForm, name: e.target.value })} /></Field>
        <Field label={t("milestone.dueDate")}><Input type="date" value={msForm.due_date} onChange={(e) => setMsForm({ ...msForm, due_date: e.target.value })} /></Field>
        <div className="flex gap-2">
          <Button type="button" variant={msForm.mode === "amount" ? "primary" : "subtle"} className="py-1.5 px-3 text-xs"
            onClick={() => setMsForm({ ...msForm, mode: "amount" })}>{t("milestone.byAmount")}</Button>
          <Button type="button" variant={msForm.mode === "percentage" ? "primary" : "subtle"} className="py-1.5 px-3 text-xs"
            onClick={() => setMsForm({ ...msForm, mode: "percentage" })}>{t("milestone.byPercentage")}</Button>
        </div>
        {msForm.mode === "amount" ? (
          <Field label={t("milestone.amount")}><Input data-testid="milestone-amount" type="number" value={msForm.amount} onChange={(e) => setMsForm({ ...msForm, amount: e.target.value })} /></Field>
        ) : (
          <Field label={t("milestone.percentage")}><Input data-testid="milestone-percentage" type="number" value={msForm.percentage} onChange={(e) => setMsForm({ ...msForm, percentage: e.target.value })} /></Field>
        )}
      </Modal>
    </div>
  );
}
