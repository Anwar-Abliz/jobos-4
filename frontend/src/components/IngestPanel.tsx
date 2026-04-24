"use client";

import { useState, useCallback } from "react";

interface IngestResultData {
  hierarchy: {
    domain?: string;
    jobs?: Array<{ id: string; tier: string; statement: string; category: string; executor_type: string }>;
    edges?: Array<{ parent_id: string; child_id: string }>;
    summary?: Record<string, number>;
  };
  context: {
    who: string;
    why: string;
    what: string;
    where: string;
    when: string;
    how: string;
    keywords: string[];
    job_hints: string[];
  };
  source_type: string;
  domain_detected: string;
  provenance: { sources?: string[] };
  warnings: string[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export function IngestPanel() {
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [domain, setDomain] = useState("");
  const [goal, setGoal] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestResultData | null>(null);
  const [error, setError] = useState("");

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files);
    setFiles((prev) => [...prev, ...dropped]);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
    }
  }, []);

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleIngest = async () => {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      let response: Response;

      if (files.length > 0) {
        const formData = new FormData();
        if (text) formData.append("text", text);
        if (url) formData.append("url", url);
        if (domain) formData.append("domain", domain);
        if (goal) formData.append("goal", goal);
        files.forEach((f) => formData.append("files", f));
        response = await fetch(`${API_BASE}/pipeline/ingest`, {
          method: "POST",
          body: formData,
        });
      } else {
        response = await fetch(`${API_BASE}/pipeline/ingest`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, url, domain, goal }),
        });
      }

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }

      const data: IngestResultData = await response.json();
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ingestion failed");
    } finally {
      setLoading(false);
    }
  };

  const hasInput = text || url || files.length > 0;
  const jobs = result?.hierarchy?.jobs || [];
  const tierCounts: Record<string, number> = {};
  jobs.forEach((j) => {
    const t = j.tier?.replace("_strategic", "").replace("_core", "").replace("_execution", "").replace("_micro", "") || "?";
    tierCounts[t] = (tierCounts[t] || 0) + 1;
  });

  return (
    <div className="h-full flex flex-col bg-[var(--bg-primary)] text-[var(--text-primary)]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border-primary)]">
        <h2 className="text-sm font-semibold">Universal Ingest Pipeline</h2>
        <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
          Text, URL, files, or any combination &rarr; Job Hierarchy + Context
        </p>
      </div>

      {/* Input area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* Text input */}
        <div>
          <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">
            Text / Keyword / Goal / Process
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste text, describe a goal, list process steps, or enter keywords..."
            className="w-full mt-1 p-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-xs resize-y min-h-[80px] focus:outline-none focus:border-[var(--accent-primary)]"
            rows={4}
          />
        </div>

        {/* URL input */}
        <div>
          <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">
            Web Page URL
          </label>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://..."
            className="w-full mt-1 p-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-xs focus:outline-none focus:border-[var(--accent-primary)]"
          />
        </div>

        {/* Domain + Goal hints */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">
              Domain (optional)
            </label>
            <input
              type="text"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="e.g., Healthcare, Logistics"
              className="w-full mt-1 p-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-xs focus:outline-none focus:border-[var(--accent-primary)]"
            />
          </div>
          <div>
            <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">
              Goal (optional)
            </label>
            <input
              type="text"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g., Reduce churn by 30%"
              className="w-full mt-1 p-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-xs focus:outline-none focus:border-[var(--accent-primary)]"
            />
          </div>
        </div>

        {/* File drop zone */}
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          className="border-2 border-dashed border-[var(--border-primary)] rounded-lg p-4 text-center cursor-pointer hover:border-[var(--accent-primary)] transition-colors"
          onClick={() => document.getElementById("file-input")?.click()}
        >
          <input
            id="file-input"
            type="file"
            multiple
            className="hidden"
            onChange={handleFileSelect}
            accept=".pdf,.docx,.txt,.md,.csv"
          />
          <p className="text-[11px] text-[var(--text-muted)]">
            Drop files here or click to browse
          </p>
          <p className="text-[9px] text-[var(--text-muted)] mt-1">
            PDF, DOCX, TXT, MD, CSV
          </p>
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div className="space-y-1">
            {files.map((f, i) => (
              <div key={i} className="flex items-center justify-between text-[10px] bg-[var(--bg-secondary)] rounded px-2 py-1">
                <span className="truncate">{f.name} ({(f.size / 1024).toFixed(1)}KB)</span>
                <button onClick={() => removeFile(i)} className="text-red-400 hover:text-red-300 ml-2">&times;</button>
              </div>
            ))}
          </div>
        )}

        {/* Ingest button */}
        <button
          onClick={handleIngest}
          disabled={!hasInput || loading}
          className="w-full py-2 rounded-md text-xs font-medium bg-[var(--accent-primary)] text-white disabled:opacity-40 hover:opacity-90 transition-opacity"
        >
          {loading ? "Ingesting..." : "Ingest"}
        </button>

        {/* Error */}
        {error && (
          <div className="p-2 rounded bg-red-900/30 border border-red-700 text-[10px] text-red-300">
            {error}
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="space-y-3">
            {/* Source + domain */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-2 py-0.5 rounded text-[9px] font-semibold bg-purple-900/30 text-purple-300 border border-purple-700">
                {result.source_type}
              </span>
              {result.domain_detected && (
                <span className="px-2 py-0.5 rounded text-[9px] font-semibold bg-cyan-900/30 text-cyan-300 border border-cyan-700">
                  {result.domain_detected}
                </span>
              )}
            </div>

            {/* Tier distribution */}
            {jobs.length > 0 && (
              <div className="bg-[var(--bg-secondary)] rounded-lg p-3">
                <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-2">
                  Hierarchy: {jobs.length} jobs
                </div>
                <div className="flex gap-2">
                  {Object.entries(tierCounts).map(([tier, count]) => (
                    <div key={tier} className="text-center">
                      <div className="text-lg font-bold text-[var(--text-primary)]">{count}</div>
                      <div className="text-[9px] text-[var(--text-muted)]">{tier}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Context summary */}
            {result.context && (result.context.what || result.context.why) && (
              <div className="bg-[var(--bg-secondary)] rounded-lg p-3">
                <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-2">
                  Context (5W1H)
                </div>
                <div className="space-y-1 text-[10px]">
                  {result.context.what && <div><span className="text-cyan-400 font-medium">What:</span> {result.context.what}</div>}
                  {result.context.why && <div><span className="text-purple-400 font-medium">Why:</span> {result.context.why}</div>}
                  {result.context.who && <div><span className="text-green-400 font-medium">Who:</span> {result.context.who}</div>}
                  {result.context.where && <div><span className="text-yellow-400 font-medium">Where:</span> {result.context.where}</div>}
                  {result.context.how && <div><span className="text-orange-400 font-medium">How:</span> {result.context.how}</div>}
                </div>
                {result.context.keywords.length > 0 && (
                  <div className="mt-2 flex gap-1 flex-wrap">
                    {result.context.keywords.slice(0, 8).map((kw, i) => (
                      <span key={i} className="px-1.5 py-0.5 rounded text-[8px] bg-[var(--bg-primary)] text-[var(--text-muted)]">
                        {kw}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Job list */}
            {jobs.length > 0 && (
              <div className="bg-[var(--bg-secondary)] rounded-lg p-3">
                <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-2">
                  Jobs
                </div>
                <div className="space-y-1 max-h-[300px] overflow-y-auto">
                  {jobs.map((j, i) => (
                    <div key={i} className="flex items-start gap-2 text-[10px]">
                      <span className={`px-1 py-0.5 rounded text-[8px] font-bold shrink-0 ${
                        j.tier?.includes("T1") ? "bg-purple-900/40 text-purple-300" :
                        j.tier?.includes("T2") ? "bg-blue-900/40 text-blue-300" :
                        j.tier?.includes("T3") ? "bg-green-900/40 text-green-300" :
                        "bg-yellow-900/40 text-yellow-300"
                      }`}>
                        {j.tier?.slice(0, 2) || "?"}
                      </span>
                      <span className="text-[var(--text-secondary)]">{j.statement}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Provenance */}
            {result.provenance?.sources && result.provenance.sources.length > 0 && (
              <div className="text-[9px] text-[var(--text-muted)]">
                Sources: {result.provenance.sources.join(", ")}
              </div>
            )}

            {/* Warnings */}
            {result.warnings.length > 0 && (
              <div className="p-2 rounded bg-yellow-900/20 border border-yellow-700 text-[10px] text-yellow-300">
                {result.warnings.map((w, i) => <div key={i}>{w}</div>)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
