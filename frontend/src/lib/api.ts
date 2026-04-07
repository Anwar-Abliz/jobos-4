/**
 * JobOS 4.0 — API Client
 * Connects to the FastAPI backend at localhost:8000
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

// ── Chat ────────────────────────────────────────────────

export interface ChatRequest {
  message: string;
  session_id?: string;
  job_id?: string;
}

export interface ChatResponse {
  session_id: string;
  assistant_message: string;
  intent: string;
  entities_created: Array<{ id: string; name: string; type: string }>;
  entities_updated: Array<{ id: string; name: string; type: string }>;
  imperfections: Array<{
    metric_name: string;
    severity: number;
    is_blocker: boolean;
    ips_score: number;
  }>;
  vfe_current: number | null;
  top_blocker: Record<string, unknown> | null;
}

export function sendChat(req: ChatRequest): Promise<ChatResponse> {
  return apiFetch("/chat", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// ── Hierarchy ───────────────────────────────────────────

export interface HierarchyRequest {
  domain: string;
  keywords?: string[];
  actor?: string;
  goal?: string;
  constraints?: string;
}

export interface HierarchyJob {
  id: string;
  tier: string;
  statement: string;
  category: string;
  rationale: string;
  metrics_hint: string[];
}

export interface HierarchyEdge {
  parent_id: string;
  child_id: string;
  strength: number;
}

export interface HierarchyResponse {
  id: string;
  domain: string;
  jobs: HierarchyJob[];
  edges: HierarchyEdge[];
  summary: Record<string, number>;
}

export interface HierarchyTree {
  id: string;
  domain: string;
  tree: TreeNode[];
}

export interface TreeNode {
  id: string;
  tier: string;
  statement: string;
  category: string;
  metrics_hint: string[];
  children?: TreeNode[];
}

export function generateHierarchy(req: HierarchyRequest): Promise<HierarchyResponse> {
  return apiFetch("/hierarchy/generate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function getHierarchyTree(id: string): Promise<HierarchyTree> {
  return apiFetch(`/hierarchy/${id}/tree`);
}

// ── Health ───────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  version: string;
  neo4j: boolean;
  postgresql: boolean;
  nsaig_engine: boolean;
  cdee_engine: boolean;
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch("/health".replace("/api", ""), {
    // health is at /health, not /api/health
  });
}
