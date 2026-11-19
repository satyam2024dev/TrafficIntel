import React from 'react';
import { ScanLine } from 'lucide-react';
import { MediaDetection, MediaPlateResult } from '../types';
import { classifyProcessingModes, modeLabel } from '../utils/mediaProcessing';

interface PlateResultCardProps {
  plate: MediaPlateResult;
  detection?: MediaDetection;
  metadata: Record<string, unknown>;
  selected: boolean;
  onSelect: () => void;
}

export const PlateResultCard: React.FC<PlateResultCardProps> = ({ plate, detection, metadata, selected, onSelect }) => {
  const original = plate.original_crop_url;
  const enhanced = plate.enhanced_crop_url;
  const recognizedText = plate.normalized_ocr_text ?? plate.plate_text;
  const temporal = plate.enhancement_metadata?.temporal_aggregation as { consensus_candidate?: unknown; observation_count?: unknown } | null;
  const modes = classifyProcessingModes(metadata);
  return (
    <button type="button" onClick={onSelect} aria-pressed={selected} className={`w-full rounded-xl border p-4 text-left transition ${selected ? 'border-amber-400 bg-amber-950/20 ring-1 ring-amber-500/40' : 'border-[#222634] bg-[#11131A] hover:border-[#2B3040]'}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-center gap-2"><ScanLine className="h-4 w-4 text-rose-400" /><span className="license-plate-ui px-2 py-1 text-sm">{recognizedText || 'No OCR text recognized'}</span></div>
        <span className="text-[10px] font-mono text-blue-400 tabular-nums">OCR {plate.ocr_confidence === null ? 'confidence unavailable' : `${(plate.ocr_confidence * 100).toFixed(1)}%`}</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <p className="mb-1 text-[9px] font-mono uppercase tracking-wider text-slate-500">Original crop</p>
          {original ? <img src={original} alt={`Original crop for plate ${plate.plate_text}`} className="h-20 w-full rounded border border-[#222634] bg-black object-contain" /> : <div className="flex h-20 items-center justify-center rounded border border-[#222634] text-[10px] text-slate-500">Crop unavailable</div>}
        </div>
        <div>
          <p className="mb-1 text-[9px] font-mono uppercase tracking-wider text-blue-400">Enhanced crop</p>
          {enhanced ? <img src={enhanced} alt={`Enhanced crop for plate ${plate.plate_text}`} className="h-20 w-full rounded border border-blue-900/40 bg-black object-contain" /> : <div className="flex h-20 items-center justify-center rounded border border-[#222634] text-[10px] text-slate-500">Enhanced crop unavailable</div>}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-mono text-slate-400">
        <span>Plate detector confidence: {plate.plate_confidence === null ? 'Not available (heuristic localization)' : `${(plate.plate_confidence * 100).toFixed(1)}%`}</span>
        {plate.raw_ocr_text && plate.raw_ocr_text !== recognizedText && <span>Raw OCR: {plate.raw_ocr_text}</span>}
        {plate.plate_validation_status && <span>Format: {plate.plate_validation_status.replace(/_/g, ' ')}</span>}
        {typeof temporal?.consensus_candidate === 'string' && <span>Track OCR consensus: {temporal.consensus_candidate} ({String(temporal.observation_count ?? 1)} matching reads)</span>}
        {detection?.track_id && <span>Track #{detection.track_id}</span>}
        {plate.frame_number !== null && <span>Frame {plate.frame_number}</span>}
        {plate.timestamp !== null && <span>{plate.timestamp.toFixed(2)}s</span>}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {modes.map((mode) => <span key={mode} className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-[9px] font-bold tracking-wider text-slate-300">{modeLabel(mode)}</span>)}
      </div>
    </button>
  );
};
