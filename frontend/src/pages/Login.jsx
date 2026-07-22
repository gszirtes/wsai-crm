import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth";
import { Button, Input, Field } from "../components/common";
import { formatApiError } from "../api";

const DEMO = [
  { role: "Admin", email: "admin@wespeak.ai", pw: "admin123" },
  { role: "Manager", email: "manager@wespeak.ai", pw: "manager123" },
  { role: "User", email: "user@wespeak.ai", pw: "user123" },
  { role: "Guest", email: "guest@wespeak.ai", pw: "guest123" },
];

const BG = "https://images.unsplash.com/photo-1557264322-b44d383a2906?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzB8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMGRhcmslMjBtaW5pbWFsaXN0JTIwYXJ0fGVufDB8fHx8MTc4NDAwNDUwNnww&ixlib=rb-4.1.0&q=85";

export default function Login() {
  const { t } = useTranslation();
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(name, email, password);
      navigate("/");
    } catch (err) {
      console.error("Auth request failed:", err);
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const quick = (d) => {
    setEmail(d.email);
    setPassword(d.pw);
    setMode("login");
  };

  return (
    <div className="min-h-screen flex bg-bg text-txt">
      {/* Left visual */}
      <div className="hidden lg:flex w-1/2 relative overflow-hidden border-r border-border">
        <img src={BG} alt="" className="absolute inset-0 w-full h-full object-cover opacity-60" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#060B19] via-[#060B19]/40 to-transparent" />
        <div className="relative z-10 flex flex-col justify-end p-12">
          <div className="font-display text-5xl font-black tracking-tighter text-white">
            wespeak<span className="text-glow">.ai</span>
          </div>
          <p className="text-white/70 mt-3 max-w-sm">
            The mobile-first CRM built for AI consulting teams. Contacts, deals,
            projects and an AI command bar — in one place.
          </p>
        </div>
      </div>

      {/* Right form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="lg:hidden font-display text-3xl font-black tracking-tighter mb-8">
            wespeak<span className="text-primary">.ai</span>
          </div>
          <h1 className="font-display text-3xl font-bold">{t("auth.welcome")}</h1>
          <p className="text-muted text-sm mt-1">{t("auth.subtitle")}</p>

          <form onSubmit={submit} className="mt-8 space-y-4" data-testid="auth-form">
            {mode === "register" && (
              <Field label={t("auth.name")}>
                <Input
                  data-testid="auth-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </Field>
            )}
            <Field label={t("auth.email")}>
              <Input
                data-testid="auth-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </Field>
            <Field label={t("auth.password")}>
              <Input
                data-testid="auth-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </Field>

            {error && (
              <div className="text-sm text-danger" data-testid="auth-error">
                {error}
              </div>
            )}

            <Button type="submit" disabled={loading} className="w-full" data-testid="auth-submit">
              {loading ? t("common.loading") : mode === "login" ? t("auth.signIn") : t("auth.signUp")}
            </Button>
          </form>

          <button
            className="w-full mt-3 flex items-center justify-center gap-2 rounded-sm border border-border py-2.5 text-sm hover:bg-surface transition-colors"
            data-testid="google-login-btn"
            onClick={() => setError("Google Workspace login requires Google Cloud credentials — configure in Settings.")}
          >
            <img src="https://www.google.com/favicon.ico" alt="" className="w-4 h-4" />
            {t("auth.google")}
          </button>

          <div className="text-center text-sm text-muted mt-6">
            {mode === "login" ? t("auth.noAccount") : t("auth.haveAccount")}{" "}
            <button
              className="text-primary font-medium"
              data-testid="auth-toggle-mode"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
            >
              {mode === "login" ? t("auth.register") : t("auth.login")}
            </button>
          </div>

          <div className="mt-8 border-t border-border pt-4">
            <p className="text-xs uppercase tracking-[0.15em] text-muted mb-2">
              {t("auth.demo")}
            </p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO.map((d) => (
                <button
                  key={d.email}
                  onClick={() => quick(d)}
                  data-testid={`demo-${d.role.toLowerCase()}`}
                  className="text-left rounded-sm border border-border px-3 py-2 hover:border-primary transition-colors"
                >
                  <div className="text-sm font-medium">{d.role}</div>
                  <div className="text-xs text-muted truncate">{d.email}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
