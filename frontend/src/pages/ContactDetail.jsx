import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Mail, Phone, Building2, Handshake, Activity as ActIcon } from "lucide-react";
import api from "../api";
import { Badge, Spinner } from "../components/common";

export default function ContactDetail() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  const load = useCallback(() => {
    api.get(`/contacts/${id}/detail`).then((r) => setData(r.data)).catch(() => navigate("/contacts"));
  }, [id, navigate]);
  useEffect(() => { load(); }, [load]);

  if (!data) return <Spinner />;
  const c = data.contact;
  const eur = (n) => "€" + new Intl.NumberFormat().format(n || 0);

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
        <h3 className="font-display font-bold mb-3 flex items-center gap-2"><ActIcon size={16} className="text-glow" />{t("detail.timeline")}</h3>
        {data.activities.length === 0 ? <p className="text-sm text-muted">{t("detail.noActivities")}</p> : (
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
    </div>
  );
}
