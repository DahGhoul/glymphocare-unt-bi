import React from 'react';
import type { ReportData } from '../types/glympho';

function formatVal(val: number, dec: number): string {
  if (val === 0 && dec === 0) return '–';
  return val.toFixed(dec);
}

export const ClinicalReportTable: React.FC<{ report: ReportData }> = ({ report }) => {
  const { columns, group_start, group_span, group_header, rows, decimals } = report;

  return (
    <div className="bg-white border border-[#dce2ea] rounded-lg p-4">
      <div className="flex flex-wrap items-start justify-between gap-2 pb-3 mb-3 border-b border-[#e2e8f0]">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#0f766e]">
            GlymphoCare · UNT Ingeniería de Sistemas
          </span>
          <h3 className="text-[15px] font-bold text-[#14202b] mt-0.5">{report.title}</h3>
          <p className="text-[12px] text-[#5a6877]">{report.subtitle}</p>
        </div>
        <div className="text-right text-[12px] text-[#5a6877] font-mono-num">
          <div>Unidad: {report.unit}</div>
          <div>Muestra activa: n = {report.n_sample}</div>
        </div>
      </div>

      <div className="clinical-table-wrap">
        <table className="clinical-table">
          <thead>
            <tr>
              <th rowSpan={2}>Categoría / Segmento</th>
              {columns.map((col, idx) => {
                if (idx < group_start || idx >= group_start + group_span) {
                  return (
                    <th key={col} rowSpan={2}>
                      {col}
                    </th>
                  );
                }
                if (idx === group_start) {
                  return (
                    <th key="grp" className="group-head" colSpan={group_span}>
                      {group_header}
                    </th>
                  );
                }
                return null;
              })}
            </tr>
            <tr>
              {columns.slice(group_start, group_start + group_span).map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => {
              if (row.type === 'group') {
                return (
                  <tr key={idx} className="row-group">
                    <td colSpan={columns.length + 1}>{row.label}</td>
                  </tr>
                );
              }
              const cls =
                row.type === 'subtotal'
                  ? 'row-subtotal'
                  : row.type === 'total'
                  ? 'row-total'
                  : 'row-item';
              return (
                <tr key={idx} className={cls}>
                  <td>{row.label}</td>
                  {row.values.map((v, cIdx) => (
                    <td key={cIdx} className={row.bad?.[cIdx] ? 'cell-bad' : ''}>
                      {formatVal(v, decimals[cIdx] ?? 1)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[12px] text-[#5a6877] leading-relaxed">{report.note}</p>
    </div>
  );
};
