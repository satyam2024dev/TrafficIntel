import React from 'react';
import { MediaDetection, MediaPlateResult, VehicleTrackTrail } from '../types';

interface DetectionOverlayProps {
  width: number;
  height: number;
  detections: MediaDetection[];
  plates: MediaPlateResult[];
  selectedPlateId?: number | null;
  trajectories?: VehicleTrackTrail[];
  selectedTrackId?: string | null;
}

export const DetectionOverlay: React.FC<DetectionOverlayProps> = ({ width, height, detections, plates, selectedPlateId, trajectories = [], selectedTrackId }) => {
  if (width <= 0 || height <= 0) return null;
  const labelSize = Math.max(12, Math.min(width, height) * 0.025);
  return (
    <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={`Overlay showing ${detections.length} vehicle detections and ${plates.length} license plate results`}>
      {trajectories.map((trajectory, index) => {
        const points = trajectory.points.map((point) => `${point.center_x},${point.center_y}`).join(' ');
        const lastPoint = trajectory.points[trajectory.points.length - 1];
        const highlighted = trajectory.track_id === selectedTrackId;
        const hue = Array.from(trajectory.track_id).reduce((total, character) => total + character.charCodeAt(0), index * 53) % 360;
        const stroke = highlighted ? '#facc15' : `hsl(${hue} 85% 65%)`;
        return <g key={`trail-${trajectory.track_id}`}>
          {trajectory.points.length > 1 && <polyline points={points} fill="none" stroke={stroke} strokeWidth={highlighted ? 4 : 3} strokeOpacity="0.88" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />}
          {lastPoint && <><circle cx={lastPoint.center_x} cy={lastPoint.center_y} r={Math.max(4, width / 180)} fill={stroke} stroke="#0f172a" strokeWidth={2} vectorEffect="non-scaling-stroke" /><text x={lastPoint.center_x + labelSize * 0.5} y={lastPoint.center_y - labelSize * 0.6} fill={stroke} fontSize={labelSize} fontFamily="monospace">#{trajectory.track_id} trail</text></>}
        </g>;
      })}
      {detections.map((detection) => {
        const boxHeight = detection.y2 - detection.y1;
        return <g key={`vehicle-${detection.id}`}>
          <rect x={detection.x1} y={detection.y1} width={detection.x2 - detection.x1} height={boxHeight} fill="none" stroke="#22d3ee" strokeWidth={Math.max(2, width / 500)} vectorEffect="non-scaling-stroke" />
          <rect x={detection.x1} y={Math.max(0, detection.y1 - labelSize * 1.6)} width={Math.min(width - detection.x1, labelSize * 13)} height={labelSize * 1.6} fill="#082f49" fillOpacity="0.92" />
          <text x={detection.x1 + labelSize * 0.3} y={Math.max(labelSize, detection.y1 - labelSize * 0.35)} fill="#cffafe" fontSize={labelSize} fontFamily="monospace">{detection.object_type} {(detection.confidence * 100).toFixed(0)}%{detection.track_id ? ` · #${detection.track_id}` : ''}</text>
        </g>;
      })}
      {plates.map((plate) => {
        const highlighted = plate.id === selectedPlateId;
        return <g key={`plate-${plate.id}`}>
          <rect x={plate.x1} y={plate.y1} width={plate.x2 - plate.x1} height={plate.y2 - plate.y1} fill="none" stroke={highlighted ? '#facc15' : '#fb7185'} strokeWidth={highlighted ? 4 : 2} vectorEffect="non-scaling-stroke" />
          <text x={plate.x1} y={Math.max(labelSize, plate.y1 - 3)} fill={highlighted ? '#fef08a' : '#fecdd3'} fontSize={labelSize} fontFamily="monospace">{plate.normalized_ocr_text || plate.plate_text || 'PLATE'}{plate.ocr_confidence === null ? '' : ` ${(plate.ocr_confidence * 100).toFixed(0)}%`}</text>
        </g>;
      })}
    </svg>
  );
};
