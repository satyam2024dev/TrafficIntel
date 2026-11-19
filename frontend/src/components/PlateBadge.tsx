import React from 'react';

interface PlateBadgeProps {
  plate: string;
  isFlagged?: boolean;
  isValid?: boolean;
  status?: 'valid' | 'invalid' | 'unvalidated' | 'pending';
  size?: 'sm' | 'md' | 'lg';
}

export const PlateBadge: React.FC<PlateBadgeProps> = ({
  plate,
  isFlagged = false,
  isValid,
  status,
  size = 'md',
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

  const statusBorderClass = isFlagged
    ? 'border-rose-600 ring-2 ring-rose-500/50'
    : determinedStatus === 'valid'
    ? 'border-emerald-600 ring-1 ring-emerald-500/40'
    : determinedStatus === 'invalid'
    ? 'border-rose-500/80'
    : determinedStatus === 'unvalidated' || determinedStatus === 'pending'
    ? 'border-amber-500/60'
    : 'border-slate-800';

  return (
    <div
      className={`license-plate-ui ${sizeClasses[size]} ${statusBorderClass}`}
      title={isFlagged ? 'FLAGGED VEHICLE' : `License Plate: ${plate || 'UNKNOWN'}`}
    >
      <div className="license-plate-ind h-full justify-center">
        <span className="text-[8px] leading-tight font-extrabold text-blue-200">IND</span>
      </div>
      <span className="font-mono text-slate-900 font-extrabold pr-2.5 tracking-wider tabular-nums">
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
