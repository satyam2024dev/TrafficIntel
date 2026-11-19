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
      return { label: 'Rain', color: 'bg-blue-50 text-blue-700 border-blue-200', icon: '🌧️', filter: 'CLAHE' };
    case 'fog':
      return { label: 'Fog', color: 'bg-slate-100 text-slate-700 border-slate-300', icon: '🌫️', filter: 'Dehaze' };
    case 'night':
      return { label: 'Night', color: 'bg-indigo-50 text-indigo-700 border-indigo-200', icon: '🌙', filter: 'Gamma 0.55' };
    case 'low_light':
      return { label: 'Low Light', color: 'bg-purple-50 text-purple-700 border-purple-200', icon: '🌆', filter: 'Gamma+CLAHE' };
    case 'glare':
      return { label: 'Glare', color: 'bg-amber-50 text-amber-700 border-amber-200', icon: '☀️', filter: 'Anti-Glare' };
    case 'clear':
    default:
      return { label: 'Clear', color: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: '☀️', filter: 'RGB Pass' };
  }
}

export function getSeverityBadge(severity: string) {
  switch (severity.toLowerCase()) {
    case 'critical':
      return { label: 'CRITICAL', color: 'bg-rose-50 text-rose-700 border-rose-300 font-bold animate-pulse' };
    case 'high':
      return { label: 'HIGH', color: 'bg-orange-50 text-orange-700 border-orange-300 font-semibold' };
    case 'warning':
      return { label: 'WARNING', color: 'bg-amber-50 text-amber-800 border-amber-300 font-semibold' };
    case 'info':
    default:
      return { label: 'INFO', color: 'bg-blue-50 text-blue-700 border-blue-200 font-medium' };
  }
}
