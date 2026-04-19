"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Loader2,
  Brain,
  Cpu,
  ChevronDown,
  ChevronUp,
  ArrowUpRight,
  ArrowDownRight,
  Info,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { getPreliminaryRecommendation, type PreliminaryRecommendation } from "@/lib/api";
import { TargetJobBadge } from "./TargetJobBadge";
import { GoNoGoWidget } from "./GoNoGoWidget";
import { SwitchTimeline } from "./SwitchTimeline";
import { BaselineComparison } from "./BaselineComparison";

const RECOMMENDATION_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  switch_to_ai: {
    bg: "bg-blue-500/10 border-blue-500/30",
    text: "text-blue-400",
    label: "Switch to AI",
  },
  keep_human: {
    bg: "bg-green-500/10 border-green-500/30",
    text: "text-green-400",
    label: "Keep Human",
  },
  needs_more_data: {
    bg: "bg-amber-500/10 border-amber-500/30",
    text: "text-amber-400",
    label: "Needs More Data",
  },
};

const EVALUATION_METHOD_LABELS: Record<string, string> = {
  llm_analysis: "Analyzed by LLM",
  heuristic_template: "Heuristic scoring (LLM disabled)",
};

export function PhaseThreePanel() {
  const {
    targetJob,
    outcomes,
    preliminaryResult,
    phaseEvaluation,
    switchEvents,
    baselineSummary,
    setPreliminaryResult,
  } = useAppStore();

  const [isLoadingPreliminary, setIsLoadingPreliminary] = useState(false);
  const [preliminaryError, setPreliminaryError] = useState<string | null>(null);
  const fetchedRef = useRef(false);

  const fetchRecommendation = useCallback(async () => {
    if (!targetJob || preliminaryResult) return;
    setIsLoadingPreliminary(true);
    setPreliminaryError(null);
    try {
      const result = await getPreliminaryRecommendation(targetJob.id, {
        experience_markers: outcomes.experienceMarkers,
        metrics: outcomes.metrics.map((m) => ({
          statement: m.statement,
          target: m.target,
          switch_threshold: m.switchThreshold,
        })),
      });
      setPreliminaryResult(result);
    } catch (err) {
      setPreliminaryError(
        err instanceof Error ? err.message : "Failed to get recommendation",
      );
    } finally {
      setIsLoadingPreliminary(false);
    }
  }, [targetJob, outcomes, preliminaryResult, setPreliminaryResult]);

  // Fetch preliminary recommendation on mount
  useEffect(() => {
    if (!fetchedRef.current && targetJob && !preliminaryResult) {
      fetchedRef.current = true;
      fetchRecommendation();
    }
  }, [fetchRecommendation, targetJob, preliminaryResult]);

  if (!targetJob) return null;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border)] space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Decision
        </h2>
        <TargetJobBadge />
        <p className="text-[10px] text-[var(--text-muted)] leading-relaxed">
          {targetJob.executorType === "AI"
            ? "Evaluating AI performance (no experience dimension)"
            : "Evaluating human execution (experience + metrics)"}
        </p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {/* LLM Preliminary Recommendation */}
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Brain className="w-3.5 h-3.5 text-[var(--accent)]" />
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              LLM Preliminary
            </span>
          </div>

          {isLoadingPreliminary ? (
            <div className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] p-4">
              <Loader2 className="w-4 h-4 animate-spin text-[var(--accent)]" />
              <span className="text-xs text-[var(--text-muted)]">Analyzing job structure...</span>
            </div>
          ) : preliminaryError ? (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3">
              <p className="text-xs text-red-400">{preliminaryError}</p>
            </div>
          ) : preliminaryResult ? (
            <PreliminaryCard result={preliminaryResult} />
          ) : null}
        </div>

        {/* Engine Verdict */}
        {phaseEvaluation && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Cpu className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
              <span className="text-xs font-semibold text-[var(--text-secondary)]">
                Engine Verdict
              </span>
            </div>
            <GoNoGoWidget evaluation={phaseEvaluation} />
          </div>
        )}

        {/* Switch Timeline */}
        {switchEvents.length > 0 && <SwitchTimeline events={switchEvents} />}

        {/* Baseline Comparison */}
        {baselineSummary && <BaselineComparison summary={baselineSummary} />}
      </div>
    </div>
  );
}

function PreliminaryCard({ result }: { result: PreliminaryRecommendation }) {
  const [showExplanation, setShowExplanation] = useState(false);

  const style = RECOMMENDATION_STYLES[result.recommendation] || RECOMMENDATION_STYLES.needs_more_data;
  const confidencePct = Math.round(result.confidence * 100);

  return (
    <div className={`rounded-lg border ${style.bg} p-4 space-y-3`}>
      {/* Recommendation + confidence */}
      <div className="flex items-center justify-between">
        <span className={`text-sm font-bold ${style.text}`}>{style.label}</span>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[var(--text-muted)]">{confidencePct}%</span>
        </div>
      </div>

      {/* Confidence meter */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-[9px] uppercase text-[var(--text-muted)]">Confidence</span>
          <span className="text-[10px] text-[var(--text-muted)]">{confidencePct}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-[var(--bg-tertiary)] overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${confidencePct}%`,
              backgroundColor: confidencePct >= 70
                ? "#10b981"
                : confidencePct >= 40
                  ? "#f59e0b"
                  : "#ef4444",
            }}
          />
        </div>
      </div>

      {/* Reasoning */}
      <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
        {result.reasoning}
      </p>

      {/* Factors */}
      {result.factors.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase text-[var(--text-muted)]">Factors</p>
          {result.factors.map((f, i) => (
            <div key={i} className="space-y-0.5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  {f.impact === "positive" ? (
                    <ArrowUpRight className="w-3 h-3 text-green-400 shrink-0" />
                  ) : (
                    <ArrowDownRight className="w-3 h-3 text-red-400 shrink-0" />
                  )}
                  <span className="text-[11px] text-[var(--text-primary)]">{f.factor}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`text-[10px] font-medium ${
                      f.impact === "positive" ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {f.impact === "positive" ? "Favors switch" : "Favors human"}
                  </span>
                  <span className="text-[10px] text-[var(--text-muted)]">
                    {Math.round(f.weight * 100)}%
                  </span>
                </div>
              </div>
              {f.explanation && (
                <p className="text-[10px] text-[var(--text-muted)] leading-relaxed pl-[18px]">
                  {f.explanation}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* How was this decided? */}
      <div>
        <button
          onClick={() => setShowExplanation(!showExplanation)}
          className="flex items-center gap-1 text-[10px] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
        >
          <Info className="w-3 h-3" />
          How was this decided?
          {showExplanation ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>

        {showExplanation && (
          <div className="mt-2 rounded-md bg-[var(--bg-tertiary)] p-3 space-y-2">
            <div>
              <p className="text-[9px] uppercase text-[var(--text-muted)] mb-0.5">Method</p>
              <p className="text-[11px] text-[var(--text-primary)]">
                {EVALUATION_METHOD_LABELS[result.evaluation_method] || result.evaluation_method}
              </p>
            </div>

            {result.evaluation_criteria && result.evaluation_criteria.length > 0 && (
              <div>
                <p className="text-[9px] uppercase text-[var(--text-muted)] mb-1">Criteria Evaluated</p>
                <ul className="space-y-0.5">
                  {result.evaluation_criteria.map((c, i) => (
                    <li key={i} className="flex items-center gap-1.5 text-[10px] text-[var(--text-secondary)]">
                      <span className="w-1 h-1 rounded-full bg-[var(--accent)] shrink-0" />
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
