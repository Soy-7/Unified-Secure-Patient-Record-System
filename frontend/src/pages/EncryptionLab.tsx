import { useState, useEffect } from 'react';
import { Lock, ArrowRight, ShieldCheck, AlertCircle, ShieldOff } from 'lucide-react';
import client from '../api/client';
import { Badge, actionBadge } from '../components/ui/Badge';
import { InlineSpinner } from '../components/ui/Spinner';
import type { AuditLog, AuditVerifyResult } from '../types';

export default function EncryptionLab() {
  // Panel A
  const [aesText, setAesText] = useState('Patient resting heart rate 72 bpm. No abnormalities detected.');
  const [aesLoading, setAesLoading] = useState(false);
  const [aesRes, setAesRes] = useState<{ ciphertext: string, iv: string, algorithm: string, keyLength: number } | null>(null);
  const [aesDecrypted, setAesDecrypted] = useState<string | null>(null);

  // Panel B
  const [ecdhLoading, setEcdhLoading] = useState(false);
  const [ecdhRes, setEcdhRes] = useState<{ hospitalAFingerprint: string, hospitalBFingerprint: string, sharedSecretMatch: boolean, sharedSecretPreview: string } | null>(null);

  // Panel C
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [verifyRes, setVerifyRes] = useState<AuditVerifyResult | null>(null);
  const [tampered, setTampered] = useState(false);

  useEffect(() => {
    client.get('/audit?limit=5').then(r => setLogs(r.data.logs ?? [])).catch(() => {});
  }, []);

  const runAesEncrypt = async () => {
    setAesLoading(true); setAesDecrypted(null);
    try {
      const { data } = await client.post('/crypto/encrypt-demo', { text: aesText });
      setAesRes(data);
    } finally { setAesLoading(false); }
  };

  const runAesDecrypt = async () => {
    if (!aesRes) return;
    setAesLoading(true);
    try {
      const { data } = await client.post('/crypto/decrypt-demo', { ciphertext: aesRes.ciphertext, iv: aesRes.iv });
      setAesDecrypted(data.plaintext);
    } finally { setAesLoading(false); }
  };

  const runEcdh = async () => {
    setEcdhLoading(true);
    try {
      const { data } = await client.post('/crypto/ecdh-demo');
      setEcdhRes(data);
    } finally { setEcdhLoading(false); }
  };

  const runVerify = async () => {
    if (tampered) {
      setVerifyRes({ intact: false, total: 5, verified: 2, failed: 3, brokenAt: logs[2]?.id });
      return;
    }
    try {
      const { data } = await client.get('/audit/verify');
      setVerifyRes(data);
    } catch { /* ignore */ }
  };

  const simulateTamper = () => {
    setTampered(true); setVerifyRes(null);
    const newLogs = [...logs];
    if (newLogs[2]) {
      newLogs[2] = { ...newLogs[2], action: 'TAMPERED' as string };
    }
    setLogs(newLogs);
  };

  const restoreChain = () => {
    setTampered(false); setVerifyRes(null);
    client.get('/audit?limit=5').then(r => setLogs(r.data.logs ?? [])).catch(() => {});
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      
      {/* PANEL A: AES */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden flex flex-col">
        <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center gap-2">
          <Lock size={18} className="text-blue-600" />
          <h3 className="font-semibold text-gray-900">AES-256-GCM Live Encryption</h3>
        </div>
        <div className="p-5 flex-1 flex flex-col space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Enter medical text</label>
            <textarea rows={3} value={aesText} onChange={e => setAesText(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm resize-none focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <button onClick={runAesEncrypt} disabled={aesLoading || !aesText}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-lg text-sm transition-colors flex justify-center items-center gap-2 disabled:opacity-50">
            {aesLoading ? <InlineSpinner /> : 'Encrypt Content'}
          </button>
          
          {aesRes && (
            <div className="bg-gray-50 rounded-lg p-3 space-y-2 border border-gray-100 mt-2">
              <div className="flex gap-2">
                <Badge label={`Algorithm: ${aesRes.algorithm}`} color="blue" size="xs" />
                <Badge label={`Key Length: ${aesRes.keyLength} bits`} color="gray" size="xs" />
              </div>
              <div>
                <p className="text-[10px] text-gray-500 font-medium uppercase mb-0.5">Initialization Vector (IV)</p>
                <p className="text-xs font-mono text-gray-600 break-all">{aesRes.iv}</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500 font-medium uppercase mb-0.5">Ciphertext (Truncated)</p>
                <div className="h-16 overflow-y-auto bg-white border border-gray-200 rounded p-2 text-xs font-mono text-gray-600 break-all">
                  {aesRes.ciphertext}
                </div>
              </div>
              
              {!aesDecrypted ? (
                <button onClick={runAesDecrypt} disabled={aesLoading}
                  className="w-full mt-2 bg-gray-800 hover:bg-gray-900 text-white font-medium py-1.5 rounded-lg text-sm transition-colors flex justify-center items-center gap-2">
                  {aesLoading ? <InlineSpinner /> : 'Decrypt Content'}
                </button>
              ) : (
                <div className="mt-3 p-2 bg-green-50 border border-green-200 rounded-lg">
                  <div className="flex items-center gap-1.5 text-green-700 text-sm font-medium mb-1">
                    <ShieldCheck size={16} /> Decrypted Successfully
                  </div>
                  <p className="text-sm text-green-900">{aesDecrypted}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* PANEL B: ECDH */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden flex flex-col">
        <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center gap-2">
          <ArrowRight size={18} className="text-purple-600" />
          <h3 className="font-semibold text-gray-900">ECDH P-256 Key Exchange</h3>
        </div>
        <div className="p-5 flex-1 flex flex-col space-y-4">
          <p className="text-sm text-gray-600 leading-relaxed">
            Demonstrates how two hospitals securely establish a shared encryption key without transmitting the key itself.
          </p>
          <button onClick={runEcdh} disabled={ecdhLoading}
            className="w-full bg-purple-600 hover:bg-purple-700 text-white font-medium py-2 rounded-lg text-sm transition-colors flex justify-center items-center gap-2 disabled:opacity-50">
            {ecdhLoading ? <InlineSpinner /> : 'Generate Key Exchange'}
          </button>

          {ecdhRes && (
            <div className="space-y-4 mt-2">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                  <p className="text-xs font-semibold text-gray-700 mb-1">Hospital A</p>
                  <p className="text-[10px] text-gray-500 font-mono break-all">{ecdhRes.hospitalAFingerprint}</p>
                </div>
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                  <p className="text-xs font-semibold text-gray-700 mb-1">Hospital B</p>
                  <p className="text-[10px] text-gray-500 font-mono break-all">{ecdhRes.hospitalBFingerprint}</p>
                </div>
              </div>
              <div className="flex justify-center -my-3 relative z-10">
                <div className="bg-white px-2 py-0.5 text-[10px] font-medium uppercase text-gray-400">Key Agreement</div>
              </div>
              {ecdhRes.sharedSecretMatch && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                  <p className="text-sm font-medium text-green-700 flex items-center justify-center gap-1.5 mb-1">
                    <ShieldCheck size={16} /> Both hospitals derived identical key
                  </p>
                  <p className="text-[10px] text-green-600/70 font-mono break-all">Secret: {ecdhRes.sharedSecretPreview}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* PANEL C: Audit Chain */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden flex flex-col">
        <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck size={18} className="text-teal-600" />
            <h3 className="font-semibold text-gray-900">Audit Chain Integrity</h3>
          </div>
          {tampered && <Badge label="Compromised" color="red" size="xs" />}
        </div>
        <div className="p-5 flex-1 flex flex-col space-y-4">
          <div className="flex gap-2">
            <button onClick={runVerify} className="flex-1 bg-gray-800 hover:bg-gray-900 text-white font-medium py-1.5 rounded-lg text-sm transition-colors">Verify Chain</button>
            <button onClick={tampered ? restoreChain : simulateTamper} className={`flex-1 font-medium py-1.5 rounded-lg text-sm transition-colors ${tampered ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-red-100 text-red-700 hover:bg-red-200'}`}>
              {tampered ? 'Restore' : 'Simulate Tampering'}
            </button>
          </div>

          {verifyRes && (
            <div className={`p-2.5 rounded-lg text-sm font-medium flex items-start gap-2 ${verifyRes.intact ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
              {verifyRes.intact ? <ShieldCheck size={18} className="flex-shrink-0" /> : <ShieldOff size={18} className="flex-shrink-0 mt-0.5" />}
              <span>
                {verifyRes.intact 
                  ? `Chain Intact — all ${verifyRes.total} entries cryptographically verified.` 
                  : `Chain integrity compromised — entries invalidated starting at ${verifyRes.brokenAt?.slice(0,8)}.`}
              </span>
            </div>
          )}

          <div className="flex-1 space-y-0 relative before:absolute before:inset-y-0 before:left-3.5 before:w-px before:bg-gray-200 mt-2">
            {logs.slice(0, 5).map((l, i) => {
              const isTamperedRow = tampered && i === 2;
              const isBrokenAfter = tampered && i < 2; // Newer items visually below it break
              return (
                <div key={l.id} className="relative pl-10 py-3">
                  <div className={`absolute left-2.5 w-2.5 h-2.5 rounded-full top-4 border-2 border-white ${isTamperedRow ? 'bg-red-500' : isBrokenAfter ? 'bg-gray-300' : 'bg-teal-500'}`} />
                  <div className="flex items-center gap-2 mb-1">
                    {isTamperedRow ? <Badge label="TAMPERED" color="red" size="xs" /> : actionBadge(l.action)}
                    <span className="text-[10px] text-gray-400 font-mono">{new Date(l.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className="space-y-0.5">
                    <p className="text-[10px] text-gray-500 font-mono">Hash: <span className={isTamperedRow ? 'text-red-500' : ''}>{l.hash.slice(0, 16)}...</span></p>
                    <p className="text-[10px] text-gray-400 font-mono">Prev: {l.prevHash.slice(0, 16)}...</p>
                  </div>
                  {isTamperedRow && <p className="text-xs text-red-600 font-medium mt-1 flex items-center gap-1"><AlertCircle size={12}/> MODIFIED</p>}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
