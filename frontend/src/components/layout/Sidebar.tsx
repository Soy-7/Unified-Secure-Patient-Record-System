import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  Shield, LayoutDashboard, Users, FileText,
  ArrowLeftRight, Lock, UserCog, Settings, LogOut,
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { roleBadge } from '../ui/Badge';
import client from '../../api/client';
import type { UserRole } from '../../types';

interface NavItem {
  to: string;
  label: string;
  Icon: React.ElementType;
  roles: UserRole[];
}

const NAV: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', Icon: LayoutDashboard, roles: ['admin', 'doctor', 'nurse', 'patient'] },
  { to: '/timeline', label: 'My Timeline', Icon: FileText, roles: ['patient'] },
  { to: '/patients', label: 'Patients', Icon: Users, roles: ['admin', 'doctor', 'nurse'] },
  { to: '/records', label: 'Records', Icon: FileText, roles: ['admin', 'doctor', 'nurse'] },
  { to: '/exchange', label: 'Exchange', Icon: ArrowLeftRight, roles: ['admin', 'doctor'] },
  { to: '/encryption', label: 'Encryption Lab', Icon: Lock, roles: ['admin', 'doctor'] },
  { to: '/audit', label: 'Audit Trail', Icon: Shield, roles: ['admin'] },
  { to: '/users', label: 'User Management', Icon: UserCog, roles: ['admin'] },
  { to: '/settings', label: 'Settings', Icon: Settings, roles: ['admin', 'doctor', 'nurse', 'patient'] },
];

export function Sidebar() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try { await client.post('/auth/logout'); } catch { /* ignore */ }
    logout();
    navigate('/login');
  };

  const visible = NAV.filter(n => user && n.roles.includes(user.role));
  const initials = (user?.name ?? 'U').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();

  return (
    <aside className="fixed inset-y-0 left-0 w-64 flex flex-col z-30 select-none bg-brand-900 border-r border-brand-800">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-8">
        <div className="p-2.5 bg-primary-600 rounded-xl shadow-lg shadow-primary-600/20">
          <Shield size={20} className="text-white" />
        </div>
        <div className="leading-tight">
          <p className="text-white font-bold text-lg tracking-tight"></p>
          <p className="text-brand-400 text-[10px] uppercase tracking-widest font-semibold">CareNexus</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-4 py-2 space-y-1.5 overflow-y-auto">
        {visible.map(({ to, label, Icon }) => (
          <NavLink key={to} to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all group ${isActive
                ? 'bg-primary-600 text-white shadow-md shadow-primary-900/20'
                : 'text-brand-400 hover:text-white hover:bg-brand-800'
              }`
            }
          >
            <Icon size={18} className="transition-transform group-hover:scale-110" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User + Logout */}
      <div className="p-4 bg-brand-950/50 border-t border-brand-800 space-y-4">
        <div className="flex items-center gap-3 px-2 py-1">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-white text-xs font-bold flex-shrink-0 shadow-inner">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-white text-sm font-semibold truncate leading-none">{user?.name}</p>
            <div className="mt-1.5 transform scale-90 origin-left opacity-90">
              {user && roleBadge(user.role)}
            </div>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-xl text-brand-400 hover:bg-red-500/10 hover:text-red-400 transition-all text-sm font-medium border border-transparent hover:border-red-500/20"
        >
          <LogOut size={16} /> Sign Out
        </button>
      </div>
    </aside>
  );
}
