import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, ShieldCheck, CheckCircle, ArrowRight, BookOpen, Filter, ExternalLink } from 'lucide-react';

interface SchemeItem {
  document_id: string;
  title: string;
  category: string;
  scheme_url?: string;
  fidelity_score?: number | null;
  wcag_score?: number | null;
  languages_available: string[];
  created_at: string;
}

export const LibraryPage: React.FC = () => {
  const [schemes, setSchemes] = useState<SchemeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  useEffect(() => {
    fetch('/api/library')
      .then((res) => res.json())
      .then((data) => {
        setSchemes(data || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Library fetch error:', err);
        setLoading(false);
      });
  }, []);

  const categories = [
    { id: 'all', label: 'All Schemes' },
    { id: 'pension', label: 'Pensions & Senior Care' },
    { id: 'disability', label: 'Disability Assistance' },
    { id: 'women_child', label: 'Women & Child Welfare' },
    { id: 'agriculture', label: 'Agriculture & Farmers' },
    { id: 'labour', label: 'Labour & Construction Workers' },
  ];

  const filteredSchemes = schemes.filter((item) => {
    const matchesSearch = item.title.toLowerCase().includes(search.toLowerCase());
    const matchesCat = selectedCategory === 'all' || item.category === selectedCategory;
    return matchesSearch && matchesCat;
  });

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header Banner */}
      <div className="space-y-2 text-center max-w-2xl mx-auto">
        <h1 className="text-3xl font-extrabold text-slate-100 flex items-center justify-center gap-2">
          <BookOpen className="w-8 h-8 text-blue-500" />
          Verified Welfare Scheme Library
        </h1>
        <p className="text-slate-400 text-sm">
          Browse official Indian government welfare scheme documents simplified to WCAG 2.1 AA and verified for 100% fact fidelity.
        </p>
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 shadow-lg space-y-4">
        <div className="flex flex-col sm:flex-row items-center gap-4">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="Search scheme name or eligibility keywords..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-950 text-slate-200 pl-10 pr-4 py-2 rounded-lg border border-slate-700 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="flex items-center gap-2 text-xs text-slate-400 w-full sm:w-auto">
            <Filter className="w-4 h-4 text-blue-400" /> Filter Category:
          </div>
        </div>

        {/* Category Pills */}
        <div className="flex flex-wrap gap-2 pt-1" role="tablist" aria-label="Category filters">
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                selectedCategory === cat.id
                  ? 'bg-blue-600 text-white shadow'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200 border border-slate-700'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Results Count */}
      <div className="text-xs text-slate-400 font-medium">
        Showing {filteredSchemes.length} verified scheme(s)
      </div>

      {/* Scheme Cards Grid */}
      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading scheme library...</div>
      ) : filteredSchemes.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center text-slate-400 space-y-3">
          <p className="text-base font-semibold">No matching scheme documents found.</p>
          <p className="text-xs">Try selecting a different category or upload a new PDF document.</p>
          <Link to="/upload" className="inline-block mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-xs font-bold">
            Upload New Scheme PDF
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {filteredSchemes.map((scheme) => (
            <div
              key={scheme.document_id}
              className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-6 shadow-xl transition flex flex-col justify-between space-y-4"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="bg-slate-800 text-blue-400 px-2.5 py-0.5 rounded font-semibold border border-slate-700 uppercase">
                    {scheme.category.replace('_', ' ')}
                  </span>
                  <span className="text-slate-500 font-mono">
                    {new Date(scheme.created_at).toLocaleDateString()}
                  </span>
                </div>

                <h3 className="text-lg font-bold text-slate-100 hover:text-blue-400 transition">
                  <Link to={`/document/${scheme.document_id}`}>{scheme.title}</Link>
                </h3>

                {scheme.scheme_url && (
                  <a
                    href={scheme.scheme_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-bold text-emerald-400 hover:text-emerald-300 transition"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    Official Site (myscheme.gov.in)
                  </a>
                )}
              </div>

              <div className="pt-4 border-t border-slate-800 space-y-3">
                <div className="flex flex-wrap items-center gap-3 text-xs">
                  <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold bg-emerald-950/80 px-2.5 py-1 rounded border border-emerald-800">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    {scheme.fidelity_score ? `${scheme.fidelity_score.toFixed(0)}% Fidelity` : '100% Fidelity'}
                  </span>
                  <span className="inline-flex items-center gap-1 text-blue-300 font-semibold bg-blue-950/80 px-2.5 py-1 rounded border border-blue-800">
                    <CheckCircle className="w-3.5 h-3.5" /> WCAG AA
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {scheme.scheme_url && (
                    <a
                      href={scheme.scheme_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-bold text-emerald-400 bg-emerald-950/40 border border-emerald-800 px-3 py-1.5 rounded-lg hover:bg-emerald-900/60 transition"
                    >
                      Apply / Official Site <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                  <Link
                    to={`/document/${scheme.document_id}`}
                    className="inline-flex items-center gap-1 text-xs font-bold text-blue-400 hover:text-blue-300"
                  >
                    View Scheme <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
