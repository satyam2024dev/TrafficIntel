import React, { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { BarChart3, Download, RefreshCw, ShieldCheck } from 'lucide-react';
import { api } from '../services/api';
import type { AnalyticsData, AnalyticsFilterInput, Camera } from '../types';

const colors = ['#22d3ee', '#34d399', '#fbbf24', '#a78bfa', '#fb7185', '#94a3b8'];
const card = 'glass-panel p-4 rounded-xl border border-slate-800';

export const Analytics: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [camera, setCamera] = useState('');
  const [bucket, setBucket] = useState<'hour' | 'day' | 'week'>('hour');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const filters = useMemo<AnalyticsFilterInput>(() => ({
    ...(start ? { start_at: `${start}T00:00:00Z` } : {}),
    ...(end ? { end_at: `${end}T23:59:59Z` } : {}),
    ...(camera ? { camera_id: camera } : {}), bucket,
  }), [start, end, camera, bucket]);

  useEffect(() => { api.getCameras().then(setCameras).catch(() => setCameras([])); }, []);
  useEffect(() => {
    let active = true;
    setLoading(true); setError('');
    api.getAnalytics(filters).then((result) => { if (active) setData(result); })
      .catch((reason) => { if (active) setError(reason?.response?.data?.detail ?? 'Could not load persisted analytics.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [filters]);

  const exportLink = (type: Parameters<typeof api.getAnalyticsExportUrl>[0]) => api.getAnalyticsExportUrl(type, filters);
  const distribution = [
    { title: 'Vehicle confidence', rows: data?.vehicle_confidence_distribution ?? [] },
    { title: 'Plate detector confidence', rows: data?.plate_confidence_distribution ?? [] },
    { title: 'OCR confidence', rows: data?.ocr_confidence_distribution ?? [] },
  ];
  const metric = (title: string, value: number, detail: string) => <div className={card} key={title}><p className="text-xs uppercase tracking-wide text-slate-400">{title}</p><p className="mt-2 text-2xl font-bold font-mono text-white">{value.toLocaleString()}</p><p className="mt-1 text-[11px] text-slate-500">{detail}</p></div>;
  const download = (type: Parameters<typeof api.getAnalyticsExportUrl>[0], label: string) => <a key={type} href={exportLink(type)} className="inline-flex items-center gap-1 rounded border border-slate-700 px-2.5 py-1.5 text-xs text-cyan-300 hover:bg-slate-800"><Download size={13} />{label}</a>;

  return <div className="space-y-5">
    <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div><h1 className="text-xl font-bold text-white flex items-center gap-2"><BarChart3 className="text-cyan-400" />Traffic analytics</h1><p className="text-xs text-slate-400 mt-1">Aggregates completed real-inference media jobs and persisted live-camera events. No demo records or accuracy estimates are included.</p></div>
      <span className="inline-flex items-center gap-1 rounded border border-emerald-800 bg-emerald-950/40 px-2 py-1 text-[11px] uppercase text-emerald-300"><ShieldCheck size={13} />{data?.mode ?? 'Persisted records only'}</span>
    </header>
    <section className={`${card} flex flex-wrap items-end gap-3`}>
      <label className="text-xs text-slate-400">From<input aria-label="Analytics start date" type="date" value={start} onChange={(e) => setStart(e.target.value)} className="mt-1 block rounded border border-slate-700 bg-slate-950 p-2 text-white" /></label>
      <label className="text-xs text-slate-400">To<input aria-label="Analytics end date" type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="mt-1 block rounded border border-slate-700 bg-slate-950 p-2 text-white" /></label>
      <label className="text-xs text-slate-400">Camera<select aria-label="Analytics camera" value={camera} onChange={(e) => setCamera(e.target.value)} className="mt-1 block min-w-40 rounded border border-slate-700 bg-slate-950 p-2 text-white"><option value="">All cameras</option>{cameras.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.id})</option>)}</select></label>
      <label className="text-xs text-slate-400">Trend interval<select aria-label="Traffic trend interval" value={bucket} onChange={(e) => setBucket(e.target.value as typeof bucket)} className="mt-1 block rounded border border-slate-700 bg-slate-950 p-2 text-white"><option value="hour">Hourly</option><option value="day">Daily</option><option value="week">Weekly</option></select></label>
      <button onClick={() => { setStart(''); setEnd(''); setCamera(''); }} className="inline-flex items-center gap-1 rounded border border-slate-700 px-3 py-2 text-xs text-slate-300"><RefreshCw size={13} />Reset filters</button>
    </section>
    {error && <div role="alert" className="rounded border border-rose-800 bg-rose-950/40 p-3 text-sm text-rose-200">{error}</div>}
    {loading && <p className="text-xs text-slate-400">Loading persisted analytics…</p>}
    {data && <>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {metric('Vehicle detections', data.total_vehicle_detections, 'Persisted detection records')}
        {metric('Tracked identities', data.total_unique_tracked_vehicles, 'Local track IDs; never merged across cameras')}
        {metric('Plate detections', data.total_plates_detected, 'Real detector records')}
        {metric('Recognized registrations', data.recognized_registration_numbers, `${data.validated_registration_numbers.toLocaleString()} pass Indian format validation`)}
      </div>
      <div className="grid grid-cols-2 gap-3">
        {metric('Unrecognized plates', data.unrecognized_plates, 'Plate detections without normalized OCR text')}
        {metric('Unreadable plates', data.unreadable_plates, 'No raw or normalized OCR output saved')}
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <section className={`${card} min-h-80`}><h2 className="font-semibold text-white">Vehicle classification</h2><p className="mb-4 text-xs text-slate-500">Counts use persisted real vehicle class labels.</p>{Object.values(data.vehicles_by_class).reduce((a, b) => a + b, 0) ? <ResponsiveContainer width="100%" height={270}><BarChart data={Object.entries(data.vehicles_by_class).map(([name, count]) => ({ name: name.replace(/_/g, ' '), count }))}><CartesianGrid stroke="#1e293b" /><XAxis dataKey="name" stroke="#94a3b8" /><YAxis allowDecimals={false} stroke="#94a3b8" /><Tooltip /><Bar dataKey="count" fill="#22d3ee" /></BarChart></ResponsiveContainer> : <p className="py-20 text-center text-sm text-slate-500">No real vehicle detections in this filter.</p>}</section>
        <section className={`${card} min-h-80`}><h2 className="font-semibold text-white">Traffic and ANPR trend</h2><p className="mb-4 text-xs text-slate-500">Detections and recognized OCR candidates by selected interval.</p>{data.time_series.length ? <ResponsiveContainer width="100%" height={270}><LineChart data={data.time_series}><CartesianGrid stroke="#1e293b" /><XAxis dataKey="period" stroke="#94a3b8" tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} stroke="#94a3b8" /><Tooltip /><Legend /><Line dataKey="vehicles" name="Vehicle detections" stroke="#22d3ee" /><Line dataKey="plates" name="Plate detections" stroke="#fbbf24" /><Line dataKey="recognized_plates" name="Recognized OCR" stroke="#34d399" /></LineChart></ResponsiveContainer> : <p className="py-20 text-center text-sm text-slate-500">No time-series records in this filter.</p>}</section>
      </div>
      <section className="grid grid-cols-1 md:grid-cols-3 gap-3">{distribution.map(({ title, rows }) => { const total = rows.reduce((sum, row) => sum + row.count, 0); return <div className={card} key={title}><h3 className="mb-3 text-sm font-semibold text-white">{title}</h3>{rows.map((row, index) => <div key={row.range} className="mb-2"><div className="flex justify-between text-xs text-slate-400"><span>{row.range}</span><span>{row.count}</span></div><div className="mt-1 h-1.5 rounded bg-slate-800"><div className="h-full rounded" style={{ width: `${Math.min(100, total ? row.count / total * 100 : 0)}%`, backgroundColor: colors[index] }} /></div></div>)}</div>; })}</section>
      <section className={`${card} overflow-x-auto`}><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-semibold text-white">Camera statistics</h2><p className="text-xs text-slate-500">Vehicle detections grouped by source camera.</p></div><div className="flex flex-wrap gap-2">{download('daily_traffic', 'Daily traffic CSV')}{download('vehicle_classification', 'Classes CSV')}{download('camera_detections', 'Cameras CSV')}{download('anpr', 'ANPR CSV')}{download('ocr_confidence', 'OCR confidence CSV')}{download('alert_history', 'Alert history CSV')}</div></div><table className="w-full min-w-[500px] text-left text-xs"><thead className="text-slate-500"><tr><th className="p-2">Camera</th><th className="p-2">Vehicle detections</th><th className="p-2">Configured FPS</th></tr></thead><tbody>{data.camera_statistics.map((row) => <tr key={row.camera_id} className="border-t border-slate-800"><td className="p-2 text-white">{row.camera_name} ({row.camera_id})</td><td className="p-2 text-cyan-300">{row.vehicle_detections}</td><td className="p-2 text-slate-400">{row.configured_fps ?? '—'}</td></tr>)}</tbody></table>{!data.camera_statistics.length && <p className="py-5 text-center text-sm text-slate-500">No camera-linked detections in this filter.</p>}</section>
      <p className="text-[11px] text-slate-500">Mean OCR confidence: {data.mean_ocr_confidence == null ? 'unavailable' : `${(data.mean_ocr_confidence * 100).toFixed(1)}%`}. Confidence is not measured accuracy. {data.time_basis} {data.track_identity_scope}</p>
    </>}
  </div>;
};
