import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LogIn,
  UserPlus,
  ShieldCheck,
  AlertTriangle,
  Loader2,
  Fingerprint,
  KeyRound,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../lib/api';

type Tab = 'login' | 'register' | 'aadhaar';

interface OtpInfo {
  otp: string;
  demo: boolean;
  masked_aadhaar: string;
  registered: boolean;
  details?: {
    full_name?: string;
    dob?: string;
    gender?: string;
    state?: string;
    district?: string;
    pincode?: string;
  };
}

const DEMO_AADHAARS = ['1111 2222 3333', '2222 2222 2222', '3333 3333 3333', '4444 4444 4444'];

const tabCls = 'flex-1 py-2 rounded-md font-bold transition flex items-center justify-center gap-1.5';

export const AuthPage: React.FC<{ mode: 'login' | 'register' }> = ({ mode }) => {
  const [tab, setTab] = useState<Tab>(mode === 'login' ? 'login' : 'register');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [aadhaarOptional, setAadhaarOptional] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Aadhaar OTP state
  const [aadhaar, setAadhaar] = useState('');
  const [otp, setOtp] = useState('');
  const [otpInfo, setOtpInfo] = useState<OtpInfo | null>(null);
  const [sendingOtp, setSendingOtp] = useState(false);

  const { login, register, loginWithAadhaar } = useAuth();
  const navigate = useNavigate();

  const formatAadhaar = (value: string) => {
    const digits = value.replace(/\D/g, '').slice(0, 12);
    return digits.replace(/(\d{4})(?=\d)/g, '$1 ');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      if (tab === 'login') {
        await login(email, password);
      } else {
        await register(email, password, fullName, aadhaarOptional.replace(/\D/g, ''));
      }
      navigate('/profile', { replace: true });
    } catch (err: any) {
      setError(err?.message || 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSendOtp = async () => {
    setError(null);
    setNotice(null);
    setOtpInfo(null);
    setSendingOtp(true);
    try {
      const info = await apiFetch<OtpInfo>('/api/auth/aadhaar/request-otp', {
        method: 'POST',
        body: JSON.stringify({ aadhaar: aadhaar.replace(/\D/g, '') }),
      });
      setOtpInfo(info);
    } catch (err: any) {
      setError(err?.message || 'Could not send OTP. Check the Aadhaar number.');
    } finally {
      setSendingOtp(false);
    }
  };

  const handleAadhaarLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      const masked = otpInfo?.masked_aadhaar ?? 'Aadhaar';
      const created = await loginWithAadhaar(aadhaar.replace(/\D/g, ''), otp.trim());
      setNotice(
        created
          ? `Profile created from Aadhaar (${masked}). Redirecting to your report...`
          : `Signed in via Aadhaar (${masked}). Redirecting to your report...`,
      );
      setTimeout(() => navigate('/profile', { replace: true }), 900);
    } catch (err: any) {
      setError(err?.message || 'Aadhaar login failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const switchTab = (next: Tab) => {
    setTab(next);
    setError(null);
    setNotice(null);
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="p-3 bg-blue-950 rounded-full border border-blue-800 inline-flex text-blue-400 mb-1">
            {tab === 'aadhaar' ? (
              <Fingerprint className="w-7 h-7" />
            ) : tab === 'login' ? (
              <LogIn className="w-7 h-7" />
            ) : (
              <UserPlus className="w-7 h-7" />
            )}
          </div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center justify-center gap-2">
            <ShieldCheck className="w-6 h-6 text-blue-500" />
            {tab === 'login'
              ? 'Sign In to NoBar'
              : tab === 'register'
                ? 'Create Your Profile'
                : 'Sign In with Aadhaar'}
          </h1>
          <p className="text-xs text-slate-400">
            {tab === 'aadhaar'
              ? 'Enter your Aadhaar number — we fetch your details (simulated UIDAI) and sign you in, or pre-fill a new account in one step.'
              : tab === 'login'
                ? 'Get your entitlement report, save schemes and apply with one click.'
                : 'Tell us a little about yourself so we can match the right government schemes for you.'}
          </p>
        </div>

        {/* Mode toggle */}
        <div className="flex rounded-lg bg-slate-950 border border-slate-800 p-1 text-xs" role="tablist" aria-label="Authentication mode">
          <button role="tab" aria-selected={tab === 'login'} onClick={() => switchTab('login')} className={`${tabCls} ${tab === 'login' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
            Sign In
          </button>
          <button role="tab" aria-selected={tab === 'aadhaar'} onClick={() => switchTab('aadhaar')} className={`${tabCls} ${tab === 'aadhaar' ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
            <Fingerprint className="w-3.5 h-3.5" /> Aadhaar
          </button>
          <button role="tab" aria-selected={tab === 'register'} onClick={() => switchTab('register')} className={`${tabCls} ${tab === 'register' ? 'bg-emerald-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
            Register
          </button>
        </div>

        {error && (
          <div className="bg-rose-950/80 border border-rose-800 text-rose-300 p-3 rounded-lg text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
        {notice && (
          <div className="bg-emerald-950/80 border border-emerald-800 text-emerald-300 p-3 rounded-lg text-sm">{notice}</div>
        )}

        {tab === 'aadhaar' ? (
          <div className="space-y-4">
            <form onSubmit={handleAadhaarLogin} className="space-y-4">
              <div>
                <label htmlFor="aa-no" className="block text-xs font-semibold text-slate-400 mb-1">
                  Aadhaar Number
                </label>
                <input
                  id="aa-no"
                  type="text"
                  inputMode="numeric"
                  required
                  value={aadhaar}
                  onChange={(e) => setAadhaar(formatAadhaar(e.target.value))}
                  placeholder="XXXX XXXX XXXX"
                  className="w-full bg-slate-950 text-slate-200 px-3 py-2.5 rounded-lg border border-slate-700 text-lg tracking-widest font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <button
                type="button"
                onClick={handleSendOtp}
                disabled={sendingOtp || aadhaar.replace(/\D/g, '').length !== 12}
                className={`w-full py-2.5 rounded-xl font-bold text-white shadow transition flex items-center justify-center gap-2 ${
                  sendingOtp || aadhaar.replace(/\D/g, '').length !== 12
                    ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                    : 'bg-slate-700 hover:bg-slate-600'
                }`}
              >
                {sendingOtp ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
                {sendingOtp ? 'Sending OTP...' : 'Send OTP / Fetch Details'}
              </button>

              {otpInfo && (
                <div className="bg-cyan-950/60 border border-cyan-800 rounded-lg p-3 space-y-2 text-xs">
                  <p className="text-cyan-300">
                    Demo OTP for <span className="font-mono font-bold">{otpInfo.masked_aadhaar}</span> is{' '}
                    <span className="font-mono font-bold bg-slate-950 px-2 py-0.5 rounded border border-cyan-700">{otpInfo.otp}</span>
                  </p>
                  <p className="text-slate-300">
                    {otpInfo.registered
                      ? 'An account is linked to this Aadhaar — you will be signed straight in.'
                      : 'New to NoBar — your profile will be created from the details fetched from Aadhaar.'}
                  </p>
                  {otpInfo.details && (
                    <div className="bg-slate-950/80 border border-slate-800 rounded p-2 space-y-0.5">
                      <p className="text-slate-200 font-semibold">{otpInfo.details.full_name}</p>
                      <p className="text-slate-400">
                        DOB {otpInfo.details.dob} • {otpInfo.details.gender}
                      </p>
                      <p className="text-slate-400">
                        {otpInfo.details.district}, {otpInfo.details.state} — {otpInfo.details.pincode}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {otpInfo && (
                <div>
                  <label htmlFor="aa-otp" className="block text-xs font-semibold text-slate-400 mb-1">
                    Enter OTP
                  </label>
                  <input
                    id="aa-otp"
                    type="text"
                    inputMode="numeric"
                    required
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="6-digit OTP"
                    className="w-full bg-slate-950 text-slate-200 px-3 py-2.5 rounded-lg border border-slate-700 text-lg tracking-widest font-mono focus:outline-none focus:border-cyan-500"
                  />
                </div>
              )}

              {otpInfo && (
                <button
                  type="submit"
                  disabled={submitting || otp.trim().length !== 6}
                  className={`w-full py-2.5 rounded-xl font-bold text-white shadow transition flex items-center justify-center gap-2 ${
                    submitting || otp.trim().length !== 6
                      ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                      : 'bg-cyan-600 hover:bg-cyan-500 cursor-pointer'
                  }`}
                >
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Fingerprint className="w-4 h-4" />}
                  {submitting ? 'Verifying & signing in...' : 'Login with Aadhaar'}
                </button>
              )}
            </form>

            <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 text-[11px] text-slate-400 space-y-1">
              <p className="font-bold text-slate-300">Try a demo Aadhaar number:</p>
              <div className="flex flex-wrap gap-1.5">
                {DEMO_AADHAARS.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => {
                      setAadhaar(n);
                      setOtpInfo(null);
                      setOtp('');
                      setError(null);
                    }}
                    className="font-mono bg-slate-800 hover:bg-slate-700 border border-slate-700 px-2 py-1 rounded text-slate-200"
                  >
                    {n}
                  </button>
                ))}
              </div>
              <p className="pt-1">OTP is always 123456 in this demo. Aadhaar authentication is simulated — no real citizen data is used.</p>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {tab === 'register' && (
              <>
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
                <div>
                  <label htmlFor="aa-optional" className="block text-xs font-semibold text-slate-400 mb-1">
                    Aadhaar Number (optional)
                  </label>
                  <input
                    id="aa-optional"
                    type="text"
                    inputMode="numeric"
                    value={aadhaarOptional}
                    onChange={(e) => setAadhaarOptional(formatAadhaar(e.target.value))}
                    placeholder="XXXX XXXX XXXX"
                    className="w-full bg-slate-950 text-slate-200 px-3 py-2.5 rounded-lg border border-slate-700 text-sm tracking-widest font-mono focus:outline-none focus:border-blue-500"
                  />
                </div>
              </>
            )}

            <div>
              <label htmlFor="email" className="block text-xs font-semibold text-slate-400 mb-1">
                Email Address
              </label>
              <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" className="w-full bg-slate-950 text-slate-200 px-3 py-2.5 rounded-lg border border-slate-700 text-sm focus:outline-none focus:border-blue-500" />
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-semibold text-slate-400 mb-1">
                Password
              </label>
              <input id="password" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Min. 6 characters" className="w-full bg-slate-950 text-slate-200 px-3 py-2.5 rounded-lg border border-slate-700 text-sm focus:outline-none focus:border-blue-500" />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className={`w-full py-2.5 rounded-xl font-bold text-white shadow transition flex items-center justify-center gap-2 ${
                submitting
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                  : tab === 'login'
                    ? 'bg-blue-600 hover:bg-blue-500'
                    : 'bg-emerald-600 hover:bg-emerald-500'
              }`}
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Please wait...
                </>
              ) : tab === 'login' ? (
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
        )}

        <p className="text-[11px] text-slate-500 text-center leading-relaxed">
          Your socio-economic details are used only to match verified government schemes and build your
          personal entitlement report (PDF). You control what you share.
        </p>
      </div>
    </div>
  );
};