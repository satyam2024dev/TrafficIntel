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

  const metric = (label: string, value: string | number, caption: string, icon: React.ReactNode) => (
    <div className="glass-panel rounded-xl border border-[#222634] p-4 shadow-sm border-t-2 border-t-blue-600">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>{label}</span>
        <div className="p-2 rounded-lg bg-[#171A24] border border-[#2B3040] text-blue-400">
          {icon}
        </div>
      </div>
      <p className="mt-2 text-2xl font-bold font-mono tabular-nums text-white">{value}</p>
      <p className="mt-1 text-[10px] text-slate-400">{caption}</p>
    </div>
  );

  return (
    <div className="space-y-6">
      <MediaProcessingWorkspace />

      <header>
        <h1 className="text-xl font-bold text-white tracking-tight">Traffic intelligence overview</h1>
        <p className="mt-1 text-xs text-slate-400">
          Counts aggregate completed real-inference jobs and persisted live-camera events. Track IDs are scoped to a job or camera; OCR confidence is not accuracy.
        </p>
      </header>

      {error && <p role="alert" className="rounded-lg border border-rose-800 bg-rose-950/40 p-3 text-sm text-rose-200">{error}</p>}

      <section className="grid grid-cols-2 gap-3 xl:grid-cols-5">
        {metric('Vehicle detections', analytics?.total_vehicle_detections ?? '—', 'Persisted detection observations', <Car size={16} />)}
        {metric('Unique track IDs', analytics?.total_unique_tracked_vehicles ?? '—', 'Within jobs/cameras; no cross-camera merge', <Car size={16} />)}
        {metric('Plate detections', analytics?.total_plates_detected ?? '—', 'Persisted plate results', <ScanLine size={16} />)}
        {metric('Recognized plates', analytics?.recognized_registration_numbers ?? '—', 'Non-empty normalized OCR candidates', <ScanLine size={16} />)}
        {metric('Cameras', cameras.length, 'Configured camera records', <Video size={16} />)}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="glass-panel rounded-xl border border-[#222634] p-5 lg:col-span-2 shadow-sm">
          <div className="mb-4 flex items-start justify-between">
            <div>
              <h2 className="font-semibold text-white">Persisted traffic observations</h2>
              <p className="text-[11px] text-slate-400">{analytics?.time_basis ?? 'No time series available'}</p>
            </div>
            <Link to="/analytics" className="flex items-center gap-1 text-xs font-medium text-blue-400 hover:text-blue-300 transition">
              Analytics <ArrowRight size={13} />
            </Link>
          </div>
          {analytics?.time_series.length ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={analytics.time_series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222634" />
                  <XAxis dataKey="period" stroke="#64748b" fontSize={10} />
                  <YAxis stroke="#64748b" fontSize={10} />
                  <Tooltip contentStyle={{ background: '#11131A', borderColor: '#222634', color: '#F8FAFC', borderRadius: '8px' }} />
                  <Area type="monotone" dataKey="vehicles" name="Vehicle detections" stroke="#2563EB" fill="#2563EB" fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="py-16 text-center text-xs text-slate-500">No persisted detections in this time range.</p>
          )}
        </div>

        <div className="glass-panel rounded-xl border border-[#222634] p-5 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-white">Active alerts</h2>
            <Link to="/alerts" className="text-xs font-medium text-blue-400 hover:text-blue-300 transition">
              View all ({alerts.length})
            </Link>
          </div>
          {alerts.length ? (
            alerts.slice(0, 5).map((a) => (
              <div key={a.id} className="border-t border-[#222634] py-2.5">
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span className="uppercase font-mono text-amber-400">{a.severity} · {a.source ?? 'legacy'}</span>
                  <span>{new Date(a.created_at).toLocaleString()}</span>
                </div>
                <p className="mt-1 text-xs text-slate-200">{a.message}</p>
              </div>
            ))
          ) : (
            <p className="py-8 text-center text-xs text-slate-500">No unresolved alert records.</p>
          )}
        </div>
      </section>

      <section className="glass-panel rounded-xl border border-[#222634] p-5 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-white">Configured camera locations</h2>
            <p className="text-[11px] text-slate-400">Camera coordinates only; this map does not imply a vehicle route.</p>
          </div>
          <Link to="/cameras" className="text-xs font-medium text-blue-400 hover:text-blue-300 transition">
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

      <section className="glass-panel rounded-xl border border-[#222634] p-5 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-white">Recent persisted ANPR observations</h2>
            <p className="text-[11px] text-slate-400">Raw OCR, normalized text and validation remain distinct.</p>
          </div>
          <Link to="/detections" className="flex items-center gap-1 text-xs font-medium text-blue-400 hover:text-blue-300 transition">
            History <ArrowRight size={13} />
          </Link>
        </div>
        {detections?.items.length ? (
          <div className="grid gap-2.5 md:grid-cols-2">
            {detections.items.map((d) => (
              <article key={`${d.source}-${d.record_id}`} className="rounded-lg border border-[#222634] bg-[#171A24]/60 p-3">
                <div className="flex justify-between gap-2">
                  <b className="font-mono text-emerald-400">{d.validated_registration_number ?? 'Not validated'}</b>
                  <span className="text-[10px] text-slate-400">
                    {d.source === 'live_camera' ? 'Live' : 'Media'} · {new Date(d.timestamp).toLocaleString()}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-300">
                  {d.camera_name ?? d.camera_id ?? 'No camera'} · track {d.track_id ?? 'unassigned'} · raw: {d.raw_ocr_text ?? '—'} · normalized: {d.normalized_ocr_text ?? '—'}
                </p>
                <p className="mt-1 text-[10px] text-slate-400 tabular-nums">
                  OCR confidence {d.ocr_confidence == null ? '—' : `${(d.ocr_confidence * 100).toFixed(1)}%`} · Plate confidence {d.plate_confidence == null ? 'Not available' : `${(d.plate_confidence * 100).toFixed(1)}%`}
                </p>
              </article>
            ))}
          </div>
        ) : (
          <p className="py-8 text-center text-xs text-slate-500">No persisted ANPR records are available.</p>
        )}
      </section>

      <section className="glass-panel rounded-xl border border-[#222634] p-5 shadow-sm">
        <h2 className="mb-3 font-semibold text-white">Vehicle classification observations</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {Object.entries(analytics?.vehicles_by_class ?? {}).map(([name, count]) => (
            <div key={name} className="rounded-lg border border-[#222634] bg-[#171A24]/60 p-3">
              <p className="text-[10px] uppercase font-mono text-slate-400">{name.replace(/_/g, ' ')}</p>
              <p className="mt-1 text-lg font-bold font-mono tabular-nums text-white">{count}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="glass-panel rounded-xl border border-[#222634] p-5 shadow-sm">
        <h2 className="mb-3 font-semibold text-white">Camera-wise detections</h2>
        {analytics?.camera_statistics.length ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {analytics.camera_statistics.map((c) => (
              <div key={c.camera_id} className="flex justify-between rounded-lg border border-[#222634] bg-[#171A24]/60 p-3 text-xs">
                <span className="text-slate-300">
                  {c.camera_name} <span className="text-slate-500">({c.camera_id})</span>
                </span>
                <b className="text-blue-400 font-mono tabular-nums">{c.vehicle_detections}</b>
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
