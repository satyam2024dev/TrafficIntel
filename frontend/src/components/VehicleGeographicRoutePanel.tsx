import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { GeographicRoutesResponse } from '../types';
import { getApiErrorMessage } from '../utils/mediaProcessing';
import { GeographicRouteMap } from './GeographicRouteMap';

export const VehicleGeographicRoutePanel: React.FC<{ jobId: number }> = ({ jobId }) => {
  const [routes, setRoutes] = useState<GeographicRoutesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  useEffect(() => {
    let active = true;
    setRoutes(null);
    setError(null);
    void api.getGeographicRoutes(jobId).then((data) => { if (active) setRoutes(data); }).catch((cause) => { if (active) setError(getApiErrorMessage(cause)); });
    return () => { active = false; };
  }, [jobId, refreshVersion]);

  return <section className="glass-panel space-y-3 rounded-xl border border-[#222634] p-4 shadow-sm" aria-labelledby="geographic-route-heading">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div>
      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-emerald-400">Geographic route reconstruction</p>
      <h3 id="geographic-route-heading" className="mt-1 text-base font-bold text-white">Valid geographic observations</h3>
      <p className="mt-1 text-[10px] text-slate-500">Only external GPS observations and calibrated camera estimates are mapped. Image pixels are never treated as GPS.</p>
      </div>
      <button type="button" onClick={() => setRefreshVersion((version) => version + 1)} className="rounded border border-[#2B3040] bg-[#171A24] px-2 py-1 text-[10px] text-slate-300 hover:text-white">Refresh routes</button>
    </div>
    {error && <p role="alert" className="rounded border border-rose-900/60 bg-rose-950/30 p-2 text-xs text-rose-200">Route history unavailable: {error}</p>}
    {!routes && !error && <p className="text-xs text-slate-500">Loading geographic route data...</p>}
    {routes && routes.tracks.length === 0 && <div role="status" className="rounded border border-[#222634] bg-[#11131A] p-3 text-xs text-slate-300">
      <p>No geographic routes are available for this job.</p>
      <p className="mt-1 text-slate-500">Select a camera with a calibration matching this video's dimensions, or attach time-stamped GPS observations to tracked IDs. Uncalibrated image coordinates cannot be mapped.</p>
    </div>}
    {routes && routes.tracks.length > 0 && <>
      <div className="flex flex-wrap gap-2 text-[10px]">
        {routes.available_sources.map((source) => <span key={source} className="rounded border border-emerald-900/70 bg-emerald-950/40 px-2 py-1 text-emerald-200">{source === 'gps_observation' ? 'External GPS observation' : 'Calibrated estimate'}</span>)}
        <span className="rounded border border-[#2B3040] bg-[#171A24] px-2 py-1 text-slate-400">GPS and video-relative timestamps are separate; map lines do not join across time bases</span>
        {routes.unassigned_geographic_point_count > 0 && <span className="rounded border border-amber-900/70 bg-amber-950/30 px-2 py-1 text-amber-200">{routes.unassigned_geographic_point_count} geographic observations lack a tracker ID and are not included in track routes</span>}
      </div>
      <GeographicRouteMap tracks={routes.tracks} />
      <div className="max-h-72 overflow-auto rounded border border-[#222634]">
        <table className="w-full min-w-[700px] text-left text-[10px]">
          <thead className="sticky top-0 bg-[#171A24] text-slate-400"><tr><th className="p-2">Track ID</th><th className="p-2">Camera / direction</th><th className="p-2">Time</th><th className="p-2">Latitude, longitude</th><th className="p-2">Source</th><th className="p-2">Plate readings (track association)</th></tr></thead>
          <tbody className="divide-y divide-[#222634]">{routes.tracks.flatMap((track) => track.points.map((point) => <tr key={point.id} className="text-slate-300">
            <td className="p-2 font-mono text-blue-400 tabular-nums">#{track.track_id}</td>
            <td className="p-2">{point.camera_name || point.camera_id || 'External GPS'}{point.camera_direction && point.camera_direction !== 'unknown' ? ` · ${point.camera_direction}` : ''}</td>
            <td className="p-2">{point.timestamp ? new Date(point.timestamp).toLocaleString() : point.media_timestamp_seconds === null ? 'Unavailable' : `Video +${point.media_timestamp_seconds.toFixed(2)} s`}</td>
            <td className="p-2 font-mono tabular-nums">{point.latitude.toFixed(6)}, {point.longitude.toFixed(6)}</td>
            <td className="p-2">{point.source_type === 'gps_observation' ? 'GPS observation' : 'Calibrated estimate'}</td>
            <td className="p-2 font-mono text-amber-300">{(point.plate_reads.length ? point.plate_reads.map((plate) => plate.validated_registration_number || plate.normalized_ocr_text || plate.raw_ocr_text) : track.plate_reads.map((plate) => plate.validated_registration_number || plate.normalized_ocr_text || plate.raw_ocr_text)).filter(Boolean).join(', ') || 'No plate read available'}</td>
          </tr>))}</tbody>
        </table>
      </div>
    </>}
  </section>;
};
