import React, { useEffect, useState } from 'react';
import { BookOpen, Clock, SlidersHorizontal } from 'lucide-react';
import { EChartBox } from '../components/EChartBox';
import { FilterBar } from '../components/FilterBar';
import { KpiCard } from '../components/KpiCard';
import { useFilters } from '../context/FilterContext';
import { apiFetch, filtersToQuery } from '../services/api';

interface SimResult {
  n_referencia: number;
  linea_base: { sol_min: number; waso_min: number; tst_min: number; se_pct: number; pct_n3: number; psqi: number };
  proyeccion: { sol_min: number; waso_min: number; tst_min: number; se_pct: number; pct_n3: number; psqi: number };
  deuda_cognitiva: { deuda_semanal_base_h: number; deuda_semanal_proyectada_h: number; alerta: string };
  horario_recomendado: { hora_levantarse: string; hora_acostarse: string; hora_apagar_pantallas: string; hora_limite_cafeina: string };
}

interface GlymphaticResponse {
  n_participantes: number;
  ig_prom: number;
  pct_n3_prom: number;
  horas_n3_acum_prom: number;
  architecture: { fase: string; minutos: number; pct: number; potencial_glinfatico: string }[];
  scatter: { codigo: string; facultad: string; pct_n3: number; psqi_global: number; se_pct: number; ig: number }[];
  regression: { slope: number | null; intercept: number | null; r: number | null; r2: number | null; p_value: number | null };
}

export const GlymphaticPage: React.FC = () => {
  const { filters } = useFilters();
  const [data, setData] = useState<GlymphaticResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const [simPantallas, setSimPantallas] = useState('<=1h');
  const [simCafeina, setSimCafeina] = useState('antes_14h_o_ninguna');
  const [simEjercicio, setSimEjercicio] = useState('>=3_dias');
  const [simEstres, setSimEstres] = useState('bajo');
  const [simWake, setSimWake] = useState('06:45');
  const [simRes, setSimRes] = useState<SimResult | null>(null);

  useEffect(() => {
    setLoading(true);
    apiFetch<GlymphaticResponse>(`/api/dashboard/glymphatic${filtersToQuery(filters)}`)
      .then(setData)
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => {
    apiFetch<SimResult>('/api/dashboard/simulate-habits', {
      method: 'POST',
      body: JSON.stringify({
        pantallas: simPantallas,
        cafeina: simCafeina,
        ejercicio: simEjercicio,
        estres: simEstres,
        wake_time: simWake,
      }),
    })
      .then(setSimRes)
      .catch(() => {});
  }, [simPantallas, simCafeina, simEjercicio, simEstres, simWake]);

  const scatterPts = (data?.scatter || []).map((s) => [s.pct_n3, s.psqi_global, s.codigo]);
  const quadPts = (data?.scatter || []).map((s) => [s.se_pct, s.psqi_global, s.codigo]);
  const reg = data?.regression;

  // Linea de regresion calculada
  const minX = scatterPts.length ? Math.min(...scatterPts.map((p) => Number(p[0]))) : 10;
  const maxX = scatterPts.length ? Math.max(...scatterPts.map((p) => Number(p[0]))) : 24;
  const regLine =
    reg?.slope != null && reg?.intercept != null
      ? [
          [minX, Number((reg.slope * minX + reg.intercept).toFixed(2))],
          [maxX, Number((reg.slope * maxX + reg.intercept).toFixed(2))],
        ]
      : [];

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-[20px] font-bold text-[#14202b]">Limpieza Cerebral y Sueño Profundo (%N3)</h1>
        <p className="text-[13px] text-[#5a6877]">
          Análisis de arquitectura fisiológica y ventana glinfática nocturna (Xie et al., 2013).
        </p>
      </div>

      <div className="bg-white border-l-4 border-l-[#3b4990] border border-[#dce2ea] rounded-r-lg p-3.5 mb-4 flex items-start gap-3">
        <BookOpen size={18} className="text-[#3b4990] shrink-0 mt-0.5" />
        <div className="text-[12.5px] text-[#334155] leading-relaxed">
          <strong className="text-[#14202b]">Base científica (Xie et al., 2013, Science):</strong> Durante el sueño profundo de ondas lentas (<span className="font-mono-num">NREM N3</span>), el espacio intersticial cortical se expande hasta un 60%, incrementando el flujo glinfático que depura metabolitos neurotóxicos como la beta-amiloide. En GlymphoCare, el <strong>%N3</strong> opera como indicador objetivo de oportunidad de limpieza cerebral.
        </div>
      </div>

      <FilterBar />

      {loading && !data ? (
        <div className="bg-white border border-[#dce2ea] rounded-lg p-8 text-center text-[13px] text-[#5a6877]">
          Calculando arquitectura del sueño (%N3) y regresión desde el Data Mart...
        </div>
      ) : (
      <>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <KpiCard
          label="Sueño Profundo (%N3)"
          value={data?.pct_n3_prom?.toFixed(1)}
          unit="%"
          thresholdLabel="KPI Oficial N3"
          status={(data?.pct_n3_prom ?? 0) >= 15 ? 'neutral' : 'warn'}
          detail="Proporción del TST destinada a ondas lentas"
        />
        <KpiCard
          label="Índice Glinfático (IG)"
          value={data?.ig_prom?.toFixed(3)}
          unit="/ 1.000"
          thresholdLabel="Métrica derivada"
          status={(data?.ig_prom ?? 0) >= 0.55 ? 'good' : 'warn'}
          detail="IG = (%N3/25) × (SE/100) × min(1, 20/max(SOL,10))"
        />
        <KpiCard
          label="Horas N3 Acumuladas"
          value={data?.horas_n3_acum_prom?.toFixed(1)}
          unit="h / período"
          thresholdLabel="Promedio por estudiante"
          status="neutral"
          detail="Suma acumulada de minutos en fase N3 por participante"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <EChartBox
          title="Arquitectura del Sueño vs. Potencial Glinfático"
          subtitle="Distribución media por noche (N1, N2, N3 y REM)"
          height={290}
          provenance={`Fuente: glympho_dw.fact_sueno_noche · n = ${data?.n_participantes ?? 0} estudiantes`}
          option={{
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: 145, right: 35, top: 15, bottom: 30 },
            xAxis: { type: 'value', name: 'Minutos' },
            yAxis: { type: 'category', data: (data?.architecture || []).map((a) => a.fase) },
            series: [
              {
                type: 'bar',
                data: (data?.architecture || []).map((a) => ({
                  value: a.minutos,
                  itemStyle: { color: a.fase.includes('N3') ? '#3b4990' : '#94a3b8' },
                })),
                label: { show: true, position: 'right', formatter: '{c} min' },
              },
            ],
          }}
        />

        <EChartBox
          title="Correlación: %N3 vs. Puntuación PSQI"
          subtitle={`Regresión lineal real: r = ${reg?.r ?? '–'} · R² = ${reg?.r2 ?? '–'} · p = ${reg?.p_value ?? '–'}`}
          height={290}
          provenance="Fuente: glympho_dw.fact_sueno_noche × fact_cuestionario"
          option={{
            tooltip: {
              formatter: (p: unknown) => {
                const d = (p as { data: (string | number)[] }).data;
                return `${d[2] ?? 'Tendencia'}<br/>%N3: <b>${d[0]}%</b> · PSQI: <b>${d[1]}</b>`;
              },
            },
            grid: { left: 45, right: 20, top: 20, bottom: 40 },
            xAxis: { type: 'value', name: '%N3', min: 10, max: 25 },
            yAxis: { type: 'value', name: 'PSQI Global', min: 0, max: 20 },
            series: [
              {
                type: 'scatter',
                symbolSize: 8,
                itemStyle: { color: '#3b4990', opacity: 0.78 },
                data: scatterPts,
              },
              ...(regLine.length
                ? [
                    {
                      type: 'line' as const,
                      data: regLine,
                      showSymbol: false,
                      lineStyle: { color: '#0f766e', width: 2, type: 'dashed' as const },
                    },
                  ]
                : []),
            ],
          }}
        />
      </div>

      <EChartBox
        title="Cuadrante Percepción vs. Realidad (PSQI Subjetivo vs. Eficiencia Objetiva SE %)"
        subtitle="Permite detectar brechas entre cómo cree dormir el estudiante (PSQI <= 5) y su eficiencia real (SE >= 85%)"
        height={300}
        provenance="Fuente: glympho_dw.fact_cuestionario × fact_sueno_noche"
        option={{
          tooltip: {
            formatter: (p: unknown) => {
              const d = (p as { data: (string | number)[] }).data;
              return `${d[2]}<br/>SE: <b>${d[0]}%</b> · PSQI: <b>${d[1]}</b>`;
            },
          },
          grid: { left: 50, right: 30, top: 25, bottom: 45 },
          xAxis: { type: 'value', name: 'Eficiencia SE (%)', min: 75, max: 96 },
          yAxis: { type: 'value', name: 'PSQI Global', min: 0, max: 20 },
          series: [
            {
              type: 'scatter',
              symbolSize: 9,
              itemStyle: {
                color: (p: unknown) => {
                  const d = (p as { data: number[] }).data;
                  if (d[0] >= 85 && d[1] <= 5) return '#15803d';
                  if (d[0] < 85 && d[1] > 5) return '#b91c1c';
                  return '#b45309';
                },
              },
              data: quadPts,
              markLine: {
                silent: true,
                lineStyle: { type: 'dashed', color: '#64748b' },
                data: [{ xAxis: 85 }, { yAxis: 5 }],
              },
            },
          ],
        }}
      />

      {simRes && (
        <div className="mt-4 bg-white border border-[#dce2ea] rounded-lg p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 pb-3 mb-3 border-b border-[#eef2f6]">
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={16} className="text-[#0f766e]" />
              <div>
                <h3 className="text-[14px] font-semibold text-[#14202b]">
                  Simulador de Higiene del Sueño y Ajuste de Horario de Descanso
                </h3>
                <p className="text-[12px] text-[#5a6877]">
                  Estimación empírica sobre promedios reales del Data Mart (n = {simRes.n_referencia}) · Sin modelos predictivos ML.
                </p>
              </div>
            </div>
            <span className="text-[11px] font-mono-num px-2 py-0.5 rounded bg-[#fffbeb] text-[#b45309] border border-[#fde68a]">
              {simRes.deuda_cognitiva.alerta} · Deuda actual: {simRes.deuda_cognitiva.deuda_semanal_base_h} h/sem
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5 mb-4 text-[12px]">
            <div>
              <label className="block text-[#5a6877] mb-1">Pantallas antes de dormir</label>
              <select value={simPantallas} onChange={(e) => setSimPantallas(e.target.value)} className="w-full p-1.5 border border-[#dce2ea] rounded bg-[#f8fafc]">
                <option value="<=1h">No (&lt;= 1 h)</option>
                <option value=">1h">Sí (&gt; 1 h)</option>
              </select>
            </div>
            <div>
              <label className="block text-[#5a6877] mb-1">Cafeína</label>
              <select value={simCafeina} onChange={(e) => setSimCafeina(e.target.value)} className="w-full p-1.5 border border-[#dce2ea] rounded bg-[#f8fafc]">
                <option value="antes_14h_o_ninguna">Antes 14:00 h / Ninguna</option>
                <option value="despues_14h">Después de 14:00 h</option>
              </select>
            </div>
            <div>
              <label className="block text-[#5a6877] mb-1">Ejercicio semanal</label>
              <select value={simEjercicio} onChange={(e) => setSimEjercicio(e.target.value)} className="w-full p-1.5 border border-[#dce2ea] rounded bg-[#f8fafc]">
                <option value=">=3_dias">&gt;= 3 días/sem</option>
                <option value="<3_dias">&lt; 3 días/sem</option>
              </select>
            </div>
            <div>
              <label className="block text-[#5a6877] mb-1">Nivel de estrés</label>
              <select value={simEstres} onChange={(e) => setSimEstres(e.target.value)} className="w-full p-1.5 border border-[#dce2ea] rounded bg-[#f8fafc]">
                <option value="bajo">Bajo</option>
                <option value="medio">Medio</option>
                <option value="alto">Alto</option>
              </select>
            </div>
            <div>
              <label className="block text-[#5a6877] mb-1">Hora objetivo despertar</label>
              <input type="time" value={simWake} onChange={(e) => setSimWake(e.target.value)} className="w-full p-1.5 border border-[#dce2ea] rounded bg-[#f8fafc] font-mono-num" />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-[#dce2ea] rounded p-3 bg-[#f8fafc]">
              <div className="text-[12px] font-semibold text-[#14202b] mb-2">Comparativa Empírica (Cohorte Base vs Escenario Simulado)</div>
              <div className="grid grid-cols-4 gap-2 text-center font-mono-num text-[12px]">
                <div className="bg-white p-2 rounded border border-[#dce2ea]">
                  <div className="text-[11px] text-[#5a6877]">%N3</div>
                  <div className="font-bold text-[#3b4990]">{simRes.linea_base.pct_n3}% → {simRes.proyeccion.pct_n3}%</div>
                </div>
                <div className="bg-white p-2 rounded border border-[#dce2ea]">
                  <div className="text-[11px] text-[#5a6877]">SOL (min)</div>
                  <div className="font-bold text-[#0f766e]">{simRes.linea_base.sol_min} → {simRes.proyeccion.sol_min}</div>
                </div>
                <div className="bg-white p-2 rounded border border-[#dce2ea]">
                  <div className="text-[11px] text-[#5a6877]">TST (h)</div>
                  <div className="font-bold text-[#0f766e]">{(simRes.linea_base.tst_min / 60).toFixed(1)} → {(simRes.proyeccion.tst_min / 60).toFixed(1)}</div>
                </div>
                <div className="bg-white p-2 rounded border border-[#dce2ea]">
                  <div className="text-[11px] text-[#5a6877]">PSQI</div>
                  <div className="font-bold text-[#14202b]">{simRes.linea_base.psqi} → {simRes.proyeccion.psqi}</div>
                </div>
              </div>
            </div>

            <div className="border border-[#99f6e4] rounded p-3 bg-[#e6f4f3]/60">
              <div className="flex items-center gap-1.5 text-[12px] font-semibold text-[#0f766e] mb-2">
                <Clock size={14} />
                Ajuste Sugerido de Horarios (Meta &gt;= 7.5 h efectivas)
              </div>
              <div className="grid grid-cols-3 gap-2 text-center font-mono-num text-[12px]">
                <div className="bg-white p-2 rounded border border-[#dce2ea]">
                  <div className="text-[11px] text-[#5a6877]">Límite cafeína</div>
                  <div className="font-bold text-[#14202b]">{simRes.horario_recomendado.hora_limite_cafeina}</div>
                </div>
                <div className="bg-white p-2 rounded border border-[#dce2ea]">
                  <div className="text-[11px] text-[#5a6877]">Apagar pantallas</div>
                  <div className="font-bold text-[#b45309]">{simRes.horario_recomendado.hora_apagar_pantallas}</div>
                </div>
                <div className="bg-white p-2 rounded border border-[#dce2ea]">
                  <div className="text-[11px] text-[#5a6877]">Acostarse</div>
                  <div className="font-bold text-[#0f766e]">{simRes.horario_recomendado.hora_acostarse}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      </>
      )}
    </div>
  );
};
