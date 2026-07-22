import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";
import api from "../api";
import { Spinner } from "../components/common";
import { formatMoneyByCurrency } from "../format";

const COLORS = ["#4338CA", "#00E5FF", "#10B981", "#F59E0B", "#8b5cf6", "#EF4444"];

export default function Utilization() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState("week");
  const [data, setData] = useState(null);

  useEffect(() => {
    setData(null);
    api.get("/reports/utilization", { params: { period } }).then((r) => setData(r.data));
  }, [period]);

  const moneyByCurrency = formatMoneyByCurrency;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{t("util.title")}</h1>
        <div className="flex border border-border rounded-sm overflow-hidden">
          {["week", "month"].map((p) => (
            <button key={p} onClick={() => setPeriod(p)} data-testid={`util-period-${p}`}
              className={`px-4 py-2 text-sm transition-colors ${period === p ? "bg-primary text-white" : "text-muted hover:bg-surface"}`}>
              {t(`util.${p}`)}
            </button>
          ))}
        </div>
      </div>

      {!data ? <Spinner /> : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="border border-border rounded-sm p-5" data-testid="util-total-hours">
              <div className="text-xs uppercase tracking-[0.15em] text-muted">{t("util.total")}</div>
              <div className="font-display text-3xl font-bold mt-2">{data.totals.total_hours}h</div>
            </div>
            <div className="border border-border rounded-sm p-5">
              <div className="text-xs uppercase tracking-[0.15em] text-muted">{t("util.billable")}</div>
              <div className="font-display text-3xl font-bold mt-2">{data.totals.billable_hours}h</div>
            </div>
            <div className="border border-border rounded-sm p-5">
              <div className="text-xs uppercase tracking-[0.15em] text-muted">{t("util.amount")}</div>
              <div className="font-display text-3xl font-bold mt-2">{moneyByCurrency(data.totals.billable_amount_by_currency)}</div>
            </div>
          </div>

          <div className="border border-border rounded-sm p-5">
            <h3 className="font-display font-bold mb-4">{t("util.billable")}</h3>
            {data.totals.total_hours === 0 ? (
              <p className="text-sm text-muted">{t("util.noData")}</p>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data.users} layout="vertical" margin={{ left: 20 }}>
                  <XAxis type="number" tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: "var(--surface)" }} contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 3, fontSize: 12 }} formatter={(v) => `${v}h`} />
                  <Bar dataKey="billable_hours" radius={[0, 3, 3, 0]}>
                    {data.users.map((u, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="border border-border rounded-sm overflow-hidden">
            <div className="grid grid-cols-12 px-4 py-2.5 border-b border-border text-xs uppercase tracking-[0.1em] text-muted">
              <div className="col-span-5">{t("util.user")}</div>
              <div className="col-span-2 text-right">{t("util.total")}</div>
              <div className="col-span-2 text-right">{t("util.billable")}</div>
              <div className="col-span-3 text-right">{t("util.amount")}</div>
            </div>
            {data.users.map((u) => (
              <div key={u.user_id} data-testid={`util-row-${u.user_id}`} className="grid grid-cols-12 px-4 py-3 border-b border-border last:border-0 items-center text-sm hover:bg-surface/60 transition-colors">
                <div className="col-span-5 flex items-center gap-2 min-w-0">
                  <div className="w-7 h-7 rounded-sm bg-primary/15 text-primary flex items-center justify-center text-xs font-bold shrink-0">{u.name?.[0]?.toUpperCase()}</div>
                  <span className="truncate">{u.name}</span>
                </div>
                <div className="col-span-2 text-right">{u.total_hours}h</div>
                <div className="col-span-2 text-right font-medium">{u.billable_hours}h</div>
                <div className="col-span-3 text-right">{moneyByCurrency(u.billable_amount_by_currency)}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
