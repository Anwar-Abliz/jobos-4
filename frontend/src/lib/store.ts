import { create } from "zustand";
import type {
  ChatResponse,
  HierarchyResponse,
  HierarchyJob,
  TreeNode,
  BaselineSummary,
  SwitchEvent,
  PhaseEvaluation,
  PreliminaryRecommendation,
  SAPProcess,
  FreshnessStatus,
  Survey,
  SurveyOutcome,
  ScatterPoint,
  DecisionTrailEntry,
} from "./api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  intent?: string;
  entities_created?: Array<{ id: string; name: string; type: string }>;
}

export interface TargetJob {
  id: string;
  statement: string;
  tier: string;
  category: string;
  metricsHint: string[];
  executorType: "HUMAN" | "AI";
}

export interface MetricDefinition {
  statement: string;
  target: string;
  switchThreshold: string;
}

export interface Outcomes {
  experienceMarkers: {
    feel_markers: string[];
    to_be_markers: string[];
  };
  metrics: MetricDefinition[];
  confirmedAt: number | null;
}

interface AppState {
  // Phase
  currentPhase: 1 | 2 | 3;

  // Chat
  messages: ChatMessage[];
  isLoading: boolean;
  sessionId: string | null;

  // Phase 1 — Identify
  hierarchy: HierarchyResponse | null;
  hierarchyFunctionalSpine: TreeNode[] | null;
  hierarchyExperienceDimension: TreeNode[] | null;
  isGeneratingHierarchy: boolean;
  selectedJobId: string | null;
  visualizationMode: "tree" | "graph";
  targetJob: TargetJob | null;

  // Phase 2 — Define
  dimensionView: "A" | "B";
  outcomes: Outcomes;

  // Phase 3 — Decide
  preliminaryResult: PreliminaryRecommendation | null;
  phaseEvaluation: PhaseEvaluation | null;
  switchEvents: SwitchEvent[];
  baselineSummary: BaselineSummary | null;

  // Panel
  rightPanelVisible: boolean;

  // SAP Context Graph
  sapProcesses: SAPProcess[];
  activeSurvey: (Survey & { outcomes: SurveyOutcome[] }) | null;
  surveyScatter: ScatterPoint[];
  decisionTrail: DecisionTrailEntry[];
  contextFreshness: Record<string, FreshnessStatus>;

  // Actions — Chat
  addUserMessage: (content: string) => void;
  addAssistantMessage: (response: ChatResponse) => void;
  setLoading: (loading: boolean) => void;
  setSessionId: (id: string) => void;

  // Actions — Phase 1
  setHierarchy: (
    h: HierarchyResponse,
    functionalSpine: TreeNode[],
    experienceDimension: TreeNode[],
  ) => void;
  setGeneratingHierarchy: (loading: boolean) => void;
  setSelectedJobId: (id: string | null) => void;
  setVisualizationMode: (mode: "tree" | "graph") => void;
  updateHierarchyJob: (jobId: string, updates: Partial<HierarchyJob>) => void;

  // Actions — Phase transitions
  lockTargetJob: (job: TargetJob) => void;
  unlockTargetJob: () => void;
  confirmOutcomes: () => void;

  // Actions — Phase 2
  setDimensionView: (view: "A" | "B") => void;
  setOutcomes: (outcomes: Partial<Outcomes>) => void;

  // Actions — Phase 3
  setPreliminaryResult: (result: PreliminaryRecommendation | null) => void;
  setPhaseEvaluation: (evaluation: PhaseEvaluation | null) => void;
  setSwitchEvents: (events: SwitchEvent[]) => void;
  setBaselineSummary: (summary: BaselineSummary | null) => void;

  // Actions — Panel
  toggleRightPanel: () => void;
  reset: () => void;

  // Actions — SAP Context Graph
  setSAPProcesses: (processes: SAPProcess[]) => void;
  setActiveSurvey: (survey: (Survey & { outcomes: SurveyOutcome[] }) | null) => void;
  setSurveyScatter: (points: ScatterPoint[]) => void;
  setDecisionTrail: (trail: DecisionTrailEntry[]) => void;
  setContextFreshness: (entityId: string, freshness: FreshnessStatus) => void;
}

const DEFAULT_OUTCOMES: Outcomes = {
  experienceMarkers: { feel_markers: [], to_be_markers: [] },
  metrics: [],
  confirmedAt: null,
};

export const useAppStore = create<AppState>((set) => ({
  currentPhase: 1,

  messages: [],
  isLoading: false,
  sessionId: null,

  hierarchy: null,
  hierarchyFunctionalSpine: null,
  hierarchyExperienceDimension: null,
  isGeneratingHierarchy: false,
  selectedJobId: null,
  visualizationMode: "tree",
  targetJob: null,

  dimensionView: "B",
  outcomes: { ...DEFAULT_OUTCOMES },

  preliminaryResult: null,
  phaseEvaluation: null,
  switchEvents: [],
  baselineSummary: null,

  rightPanelVisible: true,

  sapProcesses: [],
  activeSurvey: null,
  surveyScatter: [],
  decisionTrail: [],
  contextFreshness: {},

  // Chat
  addUserMessage: (content) =>
    set((s) => ({
      messages: [...s.messages, { role: "user", content, timestamp: Date.now() }],
    })),

  addAssistantMessage: (response) =>
    set((s) => ({
      messages: [
        ...s.messages,
        {
          role: "assistant",
          content: response.assistant_message,
          timestamp: Date.now(),
          intent: response.intent,
          entities_created: response.entities_created,
        },
      ],
      sessionId: response.session_id,
    })),

  setLoading: (loading) => set({ isLoading: loading }),
  setSessionId: (id) => set({ sessionId: id }),

  // Phase 1
  setHierarchy: (h, functionalSpine, experienceDimension) =>
    set({
      hierarchy: h,
      hierarchyFunctionalSpine: functionalSpine,
      hierarchyExperienceDimension: experienceDimension,
      rightPanelVisible: true,
    }),
  setGeneratingHierarchy: (loading) => set({ isGeneratingHierarchy: loading }),
  setSelectedJobId: (id) => set({ selectedJobId: id }),
  setVisualizationMode: (mode) => set({ visualizationMode: mode }),
  updateHierarchyJob: (jobId, updates) =>
    set((s) => {
      if (!s.hierarchy) return {};
      const jobs = s.hierarchy.jobs.map((j) =>
        j.id === jobId ? { ...j, ...updates } : j,
      );
      return { hierarchy: { ...s.hierarchy, jobs } };
    }),

  // Phase transitions
  lockTargetJob: (job) =>
    set({
      targetJob: job,
      currentPhase: 2,
      selectedJobId: job.id,
    }),

  unlockTargetJob: () =>
    set({
      targetJob: null,
      currentPhase: 1,
      outcomes: { ...DEFAULT_OUTCOMES },
      preliminaryResult: null,
      phaseEvaluation: null,
      switchEvents: [],
      baselineSummary: null,
    }),

  confirmOutcomes: () =>
    set((s) => ({
      currentPhase: 3,
      outcomes: { ...s.outcomes, confirmedAt: Date.now() },
    })),

  // Phase 2
  setDimensionView: (view) => set({ dimensionView: view }),
  setOutcomes: (partial) =>
    set((s) => ({ outcomes: { ...s.outcomes, ...partial } })),

  // Phase 3
  setPreliminaryResult: (result) => set({ preliminaryResult: result }),
  setPhaseEvaluation: (evaluation) => set({ phaseEvaluation: evaluation }),
  setSwitchEvents: (events) => set({ switchEvents: events }),
  setBaselineSummary: (summary) => set({ baselineSummary: summary }),

  // Panel
  toggleRightPanel: () => set((s) => ({ rightPanelVisible: !s.rightPanelVisible })),

  // SAP Context Graph
  setSAPProcesses: (processes) => set({ sapProcesses: processes }),
  setActiveSurvey: (survey) => set({ activeSurvey: survey }),
  setSurveyScatter: (points) => set({ surveyScatter: points }),
  setDecisionTrail: (trail) => set({ decisionTrail: trail }),
  setContextFreshness: (entityId, freshness) =>
    set((s) => ({
      contextFreshness: { ...s.contextFreshness, [entityId]: freshness },
    })),

  reset: () =>
    set({
      currentPhase: 1,
      messages: [],
      isLoading: false,
      sessionId: null,
      hierarchy: null,
      hierarchyFunctionalSpine: null,
      hierarchyExperienceDimension: null,
      isGeneratingHierarchy: false,
      selectedJobId: null,
      visualizationMode: "tree",
      targetJob: null,
      dimensionView: "B",
      outcomes: { ...DEFAULT_OUTCOMES },
      preliminaryResult: null,
      phaseEvaluation: null,
      switchEvents: [],
      baselineSummary: null,
      sapProcesses: [],
      activeSurvey: null,
      surveyScatter: [],
      decisionTrail: [],
      contextFreshness: {},
    }),
}));
