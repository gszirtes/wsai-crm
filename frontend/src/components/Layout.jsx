import React, { useState, useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutGrid, Users, Building2, Handshake, FolderKanban, CheckSquare,
  Settings, LogOut, Moon, Sun, Globe, Shield, CalendarDays, BarChart3,
} from "lucide-react";
import { useAuth, can } from "../auth";
import i18n from "../i18n";
import api from "../api";
import NotificationBell from "./NotificationBell";

const NAV = [
  { to: "/", key: "dashboard", icon: LayoutGrid, exact: true },
  { to: "/contacts", key: "contacts", icon: Users },
  { to: "/companies", key: "companies", icon: Building2 },
  { to: "/deals", key: "deals", icon: Handshake },
  { to: "/projects", key: "projects", icon: FolderKanban },
  { to: "/activities", key: "activities", icon: CheckSquare },
  { to: "/calendar", key: "calendar", icon: CalendarDays },
];

const MOBILE_NAV = [
  { to: "/", key: "dashboard", icon: LayoutGrid, exact: true },
  { to: "/contacts", key: "contacts", icon: Users },
  { to: "/deals", key: "deals", icon: Handshake },
  { to: "/projects", key: "projects", icon: FolderKanban },
  { to: "/calendar", key: "calendar", icon: CalendarDays },
];

function useTheme() {
  const [dark, setDark] = useState(
    () => (localStorage.getItem("theme") || "dark") === "dark"
  );
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);
  return [dark, setDark];
}

export default function Layout({ children }) {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [dark, setDark] = useTheme();
  const [lang, setLang] = useState(i18n.language);

  const toggleLang = async () => {
    const next = lang === "en" ? "hu" : "en";
    setLang(next);
    i18n.changeLanguage(next);
    localStorage.setItem("locale", next);
    try {
      await api.put("/users/me/locale", { locale: next });
    } catch (e) {}
  };

  const doLogout = async () => {
    await logout();
    navigate("/login");
  };

  const nav = [...NAV];
  if (user && (user.role === "admin" || user.role === "manager")) {
    nav.push({ to: "/utilization", key: "utilization", icon: BarChart3 });
  }
  if (can.admin(user)) {
    nav.push({ to: "/users", key: "users", icon: Shield });
    nav.push({ to: "/settings", key: "settings", icon: Settings });
  }

  return (
    <div className="min-h-screen bg-bg text-txt flex">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-64 border-r border-border shrink-0 sticky top-0 h-screen">
        <div className="px-6 py-6 border-b border-border">
          <div className="font-display text-2xl font-black tracking-tighter">
            wespeak<span className="text-primary">.ai</span>
          </div>
          <div className="text-xs uppercase tracking-[0.2em] text-muted mt-1">
            {t("app.tagline")}
          </div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {nav.map((item) => (
            <NavLink
              key={item.key}
              to={item.to}
              end={item.exact}
              data-testid={`nav-${item.key}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-sm text-sm transition-colors duration-200 ${
                  isActive
                    ? "bg-primary text-white"
                    : "text-muted hover:bg-surface hover:text-txt"
                }`
              }
            >
              <item.icon size={18} />
              {t(`nav.${item.key}`)}
            </NavLink>
          ))}
        </nav>
        <div className="px-3 py-4 border-t border-border space-y-1">
          <button
            onClick={toggleLang}
            data-testid="lang-toggle"
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-sm text-sm text-muted hover:bg-surface hover:text-txt transition-colors"
          >
            <Globe size={18} /> {lang === "en" ? "Magyar" : "English"}
          </button>
          <button
            onClick={() => setDark(!dark)}
            data-testid="theme-toggle"
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-sm text-sm text-muted hover:bg-surface hover:text-txt transition-colors"
          >
            {dark ? <Sun size={18} /> : <Moon size={18} />}
            {dark ? t("settings.light") : t("settings.dark")}
          </button>
          <div className="flex items-center gap-3 px-3 py-2.5">
            <div className="w-8 h-8 rounded-sm bg-primary/20 text-primary flex items-center justify-center text-sm font-bold shrink-0">
              {user?.name?.[0]?.toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium truncate">{user?.name}</div>
              <div className="text-xs text-muted">{t(`roles.${user?.role}`)}</div>
            </div>
            <button onClick={doLogout} data-testid="logout-btn" className="text-muted hover:text-danger transition-colors">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Mobile header */}
        <header className="lg:hidden sticky top-0 z-30 flex items-center justify-between px-4 py-3 border-b border-border bg-bg/80 backdrop-blur-xl">
          <div className="font-display text-xl font-black tracking-tighter">
            wespeak<span className="text-primary">.ai</span>
          </div>
          <div className="flex items-center gap-1">
            <NotificationBell />
            <button onClick={toggleLang} data-testid="lang-toggle-mobile" className="p-2 rounded-sm hover:bg-surface transition-colors text-muted">
              <Globe size={18} />
            </button>
            <button onClick={() => setDark(!dark)} data-testid="theme-toggle-mobile" className="p-2 rounded-sm hover:bg-surface transition-colors text-muted">
              {dark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <button onClick={doLogout} data-testid="logout-btn-mobile" className="p-2 rounded-sm hover:bg-surface transition-colors text-muted">
              <LogOut size={18} />
            </button>
          </div>
        </header>

        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 pb-28 lg:pb-8 max-w-7xl w-full mx-auto">
          <div className="hidden lg:flex justify-end mb-2 -mt-2">
            <NotificationBell />
          </div>
          {children}
        </main>
      </div>

      {/* Mobile bottom nav */}
      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 mx-3 mb-3 rounded-sm border border-border bg-bg/85 backdrop-blur-xl shadow-2xl">
        <div className="flex items-center justify-around">
          {MOBILE_NAV.map((item) => (
            <NavLink
              key={item.key}
              to={item.to}
              end={item.exact}
              data-testid={`nav-mobile-${item.key}`}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 py-2.5 flex-1 text-[10px] transition-colors ${
                  isActive ? "text-primary" : "text-muted"
                }`
              }
            >
              <item.icon size={20} />
              {t(`nav.${item.key}`)}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
