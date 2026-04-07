"use client";

import { useState, useCallback } from "react";
import { ChevronRight, ChevronDown, Sparkles, Loader2 } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { generateHierarchy, getHierarchyTree, type TreeNode } from "@/lib/api";

const TIER_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  T1_strategic: { bg: "bg-violet-500/15", text: "text-violet-400", label: "Strategic" },
  T2_core: { bg: "bg-blue-500/15", text: "text-blue-400", label: "Core" },
  T3_execution: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "Execution" },
  T4_experience: { bg: "bg-amber-500/15", text: "text-amber-400", label: "Experience" },
};

export function HierarchyPanel() {
  const {
    hierarchyTree,
    hierarchy,
    isGeneratingHierarchy,
    setHierarchy,
    setGeneratingHierarchy,
  } = useAppStore();

  const [domain, setDomain] = useState("");

  const handleGenerate = useCallback(async () => {
    if (!domain.trim() || isGeneratingHierarchy) return;
    setGeneratingHierarchy(true);
    try {
      const result = await generateHierarchy({
        domain: domain.trim(),
        keywords: domain.split(/[,\s]+/).filter(Boolean),
      });
      const tree = await getHierarchyTree(result.id);
      setHierarchy(result, tree.tree);
    } catch (err) {
      console.error("Hierarchy generation failed:", err);
    } finally {
      setGeneratingHierarchy(false);
    }
  }, [domain, isGeneratingHierarchy, setHierarchy, setGeneratingHierarchy]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border)]">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-3">
          Job Hierarchy
        </h2>
        <div className="flex gap-2">
          <input
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
            placeholder="Domain (e.g. B2B SaaS)"
            className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
          />
          <button
            onClick={handleGenerate}
            disabled={!domain.trim() || isGeneratingHierarchy}
            className="flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
          >
            {isGeneratingHierarchy ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Sparkles className="w-3 h-3" />
            )}
            Generate
          </button>
        </div>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto px-3 py-3">
        {hierarchyTree && hierarchyTree.length > 0 ? (
          <div className="space-y-1">
            {hierarchyTree.map((node) => (
              <TreeNodeComponent key={node.id} node={node} depth={0} />
            ))}
          </div>
        ) : isGeneratingHierarchy ? (
          <div className="flex flex-col items-center justify-center h-full text-[var(--text-muted)]">
            <Loader2 className="w-6 h-6 animate-spin mb-2" />
            <p className="text-xs">Generating hierarchy...</p>
          </div>
        ) : (
          <EmptyState />
        )}

        {/* Summary */}
        {hierarchy && (
          <div className="mt-4 pt-3 border-t border-[var(--border)]">
            <div className="flex flex-wrap gap-2">
              {Object.entries(hierarchy.summary)
                .filter(([k]) => k.startsWith("T"))
                .map(([tier, count]) => {
                  const style = TIER_COLORS[tier] || TIER_COLORS.T1_strategic;
                  return (
                    <span
                      key={tier}
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] ${style.bg} ${style.text}`}
                    >
                      {style.label}: {count as number}
                    </span>
                  );
                })}
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] bg-[var(--bg-tertiary)] text-[var(--text-muted)]">
                Total: {hierarchy.summary.total_jobs}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function TreeNodeComponent({ node, depth }: { node: TreeNode; depth: number }) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.children && node.children.length > 0;
  const style = TIER_COLORS[node.tier] || TIER_COLORS.T1_strategic;

  return (
    <div className="tree-node-enter">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-start gap-1.5 w-full text-left rounded-lg px-2 py-1.5 hover:bg-[var(--bg-tertiary)] transition-colors group"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {/* Expand/collapse icon */}
        <span className="mt-0.5 shrink-0 w-4 h-4 flex items-center justify-center">
          {hasChildren ? (
            expanded ? (
              <ChevronDown className="w-3 h-3 text-[var(--text-muted)]" />
            ) : (
              <ChevronRight className="w-3 h-3 text-[var(--text-muted)]" />
            )
          ) : (
            <span className={`w-1.5 h-1.5 rounded-full ${style.bg}`} />
          )}
        </span>

        {/* Tier badge */}
        <span
          className={`shrink-0 mt-0.5 rounded px-1 py-0 text-[9px] font-medium uppercase ${style.bg} ${style.text}`}
        >
          {style.label.charAt(0)}
          {node.tier.split("_")[0].replace("T", "")}
        </span>

        {/* Statement */}
        <span className="text-xs text-[var(--text-primary)] leading-relaxed">
          {node.statement}
        </span>
      </button>

      {/* Children */}
      {expanded && hasChildren && (
        <div>
          {node.children!.map((child) => (
            <TreeNodeComponent key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center mb-3">
        <Sparkles className="w-4 h-4 text-[var(--text-muted)]" />
      </div>
      <p className="text-xs text-[var(--text-secondary)] mb-1">No hierarchy yet</p>
      <p className="text-[11px] text-[var(--text-muted)] max-w-48">
        Enter a domain above to generate a structured job hierarchy.
      </p>
    </div>
  );
}
