import React from 'react';

type Color = 'blue' | 'green' | 'red' | 'amber' | 'purple' | 'teal' | 'gray';

const styles: Record<Color, string> = {
  blue:   'bg-blue-50 text-blue-700 border-blue-100',
  green:  'bg-emerald-50 text-emerald-700 border-emerald-100',
  red:    'bg-rose-50 text-rose-700 border-rose-100',
  amber:  'bg-amber-50 text-amber-700 border-amber-100',
  purple: 'bg-violet-50 text-violet-700 border-violet-100',
  teal:   'bg-teal-50 text-teal-700 border-teal-100',
  gray:   'bg-slate-100 text-slate-600 border-slate-200',
};

interface BadgeProps {
  label: string;
  color?: Color;
  size?: 'xs' | 'sm';
}

export function Badge({ label, color = 'gray', size = 'sm' }: BadgeProps) {
  const sz = size === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider';
  return (
    <span className={`inline-flex items-center rounded-full border shadow-sm ${sz} ${styles[color]}`}>
      {label}
    </span>
  );
}

// ── Semantic badge helpers ───────────────────────────────────────────────────

export function roleBadge(role: string): React.ReactElement {
  const map: Record<string, Color> = { admin: 'red', doctor: 'blue', nurse: 'green', patient: 'gray' };
  return <Badge label={role} color={map[role] ?? 'gray'} />;
}

export function recordTypeBadge(type: string): React.ReactElement {
  const map: Record<string, Color> = {
    diagnosis: 'blue', prescription: 'green', lab_result: 'amber',
    imaging: 'purple', discharge_summary: 'red', consultation: 'teal',
  };
  return <Badge label={type.replace(/_/g, ' ')} color={map[type] ?? 'gray'} />;
}

export function statusBadge(status: string): React.ReactElement {
  const map: Record<string, Color> = {
    pending: 'amber', approved: 'green', completed: 'green',
    rejected: 'red',  active: 'green',   revoked: 'red',
  };
  return <Badge label={status} color={map[status] ?? 'gray'} />;
}

export function actionBadge(action: string): React.ReactElement {
  const green = new Set(['VIEW', 'LOGIN', 'LOGOUT']);
  const amber = new Set(['CREATE', 'UPDATE', 'SHARE', 'EXPORT']);
  const red   = new Set(['DELETE', 'ACCESS_DENIED']);
  const color: Color = green.has(action) ? 'green' : amber.has(action) ? 'amber' : red.has(action) ? 'red' : 'blue';
  return <Badge label={action.replace(/_/g, ' ')} color={color} />;
}
