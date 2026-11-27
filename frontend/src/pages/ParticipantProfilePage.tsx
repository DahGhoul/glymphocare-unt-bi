import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, Sparkles } from 'lucide-react';
import { EChartBox } from '../components/EChartBox';
import { KpiCard } from '../components/KpiCard';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../services/api';
import type { AiInterpretation, RuleAlert } from '../types/glympho';

interface ParticipantItem {
  codigo: string;
  facultad: string;
  carrera: string;
  ciclo: number;
  psqi_global: number;
  ess_total: number;
  pct_n3_prom: number | null;
  noches: number;
}

interface ParticipantDetail {
  participante: { codigo: string; edad: number; sexo: string; ciclo: number; facultad: string; carrera: string };
  kpis: Record<string, number | null>;
  habitos_actuales: Record<string, string | null>;
  evaluaciones: { fecha: string; psqi_global: number; ess_total: number; clasificacion_psqi: string; clasificacion_ess: string }[];
  noches: { fecha: string; dia_semana: string; tst_min: number; se_pct: number; pct_n3: number; sol_min: number; waso_min: number }[];
  alerts: RuleAlert[];
}

export const ParticipantProfilePage: React.FC = () => {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [list, setList] = useState<ParticipantItem[]>([]);
  const [query, setQuery] = useState('');
  const [selectedCode, setSelectedCode] = useState<string>(
    searchParams.get('codigo') || user?.participante_codigo || 'UNT-001'
  );
  const [detail, setDetail] = useState<ParticipantDetail | null>(null);
  const [ai, setAi] = useState<AiInterpretation | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    apiFetch<ParticipantItem[]>(`/api/dashboard/participants${query ? `?q=${encodeURIComponent(query)}` : ''}`)
      .then(setList)
      .catch(() => {});
  }, [query]);

  useEffect(() => {
    if (!selectedCode) return;
    setAi(null);
    apiFetch<ParticipantDetail>(`/api/dashboard/participants/${selectedCode}`)
      .then(setDetail)
      .catch(() => {});
  }, [selectedCode]);

  const handleInterpret = async () => {
    setAiLoading(true);
    try {
      const res = await apiFetch<AiInterpretation>('/api/ai/interpret', {
        method: 'POST',
        body: JSON.stringify({ scope: 'participant', codigo: selectedCode }),
      });
      setAi(res);
    } finally {
      setAiLoading(false);
    }
  };

  const p = detail?.participante;
  const k = detail?.kpis || {};

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <h1 className="text-[20px] font-bold text-[#14202b]">Perfil Individual e Interpretación IA</h1>
          <p className="text-[13px] text-[#5a6877]">
            Seguimiento longitudinal anonimizado, reglas activadas e interpretación generativa sin diagnóstico clínico.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-[#5a6877]" />
            <input
              type="text"
              placeholder="Buscar UNT-001 o carrera..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-[12px] border border-[#dce2ea] rounded bg-white w-[190px]"
            />
          </div>
          <select
            value={selectedCode}
            onChange={(e) => {
              setSelectedCode(e.target.value);
              setSearchParams({ codigo: e.target.value });
            }}
            className="text-[13px] font-mono-num border border-[#dce2ea] rounded px-2.5 py-1.5 bg-white text-[#14202b]"
          >
            {list.map((item) => (
              <option key={item.codigo} value={item.codigo}>
                {item.codigo} · {item.carrera} (PSQI {item.psqi_global})
              </option>
            ))}
          </select>
        </div>
      </div>

      {detail && p && (
        <>
          <div className="bg-white border border-[#dce2ea] rounded-lg p-4 mb-4 flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono-num text-[16px] font-bold text-[#0f766e]">{p.codigo}</span>
                <span className="text-[12px] px-2 py-0.5 rounded bg-[#f1f5f9] text-[#334155]">
                  {p.facultad} · {p.carrera} · Ciclo {p.ciclo}
                </span>
                <span className="text-[12px] text-[#5a6877] font-mono-num">
                  {p.edad} años · Sexo {p.sexo}
                </span>
              </div>
              <div className="text-[12px] text-[#5a6877] mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
                <span>Pantallas: <strong className="text-[#14202b]">{detail.habitos_actuales.uso_pantallas ?? '–'}</strong></span>
                <span>Cafeína: <strong className="text-[#14202b]">{detail.habitos_actuales.cafeina ?? '–'}</strong></span>
                <span>Ejercicio: <strong className="text-[#14202b]">{detail.habitos_actuales.ejercicio ?? '–'}</strong></span>
                <span>Estrés: <strong className="text-[#14202b]">{detail.habitos_actuales.estres ?? '–'}</strong></span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleInterpret}
              disabled={aiLoading}
              className="inline-flex items-center gap-2 px-4 py-2 rounded bg-[#3b4990] hover:bg-[#313d7a] text-white text-[13px] font-semibold cursor-pointer disabled:opacity-60"
            >
              <Sparkles size={15} />
              {aiLoading ? 'Interpretando KPIs...' : 'Generar interpretación IA'}
            </button>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
            <KpiCard label="PSQI Actual" value={k.PSQI} unit="/ 21" thresholdLabel="<= 5" status={(k.PSQI ?? 0) > 5 ? 'bad' : 'good'} />
            <KpiCard label="ESS Epworth" value={k.ESS} unit="/ 24" thresholdLabel="<= 10" status={(k.ESS ?? 0) > 10 ? 'warn' : 'good'} />
            <KpiCard label="Eficiencia (SE)" value={k.SE?.toFixed(1)} unit="%" thresholdLabel=">= 85%" status={(k.SE ?? 0) >= 85 ? 'good' : 'warn'} />
            <KpiCard label="Latencia (SOL)" value={k.SOL?.toFixed(1)} unit="min" thresholdLabel="<= 20 min" status={(k.SOL ?? 0) > 20 ? 'bad' : 'good'} />
            <KpiCard label="%N3 Profundo" value={k.PCT_N3?.toFixed(1)} unit="%" thresholdLabel={`IG ${k.indice_glinfatico?.toFixed(2) ?? '–'}`} status={(k.PCT_N3 ?? 0) >= 15 ? 'neutral' : 'warn'} />
          </div>

          {ai && (
            <div className="bg-white border border-[#3b4990]/40 rounded-lg p-4 mb-4">
              <div className="flex flex-wrap items-center justify-between gap-2 pb-2 mb-3 border-b border-[#eef2f6]">
                <h3 className="text-[14px] font-bold text-[#14202b]">Síntesis Interpretativa de Resultados</h3>
                <span className="text-[11px] font-mono-num px-2 py-0.5 rounded bg-[#eef2ff] text-[#3b4990]">
                  {ai.provider_used}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[13px] text-[#334155]">
                <div>
                  <h4 className="font-semibold text-[#14202b] mb-1">1. Resumen ejecutivo</h4>
                  <p className="leading-relaxed">{ai.resumen_ejecutivo}</p>
                  <h4 className="font-semibold text-[#14202b] mt-3 mb-1">2. Componentes críticos</h4>
                  <p className="leading-relaxed">{ai.componentes_criticos}</p>
                </div>
                <div>
                  <h4 className="font-semibold text-[#14202b] mb-1">3. Ventana glinfática (%N3)</h4>
                  <p className="leading-relaxed">{ai.analisis_glinfatico_n3}</p>
                  <h4 className="font-semibold text-[#14202b] mt-3 mb-1">4. Plan de higiene del sueño</h4>
                  <ul className="list-disc pl-5 space-y-1">
                    {ai.plan_accion.map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <p className="mt-3 pt-2 border-t border-[#eef2f6] text-[11px] text-[#5a6877]">{ai.aviso_no_clinico}</p>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <EChartBox
              title="Evolución Longitudinal PSQI y ESS"
              subtitle="Comparación de cuestionarios sucesivos frente al umbral PSQI = 5"
              height={260}
              provenance={`Fuente: glympho_dw.fact_cuestionario · ${detail.evaluaciones.length} evaluaciones`}
              option={{
                tooltip: { trigger: 'axis' },
                legend: { data: ['PSQI Global', 'ESS'], bottom: 0 },
                grid: { left: 40, right: 20, top: 20, bottom: 40 },
                xAxis: { type: 'category', data: detail.evaluaciones.map((e) => e.fecha) },
                yAxis: { type: 'value', min: 0, max: 24 },
                series: [
                  {
                    name: 'PSQI Global',
                    type: 'line',
                    data: detail.evaluaciones.map((e) => e.psqi_global),
                    itemStyle: { color: '#0f766e' },
                    markLine: { silent: true, data: [{ yAxis: 5, name: 'Umbral PSQI' }], lineStyle: { color: '#b91c1c', type: 'dashed' } },
                  },
                  {
                    name: 'ESS',
                    type: 'line',
                    data: detail.evaluaciones.map((e) => e.ess_total),
                    itemStyle: { color: '#3b4990' },
                  },
                ],
              }}
            />

            <EChartBox
              title="Noches Registradas: Duración (TST) y %N3"
              subtitle="Evolución objetiva por noche (wearable / manual)"
              height={260}
              provenance={`Fuente: glympho_dw.fact_sueno_noche · ${detail.noches.length} noches`}
              option={{
                tooltip: { trigger: 'axis' },
                legend: { data: ['TST (min)', '%N3'], bottom: 0 },
                grid: { left: 45, right: 40, top: 20, bottom: 40 },
                xAxis: { type: 'category', data: detail.noches.map((n) => n.fecha.slice(5)) },
                yAxis: [
                  { type: 'value', name: 'min' },
                  { type: 'value', name: '%N3', min: 0, max: 35, splitLine: { show: false } },
                ],
                series: [
                  { name: 'TST (min)', type: 'bar', data: detail.noches.map((n) => n.tst_min), itemStyle: { color: '#99f6e4' } },
                  { name: '%N3', type: 'line', yAxisIndex: 1, data: detail.noches.map((n) => n.pct_n3), itemStyle: { color: '#3b4990' } },
                ],
              }}
            />
          </div>

          <div className="bg-white border border-[#dce2ea] rounded-lg p-4">
            <h3 className="text-[14px] font-semibold text-[#14202b] mb-3">
              Recomendaciones Activas Según Motor de Reglas (RF-08)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {detail.alerts.length === 0 ? (
                <p className="text-[13px] text-[#15803d]">Sin alertas pendientes: todos los KPIs cumplen la meta actual.</p>
              ) : (
                detail.alerts.map((a) => (
                  <div key={a.rule_id} className="p-3 rounded border border-[#dce2ea] bg-[#f8fafc] text-[12.5px]">
                    <div className="flex items-center justify-between font-semibold text-[#14202b]">
                      <span>{a.titulo}</span>
                      <span className="font-mono-num text-[#b91c1c]">{a.valor_actual} ({a.operador} {a.umbral})</span>
                    </div>
                    <p className="text-[#334155] mt-1">{a.texto_recomendacion}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
