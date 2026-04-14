"use client";

import { List, Network } from "lucide-react";
import { useAppStore } from "@/lib/store";

export function ViewToggle() {
  const visualizationMode = useAppStore((s) => s.visualizationMode);
  const setVisualizationMode = useAppStore((s) => s.setVisualizationMode);

  return (
    <div className="inline-flex rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] p-0.5">
      <button
        onClick={() => setVisualizationMode("tree")}
        className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${
          visualizationMode === "tree"
            ? "bg-[var(--accent)] text-white"
            : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
        }`}
      >
        <List className="w-3 h-3" />
        Tree
      </button>
      <button
        onClick={() => setVisualizationMode("graph")}
        className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${
          visualizationMode === "graph"
            ? "bg-[var(--accent)] text-white"
            : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
        }`}
      >
        <Network className="w-3 h-3" />
        Graph
      </button>
    </div>
  );
}
