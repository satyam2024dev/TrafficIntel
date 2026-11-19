import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  badge?: string;
  badgeColor?: string;
  trend?: {
    direction: 'up' | 'down' | 'neutral';
    text: string;
  };
  glowColor?: 'blue' | 'emerald' | 'amber' | 'rose' | 'indigo' | 'coral' | 'teal' | 'slate';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  badge,
  badgeColor = 'text-teal-700 bg-teal-50 border-teal-200',
  trend,
  glowColor = 'teal',
}) => {
  const accentClasses: Record<string, string> = {
    coral: 'border-t-[3px] border-t-[#EF4444]',
    rose: 'border-t-[3px] border-t-[#EF4444]',
    amber: 'border-t-[3px] border-t-[#F59E0B]',
    teal: 'border-t-[3px] border-t-[#00A8C6]',
    blue: 'border-t-[3px] border-t-[#00A8C6]',
    emerald: 'border-t-[3px] border-t-[#059669]',
    indigo: 'border-t-[3px] border-t-[#0891B2]',
    slate: 'border-t-[3px] border-t-[#0F172A]',
  };

  const textClasses: Record<string, string> = {
    coral: 'text-[#EF4444]',
    rose: 'text-[#EF4444]',
    amber: 'text-[#F59E0B]',
    teal: 'text-[#00A8C6]',
    blue: 'text-[#00A8C6]',
    emerald: 'text-[#059669]',
    indigo: 'text-[#0891B2]',
    slate: 'text-[#0F172A]',
  };

  const iconClasses: Record<string, string> = {
    coral: 'bg-rose-50 border-rose-100 text-[#EF4444]',
    rose: 'bg-rose-50 border-rose-100 text-[#EF4444]',
    amber: 'bg-amber-50 border-amber-100 text-[#F59E0B]',
    teal: 'bg-teal-50 border-teal-100 text-[#00A8C6]',
    blue: 'bg-teal-50 border-teal-100 text-[#00A8C6]',
    emerald: 'bg-emerald-50 border-emerald-100 text-[#059669]',
    indigo: 'bg-cyan-50 border-cyan-100 text-[#0891B2]',
    slate: 'bg-slate-100 border-slate-200 text-[#0F172A]',
  };

  const currentAccent = accentClasses[glowColor] || accentClasses.teal;
  const currentTextColor = textClasses[glowColor] || textClasses.slate;
  const currentIconClass = iconClasses[glowColor] || iconClasses.teal;

  return (
    <div
      className={`bg-white p-5 rounded-2xl border border-slate-200/90 shadow-sm transition-all duration-200 hover:shadow-md ${currentAccent}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
          {title}
        </span>
        <div className={`p-2.5 rounded-xl border shadow-sm ${currentIconClass}`}>
          {icon}
        </div>
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className={`text-2xl font-extrabold font-mono tabular-nums tracking-tight ${currentTextColor}`}>
          {value}
        </span>
        {badge && (
          <span className={`text-[11px] font-mono tabular-nums px-2 py-0.5 rounded border font-semibold ${badgeColor}`}>
            {badge}
          </span>
        )}
      </div>

      {(subtitle || trend) && (
        <div className="mt-2.5 flex items-center justify-between text-xs text-[#64748B]">
          {subtitle && <span>{subtitle}</span>}
          {trend && (
            <span
              className={`font-semibold tabular-nums ${
                trend.direction === 'up'
                  ? 'text-emerald-700'
                  : trend.direction === 'down'
                  ? 'text-rose-700'
                  : 'text-slate-500'
              }`}
            >
              {trend.direction === 'up' ? '↑' : trend.direction === 'down' ? '↓' : '•'} {trend.text}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
