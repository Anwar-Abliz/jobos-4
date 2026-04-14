"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { Send } from "lucide-react";
import { useAppStore, type ChatMessage } from "@/lib/store";
import { sendChat } from "@/lib/api";
import { TargetJobBadge } from "./TargetJobBadge";

export function ChatPanel() {
  const {
    messages,
    isLoading,
    sessionId,
    targetJob,
    currentPhase,
    addUserMessage,
    addAssistantMessage,
    setLoading,
  } = useAppStore();

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    setInput("");
    addUserMessage(text);
    setLoading(true);

    try {
      const response = await sendChat({
        message: text,
        session_id: sessionId ?? undefined,
        job_id: targetJob?.id ?? undefined,
      });
      addAssistantMessage(response);
    } catch (err) {
      addAssistantMessage({
        session_id: sessionId ?? "",
        assistant_message: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
        intent: "error",
        entities_created: [],
        entities_updated: [],
        imperfections: [],
        vfe_current: null,
        top_blocker: null,
      });
    } finally {
      setLoading(false);
    }
  }, [input, isLoading, sessionId, targetJob, addUserMessage, addAssistantMessage, setLoading]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-3 py-4">
        {messages.length === 0 ? (
          <WelcomeScreen phase={currentPhase} targetJobStatement={targetJob?.statement} />
        ) : (
          <div className="space-y-3">
            {messages.map((msg, i) => (
              <MessageBubble key={`${msg.timestamp}-${i}`} message={msg} />
            ))}
            {isLoading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Target job badge above input */}
      {targetJob && (
        <div className="px-3 pb-1">
          <TargetJobBadge readOnly />
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-[var(--border)] px-3 py-2">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={getPlaceholder(currentPhase)}
            className="w-full resize-none rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-2 pr-10 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
            rows={1}
            disabled={isLoading}
            style={{ minHeight: "36px", maxHeight: "100px" }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = Math.min(target.scrollHeight, 100) + "px";
            }}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md text-[var(--text-muted)] hover:text-[var(--accent)] hover:bg-[var(--accent-dim)] disabled:opacity-30 disabled:hover:bg-transparent transition-all"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

function getPlaceholder(phase: 1 | 2 | 3): string {
  switch (phase) {
    case 1:
      return "Describe a goal or task...";
    case 2:
      return "Define metrics or outcomes...";
    case 3:
      return "Ask about the recommendation...";
  }
}

const PHASE_CHIPS: Record<number, string[]> = {
  1: [
    "Reduce churn from 8% to 3%",
    "Onboarding is broken",
    "Improve translation pipeline",
  ],
  2: [
    "Time below 5 minutes",
    "Satisfaction above 4.5",
    "Error rate below 1%",
  ],
  3: [
    "Risks of switching?",
    "Human vs AI comparison",
    "What data would help?",
  ],
};

function WelcomeScreen({
  phase,
  targetJobStatement,
}: {
  phase: 1 | 2 | 3;
  targetJobStatement?: string;
}) {
  const chips = PHASE_CHIPS[phase] || PHASE_CHIPS[1];

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-3">
      <div className="mb-4">
        <div className="w-8 h-8 rounded-lg bg-[var(--accent-dim)] flex items-center justify-center mb-3 mx-auto">
          <span className="text-[var(--accent)] font-bold text-sm">J</span>
        </div>
        <h1 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
          JobOS
        </h1>
        <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
          {phase === 1 && "Describe a goal. I'll structure it into measurable jobs."}
          {phase === 2 &&
            `Define success for "${targetJobStatement}".`}
          {phase === 3 && "Ask about the recommendation."}
        </p>
      </div>
      <div className="flex flex-col gap-1.5 w-full max-w-[200px]">
        {chips.map((chip) => (
          <button
            key={chip}
            onClick={() => {
              useAppStore.getState().addUserMessage(chip);
              useAppStore.getState().setLoading(true);
              const state = useAppStore.getState();
              sendChat({
                message: chip,
                session_id: state.sessionId ?? undefined,
                job_id: state.targetJob?.id ?? undefined,
              })
                .then((r) => {
                  useAppStore.getState().addAssistantMessage(r);
                })
                .catch((err) => {
                  useAppStore.getState().addAssistantMessage({
                    session_id: state.sessionId ?? "",
                    assistant_message: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
                    intent: "error",
                    entities_created: [],
                    entities_updated: [],
                    imperfections: [],
                    vfe_current: null,
                    top_blocker: null,
                  });
                })
                .finally(() => {
                  useAppStore.getState().setLoading(false);
                });
            }}
            className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-2.5 py-1.5 text-[10px] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors text-left"
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-2 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="w-5 h-5 rounded-md bg-[var(--accent-dim)] flex items-center justify-center shrink-0 mt-0.5">
          <span className="text-[var(--accent)] text-[9px] font-bold">J</span>
        </div>
      )}
      <div
        className={`max-w-full rounded-xl px-3 py-2 text-xs leading-relaxed ${
          isUser
            ? "bg-[var(--user-bubble)] text-[var(--text-primary)]"
            : "text-[var(--text-primary)]"
        }`}
      >
        <div className="whitespace-pre-wrap break-words">{message.content}</div>
        {!isUser && message.entities_created && message.entities_created.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {message.entities_created.map((e) => (
              <span
                key={e.id}
                className="inline-flex items-center rounded-full bg-[var(--accent-dim)] px-1.5 py-0.5 text-[9px] text-[var(--accent)]"
              >
                {e.type}: {e.name}
              </span>
            ))}
          </div>
        )}
      </div>
      {isUser && (
        <div className="w-5 h-5 rounded-md bg-[var(--bg-tertiary)] flex items-center justify-center shrink-0 mt-0.5">
          <span className="text-[var(--text-muted)] text-[9px]">U</span>
        </div>
      )}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-2">
      <div className="w-5 h-5 rounded-md bg-[var(--accent-dim)] flex items-center justify-center shrink-0">
        <span className="text-[var(--accent)] text-[9px] font-bold">J</span>
      </div>
      <div className="flex items-center gap-1 px-3 py-2">
        <span className="w-1 h-1 rounded-full bg-[var(--text-muted)] animate-bounce" style={{ animationDelay: "0ms" }} />
        <span className="w-1 h-1 rounded-full bg-[var(--text-muted)] animate-bounce" style={{ animationDelay: "150ms" }} />
        <span className="w-1 h-1 rounded-full bg-[var(--text-muted)] animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
    </div>
  );
}
