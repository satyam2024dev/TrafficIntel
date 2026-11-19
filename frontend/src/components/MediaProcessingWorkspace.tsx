import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../services/api';
import { Camera, MediaFile, ProcessingHistoryItem, ProcessingJob, ProcessingResults, VehicleTrackSummaryResponse, VehicleTrackTrail } from '../types';
import { getApiErrorMessage, mediaTypeForFile } from '../utils/mediaProcessing';
import { MediaPreview } from './MediaPreview';
import { MediaUploadWorkspace } from './MediaUploadWorkspace';
import { ProcessingHistory } from './ProcessingHistory';
import { ProcessingProgress } from './ProcessingProgress';
import { ProcessingResults as ProcessingResultsPanel } from './ProcessingResults';
import { ANPREvaluationPanel } from './ANPREvaluationPanel';
import { VehicleTrackingPanel } from './VehicleTrackingPanel';

export const MediaProcessingWorkspace: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [media, setMedia] = useState<MediaFile | null>(null);
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [results, setResults] = useState<ProcessingResults | null>(null);
  const [history, setHistory] = useState<ProcessingHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedPlateId, setSelectedPlateId] = useState<number | null>(null);
  const [selectedFrameNumber, setSelectedFrameNumber] = useState<number | null>(null);
  const [vehicleTracks, setVehicleTracks] = useState<VehicleTrackSummaryResponse | null>(null);
  const [trackTrajectories, setTrackTrajectories] = useState<VehicleTrackTrail[]>([]);
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(null);
  const [trackingError, setTrackingError] = useState<string | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [cameraLoadError, setCameraLoadError] = useState<string | null>(null);
  const [routeCameraId, setRouteCameraId] = useState('');
  const [selectionVersion, setSelectionVersion] = useState(0);
  const previewMedia: MediaFile | null = media ?? (selectedFile ? {
    original_filename: selectedFile.name,
    stored_filename: '',
    media_type: mediaTypeForFile(selectedFile),
    file_size: selectedFile.size,
    mime_type: selectedFile.type || 'application/octet-stream',
    width: null,
    height: null,
    duration: null,
    frame_count: null,
    created_at: new Date().toISOString(),
  } : null);

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      setHistory(await api.getProcessingHistory());
      setHistoryError(null);
    } catch (error) {
      setHistoryError(getApiErrorMessage(error));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => { void refreshHistory(); }, [refreshHistory]);

  useEffect(() => {
    let active = true;
    void api.getCameras().then((items) => { if (active) { setCameras(items); setCameraLoadError(null); } }).catch((error) => { if (active) setCameraLoadError(getApiErrorMessage(error)); });
    return () => { active = false; };
  }, []);

  const startProcessing = useCallback(async () => {
    setPreparing(true);
    setWorkspaceError(null);
    setResults(null);
    setSelectedPlateId(null);
    setUploadProgress(0);
    try {
      await api.getHealth();
      let mediaId = media?.id ?? media?.media_id;
      if (mediaId === undefined) {
        if (!selectedFile) throw new Error('Select an image or video first.');
        const uploaded = await api.uploadMedia(selectedFile, setUploadProgress);
        mediaId = uploaded.media_id;
        setMedia(uploaded);
      }
      const isVideo = (media?.media_type ?? (selectedFile ? mediaTypeForFile(selectedFile) : null)) === 'video';
      const created = await api.startMediaProcessing(mediaId, isVideo ? routeCameraId || null : null);
      const currentJob = await api.getProcessingJob(created.job_id);
      setJob(currentJob);
      setSelectionVersion((version) => version + 1);
    } catch (error) {
      setWorkspaceError(getApiErrorMessage(error));
    } finally {
      setPreparing(false);
    }
  }, [media, selectedFile, routeCameraId]);

  useEffect(() => {
    const jobId = job?.id;
    if (jobId === undefined || job?.status === 'completed' || job?.status === 'failed') return;
    let active = true;
    const poll = async () => {
      try {
        const fresh = await api.getProcessingJob(jobId);
        if (!active) return;
        setJob((current) => current?.id === jobId ? fresh : current);
        setWorkspaceError(null);
      } catch (error) {
        if (active) setWorkspaceError(getApiErrorMessage(error));
      }
    };
    const interval = window.setInterval(() => { void poll(); }, 1000);
    void poll();
    return () => { active = false; window.clearInterval(interval); };
  }, [job?.id, job?.status]);

  useEffect(() => {
    const jobId = job?.id;
    if (jobId === undefined || (job.status !== 'completed' && job.status !== 'failed')) return;
    let active = true;
    const loadResults = async () => {
      try {
        const data = await api.getProcessingResults(jobId);
        if (active) {
          setResults(data);
          setSelectedFrameNumber(data.frames[0]?.frame_number ?? null);
          setWorkspaceError(null);
          void refreshHistory();
        }
      } catch (error) {
        if (active) setWorkspaceError(getApiErrorMessage(error));
      }
    };
    void loadResults();
    return () => { active = false; };
  }, [job?.id, job?.status, selectionVersion, refreshHistory]);

  const trackingEnabled = results?.status === 'completed'
    && results.processing_metadata.mode === 'REAL INFERENCE'
    && media?.media_type === 'video'
    && !String(results.processing_metadata.tracker ?? '').toUpperCase().includes('DEMO');

  useEffect(() => {
    if (!trackingEnabled || !job) {
      setVehicleTracks(null);
      setTrackTrajectories([]);
      setSelectedTrackId(null);
      setTrackingError(null);
      return;
    }
    let active = true;
    setVehicleTracks(null);
    setTrackTrajectories([]);
    setSelectedTrackId(null);
    setTrackingError(null);
    void api.getVehicleTrackSummary(job.id).then((summary) => {
      if (active) setVehicleTracks(summary);
    }).catch((error) => {
      if (active) setTrackingError(getApiErrorMessage(error));
    });
    return () => { active = false; };
  }, [trackingEnabled, job?.id, results?.job_id]);

  useEffect(() => {
    if (!trackingEnabled || !job) return;
    let active = true;
    void api.getVehicleTrackTrajectories(job.id, selectedFrameNumber).then((response) => {
      if (active) setTrackTrajectories(response.tracks);
    }).catch((error) => {
      if (active) setTrackingError(getApiErrorMessage(error));
    });
    return () => { active = false; };
  }, [trackingEnabled, job?.id, results?.job_id, selectedFrameNumber]);

  const resetWorkspace = () => {
    setSelectedFile(null);
    setMedia(null);
    setJob(null);
    setResults(null);
    setWorkspaceError(null);
    setUploadProgress(0);
    setSelectedPlateId(null);
    setSelectedFrameNumber(null);
    setVehicleTracks(null);
    setTrackTrajectories([]);
    setSelectedTrackId(null);
    setRouteCameraId('');
    setTrackingError(null);
    setSelectionVersion((version) => version + 1);
  };

  const selectHistoryItem = async (item: ProcessingHistoryItem) => {
    setWorkspaceError(null);
    setSelectedFile(null);
    setJob(null);
    setResults(null);
    setSelectedPlateId(null);
    setSelectedFrameNumber(null);
    setSelectedTrackId(null);
    try {
      const details = await api.getMediaDetails(item.media.id as number);
      setMedia(details.media);
      const historyJob = details.jobs[0] ?? item.job;
      setJob(historyJob);
      setRouteCameraId(historyJob.camera_id ?? '');
      setSelectionVersion((version) => version + 1);
    } catch (error) {
      setMedia(item.media);
      setJob(item.job);
      setRouteCameraId(item.job.camera_id ?? '');
      setWorkspaceError(getApiErrorMessage(error));
      setSelectionVersion((version) => version + 1);
    }
  };

  const onFileSelect = (file: File | null) => {
    setSelectedFile(file);
    setMedia(null);
    setJob(null);
    setResults(null);
    setWorkspaceError(null);
    setSelectedPlateId(null);
    setSelectedFrameNumber(null);
    setSelectedTrackId(null);
    setRouteCameraId('');
  };

  return (
    <div className="mb-8 space-y-4">
      <MediaUploadWorkspace
        key={selectionVersion}
        selectedFile={selectedFile}
        busy={preparing}
        uploadProgress={uploadProgress}
        onSelect={onFileSelect}
        onStart={() => { void startProcessing(); }}
        onReset={resetWorkspace}
      />
      {(media?.media_type === 'video' || (selectedFile && mediaTypeForFile(selectedFile) === 'video')) && <div className="bg-white flex flex-wrap items-end gap-3 rounded-xl border border-[#E2E8F0] p-4 shadow-sm">
        <label className="min-w-[250px] flex-1 text-xs text-slate-700 font-medium">Camera used to record this video
          <select value={routeCameraId} onChange={(event) => setRouteCameraId(event.target.value)} disabled={preparing} className="mt-1 block w-full rounded-lg border border-[#CBD5E1] bg-[#F8FAFC] px-3 py-2 text-xs text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500">
            <option value="">No camera selected (GPS import only)</option>
            {cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.id} · {camera.name}{camera.calibration_homography ? ' · calibrated' : ' · uncalibrated'}</option>)}
          </select>
        </label>
        <p className="max-w-xl text-[10px] text-slate-500">Calibrated mapping is used only when its recorded image dimensions match the uploaded video. An uncalibrated camera supplies no geographic route points; actual GPS observations can be attached to assigned track IDs.</p>
        {cameraLoadError && <p role="alert" className="w-full text-xs text-rose-700 font-medium">Camera list unavailable: {cameraLoadError}</p>}
      </div>}
      {(preparing || job || workspaceError) && <ProcessingProgress job={job} uploading={preparing} uploadProgress={uploadProgress} error={workspaceError} onRetry={() => { void startProcessing(); }} />}
      {previewMedia && <MediaPreview media={previewMedia} selectedFile={selectedFile} frames={results?.frames ?? []} detections={results?.detections ?? []} plates={results?.plate_results ?? []} selectedPlateId={selectedPlateId} onPlateSelect={setSelectedPlateId} selectedFrameNumber={selectedFrameNumber} onFrameSelect={setSelectedFrameNumber} trajectories={trackTrajectories} selectedTrackId={selectedTrackId} />}
      {results && <ProcessingResultsPanel results={results} selectedPlateId={selectedPlateId} onPlateSelect={setSelectedPlateId} />}
      {trackingEnabled && job && <VehicleTrackingPanel jobId={job.id} summary={vehicleTracks} selectedTrackId={selectedTrackId} onTrackSelect={setSelectedTrackId} onFrameSelect={setSelectedFrameNumber} error={trackingError} />}
      {results?.status === 'completed' && results.processing_metadata.mode === 'REAL INFERENCE' && media && job && (
        results.processing_metadata.plate_detector === 'REAL YOLO PLATE DETECTOR' && String(results.processing_metadata.ocr_engine ?? '').toLowerCase().includes('paddleocr')
          ? <ANPREvaluationPanel key={job.id} jobId={job.id} media={media} frames={results.frames} selectedFrameNumber={selectedFrameNumber} onFrameSelect={setSelectedFrameNumber} />
          : <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 font-medium">Accuracy evaluation is available for real YOLO plate detector and PaddleOCR results. This job used {String(results.processing_metadata.plate_detector ?? 'an unavailable plate detector')} / {String(results.processing_metadata.ocr_engine ?? 'an unavailable OCR provider')}; run a new real-model job before evaluating.</p>
      )}
      <ProcessingHistory items={history} loading={historyLoading} error={historyError} selectedJobId={job?.id ?? null} onSelect={(item) => { void selectHistoryItem(item); }} onRefresh={() => { void refreshHistory(); }} />
    </div>
  );
};
