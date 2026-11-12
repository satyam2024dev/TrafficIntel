import React, { useEffect, useState } from 'react';
import { ScanLine, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { api } from '../services/api';
import type { ANPRSearchPage, Camera } from '../types';

export const ANPRDetections: React.FC = () => {
  const [data, setData] = useState<ANPRSearchPage | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [camera, setCamera] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  useEffect(() => { api.getCameras().then(setCameras).catch(() => setCameras([])); }, []);
  useEffect(() => {
    let active = true;
    api.getANPRDetections({ camera_id: camera || undefined, start_at: start ? `${start}T00:00:00Z` : undefined, end_at: end ? `${end}T23:59:59Z` : undefined, limit: 50, offset })
      .then((page) => { if (active) { setData(page); setError(''); } }).catch((e) => { if (active) setError(e?.response?.data?.detail ?? 'Could not load persisted ANPR results.'); });
    return () => { active = false; };
  }, [camera, start, end, offset]);
  return <div className="space-y-5">
    <header><h1 className="flex items-center gap-2 text-xl font-bold text-white"><ScanLine className="text-cyan-400"/>ANPR detection history</h1><p className="mt-1 text-xs text-slate-400">Persisted detections from completed real-inference jobs and live cameras. Cross-camera identity is not inferred.</p></header>
    <form onSubmit={(e) => { e.preventDefault(); setOffset(0); }} className="glass-panel flex flex-wrap items-end gap-3 rounded-xl border border-slate-800 p-4">
      <label className="text-xs text-slate-400">Camera<select value={camera} onChange={(e) => { setCamera(e.target.value); setOffset(0); }} className="mt-1 block rounded border border-slate-700 bg-slate-950 p-2 text-white"><option value="">All cameras</option>{cameras.map(c => <option key={c.id} value={c.id}>{c.name} ({c.id})</option>)}</select></label>
      <label className="text-xs text-slate-400">From<input type="date" value={start} onChange={e => { setStart(e.target.value); setOffset(0); }} className="mt-1 block rounded border border-slate-700 bg-slate-950 p-2 text-white"/></label>
      <label className="text-xs text-slate-400">To<input type="date" value={end} onChange={e => { setEnd(e.target.value); setOffset(0); }} className="mt-1 block rounded border border-slate-700 bg-slate-950 p-2 text-white"/></label>
      <a href={api.getAnalyticsExportUrl('anpr', { ...(camera ? {camera_id: camera} : {}), ...(start ? {start_at: `${start}T00:00:00Z`} : {}), ...(end ? {end_at: `${end}T23:59:59Z`} : {}) })} className="rounded border border-slate-700 px-3 py-2 text-xs text-cyan-300">Export CSV</a>
    </form>
    {error && <p role="alert" className="rounded border border-rose-800 p-3 text-sm text-rose-200">{error}</p>}
    <p className="text-xs text-slate-400">{data ? `${data.total.toLocaleString()} persisted plate records` : 'Loading…'}</p>
    <div className="overflow-x-auto rounded-xl border border-slate-800"><table className="w-full min-w-[1000px] text-left text-xs"><thead className="bg-slate-900 text-slate-400"><tr>{['Time / source','Camera','Track / class','Raw OCR','Normalized OCR','Validated registration','OCR confidence','Plate confidence','Artifacts / route'].map(x=><th key={x} className="p-3">{x}</th>)}</tr></thead><tbody>{data?.items.map(row=><tr key={`${row.source}-${row.record_id}`} className="border-t border-slate-800 text-slate-300">
      <td className="p-3">{new Date(row.timestamp).toLocaleString()}<div className="text-[10px] text-slate-500">{row.source === 'live_camera' ? 'Live capture' : `Media job${row.media_timestamp_seconds != null ? ` · ${row.media_timestamp_seconds.toFixed(2)}s` : ''}`}</div></td><td className="p-3">{row.camera_name ?? row.camera_id ?? '—'}</td><td className="p-3">{row.track_id ?? 'No track ID'}<div className="text-[10px] text-slate-500">{row.vehicle_class ?? '—'}</div></td><td className="p-3 font-mono">{row.raw_ocr_text ?? '—'}</td><td className="p-3 font-mono">{row.normalized_ocr_text ?? '—'}</td><td className="p-3 font-mono text-emerald-300">{row.validated_registration_number ?? 'Not validated'}</td><td className="p-3">{row.ocr_confidence == null ? '—' : `${(row.ocr_confidence * 100).toFixed(1)}%`}</td><td className="p-3">{row.plate_confidence == null ? 'Not available' : `${(row.plate_confidence * 100).toFixed(1)}%`}</td><td className="p-3"><div className="flex gap-2">{row.original_url && <a className="text-cyan-300" href={row.original_url} target="_blank" rel="noreferrer">Image</a>}{row.plate_crop_url && <a className="text-cyan-300" href={row.plate_crop_url} target="_blank" rel="noreferrer">Crop</a>}{row.route_history_url && <a className="text-cyan-300" href={row.route_history_url} target="_blank" rel="noreferrer">Route</a>}</div></td></tr>)}{data?.items.length === 0 && <tr><td colSpan={9} className="p-8 text-center text-slate-500">No persisted ANPR records match these filters.</td></tr>}</tbody></table></div>
    <div className="flex items-center justify-end gap-3"><button disabled={!data || offset===0} onClick={()=>setOffset(Math.max(0,offset-50))} className="rounded border border-slate-700 p-2 text-slate-300 disabled:opacity-40"><ChevronLeft size={16}/></button><span className="text-xs text-slate-400">{data ? `${offset+1}–${Math.min(offset+50,data.total)} of ${data.total}` : ''}</span><button disabled={!data || offset+50>=data.total} onClick={()=>setOffset(offset+50)} className="rounded border border-slate-700 p-2 text-slate-300 disabled:opacity-40"><ChevronRight size={16}/></button></div>
  </div>;
};
