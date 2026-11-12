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
  glowColor?: 'cyan' | 'emerald' | 'amber' | 'rose' | 'indigo';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  badge,
  badgeColor = 'text-cyan-400 bg-cyan-950/60 border-cyan-800/40',
  trend,
  glowColor = 'cyan',
}) => {
  const glowClasses = {
    cyan: 'hover:border-cyan-500/50 hover:shadow-cyan-500/10',
    emerald: 'hover:border-emerald-500/50 hover:shadow-emerald-500/10',
    amber: 'hover:border-amber-500/50 hover:shadow-amber-500/10',
    rose: 'hover:border-rose-500/50 hover:shadow-rose-500/10',
    indigo: 'hover:border-indigo-500/50 hover:shadow-indigo-500/10',
  };

  return (
    <div
      className={`glass-panel p-5 rounded-xl border border-slate-800 transition-all duration-300 hover:shadow-xl ${glowClasses[glowColor]}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </span>
        <div className="p-2.5 rounded-lg bg-slate-800/80 text-cyan-400 border border-slate-700/60 shadow-inner">
          {icon}
        </div>
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-2xl font-bold font-mono tracking-tight text-white">
          {value}
        </span>
        {badge && (
          <span className={`text-[11px] font-mono px-2 py-0.5 rounded border ${badgeColor}`}>
            {badge}
          </span>
        )}
      </div>

      {(subtitle || trend) && (
        <div className="mt-2.5 flex items-center justify-between text-xs text-slate-400">
          {subtitle && <span>{subtitle}</span>}
          {trend && (
            <span
              className={`font-medium ${
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
