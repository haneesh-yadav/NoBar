import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileText, CheckCircle, AlertTriangle, Loader2, ArrowRight } from 'lucide-react';

export const UploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [docId, setDocId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a PDF document to upload.');
      return;
    }

    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/documents/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json();
        throw new Error(errJson.detail || 'Upload failed');
      }

      const data = await res.json();
      setDocId(data.document_id);
      setStatus('processing');
    } catch (err: any) {
      setError(err.message || 'An error occurred during file upload.');
      setUploading(false);
    }
  };

  // Poll status while processing
  useEffect(() => {
    if (!docId || status === 'published' || status === 'needs_review' || status === 'failed') {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/documents/${docId}/status`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data.status);

          if (data.status === 'published' || data.status === 'needs_review') {
            setUploading(false);
            clearInterval(interval);
          } else if (data.status === 'failed') {
            setError('Pipeline processing failed for this document.');
            setUploading(false);
            clearInterval(interval);
          }
        }
      } catch (err) {
        console.error('Status poll error:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [docId, status]);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-extrabold text-slate-100 flex items-center justify-center gap-2">
          <Upload className="w-8 h-8 text-blue-500" aria-hidden="true" />
          Audit & Simplify a Welfare Scheme Document
        </h1>
        <p className="text-slate-400 text-sm max-w-xl mx-auto">
          Upload any official government/NGO PDF scheme document (pension, disability aid, agriculture subsidy).
          NoBar will extract all facts, simplify the text to WCAG 2.1 AA, translate it, and run 3-tier fact fidelity verification.
        </p>
      </div>

      {/* Upload Box */}
      <div className="bg-slate-900 border-2 border-dashed border-slate-700 hover:border-blue-500 rounded-2xl p-8 transition text-center space-y-6 shadow-xl">
        <form onSubmit={handleUpload} className="space-y-6">
          <div className="flex flex-col items-center justify-center space-y-3">
            <div className="p-4 bg-blue-950 rounded-full border border-blue-800 text-blue-400">
              <FileText className="w-10 h-10" />
            </div>
            <div>
              <label htmlFor="file-upload" className="block text-slate-200 font-semibold text-base cursor-pointer hover:text-blue-400">
                Choose a PDF document or drag it here
              </label>
              <input
                id="file-upload"
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="hidden"
              />
              <span className="text-xs text-slate-400 mt-1 block">Supports official myscheme.gov.in and text PDFs</span>
            </div>
          </div>

          {file && (
            <div className="inline-flex items-center gap-2 bg-slate-800 text-slate-200 px-4 py-2 rounded-lg border border-slate-700 text-sm font-medium">
              <FileText className="w-4 h-4 text-blue-400" />
              <span>{file.name}</span>
              <span className="text-xs text-slate-400">({(file.size / 1024).toFixed(0)} KB)</span>
            </div>
          )}

          {error && (
            <div className="bg-rose-950/80 border border-rose-800 text-rose-300 p-3 rounded-lg text-sm flex items-center justify-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <button
              type="submit"
              disabled={uploading || !file}
              className={`px-6 py-3 rounded-xl font-bold text-white shadow-lg transition flex items-center justify-center gap-2 mx-auto ${
                uploading || !file
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                  : 'bg-blue-600 hover:bg-blue-500 cursor-pointer'
              }`}
            >
              {uploading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin text-white" />
                  <span>Processing Pipeline...</span>
                </>
              ) : (
                <>
                  <Upload className="w-5 h-5" />
                  <span>Start Accessibility Audit</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Live Pipeline Status Tracker */}
      {docId && (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 space-y-4 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
              <Loader2 className={`w-5 h-5 text-blue-400 ${status === 'processing' ? 'animate-spin' : ''}`} />
              Pipeline Execution Status
            </h2>
            <span className="text-xs font-mono text-slate-400">ID: {docId}</span>
          </div>

          <div className="space-y-3">
            {/* Stages */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3 bg-slate-950 rounded border border-slate-800 flex items-center gap-2 text-emerald-400">
                <CheckCircle className="w-4 h-4" /> 1. Ingest PDF & Clean
              </div>
              <div className="p-3 bg-slate-950 rounded border border-slate-800 flex items-center gap-2 text-emerald-400">
                <CheckCircle className="w-4 h-4" /> 2. Extract FactLedger
              </div>
              <div className="p-3 bg-slate-950 rounded border border-slate-800 flex items-center gap-2 text-emerald-400">
                <CheckCircle className="w-4 h-4" /> 3. Simplify to Plain Language
              </div>
              <div className="p-3 bg-slate-950 rounded border border-slate-800 flex items-center gap-2 text-emerald-400">
                <CheckCircle className="w-4 h-4" /> 4. 3-Tier Fact Fidelity Gate
              </div>
            </div>

            {status === 'processing' && (
              <p className="text-sm text-slate-400 text-center py-2 animate-pulse">
                Analyzing criteria thresholds, running verifier checks, and formatting WCAG HTML...
              </p>
            )}

            {(status === 'published' || status === 'needs_review') && (
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-800">
                <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
                  <CheckCircle className="w-5 h-5" />
                  <span>Audit Complete! Result: {status.toUpperCase()}</span>
                </div>
                <button
                  onClick={() => navigate(`/document/${docId}`)}
                  className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-bold text-sm transition flex items-center gap-2 shadow"
                >
                  <span>View Simplified Scheme & Trust Report</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
