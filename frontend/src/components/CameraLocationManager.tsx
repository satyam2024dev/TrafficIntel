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

  return <section className="bg-white space-y-4 rounded-2xl border border-slate-200/90 p-6 shadow-sm" aria-labelledby="camera-location-heading">
    <div><h2 id="camera-location-heading" className="text-sm font-bold text-[#0F172A]">Camera locations and calibration</h2><p className="mt-1 text-xs text-slate-500">Enter surveyed camera coordinates and direction. Calibration maps image pixels to nearby ground-plane meters using paired image and GPS control points.</p></div>
    {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 font-medium">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800 font-medium">{message}</p>}
    <label className="block max-w-sm text-xs text-slate-700 font-medium">Camera<select value={cameraId} onChange={(event) => setCameraId(event.target.value)} className="mt-1 block w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-xs text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#00A8C6]">{cameras.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.name}</option>)}</select></label>
    {camera && <div className="grid gap-4 xl:grid-cols-2">
      <form onSubmit={(event) => void saveLocation(event)} className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
        <h3 className="text-xs font-bold text-[#0891B2]">Camera location</h3>
        <div className="grid grid-cols-2 gap-2">{([
          ['name', 'Camera name'], ['location_name', 'Location'], ['latitude', 'Latitude'], ['longitude', 'Longitude'], ['direction', 'Direction / view'], ['road_segment', 'Road segment'],
        ] as const).map(([key, label]) => <label key={key} className="text-[10px] text-slate-600 font-medium">{label}<input required value={location[key]} onChange={(event) => setLocation((current) => ({ ...current, [key]: event.target.value }))} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-[#0F172A] font-mono focus:border-[#00A8C6] focus:outline-none" /></label>)}</div>
        <button disabled={saving} className="rounded-xl bg-[#00A8C6] hover:bg-[#0090AA] px-4 py-2 text-xs font-semibold text-white shadow-sm disabled:opacity-50">Save camera details</button>
      </form>
      <form onSubmit={(event) => void calibrate(event)} className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-xs font-bold text-emerald-700">Image-to-ground calibration</h3><span className="text-[10px] text-slate-500 font-mono font-medium">{camera.calibration_point_count ? `Calibrated · ${camera.calibration_point_count} points` : 'Not calibrated'}</span></div>
        <div className="grid grid-cols-2 gap-2"><label className="text-[10px] text-slate-600 font-medium">Image width<input required min="1" type="number" value={imageSize.width} onChange={(event) => setImageSize((current) => ({ ...current, width: event.target.value }))} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-[#0F172A] font-mono focus:border-[#00A8C6] focus:outline-none" /></label><label className="text-[10px] text-slate-600 font-medium">Image height<input required min="1" type="number" value={imageSize.height} onChange={(event) => setImageSize((current) => ({ ...current, height: event.target.value }))} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-[#0F172A] font-mono focus:border-[#00A8C6] focus:outline-none" /></label></div>
        <p className="text-[10px] text-slate-500">At least four non-collinear surveyed points are required. x/y are source-image pixels; lat/lon must be actual ground control measurements.</p>
        {points.map((point, index) => <div key={index} className="grid grid-cols-4 gap-1.5">
          {([['image_x', 'Image x'], ['image_y', 'Image y'], ['latitude', 'Latitude'], ['longitude', 'Longitude']] as const).map(([key, label]) => <label key={key} className="text-[9px] text-slate-600 font-medium">{label}<input required type="number" step="any" value={point[key]} onChange={(event) => setPointField(index, key, event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-1 text-[10px] text-[#0F172A] font-mono focus:border-[#00A8C6] focus:outline-none" /></label>)}
          {points.length > 4 && <button type="button" onClick={() => setPoints((current) => current.filter((_item, pointIndex) => pointIndex !== index))} aria-label={`Remove calibration point ${index + 1}`} className="col-span-4 text-right text-[10px] text-rose-600 font-medium hover:text-rose-800">Remove point</button>}
        </div>)}
        <div className="flex flex-wrap gap-2 pt-1"><button type="button" onClick={() => setPoints((current) => [...current, emptyPoint()])} className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 shadow-sm font-medium">Add control point</button><button disabled={saving} className="rounded-xl bg-emerald-600 hover:bg-emerald-700 px-4 py-2 text-xs font-semibold text-white shadow-sm disabled:opacity-50">Save calibration</button>{camera.calibration_homography && <button type="button" disabled={saving} onClick={() => void clearCalibration()} className="rounded-xl border border-rose-300 bg-white px-3 py-2 text-xs text-rose-700 hover:bg-rose-50 shadow-sm font-semibold disabled:opacity-50">Clear calibration</button>}</div>
      </form>
    </div>}
  </section>;
};
