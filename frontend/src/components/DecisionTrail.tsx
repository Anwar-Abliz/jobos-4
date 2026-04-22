"use client";

import { Clock, ArrowRightCircle, Info } from "lucide-react";

interface ContextSnapshot {
  key: string;
  value: string;
}

interface Decision {
  id: string;
  timestamp: string;
  action: "hire" | "fire" | "switch" | "escalate" | "hold";
  summary: string;
  reason?: string;
  entityId?: string;
  entityLabel?: string;
  contextSnapshot: ContextSnapshot[];
  vfeBefore?: number;
  vfeAfter?: number;
}

interface DecisionTrailProps {
  decisions: Decision[];
}

const ACTION_STYLES: Record<Decision["action"], { color: string; bg: string; label: string }> = {
  hire: { color: "text-green-400", bg: "bg-green-400", label: "HIRE" },
  fire: { color: "text-red-400", bg: "bg-red-400", label: "FIRE" },
  switch: { color: "text-amber-400", bg: "bg-amber-400", label: "SWITCH" },
  escalate: { color: "text-orange-400", bg: "bg-orange-400", label: "ESCALATE" },
  hold: { color: "text-blue-400", bg: "bg-blue-400", label: "HOLD" },
};

export function DecisionTrail({ decisions }: DecisionTrailProps) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-3.5 h-3.5 text-[var(--text-muted)]" />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Decision Trail ({decisions.length})
        </h3>
      </div>

      {decisions.length === 0 ? (
        <p className="text-xs text-[var(--text-muted)]">No decisions recorded yet.</p>
      ) : (
        <div className="relative pl-4 border-l-2 border-[var(--border)] space-y-4">
          {decisions.map((decision) => {
            const style = ACTION_STYLES[decision.action] || ACTION_STYLES.hold;
            const vfeDelta =
              decision.vfeBefore !== undefined && decision.vfeAfter !== undefined
                ? decision.vfeAfter - decision.vfeBefore
                : undefined;

            return (
              <div key={decision.id} className="relative">
                {/* Timeline dot */}
                <div
                  className={`absolute -left-[21px] w-3 h-3 rounded-full border-2 border-[var(--bg-secondary)] ${style.bg}`}
                />

                <div className="ml-2">
                  {/* Header */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-[10px] font-semibold uppercase ${style.color}`}>
                      {style.label}
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)]">
                      {new Date(decision.timestamp).toLocaleString()}
                    </span>
                    {decision.entityLabel && (
                      <span className="inline-flex items-center gap-0.5 text-[10px] text-[var(--text-secondary)]">
                        <ArrowRightCircle className="w-2.5 h-2.5" />
                        {decision.entityLabel}
                      </span>
                    )}
                  </div>

                  {/* Summary */}
                  <p className="text-xs text-[var(--text-primary)] mt-0.5 leading-relaxed">
                    {decision.summary}
                  </p>

                  {/* Reason */}
                  {decision.reason && (
                    <div className="flex items-start gap-1 mt-1">
                      <Info className="w-2.5 h-2.5 text-[var(--text-muted)] mt-0.5 shrink-0" />
                      <p className="text-[10px] text-[var(--text-muted)] leading-relaxed">
                        {decision.reason}
                      </p>
                    </div>
                  )}

                  {/* VFE delta */}
                  {vfeDelta !== undefined && (
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-[9px] text-[var(--text-muted)]">VFE</span>
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">
                        {decision.vfeBefore!.toFixed(3)}
                      </span>
                      <ArrowRightCircle className="w-2.5 h-2.5 text-[var(--text-muted)]" />
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">
                        {decision.vfeAfter!.toFixed(3)}
                      </span>
                      <span
                        className={`text-[10px] font-medium ${
                          vfeDelta < 0 ? "text-green-400" : vfeDelta > 0 ? "text-red-400" : "text-[var(--text-muted)]"
                        }`}
                      >
                        ({vfeDelta > 0 ? "+" : ""}
                        {vfeDelta.toFixed(3)})
                      </span>
                    </div>
                  )}

                  {/* Context snapshot */}
                  {decision.contextSnapshot.length > 0 && (
                    <div className="mt-2 rounded bg-[var(--bg-tertiary)] px-2 py-1.5 space-y-0.5">
                      <p className="text-[9px] font-semibold uppercase text-[var(--text-muted)] mb-0.5">
                        Context Snapshot
                      </p>
                      {decision.contextSnapshot.map((ctx) => (
                        <div key={ctx.key} className="flex items-baseline gap-1.5">
                          <span className="text-[9px] text-[var(--text-muted)] shrink-0">
                            {ctx.key}:
                          </span>
                          <span className="text-[9px] text-[var(--text-secondary)]">{ctx.value}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
