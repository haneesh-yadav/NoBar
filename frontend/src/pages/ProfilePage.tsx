import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Download,
  FileText,
  Save,
  CheckCircle,
  ExternalLink,
  UserRound,
  Loader2,
  ArrowRight,
  AlertTriangle,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiDownload, apiFetch } from '../lib/api';

interface SchemeRef {
  document_id: string;
  title: string;
  category: string;
  scheme_url?: string;
  summary?: string;
  reasons?: string[];
  status?: string;
  saved_at?: string;
  applied_at?: string;
}

interface MySchemesPayload {
  matched: SchemeRef[];
  saved: SchemeRef[];
  applications: SchemeRef[];
}

const selectorCls =
  'w-full bg-slate-950 text-slate-200 px-3 py-2 rounded-lg border border-slate-700 text-sm focus:outline-none focus:border-blue-500';
const inputCls =
  'w-full bg-slate-950 text-slate-200 px-3 py-2 rounded-lg border border-slate-700 text-sm focus:outline-none focus:border-blue-500';

export const ProfilePage: React.FC = () => {
  const { user, loading, updateProfile } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [payload, setPayload] = useState<MySchemesPayload | null>(null);
  const [payloadLoading, setPayloadLoading] = useState(true);

  useEffect(() => {
    if (!loading && !user) navigate('/auth/login', { replace: true });
  }, [user, loading, navigate]);

  useEffect(() => {
    if (user) {
      setForm({ ...user });
    }
  }, [user]);

  useEffect(() => {
    if (!user) return;
    setPayloadLoading(true);
    apiFetch<MySchemesPayload>('/api/users/me/schemes')
      .then(setPayload)
      .catch(() => setPayload(null))
      .finally(() => setPayloadLoading(false));
  }, [user]);

  if (loading) {
    return <div className="text-center py-20 text-slate-400">Checking your session...</div>;
  }
  if (!user) return null;

  const set = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v }));

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveMsg(null);
    try {
      const editable = [
        'dob',
        'gender',
        'marital_status',
        'caste_category',
        'disability_status',
        'disability_type',
        'bpl_status',
        'annual_income',
        'employment_type',
        'state',
        'district',
        'pincode',
      ];
      const updates: any = {};
      for (const k of editable) updates[k] = form[k] ?? '';
      if (updates.annual_income === '' || updates.annual_income == null) updates.annual_income = null;
      else updates.annual_income = Number(updates.annual_income);
      await updateProfile(updates);
      setSaveMsg('Profile updated. Eligibility matching refreshed.');
      setTimeout(() => setSaveMsg(null), 3500);
    } catch (err: any) {
      setSaveMsg(`Failed to save: ${err?.message || 'unknown error'}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadPdf = async () => {
    setDownloading(true);
    try {
      const blob = await apiDownload('/api/users/me/schemes/pdf');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `NoBar_Entitlement_Report_${(user.full_name || user.email).replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setSaveMsg(`PDF download failed: ${err?.message || 'unknown error'}`);
    } finally {
      setDownloading(false);
    }
  };

  const renderSchemeRow = (item: SchemeRef, tag: 'matched' | 'saved' | 'applied') => (
    <div
      key={`${tag}-${item.document_id}`}
      className="flex items-start justify-between gap-3 bg-slate-950 border border-slate-800 rounded-lg px-4 py-3"
    >
      <div className="space-y-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Link to={`/document/${item.document_id}`} className="text-sm font-bold text-blue-400 hover:text-blue-300">
            {item.title}
          </Link>
          <span className="text-[10px] uppercase bg-slate-800 text-slate-400 px-2 py-0.5 rounded border border-slate-700">
            {item.category}
          </span>
        </div>
        {item.summary ? <p className="text-xs text-slate-400 line-clamp-1">{item.summary}</p> : null}
        {item.reasons && item.reasons.length > 0 ? (
          <p className="text-[11px] text-emerald-400">{item.reasons.join(' ')}</p>
        ) : null}
        {item.status ? (
          <p className="text-[11px] text-amber-400 border border-amber-800 bg-amber-950/60 inline-block px-2 py-0.5 rounded">
            Status: {item.status.toUpperCase()}
          </p>
        ) : null}
      </div>
      {item.scheme_url ? (
        <a
          href={item.scheme_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[11px] font-bold text-blue-400 hover:text-blue-300 shrink-0"
        >
          Official Site <ExternalLink className="w-3 h-3" />
        </a>
      ) : (
        <Link to={`/document/${item.document_id}`} className="text-[11px] font-bold text-slate-400 shrink-0">
          View <ArrowRight className="w-3 h-3 inline" />
        </Link>
      )}
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header + PDF download */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-950 rounded-full border border-blue-800 text-blue-400">
            <UserRound className="w-7 h-7" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-slate-100">{user.full_name || 'My Profile'}</h1>
            <p className="text-sm text-slate-400">
              {user.aadhaar_masked || user.email}
              {user.aadhaar_masked && user.email && !user.email.startsWith('aadhaar-') ? ` • ${user.email}` : ''}
              {user.state ? ` • ${user.state}${user.district ? ', ' + user.district : ''}` : ' • Complete your profile for matched schemes'}
            </p>
          </div>
        </div>

        <button
          onClick={handleDownloadPdf}
          disabled={downloading}
          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-white shadow transition ${
            downloading
              ? 'bg-slate-700 text-slate-300 cursor-wait'
              : 'bg-emerald-600 hover:bg-emerald-500 cursor-pointer'
          }`}
        >
          {downloading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" /> Generating PDF...
            </>
          ) : (
            <>
              <Download className="w-4 h-4" /> Download My Report (PDF)
            </>
          )}
        </button>
      </div>

      {saveMsg && (
        <div className="bg-slate-800 border border-slate-700 text-slate-200 px-4 py-3 rounded-lg text-sm">{saveMsg}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Personal details form */}
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-4">
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-400" /> Your Profile Details
            </h2>

            <form onSubmit={handleSaveProfile} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1" htmlFor="pd-dob">Date of Birth</label>
                  <input id="pd-dob" type="date" className={inputCls} value={form.dob || ''} onChange={(e) => set('dob', e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1" htmlFor="pd-gender">Gender</label>
                  <select id="pd-gender" className={selectorCls} value={form.gender || ''} onChange={(e) => set('gender', e.target.value)}>
                    <option value="">Select...</option>
                    <option>Female</option>
                    <option>Male</option>
                    <option>Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1" htmlFor="pd-marital">Marital Status</label>
                  <select id="pd-marital" className={selectorCls} value={form.marital_status || ''} onChange={(e) => set('marital_status', e.target.value)}>
                    <option value="">Select...</option>
                    <option>Single</option>
                    <option>Married</option>
                    <option>Widowed</option>
                    <option>Divorced</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1" htmlFor="pd-caste">Caste Category</label>
                  <select id="pd-caste" className={selectorCls} value={form.caste_category || ''} onChange={(e) => set('caste_category', e.target.value)}>
                    <option value="">Select...</option>
                    <option>Scheduled Caste (SC)</option>
                    <option>Scheduled Tribe (ST)</option>
                    <option>Other Backward Class (OBC)</option>
                    <option>General</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1" htmlFor="pd-disab">Disability Status</label>
                  <select id="pd-disab" className={selectorCls} value={form.disability_status || 'no'} onChange={(e) => set('disability_status', e.target.value)}>
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1" htmlFor="pd-disab-type">Disability Type</label>
                  <input id="pd-disab-type" className={inputCls} placeholder="e.g. Locomotor" value={form.disability_type || ''} onChange={(e) => set('disability_type', e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1" htmlFor="pd-bpl">BPL Status</label>
                  <select id="pd-bpl" className={selectorCls} value={form.bpl_status || ''} onChange={(e) => set('bpl_status', e.target.value)}>
                    <option value="">Select...</option>
                    <option value="yes">Yes (BPL card holder)</option>
                    <option value="no">No</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1" htmlFor="pd-income">Annual Income (INR)</label>
                  <input id="pd-income" type="number" min={0} step={1000} className={inputCls} value={form.annual_income ?? ''} onChange={(e) => set('annual_income', e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1" htmlFor="pd-emp">Employment Type</label>
                  <select id="pd-emp" className={selectorCls} value={form.employment_type || ''} onChange={(e) => set('employment_type', e.target.value)}>
                    <option value="">Select...</option>
                    <option>Self Employed</option>
                    <option>Daily Wage Labourer</option>
                    <option>Construction Worker</option>
                    <option>Government Employee</option>
                    <option>Private Employee</option>
                    <option>Farmer/Kisan</option>
                    <option>Unemployed</option>
                    <option>Student</option>
                    <option>Home Maker</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1" htmlFor="pd-state">State</label>
                  <input id="pd-state" className={inputCls} value={form.state || ''} onChange={(e) => set('state', e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1" htmlFor="pd-district">District</label>
                  <input id="pd-district" className={inputCls} value={form.district || ''} onChange={(e) => set('district', e.target.value)} />
                </div>
              </div>

              <button
                type="submit"
                disabled={saving}
                className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-white transition ${
                  saving ? 'bg-slate-700 text-slate-300 cursor-wait' : 'bg-blue-600 hover:bg-blue-500 cursor-pointer'
                }`}
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {saving ? 'Saving...' : 'Save Profile'}
              </button>
            </form>
          </div>
        </div>

        {/* My schemes */}
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-4">
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-emerald-400" /> Schemes You Match ({payload?.matched?.length ?? 0})
            </h2>
            {payloadLoading ? (
              <p className="text-xs text-slate-400">Matching your profile...</p>
            ) : !payload || payload.matched.length === 0 ? (
              <p className="text-xs text-slate-400 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                No matches yet — complete your profile above to unlock personalised matching.
              </p>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {payload.matched.map((m) => renderSchemeRow(m, 'matched'))}
              </div>
            )}
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-4">
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              <Save className="w-5 h-5 text-blue-400" /> Saved Schemes ({payload?.saved?.length ?? 0})
            </h2>
            {!payloadLoading && payload && payload.saved.length > 0 ? (
              <div className="space-y-2">{payload.saved.map((m) => renderSchemeRow(m, 'saved'))}</div>
            ) : (
              <p className="text-xs text-slate-400">No saved schemes. Use "Save" on any scheme page.</p>
            )}
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-4">
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              <ArrowRight className="w-5 h-5 text-amber-400" /> My Applications ({payload?.applications?.length ?? 0})
            </h2>
            {!payloadLoading && payload && payload.applications.length > 0 ? (
              <div className="space-y-2">{payload.applications.map((m) => renderSchemeRow(m, 'applied'))}</div>
            ) : (
              <p className="text-xs text-slate-400">No applications yet. Apply from any scheme you are eligible for.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};