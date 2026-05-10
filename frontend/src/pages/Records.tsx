import React, { useEffect, useState, useCallback } from 'react';
import { Search, Plus, FileText, ShieldOff, Eye } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { recordTypeBadge, Badge, statusBadge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { PageSpinner, InlineSpinner } from '../components/ui/Spinner';
import client from '../api/client';
import type { EHRRecord, Hospital, PaginatedRecords, Patient, PaginatedPatients } from '../types';

const RECORD_TYPES = ['diagnosis', 'prescription', 'lab_result', 'imaging', 'discharge_summary', 'consultation'];
const POLICIES = ['doctor', 'nurse', 'admin', 'cardiology', 'neurology', 'senior', 'patient', 'general'];

export default function Records() {
  const { user } = useAuthStore();
  const canWrite = user?.role === 'admin' || user?.role === 'doctor';

  const [records, setRecords] = useState<EHRRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState('');
  const [hospFilter, setHospFilter] = useState('');
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [patientMap, setPatientMap] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  // View state
  const [viewRecord, setViewRecord] = useState<EHRRecord | null>(null);
  const [accessError, setAccessError] = useState<{ message: string; userAttributes?: string[]; requiredPolicy?: string[] } | null>(null);
  const [viewLoading, setViewLoading] = useState(false);

  // Add state
  const [showAdd, setShowAdd] = useState(false);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [formErr, setFormErr] = useState('');
  const [patientQuery, setPatientQuery] = useState('');
  const [patientResults, setPatientResults] = useState<Patient[]>([]);
  const [form, setForm] = useState({
    patientId: '', recordType: 'diagnosis', title: '', content: '', accessPolicy: [] as string[], tags: ''
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const LIMIT = 10;

  const load = useCallback(async (t: string, h: string, p: number) => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page: p, limit: LIMIT };
      if (t) params.record_type = t;
      if (h) params.hospital_id = h;
      const { data } = await client.get<PaginatedRecords>('/records', { params });
      setRecords(data.records ?? []);
      setTotal(data.total ?? 0);
      
      // Fetch missing patient names
      const pIds = [...new Set((data.records ?? []).map(r => r.patientId))];
      pIds.forEach(async id => {
        if (!patientMap[id]) {
          try {
            const pr = await client.get<Patient>(`/patients/${id}`);
            setPatientMap(m => ({ ...m, [id]: pr.data.name }));
          } catch { /* ignore */ }
        }
      });
    } finally {
      setLoading(false);
    }
  }, [patientMap]);

  useEffect(() => {
    client.get<Hospital[]>('/hospitals').then(r => setHospitals(r.data ?? [])).catch(() => {});
  }, []);

  useEffect(() => { load(typeFilter, hospFilter, page); }, [page, typeFilter, hospFilter, load]);

  // Debounced patient search for the add form
  useEffect(() => {
    if (!patientQuery || patientQuery.length < 2) { setPatientResults([]); return; }
    const t = setTimeout(async () => {
      try {
        const { data } = await client.get<PaginatedPatients>(`/patients?search=${patientQuery}&limit=5`);
        setPatientResults(data.patients ?? []);
      } catch { /* ignore */ }
    }, 300);
    return () => clearTimeout(t);
  }, [patientQuery]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.accessPolicy.length === 0) { setFormErr('Please select at least one access policy.'); return; }
    if (!form.patientId) { setFormErr('Please select a patient.'); return; }
    
    setSaving(true); setFormErr('');
    try {
      let fileData = null;
      if (selectedFile) {
        fileData = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result as string);
          reader.onerror = reject;
          reader.readAsDataURL(selectedFile);
        });
      }

      const contentObj = {
        text: form.content,
        fileName: selectedFile?.name,
        fileData: fileData
      };

      const payload = {
        patientId: form.patientId,
        recordType: form.recordType,
        title: form.title,
        content: JSON.stringify(contentObj),
        accessPolicy: form.accessPolicy,
        tags: form.tags ? form.tags.split(',').map(s => s.trim()) : [],
      };
      await client.post('/records', payload);
      setShowAdd(false);
      setForm({ patientId: '', recordType: 'diagnosis', title: '', content: '', accessPolicy: [], tags: '' });
      setSelectedFile(null);
      setPatientQuery('');
      setSuccessMsg('Record encrypted and stored successfully.');
      setTimeout(() => setSuccessMsg(''), 3000);
      load(typeFilter, hospFilter, page);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setFormErr(msg ?? 'Failed to create record.');
    } finally { setSaving(false); }
  };

  const viewRecordDetail = async (rec: EHRRecord) => {
    setViewLoading(true); setViewRecord(null); setAccessError(null);
    try {
      const { data } = await client.get<EHRRecord>(`/records/${rec.id}`);
      setViewRecord(data);
    } catch (err: unknown) {
      const e = err as { response?: { status: number; data: { message?: string; userAttributes?: string[]; requiredPolicy?: string[] } } };
      if (e.response?.status === 403) {
        setAccessError({
          message: e.response.data?.message ?? 'You do not have the required attributes to access this record.',
          userAttributes: e.response.data?.userAttributes,
          requiredPolicy: e.response.data?.requiredPolicy,
        });
      }
    } finally { setViewLoading(false); }
  };

  const handleApprove = async (rec: EHRRecord) => {
    try {
      await client.put(`/records/${rec.id}/status?status_val=approved`);
      load(typeFilter, hospFilter, page);
    } catch {
      alert("Failed to approve record.");
    }
  };

  const pages = Math.ceil(total / LIMIT) || 1;
  const hospName = (id: string) => hospitals.find(h => h.id === id)?.name ?? id;
  const togglePol = (p: string) => setForm(f => ({ ...f, accessPolicy: f.accessPolicy.includes(p) ? f.accessPolicy.filter(x=>x!==p) : [...f.accessPolicy, p] }));

  const parseDecrypted = (raw: string | null | undefined) => {
    if (!raw) return null;
    try { return Object.entries(JSON.parse(raw)); } catch { return [['\u200b', raw]] as [string,string][]; }
  };

  return (
    <div className="space-y-5">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <select value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setPage(1); }}
          className="px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All Types</option>
          {RECORD_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
        </select>
        <select value={hospFilter} onChange={e => { setHospFilter(e.target.value); setPage(1); }}
          className="px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All Hospitals</option>
          {hospitals.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
        </select>
        {canWrite && (
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-xl transition-colors ml-auto">
            <Plus size={15} /> Consult Patient / Create Case
          </button>
        )}
      </div>

      {successMsg && (
        <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-xl px-4 py-3">{successMsg}</div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? <PageSpinner /> : records.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400">
            <FileText size={36} className="opacity-30 mb-3" />
            <p className="text-sm">No records found.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
                  <tr>
                    {['Patient', 'Type', 'Title', 'Hospital', 'Created By', 'Date', 'Status', ''].map(h => (
                      <th key={h} className="text-left px-5 py-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {records.map((r, i) => (
                    <tr key={r.id} className={`border-t border-gray-50 hover:bg-blue-50/30 ${i % 2 === 1 ? 'bg-gray-50/40' : ''}`}>
                      <td className="px-5 py-3 font-medium text-gray-900">{patientMap[r.patientId] || <span className="text-gray-400 font-mono text-xs">{r.patientId.slice(0,8)}</span>}</td>
                      <td className="px-5 py-3">{recordTypeBadge(r.recordType)}</td>
                      <td className="px-5 py-3 text-gray-800">{r.title}</td>
                      <td className="px-5 py-3 text-gray-500 text-xs">{hospName(r.hospitalId)}</td>
                      <td className="px-5 py-3 text-gray-400 text-xs">{r.createdBy.slice(0,16)}</td>
                      <td className="px-5 py-3 text-gray-500 text-xs">{new Date(r.createdAt).toLocaleDateString()}</td>
                      <td className="px-5 py-3">{statusBadge(r.status)}</td>
                      <td className="px-5 py-3 flex gap-2">
                        {r.status === 'pending' && user?.role !== 'doctor' && (
                          <button onClick={() => handleApprove(r)} className="text-green-600 hover:text-green-800 text-xs font-medium bg-green-50 px-2 py-1 rounded">Approve</button>
                        )}
                        <button disabled={viewLoading} onClick={() => viewRecordDetail(r)}
                          className="flex items-center gap-1 text-blue-600 hover:text-blue-800 text-xs font-medium disabled:opacity-50">
                          <Eye size={13} /> View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 text-sm text-gray-500">
              <span>Showing {(page - 1) * LIMIT + 1}–{Math.min(page * LIMIT, total)} of {total} records</span>
              <div className="flex gap-2">
                <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="px-3 py-1.5 border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50 text-xs">Prev</button>
                <button disabled={page >= pages} onClick={() => setPage(p => p + 1)} className="px-3 py-1.5 border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50 text-xs">Next</button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Add Record Modal */}
      <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="Consultation: Create Case" size="lg">
        <form onSubmit={handleAdd} className="space-y-4">
          {formErr && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">{formErr}</div>}
          
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2 relative">
              <label className="block text-xs font-medium text-gray-700 mb-1">Enter Patient ID (10-digit) or Name for Consultation</label>
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input value={patientQuery} onChange={e => { setPatientQuery(e.target.value); setForm(f => ({ ...f, patientId: '' })); }}
                  placeholder="Type ID or Name to search..." className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
              </div>
              {patientResults.length > 0 && !form.patientId && (
                <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg">
                  {patientResults.map(p => (
                    <button key={p.id} type="button" onClick={() => { setForm(f => ({ ...f, patientId: p.id })); setPatientQuery(p.name); setPatientResults([]); }}
                      className="w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex justify-between">
                      <span className="font-medium text-gray-900">{p.name}</span><span className="text-gray-400 font-mono text-xs">{p.id.slice(0,8)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Record Type</label>
              <select value={form.recordType} onChange={e => setForm(f => ({ ...f, recordType: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm">
                {RECORD_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
            
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Title</label>
              <input required value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" />
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">Attach File (PDF, Image, etc.)</label>
              <input type="file" onChange={e => setSelectedFile(e.target.files?.[0] || null)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm file:mr-4 file:py-1 file:px-3 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">Notes / Text Content — will be AES-256-GCM encrypted before storage</label>
              <textarea required={!selectedFile} rows={4} value={form.content} onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm resize-none" placeholder="Enter optional notes or JSON..." />
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-2">Access Policy (CP-ABE)</label>
              <div className="flex flex-wrap gap-2">
                {POLICIES.map(p => (
                  <button key={p} type="button" onClick={() => togglePol(p)}
                    className={`px-3 py-1 text-xs rounded-full border transition-colors ${form.accessPolicy.includes(p) ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 text-gray-600 hover:border-blue-400'}`}>
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">Tags (comma separated)</label>
              <input value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" placeholder="urgent, review_needed" />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
            <button type="button" onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-xl hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={saving || !form.patientId} className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-60">
              {saving && <InlineSpinner />} Encrypt & Store
            </button>
          </div>
        </form>
      </Modal>

      {/* Access Denied Modal */}
      <Modal isOpen={!!accessError} onClose={() => setAccessError(null)} title="Access Denied">
        <div className="space-y-4">
          <div className="flex items-center gap-3 text-red-600"><ShieldOff size={24}/><p className="font-semibold">Access Denied</p></div>
          <p className="text-sm text-gray-600">{accessError?.message}</p>
          {accessError?.userAttributes && (
            <div className="bg-gray-50 rounded-xl p-4 space-y-2">
              <div className="flex flex-wrap gap-1"><span className="text-xs text-gray-500 mr-1">Your attributes:</span>{accessError.userAttributes.map(a=><Badge key={a} label={a} color="gray" size="xs"/>)}</div>
              {accessError.requiredPolicy && (
                <div className="flex flex-wrap gap-1"><span className="text-xs text-gray-500 mr-1">Required policy:</span>{accessError.requiredPolicy.map(a=><Badge key={a} label={a} color="red" size="xs"/>)}</div>
              )}
            </div>
          )}
          <p className="text-xs text-gray-400 italic">This access attempt has been logged to the audit trail.</p>
        </div>
      </Modal>

      {/* View Record Modal */}
      <Modal isOpen={!!viewRecord} onClose={() => setViewRecord(null)} title={viewRecord?.title ?? ''} size="lg">
        {viewRecord && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              {recordTypeBadge(viewRecord.recordType)}
              <Badge label="AES-256-GCM Decrypted Successfully" color="green" />
            </div>
            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-xs text-gray-400 mb-3 font-mono">IV: {viewRecord.iv}</p>
              <div className="space-y-2">
                {parseDecrypted(viewRecord.decryptedContent)?.map(([k,v]) => (
                  <div key={k} className="flex gap-3 text-sm">
                    <span className="text-gray-400 capitalize w-40 flex-shrink-0">{String(k).replace(/_/g,' ')}:</span>
                    <span className="text-gray-800 font-medium">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
