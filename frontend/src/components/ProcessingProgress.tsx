import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, LoaderCircle, UploadCloud } from 'lucide-react';
import { ProcessingJob } from '../types';
import { friendlyProcessingStage, getProcessingErrorMessage } from '../utils/mediaProcessing';

interface ProcessingProgressProps {
  job: ProcessingJob | null;
  uploading: boolean;
  uploadProgress: number;
  error: string | null;
  onRetry: () => void;
}

const WORKFLOW_STAGES = [
  'Uploading', 'Loading media', 'Analyzing quality', 'Enhancing', 'Detecting vehicles',
  'Tracking', 'Detecting plates', 'Enhancing plates', 'Running OCR', 'Saving results', 'Completed',
];

export const ProcessingProgress: React.FC<ProcessingProgressProps> = ({ job, uploading, uploadProgress, error, onRetry }) => {
  const [, setClock] = useState(0);
  useEffect(() => {
    if (!uploading && job?.status !== 'queued' && job?.status !== 'processing') return;
    const timer = window.setInterval(() => setClock((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [uploading, job?.status]);

  const status = uploading ? 'uploading' : job?.status;
  if (!status && !error) return null;
  const percent = uploading ? uploadProgress : job?.progress ?? 0;
  const stage = uploading ? 'Uploading' : friendlyProcessingStage(job?.current_stage);
  const activeIndex = WORKFLOW_STAGES.findIndex((item) => stage.toLowerCase().includes(item.toLowerCase()));
  const elapsed = job?.started_at
    ? Math.max(0, Math.floor(((job.completed_at ? new Date(job.completed_at).getTime() : Date.now()) - new Date(job.started_at).getTime()) / 1000))
    : null;
  const rawError = error ?? job?.error_message ?? null;
  const errorMessage = getProcessingErrorMessage(rawError);
  const unavailable = (rawError ?? '').toLowerCase().includes('unavailable');

  return (
    <section aria-live="polite" aria-labelledby="processing-status-heading" className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {status === 'completed' ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : status === 'failed' || error ? <AlertTriangle className="h-5 w-5 text-rose-600" /> : uploading ? <UploadCloud className="h-5 w-5 text-blue-600" /> : <LoaderCircle className="h-5 w-5 animate-spin text-blue-600" />}
          <div>
            <h3 id="processing-status-heading" className="text-sm font-bold text-[#0F172A]">{unavailable ? 'REAL AI MODEL UNAVAILABLE' : 'Processing status'}</h3>
            <p className="mt-0.5 text-xs text-slate-500">{status ? `${status.toUpperCase()} · ${stage}` : errorMessage ?? 'Processing service is unavailable'}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs font-mono text-slate-500">
          {elapsed !== null && <span className="tabular-nums">Elapsed {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')}</span>}
          <span className="font-bold text-blue-600 tabular-nums">{Math.round(percent)}%</span>
        </div>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100 border border-slate-200" role="progressbar" aria-valuenow={Math.round(percent)} aria-valuemin={0} aria-valuemax={100} aria-label="Media processing progress">
        <div className={`h-full transition-all duration-500 ${status === 'failed' || error ? 'bg-rose-500' : status === 'completed' ? 'bg-emerald-500' : 'bg-blue-600'}`} style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
      </div>
      <div className="mt-3 hidden grid-cols-2 gap-x-2 gap-y-1 sm:grid sm:grid-cols-4 lg:grid-cols-6">
        {WORKFLOW_STAGES.map((item, index) => {
          const complete = status === 'completed' || (activeIndex >= 0 && index < activeIndex);
          const active = status !== 'failed' && index === activeIndex;
          return <span key={item} className={`text-[9px] font-mono ${complete ? 'text-emerald-700 font-semibold' : active ? 'text-blue-600 font-bold' : 'text-slate-400'}`}>{complete ? '✓ ' : active ? '› ' : '· '}{item}</span>;
        })}
      </div>
      {errorMessage && (
        <div role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
          <p className="whitespace-pre-line font-medium">{errorMessage}</p>
          {unavailable && <p className="mt-1 text-rose-600">Install the listed real inference dependencies and configure the YOLO weights path, then retry.</p>}
          <button type="button" onClick={onRetry} className="mt-2 rounded-md border border-rose-300 bg-white px-3 py-1.5 font-semibold text-rose-700 hover:bg-rose-100 shadow-sm">Retry processing</button>
        </div>
      )}
    </section>
  );
};
