"use client";

import { useState, useCallback, useMemo } from "react";
import {
  Sparkles,
  Loader2,
  Lock,
  Globe,
  Upload,
  FileText,
  Pencil,
  Check,
  X,
  Play,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import {
  generateHierarchy,
  extractFromUrl,
  extractFromDocument,
  updateEntity,
  type HierarchyJob,
  type HierarchyEdge,
  type TreeNode,
  type ExtractedContent,
} from "@/lib/api";
import { validateFunctionalJobStatement, extractFirstWord } from "@/lib/validators";
import { ViewToggle } from "./ViewToggle";
import { JobTreeView } from "./JobTreeView";
import { JobGraphView } from "./JobGraphView";

const TIER_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  T1_strategic: { bg: "bg-violet-500/15", text: "text-violet-400", label: "Strategic" },
  T2_core: { bg: "bg-blue-500/15", text: "text-blue-400", label: "Core" },
  T3_execution: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "Execution" },
  T4_micro: { bg: "bg-amber-500/15", text: "text-amber-400", label: "Micro" },
};

const EXECUTOR_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  HUMAN: { bg: "bg-orange-500/15", text: "text-orange-400", label: "H" },
  AI: { bg: "bg-cyan-500/15", text: "text-cyan-400", label: "AI" },
};

type InputTab = "text" | "url" | "upload";

/** Generate a short hex ID (matches backend _uid format). */
function uid(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(6)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Parse the sample-job-hierarchy.json format into flat jobs + edges. */
function parseSampleJson(data: {
  jobHierarchy: {
    tier1: string;
    phases: Array<{
      tier2: string;
      jobSteps: Array<{
        tier3: string;
        outcomes: Array<{ tier4: string }>;
      }>;
    }>;
  };
}): { jobs: HierarchyJob[]; edges: HierarchyEdge[]; domain: string; summary: Record<string, number> } {
  const jobs: HierarchyJob[] = [];
  const edges: HierarchyEdge[] = [];
  const h = data.jobHierarchy;

  const t1Id = uid();
  jobs.push({ id: t1Id, tier: "T1_strategic", statement: h.tier1, category: "", rationale: "", metrics_hint: [] });

  for (const phase of h.phases) {
    const t2Id = uid();
    jobs.push({ id: t2Id, tier: "T2_core", statement: phase.tier2, category: "", rationale: "", metrics_hint: [] });
    edges.push({ parent_id: t1Id, child_id: t2Id, strength: 1 });

    for (const step of phase.jobSteps) {
      const t3Id = uid();
      jobs.push({ id: t3Id, tier: "T3_execution", statement: step.tier3, category: "", rationale: "", metrics_hint: [] });
      edges.push({ parent_id: t2Id, child_id: t3Id, strength: 1 });

      for (const outcome of step.outcomes) {
        const t4Id = uid();
        jobs.push({
          id: t4Id, tier: "T4_micro", statement: outcome.tier4,
          category: "metric_outcome", rationale: "", metrics_hint: [outcome.tier4],
        });
        edges.push({ parent_id: t3Id, child_id: t4Id, strength: 1 });
      }
    }
  }

  const counts: Record<string, number> = { T1_strategic: 0, T2_core: 0, T3_execution: 0, T4_micro: 0 };
  for (const j of jobs) counts[j.tier] = (counts[j.tier] || 0) + 1;

  return { jobs, edges, domain: h.tier1, summary: { ...counts, total_jobs: jobs.length } };
}

function buildTreeFromResponse(
  jobs: HierarchyJob[],
  edges: HierarchyEdge[],
): { functionalSpine: TreeNode[]; experienceDimension: TreeNode[] } {
  const childrenMap = new Map<string, string[]>();
  for (const e of edges) {
    if (!childrenMap.has(e.parent_id)) childrenMap.set(e.parent_id, []);
    childrenMap.get(e.parent_id)!.push(e.child_id);
  }

  const jobMap = new Map(jobs.map((j) => [j.id, j]));
  const allFunctionalChildren = new Set([...childrenMap.values()].flat());

  function buildNode(id: string): TreeNode {
    const j = jobMap.get(id)!;
    const kids = (childrenMap.get(id) ?? []).map(buildNode);
    const node: TreeNode = {
      id: j.id,
      tier: j.tier,
      statement: j.statement,
      category: j.category,
      metrics_hint: j.metrics_hint,
      executor_type: j.executor_type || "HUMAN",
    };
    if (kids.length > 0) node.children = kids;
    return node;
  }

  const functionalSpine = jobs
    .filter((j) => j.tier === "T1_strategic" && !allFunctionalChildren.has(j.id))
    .map((j) => buildNode(j.id));

  const experienceDimension: TreeNode[] = [];
  return { functionalSpine, experienceDimension };
}

export function PhaseOnePanel() {
  const {
    hierarchy,
    isGeneratingHierarchy,
    selectedJobId,
    visualizationMode,
    setHierarchy,
    setGeneratingHierarchy,
    lockTargetJob,
    updateHierarchyJob,
  } = useAppStore();

  const [activeTab, setActiveTab] = useState<InputTab>("text");
  const [domain, setDomain] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [extractedContent, setExtractedContent] = useState<ExtractedContent | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);

  // Job editing state
  const [editingJobId, setEditingJobId] = useState<string | null>(null);
  const [editStatement, setEditStatement] = useState("");
  const [editCategory, setEditCategory] = useState("");
  const [editMetrics, setEditMetrics] = useState<string[]>([]);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [isLoadingSample, setIsLoadingSample] = useState(false);

  const handleGenerate = useCallback(async (text?: string, keywords?: string[]) => {
    const input = text || domain.trim();
    if (!input || isGeneratingHierarchy) return;
    setGeneratingHierarchy(true);
    try {
      const result = await generateHierarchy({
        domain: input,
        keywords: keywords || input.split(/[,\s]+/).filter(Boolean),
      });
      const { functionalSpine, experienceDimension } = buildTreeFromResponse(
        result.jobs,
        result.edges,
      );
      setHierarchy(result, functionalSpine, experienceDimension);
    } catch (err) {
      console.error("Hierarchy generation failed:", err);
    } finally {
      setGeneratingHierarchy(false);
    }
  }, [domain, isGeneratingHierarchy, setHierarchy, setGeneratingHierarchy]);

  const handleExtractUrl = useCallback(async () => {
    if (!urlInput.trim() || isExtracting) return;
    setIsExtracting(true);
    setExtractError(null);
    setExtractedContent(null);
    try {
      const result = await extractFromUrl(urlInput.trim());
      setExtractedContent(result);
    } catch (err) {
      setExtractError(err instanceof Error ? err.message : "URL extraction failed");
    } finally {
      setIsExtracting(false);
    }
  }, [urlInput, isExtracting]);

  const handleUpload = useCallback(async (file: File) => {
    setIsExtracting(true);
    setExtractError(null);
    setExtractedContent(null);
    try {
      const result = await extractFromDocument(file);
      setExtractedContent(result);
    } catch (err) {
      setExtractError(err instanceof Error ? err.message : "Document extraction failed");
    } finally {
      setIsExtracting(false);
    }
  }, []);

  const handleGenerateFromExtracted = useCallback(() => {
    if (!extractedContent) return;

    // If the backend already parsed a structured hierarchy (e.g. ODI CSV), use it directly
    if (extractedContent.hierarchy) {
      const h = extractedContent.hierarchy;
      const fakeId = `csv-${Date.now().toString(16)}`;
      const result = {
        id: fakeId,
        domain: h.domain,
        jobs: h.jobs,
        edges: h.edges,
        summary: h.summary,
      };
      const { functionalSpine, experienceDimension } = buildTreeFromResponse(
        result.jobs,
        result.edges,
      );
      setHierarchy(result, functionalSpine, experienceDimension);
      return;
    }

    // Otherwise, use text to generate via LLM
    const text = extractedContent.context.what || extractedContent.title || extractedContent.text.slice(0, 200);
    const kw = extractedContent.keywords.length > 0 ? extractedContent.keywords : undefined;
    handleGenerate(text, kw);
  }, [extractedContent, handleGenerate, setHierarchy]);

  const handleLoadSample = useCallback(async () => {
    if (isLoadingSample) return;
    setIsLoadingSample(true);
    try {
      const resp = await fetch("/sample-job-hierarchy.json");
      const data = await resp.json();
      const parsed = parseSampleJson(data);
      const result = {
        id: `sample-${Date.now().toString(16)}`,
        domain: parsed.domain,
        jobs: parsed.jobs,
        edges: parsed.edges,
        summary: parsed.summary,
      };
      const { functionalSpine, experienceDimension } = buildTreeFromResponse(
        result.jobs,
        result.edges,
      );
      setHierarchy(result, functionalSpine, experienceDimension);
    } catch (err) {
      console.error("Failed to load sample:", err);
    } finally {
      setIsLoadingSample(false);
    }
  }, [isLoadingSample, setHierarchy]);

  const selectedJob = useMemo(() => {
    if (!selectedJobId || !hierarchy) return null;
    return hierarchy.jobs.find((j) => j.id === selectedJobId) ?? null;
  }, [selectedJobId, hierarchy]);

  const handleLock = useCallback(() => {
    if (!selectedJob) return;
    lockTargetJob({
      id: selectedJob.id,
      statement: selectedJob.statement,
      tier: selectedJob.tier,
      category: selectedJob.category,
      metricsHint: selectedJob.metrics_hint,
      executorType: (selectedJob.executor_type as "HUMAN" | "AI") || "HUMAN",
    });
  }, [selectedJob, lockTargetJob]);

  // Job editing handlers
  const startEditing = useCallback((job: HierarchyJob) => {
    setEditingJobId(job.id);
    setEditStatement(job.statement);
    setEditCategory(job.category);
    setEditMetrics([...job.metrics_hint]);
    setEditError(null);
  }, []);

  const cancelEditing = useCallback(() => {
    setEditingJobId(null);
    setEditError(null);
  }, []);

  const saveEdit = useCallback(async () => {
    if (!editingJobId) return;
    if (!validateFunctionalJobStatement(editStatement)) {
      setEditError(`Statement must start with an action verb. "${extractFirstWord(editStatement)}" is not valid.`);
      return;
    }
    setIsSavingEdit(true);
    setEditError(null);
    try {
      await updateEntity(editingJobId, {
        statement: editStatement,
        properties: { category: editCategory, metrics_hint: editMetrics },
      });
      updateHierarchyJob(editingJobId, {
        statement: editStatement,
        category: editCategory,
        metrics_hint: editMetrics,
      });
      setEditingJobId(null);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setIsSavingEdit(false);
    }
  }, [editingJobId, editStatement, editCategory, editMetrics, updateHierarchyJob]);

  const tabs: { key: InputTab; label: string; icon: React.ReactNode }[] = [
    { key: "text", label: "Text", icon: <FileText className="w-3 h-3" /> },
    { key: "url", label: "URL", icon: <Globe className="w-3 h-3" /> },
    { key: "upload", label: "Upload", icon: <Upload className="w-3 h-3" /> },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border)]">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Job Hierarchy
          </h2>
          {hierarchy && <ViewToggle />}
        </div>

        {/* Input tabs */}
        <div className="flex items-center gap-1 mb-3">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => { setActiveTab(tab.key); setExtractedContent(null); setExtractError(null); }}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${
                activeTab === tab.key
                  ? "bg-[var(--accent)] text-white"
                  : "bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
          {!hierarchy && (
            <button
              onClick={handleLoadSample}
              disabled={isLoadingSample}
              className="flex items-center gap-1 ml-auto px-2.5 py-1 rounded-md text-[10px] font-medium border border-dashed border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors disabled:opacity-40"
            >
              {isLoadingSample ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
              Try Sample
            </button>
          )}
        </div>

        {/* Tab content */}
        {activeTab === "text" && (
          <div className="space-y-2">
            <textarea
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="Paste a job description, goals, or constraints..."
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] px-3 py-2 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors resize-none"
              rows={3}
            />
            <button
              onClick={() => handleGenerate()}
              disabled={!domain.trim() || isGeneratingHierarchy}
              className="flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
            >
              {isGeneratingHierarchy ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Sparkles className="w-3 h-3" />
              )}
              Generate Hierarchy
            </button>
          </div>
        )}

        {activeTab === "url" && (
          <div className="space-y-2">
            <div className="flex gap-2">
              <input
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleExtractUrl()}
                placeholder="https://example.com/job-posting"
                className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
              />
              <button
                onClick={handleExtractUrl}
                disabled={!urlInput.trim() || isExtracting}
                className="flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
              >
                {isExtracting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Globe className="w-3 h-3" />}
                Extract
              </button>
            </div>
            {extractError && <p className="text-[10px] text-red-400">{extractError}</p>}
          </div>
        )}

        {activeTab === "upload" && (
          <div className="space-y-2">
            <label className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-[var(--border)] bg-[var(--bg-primary)] px-4 py-4 cursor-pointer hover:border-[var(--accent)] transition-colors">
              <Upload className="w-5 h-5 text-[var(--text-muted)] mb-1" />
              <span className="text-[10px] text-[var(--text-muted)]">
                Drop or click: PDF, DOCX, TXT, MD, CSV
              </span>
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md,.csv"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleUpload(f);
                }}
              />
            </label>
            {isExtracting && (
              <div className="flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin text-[var(--accent)]" />
                <span className="text-[10px] text-[var(--text-muted)]">Extracting...</span>
              </div>
            )}
            {extractError && <p className="text-[10px] text-red-400">{extractError}</p>}
          </div>
        )}

        {/* Extracted content summary */}
        {extractedContent && (activeTab === "url" || activeTab === "upload") && (
          <div className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] p-3 space-y-2">
            <p className="text-[10px] font-semibold uppercase text-[var(--text-muted)]">Extracted</p>
            {extractedContent.title && (
              <p className="text-xs font-medium text-[var(--text-primary)]">{extractedContent.title}</p>
            )}
            {extractedContent.hierarchy && (
              <div className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1.5">
                <p className="text-[10px] font-medium text-emerald-400">
                  Structured hierarchy detected: {extractedContent.hierarchy.summary.total_jobs} jobs across 4 tiers
                </p>
              </div>
            )}
            {!extractedContent.hierarchy && extractedContent.context.what && (
              <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                {extractedContent.context.what}
              </p>
            )}
            {extractedContent.keywords.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {extractedContent.keywords.map((kw, i) => (
                  <span key={i} className="rounded-full bg-[var(--bg-tertiary)] px-2 py-0.5 text-[9px] text-[var(--text-muted)]">
                    {kw}
                  </span>
                ))}
              </div>
            )}
            {extractedContent.job_hints.length > 0 && (
              <div>
                <p className="text-[9px] text-[var(--text-muted)] mb-1">Job hints:</p>
                {extractedContent.job_hints.map((h, i) => (
                  <p key={i} className="text-[10px] text-[var(--accent)]">{h}</p>
                ))}
              </div>
            )}
            <button
              onClick={handleGenerateFromExtracted}
              disabled={isGeneratingHierarchy}
              className="flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
            >
              {isGeneratingHierarchy ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Sparkles className="w-3 h-3" />
              )}
              {extractedContent.hierarchy ? "Load Hierarchy" : "Generate Hierarchy"}
            </button>
          </div>
        )}
      </div>

      {/* Visualization */}
      <div className="flex-1 overflow-y-auto px-3 py-3">
        {hierarchy ? (
          visualizationMode === "tree" ? (
            <JobTreeView />
          ) : (
            <JobGraphView />
          )
        ) : isGeneratingHierarchy ? (
          <div className="flex flex-col items-center justify-center h-full text-[var(--text-muted)]">
            <Loader2 className="w-6 h-6 animate-spin mb-2" />
            <p className="text-xs">Generating hierarchy...</p>
          </div>
        ) : (
          <EmptyState onLoadSample={handleLoadSample} isLoading={isLoadingSample} />
        )}

        {/* Summary badges */}
        {hierarchy && (
          <div className="mt-4 pt-3 border-t border-[var(--border)]">
            <div className="flex flex-wrap gap-2">
              {Object.entries(hierarchy.summary)
                .filter(([k]) => k.startsWith("T"))
                .map(([tier, count]) => {
                  const style = TIER_COLORS[tier] || TIER_COLORS.T1_strategic;
                  return (
                    <span
                      key={tier}
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] ${style.bg} ${style.text}`}
                    >
                      {style.label}: {count as number}
                    </span>
                  );
                })}
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] bg-[var(--bg-tertiary)] text-[var(--text-muted)]">
                Total: {hierarchy.summary.total_jobs}
              </span>
            </div>

            {/* Related jobs */}
            {hierarchy.related_jobs && hierarchy.related_jobs.length > 0 && (
              <div className="mt-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                  Related Jobs
                </p>
                <div className="space-y-1">
                  {hierarchy.related_jobs.map((rj) => {
                    const exec = EXECUTOR_COLORS[(rj.executor_type as string) || "HUMAN"] || EXECUTOR_COLORS.HUMAN;
                    return (
                      <div
                        key={rj.id}
                        className="flex items-start gap-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] px-2 py-1.5"
                      >
                        <span className={`shrink-0 mt-0.5 rounded px-1 py-0 text-[9px] font-medium uppercase ${exec.bg} ${exec.text}`}>
                          {exec.label}
                        </span>
                        <span className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                          {rj.statement}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Selected job detail + edit + lock button */}
      {selectedJob && (
        <div className="border-t border-[var(--border)] px-4 py-3">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] p-3">
            {editingJobId === selectedJob.id ? (
              /* Editing mode */
              <div className="space-y-2">
                <div>
                  <label className="text-[9px] text-[var(--text-muted)] uppercase">Statement</label>
                  <input
                    value={editStatement}
                    onChange={(e) => setEditStatement(e.target.value)}
                    className="w-full rounded border border-[var(--border)] bg-[var(--bg-secondary)] px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
                  />
                  {editError && <p className="text-[9px] text-red-400 mt-0.5">{editError}</p>}
                </div>
                <div>
                  <label className="text-[9px] text-[var(--text-muted)] uppercase">Category</label>
                  <input
                    value={editCategory}
                    onChange={(e) => setEditCategory(e.target.value)}
                    className="w-full rounded border border-[var(--border)] bg-[var(--bg-secondary)] px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
                  />
                </div>
                <div>
                  <label className="text-[9px] text-[var(--text-muted)] uppercase">Metrics Hints</label>
                  <div className="flex flex-wrap gap-1 mb-1">
                    {editMetrics.map((m, i) => (
                      <span key={i} className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-tertiary)] px-2 py-0.5 text-[9px] text-[var(--text-muted)]">
                        {m}
                        <button onClick={() => setEditMetrics(editMetrics.filter((_, j) => j !== i))} className="hover:text-red-400">
                          <X className="w-2.5 h-2.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                  <input
                    placeholder="Add metric hint + Enter"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && e.currentTarget.value.trim()) {
                        setEditMetrics([...editMetrics, e.currentTarget.value.trim()]);
                        e.currentTarget.value = "";
                      }
                    }}
                    className="w-full rounded border border-[var(--border)] bg-[var(--bg-secondary)] px-2 py-1 text-[10px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={saveEdit}
                    disabled={isSavingEdit}
                    className="flex items-center gap-1 rounded-md bg-[var(--accent)] px-2.5 py-1 text-[10px] font-medium text-white hover:opacity-90 disabled:opacity-40"
                  >
                    {isSavingEdit ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                    Save
                  </button>
                  <button
                    onClick={cancelEditing}
                    className="flex items-center gap-1 rounded-md bg-[var(--bg-tertiary)] px-2.5 py-1 text-[10px] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                  >
                    <X className="w-3 h-3" />
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              /* Display mode */
              <>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="text-xs font-medium text-[var(--text-primary)]">
                    {selectedJob.statement}
                  </span>
                  <div className="flex items-center gap-1 shrink-0">
                    <span
                      className={`rounded px-1.5 py-0.5 text-[9px] font-medium uppercase ${
                        (TIER_COLORS[selectedJob.tier] || TIER_COLORS.T1_strategic).bg
                      } ${(TIER_COLORS[selectedJob.tier] || TIER_COLORS.T1_strategic).text}`}
                    >
                      {(TIER_COLORS[selectedJob.tier] || TIER_COLORS.T1_strategic).label}
                    </span>
                    {(() => {
                      const exec = EXECUTOR_COLORS[(selectedJob.executor_type as string) || "HUMAN"] || EXECUTOR_COLORS.HUMAN;
                      return (
                        <span className={`rounded px-1.5 py-0.5 text-[9px] font-medium uppercase ${exec.bg} ${exec.text}`}>
                          {exec.label}
                        </span>
                      );
                    })()}
                    <button
                      onClick={() => startEditing(selectedJob)}
                      className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--accent)] hover:bg-[var(--accent-dim)] transition-colors"
                      title="Edit job"
                    >
                      <Pencil className="w-3 h-3" />
                    </button>
                  </div>
                </div>
                {selectedJob.category && (
                  <p className="text-[10px] text-[var(--text-muted)] mb-1">
                    Category: {selectedJob.category}
                  </p>
                )}
                {selectedJob.metrics_hint.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-2">
                    {selectedJob.metrics_hint.map((hint, i) => (
                      <span
                        key={i}
                        className="rounded-full bg-[var(--bg-tertiary)] px-2 py-0.5 text-[9px] text-[var(--text-muted)]"
                      >
                        {hint}
                      </span>
                    ))}
                  </div>
                )}
                <button
                  onClick={handleLock}
                  className="flex items-center gap-1.5 w-full justify-center rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 transition-opacity"
                >
                  <Lock className="w-3 h-3" />
                  Lock as Target Job
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function EmptyState({ onLoadSample, isLoading }: { onLoadSample: () => void; isLoading: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center mb-3">
        <Sparkles className="w-4 h-4 text-[var(--text-muted)]" />
      </div>
      <p className="text-xs text-[var(--text-secondary)] mb-1">No hierarchy yet</p>
      <p className="text-[11px] text-[var(--text-muted)] max-w-52 mb-3">
        Enter text, a URL, or upload a document to generate a structured job hierarchy.
      </p>
      <button
        onClick={onLoadSample}
        disabled={isLoading}
        className="flex items-center gap-1.5 rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-primary)] px-3 py-1.5 text-[10px] text-[var(--text-muted)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors disabled:opacity-40"
      >
        {isLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
        Try with sample: &ldquo;Manage Translation Projects&rdquo;
      </button>
    </div>
  );
}
