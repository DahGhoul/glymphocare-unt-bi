-- ============================================================================
-- GlymphoCare - Esquema Transaccional (OLTP)
-- Motor: PostgreSQL 16 (compatible 100% con Amazon RDS for PostgreSQL)
-- Grupo G5 - Inteligencia de Negocios UNT (2026)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS glympho_oltp;
SET search_path TO glympho_oltp, public;

-- 1. Usuarios y roles de acceso (RF-01, RNF-03)
CREATE TABLE IF NOT EXISTS usuario (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(160) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    nombre_display  VARCHAR(120) NOT NULL,
    rol             VARCHAR(20) NOT NULL CHECK (rol IN ('participante', 'investigador', 'analista', 'admin')),
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Participantes anonimizados por codigo (RNF-04)
CREATE TABLE IF NOT EXISTS participante (
    id              SERIAL PRIMARY KEY,
    usuario_id      INTEGER UNIQUE REFERENCES usuario(id) ON DELETE SET NULL,
    codigo          VARCHAR(20) NOT NULL UNIQUE,
    edad            SMALLINT NOT NULL CHECK (edad BETWEEN 16 AND 65),
    sexo            VARCHAR(20) NOT NULL CHECK (sexo IN ('F', 'M', 'Otro')),
    facultad        VARCHAR(80) NOT NULL,
    carrera         VARCHAR(100) NOT NULL,
    ciclo           SMALLINT NOT NULL CHECK (ciclo BETWEEN 1 AND 12),
    fecha_registro  DATE NOT NULL DEFAULT CURRENT_DATE
);

-- 3. Consentimiento informado voluntario (RF-01, RNF-04)
CREATE TABLE IF NOT EXISTS consentimiento (
    id              SERIAL PRIMARY KEY,
    participante_id INTEGER NOT NULL REFERENCES participante(id) ON DELETE CASCADE,
    version_texto   VARCHAR(30) NOT NULL DEFAULT 'v1.0-UNT-2026',
    aceptado        BOOLEAN NOT NULL CHECK (aceptado = TRUE),
    fecha           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Cabecera del cuestionario PSQI (19 items)
CREATE TABLE IF NOT EXISTS cuestionario_psqi (
    id                  SERIAL PRIMARY KEY,
    participante_id     INTEGER NOT NULL REFERENCES participante(id) ON DELETE CASCADE,
    fecha               DATE NOT NULL,
    hora_acostarse      TIME NOT NULL,
    minutos_latencia    SMALLINT NOT NULL CHECK (minutos_latencia BETWEEN 0 AND 360),
    hora_levantarse     TIME NOT NULL,
    horas_sueno_real    NUMERIC(4,2) NOT NULL CHECK (horas_sueno_real > 0 AND horas_sueno_real <= 24),
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (participante_id, fecha)
);

-- 5. Respuestas codificadas (0-3) del PSQI (items 5a-5j, 6, 7, 8, 9)
CREATE TABLE IF NOT EXISTS respuesta_psqi (
    id          SERIAL PRIMARY KEY,
    psqi_id     INTEGER NOT NULL REFERENCES cuestionario_psqi(id) ON DELETE CASCADE,
    item_codigo VARCHAR(4) NOT NULL CHECK (
        item_codigo IN ('5a','5b','5c','5d','5e','5f','5g','5h','5i','5j','6','7','8','9')
    ),
    valor       SMALLINT NOT NULL CHECK (valor BETWEEN 0 AND 3),
    UNIQUE (psqi_id, item_codigo)
);

-- 6. Cabecera del cuestionario ESS (Escala de Somnolencia de Epworth)
CREATE TABLE IF NOT EXISTS cuestionario_ess (
    id              SERIAL PRIMARY KEY,
    participante_id INTEGER NOT NULL REFERENCES participante(id) ON DELETE CASCADE,
    fecha           DATE NOT NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (participante_id, fecha)
);

-- 7. Respuestas a las 8 situaciones cotidianas del ESS (0-3)
CREATE TABLE IF NOT EXISTS respuesta_ess (
    id              SERIAL PRIMARY KEY,
    ess_id          INTEGER NOT NULL REFERENCES cuestionario_ess(id) ON DELETE CASCADE,
    situacion_num   SMALLINT NOT NULL CHECK (situacion_num BETWEEN 1 AND 8),
    valor           SMALLINT NOT NULL CHECK (valor BETWEEN 0 AND 3),
    UNIQUE (ess_id, situacion_num)
);

-- 8. Habitos de higiene del sueno (RI-10)
CREATE TABLE IF NOT EXISTS habito_sueno (
    id                      SERIAL PRIMARY KEY,
    participante_id         INTEGER NOT NULL REFERENCES participante(id) ON DELETE CASCADE,
    fecha                   DATE NOT NULL,
    pantallas_antes_dormir  VARCHAR(20) NOT NULL CHECK (pantallas_antes_dormir IN ('>1h', '<=1h')),
    cafeina_nivel           VARCHAR(30) NOT NULL CHECK (cafeina_nivel IN ('despues_14h', 'antes_14h_o_ninguna')),
    ejercicio_nivel         VARCHAR(20) NOT NULL CHECK (ejercicio_nivel IN ('>=3_dias', '<3_dias')),
    estres_nivel            VARCHAR(15) NOT NULL CHECK (estres_nivel IN ('alto', 'medio', 'bajo')),
    regularidad_horarios    VARCHAR(15) NOT NULL CHECK (regularidad_horarios IN ('regular', 'irregular')),
    creado_en               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (participante_id, fecha)
);

-- 9. Control de cargas CSV de wearables (RF-03)
CREATE TABLE IF NOT EXISTS carga_archivo (
    id                      SERIAL PRIMARY KEY,
    participante_id         INTEGER REFERENCES participante(id) ON DELETE SET NULL,
    usuario_id              INTEGER REFERENCES usuario(id) ON DELETE SET NULL,
    nombre_archivo          VARCHAR(200) NOT NULL,
    s3_key                  VARCHAR(300),
    registros_totales       INTEGER NOT NULL DEFAULT 0,
    registros_validos       INTEGER NOT NULL DEFAULT 0,
    registros_rechazados    INTEGER NOT NULL DEFAULT 0,
    estado                  VARCHAR(30) NOT NULL CHECK (estado IN ('procesado', 'parcial', 'rechazado', 'error')),
    detalle_errores         JSONB NOT NULL DEFAULT '[]'::jsonb,
    fecha                   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. Registros objetivos de sueno por noche (RI-04..RI-09)
CREATE TABLE IF NOT EXISTS registro_sueno_noche (
    id              SERIAL PRIMARY KEY,
    participante_id INTEGER NOT NULL REFERENCES participante(id) ON DELETE CASCADE,
    fecha           DATE NOT NULL,
    tib_min         NUMERIC(6,2) NOT NULL CHECK (tib_min > 0 AND tib_min <= 1440),
    tst_min         NUMERIC(6,2) NOT NULL CHECK (tst_min > 0 AND tst_min <= 1440),
    sol_min         NUMERIC(6,2) NOT NULL CHECK (sol_min >= 0 AND sol_min <= 360),
    despertares     SMALLINT NOT NULL CHECK (despertares >= 0 AND despertares <= 50),
    min_n1          NUMERIC(6,2) NOT NULL CHECK (min_n1 >= 0),
    min_n2          NUMERIC(6,2) NOT NULL CHECK (min_n2 >= 0),
    min_n3          NUMERIC(6,2) NOT NULL CHECK (min_n3 >= 0),
    min_rem         NUMERIC(6,2) NOT NULL CHECK (min_rem >= 0),
    origen          VARCHAR(15) NOT NULL CHECK (origen IN ('csv', 'manual', 'seed')),
    carga_id        INTEGER REFERENCES carga_archivo(id) ON DELETE SET NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (participante_id, fecha),
    CHECK (tst_min + sol_min <= tib_min + 0.01),
    CHECK (ABS((min_n1 + min_n2 + min_n3 + min_rem) - tst_min) <= 1.0)
);

-- 11. Reglas y umbrales configurables por administrador (RF-08, RF-11, RNF-06)
CREATE TABLE IF NOT EXISTS recomendacion_regla (
    id                  SERIAL PRIMARY KEY,
    kpi_codigo          VARCHAR(20) NOT NULL CHECK (
        kpi_codigo IN ('PSQI', 'ESS', 'SE', 'SOL', 'WASO', 'TST', 'DESPERTARES', 'PCT_N3')
    ),
    operador            VARCHAR(4) NOT NULL CHECK (operador IN ('>', '>=', '<', '<=')),
    umbral              NUMERIC(8,2) NOT NULL,
    severidad           VARCHAR(15) NOT NULL CHECK (severidad IN ('info', 'alerta', 'critico')),
    titulo              VARCHAR(140) NOT NULL,
    texto_recomendacion TEXT NOT NULL,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. Historial de reportes exportados (RF-09)
CREATE TABLE IF NOT EXISTS reporte_generado (
    id              SERIAL PRIMARY KEY,
    usuario_id      INTEGER REFERENCES usuario(id) ON DELETE SET NULL,
    tipo            VARCHAR(40) NOT NULL,
    formato         VARCHAR(10) NOT NULL CHECK (formato IN ('pdf', 'csv')),
    parametros_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    s3_key          VARCHAR(300),
    fecha           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 13. Configuracion del sistema (IA generativa, metadatos)
CREATE TABLE IF NOT EXISTS configuracion_sistema (
    clave           VARCHAR(80) PRIMARY KEY,
    valor           TEXT NOT NULL,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indices de rendimiento para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_psqi_part_fecha ON cuestionario_psqi(participante_id, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_ess_part_fecha ON cuestionario_ess(participante_id, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_habito_part_fecha ON habito_sueno(participante_id, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_noche_part_fecha ON registro_sueno_noche(participante_id, fecha DESC);
