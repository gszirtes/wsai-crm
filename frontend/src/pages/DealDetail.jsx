import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Building2, User, Activity as ActIcon } from "lucide-react";
import api from "../api";
import { Badge, Spinner } from "../components/common";

export default function DealDetail() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  const load = useCallback(() => {
    api.get(`/deals/${id}/detail`).then((r) => setData(r.data)).catch(() => navigate("/deals"));
  }, [id, navigate]);
  useEffect(() => { load(); }, [load]);

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
        <h3 className="font-display font-bold mb-3 flex items-center gap-2"><ActIcon size={16} className="text-glow" />{t("detail.timeline")}</h3>
        {data.activities.length === 0 ? <p className="text-sm text-muted">{t("detail.noActivities")}</p> : (
          <div className="space-y-3">
            {data.activities.map((a) => (
              <div key={a.id} className="flex items-start gap-3">
                <span className="mt-1.5 w-2 h-2 rounded-full bg-primary shrink-0" />
                <div><div className="text-sm">{a.subject}</div><div className="text-xs text-muted">{t(`statuses.${a.type}`)}{a.completed ? " · ✓" : ""}</div></div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
