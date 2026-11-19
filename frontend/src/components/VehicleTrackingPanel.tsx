import React, { useEffect, useState } from 'react';
import { Activity, Route } from 'lucide-react';
import { api } from '../services/api';
import { VehicleTrackHistoryResponse, VehicleTrackSummary, VehicleTrackSummaryResponse } from '../types';
import { getApiErrorMessage } from '../utils/mediaProcessing';
import { VehicleGeographicRoutePanel } from './VehicleGeographicRoutePanel';

interface VehicleTrackingPanelProps {
  jobId: number;
  summary: VehicleTrackSummaryResponse | null;
  selectedTrackId: string | null;
  onTrackSelect: (trackId: string | null) => void;
  onFrameSelect: (frameNumber: number) => void;
  error: string | null;
}

const confidence = (value: number | null | undefined) => value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`;

export const VehicleTrackingPanel: React.FC<VehicleTrackingPanelProps> = ({ jobId, summary, selectedTrackId, onTrackSelect, onFrameSelect, error }) => {
  const [history, setHistory] = useState<VehicleTrackHistoryResponse | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const tracks = summary?.tracks ?? [];
  const selectedTrack = tracks.find((track) => track.track_id === selectedTrackId) ?? null;

  useEffect(() => {
    if (!selectedTrackId) {
      setHistory(null);
      setHistoryError(null);
      return;
    }
    let active = true;
    setHistoryLoading(true);
    void api.getVehicleTrackHistory(jobId, selectedTrackId).then((result) => {
      if (active) {
        setHistory(result);
        setHistoryError(null);
      }
    }).catch((loadError) => {
      if (active) setHistoryError(getApiErrorMessage(loadError));
    }).finally(() => { if (active) setHistoryLoading(false); });
    return () => { active = false; };
  }, [jobId, selectedTrackId]);

  return <><section className="glass-panel space-y-3 rounded-xl border border-[#222634] p-4 shadow-sm" aria-labelledby="vehicle-tracking-heading">
    <div>
      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-blue-500">ByteTrack · sampled video</p>
      <h3 id="vehicle-tracking-heading" className="mt-1 flex items-center gap-2 text-base font-bold text-white"><Route className="h-4 w-4 text-blue-500" /> Vehicle tracks and image-space trajectories</h3>
      <p className="mt-1 text-[10px] text-slate-500">Centers and paths are measured in source-video pixels. They are not geographic or GPS routes.</p>
    </div>
    {error && <p role="alert" className="rounded border border-rose-900/60 bg-rose-950/30 p-2 text-xs text-rose-200">{error}</p>}
    {!summary && !error && <p className="text-xs text-slate-500">Loading tracking summary…</p>}
    {summary && <>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <SummaryMetric label="Unique tracked vehicles" value={summary.total_unique_tracked_vehicles} />
        <SummaryMetric label="Detection records" value={summary.total_detection_records} />
        <SummaryMetric label="Unassigned track IDs" value={summary.untracked_detection_count} />
        <SummaryMetric label="Tracks with plate reads" value={tracks.filter((track) => track.plate_read_count > 0).length} />
      </div>
      {tracks.length === 0 ? <p role="status" className="rounded border border-[#222634] bg-[#11131A] p-3 text-xs text-slate-400">No stable ByteTrack IDs were assigned. Detections remain available with null tracking IDs.</p> : <div className="grid gap-3 xl:grid-cols-[minmax(240px,0.7fr)_minmax(0,1.3fr)]">
        <div className="max-h-72 space-y-1 overflow-y-auto rounded border border-[#222634] bg-[#11131A] p-2">
          {tracks.map((track) => <TrackButton key={track.track_id} track={track} selected={track.track_id === selectedTrackId} onSelect={() => onTrackSelect(track.track_id)} />)}
        </div>
        <div className="min-w-0 rounded border border-[#222634] bg-[#11131A] p-3">
          {!selectedTrack && <p className="py-6 text-center text-xs text-slate-500">Select a track to inspect its detections and plate associations.</p>}
          {selectedTrack && <>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><h4 className="font-mono text-xs font-bold text-blue-400">Track #{selectedTrack.track_id} · {selectedTrack.vehicle_class}</h4><span className="text-[10px] text-slate-400">{selectedTrack.frame_count} frames · {selectedTrack.duration_seconds.toFixed(2)}s · mean detection {confidence(selectedTrack.mean_detection_confidence)}</span></div>
            {historyLoading && <p className="py-2 text-xs text-slate-500">Loading detection history…</p>}
            {historyError && <p role="alert" className="py-2 text-xs text-rose-300">{historyError}</p>}
            {history && <div className="max-h-80 overflow-auto">
              <table className="w-full min-w-[680px] text-left text-[10px]">
                <thead className="sticky top-0 bg-[#171A24] text-slate-400"><tr><th className="p-2">Frame / time</th><th className="p-2">Center (x, y)</th><th className="p-2">Bounding box (x1, y1, x2, y2)</th><th className="p-2">Detection confidence</th><th className="p-2">Associated plate / OCR</th></tr></thead>
                <tbody className="divide-y divide-[#222634]">{history.points.map((point) => <tr key={point.detection_id} className="text-slate-300">
                  <td className="p-2"><button type="button" onClick={() => point.frame_number !== null && onFrameSelect(point.frame_number)} className="font-mono text-blue-400 hover:text-blue-300">{point.frame_number ?? '—'} · {point.timestamp === null ? '—' : `${point.timestamp.toFixed(2)}s`}</button></td>
                  <td className="p-2 font-mono tabular-nums">{point.center_x.toFixed(1)}, {point.center_y.toFixed(1)}</td>
                  <td className="p-2 font-mono tabular-nums">{point.bbox.x1.toFixed(0)}, {point.bbox.y1.toFixed(0)}, {point.bbox.x2.toFixed(0)}, {point.bbox.y2.toFixed(0)}</td>
                  <td className="p-2 tabular-nums">{confidence(point.detection_confidence)}</td>
                  <td className="p-2">{point.plate_reads?.length ? point.plate_reads.map((plate) => <span key={plate.plate_result_id} className="mr-1 inline-block font-mono text-amber-300">{plate.normalized_ocr_text || plate.raw_ocr_text || 'Plate · no OCR'} · OCR {confidence(plate.ocr_confidence)}</span>) : 'No plate associated'}</td>
                </tr>)}</tbody>
              </table>
            </div>}
          </>}
        </div>
      </div>}
    </>}
  </section><VehicleGeographicRoutePanel jobId={jobId} /></>;
};

const TrackButton: React.FC<{ track: VehicleTrackSummary; selected: boolean; onSelect: () => void }> = ({ track, selected, onSelect }) => (
  <button type="button" onClick={onSelect} aria-pressed={selected} className={`w-full rounded border px-3 py-2 text-left transition ${selected ? 'border-blue-500 bg-blue-600/10' : 'border-transparent hover:border-[#2B3040] hover:bg-[#171A24]'}`}>
    <span className="flex items-center justify-between gap-2"><span className="font-mono text-xs font-bold text-blue-400">#{track.track_id} · {track.vehicle_class}</span><Activity className="h-3.5 w-3.5 text-blue-500" /></span>
    <span className="mt-1 block text-[10px] text-slate-400 tabular-nums">{track.frame_count} frames · {track.duration_seconds.toFixed(2)}s · {track.plate_read_count} plate reads</span>
    {track.plate_reads.filter((plate) => plate.normalized_ocr_text).slice(0, 2).map((plate) => <span key={plate.plate_result_id} className="mt-1 block truncate font-mono text-[10px] text-amber-300">{plate.normalized_ocr_text}</span>)}
  </button>
);

const SummaryMetric: React.FC<{ label: string; value: number }> = ({ label, value }) => <div className="rounded border border-[#222634] bg-[#11131A] p-2"><span className="block text-[9px] uppercase tracking-wider text-slate-400">{label}</span><span className="mt-1 block text-sm font-bold text-white tabular-nums">{value}</span></div>;
