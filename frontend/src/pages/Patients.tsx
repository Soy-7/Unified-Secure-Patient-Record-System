import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, Eye, Users } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { PageSpinner, InlineSpinner } from '../components/ui/Spinner';
import client from '../api/client';
import type { Patient, Hospital, PaginatedPatients } from '../types';

const BLOOD_GROUPS = ['A+','A-','B+','B-','O+','O-','AB+','AB-'];

interface NewPatientForm {
  name: string; dob: string; gender: string; bloodGroup: string;
  phone: string; email: string; address: string;
  primaryHospitalId: string;
  emergencyContact: { name: string; phone: string };
}

const defaultForm = (): NewPatientForm => ({
  name: '', dob: '', gender: 'Male', bloodGroup: 'O+',
  phone: '', email: '', address: '',
  primaryHospitalId: '',
  emergencyContact: { name: '', phone: '' },
});

export default function Patients() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const canWrite = user?.role === 'admin' || user?.role === 'nurse';

  const [patients, setPatients]   = useState<Patient[]>([]);
  const [total, setTotal]         = useState(0);
  const [page, setPage]           = useState(1);
  const [search, setSearch]       = useState('');
  const [hospFilter, setHospFilter] = useState('');
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading]     = useState(true);
  const [showAdd, setShowAdd]     = useState(false);
  const [saving, setSaving]       = useState(false);
  const [formErr, setFormErr]     = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [form, setForm]           = useState<NewPatientForm>(defaultForm());

  const LIMIT = 10;

  const load = useCallback(async (q: string, h: string, p: number) => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page: p, limit: LIMIT };
      if (q) params.search = q;
      if (h) params.hospital_id = h;
      const { data } = await client.get<PaginatedPatients>('/patients', { params });
      setPatients(data.patients ?? []);
      setTotal(data.total ?? 0);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load hospitals once
  useEffect(() => {
    client.get<Hospital[]>('/hospitals').then(r => {
      setHospitals(r.data ?? []);
      if (r.data?.[0]) setForm(f => ({ ...f, primaryHospitalId: r.data[0].id }));
    }).catch(() => {});
  }, []);

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => { setPage(1); load(search, hospFilter, 1); }, 300);
    return () => clearTimeout(t);
  }, [search, hospFilter, load]);

  useEffect(() => { load(search, hospFilter, page); }, [page, load]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setFormErr('');
    try {
      await client.post('/patients', form);
      setShowAdd(false);
      setForm(defaultForm());
      setSuccessMsg('Patient registered successfully.');
      setTimeout(() => setSuccessMsg(''), 3000);
      load(search, hospFilter, page);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setFormErr(msg ?? 'Failed to register patient.');
    } finally { setSaving(false); }
  };

  const pages = Math.ceil(total / LIMIT) || 1;
  const hospName = (id: string) => hospitals.find(h => h.id === id)?.name ?? id;

  return (
    <div className="max-w-7xl mx-auto space-y-8 py-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 flex-wrap bg-white p-4 rounded-3xl border border-slate-100 shadow-subtle">
        <div className="flex items-center gap-3 flex-1 min-w-[300px]">
          <div className="relative flex-1">
            <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={search} onChange={e => setSearch(e.target.value)}
              type="text" placeholder="Search patients by name or ID..."
              className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-all" />
          </div>
          <select value={hospFilter} onChange={e => { setHospFilter(e.target.value); setPage(1); }}
            className="px-4 py-3 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all outline-none">
            <option value="">All Hospitals</option>
            {hospitals.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
        </div>
        {canWrite && (
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-bold px-6 py-3 rounded-2xl transition-all shadow-lg shadow-primary-900/20 active:scale-95">
            <Plus size={18} strokeWidth={3} /> New Patient
          </button>
        )}
      </div>

      {successMsg && (
        <div className="bg-emerald-50 border border-emerald-100 text-emerald-700 text-sm font-bold rounded-2xl px-6 py-4 animate-in fade-in slide-in-from-top-2">{successMsg}</div>
      )}

      {/* Table */}
      <div className="bg-white rounded-[2.5rem] border border-slate-100 shadow-subtle overflow-hidden">
        {loading ? <div className="py-20"><PageSpinner /></div> : patients.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-slate-400">
            <div className="w-20 h-20 bg-slate-50 rounded-3xl flex items-center justify-center mb-6">
               <Users size={40} className="opacity-20" />
            </div>
            <p className="text-lg font-bold text-slate-900">No patients found</p>
            <p className="text-sm mt-1">Try adjusting your search or filters.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50/50 text-[10px] text-slate-400 uppercase tracking-widest font-bold">
                  <tr>
                    {['Patient ID','Full Name','Date of Birth','Blood','Primary Facility','Actions'].map(h => (
                      <th key={h} className="text-left px-8 py-5">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {patients.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/50 transition-colors group">
                      <td className="px-8 py-6 text-slate-400 font-mono text-xs">#{p.id.slice(0,8).toUpperCase()}</td>
                      <td className="px-8 py-6">
                        <div className="flex flex-col">
                           <span className="font-bold text-slate-900">{p.name}</span>
                           <span className="text-[10px] text-slate-400 uppercase font-bold tracking-tighter mt-0.5">{p.gender}</span>
                        </div>
                      </td>
                      <td className="px-8 py-6 text-slate-500 font-medium">{p.dob}</td>
                      <td className="px-8 py-6"><Badge label={p.bloodGroup} color="red" /></td>
                      <td className="px-8 py-6">
                        <div className="flex items-center gap-2">
                           <span className="text-slate-600 font-bold">{hospName(p.primaryHospitalId)}</span>
                           {p.linkedHospitalIds?.length > 0 && (
                             <Badge label={`+${p.linkedHospitalIds.length}`} color="blue" size="xs" />
                           )}
                        </div>
                      </td>
                      <td className="px-8 py-6">
                        <button onClick={() => navigate(`/patients/${p.id}`)}
                          className="flex items-center gap-2 bg-slate-100 hover:bg-primary-600 hover:text-white text-slate-600 text-xs font-bold px-4 py-2 rounded-xl transition-all">
                          <Eye size={14} /> View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between px-8 py-6 border-t border-slate-50 text-xs font-bold text-slate-400">
              <span className="uppercase tracking-wider">Showing {(page-1)*LIMIT+1}–{Math.min(page*LIMIT,total)} of {total} records</span>
              <div className="flex gap-3">
                <button disabled={page<=1} onClick={() => setPage(p=>p-1)}
                  className="px-5 py-2.5 bg-slate-50 border border-slate-100 rounded-xl disabled:opacity-30 hover:bg-white hover:shadow-subtle transition-all uppercase tracking-widest text-[10px]">Prev</button>
                <button disabled={page>=pages} onClick={() => setPage(p=>p+1)}
                  className="px-5 py-2.5 bg-slate-50 border border-slate-100 rounded-xl disabled:opacity-30 hover:bg-white hover:shadow-subtle transition-all uppercase tracking-widest text-[10px]">Next</button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Add Patient Modal */}
      <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="Register New Patient" size="lg">
        <form onSubmit={handleAdd} className="space-y-6 py-2">
          {formErr && (
            <div className="bg-rose-50 border border-rose-100 text-rose-700 text-sm font-bold rounded-2xl px-5 py-4">{formErr}</div>
          )}
          <div className="grid grid-cols-2 gap-5">
            {([['Full Name','name','text'],['Date of Birth','dob','date'],['Phone Number','phone','tel'],['Email Address','email','email']] as const).map(([label,field,type]) => (
              <div key={field} className={field==='name'?'col-span-2':''}>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 ml-1">{label}</label>
                <input type={type} value={(form as any)[field] ?? ''} required={field!=='email'}
                  onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))}
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-all outline-none" />
              </div>
            ))}
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 ml-1">Gender</label>
              <select value={form.gender} onChange={e => setForm(f => ({ ...f, gender: e.target.value }))}
                className="w-full px-4 py-3 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all outline-none">
                {['Male','Female','Other'].map(o => <option key={o}>{o}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 ml-1">Blood Group</label>
              <select value={form.bloodGroup} onChange={e => setForm(f => ({ ...f, bloodGroup: e.target.value }))}
                className="w-full px-4 py-3 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all outline-none">
                {BLOOD_GROUPS.map(b => <option key={b}>{b}</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 ml-1">Residential Address</label>
              <textarea rows={2} value={form.address} onChange={e => setForm(f => ({ ...f, address: e.target.value }))}
                className="w-full px-4 py-3 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-all outline-none resize-none" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 ml-1">Primary Healthcare Facility</label>
              <select value={form.primaryHospitalId} onChange={e => setForm(f => ({ ...f, primaryHospitalId: e.target.value }))}
                className="w-full px-4 py-3 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all outline-none">
                {hospitals.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 ml-1">Emergency Contact Name</label>
              <input value={form.emergencyContact.name}
                onChange={e => setForm(f => ({ ...f, emergencyContact: { ...f.emergencyContact, name: e.target.value } }))}
                className="w-full px-4 py-3 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-all outline-none" />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 ml-1">Emergency Contact Phone</label>
              <input value={form.emergencyContact.phone}
                onChange={e => setForm(f => ({ ...f, emergencyContact: { ...f.emergencyContact, phone: e.target.value } }))}
                className="w-full px-4 py-3 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-all outline-none" />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-6">
            <button type="button" onClick={() => setShowAdd(false)}
              className="px-6 py-3 text-sm font-bold text-slate-500 hover:text-slate-700 transition-colors">Cancel</button>
            <button type="submit" disabled={saving}
              className="flex items-center gap-2 px-8 py-3 bg-primary-600 text-white text-sm font-bold rounded-2xl hover:bg-primary-700 shadow-lg shadow-primary-900/20 transition-all active:scale-95 disabled:opacity-60">
              {saving ? <InlineSpinner /> : <Plus size={18} strokeWidth={3} />} Register Patient
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
