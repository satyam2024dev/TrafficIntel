import axios from 'axios';
import {
  Camera,
  Vehicle,
  Observation,
  Route,
  PlateDetection,
  AlertItem,
  AnalyticsData,
  MediaDetails,
  MediaFile,
  MediaUploadResponse,
  ProcessingHistoryItem,
  ProcessingJob,
  ProcessingJobCreated,
  ProcessingResults,
  ANPREvaluationResult,
  ANPREvaluationSampleInput,
  VehicleTrackHistoryResponse,
  VehicleTrackSummaryResponse,
  VehicleTrackTrailsResponse,
  CameraLocation,
  GeographicRoutesResponse,
  LiveCameraStatus,
  LiveDetectionEvent,
  LiveGeographicRoutesResponse,
  AnalyticsFilterInput,
  ANPRSearchPage,
  AlertPage,
  AlertRule,
} from '../types';

const API_BASE = '/api';
const DEV_AUTH_BYPASS = import.meta.env?.DEV === true && import.meta.env?.VITE_DEV_AUTH_BYPASS === 'true';

export const apiClient = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const requestUrl = String(error?.config?.url ?? '');
    if (!DEV_AUTH_BYPASS && error?.response?.status === 401 && !requestUrl.includes('/auth/login') && window.location.pathname !== '/login') {
      window.location.assign('/login');
    }
    return Promise.reject(error);
  },
);

export const api = {
  login: async (username: string, password: string) => (await apiClient.post<{id:number;username:string;full_name:string|null;role:string}>('/auth/login', { username, password })).data,
  logout: async () => { await apiClient.post('/auth/logout'); },
  getCurrentUser: async () => (await apiClient.get<{id:number;username:string;full_name:string|null;role:string}>('/auth/me')).data,
  getHealth: async () => {
    const res = await apiClient.get<{ status: string; database: string; ai_mode: 'real' | 'demo' }>('/health');
    return res.data;
  },

  // Vehicles
  getVehicles: async (status?: string, search?: string) => {
    const params: any = {};
    if (status) params.status = status;
    if (search) params.search = search;
    const res = await apiClient.get<Vehicle[]>('/vehicles', { params });
    return res.data;
  },
  getVehicleById: async (id: string) => {
    const res = await apiClient.get<Vehicle>(`/vehicles/${id}`);
    return res.data;
  },
  getVehicleHistory: async (id: string) => {
    const res = await apiClient.get<Observation[]>(`/vehicles/${id}/history`);
    return res.data;
  },
  getVehicleRoute: async (id: string) => {
    const res = await apiClient.get<Route>(`/vehicles/${id}/route`);
    return res.data;
  },

  // Cameras
  getCameras: async () => {
    const res = await apiClient.get<Camera[]>('/cameras');
    return res.data;
  },
  getCameraById: async (id: string) => {
    const res = await apiClient.get<Camera>(`/cameras/${id}`);
    return res.data;
  },
  getCameraLocations: async () => {
    const res = await apiClient.get<CameraLocation[]>('/cameras/locations');
    return res.data;
  },
  updateCameraLocation: async (id: string, data: { name?: string; location_name?: string; latitude?: number; longitude?: number; direction?: string; road_segment?: string }) => {
    const res = await apiClient.put<Camera>(`/cameras/${encodeURIComponent(id)}/location`, data);
    return res.data;
  },
  calibrateCamera: async (id: string, data: { image_width: number; image_height: number; points: { image_x: number; image_y: number; latitude: number; longitude: number }[] }) => {
    const res = await apiClient.put(`/cameras/${encodeURIComponent(id)}/calibration`, data);
    return res.data;
  },
  clearCameraCalibration: async (id: string) => {
    await apiClient.delete(`/cameras/${encodeURIComponent(id)}/calibration`);
  },
  createCamera: async (data: Partial<Camera>) => {
    const res = await apiClient.post<Camera>('/cameras', data);
    return res.data;
  },
  configureCameraStream: async (id: string, data: { source_type: 'webcam' | 'rtsp'; device_index?: number; stream_url?: string }) => {
    const res = await apiClient.put(`/cameras/${encodeURIComponent(id)}/stream`, data);
    return res.data as { camera_id: string; stream_type: string; stream_configured: boolean; credentials_returned: false };
  },
  startLiveCamera: async (id: string) => (await apiClient.post<LiveCameraStatus>(`/cameras/${encodeURIComponent(id)}/live/start`)).data,
  stopLiveCamera: async (id: string) => (await apiClient.post<LiveCameraStatus>(`/cameras/${encodeURIComponent(id)}/live/stop`)).data,
  getLiveCameraStatus: async (id: string) => (await apiClient.get<LiveCameraStatus>(`/cameras/${encodeURIComponent(id)}/live/status`)).data,
  getLiveCameraEvents: async (id: string) => (await apiClient.get<LiveDetectionEvent[]>(`/cameras/${encodeURIComponent(id)}/live/events`)).data,
  getLiveCameraRoutes: async (id: string) => (await apiClient.get<LiveGeographicRoutesResponse>(`/cameras/${encodeURIComponent(id)}/live/routes`)).data,
  getLiveCameraStreamUrl: (id: string) => `${API_BASE}/cameras/${encodeURIComponent(id)}/live/stream`,

  // Detections & Plates
  getDetections: async (cameraId?: string, limit: number = 50) => {
    const params: any = { limit };
    if (cameraId) params.camera_id = cameraId;
    const res = await apiClient.get<PlateDetection[]>('/detections', { params });
    return res.data;
  },
  getPlates: async () => {
    const res = await apiClient.get<any[]>('/plates');
    return res.data;
  },

  // Routes
  getRoutes: async (limit: number = 30) => {
    const res = await apiClient.get<Route[]>('/routes', { params: { limit } });
    return res.data;
  },

  // Analytics
  getAnalytics: async (filters: AnalyticsFilterInput = {}) => {
    const res = await apiClient.get<AnalyticsData>('/analytics', { params: filters });
    return res.data;
  },
  searchANPRHistory: async (params: AnalyticsFilterInput & { registration?: string; limit?: number; offset?: number } = {}) =>
    (await apiClient.get<ANPRSearchPage>('/analytics/anpr/search', { params })).data,
  getANPRDetections: async (params: AnalyticsFilterInput & { limit?: number; offset?: number } = {}) =>
    (await apiClient.get<ANPRSearchPage>('/analytics/anpr/detections', { params })).data,
  getAnalyticsExportUrl: (reportType: 'daily_traffic' | 'vehicle_classification' | 'camera_detections' | 'anpr' | 'ocr_confidence' | 'alert_history', filters: AnalyticsFilterInput & { severity?: string; resolved?: boolean; acknowledged?: boolean } = {}) => {
    const params = new URLSearchParams({ report_type: reportType });
    Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== '') params.set(key, String(value)); });
    return `${API_BASE}/analytics/reports.csv?${params.toString()}`;
  },

  // Alerts
  getAlerts: async (resolved?: boolean) => {
    const params: any = {};
    if (resolved !== undefined) params.resolved = resolved;
    const res = await apiClient.get<AlertItem[]>('/alerts', { params });
    return res.data;
  },
  getAlertsPage: async (params: { resolved?: boolean; severity?: string; camera_id?: string; start_at?: string; end_at?: string; acknowledged?: boolean; limit?: number; offset?: number } = {}) =>
    (await apiClient.get<AlertPage>('/alerts/page', { params })).data,
  getAlertRules: async () => (await apiClient.get<AlertRule[]>('/alerts/rules')).data,
  createAlertRule: async (data: { name: string; rule_type: AlertRule['rule_type']; severity: string; configuration: Record<string, string | number | boolean>; enabled?: boolean }) =>
    (await apiClient.post<AlertRule>('/alerts/rules', data)).data,
  updateAlertRule: async (id: number, data: Partial<Pick<AlertRule, 'name' | 'rule_type' | 'severity' | 'configuration' | 'enabled'>>) =>
    (await apiClient.patch<AlertRule>(`/alerts/rules/${id}`, data)).data,
  deleteAlertRule: async (id: number) => { await apiClient.delete(`/alerts/rules/${id}`); },
  acknowledgeAlert: async (id: number) => (await apiClient.patch<AlertItem>(`/alerts/${id}/acknowledge`)).data,
  resolveAlert: async (id: number) => {
    const res = await apiClient.patch<AlertItem>(`/alerts/${id}/resolve`);
    return res.data;
  },

  // Weather
  getWeather: async () => {
    const res = await apiClient.get<any[]>('/weather');
    return res.data;
  },

  // Demo Control
  startDemo: async () => {
    const res = await apiClient.post<{ status: string; message: string }>('/demo/start');
    return res.data;
  },
  pauseDemo: async () => {
    const res = await apiClient.post<{ status: string; message: string }>('/demo/pause');
    return res.data;
  },
  resetDemo: async () => {
    const res = await apiClient.post<{ status: string; message: string }>('/demo/reset');
    return res.data;
  },
  getDemoStatus: async () => {
    const res = await apiClient.get<{
      is_running: boolean;
      is_paused: boolean;
      active_vehicles_count: number;
      camera_weather: Record<string, string>;
      camera_fps: Record<string, number>;
    }>('/demo/status');
    return res.data;
  },

  // Uploaded media and AI processing
  uploadMedia: async (file: File, onProgress?: (percent: number) => void) => {
    const form = new FormData();
    form.append('file', file);
    const res = await apiClient.post<MediaUploadResponse>('/media/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (event) => {
        if (event.total) onProgress?.(Math.round((event.loaded / event.total) * 100));
      },
    });
    return res.data;
  },
  startMediaProcessing: async (mediaId: number, cameraId?: string | null) => {
    const res = await apiClient.post<ProcessingJobCreated>(`/media/process/${mediaId}`, undefined, { params: cameraId ? { camera_id: cameraId } : {} });
    return res.data;
  },
  getProcessingJob: async (jobId: number) => {
    const res = await apiClient.get<ProcessingJob & { job_id?: number; media_id: number }>(`/media/jobs/${jobId}`);
    return { ...res.data, id: res.data.id ?? res.data.job_id ?? jobId };
  },
  getProcessingResults: async (jobId: number) => {
    const res = await apiClient.get<ProcessingResults>(`/media/jobs/${jobId}/results`);
    return res.data;
  },
  createANPREvaluation: async (jobId: number, samples: ANPREvaluationSampleInput[], iouThreshold = 0.5) => {
    const res = await apiClient.post<ANPREvaluationResult>(`/media/jobs/${jobId}/evaluations`, {
      samples,
      iou_threshold: iouThreshold,
    });
    return res.data;
  },
  getANPREvaluations: async (jobId: number) => {
    const res = await apiClient.get<ANPREvaluationResult[]>(`/media/jobs/${jobId}/evaluations`);
    return res.data;
  },
  getVehicleTrackSummary: async (jobId: number) => {
    const res = await apiClient.get<VehicleTrackSummaryResponse>(`/media/jobs/${jobId}/tracks`);
    return res.data;
  },
  getVehicleTrackTrajectories: async (jobId: number, throughFrameNumber: number | null) => {
    const res = await apiClient.get<VehicleTrackTrailsResponse>(`/media/jobs/${jobId}/tracks/trajectories`, {
      params: throughFrameNumber === null ? {} : { through_frame_number: throughFrameNumber },
    });
    return res.data;
  },
  getVehicleTrackHistory: async (jobId: number, trackId: string) => {
    const res = await apiClient.get<VehicleTrackHistoryResponse>(`/media/jobs/${jobId}/tracks/${encodeURIComponent(trackId)}/trajectory`);
    return res.data;
  },
  getGeographicRoutes: async (jobId: number) => {
    const res = await apiClient.get<GeographicRoutesResponse>(`/media/jobs/${jobId}/routes`);
    return res.data;
  },
  importGPSRoutePoints: async (jobId: number, points: { track_id: string; timestamp: string; latitude: number; longitude: number; camera_id?: string }[]) => {
    const res = await apiClient.post(`/media/jobs/${jobId}/routes/gps`, { points });
    return res.data;
  },
  getProcessingHistory: async (limit: number = 30) => {
    const res = await apiClient.get<ProcessingHistoryItem[]>('/media/history', { params: { limit } });
    return res.data;
  },
  getMediaDetails: async (mediaId: number) => {
    const res = await apiClient.get<MediaDetails>(`/media/${mediaId}`);
    return res.data;
  },
  getMediaArtifactUrl: (filename: string) => `${API_BASE}/media/artifacts/${encodeURIComponent(filename)}`,
  getMediaOriginalUrl: (mediaId: number) => `${API_BASE}/media/${mediaId}/original`,
  getUploadedMedia: async (media: MediaFile) => {
    const mediaId = media.id ?? media.media_id;
    if (mediaId === undefined) throw new Error('Media ID is missing.');
    const details = await api.getMediaDetails(mediaId);
    return details.media;
  },
};
