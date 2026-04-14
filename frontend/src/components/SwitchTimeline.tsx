"use client";

import type { SwitchEvent } from "@/lib/api";

interface SwitchTimelineProps {
  events: SwitchEvent[];
}

export function SwitchTimeline({ events }: SwitchTimelineProps) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-3">
        Switch Events ({events.length})
      </h3>
      <div className="relative pl-4 border-l-2 border-[var(--border)] space-y-4">
        {events.map((evt) => (
          <div key={evt.id} className="relative">
            <div
              className={`absolute -left-[21px] w-3 h-3 rounded-full border-2 border-[var(--bg-secondary)] ${
                evt.action === "fire"
                  ? "bg-red-400"
                  : evt.action === "hire"
                  ? "bg-green-400"
                  : "bg-yellow-400"
              }`}
            />
            <div className="ml-2">
              <div className="flex items-center gap-2">
                <span
                  className={`text-[10px] font-semibold uppercase ${
                    evt.action === "fire" ? "text-red-400" : "text-green-400"
                  }`}
                >
                  {evt.action}
                </span>
                <span className="text-[10px] text-[var(--text-muted)]">
                  {new Date(evt.occurred_at).toLocaleString()}
                </span>
              </div>
              <p className="text-xs text-[var(--text-primary)] mt-0.5">
                <span className="font-medium">{evt.trigger_metric}</span> = {evt.trigger_value}
                {evt.trigger_bound && (
                  <span className="text-[var(--text-muted)]"> (bound: {evt.trigger_bound})</span>
                )}
              </p>
              {evt.reason && (
                <p className="text-[10px] text-[var(--text-muted)] mt-0.5">{evt.reason}</p>
              )}
              {evt.resolution && (
                <p className="text-[10px] text-green-400 mt-0.5">Resolved: {evt.resolution}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
