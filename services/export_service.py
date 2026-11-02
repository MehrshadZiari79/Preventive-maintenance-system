# services/export_service.py
"""
PM System - Excel Export Service
================================

Centralized Excel export layer.

Important compatibility rules
-----------------------------

Existing callers remain valid:

    export_xxx_excel(data, path)

New callers may optionally provide:

    selected_columns=[...]

The export dialog receives its column definitions directly from this
module, so UI code does not need to know how Excel files are constructed.

Current personnel / department workflow
---------------------------------------

Work Order creation:
    Equipment
    Department
    Scheduled date/time

Finish request:
    Work Order Department
        ->
    Personnel belonging to that Department
        ->
    completed_by_personnel_id

Therefore Work Order exports must distinguish:

    Department
    Actual completed Personnel

The legacy User technician fields are still retained because historical
records may contain them.
"""


from datetime import (
    datetime,
    date,
)

from typing import (
    Any,
    Iterable,
    Optional,
)

import jdatetime

from openpyxl import Workbook

from openpyxl.styles import (
    Font,
    PatternFill,
    Alignment,
    Border,
    Side,
)

from openpyxl.utils import (
    get_column_letter,
)
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


# ============================================================================
# CONSTANTS
# ============================================================================

COMPANY_NAME = "شرکت گلا — آمل"

C_PRIMARY = "1A2A44"
C_RED = "DC2626"
C_WHITE = "FFFFFF"
C_LIGHT = "F4F6F9"
C_DARK = "202124"
C_WARNING = "D97706"
C_SUCCESS = "16A34A"
C_BORDER = "BBBBBB"
C_DATA_BORDER = "DDDDDD"


# ============================================================================
# DATE HELPERS
# ============================================================================

def _now_jalali() -> str:
    """Return current date/time in Jalali format."""

    jd = jdatetime.datetime.fromgregorian(datetime=tehran_now())

    return jd.strftime(
        "%Y/%m/%d %H:%M"
    )


def _parse_date(
    dt: Any,
) -> Optional[date]:
    """
    Convert common date/datetime/string values into datetime.date.

    Returns None when conversion is not possible.
    """

    if dt is None:
        return None

    if isinstance(
        dt,
        datetime,
    ):
        return dt.date()

    if isinstance(
        dt,
        date,
    ):
        return dt

    if isinstance(
        dt,
        str,
    ):

        value = dt.strip()

        if not value:
            return None

        formats = (
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
        )

        for fmt in formats:

            try:

                return datetime.strptime(
                    value,
                    fmt,
                ).date()

            except ValueError:

                continue

    if hasattr(
        dt,
        "date",
    ):

        try:

            converted = dt.date()

            if isinstance(
                converted,
                datetime,
            ):

                return converted.date()

            if isinstance(
                converted,
                date,
            ):

                return converted

        except Exception:

            pass

    return None


def _to_jalali_str(
    dt: Any,
    fmt: str = "%Y/%m/%d",
) -> str:
    """
    Convert Gregorian date/datetime to Jalali text.

    Supports date-only and datetime formats.
    """

    if dt is None:
        return "—"

    if isinstance(
        dt,
        datetime,
    ):

        try:

            jdt = (
                jdatetime.datetime.fromgregorian(
                    datetime=dt
                )
            )

            return jdt.strftime(
                fmt
            )

        except Exception:

            return str(dt)

    parsed = _parse_date(
        dt
    )

    if parsed is None:
        return str(dt)

    try:

        jdt = (
            jdatetime.date.fromgregorian(
                date=parsed
            )
        )

        return jdt.strftime(
            fmt
        )

    except Exception:

        return str(dt)


# ============================================================================
# GENERAL HELPERS
# ============================================================================

def _safe_text(
    value: Any,
    default: str = "",
) -> str:
    """
    Return a safe string representation.
    """

    if value is None:
        return default

    return str(
        value
    )


def _format_number(
    value: Any,
    decimals: int = 2,
) -> str:
    """
    Format numeric values.
    """

    if value is None:
        return ""

    try:

        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return str(value)

    return (
        f"{number:,.{decimals}f}"
    )


def _format_cost(
    value: Any,
) -> str:
    """
    Format monetary values.
    """

    if value is None:
        return "0.00"

    try:

        return f"{float(value):,.2f}"

    except (
        TypeError,
        ValueError,
    ):

        return str(value)


def _enum_name(
    value: Any,
) -> str:
    """
    Safely return Enum.name or string.
    """

    if value is None:
        return ""

    name = getattr(
        value,
        "name",
        None,
    )

    if name is not None:
        return str(name)

    return str(
        value
    )


def _enum_value(
    value: Any,
) -> str:
    """
    Safely return Enum.value or string.
    """

    if value is None:
        return ""

    enum_value = getattr(
        value,
        "value",
        None,
    )

    if enum_value is not None:
        return str(
            enum_value
        )

    return str(
        value
    )


def _relationship_name(
    relationship: Any,
    default: str = "—",
) -> str:
    """
    Safely obtain a person's/user's full name.
    """

    if relationship is None:
        return default

    full_name = getattr(
        relationship,
        "full_name",
        None,
    )

    if full_name:
        return str(
            full_name
        )

    username = getattr(
        relationship,
        "username",
        None,
    )

    if username:
        return str(
            username
        )

    return default


def _object_value(obj: Any, key: str, default: Any = None) -> Any:
    """Safely read a value from either an ORM object or a dictionary."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _department_name(
    department: Any,
) -> str:
    """Safely obtain Department.name from ORM objects or dictionaries."""
    name = _object_value(department, "name", None)
    return str(name) if name else "—"


def _personnel_name(
    personnel: Any,
) -> str:
    """
    Safely obtain Personnel.full_name.
    """

    if personnel is None:
        return "—"

    name = getattr(
        personnel,
        "full_name",
        None,
    )

    return (
        str(name)
        if name
        else "—"
    )


def _personnel_code(
    personnel: Any,
) -> str:
    """
    Safely obtain Personnel.personnel_code.
    """

    if personnel is None:
        return "—"

    code = getattr(
        personnel,
        "personnel_code",
        None,
    )

    return (
        str(code)
        if code
        else "—"
    )


# ============================================================================
# EXCEL STYLE HELPERS
# ============================================================================

def _xl_header_style(
    ws,
    row: int,
    cols: int,
    title: str,
) -> None:

    if cols < 1:
        return

    # ------------------------------------------------------------------------
    # Company
    # ------------------------------------------------------------------------

    ws.merge_cells(
        start_row=row,
        start_column=1,
        end_row=row,
        end_column=cols,
    )

    company_cell = ws.cell(
        row=row,
        column=1,
        value=COMPANY_NAME,
    )

    company_cell.font = Font(
        name="Tahoma",
        bold=True,
        size=11,
        color=C_WHITE,
    )

    company_cell.fill = PatternFill(
        start_color=C_PRIMARY,
        end_color=C_PRIMARY,
        fill_type="solid",
    )

    company_cell.alignment = Alignment(
        horizontal="center",
        vertical="center",
    )

    ws.row_dimensions[
        row
    ].height = 24

    # ------------------------------------------------------------------------
    # Title
    # ------------------------------------------------------------------------

    ws.merge_cells(
        start_row=row + 1,
        start_column=1,
        end_row=row + 1,
        end_column=cols,
    )

    title_cell = ws.cell(
        row=row + 1,
        column=1,
        value=title,
    )

    title_cell.font = Font(
        name="Tahoma",
        bold=True,
        size=13,
        color=C_PRIMARY,
    )

    title_cell.fill = PatternFill(
        start_color=C_LIGHT,
        end_color=C_LIGHT,
        fill_type="solid",
    )

    title_cell.alignment = Alignment(
        horizontal="center",
        vertical="center",
    )

    ws.row_dimensions[
        row + 1
    ].height = 28

    # ------------------------------------------------------------------------
    # Creation date
    # ------------------------------------------------------------------------

    ws.merge_cells(
        start_row=row + 2,
        start_column=1,
        end_row=row + 2,
        end_column=cols,
    )

    date_cell = ws.cell(
        row=row + 2,
        column=1,
        value=(
            f"تاریخ تهیه: "
            f"{_now_jalali()}"
        ),
    )

    date_cell.font = Font(
        name="Tahoma",
        size=9,
        color=C_DARK,
    )

    date_cell.fill = PatternFill(
        start_color=C_LIGHT,
        end_color=C_LIGHT,
        fill_type="solid",
    )

    date_cell.alignment = Alignment(
        horizontal="center",
        vertical="center",
    )

    ws.row_dimensions[
        row + 2
    ].height = 18


def _xl_col_header(
    ws,
    row: int,
    headers: list[str],
) -> None:

    thin = Side(
        style="thin",
        color=C_BORDER,
    )

    border = Border(
        left=thin,
        right=thin,
        top=thin,
        bottom=thin,
    )

    for col, text in enumerate(
        headers,
        1,
    ):

        cell = ws.cell(
            row=row,
            column=col,
            value=text,
        )

        cell.font = Font(
            name="Tahoma",
            bold=True,
            size=10,
            color=C_WHITE,
        )

        cell.fill = PatternFill(
            start_color=C_PRIMARY,
            end_color=C_PRIMARY,
            fill_type="solid",
        )

        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )

        cell.border = border

    ws.row_dimensions[
        row
    ].height = 22


def _xl_data_row(
    ws,
    row: int,
    values: list[Any],
    zebra: bool = False,
) -> None:

    thin = Side(
        style="thin",
        color=C_DATA_BORDER,
    )

    border = Border(
        left=thin,
        right=thin,
        top=thin,
        bottom=thin,
    )

    bg = (
        C_LIGHT
        if zebra
        else C_WHITE
    )

    for col, value in enumerate(
        values,
        1,
    ):

        cell = ws.cell(
            row=row,
            column=col,
            value=value,
        )

        cell.fill = PatternFill(
            start_color=bg,
            end_color=bg,
            fill_type="solid",
        )

        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )

        cell.border = border

    ws.row_dimensions[
        row
    ].height = 20


def _xl_auto_width(
    ws,
    min_w: int = 10,
    max_w: int = 28,
) -> None:
    """Fit columns for practical A4 printing without creating oversized sheets."""

    for col in ws.columns:
        if not col:
            continue

        max_len = 0
        col_letter = get_column_letter(col[0].column)

        for cell in col:
            if cell.value is None:
                continue

            lines = str(cell.value).split("\n")
            longest = max((len(line) for line in lines), default=0)
            max_len = max(max_len, longest)

        ws.column_dimensions[col_letter].width = max(
            min_w,
            min(max_len + 2, max_w),
        )


def _xl_apply_a4_table_setup(
    ws,
    end_row: int,
    orientation: str = "portrait",
) -> None:
    """Apply consistent A4 print settings to tabular exports."""

    last_col = get_column_letter(max(1, ws.max_column))
    ws.sheet_view.rightToLeft = True
    ws.sheet_view.showGridLines = False
    ws.page_setup.paperSize = "9"
    ws.page_setup.orientation = orientation
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins.left = 0.20
    ws.page_margins.right = 0.20
    ws.page_margins.top = 0.28
    ws.page_margins.bottom = 0.35
    ws.page_margins.header = 0.10
    ws.page_margins.footer = 0.15
    ws.print_options.horizontalCentered = True
    ws.sheet_view.zoomScale = 90
    ws.print_area = f"A1:{last_col}{max(1, end_row)}"
    ws.print_title_rows = "1:4"
    if end_row >= 5:
        ws.auto_filter.ref = f"A4:{last_col}{end_row}"
    ws.oddFooter.center.text = "صفحه &P از &N"
    ws.oddFooter.center.size = 8
    ws.oddFooter.center.font = FORM_FONT if "FORM_FONT" in globals() else "Tahoma"
    ws.oddFooter.right.text = "سیستم نگهداری و تعمیرات"
    ws.oddFooter.right.size = 8
    ws.oddFooter.right.font = FORM_FONT if "FORM_FONT" in globals() else "Tahoma"


def _prepare_workbook(
    title: str,
    sheet_name: str,
    headers: list[str],
):
    """Create a consistent A4 workbook for list-style exports; printing defaults to portrait."""

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]
    ws.sheet_view.rightToLeft = True
    ws.sheet_view.showGridLines = False

    # A compact A4 grid. Actual widths are refined after data is written.
    for col_idx in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 14

    _xl_header_style(ws, 1, len(headers), title)
    _xl_col_header(ws, 4, headers)
    return wb, ws


# ============================================================================
# COLUMN SELECTION
# ============================================================================

def _normalize_selected_columns(
    available_keys: list[str],
    selected_columns: Optional[
        Iterable[str]
    ],
) -> list[str]:

    if selected_columns is None:
        return list(
            available_keys
        )

    selected_set = set(
        selected_columns
    )

    return [
        key
        for key in available_keys
        if key in selected_set
    ]


def _build_selected_rows(
    rows: list[dict],
    column_definitions: list[
        tuple[str, str]
    ],
    selected_columns: Optional[
        Iterable[str]
    ],
):

    available_keys = [
        key
        for key, _label
        in column_definitions
    ]

    selected_keys = (
        _normalize_selected_columns(
            available_keys,
            selected_columns,
        )
    )

    labels = dict(
        column_definitions
    )

    headers = [
        labels[key]
        for key in selected_keys
    ]

    values = []

    for row in rows:

        values.append(
            [
                row.get(
                    key,
                    "",
                )
                for key in selected_keys
            ]
        )

    return (
        headers,
        values,
    )


# ============================================================================
# PUBLIC COLUMN DEFINITIONS
# ============================================================================

EQUIPMENT_COLUMNS = [
    ("code", "کد"),
    ("name", "نام تجهیز"),
    ("category", "دسته‌بندی"),
    ("manufacturer", "سازنده"),
    ("model", "مدل"),
    ("location", "موقعیت"),
    ("status", "وضعیت"),
    ("installation_date", "تاریخ نصب"),
    ("updated_at", "آخرین بروزرسانی"),
    ("length", "طول (متر)"),
    ("width", "عرض (متر)"),
    ("diameter", "قطر (متر)"),
    ("height", "ارتفاع (متر)"),
    ("volume", "حجم (متر³)"),
    ("weight", "وزن (کیلوگرم)"),
    ("specifications", "مشخصات فنی"),
    ("notes", "توضیحات"),
]


# ----------------------------------------------------------------------------
# PM
# ----------------------------------------------------------------------------
#
# NEW:
#     department
#     department_id
#
# Legacy technician_name remains available because old PM data may still
# contain it. New PM workflow does not assign an actual worker at creation.
#

PM_COLUMNS = [
    ("id", "شناسه"),
    ("title", "عنوان برنامه"),
    ("equipment_name", "تجهیز"),
    ("equipment_code", "کد تجهیز"),
    ("department_id", "شناسه دپارتمان"),
    ("department_name", "دپارتمان انجام‌دهنده"),
    ("frequency", "دوره تناوب"),
    ("interval_days", "بازه (روز)"),
    ("last_done", "آخرین انجام"),
    ("next_due", "سررسید بعدی"),
    ("days_until", "روز مانده"),
    ("status", "وضعیت"),
]


# ----------------------------------------------------------------------------
# WORK ORDER
# ----------------------------------------------------------------------------
#
# NEW workflow:
#
#     department_id
#     department_name
#     completed_by_personnel_id
#     completed_by_personnel_name
#
# Legacy User technician fields remain exportable for historical records,
# but they are clearly labeled as legacy application-user assignments.
#

WORK_ORDER_COLUMNS = [
    ("id", "شناسه"),
    ("title", "عنوان"),
    ("equipment_name", "تجهیز"),
    ("equipment_id", "شناسه تجهیز"),
    ("equipment_code", "کد تجهیز"),
    ("department_id", "شناسه دپارتمان"),
    ("department_name", "دپارتمان انجام‌دهنده"),
    ("type", "نوع"),
    ("priority", "اولویت"),
    ("completed_by_personnel_name", "پرسنل انجام‌دهنده"),
    ("operator", "اپراتور تحویل‌گیرنده"),
    ("failure_report_time", "ساعت اعلام خرابی"),
    ("status", "وضعیت"),
    ("scheduled_date", "تاریخ برنامه"),
    ("start_time", "شروع تعمیر"),
    ("end_time", "پایان تعمیر"),
    ("deadline", "ددلاین"),
    ("operator_signature", "امضای اپراتور"),
    ("description", "توضیحات تعمیر"),
    ("parts_used", "قطعات مصرفی"),
    ("delay_minutes", "دقایق تأخیر"),
    ("delay_reason", "علت تأخیر"),
    ("manual_cost", "هزینه دستی (ریال)"),
    ("cost_description", "توضیح هزینه"),
]


INSPECTION_COLUMNS = [
    ("id", "شناسه"),
    ("template_name", "قالب بازرسی"),
    ("equipment_name", "تجهیز"),
    ("inspector_name", "بازرس"),
    ("status", "وضعیت"),
    ("overall_result", "نتیجه کلی"),
    ("started_at", "تاریخ شروع"),
    ("completed_at", "تاریخ پایان"),
    ("notes", "یادداشت"),
]


SPARE_PART_COLUMNS = [
    ("id", "شناسه"),
    ("part_number", "شماره قطعه"),
    ("name", "نام قطعه"),
    ("category", "دسته‌بندی"),
    ("current_stock", "موجودی فعلی"),
    ("min_stock", "حداقل موجودی"),
    ("unit", "واحد"),
    ("unit_price", "قیمت واحد"),
    ("location", "موقعیت"),
    ("supplier", "تامین‌کننده"),
    ("description", "توضیحات"),
]


# ============================================================================
# EQUIPMENT EXPORT
# ============================================================================

def export_equipment_excel(
    equipment_list: list[dict],
    path: str,
    selected_columns: Optional[
        Iterable[str]
    ] = None,
) -> str:

    status_fa = {
        "operational": "عملیاتی",
        "maintenance": "در تعمیر",
        "breakdown": "خراب",
        "inactive": "غیرفعال",
    }

    prepared_rows = []

    for eq in (
        equipment_list
        or []
    ):

        prepared_rows.append(
            {
                "code":
                    eq.get(
                        "code",
                        "",
                    ),

                "name":
                    eq.get(
                        "name",
                        "",
                    ),

                "category":
                    eq.get(
                        "category",
                        "",
                    ),

                "manufacturer":
                    eq.get(
                        "manufacturer",
                        "",
                    ),

                "model":
                    eq.get(
                        "model",
                        "",
                    ),

                "location":
                    eq.get(
                        "location",
                        "",
                    ),

                "status":
                    status_fa.get(
                        eq.get(
                            "status",
                            "",
                        ),
                        eq.get(
                            "status",
                            "",
                        ),
                    ),

                "installation_date":
                    _to_jalali_str(
                        eq.get(
                            "installation_date"
                        )
                    ),

                "updated_at":
                    _to_jalali_str(
                        eq.get(
                            "updated_at"
                        ),
                        fmt="%Y/%m/%d %H:%M",
                    ),

                "length":
                    _format_number(
                        eq.get(
                            "length"
                        )
                    ),

                "width":
                    _format_number(
                        eq.get(
                            "width"
                        )
                    ),

                "diameter":
                    _format_number(
                        eq.get(
                            "diameter"
                        )
                    ),

                "height":
                    _format_number(
                        eq.get(
                            "height"
                        )
                    ),

                "volume":
                    _format_number(
                        eq.get(
                            "volume"
                        )
                    ),

                "weight":
                    _format_number(
                        eq.get(
                            "weight"
                        )
                    ),

                "specifications":
                    eq.get(
                        "specifications",
                        "",
                    )
                    or "",

                "notes":
                    eq.get(
                        "notes",
                        "",
                    )
                    or "",
            }
        )

    headers, rows = (
        _build_selected_rows(
            prepared_rows,
            EQUIPMENT_COLUMNS,
            selected_columns,
        )
    )

    if not headers:

        raise ValueError(
            "حداقل یک ستون برای خروجی تجهیزات باید انتخاب شود."
        )

    wb, ws = _prepare_workbook(
        "لیست تجهیزات",
        "Equipment",
        headers,
    )

    for index, values in enumerate(
        rows
    ):

        _xl_data_row(
            ws,
            5 + index,
            values,
            zebra=(
                index % 2 == 1
            ),
        )

    _xl_auto_width(ws)
    footer_row = 5 + len(rows) + 1
    _merge(ws, f"A{footer_row}:J{footer_row}", "توضیحات تکمیلی", FORM_SECTION_FILL, _font(10, True, C_PRIMARY), _rtl(), _border())
    _merge(ws, f"A{footer_row+1}:J{footer_row+2}", "", FORM_WRITE_FILL, _font(10), _rtl("top"), _border())
    ws.row_dimensions[footer_row+1].height = 24
    ws.row_dimensions[footer_row+2].height = 24
    sig_end = _add_table_signature_footer(ws, footer_row + 3)
    _xl_apply_a4_table_setup(ws, sig_end, A4_DEFAULT_ORIENTATION)
    ws.freeze_panes = "A5"

    wb.save(path)
    return path


# ============================================================================

# ============================================================================
# PROFESSIONAL PRINTABLE FORMS + CONSOLIDATED REPORT EXPORT
# ============================================================================

FORM_FONT = "Tahoma"
FORM_TITLE_SIZE = 17
FORM_LABEL_SIZE = 10
FORM_VALUE_SIZE = 11
FORM_SMALL_SIZE = 9
FORM_BORDER_COLOR = "AAB4C2"
FORM_HEADER_FILL = "1A2A44"
FORM_SECTION_FILL = "EAF0F6"
FORM_LABEL_FILL = "F5F7FA"
FORM_WRITE_FILL = "FFFFFF"
FORM_WARNING_FILL = "FFF4E5"
FORM_SUCCESS_FILL = "EAF7EE"
FORM_DANGER_FILL = "FCEBEC"
FORM_ACCENT_FILL = "DDE7F2"

A4_LANDSCAPE_ORIENTATION = "landscape"  # legacy compatibility constant
A4_PORTRAIT_ORIENTATION = "portrait"
A4_DEFAULT_ORIENTATION = A4_PORTRAIT_ORIENTATION


def _selected_set(selected_columns, available):
    return set(_normalize_selected_columns(available, selected_columns))


def _legacy_technicians_display(wo):
    names = []
    primary = getattr(getattr(wo, "technician", None), "full_name", None)
    if primary:
        names.append(str(primary))
    try:
        for user in getattr(wo, "technicians", None) or []:
            name = getattr(user, "full_name", None) or getattr(user, "username", None)
            if name and name not in names:
                names.append(str(name))
    except Exception:
        pass
    return ", ".join(names) if names else "—"


def _repair_value(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _unique_sheet_name(wb, base):
    base = str(base or "Sheet")[:31]
    name = base
    n = 2
    while name in wb.sheetnames:
        suffix = f"-{n}"
        name = base[:31 - len(suffix)] + suffix
        n += 1
    return name


def _fill(color):
    return PatternFill(start_color=color, end_color=color, fill_type="solid")


def _border(color=FORM_BORDER_COLOR, style="thin"):
    side = Side(style=style, color=color)
    return Border(left=side, right=side, top=side, bottom=side)


def _font(size=FORM_VALUE_SIZE, bold=False, color=C_DARK):
    return Font(name=FORM_FONT, size=size, bold=bold, color=color)


def _rtl(vertical="center", wrap=True, horizontal="right"):
    return Alignment(horizontal=horizontal, vertical=vertical, wrap_text=wrap, readingOrder=2)


def _center():
    return Alignment(horizontal="center", vertical="center", readingOrder=2)


def _merge(ws, rng, value, fill=None, font=None, alignment=None, border=None):
    """Merge a range while keeping the ENTIRE rectangle visibly closed."""
    from openpyxl.utils.cell import range_boundaries

    min_col, min_row, max_col, max_row = range_boundaries(rng)

    # Style every cell first. This prevents the common openpyxl merged-cell
    # problem where only the top-left cell keeps the border.
    if fill:
        fill_obj = _fill(fill)
        for r in range(min_row, max_row + 1):
            for c in range(min_col, max_col + 1):
                ws.cell(r, c).fill = fill_obj

    if border:
        # Give every underlying cell the full border before the merge.
        for r in range(min_row, max_row + 1):
            for c in range(min_col, max_col + 1):
                ws.cell(r, c).border = border

    ws.merge_cells(rng)

    anchor = ws.cell(min_row, min_col)
    anchor.value = value

    if fill:
        anchor.fill = _fill(fill)
    if font:
        anchor.font = font
    if alignment:
        anchor.alignment = alignment

    if border:
        # Restore the outer perimeter explicitly after merging.
        # Left edge
        for r in range(min_row, max_row + 1):
            ws.cell(r, min_col).border = Border(
                left=border.left,
                right=ws.cell(r, min_col).border.right,
                top=ws.cell(r, min_col).border.top,
                bottom=ws.cell(r, min_col).border.bottom,
            )

        # Right edge
        for r in range(min_row, max_row + 1):
            ws.cell(r, max_col).border = Border(
                left=ws.cell(r, max_col).border.left,
                right=border.right,
                top=ws.cell(r, max_col).border.top,
                bottom=ws.cell(r, max_col).border.bottom,
            )

        # Top edge
        for c in range(min_col, max_col + 1):
            ws.cell(min_row, c).border = Border(
                left=ws.cell(min_row, c).border.left,
                right=ws.cell(min_row, c).border.right,
                top=border.top,
                bottom=ws.cell(min_row, c).border.bottom,
            )

        # Bottom edge
        for c in range(min_col, max_col + 1):
            ws.cell(max_row, c).border = Border(
                left=ws.cell(max_row, c).border.left,
                right=ws.cell(max_row, c).border.right,
                top=ws.cell(max_row, c).border.top,
                bottom=border.bottom,
            )

        # Keep the anchor fully bordered too.
        anchor.border = border

    return anchor


def _apply_print_setup(ws, print_area, orientation=A4_DEFAULT_ORIENTATION,
                       fit_height=1):
    ws.sheet_view.rightToLeft = True
    ws.sheet_view.showGridLines = False
    ws.page_setup.paperSize = "9"
    ws.page_setup.orientation = orientation
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = fit_height
    ws.page_setup.scale = None
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins.left = 0.16
    ws.page_margins.right = 0.16
    ws.page_margins.top = 0.20
    ws.page_margins.bottom = 0.24
    ws.page_margins.header = 0.10
    ws.page_margins.footer = 0.15
    ws.print_options.horizontalCentered = True
    ws.print_options.verticalCentered = False
    ws.sheet_view.zoomScale = 90
    ws.print_area = print_area
    ws.oddFooter.center.text = "صفحه &P از &N"
    ws.oddFooter.center.size = 8
    ws.oddFooter.center.font = FORM_FONT
    ws.oddFooter.right.text = "سیستم نگهداری و تعمیرات"
    ws.oddFooter.right.size = 8
    ws.oddFooter.right.font = FORM_FONT


def _set_form_columns(ws):
    """Use one consistent 10-column grid for every printable form.

    A and F are narrow gutters. Every actual field uses the same aligned
    label/value columns so borders, text and print scaling line up cleanly.
    """
    widths = {
        "A": 2,
        "B": 12,
        "C": 12,
        "D": 16,
        "E": 16,
        "F": 2,
        "G": 12,
        "H": 12,
        "I": 16,
        "J": 16,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width


def _new_form_sheet(wb, title, sheet_name):
    ws = wb.create_sheet(sheet_name[:31])
    _set_form_columns(ws)
    _merge(ws, "A1:J1", COMPANY_NAME, FORM_HEADER_FILL, _font(12, True, C_WHITE), _center(), _border(FORM_HEADER_FILL, "medium"))
    _merge(ws, "A2:J2", title, FORM_ACCENT_FILL, _font(FORM_TITLE_SIZE, True, C_PRIMARY), _center(), _border())
    _merge(ws, "A3:J3", f"تاریخ تهیه سند: {_now_jalali()}", FORM_LABEL_FILL, _font(9), _center(), _border())
    ws.row_dimensions[1].height = 27
    ws.row_dimensions[2].height = 31
    ws.row_dimensions[3].height = 20
    return ws


def _section_header(ws, row, title):
    _merge(ws, f"A{row}:J{row}", title, FORM_SECTION_FILL, _font(11, True, C_PRIMARY), _rtl(), _border())
    ws.row_dimensions[row].height = 24


def _value(selected, key, value):
    return value if key in selected else "—"


def _field_row(ws, row, right_label, right_value, left_label, left_value,
               right_key=None, left_key=None, selected=None, value_size=11,
               right_fill=FORM_WRITE_FILL, left_fill=FORM_WRITE_FILL):
    selected = selected or set()
    if right_key:
        right_value = _value(selected, right_key, right_value)
    if left_key:
        left_value = _value(selected, left_key, left_value)
    b = _border()
    _merge(ws, f"G{row}:H{row}", right_label, FORM_LABEL_FILL, _font(10, True), _rtl(), b)
    _merge(ws, f"I{row}:J{row}", right_value or "—", right_fill, _font(value_size), _rtl(), b)
    _merge(ws, f"B{row}:C{row}", left_label, FORM_LABEL_FILL, _font(10, True), _rtl(), b)
    _merge(ws, f"A{row}:A{row}", left_value or "—", left_fill, _font(value_size), _rtl(), b)
    ws[f"D{row}"].fill = _fill(C_WHITE)
    ws[f"E{row}"].fill = _fill(C_WHITE)
    ws[f"F{row}"].fill = _fill(C_WHITE)
    ws.row_dimensions[row].height = 27


def _wide_title_row(ws, row, id_label, id_value, title_label, title_value,
                    id_key=None, title_key=None, selected=None, title_size=12):
    """Aligned title/identifier row for the printable Work Order and PM forms.

    The title field keeps the exact same left/right grid as every other field
    while gaining extra height and wrapping room for long Persian titles.
    This prevents the uneven-looking merged geometry of the older layout.
    """
    selected = selected or set()
    if id_key:
        id_value = _value(selected, id_key, id_value)
    if title_key:
        title_value = _value(selected, title_key, title_value)

    b = _border()
    _merge(ws, f"B{row}:C{row}", id_label, FORM_LABEL_FILL, _font(10, True), _rtl(), b)
    _merge(ws, f"D{row}:E{row}", id_value or "—", FORM_WRITE_FILL, _font(11), _center(), b)
    _merge(ws, f"G{row}:H{row}", title_label, FORM_LABEL_FILL, _font(10, True), _rtl(), b)
    _merge(
        ws,
        f"I{row}:J{row}",
        title_value or "—",
        FORM_WRITE_FILL,
        _font(title_size, True),
        _rtl("center"),
        b,
    )
    ws[f"A{row}"].fill = _fill(C_WHITE)
    ws[f"F{row}"].fill = _fill(C_WHITE)
    ws.row_dimensions[row].height = 46


def _field_row_v2(ws, row, right_label, right_value, left_label, left_value,
                  right_key=None, left_key=None, selected=None, value_size=11,
                  right_fill=FORM_WRITE_FILL, left_fill=FORM_WRITE_FILL):
    selected = selected or set()
    if right_key:
        right_value = _value(selected, right_key, right_value)
    if left_key:
        left_value = _value(selected, left_key, left_value)
    b = _border()
    # Right half: label G:H, value I:J.
    _merge(ws, f"G{row}:H{row}", right_label, FORM_LABEL_FILL, _font(10, True), _rtl(), b)
    _merge(ws, f"I{row}:J{row}", right_value or "—", right_fill, _font(value_size), _rtl(), b)
    # Left half: label B:C, value D:E.
    _merge(ws, f"B{row}:C{row}", left_label, FORM_LABEL_FILL, _font(10, True), _rtl(), b)
    _merge(ws, f"D{row}:E{row}", left_value or "—", left_fill, _font(value_size), _rtl(), b)
    for c in ("A", "F"):
        ws[f"{c}{row}"].fill = _fill(C_WHITE)
    ws.row_dimensions[row].height = 27


def _text_block(ws, row, title, text="", rows=3):
    _section_header(ws, row, title)
    row += 1
    end = row + rows - 1
    _merge(ws, f"A{row}:J{end}", text or "", FORM_WRITE_FILL, _font(11), _rtl("top"), _border())
    for r in range(row, end + 1):
        ws.row_dimensions[r].height = 25
    return end + 1


def _signature_block(ws, row, labels):
    _section_header(ws, row, "امضا و تأیید")
    row += 1
    if len(labels) == 3:
        spans = [(1, 3), (4, 7), (8, 10)]
    elif len(labels) == 2:
        spans = [(1, 5), (6, 10)]
    else:
        spans = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10)]
    for i, label in enumerate(labels):
        a, b = spans[i]
        s, e = get_column_letter(a), get_column_letter(b)
        _merge(ws, f"{s}{row}:{e}{row}", label, FORM_LABEL_FILL, _font(9, True), _center(), _border())
        _merge(ws, f"{s}{row+1}:{e}{row+3}", "\nامضا: ................................\n", FORM_WRITE_FILL, _font(9), _center(), _border())
    for r in range(row, row + 4):
        ws.row_dimensions[r].height = 22
    return row + 4


def _finish_form_sheet(ws, last_row, orientation=A4_DEFAULT_ORIENTATION):
    """Finalize a printable form as one professional A4 portrait page."""
    _apply_print_setup(ws, f"A1:J{last_row}", orientation, fit_height=1)
    ws.print_title_rows = "1:3"
    ws.freeze_panes = "A5"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_margins.left = 0.20
    ws.page_margins.right = 0.20
    ws.page_margins.top = 0.18
    ws.page_margins.bottom = 0.22
    ws.page_margins.header = 0.08
    ws.page_margins.footer = 0.10


def _action_writing_area(ws, row, rows=4, title=None):
    """Add title-free white writing space for handwritten completion notes.

    The historical ``title`` argument is retained for source compatibility,
    but no heading is printed.  The requested Excel output must show only
    clean white space in this area.
    """
    start = row
    end = start + rows - 1
    _merge(
        ws,
        f"A{start}:J{end}",
        "",
        FORM_WRITE_FILL,
        _font(11),
        _rtl("top"),
        _border(FORM_BORDER_COLOR, "thin"),
    )
    # Keep the blank writing area visibly open and usable on a printed A4 sheet.
    for r in range(start, end + 1):
        ws.row_dimensions[r].height = 25
    return end + 1


def _add_table_signature_footer(ws, row, labels=("تهیه‌کننده", "مدیر / سرپرست")):
    """Add a compact approval/signature block below list exports."""
    row += 1
    end = _signature_block(ws, row, list(labels))
    return end


def export_inspections_excel(
    inspections: list[dict],
    path: str,
    selected_columns: Optional[
        Iterable[str]
    ] = None,
) -> str:

    status_fa = {
        "in_progress":
            "در حال انجام",

        "completed":
            "تکمیل شده",

        "cancelled":
            "لغو شده",
    }

    result_fa = {
        "pass":
            "قبول",

        "fail":
            "رد",

        "partial":
            "جزئی",

        "":
            "—",
    }

    result_colors = {
        "pass":
            "E6F4EA",

        "fail":
            "FCE8E6",

        "partial":
            "FFF8E1",

        "":
            C_WHITE,
    }

    prepared_rows = []

    for inspection in (
        inspections
        or []
    ):

        result = inspection.get(
            "overall_result",
            "",
        )

        prepared_rows.append(
            {
                "id":
                    inspection.get(
                        "id",
                        "",
                    ),

                "template_name":
                    inspection.get(
                        "template_name",
                        "",
                    ),

                "equipment_name":
                    inspection.get(
                        "equipment_name",
                        "",
                    ),

                "inspector_name":
                    inspection.get(
                        "inspector_name",
                        "",
                    ),

                "status":
                    status_fa.get(
                        inspection.get(
                            "status",
                            "",
                        ),
                        inspection.get(
                            "status",
                            "",
                        ),
                    ),

                "overall_result":
                    result_fa.get(
                        result,
                        result,
                    ),

                "started_at":
                    _to_jalali_str(
                        inspection.get(
                            "started_at"
                        ),
                        fmt="%Y/%m/%d %H:%M",
                    ),

                "completed_at":
                    (
                        _to_jalali_str(
                            inspection.get(
                                "completed_at"
                            ),
                            fmt="%Y/%m/%d %H:%M",
                        )
                        if inspection.get(
                            "completed_at"
                        )
                        else "—"
                    ),

                "notes":
                    inspection.get(
                        "notes",
                        "",
                    )
                    or "",

                "_result_code":
                    result,
            }
        )

    headers, rows = (
        _build_selected_rows(
            prepared_rows,
            INSPECTION_COLUMNS,
            selected_columns,
        )
    )

    if not headers:

        raise ValueError(
            "حداقل یک ستون برای خروجی بازرسی باید انتخاب شود."
        )

    wb, ws = _prepare_workbook(
        "تاریخچه بازرسی‌ها",
        "Inspections",
        headers,
    )

    for index, values in enumerate(
        rows
    ):

        _xl_data_row(
            ws,
            5 + index,
            values,
            zebra=(
                index % 2 == 1
            ),
        )

        result_code = (
            prepared_rows[index].get(
                "_result_code",
                "",
            )
        )

        bg = result_colors.get(
            result_code,
            C_WHITE,
        )

        for col in range(
            1,
            len(headers) + 1,
        ):

            ws.cell(
                row=5 + index,
                column=col,
            ).fill = PatternFill(
                start_color=bg,
                end_color=bg,
                fill_type="solid",
            )

    _xl_auto_width(ws)
    footer_row = 5 + len(rows) + 1
    last_col = get_column_letter(max(1, len(headers)))
    _merge(ws, f"A{footer_row}:{last_col}{footer_row}", "توضیحات تکمیلی", FORM_SECTION_FILL, _font(10, True, C_PRIMARY), _rtl(), _border())
    _merge(ws, f"A{footer_row+1}:{last_col}{footer_row+2}", "", FORM_WRITE_FILL, _font(10), _rtl("top"), _border())
    ws.row_dimensions[footer_row+1].height = 24
    ws.row_dimensions[footer_row+2].height = 24
    sig_end = _add_table_signature_footer(ws, footer_row + 3)
    _xl_apply_a4_table_setup(ws, sig_end, A4_DEFAULT_ORIENTATION)
    ws.freeze_panes = "A5"
    wb.save(path)
    return path

def export_spare_parts_excel(
    parts_list: list,
    path: str,
    selected_columns: Optional[
        Iterable[str]
    ] = None,
) -> str:

    prepared_rows = []

    for part in (
        parts_list
        or []
    ):

        prepared_rows.append(
            {
                "id":
                    getattr(
                        part,
                        "id",
                        "",
                    ),

                "part_number":
                    getattr(
                        part,
                        "part_number",
                        "",
                    ),

                "name":
                    getattr(
                        part,
                        "name",
                        "",
                    ),

                "category":
                    getattr(
                        part,
                        "category",
                        "",
                    )
                    or "",

                "current_stock":
                    getattr(
                        part,
                        "current_stock",
                        "",
                    ),

                "min_stock":
                    getattr(
                        part,
                        "min_stock",
                        "",
                    ),

                "unit":
                    getattr(
                        part,
                        "unit",
                        "",
                    )
                    or "",

                "unit_price":
                    _format_number(
                        getattr(
                            part,
                            "unit_price",
                            None,
                        )
                    ),

                "location":
                    getattr(
                        part,
                        "location",
                        "",
                    )
                    or "",

                "supplier":
                    getattr(
                        part,
                        "supplier",
                        "",
                    )
                    or "",

                "description":
                    getattr(
                        part,
                        "description",
                        "",
                    )
                    or "",
            }
        )

    headers, rows = (
        _build_selected_rows(
            prepared_rows,
            SPARE_PART_COLUMNS,
            selected_columns,
        )
    )

    if not headers:

        raise ValueError(
            "حداقل یک ستون برای خروجی قطعات یدکی باید انتخاب شود."
        )

    wb, ws = _prepare_workbook(
        "لیست قطعات یدکی",
        "Spare Parts",
        headers,
    )

    for index, values in enumerate(
        rows
    ):

        _xl_data_row(
            ws,
            5 + index,
            values,
            zebra=(
                index % 2 == 1
            ),
        )

    _xl_auto_width(ws)
    footer_row = 5 + len(rows) + 1
    last_col = get_column_letter(max(1, len(headers)))
    _merge(ws, f"A{footer_row}:{last_col}{footer_row}", "توضیحات تکمیلی", FORM_SECTION_FILL, _font(10, True, C_PRIMARY), _rtl(), _border())
    _merge(ws, f"A{footer_row+1}:{last_col}{footer_row+2}", "", FORM_WRITE_FILL, _font(10), _rtl("top"), _border())
    ws.row_dimensions[footer_row+1].height = 24
    ws.row_dimensions[footer_row+2].height = 24
    sig_end = _add_table_signature_footer(ws, footer_row + 3)
    _xl_apply_a4_table_setup(ws, sig_end, A4_DEFAULT_ORIENTATION)
    ws.freeze_panes = "A5"
    wb.save(path)
    return path



# PERSONNEL / DEPARTMENT MANAGEMENT
# ----------------------------------------------------------------------------

PERSONNEL_DEPARTMENT_COLUMNS = [
    ("id", "شناسه"),
    ("full_name", "نام کامل"),
    ("department_id", "شناسه دپارتمان"),
    ("department_name", "دپارتمان"),
]


def _personnel_value(obj, key, default=""):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def export_personnel_departments_excel(
    personnel_list,
    path: str,
    selected_columns: Optional[Iterable[str]] = None,
    departments=None,
) -> str:
    """Export the Personnel & Department register as a professional A4 roster."""
    available = [key for key, _ in PERSONNEL_DEPARTMENT_COLUMNS]
    selected = _selected_set(selected_columns, available)
    if not selected:
        raise ValueError("حداقل یک ستون برای خروجی پرسنل و دپارتمان‌ها باید انتخاب شود.")

    # Build a department lookup so the export works with ORM objects or dicts.
    department_lookup = {}
    for dept in departments or []:
        did = _personnel_value(dept, "id", None)
        dname = _personnel_value(dept, "name", "")
        if did is not None and dname:
            department_lookup[did] = str(dname)

    rows = []
    for person in personnel_list or []:
        department = _personnel_value(person, "department", None)
        department_id = _personnel_value(person, "department_id", None)
        department_name = _personnel_value(person, "department_name", None)
        if not department_name and department is not None:
            department_name = _personnel_value(department, "name", "")
        if not department_name and department_id in department_lookup:
            department_name = department_lookup[department_id]

        rows.append({
            "id": _personnel_value(person, "id", "—"),
            "personnel_code": _personnel_value(person, "personnel_code", "") or "—",
            "full_name": _personnel_value(person, "full_name", "") or "—",
            "department_id": department_id if department_id is not None else "—",
            "department_name": department_name or "—",
        })

    if not rows:
        raise ValueError("داده‌ای برای خروجی پرسنل و دپارتمان‌ها وجود ندارد.")

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Personnel & Departments")
    widths = {"A": 10, "B": 38, "C": 18, "D": 38}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    border = _form_border()
    _merged_value(ws, "A1:D1", COMPANY_NAME, fill=FORM_HEADER_FILL,
                   font=Font(name=FORM_FONT, size=11, bold=True, color=C_WHITE),
                   alignment=Alignment(horizontal="center", vertical="center"), border=border)
    _merged_value(ws, "A2:D2", "فهرست پرسنل و دپارتمان‌ها", fill=C_LIGHT,
                   font=Font(name=FORM_FONT, size=15, bold=True, color=C_PRIMARY),
                   alignment=Alignment(horizontal="center", vertical="center"), border=border)
    _merged_value(ws, "A3:D3", f"تاریخ تهیه سند: {_now_jalali()}", fill=C_LIGHT,
                   font=Font(name=FORM_FONT, size=9, color=C_DARK),
                   alignment=Alignment(horizontal="center", vertical="center"), border=border)

    label_map = dict(PERSONNEL_DEPARTMENT_COLUMNS)
    selected_keys = [k for k in available if k in selected]
    for col_idx, key in enumerate(selected_keys, 1):
        cell = ws.cell(row=5, column=col_idx, value=label_map[key])
        cell.font = Font(name=FORM_FONT, size=10, bold=True, color=C_WHITE)
        cell.fill = PatternFill(start_color=C_PRIMARY, end_color=C_PRIMARY, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    ws.row_dimensions[5].height = 24

    light = PatternFill(start_color=FORM_LABEL_FILL, end_color=FORM_LABEL_FILL, fill_type="solid")
    for idx, record in enumerate(rows, start=6):
        for col_idx, key in enumerate(selected_keys, 1):
            cell = ws.cell(row=idx, column=col_idx, value=record.get(key, ""))
            cell.font = Font(name=FORM_FONT, size=10, color=C_DARK)
            cell.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
            cell.border = border
            if idx % 2 == 0:
                cell.fill = light
        ws.row_dimensions[idx].height = 22

    # Summary / signature area for managerial use.
    summary_row = 6 + len(rows) + 1
    _section_header(ws, summary_row, "تأیید اطلاعات")
    _merged_value(ws, f"A{summary_row+1}:D{summary_row+2}",
                   "این فهرست جهت استفاده در مدیریت پرسنل و تخصیص دپارتمان‌ها تهیه شده است.",
                   fill=FORM_WRITE_FILL,
                   font=Font(name=FORM_FONT, size=10, color=C_DARK),
                   alignment=Alignment(horizontal="right", vertical="center", wrap_text=True),
                   border=border)
    ws.row_dimensions[summary_row+1].height = 25
    ws.row_dimensions[summary_row+2].height = 25
    sig_end = _signature_block(ws, summary_row + 3, ["تهیه‌کننده", "مدیر / سرپرست"])
    selected_end_col = get_column_letter(len(selected_keys))
    _apply_print_setup(ws, f"A1:{selected_end_col}{sig_end-1}", A4_PORTRAIT_ORIENTATION, fit_height=0)
    ws.print_title_rows = "1:5"
    if ws.max_row >= 5:
        ws.auto_filter.ref = f"A5:{selected_end_col}{len(rows)+5}"
    ws.freeze_panes = "A6"
    wb.active = 0
    wb.save(path)
    return path



# Compatibility names used by the retained personnel/department exporter.
def _form_border(style="thin", color=FORM_BORDER_COLOR):
    return _border(color=color, style=style)

def _merged_value(ws, rng, value, *, fill=None, font=None, alignment=None, border=None):
    return _merge(ws, rng, value, fill=fill, font=font, alignment=alignment, border=border)

# -----------------------------------------------------------------------------
# Work Order
# -----------------------------------------------------------------------------

def _work_order_performer_names(wo):
    people = []
    try:
        completers = getattr(wo, "completers", None) or []
        for person in completers:
            name = _personnel_name(person)
            if name and name != "—" and name not in people:
                people.append(name)
    except Exception:
        pass

    if not people:
        person = getattr(wo, "completed_by_personnel", None)
        name = _personnel_name(person)
        if name and name != "—":
            people.append(name)

    return "\n".join(people) if people else "—"


def _performer_write_block(ws, row, label, text, selected_key, selected, rows=6):
    """Full-width performer area with enough room for multiple people.

    The old two-column placement left a large unused area beside the field.
    The performer field now uses the complete printable width so names can
    wrap naturally without leaving a dead area on the page.
    """
    value = text if selected_key in selected else "—"
    b = _border()
    _merge(
        ws,
        f"A{row}:B{row}",
        label,
        FORM_LABEL_FILL,
        _font(10, True),
        _rtl(),
        b,
    )
    _merge(
        ws,
        f"C{row}:J{row + rows - 1}",
        value,
        FORM_WRITE_FILL,
        _font(10),
        _rtl("top"),
        b,
    )
    for r in range(row, row + rows):
        ws.row_dimensions[r].height = 24
    return row + rows


def _pm_performer_names(pm):
    """Return actual PM completion personnel when available, names only."""
    candidates = []

    for attr in (
        "completed_personnel",
        "performers",
        "completers",
        "personnel",
    ):
        value = getattr(pm, attr, None)
        if value:
            if isinstance(value, (list, tuple, set)):
                candidates.extend(value)
            else:
                candidates.append(value)

    completion = getattr(pm, "completion", None)
    if completion is not None:
        people = getattr(completion, "personnel", None) or []
        if isinstance(people, (list, tuple, set)):
            candidates.extend(people)
        elif people:
            candidates.append(people)

    names = []
    for person in candidates:
        if isinstance(person, str):
            name = person.strip()
        else:
            name = _personnel_name(person)
        if name and name != "—" and name not in names:
            names.append(name)

    return "\n".join(names) if names else "هنوز در زمان ثبت پایان کار انتخاب نشده است"


def export_work_orders_excel(work_orders: list, path: str,
                             selected_columns: Optional[Iterable[str]] = None) -> str:
    type_fa = {"PREVENTIVE":"پیشگیرانه", "CORRECTIVE":"اصلاحی", "EMERGENCY":"اضطراری", "INSPECTION":"بازرسی", "PM":"PM"}
    status_fa = {"PENDING_APPROVAL":"در انتظار تأیید", "PENDING":"در انتظار", "IN_PROGRESS":"در حال انجام", "FINISH_REQUESTED":"درخواست اتمام", "COMPLETED":"تکمیل شده", "APPROVED":"تأیید شده", "REJECTED":"رد شده"}
    priority_fa = {"LOW":"کم", "MEDIUM":"متوسط", "HIGH":"بالا", "URGENT":"فوری"}
    available = [k for k, _ in WORK_ORDER_COLUMNS]
    selected = _selected_set(selected_columns, available)
    if not selected:
        raise ValueError("حداقل یک ستون برای خروجی دستورکارها باید انتخاب شود.")

    wb = Workbook()
    wb.remove(wb.active)

    for idx, wo in enumerate(work_orders or [], start=1):
        equipment = _object_value(wo, "equipment", None)
        department = _object_value(wo, "department", None)
        operator = _object_value(wo, "operator", None)
        equipment_name = (
            _object_value(equipment, "name", None)
            or _object_value(wo, "equipment_name", None)
            or "—"
        )
        equipment_code = (
            _object_value(equipment, "code", None)
            or _object_value(equipment, "equipment_code", None)
            or _object_value(wo, "equipment_code", None)
            or "—"
        )
        department_name = _department_name(department)
        if department_name == "—":
            department_name = str(
                _object_value(wo, "department_name", None) or "—"
            )
        department_id = _object_value(wo, "department_id", None)
        performer = _work_order_performer_names(wo)
        status_code = _enum_name(getattr(wo, "status", None)).upper()
        type_code = _enum_name(getattr(wo, "type", None)).upper()
        priority_code = _enum_name(getattr(wo, "priority", None)).upper()

        sheet = _new_form_sheet(wb, "فرم اجرای دستور کار تعمیرات", _unique_sheet_name(wb, f"WO-{getattr(wo,'id',idx)}"))
        row = 5
        _section_header(sheet, row, "مشخصات دستور کار"); row += 1
        _wide_title_row(
            sheet, row,
            "شماره دستور کار", _object_value(wo, "id", "—"),
            "عنوان", _object_value(wo, "title", "—") or "—",
            "id", "title", selected,
            title_size=13,
        ); row += 1
        equipment_id = _object_value(wo, "equipment_id", None)
        _field_row_v2(
            sheet, row,
            "تجهیز", equipment_name,
            "شناسه تجهیز", equipment_id if equipment_id is not None else "—",
            "equipment_name", "equipment_id", selected
        ); row += 1
        _field_row_v2(
            sheet, row,
            "کد تجهیز", equipment_code,
            "دپارتمان انجام‌دهنده", department_name,
            "equipment_code", "department_name", selected
        ); row += 1
        _field_row_v2(sheet, row, "نوع کار", type_fa.get(type_code, type_code or "—"), "اولویت", priority_fa.get(priority_code, priority_code or "—"), "type", "priority", selected); row += 1
        _field_row_v2(sheet, row, "وضعیت", status_fa.get(status_code, status_code or "—"), "", "", "status", None, selected, 10,
                      right_fill=FORM_WARNING_FILL if status_code in ("PENDING_APPROVAL","IN_PROGRESS") else FORM_WRITE_FILL); row += 2

        _section_header(sheet, row, "زمان‌بندی و اجرای کار"); row += 1
        _field_row_v2(sheet, row, "تاریخ / ساعت برنامه", _to_jalali_str(getattr(wo,"scheduled_date",None), "%Y/%m/%d %H:%M"), "مهلت انجام", _to_jalali_str(getattr(wo,"deadline",None), "%Y/%m/%d %H:%M"), "scheduled_date", "deadline", selected); row += 1
        row = _performer_write_block(sheet, row, "پرسنل انجام‌دهنده", performer, "completed_by_personnel_name", selected, rows=7)
        row += 1
        _field_row_v2(sheet, row, "اپراتور تحویل‌گیرنده", _relationship_name(operator), "ساعت اعلام خرابی", _to_jalali_str(getattr(wo,"failure_report_time",None), "%Y/%m/%d %H:%M"), "operator", "failure_report_time", selected); row += 1
        _field_row_v2(sheet, row, "شروع تعمیر", _to_jalali_str(getattr(wo,"start_time",None), "%Y/%m/%d %H:%M"), "پایان تعمیر", _to_jalali_str(getattr(wo,"end_time",None), "%Y/%m/%d %H:%M"), "start_time", "end_time", selected); row += 2

        row = _text_block(
            sheet,
            row,
            "شرح و دستورالعمل تعمیرات",
            getattr(wo, "description", "") or "",
            7,
        )
        row += 1

        _section_header(sheet, row, "هزینه، تأخیر و قطعات")
        row += 1
        _field_row_v2(
            sheet,
            row,
            "هزینه دستی (ریال)",
            _format_cost(getattr(wo, "manual_cost", 0)),
            "دقایق تأخیر",
            getattr(wo, "delay_minutes", None) if getattr(wo, "delay_minutes", None) is not None else "—",
            "manual_cost",
            "delay_minutes",
            selected,
        )
        row += 1
        _field_row_v2(
            sheet,
            row,
            "قطعات مصرفی",
            getattr(wo, "parts_used", "") or "—",
            "توضیح هزینه",
            getattr(wo, "cost_description", "") or "—",
            "parts_used",
            "cost_description",
            selected,
            9,
        )
        row += 2

        # The previous duplicate personnel-report block is intentionally removed.
        # Preserve the underlying selected fields by giving them their own larger
        # printable areas only when the caller selected them.
        if "delay_reason" in selected:
            row = _text_block(
                sheet, row, "علت تأخیر",
                getattr(wo, "delay_reason", "") or "", 2
            )
            row += 1

        row = _signature_block(sheet, row, ["پرسنل انجام دهنده", "مدیر فنی", "مدیر واحد متقاضی"])
        _merge(sheet, f"A{row}:J{row}", "این فرم برای ثبت و تأیید اجرای دستور کار تهیه شده است.", FORM_LABEL_FILL, _font(8), _center(), _border())
        sheet.row_dimensions[row].height = 18
        _finish_form_sheet(sheet, row)

    if not wb.sheetnames:
        raise ValueError("داده‌ای برای خروجی دستورکارها وجود ندارد.")
    wb.active = 0
    wb.save(path)
    return path


# -----------------------------------------------------------------------------
# PM
# -----------------------------------------------------------------------------

def _pm_frequency_fa(value):
    return {"daily":"روزانه", "weekly":"هفتگی", "monthly":"ماهانه", "quarterly":"سه‌ماهه", "biannual":"شش‌ماهه", "annual":"سالانه", "custom":"سفارشی"}.get(str(value or "").lower(), _safe_text(value, "—"))


def export_pm_excel(pm_list: list, path: str,
                    selected_columns: Optional[Iterable[str]] = None) -> str:
    available = [k for k, _ in PM_COLUMNS]
    selected = _selected_set(selected_columns, available)
    if not selected:
        raise ValueError("حداقل یک ستون برای خروجی برنامه PM باید انتخاب شود.")
    wb = Workbook(); wb.remove(wb.active)

    for idx, pm in enumerate(pm_list or [], start=1):
        get = (lambda k,d=None: pm.get(k,d)) if isinstance(pm,dict) else (lambda k,d=None: getattr(pm,k,d))
        department = get("department")
        department_id = get("department_id")
        department_name = _department_name(department) if department else (get("department_name") or "—")
        days_until = get("days_until")
        status = "غیرفعال" if not get("is_active",True) else "عقب‌افتاده" if get("is_overdue",False) else "این هفته" if days_until is not None and 0 <= days_until <= 7 else "به‌موقع"
        sheet = _new_form_sheet(wb, "فرم اجرای برنامه نگهداری پیشگیرانه (PM)", _unique_sheet_name(wb, f"PM-{get('id',idx)}"))
        row=5; _section_header(sheet,row,"مشخصات برنامه"); row+=1
        _wide_title_row(
            sheet, row,
            "شناسه برنامه", get("id", "—"),
            "عنوان برنامه", get("title") or "برنامه PM",
            "id", "title", selected,
            title_size=13,
        ); row+=1
        _field_row_v2(sheet,row,"تجهیز",get("equipment_name") or "—","کد تجهیز",get("equipment_code") or "—","equipment_name","equipment_code",selected); row+=1
        _field_row_v2(sheet,row,"دپارتمان انجام‌دهنده",department_name,"دوره تناوب",_pm_frequency_fa(get("frequency")),"department_name","frequency",selected); row+=1
        _field_row_v2(sheet,row,"شناسه دپارتمان",department_id if department_id is not None else "—","بازه تناوب (روز)",get("interval_days","—"),"department_id","interval_days",selected); row+=2
        _section_header(sheet,row,"برنامه زمانی و وضعیت"); row+=1
        _field_row_v2(sheet,row,"آخرین انجام",_to_jalali_str(get("last_done")),"سررسید بعدی",_to_jalali_str(get("next_due")),"last_done","next_due",selected); row+=1
        _field_row_v2(sheet,row,"روز مانده",days_until if days_until is not None else "—","وضعیت",status,"days_until","status",selected,10,
                      right_fill=FORM_WARNING_FILL if status=="عقب‌افتاده" else FORM_SUCCESS_FILL if status=="به‌موقع" else FORM_WRITE_FILL); row+=2
        row=_text_block(sheet,row,"چک‌لیست / دستورالعمل",get("checklist") or "",4); row+=1
        notes="\n".join(v for v in (get("notes") or "",get("parts_required") or "") if v)
        row=_text_block(sheet,row,"یادداشت / قطعات موردنیاز / نتیجه انجام",notes,3); row+=1
        _section_header(sheet,row,"جزئیات اجرای PM"); row+=1
        _field_row_v2(sheet,row,"دپارتمان انجام‌دهنده",department_name,"مدت برآوردی",get("estimated_duration","—"),"department_name","estimated_duration",selected); row+=2

        # Actual completion personnel is selected only when the generated
        # Work Order is finished. Use the complete page width for the field.
        pm_performers = _pm_performer_names(pm)
        row = _performer_write_block(
            sheet,
            row,
            "پرسنل انجام دهنده",
            pm_performers,
            "completed_personnel",
            {"completed_personnel"},
            rows=7,
        )
        row += 1

        row=_signature_block(sheet,row,["پرسنل انجام دهنده","مدیر فنی","مدیر واحد متقاضی"])
        _merge(sheet,f"A{row}:J{row}","توجه: اجرای واقعی PM از طریق دستورکار ایجادشده ثبت و با پرسنل انجام‌دهنده تکمیل می‌شود.",FORM_LABEL_FILL,_font(8),_center(),_border())
        sheet.row_dimensions[row].height=18; _finish_form_sheet(sheet,row)
    if not wb.sheetnames: raise ValueError("داده‌ای برای خروجی برنامه PM وجود ندارد.")
    wb.active=0; wb.save(path); return path


# -----------------------------------------------------------------------------
# Repair Request
# -----------------------------------------------------------------------------

REPAIR_REQUEST_COLUMNS = [
    ("id", "شناسه درخواست"),
    ("requesting_unit", "واحد متقاضی"),
    ("equipment_name", "نام دستگاه/وسیله"),
    ("breakdown_datetime", "ساعت و تاریخ اعلام خرابی"),
    ("operator_name", "اپراتور"),
    ("requester_name", "نام درخواست‌دهنده"),
    ("department_name", "دپارتمان انجام‌دهنده"),
    ("request_description", "شرح درخواست"),
    ("created_at", "تاریخ ثبت"),
    ("updated_at", "آخرین بروزرسانی"),
    ("completion_datetime", "زمان اتمام"),
    ("completed_personnel", "پرسنل انجام‌دهنده"),
    ("finish_notes", "توضیحات پرسنل / اقدامات انجام شده"),
]



def _repair_people_safe_text(completion):
    """Return completion Personnel names only; personnel codes are never printed."""
    if not completion:
        return "—"

    people = []
    for person in list(getattr(completion, "personnel", []) or []):
        name = _safe_text(getattr(person, "full_name", ""), "").strip()
        if name and name != "—" and name not in people:
            people.append(name)

    return "، ".join(people) if people else "—"


def export_repair_requests_excel(requests, path: str,
                                 selected_columns: Optional[Iterable[str]] = None) -> str:
    available=[k for k,_ in REPAIR_REQUEST_COLUMNS]
    selected=_selected_set(selected_columns,available)
    if not selected:
        raise ValueError("حداقل یک ستون برای خروجی درخواست تعمیرات باید انتخاب شود.")
    wb=Workbook(); wb.remove(wb.active)

    for idx, request in enumerate(requests or [], start=1):
        completion=_repair_value(request,"completion",None)
        department=_repair_value(request,"department",None)
        department_id=_repair_value(request,"department_id",None)
        department_name=_department_name(department) if department else (_repair_value(request,"department_name",None) or "—")
        completed_people=_repair_people_safe_text(completion)
        sheet=_new_form_sheet(wb,"حکم درخواست تعمیرات",_unique_sheet_name(wb,f"REQ-{_repair_value(request,'id',idx)}"))
        row=5; _section_header(sheet,row,"اطلاعات درخواست"); row+=1
        _field_row_v2(sheet,row,"شماره درخواست",_repair_value(request,"id","—"),"واحد متقاضی",_repair_value(request,"requesting_unit") or "—","id","requesting_unit",selected); row+=1
        _field_row_v2(sheet,row,"نام دستگاه / وسیله",_repair_value(request,"equipment_name") or "—","ساعت و تاریخ اعلام خرابی",_to_jalali_str(_repair_value(request,"breakdown_datetime"),"%Y/%m/%d %H:%M"),"equipment_name","breakdown_datetime",selected,10); row+=1
        _field_row_v2(sheet,row,"اپراتور",_repair_value(request,"operator_name") or "—","نام درخواست‌دهنده",_repair_value(request,"requester_name") or "—","operator_name","requester_name",selected); row+=1
        _field_row_v2(sheet,row,"دپارتمان انجام‌دهنده",department_name,"زمان اتمام",_to_jalali_str(getattr(completion,"completion_datetime",None),"%Y/%m/%d %H:%M") if completion else "—","department_name","completion_datetime",selected,10); row+=2

        # The old "پیگیری و نتیجه تعمیر" section is intentionally removed.
        # Its space is redistributed to the actual repair content so the printed
        # A4 form gives users much more room for Persian text and handwriting.

        # Larger area because multiple Personnel may perform the repair.
        row = _performer_write_block(
            sheet,
            row,
            "پرسنل انجام‌دهنده",
            completed_people,
            "completed_personnel",
            selected,
            rows=8,
        )
        row += 1

        # Use the freed vertical space for the request description.
        row = _text_block(
            sheet,
            row,
            "شرح درخواست / عیب اعلام‌شده",
            _repair_value(request, "request_description") or "",
            6,
        )
        row += 1

        # Personnel notes/actions are intentionally visible in the final Excel form
        # and receive the largest writing area.
        finish_notes = _repair_value(completion, "finish_notes") if completion else ""
        row = _text_block(
            sheet,
            row,
            "توضیحات پرسنل / اقدامات انجام شده",
            finish_notes or "",
            8,
        )
        row += 1

        row=_signature_block(sheet,row,["درخواست دهنده","پرسنل انجام دهنده","مدیر فنی"])
        _merge(sheet,f"A{row}:J{row}","حکم درخواست تعمیرات — برای ثبت درخواست، اجرای تعمیر و تأیید نهایی.",FORM_LABEL_FILL,_font(8),_center(),_border()); sheet.row_dimensions[row].height=18
        _finish_form_sheet(sheet,row)
    if not wb.sheetnames: raise ValueError("داده‌ای برای خروجی درخواست تعمیرات وجود ندارد.")
    wb.active=0; wb.save(path); return path


# -----------------------------------------------------------------------------
# Consolidated Reports
# -----------------------------------------------------------------------------

REPORT_EXPORT_COLUMNS=[("section","بخش گزارش"),("metric","شاخص / عنوان"),("value","مقدار"),("period","دوره گزارش")]
_REPORT_SECTION_LABELS={
    "overview":"خلاصه مدیریتی", "equipment_performance":"عملکرد تجهیزات", "kpi_analysis":"تحلیل KPI",
    "cost_analysis":"تحلیل هزینه", "technician_performance":"عملکرد پرسنل", "failure_analysis":"تحلیل خرابی",
    "pm_compliance":"انطباق PM", "maintenance_summary":"خلاصه نگهداری", "oee":"OEE",
}


def _report_is_scalar(v): return v is None or isinstance(v,(str,int,float,bool,date,datetime))


def _report_sections(data):
    if data is None: return []
    if isinstance(data,dict):
        known=[(k,data[k]) for k in _REPORT_SECTION_LABELS if k in data]
        return known or list(data.items())
    if isinstance(data,(list,tuple)) and all(isinstance(x,(list,tuple)) and len(x)==2 for x in data): return list(data)
    return [("report",data)]


def _report_rows(data):
    if data is None: return ["مقدار"],[{"مقدار":"—"}]
    if isinstance(data,dict):
        return ["شاخص","مقدار"],[{"شاخص":str(k),"مقدار":v} for k,v in data.items()]
    if not isinstance(data,(list,tuple)): return ["مقدار"],[{"مقدار":data}]
    rows=[]
    for item in data:
        if isinstance(item,dict): rows.append(dict(item))
        elif hasattr(item,"__dict__"): rows.append(dict(vars(item)))
        else: rows.append({"مقدار":item})
    if not rows: return ["مقدار"],[]
    headers=[]; seen=set()
    for r in rows:
        for k in r:
            if k not in seen: seen.add(k); headers.append(str(k))
    return headers,rows


def _report_blocks(data):
    if isinstance(data,dict):
        nested=[(k,v) for k,v in data.items() if isinstance(v,(list,tuple))]
        scalars=[(k,v) for k,v in data.items() if k not in {x[0] for x in nested}]
        blocks=[]
        if scalars: blocks.append((None,["شاخص","مقدار"],[{"شاخص":str(k),"مقدار":v} for k,v in scalars]))
        for k,v in nested:
            h,r=_report_rows(v); blocks.append((str(k),h,r))
        return blocks or [(None,["مقدار"],[{"مقدار":data}])]
    h,r=_report_rows(data); return [(None,h,r)]


def _pretty_key(k):
    return {"total_wo":"کل دستورکارها","completed":"تکمیل‌شده","pending":"در انتظار","in_progress":"در حال انجام",
            "completion_rate":"نرخ تکمیل","pm_compliance":"انطباق PM","mtbf_hours":"MTBF (ساعت)","mttr_hours":"MTTR (ساعت)",
            "availability":"دسترس‌پذیری (%)","performance":"عملکرد (%)","quality":"کیفیت (%)","oee":"OEE (%)","total_cost":"هزینه کل"}.get(str(k),str(k).replace("_"," "))


def _report_value(v):
    if v is None: return "—"
    if isinstance(v,datetime): return _to_jalali_str(v,"%Y/%m/%d %H:%M")
    if isinstance(v,date): return _to_jalali_str(v,"%Y/%m/%d")
    if isinstance(v,float): return f"{v:,.2f}"
    return v


def _report_table_header(ws,row,headers):
    for i,h in enumerate(headers,1):
        c=ws.cell(row,i,_pretty_key(h)); c.fill=_fill(FORM_HEADER_FILL); c.font=_font(10,True,C_WHITE); c.alignment=_center(); c.border=_border()
    ws.row_dimensions[row].height=24


def _report_write_rows(ws,start,headers,rows):
    b=_border("D4D9E1")
    for r_index,data in enumerate(rows):
        for c_index,h in enumerate(headers,1):
            c=ws.cell(start+r_index,c_index,_report_value(data.get(h,""))); c.fill=_fill(C_LIGHT if r_index%2 else C_WHITE); c.font=_font(10); c.alignment=_rtl(); c.border=b
        ws.row_dimensions[start+r_index].height=22


def _report_widths(ws):
    for col in range(1,ws.max_column+1):
        longest=0
        for row in range(1,ws.max_row+1):
            v=ws.cell(row,col).value
            if v is not None: longest=max(longest,max((len(x) for x in str(v).split("\n")),default=0))
        ws.column_dimensions[get_column_letter(col)].width=max(14,min(42,longest+3))


def _report_sheet_header(ws,cols,title):
    end=get_column_letter(cols)
    _merge(ws,f"A1:{end}1",COMPANY_NAME,FORM_HEADER_FILL,_font(12,True,C_WHITE),_center(),_border(FORM_HEADER_FILL,"medium"))
    _merge(ws,f"A2:{end}2",title,FORM_ACCENT_FILL,_font(15,True,C_PRIMARY),_center(),_border())
    _merge(ws,f"A3:{end}3",f"تاریخ تهیه: {_now_jalali()}",FORM_LABEL_FILL,_font(9),_center(),_border())
    ws.row_dimensions[1].height=27; ws.row_dimensions[2].height=30; ws.row_dimensions[3].height=20


def _apply_report_print(ws):
    _apply_print_setup(ws,f"A1:{get_column_letter(max(1,ws.max_column))}{max(1,ws.max_row)}",A4_DEFAULT_ORIENTATION,fit_height=0)
    ws.print_title_rows="1:5"
    if ws.max_row>=5: ws.auto_filter.ref=f"A5:{get_column_letter(ws.max_column)}{ws.max_row}"


def export_reports_excel(report_data, path: str,
                         selected_columns: Optional[Iterable[str]] = None) -> str:
    """Create one consolidated Excel workbook for the entire Reports section.

    It contains one management summary plus one worksheet per report section.
    It NEVER creates one worksheet per individual report record.
    """
    sections=_report_sections(report_data)
    if not sections: raise ValueError("داده‌ای برای گزارش جامع وجود ندارد.")
    wb=Workbook(); summary=wb.active; summary.title="گزارش جامع"
    for c,w in {"A":4,"B":30,"C":20,"D":22,"E":24}.items(): summary.column_dimensions[c].width=w
    summary.sheet_view.rightToLeft=True; summary.sheet_view.showGridLines=False
    _report_sheet_header(summary,5,"گزارش جامع سیستم نگهداری و تعمیرات")
    # Header helper wrote rows 5-7 because first arg is row. Move summary content above/after.
    # Replace these cells with the final summary layout.
    summary.delete_rows(5,3)
    _report_sheet_header(summary,5,"گزارش جامع سیستم نگهداری و تعمیرات")
    summary_row=9
    _merge(summary,f"A{summary_row}:E{summary_row}","خلاصه خروجی",FORM_SECTION_FILL,_font(11,True,C_PRIMARY),_rtl(),_border()); summary_row+=1
    headers=["#","بخش گزارش","تعداد رکورد","نوع خروجی","وضعیت"]
    _report_table_header(summary,summary_row,headers); summary_row+=1
    for i,(name,data) in enumerate(sections,1):
        label=_REPORT_SECTION_LABELS.get(str(name).lower(),str(name)); count=len(data) if isinstance(data,(list,tuple,dict)) else 1; kind="جدول" if isinstance(data,(list,tuple)) else "شاخص / خلاصه" if isinstance(data,dict) else "مقدار"
        vals=[i,label,count,kind,"آماده خروجی"]
        for j,v in enumerate(vals,1):
            c=summary.cell(summary_row,j,v); c.fill=_fill(C_LIGHT if i%2==0 else C_WHITE); c.font=_font(10); c.alignment=_center() if j!=2 else _rtl(); c.border=_border("D4D9E1")
        summary.row_dimensions[summary_row].height=22; summary_row+=1
    overview=next((d for n,d in sections if str(n).lower()=="overview"),None)
    if isinstance(overview,dict):
        summary_row+=1; _merge(summary,f"A{summary_row}:E{summary_row}","شاخص‌های کلیدی",FORM_SECTION_FILL,_font(11,True,C_PRIMARY),_rtl(),_border()); summary_row+=1
        for k,v in overview.items():
            if not _report_is_scalar(v): continue
            summary.cell(summary_row,2,_pretty_key(k)); summary.cell(summary_row,3,_report_value(v))
            for j in range(2,6):
                c=summary.cell(summary_row,j); c.fill=_fill(C_LIGHT if summary_row%2 else C_WHITE); c.font=_font(10); c.alignment=_rtl() if j==2 else _center(); c.border=_border("D4D9E1")
            summary.row_dimensions[summary_row].height=22; summary_row+=1
    _apply_print_setup(summary,f"A1:E{max(summary_row,12)}",A4_PORTRAIT_ORIENTATION,fit_height=0)
    summary.freeze_panes="B11"

    used={summary.title}
    for name,data in sections:
        title=_REPORT_SECTION_LABELS.get(str(name).lower(),str(name)); ws=wb.create_sheet(_unique_sheet_name(wb,title)); used.add(ws.title)
        blocks=_report_blocks(data); cursor=5
        first=True
        for block_name,headers,rows in blocks:
            if first:
                _report_sheet_header(ws,max(1,len(headers)),title); cursor=5; first=False
            elif block_name:
                _merge(ws,f"A{cursor}:{get_column_letter(max(1,len(headers)))}{cursor}",f"{title} — {_pretty_key(block_name)}",FORM_SECTION_FILL,_font(11,True,C_PRIMARY),_rtl(),_border()); cursor+=2
            _report_table_header(ws,cursor,headers); _report_write_rows(ws,cursor+1,headers,rows); cursor+=1+len(rows)+2
        _report_widths(ws); _apply_report_print(ws); ws.freeze_panes="A6"
    wb.active=0; wb.save(path); return path


# Compatibility aliases.
export_report_excel = export_reports_excel
export_total_report_excel = export_reports_excel


# -----------------------------------------------------------------------------
# Public metadata
# -----------------------------------------------------------------------------

def get_export_columns(export_type: str) -> list[tuple[str,str]]:
    mapping={
        "equipment":EQUIPMENT_COLUMNS,
        "pm":PM_COLUMNS,
        "work_orders":WORK_ORDER_COLUMNS,
        "inspections":INSPECTION_COLUMNS,
        "spare_parts":SPARE_PART_COLUMNS,
        "repair_requests":REPAIR_REQUEST_COLUMNS,
        "personnel_departments":PERSONNEL_DEPARTMENT_COLUMNS,
        "reports":REPORT_EXPORT_COLUMNS,
        "report":REPORT_EXPORT_COLUMNS,
        "total_report":REPORT_EXPORT_COLUMNS,
    }
    return list(mapping.get(str(export_type or "").lower(),[]))


def get_default_export_columns(export_type: str) -> list[str]:
    return [key for key,_ in get_export_columns(export_type)]

