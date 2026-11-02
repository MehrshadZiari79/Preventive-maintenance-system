# views/reports_view.py
"""
PM System - Reports & Analytics View
====================================

UPDATED WORKFLOW
----------------

The application now distinguishes between:

    User
        = application/login account

    Personnel
        = actual maintenance worker

Work Order creation:
    Equipment + Department

Work completion:
    Department -> Personnel from that Department

Reports therefore use Personnel for actual completion performance.

Legacy User technician fields remain readable for historical records,
but they are no longer presented as the actual maintenance Personnel
when the new completion workflow is available.
"""
from views.detailed_report_tabs import attach_detail_tabs
import tkinter as tk
from views.ui_kit import reflow_grid, rtl_columns  # RTL (right-to-left) table columns
from tkinter import (
    ttk,
    messagebox,
    filedialog,
)

from datetime import (
    datetime,
    timedelta,
)

import threading
import json

from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
)

from matplotlib.figure import Figure

import numpy as np

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

from sqlalchemy import (
    func,
)

from database.models import (
    Personnel,
    Department,
    work_order_completers,
)

from database.report_repository import (
    ReportRepository,
)

from database.equipment_repository import (
    EquipmentRepository,
)

from database.work_order import (
    WorkOrder,
    WorkOrderType,
)

from database.work_order_repository import (
    WorkOrderRepository,
)

from database.spare_parts_repository import (
    SparePartsRepository,
)

from database.db import (
    SessionLocal,
)

from utils.theme import (
    NAVY,
    NAVY_LIGHT,
    WHITE,
    TEXT_DARK,
    TEXT_LIGHT,
    SUCCESS,
    FONT_TITLE,
    FONT_HEADING,
    FONT_NORMAL,
    FONT_SMALL,
    FONT_BOLD,
)

from views.jalali_date_entry import (
    JalaliDateEntry,
)

from utils.date_helpers import (
    to_jalali_date_str,
    to_jalali_datetime_str,
)
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock
from utils.date_helpers import jalali_stamp  # Jalali file names / stamps



# ============================================================================
# DESIGN TOKENS
# ============================================================================

CARD_BG = "#FFFFFF"
CARD_BORDER = "#E8ECF0"
SECTION_BG = "#F4F6F9"

HEADER_H = 72

ACCENT_TEAL = "#0D9488"
ACCENT_AMBER = "#D97706"
ACCENT_ROSE = "#DC2626"
ACCENT_BLUE = "#1D4ED8"
ACCENT_PURP = "#7C3AED"

STRIP_H = 4

FONT_SUBHEADING = (
    "Tahoma",
    11,
    "bold",
)


# ============================================================================
# STATUS / TYPE TRANSLATION
# ============================================================================

STATUS_FA = {
    "operational": "عملیاتی",
    "maintenance": "در تعمیر",
    "breakdown": "خراب",
    "inactive": "غیرفعال",
}


WO_TYPE_FA = {
    "PREVENTIVE": "پیشگیرانه",
    "CORRECTIVE": "اصلاحی",
    "EMERGENCY": "اضطراری",
    "INSPECTION": "بازرسی",
    "PM": "PM",
}


WO_STATUS_FA = {
    "PENDING": "در انتظار",
    "IN_PROGRESS": "در حال انجام",
    "FINISH_REQUESTED": "درخواست اتمام",
    "APPROVED": "تأیید شده",
    "REJECTED": "رد شده",
    "PENDING_APPROVAL": "در انتظار تأیید",
    "COMPLETED": "تکمیل شده",
}


# ============================================================================
# TTK STYLES
# ============================================================================

def _ttk_styles():

    style = ttk.Style()

    style.configure(
        "Report.Treeview",
        background=CARD_BG,
        fieldbackground=CARD_BG,
        foreground=TEXT_DARK,
        rowheight=28,
        font=("Tahoma", 9),
    )

    style.configure(
        "Report.Treeview.Heading",
        background=NAVY,
        foreground=WHITE,
        font=("Tahoma", 9, "bold"),
        relief="flat",
    )

    style.map(
        "Report.Treeview.Heading",
        background=[
            ("active", NAVY_LIGHT),
        ],
    )

    style.map(
        "Report.Treeview",
        background=[
            ("selected", NAVY),
        ],
        foreground=[
            ("selected", WHITE),
        ],
    )

    style.configure(
        "Report.TNotebook",
        background=SECTION_BG,
        tabmargins=[
            0,
            0,
            0,
            0,
        ],
    )

    style.configure(
        "Report.TNotebook.Tab",
        background=SECTION_BG,
        foreground=TEXT_LIGHT,
        font=("Tahoma", 9),
        padding=[
            10,
            7,
        ],
    )

    style.map(
        "Report.TNotebook.Tab",
        background=[
            ("selected", CARD_BG),
        ],
        foreground=[
            ("selected", NAVY),
        ],
    )


# ============================================================================
# REPORTS VIEW
# ============================================================================

class ReportsView(ttk.Frame):

    def __init__(
        self,
        parent,
        current_user,
    ):

        super().__init__(
            parent
        )

        # ------------------------------------------------------------------
        # Permissions
        # ------------------------------------------------------------------

        # built-in: admin / manager / technician; custom roles: «مدیریت نقش‌ها»
        from auth.auth_manager import AuthManager

        if not AuthManager.allows(("admin", "manager", "technician"), "reports", "read"):

            messagebox.showerror(
                "خطا",
                "دسترسی غیرمجاز. شما مجاز به مشاهده گزارشات نیستید.",
                parent=parent,
            )

            self.destroy()

            return

        self.current_user = (
            current_user
        )

        self.report_repo = (
            ReportRepository(
                SessionLocal
            )
        )

        self.eq_repo = (
            EquipmentRepository(
                SessionLocal
            )
        )

        self._loading = False

        self._sort_col = None

        self._sort_asc = True

        self._tabs_loaded = {
            "overview": False,
            "equipment": False,
            "kpi": False,
            "cost": False,
            "tech": False,
            "failure": False,
        }

        self._personnel_performance_data = []
        self._report_tab_data = {}

        _ttk_styles()

        self._build_ui()

        self._load_overview_tab()

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _card(
        self,
        parent,
        padx=12,
        pady=6,
        fill=tk.BOTH,
        expand=True,
    ):

        shadow = tk.Frame(
            parent,
            bg=CARD_BORDER,
        )

        shadow.pack(
            fill=fill,
            expand=expand,
            padx=padx,
            pady=pady,
        )

        inner = tk.Frame(
            shadow,
            bg=CARD_BG,
        )

        inner.pack(
            fill=tk.BOTH,
            expand=True,
            padx=1,
            pady=1,
        )

        return inner

    # -------------------------------------------------------------------------

    def _card_header(
        self,
        card,
        title,
        icon="",
    ):

        hdr = tk.Frame(
            card,
            bg=CARD_BG,
            pady=10,
        )

        hdr.pack(
            fill=tk.X,
            padx=14,
        )

        tk.Label(
            hdr,
            text=(
                f"{icon}  {title}"
                if icon
                else title
            ),
            font=FONT_SUBHEADING,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).pack(
            side=tk.RIGHT
        )

        tk.Frame(
            card,
            bg=CARD_BORDER,
            height=1,
        ).pack(
            fill=tk.X,
            padx=10,
        )

    # -------------------------------------------------------------------------

    def _section_label(
        self,
        parent,
        text,
        icon="",
    ):

        row = tk.Frame(
            parent,
            bg=SECTION_BG,
        )

        row.pack(
            fill=tk.X,
            padx=16,
            pady=(
                14,
                4,
            ),
        )

        tk.Label(
            row,
            text=(
                f"{icon}  {text}"
                if icon
                else text
            ),
            font=FONT_HEADING,
            bg=SECTION_BG,
            fg=TEXT_DARK,
        ).pack(
            side=tk.RIGHT
        )

    # -------------------------------------------------------------------------

    def _styled_tree(
        self,
        parent,
        columns,
        col_defs,
        height=15,
        sort_callback=None,
    ):

        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            height=height,
            style="Report.Treeview",
        )
        rtl_columns(tree)  # RTL column order

        for (
            col,
            text,
            width,
        ) in col_defs:

            tree.heading(
                col,
                text=text,
                command=(
                    lambda c=col:
                    sort_callback(c)
                    if sort_callback
                    else None
                ),
            )

            tree.column(
                col,
                width=width,
                anchor="center",
                minwidth=50,
            )

        tree.tag_configure(
            "odd",
            background=SECTION_BG,
        )

        tree.tag_configure(
            "even",
            background=CARD_BG,
        )

        vsb = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=tree.yview,
        )

        hsb = ttk.Scrollbar(
            parent,
            orient="horizontal",
            command=tree.xview,
        )

        tree.configure(
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
        )

        tree.grid(
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

        parent.rowconfigure(
            0,
            weight=1,
        )

        parent.columnconfigure(
            0,
            weight=1,
        )

        return tree

    # -------------------------------------------------------------------------

    def _sort_column(
        self,
        col,
    ):

        numeric_cols = {
            "total_wo",
            "completed",
            "pm",
            "cm",
            "em",
            "mtbf",
            "mttr",
            "availability",
            "oee",
            "downtime",
            "total_cost",
        }

        is_numeric = (
            col in numeric_cols
        )

        if self._sort_col == col:

            self._sort_asc = (
                not self._sort_asc
            )

        else:

            self._sort_col = col
            self._sort_asc = True

        items = []

        tree = getattr(
            self,
            "equipment_tree",
            None,
        )

        if tree is None:
            return

        for item in (
            tree.get_children("")
        ):

            val = tree.set(
                item,
                col,
            )

            if is_numeric:

                try:

                    numeric_val = float(
                        str(val)
                        .replace(",", "")
                        .replace(
                            "N/A",
                            "0",
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    numeric_val = None      # «—» (no data): always listed last

                items.append(
                    (
                        numeric_val,
                        item,
                    )
                )

            else:

                items.append(
                    (
                        str(val),
                        item,
                    )
                )

        empty = [pair for pair in items if pair[0] is None]
        items = [pair for pair in items if pair[0] is not None]

        items.sort(
            key=lambda x: x[0],
            reverse=(
                not self._sort_asc
            ),
        )

        for index, (_, item) in enumerate(
            items + empty
        ):

            tree.move(
                item,
                "",
                index,
            )

    # -------------------------------------------------------------------------

    def _fig(
        self,
        w=10,
        h=5,
    ):

        fig = Figure(
            figsize=(
                w,
                h,
            ),
            dpi=88,
            facecolor=CARD_BG,
        )

        ax = fig.add_subplot(
            111
        )

        ax.set_facecolor(
            CARD_BG
        )

        return (
            fig,
            ax,
        )

    # -------------------------------------------------------------------------

    def _embed_chart(
        self,
        fig,
        parent,
    ):

        cv = FigureCanvasTkAgg(
            fig,
            parent,
        )

        cv.draw()

        cv.get_tk_widget().pack(
            fill=tk.BOTH,
            expand=True,
            padx=8,
            pady=8,
        )

    # -------------------------------------------------------------------------

    def _kpi_card(
        self,
        parent,
        title,
        value,
        subtitle,
        color,
        icon,
        row,
        col,
    ):

        if not getattr(parent, "_reflow_installed", False):
            # cards wrap to fewer columns on narrow windows
            parent._reflow_installed = True
            parent.after_idle(lambda p=parent: reflow_grid(p, 175))

        shadow = tk.Frame(
            parent,
            bg=CARD_BORDER,
        )

        shadow.grid(
            row=row,
            column=col,
            padx=8,
            pady=8,
            sticky="nsew",
        )

        card = tk.Frame(
            shadow,
            bg=CARD_BG,
        )

        card.pack(
            fill=tk.BOTH,
            expand=True,
            padx=1,
            pady=1,
        )

        tk.Frame(
            card,
            bg=color,
            height=STRIP_H,
        ).pack(
            fill=tk.X
        )

        inner = tk.Frame(
            card,
            bg=CARD_BG,
        )

        inner.pack(
            fill=tk.BOTH,
            expand=True,
            padx=14,
            pady=10,
        )

        top = tk.Frame(
            inner,
            bg=CARD_BG,
        )

        top.pack(
            fill=tk.X
        )

        tk.Label(
            top,
            text=icon,
            font=("Tahoma", 14),
            bg=CARD_BG,
            fg=color,
        ).pack(
            side=tk.RIGHT
        )

        tk.Label(
            top,
            text=title,
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
        ).pack(
            side=tk.RIGHT,
            padx=(0, 4),
        )

        tk.Label(
            inner,
            text=str(value),
            font=(
                "Tahoma",
                22,
                "bold",
            ),
            bg=CARD_BG,
            fg=color,
        ).pack(
            anchor="center",
            pady=(
                6,
                2,
            ),
        )

        tk.Label(
            inner,
            text=subtitle,
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            wraplength=160,
            justify="center",
        ).pack(
            anchor="center"
        )

    # =========================================================================
    # MAIN UI
    # =========================================================================

    def _build_ui(self):

        self._build_header()
        self._build_filter_bar()
        self._build_notebook()
        self._add_export_buttons()

    # -------------------------------------------------------------------------

    def _build_header(self):

        hdr = tk.Frame(
            self,
            bg=NAVY,
            height=HEADER_H,
        )

        hdr.pack(
            fill=tk.X
        )

        hdr.pack_propagate(
            False
        )

        right = tk.Frame(
            hdr,
            bg=NAVY,
        )

        right.pack(
            side=tk.RIGHT,
            padx=24,
            fill=tk.Y,
        )

        tk.Label(
            right,
            text="📈",
            font=("Tahoma", 20),
            bg=NAVY,
            fg=WHITE,
        ).pack(
            side=tk.RIGHT,
            pady=16,
        )

        col = tk.Frame(
            right,
            bg=NAVY,
        )

        col.pack(
            side=tk.RIGHT,
            padx=(0, 10),
            fill=tk.Y,
        )

        tk.Label(
            col,
            text="گزارشات و تحلیل‌های پیشرفته",
            font=FONT_TITLE,
            bg=NAVY,
            fg=WHITE,
        ).pack(
            anchor="e",
            pady=(
                14,
                0,
            ),
        )

        tk.Label(
            col,
            text="داده‌های عملکردی سیستم نگهداری",
            font=FONT_SMALL,
            bg=NAVY,
            fg=NAVY_LIGHT,
        ).pack(
            anchor="e"
        )

        tk.Frame(
            self,
            bg=CARD_BORDER,
            height=1,
        ).pack(
            fill=tk.X
        )

    # =========================================================================
    # FILTER BAR
    # =========================================================================

    def _build_filter_bar(self):

        bar_outer = tk.Frame(
            self,
            bg=CARD_BG,
        )

        bar_outer.pack(
            fill=tk.X
        )

        tk.Frame(
            bar_outer,
            bg=CARD_BORDER,
            height=1,
        ).pack(
            fill=tk.X,
            side=tk.BOTTOM,
        )

        bar = tk.Frame(
            bar_outer,
            bg=CARD_BG,
        )

        bar.pack(
            padx=20,
            pady=10,
            anchor="e",
        )

        tk.Label(
            bar,
            text="از تاریخ:",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
        ).pack(
            side=tk.RIGHT,
            padx=(0, 4),
        )

        self.start_date = (
            JalaliDateEntry(
                bar,
                width=12,
            )
        )

        self.start_date.set_date(
            tehran_now()
            - timedelta(
                days=30
            )
        )

        self.start_date.pack(
            side=tk.RIGHT,
            padx=(0, 16),
        )

        tk.Label(
            bar,
            text="تا تاریخ:",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
        ).pack(
            side=tk.RIGHT,
            padx=(0, 4),
        )

        self.end_date = (
            JalaliDateEntry(
                bar,
                width=12,
            )
        )

        self.end_date.set_date(
            tehran_now()
        )

        self.end_date.pack(
            side=tk.RIGHT,
            padx=(0, 16),
        )

        tk.Button(
            bar,
            text="🔄  بروزرسانی",
            font=FONT_SMALL,
            bg=NAVY,
            fg=WHITE,
            activebackground=NAVY_LIGHT,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=6,
            command=self._refresh_all,
        ).pack(
            side=tk.RIGHT
        )

        tk.Label(
            bar,
            text="بازه سریع:",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
        ).pack(
            side=tk.RIGHT,
            padx=(20, 4),
        )

        for text, days in (
            ("۷ روز", 7),
            ("۳۰ روز", 30),
            ("۹۰ روز", 90),
            ("امسال", None),
        ):
            tk.Button(
                bar,
                text=text,
                font=FONT_SMALL,
                bg=SECTION_BG,
                fg=TEXT_DARK,
                relief="flat",
                cursor="hand2",
                padx=8,
                pady=4,
                command=lambda d=days: self._set_period(d),
            ).pack(
                side=tk.RIGHT,
                padx=2,
            )

    def _set_period(self, days):
        """Quick period: the last N days up to today, or this Jalali year."""
        today = tehran_now().date()
        if days is None:
            import jdatetime
            jalali_today = jdatetime.date.fromgregorian(date=today)
            start = jdatetime.date(jalali_today.year, 1, 1).togregorian()
        else:
            start = today - timedelta(days=days)
        self.start_date.set_date(start)
        self.end_date.set_date(today)
        self._refresh_all()


    # =========================================================================
    # NOTEBOOK
    # =========================================================================

    def _build_notebook(self):

        self.notebook = ttk.Notebook(
            self,
            style="Report.TNotebook",
        )

        self.notebook.pack(
            fill=tk.BOTH,
            expand=True,
            padx=0,
            pady=0,
        )

        self.overview_frame = tk.Frame(
            self.notebook,
            bg=SECTION_BG,
        )

        self.scorecard_frame = tk.Frame(
            self.notebook,
            bg=SECTION_BG,
        )

        self.equipment_frame = tk.Frame(
            self.notebook,
            bg=SECTION_BG,
        )

        self.kpi_frame = tk.Frame(
            self.notebook,
            bg=SECTION_BG,
        )

        self.cost_frame = tk.Frame(
            self.notebook,
            bg=SECTION_BG,
        )

        self.tech_frame = tk.Frame(
            self.notebook,
            bg=SECTION_BG,
        )

        self.failure_frame = tk.Frame(
            self.notebook,
            bg=SECTION_BG,
        )

        tabs = [
            (
                self.overview_frame,
                "📊  داشبورد کلی",
                "overview",
            ),
            (
                self.scorecard_frame,
                "📐  شاخص‌های استاندارد",
                "scorecard",
            ),
            (
                self.equipment_frame,
                "🛠️  تجهیزات",
                "equipment",
            ),
            (
                self.kpi_frame,
                "📈  KPI",
                "kpi",
            ),
            (
                self.cost_frame,
                "💰  هزینه",
                "cost",
            ),
            (
                self.tech_frame,
                "👷  پرسنل",
                "tech",
            ),
            (
                self.failure_frame,
                "⚠️  خرابی‌ها",
                "failure",
            ),
        ]

        for (
            frame,
            label,
            tag,
        ) in tabs:

            self.notebook.add(
                frame,
                text=label,
            )

            frame._tab_tag = tag

            loading = tk.Label(
                frame,
                text="⏳ در حال بارگذاری...",
                font=FONT_HEADING,
                bg=SECTION_BG,
                fg=TEXT_LIGHT,
            )

            loading.pack(
                expand=True
            )

            frame._loading_label = (
                loading
            )
        attach_detail_tabs(self)

        # Right-to-left tab order: the first report sits on the right.
        for tab_id in list(self.notebook.tabs()):
            self.notebook.insert(0, tab_id)
        self.notebook.select(self.overview_frame)
        self.notebook.bind(
            "<<NotebookTabChanged>>",
            self._on_tab_changed,
        )

    # =========================================================================
    # EXPORT BUTTONS
    # =========================================================================

    def _add_export_buttons(self):
        """Create Excel buttons only for the requested report tabs.

        The toolbar is stored on the tab frame so lazy loading and refresh
        can preserve it instead of accidentally destroying the button.
        """

        export_tabs = [
            (self.equipment_frame, "عملکرد تجهیزات"),
            (self.kpi_frame, "تحلیل KPI"),
            (self.tech_frame, "عملکرد پرسنل"),
            (self.failure_frame, "تحلیل خرابی‌ها"),
        ]

        for frame, title in export_tabs:
            toolbar = tk.Frame(
                frame,
                bg=CARD_BG,
            )
            toolbar.pack(
                fill=tk.X,
                side=tk.TOP,
            )
            frame._report_export_toolbar = toolbar

            tk.Frame(
                toolbar,
                bg=CARD_BORDER,
                height=1,
            ).pack(
                fill=tk.X,
                side=tk.BOTTOM,
            )

            tk.Button(
                toolbar,
                text="📊  خروجی Excel این گزارش",
                font=FONT_SMALL,
                bg=ACCENT_TEAL,
                fg=WHITE,
                activebackground=NAVY_LIGHT,
                activeforeground=WHITE,
                relief="flat",
                cursor="hand2",
                padx=14,
                pady=7,
                command=lambda f=frame, t=title: self._export_tab_to_excel(f, t),
            ).pack(
                side=tk.LEFT,
                padx=12,
                pady=8,
            )

            tk.Label(
                toolbar,
                text="بازه زمانی انتخاب‌شده در خروجی اعمال می‌شود",
                font=FONT_SMALL,
                bg=CARD_BG,
                fg=TEXT_LIGHT,
                anchor="e",
            ).pack(
                side=tk.RIGHT,
                padx=12,
                pady=8,
            )

    # =========================================================================
    # LAZY LOADING
    # =========================================================================

    def _load_overview_tab(self):
        self._load_tab_data(
            "overview"
        )

    # -------------------------------------------------------------------------

    def _on_tab_changed(
        self,
        event,
    ):

        selected = (
            self.notebook.select()
        )

        if not selected:
            return

        frame = (
            self.notebook
            .nametowidget(
                selected
            )
        )

        tag = getattr(
            frame,
            "_tab_tag",
            None,
        )

        if (
            tag
            and not self._tabs_loaded.get(
                tag,
                False,
            )
        ):

            self._load_tab_data(
                tag
            )

    # -------------------------------------------------------------------------

    def _load_tab_data(
        self,
        tag,
    ):

        if self._tabs_loaded.get(
            tag,
            False,
        ):

            return

        self._tabs_loaded[
            tag
        ] = True

        frame = getattr(
            self,
            f"{tag}_frame",
            None,
        )

        if not frame:
            return

        loading = getattr(
            frame,
            "_loading_label",
            None,
        )

        if loading:
            loading.pack(
                expand=True
            )

        export_toolbar = getattr(
            frame,
            "_report_export_toolbar",
            None,
        )

        for child in frame.winfo_children():
            if child in (loading, export_toolbar):
                continue
            child.destroy()

        # Tk widgets are read here, on the UI thread - never in the worker.
        start_value = self.start_date.get_date()
        end_value = self.end_date.get_date()

        if start_value and end_value and start_value > end_value:
            self._show_tab_error(
                tag,
                "«از تاریخ» بعد از «تا تاریخ» است. بازه را اصلاح کنید و «بروزرسانی» را بزنید.",
            )
            self._tabs_loaded[tag] = False
            return

        def post(callback):
            # the report window may have been closed meanwhile (logout, page change)
            try:
                self.after(0, callback)
            except (RuntimeError, tk.TclError):
                pass

        def load_thread():

            try:

                start = start_value

                end = end_value

                if tag == "overview":

                    data = {
                        "summary":
                            self.report_repo
                            .get_kpi_summary(
                                start,
                                end,
                            ),

                        "backlog":
                            self.report_repo
                            .get_backlog_analysis(
                                start,
                                end,
                            ),

                        "rejection":
                            self.report_repo
                            .get_rejection_percentage(
                                start,
                                end,
                            ),

                        "delay":
                            self.report_repo
                            .get_delay_summary(
                                start,
                                end,
                            ),
                    }

                elif tag == "scorecard":

                    from database.scorecard_repository import ScorecardRepository
                    data = ScorecardRepository(
                        self.report_repo.Session
                    ).build(start, end, self.report_repo)

                elif tag == "equipment":

                    data = (
                        self.report_repo
                        .get_all_equipment_performance(
                            start,
                            end,
                        )
                    )

                elif tag == "kpi":

                    data = {
                        "trend":
                            self._get_kpi_trend_for_period(
                                start,
                                end,
                            ),

                        "compliance":
                            self.report_repo
                            .get_schedule_compliance(
                                start,
                                end,
                            ),

                        "risk":
                            self.report_repo
                            .get_equipment_risk_score(),

                        "pm_cm":
                            self.report_repo
                            .get_pm_cm_ratio(
                                start,
                                end,
                            ),
                    }

                elif tag == "cost":

                    data = (
                        self.report_repo
                        .get_cost_analysis(
                            start,
                            end,
                        )
                    )

                elif tag == "tech":

                    # ------------------------------------------------------
                    # NEW PERSONNEL REPORT
                    #
                    # Do NOT use get_technician_performance() here because
                    # that is the old User-based workflow.
                    # ------------------------------------------------------

                    data = (
                        self._get_personnel_performance(
                            start,
                            end,
                        )
                    )

                elif tag == "failure":

                    data = (
                        self.report_repo
                        .get_top_failure_modes(
                            start,
                            end,
                            limit=50,
                        )
                    )

                else:

                    data = None

                post(
                    lambda:
                    self._render_tab(
                        tag,
                        data,
                    ),
                )

            except Exception as exc:

                error_msg = str(
                    exc
                )

                post(
                    lambda:
                    self._show_tab_error(
                        tag,
                        error_msg,
                    ),
                )

        threading.Thread(
            target=load_thread,
            daemon=True,
        ).start()

    def _get_kpi_trend_for_period(self, start_date, end_date):
        """Return monthly PM/CM/EM trend restricted to the selected period."""
        try:
            if start_date and end_date and start_date > end_date:
                return []

            # get_monthly_trends() is anchored to now, so request enough
            # months to cover the selected range and then apply the exact
            # selected month bounds locally. This keeps compatibility with
            # the existing ReportRepository API.
            now = tehran_now()
            months_back = 6
            if start_date:
                months_back = max(6, (now.year - start_date.year) * 12 + (now.month - start_date.month) + 2)

            trend = self.report_repo.get_monthly_trends(months_back) or []

            if not start_date and not end_date:
                return trend

            filtered = []
            for item in trend:
                try:
                    year = int(item.get("year"))
                    month = int(item.get("month"))
                except (TypeError, ValueError):
                    continue

                # Trend months are Jalali (see ReportRepository.get_monthly_trends).
                import jdatetime
                from utils.date_helpers import jalali_month_start
                month_start = jdatetime.date(year, month, 1).togregorian()
                if start_date:
                    start_d = start_date.date() if hasattr(start_date, "date") else start_date
                    if month_start < jalali_month_start(start_d):
                        continue
                if end_date:
                    end_d = end_date.date() if hasattr(end_date, "date") else end_date
                    if month_start > jalali_month_start(end_d):
                        continue
                filtered.append(item)

            return filtered
        except Exception:
            return []

    # =========================================================================
    # NEW PERSONNEL REPORT
    # =========================================================================

    def _get_personnel_performance(
        self,
        start_date,
        end_date,
    ):
        """
        Calculate actual Personnel performance from the new completion
        relationship.

        This method uses:
            work_orders
                +
            work_order_completers
                +
            personnel
                +
            departments

        It deliberately does NOT use User.technician_id.

        Returns dictionaries compatible with the report renderer.
        """

        session = SessionLocal()

        try:

            # --------------------------------------------------------------
            # The new tables may not exist until Migration 002 is run.
            # Fail safely instead of breaking the whole Reports page.
            # --------------------------------------------------------------

            try:

                personnel_query = (
                    session.query(
                        Personnel.id,
                        Personnel.personnel_code,
                        Personnel.full_name,
                        Department.name.label(
                            "department_name"
                        ),

                        func.count(
                            WorkOrder.id
                        ).label(
                            "total_tasks"
                        ),

                        func.sum(
                            case=(
                                False
                                if False
                                else 0
                            )
                        ) if False else None,
                    )
                )

            except Exception:
                # We don't use this temporary query.
                # The actual grouped query is below.
                personnel_query = None

            # --------------------------------------------------------------
            # Build one row at a time.
            #
            # This avoids relying on SQL Server-specific conditional
            # aggregation syntax and remains compatible with the existing
            # SQLAlchemy version.
            # --------------------------------------------------------------

            personnel_list = (
                session.query(
                    Personnel
                )
                .options(
                    # Department is loaded through the Personnel relationship.
                )
                .order_by(
                    Personnel.full_name.asc()
                )
                .all()
            )

            results = []

            for person in personnel_list:

                base_query = (
                    session.query(
                        WorkOrder
                    )
                    .join(
                        work_order_completers,
                        work_order_completers.c.work_order_id
                        == WorkOrder.id,
                    )
                    .filter(
                        work_order_completers.c.personnel_id
                        == person.id
                    )
                )

                if start_date:

                    base_query = (
                        base_query.filter(
                            WorkOrder.created_at
                            >= start_date
                        )
                    )

                if end_date:

                    end_exclusive = (
                        end_date
                        + timedelta(
                            days=1
                        )
                    )

                    base_query = (
                        base_query.filter(
                            WorkOrder.created_at
                            < end_exclusive
                        )
                    )

                work_orders = (
                    base_query
                    .all()
                )

                total_tasks = len(
                    work_orders
                )

                completed_tasks = 0
                duration_hours = []

                for wo in work_orders:

                    status_name = (
                        getattr(
                            wo.status,
                            "name",
                            "",
                        )
                        or ""
                    ).upper()

                    if status_name in {
                        "APPROVED",
                        "COMPLETED",
                    }:

                        completed_tasks += 1

                    if (
                        wo.start_time
                        and wo.end_time
                    ):

                        try:

                            seconds = (
                                wo.end_time
                                - wo.start_time
                            ).total_seconds()

                            hours = (
                                seconds
                                / 3600.0
                            )

                            if hours >= 0:

                                duration_hours.append(
                                    hours
                                )

                        except Exception:
                            pass

                completion_rate = (
                    (
                        completed_tasks
                        / total_tasks
                    )
                    * 100.0
                    if total_tasks
                    else 0.0
                )

                avg_completion_hours = (
                    sum(
                        duration_hours
                    )
                    / len(
                        duration_hours
                    )
                    if duration_hours
                    else 0.0
                )

                department = getattr(
                    person,
                    "department",
                    None,
                )

                department_name = (
                    getattr(
                        department,
                        "name",
                        "",
                    )
                    or "بدون دپارتمان"
                )

                personnel_code = (
                    getattr(
                        person,
                        "personnel_code",
                        "",
                    )
                    or ""
                )

                full_name = (
                    getattr(
                        person,
                        "full_name",
                        "",
                    )
                    or "—"
                )

                if personnel_code:

                    display_name = (
                        f"{personnel_code} - "
                        f"{full_name}"
                    )

                else:

                    display_name = (
                        full_name
                    )

                results.append(
                    {
                        "personnel_id":
                            person.id,

                        "personnel_code":
                            personnel_code,

                        "personnel_name":
                            display_name,

                        "department_name":
                            department_name,

                        "total_tasks":
                            total_tasks,

                        "completed_tasks":
                            completed_tasks,

                        "completion_rate":
                            completion_rate,

                        "avg_completion_hours":
                            avg_completion_hours,
                    }
                )

            # --------------------------------------------------------------
            # Show Personnel with activity first, then inactive Personnel.
            # --------------------------------------------------------------

            results.sort(
                key=lambda item: (
                    -item["completed_tasks"],
                    -item["total_tasks"],
                    item["personnel_name"],
                )
            )

            return results

        except Exception as exc:

            print(
                "Personnel report error:",
                exc,
            )

            raise

        finally:

            session.close()

    # =========================================================================
    # RENDER TAB
    # =========================================================================

    def _render_tab(
        self,
        tag,
        data,
    ):

        frame = getattr(
            self,
            f"{tag}_frame",
            None,
        )

        if not frame:
            return

        loading = getattr(
            frame,
            "_loading_label",
            None,
        )

        if loading:

            try:
                loading.destroy()
            except Exception:
                pass

            try:
                delattr(
                    frame,
                    "_loading_label",
                )
            except Exception:
                pass

        self._report_tab_data[tag] = data

        if tag == "overview":

            self._render_overview(
                frame,
                data,
            )

        elif tag == "scorecard":

            from views.report_scorecard import render_scorecard
            render_scorecard(self, frame, data)

        elif tag == "equipment":

            self._render_equipment(
                frame,
                data,
            )

        elif tag == "kpi":

            self._render_kpi(
                frame,
                data,
            )

        elif tag == "cost":

            self._render_cost(
                frame,
                data,
            )

        elif tag == "tech":

            self._render_tech(
                frame,
                data,
            )

        elif tag == "failure":

            self._render_failure(
                frame,
                data,
            )

        self._tabs_loaded[
            tag
        ] = True

    # -------------------------------------------------------------------------

    def _show_tab_error(
        self,
        tag,
        error,
    ):

        frame = getattr(
            self,
            f"{tag}_frame",
            None,
        )

        if not frame:
            return

        loading = getattr(
            frame,
            "_loading_label",
            None,
        )

        if loading:

            loading.config(
                text=(
                    f"❌ خطا: {error}"
                ),
                fg=ACCENT_ROSE,
            )

    # =========================================================================
    # OVERVIEW
    # =========================================================================

    def _render_overview(
        self,
        parent,
        data,
    ):

        summary = data[
            "summary"
        ]

        backlog = data[
            "backlog"
        ]

        rejection = data[
            "rejection"
        ]

        delay = data[
            "delay"
        ]

        self._section_label(
            parent,
            "شاخص‌های اصلی عملکرد",
            "📌",
        )

        g1 = tk.Frame(
            parent,
            bg=SECTION_BG,
        )

        g1.pack(
            fill=tk.X,
            padx=16,
            pady=(0, 4),
        )

        total = summary.get(
            "total_work_orders",
            0,
        )

        done = summary.get(
            "completed_work_orders",
            0,
        )

        prog = summary.get(
            "in_progress_work_orders",
            0,
        )

        overdue = summary.get(
            "overdue_work_orders",
            0,
        )

        comp_pct = (
            (
                done
                / max(
                    1,
                    total,
                )
            )
            * 100
            if total
            else 0
        )

        values = [
            (
                "کل دستورات کار",
                total,
                "تمام دستورات ثبت شده",
                ACCENT_BLUE,
                "📋",
                0,
            ),
            (
                "تکمیل شده",
                done,
                f"{comp_pct:.1f}٪ از کل",
                SUCCESS,
                "✅",
                1,
            ),
            (
                "در حال انجام",
                prog,
                "دستورات فعال",
                ACCENT_AMBER,
                "🔄",
                2,
            ),
            (
                "معوق",
                overdue,
                "نیاز به توجه فوری",
                ACCENT_ROSE,
                "🚨",
                3,
            ),
            (
                "درصد رد کارها",
                f"{rejection['percentage']:.1f}٪",
                (
                    f"{rejection['rejected']} "
                    f"از {rejection['total']}"
                ),
                ACCENT_ROSE,
                "🚫",
                4,
            ),
            (
                "مجموع تأخیر",
                f"{delay['total_minutes']} دقیقه",
                (
                    f"{delay['delayed_count']} "
                    "کار دارای تأخیر"
                ),
                ACCENT_AMBER,
                "⏳",
                5,
            ),
        ]

        for (
            title,
            val,
            sub,
            color,
            icon,
            col,
        ) in values:

            self._kpi_card(
                g1,
                title,
                val,
                sub,
                color,
                icon,
                0,
                col,
            )

            g1.columnconfigure(
                col,
                weight=1,
            )

        g2 = tk.Frame(
            parent,
            bg=SECTION_BG,
        )

        g2.pack(
            fill=tk.X,
            padx=16,
            pady=(0, 4),
        )

        total_eq = summary.get(
            "total_equipment",
            0,
        )

        op_eq = summary.get(
            "operational_equipment",
            0,
        )

        avg_t = summary.get(
            "avg_completion_time_hours",
            0,
        )

        pm_comp = summary.get(
            "pm_compliance_rate",
            0,
        )

        op_pct = (
            (
                op_eq
                / max(
                    1,
                    total_eq,
                )
            )
            * 100
            if total_eq
            else 0
        )

        values = [
            (
                "کل تجهیزات",
                total_eq,
                "تجهیزات ثبت شده",
                ACCENT_PURP,
                "⚙️",
                0,
            ),
            (
                "عملیاتی",
                op_eq,
                f"{op_pct:.1f}٪ آماده",
                ACCENT_TEAL,
                "✅",
                1,
            ),
            (
                "میانگین زمان تعمیر",
                f"{avg_t:.1f} ساعت",
                "میانگین تعمیر",
                "#795548",
                "⏱️",
                2,
            ),
            (
                "انطباق PM",
                f"{pm_comp:.1f}٪",
                "نگهداری پیشگیرانه",
                NAVY,
                "🎯",
                3,
            ),
        ]

        for (
            title,
            val,
            sub,
            color,
            icon,
            col,
        ) in values:

            self._kpi_card(
                g2,
                title,
                val,
                sub,
                color,
                icon,
                0,
                col,
            )

            g2.columnconfigure(
                col,
                weight=1,
            )

        self._section_label(
            parent,
            "تحلیل کارهای معوق",
            "📂",
        )

        g3 = tk.Frame(
            parent,
            bg=SECTION_BG,
        )

        g3.pack(
            fill=tk.X,
            padx=16,
            pady=(0, 16),
        )

        values = [
            (
                "در انتظار",
                backlog.get(
                    "pending",
                    0,
                ),
                "دستورات معلق",
                "#FFC107",
                "⏳",
                0,
            ),
            (
                "در حال انجام",
                backlog.get(
                    "in_progress",
                    0,
                ),
                "در دست اقدام",
                "#03A9F4",
                "🔄",
                1,
            ),
            (
                "سررسید گذشته",
                backlog.get(
                    "overdue",
                    0,
                ),
                "نیاز به اقدام فوری",
                "#E91E63",
                "❗",
                2,
            ),
            (
                "کل معوقات",
                backlog.get(
                    "total_backlog",
                    0,
                ),
                "مجموع کارهای باز",
                "#673AB7",
                "📋",
                3,
            ),
        ]

        for (
            title,
            val,
            sub,
            color,
            icon,
            col,
        ) in values:

            self._kpi_card(
                g3,
                title,
                val,
                sub,
                color,
                icon,
                0,
                col,
            )

            g3.columnconfigure(
                col,
                weight=1,
            )

    # =========================================================================
    # EQUIPMENT
    # =========================================================================

    # Equipment report filters (label above each control, right to left)
    _EQ_ALL = "همه"
    _EQ_NONE_CATEGORY = "بدون دسته"
    _EQ_NONE_LOCATION = "بدون محل"

    def _render_equipment(
        self,
        parent,
        performance_data,
    ):

        self._equipment_data = [
            row for row in (performance_data or [])
            if isinstance(row, dict)
        ]
        data = self._equipment_data
        ALL = self._EQ_ALL

        card = self._card(
            parent,
            padx=12,
            pady=10,
        )

        self._card_header(
            card,
            "عملکرد تجهیزات",
            "🛠️",
        )

        # ---------------- filters ----------------
        filters = tk.Frame(card, bg=CARD_BG)
        filters.pack(fill=tk.X, padx=10, pady=(5, 0))

        def values(items, empty_label):
            found = sorted({(v or empty_label) for v in items})
            return [ALL, *found]

        statuses = [ALL] + [
            STATUS_FA.get(s, s) for s in
            sorted({str(r.get("equipment_status") or "") for r in data if r.get("equipment_status")})
        ]

        self.eq_search_var = tk.StringVar()
        self.eq_cat_var = tk.StringVar(value=ALL)
        self.eq_loc_var = tk.StringVar(value=ALL)
        self.eq_status_var = tk.StringVar(value=ALL)
        self.eq_wo_var = tk.StringVar(value=ALL)
        self.eq_prod_var = tk.StringVar(value=ALL)

        grid = tk.Frame(filters, bg=CARD_BG)
        grid.pack(fill=tk.X)

        def cell(label):
            frame = tk.Frame(grid, bg=CARD_BG)
            tk.Label(frame, text=label, font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT,
                     anchor="e").pack(fill=tk.X)
            return frame

        cells = []

        search_cell = cell("🔍  جستجو (نام، کد، دسته، محل)")
        search_entry = tk.Entry(search_cell, textvariable=self.eq_search_var, font=FONT_NORMAL,
                                relief="solid", bd=1, justify="right")
        search_entry.pack(fill=tk.X, pady=(2, 0), ipady=3)
        self.eq_search_var.trace_add("write", lambda *_: self._refresh_equipment_table())
        cells.append(search_cell)

        combos = (
            ("دسته تجهیز", self.eq_cat_var,
             values((r.get("equipment_category") for r in data), self._EQ_NONE_CATEGORY)),
            ("محل (Location)", self.eq_loc_var,
             values((r.get("equipment_location") for r in data), self._EQ_NONE_LOCATION)),
            ("وضعیت تجهیز", self.eq_status_var, statuses),
            ("دستورکار در این بازه", self.eq_wo_var, [ALL, "دارای دستورکار", "بدون دستورکار"]),
            ("ساعت کار ثبت‌شده", self.eq_prod_var, [ALL, "دارای ساعت کار", "بدون ساعت کار"]),
        )
        for label, var, items in combos:
            frame = cell(label)
            combo = ttk.Combobox(frame, textvariable=var, values=items, state="readonly",
                                 font=FONT_SMALL, width=14, justify="right")
            combo.pack(fill=tk.X, pady=(2, 0))
            combo.bind("<<ComboboxSelected>>", lambda *_: self._refresh_equipment_table())
            cells.append(frame)

        columns = len(cells)
        for index, frame in enumerate(cells):
            frame.grid(row=0, column=columns - 1 - index, sticky="ew", padx=5, pady=3)
        for column in range(columns):
            grid.columnconfigure(column, weight=2 if column == columns - 1 else 1,
                                 uniform="" if column == columns - 1 else "eqf")
        reflow_grid(grid, min_width=150)

        # count + clear
        tools = tk.Frame(filters, bg=CARD_BG)
        tools.pack(fill=tk.X, pady=(4, 0))
        self.eq_count_lbl = tk.Label(tools, text="", font=FONT_SMALL, bg=NAVY, fg=WHITE, padx=10, pady=2)
        self.eq_count_lbl.pack(side=tk.LEFT)
        tk.Button(tools, text="✖  پاک کردن فیلترها", font=FONT_SMALL, bg=SECTION_BG, fg=TEXT_DARK,
                  relief="flat", cursor="hand2", padx=10, pady=3,
                  command=self._clear_equipment_filters).pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(tools, text="برای جزئیات هر تجهیز روی ردیف آن دوبار کلیک کنید.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side=tk.RIGHT)

        # ---------------- summary of the rows shown ----------------
        self.eq_summary = tk.Frame(card, bg=CARD_BG)
        self.eq_summary.pack(fill=tk.X, padx=10, pady=(8, 0))

        # ---------------- table ----------------
        tree_frame = tk.Frame(card, bg=CARD_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = (
            "id", "name", "category", "location", "status",
            "total_wo", "completed", "pm", "cm", "em",
            "mtbf", "mttr", "availability", "oee", "downtime", "total_cost",
        )
        col_defs = [
            ("id", "شناسه", 50),
            ("name", "نام تجهیز", 180),
            ("category", "دسته", 100),
            ("location", "محل", 100),
            ("status", "وضعیت", 85),
            ("total_wo", "کل WO", 65),
            ("completed", "تکمیل شده", 80),
            ("pm", "PM", 50),
            ("cm", "CM", 50),
            ("em", "EM", 50),
            ("mtbf", "MTBF (h)", 80),
            ("mttr", "MTTR (h)", 80),
            ("availability", "دسترسی٪", 75),
            ("oee", "OEE٪", 65),
            ("downtime", "توقف (h)", 80),
            ("total_cost", "هزینه کل (ریال)", 130),
        ]

        self.equipment_tree = self._styled_tree(
            tree_frame,
            columns,
            col_defs,
            height=18,
            sort_callback=self._sort_column,
        )

        self.equipment_tree.bind(
            "<Double-1>",
            self._open_equipment_detail,
        )

        self._refresh_equipment_table()

    # -------------------------------------------------------------------------

    def _clear_equipment_filters(self):
        for name in ("eq_cat_var", "eq_loc_var", "eq_status_var", "eq_wo_var", "eq_prod_var"):
            var = getattr(self, name, None)
            if var is not None:
                var.set(self._EQ_ALL)
        if getattr(self, "eq_search_var", None) is not None:
            self.eq_search_var.set("")          # also refreshes the table
        self._refresh_equipment_table()

    def _equipment_rows_filtered(self):
        """Rows of the equipment report that pass every filter."""
        ALL = self._EQ_ALL
        data = getattr(self, "_equipment_data", None) or []

        def get(name):
            var = getattr(self, name, None)
            return var.get() if var is not None else ALL

        search = get("eq_search_var").strip().lower() if hasattr(self, "eq_search_var") else ""
        category, location = get("eq_cat_var"), get("eq_loc_var")
        status, has_wo, has_prod = get("eq_status_var"), get("eq_wo_var"), get("eq_prod_var")

        rows = []
        for eq in data:
            cat = eq.get("equipment_category") or self._EQ_NONE_CATEGORY
            loc = eq.get("equipment_location") or self._EQ_NONE_LOCATION
            if search:
                haystack = " ".join(str(v or "") for v in (
                    eq.get("equipment_name"), eq.get("equipment_code"), cat, loc,
                )).lower()
                if search not in haystack:
                    continue
            if category not in ("", ALL) and cat != category:
                continue
            if location not in ("", ALL) and loc != location:
                continue
            status_text = STATUS_FA.get(eq.get("equipment_status") or "", eq.get("equipment_status") or "")
            if status not in ("", ALL) and status_text != status:
                continue
            total_wo = int(eq.get("total_work_orders") or 0)
            if has_wo == "دارای دستورکار" and total_wo == 0:
                continue
            if has_wo == "بدون دستورکار" and total_wo > 0:
                continue
            planned = float(eq.get("planned_hours") or 0)
            if has_prod == "دارای ساعت کار" and planned <= 0:
                continue
            if has_prod == "بدون ساعت کار" and planned > 0:
                continue
            rows.append(eq)
        return rows

    def _refresh_equipment_summary(self, rows):
        frame = getattr(self, "eq_summary", None)
        if frame is None:
            return
        for child in frame.winfo_children():
            child.destroy()

        planned = sum(float(r.get("planned_hours") or 0) for r in rows)
        operating = sum(float(r.get("operating_hours") or 0) for r in rows)
        # availability of the group = operating / planned hours (only equipment with logs)
        availability = f"{operating / planned * 100:,.1f}٪" if planned > 0 else "—"
        items = (
            ("تعداد تجهیز", f"{len(rows):,}"),
            ("کل دستورکارها", f"{sum(int(r.get('total_work_orders') or 0) for r in rows):,}"),
            ("تکمیل‌شده", f"{sum(int(r.get('completed_work_orders') or 0) for r in rows):,}"),
            ("PM / CM / EM", "{:,} / {:,} / {:,}".format(
                sum(int(r.get("pm_work_orders") or 0) for r in rows),
                sum(int(r.get("cm_work_orders") or 0) for r in rows),
                sum(int(r.get("em_work_orders") or 0) for r in rows))),
            ("دسترسی کل گروه", availability),
            ("کل توقف (ساعت)", f"{sum(float(r.get('total_downtime_hours') or 0) for r in rows):,.1f}"),
            ("کل هزینه (ریال)", f"{sum(float(r.get('total_cost') or 0) for r in rows):,.0f}"),
        )
        for index, (label, value) in enumerate(items):
            box = tk.Frame(frame, bg=SECTION_BG, padx=10, pady=4)
            box.grid(row=0, column=len(items) - 1 - index, sticky="nsew", padx=3)
            tk.Label(box, text=label, font=FONT_SMALL, bg=SECTION_BG, fg=TEXT_LIGHT).pack()
            tk.Label(box, text=value, font=FONT_BOLD, bg=SECTION_BG, fg=NAVY).pack()
            frame.columnconfigure(len(items) - 1 - index, weight=1, uniform="eqsum")
        reflow_grid(frame, min_width=120)

    def _refresh_equipment_table(
        self
    ):

        tree = getattr(
            self,
            "equipment_tree",
            None,
        )

        if tree is None:
            return

        tree.delete(
            *tree.get_children()
        )

        rows = self._equipment_rows_filtered()
        total = len(getattr(self, "_equipment_data", None) or [])

        label = getattr(self, "eq_count_lbl", None)
        if label is not None:
            if not rows:
                text = "  بدون نتیجه  "
            elif len(rows) == total:
                text = f"  {len(rows)} تجهیز  "
            else:
                text = f"  {len(rows)} از {total} تجهیز  "
            label.configure(text=text)

        self._refresh_equipment_summary(rows)

        for i, eq in enumerate(rows):

            # no production hours logged -> availability / OEE are unknown, not 0 %
            has_logs = float(eq.get("planned_hours") or 0) > 0

            tree.insert(
                "",
                tk.END,
                tags=("even" if i % 2 == 0 else "odd",),
                values=(
                    eq.get("equipment_id", 0),
                    eq.get("equipment_name", "—"),
                    eq.get("equipment_category") or "—",
                    eq.get("equipment_location") or "—",
                    STATUS_FA.get(eq.get("equipment_status", ""), eq.get("equipment_status", "—")),
                    eq.get("total_work_orders", 0),
                    eq.get("completed_work_orders", 0),
                    eq.get("pm_work_orders", 0),
                    eq.get("cm_work_orders", 0),
                    eq.get("em_work_orders", 0),
                    eq.get("mtbf_hours", 0) if has_logs else "—",
                    eq.get("mttr_hours", 0),
                    eq.get("availability", 0) if has_logs else "—",
                    eq.get("oee", 0) if has_logs else "—",
                    eq.get("total_downtime_hours", 0),
                    f"{float(eq.get('total_cost', 0) or 0):,.0f}",
                ),
            )

    # =========================================================================
    # KPI
    # =========================================================================

    def _render_kpi(
        self,
        parent,
        data,
    ):

        trend_data = (
            data["trend"]
        )

        compliance = (
            data["compliance"]
        )

        risk_data = (
            data["risk"]
        )

        pm_cm = (
            data["pm_cm"]
        )

        trend_card = self._card(
            parent
        )

        self._card_header(
            trend_card,
            "روند ماهانه PM / CM / EM",
            "📅",
        )

        if (
            trend_data
            and any(
                item["count"] > 0
                for item in trend_data
            )
        ):

            months_dict = {}

            for item in trend_data:

                key = (
                    f"{item['year']}-"
                    f"{item['month']:02d}"
                )

                if key not in months_dict:

                    months_dict[key] = {
                        "PM": 0,
                        "CM": 0,
                        "EM": 0,
                    }

                typ = item[
                    "type"
                ]

                if typ in (
                    "PREVENTIVE",
                    "PM",
                ):

                    months_dict[
                        key
                    ]["PM"] += item[
                        "count"
                    ]

                elif typ == "CORRECTIVE":

                    months_dict[
                        key
                    ]["CM"] += item[
                        "count"
                    ]

                elif typ == "EMERGENCY":

                    months_dict[
                        key
                    ]["EM"] += item[
                        "count"
                    ]

            sorted_months = sorted(
                months_dict.keys()
            )

            pm_counts = [
                months_dict[m]["PM"]
                for m in sorted_months
            ]

            cm_counts = [
                months_dict[m]["CM"]
                for m in sorted_months
            ]

            em_counts = [
                months_dict[m]["EM"]
                for m in sorted_months
            ]

            fig1, ax1 = (
                self._fig(
                    10,
                    4,
                )
            )

            x = np.arange(
                len(
                    sorted_months
                )
            )

            width = 0.25

            ax1.bar(
                x - width,
                pm_counts,
                width,
                label="PM",
                color=ACCENT_TEAL,
                edgecolor="white",
            )

            ax1.bar(
                x,
                cm_counts,
                width,
                label="CM",
                color=ACCENT_ROSE,
                edgecolor="white",
            )

            ax1.bar(
                x + width,
                em_counts,
                width,
                label="EM",
                color=ACCENT_AMBER,
                edgecolor="white",
            )

            ax1.set_xticks(
                x
            )

            ax1.set_xticklabels(
                sorted_months,
                rotation=35,
                ha="right",
                fontsize=8,
            )

            ax1.set_ylabel(
                "Count",
                fontsize=8,
                color=TEXT_LIGHT,
            )

            ax1.set_title(
                "Monthly PM / CM / EM Comparison",
                fontsize=11,
                color=NAVY,
                pad=8,
            )

            ax1.legend(
                fontsize=8
            )

            ax1.yaxis.grid(
                True,
                color=CARD_BORDER,
                linewidth=0.8,
            )

            ax1.set_axisbelow(
                True
            )

            ax1.spines[
                "top"
            ].set_visible(
                False
            )

            ax1.spines[
                "right"
            ].set_visible(
                False
            )

            ax1.tick_params(
                colors=TEXT_LIGHT,
                labelsize=8,
            )

            fig1.tight_layout(
                pad=1
            )

            self._embed_chart(
                fig1,
                trend_card,
            )

        else:

            tk.Label(
                trend_card,
                text=(
                    "داده‌ای برای نمایش ماهانه "
                    "وجود ندارد."
                ),
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=TEXT_LIGHT,
            ).pack(
                pady=20
            )

        comp_card = self._card(
            parent
        )

        self._card_header(
            comp_card,
            "انطباق برنامه (به موقع / دیرکرد)",
            "🎯",
        )

        fig2, ax2 = (
            self._fig(
                7,
                3.5,
            )
        )

        if (
            compliance.get(
                "on_time",
                0,
            ) > 0
            or compliance.get(
                "late",
                0,
            ) > 0
        ):

            ax2.pie(
                [
                    compliance[
                        "on_time"
                    ],
                    compliance[
                        "late"
                    ],
                ],
                labels=[
                    "On Time",
                    "Late",
                ],
                autopct="%1.1f%%",
                colors=[
                    SUCCESS,
                    ACCENT_ROSE,
                ],
                startangle=90,
                wedgeprops=dict(
                    linewidth=1.5,
                    edgecolor="white",
                ),
            )

            ax2.set_title(
                (
                    "Schedule Compliance: "
                    f"{compliance.get('compliance_rate', 0):.1f}%"
                ),
                fontsize=11,
                color=NAVY,
            )

        else:

            ax2.text(
                0.5,
                0.5,
                "No Data",
                ha="center",
                va="center",
                color=TEXT_LIGHT,
            )

            ax2.set_axis_off()

        fig2.tight_layout(
            pad=0.5
        )

        self._embed_chart(
            fig2,
            comp_card,
        )

        if risk_data:

            risk_card = self._card(
                parent
            )

            self._card_header(
                risk_card,
                "تجهیزات با ریسک بالا",
                "⚠️",
            )

            rf = tk.Frame(
                risk_card,
                bg=CARD_BG,
            )

            rf.pack(
                fill=tk.X,
                padx=10,
                pady=8,
            )

            risk_tree = self._styled_tree(
                rf,
                (
                    "name",
                    "risk",
                    "level",
                    "failures",
                    "downtime",
                ),
                [
                    (
                        "name",
                        "تجهیز",
                        130,
                    ),
                    (
                        "risk",
                        "امتیاز ریسک",
                        110,
                    ),
                    (
                        "level",
                        "سطح ریسک",
                        90,
                    ),
                    (
                        "failures",
                        "تعداد خرابی",
                        100,
                    ),
                    (
                        "downtime",
                        "متوسط توقف (h)",
                        120,
                    ),
                ],
                height=8,
            )

            risk_tree.tag_configure(
                "high",
                foreground=ACCENT_ROSE,
            )

            risk_tree.tag_configure(
                "medium",
                foreground=ACCENT_AMBER,
            )

            risk_tree.tag_configure(
                "low",
                foreground=SUCCESS,
            )

            for item in (
                risk_data[:10]
            ):

                score = item.get(
                    "risk_score",
                    0,
                )

                level = item.get(
                    "risk_level",
                    "",
                )

                tag = (
                    "high"
                    if score >= 70
                    or level == "HIGH"
                    else
                    "medium"
                    if score >= 40
                    or level == "MEDIUM"
                    else
                    "low"
                )

                lv = (
                    "بالا"
                    if tag == "high"
                    else
                    "متوسط"
                    if tag == "medium"
                    else
                    "پایین"
                )

                risk_tree.insert(
                    "",
                    tk.END,
                    tags=(tag,),
                    values=(
                        item.get(
                            "equipment_name",
                            "—",
                        ),
                        f"{score:.1f}",
                        lv,
                        item.get(
                            "failure_count",
                            0,
                        ),
                        f"{item.get('avg_downtime_hours', 0):.1f}",
                    ),
                )

    # =========================================================================
    # COST
    # =========================================================================

    def _render_cost(
        self,
        parent,
        cost_data,
    ):

        cost_card = self._card(
            parent
        )

        self._card_header(
            cost_card,
            "توزیع هزینه‌ها",
            "💰",
        )

        if (
            cost_data.get(
                "breakdown"
            )
            and len(
                cost_data[
                    "breakdown"
                ]
            ) > 0
        ):

            fig, ax = (
                self._fig(
                    8,
                    5,
                )
            )

            labels = [
                d["type"]
                for d in cost_data[
                    "breakdown"
                ]
            ]

            sizes = [
                d["total_cost"]
                for d in cost_data[
                    "breakdown"
                ]
            ]

            palette = [
                ACCENT_BLUE,
                ACCENT_TEAL,
                ACCENT_AMBER,
                ACCENT_PURP,
                ACCENT_ROSE,
            ]

            ax.pie(
                sizes,
                labels=labels,
                autopct="%1.1f%%",
                startangle=90,
                colors=palette[
                    :len(labels)
                ],
                wedgeprops=dict(
                    linewidth=1.5,
                    edgecolor="white",
                ),
            )

            total = cost_data.get(
                "total_cost",
                0,
            )

            ax.set_title(
                (
                    "Cost Distribution "
                    f"(Total: {total:,.0f} Rials)"
                ),
                fontsize=11,
                color=NAVY,
                pad=10,
            )

            fig.tight_layout(
                pad=0.5
            )

            self._embed_chart(
                fig,
                cost_card,
            )

        else:

            tk.Label(
                cost_card,
                text=(
                    "داده‌ای برای نمایش وجود ندارد"
                ),
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=TEXT_LIGHT,
            ).pack(
                pady=40
            )

    # =========================================================================
    # PERSONNEL
    # =========================================================================

    def _render_tech(
        self,
        parent,
        personnel_data,
    ):
        """
        Render actual maintenance Personnel performance.

        This replaces the old User-technician report.
        """

        pc = self._card(
            parent
        )

        self._card_header(
            pc,
            "عملکرد پرسنل انجام‌دهنده",
            "👷",
        )

        info = tk.Frame(
            pc,
            bg=CARD_BG,
        )

        info.pack(
            fill=tk.X,
            padx=12,
            pady=8,
        )

        tk.Label(
            info,
            text=(
                "این گزارش بر اساس پرسنلی است که "
                "در زمان درخواست اتمام دستورکار انتخاب شده‌اند."
            ),
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            anchor="e",
            justify="right",
        ).pack(
            anchor="e"
        )

        tf = tk.Frame(
            pc,
            bg=CARD_BG,
        )

        tf.pack(
            fill=tk.BOTH,
            expand=True,
            padx=10,
            pady=10,
        )

        if not personnel_data:

            tk.Label(
                tf,
                text=(
                    "داده‌ای برای نمایش وجود ندارد.\n\n"
                    "برای ثبت عملکرد پرسنل، ابتدا "
                    "دستورکار باید با انتخاب دپارتمان ایجاد "
                    "و سپس هنگام درخواست اتمام، پرسنل همان "
                    "دپارتمان انتخاب شود."
                ),
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=TEXT_LIGHT,
                justify="center",
            ).pack(
                pady=40
            )

            self.tech_tree = None

            return

        columns = (
            "name",
            "department",
            "total",
            "completed",
            "rate",
            "avg_time",
        )

        col_defs = [
            (
                "name",
                "پرسنل",
                240,
            ),
            (
                "department",
                "دپارتمان",
                170,
            ),
            (
                "total",
                "کل وظایف",
                100,
            ),
            (
                "completed",
                "تکمیل شده",
                110,
            ),
            (
                "rate",
                "نرخ تکمیل٪",
                120,
            ),
            (
                "avg_time",
                "میانگین زمان (h)",
                150,
            ),
        ]

        self.tech_tree = (
            self._styled_tree(
                tf,
                columns,
                col_defs,
                height=15,
            )
        )

        self._personnel_performance_data = (
            personnel_data
        )

        for i, item in enumerate(
            personnel_data
        ):

            tag = (
                "even"
                if i % 2 == 0
                else "odd"
            )

            self.tech_tree.insert(
                "",
                tk.END,
                tags=(tag,),
                values=(
                    item.get(
                        "personnel_name",
                        "—",
                    ),
                    item.get(
                        "department_name",
                        "—",
                    ),
                    item.get(
                        "total_tasks",
                        0,
                    ),
                    item.get(
                        "completed_tasks",
                        0,
                    ),
                    (
                        f"{item.get('completion_rate', 0):.1f}"
                    ),
                    (
                        f"{item.get('avg_completion_hours', 0):.1f}"
                    ),
                ),
            )

    # =========================================================================
    # FAILURE
    # =========================================================================

    def _render_failure(
        self,
        parent,
        failures,
    ):

        fc = self._card(
            parent
        )

        self._card_header(
            fc,
            "پرتکرارترین خرابی‌ها",
            "⚠️",
        )

        ff = tk.Frame(
            fc,
            bg=CARD_BG,
        )

        ff.pack(
            fill=tk.BOTH,
            expand=True,
            padx=10,
            pady=10,
        )

        if not failures:

            tk.Label(
                ff,
                text="هیچ خرابی ثبت نشده است.",
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=TEXT_LIGHT,
            ).pack(
                pady=40
            )

            return

        tree = self._styled_tree(
            ff,
            (
                "description",
                "count",
            ),
            [
                (
                    "description",
                    "توضیحات خرابی",
                    600,
                ),
                (
                    "count",
                    "تعداد تکرار",
                    100,
                ),
            ],
            height=12,
        )

        for i, item in enumerate(
            failures
        ):

            tag = (
                "even"
                if i % 2 == 0
                else "odd"
            )

            tree.insert(
                "",
                tk.END,
                tags=(tag,),
                values=(
                    item.get(
                        "description",
                        "—",
                    ),
                    item.get(
                        "count",
                        0,
                    ),
                ),
            )

    # =========================================================================
    # REFRESH ALL
    # =========================================================================

    def _refresh_all(
        self
    ):

        if self._loading:
            return

        start = self.start_date.get_date()
        end = self.end_date.get_date()

        if start and end and start > end:
            messagebox.showwarning(
                "بازه تاریخ",
                "«از تاریخ» نمی‌تواند بعد از «تا تاریخ» باشد.",
                parent=self,
            )
            return

        self._loading = True

        for tag in (
            self._tabs_loaded
        ):

            self._tabs_loaded[
                tag
            ] = False

        for tag in [
            "overview",
            "scorecard",
            "equipment",
            "kpi",
            "cost",
            "tech",
            "failure",
        ]:

            frame = getattr(
                self,
                f"{tag}_frame",
                None,
            )

            if frame:

                export_toolbar = getattr(
                    frame,
                    "_report_export_toolbar",
                    None,
                )

                for child in frame.winfo_children():
                    if child == export_toolbar:
                        continue
                    child.destroy()

                loading = tk.Label(
                    frame,
                    text="⏳ در حال بارگذاری...",
                    font=FONT_HEADING,
                    bg=SECTION_BG,
                    fg=TEXT_LIGHT,
                )

                loading.pack(
                    expand=True
                )

                frame._loading_label = (
                    loading
                )

        current = (
            self.notebook.select()
        )

        if current:

            frame = (
                self.notebook
                .nametowidget(
                    current
                )
            )

            tag = getattr(
                frame,
                "_tab_tag",
                "overview",
            )

            self._load_tab_data(
                tag
            )

        else:

            self._load_tab_data(
                "overview"
            )

        self._loading = False

    # =========================================================================
    # EQUIPMENT DETAIL
    # =========================================================================

    def _open_equipment_detail(
        self,
        event,
    ):

        selection = (
            self.equipment_tree
            .selection()
        )

        if not selection:
            return

        try:

            equipment_id = int(
                self.equipment_tree
                .item(
                    selection[0]
                )["values"][0]
            )

        except (
            TypeError,
            ValueError,
            IndexError,
        ):

            messagebox.showerror(
                "خطا",
                "شناسه تجهیز نامعتبر است.",
                parent=self,
            )

            return

        eq_data = (
            self.eq_repo
            .get_equipment_by_id(
                equipment_id
            )
        )

        if not eq_data:

            messagebox.showerror(
                "خطا",
                "تجهیز یافت نشد.",
                parent=self,
            )

            return

        dialog = tk.Toplevel(
            self
        )

        dialog.title(
            (
                "گزارش تفصیلی — "
                f"{eq_data['name']}"
            )
        )

        screen_w = (
            dialog.winfo_screenwidth()
        )

        screen_h = (
            dialog.winfo_screenheight()
        )

        width = min(
            1100,
            max(
                760,
                int(
                    screen_w * 0.80
                ),
            ),
        )

        height = min(
            800,
            max(
                600,
                int(
                    screen_h * 0.82
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

        dialog.geometry(
            f"{width}x{height}+{x}+{y}"
        )

        dialog.configure(
            bg=SECTION_BG
        )

        dialog.transient(
            self
        )

        dialog.grab_set()

        dh = tk.Frame(
            dialog,
            bg=NAVY,
            height=56,
        )

        dh.pack(
            fill=tk.X
        )

        dh.pack_propagate(
            False
        )

        tk.Label(
            dh,
            text=(
                f"⚙️  {eq_data['name']}"
            ),
            font=FONT_TITLE,
            bg=NAVY,
            fg=WHITE,
        ).pack(
            side=tk.RIGHT,
            padx=20,
            pady=12,
        )

        notebook = ttk.Notebook(
            dialog,
            style="Report.TNotebook",
        )

        notebook.pack(
            fill=tk.BOTH,
            expand=True,
            padx=10,
            pady=10,
        )

        # ------------------------------------------------------------------
        # Main information
        # ------------------------------------------------------------------

        main_frame = tk.Frame(
            notebook,
            bg=SECTION_BG,
        )

        notebook.add(
            main_frame,
            text="اطلاعات و عملکرد",
        )

        canvas = tk.Canvas(
            main_frame,
            bg=SECTION_BG,
            highlightthickness=0,
        )

        vsb = ttk.Scrollbar(
            main_frame,
            orient="vertical",
            command=canvas.yview,
        )

        scrollable = tk.Frame(
            canvas,
            bg=SECTION_BG,
        )

        scrollable.bind(
            "<Configure>",
            lambda _event:
            canvas.configure(
                scrollregion=(
                    canvas.bbox("all")
                )
            ),
        )

        window_id = (
            canvas.create_window(
                (
                    0,
                    0,
                ),
                window=scrollable,
                anchor="nw",
            )
        )

        canvas.configure(
            yscrollcommand=vsb.set
        )

        canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )

        vsb.pack(
            side="right",
            fill="y",
        )

        canvas.bind(
            "<Configure>",
            lambda event:
            canvas.itemconfigure(
                window_id,
                width=event.width,
            ),
        )

        canvas.bind(
            "<MouseWheel>",
            lambda event:
            canvas.yview_scroll(
                -1
                * (
                    event.delta
                    // 120
                ),
                "units",
            ),
        )

        info_card = self._card(
            scrollable
        )

        self._card_header(
            info_card,
            "مشخصات اصلی",
            "📋",
        )

        info_grid = tk.Frame(
            info_card,
            bg=CARD_BG,
        )

        info_grid.pack(
            fill=tk.X,
            padx=14,
            pady=10,
        )

        inst_date_raw = eq_data.get(
            "installation_date"
        )

        if inst_date_raw:

            try:

                if isinstance(
                    inst_date_raw,
                    str,
                ):

                    dt = datetime.strptime(
                        inst_date_raw,
                        "%Y-%m-%d",
                    )

                else:

                    dt = inst_date_raw

                inst_date = (
                    to_jalali_date_str(
                        dt
                    )
                )

            except Exception:

                inst_date = "—"

        else:

            inst_date = "—"

        fields = [
            (
                "کد تجهیز:",
                eq_data.get(
                    "code",
                    "—",
                ),
            ),
            (
                "نام تجهیز:",
                eq_data.get(
                    "name",
                    "—",
                ),
            ),
            (
                "دسته‌بندی:",
                eq_data.get(
                    "category",
                    "—",
                ),
            ),
            (
                "سازنده:",
                eq_data.get(
                    "manufacturer",
                    "—",
                ),
            ),
            (
                "مدل:",
                eq_data.get(
                    "model",
                    "—",
                ),
            ),
            (
                "شماره سریال:",
                eq_data.get(
                    "serial_number",
                    "—",
                ),
            ),
            (
                "موقعیت:",
                eq_data.get(
                    "location",
                    "—",
                ),
            ),
            (
                "تاریخ نصب:",
                inst_date,
            ),
            (
                "وضعیت:",
                STATUS_FA.get(
                    eq_data.get(
                        "status",
                        "",
                    ),
                    eq_data.get(
                        "status",
                        "—",
                    ),
                ),
            ),
        ]

        for i, (
            label,
            value,
        ) in enumerate(
            fields
        ):

            r, c = divmod(
                i,
                2,
            )

            tk.Label(
                info_grid,
                text=label,
                font=(
                    "Tahoma",
                    9,
                    "bold",
                ),
                bg=CARD_BG,
                fg=TEXT_LIGHT,
            ).grid(
                row=r,
                column=c * 2,
                sticky="e",
                padx=(
                    10,
                    4,
                ),
                pady=4,
            )

            tk.Label(
                info_grid,
                text=value,
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=TEXT_DARK,
            ).grid(
                row=r,
                column=c * 2 + 1,
                sticky="w",
                padx=(
                    0,
                    20,
                ),
                pady=4,
            )

        for col_w in [
            0,
            1,
            2,
            3,
        ]:

            info_grid.columnconfigure(
                col_w,
                weight=1,
            )

        specs_card = self._card(
            scrollable
        )

        self._card_header(
            specs_card,
            "مشخصات فنی",
            "🔧",
        )

        tk.Label(
            specs_card,
            text=(
                eq_data.get(
                    "specifications",
                    "—",
                )
            ),
            wraplength=900,
            justify="right",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).pack(
            anchor="w",
            padx=14,
            pady=10,
        )

        notes_card = self._card(
            scrollable
        )

        self._card_header(
            notes_card,
            "یادداشت‌ها",
            "📝",
        )

        tk.Label(
            notes_card,
            text=(
                eq_data.get(
                    "notes",
                    "—",
                )
            ),
            wraplength=900,
            justify="right",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).pack(
            anchor="w",
            padx=14,
            pady=10,
        )

        # ------------------------------------------------------------------
        # Report KPI
        # ------------------------------------------------------------------

        start = (
            self.start_date
            .get_date()
        )

        end = (
            self.end_date
            .get_date()
        )

        report = (
            self.report_repo
            .get_equipment_report(
                equipment_id,
                start,
                end,
            )
        )

        if report:

            kpi_card = self._card(
                scrollable
            )

            self._card_header(
                kpi_card,
                "شاخص‌های عملکردی",
                "📊",
            )

            kpi_grid = tk.Frame(
                kpi_card,
                bg=CARD_BG,
            )

            kpi_grid.pack(
                fill=tk.X,
                padx=14,
                pady=10,
            )

            total_cost = 0.0

            wo_repo = (
                WorkOrderRepository(
                    SessionLocal
                )
            )

            sp_repo = (
                SparePartsRepository(
                    SessionLocal
                )
            )

            for wo in (
                wo_repo.get_all()
            ):

                if (
                    wo.equipment_id
                    != equipment_id
                ):

                    continue

                if (
                    start
                    and wo.created_at
                    and wo.created_at.date()
                    < start
                ):

                    continue

                if (
                    end
                    and wo.created_at
                    and wo.created_at.date()
                    > end
                ):

                    continue

                if wo.parts_used:

                    try:

                        for item in (
                            json.loads(
                                wo.parts_used
                            )
                        ):

                            part = (
                                sp_repo.get_by_id(
                                    item.get(
                                        "part_id"
                                    )
                                )
                            )

                            if part:

                                total_cost += (
                                    float(
                                        part.unit_price
                                        or 0
                                    )
                                    * float(
                                        item.get(
                                            "quantity",
                                            0,
                                        )
                                        or 0
                                    )
                                )

                    except Exception:

                        pass

                if (
                    wo.start_time
                    and wo.end_time
                ):

                    total_cost += (
                        (
                            wo.end_time
                            - wo.start_time
                        ).total_seconds()
                        / 3600
                        * 50
                    )

                total_cost += float(
                    wo.manual_cost
                    or 0
                )

            kpis = [
                (
                    "کل دستورات کار:",
                    report.get(
                        "total_work_orders",
                        0,
                    ),
                ),
                (
                    "تکمیل شده:",
                    report.get(
                        "completed_work_orders",
                        0,
                    ),
                ),
                (
                    "PM:",
                    report.get(
                        "pm_work_orders",
                        0,
                    ),
                ),
                (
                    "CM:",
                    report.get(
                        "cm_work_orders",
                        0,
                    ),
                ),
                (
                    "میانگین زمان تعمیر (h):",
                    f"{report.get('avg_repair_time_hours', 0):.2f}",
                ),
                (
                    "کل زمان توقف (h):",
                    f"{report.get('total_downtime_hours', 0):.2f}",
                ),
                (
                    "انطباق PM٪:",
                    f"{report.get('pm_compliance_rate', 0):.1f}",
                ),
                (
                    "MTBF (h):",
                    f"{report.get('mtbf_hours', 0):.2f}",
                ),
                (
                    "MTTR (h):",
                    f"{report.get('mttr_hours', 0):.2f}",
                ),
                (
                    "تعداد خرابی:",
                    report.get(
                        "failure_count",
                        0,
                    ),
                ),
                (
                    "هزینه کل (ریال):",
                    f"{total_cost:,.0f}",
                ),
            ]

            for i, (
                label,
                value,
            ) in enumerate(
                kpis
            ):

                r, c = divmod(
                    i,
                    2,
                )

                tk.Label(
                    kpi_grid,
                    text=label,
                    font=(
                        "Tahoma",
                        9,
                        "bold",
                    ),
                    bg=CARD_BG,
                    fg=TEXT_LIGHT,
                ).grid(
                    row=r,
                    column=c * 2,
                    sticky="e",
                    padx=(
                        10,
                        4,
                    ),
                    pady=4,
                )

                tk.Label(
                    kpi_grid,
                    text=str(value),
                    font=FONT_NORMAL,
                    bg=CARD_BG,
                    fg=TEXT_DARK,
                ).grid(
                    row=r,
                    column=c * 2 + 1,
                    sticky="w",
                    padx=(
                        0,
                        20,
                    ),
                    pady=4,
                )

            for col_w in [
                0,
                1,
                2,
                3,
            ]:

                kpi_grid.columnconfigure(
                    col_w,
                    weight=1,
                )

        # ------------------------------------------------------------------
        # Charts
        # ------------------------------------------------------------------

        chart_frame = tk.Frame(
            notebook,
            bg=SECTION_BG,
        )

        notebook.add(
            chart_frame,
            text="نمودارها",
        )

        fig = Figure(
            figsize=(
                12,
                5,
            ),
            dpi=88,
            facecolor=SECTION_BG,
        )

        ax1 = fig.add_subplot(
            121
        )

        ax1.set_facecolor(
            CARD_BG
        )

        if report:

            pm = report.get(
                "pm_work_orders",
                0,
            )

            cm = report.get(
                "cm_work_orders",
                0,
            )

            em_count = 0

            session = (
                SessionLocal()
            )

            try:

                q = (
                    session.query(
                        func.count(
                            WorkOrder.id
                        )
                    )
                    .filter(
                        WorkOrder.equipment_id
                        == equipment_id,

                        WorkOrder.type
                        == WorkOrderType.EMERGENCY,

                    )
                )

                if start:

                    q = q.filter(
                        WorkOrder.created_at
                        >= start
                    )

                if end:

                    q = q.filter(
                        WorkOrder.created_at
                        < (
                            end
                            + timedelta(
                                days=1
                            )
                        )
                    )

                em_count = (
                    q.scalar()
                    or 0
                )

            finally:

                session.close()

            if (
                pm
                + cm
                + em_count
                > 0
            ):

                ax1.pie(
                    [
                        pm,
                        cm,
                        em_count,
                    ],
                    labels=[
                        "PM",
                        "CM",
                        "EM",
                    ],
                    autopct="%1.1f%%",
                    colors=[
                        SUCCESS,
                        ACCENT_ROSE,
                        ACCENT_AMBER,
                    ],
                    wedgeprops=dict(
                        linewidth=1.5,
                        edgecolor="white",
                    ),
                )

                ax1.set_title(
                    "Work Order Distribution",
                    color=NAVY,
                    fontsize=10,
                )

            else:

                ax1.text(
                    0.5,
                    0.5,
                    "No Data",
                    ha="center",
                    va="center",
                    color=TEXT_LIGHT,
                )

                ax1.set_axis_off()

        else:

            ax1.text(
                0.5,
                0.5,
                "No Data",
                ha="center",
                va="center",
                color=TEXT_LIGHT,
            )

        ax2 = fig.add_subplot(
            122
        )

        ax2.set_facecolor(
            CARD_BG
        )

        if report:

            metrics = [
                "MTBF",
                "MTTR",
                "Downtime",
            ]

            values = [
                report.get(
                    "mtbf_hours",
                    0,
                ),
                report.get(
                    "mttr_hours",
                    0,
                ),
                report.get(
                    "total_downtime_hours",
                    0,
                ),
            ]

            bars = ax2.bar(
                metrics,
                values,
                color=[
                    NAVY,
                    ACCENT_AMBER,
                    ACCENT_ROSE,
                ],
                width=0.5,
                edgecolor="white",
            )

            for bar, val in zip(
                bars,
                values,
            ):

                if val > 0:

                    ax2.text(
                        bar.get_x()
                        + bar.get_width()
                        / 2,
                        bar.get_height()
                        + 0.05,
                        f"{val:.1f}",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                        color=TEXT_DARK,
                    )

            ax2.set_ylabel(
                "Hours",
                fontsize=8,
                color=TEXT_LIGHT,
            )

            ax2.set_title(
                "Key Metrics (Hours)",
                color=NAVY,
                fontsize=10,
            )

            ax2.spines[
                "top"
            ].set_visible(
                False
            )

            ax2.spines[
                "right"
            ].set_visible(
                False
            )

        else:

            ax2.text(
                0.5,
                0.5,
                "No Data",
                ha="center",
                va="center",
                color=TEXT_LIGHT,
            )

        fig.tight_layout(
            pad=1.5
        )

        self._embed_chart(
            fig,
            chart_frame,
        )

        # ------------------------------------------------------------------
        # Work Order notes
        # ------------------------------------------------------------------

        notes_tab = tk.Frame(
            notebook,
            bg=SECTION_BG,
        )

        notebook.add(
            notes_tab,
            text="یادداشت دستورکارها",
        )

        notes_card = self._card(
            notes_tab
        )

        self._card_header(
            notes_card,
            "یادداشت دستورکارها",
            "📝",
        )

        wo_tree_frame = tk.Frame(
            notes_card,
            bg=CARD_BG,
        )

        wo_tree_frame.pack(
            fill=tk.BOTH,
            expand=True,
            padx=10,
            pady=10,
        )

        wo_cols = (
            "id",
            "title",
            "department",
            "type",
            "status",
            "created_date",
            "created_time",
            "personnel",
            "operator_notes",
            "technician_notes",
            "part_notes",
        )

        wo_col_defs = [
            (
                "id",
                "شناسه",
                60,
            ),
            (
                "title",
                "عنوان",
                150,
            ),
            (
                "department",
                "دپارتمان",
                130,
            ),
            (
                "type",
                "نوع",
                80,
            ),
            (
                "status",
                "وضعیت",
                90,
            ),
            (
                "created_date",
                "تاریخ",
                80,
            ),
            (
                "created_time",
                "زمان",
                60,
            ),
            (
                "personnel",
                "پرسنل انجام‌دهنده",
                180,
            ),
            (
                "operator_notes",
                "یادداشت اپراتور",
                220,
            ),
            (
                "technician_notes",
                "توضیحات تعمیر",
                220,
            ),
            (
                "part_notes",
                "قطعات مصرفی",
                180,
            ),
        ]

        wo_tree = (
            self._styled_tree(
                wo_tree_frame,
                wo_cols,
                wo_col_defs,
                height=20,
            )
        )

        wo_tree.bind(
            "<Double-1>",
            lambda _event:
            self._show_work_order_detail(
                wo_tree
            ),
        )

        wo_repo = (
            WorkOrderRepository(
                SessionLocal
            )
        )

        try:

            equipment_work_orders = [
                wo
                for wo in wo_repo.get_all()
                if wo.equipment_id
                == equipment_id
            ]

        except Exception:

            equipment_work_orders = []

        for i, wo in enumerate(
            equipment_work_orders
        ):

            tag = (
                "even"
                if i % 2 == 0
                else "odd"
            )

            if (
                hasattr(
                    wo,
                    "created_at",
                )
                and wo.created_at
            ):

                date_str = (
                    to_jalali_date_str(
                        wo.created_at
                    )
                )

                time_str = (
                    wo.created_at
                    .strftime(
                        "%H:%M:%S"
                    )
                )

            else:

                date_str = "—"
                time_str = "—"

            department_name = (
                getattr(
                    getattr(
                        wo,
                        "department",
                        None,
                    ),
                    "name",
                    None,
                )
                or "—"
            )

            completers = getattr(
                wo,
                "completers",
                []
            ) or []

            personnel_names = []

            for person in (
                completers
            ):

                person_code = (
                    getattr(
                        person,
                        "personnel_code",
                        "",
                    )
                    or ""
                )

                person_name = (
                    getattr(
                        person,
                        "full_name",
                        "",
                    )
                    or ""
                )

                if (
                    person_code
                    and person_name
                ):

                    personnel_names.append(
                        (
                            f"{person_code} - "
                            f"{person_name}"
                        )
                    )

                elif person_name:

                    personnel_names.append(
                        person_name
                    )

            personnel_text = (
                "، ".join(
                    personnel_names
                )
                if personnel_names
                else "—"
            )

            wo_tree.insert(
                "",
                tk.END,
                tags=(tag,),
                values=(
                    wo.id,
                    wo.title,
                    department_name,
                    WO_TYPE_FA.get(
                        getattr(
                            wo.type,
                            "name",
                            "",
                        ),
                        getattr(
                            wo.type,
                            "name",
                            "—",
                        ),
                    ),
                    WO_STATUS_FA.get(
                        getattr(
                            wo.status,
                            "name",
                            "",
                        ),
                        getattr(
                            wo.status,
                            "name",
                            "—",
                        ),
                    ),
                    date_str,
                    time_str,
                    personnel_text,
                    wo.operator_notes
                    or "—",
                    wo.description
                    or "—",
                    wo.parts_used
                    or "—",
                )
            )

        tk.Button(
            dialog,
            text="✕  بستن",
            font=FONT_NORMAL,
            bg=ACCENT_ROSE,
            fg=WHITE,
            relief="flat",
            cursor="hand2",
            padx=20,
            pady=8,
            command=dialog.destroy,
        ).pack(
            pady=10
        )

    # =========================================================================
    # WORK ORDER DETAIL
    # =========================================================================

    def _show_work_order_detail(
        self,
        tree,
    ):

        selection = (
            tree.selection()
        )

        if not selection:
            return

        try:

            wo_id = int(
                tree.item(
                    selection[0]
                )["values"][0]
            )

        except (
            TypeError,
            ValueError,
            IndexError,
        ):

            return

        wo_repo = (
            WorkOrderRepository(
                SessionLocal
            )
        )

        wo = (
            wo_repo.get_by_id(
                wo_id
            )
        )

        if not wo:

            messagebox.showerror(
                "خطا",
                "دستور کار یافت نشد.",
                parent=self,
            )

            return

        detail = tk.Toplevel(
            self
        )

        detail.title(
            f"دستور کار #{wo.id}"
        )

        screen_w = (
            detail.winfo_screenwidth()
        )

        screen_h = (
            detail.winfo_screenheight()
        )

        width = min(
            850,
            max(
                700,
                int(
                    screen_w * 0.65
                ),
            ),
        )

        height = min(
            720,
            max(
                560,
                int(
                    screen_h * 0.75
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

        detail.geometry(
            f"{width}x{height}+{x}+{y}"
        )

        detail.configure(
            bg=SECTION_BG
        )

        detail.transient(
            self
        )

        detail.grab_set()

        dh = tk.Frame(
            detail,
            bg=NAVY,
            height=52,
        )

        dh.pack(
            fill=tk.X
        )

        dh.pack_propagate(
            False
        )

        tk.Label(
            dh,
            text=(
                f"📝  WO#{wo.id} — "
                f"{wo.title}"
            ),
            font=FONT_HEADING,
            bg=NAVY,
            fg=WHITE,
        ).pack(
            side=tk.RIGHT,
            padx=20,
            pady=12,
        )

        outer = tk.Frame(
            detail,
            bg=SECTION_BG,
        )

        outer.pack(
            fill=tk.BOTH,
            expand=True,
            padx=12,
            pady=10,
        )

        canvas = tk.Canvas(
            outer,
            bg=SECTION_BG,
            highlightthickness=0,
        )

        vsb = ttk.Scrollbar(
            outer,
            orient="vertical",
            command=canvas.yview,
        )

        scrollable = tk.Frame(
            canvas,
            bg=SECTION_BG,
        )

        scroll_window = (
            canvas.create_window(
                (
                    0,
                    0,
                ),
                window=scrollable,
                anchor="nw",
            )
        )

        scrollable.bind(
            "<Configure>",
            lambda _event:
            canvas.configure(
                scrollregion=(
                    canvas.bbox("all")
                )
            ),
        )

        canvas.bind(
            "<Configure>",
            lambda event:
            canvas.itemconfigure(
                scroll_window,
                width=event.width,
            ),
        )

        canvas.configure(
            yscrollcommand=vsb.set
        )

        canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )

        vsb.pack(
            side="right",
            fill="y",
        )

        canvas.bind(
            "<MouseWheel>",
            lambda event:
            canvas.yview_scroll(
                -1
                * (
                    event.delta
                    // 120
                ),
                "units",
            ),
        )

        def add_row(
            parent,
            text,
            value,
            row,
        ):

            tk.Label(
                parent,
                text=text,
                font=(
                    "Tahoma",
                    9,
                    "bold",
                ),
                bg=CARD_BG,
                fg=TEXT_LIGHT,
            ).grid(
                row=row,
                column=0,
                sticky="ne",
                padx=10,
                pady=5,
            )

            tk.Label(
                parent,
                text=str(value),
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=TEXT_DARK,
                wraplength=550,
                justify="right",
            ).grid(
                row=row,
                column=1,
                sticky="nw",
                padx=10,
                pady=5,
            )

            return row + 1

        info_card = self._card(
            scrollable
        )

        self._card_header(
            info_card,
            "اطلاعات اصلی",
            "📋",
        )

        grid = tk.Frame(
            info_card,
            bg=CARD_BG,
        )

        grid.pack(
            fill=tk.X,
            padx=10,
            pady=8,
        )

        r = 0

        r = add_row(
            grid,
            "شناسه:",
            wo.id,
            r,
        )

        r = add_row(
            grid,
            "عنوان:",
            wo.title
            or "—",
            r,
        )

        r = add_row(
            grid,
            "تجهیز:",
            (
                wo.equipment.name
                if wo.equipment
                else "—"
            ),
            r,
        )

        r = add_row(
            grid,
            "دپارتمان:",
            (
                wo.department.name
                if wo.department
                else "—"
            ),
            r,
        )

        r = add_row(
            grid,
            "نوع:",
            WO_TYPE_FA.get(
                getattr(
                    wo.type,
                    "name",
                    "",
                ),
                getattr(
                    wo.type,
                    "name",
                    "—",
                ),
            ),
            r,
        )

        r = add_row(
            grid,
            "اولویت:",
            getattr(
                wo.priority,
                "name",
                "—",
            ),
            r,
        )

        r = add_row(
            grid,
            "وضعیت:",
            WO_STATUS_FA.get(
                getattr(
                    wo.status,
                    "name",
                    "",
                ),
                getattr(
                    wo.status,
                    "name",
                    "—",
                ),
            ),
            r,
        )

        scheduled_text = "—"

        if wo.scheduled_date:

            try:

                scheduled_text = (
                    to_jalali_datetime_str(
                        wo.scheduled_date
                    )
                )

            except Exception:

                scheduled_text = str(
                    wo.scheduled_date
                )

        r = add_row(
            grid,
            "تاریخ برنامه:",
            scheduled_text,
            r,
        )

        r = add_row(
            grid,
            "شروع:",
            to_jalali_datetime_str(
                wo.start_time
            ),
            r,
        )

        r = add_row(
            grid,
            "پایان:",
            to_jalali_datetime_str(
                wo.end_time
            ),
            r,
        )

        # ------------------------------------------------------------------
        # Personnel
        # ------------------------------------------------------------------

        completers = getattr(
            wo,
            "completers",
            []
        ) or []

        personnel_names = []

        for person in completers:

            person_code = (
                getattr(
                    person,
                    "personnel_code",
                    "",
                )
                or ""
            )

            person_name = (
                getattr(
                    person,
                    "full_name",
                    "",
                )
                or ""
            )

            if (
                person_code
                and person_name
            ):

                personnel_names.append(
                    f"{person_code} - {person_name}"
                )

            elif person_name:

                personnel_names.append(
                    person_name
                )

        personnel_text = (
            "، ".join(
                personnel_names
            )
            if personnel_names
            else "انتخاب نشده"
        )

        r = add_row(
            grid,
            "پرسنل انجام‌دهنده:",
            personnel_text,
            r,
        )

        # ------------------------------------------------------------------
        # Keep legacy User technician visible only as historical/application
        # account information.
        # ------------------------------------------------------------------

        legacy_technician = (
            getattr(
                getattr(
                    wo,
                    "technician",
                    None,
                ),
                "full_name",
                None,
            )
        )

        if legacy_technician:

            r = add_row(
                grid,
                "کاربر فنی قدیمی:",
                legacy_technician,
                r,
            )

        cost_card = self._card(
            scrollable
        )

        self._card_header(
            cost_card,
            "هزینه‌ها",
            "💰",
        )

        cg = tk.Frame(
            cost_card,
            bg=CARD_BG,
        )

        cg.pack(
            fill=tk.X,
            padx=10,
            pady=8,
        )

        cr = 0

        cr = add_row(
            cg,
            "هزینه دستی (ریال):",
            (
                f"{wo.manual_cost:,.0f}"
                if wo.manual_cost
                else "0"
            ),
            cr,
        )

        cr = add_row(
            cg,
            "توضیح هزینه:",
            wo.cost_description
            or "—",
            cr,
        )

        # ------------------------------------------------------------------
        # Delay
        # ------------------------------------------------------------------

        if (
            wo.delay_minutes
            or wo.delay_reason
        ):

            delay_card = self._card(
                scrollable
            )

            self._card_header(
                delay_card,
                "تأخیر",
                "⏱️",
            )

            dg = tk.Frame(
                delay_card,
                bg=CARD_BG,
            )

            dg.pack(
                fill=tk.X,
                padx=10,
                pady=8,
            )

            dr = 0

            dr = add_row(
                dg,
                "دقیقه تأخیر:",
                wo.delay_minutes
                or 0,
                dr,
            )

            dr = add_row(
                dg,
                "علت تأخیر:",
                wo.delay_reason
                or "—",
                dr,
            )

        def text_card(
            title,
            icon,
            content,
        ):

            tc = self._card(
                scrollable
            )

            self._card_header(
                tc,
                title,
                icon,
            )

            txt = tk.Text(
                tc,
                height=4,
                wrap="word",
                font=FONT_NORMAL,
                bg=SECTION_BG,
                fg=TEXT_DARK,
                relief="flat",
                padx=10,
                pady=6,
            )

            txt.insert(
                "1.0",
                content
                or "—",
            )

            txt.config(
                state="disabled"
            )

            txt.pack(
                fill=tk.X,
                padx=10,
                pady=8,
            )

        text_card(
            "یادداشت اپراتور",
            "👤",
            wo.operator_notes,
        )

        text_card(
            "توضیحات تعمیر",
            "🔧",
            wo.description,
        )

        text_card(
            "قطعات مصرفی",
            "🔩",
            wo.parts_used,
        )

        tk.Button(
            detail,
            text="✕  بستن",
            font=FONT_NORMAL,
            bg=ACCENT_ROSE,
            fg=WHITE,
            relief="flat",
            cursor="hand2",
            padx=20,
            pady=8,
            command=detail.destroy,
        ).pack(
            pady=10
        )

    # =========================================================================
    # EXCEL EXPORT
    # =========================================================================

    def _export_tab_to_excel(
        self,
        frame,
        tab_title,
    ):

        # Export only the report tab whose button was pressed.
        # The same date-range filter used by the Reports screen is applied
        # to the exported data and written into the Excel header.
        try:
            start_date = self.start_date.get_date()
            end_date = self.end_date.get_date()
        except Exception as exc:
            messagebox.showerror(
                "بازه گزارش",
                f"دریافت بازه تاریخ با خطا مواجه شد:\n\n{exc}",
                parent=self,
            )
            return

        if start_date is None or end_date is None:
            messagebox.showwarning(
                "بازه گزارش",
                "لطفاً تاریخ شروع و پایان گزارش را مشخص کنید.",
                parent=self,
            )
            return

        if start_date > end_date:
            messagebox.showwarning(
                "بازه گزارش",
                "تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.",
                parent=self,
            )
            return

        data = self._collect_tab_data(
            frame,
            tab_title,
        )

        if not data:

            messagebox.showwarning(
                "هشدار",
                "داده‌ای برای خروجی وجود ندارد!",
                parent=self,
            )

            return

        filename = (
            filedialog
            .asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[
                    (
                        "Excel files",
                        "*.xlsx",
                    )
                ],
                initialfile=(
                    f"{tab_title}_"
                    f"{jalali_stamp()}.xlsx"
                ),
            )
        )

        if not filename:
            return

        try:

            wb = Workbook()

            ws = wb.active

            ws.title = (
                tab_title[:31]
            )

            ws.sheet_view.rightToLeft = True
            ws.sheet_view.showGridLines = False
            ws.page_setup.paperSize = "9"  # A4
            ws.page_setup.orientation = "landscape"
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.page_margins.left = 0.25
            ws.page_margins.right = 0.25
            ws.page_margins.top = 0.35
            ws.page_margins.bottom = 0.35
            ws.page_margins.header = 0.15
            ws.page_margins.footer = 0.15
            ws.print_options.horizontalCentered = True

            headers = list(
                data[0].keys()
            )

            max_cols = len(
                headers
            )

            ws.merge_cells(
                start_row=1,
                start_column=1,
                end_row=1,
                end_column=max_cols,
            )

            cell = ws.cell(
                row=1,
                column=1,
                value=(
                    "شرکت گلا — "
                    "سیستم نگهداری پیشگیرانه"
                ),
            )

            cell.font = Font(
                name="Tahoma",
                size=12,
                bold=True,
                color="FFFFFF",
            )

            cell.fill = PatternFill(
                start_color="1A2A44",
                end_color="1A2A44",
                fill_type="solid",
            )

            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

            ws.row_dimensions[
                1
            ].height = 30

            ws.merge_cells(
                start_row=2,
                start_column=1,
                end_row=2,
                end_column=max_cols,
            )

            tc = ws.cell(
                row=2,
                column=1,
                value=tab_title,
            )

            tc.font = Font(
                name="Tahoma",
                size=14,
                bold=True,
                color="1A2A44",
            )

            tc.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

            ws.row_dimensions[
                2
            ].height = 25

            # Report period is shown to users in the Jalali calendar.
            start = to_jalali_date_str(start_date)
            end = to_jalali_date_str(end_date)

            ws.merge_cells(
                start_row=3,
                start_column=1,
                end_row=3,
                end_column=max_cols,
            )

            ic = ws.cell(
                row=3,
                column=1,
                value=(
                    f"بازه گزارش: "
                    f"{start} تا {end}  |  "
                    "تاریخ تهیه: "
                    f"{to_jalali_datetime_str(tehran_now())}"
                ),
            )

            ic.font = Font(
                name="Tahoma",
                size=9,
                italic=True,
                color="5F6368",
            )

            ic.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

            ws.row_dimensions[
                3
            ].height = 20

            header_row = 5

            for ci, header in enumerate(
                headers,
                1,
            ):

                c = ws.cell(
                    row=header_row,
                    column=ci,
                    value=header,
                )

                c.font = Font(
                    name="Tahoma",
                    size=10,
                    bold=True,
                    color="FFFFFF",
                )

                c.fill = PatternFill(
                    start_color="1A2A44",
                    end_color="1A2A44",
                    fill_type="solid",
                )

                c.alignment = Alignment(
                    horizontal="center",
                    vertical="center",
                    wrap_text=True,
                )

                c.border = Border(
                    left=Side(
                        style="thin"
                    ),
                    right=Side(
                        style="thin"
                    ),
                    top=Side(
                        style="thin"
                    ),
                    bottom=Side(
                        style="thin"
                    ),
                )

            ws.row_dimensions[
                header_row
            ].height = 28

            for ri, row_data in enumerate(
                data,
                start=header_row + 1,
            ):

                bg = (
                    "F4F6F9"
                    if ri % 2 == 0
                    else "FFFFFF"
                )

                for ci, value in enumerate(
                    row_data.values(),
                    1,
                ):

                    c = ws.cell(
                        row=ri,
                        column=ci,
                        value=value,
                    )

                    c.font = Font(
                        name="Tahoma",
                        size=9,
                    )

                    c.fill = PatternFill(
                        start_color=bg,
                        end_color=bg,
                        fill_type="solid",
                    )

                    c.alignment = Alignment(
                        horizontal="center",
                        vertical="center",
                        wrap_text=True,
                    )

                    c.border = Border(
                        left=Side(
                            style="thin",
                            color="E8ECF0",
                        ),
                        right=Side(
                            style="thin",
                            color="E8ECF0",
                        ),
                        top=Side(
                            style="thin",
                            color="E8ECF0",
                        ),
                        bottom=Side(
                            style="thin",
                            color="E8ECF0",
                        ),
                    )

                    if (
                        isinstance(
                            value,
                            (
                                int,
                                float,
                            ),
                        )
                        and not isinstance(
                            value,
                            bool,
                        )
                    ):

                        try:

                            c.number_format = (
                                "#,##0.00"
                                if isinstance(
                                    value,
                                    float,
                                )
                                else
                                "#,##0"
                            )

                        except Exception:

                            pass

                ws.row_dimensions[
                    ri
                ].height = 20

            for ci in range(
                1,
                len(headers) + 1,
            ):

                max_len = 10

                for r in range(
                    header_row,
                    header_row
                    + len(data)
                    + 1,
                ):

                    v = ws.cell(
                        row=r,
                        column=ci,
                    ).value

                    if v:

                        max_len = max(
                            max_len,
                            len(
                                str(v)
                            ),
                        )

                ws.column_dimensions[
                    get_column_letter(
                        ci
                    )
                ].width = min(
                    max_len + 2,
                    50,
                )

            ws.freeze_panes = ws.cell(
                row=header_row + 1,
                column=1,
            )
            last_row = header_row + len(data)
            last_col = len(headers)
            ws.print_area = f"A1:{get_column_letter(last_col)}{max(last_row, header_row)}"
            ws.print_title_rows = "1:5"

            wb.save(
                filename
            )

            messagebox.showinfo(
                "موفق",
                "خروجی Excel با موفقیت ذخیره شد!",
                parent=self,
            )

        except Exception as exc:

            messagebox.showerror(
                "خطا",
                (
                    "خطا در ایجاد خروجی:\n"
                    f"{exc}"
                ),
                parent=self,
            )

    # =========================================================================
    # COLLECT EXPORT DATA
    # =========================================================================

    def _collect_tab_data(
        self,
        frame,
        tab_title,
    ):
        """Collect exactly the data represented by the requested report tab.

        Only the four report tabs with Excel actions are supported here. The
        currently selected Reports date range is already applied when the tab
        data is loaded; KPI trend data is additionally period-filtered by
        _get_kpi_trend_for_period().
        """

        # ------------------------------------------------------------------
        # Equipment: export the rows currently visible after search/category
        # filtering, so Excel matches what the user is looking at.
        # ------------------------------------------------------------------
        if tab_title == "عملکرد تجهیزات":
            tree = getattr(self, "equipment_tree", None)
            if tree is None:
                return []

            headers = {
                "id": "شناسه", "name": "نام تجهیز", "category": "دسته", "location": "محل",
                "status": "وضعیت", "total_wo": "کل WO", "completed": "تکمیل شده",
                "pm": "PM", "cm": "CM", "em": "EM",
                "mtbf": "MTBF (ساعت)", "mttr": "MTTR (ساعت)",
                "availability": "دسترسی (%)", "oee": "OEE (%)",
                "downtime": "توقف (ساعت)", "total_cost": "هزینه کل (ریال)",
            }
            columns = list(tree["columns"])
            data = []
            for child in tree.get_children():
                values = list(tree.item(child).get("values", ()))
                data.append({
                    headers[col]: value
                    for col, value in zip(columns, values)
                    if col in headers
                })
            return data

        # ------------------------------------------------------------------
        # Personnel: export the same rows shown in the visible Personnel tree.
        # ------------------------------------------------------------------
        if tab_title == "عملکرد پرسنل":
            tree = getattr(self, "tech_tree", None)
            if tree is not None:
                data = []
                for child in tree.get_children():
                    values = tree.item(child).get("values", ())
                    if len(values) < 6:
                        continue
                    data.append({
                        "پرسنل": values[0],
                        "دپارتمان": values[1],
                        "کل وظایف": values[2],
                        "تکمیل شده": values[3],
                        "نرخ تکمیل (%)": values[4],
                        "میانگین زمان (ساعت)": values[5],
                    })
                if data:
                    return data

            personnel_data = self._personnel_performance_data or []
            return [
                {
                    "پرسنل": item.get("personnel_name", "—"),
                    "دپارتمان": item.get("department_name", "—"),
                    "کل وظایف": item.get("total_tasks", 0),
                    "تکمیل شده": item.get("completed_tasks", 0),
                    "نرخ تکمیل (%)": item.get("completion_rate", 0),
                    "میانگین زمان (ساعت)": item.get("avg_completion_hours", 0),
                }
                for item in personnel_data
            ]

        # ------------------------------------------------------------------
        # Failure: the renderer displays the complete list returned for the
        # selected period (up to the repository's existing limit=50).
        # ------------------------------------------------------------------
        if tab_title == "تحلیل خرابی‌ها":
            failures = self._report_tab_data.get("failure") or []
            if not isinstance(failures, list):
                return []
            return [
                {
                    "توضیحات خرابی": item.get("description", "—"),
                    "تعداد تکرار": item.get("count", 0),
                }
                for item in failures
                if isinstance(item, dict)
            ]

        # ------------------------------------------------------------------
        # KPI: export every data component currently represented in the tab:
        # monthly PM/CM/EM trend, schedule compliance, PM/CM/EM ratio, and
        # the same top-10 risk table shown by the UI.
        # ------------------------------------------------------------------
        if tab_title == "تحلیل KPI":
            kpi = self._report_tab_data.get("kpi") or {}
            if not isinstance(kpi, dict):
                return []

            rows = []

            for item in kpi.get("trend") or []:
                if not isinstance(item, dict):
                    continue
                rows.append({
                    "بخش": "روند ماهانه PM / CM / EM",
                    "شاخص": item.get("type", "—"),
                    "دوره": (
                        f"{item.get('year', '—')}/{int(item.get('month', 0) or 0):02d}"
                        if item.get("month") is not None
                        else "—"
                    ),
                    "مقدار": item.get("count", 0),
                    "توضیحات": "تعداد دستورکار در ماه",
                })

            compliance = kpi.get("compliance") or {}
            if isinstance(compliance, dict):
                rows.extend([
                    {
                        "بخش": "انطباق برنامه",
                        "شاخص": "کل وظایف برنامه",
                        "دوره": "بازه انتخاب‌شده",
                        "مقدار": compliance.get("total_tasks", 0),
                        "توضیحات": "کل برنامه‌های بررسی‌شده",
                    },
                    {
                        "بخش": "انطباق برنامه",
                        "شاخص": "انجام به موقع",
                        "دوره": "بازه انتخاب‌شده",
                        "مقدار": compliance.get("on_time", 0),
                        "توضیحات": "وظایف انجام‌شده در موعد",
                    },
                    {
                        "بخش": "انطباق برنامه",
                        "شاخص": "تاخیر",
                        "دوره": "بازه انتخاب‌شده",
                        "مقدار": compliance.get("late", 0),
                        "توضیحات": "وظایف انجام‌شده با تأخیر",
                    },
                    {
                        "بخش": "انطباق برنامه",
                        "شاخص": "نرخ انطباق (%)",
                        "دوره": "بازه انتخاب‌شده",
                        "مقدار": compliance.get("compliance_rate", 0),
                        "توضیحات": "درصد انطباق برنامه",
                    },
                ])

            pm_cm = kpi.get("pm_cm") or {}
            if isinstance(pm_cm, dict):
                rows.extend([
                    {
                        "بخش": "نسبت PM / CM / EM",
                        "شاخص": "PM",
                        "دوره": "بازه انتخاب‌شده",
                        "مقدار": pm_cm.get("preventive_count", 0),
                        "توضیحات": "دستورکار پیشگیرانه",
                    },
                    {
                        "بخش": "نسبت PM / CM / EM",
                        "شاخص": "CM",
                        "دوره": "بازه انتخاب‌شده",
                        "مقدار": pm_cm.get("corrective_count", 0),
                        "توضیحات": "دستورکار اصلاحی",
                    },
                    {
                        "بخش": "نسبت PM / CM / EM",
                        "شاخص": "EM",
                        "دوره": "بازه انتخاب‌شده",
                        "مقدار": pm_cm.get("emergency_count", 0),
                        "توضیحات": "دستورکار اضطراری",
                    },
                    {
                        "بخش": "نسبت PM / CM / EM",
                        "شاخص": "نسبت PM/CM",
                        "دوره": "بازه انتخاب‌شده",
                        "مقدار": pm_cm.get("ratio", 0),
                        "توضیحات": "نسبت دستورکارهای PM به CM",
                    },
                ])

            for item in (kpi.get("risk") or [])[:10]:
                if not isinstance(item, dict):
                    continue
                score = item.get("risk_score", 0) or 0
                level = item.get("risk_level", "—")
                if score >= 70 or level == "HIGH":
                    level_text = "بالا"
                elif score >= 40 or level == "MEDIUM":
                    level_text = "متوسط"
                else:
                    level_text = "پایین"

                rows.append({
                    "بخش": "تجهیزات با ریسک بالا",
                    "شاخص": item.get("equipment_name", "—"),
                    "دوره": "بازه انتخاب‌شده",
                    "مقدار": score,
                    "توضیحات": (
                        f"سطح: {level_text} | "
                        f"تعداد خرابی: {item.get('failure_count', 0)} | "
                        f"متوسط توقف: {item.get('avg_downtime_hours', 0):.1f} ساعت"
                    ),
                })

            return rows

        return []

