import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Eye, EyeOff, AlertCircle, CheckCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { InlineSpinner } from '../components/ui/Spinner';
import client from '../api/client';
import type { UserResponse } from '../types';

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

const DEMO_ACCOUNTS = [
  { role: 'Super Admin', email: 'superadmin@ehr.in', hospital: 'All' },
  { role: 'Admin', email: 'admin@citygeneral.in', hospital: 'City General' },
  { role: 'Hospital', email: 'hospital@hospital.in', hospital: 'City General' },
  { role: 'Doctor', email: 'dr.priya@citygeneral.in', hospital: 'City General' },
  { role: 'Nurse', email: 'nurse.anitha@citygeneral.in', hospital: 'City General' },
  { role: 'Doctor', email: 'dr.vikram@apollo.in', hospital: 'Apollo' },
  { role: 'Patient', email: 'srihari@patient.in', hospital: 'City General' },
];

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [verified, setVerified] = useState(false);
  const [showDemo, setShowDemo] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const fd = new FormData();
    fd.append('username', email);
    fd.append('password', password);

    try {
      const { data } = await client.post<LoginResponse>('/auth/login', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      login(data.user, data.access_token);
      setVerified(true);
      setTimeout(() => navigate('/dashboard'), 1500);
    } catch (err: unknown) {
      const status = (err as { response?: { status: number } }).response?.status;
      if (status === 403)
        setError('Your account access has been revoked. Contact your administrator.');
      else if (status === 401)
        setError('Access denied — credentials not recognised.');
      else
        setError('An unexpected error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const fill = (em: string) => { setEmail(em); setPassword('Password@123'); };

  return (
    <div className="min-h-screen bg-brand-950 flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Decorative background elements */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 opacity-20 pointer-events-none">
        <div className="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] rounded-full bg-primary-600/30 blur-[120px]" />
        <div className="absolute -bottom-[10%] -right-[10%] w-[40%] h-[40%] rounded-full bg-indigo-600/20 blur-[120px]" />
      </div>

      <div className="w-full max-w-md space-y-6 z-10">
        {/* Card */}
        <div className="bg-white rounded-[2rem] shadow-2xl p-10 border border-white/10 relative">
          {/* Header */}
          <div className="flex flex-col items-center mb-10 text-center">
            <div className="w-16 h-16 bg-primary-600 rounded-2xl flex items-center justify-center shadow-xl shadow-primary-900/30 mb-6 group transition-transform hover:scale-105">
              <Shield size={32} className="text-white" />
            </div>
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">CareNexus</h1>
            <p className="text-slate-500 font-medium mt-2 max-w-[240px]">Secure patient health record exchange and management</p>
          </div>

          {verified ? (
            <div className="flex flex-col items-center gap-4 py-8">
              <div className="w-16 h-16 rounded-full bg-emerald-50 flex items-center justify-center text-emerald-500 border border-emerald-100 animate-bounce">
                <CheckCircle size={32} />
              </div>
              <p className="font-bold text-slate-800 text-lg">Identity verified</p>
              <p className="text-slate-400 text-sm">Redirecting to secure dashboard...</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              {error && (
                <div className="flex items-start gap-3 bg-rose-50 border border-rose-100 text-rose-700 text-sm rounded-2xl p-4 animate-in fade-in slide-in-from-top-2">
                  <AlertCircle size={18} className="mt-0.5 flex-shrink-0" />
                  <span className="font-medium">{error}</span>
                </div>
              )}

              <div className="space-y-2">
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider ml-1">Email address</label>
                <input
                  type="email" required value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full px-5 py-4 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-all outline-none"
                  placeholder="Enter your email"
                />
              </div>

              <div className="space-y-2">
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider ml-1">Password</label>
                <div className="relative">
                  <input
                    type={showPwd ? 'text' : 'password'} required value={password}
                    onChange={e => setPassword(e.target.value)}
                    className="w-full px-5 py-4 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-all outline-none pr-12"
                    placeholder="••••••••"
                  />
                  <button type="button" onClick={() => setShowPwd(v => !v)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-primary-600 transition-colors p-1">
                    {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <button
                type="submit" disabled={loading}
                className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-primary-300 text-white font-bold py-4 rounded-2xl shadow-lg shadow-primary-900/20 transition-all flex items-center justify-center gap-3 active:scale-[0.98]"
              >
                {loading ? <><InlineSpinner /> Verifying Account...</> : 'Sign In'}
              </button>
            </form>
          )}
        </div>

        {/* Demo accounts */}
        <div className="bg-white/5 rounded-[2rem] overflow-hidden border border-white/10 backdrop-blur-md">
          <button
            onClick={() => setShowDemo(v => !v)}
            className="w-full flex items-center justify-between px-8 py-5 text-white/90 text-sm font-bold hover:bg-white/5 transition-colors group"
          >
            <span>Platform Access Keys (Demo)</span>
            {showDemo ? <ChevronUp size={18} /> : <ChevronDown size={18} className="transition-transform group-hover:translate-y-0.5" />}
          </button>
          {showDemo && (
            <div className="px-6 pb-6 animate-in slide-in-from-top-4 duration-300">
              <p className="text-white/40 text-[10px] uppercase tracking-widest font-bold mb-4 ml-1">Universal Password: Password@123</p>
              <div className="grid grid-cols-1 gap-2">
                {DEMO_ACCOUNTS.map(a => (
                  <div key={a.email}
                    onClick={() => fill(a.email)}
                    className="flex items-center justify-between p-3 rounded-xl bg-white/5 hover:bg-white/10 cursor-pointer transition-all border border-transparent hover:border-white/10 group">
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-white leading-none">{a.role}</p>
                      <p className="text-[10px] text-white/50 mt-1 truncate">{a.email}</p>
                    </div>
                    <div className="text-[10px] font-bold text-primary-400 uppercase tracking-tighter opacity-0 group-hover:opacity-100 transition-opacity">Auto-fill</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-col items-center gap-2">
          <p className="text-white/20 text-[10px] uppercase tracking-[0.2em] font-bold">Encrypted Security Channel · Active</p>
          <div className="h-1 w-12 bg-white/10 rounded-full overflow-hidden">
            <div className="h-full w-1/3 bg-primary-500 animate-infinite-scroll" />
          </div>
        </div>
      </div>
    </div>
  );
}
