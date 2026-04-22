"use client";

import { Shield, ShieldCheck, ShieldAlert, ShieldX } from "lucide-react";

type ComplianceLevel = "compliant" | "warning" | "violation" | "unchecked";

interface PolicyCheck {
  policyName: string;
  status: ComplianceLevel;
  detail?: string;
}

interface GovernanceBadgeProps {
  entityId: string;
  entityLabel: string;
  overallStatus: ComplianceLevel;
  checks: PolicyCheck[];
  compact?: boolean;
}

const COMPLIANCE_STYLES: Record<
  ComplianceLevel,
  { icon: typeof Shield; color: string; bg: string; label: string }
> = {
  compliant: {
    icon: ShieldCheck,
    color: "text-green-400",
    bg: "bg-green-500/10 border-green-500/30",
    label: "Compliant",
  },
  warning: {
    icon: ShieldAlert,
    color: "text-amber-400",
    bg: "bg-amber-500/10 border-amber-500/30",
    label: "Warning",
  },
  violation: {
    icon: ShieldX,
    color: "text-red-400",
    bg: "bg-red-500/10 border-red-500/30",
    label: "Violation",
  },
  unchecked: {
    icon: Shield,
    color: "text-[var(--text-muted)]",
    bg: "bg-[var(--bg-tertiary)] border-[var(--border)]",
    label: "Unchecked",
  },
};

export function GovernanceBadge({
  entityLabel,
  overallStatus,
  checks,
  compact = false,
}: GovernanceBadgeProps) {
  const style = COMPLIANCE_STYLES[overallStatus];
  const Icon = style.icon;

  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium border ${style.bg} ${style.color}`}
        title={`${entityLabel}: ${style.label}`}
      >
        <Icon className="w-3 h-3" />
        {style.label}
      </span>
    );
  }

  return (
    <div className={`rounded-lg border ${style.bg} p-3`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${style.color}`} />
        <div className="min-w-0">
          <span className={`text-[10px] font-semibold uppercase ${style.color}`}>
            {style.label}
          </span>
          <span className="text-[10px] text-[var(--text-muted)] ml-1.5 truncate">
            {entityLabel}
          </span>
        </div>
      </div>

      {checks.length > 0 && (
        <div className="space-y-1">
          {checks.map((check, i) => {
            const checkStyle = COMPLIANCE_STYLES[check.status];
            const CheckIcon = checkStyle.icon;
            return (
              <div key={i} className="flex items-start gap-1.5">
                <CheckIcon className={`w-3 h-3 ${checkStyle.color} shrink-0 mt-0.5`} />
                <div className="min-w-0">
                  <span className="text-[10px] text-[var(--text-primary)]">{check.policyName}</span>
                  {check.detail && (
                    <p className="text-[9px] text-[var(--text-muted)] leading-relaxed">
                      {check.detail}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Summary counts */}
      <div className="flex gap-3 mt-2 pt-1.5 border-t border-[var(--border)]">
        {(["compliant", "warning", "violation"] as ComplianceLevel[]).map((level) => {
          const count = checks.filter((c) => c.status === level).length;
          if (count === 0) return null;
          const s = COMPLIANCE_STYLES[level];
          return (
            <span key={level} className={`text-[9px] font-medium ${s.color}`}>
              {count} {s.label.toLowerCase()}
            </span>
          );
        })}
      </div>
    </div>
  );
}
