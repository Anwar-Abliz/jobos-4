"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import { useAppStore } from "@/lib/store";
import type { TreeNode } from "@/lib/api";

const TIER_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  T1_strategic: { bg: "bg-violet-500/15", text: "text-violet-400", label: "Strategic" },
  T2_core: { bg: "bg-blue-500/15", text: "text-blue-400", label: "Core" },
  T3_execution: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "Execution" },
  T4_micro: { bg: "bg-amber-500/15", text: "text-amber-400", label: "Micro" },
};

export function JobTreeView() {
  const functionalSpine = useAppStore((s) => s.hierarchyFunctionalSpine);
  const experienceDimension = useAppStore((s) => s.hierarchyExperienceDimension);

  if (!functionalSpine || functionalSpine.length === 0) return null;

  return (
    <div className="space-y-1">
      {functionalSpine.map((node) => (
        <TreeNodeComponent key={node.id} node={node} depth={0} />
      ))}
      {experienceDimension && experienceDimension.length > 0 && (
        <>
          <div className="mt-3 mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Experience Dimension
          </div>
          {experienceDimension.map((node) => (
            <TreeNodeComponent key={node.id} node={node} depth={0} />
          ))}
        </>
      )}
    </div>
  );
}

function TreeNodeComponent({ node, depth }: { node: TreeNode; depth: number }) {
  const [expanded, setExpanded] = useState(depth < 2);
  const selectedJobId = useAppStore((s) => s.selectedJobId);
  const setSelectedJobId = useAppStore((s) => s.setSelectedJobId);
  const hasChildren = node.children && node.children.length > 0;
  const style = TIER_COLORS[node.tier] || TIER_COLORS.T1_strategic;
  const isSelected = node.id === selectedJobId;

  return (
    <div className="tree-node-enter">
      <button
        onClick={() => {
          setSelectedJobId(node.id);
          if (hasChildren) setExpanded(!expanded);
        }}
        className={`flex items-start gap-1.5 w-full text-left rounded-lg px-2 py-1.5 transition-colors group ${
          isSelected
            ? "bg-[var(--accent-dim)] ring-1 ring-[var(--accent)]/40"
            : "hover:bg-[var(--bg-tertiary)]"
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
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

        <span
          className={`shrink-0 mt-0.5 rounded px-1 py-0 text-[9px] font-medium uppercase ${style.bg} ${style.text}`}
        >
          {style.label.charAt(0)}
          {node.tier.split("_")[0].replace("T", "")}
        </span>

        <span className="text-xs text-[var(--text-primary)] leading-relaxed">
          {node.statement}
        </span>
      </button>

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
