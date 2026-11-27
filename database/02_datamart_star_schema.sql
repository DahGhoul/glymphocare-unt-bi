-- ============================================================================
-- GlymphoCare - Data Mart Dimensional (Esquema en Estrella)
-- Motor: PostgreSQL 16 (compatible 100% con Amazon RDS for PostgreSQL)
-- Grupo G5 - Inteligencia de Negocios UNT (2026)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS glympho_dw;
SET search_path TO glympho_dw, public;

-- Dimension 1: Tiempo
CREATE TABLE IF NOT EXISTS dim_tiempo (
    tiempo_key      SERIAL PRIMARY KEY,
    fecha           DATE NOT NULL UNIQUE,
    dia_semana_num  SMALLINT NOT NULL CHECK (dia_semana_num BETWEEN 1 AND 7), -- 1=Lunes .. 7=Domingo
    dia_semana      VARCHAR(15) NOT NULL,
    es_fin_semana   BOOLEAN NOT NULL,
    semana_anio     SMALLINT NOT NULL,
    mes             SMALLINT NOT NULL,
    mes_nombre      VARCHAR(15) NOT NULL,
    anio            SMALLINT NOT NULL,
    ciclo_academico VARCHAR(20) NOT NULL
);

-- Dimension 2: Participante (anonimizado)
CREATE TABLE IF NOT EXISTS dim_participante (
    participante_key     SERIAL PRIMARY KEY,
    participante_id_oltp INTEGER NOT NULL UNIQUE,
    codigo               VARCHAR(20) NOT NULL UNIQUE,
    edad                 SMALLINT NOT NULL,
    rango_edad           VARCHAR(20) NOT NULL,
    sexo                 VARCHAR(20) NOT NULL,
    ciclo                SMALLINT NOT NULL
);

-- Dimension 3: Carrera y Facultad
CREATE TABLE IF NOT EXISTS dim_carrera (
    carrera_key SERIAL PRIMARY KEY,
    carrera     VARCHAR(100) NOT NULL UNIQUE,
    facultad    VARCHAR(80) NOT NULL
);

-- Dimension 4: Perfil de Habitos de Higiene del Sueno
CREATE TABLE IF NOT EXISTS dim_habito (
    habito_key              SERIAL PRIMARY KEY,
    uso_pantallas           VARCHAR(20) NOT NULL,
    cafeina                 VARCHAR(30) NOT NULL,
    ejercicio               VARCHAR(20) NOT NULL,
    estres                  VARCHAR(15) NOT NULL,
    regularidad_horarios    VARCHAR(15) NOT NULL,
    UNIQUE (uso_pantallas, cafeina, ejercicio, estres, regularidad_horarios)
);

-- Tabla de Hechos 1: Sueno Objetivo por Noche
-- Granularidad: un participante por noche registrada
CREATE TABLE IF NOT EXISTS fact_sueno_noche (
    sueno_noche_key     BIGSERIAL PRIMARY KEY,
    tiempo_key          INTEGER NOT NULL REFERENCES dim_tiempo(tiempo_key),
    participante_key    INTEGER NOT NULL REFERENCES dim_participante(participante_key),
    carrera_key         INTEGER NOT NULL REFERENCES dim_carrera(carrera_key),
    habito_key          INTEGER NOT NULL REFERENCES dim_habito(habito_key),
    tib_min             NUMERIC(6,2) NOT NULL,
    tst_min             NUMERIC(6,2) NOT NULL,
    sol_min             NUMERIC(6,2) NOT NULL,
    waso_min            NUMERIC(6,2) NOT NULL,
    despertares         SMALLINT NOT NULL,
    min_n1              NUMERIC(6,2) NOT NULL,
    min_n2              NUMERIC(6,2) NOT NULL,
    min_n3              NUMERIC(6,2) NOT NULL,
    min_rem             NUMERIC(6,2) NOT NULL,
    se_pct              NUMERIC(5,2) NOT NULL,
    pct_n3              NUMERIC(5,2) NOT NULL,
    indice_glinfatico   NUMERIC(5,3) NOT NULL, -- Metrica derivada exploratoria (IG)
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (participante_key, tiempo_key)
);

-- Tabla de Hechos 2: Evaluacion Subjetiva (PSQI + ESS)
-- Granularidad: un participante por fecha de aplicacion
CREATE TABLE IF NOT EXISTS fact_cuestionario (
    cuestionario_key    BIGSERIAL PRIMARY KEY,
    tiempo_key          INTEGER NOT NULL REFERENCES dim_tiempo(tiempo_key),
    participante_key    INTEGER NOT NULL REFERENCES dim_participante(participante_key),
    carrera_key         INTEGER NOT NULL REFERENCES dim_carrera(carrera_key),
    habito_key          INTEGER NOT NULL REFERENCES dim_habito(habito_key),
    c1_calidad          SMALLINT NOT NULL CHECK (c1_calidad BETWEEN 0 AND 3),
    c2_latencia         SMALLINT NOT NULL CHECK (c2_latencia BETWEEN 0 AND 3),
    c3_duracion         SMALLINT NOT NULL CHECK (c3_duracion BETWEEN 0 AND 3),
    c4_eficiencia       SMALLINT NOT NULL CHECK (c4_eficiencia BETWEEN 0 AND 3),
    c5_alteraciones     SMALLINT NOT NULL CHECK (c5_alteraciones BETWEEN 0 AND 3),
    c6_medicacion       SMALLINT NOT NULL CHECK (c6_medicacion BETWEEN 0 AND 3),
    c7_disfuncion       SMALLINT NOT NULL CHECK (c7_disfuncion BETWEEN 0 AND 3),
    psqi_global         SMALLINT NOT NULL CHECK (psqi_global BETWEEN 0 AND 21),
    ess_total           SMALLINT NOT NULL CHECK (ess_total BETWEEN 0 AND 24),
    clasificacion_psqi  VARCHAR(20) NOT NULL CHECK (clasificacion_psqi IN ('Buen dormidor', 'Mal dormidor')),
    clasificacion_ess   VARCHAR(25) NOT NULL,
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (participante_key, tiempo_key)
);

-- Log auditable del proceso ETL (RETL-06)
CREATE TABLE IF NOT EXISTS etl_ejecucion_log (
    id                  SERIAL PRIMARY KEY,
    origen              VARCHAR(40) NOT NULL,
    inicio              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fin                 TIMESTAMPTZ,
    estado              VARCHAR(20) NOT NULL CHECK (estado IN ('en_proceso', 'completado', 'completado_con_alertas', 'error')),
    filas_leidas        INTEGER NOT NULL DEFAULT 0,
    filas_cargadas      INTEGER NOT NULL DEFAULT 0,
    filas_rechazadas    INTEGER NOT NULL DEFAULT 0,
    detalle_errores     JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_fsn_tiempo ON fact_sueno_noche(tiempo_key);
CREATE INDEX IF NOT EXISTS idx_fsn_part ON fact_sueno_noche(participante_key);
CREATE INDEX IF NOT EXISTS idx_fsn_carrera ON fact_sueno_noche(carrera_key);
CREATE INDEX IF NOT EXISTS idx_fsn_habito ON fact_sueno_noche(habito_key);

CREATE INDEX IF NOT EXISTS idx_fc_tiempo ON fact_cuestionario(tiempo_key);
CREATE INDEX IF NOT EXISTS idx_fc_part ON fact_cuestionario(participante_key);
CREATE INDEX IF NOT EXISTS idx_fc_carrera ON fact_cuestionario(carrera_key);
CREATE INDEX IF NOT EXISTS idx_fc_habito ON fact_cuestionario(habito_key);
