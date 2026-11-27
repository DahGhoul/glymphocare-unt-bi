-- ============================================================================
-- GlymphoCare - Semilla inicial de reglas clinicas (RF-08, RF-11, RNF-06)
-- Basada en la matriz de umbrales de la Seccion 6.1 del proyecto
-- ============================================================================

SET search_path TO glympho_oltp, public;

INSERT INTO recomendacion_regla (kpi_codigo, operador, umbral, severidad, titulo, texto_recomendacion, activo)
SELECT * FROM (VALUES
    ('PSQI', '>', 5.00, 'critico',
     'Mala calidad subjetiva de sueno (PSQI > 5)',
     'Establecer horario fijo para acostarse y despertarse incluso los fines de semana, y revisar los componentes PSQI con puntuacion >= 2.',
     TRUE),
    ('ESS', '>', 10.00, 'alerta',
     'Somnolencia diurna excesiva (ESS > 10)',
     'Priorizar 7 a 8 horas de descanso nocturno continuo y evitar sesiones de estudio nocturno prolongadas antes de evaluaciones.',
     TRUE),
    ('SOL', '>', 20.00, 'alerta',
     'Latencia de inicio prolongada (SOL > 20 min)',
     'Suspender pantallas emisoras de luz azul al menos 60 minutos antes de acostarse y evitar cafeina despues de las 14:00 h.',
     TRUE),
    ('SOL', '>', 30.00, 'critico',
     'Latencia clinicamente alterada (SOL > 30 min)',
     'Aplicar rutina de desaceleracion de 30 minutos previa al sueno (luz tenue, lectura en papel o respiracion diafragmatica) y no permanecer en cama despierto mas de 25 minutos.',
     TRUE),
    ('WASO', '>', 40.00, 'alerta',
     'Fragmentacion nocturna elevada (WASO > 40 min)',
     'Mantener el dormitorio fresco (18-20 C), oscuro y silencioso; limitar liquidos en las 2 horas previas a dormir.',
     TRUE),
    ('TST', '<', 420.00, 'critico',
     'Duracion insuficiente de sueno (TST < 7 horas)',
     'Adelantar gradualmente la hora de acostarse en bloques de 15-20 minutos cada 3 dias hasta alcanzar >= 420 minutos efectivos.',
     TRUE),
    ('SE', '<', 85.00, 'alerta',
     'Eficiencia del sueno por debajo de meta (SE < 85%)',
     'Reservar la cama exclusivamente para dormir (evitar estudiar, comer o usar el celular en ella) para consolidar la eficiencia.',
     TRUE),
    ('PCT_N3', '<', 15.00, 'alerta',
     'Baja proporcion de sueno profundo N3 (< 15%)',
     'Incorporar actividad fisica aerobica moderada >= 3 dias/semana (preferiblemente antes de las 19:00 h) y reducir estres nocturno para potenciar la ventana glinfatica.',
     TRUE),
    ('DESPERTARES', '>', 3.00, 'info',
     'Despertares nocturnos frecuentes (> 3 por noche)',
     'Revisar factores ambientales de ruido/temperatura y evitar cenas copiosas o cafeina tardia que fragmenten los ciclos NREM.',
     TRUE)
) AS v(kpi_codigo, operador, umbral, severidad, titulo, texto_recomendacion, activo)
WHERE NOT EXISTS (SELECT 1 FROM recomendacion_regla);

INSERT INTO configuracion_sistema (clave, valor)
VALUES ('gemini_model', 'gemini-2.0-flash')
ON CONFLICT (clave) DO NOTHING;
