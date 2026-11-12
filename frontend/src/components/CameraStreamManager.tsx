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

  return <section className="glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
    <div><h2 className="text-base font-bold text-white">Live camera sources</h2><p className="text-xs text-slate-400 mt-1">Configure a local webcam or an allowlisted RTSP source. Stream credentials are stored by the backend and never returned.</p></div>
    {!cameras.length ? <p className="text-sm text-amber-300">No camera records are configured yet. Add a camera above before connecting a physical device.</p> : <>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <label className="text-xs text-slate-400">Camera<select className="mt-1 w-full rounded bg-slate-950 border border-slate-700 p-2 text-white" value={selected} onChange={(e) => setSelected(e.target.value)}>{cameras.map((cam) => <option key={cam.id} value={cam.id}>{cam.name} ({cam.id})</option>)}</select></label>
        <label className="text-xs text-slate-400">Source<select className="mt-1 w-full rounded bg-slate-950 border border-slate-700 p-2 text-white" value={source} onChange={(e) => setSource(e.target.value as 'webcam' | 'rtsp')}><option value="webcam">Local webcam</option><option value="rtsp">RTSP stream</option></select></label>
        {source === 'webcam' ? <label className="text-xs text-slate-400">Device index<input type="number" min="0" max="15" className="mt-1 w-full rounded bg-slate-950 border border-slate-700 p-2 text-white" value={deviceIndex} onChange={(e) => setDeviceIndex(Number(e.target.value))} /></label> : <label className="text-xs text-slate-400 md:col-span-2">RTSP URL<input type="password" autoComplete="new-password" className="mt-1 w-full rounded bg-slate-950 border border-slate-700 p-2 text-white" placeholder="rtsp://user:password@host:554/path" value={streamUrl} onChange={(e) => setStreamUrl(e.target.value)} /></label>}
        <button disabled={busy || !selected || (source === 'rtsp' && !streamUrl)} onClick={() => void configure()} className="rounded bg-cyan-700 hover:bg-cyan-600 disabled:opacity-50 p-2 text-sm text-white">Save source</button>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-slate-800 pt-4">
        <span className="text-xs text-slate-300">State: <strong className="uppercase">{status?.status ?? 'stopped'}</strong></span>
        <span className="text-xs text-slate-400">Configured source: {cameras.find((cam) => cam.id === selected)?.stream_configured ? cameras.find((cam) => cam.id === selected)?.stream_type : 'none'}</span>
        <button disabled={busy || !cameras.find((cam) => cam.id === selected)?.stream_configured || ['starting', 'connected', 'reconnecting'].includes(status?.status ?? '')} onClick={() => void control('start')} className="rounded bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 px-3 py-2 text-xs text-white">Start monitoring</button>
        <button disabled={busy || !['starting', 'connected', 'reconnecting'].includes(status?.status ?? '')} onClick={() => void control('stop')} className="rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-3 py-2 text-xs text-white">Stop</button>
        {status?.last_frame_at && <span className="text-xs text-slate-400">Last frame: {new Date(status.last_frame_at).toLocaleString()}</span>}
        {(status?.reconnect_count ?? 0) > 0 && <span className="text-xs text-amber-300">Reconnects: {status?.reconnect_count}</span>}
      </div>
      {(error || status?.error) && <p role="alert" className="text-sm text-rose-300">{error || status?.error}</p>}
    </>}
  </section>;
};
