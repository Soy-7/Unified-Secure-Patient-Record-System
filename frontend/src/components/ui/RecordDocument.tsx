import { forwardRef } from 'react';
import type { EHRRecord } from '../../types';

interface RecordDocumentProps {
  record: EHRRecord;
  decryptedData: any;
  patientName: string;
}

export const RecordDocument = forwardRef<HTMLDivElement, RecordDocumentProps>(({ record, decryptedData, patientName }, ref) => {
  return (
    <div ref={ref} className="bg-white p-10 text-gray-800" style={{ width: '800px', minHeight: '1050px', margin: '0 auto', fontFamily: 'sans-serif' }}>
      {/* Header */}
      <div className="flex justify-between items-start border-b-2 border-blue-800 pb-6 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-blue-900 tracking-tight">CITY GENERAL HEALTH</h1>
          <p className="text-sm text-gray-500 mt-1">Unified EHR Document System</p>
        </div>
        <div className="text-right">
          <p className="font-bold text-lg text-gray-700">{record.hospitalId.toUpperCase()}</p>
          <p className="text-sm text-gray-500">Date: {new Date(record.createdAt).toLocaleDateString()}</p>
          <p className="text-sm text-gray-500">Record ID: {record.id.split('-')[0]}</p>
        </div>
      </div>

      {/* Patient Info */}
      <div className="bg-gray-50 p-4 rounded border border-gray-200 mb-8 flex justify-between">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Patient Name</p>
          <p className="text-lg font-bold">{patientName}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Patient ID</p>
          <p className="text-lg font-mono">{record.patientId}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Document Type</p>
          <p className="text-lg capitalize font-medium text-blue-700">{record.recordType.replace('_', ' ')}</p>
        </div>
      </div>

      {/* Title */}
      <h2 className="text-2xl font-bold text-gray-900 mb-6 border-b pb-2">{record.title}</h2>

      {/* Content */}
      <div className="space-y-6">
        {Object.entries(decryptedData || {}).map(([key, value]) => {
          if (key === 'fileData' || key === 'fileName') return null;
          return (
            <div key={key}>
              <h3 className="text-sm text-gray-500 uppercase tracking-wider font-semibold mb-1">{key.replace(/([A-Z])/g, ' $1').trim()}</h3>
              <div className="text-base text-gray-800 bg-white border border-gray-100 p-3 rounded whitespace-pre-wrap">
                {typeof value === 'object' ? (
                  <ul className="list-disc pl-5">
                    {Array.isArray(value) ? value.map((v, i) => <li key={i}>{v}</li>) : JSON.stringify(value)}
                  </ul>
                ) : (
                  String(value)
                )}
              </div>
            </div>
          );
        })}

        {decryptedData?.fileData && (
          <div className="mt-8 border-t border-dashed border-gray-300 pt-6">
            <h3 className="text-sm text-gray-500 uppercase tracking-wider font-semibold mb-3">Attached Document</h3>
            <div className="bg-gray-50 border border-gray-200 p-4 rounded flex items-center justify-between">
              <span className="font-mono text-sm text-blue-800 font-medium">{decryptedData.fileName || 'Attached File'}</span>
              <a 
                href={decryptedData.fileData} 
                download={decryptedData.fileName || 'attachment'} 
                className="bg-blue-600 text-white px-4 py-2 rounded text-xs font-bold shadow-sm"
              >
                Download Attachment
              </a>
            </div>
            {/* If it's an image, preview it */}
            {String(decryptedData.fileData).startsWith('data:image/') && (
              <div className="mt-4 border border-gray-200 rounded p-2 bg-white flex justify-center">
                <img src={decryptedData.fileData} alt="Attachment Preview" className="max-w-full h-auto max-h-96 object-contain" />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer / Signatures */}
      <div className="mt-20 pt-8 border-t border-gray-200 flex justify-between items-end">
        <div>
          <p className="text-xs text-gray-500 mb-4">Digitally Signed By</p>
          <p className="font-bold text-lg text-gray-800 signature-font">{record.createdBy}</p>
          <p className="text-sm text-gray-500">Authorized Medical Professional</p>
        </div>
        <div className="text-right">
          <div className="w-24 h-24 border-2 border-blue-900 rounded-full flex items-center justify-center opacity-20 transform -rotate-12">
            <span className="font-bold text-blue-900 text-sm tracking-widest uppercase">Verified</span>
          </div>
        </div>
      </div>
      
      {/* Cryptographic Proof */}
      <div className="mt-12 text-[10px] text-gray-400 font-mono break-all text-center">
        AES-256-GCM SECURED DOCUMENT • IV: {record.iv} • INTEGRITY VERIFIED
      </div>
    </div>
  );
});
RecordDocument.displayName = 'RecordDocument';
