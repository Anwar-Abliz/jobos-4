/**
 * JobOS 4.0 — Global State Store (Zustand)
 */
import { create } from "zustand";
import type { ChatResponse, HierarchyResponse, TreeNode } from "./api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  intent?: string;
  entities_created?: Array<{ id: string; name: string; type: string }>;
}

interface AppState {
  // Chat
  messages: ChatMessage[];
  isLoading: boolean;
  sessionId: string | null;
  activeJobId: string | null;

  // Hierarchy
  hierarchy: HierarchyResponse | null;
  hierarchyTree: TreeNode[] | null;
  isGeneratingHierarchy: boolean;

  // Panel
  rightPanelVisible: boolean;

  // Actions
  addUserMessage: (content: string) => void;
  addAssistantMessage: (response: ChatResponse) => void;
  setLoading: (loading: boolean) => void;
  setSessionId: (id: string) => void;
  setActiveJobId: (id: string | null) => void;
  setHierarchy: (h: HierarchyResponse, tree: TreeNode[]) => void;
  setGeneratingHierarchy: (loading: boolean) => void;
  toggleRightPanel: () => void;
  reset: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  messages: [],
  isLoading: false,
  sessionId: null,
  activeJobId: null,
  hierarchy: null,
  hierarchyTree: null,
  isGeneratingHierarchy: false,
  rightPanelVisible: true,

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
      activeJobId:
        response.entities_created?.find((e) => e.type === "job")?.id ?? s.activeJobId,
    })),

  setLoading: (loading) => set({ isLoading: loading }),
  setSessionId: (id) => set({ sessionId: id }),
  setActiveJobId: (id) => set({ activeJobId: id }),
  setHierarchy: (h, tree) => set({ hierarchy: h, hierarchyTree: tree, rightPanelVisible: true }),
  setGeneratingHierarchy: (loading) => set({ isGeneratingHierarchy: loading }),
  toggleRightPanel: () => set((s) => ({ rightPanelVisible: !s.rightPanelVisible })),
  reset: () =>
    set({
      messages: [],
      isLoading: false,
      sessionId: null,
      activeJobId: null,
      hierarchy: null,
      hierarchyTree: null,
      isGeneratingHierarchy: false,
    }),
}));
