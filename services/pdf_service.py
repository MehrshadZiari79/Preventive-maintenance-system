# services/pdf_service.py
"""
PM System - Printable PDF Export Service (simple table layout)

A4 LANDSCAPE, one table per page, 10 records per page.
One row per record, one column per title. Columns for hand-filling
(dates, report, signatures) are left empty so people can write in them.

Columns run right-to-left (first column = right edge), matching Persian.
Change ROWS_PER_PAGE below to fit more or fewer rows per page.

Persian/Arabic text: Pillow + libraqm when available, otherwise
arabic_reshaper + python-bidi (clear RuntimeError if neither exists).

This module only reads supplied records. It never changes the database.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, date
from typing import Any, Callable, Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont

try:
    from PIL import features as _pil_features
    _RAQM_AVAILABLE = bool(_pil_features.check("raqm"))
except Exception:
    _RAQM_AVAILABLE = False

try:
    import arabic_reshaper as _arabic_reshaper
except Exception:
    _arabic_reshaper = None

try:
    from bidi.algorithm import get_display as _bidi_get_display
except Exception:
    try:
        from bidi import get_display as _bidi_get_display
    except Exception:
        _bidi_get_display = None

try:
    import jdatetime
except Exception:  # pragma: no cover
    jdatetime = None


# -----------------------------------------------------------------------------
# Page / table contract
# -----------------------------------------------------------------------------
COMPANY_NAME = "شرکت گلا - آمل"
DPI = 200
A4_W_MM = 297
A4_H_MM = 210
PAGE_W = int(A4_W_MM / 25.4 * DPI)        # 2338 px
PAGE_H = int(A4_H_MM / 25.4 * DPI)        # 1653 px

ROWS_PER_PAGE = 10
FORMS_PER_PAGE = ROWS_PER_PAGE            # kept for backward compatibility

MARGIN_X = 42
MARGIN_Y = 34
TITLE_H = 70                              # page title area
FOOTER_H = 30                             # page number area
TABLE_HEADER_H = 66

TABLE_X = MARGIN_X
TABLE_W = PAGE_W - 2 * MARGIN_X
TABLE_Y = MARGIN_Y + TITLE_H
TABLE_H = PAGE_H - MARGIN_Y - FOOTER_H - TABLE_Y
ROW_H = (TABLE_H - TABLE_HEADER_H) // ROWS_PER_PAGE

NAVY = (28, 47, 76)
WHITE = (255, 255, 255)
TEXT = (28, 33, 40)
MUTED = (91, 99, 110)
GRID = (120, 128, 140)
ZEBRA = (244, 246, 250)


# -----------------------------------------------------------------------------
# Runtime / font helpers
# -----------------------------------------------------------------------------
def _resource_path(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


def _find_font(bold: bool = False) -> str | None:
    candidates: list[str] = []
    if os.name == "nt":
        root = os.environ.get("WINDIR", r"C:\Windows")
        fonts = os.path.join(root, "Fonts")
        candidates.extend([
            os.path.join(fonts, "tahomabd.ttf" if bold else "tahoma.ttf"),
            os.path.join(fonts, "segoeuib.ttf" if bold else "segoeui.ttf"),
            os.path.join(fonts, "arialbd.ttf" if bold else "arial.ttf"),
        ])
    candidates.extend([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ])
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


FONT_REGULAR = _find_font(False)
FONT_BOLD = _find_font(True) or FONT_REGULAR
_FONT_CACHE: dict[tuple[int, bool], Any] = {}


def _font(size: int, bold: bool = False):
    key = (size, bold)
    cached = _FONT_CACHE.get(key)
    if cached is not None:
        return cached
    path = FONT_BOLD if bold else FONT_REGULAR
    result = None
    if path:
        try:
            result = ImageFont.truetype(path, size=size)
        except Exception:
            result = None
    if result is None:
        result = ImageFont.load_default()
    _FONT_CACHE[key] = result
    return result


# -----------------------------------------------------------------------------
# Text / RTL helpers
# -----------------------------------------------------------------------------
def _text(value: Any, default: str = "-") -> str:
    if value is None:
        return default
    value = str(value).strip()
    return value if value else default


def _blank(value: Any) -> str:
    v = _text(value, "")
    return "" if v == "-" else v


def _jdate(value: Any, with_time: bool = False) -> str:
    if not value:
        return "-"
    if isinstance(value, str):
        # Gregorian ISO strings ("2026-09-30", "2026-09-30 08:00") -> Jalali.
        # Anything else (already Jalali, or text like "انجام نشده") is kept.
        raw = value.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(raw, fmt)
            except ValueError:
                continue
            if parsed.year > 1700:
                return _jdate(parsed, with_time and fmt != "%Y-%m-%d")
            break
        return value
    try:
        if jdatetime is not None and isinstance(value, datetime):
            jd = jdatetime.datetime.fromgregorian(datetime=value)
            return jd.strftime("%Y/%m/%d %H:%M" if with_time else "%Y/%m/%d")
        if jdatetime is not None and isinstance(value, date):
            jd = jdatetime.date.fromgregorian(date=value)
            return jd.strftime("%Y/%m/%d")
    except Exception:
        pass
    try:
        return value.strftime("%Y/%m/%d %H:%M" if with_time else "%Y/%m/%d")
    except Exception:
        return _text(value)


def _enum(value: Any, mapping: dict[str, str] | None = None) -> str:
    if value is None:
        return "-"
    raw = getattr(value, "value", None)
    if raw is None:
        raw = getattr(value, "name", None)
    raw = str(raw if raw is not None else value)
    if mapping:
        return mapping.get(raw.lower(), mapping.get(raw.upper(), raw))
    return raw


def _contains_rtl(text: str) -> bool:
    return any(
        0x0590 <= ord(ch) <= 0x08FF
        or 0xFB1D <= ord(ch) <= 0xFDFF
        or 0xFE70 <= ord(ch) <= 0xFEFF
        for ch in str(text or "")
    )


def _shape_rtl_text(text: str) -> str:
    value = str(text or "")
    if not _contains_rtl(value):
        return value
    if _arabic_reshaper is None or _bidi_get_display is None:
        raise RuntimeError(
            "Persian/Arabic PDF rendering requires either Pillow built with "
            "libraqm, or the 'arabic-reshaper' and 'python-bidi' packages. "
            "Install with: python -m pip install --upgrade arabic-reshaper python-bidi "
            "-- and if this is a PyInstaller build, make sure both are listed "
            "as hidden imports so they actually get bundled into the .exe."
        )
    reshaped = _arabic_reshaper.reshape(value)
    try:
        return _bidi_get_display(reshaped, base_dir="R")
    except TypeError:
        return _bidi_get_display(reshaped)


def _bbox(draw, text: str, font):
    value = _text(text, "")
    if _contains_rtl(value):
        if _RAQM_AVAILABLE:
            try:
                return draw.textbbox((0, 0), value, font=font, direction="rtl", language="fa")
            except Exception:
                pass
        return draw.textbbox((0, 0), _shape_rtl_text(value), font=font)
    return draw.textbbox((0, 0), value, font=font)


def _width(draw, text: str, font) -> int:
    box = _bbox(draw, text, font)
    return max(0, box[2] - box[0])


def _ellipsize(draw, text: str, font, max_width: int) -> str:
    value = _text(text, "")
    if not value or _width(draw, value, font) <= max_width:
        return value
    lo, hi = 0, len(value)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _width(draw, value[:mid].rstrip() + "…", font) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return (value[:lo].rstrip() + "…") if lo > 0 else "…"


def _wrap(draw, text: str, font, max_width: int, max_lines: int = 0) -> list[str]:
    value = _text(text, "")
    if not value:
        return []
    result: list[str] = []
    for paragraph in value.replace("\r", "").split("\n"):
        words = paragraph.split()
        if not words:
            continue
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if _width(draw, candidate, font) <= max_width or not current:
                current = candidate
            else:
                result.append(current)
                current = word
        result.append(current)
    if max_lines and len(result) > max_lines:
        result = result[:max_lines]
        result[-1] = result[-1].rstrip("…") + "…"
    return [_ellipsize(draw, line, font, max_width) for line in result]


def _draw_rtl(draw, xy, text, font, fill=TEXT, anchor="ra") -> None:
    value = _text(text, "")
    if not value:
        return
    if _RAQM_AVAILABLE:
        try:
            draw.text(xy, value, font=font, fill=fill, anchor=anchor, direction="rtl", language="fa")
            return
        except Exception:
            pass
    draw.text(xy, _shape_rtl_text(value), font=font, fill=fill, anchor=anchor)


def _draw_ltr(draw, xy, text, font, fill=TEXT, anchor="la") -> None:
    draw.text(xy, _text(text, ""), font=font, fill=fill, anchor=anchor)


# -----------------------------------------------------------------------------
# Table engine
# -----------------------------------------------------------------------------
class Col:
    """One table column. `key` is looked up in the row dict; a missing or
    empty value leaves the cell blank (used for write-in and signature columns)."""

    def __init__(self, header: str, weight: float, key: str | None = None):
        self.header = header
        self.weight = weight
        self.key = key


def _column_edges(cols: Sequence[Col]) -> list[tuple[int, int]]:
    """Returns (x_left, x_right) per column, first column at the RIGHT edge."""
    total = sum(c.weight for c in cols)
    edges = []
    right = TABLE_X + TABLE_W
    for i, c in enumerate(cols):
        w = TABLE_W * c.weight / total
        left = right - w
        edges.append((int(round(left)), int(round(right))))
        right = left
    # snap last column to the table's left edge
    edges[-1] = (TABLE_X, edges[-1][1])
    return edges


def _draw_cell_text(draw, x0, y0, x1, y1, text: str, start=21, minimum=12, bold=False, fill=TEXT, center=False):
    value = _text(text, "")
    if not value:
        return
    pad_x, pad_y = 8, 6
    aw = (x1 - x0) - 2 * pad_x
    ah = (y1 - y0) - 2 * pad_y
    chosen = None
    for size in range(start, minimum - 1, -1):
        f = _font(size, bold)
        lh = int(size * 1.45)
        lines = _wrap(draw, value, f, aw)
        if len(lines) * lh <= ah:
            chosen = (f, lh, lines)
            break
    if chosen is None:
        f = _font(minimum, bold)
        lh = int(minimum * 1.45)
        lines = _wrap(draw, value, f, aw, max_lines=max(1, ah // lh))
        chosen = (f, lh, lines)
    f, lh, lines = chosen
    top = y0 + ((y1 - y0) - len(lines) * lh) / 2
    for i, line in enumerate(lines):
        ly = int(top + i * lh)
        if center:
            _draw_rtl(draw, ((x0 + x1) // 2, ly), line, f, fill=fill, anchor="ma")
        else:
            _draw_rtl(draw, (x1 - pad_x, ly), line, f, fill=fill, anchor="ra")


def _page_header(draw, page, title_rtl: str, total: int, english: str):
    logo = None
    for path in (_resource_path("views", "gela-logo.png"), _resource_path("gela-logo.png"),
                 _resource_path("views", "gela-logo.gif"), _resource_path("gela-logo.gif")):
        if os.path.exists(path):
            try:
                logo = Image.open(path).convert("RGBA")
                logo.thumbnail((170, 50), Image.LANCZOS)
                break
            except Exception:
                logo = None
    if logo:
        page.paste(logo, (PAGE_W - MARGIN_X - logo.width, MARGIN_Y - 16), logo)
    _draw_rtl(draw, (PAGE_W // 2, MARGIN_Y - 14), title_rtl, _font(30, True), fill=NAVY, anchor="ma")
    _draw_ltr(draw, (MARGIN_X, MARGIN_Y + 8), f"{total:,} {english}", _font(14, True), fill=MUTED, anchor="lm")


def _draw_table_page(page, draw, cols: Sequence[Col], rows: list[dict[str, str]],
                     title: str, english: str, total: int, page_no: int, page_count: int):
    _page_header(draw, page, title, total, english)
    edges = _column_edges(cols)
    y_head = TABLE_Y
    y_body = TABLE_Y + TABLE_HEADER_H

    # header row
    for c, (xl, xr) in zip(cols, edges):
        draw.rectangle((xl, y_head, xr, y_body), fill=NAVY, outline=WHITE, width=1)
        _draw_cell_text(draw, xl, y_head, xr, y_body, c.header, start=19, minimum=12, bold=True, fill=WHITE, center=True)

    # body rows (always ROWS_PER_PAGE slots so empty lines can be written on)
    for r in range(ROWS_PER_PAGE):
        y0 = y_body + r * ROW_H
        y1 = y0 + ROW_H
        record = rows[r] if r < len(rows) else None
        fill = ZEBRA if r % 2 else WHITE
        for c, (xl, xr) in zip(cols, edges):
            draw.rectangle((xl, y0, xr, y1), fill=fill, outline=GRID, width=1)
            if record is not None and c.key:
                _draw_cell_text(draw, xl, y0, xr, y1, record.get(c.key, ""))

    # outer border
    draw.rectangle((TABLE_X, y_head, TABLE_X + TABLE_W, y_body + ROWS_PER_PAGE * ROW_H), outline=NAVY, width=3)

    # footer
    fy = PAGE_H - MARGIN_Y - FOOTER_H // 2 + 6
    _draw_ltr(draw, (PAGE_W // 2, fy), f"{page_no} / {page_count}", _font(15, True), fill=MUTED, anchor="mm")
    _draw_rtl(draw, (PAGE_W - MARGIN_X, fy), COMPANY_NAME, _font(15, True), fill=MUTED, anchor="rm")


def _chunks(items: Sequence[Any], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _finish_pdf(path: str, pages: Sequence[Image.Image]) -> str:
    if not pages:
        raise ValueError("هیچ رکوردی برای خروجی PDF وجود ندارد.")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    rgb = [p.convert("RGB") for p in pages]
    try:
        rgb[0].save(path, "PDF", resolution=DPI, save_all=True, append_images=rgb[1:])
    except PermissionError:
        raise PermissionError(
            "فایل در برنامه دیگری (مثلاً نمایشگر PDF) باز است یا اجازه نوشتن ندارید.\n"
            "فایل را ببندید یا نام دیگری انتخاب کنید."
        ) from None
    return path


def _export_table(items: list[Any], path: str, cols: Sequence[Col], to_row: Callable[[Any], dict[str, str]],
                  title: str, english: str) -> str:
    chunks = list(_chunks(items, ROWS_PER_PAGE))
    pages = []
    for n, chunk in enumerate(chunks, start=1):
        page = Image.new("RGB", (PAGE_W, PAGE_H), WHITE)
        draw = ImageDraw.Draw(page)
        _draw_table_page(page, draw, cols, [to_row(x) for x in chunk], title, english, len(items), n, len(chunks))
        pages.append(page)
    return _finish_pdf(path, pages)


def _join(*parts: Any, sep: str = "\n") -> str:
    return sep.join(p for p in (_blank(x) for x in parts) if p)


# -----------------------------------------------------------------------------
# Work Order
# -----------------------------------------------------------------------------
def _work_order_fields(wo):
    eq = getattr(wo, "equipment", None)
    dep = getattr(wo, "department", None)
    operator = getattr(wo, "operator", None)
    completers = list(getattr(wo, "completers", []) or getattr(wo, "completed_personnel", []) or [])
    personnel_text = "، ".join(_text(getattr(p, "full_name", ""), "") for p in completers if getattr(p, "full_name", None))
    type_map = {"corrective": "اصلاحی", "preventive": "پیشگیرانه", "emergency": "اضطراری", "inspection": "بازرسی", "pm": "PM"}
    priority_map = {"low": "کم", "medium": "متوسط", "high": "بالا", "urgent": "فوری"}
    status_map = {"pending_approval": "در انتظار تایید", "pending": "در انتظار", "in_progress": "در حال انجام", "finish_requested": "درخواست اتمام", "completed": "تکمیل شده", "approved": "تایید شده", "rejected": "رد شده"}
    raw_cost = float(getattr(wo, "manual_cost", 0) or 0)
    return {
        "id": getattr(wo, "id", "-"),
        "title": getattr(wo, "title", ""),
        "equipment": getattr(eq, "name", "-") if eq else "-",
        "equipment_code": getattr(eq, "code", "-") if eq else "-",
        "department": getattr(dep, "name", "-") if dep else "-",
        "type": _enum(getattr(wo, "type", None), type_map),
        "priority": _enum(getattr(wo, "priority", None), priority_map),
        "status": _enum(getattr(wo, "status", None), status_map),
        "scheduled": _jdate(getattr(wo, "scheduled_date", None), True),
        "deadline": _jdate(getattr(wo, "deadline", None), True),
        "failure": _jdate(getattr(wo, "failure_report_time", None), True),
        "start": _jdate(getattr(wo, "start_time", None), True),
        "end": _jdate(getattr(wo, "end_time", None), True),
        "operator": getattr(operator, "full_name", "-") if operator else "-",
        "description": getattr(wo, "description", "") or "",
        "operator_notes": getattr(wo, "operator_notes", "") or "",
        "cost": f"{raw_cost:,.0f}" if raw_cost else "",
        "cost_description": getattr(wo, "cost_description", "") or "",
        "delay_minutes": getattr(wo, "delay_minutes", "") or "",
        "delay_reason": getattr(wo, "delay_reason", "") or "",
        "personnel": personnel_text,
    }


WORK_ORDER_COLS = [
    Col("شماره", 0.55, "id"),
    Col("تجهیز", 1.6, "equipment"),
    Col("واحد", 1.1, "department"),
    Col("شرح کار", 2.6, "description"),
    Col("نوع / اولویت", 1.0, "type"),
    Col("زمان برنامه / مهلت", 1.75, "dates"),
    Col("پرسنل انجام‌دهنده", 1.3, "personnel"),
    Col("شروع", 1.0, "start"),
    Col("پایان", 1.0, "end"),
    Col("گزارش انجام کار", 1.7, "report"),
    Col("امضاء پرسنل", 1.3),
    Col("امضاء سرپرست", 1.3),
]


def _work_order_row(wo) -> dict[str, str]:
    f = _work_order_fields(wo)
    return {
        "id": _text(f["id"]),
        "equipment": _join(f["equipment"], f["equipment_code"]),
        "department": _blank(f["department"]),
        "description": _join(f["title"], f["description"]),
        "type": _join(f["type"], f["priority"]),
        "dates": _join(_blank(f["scheduled"]), _blank(f["deadline"])),
        "personnel": f["personnel"],
        "start": _blank(f["start"]),
        "end": _blank(f["end"]),
        "report": _join(f["operator_notes"], f["cost_description"], f["delay_reason"]),
    }


def export_work_orders_pdf(work_orders: Iterable[Any], path: str) -> str:
    items = list(work_orders or [])
    if not items:
        raise ValueError("هیچ دستورکاری برای خروجی PDF انتخاب نشده است.")
    return _export_table(items, path, WORK_ORDER_COLS, _work_order_row,
                         "فهرست دستور کار", "WORK ORDERS")


# -----------------------------------------------------------------------------
# Preventive Maintenance
# -----------------------------------------------------------------------------
def _pm_fields(pm):
    if isinstance(pm, dict):
        get = lambda k, d=None: pm.get(k, d)
    else:
        get = lambda k, d=None: getattr(pm, k, d)
    frequency_map = {"daily": "روزانه", "weekly": "هفتگی", "monthly": "ماهانه", "quarterly": "سه‌ماهه", "biannual": "شش‌ماهه", "annual": "سالانه", "custom": "سفارشی"}
    return {
        "id": get("id", "-"),
        "title": get("title", ""),
        "equipment": get("equipment_name", "-"),
        "equipment_code": get("equipment_code", "-"),
        "department": get("department_name", "-") or "-",
        "frequency": frequency_map.get(str(get("frequency", "")).lower(), _text(get("frequency", "-"))),
        "interval": get("interval_days", "-"),
        "last_done": _jdate(get("last_done", None)),
        "next_due": _jdate(get("next_due_dt", None) or get("next_due", None)),
        "status": "غیرفعال" if not get("is_active", True) else "عقب‌افتاده" if get("is_overdue", False) else "این هفته" if (get("days_until") is not None and 0 <= get("days_until") <= 7) else "به‌موقع",
        "duration": get("estimated_duration", "-"),
        "checklist": get("checklist", "") or "",
        "notes": get("notes", "") or "",
        "parts": get("parts_required", "") or "",
    }


PM_COLS = [
    Col("شماره", 0.55, "id"),
    Col("تجهیز", 1.6, "equipment"),
    Col("واحد", 1.1, "department"),
    Col("عنوان / چک لیست", 2.6, "task"),
    Col("آخرین انجام", 1.1, "last_done"),
    Col("تاریخ انجام", 1.1),
    Col("یادداشت / توضیحات", 6.5, "notes"),
    Col("امضاء تکنسین", 1.3),
]

def _pm_row(pm) -> dict[str, str]:
    f = _pm_fields(pm)
    return {
        "id": _text(f["id"]),
        "equipment": _join(f["equipment"], f["equipment_code"]),
        "department": _blank(f["department"]),
        "task": _join(f["title"], f["checklist"]),
        "last_done": _blank(f["last_done"]),
        "notes": f["notes"],
    }


def export_pm_pdf(pm_list: Iterable[Any], path: str) -> str:
    items = list(pm_list or [])
    if not items:
        raise ValueError("هیچ برنامه PM برای خروجی PDF انتخاب نشده است.")
    # "12 PM SCHEDULES" in the header: "12 PM" alone read like a time of day
    return _export_table(items, path, PM_COLS, _pm_row, "فهرست برنامه PM", "PM SCHEDULES")


# -----------------------------------------------------------------------------
# Repair Request
# -----------------------------------------------------------------------------
def _repair_request_fields(record):
    completion = getattr(record, "completion", None)
    assigned = getattr(record, "assigned_personnel", None)
    assigned_code = _text(getattr(assigned, "personnel_code", ""), "")
    assigned_name = _text(getattr(assigned, "full_name", ""), "")
    assigned_text = " - ".join(p for p in (assigned_code, assigned_name) if p and p != "-")

    people = []
    if completion:
        for person in list(getattr(completion, "personnel", []) or []):
            code = _text(getattr(person, "personnel_code", ""), "")
            name = _text(getattr(person, "full_name", ""), "")
            people.append(f"{code} - {name}" if code and name else (name or code or "-"))

    raw_cost = float(getattr(completion, "manual_cost", 0) or 0) if completion else 0
    return {
        "id": getattr(record, "id", "-"),
        "unit": getattr(record, "requesting_unit", ""),
        "equipment": getattr(record, "equipment_name", ""),
        "breakdown": _jdate(getattr(record, "breakdown_datetime", None), True),
        "operator": getattr(record, "operator_name", ""),
        "requester": getattr(record, "requester_name", ""),
        "description": getattr(record, "request_description", "") or "",
        "status": "انجام شده" if completion else "در انتظار انجام",
        "assigned_personnel": assigned_text,
        "personnel": "، ".join(people),
        "completion": _jdate(getattr(completion, "completion_datetime", None), True) if completion else "",
        "finish_notes": getattr(completion, "finish_notes", "") if completion else "",
        "cost": f"{raw_cost:,.0f}" if raw_cost else "",
        "delay": getattr(completion, "delay_minutes", "") if completion else "",
    }


REPAIR_COLS = [
    Col("شماره", 0.55, "id"),
    Col("واحد متقاضی", 1.1, "unit"),
    Col("تجهیز", 1.5, "equipment"),
    Col("زمان اعلام خرابی", 1.3, "breakdown"),
    Col("شرح عیب", 2.4, "description"),
    Col("درخواست‌دهنده / اپراتور", 1.3, "people"),
    Col("پرسنل مسئول", 1.3, "assigned"),
    Col("اقدامات انجام‌شده", 2.0, "finish_notes"),
    Col("زمان اتمام", 1.2, "completion"),
    Col("تاخیر / هزینه", 1.0, "delay_cost"),
    Col("امضاء پرسنل", 1.3),
    Col("امضاء سرپرست", 1.3),
]


def _repair_row(record) -> dict[str, str]:
    f = _repair_request_fields(record)
    delay = f'{f["delay"]} دقیقه' if _blank(f["delay"]) else ""
    return {
        "id": _text(f["id"]),
        "unit": _blank(f["unit"]),
        "equipment": _blank(f["equipment"]),
        "breakdown": _blank(f["breakdown"]),
        "description": f["description"],
        "people": _join(f["requester"], f["operator"]),
        "assigned": f["assigned_personnel"],
        "finish_notes": _blank(f["finish_notes"]),
        "completion": _blank(f["completion"]),
        "delay_cost": _join(delay, f["cost"]),
    }


def export_repair_requests_pdf(records: Iterable[Any], path: str) -> str:
    items = list(records or [])
    if not items:
        raise ValueError("هیچ درخواست تعمیراتی برای خروجی PDF انتخاب نشده است.")
    return _export_table(items, path, REPAIR_COLS, _repair_row,
                         "فهرست درخواست تعمیرات", "REPAIR REQUESTS")


# -----------------------------------------------------------------------------
# Diagnostics
# -----------------------------------------------------------------------------
def get_persian_pdf_rendering_status() -> dict[str, Any]:
    """Call at app startup and log the result so a broken RTL setup shows up
    immediately instead of as garbled text on a customer's machine."""
    return {
        "pillow_raqm": bool(_RAQM_AVAILABLE),
        "arabic_reshaper": bool(_arabic_reshaper is not None),
        "python_bidi": bool(_bidi_get_display is not None),
        "rtl_rendering_ok": bool(_RAQM_AVAILABLE or (_arabic_reshaper is not None and _bidi_get_display is not None)),
        "font_regular": FONT_REGULAR,
        "font_bold": FONT_BOLD,
        "a4_mm": (A4_W_MM, A4_H_MM),
        "a4_pixels": (PAGE_W, PAGE_H),
        "rows_per_page": ROWS_PER_PAGE,
        "row_height_px": ROW_H,
        "dpi": DPI,
    }