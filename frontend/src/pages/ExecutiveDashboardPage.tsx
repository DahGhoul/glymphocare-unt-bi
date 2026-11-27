import React, { useEffect, useState } from 'react';
import { AlertTriangle, Sparkles } from 'lucide-react';
import { EChartBox } from '../components/EChartBox';
import { FilterBar } from '../components/FilterBar';
import { KpiCard } from '../components/KpiCard';
import { useFilters } from '../context/FilterContext';
import { apiFetch, filtersToQuery } from '../services/api';
import type { AiInterpretation, RuleAlert } from '../types/glympho';

interface ExecutiveResponse {
  n_participantes: number;
  n_noches: number;
  kpis: {
    PSQI: number | null;
    ESS: number | null;
    SE: number | null;
    SOL: number | null;
    WASO: number | null;
    TST: number | null;
    PCT_N3: number | null;
    DESPERTARES: number | null;
    pct_malos_dormidores: number;
    buenos_dormidores: number;
    malos_dormidores: number;
    indice_glinfatico: number | null;
  };
  trend_nights: { fecha: string; se_pct: number; pct_n3: number; tst_h: number }[];
  distribution: { name: string; value: number }[];
  heatmap: { facultad: string; dia_num: number; dia: string; pct_n3: number; tst_min: number }[];
  alerts: RuleAlert[];
}

export const ExecutiveDashboardPage: React.FC = () => {
  const { filters } = useFilters();
  const [data, setData] = useState<ExecutiveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [ai, setAi] = useState<AiInterpretation | null>(null);
  const [aiBusy, setAiBusy] = useState(false);

  useEffect(() => {
    setLoading(true);
    apiFetch<ExecutiveResponse>(`/api/dashboard/executive${filtersToQuery(filters)}`)
      .then(setData)
      .finally(() => setLoading(false));
  }, [filters]);

  const handleCohortAi = async () => {
    setAiBusy(true);
    try {
      const res = await apiFetch<AiInterpretation>('/api/ai/interpret', {
        method: 'POST',
        body: JSON.stringify({ scope: 'cohort' }),
      });
      setAi(res);
    } finally {
      setAiBusy(false);
    }
  };

  const k = data?.kpis;
  const tstHours = k?.TST != null ? (k.TST / 60).toFixed(2) : '–';

  const daysOrder = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo'];
  const faculties = Array.from(new Set((data?.heatmap || []).map((h) => h.facultad)));
  const heatData = (data?.heatmap || []).map((h) => [
    daysOrder.indexOf(h.dia),
    faculties.indexOf(h.facultad),
    h.pct_n3,
  ]);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-2 mb-4">
        <div>
          <h1 className="text-[20px] font-bold text-[#14202b]">Dashboard Ejecutivo de Cohorte</h1>
          <p className="text-[13px] text-[#5a6877]">
            Síntesis integrada de percepción subjetiva (PSQI, ESS) y arquitectura nocturna objetiva.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="text-[12px] font-mono-num text-[#5a6877] bg-white border border-[#dce2ea] rounded px-3 py-1.5">
            Participantes: <strong className="text-[#14202b]">{data?.n_participantes ?? '–'}</strong> · Noches:{' '}
            <strong className="text-[#14202b]">{data?.n_noches ?? '–'}</strong>
          </div>
          <button
            type="button"
            onClick={handleCohortAi}
            disabled={aiBusy}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#3b4990] hover:bg-[#313d7a] text-white text-[12.5px] font-semibold cursor-pointer disabled:opacity-60"
          >
            <Sparkles size={14} />
            {aiBusy ? 'Analizando cohorte...' : 'Interpretar cohorte con IA'}
          </button>
        </div>
      </div>

      <FilterBar />

      {ai && (
        <div className="bg-white border border-[#3b4990]/40 rounded-lg p-4 mb-4">
          <div className="flex flex-wrap items-center justify-between gap-2 pb-2 mb-2.5 border-b border-[#eef2f6]">
            <h3 className="text-[14px] font-bold text-[#14202b]">Interpretación Ejecutiva de Cohorte (IA Generativa)</h3>
            <span className="text-[11px] font-mono-num px-2 py-0.5 rounded bg-[#eef2ff] text-[#3b4990]">
              {ai.provider_used}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[12.5px] text-[#334155]">
            <div>
              <strong className="text-[#14202b]">Resumen:</strong> {ai.resumen_ejecutivo}
              <div className="mt-2"><strong className="text-[#14202b]">Componentes críticos:</strong> {ai.componentes_criticos}</div>
            </div>
            <div>
              <strong className="text-[#14202b]">Limpieza glinfática (%N3):</strong> {ai.analisis_glinfatico_n3}
              <ul className="list-disc pl-4 mt-1.5 space-y-0.5">
                {ai.plan_accion.map((a, idx) => <li key={idx}>{a}</li>)}
              </ul>
            </div>
          </div>
          <p className="mt-2 text-[11px] text-[#5a6877]">{ai.aviso_no_clinico}</p>
        </div>
      )}

      {loading && !data ? (
        <div className="bg-white border border-[#dce2ea] rounded-lg p-8 text-center text-[13px] text-[#5a6877]">
          Consultando Data Mart en PostgreSQL...
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
            <KpiCard
              label="PSQI Promedio"
              value={k?.PSQI?.toFixed(2)}
              unit="/ 21"
              thresholdLabel="Meta <= 5"
              status={(k?.PSQI ?? 0) > 5 ? 'bad' : 'good'}
              detail={`${k?.pct_malos_dormidores ?? 0}% clasificados como mal dormidor`}
            />
            <KpiCard
              label="ESS Somnolencia"
              value={k?.ESS?.toFixed(2)}
              unit="/ 24"
              thresholdLabel="Meta <= 10"
              status={(k?.ESS ?? 0) > 10 ? 'warn' : 'good'}
              detail="Escala de somnolencia diurna Epworth"
            />
            <KpiCard
              label="Eficiencia (SE)"
              value={k?.SE?.toFixed(1)}
              unit="%"
              thresholdLabel="Meta >= 85%"
              status={(k?.SE ?? 0) >= 85 ? 'good' : 'warn'}
              detail={`SOL ${k?.SOL?.toFixed(1) ?? '–'} min · WASO ${k?.WASO?.toFixed(1) ?? '–'} min`}
            />
            <KpiCard
              label="Duración (TST)"
              value={tstHours}
              unit="h/noche"
              thresholdLabel="Meta >= 7.0 h"
              status={(k?.TST ?? 0) >= 420 ? 'good' : 'bad'}
              detail={`Despertares prom.: ${k?.DESPERTARES?.toFixed(1) ?? '–'} / noche`}
            />
            <KpiCard
              label="Sueño Profundo (%N3)"
              value={k?.PCT_N3?.toFixed(1)}
              unit="%"
              thresholdLabel="Ventana glinfática"
              status={(k?.PCT_N3 ?? 0) >= 15 ? 'neutral' : 'warn'}
              detail={`Índice Glinfático derivado: ${k?.indice_glinfatico?.toFixed(3) ?? '–'}`}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            <div className="lg:col-span-2">
              <EChartBox
                title="Tendencia Diaria de Continuidad y Sueño Profundo"
                subtitle="Evolución de Eficiencia del Sueño (SE %) y %N3 por noche registrada"
                height={300}
                provenance={`Fuente: glympho_dw.fact_sueno_noche · n = ${data?.n_noches ?? 0} noches`}
                option={{
                  tooltip: { trigger: 'axis' },
                  legend: { data: ['Eficiencia SE (%)', 'Sueño Profundo (%N3)'], bottom: 0, textStyle: { fontSize: 12 } },
                  grid: { left: 45, right: 45, top: 20, bottom: 45 },
                  xAxis: {
                    type: 'category',
                    data: (data?.trend_nights || []).map((t) => t.fecha.slice(5)),
                    axisLine: { lineStyle: { color: '#cbd5e1' } },
                  },
                  yAxis: [
                    { type: 'value', name: 'SE %', min: 70, max: 100, splitLine: { lineStyle: { color: '#f1f5f9' } } },
                    { type: 'value', name: '%N3', min: 8, max: 28, splitLine: { show: false } },
                  ],
                  series: [
                    {
                      name: 'Eficiencia SE (%)',
                      type: 'line',
                      smooth: true,
                      data: (data?.trend_nights || []).map((t) => t.se_pct),
                      itemStyle: { color: '#0f766e' },
                      lineStyle: { width: 2 },
                    },
                    {
                      name: 'Sueño Profundo (%N3)',
                      type: 'line',
                      yAxisIndex: 1,
                      smooth: true,
                      data: (data?.trend_nights || []).map((t) => t.pct_n3),
                      itemStyle: { color: '#3b4990' },
                      lineStyle: { width: 2 },
                    },
                  ],
                }}
              />
            </div>

            <EChartBox
              title="Distribución de Calidad Subjetiva"
              subtitle="Clasificación según último PSQI del período"
              height={300}
              provenance={`Fuente: glympho_dw.fact_cuestionario · n = ${data?.n_participantes ?? 0} estudiantes`}
              option={{
                tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
                legend: { bottom: 0, textStyle: { fontSize: 12 } },
                series: [
                  {
                    type: 'pie',
                    radius: ['48%', '74%'],
                    center: ['50%', '44%'],
                    label: { show: false },
                    color: ['#0f766e', '#b91c1c'],
                    data: data?.distribution || [],
                  },
                ],
              }}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <EChartBox
                title="Mapa de Calor: %N3 por Facultad y Día de la Semana"
                subtitle="Identifica qué días de la semana académica reducen la ventana de limpieza cerebral"
                height={250}
                provenance="Fuente: glympho_dw.fact_sueno_noche × dim_carrera × dim_tiempo"
                option={{
                  tooltip: {
                    position: 'top',
                    formatter: (p: unknown) => {
                      const d = (p as { data: number[] }).data;
                      return `${faculties[d[1]]} · ${daysOrder[d[0]]}: <b>${d[2]}% N3</b>`;
                    },
                  },
                  grid: { top: 15, bottom: 35, left: 150, right: 20 },
                  xAxis: { type: 'category', data: daysOrder.map((d) => d.slice(0, 3)), splitArea: { show: true } },
                  yAxis: { type: 'category', data: faculties, splitArea: { show: true } },
                  visualMap: {
                    min: 12,
                    max: 22,
                    calculable: false,
                    orient: 'horizontal',
                    left: 'center',
                    bottom: 0,
                    inRange: { color: ['#fee2e2', '#e0f2fe', '#3b4990'] },
                    show: false,
                  },
                  series: [
                    {
                      type: 'heatmap',
                      data: heatData,
                      label: { show: true, formatter: '{@[2]}%', fontSize: 11 },
                    },
                  ],
                }}
              />
            </div>

            <div className="bg-white border border-[#dce2ea] rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={16} className="text-[#b45309]" />
                <h3 className="text-[14px] font-semibold text-[#14202b]">Alertas Activas de Cohorte</h3>
              </div>
              <div className="space-y-2.5 max-h-[225px] overflow-y-auto pr-1">
                {(data?.alerts || []).length === 0 ? (
                  <p className="text-[12px] text-[#15803d] bg-[#ecfdf5] p-3 rounded border border-[#bbf7d0]">
                    Todos los indicadores agregados de la selección se mantienen dentro de meta.
                  </p>
                ) : (
                  data?.alerts.map((a) => (
                    <div
                      key={a.rule_id}
                      className={`p-2.5 rounded border text-[12px] ${
                        a.severidad === 'critico'
                          ? 'bg-[#fef2f2] border-[#fecaca]'
                          : 'bg-[#fffbeb] border-[#fde68a]'
                      }`}
                    >
                      <div className="font-semibold text-[#14202b] flex items-center justify-between gap-2">
                        <span>{a.titulo}</span>
                        <span className="font-mono-num text-[11px]">{a.valor_actual}</span>
                      </div>
                      <p className="text-[#334155] mt-1 leading-snug">{a.texto_recomendacion}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
