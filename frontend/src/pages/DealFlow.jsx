import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";
import api from "../api";
import { Spinner } from "../components/common";

const STAGES = ["lead", "qualified", "proposal", "negotiation", "won", "lost"];
const COLORS = ["#4338CA", "#00E5FF", "#10B981", "#F59E0B", "#8b5cf6", "#EF4444"];

export default function DealFlow() {
  const { t } = useTranslation();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/reports/deal-flow").then((r) => setData(r.data));
  }, []);

  if (!data) return <Spinner />;

  const stageRows = STAGES
    .filter((s) => data.avg_days_per_stage[s] != null)
    .map((s) => ({ stage: s, days: data.avg_days_per_stage[s] }));

  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{t("dealFlow.title")}</h1>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="border border-border rounded-sm p-5" data-testid="deal-flow-won-lost">
          <div className="text-xs uppercase tracking-[0.15em] text-muted">{t("dealFlow.wonLostRatio")}</div>
          <div className="font-display text-3xl font-bold mt-2">
            {data.won} / {data.lost}
          </div>
        </div>
        <div className="border border-border rounded-sm p-5">
          <div className="text-xs uppercase tracking-[0.15em] text-muted">{t("dealFlow.avgPasses")}</div>
          <div className="font-display text-3xl font-bold mt-2">{data.avg_passes_to_won}</div>
        </div>
      </div>

      <div className="border border-border rounded-sm p-5">
        <h3 className="font-display font-bold mb-4">{t("dealFlow.avgDaysPerStage")}</h3>
        {stageRows.length === 0 ? (
          <p className="text-sm text-muted">{t("dealFlow.noData")}</p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={stageRows} layout="vertical" margin={{ left: 20 }}>
              <XAxis type="number" tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="stage" width={90}
                tickFormatter={(s) => t(`statuses.${s}`)}
                tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "var(--surface)" }}
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 3, fontSize: 12 }}
                formatter={(v) => `${v} d`} labelFormatter={(s) => t(`statuses.${s}`)} />
              <Bar dataKey="days" radius={[0, 3, 3, 0]}>
                {stageRows.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
