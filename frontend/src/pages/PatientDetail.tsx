import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, ShieldOff, CheckCircle, Lock, Trash2, Plus,
  FileText, AlertCircle, Download,
} from 'lucide-react';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import { RecordDocument } from '../components/ui/RecordDocument';
import { useAuthStore } from '../store/authStore';
import { recordTypeBadge, statusBadge, Badge, actionBadge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { PageSpinner, InlineSpinner } from '../components/ui/Spinner';
import client from '../api/client';
import type {
  Patient, EHRRecord, Consent, ExchangeRequest,
  AuditLog, Hospital, AuditVerifyResult,
} from '../types';

type Tab = 'records' | 'consents' | 'history' | 'exchange';

const RECORD_TYPES = ['diagnosis','prescription','lab_result','imaging','discharge_summary','consultation'];

export default function PatientDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const [patient, setPatient]     = useState<Patient | null>(null);
  const [records, setRecords]     = useState<EHRRecord[]>([]);
  const [consents, setConsents]   = useState<Consent[]>([]);
  const [exchanges, setExchanges] = useState<ExchangeRequest[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading]     = useState(true);
  const [tab, setTab]             = useState<Tab>('records');

  // Record view state
  const [viewRecord, setViewRecord]   = useState<EHRRecord | null>(null);
  const [accessError, setAccessError] = useState<{ message: string; userAttributes?: string[]; requiredPolicy?: string[] } | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const documentRef = useRef<HTMLDivElement>(null);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);

  // Audit verify
  const [verifyResult, setVerifyResult]   = useState<AuditVerifyResult | null>(null);
  const [verifying, setVerifying]         = useState(false);

  // Consent modal
  const [showGrant, setShowGrant]   = useState(false);
  const [grantForm, setGrantForm]   = useState({ grantedTo: '', grantedToType: 'user', recordIds: '*', permissions: ['read'], validFrom: '', validUntil: '' });
  const [grantSaving, setGrantSaving] = useState(false);

  // Exchange modal
  const [showExchange, setShowExchange] = useState(false);
  const [exForm, setExForm] = useState({ toHospitalId: '', recordTypes: [] as string[], purpose: '' });
  const [exSaving, setExSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    Promise.allSettled([
      client.get<Patient>(`/patients/${id}`).then(r => setPatient(r.data)),
      client.get(`/records?patient_id=${id}&limit=50`).then(r => setRecords(r.data.records ?? [])),
      client.get<Consent[]>(`/consents/patient/${id}`).then(r => setConsents(r.data ?? [])),
      client.get<ExchangeRequest[]>('/exchange').then(r => setExchanges((r.data ?? []).filter((e: ExchangeRequest) => e.patientId === id))),
      client.get<Hospital[]>('/hospitals').then(r => setHospitals(r.data ?? [])),
      (user?.role === 'admin' ? client.get('/audit?limit=20').then(r => setAuditLogs(r.data.logs ?? [])) : Promise.resolve()),
    ]).finally(() => setLoading(false));
  }, [id, user]);

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

  const verifyChain = async () => {
    setVerifying(true);
    try { const { data } = await client.get<AuditVerifyResult>('/audit/verify'); setVerifyResult(data); }
    finally { setVerifying(false); }
  };

  const revokeConsent = async (cid: string) => {
    await client.delete(`/consents/${cid}`);
    setConsents(cs => cs.map(c => c.id === cid ? { ...c, isRevoked: true } : c));
  };

  const grantConsent = async (e: React.FormEvent) => {
    e.preventDefault(); setGrantSaving(true);
    try {
      await client.post('/consents', { ...grantForm, patientId: id, recordIds: grantForm.recordIds === '*' ? ['*'] : grantForm.recordIds.split(',').map(s=>s.trim()) });
      const r = await client.get<Consent[]>(`/consents/patient/${id}`); setConsents(r.data ?? []);
      setShowGrant(false);
    } finally { setGrantSaving(false); }
  };

  const submitExchange = async (e: React.FormEvent) => {
    e.preventDefault(); setExSaving(true);
    try {
      await client.post('/exchange', { ...exForm, patientId: id, fromHospitalId: user?.hospitalId });
      const r = await client.get<ExchangeRequest[]>('/exchange'); setExchanges((r.data ?? []).filter((x: ExchangeRequest) => x.patientId === id));
      setShowExchange(false);
    } finally { setExSaving(false); }
  };

  const hospName = (hid: string) => hospitals.find(h => h.id === hid)?.name ?? hid;
  const toggleRt = (t: string) => setExForm(f => ({ ...f, recordTypes: f.recordTypes.includes(t) ? f.recordTypes.filter(x=>x!==t) : [...f.recordTypes, t] }));

  const handleDownloadPdf = async () => {
    if (!documentRef.current || !viewRecord) return;
    setIsGeneratingPdf(true);
    try {
      const canvas = await html2canvas(documentRef.current, { scale: 2 });
      const imgData = canvas.toDataURL('image/jpeg', 1.0);
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = (canvas.height * pdfWidth) / canvas.width;
      pdf.addImage(imgData, 'JPEG', 0, 0, pdfWidth, pdfHeight);
      pdf.save(`EHR_${viewRecord.patientId}_${viewRecord.recordType}.pdf`);
    } catch (err) {
      console.error(err);
      alert("Failed to generate PDF");
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  const handleApprove = async (rec: EHRRecord) => {
    try {
      await client.put(`/records/${rec.id}/status?status_val=approved`);
      const r = await client.get(`/records?patient_id=${id}&limit=50`);
      setRecords(r.data.records ?? []);
    } catch {
      alert("Failed to approve record.");
    }
  };

  if (loading) return <PageSpinner />;
  if (!patient) return <div className="text-center py-20 text-gray-400">Patient not found.</div>;

  const TABS: { key: Tab; label: string }[] = [
    { key: 'records',  label: `Records (${records.length})` },
    { key: 'consents', label: `Consents (${consents.length})` },
    { key: 'history',  label: 'Access History' },
    { key: 'exchange', label: `Exchange (${exchanges.length})` },
  ];

  return (
    <div className="space-y-5">
      <button onClick={() => navigate('/patients')} className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800">
        <ArrowLeft size={15} /> Back to Patients
      </button>

      {/* Patient card */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{patient.name}</h2>
            <p className="text-gray-400 text-xs font-mono mt-1">{patient.id}</p>
          </div>
          <div className="flex gap-2">
            <Badge label={patient.bloodGroup} color="red" />
            <Badge label={patient.gender} color="blue" />
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5">
          {[
            ['Date of Birth', patient.dob],
            ['Primary Hospital', hospName(patient.primaryHospitalId)],
            ['Phone', patient.phone],
            ['Linked Hospitals', patient.linkedHospitalIds.join(', ') || '—'],
          ].map(([k, v]) => (
            <div key={k}>
              <p className="text-xs text-gray-400 uppercase font-medium">{k}</p>
              <p className="text-sm text-gray-800 font-medium mt-0.5">{v}</p>
            </div>
          ))}
        </div>
        {Object.keys(patient.emergencyContact).length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-100 text-xs text-gray-500">
            <span className="font-medium text-gray-700">Emergency: </span>
            {Object.entries(patient.emergencyContact).map(([k,v]) => `${k}: ${v}`).join(' · ')}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 gap-0">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-5 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}>{t.label}</button>
        ))}
      </div>

      {/* RECORDS TAB */}
      {tab === 'records' && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          {records.length === 0 ? (
            <div className="flex flex-col items-center py-12 text-gray-400">
              <FileText size={32} className="opacity-30 mb-2" /><p className="text-sm">No records found.</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                <tr>{['Type','Title','Created By','Date','Policy','Status',''].map(h=><th key={h} className="text-left px-5 py-3">{h}</th>)}</tr>
              </thead>
              <tbody>
                {records.map((r,i) => (
                  <tr key={r.id} className={`border-t border-gray-50 hover:bg-blue-50/20 ${i%2===1?'bg-gray-50/40':''}`}>
                    <td className="px-5 py-3">{recordTypeBadge(r.recordType)}</td>
                    <td className="px-5 py-3 font-medium text-gray-800">{r.title}</td>
                    <td className="px-5 py-3 text-gray-400 text-xs">{r.createdBy.slice(0,16)}</td>
                    <td className="px-5 py-3 text-gray-400 text-xs">{new Date(r.createdAt).toLocaleDateString()}</td>
                    <td className="px-5 py-3 flex flex-wrap gap-1">{r.accessPolicy.slice(0,3).map(p=><Badge key={p} label={p} color="gray" size="xs" />)}</td>
                    <td className="px-5 py-3">{statusBadge(r.status)}</td>
                    <td className="px-5 py-3 flex gap-2">
                      {r.status === 'pending' && user?.role !== 'doctor' && (
                        <button onClick={() => handleApprove(r)} className="text-green-600 hover:text-green-800 text-xs font-medium bg-green-50 px-2 py-1 rounded">Approve</button>
                      )}
                      <button disabled={viewLoading} onClick={() => viewRecordDetail(r)}
                        className="flex items-center gap-1 text-blue-600 hover:text-blue-800 text-xs font-medium disabled:opacity-50">
                        <Lock size={12}/><span>View</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* CONSENTS TAB */}
      {tab === 'consents' && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setShowGrant(true)}
              className="flex items-center gap-2 bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded-xl hover:bg-blue-700">
              <Plus size={14}/> Grant Consent
            </button>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            {consents.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-gray-400"><p className="text-sm">No consents granted.</p></div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                  <tr>{['Granted To','Type','Permissions','Valid Until','Status',''].map(h=><th key={h} className="text-left px-5 py-3">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {consents.map((c,i) => (
                    <tr key={c.id} className={`border-t border-gray-50 hover:bg-gray-50/60 ${i%2===1?'bg-gray-50/40':''}`}>
                      <td className="px-5 py-3 font-mono text-xs text-gray-600">{c.grantedTo.slice(0,16)}</td>
                      <td className="px-5 py-3"><Badge label={c.grantedToType} color="blue" /></td>
                      <td className="px-5 py-3 text-xs text-gray-500">{c.permissions.join(', ')}</td>
                      <td className="px-5 py-3 text-xs text-gray-400">{new Date(c.validUntil).toLocaleDateString()}</td>
                      <td className="px-5 py-3">{statusBadge(c.isRevoked ? 'revoked' : 'active')}</td>
                      <td className="px-5 py-3">
                        {!c.isRevoked && (
                          <button onClick={() => revokeConsent(c.id)} className="flex items-center gap-1 text-red-500 hover:text-red-700 text-xs">
                            <Trash2 size={12}/> Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* HISTORY TAB */}
      {tab === 'history' && (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <button onClick={verifyChain} disabled={verifying}
              className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-xl text-sm hover:bg-gray-50">
              {verifying ? <InlineSpinner /> : <CheckCircle size={15}/>} Verify Audit Chain
            </button>
          </div>
          {verifyResult && (
            <div className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-medium ${verifyResult.intact ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
              {verifyResult.intact
                ? <><CheckCircle size={16}/> Chain Intact — {verifyResult.total} entries verified, no tampering detected</>
                : <><ShieldOff size={16}/> Tampering Detected — chain broken at entry {verifyResult.brokenAt}</>}
            </div>
          )}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            {auditLogs.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-gray-400"><AlertCircle size={28} className="opacity-30 mb-2"/><p className="text-sm">No access history available.</p></div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                  <tr>{['Timestamp','User','Action','Details','IP'].map(h=><th key={h} className="text-left px-5 py-3">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {auditLogs.map((l,i) => (
                    <tr key={l.id} className={`border-t border-gray-50 hover:bg-gray-50/60 ${i%2===1?'bg-gray-50/40':''}`}>
                      <td className="px-5 py-3 text-gray-400 text-xs font-mono">{new Date(l.timestamp).toLocaleString('en-IN',{dateStyle:'short',timeStyle:'short'})}</td>
                      <td className="px-5 py-3 text-gray-800 text-xs">{l.userName}</td>
                      <td className="px-5 py-3">{actionBadge(l.action)}</td>
                      <td className="px-5 py-3 text-gray-400 text-xs truncate max-w-xs">{l.details}</td>
                      <td className="px-5 py-3 text-gray-400 font-mono text-xs">{l.ipAddress}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* EXCHANGE TAB */}
      {tab === 'exchange' && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setShowExchange(true)}
              className="flex items-center gap-2 bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded-xl hover:bg-blue-700">
              <Plus size={14}/> New Exchange Request
            </button>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            {exchanges.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-gray-400"><p className="text-sm">No exchange requests for this patient.</p></div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                  <tr>{['From','To','Status','Types','Purpose','Date'].map(h=><th key={h} className="text-left px-5 py-3">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {exchanges.map((x,i) => (
                    <tr key={x.id} className={`border-t border-gray-50 hover:bg-gray-50/60 ${i%2===1?'bg-gray-50/40':''}`}>
                      <td className="px-5 py-3 text-xs text-gray-500">{hospName(x.fromHospitalId)}</td>
                      <td className="px-5 py-3 text-xs text-gray-500">{hospName(x.toHospitalId)}</td>
                      <td className="px-5 py-3">{statusBadge(x.status)}</td>
                      <td className="px-5 py-3 text-xs text-gray-400">{x.recordTypes.join(', ')}</td>
                      <td className="px-5 py-3 text-xs text-gray-500 truncate max-w-xs">{x.purpose}</td>
                      <td className="px-5 py-3 text-xs text-gray-400">{new Date(x.createdAt).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

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
      <Modal isOpen={!!viewRecord} onClose={() => setViewRecord(null)} title="Medical Document" size="lg">
        {viewRecord && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 bg-gray-50 p-3 rounded-lg border border-gray-200">
              <div className="flex gap-2">
                {recordTypeBadge(viewRecord.recordType)}
                <Badge label="AES-256-GCM Decrypted" color="green" />
              </div>
              <button 
                onClick={handleDownloadPdf} 
                disabled={isGeneratingPdf}
                className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                <Download size={16} />
                {isGeneratingPdf ? "Generating PDF..." : "Download as PDF"}
              </button>
            </div>
            
            {/* The Document View (Scaled down for modal, actual size used for PDF) */}
            <div className="bg-gray-200 p-4 rounded-xl max-h-[60vh] overflow-y-auto overflow-x-auto flex justify-center">
              <div className="transform scale-[0.85] origin-top">
                <RecordDocument 
                  ref={documentRef} 
                  record={viewRecord} 
                  decryptedData={viewRecord.decryptedContent ? JSON.parse(viewRecord.decryptedContent) : {}} 
                  patientName={patient?.name || ''} 
                />
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Grant Consent Modal */}
      <Modal isOpen={showGrant} onClose={() => setShowGrant(false)} title="Grant Consent" size="md">
        <form onSubmit={grantConsent} className="space-y-3">
          {[['Granted To (User/Hospital ID)','grantedTo','text'],['Valid From','validFrom','date'],['Valid Until','validUntil','date']].map(([label,field,type]) => (
            <div key={field}>
              <label className="block text-xs font-medium text-gray-700 mb-1">{label}</label>
              <input type={type} required value={(grantForm as any)[field]}
                onChange={e => setGrantForm(f => ({ ...f, [field]: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"/>
            </div>
          ))}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Granted To Type</label>
            <select value={grantForm.grantedToType} onChange={e => setGrantForm(f=>({...f,grantedToType:e.target.value}))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm">
              <option value="user">User</option><option value="hospital">Hospital</option>
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={() => setShowGrant(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-xl hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={grantSaving} className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-60">
              {grantSaving && <InlineSpinner />} Grant
            </button>
          </div>
        </form>
      </Modal>

      {/* New Exchange Modal */}
      <Modal isOpen={showExchange} onClose={() => setShowExchange(false)} title="New Exchange Request" size="md">
        <form onSubmit={submitExchange} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Target Hospital</label>
            <select required value={exForm.toHospitalId} onChange={e => setExForm(f=>({...f,toHospitalId:e.target.value}))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm">
              <option value="">Select hospital…</option>
              {hospitals.filter(h=>h.id!==user?.hospitalId).map(h=><option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-2">Record Types</label>
            <div className="flex flex-wrap gap-2">
              {RECORD_TYPES.map(t => (
                <button key={t} type="button" onClick={() => toggleRt(t)}
                  className={`px-3 py-1 text-xs rounded-full border transition-colors ${exForm.recordTypes.includes(t)?'bg-blue-600 text-white border-blue-600':'border-gray-200 text-gray-600 hover:border-blue-400'}`}>
                  {t.replace(/_/g,' ')}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Purpose</label>
            <textarea required rows={3} value={exForm.purpose} onChange={e => setExForm(f=>({...f,purpose:e.target.value}))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm resize-none"/>
          </div>
          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={() => setShowExchange(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-xl hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={exSaving} className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-60">
              {exSaving && <InlineSpinner />} Submit
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
