-- ============================================================================
-- GlymphoCare - Consultas SQL Demostrables contra el Data Mart (glympho_dw)
-- Demuestra los 8 KPIs oficiales + los 3 Reportes Tabulares del proyecto
-- ============================================================================

SET search_path TO glympho_dw, public;

-- ----------------------------------------------------------------------------
-- CONSULTA 1: Resumen Ejecutivo de los 8 KPIs Oficiales de la Cohorte
-- ----------------------------------------------------------------------------
WITH ultimo_cuestionario AS (
    SELECT DISTINCT ON (fc.participante_key)
        fc.participante_key,
        fc.psqi_global,
        fc.ess_total,
        fc.clasificacion_psqi
    FROM fact_cuestionario fc
    JOIN dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
    ORDER BY fc.participante_key, dt.fecha DESC
)
SELECT
    COUNT(DISTINCT uc.participante_key) AS total_participantes,
    ROUND(AVG(uc.psqi_global)::numeric, 2) AS kpi1_psqi_promedio,
    ROUND(AVG(uc.ess_total)::numeric, 2) AS kpi2_ess_promedio,
    ROUND(100.0 * SUM(CASE WHEN uc.clasificacion_psqi = 'Mal dormidor' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_malos_dormidores,
    ROUND(AVG(fsn.se_pct)::numeric, 1) AS kpi3_eficiencia_se_pct,
    ROUND(AVG(fsn.sol_min)::numeric, 1) AS kpi4_latencia_sol_min,
    ROUND(AVG(fsn.waso_min)::numeric, 1) AS kpi5_waso_min,
    ROUND(AVG(fsn.despertares)::numeric, 2) AS kpi6_despertares_prom,
    ROUND((AVG(fsn.tst_min) / 60.0)::numeric, 2) AS kpi7_tst_horas,
    ROUND(AVG(fsn.pct_n3)::numeric, 1) AS kpi8_sueno_profundo_n3_pct,
    ROUND(AVG(fsn.indice_glinfatico)::numeric, 3) AS metrica_derivada_ig
FROM ultimo_cuestionario uc
JOIN fact_sueno_noche fsn ON fsn.participante_key = uc.participante_key;

-- ----------------------------------------------------------------------------
-- CONSULTA 2 (REPORTE 1 / RR-03): Resumen de Cohorte por Facultad y Carrera
-- ----------------------------------------------------------------------------
WITH ultimo_psqi AS (
    SELECT DISTINCT ON (fc.participante_key)
        fc.participante_key,
        fc.carrera_key,
        fc.psqi_global,
        fc.clasificacion_psqi
    FROM fact_cuestionario fc
    JOIN dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
    ORDER BY fc.participante_key, dt.fecha DESC
)
SELECT
    dc.facultad,
    dc.carrera,
    SUM(CASE WHEN up.clasificacion_psqi = 'Buen dormidor' THEN 1 ELSE 0 END) AS buenos_dormidores,
    SUM(CASE WHEN up.clasificacion_psqi = 'Mal dormidor' THEN 1 ELSE 0 END) AS malos_dormidores,
    COUNT(*) AS total_participantes,
    ROUND(100.0 * SUM(CASE WHEN up.clasificacion_psqi = 'Mal dormidor' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_malos_dormidores
FROM ultimo_psqi up
JOIN dim_carrera dc ON dc.carrera_key = up.carrera_key
GROUP BY ROLLUP (dc.facultad, dc.carrera)
ORDER BY dc.facultad NULLS LAST, dc.carrera NULLS LAST;

-- ----------------------------------------------------------------------------
-- CONSULTA 3 (REPORTE 2): Indicadores de Sueno por Dia de la Semana
-- ----------------------------------------------------------------------------
SELECT
    CASE WHEN dt.es_fin_semana THEN 'Fin de semana' ELSE 'Entre semana' END AS grupo_dia,
    dt.dia_semana_num,
    dt.dia_semana,
    COUNT(*) AS noches_registradas,
    ROUND(AVG(fsn.sol_min)::numeric, 1) AS sol_min,
    ROUND(AVG(fsn.waso_min)::numeric, 1) AS waso_min,
    ROUND(AVG(fsn.tst_min)::numeric, 1) AS tst_min,
    ROUND((AVG(fsn.tst_min) / NULLIF(AVG(fsn.sol_min + fsn.waso_min + fsn.tst_min), 0) * 100.0)::numeric, 1) AS se_pct,
    ROUND((AVG(fsn.min_n3) / NULLIF(AVG(fsn.tst_min), 0) * 100.0)::numeric, 1) AS pct_n3,
    ROUND(AVG(fsn.despertares)::numeric, 1) AS despertares
FROM fact_sueno_noche fsn
JOIN dim_tiempo dt ON dt.tiempo_key = fsn.tiempo_key
GROUP BY ROLLUP (dt.es_fin_semana, (dt.dia_semana_num, dt.dia_semana))
ORDER BY dt.es_fin_semana NULLS LAST, dt.dia_semana_num NULLS LAST;

-- ----------------------------------------------------------------------------
-- CONSULTA 4 (REPORTE 3 / RR-06): Habitos vs Indicadores de Sueno
-- ----------------------------------------------------------------------------
WITH ultimo_psqi AS (
    SELECT DISTINCT ON (fc.participante_key)
        fc.participante_key,
        fc.psqi_global
    FROM fact_cuestionario fc
    JOIN dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
    ORDER BY fc.participante_key, dt.fecha DESC
),
resumen_part AS (
    SELECT
        fsn.participante_key,
        MAX(dh.uso_pantallas) AS uso_pantallas,
        MAX(dh.cafeina) AS cafeina,
        MAX(dh.ejercicio) AS ejercicio,
        MAX(dh.estres) AS estres,
        AVG(fsn.sol_min) AS sol_min,
        AVG(fsn.waso_min) AS waso_min,
        AVG(fsn.tst_min) AS tst_min,
        AVG(fsn.min_n3) AS min_n3
    FROM fact_sueno_noche fsn
    JOIN dim_habito dh ON dh.habito_key = fsn.habito_key
    GROUP BY fsn.participante_key
)
SELECT
    'Uso de pantallas antes de dormir' AS dimension_habito,
    rp.uso_pantallas AS nivel,
    COUNT(*) AS participantes,
    ROUND(AVG(rp.sol_min)::numeric, 1) AS sol_min,
    ROUND(AVG(rp.waso_min)::numeric, 1) AS waso_min,
    ROUND(AVG(rp.tst_min)::numeric, 1) AS tst_min,
    ROUND((AVG(rp.tst_min) / NULLIF(AVG(rp.sol_min + rp.waso_min + rp.tst_min), 0) * 100.0)::numeric, 1) AS se_pct,
    ROUND((AVG(rp.min_n3) / NULLIF(AVG(rp.tst_min), 0) * 100.0)::numeric, 1) AS pct_n3,
    ROUND(AVG(up.psqi_global)::numeric, 1) AS psqi_global
FROM resumen_part rp
JOIN ultimo_psqi up ON up.participante_key = rp.participante_key
GROUP BY rp.uso_pantallas
UNION ALL
SELECT
    'Cafeina', rp.cafeina, COUNT(*),
    ROUND(AVG(rp.sol_min)::numeric, 1), ROUND(AVG(rp.waso_min)::numeric, 1), ROUND(AVG(rp.tst_min)::numeric, 1),
    ROUND((AVG(rp.tst_min) / NULLIF(AVG(rp.sol_min + rp.waso_min + rp.tst_min), 0) * 100.0)::numeric, 1),
    ROUND((AVG(rp.min_n3) / NULLIF(AVG(rp.tst_min), 0) * 100.0)::numeric, 1),
    ROUND(AVG(up.psqi_global)::numeric, 1)
FROM resumen_part rp JOIN ultimo_psqi up ON up.participante_key = rp.participante_key GROUP BY rp.cafeina
UNION ALL
SELECT
    'Ejercicio', rp.ejercicio, COUNT(*),
    ROUND(AVG(rp.sol_min)::numeric, 1), ROUND(AVG(rp.waso_min)::numeric, 1), ROUND(AVG(rp.tst_min)::numeric, 1),
    ROUND((AVG(rp.tst_min) / NULLIF(AVG(rp.sol_min + rp.waso_min + rp.tst_min), 0) * 100.0)::numeric, 1),
    ROUND((AVG(rp.min_n3) / NULLIF(AVG(rp.tst_min), 0) * 100.0)::numeric, 1),
    ROUND(AVG(up.psqi_global)::numeric, 1)
FROM resumen_part rp JOIN ultimo_psqi up ON up.participante_key = rp.participante_key GROUP BY rp.ejercicio
UNION ALL
SELECT
    'Nivel de estres', rp.estres, COUNT(*),
    ROUND(AVG(rp.sol_min)::numeric, 1), ROUND(AVG(rp.waso_min)::numeric, 1), ROUND(AVG(rp.tst_min)::numeric, 1),
    ROUND((AVG(rp.tst_min) / NULLIF(AVG(rp.sol_min + rp.waso_min + rp.tst_min), 0) * 100.0)::numeric, 1),
    ROUND((AVG(rp.min_n3) / NULLIF(AVG(rp.tst_min), 0) * 100.0)::numeric, 1),
    ROUND(AVG(up.psqi_global)::numeric, 1)
FROM resumen_part rp JOIN ultimo_psqi up ON up.participante_key = rp.participante_key GROUP BY rp.estres;
