# views/dashboard_view.py
"""
Dashboard View - Main landing page with KPIs, charts, and recent activities.
All chart text is in English to avoid Persian font rendering issues.
UI text (labels, buttons, listboxes) is in Persian.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

from database.report_repository import ReportRepository
from database.equipment_repository import EquipmentRepository
from database.work_order_repository import WorkOrderRepository
from database.pm_repository import PMRepository
from database.spare_parts_repository import SparePartsRepository
from database.inspection_repository import InspectionRepository
from database.db import SessionLocal

# Theme (matches main_view)
BG = "#F0F4F8"
WHITE = "#FFFFFF"
PRIMARY = "#1A73E8"
DANGER = "#DC3545"
SUCCESS = "#28A745"
WARNING = "#F29900"
TEXT = "#202124"
SUBTLE = "#5F6368"
BORDER = "#DADCE0"

FONT_TITLE = ("Tahoma", 14, "bold")
FONT_LABEL = ("Tahoma", 10, "bold")
FONT_NORMAL = ("Tahoma", 10)
FONT_SMALL = ("Tahoma", 9)
FONT_KPI = ("Tahoma", 20, "bold")


class DashboardView(ttk.Frame):
    def __init__(self, parent, current_user):
        super().__init__(parent)
        self.current_user = current_user
        self.report_repo = ReportRepository()
        self.eq_repo = EquipmentRepository()
        self.wo_repo = WorkOrderRepository()
        self.pm_repo = PMRepository()
        self.sp_repo = SparePartsRepository(SessionLocal())
        self.ins_repo = InspectionRepository()

        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        # Header with title and refresh button
        header = tk.Frame(self, bg=BG)
        header.pack(fill=tk.X, padx=20, pady=(10, 0))

        tk.Label(header, text="📊  داشبورد مدیریت", font=FONT_TITLE,
                 bg=BG, fg=PRIMARY).pack(side=tk.RIGHT)

        refresh_btn = tk.Button(header, text="🔄 بروزرسانی", font=FONT_NORMAL,
                                bg=PRIMARY, fg=WHITE, relief="flat", cursor="hand2",
                                padx=15, pady=5, command=self._refresh_all)
        refresh_btn.pack(side=tk.LEFT)

        # Scrollable canvas
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable = tk.Frame(self.canvas, bg=BG)

        self.scrollable.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Bind mousewheel
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _refresh_all(self):
        # Clear existing widgets
        for w in self.scrollable.winfo_children():
            w.destroy()

        # Fetch data
        self.kpi_data = self.report_repo.get_kpi_summary()
        self.backlog = self.report_repo.get_backlog_analysis()
        self.pm_cm = self.report_repo.get_pm_cm_ratio()
        self.risk_data = self.report_repo.get_equipment_risk_score()[:5]  # top 5 risky equipments

        # Recent work orders
        recent_wos = self.wo_repo.get_all(status_filter=None, type_filter=None)[:5]

        # Low stock parts
        low_stock = self.sp_repo.get_low_stock()[:5]

        # Upcoming PMs (next 7 days)
        upcoming_pms = self.pm_repo.get_upcoming_pms(days=7)[:5]

        # Recent inspections
        inspections = self.ins_repo.get_all_inspections()
        recent_ins = inspections[:5] if inspections else []

        # Build UI sections
        self._build_kpi_row()
        self._build_charts_row()
        self._build_recent_lists(recent_wos, low_stock, upcoming_pms, recent_ins)
        self._build_quick_actions()

    def _build_kpi_row(self):
        row_frame = tk.Frame(self.scrollable, bg=BG)
        row_frame.pack(fill=tk.X, pady=10, padx=10)

        completion_rate = self._calc_completion_rate()
        low_stock_count = len(self.sp_repo.get_low_stock())
        overdue_pm_count = self.pm_repo.get_overdue_count()

        kpis = [
            ("کل دستورات کار", self.kpi_data['total_work_orders'], PRIMARY),
            ("تکمیل شده", self.kpi_data['completed_work_orders'], SUCCESS),
            ("نرخ تکمیل", f"{completion_rate:.1f}%", SUCCESS),
            ("انطباق PM", f"{self.kpi_data['pm_compliance_rate']:.1f}%", PRIMARY),
            ("قطعات کم‌موجود", low_stock_count, WARNING),
            ("PM‌های معوق", overdue_pm_count, DANGER),
        ]

        for i, (title, value, color) in enumerate(kpis):
            card = tk.Frame(row_frame, bg=WHITE, highlightbackground=BORDER, highlightthickness=1, relief=tk.RAISED)
            card.grid(row=0, column=i, padx=8, pady=5, sticky="nsew")
            row_frame.grid_columnconfigure(i, weight=1)

            tk.Label(card, text=title, font=FONT_SMALL, bg=WHITE, fg=SUBTLE).pack(pady=(10, 0))
            tk.Label(card, text=str(value), font=FONT_KPI, bg=WHITE, fg=color).pack(pady=(0, 10))

    def _calc_completion_rate(self):
        total = self.kpi_data['total_work_orders']
        completed = self.kpi_data['completed_work_orders']
        return (completed / total * 100) if total > 0 else 0

    def _build_charts_row(self):
        row_frame = tk.Frame(self.scrollable, bg=BG)
        row_frame.pack(fill=tk.X, pady=10, padx=10)

        # Chart 1: Work order trends (last 6 months) - English text only
        trends = self.report_repo.get_monthly_trends(6)
        if trends:
            fig1 = Figure(figsize=(5, 3), dpi=80)
            ax1 = fig1.add_subplot(111)
            months = {}
            for t in trends:
                key = f"{t['year']}-{t['month']:02d}"
                if key not in months:
                    months[key] = {'PREVENTIVE': 0, 'PM': 0, 'CORRECTIVE': 0, 'INSPECTION': 0}
                typ = t['type']
                if typ in months[key]:
                    months[key][typ] += t['count']
            x = list(months.keys())
            preventive = [months[m].get('PREVENTIVE', 0) + months[m].get('PM', 0) for m in x]
            corrective = [months[m].get('CORRECTIVE', 0) for m in x]
            ax1.plot(x, preventive, marker='o', label='Preventive', color=SUCCESS)
            ax1.plot(x, corrective, marker='s', label='Corrective', color=DANGER)
            ax1.set_title("Work Order Trends", fontsize=10)
            ax1.legend(fontsize=8)
            ax1.tick_params(axis='x', rotation=45, labelsize=8)
            canvas1 = FigureCanvasTkAgg(fig1, row_frame)
            canvas1.draw()
            canvas1.get_tk_widget().pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

        # Chart 2: Equipment status distribution - English text only
        eq_stats = self.eq_repo.get_stats()
        labels = ['Operational', 'Maintenance', 'Breakdown', 'Inactive']
        sizes = [eq_stats['operational'], eq_stats['maintenance'], eq_stats['breakdown'], eq_stats['inactive']]
        colors = [SUCCESS, WARNING, DANGER, SUBTLE]
        fig2 = Figure(figsize=(4, 3), dpi=80)
        ax2 = fig2.add_subplot(111)
        ax2.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
        ax2.set_title("Equipment Status", fontsize=10)
        canvas2 = FigureCanvasTkAgg(fig2, row_frame)
        canvas2.draw()
        canvas2.get_tk_widget().pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

        # Chart 3: PM/CM ratio - English text only
        fig3 = Figure(figsize=(3, 3), dpi=80)
        ax3 = fig3.add_subplot(111)
        ax3.bar(['PM', 'CM'], [self.pm_cm['preventive_count'], self.pm_cm['corrective_count']], color=[SUCCESS, DANGER])
        ax3.set_title(f"PM/CM Ratio = {self.pm_cm['ratio']:.2f}", fontsize=10)
        canvas3 = FigureCanvasTkAgg(fig3, row_frame)
        canvas3.draw()
        canvas3.get_tk_widget().pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

    def _build_recent_lists(self, recent_wos, low_stock, upcoming_pms, recent_ins):
        row_frame = tk.Frame(self.scrollable, bg=BG)
        row_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        # Column 1: Recent Work Orders
        frame1 = tk.LabelFrame(row_frame, text="📝 دستورکارهای اخیر", font=FONT_LABEL, bg=WHITE, fg=TEXT)
        frame1.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self._build_listbox(frame1, recent_wos, self._format_work_order)

        # Column 2: Low Stock Spare Parts
        frame2 = tk.LabelFrame(row_frame, text="⚠️ قطعات با موجودی کم", font=FONT_LABEL, bg=WHITE, fg=TEXT)
        frame2.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self._build_listbox(frame2, low_stock, self._format_spare_part)

        # Column 3: Upcoming PMs
        frame3 = tk.LabelFrame(row_frame, text="📅 برنامه‌های نزدیک PM", font=FONT_LABEL, bg=WHITE, fg=TEXT)
        frame3.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        self._build_listbox(frame3, upcoming_pms, self._format_pm)

        # Column 4: Recent Inspections
        frame4 = tk.LabelFrame(row_frame, text="🔍 بازرسی‌های اخیر", font=FONT_LABEL, bg=WHITE, fg=TEXT)
        frame4.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")

        for i in range(4):
            row_frame.grid_columnconfigure(i, weight=1)
        row_frame.grid_rowconfigure(0, weight=1)

        self._build_listbox(frame4, recent_ins, self._format_inspection)

    def _build_listbox(self, parent, items, formatter):
        listbox = tk.Listbox(parent, bg=WHITE, fg=TEXT, font=FONT_SMALL, height=8, relief="flat", highlightbackground=BORDER)
        listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        for item in items:
            listbox.insert(tk.END, formatter(item))
        listbox.bind("<Double-1>", lambda e, items=items: self._on_listbox_double_click(items, listbox.curselection()))

    def _format_work_order(self, wo):
        eq_name = wo.equipment.name if wo.equipment else "—"
        status_map = {"pending": "در انتظار", "in_progress": "در حال انجام", "completed": "تکمیل شده"}
        status_text = status_map.get(wo.status.value, wo.status.value)
        return f"WO#{wo.id} - {eq_name} ({status_text})"

    def _format_spare_part(self, part):
        return f"{part.part_number} - {part.name} (موجودی: {part.current_stock}/{part.min_stock})"

    def _format_pm(self, pm):
        eq_name = pm.equipment.name if pm.equipment else "—"
        due = pm.next_due.strftime("%Y-%m-%d") if pm.next_due else "—"
        return f"{pm.title} - {eq_name} (سررسید: {due})"

    def _format_inspection(self, ins):
        eq_name = ins.equipment.name if ins.equipment else "—"
        result_map = {"pass": "قبول", "fail": "رد", "partial": "جزئی"}
        result_text = result_map.get(ins.overall_result, "در حال انجام")
        template_name = ins.template.name if ins.template else "—"
        return f"{template_name} - {eq_name} ({result_text})"

    def _on_listbox_double_click(self, items, selection):
        if not selection:
            return
        idx = selection[0]
        item = items[idx]
        # Optional: open detail dialog – can be extended later
        pass

    def _build_quick_actions(self):
        actions_frame = tk.LabelFrame(self.scrollable, text="عملیات سریع", font=FONT_LABEL, bg=WHITE, fg=TEXT)
        actions_frame.pack(fill=tk.X, pady=10, padx=10)

        btn_frame = tk.Frame(actions_frame, bg=WHITE)
        btn_frame.pack(pady=10)

        buttons = [
            ("➕ دستور کار جدید", self._goto_work_orders),
            ("⚙️ افزودن تجهیز", self._goto_equipment),
            ("🔧 ورود/خروج قطعه", self._goto_spare_parts),
            ("📅 برنامه PM جدید", self._goto_pm),
            ("🔍 بازرسی جدید", self._goto_inspections),
        ]

        for text, cmd in buttons:
            btn = tk.Button(btn_frame, text=text, font=FONT_NORMAL,
                            bg=PRIMARY, fg=WHITE, relief="flat", cursor="hand2",
                            padx=12, pady=5, command=cmd)
            btn.pack(side=tk.LEFT, padx=8)

    # Navigation methods
    def _goto_work_orders(self):
        self._navigate("work_orders")

    def _goto_equipment(self):
        self._navigate("equipment")

    def _goto_spare_parts(self):
        self._navigate("spare_parts")

    def _goto_pm(self):
        self._navigate("pm_schedule")

    def _goto_inspections(self):
        self._navigate("inspections")

    def _navigate(self, view_key):
        root = self.winfo_toplevel()
        if hasattr(root, "_show_view"):
            root._show_view(view_key)
        else:
            for child in root.winfo_children():
                if hasattr(child, "_show_view"):
                    child._show_view(view_key)
                    break