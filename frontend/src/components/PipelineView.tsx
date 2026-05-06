"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getSpec,
  runStage,
  evaluateSpec,
  decideQuestion,
  type HandoffSpec,
  type SpecStage,
  type OpenQuestion,
  type EvalCheck,
} from "@/lib/api";

// ── Helpers ──────────────────────────────────────────────────────────────────

const STAGE_ORDER = ["research", "synthesis", "decision", "engineering", "evaluation"];

function statusColor(status: string) {
  switch (status) {
    case "done": return "text-emerald-400 bg-emerald-900/30 border-emerald-700";
    case "in_progress": return "text-blue-400 bg-blue-900/30 border-blue-700";
    case "needs_human_decision": return "text-amber-400 bg-amber-900/30 border-amber-700";
    case "blocked": return "text-red-400 bg-red-900/30 border-red-700";
    default: return "text-[var(--text-muted)] bg-[var(--bg-tertiary)] border-[var(--border-primary)]";
  }
}

function statusDot(status: string) {
  switch (status) {
    case "done": return "bg-emerald-400";
    case "in_progress": return "bg-blue-400 animate-pulse";
    case "needs_human_decision": return "bg-amber-400 animate-pulse";
    case "blocked": return "bg-red-400";
    default: return "bg-[var(--text-muted)]";
  }
}

function evalStatusColor(status: string) {
  switch (status) {
    case "pass": return "text-emerald-400";
    case "fail": return "text-red-400";
    case "partial": return "text-amber-400";
    default: return "text-[var(--text-muted)]";
  }
}

function priorityBadge(priority: string) {
  switch (priority) {
    case "P0": return "text-red-300 bg-red-900/30 border-red-700";
    case "P1": return "text-amber-300 bg-amber-900/30 border-amber-700";
    default: return "text-[var(--text-muted)] bg-[var(--bg-tertiary)] border-[var(--border-primary)]";
  }
}

function ownerBadge(owner: string) {
  switch (owner) {
    case "claude": return "text-purple-300 bg-purple-900/30 border-purple-700";
    case "gemini": return "text-cyan-300 bg-cyan-900/30 border-cyan-700";
    case "human": return "text-green-300 bg-green-900/30 border-green-700";
    default: return "text-[var(--text-muted)] bg-[var(--bg-tertiary)] border-[var(--border-primary)]";
  }
}

function overallStatusColor(status: string) {
  switch (status) {
    case "green": return "text-emerald-400";
    case "yellow": return "text-amber-400";
    case "red": return "text-red-400";
    default: return "text-[var(--text-muted)]";
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StagePill({ stage, isActive, onClick }: {
  stage: SpecStage;
  isActive: boolean;
  onClick: () => void;
}) {
  const idx = STAGE_ORDER.indexOf(stage.id);
  const isLast = idx === STAGE_ORDER.length - 1;
  return (
    <div className="flex items-center">
      <button
        onClick={onClick}
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[10px] font-medium transition-all ${
          isActive
            ? statusColor(stage.status)
            : "text-[var(--text-muted)] bg-[var(--bg-tertiary)] border-[var(--border-primary)] hover:text-[var(--text-secondary)]"
        }`}
      >
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isActive ? statusDot(stage.status) : "bg-[var(--text-muted)]"}`} />
        {stage.name}
      </button>
      {!isLast && (
        <span className="text-[var(--text-muted)] text-[10px] mx-1">→</span>
      )}
    </div>
  );
}

function StagePanel({ stage, onRun, running }: {
  stage: SpecStage;
  onRun: (id: string) => void;
  running: string | null;
}) {
  const canRun = stage.owner === "claude" || stage.owner === "gemini";
  const isRunning = running === stage.id;

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold border ${statusColor(stage.status)}`}>
              {stage.status.replace(/_/g, " ")}
            </span>
            <span className={`px-1.5 py-0.5 rounded text-[9px] border ${ownerBadge(stage.owner)}`}>
              {stage.owner}
            </span>
          </div>
          <p className="text-[10px] text-[var(--text-secondary)] mt-1.5 leading-relaxed">
            {stage.description}
          </p>
        </div>
        {canRun && (
          <button
            onClick={() => onRun(stage.id)}
            disabled={isRunning}
            className="shrink-0 px-2.5 py-1.5 rounded-md bg-[var(--accent-primary)] text-white text-[10px] font-medium disabled:opacity-40 hover:opacity-90 transition-opacity"
          >
            {isRunning ? "Running…" : "Run Stage"}
          </button>
        )}
        {stage.owner === "human" && (
          <span className="shrink-0 text-[10px] text-amber-400 font-medium">
            Needs human action
          </span>
        )}
      </div>

      {/* Outputs */}
      {stage.outputs.length > 0 && (
        <div>
          <div className="text-[9px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Outputs</div>
          <div className="flex gap-1 flex-wrap">
            {stage.outputs.map((o) => (
              <span key={o} className="px-1.5 py-0.5 rounded text-[9px] bg-[var(--bg-tertiary)] text-[var(--text-secondary)] font-mono">
                {o}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Last run result */}
      {stage.last_run && (
        <div className="bg-[var(--bg-tertiary)] rounded-md p-2">
          <div className="text-[9px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Last Run</div>
          <div className="text-[10px] text-[var(--text-muted)]">{stage.last_run}</div>
          {stage.last_run_result && (
            <div className="mt-1 text-[10px]">
              {typeof stage.last_run_result.passed === "number" && (
                <span className="text-emerald-400">{stage.last_run_result.passed as number} passed</span>
              )}
              {typeof stage.last_run_result.failed === "number" && (stage.last_run_result.failed as number) > 0 && (
                <span className="text-red-400 ml-2">{stage.last_run_result.failed as number} failed</span>
              )}
              {typeof stage.last_run_result.status === "string" && (
                <span className={`ml-2 ${overallStatusColor(stage.last_run_result.status as string)}`}>
                  ● {stage.last_run_result.status as string}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function QuestionCard({ q, onDecide }: {
  q: OpenQuestion;
  onDecide: (id: string, decision: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [decisionText, setDecisionText] = useState("");
  const [deciding, setDeciding] = useState(false);

  const daysLeft = Math.ceil(
    (new Date(q.deadline).getTime() - Date.now()) / 86400000
  );
  const urgent = daysLeft <= 1 && q.status === "open";

  const handleDecide = async () => {
    if (!decisionText.trim()) return;
    setDeciding(true);
    try {
      await onDecide(q.id, decisionText);
    } finally {
      setDeciding(false);
      setDecisionText("");
    }
  };

  return (
    <div className={`rounded-md border p-2.5 ${
      q.status === "resolved"
        ? "border-emerald-800 bg-emerald-900/10"
        : urgent
        ? "border-red-800 bg-red-900/10"
        : "border-[var(--border-primary)] bg-[var(--bg-secondary)]"
    }`}>
      <div className="flex items-start gap-2">
        <div className="flex gap-1 shrink-0 mt-0.5">
          <span className={`px-1 py-0.5 rounded text-[8px] font-bold border ${priorityBadge(q.priority)}`}>
            {q.priority}
          </span>
          <span className="px-1 py-0.5 rounded text-[8px] border text-[var(--text-muted)] bg-[var(--bg-tertiary)] border-[var(--border-primary)]">
            {q.stage}
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed">
            {q.prompt}
          </p>
          {q.status === "resolved" && q.decision && (
            <p className="text-[9px] text-emerald-400 mt-1">
              ✓ {q.decision}
            </p>
          )}
          {q.status === "open" && (
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-[9px] ${urgent ? "text-red-400" : "text-[var(--text-muted)]"}`}>
                {daysLeft > 0 ? `${daysLeft}d left` : "overdue"}
              </span>
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-[9px] text-[var(--accent-primary)] hover:opacity-80"
              >
                {expanded ? "cancel" : "decide →"}
              </button>
            </div>
          )}
        </div>
        <span className="shrink-0 text-[9px] font-bold text-[var(--text-muted)]">{q.id}</span>
      </div>

      {expanded && q.status === "open" && (
        <div className="mt-2 flex gap-1.5">
          <input
            type="text"
            value={decisionText}
            onChange={(e) => setDecisionText(e.target.value)}
            placeholder="Enter decision..."
            className="flex-1 px-2 py-1 rounded bg-[var(--bg-tertiary)] border border-[var(--border-primary)] text-[10px] focus:outline-none focus:border-[var(--accent-primary)]"
            onKeyDown={(e) => e.key === "Enter" && handleDecide()}
          />
          <button
            onClick={handleDecide}
            disabled={deciding || !decisionText.trim()}
            className="px-2 py-1 rounded bg-emerald-700 text-white text-[9px] disabled:opacity-40 hover:bg-emerald-600"
          >
            {deciding ? "…" : "Save"}
          </button>
        </div>
      )}
    </div>
  );
}

function EvalReport({ checks }: { checks: EvalCheck[] }) {
  return (
    <div className="space-y-1.5">
      {checks.map((c) => (
        <div key={c.id} className="flex items-center gap-2 text-[10px]">
          <span className={`font-bold shrink-0 ${evalStatusColor(c.status)}`}>
            {c.status === "pass" ? "✓" : c.status === "fail" ? "✗" : "~"}
          </span>
          <span className="text-[var(--text-secondary)] shrink-0">{c.name}</span>
          {typeof c.pct === "number" && (
            <div className="flex-1 h-1.5 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  c.status === "pass" ? "bg-emerald-500" :
                  c.status === "fail" ? "bg-red-500" : "bg-amber-500"
                }`}
                style={{ width: `${c.pct}%` }}
              />
            </div>
          )}
          {typeof c.pct === "number" && (
            <span className={`text-[9px] shrink-0 ${evalStatusColor(c.status)}`}>{c.pct}%</span>
          )}
          {typeof c.passed === "number" && typeof c.failed === "number" && (
            <span className="text-[9px] text-[var(--text-muted)] shrink-0">
              {c.passed}✓ {c.failed > 0 ? `${c.failed}✗` : ""}
            </span>
          )}
          {c.note && (
            <span className="text-[9px] text-[var(--text-muted)] italic truncate">{c.note}</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function PipelineView() {
  const [spec, setSpec] = useState<HandoffSpec | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeStage, setActiveStage] = useState("engineering");
  const [running, setRunning] = useState<string | null>(null);
  const [evalResult, setEvalResult] = useState<{ status: string; checks: EvalCheck[]; ran_at: string } | null>(null);
  const [activeTab, setActiveTab] = useState<"pipeline" | "questions" | "tasks" | "eval">("pipeline");

  const loadSpec = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const s = await getSpec();
      setSpec(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load spec");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSpec(); }, [loadSpec]);

  const handleRun = async (stageId: string) => {
    setRunning(stageId);
    try {
      const result = await runStage(stageId);
      // Refresh spec to get updated stage state
      const updated = await getSpec();
      setSpec(updated);
      if (stageId === "evaluation" && result.result?.checks) {
        setEvalResult({
          status: result.result.status,
          checks: result.result.checks as EvalCheck[],
          ran_at: result.ran_at,
        });
        setActiveTab("eval");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Stage run failed");
    } finally {
      setRunning(null);
    }
  };

  const handleEvaluate = async () => {
    setRunning("evaluation");
    try {
      const result = await evaluateSpec();
      setEvalResult({ status: result.status, checks: result.checks, ran_at: result.ran_at });
      setActiveTab("eval");
      const updated = await getSpec();
      setSpec(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Evaluation failed");
    } finally {
      setRunning(null);
    }
  };

  const handleDecide = async (id: string, decision: string) => {
    await decideQuestion(id, decision);
    const updated = await getSpec();
    setSpec(updated);
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center text-[var(--text-muted)] text-xs">
        Loading pipeline spec…
      </div>
    );
  }

  if (error || !spec) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2 p-8">
        <p className="text-red-400 text-xs">{error || "No spec loaded"}</p>
        <button onClick={loadSpec} className="text-[10px] text-[var(--accent-primary)] hover:opacity-80">
          Retry
        </button>
      </div>
    );
  }

  const stages = spec.pipeline.stages;
  const activeStageObj = stages.find((s) => s.id === activeStage);
  const openQuestions = spec.open_questions.filter((q) => q.status === "open");
  const resolvedQuestions = spec.open_questions.filter((q) => q.status === "resolved");
  const pendingTasks = spec.engineering_tasks.filter((t) => t.status === "pending");
  const inProgressTasks = spec.engineering_tasks.filter((t) => t.status === "in_progress");
  const doneTasks = spec.engineering_tasks.filter((t) => t.status === "done");
  const metCriteria = spec.acceptance_criteria.filter((ac) => ac.status === "met");

  return (
    <div className="h-full flex flex-col bg-[var(--bg-primary)] text-[var(--text-primary)]">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-[var(--border-primary)] flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-semibold">Pipeline Orchestrator</h2>
            <span className="px-1.5 py-0.5 rounded text-[8px] bg-[var(--bg-tertiary)] text-[var(--text-muted)] border border-[var(--border-primary)]">
              {spec.metadata.spec_id}
            </span>
            <span className="px-1.5 py-0.5 rounded text-[8px] bg-purple-900/30 text-purple-300 border border-purple-700">
              v{spec.metadata.version}
            </span>
          </div>
          <p className="text-[9px] text-[var(--text-muted)] mt-0.5 truncate max-w-lg">
            {spec.metadata.description}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-[9px] text-[var(--text-muted)]">
            {metCriteria.length}/{spec.acceptance_criteria.length} AC met
          </div>
          <button
            onClick={handleEvaluate}
            disabled={running !== null}
            className="px-2.5 py-1 rounded bg-[var(--accent-primary)] text-white text-[10px] font-medium disabled:opacity-40 hover:opacity-90 transition-opacity"
          >
            {running === "evaluation" ? "Evaluating…" : "▶ Evaluate All"}
          </button>
          <button onClick={loadSpec} className="text-[9px] text-[var(--text-muted)] hover:text-[var(--text-secondary)]">
            ↺
          </button>
        </div>
      </div>

      {/* Stage tracker */}
      <div className="px-4 py-2 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)]">
        <div className="flex items-center gap-0.5 flex-wrap">
          {stages.map((s) => (
            <StagePill
              key={s.id}
              stage={s}
              isActive={s.id === activeStage}
              onClick={() => setActiveStage(s.id)}
            />
          ))}
        </div>
      </div>

      {/* Body tabs */}
      <div className="flex items-center gap-0 border-b border-[var(--border-primary)] px-4 bg-[var(--bg-secondary)]">
        {(["pipeline", "questions", "tasks", "eval"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1.5 text-[10px] font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-[var(--accent-primary)] text-[var(--text-primary)]"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            }`}
          >
            {tab === "pipeline" && "Stage Detail"}
            {tab === "questions" && (
              <>Questions {openQuestions.length > 0 && <span className="ml-1 px-1 rounded-full bg-amber-900/40 text-amber-300 text-[8px]">{openQuestions.length}</span>}</>
            )}
            {tab === "tasks" && "Engineering Tasks"}
            {tab === "eval" && (
              <>Evaluation{evalResult && <span className={`ml-1 text-[8px] ${overallStatusColor(evalResult.status)}`}> ● {evalResult.status}</span>}</>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Pipeline — Stage Detail */}
        {activeTab === "pipeline" && activeStageObj && (
          <div className="space-y-4">
            <StagePanel
              stage={activeStageObj}
              onRun={handleRun}
              running={running}
            />

            {/* Acceptance criteria for this stage */}
            {spec.acceptance_criteria.filter((ac) => ac.stage === activeStageObj.id).length > 0 && (
              <div>
                <div className="text-[9px] text-[var(--text-muted)] uppercase tracking-wider mb-2">
                  Acceptance Criteria
                </div>
                <div className="space-y-1.5">
                  {spec.acceptance_criteria
                    .filter((ac) => ac.stage === activeStageObj.id)
                    .map((ac) => (
                      <div key={ac.id} className="flex items-start gap-2 text-[10px]">
                        <span className={
                          ac.status === "met" ? "text-emerald-400 shrink-0" :
                          ac.status === "failed" ? "text-red-400 shrink-0" :
                          "text-[var(--text-muted)] shrink-0"
                        }>
                          {ac.status === "met" ? "✓" : ac.status === "failed" ? "✗" : "○"}
                        </span>
                        <span className="text-[var(--text-secondary)]">{ac.text}</span>
                        <span className="shrink-0 text-[8px] text-[var(--text-muted)]">{ac.id}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Open questions for this stage */}
            {spec.open_questions.filter((q) => q.stage === activeStageObj.id).length > 0 && (
              <div>
                <div className="text-[9px] text-[var(--text-muted)] uppercase tracking-wider mb-2">
                  Open Questions
                </div>
                <div className="space-y-2">
                  {spec.open_questions
                    .filter((q) => q.stage === activeStageObj.id)
                    .map((q) => (
                      <QuestionCard key={q.id} q={q} onDecide={handleDecide} />
                    ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Questions tab */}
        {activeTab === "questions" && (
          <div className="space-y-4">
            {openQuestions.length > 0 && (
              <div>
                <div className="text-[9px] text-[var(--text-muted)] uppercase tracking-wider mb-2">
                  Open — {openQuestions.length} questions need decisions
                </div>
                <div className="space-y-2">
                  {openQuestions.map((q) => (
                    <QuestionCard key={q.id} q={q} onDecide={handleDecide} />
                  ))}
                </div>
              </div>
            )}
            {resolvedQuestions.length > 0 && (
              <div>
                <div className="text-[9px] text-[var(--text-muted)] uppercase tracking-wider mb-2">
                  Resolved — {resolvedQuestions.length}
                </div>
                <div className="space-y-1.5">
                  {resolvedQuestions.map((q) => (
                    <QuestionCard key={q.id} q={q} onDecide={handleDecide} />
                  ))}
                </div>
              </div>
            )}
            {openQuestions.length === 0 && resolvedQuestions.length === 0 && (
              <p className="text-[var(--text-muted)] text-xs">No open questions.</p>
            )}
          </div>
        )}

        {/* Engineering Tasks tab */}
        {activeTab === "tasks" && (
          <div className="space-y-4">
            {inProgressTasks.length > 0 && (
              <div>
                <div className="text-[9px] text-[var(--text-muted)] uppercase tracking-wider mb-2">In Progress</div>
                <TaskList tasks={inProgressTasks} />
              </div>
            )}
            {pendingTasks.length > 0 && (
              <div>
                <div className="text-[9px] text-[var(--text-muted)] uppercase tracking-wider mb-2">Pending</div>
                <TaskList tasks={pendingTasks} />
              </div>
            )}
            {doneTasks.length > 0 && (
              <div>
                <div className="text-[9px] text-[var(--text-muted)] uppercase tracking-wider mb-2">Done — {doneTasks.length}</div>
                <TaskList tasks={doneTasks} />
              </div>
            )}
          </div>
        )}

        {/* Evaluation tab */}
        {activeTab === "eval" && (
          <div className="space-y-4">
            {evalResult ? (
              <>
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-bold ${overallStatusColor(evalResult.status)}`}>
                    ● {evalResult.status.toUpperCase()}
                  </span>
                  <span className="text-[10px] text-[var(--text-muted)]">{evalResult.ran_at}</span>
                  <button
                    onClick={handleEvaluate}
                    disabled={running !== null}
                    className="ml-auto px-2 py-0.5 rounded bg-[var(--bg-tertiary)] text-[10px] text-[var(--text-muted)] hover:text-[var(--text-secondary)] disabled:opacity-40"
                  >
                    {running === "evaluation" ? "Running…" : "Re-run"}
                  </button>
                </div>
                <EvalReport checks={evalResult.checks} />
              </>
            ) : (
              <div className="space-y-3">
                <p className="text-[var(--text-muted)] text-xs">No evaluation run yet.</p>
                <div>
                  <div className="text-[9px] text-[var(--text-muted)] uppercase tracking-wider mb-2">
                    Evaluation Plan
                  </div>
                  <div className="space-y-1.5">
                    {spec.evaluation_plan.tests.map((t) => (
                      <div key={t.id} className="flex items-start gap-2 text-[10px]">
                        <span className="text-[var(--text-muted)] shrink-0 font-mono">{t.id}</span>
                        <div className="flex-1 min-w-0">
                          <span className="text-[var(--text-secondary)]">{t.name}</span>
                          <span className="text-[var(--text-muted)] ml-2">— {t.description}</span>
                        </div>
                        <span className="shrink-0 text-[9px] text-emerald-400">{t.threshold}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <button
                  onClick={handleEvaluate}
                  disabled={running !== null}
                  className="px-3 py-1.5 rounded bg-[var(--accent-primary)] text-white text-[10px] font-medium disabled:opacity-40 hover:opacity-90"
                >
                  {running === "evaluation" ? "Running…" : "▶ Run Evaluation"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer: spec metadata */}
      <div className="px-4 py-1.5 border-t border-[var(--border-primary)] flex items-center justify-between text-[9px] text-[var(--text-muted)]">
        <span>Updated: {spec.metadata.updated}</span>
        <span>
          {doneTasks.length}/{spec.engineering_tasks.length} tasks done ·{" "}
          {metCriteria.length}/{spec.acceptance_criteria.length} criteria met ·{" "}
          {openQuestions.length} open questions
        </span>
        <span>Status: <span className={overallStatusColor(
          openQuestions.some((q) => q.priority === "P0") ? "red" :
          openQuestions.length > 0 ? "yellow" : "green"
        )}>{
          openQuestions.some((q) => q.priority === "P0") ? "blocked" :
          openQuestions.length > 0 ? "in progress" : "on track"
        }</span></span>
      </div>
    </div>
  );
}

function TaskList({ tasks }: { tasks: Array<{ id: string; title: string; priority: string; status: string; artifact?: string }> }) {
  return (
    <div className="space-y-1.5">
      {tasks.map((t) => (
        <div key={t.id} className="flex items-start gap-2 text-[10px]">
          <span className={`px-1 py-0.5 rounded text-[8px] font-bold border shrink-0 ${priorityBadge(t.priority)}`}>
            {t.priority}
          </span>
          <span className={`shrink-0 font-mono text-[9px] text-[var(--text-muted)]`}>{t.id}</span>
          <div className="flex-1 min-w-0">
            <span className={`${t.status === "done" ? "text-[var(--text-muted)] line-through" : "text-[var(--text-secondary)]"}`}>
              {t.title}
            </span>
            {t.artifact && (
              <span className="block text-[8px] text-[var(--text-muted)] font-mono mt-0.5 truncate">
                {t.artifact}
              </span>
            )}
          </div>
          <span className={`shrink-0 text-[8px] ${
            t.status === "done" ? "text-emerald-400" :
            t.status === "in_progress" ? "text-blue-400" : "text-[var(--text-muted)]"
          }`}>
            {t.status === "done" ? "✓" : t.status === "in_progress" ? "●" : "○"}
          </span>
        </div>
      ))}
    </div>
  );
}
