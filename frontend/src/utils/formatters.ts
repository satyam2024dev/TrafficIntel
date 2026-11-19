export function formatDate(isoStr?: string): string {
  if (!isoStr) return '--';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + 
           ' (' + d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ')';
  } catch {
    return isoStr;
  }
}

export function formatDuration(minutes: number): string {
  if (minutes < 1) return '< 1 min';
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hrs = Math.floor(minutes / 60);
  const remainingMins = Math.round(minutes % 60);
  return `${hrs}h ${remainingMins}m`;
}

export function getWeatherBadge(condition: string) {
  switch (condition.toLowerCase()) {
    case 'rain':
      return { label: 'Rain', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', icon: '🌧️', filter: 'CLAHE' };
    case 'fog':
      return { label: 'Fog', color: 'bg-slate-500/20 text-slate-300 border-slate-500/30', icon: '🌫️', filter: 'Dehaze' };
    case 'night':
      return { label: 'Night', color: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30', icon: '🌙', filter: 'Gamma 0.55' };
    case 'low_light':
      return { label: 'Low Light', color: 'bg-purple-500/20 text-purple-300 border-purple-500/30', icon: '🌆', filter: 'Gamma+CLAHE' };
    case 'glare':
      return { label: 'Glare', color: 'bg-amber-500/20 text-amber-300 border-amber-500/30', icon: '☀️', filter: 'Anti-Glare' };
    case 'clear':
    default:
      return { label: 'Clear', color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30', icon: '☀️', filter: 'RGB Pass' };
  }
}

export function getSeverityBadge(severity: string) {
  switch (severity.toLowerCase()) {
    case 'critical':
      return { label: 'CRITICAL', color: 'bg-rose-500/20 text-rose-400 border-rose-500/40 animate-pulse' };
    case 'high':
      return { label: 'HIGH', color: 'bg-orange-500/20 text-orange-400 border-orange-500/40' };
    case 'warning':
      return { label: 'WARNING', color: 'bg-amber-500/20 text-amber-400 border-amber-500/40' };
    case 'info':
    default:
      return { label: 'INFO', color: 'bg-blue-500/15 text-blue-400 border-blue-500/30' };
  }
}
