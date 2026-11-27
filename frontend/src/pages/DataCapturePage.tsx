import React, { useState } from 'react';
import { CheckCircle2, Download, Upload } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiDownload, apiFetch } from '../services/api';

const ESS_SITUATIONS = [
  '1. Sentado y leyendo',
  '2. Viendo televisión',
  '3. Sentado inactivo en un lugar público (aula, cine, reunión)',
  '4. Como pasajero en un vehículo durante una hora seguida',
  '5. Acostado descansando por la tarde cuando las circunstancias lo permiten',
  '6. Sentado conversando con alguien',
  '7. Sentado tranquilo después de un almuerzo sin alcohol',
  '8. En un vehículo detenido unos minutos en el tráfico',
];

const PSQI_DISTURBANCES: [string, string][] = [
  ['5a', 'No poder conciliar el sueño en los primeros 30 minutos'],
  ['5b', 'Despertarse en mitad de la noche o de madrugada'],
  ['5c', 'Tener que levantarse para ir al baño'],
  ['5d', 'No poder respirar cómodamente'],
  ['5e', 'Toser o roncar ruidosamente'],
  ['5f', 'Sentir demasiado frío'],
  ['5g', 'Sentir demasiado calor'],
  ['5h', 'Tener pesadillas'],
  ['5i', 'Sentir dolor físico'],
  ['5j', 'Otras razones (preocupación académica, ruido, etc.)'],
];

const FREQ_OPTIONS = [
  { v: 0, l: 'Ninguna vez en el último mes' },
  { v: 1, l: '< 1 vez por semana' },
  { v: 2, l: '1 o 2 veces por semana' },
  { v: 3, l: '3 o más veces por semana' },
];

export const DataCapturePage: React.FC = () => {
  const { user } = useAuth();
  const [tab, setTab] = useState<'wizard' | 'objective'>('wizard');
  const [step, setStep] = useState(1);

  // Wizard state
  const [codigo, setCodigo] = useState(user?.participante_codigo || 'UNT-001');
  const [consent, setConsent] = useState(true);
  const [fecha, setFecha] = useState('2026-11-26');
  const [pantallas, setPantallas] = useState('>1h');
  const [cafeina, setCafeina] = useState('antes_14h_o_ninguna');
  const [ejercicio, setEjercicio] = useState('>=3_dias');
  const [estres, setEstres] = useState('medio');
  const [regularidad, setRegularidad] = useState('regular');
  const [horaAcostarse, setHoraAcostarse] = useState('23:30');
  const [minutosLatencia, setMinutosLatencia] = useState(20);
  const [horaLevantarse, setHoraLevantarse] = useState('06:30');
  const [horasSueno, setHorasSueno] = useState(6.5);
  const [psqiItems, setPsqiItems] = useState<Record<string, number>>({
    '5a': 1, '5b': 1, '5c': 0, '5d': 0, '5e': 0, '5f': 0, '5g': 1, '5h': 0, '5i': 0, '5j': 1,
    '6': 1, '7': 0, '8': 1, '9': 1,
  });
  const [essItems, setEssItems] = useState<number[]>([1, 1, 1, 2, 2, 0, 1, 0]);
  const [wizardResult, setWizardResult] = useState<any>(null);
  const [wizardErr, setWizardErr] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // CSV & Manual night state
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvResult, setCsvResult] = useState<any>(null);
  const [csvErr, setCsvErr] = useState('');
  const [nightFecha, setNightFecha] = useState('2026-11-26');
  const [tib, setTib] = useState(480);
  const [sol, setSol] = useState(18);
  const [despertares, setDespertares] = useState(1);
  const [n1, setN1] = useState(25);
  const [n2, setN2] = useState(215);
  const [n3, setN3] = useState(90);
  const [rem, setRem] = useState(90);
  const [nightResult, setNightResult] = useState<any>(null);
  const [nightErr, setNightErr] = useState('');

  const tstCalc = n1 + n2 + n3 + rem;
  const wasoCalc = Math.max(0, tib - sol - tstCalc);
  const seCalc = tib > 0 ? ((tstCalc / tib) * 100).toFixed(1) : '0.0';
  const pctN3Calc = tstCalc > 0 ? ((n3 / tstCalc) * 100).toFixed(1) : '0.0';

  const submitWizard = async () => {
    setWizardErr('');
    setSubmitting(true);
    try {
      const res = await apiFetch('/api/capture/questionnaire', {
        method: 'POST',
        body: JSON.stringify({
          participante_codigo: codigo,
          consentimiento_aceptado: consent,
          fecha,
          pantallas_antes_dormir: pantallas,
          cafeina_nivel: cafeina,
          ejercicio_nivel: ejercicio,
          estres_nivel: estres,
          regularidad_horarios: regularidad,
          hora_acostarse: horaAcostarse,
          minutos_latencia: minutosLatencia,
          hora_levantarse: horaLevantarse,
          horas_sueno_real: horasSueno,
          psqi_items: psqiItems,
          ess_items: essItems,
        }),
      });
      setWizardResult(res);
    } catch (err) {
      setWizardErr(err instanceof Error ? err.message : 'Error al guardar evaluación');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCsvUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) return;
    setCsvErr('');
    setCsvResult(null);
    const fd = new FormData();
    fd.append('file', csvFile);
    fd.append('participante_codigo', codigo);
    try {
      const res = await apiFetch('/api/capture/sleep-csv', { method: 'POST', body: fd });
      setCsvResult(res);
    } catch (err) {
      setCsvErr(err instanceof Error ? err.message : 'Error al procesar CSV');
    }
  };

  const handleManualNight = async (e: React.FormEvent) => {
    e.preventDefault();
    setNightErr('');
    setNightResult(null);
    try {
      const res = await apiFetch('/api/capture/sleep-night', {
        method: 'POST',
        body: JSON.stringify({
          participante_codigo: codigo,
          fecha: nightFecha,
          tib_min: tib,
          tst_min: tstCalc,
          sol_min: sol,
          despertares,
          min_n1: n1,
          min_n2: n2,
          min_n3: n3,
          min_rem: rem,
        }),
      });
      setNightResult(res);
    } catch (err) {
      setNightErr(err instanceof Error ? err.message : 'Error al registrar noche');
    }
  };

  return (
    <div className="max-w-[960px]">
      <div className="mb-4">
        <h1 className="text-[20px] font-bold text-[#14202b]">Captura de Datos (Cuestionarios y Wearable)</h1>
        <p className="text-[13px] text-[#5a6877]">
          Ingreso móvil-amigable de PSQI (19 ítems), ESS (8 situaciones), hábitos y carga CSV/manual de noches objetivas con ejecución inmediata del ETL.
        </p>
      </div>

      <div className="bg-white border border-[#dce2ea] rounded-lg p-3 mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={() => setTab('wizard')}
            className={`px-3.5 py-1.5 rounded text-[13px] font-medium cursor-pointer ${
              tab === 'wizard' ? 'bg-[#0f766e] text-white' : 'bg-[#f1f5f9] text-[#334155]'
            }`}
          >
            Formulario Multi-paso (PSQI + ESS)
          </button>
          <button
            type="button"
            onClick={() => setTab('objective')}
            className={`px-3.5 py-1.5 rounded text-[13px] font-medium cursor-pointer ${
              tab === 'objective' ? 'bg-[#0f766e] text-white' : 'bg-[#f1f5f9] text-[#334155]'
            }`}
          >
            Carga CSV Wearable / Noche Manual
          </button>
        </div>

        <div className="flex items-center gap-2 text-[12px]">
          <span className="text-[#5a6877]">Participante:</span>
          <input
            type="text"
            value={codigo}
            onChange={(e) => setCodigo(e.target.value)}
            className="font-mono-num px-2.5 py-1 border border-[#dce2ea] rounded w-[110px] bg-[#f8fafc]"
          />
        </div>
      </div>

      {tab === 'wizard' ? (
        <div className="bg-white border border-[#dce2ea] rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="text-[13px] font-semibold text-[#14202b]">
              Paso {step} de 4 —{' '}
              {step === 1
                ? 'Consentimiento y Fecha'
                : step === 2
                ? 'Hábitos de Higiene del Sueño'
                : step === 3
                ? 'Cuestionario PSQI (Pittsburgh)'
                : 'Escala ESS (Epworth) y Envío'}
            </div>
            <div className="w-[140px] h-2 bg-[#f1f5f9] rounded-full overflow-hidden">
              <div className="h-full bg-[#0f766e] transition-all" style={{ width: `${step * 25}%` }} />
            </div>
          </div>

          {step === 1 && (
            <div className="space-y-4">
              <div>
                <label className="block text-[12px] font-medium text-[#334155] mb-1">Fecha de evaluación</label>
                <input
                  type="date"
                  value={fecha}
                  onChange={(e) => setFecha(e.target.value)}
                  className="px-3 py-2 border border-[#dce2ea] rounded text-[13px]"
                />
              </div>
              <label className="flex items-start gap-2.5 p-3.5 rounded bg-[#f8fafc] border border-[#dce2ea] text-[13px] text-[#334155] cursor-pointer">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  className="mt-1 accent-[#0f766e]"
                />
                <span>
                  Confirmo participación voluntaria en el monitoreo académico GlymphoCare. Los datos se almacenan anonimizados en la base transaccional y alimentan el Data Mart tras validar rangos.
                </span>
              </label>
            </div>
          )}

          {step === 2 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[13px]">
              <div>
                <label className="block font-medium mb-1">Uso de pantallas antes de dormir</label>
                <select value={pantallas} onChange={(e) => setPantallas(e.target.value)} className="w-full p-2 border border-[#dce2ea] rounded">
                  <option value=">1h">Sí (&gt; 1 hora antes de dormir)</option>
                  <option value="<=1h">No (&lt;= 1 hora antes de dormir)</option>
                </select>
              </div>
              <div>
                <label className="block font-medium mb-1">Consumo de cafeína</label>
                <select value={cafeina} onChange={(e) => setCafeina(e.target.value)} className="w-full p-2 border border-[#dce2ea] rounded">
                  <option value="despues_14h">Después de las 14:00 h</option>
                  <option value="antes_14h_o_ninguna">Antes de las 14:00 h o ninguna</option>
                </select>
              </div>
              <div>
                <label className="block font-medium mb-1">Ejercicio físico semanal</label>
                <select value={ejercicio} onChange={(e) => setEjercicio(e.target.value)} className="w-full p-2 border border-[#dce2ea] rounded">
                  <option value=">=3_dias">&gt;= 3 días por semana</option>
                  <option value="<3_dias">&lt; 3 días por semana</option>
                </select>
              </div>
              <div>
                <label className="block font-medium mb-1">Nivel de estrés académico</label>
                <select value={estres} onChange={(e) => setEstres(e.target.value)} className="w-full p-2 border border-[#dce2ea] rounded">
                  <option value="bajo">Bajo</option>
                  <option value="medio">Medio</option>
                  <option value="alto">Alto</option>
                </select>
              </div>
              <div>
                <label className="block font-medium mb-1">Regularidad de horarios</label>
                <select value={regularidad} onChange={(e) => setRegularidad(e.target.value)} className="w-full p-2 border border-[#dce2ea] rounded">
                  <option value="regular">Regular (+/- 30 min)</option>
                  <option value="irregular">Irregular</option>
                </select>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4 text-[13px]">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <label className="block text-[12px] font-medium mb-1">1. Hora de acostarse</label>
                  <input type="time" value={horaAcostarse} onChange={(e) => setHoraAcostarse(e.target.value)} className="w-full p-2 border border-[#dce2ea] rounded" />
                </div>
                <div>
                  <label className="block text-[12px] font-medium mb-1">2. Latencia (min)</label>
                  <input type="number" min={0} max={360} value={minutosLatencia} onChange={(e) => setMinutosLatencia(Number(e.target.value))} className="w-full p-2 border border-[#dce2ea] rounded" />
                </div>
                <div>
                  <label className="block text-[12px] font-medium mb-1">3. Hora de levantarse</label>
                  <input type="time" value={horaLevantarse} onChange={(e) => setHoraLevantarse(e.target.value)} className="w-full p-2 border border-[#dce2ea] rounded" />
                </div>
                <div>
                  <label className="block text-[12px] font-medium mb-1">4. Horas reales dormidas</label>
                  <input type="number" step="0.25" min={1} max={16} value={horasSueno} onChange={(e) => setHorasSueno(Number(e.target.value))} className="w-full p-2 border border-[#dce2ea] rounded" />
                </div>
              </div>

              <div className="border-t border-[#eef2f6] pt-3 space-y-2">
                <div className="font-semibold text-[#14202b]">5. Dificultades para dormir durante el último mes:</div>
                {PSQI_DISTURBANCES.map(([code, label]) => (
                  <div key={code} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 py-1.5 border-b border-[#f1f5f9]">
                    <span>{code}. {label}</span>
                    <select
                      value={psqiItems[code]}
                      onChange={(e) => setPsqiItems({ ...psqiItems, [code]: Number(e.target.value) })}
                      className="p-1.5 border border-[#dce2ea] rounded text-[12px] sm:w-[230px]"
                    >
                      {FREQ_OPTIONS.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
                    </select>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                <div>
                  <label className="block font-medium mb-1">6. Calidad subjetiva global del sueño</label>
                  <select value={psqiItems['6']} onChange={(e) => setPsqiItems({ ...psqiItems, '6': Number(e.target.value) })} className="w-full p-2 border border-[#dce2ea] rounded">
                    <option value={0}>Muy buena (0)</option>
                    <option value={1}>Bastante buena (1)</option>
                    <option value={2}>Bastante mala (2)</option>
                    <option value={3}>Muy mala (3)</option>
                  </select>
                </div>
                <div>
                  <label className="block font-medium mb-1">7. Medicación para dormir</label>
                  <select value={psqiItems['7']} onChange={(e) => setPsqiItems({ ...psqiItems, '7': Number(e.target.value) })} className="w-full p-2 border border-[#dce2ea] rounded">
                    {FREQ_OPTIONS.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block font-medium mb-1">8. Somnolencia realizando actividades</label>
                  <select value={psqiItems['8']} onChange={(e) => setPsqiItems({ ...psqiItems, '8': Number(e.target.value) })} className="w-full p-2 border border-[#dce2ea] rounded">
                    {FREQ_OPTIONS.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block font-medium mb-1">9. Falta de ánimo/entusiasmo</label>
                  <select value={psqiItems['9']} onChange={(e) => setPsqiItems({ ...psqiItems, '9': Number(e.target.value) })} className="w-full p-2 border border-[#dce2ea] rounded">
                    <option value={0}>Ningún problema (0)</option>
                    <option value={1}>Solo un leve problema (1)</option>
                    <option value={2}>Un problema moderado (2)</option>
                    <option value={3}>Un gran problema (3)</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-3 text-[13px]">
              <p className="text-[#5a6877]">
                Escala de Somnolencia de Epworth (ESS): probabilidad de quedarse dormido (0 = nunca, 3 = alta probabilidad).
              </p>
              {ESS_SITUATIONS.map((label, idx) => (
                <div key={idx} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 py-1.5 border-b border-[#f1f5f9]">
                  <span>{label}</span>
                  <select
                    value={essItems[idx]}
                    onChange={(e) => {
                      const next = [...essItems];
                      next[idx] = Number(e.target.value);
                      setEssItems(next);
                    }}
                    className="p-1.5 border border-[#dce2ea] rounded text-[12px] sm:w-[210px]"
                  >
                    <option value={0}>0 · Nunca</option>
                    <option value={1}>1 · Leve probabilidad</option>
                    <option value={2}>2 · Moderada probabilidad</option>
                    <option value={3}>3 · Alta probabilidad</option>
                  </select>
                </div>
              ))}
            </div>
          )}

          {wizardErr && (
            <div className="mt-4 p-3 rounded bg-[#fef2f2] border border-[#fecaca] text-[#b91c1c] text-[12px]">
              {wizardErr}
            </div>
          )}

          {wizardResult && (
            <div className="mt-4 p-4 rounded bg-[#ecfdf5] border border-[#bbf7d0] text-[13px]">
              <div className="flex items-center gap-2 font-bold text-[#15803d]">
                <CheckCircle2 size={16} />
                Evaluación guardada y procesada en el Data Mart (ETL #{wizardResult.etl?.log_id})
              </div>
              <div className="mt-2 font-mono-num text-[#14202b]">
                PSQI Global: <strong>{wizardResult.psqi.psqi_global}</strong> ({wizardResult.psqi.clasificacion_psqi}) · ESS:{' '}
                <strong>{wizardResult.ess.ess_total}</strong> ({wizardResult.ess.clasificacion_ess})
              </div>
            </div>
          )}

          <div className="mt-6 flex items-center justify-between pt-4 border-t border-[#eef2f6]">
            <button
              type="button"
              disabled={step === 1}
              onClick={() => setStep((s) => Math.max(1, s - 1))}
              className="px-4 py-2 rounded border border-[#dce2ea] text-[13px] font-medium disabled:opacity-40 cursor-pointer"
            >
              Anterior
            </button>
            {step < 4 ? (
              <button
                type="button"
                onClick={() => setStep((s) => Math.min(4, s + 1))}
                className="px-4 py-2 rounded bg-[#0f766e] text-white text-[13px] font-semibold cursor-pointer"
              >
                Siguiente
              </button>
            ) : (
              <button
                type="button"
                disabled={submitting}
                onClick={submitWizard}
                className="px-5 py-2 rounded bg-[#0f766e] text-white text-[13px] font-semibold cursor-pointer disabled:opacity-60"
              >
                {submitting ? 'Calculando y cargando...' : 'Enviar evaluación y ejecutar ETL'}
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white border border-[#dce2ea] rounded-lg p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[15px] font-semibold text-[#14202b]">Carga Masiva CSV (Wearable)</h3>
              <button
                type="button"
                onClick={() => apiDownload('/api/capture/csv-template', { method: 'GET' }, 'plantilla_wearable_glymphocare.csv')}
                className="inline-flex items-center gap-1 text-[12px] text-[#0f766e] hover:underline cursor-pointer"
              >
                <Download size={13} />
                Plantilla CSV
              </button>
            </div>
            <form onSubmit={handleCsvUpload} className="space-y-3">
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                className="block w-full text-[12px] border border-[#dce2ea] rounded p-2 bg-[#f8fafc]"
              />
              <button
                type="submit"
                disabled={!csvFile}
                className="inline-flex items-center gap-2 px-4 py-2 bg-[#0f766e] text-white text-[13px] font-semibold rounded cursor-pointer disabled:opacity-50"
              >
                <Upload size={14} />
                Subir y validar en ETL
              </button>
            </form>

            {csvErr && <div className="mt-3 p-2.5 text-[12px] bg-[#fef2f2] text-[#b91c1c] rounded">{csvErr}</div>}
            {csvResult && (
              <div className="mt-3 p-3 text-[12px] bg-[#f8fafc] border border-[#dce2ea] rounded space-y-1">
                <div>Estado: <strong className="uppercase">{csvResult.estado}</strong></div>
                <div className="font-mono-num">
                  Válidos: <strong className="text-[#15803d]">{csvResult.registros_validos}</strong> · Rechazados:{' '}
                  <strong className="text-[#b91c1c]">{csvResult.registros_rechazados}</strong>
                </div>
                {csvResult.errores?.length > 0 && (
                  <ul className="list-disc pl-4 text-[#b91c1c] mt-1">
                    {csvResult.errores.map((er: string, i: number) => <li key={i}>{er}</li>)}
                  </ul>
                )}
              </div>
            )}
          </div>

          <div className="bg-white border border-[#dce2ea] rounded-lg p-5">
            <h3 className="text-[15px] font-semibold text-[#14202b] mb-3">Ingreso Manual de Noche</h3>
            <form onSubmit={handleManualNight} className="space-y-2.5 text-[12.5px]">
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block mb-1">Fecha</label>
                  <input type="date" value={nightFecha} onChange={(e) => setNightFecha(e.target.value)} className="w-full p-1.5 border border-[#dce2ea] rounded" />
                </div>
                <div>
                  <label className="block mb-1">TIB (min cama)</label>
                  <input type="number" value={tib} onChange={(e) => setTib(Number(e.target.value))} className="w-full p-1.5 border border-[#dce2ea] rounded font-mono-num" />
                </div>
                <div>
                  <label className="block mb-1">Latencia SOL</label>
                  <input type="number" value={sol} onChange={(e) => setSol(Number(e.target.value))} className="w-full p-1.5 border border-[#dce2ea] rounded font-mono-num" />
                </div>
              </div>
              <div className="grid grid-cols-5 gap-2">
                <div><label className="block mb-1">N1</label><input type="number" value={n1} onChange={(e) => setN1(Number(e.target.value))} className="w-full p-1.5 border border-[#dce2ea] rounded font-mono-num" /></div>
                <div><label className="block mb-1">N2</label><input type="number" value={n2} onChange={(e) => setN2(Number(e.target.value))} className="w-full p-1.5 border border-[#dce2ea] rounded font-mono-num" /></div>
                <div><label className="block mb-1 font-semibold text-[#3b4990]">N3</label><input type="number" value={n3} onChange={(e) => setN3(Number(e.target.value))} className="w-full p-1.5 border border-[#3b4990] rounded font-mono-num" /></div>
                <div><label className="block mb-1">REM</label><input type="number" value={rem} onChange={(e) => setRem(Number(e.target.value))} className="w-full p-1.5 border border-[#dce2ea] rounded font-mono-num" /></div>
                <div><label className="block mb-1">Desp.</label><input type="number" value={despertares} onChange={(e) => setDespertares(Number(e.target.value))} className="w-full p-1.5 border border-[#dce2ea] rounded font-mono-num" /></div>
              </div>
              <div className="p-2.5 rounded bg-[#f8fafc] border border-[#dce2ea] font-mono-num text-[12px]">
                Vista previa: TST = <strong>{tstCalc} min</strong> · WASO = <strong>{wasoCalc} min</strong> · SE = <strong>{seCalc}%</strong> · %N3 = <strong>{pctN3Calc}%</strong>
              </div>
              <button type="submit" className="px-4 py-2 bg-[#0f766e] text-white text-[13px] font-semibold rounded cursor-pointer">
                Guardar noche y actualizar Data Mart
              </button>
              {nightErr && <div className="p-2 bg-[#fef2f2] text-[#b91c1c] rounded">{nightErr}</div>}
              {nightResult && (
                <div className="p-2 bg-[#ecfdf5] text-[#15803d] rounded font-mono-num">
                  Noche registrada · SE {nightResult.kpis.se_pct}% · %N3 {nightResult.kpis.pct_n3}%
                </div>
              )}
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
