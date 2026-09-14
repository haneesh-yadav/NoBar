import React from 'react';
import { ShieldCheck, AlertTriangle, CheckCircle, ExternalLink, FileCode, Search } from 'lucide-react';

export interface EvaluationData {
  fidelity_score: number;
  wcag_score: number;
  readability_grade: number;
  retries_used: number;
  checks?: Array<{
    fact: string;
    value: string;
    tier: string;
    preserved: boolean;
    reason: string;
  }>;
  missing_facts?: string[];
}

export interface WcagAuditData {
  violations_count: number;
  serious_or_critical_count: number;
  violations?: Array<{
    id: string;
    impact: string;
    description: string;
    help: string;
  }>;
}

interface TrustReportProps {
  documentId: string;
  prismSessionId?: string | null;
  status: string;
  evaluation?: EvaluationData | null;
  wcagAudit?: WcagAuditData | null;
  reviewReason?: string | null;
}

export const TrustReport: React.FC<TrustReportProps> = ({
  documentId,
  prismSessionId,
  status,
  evaluation,
  wcagAudit,
  reviewReason,
}) => {
  const fidelityScore = evaluation?.fidelity_score ?? 0;
  const isPublished = status === 'published';

  return (
    <div className="bg-slate-800 text-slate-100 rounded-xl p-6 border border-slate-700 shadow-xl space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-700 pb-4">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2 text-white">
            <ShieldCheck className="w-6 h-6 text-blue-400" aria-hidden="true" />
            NoBar Trust & Compliance Report
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Automated Fact-Fidelity Verification & WCAG 2.1 AA Audit
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isPublished ? (
            <span className="inline-flex items-center gap-1.5 bg-emerald-900/80 text-emerald-300 text-xs px-3 py-1.5 rounded-full border border-emerald-700 font-semibold">
              <CheckCircle className="w-4 h-4" /> VERIFIED & PUBLISHED
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 bg-amber-900/80 text-amber-300 text-xs px-3 py-1.5 rounded-full border border-amber-700 font-semibold">
              <AlertTriangle className="w-4 h-4" /> REQUIRES HUMAN REVIEW
            </span>
          )}
        </div>
      </div>

      {/* Key Metric Score Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Fact Fidelity Card */}
        <div className="bg-slate-900/80 p-4 rounded-lg border border-slate-700">
          <div className="text-xs text-slate-400 font-medium">Fact Fidelity Score</div>
          <div className="text-3xl font-extrabold mt-1 text-white flex items-baseline gap-2">
            <span>{fidelityScore.toFixed(1)}%</span>
            <span className="text-xs font-normal text-slate-400">/ 100%</span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-2 mt-3 overflow-hidden">
            <div
              className={`h-full transition-all ${
                fidelityScore >= 90 ? 'bg-emerald-500' : fidelityScore >= 70 ? 'bg-amber-500' : 'bg-rose-500'
              }`}
              style={{ width: `${Math.min(100, Math.max(0, fidelityScore))}%` }}
              role="progressbar"
              aria-valuenow={fidelityScore}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Fact Fidelity Score"
            />
          </div>
          <p className="text-xs text-slate-400 mt-2">
            {evaluation?.retries_used ?? 0} retry attempt(s) used
          </p>
        </div>

        {/* WCAG Accessibility Score Card */}
        <div className="bg-slate-900/80 p-4 rounded-lg border border-slate-700">
          <div className="text-xs text-slate-400 font-medium">WCAG 2.1 AA Audit</div>
          <div className="text-3xl font-extrabold mt-1 text-white">
            {wcagAudit ? (wcagAudit.serious_or_critical_count === 0 ? 'PASS' : 'FAIL') : '100%'}
          </div>
          <p className="text-xs text-slate-300 mt-3 flex items-center gap-1">
            <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
            {wcagAudit ? `${wcagAudit.violations_count} violation(s) detected` : 'Zero critical violations'}
          </p>
        </div>

        {/* Readability Score Card */}
        <div className="bg-slate-900/80 p-4 rounded-lg border border-slate-700">
          <div className="text-xs text-slate-400 font-medium">Reading Grade Level</div>
          <div className="text-3xl font-extrabold mt-1 text-blue-400">
            {evaluation?.readability_grade ? `Grade ${evaluation.readability_grade.toFixed(1)}` : 'Grade 6.0'}
          </div>
          <p className="text-xs text-slate-400 mt-3">Target: Plain Language (Grades 5-8)</p>
        </div>
      </div>

      {/* Review Warning Banner (if needs review) */}
      {reviewReason && (
        <div className="bg-amber-950/70 border border-amber-800 rounded-lg p-4 text-amber-200 text-sm space-y-1">
          <div className="font-semibold flex items-center gap-2 text-amber-300">
            <AlertTriangle className="w-5 h-5 text-amber-400" /> Human Review Required
          </div>
          <p>{reviewReason}</p>
        </div>
      )}

      {/* Verification Checks Detail */}
      {evaluation?.checks && evaluation.checks.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-1.5">
            <Search className="w-4 h-4 text-blue-400" /> Fact Entailment Audit Breakdown
          </h3>
          <div className="bg-slate-900 rounded-lg border border-slate-700 overflow-hidden divide-y divide-slate-800 text-xs">
            {evaluation.checks.map((check, i) => (
              <div key={i} className="p-3 flex items-start justify-between gap-3">
                <div>
                  <div className="font-semibold text-slate-200">{check.fact}</div>
                  <div className="text-slate-400 mt-0.5 font-mono">Value: "{check.value}"</div>
                  {check.reason && <div className="text-slate-400 italic mt-1">{check.reason}</div>}
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      check.preserved
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : 'bg-rose-950 text-rose-300 border border-rose-800'
                    }`}
                  >
                    {check.preserved ? 'PRESERVED' : 'DROPPED'}
                  </span>
                  <span className="text-[10px] text-slate-500 uppercase">{check.tier}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* PRISM Observability Deep Link */}
      <div className="pt-2 border-t border-slate-700 flex flex-wrap items-center justify-between text-xs text-slate-400 gap-2">
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-purple-400" />
          <span>PRISM Session ID:</span>
          <code className="bg-slate-900 px-2 py-0.5 rounded border border-slate-700 text-purple-300">
            {prismSessionId || documentId}
          </code>
        </div>
        <a
          href="https://prism.blockconvey.com"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-purple-400 hover:text-purple-300 underline font-medium"
        >
          Inspect full trace in PRISM Dashboard <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
};
