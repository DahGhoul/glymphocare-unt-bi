import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { EChartBox } from '../components/EChartBox';
import { FilterBar } from '../components/FilterBar';
import { useFilters } from '../context/FilterContext';
import { apiFetch, filtersToQuery } from '../services/api';

interface SubjectiveResponse {
  n_participantes: number;
  radar: { component: string; cohorte: number; ideal: number }[];
  faculty_summary: { facultad: string; psqi_prom: number; n: number; boxplot: number[] }[];
  longitudinal: { periodo: string; psqi_prom: number; ess_prom: number; n: number }[];
  top_risk: {
    codigo: string;
    facultad: string;
    carrera: string;
    ciclo: number;
    edad: number;
    psqi_global: number;
    ess_total: number;
    clasificacion_psqi: string;
    fecha_eval: string;
  }[];
}

export const SubjectiveQualityPage: React.FC = () => {
  const { filters } = useFilters();
  const [data, setData] = useState<SubjectiveResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<SubjectiveResponse>(`/api/dashboard/subjective${filtersToQuery(filters)}`)
      .then(setData)
      .finally(() => setLoading(false));
  }, [filters]);

  const hasData = !!data && data.radar.length > 0;

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-[20px] font-bold text-[#14202b]">Calidad Subjetiva del Sueño (PSQI y ESS)</h1>
        <p className="text-[13px] text-[#5a6877]">
          Desglose de los 7 componentes clínicos de Pittsburgh (0–3 cada uno) y somnolencia diurna de Epworth.
        </p>
      </div>

      <FilterBar />

      {loading && !data ? (
        <div className="bg-white border border-[#dce2ea] rounded-lg p-8 text-center text-[13px] text-[#5a6877]">
          Cargando análisis PSQI y ESS desde el Data Mart...
        </div>
      ) : !hasData ? (
        <div className="bg-white border border-[#dce2ea] rounded-lg p-8 text-center text-[13px] text-[#5a6877]">
          Sin evaluaciones subjetivas para los filtros seleccionados.
        </div>
      ) : (
      <>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <EChartBox
          title="Radar de los 7 Componentes del PSQI"
          subtitle="Puntuación promedio de la cohorte (mayor valor = mayor alteración)"
          height={330}
          provenance={`Fuente: glympho_dw.fact_cuestionario · n = ${data?.n_participantes ?? 0}`}
          option={{
            tooltip: {},
            legend: { data: ['Cohorte actual', 'Referencia óptima'], bottom: 0 },
            radar: {
              indicator: (data?.radar || []).map((r) => ({ name: r.component, max: 3 })),
              radius: '62%',
              splitArea: { areaStyle: { color: ['#ffffff', '#f8fafc'] } },
            },
            series: [
              {
                type: 'radar',
                data: [
                  {
                    value: (data?.radar || []).map((r) => r.cohorte),
                    name: 'Cohorte actual',
                    areaStyle: { color: 'rgba(15, 118, 110, 0.22)' },
                    itemStyle: { color: '#0f766e' },
                  },
                  {
                    value: (data?.radar || []).map((r) => r.ideal),
                    name: 'Referencia óptima',
                    lineStyle: { type: 'dashed', color: '#64748b' },
                    itemStyle: { color: '#64748b' },
                  },
                ],
              },
            ],
          }}
        />

        <EChartBox
          title="Distribución de PSQI Global por Facultad (Boxplot)"
          subtitle="Mínimo, Q1, Mediana, Q3 y Máximo (umbral buena calidad <= 5)"
          height={330}
          provenance="Fuente: glympho_dw.fact_cuestionario × dim_carrera"
          option={{
            tooltip: { trigger: 'item' },
            grid: { left: 45, right: 20, top: 20, bottom: 40 },
            xAxis: { type: 'category', data: (data?.faculty_summary || []).map((f) => f.facultad) },
            yAxis: { type: 'value', name: 'PSQI (0-21)', min: 0, max: 21 },
            series: [
              {
                type: 'boxplot',
                data: (data?.faculty_summary || []).map((f) => f.boxplot),
                itemStyle: { color: '#e6f4f3', borderColor: '#0f766e', borderWidth: 2 },
              },
            ],
          }}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <EChartBox
          title="Evolución Mensual PSQI y ESS"
          subtitle="Seguimiento longitudinal de evaluaciones"
          height={290}
          provenance="Fuente: glympho_dw.fact_cuestionario"
          option={{
            tooltip: { trigger: 'axis' },
            legend: { data: ['PSQI Global', 'ESS Somnolencia'], bottom: 0 },
            grid: { left: 40, right: 20, top: 20, bottom: 45 },
            xAxis: { type: 'category', data: (data?.longitudinal || []).map((l) => l.periodo) },
            yAxis: { type: 'value' },
            series: [
              { name: 'PSQI Global', type: 'line', data: (data?.longitudinal || []).map((l) => l.psqi_prom), itemStyle: { color: '#0f766e' } },
              { name: 'ESS Somnolencia', type: 'line', data: (data?.longitudinal || []).map((l) => l.ess_prom), itemStyle: { color: '#3b4990' } },
            ],
          }}
        />

        <div className="lg:col-span-2 bg-white border border-[#dce2ea] rounded-lg p-4">
          <h3 className="text-[14px] font-semibold text-[#14202b] mb-1">
            Participantes con Mayor Alteración Subjetiva (Top 10 PSQI)
          </h3>
          <p className="text-[12px] text-[#5a6877] mb-3">
            Haz clic en cualquier código anonimizado para inspeccionar su perfil nocturno y recomendaciones.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px] border-collapse">
              <thead>
                <tr className="border-b border-[#dce2ea] text-left text-[11px] uppercase text-[#5a6877]">
                  <th className="py-2 pr-3">Código</th>
                  <th className="py-2 pr-3">Carrera</th>
                  <th className="py-2 pr-3 text-right">Ciclo</th>
                  <th className="py-2 pr-3 text-right">PSQI</th>
                  <th className="py-2 pr-3 text-right">ESS</th>
                  <th className="py-2 pr-3">Clasificación</th>
                  <th className="py-2 text-right">Acción</th>
                </tr>
              </thead>
              <tbody>
                {(data?.top_risk || []).map((r) => (
                  <tr key={r.codigo} className="border-b border-[#f1f5f9] hover:bg-[#f8fafc]">
                    <td className="py-2 pr-3 font-mono-num font-semibold text-[#14202b]">{r.codigo}</td>
                    <td className="py-2 pr-3 text-[#334155]">{r.carrera}</td>
                    <td className="py-2 pr-3 text-right font-mono-num">{r.ciclo}</td>
                    <td className="py-2 pr-3 text-right font-mono-num font-bold text-[#b91c1c]">{r.psqi_global}</td>
                    <td className="py-2 pr-3 text-right font-mono-num">{r.ess_total}</td>
                    <td className="py-2 pr-3">
                      <span className="text-[11px] px-2 py-0.5 rounded bg-[#fef2f2] text-[#b91c1c] border border-[#fecaca]">
                        {r.clasificacion_psqi}
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      <Link
                        to={`/participantes?codigo=${r.codigo}`}
                        className="text-[12px] font-medium text-[#0f766e] hover:underline"
                      >
                        Ver perfil
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      </>
      )}
    </div>
  );
};
