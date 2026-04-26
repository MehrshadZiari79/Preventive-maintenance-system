# services/export_service.py (only Excel exports)
"""
Export Service — Excel generation.
Libraries: openpyxl (Excel)
"""
import os
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

COMPANY_NAME = "شرکت گلا — آمل"
APP_NAME = "سیستم مدیریت نگهداری پیشگیرانه"

C_PRIMARY = "1A73E8"
C_SUCCESS = "34A853"
C_WARNING = "F29900"
C_DANGER = "EA4335"
C_LIGHT = "E8F0FE"
C_SUBTLE = "5F6368"
C_WHITE = "FFFFFF"
C_DARK = "202124"

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def _xl_header_style(ws, row: int, cols: int, title: str):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=cols)
    cell = ws.cell(row=row, column=1, value=COMPANY_NAME)
    cell.font = Font(bold=True, size=11, color=C_WHITE)
    cell.fill = PatternFill("solid", fgColor=C_PRIMARY)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row].height = 24

    ws.merge_cells(start_row=row+1, start_column=1, end_row=row+1, end_column=cols)
    cell2 = ws.cell(row=row+1, column=1, value=title)
    cell2.font = Font(bold=True, size=13, color=C_WHITE)
    cell2.fill = PatternFill("solid", fgColor=C_PRIMARY)
    cell2.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row+1].height = 28

    ws.merge_cells(start_row=row+2, start_column=1, end_row=row+2, end_column=cols)
    cell3 = ws.cell(row=row+2, column=1, value=f"تاریخ تهیه: {_now_str()}")
    cell3.font = Font(size=9, color=C_SUBTLE)
    cell3.fill = PatternFill("solid", fgColor=C_LIGHT)
    cell3.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row+2].height = 18

def _xl_col_header(ws, row: int, headers: list[str]):
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col, text in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = Font(bold=True, size=10, color=C_WHITE)
        cell.fill = PatternFill("solid", fgColor="2C3E50")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    ws.row_dimensions[row].height = 22

def _xl_data_row(ws, row: int, values: list, zebra: bool = False):
    thin = Side(style="thin", color="DDDDDD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    bg = "F5F7FA" if zebra else C_WHITE
    for col, val in enumerate(values, 1):
        cell = ws.cell(row=row, column=col, value=val)
        cell.fill = PatternFill("solid", fgColor=bg)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
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

# ==================== EQUIPMENT ====================
def export_equipment_excel(equipment_list: list[dict], path: str) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Equipment List"
    ws.sheet_view.rightToLeft = True

    headers = ["کد", "نام تجهیز", "دسته‌بندی", "سازنده", "مدل",
               "موقعیت", "وضعیت", "سطح اهمیت", "تاریخ نصب", "آخرین بروزرسانی"]
    _xl_header_style(ws, 1, len(headers), "لیست تجهیزات")
    _xl_col_header(ws, 4, headers)

    STATUS_FA = {"operational": "عملیاتی", "maintenance": "در تعمیر", "breakdown": "خراب", "inactive": "غیرفعال"}
    for i, eq in enumerate(equipment_list):
        _xl_data_row(ws, 5+i, [
            eq.get("code", ""), eq.get("name", ""), eq.get("category", ""),
            eq.get("manufacturer", ""), eq.get("model", ""), eq.get("location", ""),
            STATUS_FA.get(eq.get("status", ""), eq.get("status", "")),
            eq.get("criticality_level", ""), eq.get("installation_date", ""), eq.get("updated_at", "")
        ], zebra=(i % 2 == 1))
    _xl_auto_width(ws)
    wb.save(path)
    return path

# ==================== PM SCHEDULES ====================
def export_pm_excel(pm_list: list[dict], path: str) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "PM Schedules"
    ws.sheet_view.rightToLeft = True

    headers = ["شناسه", "عنوان برنامه", "تجهیز", "کد تجهیز", "تکنسین",
               "دوره تناوب", "بازه (روز)", "آخرین انجام", "سررسید بعدی", "روز مانده", "وضعیت"]
    _xl_header_style(ws, 1, len(headers), "برنامه‌های نگهداری پیشگیرانه PM")
    _xl_col_header(ws, 4, headers)

    FREQ_FA = {"daily": "روزانه", "weekly": "هفتگی", "monthly": "ماهانه", "quarterly": "سه‌ماهه",
               "biannual": "شش‌ماهه", "annual": "سالانه", "custom": "سفارشی"}
    for i, pm in enumerate(pm_list):
        days = pm.get("days_until")
        overdue = pm.get("is_overdue", False)
        active = pm.get("is_active", True)
        if not active: status = "غیرفعال"
        elif overdue: status = "عقب‌افتاده"
        elif days is not None and 0 <= days <= 7: status = "این هفته"
        else: status = "به‌موقع"
        _xl_data_row(ws, 5+i, [
            pm.get("id", ""), pm.get("title", ""), pm.get("equipment_name", ""),
            pm.get("equipment_code", ""), pm.get("technician_name", ""),
            FREQ_FA.get(pm.get("frequency", ""), pm.get("frequency", "")),
            pm.get("interval_days", ""), pm.get("last_done", ""), pm.get("next_due", ""),
            str(days) if days is not None else "—", status
        ], zebra=(i % 2 == 1))
        if overdue and active:
            for col in range(1, len(headers)+1):
                ws.cell(row=5+i, column=col).fill = PatternFill("solid", fgColor="FCE8E6")
    _xl_auto_width(ws)
    wb.save(path)
    return path

# ==================== WORK ORDERS ====================
def export_work_orders_excel(work_orders: list, path: str) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Work Orders"
    ws.sheet_view.rightToLeft = True

    headers = [
        "شناسه", "عنوان", "تجهیز", "نوع", "اولویت", "تکنسین",
        "اپراتور تحویل گیرنده", "ساعت اعلام خرابی", "وضعیت", "تاریخ برنامه",
        "شروع تعمیر", "پایان تعمیر", "توضیحات اپراتور", "امضای اپراتور",
        "توضیحات تکنسین", "قطعات مصرفی", "هزینه دستی (ریال)", "توضیح هزینه"
    ]
    _xl_header_style(ws, 1, len(headers), "لیست دستور کارها")
    _xl_col_header(ws, 4, headers)

    TYPE_FA = {"PREVENTIVE": "پیشگیرانه", "CORRECTIVE": "اصلاحی", "EMERGENCY": "اضطراری",
               "INSPECTION": "بازرسی", "PM": "PM"}
    PRIORITY_FA = {"LOW": "کم", "MEDIUM": "متوسط", "HIGH": "زیاد", "URGENT": "فوری"}
    STATUS_FA = {"PENDING": "در انتظار", "IN_PROGRESS": "در حال انجام", "COMPLETED": "تکمیل شده",
                 "APPROVED": "تایید شده", "REJECTED": "رد شده"}
    STATUS_COLORS = {"PENDING": "FFF8E1", "IN_PROGRESS": "E3F2FD", "COMPLETED": "E6F4EA",
                     "APPROVED": "E6F4EA", "REJECTED": "FCE8E6"}

    for i, wo in enumerate(work_orders):
        eq_name = wo.equipment.name if wo.equipment else "—"
        tech_name = wo.technician.full_name if wo.technician else "—"
        operator_name = wo.operator.full_name if wo.operator else "—"
        failure_time = wo.failure_report_time.strftime("%Y-%m-%d %H:%M") if wo.failure_report_time else "—"
        status = wo.status.name
        scheduled = wo.scheduled_date.strftime("%Y-%m-%d") if wo.scheduled_date else "—"
        start = wo.start_time.strftime("%Y-%m-%d %H:%M") if wo.start_time else "—"
        end = wo.end_time.strftime("%Y-%m-%d %H:%M") if wo.end_time else "—"

        manual_cost_val = float(wo.manual_cost) if wo.manual_cost else 0.0
        manual_cost_str = f"{manual_cost_val:,.2f}"
        cost_desc = wo.cost_description or "—"

        _xl_data_row(ws, 5+i, [
            wo.id, wo.title, eq_name, TYPE_FA.get(wo.type.name, wo.type.name),
            PRIORITY_FA.get(wo.priority.name, wo.priority.name), tech_name, operator_name,
            failure_time, STATUS_FA.get(status, status), scheduled, start, end,
            wo.operator_notes or "", wo.operator_signature or "", wo.description or "",
            wo.parts_used or "", manual_cost_str, cost_desc
        ], zebra=(i % 2 == 1))

        bg = STATUS_COLORS.get(status, C_WHITE)
        for col in range(1, len(headers)+1):
            ws.cell(row=5+i, column=col).fill = PatternFill("solid", fgColor=bg)

    _xl_auto_width(ws)
    wb.save(path)
    return path

# ==================== INSPECTIONS ====================
def export_inspections_excel(inspections: list[dict], path: str) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Inspections"
    ws.sheet_view.rightToLeft = True

    headers = ["شناسه", "قالب بازرسی", "تجهیز", "بازرس", "وضعیت", "نتیجه کلی", "تاریخ شروع", "تاریخ پایان"]
    _xl_header_style(ws, 1, len(headers), "تاریخچه بازرسی‌ها")
    _xl_col_header(ws, 4, headers)

    STATUS_FA = {"in_progress": "در حال انجام", "completed": "تکمیل شده", "cancelled": "لغو شده"}
    RESULT_FA = {"pass": "قبول", "fail": "رد", "partial": "جزئی", "": "—"}
    RESULT_COLORS = {"pass": "E6F4EA", "fail": "FCE8E6", "partial": "FFF8E1", "": C_WHITE}

    for i, ins in enumerate(inspections):
        result = ins.get("overall_result", "")
        _xl_data_row(ws, 5+i, [
            ins.get("id", ""), ins.get("template_name", ""), ins.get("equipment_name", ""),
            ins.get("inspector_name", ""), STATUS_FA.get(ins.get("status", ""), ins.get("status", "")),
            RESULT_FA.get(result, result), ins.get("started_at", ""), ins.get("completed_at", "") or "—"
        ], zebra=(i % 2 == 1))
        bg = RESULT_COLORS.get(result, C_WHITE)
        for col in range(1, len(headers)+1):
            ws.cell(row=5+i, column=col).fill = PatternFill("solid", fgColor=bg)
    _xl_auto_width(ws)
    wb.save(path)
    return path

# ==================== SPARE PARTS ====================
def export_spare_parts_excel(parts_list: list, path: str) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Spare Parts"
    ws.sheet_view.rightToLeft = True

    headers = ["شناسه", "شماره قطعه", "نام قطعه", "دسته‌بندی", "موجودی فعلی", "حداقل موجودی",
               "واحد", "قیمت واحد", "موقعیت", "تامین‌کننده", "توضیحات"]
    _xl_header_style(ws, 1, len(headers), "لیست قطعات یدکی")
    _xl_col_header(ws, 4, headers)

    for i, part in enumerate(parts_list):
        _xl_data_row(ws, 5+i, [
            part.id, part.part_number, part.name, part.category or "", part.current_stock,
            part.min_stock, part.unit or "", f"{part.unit_price:.2f}", part.location or "",
            part.supplier or "", part.description or ""
        ], zebra=(i % 2 == 1))
    _xl_auto_width(ws)
    wb.save(path)
    return path