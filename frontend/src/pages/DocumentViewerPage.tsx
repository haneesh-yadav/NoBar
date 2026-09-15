import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { TrustReport } from '../components/TrustReport';
import { AudioPlayer } from '../components/AudioPlayer';
import { AssistantPanel } from '../components/AssistantPanel';
import {
  FileText,
  ArrowLeft,
  Globe,
  AlertTriangle,
  Layers,
  BookOpen,
  ExternalLink,
  Bookmark,
  CheckCircle,
  LogIn,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../lib/api';

interface DocumentDetail {
  document_id: string;
  title: string;
  status: string;
  category: string;
  scheme_url?: string;
  prism_session_id?: string;
  fact_ledger?: any;
  versions: Array<{
    language: string;
    plain_text: string;
    html_output?: string;
    audio_path?: string;
    reading_grade?: number;
  }>;
  evaluation?: any;
  wcag_audit?: any;
  review_reason?: string;
}

export const DocumentViewerPage: React.FC<{ language: string; setLanguage: (lang: string) => void }> = ({
  language,
  setLanguage,
}) => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'simplified' | 'original' | 'ledger'>('simplified');
  const [saved, setSaved] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetch(`/api/documents/${id}`)
      .then((res) => {
        if (!res.ok) throw new Error('Document not found');
        return res.json();
      })
      .then((data) => {
        setDoc(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [id]);

  useEffect(() => {
    if (!id || !user) {
      setSaved(false);
      return;
    }
    apiFetch<{ saved: boolean }>(`/api/users/me/schemes/${id}/saved-status`)
      .then((r) => setSaved(r.saved))
      .catch(() => setSaved(false));
  }, [id, user]);

  const handleSave = async () => {
    if (!user) return;
    setActionMsg(null);
    try {
      if (saved) {
        await apiFetch(`/api/users/me/schemes/${id}/save`, { method: 'DELETE' });
        setSaved(false);
        setActionMsg('Removed from your saved schemes.');
      } else {
        await apiFetch(`/api/users/me/schemes/${id}/save`, { method: 'POST' });
        setSaved(true);
        setActionMsg('Saved — find it under "Saved Schemes" in your profile.');
      }
    } catch (err: any) {
      setActionMsg(`Action failed: ${err?.message || 'unknown error'}`);
    }
    setTimeout(() => setActionMsg(null), 3000);
  };

  const handleApply = async () => {
    if (!user) return;
    setActionMsg(null);
    try {
      const res = await apiFetch<{ status: string; official_url: string }>(
        `/api/users/me/schemes/${id}/apply`,
        { method: 'POST' },
      );
      setActionMsg(
        `Application intent recorded (${res.status}). Redirecting to the official portal to complete your submission...`,
      );
      if (res.official_url) {
        setTimeout(() => window.open(res.official_url, '_blank', 'noopener,noreferrer'), 800);
      }
    } catch (err: any) {
      setActionMsg(`Apply failed: ${err?.message || 'unknown error'}`);
    }
    setTimeout(() => setActionMsg(null), 4500);
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center text-slate-400">
        <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
        Loading scheme accessibility report...
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center text-rose-300">
        <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto mb-3" />
        <h2 className="text-xl font-bold">Error Loading Document</h2>
        <p className="text-slate-400 mt-1">{error || 'Unable to retrieve document details'}</p>
        <Link to="/library" className="inline-block mt-4 text-blue-400 hover:underline">
          Return to Scheme Library
        </Link>
      </div>
    );
  }

  // Language versions actually present for this document.
  const availableLanguages = doc.versions.map((v) => v.language);
  const effectiveLanguage = availableLanguages.includes(language) ? language : 'en';

  // Get requested language version, English always as a fallback.
  const currentVersion =
    doc.versions.find((v) => v.language === effectiveLanguage) ||
    doc.versions.find((v) => v.language === 'en') ||
    doc.versions[0];

  const isTranslated = effectiveLanguage !== 'en' && availableLanguages.includes(effectiveLanguage);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Back Button & Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Link to="/library" className="inline-flex items-center gap-2 text-slate-400 hover:text-slate-200 text-sm">
          <ArrowLeft className="w-4 h-4" /> Back to Scheme Library
        </Link>

        {/* Action buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {doc.scheme_url && (
            <a
              href={doc.scheme_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-lg text-xs font-bold transition"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Apply on Official Site
            </a>
          )}

          {user ? (
            <>
              <button
                onClick={handleSave}
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold border transition ${
                  saved
                    ? 'bg-blue-600 text-white border-blue-500'
                    : 'bg-slate-800 text-slate-200 border-slate-600 hover:bg-slate-700'
                }`}
              >
                {saved ? <CheckCircle className="w-3.5 h-3.5" /> : <Bookmark className="w-3.5 h-3.5" />}
                {saved ? 'Saved' : 'Save Scheme'}
              </button>
              <button
                onClick={handleApply}
                className="inline-flex items-center gap-2 bg-amber-600 hover:bg-amber-500 text-white px-3 py-1.5 rounded-lg text-xs font-bold transition"
              >
                <ExternalLink className="w-3.5 h-3.5" /> Apply
              </button>
            </>
          ) : (
            <Link
              to="/auth/login"
              className="inline-flex items-center gap-2 bg-slate-800 text-slate-200 border border-slate-600 px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-slate-700 transition"
            >
              <LogIn className="w-3.5 h-3.5" /> Sign in to save & apply
            </Link>
          )}

          {/* Language Version Selector */}
          <div className="flex items-center gap-2 bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-700">
            <Globe className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-slate-300">View Language:</span>
            <div className="flex items-center gap-1">
              {['en', 'hi', 'ta'].map((lang) => {
                const available = availableLanguages.includes(lang) || lang === 'en';
                const active = effectiveLanguage === lang;
                return (
                  <button
                    key={lang}
                    disabled={!available}
                    onClick={() => setLanguage(lang)}
                    title={available ? '' : `Not translated to ${lang.toUpperCase()} yet`}
                    aria-pressed={active}
                    className={`px-2.5 py-1 rounded text-xs font-bold transition ${
                      !available
                        ? 'bg-slate-900 text-slate-600 cursor-not-allowed line-through'
                        : active
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {lang.toUpperCase()}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {actionMsg && (
        <div className="bg-slate-800 border border-slate-700 text-slate-200 px-4 py-3 rounded-lg text-sm">{actionMsg}</div>
      )}

      {/* Document Title Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-blue-400 uppercase tracking-wider">
            <FileText className="w-4 h-4" /> {doc.category.replace('_', ' ')}
          </div>
          {doc.scheme_url && (
            <a
              href={doc.scheme_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs font-bold text-emerald-400 hover:text-emerald-300"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Official Scheme Page
            </a>
          )}
        </div>
        <h1 className="text-2xl font-extrabold text-slate-100">{doc.title}</h1>

        {isTranslated && (
          <div className="mt-2 inline-flex items-center gap-1.5 bg-amber-950/80 border border-amber-800 text-amber-300 text-xs px-3 py-1 rounded">
            <AlertTriangle className="w-3.5 h-3.5" />
            Machine-translated to {effectiveLanguage.toUpperCase()}. Fact ledger values preserved.
          </div>
        )}
      </div>

      {/* Audio Narration Component */}
      <AudioPlayer
        documentId={doc.document_id}
        language={effectiveLanguage}
        transcriptText={currentVersion?.plain_text}
        hasRecording={Boolean(currentVersion?.audio_path)}
      />

      {/* View Tabs */}
      <div className="space-y-4">
        <div className="flex border-b border-slate-800 flex-wrap" role="tablist" aria-label="Document view modes">
          <button
            role="tab"
            aria-selected={activeTab === 'simplified'}
            onClick={() => setActiveTab('simplified')}
            className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
              activeTab === 'simplified'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <BookOpen className="w-4 h-4" /> Simplified Plain Language (WCAG 2.1 AA)
          </button>

          <button
            role="tab"
            aria-selected={activeTab === 'ledger'}
            onClick={() => setActiveTab('ledger')}
            className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
              activeTab === 'ledger'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-4 h-4" /> Extracted Fact Ledger
          </button>
        </div>

        {/* Tab Contents */}
        {activeTab === 'simplified' && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-xl text-slate-200 prose prose-invert max-w-none leading-relaxed space-y-4">
            {currentVersion?.html_output ? (
              <div
                dangerouslySetInnerHTML={{ __html: currentVersion.html_output }}
                className="w-full space-y-4"
              />
            ) : (
              <div className="whitespace-pre-wrap text-base">{currentVersion?.plain_text}</div>
            )}
          </div>
        )}

        {activeTab === 'ledger' && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-slate-300">Structured Fact Ledger (Pydantic Extracted)</h3>
            <pre className="bg-slate-950 p-4 rounded-lg text-xs font-mono text-emerald-400 overflow-x-auto border border-slate-800">
              {JSON.stringify(doc.fact_ledger, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Trust & Compliance Report Section */}
      <TrustReport
        documentId={doc.document_id}
        prismSessionId={doc.prism_session_id}
        status={doc.status}
        evaluation={doc.evaluation}
        wcagAudit={doc.wcag_audit}
        reviewReason={doc.review_reason}
      />

      {/* AI citizen assistant */}
      <AssistantPanel documentId={doc.document_id} documentTitle={doc.title} language={effectiveLanguage} />
    </div>
  );
};