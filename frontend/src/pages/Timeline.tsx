import { useEffect, useState, useRef } from 'react';
import { Clock, Eye, Lock, Activity, ShieldCheck, Download, Plus } from 'lucide-react';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import { RecordDocument } from '../components/ui/RecordDocument';
import { useAuthStore } from '../store/authStore';
import { recordTypeBadge, actionBadge, Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { PageSpinner, InlineSpinner } from '../components/ui/Spinner';
import client from '../api/client';
import type { EHRRecord, Patient, AuditLog, PaginatedRecords } from '../types';

export default function Timeline() {
  const { user } = useAuthStore();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [records, setRecords] = useState<EHRRecord[]>([]);
  const [loading, setLoading] = useState(true);
  
  // View Record State
  const [viewRecord, setViewRecord] = useState<EHRRecord | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const documentRef = useRef<HTMLDivElement>(null);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  
  // Audit Logs State
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);

  const [showLogsFor, setShowLogsFor] = useState<string | null>(null);
  const [logsLoading, setLogsLoading] = useState(false);

  // Add Record State
  const [showAdd, setShowAdd] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ recordType: 'diagnosis', title: '', content: '', recordDate: new Date().toISOString().split('T')[0] });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const loadTimeline = async (patId: string) => {
    const recRes = await client.get<PaginatedRecords>(`/records?patient_id=${patId}&limit=100`);
    const sorted = (recRes.data.records ?? []).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
    setRecords(sorted);
  };

  useEffect(() => {
    const init = async () => {
      try {
        if (!user || user.role !== 'patient') return;
        // 1. Find the patient document for this user (via search matching email/name, or just fetching all and filtering)
        const patRes = await client.get(`/patients?search=${user.name.split(' ')[0]}`);
        const found = patRes.data.patients?.find((p: Patient) => p.email === user.email) || patRes.data.patients?.[0];
        
        if (found) {
          setPatient(found);
          await loadTimeline(found.id);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [user]);

  const handleViewRecord = async (rec: EHRRecord) => {
    setViewLoading(true); setViewRecord(null);
    try {
      const { data } = await client.get<EHRRecord>(`/records/${rec.id}`);
      setViewRecord(data);
    } catch {
      alert("Error decrypting record.");
    } finally { setViewLoading(false); }
  };

  const handleViewLogs = async (resourceId: string, title: string) => {
    setLogsLoading(true); setShowLogsFor(title); setAuditLogs([]);
    try {
      const { data } = await client.get(`/audit?resource_id=${resourceId}&limit=50`);
      setAuditLogs(data.logs ?? []);
    } catch {
      alert("Error fetching logs.");
    } finally { setLogsLoading(false); }
  };

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

  const handleAddRecord = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patient || !user) return;
    setSaving(true);
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

      await client.post('/records', {
        patientId: patient.id,
        hospitalId: "patient-upload",
        recordType: form.recordType,
        title: form.title,
        content: JSON.stringify(contentObj),
        accessPolicy: ["patient"],
        tags: ["patient_uploaded"],
        recordDate: new Date(form.recordDate).toISOString()
      });
      setShowAdd(false);
      setForm({ recordType: 'diagnosis', title: '', content: '', recordDate: new Date().toISOString().split('T')[0] });
      setSelectedFile(null);
      await loadTimeline(patient.id);
    } catch {
      alert("Failed to upload document.");
    } finally {
      setSaving(false);
    }
  };



  if (loading) return <PageSpinner />;
  
  if (!patient) return (
    <div className="flex flex-col items-center justify-center py-20 text-gray-500">
      <Activity size={48} className="opacity-20 mb-4" />
      <h2 className="text-xl font-bold text-gray-800">No Patient Record Linked</h2>
      <p className="mt-2 text-sm">We could not find a patient record linked to your email address.</p>
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-900 to-indigo-900 rounded-2xl p-8 text-white shadow-lg relative overflow-hidden">
        <div className="relative z-10 flex justify-between items-start">
          <div>
            <Badge label="DigiLocker for Health" color="blue" />
            <h1 className="text-3xl font-bold mt-4 mb-2">My Health Timeline</h1>
            <p className="text-blue-100/80 text-sm max-w-xl">
              Welcome, {patient.name}. Your medical data is encrypted with AES-256-GCM. 
              You retain full ownership, and every access by a doctor or nurse is cryptographically logged below.
            </p>
          </div>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 bg-white/20 hover:bg-white/30 text-white text-sm font-medium px-4 py-2 rounded-xl transition-colors backdrop-blur-sm">
            <Plus size={15} /> Upload Document
          </button>
        </div>
        <Clock size={160} className="absolute -right-10 -bottom-10 text-white opacity-5" />
      </div>

      {/* Timeline */}
      <div className="relative pt-6 pb-12">
        <div className="absolute left-6 top-0 bottom-0 w-px bg-gray-200" />
        
        {records.length === 0 ? (
          <div className="pl-16 text-gray-500 text-sm">No medical records found in your timeline.</div>
        ) : (
          <div className="space-y-8">
            {records.map((r) => (
              <div key={r.id} className="relative pl-16">
                {/* Timeline Dot */}
                <div className="absolute left-[19px] top-5 w-3.5 h-3.5 bg-blue-600 rounded-full border-4 border-gray-50 shadow-sm" />
                
                {/* Card */}
                <div 
                  onClick={() => handleViewRecord(r)}
                  className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden hover:shadow-md hover:border-blue-300 transition-all cursor-pointer group"
                >
                  <div className="px-5 py-4 flex flex-wrap gap-4 items-start justify-between border-b border-gray-50 bg-gray-50/50 group-hover:bg-blue-50/30 transition-colors">
                    <div>
                      <div className="flex items-center gap-2 mb-1.5">
                        {recordTypeBadge(r.recordType)}
                        <span className="text-xs text-gray-400 font-mono">{new Date(r.createdAt).toLocaleDateString('en-US', { year:'numeric', month:'short', day:'numeric' })}</span>
                      </div>
                      <h3 className="font-bold text-gray-900 text-base group-hover:text-blue-700 transition-colors">{r.title}</h3>
                      <p className="text-xs text-gray-500 mt-1">Created by {r.createdBy} • Hospital: {r.hospitalId}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button disabled={viewLoading}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-lg text-xs font-medium transition-colors">
                        <Lock size={12} /> View Encrypted Content
                      </button>
                      <button onClick={(e) => { e.stopPropagation(); handleViewLogs(r.id, r.title); }}
                        className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-200 text-gray-600 hover:bg-gray-50 hover:border-gray-300 rounded-lg text-xs font-medium transition-colors">
                        <Eye size={12} /> Access Logs
                      </button>
                    </div>
                  </div>
                  {/* Preview Footer */}
                  <div className="px-5 py-3 bg-white text-xs text-gray-400 font-mono flex items-center justify-between">
                    <span>IV: {r.iv}</span>
                    <span className="flex items-center gap-1 text-green-600"><ShieldCheck size={12}/> Secured</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

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

      {/* Logs Modal */}
      <Modal isOpen={!!showLogsFor} onClose={() => setShowLogsFor(null)} title={`Access Logs: ${showLogsFor}`} size="lg">
        <div className="space-y-4">
          <p className="text-sm text-gray-600">Every decryption or access attempt is recorded here immutably.</p>
          {logsLoading ? <div className="py-10"><PageSpinner /></div> : auditLogs.length === 0 ? (
            <div className="py-10 text-center text-gray-400 text-sm">No access logs found for this record.</div>
          ) : (
            <div className="overflow-x-auto bg-white border border-gray-100 rounded-xl">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                  <tr>{['Time', 'User', 'Action', 'Details'].map(h=><th key={h} className="text-left px-4 py-2.5">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {auditLogs.map((l, i) => (
                    <tr key={l.id} className={`border-t border-gray-50 ${i%2===1?'bg-gray-50/40':''}`}>
                      <td className="px-4 py-2.5 text-xs text-gray-500 font-mono whitespace-nowrap">{new Date(l.timestamp).toLocaleString('en-IN', {dateStyle:'short',timeStyle:'short'})}</td>
                      <td className="px-4 py-2.5 font-medium text-gray-800 text-xs">{l.userName}</td>
                      <td className="px-4 py-2.5">{actionBadge(l.action)}</td>
                      <td className="px-4 py-2.5 text-xs text-gray-500">{l.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Modal>

      {/* Add Document Modal */}
      <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="Upload Secure Document" size="md">
        <form onSubmit={handleAddRecord} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Document Type</label>
            <select value={form.recordType} onChange={e => setForm(f => ({ ...f, recordType: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm">
              {['diagnosis','prescription','lab_result','imaging','discharge_summary','consultation'].map(t => (
                <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Document Title</label>
            <input required value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              placeholder="e.g. Blood Test Results"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Date of Document</label>
            <input required type="date" value={form.recordDate} onChange={e => setForm(f => ({ ...f, recordDate: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Attach File (PDF, Image, etc.)</label>
            <input type="file" onChange={e => setSelectedFile(e.target.files?.[0] || null)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm file:mr-4 file:py-1 file:px-3 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Notes / Text Content</label>
            <textarea rows={3} value={form.content} onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm resize-none" placeholder="Enter optional notes..." />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-xl hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={saving} className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-60">
              {saving && <InlineSpinner />} Encrypt & Store
            </button>
          </div>
        </form>
      </Modal>

    </div>
  );
}
