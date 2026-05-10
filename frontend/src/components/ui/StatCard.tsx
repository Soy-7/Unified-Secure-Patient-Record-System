import type { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: number | string;
  icon: LucideIcon;
  color: string;
  subtitle?: string;
}

export function StatCard({ title, value, icon: Icon, color, subtitle }: StatCardProps) {
  // Extract text color from bg color if possible, or just use a default
  const iconColor = color.replace('bg-', 'text-');

  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-subtle p-5 flex items-start justify-between card-hover">
      <div className="min-w-0">
        <p className="text-sm font-medium text-slate-500 mb-1">{title}</p>
        <div className="flex items-baseline gap-2">
          <h3 className="text-2xl font-bold text-slate-900 tracking-tight">{value}</h3>
          {subtitle && <span className="text-xs text-slate-400">{subtitle}</span>}
        </div>
      </div>
      <div className={`p-2.5 rounded-xl ${color.replace('600', '50').replace('500', '50')} ${iconColor} flex-shrink-0`}>
        <Icon size={20} strokeWidth={2.5} />
      </div>
    </div>
  );
}
