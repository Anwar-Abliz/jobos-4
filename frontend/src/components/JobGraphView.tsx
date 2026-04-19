"use client";

import { useRef, useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useAppStore } from "@/lib/store";
import { buildGraphData, TIER_LABELS, type GraphNode } from "@/lib/graph-data";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

export function JobGraphView() {
  const hierarchy = useAppStore((s) => s.hierarchy);
  const selectedJobId = useAppStore((s) => s.selectedJobId);
  const setSelectedJobId = useAppStore((s) => s.setSelectedJobId);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 400 });
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  // Track mouse for tooltip positioning
  useEffect(() => {
    const handler = (e: MouseEvent) => setTooltipPos({ x: e.clientX, y: e.clientY });
    window.addEventListener("mousemove", handler);
    return () => window.removeEventListener("mousemove", handler);
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  const graphData = useMemo(() => {
    if (!hierarchy) return { nodes: [], links: [] };
    return buildGraphData(hierarchy.jobs, hierarchy.edges);
  }, [hierarchy]);

  const selectedNode = useMemo(() => {
    if (!selectedJobId) return null;
    return graphData.nodes.find((n) => n.id === selectedJobId) ?? null;
  }, [selectedJobId, graphData]);

  const handleNodeClick = useCallback(
    (node: { id?: string | number }) => {
      if (node.id) setSelectedJobId(String(node.id));
    },
    [setSelectedJobId],
  );

  const handleNodeHover = useCallback(
    (node: { id?: string | number } | null) => {
      if (node && node.id) {
        const gNode = graphData.nodes.find((n) => n.id === String(node.id));
        setHoveredNode(gNode ?? null);
      } else {
        setHoveredNode(null);
      }
    },
    [graphData.nodes],
  );

  const nodeCanvasObject = useCallback(
    (node: Record<string, unknown>, ctx: CanvasRenderingContext2D) => {
      const gNode = node as unknown as GraphNode & { x: number; y: number };
      const { x, y, size, color, label, id } = gNode;
      const isSelected = id === selectedJobId;
      const radius = size / 2;

      // Draw node circle
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      if (isSelected) {
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // AI executor indicator: cyan ring
      if (gNode.executorType === "AI") {
        ctx.beginPath();
        ctx.arc(x, y, radius + 2, 0, 2 * Math.PI);
        ctx.strokeStyle = "#22d3ee";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Draw label
      ctx.font = `${Math.max(3, radius * 0.8)}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = "#a3a3a3";
      ctx.fillText(label, x, y + radius + 2);
    },
    [selectedJobId],
  );

  const linkCanvasObject = useCallback(
    (link: Record<string, unknown>, ctx: CanvasRenderingContext2D) => {
      const source = link.source as { x: number; y: number } | undefined;
      const target = link.target as { x: number; y: number } | undefined;
      if (!source || !target) return;

      // Draw directed arrow with tier-aware color
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const len = Math.sqrt(dx * dx + dy * dy);
      if (len === 0) return;

      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.lineTo(target.x, target.y);
      ctx.strokeStyle = "rgba(100, 100, 100, 0.4)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Arrowhead
      const arrowLen = 4;
      const angle = Math.atan2(dy, dx);
      const ax = target.x - arrowLen * Math.cos(angle - Math.PI / 7);
      const ay = target.y - arrowLen * Math.sin(angle - Math.PI / 7);
      const bx = target.x - arrowLen * Math.cos(angle + Math.PI / 7);
      const by = target.y - arrowLen * Math.sin(angle + Math.PI / 7);

      ctx.beginPath();
      ctx.moveTo(target.x, target.y);
      ctx.lineTo(ax, ay);
      ctx.lineTo(bx, by);
      ctx.fillStyle = "rgba(100, 100, 100, 0.6)";
      ctx.fill();
    },
    [],
  );

  if (!hierarchy) return null;

  // Calculate graph area width: full if no node selected, minus detail panel if selected
  const graphWidth = selectedNode ? dimensions.width * 0.65 : dimensions.width;

  return (
    <div ref={containerRef} className="graph-container relative">
      <div className="flex h-full">
        {/* Graph */}
        <div style={{ width: graphWidth, height: dimensions.height }}>
          <ForceGraph2D
            graphData={graphData}
            width={graphWidth}
            height={dimensions.height}
            backgroundColor="transparent"
            nodeCanvasObject={nodeCanvasObject}
            nodePointerAreaPaint={(node: Record<string, unknown>, color, ctx) => {
              const gNode = node as unknown as GraphNode & { x: number; y: number };
              ctx.beginPath();
              ctx.arc(gNode.x, gNode.y, gNode.size, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
            }}
            onNodeClick={handleNodeClick}
            onNodeHover={handleNodeHover}
            linkCanvasObjectMode={() => "replace"}
            linkCanvasObject={linkCanvasObject}
            cooldownTicks={80}
            d3AlphaDecay={0.04}
          />
        </div>

        {/* Detail panel */}
        {selectedNode && (
          <div className="w-[35%] border-l border-[var(--border)] bg-[var(--bg-primary)] overflow-y-auto p-3 space-y-3">
            <div>
              <p className="text-[9px] font-semibold uppercase text-[var(--text-muted)] mb-1">
                {TIER_LABELS[selectedNode.tier] || selectedNode.tier}
              </p>
              <div className="flex items-center gap-1 mb-1">
                <span
                  className={`rounded px-1.5 py-0.5 text-[9px] font-medium uppercase ${
                    selectedNode.executorType === "AI"
                      ? "bg-cyan-500/15 text-cyan-400"
                      : "bg-orange-500/15 text-orange-400"
                  }`}
                >
                  {selectedNode.executorType === "AI" ? "AI" : "HUMAN"}
                </span>
              </div>
              <p className="text-xs font-medium text-[var(--text-primary)] leading-relaxed">
                {selectedNode.statement}
              </p>
            </div>

            {selectedNode.category && (
              <div>
                <p className="text-[9px] font-semibold uppercase text-[var(--text-muted)] mb-0.5">How</p>
                <p className="text-[11px] text-[var(--text-secondary)]">{selectedNode.category}</p>
              </div>
            )}

            {selectedNode.rationale && (
              <div>
                <p className="text-[9px] font-semibold uppercase text-[var(--text-muted)] mb-0.5">Why</p>
                <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                  {selectedNode.rationale}
                </p>
              </div>
            )}

            {selectedNode.metricsHint.length > 0 && (
              <div>
                <p className="text-[9px] font-semibold uppercase text-[var(--text-muted)] mb-1">Metrics</p>
                <div className="space-y-1">
                  {selectedNode.metricsHint.map((m, i) => (
                    <div
                      key={i}
                      className="rounded bg-[var(--bg-tertiary)] px-2 py-1 text-[10px] text-[var(--text-muted)]"
                    >
                      {m}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Hover tooltip */}
      {hoveredNode && hoveredNode.id !== selectedJobId && (
        <div
          className="fixed z-50 pointer-events-none rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] px-3 py-2 shadow-lg max-w-[240px]"
          style={{
            left: tooltipPos.x + 12,
            top: tooltipPos.y + 12,
          }}
        >
          <p className="text-[9px] font-semibold uppercase" style={{ color: hoveredNode.color }}>
            {TIER_LABELS[hoveredNode.tier] || hoveredNode.tier}
          </p>
          <p className="text-[11px] text-[var(--text-primary)] leading-snug">
            {hoveredNode.statement}
          </p>
        </div>
      )}
    </div>
  );
}
