import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { Camera, LiveCameraStatus } from '../types';

const message = (error: unknown) => {
  if (typeof error === 'object' && error && 'response' in error) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (detail) return detail;
  }
  return error instanceof Error ? error.message : 'Camera request failed.';
};

export const CameraStreamManager: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selected, setSelected] = useState('');
  const [source, setSource] = useState<'webcam' | 'rtsp'>('webcam');
  const [deviceIndex, setDeviceIndex] = useState(0);
  const [streamUrl, setStreamUrl] = useState('');
  const [status, setStatus] = useState<LiveCameraStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const refresh = async () => {
    const rows = await api.getCameras();
    setCameras(rows);
    if (!selected && rows.length) setSelected(rows[0].id);
  };
  useEffect(() => { void refresh().catch((e) => setError(message(e))); }, []);
  useEffect(() => {
    if (!selected) return;
    let alive = true;
    const poll = async () => {
      try { const next = await api.getLiveCameraStatus(selected); if (alive) setStatus(next); }
      catch (e) { if (alive) setError(message(e)); }
    };
    void poll();
    const timer = window.setInterval(() => { void poll(); }, 2500);
    return () => { alive = false; window.clearInterval(timer); };
  }, [selected]);

  const configure = async () => {
    if (!selected) return;
    setBusy(true); setError('');
    try {
      await api.configureCameraStream(selected, source === 'webcam'
        ? { source_type: source, device_index: deviceIndex }
        : { source_type: source, stream_url: streamUrl });
      setStreamUrl('');
      await refresh();
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };
  const control = async (action: 'start' | 'stop') => {
    if (!selected) return;
    setBusy(true); setError('');
    try { setStatus(action === 'start' ? await api.startLiveCamera(selected) : await api.stopLiveCamera(selected)); }
    catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };

  return <section className="bg-white p-6 rounded-2xl border border-slate-200/90 space-y-4 shadow-sm">
    <div><h2 className="text-base font-bold text-[#0F172A]">Live camera sources</h2><p className="text-xs text-slate-500 mt-1">Configure a local webcam or an allowlisted RTSP source. Stream credentials are stored by the backend and never returned.</p></div>
    {!cameras.length ? <p className="text-sm text-amber-700 font-medium">No camera records are configured yet. Add a camera above before connecting a physical device.</p> : <>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <label className="text-xs text-slate-600 font-medium">Camera<select className="mt-1 w-full rounded-xl bg-slate-50 border border-slate-300 p-2.5 text-[#0F172A] text-xs focus:outline-none focus:ring-2 focus:ring-[#00A8C6]" value={selected} onChange={(e) => setSelected(e.target.value)}>{cameras.map((cam) => <option key={cam.id} value={cam.id}>{cam.name} ({cam.id})</option>)}</select></label>
        <label className="text-xs text-slate-600 font-medium">Source<select className="mt-1 w-full rounded-xl bg-slate-50 border border-slate-300 p-2.5 text-[#0F172A] text-xs focus:outline-none focus:ring-2 focus:ring-[#00A8C6]" value={source} onChange={(e) => setSource(e.target.value as 'webcam' | 'rtsp')}><option value="webcam">Local webcam</option><option value="rtsp">RTSP stream</option></select></label>
        {source === 'webcam' ? <label className="text-xs text-slate-600 font-medium">Device index<input type="number" min="0" max="15" className="mt-1 w-full rounded-xl bg-slate-50 border border-slate-300 p-2 text-[#0F172A] font-mono text-xs focus:outline-none focus:ring-2 focus:ring-[#00A8C6]" value={deviceIndex} onChange={(e) => setDeviceIndex(Number(e.target.value))} /></label> : <label className="text-xs text-slate-600 font-medium md:col-span-2">RTSP URL<input type="password" autoComplete="new-password" className="mt-1 w-full rounded-xl bg-slate-50 border border-slate-300 p-2 text-[#0F172A] font-mono text-xs focus:outline-none focus:ring-2 focus:ring-[#00A8C6]" placeholder="rtsp://user:password@host:554/path" value={streamUrl} onChange={(e) => setStreamUrl(e.target.value)} /></label>}
        <button disabled={busy || !selected || (source === 'rtsp' && !streamUrl)} onClick={() => void configure()} className="rounded-xl bg-[#00A8C6] hover:bg-[#0090AA] disabled:opacity-50 px-4 py-2.5 text-xs font-semibold text-white shadow-sm transition">Save source</button>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-4">
        <span className="text-xs text-slate-700 font-medium">State: <strong className="uppercase font-mono text-[#0891B2]">{status?.status ?? 'stopped'}</strong></span>
        <span className="text-xs text-slate-500">Configured source: {cameras.find((cam) => cam.id === selected)?.stream_configured ? cameras.find((cam) => cam.id === selected)?.stream_type : 'none'}</span>
        <button disabled={busy || !cameras.find((cam) => cam.id === selected)?.stream_configured || ['starting', 'connected', 'reconnecting'].includes(status?.status ?? '')} onClick={() => void control('start')} className="rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 px-4 py-2 text-xs font-semibold text-white shadow-sm transition">Start monitoring</button>
        <button disabled={busy || !['starting', 'connected', 'reconnecting'].includes(status?.status ?? '')} onClick={() => void control('stop')} className="rounded-xl bg-white hover:bg-slate-50 border border-slate-300 disabled:opacity-50 px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm transition">Stop</button>
        {status?.last_frame_at && <span className="text-xs text-slate-500 font-mono">Last frame: {new Date(status.last_frame_at).toLocaleString()}</span>}
        {(status?.reconnect_count ?? 0) > 0 && <span className="text-xs text-amber-700 font-mono tabular-nums font-semibold">Reconnects: {status?.reconnect_count}</span>}
      </div>
      {(error || status?.error) && <p role="alert" className="text-xs text-rose-700 font-medium">{error || status?.error}</p>}
    </>}
  </section>;
};
