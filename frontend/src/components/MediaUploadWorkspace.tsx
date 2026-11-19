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
    <section aria-labelledby="media-upload-heading" className="glass-panel rounded-xl border border-[#222634] p-5 lg:p-6 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-blue-500">AI Processing Workspace</p>
          <h2 id="media-upload-heading" className="mt-1 text-lg font-bold text-white">Analyze an image or video</h2>
          <p className="mt-1 max-w-2xl text-xs text-slate-400">Choose media, then start processing when you are ready. Your existing live traffic feed continues independently.</p>
        </div>
        {(selectedFile || busy) && (
          <button type="button" onClick={() => { setValidationError(null); onReset(); }} disabled={busy} className="inline-flex items-center gap-1.5 rounded-lg border border-[#2B3040] bg-[#171A24] px-3 py-2 text-xs text-slate-300 hover:text-white disabled:opacity-50">
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
          className={`cursor-pointer rounded-xl border border-dashed p-7 text-center transition ${dragging ? 'border-blue-500 bg-blue-950/20' : 'border-[#2B3040] bg-[#171A24]/60 hover:border-blue-500/60 hover:bg-[#171A24]'}`}
        >
          <UploadCloud className="mx-auto h-8 w-8 text-blue-500" aria-hidden="true" />
          <p className="mt-3 text-sm font-semibold text-white">Drop media here or browse files</p>
          <p className="mt-1 text-xs text-slate-400">Images up to 20 MB · Videos up to 100 MB</p>
          <p className="mt-3 text-[10px] font-mono text-slate-500">JPG · JPEG · PNG · WEBP · MP4 · AVI · MOV · MKV</p>
        </div>
      ) : (
        <div className="flex flex-col gap-4 rounded-xl border border-[#222634] bg-[#11131A] p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="rounded-lg bg-[#171A24] border border-[#2B3040] p-3 text-blue-400">
              {/\.(mp4|avi|mov|mkv)$/i.test(selectedFile.name) ? <FileVideo2 aria-hidden="true" /> : <ImagePlus aria-hidden="true" />}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{selectedFile.name}</p>
              <p className="mt-1 text-xs font-mono text-slate-400">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · {/\.(mp4|avi|mov|mkv)$/i.test(selectedFile.name) ? 'VIDEO' : 'IMAGE'}</p>
            </div>
            {!busy && <button type="button" aria-label="Remove selected file" onClick={() => { onSelect(null); setValidationError(null); }} className="ml-1 rounded p-2 text-slate-400 hover:bg-[#171A24] hover:text-white"><X className="h-4 w-4" /></button>}
          </div>
          <button type="button" onClick={onStart} disabled={busy || Boolean(validationError)} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition disabled:cursor-not-allowed disabled:opacity-50">
            <UploadCloud className="h-4 w-4" />
            {busy ? `Uploading ${uploadProgress}%` : 'Upload and process'}
          </button>
        </div>
      )}

      {validationError && <p role="alert" className="mt-3 rounded-lg border border-rose-900/60 bg-rose-950/30 px-3 py-2 text-xs text-rose-300">VALIDATION ERROR — {validationError}</p>}
      {busy && <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#171A24]" aria-label={`Upload progress ${uploadProgress}%`}><div className="h-full bg-blue-500 transition-all" style={{ width: `${uploadProgress}%` }} /></div>}
    </section>
  );
};
