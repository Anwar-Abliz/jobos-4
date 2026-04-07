"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { Send } from "lucide-react";
import { useAppStore, type ChatMessage } from "@/lib/store";
import { sendChat } from "@/lib/api";

export function ChatPanel() {
  const {
    messages,
    isLoading,
    sessionId,
    activeJobId,
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
        job_id: activeJobId ?? undefined,
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
  }, [input, isLoading, sessionId, activeJobId, addUserMessage, addAssistantMessage, setLoading]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <WelcomeScreen />
        ) : (
          <div className="max-w-2xl mx-auto space-y-4">
            {messages.map((msg, i) => (
              <MessageBubble key={`${msg.timestamp}-${i}`} message={msg} />
            ))}
            {isLoading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-[var(--border)] px-4 py-3">
        <div className="max-w-2xl mx-auto relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe a goal, report a metric, or ask a question..."
            className="w-full resize-none rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-3 pr-12 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
            rows={1}
            disabled={isLoading}
            style={{ minHeight: "44px", maxHeight: "120px" }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = Math.min(target.scrollHeight, 120) + "px";
            }}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--accent)] hover:bg-[var(--accent-dim)] disabled:opacity-30 disabled:hover:bg-transparent transition-all"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function WelcomeScreen() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-6">
      <div className="mb-6">
        <div className="w-10 h-10 rounded-xl bg-[var(--accent-dim)] flex items-center justify-center mb-4 mx-auto">
          <span className="text-[var(--accent)] font-bold text-lg">J</span>
        </div>
        <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
          JobOS
        </h1>
        <p className="text-sm text-[var(--text-secondary)] max-w-md">
          Describe a goal you are working toward. I will help you structure it
          into measurable jobs, identify blockers, and track progress.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center max-w-lg">
        {[
          "Reduce monthly churn from 8% to 3%",
          "Launch a new product in Q3",
          "Improve onboarding completion rate",
        ].map((chip) => (
          <button
            key={chip}
            onClick={() => {
              useAppStore.getState().addUserMessage(chip);
              sendChat({ message: chip }).then((r) => {
                useAppStore.getState().addAssistantMessage(r);
              });
            }}
            className="rounded-full border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors"
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
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-lg bg-[var(--accent-dim)] flex items-center justify-center shrink-0 mt-0.5">
          <span className="text-[var(--accent)] text-xs font-bold">J</span>
        </div>
      )}
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "bg-[var(--user-bubble)] text-[var(--text-primary)]"
            : "text-[var(--text-primary)]"
        }`}
      >
        <div className="whitespace-pre-wrap">{message.content}</div>
        {!isUser && message.entities_created && message.entities_created.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.entities_created.map((e) => (
              <span
                key={e.id}
                className="inline-flex items-center rounded-full bg-[var(--accent-dim)] px-2 py-0.5 text-[10px] text-[var(--accent)]"
              >
                {e.type}: {e.name}
              </span>
            ))}
          </div>
        )}
      </div>
      {isUser && (
        <div className="w-7 h-7 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center shrink-0 mt-0.5">
          <span className="text-[var(--text-muted)] text-xs">U</span>
        </div>
      )}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-lg bg-[var(--accent-dim)] flex items-center justify-center shrink-0">
        <span className="text-[var(--accent)] text-xs font-bold">J</span>
      </div>
      <div className="flex items-center gap-1 px-4 py-3">
        <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-muted)] animate-bounce" style={{ animationDelay: "0ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-muted)] animate-bounce" style={{ animationDelay: "150ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-muted)] animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
    </div>
  );
}
