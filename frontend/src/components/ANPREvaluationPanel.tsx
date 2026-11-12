import React, { useEffect, useState } from 'react';
import { ClipboardCheck, Plus, Save } from 'lucide-react';
import { api } from '../services/api';
import { ANPREvaluationReport, ANPREvaluationResult, ANPREvaluationSampleInput, MediaFile, MediaFrame } from '../types';
import { getApiErrorMessage } from '../utils/mediaProcessing';

type GroundTruthDraft = {
  id: number;
  registration_number: string;
  bbox: { x1: number; y1: number; x2: number; y2: number };
};
type SampleDraft = { frame_number: number; ground_truth_plates: GroundTruthDraft[] };

const percent = (value: number | null) => value === null ? 'N/A (no labeled denominator)' : `${(value * 100).toFixed(1)}%`;
const confidence = (value: unknown) => typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : 'Not available';

interface ANPREvaluationPanelProps {
  jobId: number;
  media: MediaFile;
  frames: MediaFrame[];
  selectedFrameNumber: number | null;
  onFrameSelect: (frameNumber: number) => void;
}

export const ANPREvaluationPanel: React.FC<ANPREvaluationPanelProps> = ({ jobId, media, frames, selectedFrameNumber, onFrameSelect }) => {
  const frameOptions = media.media_type === 'image' ? [1] : frames.map((frame) => frame.frame_number);
  const frameNumber = selectedFrameNumber ?? frameOptions[0] ?? 1;
  const [samples, setSamples] = useState<SampleDraft[]>([]);
  const [draft, setDraft] = useState({ registration_number: '', x1: '', y1: '', x2: '', y2: '' });
  const [iouThreshold, setIouThreshold] = useState('0.5');
  const [latest, setLatest] = useState<ANPREvaluationResult | null>(null);
  const [history, setHistory] = useState<ANPREvaluationResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setSamples([]);
    setLatest(null);
    void api.getANPREvaluations(jobId).then((items) => {
      if (active) {
        setHistory(items);
        setLatest(items[0] ?? null);
      }
    }).catch((loadError) => {
      if (active) setError(getApiErrorMessage(loadError));
    });
    return () => { active = false; };
  }, [jobId]);

  const markSampleReviewed = () => {
    setError(null);
    if (samples.some((sample) => sample.frame_number === frameNumber)) {
      setNotice(`Frame ${frameNumber} is already included in this evaluation.`);
      return;
    }
    setSamples((current) => [...current, { frame_number: frameNumber, ground_truth_plates: [] }].sort((a, b) => a.frame_number - b.frame_number));
    setNotice(`Frame ${frameNumber} marked reviewed with no ground-truth plates.`);
  };

  const removeSample = (sampleFrame: number) => {
    setSamples((current) => current.filter((sample) => sample.frame_number !== sampleFrame));
  };

  const removeGroundTruthPlate = (sampleFrame: number, plateId: number) => {
    setSamples((current) => current.map((sample) => sample.frame_number === sampleFrame
      ? { ...sample, ground_truth_plates: sample.ground_truth_plates.filter((plate) => plate.id !== plateId) }
      : sample));
  };

  const addGroundTruthPlate = () => {
    setError(null);
    setNotice(null);
    const coords = [draft.x1, draft.y1, draft.x2, draft.y2].map(Number);
    if (!draft.registration_number.trim() || coords.some((value, index) => !Number.isFinite(value) || value < 0 || (index > 1 && value <= 0)) || coords[2] <= coords[0] || coords[3] <= coords[1]) {
      setError('Enter a registration number and a positive pixel bounding box.');
      return;
    }
    if (media.width && coords[2] > media.width || media.height && coords[3] > media.height) {
      setError(`Box must fit within the source dimensions (${media.width} × ${media.height}).`);
      return;
    }
    const item: GroundTruthDraft = {
      id: Date.now() + Math.floor(Math.random() * 1000),
      registration_number: draft.registration_number.trim(),
      bbox: { x1: coords[0], y1: coords[1], x2: coords[2], y2: coords[3] },
    };
    setSamples((current) => {
      const existing = current.find((sample) => sample.frame_number === frameNumber);
      if (existing) return current.map((sample) => sample.frame_number === frameNumber
        ? { ...sample, ground_truth_plates: [...sample.ground_truth_plates, item] }
        : sample);
      return [...current, { frame_number: frameNumber, ground_truth_plates: [item] }].sort((a, b) => a.frame_number - b.frame_number);
    });
    setDraft((current) => ({ ...current, registration_number: '' }));
    setNotice(`Ground truth added to frame ${frameNumber}.`);
  };

  const submitEvaluation = async () => {
    if (!samples.length) {
      setError('Mark at least one processed frame as reviewed before evaluating.');
      return;
    }
    const parsedThreshold = Number(iouThreshold);
    if (!Number.isFinite(parsedThreshold) || parsedThreshold <= 0 || parsedThreshold > 1) {
      setError('IoU threshold must be greater than 0 and at most 1.');
      return;
    }
    const input: ANPREvaluationSampleInput[] = samples.map((sample) => ({
      frame_number: sample.frame_number,
      ground_truth_plates: sample.ground_truth_plates.map(({ registration_number, bbox }) => ({ registration_number, bbox })),
    }));
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.createANPREvaluation(jobId, input, parsedThreshold);
      setLatest(result);
      const items = await api.getANPREvaluations(jobId);
      setHistory(items);
      setNotice('Evaluation report saved. Metrics cover only the samples labeled above.');
    } catch (submitError) {
      setError(getApiErrorMessage(submitError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="glass-panel space-y-4 rounded-xl p-4" aria-labelledby="anpr-evaluation-heading">
      <div>
        <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-cyan-400">Phase 2 · Ground-truth evaluation</p>
        <h3 id="anpr-evaluation-heading" className="mt-1 flex items-center gap-2 text-base font-bold text-white"><ClipboardCheck className="h-4 w-4 text-cyan-400" /> ANPR accuracy evaluation</h3>
        <p className="mt-1 text-xs leading-relaxed text-slate-400">Manually label every plate in each reviewed sample, including plate pixel boxes. For video, labels apply to sampled frame numbers. Detection metrics use one-to-one IoU matching; unreviewed frames are excluded.</p>
        {media.width && media.height && <p className="mt-1 text-[10px] font-mono text-slate-500">Source coordinate space: {media.width} × {media.height} pixels. Use the original image/video frame shown above.</p>}
      </div>

      {frameOptions.length > 0 ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <label className="space-y-1 text-[10px] text-slate-400">Processed sample
          <select value={frameNumber} onChange={(event) => onFrameSelect(Number(event.target.value))} className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-white">
            {frameOptions.map((frame) => <option key={frame} value={frame}>{media.media_type === 'image' ? 'Image' : `Frame ${frame}`}{frames.find((item) => item.frame_number === frame) ? ` · ${frames.find((item) => item.frame_number === frame)?.timestamp.toFixed(2)}s` : ''}</option>)}
          </select>
        </label>
        <label className="space-y-1 text-[10px] text-slate-400">Ground-truth Indian registration number
          <input value={draft.registration_number} onChange={(event) => setDraft({ ...draft, registration_number: event.target.value })} placeholder="KA01AB1234" className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-xs font-mono text-white" />
        </label>
        <label className="space-y-1 text-[10px] text-slate-400">Plate box x1, y1, x2, y2 (pixels)
          <div className="grid grid-cols-4 gap-1">{(['x1', 'y1', 'x2', 'y2'] as const).map((key) => <input key={key} aria-label={key} type="number" min="0" value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} placeholder={key} className="min-w-0 rounded border border-slate-700 bg-slate-950 px-2 py-2 text-xs font-mono text-white" />)}</div>
        </label>
        <div className="flex flex-wrap items-end gap-2">
          <button type="button" onClick={addGroundTruthPlate} className="flex items-center gap-1 rounded bg-cyan-700 px-3 py-2 text-[11px] font-semibold text-white hover:bg-cyan-600"><Plus className="h-3.5 w-3.5" /> Add labeled plate</button>
          <button type="button" onClick={markSampleReviewed} className="rounded border border-slate-700 px-3 py-2 text-[11px] text-slate-300 hover:border-slate-500">Mark frame reviewed (zero plates)</button>
        </div>
        <label className="space-y-1 text-[10px] text-slate-400">Detection IoU match threshold
          <input type="number" min="0.01" max="1" step="0.05" value={iouThreshold} onChange={(event) => setIouThreshold(event.target.value)} className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-xs font-mono text-white" />
        </label>
        <div className="flex items-end"><button type="button" onClick={() => { void submitEvaluation(); }} disabled={busy || !samples.length} className="flex items-center gap-1 rounded bg-emerald-700 px-3 py-2 text-[11px] font-semibold text-white enabled:hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-50"><Save className="h-3.5 w-3.5" /> {busy ? 'Evaluating…' : 'Evaluate labeled samples'}</button></div>
      </div> : <p className="rounded border border-amber-900/60 bg-amber-950/20 p-3 text-xs text-amber-200">No processed sample frames are available for annotation.</p>}

      {error && <p role="alert" className="rounded border border-rose-900/60 bg-rose-950/30 p-3 text-xs text-rose-200">{error}</p>}
      {notice && <p role="status" className="rounded border border-emerald-900/60 bg-emerald-950/20 p-3 text-xs text-emerald-200">{notice}</p>}
      {samples.length > 0 && <div className="space-y-2 rounded border border-slate-800 bg-slate-950/50 p-3">
        <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-300">Samples to score</h4>
        {samples.map((sample) => <div key={sample.frame_number} className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400"><span>{media.media_type === 'image' ? 'Image' : `Frame ${sample.frame_number}`} · {sample.ground_truth_plates.length} ground-truth plates</span><div className="flex flex-wrap gap-2">{sample.ground_truth_plates.map((plate) => <span key={plate.id} className="flex items-center gap-1 rounded bg-slate-800 px-2 py-1 font-mono text-cyan-200">{plate.registration_number}<button type="button" onClick={() => removeGroundTruthPlate(sample.frame_number, plate.id)} aria-label={`Remove ${plate.registration_number} ground truth`} className="text-rose-300">×</button></span>)}<button type="button" onClick={() => removeSample(sample.frame_number)} className="text-rose-300 hover:text-rose-200">Remove sample</button></div></div>)}
      </div>}

      {history.length > 0 && <label className="block space-y-1 text-[10px] text-slate-400">Saved evaluation report
        <select value={latest?.id ?? history[0].id} onChange={(event) => setLatest(history.find((item) => item.id === Number(event.target.value)) ?? null)} className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-white">
          {history.map((item) => <option key={item.id} value={item.id}>Report #{item.id} · {new Date(item.created_at).toLocaleString()}</option>)}
        </select>
      </label>}
      {latest && <EvaluationReport report={latest.report} />}
    </section>
  );
};

const EvaluationReport: React.FC<{ report: ANPREvaluationReport }> = ({ report }) => {
  const summary = report.aggregate;
  const confidenceGroups = [
    ...Object.entries(report.confidence_analysis.plate_detection_confidence).map(([label, value]) => ({ name: `Plate detector · ${label.replace(/_/g, ' ')}`, ...value })),
    ...Object.entries(report.confidence_analysis.ocr_confidence).map(([label, value]) => ({ name: `OCR · ${label.replace(/_/g, ' ')}`, ...value })),
  ];
  return <div className="space-y-3 border-t border-slate-800 pt-4">
    <h4 className="text-xs font-bold uppercase tracking-wider text-white">Evaluation report</h4>
    <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
      <Metric label="Detection precision" value={percent(summary.precision)} />
      <Metric label="Detection recall" value={percent(summary.recall)} />
      <Metric label="Detection F1" value={percent(summary.f1_score)} />
      <Metric label="OCR exact match" value={percent(summary.ocr_exact_match_accuracy)} />
      <Metric label="Character error rate" value={percent(summary.character_error_rate)} />
      <Metric label="TP / FP / FN" value={`${summary.true_positives} / ${summary.false_positives} / ${summary.false_negatives}`} />
      <Metric label="Duplicates" value={summary.duplicate_detection_count} />
      <Metric label="Incorrect detections" value={summary.incorrect_detection_count} />
      <Metric label="OCR failures / errors" value={`${summary.ocr_failure_count} / ${summary.incorrect_ocr_count}`} />
      <Metric label="Labeled samples" value={summary.sample_count} />
    </div>
    <div className="rounded border border-slate-800 bg-slate-950/50 p-3">
      <h5 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">Independent confidence analysis</h5>
      <p className="mb-2 text-[10px] text-slate-500">Plate confidence scores localization; OCR confidence scores text recognition.</p>
      <div className="grid gap-1 md:grid-cols-2">{confidenceGroups.map((group) => <div key={group.name} className="flex justify-between gap-2 text-[10px] text-slate-300"><span>{group.name} ({group.count})</span><span className="font-mono">{confidence(group.mean)}</span></div>)}</div>
    </div>
    <div className="overflow-x-auto rounded border border-slate-800">
      <table className="w-full min-w-[700px] text-left text-[10px]">
        <thead className="bg-slate-950 text-slate-500"><tr><th className="p-2">Sample</th><th className="p-2">Detection TP / FP / FN</th><th className="p-2">OCR exact</th><th className="p-2">CER</th><th className="p-2">Ground truth & predictions</th></tr></thead>
        <tbody className="divide-y divide-slate-800">{report.samples.map((sample) => <tr key={sample.frame_number} className="align-top text-slate-300">
          <td className="p-2">Frame {sample.frame_number}</td>
          <td className="p-2">{sample.detection.true_positives} / {sample.detection.false_positives} / {sample.detection.false_negatives}<span className="block text-slate-500">P {percent(sample.detection.precision)} · R {percent(sample.detection.recall)}</span></td>
          <td className="p-2">{sample.ocr.exact_matches}/{sample.ocr.count}<span className="block text-slate-500">{percent(sample.ocr.exact_match_accuracy)}</span></td>
          <td className="p-2">{percent(sample.ocr.character_error_rate)}</td>
          <td className="space-y-2 p-2">{sample.ground_truth.map((item, index) => <div key={`gt-${index}`} className="rounded bg-slate-950 p-2 font-mono">
            <div>GT {String(item.registration_number)} → {String(item.normalized_registration_number)} ({String(item.validation_status)})</div>
            <div className="text-slate-400">OCR raw: {String(item.raw_ocr_text ?? (item.matched_prediction_id === null ? 'No detection' : 'Unreadable'))}</div>
            <div className="text-slate-400">GT validated: {String(item.validated_registration_number ?? 'Not available')} · OCR normalized: {String(item.normalized_ocr_text ?? 'Not available')} · OCR validated: {String(item.predicted_validated_registration_number ?? 'Not available')}</div>
            <div className="text-slate-400">Status: {String(item.ocr_status)} · edit distance {String(item.ocr_edit_distance)} · plate conf {confidence(item.plate_confidence)} · OCR conf {confidence(item.ocr_confidence)}</div>
          </div>)}{sample.predictions.map((item, index) => <div key={`pred-${index}`} className={`rounded p-2 font-mono ${item.match_status === 'true_positive' ? 'bg-emerald-950/30' : 'bg-rose-950/30'}`}>
            <div>Detection {String(item.prediction_id ?? index)} · {String(item.match_status)}{item.duplicate_of_prediction_id ? ` of ${String(item.duplicate_of_prediction_id)}` : ''}</div>
            <div className="text-slate-400">OCR raw: {String(item.raw_ocr_text ?? 'Unreadable')} · normalized: {String(item.normalized_ocr_text ?? 'Not available')}</div>
            <div className="text-slate-400">Validated registration: {String(item.validated_registration_number ?? 'Not available')} · OCR status: {String(item.ocr_status)}</div>
            <div className="text-slate-400">Plate confidence: {confidence(item.plate_confidence)} · OCR confidence: {confidence(item.ocr_confidence)}</div>
          </div>)}</td>
        </tr>)}</tbody>
      </table>
    </div>
    <details className="text-[10px] text-slate-500"><summary className="cursor-pointer">Evaluation methodology</summary><pre className="mt-2 whitespace-pre-wrap rounded bg-slate-950 p-3">{JSON.stringify(report.methodology, null, 2)}</pre></details>
  </div>;
};

const Metric: React.FC<{ label: string; value: number | string }> = ({ label, value }) => <div className="rounded border border-slate-800 bg-slate-950/60 p-2"><span className="block text-[9px] uppercase tracking-wider text-slate-500">{label}</span><span className="mt-1 block text-xs font-bold text-white">{value}</span></div>;
