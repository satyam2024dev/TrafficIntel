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
  glowColor?: 'blue' | 'emerald' | 'amber' | 'rose' | 'indigo';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  badge,
  badgeColor = 'text-blue-400 bg-blue-950/50 border-blue-800/40',
  trend,
  glowColor = 'blue',
}) => {
  const accentClasses: Record<string, string> = {
    blue: 'hover:border-blue-500/50 border-t-2 border-t-blue-600',
    emerald: 'hover:border-emerald-500/50 border-t-2 border-t-emerald-600',
    amber: 'hover:border-amber-500/50 border-t-2 border-t-amber-600',
    rose: 'hover:border-rose-500/50 border-t-2 border-t-rose-600',
    indigo: 'hover:border-indigo-500/50 border-t-2 border-t-indigo-600',
  };

  const iconColorClasses: Record<string, string> = {
    blue: 'text-blue-400',
    emerald: 'text-emerald-400',
    amber: 'text-amber-400',
    rose: 'text-rose-400',
    indigo: 'text-indigo-400',
  };

  const currentAccent = accentClasses[glowColor] || accentClasses.blue;
  const currentIconColor = iconColorClasses[glowColor] || iconColorClasses.blue;

  return (
    <div
      className={`glass-panel p-5 rounded-xl border border-[#222634] transition-all duration-200 shadow-sm ${currentAccent}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </span>
        <div className={`p-2.5 rounded-lg bg-[#171A24] border border-[#2B3040] shadow-sm ${currentIconColor}`}>
          {icon}
        </div>
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-2xl font-bold font-mono tabular-nums tracking-tight text-white">
          {value}
        </span>
        {badge && (
          <span className={`text-[11px] font-mono tabular-nums px-2 py-0.5 rounded border ${badgeColor}`}>
            {badge}
          </span>
        )}
      </div>

      {(subtitle || trend) && (
        <div className="mt-2.5 flex items-center justify-between text-xs text-slate-400">
          {subtitle && <span>{subtitle}</span>}
          {trend && (
            <span
              className={`font-medium tabular-nums ${
                trend.direction === 'up'
                  ? 'text-emerald-400'
                  : trend.direction === 'down'
                  ? 'text-rose-400'
                  : 'text-slate-400'
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
