import React, { useEffect, useState } from 'react';
import { ScanLine, ChevronLeft, ChevronRight } from 'lucide-react';
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

  useEffect(() => {
    api.getCameras().then(setCameras).catch(() => setCameras([]));
  }, []);

  useEffect(() => {
    let active = true;
    api
      .getANPRDetections({
        camera_id: camera || undefined,
        start_at: start ? `${start}T00:00:00Z` : undefined,
        end_at: end ? `${end}T23:59:59Z` : undefined,
        limit: 50,
        offset,
      })
      .then((page) => {
        if (active) {
          setData(page);
          setError('');
        }
      })
      .catch((e) => {
        if (active) setError(e?.response?.data?.detail ?? 'Could not load persisted ANPR results.');
      });
    return () => {
      active = false;
    };
  }, [camera, start, end, offset]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="flex items-center gap-2.5 text-xl font-extrabold text-slate-900 tracking-tight">
          <ScanLine className="text-[#00A8C6] w-6 h-6" />
          <span>ANPR Detection History & Audit</span>
        </h1>
        <p className="mt-1 text-xs text-slate-500">
          Persisted detections from completed real-inference jobs and live cameras. Cross-camera identity is not inferred.
        </p>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setOffset(0);
        }}
        className="bg-white flex flex-wrap items-end gap-3 rounded-2xl border border-slate-200/90 p-5 shadow-sm"
      >
        <label className="text-xs text-slate-600 font-semibold">
          Camera
          <select
            value={camera}
            onChange={(e) => {
              setCamera(e.target.value);
              setOffset(0);
            }}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          >
            <option value="">All cameras</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.id})
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-600 font-semibold">
          From
          <input
            type="date"
            value={start}
            onChange={(e) => {
              setStart(e.target.value);
              setOffset(0);
            }}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          />
        </label>
        <label className="text-xs text-slate-600 font-semibold">
          To
          <input
            type="date"
            value={end}
            onChange={(e) => {
              setEnd(e.target.value);
              setOffset(0);
            }}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          />
        </label>
        <a
          href={api.getAnalyticsExportUrl('anpr', {
            ...(camera ? { camera_id: camera } : {}),
            ...(start ? { start_at: `${start}T00:00:00Z` } : {}),
            ...(end ? { end_at: `${end}T23:59:59Z` } : {}),
          })}
          className="rounded-xl bg-[#00A8C6] hover:bg-[#0090AA] px-4 py-2 text-xs font-semibold text-white shadow-sm transition"
        >
          Export CSV
        </a>
      </form>

      {error && <p role="alert" className="rounded-2xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800 shadow-sm font-medium">{error}</p>}

      <p className="text-xs text-slate-600 font-mono font-medium">
        {data ? `${data.total.toLocaleString()} persisted plate records` : 'Loading…'}
      </p>

      <div className="overflow-x-auto rounded-2xl border border-slate-200/90 bg-white shadow-sm">
        <table className="w-full min-w-[1000px] text-left text-xs">
          <thead className="bg-[#F8FAFC] text-slate-600 border-b border-[#E2E8F0]">
            <tr>
              {[
                'Time / source',
                'Camera',
                'Track / class',
                'Raw OCR',
                'Normalized OCR',
                'Validated registration',
                'OCR confidence',
                'Plate confidence',
                'Artifacts / route',
              ].map((x) => (
                <th key={x} className="p-3.5 font-bold uppercase text-[10px] font-mono">
                  {x}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0]">
            {data?.items.map((row) => (
              <tr key={`${row.source}-${row.record_id}`} className="text-slate-700 hover:bg-slate-50 transition">
                <td className="p-3.5">
                  <span className="font-mono">{new Date(row.timestamp).toLocaleString()}</span>
                  <div className="text-[10px] text-slate-500">
                    {row.source === 'live_camera'
                      ? 'Live capture'
                      : `Media job${row.media_timestamp_seconds != null ? ` · ${row.media_timestamp_seconds.toFixed(2)}s` : ''}`}
                  </div>
                </td>
                <td className="p-3.5 font-medium">{row.camera_name ?? row.camera_id ?? '—'}</td>
                <td className="p-3.5 font-mono">
                  {row.track_id ?? 'No track ID'}
                  <div className="text-[10px] text-slate-500">{row.vehicle_class ?? '—'}</div>
                </td>
                <td className="p-3.5 font-mono">{row.raw_ocr_text ?? '—'}</td>
                <td className="p-3.5 font-mono">{row.normalized_ocr_text ?? '—'}</td>
                <td className="p-3.5 font-mono font-bold text-emerald-700">
                  {row.validated_registration_number ?? 'Not validated'}
                </td>
                <td className="p-3.5 font-mono tabular-nums">
                  {row.ocr_confidence == null ? '—' : `${(row.ocr_confidence * 100).toFixed(1)}%`}
                </td>
                <td className="p-3.5 font-mono tabular-nums">
                  {row.plate_confidence == null ? 'Not available' : `${(row.plate_confidence * 100).toFixed(1)}%`}
                </td>
                <td className="p-3.5">
                  <div className="flex gap-2 font-semibold">
                    {row.original_url && (
                      <a className="text-[#00A8C6] hover:text-[#0090AA] transition" href={row.original_url} target="_blank" rel="noreferrer">
                        Image
                      </a>
                    )}
                    {row.plate_crop_url && (
                      <a className="text-[#00A8C6] hover:text-[#0090AA] transition" href={row.plate_crop_url} target="_blank" rel="noreferrer">
                        Crop
                      </a>
                    )}
                    {row.route_history_url && (
                      <a className="text-[#00A8C6] hover:text-[#0090AA] transition" href={row.route_history_url} target="_blank" rel="noreferrer">
                        Route
                      </a>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {data?.items.length === 0 && (
              <tr>
                <td colSpan={9} className="p-8 text-center text-slate-500">
                  No persisted ANPR records match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-end gap-3">
        <button
          disabled={!data || offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 50))}
          className="rounded-xl border border-slate-300 bg-white p-2 text-slate-700 hover:bg-slate-50 hover:text-[#00A8C6] shadow-sm disabled:opacity-40 transition"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="text-xs font-mono text-slate-600 tabular-nums font-semibold">
          {data ? `${offset + 1}–${Math.min(offset + 50, data.total)} of ${data.total}` : ''}
        </span>
        <button
          disabled={!data || offset + 50 >= data.total}
          onClick={() => setOffset(offset + 50)}
          className="rounded-xl border border-slate-300 bg-white p-2 text-slate-700 hover:bg-slate-50 hover:text-[#00A8C6] shadow-sm disabled:opacity-40 transition"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
};
