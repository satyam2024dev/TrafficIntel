import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import { Camera } from '../types';
import { getApiErrorMessage } from '../utils/mediaProcessing';

type CalibrationField = 'image_x' | 'image_y' | 'latitude' | 'longitude';
const emptyPoint = () => ({ image_x: '', image_y: '', latitude: '', longitude: '' });

export const CameraLocationManager: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [cameraId, setCameraId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const camera = useMemo(() => cameras.find((item) => item.id === cameraId) ?? null, [cameras, cameraId]);
  const [location, setLocation] = useState({ name: '', location_name: '', latitude: '', longitude: '', direction: '', road_segment: '' });
  const [imageSize, setImageSize] = useState({ width: '', height: '' });
  const [points, setPoints] = useState([emptyPoint(), emptyPoint(), emptyPoint(), emptyPoint()]);

  const refresh = async () => {
    try {
      const data = await api.getCameras();
      setCameras(data);
      if (!cameraId && data.length) setCameraId(data[0].id);
      setError(null);
    } catch (cause) { setError(getApiErrorMessage(cause)); }
  };
  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    if (!camera) return;
    setLocation({ name: camera.name, location_name: camera.location_name, latitude: String(camera.latitude), longitude: String(camera.longitude), direction: camera.direction ?? 'unknown', road_segment: camera.road_segment });
  }, [camera]);

  const saveLocation = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!camera) return;
    setSaving(true); setError(null); setMessage(null);
    try {
      await api.updateCameraLocation(camera.id, { ...location, latitude: Number(location.latitude), longitude: Number(location.longitude) });
      await refresh(); setMessage('Camera location and direction saved.');
    } catch (cause) { setError(getApiErrorMessage(cause)); }
    finally { setSaving(false); }
  };

  const calibrate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!camera) return;
    const numeric = points.map((point) => Object.fromEntries(Object.entries(point).map(([key, value]) => [key, Number(value)])) as unknown as { image_x: number; image_y: number; latitude: number; longitude: number });
    if (numeric.some((point) => Object.values(point).some((value) => !Number.isFinite(value)))) {
      setError('Enter image x/y and surveyed latitude/longitude for every calibration point.'); return;
    }
    setSaving(true); setError(null); setMessage(null);
    try {
      const result = await api.calibrateCamera(camera.id, { image_width: Number(imageSize.width), image_height: Number(imageSize.height), points: numeric });
      await refresh(); setMessage(`Calibration saved from ${result.point_count} paired points.`);
    } catch (cause) { setError(getApiErrorMessage(cause)); }
    finally { setSaving(false); }
  };

  const clearCalibration = async () => {
    if (!camera) return;
    setSaving(true); setError(null); setMessage(null);
    try { await api.clearCameraCalibration(camera.id); await refresh(); setMessage('Camera calibration removed.'); }
    catch (cause) { setError(getApiErrorMessage(cause)); }
    finally { setSaving(false); }
  };

  const setPointField = (index: number, field: CalibrationField, value: string) => setPoints((current) => current.map((point, pointIndex) => pointIndex === index ? { ...point, [field]: value } : point));

  return <section className="glass-panel space-y-4 rounded-xl border border-slate-800 p-5" aria-labelledby="camera-location-heading">
    <div><h2 id="camera-location-heading" className="text-sm font-bold text-white">Camera locations and calibration</h2><p className="mt-1 text-xs text-slate-400">Enter surveyed camera coordinates and direction. Calibration maps image pixels to nearby ground-plane meters using paired image and GPS control points.</p></div>
    {error && <p role="alert" className="rounded border border-rose-900/60 bg-rose-950/30 p-2 text-xs text-rose-200">{error}</p>}
    {message && <p role="status" className="rounded border border-emerald-900/60 bg-emerald-950/30 p-2 text-xs text-emerald-200">{message}</p>}
    <label className="block max-w-sm text-xs text-slate-300">Camera<select value={cameraId} onChange={(event) => setCameraId(event.target.value)} className="mt-1 block w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white">{cameras.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.name}</option>)}</select></label>
    {camera && <div className="grid gap-4 xl:grid-cols-2">
      <form onSubmit={(event) => void saveLocation(event)} className="space-y-2 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
        <h3 className="text-xs font-bold text-cyan-200">Camera location</h3>
        <div className="grid grid-cols-2 gap-2">{([
          ['name', 'Camera name'], ['location_name', 'Location'], ['latitude', 'Latitude'], ['longitude', 'Longitude'], ['direction', 'Direction / view'], ['road_segment', 'Road segment'],
        ] as const).map(([key, label]) => <label key={key} className="text-[10px] text-slate-400">{label}<input required value={location[key]} onChange={(event) => setLocation((current) => ({ ...current, [key]: event.target.value }))} className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-white" /></label>)}</div>
        <button disabled={saving} className="rounded bg-cyan-500 px-3 py-2 text-xs font-bold text-slate-950 disabled:opacity-50">Save camera details</button>
      </form>
      <form onSubmit={(event) => void calibrate(event)} className="space-y-2 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-xs font-bold text-emerald-200">Image-to-ground calibration</h3><span className="text-[10px] text-slate-500">{camera.calibration_point_count ? `Calibrated · ${camera.calibration_point_count} points` : 'Not calibrated'}</span></div>
        <div className="grid grid-cols-2 gap-2"><label className="text-[10px] text-slate-400">Image width<input required min="1" type="number" value={imageSize.width} onChange={(event) => setImageSize((current) => ({ ...current, width: event.target.value }))} className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-white" /></label><label className="text-[10px] text-slate-400">Image height<input required min="1" type="number" value={imageSize.height} onChange={(event) => setImageSize((current) => ({ ...current, height: event.target.value }))} className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-white" /></label></div>
        <p className="text-[10px] text-slate-500">At least four non-collinear surveyed points are required. x/y are source-image pixels; lat/lon must be actual ground control measurements.</p>
        {points.map((point, index) => <div key={index} className="grid grid-cols-4 gap-1.5">
          {([['image_x', 'Image x'], ['image_y', 'Image y'], ['latitude', 'Latitude'], ['longitude', 'Longitude']] as const).map(([key, label]) => <label key={key} className="text-[9px] text-slate-500">{label}<input required type="number" step="any" value={point[key]} onChange={(event) => setPointField(index, key, event.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-1.5 py-1 text-[10px] text-white" /></label>)}
          {points.length > 4 && <button type="button" onClick={() => setPoints((current) => current.filter((_item, pointIndex) => pointIndex !== index))} aria-label={`Remove calibration point ${index + 1}`} className="col-span-4 text-right text-[10px] text-rose-300">Remove point</button>}
        </div>)}
        <div className="flex flex-wrap gap-2"><button type="button" onClick={() => setPoints((current) => [...current, emptyPoint()])} className="rounded border border-slate-700 px-3 py-2 text-xs text-slate-300">Add control point</button><button disabled={saving} className="rounded bg-emerald-500 px-3 py-2 text-xs font-bold text-slate-950 disabled:opacity-50">Save calibration</button>{camera.calibration_homography && <button type="button" disabled={saving} onClick={() => void clearCalibration()} className="rounded border border-rose-900 px-3 py-2 text-xs text-rose-300 disabled:opacity-50">Clear calibration</button>}</div>
      </form>
    </div>}
  </section>;
};
