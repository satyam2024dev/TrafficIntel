import React from 'react';
import { Clock3, FileVideo2, ImageIcon, RefreshCw } from 'lucide-react';
import { ProcessingHistoryItem } from '../types';
import { classifyProcessingModes, modeLabel } from '../utils/mediaProcessing';

interface ProcessingHistoryProps {
  items: ProcessingHistoryItem[];
  loading: boolean;
  error: string | null;
  selectedJobId: number | null;
  onSelect: (item: ProcessingHistoryItem) => void;
  onRefresh: () => void;
}

export const ProcessingHistory: React.FC<ProcessingHistoryProps> = ({ items, loading, error, selectedJobId, onSelect, onRefresh }) => (
  <section aria-labelledby="processing-history-heading" className="glass-panel rounded-xl border border-[#222634] p-4 shadow-sm">
    <div className="mb-3 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2"><Clock3 className="h-4 w-4 text-blue-500" /><h3 id="processing-history-heading" className="text-sm font-bold text-white">Recent AI processing</h3></div>
      <button type="button" onClick={onRefresh} disabled={loading} className="rounded-md p-2 text-slate-400 hover:bg-[#171A24] hover:text-white disabled:opacity-50" aria-label="Refresh processing history"><RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /></button>
    </div>
    {error && <p role="status" className="mb-3 rounded-lg border border-amber-900/50 bg-amber-950/20 p-2 text-[11px] text-amber-200">History could not be loaded: {error}</p>}
    {loading && items.length === 0 ? <div className="space-y-2" aria-label="Loading history">{[0, 1, 2].map((item) => <div key={item} className="h-16 animate-pulse rounded-lg bg-[#171A24]" />)}</div> : items.length === 0 ? <p className="py-7 text-center text-xs text-slate-500">No media processing jobs yet.</p> : (
      <div className="space-y-2">
        {items.map((item) => {
          const job = item.job;
          const metadata = job?.processing_metadata ?? {};
          const modes = classifyProcessingModes(metadata);
          const status = job?.status ?? 'uploaded';
          const active = job?.id === selectedJobId;
          return <button key={item.media.id} type="button" onClick={() => onSelect(item)} aria-current={active ? 'true' : undefined} className={`w-full rounded-lg border p-3 text-left transition ${active ? 'border-blue-600 bg-blue-600/10' : 'border-[#222634] bg-[#11131A] hover:border-[#2B3040]'}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-2.5">
                {item.media.media_type === 'video' ? <FileVideo2 className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" /> : <ImageIcon className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />}
                <div className="min-w-0"><p className="truncate text-xs font-semibold text-slate-100">{item.media.original_filename}</p><p className="mt-1 text-[9px] font-mono uppercase text-slate-500">{item.media.media_type} · {new Date(item.media.created_at).toLocaleString()}</p></div>
              </div>
              <span className={`shrink-0 rounded border px-2 py-1 text-[9px] font-bold ${status === 'completed' ? 'border-emerald-900 text-emerald-300' : status === 'failed' ? 'border-rose-900 text-rose-300' : status === 'processing' ? 'border-blue-900 text-blue-400' : 'border-[#2B3040] text-slate-400'}`}>{status.toUpperCase()} {job && (status === 'processing' || status === 'queued') ? `${Math.round(job.progress)}%` : ''}</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[9px] text-slate-400"><span>{item.vehicle_count} vehicles</span><span>{item.plate_count} plates</span>{modes.length ? modes.map((mode) => <span key={mode} className="text-blue-400">{modeLabel(mode)}</span>) : <span>{status === 'failed' ? 'Model unavailable' : 'Awaiting analysis'}</span>}{job?.current_stage && (status === 'processing' || status === 'queued') && <span className="truncate">{job.current_stage}</span>}</div>
          </button>;
        })}
      </div>
    )}
  </section>
);
