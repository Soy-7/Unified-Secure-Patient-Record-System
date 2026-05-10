// ─── Shared TypeScript types ────────────────────────────────────────────────

export type UserRole = 'admin' | 'doctor' | 'nurse' | 'patient';

export interface UserResponse {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  hospitalId: string;
  department?: string;
  attributes: string[];
  publicKey: string;
  createdAt: string;
  isRevoked: boolean;
}

export interface Hospital {
  id: string;
  name: string;
  city: string;
  apiEndpoint: string;
  tlsCertFingerprint: string;
  createdAt: string;
}

export interface Patient {
  id: string;
  soundexCode: string;
  name: string;
  dob: string;
  gender: string;
  bloodGroup: string;
  phone: string;
  email?: string;
  address: string;
  primaryHospitalId: string;
  linkedHospitalIds: string[];
  emergencyContact: Record<string, string>;
  createdAt: string;
  updatedAt: string;
  phoneticMatch?: boolean;
}

export type RecordType =
  | 'diagnosis' | 'prescription' | 'lab_result'
  | 'imaging'   | 'discharge_summary' | 'consultation';

export interface EHRRecord {
  id: string;
  patientId: string;
  hospitalId: string;
  createdBy: string;
  recordType: RecordType;
  title: string;
  encryptedContent: string;
  iv: string;
  accessPolicy: string[];
  tags: string[];
  createdAt: string;
  updatedAt: string;
  isFlagged: boolean;
  status: string;
  decryptedContent?: string | null;
}

export interface AuditLog {
  id: string;
  userId: string;
  userName: string;
  userRole: string;
  action: string;
  resourceType: string;
  resourceId: string;
  hospitalId: string;
  ipAddress: string;
  timestamp: string;
  hash: string;
  prevHash: string;
  details: string;
}

export interface Consent {
  id: string;
  patientId: string;
  grantedTo: string;
  grantedToType: 'user' | 'hospital';
  recordIds: string[];
  permissions: string[];
  validFrom: string;
  validUntil: string;
  isRevoked: boolean;
  revokedAt?: string | null;
  createdAt: string;
}

export type ExchangeStatus = 'pending' | 'approved' | 'rejected' | 'completed';

export interface ExchangeRequest {
  id: string;
  fromHospitalId: string;
  toHospitalId: string;
  patientId: string;
  requestedBy: string;
  status: ExchangeStatus;
  recordTypes: string[];
  purpose: string;
  encryptedPayload?: string | null;
  createdAt: string;
  resolvedAt?: string | null;
}

export interface AuditVerifyResult {
  total: number;
  verified: number;
  failed: number;
  intact: boolean;
  brokenAt?: string | null;
}

export interface PaginatedPatients {
  patients: Patient[];
  total: number;
  page: number;
  pages: number;
}

export interface PaginatedRecords {
  records: EHRRecord[];
  total: number;
  page: number;
  pages: number;
}

export interface PaginatedAudit {
  logs: AuditLog[];
  total: number;
  page: number;
  pages: number;
}

export interface PaginatedUsers {
  users: UserResponse[];
  total: number;
  page: number;
  pages: number;
}
