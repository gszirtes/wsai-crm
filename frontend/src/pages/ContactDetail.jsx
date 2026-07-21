import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Mail, Phone, Building2, Handshake, Activity as ActIcon } from "lucide-react";
import api from "../api";
import { useAuth, can } from "../auth";
import { Badge, Spinner, Button, Modal, Field, Input, Textarea, Select } from "../components/common";

export default function ContactDetail() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const writable = can.write(user);
  const [data, setData] = useState(null);
  const [modal, setModal] = useState(false);
  const [email, setEmail] = useState({ direction: "outbound", subject: "", body: "" });

  const load = useCallback(() => {
    api.get(`/contacts/${id}/detail`).then((r) => setData(r.data)).catch(() => navigate("/contacts"));
  }, [id, navigate]);
  useEffect(() => { load(); }, [load]);

  const logEmail = async () => {
    await api.post("/activities", {
      type: "email",
      direction: email.direction,
      subject: email.subject,
      description: email.body,
      contact_id: id,
    });
    setModal(false);
    setEmail({ direction: "outbound", subject: "", body: "" });
    load();
  };

  if (!data) return <Spinner />;
  const c = data.contact;
  const eur = (n) => (n == null ? "—" : "€" + new Intl.NumberFormat().format(n));

  return (
    <div className="space-y-6">
      <button onClick={() => navigate("/contacts")} data-testid="detail-back" className="flex items-center gap-1 text-sm text-muted hover:text-txt transition-colors">
        <ArrowLeft size={16} /> {t("detail.back")}
      </button>

      <div className="flex items-start gap-4">
        <div className="w-14 h-14 rounded-sm bg-primary/15 text-primary flex items-center justify-center text-xl font-bold shrink-0">
          {c.first_name?.[0]?.toUpperCase()}
        </div>
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{c.first_name} {c.last_name}</h1>
          <div className="text-sm text-muted">{c.title}{c.company_name && ` · ${c.company_name}`}</div>
          <div className="mt-2"><Badge value={c.status} label={t(`statuses.${c.status}`)} /></div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="border border-border rounded-sm p-5 space-y-2">
          <h3 className="font-display font-bold mb-2">{t("detail.overview")}</h3>
          {c.email && <div className="flex items-center gap-2 text-sm"><Mail size={14} className="text-muted" />{c.email}</div>}
          {c.phone && <div className="flex items-center gap-2 text-sm"><Phone size={14} className="text-muted" />{c.phone}</div>}
          {c.company_name && <div className="flex items-center gap-2 text-sm"><Building2 size={14} className="text-muted" />{c.company_name}</div>}
          {c.notes && <p className="text-sm text-muted pt-2 border-t border-border">{c.notes}</p>}
        </div>

        <div className="border border-border rounded-sm p-5">
          <h3 className="font-display font-bold mb-3 flex items-center gap-2"><Handshake size={16} className="text-primary" />{t("detail.deals")}</h3>
          {data.deals.length === 0 ? <p className="text-sm text-muted">{t("detail.noItems")}</p> : (
            <div className="space-y-2">
              {data.deals.map((d) => (
                <Link to="/deals" key={d.id} className="flex items-center justify-between text-sm hover:text-primary transition-colors">
                  <span className="truncate">{d.title}</span>
                  <span className="flex items-center gap-2 shrink-0"><span className="font-medium">{eur(d.value)}</span><Badge value={d.stage} label={t(`statuses.${d.stage}`)} /></span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="border border-border rounded-sm p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display font-bold flex items-center gap-2"><ActIcon size={16} className="text-glow" />{t("detail.timeline")}</h3>
          {writable && (
            <Button variant="subtle" onClick={() => setModal(true)} data-testid="log-email-btn" className="py-1.5 px-3 text-xs">
              <Mail size={13} /> {t("email.log")}
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

      <Modal open={modal} onClose={() => setModal(false)} title={t("email.log")}
        footer={<>
          <Button variant="ghost" onClick={() => setModal(false)}>{t("common.cancel")}</Button>
          <Button onClick={logEmail} data-testid="save-email-btn">{t("common.save")}</Button>
        </>}>
        <Field label={t("email.direction")}>
          <Select data-testid="email-direction" value={email.direction} onChange={(e) => setEmail({ ...email, direction: e.target.value })}>
            <option value="outbound">{t("email.outbound")}</option>
            <option value="inbound">{t("email.inbound")}</option>
          </Select>
        </Field>
        <Field label={t("email.subject")}><Input data-testid="email-subject" value={email.subject} onChange={(e) => setEmail({ ...email, subject: e.target.value })} /></Field>
        <Field label={t("email.body")}><Textarea data-testid="email-body" rows={4} value={email.body} onChange={(e) => setEmail({ ...email, body: e.target.value })} /></Field>
      </Modal>
    </div>
  );
}
