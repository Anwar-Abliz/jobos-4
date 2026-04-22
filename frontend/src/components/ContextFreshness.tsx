"use client";

import { Wifi, Camera, WifiOff, Clock } from "lucide-react";

type FreshnessLevel = "live" | "snapshot" | "stale";

interface FreshnessEntry {
  entityId: string;
  entityLabel: string;
  freshness: FreshnessLevel;
  lastUpdated: string;
  sourceLabel?: string;
}

interface ContextFreshnessProps {
  entries: FreshnessEntry[];
}

const FRESHNESS_STYLES: Record<
  FreshnessLevel,
  { icon: typeof Wifi; color: string; bg: string; label: string; pulse: boolean }
> = {
  live: {
    icon: Wifi,
    color: "text-green-400",
    bg: "bg-green-500/10",
    label: "Live",
    pulse: true,
  },
  snapshot: {
    icon: Camera,
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    label: "Snapshot",
    pulse: false,
  },
  stale: {
    icon: WifiOff,
    color: "text-red-400",
    bg: "bg-red-500/10",
    label: "Stale",
    pulse: false,
  },
};

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

export function ContextFreshness({ entries }: ContextFreshnessProps) {
  const counts = {
    live: entries.filter((e) => e.freshness === "live").length,
    snapshot: entries.filter((e) => e.freshness === "snapshot").length,
    stale: entries.filter((e) => e.freshness === "stale").length,
  };

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Context Freshness
          </h3>
        </div>
        <div className="flex gap-2">
          {(["live", "snapshot", "stale"] as FreshnessLevel[]).map((level) => {
            const style = FRESHNESS_STYLES[level];
            return (
              <span
                key={level}
                className={`inline-flex items-center gap-1 text-[9px] font-medium ${style.color}`}
              >
                {counts[level]} {style.label.toLowerCase()}
              </span>
            );
          })}
        </div>
      </div>

      {entries.length === 0 ? (
        <p className="text-xs text-[var(--text-muted)]">No entities tracked.</p>
      ) : (
        <div className="space-y-1.5">
          {entries.map((entry) => {
            const style = FRESHNESS_STYLES[entry.freshness];
            const Icon = style.icon;

            return (
              <div
                key={entry.entityId}
                className="flex items-center gap-2 rounded bg-[var(--bg-primary)] px-2.5 py-1.5"
              >
                <div className="relative shrink-0">
                  <Icon className={`w-3.5 h-3.5 ${style.color}`} />
                  {style.pulse && (
                    <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                  )}
                </div>

                <span className="text-xs text-[var(--text-primary)] truncate flex-1 min-w-0">
                  {entry.entityLabel}
                </span>

                {entry.sourceLabel && (
                  <span className="text-[9px] text-[var(--text-muted)] shrink-0">
                    {entry.sourceLabel}
                  </span>
                )}

                <span
                  className={`shrink-0 rounded px-1.5 py-0 text-[9px] font-medium ${style.bg} ${style.color}`}
                >
                  {style.label}
                </span>

                <span className="text-[9px] text-[var(--text-muted)] shrink-0 w-12 text-right">
                  {timeAgo(entry.lastUpdated)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
