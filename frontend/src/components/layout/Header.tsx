import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { roleBadge } from '../ui/Badge';
import client from '../../api/client';
import type { ExchangeRequest } from '../../types';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard':  'Dashboard',
  '/patients':   'Patient Registry',
  '/records':    'EHR Records',
  '/exchange':   'Inter-Hospital Exchange',
  '/encryption': 'Encryption Laboratory',
  '/audit':      'Audit Trail',
  '/users':      'User Management',
  '/settings':   'Settings',
  '/timeline':   'My Health Timeline',
};

export function Header() {
  const { pathname } = useLocation();
  const { user } = useAuthStore();
  const [pending, setPending] = useState(0);

  useEffect(() => {
    client.get<ExchangeRequest[]>('/exchange')
      .then(r => setPending((r.data ?? []).filter(x => x.status === 'pending').length))
      .catch(() => {});
  }, [pathname]);

  const base = '/' + pathname.split('/')[1];
  const title = PAGE_TITLES[base] ?? 'Platform';

  return (
    <header className="fixed top-0 left-64 right-0 z-20 bg-white/80 backdrop-blur-md border-b border-slate-100">
      <div className="flex items-center justify-between px-8 h-20">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">{title}</h1>
          <div className="h-4 w-[1px] bg-slate-200 hidden md:block" />
          <p className="text-xs font-medium text-slate-400 hidden md:block uppercase tracking-wider">Health Information System</p>
        </div>
        <div className="flex items-center gap-6">
          <div className="relative group cursor-pointer">
            <div className="p-2 rounded-xl bg-slate-50 group-hover:bg-slate-100 transition-colors">
              <Bell size={20} className="text-slate-500 group-hover:text-primary-600 transition-colors" />
            </div>
            {pending > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-primary-600 text-white text-[10px] font-bold rounded-lg flex items-center justify-center border-2 border-white shadow-sm">
                {pending}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 pl-6 border-l border-slate-100">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-bold text-slate-900 leading-none">{user?.name}</p>
              <p className="text-[10px] font-bold text-primary-600 uppercase mt-1 tracking-tighter opacity-80">{user?.role}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center border border-slate-200 shadow-sm overflow-hidden">
               <span className="text-xs font-bold text-slate-500">{(user?.name ?? 'U')[0]}</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
