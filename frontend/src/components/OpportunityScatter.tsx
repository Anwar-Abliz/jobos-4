"use client";

import { Target } from "lucide-react";

interface OpportunityPoint {
  id: string;
  label: string;
  importance: number;
  satisfaction: number;
  frequency?: number;
  segment?: string;
}

interface OpportunityScatterProps {
  points: OpportunityPoint[];
  highlightIds?: string[];
  onPointClick?: (pointId: string) => void;
  showThresholdLine?: boolean;
  importanceThreshold?: number;
}

const SEGMENT_COLORS = [
  "rgb(139, 92, 246)",   // violet
  "rgb(59, 130, 246)",   // blue
  "rgb(16, 185, 129)",   // emerald
  "rgb(245, 158, 11)",   // amber
  "rgb(239, 68, 68)",    // red
  "rgb(236, 72, 153)",   // pink
  "rgb(6, 182, 212)",    // cyan
  "rgb(249, 115, 22)",   // orange
];

function getSegmentColor(segment: string | undefined, segments: string[]): string {
  if (!segment) return "rgb(163, 163, 163)";
  const index = segments.indexOf(segment);
  return SEGMENT_COLORS[index % SEGMENT_COLORS.length];
}

export function OpportunityScatter({
  points,
  highlightIds = [],
  onPointClick,
  showThresholdLine = true,
  importanceThreshold = 7,
}: OpportunityScatterProps) {
  const CHART_W = 100;
  const CHART_H = 100;
  const PADDING = 12;

  const segments = [...new Set(points.map((p) => p.segment).filter(Boolean))] as string[];

  // Compute opportunity score: importance + (importance - satisfaction)
  const scoredPoints = points.map((p) => ({
    ...p,
    opportunityScore: p.importance + Math.max(0, p.importance - p.satisfaction),
  }));

  const maxFreq = Math.max(...points.map((p) => p.frequency ?? 1), 1);

  // Scale: X = satisfaction (0-10), Y = importance (0-10)
  function toX(satisfaction: number): number {
    return PADDING + ((satisfaction / 10) * (CHART_W - 2 * PADDING));
  }
  function toY(importance: number): number {
    return CHART_H - PADDING - ((importance / 10) * (CHART_H - 2 * PADDING));
  }
  function bubbleR(frequency: number | undefined): number {
    const f = frequency ?? 1;
    return 1.5 + (f / maxFreq) * 3;
  }

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Target className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Opportunity Landscape
          </h3>
        </div>
        <span className="text-[10px] text-[var(--text-muted)]">{points.length} outcomes</span>
      </div>

      {/* Segment legend */}
      {segments.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {segments.map((seg) => (
            <div key={seg} className="flex items-center gap-1">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: getSegmentColor(seg, segments) }}
              />
              <span className="text-[9px] text-[var(--text-muted)]">{seg}</span>
            </div>
          ))}
        </div>
      )}

      {/* SVG Chart */}
      <div className="relative w-full" style={{ aspectRatio: "1 / 1", maxHeight: "400px" }}>
        <svg
          viewBox={`0 0 ${CHART_W} ${CHART_H}`}
          className="w-full h-full"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Background grid */}
          {[2, 4, 6, 8].map((v) => (
            <g key={v}>
              <line
                x1={toX(v)}
                y1={PADDING}
                x2={toX(v)}
                y2={CHART_H - PADDING}
                stroke="var(--border)"
                strokeWidth="0.2"
              />
              <line
                x1={PADDING}
                y1={toY(v)}
                x2={CHART_W - PADDING}
                y2={toY(v)}
                stroke="var(--border)"
                strokeWidth="0.2"
              />
            </g>
          ))}

          {/* Axes */}
          <line
            x1={PADDING}
            y1={CHART_H - PADDING}
            x2={CHART_W - PADDING}
            y2={CHART_H - PADDING}
            stroke="var(--text-muted)"
            strokeWidth="0.3"
          />
          <line
            x1={PADDING}
            y1={PADDING}
            x2={PADDING}
            y2={CHART_H - PADDING}
            stroke="var(--text-muted)"
            strokeWidth="0.3"
          />

          {/* Axis labels */}
          <text
            x={CHART_W / 2}
            y={CHART_H - 2}
            textAnchor="middle"
            fill="var(--text-muted)"
            fontSize="3"
          >
            Satisfaction
          </text>
          <text
            x={3}
            y={CHART_H / 2}
            textAnchor="middle"
            fill="var(--text-muted)"
            fontSize="3"
            transform={`rotate(-90, 3, ${CHART_H / 2})`}
          >
            Importance
          </text>

          {/* Overserved / underserved diagonal */}
          <line
            x1={PADDING}
            y1={CHART_H - PADDING}
            x2={CHART_W - PADDING}
            y2={PADDING}
            stroke="var(--text-muted)"
            strokeWidth="0.15"
            strokeDasharray="1,1"
          />

          {/* Threshold line */}
          {showThresholdLine && (
            <line
              x1={PADDING}
              y1={toY(importanceThreshold)}
              x2={CHART_W - PADDING}
              y2={toY(importanceThreshold)}
              stroke="rgb(245, 158, 11)"
              strokeWidth="0.3"
              strokeDasharray="1.5,1"
            />
          )}

          {/* Opportunity zone highlight (high importance, low satisfaction) */}
          <rect
            x={PADDING}
            y={toY(10)}
            width={(CHART_W - 2 * PADDING) * 0.4}
            height={toY(importanceThreshold) - toY(10)}
            fill="rgb(239, 68, 68)"
            fillOpacity="0.05"
            rx="1"
          />

          {/* Bubbles */}
          {scoredPoints.map((point) => {
            const cx = toX(point.satisfaction);
            const cy = toY(point.importance);
            const r = bubbleR(point.frequency);
            const color = getSegmentColor(point.segment, segments);
            const isHighlighted = highlightIds.includes(point.id);

            return (
              <g
                key={point.id}
                className="cursor-pointer"
                onClick={() => onPointClick?.(point.id)}
              >
                <circle
                  cx={cx}
                  cy={cy}
                  r={r}
                  fill={color}
                  fillOpacity={isHighlighted ? 0.9 : 0.6}
                  stroke={isHighlighted ? "#fff" : "none"}
                  strokeWidth={isHighlighted ? 0.4 : 0}
                />
                {isHighlighted && (
                  <text
                    x={cx}
                    y={cy - r - 1.5}
                    textAnchor="middle"
                    fill="var(--text-primary)"
                    fontSize="2.5"
                  >
                    {point.label.length > 20
                      ? point.label.substring(0, 18) + "..."
                      : point.label}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Top opportunities list */}
      {scoredPoints.length > 0 && (
        <div className="mt-3 pt-2 border-t border-[var(--border)]">
          <p className="text-[9px] font-semibold uppercase text-[var(--text-muted)] mb-1.5">
            Top Opportunities
          </p>
          <div className="space-y-1">
            {scoredPoints
              .sort((a, b) => b.opportunityScore - a.opportunityScore)
              .slice(0, 5)
              .map((point) => (
                <div
                  key={point.id}
                  className="flex items-center gap-2 cursor-pointer hover:bg-[var(--bg-primary)] rounded px-1.5 py-0.5 transition-colors"
                  onClick={() => onPointClick?.(point.id)}
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: getSegmentColor(point.segment, segments) }}
                  />
                  <span className="text-[10px] text-[var(--text-primary)] truncate flex-1">
                    {point.label}
                  </span>
                  <span className="text-[9px] font-mono text-[var(--text-muted)] shrink-0">
                    I:{point.importance.toFixed(1)} S:{point.satisfaction.toFixed(1)}
                  </span>
                  <span className="text-[9px] font-mono font-medium text-amber-400 shrink-0">
                    {point.opportunityScore.toFixed(1)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
