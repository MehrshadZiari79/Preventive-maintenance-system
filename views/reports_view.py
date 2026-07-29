# views/reports_view.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
from datetime import datetime, timedelta
import threading
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import json
from database.models import Equipment
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import func
from database.models import ProductionLog
from database.report_repository import ReportRepository
from database.equipment_repository import EquipmentRepository
from database.work_order import WorkOrder, WorkOrderType, WorkOrderStatus
from database.work_order_repository import WorkOrderRepository
from database.spare_parts_repository import SparePartsRepository
from database.db import SessionLocal
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

# ── Design tokens ─────────────────────────────────────────────────────────
CARD_BG      = "#FFFFFF"
CARD_BORDER  = "#E8ECF0"
SECTION_BG   = "#F4F6F9"
HEADER_H     = 72
ACCENT_TEAL  = "#0D9488"
ACCENT_AMBER = "#D97706"
ACCENT_ROSE  = "#DC2626"
ACCENT_BLUE  = "#1D4ED8"
ACCENT_PURP  = "#7C3AED"
STRIP_H      = 4

FONT_SUBHEADING = ("Tahoma", 11, "bold")

STATUS_FA = {
    "operational": "عملیاتی",
    "maintenance": "در تعمیر",
    "breakdown":   "خراب",
    "inactive":    "غیرفعال",
}

WO_TYPE_FA = {
    "PREVENTIVE": "پیشگیرانه", "CORRECTIVE": "اصلاحی",
    "EMERGENCY":  "اضطراری",   "INSPECTION": "بازرسی", "PM": "PM",
}
WO_STATUS_FA = {
    "PENDING":          "در انتظار",
    "IN_PROGRESS":      "در حال انجام",
    "FINISH_REQUESTED": "درخواست اتمام",
    "APPROVED":         "تایید شده",
    "REJECTED":         "رد شده",
    "PENDING_APPROVAL": "در انتظار تأیید",
}


def _ttk_styles():
    s = ttk.Style()
    s.configure("Report.Treeview",
                 background=CARD_BG, fieldbackground=CARD_BG,
                 foreground=TEXT_DARK, rowheight=28, font=("Tahoma", 9))
    s.configure("Report.Treeview.Heading",
                 background=NAVY, foreground=WHITE,
                 font=("Tahoma", 9, "bold"), relief="flat")
    s.map("Report.Treeview.Heading", background=[("active", NAVY_LIGHT)])
    s.map("Report.Treeview", background=[("selected", NAVY)],
          foreground=[("selected", WHITE)])
    s.configure("Report.TNotebook", background=SECTION_BG, tabmargins=[0, 0, 0, 0])
    s.configure("Report.TNotebook.Tab", background=SECTION_BG,
                 foreground=TEXT_LIGHT, font=("Tahoma", 9), padding=[16, 8])
    s.map("Report.TNotebook.Tab", background=[("selected", CARD_BG)],
          foreground=[("selected", NAVY)],
          font=[("selected", ("Tahoma", 9, "bold"))])


class ReportsView(ttk.Frame):
    def __init__(self, parent, current_user):
        super().__init__(parent)
        if current_user["role"] not in ["admin", "manager", "technician"]:
            messagebox.showerror("خطا", "دسترسی غیرمجاز. فقط مدیران و تکنسین‌ها می‌توانند گزارشات را مشاهده کنند.", parent=parent)
            self.destroy()
            return
        self.current_user = current_user
        self.report_repo  = ReportRepository(SessionLocal)
        self.eq_repo      = EquipmentRepository(SessionLocal)
        self._loading     = False
        self._sort_col    = None
        self._sort_asc    = True

        # Lazy loading flags & cache
        self._tabs_loaded = {
            "overview": False,
            "equipment": False,
            "kpi": False,
            "cost": False,
            "tech": False,
            "failure": False,
        }

        _ttk_styles()
        self._build_ui()
        # Load only the overview tab initially
        self._load_overview_tab()

    # ── Helpers ───────────────────────────────────────────────────────────
    def _card(self, parent, padx=12, pady=6, fill=tk.BOTH, expand=True):
        shadow = tk.Frame(parent, bg=CARD_BORDER)
        shadow.pack(fill=fill, expand=expand, padx=padx, pady=pady)
        inner = tk.Frame(shadow, bg=CARD_BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        return inner

    def _card_header(self, card, title, icon=""):
        hdr = tk.Frame(card, bg=CARD_BG, pady=10)
        hdr.pack(fill=tk.X, padx=14)
        tk.Label(hdr, text=f"{icon}  {title}" if icon else title,
                 font=FONT_SUBHEADING, bg=CARD_BG, fg=TEXT_DARK).pack(side=tk.RIGHT)
        tk.Frame(card, bg=CARD_BORDER, height=1).pack(fill=tk.X, padx=10)

    def _section_label(self, parent, text, icon=""):
        row = tk.Frame(parent, bg=SECTION_BG)
        row.pack(fill=tk.X, padx=16, pady=(14, 4))
        tk.Label(row, text=f"{icon}  {text}" if icon else text,
                 font=FONT_HEADING, bg=SECTION_BG, fg=TEXT_DARK).pack(side=tk.RIGHT)

    def _styled_tree(self, parent, columns, col_defs, height=15, sort_callback=None):
        tree = ttk.Treeview(parent, columns=columns, show="headings",
                            height=height, style="Report.Treeview")
        for col, text, width in col_defs:
            tree.heading(col, text=text,
                         command=lambda c=col: sort_callback(c) if sort_callback else None)
            tree.column(col, width=width, anchor="center")
        tree.tag_configure("odd",  background=SECTION_BG)
        tree.tag_configure("even", background=CARD_BG)

        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        return tree

    def _sort_column(self, col):
        numeric_cols = {"total_wo", "completed", "pm", "cm", "em", "mtbf", "mttr",
                        "availability", "oee", "downtime", "total_cost"}
        is_numeric = col in numeric_cols

        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True

        items = []
        for k in self.equipment_tree.get_children(""):
            val = self.equipment_tree.set(k, col)
            if is_numeric:
                try:
                    numeric_val = float(val.replace(",", "").replace("N/A", "0"))
                except:
                    numeric_val = 0.0
                items.append((numeric_val, k))
            else:
                items.append((val, k))
        items.sort(key=lambda x: x[0], reverse=not self._sort_asc)
        for index, (_, k) in enumerate(items):
            self.equipment_tree.move(k, "", index)

    def _fig(self, w=10, h=5):
        fig = Figure(figsize=(w, h), dpi=88, facecolor=CARD_BG)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(CARD_BG)
        return fig, ax

    def _embed_chart(self, fig, parent):
        cv = FigureCanvasTkAgg(fig, parent)
        cv.draw()
        cv.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _kpi_card(self, parent, title, value, subtitle, color, icon, row, col):
        shadow = tk.Frame(parent, bg=CARD_BORDER)
        shadow.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        card = tk.Frame(shadow, bg=CARD_BG)
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        tk.Frame(card, bg=color, height=STRIP_H).pack(fill=tk.X)
        inner = tk.Frame(card, bg=CARD_BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        top = tk.Frame(inner, bg=CARD_BG)
        top.pack(fill=tk.X)
        tk.Label(top, text=icon, font=("Tahoma", 14), bg=CARD_BG, fg=color).pack(side=tk.RIGHT)
        tk.Label(top, text=title, font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side=tk.RIGHT, padx=(0, 4))
        tk.Label(inner, text=str(value), font=("Tahoma", 22, "bold"),
                 bg=CARD_BG, fg=color).pack(anchor="center", pady=(6, 2))
        tk.Label(inner, text=subtitle, font=FONT_SMALL, bg=CARD_BG,
                 fg=TEXT_LIGHT, wraplength=160, justify="center").pack(anchor="center")

    # ── Main UI ───────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_filter_bar()
        self._build_notebook()
        self._add_export_buttons()

    def _build_header(self):
        hdr = tk.Frame(self, bg=NAVY, height=HEADER_H)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        right = tk.Frame(hdr, bg=NAVY)
        right.pack(side=tk.RIGHT, padx=24, fill=tk.Y)
        tk.Label(right, text="📈", font=("Tahoma", 20), bg=NAVY, fg=WHITE).pack(side=tk.RIGHT, pady=16)
        col = tk.Frame(right, bg=NAVY)
        col.pack(side=tk.RIGHT, padx=(0, 10), fill=tk.Y)
        tk.Label(col, text="گزارشات و تحلیل‌های پیشرفته",
                 font=FONT_TITLE, bg=NAVY, fg=WHITE).pack(anchor="e", pady=(14, 0))
        tk.Label(col, text="داده‌های عملکردی سیستم نگهداری",
                 font=FONT_SMALL, bg=NAVY, fg=NAVY_LIGHT).pack(anchor="e")
        tk.Frame(self, bg=CARD_BORDER, height=1).pack(fill=tk.X)

    def _build_filter_bar(self):
        bar_outer = tk.Frame(self, bg=CARD_BG)
        bar_outer.pack(fill=tk.X)
        tk.Frame(bar_outer, bg=CARD_BORDER, height=1).pack(fill=tk.X, side=tk.BOTTOM)
        bar = tk.Frame(bar_outer, bg=CARD_BG)
        bar.pack(padx=20, pady=10, anchor="e")

        tk.Label(bar, text="از تاریخ:", font=FONT_SMALL,
                 bg=CARD_BG, fg=TEXT_LIGHT).pack(side=tk.RIGHT, padx=(0, 4))
        self.start_date = DateEntry(bar, width=12, date_pattern='yyyy-mm-dd',
                                    font=FONT_SMALL, background=NAVY, foreground=WHITE,
                                    headersbackground=NAVY, headersforeground=WHITE)
        self.start_date.set_date(datetime.now() - timedelta(days=30))
        self.start_date.pack(side=tk.RIGHT, padx=(0, 16))

        tk.Label(bar, text="تا تاریخ:", font=FONT_SMALL,
                 bg=CARD_BG, fg=TEXT_LIGHT).pack(side=tk.RIGHT, padx=(0, 4))
        self.end_date = DateEntry(bar, width=12, date_pattern='yyyy-mm-dd',
                                  font=FONT_SMALL, background=NAVY, foreground=WHITE,
                                  headersbackground=NAVY, headersforeground=WHITE)
        self.end_date.set_date(datetime.now())
        self.end_date.pack(side=tk.RIGHT, padx=(0, 16))

        refresh_btn = tk.Button(
            bar, text="🔄  بروزرسانی", font=FONT_SMALL,
            bg=NAVY, fg=WHITE, activebackground=NAVY_LIGHT,
            relief="flat", cursor="hand2", padx=14, pady=6,
            command=self._refresh_all)
        refresh_btn.pack(side=tk.RIGHT)

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self, style="Report.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Create frames and store tags
        self.overview_frame  = tk.Frame(self.notebook, bg=SECTION_BG)
        self.equipment_frame = tk.Frame(self.notebook, bg=SECTION_BG)
        self.kpi_frame       = tk.Frame(self.notebook, bg=SECTION_BG)
        self.cost_frame      = tk.Frame(self.notebook, bg=SECTION_BG)
        self.tech_frame      = tk.Frame(self.notebook, bg=SECTION_BG)
        self.failure_frame   = tk.Frame(self.notebook, bg=SECTION_BG)

        tabs = [
            (self.overview_frame,  "📊  داشبورد کلی", "overview"),
            (self.equipment_frame, "🛠️  عملکرد تجهیزات", "equipment"),
            (self.kpi_frame,       "📈  تحلیل KPI", "kpi"),
            (self.cost_frame,      "💰  تحلیل هزینه", "cost"),
            (self.tech_frame,      "👨‍🔧  عملکرد تکنسین‌ها", "tech"),
            (self.failure_frame,   "⚠️  تحلیل خرابی‌ها", "failure"),
        ]
        for frame, label, tag in tabs:
            self.notebook.add(frame, text=label)
            frame._tab_tag = tag
            # Add a loading label
            loading = tk.Label(frame, text="⏳ در حال بارگذاری...", font=FONT_HEADING,
                               bg=SECTION_BG, fg=TEXT_LIGHT)
            loading.pack(expand=True)
            frame._loading_label = loading

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _add_export_buttons(self):
        for frame, title in [
            (self.overview_frame,  "داشبورد کلی"),
            (self.equipment_frame, "عملکرد تجهیزات"),
            (self.kpi_frame,       "تحلیل KPI"),
            (self.cost_frame,      "تحلیل هزینه"),
            (self.tech_frame,      "عملکرد تکنسین‌ها"),
            (self.failure_frame,   "تحلیل خرابی‌ها"),
        ]:
            toolbar = tk.Frame(frame, bg=CARD_BG)
            toolbar.pack(fill=tk.X)
            tk.Frame(toolbar, bg=CARD_BORDER, height=1).pack(fill=tk.X, side=tk.BOTTOM)
            tk.Button(
                toolbar, text="📎  خروجی Excel", font=FONT_SMALL,
                bg=ACCENT_TEAL, fg=WHITE, activebackground=NAVY_LIGHT,
                relief="flat", cursor="hand2", padx=12, pady=6,
                command=lambda f=frame, t=title: self._export_tab_to_excel(f, t)
            ).pack(side=tk.LEFT, padx=12, pady=8)

    # ── Lazy loading ─────────────────────────────────────────────────────
    def _load_overview_tab(self):
        """Load overview immediately (it's the first tab)."""
        self._load_tab_data("overview")

    def _on_tab_changed(self, event):
        selected = self.notebook.select()
        if not selected:
            return
        frame = self.notebook.nametowidget(selected)
        tag = getattr(frame, '_tab_tag', None)
        if tag and not self._tabs_loaded.get(tag, False):
            self._load_tab_data(tag)

    def _load_tab_data(self, tag):
        if self._tabs_loaded.get(tag, False):
            return
        # Mark as loading (prevent duplicate)
        self._tabs_loaded[tag] = True

        frame = getattr(self, f"{tag}_frame", None)
        if not frame:
            return

        # Show loading label
        loading = getattr(frame, '_loading_label', None)
        if loading:
            loading.pack(expand=True)

        # Remove any previously built content (keep only loading label)
        for child in frame.winfo_children():
            if child != loading:
                child.destroy()

        # Start background thread
        def load_thread():
            try:
                start = self.start_date.get_date()
                end   = self.end_date.get_date()
                if tag == "overview":
                    data = {
                        "summary": self.report_repo.get_kpi_summary(start, end),
                        "backlog": self.report_repo.get_backlog_analysis(start, end),
                        "rejection": self.report_repo.get_rejection_percentage(start, end),
                        "delay": self.report_repo.get_delay_summary(start, end),
                    }
                elif tag == "equipment":
                    data = self.report_repo.get_all_equipment_performance(start, end)
                elif tag == "kpi":
                    data = {
                        "trend": self.report_repo.get_monthly_trends(6),
                        "compliance": self.report_repo.get_schedule_compliance(start, end),
                        "risk": self.report_repo.get_equipment_risk_score(),
                        "pm_cm": self.report_repo.get_pm_cm_ratio(start, end),
                    }
                elif tag == "cost":
                    data = self.report_repo.get_cost_analysis(start, end)
                elif tag == "tech":
                    data = self.report_repo.get_technician_performance(start, end)
                elif tag == "failure":
                    data = self.report_repo.get_top_failure_modes(start, end, limit=50)
                else:
                    data = None
                self.after(0, lambda: self._render_tab(tag, data))
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda: self._show_tab_error(tag, error_msg))

        threading.Thread(target=load_thread, daemon=True).start()

    def _render_tab(self, tag, data):
        frame = getattr(self, f"{tag}_frame", None)
        if not frame:
            return
        # Remove loading label
        loading = getattr(frame, '_loading_label', None)
        if loading:
            loading.destroy()
            delattr(frame, '_loading_label')

        # Render based on tag
        if tag == "overview":
            self._render_overview(frame, data)
        elif tag == "equipment":
            self._render_equipment(frame, data)
        elif tag == "kpi":
            self._render_kpi(frame, data)
        elif tag == "cost":
            self._render_cost(frame, data)
        elif tag == "tech":
            self._render_tech(frame, data)
        elif tag == "failure":
            self._render_failure(frame, data)

        self._tabs_loaded[tag] = True

    def _show_tab_error(self, tag, error):
        frame = getattr(self, f"{tag}_frame", None)
        if not frame:
            return
        loading = getattr(frame, '_loading_label', None)
        if loading:
            loading.config(text=f"❌ خطا: {error}", fg=ACCENT_ROSE)

    # ── Render methods ──────────────────────────────────────────────────
    def _render_overview(self, parent, data):
        summary = data["summary"]
        backlog = data["backlog"]
        rejection = data["rejection"]
        delay = data["delay"]

        self._section_label(parent, "شاخص‌های اصلی عملکرد", "📌")
        g1 = tk.Frame(parent, bg=SECTION_BG)
        g1.pack(fill=tk.X, padx=16, pady=(0, 4))
        total = summary.get('total_work_orders', 0)
        done  = summary.get('completed_work_orders', 0)
        prog  = summary.get('in_progress_work_orders', 0)
        overdue = summary.get('overdue_work_orders', 0)
        comp_pct = (done / max(1, total) * 100) if total else 0

        for title, val, sub, color, icon, col in [
            ("کل دستورات کار", total, "تمام دستورات ثبت شده", ACCENT_BLUE, "📋", 0),
            ("تکمیل شده", done, f"{comp_pct:.1f}٪ از کل", SUCCESS, "✅", 1),
            ("در حال انجام", prog, "دستورات فعال", ACCENT_AMBER, "🔄", 2),
            ("معوق", overdue, "نیاز به توجه فوری", ACCENT_ROSE, "🚨", 3),
            ("درصد رد کارها", f"{rejection['percentage']:.1f}٪",
             f"{rejection['rejected']} از {rejection['total']}", ACCENT_ROSE, "🚫", 4),
            ("مجموع تأخیر", f"{delay['total_minutes']} دقیقه",
             f"{delay['delayed_count']} کار دارای تأخیر", ACCENT_AMBER, "⏳", 5),
        ]:
            self._kpi_card(g1, title, val, sub, color, icon, 0, col)
            g1.columnconfigure(col, weight=1)

        g2 = tk.Frame(parent, bg=SECTION_BG)
        g2.pack(fill=tk.X, padx=16, pady=(0, 4))
        total_eq = summary.get('total_equipment', 0)
        op_eq = summary.get('operational_equipment', 0)
        avg_t = summary.get('avg_completion_time_hours', 0)
        pm_comp = summary.get('pm_compliance_rate', 0)
        op_pct = (op_eq / max(1, total_eq) * 100) if total_eq else 0

        for title, val, sub, color, icon, col in [
            ("کل تجهیزات", total_eq, "تجهیزات ثبت شده", ACCENT_PURP, "⚙️", 0),
            ("عملیاتی", op_eq, f"{op_pct:.1f}٪ آماده", ACCENT_TEAL, "✅", 1),
            ("میانگین زمان تعمیر", f"{avg_t:.1f} ساعت", "میانگین تعمیر", "#795548", "⏱️", 2),
            ("انطباق PM", f"{pm_comp:.1f}٪", "نگهداری پیشگیرانه", NAVY, "🎯", 3),
        ]:
            self._kpi_card(g2, title, val, sub, color, icon, 0, col)
            g2.columnconfigure(col, weight=1)

        self._section_label(parent, "تحلیل کارهای معوق", "📂")
        g3 = tk.Frame(parent, bg=SECTION_BG)
        g3.pack(fill=tk.X, padx=16, pady=(0, 16))
        for title, val, sub, color, icon, col in [
            ("در انتظار", backlog.get('pending', 0), "دستورات معلق", "#FFC107", "⏳", 0),
            ("در حال انجام", backlog.get('in_progress', 0), "در دست اقدام", "#03A9F4", "🔄", 1),
            ("سررسید گذشته", backlog.get('overdue', 0), "نیاز به اقدام فوری", "#E91E63", "❗", 2),
            ("کل معوقات", backlog.get('total_backlog', 0), "مجموع کارهای باز", "#673AB7", "📋", 3),
        ]:
            self._kpi_card(g3, title, val, sub, color, icon, 0, col)
            g3.columnconfigure(col, weight=1)

    def _render_equipment(self, parent, performance_data):
        card = self._card(parent, padx=12, pady=10)
        self._card_header(card, "عملکرد تجهیزات", "🛠️")

        filter_row = tk.Frame(card, bg=CARD_BG)
        filter_row.pack(fill=tk.X, padx=10, pady=(5, 0))

        tk.Label(filter_row, text="🔍  جستجو:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).pack(side=tk.RIGHT, padx=(0,4))
        self.eq_search_var = tk.StringVar()
        self.eq_search_var.trace("w", lambda *_: self._refresh_equipment_table())
        tk.Entry(filter_row, textvariable=self.eq_search_var, font=FONT_NORMAL, width=18,
                 relief="solid", bd=1).pack(side=tk.RIGHT, ipady=4)

        tk.Label(filter_row, text="دسته:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).pack(side=tk.RIGHT, padx=(16,4))
        self.eq_cat_var = tk.StringVar(value="همه")
        categories = ["همه"] + self.eq_repo.get_categories()
        cat_combo = ttk.Combobox(filter_row, textvariable=self.eq_cat_var, values=categories,
                                 state="readonly", font=FONT_NORMAL, width=14)
        cat_combo.pack(side=tk.RIGHT, ipady=2)
        cat_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_equipment_table())

        tree_frame = tk.Frame(card, bg=CARD_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ("id", "name", "status", "total_wo", "completed", "pm", "cm", "em",
                   "mtbf", "mttr", "availability", "oee", "downtime", "total_cost")
        col_defs = [
            ("id", "شناسه", 50), ("name", "نام تجهیز", 200),
            ("status", "وضعیت", 100), ("total_wo", "کل WO", 70),
            ("completed", "تکمیل شده", 90), ("pm", "PM", 55),
            ("cm", "CM", 55), ("em", "EM", 55),
            ("mtbf", "MTBF (h)", 90), ("mttr", "MTTR (h)", 90),
            ("availability", "دسترسی٪", 80), ("oee", "OEE٪", 70),
            ("downtime", "توقف (h)", 90), ("total_cost", "هزینه کل (ریال)", 140),
        ]
        self.equipment_tree = self._styled_tree(tree_frame, columns, col_defs, height=18,
                                                sort_callback=self._sort_column)
        self.equipment_tree.bind("<Double-1>", self._open_equipment_detail)

        # Store data for filtering – ensure it's a list of dicts
        if performance_data is None:
            performance_data = []
        self._equipment_data = performance_data
        self._refresh_equipment_table()

    def _refresh_equipment_table(self):
        self.equipment_tree.delete(*self.equipment_tree.get_children())
        data = self._equipment_data
        if not data:
            return

        search = self.eq_search_var.get().strip().lower() if hasattr(self, 'eq_search_var') else ""
        category = self.eq_cat_var.get() if hasattr(self, 'eq_cat_var') else "همه"

        # Filter by search and category
        filtered = []
        for eq in data:
            # eq is a dict; if not, skip
            if not isinstance(eq, dict):
                continue
            name = eq.get('equipment_name', '').lower()
            if search and search not in name:
                continue
            if category != "همه":
                # Fetch category map if not already cached
                if not hasattr(self, '_eq_category_map'):
                    session = SessionLocal()
                    try:
                        eqs = session.query(Equipment).all()
                        self._eq_category_map = {e.id: e.category for e in eqs}
                    finally:
                        session.close()
                if self._eq_category_map.get(eq.get('equipment_id')) != category:
                    continue
            filtered.append(eq)

        for i, eq in enumerate(filtered):
            # Calculate total cost (approximate) – we'll just set 0 or use a placeholder
            total_cost = 0.0  # You can compute if needed; for speed, leave as 0
            tag = "even" if i % 2 == 0 else "odd"
            self.equipment_tree.insert("", tk.END, tags=(tag,), values=(
                eq.get('equipment_id', 0),
                eq.get('equipment_name', '—'),
                STATUS_FA.get(eq.get('equipment_status', ''), eq.get('equipment_status', '—')),
                eq.get('total_work_orders', 0),
                eq.get('completed_work_orders', 0),
                eq.get('pm_work_orders', 0),
                eq.get('cm_work_orders', 0),
                eq.get('em_work_orders', 0),
                eq.get('mtbf_hours', 0),
                eq.get('mttr_hours', 0),
                eq.get('availability', 0),
                eq.get('oee', 0),
                eq.get('total_downtime_hours', 0),
                f"{total_cost:,.0f}",
            ))

    def _render_kpi(self, parent, data):
        trend_data = data["trend"]
        compliance = data["compliance"]
        risk_data = data["risk"]
        pm_cm = data["pm_cm"]

        trend_card = self._card(parent)
        self._card_header(trend_card, "روند ماهانه PM / CM / EM", "📅")
        if trend_data and any(item['count'] > 0 for item in trend_data):
            months_dict = {}
            for item in trend_data:
                key = f"{item['year']}-{item['month']:02d}"
                if key not in months_dict: months_dict[key] = {'PM':0,'CM':0,'EM':0}
                typ = item['type']
                if typ in ('PREVENTIVE','PM'): months_dict[key]['PM'] += item['count']
                elif typ == 'CORRECTIVE': months_dict[key]['CM'] += item['count']
                elif typ == 'EMERGENCY': months_dict[key]['EM'] += item['count']
            sorted_months = sorted(months_dict.keys())
            pm_counts = [months_dict[m]['PM'] for m in sorted_months]
            cm_counts = [months_dict[m]['CM'] for m in sorted_months]
            em_counts = [months_dict[m]['EM'] for m in sorted_months]
            fig1, ax1 = self._fig(10, 4)
            x = np.arange(len(sorted_months)); w = 0.25
            ax1.bar(x-w, pm_counts, w, label='PM', color=ACCENT_TEAL, edgecolor='white')
            ax1.bar(x, cm_counts, w, label='CM', color=ACCENT_ROSE, edgecolor='white')
            ax1.bar(x+w, em_counts, w, label='EM', color=ACCENT_AMBER, edgecolor='white')
            ax1.set_xticks(x); ax1.set_xticklabels(sorted_months, rotation=35, ha='right', fontsize=8)
            ax1.set_ylabel('Count', fontsize=8, color=TEXT_LIGHT)
            ax1.set_title('Monthly PM / CM / EM Comparison', fontsize=11, color=NAVY, pad=8)
            ax1.legend(fontsize=8); ax1.yaxis.grid(True, color=CARD_BORDER, linewidth=0.8)
            ax1.set_axisbelow(True); ax1.spines['top'].set_visible(False); ax1.spines['right'].set_visible(False)
            ax1.tick_params(colors=TEXT_LIGHT, labelsize=8); fig1.tight_layout(pad=1)
            self._embed_chart(fig1, trend_card)
        else:
            tk.Label(trend_card, text="داده‌ای برای نمایش ماهانه وجود ندارد.",
                     font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_LIGHT).pack(pady=20)

        comp_card = self._card(parent)
        self._card_header(comp_card, "انطباق برنامه (به موقع / دیرکرد)", "🎯")
        fig2, ax2 = self._fig(7, 3.5)
        if compliance.get('on_time',0) > 0 or compliance.get('late',0) > 0:
            ax2.pie([compliance['on_time'], compliance['late']], labels=['On Time','Late'],
                    autopct='%1.1f%%', colors=[SUCCESS, ACCENT_ROSE], startangle=90,
                    wedgeprops=dict(linewidth=1.5, edgecolor='white'))
            ax2.set_title(f"Schedule Compliance: {compliance.get('compliance_rate',0):.1f}%", fontsize=11, color=NAVY)
        else:
            ax2.text(0.5,0.5,'No Data', ha='center', va='center', color=TEXT_LIGHT); ax2.set_axis_off()
        fig2.tight_layout(pad=0.5); self._embed_chart(fig2, comp_card)

        if risk_data:
            risk_card = self._card(parent)
            self._card_header(risk_card, "تجهیزات با ریسک بالا", "⚠️")
            rf = tk.Frame(risk_card, bg=CARD_BG); rf.pack(fill=tk.X, padx=10, pady=8)
            risk_tree = self._styled_tree(rf,
                ("name","risk","level","failures","downtime"),
                [("name","تجهیز",130),("risk","امتیاز ریسک",110),("level","سطح ریسک",90),
                 ("failures","تعداد خرابی",100),("downtime","متوسط توقف (h)",120)], height=8)
            risk_tree.tag_configure("high", foreground=ACCENT_ROSE)
            risk_tree.tag_configure("medium", foreground=ACCENT_AMBER)
            risk_tree.tag_configure("low", foreground=SUCCESS)
            for item in risk_data[:10]:
                score = item.get('risk_score',0)
                level = item.get('risk_level','')
                tag = "high" if score >= 70 or level == "HIGH" else "medium" if score >= 40 or level == "MEDIUM" else "low"
                lv = "بالا" if tag=="high" else "متوسط" if tag=="medium" else "پایین"
                risk_tree.insert("", tk.END, tags=(tag,), values=(
                    item.get('equipment_name', '—'),
                    f"{score:.1f}", lv,
                    item.get('failure_count', 0),
                    f"{item.get('avg_downtime_hours', 0):.1f}",
                ))

    def _render_cost(self, parent, cost_data):
        cost_card = self._card(parent)
        self._card_header(cost_card, "توزیع هزینه‌ها", "💰")
        if cost_data.get('breakdown') and len(cost_data['breakdown']) > 0:
            fig, ax = self._fig(8, 5)
            labels = [d['type'] for d in cost_data['breakdown']]
            sizes  = [d['total_cost'] for d in cost_data['breakdown']]
            pal = [ACCENT_BLUE, ACCENT_TEAL, ACCENT_AMBER, ACCENT_PURP, ACCENT_ROSE]
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90,
                   colors=pal[:len(labels)], wedgeprops=dict(linewidth=1.5, edgecolor='white'))
            total = cost_data.get('total_cost', 0)
            ax.set_title(f"Cost Distribution   (Total: {total:,.0f} Rials)", fontsize=11, color=NAVY, pad=10)
            fig.tight_layout(pad=0.5); self._embed_chart(fig, cost_card)
        else:
            tk.Label(cost_card, text="داده‌ای برای نمایش وجود ندارد",
                     font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_LIGHT).pack(pady=40)

    def _render_tech(self, parent, tech_data):
        tc = self._card(parent); self._card_header(tc, "عملکرد تکنسین‌ها", "👨‍🔧")
        tf = tk.Frame(tc, bg=CARD_BG); tf.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        if not tech_data:
            tk.Label(tf, text="داده‌ای برای نمایش وجود ندارد",
                     font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_LIGHT).pack(pady=40)
            return
        tree = self._styled_tree(tf,
            ("name","total","completed","rate","avg_time"),
            [("name","تکنسین",200),("total","کل وظایف",100),("completed","تکمیل شده",120),
             ("rate","نرخ تکمیل٪",120),("avg_time","میانگین زمان (h)",150)], height=15)
        for i, item in enumerate(tech_data):
            tag = "even" if i % 2 == 0 else "odd"
            tree.insert("", tk.END, tags=(tag,), values=(
                item.get('technician_name','—'), item.get('total_tasks',0),
                item.get('completed_tasks',0), f"{item.get('completion_rate',0):.1f}",
                f"{item.get('avg_completion_hours',0):.1f}"))

    def _render_failure(self, parent, failures):
        fc = self._card(parent); self._card_header(fc, "پرتکرارترین خرابی‌ها", "⚠️")
        ff = tk.Frame(fc, bg=CARD_BG); ff.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        if not failures:
            tk.Label(ff, text="هیچ خرابی ثبت نشده است.", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_LIGHT).pack(pady=40)
            return
        tree = self._styled_tree(ff, ("description","count"),
            [("description","توضیحات خرابی",600),("count","تعداد تکرار",100)], height=12)
        for i, item in enumerate(failures):
            tag = "even" if i % 2 == 0 else "odd"
            tree.insert("", tk.END, tags=(tag,), values=(item.get('description','—'), item.get('count',0)))

    # ── Refresh all ──────────────────────────────────────────────────────
    def _refresh_all(self):
        if self._loading:
            return
        self._loading = True
        # Reset loading flags so tabs reload on next view
        for tag in self._tabs_loaded:
            self._tabs_loaded[tag] = False
        # Clear all frames and put back loading labels
        for tag in ["overview", "equipment", "kpi", "cost", "tech", "failure"]:
            frame = getattr(self, f"{tag}_frame", None)
            if frame:
                for child in frame.winfo_children():
                    child.destroy()
                # Re-add loading label
                loading = tk.Label(frame, text="⏳ در حال بارگذاری...", font=FONT_HEADING,
                                   bg=SECTION_BG, fg=TEXT_LIGHT)
                loading.pack(expand=True)
                frame._loading_label = loading
        # Reload only the current visible tab
        current = self.notebook.select()
        if current:
            frame = self.notebook.nametowidget(current)
            tag = getattr(frame, '_tab_tag', 'overview')
            self._load_tab_data(tag)
        else:
            self._load_tab_data("overview")
        self._loading = False

    # ── Equipment Detail Dialog ──────────────────────────────────────────
    def _open_equipment_detail(self, event):
        selection = self.equipment_tree.selection()
        if not selection:
            return
        equipment_id = self.equipment_tree.item(selection[0])['values'][0]
        eq_data = self.eq_repo.get_equipment_by_id(equipment_id)
        if not eq_data:
            messagebox.showerror("خطا", "تجهیز یافت نشد")
            return

        dialog = tk.Toplevel(self)
        dialog.title(f"گزارش تفصیلی — {eq_data['name']}")
        dialog.geometry("1100x800")
        dialog.configure(bg=SECTION_BG)
        dialog.transient(self); dialog.grab_set()

        dh = tk.Frame(dialog, bg=NAVY, height=56)
        dh.pack(fill=tk.X); dh.pack_propagate(False)
        tk.Label(dh, text=f"⚙️  {eq_data['name']}", font=FONT_TITLE,
                 bg=NAVY, fg=WHITE).pack(side=tk.RIGHT, padx=20, pady=12)

        notebook = ttk.Notebook(dialog, style="Report.TNotebook")
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        main_frame = tk.Frame(notebook, bg=SECTION_BG)
        notebook.add(main_frame, text="اطلاعات و عملکرد")
        canvas = tk.Canvas(main_frame, bg=SECTION_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=SECTION_BG)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        info_card = self._card(scrollable)
        self._card_header(info_card, "مشخصات اصلی", "📋")
        info_grid = tk.Frame(info_card, bg=CARD_BG)
        info_grid.pack(fill=tk.X, padx=14, pady=10)
        inst_date = eq_data.get("installation_date", "—")
        fields = [
            ("کد تجهیز:", eq_data.get("code", "—")),
            ("نام تجهیز:", eq_data.get("name", "—")),
            ("دسته‌بندی:", eq_data.get("category", "—")),
            ("سازنده:", eq_data.get("manufacturer", "—")),
            ("مدل:", eq_data.get("model", "—")),
            ("شماره سریال:", eq_data.get("serial_number", "—")),
            ("موقعیت:", eq_data.get("location", "—")),
            ("تاریخ نصب:", inst_date),
            ("وضعیت:", STATUS_FA.get(eq_data.get("status", ""), eq_data.get("status", "—"))),
        ]
        for i, (label, value) in enumerate(fields):
            r, c = divmod(i, 2)
            tk.Label(info_grid, text=label, font=("Tahoma", 9, "bold"),
                     bg=CARD_BG, fg=TEXT_LIGHT).grid(row=r, column=c*2, sticky="e", padx=(10, 4), pady=4)
            tk.Label(info_grid, text=value, font=FONT_NORMAL,
                     bg=CARD_BG, fg=TEXT_DARK).grid(row=r, column=c*2+1, sticky="w", padx=(0, 20), pady=4)
        for col_w in [0,1,2,3]: info_grid.columnconfigure(col_w, weight=1)

        specs_card = self._card(scrollable)
        self._card_header(specs_card, "مشخصات فنی", "🔧")
        tk.Label(specs_card, text=eq_data.get("specifications", "—"),
                 wraplength=900, justify="right", font=FONT_NORMAL,
                 bg=CARD_BG, fg=TEXT_DARK).pack(anchor="w", padx=14, pady=10)

        notes_card = self._card(scrollable)
        self._card_header(notes_card, "یادداشت‌ها", "📝")
        tk.Label(notes_card, text=eq_data.get("notes", "—"),
                 wraplength=900, justify="right", font=FONT_NORMAL,
                 bg=CARD_BG, fg=TEXT_DARK).pack(anchor="w", padx=14, pady=10)

        start = self.start_date.get_date()
        end   = self.end_date.get_date()
        report = self.report_repo.get_equipment_report(equipment_id, start, end)
        if report:
            kpi_card = self._card(scrollable)
            self._card_header(kpi_card, "شاخص‌های عملکردی", "📊")
            kpi_grid = tk.Frame(kpi_card, bg=CARD_BG)
            kpi_grid.pack(fill=tk.X, padx=14, pady=10)
            total_cost = 0.0
            wo_repo = WorkOrderRepository(SessionLocal)
            sp_repo = SparePartsRepository(SessionLocal)
            for wo in wo_repo.get_all():
                if wo.equipment_id != equipment_id: continue
                if start and wo.created_at.date() < start: continue
                if end and wo.created_at.date() > end: continue
                if wo.parts_used:
                    try:
                        for item in json.loads(wo.parts_used):
                            part = sp_repo.get_by_id(item.get("part_id"))
                            if part:
                                total_cost += float(part.unit_price) * float(item.get("quantity", 0))
                    except: pass
                if wo.start_time and wo.end_time:
                    total_cost += (wo.end_time - wo.start_time).total_seconds() / 3600 * 50
                total_cost += float(wo.manual_cost or 0)

            kpis = [
                ("کل دستورات کار:", report.get('total_work_orders', 0)),
                ("تکمیل شده:", report.get('completed_work_orders', 0)),
                ("PM:", report.get('pm_work_orders', 0)),
                ("CM:", report.get('cm_work_orders', 0)),
                ("میانگین زمان تعمیر (h):", f"{report.get('avg_repair_time_hours', 0):.2f}"),
                ("کل زمان توقف (h):", f"{report.get('total_downtime_hours', 0):.2f}"),
                ("انطباق PM٪:", f"{report.get('pm_compliance_rate', 0):.1f}"),
                ("MTBF (h):", f"{report.get('mtbf_hours', 0):.2f}"),
                ("MTTR (h):", f"{report.get('mttr_hours', 0):.2f}"),
                ("تعداد خرابی:", report.get('failure_count', 0)),
                ("هزینه کل (ریال):", f"{total_cost:,.0f}"),
            ]
            for i, (label, value) in enumerate(kpis):
                r, c = divmod(i, 2)
                tk.Label(kpi_grid, text=label, font=("Tahoma", 9, "bold"),
                         bg=CARD_BG, fg=TEXT_LIGHT).grid(row=r, column=c*2, sticky="e", padx=(10, 4), pady=4)
                tk.Label(kpi_grid, text=str(value), font=FONT_NORMAL,
                         bg=CARD_BG, fg=TEXT_DARK).grid(row=r, column=c*2+1, sticky="w", padx=(0, 20), pady=4)
            for col_w in [0,1,2,3]: kpi_grid.columnconfigure(col_w, weight=1)

        chart_frame = tk.Frame(notebook, bg=SECTION_BG)
        notebook.add(chart_frame, text="نمودارها")
        fig = Figure(figsize=(12, 5), dpi=88, facecolor=SECTION_BG)
        ax1 = fig.add_subplot(121); ax1.set_facecolor(CARD_BG)
        if report:
            pm = report.get('pm_work_orders', 0)
            cm = report.get('cm_work_orders', 0)
            em_count = 0
            session = SessionLocal()
            try:
                q = session.query(func.count(WorkOrder.id)).filter(
                    WorkOrder.equipment_id == equipment_id,
                    WorkOrder.type == WorkOrderType.EMERGENCY,
                    WorkOrder.status == WorkOrderStatus.APPROVED)
                if start: q = q.filter(WorkOrder.created_at >= start)
                if end:   q = q.filter(WorkOrder.created_at <= end)
                em_count = q.scalar() or 0
            finally: session.close()
            if pm + cm + em_count > 0:
                ax1.pie([pm, cm, em_count], labels=['PM', 'CM', 'EM'], autopct='%1.1f%%',
                        colors=[SUCCESS, ACCENT_ROSE, ACCENT_AMBER],
                        wedgeprops=dict(linewidth=1.5, edgecolor='white'))
                ax1.set_title('Work Order Distribution', color=NAVY, fontsize=10)
            else:
                ax1.text(0.5, 0.5, 'No Data', ha='center', va='center', color=TEXT_LIGHT); ax1.set_axis_off()
        else:
            ax1.text(0.5, 0.5, 'No Data', ha='center', va='center', color=TEXT_LIGHT)

        ax2 = fig.add_subplot(122); ax2.set_facecolor(CARD_BG)
        if report:
            metrics = ['MTBF', 'MTTR', 'Downtime']
            values = [report.get('mtbf_hours', 0), report.get('mttr_hours', 0),
                      report.get('total_downtime_hours', 0)]
            bars = ax2.bar(metrics, values, color=[NAVY, ACCENT_AMBER, ACCENT_ROSE],
                           width=0.5, edgecolor='white')
            for bar, val in zip(bars, values):
                if val > 0:
                    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                             f"{val:.1f}", ha='center', va='bottom', fontsize=8, color=TEXT_DARK)
            ax2.set_ylabel('Hours', fontsize=8, color=TEXT_LIGHT)
            ax2.set_title('Key Metrics (Hours)', color=NAVY, fontsize=10)
            ax2.spines['top'].set_visible(False); ax2.spines['right'].set_visible(False)
        else:
            ax2.text(0.5, 0.5, 'No Data', ha='center', va='center', color=TEXT_LIGHT)
        fig.tight_layout(pad=1.5)
        self._embed_chart(fig, chart_frame)

        notes_tab = tk.Frame(notebook, bg=SECTION_BG)
        notebook.add(notes_tab, text="یادداشت دستورکارها")
        notes_card = self._card(notes_tab)
        self._card_header(notes_card, "یادداشت دستورکارها", "📝")
        wo_tree_frame = tk.Frame(notes_card, bg=CARD_BG)
        wo_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        wo_cols = ("id", "title", "type", "status", "created_date", "created_time",
                   "operator_notes", "technician_notes", "part_notes")
        wo_col_defs = [
            ("id", "شناسه", 60),
            ("title", "عنوان", 150),
            ("type", "نوع", 80),
            ("status", "وضعیت", 80),
            ("created_date", "تاریخ", 80),
            ("created_time", "زمان", 60),
            ("operator_notes", "یادداشت اپراتور", 250),
            ("technician_notes", "توضیحات تکنسین", 250),
            ("part_notes", "قطعات مصرفی", 180),
        ]
        wo_tree = self._styled_tree(wo_tree_frame, wo_cols, wo_col_defs, height=20)
        wo_tree.bind("<Double-1>", lambda e: self._show_work_order_detail(wo_tree))
        wo_repo = WorkOrderRepository(SessionLocal)
        for i, wo in enumerate(wo for wo in wo_repo.get_all() if wo.equipment_id == equipment_id):
            tag = "even" if i % 2 == 0 else "odd"
            if hasattr(wo, 'created_at') and wo.created_at:
                date_str = wo.created_at.strftime("%Y-%m-%d")
                time_str = wo.created_at.strftime("%H:%M:%S")
            else:
                date_str = "—"
                time_str = "—"
            wo_tree.insert("", tk.END, tags=(tag,), values=(
                wo.id,
                wo.title,
                WO_TYPE_FA.get(wo.type.name, wo.type.name),
                WO_STATUS_FA.get(wo.status.name, wo.status.name),
                date_str,
                time_str,
                wo.operator_notes or "—",
                wo.description or "—",
                wo.parts_used or "—",
            ))
        tk.Button(dialog, text="✕  بستن", font=FONT_NORMAL,
                  bg=ACCENT_ROSE, fg=WHITE, relief="flat",
                  cursor="hand2", padx=20, pady=8,
                  command=dialog.destroy).pack(pady=10)

    def _show_work_order_detail(self, tree):
        selection = tree.selection()
        if not selection:
            return
        wo_id = int(tree.item(selection[0])['values'][0])
        wo_repo = WorkOrderRepository(SessionLocal)
        wo = wo_repo.get_by_id(wo_id)
        if not wo:
            messagebox.showerror("خطا", "دستور کار یافت نشد")
            return

        detail = tk.Toplevel(self)
        detail.title(f"دستور کار #{wo.id}")
        detail.geometry("750x660")
        detail.configure(bg=SECTION_BG)
        detail.transient(self); detail.grab_set()

        dh = tk.Frame(detail, bg=NAVY, height=52)
        dh.pack(fill=tk.X); dh.pack_propagate(False)
        tk.Label(dh, text=f"📝  WO#{wo.id} — {wo.title}", font=FONT_HEADING,
                 bg=NAVY, fg=WHITE).pack(side=tk.RIGHT, padx=20, pady=12)

        canvas = tk.Canvas(detail, bg=SECTION_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(detail, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=SECTION_BG)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        def add_row(parent, text, value, row):
            tk.Label(parent, text=text, font=("Tahoma", 9, "bold"),
                     bg=CARD_BG, fg=TEXT_LIGHT).grid(row=row, column=0, sticky="ne", padx=10, pady=5)
            tk.Label(parent, text=str(value), font=FONT_NORMAL,
                     bg=CARD_BG, fg=TEXT_DARK, wraplength=500, justify="right").grid(
                row=row, column=1, sticky="nw", padx=10, pady=5)
            return row + 1

        info_card = self._card(scrollable)
        self._card_header(info_card, "اطلاعات اصلی", "📋")
        grid = tk.Frame(info_card, bg=CARD_BG)
        grid.pack(fill=tk.X, padx=10, pady=8)

        r = 0
        r = add_row(grid, "شناسه:", wo.id, r)
        r = add_row(grid, "عنوان:", wo.title or "—", r)
        r = add_row(grid, "تجهیز:", wo.equipment.name if wo.equipment else "—", r)
        r = add_row(grid, "نوع:", WO_TYPE_FA.get(wo.type.name, wo.type.name), r)
        r = add_row(grid, "اولویت:", WO_STATUS_FA.get(wo.priority.name, wo.priority.name), r)
        r = add_row(grid, "وضعیت:", WO_STATUS_FA.get(wo.status.name, wo.status.name), r)
        r = add_row(grid, "تاریخ برنامه:", wo.scheduled_date.strftime("%Y-%m-%d") if wo.scheduled_date else "—", r)
        r = add_row(grid, "شروع:", wo.start_time.strftime("%Y-%m-%d %H:%M") if wo.start_time else "—", r)
        r = add_row(grid, "پایان:", wo.end_time.strftime("%Y-%m-%d %H:%M") if wo.end_time else "—", r)
        r = add_row(grid, "تکنسین:", wo.technician.full_name if wo.technician else "—", r)

        cost_card = self._card(scrollable)
        self._card_header(cost_card, "هزینه‌ها", "💰")
        cg = tk.Frame(cost_card, bg=CARD_BG)
        cg.pack(fill=tk.X, padx=10, pady=8)
        cr = 0
        cr = add_row(cg, "هزینه دستی (ریال):", f"{wo.manual_cost:,.0f}" if wo.manual_cost else "0", cr)
        cr = add_row(cg, "توضیح هزینه:", wo.cost_description or "—", cr)

        def text_card(title, icon, content):
            tc = self._card(scrollable)
            self._card_header(tc, title, icon)
            txt = tk.Text(tc, height=4, wrap="word", font=FONT_NORMAL,
                          bg=SECTION_BG, fg=TEXT_DARK, relief="flat", padx=10, pady=6)
            txt.insert("1.0", content or "—"); txt.config(state="disabled")
            txt.pack(fill=tk.X, padx=10, pady=8)

        text_card("یادداشت اپراتور", "👤", wo.operator_notes)
        text_card("توضیحات تکنسین", "🔧", wo.description)
        text_card("قطعات مصرفی", "🔩", wo.parts_used)

        tk.Button(detail, text="✕  بستن", font=FONT_NORMAL,
                  bg=ACCENT_ROSE, fg=WHITE, relief="flat",
                  cursor="hand2", padx=20, pady=8,
                  command=detail.destroy).pack(pady=10)

    # ── Excel Export ────────────────────────────────────────────────────
    def _export_tab_to_excel(self, frame, tab_title):
        data = self._collect_tab_data(frame, tab_title)
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"{tab_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        if not filename:
            return
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = tab_title[:31]
            ws.sheet_view.rightToLeft = True
            headers = list(data[0].keys())
            max_cols = len(headers)
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max_cols)
            cell = ws.cell(row=1, column=1, value="شرکت گلا — سیستم نگهداری پیشگیرانه")
            cell.font = Font(name="Tahoma", size=12, bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="1A2A44", end_color="1A2A44", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[1].height = 30
            ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max_cols)
            tc = ws.cell(row=2, column=1, value=tab_title)
            tc.font = Font(name="Tahoma", size=14, bold=True, color="1A2A44")
            tc.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[2].height = 25
            start = self.start_date.get_date().strftime("%Y-%m-%d")
            end = self.end_date.get_date().strftime("%Y-%m-%d")
            ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=max_cols)
            ic = ws.cell(row=3, column=1, value=f"بازه گزارش: {start} تا {end}  |  تاریخ تهیه: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            ic.font = Font(name="Tahoma", size=9, italic=True, color="5F6368")
            ic.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[3].height = 20
            header_row = 5
            for ci, header in enumerate(headers, 1):
                c = ws.cell(row=header_row, column=ci, value=header)
                c.font = Font(name="Tahoma", size=10, bold=True, color="FFFFFF")
                c.fill = PatternFill(start_color="1A2A44", end_color="1A2A44", fill_type="solid")
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                c.border = Border(left=Side(style="thin"), right=Side(style="thin"),
                                  top=Side(style="thin"), bottom=Side(style="thin"))
            ws.row_dimensions[header_row].height = 28
            for ri, row_data in enumerate(data, start=header_row+1):
                bg = "F4F6F9" if ri % 2 == 0 else "FFFFFF"
                for ci, value in enumerate(row_data.values(), 1):
                    c = ws.cell(row=ri, column=ci, value=value)
                    c.font = Font(name="Tahoma", size=9)
                    c.fill = PatternFill(start_color=bg, end_color=bg, fill_type="solid")
                    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    c.border = Border(left=Side(style="thin", color="E8ECF0"),
                                      right=Side(style="thin", color="E8ECF0"),
                                      top=Side(style="thin", color="E8ECF0"),
                                      bottom=Side(style="thin", color="E8ECF0"))
                    if isinstance(value, (int,float)) and not isinstance(value, bool):
                        try:
                            c.number_format = "#,##0.00" if isinstance(value, float) else "#,##0"
                        except:
                            pass
                ws.row_dimensions[ri].height = 20
            for ci in range(1, len(headers)+1):
                max_len = 10
                for r in range(header_row, header_row+len(data)+1):
                    v = ws.cell(row=r, column=ci).value
                    if v:
                        max_len = max(max_len, len(str(v)))
                ws.column_dimensions[get_column_letter(ci)].width = min(max_len+2, 50)
            ws.freeze_panes = ws.cell(row=header_row+1, column=1)
            wb.save(filename)
            messagebox.showinfo("موفق", "خروجی Excel با موفقیت ذخیره شد!")
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد خروجی: {str(e)}")

    def _collect_tab_data(self, frame, tab_title):
        data = []
        if tab_title == "عملکرد تجهیزات" and hasattr(self, 'equipment_tree'):
            for child in self.equipment_tree.get_children():
                values = self.equipment_tree.item(child)['values']
                data.append({
                    "شناسه": values[0], "نام تجهیز": values[1], "وضعیت": values[2],
                    "کل WO": values[3], "تکمیل شده": values[4], "PM": values[5],
                    "CM": values[6], "EM": values[7], "MTBF (ساعت)": values[8],
                    "MTTR (ساعت)": values[9], "دسترسی (%)": values[10], "OEE (%)": values[11],
                    "توقف (ساعت)": values[12], "هزینه کل (ریال)": values[13],
                })
        elif tab_title == "عملکرد تکنسین‌ها" and hasattr(self, 'tech_tree') and self.tech_tree:
            for child in self.tech_tree.get_children():
                values = self.tech_tree.item(child)['values']
                data.append({
                    "تکنسین": values[0], "کل وظایف": values[1], "تکمیل شده": values[2],
                    "نرخ تکمیل (%)": values[3], "میانگین زمان (ساعت)": values[4],
                })
        elif tab_title == "داشبورد کلی":
            start = self.start_date.get_date()
            end = self.end_date.get_date()
            summary = self.report_repo.get_kpi_summary(start, end)
            backlog = self.report_repo.get_backlog_analysis(start, end)
            rejection = self.report_repo.get_rejection_percentage(start, end)
            delay = self.report_repo.get_delay_summary(start, end)
            data.append({
                "کل دستورات کار": summary.get('total_work_orders',0),
                "تکمیل شده": summary.get('completed_work_orders',0),
                "در حال انجام": summary.get('in_progress_work_orders',0),
                "معوق": summary.get('overdue_work_orders',0),
                "کل تجهیزات": summary.get('total_equipment',0),
                "عملیاتی": summary.get('operational_equipment',0),
                "میانگین زمان تعمیر (ساعت)": summary.get('avg_completion_time_hours',0),
                "انطباق PM (%)": summary.get('pm_compliance_rate',0),
                "در انتظار": backlog.get('pending',0),
                "در حال انجام (بک‌لاگ)": backlog.get('in_progress',0),
                "سررسید گذشته": backlog.get('overdue',0),
                "کل معوقات": backlog.get('total_backlog',0),
                "درصد رد": f"{rejection['percentage']:.1f}",
                "مجموع تأخیر (دقیقه)": delay['total_minutes'],
                "تعداد کارهای دارای تأخیر": delay['delayed_count'],
            })
        elif tab_title == "تحلیل KPI":
            start = self.start_date.get_date()
            end = self.end_date.get_date()
            pm_cm = self.report_repo.get_pm_cm_ratio(start, end)
            compliance = self.report_repo.get_schedule_compliance(start, end)
            risk = self.report_repo.get_equipment_risk_score()
            data.append({
                "PM": pm_cm.get('preventive_count',0), "CM": pm_cm.get('corrective_count',0),
                "EM": pm_cm.get('emergency_count',0), "نسبت PM/CM": pm_cm.get('ratio',0),
                "کل وظایف برنامه": compliance.get('total_tasks',0),
                "انجام به موقع": compliance.get('on_time',0),
                "تاخیر": compliance.get('late',0),
                "نرخ انطباق (%)": compliance.get('compliance_rate',0),
            })
            for r in risk[:10]:
                data.append({"تجهیز": r.get('equipment_name','—'),
                             "امتیاز ریسک": r.get('risk_score',0), "سطح": r.get('risk_level','—')})
        elif tab_title == "تحلیل هزینه":
            start = self.start_date.get_date()
            end = self.end_date.get_date()
            cost = self.report_repo.get_cost_analysis(start, end)
            for item in cost.get('breakdown', []):
                data.append({
                    "نوع": item.get('type','—'), "هزینه کل": item.get('total_cost',0),
                    "درصد": item.get('percentage',0), "هزینه قطعات": item.get('part_cost',0),
                    "هزینه نیروی کار": item.get('labor_cost',0),
                })
        elif tab_title == "تحلیل خرابی‌ها":
            start = self.start_date.get_date()
            end = self.end_date.get_date()
            failures = self.report_repo.get_top_failure_modes(start, end, limit=50)
            for item in failures:
                data.append({"توضیحات خرابی": item.get('description','—'), "تعداد تکرار": item.get('count',0)})
        return data