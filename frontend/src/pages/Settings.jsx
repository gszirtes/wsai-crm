import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Sparkles, Calendar, Check, X } from "lucide-react";
import api from "../api";
import { Button, Input, Select, Field, Badge } from "../components/common";

const MODELS = [
  "deepseek/deepseek-chat-v3-0324:free",
  "meta-llama/llama-3.3-70b-instruct:free",
  "google/gemini-2.0-flash-exp:free",
  "mistralai/mistral-7b-instruct:free",
];

export default function SettingsPage() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(MODELS[0]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get("/settings").then((r) => {
      setSettings(r.data);
      setModel(r.data.openrouter_model || MODELS[0]);
    });
  }, []);

  const save = async () => {
    const payload = { openrouter_model: model };
    if (apiKey) payload.openrouter_api_key = apiKey;
    const r = await api.put("/settings", payload);
    setSettings(r.data);
    setApiKey("");
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{t("settings.title")}</h1>

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
