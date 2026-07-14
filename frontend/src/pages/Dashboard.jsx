import React, { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  Users, Building2, Handshake, FolderKanban, TrendingUp, Trophy, CheckSquare,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, PieChart, Pie, Tooltip,
} from "recharts";
import api from "../api";
import { useAuth } from "../auth";
import AICommandBar from "../components/AICommandBar";
import { Spinner } from "../components/common";

const STAGE_COLORS = {
  lead: "#64748b", qualified: "#3b82f6", proposal: "#8b5cf6",
  negotiation: "#f59e0b", won: "#10b981", lost: "#ef4444",
};
const PIE_COLORS = ["#4338CA", "#00E5FF", "#10B981", "#F59E0B", "#EF4444", "#8b5cf6"];

function Metric({ icon: Icon, label, value, accent }) {
  return (
    <div className="border border-border rounded-sm p-5 bg-surface/40 hover:-translate-y-px transition-transform duration-200" data-testid={`metric-${label}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.15em] text-muted">{label}</span>
        <Icon size={16} className={accent} />
      </div>
      <div className="font-display text-3xl font-bold mt-3 tracking-tight">{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [tasks, setTasks] = useState([]);

  const load = useCallback(() => {
    api.get("/dashboard/stats").then((r) => setStats(r.data));
    api.get("/activities", { params: { completed: "false", upcoming: "true" } })
      .then((r) => setTasks(r.data.slice(0, 5)));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (!stats) return <Spinner />;

  const fmt = (n) => new Intl.NumberFormat().format(n);
  const eur = (n) => "€" + new Intl.NumberFormat().format(n);

  const stageData = stats.deals_by_stage.map((d) => ({
    name: t(`statuses.${d.stage}`), value: d.value, stage: d.stage,
  }));
  const statusData = stats.contacts_by_status.map((d) => ({
    name: t(`statuses.${d.status}`), value: d.count,
  }));

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted">{t("dashboard.greeting")}</p>
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">{user?.name}</h1>
      </div>

      <AICommandBar onResult={load} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger">
        <Metric icon={Users} label={t("dashboard.contacts")} value={fmt(stats.total_contacts)} accent="text-primary" />
        <Metric icon={Building2} label={t("dashboard.companies")} value={fmt(stats.total_companies)} accent="text-glow" />
        <Metric icon={Handshake} label={t("dashboard.openDeals")} value={fmt(stats.open_deals)} accent="text-amber-500" />
        <Metric icon={FolderKanban} label={t("dashboard.activeProjects")} value={fmt(stats.active_projects)} accent="text-success" />
        <Metric icon={TrendingUp} label={t("dashboard.pipelineValue")} value={eur(stats.pipeline_value)} accent="text-primary" />
        <Metric icon={Trophy} label={t("dashboard.wonValue")} value={eur(stats.won_value)} accent="text-success" />
        <Metric icon={CheckSquare} label={t("dashboard.openTasks")} value={fmt(stats.open_tasks)} accent="text-amber-500" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 border border-border rounded-sm p-5">
          <h3 className="font-display font-bold mb-4">{t("dashboard.pipelineByStage")}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={stageData}>
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
              <Tooltip
                cursor={{ fill: "var(--surface)" }}
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 3, fontSize: 12 }}
                formatter={(v) => eur(v)}
              />
              <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                {stageData.map((d, i) => (
                  <Cell key={i} fill={STAGE_COLORS[d.stage] || "#4338CA"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="border border-border rounded-sm p-5">
          <h3 className="font-display font-bold mb-4">{t("dashboard.contactsByStatus")}</h3>
          {statusData.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={90} paddingAngle={2}>
                  {statusData.map((d, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 3, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted">{t("common.noResults")}</p>
          )}
          <div className="flex flex-wrap gap-2 mt-3">
            {statusData.map((d, i) => (
              <span key={i} className="flex items-center gap-1.5 text-xs text-muted">
                <span className="w-2 h-2 rounded-full" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                {d.name} ({d.value})
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="border border-border rounded-sm p-5">
        <h3 className="font-display font-bold mb-4">{t("dashboard.upcomingTasks")}</h3>
        {tasks.length ? (
          <div className="divide-y divide-border">
            {tasks.map((a) => (
              <div key={a.id} className="flex items-center justify-between py-3" data-testid={`dash-task-${a.id}`}>
                <div className="flex items-center gap-3 min-w-0">
                  <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
                  <span className="text-sm truncate">{a.subject}</span>
                </div>
                <span className="text-xs text-muted shrink-0 ml-2">
                  {a.due_date ? new Date(a.due_date).toLocaleDateString() : "—"}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted">{t("common.noResults")}</p>
        )}
      </div>
    </div>
  );
}
