import React from "react";
import { CheckCircle2, XCircle, ShieldCheck, ShieldAlert } from "lucide-react";

export interface MacroCheckItem {
  id: string; // M1..M8
  name: string;
  passed: boolean;
  detail: string;
}

export interface MacroChecklistProps {
  passed: boolean;
  checks: MacroCheckItem[];
  blockedBy?: string[];
}

export const MacroChecklist: React.FC<MacroChecklistProps> = ({
  passed,
  checks,
  blockedBy = [],
}) => {
  return (
    <div className="p-4 rounded-xl bg-surface border border-border shadow-sm space-y-3">
      {/* Header with Status Badge */}
      <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
        <div className="flex items-center gap-2">
          {passed ? (
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          ) : (
            <ShieldAlert className="w-4 h-4 text-amber-500" />
          )}
          <h3 className="text-sm font-bold text-fg tracking-wide">
            Macro Filter (M1–M8)
          </h3>
        </div>
        <span
          className={`px-2 py-0.5 rounded text-xs font-bold font-mono border ${
            passed
              ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
              : "bg-amber-500/15 border-amber-500/30 text-amber-500"
          }`}
        >
          {passed ? "✓ SEMUA LOLOS" : `⚠ ${blockedBy.length} TERBLOKIR`}
        </span>
      </div>

      {/* Checklist Grid */}
      <div className="space-y-2">
        {checks.map((chk) => (
          <div
            key={chk.id}
            className={`p-2.5 rounded-lg border transition-colors ${
              chk.passed
                ? "bg-surface-2/30 border-border/60 hover:border-border"
                : "bg-rose-500/10 border-rose-500/30"
            }`}
          >
            <div className="flex items-start gap-2">
              <span className="flex-shrink-0 mt-0.5">
                {chk.passed ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <XCircle className="w-4 h-4 text-rose-500" />
                )}
              </span>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-1">
                  <span className="text-xs font-bold text-fg">
                    <span className="font-mono text-accent mr-1.5">{chk.id}</span>
                    {chk.name}
                  </span>
                  <span
                    className={`text-[10px] font-mono font-bold uppercase ${
                      chk.passed ? "text-emerald-400" : "text-rose-400"
                    }`}
                  >
                    {chk.passed ? "Lolos" : "Gagal"}
                  </span>
                </div>
                <p className="text-[11px] text-muted leading-tight mt-0.5">
                  {chk.detail}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
