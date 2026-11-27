import React, { useEffect, useState } from 'react';
import { Filter, RotateCcw } from 'lucide-react';
import { useFilters } from '../context/FilterContext';
import { apiFetch } from '../services/api';
import type { FilterOptions } from '../types/glympho';

export const FilterBar: React.FC = () => {
  const { filters, setFilter, resetFilters, activeCount } = useFilters();
  const [opts, setOpts] = useState<FilterOptions | null>(null);

  useEffect(() => {
    apiFetch<FilterOptions>('/api/dashboard/filters').then(setOpts).catch(() => {});
  }, []);

  const visibleCareers = (opts?.carreras || []).filter(
    (c) => !filters.facultad || c.facultad === filters.facultad
  );

  return (
    <div className="bg-white border border-[#dce2ea] rounded-lg px-3.5 py-2.5 mb-4">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="flex items-center gap-1.5 text-[12px] font-semibold text-[#14202b] mr-1">
          <Filter size={14} strokeWidth={1.75} className="text-[#0f766e]" />
          <span>Segmentación BI</span>
          {activeCount > 0 && (
            <span className="text-[11px] bg-[#e6f4f3] text-[#0f766e] px-1.5 py-0.5 rounded font-mono-num">
              {activeCount}
            </span>
          )}
        </div>

        <input
          type="date"
          aria-label="Fecha desde"
          value={filters.date_from}
          onChange={(e) => setFilter('date_from', e.target.value)}
          className="text-[12px] border border-[#dce2ea] rounded px-2 py-1 bg-[#f6f8fa] text-[#14202b]"
        />
        <span className="text-[11px] text-[#5a6877]">a</span>
        <input
          type="date"
          aria-label="Fecha hasta"
          value={filters.date_to}
          onChange={(e) => setFilter('date_to', e.target.value)}
          className="text-[12px] border border-[#dce2ea] rounded px-2 py-1 bg-[#f6f8fa] text-[#14202b]"
        />

        <select
          value={filters.facultad}
          onChange={(e) => setFilter('facultad', e.target.value)}
          className="text-[12px] border border-[#dce2ea] rounded px-2 py-1 bg-[#f6f8fa] text-[#14202b]"
        >
          <option value="">Todas las facultades</option>
          {(opts?.facultades || []).map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>

        <select
          value={filters.carrera}
          onChange={(e) => setFilter('carrera', e.target.value)}
          className="text-[12px] border border-[#dce2ea] rounded px-2 py-1 bg-[#f6f8fa] text-[#14202b]"
        >
          <option value="">Todas las carreras</option>
          {visibleCareers.map((c) => (
            <option key={c.carrera} value={c.carrera}>{c.carrera}</option>
          ))}
        </select>

        <select
          value={filters.ciclo}
          onChange={(e) => setFilter('ciclo', e.target.value)}
          className="text-[12px] border border-[#dce2ea] rounded px-2 py-1 bg-[#f6f8fa] text-[#14202b]"
        >
          <option value="">Todos los ciclos</option>
          {(opts?.ciclos || []).map((c) => (
            <option key={c} value={String(c)}>Ciclo {c}</option>
          ))}
        </select>

        <select
          value={filters.pantallas}
          onChange={(e) => setFilter('pantallas', e.target.value)}
          className="text-[12px] border border-[#dce2ea] rounded px-2 py-1 bg-[#f6f8fa] text-[#14202b]"
        >
          <option value="">Pantallas: todas</option>
          <option value=">1h">Pantallas &gt; 1h</option>
          <option value="<=1h">Pantallas &lt;= 1h</option>
        </select>

        {activeCount > 0 && (
          <button
            type="button"
            onClick={resetFilters}
            className="ml-auto inline-flex items-center gap-1 text-[12px] text-[#5a6877] hover:text-[#14202b] px-2 py-1 rounded border border-[#dce2ea] bg-white cursor-pointer"
          >
            <RotateCcw size={12} />
            Limpiar
          </button>
        )}
      </div>
    </div>
  );
};
