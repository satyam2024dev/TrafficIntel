import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Film, ImageIcon } from 'lucide-react';
import { MediaDetection, MediaFile, MediaFrame, MediaPlateResult, VehicleTrackTrail } from '../types';
import { api } from '../services/api';
import { DetectionOverlay } from './DetectionOverlay';

interface MediaPreviewProps {
  media: MediaFile;
  selectedFile: File | null;
  frames: MediaFrame[];
  detections: MediaDetection[];
  plates: MediaPlateResult[];
  selectedPlateId: number | null;
  onPlateSelect: (id: number) => void;
  selectedFrameNumber?: number | null;
  onFrameSelect?: (frameNumber: number) => void;
  trajectories?: VehicleTrackTrail[];
  selectedTrackId?: string | null;
}

export const MediaPreview: React.FC<MediaPreviewProps> = ({ media, selectedFile, frames, detections, plates, selectedPlateId, onPlateSelect, selectedFrameNumber, onFrameSelect, trajectories = [], selectedTrackId }) => {
  const localUrl = useMemo(() => selectedFile ? URL.createObjectURL(selectedFile) : null, [selectedFile]);
  const [originalFallback, setOriginalFallback] = useState(false);
  const [originalUnavailable, setOriginalUnavailable] = useState(false);
  const [unavailableArtifacts, setUnavailableArtifacts] = useState<Set<string>>(() => new Set());
  useEffect(() => () => { if (localUrl) URL.revokeObjectURL(localUrl); }, [localUrl]);
  const videoRef = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    setOriginalFallback(false);
    setOriginalUnavailable(false);
    setUnavailableArtifacts(new Set());
  }, [media.id, media.stored_filename, localUrl]);

  const originalApiUrl = media.original_url ?? (media.id ? api.getMediaOriginalUrl(media.id) : null);
  const sourceUrl = originalFallback ? localUrl : media.id ? originalApiUrl : localUrl ?? originalApiUrl;
  const currentFrame = frames.find((frame) => frame.frame_number === selectedFrameNumber) ?? frames[0];
  useEffect(() => {
    if (videoRef.current && videoRef.current.readyState >= 1 && currentFrame && Number.isFinite(currentFrame.timestamp)) {
      videoRef.current.currentTime = currentFrame.timestamp;
    }
  }, [currentFrame?.frame_number, currentFrame?.timestamp]);
  const currentDetections = media.media_type === 'image'
    ? detections
    : detections.filter((detection) => detection.frame_number === currentFrame?.frame_number);
  const currentPlates = media.media_type === 'image'
    ? plates
    : plates.filter((plate) => plate.frame_number === currentFrame?.frame_number);

  const stillPane = (title: string, src: string | null, overlayDetections: MediaDetection[], overlayPlates: MediaPlateResult[], accent: boolean, overlayTrajectories: VehicleTrackTrail[] = []) => {
    const unavailable = Boolean(src && unavailableArtifacts.has(src));
    const missingMessage = title.includes('ENHANCED') ? 'Enhanced image is unavailable because no enhanced artifact was saved.' : 'Original image could not be loaded from the uploaded file.';
    return (
    <div className={`overflow-hidden rounded-xl border ${accent ? 'border-blue-400' : 'border-[#E2E8F0]'} bg-[#0F172A] shadow-sm`}>
      <div className="flex items-center justify-between border-b border-slate-800 bg-[#0F172A] px-3 py-2">
        <span className={`text-[10px] font-bold tracking-[0.16em] ${accent ? 'text-blue-400' : 'text-slate-200'}`}>{title}</span>
        {accent && <span className="rounded bg-blue-950/70 border border-blue-600/40 px-2 py-0.5 text-[9px] font-mono text-blue-300 font-semibold">AI ENHANCED</span>}
      </div>
      {src && !unavailable ? (
        <div className={`relative mx-auto w-full ${media.width && media.height ? '' : 'flex max-h-96 min-h-48 items-center justify-center'}`} style={media.width && media.height ? { aspectRatio: `${media.width} / ${media.height}` } : undefined}>
          <img src={src} alt={`${title} media preview`} onError={() => {
            if (title === 'ORIGINAL' && !originalFallback && localUrl && src !== localUrl) {
              setOriginalFallback(true);
              return;
            }
            if (title === 'ORIGINAL') setOriginalUnavailable(true);
            setUnavailableArtifacts((current) => new Set(current).add(src));
          }} className={media.width && media.height ? 'absolute inset-0 h-full w-full object-fill' : 'max-h-96 w-full object-contain'} />
          <DetectionOverlay width={media.width ?? 0} height={media.height ?? 0} detections={overlayDetections} plates={overlayPlates} selectedPlateId={selectedPlateId} trajectories={overlayTrajectories} selectedTrackId={selectedTrackId} />
          {overlayPlates.map((plate) => <button key={plate.id} type="button" aria-label={`Inspect OCR result ${plate.plate_text}`} onClick={() => onPlateSelect(plate.id)} className="pointer-events-auto absolute z-10 rounded-sm border-2 border-transparent focus:border-amber-300 focus:outline-none" style={{ left: `${(plate.x1 / (media.width || 1)) * 100}%`, top: `${(plate.y1 / (media.height || 1)) * 100}%`, width: `${((plate.x2 - plate.x1) / (media.width || 1)) * 100}%`, height: `${((plate.y2 - plate.y1) / (media.height || 1)) * 100}%` }} />)}
        </div>
      ) : <div role="status" className="flex aspect-video items-center justify-center px-5 text-center text-xs text-slate-400">{unavailable ? missingMessage : title.includes('ENHANCED') ? 'Enhanced image is unavailable because no enhanced artifact was saved.' : originalUnavailable ? 'Original image could not be loaded from the uploaded file.' : 'Preview is unavailable.'}</div>}
      <div className="border-t border-slate-800 bg-[#0F172A] px-3 py-2 text-[10px] text-slate-400 font-mono">{overlayDetections.length} vehicles · {overlayPlates.length} plate reads</div>
    </div>
    );
  };

  return (
    <section aria-labelledby="media-preview-heading" className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          {media.media_type === 'video' ? <Film className="h-4 w-4 text-blue-600" /> : <ImageIcon className="h-4 w-4 text-blue-600" />}
          <h3 id="media-preview-heading" className="truncate text-sm font-bold text-[#0F172A]">{media.original_filename}</h3>
        </div>
        <div className="text-[10px] font-mono text-slate-500 font-medium">{media.width ?? '—'} × {media.height ?? '—'}{media.duration !== null && ` · ${media.duration.toFixed(1)}s`}{media.frame_count !== null && ` · ${media.frame_count} frames`}</div>
      </div>

      {media.media_type === 'image' ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {stillPane('ORIGINAL', sourceUrl, detections, plates, false)}
          {stillPane('AI ENHANCED', frames[0]?.enhanced_frame_url ?? null, detections, plates, true)}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="overflow-hidden rounded-xl border border-[#E2E8F0] bg-black shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-800 bg-[#0F172A] px-3 py-2"><span className="text-[10px] font-bold tracking-[0.16em] text-slate-200">ORIGINAL VIDEO</span><span className="text-[9px] font-mono text-slate-400">{frames.length} sampled frames processed</span></div>
            {sourceUrl ? <video ref={videoRef} src={sourceUrl} controls preload="metadata" onLoadedMetadata={() => { if (currentFrame && videoRef.current) videoRef.current.currentTime = currentFrame.timestamp; }} className="max-h-[440px] w-full bg-black" aria-label={`Original video ${media.original_filename}`} /> : <div className="p-10 text-center text-xs text-slate-400">Video preview unavailable.</div>}
          </div>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-3 shadow-xs">
              <p className="mb-2 text-[10px] font-bold tracking-wider text-slate-600">PROCESSED FRAME TIMELINE</p>
              {frames.length ? <div className="flex flex-wrap gap-2">{frames.map((frame) => <button key={frame.id} type="button" onClick={() => onFrameSelect?.(frame.frame_number)} aria-pressed={frame.frame_number === currentFrame?.frame_number} className={`rounded-lg border px-3 py-2 text-left text-[10px] font-mono tabular-nums transition ${frame.frame_number === currentFrame?.frame_number ? 'border-blue-600 bg-blue-50 text-blue-700 font-bold shadow-xs' : 'border-slate-300 bg-white text-slate-600 hover:border-blue-400 hover:text-blue-600'}`}>Frame {frame.frame_number}<span className="block text-[9px] opacity-75">{frame.timestamp.toFixed(2)}s</span></button>)}</div> : <p className="py-5 text-center text-xs text-slate-500">No processed frames yet.</p>}
              <p className="mt-3 text-[10px] text-slate-500">Choose a sampled frame to inspect its detections and enhancement.</p>
            </div>
            {stillPane('AI ENHANCED FRAME', currentFrame?.enhanced_frame_url ?? null, currentDetections, currentPlates, true, trajectories)}
          </div>
        </div>
      )}
    </section>
  );
};
