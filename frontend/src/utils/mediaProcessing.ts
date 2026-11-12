import type { ProcessingMode, ProcessingResults } from '../types';

const IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp']);
const VIDEO_EXTENSIONS = new Set(['mp4', 'avi', 'mov', 'mkv']);
const IMAGE_LIMIT_BYTES = 20 * 1024 * 1024;
const VIDEO_LIMIT_BYTES = 100 * 1024 * 1024;

export function validateMediaFile(file: File): string | null {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
  const isImage = IMAGE_EXTENSIONS.has(extension);
  const isVideo = VIDEO_EXTENSIONS.has(extension);
  if (!isImage && !isVideo) return 'Choose a JPG, JPEG, PNG, WEBP, MP4, AVI, MOV, or MKV file.';
  if (isImage && file.size > IMAGE_LIMIT_BYTES) return 'Images must be 20 MB or smaller.';
  if (isVideo && file.size > VIDEO_LIMIT_BYTES) return 'Videos must be 100 MB or smaller.';
  if (file.size === 0) return 'The selected file is empty.';
  return null;
}

export function mediaTypeForFile(file: File): 'image' | 'video' {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
  return VIDEO_EXTENSIONS.has(extension) ? 'video' : 'image';
}

export function classifyProcessingModes(metadata: Record<string, unknown>): ProcessingMode[] {
  const mode = String(metadata.mode ?? '').toUpperCase();
  const vehicleProvider = String(metadata.vehicle_provider ?? metadata.vehicle_detector ?? '').toUpperCase();
  const ocrProvider = String(metadata.ocr_provider ?? metadata.ocr_engine ?? '').toUpperCase();
  const plateProvider = String(metadata.plate_localization_mode ?? metadata.plate_detector ?? '').toUpperCase();
  const result: ProcessingMode[] = [];
  if (mode.includes('DEMO') || mode.includes('SYNTHETIC') || vehicleProvider.includes('DEMO') || ocrProvider.includes('DEMO')) {
    result.push('DEMO');
  } else if (vehicleProvider.includes('YOLO') && ocrProvider.includes('PADDLEOCR')) {
    result.push('REAL');
  }
  if (plateProvider.includes('HEURISTIC') || plateProvider.includes('GEOMETRIC')) result.push('HEURISTIC');
  return result;
}

export function modeLabel(mode: ProcessingMode): string {
  if (mode === 'REAL') return 'REAL AI';
  if (mode === 'DEMO') return 'DEMO MODE';
  return 'HEURISTIC';
}

export function artifactUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  const filename = path.split(/[\\/]/).filter(Boolean).pop();
  return filename ? `/api/media/artifacts/${encodeURIComponent(filename)}` : null;
}

export function getApiErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const axiosError = error as { code?: string; response?: { status?: number; data?: { detail?: unknown } } };
    const response = axiosError.response;
    const detail = response?.data?.detail;
    if (!response) {
      return 'NETWORK ERROR — Backend unavailable through the Vite /api proxy (default target: http://127.0.0.1:8000). Start FastAPI or check VITE_API_PROXY_TARGET and retry.';
    }
    if (typeof detail === 'string') {
      if (/real .*unavailable|model unavailable|ocr unavailable|tracker unavailable/i.test(detail)) return `MODEL ERROR — ${detail}`;
      if ([400, 413, 415, 422].includes(response.status ?? 0)) return `VALIDATION ERROR — ${detail}`;
      return `BACKEND ERROR — ${detail}`;
    }
    return `BACKEND ERROR — Request failed with HTTP ${response.status ?? 'unknown'}.`;
  }
  if (error instanceof Error) return error.message;
  return 'NETWORK ERROR — Backend unavailable through the Vite /api proxy (default target: http://127.0.0.1:8000). Start FastAPI or check VITE_API_PROXY_TARGET and retry.';
}

export function getProcessingErrorMessage(message: string | null | undefined): string | null {
  if (!message) return null;
  if (/^(network|backend|model|validation|processing|database) error/i.test(message)) return message;
  if (/real .*unavailable|model unavailable|ocr unavailable|tracker unavailable/i.test(message)) return `MODEL ERROR — ${message}`;
  if (/database|sqlalchemy|integrityerror|operationalerror/i.test(message)) return `DATABASE ERROR — ${message}`;
  return `PROCESSING ERROR — ${message}`;
}

export function friendlyProcessingStage(stage: string | null | undefined): string {
  if (!stage) return 'Waiting for worker';
  const lower = stage.toLowerCase();
  if (lower.includes('queue')) return 'Queued';
  if (lower.includes('initial')) return 'Loading media';
  if (lower.includes('fail')) return 'Processing failed';
  if (lower.includes('complet')) return 'Completed';
  if (lower.includes('processed frame')) return 'Saving results';
  if (lower.includes('ocr')) return 'Running OCR';
  if (lower.includes('plate')) return 'Detecting plates';
  if (lower.includes('track')) return 'Tracking';
  if (lower.includes('enhanc')) return 'Enhancing';
  if (lower.includes('detect')) return 'Detecting vehicles';
  if (lower.includes('frame')) return stage;
  return stage;
}

export function processingSummary(results: ProcessingResults) {
  const scores = [
    ...results.detections.map((detection) => detection.confidence),
    ...results.plate_results.map((plate) => plate.ocr_confidence).filter((score): score is number => score !== null),
  ];
  const tracks = new Set(results.detections.map((detection) => detection.track_id).filter((id): id is string => Boolean(id)));
  return {
    vehicles: results.detections.length,
    uniqueTracks: tracks.size,
    plates: results.plate_results.filter((plate) => Boolean(plate.normalized_ocr_text ?? plate.plate_text)).length,
    averageConfidence: scores.length ? scores.reduce((sum, score) => sum + score, 0) / scores.length : null,
    frames: results.frames.length,
  };
}
