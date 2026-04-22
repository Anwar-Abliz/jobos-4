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
    vfe_score: number;
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
  executor_type?: "HUMAN" | "AI";
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
  related_jobs?: HierarchyJob[];
}

export interface HierarchyTree {
  id: string;
  domain: string;
  functional_spine: TreeNode[];
  experience_dimension: TreeNode[];
}

export interface TreeNode {
  id: string;
  tier: string;
  statement: string;
  category: string;
  metrics_hint: string[];
  executor_type?: "HUMAN" | "AI";
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

// ── Segments ────────────────────────────────────────────

export interface Segment {
  id: string;
  name: string;
  slug: string;
  description: string;
  root_job_ids: string[];
  tags: string[];
  status: string;
}

export interface Scenario {
  id: string;
  name: string;
  slug: string;
  pilot_id: string;
  hypothesis: string;
  exit_criteria?: string;
  risks?: Array<{ risk: string; mitigation: string }>;
  dimension_b_metrics?: Array<{
    name: string;
    description: string;
    target: string;
    switch_trigger_threshold: string;
  }>;
  dimension_a_config?: Record<string, string[]>;
  status: string;
  phase: string;
  segment_id?: string;
}

export interface ScenarioTree {
  id: string;
  scenario_name: string;
  functional_spine: TreeNode[];
  experience_dimension: TreeNode[];
}

export function listSegments(): Promise<Segment[]> {
  return apiFetch("/segments");
}

export function getSegment(id: string): Promise<Segment> {
  return apiFetch(`/segments/${id}`);
}

export function getSegmentScenarios(id: string): Promise<Scenario[]> {
  return apiFetch(`/segments/${id}/scenarios`);
}

export function getScenario(id: string): Promise<Scenario> {
  return apiFetch(`/scenarios/${id}`);
}

export function getScenarioJobTree(id: string): Promise<ScenarioTree> {
  return apiFetch(`/scenarios/${id}/tree`);
}

// ── Experience ──────────────────────────────────────────

export interface ExperienceResult {
  experience_id: string;
  job_id: string;
  version: number;
  markers: {
    feel_markers: string[];
    to_be_markers: string[];
  };
  source: string;
  confidence: number;
  reconciliation_score?: number;
}

export interface ExperienceVersion {
  id: string;
  job_id: string;
  version: number;
  markers: Record<string, string[]>;
  source: string;
  confidence: number | null;
  created_by: string | null;
  created_at: string;
}

export function generateExperience(
  jobId: string,
  roleArchetype?: string,
): Promise<ExperienceResult> {
  return apiFetch("/experience/generate", {
    method: "POST",
    body: JSON.stringify({
      job_id: jobId,
      role_archetype: roleArchetype || "",
    }),
  });
}

export function editExperience(
  jobId: string,
  feelMarkers: string[],
  toBeMarkers: string[],
): Promise<ExperienceResult> {
  return apiFetch(`/experience/${jobId}`, {
    method: "PATCH",
    body: JSON.stringify({
      feel_markers: feelMarkers,
      to_be_markers: toBeMarkers,
    }),
  });
}

export function getExperienceHistory(
  jobId: string,
): Promise<ExperienceVersion[]> {
  return apiFetch(`/experience/${jobId}/history`);
}

// ── Baseline & Switch ───────────────────────────────────

export interface BaselineResult {
  scenario_id: string;
  snapshots: Array<{
    id: string;
    job_id: string;
    metrics: Record<string, number>;
    bounds: Record<string, number[]>;
  }>;
  total_jobs: number;
}

export interface BaselineSummary {
  scenario_id: string;
  comparisons: Array<{
    job_id: string;
    baseline: Record<string, number>;
    current: Record<string, number>;
    deltas: Record<string, number>;
  }>;
  total_compared: number;
}

export interface SwitchEvent {
  id: string;
  scenario_id: string;
  job_id: string;
  trigger_metric: string;
  trigger_value: number;
  trigger_bound: string;
  action: string;
  reason: string;
  occurred_at: string;
  resolved_at: string | null;
  resolution: string | null;
}

export interface PhaseEvaluation {
  scenario_id: string;
  verdict: "go" | "no_go" | "inconclusive";
  reasons: string[];
  switch_events_count: number;
  comparisons_count: number;
}

export function captureBaseline(scenarioId: string): Promise<BaselineResult> {
  return apiFetch(`/scenarios/${scenarioId}/baseline/capture`, {
    method: "POST",
    body: JSON.stringify({ captured_by: "user" }),
  });
}

export function getBaselineSummary(
  scenarioId: string,
): Promise<BaselineSummary> {
  return apiFetch(`/scenarios/${scenarioId}/baseline/summary`);
}

export function getSwitchEvents(
  scenarioId: string,
): Promise<SwitchEvent[]> {
  return apiFetch(`/scenarios/${scenarioId}/switch-events`);
}

export function evaluatePhase(
  scenarioId: string,
): Promise<PhaseEvaluation> {
  return apiFetch(`/scenarios/${scenarioId}/evaluate-phase`);
}

// ── Preliminary Recommendation ──────────────────────────

export interface PreliminaryRecommendation {
  job_id: string;
  recommendation: "switch_to_ai" | "keep_human" | "needs_more_data";
  confidence: number;
  reasoning: string;
  evaluation_method: string;
  evaluation_criteria: string[];
  factors: Array<{
    factor: string;
    explanation: string;
    impact: string;
    weight: number;
  }>;
}

export function getPreliminaryRecommendation(
  jobId: string,
  outcomes: {
    experience_markers?: { feel_markers: string[]; to_be_markers: string[] };
    metrics?: Array<{
      statement: string;
      target: string;
      switch_threshold: string;
    }>;
  },
): Promise<PreliminaryRecommendation> {
  return apiFetch("/recommendation/preliminary", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId, outcomes }),
  });
}

// ── Extraction ──────────────────────────────────────────

export interface ExtractedContent {
  text: string;
  title: string;
  source: string;
  context: {
    who: string;
    why: string;
    what: string;
    where: string;
    when: string;
    how: string;
  };
  keywords: string[];
  job_hints: string[];
  hierarchy?: {
    domain: string;
    jobs: HierarchyJob[];
    edges: HierarchyEdge[];
    summary: Record<string, number>;
  };
}

export function extractFromUrl(url: string): Promise<ExtractedContent> {
  return apiFetch("/extract/url", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function extractFromDocument(file: File): Promise<ExtractedContent> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/extract/document`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

// ── Entity Update ────────────────────────────────────────

export interface EntityBase {
  id: string;
  name: string;
  statement: string;
  type: string;
  properties: Record<string, unknown>;
}

export function updateEntity(
  id: string,
  updates: {
    name?: string;
    statement?: string;
    properties?: Record<string, unknown>;
  },
): Promise<EntityBase> {
  return apiFetch(`/entities/${id}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

// ── SAP Context Graph ──────────────────────────────────

export interface SAPProcess {
  id: string;
  name: string;
  sap_module: string;
  process_type: string;
  automation_level: number;
  context_freshness: string;
}

export interface ContextSnapshot {
  snapshot_id: string;
  entity_id: string;
}

export interface FreshnessStatus {
  entity_id: string;
  stale: boolean;
  age_hours: number;
  freshness: "live" | "snapshot" | "stale";
  threshold_hours: number;
}

export interface ContextCoverage {
  scope_id: string;
  total_steps: number;
  covered_steps: number;
  coverage_pct: number;
}

export function ingestProcess(templateName: string): Promise<{ entity_id: string }> {
  return apiFetch("/sap/ingest/process", {
    method: "POST",
    body: JSON.stringify({ template_name: templateName }),
  });
}

export function ingestOrgStructure(): Promise<{ entity_id: string }> {
  return apiFetch("/sap/ingest/org-structure", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function listSAPProcesses(): Promise<SAPProcess[]> {
  return apiFetch("/sap/processes");
}

export function getSAPProcessContext(processId: string): Promise<Record<string, unknown>> {
  return apiFetch(`/sap/processes/${processId}/context`);
}

export function captureContextSnapshot(entityId: string): Promise<ContextSnapshot> {
  return apiFetch(`/context/snapshot/${entityId}`, { method: "POST" });
}

export function checkFreshness(entityId: string): Promise<FreshnessStatus> {
  return apiFetch(`/context/freshness/${entityId}`);
}

export function getContextCoverage(scopeId: string): Promise<ContextCoverage> {
  return apiFetch(`/context/coverage/${scopeId}`);
}

// ── Decisions ──────────────────────────────────────────

export interface DecisionRecord {
  decision_id: string;
  actor: string;
  action: string;
  target_entity_id: string;
  rationale: string;
}

export interface DecisionTrailEntry {
  id: string;
  actor: string;
  action: string;
  rationale: string;
  created_at: string;
  context_snapshot: Record<string, unknown>;
}

export function recordDecision(req: {
  actor: string;
  action: string;
  target_entity_id: string;
  rationale?: string;
}): Promise<DecisionRecord> {
  return apiFetch("/decisions", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function getDecisionTrail(entityId: string): Promise<DecisionTrailEntry[]> {
  return apiFetch(`/decisions/${entityId}/trail`);
}

// ── Governance ─────────────────────────────────────────

export interface PolicyRecord {
  id: string;
  name: string;
  policy_type: string;
  enforcement: string;
}

export function createPolicy(req: {
  name: string;
  policy_type?: string;
  enforcement?: string;
}): Promise<PolicyRecord> {
  return apiFetch("/governance/policies", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function checkPermission(req: {
  actor: string;
  action: string;
  target_entity_id: string;
}): Promise<{ allowed: boolean; reason: string }> {
  return apiFetch("/governance/check", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// ── Surveys ────────────────────────────────────────────

export interface Survey {
  id: string;
  name: string;
  status: string;
  total_outcomes: number;
}

export interface SurveyOutcome {
  id: string;
  statement: string;
  context_label: string;
  direction: string;
  importance_mean?: number;
  satisfaction_mean?: number;
  opportunity_score?: number;
}

export interface SurveyResults {
  survey_id: string;
  outcomes: Array<SurveyOutcome & {
    opportunity_mean: number;
    response_count: number;
  }>;
  total_outcomes: number;
}

export interface ScatterPoint {
  outcome_id: string;
  statement: string;
  importance: number;
  satisfaction: number;
  opportunity: number;
  response_count: number;
}

export function createSurvey(name: string, processId?: string): Promise<Survey> {
  return apiFetch("/surveys", {
    method: "POST",
    body: JSON.stringify({ name, process_id: processId || "" }),
  });
}

export function generateOutcomes(
  surveyId: string,
  jobId?: string,
  processId?: string,
): Promise<{ survey_id: string; outcomes_generated: number; outcomes: SurveyOutcome[] }> {
  return apiFetch(`/surveys/${surveyId}/generate-outcomes`, {
    method: "POST",
    body: JSON.stringify({ job_id: jobId, process_id: processId }),
  });
}

export function getSurvey(surveyId: string): Promise<Survey & { outcomes: SurveyOutcome[] }> {
  return apiFetch(`/surveys/${surveyId}`);
}

export function submitSurveyResponses(
  surveyId: string,
  responses: Array<{
    outcome_id: string;
    session_id: string;
    importance: number;
    satisfaction: number;
  }>,
): Promise<{ survey_id: string; responses_recorded: number }> {
  return apiFetch(`/surveys/${surveyId}/responses`, {
    method: "POST",
    body: JSON.stringify({ responses }),
  });
}

export function getSurveyResults(surveyId: string): Promise<SurveyResults> {
  return apiFetch(`/surveys/${surveyId}/results`);
}

export function getSurveyScatter(surveyId: string): Promise<{ points: ScatterPoint[] }> {
  return apiFetch(`/surveys/${surveyId}/scatter`);
}

export function syncSurveyImperfections(
  surveyId: string,
): Promise<{ imperfections_created: number }> {
  return apiFetch(`/surveys/${surveyId}/sync-imperfections`, { method: "POST" });
}
