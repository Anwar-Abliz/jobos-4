"use client";

import { useState } from "react";
import { RefreshCw, Database } from "lucide-react";
import { SAPProcessView } from "./SAPProcessView";
import { ContextGraphPanel } from "./ContextGraphPanel";
import { DecisionTrail } from "./DecisionTrail";
import { GovernanceBadge } from "./GovernanceBadge";
import { ContextFreshness } from "./ContextFreshness";
import { SurveyPanel } from "./SurveyPanel";
import { OpportunityScatter } from "./OpportunityScatter";
import * as api from "@/lib/api";
import { useAppStore } from "@/lib/store";

// ── Demo data ────────────────────────────────────────────

interface DemoProcessStep {
  id: string;
  label: string;
  description?: string;
  status: "pending" | "active" | "completed" | "error";
  context?: Record<string, string>;
}

const DEMO_PROCESS_STEPS: DemoProcessStep[] = [
  { id: "s1", label: "Sales Order Create", description: "VA01 — create sales order", status: "completed" as const, context: { org: "1000", channel: "10" } },
  { id: "s2", label: "Credit Check", description: "Automated credit limit validation", status: "completed" as const, context: { limit: "50,000 EUR" } },
  { id: "s3", label: "Delivery Create", description: "VL01N — outbound delivery", status: "active" as const },
  { id: "s4", label: "Pick & Pack", description: "Warehouse task assignment", status: "pending" as const },
  { id: "s5", label: "Goods Issue", description: "Post goods issue to inventory", status: "pending" as const },
  { id: "s6", label: "Invoice", description: "VF01 — billing document", status: "pending" as const },
  { id: "s7", label: "Payment Receipt", description: "FI posting — incoming payment", status: "pending" as const },
  { id: "s8", label: "Dunning", description: "FI — automated dunning run", status: "error" as const, context: { error: "Config missing for company code 2000" } },
];

const DEMO_GRAPH_NODES = [
  { id: "n1", label: "Process Order Fulfillment", type: "job" as const, vfe: 0.42 },
  { id: "n2", label: "SAP SD Module", type: "executor" as const },
  { id: "n3", label: "Automated Credit Check", type: "capability" as const, vfe: 0.15 },
  { id: "n4", label: "Manual Dunning Steps", type: "imperfection" as const, vfe: 0.78 },
  { id: "n5", label: "DACH Region Q2", type: "context" as const },
  { id: "n6", label: "Payment Delay Report", type: "evidence" as const, vfe: 0.61 },
  { id: "n7", label: "Minimize Payment Delays", type: "job" as const, vfe: 0.55 },
  { id: "n8", label: "AI Collections Agent", type: "executor" as const },
];

const DEMO_GRAPH_EDGES = [
  { source: "n1", target: "n2", relationship: "HIRES" },
  { source: "n2", target: "n3", relationship: "QUALIFIES" },
  { source: "n1", target: "n4", relationship: "MINIMIZES" },
  { source: "n5", target: "n1", relationship: "OCCURS_IN" },
  { source: "n6", target: "n4", relationship: "SUPPORTS" },
  { source: "n7", target: "n8", relationship: "HIRES" },
  { source: "n7", target: "n1", relationship: "PART_OF" },
];

const DEMO_FRESHNESS = [
  { entityId: "f1", entityLabel: "SAP SD — Order Data", freshness: "live" as const, lastUpdated: new Date(Date.now() - 120_000).toISOString(), sourceLabel: "RFC" },
  { entityId: "f2", entityLabel: "Credit Limit — Company 1000", freshness: "snapshot" as const, lastUpdated: new Date(Date.now() - 3_600_000).toISOString(), sourceLabel: "S/4" },
  { entityId: "f3", entityLabel: "Dunning Config — CC 2000", freshness: "stale" as const, lastUpdated: new Date(Date.now() - 172_800_000).toISOString(), sourceLabel: "IMG" },
];

const DEMO_GOVERNANCE_CHECKS = [
  { policyName: "Data Retention Policy", status: "compliant" as const, detail: "All audit logs retained for 10 years per SOX requirement." },
  { policyName: "GDPR — Customer PII", status: "warning" as const, detail: "Customer email exposed in dunning correspondence — review anonymization." },
  { policyName: "Segregation of Duties", status: "compliant" as const, detail: "Order creation and approval separated." },
  { policyName: "Change Management", status: "violation" as const, detail: "Dunning config modified without change request in Solution Manager." },
];

const DEMO_DECISIONS = [
  {
    id: "d1",
    timestamp: new Date(Date.now() - 86_400_000).toISOString(),
    action: "hire" as const,
    summary: "Hired SAP SD Module to process order fulfillment for DACH region.",
    reason: "Lowest EFE among candidates; existing integration with FI module.",
    entityId: "n2",
    entityLabel: "SAP SD Module",
    contextSnapshot: [
      { key: "Region", value: "DACH" },
      { key: "Volume", value: "1,200 orders/month" },
    ],
    vfeBefore: 0.65,
    vfeAfter: 0.42,
  },
  {
    id: "d2",
    timestamp: new Date(Date.now() - 43_200_000).toISOString(),
    action: "switch" as const,
    summary: "Switched dunning execution from manual process to AI Collections Agent.",
    reason: "Manual dunning VFE exceeded switch threshold (0.75). AI agent projected to reduce VFE by 40%.",
    entityId: "n8",
    entityLabel: "AI Collections Agent",
    contextSnapshot: [
      { key: "Trigger", value: "VFE breach > 0.75" },
      { key: "Metric", value: "Days Sales Outstanding" },
    ],
    vfeBefore: 0.78,
    vfeAfter: 0.47,
  },
  {
    id: "d3",
    timestamp: new Date(Date.now() - 3_600_000).toISOString(),
    action: "hold" as const,
    summary: "Holding credit check automation — awaiting Q2 threshold recalibration.",
    entityLabel: "Automated Credit Check",
    contextSnapshot: [
      { key: "Status", value: "Pending finance review" },
    ],
  },
];

const DEMO_SURVEY_OUTCOMES = [
  { id: "o1", statement: "Minimize the time it takes to create a sales order", tier: "T3" },
  { id: "o2", statement: "Minimize the likelihood of credit check false positives", tier: "T2" },
  { id: "o3", statement: "Minimize the time to resolve dunning exceptions", tier: "T3" },
];

const DEMO_SURVEY_RESPONSES = [
  { outcomeId: "o1", importance: 4 as const, satisfaction: 3 as const },
  { outcomeId: "o2", importance: 5 as const, satisfaction: 2 as const },
  { outcomeId: "o3", importance: 5 as const, satisfaction: 1 as const },
];

const DEMO_SCATTER_POINTS = [
  { id: "p1", label: "Minimize order creation time", importance: 7, satisfaction: 6, frequency: 80, segment: "Operations" },
  { id: "p2", label: "Minimize credit check false positives", importance: 9, satisfaction: 3, frequency: 45, segment: "Finance" },
  { id: "p3", label: "Minimize dunning exception resolution time", importance: 9.5, satisfaction: 2, frequency: 60, segment: "Finance" },
  { id: "p4", label: "Minimize delivery scheduling errors", importance: 6, satisfaction: 7, frequency: 30, segment: "Logistics" },
  { id: "p5", label: "Minimize invoice discrepancies", importance: 8, satisfaction: 5, frequency: 55, segment: "Finance" },
  { id: "p6", label: "Minimize manual data entry in order capture", importance: 8.5, satisfaction: 4, frequency: 70, segment: "Operations" },
  { id: "p7", label: "Minimize payment allocation errors", importance: 7.5, satisfaction: 3.5, frequency: 40, segment: "Finance" },
  { id: "p8", label: "Minimize warehouse pick-path inefficiency", importance: 5, satisfaction: 6.5, frequency: 25, segment: "Logistics" },
];

// ── Component ────────────────────────────────────────────

export function ContextDashboard() {
  const [loadingApi, setLoadingApi] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const { setSAPProcesses, setDecisionTrail, setSurveyScatter } = useAppStore();

  async function handleLoadFromApi() {
    setLoadingApi(true);
    setApiError(null);
    try {
      const [processes, trail] = await Promise.allSettled([
        api.listSAPProcesses(),
        api.getDecisionTrail("root"),
      ]);
      if (processes.status === "fulfilled") setSAPProcesses(processes.value);
      if (trail.status === "fulfilled") setDecisionTrail(trail.value);

      // Try scatter from first available survey
      try {
        const surveys = await api.createSurvey("context-graph-demo");
        if (surveys?.id) {
          const scatter = await api.getSurveyScatter(surveys.id);
          setSurveyScatter(scatter.points);
        }
      } catch {
        // survey endpoints may not exist yet
      }
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Failed to load from API");
    } finally {
      setLoadingApi(false);
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Dashboard header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--border)] bg-[var(--bg-primary)] shrink-0">
        <div className="flex items-center gap-2">
          <Database className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span className="text-xs font-semibold text-[var(--text-primary)]">
            Context Graph Dashboard
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">Demo data</span>
        </div>
        <button
          onClick={handleLoadFromApi}
          disabled={loadingApi}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-medium
            bg-[var(--bg-tertiary)] text-[var(--text-secondary)]
            hover:bg-[var(--accent)]/10 hover:text-[var(--accent)]
            disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-3 h-3 ${loadingApi ? "animate-spin" : ""}`} />
          Load from API
        </button>
      </div>

      {apiError && (
        <div className="px-4 py-1.5 bg-red-500/10 border-b border-red-500/20">
          <p className="text-[10px] text-red-400">{apiError}</p>
        </div>
      )}

      {/* Scrollable dashboard body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* Row 1: SAP Process + Freshness */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div className="xl:col-span-2">
            <SAPProcessView
              title="Order to Cash (O2C)"
              steps={DEMO_PROCESS_STEPS}
              activeStepId="s3"
            />
          </div>
          <div>
            <ContextFreshness entries={DEMO_FRESHNESS} />
          </div>
        </div>

        {/* Row 2: Context Graph + Governance */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div className="xl:col-span-2">
            <ContextGraphPanel
              nodes={DEMO_GRAPH_NODES}
              edges={DEMO_GRAPH_EDGES}
              focusNodeId="n4"
            />
          </div>
          <div className="space-y-4">
            <GovernanceBadge
              entityId="n1"
              entityLabel="Order Fulfillment Process"
              overallStatus="warning"
              checks={DEMO_GOVERNANCE_CHECKS}
            />
          </div>
        </div>

        {/* Row 3: Decision Trail */}
        <DecisionTrail decisions={DEMO_DECISIONS} />

        {/* Row 4: Survey + Scatter */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <SurveyPanel
            title="O2C Outcome Survey"
            description="Rate each outcome statement on importance and current satisfaction (1-5 scale)."
            outcomes={DEMO_SURVEY_OUTCOMES}
            responses={DEMO_SURVEY_RESPONSES}
            readOnly
          />
          <OpportunityScatter
            points={DEMO_SCATTER_POINTS}
            highlightIds={["p3", "p2"]}
            showThresholdLine
            importanceThreshold={7}
          />
        </div>
      </div>
    </div>
  );
}
