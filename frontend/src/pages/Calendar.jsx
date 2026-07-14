import React, { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight } from "lucide-react";
import api from "../api";
import i18n from "../i18n";
import { Badge, Spinner } from "../components/common";

export default function Calendar() {
  const { t } = useTranslation();
  const [items, setItems] = useState(null);
  const [cursor, setCursor] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const [selected, setSelected] = useState(null);

  useEffect(() => { api.get("/activities").then((r) => setItems(r.data)); }, []);

  const byDate = useMemo(() => {
    const map = {};
    (items || []).forEach((a) => {
      if (!a.due_date) return;
      const key = new Date(a.due_date).toDateString();
      (map[key] = map[key] || []).push(a);
    });
    return map;
  }, [items]);

  if (!items) return <Spinner />;

  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const firstDay = new Date(year, month, 1);
  const startOffset = (firstDay.getDay() + 6) % 7; // Monday first
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));

  const monthLabel = cursor.toLocaleDateString(i18n.language, { month: "long", year: "numeric" });
  const weekdays = [...Array(7)].map((_, i) => {
    const d = new Date(2024, 0, 1 + i); // Mon..Sun
    return d.toLocaleDateString(i18n.language, { weekday: "short" });
  });
  const today = new Date().toDateString();
  const selectedTasks = selected ? (byDate[selected] || []) : [];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{t("calendar.title")}</h1>
        <div className="flex items-center gap-2">
          <button data-testid="cal-prev" onClick={() => setCursor(new Date(year, month - 1, 1))} className="p-2 rounded-sm border border-border hover:bg-surface transition-colors"><ChevronLeft size={16} /></button>
          <span className="font-display font-bold w-40 text-center capitalize">{monthLabel}</span>
          <button data-testid="cal-next" onClick={() => setCursor(new Date(year, month + 1, 1))} className="p-2 rounded-sm border border-border hover:bg-surface transition-colors"><ChevronRight size={16} /></button>
        </div>
      </div>

      <div className="border border-border rounded-sm overflow-hidden">
        <div className="grid grid-cols-7 border-b border-border">
          {weekdays.map((w) => <div key={w} className="text-center text-xs uppercase tracking-[0.1em] text-muted py-2 capitalize">{w}</div>)}
        </div>
        <div className="grid grid-cols-7">
          {cells.map((date, i) => {
            if (!date) return <div key={i} className="min-h-[70px] sm:min-h-[96px] border-r border-b border-border bg-surface/30" />;
            const key = date.toDateString();
            const tasks = byDate[key] || [];
            const isToday = key === today;
            return (
              <button key={i} onClick={() => setSelected(key)} data-testid={`cal-day-${date.getDate()}`}
                className={`min-h-[70px] sm:min-h-[96px] border-r border-b border-border p-1.5 text-left align-top hover:bg-surface transition-colors ${selected === key ? "bg-primary/5" : ""}`}>
                <div className={`text-xs w-6 h-6 flex items-center justify-center rounded-sm ${isToday ? "bg-primary text-white font-bold" : "text-muted"}`}>{date.getDate()}</div>
                <div className="mt-1 space-y-1">
                  {tasks.slice(0, 2).map((a) => (
                    <div key={a.id} className={`text-[10px] truncate rounded-sm px-1 py-0.5 ${a.completed ? "bg-success/15 text-success line-through" : "bg-primary/15 text-primary"}`}>{a.subject}</div>
                  ))}
                  {tasks.length > 2 && <div className="text-[10px] text-muted">+{tasks.length - 2}</div>}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {selected && (
        <div className="border border-border rounded-sm p-5">
          <h3 className="font-display font-bold mb-3">{new Date(selected).toLocaleDateString(i18n.language, { weekday: "long", month: "long", day: "numeric" })}</h3>
          {selectedTasks.length === 0 ? <p className="text-sm text-muted">{t("calendar.noTasks")}</p> : (
            <div className="divide-y divide-border">
              {selectedTasks.map((a) => (
                <div key={a.id} className="flex items-center gap-3 py-2">
                  <span className={`w-2 h-2 rounded-full ${a.completed ? "bg-success" : "bg-primary"}`} />
                  <span className={`text-sm flex-1 ${a.completed ? "line-through text-muted" : ""}`}>{a.subject}</span>
                  <Badge value={a.type} label={t(`statuses.${a.type}`)} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
