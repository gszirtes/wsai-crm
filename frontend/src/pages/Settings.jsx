import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Sparkles, Calendar, Check, X, ShieldCheck, Timer } from "lucide-react";
import api, { formatApiError } from "../api";
import { Button, Input, Select, Field, Badge } from "../components/common";

const MODELS = [
  "deepseek/deepseek-chat-v3-0324:free",
  "meta-llama/llama-3.3-70b-instruct:free",
  "google/gemini-2.0-flash-exp:free",
  "mistralai/mistral-7b-instruct:free",
];

const CAPABILITIES = [
  "view_financials", "manage_deals", "manage_projects",
  "invite_members", "set_visibility", "reassign_owner", "view_all_reports",
];
const EDITABLE_ROLES = ["user", "guest"];
const FIXED_ROLES = ["admin", "manager"];

export default function SettingsPage() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(MODELS[0]);
  const [defaultVisibility, setDefaultVisibility] = useState("public");
  const [saved, setSaved] = useState(false);
  const [capabilities, setCapabilities] = useState(null);
  const [capsSaved, setCapsSaved] = useState(false);
  const [error, setError] = useState("");
  const [housekeeping, setHousekeeping] = useState(null);
  const [housekeepingRunning, setHousekeepingRunning] = useState(false);

  useEffect(() => {
    api.get("/settings").then((r) => {
      setSettings(r.data);
      setModel(r.data.openrouter_model || MODELS[0]);
      setDefaultVisibility(r.data.default_visibility || "public");
    }).catch((e) => setError(formatApiError(e.response?.data?.detail) || e.message));
    api.get("/settings/capabilities").then((r) => setCapabilities(r.data))
      .catch((e) => setError(formatApiError(e.response?.data?.detail) || e.message));
  }, []);

  const save = async () => {
    setError("");
    try {
      const payload = { openrouter_model: model };
      if (apiKey) payload.openrouter_api_key = apiKey;
      const r = await api.put("/settings", payload);
      setSettings(r.data);
      setApiKey("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error("Settings request failed:", e);
      setError(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const toggleCapability = (role, cap) => {
    setCapabilities({
      ...capabilities,
      [role]: { ...capabilities[role], [cap]: !capabilities[role][cap] },
    });
  };

  const saveCapabilities = async () => {
    setError("");
    try {
      const r = await api.put("/settings/capabilities", capabilities);
      setCapabilities(r.data);
      setCapsSaved(true);
      setTimeout(() => setCapsSaved(false), 2000);
    } catch (e) {
      console.error("Settings request failed:", e);
      setError(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const runHousekeeping = async () => {
    setHousekeepingRunning(true);
    setError("");
    try {
      const r = await api.post("/settings/housekeeping/run");
      setHousekeeping(r.data);
    } catch (e) {
      console.error("Housekeeping run failed:", e);
      setError(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setHousekeepingRunning(false);
    }
  };

  const saveDefaultVisibility = async (value) => {
    const previous = defaultVisibility;
    setDefaultVisibility(value);
    setError("");
    try {
      const r = await api.put("/settings", { default_visibility: value });
      setSettings(r.data);
    } catch (e) {
      setDefaultVisibility(previous);
      setError(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{t("settings.title")}</h1>

      {error && <p className="text-sm text-danger">{error}</p>}

      {/* AI */}
      <div className="border border-border rounded-sm p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-sm bg-glow/15 text-glow flex items-center justify-center"><Sparkles size={18} /></div>
            <div>
              <h3 className="font-display font-bold">{t("settings.ai")}</h3>
              <p className="text-sm text-muted">{t("settings.aiDesc")}</p>
            </div>
          </div>
          {settings && (
            <Badge value={settings.openrouter_configured ? "won" : "lost"}
              label={settings.openrouter_configured ? t("settings.configured") : t("settings.notConfigured")} />
          )}
        </div>
        <div className="mt-5 space-y-4">
          <Field label={t("settings.apiKey")}>
            <Input data-testid="openrouter-key-input" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
              placeholder={settings?.openrouter_configured ? "•••••••••• (saved)" : "sk-or-v1-..."} />
          </Field>
          <Field label={t("settings.model")}>
            <Select data-testid="openrouter-model-select" value={model} onChange={(e) => setModel(e.target.value)}>
              {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
            </Select>
          </Field>
          <Button onClick={save} data-testid="save-settings-btn">
            {saved ? <><Check size={16} /> {t("common.save")}d</> : t("common.save")}
          </Button>
          <p className="text-xs text-muted">
            Get a free key at <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer" className="text-primary hover:underline">openrouter.ai/keys</a>
          </p>
        </div>
      </div>

      {/* Capability matrix */}
      <div className="border border-border rounded-sm p-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-sm bg-success/15 text-success flex items-center justify-center"><ShieldCheck size={18} /></div>
          <div>
            <h3 className="font-display font-bold">{t("capabilities.title")}</h3>
            <p className="text-sm text-muted">{t("capabilities.desc")}</p>
          </div>
        </div>
        <div className="mt-5 max-w-xs">
          <Field label={t("capabilities.defaultVisibility")}>
            <Select data-testid="default-visibility-select" value={defaultVisibility}
              onChange={(e) => saveDefaultVisibility(e.target.value)}>
              <option value="public">{t("capabilities.public")}</option>
              <option value="private">{t("capabilities.private")}</option>
            </Select>
          </Field>
        </div>
        {capabilities && (
          <div className="mt-5 overflow-x-auto">
            <table className="w-full text-sm" data-testid="capability-matrix">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 pr-3 font-medium text-muted">{t("capabilities.capability")}</th>
                  {FIXED_ROLES.map((role) => (
                    <th key={role} className="text-center py-2 px-3 font-medium text-muted">{t(`roles.${role}`)}</th>
                  ))}
                  {EDITABLE_ROLES.map((role) => (
                    <th key={role} className="text-center py-2 px-3 font-medium text-muted">{t(`roles.${role}`)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {CAPABILITIES.map((cap) => (
                  <tr key={cap} className="border-b border-border last:border-0">
                    <td className="py-2 pr-3">
                      {t(`capabilities.${cap}`)}
                      {cap === "reassign_owner" && (
                        <span className="block text-xs text-muted">{t("capabilities.reassignOwnerNote")}</span>
                      )}
                    </td>
                    {FIXED_ROLES.map((role) => (
                      <td key={role} className="text-center py-2 px-3 text-success">
                        {capabilities[role][cap] ? <Check size={16} className="inline" /> : <X size={16} className="inline text-muted" />}
                      </td>
                    ))}
                    {EDITABLE_ROLES.map((role) => (
                      <td key={role} className="text-center py-2 px-3">
                        <input
                          type="checkbox"
                          data-testid={`cap-${role}-${cap}`}
                          checked={!!capabilities[role][cap]}
                          onChange={() => toggleCapability(role, cap)}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <Button onClick={saveCapabilities} data-testid="save-capabilities-btn" className="mt-4">
              {capsSaved ? <><Check size={16} /> {t("common.save")}d</> : t("common.save")}
            </Button>
          </div>
        )}
      </div>

      {/* Housekeeping job (Phase 5) */}
      <div className="border border-border rounded-sm p-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-sm bg-amber-500/15 text-amber-600 flex items-center justify-center"><Timer size={18} /></div>
          <div>
            <h3 className="font-display font-bold">{t("settings.housekeeping")}</h3>
            <p className="text-sm text-muted">{t("settings.housekeepingDesc")}</p>
          </div>
        </div>
        <div className="mt-4">
          <Button onClick={runHousekeeping} disabled={housekeepingRunning} data-testid="run-housekeeping-btn">
            {housekeepingRunning ? t("settings.housekeepingRunning") : t("settings.housekeepingRun")}
          </Button>
          {housekeeping && (
            <div className="mt-3 text-sm text-muted space-y-1" data-testid="housekeeping-result">
              {housekeeping.ran ? (
                <>
                  <div>{t("settings.housekeepingFollowUps")}: {housekeeping.follow_up_tasks_created}</div>
                  <div>{t("settings.housekeepingStale")}: {housekeeping.deals_stale_flag_changed}</div>
                  <div>{t("settings.housekeepingNotifications")}: {housekeeping.users_notifications_synced}</div>
                </>
              ) : (
                <div>{t("settings.housekeepingSkipped")}</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Google Workspace */}
      <div className="border border-border rounded-sm p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-sm bg-primary/15 text-primary flex items-center justify-center"><Calendar size={18} /></div>
            <div>
              <h3 className="font-display font-bold">{t("settings.google")}</h3>
              <p className="text-sm text-muted">{t("settings.googleDesc")}</p>
            </div>
          </div>
          <Badge value="lost" label={t("settings.notConfigured")} />
        </div>
        <div className="mt-4 flex items-center gap-2 text-sm text-muted">
          <X size={14} className="text-muted" /> Requires Google Cloud OAuth credentials (Client ID & Secret).
        </div>
      </div>
    </div>
  );
}
