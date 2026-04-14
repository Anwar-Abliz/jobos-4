/**
 * Transforms flat HierarchyJob[] + HierarchyEdge[] into graph data
 * suitable for react-force-graph-2d.
 */
import type { HierarchyJob, HierarchyEdge } from "./api";

export interface GraphNode {
  id: string;
  label: string;
  tier: string;
  category: string;
  color: string;
  size: number;
  statement: string;
  rationale: string;
  metricsHint: string[];
}

export interface GraphLink {
  source: string;
  target: string;
  strength: number;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

const TIER_COLORS: Record<string, string> = {
  T1_strategic: "#8b5cf6",
  T2_core: "#3b82f6",
  T3_execution: "#10b981",
  T4_micro: "#f59e0b",
};

const TIER_SIZES: Record<string, number> = {
  T1_strategic: 16,
  T2_core: 12,
  T3_execution: 8,
  T4_micro: 5,
};

const TIER_LABELS: Record<string, string> = {
  T1_strategic: "Strategic",
  T2_core: "Core",
  T3_execution: "Execution",
  T4_micro: "Micro",
};

export function buildGraphData(
  jobs: HierarchyJob[],
  edges: HierarchyEdge[],
): GraphData {
  const nodes: GraphNode[] = jobs.map((j) => ({
    id: j.id,
    label: j.statement.length > 40 ? j.statement.slice(0, 37) + "..." : j.statement,
    tier: j.tier,
    category: j.category,
    color: TIER_COLORS[j.tier] || TIER_COLORS.T1_strategic,
    size: TIER_SIZES[j.tier] || 8,
    statement: j.statement,
    rationale: j.rationale,
    metricsHint: j.metrics_hint,
  }));

  const nodeIds = new Set(jobs.map((j) => j.id));
  const links: GraphLink[] = edges
    .filter((e) => nodeIds.has(e.parent_id) && nodeIds.has(e.child_id))
    .map((e) => ({
      source: e.parent_id,
      target: e.child_id,
      strength: e.strength,
    }));

  return { nodes, links };
}

export { TIER_COLORS, TIER_LABELS };
