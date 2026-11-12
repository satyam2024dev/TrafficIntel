import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { api } from '../services/api';
import { trafficWs } from '../services/websocket';
import {
  Camera,
  Vehicle,
  AlertItem,
  AnalyticsData,
  SimulationTickEvent,
  PlateDetection,
} from '../types';

interface TrafficContextType {
  cameras: Camera[];
  vehicles: Vehicle[];
  alerts: AlertItem[];
  detections: PlateDetection[];
  analytics: AnalyticsData | null;
  wsConnected: boolean;
  isSimRunning: boolean;
  isSimPaused: boolean;
  liveStreamEvents: SimulationTickEvent | null;
  loading: boolean;
  refreshAll: () => Promise<void>;
  startSimulation: () => Promise<void>;
  pauseSimulation: () => Promise<void>;
  resetSimulation: () => Promise<void>;
}

const TrafficContext = createContext<TrafficContextType | undefined>(undefined);

export const TrafficProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [detections, setDetections] = useState<PlateDetection[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);

  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [isSimRunning, setIsSimRunning] = useState<boolean>(false);
  const [isSimPaused, setIsSimPaused] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  const [liveStreamEvents, setLiveStreamEvents] = useState<SimulationTickEvent | null>(null);

  const refreshAll = useCallback(async () => {
    try {
      const [camsData, vehsData, alertsData, analyticsData, simStatus, detsData] = await Promise.all([
        api.getCameras().catch(() => []),
        api.getVehicles().catch(() => []),
        api.getAlerts().catch(() => []),
        api.getAnalytics().catch(() => null),
        api.getDemoStatus().catch(() => ({ is_running: false, is_paused: false })),
        api.getDetections(undefined, 35).catch(() => []),
      ]);

      setCameras(camsData);
      setVehicles(vehsData);
      setAlerts(alertsData);
      setAnalytics(analyticsData);
      setIsSimRunning(simStatus.is_running);
      setIsSimPaused(simStatus.is_paused);
      setDetections(detsData);
    } catch (err) {
      console.error('Failed to load traffic intelligence data', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const startSimulation = useCallback(async () => {
    try {
      setIsSimRunning(true);
      setIsSimPaused(false);
      await api.startDemo();
      await refreshAll();
    } catch (e) {
      console.error('Error starting demo:', e);
    }
  }, [refreshAll]);

  const pauseSimulation = useCallback(async () => {
    try {
      setIsSimPaused(true);
      await api.pauseDemo();
      await refreshAll();
    } catch (e) {
      console.error('Error pausing demo:', e);
    }
  }, [refreshAll]);

  const resetSimulation = useCallback(async () => {
    try {
      setIsSimRunning(false);
      setIsSimPaused(false);
      setLiveStreamEvents(null);
      await api.resetDemo();
      await refreshAll();
    } catch (e) {
      console.error('Error resetting demo:', e);
    }
  }, [refreshAll]);

  useEffect(() => {
    refreshAll();

    // Connect WebSocket singleton
    trafficWs.connect();
    const unsubStatus = trafficWs.onStatus((status) => {
      setWsConnected(status);
    });

    const unsubMessages = trafficWs.subscribe((event: SimulationTickEvent) => {
      if (event.type === 'SIMULATION_TICK') {
        setLiveStreamEvents(event);
        setIsSimRunning(true);
        setIsSimPaused(false);

        // Update camera weather & fps in real time
        if (event.camera_weather) {
          setCameras((prev) =>
            prev.map((c) => ({
              ...c,
              weather_condition: event.camera_weather[c.id] || c.weather_condition,
              fps: event.camera_fps ? event.camera_fps[c.id] || c.fps : c.fps,
            }))
          );
        }

        // Prepend new alerts
        if (event.alerts && event.alerts.length > 0) {
          setAlerts((prev) => {
            const existingIds = new Set(prev.map((a) => a.id));
            const newOnes = event.alerts.filter((a) => !existingIds.has(a.id));
            return [...newOnes, ...prev].slice(0, 50);
          });
        }

        // Prepend new detections & update vehicle counts in analytics
        if (event.detections && event.detections.length > 0) {
          const newDets: PlateDetection[] = event.detections.map((d, idx) => ({
            id: Date.now() + idx,
            global_vehicle_id: d.global_vehicle_id,
            camera_id: d.camera_id,
            plate_number: d.license_plate,
            ocr_confidence: d.ocr_confidence,
            plate_bbox_x: d.plate_bbox.x,
            plate_bbox_y: d.plate_bbox.y,
            plate_bbox_w: d.plate_bbox.w,
            plate_bbox_h: d.plate_bbox.h,
            weather_condition: d.weather_condition,
            enhancement_applied: d.enhancement_applied,
            is_flagged: d.is_anomalous,
            detected_at: d.timestamp,
          }));

          setDetections((prev) => [...newDets, ...prev].slice(0, 50));

          // Also asynchronously sync vehicles and routes with DB
          api.getVehicles().then(setVehicles).catch(() => {});
          api.getAnalytics().then(setAnalytics).catch(() => {});
        }
      }
    });

    // Gentle polling interval when idle
    const pollInterval = setInterval(() => {
      if (!isSimRunning) {
        refreshAll();
      }
    }, 10000);

    return () => {
      unsubStatus();
      unsubMessages();
      clearInterval(pollInterval);
    };
  }, [refreshAll, isSimRunning]);

  return (
    <TrafficContext.Provider
      value={{
        cameras,
        vehicles,
        alerts,
        detections,
        analytics,
        wsConnected,
        isSimRunning,
        isSimPaused,
        liveStreamEvents,
        loading,
        refreshAll,
        startSimulation,
        pauseSimulation,
        resetSimulation,
      }}
    >
      {children}
    </TrafficContext.Provider>
  );
};

export function useTrafficData() {
  const context = useContext(TrafficContext);
  if (!context) {
    throw new Error('useTrafficData must be used within a TrafficProvider');
  }
  return context;
}
