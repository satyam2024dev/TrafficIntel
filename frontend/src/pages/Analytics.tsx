import React, { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { BarChart3, Download, RefreshCw, ShieldCheck } from 'lucide-react';
import { api } from '../services/api';
import type { AnalyticsData, AnalyticsFilterInput, Camera } from '../types';

const colors = ['#00A8C6', '#10B981', '#F59E0B', '#6366F1', '#EC4899', '#64748B'];
const card = 'bg-white p-5 rounded-2xl border border-slate-200/90 shadow-sm';

export const Analytics: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [camera, setCamera] = useState('');
  const [bucket, setBucket] = useState<'hour' | 'day' | 'week'>('hour');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const filters = useMemo<AnalyticsFilterInput>(
    () => ({
      ...(start ? { start_at: `${start}T00:00:00Z` } : {}),
      ...(end ? { end_at: `${end}T23:59:59Z` } : {}),
      ...(camera ? { camera_id: camera } : {}),
      bucket,
    }),
    [start, end, camera, bucket]
  );

  useEffect(() => {
    api.getCameras().then(setCameras).catch(() => setCameras([]));
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    api
      .getAnalytics(filters)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((reason) => {
        if (active) setError(reason?.response?.data?.detail ?? 'Could not load persisted analytics.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [filters]);

  const exportLink = (type: Parameters<typeof api.getAnalyticsExportUrl>[0]) => api.getAnalyticsExportUrl(type, filters);

  const distribution = [
    { title: 'Vehicle confidence', rows: data?.vehicle_confidence_distribution ?? [] },
    { title: 'Plate detector confidence', rows: data?.plate_confidence_distribution ?? [] },
    { title: 'OCR confidence', rows: data?.ocr_confidence_distribution ?? [] },
  ];

  const metric = (title: string, value: number, detail: string) => (
    <div className={card} key={title}>
      <p className="text-xs uppercase tracking-wider font-mono text-slate-500 font-bold">{title}</p>
      <p className="mt-2 text-2xl font-extrabold font-mono tabular-nums text-slate-900">{value.toLocaleString()}</p>
      <p className="mt-1 text-[11px] text-[#64748B] font-medium">{detail}</p>
    </div>
  );

  const download = (type: Parameters<typeof api.getAnalyticsExportUrl>[0], label: string) => (
    <a
      key={type}
      href={exportLink(type)}
      className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 hover:text-[#00A8C6] hover:bg-slate-50 shadow-sm transition"
    >
      <Download size={13} className="text-[#00A8C6]" />
      {label}
    </a>
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-xl font-extrabold text-slate-900 flex items-center gap-2.5 tracking-tight">
            <BarChart3 className="text-[#00A8C6] w-6 h-6" />
            <span>Traffic & ANPR Analytics Intelligence</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Aggregates completed real-inference media jobs and persisted live-camera events. No demo records or accuracy estimates are included.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs uppercase font-mono text-emerald-800 font-bold shadow-sm">
          <ShieldCheck size={14} className="text-emerald-700" />
          {data?.mode ?? 'Persisted records only'}
        </span>
      </header>

      <section className={`${card} flex flex-wrap items-end gap-3`}>
        <label className="text-xs text-slate-600 font-semibold">
          From
          <input
            aria-label="Analytics start date"
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          />
        </label>
        <label className="text-xs text-slate-600 font-semibold">
          To
          <input
            aria-label="Analytics end date"
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          />
        </label>
        <label className="text-xs text-slate-600 font-semibold">
          Camera
          <select
            aria-label="Analytics camera"
            value={camera}
            onChange={(e) => setCamera(e.target.value)}
            className="mt-1.5 block min-w-40 rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          >
            <option value="">All cameras</option>
            {cameras.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} ({item.id})
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-600 font-semibold">
          Trend interval
          <select
            aria-label="Traffic trend interval"
            value={bucket}
            onChange={(e) => setBucket(e.target.value as typeof bucket)}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          >
            <option value="hour">Hourly</option>
            <option value="day">Daily</option>
            <option value="week">Weekly</option>
          </select>
        </label>
        <button
          onClick={() => {
            setStart('');
            setEnd('');
            setCamera('');
          }}
          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-[#00A8C6] shadow-sm transition"
        >
          <RefreshCw size={13} />
          Reset filters
        </button>
      </section>

      {error && <div role="alert" className="rounded-2xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800 shadow-sm font-medium">{error}</div>}
      {loading && <p className="text-xs text-slate-500 font-mono">Loading persisted analytics…</p>}

      {data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {metric('Vehicle detections', data.total_vehicle_detections, 'Persisted detection records')}
            {metric('Tracked identities', data.total_unique_tracked_vehicles, 'Local track IDs; never merged across cameras')}
            {metric('Plate detections', data.total_plates_detected, 'Real detector records')}
            {metric('Recognized registrations', data.recognized_registration_numbers, `${data.validated_registration_numbers.toLocaleString()} pass Indian format validation`)}
          </div>

          <div className="grid grid-cols-2 gap-4">
            {metric('Unrecognized plates', data.unrecognized_plates, 'Plate detections without normalized OCR text')}
            {metric('Unreadable plates', data.unreadable_plates, 'No raw or normalized OCR output saved')}
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <section className={`${card} min-h-80`}>
              <h2 className="font-bold text-base text-slate-900">Vehicle classification</h2>
              <p className="mb-4 text-xs text-slate-500">Counts use persisted real vehicle class labels.</p>
              {Object.values(data.vehicles_by_class).reduce((a, b) => a + b, 0) ? (
                <ResponsiveContainer width="100%" height={270}>
                  <BarChart data={Object.entries(data.vehicles_by_class).map(([name, count]) => ({ name: name.replace(/_/g, ' '), count }))}>
                    <CartesianGrid stroke="#E2E8F0" />
                    <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                    <YAxis allowDecimals={false} stroke="#64748b" fontSize={11} />
                    <Tooltip contentStyle={{ background: '#FFFFFF', borderColor: '#CBD5E1', color: '#0F172A', borderRadius: '12px' }} />
                    <Bar dataKey="count" fill="#00A8C6" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-20 text-center text-sm text-slate-500">No real vehicle detections in this filter.</p>
              )}
            </section>

            <section className={`${card} min-h-80`}>
              <h2 className="font-bold text-base text-slate-900">Traffic and ANPR trend</h2>
              <p className="mb-4 text-xs text-slate-500">Detections and recognized OCR candidates by selected interval.</p>
              {data.time_series.length ? (
                <ResponsiveContainer width="100%" height={270}>
                  <LineChart data={data.time_series}>
                    <CartesianGrid stroke="#E2E8F0" />
                    <XAxis dataKey="period" stroke="#64748b" tick={{ fontSize: 10 }} />
                    <YAxis allowDecimals={false} stroke="#64748b" fontSize={11} />
                    <Tooltip contentStyle={{ background: '#FFFFFF', borderColor: '#CBD5E1', color: '#0F172A', borderRadius: '12px' }} />
                    <Legend wrapperStyle={{ paddingTop: '8px' }} />
                    <Line dataKey="vehicles" name="Vehicle detections" stroke="#00A8C6" strokeWidth={2.5} dot={false} />
                    <Line dataKey="plates" name="Plate detections" stroke="#F59E0B" strokeWidth={2} dot={false} />
                    <Line dataKey="recognized_plates" name="Recognized OCR" stroke="#10B981" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-20 text-center text-sm text-slate-500">No time-series records in this filter.</p>
              )}
            </section>
          </div>

          <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {distribution.map(({ title, rows }) => {
              const total = rows.reduce((sum, row) => sum + row.count, 0);
              return (
                <div className={card} key={title}>
                  <h3 className="mb-3 text-sm font-semibold text-slate-900">{title}</h3>
                  {rows.map((row, index) => (
                    <div key={row.range} className="mb-2.5">
                      <div className="flex justify-between text-xs text-slate-600">
                        <span>{row.range}</span>
                        <span className="font-mono tabular-nums text-slate-800">{row.count}</span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-[#F1F5F9]">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${Math.min(100, total ? (row.count / total) * 100 : 0)}%`,
                            backgroundColor: colors[index % colors.length],
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              );
            })}
          </section>

          <section className={`${card} overflow-x-auto`}>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold text-slate-900">Camera statistics</h2>
                <p className="text-xs text-slate-500">Vehicle detections grouped by source camera.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {download('daily_traffic', 'Daily traffic CSV')}
                {download('vehicle_classification', 'Classes CSV')}
                {download('camera_detections', 'Cameras CSV')}
                {download('anpr', 'ANPR CSV')}
                {download('ocr_confidence', 'OCR confidence CSV')}
                {download('alert_history', 'Alert history CSV')}
              </div>
            </div>
            <table className="w-full min-w-[500px] text-left text-xs">
              <thead className="text-slate-600 bg-[#F8FAFC] border-b border-[#E2E8F0]">
                <tr>
                  <th className="p-2.5 font-semibold font-mono uppercase text-[10px]">Camera</th>
                  <th className="p-2.5 font-semibold font-mono uppercase text-[10px]">Vehicle detections</th>
                  <th className="p-2.5 font-semibold font-mono uppercase text-[10px]">Configured FPS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {data.camera_statistics.map((row) => (
                  <tr key={row.camera_id} className="hover:bg-slate-50 transition">
                    <td className="p-2.5 text-slate-900 font-medium">
                      {row.camera_name} <span className="text-slate-500 font-mono">({row.camera_id})</span>
                    </td>
                    <td className="p-2.5 text-blue-600 font-mono tabular-nums font-bold">{row.vehicle_detections}</td>
                    <td className="p-2.5 text-slate-500 font-mono tabular-nums">{row.configured_fps ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!data.camera_statistics.length && (
              <p className="py-6 text-center text-sm text-slate-500">No camera-linked detections in this filter.</p>
            )}
          </section>

          <p className="text-[11px] text-slate-500 font-mono">
            Mean OCR confidence: {data.mean_ocr_confidence == null ? 'unavailable' : `${(data.mean_ocr_confidence * 100).toFixed(1)}%`}. Confidence is not measured accuracy. {data.time_basis} {data.track_identity_scope}
          </p>
        </>
      )}
    </div>
  );
};
