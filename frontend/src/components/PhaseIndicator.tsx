"use client";

import { Check } from "lucide-react";
import { useAppStore } from "@/lib/store";

const PHASES = [
  { num: 1, label: "Identify" },
  { num: 2, label: "Define" },
  { num: 3, label: "Decide" },
] as const;

export function PhaseIndicator() {
  const currentPhase = useAppStore((s) => s.currentPhase);

  return (
    <div className="flex items-center justify-center gap-0 px-4 py-2">
      {PHASES.map((phase, i) => {
        const isActive = phase.num === currentPhase;
        const isCompleted = phase.num < currentPhase;

        return (
          <div key={phase.num} className="flex items-center">
            {i > 0 && (
              <div
                className={`w-8 h-px mx-1 ${
                  isCompleted || isActive ? "bg-[var(--accent)]" : "bg-[var(--border)]"
                }`}
              />
            )}
            <div className="flex items-center gap-1.5">
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold transition-colors ${
                  isCompleted
                    ? "bg-[var(--accent)] text-white"
                    : isActive
                    ? "bg-[var(--accent)] text-white"
                    : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
                }`}
              >
                {isCompleted ? <Check className="w-3 h-3" /> : phase.num}
              </div>
              <span
                className={`text-[10px] font-medium ${
                  isActive
                    ? "text-[var(--accent)]"
                    : isCompleted
                    ? "text-[var(--text-secondary)]"
                    : "text-[var(--text-muted)]"
                }`}
              >
                {phase.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
