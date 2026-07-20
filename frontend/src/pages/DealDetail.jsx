import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Building2, User, Activity as ActIcon, Plus } from "lucide-react";
import api from "../api";
import { useAuth, can } from "../auth";
import { Badge, Spinner, Button, Modal, Field, Input, Textarea, Select } from "../components/common";

const TYPES = ["call", "email", "meeting", "task", "note"];
const emptyActivity = { type: "call", direction: "", subject: "", description: "" };

export default function DealDetail() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const writable = can.write(user);
  const [data, setData] = useState(null);
  const [modal, setModal] = useState(false);
  const [activity, setActivity] = useState(emptyActivity);

  const load = useCallback(() => {
    api.get(`/deals/${id}/detail`).then((r) => setData(r.data)).catch(() => navigate("/deals"));
  }, [id, navigate]);
  useEffect(() => { load(); }, [load]);

  const logActivity = async () => {
    await api.post("/activities", {
      type: activity.type,
      direction: activity.direction || null,
      subject: activity.subject,
      description: activity.description,
      deal_id: id,
    });
    setModal(false);
    setActivity(emptyActivity);
    load();
  };
  const set = (k) => (e) => setActivity({ ...activity, [k]: e.target.value });

  if (!data) return <Spinner />;
  const d = data.deal;
  const eur = (n) => "€" + new Intl.NumberFormat().format(n || 0);

  return (
    <div className="space-y-6">
      <button onClick={() => navigate("/deals")} data-testid="detail-back" className="flex items-center gap-1 text-sm text-muted hover:text-txt transition-colors">
        <ArrowLeft size={16} /> {t("detail.back")}
      </button>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{d.title}</h1>
          <div className="font-display text-3xl font-bold mt-2">{eur(d.value)}</div>
        </div>
        <div className="flex items-center gap-2">
          <Badge value={d.stage} label={t(`statuses.${d.stage}`)} />
          <span className="text-sm text-muted">{d.probability}%</span>
        </div>
      </div>

      <div className="border border-border rounded-sm p-5 space-y-2">
        <h3 className="font-display font-bold mb-2">{t("detail.overview")}</h3>
        {data.company_name && <div className="flex items-center gap-2 text-sm"><Building2 size={14} className="text-muted" />{data.company_name}</div>}
        {data.contact_name && <div className="flex items-center gap-2 text-sm"><User size={14} className="text-muted" />{data.contact_name}</div>}
        {d.expected_close && <div className="text-sm text-muted">{t("deal.expectedClose")}: {new Date(d.expected_close).toLocaleDateString()}</div>}
        {d.notes && <p className="text-sm text-muted pt-2 border-t border-border">{d.notes}</p>}
      </div>

      <div className="border border-border rounded-sm p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display font-bold flex items-center gap-2"><ActIcon size={16} className="text-glow" />{t("detail.timeline")}</h3>
          {writable && (
            <Button variant="subtle" onClick={() => setModal(true)} data-testid="log-activity-btn" className="py-1.5 px-3 text-xs">
              <Plus size={13} /> {t("activity.logActivity")}
            </Button>
          )}
        </div>
        {data.activities.length === 0 ? <p className="text-sm text-muted">{t("detail.noActivities")}</p> : (
          <div className="space-y-3">
            {data.activities.map((a) => (
              <div key={a.id} className="flex items-start gap-3">
                <span className="mt-1.5 w-2 h-2 rounded-full bg-primary shrink-0" />
                <div>
                  <div className="text-sm">{a.subject}</div>
                  <div className="text-xs text-muted">{t(`statuses.${a.type}`)}{a.direction ? ` · ${t(`activity.direction.${a.direction}`)}` : ""}{a.completed ? " · ✓" : ""}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal open={modal} onClose={() => setModal(false)} title={t("activity.logActivity")}
        footer={<>
          <Button variant="ghost" onClick={() => setModal(false)}>{t("common.cancel")}</Button>
          <Button onClick={logActivity} data-testid="save-activity-btn">{t("common.save")}</Button>
        </>}>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("activity.type")}>
            <Select data-testid="activity-type" value={activity.type} onChange={set("type")}>
              {TYPES.map((s) => <option key={s} value={s}>{t(`statuses.${s}`)}</option>)}
            </Select>
          </Field>
          <Field label={t("activity.directionLabel")}>
            <Select data-testid="activity-direction" value={activity.direction} onChange={set("direction")}>
              <option value="">{t("activity.noDirection")}</option>
              <option value="inbound">{t("activity.direction.inbound")}</option>
              <option value="outbound">{t("activity.direction.outbound")}</option>
              <option value="internal">{t("activity.direction.internal")}</option>
            </Select>
          </Field>
        </div>
        <Field label={t("activity.subject")}><Input data-testid="activity-subject" value={activity.subject} onChange={set("subject")} /></Field>
        <Field label={t("activity.description")}><Textarea rows={3} value={activity.description} onChange={set("description")} /></Field>
      </Modal>
    </div>
  );
}
