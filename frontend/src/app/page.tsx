"use client";

import { useSyncExternalStore } from "react";
import { PanelRightClose, PanelRightOpen, RotateCcw } from "lucide-react";
import { ChatPanel } from "@/components/ChatPanel";
import { PhaseIndicator } from "@/components/PhaseIndicator";
import { PhaseOnePanel } from "@/components/PhaseOnePanel";
import { PhaseTwoPanel } from "@/components/PhaseTwoPanel";
import { PhaseThreePanel } from "@/components/PhaseThreePanel";
import { ContextDashboard } from "@/components/ContextDashboard";
import { useAppStore } from "@/lib/store";

export default function HomePage() {
  const { rightPanelVisible, toggleRightPanel, reset, currentPhase, activeView, setActiveView } = useAppStore();
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );

  if (!mounted) {
    return <div className="h-screen bg-[var(--bg-primary)]" />;
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Top bar */}
      <header className="flex items-center justify-between h-11 px-4 border-b border-[var(--border)] bg-[var(--bg-primary)] shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-[var(--accent-dim)] flex items-center justify-center">
            <span className="text-[var(--accent)] font-bold text-xs">J</span>
          </div>
          <span className="text-sm font-semibold text-[var(--text-primary)] tracking-tight">
            JobOS
          </span>
          <span className="text-[10px] text-[var(--text-muted)] ml-1">4.0</span>
        </div>

        {/* View toggle tabs */}
        <div className="flex items-center gap-0.5 bg-[var(--bg-tertiary)] rounded-md p-0.5">
          <button
            onClick={() => setActiveView("jtbd")}
            className={`px-2.5 py-1 rounded text-[10px] font-medium transition-colors ${
              activeView === "jtbd"
                ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
                : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            }`}
          >
            JTBD
          </button>
          <button
            onClick={() => setActiveView("context")}
            className={`px-2.5 py-1 rounded text-[10px] font-medium transition-colors ${
              activeView === "context"
                ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
                : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            }`}
          >
            Context Graph
          </button>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={reset}
            className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] transition-colors"
            title="New session"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={toggleRightPanel}
            className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] transition-colors"
            title={rightPanelVisible ? "Hide panel" : "Show panel"}
          >
            {rightPanelVisible ? (
              <PanelRightClose className="w-3.5 h-3.5" />
            ) : (
              <PanelRightOpen className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </header>

      {/* Main content */}
      {activeView === "context" ? (
        <div className="flex-1 overflow-hidden">
          <ContextDashboard />
        </div>
      ) : (
        <div className="flex flex-1 overflow-hidden">
          {/* Left: Chat */}
          <div
            className={`flex flex-col transition-all duration-300 ${
              rightPanelVisible ? "w-[25%]" : "w-full"
            }`}
          >
            <ChatPanel />
          </div>

          {/* Right: Phase panel */}
          {rightPanelVisible && (
            <div className="w-[75%] border-l border-[var(--border)] bg-[var(--bg-secondary)] flex flex-col">
              <PhaseIndicator />
              <div className="flex-1 overflow-hidden">
                {currentPhase === 1 && <PhaseOnePanel />}
                {currentPhase === 2 && <PhaseTwoPanel />}
                {currentPhase === 3 && <PhaseThreePanel />}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
