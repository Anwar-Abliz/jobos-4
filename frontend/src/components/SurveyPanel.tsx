"use client";

import { ClipboardList } from "lucide-react";

interface OutcomeStatement {
  id: string;
  statement: string;
  tier?: string;
}

type LikertValue = 1 | 2 | 3 | 4 | 5;

interface SurveyResponse {
  outcomeId: string;
  importance: LikertValue;
  satisfaction: LikertValue;
}

interface SurveyPanelProps {
  title: string;
  description?: string;
  outcomes: OutcomeStatement[];
  responses: SurveyResponse[];
  onResponseChange?: (outcomeId: string, dimension: "importance" | "satisfaction", value: LikertValue) => void;
  readOnly?: boolean;
}

const LIKERT_LABELS: Record<"importance" | "satisfaction", string[]> = {
  importance: ["Not at all", "Slightly", "Moderately", "Very", "Extremely"],
  satisfaction: ["Not at all", "Slightly", "Moderately", "Very", "Extremely"],
};

function LikertCell({
  value,
  selected,
  readOnly,
  onClick,
}: {
  value: LikertValue;
  selected: boolean;
  readOnly?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      disabled={readOnly}
      onClick={onClick}
      className={`w-7 h-7 rounded-full text-[10px] font-medium transition-colors ${
        selected
          ? "bg-[var(--accent)] text-white"
          : readOnly
          ? "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
          : "bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:bg-[var(--accent)]/20 hover:text-[var(--text-secondary)]"
      }`}
    >
      {value}
    </button>
  );
}

export function SurveyPanel({
  title,
  description,
  outcomes,
  responses,
  onResponseChange,
  readOnly = false,
}: SurveyPanelProps) {
  const getResponse = (outcomeId: string): SurveyResponse | undefined =>
    responses.find((r) => r.outcomeId === outcomeId);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
      <div className="flex items-center gap-2 mb-1">
        <ClipboardList className="w-3.5 h-3.5 text-[var(--text-muted)]" />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          {title}
        </h3>
      </div>
      {description && (
        <p className="text-[10px] text-[var(--text-muted)] mb-4 leading-relaxed">{description}</p>
      )}

      {/* Table header */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="text-left text-[9px] font-semibold uppercase text-[var(--text-muted)] pb-2 pr-4 min-w-[200px]">
                Outcome
              </th>
              <th
                colSpan={5}
                className="text-center text-[9px] font-semibold uppercase text-[var(--text-muted)] pb-1"
              >
                Importance
              </th>
              <th className="w-4" />
              <th
                colSpan={5}
                className="text-center text-[9px] font-semibold uppercase text-[var(--text-muted)] pb-1"
              >
                Satisfaction
              </th>
            </tr>
            <tr>
              <th />
              {LIKERT_LABELS.importance.map((label, i) => (
                <th
                  key={`imp-${i}`}
                  className="text-center text-[8px] text-[var(--text-muted)] pb-2 px-0.5 font-normal"
                >
                  {label}
                </th>
              ))}
              <th />
              {LIKERT_LABELS.satisfaction.map((label, i) => (
                <th
                  key={`sat-${i}`}
                  className="text-center text-[8px] text-[var(--text-muted)] pb-2 px-0.5 font-normal"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {outcomes.map((outcome) => {
              const resp = getResponse(outcome.id);
              return (
                <tr
                  key={outcome.id}
                  className="border-t border-[var(--border)] hover:bg-[var(--bg-primary)] transition-colors"
                >
                  <td className="py-2 pr-4">
                    <div className="flex items-baseline gap-1.5">
                      {outcome.tier && (
                        <span className="text-[8px] text-[var(--text-muted)] shrink-0 uppercase font-medium">
                          {outcome.tier}
                        </span>
                      )}
                      <span className="text-[11px] text-[var(--text-primary)] leading-snug">
                        {outcome.statement}
                      </span>
                    </div>
                  </td>

                  {/* Importance Likert */}
                  {([1, 2, 3, 4, 5] as LikertValue[]).map((val) => (
                    <td key={`imp-${val}`} className="text-center py-2 px-0.5">
                      <LikertCell
                        value={val}
                        selected={resp?.importance === val}
                        readOnly={readOnly}
                        onClick={() => onResponseChange?.(outcome.id, "importance", val)}
                      />
                    </td>
                  ))}

                  {/* Separator */}
                  <td className="w-4">
                    <div className="w-px h-5 bg-[var(--border)] mx-auto" />
                  </td>

                  {/* Satisfaction Likert */}
                  {([1, 2, 3, 4, 5] as LikertValue[]).map((val) => (
                    <td key={`sat-${val}`} className="text-center py-2 px-0.5">
                      <LikertCell
                        value={val}
                        selected={resp?.satisfaction === val}
                        readOnly={readOnly}
                        onClick={() => onResponseChange?.(outcome.id, "satisfaction", val)}
                      />
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="flex gap-4 mt-3 pt-2 border-t border-[var(--border)]">
        <span className="text-[10px] text-[var(--text-muted)]">
          {outcomes.length} outcome{outcomes.length !== 1 ? "s" : ""}
        </span>
        <span className="text-[10px] text-[var(--text-muted)]">
          {responses.length}/{outcomes.length * 2} ratings completed
        </span>
      </div>
    </div>
  );
}
