"use client";

import type { BaselineSummary } from "@/lib/api";

interface BaselineComparisonProps {
  summary: BaselineSummary;
}

export function BaselineComparison({ summary }: BaselineComparisonProps) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-3">
        Baseline vs Current ({summary.total_compared} jobs)
      </h3>
      <div className="space-y-3">
        {summary.comparisons.map((comp) => (
          <div key={comp.job_id} className="space-y-1">
            <p className="text-[10px] font-medium text-[var(--text-muted)]">
              Job: {comp.job_id}
            </p>
            {Object.entries(comp.deltas).map(([metric, delta]) => {
              const baseVal = comp.baseline[metric] ?? 0;
              const isPositive = delta > 0;
              const pctChange = baseVal !== 0 ? ((delta / baseVal) * 100).toFixed(1) : "N/A";
              const barWidth = Math.min(Math.abs(delta) * 100, 100);

              return (
                <div key={metric} className="flex items-center gap-2">
                  <span className="text-[10px] text-[var(--text-muted)] w-20 shrink-0">{metric}</span>
                  <div className="flex-1 h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        isPositive ? "bg-green-400" : "bg-red-400"
                      }`}
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                  <span className={`text-[10px] font-medium w-16 text-right ${isPositive ? "text-green-400" : "text-red-400"}`}>
                    {isPositive ? "+" : ""}{typeof delta === "number" ? delta.toFixed(3) : delta}
                  </span>
                  <span className="text-[10px] text-[var(--text-muted)] w-12 text-right">
                    {pctChange}%
                  </span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
