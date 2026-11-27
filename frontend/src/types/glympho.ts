export type UserRole = 'participante' | 'investigador' | 'analista' | 'admin';

export interface AuthUser {
  id: number;
  email: string;
  nombre_display: string;
  rol: UserRole;
  participante_codigo?: string | null;
}

export interface GlobalFilters {
  date_from: string;
  date_to: string;
  facultad: string;
  carrera: string;
  ciclo: string;
  pantallas: string;
  cafeina: string;
  ejercicio: string;
  estres: string;
}

export interface FilterOptions {
  facultades: string[];
  carreras: { facultad: string; carrera: string }[];
  ciclos: number[];
  min_fecha: string | null;
  max_fecha: string | null;
}

export interface RuleAlert {
  rule_id: number;
  kpi_codigo: string;
  valor_actual: number;
  operador: string;
  umbral: number;
  severidad: 'info' | 'alerta' | 'critico';
  titulo: string;
  texto_recomendacion: string;
}

export interface ReportRow {
  type: 'group' | 'item' | 'subtotal' | 'total';
  label: string;
  values: number[];
  bad: boolean[];
}

export interface ReportData {
  id: string;
  title: string;
  subtitle: string;
  unit: string;
  group_header: string;
  group_start: number;
  group_span: number;
  columns: string[];
  decimals: number[];
  rows: ReportRow[];
  n_sample: number;
  note: string;
}

export interface AiInterpretation {
  provider_used: string;
  resumen_ejecutivo: string;
  componentes_criticos: string;
  analisis_glinfatico_n3: string;
  plan_accion: string[];
  aviso_no_clinico: string;
}
