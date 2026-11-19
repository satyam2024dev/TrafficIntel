import React from 'react';
import { Activity, CarFront, CloudSun, ScanLine, Target } from 'lucide-react';
import { MediaDetection, MediaPlateResult, ProcessingResults as ProcessingResultsData } from '../types';
import { classifyProcessingModes, modeLabel, processingSummary } from '../utils/mediaProcessing';
import { PlateResultCard } from './PlateResultCard';

interface ProcessingResultsProps {
  results: ProcessingResultsData;
  selectedPlateId: number | null;
  onPlateSelect: (id: number) => void;
}

const confidenceText = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(1)}%`;

export const ProcessingResults: React.FC<ProcessingResultsProps> = ({ results, selectedPlateId, onPlateSelect }) => {
  const summary = processingSummary(results);
  const metadata = results.processing_metadata;
  const modes = classifyProcessingModes(metadata);
  const weather = String(metadata.weather_condition ?? 'Not classified');
  const operations = Array.from(new Set(results.frames.map((frame) => String(frame.enhancement_metadata?.frame_enhancement ?? '')).filter(Boolean)));
  const detectionForPlate = (plate: MediaPlateResult) => results.detections.find((detection) => detection.id === plate.detection_id);
  const plateByDetection = new Map<number, MediaPlateResult>();
  results.plate_results.forEach((plate) => { if (plate.detection_id !== null) plateByDetection.set(plate.detection_id, plate); });
  const ocrUnavailable = String(metadata.ocr_provider ?? '').toUpperCase().includes('UNAVAILABLE') || String(metadata.error ?? '').toLowerCase().includes('ocr');
  const plateDetectorError = typeof metadata.plate_detector_error === 'string' ? metadata.plate_detector_error : '';
  const readablePlateCount = results.plate_results.filter((plate) => Boolean(plate.normalized_ocr_text ?? plate.plate_text)).length;

  return (
    <section className="space-y-4" aria-labelledby="processing-results-heading">
      <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><p className="text-[10px] font-mono uppercase tracking-[0.18em] text-blue-600 font-bold">Analysis output</p><h3 id="processing-results-heading" className="mt-1 text-base font-bold text-[#0F172A]">Processing results</h3></div>
          <div className="flex flex-wrap gap-2">
            {modes.map((mode) => <span key={mode} className={`rounded-md border px-2.5 py-1 text-[10px] font-bold tracking-wider ${mode === 'REAL' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : mode === 'DEMO' ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-indigo-200 bg-indigo-50 text-indigo-800'}`}>{modeLabel(mode)}</span>)}
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <SummaryTile icon={<CarFront className="h-4 w-4" />} label="Vehicles" value={summary.vehicles} />
          <SummaryTile icon={<Activity className="h-4 w-4" />} label="Unique tracks" value={summary.uniqueTracks} />
          <SummaryTile icon={<ScanLine className="h-4 w-4" />} label="OCR reads" value={summary.plates} />
          <SummaryTile icon={<ScanLine className="h-4 w-4" />} label="Plate detections" value={results.plate_results.length} />
          <SummaryTile icon={<Target className="h-4 w-4" />} label="Avg confidence" value={summary.averageConfidence === null ? '—' : confidenceText(summary.averageConfidence)} />
          <SummaryTile icon={<CloudSun className="h-4 w-4" />} label="Condition" value={weather} />
        </div>
        {(operations.length > 0 || Boolean(metadata.plate_detector)) && <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] text-slate-500"><span className="font-semibold text-slate-700">Enhancement:</span>{operations.length ? operations.map((operation) => <span key={operation} className="rounded bg-slate-100 border border-slate-200 px-2 py-1 text-slate-700">{operation}</span>) : <span>None reported</span>}{Boolean(metadata.plate_detector) && <span className="rounded border border-indigo-200 bg-indigo-50 px-2 py-1 text-indigo-800 font-medium">Plate localization: {String(metadata.plate_detector)}</span>}</div>}
      </div>

      {String(metadata.plate_detector ?? '').toUpperCase().includes('HEURISTIC') && <p className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-xs text-indigo-800">HEURISTIC plate localization uses a geometric region inside each vehicle box; it is not a trained plate detector and does not provide plate confidence. Configure <code>PLATE_MODEL_PATH</code> with compatible Ultralytics plate weights to use a real plate detector.</p>}
      {plateDetectorError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 font-medium">{plateDetectorError}</p>}

      {results.detections.length === 0 && <div className="rounded-xl border border-[#E2E8F0] bg-white p-4 text-xs text-slate-500 shadow-sm">No vehicles were detected in the processed media.</div>}
      {results.plate_results.length === 0 && <div role="status" className="rounded-xl border border-[#E2E8F0] bg-white p-4 text-xs text-slate-500 shadow-sm">{plateDetectorError ? 'Plate detection did not run because its real model is unavailable; vehicle results are preserved above.' : ocrUnavailable ? 'OCR unavailable. No plate reads were produced.' : results.detections.length ? 'No license plates were detected inside the vehicle boxes.' : 'No plate results are available.'}</div>}
      {results.plate_results.length > 0 && readablePlateCount === 0 && <div role="status" className="rounded-xl border border-[#E2E8F0] bg-white p-4 text-xs text-slate-500 shadow-sm">{ocrUnavailable ? 'Plate detections were saved, but OCR is unavailable.' : 'Plate detections were saved, but OCR did not return readable text.'}</div>}

      {results.plate_results.length > 0 && <div className="grid gap-3 lg:grid-cols-2">{results.plate_results.map((plate) => <PlateResultCard key={plate.id} plate={plate} detection={detectionForPlate(plate)} metadata={metadata} selected={plate.id === selectedPlateId} onSelect={() => onPlateSelect(plate.id)} />)}</div>}

      {results.detections.length > 0 && (
        <div className="bg-white overflow-hidden rounded-xl border border-[#E2E8F0] shadow-sm">
          <div className="border-b border-[#E2E8F0] px-4 py-3"><h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">Detection details</h4></div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-left text-[11px]">
              <thead className="bg-[#F8FAFC] text-[9px] uppercase tracking-wider text-slate-500 border-b border-[#E2E8F0]"><tr><th className="px-3 py-2">Frame</th><th className="px-3 py-2">Time</th><th className="px-3 py-2">Track</th><th className="px-3 py-2">Vehicle</th><th className="px-3 py-2">Vehicle confidence</th><th className="px-3 py-2">Plate / OCR</th></tr></thead>
              <tbody className="divide-y divide-[#E2E8F0]">{results.detections.map((detection: MediaDetection) => {
                const plate = plateByDetection.get(detection.id);
                return <tr key={detection.id} className="text-slate-700 hover:bg-slate-50"><td className="px-3 py-2">{detection.frame_number ?? 'Image'}</td><td className="px-3 py-2 tabular-nums">{detection.timestamp === null ? '—' : `${detection.timestamp.toFixed(2)}s`}</td><td className="px-3 py-2 font-mono tabular-nums font-semibold">{detection.track_id ?? '—'}</td><td className="px-3 py-2 font-medium">{detection.object_type}</td><td className="px-3 py-2 tabular-nums">{confidenceText(detection.confidence)}</td><td className="px-3 py-2">{plate ? <button type="button" onClick={() => onPlateSelect(plate.id)} className="font-mono text-blue-600 hover:text-blue-800 font-semibold">{plate.normalized_ocr_text || plate.plate_text || 'Plate detected · no OCR read'} · {confidenceText(plate.ocr_confidence)}</button> : 'No plate detected'}</td></tr>;
              })}</tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
};

const SummaryTile: React.FC<{ icon: React.ReactNode; label: string; value: string | number }> = ({ icon, label, value }) => (
  <div className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-3 shadow-xs"><div className="flex items-center gap-1.5 text-blue-600">{icon}<span className="text-[9px] uppercase tracking-wider text-slate-500 font-medium">{label}</span></div><p className="mt-2 truncate text-sm font-bold text-[#0F172A] tabular-nums">{value}</p></div>
);
