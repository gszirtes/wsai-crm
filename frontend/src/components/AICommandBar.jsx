import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Sparkles, CornerDownLeft, Check, Loader2 } from "lucide-react";
import api, { formatApiError } from "../api";

export default function AICommandBar({ onResult }) {
  const { t } = useTranslation();
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const run = async () => {
    if (!value.trim() || loading) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.post("/ai/command", { command: value });
      setResult(res.data);
      setValue("");
      if (res.data.created && onResult) onResult(res.data);
    } catch (e) {
      setError(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative">
      <div
        className={`relative rounded-sm p-[1.5px] transition-opacity duration-300 ${
          focused ? "ai-trace animate-trace" : "bg-border"
        }`}
      >
        <div className="flex items-center gap-2 bg-bg/80 backdrop-blur-xl rounded-sm px-3 py-2">
          <Sparkles size={16} className="text-glow shrink-0" />
          <input
            data-testid="ai-command-input"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder={t("ai.placeholder")}
            className="flex-1 bg-transparent outline-none text-sm text-txt placeholder:text-muted min-w-0"
          />
          <button
            data-testid="ai-command-run-btn"
            onClick={run}
            disabled={loading || !value.trim()}
            className="shrink-0 flex items-center gap-1 text-xs font-medium bg-primary text-white rounded-sm px-2.5 py-1.5 hover:bg-primary-hover transition-colors disabled:opacity-40"
          >
            {loading ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <CornerDownLeft size={13} />
            )}
            {t("ai.run")}
          </button>
        </div>
      </div>

      {(result || error || loading) && (
        <div
          className="mt-2 rounded-sm border border-border bg-surface px-4 py-3 text-sm animate-fade-up"
          data-testid="ai-result"
        >
          {loading && (
            <span className="text-muted flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" /> {t("ai.thinking")}
            </span>
          )}
          {error && <span className="text-danger">{error}</span>}
          {result && (
            <div className="space-y-1">
              <p className="text-txt">{result.message}</p>
              {result.created && (
                <span className="inline-flex items-center gap-1 text-xs text-success">
                  <Check size={13} /> {t("ai.created")}: {result.created.name} (
                  {result.created.type})
                </span>
              )}
            </div>
          )}
        </div>
      )}
      {!result && !error && !loading && focused && (
        <p className="mt-1.5 text-xs text-muted px-1">{t("ai.hint")}</p>
      )}
    </div>
  );
}
