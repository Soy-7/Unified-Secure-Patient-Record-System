import React, { useEffect, useState } from 'react';
import { Plus, CheckCircle, XCircle } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { statusBadge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { PageSpinner, InlineSpinner } from '../components/ui/Spinner';
import client from '../api/client';
import type { ExchangeRequest, Hospital } from '../types';

const RECORD_TYPES = ['diagnosis', 'prescription', 'lab_result', 'imaging', 'discharge_summary', 'consultation'];

export default function Exchange() {
  const { user } = useAuthStore();
  const [outgoing, setOutgoing] = useState<ExchangeRequest[]>([]);
  const [incoming, setIncoming] = useState<ExchangeRequest[]>([]);
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);

  // New Request modal
  const [showAdd, setShowAdd] = useState(false);
  const [addSaving, setAddSaving] = useState(false);
  const [addForm, setAddForm] = useState({ toHospitalId: '', patientId: '', purpose: '', recordTypes: [] as string[] });

  // Approve modal
  const [approveReq, setApproveReq] = useState<ExchangeRequest | null>(null);
  const [approveSaving, setApproveSaving] = useState(false);
  const [payloadPreview, setPayloadPreview] = useState('');

  const load = async () => {
    try {
      const [exRes, hRes] = await Promise.all([
        client.get<ExchangeRequest[]>('/exchange'),
        client.get<Hospital[]>('/hospitals')
      ]);
      const all = exRes.data ?? [];
      setHospitals(hRes.data ?? []);
      setOutgoing(all.filter(x => x.fromHospitalId === user?.hospitalId));
      setIncoming(all.filter(x => x.toHospitalId === user?.hospitalId));
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [user]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault(); setAddSaving(true);
    try {
      await client.post('/exchange', addForm);
      setShowAdd(false); setAddForm({ toHospitalId: '', patientId: '', purpose: '', recordTypes: [] });
      load();
    } finally { setAddSaving(false); }
  };

  const handleApprove = async () => {
    if (!approveReq) return;
    setApproveSaving(true);
    try {
      const { data } = await client.put<{ message: string, payloadPreview: string }>(`/exchange/${approveReq.id}/approve`);
      setPayloadPreview(data.payloadPreview);
      load();
    } finally { setApproveSaving(false); }
  };

  const handleReject = async (id: string) => {
    try { await client.put(`/exchange/${id}/reject`); load(); } catch { /* ignore */ }
  };

  const hospName = (id: string) => hospitals.find(h => h.id === id)?.name ?? id;
  const toggleRt = (t: string) => setAddForm(f => ({ ...f, recordTypes: f.recordTypes.includes(t) ? f.recordTypes.filter(x => x !== t) : [...f.recordTypes, t] }));

  if (loading) return <PageSpinner />;

  const ReqTable = ({ reqs, type }: { reqs: ExchangeRequest[], type: 'in' | 'out' }) => (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden mb-6">
      <div className="px-5 py-4 border-b border-gray-100 bg-gray-50">
        <h3 className="font-semibold text-gray-900">{type === 'in' ? 'Incoming Requests (Action Required)' : 'Outgoing Requests'}</h3>
      </div>
      {reqs.length === 0 ? <div className="p-8 text-center text-gray-400 text-sm">No {type === 'in' ? 'incoming' : 'outgoing'} requests.</div> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide border-t border-gray-100">
              <tr>{[(type==='in'?'From':'To')+' Hospital','Patient ID','Status','Types','Purpose','Date','Actions'].map(h=><th key={h} className="text-left px-5 py-3">{h}</th>)}</tr>
            </thead>
            <tbody>
              {reqs.map((r, i) => (
                <tr key={r.id} className={`border-t border-gray-50 hover:bg-gray-50/60 ${i % 2 === 1 ? 'bg-gray-50/40' : ''}`}>
                  <td className="px-5 py-3 text-xs text-gray-800 font-medium">{hospName(type === 'in' ? r.fromHospitalId : r.toHospitalId)}</td>
                  <td className="px-5 py-3 text-xs text-gray-500 font-mono">{r.patientId.slice(0, 8)}</td>
                  <td className="px-5 py-3">{statusBadge(r.status)}</td>
                  <td className="px-5 py-3 text-xs text-gray-500">{r.recordTypes.join(', ')}</td>
                  <td className="px-5 py-3 text-xs text-gray-500 max-w-xs truncate">{r.purpose}</td>
                  <td className="px-5 py-3 text-xs text-gray-400">{new Date(r.createdAt).toLocaleDateString()}</td>
                  <td className="px-5 py-3 flex gap-2">
                    {type === 'in' && r.status === 'pending' && (
                      <>
                        <button onClick={() => setApproveReq(r)} className="text-green-600 hover:text-green-800 p-1 bg-green-50 rounded" title="Approve"><CheckCircle size={15} /></button>
                        <button onClick={() => handleReject(r.id)} className="text-red-600 hover:text-red-800 p-1 bg-red-50 rounded" title="Reject"><XCircle size={15} /></button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={() => setShowAdd(true)} className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-xl text-sm transition-colors">
          <Plus size={15} /> New Request
        </button>
      </div>

      <ReqTable reqs={incoming} type="in" />
      <ReqTable reqs={outgoing} type="out" />

      {/* New Request Modal */}
      <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="New Exchange Request">
        <form onSubmit={handleAdd} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Target Hospital</label>
            <select required value={addForm.toHospitalId} onChange={e => setAddForm(f => ({ ...f, toHospitalId: e.target.value }))} className="w-full px-3 py-2 border rounded-lg text-sm">
              <option value="">Select hospital…</option>
              {hospitals.filter(h => h.id !== user?.hospitalId).map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
          </div>
          <div><label className="block text-xs font-medium text-gray-700 mb-1">Patient ID (UUID)</label><input required value={addForm.patientId} onChange={e => setAddForm(f => ({ ...f, patientId: e.target.value }))} className="w-full px-3 py-2 border rounded-lg text-sm font-mono" /></div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-2">Record Types</label>
            <div className="flex flex-wrap gap-2">
              {RECORD_TYPES.map(t => (
                <button key={t} type="button" onClick={() => toggleRt(t)} className={`px-3 py-1 text-xs rounded-full border transition-colors ${addForm.recordTypes.includes(t) ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 text-gray-600 hover:border-blue-400'}`}>
                  {t.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>
          <div><label className="block text-xs font-medium text-gray-700 mb-1">Purpose</label><textarea required rows={3} value={addForm.purpose} onChange={e => setAddForm(f => ({ ...f, purpose: e.target.value }))} className="w-full px-3 py-2 border rounded-lg text-sm resize-none" /></div>
          <div className="flex justify-end gap-2 pt-2"><button type="button" onClick={() => setShowAdd(false)} className="px-4 py-2 border rounded-xl text-sm hover:bg-gray-50">Cancel</button><button type="submit" disabled={addSaving} className="flex gap-2 items-center px-4 py-2 bg-blue-600 text-white rounded-xl text-sm">{addSaving && <InlineSpinner />} Submit</button></div>
        </form>
      </Modal>

      {/* Approve Payload Modal */}
      <Modal isOpen={!!approveReq} onClose={() => { setApproveReq(null); setPayloadPreview(''); }} title="Approve Transfer">
        {!payloadPreview ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">This will encrypt requested records with the shared ECDH key established with <strong>{hospName(approveReq?.fromHospitalId ?? '')}</strong>.</p>
            <div className="flex justify-end gap-2"><button onClick={() => setApproveReq(null)} className="px-4 py-2 border rounded-xl text-sm">Cancel</button><button onClick={handleApprove} disabled={approveSaving} className="flex gap-2 items-center px-4 py-2 bg-green-600 text-white rounded-xl text-sm">{approveSaving && <InlineSpinner />} Approve & Encrypt Payload</button></div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="bg-green-50 text-green-700 p-3 rounded-xl flex items-center gap-2"><CheckCircle size={18} /> <span className="font-medium text-sm">Transfer Approved — Records Encrypted and Transmitted</span></div>
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">Encrypted Payload Preview (First 100 bytes)</p>
              <div className="bg-gray-50 border border-gray-200 p-3 rounded-xl text-xs font-mono text-gray-500 break-all">{payloadPreview}</div>
            </div>
            <div className="flex justify-end"><button onClick={() => { setApproveReq(null); setPayloadPreview(''); }} className="px-4 py-2 bg-gray-800 text-white rounded-xl text-sm">Done</button></div>
          </div>
        )}
      </Modal>
    </div>
  );
}
