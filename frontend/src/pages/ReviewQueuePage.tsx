import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle, XCircle, ExternalLink, ShieldAlert } from 'lucide-react';

interface ReviewEntry {
  id: string;
  document_id: string;
  document_title?: string | null;
  reason: string;
  status: string;
  created_at: string;
}

export const ReviewQueuePage: React.FC = () => {
  const [entries, setEntries] = useState<ReviewEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchQueue = () => {
    fetch('/api/review/queue')
      .then((res) => res.json())
      .then((data) => {
        setEntries(data || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Fetch review queue error:', err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchQueue();
  }, []);

  const handleResolve = async (entryId: string, action: 'approve' | 'reject') => {
    try {
      const res = await fetch(`/api/review/${entryId}/resolve?action=${action}`, {
        method: 'POST',
      });
      if (res.ok) {
        setActionMessage(`Entry ${entryId} successfully resolved (${action}d).`);
        fetchQueue();
      }
    } catch (err) {
      console.error('Resolve error:', err);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      <div className="space-y-2 text-center max-w-xl mx-auto">
        <h1 className="text-3xl font-extrabold text-slate-100 flex items-center justify-center gap-2">
          <ShieldAlert className="w-8 h-8 text-amber-500" />
          Caseworker Review Queue
        </h1>
        <p className="text-slate-400 text-sm">
          Scheme documents flagged by NoBar's 3-tier fact fidelity gate for human auditor verification before publishing.
        </p>
      </div>

      {actionMessage && (
        <div className="bg-emerald-950/80 border border-emerald-800 text-emerald-300 p-3 rounded-lg text-sm text-center">
          {actionMessage}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading review queue...</div>
      ) : entries.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center text-slate-400 space-y-2">
          <CheckCircle className="w-10 h-10 text-emerald-400 mx-auto" />
          <h2 className="text-lg font-bold text-slate-200">Review Queue Empty</h2>
          <p className="text-xs">All processed scheme documents passed fact fidelity verification standards.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {entries.map((entry) => (
            <div
              key={entry.id}
              className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-6"
            >
              <div className="space-y-2 flex-1">
                <div className="flex items-center gap-2 text-xs">
                  <span className="bg-amber-950 text-amber-300 px-2.5 py-0.5 rounded font-bold border border-amber-800">
                    FLAGGED LOW FIDELITY
                  </span>
                  <span className="text-slate-500 font-mono">
                    {new Date(entry.created_at).toLocaleString()}
                  </span>
                </div>

                <h3 className="text-lg font-bold text-slate-100">
                  {entry.document_title || `Document #${entry.document_id}`}
                </h3>

                <div className="bg-slate-950 p-3 rounded border border-slate-800 text-xs text-amber-200 font-mono">
                  Reason: {entry.reason}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <Link
                  to={`/document/${entry.document_id}`}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold border border-slate-700 flex items-center gap-1.5"
                >
                  Inspect <ExternalLink className="w-3.5 h-3.5" />
                </Link>

                <button
                  onClick={() => handleResolve(entry.id, 'approve')}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow"
                >
                  <CheckCircle className="w-4 h-4" /> Approve & Publish
                </button>

                <button
                  onClick={() => handleResolve(entry.id, 'reject')}
                  className="px-4 py-2 bg-rose-900 hover:bg-rose-800 text-rose-200 rounded-lg text-xs font-bold transition flex items-center gap-1.5"
                >
                  <XCircle className="w-4 h-4" /> Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
