# views/detailed_report_tabs.py
from __future__ import annotations

import threading
from collections import defaultdict
from datetime import datetime
from typing import Any

import tkinter as tk
from views.ui_kit import rtl_columns  # RTL (right-to-left) table columns
from tkinter import ttk, messagebox, filedialog

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter

from sqlalchemy.orm import joinedload, subqueryload

from database.db import SessionLocal
from database.work_order_repository import WorkOrderRepository
from database.repair_request_repository import RepairRequestRepository
from database.models import (
    Department,
    Equipment,
    RepairRequestDocument,
    RepairRequestCompletion,
    Personnel,
)
from database.work_order import WorkOrder

from services.export_service import (
    export_work_orders_excel,
    export_repair_requests_excel,
)
from services.pdf_service import (
    export_work_orders_pdf,
    export_repair_requests_pdf,
)

from utils.date_helpers import to_jalali_date_str, to_jalali_datetime_str

from utils.date_helpers import jalali_stamp  # Jalali file names / stamps
from utils.theme import (
    NAVY,
    NAVY_LIGHT,
    WHITE,
    GRAY_BG,
    TEXT_DARK,
    TEXT_LIGHT,
    SUCCESS,
    WARNING,
    RED,
    FONT_HEADING,
    FONT_NORMAL,
    FONT_SMALL,
)
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock

# Re-use the visual language from reports_view.py.
CARD_BG = "#FFFFFF"
CARD_BORDER = "#E8ECF0"
SECTION_BG = "#F4F6F9"
FONT_SUBHEADING = ("Tahoma", 11, "bold")


# -----------------------------------------------------------------------------
# Translation maps
# -----------------------------------------------------------------------------
WO_TYPE_FA = {
    "PREVENTIVE": "پیشگیرانه",
    "CORRECTIVE": "اصلاحی",
    "EMERGENCY": "اضطراری",
    "INSPECTION": "بازرسی",
    "PM": "PM",
}

WO_STATUS_FA = {
    "PENDING_APPROVAL": "در انتظار تأیید",
    "PENDING": "در انتظار",
    "IN_PROGRESS": "در حال انجام",
    "FINISH_REQUESTED": "درخواست اتمام",
    "COMPLETED": "تکمیل شده",
    "APPROVED": "تأیید شده",
    "REJECTED": "رد شده",
}

WO_PRIORITY_FA = {
    "LOW": "کم",
    "MEDIUM": "متوسط",
    "HIGH": "بالا",
    "URGENT": "فوری",
}

WO_TYPE_REVERSE = {v: k for k, v in WO_TYPE_FA.items()}
WO_STATUS_REVERSE = {v: k for k, v in WO_STATUS_FA.items()}
WO_PRIORITY_REVERSE = {v: k for k, v in WO_PRIORITY_FA.items()}

WO_COMPLETED_STATUSES = {"APPROVED", "COMPLETED"}
WO_ACTIVE_STATUSES = {"IN_PROGRESS", "FINISH_REQUESTED"}
WO_PENDING_STATUSES = {"PENDING", "PENDING_APPROVAL"}


# -----------------------------------------------------------------------------
# Output wait dialog
# -----------------------------------------------------------------------------
class _OutputWaitDialog(tk.Toplevel):
    """Modal Persian wait dialog shown while Excel/PDF is being generated."""

    def __init__(self, parent, output_title: str):
        super().__init__(parent)
        self.title("لطفاً صبر کنید")
        self.configure(bg=CARD_BG)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        width = 430
        height = 190
        try:
            parent.update_idletasks()
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
        except Exception:
            x = 100
            y = 100

        self.geometry(f"{width}x{height}+{x}+{y}")

        body = tk.Frame(self, bg=CARD_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        tk.Label(
            body,
            text="لطفاً صبر کنید",
            font=FONT_HEADING,
            bg=CARD_BG,
            fg=NAVY,
            anchor="e",
        ).pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            body,
            text=f"در حال تهیه {output_title} هستیم...",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
            anchor="e",
        ).pack(fill=tk.X)

        tk.Label(
            body,
            text="این عملیات ممکن است کمی زمان ببرد. لطفاً تا پایان عملیات صبر کنید.",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            anchor="e",
            justify="right",
            wraplength=380,
        ).pack(fill=tk.X, pady=(5, 12))

        self.progress = ttk.Progressbar(
            body,
            mode="indeterminate",
            length=360,
        )
        self.progress.pack(fill=tk.X, pady=(0, 4))
        self.progress.start(12)
        self.grab_set()
        self.update_idletasks()
        self.update()

    def close(self):
        try:
            self.progress.stop()
        except Exception:
            pass
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


def _run_output_in_background(owner, output_title: str, worker, on_success, on_error):
    """Run a heavy Excel/PDF export outside Tk's main thread.

    ``owner`` is a report-tab controller object, not a Tkinter widget.
    The actual Tk widget is stored in ``owner._frame``.
    """
    if getattr(owner, "_output_running", False):
        return

    owner._output_running = True

    # Report tabs are controller objects, not Tkinter widgets.
    # Always resolve the real frame before calling Tk methods such as
    # ``winfo_toplevel`` and ``after``.
    widget_owner = getattr(owner, "_frame", owner)
    parent = widget_owner.winfo_toplevel()
    wait_dialog = _OutputWaitDialog(parent, output_title)

    def _worker():
        error = None
        try:
            worker()
        except Exception as exc:
            error = exc

        def _finish():
            owner._output_running = False
            wait_dialog.close()
            if error is None:
                on_success()
            else:
                on_error(error)

        try:
            widget_owner.after(0, _finish)
        except Exception:
            try:
                wait_dialog.close()
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _jdate(value: Any, with_time: bool = False) -> str:
    if value is None:
        return "—"
    try:
        if with_time:
            return to_jalali_datetime_str(value) or "—"
        return to_jalali_date_str(value) or "—"
    except Exception:
        return str(value)


def _safe(value: Any, default: str = "—") -> str:
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def _enum_name(value: Any) -> str:
    if value is None:
        return ""
    name = getattr(value, "name", None) or getattr(value, "value", None) or str(value)
    return str(name).upper()


def _enum_fa(value: Any, mapping: dict[str, str]) -> str:
    name = _enum_name(value)
    return mapping.get(name, name or "—")


def _personnel_names(people) -> str:
    try:
        names = [getattr(p, "full_name", "") or "" for p in (people or [])]
        return "، ".join(n for n in names if n) or "—"
    except Exception:
        return "—"


def _money(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _pct(part: int | float, total: int | float) -> str:
    if not total:
        return "۰٪"
    return f"{(float(part) / float(total) * 100):.1f}٪"


def _month_key(value: Any):
    if value is None:
        return None
    if isinstance(value, datetime):
        return (value.year, value.month)
    if hasattr(value, "year") and hasattr(value, "month"):
        return (value.year, value.month)
    return None


def _month_label(key) -> str:
    if not key:
        return "—"
    try:
        return to_jalali_date_str(datetime(key[0], key[1], 1))[:7]
    except Exception:
        return f"{key[0]:04d}/{key[1]:02d}"


def _clear_frame(frame: tk.Frame) -> None:
    for child in frame.winfo_children():
        child.destroy()


class _ReportSearchCombobox(ttk.Combobox):
    """Searchable combobox for report filters.

    Unlike a read-only ttk.Combobox, users can type a partial Persian or
    Latin equipment name and the list narrows immediately. The typed value is
    still required to match one of the known values when the user applies the
    filter.
    """

    _NAV_KEYS = {
        "Up", "Down", "Left", "Right", "Home", "End",
        "Prior", "Next", "Return", "Escape", "Tab",
        "Shift_L", "Shift_R", "Control_L", "Control_R",
        "Alt_L", "Alt_R", "Caps_Lock",
    }

    def __init__(self, parent, textvariable=None, **kwargs):
        kwargs.setdefault("state", "normal")
        super().__init__(parent, textvariable=textvariable, **kwargs)
        self._all_values: list[str] = []
        self._filtered_values: list[str] = []
        self.bind("<KeyRelease>", self._on_key_release, add="+")
        self.bind("<Button-1>", self._on_click, add="+")
        self.bind("<FocusIn>", self._on_focus_in, add="+")
        self.bind("<Escape>", self._on_escape, add="+")

    def set_values(self, values):
        unique = []
        seen = set()
        for value in values or []:
            text = str(value or "").strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique.append(text)
        self._all_values = unique
        self._filtered_values = list(unique)
        self.configure(values=self._filtered_values)

    def _filter(self, query: str):
        query = (query or "").strip().casefold()
        if not query:
            return list(self._all_values)
        parts = [part for part in query.split() if part]
        return [
            value
            for value in self._all_values
            if all(part in value.casefold() for part in parts)
        ]

    def _apply_filter(self):
        current = self.get().strip()
        values = self._filter(current)
        self._filtered_values = values
        self.configure(values=values)

    def _on_key_release(self, event):
        if event.keysym in self._NAV_KEYS:
            return
        self._apply_filter()

    def _on_click(self, _event):
        self.after_idle(self._apply_filter)

    def _on_focus_in(self, _event):
        self.after_idle(self._apply_filter)

    def _on_escape(self, _event):
        self.set("")
        self._apply_filter()
        return "break"


# -----------------------------------------------------------------------------
# Detailed Excel export
# -----------------------------------------------------------------------------

def _excel_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    return text if text else default


def _excel_dt(value: Any) -> str:
    if value is None:
        return ""
    try:
        return to_jalali_datetime_str(value) or ""
    except Exception:
        return str(value)


def _excel_money(value: Any):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _excel_personnel_text(people) -> str:
    """Return Personnel text without triggering lazy loads on detached ORM objects."""
    result = []
    for person in list(people or []):
        code = _excel_text(getattr(person, "personnel_code", ""))
        name = _excel_text(getattr(person, "full_name", ""))

        department_name = ""
        try:
            department = getattr(person, "department", None)
            department_name = _excel_text(getattr(department, "name", ""))
        except Exception:
            # The report loaders eagerly load Personnel.department.  This
            # fallback is deliberately defensive so an old/detached object
            # can never crash the report; code/name remain useful.
            department_name = ""

        parts = [p for p in (code, name, department_name) if p]
        if parts:
            result.append(" - ".join(parts))
    return "، ".join(result)


def _excel_user_name(user) -> str:
    if user is None:
        return ""
    return _excel_text(
        getattr(user, "full_name", None)
        or getattr(user, "username", None)
    )


def _work_order_detail_row(wo: WorkOrder) -> list[Any]:
    equipment = getattr(wo, "equipment", None)
    department = getattr(wo, "department", None)
    schedule = getattr(wo, "schedule", None)
    completers = getattr(wo, "completers", None) or []

    start = getattr(wo, "start_time", None)
    end = getattr(wo, "end_time", None)
    duration_hours = ""
    if start and end:
        try:
            seconds = (end - start).total_seconds()
            if seconds >= 0:
                duration_hours = round(seconds / 3600.0, 2)
        except Exception:
            duration_hours = ""

    return [
        getattr(wo, "id", ""),
        _excel_text(getattr(wo, "title", "")),
        _excel_text(getattr(equipment, "code", "")),
        _excel_text(getattr(equipment, "name", "")),
        _excel_text(getattr(department, "name", "")),
        _enum_fa(getattr(wo, "type", None), WO_TYPE_FA),
        _enum_fa(getattr(wo, "status", None), WO_STATUS_FA),
        _enum_fa(getattr(wo, "priority", None), WO_PRIORITY_FA),
        getattr(wo, "equipment_id", ""),
        getattr(wo, "department_id", ""),
        getattr(wo, "schedule_id", ""),
        _excel_text(getattr(schedule, "title", "")),
        getattr(wo, "parent_work_order_id", ""),
        getattr(wo, "root_parent_id", ""),
        _excel_user_name(getattr(wo, "technician", None)),
        _excel_user_name(getattr(wo, "supervisor", None)),
        _excel_user_name(getattr(wo, "operator", None)),
        _excel_text(getattr(wo, "emergency_reported_by", "")),
        _excel_personnel_text(completers),
        _excel_dt(getattr(wo, "failure_report_time", None)),
        _excel_dt(getattr(wo, "scheduled_date", None)),
        _excel_dt(getattr(wo, "deadline", None)),
        _excel_dt(start),
        _excel_dt(end),
        duration_hours,
        getattr(wo, "delay_minutes", "") if getattr(wo, "delay_minutes", None) is not None else "",
        _excel_text(getattr(wo, "delay_reason", "")),
        _excel_money(getattr(wo, "manual_cost", 0)),
        _excel_text(getattr(wo, "cost_description", "")),
        _excel_text(getattr(wo, "description", "")),
        _excel_text(getattr(wo, "parts_used", "")),
        _excel_text(getattr(wo, "operator_notes", "")),
        _excel_text(getattr(wo, "operator_signature", "")),
        _excel_text(getattr(wo, "supervisor_notes", "")),
        _excel_text(getattr(wo, "attachments", "")),
        _excel_dt(getattr(wo, "created_at", None)),
        _excel_dt(getattr(wo, "updated_at", None)),
    ]


WORK_ORDER_DETAIL_HEADERS = [
    "شناسه دستورکار", "عنوان دستورکار", "کد تجهیز", "نام تجهیز",
    "دپارتمان", "نوع فعالیت", "وضعیت", "اولویت", "شناسه تجهیز",
    "شناسه دپارتمان", "شناسه برنامه PM", "عنوان برنامه PM",
    "دستورکار والد", "دستورکار ریشه", "کاربر تکنسین (قدیمی)",
    "سرپرست (کاربر)", "اپراتور (کاربر)", "گزارش‌دهنده اضطراری",
    "پرسنل انجام‌دهنده", "زمان اعلام خرابی", "زمان برنامه‌ریزی",
    "مهلت", "شروع کار", "پایان کار", "مدت انجام (ساعت)",
    "تاخیر (دقیقه)", "علت تاخیر", "هزینه دستی (ریال)",
    "شرح هزینه", "شرح دستورکار", "قطعات مصرفی", "یادداشت اپراتور",
    "امضای اپراتور", "یادداشت سرپرست", "پیوست‌ها", "تاریخ ایجاد",
    "آخرین ویرایش",
]


def _repair_request_detail_row(rr: RepairRequestDocument) -> list[Any]:
    completion = getattr(rr, "completion", None)
    department = getattr(rr, "department", None)
    assigned = getattr(rr, "assigned_personnel", None)
    completion_people = getattr(completion, "personnel", None) if completion else None
    created_by = getattr(rr, "created_by", None)

    return [
        getattr(rr, "id", ""),
        _excel_text(getattr(rr, "requesting_unit", "")),
        _excel_text(getattr(department, "name", "")),
        _excel_text(getattr(rr, "equipment_name", "")),
        _excel_dt(getattr(rr, "breakdown_datetime", None)),
        _excel_text(getattr(rr, "operator_name", "")),
        _excel_text(getattr(rr, "requester_name", "")),
        _excel_text(getattr(rr, "request_description", "")),
        _excel_personnel_text([assigned] if assigned else []),
        "انجام شده" if completion else "در انتظار انجام",
        _excel_personnel_text(completion_people),
        _excel_dt(getattr(completion, "completion_datetime", None)) if completion else "",
        _excel_text(getattr(completion, "finish_notes", "")) if completion else "",
        _excel_money(getattr(completion, "manual_cost", 0)) if completion else 0.0,
        _excel_text(getattr(completion, "cost_description", "")) if completion else "",
        getattr(completion, "delay_minutes", "") if completion and getattr(completion, "delay_minutes", None) is not None else "",
        _excel_text(getattr(completion, "delay_reason", "")) if completion else "",
        _excel_user_name(created_by),
        _excel_dt(getattr(rr, "created_at", None)),
        _excel_dt(getattr(rr, "updated_at", None)),
    ]


REPAIR_REQUEST_DETAIL_HEADERS = [
    "شناسه درخواست", "واحد متقاضی", "دپارتمان انجام‌دهنده",
    "نام دستگاه/وسیله", "زمان اعلام خرابی", "اپراتور (قدیمی)",
    "نام درخواست‌دهنده", "شرح درخواست", "پرسنل مسئول قدیمی",
    "وضعیت", "پرسنل انجام‌دهنده", "تاریخ و ساعت اتمام",
    "گزارش انجام کار", "هزینه دستی (ریال)", "شرح هزینه",
    "تاخیر (دقیقه)", "علت تاخیر", "ثبت‌کننده درخواست",
    "تاریخ ایجاد", "آخرین ویرایش",
]


def _excel_fill(color: str):
    return PatternFill(fill_type="solid", fgColor=color)


def _excel_border(color="D5DCE5", style="thin"):
    side = Side(style=style, color=color)
    return Border(left=side, right=side, top=side, bottom=side)


def _excel_section_header(ws, row: int, start_col: int, end_col: int, title: str):
    start = get_column_letter(start_col)
    end = get_column_letter(end_col)
    ws.merge_cells(f"{start}{row}:{end}{row}")
    cell = ws.cell(row=row, column=start_col, value=title)
    cell.fill = _excel_fill("17365D")
    cell.font = Font(name="Tahoma", size=11, bold=True, color="FFFFFF")
    cell.alignment = Alignment(horizontal="right", vertical="center")
    cell.border = _excel_border("17365D", "medium")
    ws.row_dimensions[row].height = 24


def _excel_kpi_card(ws, row: int, start_col: int, end_col: int, title: str, value, subtitle: str = ""):
    start = get_column_letter(start_col)
    end = get_column_letter(end_col)
    ws.merge_cells(f"{start}{row}:{end}{row}")
    ws.merge_cells(f"{start}{row+1}:{end}{row+1}")
    ws.merge_cells(f"{start}{row+2}:{end}{row+2}")

    c1 = ws.cell(row=row, column=start_col, value=title)
    c2 = ws.cell(row=row+1, column=start_col, value=value)
    c3 = ws.cell(row=row+2, column=start_col, value=subtitle or "")

    for cell in (c1, c2, c3):
        cell.fill = _excel_fill("F4F7FA")
        cell.border = _excel_border("D7DEE7")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    c1.font = Font(name="Tahoma", size=9, bold=True, color="64748B")
    c2.font = Font(name="Tahoma", size=14, bold=True, color="17365D")
    c3.font = Font(name="Tahoma", size=8, color="64748B")

    ws.row_dimensions[row].height = 20
    ws.row_dimensions[row+1].height = 27
    ws.row_dimensions[row+2].height = 20


def _excel_summary_table(ws, start_row: int, start_col: int, headers, rows, title: str):
    if not headers:
        return start_row

    end_col = start_col + len(headers) - 1
    _excel_section_header(ws, start_row, start_col, end_col, title)
    header_row = start_row + 1

    for offset, header in enumerate(headers):
        cell = ws.cell(header_row, start_col + offset, header)
        cell.fill = _excel_fill("DCE6F1")
        cell.font = Font(name="Tahoma", size=9, bold=True, color="17365D")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _excel_border()
    ws.row_dimensions[header_row].height = 28

    body_start = header_row + 1
    for ridx, data_row in enumerate(rows):
        excel_row = body_start + ridx
        for cidx, value in enumerate(data_row):
            cell = ws.cell(excel_row, start_col + cidx, value)
            cell.fill = _excel_fill("FFFFFF" if ridx % 2 == 0 else "F8FAFC")
            cell.font = Font(name="Tahoma", size=9, color="1F2937")
            cell.alignment = Alignment(
                horizontal="right" if isinstance(value, str) else "center",
                vertical="center",
                wrap_text=True,
            )
            cell.border = _excel_border()
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cell.number_format = "#,##0.00" if isinstance(value, float) and not float(value).is_integer() else "#,##0"
        ws.row_dimensions[excel_row].height = 22

    return body_start + len(rows)


def _excel_summary_work_orders(ws, source_records, start_row: int) -> int:
    records = list(source_records or [])
    total = len(records)
    completed = sum(_enum_name(getattr(x, "status", None)) in WO_COMPLETED_STATUSES for x in records)
    active = sum(_enum_name(getattr(x, "status", None)) in WO_ACTIVE_STATUSES for x in records)
    pending = sum(_enum_name(getattr(x, "status", None)) in WO_PENDING_STATUSES for x in records)
    rejected = sum(_enum_name(getattr(x, "status", None)) == "REJECTED" for x in records)
    em_count = sum(_enum_name(getattr(x, "type", None)) in {"EMERGENCY", "EM"} for x in records)
    pm_count = sum(_enum_name(getattr(x, "type", None)) in {"PREVENTIVE", "PM"} for x in records)
    high_priority = sum(_enum_name(getattr(x, "priority", None)) in {"HIGH", "URGENT"} for x in records)
    total_cost = sum(_money(getattr(x, "manual_cost", 0)) for x in records)
    total_delay = sum(_money(getattr(x, "delay_minutes", 0)) for x in records)

    durations = []
    for wo in records:
        start = getattr(wo, "start_time", None)
        end = getattr(wo, "end_time", None)
        if start and end:
            try:
                hours = (end - start).total_seconds() / 3600.0
                if 0 <= hours <= 24 * 365:
                    durations.append(hours)
            except Exception:
                pass
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    last_summary_col = len(WORK_ORDER_DETAIL_HEADERS)
    _excel_section_header(ws, start_row, 1, last_summary_col, "خلاصه مدیریتی گزارش دستورکارها")
    kpi_row = start_row + 1
    card_width = 6
    kpis = [
        ("کل دستورکارها", f"{total:,}", "رکورد منطبق با فیلتر"),
        ("تکمیل‌شده", f"{completed:,}", f"نرخ تکمیل: {_pct(completed, total)}"),
        ("در حال انجام", f"{active:,}", "در حال اجرا / درخواست اتمام"),
        ("در انتظار", f"{pending:,}", "در انتظار تأیید یا شروع"),
        ("اضطراری (EM)", f"{em_count:,}", "تعداد دستورکار اضطراری"),
        ("هزینه کل", f"{total_cost:,.0f}", "ریال"),
    ]
    for i, (title, value, sub) in enumerate(kpis):
        s_col = 1 + i * card_width
        _excel_kpi_card(ws, kpi_row, s_col, s_col + card_width - 1, title, value, sub)

    meta_row = kpi_row + 4
    ws.merge_cells(start_row=meta_row, start_column=1, end_row=meta_row, end_column=last_summary_col)
    meta = ws.cell(
        meta_row,
        1,
        f"PM: {pm_count:,} | اولویت بالا/فوری: {high_priority:,} | ردشده: {rejected:,} | تاخیر ثبت‌شده: {total_delay:,.0f} دقیقه | میانگین زمان انجام: {avg_duration:.1f} ساعت",
    )
    meta.fill = _excel_fill("F8FAFC")
    meta.font = Font(name="Tahoma", size=9, bold=True, color="64748B")
    meta.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
    meta.border = _excel_border()
    ws.row_dimensions[meta_row].height = 25

    dep_data = defaultdict(lambda: {"total": 0, "done": 0, "active": 0, "open": 0, "cost": 0.0})
    type_data = defaultdict(lambda: {"total": 0, "done": 0, "cost": 0.0})
    eq_data = defaultdict(lambda: {"total": 0, "done": 0, "em": 0, "cost": 0.0})
    priority_data = defaultdict(lambda: {"total": 0, "done": 0})
    months = defaultdict(lambda: {"total": 0, "done": 0, "active": 0, "open": 0})
    people_data = defaultdict(lambda: {"total": 0, "em": 0})

    for wo in records:
        dep = getattr(getattr(wo, "department", None), "name", "") or "بدون دپارتمان"
        status = _enum_name(getattr(wo, "status", None))
        typ = _enum_name(getattr(wo, "type", None)) or "OTHER"
        eq = getattr(getattr(wo, "equipment", None), "name", "") or "بدون تجهیز"
        priority = _enum_name(getattr(wo, "priority", None)) or "OTHER"
        cost = _money(getattr(wo, "manual_cost", 0))

        b = dep_data[dep]
        b["total"] += 1; b["done"] += status in WO_COMPLETED_STATUSES; b["active"] += status in WO_ACTIVE_STATUSES; b["open"] += status in WO_PENDING_STATUSES; b["cost"] += cost
        b = type_data[typ]
        b["total"] += 1; b["done"] += status in WO_COMPLETED_STATUSES; b["cost"] += cost
        b = eq_data[eq]
        b["total"] += 1; b["done"] += status in WO_COMPLETED_STATUSES; b["em"] += typ in {"EMERGENCY", "EM"}; b["cost"] += cost
        b = priority_data[priority]
        b["total"] += 1; b["done"] += status in WO_COMPLETED_STATUSES

        key = _month_key(getattr(wo, "scheduled_date", None))
        if key:
            b = months[key]
            b["total"] += 1; b["done"] += status in WO_COMPLETED_STATUSES; b["active"] += status in WO_ACTIVE_STATUSES; b["open"] += status in WO_PENDING_STATUSES

        is_em = typ in {"EMERGENCY", "EM"}
        for person in list(getattr(wo, "completers", None) or []):
            label = _personnel_label(person)
            if label:
                people_data[label]["total"] += 1
                people_data[label]["em"] += is_em

    dep_rows = [
        (name, b["total"], b["done"], b["active"], b["open"], _pct(b["done"], b["total"]), f"{b['cost']:,.0f}")
        for name, b in sorted(dep_data.items(), key=lambda x: (-x[1]["total"], x[0]))
    ]
    type_rows = [
        (WO_TYPE_FA.get(key, key), b["total"], b["done"], _pct(b["done"], b["total"]), f"{b['cost']:,.0f}")
        for key, b in sorted(type_data.items(), key=lambda x: (-x[1]["total"], x[0]))
    ]
    eq_rows = [
        (name, b["total"], b["done"], b["em"], f"{b['cost']:,.0f}")
        for name, b in sorted(eq_data.items(), key=lambda x: (-x[1]["total"], x[0]))[:15]
    ]
    trend_rows = [
        (_month_label(key), b["total"], b["done"], b["active"], b["open"], _pct(b["done"], b["total"]))
        for key, b in sorted(months.items(), reverse=True)[:12]
    ]
    priority_rows = [
        (WO_PRIORITY_FA.get(key, key), b["total"], b["done"], _pct(b["done"], b["total"]))
        for key, b in sorted(priority_data.items(), key=lambda x: (-x[1]["total"], x[0]))
    ]
    people_rows = [
        (name, b["total"], b["em"])
        for name, b in sorted(people_data.items(), key=lambda x: (-x[1]["total"], x[0]))[:15]
    ]

    summary_row = meta_row + 2
    _excel_summary_table(ws, summary_row, 1, ["دپارتمان", "کل", "تکمیل", "فعال", "باز", "درصد تکمیل", "هزینه"], dep_rows, "خلاصه عملکرد بر اساس دپارتمان")
    _excel_summary_table(ws, summary_row, 9, ["نوع", "کل", "تکمیل", "درصد تکمیل", "هزینه"], type_rows, "خلاصه بر اساس نوع فعالیت")

    second_row = summary_row + max(len(dep_rows), len(type_rows)) + 4
    _excel_summary_table(ws, second_row, 1, ["تجهیز", "کل", "تکمیل", "EM", "هزینه"], eq_rows, "تجهیزات با بیشترین دستورکار")
    _excel_summary_table(ws, second_row, 8, ["ماه", "کل", "تکمیل", "فعال", "باز", "درصد تکمیل"], trend_rows, "روند ماهانه دستورکارها")
    _excel_summary_table(ws, second_row, 15, ["اولویت", "کل", "تکمیل", "درصد تکمیل"], priority_rows, "خلاصه بر اساس اولویت")

    third_row = second_row + max(len(eq_rows), len(trend_rows), len(priority_rows)) + 4
    if people_rows:
        _excel_summary_table(ws, third_row, 1, ["پرسنل انجام‌دهنده", "دستورکار", "EM"], people_rows, "پرسنل انجام‌دهنده — خلاصه عملکرد")
        return third_row + len(people_rows) + 5
    return third_row + 3


def _excel_summary_repair_requests(ws, source_records, start_row: int) -> int:
    records = list(source_records or [])
    total = len(records)
    completed = sum(getattr(rr, "completion", None) is not None for rr in records)
    pending = total - completed
    total_cost = sum(_money(getattr(getattr(rr, "completion", None), "manual_cost", 0)) for rr in records)
    total_delay = sum(_money(getattr(getattr(rr, "completion", None), "delay_minutes", 0)) for rr in records)

    repair_hours = []
    for rr in records:
        completion = getattr(rr, "completion", None)
        if completion:
            start = getattr(rr, "breakdown_datetime", None)
            finish = getattr(completion, "completion_datetime", None)
            if start and finish:
                try:
                    hours = (finish - start).total_seconds() / 3600.0
                    if 0 <= hours <= 24 * 365:
                        repair_hours.append(hours)
                except Exception:
                    pass
    avg_repair = sum(repair_hours) / len(repair_hours) if repair_hours else 0.0

    _excel_section_header(ws, start_row, 1, len(REPAIR_REQUEST_DETAIL_HEADERS), "خلاصه مدیریتی گزارش درخواست‌های تعمیرات")
    kpi_row = start_row + 1
    card_width = 4
    kpis = [
        ("کل درخواست‌ها", f"{total:,}", "رکورد منطبق با فیلتر"),
        ("انجام‌شده", f"{completed:,}", f"نرخ تکمیل: {_pct(completed, total)}"),
        ("در انتظار", f"{pending:,}", "باز"),
        ("میانگین زمان رفع", f"{avg_repair:.1f} ساعت", "رکوردهای دارای زمان معتبر"),
        ("هزینه کل", f"{total_cost:,.0f}", "ریال"),
    ]
    for i, (title, value, sub) in enumerate(kpis):
        s_col = 1 + i * card_width
        _excel_kpi_card(ws, kpi_row, s_col, s_col + card_width - 1, title, value, sub)

    meta_row = kpi_row + 4
    ws.merge_cells(start_row=meta_row, start_column=1, end_row=meta_row, end_column=len(REPAIR_REQUEST_DETAIL_HEADERS))
    meta = ws.cell(meta_row, 1, f"تاخیر ثبت‌شده: {total_delay:,.0f} دقیقه | نرخ تکمیل: {_pct(completed, total)} | تعداد سوابق دارای زمان رفع معتبر: {len(repair_hours):,}")
    meta.fill = _excel_fill("F8FAFC")
    meta.font = Font(name="Tahoma", size=9, bold=True, color="64748B")
    meta.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
    meta.border = _excel_border()
    ws.row_dimensions[meta_row].height = 24

    dep_data = defaultdict(lambda: {"total": 0, "done": 0, "pending": 0, "cost": 0.0})
    unit_data = defaultdict(lambda: {"total": 0, "done": 0, "pending": 0})
    eq_data = defaultdict(lambda: {"total": 0, "done": 0, "pending": 0, "cost": 0.0})
    months = defaultdict(lambda: {"total": 0, "done": 0, "pending": 0})
    people_data = defaultdict(int)

    for rr in records:
        completion = getattr(rr, "completion", None)
        done = completion is not None
        dep = getattr(getattr(rr, "department", None), "name", "") or "بدون دپارتمان"
        unit = str(getattr(rr, "requesting_unit", "") or "بدون واحد")
        eq = str(getattr(rr, "equipment_name", "") or "بدون تجهیز")
        cost = _money(getattr(completion, "manual_cost", 0)) if completion else 0.0

        b = dep_data[dep]; b["total"] += 1; b["done"] += done; b["pending"] += not done; b["cost"] += cost
        b = unit_data[unit]; b["total"] += 1; b["done"] += done; b["pending"] += not done
        b = eq_data[eq]; b["total"] += 1; b["done"] += done; b["pending"] += not done; b["cost"] += cost

        key = _month_key(getattr(rr, "breakdown_datetime", None))
        if key:
            b = months[key]; b["total"] += 1; b["done"] += done; b["pending"] += not done

        if completion:
            for person in list(getattr(completion, "personnel", None) or []):
                label = _personnel_label(person)
                if label:
                    people_data[label] += 1

    dep_rows = [
        (name, b["total"], b["done"], b["pending"], _pct(b["done"], b["total"]), f"{b['cost']:,.0f}")
        for name, b in sorted(dep_data.items(), key=lambda x: (-x[1]["total"], x[0]))
    ]
    unit_rows = [
        (name, b["total"], b["done"], b["pending"], _pct(b["done"], b["total"]))
        for name, b in sorted(unit_data.items(), key=lambda x: (-x[1]["total"], x[0]))[:20]
    ]
    eq_rows = [
        (name, b["total"], b["done"], b["pending"], f"{b['cost']:,.0f}")
        for name, b in sorted(eq_data.items(), key=lambda x: (-x[1]["total"], x[0]))[:15]
    ]
    trend_rows = [
        (_month_label(key), b["total"], b["done"], b["pending"], _pct(b["done"], b["total"]))
        for key, b in sorted(months.items(), reverse=True)[:12]
    ]
    people_rows = [
        (name, count)
        for name, count in sorted(people_data.items(), key=lambda x: (-x[1], x[0]))[:15]
    ]

    summary_row = meta_row + 2
    _excel_summary_table(ws, summary_row, 1, ["دپارتمان", "کل", "انجام", "باز", "درصد تکمیل", "هزینه"], dep_rows, "خلاصه بر اساس دپارتمان انجام‌دهنده")
    _excel_summary_table(ws, summary_row, 8, ["واحد متقاضی", "کل", "انجام", "باز", "درصد تکمیل"], unit_rows, "خلاصه بر اساس واحد متقاضی")

    second_row = summary_row + max(len(dep_rows), len(unit_rows)) + 4
    _excel_summary_table(ws, second_row, 1, ["تجهیز", "کل", "انجام", "باز", "هزینه"], eq_rows, "تجهیزات با بیشترین درخواست تعمیر")
    _excel_summary_table(ws, second_row, 8, ["ماه", "کل", "انجام", "باز", "درصد تکمیل"], trend_rows, "روند ماهانه احکام تعمیرات")
    if people_rows:
        _excel_summary_table(ws, second_row, 14, ["پرسنل انجام‌دهنده", "موارد انجام"], people_rows, "پرسنل انجام‌دهنده — خلاصه عملکرد")

    return second_row + max(len(eq_rows), len(trend_rows), len(people_rows)) + 5


def _write_detail_rows(ws, header_row: int, headers: list[str], rows: list[list[Any]]):
    last_col = len(headers)
    last_col_letter = get_column_letter(last_col)
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(header_row, col_idx, header)
        cell.fill = _excel_fill("17365D")
        cell.font = Font(name="Tahoma", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _excel_border("17365D", "medium")
    ws.row_dimensions[header_row].height = 36

    for ridx, row_values in enumerate(rows, start=header_row + 1):
        for cidx, value in enumerate(row_values, start=1):
            cell = ws.cell(ridx, cidx, value)
            cell.fill = _excel_fill("FFFFFF" if (ridx - header_row) % 2 else "F8FAFC")
            cell.font = Font(name="Tahoma", size=9, color="1F2937")
            cell.alignment = Alignment(
                horizontal="right" if isinstance(value, str) else "center",
                vertical="top",
                wrap_text=True,
            )
            cell.border = _excel_border("E1E7EF")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cell.number_format = "#,##0.00" if isinstance(value, float) and not float(value).is_integer() else "#,##0"
        ws.row_dimensions[ridx].height = 42

    # Useful status emphasis without conditional formatting or tables.
    status_columns = [i + 1 for i, h in enumerate(headers) if h in {"وضعیت", "وضعیت اتمام"}]
    for col_idx in status_columns:
        for row_idx in range(header_row + 1, header_row + 1 + len(rows)):
            cell = ws.cell(row_idx, col_idx)
            text = str(cell.value or "")
            if "انجام" in text or "تکمیل" in text or "تأیید" in text:
                cell.fill = _excel_fill("E9F7EF")
                cell.font = Font(name="Tahoma", size=9, bold=True, color="146C43")
            elif "رد" in text:
                cell.fill = _excel_fill("FDECEC")
                cell.font = Font(name="Tahoma", size=9, bold=True, color="B42318")
            elif "در انتظار" in text or "درخواست اتمام" in text:
                cell.fill = _excel_fill("FFF7E6")
                cell.font = Font(name="Tahoma", size=9, bold=True, color="9A6700")

    detail_ref = f"A{header_row}:{last_col_letter}{header_row + len(rows)}"
    # IMPORTANT: use a normal worksheet AutoFilter, not an Excel Table.
    # The previous table+autofilter combination produced Excel repair warnings
    # and caused Excel to remove the table on open.
    ws.auto_filter.ref = detail_ref
    return detail_ref


def _set_detail_widths(ws, headers: list[str], rows: list[list[Any]]):
    long_keywords = ("شرح", "یادداشت", "گزارش", "علت", "پیوست", "امضا")
    for col_idx, header in enumerate(headers, start=1):
        max_len = min(42, len(str(header)) + 2)
        for row_values in rows[:200]:
            if col_idx - 1 >= len(row_values):
                continue
            value = row_values[col_idx - 1]
            if value is None:
                continue
            for line in str(value).splitlines() or [""]:
                max_len = max(max_len, min(42, len(line) + 2))
        width = min(38, max(12, max_len))
        if any(k in str(header) for k in long_keywords):
            width = min(42, max(width, 28))
        if "شناسه" in str(header):
            width = min(width, 15)
        if "تاریخ" in str(header) or "زمان" in str(header):
            width = min(max(width, 19), 24)
        if "هزینه" in str(header):
            width = min(max(width, 18), 20)
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def _export_detailed_single_sheet(
    path: str,
    report_title: str,
    headers: list[str],
    rows: list[list[Any]],
    filter_summary: str = "",
    source_records=None,
    report_kind: str = "generic",
) -> str:
    """Create one professional single-sheet report with summary + all details.

    Design rules:
      * one visible worksheet only;
      * management summary at the top;
      * complete filtered data below it;
      * normal worksheet AutoFilter (no Excel Table XML, so no repair warning);
      * stable Persian/RTL layout and print settings;
      * navigation links between summary and detail section.
    """
    if not rows:
        raise ValueError("رکوردی برای خروجی تفصیلی وجود ندارد.")

    wb = Workbook()
    ws = wb.active
    ws.title = "گزارش تفصیلی"
    ws.sheet_view.rightToLeft = True
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "17365D"
    ws.sheet_format.defaultRowHeight = 20

    last_detail_col = max(1, len(headers))
    last_col_letter = get_column_letter(last_detail_col)

    # ------------------------------------------------------------------
    # Cover / metadata
    # ------------------------------------------------------------------
    ws.merge_cells(f"A1:{last_col_letter}1")
    title = ws["A1"]
    title.value = report_title
    title.fill = _excel_fill("17365D")
    title.font = Font(name="Tahoma", size=16, bold=True, color="FFFFFF")
    title.alignment = Alignment(horizontal="right", vertical="center")
    title.border = _excel_border("17365D", "medium")
    ws.row_dimensions[1].height = 34

    ws.merge_cells(f"A2:{last_col_letter}2")
    meta = ws["A2"]
    meta.value = (
        f"شرکت گلا | تعداد رکورد فیلترشده: {len(rows):,}"
        + (f" | {filter_summary}" if filter_summary else "")
    )
    meta.fill = _excel_fill("EAF0F6")
    meta.font = Font(name="Tahoma", size=9, bold=True, color="17365D")
    meta.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
    meta.border = _excel_border()
    ws.row_dimensions[2].height = 34

    ws.merge_cells(f"A3:{last_col_letter}3")
    stamp = ws["A3"]
    stamp.value = "تاریخ تهیه: " + _jdate(tehran_now(), True) + " | خلاصه مدیریتی و جزئیات کامل رکوردهای منطبق با فیلتر در همین Sheet قرار دارد."
    stamp.fill = _excel_fill("F8FAFC")
    stamp.font = Font(name="Tahoma", size=9, color="64748B")
    stamp.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
    stamp.border = _excel_border()
    ws.row_dimensions[3].height = 26

    # Summary starts at row 5.  Row 4 is reserved for navigation.
    summary_start = 5
    if report_kind == "work_orders":
        detail_section_row = _excel_summary_work_orders(ws, source_records or [], summary_start)
    elif report_kind == "repair_requests":
        detail_section_row = _excel_summary_repair_requests(ws, source_records or [], summary_start)
    else:
        detail_section_row = summary_start

    # ------------------------------------------------------------------
    # Navigation row after the summary is known.
    # ------------------------------------------------------------------
    _excel_nav_button(ws, 4, 1, 6, "📌 خلاصه مدیریتی", f"#'گزارش تفصیلی'!A{summary_start}", "FFF7E6")
    _excel_nav_button(ws, 4, 7, 13, "🔽 رفتن به جزئیات کامل", f"#'گزارش تفصیلی'!A{detail_section_row}", "EAF0F6")
    _excel_nav_button(ws, 4, 14, min(last_detail_col, 21), "ℹ فیلترهای فعال در ردیف 2 ثبت شده‌اند", None, "F8FAFC")
    ws.row_dimensions[4].height = 25

    _excel_section_header(ws, detail_section_row, 1, last_detail_col, "جزئیات کامل رکوردهای فیلترشده")
    detail_header_row = detail_section_row + 1

    _write_detail_rows(ws, detail_header_row, headers, rows)
    last_row = detail_header_row + len(rows)

    # ------------------------------------------------------------------
    # Detail usability
    # ------------------------------------------------------------------
    _set_detail_widths(ws, headers, rows)
    ws.freeze_panes = "A5"
    ws.sheet_view.zoomScale = 72 if len(headers) >= 30 else 82
    ws.auto_filter.ref = f"A{detail_header_row}:{last_col_letter}{last_row}"

    # Print as a proper management report: summary pages first, then detail
    # pages with only the detail header repeated.
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 2 if len(headers) >= 30 else 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins.left = 0.25
    ws.page_margins.right = 0.25
    ws.page_margins.top = 0.45
    ws.page_margins.bottom = 0.45
    ws.page_margins.header = 0.2
    ws.page_margins.footer = 0.2
    ws.print_title_rows = f"{detail_header_row}:{detail_header_row}"
    ws.print_area = f"A1:{last_col_letter}{last_row}"
    ws.oddHeader.center.text = report_title
    ws.oddHeader.center.size = 9
    ws.oddHeader.center.font = "Tahoma,Regular"
    ws.oddFooter.right.text = "صفحه &[Page] از &N"
    ws.oddFooter.right.size = 8
    ws.oddFooter.right.font = "Tahoma,Regular"
    ws.oddFooter.left.text = "شرکت گلا"
    ws.oddFooter.left.size = 8
    ws.oddFooter.left.font = "Tahoma,Regular"

    footer_row = last_row + 2
    ws.merge_cells(f"A{footer_row}:{last_col_letter}{footer_row}")
    footer = ws.cell(
        footer_row,
        1,
        "راهنما: ردیف عنوان جزئیات دارای فیلتر و مرتب‌سازی استاندارد Excel است. برای مشاهده همه سوابق، فیلتر ستون‌ها را روی «همه» قرار دهید. این فایل عمداً Excel Table ندارد تا در نسخه‌های مختلف Excel بدون خطای Repair باز شود.",
    )
    footer.fill = _excel_fill("F8FAFC")
    footer.font = Font(name="Tahoma", size=8, italic=True, color="64748B")
    footer.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
    footer.border = _excel_border()
    ws.row_dimensions[footer_row].height = 34

    wb.active = 0
    wb.save(path)
    return path


def _excel_nav_button(ws, row: int, start_col: int, end_col: int, text: str, hyperlink: str | None, fill_color: str):
    """Render a compact navigation cell range without creating Excel tables."""
    if start_col > end_col:
        return
    ws.merge_cells(start_row=row, start_column=start_col, end_row=row, end_column=end_col)
    cell = ws.cell(row, start_col, text)
    cell.fill = _excel_fill(fill_color)
    cell.font = Font(name="Tahoma", size=9, bold=True, color="17365D", underline="single" if hyperlink else None)
    cell.alignment = Alignment(horizontal="right", vertical="center")
    cell.border = _excel_border()
    if hyperlink:
        cell.hyperlink = hyperlink


def _safe_filter_text(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace(" | ", " / ")


def _read_global_report_dates(view):
    """Read the single global date range used by the ReportsView."""
    try:
        start = view.start_date.get_date()
    except Exception:
        start = None
    try:
        end = view.end_date.get_date()
    except Exception:
        end = None
    return start, end


def _format_date_filter(start, end) -> str:
    if start and end:
        return f"{_jdate(start)} تا {_jdate(end)}"
    if start:
        return f"از {_jdate(start)}"
    if end:
        return f"تا {_jdate(end)}"
    return "همه تاریخ‌ها"


def _text_filter_match(selected: str, actual: Any, all_value: str = "همه") -> bool:
    """Case-insensitive contains filter for searchable report fields."""
    if not selected or selected == all_value:
        return True
    wanted = str(selected).strip().casefold()
    actual_text = str(actual or "").strip().casefold()
    return bool(wanted and wanted in actual_text)


def _personnel_label(person) -> str:
    code = _excel_text(getattr(person, "personnel_code", ""))
    name = _excel_text(getattr(person, "full_name", ""))
    if code and name:
        return f"{code} - {name}"
    return name or code


def _collect_wo_personnel_options(records) -> list[str]:
    labels = set()
    for wo in records or []:
        for person in list(getattr(wo, "completers", None) or []):
            label = _personnel_label(person)
            if label:
                labels.add(label)
    return sorted(labels, key=lambda x: x.casefold())


def _collect_rr_personnel_options(records) -> list[str]:
    labels = set()
    for rr in records or []:
        completion = getattr(rr, "completion", None)
        for person in list(getattr(completion, "personnel", None) or []) if completion else []:
            label = _personnel_label(person)
            if label:
                labels.add(label)
    return sorted(labels, key=lambda x: x.casefold())


def _personnel_filter_match(people, selected: str) -> bool:
    if not selected or selected == "همه":
        return True
    wanted = str(selected).strip().casefold()
    if not wanted:
        return True
    for person in list(people or []):
        label = _personnel_label(person).casefold()
        name = _excel_text(getattr(person, "full_name", "")).casefold()
        code = _excel_text(getattr(person, "personnel_code", "")).casefold()
        if wanted in label or wanted in name or (code and wanted in code):
            return True
    return False


def _current_filter_summary_work_order(tab) -> str:
    f = tab._filters
    start, end = _read_global_report_dates(tab._view)
    values = [
        ("بازه", _format_date_filter(start, end)),
        ("دپارتمان", f["dept"].get()),
        ("تجهیز", f["selector"].get()),
        ("نوع", f["type"].get()),
        ("اولویت", f["priority"].get()),
        ("پرسنل انجام‌دهنده", f["personnel"].get()),
        ("وضعیت", f["status"].get()),
    ]
    return " | ".join(
        f"{key}: {_safe_filter_text(value)}"
        for key, value in values
        if _safe_filter_text(value) and _safe_filter_text(value) not in {"همه", "همه دپارتمان‌ها", "همه انواع", "همه اولویت‌ها", "همه وضعیت‌ها", "همه تاریخ‌ها"}
    ) or "همه رکوردها"


def _current_filter_summary_repair(tab) -> str:
    f = tab._filters
    start, end = _read_global_report_dates(tab._view)
    values = [
        ("بازه", _format_date_filter(start, end)),
        ("دپارتمان", f["dept"].get()),
        ("واحد متقاضی", f["selector"].get()),
        ("تجهیز", f["extra"].get()),
        ("پرسنل انجام‌دهنده", f["personnel"].get()),
        ("وضعیت", f["status"].get()),
    ]
    return " | ".join(
        f"{key}: {_safe_filter_text(value)}"
        for key, value in values
        if _safe_filter_text(value) and _safe_filter_text(value) not in {"همه", "همه دپارتمان‌ها", "همه وضعیت‌ها", "همه تاریخ‌ها"}
    ) or "همه رکوردها"


# -----------------------------------------------------------------------------
# Filter bar
# -----------------------------------------------------------------------------
def _build_filter_row(
    parent: tk.Frame,
    *,
    dept_options: list[str],
    selector_options: list[str],
    selector_label: str,
    status_options: list[str],
    apply_cmd,
    type_options: list[str] | None = None,
    priority_options: list[str] | None = None,
    personnel_options: list[str] | None = None,
    personnel_label: str = "پرسنل انجام‌دهنده",
    extra_options: list[str] | None = None,
    extra_label: str = "",
) -> dict:
    """Professional two-row report filter bar with searchable personnel/equipment/unit fields."""
    outer = tk.Frame(parent, bg=CARD_BG)
    outer.pack(fill=tk.X, padx=12, pady=(6, 0))

    top_row = tk.Frame(outer, bg=CARD_BG)
    bottom_row = tk.Frame(outer, bg=CARD_BG)
    top_row.pack(fill=tk.X, pady=(0, 3))
    bottom_row.pack(fill=tk.X, pady=(0, 5))

    def _add_label(host, text):
        return tk.Label(
            host,
            text=text,
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
        )

    controls = []

    def _new_combo(key, host, label, values, width=14, searchable=False):
        lab = _add_label(host, label)
        lab.pack(side=tk.RIGHT, padx=(0, 3))
        values = values or []
        initial = values[0] if values else ""
        var = tk.StringVar(value=initial)
        if searchable:
            cb = _ReportSearchCombobox(
                host,
                textvariable=var,
                width=width,
                font=FONT_SMALL,
                justify="right",
            )
            cb.set_values(values)
        else:
            cb = ttk.Combobox(
                host,
                textvariable=var,
                values=values,
                width=width,
                state="readonly",
                font=FONT_SMALL,
            )
        cb.pack(side=tk.RIGHT, padx=(0, 11))
        cb.bind("<Return>", lambda _e: apply_cmd(), add="+")
        controls.append((key, var, cb))
        return var, cb

    _new_combo("dept", top_row, "دپارتمان:", ["همه دپارتمان‌ها"] + list(dept_options or []), 16, False)
    _new_combo(
        "selector",
        top_row,
        f"{selector_label}:",
        ["همه"] + list(selector_options or []),
        20,
        selector_label in {"تجهیز", "واحد متقاضی"},
    )
    if extra_label:
        _new_combo(
            "extra",
            top_row,
            f"{extra_label}:",
            ["همه"] + list(extra_options or []),
            20,
            extra_label in {"تجهیز", "واحد متقاضی"},
        )
    if type_options is not None:
        _new_combo("type", top_row, "نوع:", ["همه انواع"] + list(type_options), 14, False)
    if priority_options is not None:
        _new_combo("priority", top_row, "اولویت:", ["همه اولویت‌ها"] + list(priority_options), 14, False)
    _new_combo(
        "personnel",
        bottom_row,
        f"{personnel_label}:",
        ["همه"] + list(personnel_options or []),
        24,
        True,
    )
    _new_combo(
        "status",
        bottom_row,
        "وضعیت:",
        ["همه وضعیت‌ها"] + list(status_options or []),
        16,
        False,
    )

    # Keep the most important controls visible on the first row; remaining
    # controls and actions live on the second row.  This stays readable even
    # at smaller desktop resolutions.
    if len(controls) <= 4:
        # For compact reports (e.g. a future generic report), all controls can
        # stay in the first row; move the last action row widgets back if needed.
        pass

    actions_host = tk.Frame(bottom_row, bg=CARD_BG)
    actions_host.pack(side=tk.LEFT, padx=(8, 0))
    tk.Button(
        actions_host,
        text="🔍  اعمال فیلتر",
        font=FONT_SMALL,
        bg=NAVY,
        fg=WHITE,
        activebackground=NAVY_LIGHT,
        relief="flat",
        cursor="hand2",
        padx=12,
        pady=4,
        command=apply_cmd,
    ).pack(side=tk.LEFT, padx=(0, 5))

    def _reset():
        for key, var, _cb in controls:
            if key == "dept":
                var.set("همه دپارتمان‌ها")
            elif key == "type":
                var.set("همه انواع")
            elif key == "priority":
                var.set("همه اولویت‌ها")
            elif key == "status":
                var.set("همه وضعیت‌ها")
            else:
                var.set("همه")
        apply_cmd()

    tk.Button(
        actions_host,
        text="↺  بازنشانی",
        font=FONT_SMALL,
        bg=GRAY_BG,
        fg=TEXT_DARK,
        relief="flat",
        cursor="hand2",
        padx=8,
        pady=4,
        command=_reset,
    ).pack(side=tk.LEFT)

    tk.Label(
        bottom_row,
        text="بازه زمانی از فیلتر تاریخ گزارش اصلی خوانده می‌شود.",
        font=("Tahoma", 8),
        bg=CARD_BG,
        fg=TEXT_LIGHT,
    ).pack(side=tk.LEFT, padx=(14, 0))

    tk.Frame(parent, bg=CARD_BORDER, height=1).pack(fill=tk.X)

    result = {key: var for key, var, _cb in controls}
    result.update({f"{key}_cb": cb for key, _var, cb in controls})
    return result


def _toolbar(parent: tk.Frame, excel_cmd, pdf_cmd, detailed_excel_cmd=None) -> None:
    tb = tk.Frame(parent, bg=CARD_BG)
    tb.pack(fill=tk.X, padx=12, pady=(4, 0))

    buttons = []
    if detailed_excel_cmd is not None:
        buttons.append(("📊  Excel تفصیلی", detailed_excel_cmd, NAVY_LIGHT))
    buttons.extend([
        ("📥  خروجی Excel", excel_cmd, SUCCESS),
        ("🖨️  خروجی PDF", pdf_cmd, NAVY),
    ])

    for label, cmd, color in buttons:
        tk.Button(
            tb,
            text=label,
            font=FONT_SMALL,
            bg=color,
            fg=WHITE,
            activebackground=NAVY_LIGHT,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=5,
            command=cmd,
        ).pack(side=tk.RIGHT, padx=(0, 6), pady=4)

    tk.Frame(parent, bg=CARD_BORDER, height=1).pack(fill=tk.X)


def _status_bar(parent: tk.Frame) -> tk.StringVar:
    var = tk.StringVar(value="")
    tk.Label(
        parent,
        textvariable=var,
        font=FONT_SMALL,
        bg=CARD_BG,
        fg=TEXT_LIGHT,
        anchor="w",
    ).pack(fill=tk.X, padx=14, pady=(2, 4))
    return var


# -----------------------------------------------------------------------------
# Database loaders
# -----------------------------------------------------------------------------
def _fetch_departments() -> list[str]:
    session = SessionLocal()
    try:
        return [
            row[0]
            for row in session.query(Department.name)
            .order_by(Department.name)
            .all()
            if row[0]
        ]
    except Exception:
        return []
    finally:
        session.close()


def _fetch_equipment_names() -> list[str]:
    session = SessionLocal()
    try:
        return [
            row[0]
            for row in session.query(Equipment.name)
            .order_by(Equipment.name)
            .all()
            if row[0]
        ]
    except Exception:
        return []
    finally:
        session.close()


def _fetch_wo_report_data():
    """Load only the relations needed by the report/export workflow."""
    session = SessionLocal()
    try:
        records = (
            session.query(WorkOrder)
            .options(
                joinedload(WorkOrder.equipment),
                joinedload(WorkOrder.department),
                joinedload(WorkOrder.operator),
                joinedload(WorkOrder.technician),
                joinedload(WorkOrder.supervisor),
                joinedload(WorkOrder.schedule),
                subqueryload(WorkOrder.completers).joinedload(Personnel.department),
            )
            .order_by(
                WorkOrder.created_at.desc(),
                WorkOrder.id.desc(),
            )
            .all()
        )

        dept_names = [
            row[0]
            for row in session.query(Department.name)
            .order_by(Department.name)
            .all()
            if row[0]
        ]
        eq_names = [
            row[0]
            for row in session.query(Equipment.name)
            .order_by(Equipment.name)
            .all()
            if row[0]
        ]

        session.expunge_all()
        return records, dept_names, eq_names
    finally:
        session.close()


def _fetch_rr_report_data():
    """Load repair requests plus completion information in one background job."""
    session = SessionLocal()
    try:
        records = (
            session.query(RepairRequestDocument)
            .options(
                joinedload(RepairRequestDocument.department),
                joinedload(RepairRequestDocument.assigned_personnel)
                .joinedload(Personnel.department),
                joinedload(RepairRequestDocument.completion)
                .subqueryload(RepairRequestCompletion.personnel)
                .joinedload(Personnel.department),
                joinedload(RepairRequestDocument.created_by),
            )
            .order_by(
                RepairRequestDocument.created_at.desc(),
                RepairRequestDocument.id.desc(),
            )
            .all()
        )

        dept_names = [
            row[0]
            for row in session.query(Department.name)
            .order_by(Department.name)
            .all()
            if row[0]
        ]
        equipment_names = sorted({
            str(getattr(row, "equipment_name", "") or "")
            for row in records
            if getattr(row, "equipment_name", None)
        })
        unit_names = sorted({
            str(getattr(row, "requesting_unit", "") or "")
            for row in records
            if getattr(row, "requesting_unit", None)
        })

        session.expunge_all()
        return records, dept_names, unit_names, equipment_names
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Shared summary widgets
# -----------------------------------------------------------------------------
def _kpi_card(parent, title: str, value: str, note: str = "", accent=None):
    """Build a spacious management KPI card with enough room for Persian text."""
    outer = tk.Frame(
        parent,
        bg=CARD_BORDER,
        highlightthickness=0,
        width=300,
        height=158,
    )
    outer.grid_propagate(False)

    card = tk.Frame(outer, bg=CARD_BG)
    card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

    top = tk.Frame(card, bg=CARD_BG)
    top.pack(fill=tk.X, padx=18, pady=(14, 0))

    indicator = tk.Frame(
        top,
        bg=accent or NAVY,
        width=8,
        height=48,
    )
    indicator.pack(side=tk.RIGHT, padx=(0, 11))
    indicator.pack_propagate(False)

    tk.Label(
        top,
        text=title,
        font=("Tahoma", 11, "bold"),
        bg=CARD_BG,
        fg=TEXT_LIGHT,
        anchor="e",
        justify="right",
        wraplength=235,
    ).pack(side=tk.RIGHT, fill=tk.X, expand=True)

    tk.Label(
        card,
        text=value,
        font=("Tahoma", 29, "bold"),
        bg=CARD_BG,
        fg=TEXT_DARK,
        anchor="center",
    ).pack(fill=tk.X, padx=16, pady=(8, 0))

    if note:
        tk.Label(
            card,
            text=note,
            font=("Tahoma", 10),
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            anchor="center",
            justify="center",
            wraplength=255,
        ).pack(fill=tk.X, padx=16, pady=(5, 14))
    else:
        tk.Frame(card, bg=CARD_BG, height=14).pack()

    return outer


def _build_kpi_row(parent, cards_data: list[tuple[str, str, str, Any]]) -> None:
    """Arrange KPI cards in up to three columns so text is never cramped."""
    for child in parent.winfo_children():
        child.destroy()

    columns = min(3, max(1, len(cards_data)))
    rows = (len(cards_data) + columns - 1) // columns

    for col in range(columns):
        parent.grid_columnconfigure(col, weight=1, uniform="kpi")

    for row in range(rows):
        parent.grid_rowconfigure(row, weight=1, minsize=158)

    for index, (title, value, note, accent) in enumerate(cards_data):
        row = index // columns
        col = index % columns
        card = _kpi_card(parent, title, value, note, accent)
        card.grid(row=row, column=col, sticky="nsew", padx=7, pady=5)


def _section(parent, title: str):
    outer = tk.Frame(parent, bg=CARD_BG)
    header = tk.Frame(outer, bg=CARD_BG)
    header.pack(fill=tk.X, padx=10, pady=(8, 4))

    tk.Label(
        header,
        text=title,
        font=FONT_SUBHEADING,
        bg=CARD_BG,
        fg=NAVY,
        anchor="e",
    ).pack(side=tk.RIGHT)

    tk.Frame(header, bg=CARD_BORDER, height=1).pack(
        side=tk.LEFT,
        fill=tk.X,
        expand=True,
        padx=(8, 0),
        pady=7,
    )
    return outer


def _summary_tree(parent, columns: list[tuple[str, str, int]], height: int = 8):
    tree_frame = tk.Frame(parent, bg=CARD_BG)
    tree = ttk.Treeview(
        tree_frame,
        columns=[c[0] for c in columns],
        show="headings",
        height=height,
        selectmode="browse",
    )
    rtl_columns(tree)  # RTL column order

    for col_id, heading, width in columns:
        tree.heading(col_id, text=heading, anchor="center")
        tree.column(col_id, width=width, minwidth=45, anchor="e", stretch=True)

    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)

    tree.tag_configure("even", background=WHITE)
    tree.tag_configure("odd", background="#F8FAFC")
    return tree_frame, tree


def _fill_table(tree, rows: list[tuple[Any, ...]], formatter=None):
    children = tree.get_children()
    if children:
        tree.delete(*children)

    for idx, row in enumerate(rows):
        values = formatter(row) if formatter else row
        tree.insert("", "end", values=values, tags=("odd" if idx % 2 else "even",))


def _create_scrollable_summary(parent: tk.Frame):
    """Create the vertically scrollable report body.

    The previous implementation created a Canvas correctly, but only bound
    the scrollbar.  On Windows, mouse-wheel events usually arrive at the
    child widget under the cursor, so the report body could appear to stop
    before the lower sections.  This version stores the canvas on the inner
    content frame and binds wheel events to the actual report widgets.
    """
    canvas = tk.Canvas(
        parent,
        bg=SECTION_BG,
        highlightthickness=0,
        borderwidth=0,
    )
    scrollbar = ttk.Scrollbar(
        parent,
        orient="vertical",
        command=canvas.yview,
    )
    canvas.configure(yscrollcommand=scrollbar.set)

    content = tk.Frame(canvas, bg=SECTION_BG)
    window_id = canvas.create_window(
        (0, 0),
        window=content,
        anchor="nw",
    )

    def _sync(_event=None):
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass
        try:
            canvas.itemconfigure(
                window_id,
                width=max(1, canvas.winfo_width()),
            )
        except Exception:
            pass

    content.bind("<Configure>", _sync)
    canvas.bind("<Configure>", _sync)
    # Rendered report sections are populated after the Canvas exists.  Force
    # one final geometry pass so the scrollbar always knows the full report
    # height, including the detail section at the bottom.
    content.after_idle(_sync)

    # Keep these references on the inner frame so renderers can re-bind the
    # wheel to newly-created widgets after the summary is rebuilt.
    content._summary_canvas = canvas
    content._summary_window_id = window_id
    content._summary_scrollbar = scrollbar

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    return content


def _bind_summary_mousewheel(root: tk.Misc, content: tk.Frame) -> None:
    """Bind mouse-wheel scrolling to the visible report body.

    Treeviews keep their own wheel behavior; all other descendants scroll the
    outer report canvas.  This makes the long report page scroll naturally on
    Windows, including when the cursor is over cards, labels, and blank areas.
    """
    canvas = getattr(content, "_summary_canvas", None)
    if canvas is None:
        return

    def _vertical(event):
        try:
            if isinstance(event.widget, ttk.Treeview):
                return None
            delta = getattr(event, "delta", 0)
            if delta:
                units = int(-delta / 120)
                if units == 0:
                    units = -1 if delta > 0 else 1
                canvas.yview_scroll(units, "units")
                return "break"
        except Exception:
            pass
        return None

    def _linux_up(_event):
        try:
            canvas.yview_scroll(-3, "units")
            return "break"
        except Exception:
            return None

    def _linux_down(_event):
        try:
            canvas.yview_scroll(3, "units")
            return "break"
        except Exception:
            return None

    def _bind(widget):
        if isinstance(widget, ttk.Treeview):
            # Treeviews have their own vertical scrollbar and should retain it.
            return
        try:
            widget.bind("<MouseWheel>", _vertical, add="+")
            widget.bind("<Shift-MouseWheel>", _vertical, add="+")
            widget.bind("<Button-4>", _linux_up, add="+")
            widget.bind("<Button-5>", _linux_down, add="+")
        except Exception:
            pass
        for child in widget.winfo_children():
            _bind(child)

    _bind(content)
    try:
        canvas.bind("<MouseWheel>", _vertical, add="+")
        canvas.bind("<Shift-MouseWheel>", _vertical, add="+")
        canvas.bind("<Button-4>", _linux_up, add="+")
        canvas.bind("<Button-5>", _linux_down, add="+")
    except Exception:
        pass


def _detail_section(parent, title, columns, rows, widths=None):
    """Add a full-width filtered detail table below the management summaries."""
    section = _section(parent, title)
    section.pack(fill=tk.BOTH, expand=False, padx=8, pady=(10, 8))

    host = tk.Frame(section, bg=CARD_BG)
    host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
    host.grid_rowconfigure(0, weight=1)
    host.grid_columnconfigure(0, weight=1)

    tree_columns = [item[0] for item in columns]
    tree = ttk.Treeview(
        host,
        columns=tree_columns,
        show="headings",
        selectmode="browse",
        height=12,
    )
    rtl_columns(tree)  # RTL column order

    for idx, (column_id, heading) in enumerate(columns):
        width = (widths or {}).get(column_id, 130)
        tree.heading(column_id, text=heading, anchor="center")
        tree.column(
            column_id,
            width=width,
            minwidth=55,
            anchor="e",
            stretch=True,
        )

    vsb = ttk.Scrollbar(host, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(host, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")

    tree.tag_configure("even", background=WHITE)
    tree.tag_configure("odd", background="#F8FAFC")

    for idx, row in enumerate(rows):
        tree.insert(
            "",
            "end",
            values=tuple(row),
            tags=("odd" if idx % 2 else "even",),
        )

    return section, tree


def _work_order_detail_table_rows(records):
    rows = []
    for wo in records:
        equipment = getattr(wo, "equipment", None)
        department = getattr(wo, "department", None)
        completers = getattr(wo, "completers", None) or []
        rows.append((
            getattr(wo, "id", ""),
            _safe(getattr(wo, "title", ""), "—"),
            _safe(getattr(equipment, "code", ""), "—"),
            _safe(getattr(equipment, "name", ""), "—"),
            _safe(getattr(department, "name", ""), "—"),
            _enum_fa(getattr(wo, "type", None), WO_TYPE_FA),
            _enum_fa(getattr(wo, "status", None), WO_STATUS_FA),
            _enum_fa(getattr(wo, "priority", None), WO_PRIORITY_FA),
            _jdate(getattr(wo, "scheduled_date", None), True),
            _jdate(getattr(wo, "start_time", None), True),
            _jdate(getattr(wo, "end_time", None), True),
            _excel_personnel_text(completers) or "—",
            f"{_money(getattr(wo, 'manual_cost', 0)):,.0f}",
        ))
    return rows


def _repair_request_detail_table_rows(records):
    rows = []
    for rr in records:
        completion = getattr(rr, "completion", None)
        department = getattr(rr, "department", None)
        people = getattr(completion, "personnel", None) if completion else []
        rows.append((
            getattr(rr, "id", ""),
            _safe(getattr(rr, "requesting_unit", ""), "—"),
            _safe(getattr(department, "name", ""), "—"),
            _safe(getattr(rr, "equipment_name", ""), "—"),
            _jdate(getattr(rr, "breakdown_datetime", None), True),
            _safe(getattr(rr, "requester_name", ""), "—"),
            "انجام شده" if completion else "در انتظار انجام",
            _jdate(getattr(completion, "completion_datetime", None), True) if completion else "—",
            _excel_personnel_text(people) or "—",
            f"{_money(getattr(completion, 'manual_cost', 0)):,.0f}" if completion else "0",
        ))
    return rows


# =============================================================================
# TAB 1 – MANAGEMENT SUMMARY: Work Orders
# =============================================================================
class _WorkOrderReportTab:
    """Management summary for Work Orders, with in-memory filtering."""

    def __init__(self, view, frame: tk.Frame):
        self._view = view
        self._frame = frame
        self._repo = WorkOrderRepository(SessionLocal)
        self._all_records: list[WorkOrder] = []
        self._records: list[WorkOrder] = []
        self._loading = False
        self._dept_names: list[str] = []
        self._eq_names: list[str] = []
        self._personnel_names: list[str] = []
        self._summary_content = None
        self._output_running = False
        self._build()

    def _build(self):
        f = self._frame
        self._filters = _build_filter_row(
            f,
            dept_options=[],
            selector_options=[],
            selector_label="تجهیز",
            type_options=list(WO_TYPE_FA.values()),
            priority_options=list(WO_PRIORITY_FA.values()),
            personnel_options=[],
            personnel_label="پرسنل انجام‌دهنده",
            status_options=list(WO_STATUS_FA.values()),
            apply_cmd=self._apply_filters,
        )
        _toolbar(f, self._export_excel, self._export_pdf, self._export_detailed_excel)
        self._summary_content = _create_scrollable_summary(f)
        self._status_var = _status_bar(f)
        self._load_data()

    def _load_data(self):
        if self._loading:
            return
        self._loading = True
        self._status_var.set("  در حال بارگذاری گزارش کلی دستورکارها...")

        def _do():
            try:
                records, departments, equipment = _fetch_wo_report_data()
                self._all_records = records
                self._dept_names = sorted(set(departments))
                self._eq_names = sorted(set(equipment))
                self._personnel_names = _collect_wo_personnel_options(records)
            except Exception:
                self._all_records = []
                self._dept_names = []
                self._eq_names = []
                self._personnel_names = []
            finally:
                self._loading = False
            self._frame.after(0, self._after_load)

        threading.Thread(target=_do, daemon=True).start()

    def _after_load(self):
        self._filters["dept_cb"]["values"] = ["همه دپارتمان‌ها"] + self._dept_names
        if isinstance(self._filters["selector_cb"], _ReportSearchCombobox):
            self._filters["selector_cb"].set_values(["همه"] + self._eq_names)
        else:
            self._filters["selector_cb"]["values"] = ["همه"] + self._eq_names

        if isinstance(self._filters["personnel_cb"], _ReportSearchCombobox):
            self._filters["personnel_cb"].set_values(["همه"] + self._personnel_names)
        else:
            self._filters["personnel_cb"]["values"] = ["همه"] + self._personnel_names

        self._filters["dept"].set("همه دپارتمان‌ها")
        self._filters["selector"].set("همه")
        self._filters["type"].set("همه انواع")
        self._filters["priority"].set("همه اولویت‌ها")
        self._filters["personnel"].set("همه")
        self._filters["status"].set("همه وضعیت‌ها")
        self._apply_filters()

    def _filter_values(self):
        f = self._filters
        start, end = _read_global_report_dates(self._view)
        return (
            start,
            end,
            f["dept"].get(),
            f["selector"].get(),
            f["type"].get(),
            f["priority"].get(),
            f["personnel"].get(),
            f["status"].get(),
        )

    def _apply_filters(self):
        if not hasattr(self, "_filters"):
            return

        start, end, dept_sel, eq_sel, type_sel, priority_sel, personnel_sel, status_sel = self._filter_values()
        if start and end and start > end:
            self._records = []
            self._status_var.set("  بازه تاریخ نامعتبر است: تاریخ شروع نباید بعد از تاریخ پایان باشد.")
            self._render_summary()
            return

        target_type = WO_TYPE_REVERSE.get(type_sel, "")
        target_priority = WO_PRIORITY_REVERSE.get(priority_sel, "")
        target_status = WO_STATUS_REVERSE.get(status_sel, "")
        filtered = []

        for wo in self._all_records:
            date_value = getattr(wo, "scheduled_date", None)
            d = date_value.date() if hasattr(date_value, "date") else date_value
            if start and (d is None or d < start):
                continue
            if end and (d is None or d > end):
                continue

            dep = getattr(getattr(wo, "department", None), "name", "")
            if dept_sel and dept_sel != "همه دپارتمان‌ها" and dep != dept_sel:
                continue

            eq = getattr(getattr(wo, "equipment", None), "name", "")
            if not _text_filter_match(eq_sel, eq):
                continue

            if type_sel and type_sel != "همه انواع" and _enum_name(getattr(wo, "type", None)) != target_type:
                continue
            if priority_sel and priority_sel != "همه اولویت‌ها" and _enum_name(getattr(wo, "priority", None)) != target_priority:
                continue
            if status_sel and status_sel != "همه وضعیت‌ها" and _enum_name(getattr(wo, "status", None)) != target_status:
                continue

            if not _personnel_filter_match(getattr(wo, "completers", None) or [], personnel_sel):
                continue

            filtered.append(wo)

        self._records = filtered
        self._render_summary()

    def _render_summary(self):
        content = self._summary_content
        if content is None:
            return
        _clear_frame(content)

        records = self._records
        total = len(records)

        completed = sum(_enum_name(getattr(x, "status", None)) in WO_COMPLETED_STATUSES for x in records)
        active = sum(_enum_name(getattr(x, "status", None)) in WO_ACTIVE_STATUSES for x in records)
        pending = sum(_enum_name(getattr(x, "status", None)) in WO_PENDING_STATUSES for x in records)
        rejected = sum(_enum_name(getattr(x, "status", None)) == "REJECTED" for x in records)
        em_count = sum(_enum_name(getattr(x, "type", None)) in {"EMERGENCY", "EM"} for x in records)
        pm_count = sum(_enum_name(getattr(x, "type", None)) in {"PREVENTIVE", "PM"} for x in records)
        total_cost = sum(_money(getattr(x, "manual_cost", 0)) for x in records)
        total_delay = sum(_money(getattr(x, "delay_minutes", 0)) for x in records)

        kpis = tk.Frame(content, bg=SECTION_BG)
        kpis.pack(fill=tk.X, padx=8, pady=(10, 8))
        _build_kpi_row(
            kpis,
            [
                ("کل دستورکارها", f"{total:,}", "رکوردهای منطبق با فیلتر", NAVY),
                ("تکمیل‌شده", f"{completed:,}", _pct(completed, total), SUCCESS),
                ("در حال انجام", f"{active:,}", "در حال اجرا / درخواست اتمام", WARNING),
                ("در انتظار", f"{pending:,}", "در انتظار تأیید یا شروع", NAVY_LIGHT),
                ("اضطراری (EM)", f"{em_count:,}", "سهم از کل", RED),
                ("هزینه کل", f"{total_cost:,.0f}", "ریال", SUCCESS),
            ],
        )

        meta = tk.Frame(content, bg=SECTION_BG)
        meta.pack(fill=tk.X, padx=12, pady=(0, 8))
        tk.Label(
            meta,
            text=(
                f"نرخ تکمیل: {_pct(completed, total)}   |   "
                f"PM: {pm_count:,}   |   "
                f"تاخیر ثبت‌شده: {total_delay:,.0f} دقیقه   |   "
                f"ردشده: {rejected:,}"
            ),
            font=FONT_SMALL,
            bg=SECTION_BG,
            fg=TEXT_LIGHT,
            anchor="e",
        ).pack(fill=tk.X)

        grid = tk.Frame(content, bg=SECTION_BG)
        grid.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        grid.grid_columnconfigure(0, weight=1, uniform="summary")
        grid.grid_columnconfigure(1, weight=1, uniform="summary")
        grid.grid_rowconfigure(0, weight=1)
        grid.grid_rowconfigure(1, weight=1)

        # Department summary
        dep_section = _section(grid, "خلاصه عملکرد بر اساس دپارتمان")
        dep_section.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        dep_section.pack_propagate(False)
        dep_frame = dep_section.winfo_children()[0]  # header
        table_host = tk.Frame(dep_section, bg=CARD_BG)
        table_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        dep_cols = [
            ("name", "دپارتمان", 150),
            ("total", "کل", 60),
            ("done", "تکمیل", 70),
            ("active", "فعال", 65),
            ("open", "باز", 65),
            ("rate", "درصد تکمیل", 90),
            ("cost", "هزینه", 105),
        ]
        dep_tree_frame, dep_tree = _summary_tree(table_host, dep_cols, 8)
        dep_tree_frame.pack(fill=tk.BOTH, expand=True)
        dep_data = defaultdict(lambda: {"total": 0, "done": 0, "active": 0, "open": 0, "cost": 0.0})
        for wo in records:
            name = getattr(getattr(wo, "department", None), "name", "") or "بدون دپارتمان"
            status = _enum_name(getattr(wo, "status", None))
            bucket = dep_data[name]
            bucket["total"] += 1
            bucket["done"] += status in WO_COMPLETED_STATUSES
            bucket["active"] += status in WO_ACTIVE_STATUSES
            bucket["open"] += status in WO_PENDING_STATUSES
            bucket["cost"] += _money(getattr(wo, "manual_cost", 0))
        dep_rows = []
        for name, bucket in sorted(dep_data.items(), key=lambda item: (-item[1]["total"], item[0])):
            dep_rows.append((name, bucket["total"], bucket["done"], bucket["active"], bucket["open"], _pct(bucket["done"], bucket["total"]), f"{bucket['cost']:,.0f}"))
        _fill_table(dep_tree, dep_rows)

        # Type summary
        type_section = _section(grid, "خلاصه بر اساس نوع فعالیت")
        type_section.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        type_section.pack_propagate(False)
        type_host = tk.Frame(type_section, bg=CARD_BG)
        type_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        type_cols = [
            ("name", "نوع", 140),
            ("total", "کل", 70),
            ("done", "تکمیل", 70),
            ("rate", "درصد تکمیل", 95),
            ("cost", "هزینه", 120),
        ]
        type_tree_frame, type_tree = _summary_tree(type_host, type_cols, 8)
        type_tree_frame.pack(fill=tk.BOTH, expand=True)
        type_data = defaultdict(lambda: {"total": 0, "done": 0, "cost": 0.0})
        for wo in records:
            key = _enum_name(getattr(wo, "type", None)) or "OTHER"
            bucket = type_data[key]
            bucket["total"] += 1
            bucket["done"] += _enum_name(getattr(wo, "status", None)) in WO_COMPLETED_STATUSES
            bucket["cost"] += _money(getattr(wo, "manual_cost", 0))
        type_rows = []
        for key, bucket in sorted(type_data.items(), key=lambda item: (-item[1]["total"], item[0])):
            type_rows.append((WO_TYPE_FA.get(key, key), bucket["total"], bucket["done"], _pct(bucket["done"], bucket["total"]), f"{bucket['cost']:,.0f}"))
        _fill_table(type_tree, type_rows)

        # Top equipment
        eq_section = _section(grid, "تجهیزات با بیشترین دستورکار")
        eq_section.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        eq_section.pack_propagate(False)
        eq_host = tk.Frame(eq_section, bg=CARD_BG)
        eq_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        eq_cols = [
            ("name", "تجهیز", 190),
            ("total", "کل", 65),
            ("done", "تکمیل", 70),
            ("em", "EM", 60),
            ("cost", "هزینه", 115),
        ]
        eq_tree_frame, eq_tree = _summary_tree(eq_host, eq_cols, 8)
        eq_tree_frame.pack(fill=tk.BOTH, expand=True)
        eq_data = defaultdict(lambda: {"total": 0, "done": 0, "em": 0, "cost": 0.0})
        for wo in records:
            name = getattr(getattr(wo, "equipment", None), "name", "") or "بدون تجهیز"
            bucket = eq_data[name]
            bucket["total"] += 1
            bucket["done"] += _enum_name(getattr(wo, "status", None)) in WO_COMPLETED_STATUSES
            bucket["em"] += _enum_name(getattr(wo, "type", None)) in {"EMERGENCY", "EM"}
            bucket["cost"] += _money(getattr(wo, "manual_cost", 0))
        eq_rows = []
        for name, bucket in sorted(eq_data.items(), key=lambda item: (-item[1]["total"], item[0]))[:10]:
            eq_rows.append((name, bucket["total"], bucket["done"], bucket["em"], f"{bucket['cost']:,.0f}"))
        _fill_table(eq_tree, eq_rows)

        # Monthly trend
        trend_section = _section(grid, "روند ماهانه دستورکارها")
        trend_section.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        trend_section.pack_propagate(False)
        trend_host = tk.Frame(trend_section, bg=CARD_BG)
        trend_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        trend_cols = [
            ("month", "ماه", 95),
            ("total", "کل", 65),
            ("done", "تکمیل", 70),
            ("active", "فعال", 65),
            ("open", "باز", 65),
            ("rate", "درصد", 75),
        ]
        trend_tree_frame, trend_tree = _summary_tree(trend_host, trend_cols, 8)
        trend_tree_frame.pack(fill=tk.BOTH, expand=True)
        months = defaultdict(lambda: {"total": 0, "done": 0, "active": 0, "open": 0})
        for wo in records:
            key = _month_key(getattr(wo, "scheduled_date", None))
            if not key:
                continue
            status = _enum_name(getattr(wo, "status", None))
            bucket = months[key]
            bucket["total"] += 1
            bucket["done"] += status in WO_COMPLETED_STATUSES
            bucket["active"] += status in WO_ACTIVE_STATUSES
            bucket["open"] += status in WO_PENDING_STATUSES
        trend_rows = []
        for key in sorted(months.keys(), reverse=True)[:12]:
            bucket = months[key]
            trend_rows.append((_month_label(key), bucket["total"], bucket["done"], bucket["active"], bucket["open"], _pct(bucket["done"], bucket["total"])))
        _fill_table(trend_tree, trend_rows)

        # ------------------------------------------------------------------
        # Filtered detail records.  This is intentionally below the four
        # management summary blocks so the entire page can be scrolled.
        # ------------------------------------------------------------------
        detail_columns = [
            ("id", "شناسه",),
            ("title", "عنوان",),
            ("code", "کد تجهیز",),
            ("equipment", "تجهیز",),
            ("department", "دپارتمان",),
            ("type", "نوع",),
            ("status", "وضعیت",),
            ("priority", "اولویت",),
            ("scheduled", "برنامه",),
            ("start", "شروع",),
            ("end", "پایان",),
            ("personnel", "پرسنل انجام‌دهنده",),
            ("cost", "هزینه",),
        ]
        _detail_section(
            content,
            "جزئیات دستورکارهای فیلترشده",
            detail_columns,
            _work_order_detail_table_rows(records),
            widths={
                "id": 70, "title": 190, "code": 95, "equipment": 180,
                "department": 150, "type": 95, "status": 115,
                "priority": 90, "scheduled": 145, "start": 145,
                "end": 145, "personnel": 240, "cost": 120,
            },
        )

        _bind_summary_mousewheel(self._frame.winfo_toplevel(), content)

        self._status_var.set(
            f"  گزارش کلی: {total:,} دستور کار | تکمیل: {completed:,} | "
            f"نرخ تکمیل: {_pct(completed, total)}"
        )

    def _export_excel(self):
        if not self._records:
            messagebox.showwarning("هشدار", "رکوردی برای خروجی وجود ندارد.", parent=self._frame)
            return
        filename = filedialog.asksaveasfilename(
            title="ذخیره Excel دستور کار",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"work_orders_{jalali_stamp(False)}.xlsx",
        )
        if not filename:
            return
        records = list(self._records)

        def _done():
            messagebox.showinfo("موفق", "فایل Excel با موفقیت ذخیره شد!", parent=self._frame)

        def _error(exc):
            messagebox.showerror("خطا", f"خطا در ایجاد Excel:\n{exc}", parent=self._frame)

        _run_output_in_background(
            self,
            "خروجی Excel دستورکارها",
            lambda: export_work_orders_excel(records, filename),
            _done,
            _error,
        )

    def _export_detailed_excel(self):
        if not self._records:
            messagebox.showwarning(
                "هشدار",
                "رکوردی با فیلترهای فعلی برای خروجی تفصیلی وجود ندارد.",
                parent=self._frame,
            )
            return

        filename = filedialog.asksaveasfilename(
            title="ذخیره Excel تفصیلی دستورکارها",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"work_orders_detailed_{jalali_stamp(False)}.xlsx",
        )
        if not filename:
            return

        records = list(self._records)
        filter_summary = _current_filter_summary_work_order(self)
        detail_rows = [_work_order_detail_row(wo) for wo in records]

        _run_output_in_background(
            self,
            "Excel تفصیلی دستورکارها",
            lambda: _export_detailed_single_sheet(
                filename,
                "گزارش تفصیلی دستورکارها",
                WORK_ORDER_DETAIL_HEADERS,
                detail_rows,
                filter_summary,
                source_records=records,
                report_kind="work_orders",
            ),
            lambda: messagebox.showinfo(
                "موفق",
                f"Excel تفصیلی ایجاد شد.\nتعداد رکورد: {len(records):,}",
                parent=self._frame,
            ),
            lambda exc: messagebox.showerror(
                "خطا",
                f"خطا در ایجاد Excel تفصیلی:\n{exc}",
                parent=self._frame,
            ),
        )

    def _export_pdf(self):
        if not self._records:
            messagebox.showwarning("هشدار", "رکوردی برای خروجی وجود ندارد.", parent=self._frame)
            return
        filename = filedialog.asksaveasfilename(
            title="ذخیره PDF دستور کار",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"work_orders_{jalali_stamp(False)}.pdf",
        )
        if not filename:
            return
        records = list(self._records)

        def _done():
            from services.pdf_service import ROWS_PER_PAGE
            pages = (len(records) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
            messagebox.showinfo(
                "موفق",
                f"فایل PDF با موفقیت ذخیره شد.\n\nتعداد رکورد: {len(records):,}\nتعداد صفحات: {pages:,}",
                parent=self._frame,
            )

        def _error(exc):
            messagebox.showerror("خطا", f"خطا در ایجاد PDF:\n{exc}", parent=self._frame)

        _run_output_in_background(
            self,
            "خروجی PDF دستورکارها",
            lambda: export_work_orders_pdf(records, filename),
            _done,
            _error,
        )

    def refresh(self):
        self._all_records = []
        self._load_data()


# =============================================================================
# TAB 2 – MANAGEMENT SUMMARY: Repair Requests
# =============================================================================
class _RepairRequestReportTab:
    """Management summary for Repair Requests with Department + Unit + Equipment filters."""

    def __init__(self, view, frame: tk.Frame):
        self._view = view
        self._frame = frame
        self._repo = RepairRequestRepository(SessionLocal)
        self._all_records: list[RepairRequestDocument] = []
        self._records: list[RepairRequestDocument] = []
        self._loading = False
        self._dept_names: list[str] = []
        self._unit_names: list[str] = []
        self._equipment_names: list[str] = []
        self._personnel_names: list[str] = []
        self._summary_content = None
        self._output_running = False
        self._build()

    def _build(self):
        f = self._frame
        self._filters = _build_filter_row(
            f,
            dept_options=[],
            selector_options=[],
            selector_label="واحد متقاضی",
            extra_options=[],
            extra_label="تجهیز",
            personnel_options=[],
            personnel_label="پرسنل انجام‌دهنده",
            type_options=None,
            priority_options=None,
            status_options=["انجام شده", "در انتظار انجام"],
            apply_cmd=self._apply_filters,
        )
        _toolbar(f, self._export_excel, self._export_pdf, self._export_detailed_excel)
        self._summary_content = _create_scrollable_summary(f)
        self._status_var = _status_bar(f)
        self._load_data()

    def _load_data(self):
        if self._loading:
            return
        self._loading = True
        self._status_var.set("  در حال بارگذاری گزارش کلی احکام تعمیرات...")

        def _do():
            try:
                records, departments, units, equipment = _fetch_rr_report_data()
                self._all_records = records
                self._dept_names = sorted(set(departments))
                self._unit_names = sorted(set(units))
                self._equipment_names = sorted(set(equipment))
                self._personnel_names = _collect_rr_personnel_options(records)
            except Exception:
                self._all_records = []
                self._dept_names = []
                self._unit_names = []
                self._equipment_names = []
                self._personnel_names = []
            finally:
                self._loading = False
            self._frame.after(0, self._after_load)

        threading.Thread(target=_do, daemon=True).start()

    def _after_load(self):
        self._filters["dept_cb"]["values"] = ["همه دپارتمان‌ها"] + self._dept_names
        if isinstance(self._filters["selector_cb"], _ReportSearchCombobox):
            self._filters["selector_cb"].set_values(["همه"] + self._unit_names)
        else:
            self._filters["selector_cb"]["values"] = ["همه"] + self._unit_names
        if isinstance(self._filters["extra_cb"], _ReportSearchCombobox):
            self._filters["extra_cb"].set_values(["همه"] + self._equipment_names)
        else:
            self._filters["extra_cb"]["values"] = ["همه"] + self._equipment_names
        if isinstance(self._filters["personnel_cb"], _ReportSearchCombobox):
            self._filters["personnel_cb"].set_values(["همه"] + self._personnel_names)
        else:
            self._filters["personnel_cb"]["values"] = ["همه"] + self._personnel_names

        self._filters["dept"].set("همه دپارتمان‌ها")
        self._filters["selector"].set("همه")
        self._filters["extra"].set("همه")
        self._filters["personnel"].set("همه")
        self._filters["status"].set("همه وضعیت‌ها")
        self._apply_filters()

    def _apply_filters(self):
        if not hasattr(self, "_filters"):
            return

        f = self._filters
        start, end = _read_global_report_dates(self._view)
        if start and end and start > end:
            self._records = []
            self._status_var.set("  بازه تاریخ نامعتبر است: تاریخ شروع نباید بعد از تاریخ پایان باشد.")
            self._render_summary()
            return

        dept_sel = f["dept"].get()
        unit_sel = f["selector"].get()
        eq_sel = f["extra"].get()
        personnel_sel = f["personnel"].get()
        status_sel = f["status"].get()

        filtered = []
        for rr in self._all_records:
            date_value = getattr(rr, "breakdown_datetime", None)
            d = date_value.date() if hasattr(date_value, "date") else date_value
            if start and (d is None or d < start):
                continue
            if end and (d is None or d > end):
                continue

            dep = getattr(getattr(rr, "department", None), "name", "")
            if dept_sel and dept_sel != "همه دپارتمان‌ها" and dep != dept_sel:
                continue
            if not _text_filter_match(unit_sel, getattr(rr, "requesting_unit", "")):
                continue
            if not _text_filter_match(eq_sel, getattr(rr, "equipment_name", "")):
                continue

            completion = getattr(rr, "completion", None)
            if status_sel and status_sel != "همه وضعیت‌ها":
                if status_sel == "انجام شده" and completion is None:
                    continue
                if status_sel == "در انتظار انجام" and completion is not None:
                    continue

            completion_people = getattr(completion, "personnel", None) if completion else []
            if not _personnel_filter_match(completion_people or [], personnel_sel):
                continue

            filtered.append(rr)

        self._records = filtered
        self._render_summary()

    def _render_summary(self):
        content = self._summary_content
        if content is None:
            return
        _clear_frame(content)

        records = self._records
        total = len(records)
        completed = sum(getattr(x, "completion", None) is not None for x in records)
        pending = total - completed
        total_cost = 0.0
        total_delay = 0.0
        repair_hours = []

        for rr in records:
            completion = getattr(rr, "completion", None)
            if completion is not None:
                total_cost += _money(getattr(completion, "manual_cost", 0))
                total_delay += _money(getattr(completion, "delay_minutes", 0))
                start = getattr(rr, "breakdown_datetime", None)
                finish = getattr(completion, "completion_datetime", None)
                if start and finish:
                    try:
                        hours = (finish - start).total_seconds() / 3600.0
                        if 0 <= hours <= 24 * 365:
                            repair_hours.append(hours)
                    except Exception:
                        pass

        avg_repair = sum(repair_hours) / len(repair_hours) if repair_hours else 0.0

        kpis = tk.Frame(content, bg=SECTION_BG)
        kpis.pack(fill=tk.X, padx=8, pady=(10, 8))
        _build_kpi_row(
            kpis,
            [
                ("کل احکام تعمیرات", f"{total:,}", "رکوردهای منطبق با فیلتر", NAVY),
                ("انجام‌شده", f"{completed:,}", _pct(completed, total), SUCCESS),
                ("در انتظار انجام", f"{pending:,}", "نیازمند پیگیری", WARNING),
                ("نرخ تکمیل", _pct(completed, total), "بر اساس درخواست‌های فیلترشده", NAVY_LIGHT),
                ("میانگین زمان رفع", f"{avg_repair:.1f} ساعت", "رکوردهای دارای زمان معتبر", RED),
                ("هزینه کل", f"{total_cost:,.0f}", "ریال", SUCCESS),
            ],
        )

        meta = tk.Frame(content, bg=SECTION_BG)
        meta.pack(fill=tk.X, padx=12, pady=(0, 8))
        tk.Label(
            meta,
            text=f"تاخیر ثبت‌شده: {total_delay:,.0f} دقیقه",
            font=FONT_SMALL,
            bg=SECTION_BG,
            fg=TEXT_LIGHT,
            anchor="e",
        ).pack(fill=tk.X)

        grid = tk.Frame(content, bg=SECTION_BG)
        grid.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        grid.grid_columnconfigure(0, weight=1, uniform="summary")
        grid.grid_columnconfigure(1, weight=1, uniform="summary")
        grid.grid_rowconfigure(0, weight=1)
        grid.grid_rowconfigure(1, weight=1)

        # Department summary
        dep_section = _section(grid, "خلاصه بر اساس دپارتمان انجام‌دهنده")
        dep_section.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        dep_section.pack_propagate(False)
        dep_host = tk.Frame(dep_section, bg=CARD_BG)
        dep_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        dep_cols = [
            ("name", "دپارتمان", 155),
            ("total", "کل", 60),
            ("done", "انجام", 70),
            ("pending", "باز", 65),
            ("rate", "درصد", 80),
            ("cost", "هزینه", 105),
        ]
        dep_tree_frame, dep_tree = _summary_tree(dep_host, dep_cols, 8)
        dep_tree_frame.pack(fill=tk.BOTH, expand=True)
        dep_data = defaultdict(lambda: {"total": 0, "done": 0, "pending": 0, "cost": 0.0})
        for rr in records:
            name = getattr(getattr(rr, "department", None), "name", "") or "بدون دپارتمان"
            completed_flag = getattr(rr, "completion", None) is not None
            bucket = dep_data[name]
            bucket["total"] += 1
            bucket["done"] += completed_flag
            bucket["pending"] += not completed_flag
            completion = getattr(rr, "completion", None)
            if completion:
                bucket["cost"] += _money(getattr(completion, "manual_cost", 0))
        dep_rows = []
        for name, bucket in sorted(dep_data.items(), key=lambda item: (-item[1]["total"], item[0])):
            dep_rows.append((name, bucket["total"], bucket["done"], bucket["pending"], _pct(bucket["done"], bucket["total"]), f"{bucket['cost']:,.0f}"))
        _fill_table(dep_tree, dep_rows)

        # Requesting unit summary
        unit_section = _section(grid, "خلاصه بر اساس واحد متقاضی")
        unit_section.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        unit_section.pack_propagate(False)
        unit_host = tk.Frame(unit_section, bg=CARD_BG)
        unit_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        unit_cols = [
            ("name", "واحد متقاضی", 165),
            ("total", "کل", 60),
            ("done", "انجام", 70),
            ("pending", "باز", 65),
            ("rate", "درصد", 80),
        ]
        unit_tree_frame, unit_tree = _summary_tree(unit_host, unit_cols, 8)
        unit_tree_frame.pack(fill=tk.BOTH, expand=True)
        unit_data = defaultdict(lambda: {"total": 0, "done": 0, "pending": 0})
        for rr in records:
            name = str(getattr(rr, "requesting_unit", "") or "بدون واحد")
            completed_flag = getattr(rr, "completion", None) is not None
            bucket = unit_data[name]
            bucket["total"] += 1
            bucket["done"] += completed_flag
            bucket["pending"] += not completed_flag
        unit_rows = []
        for name, bucket in sorted(unit_data.items(), key=lambda item: (-item[1]["total"], item[0]))[:15]:
            unit_rows.append((name, bucket["total"], bucket["done"], bucket["pending"], _pct(bucket["done"], bucket["total"])))
        _fill_table(unit_tree, unit_rows)

        # Equipment summary
        eq_section = _section(grid, "تجهیزات با بیشترین درخواست تعمیر")
        eq_section.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        eq_section.pack_propagate(False)
        eq_host = tk.Frame(eq_section, bg=CARD_BG)
        eq_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        eq_cols = [
            ("name", "تجهیز", 200),
            ("total", "کل", 65),
            ("done", "انجام", 70),
            ("pending", "باز", 65),
            ("cost", "هزینه", 110),
        ]
        eq_tree_frame, eq_tree = _summary_tree(eq_host, eq_cols, 8)
        eq_tree_frame.pack(fill=tk.BOTH, expand=True)
        eq_data = defaultdict(lambda: {"total": 0, "done": 0, "pending": 0, "cost": 0.0})
        for rr in records:
            name = str(getattr(rr, "equipment_name", "") or "بدون تجهیز")
            completed_flag = getattr(rr, "completion", None) is not None
            bucket = eq_data[name]
            bucket["total"] += 1
            bucket["done"] += completed_flag
            bucket["pending"] += not completed_flag
            completion = getattr(rr, "completion", None)
            if completion:
                bucket["cost"] += _money(getattr(completion, "manual_cost", 0))
        eq_rows = []
        for name, bucket in sorted(eq_data.items(), key=lambda item: (-item[1]["total"], item[0]))[:10]:
            eq_rows.append((name, bucket["total"], bucket["done"], bucket["pending"], f"{bucket['cost']:,.0f}"))
        _fill_table(eq_tree, eq_rows)

        # Monthly trend
        trend_section = _section(grid, "روند ماهانه احکام تعمیرات")
        trend_section.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        trend_section.pack_propagate(False)
        trend_host = tk.Frame(trend_section, bg=CARD_BG)
        trend_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        trend_cols = [
            ("month", "ماه", 95),
            ("total", "کل", 65),
            ("done", "انجام", 70),
            ("pending", "باز", 65),
            ("rate", "درصد", 80),
        ]
        trend_tree_frame, trend_tree = _summary_tree(trend_host, trend_cols, 8)
        trend_tree_frame.pack(fill=tk.BOTH, expand=True)
        months = defaultdict(lambda: {"total": 0, "done": 0, "pending": 0})
        for rr in records:
            key = _month_key(getattr(rr, "breakdown_datetime", None))
            if not key:
                continue
            bucket = months[key]
            bucket["total"] += 1
            bucket["done"] += getattr(rr, "completion", None) is not None
            bucket["pending"] += getattr(rr, "completion", None) is None
        trend_rows = []
        for key in sorted(months.keys(), reverse=True)[:12]:
            bucket = months[key]
            trend_rows.append((_month_label(key), bucket["total"], bucket["done"], bucket["pending"], _pct(bucket["done"], bucket["total"])))
        _fill_table(trend_tree, trend_rows)

        detail_columns = [
            ("id", "شناسه",),
            ("unit", "واحد متقاضی",),
            ("department", "دپارتمان",),
            ("equipment", "دستگاه/وسیله",),
            ("breakdown", "اعلام خرابی",),
            ("requester", "درخواست‌دهنده",),
            ("status", "وضعیت",),
            ("completion", "اتمام",),
            ("personnel", "پرسنل انجام‌دهنده",),
            ("cost", "هزینه",),
        ]
        _detail_section(
            content,
            "جزئیات درخواست‌های تعمیرات فیلترشده",
            detail_columns,
            _repair_request_detail_table_rows(records),
            widths={
                "id": 70, "unit": 170, "department": 150, "equipment": 200,
                "breakdown": 150, "requester": 150, "status": 110,
                "completion": 150, "personnel": 250, "cost": 120,
            },
        )

        _bind_summary_mousewheel(self._frame.winfo_toplevel(), content)

        self._status_var.set(
            f"  گزارش کلی: {total:,} حکم تعمیرات | انجام‌شده: {completed:,} | "
            f"نرخ تکمیل: {_pct(completed, total)}"
        )

    def _export_excel(self):
        if not self._records:
            messagebox.showwarning("هشدار", "رکوردی برای خروجی وجود ندارد.", parent=self._frame)
            return
        filename = filedialog.asksaveasfilename(
            title="ذخیره Excel حکم تعمیرات",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"repair_requests_{jalali_stamp(False)}.xlsx",
        )
        if not filename:
            return
        records = list(self._records)

        def _done():
            messagebox.showinfo("موفق", "فایل Excel با موفقیت ذخیره شد!", parent=self._frame)

        def _error(exc):
            messagebox.showerror("خطا", f"خطا در ایجاد Excel:\n{exc}", parent=self._frame)

        _run_output_in_background(
            self,
            "خروجی Excel احکام تعمیرات",
            lambda: export_repair_requests_excel(records, filename),
            _done,
            _error,
        )

    def _export_detailed_excel(self):
        if not self._records:
            messagebox.showwarning(
                "هشدار",
                "رکوردی با فیلترهای فعلی برای خروجی تفصیلی وجود ندارد.",
                parent=self._frame,
            )
            return

        filename = filedialog.asksaveasfilename(
            title="ذخیره Excel تفصیلی درخواست تعمیرات",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"repair_requests_detailed_{jalali_stamp(False)}.xlsx",
        )
        if not filename:
            return

        records = list(self._records)
        filter_summary = _current_filter_summary_repair(self)
        detail_rows = [_repair_request_detail_row(rr) for rr in records]

        _run_output_in_background(
            self,
            "Excel تفصیلی درخواست تعمیرات",
            lambda: _export_detailed_single_sheet(
                filename,
                "گزارش تفصیلی درخواست‌های تعمیرات",
                REPAIR_REQUEST_DETAIL_HEADERS,
                detail_rows,
                filter_summary,
                source_records=records,
                report_kind="repair_requests",
            ),
            lambda: messagebox.showinfo(
                "موفق",
                f"Excel تفصیلی ایجاد شد.\nتعداد رکورد: {len(records):,}",
                parent=self._frame,
            ),
            lambda exc: messagebox.showerror(
                "خطا",
                f"خطا در ایجاد Excel تفصیلی:\n{exc}",
                parent=self._frame,
            ),
        )

    def _export_pdf(self):
        if not self._records:
            messagebox.showwarning("هشدار", "رکوردی برای خروجی وجود ندارد.", parent=self._frame)
            return
        filename = filedialog.asksaveasfilename(
            title="ذخیره PDF حکم تعمیرات",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"repair_requests_{jalali_stamp(False)}.pdf",
        )
        if not filename:
            return
        records = list(self._records)

        def _done():
            from services.pdf_service import ROWS_PER_PAGE
            pages = (len(records) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
            messagebox.showinfo(
                "موفق",
                f"فایل PDF با موفقیت ذخیره شد.\n\nتعداد رکورد: {len(records):,}\nتعداد صفحات: {pages:,}",
                parent=self._frame,
            )

        def _error(exc):
            messagebox.showerror("خطا", f"خطا در ایجاد PDF:\n{exc}", parent=self._frame)

        _run_output_in_background(
            self,
            "خروجی PDF احکام تعمیرات",
            lambda: export_repair_requests_pdf(records, filename),
            _done,
            _error,
        )

    def refresh(self):
        self._all_records = []
        self._load_data()


# =============================================================================
# PUBLIC ENTRY POINT
# =============================================================================
def attach_detail_tabs(view) -> None:
    """
    Add two management-summary tabs to an existing ReportsView.

    Existing ReportsView behavior is preserved; these two tabs remain lazy and
    load only when selected. Filters are applied in memory after the initial
    background load.
    """
    notebook: ttk.Notebook = view.notebook

    wo_frame = tk.Frame(notebook, bg=SECTION_BG)
    notebook.add(wo_frame, text="📋  دستورکارها")
    wo_frame._tab_tag = "wo_detail"

    loading_wo = tk.Label(
        wo_frame,
        text="⏳ در حال بارگذاری...",
        font=("Tahoma", 11),
        bg=SECTION_BG,
        fg=TEXT_LIGHT,
    )
    loading_wo.pack(expand=True)
    wo_frame._loading_label = loading_wo

    rr_frame = tk.Frame(notebook, bg=SECTION_BG)
    notebook.add(rr_frame, text="🔧  احکام تعمیرات")
    rr_frame._tab_tag = "rr_detail"

    loading_rr = tk.Label(
        rr_frame,
        text="⏳ در حال بارگذاری...",
        font=("Tahoma", 11),
        bg=SECTION_BG,
        fg=TEXT_LIGHT,
    )
    loading_rr.pack(expand=True)
    rr_frame._loading_label = loading_rr

    view._wo_detail_frame = wo_frame
    view._rr_detail_frame = rr_frame
    view._wo_detail_tab: _WorkOrderReportTab | None = None
    view._rr_detail_tab: _RepairRequestReportTab | None = None

    original_on_tab_changed = view._on_tab_changed

    def _patched_on_tab_changed(event=None):
        original_on_tab_changed(event)

        try:
            selected = notebook.select()
            selected_frame = notebook.nametowidget(selected)
        except Exception:
            return

        tag = getattr(selected_frame, "_tab_tag", "")

        if tag == "wo_detail" and view._wo_detail_tab is None:
            label = getattr(wo_frame, "_loading_label", None)
            if label:
                label.destroy()
            view._wo_detail_tab = _WorkOrderReportTab(view, wo_frame)

        elif tag == "rr_detail" and view._rr_detail_tab is None:
            label = getattr(rr_frame, "_loading_label", None)
            if label:
                label.destroy()
            view._rr_detail_tab = _RepairRequestReportTab(view, rr_frame)

    view._on_tab_changed = _patched_on_tab_changed
    notebook.bind("<<NotebookTabChanged>>", _patched_on_tab_changed, add=True)

    original_refresh_all = getattr(view, "_refresh_all", None)

    def _patched_refresh_all():
        # Keep the original ReportsView refresh behavior intact.
        # The same top date range must also be applied to the two new
        # management-summary tabs when the user presses the global
        # "به‌روزرسانی" button. Other tab-specific filters remain unchanged.
        if original_refresh_all:
            original_refresh_all()

        for tab in (
            getattr(view, "_wo_detail_tab", None),
            getattr(view, "_rr_detail_tab", None),
        ):
            if tab is None:
                continue
            try:
                tab._apply_filters()
            except Exception:
                pass

    view._refresh_all = _patched_refresh_all
