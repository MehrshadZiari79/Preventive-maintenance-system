# views/reports_view.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import json
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
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

STATUS_FA = {
    "operational": "عملیاتی",
    "maintenance": "در تعمیر",
    "breakdown": "خراب",
    "inactive": "غیرفعال",
}


class ReportsView(ttk.Frame):
    def __init__(self, parent, current_user):
        super().__init__(parent)
        # Only manager or admin can access reports
        if current_user["role"] not in ["admin", "manager"]:
            messagebox.showerror("خطا", "دسترسی غیرمجاز. فقط مدیران می‌توانند گزارشات را مشاهده کنند.", parent=parent)
            self.destroy()
            return
        self.current_user = current_user
        self.report_repo = ReportRepository()
        self.eq_repo = EquipmentRepository()
        self._loading = False

        self._build_ui()
        self._load_dashboard()

    def _build_ui(self):
        # Header
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(title_frame, text="گزارشات و تحلیل‌های پیشرفته", font=FONT_TITLE).pack(side=tk.RIGHT)

        # Filter bar
        filter_frame = ttk.LabelFrame(self, text="فیلترهای تاریخ", padding=10)
        filter_frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(filter_frame, text="از تاریخ:").grid(row=0, column=3, padx=5, sticky="e")
        self.start_date = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd', locale='fa_IR')
        self.start_date.set_date(datetime.now() - timedelta(days=30))
        self.start_date.grid(row=0, column=2, padx=5)

        ttk.Label(filter_frame, text="تا تاریخ:").grid(row=0, column=1, padx=5, sticky="e")
        self.end_date = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd', locale='fa_IR')
        self.end_date.set_date(datetime.now())
        self.end_date.grid(row=0, column=0, padx=5)

        refresh_btn = ttk.Button(filter_frame, text="🔄 بروزرسانی", command=self._refresh_all)
        refresh_btn.grid(row=0, column=4, padx=10)

        # Notebook tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_frame, text="📊 داشبورد کلی")

        self.equipment_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.equipment_frame, text="🛠️ عملکرد تجهیزات")

        self.kpi_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.kpi_frame, text="📈 تحلیل KPI")

        self.cost_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.cost_frame, text="💰 تحلیل هزینه")

        self.tech_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tech_frame, text="👨‍🔧 عملکرد تکنسین‌ها")

        self.failure_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.failure_frame, text="⚠️ تحلیل خرابی‌ها")

        self._add_export_buttons()

    def _add_export_buttons(self):
        tabs = [
            (self.overview_frame, "داشبورد کلی"),
            (self.equipment_frame, "عملکرد تجهیزات"),
            (self.kpi_frame, "تحلیل KPI"),
            (self.cost_frame, "تحلیل هزینه"),
            (self.tech_frame, "عملکرد تکنسین‌ها"),
            (self.failure_frame, "تحلیل خرابی‌ها"),
        ]
        for frame, title in tabs:
            toolbar = ttk.Frame(frame)
            toolbar.pack(fill=tk.X, pady=(0, 10))
            btn = ttk.Button(toolbar, text="📎 خروجی Excel", command=lambda f=frame, t=title: self._export_tab_to_excel(f, t))
            btn.pack(side=tk.LEFT, padx=5)

    def _refresh_all(self):
        if self._loading:
            return
        self._loading = True
        try:
            self._load_dashboard()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در بروزرسانی: {str(e)}")
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

    # ------------------------------------------------------------
    # Overview Dashboard (KPI Cards)
    # ------------------------------------------------------------
    def _load_overview_dashboard(self):
        for child in self.overview_frame.winfo_children():
            if not isinstance(child, ttk.Frame) or child != self.overview_frame.winfo_children()[0]:
                child.destroy()

        canvas = tk.Canvas(self.overview_frame, bg=GRAY_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.overview_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        try:
            summary = self.report_repo.get_kpi_summary()
            backlog = self.report_repo.get_backlog_analysis()
        except Exception as e:
            ttk.Label(scrollable, text=f"خطا در بارگیری داده‌ها: {str(e)}", foreground=RED).pack(pady=20)
            return

        row = 0
        self._create_kpi_card(scrollable, "کل دستورات کار", f"{summary.get('total_work_orders', 0)}", "تمام دستورات ثبت شده", row, 0, NAVY)
        comp_pct = (summary.get('completed_work_orders', 0) / summary.get('total_work_orders', 1) * 100) if summary.get('total_work_orders', 0) > 0 else 0
        self._create_kpi_card(scrollable, "تکمیل شده", f"{summary.get('completed_work_orders', 0)}", f"{comp_pct:.1f}% از کل", row, 1, SUCCESS)
        self._create_kpi_card(scrollable, "در حال انجام", f"{summary.get('in_progress_work_orders', 0)}", "دستورات فعال", row, 2, WARNING)
        self._create_kpi_card(scrollable, "معوق", f"{summary.get('overdue_work_orders', 0)}", "نیاز به توجه فوری", row, 3, RED)
        row += 1

        self._create_kpi_card(scrollable, "کل تجهیزات", f"{summary.get('total_equipment', 0)}", "تجهیزات ثبت شده", row, 0, "#9C27B0")
        op_pct = (summary.get('operational_equipment', 0) / summary.get('total_equipment', 1) * 100) if summary.get('total_equipment', 0) > 0 else 0
        self._create_kpi_card(scrollable, "عملیاتی", f"{summary.get('operational_equipment', 0)}", f"{op_pct:.1f}% آماده", row, 1, "#00BCD4")
        self._create_kpi_card(scrollable, "میانگین زمان تعمیر", f"{summary.get('avg_completion_time_hours', 0):.1f}", "ساعت", row, 2, "#795548")
        self._create_kpi_card(scrollable, "انطباق PM", f"{summary.get('pm_compliance_rate', 0):.1f}%", "نگهداری پیشگیرانه", row, 3, "#607D8B")
        row += 1

        ttk.Label(scrollable, text="تحلیل کارهای معوق", font=FONT_HEADING).grid(row=row, column=0, columnspan=4, pady=(20, 10), sticky=tk.W)
        row += 1
        self._create_kpi_card(scrollable, "در انتظار", f"{backlog.get('pending', 0)}", "دستورات معلق", row, 0, "#FFC107")
        self._create_kpi_card(scrollable, "در حال انجام", f"{backlog.get('in_progress', 0)}", "در دست اقدام", row, 1, "#03A9F4")
        self._create_kpi_card(scrollable, "سررسید گذشته", f"{backlog.get('overdue', 0)}", "نیاز به اقدام فوری", row, 2, "#E91E63")
        self._create_kpi_card(scrollable, "کل معوقات", f"{backlog.get('total_backlog', 0)}", "مجموع کارهای باز", row, 3, "#673AB7")

    def _create_kpi_card(self, parent, title, value, subtitle, row, col, bg_color):
        card = tk.Frame(parent, bg=bg_color, relief=tk.RAISED, borderwidth=2, padx=10, pady=10)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)

        ttk.Label(card, text=title, font=FONT_HEADING, background=bg_color, foreground='white').pack(pady=(5, 0))
        ttk.Label(card, text=value, font=FONT_TITLE, background=bg_color, foreground='white').pack()
        ttk.Label(card, text=subtitle, font=FONT_SMALL, background=bg_color, foreground='white', wraplength=150).pack(pady=(0, 5))

    # ------------------------------------------------------------
    # Equipment Performance Tab
    # ------------------------------------------------------------
    def _load_equipment_performance(self, start_date=None, end_date=None):
        for child in self.equipment_frame.winfo_children():
            if not isinstance(child, ttk.Frame) or child != self.equipment_frame.winfo_children()[0]:
                child.destroy()

        tree_frame = ttk.Frame(self.equipment_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ("id", "name", "status", "total_wo", "completed", "pm", "cm", "em",
                   "mtbf", "mttr", "availability", "oee", "downtime", "total_cost")
        self.equipment_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)
        col_defs = [
            ("id", "شناسه", 50), ("name", "نام تجهیز", 200), ("status", "وضعیت", 100),
            ("total_wo", "کل WO", 80), ("completed", "تکمیل شده", 100), ("pm", "PM", 60),
            ("cm", "CM", 60), ("em", "EM", 60), ("mtbf", "MTBF (ساعت)", 100),
            ("mttr", "MTTR (ساعت)", 100), ("availability", "دسترسی (%)", 100),
            ("oee", "OEE (%)", 100), ("downtime", "توقف (ساعت)", 120),
            ("total_cost", "هزینه کل (ریال)", 150)
        ]
        for col, text, width in col_defs:
            self.equipment_tree.heading(col, text=text)
            self.equipment_tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=vsb.set)
        self.equipment_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.equipment_tree.bind("<Double-1>", self._open_equipment_detail)

        equipments = self.eq_repo.get_all_equipment()
        if not equipments:
            ttk.Label(tree_frame, text="هیچ تجهیزی یافت نشد.", font=FONT_NORMAL).pack(pady=50)
            return

        with self.report_repo._session() as session:
            sp_repo = SparePartsRepository(session)
            for eq in equipments:
                try:
                    report = self.report_repo.get_equipment_report(eq['id'], start_date, end_date)
                    if not report:
                        continue

                    mtbf = float(report.get('mtbf_hours') or 0)
                    mttr = float(report.get('mttr_hours') or 0)
                    availability_value = 0.0
                    availability_str = "N/A"
                    if mtbf + mttr > 0:
                        availability_value = (mtbf / (mtbf + mttr)) * 100
                        availability_str = f"{availability_value:.1f}"

                    logs_q = session.query(ProductionLog).filter(ProductionLog.equipment_id == eq['id'])
                    if start_date:
                        logs_q = logs_q.filter(ProductionLog.log_date >= start_date)
                    if end_date:
                        logs_q = logs_q.filter(ProductionLog.log_date <= end_date)
                    logs = logs_q.all()

                    if logs:
                        total_actual_output = sum(float(log.output_units) for log in logs)
                        total_planned_hours = sum(float(log.planned_hours) for log in logs)
                        max_output_per_hour = 0.0
                        for log in logs:
                            if log.planned_hours > 0:
                                rate = float(log.output_units) / float(log.planned_hours)
                                if rate > max_output_per_hour:
                                    max_output_per_hour = rate
                        if max_output_per_hour > 0 and total_planned_hours > 0:
                            performance = (total_actual_output / (total_planned_hours * max_output_per_hour)) * 100
                        else:
                            performance = 95.0
                    else:
                        performance = 95.0

                    quality = float(self.report_repo._get_inspection_pass_rate(session, eq['id'], start_date, end_date) or 100.0)
                    if quality == 0:
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

                    total_cost = 0.0
                    wo_q = session.query(WorkOrder).filter(WorkOrder.equipment_id == eq['id'])
                    if start_date:
                        wo_q = wo_q.filter(WorkOrder.created_at >= start_date)
                    if end_date:
                        wo_q = wo_q.filter(WorkOrder.created_at <= end_date)
                    work_orders = wo_q.all()
                    for wo in work_orders:
                        if wo.parts_used:
                            try:
                                parts_list = json.loads(wo.parts_used)
                                for item in parts_list:
                                    part_id = item.get("part_id")
                                    qty = float(item.get("quantity", 0))
                                    part = sp_repo.get_by_id(part_id)
                                    if part:
                                        total_cost += float(part.unit_price) * qty
                            except:
                                pass
                        if wo.start_time and wo.end_time:
                            hours = (wo.end_time - wo.start_time).total_seconds() / 3600.0
                            total_cost += hours * 50.0
                        total_cost += float(wo.manual_cost or 0)

                    self.equipment_tree.insert("", tk.END, values=(
                        report['equipment_id'], report['equipment_name'],
                        STATUS_FA.get(report.get('equipment_status', ''), report.get('equipment_status', '—')),
                        report.get('total_work_orders', 0), report.get('completed_work_orders', 0),
                        report.get('pm_work_orders', 0), report.get('cm_work_orders', 0),
                        em_count, f"{mtbf:.1f}", f"{mttr:.1f}", availability_str,
                        oee_str, f"{report.get('total_downtime_hours', 0):.1f}", f"{total_cost:,.0f}"
                    ))
                except Exception as e:
                    print(f"Error loading equipment {eq['id']}: {e}")

    # ------------------------------------------------------------
    # Equipment Detail Dialog
    # ------------------------------------------------------------
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
        dialog.geometry("1100x800")
        dialog.configure(bg=GRAY_BG)
        dialog.transient(self)
        dialog.grab_set()

        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="اطلاعات و عملکرد")

        canvas = tk.Canvas(main_frame, bg=GRAY_BG, highlightthickness=0)
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
            ("کد تجهیز:", eq_data.get("code", "—")), ("نام تجهیز:", eq_data.get("name", "—")),
            ("دسته‌بندی:", eq_data.get("category", "—")), ("سازنده:", eq_data.get("manufacturer", "—")),
            ("مدل:", eq_data.get("model", "—")), ("شماره سریال:", eq_data.get("serial_number", "—")),
            ("موقعیت:", eq_data.get("location", "—")), ("تاریخ نصب:", eq_data.get("installation_date", "—")),
            ("وضعیت:", STATUS_FA.get(eq_data.get("status", ""), eq_data.get("status", "—")))
        ]
        for i, (label, value) in enumerate(fields):
            ttk.Label(info_frame, text=label, font=FONT_HEADING).grid(row=i, column=0, sticky="e", padx=5, pady=3)
            ttk.Label(info_frame, text=value, font=FONT_NORMAL).grid(row=i, column=1, sticky="w", padx=5, pady=3)

        specs_frame = ttk.LabelFrame(scrollable, text="مشخصات فنی", padding=10)
        specs_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(specs_frame, text=eq_data.get("specifications", "—"), wraplength=800, justify="right").pack(anchor="w")

        notes_frame = ttk.LabelFrame(scrollable, text="یادداشت‌ها", padding=10)
        notes_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(notes_frame, text=eq_data.get("notes", "—"), wraplength=800, justify="right").pack(anchor="w")

        start = self.start_date.get_date()
        end = self.end_date.get_date()
        report = self.report_repo.get_equipment_report(equipment_id, start, end)
        if report:
            kpi_frame = ttk.LabelFrame(scrollable, text="شاخص‌های عملکردی", padding=10)
            kpi_frame.pack(fill=tk.X, padx=10, pady=5)
            kpis = [
                ("کل دستورات کار:", report.get('total_work_orders', 0)),
                ("تکمیل شده:", report.get('completed_work_orders', 0)),
                ("PM:", report.get('pm_work_orders', 0)),
                ("CM:", report.get('cm_work_orders', 0)),
                ("میانگین زمان تعمیر (ساعت):", f"{report.get('avg_repair_time_hours', 0):.2f}"),
                ("کل زمان توقف (ساعت):", f"{report.get('total_downtime_hours', 0):.2f}"),
                ("انطباق PM (%):", f"{report.get('pm_compliance_rate', 0):.1f}"),
                ("MTBF (ساعت):", f"{report.get('mtbf_hours', 0):.2f}"),
                ("MTTR (ساعت):", f"{report.get('mttr_hours', 0):.2f}"),
                ("تعداد خرابی:", report.get('failure_count', 0))
            ]
            total_cost = 0.0
            wo_repo = WorkOrderRepository()
            all_wos = wo_repo.get_all()
            with self.report_repo._session() as session:
                sp_repo = SparePartsRepository(session)
                for wo in all_wos:
                    if wo.equipment_id != equipment_id:
                        continue
                    if start and wo.created_at.date() < start:
                        continue
                    if end and wo.created_at.date() > end:
                        continue
                    if wo.parts_used:
                        try:
                            parts_list = json.loads(wo.parts_used)
                            for item in parts_list:
                                part_id = item.get("part_id")
                                qty = float(item.get("quantity", 0))
                                part = sp_repo.get_by_id(part_id)
                                if part:
                                    total_cost += float(part.unit_price) * qty
                        except:
                            pass
                    if wo.start_time and wo.end_time:
                        hours = (wo.end_time - wo.start_time).total_seconds() / 3600
                        total_cost += hours * 50
                    total_cost += float(wo.manual_cost or 0)
            kpis.append(("هزینه کل (ریال):", f"{total_cost:,.0f}"))

            for i, (label, value) in enumerate(kpis):
                ttk.Label(kpi_frame, text=label, font=FONT_HEADING).grid(row=i, column=0, sticky="e", padx=5, pady=3)
                ttk.Label(kpi_frame, text=str(value), font=FONT_NORMAL).grid(row=i, column=1, sticky="w", padx=5, pady=3)

        chart_frame = ttk.Frame(notebook)
        notebook.add(chart_frame, text="نمودارها")
        fig = Figure(figsize=(12, 5))
        ax1 = fig.add_subplot(121)
        if report:
            pm = report.get('pm_work_orders', 0)
            cm = report.get('cm_work_orders', 0)
            em_count = 0
            with self.report_repo._session() as session:
                em_count = session.query(func.count(WorkOrder.id)).filter(
                    WorkOrder.equipment_id == equipment_id,
                    WorkOrder.type == WorkOrderType.EMERGENCY,
                    WorkOrder.status == WorkOrderStatus.COMPLETED
                )
                if start:
                    em_count = em_count.filter(WorkOrder.created_at >= start)
                if end:
                    em_count = em_count.filter(WorkOrder.created_at <= end)
                em_count = em_count.scalar() or 0
            if pm + cm + em_count > 0:
                ax1.pie([pm, cm, em_count], labels=['PM', 'CM', 'EM'], autopct='%1.1f%%',
                        colors=[SUCCESS, RED, WARNING])
                ax1.set_title('Work Order Distribution')
            else:
                ax1.text(0.5, 0.5, 'No Data', ha='center', va='center')
        else:
            ax1.text(0.5, 0.5, 'No Data', ha='center', va='center')

        ax2 = fig.add_subplot(122)
        if report:
            metrics = ['MTBF', 'MTTR', 'Downtime']
            values = [report.get('mtbf_hours', 0), report.get('mttr_hours', 0), report.get('total_downtime_hours', 0)]
            ax2.bar(metrics, values, color=[NAVY, WARNING, RED])
            ax2.set_ylabel('Hours')
            ax2.set_title('Key Metrics')
        else:
            ax2.text(0.5, 0.5, 'No Data', ha='center', va='center')

        canvas_chart = FigureCanvasTkAgg(fig, chart_frame)
        canvas_chart.draw()
        canvas_chart.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

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
        for col, width in [("id", 60), ("title", 200), ("type", 100), ("status", 100), ("operator_notes", 300), ("technician_notes", 300), ("part_notes", 200)]:
            wo_tree.column(col, width=width)
        vsb = ttk.Scrollbar(wo_tree_frame, orient="vertical", command=wo_tree.yview)
        wo_tree.configure(yscrollcommand=vsb.set)
        wo_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        wo_tree.bind("<Double-1>", lambda e: self._show_work_order_detail(wo_tree))

        wo_repo = WorkOrderRepository()
        work_orders = wo_repo.get_all()
        eq_work_orders = [wo for wo in work_orders if wo.equipment_id == equipment_id]
        type_fa = {"PREVENTIVE": "پیشگیرانه", "CORRECTIVE": "اصلاحی", "EMERGENCY": "اضطراری", "INSPECTION": "بازرسی", "PM": "PM"}
        status_fa = {"PENDING": "در انتظار", "IN_PROGRESS": "در حال انجام", "COMPLETED": "تکمیل شده", "APPROVED": "تایید شده", "REJECTED": "رد شده"}
        for wo in eq_work_orders:
            wo_tree.insert("", tk.END, values=(
                wo.id, wo.title, type_fa.get(wo.type.name, wo.type.name),
                status_fa.get(wo.status.name, wo.status.name),
                wo.operator_notes or "—", wo.description or "—", wo.parts_used or "—"
            ))

        ttk.Button(dialog, text="بستن", command=dialog.destroy).pack(pady=10)

    def _show_work_order_detail(self, tree):
        selection = tree.selection()
        if not selection:
            return
        item = tree.item(selection[0])
        wo_id = int(item['values'][0])
        wo_repo = WorkOrderRepository()
        wo = wo_repo.get_by_id(wo_id)
        if not wo:
            messagebox.showerror("خطا", "دستور کار یافت نشد")
            return

        type_fa = {"PREVENTIVE": "پیشگیرانه", "CORRECTIVE": "اصلاحی", "EMERGENCY": "اضطراری", "INSPECTION": "بازرسی", "PM": "PM"}
        status_fa = {"PENDING": "در انتظار", "IN_PROGRESS": "در حال انجام", "COMPLETED": "تکمیل شده", "APPROVED": "تایید شده", "REJECTED": "رد شده"}

        detail = tk.Toplevel(self)
        detail.title(f"جزئیات دستور کار #{wo.id} - {wo.title}")
        detail.geometry("750x650")
        detail.configure(bg=GRAY_BG)
        detail.transient(self)
        detail.grab_set()

        canvas = tk.Canvas(detail, bg=GRAY_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(detail, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def add_row(parent, text, value, row):
            ttk.Label(parent, text=text, font=FONT_HEADING).grid(row=row, column=0, sticky="ne", padx=10, pady=5)
            ttk.Label(parent, text=str(value), font=FONT_NORMAL, wraplength=500, justify="right").grid(row=row, column=1, sticky="nw", padx=10, pady=5)
            return row + 1

        row = 0
        info_frame = ttk.LabelFrame(scrollable, text="اطلاعات اصلی", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        row = add_row(info_frame, "شناسه:", wo.id, row)
        row = add_row(info_frame, "عنوان:", wo.title or "—", row)
        row = add_row(info_frame, "تجهیز:", wo.equipment.name if wo.equipment else "—", row)
        row = add_row(info_frame, "نوع:", type_fa.get(wo.type.name, wo.type.name), row)
        row = add_row(info_frame, "اولویت:", wo.priority.name, row)
        row = add_row(info_frame, "وضعیت:", status_fa.get(wo.status.name, wo.status.name), row)
        row = add_row(info_frame, "تاریخ برنامه:", wo.scheduled_date.strftime("%Y-%m-%d") if wo.scheduled_date else "—", row)
        row = add_row(info_frame, "شروع:", wo.start_time.strftime("%Y-%m-%d %H:%M") if wo.start_time else "—", row)
        row = add_row(info_frame, "پایان:", wo.end_time.strftime("%Y-%m-%d %H:%M") if wo.end_time else "—", row)
        row = add_row(info_frame, "تکنسین:", wo.technician.full_name if wo.technician else "—", row)
        row = add_row(info_frame, "اپراتور:", wo.operator.full_name if wo.operator else "—", row)
        row = add_row(info_frame, "ساعت خرابی:", wo.failure_report_time.strftime("%Y-%m-%d %H:%M") if wo.failure_report_time else "—", row)
        row = add_row(info_frame, "گزارش‌دهنده:", wo.emergency_reported_by or "—", row)

        cost_frame = ttk.LabelFrame(scrollable, text="هزینه‌ها", padding=10)
        cost_frame.pack(fill=tk.X, padx=10, pady=5)
        row = 0
        row = add_row(cost_frame, "هزینه دستی (ریال):", f"{wo.manual_cost:,.0f}" if wo.manual_cost else "0", row)
        row = add_row(cost_frame, "توضیح هزینه:", wo.cost_description or "—", row)

        op_frame = ttk.LabelFrame(scrollable, text="یادداشت اپراتور", padding=10)
        op_frame.pack(fill=tk.X, padx=10, pady=5)
        op_text = tk.Text(op_frame, height=4, wrap="word", font=FONT_NORMAL)
        op_text.insert("1.0", wo.operator_notes or "—")
        op_text.config(state="disabled")
        op_text.pack(fill=tk.X)

        tech_frame = ttk.LabelFrame(scrollable, text="توضیحات تکنسین", padding=10)
        tech_frame.pack(fill=tk.X, padx=10, pady=5)
        tech_text = tk.Text(tech_frame, height=5, wrap="word", font=FONT_NORMAL)
        tech_text.insert("1.0", wo.description or "—")
        tech_text.config(state="disabled")
        tech_text.pack(fill=tk.X)

        parts_frame = ttk.LabelFrame(scrollable, text="قطعات مصرفی", padding=10)
        parts_frame.pack(fill=tk.X, padx=10, pady=5)
        parts_text = tk.Text(parts_frame, height=4, wrap="word", font=FONT_NORMAL)
        parts_text.insert("1.0", wo.parts_used or "—")
        parts_text.config(state="disabled")
        parts_text.pack(fill=tk.X)

        ttk.Button(detail, text="بستن", command=detail.destroy).pack(pady=10)

    # ------------------------------------------------------------
    # KPI Analysis Tab
    # ------------------------------------------------------------
    def _load_kpi_analysis(self, start_date, end_date):
        for child in self.kpi_frame.winfo_children():
            if not isinstance(child, ttk.Frame) or child != self.kpi_frame.winfo_children()[0]:
                child.destroy()

        canvas = tk.Canvas(self.kpi_frame, bg=GRAY_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.kpi_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        try:
            # Monthly trends
            trend_data = self.report_repo.get_monthly_trends(6)
            if trend_data and any(item['count'] > 0 for item in trend_data):
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
                ax1.bar(x - width, pm_counts, width, label='PM', color=SUCCESS)
                ax1.bar(x, cm_counts, width, label='CM', color=RED)
                ax1.bar(x + width, em_counts, width, label='EM', color=WARNING)
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
                # Show a message when no data
                msg_frame = tk.Frame(scrollable, bg=WHITE, pady=20)
                msg_frame.pack(pady=10, fill=tk.X)
                tk.Label(msg_frame, text="📊 داده‌ای برای نمایش ماهانه وجود ندارد. لطفاً ابتدا دستورکارهایی ایجاد کنید.",
                         font=FONT_NORMAL, bg=WHITE, fg=TEXT_LIGHT).pack()

            # Schedule compliance pie chart
            compliance = self.report_repo.get_schedule_compliance(start_date, end_date)
            fig2 = Figure(figsize=(8, 4))
            ax2 = fig2.add_subplot(111)
            if compliance.get('on_time', 0) > 0 or compliance.get('late', 0) > 0:
                ax2.pie([compliance['on_time'], compliance['late']], labels=['On Time', 'Late'],
                        autopct='%1.1f%%', colors=[SUCCESS, RED])
                ax2.set_title(f"Schedule Compliance: {compliance.get('compliance_rate', 0):.1f}%")
            else:
                ax2.text(0.5, 0.5, 'No Data', ha='center', va='center')
            canvas2 = FigureCanvasTkAgg(fig2, scrollable)
            canvas2.draw()
            canvas2.get_tk_widget().pack(pady=10)

            # Equipment risk table with proper title and styling
            risk_data = self.report_repo.get_equipment_risk_score()
            if risk_data:
                # Title frame
                title_frame = tk.Frame(scrollable, bg=GRAY_BG)
                title_frame.pack(fill=tk.X, pady=(10, 0))
                tk.Label(title_frame, text="⚠️ تجهیزات با ریسک بالا", font=FONT_HEADING,
                         bg=GRAY_BG, fg=TEXT_DARK).pack(side="right")
                tk.Label(title_frame, text="(بر اساس خرابی و زمان توقف)", font=FONT_SMALL,
                         bg=GRAY_BG, fg=TEXT_LIGHT).pack(side="right", padx=(5, 0))

                tree_frame = ttk.Frame(scrollable)
                tree_frame.pack(fill=tk.X, pady=5)
                risk_tree = ttk.Treeview(tree_frame, columns=("name", "risk", "level", "failures", "downtime"),
                                         show="headings", height=8)
                risk_tree.heading("name", text="تجهیز")
                risk_tree.heading("risk", text="امتیاز ریسک")
                risk_tree.heading("level", text="سطح ریسک")
                risk_tree.heading("failures", text="تعداد خرابی")
                risk_tree.heading("downtime", text="زمان توقف (ساعت)")

                for col in ("name", "risk", "level", "failures", "downtime"):
                    risk_tree.column(col, width=130, anchor="center")

                # Insert data with color tags based on risk level
                risk_tree.tag_configure("high", foreground=RED)
                risk_tree.tag_configure("medium", foreground=WARNING)
                risk_tree.tag_configure("low", foreground=SUCCESS)

                for item in risk_data:
                    risk_score = item.get('risk_score', 0)
                    level = item.get('risk_level', '')
                    if risk_score >= 70 or level == "High":
                        tag = "high"
                    elif risk_score >= 40 or level == "Medium":
                        tag = "medium"
                    else:
                        tag = "low"

                    risk_tree.insert("", tk.END, tags=(tag,), values=(
                        item.get('equipment_name', '—'),
                        f"{risk_score:.1f}",
                        level if level else ("بالا" if risk_score >= 70 else "متوسط" if risk_score >= 40 else "پایین"),
                        item.get('failure_count', 0),
                        f"{item.get('avg_downtime_hours', 0):.1f}"
                    ))
                risk_tree.pack(fill=tk.X)
            else:
                tk.Label(scrollable, text="هیچ داده ریسکی یافت نشد. لطفاً دستورکارهای تکمیل شده داشته باشید.",
                         font=FONT_NORMAL, fg=TEXT_LIGHT).pack(pady=10)

        except Exception as e:
            ttk.Label(scrollable, text=f"خطا در بارگیری داده‌ها: {str(e)}", foreground=RED).pack(pady=20)
    # ------------------------------------------------------------
    # Cost Analysis Tab
    # ------------------------------------------------------------
    def _load_cost_analysis(self, start_date, end_date):
        for child in self.cost_frame.winfo_children():
            if not isinstance(child, ttk.Frame) or child != self.cost_frame.winfo_children()[0]:
                child.destroy()

        try:
            cost_data = self.report_repo.get_cost_analysis(start_date, end_date)
            if cost_data.get('breakdown') and len(cost_data['breakdown']) > 0:
                fig = Figure(figsize=(9, 7))
                ax = fig.add_subplot(111)
                labels = [d['type'] for d in cost_data['breakdown']]
                sizes = [d['total_cost'] for d in cost_data['breakdown']]
                ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
                ax.set_title(f"Cost Distribution (Total: {cost_data.get('total_cost', 0):,.0f} Rials)")
                canvas = FigureCanvasTkAgg(fig, self.cost_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            else:
                ttk.Label(self.cost_frame, text="داده‌ای برای نمایش وجود ندارد", font=FONT_NORMAL).pack(pady=50)
        except Exception as e:
            ttk.Label(self.cost_frame, text=f"خطا: {str(e)}", foreground=RED).pack(pady=20)

    # ------------------------------------------------------------
    # Technician Performance Tab
    # ------------------------------------------------------------
    def _load_technician_performance(self, start_date, end_date):
        for child in self.tech_frame.winfo_children():
            if not isinstance(child, ttk.Frame) or child != self.tech_frame.winfo_children()[0]:
                child.destroy()

        try:
            tech_data = self.report_repo.get_technician_performance(start_date, end_date)
            if not tech_data:
                ttk.Label(self.tech_frame, text="داده‌ای برای نمایش وجود ندارد", font=FONT_NORMAL).pack(pady=50)
                return
            tree = ttk.Treeview(self.tech_frame, columns=("name", "total", "completed", "rate", "avg_time"),
                                show="headings", height=15)
            tree.heading("name", text="تکنسین")
            tree.heading("total", text="کل وظایف")
            tree.heading("completed", text="تکمیل شده")
            tree.heading("rate", text="نرخ تکمیل (%)")
            tree.heading("avg_time", text="میانگین زمان (ساعت)")
            for col, w in [("name", 200), ("total", 100), ("completed", 120), ("rate", 120), ("avg_time", 150)]:
                tree.column(col, width=w, anchor="center")
            for item in tech_data:
                tree.insert("", tk.END, values=(
                    item.get('technician_name', '—'), item.get('total_tasks', 0),
                    item.get('completed_tasks', 0), f"{item.get('completion_rate', 0):.1f}",
                    f"{item.get('avg_completion_hours', 0):.1f}"
                ))
            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        except Exception as e:
            ttk.Label(self.tech_frame, text=f"خطا: {str(e)}", foreground=RED).pack(pady=20)

    # ------------------------------------------------------------
    # Failure Analysis Tab
    # ------------------------------------------------------------
    def _load_failure_analysis(self, start_date, end_date):
        for child in self.failure_frame.winfo_children():
            if not isinstance(child, ttk.Frame) or child != self.failure_frame.winfo_children()[0]:
                child.destroy()

        try:
            top_failures = self.report_repo.get_top_failure_modes(start_date, end_date, limit=10)
            if not top_failures:
                tk.Label(self.failure_frame, text="هیچ خرابی ثبت نشده است.", font=FONT_NORMAL).pack(pady=50)
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
                tree.insert("", tk.END, values=(item.get('description', '—'), item.get('count', 0)))
            vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            tree.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")
        except Exception as e:
            ttk.Label(self.failure_frame, text=f"خطا: {str(e)}", foreground=RED).pack(pady=20)

    # ------------------------------------------------------------
    # Excel Export (Enhanced)
    # ------------------------------------------------------------
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

            # Company header (ensure colors are valid hex strings)
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max_cols)
            cell = ws.cell(row=1, column=1, value="شرکت گلا — سیستم نگهداری پیشگیرانه")
            cell.font = Font(name="Tahoma", size=12, bold=True, color="FFFFFF")  # white text
            cell.fill = PatternFill(start_color="1A73E8", end_color="1A73E8", fill_type="solid")  # valid hex
            cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[1].height = 30

            # Title
            ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max_cols)
            title_cell = ws.cell(row=2, column=1, value=tab_title)
            title_cell.font = Font(name="Tahoma", size=14, bold=True, color="1A73E8")
            title_cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[2].height = 25

            # Date range
            start = self.start_date.get_date().strftime("%Y-%m-%d")
            end = self.end_date.get_date().strftime("%Y-%m-%d")
            ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=max_cols)
            info_cell = ws.cell(row=3, column=1,
                                value=f"بازه گزارش: {start} تا {end}  |  تاریخ تهیه: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            info_cell.font = Font(name="Tahoma", size=9, italic=True, color="5F6368")
            info_cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[3].height = 20

            # Headers (dark background with white text)
            header_row = 5
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=header_row, column=col_idx, value=header)
                cell.font = Font(name="Tahoma", size=10, bold=True, color="FFFFFF")  # white
                cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = Border(left=Side(style="thin"), right=Side(style="thin"),
                                     top=Side(style="thin"), bottom=Side(style="thin"))
            ws.row_dimensions[header_row].height = 28

            # Data rows (alternating colors)
            for row_idx, row_data in enumerate(data, start=header_row + 1):
                bg_color = "F5F7FA" if (row_idx % 2 == 0) else "FFFFFF"  # valid hex without #
                for col_idx, value in enumerate(row_data.values(), 1):
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
                            cell.number_format = "#,##0.00" if isinstance(value, float) else "#,##0"
                        except:
                            pass
                ws.row_dimensions[row_idx].height = 20

            # Auto-fit columns
            for col_idx in range(1, len(headers) + 1):
                max_len = 10
                for row in range(header_row, header_row + len(data) + 1):
                    val = ws.cell(row=row, column=col_idx).value
                    if val:
                        max_len = max(max_len, len(str(val)))
                ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 50)

            ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
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
                    "توقف (ساعت)": values[12], "هزینه کل (ریال)": values[13]
                })
        elif tab_title == "عملکرد تکنسین‌ها" and hasattr(self, 'tech_tree'):
            for child in self.tech_tree.get_children():
                values = self.tech_tree.item(child)['values']
                data.append({
                    "تکنسین": values[0], "کل وظایف": values[1], "تکمیل شده": values[2],
                    "نرخ تکمیل (%)": values[3], "میانگین زمان (ساعت)": values[4]
                })
        elif tab_title == "داشبورد کلی":
            summary = self.report_repo.get_kpi_summary()
            backlog = self.report_repo.get_backlog_analysis()
            data.append({
                "کل دستورات کار": summary.get('total_work_orders', 0),
                "تکمیل شده": summary.get('completed_work_orders', 0),
                "در حال انجام": summary.get('in_progress_work_orders', 0),
                "معوق": summary.get('overdue_work_orders', 0),
                "کل تجهیزات": summary.get('total_equipment', 0),
                "عملیاتی": summary.get('operational_equipment', 0),
                "میانگین زمان تعمیر (ساعت)": summary.get('avg_completion_time_hours', 0),
                "انطباق PM (%)": summary.get('pm_compliance_rate', 0),
                "در انتظار": backlog.get('pending', 0),
                "در حال انجام (بک‌لاگ)": backlog.get('in_progress', 0),
                "سررسید گذشته": backlog.get('overdue', 0),
                "کل معوقات": backlog.get('total_backlog', 0)
            })
        elif tab_title == "تحلیل KPI":
            start = self.start_date.get_date()
            end = self.end_date.get_date()
            pm_cm = self.report_repo.get_pm_cm_ratio(start, end)
            compliance = self.report_repo.get_schedule_compliance(start, end)
            risk = self.report_repo.get_equipment_risk_score()
            data.append({
                "PM": pm_cm.get('preventive_count', 0), "CM": pm_cm.get('corrective_count', 0),
                "EM": pm_cm.get('emergency_count', 0), "نسبت PM/CM": pm_cm.get('ratio', 0),
                "کل وظایف برنامه": compliance.get('total_tasks', 0), "انجام به موقع": compliance.get('on_time', 0),
                "تاخیر": compliance.get('late', 0), "نرخ انطباق (%)": compliance.get('compliance_rate', 0)
            })
            for r in risk[:10]:
                data.append({"تجهیز": r.get('equipment_name', '—'), "امتیاز ریسک": r.get('risk_score', 0), "سطح": r.get('risk_level', '—')})
        elif tab_title == "تحلیل هزینه":
            start = self.start_date.get_date()
            end = self.end_date.get_date()
            cost = self.report_repo.get_cost_analysis(start, end)
            for item in cost.get('breakdown', []):
                data.append({
                    "نوع": item.get('type', '—'), "هزینه کل": item.get('total_cost', 0),
                    "درصد": item.get('percentage', 0), "هزینه قطعات": item.get('part_cost', 0),
                    "هزینه نیروی کار": item.get('labor_cost', 0)
                })
        elif tab_title == "تحلیل خرابی‌ها":
            start = self.start_date.get_date()
            end = self.end_date.get_date()
            failures = self.report_repo.get_top_failure_modes(start, end, limit=50)
            for item in failures:
                data.append({"توضیحات خرابی": item.get('description', '—'), "تعداد تکرار": item.get('count', 0)})
        return data
