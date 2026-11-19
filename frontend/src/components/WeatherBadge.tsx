import React from 'react';
import { getWeatherBadge } from '../utils/formatters';

interface WeatherBadgeProps {
  condition: string;
  showFilter?: boolean;
}

export const WeatherBadge: React.FC<WeatherBadgeProps> = ({ condition, showFilter = true }) => {
  const badge = getWeatherBadge(condition);

  return (
    <div className="inline-flex items-center gap-1.5">
      <span
        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${badge.color}`}
      >
        <span>{badge.icon}</span>
        <span className="capitalize">{badge.label}</span>
      </span>
      {showFilter && (
        <span className="text-[10px] font-mono text-blue-700 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded font-medium">
          {badge.filter}
        </span>
      )}
    </div>
  );
};
