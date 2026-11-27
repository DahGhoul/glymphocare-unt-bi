import React from 'react';

interface KpiCardProps {
  label: string;
  value: string | number | null | undefined;
  unit?: string;
  thresholdLabel: string;
  status: 'good' | 'warn' | 'bad' | 'neutral';
  detail?: string;
}

const STATUS_STYLE = {
  good: 'text-[#15803d] bg-[#ecfdf5] border-[#bbf7d0]',
  warn: 'text-[#b45309] bg-[#fffbeb] border-[#fde68a]',
  bad: 'text-[#b91c1c] bg-[#fef2f2] border-[#fecaca]',
  neutral: 'text-[#3b4990] bg-[#eef2ff] border-[#c7d2fe]',
};

export const KpiCard: React.FC<KpiCardProps> = ({
  label,
  value,
  unit,
  thresholdLabel,
  status,
  detail,
}) => {
  return (
    <div className="bg-white border border-[#dce2ea] rounded-lg p-4 flex flex-col justify-between">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-medium text-[#5a6877] uppercase tracking-wide">
          {label}
        </span>
        <span className={`text-[11px] font-medium px-2 py-0.5 rounded border ${STATUS_STYLE[status]}`}>
          {thresholdLabel}
        </span>
      </div>
      <div className="mt-2.5 flex items-baseline gap-1.5">
        <span className="text-[26px] font-semibold text-[#14202b] font-mono-num leading-none">
          {value ?? '–'}
        </span>
        {unit && <span className="text-[13px] text-[#5a6877] font-mono-num">{unit}</span>}
      </div>
      {detail && <p className="mt-2 text-[12px] text-[#5a6877] leading-snug">{detail}</p>}
    </div>
  );
};
