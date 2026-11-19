import React, { useEffect, useState } from 'react';
import { AlertTriangle, ArrowRight, Car, ScanLine, Video } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import type { AlertItem, AnalyticsData, ANPRSearchPage, Camera } from '../types';
import { MediaProcessingWorkspace } from '../components/MediaProcessingWorkspace';
import { LeafletRouteMap } from '../components/LeafletRouteMap';

export const Dashboard: React.FC = () => {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [detections, setDetections] = useState<ANPRSearchPage | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all([
      api.getAnalytics({ bucket: 'hour' }),
      api.getAlerts(false),
      api.getANPRDetections({ limit: 6, offset: 0 }),
      api.getCameras(),
    ])
      .then(([a, al, d, c]) => {
        if (active) {
          setAnalytics(a);
          setAlerts(al);
          setDetections(d);
          setCameras(c);
        }
      })
      .catch((e) => {
        if (active) setError(e?.response?.data?.detail ?? 'Persisted traffic data could not be loaded.');
      });
    return () => {
      active = false;
    };
  }, []);

  const metric = (
    label: string,
    value: string | number,
    caption: string,
    icon: React.ReactNode,
    valueColor: string = 'text-[#0F172A]',
    accentTop: string = 'border-t-slate-400',
    iconBg: string = 'bg-slate-50 text-slate-700'
  ) => (
    <div className={`bg-white rounded-2xl border border-slate-200/90 p-5 shadow-sm border-t-[3px] ${accentTop} hover:shadow-md transition-all`}>
      <div className="flex items-center justify-between text-xs text-slate-500 font-bold uppercase tracking-wider">
        <span>{label}</span>
        <div className={`p-2.5 rounded-xl ${iconBg} border border-slate-200/60 shadow-sm`}>
          {icon}
        </div>
      </div>
      <p className={`mt-3 text-2xl font-extrabold font-mono tabular-nums ${valueColor}`}>{value}</p>
      <p className="mt-1 text-xs text-[#64748B] font-medium leading-relaxed">{caption}</p>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Hero Spotlight / Quick-Action Banner Card */}
      <section className="rounded-2xl bg-[#111C2D] border border-[#26354D] p-6 text-white shadow-md flex flex-col md:flex-row md:items-center md:justify-between gap-5">
        <div className="space-y-1.5 max-w-2xl">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#00A8C6] animate-ping" />
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest px-2.5 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-700/50">
              TACTICAL OPERATIONS · 5 NODES ACTIVE
            </span>
          </div>
          <h1 className="text-xl lg:text-2xl font-extrabold text-white tracking-tight">
            Traffic Intelligence & ANPR Operations
          </h1>
          <p className="text-xs text-[#CBD5E1] leading-relaxed">
            Multi-camera vehicle tracking, adverse-weather license plate recognition, and corridor route intelligence across Bangalore Outer Ring Road. Counts aggregate completed real-inference jobs and persisted live-camera events.
          </p>
        </div>
        <div className="flex items-center gap-2.5 shrink-0 flex-wrap">
          <Link
            to="/live"
            className="inline-flex items-center gap-2 rounded-xl bg-[#00A8C6] hover:bg-[#0090AA] px-4 py-2.5 text-xs font-semibold text-white shadow-sm transition"
          >
            <Video size={14} />
            <span>Live Monitoring</span>
          </Link>
          <Link
            to="/detections"
            className="inline-flex items-center gap-2 rounded-xl bg-[#09111E] hover:bg-[#1a283e] border border-[#26354D] px-4 py-2.5 text-xs font-semibold text-[#CBD5E1] transition"
          >
            <ScanLine size={14} />
            <span>ANPR History</span>
          </Link>
        </div>
      </section>

      <MediaProcessingWorkspace />

      {error && <p role="alert" className="rounded-xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800 shadow-sm">{error}</p>}

      {/* Multi-Color High-Contrast Metric Cards Grid */}
      <section className="grid grid-cols-2 gap-3.5 xl:grid-cols-5">
        {metric('Vehicle detections', analytics?.total_vehicle_detections ?? '—', 'Persisted detection observations', <Car size={16} />, 'text-[#EF4444]', 'border-t-[#EF4444]', 'bg-rose-50 text-[#EF4444]')}
        {metric('Unique track IDs', analytics?.total_unique_tracked_vehicles ?? '—', 'Within jobs/cameras; no cross-camera merge', <Car size={16} />, 'text-[#00A8C6]', 'border-t-[#00A8C6]', 'bg-teal-50 text-[#00A8C6]')}
        {metric('Plate detections', analytics?.total_plates_detected ?? '—', 'Persisted plate results', <ScanLine size={16} />, 'text-[#0891B2]', 'border-t-[#0891B2]', 'bg-cyan-50 text-[#0891B2]')}
        {metric('Recognized plates', analytics?.recognized_registration_numbers ?? '—', 'Non-empty normalized OCR candidates', <ScanLine size={16} />, 'text-[#F59E0B]', 'border-t-[#F59E0B]', 'bg-amber-50 text-[#F59E0B]')}
        {metric('Cameras', cameras.length, 'Configured camera records', <Video size={16} />, 'text-[#0F172A]', 'border-t-[#0F172A]', 'bg-slate-100 text-[#0F172A]')}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="bg-white rounded-2xl border border-slate-200/90 p-5 lg:col-span-2 shadow-sm">
          <div className="mb-4 flex items-start justify-between">
            <div>
              <h2 className="font-bold text-base text-slate-900">Persisted traffic observations</h2>
              <p className="text-[11px] text-[#64748B]">{analytics?.time_basis ?? 'No time series available'}</p>
            </div>
            <Link to="/analytics" className="flex items-center gap-1 text-xs font-semibold text-[#00A8C6] hover:text-[#0090AA] transition">
              Analytics <ArrowRight size={13} />
            </Link>
          </div>
          {analytics?.time_series.length ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={analytics.time_series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="period" stroke="#64748b" fontSize={10} />
                  <YAxis stroke="#64748b" fontSize={10} />
                  <Tooltip contentStyle={{ background: '#FFFFFF', borderColor: '#CBD5E1', color: '#0F172A', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                  <Area type="monotone" dataKey="vehicles" name="Vehicle detections" stroke="#00A8C6" fill="#00A8C6" fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="py-16 text-center text-xs text-slate-500">No persisted detections in this time range.</p>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-bold text-base text-slate-900">Active alerts</h2>
            <Link to="/alerts" className="text-xs font-semibold text-[#00A8C6] hover:text-[#0090AA] transition">
              View all ({alerts.length})
            </Link>
          </div>
          {alerts.length ? (
            alerts.slice(0, 5).map((a) => (
              <div key={a.id} className="border-t border-[#E2E8F0] py-2.5">
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span className="uppercase font-mono font-bold text-[#F59E0B]">{a.severity} · {a.source ?? 'legacy'}</span>
                  <span>{new Date(a.created_at).toLocaleString()}</span>
                </div>
                <p className="mt-1 text-xs text-slate-700 font-medium">{a.message}</p>
              </div>
            ))
          ) : (
            <p className="py-8 text-center text-xs text-slate-500">No unresolved alert records.</p>
          )}
        </div>
      </section>

      <section className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="font-bold text-base text-slate-900">Configured camera locations</h2>
            <p className="text-[11px] text-[#64748B]">Camera coordinates only; this map does not imply a vehicle route.</p>
          </div>
          <Link to="/cameras" className="text-xs font-semibold text-[#00A8C6] hover:text-[#0090AA] transition">
            Manage cameras
          </Link>
        </div>
        {cameras.length ? (
          <LeafletRouteMap
            cameras={cameras.map((c) => ({
              id: c.id,
              name: c.location_name || c.name,
              latitude: c.latitude,
              longitude: c.longitude,
              weather: c.weather_condition,
            }))}
            height="300px"
          />
        ) : (
          <p className="py-10 text-center text-xs text-slate-500">No cameras with persisted location records.</p>
        )}
      </section>

      <section className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="font-bold text-base text-slate-900">Recent persisted ANPR observations</h2>
            <p className="text-[11px] text-[#64748B]">Raw OCR, normalized text and validation remain distinct.</p>
          </div>
          <Link to="/detections" className="flex items-center gap-1 text-xs font-semibold text-[#00A8C6] hover:text-[#0090AA] transition">
            History <ArrowRight size={13} />
          </Link>
        </div>
        {detections?.items.length ? (
          <div className="grid gap-2.5 md:grid-cols-2">
            {detections.items.map((d) => (
              <article key={`${d.source}-${d.record_id}`} className="rounded-xl border border-slate-200/90 bg-[#F8FAFC] p-3.5 hover:bg-white hover:border-teal-200 transition-colors shadow-sm">
                <div className="flex justify-between gap-2">
                  <b className="font-mono text-emerald-700 font-bold">{d.validated_registration_number ?? 'Not validated'}</b>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {d.source === 'live_camera' ? 'Live' : 'Media'} · {new Date(d.timestamp).toLocaleString()}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-700">
                  {d.camera_name ?? d.camera_id ?? 'No camera'} · track {d.track_id ?? 'unassigned'} · raw: {d.raw_ocr_text ?? '—'} · normalized: {d.normalized_ocr_text ?? '—'}
                </p>
                <p className="mt-1 text-[10px] text-slate-500 tabular-nums">
                  OCR confidence {d.ocr_confidence == null ? '—' : `${(d.ocr_confidence * 100).toFixed(1)}%`} · Plate confidence {d.plate_confidence == null ? 'Not available' : `${(d.plate_confidence * 100).toFixed(1)}%`}
                </p>
              </article>
            ))}
          </div>
        ) : (
          <p className="py-8 text-center text-xs text-slate-500">No persisted ANPR records are available.</p>
        )}
      </section>

      <section className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-sm">
        <h2 className="mb-3 font-bold text-base text-slate-900">Vehicle classification observations</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {Object.entries(analytics?.vehicles_by_class ?? {}).map(([name, count]) => (
            <div key={name} className="rounded-xl border border-slate-200/90 bg-[#F8FAFC] p-3.5">
              <p className="text-[10px] uppercase font-mono text-slate-500 font-bold">{name.replace(/_/g, ' ')}</p>
              <p className="mt-1.5 text-xl font-extrabold font-mono tabular-nums text-slate-900">{count}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-sm">
        <h2 className="mb-3 font-bold text-base text-slate-900">Camera-wise detections</h2>
        {analytics?.camera_statistics.length ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {analytics.camera_statistics.map((c) => (
              <div key={c.camera_id} className="flex justify-between items-center rounded-xl border border-slate-200/90 bg-[#F8FAFC] p-3 text-xs">
                <span className="text-slate-800 font-medium">
                  {c.camera_name} <span className="text-slate-500 font-mono">({c.camera_id})</span>
                </span>
                <b className="text-[#00A8C6] font-mono tabular-nums font-bold text-sm">{c.vehicle_detections}</b>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500">No camera-associated detection records.</p>
        )}
      </section>
    </div>
  );
};
