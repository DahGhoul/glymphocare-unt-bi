import React, { useEffect, useState } from 'react';
import { Database, FileDown, FileSpreadsheet, Play } from 'lucide-react';
import { ClinicalReportTable } from '../components/ClinicalReportTable';
import { FilterBar } from '../components/FilterBar';
import { useFilters } from '../context/FilterContext';
import { apiDownload, apiFetch, filtersToQuery } from '../services/api';
import type { ReportData } from '../types/glympho';

const REPORT_TABS = [
  { id: 'cohorte', label: '1 · Cohorte (RR-03)' },
  { id: 'dias_semana', label: '2 · Días de la semana' },
  { id: 'habitos', label: '3 · Hábitos vs KPIs (RR-06)' },
  { id: 'sql_evidence', label: '4 · Evidencia SQL (Data Mart)' },
];

interface SqlQuerySpec {
  id: string;
  title: string;
  description: string;
  sql: string;
}

interface SqlRunResult {
  query_id: string;
  title: string;
  sql: string;
  columns: string[];
  rows: Record<string, any>[];
  row_count: number;
  elapsed_ms: number;
  engine: string;
}

export const ReportsPage: React.FC = () => {
  const { filters } = useFilters();
  const [activeTab, setActiveTab] = useState<'cohorte' | 'dias_semana' | 'habitos' | 'sql_evidence'>('cohorte');
  const [report, setReport] = useState<ReportData | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [exporting, setExporting] = useState(false);

  const [sqlQueries, setSqlQueries] = useState<SqlQuerySpec[]>([]);
  const [selectedQueryId, setSelectedQueryId] = useState('q1_kpis');
  const [sqlResult, setSqlResult] = useState<SqlRunResult | null>(null);
  const [sqlRunning, setSqlRunning] = useState(false);

  const loadReport = () => {
    if (activeTab === 'sql_evidence') return;
    apiFetch<ReportData>(`/api/reports/preview/${activeTab}${filtersToQuery(filters)}`).then(setReport);
  };

  const loadHistory = () => {
    apiFetch<any[]>('/api/reports/history').then(setHistory).catch(() => {});
  };

  useEffect(() => {
    loadReport();
  }, [activeTab, filters]);

  useEffect(() => {
    loadHistory();
    apiFetch<SqlQuerySpec[]>('/api/reports/sql-evidence').then(setSqlQueries).catch(() => {});
  }, []);

  const handleRunSql = async (qid?: string) => {
    const id = qid || selectedQueryId;
    setSqlRunning(true);
    try {
      const res = await apiFetch<SqlRunResult>('/api/reports/sql-evidence/run', {
        method: 'POST',
        body: JSON.stringify({ query_id: id }),
      });
      setSqlResult(res);
    } finally {
      setSqlRunning(false);
    }
  };

  const handleExport = async (format: 'pdf' | 'csv') => {
    if (activeTab === 'sql_evidence') return;
    setExporting(true);
    try {
      await apiDownload(
        '/api/reports/export',
        {
          method: 'POST',
          body: JSON.stringify({ report_type: activeTab, format, filters }),
        },
        `glymphocare_${activeTab}.${format}`
      );
      loadHistory();
    } finally {
      setExporting(false);
    }
  };

  const activeSqlSpec = sqlQueries.find((q) => q.id === selectedQueryId);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <h1 className="text-[20px] font-bold text-[#14202b]">Reportes Oficiales, Evidencia SQL y Exportación</h1>
          <p className="text-[13px] text-[#5a6877]">
            Tablas clínicas conectadas en vivo al Data Mart (glympho_dw), consultas SQL demostrables en Amazon RDS y exportación PDF/CSV.
          </p>
        </div>
        {activeTab !== 'sql_evidence' && (
          <div className="flex gap-2">
            <button
              type="button"
              disabled={exporting}
              onClick={() => handleExport('pdf')}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded bg-[#0f766e] hover:bg-[#0d625b] text-white text-[13px] font-semibold cursor-pointer disabled:opacity-50"
            >
              <FileDown size={15} />
              Exportar PDF
            </button>
            <button
              type="button"
              disabled={exporting}
              onClick={() => handleExport('csv')}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded border border-[#dce2ea] bg-white hover:bg-[#f8fafc] text-[#14202b] text-[13px] font-medium cursor-pointer disabled:opacity-50"
            >
              <FileSpreadsheet size={15} />
              Exportar CSV
            </button>
          </div>
        )}
      </div>

      {activeTab !== 'sql_evidence' && <FilterBar />}

      <div className="flex flex-wrap gap-2 mb-4">
        {REPORT_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => {
              const next = t.id as 'cohorte' | 'dias_semana' | 'habitos' | 'sql_evidence';
              setActiveTab(next);
              if (next === 'sql_evidence' && !sqlResult) {
                handleRunSql(selectedQueryId);
              }
            }}
            className={`px-4 py-1.5 rounded-full text-[13px] font-medium border cursor-pointer ${
              activeTab === t.id
                ? 'bg-[#0f766e] border-[#0f766e] text-white'
                : 'bg-white border-[#dce2ea] text-[#14202b] hover:bg-[#f8fafc]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'sql_evidence' ? (
        <div className="bg-white border border-[#dce2ea] rounded-lg p-4 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Database size={16} className="text-[#0f766e]" />
              <select
                value={selectedQueryId}
                onChange={(e) => {
                  setSelectedQueryId(e.target.value);
                  handleRunSql(e.target.value);
                }}
                className="text-[13px] font-medium border border-[#dce2ea] rounded px-3 py-1.5 bg-[#f8fafc]"
              >
                {sqlQueries.map((q) => (
                  <option key={q.id} value={q.id}>{q.title}</option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={() => handleRunSql()}
              disabled={sqlRunning}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded bg-[#0f766e] text-white text-[13px] font-semibold cursor-pointer disabled:opacity-60"
            >
              <Play size={14} />
              {sqlRunning ? 'Consultando RDS...' : 'Ejecutar consulta en Amazon RDS'}
            </button>
          </div>

          {activeSqlSpec && (
            <div>
              <p className="text-[12.5px] text-[#5a6877] mb-2">{activeSqlSpec.description}</p>
              <pre className="p-3 rounded bg-[#14202b] text-[#e2e8f0] text-[11.5px] font-mono-num overflow-x-auto leading-relaxed">
                {activeSqlSpec.sql}
              </pre>
            </div>
          )}

          {sqlResult && (
            <div>
              <div className="flex flex-wrap items-center justify-between gap-2 text-[12px] text-[#5a6877] mb-2 font-mono-num">
                <span>Motor: <strong className="text-[#14202b]">{sqlResult.engine}</strong></span>
                <span>Filas: <strong className="text-[#14202b]">{sqlResult.row_count}</strong> · Tiempo: <strong className="text-[#0f766e]">{sqlResult.elapsed_ms} ms</strong></span>
              </div>
              <div className="overflow-x-auto border border-[#dce2ea] rounded">
                <table className="w-full text-[12.5px] border-collapse">
                  <thead>
                    <tr className="bg-[#0f766e] text-white text-left">
                      {sqlResult.columns.map((c) => (
                        <th key={c} className="px-3 py-2 font-mono-num text-[11.5px] whitespace-nowrap">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sqlResult.rows.map((r, idx) => (
                      <tr key={idx} className="border-b border-[#eef2f6] odd:bg-white even:bg-[#f8fafc]">
                        {sqlResult.columns.map((c) => (
                          <td key={c} className="px-3 py-1.5 font-mono-num whitespace-nowrap">
                            {r[c] ?? '–'}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : (
        report && <ClinicalReportTable report={report} />
      )}

      <div className="mt-4 bg-white border border-[#dce2ea] rounded-lg p-4">
        <h3 className="text-[14px] font-semibold text-[#14202b] mb-2">Historial de Exportaciones (reporte_generado)</h3>
        {history.length === 0 ? (
          <p className="text-[12px] text-[#5a6877]">Aún no se han generado descargas en esta sesión.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px] border-collapse">
              <thead>
                <tr className="border-b border-[#dce2ea] text-left text-[11px] uppercase text-[#5a6877]">
                  <th className="py-1.5 pr-3">Fecha</th>
                  <th className="py-1.5 pr-3">Reporte</th>
                  <th className="py-1.5 pr-3">Formato</th>
                  <th className="py-1.5">Generado por</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id} className="border-b border-[#f1f5f9]">
                    <td className="py-1.5 pr-3 font-mono-num">{h.fecha.slice(0, 19).replace('T', ' ')}</td>
                    <td className="py-1.5 pr-3">{h.tipo}</td>
                    <td className="py-1.5 pr-3 uppercase font-mono-num">{h.formato}</td>
                    <td className="py-1.5 text-[#5a6877]">{h.generado_por}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
