import React, { useEffect, useState } from 'react';
import { Activity, Camera, Play, Square, Video } from 'lucide-react';
import { GeographicRouteMap } from '../components/GeographicRouteMap';
import { useTrafficData } from '../hooks/useTrafficData';
import { api } from '../services/api';
import type { Camera as CameraType, LiveCameraStatus, LiveDetectionEvent, LiveGeographicRoutesResponse } from '../types';

const errorText = (error: unknown) => {
  if (typeof error === 'object' && error && 'response' in error) return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Camera request failed.';
  return error instanceof Error ? error.message : 'Camera request failed.';
};

export const LiveMonitoring: React.FC = () => {
  const { startSimulation, pauseSimulation, resetSimulation, isSimRunning, isSimPaused } = useTrafficData();
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [cameraId, setCameraId] = useState('');
  const [status, setStatus] = useState<LiveCameraStatus | null>(null);
  const [events, setEvents] = useState<LiveDetectionEvent[]>([]);
  const [routes, setRoutes] = useState<LiveGeographicRoutesResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => { let alive = true; api.getCameras().then((rows) => { if (alive) { setCameras(rows); setCameraId((current) => current || rows[0]?.id || ''); } }).catch((e) => alive && setError(errorText(e))); return () => { alive = false; }; }, []);
  useEffect(() => {
    if (!cameraId) { setStatus(null); setEvents([]); setRoutes(null); return; }
    let alive = true;
    const poll = async () => {
      try {
        const [nextStatus, nextEvents, nextRoutes] = await Promise.all([api.getLiveCameraStatus(cameraId), api.getLiveCameraEvents(cameraId), api.getLiveCameraRoutes(cameraId)]);
        if (alive) { setStatus(nextStatus); setEvents(nextEvents); setRoutes(nextRoutes); setError(''); }
      } catch (e) { if (alive) setError(errorText(e)); }
    };
    void poll(); const timer = window.setInterval(() => { void poll(); }, 2000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [cameraId]);

  const control = async (action: 'start' | 'stop') => {
    if (!cameraId) return;
    setBusy(true); setError('');
    try { setStatus(action === 'start' ? await api.startLiveCamera(cameraId) : await api.stopLiveCamera(cameraId)); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  };
  const connected = status?.status === 'connected';
  const selected = cameras.find((item) => item.id === cameraId);
  const sourceActive = ['starting', 'connected', 'reconnecting'].includes(status?.status ?? '');

  return (
    <div className="space-y-6">
      <header className="glass-panel rounded-xl border border-[#222634] p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4 shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Video className="w-5 h-5 text-blue-500" />
            <span>Live Camera Monitoring</span>
          </h1>
          <p className="mt-1 text-xs text-slate-400">
            Frames and overlays below come from the selected physical camera and the real inference pipeline.
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <select aria-label="Select camera" className="rounded-lg bg-[#171A24] border border-[#2B3040] p-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium" value={cameraId} onChange={(e) => setCameraId(e.target.value)}>
            <option value="">Select a camera</option>
            {cameras.map((cam) => <option key={cam.id} value={cam.id}>{cam.name} ({cam.id})</option>)}
          </select>
          <button disabled={busy || !cameraId || !selected?.stream_configured || sourceActive} onClick={() => void control('start')} className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition disabled:opacity-40">
            <Play size={14} className="fill-current" />Start
          </button>
          <button disabled={busy || !sourceActive} onClick={() => void control('stop')} className="inline-flex items-center gap-1.5 rounded-lg bg-[#171A24] hover:bg-[#222634] border border-[#2B3040] px-3.5 py-2 text-xs font-semibold text-slate-300 transition disabled:opacity-40">
            <Square size={13} />Stop
          </button>
        </div>
      </header>

      {!cameras.length ? (
        <div className="rounded-xl border border-amber-800/60 bg-amber-950/20 p-5 text-sm text-amber-200">
          No camera is registered. Add a camera and configure a webcam or allowlisted RTSP source on the Cameras page.
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)] gap-6">
          <section className="glass-panel rounded-xl border border-[#222634] p-4 space-y-3 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-white">{selected?.name ?? 'Camera feed'}</h2>
                <p className="text-xs text-slate-400">{selected?.location_name ?? ''} {selected?.direction ? `· ${selected.direction}` : ''}</p>
              </div>
              <span className={`text-xs uppercase font-mono font-semibold ${connected ? 'text-emerald-400' : status?.status === 'failed' ? 'text-rose-400' : 'text-amber-400'}`}>
                <Activity className="inline mr-1" size={13} />{status?.status ?? 'stopped'}
              </span>
            </div>
            {connected ? (
              <img key={cameraId} src={api.getLiveCameraStreamUrl(cameraId)} alt={`${selected?.name ?? 'Camera'} live frame with detected vehicle and plate overlays`} className="w-full aspect-video rounded-lg bg-black object-contain border border-[#222634]" onError={() => setError('The live frame stream ended. Check camera status and reconnect if needed.')} />
            ) : (
              <div className="aspect-video rounded-lg border border-[#222634] bg-[#0D0F16] flex flex-col items-center justify-center text-center p-6">
                <Camera className="text-slate-600 mb-3" size={34} />
                <p className="text-sm text-slate-300">{status?.status === 'reconnecting' ? 'Camera disconnected. Reconnection is in progress.' : status?.status === 'failed' ? 'Live processing failed.' : selected?.stream_configured ? 'Monitoring is starting or stopped. The live view appears after the first successful frame.' : 'No physical camera source is configured.'}</p>
                <p className="mt-2 text-xs text-slate-500">The live view does not substitute demo footage or generated detections.</p>
              </div>
            )}
            <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-400 font-mono">
              <span>Last frame: {status?.last_frame_at ? new Date(status.last_frame_at).toLocaleString() : 'none received'}</span>
              <span className="tabular-nums">Reconnects: {status?.reconnect_count ?? 0}</span>
              <span>Size: {status?.frame_width && status.frame_height ? `${status.frame_width}×${status.frame_height}` : 'unknown'}</span>
            </div>
            {(error || status?.error) && <p role="alert" className="text-sm text-rose-300">{error || status?.error}</p>}
          </section>

          <section className="glass-panel rounded-xl border border-[#222634] p-4 shadow-sm">
            <h2 className="font-semibold text-white mb-3">Recent detections</h2>
            {events.length ? (
              <div className="space-y-2 max-h-[510px] overflow-auto">
                {events.map((event) => (
                  <article key={event.id} className="rounded-lg border border-[#222634] bg-[#171A24]/60 p-3 text-xs">
                    <div className="flex justify-between gap-2">
                      <strong className="text-blue-400 font-mono font-bold">{event.plate_text || event.normalized_ocr_text || event.raw_ocr_text || 'Plate not read'}</strong>
                      <span className="text-slate-400 font-mono text-[10px]">{new Date(event.captured_at).toLocaleTimeString()}</span>
                    </div>
                    <p className="mt-1 text-slate-300">Track {event.track_id ?? 'unassigned'} · {event.vehicle_class} · vehicle {event.vehicle_confidence.toFixed(2)}</p>
                    <p className="text-slate-400 font-mono text-[11px] tabular-nums">OCR conf: {event.ocr_confidence == null ? '—' : event.ocr_confidence.toFixed(2)} · plate conf: {event.plate_confidence == null ? '—' : event.plate_confidence.toFixed(2)}</p>
                    {event.raw_ocr_text && <p className="text-slate-400 font-mono text-[10px]">Raw OCR: {event.raw_ocr_text}</p>}
                    {event.plate_crop_url && <img src={event.plate_crop_url} alt="Detected license plate crop" className="mt-2 max-h-16 rounded border border-[#222634] bg-black object-contain" />}
                  </article>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No persisted detections for this camera yet.</p>
            )}
          </section>
        </div>
      )}

      {routes && (
        <section className="glass-panel rounded-xl border border-[#222634] p-4 space-y-3 shadow-sm">
          <div>
            <h2 className="font-semibold text-white">Calibrated geographic estimates</h2>
            <p className="text-xs text-slate-400">Only calibrated ground-plane points and imported GPS observations appear here. Pixel coordinates are never shown as geographic positions.</p>
          </div>
          {routes.tracks.length ? (
            <GeographicRouteMap tracks={routes.tracks} />
          ) : (
            <p className="text-sm text-slate-500">{routes.limitations.join(' ') || 'No valid geographic route points are available.'}</p>
          )}
        </section>
      )}

      <details className="rounded-xl border border-[#222634] bg-[#11131A] p-4 shadow-sm">
        <summary className="cursor-pointer text-xs font-semibold text-slate-400 hover:text-slate-200">Synthetic simulation demo (separate from physical camera feeds)</summary>
        <p className="mt-3 text-xs text-amber-300">Demo controls below do not produce camera frames or live ANPR events.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button onClick={() => void startSimulation()} disabled={isSimRunning && !isSimPaused} className="rounded-lg bg-[#171A24] border border-[#2B3040] px-3 py-2 text-xs font-semibold text-white hover:bg-[#222634] transition">Start demo</button>
          <button onClick={() => void pauseSimulation()} disabled={!isSimRunning || isSimPaused} className="rounded-lg bg-[#171A24] border border-[#2B3040] px-3 py-2 text-xs font-semibold text-white hover:bg-[#222634] transition">Pause demo</button>
          <button onClick={() => void resetSimulation()} className="rounded-lg bg-[#171A24] border border-[#2B3040] px-3 py-2 text-xs font-semibold text-white hover:bg-[#222634] transition">Reset demo</button>
          <span className="self-center text-xs font-mono text-slate-400 ml-2">{isSimRunning ? (isSimPaused ? 'Paused' : 'Running') : 'Stopped'}</span>
        </div>
      </details>
    </div>
  );
};
