# views/jalali_date_entry.py
"""
Gela PM System - Correct Jalali Date Entry

This widget is the single shared calendar/date-entry implementation used by
Work Orders, PM, Equipment, Reports, Machine Hours, Repair Requests, exports,
and other dialogs.

IMPORTANT
---------
The application stores Gregorian ``datetime.date`` values internally.
The user sees and edits Jalali (Persian) dates.

The calendar grid is explicitly laid out for a Persian RTL week:

    شنبه | یکشنبه | دوشنبه | سه‌شنبه | چهارشنبه | پنجشنبه | جمعه

with شنبه on the RIGHT side of the calendar.

The previous implementation calculated a correct weekday index but placed the
columns left-to-right, which made the displayed weekday headers and day cells
visually mismatched in an RTL interface.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from datetime import date, datetime, timedelta

import jdatetime
from utils.date_helpers import tehran_today  # Iranian (Asia/Tehran) clock


# ---------------------------------------------------------------------------
# Persian digit normalization
# ---------------------------------------------------------------------------

_PERSIAN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹",
    "0123456789",
)

_ARABIC_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩",
    "0123456789",
)


def _normalize_digits(value: str) -> str:
    value = str(value or "")
    return value.translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)


# ---------------------------------------------------------------------------
# Calendar constants
# ---------------------------------------------------------------------------

MONTH_NAMES = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

# Logical week order for the Persian calendar.
# Index 0 = Saturday, ..., index 6 = Friday.
WEEKDAY_NAMES = (
    "شنبه",
    "یکشنبه",
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنجشنبه",
    "جمعه",
)


# ---------------------------------------------------------------------------
# Date conversion helpers
# ---------------------------------------------------------------------------


def _jalali_weekday_index(jalali_date: jdatetime.date) -> int:
    """
    Return Persian week index:

        0 Saturday
        1 Sunday
        2 Monday
        3 Tuesday
        4 Wednesday
        5 Thursday
        6 Friday

    Python/Gregorian weekday numbering is Monday=0 ... Sunday=6.
    Converting through the Gregorian date avoids relying on implementation
    details of a third-party Jalali weekday numbering scheme.
    """

    gregorian = jalali_date.togregorian()
    return (gregorian.weekday() + 2) % 7


class JalaliDateEntry(ttk.Frame):
    """
    Persian/Jalali date entry with a correct RTL calendar popup.

    Public API retained for compatibility with the existing application:

        get_date() -> datetime.date | None
        set_date(date)
        get() -> str
        delete(first, last)
        insert(index, text)
        bind(...)

    The internal value is always Gregorian ``datetime.date``.
    """

    def __init__(
        self,
        parent,
        width=12,
        date_pattern="yyyy-mm-dd",
        **kwargs,
    ):
        frame_options = {}
        entry_options = {}

        frame_keys = {
            "class_",
            "cursor",
            "padding",
            "relief",
            "style",
            "takefocus",
        }

        for key, value in kwargs.items():
            if key in frame_keys or key.startswith("_"):
                frame_options[key] = value
            else:
                entry_options[key] = value

        super().__init__(parent, **frame_options)

        self.width = width
        self._date: date | None = None
        self._pattern = date_pattern
        self._popup = None
        self._updating_entry = False

        entry_options.setdefault("justify", "right")

        entry_opts = {
            "width": width,
            "font": ("Tahoma", 10),
        }
        entry_opts.update(entry_options)

        self.entry = ttk.Entry(self, **entry_opts)
        self.entry.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )

        self.btn = ttk.Button(
            self,
            text="📅",
            command=self._open_calendar,
            width=3,
        )
        self.btn.pack(
            side=tk.LEFT,
            padx=(2, 0),
        )

        self.entry.bind(
            "<FocusOut>",
            self._on_focus_out,
            add="+",
        )
        self.entry.bind(
            "<KeyRelease>",
            self._on_key_release,
            add="+",
        )
        self.entry.bind(
            "<Return>",
            self._on_return,
            add="+",
        )

    # ======================================================================
    # PARSING
    # ======================================================================

    def _parse_entry_text(self, show_error=False):
        """
        Parse the current entry text and update ``self._date``.
        """

        raw = self.entry.get().strip()

        if not raw:
            self._date = None
            return None

        normalized = _normalize_digits(raw)
        normalized = (
            normalized
            .replace("/", "-")
            .replace("\\", "-")
            .replace("–", "-")
            .replace("—", "-")
        )

        parts = [part.strip() for part in normalized.split("-")]

        if len(parts) != 3:
            self._date = None
            if show_error:
                self._show_invalid_date()
            return None

        try:
            year, month, day = (int(part) for part in parts)
        except ValueError:
            self._date = None
            if show_error:
                self._show_invalid_date()
            return None

        try:
            jalali = jdatetime.date(
                year,
                month,
                day,
            )
            gregorian = jalali.togregorian()
        except (TypeError, ValueError, OverflowError):
            self._date = None
            if show_error:
                self._show_invalid_date()
            return None

        self._date = gregorian
        return gregorian

    def _show_invalid_date(self):
        # Do not import messagebox globally; date fields are also used in
        # background/embedded contexts where no dialog should be raised during
        # every keystroke. Focus-out/Return callers can simply leave the field
        # invalid until the user corrects it.
        return None

    # ======================================================================
    # KEYBOARD / FOCUS
    # ======================================================================

    def _on_key_release(self, _event=None):
        if self._updating_entry:
            return
        self._parse_entry_text(show_error=False)

    def _on_focus_out(self, _event=None):
        self._parse_entry_text(show_error=True)

    def _on_return(self, _event=None):
        self._parse_entry_text(show_error=True)
        return None

    # ======================================================================
    # CALENDAR OPEN/CLOSE
    # ======================================================================

    def _open_calendar(self):
        if self._popup is not None:
            try:
                if self._popup.winfo_exists():
                    self._popup.focus_set()
                    return
            except Exception:
                pass

        # Always synchronize typed text before opening the calendar.
        self._parse_entry_text(show_error=False)

        self._popup = _JalaliCalendarPopup(
            self,
            self._date,
        )

        try:
            self._popup.bind(
                "<Destroy>",
                self._on_popup_destroy,
                add="+",
            )
        except Exception:
            pass

    def _on_popup_destroy(self, _event=None):
        self._popup = None

    # ======================================================================
    # PUBLIC DATE API
    # ======================================================================

    def get_date(self):
        """
        Return the current Gregorian date.

        The current text is parsed first so manually typed dates are never
        silently stale.
        """

        parsed = self._parse_entry_text(show_error=False)
        return parsed

    def set_date(self, date_obj):
        if date_obj is None:
            self._date = None
            self._updating_entry = True
            try:
                self.entry.delete(0, tk.END)
            finally:
                self._updating_entry = False
            return

        if isinstance(date_obj, datetime):
            date_obj = date_obj.date()

        if not isinstance(date_obj, date):
            raise TypeError(
                "Expected datetime.date or datetime.datetime"
            )

        jalali = jdatetime.date.fromgregorian(
            date=date_obj
        )

        self._date = date_obj

        self._updating_entry = True
        try:
            self.entry.delete(0, tk.END)
            self.entry.insert(
                0,
                jalali.strftime("%Y-%m-%d"),
            )
        finally:
            self._updating_entry = False

    def get(self):
        return self.entry.get()

    def delete(self, first, last=None):
        self.entry.delete(
            first,
            last,
        )
        self._parse_entry_text(show_error=False)

    def insert(self, index, string):
        self.entry.insert(
            index,
            string,
        )
        self._parse_entry_text(show_error=False)

    def bind(self, sequence=None, func=None, add=None):
        """
        Preserve the historical API:

        * Date-selection virtual events belong to this wrapper frame.
        * Ordinary typing/focus events belong to the actual Entry control.
        """

        if sequence == "<<DateEntrySelected>>":
            return super().bind(
                sequence,
                func,
                add,
            )

        return self.entry.bind(
            sequence,
            func,
            add,
        )

    def focus_set(self):
        try:
            return self.entry.focus_set()
        except Exception:
            return super().focus_set()

    # ======================================================================
    # DATE SELECTED
    # ======================================================================

    def _date_selected(self, greg_date):
        self.set_date(greg_date)
        self.event_generate(
            "<<DateEntrySelected>>"
        )

        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None


class _JalaliCalendarPopup(tk.Toplevel):
    """
    Correct RTL Jalali calendar popup.

    Screen columns are intentionally reversed:

        column 6 = شنبه
        column 5 = یکشنبه
        column 4 = دوشنبه
        column 3 = سه‌شنبه
        column 2 = چهارشنبه
        column 1 = پنجشنبه
        column 0 = جمعه

    Therefore the Persian week visually runs from right to left.
    """

    def __init__(
        self,
        parent,
        current_date,
    ):
        super().__init__(parent)

        self.parent = parent
        self.current_date = current_date

        self.transient(parent)
        self.grab_set()

        self.title("انتخاب تاریخ")
        self.resizable(False, False)
        self.configure(
            bg="#F0F2F5"
        )

        if current_date is None:
            current_date = tehran_today()

        if isinstance(current_date, datetime):
            current_date = current_date.date()

        if not isinstance(current_date, date):
            current_date = tehran_today()

        self.current_date = current_date

        self._jalali = jdatetime.date.fromgregorian(
            date=current_date
        )

        self._build_ui()
        self._draw_calendar()
        self._center()

        self.bind(
            "<Escape>",
            lambda _event: self.destroy(),
        )

    # ======================================================================
    # UI
    # ======================================================================

    def _build_ui(self):
        header = tk.Frame(
            self,
            bg="#1A2A44",
        )
        header.pack(
            fill="x",
            padx=10,
            pady=(10, 0),
        )

        tk.Label(
            header,
            text="تقویم شمسی",
            bg="#1A2A44",
            fg="white",
            font=("Tahoma", 10, "bold"),
        ).pack(
            side=tk.RIGHT,
            padx=12,
            pady=8,
        )

        nav = tk.Frame(
            self,
            bg="#F0F2F5",
        )
        nav.pack(
            fill="x",
            padx=10,
            pady=10,
        )

        self.prev_btn = tk.Button(
            nav,
            text="‹",
            width=3,
            font=("Tahoma", 12, "bold"),
            relief="flat",
            bg="white",
            cursor="hand2",
            command=self._previous_month,
        )
        self.prev_btn.pack(
            side=tk.LEFT,
            padx=3,
        )

        self.next_btn = tk.Button(
            nav,
            text="›",
            width=3,
            font=("Tahoma", 12, "bold"),
            relief="flat",
            bg="white",
            cursor="hand2",
            command=self._next_month,
        )
        self.next_btn.pack(
            side=tk.RIGHT,
            padx=3,
        )

        self.year_spin = tk.Spinbox(
            nav,
            from_=1200,
            to=1600,
            width=6,
            font=("Tahoma", 10),
            justify="center",
            command=self._on_nav,
            bg="white",
            relief="solid",
            bd=1,
        )
        self.year_spin.pack(
            side=tk.RIGHT,
            padx=3,
        )

        tk.Label(
            nav,
            text="سال",
            bg="#F0F2F5",
            font=("Tahoma", 9),
        ).pack(
            side=tk.RIGHT,
            padx=2,
        )

        self.month_spin = tk.Spinbox(
            nav,
            from_=1,
            to=12,
            width=3,
            font=("Tahoma", 10),
            justify="center",
            command=self._on_nav,
            bg="white",
            relief="solid",
            bd=1,
        )
        self.month_spin.pack(
            side=tk.RIGHT,
            padx=3,
        )

        tk.Label(
            nav,
            text="ماه",
            bg="#F0F2F5",
            font=("Tahoma", 9),
        ).pack(
            side=tk.RIGHT,
            padx=2,
        )

        self.month_name_var = tk.StringVar()
        tk.Label(
            nav,
            textvariable=self.month_name_var,
            bg="#F0F2F5",
            fg="#1A2A44",
            font=("Tahoma", 10, "bold"),
            width=10,
            anchor="e",
        ).pack(
            side=tk.RIGHT,
            padx=8,
        )

        self.cal_frame = tk.Frame(
            self,
            bg="white",
            bd=1,
            relief="solid",
        )
        self.cal_frame.pack(
            padx=10,
            pady=(0, 8),
        )

        footer = tk.Frame(
            self,
            bg="#F0F2F5",
        )
        footer.pack(
            fill="x",
            padx=10,
            pady=(0, 10),
        )

        today_btn = tk.Button(
            footer,
            text="تاریخ امروز",
            font=("Tahoma", 9),
            bg="#1A2A44",
            fg="white",
            activebackground="#243B61",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=self._go_today,
        )
        today_btn.pack(
            side=tk.RIGHT,
            padx=4,
        )

        close_btn = tk.Button(
            footer,
            text="بستن",
            font=("Tahoma", 9),
            bg="#D9DEE7",
            fg="#1F2937",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=self.destroy,
        )
        close_btn.pack(
            side=tk.LEFT,
            padx=4,
        )

    # ======================================================================
    # NAVIGATION
    # ======================================================================

    def _sync_nav_fields(self):
        self.year_spin.delete(0, tk.END)
        self.year_spin.insert(0, str(self._jalali.year))

        self.month_spin.delete(0, tk.END)
        self.month_spin.insert(0, str(self._jalali.month))

        self.month_name_var.set(
            MONTH_NAMES[self._jalali.month - 1]
        )

    def _set_year_month(self, year, month):
        year = max(1200, min(1600, int(year)))
        month = max(1, min(12, int(month)))

        try:
            self._jalali = jdatetime.date(
                year,
                month,
                1,
            )
        except ValueError:
            self._jalali = jdatetime.date(
                year,
                month,
                1,
            )

        self._draw_calendar()

    def _on_nav(self):
        try:
            year = int(
                _normalize_digits(
                    self.year_spin.get()
                )
            )
            month = int(
                _normalize_digits(
                    self.month_spin.get()
                )
            )
        except (TypeError, ValueError):
            return

        self._set_year_month(
            year,
            month,
        )

    def _previous_month(self):
        year = self._jalali.year
        month = self._jalali.month - 1

        if month < 1:
            month = 12
            year -= 1

        self._set_year_month(
            year,
            month,
        )

    def _next_month(self):
        year = self._jalali.year
        month = self._jalali.month + 1

        if month > 12:
            month = 1
            year += 1

        self._set_year_month(
            year,
            month,
        )

    # ======================================================================
    # TODAY
    # ======================================================================

    def _go_today(self):
        today_jalali = jdatetime.date.fromgregorian(date=tehran_today())
        self._jalali = today_jalali
        self._draw_calendar()

        self.parent._date_selected(
            today_jalali.togregorian()
        )

    # ======================================================================
    # CALENDAR DRAWING
    # ======================================================================

    @staticmethod
    def _days_in_month(jalali_date):
        try:
            return int(jalali_date.days_in_month)
        except Exception:
            if jalali_date.month == 12:
                next_month = jdatetime.date(
                    jalali_date.year + 1,
                    1,
                    1,
                )
            else:
                next_month = jdatetime.date(
                    jalali_date.year,
                    jalali_date.month + 1,
                    1,
                )

            previous_day = next_month.togregorian() - timedelta(days=1)
            return jdatetime.date.fromgregorian(
                date=previous_day
            ).day

    @staticmethod
    def _screen_column(logical_weekday_index):
        """
        Convert Persian logical week index into a left-to-right Tk column.

        logical 0 = Saturday -> screen column 6 (rightmost)
        logical 6 = Friday   -> screen column 0 (leftmost)
        """

        return 6 - int(logical_weekday_index)

    def _draw_weekday_headers(self):
        # Header positions use the SAME mapping as day cells.
        for logical_index, weekday_name in enumerate(WEEKDAY_NAMES):
            column = self._screen_column(
                logical_index
            )

            label = tk.Label(
                self.cal_frame,
                text=weekday_name,
                font=("Tahoma", 8, "bold"),
                bg="#E8ECF2",
                fg="#1A2A44",
                width=9,
                anchor="center",
                relief="ridge",
                bd=1,
            )

            label.grid(
                row=0,
                column=column,
                padx=0,
                pady=0,
                sticky="nsew",
            )

    def _draw_calendar(self):
        for widget in self.cal_frame.winfo_children():
            widget.destroy()

        self._sync_nav_fields()
        self._draw_weekday_headers()

        first_day = jdatetime.date(
            self._jalali.year,
            self._jalali.month,
            1,
        )

        first_weekday = _jalali_weekday_index(
            first_day
        )

        num_days = self._days_in_month(
            self._jalali
        )

        today_jalali = jdatetime.date.fromgregorian(date=tehran_today())

        for logical_day_offset in range(num_days):
            day_number = logical_day_offset + 1

            logical_week_position = (
                first_weekday
                + logical_day_offset
            ) % 7

            screen_column = self._screen_column(
                logical_week_position
            )

            row = (
                logical_day_offset
                + first_weekday
            ) // 7 + 1

            is_today = (
                today_jalali.year == self._jalali.year
                and today_jalali.month == self._jalali.month
                and today_jalali.day == day_number
            )

            # Highlight the currently selected date as well as today.
            selected = False
            try:
                selected_jalali = jdatetime.date.fromgregorian(
                    date=self.current_date
                )
                selected = (
                    selected_jalali.year == self._jalali.year
                    and selected_jalali.month == self._jalali.month
                    and selected_jalali.day == day_number
                )
            except Exception:
                pass

            if selected:
                bg_color = "#1A2A44"
                fg_color = "white"
            elif is_today:
                bg_color = "#D9E8FF"
                fg_color = "#0B4EA2"
            else:
                bg_color = "white"
                fg_color = "#1F2937"

            button = tk.Button(
                self.cal_frame,
                text=str(day_number),
                width=9,
                height=1,
                font=("Tahoma", 9),
                relief="flat",
                bd=0,
                bg=bg_color,
                fg=fg_color,
                activebackground="#DDE6F5",
                activeforeground="#1A2A44",
                cursor="hand2",
                command=lambda d=day_number: self._select_date(d),
            )

            button.grid(
                row=row,
                column=screen_column,
                padx=1,
                pady=1,
                sticky="nsew",
            )

        for column in range(7):
            self.cal_frame.columnconfigure(
                column,
                weight=1,
            )

    # ======================================================================
    # SELECT
    # ======================================================================

    def _select_date(self, day):
        try:
            jalali = jdatetime.date(
                self._jalali.year,
                self._jalali.month,
                int(day),
            )
        except (TypeError, ValueError):
            return

        gregorian = jalali.togregorian()
        self.current_date = gregorian

        self.parent._date_selected(
            gregorian
        )

    # ======================================================================
    # POSITION
    # ======================================================================

    def _center(self):
        self.update_idletasks()

        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = max(
            0,
            (screen_width - width) // 2,
        )

        y = max(
            0,
            (screen_height - height) // 2,
        )

        self.geometry(
            f"+{x}+{y}"
        )


__all__ = [
    "JalaliDateEntry",
]
