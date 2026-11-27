import React, { useEffect, useState } from 'react';
import { EChartBox } from '../components/EChartBox';
import { FilterBar } from '../components/FilterBar';
import { useFilters } from '../context/FilterContext';
import { apiFetch, filtersToQuery } from '../services/api';

interface HabitsResponse {
  n_participantes: number;
  matrix: {
    habits: string[];
    kpis: string[];
    cells: { habit_index: number; kpi_index: number; habit: string; kpi: string; r: number | null; p_value: number | null }[];
  };
  findings: { titulo: string; descripcion: string; diferencia: number; unidad: string; p_value: number; significativo: boolean }[];
  comparisons: {
    pantallas_sol: { label: string; n: number; mean: number; boxplot: number[] }[];
    cafeina_psqi: { label: string; n: number; mean: number; boxplot: number[] }[];
    ejercicio_n3: { label: string; n: number; mean: number; boxplot: number[] }[];
    estres_waso: { label: string; n: number; mean: number; boxplot: number[] }[];
  };
}

export const HabitsCorrelationPage: React.FC = () => {
  const { filters } = useFilters();
  const [data, setData] = useState<HabitsResponse | null>(null);

  useEffect(() => {
    apiFetch<HabitsResponse>(`/api/dashboard/habits${filtersToQuery(filters)}`).then(setData);
  }, [filters]);

  const cells = (data?.matrix.cells || []).map((c) => [c.kpi_index, c.habit_index, c.r ?? 0]);

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-[20px] font-bold text-[#14202b]">Hábitos de Higiene y Correlaciones</h1>
        <p className="text-[13px] text-[#5a6877]">
          Correlaciones de Pearson y hallazgos estadísticos automáticos calculados en tiempo real sobre la cohorte.
        </p>
      </div>

      <FilterBar />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-2">
          <EChartBox
            title="Matriz de Correlación Real (Coeficiente r de Pearson)"
            subtitle="Relación entre exposición a hábitos y los 6 indicadores principales"
            height={320}
            provenance={`Fuente: scipy.stats.pearsonr sobre glympho_dw · n = ${data?.n_participantes ?? 0}`}
            option={{
              tooltip: {
                formatter: (p: unknown) => {
                  const d = (p as { data: number[] }).data;
                  const cell = data?.matrix.cells.find((c) => c.kpi_index === d[0] && c.habit_index === d[1]);
                  return `${cell?.habit} × ${cell?.kpi}<br/>r = <b>${cell?.r}</b> (p = ${cell?.p_value})`;
                },
              },
              grid: { top: 20, bottom: 45, left: 130, right: 20 },
              xAxis: { type: 'category', data: data?.matrix.kpis || [], splitArea: { show: true } },
              yAxis: { type: 'category', data: data?.matrix.habits || [], splitArea: { show: true } },
              visualMap: {
                min: -0.7,
                max: 0.7,
                orient: 'horizontal',
                left: 'center',
                bottom: 0,
                inRange: { color: ['#1d4ed8', '#f8fafc', '#b91c1c'] },
                show: false,
              },
              series: [
                {
                  type: 'heatmap',
                  data: cells,
                  label: { show: true, fontSize: 11 },
                },
              ],
            }}
          />
        </div>

        <div className="bg-white border border-[#dce2ea] rounded-lg p-4">
          <h3 className="text-[14px] font-semibold text-[#14202b] mb-1">
            Hallazgos Estadísticos Automáticos (RF-07)
          </h3>
          <p className="text-[12px] text-[#5a6877] mb-3">
            Calculados dinámicamente mediante prueba t de Welch sobre la muestra filtrada.
          </p>
          <div className="space-y-2.5">
            {(data?.findings || []).map((f) => (
              <div key={f.titulo} className="p-2.5 rounded border border-[#dce2ea] bg-[#f8fafc]">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[12.5px] font-semibold text-[#14202b]">{f.titulo}</span>
                  <span
                    className={`text-[11px] font-mono-num px-1.5 py-0.5 rounded border ${
                      f.significativo
                        ? 'bg-[#e6f4f3] text-[#0f766e] border-[#99f6e4]'
                        : 'bg-white text-[#5a6877] border-[#dce2ea]'
                    }`}
                  >
                    p={f.p_value}
                  </span>
                </div>
                <p className="text-[12px] text-[#334155] mt-1 leading-snug">{f.descripcion}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <EChartBox
          title="Pantallas antes de dormir vs. Latencia SOL (min)"
          subtitle="Promedio de minutos para conciliar el sueño"
          height={250}
          provenance="Fuente: glympho_dw.fact_sueno_noche × dim_habito"
          option={{
            tooltip: { trigger: 'axis' },
            grid: { left: 45, right: 20, top: 20, bottom: 35 },
            xAxis: { type: 'category', data: (data?.comparisons.pantallas_sol || []).map((c) => c.label) },
            yAxis: { type: 'value', name: 'min' },
            series: [
              {
                type: 'bar',
                barWidth: '42%',
                data: (data?.comparisons.pantallas_sol || []).map((c) => ({
                  value: c.mean,
                  itemStyle: { color: c.mean > 20 ? '#b91c1c' : '#0f766e' },
                })),
                label: { show: true, position: 'top', formatter: '{c} min' },
              },
            ],
          }}
        />

        <EChartBox
          title="Ejercicio físico semanal vs. Sueño Profundo (%N3)"
          subtitle="Impacto en la proporción de ondas lentas N3"
          height={250}
          provenance="Fuente: glympho_dw.fact_sueno_noche × dim_habito"
          option={{
            tooltip: { trigger: 'axis' },
            grid: { left: 45, right: 20, top: 20, bottom: 35 },
            xAxis: { type: 'category', data: (data?.comparisons.ejercicio_n3 || []).map((c) => c.label) },
            yAxis: { type: 'value', name: '%N3' },
            series: [
              {
                type: 'bar',
                barWidth: '42%',
                data: (data?.comparisons.ejercicio_n3 || []).map((c) => ({
                  value: c.mean,
                  itemStyle: { color: c.label.includes('>=') ? '#3b4990' : '#94a3b8' },
                })),
                label: { show: true, position: 'top', formatter: '{c}%' },
              },
            ],
          }}
        />
      </div>
    </div>
  );
};
