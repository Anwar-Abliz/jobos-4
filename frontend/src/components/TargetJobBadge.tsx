"use client";

import { useState } from "react";
import { Lock, Unlock } from "lucide-react";
import { useAppStore } from "@/lib/store";

const TIER_LABELS: Record<string, { label: string; color: string }> = {
  T1_strategic: { label: "Strategic", color: "text-violet-400 bg-violet-500/15" },
  T2_core: { label: "Core", color: "text-blue-400 bg-blue-500/15" },
  T3_execution: { label: "Execution", color: "text-emerald-400 bg-emerald-500/15" },
  T4_micro: { label: "Micro", color: "text-amber-400 bg-amber-500/15" },
};

interface TargetJobBadgeProps {
  readOnly?: boolean;
}

export function TargetJobBadge({ readOnly = false }: TargetJobBadgeProps) {
  const targetJob = useAppStore((s) => s.targetJob);
  const unlockTargetJob = useAppStore((s) => s.unlockTargetJob);
  const [confirmingUnlock, setConfirmingUnlock] = useState(false);

  if (!targetJob) return null;

  const tierInfo = TIER_LABELS[targetJob.tier] || TIER_LABELS.T1_strategic;

  return (
    <div className="rounded-lg border border-[var(--accent)]/30 bg-[var(--accent-dim)] px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Lock className="w-3 h-3 text-[var(--accent)] shrink-0" />
          <span className={`shrink-0 rounded px-1.5 py-0 text-[9px] font-medium uppercase ${tierInfo.color}`}>
            {tierInfo.label}
          </span>
          <span className="text-xs text-[var(--text-primary)] truncate">
            {targetJob.statement}
          </span>
        </div>
        {!readOnly && (
          <>
            {confirmingUnlock ? (
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => {
                    unlockTargetJob();
                    setConfirmingUnlock(false);
                  }}
                  className="text-[10px] font-medium text-red-400 hover:text-red-300 transition-colors"
                >
                  Confirm
                </button>
                <button
                  onClick={() => setConfirmingUnlock(false)}
                  className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmingUnlock(true)}
                className="flex items-center gap-1 text-[10px] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors shrink-0"
                title="Unlock target job"
              >
                <Unlock className="w-3 h-3" />
                Unlock
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
