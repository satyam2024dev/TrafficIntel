import React from 'react';

interface PlateBadgeProps {
  plate: string;
  isFlagged?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export const PlateBadge: React.FC<PlateBadgeProps> = ({ plate, isFlagged = false, size = 'md' }) => {
  const sizeClasses = {
    sm: 'text-xs h-6',
    md: 'text-sm h-8',
    lg: 'text-base h-10 px-1',
  };

  return (
    <div
      className={`license-plate-ui ${sizeClasses[size]} ${
        isFlagged ? 'border-rose-600 ring-2 ring-rose-500/50' : 'border-slate-900'
      }`}
      title={isFlagged ? 'FLAGGED VEHICLE' : 'License Plate'}
    >
      <div className="license-plate-ind h-full justify-center">
        <span>IND</span>
      </div>
      <span className="font-mono text-slate-900 font-extrabold pr-2 tracking-wider">
        {plate || 'UNKNOWN'}
      </span>
      {isFlagged && (
        <span className="mr-1 w-2 h-2 rounded-full bg-rose-600 animate-ping" />
      )}
    </div>
  );
};
