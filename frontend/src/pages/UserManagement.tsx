import React, { useEffect, useState } from 'react';
import { Plus, UserX, Edit2 } from 'lucide-react';
import { roleBadge, Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { PageSpinner, InlineSpinner } from '../components/ui/Spinner';
import client from '../api/client';
import type { UserResponse, Hospital, PaginatedUsers } from '../types';

export default function UserManagement() {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);

  const [showAdd, setShowAdd] = useState(false);
  const [addSaving, setAddSaving] = useState(false);
  const [addForm, setAddForm] = useState({ name:'', email:'', password:'', role:'doctor', hospitalId:'', department:'', attributes:'' });

  const [showEdit, setShowEdit] = useState<UserResponse | null>(null);
  const [editAttrs, setEditAttrs] = useState('');
  const [editSaving, setEditSaving] = useState(false);

  const [showRevoke, setShowRevoke] = useState<UserResponse | null>(null);
  const [revokeReason, setRevokeReason] = useState('');
  const [revokeSaving, setRevokeSaving] = useState(false);

  const [msg, setMsg] = useState('');

  const load = async () => {
    try {
      const [uRes, hRes] = await Promise.all([
        client.get<PaginatedUsers>('/users?limit=100'),
        client.get<Hospital[]>('/hospitals')
      ]);
      setUsers(uRes.data.users ?? []);
      setHospitals(hRes.data ?? []);
      if (!addForm.hospitalId && hRes.data?.[0]) {
        setAddForm(f => ({ ...f, hospitalId: hRes.data[0].id }));
      }
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault(); setAddSaving(true);
    try {
      await client.post('/users', {
        ...addForm,
        attributes: addForm.attributes.split(',').map(s=>s.trim()).filter(Boolean)
      });
      setShowAdd(false); setMsg('User created successfully.');
      load();
    } catch { alert('Failed to create user'); }
    finally { setAddSaving(false); }
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault(); if (!showEdit) return;
    setEditSaving(true);
    try {
      await client.put(`/users/${showEdit.id}`, {
        attributes: editAttrs.split(',').map(s=>s.trim()).filter(Boolean)
      });
      setShowEdit(null); setMsg('Attributes updated.');
      load();
    } finally { setEditSaving(false); }
  };

  const handleRevoke = async (e: React.FormEvent) => {
    e.preventDefault(); if (!showRevoke) return;
    setRevokeSaving(true);
    try {
      await client.post(`/users/${showRevoke.id}/revoke`, { reason: revokeReason });
      setShowRevoke(null); setMsg('User access revoked.');
      load();
    } finally { setRevokeSaving(false); }
  };

  const hospName = (id: string) => hospitals.find(h => h.id === id)?.name ?? id;

  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <button onClick={() => setShowAdd(true)} className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-xl text-sm transition-colors">
          <Plus size={15}/> Add User
        </button>
      </div>

      {msg && <div className="bg-green-50 text-green-700 px-4 py-3 rounded-xl text-sm border border-green-200">{msg}</div>}

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>{['Name','Email','Role','Hospital','Attributes','Status','Actions'].map(h=><th key={h} className="text-left px-5 py-3">{h}</th>)}</tr>
            </thead>
            <tbody>
              {users.map((u, i) => (
                <tr key={u.id} className={`border-t border-gray-50 ${i%2===1?'bg-gray-50/40':''}`}>
                  <td className="px-5 py-3 font-medium text-gray-800">{u.name}</td>
                  <td className="px-5 py-3 text-gray-500 font-mono text-xs">{u.email}</td>
                  <td className="px-5 py-3">{roleBadge(u.role)}</td>
                  <td className="px-5 py-3 text-xs text-gray-500">{hospName(u.hospitalId)}</td>
                  <td className="px-5 py-3 flex flex-wrap gap-1">{u.attributes.map(a=><Badge key={a} label={a} color="gray" size="xs"/>)}</td>
                  <td className="px-5 py-3"><Badge label={u.isRevoked ? 'Revoked' : 'Active'} color={u.isRevoked ? 'red' : 'green'} /></td>
                  <td className="px-5 py-3 space-x-3">
                    <button onClick={() => { setShowEdit(u); setEditAttrs(u.attributes.join(', ')); }} className="text-blue-600 hover:text-blue-800 text-xs font-medium"><Edit2 size={13} className="inline mr-1"/>Edit</button>
                    {!u.isRevoked && <button onClick={() => { setShowRevoke(u); setRevokeReason(''); }} className="text-red-500 hover:text-red-700 text-xs font-medium"><UserX size={13} className="inline mr-1"/>Revoke</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="Add User" size="md">
        <form onSubmit={handleAdd} className="space-y-3">
          {[['Name','name','text'],['Email','email','email'],['Password','password','text'],['Department','department','text']].map(([l,f,t]) => (
            <div key={f}>
              <label className="block text-xs font-medium text-gray-700 mb-1">{l}</label>
              <input type={t} required={f!=='department'} value={(addForm as any)[f]} onChange={e => setAddForm(x=>({...x,[f]:e.target.value}))} className="w-full px-3 py-2 border rounded-lg text-sm" />
            </div>
          ))}
          <div><label className="block text-xs font-medium text-gray-700 mb-1">Role</label>
            <select value={addForm.role} onChange={e=>setAddForm(x=>({...x,role:e.target.value}))} className="w-full px-3 py-2 border rounded-lg text-sm">
              <option value="doctor">Doctor</option><option value="nurse">Nurse</option><option value="admin">Admin</option>
            </select>
          </div>
          <div><label className="block text-xs font-medium text-gray-700 mb-1">Hospital</label>
            <select value={addForm.hospitalId} onChange={e=>setAddForm(x=>({...x,hospitalId:e.target.value}))} className="w-full px-3 py-2 border rounded-lg text-sm">
              {hospitals.map(h=><option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
          </div>
          <div><label className="block text-xs font-medium text-gray-700 mb-1">Attributes (comma separated)</label>
            <input value={addForm.attributes} onChange={e=>setAddForm(x=>({...x,attributes:e.target.value}))} placeholder="cardiology, senior" className="w-full px-3 py-2 border rounded-lg text-sm"/>
          </div>
          <div className="flex justify-end gap-2 pt-2"><button type="button" onClick={()=>setShowAdd(false)} className="px-4 py-2 border rounded-xl text-sm hover:bg-gray-50">Cancel</button><button type="submit" disabled={addSaving} className="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm flex gap-2 items-center">{addSaving && <InlineSpinner/>} Save</button></div>
        </form>
      </Modal>

      <Modal isOpen={!!showEdit} onClose={() => setShowEdit(null)} title={`Edit Attributes: ${showEdit?.name}`}>
        <form onSubmit={handleEdit} className="space-y-4">
          <div><label className="block text-sm font-medium mb-1">Attributes (comma separated)</label><input value={editAttrs} onChange={e=>setEditAttrs(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm"/></div>
          <div className="flex justify-end gap-2"><button type="button" onClick={()=>setShowEdit(null)} className="px-4 py-2 border rounded-xl text-sm">Cancel</button><button type="submit" disabled={editSaving} className="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm">Save</button></div>
        </form>
      </Modal>

      <Modal isOpen={!!showRevoke} onClose={() => setShowRevoke(null)} title="Revoke Access">
        <form onSubmit={handleRevoke} className="space-y-4">
          <p className="text-sm text-gray-600">This will immediately block <strong>{showRevoke?.name}</strong> from logging in.</p>
          <div><label className="block text-sm font-medium mb-1">Reason</label><textarea required rows={3} value={revokeReason} onChange={e=>setRevokeReason(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm resize-none"/></div>
          <div className="flex justify-end gap-2"><button type="button" onClick={()=>setShowRevoke(null)} className="px-4 py-2 border rounded-xl text-sm">Cancel</button><button type="submit" disabled={revokeSaving} className="px-4 py-2 bg-red-600 text-white rounded-xl text-sm flex gap-2 items-center">{revokeSaving && <InlineSpinner/>} Revoke Access</button></div>
        </form>
      </Modal>
    </div>
  );
}
