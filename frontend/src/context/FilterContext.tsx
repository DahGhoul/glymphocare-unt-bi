import React, { createContext, useContext, useState } from 'react';
import type { GlobalFilters } from '../types/glympho';

const EMPTY_FILTERS: GlobalFilters = {
  date_from: '',
  date_to: '',
  facultad: '',
  carrera: '',
  ciclo: '',
  pantallas: '',
  cafeina: '',
  ejercicio: '',
  estres: '',
};

interface FilterContextValue {
  filters: GlobalFilters;
  setFilter: (key: keyof GlobalFilters, value: string) => void;
  resetFilters: () => void;
  activeCount: number;
}

const FilterContext = createContext<FilterContextValue | null>(null);

export const FilterProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [filters, setFilters] = useState<GlobalFilters>(EMPTY_FILTERS);

  const setFilter = (key: keyof GlobalFilters, value: string) => {
    setFilters((prev) => {
      const next = { ...prev, [key]: value };
      if (key === 'facultad') next.carrera = '';
      return next;
    });
  };

  const resetFilters = () => setFilters(EMPTY_FILTERS);

  const activeCount = Object.values(filters).filter((v) => v !== '').length;

  return (
    <FilterContext.Provider value={{ filters, setFilter, resetFilters, activeCount }}>
      {children}
    </FilterContext.Provider>
  );
};

export function useFilters(): FilterContextValue {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error('useFilters must be used inside FilterProvider');
  return ctx;
}
