from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from queue import Queue, Empty
from threading import Thread
from time import monotonic

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from database.report_repository import ReportRepository
from database.work_order_repository import WorkOrderRepository
from database.pm_repository import PMRepository
from database.spare_parts_repository import SparePartsRepository
from database.inspection_repository import InspectionRepository
from database.db import SessionLocal

from utils.theme import (
    NAVY,
    NAVY_LIGHT,
    WHITE,
    RED,
    TEXT_DARK,
    TEXT_LIGHT,
    SUCCESS,
    FONT_TITLE,
    FONT_HEADING,
    FONT_SUBHEADING,
    FONT_NORMAL,
    FONT_SMALL,
    FONT_KPI,
)

from utils.date_helpers import to_jalali_date_str
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock
import jdatetime


# =============================================================================
# LOCAL DESIGN TOKENS
# =============================================================================

PAGE_BG = "#E9EFF5"
SECTION_BG = "#E7EDF3"

CARD_BG = "#FFFFFF"
CARD_ALT_BG = "#F8FAFC"

CARD_BORDER = "#D5DEE8"
SECTION_BORDER = "#CFD9E4"

MUTED_BG = "#EEF3F7"

ACCENT_TEAL = "#0D9488"
ACCENT_AMBER = "#D97706"
ACCENT_ROSE = "#DC2626"
ACCENT_BLUE = "#2563EB"
ACCENT_PURPLE = "#7C3AED"
ACCENT_CYAN = "#0891B2"

SUCCESS_BG = "#DCFCE7"
WARNING_BG = "#FEF3C7"
DANGER_BG = "#FEE2E2"
INFO_BG = "#DBEAFE"
PURPLE_BG = "#EDE9FE"

SHADOW = "#CDD7E2"

STATUS_COLORS = {
    "PENDING": ("#FEF3C7", "#92400E"),
    "IN_PROGRESS": ("#DBEAFE", "#1E40AF"),
    "APPROVED": ("#D1FAE5", "#065F46"),
    "REJECTED": ("#FEE2E2", "#991B1B"),
    "PENDING_APPROVAL": ("#EDE9FE", "#5B21B6"),
    "FINISH_REQUESTED": ("#FFF7ED", "#C2410C"),
}

STATUS_FA = {
    "PENDING": "در انتظار",
    "IN_PROGRESS": "در حال انجام",
    "APPROVED": "تکمیل شده",
    "PENDING_APPROVAL": "در انتظار تأیید",
    "FINISH_REQUESTED": "درخواست اتمام",
    "REJECTED": "رد شده",
}

VIEW_KEYS = {
    "work_orders": "دستورکارها",
    "equipment": "تجهیزات",
    "spare_parts": "قطعات یدکی",
    "pm_schedule": "PM",
    "inspection": "بازرسی‌ها",
    "repair_request": "حکم درخواست تعمیرات",
    "machine_hours": "ساعات کارکرد",
    "reports": "تحلیل و گزارشات",
}

AUTO_REFRESH_TTL_SECONDS = 45.0


# =============================================================================
# HELPERS
# =============================================================================

def _enum_name(value):
    if value is None:
        return ""

    return str(
        getattr(
            value,
            "name",
            value,
        )
    )


def _safe_int(
    value,
    default=0,
):
    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def _safe_float(
    value,
    default=0.0,
):
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def _safe_text(
    value,
    default="—",
):
    if value is None:
        return default

    text = str(value).strip()

    return (
        text
        if text
        else default
    )


def _pct(
    part,
    total,
):
    try:
        if not total:
            return 0.0

        return (
            float(part)
            / float(total)
        ) * 100.0

    except Exception:
        return 0.0


# =============================================================================
# DASHBOARD
# =============================================================================

class DashboardView(ttk.Frame):
    """Responsive maintenance dashboard for the Gela PM System.

    Database work is performed in a background thread so the Tkinter event
    loop remains responsive.

    The dashboard keeps the application UI Persian while chart terminology
    uses English labels for clearer graphical presentation.
    """

    def __init__(
        self,
        parent,
        current_user,
    ):
        super().__init__(
            parent
        )

        self.current_user = (
            current_user or {}
        )

        # ---------------------------------------------------------------------
        # Repository references
        # ---------------------------------------------------------------------
        #
        # Database calls during refresh are executed using fresh repository
        # instances inside the worker thread.
        #
        # These references are kept for compatibility with existing dashboard
        # integrations.
        #
        self.report_repo = ReportRepository(
            SessionLocal
        )

        self.wo_repo = WorkOrderRepository(
            SessionLocal
        )

        self.pm_repo = PMRepository(
            SessionLocal
        )

        self.sp_repo = SparePartsRepository(
            SessionLocal
        )

        self.ins_repo = InspectionRepository(
            SessionLocal
        )

        # ---------------------------------------------------------------------
        # Cached dashboard data
        # ---------------------------------------------------------------------

        self.kpi_data = {}
        self.backlog = {}
        self.pm_cm = {}
        self.risk_data = []

        self.recent_wos = []
        self.low_stock = []
        self.upcoming_pms = []
        self.recent_ins = []

        self.low_stock_count = 0
        self.overdue_count = 0

        # ---------------------------------------------------------------------
        # State
        # ---------------------------------------------------------------------

        self._refresh_running = False

        self._last_layout_signature = None

        self._resize_after_id = None
        self._poll_after_id = None

        self._last_refresh_text = "—"
        self._last_refresh_monotonic = 0.0

        self._refresh_queue = Queue()

        # Explicit matplotlib figure tracking.
        self._chart_figures = []

        # ---------------------------------------------------------------------
        # Build
        # ---------------------------------------------------------------------

        self._build_ui_shell()

        self.bind(
            "<Configure>",
            self._on_resize,
            add="+",
        )

        self.after_idle(
            self._refresh_all
        )

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def _on_show(self):
        if self._refresh_running:
            return

        if self._has_loaded_data():

            age = (
                monotonic()
                - self._last_refresh_monotonic
            )

            if age < AUTO_REFRESH_TTL_SECONDS:
                return

        self._refresh_all()

    def _has_loaded_data(self):
        return bool(
            self.kpi_data
            or self.backlog
            or self.pm_cm
        )

    # =========================================================================
    # SHELL
    # =========================================================================

    def _build_ui_shell(self):
        self.configure(
            style="Dashboard.TFrame"
        )

        style = ttk.Style(self)

        try:
            style.configure(
                "Dashboard.TFrame",
                background=PAGE_BG,
            )
        except Exception:
            pass

        self.header = tk.Frame(
            self,
            bg=PAGE_BG,
        )

        # Shared page-header style (views/ux.py): a full-width white band
        # with a thin bottom border, like every other page.
        self.header.pack(
            fill=tk.X,
            padx=0,
            pady=(0, 10),
        )

        self._build_header(
            self.header
        )

        self.content_frame = tk.Frame(
            self,
            bg=PAGE_BG,
        )

        self.content_frame.pack(
            fill=tk.BOTH,
            expand=True,
        )

    def _build_header(
        self,
        parent,
    ):
        card = tk.Frame(
            parent,
            bg=CARD_BG,
            bd=0,
            highlightthickness=0,
        )

        card.pack(
            fill=tk.X
        )

        body = tk.Frame(
            card,
            bg=CARD_BG,
        )

        body.pack(
            fill=tk.X,
            padx=22,
            pady=12,
        )

        tk.Frame(
            card,
            bg=CARD_BORDER,
            height=1,
        ).pack(
            fill=tk.X
        )

        left = tk.Frame(
            body,
            bg=CARD_BG,
        )

        left.pack(
            side=tk.LEFT,
            fill=tk.Y,
        )

        self.refresh_button = tk.Button(
            left,
            text="↻  بروزرسانی",
            command=self._refresh_all,
            bg=NAVY,
            fg=WHITE,
            activebackground=NAVY_LIGHT,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=18,
            pady=9,
        )

        try:
            from views.ux import style_button
            style_button(self.refresh_button, "outline")
        except Exception:
            pass

        self.refresh_button.pack(
            side=tk.LEFT,
            padx=(0, 8),
            pady=3,
        )

        self.header_refresh_label = tk.Label(
            left,
            text="آخرین بروزرسانی: —",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
        )

        self.header_refresh_label.pack(
            side=tk.LEFT,
            padx=8,
        )

        right = tk.Frame(
            body,
            bg=CARD_BG,
        )

        right.pack(
            side=tk.RIGHT,
            fill=tk.Y,
        )

        title_row = tk.Frame(
            right,
            bg=CARD_BG,
        )

        title_row.pack(
            anchor="e"
        )

        tk.Label(
            title_row,
            text="داشبورد مدیریت",
            font=FONT_TITLE,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).pack(
            side=tk.RIGHT
        )

        tk.Label(
            title_row,
            text="📊",
            font=(
                "Segoe UI Symbol",
                21,
            ),
            bg=CARD_BG,
            fg=ACCENT_TEAL,
        ).pack(
            side=tk.RIGHT,
            padx=(0, 10),
        )

        full_name = _safe_text(
            self.current_user.get(
                "full_name"
            ),
            "کاربر",
        )

        username = _safe_text(
            self.current_user.get(
                "username"
            ),
            "",
        )

        greeting = (
            f"خوش آمدید، "
            f"{full_name}"
        )

        if (
            username
            and username != full_name
        ):
            greeting += (
                f"  ·  "
                f"{username}"
            )

        tk.Label(
            right,
            text=greeting,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
            anchor="e",
        ).pack(
            anchor="e",
            pady=(5, 0),
        )

        tk.Label(
            right,
            text=(
                "تمرکز بر عملکرد، ریسک، "
                "انطباق PM و اقدامات موردنیاز"
            ),
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            anchor="e",
        ).pack(
            anchor="e",
            pady=(2, 0),
        )

        self._hero_status = tk.Label(
            body,
            text="● آماده",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=SUCCESS,
        )

        self._hero_status.pack(
            side=tk.RIGHT,
            padx=(0, 16),
            pady=(25, 0),
        )

    # =========================================================================
    # DATA LOADING
    # =========================================================================

    def _refresh_all(self):
        if self._refresh_running:
            return

        self._refresh_running = True

        self.refresh_button.configure(
            state="disabled",
            text="⟳  در حال بروزرسانی...",
        )

        self._hero_status.configure(
            text=(
                "● در حال دریافت "
                "آخرین داده‌ها..."
            ),
            fg=ACCENT_BLUE,
        )

        if not self._has_loaded_data():
            self._render_loading_state()

        worker = Thread(
            target=self._refresh_worker,
            name="dashboard-refresh",
            daemon=True,
        )

        worker.start()

        self._schedule_refresh_poll()

    def _schedule_refresh_poll(self):
        if (
            self._poll_after_id
            is not None
        ):
            return

        self._poll_after_id = self.after(
            60,
            self._poll_refresh_queue,
        )

    def _poll_refresh_queue(self):
        self._poll_after_id = None

        if not self.winfo_exists():
            return

        try:
            kind, payload = (
                self._refresh_queue.get_nowait()
            )

        except Empty:

            if self._refresh_running:
                self._schedule_refresh_poll()

            return

        if kind == "success":
            self._apply_refresh_result(
                payload
            )

        else:
            self._finish_refresh_with_error(
                payload
            )

    def _refresh_worker(self):
        """Perform dashboard database reads in a background thread."""

        try:

            # Fresh repositories per thread.
            report_repo = ReportRepository(
                SessionLocal
            )

            wo_repo = WorkOrderRepository(
                SessionLocal
            )

            pm_repo = PMRepository(
                SessionLocal
            )

            sp_repo = SparePartsRepository(
                SessionLocal
            )

            ins_repo = InspectionRepository(
                SessionLocal
            )

            # -----------------------------------------------------------------
            # Reporting data
            # -----------------------------------------------------------------

            kpi_data = (
                report_repo.get_kpi_summary()
                or {}
            )

            backlog = (
                report_repo.get_backlog_analysis()
                or {}
            )

            pm_cm = (
                report_repo.get_pm_cm_ratio()
                or {}
            )

            risk_data = list(
                report_repo.get_equipment_risk_score()
                or []
            )[:6]

            # -----------------------------------------------------------------
            # PM overdue
            # -----------------------------------------------------------------

            overdue_count = _safe_int(
                pm_repo.get_overdue_count()
            )

            # -----------------------------------------------------------------
            # Recent Work Orders
            # -----------------------------------------------------------------

            recent_wos = []

            for wo in (
                wo_repo.get_all(
                    status_filter=None,
                    type_filter=None,
                    limit=6,  # only the 6 newest are shown
                )
                or []
            )[:6]:

                try:

                    equipment = getattr(
                        wo,
                        "equipment",
                        None,
                    )

                    recent_wos.append(
                        {
                            "id": getattr(
                                wo,
                                "id",
                                None,
                            ),
                            "equipment": getattr(
                                equipment,
                                "name",
                                None,
                            ),
                            "title": getattr(
                                wo,
                                "title",
                                None,
                            ),
                            "status": _enum_name(
                                getattr(
                                    wo,
                                    "status",
                                    None,
                                )
                            ),
                        }
                    )

                except Exception:
                    continue

            # -----------------------------------------------------------------
            # Low stock
            # -----------------------------------------------------------------

            low_stock_all = (
                sp_repo.get_low_stock()
                or []
            )

            low_stock = []

            for part in (
                low_stock_all[:6]
            ):

                low_stock.append(
                    {
                        "name": getattr(
                            part,
                            "name",
                            None,
                        ),
                        "current": getattr(
                            part,
                            "current_stock",
                            0,
                        ),
                        "minimum": getattr(
                            part,
                            "min_stock",
                            0,
                        ),
                    }
                )

            low_stock_count = len(
                low_stock_all
            )

            # -----------------------------------------------------------------
            # Upcoming PMs
            # -----------------------------------------------------------------

            upcoming_pms = list(
                pm_repo.get_upcoming_pms_dict(
                    days=7
                )
                or []
            )[:6]

            # -----------------------------------------------------------------
            # Recent Inspections
            # -----------------------------------------------------------------

            recent_ins = []

            for ins in (
                ins_repo.get_all_inspections(limit=6)
                or []
            )[:6]:

                try:

                    equipment = getattr(
                        ins,
                        "equipment",
                        None,
                    )

                    template = getattr(
                        ins,
                        "template",
                        None,
                    )

                    recent_ins.append(
                        {
                            "equipment": getattr(
                                equipment,
                                "name",
                                None,
                            ),
                            "template": getattr(
                                template,
                                "name",
                                None,
                            ),
                            "result": getattr(
                                ins,
                                "overall_result",
                                None,
                            ),
                            "status": _enum_name(
                                getattr(
                                    ins,
                                    "status",
                                    None,
                                )
                            ),
                        }
                    )

                except Exception:
                    continue

            result = {
                "kpi_data": kpi_data,
                "backlog": backlog,
                "pm_cm": pm_cm,
                "risk_data": risk_data,
                "recent_wos": recent_wos,
                "low_stock": low_stock,
                "low_stock_count": low_stock_count,
                "upcoming_pms": upcoming_pms,
                "recent_ins": recent_ins,
                "overdue_count": overdue_count,
                "timestamp": jdatetime.datetime.fromgregorian(datetime=tehran_now()).strftime("%Y/%m/%d %H:%M:%S"),
            }

            self._refresh_queue.put(
                (
                    "success",
                    result,
                )
            )

        except Exception as exc:

            self._refresh_queue.put(
                (
                    "error",
                    exc,
                )
            )

    def _apply_refresh_result(
        self,
        result,
    ):
        self.kpi_data = (
            result.get(
                "kpi_data"
            )
            or {}
        )

        self.backlog = (
            result.get(
                "backlog"
            )
            or {}
        )

        self.pm_cm = (
            result.get(
                "pm_cm"
            )
            or {}
        )

        self.risk_data = (
            result.get(
                "risk_data"
            )
            or []
        )

        self.recent_wos = (
            result.get(
                "recent_wos"
            )
            or []
        )

        self.low_stock = (
            result.get(
                "low_stock"
            )
            or []
        )

        self.upcoming_pms = (
            result.get(
                "upcoming_pms"
            )
            or []
        )

        self.recent_ins = (
            result.get(
                "recent_ins"
            )
            or []
        )

        self.low_stock_count = _safe_int(
            result.get(
                "low_stock_count",
                0,
            )
        )

        self.overdue_count = _safe_int(
            result.get(
                "overdue_count",
                0,
            )
        )

        self._last_refresh_text = (
            result.get(
                "timestamp",
                "—",
            )
        )

        self._last_refresh_monotonic = (
            monotonic()
        )

        self.header_refresh_label.configure(
            text=(
                "آخرین بروزرسانی: "
                f"{self._last_refresh_text}"
            )
        )

        self._hero_status.configure(
            text="● داده‌ها بروزرسانی شد",
            fg=SUCCESS,
        )

        self._refresh_running = False

        self.refresh_button.configure(
            state="normal",
            text="↻  بروزرسانی",
        )

        self._render_dashboard(
            force=True
        )

    def _finish_refresh_with_error(
        self,
        exc,
    ):
        self._refresh_running = False

        self.refresh_button.configure(
            state="normal",
            text="↻  بروزرسانی",
        )

        self._hero_status.configure(
            text="● خطا در دریافت داده‌ها",
            fg=RED,
        )

        self._render_error(
            exc
        )

    # =========================================================================
    # RESPONSIVE RENDERER
    # =========================================================================

    def _on_resize(
        self,
        _event=None,
    ):
        if (
            self._resize_after_id
            is not None
        ):

            try:
                self.after_cancel(
                    self._resize_after_id
                )

            except Exception:
                pass

        self._resize_after_id = self.after(
            180,
            self._render_dashboard,
        )

    def _layout_signature(self):
        width = max(
            1,
            self.winfo_width(),
        )

        if width < 720:
            return (
                1,
                1,
            )

        if width < 1080:
            return (
                2,
                1,
            )

        return (
            4,
            2,
        )

    def _clear_dashboard_widgets(self):

        for fig in self._chart_figures:

            try:
                fig.clear()

            except Exception:
                pass

        self._chart_figures.clear()

        for widget in (
            self.content_frame.winfo_children()
        ):

            try:
                widget.destroy()

            except Exception:
                pass

    def _render_dashboard(
        self,
        force=False,
    ):
        if not self.winfo_exists():
            return

        signature = (
            self._layout_signature()
        )

        if (
            not force
            and signature
            == self._last_layout_signature
        ):

            self._resize_after_id = None
            return

        self._last_layout_signature = (
            signature
        )

        self._resize_after_id = None

        if not self._has_loaded_data():
            self._render_loading_state()
            return

        self._clear_dashboard_widgets()

        kpi_cols, chart_cols = signature

        self._build_kpi_section(
            kpi_cols
        )

        self._build_focus_strip(
            kpi_cols
        )

        self._build_analysis_section(
            chart_cols
        )

        self._build_events_section(
            chart_cols
        )

        self._build_quick_actions(
            kpi_cols
        )

    def _render_loading_state(self):

        self._clear_dashboard_widgets()

        outer = tk.Frame(
            self.content_frame,
            bg=PAGE_BG,
        )

        outer.pack(
            fill=tk.BOTH,
            expand=True,
            padx=22,
            pady=22,
        )

        shadow = tk.Frame(
            outer,
            bg=SHADOW,
        )

        shadow.pack(
            fill=tk.BOTH,
            expand=True,
        )

        card = tk.Frame(
            shadow,
            bg=CARD_BG,
            bd=0,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )

        card.pack(
            fill=tk.BOTH,
            expand=True,
            padx=1,
            pady=1,
        )

        tk.Frame(
            card,
            bg=ACCENT_TEAL,
            height=5,
        ).pack(
            fill=tk.X
        )

        tk.Label(
            card,
            text="در حال بارگذاری داشبورد...",
            font=FONT_TITLE,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).pack(
            pady=(90, 10)
        )

        tk.Label(
            card,
            text=(
                "اطلاعات از پایگاه داده "
                "در حال دریافت است."
            ),
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
        ).pack()

        tk.Label(
            card,
            text="لطفاً چند لحظه صبر کنید",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=ACCENT_TEAL,
        ).pack(
            pady=(8, 80)
        )

    # =========================================================================
    # SECTION HELPERS
    # =========================================================================

    def _section_heading(
        self,
        parent,
        title,
        subtitle="",
        icon="•",
    ):
        row = tk.Frame(
            parent,
            bg=PAGE_BG,
        )

        row.pack(
            fill=tk.X,
            padx=22,
            pady=(18, 8),
        )

        title_side = tk.Frame(
            row,
            bg=PAGE_BG,
        )

        title_side.pack(
            side=tk.RIGHT
        )

        title_line = tk.Frame(
            title_side,
            bg=PAGE_BG,
        )

        title_line.pack(
            anchor="e"
        )

        tk.Label(
            title_line,
            text=f"{icon}  {title}",
            font=FONT_HEADING,
            bg=PAGE_BG,
            fg=TEXT_DARK,
        ).pack(
            side=tk.RIGHT
        )

        if subtitle:

            tk.Label(
                title_side,
                text=subtitle,
                font=FONT_SMALL,
                bg=PAGE_BG,
                fg=TEXT_LIGHT,
            ).pack(
                anchor="e",
                pady=(2, 0),
            )

        tk.Frame(
            row,
            bg=SECTION_BORDER,
            height=1,
        ).pack(
            side=tk.RIGHT,
            fill=tk.X,
            expand=True,
            padx=(0, 12),
            pady=9,
        )

    def _card(
        self,
        parent,
        padx=6,
        pady=6,
    ):
        shadow = tk.Frame(
            parent,
            bg=SHADOW,
        )

        shadow.grid(
            padx=padx,
            pady=pady,
            sticky="nsew",
        )

        card = tk.Frame(
            shadow,
            bg=CARD_BG,
            bd=0,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )

        card.pack(
            fill=tk.BOTH,
            expand=True,
            padx=1,
            pady=1,
        )

        return (
            shadow,
            card,
        )

    # =========================================================================
    # KPI SECTION
    # =========================================================================

    def _build_kpi_section(
        self,
        cols,
    ):
        self._section_heading(
            self.content_frame,
            "شاخص‌های کلیدی نگهداری",
            "نمای سریع از بار کار، انطباق و نقاط نیازمند توجه",
            "📌",
        )

        grid = tk.Frame(
            self.content_frame,
            bg=PAGE_BG,
        )

        grid.pack(
            fill=tk.X,
            padx=16,
            pady=(0, 2),
        )

        for col in range(cols):

            grid.grid_columnconfigure(
                col,
                weight=1,
                uniform="kpi",
            )

        total = _safe_int(
            self.kpi_data.get(
                "total_work_orders",
                0,
            )
        )

        done = _safe_int(
            self.kpi_data.get(
                "completed_work_orders",
                0,
            )
        )

        completion_rate = _pct(
            done,
            total,
        )

        pm_comp = _safe_float(
            self.kpi_data.get(
                "pm_compliance_rate",
                0,
            )
        )

        overdue = self.overdue_count

        emergency = _safe_int(
            self.kpi_data.get(
                "emergency_work_orders",
                0,
            )
        )

        total_eq = _safe_int(
            self.kpi_data.get(
                "total_equipment",
                0,
            )
        )

        low_stock = _safe_int(
            self.low_stock_count,
            len(self.low_stock),
        )

        # pending approval / ready / in progress / finish requested
        # (rejected work orders are closed, so not "total - done")
        open_wo = _safe_int(
            self.kpi_data.get(
                "open_work_orders",
                max(0, total - done),
            )
        )

        cards = [
            (
                "کل دستورکارها",
                f"{total:,}",
                "مجموع ثبت‌شده",
                ACCENT_BLUE,
                "📋",
            ),
            (
                "تکمیل‌شده",
                f"{done:,}",
                f"{completion_rate:.1f}٪ از کل",
                SUCCESS,
                "✅",
            ),
            (
                "نرخ تکمیل",
                f"{completion_rate:.1f}٪",
                "نسبت دستورکارهای تکمیل‌شده",
                ACCENT_TEAL,
                "📈",
            ),
            (
                "انطباق PM",
                f"{pm_comp:.1f}٪",
                "وضعیت اجرای نگهداری پیشگیرانه",
                ACCENT_PURPLE,
                "🎯",
            ),
            (
                "دستورکار باز",
                f"{open_wo:,}",
                "نیازمند پیگیری یا تکمیل",
                ACCENT_AMBER,
                "🔄",
            ),
            (
                "PM معوق",
                f"{overdue:,}",
                "برنامه‌های سررسید گذشته",
                ACCENT_ROSE,
                "⏰",
            ),
            (
                "دستورکار اضطراری",
                f"{emergency:,}",
                "فعالیت‌های فوری ثبت‌شده",
                RED,
                "🚨",
            ),
            (
                "تجهیزات",
                f"{total_eq:,}",
                f"قطعات کم‌موجود: {low_stock:,}",
                NAVY,
                "⚙",
            ),
        ]

        for index, item in enumerate(cards):

            row = index // cols
            col = index % cols

            self._kpi_card(
                grid,
                item,
                row,
                col,
            )

    def _kpi_card(
        self,
        parent,
        item,
        row,
        col,
    ):
        (
            title,
            value,
            subtitle,
            accent,
            icon,
        ) = item

        shadow = tk.Frame(
            parent,
            bg=SHADOW,
        )

        shadow.grid(
            row=row,
            column=col,
            padx=6,
            pady=6,
            sticky="nsew",
        )

        card = tk.Frame(
            shadow,
            bg=CARD_BG,
            bd=0,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )

        card.pack(
            fill=tk.BOTH,
            expand=True,
            padx=1,
            pady=1,
        )

        tk.Frame(
            card,
            bg=accent,
            height=5,
        ).pack(
            fill=tk.X
        )

        body = tk.Frame(
            card,
            bg=CARD_BG,
        )

        body.pack(
            fill=tk.BOTH,
            expand=True,
            padx=16,
            pady=14,
        )

        top = tk.Frame(
            body,
            bg=CARD_BG,
        )

        top.pack(
            fill=tk.X
        )

        tk.Label(
            top,
            text=icon,
            font=(
                "Segoe UI Symbol",
                17,
            ),
            bg=CARD_BG,
            fg=accent,
        ).pack(
            side=tk.RIGHT
        )

        tk.Label(
            top,
            text=title,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
            anchor="e",
        ).pack(
            side=tk.RIGHT,
            padx=(0, 8),
        )

        tk.Label(
            body,
            text=value,
            font=FONT_KPI,
            bg=CARD_BG,
            fg=accent,
            anchor="center",
        ).pack(
            fill=tk.X,
            pady=(9, 3),
        )

        tk.Label(
            body,
            text=subtitle,
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            anchor="center",
            wraplength=230,
        ).pack(
            fill=tk.X
        )

    # =========================================================================
    # FOCUS STRIP
    # =========================================================================

    def _build_focus_strip(
        self,
        cols,
    ):
        self._section_heading(
            self.content_frame,
            "تمرکز عملیاتی",
            "مواردی که بهتر است در شروع بررسی روزانه دیده شوند",
            "⚡",
        )

        container = tk.Frame(
            self.content_frame,
            bg=SECTION_BG,
        )

        container.pack(
            fill=tk.X,
            padx=16,
            pady=(0, 2),
        )

        for c in range(cols):

            container.grid_columnconfigure(
                c,
                weight=1,
                uniform="focus",
            )

        backlog_open = _safe_int(
            self.kpi_data.get(
                "open_work_orders",
                self.backlog.get("total_backlog", 0),
            )
        )

        overdue = self.overdue_count

        emergency = _safe_int(
            self.kpi_data.get(
                "emergency_work_orders",
                0,
            )
        )

        low_stock = _safe_int(
            self.low_stock_count,
            len(self.low_stock),
        )

        focus = [
            (
                "کارهای باز",
                f"{backlog_open:,}",
                "بررسی صف اجرایی",
                ACCENT_BLUE,
                INFO_BG,
                "🔄",
            ),
            (
                "PM معوق",
                f"{overdue:,}",
                "اولویت‌بندی برنامه‌های سررسید گذشته",
                ACCENT_ROSE,
                DANGER_BG,
                "⏰",
            ),
            (
                "EM ثبت‌شده",
                f"{emergency:,}",
                "پایش روند خرابی‌های اضطراری",
                ACCENT_AMBER,
                WARNING_BG,
                "🚨",
            ),
            (
                "قطعات کم‌موجود",
                f"{low_stock:,}",
                "پیگیری تأمین قطعات",
                ACCENT_PURPLE,
                PURPLE_BG,
                "🔧",
            ),
        ]

        for i, item in enumerate(focus):

            r, c = divmod(
                i,
                cols,
            )

            self._focus_card(
                container,
                item,
                r,
                c,
            )

    def _focus_card(
        self,
        parent,
        item,
        row,
        col,
    ):
        (
            title,
            value,
            subtitle,
            accent,
            soft_bg,
            icon,
        ) = item

        shadow = tk.Frame(
            parent,
            bg=SHADOW,
        )

        shadow.grid(
            row=row,
            column=col,
            padx=6,
            pady=6,
            sticky="nsew",
        )

        card = tk.Frame(
            shadow,
            bg=CARD_BG,
            bd=0,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )

        card.pack(
            fill=tk.BOTH,
            expand=True,
            padx=1,
            pady=1,
        )

        left = tk.Frame(
            card,
            bg=soft_bg,
            width=54,
        )

        left.pack(
            side=tk.RIGHT,
            fill=tk.Y,
        )

        left.pack_propagate(
            False
        )

        tk.Label(
            left,
            text=icon,
            font=(
                "Segoe UI Symbol",
                18,
            ),
            bg=soft_bg,
            fg=accent,
        ).pack(
            expand=True
        )

        body = tk.Frame(
            card,
            bg=CARD_BG,
        )

        body.pack(
            side=tk.RIGHT,
            fill=tk.BOTH,
            expand=True,
            padx=14,
            pady=11,
        )

        tk.Label(
            body,
            text=title,
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            anchor="e",
        ).pack(
            fill=tk.X
        )

        tk.Label(
            body,
            text=value,
            font=FONT_SUBHEADING,
            bg=CARD_BG,
            fg=accent,
            anchor="e",
        ).pack(
            fill=tk.X,
            pady=(2, 0),
        )

        tk.Label(
            body,
            text=subtitle,
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_DARK,
            anchor="e",
            wraplength=220,
        ).pack(
            fill=tk.X,
            pady=(2, 0),
        )

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    def _build_analysis_section(
        self,
        cols,
    ):
        self._section_heading(
            self.content_frame,
            "تحلیل عملکرد و ریسک",
            "نمای کلی از نوع فعالیت‌های نگهداری و تجهیزات پرریسک",
            "📊",
        )

        container = tk.Frame(
            self.content_frame,
            bg=PAGE_BG,
        )

        container.pack(
            fill=tk.X,
            padx=16,
            pady=(0, 2),
        )

        for c in range(cols):

            container.grid_columnconfigure(
                c,
                weight=1,
                uniform="analysis",
            )

        # ---------------------------------------------------------------------
        # One large activity chart spanning the entire dashboard width.
        # ---------------------------------------------------------------------

        shadow = tk.Frame(
            container,
            bg=SHADOW,
        )

        shadow.grid(
            row=0,
            column=0,
            columnspan=cols,
            padx=6,
            pady=6,
            sticky="nsew",
        )

        card = tk.Frame(
            shadow,
            bg=CARD_BG,
            bd=0,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )

        card.pack(
            fill=tk.BOTH,
            expand=True,
            padx=1,
            pady=1,
        )

        tk.Frame(
            card,
            bg=ACCENT_BLUE,
            height=5,
        ).pack(
            fill=tk.X
        )

        title_row = tk.Frame(
            card,
            bg=CARD_BG,
        )

        title_row.pack(
            fill=tk.X,
            padx=16,
            pady=(13, 6),
        )

        tk.Label(
            title_row,
            text="توزیع فعالیت‌های نگهداری",
            font=FONT_SUBHEADING,
            bg=CARD_BG,
            fg=TEXT_DARK,
            anchor="e",
        ).pack(
            side=tk.RIGHT
        )

        tk.Label(
            title_row,
            text=(
                "مقایسه تعداد فعالیت‌های "
                "PM، CM، EM و بازرسی"
            ),
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            anchor="w",
        ).pack(
            side=tk.LEFT
        )

        tk.Frame(
            card,
            bg=CARD_BORDER,
            height=1,
        ).pack(
            fill=tk.X,
            padx=12,
        )

        chart_frame = tk.Frame(
            card,
            bg=CARD_BG,
            height=360,
        )

        chart_frame.pack(
            fill=tk.BOTH,
            expand=True,
            padx=16,
            pady=12,
        )

        self._draw_work_order_bar(
            chart_frame
        )

        # ---------------------------------------------------------------------
        # Risk card
        # ---------------------------------------------------------------------

        risk_shadow = tk.Frame(
            container,
            bg=SHADOW,
        )

        risk_shadow.grid(
            row=1,
            column=0,
            columnspan=cols,
            padx=6,
            pady=6,
            sticky="nsew",
        )

        risk_card = tk.Frame(
            risk_shadow,
            bg=CARD_BG,
            bd=0,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )

        risk_card.pack(
            fill=tk.BOTH,
            expand=True,
            padx=1,
            pady=1,
        )

        self._build_risk_card(
            risk_card,
            accent=ACCENT_ROSE,
        )

    def _draw_work_order_bar(
        self,
        parent,
    ):
        pm = _safe_int(
            self.pm_cm.get(
                "preventive_count",
                0,
            )
        )

        cm = _safe_int(
            self.pm_cm.get(
                "corrective_count",
                0,
            )
        )

        em = _safe_int(
            self.pm_cm.get(
                "emergency_count",
                0,
            )
        )

        insp = _safe_int(
            self.pm_cm.get(
                "inspection_count",
                0,
            )
        )

        values = [
            pm,
            cm,
            em,
            insp,
        ]

        # English labels are intentional:
        # chart/bar terminology stays English as requested.
        labels = [
            "PM",
            "CM",
            "EM",
            "Inspection",
        ]

        colors = [
            ACCENT_TEAL,
            ACCENT_BLUE,
            ACCENT_AMBER,
            ACCENT_PURPLE,
        ]

        fig = Figure(
            figsize=(10.5, 4.1),
            dpi=90,
            facecolor=CARD_BG,
        )

        self._chart_figures.append(
            fig
        )

        ax = fig.add_subplot(
            111
        )

        ax.set_facecolor(
            CARD_BG
        )

        bars = ax.bar(
            labels,
            values,
            color=colors,
            width=0.58,
        )

        max_value = max(
            values or [1]
        )

        label_offset = max(
            0.25,
            max_value * 0.025,
        )

        for bar, value in zip(
            bars,
            values,
        ):
            ax.text(
                bar.get_x()
                + bar.get_width() / 2,
                value + label_offset,
                f"{value:,}",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
                color=TEXT_DARK,
            )

        # English chart text as requested.
        ax.set_ylabel(
            "Count",
            fontsize=9,
            color=TEXT_LIGHT,
        )

        ax.tick_params(
            axis="x",
            labelsize=10,
            colors=TEXT_DARK,
        )

        ax.tick_params(
            axis="y",
            labelsize=8,
            colors=TEXT_LIGHT,
        )

        ax.spines[
            "top"
        ].set_visible(False)

        ax.spines[
            "right"
        ].set_visible(False)

        ax.spines[
            "left"
        ].set_color(
            CARD_BORDER
        )

        ax.spines[
            "bottom"
        ].set_color(
            CARD_BORDER
        )

        ax.yaxis.grid(
            True,
            color=CARD_BORDER,
            linewidth=0.8,
        )

        ax.set_axisbelow(
            True
        )

        # Give the bars breathing room above the numeric labels.
        ax.set_ylim(
            0,
            max(
                1,
                max_value
                + label_offset * 4
            ),
        )

        fig.tight_layout(
            pad=1.0
        )

        canvas = FigureCanvasTkAgg(
            fig,
            parent,
        )

        canvas.draw()

        canvas.get_tk_widget().pack(
            fill=tk.BOTH,
            expand=True,
        )

        canvas._pm_figure = fig

    def _build_risk_card(
        self,
        card,
        accent=ACCENT_ROSE,
    ):
        tk.Frame(
            card,
            bg=accent,
            height=4,
        ).pack(
            fill=tk.X
        )

        title_row = tk.Frame(
            card,
            bg=CARD_BG,
        )

        title_row.pack(
            fill=tk.X,
            padx=16,
            pady=(12, 6),
        )

        tk.Label(
            title_row,
            text="⚠  تجهیزات پرریسک",
            font=FONT_SUBHEADING,
            bg=CARD_BG,
            fg=TEXT_DARK,
            anchor="e",
        ).pack(
            side=tk.RIGHT
        )

        tk.Label(
            title_row,
            text="بر اساس امتیاز ریسک موجود در گزارش‌ها",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
        ).pack(
            side=tk.LEFT
        )

        tk.Frame(
            card,
            bg=CARD_BORDER,
            height=1,
        ).pack(
            fill=tk.X,
            padx=12,
        )

        body = tk.Frame(
            card,
            bg=CARD_BG,
        )

        body.pack(
            fill=tk.X,
            padx=16,
            pady=8,
        )

        body.grid_columnconfigure(
            0,
            weight=1,
        )

        headers = [
            "تجهیز",
            "امتیاز",
            "سطح",
            "وضعیت",
        ]

        for i, title in enumerate(
            headers
        ):

            tk.Label(
                body,
                text=title,
                font=FONT_SMALL,
                bg=CARD_BG,
                fg=TEXT_LIGHT,
                anchor=(
                    "e"
                    if i == 0
                    else "center"
                ),
            ).grid(
                row=0,
                column=i,
                padx=6,
                pady=(0, 6),
                sticky="ew",
            )

            if i > 0:
                body.grid_columnconfigure(
                    i,
                    weight=0,
                    minsize=82,
                )

        if not self.risk_data:

            tk.Label(
                body,
                text=(
                    "مورد پرریسکی برای "
                    "نمایش وجود ندارد."
                ),
                font=FONT_SMALL,
                bg=CARD_BG,
                fg=TEXT_LIGHT,
            ).grid(
                row=1,
                column=0,
                columnspan=4,
                sticky="ew",
                pady=18,
            )

            return

        for row_i, eq in enumerate(
            self.risk_data[:6],
            start=1,
        ):

            score = (
                _safe_float(
                    eq.get(
                        "risk_score",
                        0,
                    )
                )
                if isinstance(
                    eq,
                    dict,
                )
                else 0
            )

            level = (
                _safe_text(
                    eq.get(
                        "risk_level",
                        "",
                    ),
                    "",
                )
                if isinstance(
                    eq,
                    dict,
                )
                else ""
            )

            if (
                score >= 70
                or str(level).upper()
                == "HIGH"
            ):

                row_accent = (
                    ACCENT_ROSE
                )

                soft = DANGER_BG
                fa = "بالا"

            elif (
                score >= 40
                or str(level).upper()
                == "MEDIUM"
            ):

                row_accent = (
                    ACCENT_AMBER
                )

                soft = WARNING_BG
                fa = "متوسط"

            else:

                row_accent = SUCCESS
                soft = SUCCESS_BG
                fa = "پایین"

            bg = (
                CARD_BG
                if row_i % 2
                else CARD_ALT_BG
            )

            name = (
                _safe_text(
                    eq.get(
                        "equipment_name",
                        "",
                    ),
                    "—",
                )
                if isinstance(
                    eq,
                    dict,
                )
                else "—"
            )

            tk.Label(
                body,
                text=name,
                font=FONT_NORMAL,
                bg=bg,
                fg=TEXT_DARK,
                anchor="e",
            ).grid(
                row=row_i,
                column=0,
                padx=6,
                pady=5,
                sticky="ew",
            )

            tk.Label(
                body,
                text=f"{score:.0f}",
                font=FONT_NORMAL,
                bg=bg,
                fg=row_accent,
                anchor="center",
            ).grid(
                row=row_i,
                column=1,
                padx=6,
                pady=5,
                sticky="ew",
            )

            tk.Label(
                body,
                text=fa,
                font=FONT_SMALL,
                bg=soft,
                fg=row_accent,
                padx=8,
                pady=3,
            ).grid(
                row=row_i,
                column=2,
                padx=6,
                pady=5,
                sticky="ew",
            )

            tk.Label(
                body,
                text=(
                    "نیازمند بررسی"
                    if fa != "پایین"
                    else "پایش"
                ),
                font=FONT_SMALL,
                bg=bg,
                fg=TEXT_LIGHT,
                anchor="center",
            ).grid(
                row=row_i,
                column=3,
                padx=6,
                pady=5,
                sticky="ew",
            )

    # =========================================================================
    # RECENT EVENTS
    # =========================================================================

    def _build_events_section(
        self,
        cols,
    ):
        self._section_heading(
            self.content_frame,
            "آخرین رویدادها",
            "نمای فشرده از آخرین دستورکارها، PMها، قطعات و بازرسی‌ها",
            "🕒",
        )

        container = tk.Frame(
            self.content_frame,
            bg=PAGE_BG,
        )

        container.pack(
            fill=tk.X,
            padx=16,
            pady=(0, 2),
        )

        for c in range(cols):

            container.grid_columnconfigure(
                c,
                weight=1,
                uniform="events",
            )

        cards = [
            (
                "📝",
                "دستورکارهای اخیر",
                self.recent_wos,
                self._wo_event_row,
                ACCENT_BLUE,
            ),
            (
                "📅",
                "PMهای نزدیک",
                self.upcoming_pms,
                self._pm_event_row,
                ACCENT_PURPLE,
            ),
            (
                "🔧",
                "قطعات کم‌موجود",
                self.low_stock,
                self._stock_event_row,
                ACCENT_AMBER,
            ),
            (
                "🔍",
                "بازرسی‌های اخیر",
                self.recent_ins,
                self._inspection_event_row,
                ACCENT_CYAN,
            ),
        ]

        for i, (
            icon,
            title,
            items,
            row_fn,
            accent,
        ) in enumerate(
            cards
        ):

            r, c = divmod(
                i,
                cols,
            )

            self._event_card(
                container,
                title,
                icon,
                items,
                row_fn,
                accent,
                r,
                c,
            )

    def _event_card(
        self,
        parent,
        title,
        icon,
        items,
        row_fn,
        accent,
        row,
        col,
    ):
        shadow = tk.Frame(
            parent,
            bg=SHADOW,
        )

        shadow.grid(
            row=row,
            column=col,
            padx=6,
            pady=6,
            sticky="nsew",
        )

        card = tk.Frame(
            shadow,
            bg=CARD_BG,
            bd=0,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )

        card.pack(
            fill=tk.BOTH,
            expand=True,
            padx=1,
            pady=1,
        )

        tk.Frame(
            card,
            bg=accent,
            height=4,
        ).pack(
            fill=tk.X
        )

        hdr = tk.Frame(
            card,
            bg=CARD_BG,
        )

        hdr.pack(
            fill=tk.X,
            padx=14,
            pady=(11, 8),
        )

        tk.Label(
            hdr,
            text=f"{icon}  {title}",
            font=FONT_SUBHEADING,
            bg=CARD_BG,
            fg=TEXT_DARK,
            anchor="e",
        ).pack(
            side=tk.RIGHT
        )

        if items:

            tk.Label(
                hdr,
                text=f"{len(items):,}",
                font=FONT_SMALL,
                bg=accent,
                fg=WHITE,
                padx=7,
                pady=2,
            ).pack(
                side=tk.LEFT
            )

        tk.Frame(
            card,
            bg=CARD_BORDER,
            height=1,
        ).pack(
            fill=tk.X,
            padx=12,
        )

        body = tk.Frame(
            card,
            bg=CARD_BG,
        )

        body.pack(
            fill=tk.BOTH,
            expand=True,
        )

        if not items:

            tk.Label(
                body,
                text="موردی برای نمایش وجود ندارد",
                font=FONT_SMALL,
                bg=CARD_BG,
                fg=TEXT_LIGHT,
            ).pack(
                pady=24
            )

            return

        display_items = items[:6]

        for idx, item in enumerate(
            display_items
        ):

            bg = (
                CARD_BG
                if idx % 2 == 0
                else CARD_ALT_BG
            )

            row_widget = tk.Frame(
                body,
                bg=bg,
            )

            row_widget.pack(
                fill=tk.X
            )

            row_fn(
                row_widget,
                item,
                bg,
            )

            if (
                idx
                < len(display_items) - 1
            ):

                tk.Frame(
                    body,
                    bg=CARD_BORDER,
                    height=1,
                ).pack(
                    fill=tk.X,
                    padx=10,
                )

    def _status_badge(
        self,
        parent,
        status,
    ):
        key = str(
            status or ""
        ).upper()

        bg, fg = STATUS_COLORS.get(
            key,
            (
                MUTED_BG,
                TEXT_LIGHT,
            ),
        )

        text = STATUS_FA.get(
            key,
            _safe_text(
                status,
                "—",
            ),
        )

        tk.Label(
            parent,
            text=text,
            font=FONT_SMALL,
            bg=bg,
            fg=fg,
            padx=8,
            pady=3,
        ).pack(
            side=tk.LEFT,
            padx=10,
            pady=7,
        )

    def _wo_event_row(
        self,
        parent,
        item,
        bg,
    ):
        eq = _safe_text(
            item.get(
                "equipment"
            ),
            "تجهیز نامشخص",
        )

        title = _safe_text(
            item.get(
                "title"
            ),
            "بدون عنوان",
        )

        wo_id = item.get(
            "id",
            "—",
        )

        text = (
            f"WO#{wo_id}"
            f"  ·  "
            f"{eq}"
        )

        tk.Label(
            parent,
            text=text,
            font=FONT_NORMAL,
            bg=bg,
            fg=TEXT_DARK,
            anchor="e",
        ).pack(
            side=tk.RIGHT,
            padx=12,
            pady=(7, 0),
        )

        tk.Label(
            parent,
            text=title,
            font=FONT_SMALL,
            bg=bg,
            fg=TEXT_LIGHT,
            anchor="e",
        ).pack(
            side=tk.RIGHT,
            padx=12,
            pady=(0, 7),
        )

        self._status_badge(
            parent,
            item.get(
                "status"
            ),
        )

    def _pm_event_row(
        self,
        parent,
        item,
        bg,
    ):
        title = _safe_text(
            item.get(
                "title"
            ),
            _safe_text(
                item.get(
                    "equipment_name"
                ),
                "برنامه PM",
            ),
        )

        due = item.get(
            "next_due_dt"
        )

        due_text = (
            to_jalali_date_str(
                due
            )
            if due
            else "—"
        )

        tk.Label(
            parent,
            text=title,
            font=FONT_NORMAL,
            bg=bg,
            fg=TEXT_DARK,
            anchor="e",
        ).pack(
            side=tk.RIGHT,
            padx=12,
            pady=9,
        )

        tk.Label(
            parent,
            text=f"سررسید: {due_text}",
            font=FONT_SMALL,
            bg=bg,
            fg=ACCENT_PURPLE,
            anchor="w",
        ).pack(
            side=tk.LEFT,
            padx=12,
            pady=9,
        )

    def _stock_event_row(
        self,
        parent,
        item,
        bg,
    ):
        name = _safe_text(
            item.get(
                "name"
            ),
            "قطعه",
        )

        current = _safe_float(
            item.get(
                "current",
                0,
            )
        )

        minimum = _safe_float(
            item.get(
                "minimum",
                0,
            )
        )

        pct = min(
            100,
            int(
                _pct(
                    current,
                    maximum(
                        1.0,
                        minimum,
                    ),
                )
            ),
        )

        accent = (
            ACCENT_ROSE
            if pct < 50
            else ACCENT_AMBER
        )

        tk.Label(
            parent,
            text=name,
            font=FONT_NORMAL,
            bg=bg,
            fg=TEXT_DARK,
            anchor="e",
        ).pack(
            side=tk.RIGHT,
            padx=12,
            pady=9,
        )

        tk.Label(
            parent,
            text=(
                f"{current:g}"
                f" / "
                f"{minimum:g}"
            ),
            font=FONT_SMALL,
            bg=bg,
            fg=accent,
        ).pack(
            side=tk.LEFT,
            padx=12,
            pady=9,
        )

    def _inspection_event_row(
        self,
        parent,
        item,
        bg,
    ):
        template = _safe_text(
            item.get(
                "template"
            ),
            "بازرسی",
        )

        eq = _safe_text(
            item.get(
                "equipment"
            ),
            "تجهیز نامشخص",
        )

        result = item.get(
            "result"
        )

        if result == "pass":

            text = "قبول"
            accent = SUCCESS

        elif result == "fail":

            text = "رد"
            accent = ACCENT_ROSE

        elif result == "partial":

            text = "جزئی"
            accent = ACCENT_AMBER

        elif str(item.get("status") or "").lower() in ("completed",):

            text = "بدون نتیجه"
            accent = TEXT_LIGHT

        elif str(item.get("status") or "").lower() in ("cancelled",):

            text = "لغو شده"
            accent = TEXT_LIGHT

        else:

            text = "در حال انجام"
            accent = TEXT_LIGHT

        tk.Label(
            parent,
            text=template,
            font=FONT_NORMAL,
            bg=bg,
            fg=TEXT_DARK,
            anchor="e",
        ).pack(
            side=tk.RIGHT,
            padx=12,
            pady=7,
        )

        tk.Label(
            parent,
            text=eq,
            font=FONT_SMALL,
            bg=bg,
            fg=TEXT_LIGHT,
            anchor="e",
        ).pack(
            side=tk.RIGHT,
            padx=4,
            pady=7,
        )

        tk.Label(
            parent,
            text=text,
            font=FONT_SMALL,
            bg=bg,
            fg=accent,
            anchor="w",
        ).pack(
            side=tk.LEFT,
            padx=12,
            pady=7,
        )

    # =========================================================================
    # QUICK ACTIONS
    # =========================================================================

    def _build_quick_actions(
        self,
        cols,
    ):
        self._section_heading(
            self.content_frame,
            "عملیات سریع",
            "شروع سریع رایج‌ترین عملیات‌های نگهداری",
            "⚡",
        )

        container = tk.Frame(
            self.content_frame,
            bg=PAGE_BG,
        )

        container.pack(
            fill=tk.X,
            padx=16,
            pady=(0, 22),
        )

        for c in range(cols):

            container.grid_columnconfigure(
                c,
                weight=1,
                uniform="quick",
            )

        actions = [
            (
                "➕",
                "دستورکار جدید",
                "work_orders",
                ACCENT_BLUE,
            ),
            (
                "📄",
                "حکم درخواست تعمیرات",
                "repair_request",
                ACCENT_CYAN,
            ),
            (
                "📅",
                "برنامه PM جدید",
                "pm_schedule",
                ACCENT_PURPLE,
            ),
            (
                "⚙",
                "افزودن تجهیز",
                "equipment",
                NAVY,
            ),
            (
                "🔧",
                "مدیریت قطعات",
                "spare_parts",
                ACCENT_TEAL,
            ),
            (
                "🔍",
                "بازرسی جدید",
                "inspection",
                ACCENT_AMBER,
            ),
            (
                "⏱",
                "ثبت ساعات کارکرد",
                "machine_hours",
                ACCENT_BLUE,
            ),
            (
                "📈",
                "گزارشات",
                "reports",
                NAVY,
            ),
        ]

        for i, action in enumerate(
            actions
        ):

            r, c = divmod(
                i,
                cols,
            )

            self._quick_button(
                container,
                action,
                r,
                c,
            )

    def _quick_button(
        self,
        parent,
        action,
        row,
        col,
    ):
        icon, title, view_key, accent = (
            action
        )

        shadow = tk.Frame(
            parent,
            bg=SHADOW,
        )

        shadow.grid(
            row=row,
            column=col,
            padx=6,
            pady=5,
            sticky="nsew",
        )

        button_shell = tk.Frame(
            shadow,
            bg=accent,
        )

        button_shell.pack(
            fill=tk.BOTH,
            expand=True,
            padx=1,
            pady=1,
        )

        button = tk.Button(
            button_shell,
            text=f"{icon}  {title}",
            command=lambda key=view_key: (
                self._navigate(key)
            ),
            bg=CARD_ALT_BG,
            fg=TEXT_DARK,
            activebackground=accent,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            anchor="e",
            padx=14,
            pady=12,
        )

        button.pack(
            fill=tk.BOTH,
            expand=True,
        )

        def enter(
            _event=None
        ):
            button.configure(
                bg=accent,
                fg=WHITE,
            )

        def leave(
            _event=None
        ):
            button.configure(
                bg=CARD_ALT_BG,
                fg=TEXT_DARK,
            )

        button.bind(
            "<Enter>",
            enter,
        )

        button.bind(
            "<Leave>",
            leave,
        )

    def _navigate(
        self,
        view_key,
    ):
        root = self.winfo_toplevel()

        show_view = getattr(
            root,
            "_show_view",
            None,
        )

        if callable(show_view):
            show_view(
                view_key
            )

    # =========================================================================
    # ERROR
    # =========================================================================

    def _render_error(
        self,
        exc,
    ):
        self._clear_dashboard_widgets()

        box = tk.Frame(
            self.content_frame,
            bg=PAGE_BG,
        )

        box.pack(
            fill=tk.BOTH,
            expand=True,
            padx=22,
            pady=22,
        )

        shadow = tk.Frame(
            box,
            bg=SHADOW,
        )

        shadow.pack(
            fill=tk.BOTH,
            expand=True,
        )

        card = tk.Frame(
            shadow,
            bg=CARD_BG,
            bd=0,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )

        card.pack(
            fill=tk.BOTH,
            expand=True,
            padx=1,
            pady=1,
        )

        tk.Frame(
            card,
            bg=RED,
            height=5,
        ).pack(
            fill=tk.X
        )

        tk.Label(
            card,
            text="خطا در بروزرسانی داشبورد",
            font=FONT_TITLE,
            bg=CARD_BG,
            fg=RED,
        ).pack(
            pady=(80, 12)
        )

        tk.Label(
            card,
            text=str(exc),
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            wraplength=800,
            justify="center",
        ).pack(
            padx=30,
            pady=10,
        )

        tk.Button(
            card,
            text="تلاش مجدد",
            command=self._refresh_all,
            bg=NAVY,
            fg=WHITE,
            activebackground=NAVY_LIGHT,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=24,
            pady=10,
        ).pack(
            pady=22
        )


# =============================================================================
# SMALL DEPENDENCY-FREE HELPER
# =============================================================================

def maximum(
    a,
    b,
):
    return (
        a
        if a >= b
        else b
    )