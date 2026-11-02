# -*- coding: utf-8 -*-
"""
Repair Request View
===================

Business workflow
-----------------
CREATE REQUEST
    Unit + equipment + breakdown date/time + requester + executing Department
    are recorded.
    NO Personnel is selected at this stage.

COMPLETE REQUEST
    When the repair is actually finished, the application shows ONLY
    Personnel belonging to the request's executing Department. One or more
    Personnel can be selected.

EDIT
    The request itself is fully editable.
    A completed request is also fully editable: completion datetime, notes,
    cost, delay and the one-or-more completion Personnel can all be changed.

The legacy assigned_personnel field is intentionally not used by the new
workflow.
"""

from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from database.db import SessionLocal
from database.equipment_repository import EquipmentRepository
from database.repair_request_repository import RepairRequestRepository
from services.pdf_service import export_repair_requests_pdf
from utils.theme import (
    GRAY_BG,
    GRAY_BORDER,
    NAVY,
    NAVY_LIGHT,
    RED,
    SUCCESS,
    TEXT_DARK,
    TEXT_LIGHT,
    WARNING,
    WHITE,
    FONT_HEADING,
    FONT_NORMAL,
    FONT_SMALL,
    FONT_TITLE,
)
from views.jalali_date_entry import JalaliDateEntry
from views.searchable_combobox import SearchableCombobox
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


from utils.date_helpers import jalali_stamp  # Jalali file names / stamps
# =============================================================================
# LOCAL THEME ALIASES
# =============================================================================

BG = GRAY_BG
CARD = WHITE
PRIMARY = NAVY
PRIMARY_LIGHT = NAVY_LIGHT
TEXT = TEXT_DARK
SUBTLE = TEXT_LIGHT
BORDER = GRAY_BORDER
DANGER = RED
OK = SUCCESS


# =============================================================================
# HELPERS
# =============================================================================

def _safe_text(value) -> str:
    return "" if value is None else str(value).strip()


def _format_jalali_datetime(value) -> str:
    if not value:
        return "—"
    try:
        import jdatetime

        if isinstance(value, datetime):
            jd = jdatetime.datetime.fromgregorian(datetime=value)
            return jd.strftime("%Y/%m/%d %H:%M")
        if hasattr(value, "year"):
            jd = jdatetime.date.fromgregorian(date=value)
            return jd.strftime("%Y/%m/%d")
    except Exception:
        pass

    try:
        return value.strftime("%Y/%m/%d %H:%M")
    except Exception:
        return str(value)


def _role_name(current_user) -> str:
    if isinstance(current_user, dict):
        return _safe_text(current_user.get("role")).lower()
    return ""


# =============================================================================
# SEARCHABLE PERSONNEL COMBO
# =============================================================================

class FilteredSearchCombobox(ttk.Combobox):
    """A stable type-to-filter ttk Combobox."""

    _NAV_KEYS = {
        "Up", "Down", "Left", "Right", "Home", "End", "Prior", "Next",
        "Return", "Escape", "Tab", "Shift_L", "Shift_R",
        "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock",
    }

    def __init__(self, parent, textvariable=None, **kwargs):
        kwargs.setdefault("state", "normal")
        super().__init__(parent, textvariable=textvariable, **kwargs)
        self._all_values: list[str] = []
        self.bind("<KeyRelease>", self._on_key_release, add="+")
        self.bind("<Button-1>", self._on_click, add="+")
        self.bind("<FocusIn>", self._on_focus_in, add="+")
        self.bind("<Escape>", self._on_escape, add="+")

    def set_completion_list(self, values):
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
        self.configure(values=unique)

    def _filter(self, query):
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
        self.configure(values=self._filter(self.get()))

    def _on_key_release(self, event):
        if event.keysym not in self._NAV_KEYS:
            self._apply_filter()

    def _on_click(self, _event):
        self.after_idle(self._apply_filter)

    def _on_focus_in(self, _event):
        self.after_idle(self._apply_filter)

    def _on_escape(self, _event):
        self.set("")
        self._apply_filter()
        return "break"


# =============================================================================
# COMMON SCROLLING MIXIN
# =============================================================================

class _ScrollableToplevel(tk.Toplevel):
    def _init_scrollable_body(self, *, header_title: str, width=900, height=760):
        self.title(header_title)
        self.configure(bg=BG)
        self.resizable(True, True)
        self.geometry(f"{width}x{height}")
        self.minsize(720, 560)
        self.transient(self.master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        header = tk.Frame(self, bg=PRIMARY, height=62)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=header_title,
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE,
            anchor="e",
            padx=20,
        ).pack(fill="both", expand=True)

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True)

        self._body_canvas = tk.Canvas(
            content,
            bg=BG,
            highlightthickness=0,
            borderwidth=0,
        )
        self._body_scrollbar = ttk.Scrollbar(
            content,
            orient="vertical",
            command=self._body_canvas.yview,
        )
        self._body_canvas.configure(yscrollcommand=self._body_scrollbar.set)

        self._body_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        self._body_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)

        self._body_frame = tk.Frame(self._body_canvas, bg=BG)
        self._body_window = self._body_canvas.create_window(
            (0, 0), window=self._body_frame, anchor="nw"
        )

        self._body_frame.bind("<Configure>", self._sync_scroll_region)
        self._body_canvas.bind("<Configure>", self._resize_body_window)
        self._body_canvas.bind("<MouseWheel>", self._scroll_mousewheel, add="+")
        self._body_canvas.bind("<Button-4>", lambda _e: self._body_canvas.yview_scroll(-3, "units"), add="+")
        self._body_canvas.bind("<Button-5>", lambda _e: self._body_canvas.yview_scroll(3, "units"), add="+")

        self.bind("<MouseWheel>", self._scroll_mousewheel, add="+")
        self.bind("<Button-4>", lambda _e: self._body_canvas.yview_scroll(-3, "units"), add="+")
        self.bind("<Button-5>", lambda _e: self._body_canvas.yview_scroll(3, "units"), add="+")

        self.after(80, self._center_window)
        return self._body_frame

    def _sync_scroll_region(self, _event=None):
        try:
            self._body_canvas.configure(scrollregion=self._body_canvas.bbox("all"))
        except Exception:
            pass

    def _resize_body_window(self, event=None):
        try:
            width = event.width if event else self._body_canvas.winfo_width()
            self._body_canvas.itemconfigure(self._body_window, width=max(1, width))
        except Exception:
            pass

    def _scroll_mousewheel(self, event):
        try:
            delta = int(getattr(event, "delta", 0) or 0)
            if delta:
                units = int(-delta / 120) or (-1 if delta > 0 else 1)
                self._body_canvas.yview_scroll(units, "units")
                return "break"
        except Exception:
            pass
        return None

    def _center_window(self):
        try:
            self.update_idletasks()
            width = min(self.winfo_width(), self.winfo_screenwidth() - 80)
            height = min(self.winfo_height(), self.winfo_screenheight() - 80)
            width = max(720, width)
            height = max(560, height)
            x = max(10, (self.winfo_screenwidth() - width) // 2)
            y = max(10, (self.winfo_screenheight() - height) // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass


# =============================================================================
# FINISH DIALOG
# =============================================================================

class RepairRequestFinishDialog(_ScrollableToplevel):
    """Register actual completion Personnel from the request Department."""

    def __init__(self, parent, repository, document):
        super().__init__(parent)
        self.repository = repository
        self.document = document

        self.result = False
        self.personnel_ids: list[int] = []
        self.completion_datetime = None
        self.finish_notes = None
        self.manual_cost = 0.0
        self.cost_description = None
        self.delay_minutes = None
        self.delay_reason = None

        body = self._init_scrollable_body(
            header_title="✅ ثبت اتمام درخواست تعمیرات",
            width=900,
            height=720,
        )
        self._build_body(body)
        self._build_footer()
        self._load_personnel()
        self._reset_position()

    def _reset_position(self):
        try:
            self._body_canvas.yview_moveto(0.0)
        except Exception:
            pass

    def _build_body(self, body):
        card = tk.Frame(body, bg=CARD, bd=0, relief="solid", highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", padx=12, pady=12)

        info = tk.Frame(card, bg=CARD)
        info.pack(fill="x", padx=22, pady=(18, 10))
        tk.Label(info, text=f"درخواست #{getattr(self.document, 'id', '—')}", font=FONT_HEADING, bg=CARD, fg=PRIMARY, anchor="e").pack(fill="x")
        tk.Label(info, text=f"دستگاه / وسیله: {_safe_text(getattr(self.document, 'equipment_name', '—')) or '—'}", font=FONT_NORMAL, bg=CARD, fg=TEXT, anchor="e").pack(fill="x", pady=(5, 0))
        department = getattr(self.document, "department", None)
        self.department_name = _safe_text(getattr(department, "name", "")) or "—"
        tk.Label(info, text=f"دپارتمان انجام‌دهنده: {self.department_name}", font=FONT_NORMAL, bg=CARD, fg=PRIMARY, anchor="e").pack(fill="x", pady=(4, 0))
        tk.Label(info, text="فقط پرسنل همین دپارتمان در فهرست اتمام کار نمایش داده می‌شوند.", font=FONT_SMALL, bg=CARD, fg=SUBTLE, anchor="e").pack(fill="x", pady=(4, 0))

        personnel_box = tk.Frame(card, bg=CARD)
        personnel_box.pack(fill="x", padx=22, pady=(6, 8))
        tk.Label(personnel_box, text="پرسنل انجام‌دهنده *", font=FONT_HEADING, bg=CARD, fg=TEXT, anchor="e").pack(fill="x")
        tk.Label(personnel_box, text="یک نفر یا چند نفر را انتخاب کنید.", font=FONT_SMALL, bg=CARD, fg=SUBTLE, anchor="e").pack(fill="x", pady=(3, 7))

        search_row = tk.Frame(personnel_box, bg=CARD)
        search_row.pack(fill="x", pady=(0, 7))
        search_row.grid_columnconfigure(0, weight=1)
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_row, textvariable=self.search_var, font=FONT_NORMAL,
            bg=WHITE, fg=TEXT, relief="solid", bd=1, highlightthickness=0,
            justify="right", insertbackground=TEXT,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", ipady=7)
        tk.Label(search_row, text="جستجوی نام / کد:", font=FONT_SMALL, bg=CARD, fg=TEXT).grid(row=0, column=1, padx=(8, 0))
        self.search_entry.bind("<KeyRelease>", lambda _e: self._render_personnel())

        list_frame = tk.Frame(personnel_box, bg=WHITE, bd=1, relief="solid")
        list_frame.pack(fill="x")
        self.personnel_listbox = tk.Listbox(
            list_frame, selectmode=tk.EXTENDED, exportselection=False, height=8,
            font=FONT_NORMAL, justify="right", bg=WHITE, fg=TEXT,
            selectbackground=PRIMARY_LIGHT, selectforeground=WHITE,
            relief="flat", bd=0, activestyle="none",
        )
        self.personnel_listbox.pack(side=tk.LEFT, fill="both", expand=True)
        personnel_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.personnel_listbox.yview)
        personnel_scroll.pack(side=tk.RIGHT, fill="y")
        self.personnel_listbox.configure(yscrollcommand=personnel_scroll.set)
        self.personnel_listbox.bind("<<ListboxSelect>>", self._update_personnel_count)

        controls = tk.Frame(personnel_box, bg=CARD)
        controls.pack(fill="x", pady=(7, 0))
        tk.Button(controls, text="انتخاب همه", command=self._select_all_visible, bg=BG, fg=TEXT, relief="solid", bd=1, font=FONT_SMALL, cursor="hand2", padx=12, pady=4).pack(side=tk.RIGHT, padx=3)
        tk.Button(controls, text="لغو انتخاب", command=self._clear_selection, bg=BG, fg=TEXT, relief="solid", bd=1, font=FONT_SMALL, cursor="hand2", padx=12, pady=4).pack(side=tk.RIGHT, padx=3)
        self.personnel_count_label = tk.Label(controls, text="انتخاب‌شده: ۰", bg=CARD, fg=SUBTLE, font=FONT_SMALL)
        self.personnel_count_label.pack(side=tk.LEFT, padx=6)

        detail = tk.Frame(card, bg=CARD)
        detail.pack(fill="x", padx=22, pady=(10, 20))
        detail.grid_columnconfigure(0, weight=1)
        detail.grid_columnconfigure(1, weight=1)

        self.time_var = tk.StringVar(value=tehran_now().strftime("%H:%M"))
        self.cost_var = tk.StringVar(value="0")
        self.delay_var = tk.StringVar(value="0")

        tk.Label(detail, text="تاریخ اتمام *", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=0, column=1, sticky="e", padx=6, pady=(4, 2))
        self.date_entry = JalaliDateEntry(detail, width=15)
        self.date_entry.set_date(tehran_now())
        self.date_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 8))

        tk.Label(detail, text="ساعت اتمام *", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=0, column=0, sticky="e", padx=6, pady=(4, 2))
        ttk.Entry(detail, textvariable=self.time_var, justify="center").grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 8), ipady=5)

        tk.Label(detail, text="هزینه دستی (ریال)", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=2, column=1, sticky="e", padx=6, pady=(4, 2))
        ttk.Entry(detail, textvariable=self.cost_var, justify="center").grid(row=3, column=1, sticky="ew", padx=6, pady=(0, 8), ipady=5)

        tk.Label(detail, text="تأخیر (دقیقه)", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=2, column=0, sticky="e", padx=6, pady=(4, 2))
        ttk.Entry(detail, textvariable=self.delay_var, justify="center").grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 8), ipady=5)

        self.notes_text = self._text_field(detail, 4, "توضیحات انجام کار", 5)
        self.cost_desc_text = self._text_field(detail, 6, "شرح هزینه", 3)
        self.delay_reason_text = self._text_field(detail, 8, "علت تأخیر", 3)

    @staticmethod
    def _text_field(parent, row, label, height):
        frame = tk.Frame(parent, bg=CARD)
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=(5, 2))
        tk.Label(frame, text=label, font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").pack(fill="x", pady=(0, 3))
        widget = tk.Text(frame, height=height, wrap="word", font=FONT_NORMAL, bg=WHITE, fg=TEXT, relief="solid", bd=1, highlightthickness=0, insertbackground=TEXT)
        widget.pack(fill="x")
        return widget

    def _load_personnel(self):
        self.personnel_map = {}
        try:
            people = self.repository.get_personnel_for_finish(getattr(self.document, "id", None)) or []
        except Exception as exc:
            messagebox.showerror("خطا", f"دریافت پرسنل دپارتمان انجام‌دهنده انجام نشد:\n\n{exc}", parent=self)
            self.destroy()
            return

        for person in people:
            pid = getattr(person, "id", None)
            name = _safe_text(getattr(person, "full_name", ""))
            code = _safe_text(getattr(person, "personnel_code", ""))
            if pid is None or not name:
                continue
            display = " - ".join(value for value in (code, name) if value)
            self.personnel_map[display] = int(pid)

        self._all_personnel_display = sorted(self.personnel_map.keys(), key=str.casefold)
        if not self._all_personnel_display:
            messagebox.showerror(
                "پرسنل",
                f"برای دپارتمان «{self.department_name}» هیچ پرسنلی برای ثبت اتمام کار یافت نشد.",
                parent=self,
            )
            self.destroy()
            return
        self._render_personnel()

    def _render_personnel(self):
        query = self.search_var.get().strip().casefold()
        parts = [part for part in query.split() if part]
        values = [
            value for value in self._all_personnel_display
            if not parts or all(part in value.casefold() for part in parts)
        ]
        selected = {
            self.personnel_listbox.get(i)
            for i in self.personnel_listbox.curselection()
        }
        self.personnel_listbox.delete(0, tk.END)
        for value in values:
            self.personnel_listbox.insert(tk.END, value)
            if value in selected:
                self.personnel_listbox.selection_set(tk.END)
        self._update_personnel_count()

    def _select_all_visible(self):
        self.personnel_listbox.selection_set(0, tk.END)
        self._update_personnel_count()

    def _clear_selection(self):
        self.personnel_listbox.selection_clear(0, tk.END)
        self._update_personnel_count()

    def _update_personnel_count(self, _event=None):
        self.personnel_count_label.config(
            text=f"انتخاب‌شده: {len(self.personnel_listbox.curselection()):,}"
        )

    @staticmethod
    def _parse_datetime(date_entry, time_text, label):
        selected_date = date_entry.get_date()
        if selected_date is None:
            raise ValueError(f"لطفاً {label} را انتخاب کنید.")
        text = _safe_text(time_text).replace("٫", ":").replace(".", ":")
        if text.isdigit() and len(text) == 4:
            text = text[:2] + ":" + text[2:]
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError(f"ساعت {label} باید به شکل HH:MM باشد.")
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"ساعت {label} نامعتبر است.")
        return datetime(selected_date.year, selected_date.month, selected_date.day, hour, minute)

    def _submit(self):
        selected = self.personnel_listbox.curselection()
        self.personnel_ids = [
            self.personnel_map[self.personnel_listbox.get(i)]
            for i in selected
            if self.personnel_listbox.get(i) in self.personnel_map
        ]
        if not self.personnel_ids:
            messagebox.showwarning("پرسنل انجام‌دهنده", "حداقل یک پرسنل انجام‌دهنده انتخاب کنید.", parent=self)
            return

        try:
            self.completion_datetime = self._parse_datetime(self.date_entry, self.time_var.get(), "تاریخ و ساعت اتمام")
            self.manual_cost = float(self.cost_var.get().strip() or 0)
            if self.manual_cost < 0:
                raise ValueError("هزینه نمی‌تواند منفی باشد.")
            raw_delay = self.delay_var.get().strip()
            self.delay_minutes = int(raw_delay or 0)
            if self.delay_minutes < 0:
                raise ValueError("تاخیر نمی‌تواند منفی باشد.")
        except ValueError as exc:
            messagebox.showwarning("اطلاعات اتمام", str(exc) if str(exc) else "مقدار واردشده نامعتبر است.", parent=self)
            return

        self.finish_notes = self.notes_text.get("1.0", tk.END).strip() or None
        self.cost_description = self.cost_desc_text.get("1.0", tk.END).strip() or None
        self.delay_reason = self.delay_reason_text.get("1.0", tk.END).strip() or None
        self.result = True
        self.destroy()

    def _build_footer(self):
        footer = tk.Frame(self, bg=CARD, height=72, highlightbackground=BORDER, highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Button(footer, text="انصراف", command=self.destroy, bg=BG, fg=TEXT, relief="solid", bd=1, cursor="hand2", font=FONT_NORMAL, padx=24, pady=8).pack(side=tk.LEFT, padx=14, pady=12)
        tk.Button(footer, text="✅ ثبت اتمام کار", command=self._submit, bg=OK, fg=WHITE, activebackground=PRIMARY, relief="flat", bd=0, cursor="hand2", font=FONT_NORMAL, padx=24, pady=8).pack(side=tk.RIGHT, padx=14, pady=12)
        self.bind("<Control-Return>", lambda _e: self._submit())
        self.bind("<Escape>", lambda _e: self.destroy())


# =============================================================================
# FULL EDIT DIALOG
# =============================================================================

class RepairRequestFullEditDialog(_ScrollableToplevel):
    """Full editor for the request and, when completed, its completion data."""

    def __init__(self, parent, repository, record, callback=None):
        super().__init__(parent)
        self.repository = repository
        self.record = record
        self.callback = callback
        self.result = False

        self.requesting_unit_var = tk.StringVar()
        self.equipment_var = tk.StringVar()
        self.department_var = tk.StringVar()
        self.requester_var = tk.StringVar()
        self.operator_var = tk.StringVar()
        self.breakdown_time_var = tk.StringVar()

        self.completion_time_var = tk.StringVar()
        self.completion_cost_var = tk.StringVar(value="0")
        self.completion_delay_var = tk.StringVar(value="0")
        self.personnel_search_var = tk.StringVar()

        self.department_map: dict[str, int] = {}
        self.equipment_map: dict[str, int] = {}
        self.completion_personnel_map: dict[str, int] = {}
        self._all_completion_personnel_display: list[str] = []
        self._selected_completion_personnel_ids: set[int] = set()

        self._build()
        self._load_reference_data()
        self._load_record()

    def _build(self):
        body = self._init_scrollable_body(
            header_title=f"✏️ ویرایش کامل درخواست تعمیرات #{getattr(self.record, 'id', '—')}",
            width=960,
            height=860,
        )

        card = tk.Frame(body, bg=CARD, bd=0, relief="solid", highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", padx=12, pady=12)
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)

        row = 0
        row = self._section(card, row, "اطلاعات درخواست")

        row = self._entry(card, row, 1, "واحد متقاضی *", self.requesting_unit_var)
        row = self._equipment_field(card, row)

        tk.Label(card, text="دپارتمان انجام‌دهنده *", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=row, column=1, sticky="e", padx=(10, 0), pady=6)
        self.department_combo = ttk.Combobox(card, textvariable=self.department_var, state="readonly", justify="right", font=FONT_NORMAL)
        self.department_combo.grid(row=row, column=0, sticky="ew", pady=6)
        self.department_combo.bind("<<ComboboxSelected>>", lambda _e: self._department_changed())
        row += 1

        row = self._entry(card, row, 1, "نام درخواست‌دهنده *", self.requester_var)
        row = self._entry(card, row, 0, "اپراتور", self.operator_var, right_column=True)

        tk.Label(card, text="تاریخ و ساعت اعلام خرابی *", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=row, column=1, sticky="e", padx=(10, 0), pady=6)
        date_host = tk.Frame(card, bg=CARD)
        date_host.grid(row=row, column=0, sticky="ew", pady=6)
        self.breakdown_date_entry = JalaliDateEntry(date_host, width=15)
        self.breakdown_date_entry.pack(side=tk.RIGHT, padx=2)
        tk.Label(date_host, text="ساعت", font=FONT_SMALL, bg=CARD, fg=SUBTLE).pack(side=tk.RIGHT, padx=4)
        ttk.Entry(date_host, textvariable=self.breakdown_time_var, width=8, justify="center").pack(side=tk.RIGHT, padx=2, ipady=5)
        row += 1

        tk.Label(card, text="شرح درخواست", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="ne").grid(row=row, column=1, sticky="ne", padx=(10, 0), pady=6)
        self.description_text = tk.Text(card, height=6, font=FONT_NORMAL, wrap="word", bg=WHITE, fg=TEXT, relief="solid", bd=1, highlightthickness=0)
        self.description_text.grid(row=row, column=0, sticky="ew", pady=6)
        row += 1

        row = self._section(card, row, "اطلاعات اتمام کار")
        self.completion_status_label = tk.Label(card, text="", font=FONT_SMALL, bg=CARD, fg=TEXT_LIGHT, anchor="e", justify="right")
        self.completion_status_label.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row += 1

        completion = tk.Frame(card, bg=CARD)
        completion.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        completion.grid_columnconfigure(0, weight=1)
        completion.grid_columnconfigure(1, weight=1)
        self.completion_container = completion

        tk.Label(completion, text="تاریخ اتمام", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=0, column=1, sticky="e", padx=6, pady=(2, 2))
        self.completion_date_entry = JalaliDateEntry(completion, width=15)
        self.completion_date_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 8))

        tk.Label(completion, text="ساعت اتمام", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=0, column=0, sticky="e", padx=6, pady=(2, 2))
        self.completion_time_entry = ttk.Entry(completion, textvariable=self.completion_time_var, justify="center")
        self.completion_time_entry.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 8), ipady=5)

        tk.Label(completion, text="هزینه دستی (ریال)", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=2, column=1, sticky="e", padx=6, pady=(2, 2))
        self.completion_cost_entry = ttk.Entry(completion, textvariable=self.completion_cost_var, justify="center")
        self.completion_cost_entry.grid(row=3, column=1, sticky="ew", padx=6, pady=(0, 8), ipady=5)

        tk.Label(completion, text="تأخیر (دقیقه)", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=2, column=0, sticky="e", padx=6, pady=(2, 2))
        self.completion_delay_entry = ttk.Entry(completion, textvariable=self.completion_delay_var, justify="center")
        self.completion_delay_entry.grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 8), ipady=5)

        search_frame = tk.Frame(completion, bg=CARD)
        search_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 4))
        search_frame.grid_columnconfigure(0, weight=1)
        tk.Label(search_frame, text="جستجوی پرسنل انجام‌دهنده", font=FONT_SMALL, bg=CARD, fg=TEXT).grid(row=0, column=1, padx=(0, 8))
        self.personnel_search_entry = ttk.Entry(search_frame, textvariable=self.personnel_search_var, justify="right")
        self.personnel_search_entry.grid(row=0, column=0, sticky="ew", ipady=5)
        self.personnel_search_var.trace_add("write", lambda *_: self._render_completion_personnel())

        list_frame = tk.Frame(completion, bg=WHITE, bd=1, relief="solid")
        list_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 6))
        self.personnel_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, exportselection=False, height=8, font=FONT_NORMAL, justify="right", bg=WHITE, fg=TEXT, selectbackground=PRIMARY_LIGHT, selectforeground=WHITE, relief="flat", bd=0, activestyle="none")
        self.personnel_listbox.pack(side=tk.LEFT, fill="both", expand=True)
        pscroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.personnel_listbox.yview)
        pscroll.pack(side=tk.RIGHT, fill="y")
        self.personnel_listbox.configure(yscrollcommand=pscroll.set)
        self.personnel_listbox.bind("<<ListboxSelect>>", self._sync_completion_selection)

        control_row = tk.Frame(completion, bg=CARD)
        control_row.grid(row=6, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
        tk.Button(control_row, text="انتخاب همه", command=self._select_all_visible, bg=BG, fg=TEXT, relief="solid", bd=1, font=FONT_SMALL, cursor="hand2", padx=12, pady=4).pack(side=tk.RIGHT, padx=3)
        tk.Button(control_row, text="لغو انتخاب", command=self._clear_visible, bg=BG, fg=TEXT, relief="solid", bd=1, font=FONT_SMALL, cursor="hand2", padx=12, pady=4).pack(side=tk.RIGHT, padx=3)
        self.personnel_count_label = tk.Label(control_row, text="انتخاب‌شده: ۰", bg=CARD, fg=SUBTLE, font=FONT_SMALL)
        self.personnel_count_label.pack(side=tk.LEFT, padx=6)

        self.finish_notes_text = self._text_area(completion, 7, "توضیحات انجام کار", 5)
        self.cost_description_text = self._text_area(completion, 9, "شرح هزینه", 3)
        self.delay_reason_text = self._text_area(completion, 11, "علت تأخیر", 3)

        self._build_footer()
        self.bind("<Control-s>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())

    @staticmethod
    def _section(parent, row, title):
        header = tk.Frame(parent, bg=PRIMARY, height=34)
        header.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(4, 10))
        header.grid_propagate(False)
        tk.Label(header, text=title, font=FONT_HEADING, bg=PRIMARY, fg=WHITE, anchor="e", padx=10).pack(fill="both", expand=True)
        return row + 1

    @staticmethod
    def _entry(parent, row, column, label, variable, right_column=False):
        actual_column = column
        tk.Label(parent, text=label, font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=row, column=1, sticky="e", padx=(10, 0), pady=6)
        ttk.Entry(parent, textvariable=variable, justify="right").grid(row=row, column=0, sticky="ew", pady=6)
        return row + 1

    def _equipment_field(self, parent, row):
        tk.Label(parent, text="دستگاه / وسیله *", font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").grid(row=row, column=1, sticky="e", padx=(10, 0), pady=6)
        self.equipment_combo = FilteredSearchCombobox(parent, textvariable=self.equipment_var, width=48, justify="right", font=FONT_NORMAL)
        self.equipment_combo.grid(row=row, column=0, sticky="ew", pady=6)
        return row + 1

    @staticmethod
    def _text_area(parent, row, label, height):
        frame = tk.Frame(parent, bg=CARD)
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=(5, 2))
        tk.Label(frame, text=label, font=FONT_SMALL, bg=CARD, fg=TEXT, anchor="e").pack(fill="x", pady=(0, 3))
        text = tk.Text(frame, height=height, wrap="word", font=FONT_NORMAL, bg=WHITE, fg=TEXT, relief="solid", bd=1, highlightthickness=0)
        text.pack(fill="x")
        return text

    def _build_footer(self):
        footer = tk.Frame(self, bg=CARD, height=72, highlightbackground=BORDER, highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Button(footer, text="انصراف", command=self.destroy, bg=BG, fg=TEXT, relief="solid", bd=1, cursor="hand2", font=FONT_NORMAL, padx=24, pady=8).pack(side=tk.LEFT, padx=14, pady=12)
        tk.Button(footer, text="💾 ذخیره تغییرات", command=self._save, bg=OK, fg=WHITE, activebackground=PRIMARY, relief="flat", bd=0, cursor="hand2", font=FONT_NORMAL, padx=24, pady=8).pack(side=tk.RIGHT, padx=14, pady=12)

    def _load_reference_data(self):
        try:
            equipment = EquipmentRepository(SessionLocal).get_all_equipment() or []
        except Exception:
            equipment = []
        values = []
        for item in equipment:
            if not isinstance(item, dict):
                continue
            code = _safe_text(item.get("code"))
            name = _safe_text(item.get("name"))
            display = f"{code} - {name}" if code and name else (name or code)
            if display:
                values.append(display)
                self.equipment_map[display] = item.get("id")
        self.equipment_combo.set_completion_list(sorted(set(values), key=str.casefold))

        try:
            departments = self.repository.get_departments() or []
        except Exception:
            departments = []
        names = []
        for department in departments:
            did = getattr(department, "id", None)
            name = _safe_text(getattr(department, "name", ""))
            if did and name:
                self.department_map[name] = int(did)
                names.append(name)
        self.department_combo["values"] = sorted(names, key=str.casefold)

    def _department_changed(self):
        if not hasattr(self, "completion_container"):
            return
        if getattr(self.record, "completion", None) is None:
            return
        name = self.department_var.get().strip()
        department_id = self.department_map.get(name)
        self._selected_completion_personnel_ids.clear()
        if department_id is None:
            self.completion_status_label.config(text="وضعیت: دپارتمان نامعتبر", fg=DANGER)
            self._load_completion_personnel([])
            return
        people = self.repository.get_personnel_for_department(department_id) or []
        self._load_completion_personnel(people)

    def _load_completion_personnel(self, people=None):
        if people is None:
            department_id = self.department_map.get(self.department_var.get().strip())
            people = self.repository.get_personnel_for_department(department_id) if department_id else []
        self.completion_personnel_map = {}
        self._all_completion_personnel_display = []
        for person in people or []:
            pid = getattr(person, "id", None)
            name = _safe_text(getattr(person, "full_name", ""))
            code = _safe_text(getattr(person, "personnel_code", ""))
            if pid is None or not name:
                continue
            display = " - ".join(value for value in (code, name) if value)
            self.completion_personnel_map[display] = int(pid)
            self._all_completion_personnel_display.append(display)
        self._all_completion_personnel_display.sort(key=str.casefold)
        self._render_completion_personnel()

    def _render_completion_personnel(self):
        if not hasattr(self, "personnel_listbox"):
            return
        query = self.personnel_search_var.get().strip().casefold()
        parts = [part for part in query.split() if part]
        visible = [
            value for value in self._all_completion_personnel_display
            if not parts or all(part in value.casefold() for part in parts)
        ]
        self.personnel_listbox.delete(0, tk.END)
        for value in visible:
            self.personnel_listbox.insert(tk.END, value)
            if self.completion_personnel_map.get(value) in self._selected_completion_personnel_ids:
                self.personnel_listbox.selection_set(tk.END)
        self._update_personnel_count()

    def _sync_completion_selection(self, _event=None):
        try:
            visible = [self.completion_personnel_map.get(self.personnel_listbox.get(i)) for i in range(self.personnel_listbox.size())]
            selected_indexes = set(self.personnel_listbox.curselection())
            for index, pid in enumerate(visible):
                if pid is None:
                    continue
                if index in selected_indexes:
                    self._selected_completion_personnel_ids.add(int(pid))
                else:
                    self._selected_completion_personnel_ids.discard(int(pid))
            self._update_personnel_count()
        except Exception:
            pass

    def _select_all_visible(self):
        for index in range(self.personnel_listbox.size()):
            pid = self.completion_personnel_map.get(self.personnel_listbox.get(index))
            if pid is not None:
                self._selected_completion_personnel_ids.add(int(pid))
        self._render_completion_personnel()

    def _clear_visible(self):
        for index in range(self.personnel_listbox.size()):
            pid = self.completion_personnel_map.get(self.personnel_listbox.get(index))
            if pid is not None:
                self._selected_completion_personnel_ids.discard(int(pid))
        self._render_completion_personnel()

    def _update_personnel_count(self):
        self.personnel_count_label.config(text=f"انتخاب‌شده: {len(self._selected_completion_personnel_ids):,}")

    @staticmethod
    def _parse_datetime(date_entry, time_text, label):
        selected_date = date_entry.get_date()
        if selected_date is None:
            raise ValueError(f"لطفاً {label} را انتخاب کنید.")
        text = _safe_text(time_text).replace("٫", ":").replace(".", ":")
        if text.isdigit() and len(text) == 4:
            text = text[:2] + ":" + text[2:]
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError(f"ساعت {label} باید به شکل HH:MM باشد.")
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"ساعت {label} نامعتبر است.")
        return datetime(selected_date.year, selected_date.month, selected_date.day, hour, minute)

    def _load_record(self):
        record = self.record
        self.requesting_unit_var.set(_safe_text(getattr(record, "requesting_unit", "")))
        self.equipment_var.set(_safe_text(getattr(record, "equipment_name", "")))
        self.requester_var.set(_safe_text(getattr(record, "requester_name", "")))
        self.operator_var.set(_safe_text(getattr(record, "operator_name", "")))

        breakdown = getattr(record, "breakdown_datetime", None)
        if breakdown:
            self.breakdown_date_entry.set_date(breakdown)
            self.breakdown_time_var.set(breakdown.strftime("%H:%M"))

        self._replace_text(self.description_text, _safe_text(getattr(record, "request_description", "")))

        department = getattr(record, "department", None)
        department_name = _safe_text(getattr(department, "name", ""))
        self.department_var.set(department_name)

        completion = getattr(record, "completion", None)
        if completion is None:
            self.completion_status_label.config(
                text="وضعیت: در انتظار انجام — پرسنل انجام‌دهنده پس از اتمام کار انتخاب می‌شوند.",
                fg=WARNING,
            )
            self._set_completion_enabled(False)
            return

        self.completion_status_label.config(
            text="وضعیت: انجام شده — اطلاعات اتمام و پرسنل انجام‌دهنده قابل ویرایش است.",
            fg=OK,
        )
        self._set_completion_enabled(True)

        completion_datetime = getattr(completion, "completion_datetime", None)
        if completion_datetime:
            self.completion_date_entry.set_date(completion_datetime)
            self.completion_time_var.set(completion_datetime.strftime("%H:%M"))
        self.completion_cost_var.set(str(getattr(completion, "manual_cost", 0) or 0))
        self.completion_delay_var.set(str(getattr(completion, "delay_minutes", 0) or 0))
        self._replace_text(self.finish_notes_text, _safe_text(getattr(completion, "finish_notes", "")))
        self._replace_text(self.cost_description_text, _safe_text(getattr(completion, "cost_description", "")))
        self._replace_text(self.delay_reason_text, _safe_text(getattr(completion, "delay_reason", "")))

        self._selected_completion_personnel_ids = {
            int(getattr(person, "id"))
            for person in (getattr(completion, "personnel", None) or [])
            if getattr(person, "id", None) is not None
        }
        department_id = self.department_map.get(department_name)
        self._load_completion_personnel(self.repository.get_personnel_for_department(department_id) if department_id else [])

    @staticmethod
    def _replace_text(widget, value):
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value or "")

    def _set_completion_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        widgets = [
            self.completion_time_entry,
            self.completion_cost_entry,
            self.completion_delay_entry,
            self.personnel_search_entry,
            self.personnel_listbox,
            self.finish_notes_text,
            self.cost_description_text,
            self.delay_reason_text,
        ]
        for widget in widgets:
            try:
                widget.configure(state=state)
            except Exception:
                pass
        try:
            self.completion_date_entry.entry.configure(state=state)
            self.completion_date_entry.btn.configure(state=state)
        except Exception:
            pass

    def _save(self):
        requesting_unit = _safe_text(self.requesting_unit_var.get())
        equipment_name = _safe_text(self.equipment_var.get())
        requester_name = _safe_text(self.requester_var.get())
        operator_name = _safe_text(self.operator_var.get())
        department_id = self.department_map.get(self.department_var.get().strip())

        if not requesting_unit:
            messagebox.showwarning("اطلاعات ناقص", "لطفاً «واحد متقاضی» را وارد کنید.", parent=self)
            return
        if not equipment_name:
            messagebox.showwarning("اطلاعات ناقص", "لطفاً «دستگاه / وسیله» را وارد کنید.", parent=self)
            return
        if not requester_name:
            messagebox.showwarning("اطلاعات ناقص", "لطفاً «نام درخواست‌دهنده» را وارد کنید.", parent=self)
            return
        if department_id is None:
            messagebox.showwarning("اطلاعات ناقص", "لطفاً «دپارتمان انجام‌دهنده» را انتخاب کنید.", parent=self)
            return

        try:
            breakdown_datetime = self._parse_datetime(self.breakdown_date_entry, self.breakdown_time_var.get(), "تاریخ و ساعت اعلام خرابی")
        except (TypeError, ValueError) as exc:
            messagebox.showwarning("تاریخ / ساعت", str(exc), parent=self)
            return

        completion_payload = None
        if getattr(self.record, "completion", None) is not None:
            personnel_ids = sorted(self._selected_completion_personnel_ids)
            if not personnel_ids:
                messagebox.showwarning("پرسنل انجام‌دهنده", "برای رکورد انجام‌شده حداقل یک پرسنل انجام‌دهنده انتخاب کنید.", parent=self)
                return
            try:
                completion_datetime = self._parse_datetime(self.completion_date_entry, self.completion_time_var.get(), "تاریخ و ساعت اتمام")
                manual_cost = float(self.completion_cost_var.get().strip() or 0)
                delay_minutes = int(self.completion_delay_var.get().strip() or 0)
                if manual_cost < 0 or delay_minutes < 0:
                    raise ValueError("هزینه و تأخیر نمی‌توانند منفی باشند.")
            except (TypeError, ValueError) as exc:
                messagebox.showwarning("اطلاعات اتمام", str(exc), parent=self)
                return

            completion_payload = {
                "personnel_ids": personnel_ids,
                "completion_datetime": completion_datetime,
                "finish_notes": self.finish_notes_text.get("1.0", tk.END).strip() or None,
                "manual_cost": manual_cost,
                "cost_description": self.cost_description_text.get("1.0", tk.END).strip() or None,
                "delay_minutes": delay_minutes,
                "delay_reason": self.delay_reason_text.get("1.0", tk.END).strip() or None,
            }

        try:
            success, message = self.repository.update_full(
                document_id=getattr(self.record, "id", None),
                requesting_unit=requesting_unit,
                equipment_name=equipment_name,
                breakdown_datetime=breakdown_datetime,
                operator_name=operator_name,
                requester_name=requester_name,
                request_description=self.description_text.get("1.0", tk.END).strip() or None,
                department_id=department_id,
                completion=completion_payload,
            )
        except Exception as exc:
            messagebox.showerror("خطا", f"خطا در ویرایش کامل درخواست تعمیرات:\n\n{exc}", parent=self)
            return

        if not success:
            messagebox.showerror("خطا", message, parent=self)
            return

        self.result = True
        messagebox.showinfo("موفق", message, parent=self)
        try:
            if self.callback:
                self.callback()
        except Exception:
            pass
        self.destroy()


# =============================================================================
# CREATE DIALOG
# =============================================================================

class RepairRequestCreateDialog(_ScrollableToplevel):
    """
    New repair request in its own window (like the work-order dialog).

    Same entries, rules and repository call as the old on-page form:
    واحد متقاضی، دستگاه / وسیله، دپارتمان انجام‌دهنده، نام درخواست‌دهنده،
    اپراتور، تاریخ و ساعت اعلام خرابی، شرح درخواست.  Only the Department is
    chosen here; the Personnel who did the work are chosen at completion.

    The old form shared «the selected row» with the table, so filling it in
    after clicking a row UPDATED that row instead of creating a new request.
    This window always creates.
    """

    def __init__(self, parent, repository, current_user=None):
        super().__init__(parent)
        self.repository = repository
        self.current_user = current_user or {}
        self.result = None          # id of the new request after saving

        self.requesting_unit_var = tk.StringVar()
        self.equipment_var = tk.StringVar()
        self.department_var = tk.StringVar()
        self.requester_var = tk.StringVar()
        self.operator_var = tk.StringVar()
        self.breakdown_time_var = tk.StringVar()
        self.department_map: dict[str, int] = {}

        self._build()
        self._load_reference_data()
        self._set_defaults()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(120, self._focus_first)

    # -------------------------------------------------------------- layout
    def _build(self):
        body = self._init_scrollable_body(
            header_title="🛠 ثبت درخواست تعمیرات جدید",
            width=900,
            height=640,
        )
        card = tk.Frame(body, bg=CARD, bd=0, relief="solid", highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", padx=12, pady=12)
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=16, pady=12)
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=0)

        row = 0
        tk.Label(
            inner,
            text="در زمان ثبت درخواست فقط دپارتمان انتخاب می‌شود؛ پرسنل هنگام اتمام کار انتخاب می‌شوند.",
            font=FONT_SMALL, bg=CARD, fg=SUBTLE, anchor="e", justify="right",
        ).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        row += 1

        self.requesting_unit_entry = self._entry(inner, row, "واحد متقاضی *", self.requesting_unit_var)
        row += 1

        self._label(inner, row, "دستگاه / وسیله *")
        self.equipment_combo = FilteredSearchCombobox(inner, textvariable=self.equipment_var, justify="right", font=FONT_NORMAL)
        self.equipment_combo.grid(row=row, column=0, sticky="ew", pady=7, ipady=3)
        row += 1

        self._label(inner, row, "دپارتمان انجام‌دهنده *")
        self.department_combo = ttk.Combobox(inner, textvariable=self.department_var, state="readonly", justify="right", font=FONT_NORMAL)
        self.department_combo.grid(row=row, column=0, sticky="ew", pady=7, ipady=3)
        row += 1

        self.requester_entry = self._entry(inner, row, "نام درخواست‌دهنده *", self.requester_var)
        row += 1
        self.operator_entry = self._entry(inner, row, "اپراتور", self.operator_var)
        row += 1

        self._label(inner, row, "تاریخ و ساعت اعلام خرابی *")
        date_host = tk.Frame(inner, bg=CARD)
        date_host.grid(row=row, column=0, sticky="ew", pady=7)
        self.breakdown_date_entry = JalaliDateEntry(date_host, width=15)
        self.breakdown_date_entry.pack(side=tk.RIGHT, padx=(0, 2))
        tk.Label(date_host, text="ساعت", font=FONT_SMALL, bg=CARD, fg=SUBTLE).pack(side=tk.RIGHT, padx=6)
        self.breakdown_time_entry = ttk.Entry(date_host, textvariable=self.breakdown_time_var, width=8, justify="center")
        self.breakdown_time_entry.pack(side=tk.RIGHT, ipady=4)
        tk.Button(
            date_host, text="اکنون", command=self._set_now, bg=BG, fg=TEXT, relief="solid", bd=1,
            cursor="hand2", font=FONT_SMALL, padx=10, pady=2,
        ).pack(side=tk.RIGHT, padx=8)
        row += 1

        self._label(inner, row, "شرح درخواست", anchor="ne")
        self.description_text = tk.Text(inner, height=6, wrap="word", font=FONT_NORMAL, bg=WHITE, fg=TEXT,
                                        relief="solid", bd=1, highlightthickness=0, insertbackground=TEXT)
        self.description_text.grid(row=row, column=0, sticky="ew", pady=7)
        row += 1

        self._build_footer()
        self.bind("<Control-Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self._cancel())

    @staticmethod
    def _label(parent, row, text, anchor="e"):
        tk.Label(parent, text=text, font=FONT_SMALL, bg=CARD, fg=TEXT, anchor=anchor, width=20).grid(
            row=row, column=1, sticky="ne" if anchor == "ne" else "e", padx=(12, 0), pady=7)

    def _entry(self, parent, row, label, variable):
        self._label(parent, row, label)
        entry = ttk.Entry(parent, textvariable=variable, justify="right")
        entry.grid(row=row, column=0, sticky="ew", pady=7, ipady=4)
        return entry

    def _build_footer(self):
        footer = tk.Frame(self, bg=CARD, height=68, highlightbackground=BORDER, highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Button(footer, text="انصراف", command=self._cancel, bg=BG, fg=TEXT, relief="solid", bd=1,
                  cursor="hand2", font=FONT_NORMAL, padx=24, pady=8).pack(side=tk.LEFT, padx=14, pady=12)
        self.save_button = tk.Button(footer, text="💾 ثبت درخواست", command=self._save, bg=OK, fg=WHITE,
                                     activebackground=PRIMARY, relief="flat", bd=0, cursor="hand2",
                                     font=FONT_NORMAL, padx=24, pady=8)
        self.save_button.pack(side=tk.RIGHT, padx=14, pady=12)
        tk.Label(footer, text="Ctrl+S: ثبت   •   Esc: انصراف", font=FONT_SMALL, bg=CARD,
                 fg=SUBTLE).pack(side=tk.RIGHT, padx=8)

    # ---------------------------------------------------------------- data
    def _load_reference_data(self):
        try:
            equipment = EquipmentRepository(SessionLocal).get_all_equipment() or []
        except Exception:
            equipment = []
        values = []
        for item in equipment:
            if not isinstance(item, dict):
                continue
            code = _safe_text(item.get("code"))
            name = _safe_text(item.get("name"))
            display = f"{code} - {name}" if code and name else (name or code)
            if display:
                values.append(display)
        self.equipment_combo.set_completion_list(sorted(set(values), key=str.casefold))

        try:
            departments = self.repository.get_departments() or []
        except Exception as exc:
            departments = []
            messagebox.showerror("خطا", f"دریافت دپارتمان‌ها انجام نشد:\n\n{exc}", parent=self)
        names = []
        for department in departments:
            did = getattr(department, "id", None)
            name = _safe_text(getattr(department, "name", ""))
            if did is not None and name:
                self.department_map[name] = int(did)
                names.append(name)
        self.department_combo["values"] = sorted(set(names), key=str.casefold)

    def _set_now(self):
        now = tehran_now()
        try:
            self.breakdown_date_entry.set_date(now)
        except Exception:
            pass
        self.breakdown_time_var.set(now.strftime("%H:%M"))

    def _set_defaults(self):
        self._set_now()
        self._initial = self._snapshot()

    def _snapshot(self):
        try:
            day = self.breakdown_date_entry.get_date()
        except Exception:
            day = None
        return (
            self.requesting_unit_var.get(), self.equipment_var.get(), self.department_var.get(),
            self.requester_var.get(), self.operator_var.get(), self.breakdown_time_var.get(), day,
            self.description_text.get("1.0", tk.END).strip(),
        )

    def _focus_first(self):
        try:
            self.requesting_unit_entry.focus_set()
        except Exception:
            pass

    # ------------------------------------------------------------- actions
    def _cancel(self):
        if self.result is None and self._snapshot() != getattr(self, "_initial", None):
            if not messagebox.askyesno(
                "انصراف",
                "اطلاعات واردشده ذخیره نشده است. پنجره بسته شود؟",
                parent=self,
            ):
                return
        self.destroy()

    def _save(self):
        from views.ux import field_error, clear_all_field_errors
        clear_all_field_errors(self)

        requesting_unit = _safe_text(self.requesting_unit_var.get())
        equipment_name = _safe_text(self.equipment_var.get())
        department_name = self.department_var.get().strip()
        department_id = self.department_map.get(department_name)
        requester_name = _safe_text(self.requester_var.get())
        operator_name = _safe_text(self.operator_var.get())
        description = self.description_text.get("1.0", tk.END).strip() or None

        # Every missing field is marked at once; the first one gets the focus.
        problems = []
        if not requesting_unit:
            problems.append((self.requesting_unit_entry, "«واحد متقاضی» را وارد کنید."))
        if not equipment_name:
            problems.append((self.equipment_combo, "«دستگاه / وسیله» را وارد یا انتخاب کنید."))
        if department_id is None:
            problems.append((self.department_combo, "«دپارتمان انجام‌دهنده» را انتخاب کنید."))
        if not requester_name:
            problems.append((self.requester_entry, "«نام درخواست‌دهنده» را وارد کنید."))

        breakdown_datetime = None
        try:
            breakdown_datetime = RepairRequestFullEditDialog._parse_datetime(
                self.breakdown_date_entry, self.breakdown_time_var.get(), "تاریخ و ساعت اعلام خرابی")
        except (TypeError, ValueError) as exc:
            problems.append((self.breakdown_time_entry, str(exc)))

        if problems:
            for index, (widget, text) in enumerate(problems):
                field_error(widget, text, focus=index == 0)
            return

        user_id = self.current_user.get("id") if isinstance(self.current_user, dict) else None
        try:
            self.save_button.configure(state="disabled")
            success, message, record = self.repository.create(
                requesting_unit=requesting_unit,
                equipment_name=equipment_name,
                breakdown_datetime=breakdown_datetime,
                operator_name=operator_name,
                requester_name=requester_name,
                request_description=description,
                created_by_user_id=user_id,
                department_id=department_id,
            )
        except Exception as exc:
            messagebox.showerror("خطا", f"ثبت درخواست تعمیرات با خطا مواجه شد:\n\n{exc}", parent=self)
            return
        finally:
            try:
                self.save_button.configure(state="normal")
            except Exception:
                pass

        if not success:
            messagebox.showerror("خطا", message, parent=self)
            return

        self.result = getattr(record, "id", None) or True
        self.message = message
        self.destroy()


# =============================================================================
# PDF SELECTION DIALOG
# =============================================================================

class RepairRequestPrintSelectionDialog(_ScrollableToplevel):
    def __init__(self, parent, records):
        super().__init__(parent)
        self.records = list(records or [])
        self.result = None
        body = self._init_scrollable_body(
            header_title="🖨️ انتخاب درخواست‌های تعمیرات برای چاپ PDF",
            width=1100,
            height=700,
        )
        self._build_body(body)
        self._build_footer()

    def _build_body(self, body):
        card = tk.Frame(body, bg=CARD, bd=0, relief="solid", highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(card, text="درخواست‌های قابل چاپ", font=FONT_HEADING, bg=CARD, fg=PRIMARY, anchor="e").pack(fill="x", padx=18, pady=(15, 8))

        table_frame = tk.Frame(card, bg=CARD)
        table_frame.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        columns = ("id", "department", "equipment", "requester", "status", "breakdown")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        headings = {
            "id": "شناسه",
            "department": "دپارتمان",
            "equipment": "دستگاه / وسیله",
            "requester": "درخواست‌دهنده",
            "status": "وضعیت",
            "breakdown": "اعلام خرابی",
        }
        widths = {"id": 70, "department": 160, "equipment": 220, "requester": 160, "status": 120, "breakdown": 170}
        for cid in columns:
            self.tree.heading(cid, text=headings[cid], anchor="center")
            self.tree.column(cid, width=widths[cid], minwidth=70, anchor="e")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree["displaycolumns"] = tuple(reversed(columns))   # RTL: شناسه on the right
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        for index, record in enumerate(self.records):
            department = getattr(getattr(record, "department", None), "name", "") or "—"
            status = "انجام شده" if getattr(record, "completion", None) is not None else "در انتظار انجام"
            self.tree.insert(
                "", "end", iid=str(index), values=(
                    getattr(record, "id", ""),
                    department,
                    _safe_text(getattr(record, "equipment_name", "")),
                    _safe_text(getattr(record, "requester_name", "")),
                    status,
                    _format_jalali_datetime(getattr(record, "breakdown_datetime", None)),
                )
            )

        controls = tk.Frame(card, bg=CARD)
        controls.pack(fill="x", padx=14, pady=(0, 12))
        self.count_label = tk.Label(controls, text="موارد انتخاب‌شده: ۰", bg=CARD, fg=SUBTLE, font=FONT_SMALL)
        self.count_label.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="انتخاب همه", command=self._select_all, bg=BG, fg=TEXT, relief="solid", bd=1, font=FONT_SMALL, cursor="hand2", padx=12, pady=4).pack(side=tk.RIGHT, padx=3)
        tk.Button(controls, text="لغو انتخاب", command=self._clear_all, bg=BG, fg=TEXT, relief="solid", bd=1, font=FONT_SMALL, cursor="hand2", padx=12, pady=4).pack(side=tk.RIGHT, padx=3)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_count())

    def _select_all(self):
        children = self.tree.get_children("")
        if children:
            self.tree.selection_set(children)
        self._update_count()

    def _clear_all(self):
        self.tree.selection_remove(self.tree.selection())
        self._update_count()

    def _update_count(self):
        self.count_label.config(text=f"موارد انتخاب‌شده: {len(self.tree.selection()):,}")

    def _build_footer(self):
        footer = tk.Frame(self, bg=CARD, height=72, highlightbackground=BORDER, highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Button(footer, text="انصراف", command=self.destroy, bg=BG, fg=TEXT, relief="solid", bd=1, cursor="hand2", font=FONT_NORMAL, padx=24, pady=8).pack(side=tk.LEFT, padx=14, pady=12)
        tk.Button(footer, text="تأیید انتخاب و چاپ", command=self._confirm, bg=PRIMARY, fg=WHITE, activebackground=PRIMARY_LIGHT, relief="flat", bd=0, cursor="hand2", font=FONT_NORMAL, padx=24, pady=8).pack(side=tk.RIGHT, padx=14, pady=12)

    def _confirm(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("انتخاب", "حداقل یک درخواست تعمیرات را برای چاپ انتخاب کنید.", parent=self)
            return
        # keep the on-screen order, not the click order
        order = {iid: n for n, iid in enumerate(self.tree.get_children(""))}
        self.result = [self.records[int(i)] for i in sorted(selection, key=lambda x: order.get(x, 0))]
        self.destroy()


# =============================================================================
# MAIN VIEW
# =============================================================================

class RepairRequestView(tk.Frame):
    """Professional repair-request management page."""

    def __init__(self, parent, current_user=None, repository=None, equipment_repo=None):
        super().__init__(parent, bg=BG)
        self.current_user = current_user or {}
        self.repository = repository or RepairRequestRepository(SessionLocal)
        self.equipment_repo = equipment_repo or EquipmentRepository(SessionLocal)

        # built-in roles as before; custom roles from «مدیریت نقش‌ها»
        from auth.auth_manager import AuthManager
        self.can_write = AuthManager.allows({"admin", "manager", "production_expert", "technician"},
                                            "repair_request", "write")
        self.can_delete = AuthManager.allows({"admin", "manager"}, "repair_request", "delete")

        self.records = []
        self.filtered_records = []
        self.selected_record = None

        self.search_var = tk.StringVar()
        self.requesting_unit_var = tk.StringVar()
        self.equipment_var = tk.StringVar()
        self.department_var = tk.StringVar()
        self.breakdown_time_var = tk.StringVar()
        self.requester_var = tk.StringVar()
        self.operator_var = tk.StringVar()

        self.department_map = {}
        self.status_var = tk.StringVar(value="آماده")
        self.count_var = tk.StringVar(value="تعداد رکوردها: ۰")

        self._build_styles()
        self._build_ui()
        self._load_records()

    # ------------------------------------------------------------------
    # STYLES
    # ------------------------------------------------------------------

    def _build_styles(self):
        style = ttk.Style(self)
        try:
            from utils.theme import ensure_theme
            ensure_theme(style)  # never switch the global ttk theme per page
        except Exception:
            pass

        style.configure("Repair.Treeview", background=WHITE, foreground=TEXT, fieldbackground=WHITE, rowheight=36, font=FONT_SMALL, borderwidth=0)
        style.configure("Repair.Treeview.Heading", background=PRIMARY, foreground=WHITE, font=FONT_SMALL, relief="flat", padding=(8, 8))
        style.map("Repair.Treeview", background=[("selected", PRIMARY_LIGHT)], foreground=[("selected", WHITE)])
        style.configure("Repair.Vertical.TScrollbar", background=PRIMARY, troughcolor=BG, arrowcolor=WHITE, bordercolor=BG)
        style.configure("Repair.Horizontal.TScrollbar", background=PRIMARY, troughcolor=BG, arrowcolor=WHITE, bordercolor=BG)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self, bg=PRIMARY, height=84)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        title_box = tk.Frame(header, bg=PRIMARY)
        title_box.pack(side=tk.RIGHT, fill="y", padx=24)
        tk.Label(title_box, text="🛠  صدور حکم درخواست تعمیرات", font=FONT_TITLE, bg=PRIMARY, fg=WHITE, anchor="e").pack(anchor="e", pady=(12, 0))
        tk.Label(title_box, text="ثبت درخواست، تعیین دپارتمان انجام‌دهنده، ثبت اتمام و انتخاب پرسنل واقعی انجام‌دهنده", font=FONT_SMALL, bg=PRIMARY, fg=WHITE, anchor="e").pack(anchor="e", pady=(2, 8))

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=18, pady=14)

        self._build_action_bar(content)
        self._build_search_card(content)
        self._build_table_card(content)

        status = tk.Frame(content, bg=BG)
        status.pack(fill="x", pady=(8, 0))
        tk.Label(status, textvariable=self.status_var, font=FONT_SMALL, bg=BG, fg=SUBTLE, anchor="e").pack(side=tk.RIGHT)
        tk.Label(status, textvariable=self.count_var, font=FONT_SMALL, bg=BG, fg=PRIMARY, anchor="w").pack(side=tk.LEFT)

    def _button(self, parent, text, command, bg, fg=WHITE, width=14, **kwargs):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=kwargs.pop("activebackground", bg),
            activeforeground=kwargs.pop("activeforeground", fg),
            relief=kwargs.pop("relief", "flat"),
            bd=kwargs.pop("bd", 0),
            highlightthickness=0,
            cursor="hand2",
            font=FONT_NORMAL,
            width=width,
            padx=8,
            pady=7,
            **kwargs,
        )

    def _build_action_bar(self, parent):
        outer = tk.Frame(parent, bg=BORDER)
        outer.pack(fill="x", pady=(0, 12))
        bar = tk.Frame(outer, bg=CARD)
        bar.pack(fill="x", padx=1, pady=1)

        right = tk.Frame(bar, bg=CARD)
        right.pack(side=tk.RIGHT, fill="x", padx=8, pady=7)
        self.new_button = self._button(right, "＋ درخواست جدید", self._new_record, OK, width=15)
        self.new_button.pack(side=tk.RIGHT, padx=3)
        self.edit_button = self._button(right, "✎ ویرایش کامل", self._edit_selected, PRIMARY, width=15, activebackground=PRIMARY_LIGHT)
        self.edit_button.pack(side=tk.RIGHT, padx=3)
        self.finish_button = self._button(right, "✅ ثبت اتمام کار", self._finish_selected, OK, width=16)
        self.finish_button.pack(side=tk.RIGHT, padx=3)
        if self.can_delete:
            self.delete_button = self._button(right, "🗑 حذف", self._delete_selected, DANGER, width=10, activebackground="#B91C1C")
            self.delete_button.pack(side=tk.RIGHT, padx=3)

        left = tk.Frame(bar, bg=CARD)
        left.pack(side=tk.LEFT, padx=8, pady=7)
        self.refresh_button = self._button(left, "↻ بروزرسانی", self._load_records, BG, TEXT, width=13, relief="solid", bd=1)
        self.refresh_button.pack(side=tk.LEFT, padx=3)
        self.pdf_button = self._button(left, "📄 PDF چاپی", self._export_pdf, "#7C3AED", width=15, activebackground="#6D28D9")
        self.pdf_button.pack(side=tk.LEFT, padx=3)
        self.excel_button = self._button(left, "📤 خروجی Excel", self._export_excel, "#0D9488", width=16)
        self.excel_button.pack(side=tk.LEFT, padx=3)

        # One main action per page: «درخواست جدید»; the rest are secondary.
        try:
            from views.ux import style_button
            style_button(self.new_button, "primary")
            style_button(self.edit_button, "outline")
            style_button(self.finish_button, "outline")
            style_button(self.refresh_button, "outline")
        except Exception:
            pass

    def _build_search_card(self, parent):
        outer = tk.Frame(parent, bg=BORDER)
        outer.pack(fill="x", pady=(0, 12))
        card = tk.Frame(outer, bg=CARD)
        card.pack(fill="x", padx=1, pady=1)
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=15, pady=10)
        row.grid_columnconfigure(0, weight=1)
        tk.Label(row, text="جستجوی سریع:", font=FONT_NORMAL, bg=CARD, fg=TEXT).grid(row=0, column=1, padx=(0, 8))
        self.search_entry = tk.Entry(row, textvariable=self.search_var, font=FONT_NORMAL, bg=WHITE, fg=TEXT, relief="solid", bd=1, highlightthickness=0, justify="right", insertbackground=TEXT)
        self.search_entry.grid(row=0, column=0, sticky="ew", ipady=6)
        self.search_entry.bind("<KeyRelease>", lambda _e: self._apply_search())
        tk.Button(row, text="✕ پاک کردن", command=self._clear_search, bg=BG, fg=TEXT, relief="solid", bd=1, cursor="hand2", font=FONT_SMALL, padx=12, pady=6).grid(row=0, column=2, padx=6)
        tk.Button(row, text="🔍 جستجو", command=self._apply_search, bg=PRIMARY, fg=WHITE, relief="flat", bd=0, cursor="hand2", font=FONT_SMALL, padx=14, pady=7).grid(row=0, column=3)

    def _build_table_card(self, parent):
        outer = tk.Frame(parent, bg=BORDER)
        outer.pack(fill="both", expand=True)
        card = tk.Frame(outer, bg=CARD)
        card.pack(fill="both", expand=True, padx=1, pady=1)

        title = tk.Frame(card, bg=CARD)
        title.pack(fill="x", padx=15, pady=(12, 8))
        tk.Label(title, text="سوابق درخواست‌های تعمیرات", font=FONT_HEADING, bg=CARD, fg=PRIMARY, anchor="e").pack(side=tk.RIGHT)
        tk.Label(title, text="دابل‌کلیک = ویرایش کامل | دپارتمان در درخواست | پرسنل در اتمام", font=FONT_SMALL, bg=CARD, fg=SUBTLE, anchor="e").pack(side=tk.RIGHT, padx=15)

        frame = tk.Frame(card, bg=CARD)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        columns = (
            "id", "department", "requesting_unit", "equipment", "breakdown",
            "requester", "status", "personnel", "completion",
        )
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", style="Repair.Treeview", selectmode="browse")
        headings = {
            "id": "شناسه",
            "department": "دپارتمان",
            "requesting_unit": "واحد متقاضی",
            "equipment": "دستگاه / وسیله",
            "breakdown": "اعلام خرابی",
            "requester": "درخواست‌دهنده",
            "status": "وضعیت",
            "personnel": "پرسنل انجام‌دهنده",
            "completion": "اتمام",
        }
        widths = {
            "id": 65, "department": 150, "requesting_unit": 145, "equipment": 210,
            "breakdown": 170, "requester": 150, "status": 115, "personnel": 260,
            "completion": 170,
        }
        for cid in columns:
            self.tree.heading(cid, text=headings[cid], anchor="center")
            self.tree.column(cid, width=widths[cid], minwidth=70, anchor="e", stretch=True)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview, style="Repair.Vertical.TScrollbar")
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview, style="Repair.Horizontal.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Delete>", self._on_delete_key)

    # ------------------------------------------------------------------
    # REFERENCE DATA
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # LOAD / SEARCH / TABLE
    # ------------------------------------------------------------------

    def _load_records(self):
        try:
            self.records = list(self.repository.get_all() or [])
            self._apply_search()
            self.status_var.set("سوابق درخواست‌های تعمیرات بروزرسانی شد.")
        except Exception as exc:
            self.records = []
            self.filtered_records = []
            self._refresh_table()
            self.status_var.set(f"خطا در دریافت سوابق: {exc}")
            messagebox.showerror("خطا", f"دریافت سوابق درخواست تعمیرات با خطا مواجه شد:\n\n{exc}", parent=self)

    def _apply_search(self):
        keyword = _safe_text(self.search_var.get()).casefold()
        if not keyword:
            self.filtered_records = list(self.records)
        else:
            parts = [part for part in keyword.split() if part]
            filtered = []
            for record in self.records:
                completion = getattr(record, "completion", None)
                values = [
                    getattr(record, "id", ""),
                    getattr(record, "requesting_unit", ""),
                    getattr(record, "equipment_name", ""),
                    getattr(record, "requester_name", ""),
                    getattr(record, "operator_name", ""),
                    getattr(record, "request_description", ""),
                    getattr(getattr(record, "department", None), "name", ""),
                    "انجام شده" if completion else "در انتظار انجام",
                ]
                if completion:
                    values.extend([
                        getattr(completion, "finish_notes", ""),
                        getattr(completion, "completion_datetime", ""),
                    ])
                    for person in (getattr(completion, "personnel", None) or []):
                        values.extend([getattr(person, "full_name", ""), getattr(person, "personnel_code", "")])
                haystack = " ".join(str(value or "") for value in values).casefold()
                if all(part in haystack for part in parts):
                    filtered.append(record)
            self.filtered_records = filtered
        self._refresh_table()

    def _clear_search(self):
        self.search_var.set("")
        self._apply_search()
        self.search_entry.focus_set()

    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for record in self.filtered_records:
            completion = getattr(record, "completion", None)
            department = _safe_text(getattr(getattr(record, "department", None), "name", "")) or "—"
            people = []
            if completion:
                for person in (getattr(completion, "personnel", None) or []):
                    code = _safe_text(getattr(person, "personnel_code", ""))
                    name = _safe_text(getattr(person, "full_name", ""))
                    people.append(" - ".join(value for value in (code, name) if value))
            status = "انجام شده" if completion else "در انتظار انجام"
            self.tree.insert(
                "", "end", iid=str(getattr(record, "id", "")), values=(
                    getattr(record, "id", ""),
                    department,
                    _safe_text(getattr(record, "requesting_unit", "")) or "—",
                    _safe_text(getattr(record, "equipment_name", "")) or "—",
                    _format_jalali_datetime(getattr(record, "breakdown_datetime", None)),
                    _safe_text(getattr(record, "requester_name", "")) or "—",
                    status,
                    "، ".join(people) if people else "—",
                    _format_jalali_datetime(getattr(completion, "completion_datetime", None)) if completion else "—",
                )
            )

        self.count_var.set(f"تعداد رکوردها: {len(self.filtered_records):,}")

    # ------------------------------------------------------------------
    # FORM
    # ------------------------------------------------------------------

    def _new_record(self):
        """«＋ درخواست جدید»: the request is entered in its own window."""
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ثبت درخواست تعمیرات نیستید.", parent=self)
            return
        dialog = RepairRequestCreateDialog(self, self.repository, self.current_user)
        self.wait_window(dialog)
        if not dialog.result:
            return
        self._load_records()
        new_id = str(dialog.result) if dialog.result is not True else None
        if new_id and self.tree.exists(new_id):
            self.tree.selection_set(new_id)
            self.tree.focus(new_id)
            self.tree.see(new_id)
        messagebox.showinfo("موفق", getattr(dialog, "message", "درخواست تعمیرات ثبت شد."), parent=self)

    # ------------------------------------------------------------------
    # SELECTION / EDIT / FINISH
    # ------------------------------------------------------------------

    def _on_tree_select(self, _event=None):
        selection = self.tree.selection()
        self.selected_record = None
        if not selection:
            return
        try:
            record_id = int(selection[0])
        except Exception:
            return
        for record in self.records:
            if getattr(record, "id", None) == record_id:
                self.selected_record = record
                break

    def _on_double_click(self, _event=None):
        self._edit_selected()

    def _on_delete_key(self, _event=None):
        if self.can_delete:
            self._delete_selected()

    def _edit_selected(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ویرایش نیستید.", parent=self)
            return
        record = self.selected_record
        if record is None:
            selection = self.tree.selection()
            if selection:
                self._on_tree_select()
                record = self.selected_record
        if record is None:
            messagebox.showwarning("انتخاب رکورد", "لطفاً ابتدا یک درخواست تعمیرات را انتخاب کنید.", parent=self)
            return

        try:
            fresh_record = self.repository.get_by_id(getattr(record, "id", None))
        except Exception as exc:
            messagebox.showerror("خطا", f"دریافت آخرین اطلاعات رکورد برای ویرایش انجام نشد:\n\n{exc}", parent=self)
            return
        if fresh_record is None:
            messagebox.showerror("خطا", "رکورد موردنظر پیدا نشد.", parent=self)
            return

        dialog = RepairRequestFullEditDialog(self, self.repository, fresh_record, callback=self._load_records)
        self.wait_window(dialog)
        if dialog.result:
            self.selected_record = None

    def _finish_selected(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ثبت اتمام کار نیستید.", parent=self)
            return
        record = self.selected_record
        if record is None:
            selection = self.tree.selection()
            if selection:
                self._on_tree_select()
                record = self.selected_record
        if record is None:
            messagebox.showwarning("انتخاب رکورد", "لطفاً ابتدا یک درخواست تعمیرات را انتخاب کنید.", parent=self)
            return

        try:
            record = self.repository.get_by_id(getattr(record, "id", None))
        except Exception as exc:
            messagebox.showerror("خطا", f"دریافت آخرین اطلاعات درخواست انجام نشد:\n\n{exc}", parent=self)
            return
        if record is None:
            messagebox.showerror("خطا", "رکورد موردنظر پیدا نشد.", parent=self)
            return
        if getattr(record, "completion", None) is not None:
            messagebox.showwarning("اتمام قبلی", "این درخواست قبلاً انجام‌شده ثبت شده است. برای تغییر اطلاعات اتمام از «ویرایش کامل» استفاده کنید.", parent=self)
            return
        if getattr(record, "department_id", None) is None:
            messagebox.showwarning("دپارتمان", "این درخواست هنوز دپارتمان انجام‌دهنده ندارد. ابتدا آن را ویرایش و دپارتمان را انتخاب کنید.", parent=self)
            return

        dialog = RepairRequestFinishDialog(self, self.repository, record)
        self.wait_window(dialog)
        if not dialog.result:
            return

        user_id = self.current_user.get("id") if isinstance(self.current_user, dict) else None
        ok, message, _completion = self.repository.request_finish(
            getattr(record, "id", None),
            personnel_ids=dialog.personnel_ids,
            completion_datetime=dialog.completion_datetime,
            finish_notes=dialog.finish_notes,
            manual_cost=dialog.manual_cost,
            cost_description=dialog.cost_description,
            delay_minutes=dialog.delay_minutes,
            delay_reason=dialog.delay_reason,
            completed_by_user_id=user_id,
        )
        if ok:
            messagebox.showinfo("موفق", message, parent=self)
            self._load_records()
        else:
            messagebox.showerror("خطا", message, parent=self)

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def _delete_selected(self):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "فقط مدیر یا مدیر سیستم مجاز به حذف درخواست تعمیرات است.", parent=self)
            return

        record = self.selected_record
        if record is None:
            selection = self.tree.selection()
            if selection:
                self._on_tree_select()
                record = self.selected_record
        if record is None:
            messagebox.showwarning("انتخاب رکورد", "لطفاً ابتدا یک درخواست تعمیرات را انتخاب کنید.", parent=self)
            return

        if not messagebox.askyesno(
            "تأیید حذف",
            (
                "آیا از حذف این درخواست تعمیرات مطمئن هستید؟\n\n"
                f"شناسه: {getattr(record, 'id', '—')}\n"
                f"دستگاه: {_safe_text(getattr(record, 'equipment_name', ''))}\n\n"
                "رکورد completion وابسته نیز حذف خواهد شد."
            ),
            parent=self,
        ):
            return

        try:
            success, message = self.repository.delete(getattr(record, "id", None))
        except Exception as exc:
            messagebox.showerror("خطا", f"حذف درخواست تعمیرات با خطا مواجه شد:\n\n{exc}", parent=self)
            return

        if not success:
            messagebox.showerror("خطا", message, parent=self)
            return

        self.selected_record = None
        self._load_records()
        messagebox.showinfo("موفق", message, parent=self)

    # ------------------------------------------------------------------
    # EXPORTS
    # ------------------------------------------------------------------

    def _records_for_export(self):
        """
        The requests shown in the table (all of them when there is no search).
        Was «filtered or all»: a search that matched NOTHING exported everything.
        """
        return list(self.filtered_records or [])

    def _export_excel(self):
        records = self._records_for_export()
        if not records:
            messagebox.showwarning("خروجی Excel", "هیچ درخواست تعمیراتی در جدول نیست (جستجو را بررسی کنید).", parent=self)
            return
        try:
            from views.export_dialog import run_repair_request_export
            run_repair_request_export(self, records, self.selected_record)
        except Exception as exc:
            messagebox.showerror("خطا در Excel", f"باز کردن خروجی Excel با خطا مواجه شد:\n\n{exc}", parent=self)

    def _export_pdf(self):
        records = self._records_for_export()
        if not records:
            messagebox.showwarning("خروجی PDF", "هیچ درخواست تعمیراتی در جدول نیست (جستجو را بررسی کنید).", parent=self)
            return

        selector = RepairRequestPrintSelectionDialog(self, records)
        self.wait_window(selector)
        if not selector.result:
            return

        selected = selector.result
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"RepairRequests_Print_{jalali_stamp()}.pdf",
        )
        if not path:
            return

        try:
            from views.ui_kit import busy
            with busy(self):
                export_repair_requests_pdf(selected, path)
            from services.pdf_service import ROWS_PER_PAGE
            pages = (len(selected) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
            messagebox.showinfo("موفق", f"PDF با موفقیت ایجاد شد.\n\nتعداد درخواست: {len(selected):,}\nتعداد صفحات: {pages:,}", parent=self)
            try:
                os.startfile(os.path.abspath(path))
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("خطا در PDF", f"ایجاد PDF با خطا مواجه شد:\n\n{exc}", parent=self)

    def refresh(self):
        self._load_records()

    def _on_show(self):
        self.refresh()

    # ------------------------------------------------------------------
    # GLOBAL KEYBOARD HANDLERS  (called by MainView)
    # ------------------------------------------------------------------

    def handle_f2(self):
        """Called when F2 is pressed while this view is active."""
        self._edit_selected()

    def handle_new(self):
        """Called when Ctrl+N is pressed while this view is active."""
        self._new_record()

    def handle_delete(self):
        """Called when Delete is pressed while this view is active."""
        self._delete_selected()

    def handle_enter(self):
        """Called when Enter is pressed while this view is active."""
        self._edit_selected()

    def ux_footer_spec(self):
        """Filters shown as removable chips under the table (views/ux.py)."""
        return {"filters": [("جستجو", self.search_var, "")], "apply": self._apply_search,
                "total": lambda: len(getattr(self, "records", None) or []),
                "noun": "درخواست"}

