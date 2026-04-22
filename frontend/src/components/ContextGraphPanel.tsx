"use client";

import { GitBranch, ZoomIn, ZoomOut } from "lucide-react";

interface ContextNode {
  id: string;
  label: string;
  type: "job" | "executor" | "capability" | "imperfection" | "context" | "evidence";
  vfe?: number;
}

interface ContextEdge {
  source: string;
  target: string;
  relationship: string;
}

interface ContextGraphPanelProps {
  nodes: ContextNode[];
  edges: ContextEdge[];
  focusNodeId?: string;
  onNodeSelect?: (nodeId: string) => void;
}

const NODE_TYPE_STYLES: Record<ContextNode["type"], { bg: string; border: string; text: string }> = {
  job: { bg: "bg-violet-500/15", border: "border-violet-500/40", text: "text-violet-400" },
  executor: { bg: "bg-cyan-500/15", border: "border-cyan-500/40", text: "text-cyan-400" },
  capability: { bg: "bg-emerald-500/15", border: "border-emerald-500/40", text: "text-emerald-400" },
  imperfection: { bg: "bg-red-500/15", border: "border-red-500/40", text: "text-red-400" },
  context: { bg: "bg-amber-500/15", border: "border-amber-500/40", text: "text-amber-400" },
  evidence: { bg: "bg-blue-500/15", border: "border-blue-500/40", text: "text-blue-400" },
};

export function ContextGraphPanel({
  nodes,
  edges,
  focusNodeId,
  onNodeSelect,
}: ContextGraphPanelProps) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <GitBranch className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Context Graph
          </h3>
        </div>
        <div className="flex items-center gap-1">
          <button className="p-1 rounded hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors">
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button className="p-1 rounded hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors">
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Type legend */}
      <div className="flex flex-wrap gap-2 mb-3">
        {Object.entries(NODE_TYPE_STYLES).map(([type, style]) => (
          <div key={type} className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${style.bg} border ${style.border}`} />
            <span className="text-[9px] text-[var(--text-muted)] capitalize">{type}</span>
          </div>
        ))}
      </div>

      {/* Node list with edge connections */}
      <div className="space-y-2 max-h-[400px] overflow-y-auto">
        {nodes.map((node) => {
          const style = NODE_TYPE_STYLES[node.type] || NODE_TYPE_STYLES.context;
          const isFocused = node.id === focusNodeId;
          const outEdges = edges.filter((e) => e.source === node.id);
          const inEdges = edges.filter((e) => e.target === node.id);

          return (
            <div
              key={node.id}
              className={`rounded-lg border p-2.5 cursor-pointer transition-all ${
                isFocused
                  ? `${style.bg} ${style.border} ring-1 ring-[var(--accent)]/30`
                  : `bg-[var(--bg-primary)] border-[var(--border)] hover:border-[var(--text-muted)]`
              }`}
              onClick={() => onNodeSelect?.(node.id)}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`shrink-0 rounded px-1.5 py-0 text-[9px] font-medium uppercase ${style.bg} ${style.text}`}
                >
                  {node.type}
                </span>
                <span className="text-xs text-[var(--text-primary)] truncate">{node.label}</span>
                {node.vfe !== undefined && (
                  <span className="ml-auto text-[10px] font-mono text-[var(--text-muted)] shrink-0">
                    VFE {node.vfe.toFixed(3)}
                  </span>
                )}
              </div>

              {/* Edges summary */}
              {(outEdges.length > 0 || inEdges.length > 0) && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {outEdges.map((e, i) => {
                    const targetNode = nodes.find((n) => n.id === e.target);
                    return (
                      <span
                        key={`out-${i}`}
                        className="inline-flex items-center gap-0.5 text-[9px] text-[var(--text-muted)] bg-[var(--bg-tertiary)] rounded px-1 py-0"
                      >
                        {e.relationship} &rarr;{" "}
                        <span className="text-[var(--text-secondary)]">
                          {targetNode?.label || e.target}
                        </span>
                      </span>
                    );
                  })}
                  {inEdges.map((e, i) => {
                    const sourceNode = nodes.find((n) => n.id === e.source);
                    return (
                      <span
                        key={`in-${i}`}
                        className="inline-flex items-center gap-0.5 text-[9px] text-[var(--text-muted)] bg-[var(--bg-tertiary)] rounded px-1 py-0"
                      >
                        <span className="text-[var(--text-secondary)]">
                          {sourceNode?.label || e.source}
                        </span>{" "}
                        &rarr; {e.relationship}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer stats */}
      <div className="flex gap-4 mt-3 pt-2 border-t border-[var(--border)]">
        <span className="text-[10px] text-[var(--text-muted)]">{nodes.length} nodes</span>
        <span className="text-[10px] text-[var(--text-muted)]">{edges.length} edges</span>
      </div>
    </div>
  );
}
