"""Generador de reportes clinicos exportables en PDF (ReportLab) y CSV (UTF-8 BOM)."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


TEAL_HEADER = colors.HexColor("#0F766E")
SUB_BG = colors.HexColor("#E6F4F3")
TOT_BG = colors.HexColor("#BFE5E2")
LINE_COLOR = colors.HexColor("#CBD5E1")
INK_DARK = colors.HexColor("#14202B")
INK_MUTED = colors.HexColor("#5A6877")
BAD_RED = colors.HexColor("#B91C1C")


def _fmt_num(val: Any, dec: int) -> str:
    if isinstance(val, (int, float)):
        if dec == 0:
            return f"{int(round(val))}"
        return f"{val:.{dec}f}"
    return str(val)


def export_report_csv(report: Dict[str, Any]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["GlymphoCare - UNT Ingenieria de Sistemas", report["title"], f"n={report['n_sample']}"])
    writer.writerow(["Indicador / Segmento"] + report["columns"])
    for row in report["rows"]:
        if row["type"] == "group":
            writer.writerow([f"[{row['label']}]"])
        else:
            vals = [_fmt_num(v, report["decimals"][idx]) for idx, v in enumerate(row["values"])]
            writer.writerow([row["label"]] + vals)
    writer.writerow([])
    writer.writerow(["Nota metodologica", report["note"]])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def export_report_pdf(report: Dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
        topMargin=1.3 * cm,
        bottomMargin=1.3 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("GC_Title", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=INK_DARK, spaceAfter=2)
    sub_style = ParagraphStyle("GC_Sub", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=INK_MUTED, spaceAfter=8)
    note_style = ParagraphStyle("GC_Note", parent=styles["Normal"], fontName="Helvetica", fontSize=8, textColor=INK_MUTED, leading=11)

    story = [
        Paragraph(f"GlymphoCare · UNT Ingeniería de Sistemas — {report['title']}", title_style),
        Paragraph(
            f"{report['subtitle']} · Unidad: {report['unit']} · Muestra activa: n = {report['n_sample']} · Emitido: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            sub_style,
        ),
    ]

    table_data = [["Segmento / Categoría"] + report["columns"]]
    row_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), TEAL_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    for r_idx, row in enumerate(report["rows"], start=1):
        if row["type"] == "group":
            table_data.append([row["label"]] + [""] * len(report["columns"]))
            row_styles.append(("SPAN", (0, r_idx), (-1, r_idx)))
            row_styles.append(("FONTNAME", (0, r_idx), (-1, r_idx), "Helvetica-Bold"))
            row_styles.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F1F5F9")))
            continue

        formatted = [_fmt_num(v, report["decimals"][c_idx]) for c_idx, v in enumerate(row["values"])]
        prefix = "   " if row["type"] == "item" else ""
        table_data.append([prefix + row["label"]] + formatted)

        if row["type"] == "subtotal":
            row_styles.append(("BACKGROUND", (0, r_idx), (-1, r_idx), SUB_BG))
            row_styles.append(("FONTNAME", (0, r_idx), (-1, r_idx), "Helvetica-Bold"))
        elif row["type"] == "total":
            row_styles.append(("BACKGROUND", (0, r_idx), (-1, r_idx), TOT_BG))
            row_styles.append(("FONTNAME", (0, r_idx), (-1, r_idx), "Helvetica-Bold"))

        for c_idx, is_bad in enumerate(row.get("bad", [])):
            if is_bad:
                row_styles.append(("TEXTCOLOR", (c_idx + 1, r_idx), (c_idx + 1, r_idx), BAD_RED))
                row_styles.append(("FONTNAME", (c_idx + 1, r_idx), (c_idx + 1, r_idx), "Helvetica-Bold"))

    col_count = len(report["columns"]) + 1
    first_col_w = 7.2 * cm
    other_w = (26.8 * cm - first_col_w) / max(1, col_count - 1)
    tbl = Table(table_data, colWidths=[first_col_w] + [other_w] * (col_count - 1), repeatRows=1)
    tbl.setStyle(TableStyle(row_styles))
    story.append(tbl)
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Nota metodológica:</b> {report['note']}", note_style))
    story.append(Paragraph("<b>Alcance:</b> Reporte analítico de higiene del sueño. No constituye diagnóstico clínico médico.", note_style))

    doc.build(story)
    return buf.getvalue()
