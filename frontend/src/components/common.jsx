import React from "react";
import { X } from "lucide-react";

export function Button({ variant = "primary", className = "", children, ...props }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-sm text-sm font-medium px-4 py-2.5 transition-[background-color,transform,opacity,border-color] duration-200 disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]";
  const variants = {
    primary: "bg-primary text-white hover:bg-primary-hover",
    ghost: "bg-transparent text-txt hover:bg-surface border border-border",
    danger: "bg-danger text-white hover:opacity-90",
    subtle: "bg-surface text-txt hover:bg-border/60 border border-border",
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Field({ label, children }) {
  return (
    <label className="block space-y-1.5">
      {label && (
        <span className="text-xs uppercase tracking-[0.15em] text-muted">{label}</span>
      )}
      {children}
    </label>
  );
}

export function Input(props) {
  return (
    <input
      {...props}
      className={`w-full bg-bg border border-border rounded-sm px-3 py-2.5 text-sm text-txt outline-none focus:border-primary transition-colors duration-200 ${props.className || ""}`}
    />
  );
}

export function Textarea(props) {
  return (
    <textarea
      {...props}
      className={`w-full bg-bg border border-border rounded-sm px-3 py-2.5 text-sm text-txt outline-none focus:border-primary transition-colors duration-200 ${props.className || ""}`}
    />
  );
}

export function Select({ children, ...props }) {
  return (
    <select
      {...props}
      className={`w-full bg-bg border border-border rounded-sm px-3 py-2.5 text-sm text-txt outline-none focus:border-primary transition-colors duration-200 ${props.className || ""}`}
    >
      {children}
    </select>
  );
}

const STATUS_COLORS = {
  lead: "bg-slate-500/15 text-slate-500",
  prospect: "bg-amber-500/15 text-amber-600",
  customer: "bg-success/15 text-success",
  inactive: "bg-slate-400/15 text-slate-400",
  qualified: "bg-blue-500/15 text-blue-500",
  proposal: "bg-violet-500/15 text-violet-500",
  negotiation: "bg-amber-500/15 text-amber-600",
  won: "bg-success/15 text-success",
  lost: "bg-danger/15 text-danger",
  planning: "bg-slate-500/15 text-slate-500",
  active: "bg-success/15 text-success",
  on_hold: "bg-amber-500/15 text-amber-600",
  completed: "bg-blue-500/15 text-blue-500",
  cancelled: "bg-danger/15 text-danger",
  high: "bg-danger/15 text-danger",
  medium: "bg-amber-500/15 text-amber-600",
  low: "bg-slate-500/15 text-slate-500",
};

export function Badge({ value, label, className = "" }) {
  const color = STATUS_COLORS[value] || "bg-primary/15 text-primary";
  return (
    <span
      className={`inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium ${color} ${className}`}
    >
      {label || value}
    </span>
  );
}

export function Modal({ open, onClose, title, children, footer }) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      data-testid="modal-overlay"
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative z-10 w-full sm:max-w-lg bg-bg border border-border rounded-t-xl sm:rounded-sm shadow-2xl animate-fade-up max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="font-display text-lg font-bold">{title}</h3>
          <button
            onClick={onClose}
            data-testid="modal-close-btn"
            className="p-1 rounded-sm hover:bg-surface transition-colors"
          >
            <X size={18} />
          </button>
        </div>
        <div className="px-6 py-5 overflow-y-auto space-y-4">{children}</div>
        {footer && (
          <div className="px-6 py-4 border-t border-border flex justify-end gap-2">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

export function EmptyState({ title, hint, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-20 px-6">
      <div className="w-14 h-14 rounded-sm bg-surface border border-border flex items-center justify-center mb-4">
        <span className="w-2 h-2 rounded-full bg-primary" />
      </div>
      <p className="font-display text-lg font-bold">{title}</p>
      {hint && <p className="text-sm text-muted mt-1 max-w-xs">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
