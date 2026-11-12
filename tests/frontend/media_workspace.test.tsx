import React from 'react';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { MediaUploadWorkspace } from '../../frontend/src/components/MediaUploadWorkspace';
import { ProcessingProgress } from '../../frontend/src/components/ProcessingProgress';
import { ProcessingResults } from '../../frontend/src/components/ProcessingResults';
import { ProcessingHistory } from '../../frontend/src/components/ProcessingHistory';
import { PlateResultCard } from '../../frontend/src/components/PlateResultCard';
import { ANPREvaluationPanel } from '../../frontend/src/components/ANPREvaluationPanel';
import { VehicleTrackingPanel } from '../../frontend/src/components/VehicleTrackingPanel';
import { CameraLocationManager } from '../../frontend/src/components/CameraLocationManager';
import { VehicleGeographicRoutePanel } from '../../frontend/src/components/VehicleGeographicRoutePanel';
import { classifyProcessingModes, getApiErrorMessage, getProcessingErrorMessage, validateMediaFile } from '../../frontend/src/utils/mediaProcessing';
import type { MediaDetection, ProcessingHistoryItem, ProcessingJob, ProcessingResults as ResultsData, VehicleTrackSummaryResponse } from '../../frontend/src/types';
import { runFrontendTests } from './components.test';

const noOp = () => undefined;
const fixtureJob: ProcessingJob = {
  id: 4, media_file_id: 2, status: 'processing', progress: 67, current_stage: 'Detecting vehicles',
  error_message: null, processing_metadata: {}, started_at: new Date(Date.now() - 4000).toISOString(),
  completed_at: null, created_at: new Date().toISOString(),
};

export function runMediaWorkspaceTests() {
  runFrontendTests();
  const emptyResults: ResultsData = {
    job_id: 4, status: 'completed', mode: 'DEMO/SYNTHETIC', detections: [], plate_results: [], frames: [],
    processing_metadata: { mode: 'DEMO/SYNTHETIC', plate_detector: 'GEOMETRIC HEURISTIC', vehicle_detector: 'DEMO/SYNTHETIC', ocr_engine: 'DEMO/SYNTHETIC' },
  };

  // 1. Workspace renders an accessible drop/browse area.
  const workspace = renderToStaticMarkup(<MediaUploadWorkspace selectedFile={null} busy={false} uploadProgress={0} onSelect={noOp} onStart={noOp} onReset={noOp} />);
  assert.match(workspace, /Drop media here or browse files/);
  assert.match(workspace, /Choose an image or video to process/);
  assert.match(workspace, /JPG/);

  // 2. Upload validation handles supported and unsupported inputs.
  assert.equal(validateMediaFile(new File(['image'], 'road.jpg', { type: 'image/jpeg' })), null);
  assert.match(validateMediaFile(new File(['bad'], 'script.exe')) ?? '', /Choose a JPG/);
  assert.match(getApiErrorMessage({ isAxiosError: true, code: 'ERR_NETWORK', response: undefined }), /NETWORK ERROR.*127\.0\.0\.1:8000/);
  assert.match(getApiErrorMessage({ response: { status: 415, data: { detail: 'Unsupported media extension.' } } }), /VALIDATION ERROR/);
  assert.match(getProcessingErrorMessage('OpenCV could not open the uploaded video.') ?? '', /PROCESSING ERROR/);
  assert.match(getProcessingErrorMessage('Database is unavailable.') ?? '', /DATABASE ERROR/);
  // 3. Image selection renders selected-file information.
  const imageSelection = renderToStaticMarkup(<MediaUploadWorkspace selectedFile={new File(['image'], 'road.png', { type: 'image/png' })} busy={false} uploadProgress={0} onSelect={noOp} onStart={noOp} onReset={noOp} />);
  assert.match(imageSelection, /road.png/);
  assert.match(imageSelection, /Upload and process/);
  // 4. Video selection is labeled as video.
  const videoSelection = renderToStaticMarkup(<MediaUploadWorkspace selectedFile={new File(['video'], 'traffic.mp4', { type: 'video/mp4' })} busy={false} uploadProgress={0} onSelect={noOp} onStart={noOp} onReset={noOp} />);
  assert.match(videoSelection, /VIDEO/);
  // 5-6. Processing and progress status are visible.
  const progress = renderToStaticMarkup(<ProcessingProgress job={fixtureJob} uploading={false} uploadProgress={0} error={null} onRetry={noOp} />);
  assert.match(progress, /PROCESSING/);
  assert.match(progress, /aria-valuenow="67"/);
  // 7 & 10. Completed empty results show honest empty states and mode badges.
  const empty = renderToStaticMarkup(<ProcessingResults results={emptyResults} selectedPlateId={null} onPlateSelect={noOp} />);
  assert.match(empty, /No vehicles were detected/);
  assert.match(empty, /No plate results are available/);
  assert.match(empty, /DEMO MODE/);
  assert.match(empty, /HEURISTIC/);
  // 8. Failed processing reports the backend error and retry action.
  const failed = renderToStaticMarkup(<ProcessingProgress job={{ ...fixtureJob, status: 'failed', error_message: 'REAL MODEL UNAVAILABLE: YOLO weights not found' }} uploading={false} uploadProgress={0} error={null} onRetry={noOp} />);
  assert.match(failed, /REAL AI MODEL UNAVAILABLE/);
  assert.match(failed, /Retry processing/);
  // 9. Provider metadata maps independently to REAL, DEMO, and HEURISTIC indicators.
  assert.deepEqual(classifyProcessingModes({ mode: 'REAL INFERENCE', vehicle_detector: 'REAL YOLO', ocr_provider: 'PaddleOCR', plate_detector: 'GEOMETRIC HEURISTIC' }), ['REAL', 'HEURISTIC']);
  assert.deepEqual(classifyProcessingModes(emptyResults.processing_metadata), ['DEMO', 'HEURISTIC']);
  const heuristicPlate = renderToStaticMarkup(<PlateResultCard plate={{
    id: 1, processing_job_id: 4, detection_id: 1, frame_number: null, timestamp: null,
    plate_text: 'KA01AB1234', raw_ocr_text: 'KA 01 AB 1234', normalized_ocr_text: 'KA01AB1234',
    plate_validation_status: 'valid_indian_format', ocr_confidence: 0.84, plate_confidence: null,
    x1: 1, y1: 2, x2: 30, y2: 12, original_crop_url: null, enhanced_crop_url: null,
    enhancement_metadata: {}, created_at: new Date().toISOString(),
  }} metadata={{ plate_detector: 'HEURISTIC' }} selected={false} onSelect={noOp} />);
  assert.match(heuristicPlate, /Plate detector confidence: Not available \(heuristic localization\)/);
  const unreadablePlate = renderToStaticMarkup(<PlateResultCard plate={{
    id: 2, processing_job_id: 4, detection_id: 1, frame_number: null, timestamp: null,
    plate_text: '', raw_ocr_text: null, normalized_ocr_text: null, plate_validation_status: 'empty',
    ocr_confidence: null, plate_confidence: 0.87, x1: 1, y1: 2, x2: 30, y2: 12,
    original_crop_url: null, enhanced_crop_url: null, enhancement_metadata: {}, created_at: new Date().toISOString(),
  }} metadata={{ plate_detector: 'REAL YOLO PLATE DETECTOR' }} selected={false} onSelect={noOp} />);
  assert.match(unreadablePlate, /No OCR text recognized/);
  assert.match(unreadablePlate, /OCR confidence unavailable/);
  assert.match(unreadablePlate, /87\.0%/);
  const unavailableResult = renderToStaticMarkup(<ProcessingResults results={{
    ...emptyResults,
    processing_metadata: { ...emptyResults.processing_metadata, plate_detector_error: 'REAL PLATE MODEL UNAVAILABLE: Configure PLATE_MODEL_PATH' },
  }} selectedPlateId={null} onPlateSelect={noOp} />);
  assert.match(unavailableResult, /REAL PLATE MODEL UNAVAILABLE/);
  // History renders real API rows and their persisted counts.
  const history: ProcessingHistoryItem[] = [{
    media: { id: 2, original_filename: 'road.jpg', stored_filename: 'abc.jpg', media_type: 'image', file_size: 12, mime_type: 'image/jpeg', width: 12, height: 10, duration: null, frame_count: null, created_at: new Date().toISOString() },
    job: { ...fixtureJob, status: 'completed', progress: 100 }, vehicle_count: 2, plate_count: 1,
  }];
  const historyMarkup = renderToStaticMarkup(<ProcessingHistory items={history} loading={false} error={null} selectedJobId={fixtureJob.id} onSelect={noOp} onRefresh={noOp} />);
  assert.match(historyMarkup, /road.jpg/);
  assert.match(historyMarkup, /2 vehicles/);
  assert.match(historyMarkup, /1 plates/);
  const typedDetectionCheck: MediaDetection | undefined = emptyResults.detections[0];
  assert.equal(typedDetectionCheck, undefined);
  const evaluationPanel = renderToStaticMarkup(<ANPREvaluationPanel
    jobId={fixtureJob.id}
    media={{ id: 2, original_filename: 'road.jpg', stored_filename: 'abc.jpg', media_type: 'image', file_size: 12, mime_type: 'image/jpeg', width: 640, height: 480, duration: null, frame_count: null, created_at: new Date().toISOString() }}
    frames={[]}
    selectedFrameNumber={1}
    onFrameSelect={noOp}
  />);
  assert.match(evaluationPanel, /ANPR accuracy evaluation/);
  assert.match(evaluationPanel, /Ground-truth Indian registration number/);
  assert.match(evaluationPanel, /Plate box x1, y1, x2, y2/);
  assert.match(evaluationPanel, /Mark frame reviewed/);
  const trackingSummary: VehicleTrackSummaryResponse = {
    job_id: 4, total_unique_tracked_vehicles: 1, untracked_detection_count: 1, total_detection_records: 3,
    tracks: [{ track_id: '7', vehicle_class: 'car', first_frame_number: 1, last_frame_number: 7, first_timestamp: 0, last_timestamp: 0.6, duration_seconds: 0.6, frame_count: 3, detection_count: 3, mean_detection_confidence: 0.91, latest_center: { x: 140, y: 88 }, plate_read_count: 1, plate_reads: [{ plate_result_id: 6, detection_id: 8, frame_number: 7, timestamp: 0.6, raw_ocr_text: 'KA 01 AB 1234', normalized_ocr_text: 'KA01AB1234', validated_registration_number: 'KA01AB1234', plate_validation_status: 'valid_indian_format', plate_confidence: 0.93, ocr_confidence: 0.88 }] }],
  };
  const trackingPanel = renderToStaticMarkup(<VehicleTrackingPanel jobId={4} summary={trackingSummary} selectedTrackId={null} onTrackSelect={noOp} onFrameSelect={noOp} error={null} />);
  assert.match(trackingPanel, /Vehicle tracks and image-space trajectories/);
  assert.match(trackingPanel, /Unique tracked vehicles/);
  assert.match(trackingPanel, /#7.*car/);
  assert.match(trackingPanel, /not geographic or GPS routes/);
  const geographicPanel = renderToStaticMarkup(<VehicleGeographicRoutePanel jobId={4} />);
  assert.match(geographicPanel, /Only external GPS observations and calibrated camera estimates are mapped/);
  assert.match(geographicPanel, /Loading geographic route data/);
  const cameraManager = renderToStaticMarkup(<CameraLocationManager />);
  assert.match(cameraManager, /Camera locations and calibration/);
  return '22 media workspace checks passed';
}
