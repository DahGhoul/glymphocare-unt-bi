import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';

interface EChartBoxProps {
  title: string;
  subtitle?: string;
  option: EChartsOption;
  height?: number;
  provenance?: string;
  rightBadge?: React.ReactNode;
}

export const EChartBox: React.FC<EChartBoxProps> = ({
  title,
  subtitle,
  option,
  height = 300,
  provenance,
  rightBadge,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current, undefined, { renderer: 'canvas' });
    chartRef.current = chart;

    const ro = new ResizeObserver(() => {
      chart.resize();
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.setOption(
        {
          textStyle: { fontFamily: 'IBM Plex Sans, sans-serif', color: '#14202B' },
          ...option,
        },
        true
      );
    }
  }, [option]);

  return (
    <div className="bg-white border border-[#dce2ea] rounded-lg p-4 flex flex-col">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div>
          <h3 className="text-[14px] font-semibold text-[#14202b] leading-snug">{title}</h3>
          {subtitle && <p className="text-[12px] text-[#5a6877] mt-0.5">{subtitle}</p>}
        </div>
        {rightBadge}
      </div>
      <div ref={containerRef} style={{ width: '100%', height: `${height}px` }} />
      {provenance && (
        <div className="mt-2 pt-2 border-t border-[#eef2f6] text-[11px] text-[#5a6877] font-mono-num">
          {provenance}
        </div>
      )}
    </div>
  );
};
