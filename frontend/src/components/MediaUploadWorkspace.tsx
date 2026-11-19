import React, { KeyboardEvent, useRef, useState } from 'react';
import { FileVideo2, ImagePlus, RotateCcw, UploadCloud, X } from 'lucide-react';
import { validateMediaFile } from '../utils/mediaProcessing';

interface MediaUploadWorkspaceProps {
  selectedFile: File | null;
  busy: boolean;
  uploadProgress: number;
  onSelect: (file: File | null) => void;
  onStart: () => void;
  onReset: () => void;
}

export const MediaUploadWorkspace: React.FC<MediaUploadWorkspaceProps> = ({
  selectedFile, busy, uploadProgress, onSelect, onStart, onReset,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const acceptFile = (file?: File) => {
    if (!file) return;
    const issue = validateMediaFile(file);
    setValidationError(issue);
    if (issue) onSelect(null);
    else onSelect(file);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      inputRef.current?.click();
    }
  };

  return (
    <section aria-labelledby="media-upload-heading" className="bg-white rounded-2xl border border-slate-200/90 p-5 lg:p-6 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#00A8C6] font-bold">AI Processing Workspace</p>
          <h2 id="media-upload-heading" className="mt-1 text-lg font-bold text-[#0F172A]">Analyze an image or video</h2>
          <p className="mt-1 max-w-2xl text-xs text-slate-500 font-medium">Choose media, then start processing when you are ready. Your existing live traffic feed continues independently.</p>
        </div>
        {(selectedFile || busy) && (
          <button type="button" onClick={() => { setValidationError(null); onReset(); }} disabled={busy} className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs text-slate-700 hover:bg-slate-50 hover:text-slate-900 shadow-sm disabled:opacity-50 font-semibold transition">
            <RotateCcw className="h-3.5 w-3.5" /> Reset
          </button>
        )}
      </div>

      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        accept=".jpg,.jpeg,.png,.webp,.mp4,.avi,.mov,.mkv,image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/x-msvideo,video/x-matroska"
        aria-label="Choose an image or video to process"
        onChange={(event) => { acceptFile(event.currentTarget.files?.[0]); event.currentTarget.value = ''; }}
        disabled={busy}
      />

      {!selectedFile ? (
        <div
          role="button"
          tabIndex={0}
          aria-label="Choose media file or drop it here"
          onKeyDown={onKeyDown}
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFile(event.dataTransfer.files[0]); }}
          className={`cursor-pointer rounded-2xl border border-dashed p-8 text-center transition ${dragging ? 'border-[#00A8C6] bg-teal-50/50' : 'border-slate-300 bg-[#F8FAFC] hover:border-[#00A8C6] hover:bg-teal-50/20'}`}
        >
          <UploadCloud className="mx-auto h-9 w-9 text-[#00A8C6]" aria-hidden="true" />
          <p className="mt-3 text-sm font-bold text-[#0F172A]">Drop media here or browse files</p>
          <p className="mt-1 text-xs text-slate-500 font-medium">Images up to 20 MB · Videos up to 100 MB</p>
          <p className="mt-3 text-[10px] font-mono text-slate-400">JPG · JPEG · PNG · WEBP · MP4 · AVI · MOV · MKV</p>
        </div>
      ) : (
        <div className="flex flex-col gap-4 rounded-2xl border border-slate-200/90 bg-[#F8FAFC] p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="rounded-xl bg-teal-50 border border-teal-200 p-3 text-[#00A8C6]">
              {/\.(mp4|avi|mov|mkv)$/i.test(selectedFile.name) ? <FileVideo2 aria-hidden="true" /> : <ImagePlus aria-hidden="true" />}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-[#0F172A]">{selectedFile.name}</p>
              <p className="mt-1 text-xs font-mono text-slate-500">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · {/\.(mp4|avi|mov|mkv)$/i.test(selectedFile.name) ? 'VIDEO' : 'IMAGE'}</p>
            </div>
            {!busy && <button type="button" aria-label="Remove selected file" onClick={() => { onSelect(null); setValidationError(null); }} className="ml-1 rounded-lg p-2 text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition"><X className="h-4 w-4" /></button>}
          </div>
          <button type="button" onClick={onStart} disabled={busy || Boolean(validationError)} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-[#00A8C6] hover:bg-[#0090AA] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition disabled:cursor-not-allowed disabled:opacity-50">
            <UploadCloud className="h-4 w-4" />
            {busy ? `Uploading ${uploadProgress}%` : 'Upload and process'}
          </button>
        </div>
      )}

      {validationError && <p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 font-medium">VALIDATION ERROR — {validationError}</p>}
      {busy && <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-200" aria-label={`Upload progress ${uploadProgress}%`}><div className="h-full bg-blue-600 transition-all" style={{ width: `${uploadProgress}%` }} /></div>}
    </section>
  );
};
