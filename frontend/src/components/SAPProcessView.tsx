"use client";

import { ArrowRight, Circle, CheckCircle2, AlertCircle } from "lucide-react";

interface ProcessStep {
  id: string;
  label: string;
  description?: string;
  status: "pending" | "active" | "completed" | "error";
  context?: Record<string, string>;
}

interface SAPProcessViewProps {
  title: string;
  steps: ProcessStep[];
  activeStepId?: string;
}

const STATUS_STYLES: Record<ProcessStep["status"], { icon: typeof Circle; color: string; bg: string }> = {
  pending: {
    icon: Circle,
    color: "text-[var(--text-muted)]",
    bg: "bg-[var(--bg-tertiary)] border-[var(--border)]",
  },
  active: {
    icon: Circle,
    color: "text-blue-400",
    bg: "bg-blue-500/10 border-blue-500/30",
  },
  completed: {
    icon: CheckCircle2,
    color: "text-green-400",
    bg: "bg-green-500/10 border-green-500/30",
  },
  error: {
    icon: AlertCircle,
    color: "text-red-400",
    bg: "bg-red-500/10 border-red-500/30",
  },
};

export function SAPProcessView({ title, steps, activeStepId }: SAPProcessViewProps) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-4">
        {title}
      </h3>

      {/* Flow diagram */}
      <div className="flex items-start gap-1 overflow-x-auto pb-2">
        {steps.map((step, i) => {
          const isActive = step.id === activeStepId || step.status === "active";
          const style = STATUS_STYLES[step.status];
          const Icon = style.icon;

          return (
            <div key={step.id} className="flex items-start shrink-0">
              <div
                className={`rounded-lg border ${style.bg} p-3 min-w-[140px] max-w-[180px] transition-all ${
                  isActive ? "ring-1 ring-blue-500/40" : ""
                }`}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <Icon className={`w-3.5 h-3.5 ${style.color} shrink-0`} />
                  <span className={`text-[10px] font-semibold uppercase ${style.color}`}>
                    {step.status}
                  </span>
                </div>
                <p className="text-xs font-medium text-[var(--text-primary)] leading-snug">
                  {step.label}
                </p>
                {step.description && (
                  <p className="text-[10px] text-[var(--text-muted)] mt-1 leading-relaxed">
                    {step.description}
                  </p>
                )}

                {/* Step-level context */}
                {step.context && Object.keys(step.context).length > 0 && (
                  <div className="mt-2 pt-2 border-t border-[var(--border)] space-y-0.5">
                    {Object.entries(step.context).map(([key, value]) => (
                      <div key={key} className="flex items-baseline gap-1">
                        <span className="text-[9px] text-[var(--text-muted)] shrink-0">{key}:</span>
                        <span className="text-[9px] text-[var(--text-secondary)] truncate">
                          {value}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {i < steps.length - 1 && (
                <div className="flex items-center self-center pt-3 px-0.5">
                  <ArrowRight className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary footer */}
      <div className="flex gap-4 mt-3 pt-2 border-t border-[var(--border)]">
        <span className="text-[10px] text-[var(--text-muted)]">
          {steps.filter((s) => s.status === "completed").length}/{steps.length} completed
        </span>
        {steps.some((s) => s.status === "error") && (
          <span className="text-[10px] text-red-400">
            {steps.filter((s) => s.status === "error").length} error(s)
          </span>
        )}
      </div>
    </div>
  );
}
