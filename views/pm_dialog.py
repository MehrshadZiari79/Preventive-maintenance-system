# views/pm_dialog.py
"""
PM System - Preventive Maintenance Dialog
==========================================

FINAL WORKFLOW
--------------

PM CREATION / EDIT
------------------
A PM schedule contains:

    - Title
    - Equipment
    - Department
    - Frequency
    - Interval
    - First due date
    - Checklist
    - Estimated duration
    - Notes
    - Required parts

A User/technician is NOT assigned here.

Department is selected here.

ACTUAL PM EXECUTION
-------------------
When the PM-generated Work Order is actually completed:

    Work Order Department
            ↓
    Personnel from that exact Department
            ↓
    Personnel selected
            ↓
    completed_by_personnel_id

This dialog therefore NEVER asks for Personnel.

IMPORTANT
---------
The user_repo argument is retained because MainView and PMView already
pass it. It is not used for technician assignment.
"""

import json
import tkinter as tk
from views.ui_kit import rtl_columns  # RTL (right-to-left) table columns
from tkinter import ttk, messagebox
from views.ux import field_error

from database.db import SessionLocal
from database.spare_parts_repository import SparePartsRepository
from database.department_repository import DepartmentRepository

from views.jalali_date_entry import JalaliDateEntry
from views.searchable_combobox import SearchableCombobox

from utils.theme import (
    NAVY,
    NAVY_LIGHT,
    WHITE,
    RED,
    GRAY_BG,
    GRAY_BORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    SUCCESS,
    FONT_HEADING,
    FONT_NORMAL,
    FONT_SMALL,
)


# ============================================================================
# THEME
# ============================================================================

BG = GRAY_BG
CARD_BG = WHITE
PRIMARY = NAVY
DANGER = RED
OK = SUCCESS
TEXT = TEXT_DARK
SUBTLE = TEXT_LIGHT
BORDER = GRAY_BORDER


# ============================================================================
# FREQUENCIES
# ============================================================================

FREQ_FA_MAP = {
    "daily": "روزانه",
    "weekly": "هفتگی",
    "monthly": "ماهانه",
    "quarterly": "سه‌ماهه",
    "biannual": "شش‌ماهه",
    "annual": "سالانه",
    "custom": "سفارشی",
}

FREQ_EN_MAP = {
    value: key
    for key, value in FREQ_FA_MAP.items()
}

FREQ_DAYS = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
    "biannual": 180,
    "annual": 365,
}


# ============================================================================
# HELPERS
# ============================================================================

def _safe_id(item):
    if item is None:
        return None

    value = getattr(
        item,
        "id",
        None,
    )

    if value is not None:
        return value

    if isinstance(item, dict):
        return item.get("id")

    return None


def _safe_name(item):
    if item is None:
        return ""

    if isinstance(item, str):
        return item.strip()

    value = getattr(
        item,
        "name",
        None,
    )

    if value is not None:
        return str(value).strip()

    if isinstance(item, dict):
        return str(
            item.get("name")
            or ""
        ).strip()

    return ""


# ============================================================================
# PM DIALOG
# ============================================================================

class PMDialog(tk.Toplevel):

    def __init__(
        self,
        parent,
        pm_repo,
        equipment_repo,
        user_repo,
        schedule=None,
        callback=None,
    ):
        super().__init__(parent)

        self.parent = parent
        self.pm_repo = pm_repo
        self.equipment_repo = equipment_repo

        # Kept for compatibility with existing callers.
        self.user_repo = user_repo

        self.schedule = schedule
        self.callback = callback

        self.result = False

        self.equipment_map = {}
        self.department_map = {}

        self.all_parts = []
        self.selected_parts = []

        self.sp_repo = None

        # ------------------------------------------------------------------
        # Window
        # ------------------------------------------------------------------

        self.title(
            "ویرایش برنامه PM"
            if schedule
            else "برنامه PM جدید"
        )

        self.configure(
            bg=BG
        )

        self.resizable(
            True,
            True
        )

        self.minsize(
            680,
            650
        )

        self._set_responsive_geometry()

        self.transient(parent)
        self.grab_set()

        self.protocol(
            "WM_DELETE_WINDOW",
            self.destroy
        )

        self.bind(
            "<Escape>",
            lambda _event: self.destroy()
        )

        self.bind(
            "<Control-s>",
            lambda _event: self._save()
        )

        # ------------------------------------------------------------------
        # Parts
        # ------------------------------------------------------------------

        self._load_parts()

        # ------------------------------------------------------------------
        # Build
        # ------------------------------------------------------------------

        self._build_ui()

        # ------------------------------------------------------------------
        # Load existing schedule
        # ------------------------------------------------------------------

        if schedule:
            self._load_data()

        self.after_idle(
            self._refresh_scroll_region
        )

    # =========================================================================
    # WINDOW
    # =========================================================================

    def _set_responsive_geometry(self):

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        width = min(
            900,
            max(
                680,
                int(
                    screen_w * 0.70
                ),
            ),
        )

        height = min(
            900,
            max(
                650,
                int(
                    screen_h * 0.84
                ),
            ),
        )

        x = max(
            10,
            (
                screen_w
                - width
            ) // 2,
        )

        y = max(
            10,
            (
                screen_h
                - height
            ) // 2,
        )

        self.geometry(
            f"{width}x{height}+{x}+{y}"
        )

    # =========================================================================
    # UI
    # =========================================================================

    def _build_ui(self):
        """Build the PM form with a stable RTL two-column layout.

        The previous layout placed labels and their controls in the same grid
        cell because the form had only one grid column.  That made several
        Persian titles disappear underneath the entry widgets.  This version
        gives every label its own right-hand column and every control the left
        column, with a scrollable body for smaller screens.
        """
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ------------------------------------------------------------------
        # Header
        # ------------------------------------------------------------------
        header = tk.Frame(self, bg=PRIMARY, height=62)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        title = "📅  ویرایش برنامه PM" if self.schedule else "📅  برنامه PM جدید"
        tk.Label(
            header,
            text=title,
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE,
            anchor="center",
            justify="center",
        ).pack(fill="both", expand=True, padx=18)

        # ------------------------------------------------------------------
        # Scrollable body
        # ------------------------------------------------------------------
        body = tk.Frame(self, bg=BG)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            body,
            bg=BG,
            highlightthickness=0,
            bd=0,
        )
        self.scrollbar = ttk.Scrollbar(
            body,
            orient="vertical",
            command=self.canvas.yview,
        )

        self.canvas.grid(
            row=0, column=0, sticky="nsew", padx=(8, 0), pady=8
        )
        self.scrollbar.grid(
            row=0, column=1, sticky="ns", padx=(0, 8), pady=8
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollable = tk.Frame(self.canvas, bg=BG)
        self.scroll_window = self.canvas.create_window(
            (0, 0), window=self.scrollable, anchor="nw"
        )

        self.scrollable.bind(
            "<Configure>", lambda _event: self._refresh_scroll_region()
        )
        self.canvas.bind("<Configure>", self._resize_scrollable)
        self._bind_mousewheel(self.scrollable)

        # ------------------------------------------------------------------
        # Main card
        # ------------------------------------------------------------------
        border = tk.Frame(self.scrollable, bg=BORDER)
        border.pack(fill="x", padx=18, pady=18)

        main = tk.Frame(border, bg=CARD_BG, padx=24, pady=22)
        main.pack(fill="x", padx=1, pady=1)

        # RTL visual order: field on the left, label on the right.
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, minsize=190)

        row = 0

        def add_section_title(text):
            nonlocal row
            section = tk.Frame(main, bg=CARD_BG)
            section.grid(
                row=row, column=0, columnspan=2, sticky="ew", pady=(10, 4)
            )
            section.grid_columnconfigure(0, weight=1)
            tk.Frame(section, bg=PRIMARY, height=2).grid(
                row=0, column=0, sticky="ew", pady=(0, 5)
            )
            tk.Label(
                section,
                text=text,
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=PRIMARY,
                anchor="e",
                justify="right",
            ).grid(row=1, column=0, sticky="ew")
            row += 1

        def add_field(label_text, widget, *, label_anchor="e", pady=6, sticky="ew"):
            nonlocal row
            tk.Label(
                main,
                text=label_text,
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=TEXT,
                anchor=label_anchor,
                justify="right",
                wraplength=180,
            ).grid(
                row=row,
                column=1,
                sticky="ne" if label_anchor == "ne" else "e",
                padx=(12, 4),
                pady=pady,
            )
            widget.grid(
                row=row,
                column=0,
                sticky=sticky,
                pady=pady,
            )
            row += 1

        add_section_title("اطلاعات اصلی برنامه PM")

        self.title_entry = ttk.Entry(
            main, font=FONT_NORMAL, justify="right"
        )
        add_field("عنوان برنامه *:", self.title_entry)

        self.equipment_combo = SearchableCombobox(
            main, width=48, state="normal", font=FONT_NORMAL
        )
        self._load_equipment()
        add_field("تجهیز *:", self.equipment_combo)

        # Department + explanatory note
        department_frame = tk.Frame(main, bg=CARD_BG)
        department_frame.grid_columnconfigure(0, weight=1)
        self.department_var = tk.StringVar()
        self.department_combo = ttk.Combobox(
            department_frame,
            textvariable=self.department_var,
            state="readonly",
            font=FONT_NORMAL,
            justify="right",
        )
        self.department_combo.grid(row=0, column=0, sticky="ew")
        self._load_departments()
        tk.Label(
            department_frame,
            text=(
                "پرسنل انجام‌دهنده در این مرحله انتخاب نمی‌شود. "
                "پس از انجام کار، پرسنل همان دپارتمان در درخواست اتمام "
                "دستورکار انتخاب خواهد شد."
            ),
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=SUBTLE,
            justify="right",
            anchor="e",
            wraplength=620,
        ).grid(row=1, column=0, sticky="ew", pady=(5, 0))
        add_field("دپارتمان مسئول *:", department_frame)

        add_section_title("زمان‌بندی و تناوب")

        self.frequency_combo = ttk.Combobox(
            main,
            values=list(FREQ_FA_MAP.values()),
            state="readonly",
            font=FONT_NORMAL,
            justify="right",
        )
        self.frequency_combo.bind(
            "<<ComboboxSelected>>", self._on_frequency_change
        )
        add_field("دوره تناوب *:", self.frequency_combo)

        interval_frame = tk.Frame(main, bg=CARD_BG)
        interval_frame.grid_columnconfigure(0, weight=1)
        self.interval_entry = ttk.Entry(
            interval_frame, width=12, font=FONT_NORMAL, justify="center"
        )
        self.interval_entry.grid(row=0, column=0, sticky="w")
        tk.Label(
            interval_frame,
            text="روز",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=SUBTLE,
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))
        add_field("بازه تناوب *:", interval_frame)

        self.start_date = JalaliDateEntry(main, width=18)
        add_field("تاریخ شروع / اولین سررسید *:", self.start_date, sticky="w")

        add_section_title("دستورالعمل و اجرا")

        self.checklist_text = tk.Text(
            main,
            height=6,
            font=FONT_NORMAL,
            relief="solid",
            bd=1,
            wrap="word",
            padx=7,
            pady=6,
        )
        add_field(
            "چک‌لیست / دستورالعمل:",
            self.checklist_text,
            label_anchor="ne",
        )

        self.duration_entry = ttk.Entry(
            main, width=14, font=FONT_NORMAL, justify="center"
        )
        add_field("مدت مجاز (روز):", self.duration_entry, sticky="w")

        self.notes_text = tk.Text(
            main,
            height=5,
            font=FONT_NORMAL,
            relief="solid",
            bd=1,
            wrap="word",
            padx=7,
            pady=6,
        )
        add_field("یادداشت:", self.notes_text, label_anchor="ne")

        # ------------------------------------------------------------------
        # Required parts
        # ------------------------------------------------------------------
        parts_frame = tk.LabelFrame(
            main,
            text="  قطعات مورد نیاز  ",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            padx=12,
            pady=12,
        )
        parts_frame.grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(14, 6),
        )
        parts_frame.grid_columnconfigure(0, weight=1)

        columns = ("part_number", "name", "stock", "quantity")
        self.parts_tree = ttk.Treeview(
            parts_frame,
            columns=columns,
            show="headings",
            height=5,
            selectmode="browse",
        )
        rtl_columns(self.parts_tree)  # RTL column order
        headings = {
            "part_number": "شماره قطعه",
            "name": "نام قطعه",
            "stock": "موجودی",
            "quantity": "تعداد مورد نیاز",
        }
        widths = {
            "part_number": 130,
            "name": 280,
            "stock": 100,
            "quantity": 125,
        }
        for col in columns:
            self.parts_tree.heading(col, text=headings[col], anchor="center")
            self.parts_tree.column(
                col,
                width=widths[col],
                minwidth=75,
                anchor="center" if col != "name" else "e",
                stretch=True,
            )

        parts_vsb = ttk.Scrollbar(
            parts_frame, orient="vertical", command=self.parts_tree.yview
        )
        self.parts_tree.configure(yscrollcommand=parts_vsb.set)
        self.parts_tree.grid(row=0, column=0, sticky="ew", pady=5)
        parts_vsb.grid(row=0, column=1, sticky="ns", pady=5)

        parts_buttons = tk.Frame(parts_frame, bg=CARD_BG)
        parts_buttons.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        tk.Button(
            parts_buttons,
            text="➕ افزودن قطعه",
            command=self._add_part,
            bg=PRIMARY,
            fg=WHITE,
            activebackground=NAVY_LIGHT,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(side="right", padx=3)
        tk.Button(
            parts_buttons,
            text="🗑️ حذف قطعه",
            command=self._remove_part,
            bg=DANGER,
            fg=WHITE,
            activebackground=DANGER,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(side="right", padx=3)

        # Keep the card visually balanced at the bottom.
        row += 1
        tk.Label(
            main,
            text="",
            bg=CARD_BG,
        ).grid(row=row, column=0, columnspan=2, pady=3)

        # ------------------------------------------------------------------
        # Footer
        # ------------------------------------------------------------------
        footer = tk.Frame(
            self,
            bg=WHITE,
            height=70,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_propagate(False)

        tk.Button(
            footer,
            text="انصراف",
            command=self.destroy,
            bg=BG,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=24,
            pady=8,
        ).pack(side="left", padx=14, pady=11)

        tk.Button(
            footer,
            text="💾 ذخیره برنامه PM",
            command=self._save,
            bg=OK,
            fg=WHITE,
            activebackground=PRIMARY,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=25,
            pady=8,
        ).pack(side="right", padx=14, pady=11)

        # Make sure the initial view starts at the top and the scroll region
        # is recalculated after all widgets have requested their final sizes.
        self.canvas.yview_moveto(0.0)
        self.after_idle(self._refresh_scroll_region)

    # =========================================================================
    # LABEL
    # =========================================================================

    def _label(self, parent, text, row, anchor="e"):
        """Compatibility helper for older callers.

        The active PM form uses its own two-column helper, but this method is
        retained so external code that may call it still gets a visible label.
        """
        tk.Label(
            parent,
            text=text,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            anchor=anchor,
            justify="right",
            wraplength=180,
        ).grid(
            row=row,
            column=max(0, parent.grid_size()[0] - 1),
            sticky="e",
            padx=(12, 4),
            pady=6,
        )

    # =========================================================================
    # SCROLL
    # =========================================================================

    def _refresh_scroll_region(self):
        try:
            self.canvas.update_idletasks()
            bbox = self.canvas.bbox("all")
            self.canvas.configure(scrollregion=bbox if bbox else (0, 0, 0, 0))
        except Exception:
            pass

    def _resize_scrollable(self, event):
        try:
            self.canvas.itemconfigure(self.scroll_window, width=max(1, event.width))
            self.after_idle(self._refresh_scroll_region)
        except Exception:
            pass

    def _on_mousewheel(self, event):
        try:
            delta = getattr(event, "delta", 0)
            if delta:
                units = int(-delta / 120)
                if units == 0:
                    units = -1 if delta > 0 else 1
                self.canvas.yview_scroll(units, "units")
                return "break"
        except Exception:
            pass
        return None

    def _bind_mousewheel(self, root):
        """Allow scrolling when the mouse is over labels, entries or frames.

        Text and Listbox widgets are intentionally skipped so they keep their
        own internal scrolling and do not double-scroll the outer form.
        """
        def _wheel(event):
            return self._on_mousewheel(event)

        def _up(_event):
            try:
                self.canvas.yview_scroll(-3, "units")
                return "break"
            except Exception:
                return None

        def _down(_event):
            try:
                self.canvas.yview_scroll(3, "units")
                return "break"
            except Exception:
                return None

        def walk(widget):
            # Skip widgets that manage their own scrolling.
            if isinstance(widget, (tk.Text, tk.Listbox)):
                return
            try:
                widget.bind("<MouseWheel>", _wheel, add="+")
                widget.bind("<Button-4>", _up, add="+")
                widget.bind("<Button-5>", _down, add="+")
            except Exception:
                pass
            for child in widget.winfo_children():
                walk(child)

        walk(root)
        self.canvas.bind("<MouseWheel>", _wheel, add="+")
        self.canvas.bind("<Button-4>", _up, add="+")
        self.canvas.bind("<Button-5>", _down, add="+")

    # =========================================================================
    # LOAD EQUIPMENT
    # =========================================================================

    def _load_equipment(
        self
    ):

        self.equipment_map = {}

        try:

            equipment_list = (
                self.equipment_repo
                .get_all_equipment()
                or []
            )

        except Exception as exc:

            messagebox.showerror(
                "خطا",
                (
                    "بارگذاری تجهیزات انجام نشد:\n\n"
                    f"{exc}"
                ),
                parent=self
            )

            equipment_list = []

        values = []

        for equipment in equipment_list:

            if not isinstance(
                equipment,
                dict
            ):
                continue

            equipment_id = (
                equipment.get("id")
            )

            if equipment_id is None:
                continue

            code = str(
                equipment.get("code")
                or ""
            ).strip()

            name = str(
                equipment.get("name")
                or ""
            ).strip()

            if code and name:

                display = (
                    f"{code} - {name}"
                )

            elif name:

                display = name

            elif code:

                display = code

            else:

                display = (
                    f"تجهیز #{equipment_id}"
                )

            self.equipment_map[
                display
            ] = equipment_id

            values.append(
                display
            )

        values = sorted(
            set(values)
        )

        try:

            self.equipment_combo.set_completion_list(
                values
            )

            self.equipment_combo.set("")

        except Exception:
            pass

    # =========================================================================
    # LOAD DEPARTMENTS
    # =========================================================================

    def _load_departments(
        self
    ):

        self.department_map = {}

        try:

            repo = DepartmentRepository(
                SessionLocal
            )

            departments = (
                repo.get_all()
                or []
            )

        except Exception as exc:

            messagebox.showwarning(
                "هشدار",
                (
                    "بارگذاری دپارتمان‌ها انجام نشد:\n\n"
                    f"{exc}"
                ),
                parent=self
            )

            departments = []

        values = []

        for department in departments:

            department_id = _safe_id(
                department
            )

            department_name = _safe_name(
                department
            )

            if (
                department_id is None
                or not department_name
            ):
                continue

            self.department_map[
                department_name
            ] = department_id

            values.append(
                department_name
            )

        values = sorted(
            set(values)
        )

        self.department_combo[
            "values"
        ] = values

        self.department_var.set(
            ""
        )

    # =========================================================================
    # LOAD PARTS
    # =========================================================================

    def _load_parts(
        self
    ):

        try:

            self.sp_repo = (
                SparePartsRepository(
                    SessionLocal
                )
            )

            self.all_parts = (
                self.sp_repo.get_all()
                or []
            )

        except Exception as exc:

            print(
                "PM spare parts loading error:",
                exc
            )

            self.sp_repo = None
            self.all_parts = []

    # =========================================================================
    # FREQUENCY
    # =========================================================================

    def _on_frequency_change(
        self,
        _event=None
    ):

        persian_frequency = (
            self.frequency_combo
            .get()
            .strip()
        )

        frequency = (
            FREQ_EN_MAP.get(
                persian_frequency,
                "monthly"
            )
        )

        if frequency in FREQ_DAYS:

            self.interval_entry.configure(
                state="normal"
            )

            self.interval_entry.delete(
                0,
                tk.END
            )

            self.interval_entry.insert(
                0,
                str(
                    FREQ_DAYS[
                        frequency
                    ]
                )
            )

            self.interval_entry.configure(
                state="readonly"
            )

        else:

            self.interval_entry.configure(
                state="normal"
            )

            self.interval_entry.delete(
                0,
                tk.END
            )

    # =========================================================================
    # LOAD EXISTING
    # =========================================================================

    def _load_data(
        self
    ):

        schedule = (
            self.schedule
            or {}
        )

        # ------------------------------------------------------------------
        # Title
        # ------------------------------------------------------------------

        self.title_entry.insert(
            0,
            schedule.get(
                "title",
                ""
            )
            or ""
        )

        # ------------------------------------------------------------------
        # Equipment
        # ------------------------------------------------------------------

        equipment_code = (
            schedule.get(
                "equipment_code",
                ""
            )
            or ""
        )

        equipment_name = (
            schedule.get(
                "equipment_name",
                ""
            )
            or ""
        )

        if (
            equipment_code
            or equipment_name
        ):

            equipment_key = (
                f"{equipment_code} - "
                f"{equipment_name}"
            ).strip(
                " -"
            )

            if equipment_key in (
                self.equipment_map
            ):

                self.equipment_combo.set(
                    equipment_key
                )

        # ------------------------------------------------------------------
        # Department
        # ------------------------------------------------------------------

        department_name = (
            schedule.get(
                "department_name",
                ""
            )
            or ""
        )

        if department_name in (
            self.department_map
        ):

            self.department_var.set(
                department_name
            )

        else:

            department_id = (
                schedule.get(
                    "department_id"
                )
            )

            if department_id is not None:

                for (
                    name,
                    dep_id
                ) in self.department_map.items():

                    if dep_id == department_id:

                        self.department_var.set(
                            name
                        )

                        break

        # ------------------------------------------------------------------
        # Frequency
        # ------------------------------------------------------------------

        frequency = (
            schedule.get(
                "frequency",
                "monthly"
            )
            or "monthly"
        )

        self.frequency_combo.set(
            FREQ_FA_MAP.get(
                frequency,
                "ماهانه"
            )
        )

        self._on_frequency_change()

        # ------------------------------------------------------------------
        # Interval
        # ------------------------------------------------------------------

        interval_days = schedule.get(
            "interval_days"
        )

        if interval_days:

            self.interval_entry.configure(
                state="normal"
            )

            self.interval_entry.delete(
                0,
                tk.END
            )

            self.interval_entry.insert(
                0,
                str(
                    interval_days
                )
            )

            if frequency in FREQ_DAYS:

                self.interval_entry.configure(
                    state="readonly"
                )

        # ------------------------------------------------------------------
        # First due
        # ------------------------------------------------------------------

        next_due = schedule.get(
            "next_due_dt"
        )

        if next_due:

            try:

                self.start_date.set_date(
                    next_due
                )

            except Exception:
                pass

        # ------------------------------------------------------------------
        # Checklist
        # ------------------------------------------------------------------

        checklist = (
            schedule.get(
                "checklist"
            )
        )

        if checklist:

            self.checklist_text.insert(
                "1.0",
                checklist
            )

        # ------------------------------------------------------------------
        # Duration
        # ------------------------------------------------------------------

        duration = schedule.get(
            "estimated_duration"
        )

        if duration:

            self.duration_entry.insert(
                0,
                str(
                    duration
                )
            )

        # ------------------------------------------------------------------
        # Notes
        # ------------------------------------------------------------------

        notes = schedule.get(
            "notes"
        )

        if notes:

            self.notes_text.insert(
                "1.0",
                notes
            )

        # ------------------------------------------------------------------
        # Parts
        # ------------------------------------------------------------------

        parts_required = (
            schedule.get(
                "parts_required"
            )
        )

        if not parts_required:
            return

        try:

            parts_list = json.loads(
                parts_required
            )

        except Exception:
            return

        for part_info in (
            parts_list
        ):

            if not isinstance(
                part_info,
                dict
            ):
                continue

            part_id = (
                part_info.get(
                    "part_id"
                )
            )

            quantity = (
                part_info.get(
                    "quantity",
                    1
                )
            )

            part = next(
                (
                    item
                    for item
                    in self.all_parts
                    if getattr(
                        item,
                        "id",
                        None
                    )
                    == part_id
                ),
                None
            )

            if not part:
                continue

            self.selected_parts.append(
                {
                    "part_id": part.id,
                    "part_number": (
                        getattr(
                            part,
                            "part_number",
                            ""
                        )
                        or ""
                    ),
                    "name": (
                        getattr(
                            part,
                            "name",
                            ""
                        )
                        or ""
                    ),
                    "quantity": quantity,
                    "stock": (
                        getattr(
                            part,
                            "current_stock",
                            0
                        )
                        or 0
                    ),
                }
            )

        self._refresh_parts_tree()

    # =========================================================================
    # PARTS
    # =========================================================================

    def _add_part(
        self
    ):

        if not self.all_parts:

            messagebox.showinfo(
                "قطعات",
                "هیچ قطعه‌ای ثبت نشده است.",
                parent=self
            )

            return

        dialog = tk.Toplevel(
            self
        )

        dialog.title(
            "افزودن قطعه به PM"
        )

        dialog.geometry(
            "560x360"
        )

        dialog.minsize(
            460,
            300
        )

        dialog.configure(
            bg=BG
        )

        dialog.transient(
            self
        )

        dialog.grab_set()

        header = tk.Frame(
            dialog,
            bg=PRIMARY,
            height=50
        )

        header.pack(
            fill="x"
        )

        header.pack_propagate(
            False
        )

        tk.Label(
            header,
            text="🔧  افزودن قطعه",
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE
        ).pack(
            expand=True
        )

        body = tk.Frame(
            dialog,
            bg=CARD_BG,
            padx=24,
            pady=20
        )

        body.pack(
            fill="both",
            expand=True
        )

        body.grid_columnconfigure(
            0,
            weight=1
        )

        tk.Label(
            body,
            text="قطعه:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT
        ).grid(
            row=0,
            column=1,
            sticky="e",
            padx=(10, 0),
            pady=7
        )

        part_map = {}

        values = []

        for part in self.all_parts:

            part_id = getattr(
                part,
                "id",
                None
            )

            if part_id is None:
                continue

            number = str(
                getattr(
                    part,
                    "part_number",
                    ""
                )
                or ""
            ).strip()

            name = str(
                getattr(
                    part,
                    "name",
                    ""
                )
                or ""
            ).strip()

            if number and name:

                display = (
                    f"{number} - {name}"
                )

            elif name:

                display = name

            else:

                display = number

            part_map[
                display
            ] = part

            values.append(
                display
            )

        part_combo = ttk.Combobox(
            body,
            values=sorted(
                set(values)
            ),
            state="readonly",
            font=FONT_NORMAL
        )

        part_combo.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=7
        )

        tk.Label(
            body,
            text="تعداد:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT
        ).grid(
            row=1,
            column=1,
            sticky="e",
            padx=(10, 0),
            pady=7
        )

        qty_entry = ttk.Entry(
            body,
            width=12,
            font=FONT_NORMAL
        )

        qty_entry.grid(
            row=1,
            column=0,
            sticky="w",
            pady=7
        )

        qty_entry.insert(
            0,
            "1"
        )

        def save_part():

            selection = (
                part_combo.get()
                .strip()
            )

            if not selection:

                messagebox.showerror(
                    "خطا",
                    "لطفاً یک قطعه انتخاب کنید.",
                    parent=dialog
                )

                return

            try:

                quantity = int(
                    qty_entry.get().strip()
                )

            except (
                TypeError,
                ValueError
            ):

                messagebox.showerror(
                    "خطا",
                    "تعداد باید عدد صحیح باشد.",
                    parent=dialog
                )

                return

            if quantity <= 0:

                messagebox.showerror(
                    "خطا",
                    "تعداد باید بیشتر از صفر باشد.",
                    parent=dialog
                )

                return

            part = part_map.get(
                selection
            )

            if part is None:

                messagebox.showerror(
                    "خطا",
                    "قطعه انتخاب‌شده معتبر نیست.",
                    parent=dialog
                )

                return

            stock = (
                getattr(
                    part,
                    "current_stock",
                    0
                )
                or 0
            )

            existing_qty = 0

            for existing in (
                self.selected_parts
            ):

                if (
                    existing["part_id"]
                    == part.id
                ):

                    existing_qty = int(
                        existing["quantity"]
                    )

                    break

            if (
                existing_qty
                + quantity
                > stock
            ):

                messagebox.showerror(
                    "موجودی ناکافی",
                    (
                        f"موجودی فعلی: {stock}\n"
                        f"انتخاب فعلی: {existing_qty}\n"
                        f"مقدار جدید: {quantity}"
                    ),
                    parent=dialog
                )

                return

            for existing in (
                self.selected_parts
            ):

                if (
                    existing["part_id"]
                    == part.id
                ):

                    existing["quantity"] += (
                        quantity
                    )

                    self._refresh_parts_tree()

                    dialog.destroy()

                    return

            self.selected_parts.append(
                {
                    "part_id": part.id,
                    "part_number": (
                        getattr(
                            part,
                            "part_number",
                            ""
                        )
                        or ""
                    ),
                    "name": (
                        getattr(
                            part,
                            "name",
                            ""
                        )
                        or ""
                    ),
                    "quantity": quantity,
                    "stock": stock,
                }
            )

            self._refresh_parts_tree()

            dialog.destroy()

        button_frame = tk.Frame(
            body,
            bg=CARD_BG
        )

        button_frame.grid(
            row=2,
            column=0,
            columnspan=2,
            pady=(20, 0)
        )

        tk.Button(
            button_frame,
            text="انصراف",
            command=dialog.destroy,
            bg=BORDER,
            fg=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=22,
            pady=7
        ).pack(
            side="left",
            padx=5
        )

        tk.Button(
            button_frame,
            text="افزودن",
            command=save_part,
            bg=OK,
            fg=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=22,
            pady=7
        ).pack(
            side="left",
            padx=5
        )

        dialog.bind(
            "<Return>",
            lambda _event: save_part()
        )

        dialog.bind(
            "<Escape>",
            lambda _event: dialog.destroy()
        )

        part_combo.focus_set()

    def _remove_part(
        self
    ):

        selection = (
            self.parts_tree.selection()
        )

        if not selection:
            return

        try:

            index = int(
                selection[0]
            )

        except (
            TypeError,
            ValueError
        ):

            return

        if (
            0
            <= index
            < len(
                self.selected_parts
            )
        ):

            del self.selected_parts[
                index
            ]

            self._refresh_parts_tree()

    def _refresh_parts_tree(
        self
    ):

        self.parts_tree.delete(
            *self.parts_tree.get_children()
        )

        for index, item in enumerate(
            self.selected_parts
        ):

            self.parts_tree.insert(
                "",
                "end",
                iid=str(
                    index
                ),
                values=(
                    item.get(
                        "part_number",
                        ""
                    ),
                    item.get(
                        "name",
                        ""
                    ),
                    item.get(
                        "stock",
                        0
                    ),
                    item.get(
                        "quantity",
                        0
                    ),
                )
            )

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def _validate_save(
        self
    ):

        # ------------------------------------------------------------------
        # Title
        # ------------------------------------------------------------------

        title = (
            self.title_entry
            .get()
            .strip()
        )

        if not title:

            field_error(self.title_entry, "عنوان برنامه PM الزامی است.")

            return None

        # ------------------------------------------------------------------
        # Equipment
        # ------------------------------------------------------------------

        equipment_key = (
            self.equipment_combo
            .get()
            .strip()
        )

        if not equipment_key:

            field_error(self.equipment_combo, "انتخاب تجهیز الزامی است.")

            return None

        equipment_id = (
            self.equipment_map.get(
                equipment_key
            )
        )

        if equipment_id is None:

            field_error(self.equipment_combo, "تجهیز انتخاب‌شده معتبر نیست.")

            return None

        # ------------------------------------------------------------------
        # Department
        # ------------------------------------------------------------------

        department_name = (
            self.department_var
            .get()
            .strip()
        )

        if not department_name:

            field_error(self.department_combo, "انتخاب دپارتمان الزامی است.")

            return None

        department_id = (
            self.department_map.get(
                department_name
            )
        )

        if department_id is None:

            field_error(self.department_combo, "دپارتمان انتخاب‌شده معتبر نیست.")

            return None

        # ------------------------------------------------------------------
        # Frequency
        # ------------------------------------------------------------------

        frequency_fa = (
            self.frequency_combo
            .get()
            .strip()
        )

        if not frequency_fa:

            field_error(self.frequency_combo, "دوره تناوب PM را انتخاب کنید.")

            return None

        frequency = (
            FREQ_EN_MAP.get(
                frequency_fa
            )
        )

        if not frequency:

            messagebox.showerror(
                "خطا",
                "دوره تناوب نامعتبر است.",
                parent=self
            )

            return None

        # ------------------------------------------------------------------
        # Interval
        # ------------------------------------------------------------------

        interval_text = (
            self.interval_entry
            .get()
            .strip()
        )

        try:

            interval_days = int(
                interval_text
            )

            if interval_days <= 0:
                raise ValueError

        except (
            TypeError,
            ValueError
        ):

            field_error(self.interval_entry, "بازه تناوب باید یک عدد صحیح بزرگ‌تر از صفر باشد.")

            return None

        # ------------------------------------------------------------------
        # Date
        # ------------------------------------------------------------------

        try:

            start_date = (
                self.start_date
                .get_date()
            )

        except Exception:

            start_date = None

        if start_date is None:

            messagebox.showerror(
                "خطا",
                "تاریخ شروع / اولین سررسید را انتخاب کنید.",
                parent=self
            )

            return None

        # ------------------------------------------------------------------
        # Checklist
        # ------------------------------------------------------------------

        checklist = (
            self.checklist_text
            .get(
                "1.0",
                tk.END
            )
            .strip()
            or None
        )

        # ------------------------------------------------------------------
        # Estimated duration
        # ------------------------------------------------------------------

        duration_text = (
            self.duration_entry
            .get()
            .strip()
        )

        estimated_duration = None

        if duration_text:

            try:

                estimated_duration = int(
                    duration_text
                )

                if estimated_duration <= 0:
                    raise ValueError

            except (
                TypeError,
                ValueError
            ):

                field_error(self.duration_entry, "مدت مجاز باید یک عدد صحیح بزرگ‌تر از صفر باشد.")

                return None

        # ------------------------------------------------------------------
        # Notes
        # ------------------------------------------------------------------

        notes = (
            self.notes_text
            .get(
                "1.0",
                tk.END
            )
            .strip()
            or None
        )

        # ------------------------------------------------------------------
        # Parts
        # ------------------------------------------------------------------

        parts_required = None

        if self.selected_parts:

            parts_required = json.dumps(
                [
                    {
                        "part_id": item.get(
                            "part_id"
                        ),
                        "quantity": item.get(
                            "quantity",
                            1
                        ),
                    }
                    for item in self.selected_parts
                ],
                ensure_ascii=False
            )

        return {
            "title": title,
            "equipment_id": equipment_id,
            "department_id": department_id,
            "frequency": frequency,
            "interval_days": interval_days,
            "start_date": start_date,
            "checklist": checklist,
            "estimated_duration": estimated_duration,
            "notes": notes,
            "parts_required": parts_required,
        }

    # =========================================================================
    # SAVE
    # =========================================================================

    def _save(
        self
    ):

        data = (
            self._validate_save()
        )

        if not data:
            return

        # ------------------------------------------------------------------
        # Duplicate check
        # ------------------------------------------------------------------

        exclude_id = (
            self.schedule.get("id")
            if self.schedule
            else None
        )

        try:

            duplicate = (
                self.pm_repo
                .duplicate_pm_exists(
                    data["equipment_id"],
                    data["title"],
                    data["frequency"],
                    exclude_id=exclude_id
                )
            )

        except Exception as exc:

            messagebox.showerror(
                "خطا",
                (
                    "بررسی برنامه‌های تکراری "
                    f"انجام نشد:\n\n{exc}"
                ),
                parent=self
            )

            return

        if duplicate:

            confirmed = (
                messagebox.askyesno(
                    "تکرار احتمالی",
                    (
                        "یک برنامه PM مشابه برای این تجهیز "
                        "و دوره تناوب وجود دارد.\n\n"
                        "آیا همچنان می‌خواهید ادامه دهید؟"
                    ),
                    parent=self
                )
            )

            if not confirmed:
                return

        # ------------------------------------------------------------------
        # IMPORTANT
        #
        # PM NEVER assigns User technician.
        # ------------------------------------------------------------------

        technician_id = None

        # ------------------------------------------------------------------
        # Repository operation
        # ------------------------------------------------------------------

        try:

            if self.schedule:

                success, message = (
                    self.pm_repo.update(
                        self.schedule["id"],
                        data["title"],
                        data["equipment_id"],
                        technician_id,
                        data["frequency"],
                        data["interval_days"],
                        data["start_date"],
                        data["checklist"],
                        data["estimated_duration"],
                        data["notes"],
                        data["parts_required"],
                        department_id=data["department_id"]
                    )
                )

            else:

                success, message = (
                    self.pm_repo.create(
                        data["title"],
                        data["equipment_id"],
                        technician_id,
                        data["frequency"],
                        data["interval_days"],
                        data["start_date"],
                        data["checklist"],
                        data["estimated_duration"],
                        data["notes"],
                        data["parts_required"],
                        department_id=data["department_id"]
                    )
                )

        except Exception as exc:

            messagebox.showerror(
                "خطا",
                (
                    "خطایی هنگام ذخیره برنامه PM رخ داد:\n\n"
                    f"{exc}"
                ),
                parent=self
            )

            return

        # ------------------------------------------------------------------
        # Result
        # ------------------------------------------------------------------

        if success:

            self.result = True

            if self.callback:

                try:
                    self.callback()

                except Exception as exc:

                    print(
                        "PMDialog callback error:",
                        exc
                    )

            messagebox.showinfo(
                "موفق",
                message,
                parent=self
            )

            self.destroy()

        else:

            messagebox.showerror(
                "خطا",
                message,
                parent=self
            )


# ============================================================================
# DEVELOPMENT ENTRY
# ============================================================================

if __name__ == "__main__":

    root = tk.Tk()
    root.withdraw()

    messagebox.showinfo(
        "PM System",
        (
            "این پنجره باید از داخل "
            "PMView اجرا شود."
        )
    )

    root.destroy()