import React, { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bell, AlertTriangle, Clock, FolderKanban, Check } from "lucide-react";
import api from "../api";

const ICONS = {
  auto_overdue: AlertTriangle,
  auto_due_today: Clock,
  auto_project_risk: FolderKanban,
  info: Bell,
};

export default function NotificationBell() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ items: [], unread: 0 });
  const ref = useRef(null);

  const load = () => api.get("/notifications").then((r) => setData(r.data)).catch(() => {});

  useEffect(() => {
    load();
    const iv = setInterval(load, 60000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const openPanel = () => { setOpen(!open); if (!open) load(); };

  const handleClick = async (n) => {
    if (!n.read) { await api.post(`/notifications/${n.id}/read`); }
    setOpen(false);
    if (n.link) navigate(n.link);
    load();
  };

  const markAll = async () => { await api.post("/notifications/read-all"); load(); };

  return (
    <div className="relative" ref={ref}>
      <button onClick={openPanel} data-testid="notif-bell" className="relative p-2 rounded-sm hover:bg-surface transition-colors text-muted">
        <Bell size={18} />
        {data.unread > 0 && (
          <span data-testid="notif-badge" className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-danger text-white text-[10px] font-bold flex items-center justify-center">
            {data.unread}
          </span>
        )}
      </button>

      {open && (
        <div data-testid="notif-panel" className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2rem)] bg-bg border border-border rounded-sm shadow-2xl z-50 animate-fade-up">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <span className="font-display font-bold text-sm">{t("notif.title")}</span>
            {data.unread > 0 && (
              <button onClick={markAll} data-testid="notif-mark-all" className="text-xs text-primary hover:underline flex items-center gap-1">
                <Check size={12} /> {t("notif.markAll")}
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {data.items.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted">{t("notif.empty")}</div>
            ) : data.items.map((n) => {
              const Icon = ICONS[n.type] || Bell;
              return (
                <button key={n.id} onClick={() => handleClick(n)} data-testid={`notif-item-${n.id}`}
                  className={`w-full flex items-start gap-3 px-4 py-3 text-left border-b border-border last:border-0 hover:bg-surface transition-colors ${n.read ? "opacity-60" : ""}`}>
                  <Icon size={16} className={`mt-0.5 shrink-0 ${n.type === "auto_overdue" ? "text-danger" : n.type === "auto_project_risk" ? "text-amber-500" : "text-primary"}`} />
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{n.title}</div>
                    <div className="text-xs text-muted truncate">{n.body}</div>
                  </div>
                  {!n.read && <span className="ml-auto mt-1 w-2 h-2 rounded-full bg-primary shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
