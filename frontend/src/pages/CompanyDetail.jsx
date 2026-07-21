import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Globe, Users, Handshake, FolderKanban } from "lucide-react";
import api from "../api";
import { Badge, Spinner } from "../components/common";

export default function CompanyDetail() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  const load = useCallback(() => {
    api.get(`/companies/${id}/detail`).then((r) => setData(r.data)).catch(() => navigate("/companies"));
  }, [id, navigate]);
  useEffect(() => { load(); }, [load]);

  if (!data) return <Spinner />;
  const c = data.company;
  const eur = (n) => (n == null ? "—" : "€" + new Intl.NumberFormat().format(n));

  return (
    <div className="space-y-6">
      <button onClick={() => navigate("/companies")} data-testid="detail-back" className="flex items-center gap-1 text-sm text-muted hover:text-txt transition-colors">
        <ArrowLeft size={16} /> {t("detail.back")}
      </button>

      <div>
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{c.name}</h1>
        <div className="text-sm text-muted">{c.industry}{c.size && ` · ${c.size}`}</div>
        {c.website && <a href={`https://${c.website.replace(/^https?:\/\//, "")}`} target="_blank" rel="noreferrer" className="text-sm text-primary flex items-center gap-1 mt-1 hover:underline"><Globe size={13} />{c.website}</a>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="border border-border rounded-sm p-5">
          <h3 className="font-display font-bold mb-3 flex items-center gap-2"><Users size={16} className="text-primary" />{t("detail.contacts")} ({data.contacts.length})</h3>
          {data.contacts.length === 0 ? <p className="text-sm text-muted">{t("detail.noItems")}</p> : (
            <div className="space-y-2">
              {data.contacts.map((x) => (
                <Link to={`/contacts/${x.id}`} key={x.id} className="block text-sm hover:text-primary transition-colors truncate">{x.first_name} {x.last_name} <span className="text-muted">· {x.title}</span></Link>
              ))}
            </div>
          )}
        </div>
        <div className="border border-border rounded-sm p-5">
          <h3 className="font-display font-bold mb-3 flex items-center gap-2"><Handshake size={16} className="text-amber-500" />{t("detail.deals")} ({data.deals.length})</h3>
          {data.deals.length === 0 ? <p className="text-sm text-muted">{t("detail.noItems")}</p> : (
            <div className="space-y-2">
              {data.deals.map((x) => (
                <div key={x.id} className="flex items-center justify-between text-sm"><span className="truncate">{x.title}</span><span className="font-medium shrink-0">{eur(x.value)}</span></div>
              ))}
            </div>
          )}
        </div>
        <div className="border border-border rounded-sm p-5">
          <h3 className="font-display font-bold mb-3 flex items-center gap-2"><FolderKanban size={16} className="text-success" />{t("detail.projects")} ({data.projects.length})</h3>
          {data.projects.length === 0 ? <p className="text-sm text-muted">{t("detail.noItems")}</p> : (
            <div className="space-y-2">
              {data.projects.map((x) => (
                <Link to={`/projects/${x.id}`} key={x.id} className="flex items-center justify-between text-sm hover:text-primary transition-colors"><span className="truncate">{x.name}</span><Badge value={x.status} label={t(`statuses.${x.status}`)} /></Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
