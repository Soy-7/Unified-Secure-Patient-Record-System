import { useEffect, useState } from 'react';
import { User, Key, Building, ShieldCheck, CheckCircle } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { roleBadge, Badge } from '../components/ui/Badge';
import { PageSpinner, InlineSpinner } from '../components/ui/Spinner';
import client from '../api/client';
import type { Hospital } from '../types';

export default function Settings() {
  const { user } = useAuthStore();
  const [hospital, setHospital] = useState<Hospital | null>(null);
  const [loading, setLoading] = useState(true);

  // Key rotation
  const [fp, setFp] = useState(user?.publicKey ? user.publicKey.substring(0, 32) + '...' : 'N/A');
  const [rotating, setRotating] = useState(false);
  const [rotateMsg, setRotateMsg] = useState('');

  useEffect(() => {
    if (!user) return;
    client.get<Hospital[]>('/hospitals')
      .then(r => setHospital((r.data ?? []).find((h: Hospital) => h.id === user.hospitalId) ?? null))
      .finally(() => setLoading(false));
  }, [user]);

  const handleRotate = async () => {
    if (!user) return;
    setRotating(true); setRotateMsg('');
    try {
      const { data } = await client.post<{ message: string, fingerprint: string }>(`/users/${user.id}/rotate-keys`);
      setFp(data.fingerprint);
      setRotateMsg('Keys rotated successfully. New fingerprint: ' + data.fingerprint.substring(0,20) + '...');
    } finally { setRotating(false); }
  };

  if (loading) return <PageSpinner />;

  return (
    <div className="max-w-4xl space-y-6">
      
      {/* Profile */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center gap-2">
          <User size={18} className="text-blue-600" />
          <h3 className="font-semibold text-gray-900">Profile Information</h3>
        </div>
        <div className="p-5 grid grid-cols-2 gap-y-4 gap-x-8">
          <div><p className="text-xs text-gray-400 font-medium uppercase mb-0.5">Name</p><p className="font-medium text-gray-900">{user?.name}</p></div>
          <div><p className="text-xs text-gray-400 font-medium uppercase mb-0.5">Email</p><p className="font-medium text-gray-900">{user?.email}</p></div>
          <div><p className="text-xs text-gray-400 font-medium uppercase mb-0.5">Role</p><div className="mt-1">{user && roleBadge(user.role)}</div></div>
          <div><p className="text-xs text-gray-400 font-medium uppercase mb-0.5">Department</p><p className="font-medium text-gray-900">{user?.department || '—'}</p></div>
          <div className="col-span-2"><p className="text-xs text-gray-400 font-medium uppercase mb-1.5">Attributes</p><div className="flex flex-wrap gap-1">{user?.attributes.map(a => <Badge key={a} label={a} color="gray" />)}</div></div>
        </div>
      </div>

      {/* Security */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center gap-2">
          <Key size={18} className="text-amber-600" />
          <h3 className="font-semibold text-gray-900">Cryptographic Keys</h3>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <p className="text-xs text-gray-400 font-medium uppercase mb-1">Current Public Key Fingerprint</p>
            <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5 font-mono text-sm text-gray-600 break-all">{fp}</div>
          </div>
          {rotateMsg && <div className="bg-green-50 text-green-700 px-4 py-2.5 rounded-lg text-sm border border-green-200">{rotateMsg}</div>}
          <div className="flex items-center gap-4">
            <button onClick={handleRotate} disabled={rotating} className="flex items-center gap-2 bg-gray-800 hover:bg-gray-900 text-white font-medium px-5 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-70">
              {rotating && <InlineSpinner />} Rotate Encryption Keys
            </button>
            <p className="text-sm text-gray-500 italic">Session expires 8 hours after login.</p>
          </div>
        </div>
      </div>

      {/* Hospital */}
      {hospital && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center gap-2">
            <Building size={18} className="text-teal-600" />
            <h3 className="font-semibold text-gray-900">Hospital Information</h3>
          </div>
          <div className="p-5 grid grid-cols-2 gap-y-4 gap-x-8">
            <div><p className="text-xs text-gray-400 font-medium uppercase mb-0.5">Name</p><p className="font-medium text-gray-900">{hospital.name}</p></div>
            <div><p className="text-xs text-gray-400 font-medium uppercase mb-0.5">City</p><p className="font-medium text-gray-900">{hospital.city}</p></div>
            <div className="col-span-2"><p className="text-xs text-gray-400 font-medium uppercase mb-0.5">API Endpoint</p><p className="font-mono text-sm text-blue-600">{hospital.apiEndpoint}</p></div>
            <div className="col-span-2"><p className="text-xs text-gray-400 font-medium uppercase mb-0.5">TLS Certificate Fingerprint</p><p className="font-mono text-sm text-gray-600 bg-gray-50 border border-gray-100 rounded px-2 py-1 w-fit">{hospital.tlsCertFingerprint}</p></div>
          </div>
        </div>
      )}

      {/* Pillars */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2"><ShieldCheck size={18} className="text-green-600"/> Platform Security Posture</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {['bcrypt (cost 12)', 'AES-256-GCM', 'JWT (HS256, 8h expiry)', 'CP-ABE policy check', 'SHA-256 audit hash chain', 'User revocation system', 'Role-based access control'].map(p => (
            <div key={p} className="flex items-center gap-2"><CheckCircle size={16} className="text-green-500"/> <span className="text-sm text-gray-700">{p}</span></div>
          ))}
        </div>
      </div>
    </div>
  );
}
