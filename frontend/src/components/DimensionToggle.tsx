"use client";

interface DimensionToggleProps {
  view: "A" | "B";
  onToggle: (view: "A" | "B") => void;
  dimAConfig?: Record<string, string[]>;
  dimBMetrics?: Array<{
    name: string;
    description: string;
    target: string;
    switch_trigger_threshold: string;
  }>;
}

export function DimensionToggle({ view, onToggle, dimAConfig, dimBMetrics }: DimensionToggleProps) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
      <div className="flex items-center gap-2 mb-3">
        <button
          onClick={() => onToggle("A")}
          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
            view === "A"
              ? "bg-[var(--accent)] text-white"
              : "bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
          }`}
        >
          Experience (Dim A)
        </button>
        <button
          onClick={() => onToggle("B")}
          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
            view === "B"
              ? "bg-[var(--accent)] text-white"
              : "bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
          }`}
        >
          Metrics (Dim B)
        </button>
      </div>

      {view === "A" ? (
        <div>
          {dimAConfig && Object.keys(dimAConfig).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(dimAConfig).map(([role, markers]) => (
                <div key={role}>
                  <p className="text-[10px] font-semibold uppercase text-[var(--text-muted)] mb-1">{role.replace("_", " ")}</p>
                  <ul className="space-y-0.5">
                    {markers.map((m, i) => (
                      <li key={i} className="text-xs text-[var(--text-primary)]">{m}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-[var(--text-muted)]">No experience markers defined yet.</p>
          )}
        </div>
      ) : (
        <div>
          {dimBMetrics && dimBMetrics.length > 0 ? (
            <div className="space-y-2">
              {dimBMetrics.map((m, i) => (
                <div key={i} className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-medium text-[var(--text-primary)]">{m.name}</p>
                    <p className="text-[10px] text-[var(--text-muted)]">{m.description}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-[10px] text-[var(--text-muted)]">{m.target}</p>
                    {m.switch_trigger_threshold && (
                      <p className="text-[10px] text-red-400">Switch: {m.switch_trigger_threshold}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-[var(--text-muted)]">No Dimension B metrics defined yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
