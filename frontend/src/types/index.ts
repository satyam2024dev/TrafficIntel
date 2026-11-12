export type WeatherConditionType = 'clear' | 'rain' | 'fog' | 'night' | 'low_light' | 'glare';
export type ProcessingJobStatus = 'queued' | 'processing' | 'completed' | 'failed';
export type ProcessingMode = 'REAL' | 'DEMO' | 'HEURISTIC';

export interface MediaFile {
  id?: number;
  media_id?: number;
  original_filename: string;
  stored_filename: string;
  original_url?: string;
  media_type: 'image' | 'video';
  file_size: number;
  mime_type: string;
  width: number | null;
  height: number | null;
  duration: number | null;
  frame_count: number | null;
  created_at: string;
  processing_ready?: boolean;
  inference_status?: string;
}

export interface ProcessingJob {
  id: number;
  media_file_id: number;
  camera_id?: string | null;
  status: ProcessingJobStatus;
  progress: number;
  current_stage: string | null;
  error_message: string | null;
  processing_metadata: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface MediaDetection {
  id: number;
  processing_job_id: number;
  frame_number: number | null;
  timestamp: number | null;
  object_type: string;
  track_id: string | null;
  confidence: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  center_x: number | null;
  center_y: number | null;
}

export interface VehicleTrackPoint {
  detection_id: number;
  frame_number: number | null;
  timestamp: number | null;
  track_id: string;
  vehicle_class: string;
  detection_confidence: number;
  center_x: number;
  center_y: number;
  bbox: { x1: number; y1: number; x2: number; y2: number };
  plate_reads?: {
    plate_result_id: number;
    bbox?: { x1: number; y1: number; x2: number; y2: number };
    raw_ocr_text: string | null;
    normalized_ocr_text: string | null;
    validated_registration_number: string | null;
    plate_validation_status: string | null;
    plate_confidence: number | null;
    ocr_confidence: number | null;
  }[];
}

export interface VehicleTrackSummary {
  track_id: string;
  vehicle_class: string;
  first_frame_number: number | null;
  last_frame_number: number | null;
  first_timestamp: number | null;
  last_timestamp: number | null;
  duration_seconds: number;
  frame_count: number;
  detection_count: number;
  mean_detection_confidence: number;
  latest_center: { x: number; y: number };
  plate_read_count: number;
  plate_reads: {
    plate_result_id: number;
    detection_id: number;
    frame_number: number | null;
    timestamp: number | null;
    raw_ocr_text: string | null;
    normalized_ocr_text: string | null;
    validated_registration_number: string | null;
    plate_validation_status: string | null;
    plate_confidence: number | null;
    ocr_confidence: number | null;
  }[];
}

export interface VehicleTrackSummaryResponse {
  job_id: number;
  total_unique_tracked_vehicles: number;
  untracked_detection_count: number;
  total_detection_records: number;
  tracks: VehicleTrackSummary[];
}

export interface VehicleTrackTrailsResponse {
  job_id: number;
  through_frame_number: number | null;
  coordinate_space: string;
  tracks: VehicleTrackTrail[];
}

export interface VehicleTrackTrail {
  track_id: string;
  points: VehicleTrackPoint[];
}

export interface VehicleTrackHistoryResponse {
  job_id: number;
  track_id: string;
  vehicle_class: string;
  duration_seconds: number;
  frame_count: number;
  coordinate_space: string;
  points: VehicleTrackPoint[];
}

export interface CameraLocation extends Pick<Camera, 'id' | 'name' | 'location_name' | 'latitude' | 'longitude' | 'direction'> {
  calibrated: boolean;
  calibration_image_width: number | null;
  calibration_image_height: number | null;
  calibration_point_count: number | null;
}

export interface GeographicRoutePoint {
  id: number;
  track_id: string | null;
  camera_id: string | null;
  camera_name: string | null;
  camera_direction: string | null;
  detection_id: number | null;
  timestamp: string | null;
  media_timestamp_seconds: number | null;
  latitude: number;
  longitude: number;
  source_type: 'calibrated_estimate' | 'gps_observation';
  plate_reads: { plate_result_id: number; raw_ocr_text: string | null; normalized_ocr_text: string | null; validated_registration_number: string | null; ocr_confidence: number | null }[];
}

export interface GeographicRouteTrack {
  track_id: string;
  point_count: number;
  points: GeographicRoutePoint[];
  plate_reads: { plate_result_id: number; detection_id: number | null; timestamp: number | null; raw_ocr_text: string | null; normalized_ocr_text: string | null; validated_registration_number: string | null; ocr_confidence: number | null }[];
}

export interface GeographicRoutesResponse {
  job_id: number;
  camera_id: string | null;
  coordinate_space: string;
  time_alignment: string;
  available_sources: string[];
  unassigned_geographic_point_count: number;
  tracks: GeographicRouteTrack[];
  limitations: string[];
}

export interface MediaPlateResult {
  id: number;
  processing_job_id: number;
  detection_id: number | null;
  frame_number: number | null;
  timestamp: number | null;
  plate_text: string;
  raw_ocr_text: string | null;
  normalized_ocr_text: string | null;
  plate_validation_status: string | null;
  ocr_confidence: number | null;
  plate_confidence: number | null;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  original_crop_url: string | null;
  enhanced_crop_url: string | null;
  enhancement_metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface MediaFrame {
  id: number;
  processing_job_id: number;
  frame_number: number;
  timestamp: number;
  frame_url: string | null;
  enhanced_frame_url: string | null;
  weather_condition: WeatherConditionType | null;
  enhancement_metadata: Record<string, unknown> | null;
  processed: boolean;
  created_at: string;
}

export interface MediaUploadResponse extends MediaFile {
  media_id: number;
}

export interface ProcessingResults {
  job_id: number;
  status: ProcessingJobStatus;
  mode: string;
  detections: MediaDetection[];
  plate_results: MediaPlateResult[];
  frames: MediaFrame[];
  processing_metadata: Record<string, unknown> & {
    progress?: number;
    current_stage?: string;
    error_message?: string | null;
  };
}

export interface ANPREvaluationSampleInput {
  frame_number: number;
  ground_truth_plates: {
    registration_number: string;
    bbox: { x1: number; y1: number; x2: number; y2: number };
  }[];
}

export interface ANPREvaluationReport {
  methodology: Record<string, string | number>;
  aggregate: {
    sample_count: number;
    ground_truth_plate_count: number;
    prediction_count: number;
    true_positives: number;
    false_positives: number;
    false_negatives: number;
    precision: number | null;
    recall: number | null;
    f1_score: number | null;
    ocr_exact_matches: number;
    ocr_exact_match_accuracy: number | null;
    character_error_rate: number | null;
    duplicate_detection_count: number;
    incorrect_detection_count: number;
    ocr_failure_count: number;
    incorrect_ocr_count: number;
  };
  confidence_analysis: {
    plate_detection_confidence: Record<string, { count: number; mean: number | null }>;
    ocr_confidence: Record<string, { count: number; mean: number | null }>;
    confidence_semantics: string;
  };
  samples: {
    frame_number: number;
    ground_truth_count: number;
    prediction_count: number;
    detection: { true_positives: number; false_positives: number; false_negatives: number; precision: number | null; recall: number | null; f1_score: number | null };
    ocr: { exact_matches: number; count: number; exact_match_accuracy: number | null; character_error_rate: number | null };
    ground_truth: Record<string, unknown>[];
    predictions: Record<string, unknown>[];
  }[];
}

export interface ANPREvaluationResult {
  id: number;
  processing_job_id: number;
  iou_threshold: number;
  ground_truth: ANPREvaluationSampleInput[];
  report: ANPREvaluationReport;
  created_at: string;
}

export interface ProcessingHistoryItem {
  media: MediaFile & { id: number };
  job: ProcessingJob | null;
  vehicle_count: number;
  plate_count: number;
}

export interface MediaDetails {
  media: MediaFile & { id: number };
  jobs: ProcessingJob[];
}

export interface ProcessingJobCreated {
  job_id: number;
  media_id: number;
  status: ProcessingJobStatus;
  message: string;
}

export interface Camera {
  id: string;
  name: string;
  location_name: string;
  latitude: number;
  longitude: number;
  road_segment: string;
  status: 'active' | 'inactive' | 'maintenance' | 'offline';
  fps: number;
  resolution: string;
  weather_condition: WeatherConditionType;
  direction?: string;
  calibration_homography?: number[][] | null;
  calibration_image_width?: number | null;
  calibration_image_height?: number | null;
  calibration_point_count?: number | null;
  calibration_updated_at?: string | null;
  stream_type?: 'webcam' | 'rtsp' | null;
  stream_configured?: boolean;
  monitoring_status?: 'stopped' | 'starting' | 'connected' | 'reconnecting' | 'failed' | string;
  last_frame_at?: string | null;
  monitoring_error?: string | null;
  monitoring_reconnect_count?: number;
  created_at?: string;
}

export interface LiveCameraStatus {
  camera_id: string;
  status: 'stopped' | 'starting' | 'connected' | 'reconnecting' | 'failed' | string;
  last_frame_at: string | null;
  error: string | null;
  reconnect_count: number;
  frame_width: number | null;
  frame_height: number | null;
}

export interface LiveDetectionEvent {
  id: number;
  camera_id: string;
  captured_at: string;
  track_id: string | null;
  vehicle_class: string;
  vehicle_confidence: number;
  vehicle_bbox: { x1: number; y1: number; x2: number; y2: number };
  plate_text: string | null;
  raw_ocr_text: string | null;
  normalized_ocr_text: string | null;
  plate_confidence: number | null;
  ocr_confidence: number | null;
  plate_bbox: { x1: number; y1: number; x2: number; y2: number } | null;
  plate_crop_url: string | null;
}

export interface LiveGeographicRouteTrack {
  track_id: string;
  point_count: number;
  points: GeographicRoutePoint[];
  plate_reads: { event_id: number; timestamp: string; raw_ocr_text: string | null; normalized_ocr_text: string | null; validated_registration_number: string | null; ocr_confidence: number | null }[];
}

export interface LiveGeographicRoutesResponse {
  camera_id: string;
  coordinate_space: string;
  time_alignment: string;
  unassigned_point_count: number;
  tracks: LiveGeographicRouteTrack[];
  limitations: string[];
}

export interface Vehicle {
  id: string;
  license_plate: string;
  vehicle_type: 'car' | 'suv' | 'truck' | 'bus' | 'motorcycle';
  color: string;
  confidence: number;
  first_seen: string;
  last_seen: string;
  status: 'active' | 'completed' | 'parked' | 'flagged';
  total_sightings: number;
  avg_speed_kmh: number;
  registered_owner?: string;
  vehicle_make?: string;
  observations?: Observation[];
  plate_detections?: PlateDetection[];
  routes?: Route[];
}

export interface Observation {
  id: number;
  global_vehicle_id: string;
  camera_id: string;
  local_track_id: string;
  vehicle_type: string;
  color: string;
  detection_confidence: number;
  bbox_x: number;
  bbox_y: number;
  bbox_w: number;
  bbox_h: number;
  speed_kmh: number;
  observed_at: string;
  weather_condition: WeatherConditionType;
}

export interface PlateDetection {
  id: number;
  global_vehicle_id: string;
  camera_id: string;
  plate_number: string;
  ocr_confidence: number;
  plate_bbox_x: number;
  plate_bbox_y: number;
  plate_bbox_w: number;
  plate_bbox_h: number;
  weather_condition: WeatherConditionType;
  enhancement_applied: string;
  crop_image_url?: string;
  is_flagged: boolean;
  detected_at: string;
}

export interface RouteWaypoint {
  id: number;
  route_id: number;
  camera_id?: string;
  sequence_order: number;
  latitude: number;
  longitude: number;
  timestamp: string;
  speed_kmh: number;
}

export interface Route {
  id: number;
  global_vehicle_id: string;
  start_camera_id?: string;
  end_camera_id?: string;
  cameras_visited: string[];
  distance_km: number;
  duration_minutes: number;
  avg_speed_kmh: number;
  is_anomalous: boolean;
  started_at: string;
  completed_at?: string;
  points?: RouteWaypoint[];
}

export interface AlertItem {
  id: number;
  alert_type: string;
  severity: 'info' | 'warning' | 'medium' | 'high' | 'critical';
  message: string;
  camera_id?: string;
  global_vehicle_id?: string;
  rule_id?: number | null;
  source?: string;
  tracking_id?: string | null;
  registration_number?: string | null;
  related_detection_id?: number | null;
  related_live_event_id?: number | null;
  acknowledged_at?: string | null;
  is_resolved: boolean;
  created_at: string;
  resolved_at?: string;
}

export interface AnalyticsData {
  source_scope: string;
  filters: { start_at: string | null; end_at: string | null; camera_id: string | null; bucket: 'hour' | 'day' | 'week' };
  total_vehicle_detections: number;
  total_unique_tracked_vehicles: number;
  track_identity_scope: string;
  total_plates_detected: number;
  recognized_registration_numbers: number;
  validated_registration_numbers: number;
  unrecognized_plates: number;
  unreadable_plates: number;
  vehicles_by_class: Record<string, number>;
  camera_statistics: { camera_id: string; camera_name: string; vehicle_detections: number; configured_fps: number | null }[];
  time_series: { period: string; vehicles: number; plates: number; recognized_plates: number }[];
  vehicle_confidence_distribution: { range: string; count: number }[];
  plate_confidence_distribution: { range: string; count: number }[];
  ocr_confidence_distribution: { range: string; count: number }[];
  mean_ocr_confidence: number | null;
  anpr_recognition_trend: { period: string; plates_detected: number; recognized: number; read_rate: number | null }[];
  time_basis: string;
  current_traffic_level: string | null;
  traffic_level_note: string;
  mode: string;
}

export interface AnalyticsFilterInput { start_at?: string; end_at?: string; camera_id?: string; bucket?: 'hour' | 'day' | 'week'; }
export interface ANPRSearchItem {
  source: 'media_processing' | 'live_camera'; record_id: number; timestamp: string; media_timestamp_seconds: number | null;
  time_basis: string; camera_id: string | null; camera_name: string | null; track_id: string | null; vehicle_class: string | null;
  plate_text: string | null; raw_ocr_text: string | null; normalized_ocr_text: string | null;
  validated_registration_number: string | null; validation_status: string | null; ocr_confidence: number | null;
  plate_confidence: number | null; original_url: string | null; plate_crop_url: string | null;
  enhanced_crop_url: string | null; route_history_url: string | null;
}
export interface ANPRSearchPage { items: ANPRSearchItem[]; total: number; limit: number; offset: number; registration: string | null; }
export interface AlertPage { items: AlertItem[]; total: number; limit: number; offset: number; }
export type AlertRuleType = 'vehicle_detection' | 'registration_match' | 'repeated_detection' | 'low_confidence_ocr' | 'camera_disconnected' | 'camera_reconnected';
export interface AlertRule {
  id: number; name: string; rule_type: AlertRuleType; severity: string;
  configuration: Record<string, string | number | boolean>; enabled: boolean; created_at: string; updated_at: string;
}

export interface SimulationTickEvent {
  type: string;
  mode: string;
  timestamp: string;
  active_vehicles_count: number;
  camera_weather: Record<string, WeatherConditionType>;
  camera_fps: Record<string, number>;
  detections: {
    global_vehicle_id: string;
    local_track_id: string;
    camera_id: string;
    license_plate: string;
    vehicle_type: string;
    color: string;
    vehicle_make: string;
    bbox: { x: number; y: number; w: number; h: number };
    plate_bbox: { x: number; y: number; w: number; h: number };
    confidence: number;
    ocr_confidence: number;
    character_confidences: { char: string; confidence: number }[];
    weather_condition: WeatherConditionType;
    enhancement_applied: string;
    speed_kmh: number;
    cameras_visited: string[];
    route_distance_km: number;
    route_duration_min: number;
    is_anomalous: boolean;
    timestamp: string;
  }[];
  alerts: AlertItem[];
  events: any[];
}
