import React from 'react';

interface PlateBadgeProps {
  plate: string;
  isFlagged?: boolean;
  isValid?: boolean;
  status?: 'valid' | 'invalid' | 'unvalidated' | 'pending';
  size?: 'sm' | 'md' | 'lg';
  vehicleType?: string;
}

export const PlateBadge: React.FC<PlateBadgeProps> = ({
  plate,
  isFlagged = false,
  isValid,
  status,
  size = 'md',
  vehicleType,
}) => {
  const sizeClasses = {
    sm: 'text-xs h-6',
    md: 'text-sm h-8',
    lg: 'text-base h-10 px-1',
  };

  const determinedStatus =
    status ||
    (isFlagged
      ? 'invalid'
      : isValid === true
      ? 'valid'
      : isValid === false
      ? 'invalid'
      : undefined);

  const isCommercial = vehicleType?.toLowerCase() === 'truck' || vehicleType?.toLowerCase() === 'bus';

  const statusBorderClass = isFlagged
    ? 'border-rose-600 ring-2 ring-rose-400'
    : determinedStatus === 'valid'
    ? 'border-emerald-600 ring-1 ring-emerald-300'
    : determinedStatus === 'invalid'
    ? 'border-rose-400'
    : determinedStatus === 'unvalidated' || determinedStatus === 'pending'
    ? 'border-amber-400'
    : 'border-slate-400';

  return (
    <div
      className={`license-plate-ui ${isCommercial ? 'license-plate-commercial' : 'bg-white'} ${sizeClasses[size]} ${statusBorderClass}`}
      title={isFlagged ? 'FLAGGED VEHICLE' : `License Plate: ${plate || 'UNKNOWN'}`}
    >
      <div className="license-plate-ind h-full justify-center">
        <span className="text-[8px] leading-tight font-extrabold text-blue-100">IND</span>
      </div>
      <span className="font-mono text-[#0F172A] font-extrabold pr-2.5 tracking-wider tabular-nums">
        {plate || 'UNKNOWN'}
      </span>
      {isFlagged && (
        <span className="mr-1.5 w-2 h-2 rounded-full bg-rose-600 animate-ping" />
      )}
      {!isFlagged && determinedStatus === 'valid' && (
        <span className="mr-1.5 w-1.5 h-1.5 rounded-full bg-emerald-600" title="Valid Indian Format" />
      )}
      {!isFlagged && (determinedStatus === 'unvalidated' || determinedStatus === 'pending') && (
        <span className="mr-1.5 w-1.5 h-1.5 rounded-full bg-amber-500" title="Unvalidated" />
      )}
    </div>
  );
};
