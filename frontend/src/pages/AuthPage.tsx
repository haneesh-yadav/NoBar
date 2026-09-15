import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogIn, UserPlus, ShieldCheck, AlertTriangle, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const AuthPage: React.FC<{ mode: 'login' | 'register' }> = ({ mode }) => {
  const [isLogin, setIsLogin] = useState<boolean>(mode === 'login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await register(email, password, fullName);
      }
      navigate('/profile', { replace: true });
    } catch (err: any) {
      setError(err?.message || 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const switchMode = (toLogin: boolean) => {
    setIsLogin(toLogin);
    setError(null);
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="p-3 bg-blue-950 rounded-full border border-blue-800 inline-flex text-blue-400 mb-1">
            {isLogin ? <LogIn className="w-7 h-7" /> : <UserPlus className="w-7 h-7" />}
          </div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center justify-center gap-2">
            <ShieldCheck className="w-6 h-6 text-blue-500" />
            {isLogin ? 'Sign In to NoBar' : 'Create Your Profile'}
          </h1>
          <p className="text-xs text-slate-400">
            {isLogin
              ? 'Get your entitlement report, save schemes and apply with one click.'
              : 'Tell us a little about yourself so we can match the right government schemes for you.'}
          </p>
        </div>

        {/* Mode toggle */}
        <div className="flex rounded-lg bg-slate-950 border border-slate-800 p-1 text-xs" role="tablist" aria-label="Authentication mode">
          <button
            role="tab"
            aria-selected={isLogin}
            onClick={() => switchMode(true)}
            className={`flex-1 py-2 rounded-md font-bold transition ${
              isLogin ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Sign In
          </button>
          <button
            role="tab"
            aria-selected={!isLogin}
            onClick={() => switchMode(false)}
            className={`flex-1 py-2 rounded-md font-bold transition ${
              !isLogin ? 'bg-emerald-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <div>
              <label htmlFor="full-name" className="block text-xs font-semibold text-slate-400 mb-1">
                Full Name
              </label>
              <input
                id="full-name"
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Asha Singh"
                className="w-full bg-slate-950 text-slate-200 px-3 py-2.5 rounded-lg border border-slate-700 text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-xs font-semibold text-slate-400 mb-1">
              Email Address
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-slate-950 text-slate-200 px-3 py-2.5 rounded-lg border border-slate-700 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-semibold text-slate-400 mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min. 6 characters"
              className="w-full bg-slate-950 text-slate-200 px-3 py-2.5 rounded-lg border border-slate-700 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          {error && (
            <div className="bg-rose-950/80 border border-rose-800 text-rose-300 p-3 rounded-lg text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className={`w-full py-2.5 rounded-xl font-bold text-white shadow transition flex items-center justify-center gap-2 ${
              submitting
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                : isLogin
                  ? 'bg-blue-600 hover:bg-blue-500'
                  : 'bg-emerald-600 hover:bg-emerald-500'
            }`}
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Please wait...
              </>
            ) : isLogin ? (
              <>
                <LogIn className="w-4 h-4" /> Sign In
              </>
            ) : (
              <>
                <UserPlus className="w-4 h-4" /> Create Account
              </>
            )}
          </button>
        </form>

        <p className="text-[11px] text-slate-500 text-center leading-relaxed">
          Your socio-economic details are used only to match verified government schemes and build your
          personal entitlement report (PDF). You control what you share.
        </p>
      </div>
    </div>
  );
};