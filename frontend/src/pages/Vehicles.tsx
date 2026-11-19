import React, { useState } from 'react';
import { Car, Search, ScanLine } from 'lucide-react';
import { api } from '../services/api';
import type { ANPRSearchPage } from '../types';

export const Vehicles: React.FC = () => {
  const [registration, setRegistration] = useState('');
  const [results, setResults] = useState<ANPRSearchPage | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const search = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      setResults(await api.searchANPRHistory({ registration: registration.trim(), limit: 100, offset: 0 }));
    } catch (err: any) {
      setResults(null);
      setError(err?.response?.data?.detail ?? 'Could not search persisted ANPR history.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Hero Spotlight ANPR Lookup Header */}
      <section className="rounded-2xl bg-[#111C2D] border border-[#26354D] p-6 text-white shadow-md">
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#00A8C6] animate-ping" />
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest px-2.5 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-700/50">
              INDIAN REGISTRATION AUDIT · HISTORICAL ARCHIVE
            </span>
          </div>
          <h1 className="flex items-center gap-2.5 text-xl lg:text-2xl font-extrabold text-white tracking-tight">
            <Car className="text-[#00A8C6] w-6 h-6" />
            <span>Vehicle Dossier & Plate History Search</span>
          </h1>
          <p className="mt-1 text-xs text-[#CBD5E1] leading-relaxed">
            Search validated Indian registration numbers across completed inference jobs and physical cameras. Matching records verify observations within local topological nodes.
          </p>
        </div>

        <form onSubmit={search} className="flex flex-wrap items-end gap-3 pt-2">
          <label className="min-w-64 flex-1 text-xs text-[#CBD5E1] font-semibold">
            <span className="flex items-center gap-1.5 mb-1.5">
              <ScanLine className="w-3.5 h-3.5 text-[#00A8C6]" />
              Indian Registration Number (HSRP)
            </span>
            <input
              required
              maxLength={32}
              value={registration}
              onChange={(e) => setRegistration(e.target.value)}
              placeholder="e.g. KA01AB1234, DL04C9988"
              className="block w-full rounded-xl border border-[#26354D] bg-[#09111E] px-4 py-2.5 font-mono text-sm text-white placeholder-[#94A3B8] focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-inner"
            />
          </label>
          <button
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl bg-[#00A8C6] hover:bg-[#0090AA] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition disabled:opacity-50"
          >
            <Search size={15} />
            {loading ? 'Searching…' : 'Search History'}
          </button>
        </form>
      </section>

      {error && <p role="alert" className="rounded-2xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800 shadow-sm font-medium">{error}</p>}

      {results && (
        <>
          <p className="text-xs text-slate-600 font-medium">
            {results.total.toLocaleString()} matching persisted observations for <span className="font-mono font-bold text-[#00A8C6]">{results.registration}</span>. Track IDs are local to their media job or camera.
          </p>
          {results.items.length === 0 ? (
            <div className="rounded-2xl border border-slate-200/90 bg-white p-8 text-center text-sm text-slate-500 shadow-sm">
              No matching real inference records were found.
            </div>
          ) : (
            <div className="space-y-3.5">
              {results.items.map((item) => (
                <article key={`${item.source}-${item.record_id}`} className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-sm hover:border-teal-200 transition">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="flex items-center gap-2 font-mono text-lg font-bold text-emerald-700">
                        <ScanLine size={16} />
                        {item.validated_registration_number ?? 'Not validated'}
                      </h2>
                      <p className="mt-1 text-xs text-slate-500 font-medium">
                        {new Date(item.timestamp).toLocaleString()} · {item.source === 'live_camera' ? 'Live camera' : 'Uploaded media'} · {item.camera_name ?? item.camera_id ?? 'No camera'} · {item.vehicle_class ?? 'Vehicle class unavailable'}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Tracking ID: {item.track_id ?? 'not assigned'} · Raw OCR: <span className="font-mono text-slate-700 font-medium">{item.raw_ocr_text ?? '—'}</span> · Normalized: <span className="font-mono text-slate-700 font-medium">{item.normalized_ocr_text ?? '—'}</span>
                      </p>
                      <p className="mt-1 text-xs text-slate-500 tabular-nums">
                        OCR confidence: {item.ocr_confidence == null ? '—' : `${(item.ocr_confidence * 100).toFixed(1)}%`} · Plate detector confidence: {item.plate_confidence == null ? 'Not available' : `${(item.plate_confidence * 100).toFixed(1)}%`}
                      </p>
                    </div>
                    <div className="flex gap-3 text-xs font-semibold">
                      {item.original_url && <a className="text-[#00A8C6] hover:text-[#0090AA] transition" href={item.original_url} target="_blank" rel="noreferrer">Original image</a>}
                      {item.plate_crop_url && <a className="text-[#00A8C6] hover:text-[#0090AA] transition" href={item.plate_crop_url} target="_blank" rel="noreferrer">Plate crop</a>}
                      {item.route_history_url && <a className="text-[#00A8C6] hover:text-[#0090AA] transition" href={item.route_history_url}>Route history</a>}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      )}

      {!results && !error && (
        <div className="rounded-2xl border border-slate-200/90 bg-white p-8 text-center text-sm text-slate-500 shadow-sm font-medium">
          Enter an Indian registration number above to search persisted ANPR history.
        </div>
      )}
    </div>
  );
};
