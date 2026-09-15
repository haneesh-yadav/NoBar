import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Eye, Type, ShieldCheck, FileText, Upload, AlertCircle, LogIn, UserRound, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface NavbarProps {
  highContrast: boolean;
  setHighContrast: (val: boolean | ((prev: boolean) => boolean)) => void;
  fontSize: string;
  setFontSize: (size: string) => void;
  language: string;
  setLanguage: (lang: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  highContrast,
  setHighContrast,
  fontSize,
  setFontSize,
  language,
  setLanguage,
}) => {
  const location = useLocation();
  const { user, logout } = useAuth();

  const handleFontSizeChange = (delta: 'inc' | 'dec' | 'reset') => {
    if (delta === 'inc') {
      if (fontSize === 'font-size-sm') setFontSize('font-size-md');
      else if (fontSize === 'font-size-md') setFontSize('font-size-lg');
      else if (fontSize === 'font-size-lg') setFontSize('font-size-xl');
    } else if (delta === 'dec') {
      if (fontSize === 'font-size-xl') setFontSize('font-size-lg');
      else if (fontSize === 'font-size-lg') setFontSize('font-size-md');
      else if (fontSize === 'font-size-md') setFontSize('font-size-sm');
    } else {
      setFontSize('font-size-md');
    }
  };

  return (
    <header className="bg-slate-900 text-white shadow-md border-b border-slate-800">
      {/* Top Accessibility Control Bar */}
      <div className="bg-slate-950 px-4 py-2 text-xs flex flex-wrap items-center justify-between gap-2 border-b border-slate-800">
        <div className="flex items-center gap-2" role="toolbar" aria-label="Accessibility settings">
          <span className="font-semibold text-slate-400 flex items-center gap-1">
            <Eye className="w-3.5 h-3.5" aria-hidden="true" /> Accessibility:
          </span>

          {/* High Contrast Toggle */}
          <button
            onClick={() => setHighContrast((prev) => !prev)}
            aria-pressed={highContrast}
            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            {highContrast ? '⚡ High Contrast: ON' : 'High Contrast: OFF'}
          </button>

          {/* Font Size Controls */}
          <div className="flex items-center gap-1 bg-slate-800 rounded px-1 border border-slate-700">
            <span className="text-slate-400 px-1 flex items-center">
              <Type className="w-3 h-3" aria-hidden="true" /> Text Size:
            </span>
            <button
              onClick={() => handleFontSizeChange('dec')}
              aria-label="Decrease text size"
              className="px-1.5 py-0.5 hover:bg-slate-700 rounded text-slate-200 font-bold"
            >
              A-
            </button>
            <button
              onClick={() => handleFontSizeChange('reset')}
              aria-label="Reset text size to default"
              className="px-1.5 py-0.5 hover:bg-slate-700 rounded text-slate-200 font-bold text-xs"
            >
              Reset
            </button>
            <button
              onClick={() => handleFontSizeChange('inc')}
              aria-label="Increase text size"
              className="px-1.5 py-0.5 hover:bg-slate-700 rounded text-slate-200 font-bold"
            >
              A+
            </button>
          </div>
        </div>

        {/* Global Language Toggle */}
        <div className="flex items-center gap-2">
          <label htmlFor="global-lang-select" className="text-slate-400">
            Language:
          </label>
          <select
            id="global-lang-select"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="bg-slate-800 text-white rounded px-2 py-1 text-xs border border-slate-700 cursor-pointer"
          >
            <option value="en">English (Original)</option>
            <option value="hi">हिंदी (Hindi)</option>
            <option value="ta">தமிழ் (Tamil)</option>
          </select>
        </div>
      </div>

      {/* Main Navbar Navigation */}
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold text-blue-400 hover:text-blue-300">
          <ShieldCheck className="w-7 h-7 text-blue-500" aria-hidden="true" />
          <span>NoBar</span>
          <span className="text-xs bg-blue-950 text-blue-400 px-2 py-0.5 rounded border border-blue-800 font-normal">
            AI Accessibility Auditor
          </span>
        </Link>

        <nav aria-label="Main Navigation" className="flex items-center gap-1 sm:gap-4 flex-wrap">
          <Link
            to="/upload"
            className={`flex items-center gap-1.5 px-3 py-2 rounded-md font-medium text-sm transition ${
              location.pathname === '/upload'
                ? 'bg-blue-600 text-white'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <Upload className="w-4 h-4" aria-hidden="true" />
            Upload Document
          </Link>

          <Link
            to="/library"
            className={`flex items-center gap-1.5 px-3 py-2 rounded-md font-medium text-sm transition ${
              location.pathname === '/library' || location.pathname === '/'
                ? 'bg-blue-600 text-white'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <FileText className="w-4 h-4" aria-hidden="true" />
            Scheme Library
          </Link>

          <Link
            to="/review"
            className={`flex items-center gap-1.5 px-3 py-2 rounded-md font-medium text-sm transition ${
              location.pathname === '/review'
                ? 'bg-amber-600 text-white'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <AlertCircle className="w-4 h-4 text-amber-400" aria-hidden="true" />
            Review Queue
          </Link>

          {user ? (
            <div className="flex items-center gap-1.5">
              <Link
                to="/profile"
                className={`flex items-center gap-1.5 px-3 py-2 rounded-md font-medium text-sm transition ${
                  location.pathname === '/profile'
                    ? 'bg-emerald-600 text-white'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
                aria-label="My profile and entitlement report"
              >
                <UserRound className="w-4 h-4 text-emerald-400" aria-hidden="true" />
                <span className="max-w-[120px] truncate">{user.full_name || user.email}</span>
              </Link>
              <button
                onClick={logout}
                title="Sign out"
                aria-label="Sign out"
                className="flex items-center gap-1.5 px-3 py-2 rounded-md font-medium text-sm text-slate-300 hover:bg-slate-800 hover:text-rose-300 transition"
              >
                <LogOut className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
          ) : (
            <Link
              to="/auth/login"
              className={`flex items-center gap-1.5 px-3 py-2 rounded-md font-medium text-sm transition ${
                location.pathname === '/auth/login' || location.pathname === '/auth/register'
                  ? 'bg-emerald-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <LogIn className="w-4 h-4 text-emerald-400" aria-hidden="true" />
              Sign In / Register
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
};
