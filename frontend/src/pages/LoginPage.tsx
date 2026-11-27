import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../services/api';
import type { AuthUser } from '../types/glympho';

const FACULTIES: Record<string, string[]> = {
  'Ingeniería': ['Ing. de Sistemas', 'Ing. Industrial', 'Ing. Civil'],
  'Ciencias Económicas': ['Administración', 'Contabilidad'],
  'Ciencias de la Salud': ['Psicología', 'Enfermería'],
};

const DEMO_ACCOUNTS = [
  { label: 'Admin BI', email: 'admin@glymphocare.edu.pe' },
  { label: 'Analista', email: 'analista@glymphocare.edu.pe' },
  { label: 'Investigador', email: 'investigador@glymphocare.edu.pe' },
  { label: 'Participante', email: 'estudiante@glymphocare.edu.pe' },
];

export const LoginPage: React.FC = () => {
  const { login, setSession } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('analista@glymphocare.edu.pe');
  const [password, setPassword] = useState('Glympho2026!');
  const [nombre, setNombre] = useState('');
  const [edad, setEdad] = useState(21);
  const [sexo, setSexo] = useState('F');
  const [facultad, setFacultad] = useState('Ingeniería');
  const [carrera, setCarrera] = useState('Ing. de Sistemas');
  const [ciclo, setCiclo] = useState(6);
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesión');
    } finally {
      setBusy(false);
    }
  };

  const handleQuickDemo = async (demoEmail: string) => {
    setError('');
    setBusy(true);
    try {
      await login(demoEmail, 'Glympho2026!');
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de acceso demo');
    } finally {
      setBusy(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!consent) {
      setError('Debe aceptar el consentimiento informado voluntario.');
      return;
    }
    setBusy(true);
    try {
      const data = await apiFetch<{ access_token: string; user: AuthUser }>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          nombre_display: nombre,
          edad,
          sexo,
          facultad,
          carrera,
          ciclo,
          consentimiento_aceptado: consent,
        }),
      });
      setSession(data.access_token, data.user);
      navigate('/captura');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error en registro');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f6f8fa] flex items-center justify-center p-4">
      <div className="w-full max-w-[440px] bg-white border border-[#dce2ea] rounded-lg p-6">
        <div className="border-b border-[#eef2f6] pb-4 mb-5">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-[#0f766e]">
            Universidad Nacional de Trujillo · Ingeniería de Sistemas
          </div>
          <h1 className="text-[22px] font-bold text-[#14202b] mt-1">
            Glympho<span className="text-[#0f766e]">Care</span>
          </h1>
          <p className="text-[13px] text-[#5a6877] mt-0.5">
            Plataforma analítica de higiene del sueño y limpieza cerebral (%N3)
          </p>
        </div>

        <div className="grid grid-cols-2 gap-1 p-1 bg-[#f1f5f9] rounded-md mb-4">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(''); }}
            className={`py-1.5 text-[13px] font-medium rounded cursor-pointer ${
              mode === 'login' ? 'bg-white text-[#14202b] border border-[#dce2ea]' : 'text-[#5a6877]'
            }`}
          >
            Iniciar sesión
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(''); setEmail(''); setPassword(''); }}
            className={`py-1.5 text-[13px] font-medium rounded cursor-pointer ${
              mode === 'register' ? 'bg-white text-[#14202b] border border-[#dce2ea]' : 'text-[#5a6877]'
            }`}
          >
            Registro cohorte
          </button>
        </div>

        {error && (
          <div className="mb-3 px-3 py-2 text-[12px] text-[#b91c1c] bg-[#fef2f2] border border-[#fecaca] rounded">
            {error}
          </div>
        )}

        {mode === 'login' ? (
          <form onSubmit={handleLogin} className="space-y-3">
            <div>
              <label className="block text-[12px] font-medium text-[#334155] mb-1">Correo institucional o usuario</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 text-[13px] border border-[#dce2ea] rounded bg-[#f8fafc] focus:bg-white focus:outline-none focus:border-[#0f766e]"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-[#334155] mb-1">Contraseña</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 text-[13px] border border-[#dce2ea] rounded bg-[#f8fafc] focus:bg-white focus:outline-none focus:border-[#0f766e]"
              />
            </div>
            <button
              type="submit"
              disabled={busy}
              className="w-full py-2 bg-[#0f766e] hover:bg-[#0d625b] text-white text-[13px] font-semibold rounded cursor-pointer disabled:opacity-60"
            >
              {busy ? 'Validando acceso...' : 'Ingresar a GlymphoCare'}
            </button>

            <div className="pt-3 border-t border-[#eef2f6]">
              <div className="text-[11px] font-medium text-[#5a6877] mb-2">
                Acceso rápido por rol (demostración):
              </div>
              <div className="grid grid-cols-2 gap-1.5">
                {DEMO_ACCOUNTS.map((d) => (
                  <button
                    key={d.email}
                    type="button"
                    disabled={busy}
                    onClick={() => handleQuickDemo(d.email)}
                    className="text-[12px] px-2.5 py-1.5 rounded border border-[#dce2ea] bg-[#f8fafc] hover:bg-[#e6f4f3] hover:border-[#0f766e] text-[#14202b] font-medium cursor-pointer"
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>
          </form>
        ) : (
          <form onSubmit={handleRegister} className="space-y-2.5">
            <div>
              <label className="block text-[12px] font-medium text-[#334155] mb-1">Nombre (se anonimiza como código UNT)</label>
              <input
                type="text"
                required
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                className="w-full px-3 py-1.5 text-[13px] border border-[#dce2ea] rounded"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[12px] font-medium text-[#334155] mb-1">Correo</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-1.5 text-[13px] border border-[#dce2ea] rounded"
                />
              </div>
              <div>
                <label className="block text-[12px] font-medium text-[#334155] mb-1">Contraseña (mín. 6)</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-1.5 text-[13px] border border-[#dce2ea] rounded"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block text-[12px] font-medium text-[#334155] mb-1">Edad</label>
                <input
                  type="number"
                  min={16}
                  max={65}
                  value={edad}
                  onChange={(e) => setEdad(Number(e.target.value))}
                  className="w-full px-2.5 py-1.5 text-[13px] border border-[#dce2ea] rounded"
                />
              </div>
              <div>
                <label className="block text-[12px] font-medium text-[#334155] mb-1">Sexo</label>
                <select value={sexo} onChange={(e) => setSexo(e.target.value)} className="w-full px-2 py-1.5 text-[13px] border border-[#dce2ea] rounded">
                  <option value="F">F</option>
                  <option value="M">M</option>
                  <option value="Otro">Otro</option>
                </select>
              </div>
              <div>
                <label className="block text-[12px] font-medium text-[#334155] mb-1">Ciclo</label>
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={ciclo}
                  onChange={(e) => setCiclo(Number(e.target.value))}
                  className="w-full px-2.5 py-1.5 text-[13px] border border-[#dce2ea] rounded"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[12px] font-medium text-[#334155] mb-1">Facultad</label>
                <select
                  value={facultad}
                  onChange={(e) => {
                    const f = e.target.value;
                    setFacultad(f);
                    setCarrera(FACULTIES[f][0]);
                  }}
                  className="w-full px-2 py-1.5 text-[13px] border border-[#dce2ea] rounded"
                >
                  {Object.keys(FACULTIES).map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[12px] font-medium text-[#334155] mb-1">Carrera</label>
                <select
                  value={carrera}
                  onChange={(e) => setCarrera(e.target.value)}
                  className="w-full px-2 py-1.5 text-[13px] border border-[#dce2ea] rounded"
                >
                  {FACULTIES[facultad].map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
            </div>

            <label className="flex items-start gap-2 p-2.5 rounded bg-[#f8fafc] border border-[#dce2ea] text-[12px] text-[#334155] cursor-pointer">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5 accent-[#0f766e]"
              />
              <span>
                Acepto participar voluntariamente en el estudio académico de higiene del sueño. Mis datos serán tratados de forma anonimizada y no constituyen diagnóstico clínico.
              </span>
            </label>

            <button
              type="submit"
              disabled={busy}
              className="w-full py-2 bg-[#0f766e] hover:bg-[#0d625b] text-white text-[13px] font-semibold rounded cursor-pointer"
            >
              {busy ? 'Creando código...' : 'Registrarme en la cohorte'}
            </button>
          </form>
        )}

        <div className="mt-4 pt-3 border-t border-[#eef2f6] flex items-center gap-2 text-[11px] text-[#5a6877]">
          <ShieldCheck size={14} className="text-[#0f766e] shrink-0" />
          <span>Datos anonimizados por código · Sin diagnóstico médico ni entrenamiento de modelos predictivos.</span>
        </div>
      </div>
    </div>
  );
};
