# views/pm_view.py
import os
import tkinter as tk
import json
from views.ui_kit import rtl_columns, reflow_grid  # RTL table columns, responsive filter grid
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

from services.pm_service import PMService
from services.pdf_service import export_pm_pdf
from database.db import SessionLocal
from database.work_order_repository import WorkOrderRepository
from auth.auth_manager import AuthManager

from utils.theme import (
    NAVY, WHITE, TEXT_DARK, TEXT_LIGHT, SUCCESS, FONT_TITLE,
    FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

from utils.date_helpers import to_jalali_date_str
from utils.date_helpers import jalali_stamp  # Jalali file names / stamps
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


# ── Palette ────────────────────────────────────────────────────────────────

CARD_BG = "#FFFFFF"
CARD_BORDER = "#E8ECF0"
SECTION_BG = "#F4F6F9"

HEADER_H = 72
STRIP_H = 4

ACCENT_NAVY = NAVY
ACCENT_GREEN = SUCCESS
ACCENT_AMBER = "#D97706"
ACCENT_ROSE = "#DC2626"

ALL = "همه"

FREQ_FA = {
    "daily": "روزانه",
    "weekly": "هفتگی",
    "monthly": "ماهانه",
    "quarterly": "سه‌ماهه",
    "biannual": "شش‌ماهه",
    "annual": "سالانه",
    "custom": "سفارشی",
}

STATUS_VALUES = (ALL, "فعال", "غیرفعال", "عقب‌افتاده", "این هفته", "به‌موقع")

# (key, label) of the drop-down filters, in reading order (right to left)
COMBO_FILTERS = (
    ("status", "وضعیت"),
    ("category", "دسته تجهیز"),
    ("location", "محل تجهیز"),
    ("department", "دپارتمان مسئول"),
    ("frequency", "دوره"),
    ("history", "سابقه انجام"),
)

DATE_FILTERS = (
    ("due_from", "سررسید از"),
    ("due_to", "سررسید تا"),
    ("done_from", "آخرین انجام از"),
    ("done_to", "آخرین انجام تا"),
)


def frequency_text(record) -> str:
    raw = str(record.get("frequency", "") or "")
    return FREQ_FA.get(raw.lower(), raw)


def equipment_text(record) -> str:
    code = record.get("equipment_code") or ""
    name = record.get("equipment_name") or ""
    return f"{code} - {name}" if code and name else (name or code)


def status_text(record) -> str:
    """
    Same rules as the cards above the table (PMRepository.get_stats):
    overdue = active and due now or earlier; this week = active and due
    within the next 7 days; otherwise on time.
    """
    if not record.get("is_active", False):
        return "غیرفعال"
    if record.get("is_overdue", False):
        return "عقب‌افتاده"
    due = record.get("next_due_dt")
    if isinstance(due, datetime):
        if due <= tehran_now() + timedelta(days=7):
            return "این هفته"
    else:
        days = record.get("days_until")
        if days is not None and 0 <= days <= 7:
            return "این هفته"
    return "به‌موقع"


def _iso_date(value):
    """'YYYY-MM-DD' (as stored in the PM record) -> date, else None."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


class PMView(tk.Frame):
    # Rows are no longer tinted by status: the status badge shows it (views/ux.py).
    ux_status_only_rows = True


    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def __init__(
        self,
        parent,
        pm_repo,
        equipment_repo,
        user_repo,
        current_user,
    ):

        super().__init__(
            parent,
            bg=SECTION_BG,
        )

        self.pm_repo = pm_repo
        self.equipment_repo = equipment_repo
        self.user_repo = user_repo
        self.current_user = current_user

        self.is_manager = (
            current_user["role"]
            in ["admin", "manager"]
        )

        self.can_write = AuthManager.can_access(
            "pm_schedule",
            "write",
        )

        self.can_delete = AuthManager.can_access(
            "pm_schedule",
            "delete",
        )

        self._service = PMService(
            SessionLocal
        )

        self._wo_repo = WorkOrderRepository(
            SessionLocal
        )

        self._filter_var = tk.StringVar(
            value="همه"
        )

        self._search_var = tk.StringVar()

        # one variable per drop-down filter ("status" keeps the old variable)
        self._fvars = {
            key: (self._filter_var if key == "status" else tk.StringVar(value=ALL))
            for key, _label in COMBO_FILTERS
        }
        self._combos = {}
        self._date_entries = {}
        self._part_names = {}
        self._sort_state = {}

        self._all_records = []
        self._visible_records = []

        self._build_ui()
        self._load()

    # =========================================================================
    # LAYOUT
    # =========================================================================

    def _build_ui(self):

        self._build_header()
        self._build_stats_bar()
        self._build_toolbar()
        self._build_table()
        self._build_action_bar()

    # =========================================================================
    # HEADER
    # =========================================================================

    def _build_header(self):

        hdr = tk.Frame(
            self,
            bg=NAVY,
            height=HEADER_H,
        )

        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        right = tk.Frame(
            hdr,
            bg=NAVY,
        )

        right.pack(
            side="right",
            padx=24,
            fill="y",
        )

        tk.Label(
            right,
            text="📅",
            font=("Tahoma", 20),
            bg=NAVY,
            fg=WHITE,
        ).pack(
            side="right",
            pady=18,
        )

        title_col = tk.Frame(
            right,
            bg=NAVY,
        )

        title_col.pack(
            side="right",
            padx=(0, 10),
            fill="y",
        )

        tk.Label(
            title_col,
            text="برنامه‌ریزی نگهداری پیشگیرانه",
            font=FONT_TITLE,
            bg=NAVY,
            fg=WHITE,
        ).pack(
            anchor="e",
            pady=(16, 0),
        )

        tk.Label(
            title_col,
            text="مدیریت برنامه‌های پیشگیرانه",
            font=FONT_SMALL,
            bg=NAVY,
            fg=WHITE,
        ).pack(
            anchor="e",
        )

        left = tk.Frame(
            hdr,
            bg=NAVY,
        )

        left.pack(
            side="left",
            padx=20,
            fill="y",
        )

        if self.can_write:

            tk.Button(
                left,
                text="➕  برنامه جدید",
                font=FONT_SMALL,
                bg=WHITE,
                fg=NAVY,
                relief="flat",
                cursor="hand2",
                padx=14,
                pady=6,
                command=self._add,
            ).pack(
                side="left",
                padx=4,
                pady=20,
            )

        tk.Button(
            left,
            text="📤  خروجی Excel",
            font=FONT_SMALL,
            bg="#0D9488",
            fg=WHITE,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=6,
            command=self._export,
        ).pack(
            side="left",
            padx=4,
            pady=20,
        )

        tk.Button(
            left,
            text="📄  PDF چاپی",
            font=FONT_SMALL,
            bg="#7C3AED",
            fg=WHITE,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=6,
            command=self._export_pdf,
        ).pack(
            side="left",
            padx=4,
            pady=20,
        )

        tk.Frame(
            self,
            bg=CARD_BORDER,
            height=1,
        ).pack(
            fill="x"
        )

    # =========================================================================
    # STATS
    # =========================================================================

    def _build_stats_bar(self):

        self._stats_frame = tk.Frame(
            self,
            bg=SECTION_BG,
        )

        self._stats_frame.pack(
            fill="x",
            padx=20,
            pady=(16, 0),
        )

    def _refresh_stats(
        self,
        stats: dict,
    ):

        for widget in self._stats_frame.winfo_children():
            widget.destroy()

        cards = [
            (
                "📋",
                "برنامه‌های فعال",
                stats.get("total", 0),
                CARD_BG,
                ACCENT_NAVY,
                "#DBEAFE",
            ),
            (
                "🔴",
                "عقب‌افتاده",
                stats.get("overdue", 0),
                "#FEE2E2",
                ACCENT_ROSE,
                ACCENT_ROSE,
            ),
            (
                "🟡",
                "این هفته",
                stats.get("upcoming", 0),
                "#FEF3C7",
                ACCENT_AMBER,
                ACCENT_AMBER,
            ),
        ]

        for (
            icon,
            label,
            value,
            bg_color,
            fg_color,
            strip_color,
        ) in cards:

            shadow = tk.Frame(
                self._stats_frame,
                bg=CARD_BORDER,
            )

            shadow.pack(
                side="right",
                padx=6,
            )

            card = tk.Frame(
                shadow,
                bg=bg_color,
            )

            card.pack(
                fill="both",
                expand=True,
                padx=1,
                pady=1,
            )

            tk.Frame(
                card,
                bg=strip_color,
                height=STRIP_H,
            ).pack(
                fill="x"
            )

            inner = tk.Frame(
                card,
                bg=bg_color,
            )

            inner.pack(
                padx=18,
                pady=8,
            )

            top = tk.Frame(
                inner,
                bg=bg_color,
            )

            top.pack(
                fill="x"
            )

            tk.Label(
                top,
                text=icon,
                font=("Tahoma", 14),
                bg=bg_color,
                fg=fg_color,
            ).pack(
                side="right"
            )

            tk.Label(
                top,
                text=label,
                font=FONT_SMALL,
                bg=bg_color,
                fg=TEXT_LIGHT,
            ).pack(
                side="right",
                padx=(0, 4),
            )

            tk.Label(
                inner,
                text=str(value),
                font=FONT_HEADING,
                bg=bg_color,
                fg=fg_color,
            ).pack(
                anchor="center",
                pady=(4, 0),
            )

    # =========================================================================
    # TOOLBAR
    # =========================================================================

    def _build_toolbar(self):

        row = tk.Frame(
            self,
            bg=SECTION_BG,
        )

        row.pack(
            fill="x",
            padx=20,
            pady=(18, 6),
        )

        tk.Label(
            row,
            text="📋  لیست برنامه‌های PM",
            font=FONT_HEADING,
            bg=SECTION_BG,
            fg=TEXT_DARK,
        ).pack(
            side="right"
        )

        tk.Frame(
            row,
            bg=CARD_BORDER,
            height=1,
        ).pack(
            side="right",
            fill="x",
            expand=True,
            padx=(0, 12),
            pady=8,
        )

        outer = tk.Frame(
            self,
            bg=CARD_BORDER,
        )

        outer.pack(
            fill="x",
            padx=20,
            pady=(0, 10),
        )

        bar = tk.Frame(
            outer,
            bg=CARD_BG,
        )

        bar.pack(
            fill="x",
            padx=1,
            pady=1,
        )

        inner = tk.Frame(
            bar,
            bg=CARD_BG,
        )

        inner.pack(
            fill="x",
            padx=16,
            pady=10,
        )

        # --- line 1: search (left), result count and «پاک کردن فیلترها» ---
        top = tk.Frame(
            inner,
            bg=CARD_BG,
        )

        top.pack(
            fill="x",
        )

        tk.Label(
            top,
            text="فیلترها",
            font=FONT_HEADING,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).pack(
            side="right",
        )

        search_wrap = tk.Frame(
            top,
            bg=CARD_BG,
        )

        search_wrap.pack(
            side="left"
        )

        tk.Label(
            search_wrap,
            text="🔍",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
        ).pack(
            side="left"
        )

        search_entry = tk.Entry(
            search_wrap,
            textvariable=self._search_var,
            font=FONT_NORMAL,
            bg=SECTION_BG,
            relief="solid",
            bd=1,
            width=26,
        )

        search_entry.pack(
            side="left",
            padx=6,
            ipady=5,
        )

        search_entry.bind(
            "<Return>",
            lambda _event: self._apply_filter(),
        )

        tk.Button(
            search_wrap,
            text="جستجو",
            font=FONT_SMALL,
            bg=NAVY,
            fg=WHITE,
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=4,
            command=self._apply_filter,
        ).pack(
            side="left"
        )

        self._row_count_lbl = tk.Label(
            top,
            text="",
            font=FONT_SMALL,
            bg=NAVY,
            fg=WHITE,
            padx=10,
            pady=2,
        )

        self._row_count_lbl.pack(
            side="left",
            padx=(12, 0),
        )

        tk.Button(
            top,
            text="✖  پاک کردن فیلترها",
            font=FONT_SMALL,
            bg=SECTION_BG,
            fg=TEXT_DARK,
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=4,
            command=self._clear_filters,
        ).pack(
            side="left",
            padx=(12, 0),
        )

        tk.Frame(
            inner,
            bg=CARD_BORDER,
            height=1,
        ).pack(
            fill="x",
            pady=(8, 4),
        )

        # --- every property of a PM can narrow the list; all filters combine
        #     with each other and with the search ---
        grid = tk.Frame(
            inner,
            bg=CARD_BG,
        )

        grid.pack(
            fill="x",
        )

        cells = []

        for key, label in COMBO_FILTERS:

            cell = tk.Frame(
                grid,
                bg=CARD_BG,
            )

            tk.Label(
                cell,
                text=label,
                font=FONT_SMALL,
                bg=CARD_BG,
                fg=TEXT_LIGHT,
                anchor="e",
            ).pack(
                fill="x",
            )

            combo = ttk.Combobox(
                cell,
                textvariable=self._fvars[key],
                values=(ALL,),
                state="readonly",
                font=FONT_SMALL,
                width=14,
                justify="right",
            )

            combo.pack(
                fill="x",
                pady=(2, 0),
            )

            combo.bind(
                "<<ComboboxSelected>>",
                lambda _event: self._apply_filter(),
            )

            self._combos[key] = combo
            cells.append(cell)

        from views.jalali_date_entry import JalaliDateEntry

        for key, label in DATE_FILTERS:

            cell = tk.Frame(
                grid,
                bg=CARD_BG,
            )

            tk.Label(
                cell,
                text=label,
                font=FONT_SMALL,
                bg=CARD_BG,
                fg=TEXT_LIGHT,
                anchor="e",
            ).pack(
                fill="x",
            )

            entry = JalaliDateEntry(
                cell,
                width=10,
            )

            entry.set_date(None)     # blank = no limit

            entry.pack(
                fill="x",
                pady=(2, 0),
            )

            for sequence in ("<<DateEntrySelected>>", "<Return>", "<FocusOut>"):
                entry.bind(
                    sequence,
                    lambda _event: self._apply_filter(),
                )

            self._date_entries[key] = entry
            cells.append(cell)

        columns = 5

        for index, cell in enumerate(cells):

            cell.grid(
                row=index // columns,
                column=columns - 1 - index % columns,
                sticky="ew",
                padx=6,
                pady=4,
            )

        for column in range(columns):

            grid.columnconfigure(
                column,
                weight=1,
                uniform="pm_filters",
            )

        # fewer columns on small screens (keeps the right-to-left order)
        reflow_grid(
            grid,
            min_width=140,
        )

    # =========================================================================
    # TABLE
    # =========================================================================

    def _build_table(self):

        outer = tk.Frame(
            self,
            bg=CARD_BORDER,
        )

        outer.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 10),
        )

        card = tk.Frame(
            outer,
            bg=CARD_BG,
        )

        card.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
        )

        cols = (
            "id",
            "title",
            "equipment",
            "department",
            "frequency",
            "last_done",
            "next_due",
            "days_until",
            "status",
        )

        headers = {
            "id": (
                "شناسه",
                55,
            ),
            "title": (
                "عنوان برنامه",
                200,
            ),
            "equipment": (
                "تجهیز",
                180,
            ),
            "department": (
                "دپارتمان مسئول",
                150,
            ),
            "frequency": (
                "دوره",
                90,
            ),
            "last_done": (
                "آخرین انجام",
                110,
            ),
            "next_due": (
                "سررسید بعدی",
                110,
            ),
            "days_until": (
                "روز مانده",
                80,
            ),
            "status": (
                "وضعیت",
                100,
            ),
        }

        self.tree = ttk.Treeview(
            card,
            columns=cols,
            show="headings",
            height=16,
            selectmode="extended",
        )
        rtl_columns(self.tree)  # RTL column order

        style = ttk.Style()

        style.configure(
            "PM.Treeview",
            font=FONT_NORMAL,
            rowheight=30,
            background=CARD_BG,
            fieldbackground=CARD_BG,
            foreground=TEXT_DARK,
        )

        style.configure(
            "PM.Treeview.Heading",
            font=FONT_NORMAL,
            background=NAVY,
            foreground=WHITE,
            relief="flat",
        )

        style.map(
            "PM.Treeview",
            background=[
                (
                    "selected",
                    NAVY,
                )
            ],
            foreground=[
                (
                    "selected",
                    WHITE,
                )
            ],
        )

        self.tree.configure(
            style="PM.Treeview"
        )

        for col in cols:

            text, width = headers[col]

            self.tree.heading(
                col,
                text=text,
                command=lambda c=col:
                    self._sort(c),
            )

            self.tree.column(
                col,
                width=width,
                anchor="center",
                minwidth=50,
            )

        self.tree.tag_configure(
            "overdue",
            background="#FEE2E2",
            foreground=ACCENT_ROSE,
        )

        self.tree.tag_configure(
            "upcoming",
            background="#FEF3C7",
            foreground=ACCENT_AMBER,
        )

        self.tree.tag_configure(
            "ok",
            background="#D1FAE5",
            foreground="#065F46",
        )

        self.tree.tag_configure(
            "inactive",
            background=CARD_BORDER,
            foreground=TEXT_LIGHT,
        )

        vsb = ttk.Scrollbar(
            card,
            orient="vertical",
            command=self.tree.yview,
        )

        hsb = ttk.Scrollbar(
            card,
            orient="horizontal",
            command=self.tree.xview,
        )

        self.tree.configure(
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        vsb.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        hsb.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        card.rowconfigure(
            0,
            weight=1,
        )

        card.columnconfigure(
            0,
            weight=1,
        )

        self.tree.bind(
            "<Double-1>",
            lambda _event:
                self._edit(),
        )

        self.tree.bind(
            "<Delete>",
            lambda _event:
                self._delete_selected(),
        )

        self.tree.bind(
            "<F2>",
            lambda _event:
                self._edit_selected(),
        )

        self.tree.bind(
            "<Control-n>",
            lambda _event:
                self._add(),
        )

        self._build_context_menu()

    # =========================================================================
    # ACTION BAR
    # =========================================================================

    def _build_action_bar(self):

        outer = tk.Frame(
            self,
            bg=CARD_BORDER,
        )

        outer.pack(
            fill="x",
            padx=20,
            pady=(0, 20),
        )

        bar = tk.Frame(
            outer,
            bg=CARD_BG,
        )

        bar.pack(
            fill="x",
            padx=1,
            pady=1,
        )

        inner = tk.Frame(
            bar,
            bg=CARD_BG,
        )

        inner.pack(
            fill="x",
            padx=16,
            pady=10,
        )

        if self.can_write:

            tk.Button(
                inner,
                text="✏️  ویرایش",
                font=FONT_NORMAL,
                bg=NAVY,
                fg=WHITE,
                relief="flat",
                cursor="hand2",
                padx=16,
                pady=8,
                command=self._edit,
            ).pack(
                side="right",
                padx=4,
            )

            tk.Button(
                inner,
                text="📋  مشاهده دستورکار",
                font=FONT_NORMAL,
                bg=ACCENT_GREEN,
                fg=WHITE,
                relief="flat",
                cursor="hand2",
                padx=16,
                pady=8,
                command=self._open_pm_work_order,
            ).pack(
                side="right",
                padx=4,
            )

            tk.Button(
                inner,
                text="🔁  فعال / غیرفعال",
                font=FONT_NORMAL,
                bg=ACCENT_AMBER,
                fg=WHITE,
                relief="flat",
                cursor="hand2",
                padx=16,
                pady=8,
                command=self._toggle,
            ).pack(
                side="right",
                padx=4,
            )

        if self.can_delete:

            tk.Button(
                inner,
                text="🗑️  حذف",
                font=FONT_NORMAL,
                bg=ACCENT_ROSE,
                fg=WHITE,
                relief="flat",
                cursor="hand2",
                padx=16,
                pady=8,
                command=self._delete,
            ).pack(
                side="right",
                padx=4,
            )

        tk.Label(
            inner,
            text=(
                "F2: ویرایش  |  "
                "Del: حذف  |  "
                "Ctrl+N: افزودن"
            ),
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
        ).pack(
            side="left"
        )

    # =========================================================================
    # CONTEXT MENU
    # =========================================================================

    def _build_context_menu(self):

        self._menu = tk.Menu(
            self,
            tearoff=0,
            font=FONT_NORMAL,
        )

        if self.can_write:

            self._menu.add_command(
                label="✏️  ویرایش",
                command=self._edit,
            )

            self._menu.add_command(
                label="📋  مشاهده دستورکار",
                command=self._open_pm_work_order,
            )

            self._menu.add_separator()

            self._menu.add_command(
                label="🔁  تغییر وضعیت فعال",
                command=self._toggle,
            )

        if self.can_delete:

            self._menu.add_separator()

            self._menu.add_command(
                label="🗑️  حذف",
                command=self._delete,
            )

        self.tree.bind(
            "<Button-3>",
            self._show_menu,
        )

    def _show_menu(
        self,
        event,
    ):

        row = self.tree.identify_row(
            event.y
        )

        if not row:
            return

        self.tree.selection_set(
            row
        )

        try:

            self._menu.post(
                event.x_root,
                event.y_root,
            )

        finally:

            self._menu.grab_release()

    # =========================================================================
    # KEYBOARD HELPERS
    # =========================================================================

    def _delete_selected(self):

        if not self.can_delete:

            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به حذف برنامه‌ها نیستید.",
                parent=self,
            )

            return

        selected = (
            self.tree.selection()
        )

        if not selected:

            messagebox.showwarning(
                "انتخاب",
                "لطفاً برنامه‌ای انتخاب کنید.",
                parent=self,
            )

            return

        if not messagebox.askyesno(
            "حذف",
            (
                "آیا از حذف برنامه‌های "
                "انتخاب‌شده مطمئن هستید؟"
            ),
            parent=self,
        ):

            return

        errors = []

        for sid in selected:

            ok, msg = (
                self.pm_repo.delete(
                    int(sid)
                )
            )

            if not ok:
                errors.append(
                    f"PM #{sid}: {msg}"
                )

        self._load()

        if errors:

            messagebox.showerror(
                "خطا در حذف",
                "\n".join(errors),
                parent=self,
            )

    # -------------------------------------------------------------------------

    def _edit_selected(self):

        if not self.can_write:

            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به ویرایش برنامه PM نیستید.",
                parent=self,
            )

            return

        selected = (
            self.tree.selection()
        )

        if not selected:

            messagebox.showwarning(
                "انتخاب",
                "لطفاً برنامه‌ای انتخاب کنید.",
                parent=self,
            )

            return

        sid = int(
            selected[0]
        )

        record = (
            self.pm_repo.get_by_id(
                sid
            )
        )

        if not record:
            return

        from views.pm_dialog import PMDialog

        dlg = PMDialog(
            self,
            self.pm_repo,
            self.equipment_repo,
            self.user_repo,
            schedule=record,
        )

        self.wait_window(
            dlg
        )

        if dlg.result:

            self._load()

    def handle_delete(self):
        """Handle MainView's global Delete shortcut through this view's permissions."""
        self._delete_selected()

    # =========================================================================
    # DATA / ACTIONS
    # =========================================================================

    def _load(self):

        try:

            self._all_records = (
                self.pm_repo.get_all()
                or []
            )

            self._load_part_names()

            self._refresh_filter_options()

            stats = (
                self.pm_repo.get_stats()
                or {}
            )

            self._refresh_stats(
                stats
            )

            self._apply_filter()

        except Exception as exc:

            self._all_records = []
            self._visible_records = []

            messagebox.showerror(
                "خطا",
                (
                    "خطایی هنگام بارگذاری "
                    f"برنامه‌های PM رخ داد:\n\n{exc}"
                ),
                parent=self,
            )

    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # FILTER HELPERS
    # -------------------------------------------------------------------------

    def _load_part_names(self):
        """part id -> «شماره قطعه - نام» (required parts are stored as ids)."""
        try:
            from database.spare_parts_repository import SparePartsRepository
            parts = SparePartsRepository(SessionLocal).get_all() or []
            self._part_names = {
                part.id: " - ".join(
                    str(x) for x in (part.part_number, part.name) if x
                )
                for part in parts
            }
        except Exception as exc:
            print("PM view: spare parts could not be loaded:", exc)
            self._part_names = {}

    def _parts_of(self, record) -> list:
        """Names of the parts a PM needs (empty list when it needs none)."""
        raw = record.get("parts_required") or ""
        if not raw:
            return []
        try:
            items = json.loads(raw)
        except (TypeError, ValueError):
            return []
        names = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict) or item.get("part_id") is None:
                continue
            try:
                part_id = int(item.get("part_id"))
            except (TypeError, ValueError):
                continue
            names.append(self._part_names.get(part_id, f"قطعه #{part_id}"))
        return names

    @staticmethod
    def _duration_text(record) -> str:
        try:
            days = int(record.get("estimated_duration") or 0)
        except (TypeError, ValueError):
            days = 0
        return f"{days} روز" if days > 0 else "تعیین نشده"

    def _refresh_filter_options(self):
        """Fill every drop-down with the values that occur in the loaded PMs."""
        records = self._all_records or []

        def values(items, first=()):
            found = sorted({v for v in items if v})
            return [ALL, *first, *[v for v in found if v not in first]]

        options = {
            "status": list(STATUS_VALUES),
            "category": values(r.get("equipment_category") or "بدون دسته" for r in records),
            "location": values(r.get("equipment_location") or "بدون محل" for r in records),
            "department": values(r.get("department_name") or "تعیین نشده" for r in records),
            "frequency": values(frequency_text(r) for r in records),
            "history": [ALL, "انجام‌شده", "هرگز انجام نشده"],
        }

        for key, items in options.items():
            combo = self._combos.get(key)
            if combo is None:
                continue
            combo["values"] = items
            if self._fvars[key].get() not in items:
                self._fvars[key].set(ALL)      # value no longer exists (e.g. deleted equipment)

    def _date_filter(self, key):
        entry = self._date_entries.get(key)
        if entry is None:
            return None
        try:
            return entry.get_date()
        except Exception:
            return None

    def _active_filters(self) -> list:
        """«عنوان: مقدار» of every filter in use (for the PDF confirmation)."""
        lines = []
        for key, label in COMBO_FILTERS:
            value = self._fvars[key].get()
            if value and value != ALL:
                lines.append(f"{label}: {value}")
        for key, label in DATE_FILTERS:
            value = self._date_filter(key)
            if value:
                lines.append(f"{label}: {to_jalali_date_str(value)}")
        search = self._search_var.get().strip()
        if search:
            lines.append(f"جستجو: {search}")
        return lines

    def _clear_filters(self):
        for var in self._fvars.values():
            var.set(ALL)
        for entry in self._date_entries.values():
            try:
                entry.set_date(None)
            except Exception:
                pass
        self._search_var.set("")
        self._apply_filter()

    def _matches(self, record, chosen, dates) -> bool:
        """True when the PM passes every selected filter."""
        status = status_text(record)

        wanted = chosen["status"]
        if wanted == "فعال":
            if not record.get("is_active", False):
                return False
        elif wanted != ALL and status != wanted:
            return False

        checks = (
            ("category", record.get("equipment_category") or "بدون دسته"),
            ("location", record.get("equipment_location") or "بدون محل"),
            ("department", record.get("department_name") or "تعیین نشده"),
            ("frequency", frequency_text(record)),
        )
        for key, value in checks:
            if chosen[key] != ALL and value != chosen[key]:
                return False

        last_done = _iso_date(record.get("last_done"))   # "انجام نشده" -> None

        if chosen["history"] == "انجام‌شده" and last_done is None:
            return False
        if chosen["history"] == "هرگز انجام نشده" and last_done is not None:
            return False

        due = _iso_date(record.get("next_due"))
        if dates["due_from"] and (due is None or due < dates["due_from"]):
            return False
        if dates["due_to"] and (due is None or due > dates["due_to"]):
            return False
        if dates["done_from"] and (last_done is None or last_done < dates["done_from"]):
            return False
        if dates["done_to"] and (last_done is None or last_done > dates["done_to"]):
            return False

        return True

    # -------------------------------------------------------------------------

    def _apply_filter(self):

        chosen = {key: var.get() or ALL for key, var in self._fvars.items()}
        dates = {key: self._date_filter(key) for key, _label in DATE_FILTERS}

        search = (
            self._search_var.get()
            .strip()
            .lower()
        )

        filtered = []

        for record in self._all_records:

            if not self._matches(record, chosen, dates):
                continue

            if search:
                haystack = " ".join(str(v or "") for v in [
                    record.get("id"),
                    record.get("title"),
                    record.get("equipment_name"),
                    record.get("equipment_code"),
                    record.get("equipment_category"),
                    record.get("equipment_location"),
                    record.get("department_name"),
                    record.get("frequency"),
                    frequency_text(record),
                    record.get("interval_days"),
                    record.get("last_done"),
                    record.get("next_due"),
                    record.get("days_until"),
                    status_text(record),
                    record.get("checklist"),
                    record.get("notes"),
                    " ".join(self._parts_of(record)),
                    self._duration_text(record),
                ]).lower()

                if search not in haystack:
                    continue

            filtered.append(record)

        self._populate(filtered)

    # =========================================================================
    # POPULATE TABLE
    # =========================================================================

    def _populate(
        self,
        records: list,
    ):

        self._visible_records = list(records or [])

        self.tree.delete(
            *self.tree.get_children()
        )

        for record in records:

            days = record.get(
                "days_until"
            )

            status = status_text(
                record
            )

            tag = {
                "غیرفعال": "inactive",
                "عقب‌افتاده": "overdue",
                "این هفته": "upcoming",
            }.get(status, "ok")

            days_text = (
                str(days)
                if days is not None
                else "-"
            )

            # ---------------------------------------------------------------
            # Last done
            # ---------------------------------------------------------------

            last_done_raw = record.get(
                "last_done"
            )

            if (
                last_done_raw
                and last_done_raw
                != "انجام نشده"
            ):

                try:

                    if isinstance(
                        last_done_raw,
                        str,
                    ):

                        dt = datetime.strptime(
                            last_done_raw,
                            "%Y-%m-%d",
                        )

                    else:

                        dt = last_done_raw

                    last_done = (
                        to_jalali_date_str(
                            dt
                        )
                    )

                except Exception:

                    last_done = (
                        last_done_raw
                    )

            else:

                last_done = "انجام نشده"

            # ---------------------------------------------------------------
            # Next due
            # ---------------------------------------------------------------

            next_due_raw = record.get(
                "next_due"
            )

            if next_due_raw:

                try:

                    if isinstance(
                        next_due_raw,
                        str,
                    ):

                        dt = datetime.strptime(
                            next_due_raw,
                            "%Y-%m-%d",
                        )

                    else:

                        dt = next_due_raw

                    next_due = (
                        to_jalali_date_str(
                            dt
                        )
                    )

                except Exception:

                    next_due = (
                        next_due_raw
                    )

            else:

                next_due = "—"

            department_name = (
                record.get(
                    "department_name"
                )
                or "تعیین نشده"
            )

            equipment_name = (
                record.get(
                    "equipment_name"
                )
                or ""
            )

            equipment_code = (
                record.get(
                    "equipment_code"
                )
                or ""
            )

            equipment_label = (
                f"{equipment_code} - "
                f"{equipment_name}"
            )

            self.tree.insert(
                "",
                "end",
                iid=str(
                    record["id"]
                ),
                tags=(tag,),
                values=(
                    record["id"],
                    record.get(
                        "title",
                        "",
                    ),
                    equipment_label,
                    department_name,
                    frequency_text(
                        record
                    ),
                    last_done,
                    next_due,
                    days_text,
                    status,
                ),
            )

        count = len(
            records
        )

        total = len(
            self._all_records or []
        )

        if not count:
            text = "  بدون نتیجه  "
        elif count == total:
            text = f"  {count} برنامه  "
        else:
            text = f"  {count} از {total} برنامه  "

        self._row_count_lbl.config(
            text=text
        )

    # =========================================================================
    # SORT
    # =========================================================================

    def _sort(
        self,
        col,
    ):
        """
        Sort by a column; a second click reverses.  Numbers (شناسه, روز مانده)
        sort as numbers; empty values («-», «—», «انجام نشده») go last.
        """

        descending = self._sort_state.get(col, False)
        self._sort_state = {col: not descending}

        def key(pair):
            text = str(pair[0]).strip()
            if text in ("", "-", "—", "انجام نشده"):
                return (1, 0, "")
            try:
                return (0, float(text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))), "")
            except ValueError:
                return (0, 0, text)

        items = [
            (
                self.tree.set(
                    item,
                    col,
                ),
                item,
            )
            for item in self.tree.get_children("")
        ]

        filled = [pair for pair in items if key(pair)[0] == 0]
        empty = [pair for pair in items if key(pair)[0] == 1]
        filled.sort(key=key, reverse=descending)

        for index, (_, item) in enumerate(
            filled + empty
        ):

            self.tree.move(
                item,
                "",
                index,
            )

    # =========================================================================
    # SELECTION
    # =========================================================================

    def _selected_id(self):

        selection = (
            self.tree.selection()
        )

        if not selection:

            messagebox.showwarning(
                "انتخاب",
                "لطفاً یک برنامه انتخاب کنید.",
                parent=self,
            )

            return None

        try:

            return int(
                selection[0]
            )

        except (
            TypeError,
            ValueError,
        ):

            messagebox.showerror(
                "خطا",
                "شناسه برنامه نامعتبر است.",
                parent=self,
            )

            return None

    # =========================================================================
    # ADD
    # =========================================================================

    def _add(self):

        if not self.can_write:

            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به افزودن برنامه PM نیستید.",
                parent=self,
            )

            return

        from views.pm_dialog import PMDialog

        dlg = PMDialog(
            self,
            self.pm_repo,
            self.equipment_repo,
            self.user_repo,
        )

        self.wait_window(
            dlg
        )

        if dlg.result:

            self._load()

    # =========================================================================
    # EDIT
    # =========================================================================

    def _edit(self):

        if not self.can_write:

            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به ویرایش برنامه PM نیستید.",
                parent=self,
            )

            return

        sid = self._selected_id()

        if sid is None:
            return

        record = (
            self.pm_repo.get_by_id(
                sid
            )
        )

        if not record:
            return

        from views.pm_dialog import PMDialog

        dlg = PMDialog(
            self,
            self.pm_repo,
            self.equipment_repo,
            self.user_repo,
            schedule=record,
        )

        self.wait_window(
            dlg
        )

        if dlg.result:

            self._load()

    # =========================================================================
    # OPEN PM WORK ORDER
    # =========================================================================

    def _open_pm_work_order(self):

        if not self.can_write:

            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به مشاهده دستورکار PM نیستید.",
                parent=self,
            )

            return

        sid = self._selected_id()

        if sid is None:
            return

        record = (
            self.pm_repo.get_by_id(
                sid
            )
        )

        if not record:
            return

        next_due = record.get(
            "next_due_dt"
        )

        if not next_due:

            messagebox.showwarning(
                "دستورکار",
                (
                    "برای این PM تاریخ سررسید "
                    "مشخص نشده است."
                ),
                parent=self,
            )

            return

        # ---------------------------------------------------------------------
        # Find the generated Work Order for this PM.
        # ---------------------------------------------------------------------

        try:

            work_order = (
                self._wo_repo.find_by_schedule_and_date(
                    sid,
                    next_due,
                )
            )

        except Exception as exc:

            messagebox.showerror(
                "خطا",
                (
                    "خطایی هنگام پیدا کردن "
                    f"دستورکار PM رخ داد:\n\n{exc}"
                ),
                parent=self,
            )

            return

        if not work_order:

            messagebox.showinfo(
                "دستورکار PM",
                (
                    "برای این برنامه هنوز "
                    "دستورکار PM ایجاد نشده است.\n\n"
                    "دستورکار زمانی ایجاد می‌شود که "
                    "سرویس PM برنامه را به دستورکار تبدیل کند."
                ),
                parent=self,
            )

            return

        # ---------------------------------------------------------------------
        # Store the selected work order ID in the parent application.
        #
        # MainView already routes Work Orders through WorkOrderView.
        # We avoid directly duplicating that UI here.
        # ---------------------------------------------------------------------

        try:

            root = self.winfo_toplevel()

            show_view = getattr(
                root,
                "_show_view",
                None,
            )

            if callable(
                show_view
            ):

                show_view(
                    "work_orders"
                )

                messagebox.showinfo(
                    "دستورکار PM",
                    (
                        "دستورکار PM باز شد.\n\n"
                        "تکمیل واقعی کار و انتخاب "
                        "پرسنل انجام‌دهنده باید از "
                        "فرآیند درخواست اتمام دستورکار انجام شود."
                    ),
                    parent=self,
                )

            else:

                messagebox.showinfo(
                    "دستورکار PM",
                    (
                        "دستورکار PM ایجاد شده است.\n"
                        "برای ثبت پرسنل انجام‌دهنده، "
                        "آن را از بخش دستورکارها باز کنید."
                    ),
                    parent=self,
                )

        except Exception as exc:

            messagebox.showerror(
                "خطا",
                (
                    "خطایی هنگام باز کردن "
                    f"بخش دستورکارها رخ داد:\n\n{exc}"
                ),
                parent=self,
            )

    # =========================================================================
    # TOGGLE
    # =========================================================================

    def _toggle(self):

        if not self.can_write:

            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به تغییر وضعیت PM نیستید.",
                parent=self,
            )

            return

        sid = self._selected_id()

        if sid is None:
            return

        ok, msg = (
            self.pm_repo.toggle_active(
                sid
            )
        )

        if not ok:

            messagebox.showerror(
                "خطا",
                msg,
                parent=self,
            )

            return

        self._load()

    # =========================================================================
    # DELETE
    # =========================================================================

    def _delete(self):

        if not self.can_delete:

            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به حذف برنامه PM نیستید.",
                parent=self,
            )

            return

        sid = self._selected_id()

        if sid is None:
            return

        if not messagebox.askyesno(
            "حذف",
            (
                "آیا از حذف این برنامه PM "
                "مطمئن هستید؟"
            ),
            parent=self,
        ):

            return

        ok, msg = (
            self.pm_repo.delete(
                sid
            )
        )

        if ok:

            self._load()

            messagebox.showinfo(
                "موفق",
                msg,
                parent=self,
            )

        else:

            messagebox.showerror(
                "خطا",
                msg,
                parent=self,
            )

    # =========================================================================
    # EXPORT
    # =========================================================================

    def _export(self):

        from views.export_dialog import (
            run_pm_export
        )

        selection = self.tree.selection()

        visible_by_id = {}
        for record in self._visible_records or []:
            try:
                record_id = int(record.get("id"))
            except (TypeError, ValueError, AttributeError):
                continue
            visible_by_id[record_id] = record

        selected_pms = []
        for item in selection:
            try:
                record_id = int(item)
            except (TypeError, ValueError):
                continue
            record = visible_by_id.get(record_id)
            if record is not None:
                selected_pms.append(record)

        run_pm_export(
            self,
            self._all_records,
            selected_pms=selected_pms,
        )

    # =========================================================================
    # PRINTABLE PDF
    # =========================================================================

    def _export_pdf(self):
        from services.pdf_service import ROWS_PER_PAGE

        # Rows in the order the table shows them (also after sorting a column).
        record_by_id = {
            int(r.get("id")): r
            for r in self._visible_records
            if r.get("id") is not None
        }
        shown_ids = []
        for item in self.tree.get_children(""):
            try:
                shown_ids.append(int(item))
            except (TypeError, ValueError):
                pass

        selected_ids = set()
        for item in self.tree.selection():
            try:
                selected_ids.add(int(item))
            except (TypeError, ValueError):
                pass

        if selected_ids:
            records = [record_by_id[rid] for rid in shown_ids if rid in selected_ids and rid in record_by_id]
            scope_text = "برنامه‌های انتخاب‌شده"
        else:
            records = [record_by_id[rid] for rid in shown_ids if rid in record_by_id]
            scope_text = "همه برنامه‌های نمایش داده‌شده در جدول (پس از فیلتر)"

        if not records:
            messagebox.showwarning(
                "خروجی PDF",
                "هیچ برنامه PM برای چاپ/خروجی انتخاب نشده است.",
                parent=self,
            )
            return

        count = len(records)
        pages = (count + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
        first_id = records[0].get("id", "-")
        last_id = records[-1].get("id", "-")
        filters = self._active_filters()
        filters_text = (
            "\n".join(f"   • {line}" for line in filters)
            if filters else "   بدون فیلتر"
        )

        confirmation = (
            "آیا می‌خواهید خروجی PDF ایجاد شود؟\n\n"
            "نوع خروجی: فهرست چاپی برنامه‌های PM (جدول، A4 افقی)\n"
            f"دامنه: {scope_text}\n"
            f"تعداد برنامه‌ها: {count:,}\n"
            f"اولین شناسه: {first_id}\n"
            f"آخرین شناسه: {last_id}\n"
            f"فیلترها:\n{filters_text}\n"
            f"تعداد صفحات: {pages:,}\n"
            f"تعداد ردیف در هر صفحه: {ROWS_PER_PAGE}\n\n"
            "بعد از تأیید، محل ذخیره فایل PDF از شما پرسیده می‌شود."
        )

        if not messagebox.askyesno("تأیید خروجی PDF", confirmation, parent=self):
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"PM_Print_{jalali_stamp()}.pdf",
        )
        if not path:
            return

        try:
            from views.ui_kit import busy
            with busy(self):
                export_pm_pdf(records, path)
            messagebox.showinfo(
                "موفق",
                f"فایل PDF با موفقیت ایجاد شد.\n\nتعداد: {count:,}\nصفحات: {pages:,}",
                parent=self,
            )
            try:
                os.startfile(os.path.abspath(path))
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror(
                "خطا در PDF",
                f"ایجاد فایل PDF با خطا مواجه شد:\n\n{exc}",
                parent=self,
            )

    # =========================================================================
    # GLOBAL KEYBOARD HANDLERS  (called by MainView)
    # =========================================================================

    def handle_f2(self):
        """Called when F2 is pressed while this view is active."""
        self._edit_selected()

    def handle_new(self):
        """Called when Ctrl+N is pressed while this view is active."""
        self._add()

    def handle_enter(self):
        """Called when Enter is pressed while this view is active."""
        self._edit_selected()

    def ux_footer_spec(self):
        """Filters shown as removable chips under the table (views/ux.py)."""
        labels = dict(COMBO_FILTERS)
        filters = [(labels.get(key, key), var, ALL) for key, var in self._fvars.items()]
        filters.append(("جستجو", self._search_var, ""))
        return {"filters": filters, "apply": self._apply_filter,
                "total": lambda: len(self._all_records or []), "noun": "برنامه"}

