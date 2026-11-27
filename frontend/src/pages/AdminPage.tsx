import React, { useEffect, useState } from 'react';
import { KeyRound, Play, Plus, Trash2 } from 'lucide-react';
import { apiFetch } from '../services/api';

interface Rule {
  id: number;
  kpi_codigo: string;
  operador: string;
  umbral: number;
  severidad: string;
  titulo: string;
  texto_recomendacion: string;
  activo: boolean;
}

export const AdminPage: React.FC = () => {
  const [rules, setRules] = useState<Rule[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [aiStatus, setAiStatus] = useState<{ configured: boolean; model: string; masked_key: string } | null>(null);
  const [geminiKey, setGeminiKey] = useState('');
  const [etlMsg, setEtlMsg] = useState('');

  // Nueva regla
  const [kpi, setKpi] = useState('PSQI');
  const [op, setOp] = useState('>');
  const [umbral, setUmbral] = useState(5);
  const [sev, setSev] = useState('critico');
  const [titulo, setTitulo] = useState('');
  const [texto, setTexto] = useState('');

  const loadAll = () => {
    apiFetch<Rule[]>('/api/admin/rules').then(setRules);
    apiFetch<any[]>('/api/admin/users').then(setUsers);
    apiFetch<any[]>('/api/admin/etl/logs').then(setLogs);
    apiFetch<any>('/api/admin/ai-config').then(setAiStatus);
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    await apiFetch('/api/admin/rules', {
      method: 'POST',
      body: JSON.stringify({
        kpi_codigo: kpi,
        operador: op,
        umbral,
        severidad: sev,
        titulo,
        texto_recomendacion: texto,
        activo: true,
      }),
    });
    setTitulo('');
    setTexto('');
    loadAll();
  };

  const handleDeleteRule = async (id: number) => {
    await apiFetch(`/api/admin/rules/${id}`, { method: 'DELETE' });
    loadAll();
  };

  const handleRunEtl = async () => {
    setEtlMsg('Ejecutando ETL...');
    const res = await apiFetch<any>('/api/admin/etl/run', { method: 'POST' });
    setEtlMsg(`ETL #${res.log_id}: ${res.estado} (${res.filas_cargadas} filas cargadas)`);
    loadAll();
  };

  const handleSaveAiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    await apiFetch('/api/admin/ai-config', {
      method: 'PUT',
      body: JSON.stringify({ gemini_api_key: geminiKey }),
    });
    setGeminiKey('');
    loadAll();
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-bold text-[#14202b]">Administración de Umbrales, Usuarios y ETL</h1>
          <p className="text-[13px] text-[#5a6877]">
            Configuración dinámica de reglas (RNF-06), auditoría del proceso ETL (RETL-06) y proveedor IA gratuito.
          </p>
        </div>
        <button
          type="button"
          onClick={handleRunEtl}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#0f766e] text-white text-[13px] font-semibold rounded cursor-pointer"
        >
          <Play size={14} />
          Ejecutar ETL ahora
        </button>
      </div>

      {etlMsg && (
        <div className="p-3 rounded bg-[#e6f4f3] border border-[#99f6e4] text-[13px] text-[#0f766e] font-mono-num">
          {etlMsg}
        </div>
      )}

      <div className="bg-white border border-[#dce2ea] rounded-lg p-4">
        <div className="flex items-center gap-2 mb-2">
          <KeyRound size={16} className="text-[#3b4990]" />
          <h3 className="text-[14px] font-semibold text-[#14202b]">Configuración IA Generativa (Google Gemini Gratuito)</h3>
        </div>
        <p className="text-[12px] text-[#5a6877] mb-3">
          Estado actual:{' '}
          <strong className="font-mono-num text-[#14202b]">
            {aiStatus?.configured ? `Configurada (${aiStatus.masked_key})` : 'Sin API Key (usando síntesis local basada en reglas)'}
          </strong>
        </p>
        <form onSubmit={handleSaveAiKey} className="flex flex-wrap gap-2">
          <input
            type="password"
            placeholder="Pega tu Google Gemini API Key (AIza...)"
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
            className="flex-1 min-w-[240px] px-3 py-1.5 text-[13px] border border-[#dce2ea] rounded"
          />
          <button type="submit" className="px-4 py-1.5 bg-[#3b4990] text-white text-[13px] font-medium rounded cursor-pointer">
            Guardar clave
          </button>
        </form>
      </div>

      <div className="bg-white border border-[#dce2ea] rounded-lg p-4">
        <h3 className="text-[14px] font-semibold text-[#14202b] mb-3">Reglas y Umbrales por KPI (recomendacion_regla)</h3>
        <div className="overflow-x-auto mb-4">
          <table className="w-full text-[12.5px] border-collapse">
            <thead>
              <tr className="border-b border-[#dce2ea] text-left text-[11px] uppercase text-[#5a6877]">
                <th className="py-2 pr-3">KPI</th>
                <th className="py-2 pr-3">Condición</th>
                <th className="py-2 pr-3">Severidad</th>
                <th className="py-2 pr-3">Título</th>
                <th className="py-2 pr-3">Recomendación</th>
                <th className="py-2 text-right">Eliminar</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className="border-b border-[#f1f5f9]">
                  <td className="py-2 pr-3 font-mono-num font-bold">{r.kpi_codigo}</td>
                  <td className="py-2 pr-3 font-mono-num">{r.operador} {r.umbral}</td>
                  <td className="py-2 pr-3 uppercase text-[11px]">{r.severidad}</td>
                  <td className="py-2 pr-3 font-medium">{r.titulo}</td>
                  <td className="py-2 pr-3 text-[#5a6877] max-w-[360px]">{r.texto_recomendacion}</td>
                  <td className="py-2 text-right">
                    <button type="button" onClick={() => handleDeleteRule(r.id)} className="text-[#b91c1c] p-1 cursor-pointer">
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <form onSubmit={handleCreateRule} className="grid grid-cols-1 md:grid-cols-6 gap-2 pt-3 border-t border-[#eef2f6] text-[12.5px]">
          <select value={kpi} onChange={(e) => setKpi(e.target.value)} className="p-1.5 border border-[#dce2ea] rounded">
            {['PSQI', 'ESS', 'SE', 'SOL', 'WASO', 'TST', 'PCT_N3', 'DESPERTARES'].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={op} onChange={(e) => setOp(e.target.value)} className="p-1.5 border border-[#dce2ea] rounded">
            {['>', '>=', '<', '<='].map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
          <input type="number" step="0.1" value={umbral} onChange={(e) => setUmbral(Number(e.target.value))} className="p-1.5 border border-[#dce2ea] rounded font-mono-num" />
          <select value={sev} onChange={(e) => setSev(e.target.value)} className="p-1.5 border border-[#dce2ea] rounded">
            <option value="info">info</option>
            <option value="alerta">alerta</option>
            <option value="critico">critico</option>
          </select>
          <input type="text" required placeholder="Título de alerta" value={titulo} onChange={(e) => setTitulo(e.target.value)} className="p-1.5 border border-[#dce2ea] rounded md:col-span-2" />
          <input type="text" required placeholder="Texto de recomendación..." value={texto} onChange={(e) => setTexto(e.target.value)} className="p-1.5 border border-[#dce2ea] rounded md:col-span-5" />
          <button type="submit" className="inline-flex items-center justify-center gap-1 px-3 py-1.5 bg-[#0f766e] text-white font-semibold rounded cursor-pointer">
            <Plus size={14} /> Agregar
          </button>
        </form>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-[#dce2ea] rounded-lg p-4">
          <h3 className="text-[14px] font-semibold text-[#14202b] mb-2">Historial de Ejecuciones ETL (etl_ejecucion_log)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[12px] border-collapse">
              <thead>
                <tr className="border-b border-[#dce2ea] text-left text-[11px] uppercase text-[#5a6877]">
                  <th className="py-1.5 pr-2">ID</th>
                  <th className="py-1.5 pr-2">Origen</th>
                  <th className="py-1.5 pr-2">Estado</th>
                  <th className="py-1.5 text-right">Cargadas</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} className="border-b border-[#f1f5f9]">
                    <td className="py-1.5 pr-2 font-mono-num">#{l.id}</td>
                    <td className="py-1.5 pr-2">{l.origen}</td>
                    <td className="py-1.5 pr-2 font-mono-num">{l.estado}</td>
                    <td className="py-1.5 text-right font-mono-num">{l.filas_cargadas}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-white border border-[#dce2ea] rounded-lg p-4">
          <h3 className="text-[14px] font-semibold text-[#14202b] mb-2">Usuarios y Roles del Sistema</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[12px] border-collapse">
              <thead>
                <tr className="border-b border-[#dce2ea] text-left text-[11px] uppercase text-[#5a6877]">
                  <th className="py-1.5 pr-2">Correo</th>
                  <th className="py-1.5 pr-2">Nombre</th>
                  <th className="py-1.5">Rol</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-[#f1f5f9]">
                    <td className="py-1.5 pr-2 font-mono-num">{u.email}</td>
                    <td className="py-1.5 pr-2">{u.nombre_display}</td>
                    <td className="py-1.5">
                      <select
                        value={u.rol}
                        onChange={async (e) => {
                          await apiFetch(`/api/admin/users/${u.id}/role`, {
                            method: 'PATCH',
                            body: JSON.stringify({ rol: e.target.value }),
                          });
                          loadAll();
                        }}
                        className="p-1 border border-[#dce2ea] rounded text-[11.5px]"
                      >
                        {['participante', 'investigador', 'analista', 'admin'].map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
