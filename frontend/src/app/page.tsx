"use client";

import { useState, useEffect } from "react";
import { PanelRightClose, PanelRightOpen, RotateCcw } from "lucide-react";
import { ChatPanel } from "@/components/ChatPanel";
import { HierarchyPanel } from "@/components/HierarchyPanel";
import { useAppStore } from "@/lib/store";

export default function HomePage() {
  const { rightPanelVisible, toggleRightPanel, reset } = useAppStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

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
            title={rightPanelVisible ? "Hide hierarchy" : "Show hierarchy"}
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
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Chat */}
        <div
          className={`flex flex-col transition-all duration-300 ${
            rightPanelVisible ? "w-[55%]" : "w-full"
          }`}
        >
          <ChatPanel />
        </div>

        {/* Right: Hierarchy */}
        {rightPanelVisible && (
          <div className="w-[45%] border-l border-[var(--border)] bg-[var(--bg-secondary)]">
            <HierarchyPanel />
          </div>
        )}
      </div>
    </div>
  );
}
