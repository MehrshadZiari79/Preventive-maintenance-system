# views/reports_view.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import func

from database.report_repository import ReportRepository
from database.equipment_repository import EquipmentRepository
from database.work_order import WorkOrder, WorkOrderType, WorkOrderStatus

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
        self.notebook.add(self.kpi_frame, text=" تحلیل-KPI")

        self.cost_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.cost_frame, text="تحلیل هزینه")

        self.tech_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tech_frame, text="عملکرد تکنسین‌ها")


        self.failure_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.failure_frame, text="تحلیل خرابی‌ها")

        self._add_tab_export_buttons()

    def _add_tab_export_buttons(self):
        tabs = [
            (self.overview_frame, "داشبورد کلی"),
            (self.equipment_frame, "عملکرد تجهیزات"),
            (self.kpi_frame, " تحلیل-KPI"),
            (self.cost_frame, "تحلیل هزینه"),
            (self.tech_frame, "عملکرد تکنسین‌ها"),
            (self.failure_frame, "تحلیل خرابی‌ها"),
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
        self._load_failure_analysis(start, end)

    # -------------------- Overview Dashboard --------------------
    def _load_overview_dashboard(self):
        for w in self.overview_frame.winfo_children():
            if isinstance(w, ttk.Frame) and w != self.overview_frame.winfo_children()[
                0] if self.overview_frame.winfo_children() else True:
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
        self._create_kpi_card(scrollable, "کل دستورات کار", f"{summary['total_work_orders']}", "تمام دستورات ثبت شده",
                              row, 0, '#2196F3')
        comp_pct = (summary['completed_work_orders'] / summary['total_work_orders'] * 100) if summary[
                                                                                                  'total_work_orders'] > 0 else 0
        self._create_kpi_card(scrollable, "تکمیل شده", f"{summary['completed_work_orders']}", f"{comp_pct:.1f}% از کل",
                              row, 1, '#4CAF50')
        self._create_kpi_card(scrollable, "در حال انجام", f"{summary['in_progress_work_orders']}", "دستورات فعال", row,
                              2, '#FF9800')
        self._create_kpi_card(scrollable, "معوق", f"{summary['overdue_work_orders']}", "نیاز به توجه فوری", row, 3,
                              '#F44336')
        row += 1

        self._create_kpi_card(scrollable, "کل تجهیزات", f"{summary['total_equipment']}", "تجهیزات ثبت شده", row, 0,
                              '#9C27B0')
        op_pct = (summary['operational_equipment'] / summary['total_equipment'] * 100) if summary[
                                                                                              'total_equipment'] > 0 else 0
        self._create_kpi_card(scrollable, "عملیاتی", f"{summary['operational_equipment']}", f"{op_pct:.1f}% آماده", row,
                              1, '#00BCD4')
        self._create_kpi_card(scrollable, "میانگین زمان تعمیر", f"{summary['avg_completion_time_hours']:.1f}", "ساعت",
                              row, 2, '#795548')
        self._create_kpi_card(scrollable, "انطباق PM", f"{summary['pm_compliance_rate']:.1f}%", "نگهداری پیشگیرانه",
                              row, 3, '#607D8B')
        row += 1

        ttk.Label(scrollable, text="تحلیل کارهای معوق", font=("Tahoma", 12, "bold")).grid(row=row, column=0,
                                                                                          columnspan=4, pady=(20, 10),
                                                                                          sticky=tk.W)
        row += 1
        self._create_kpi_card(scrollable, "در انتظار", f"{backlog['pending']}", "دستورات معلق", row, 0, '#FFC107')
        self._create_kpi_card(scrollable, "در حال انجام", f"{backlog['in_progress']}", "در دست اقدام", row, 1,
                              '#03A9F4')
        self._create_kpi_card(scrollable, "سررسید گذشته", f"{backlog['overdue']}", "نیاز به اقدام فوری", row, 2,
                              '#E91E63')
        self._create_kpi_card(scrollable, "کل معوقات", f"{backlog['total_backlog']}", "مجموع کارهای باز", row, 3,
                              '#673AB7')

    def _create_kpi_card(self, parent, title, value, subtitle, row, col, bg):
        card = tk.Frame(parent, bg=bg, relief=tk.RAISED, borderwidth=2)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew", ipadx=20, ipady=15)
        parent.grid_columnconfigure(col, weight=1)
        ttk.Label(card, text=title, font=("Tahoma", 10), background=bg, foreground='white').pack(pady=(5, 0))
        ttk.Label(card, text=value, font=("Tahoma", 24, "bold"), background=bg, foreground='white').pack()
        ttk.Label(card, text=subtitle, font=("Tahoma", 8), background=bg, foreground='white').pack(pady=(0, 5))

    # -------------------- Equipment Performance Tab (with OEE) --------------------
    def _load_equipment_performance(self, start_date=None, end_date=None):
        for w in self.equipment_frame.winfo_children():
            if not isinstance(w, ttk.Frame) or w != self.equipment_frame.winfo_children()[0]:
                w.destroy()
        tree_frame = ttk.Frame(self.equipment_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ("id", "name", "status", "total_wo", "completed", "pm", "cm", "em", "mtbf", "mttr", "availability",
                   "oee", "downtime")
        self.equipment_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        col_defs = [
            ("id", "ID", 50), ("name", "نام تجهیز", 200), ("status", "وضعیت", 100),
            ("total_wo", "کل WO", 80), ("completed", "تکمیل شده", 100), ("pm", "PM", 60),
            ("cm", "CM", 60), ("em", "EM", 60), ("mtbf", "MTBF (ساعت)", 100),
            ("mttr", "MTTR (ساعت)", 100), ("availability", "در دسترس بودن (%)", 100),
            ("oee", "OEE (%)", 100), ("downtime", "زمان توقف (ساعت)", 120)
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
                    mtbf = float(report['mtbf_hours']) if report['mtbf_hours'] is not None else 0.0
                    mttr = float(report['mttr_hours']) if report['mttr_hours'] is not None else 0.0
                    availability_value = 0.0
                    availability_str = "N/A"
                    if mtbf + mttr > 0:
                        availability_value = (mtbf / (mtbf + mttr)) * 100
                        availability_str = f"{availability_value:.1f}"

                    # OEE: Availability * Performance * Quality
                    performance = 95.0  # placeholder, can be refined
                    quality = self.report_repo._get_inspection_pass_rate(session, eq['id'], start_date, end_date)
                    if quality is None:
                        quality = 100.0
                    oee_value = (availability_value * performance * quality) / 10000
                    oee_str = f"{oee_value:.1f}" if oee_value > 0 else "N/A"

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
                        oee_str,
                        f"{report['total_downtime_hours']:.1f}"
                    ))

    # -------------------- Equipment Detail Dialog --------------------
    def _open_equipment_detail(self, event):
        selection = self.equipment_tree.selection()
        if not selection:
            return
        item = self.equipment_tree.item(selection[0])
        equipment_id = item['values'][0]
        eq_data = self.eq_repo.get_equipment_by_id(equipment_id)
        if not eq_data:
            messagebox.showerror("خطا", "تجهیز یافت نشد")
            return

        dialog = tk.Toplevel(self)
        dialog.title(f"گزارش تفصیلی تجهیز - {eq_data['name']}")
        dialog.geometry("1000x750")
        dialog.configure(bg="#F0F4F8")

        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: اطلاعات پایه و عملکرد
        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="اطلاعات و عملکرد")

        canvas = tk.Canvas(main_frame, bg="#F0F4F8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

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
            ttk.Label(info_frame, text=label, font=("Tahoma", 10, "bold")).grid(row=i, column=0, sticky="e", padx=5,
                                                                                pady=3)
            ttk.Label(info_frame, text=value, font=("Tahoma", 10)).grid(row=i, column=1, sticky="w", padx=5, pady=3)

        specs_frame = ttk.LabelFrame(scrollable, text="مشخصات فنی", padding=10)
        specs_frame.pack(fill=tk.X, padx=10, pady=5)
        specs_text = eq_data.get("specifications", "") or "—"
        ttk.Label(specs_frame, text=specs_text, font=("Tahoma", 9), wraplength=700, justify="right").pack(anchor="w")

        notes_frame = ttk.LabelFrame(scrollable, text="یادداشت‌ها", padding=10)
        notes_frame.pack(fill=tk.X, padx=10, pady=5)
        notes_text = eq_data.get("notes", "") or "—"
        ttk.Label(notes_frame, text=notes_text, font=("Tahoma", 9), wraplength=700, justify="right").pack(anchor="w")

        report = self.report_repo.get_equipment_report(equipment_id, self.start_date.get_date(),
                                                       self.end_date.get_date())
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
                ttk.Label(kpi_frame, text=label, font=("Tahoma", 10, "bold")).grid(row=i, column=0, sticky="e", padx=5,
                                                                                   pady=3)
                ttk.Label(kpi_frame, text=value, font=("Tahoma", 10)).grid(row=i, column=1, sticky="w", padx=5, pady=3)

        # Tab 2: نمودارها
        chart_frame = ttk.Frame(notebook)
        notebook.add(chart_frame, text="نمودارها")
        fig = Figure(figsize=(10, 6))
        ax1 = fig.add_subplot(121)
        if report:
            pm = report['pm_work_orders']
            cm = report['cm_work_orders']
            with self.report_repo._session() as session:
                em_count = session.query(func.count(WorkOrder.id)).filter(
                    WorkOrder.equipment_id == equipment_id,
                    WorkOrder.type == WorkOrderType.EMERGENCY,
                    WorkOrder.status == WorkOrderStatus.COMPLETED
                )
                if self.start_date.get_date():
                    em_count = em_count.filter(WorkOrder.created_at >= self.start_date.get_date())
                if self.end_date.get_date():
                    em_count = em_count.filter(WorkOrder.created_at <= self.end_date.get_date())
                em_count = em_count.scalar() or 0
            if pm + cm + em_count > 0:
                ax1.pie([pm, cm, em_count], labels=['PM', 'CM', 'EM'], autopct='%1.1f%%',
                        colors=['#4CAF50', '#F44336', '#FF9800'])
                ax1.set_title('Comparison (PM/CM/EM)')
            else:
                ax1.text(0.5, 0.5, 'No Data', ha='center', va='center')
        else:
            ax1.text(0.5, 0.5, 'No Data', ha='center', va='center')

        ax2 = fig.add_subplot(122)
        if report:
            metrics = ['MTBF', 'MTTR', 'Downtime']
            values = [report['mtbf_hours'], report['mttr_hours'], report['total_downtime_hours']]
            ax2.bar(metrics, values, color=['#2196F3', '#FF9800', '#F44336'])
            ax2.set_ylabel('Hours')
            ax2.set_title('Key Metrics')
        else:
            ax2.text(0.5, 0.5, 'No Data', ha='center', va='center')
        canvas_chart = FigureCanvasTkAgg(fig, chart_frame)
        canvas_chart.draw()
        canvas_chart.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 3: یادداشت‌های دستورکارها
        notes_tab = ttk.Frame(notebook)
        notebook.add(notes_tab, text="یادداشت دستورکارها")
        wo_tree_frame = ttk.Frame(notes_tab)
        wo_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        wo_columns = ("id", "title", "type", "status", "operator_notes", "technician_notes", "part_notes")
        wo_tree = ttk.Treeview(wo_tree_frame, columns=wo_columns, show="headings", height=20)
        wo_tree.heading("id", text="شناسه")
        wo_tree.heading("title", text="عنوان")
        wo_tree.heading("type", text="نوع")
        wo_tree.heading("status", text="وضعیت")
        wo_tree.heading("operator_notes", text="یادداشت اپراتور")
        wo_tree.heading("technician_notes", text="توضیحات تکنسین")
        wo_tree.heading("part_notes", text="قطعات مصرفی")
        wo_tree.column("id", width=60)
        wo_tree.column("title", width=200)
        wo_tree.column("type", width=100)
        wo_tree.column("status", width=100)
        wo_tree.column("operator_notes", width=250)
        wo_tree.column("technician_notes", width=250)
        wo_tree.column("part_notes", width=200)
        vsb = ttk.Scrollbar(wo_tree_frame, orient="vertical", command=wo_tree.yview)
        wo_tree.configure(yscrollcommand=vsb.set)
        wo_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        from database.work_order_repository import WorkOrderRepository
        wo_repo = WorkOrderRepository()
        work_orders = wo_repo.get_all()
        eq_work_orders = [wo for wo in work_orders if wo.equipment_id == equipment_id]
        type_fa = {"PREVENTIVE": "پیشگیرانه", "CORRECTIVE": "اصلاحی", "EMERGENCY": "اضطراری", "INSPECTION": "بازرسی",
                   "PM": "PM"}
        status_fa = {
            "PENDING": "در انتظار", "IN_PROGRESS": "در حال انجام", "COMPLETED": "تکمیل شده",
            "APPROVED": "تایید شده", "REJECTED": "رد شده"
        }
        for wo in eq_work_orders:
            operator_notes = wo.operator_notes or "—"
            technician_notes = wo.description or "—"
            part_notes = wo.parts_used or "—"
            wo_tree.insert("", tk.END, values=(
                wo.id, wo.title,
                type_fa.get(wo.type.name, wo.type.name),
                status_fa.get(wo.status.name, wo.status.name),
                operator_notes, technician_notes, part_notes
            ))
        ttk.Button(dialog, text="بستن", command=dialog.destroy).pack(pady=10)

    # -------------------- KPI Analysis Tab (Monthly grouped bar chart) --------------------
    def _load_kpi_analysis(self, start_date, end_date):
        for w in self.kpi_frame.winfo_children():
            if not isinstance(w, ttk.Frame) or w != self.kpi_frame.winfo_children()[0]:
                w.destroy()
        canvas = tk.Canvas(self.kpi_frame, bg="#F0F4F8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.kpi_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        trend_data = self.report_repo.get_monthly_trends(6)
        if trend_data:
            months_dict = {}
            for item in trend_data:
                key = f"{item['year']}-{item['month']:02d}"
                if key not in months_dict:
                    months_dict[key] = {'PM': 0, 'CM': 0, 'EM': 0}
                typ = item['type']
                if typ in ('PREVENTIVE', 'PM'):
                    months_dict[key]['PM'] += item['count']
                elif typ == 'CORRECTIVE':
                    months_dict[key]['CM'] += item['count']
                elif typ == 'EMERGENCY':
                    months_dict[key]['EM'] += item['count']
            sorted_months = sorted(months_dict.keys())
            x_labels = sorted_months
            pm_counts = [months_dict[m]['PM'] for m in sorted_months]
            cm_counts = [months_dict[m]['CM'] for m in sorted_months]
            em_counts = [months_dict[m]['EM'] for m in sorted_months]

            fig1 = Figure(figsize=(10, 5))
            ax1 = fig1.add_subplot(111)
            x = np.arange(len(x_labels))
            width = 0.25
            ax1.bar(x - width, pm_counts, width, label='PM', color='#4CAF50')
            ax1.bar(x, cm_counts, width, label='CM', color='#F44336')
            ax1.bar(x + width, em_counts, width, label='EM', color='#FF9800')
            ax1.set_xticks(x)
            ax1.set_xticklabels(x_labels, rotation=45)
            ax1.set_ylabel('Count')
            ax1.set_title('Monthly PM / CM / EM Comparison', fontsize=12, fontweight='bold')
            ax1.legend()
            ax1.grid(True, axis='y', alpha=0.3)
            canvas1 = FigureCanvasTkAgg(fig1, scrollable)
            canvas1.draw()
            canvas1.get_tk_widget().pack(pady=10)
        else:
            tk.Label(scrollable, text="داده‌ای برای نمایش وجود ندارد", font=("Tahoma", 12)).pack(pady=20)

        compliance = self.report_repo.get_schedule_compliance(start_date, end_date)
        fig2 = Figure(figsize=(8, 4))
        ax2 = fig2.add_subplot(111)
        if compliance['on_time'] > 0 or compliance['late'] > 0:
            ax2.pie([compliance['on_time'], compliance['late']], labels=['On Time', 'Late'],
                    autopct='%1.1f%%', colors=['#4CAF50', '#F44336'])
            ax2.set_title(f"Schedule Compliance: {compliance['compliance_rate']:.1f}%")
        else:
            ax2.text(0.5, 0.5, 'No Data', ha='center', va='center')
        canvas2 = FigureCanvasTkAgg(fig2, scrollable)
        canvas2.draw()
        canvas2.get_tk_widget().pack(pady=10)

        risk_data = self.report_repo.get_equipment_risk_score()
        if risk_data:
            tree_frame = ttk.Frame(scrollable)
            tree_frame.pack(fill=tk.X, pady=10)
            risk_tree = ttk.Treeview(tree_frame, columns=("name", "risk", "level", "failures", "downtime"),
                                     show="headings", height=8)
            risk_tree.heading("name", text="تجهیز")
            risk_tree.heading("risk", text="امتیاز ریسک")
            risk_tree.heading("level", text="سطح")
            risk_tree.heading("failures", text="خرابی‌ها")
            risk_tree.heading("downtime", text="زمان توقف (ساعت)")
            for col in ("name", "risk", "level", "failures", "downtime"):
                risk_tree.column(col, width=120)
            for item in risk_data:
                risk_tree.insert("", tk.END,
                                 values=(item['equipment_name'], f"{item['risk_score']:.1f}", item['risk_level'],
                                         item['failure_count'], f"{item['avg_downtime_hours']:.1f}"))
            risk_tree.pack(fill=tk.X)

    # -------------------- Cost Analysis Tab --------------------
    def _load_cost_analysis(self, start_date, end_date):
        for w in self.cost_frame.winfo_children():
            if not isinstance(w, ttk.Frame) or w != self.cost_frame.winfo_children()[0]:
                w.destroy()
        cost_data = self.report_repo.get_cost_analysis(start_date, end_date)
        if cost_data['breakdown'] and len(cost_data['breakdown']) > 0:
            fig = Figure(figsize=(8, 6))
            ax = fig.add_subplot(111)
            labels = [d['type'] for d in cost_data['breakdown']]
            sizes = [d['total_cost'] for d in cost_data['breakdown']]
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
            ax.set_title(f"Cost Distribution (Total: {cost_data['total_cost']:,.0f} Rials)")
            canvas = FigureCanvasTkAgg(fig, self.cost_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        else:
            ttk.Label(self.cost_frame, text="داده‌ای برای نمایش وجود ندارد", font=("Tahoma", 12)).pack(pady=50)

    # -------------------- Technician Performance Tab --------------------
    def _load_technician_performance(self, start_date, end_date):
        for w in self.tech_frame.winfo_children():
            if not isinstance(w, ttk.Frame) or w != self.tech_frame.winfo_children()[0]:
                w.destroy()
        tech_data = self.report_repo.get_technician_performance(start_date, end_date)
        if not tech_data:
            ttk.Label(self.tech_frame, text="داده‌ای برای نمایش وجود ندارد", font=("Tahoma", 12)).pack(pady=50)
            return
        tree = ttk.Treeview(self.tech_frame, columns=("name", "total", "completed", "rate", "avg_time"),
                            show="headings", height=15)
        tree.heading("name", text="تکنسین")
        tree.heading("total", text="کل وظایف")
        tree.heading("completed", text="تکمیل شده")
        tree.heading("rate", text="نرخ تکمیل (%)")
        tree.heading("avg_time", text="میانگین زمان (ساعت)")
        for col, w in [("name", 200), ("total", 100), ("completed", 120), ("rate", 120), ("avg_time", 150)]:
            tree.column(col, width=w)
        for item in tech_data:
            tree.insert("", tk.END, values=(item['technician_name'], item['total_tasks'], item['completed_tasks'],
                                            f"{item['completion_rate']:.1f}", f"{item['avg_completion_hours']:.1f}"))
        self.tech_tree = tree
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # -------------------- Failure Analysis Tab --------------------
    def _load_failure_analysis(self, start_date, end_date):
        for w in self.failure_frame.winfo_children():
            w.destroy()

        top_failures = self.report_repo.get_top_failure_modes(start_date, end_date, limit=10)
        if not top_failures:
            tk.Label(self.failure_frame, text="هیچ خرابی ثبت نشده است.", font=("Tahoma", 12)).pack(pady=50)
            return

        tree_frame = ttk.Frame(self.failure_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        columns = ("description", "count")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
        tree.heading("description", text="توضیحات خرابی")
        tree.heading("count", text="تعداد تکرار")
        tree.column("description", width=600)
        tree.column("count", width=100, anchor="center")
        for item in top_failures:
            tree.insert("", tk.END, values=(item['description'], item['count']))
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # -------------------- Excel Export --------------------
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
            cell.fill = PatternFill(start_color="1A73E8", end_color="1A73E8", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[1].height = 30
            ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max_cols)
            title_cell = ws.cell(row=2, column=1, value=tab_title)
            title_cell.font = Font(name="Tahoma", size=14, bold=True, color="1A73E8")
            title_cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[2].height = 25
            start = self.start_date.get_date().strftime("%Y-%m-%d")
            end = self.end_date.get_date().strftime("%Y-%m-%d")
            ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=max_cols)
            info_cell = ws.cell(row=3, column=1,
                                value=f"بازه گزارش: {start} تا {end}  |  تاریخ تهیه: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            info_cell.font = Font(name="Tahoma", size=9, italic=True, color="5F6368")
            info_cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[3].height = 20
            rows = [[str(row.get(h, "")) for h in headers] for row in data]
            header_row = 5
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=header_row, column=col_idx, value=header)
                cell.font = Font(name="Tahoma", size=10, bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"),
                                     bottom=Side(style="thin"))
            ws.row_dimensions[header_row].height = 28
            for row_idx, row_data in enumerate(rows, start=header_row + 1):
                bg_color = "F5F7FA" if (row_idx % 2 == 0) else "FFFFFF"
                for col_idx, value in enumerate(row_data, 1):
                    cell = ws.cell(row=row_idx, column=col_idx, value=value)
                    cell.font = Font(name="Tahoma", size=9)
                    cell.fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    cell.border = Border(left=Side(style="thin", color="DDDDDD"),
                                         right=Side(style="thin", color="DDDDDD"),
                                         top=Side(style="thin", color="DDDDDD"),
                                         bottom=Side(style="thin", color="DDDDDD"))
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        try:
                            if isinstance(value, float):
                                cell.number_format = "#,##0.00"
                            else:
                                cell.number_format = "#,##0"
                        except:
                            pass
                ws.row_dimensions[row_idx].height = 20
            for col_idx in range(1, len(headers) + 1):
                max_len = 0
                col_letter = get_column_letter(col_idx)
                for row in range(header_row, header_row + len(rows) + 1):
                    val = ws.cell(row=row, column=col_idx).value
                    if val:
                        max_len = max(max_len, len(str(val)))
                ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 50)
            ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
            if tab_title == "عملکرد تجهیزات" and len(rows) > 0:
                numeric_cols = ["کل WO", "تکمیل شده", "PM", "CM", "EM", "MTBF (ساعت)", "MTTR (ساعت)", "OEE (%)",
                                "زمان توقف (ساعت)"]
                summary_row = header_row + len(rows) + 1
                for col_idx, header in enumerate(headers, 1):
                    if header in numeric_cols:
                        total = 0
                        for row_idx in range(header_row + 1, header_row + len(rows) + 1):
                            val = ws.cell(row=row_idx, column=col_idx).value
                            try:
                                total += float(val) if val else 0
                            except:
                                pass
                        cell = ws.cell(row=summary_row, column=col_idx, value=total)
                        cell.font = Font(bold=True)
                        cell.fill = PatternFill(start_color="E8F0FE", end_color="E8F0FE", fill_type="solid")
                    elif col_idx == 1:
                        cell = ws.cell(row=summary_row, column=col_idx, value="جمع کل")
                        cell.font = Font(bold=True)
                        cell.fill = PatternFill(start_color="E8F0FE", end_color="E8F0FE", fill_type="solid")
                ws.row_dimensions[summary_row].height = 22
            wb.save(filename)
            messagebox.showinfo("موفق", "خروجی Excel با موفقیت ذخیره شد!")
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد خروجی: {str(e)}")

    # -------------------- Data Collection for Export --------------------
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
                    "OEE (%)": values[11],
                    "زمان توقف (ساعت)": values[12]
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
        elif tab_title == "تحلیل خرابی‌ها":
            start = self.start_date.get_date()
            end = self.end_date.get_date()
            failures = self.report_repo.get_top_failure_modes(start, end, limit=50)
            for item in failures:
                data.append({
                    "توضیحات خرابی": item['description'],
                    "تعداد تکرار": item['count']
                })
        return data