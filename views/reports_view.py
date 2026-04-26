# views/reports_view.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from sqlalchemy import func

from database.report_repository import ReportRepository
from database.equipment_repository import EquipmentRepository
from database.work_order import WorkOrder, WorkOrderType

STATUS_FA = {
    "operational": "عملیاتی",
    "maintenance": "در تعمیر",
    "breakdown": "خراب",
    "inactive": "غیرفعال",
}

class ReportsView(ttk.Frame):
    def __init__(self, parent, current_user):
        super().__init__(parent)
        self.current_user = current_user
        self.report_repo = ReportRepository()
        self.eq_repo = EquipmentRepository()
        self._loading = False

        self._build_ui()
        self._load_dashboard()

    def _build_ui(self):
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(title_frame, text="گزارشات و تحلیل‌ها", font=("Tahoma", 16, "bold")).pack(side=tk.RIGHT)

        filter_frame = ttk.LabelFrame(self, text="فیلترها", padding=10)
        filter_frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(filter_frame, text="از تاریخ:").grid(row=0, column=3, padx=5)
        self.start_date = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd')
        self.start_date.set_date(datetime.now() - timedelta(days=30))
        self.start_date.grid(row=0, column=2, padx=5)

        ttk.Label(filter_frame, text="تا تاریخ:").grid(row=0, column=1, padx=5)
        self.end_date = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd')
        self.end_date.set_date(datetime.now())
        self.end_date.grid(row=0, column=0, padx=5)

        ttk.Button(filter_frame, text="بروزرسانی", command=self._refresh_all).grid(row=0, column=4, padx=10)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_frame, text="داشبورد کلی")

        self.equipment_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.equipment_frame, text="عملکرد تجهیزات")

        self.kpi_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.kpi_frame, text="تحلیل KPI")

        self.cost_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.cost_frame, text="تحلیل هزینه")

        self.tech_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tech_frame, text="عملکرد تکنسین‌ها")

        self.trend_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.trend_frame, text="روندها")

        self._add_tab_export_buttons()

    def _add_tab_export_buttons(self):
        tabs = [
            (self.overview_frame, "داشبورد کلی"),
            (self.equipment_frame, "عملکرد تجهیزات"),
            (self.kpi_frame, "تحلیل KPI"),
            (self.cost_frame, "تحلیل هزینه"),
            (self.tech_frame, "عملکرد تکنسین‌ها"),
            (self.trend_frame, "روندها"),
        ]
        for frame, title in tabs:
            toolbar = ttk.Frame(frame)
            toolbar.pack(fill=tk.X, pady=(0, 5))
            ttk.Button(toolbar, text="📊 Excel", command=lambda f=frame, t=title: self._export_tab_to_excel(f, t)).pack(
                side=tk.LEFT, padx=2)
    def _refresh_all(self):
        if self._loading:
            return
        self._loading = True
        try:
            self._load_dashboard()
        finally:
            self._loading = False

    def _load_dashboard(self):
        start = self.start_date.get_date()
        end = self.end_date.get_date()
        self._load_overview_dashboard()
        self._load_equipment_performance(start, end)
        self._load_kpi_analysis(start, end)
        self._load_cost_analysis(start, end)
        self._load_technician_performance(start, end)
        self._load_trends()

    # -------------------- Overview Dashboard --------------------
    def _load_overview_dashboard(self):
        for w in self.overview_frame.winfo_children():
            if isinstance(w, ttk.Frame) and w != self.overview_frame.winfo_children()[0] if self.overview_frame.winfo_children() else True:
                w.destroy()
        children = list(self.overview_frame.winfo_children())
        for w in children[1:]:
            w.destroy()

        summary = self.report_repo.get_kpi_summary()
        backlog = self.report_repo.get_backlog_analysis()

        canvas = tk.Canvas(self.overview_frame, bg="#F0F4F8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.overview_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        row = 0
        self._create_kpi_card(scrollable, "کل دستورات کار", f"{summary['total_work_orders']}", "تمام دستورات ثبت شده", row, 0, '#2196F3')
        comp_pct = (summary['completed_work_orders'] / summary['total_work_orders'] * 100) if summary['total_work_orders'] > 0 else 0
        self._create_kpi_card(scrollable, "تکمیل شده", f"{summary['completed_work_orders']}", f"{comp_pct:.1f}% از کل", row, 1, '#4CAF50')
        self._create_kpi_card(scrollable, "در حال انجام", f"{summary['in_progress_work_orders']}", "دستورات فعال", row, 2, '#FF9800')
        self._create_kpi_card(scrollable, "معوق", f"{summary['overdue_work_orders']}", "نیاز به توجه فوری", row, 3, '#F44336')
        row += 1

        self._create_kpi_card(scrollable, "کل تجهیزات", f"{summary['total_equipment']}", "تجهیزات ثبت شده", row, 0, '#9C27B0')
        op_pct = (summary['operational_equipment'] / summary['total_equipment'] * 100) if summary['total_equipment'] > 0 else 0
        self._create_kpi_card(scrollable, "عملیاتی", f"{summary['operational_equipment']}", f"{op_pct:.1f}% آماده", row, 1, '#00BCD4')
        self._create_kpi_card(scrollable, "میانگین زمان تعمیر", f"{summary['avg_completion_time_hours']:.1f}", "ساعت", row, 2, '#795548')
        self._create_kpi_card(scrollable, "انطباق PM", f"{summary['pm_compliance_rate']:.1f}%", "نگهداری پیشگیرانه", row, 3, '#607D8B')
        row += 1

        ttk.Label(scrollable, text="تحلیل کارهای معوق", font=("Tahoma", 12, "bold")).grid(row=row, column=0, columnspan=4, pady=(20,10), sticky=tk.W)
        row += 1
        self._create_kpi_card(scrollable, "در انتظار", f"{backlog['pending']}", "دستورات معلق", row, 0, '#FFC107')
        self._create_kpi_card(scrollable, "در حال انجام", f"{backlog['in_progress']}", "در دست اقدام", row, 1, '#03A9F4')
        self._create_kpi_card(scrollable, "سررسید گذشته", f"{backlog['overdue']}", "نیاز به اقدام فوری", row, 2, '#E91E63')
        self._create_kpi_card(scrollable, "کل معوقات", f"{backlog['total_backlog']}", "مجموع کارهای باز", row, 3, '#673AB7')

    def _create_kpi_card(self, parent, title, value, subtitle, row, col, bg):
        card = tk.Frame(parent, bg=bg, relief=tk.RAISED, borderwidth=2)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew", ipadx=20, ipady=15)
        parent.grid_columnconfigure(col, weight=1)
        ttk.Label(card, text=title, font=("Tahoma", 10), background=bg, foreground='white').pack(pady=(5,0))
        ttk.Label(card, text=value, font=("Tahoma", 24, "bold"), background=bg, foreground='white').pack()
        ttk.Label(card, text=subtitle, font=("Tahoma", 8), background=bg, foreground='white').pack(pady=(0,5))

    # -------------------- Equipment Performance Tab (with fixed Decimal error and details) --------------------
    def _load_equipment_performance(self, start_date=None, end_date=None):
        for w in self.equipment_frame.winfo_children():
            if not isinstance(w, ttk.Frame) or w != self.equipment_frame.winfo_children()[0]:
                w.destroy()
        tree_frame = ttk.Frame(self.equipment_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ("id", "name", "status", "total_wo", "completed", "pm", "cm", "em", "mtbf", "mttr", "availability", "downtime")
        self.equipment_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        col_defs = [
            ("id", "ID", 50), ("name", "نام تجهیز", 200), ("status", "وضعیت", 100),
            ("total_wo", "کل WO", 80), ("completed", "تکمیل شده", 100), ("pm", "PM", 60),
            ("cm", "CM", 60), ("em", "EM", 60), ("mtbf", "MTBF (ساعت)", 100),
            ("mttr", "MTTR (ساعت)", 100), ("availability", "در دسترس بودن (%)", 100),
            ("downtime", "زمان توقف (ساعت)", 120)
        ]
        for col, text, width in col_defs:
            self.equipment_tree.heading(col, text=text)
            self.equipment_tree.column(col, width=width)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=vsb.set)
        self.equipment_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.equipment_tree.bind("<Double-1>", self._open_equipment_detail)

        equipments = self.eq_repo.get_all_equipment()
        with self.report_repo._session() as session:
            for eq in equipments:
                report = self.report_repo.get_equipment_report(eq['id'], start_date, end_date)
                if report:
                    # Convert Decimal to float safely
                    mtbf = float(report['mtbf_hours']) if report['mtbf_hours'] is not None else 0.0
                    mttr = float(report['mttr_hours']) if report['mttr_hours'] is not None else 0.0
                    if mtbf + mttr > 0:
                        availability = (mtbf / (mtbf + mttr)) * 100
                        availability_str = f"{availability:.1f}"
                    else:
                        availability_str = "N/A"

                    em_count = session.query(func.count(WorkOrder.id)).filter(
                        WorkOrder.equipment_id == eq['id'],
                        WorkOrder.type == WorkOrderType.EMERGENCY
                    )
                    if start_date:
                        em_count = em_count.filter(WorkOrder.created_at >= start_date)
                    if end_date:
                        em_count = em_count.filter(WorkOrder.created_at <= end_date)
                    em_count = em_count.scalar() or 0

                    self.equipment_tree.insert("", tk.END, values=(
                        report['equipment_id'], report['equipment_name'], report['equipment_status'],
                        report['total_work_orders'], report['completed_work_orders'],
                        report['pm_work_orders'], report['cm_work_orders'],
                        em_count,
                        f"{mtbf:.1f}", f"{mttr:.1f}",
                        availability_str,
                        f"{report['total_downtime_hours']:.1f}"
                    ))

    # -------------------- Enhanced Equipment Detail Dialog --------------------
    def _open_equipment_detail(self, event):
        selection = self.equipment_tree.selection()
        if not selection:
            return
        item = self.equipment_tree.item(selection[0])
        equipment_id = item['values'][0]
        # Fetch full equipment details from equipment repository
        eq_data = self.eq_repo.get_equipment_by_id(equipment_id)
        if not eq_data:
            messagebox.showerror("خطا", "تجهیز یافت نشد")
            return

        dialog = tk.Toplevel(self)
        dialog.title(f"گزارش تفصیلی تجهیز - {eq_data['name']}")
        dialog.geometry("900x700")
        dialog.configure(bg="#F0F4F8")

        # Notebook for tabs
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: اطلاعات پایه و عملکرد
        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="اطلاعات و عملکرد")

        # Scrollable frame for main tab
        canvas = tk.Canvas(main_frame, bg="#F0F4F8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Equipment basic info
        info_frame = ttk.LabelFrame(scrollable, text="مشخصات اصلی", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        fields = [
            ("کد تجهیز:", eq_data.get("code", "—")),
            ("نام تجهیز:", eq_data.get("name", "—")),
            ("دسته‌بندی:", eq_data.get("category", "—")),
            ("سازنده:", eq_data.get("manufacturer", "—")),
            ("مدل:", eq_data.get("model", "—")),
            ("شماره سریال:", eq_data.get("serial_number", "—")),
            ("موقعیت:", eq_data.get("location", "—")),
            ("تاریخ نصب:", eq_data.get("installation_date", "—")),
            ("وضعیت:", STATUS_FA.get(eq_data.get("status", ""), eq_data.get("status", "—"))),
        ]
        for i, (label, value) in enumerate(fields):
            ttk.Label(info_frame, text=label, font=("Tahoma", 10, "bold")).grid(row=i, column=0, sticky="e", padx=5, pady=3)
            ttk.Label(info_frame, text=value, font=("Tahoma", 10)).grid(row=i, column=1, sticky="w", padx=5, pady=3)

        # Specifications (مشخصات فنی)
        specs_frame = ttk.LabelFrame(scrollable, text="مشخصات فنی", padding=10)
        specs_frame.pack(fill=tk.X, padx=10, pady=5)
        specs_text = eq_data.get("specifications", "") or "—"
        ttk.Label(specs_frame, text=specs_text, font=("Tahoma", 9), wraplength=700, justify="right").pack(anchor="w")

        # Notes (یادداشت)
        notes_frame = ttk.LabelFrame(scrollable, text="یادداشت‌ها", padding=10)
        notes_frame.pack(fill=tk.X, padx=10, pady=5)
        notes_text = eq_data.get("notes", "") or "—"
        ttk.Label(notes_frame, text=notes_text, font=("Tahoma", 9), wraplength=700, justify="right").pack(anchor="w")

        # KPI from report repository (using cached report)
        report = self.report_repo.get_equipment_report(equipment_id, self.start_date.get_date(), self.end_date.get_date())
        if report:
            kpi_frame = ttk.LabelFrame(scrollable, text="شاخص‌های عملکردی", padding=10)
            kpi_frame.pack(fill=tk.X, padx=10, pady=5)
            kpis = [
                ("کل دستورات کار:", report['total_work_orders']),
                ("تکمیل شده:", report['completed_work_orders']),
                ("PM:", report['pm_work_orders']),
                ("CM:", report['cm_work_orders']),
                ("میانگین زمان تعمیر (ساعت):", f"{report['avg_repair_time_hours']:.2f}"),
                ("کل زمان توقف (ساعت):", f"{report['total_downtime_hours']:.2f}"),
                ("انطباق PM (%):", f"{report['pm_compliance_rate']:.1f}"),
                ("MTBF (ساعت):", f"{report['mtbf_hours']:.2f}"),
                ("MTTR (ساعت):", f"{report['mttr_hours']:.2f}"),
                ("تعداد خرابی:", report['failure_count'])
            ]
            for i, (label, value) in enumerate(kpis):
                ttk.Label(kpi_frame, text=label, font=("Tahoma", 10, "bold")).grid(row=i, column=0, sticky="e", padx=5, pady=3)
                ttk.Label(kpi_frame, text=value, font=("Tahoma", 10)).grid(row=i, column=1, sticky="w", padx=5, pady=3)

        # Tab 2: نمودارها
        chart_frame = ttk.Frame(notebook)
        notebook.add(chart_frame, text="نمودارها")
        fig = Figure(figsize=(8,6))
        ax1 = fig.add_subplot(121)
        if report and (report['pm_work_orders'] > 0 or report['cm_work_orders'] > 0):
            ax1.pie([report['pm_work_orders'], report['cm_work_orders']], labels=['PM','CM'], autopct='%1.1f%%', colors=['#4CAF50','#F44336'])
            ax1.set_title('PM vs CM Distribution')
        else:
            ax1.text(0.5,0.5,'No Data', ha='center', va='center')
        ax2 = fig.add_subplot(122)
        if report:
            metrics = ['MTBF','MTTR','Downtime']
            values = [report['mtbf_hours'], report['mttr_hours'], report['total_downtime_hours']]
            ax2.bar(metrics, values, color=['#2196F3','#FF9800','#F44336'])
            ax2.set_ylabel('Hours')
            ax2.set_title('Key Metrics')
        else:
            ax2.text(0.5,0.5,'No Data', ha='center', va='center')
        canvas_chart = FigureCanvasTkAgg(fig, chart_frame)
        canvas_chart.draw()
        canvas_chart.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Button(dialog, text="بستن", command=dialog.destroy).pack(pady=10)

    # -------------------- KPI Analysis Tab --------------------
    def _load_kpi_analysis(self, start_date, end_date):
        for w in self.kpi_frame.winfo_children():
            if not isinstance(w, ttk.Frame) or w != self.kpi_frame.winfo_children()[0]:
                w.destroy()
        canvas = tk.Canvas(self.kpi_frame, bg="#F0F4F8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.kpi_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # PM/CM/EM Ratio
        pm_cm = self.report_repo.get_pm_cm_ratio(start_date, end_date)
        fig1 = Figure(figsize=(8, 4))
        ax1 = fig1.add_subplot(111)
        if pm_cm['preventive_count'] > 0 or pm_cm['corrective_count'] > 0 or pm_cm['emergency_count'] > 0:
            categories = ['Preventive (PM)', 'Corrective (CM)', 'Emergency (EM)']
            values = [pm_cm['preventive_count'], pm_cm['corrective_count'], pm_cm['emergency_count']]
            ax1.bar(categories, values, color=['#4CAF50', '#F44336', '#FF9800'])
            ax1.set_ylabel('Count')
            ax1.set_title(f"PM/CM/EM Ratio (PM/CM = {pm_cm['ratio']:.2f})")
            ax1.grid(True, alpha=0.3)
        else:
            ax1.text(0.5, 0.5, 'No Data', ha='center', va='center')
        canvas1 = FigureCanvasTkAgg(fig1, scrollable)
        canvas1.draw()
        canvas1.get_tk_widget().pack(pady=10)

        # Schedule Compliance
        compliance = self.report_repo.get_schedule_compliance(start_date, end_date)
        fig2 = Figure(figsize=(8,4))
        ax2 = fig2.add_subplot(111)
        if compliance['on_time'] > 0 or compliance['late'] > 0:
            ax2.pie([compliance['on_time'], compliance['late']], labels=['On Time', 'Late'], autopct='%1.1f%%', colors=['#4CAF50','#F44336'])
            ax2.set_title(f"Schedule Compliance: {compliance['compliance_rate']:.1f}%")
        else:
            ax2.text(0.5,0.5,'No Data', ha='center', va='center')
        canvas2 = FigureCanvasTkAgg(fig2, scrollable)
        canvas2.draw()
        canvas2.get_tk_widget().pack(pady=10)

        # Risk Score Table
        risk_data = self.report_repo.get_equipment_risk_score()
        if risk_data:
            tree_frame = ttk.Frame(scrollable)
            tree_frame.pack(fill=tk.X, pady=10)
            risk_tree = ttk.Treeview(tree_frame, columns=("name","risk","level","failures","downtime"), show="headings", height=8)
            risk_tree.heading("name", text="تجهیز")
            risk_tree.heading("risk", text="امتیاز ریسک")
            risk_tree.heading("level", text="سطح")
            risk_tree.heading("failures", text="خرابی‌ها")
            risk_tree.heading("downtime", text="زمان توقف (ساعت)")
            for col in ("name","risk","level","failures","downtime"):
                risk_tree.column(col, width=120)
            for item in risk_data:
                risk_tree.insert("", tk.END, values=(item['equipment_name'], f"{item['risk_score']:.1f}", item['risk_level'], item['failure_count'], f"{item['avg_downtime_hours']:.1f}"))
            risk_tree.pack(fill=tk.X)

    # -------------------- Cost Analysis Tab --------------------
    def _load_cost_analysis(self, start_date, end_date):
        for w in self.cost_frame.winfo_children():
            if not isinstance(w, ttk.Frame) or w != self.cost_frame.winfo_children()[0]:
                w.destroy()
        cost_data = self.report_repo.get_cost_analysis(start_date, end_date)
        if cost_data['breakdown'] and len(cost_data['breakdown']) > 0:
            fig = Figure(figsize=(8,6))
            ax = fig.add_subplot(111)
            labels = [d['type'] for d in cost_data['breakdown']]
            sizes = [d['total_cost'] for d in cost_data['breakdown']]
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
            ax.set_title(f"Cost Distribution (Total: {cost_data['total_cost']:,.0f} Rials)")
            canvas = FigureCanvasTkAgg(fig, self.cost_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        else:
            ttk.Label(self.cost_frame, text="داده‌ای برای نمایش وجود ندارد", font=("Tahoma",12)).pack(pady=50)

    # -------------------- Technician Performance Tab --------------------
    def _load_technician_performance(self, start_date, end_date):
        for w in self.tech_frame.winfo_children():
            if not isinstance(w, ttk.Frame) or w != self.tech_frame.winfo_children()[0]:
                w.destroy()
        tech_data = self.report_repo.get_technician_performance(start_date, end_date)
        if not tech_data:
            ttk.Label(self.tech_frame, text="داده‌ای برای نمایش وجود ندارد", font=("Tahoma",12)).pack(pady=50)
            return
        tree = ttk.Treeview(self.tech_frame, columns=("name","total","completed","rate","avg_time"), show="headings", height=15)
        tree.heading("name", text="تکنسین")
        tree.heading("total", text="کل وظایف")
        tree.heading("completed", text="تکمیل شده")
        tree.heading("rate", text="نرخ تکمیل (%)")
        tree.heading("avg_time", text="میانگین زمان (ساعت)")
        for col, w in [("name",200),("total",100),("completed",120),("rate",120),("avg_time",150)]:
            tree.column(col, width=w)
        for item in tech_data:
            tree.insert("", tk.END, values=(item['technician_name'], item['total_tasks'], item['completed_tasks'], f"{item['completion_rate']:.1f}", f"{item['avg_completion_hours']:.1f}"))
        self.tech_tree = tree
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # -------------------- Trends Tab --------------------
    def _load_trends(self):
        for w in self.trend_frame.winfo_children():
            if not isinstance(w, ttk.Frame) or w != self.trend_frame.winfo_children()[0]:
                w.destroy()
        trend_data = self.report_repo.get_monthly_trends(6)
        if not trend_data:
            ttk.Label(self.trend_frame, text="داده‌ای برای نمایش وجود ندارد", font=("Tahoma",12)).pack(pady=50)
            return
        fig = Figure(figsize=(10,6))
        ax = fig.add_subplot(111)
        months = {}
        for item in trend_data:
            key = f"{item['year']}-{item['month']:02d}"
            if key not in months:
                months[key] = {'PREVENTIVE':0, 'PM':0, 'CORRECTIVE':0, 'EMERGENCY':0}
            typ = item['type']
            if typ in months[key]:
                months[key][typ] += item['count']
        x = list(months.keys())
        preventive = [months[m].get('PREVENTIVE',0) + months[m].get('PM',0) for m in x]
        corrective = [months[m].get('CORRECTIVE',0) for m in x]
        emergency = [months[m].get('EMERGENCY',0) for m in x]
        ax.plot(x, preventive, marker='o', label='Preventive', color='#4CAF50')
        ax.plot(x, corrective, marker='s', label='Corrective', color='#F44336')
        ax.plot(x, emergency, marker='^', label='Emergency', color='#FF9800')
        ax.set_xlabel('Month')
        ax.set_ylabel('Count')
        ax.set_title('Work Order Trends (Last 6 Months)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        canvas = FigureCanvasTkAgg(fig, self.trend_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # -------------------- Export Methods --------------------
    def _export_tab_to_excel(self, frame, tab_title):
        data = self._collect_tab_data(frame, tab_title)
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"{tab_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        if filename:
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False)
            messagebox.showinfo("موفق", f"خروجی Excel با موفقیت ذخیره شد!")

    def _collect_tab_data(self, frame, tab_title):
        data = []
        if tab_title == "عملکرد تجهیزات":
            for child in self.equipment_tree.get_children():
                values = self.equipment_tree.item(child)['values']
                data.append({
                    "ID": values[0],
                    "نام تجهیز": values[1],
                    "وضعیت": values[2],
                    "کل WO": values[3],
                    "تکمیل شده": values[4],
                    "PM": values[5],
                    "CM": values[6],
                    "EM": values[7],
                    "MTBF (ساعت)": values[8],
                    "MTTR (ساعت)": values[9],
                    "در دسترس بودن (%)": values[10],
                    "زمان توقف (ساعت)": values[11]
                })
        elif tab_title == "عملکرد تکنسین‌ها" and hasattr(self, 'tech_tree'):
            for child in self.tech_tree.get_children():
                values = self.tech_tree.item(child)['values']
                data.append({
                    "تکنسین": values[0],
                    "کل وظایف": values[1],
                    "تکمیل شده": values[2],
                    "نرخ تکمیل (%)": values[3],
                    "میانگین زمان (ساعت)": values[4]
                })
        elif tab_title == "داشبورد کلی":
            summary = self.report_repo.get_kpi_summary()
            backlog = self.report_repo.get_backlog_analysis()
            data.append({
                "کل دستورات کار": summary['total_work_orders'],
                "تکمیل شده": summary['completed_work_orders'],
                "در حال انجام": summary['in_progress_work_orders'],
                "معوق": summary['overdue_work_orders'],
                "کل تجهیزات": summary['total_equipment'],
                "عملیاتی": summary['operational_equipment'],
                "میانگین زمان تعمیر (ساعت)": summary['avg_completion_time_hours'],
                "انطباق PM (%)": summary['pm_compliance_rate'],
                "در انتظار": backlog['pending'],
                "در حال انجام (بک‌لاگ)": backlog['in_progress'],
                "سررسید گذشته": backlog['overdue'],
                "کل معوقات": backlog['total_backlog']
            })
        elif tab_title == "تحلیل KPI":
            start = self.start_date.get_date()
            end = self.end_date.get_date()
            pm_cm = self.report_repo.get_pm_cm_ratio(start, end)
            compliance = self.report_repo.get_schedule_compliance(start, end)
            risk = self.report_repo.get_equipment_risk_score()
            data.append({
                "PM": pm_cm['preventive_count'],
                "CM": pm_cm['corrective_count'],
                "EM": pm_cm['emergency_count'],
                "نسبت PM/CM": pm_cm['ratio'],
                "کل وظایف برنامه": compliance['total_tasks'],
                "انجام به موقع": compliance['on_time'],
                "تاخیر": compliance['late'],
                "نرخ انطباق (%)": compliance['compliance_rate']
            })
            for r in risk[:10]:
                data.append({"تجهیز": r['equipment_name'], "امتیاز ریسک": r['risk_score'], "سطح": r['risk_level']})
        elif tab_title == "تحلیل هزینه":
            start = self.start_date.get_date()
            end = self.end_date.get_date()
            cost = self.report_repo.get_cost_analysis(start, end)
            for item in cost['breakdown']:
                data.append({
                    "نوع": item['type'],
                    "هزینه کل": item['total_cost'],
                    "درصد": item['percentage'],
                    "هزینه قطعات": item['part_cost'],
                    "هزینه نیروی کار": item['labor_cost']
                })
        elif tab_title == "روندها":
            trend = self.report_repo.get_monthly_trends(6)
            for item in trend:
                data.append({
                    "سال": item['year'],
                    "ماه": item['month'],
                    "نوع": item['type'],
                    "تعداد": item['count']
                })
        return data

