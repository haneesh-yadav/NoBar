import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { TrustReport } from '../components/TrustReport';
import { AudioPlayer } from '../components/AudioPlayer';
import { FileText, ArrowLeft, Globe, AlertTriangle, Layers, BookOpen } from 'lucide-react';

interface DocumentDetail {
  document_id: string;
  title: string;
  status: string;
  category: string;
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
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'simplified' | 'original' | 'ledger'>('simplified');

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

  // Get requested language version, fallback to English if not present
  const currentVersion =
    doc.versions.find((v) => v.language === language) ||
    doc.versions.find((v) => v.language === 'en') ||
    doc.versions[0];

  const isTranslated = language !== 'en';

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Back Button & Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Link to="/library" className="inline-flex items-center gap-2 text-slate-400 hover:text-slate-200 text-sm">
          <ArrowLeft className="w-4 h-4" /> Back to Scheme Library
        </Link>

        {/* Language Version Selector */}
        <div className="flex items-center gap-2 bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-700">
          <Globe className="w-4 h-4 text-blue-400" />
          <span className="text-xs text-slate-300">View Language:</span>
          <div className="flex items-center gap-1">
            {['en', 'hi', 'ta'].map((lang) => (
              <button
                key={lang}
                onClick={() => setLanguage(lang)}
                className={`px-2.5 py-1 rounded text-xs font-bold transition ${
                  language === lang
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                {lang.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Document Title Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold text-blue-400 uppercase tracking-wider">
          <FileText className="w-4 h-4" /> {doc.category.replace('_', ' ')}
        </div>
        <h1 className="text-2xl font-extrabold text-slate-100">{doc.title}</h1>

        {isTranslated && (
          <div className="mt-2 inline-flex items-center gap-1.5 bg-amber-950/80 border border-amber-800 text-amber-300 text-xs px-3 py-1 rounded">
            <AlertTriangle className="w-3.5 h-3.5" />
            Machine-translated to {language.toUpperCase()}. Fact ledger values preserved.
          </div>
        )}
      </div>

      {/* Audio Narration Component */}
      <AudioPlayer documentId={doc.document_id} language={language} transcriptText={currentVersion?.plain_text} />

      {/* View Tabs */}
      <div className="space-y-4">
        <div className="flex border-b border-slate-800" role="tablist" aria-label="Document view modes">
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
    </div>
  );
};
