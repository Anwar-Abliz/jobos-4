"use client";

import { CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import type { PhaseEvaluation } from "@/lib/api";

interface GoNoGoWidgetProps {
  evaluation: PhaseEvaluation;
}

const VERDICT_CONFIG = {
  go: {
    bg: "bg-green-500/10 border-green-500/30",
    icon: CheckCircle,
    iconColor: "text-green-400",
    label: "GO",
    labelColor: "text-green-400",
  },
  no_go: {
    bg: "bg-red-500/10 border-red-500/30",
    icon: XCircle,
    iconColor: "text-red-400",
    label: "NO GO",
    labelColor: "text-red-400",
  },
  inconclusive: {
    bg: "bg-amber-500/10 border-amber-500/30",
    icon: AlertTriangle,
    iconColor: "text-amber-400",
    label: "INCONCLUSIVE",
    labelColor: "text-amber-400",
  },
};

export function GoNoGoWidget({ evaluation }: GoNoGoWidgetProps) {
  const config = VERDICT_CONFIG[evaluation.verdict] || VERDICT_CONFIG.inconclusive;
  const Icon = config.icon;

  return (
    <div className={`rounded-lg border ${config.bg} p-4`}>
      <div className="flex items-center gap-3">
        <Icon className={`w-6 h-6 ${config.iconColor}`} />
        <div>
          <span className={`text-sm font-bold ${config.labelColor}`}>{config.label}</span>
          <span className="text-xs text-[var(--text-muted)] ml-2">
            Phase Evaluation
          </span>
        </div>
      </div>
      {evaluation.reasons.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {evaluation.reasons.map((r, i) => (
            <li key={i} className="text-xs text-[var(--text-secondary)]">• {r}</li>
          ))}
        </ul>
      )}
      <div className="flex gap-4 mt-2 text-[10px] text-[var(--text-muted)]">
        <span>{evaluation.switch_events_count} switch event(s)</span>
        <span>{evaluation.comparisons_count} comparison(s)</span>
      </div>
    </div>
  );
}
