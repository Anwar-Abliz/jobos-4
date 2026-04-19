"use client";

import { useState } from "react";
import { Plus, Trash2, Sparkles, Loader2, ArrowRight } from "lucide-react";
import { useAppStore, type MetricDefinition } from "@/lib/store";
import { generateExperience, editExperience } from "@/lib/api";
import { TargetJobBadge } from "./TargetJobBadge";

const METRIC_TEMPLATES = [
  { label: "Minimize time", template: "Minimize the time to " },
  { label: "Minimize failure", template: "Minimize the likelihood of " },
  { label: "Increase success", template: "Increase the rate of " },
  { label: "Reduce frequency", template: "Reduce the frequency of " },
  { label: "Maximize output", template: "Maximize the number of " },
];

export function PhaseTwoPanel() {
  const {
    targetJob,
    dimensionView,
    outcomes,
    setDimensionView,
    setOutcomes,
    confirmOutcomes,
  } = useAppStore();

  const [isGeneratingExp, setIsGeneratingExp] = useState(false);
  const [expError, setExpError] = useState<string | null>(null);

  // Experience marker state for editing
  const [editingFeel, setEditingFeel] = useState("");
  const [editingToBe, setEditingToBe] = useState("");

  // Metric form state
  const [metricStatement, setMetricStatement] = useState("");
  const [metricTarget, setMetricTarget] = useState("");
  const [metricThreshold, setMetricThreshold] = useState("");

  if (!targetJob) return null;

  const isAiJob = targetJob.executorType === "AI";

  const handleGenerateExperience = async () => {
    setIsGeneratingExp(true);
    setExpError(null);
    try {
      const result = await generateExperience(targetJob.id);
      setOutcomes({
        experienceMarkers: {
          feel_markers: result.markers.feel_markers,
          to_be_markers: result.markers.to_be_markers,
        },
      });
    } catch (err) {
      setExpError(err instanceof Error ? err.message : "Failed to generate experience markers");
    } finally {
      setIsGeneratingExp(false);
    }
  };

  const handleAddFeelMarker = () => {
    if (!editingFeel.trim()) return;
    const updated = [...outcomes.experienceMarkers.feel_markers, editingFeel.trim()];
    setOutcomes({
      experienceMarkers: { ...outcomes.experienceMarkers, feel_markers: updated },
    });
    setEditingFeel("");
  };

  const handleAddToBeMarker = () => {
    if (!editingToBe.trim()) return;
    const updated = [...outcomes.experienceMarkers.to_be_markers, editingToBe.trim()];
    setOutcomes({
      experienceMarkers: { ...outcomes.experienceMarkers, to_be_markers: updated },
    });
    setEditingToBe("");
  };

  const handleRemoveFeelMarker = (idx: number) => {
    const updated = outcomes.experienceMarkers.feel_markers.filter((_, i) => i !== idx);
    setOutcomes({
      experienceMarkers: { ...outcomes.experienceMarkers, feel_markers: updated },
    });
  };

  const handleRemoveToBeMarker = (idx: number) => {
    const updated = outcomes.experienceMarkers.to_be_markers.filter((_, i) => i !== idx);
    setOutcomes({
      experienceMarkers: { ...outcomes.experienceMarkers, to_be_markers: updated },
    });
  };

  const handleSaveExperience = async () => {
    try {
      await editExperience(
        targetJob.id,
        outcomes.experienceMarkers.feel_markers,
        outcomes.experienceMarkers.to_be_markers,
      );
    } catch (err) {
      console.error("Failed to save experience markers:", err);
    }
  };

  const handleSelectTemplate = (template: string) => {
    setMetricStatement(template);
  };

  const handleAddMetric = () => {
    if (!metricStatement.trim()) return;
    const metric: MetricDefinition = {
      statement: metricStatement.trim(),
      target: metricTarget.trim(),
      switchThreshold: isAiJob ? "" : metricThreshold.trim(),
    };
    setOutcomes({ metrics: [...outcomes.metrics, metric] });
    setMetricStatement("");
    setMetricTarget("");
    setMetricThreshold("");
  };

  const handleRemoveMetric = (idx: number) => {
    setOutcomes({ metrics: outcomes.metrics.filter((_, i) => i !== idx) });
  };

  const hasOutcomes =
    outcomes.experienceMarkers.feel_markers.length > 0 ||
    outcomes.experienceMarkers.to_be_markers.length > 0 ||
    outcomes.metrics.length > 0;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border)] space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Define Outcomes
        </h2>
        <TargetJobBadge />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {/* Dimension toggle — AI jobs get Dim B only */}
        {isAiJob ? (
          <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/5 px-3 py-2">
            <p className="text-[10px] font-medium text-cyan-400">
              AI Job — no experience dimension. KPI metrics only.
            </p>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setDimensionView("A")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                dimensionView === "A"
                  ? "bg-[var(--accent)] text-white"
                  : "bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
              }`}
            >
              Experience (Dim A)
            </button>
            <button
              onClick={() => setDimensionView("B")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                dimensionView === "B"
                  ? "bg-[var(--accent)] text-white"
                  : "bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
              }`}
            >
              Metrics (Dim B)
            </button>
          </div>
        )}

        {(!isAiJob && dimensionView === "A") ? (
          <div className="space-y-3">
            {/* Generate button */}
            <button
              onClick={handleGenerateExperience}
              disabled={isGeneratingExp}
              className="flex items-center gap-1.5 rounded-lg bg-[var(--bg-tertiary)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--border)] transition-colors disabled:opacity-40"
            >
              {isGeneratingExp ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Sparkles className="w-3 h-3" />
              )}
              Generate Experience Markers
            </button>
            {expError && <p className="text-[10px] text-red-400">{expError}</p>}

            {/* Feel markers */}
            <div>
              <p className="text-[10px] font-semibold uppercase text-[var(--text-muted)] mb-1">
                Feel Markers
              </p>
              <div className="space-y-1 mb-2">
                {outcomes.experienceMarkers.feel_markers.map((m, i) => (
                  <div key={i} className="flex items-center justify-between gap-2 rounded bg-[var(--bg-tertiary)] px-2 py-1">
                    <span className="text-xs text-[var(--text-primary)]">{m}</span>
                    <button
                      onClick={() => handleRemoveFeelMarker(i)}
                      className="text-[var(--text-muted)] hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex gap-1">
                <input
                  value={editingFeel}
                  onChange={(e) => setEditingFeel(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAddFeelMarker()}
                  placeholder="Feel confident in..."
                  className="flex-1 rounded border border-[var(--border)] bg-[var(--bg-primary)] px-2 py-1 text-[11px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]"
                />
                <button
                  onClick={handleAddFeelMarker}
                  disabled={!editingFeel.trim()}
                  className="p-1 rounded bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-[var(--accent)] disabled:opacity-30"
                >
                  <Plus className="w-3 h-3" />
                </button>
              </div>
            </div>

            {/* To Be markers */}
            <div>
              <p className="text-[10px] font-semibold uppercase text-[var(--text-muted)] mb-1">
                To Be Markers
              </p>
              <div className="space-y-1 mb-2">
                {outcomes.experienceMarkers.to_be_markers.map((m, i) => (
                  <div key={i} className="flex items-center justify-between gap-2 rounded bg-[var(--bg-tertiary)] px-2 py-1">
                    <span className="text-xs text-[var(--text-primary)]">{m}</span>
                    <button
                      onClick={() => handleRemoveToBeMarker(i)}
                      className="text-[var(--text-muted)] hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex gap-1">
                <input
                  value={editingToBe}
                  onChange={(e) => setEditingToBe(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAddToBeMarker()}
                  placeholder="To be seen as..."
                  className="flex-1 rounded border border-[var(--border)] bg-[var(--bg-primary)] px-2 py-1 text-[11px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]"
                />
                <button
                  onClick={handleAddToBeMarker}
                  disabled={!editingToBe.trim()}
                  className="p-1 rounded bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-[var(--accent)] disabled:opacity-30"
                >
                  <Plus className="w-3 h-3" />
                </button>
              </div>
            </div>

            {/* Save experience button */}
            {(outcomes.experienceMarkers.feel_markers.length > 0 ||
              outcomes.experienceMarkers.to_be_markers.length > 0) && (
              <button
                onClick={handleSaveExperience}
                className="text-[10px] text-[var(--accent)] hover:underline"
              >
                Save markers to backend
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {/* Template chips */}
            <div>
              <p className="text-[10px] font-semibold uppercase text-[var(--text-muted)] mb-2">
                ODI Templates
              </p>
              <div className="flex flex-wrap gap-1.5">
                {METRIC_TEMPLATES.map((t) => (
                  <button
                    key={t.label}
                    onClick={() => handleSelectTemplate(t.template)}
                    className="rounded-full border border-[var(--border)] bg-[var(--bg-primary)] px-2.5 py-1 text-[10px] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors"
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Existing metrics */}
            {outcomes.metrics.length > 0 && (
              <div className="space-y-2">
                {outcomes.metrics.map((m, i) => (
                  <div
                    key={i}
                    className="flex items-start justify-between gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] p-2"
                  >
                    <div>
                      <p className="text-xs font-medium text-[var(--text-primary)]">{m.statement}</p>
                      {m.target && (
                        <p className="text-[10px] text-[var(--text-muted)]">
                          Target: {m.target}
                        </p>
                      )}
                      {m.switchThreshold && !isAiJob && (
                        <p className="text-[10px] text-red-400">Switch: {m.switchThreshold}</p>
                      )}
                    </div>
                    <button
                      onClick={() => handleRemoveMetric(i)}
                      className="text-[var(--text-muted)] hover:text-red-400 transition-colors shrink-0"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Add metric form */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] p-3 space-y-2">
              <p className="text-[10px] font-semibold uppercase text-[var(--text-muted)]">
                Add Metric
              </p>
              <input
                value={metricStatement}
                onChange={(e) => setMetricStatement(e.target.value)}
                placeholder="Outcome statement (e.g. Minimize the time to complete onboarding)"
                className="w-full rounded border border-[var(--border)] bg-[var(--bg-secondary)] px-2 py-1 text-[11px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]"
              />
              <input
                value={metricTarget}
                onChange={(e) => setMetricTarget(e.target.value)}
                placeholder="Target (e.g. < 5 min)"
                className="w-full rounded border border-[var(--border)] bg-[var(--bg-secondary)] px-2 py-1 text-[11px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]"
              />
              {!isAiJob && (
                <input
                  value={metricThreshold}
                  onChange={(e) => setMetricThreshold(e.target.value)}
                  placeholder="Switch threshold (e.g. > 15 min)"
                  className="w-full rounded border border-[var(--border)] bg-[var(--bg-secondary)] px-2 py-1 text-[11px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]"
                />
              )}
              <button
                onClick={handleAddMetric}
                disabled={!metricStatement.trim()}
                className="flex items-center gap-1 rounded bg-[var(--bg-tertiary)] px-2 py-1 text-[10px] text-[var(--text-secondary)] hover:text-[var(--accent)] disabled:opacity-30 transition-colors"
              >
                <Plus className="w-3 h-3" />
                Add Metric
              </button>
            </div>

            {/* Metrics hints from target job */}
            {targetJob.metricsHint.length > 0 && (
              <div>
                <p className="text-[10px] text-[var(--text-muted)] mb-1">Suggested metrics:</p>
                <div className="flex flex-wrap gap-1">
                  {targetJob.metricsHint.map((hint, i) => (
                    <button
                      key={i}
                      onClick={() => setMetricStatement(hint)}
                      className="rounded-full bg-[var(--bg-tertiary)] px-2 py-0.5 text-[9px] text-[var(--text-muted)] hover:text-[var(--accent)] transition-colors"
                    >
                      {hint}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Confirm button */}
      <div className="border-t border-[var(--border)] px-4 py-3">
        <button
          onClick={confirmOutcomes}
          disabled={!hasOutcomes}
          className="flex items-center gap-1.5 w-full justify-center rounded-lg bg-[var(--accent)] px-3 py-2 text-xs font-medium text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
        >
          Confirm Outcomes & Get Decision
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}
