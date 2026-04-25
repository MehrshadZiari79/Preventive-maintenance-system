# views/dashboard_view.py
"""
Dashboard View - Modern, professional, and responsive.
All chart text is in English to avoid Persian font issues.
All UI labels are in Persian.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from database.report_repository import ReportRepository
from database.equipment_repository import EquipmentRepository
from database.work_order_repository import WorkOrderRepository
from database.pm_repository import PMRepository
from database.spare_parts_repository import SparePartsRepository
from database.inspection_repository import InspectionRepository
from database.db import SessionLocal

# ========== Theme (Matches main_view) ==========
BG = "#F0F4F8"
WHITE = "#FFFFFF"
PRIMARY = "#1A73E8"
DANGER = "#DC3545"
SUCCESS = "#28A745"
WARNING = "#F29900"
TEXT = "#202124"
SUBTLE = "#5F6368"
BORDER = "#DADCE0"
CARD_SHADOW = "#E0E0E0"

FONT_TITLE = ("Tahoma", 16, "bold")
FONT_SUBTITLE = ("Tahoma", 12, "bold")
FONT_LABEL = ("Tahoma", 10, "bold")
FONT_NORMAL = ("Tahoma", 10)
FONT_SMALL = ("Tahoma", 9)
FONT_KPI = ("Tahoma", 24, "bold")
FONT_KPI_LABEL = ("Tahoma", 10)

# views/dashboard_view.py
"""Professional Dashboard – now fully responsive in fullscreen."""
# ... (same imports and theme constants as your current file) ...

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
        header = tk.Frame(self, bg=BG, height=70)
        header.pack(fill=tk.X, padx=20, pady=(10, 0))
        header.pack_propagate(False)

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

        # Make scrollable frame fill the canvas horizontally
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

    def _on_canvas_configure(self, event):
        """Update scrollable frame width to match canvas width."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    # ... (rest of the class unchanged from your current file) ...

    # ---------------------- Data Fetching ----------------------
    def _refresh_all(self):
        for w in self.scrollable.winfo_children():
            w.destroy()

        # Fetch all data
        self.kpi_data = self.report_repo.get_kpi_summary()
        self.backlog = self.report_repo.get_backlog_analysis()
        self.pm_cm = self.report_repo.get_pm_cm_ratio()
        self.risk_data = self.report_repo.get_equipment_risk_score()[:5]

        recent_wos = self.wo_repo.get_all(status_filter=None, type_filter=None)[:5]
        low_stock = self.sp_repo.get_low_stock()[:5]
        upcoming_pms = self.pm_repo.get_upcoming_pms_dict(days=7)[:5]
        inspections = self.ins_repo.get_all_inspections()
        recent_ins = inspections[:5] if inspections else []

        # Build sections
        self._build_kpi_grid()
        self._build_charts_section()
        self._build_lists_grid(recent_wos, low_stock, upcoming_pms, recent_ins)
        self._build_quick_actions()

    # ---------------------- KPI Grid (2 rows, 4 cols) ----------------------
    def _build_kpi_grid(self):
        frame = tk.Frame(self.scrollable, bg=BG)
        frame.pack(fill=tk.X, padx=20, pady=10)

        completion_rate = (self.kpi_data['completed_work_orders'] / max(1, self.kpi_data['total_work_orders']) * 100)
        low_stock_count = len(self.sp_repo.get_low_stock())
        overdue_pm_count = self.pm_repo.get_overdue_count()
        emergency_count = self.kpi_data.get('emergency_work_orders', 0)

        kpis = [
            ("دستورات کار", self.kpi_data['total_work_orders'], PRIMARY),
            ("تکمیل شده", self.kpi_data['completed_work_orders'], SUCCESS),
            ("نرخ تکمیل", f"{completion_rate:.1f}%", SUCCESS),
            ("انطباق PM", f"{self.kpi_data['pm_compliance_rate']:.1f}%", PRIMARY),
            ("قطعات کم‌موجود", low_stock_count, WARNING),
            ("PM معوق", overdue_pm_count, DANGER),
            ("اضطراری", emergency_count, DANGER),
            ("تجهیزات", self.kpi_data['total_equipment'], PRIMARY),
        ]

        # Arrange in 2 rows, 4 columns
        for i, (title, value, color) in enumerate(kpis):
            row = i // 4
            col = i % 4
            self._create_kpi_card(frame, title, value, color, row, col)

        # Configure grid columns to be equal width
        for col in range(4):
            frame.columnconfigure(col, weight=1)

    def _create_kpi_card(self, parent, title, value, color, row, col):
        card = tk.Frame(parent, bg=WHITE, relief=tk.RAISED, bd=0,
                        highlightbackground=CARD_SHADOW, highlightthickness=1)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        tk.Label(card, text=title, font=FONT_KPI_LABEL,
                bg=WHITE, fg=SUBTLE).pack(pady=(12, 0))
        tk.Label(card, text=str(value), font=FONT_KPI,
                bg=WHITE, fg=color).pack(pady=(0, 12))

    # ---------------------- Charts Section (side by side) ----------------------
    def _build_charts_section(self):
        container = tk.Frame(self.scrollable, bg=BG)
        container.pack(fill=tk.X, padx=20, pady=10)

        # Row 1: Trend chart + Equipment status pie
        row1 = tk.Frame(container, bg=BG)
        row1.pack(fill=tk.X, pady=5)

        # Chart 1: Work order trends (last 6 months)
        trends = self.report_repo.get_monthly_trends(6)
        if trends:
            fig1 = Figure(figsize=(5.5, 3.2), dpi=90)
            ax1 = fig1.add_subplot(111)
            months = {}
            for t in trends:
                key = f"{t['year']}-{t['month']:02d}"
                if key not in months:
                    months[key] = {'PREVENTIVE': 0, 'PM': 0, 'CORRECTIVE': 0, 'EMERGENCY': 0}
                typ = t['type']
                if typ in months[key]:
                    months[key][typ] += t['count']
            x = list(months.keys())
            preventive = [months[m].get('PREVENTIVE', 0) + months[m].get('PM', 0) for m in x]
            corrective = [months[m].get('CORRECTIVE', 0) for m in x]
            emergency = [months[m].get('EMERGENCY', 0) for m in x]
            ax1.plot(x, preventive, marker='o', label='Preventive', color=SUCCESS)
            ax1.plot(x, corrective, marker='s', label='Corrective', color=DANGER)
            ax1.plot(x, emergency, marker='^', label='Emergency', color=WARNING)
            ax1.set_title("Work Order Trends (Last 6 Months)", fontsize=10)
            ax1.legend(fontsize=8)
            ax1.tick_params(axis='x', rotation=45, labelsize=7)
            canvas1 = FigureCanvasTkAgg(fig1, row1)
            canvas1.draw()
            canvas1.get_tk_widget().pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

        # Chart 2: Equipment status pie
        eq_stats = self.eq_repo.get_stats()
        labels = ['Operational', 'Maintenance', 'Breakdown', 'Inactive']
        sizes = [eq_stats['operational'], eq_stats['maintenance'], eq_stats['breakdown'], eq_stats['inactive']]
        colors = [SUCCESS, WARNING, DANGER, SUBTLE]
        fig2 = Figure(figsize=(4, 3.2), dpi=90)
        ax2 = fig2.add_subplot(111)
        ax2.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
        ax2.set_title("Equipment Status", fontsize=10)
        canvas2 = FigureCanvasTkAgg(fig2, row1)
        canvas2.draw()
        canvas2.get_tk_widget().pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

        # Row 2: PM/CM/EM bar chart (could also include a small risk table)
        row2 = tk.Frame(container, bg=BG)
        row2.pack(fill=tk.X, pady=5)

        fig3 = Figure(figsize=(4, 3), dpi=90)
        ax3 = fig3.add_subplot(111)
        pm = self.pm_cm.get('preventive_count', 0)
        cm = self.pm_cm.get('corrective_count', 0)
        em = self.pm_cm.get('emergency_count', 0)
        ax3.bar(['PM', 'CM', 'EM'], [pm, cm, em], color=[SUCCESS, DANGER, WARNING])
        ratio = (pm / cm) if cm > 0 else float(pm)
        ax3.set_title(f"PM/CM/EM Ratio (PM/CM = {ratio:.2f})", fontsize=10)
        ax3.set_ylabel("Count")
        canvas3 = FigureCanvasTkAgg(fig3, row2)
        canvas3.draw()
        canvas3.get_tk_widget().pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

        # Optional: Top 5 risk equipment (small table)
        if self.risk_data:
            risk_frame = tk.Frame(row2, bg=WHITE, relief=tk.RAISED, bd=0,
                                  highlightbackground=CARD_SHADOW, highlightthickness=1)
            risk_frame.pack(side=tk.RIGHT, padx=5, fill=tk.BOTH, expand=True)
            tk.Label(risk_frame, text="تجهیزات پرریسک", font=FONT_SUBTITLE,
                     bg=WHITE, fg=TEXT).pack(pady=5)
            for eq in self.risk_data[:4]:
                lbl = tk.Label(risk_frame, text=f"{eq['equipment_name']} - {eq['risk_score']:.0f}",
                               font=FONT_SMALL, bg=WHITE, fg=DANGER if eq['risk_score'] > 70 else WARNING)
                lbl.pack(anchor="w", padx=10, pady=2)

    # ---------------------- Lists Grid (2x2) ----------------------
    def _build_lists_grid(self, recent_wos, low_stock, upcoming_pms, recent_ins):
        container = tk.Frame(self.scrollable, bg=BG)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Row 1: Work orders and Low stock
        row1 = tk.Frame(container, bg=BG)
        row1.pack(fill=tk.BOTH, expand=True, pady=5)
        self._create_list_panel(row1, "📝 دستورکارهای اخیر", recent_wos, self._format_work_order, side=tk.LEFT)
        self._create_list_panel(row1, "⚠️ قطعات کم‌موجود", low_stock, self._format_spare_part, side=tk.RIGHT)

        # Row 2: Upcoming PMs and Recent inspections
        row2 = tk.Frame(container, bg=BG)
        row2.pack(fill=tk.BOTH, expand=True, pady=5)
        self._create_list_panel(row2, "📅 برنامه‌های نزدیک PM", upcoming_pms, self._format_pm, side=tk.LEFT)
        self._create_list_panel(row2, "🔍 بازرسی‌های اخیر", recent_ins, self._format_inspection, side=tk.RIGHT)

    def _create_list_panel(self, parent, title, items, formatter, side=tk.LEFT):
        frame = tk.LabelFrame(parent, text=title, font=FONT_LABEL,
                              bg=WHITE, fg=TEXT, padx=5, pady=5)
        frame.pack(side=side, fill=tk.BOTH, expand=True, padx=5)

        listbox = tk.Listbox(frame, bg=WHITE, fg=TEXT, font=FONT_SMALL,
                             height=8, relief="flat", highlightbackground=BORDER)
        listbox.pack(fill=tk.BOTH, expand=True)
        for item in items:
            listbox.insert(tk.END, formatter(item))
        listbox.bind("<Double-1>", lambda e, it=items, lb=listbox: self._on_listbox_double_click(it, lb.curselection()))

    # ---------------------- Formatting Helpers ----------------------
    def _format_work_order(self, wo):
        eq_name = wo.equipment.name if wo.equipment else "—"
        status_map = {"pending": "در انتظار", "in_progress": "در حال انجام", "completed": "تکمیل شده"}
        status_text = status_map.get(wo.status.value, wo.status.value)
        return f"WO#{wo.id} - {eq_name} ({status_text})"

    def _format_spare_part(self, part):
        return f"{part.part_number} - {part.name} (موجودی: {part.current_stock}/{part.min_stock})"

    def _format_pm(self, pm):
        eq_name = pm.get("equipment_name", "—")
        due = pm.get("next_due", "—")
        title = pm.get("title", "")
        return f"{title} - {eq_name} (سررسید: {due})"

    def _format_inspection(self, ins):
        eq_name = ins.equipment.name if ins.equipment else "—"
        result_map = {"pass": "قبول", "fail": "رد", "partial": "جزئی"}
        result_text = result_map.get(ins.overall_result, "در حال انجام")
        template_name = ins.template.name if ins.template else "—"
        return f"{template_name} - {eq_name} ({result_text})"

    def _on_listbox_double_click(self, items, selection):
        if not selection:
            return
        # Optionally open detail dialog (not implemented)
        pass

    # ---------------------- Quick Actions ----------------------
    def _build_quick_actions(self):
        actions_frame = tk.LabelFrame(self.scrollable, text="عملیات سریع", font=FONT_LABEL,
                                      bg=WHITE, fg=TEXT, padx=10, pady=10)
        actions_frame.pack(fill=tk.X, padx=20, pady=15)

        btn_frame = tk.Frame(actions_frame, bg=WHITE)
        btn_frame.pack()
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
                            padx=12, pady=6, command=cmd)
            btn.pack(side=tk.LEFT, padx=8)

    # ---------------------- Navigation ----------------------
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