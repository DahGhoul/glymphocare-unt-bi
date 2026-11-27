"""
Servicio de Interpretacion con IA Generativa (RF-10, RNF-07).
Usa Google Gemini API (capa gratuita) si hay API Key configurada, y cuenta con un
sintetizador clinico-pedagogico determinista de respaldo para garantizar disponibilidad 100%.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx

from app.core.config import get_settings


def _build_local_fallback_interpretation(scope: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    kpis = payload["kpis"]
    alerts: List[Dict[str, Any]] = payload.get("alerts", [])

    psqi = kpis.get("PSQI")
    ess = kpis.get("ESS")
    se = kpis.get("SE")
    sol = kpis.get("SOL")
    waso = kpis.get("WASO")
    tst = kpis.get("TST")
    pct_n3 = kpis.get("PCT_N3")

    if scope == "participant":
        subj = f"El participante {payload.get('codigo', '')} registra un PSQI de {psqi} pts ({'mala calidad > 5' if (psqi or 0) > 5 else 'calidad aceptable <= 5'}) y una somnolencia ESS de {ess} pts."
    else:
        subj = f"La cohorte analizada (n = {payload.get('n', 0)}) presenta un PSQI promedio de {psqi} pts y un ESS promedio de {ess} pts."

    gaps = []
    if sol is not None and sol > 20:
        gaps.append(f"latencia de inicio elevada ({sol:.1f} min, umbral <= 20 min)")
    if waso is not None and waso > 40:
        gaps.append(f"fragmentacion nocturna WASO ({waso:.1f} min, umbral <= 40 min)")
    if tst is not None and tst < 420:
        gaps.append(f"duracion total insuficiente ({tst/60:.1f} h, meta >= 7.0 h)")
    if se is not None and se < 85:
        gaps.append(f"eficiencia del sueno por debajo de la meta ({se:.1f}%, meta >= 85%)")

    falla_txt = (
        "Los principales puntos de deterioro detectados en los indicadores objetivos son: " + "; ".join(gaps) + "."
        if gaps
        else "Los indicadores objetivos principales de continuidad y cantidad se encuentran dentro de los rangos de referencia."
    )

    n3_txt = (
        f"El porcentaje de sueno profundo N3 se situa en {pct_n3:.1f}%. "
        "Dado que la fase N3 concentra la maxima actividad del sistema glinfatico para depurar metabolitos cerebrales (Xie et al., 2013), "
        + (
            "un valor inferior al 15% sugiere ventana reducida de limpieza nocturna, frecuentemente asociada a estres academico, cafeina vespertina o falta de ejercicio aerobico."
            if (pct_n3 or 0) < 15
            else "mantener este porcentaje junto con al menos 7 horas de TST protege la oportunidad de restauracion neurocognitiva."
        )
        if pct_n3 is not None
        else "Sin registros objetivos de fase N3 suficientes para estimar la ventana glinfatica."
    )

    plan = [a["texto_recomendacion"] for a in alerts[:4]]
    if not plan:
        plan = [
            "Mantener horarios estables de acostarse y levantarse (+/- 30 min) durante la semana academica.",
            "Conservar la desconexion de pantallas 60 minutos antes de dormir para sostener una latencia <= 20 min.",
        ]

    return {
        "provider_used": "Sintesis Local Basada en Reglas (sin Gemini Key)",
        "resumen_ejecutivo": subj,
        "componentes_criticos": falla_txt,
        "analisis_glinfatico_n3": n3_txt,
        "plan_accion": plan,
        "aviso_no_clinico": "Interpretacion orientativa generada para fines academicos y de higiene del sueno. No sustituye evaluacion medica ni diagnostico clinico.",
    }


async def generate_ai_interpretation(
    scope: str,
    payload: Dict[str, Any],
    runtime_api_key: str = "",
) -> Dict[str, Any]:
    settings = get_settings()
    api_key = (runtime_api_key or settings.gemini_api_key or "").strip()
    if not api_key:
        return _build_local_fallback_interpretation(scope, payload)

    prompt = (
        "Eres un asistente cientifico de higiene del sueno universitario (proyecto GlymphoCare, UNT). "
        "NO diagnostiques enfermedades ni inventes cifras. Redacta exclusivamente una interpretacion clara, sobria y basada en los siguientes datos reales anonimizados.\n\n"
        f"Alcance: {scope}\n"
        f"Datos JSON: {json.dumps(payload, ensure_ascii=False)}\n\n"
        "Responde UNICAMENTE con un objeto JSON valido con exactamente estas 4 claves:\n"
        "1. 'resumen_ejecutivo' (2-3 oraciones contrastando percepcion subjetiva PSQI/ESS vs sueno real)\n"
        "2. 'componentes_criticos' (que componente falla: latencia SOL, fragmentacion WASO, duracion TST o eficiencia SE)\n"
        "3. 'analisis_glinfatico_n3' (lectura del %N3 en relacion con la limpieza glinfatica de Xie et al., 2013)\n"
        "4. 'plan_accion' (lista de 3 acciones concretas de higiene del sueno basadas en las alertas activas)"
    )

    candidate_models = []
    for m in (settings.gemini_model, "gemini-3-flash-preview", "gemini-2.5-flash-lite", "gemini-flash-latest"):
        if m and m not in candidate_models:
            candidate_models.append(m)

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
    }

    last_exc: Exception | None = None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for model_name in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                try:
                    resp = await client.post(url, json=body)
                    if resp.status_code in (404, 429, 503):
                        last_exc = httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text)
                    return {
                        "provider_used": f"Google Gemini ({model_name})",
                        "resumen_ejecutivo": parsed.get("resumen_ejecutivo", ""),
                        "componentes_criticos": parsed.get("componentes_criticos", ""),
                        "analisis_glinfatico_n3": parsed.get("analisis_glinfatico_n3", ""),
                        "plan_accion": parsed.get("plan_accion", []),
                        "aviso_no_clinico": "Interpretacion orientativa generada con IA generativa sobre indicadores reales. No constituye diagnostico clinico ni entrena modelos predictivos.",
                    }
                except Exception as inner_exc:
                    last_exc = inner_exc
                    continue
        raise last_exc or RuntimeError("No se obtuvo respuesta de Gemini")
    except Exception as exc:
        fb = _build_local_fallback_interpretation(scope, payload)
        fb["provider_used"] = f"Respaldo Local (Gemini no disponible: {type(exc).__name__})"
        return fb
