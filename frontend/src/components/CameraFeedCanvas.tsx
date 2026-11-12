import React, { useEffect, useRef } from 'react';
import { WeatherConditionType } from '../types';
import { getWeatherBadge } from '../utils/formatters';

interface DetectedBox {
  trackId: string;
  plate: string;
  vehicleType: string;
  confidence: number;
  ocrConfidence: number;
  color: string;
  x: number;
  y: number;
  w: number;
  h: number;
  isFlagged?: boolean;
}

interface CameraFeedCanvasProps {
  cameraId: string;
  cameraName: string;
  locationName: string;
  fps: number;
  weatherCondition: WeatherConditionType;
  status: 'active' | 'inactive' | 'maintenance' | 'offline';
  detectedVehicles?: DetectedBox[];
}

export const CameraFeedCanvas: React.FC<CameraFeedCanvasProps> = ({
  cameraId,
  cameraName,
  locationName,
  fps,
  weatherCondition,
  status,
  detectedVehicles = [],
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let offset = 0;

    const render = () => {
      offset = (offset + 1.2) % 40;
      const width = canvas.width;
      const height = canvas.height;

      // 1. Draw highway surface
      ctx.fillStyle = '#0b0f19';
      ctx.fillRect(0, 0, width, height);

      // Draw road perspective lanes
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 2;
      ctx.beginPath();
      // Left border
      ctx.moveTo(width * 0.1, height);
      ctx.lineTo(width * 0.35, height * 0.25);
      // Right border
      ctx.moveTo(width * 0.9, height);
      ctx.lineTo(width * 0.65, height * 0.25);
      ctx.stroke();

      // Dashed lane lines
      ctx.strokeStyle = '#334155';
      ctx.setLineDash([15, 20]);
      ctx.lineDashOffset = -offset;
      ctx.beginPath();
      ctx.moveTo(width * 0.38, height);
      ctx.lineTo(width * 0.45, height * 0.25);
      ctx.moveTo(width * 0.62, height);
      ctx.lineTo(width * 0.55, height * 0.25);
      ctx.stroke();
      ctx.setLineDash([]); // Reset dash

      // Horizon line
      ctx.strokeStyle = '#0f172a';
      ctx.beginPath();
      ctx.moveTo(0, height * 0.25);
      ctx.lineTo(width, height * 0.25);
      ctx.stroke();

      // 2. Weather atmospheric layer
      if (weatherCondition === 'night' || weatherCondition === 'low_light') {
        ctx.fillStyle = 'rgba(2, 6, 23, 0.65)';
        ctx.fillRect(0, 0, width, height);
      } else if (weatherCondition === 'fog') {
        ctx.fillStyle = 'rgba(148, 163, 184, 0.25)';
        ctx.fillRect(0, 0, width, height);
      } else if (weatherCondition === 'rain') {
        // Rain particles
        ctx.strokeStyle = 'rgba(147, 197, 253, 0.35)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let i = 0; i < 40; i++) {
          const rx = (i * 37 + offset * 7) % width;
          const ry = (i * 29 + offset * 11) % height;
          ctx.moveTo(rx, ry);
          ctx.lineTo(rx - 3, ry + 10);
        }
        ctx.stroke();
      } else if (weatherCondition === 'glare') {
        const grad = ctx.createRadialGradient(width * 0.75, height * 0.2, 10, width * 0.75, height * 0.2, 160);
        grad.addColorStop(0, 'rgba(254, 240, 138, 0.35)');
        grad.addColorStop(1, 'rgba(254, 240, 138, 0)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, width, height);
      }

      // 3. Draw Detected Vehicle Bounding Boxes
      const scaleX = width / 1280;
      const scaleY = height / 720;

      const vehiclesToDraw = detectedVehicles.length > 0 ? detectedVehicles : [
        {
          trackId: `${cameraId}-04`,
          plate: 'KA01AB1234',
          vehicleType: 'car',
          confidence: 0.97,
          ocrConfidence: 0.95,
          color: 'Silver',
          x: 280,
          y: 330,
          w: 260,
          h: 180,
          isFlagged: false
        },
        {
          trackId: `${cameraId}-11`,
          plate: 'KA05XY9988',
          vehicleType: 'suv',
          confidence: 0.93,
          ocrConfidence: 0.91,
          color: 'White',
          x: 640,
          y: 360,
          w: 290,
          h: 210,
          isFlagged: true
        }
      ];

      vehiclesToDraw.forEach((v) => {
        const bx = v.x * scaleX;
        const by = v.y * scaleY;
        const bw = v.w * scaleX;
        const bh = v.h * scaleY;

        const boxColor = v.isFlagged ? '#f43f5e' : '#06b6d4';

        // Vehicle simulated chassis
        ctx.fillStyle = v.color.toLowerCase().includes('blue') ? '#1e3a8a' :
                        v.color.toLowerCase().includes('red') ? '#991b1b' :
                        v.color.toLowerCase().includes('white') ? '#cbd5e1' : '#475569';
        ctx.fillRect(bx + bw * 0.1, by + bh * 0.15, bw * 0.8, bh * 0.7);

        // Windshield
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(bx + bw * 0.2, by + bh * 0.22, bw * 0.6, bh * 0.25);

        // Headlights
        if (weatherCondition === 'night' || weatherCondition === 'rain') {
          ctx.fillStyle = '#fef08a';
          ctx.fillRect(bx + bw * 0.12, by + bh * 0.7, bw * 0.15, bh * 0.1);
          ctx.fillRect(bx + bw * 0.73, by + bh * 0.7, bw * 0.15, bh * 0.1);
        }

        // Bounding Box
        ctx.strokeStyle = boxColor;
        ctx.lineWidth = 2;
        ctx.strokeRect(bx, by, bw, bh);

        // Corner accents
        const cLen = 10;
        ctx.lineWidth = 3;
        ctx.beginPath();
        // Top-left
        ctx.moveTo(bx, by + cLen); ctx.lineTo(bx, by); ctx.lineTo(bx + cLen, by);
        // Top-right
        ctx.moveTo(bx + bw - cLen, by); ctx.lineTo(bx + bw, by); ctx.lineTo(bx + bw, by + cLen);
        // Bottom-left
        ctx.moveTo(bx, by + bh - cLen); ctx.lineTo(bx, by + bh); ctx.lineTo(bx + cLen, by + bh);
        // Bottom-right
        ctx.moveTo(bx + bw - cLen, by + bh); ctx.lineTo(bx + bw, by + bh); ctx.lineTo(bx + bw, by + bh - cLen);
        ctx.stroke();

        // Label Tag Above Box
        ctx.fillStyle = v.isFlagged ? 'rgba(225, 29, 72, 0.9)' : 'rgba(15, 23, 42, 0.85)';
        ctx.fillRect(bx, by - 22, bw, 20);

        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 10px monospace';
        ctx.fillText(`${v.trackId} | ${v.vehicleType.toUpperCase()} ${(v.confidence * 100).toFixed(0)}%`, bx + 4, by - 8);

        // License Plate Tag on Vehicle
        const pw = bw * 0.55;
        const ph = bh * 0.18;
        const px = bx + (bw - pw) / 2;
        const py = by + bh * 0.72;

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(px, py, pw, ph);
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 1;
        ctx.strokeRect(px, py, pw, ph);

        // Blue IND strip
        ctx.fillStyle = '#1e3a8a';
        ctx.fillRect(px, py, pw * 0.18, ph);

        // Plate text
        ctx.fillStyle = '#0f172a';
        ctx.font = 'bold 9px monospace';
        ctx.fillText(v.plate, px + pw * 0.22, py + ph * 0.72);
      });

      // 4. On-Screen Camera Telemetry HUD
      ctx.fillStyle = 'rgba(7, 11, 20, 0.75)';
      ctx.fillRect(0, 0, width, 28);

      // REC dot
      ctx.fillStyle = '#ef4444';
      ctx.beginPath();
      ctx.arc(14, 14, 4, 0, Math.PI * 2);
      ctx.fill();

      // Camera title
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 11px monospace';
      ctx.fillText(`CAM ${cameraId} [${cameraName}]`, 26, 18);

      // FPS & Weather
      ctx.fillStyle = '#38bdf8';
      ctx.fillText(`${fps.toFixed(1)} FPS`, width - 110, 18);

      ctx.fillStyle = '#a855f7';
      ctx.fillText(weatherCondition.toUpperCase(), width - 55, 18);

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [cameraId, cameraName, fps, weatherCondition, detectedVehicles]);

  const weatherBadge = getWeatherBadge(weatherCondition);

  return (
    <div className="glass-panel rounded-xl overflow-hidden border border-slate-800 flex flex-col shadow-lg">
      <div className="relative aspect-video w-full bg-slate-950">
        <canvas
          ref={canvasRef}
          width={640}
          height={360}
          className="w-full h-full object-cover"
        />
        <div className="absolute bottom-2 left-2 flex items-center gap-2">
          <span className="text-[10px] font-mono bg-black/70 text-slate-300 px-2 py-0.5 rounded border border-slate-700/60 backdrop-blur-sm">
            {locationName}
          </span>
        </div>
        <div className="absolute top-2 right-2 flex items-center gap-1.5">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-black/70 text-emerald-400 border border-emerald-500/40">
            AUTO-ENHANCE: {weatherBadge.filter}
          </span>
        </div>
      </div>

      <div className="px-3.5 py-2.5 bg-slate-900/90 border-t border-slate-800 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-mono font-semibold text-slate-200">{cameraId}</span>
          <span className="text-slate-400 text-[11px] truncate max-w-[120px]">{cameraName}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-cyan-400">{fps.toFixed(1)} fps</span>
          <span className={`text-[10px] px-2 py-0.5 rounded border ${weatherBadge.color}`}>
            {weatherBadge.icon} {weatherBadge.label}
          </span>
        </div>
      </div>
    </div>
  );
};
