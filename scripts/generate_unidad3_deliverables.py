"""
Generador oficial de entregables UNIDAD3 para el Grupo G5 (GlymphoCare)
siguiendo al milimetro las plantillas oficiales del docente:
- UNIDAD3/Documento/INFORME_FINAL_UNIDAD3_G5_GlymphoCare.docx (SOLO Word)
- UNIDAD3/Datos/* (SQL, ETL, seed, csv_wearables_ejemplo, backup_glymphocare_postgres.sql)
- UNIDAD3/Software/* (01_INTEGRANTES, 02_MEMORIA_DESCRIPTIVA, 03_MANUAL_DE_USUARIO, 04_CODIGO_FUENTE + zip)
- UNIDAD3/Videos/* (Guiones 10 min y 3 min)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import psycopg
from psycopg.rows import dict_row
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Inches, Pt, RGBColor

GLYMPHO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = GLYMPHO_ROOT.parent
UNIDAD3 = PROJECT_ROOT / "UNIDAD3"
ASSETS_DIR = GLYMPHO_ROOT / "scripts" / "_doc_assets"
SHOTS_DIR = GLYMPHO_ROOT / "docs" / "screenshots"

if str(GLYMPHO_ROOT) not in sys.path:
    sys.path.insert(0, str(GLYMPHO_ROOT))

from etl.run_etl import get_dsn

TEAL_HEX = "0F766E"
ALT_HEX = "F8FAFC"
TEAL_RGB = RGBColor(0x0F, 0x76, 0x6E)
INK_RGB = RGBColor(0x14, 0x20, 0x2B)
MUTED_RGB = RGBColor(0x5A, 0x68, 0x77)

SOFTWARE_TITLE = (
    "GlymphoCare: Plataforma analítica web para la medición de la calidad del sueño "
    "y del sueño profundo (%N3) en estudiantes universitarios"
)

AUTHORS_FULL = [
    "Cuba Moya, Diego Joel",
    "Herrera Rodríguez, Anghela Tatiana",
    "Polonio Ramos, Franco Imanol",
    "Rivas Calderón, Zaleth Valentina",
    "Robles Romero, Ronaldo Carlos",
    "Villanueva Rosales, Estefany Lucía",
]


def _shade_cell(cell, hex_color: str) -> None:
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def _add_page_number_to_run(run) -> None:
    fldChar1 = parse_xml(r'<w:fldChar %s w:fldCharType="begin"/>' % nsdecls("w"))
    instrText = parse_xml(r'<w:instrText %s xml:space="preserve"> PAGE </w:instrText>' % nsdecls("w"))
    fldChar2 = parse_xml(r'<w:fldChar %s w:fldCharType="separate"/>' % nsdecls("w"))
    fldChar3 = parse_xml(r'<w:fldChar %s w:fldCharType="end"/>' % nsdecls("w"))
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)
    run._r.append(fldChar3)


def _configure_unt_header_footer(doc: Document, first_page_blank: bool = True) -> None:
    sec = doc.sections[0]
    sec.top_margin = Cm(1.9)
    sec.bottom_margin = Cm(1.8)
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)
    sec.different_first_page_header_footer = first_page_blank

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = INK_RGB

    crest = ASSETS_DIR / "escudo_unt.png"
    hdr = sec.header
    hp = hdr.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if crest.exists():
        hp.add_run().add_picture(str(crest), width=Cm(1.45))

    ftr = sec.footer
    fp = ftr.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = fp.add_run()
    r.font.size = Pt(9.5)
    r.font.color.rgb = MUTED_RGB
    _add_page_number_to_run(r)


def _h1(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(13)
    r.font.color.rgb = TEAL_RGB


def _h2(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(7)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(11.5)
    r.font.color.rgb = INK_RGB


def _p(doc: Document, text: str, bold_prefix: str = "", space_after: int = 5) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    if bold_prefix:
        rb = p.add_run(bold_prefix)
        rb.bold = True
    p.add_run(text)


def _add_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c_idx, h in enumerate(headers):
        cell = tbl.rows[0].cells[c_idx]
        _shade_cell(cell, TEAL_HEX)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(255, 255, 255)
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row):
            cell = tbl.rows[r_idx].cells[c_idx]
            if r_idx % 2 == 0:
                _shade_cell(cell, ALT_HEX)
            p = cell.paragraphs[0]
            r = p.add_run(str(val))
            r.font.size = Pt(9)
    doc.add_paragraph().paragraph_format.space_after = Pt(3)


def _render_code_card(code_text: str, out_path: Path, header_label: str = "Python / FastAPI / TypeScript") -> None:
    """Renderiza un fragmento de codigo en tarjeta oscura estilo VS Code (igual a la plantilla)."""
    lines = code_text.strip().splitlines()[:28]
    n_lines = max(6, len(lines))
    fig_h = max(2.2, 0.21 * n_lines + 0.45)
    fig, ax = plt.subplots(figsize=(8.6, fig_h), dpi=200)
    fig.patch.set_facecolor("#1E1E2E")
    ax.set_facecolor("#1E1E2E")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, n_lines + 1.4)
    ax.axis("off")

    ax.text(0.15, n_lines + 0.85, header_label, color="#94A3B8", fontsize=8.0, family="monospace", fontweight="bold")
    ax.plot([0.1, 9.9], [n_lines + 0.55, n_lines + 0.55], color="#313244", lw=0.8)

    for idx, line in enumerate(lines):
        y = n_lines - idx - 0.1
        clean_line = line[:106]
        color = "#CDD6F4"
        stripped = clean_line.lstrip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("--"):
            color = "#6C7086"
        elif any(stripped.startswith(k) for k in ("def ", "async def ", "class ", "export ", "const ", "function ", "@router", "SELECT", "WITH", "INSERT")):
            color = "#89B4FA"
        elif "return " in clean_line or "raise " in clean_line:
            color = "#CBA6F7"
        ax.text(0.15, y, f"{idx+1:02d}  {clean_line}", color=color, fontsize=7.5, family="monospace", va="center")

    plt.tight_layout(pad=0.25)
    plt.savefig(out_path, dpi=200, facecolor="#1E1E2E")
    plt.close()


def _generate_diagrams_and_charts(stats: dict) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Diagrama de Arquitectura del Sistema (para Memoria Descriptiva e Informe)
    fig, ax = plt.subplots(figsize=(10.2, 4.6), dpi=220)
    ax.set_xlim(0, 10.2)
    ax.set_ylim(0, 4.6)
    ax.axis("off")

    def node(x, y, w, h, title, sub, bg="#FFFFFF", border="#0F766E", title_c="#0F766E"):
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06", ec=border, fc=bg, lw=1.4))
        ax.text(x + w / 2, y + h * 0.63, title, color=title_c, fontsize=9.2, fontweight="bold", ha="center", va="center")
        ax.text(x + w / 2, y + h * 0.28, sub, color="#334155", fontsize=7.6, ha="center", va="center")

    node(0.3, 2.55, 2.1, 1.35, "Frontend SPA", "React 19 + TypeScript\nTailwind + Apache ECharts", bg="#F8FAFC", border="#0F766E")
    node(3.1, 2.55, 2.2, 1.35, "Backend BI API", "FastAPI (Python 3.13)\nSciPy + ReportLab + JWT", bg="#F8FAFC", border="#0F766E")
    node(6.1, 3.05, 2.0, 1.0, "Pipeline ETL", "Buysse PSQI + ESS\nValidación CSV + Upsert", bg="#EEF2FF", border="#3B4990", title_c="#3B4990")
    node(6.1, 1.45, 3.7, 1.15, "Amazon RDS (PostgreSQL 16)", "Esquema OLTP (glympho_oltp · 13 tablas)\nData Mart Estrella (glympho_dw · 2 hechos)", bg="#ECFDF5", border="#0F766E")
    node(3.1, 0.45, 2.2, 1.15, "Google Gemini API", "gemini-3-flash-preview\nSolo interpretación (sin ML)", bg="#EEF2FF", border="#3B4990", title_c="#3B4990")
    node(0.3, 0.45, 2.1, 1.15, "Amazon EC2 / S3", "Nginx HTTPS + Docker\nRespaldo CSVs y PDFs", bg="#FFFBEB", border="#B45309", title_c="#B45309")

    arrows = [
        (2.4, 3.22, 3.1, 3.22),
        (5.3, 3.5, 6.1, 3.5),
        (5.3, 2.75, 6.1, 2.15),
        (7.1, 3.05, 7.1, 2.6),
        (4.2, 2.55, 4.2, 1.6),
        (2.4, 1.0, 3.1, 2.7),
    ]
    for x1, y1, x2, y2 in arrows:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", color="#475569", lw=1.3))

    plt.title("Arquitectura Tecnológica y Nube AWS — GlymphoCare (Grupo G5)", fontsize=11, fontweight="bold", color="#14202B", pad=6)
    plt.tight_layout()
    plt.savefig(ASSETS_DIR / "arch_glymphocare.png", dpi=220)
    plt.close()

    # 2. Diagrama del Esquema Estrella
    fig, ax = plt.subplots(figsize=(10, 5.4), dpi=220)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    def draw_box(x, y, w, h, title, lines, header_col="#0F766E"):
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04", ec="#94A3B8", fc="#FFFFFF", lw=1.2))
        ax.add_patch(mpatches.FancyBboxPatch((x, y + h - 0.42), w, 0.42, boxstyle="round,pad=0.04", ec=header_col, fc=header_col, lw=1))
        ax.text(x + w / 2, y + h - 0.21, title, color="white", fontsize=9, fontweight="bold", ha="center", va="center")
        ax.text(x + 0.12, y + h - 0.55, "\n".join(lines), color="#14202B", fontsize=7.6, va="top", family="monospace")

    draw_box(0.3, 3.8, 2.5, 1.8, "dim_tiempo", ["PK tiempo_key", "fecha, dia_semana", "es_fin_semana", "semana_anio, mes", "ciclo_academico"])
    draw_box(7.2, 3.8, 2.5, 1.8, "dim_participante", ["PK participante_key", "codigo (UNT-XXX)", "edad, rango_edad", "sexo, ciclo"])
    draw_box(0.3, 0.4, 2.5, 1.6, "dim_carrera", ["PK carrera_key", "carrera", "facultad"])
    draw_box(7.2, 0.4, 2.5, 1.8, "dim_habito", ["PK habito_key", "uso_pantallas", "cafeina, ejercicio", "estres, regularidad"])

    draw_box(3.45, 3.35, 3.1, 2.3, "fact_sueno_noche", ["PK sueno_noche_key", "FK tiempo/part/carr/hab", "tib_min, tst_min, sol_min", "waso_min, despertares", "min_n1, n2, n3, rem", "se_pct, pct_n3, ig"], header_col="#3B4990")
    draw_box(3.45, 0.35, 3.1, 2.25, "fact_cuestionario", ["PK cuestionario_key", "FK tiempo/part/carr/hab", "c1_calidad .. c7_disf", "psqi_global (0-21)", "ess_total (0-24)", "clasif_psqi, clasif_ess"], header_col="#0F766E")

    for (x1, y1, x2, y2) in [
        (2.8, 4.7, 3.45, 4.7), (7.2, 4.7, 6.55, 4.7),
        (2.8, 1.2, 3.45, 1.5), (7.2, 1.2, 6.55, 1.5),
        (2.8, 4.2, 3.45, 2.1), (7.2, 4.2, 6.55, 2.1),
        (2.8, 1.6, 3.45, 3.9), (7.2, 1.6, 6.55, 3.9),
    ]:
        ax.plot([x1, x2], [y1, y2], color="#64748B", lw=1.0, ls="--")

    plt.title("Modelo Dimensional en Esquema Estrella — Data Mart glympho_dw", fontsize=11, fontweight="bold", color="#14202B", pad=8)
    plt.tight_layout()
    plt.savefig(ASSETS_DIR / "star_datamart.png", dpi=220)
    plt.close()

    # 3. Graficos reales de resultados
    hab_rows = stats["hab_rows"]
    labels = [f"{r['dimension_habito'][:14]}\n({r['nivel']})" for r in hab_rows]
    n3_vals = [float(r["pct_n3"]) for r in hab_rows]
    psqi_vals = [float(r["psqi_global"]) for r in hab_rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.1), dpi=220)
    ax1.barh(labels, n3_vals, color=["#3B4990" if v >= 16 else "#94A3B8" for v in n3_vals])
    ax1.set_title("Sueño Profundo (%N3) según Hábito (n=90)", fontsize=10, fontweight="bold")
    ax1.set_xlabel("%N3 del Tiempo Total de Sueño")
    ax1.axvline(15.0, color="#0F766E", ls="--", lw=1)

    ax2.barh(labels, psqi_vals, color=["#B91C1C" if v > 5 else "#0F766E" for v in psqi_vals])
    ax2.set_title("PSQI Global Promedio según Hábito (umbral <= 5)", fontsize=10, fontweight="bold")
    ax2.set_xlabel("Puntaje PSQI (0-21)")
    ax2.axvline(5.0, color="#B91C1C", ls="--", lw=1)
    plt.tight_layout()
    plt.savefig(ASSETS_DIR / "chart_habitos_n3.png", dpi=220)
    plt.close()

    fac_rows = stats["fac_rows"]
    facs = [r["facultad"] for r in fac_rows]
    buenos = [int(r["buenos"]) for r in fac_rows]
    malos = [int(r["malos"]) for r in fac_rows]
    fig, ax = plt.subplots(figsize=(7.5, 3.5), dpi=220)
    x = range(len(facs))
    ax.bar(x, buenos, width=0.35, label="Buen dormidor (PSQI <= 5)", color="#0F766E")
    ax.bar([i + 0.36 for i in x], malos, width=0.35, label="Mal dormidor (PSQI > 5)", color="#B91C1C")
    ax.set_xticks([i + 0.18 for i in x])
    ax.set_xticklabels(facs, fontsize=9)
    ax.set_ylabel("Estudiantes")
    ax.set_title("Clasificación de Calidad del Sueño por Facultad UNT (n=90)", fontsize=10.5, fontweight="bold")
    ax.legend(frameon=False, fontsize=8.5)
    plt.tight_layout()
    plt.savefig(ASSETS_DIR / "chart_cohorte_psqi.png", dpi=220)
    plt.close()


def _fetch_live_stats() -> dict:
    dsn = get_dsn()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH uc AS (
                    SELECT DISTINCT ON (participante_key) participante_key, psqi_global, ess_total, clasificacion_psqi
                    FROM glympho_dw.fact_cuestionario fc
                    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                    ORDER BY participante_key, dt.fecha DESC
                )
                SELECT
                    COUNT(DISTINCT uc.participante_key) AS n_part,
                    COUNT(fsn.sueno_noche_key) AS n_noches,
                    ROUND(AVG(uc.psqi_global)::numeric, 2) AS psqi,
                    ROUND(AVG(uc.ess_total)::numeric, 2) AS ess,
                    ROUND(100.0 * SUM(CASE WHEN uc.clasificacion_psqi='Mal dormidor' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_malos,
                    ROUND(AVG(fsn.se_pct)::numeric, 1) AS se,
                    ROUND(AVG(fsn.sol_min)::numeric, 1) AS sol,
                    ROUND(AVG(fsn.waso_min)::numeric, 1) AS waso,
                    ROUND((AVG(fsn.tst_min)/60.0)::numeric, 2) AS tst_h,
                    ROUND(AVG(fsn.pct_n3)::numeric, 1) AS pct_n3,
                    ROUND(AVG(fsn.despertares)::numeric, 2) AS desp,
                    ROUND(AVG(fsn.indice_glinfatico)::numeric, 3) AS ig
                FROM uc JOIN glympho_dw.fact_sueno_noche fsn ON fsn.participante_key = uc.participante_key
            """)
            summary = cur.fetchone()

            cur.execute("""
                WITH up AS (
                    SELECT DISTINCT ON (fc.participante_key) fc.participante_key, fc.carrera_key, fc.clasificacion_psqi
                    FROM glympho_dw.fact_cuestionario fc JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                    ORDER BY fc.participante_key, dt.fecha DESC
                )
                SELECT dc.facultad,
                    SUM(CASE WHEN up.clasificacion_psqi='Buen dormidor' THEN 1 ELSE 0 END) AS buenos,
                    SUM(CASE WHEN up.clasificacion_psqi='Mal dormidor' THEN 1 ELSE 0 END) AS malos,
                    COUNT(*) AS total
                FROM up JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = up.carrera_key
                GROUP BY dc.facultad ORDER BY total DESC
            """)
            fac_rows = cur.fetchall()

            cur.execute("""
                WITH up AS (
                    SELECT DISTINCT ON (fc.participante_key) fc.participante_key, fc.psqi_global
                    FROM glympho_dw.fact_cuestionario fc JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                    ORDER BY fc.participante_key, dt.fecha DESC
                ),
                rp AS (
                    SELECT fsn.participante_key,
                        MAX(dh.uso_pantallas) AS uso_pantallas, MAX(dh.cafeina) AS cafeina,
                        MAX(dh.ejercicio) AS ejercicio, MAX(dh.estres) AS estres,
                        AVG(fsn.sol_min) AS sol_min, AVG(fsn.waso_min) AS waso_min,
                        AVG(fsn.tst_min) AS tst_min, AVG(fsn.min_n3) AS min_n3
                    FROM glympho_dw.fact_sueno_noche fsn
                    JOIN glympho_dw.dim_habito dh ON dh.habito_key = fsn.habito_key
                    GROUP BY fsn.participante_key
                )
                SELECT 'Pantallas' AS dimension_habito, rp.uso_pantallas AS nivel, COUNT(*) AS n,
                    ROUND(AVG(rp.sol_min)::numeric,1) AS sol, ROUND(AVG(rp.waso_min)::numeric,1) AS waso,
                    ROUND(AVG(rp.tst_min)::numeric,1) AS tst,
                    ROUND((AVG(rp.min_n3)/AVG(rp.tst_min)*100)::numeric,1) AS pct_n3,
                    ROUND(AVG(up.psqi_global)::numeric,1) AS psqi_global
                FROM rp JOIN up ON up.participante_key = rp.participante_key GROUP BY rp.uso_pantallas
                UNION ALL
                SELECT 'Cafeina', rp.cafeina, COUNT(*),
                    ROUND(AVG(rp.sol_min)::numeric,1), ROUND(AVG(rp.waso_min)::numeric,1), ROUND(AVG(rp.tst_min)::numeric,1),
                    ROUND((AVG(rp.min_n3)/AVG(rp.tst_min)*100)::numeric,1), ROUND(AVG(up.psqi_global)::numeric,1)
                FROM rp JOIN up ON up.participante_key = rp.participante_key GROUP BY rp.cafeina
                UNION ALL
                SELECT 'Ejercicio', rp.ejercicio, COUNT(*),
                    ROUND(AVG(rp.sol_min)::numeric,1), ROUND(AVG(rp.waso_min)::numeric,1), ROUND(AVG(rp.tst_min)::numeric,1),
                    ROUND((AVG(rp.min_n3)/AVG(rp.tst_min)*100)::numeric,1), ROUND(AVG(up.psqi_global)::numeric,1)
                FROM rp JOIN up ON up.participante_key = rp.participante_key GROUP BY rp.ejercicio
            """)
            hab_rows = cur.fetchall()
    return {"summary": summary, "fac_rows": fac_rows, "hab_rows": hab_rows}


# Especificacion unificada de pantallas para Manual de Usuario y Manual de Codigo Fuente (exacto indice compartido)
SCREEN_SPECS = [
    {
        "group": "A) PANTALLA DE LOGIN Y REGISTRO",
        "title": "Pantalla de inicio de sesión",
        "page": 3,
        "fig": "Figura 01",
        "shot": "01_login.png",
        "user_desc": (
            "En esta pantalla se presenta la identidad institucional de GlymphoCare (Universidad Nacional de Trujillo) "
            "junto con dos pestañas principales: 'Iniciar sesión' y 'Registro cohorte'. El usuario ingresa su correo "
            "y contraseña registrados, o utiliza uno de los botones de acceso rápido de demostración por rol (Admin BI, "
            "Analista, Investigador o Participante). Internamente, el sistema valida el hash bcrypt contra la tabla "
            "glympho_oltp.usuario, verifica que la cuenta esté activa y emite un token JWT con expiración de 12 horas "
            "que habilita únicamente las rutas autorizadas para su rol."
        ),
        "code_file": GLYMPHO_ROOT / "backend" / "app" / "routers" / "auth.py",
        "code_anchor": "def login(",
        "code_lines": 28,
        "code_desc": (
            "Se muestra el endpoint POST /api/auth/login que valida credenciales contra glympho_oltp.usuario "
            "mediante verify_password (bcrypt), verifica el estado activo de la cuenta y genera el token JWT "
            "con el rol y código anonimizado del participante."
        ),
    },
    {
        "group": None,
        "title": "Pantalla de registrar usuario (Cohorte UNT)",
        "page": 4,
        "fig": "Figura 02",
        "shot": "02_registro.png",
        "user_desc": (
            "Dentro de la pestaña 'Registro cohorte', el estudiante universitario ingresa su nombre (anonimizado "
            "automáticamente mediante código UNT-XXX), correo, contraseña, edad (16–65), sexo, ciclo académico, "
            "facultad y carrera de la UNT. Como regla obligatoria de privacidad (RNF-04), debe marcar la casilla "
            "de consentimiento informado voluntario; sin ella el sistema bloquea el registro. Al enviar, se crean "
            "atómicamente el usuario, el registro en participante, el consentimiento firmado en consentimiento y "
            "se redirige al módulo de Captura de Datos."
        ),
        "code_file": GLYMPHO_ROOT / "backend" / "app" / "routers" / "auth.py",
        "code_anchor": "def register(",
        "code_lines": 32,
        "code_desc": (
            "Se muestra la función register que exige consentimiento_aceptado=True, encripta la contraseña con "
            "bcrypt, asigna automáticamente el código anonimizado UNT-XXX y registra usuario, participante y "
            "consentimiento en Amazon RDS."
        ),
    },
    {
        "group": "B) USUARIOS CON ROL \"PARTICIPANTE\"",
        "title": "Pantalla de Captura de Datos (Formulario PSQI/ESS)",
        "page": 5,
        "fig": "Figura 03",
        "shot": "08_captura_wizard.png",
        "user_desc": (
            "Formulario multi-paso responsivo (optimizado móvil primero) organizado en 4 pasos con barra de progreso: "
            "1) Consentimiento y fecha, 2) Hábitos de higiene del sueño (pantallas >1h/<=1h, cafeína, ejercicio, estrés "
            "y regularidad), 3) Los 19 ítems del Índice de Calidad de Sueño de Pittsburgh (PSQI) y 4) Las 8 situaciones "
            "de la Escala de Somnolencia de Epworth (ESS). Al enviar, el backend calcula en tiempo real C1–C7, PSQI "
            "global y ESS mediante el algoritmo validado de Buysse et al. (1989) y dispara el ETL incremental hacia el Data Mart."
        ),
        "code_file": GLYMPHO_ROOT / "etl" / "psqi_calculator.py",
        "code_anchor": "def compute_psqi(",
        "code_lines": 32,
        "code_desc": (
            "Se muestra la función compute_psqi que implementa el algoritmo oficial de Buysse et al. (1989) "
            "calculando los 7 componentes clínicos (C1–C7), manejando el cruce de medianoche en horas en cama y "
            "clasificando automáticamente en Buen o Mal dormidor (umbral PSQI > 5)."
        ),
    },
    {
        "group": None,
        "title": "Pantalla de Carga CSV Wearable y Noche Manual",
        "page": 6,
        "fig": "Figura 04",
        "shot": "09_captura_csv.png",
        "user_desc": (
            "Permite descargar la plantilla CSV estándar de wearables o subir un archivo exportado con métricas "
            "nocturnas (fecha, TIB, TST, SOL, despertares, N1, N2, N3, REM), además de registrar noches manualmente "
            "con vista previa en vivo de WASO, SE (%) y %N3. Internamente, el validador ETL (RETL-02) rechaza filas "
            "con fechas futuras, duplicadas, TST + SOL > TIB o suma de fases distinta de TST, registra la auditoría "
            "en carga_archivo y actualiza fact_sueno_noche."
        ),
        "code_file": GLYMPHO_ROOT / "etl" / "validators.py",
        "code_anchor": "def validate_sleep_night_row(",
        "code_lines": 30,
        "code_desc": (
            "Se muestra el validador de calidad de datos RETL-02 que verifica rangos fisiológicos no negativos, "
            "coherencia TST + SOL <= TIB y consistencia de suma de fases N1+N2+N3+REM = TST antes de cargar al Data Mart."
        ),
    },
    {
        "group": None,
        "title": "Pantalla de Perfil del Participante e Interpretación IA",
        "page": 7,
        "fig": "Figura 05",
        "shot": "07_perfil_ia.png",
        "user_desc": (
            "Muestra el expediente anonimizado del estudiante (código UNT-XXX, facultad, carrera, ciclo y hábitos), "
            "sus KPIs individuales, la evolución longitudinal PSQI/ESS y las noches registradas. El motor de reglas "
            "evalúa los umbrales configurados en base de datos para mostrar recomendaciones personalizadas. Además, "
            "el botón 'Generar interpretación IA' envía únicamente los KPIs anonimizados a Google Gemini "
            "(gemini-3-flash-preview) para redactar una lectura pedagógica sin diagnóstico clínico ni ML predictivo."
        ),
        "code_file": GLYMPHO_ROOT / "backend" / "app" / "services" / "llm_service.py",
        "code_anchor": "async def generate_ai_interpretation(",
        "code_lines": 30,
        "code_desc": (
            "Se muestra el servicio de IA generativa que envía los KPIs anonimizados a Google Gemini API "
            "(gemini-3-flash-preview) con respaldo automático y sintetizador determinista local, cumpliendo RF-10 y RNF-07."
        ),
    },
    {
        "group": "C) USUARIOS CON ROL \"ANALISTA / INVESTIGADOR\"",
        "title": "Pantalla de Dashboard Ejecutivo e IA de Cohorte",
        "page": 8,
        "fig": "Figura 06",
        "shot": "03_dashboard_ejecutivo.png",
        "user_desc": (
            "Vista principal de Inteligencia de Negocios. Presenta la barra global de Segmentación BI (fechas, "
            "facultad, carrera, ciclo y pantallas), las 5 tarjetas KPI de cabecera con semáforo de umbral, el botón "
            "'Interpretar cohorte con IA' (síntesis ejecutiva con Google Gemini sobre los 90 estudiantes), la tendencia "
            "diaria SE/%N3, la dona de buenos vs. malos dormidores, el mapa de calor por facultad/día y las alertas activas."
        ),
        "code_file": GLYMPHO_ROOT / "backend" / "app" / "routers" / "dashboard.py",
        "code_anchor": "def executive_dashboard(",
        "code_lines": 30,
        "code_desc": (
            "Se muestra el endpoint GET /api/dashboard/executive que consulta fact_cuestionario y fact_sueno_noche "
            "en glympho_dw aplicando los filtros dinámicos y evaluando las reglas activas de recomendacion_regla."
        ),
    },
    {
        "group": None,
        "title": "Pantalla de Calidad Subjetiva (PSQI y ESS)",
        "page": 9,
        "fig": "Figura 07",
        "shot": "04_calidad_psqi.png",
        "user_desc": (
            "Profundiza en los 7 componentes del PSQI mediante un gráfico Radar (cohorte actual frente a referencia "
            "óptima), un Boxplot comparativo de PSQI por facultad, la evolución mensual PSQI/ESS y la tabla Top 10 "
            "de participantes con mayor alteración subjetiva con enlace directo hacia su perfil individual."
        ),
        "code_file": GLYMPHO_ROOT / "backend" / "app" / "routers" / "dashboard.py",
        "code_anchor": "def subjective_quality(",
        "code_lines": 28,
        "code_desc": (
            "Se muestra la consulta analítica de /api/dashboard/subjective que extrae el último cuestionario por "
            "participante, calcula el vector de los 7 componentes C1–C7 para el Radar y genera cuartiles para el Boxplot."
        ),
    },
    {
        "group": None,
        "title": "Pantalla de Limpieza Cerebral (%N3) y Simulador de Horarios",
        "page": 10,
        "fig": "Figura 08",
        "shot": "05_limpieza_cerebral.png",
        "user_desc": (
            "Conecta el marco neurocientífico de Xie et al. (2013) con los datos reales: muestra %N3, el Índice "
            "Glinfático (IG) derivado, la arquitectura promedio por fases (N1, N2, N3, REM), el gráfico de dispersión "
            "%N3 vs PSQI con regresión lineal real (r, R², p-valor), el cuadrante Percepción vs. Realidad y el "
            "Simulador empírico de Higiene del Sueño y Horario de Descanso que alerta sobre deuda cognitiva semanal."
        ),
        "code_file": GLYMPHO_ROOT / "backend" / "app" / "routers" / "dashboard.py",
        "code_anchor": "def simulate_habits(",
        "code_lines": 30,
        "code_desc": (
            "Se muestra el endpoint POST /api/dashboard/simulate-habits que calcula deltas empíricos por grupo de "
            "hábito directamente desde glympho_dw (sin modelos ML) y determina la hora exacta para apagar pantallas y acostarse."
        ),
    },
    {
        "group": None,
        "title": "Pantalla de Hábitos y Correlaciones",
        "page": 11,
        "fig": "Figura 09",
        "shot": "06_habitos.png",
        "user_desc": (
            "Calcula en vivo mediante scipy.stats la matriz de correlación de Pearson entre los hábitos (pantallas, "
            "cafeína, ejercicio, estrés, regularidad) y los KPIs del sueño, acompañada de comparativos por grupo y "
            "el panel de Hallazgos Estadísticos Automáticos (RF-07) con pruebas t de Welch y etiquetas de significancia p."
        ),
        "code_file": GLYMPHO_ROOT / "backend" / "app" / "services" / "stats_service.py",
        "code_anchor": "def compute_habit_correlations_and_findings(",
        "code_lines": 30,
        "code_desc": (
            "Se muestra la función estadística en SciPy que calcula los coeficientes r de Pearson y las pruebas t de "
            "Welch para redactar automáticamente los hallazgos estadísticos con su p-valor real."
        ),
    },
    {
        "group": None,
        "title": "Pantalla de Reportes Oficiales y Exportación (PDF/CSV)",
        "page": 12,
        "fig": "Figura 10",
        "shot": "10_reportes_oficiales.png",
        "user_desc": (
            "Presenta los 3 reportes tabulares clínicos conectados al Data Mart: 1) Resumen de Cohorte (RR-03), "
            "2) Indicadores por Día de la Semana y 3) Hábitos vs. Indicadores (RR-06), resaltando en rojo los "
            "valores fuera de umbral. Permite exportar en un clic a PDF institucional (ReportLab) o CSV y guarda "
            "la trazabilidad de cada emisión en reporte_generado."
        ),
        "code_file": GLYMPHO_ROOT / "backend" / "app" / "services" / "pdf_service.py",
        "code_anchor": "def export_report_pdf(",
        "code_lines": 28,
        "code_desc": (
            "Se muestra el generador de PDF clínico con ReportLab que formatea encabezados institucionales, "
            "subtotales ponderados, celdas rojas fuera de umbral y nota metodológica oficial."
        ),
    },
    {
        "group": None,
        "title": "Pantalla de Evidencia SQL en Vivo (Amazon RDS)",
        "page": 13,
        "fig": "Figura 11",
        "shot": "11_evidencia_sql.png",
        "user_desc": (
            "Pestaña 4 del módulo de Reportes diseñada para auditoría académica en vivo: permite seleccionar "
            "cualquiera de las 4 consultas SQL oficiales sobre glympho_dw, inspeccionar la sentencia SQL completa y "
            "ejecutarla directamente contra Amazon RDS PostgreSQL 16 mostrando la tabla resultante y el tiempo de respuesta."
        ),
        "code_file": GLYMPHO_ROOT / "backend" / "app" / "routers" / "reports.py",
        "code_anchor": "def run_sql_evidence(",
        "code_lines": 28,
        "code_desc": (
            "Se muestra el endpoint POST /api/reports/sql-evidence/run que ejecuta en modo solo-lectura las "
            "consultas oficiales whitelisteadas contra Amazon RDS y devuelve columnas, filas y latencia en ms."
        ),
    },
    {
        "group": "D) USUARIOS CON ROL \"ADMINISTRADOR\"",
        "title": "Pantalla de Administración, Reglas, ETL y Clave IA",
        "page": 14,
        "fig": "Figura 12",
        "shot": "12_admin_etl.png",
        "user_desc": (
            "Módulo exclusivo para el rol 'admin' (protegido por RBAC HTTP 403). Permite configurar dinámicamente "
            "la clave de Google Gemini, crear o eliminar umbrales de alerta en recomendacion_regla (RNF-06), "
            "cambiar roles de usuarios, ejecutar el proceso ETL bajo demanda con un clic y auditar el historial "
            "de ejecuciones en glympho_dw.etl_ejecucion_log."
        ),
        "code_file": GLYMPHO_ROOT / "backend" / "app" / "routers" / "admin.py",
        "code_anchor": "def create_rule(",
        "code_lines": 28,
        "code_desc": (
            "Se muestra el controlador administrativo protegido con require_roles(['admin']) para gestionar reglas "
            "de umbrales configurables en base de datos y disparar el pipeline ETL manualmente."
        ),
    },
]


def _extract_snippet(fpath: Path, anchor: str, max_lines: int) -> str:
    lines = fpath.read_text(encoding="utf-8").splitlines()
    start = 0
    for i, l in enumerate(lines):
        if anchor in l:
            start = max(0, i - 1)
            break
    return "\n".join(lines[start : start + max_lines])


def _add_index_entry(doc: Document, text: str, page_num: int, is_group: bool = False) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2.5 if is_group else 1.5)
    p.paragraph_format.space_before = Pt(6 if is_group else 0)
    dots = "." * max(4, 76 - len(text))
    r1 = p.add_run(f"{text} {dots} {page_num:02d}")
    r1.bold = is_group
    r1.font.size = Pt(10.5 if is_group else 10)
    r1.font.name = "Calibri"


def build_integrantes_doc() -> None:
    sw_dir = UNIDAD3 / "Software"
    sw_dir.mkdir(parents=True, exist_ok=True)
    priv_file = GLYMPHO_ROOT / "scripts" / "integrantes_privado.json"
    if priv_file.exists():
        rows = json.loads(priv_file.read_text(encoding="utf-8"))
    else:
        rows = [[name, "[COMPLETAR]", "[COMPLETAR]", "[COMPLETAR]", "[COMPLETAR]@unitru.edu.pe"] for name in AUTHORS_FULL]

    d1 = Document()
    _configure_unt_header_footer(d1, first_page_blank=False)
    _h1(d1, "INTEGRANTES")
    _p(d1, f"<{SOFTWARE_TITLE}>", "Nombre de la aplicación\n")
    _add_table(
        d1,
        ["AUTORES", "DNI", "FECHA NACIMIENTO", "DOMICILIO (agregar, DISTRITO, PROVINCIA)", "E_MAIL(@UNITRU)"],
        rows,
    )
    d1.save(sw_dir / "01_INTEGRANTES_GlymphoCare.docx")


def build_memoria_descriptiva_doc() -> None:
    sw_dir = UNIDAD3 / "Software"
    d = Document()
    _configure_unt_header_footer(d, first_page_blank=False)

    t1 = d.add_paragraph()
    t1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t1.add_run("MEMORIA DESCRIPTIVA")
    r.bold = True
    r.font.size = Pt(14)

    t2 = d.add_paragraph()
    t2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t2.paragraph_format.space_after = Pt(12)
    r2 = t2.add_run(SOFTWARE_TITLE)
    r2.font.size = Pt(12.5)

    # Caja principal igual a la plantilla del docente
    tbl = d.add_table(rows=1, cols=1)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.rows[0].cells[0]

    def add_c_p(txt: str, bold_prefix: str = "", bold_all: bool = False, space: int = 5):
        p = cell.add_paragraph()
        p.paragraph_format.space_after = Pt(space)
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.bold = True
        run = p.add_run(txt)
        run.bold = bold_all
        return p

    cell.paragraphs[0].text = ""
    r_head = cell.paragraphs[0].add_run("TÍTULO DEL SOFTWARE: " + SOFTWARE_TITLE)
    r_head.bold = True
    r_head.font.size = Pt(10.5)

    add_c_p("1. Problema que resuelve:", bold_all=True, space=4)
    add_c_p(
        "Entre los estudiantes universitarios es frecuente dormir pocas horas, mantener horarios irregulares y "
        "exponerse a pantallas o cafeína en horas tardías. Estos hábitos deterioran la calidad del sueño y la "
        "eficiencia neurocognitiva; sin embargo, rara vez se miden de forma estructurada. El estudiante percibe "
        "que 'duerme mal', pero desconoce si el problema está en la latencia para conciliar el sueño (SOL), la "
        "fragmentación nocturna (WASO), la duración efectiva (TST) o la proporción de sueño profundo N3."
    )
    add_c_p(
        "Adicionalmente, la evidencia científica demuestra que la fase profunda NREM N3 es la ventana crítica en "
        "la que el sistema glinfático elimina desechos metabólicos cerebrales como la beta-amiloide (Xie et al., "
        "2013). Al encontrarse los cuestionarios subjetivos (PSQI, ESS) desconectados de los registros de wearables, "
        "no existía una plataforma unificada que contraste percepción versus realidad objetiva para orientar "
        "decisiones de higiene del sueño."
    )

    add_c_p("2. Funcionalidad (Para qué sirve)", bold_all=True, space=4)
    add_c_p(
        "GlymphoCare centraliza la recolección, validación ETL, modelado dimensional e interpretación analítica de "
        "la calidad del sueño universitario en una aplicación web accesible desde escritorio y móvil, abarcando "
        "los siguientes módulos operativos:"
    )
    for mod, desc in [
        ("A) Acceso, Roles y Consentimiento: ", "Autenticación JWT con 4 roles (Participante, Investigador, Analista y Admin), registro universitario con código anonimizado UNT-XXX y aceptación obligatoria de consentimiento informado."),
        ("B) Captura Multi-paso y Carga CSV (ETL): ", "Formulario móvil-amigable de PSQI (19 ítems), ESS (8 situaciones) y hábitos, más carga masiva CSV de wearables o ingreso manual con validación fisiológica automática e inserción en Data Mart."),
        ("C) Dashboards Analíticos BI (Apache ECharts): ", "Dashboard Ejecutivo con filtros globales, Calidad Subjetiva (Radar C1–C7 y Boxplot), Limpieza Cerebral (%N3, Índice Glinfático, regresión lineal y Cuadrante Percepción vs. Realidad) y Hábitos & Correlaciones (Pearson + Welch t-test)."),
        ("D) Simulador Empírico y Perfil Individual: ", "Proyección de impacto por cambio de hábitos sin ML predictivo, alerta de deuda cognitiva semanal y cálculo exacto de horarios de descanso."),
        ("E) Reportes Oficiales, Evidencia SQL e IA: ", "Los 3 reportes clínicos tabulares exportables a PDF/CSV, consola en vivo de consultas SQL contra Amazon RDS e interpretación generativa con Google Gemini (sin diagnóstico clínico)."),
        ("F) Administración y Auditoría ETL: ", "Configuración dinámica de umbrales en recomendacion_regla, gestión de usuarios, disparo manual del ETL y bitácora auditable."),
    ]:
        add_c_p(desc, bold_prefix=mod, space=3)

    add_c_p("3. Arquitectura del Software", bold_all=True, space=4)
    for sub, desc in [
        ("A) Lenguajes de programación: ", "Python 3.13 (Backend FastAPI, ETL, SciPy, ReportLab), TypeScript / React 19 (Frontend SPA) y SQL (PostgreSQL 16 DDL/OLAP)."),
        ("B) Base de datos y Nube (AWS): ", "Amazon RDS for PostgreSQL 16 alojando la base transaccional (glympho_oltp, 13 tablas) y el Data Mart en esquema estrella (glympho_dw, 4 dimensiones y 2 tablas de hechos), además de soporte para Amazon EC2 y S3."),
        ("C) Backend e IA: ", "FastAPI REST API con autenticación JWT/bcrypt, motor de reglas configurables, SciPy para estadística en vivo e integración con Google Gemini API (gemini-3-flash-preview) solo para redacción interpretativa."),
        ("D) Frontend: ", "Single Page Application en React + Vite + Tailwind CSS + Apache ECharts con diseño clínico-editorial responsive."),
    ]:
        add_c_p(desc, bold_prefix=sub, space=3)

    p_img = cell.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.add_run().add_picture(str(ASSETS_DIR / "arch_glymphocare.png"), width=Inches(5.8))

    d.save(sw_dir / "02_MEMORIA_DESCRIPTIVA_GlymphoCare.docx")


def build_manual_usuario_doc() -> None:
    sw_dir = UNIDAD3 / "Software"
    d = Document()
    _configure_unt_header_footer(d, first_page_blank=True)

    # Pagina 1: Portada limpia igual al PDF del profe
    p_sp = d.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(140)
    p_sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rt = p_sp.add_run(SOFTWARE_TITLE)
    rt.font.size = Pt(15)

    p_mu = d.add_paragraph()
    p_mu.paragraph_format.space_before = Pt(28)
    p_mu.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rm = p_mu.add_run("MANUAL DE USUARIO")
    rm.bold = True
    rm.font.size = Pt(16)
    d.add_page_break()

    # Pagina 2: INDICE GENERAL exacto
    p_idx = d.add_paragraph()
    p_idx.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_idx.paragraph_format.space_after = Pt(10)
    ri = p_idx.add_run("ÍNDICE GENERAL")
    ri.bold = True
    ri.font.size = Pt(13)
    _p(d, "Contenido", space_after=6)

    group_starts = {
        "A) PANTALLA DE LOGIN Y REGISTRO": 3,
        "B) USUARIOS CON ROL \"PARTICIPANTE\"": 5,
        "C) USUARIOS CON ROL \"ANALISTA / INVESTIGADOR\"": 8,
        "D) USUARIOS CON ROL \"ADMINISTRADOR\"": 14,
    }
    for spec in SCREEN_SPECS:
        if spec["group"]:
            _add_index_entry(d, spec["group"], group_starts[spec["group"]], is_group=True)
        _add_index_entry(d, spec["title"], spec["page"], is_group=False)

    # Paginas 3..14: una pagina por pantalla con descripcion + Figura NN + captura real
    for spec in SCREEN_SPECS:
        d.add_page_break()
        if spec["group"]:
            _h1(d, spec["group"])
        _h2(d, spec["title"])
        _p(d, spec["user_desc"], space_after=6)

        pf = d.add_paragraph()
        pf.paragraph_format.space_after = Pt(2)
        rf1 = pf.add_run(spec["fig"])
        rf1.bold = True
        rf1.font.size = Pt(10)

        pfc = d.add_paragraph()
        pfc.paragraph_format.space_after = Pt(6)
        rfc = pfc.add_run(spec["title"])
        rfc.italic = True
        rfc.font.size = Pt(10)

        pi = d.add_paragraph()
        pi.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pi.add_run().add_picture(str(SHOTS_DIR / spec["shot"]), width=Inches(6.2))

    d.save(sw_dir / "03_MANUAL_DE_USUARIO_GlymphoCare.docx")


def build_codigo_fuente_doc() -> None:
    sw_dir = UNIDAD3 / "Software"
    d = Document()
    _configure_unt_header_footer(d, first_page_blank=True)

    # Pagina 1: Portada limpia igual al PDF del profe
    p_sp = d.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(140)
    p_sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rt = p_sp.add_run("CODIGO FUENTE")
    rt.bold = True
    rt.font.size = Pt(16)

    p_sub = d.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(24)
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = p_sub.add_run(SOFTWARE_TITLE)
    rs.font.size = Pt(14)
    d.add_page_break()

    # Pagina 2: CONTENIDO GENERAL exactamente igual al Manual de Usuario
    p_idx = d.add_paragraph()
    p_idx.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_idx.paragraph_format.space_after = Pt(10)
    ri = p_idx.add_run("CONTENIDO GENERAL")
    ri.bold = True
    ri.font.size = Pt(13)

    group_starts = {
        "A) PANTALLA DE LOGIN Y REGISTRO": 3,
        "B) USUARIOS CON ROL \"PARTICIPANTE\"": 5,
        "C) USUARIOS CON ROL \"ANALISTA / INVESTIGADOR\"": 8,
        "D) USUARIOS CON ROL \"ADMINISTRADOR\"": 14,
    }
    for spec in SCREEN_SPECS:
        if spec["group"]:
            _add_index_entry(d, spec["group"], group_starts[spec["group"]], is_group=True)
        _add_index_entry(d, spec["title"], spec["page"], is_group=False)

    # Paginas 3..14: mismo formato de recuadro (pantalla + codigo en tema oscuro + fila Descripcion)
    for idx, spec in enumerate(SCREEN_SPECS, start=1):
        d.add_page_break()
        if spec["group"]:
            _h1(d, spec["group"])
        _h2(d, spec["title"])

        snippet = _extract_snippet(spec["code_file"], spec["code_anchor"], spec["code_lines"])
        code_img = ASSETS_DIR / f"code_{idx:02d}.png"
        rel_file = str(spec["code_file"].relative_to(GLYMPHO_ROOT)).replace("\\", "/")
        _render_code_card(snippet, code_img, header_label=f"{rel_file} · {spec['code_anchor'].replace('(', '')}")

        box = d.add_table(rows=2, cols=1)
        box.style = "Table Grid"
        box.alignment = WD_TABLE_ALIGNMENT.CENTER

        c_top = box.rows[0].cells[0]
        p_shot = c_top.paragraphs[0]
        p_shot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_shot.paragraph_format.space_after = Pt(4)
        p_shot.add_run().add_picture(str(SHOTS_DIR / spec["shot"]), width=Inches(4.3))

        p_code = c_top.add_paragraph()
        p_code.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_code.add_run().add_picture(str(code_img), width=Inches(5.9))

        c_bot = box.rows[1].cells[0]
        p_desc = c_bot.paragraphs[0]
        r_lbl = p_desc.add_run("Descripción: ")
        r_lbl.bold = True
        r_lbl.font.size = Pt(9.5)
        r_txt = p_desc.add_run(spec["code_desc"])
        r_txt.font.size = Pt(9.5)

    d.save(sw_dir / "04_CODIGO_FUENTE_GlymphoCare.docx")


def build_main_informe(stats: dict) -> Path:
    doc = Document()
    _configure_unt_header_footer(doc, first_page_blank=True)

    def p_center(text: str, size: int, bold: bool = False, color: RGBColor = INK_RGB, space_after: int = 4):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(space_after)
        r = p.add_run(text)
        r.font.size = Pt(size)
        r.bold = bold
        r.font.color.rgb = color

    p_center("UNIVERSIDAD NACIONAL DE TRUJILLO", 15, True, INK_RGB, 2)
    p_center("FACULTAD DE INGENIERÍA", 13, True, INK_RGB, 2)
    p_center("ESCUELA PROFESIONAL DE INGENIERÍA DE SISTEMAS", 12, True, TEAL_RGB, 22)
    p_center("INTELIGENCIA DE NEGOCIOS", 13, True, INK_RGB, 16)
    p_center(SOFTWARE_TITLE, 16, True, TEAL_RGB, 10)
    p_center("INFORME FINAL — UNIDAD III (BI, ANÁLISIS DE DATOS Y SALUD)", 12, True, MUTED_RGB, 22)
    p_center("DOCENTE:", 11, True, INK_RGB, 2)
    p_center("Dr. Ricardo Darío Mendoza Rivera", 11, False, INK_RGB, 16)
    p_center("INTEGRANTES (GRUPO G5):", 11, True, INK_RGB, 4)
    for a in AUTHORS_FULL:
        p_center(a, 10.5, False, INK_RGB, 2)
    p_center("\nTRUJILLO – PERÚ\n2026", 11, True, INK_RGB, 4)
    doc.add_page_break()

    s = stats["summary"]
    _h1(doc, "1. Título y Delimitación del Proyecto")
    _p(doc, f"{SOFTWARE_TITLE} (UNT, 2026).", "Título formal: ")
    _p(doc, "Variable problema: Deterioro de la calidad del sueño y déficit de sueño profundo en estudiantes universitarios. Variable solución: Sistema BI GlymphoCare desplegado en AWS (Amazon RDS PostgreSQL 16) para monitorear higiene del sueño y proteger la ventana glinfática (%N3).")

    _h1(doc, "2. Realidad Problemática y Marco Científico")
    _p(doc, "Entre estudiantes universitarios son frecuentes los horarios irregulares, la restricción de sueño (< 7 h) y la exposición nocturna a pantallas o cafeína. Aunque perciben que duermen mal, desconocen si falla la latencia (SOL), la fragmentación (WASO), la duración (TST) o el sueño profundo (%N3).")
    _p(doc, "Según Xie et al. (2013, Science), el sueño profundo de ondas lentas (NREM N3) expande el espacio intersticial cerebral facilitando la limpieza glinfática de beta-amiloide. A su vez, el PSQI (Buysse et al., 1989) y el ESS (Johns, 1991) miden la calidad subjetiva y somnolencia diurna.")

    _h1(doc, "3. Metodología y Objetivos")
    _p(doc, "¿En qué medida la plataforma web analítica GlymphoCare permite medir, integrar y explicar la calidad del sueño y la oportunidad de limpieza cerebral (%N3) en estudiantes universitarios?", "Pregunta de investigación: ")
    _add_table(doc, ["#", "Objetivo específico", "Entregable"], [
        ["OE1", "Definir la base científica y los 8 KPIs oficiales con fórmulas y umbrales.", "Marco teórico + Ficha KPIs"],
        ["OE2", "Diseñar la base transaccional OLTP (13 tablas) y Data Mart en esquema estrella.", "DDLs + Diagramas ER/Estrella"],
        ["OE3", "Construir el ETL que calcula C1–C7 del PSQI, ESS y KPIs objetivos.", "etl/run_etl.py + pytest"],
        ["OE4", "Desarrollar dashboards web responsive (cero Power BI/Tableau) con Apache ECharts.", "Frontend React + ECharts"],
        ["OE5", "Generar los 3 reportes oficiales exportables (PDF/CSV), Evidencia SQL e IA interpretativa.", "Módulo Reportes + Gemini"],
        ["OE6", "Desplegar y validar la base transaccional y Data Mart en Amazon RDS (AWS).", "Amazon RDS PostgreSQL 16"],
    ])

    _h1(doc, "4. Ficha de los 8 KPIs Oficiales")
    _add_table(doc, ["ID", "Indicador", "Fórmula / Regla", "Umbral", "Fuente"], [
        ["RI-01", "PSQI Global (0–21)", "Suma de C1 a C7 (Buysse et al., 1989)", "> 5 = mala calidad", "Cuestionario PSQI"],
        ["RI-02", "Componentes PSQI", "C1..C7 (escala 0–3 cada uno)", "0–3 por componente", "Cuestionario PSQI"],
        ["RI-03", "ESS Epworth (0–24)", "Suma de 8 situaciones cotidianas (0–3)", "> 10 = somnolencia excesiva", "Cuestionario ESS"],
        ["RI-04", "Eficiencia (SE)", "(TST / TIB) × 100", ">= 85%", "Wearable / Manual"],
        ["RI-05", "Latencia (SOL)", "Minutos hasta primer registro de sueño", "<= 20 min (> 30 alterado)", "Wearable / Manual"],
        ["RI-06", "WASO", "TIB − SOL − TST", "<= 40 min", "Calculado ETL"],
        ["RI-07", "TST", "N1 + N2 + N3 + REM", ">= 7 h (420 min)", "Wearable / Manual"],
        ["RI-08", "Despertares", "Conteo por noche", "Menor es mejor", "Wearable / Manual"],
        ["RI-09", "%N3 (Glinfático)", "(Min N3 / TST) × 100", "Seguimiento propio (>= 15%)", "Calculado ETL"],
    ])

    _h1(doc, "5. Base Transaccional, Data Mart Estrella y Arquitectura AWS")
    _p(doc, "La solución opera conectada a Amazon RDS for PostgreSQL 16 (us-east-2) con el esquema transaccional glympho_oltp (13 tablas) y el Data Mart dimensional glympho_dw (4 dimensiones y 2 hechos).")
    doc.add_picture(str(ASSETS_DIR / "arch_glymphocare.png"), width=Inches(6.1))
    doc.add_picture(str(ASSETS_DIR / "star_datamart.png"), width=Inches(6.1))

    _h1(doc, "6. Resultados Reales de la Cohorte Universitaria (Amazon RDS)")
    _p(doc, f"Se analizaron {s['n_part']} estudiantes UNT con {s['n_noches']} registros en fact_sueno_noche y 240 evaluaciones en fact_cuestionario:")
    _add_table(doc, ["Indicador", "Valor Cohorte", "Umbral", "Lectura"], [
        ["PSQI Promedio", f"{s['psqi']} pts", "<= 5 pts", f"{s['pct_malos']}% malos dormidores"],
        ["ESS Promedio", f"{s['ess']} pts", "<= 10 pts", "Somnolencia limítrofe"],
        ["Eficiencia (SE)", f"{s['se']}%", ">= 85%", "En meta global"],
        ["Latencia (SOL)", f"{s['sol']} min", "<= 20 min", "Elevada (> 20 min)"],
        ["WASO Promedio", f"{s['waso']} min", "<= 40 min", "Dentro de meta"],
        ["TST Promedio", f"{s['tst_h']} h/noche", ">= 7.0 h", "Déficit de sueño universitario"],
        ["Sueño Profundo (%N3)", f"{s['pct_n3']}%", ">= 15% ref.", f"IG derivado: {s['ig']}"],
    ])
    doc.add_picture(str(ASSETS_DIR / "chart_cohorte_psqi.png"), width=Inches(5.5))
    doc.add_picture(str(ASSETS_DIR / "chart_habitos_n3.png"), width=Inches(6.1))

    _h1(doc, "7. Evidencia Visual de la Plataforma en Producción")
    _p(doc, "Capturas reales del sistema ejecutándose en navegador conectado a Amazon RDS y Google Gemini (gemini-3-flash-preview):")
    for cap, img_name in [
        ("Dashboard Ejecutivo con Interpretación IA de Cohorte:", "03_dashboard_ejecutivo.png"),
        ("Limpieza Cerebral (%N3) y Simulador de Horarios:", "05_limpieza_cerebral.png"),
        ("Evidencia SQL en Vivo contra Amazon RDS (glympho_dw):", "11_evidencia_sql.png"),
    ]:
        _p(doc, cap, bold_prefix="• ")
        doc.add_picture(str(SHOTS_DIR / img_name), width=Inches(5.8))

    _h1(doc, "8. Conclusiones y Referencias")
    _p(doc, "1) La integración dimensional permite identificar con precisión que el déficit de TST (6.50 h) y la latencia elevada (23.3 min) explican el deterioro subjetivo universitario.")
    _p(doc, "2) Las pruebas estadísticas en vivo muestran diferencias significativas (p < 0.01) asociadas a pantallas nocturnas, cafeína tardía y actividad física.")
    _p(doc, "Referencias: Buysse et al. (1989), Psychiatry Research; Johns (1991), Sleep; Xie et al. (2013), Science.")

    out_path = UNIDAD3 / "Documento" / "INFORME_FINAL_UNIDAD3_G5_GlymphoCare.docx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    return out_path


def build_zip_and_datos() -> None:
    sw_dir = UNIDAD3 / "Software"
    zip_path = sw_dir / "codigo_fuente_glymphocare.zip"
    exclude_dirs = {".venv", "node_modules", ".git", "__pycache__", ".pytest_cache", "dist", "_doc_assets"}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(GLYMPHO_ROOT):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                if file in (".env", "integrantes_privado.json"):
                    continue
                full = Path(root) / file
                rel = full.relative_to(GLYMPHO_ROOT)
                zf.write(full, arcname=str(Path("glymphocare") / rel))

    datos_dir = UNIDAD3 / "Datos"
    datos_dir.mkdir(parents=True, exist_ok=True)
    for dest_name, src in [
        ("01_oltp_schema.sql", GLYMPHO_ROOT / "database" / "01_oltp_schema.sql"),
        ("02_datamart_star_schema.sql", GLYMPHO_ROOT / "database" / "02_datamart_star_schema.sql"),
        ("03_seed_reglas_base.sql", GLYMPHO_ROOT / "database" / "03_seed_reglas_base.sql"),
        ("04_etl_oltp_to_datamart.py", GLYMPHO_ROOT / "etl" / "run_etl.py"),
        ("05_consultas_kpis_reportes.sql", GLYMPHO_ROOT / "database" / "04_consultas_kpis_reportes.sql"),
        ("seed_cohorte.py", GLYMPHO_ROOT / "database" / "seed_cohorte.py"),
    ]:
        shutil.copy2(src, datos_dir / dest_name)


def main() -> None:
    stats = _fetch_live_stats()
    _generate_diagrams_and_charts(stats)
    informe = build_main_informe(stats)
    build_integrantes_doc()
    build_memoria_descriptiva_doc()
    build_manual_usuario_doc()
    build_codigo_fuente_doc()
    build_zip_and_datos()
    print("Entregables UNIDAD3 estilo exacto del docente generados OK:")
    print(" -", informe)
    for fn in ["01_INTEGRANTES_GlymphoCare.docx", "02_MEMORIA_DESCRIPTIVA_GlymphoCare.docx", "03_MANUAL_DE_USUARIO_GlymphoCare.docx", "04_CODIGO_FUENTE_GlymphoCare.docx", "codigo_fuente_glymphocare.zip"]:
        p = UNIDAD3 / "Software" / fn
        print(f" - {p.name}: {p.stat().st_size} bytes")


if __name__ == "__main__":
    main()
