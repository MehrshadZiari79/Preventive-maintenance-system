# utils/export_service.py
"""
Export Service — Excel and PDF generation for all modules.
Libraries: openpyxl (Excel), reportlab (PDF).
All text is Persian-friendly; charts use English labels (matplotlib RTL issue).
"""
import os
from datetime import datetime
from pathlib import Path

# ── Excel ────────────────────────────────────────────────────────────────────
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter

# ── PDF ──────────────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Constants ────────────────────────────────────────────────────────────────
COMPANY_NAME = "شرکت گلا دری — آمل"
APP_NAME     = "سیستم مدیریت نگهداری پیشگیرانه"

# Colour palette (matches app theme)
C_PRIMARY  = "1A73E8"
C_SUCCESS  = "34A853"
C_WARNING  = "F29900"
C_DANGER   = "EA4335"
C_LIGHT    = "E8F0FE"
C_SUBTLE   = "5F6368"
C_WHITE    = "FFFFFF"
C_DARK     = "202124"

# reportlab colours
RL_PRIMARY = colors.HexColor("#1A73E8")
RL_SUCCESS = colors.HexColor("#34A853")
RL_WARNING = colors.HexColor("#F29900")
RL_DANGER  = colors.HexColor("#EA4335")
RL_LIGHT   = colors.HexColor("#E8F0FE")
RL_SUBTLE  = colors.HexColor("#5F6368")
RL_DARK    = colors.HexColor("#202124")
RL_WHITE   = colors.white

# ── Font registration (uses built-in Helvetica — no Persian font needed
#    because we transliterate headings to English and keep data as-is) ──────
#  NOTE: reportlab can render Persian *data* correctly without a special font
#  when using Paragraph objects with right-to-left text. For table cells
#  that contain Persian we use Paragraph wrappers.

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def _date_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _para(text: str, style) -> Paragraph:
    """Wrap text in a Paragraph for RTL support inside table cells."""
    return Paragraph(str(text), style)


# ═══════════════════════════════════════════════════════════════════════════
#  EXCEL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _xl_header_style(ws, row: int, cols: int, title: str):
    """Write a merged header row with company + title."""
    ws.merge_cells(start_row=row, start_column=1,
                   end_row=row, end_column=cols)
    cell = ws.cell(row=row, column=1, value=COMPANY_NAME)
    cell.font      = Font(bold=True, size=11, color=C_WHITE)
    cell.fill      = PatternFill("solid", fgColor=C_PRIMARY)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row].height = 24

    ws.merge_cells(start_row=row + 1, start_column=1,
                   end_row=row + 1, end_column=cols)
    cell2 = ws.cell(row=row + 1, column=1, value=title)
    cell2.font      = Font(bold=True, size=13, color=C_WHITE)
    cell2.fill      = PatternFill("solid", fgColor=C_PRIMARY)
    cell2.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row + 1].height = 28

    ws.merge_cells(start_row=row + 2, start_column=1,
                   end_row=row + 2, end_column=cols)
    cell3 = ws.cell(row=row + 2, column=1,
                    value=f"تاریخ تهیه: {_now_str()}")
    cell3.font      = Font(size=9, color=C_SUBTLE)
    cell3.fill      = PatternFill("solid", fgColor=C_LIGHT)
    cell3.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row + 2].height = 18


def _xl_col_header(ws, row: int, headers: list[str]):
    """Write styled column headers."""
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col, text in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font      = Font(bold=True, size=10, color=C_WHITE)
        cell.fill      = PatternFill("solid", fgColor="2C3E50")
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)
        cell.border    = border
    ws.row_dimensions[row].height = 22


def _xl_data_row(ws, row: int, values: list, zebra: bool = False):
    """Write a data row with alternating background."""
    thin = Side(style="thin", color="DDDDDD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    bg = "F5F7FA" if zebra else C_WHITE
    for col, val in enumerate(values, 1):
        cell = ws.cell(row=row, column=col, value=val)
        cell.fill      = PatternFill("solid", fgColor=bg)
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)
        cell.border    = border
    ws.row_dimensions[row].height = 20


def _xl_auto_width(ws, min_w: int = 12, max_w: int = 40):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = max(min_w, min(max_len + 4, max_w))


# ═══════════════════════════════════════════════════════════════════════════
#  PDF HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _pdf_styles():
    """Return a dict of named ParagraphStyles."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=RL_PRIMARY,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName="Helvetica",
            fontSize=10,
            textColor=RL_SUBTLE,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "section": ParagraphStyle(
            "section",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=RL_WHITE,
            alignment=TA_LEFT,
            spaceAfter=4,
            spaceBefore=8,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=9,
            textColor=RL_DARK,
            alignment=TA_RIGHT,
            spaceAfter=2,
        ),
        "cell": ParagraphStyle(
            "cell",
            fontName="Helvetica",
            fontSize=8,
            textColor=RL_DARK,
            alignment=TA_RIGHT,
            leading=11,
        ),
        "cell_bold": ParagraphStyle(
            "cell_bold",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=RL_DARK,
            alignment=TA_RIGHT,
            leading=11,
        ),
        "small": ParagraphStyle(
            "small",
            fontName="Helvetica",
            fontSize=7,
            textColor=RL_SUBTLE,
            alignment=TA_CENTER,
        ),
        "label": ParagraphStyle(
            "label",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=RL_PRIMARY,
            alignment=TA_RIGHT,
        ),
    }


def _pdf_header(story: list, title: str, subtitle: str = ""):
    """Add a standard document header to the story."""
    st = _pdf_styles()
    story.append(Paragraph(COMPANY_NAME, st["subtitle"]))
    story.append(Paragraph(title, st["title"]))
    if subtitle:
        story.append(Paragraph(subtitle, st["subtitle"]))
    story.append(Paragraph(f"Generated: {_now_str()}", st["small"]))
    story.append(HRFlowable(width="100%", thickness=2,
                            color=RL_PRIMARY, spaceAfter=10))


def _pdf_section(story: list, text: str):
    """Add a coloured section divider."""
    tbl = Table([[text]], colWidths=["100%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), RL_PRIMARY),
        ("TEXTCOLOR",   (0, 0), (-1, -1), RL_WHITE),
        ("FONTNAME",    (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 4))


def _pdf_kv_table(story: list, pairs: list[tuple[str, str]], cols: int = 2):
    """Render key-value pairs in a clean grid table."""
    st = _pdf_styles()
    # Group into rows of `cols` pairs
    rows = []
    row  = []
    for label, value in pairs:
        row.extend([
            _para(label, st["label"]),
            _para(value or "—", st["cell"]),
        ])
        if len(row) == cols * 2:
            rows.append(row)
            row = []
    if row:
        # Pad incomplete last row
        while len(row) < cols * 2:
            row.extend([_para("", st["label"]), _para("", st["cell"])])
        rows.append(row)

    col_w = A4[0] - 3 * cm   # usable width
    unit  = col_w / (cols * 2)
    col_widths = [unit * 0.8, unit * 1.2] * cols

    tbl = Table(rows, colWidths=col_widths, repeatRows=0)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.HexColor("#F5F7FA"), colors.white]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))


def _pdf_data_table(story: list, headers: list[str],
                    rows: list[list], col_widths=None):
    """Render a full data table with styled headers."""
    st   = _pdf_styles()
    page_w = A4[0] - 3 * cm

    if col_widths is None:
        col_widths = [page_w / len(headers)] * len(headers)

    header_row = [_para(h, st["cell_bold"]) for h in headers]
    data_rows  = [
        [_para(str(v) if v is not None else "—", st["cell"]) for v in row]
        for row in rows
    ]

    table_data = [header_row] + data_rows

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    row_bgs = [colors.HexColor("#F5F7FA"), colors.white]
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  RL_PRIMARY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  RL_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  9),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), row_bgs),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))


def _pdf_signature_row(story: list, labels: list[str]):
    """Add a signature row at the bottom of a form."""
    st   = _pdf_styles()
    page_w = A4[0] - 3 * cm
    col_w  = page_w / len(labels)

    rows = [
        [_para(lbl, st["cell_bold"]) for lbl in labels],
        [_para("", st["cell"]) for _ in labels],
        [_para("امضاء: _______________", st["small"]) for _ in labels],
        [_para("تاریخ: _______________", st["small"]) for _ in labels],
    ]
    tbl = Table(rows, colWidths=[col_w] * len(labels))
    tbl.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.8, RL_SUBTLE),
        ("INNERGRID",     (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND",    (0, 0), (-1, 0),  RL_LIGHT),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
    ]))
    story.append(Spacer(1, 16))
    story.append(tbl)


# ═══════════════════════════════════════════════════════════════════════════
#  EQUIPMENT EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

def export_equipment_excel(equipment_list: list[dict], path: str) -> str:
    """Export full equipment list to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Equipment List"
    ws.sheet_view.rightToLeft = True

    headers = ["کد", "نام تجهیز", "دسته‌بندی", "سازنده", "مدل",
               "موقعیت", "وضعیت", "سطح اهمیت", "تاریخ نصب", "آخرین بروزرسانی"]

    _xl_header_style(ws, 1, len(headers), "لیست تجهیزات")
    _xl_col_header(ws, 4, headers)

    STATUS_FA = {
        "operational": "عملیاتی",
        "maintenance": "در تعمیر",
        "breakdown":   "خراب",
        "inactive":    "غیرفعال",
    }

    for i, eq in enumerate(equipment_list):
        _xl_data_row(ws, 5 + i, [
            eq.get("code", ""),
            eq.get("name", ""),
            eq.get("category", ""),
            eq.get("manufacturer", ""),
            eq.get("model", ""),
            eq.get("location", ""),
            STATUS_FA.get(eq.get("status", ""), eq.get("status", "")),
            eq.get("criticality_level", ""),
            eq.get("installation_date", ""),
            eq.get("updated_at", ""),
        ], zebra=(i % 2 == 1))

    _xl_auto_width(ws)
    wb.save(path)
    return path


def export_equipment_card_pdf(equipment: dict, path: str) -> str:
    """Export a single equipment card as a PDF."""
    doc   = SimpleDocTemplate(path, pagesize=A4,
                              leftMargin=1.5*cm, rightMargin=1.5*cm,
                              topMargin=1.5*cm, bottomMargin=1.5*cm)
    story = []
    st    = _pdf_styles()

    STATUS_FA = {
        "operational": "عملیاتی",
        "maintenance": "در تعمیر",
        "breakdown":   "خراب",
        "inactive":    "غیرفعال",
    }

    _pdf_header(story, "Equipment Card", f"کد: {equipment.get('code', '')}")
    _pdf_section(story, "Basic Information — اطلاعات پایه")
    _pdf_kv_table(story, [
        ("Equipment Code / کد تجهیز",     equipment.get("code", "")),
        ("Name / نام",                     equipment.get("name", "")),
        ("Category / دسته‌بندی",           equipment.get("category", "")),
        ("Location / موقعیت",              equipment.get("location", "")),
        ("Status / وضعیت",                 STATUS_FA.get(equipment.get("status", ""), "")),
        ("Criticality / سطح اهمیت",        equipment.get("criticality_level", "")),
        ("Manufacturer / سازنده",          equipment.get("manufacturer", "")),
        ("Model / مدل",                    equipment.get("model", "")),
        ("Serial No. / شماره سریال",       equipment.get("serial_number", "")),
        ("Install Date / تاریخ نصب",       equipment.get("installation_date", "")),
    ])

    _pdf_section(story, "Technical Specs — مشخصات فنی")
    specs = equipment.get("specifications", "") or "—"
    story.append(_para(specs, st["body"]))
    story.append(Spacer(1, 8))

    _pdf_section(story, "Notes — یادداشت")
    notes = equipment.get("notes", "") or "—"
    story.append(_para(notes, st["body"]))
    story.append(Spacer(1, 16))

    _pdf_signature_row(story, ["Responsible Tech / تکنسین مسئول",
                                "Supervisor / سرپرست",
                                "Date / تاریخ"])

    doc.build(story)
    return path


# ═══════════════════════════════════════════════════════════════════════════
#  PM SCHEDULE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

def export_pm_excel(pm_list: list[dict], path: str) -> str:
    """Export PM schedule list to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "PM Schedules"
    ws.sheet_view.rightToLeft = True

    headers = ["شناسه", "عنوان برنامه", "تجهیز", "کد تجهیز", "تکنسین",
               "دوره تناوب", "بازه (روز)", "آخرین انجام",
               "سررسید بعدی", "روز مانده", "وضعیت"]

    FREQ_FA = {
        "daily":     "روزانه",
        "weekly":    "هفتگی",
        "monthly":   "ماهانه",
        "quarterly": "سه‌ماهه",
        "biannual":  "شش‌ماهه",
        "annual":    "سالانه",
        "custom":    "سفارشی",
    }

    _xl_header_style(ws, 1, len(headers), "برنامه‌های نگهداری پیشگیرانه PM")
    _xl_col_header(ws, 4, headers)

    for i, pm in enumerate(pm_list):
        days    = pm.get("days_until")
        overdue = pm.get("is_overdue", False)
        active  = pm.get("is_active", True)

        if not active:
            status = "غیرفعال"
        elif overdue:
            status = "عقب‌افتاده"
        elif days is not None and 0 <= days <= 7:
            status = "این هفته"
        else:
            status = "به‌موقع"

        _xl_data_row(ws, 5 + i, [
            pm.get("id", ""),
            pm.get("title", ""),
            pm.get("equipment_name", ""),
            pm.get("equipment_code", ""),
            pm.get("technician_name", ""),
            FREQ_FA.get(pm.get("frequency", ""), pm.get("frequency", "")),
            pm.get("interval_days", ""),
            pm.get("last_done", ""),
            pm.get("next_due", ""),
            str(days) if days is not None else "—",
            status,
        ], zebra=(i % 2 == 1))

        # Colour overdue rows red
        if overdue and active:
            for col in range(1, len(headers) + 1):
                ws.cell(row=5 + i, column=col).fill = \
                    PatternFill("solid", fgColor="FCE8E6")

    _xl_auto_width(ws)
    wb.save(path)
    return path


def export_pm_form_pdf(pm: dict, path: str) -> str:
    """Export a single PM schedule as a printable work order form."""
    doc   = SimpleDocTemplate(path, pagesize=A4,
                              leftMargin=1.5*cm, rightMargin=1.5*cm,
                              topMargin=1.5*cm, bottomMargin=1.5*cm)
    story = []
    st    = _pdf_styles()

    FREQ_FA = {
        "daily": "روزانه", "weekly": "هفتگی", "monthly": "ماهانه",
        "quarterly": "سه‌ماهه", "biannual": "شش‌ماهه",
        "annual": "سالانه", "custom": "سفارشی",
    }

    _pdf_header(story, "PM Work Order Form",
                f"Preventive Maintenance — نگهداری پیشگیرانه")
    _pdf_section(story, "Schedule Info — اطلاعات برنامه")
    _pdf_kv_table(story, [
        ("PM Title / عنوان",         pm.get("title", "")),
        ("Equipment / تجهیز",        pm.get("equipment_name", "")),
        ("Equipment Code / کد",      pm.get("equipment_code", "")),
        ("Assigned Tech / تکنسین",   pm.get("technician_name", "")),
        ("Frequency / دوره",         FREQ_FA.get(pm.get("frequency", ""), "")),
        ("Interval / بازه (روز)",    str(pm.get("interval_days", ""))),
        ("Last Done / آخرین انجام",  pm.get("last_done", "")),
        ("Next Due / سررسید بعدی",   pm.get("next_due", "")),
        ("Est. Duration / مدت تخمینی", f"{pm.get('estimated_duration', 0)} min"),
        ("Days Remaining / روز مانده",
         str(pm.get("days_until", "")) if pm.get("days_until") is not None else "—"),
    ])

    # Checklist
    _pdf_section(story, "Checklist — چک‌لیست کارها")
    checklist = pm.get("checklist", "") or ""
    items     = [line.strip() for line in checklist.splitlines() if line.strip()]

    if items:
        rows = [[f"☐  {item}"] for item in items]
        tbl  = Table(rows, colWidths=[A4[0] - 3 * cm])
        tbl.setStyle(TableStyle([
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1),
             [colors.white, colors.HexColor("#F5F7FA")]),
            ("BOX",           (0, 0), (-1, -1), 0.5, RL_SUBTLE),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, colors.HexColor("#EEEEEE")),
        ]))
        story.append(tbl)
    else:
        story.append(_para("— بدون چک‌لیست —", st["body"]))

    story.append(Spacer(1, 8))

    # Notes field
    _pdf_section(story, "Notes / یادداشت")
    story.append(
        Table([["" ]], colWidths=[A4[0] - 3*cm], rowHeights=[3*cm])
    )
    story[-1].setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, RL_SUBTLE),
    ]))
    story.append(Spacer(1, 8))

    _pdf_signature_row(story, ["Technician / تکنسین",
                                "Supervisor / سرپرست",
                                "Date / تاریخ"])
    doc.build(story)
    return path


# ═══════════════════════════════════════════════════════════════════════════
#  WORK ORDER EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

def export_work_orders_excel(work_orders: list, path: str) -> str:
    """
    Export work order list to Excel.
    work_orders: list of ORM WorkOrder objects (as returned by wo_repo.get_all()).
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Work Orders"
    ws.sheet_view.rightToLeft = True

    headers = ["شناسه", "عنوان", "تجهیز", "نوع", "اولویت",
               "تکنسین", "وضعیت", "تاریخ برنامه", "شروع", "پایان", "توضیحات"]

    TYPE_FA = {
        "PREVENTIVE": "پیشگیرانه",
        "CORRECTIVE":  "اصلاحی",
        "INSPECTION":  "بازرسی",
        "PM":          "PM",
    }
    PRIORITY_FA = {
        "LOW": "کم", "MEDIUM": "متوسط", "HIGH": "زیاد", "URGENT": "فوری",
    }
    STATUS_FA = {
        "PENDING":     "در انتظار",
        "IN_PROGRESS": "در حال انجام",
        "COMPLETED":   "تکمیل شده",
        "APPROVED":    "تایید شده",
        "REJECTED":    "رد شده",
    }

    _xl_header_style(ws, 1, len(headers), "لیست دستور کارها")
    _xl_col_header(ws, 4, headers)

    STATUS_COLORS = {
        "PENDING":     "FFF8E1",
        "IN_PROGRESS": "E3F2FD",
        "COMPLETED":   "E6F4EA",
        "APPROVED":    "E6F4EA",
        "REJECTED":    "FCE8E6",
    }

    for i, wo in enumerate(work_orders):
        eq_name   = wo.equipment.name if wo.equipment else "—"
        tech_name = wo.technician.full_name if wo.technician else "—"
        status    = wo.status.name
        _xl_data_row(ws, 5 + i, [
            wo.id,
            wo.title,
            eq_name,
            TYPE_FA.get(wo.type.name, wo.type.name),
            PRIORITY_FA.get(wo.priority.name, wo.priority.name),
            tech_name,
            STATUS_FA.get(status, status),
            wo.scheduled_date.strftime("%Y-%m-%d") if wo.scheduled_date else "—",
            wo.start_time.strftime("%Y-%m-%d %H:%M") if wo.start_time else "—",
            wo.end_time.strftime("%Y-%m-%d %H:%M") if wo.end_time else "—",
            wo.description or "",
        ], zebra=(i % 2 == 1))

        # Status colour
        bg = STATUS_COLORS.get(status, C_WHITE)
        for col in range(1, len(headers) + 1):
            ws.cell(row=5 + i, column=col).fill = \
                PatternFill("solid", fgColor=bg)

    _xl_auto_width(ws)
    wb.save(path)
    return path


def export_work_order_form_pdf(wo, path: str) -> str:
    """
    Export a single work order as a printable form PDF.
    wo: ORM WorkOrder object.
    """
    doc   = SimpleDocTemplate(path, pagesize=A4,
                              leftMargin=1.5*cm, rightMargin=1.5*cm,
                              topMargin=1.5*cm, bottomMargin=1.5*cm)
    story = []
    st    = _pdf_styles()

    TYPE_FA = {
        "PREVENTIVE": "Preventive / پیشگیرانه",
        "CORRECTIVE":  "Corrective / اصلاحی",
        "INSPECTION":  "Inspection / بازرسی",
        "PM":          "PM",
    }
    PRIORITY_FA = {
        "LOW": "Low / کم", "MEDIUM": "Medium / متوسط",
        "HIGH": "High / زیاد", "URGENT": "URGENT / فوری",
    }
    STATUS_FA = {
        "PENDING":     "Pending / در انتظار",
        "IN_PROGRESS": "In Progress / در حال انجام",
        "COMPLETED":   "Completed / تکمیل شده",
        "APPROVED":    "Approved / تایید شده",
        "REJECTED":    "Rejected / رد شده",
    }

    eq_name   = wo.equipment.name if wo.equipment else "—"
    tech_name = wo.technician.full_name if wo.technician else "—"

    _pdf_header(story, "Work Order Form",
                f"WO #{wo.id} — {wo.title}")

    _pdf_section(story, "Work Order Details — اطلاعات دستور کار")
    _pdf_kv_table(story, [
        ("WO # / شناسه",              str(wo.id)),
        ("Title / عنوان",             wo.title),
        ("Equipment / تجهیز",         eq_name),
        ("Type / نوع",                TYPE_FA.get(wo.type.name, wo.type.name)),
        ("Priority / اولویت",         PRIORITY_FA.get(wo.priority.name, wo.priority.name)),
        ("Technician / تکنسین",       tech_name),
        ("Status / وضعیت",            STATUS_FA.get(wo.status.name, wo.status.name)),
        ("Scheduled / برنامه‌ریزی",
         wo.scheduled_date.strftime("%Y-%m-%d") if wo.scheduled_date else "—"),
        ("Start / شروع",
         wo.start_time.strftime("%Y-%m-%d %H:%M") if wo.start_time else "—"),
        ("End / پایان",
         wo.end_time.strftime("%Y-%m-%d %H:%M") if wo.end_time else "—"),
    ])

    _pdf_section(story, "Description / توضیحات")
    story.append(_para(wo.description or "—", st["body"]))
    story.append(Spacer(1, 8))

    _pdf_section(story, "Parts Used / قطعات مصرفی")
    story.append(_para(wo.parts_used or "—", st["body"]))
    story.append(Spacer(1, 8))

    _pdf_section(story, "Work Notes / یادداشت اجرا")
    story.append(
        Table([[""]], colWidths=[A4[0] - 3*cm], rowHeights=[2.5*cm])
    )
    story[-1].setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, RL_SUBTLE),
    ]))
    story.append(Spacer(1, 8))

    if wo.supervisor_notes:
        _pdf_section(story, "Supervisor Notes / یادداشت سرپرست")
        story.append(_para(wo.supervisor_notes, st["body"]))
        story.append(Spacer(1, 8))

    _pdf_signature_row(story, ["Technician / تکنسین",
                                "Supervisor / سرپرست",
                                "Date / تاریخ"])
    doc.build(story)
    return path


# ═══════════════════════════════════════════════════════════════════════════
#  INSPECTION EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

def export_inspections_excel(inspections: list[dict], path: str) -> str:
    """Export inspection history list to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Inspections"
    ws.sheet_view.rightToLeft = True

    headers = ["شناسه", "قالب بازرسی", "تجهیز", "بازرس",
               "وضعیت", "نتیجه کلی", "تاریخ شروع", "تاریخ پایان"]

    STATUS_FA = {
        "in_progress": "در حال انجام",
        "completed":   "تکمیل شده",
        "cancelled":   "لغو شده",
    }
    RESULT_FA = {
        "pass":    "قبول",
        "fail":    "رد",
        "partial": "جزئی",
        "":        "—",
    }

    _xl_header_style(ws, 1, len(headers), "تاریخچه بازرسی‌ها")
    _xl_col_header(ws, 4, headers)

    RESULT_COLORS = {
        "pass":    "E6F4EA",
        "fail":    "FCE8E6",
        "partial": "FFF8E1",
        "":        C_WHITE,
    }

    for i, ins in enumerate(inspections):
        result = ins.get("overall_result", "")
        _xl_data_row(ws, 5 + i, [
            ins.get("id", ""),
            ins.get("template_name", ""),
            ins.get("equipment_name", ""),
            ins.get("inspector_name", ""),
            STATUS_FA.get(ins.get("status", ""), ins.get("status", "")),
            RESULT_FA.get(result, result),
            ins.get("started_at", ""),
            ins.get("completed_at", "") or "—",
        ], zebra=(i % 2 == 1))

        bg = RESULT_COLORS.get(result, C_WHITE)
        for col in range(1, len(headers) + 1):
            ws.cell(row=5 + i, column=col).fill = \
                PatternFill("solid", fgColor=bg)

    _xl_auto_width(ws)
    wb.save(path)
    return path


def export_inspection_report_pdf(inspection: dict, path: str) -> str:
    """
    Export a completed inspection as a detailed PDF report.
    inspection: dict from InspectionService._inspection_to_dict()
                Must include 'template_obj' for checkpoint details.
    """
    doc   = SimpleDocTemplate(path, pagesize=A4,
                              leftMargin=1.5*cm, rightMargin=1.5*cm,
                              topMargin=1.5*cm, bottomMargin=1.5*cm)
    story = []
    st    = _pdf_styles()

    RESULT_FA = {
        "pass":    "✓ Pass / قبول",
        "fail":    "✗ Fail / رد",
        "partial": "~ Partial / جزئی",
        "na":      "N/A",
        "":        "—",
    }
    OVERALL_FA = {
        "pass":    "PASS — قبول",
        "fail":    "FAIL — رد",
        "partial": "PARTIAL — جزئی",
        "":        "In Progress",
    }

    overall = inspection.get("overall_result", "")
    _pdf_header(story, "Inspection Report",
                f"Inspection #{inspection.get('id', '')} — "
                f"{inspection.get('template_name', '')}")

    _pdf_section(story, "Inspection Summary — خلاصه بازرسی")
    _pdf_kv_table(story, [
        ("Inspection # / شناسه",    str(inspection.get("id", ""))),
        ("Template / قالب",         inspection.get("template_name", "")),
        ("Equipment / تجهیز",       inspection.get("equipment_name", "")),
        ("Inspector / بازرس",       inspection.get("inspector_name", "")),
        ("Status / وضعیت",          inspection.get("status", "")),
        ("Overall Result / نتیجه",  OVERALL_FA.get(overall, overall)),
        ("Started / شروع",          inspection.get("started_at", "")),
        ("Completed / پایان",       inspection.get("completed_at", "") or "—"),
    ])

    # Checkpoint results
    _pdf_section(story, "Checkpoint Results — نتایج چک‌پوینت‌ها")

    results_map = {r["checkpoint_id"]: r for r in inspection.get("results", [])}
    template_obj = inspection.get("template_obj")

    if template_obj and hasattr(template_obj, "checkpoints"):
        checkpoints = sorted(template_obj.checkpoints, key=lambda x: x.order_number)
        rows = []
        for cp in checkpoints:
            r          = results_map.get(cp.id, {})
            res_val    = r.get("result", "")
            res_text   = RESULT_FA.get(res_val, res_val)
            comment    = r.get("comment", "") or "—"
            rows.append([
                str(cp.order_number),
                cp.title,
                cp.checkpoint_type,
                res_text,
                comment,
            ])

        page_w = A4[0] - 3 * cm
        _pdf_data_table(
            story,
            ["#", "Checkpoint / چک‌پوینت", "Type / نوع",
             "Result / نتیجه", "Comment / توضیح"],
            rows,
            col_widths=[
                page_w * 0.05,
                page_w * 0.30,
                page_w * 0.12,
                page_w * 0.15,
                page_w * 0.38,
            ],
        )
    else:
        story.append(_para("No checkpoint data available.", st["body"]))
        story.append(Spacer(1, 8))

    if inspection.get("notes"):
        _pdf_section(story, "Notes / یادداشت")
        story.append(_para(inspection["notes"], st["body"]))
        story.append(Spacer(1, 8))

    _pdf_signature_row(story, ["Inspector / بازرس",
                                "Supervisor / سرپرست",
                                "Date / تاریخ"])
    doc.build(story)
    return path


def export_inspection_checklist_pdf(template: dict, path: str) -> str:
    """
    Export a blank inspection checklist form for field use.
    template: dict from InspectionService._template_to_dict()
    """
    doc   = SimpleDocTemplate(path, pagesize=A4,
                              leftMargin=1.5*cm, rightMargin=1.5*cm,
                              topMargin=1.5*cm, bottomMargin=1.5*cm)
    story = []
    st    = _pdf_styles()

    FREQ_FA = {
        "daily": "روزانه", "weekly": "هفتگی", "monthly": "ماهانه",
        "quarterly": "سه‌ماهه", "yearly": "سالانه",
    }

    _pdf_header(story, "Inspection Checklist Form",
                template.get("name", ""))

    _pdf_section(story, "Template Info — اطلاعات قالب")
    _pdf_kv_table(story, [
        ("Template / قالب",          template.get("name", "")),
        ("Equipment / تجهیز",        template.get("equipment_name", "عمومی")),
        ("Frequency / دوره",         FREQ_FA.get(template.get("frequency", ""), "")),
        ("Est. Duration / مدت",      f"{template.get('estimated_duration_minutes', 0)} min"),
        ("Inspector / بازرس",        "___________________________"),
        ("Date / تاریخ",             "___________________________"),
    ])

    _pdf_section(story, "Checkpoints — چک‌پوینت‌ها")

    checkpoints = template.get("checkpoints", [])
    if checkpoints:
        page_w = A4[0] - 3 * cm
        rows   = []
        for cp in checkpoints:
            rows.append([
                str(cp["order_number"]),
                cp["title"],
                cp.get("checkpoint_type", "visual"),
                cp.get("description", "") or "—",
                "☐ Pass    ☐ Fail    ☐ N/A",
                "",   # comment field
            ])

        _pdf_data_table(
            story,
            ["#", "Checkpoint / چک‌پوینت", "Type",
             "Description / توضیح", "Result / نتیجه", "Comment / نظر"],
            rows,
            col_widths=[
                page_w * 0.04,
                page_w * 0.22,
                page_w * 0.09,
                page_w * 0.25,
                page_w * 0.22,
                page_w * 0.18,
            ],
        )
    else:
        story.append(_para("No checkpoints defined.", st["body"]))
        story.append(Spacer(1, 8))

    _pdf_signature_row(story, ["Inspector / بازرس",
                                "Supervisor / سرپرست",
                                "Date / تاریخ"])
    doc.build(story)
    return path