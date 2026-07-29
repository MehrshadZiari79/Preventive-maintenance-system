# services/export_service.py
from datetime import datetime
import jdatetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

COMPANY_NAME = "شرکت گلا — آمل"

C_PRIMARY = "1A2A44"
C_RED     = "DC2626"
C_WHITE   = "FFFFFF"
C_LIGHT   = "F4F6F9"
C_DARK    = "202124"
C_WARNING = "D97706"
C_SUCCESS = "16A34A"

def _now_jalali() -> str:
    jd = jdatetime.datetime.now()
    return jd.strftime("%Y/%m/%d %H:%M")

def _to_jalali_str(dt, fmt="%Y/%m/%d"):
    if dt is None:
        return "—"
    if hasattr(dt, "strftime"):
        jdt = jdatetime.datetime.fromgregorian(datetime=dt)
        return jdt.strftime(fmt)
    return str(dt)

def _xl_header_style(ws, row: int, cols: int, title: str):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=cols)
    cell = ws.cell(row=row, column=1, value=COMPANY_NAME)
    cell.font = Font(bold=True, size=11, color=C_WHITE)
    cell.fill = PatternFill(start_color=C_PRIMARY, end_color=C_PRIMARY, fill_type="solid")
    cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row].height = 24

    ws.merge_cells(start_row=row+1, start_column=1, end_row=row+1, end_column=cols)
    cell2 = ws.cell(row=row+1, column=1, value=title)
    cell2.font = Font(bold=True, size=13, color=C_WHITE)
    cell2.fill = PatternFill(start_color=C_PRIMARY, end_color=C_PRIMARY, fill_type="solid")
    cell2.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row+1].height = 28

    ws.merge_cells(start_row=row+2, start_column=1, end_row=row+2, end_column=cols)
    cell3 = ws.cell(row=row+2, column=1, value=f"تاریخ تهیه: {_now_jalali()}")
    cell3.font = Font(size=9, color=C_DARK)
    cell3.fill = PatternFill(start_color=C_LIGHT, end_color=C_LIGHT, fill_type="solid")
    cell3.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row+2].height = 18

def _xl_col_header(ws, row: int, headers: list[str]):
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col, text in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = Font(bold=True, size=10, color=C_WHITE)
        cell.fill = PatternFill(start_color=C_PRIMARY, end_color=C_PRIMARY, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    ws.row_dimensions[row].height = 22

def _xl_data_row(ws, row: int, values: list, zebra: bool = False):
    thin = Side(style="thin", color="DDDDDD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    bg = C_LIGHT if zebra else C_WHITE
    for col, val in enumerate(values, 1):
        cell = ws.cell(row=row, column=col, value=val)
        cell.fill = PatternFill(start_color=bg, end_color=bg, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    ws.row_dimensions[row].height = 20

def _xl_auto_width(ws, min_w: int = 14, max_w: int = 55):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                lines = str(cell.value).split('\n')
                max_line = max((len(line) for line in lines), default=0)
                max_len = max(max_len, max_line)
        ws.column_dimensions[col_letter].width = max(min_w, min(max_len + 4, max_w))

# ── EQUIPMENT EXPORT ───────────────────────────────────────────────────
def export_equipment_excel(equipment_list: list[dict], path: str) -> str:
    wb = Workbook(); ws = wb.active; ws.title = "Equipment List"; ws.sheet_view.rightToLeft = True
    headers = [
        "کد", "نام تجهیز", "دسته‌بندی", "سازنده", "مدل",
        "موقعیت", "وضعیت", "تاریخ نصب", "آخرین بروزرسانی",
        "طول (متر)", "عرض (متر)", "قطر (متر)", "ارتفاع (متر)", "حجم (متر³)", "وزن (کیلوگرم)"
    ]
    _xl_header_style(ws, 1, len(headers), "لیست تجهیزات")
    _xl_col_header(ws, 4, headers)

    STATUS_FA = {"operational":"عملیاتی","maintenance":"در تعمیر","breakdown":"خراب","inactive":"غیرفعال"}
    for i, eq in enumerate(equipment_list):
        def flt(val):
            if val is None: return ""
            return f"{val:.2f}" if isinstance(val, float) else str(val)
        _xl_data_row(ws, 5+i, [
            eq.get("code",""), eq.get("name",""), eq.get("category",""),
            eq.get("manufacturer",""), eq.get("model",""), eq.get("location",""),
            STATUS_FA.get(eq.get("status",""), eq.get("status","")),
            _to_jalali_str(eq.get("installation_date")),
            _to_jalali_str(eq.get("updated_at"), fmt="%Y/%m/%d %H:%M"),
            flt(eq.get("length")), flt(eq.get("width")), flt(eq.get("diameter")),
            flt(eq.get("height")), flt(eq.get("volume")), flt(eq.get("weight"))
        ], zebra=(i%2==1))
    _xl_auto_width(ws)
    wb.save(path)
    return path

# ── PM SCHEDULES EXPORT ────────────────────────────────────────────────
def export_pm_excel(pm_list: list[dict], path: str) -> str:
    wb = Workbook(); ws = wb.active; ws.title = "PM Schedules"; ws.sheet_view.rightToLeft = True
    headers = ["شناسه", "عنوان برنامه", "تجهیز", "کد تجهیز", "تکنسین",
               "دوره تناوب", "بازه (روز)", "آخرین انجام", "سررسید بعدی", "روز مانده", "وضعیت"]
    _xl_header_style(ws, 1, len(headers), "برنامه‌های نگهداری پیشگیرانه PM")
    _xl_col_header(ws, 4, headers)

    FREQ_FA = {"daily":"روزانه","weekly":"هفتگی","monthly":"ماهانه","quarterly":"سه‌ماهه",
               "biannual":"شش‌ماهه","annual":"سالانه","custom":"سفارشی"}
    for i, pm in enumerate(pm_list):
        days = pm.get("days_until")
        overdue = pm.get("is_overdue", False)
        active = pm.get("is_active", True)
        if not active: status = "غیرفعال"
        elif overdue: status = "عقب‌افتاده"
        elif days is not None and 0 <= days <= 7: status = "این هفته"
        else: status = "به‌موقع"
        _xl_data_row(ws, 5+i, [
            pm.get("id",""), pm.get("title",""), pm.get("equipment_name",""),
            pm.get("equipment_code",""), pm.get("technician_name",""),
            FREQ_FA.get(pm.get("frequency",""), pm.get("frequency","")),
            pm.get("interval_days",""),
            _to_jalali_str(pm.get("last_done")),
            _to_jalali_str(pm.get("next_due")),
            str(days) if days is not None else "—", status
        ], zebra=(i%2==1))
        if overdue and active:
            for col in range(1, len(headers)+1):
                ws.cell(row=5+i, column=col).fill = PatternFill(start_color="FCE8E6", end_color="FCE8E6", fill_type="solid")
    _xl_auto_width(ws)
    wb.save(path)
    return path

# ── WORK ORDERS EXPORT (priority added, technicians column) ────────────
def export_work_orders_excel(work_orders: list, path: str) -> str:
    wb = Workbook(); ws = wb.active; ws.title = "Work Orders"; ws.sheet_view.rightToLeft = True
    headers = [
        "شناسه", "عنوان", "تجهیز", "نوع", "اولویت", "تکنسین(ها)",
        "اپراتور تحویل گیرنده", "ساعت اعلام خرابی", "وضعیت", "تاریخ برنامه",
        "شروع تعمیر", "پایان تعمیر", "ددلاین", "توضیحات اپراتور", "امضای اپراتور",
        "توضیحات تکنسین", "قطعات مصرفی", "هزینه دستی (ریال)", "توضیح هزینه"
    ]
    _xl_header_style(ws, 1, len(headers), "لیست دستور کارها")
    _xl_col_header(ws, 4, headers)

    TYPE_FA = {"PREVENTIVE":"پیشگیرانه","CORRECTIVE":"اصلاحی","EMERGENCY":"اضطراری","INSPECTION":"بازرسی","PM":"PM"}
    STATUS_FA = {"PENDING_APPROVAL":"در انتظار تأیید","PENDING":"در انتظار","IN_PROGRESS":"در حال انجام",
                 "FINISH_REQUESTED":"درخواست اتمام","APPROVED":"تایید شده","REJECTED":"رد شده"}
    STATUS_COLORS = {"PENDING_APPROVAL":"FFF8E1","PENDING":"E3F2FD","IN_PROGRESS":"FFF3E0",
                     "FINISH_REQUESTED":"FCE8E6","APPROVED":"E8F5E9","REJECTED":"FFEBEE"}
    PRIORITY_FA = {"low":"کم","medium":"متوسط","high":"بالا","urgent":"فوری"}

    for i, wo in enumerate(work_orders):
        eq_name = wo.equipment.name if wo.equipment else "—"
        tech_name = wo.technician.full_name if wo.technician else "—"
        additional = [t.full_name for t in wo.technicians if t.id != wo.technician_id]
        all_techs = [tech_name] + additional
        tech_display = ", ".join([n for n in all_techs if n and n != "—"]) or "—"
        operator_name = wo.operator.full_name if wo.operator else "—"
        status = wo.status.name

        _xl_data_row(ws, 5+i, [
            wo.id, wo.title, eq_name,
            TYPE_FA.get(wo.type.name, wo.type.name),
            PRIORITY_FA.get(wo.priority.name, wo.priority.name),
            tech_display,
            operator_name,
            _to_jalali_str(wo.failure_report_time, "%Y/%m/%d %H:%M") if wo.failure_report_time else "—",
            STATUS_FA.get(status, status),
            _to_jalali_str(wo.scheduled_date),
            _to_jalali_str(wo.start_time, "%Y/%m/%d %H:%M") if wo.start_time else "—",
            _to_jalali_str(wo.end_time, "%Y/%m/%d %H:%M") if wo.end_time else "—",
            _to_jalali_str(wo.deadline, "%Y/%m/%d %H:%M") if wo.deadline else "—",
            wo.operator_notes or "", wo.operator_signature or "",
            wo.description or "", wo.parts_used or "",
            f"{float(wo.manual_cost or 0):,.2f}", wo.cost_description or "—"
        ], zebra=(i%2==1))

        bg = STATUS_COLORS.get(status, C_WHITE)
        for col in range(1, len(headers)+1):
            ws.cell(row=5+i, column=col).fill = PatternFill(start_color=bg, end_color=bg, fill_type="solid")

    _xl_auto_width(ws)
    for col_idx, header in enumerate(headers, 1):
        if header in ("توضیحات اپراتور", "امضای اپراتور", "توضیحات تکنسین", "قطعات مصرفی", "توضیح هزینه"):
            ws.column_dimensions[get_column_letter(col_idx)].width = 40
    wb.save(path)
    return path

# ── INSPECTIONS EXPORT ─────────────────────────────────────────────────
def export_inspections_excel(inspections: list[dict], path: str) -> str:
    wb = Workbook(); ws = wb.active; ws.title = "Inspections"; ws.sheet_view.rightToLeft = True
    headers = ["شناسه", "قالب بازرسی", "تجهیز", "بازرس", "وضعیت", "نتیجه کلی", "تاریخ شروع", "تاریخ پایان"]
    _xl_header_style(ws, 1, len(headers), "تاریخچه بازرسی‌ها")
    _xl_col_header(ws, 4, headers)

    STATUS_FA = {"in_progress":"در حال انجام","completed":"تکمیل شده","cancelled":"لغو شده"}
    RESULT_FA = {"pass":"قبول","fail":"رد","partial":"جزئی","":"—"}
    RESULT_COLORS = {"pass":"E6F4EA","fail":"FCE8E6","partial":"FFF8E1","":C_WHITE}

    for i, ins in enumerate(inspections):
        result = ins.get("overall_result","")
        _xl_data_row(ws, 5+i, [
            ins.get("id",""),
            ins.get("template_name",""),
            ins.get("equipment_name",""),
            ins.get("inspector_name",""),
            STATUS_FA.get(ins.get("status",""), ins.get("status","")),
            RESULT_FA.get(result, result),
            _to_jalali_str(ins.get("started_at"), "%Y/%m/%d %H:%M"),
            _to_jalali_str(ins.get("completed_at"), "%Y/%m/%d %H:%M") if ins.get("completed_at") else "—"
        ], zebra=(i%2==1))
        bg = RESULT_COLORS.get(result, C_WHITE)
        for col in range(1, len(headers)+1):
            ws.cell(row=5+i, column=col).fill = PatternFill(start_color=bg, end_color=bg, fill_type="solid")
    _xl_auto_width(ws)
    wb.save(path)
    return path

# ── SPARE PARTS EXPORT ─────────────────────────────────────────────────
def export_spare_parts_excel(parts_list: list, path: str) -> str:
    wb = Workbook(); ws = wb.active; ws.title = "Spare Parts"; ws.sheet_view.rightToLeft = True
    headers = ["شناسه", "شماره قطعه", "نام قطعه", "دسته‌بندی", "موجودی فعلی", "حداقل موجودی",
               "واحد", "قیمت واحد", "موقعیت", "تامین‌کننده", "توضیحات"]
    _xl_header_style(ws, 1, len(headers), "لیست قطعات یدکی")
    _xl_col_header(ws, 4, headers)

    for i, part in enumerate(parts_list):
        _xl_data_row(ws, 5+i, [
            part.id, part.part_number, part.name, part.category or "",
            part.current_stock, part.min_stock, part.unit or "",
            f"{part.unit_price:.2f}", part.location or "",
            part.supplier or "", part.description or ""
        ], zebra=(i%2==1))
    _xl_auto_width(ws)
    wb.save(path)
    return path