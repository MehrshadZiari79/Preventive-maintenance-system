
# views/reports_view.py
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

from database.report_repository import ReportRepository
from database.equipment_repository import EquipmentRepository

# Add this Persian status mapping
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

        self._build_ui()
        self._load_dashboard()

    def _build_ui(self):
        # Title
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(title_frame, text="گزارشات و تحلیل‌ها", font=("Arial", 16, "bold")).pack(side=tk.RIGHT)

        # Filters
        filter_frame = ttk.LabelFrame(self, text="فیلترها", padding=10)
        filter_frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(filter_frame, text="از تاریخ:").grid(row=0, column=3, padx=5)
        self.start_date = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd')
        self.start_date.set_date(datetime.now() - timedelta(days=30))
        self.start_date.grid(row=0, column=2, padx=5)

        ttk.Label(filter_frame, text="تا تاریخ:").grid(row=0, column=1, padx=5)
        self.end_date = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd')
        self.end_date.grid(row=0, column=0, padx=5)

        ttk.Button(filter_frame, text="بروزرسانی", command=self._load_dashboard).grid(row=0, column=4, padx=10)

        # Notebook for different report sections
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Tab 1: Overall Dashboard
        self.overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_frame, text="داشبورد کلی")

        # Tab 2: Equipment Performance
        self.equipment_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.equipment_frame, text="عملکرد تجهیزات")

        # Tab 3: KPI Analysis
        self.kpi_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.kpi_frame, text="تحلیل KPI")

        # Tab 4: Cost Analysis
        self.cost_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.cost_frame, text="تحلیل هزینه")

        # Tab 5: Technician Performance
        self.tech_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tech_frame, text="عملکرد تکنسین‌ها")

        # Tab 6: Trends
        self.trend_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.trend_frame, text="روندها")

    def _load_dashboard(self):
        start = self.start_date.get_date()
        end = self.end_date.get_date()

        self._load_overview_dashboard()
        self._load_equipment_performance()
        self._load_kpi_analysis(start, end)
        self._load_cost_analysis(start, end)
        self._load_technician_performance(start, end)
        self._load_trends()

    def _load_overview_dashboard(self):
        """Overall KPI summary cards"""
        for widget in self.overview_frame.winfo_children():
            widget.destroy()

        canvas = tk.Canvas(self.overview_frame)
        scrollbar = ttk.Scrollbar(self.overview_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        summary = self.report_repo.get_kpi_summary()

        row = 0

        self._create_kpi_card(scrollable_frame, "کل دستورات کار",
                              f"{summary['total_work_orders']}",
                              "تمام دستورات ثبت شده",
                              row, 0, bg='#2196F3')

        completion_pct = (summary['completed_work_orders'] / summary['total_work_orders'] * 100) if summary[
                                                                                                        'total_work_orders'] > 0 else 0
        self._create_kpi_card(scrollable_frame, "تکمیل شده",
                              f"{summary['completed_work_orders']}",
                              f"{completion_pct:.1f}% از کل",
                              row, 1, bg='#4CAF50')

        self._create_kpi_card(scrollable_frame, "در حال انجام",
                              f"{summary['in_progress_work_orders']}",
                              "دستورات فعال",
                              row, 2, bg='#FF9800')

        self._create_kpi_card(scrollable_frame, "معوق",
                              f"{summary['overdue_work_orders']}",
                              "نیاز به توجه فوری",
                              row, 3, bg='#F44336')

        row += 1

        self._create_kpi_card(scrollable_frame, "کل تجهیزات",
                              f"{summary['total_equipment']}",
                              "تجهیزات ثبت شده",
                              row, 0, bg='#9C27B0')

        operational_pct = (summary['operational_equipment'] / summary['total_equipment'] * 100) if summary[
                                                                                                       'total_equipment'] > 0 else 0
        self._create_kpi_card(scrollable_frame, "عملیاتی",
                              f"{summary['operational_equipment']}",
                              f"{operational_pct:.1f}% آماده",
                              row, 1, bg='#00BCD4')

        self._create_kpi_card(scrollable_frame, "میانگین زمان تعمیر",
                              f"{summary['avg_completion_time_hours']:.1f}",
                              "ساعت",
                              row, 2, bg='#795548')

        self._create_kpi_card(scrollable_frame, "انطباق PM",
                              f"{summary['pm_compliance_rate']:.1f}%",
                              "نگهداری پیشگیرانه",
                              row, 3, bg='#607D8B')

        row += 1

        backlog = self.report_repo.get_backlog_analysis()
        ttk.Label(scrollable_frame, text="تحلیل کارهای معوق", font=("Arial", 12, "bold")).grid(
            row=row, column=0, columnspan=4, pady=(20, 10), sticky=tk.W
        )
        row += 1

        self._create_kpi_card(scrollable_frame, "در انتظار",
                              f"{backlog['pending']}",
                              "دستورات معلق",
                              row, 0, bg='#FFC107')

        self._create_kpi_card(scrollable_frame, "در حال انجام",
                              f"{backlog['in_progress']}",
                              "در دست اقدام",
                              row, 1, bg='#03A9F4')

        self._create_kpi_card(scrollable_frame, "سررسید گذشته",
                              f"{backlog['overdue']}",
                              "نیاز به اقدام فوری",
                              row, 2, bg='#E91E63')

        self._create_kpi_card(scrollable_frame, "کل معوقات",
                              f"{backlog['total_backlog']}",
                              "مجموع کارهای باز",
                              row, 3, bg='#673AB7')

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _load_equipment_performance(self):
        """Per-equipment performance table with drill-down"""
        for widget in self.equipment_frame.winfo_children():
            widget.destroy()

        header_frame = ttk.Frame(self.equipment_frame)
        header_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(header_frame, text="عملکرد تجهیزات", font=("Arial", 14, "bold")).pack(side=tk.RIGHT)
        ttk.Label(header_frame, text="دوبار کلیک برای جزئیات", font=("Arial", 9, "italic")).pack(side=tk.LEFT)

        tree_frame = ttk.Frame(self.equipment_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("id", "name", "status", "total_wo", "completed", "pm", "cm", "mtbf", "mttr", "downtime")
        self.equipment_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        self.equipment_tree.heading("id", text="ID")
        self.equipment_tree.heading("name", text="نام تجهیز")
        self.equipment_tree.heading("status", text="وضعیت")
        self.equipment_tree.heading("total_wo", text="کل WO")
        self.equipment_tree.heading("completed", text="تکمیل شده")
        self.equipment_tree.heading("pm", text="PM")
        self.equipment_tree.heading("cm", text="CM")
        self.equipment_tree.heading("mtbf", text="MTBF (ساعت)")
        self.equipment_tree.heading("mttr", text="MTTR (ساعت)")
        self.equipment_tree.heading("downtime", text="زمان توقف (ساعت)")

        self.equipment_tree.column("id", width=50)
        self.equipment_tree.column("name", width=200)
        self.equipment_tree.column("status", width=100)
        self.equipment_tree.column("total_wo", width=80)
        self.equipment_tree.column("completed", width=100)
        self.equipment_tree.column("pm", width=60)
        self.equipment_tree.column("cm", width=60)
        self.equipment_tree.column("mtbf", width=100)
        self.equipment_tree.column("mttr", width=100)
        self.equipment_tree.column("downtime", width=120)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=scrollbar.set)

        self.equipment_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        equipments = self.eq_repo.get_all_equipment()
        for eq in equipments:
            report = self.report_repo.get_equipment_report(eq['id'])
            if report:
                self.equipment_tree.insert("", tk.END, values=(
                    report['equipment_id'],
                    report['equipment_name'],
                    report['equipment_status'],
                    report['total_work_orders'],
                    report['completed_work_orders'],
                    report['pm_work_orders'],
                    report['cm_work_orders'],
                    f"{report['mtbf_hours']:.1f}",
                    f"{report['mttr_hours']:.1f}",
                    f"{report['total_downtime_hours']:.1f}"
                ))

        self.equipment_tree.bind("<Double-1>", self._open_equipment_detail)

    def _open_equipment_detail(self, event):
        """Open detailed report dialog for selected equipment"""
        selection = self.equipment_tree.selection()
        if not selection:
            return

        item = self.equipment_tree.item(selection[0])
        equipment_id = item['values'][0]

        dialog = tk.Toplevel(self)
        dialog.title(f"گزارش تفصیلی تجهیز")
        dialog.geometry("800x600")

        report = self.report_repo.get_equipment_report(equipment_id)
        if not report:
            messagebox.showerror("خطا", "گزارش یافت نشد")
            dialog.destroy()
            return

        header_frame = ttk.Frame(dialog)
        header_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(header_frame, text=f"تجهیز: {report['equipment_name']}",
                  font=("Arial", 14, "bold")).pack(side=tk.RIGHT)
        ttk.Label(header_frame, text=f"وضعیت: {report['equipment_status']}",
                  font=("Arial", 10)).pack(side=tk.LEFT)

        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Tab 1: Summary (Persian UI — no charts here, safe)
        summary_frame = ttk.Frame(notebook)
        notebook.add(summary_frame, text="خلاصه")

        summary_data = [
            ("کل دستورات کار:", report['total_work_orders']),
            ("تکمیل شده:", report['completed_work_orders']),
            ("نگهداری پیشگیرانه (PM):", report['pm_work_orders']),
            ("نگهداری اصلاحی (CM):", report['cm_work_orders']),
            ("میانگین زمان تعمیر:", f"{report['avg_repair_time_hours']:.2f} ساعت"),
            ("کل زمان توقف:", f"{report['total_downtime_hours']:.2f} ساعت"),
            ("نرخ انطباق PM:", f"{report['pm_compliance_rate']:.1f}%"),
            ("MTBF:", f"{report['mtbf_hours']:.2f} ساعت"),
            ("MTTR:", f"{report['mttr_hours']:.2f} ساعت"),
            ("تعداد خرابی:", report['failure_count'])
        ]

        for i, (label, value) in enumerate(summary_data):
            ttk.Label(summary_frame, text=label, font=("Arial", 10, "bold")).grid(
                row=i, column=0, sticky=tk.E, padx=20, pady=5
            )
            ttk.Label(summary_frame, text=str(value), font=("Arial", 10)).grid(
                row=i, column=1, sticky=tk.W, padx=20, pady=5
            )

        # Tab 2: Charts — ALL TEXT IN ENGLISH
        chart_frame = ttk.Frame(notebook)
        notebook.add(chart_frame, text="نمودارها")

        fig = Figure(figsize=(8, 6))

        ax1 = fig.add_subplot(121)
        if report['pm_work_orders'] > 0 or report['cm_work_orders'] > 0:
            ax1.pie([report['pm_work_orders'], report['cm_work_orders']],
                    labels=['PM', 'CM'],
                    autopct='%1.1f%%',
                    colors=['#4CAF50', '#F44336'],
                    startangle=90)
            ax1.set_title('PM vs CM Distribution')
        else:
            ax1.text(0.5, 0.5, 'No Data Available',
                     ha='center', va='center', fontsize=12)
            ax1.set_xlim(0, 1)
            ax1.set_ylim(0, 1)
            ax1.axis('off')

        ax2 = fig.add_subplot(122)
        metrics = ['MTBF', 'MTTR', 'Downtime']
        values = [report['mtbf_hours'], report['mttr_hours'], report['total_downtime_hours']]
        ax2.bar(metrics, values, color=['#2196F3', '#FF9800', '#F44336'])
        ax2.set_ylabel('Hours')
        ax2.set_title('Key Metrics')

        canvas = FigureCanvasTkAgg(fig, chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Button(dialog, text="بستن", command=dialog.destroy).pack(pady=10)

    def _create_kpi_card(self, parent, title, value, subtitle, row, col, bg='#2196F3'):
        """Create a colored KPI card"""
        card = tk.Frame(parent, bg=bg, relief=tk.RAISED, borderwidth=2)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew", ipadx=20, ipady=15)

        parent.grid_columnconfigure(col, weight=1)

        ttk.Label(card, text=title, font=("Arial", 10), background=bg,
                  foreground='white').pack(pady=(5, 0))
        ttk.Label(card, text=value, font=("Arial", 24, "bold"), background=bg,
                  foreground='white').pack()
        ttk.Label(card, text=subtitle, font=("Arial", 8), background=bg,
                  foreground='white').pack(pady=(0, 5))

    def _load_kpi_analysis(self, start_date, end_date):
        """Detailed KPI analysis with charts — all chart text in English"""
        for widget in self.kpi_frame.winfo_children():
            widget.destroy()

        canvas = tk.Canvas(self.kpi_frame)
        scrollbar = ttk.Scrollbar(self.kpi_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        row = 0

        # PM/CM Ratio
        pm_cm = self.report_repo.get_pm_cm_ratio(start_date, end_date)
        ttk.Label(scrollable_frame, text="نسبت PM/CM", font=("Arial", 12, "bold")).grid(
            row=row, column=0, columnspan=2, pady=10, sticky=tk.W
        )
        row += 1

        pm_cm_frame = ttk.Frame(scrollable_frame)
        pm_cm_frame.grid(row=row, column=0, columnspan=2, sticky="nsew", pady=5)

        fig1 = Figure(figsize=(10, 4))
        ax1 = fig1.add_subplot(111)

        if pm_cm['preventive_count'] > 0 or pm_cm['corrective_count'] > 0:
            ax1.bar(['Preventive (PM)', 'Corrective (CM)'],
                    [pm_cm['preventive_count'], pm_cm['corrective_count']],
                    color=['#4CAF50', '#F44336'])
            ax1.set_ylabel('Count')
            ax1.set_title(f"PM / CM Ratio: {pm_cm['ratio']:.2f}")
            ax1.grid(True, alpha=0.3)
        else:
            ax1.text(0.5, 0.5, 'No Data Available',
                     ha='center', va='center',
                     transform=ax1.transAxes, fontsize=12)

        canvas1 = FigureCanvasTkAgg(fig1, pm_cm_frame)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        row += 1

        # Schedule Compliance
        compliance = self.report_repo.get_schedule_compliance(start_date, end_date)
        ttk.Label(scrollable_frame, text="انطباق برنامه", font=("Arial", 12, "bold")).grid(
            row=row, column=0, columnspan=2, pady=(20, 10), sticky=tk.W
        )
        row += 1

        comp_frame = ttk.Frame(scrollable_frame)
        comp_frame.grid(row=row, column=0, columnspan=2, sticky="nsew", pady=5)

        fig2 = Figure(figsize=(10, 4))
        ax2 = fig2.add_subplot(111)

        on_time = compliance['on_time'] if not np.isnan(compliance['on_time']) else 0
        late = compliance['late'] if not np.isnan(compliance['late']) else 0

        if on_time > 0 or late > 0:
            ax2.pie([on_time, late],
                    labels=['On Time', 'Late'],
                    autopct='%1.1f%%',
                    colors=['#4CAF50', '#F44336'],
                    startangle=90)
            ax2.set_title(f"Schedule Compliance Rate: {compliance['compliance_rate']:.1f}%")
        else:
            ax2.text(0.5, 0.5, 'No Data Available',
                     ha='center', va='center',
                     transform=ax2.transAxes, fontsize=12)
            ax2.axis('off')

        canvas2 = FigureCanvasTkAgg(fig2, comp_frame)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        row += 1

        # Equipment Risk Score
        ttk.Label(scrollable_frame, text="امتیاز ریسک تجهیزات", font=("Arial", 12, "bold")).grid(
            row=row, column=0, columnspan=2, pady=(20, 10), sticky=tk.W
        )
        row += 1

        risk_data = self.report_repo.get_equipment_risk_score()
        risk_tree_frame = ttk.Frame(scrollable_frame)
        risk_tree_frame.grid(row=row, column=0, columnspan=2, sticky="nsew", pady=5)

        risk_tree = ttk.Treeview(risk_tree_frame,
                                 columns=("name", "risk", "level", "failures", "downtime"),
                                 show="headings", height=10)
        risk_tree.heading("name", text="تجهیز")
        risk_tree.heading("risk", text="امتیاز ریسک")
        risk_tree.heading("level", text="سطح")
        risk_tree.heading("failures", text="خرابی‌ها")
        risk_tree.heading("downtime", text="زمان توقف (ساعت)")

        risk_tree.column("name", width=200)
        risk_tree.column("risk", width=100)
        risk_tree.column("level", width=100)
        risk_tree.column("failures", width=100)
        risk_tree.column("downtime", width=150)

        for item in risk_data:
            risk_tree.insert("", tk.END, values=(
                item['equipment_name'],
                f"{item['risk_score']:.1f}",
                item['risk_level'],
                item['failure_count'],
                f"{item['avg_downtime_hours']:.1f}"
            ))

        risk_tree.pack(fill=tk.BOTH, expand=True)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _load_cost_analysis(self, start_date, end_date):
        for widget in self.cost_frame.winfo_children():
            widget.destroy()

        cost_data = self.report_repo.get_cost_analysis(start_date, end_date)

        if cost_data['breakdown'] and len(cost_data['breakdown']) > 0:
            fig = Figure(figsize=(10, 6))
            ax = fig.add_subplot(111)

            labels = [d['type'] for d in cost_data['breakdown']]
            sizes = [d['total_cost'] for d in cost_data['breakdown']]
            colors = ['#4CAF50', '#F44336', '#FF9800']

            if sum(sizes) > 0:
                ax.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
                ax.set_title(f"Cost Distribution (Total: {cost_data['total_cost']:,.0f} Rials)")
            else:
                ax.text(0.5, 0.5, 'No Data Available',
                        ha='center', va='center', fontsize=12)
                ax.axis('off')

            canvas = FigureCanvasTkAgg(fig, self.cost_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        else:
            ttk.Label(self.cost_frame, text="داده‌ای برای نمایش وجود ندارد",
                      font=("Arial", 12)).pack(pady=50)

    def _load_technician_performance(self, start_date, end_date):
        for widget in self.tech_frame.winfo_children():
            widget.destroy()

        tech_data = self.report_repo.get_technician_performance(start_date, end_date)

        if not tech_data:
            ttk.Label(self.tech_frame, text="داده‌ای برای نمایش وجود ندارد",
                      font=("Arial", 12)).pack(pady=50)
            return

        tree = ttk.Treeview(self.tech_frame,
                            columns=("name", "total", "completed", "rate", "avg_time"),
                            show="headings")
        tree.heading("name", text="تکنسین")
        tree.heading("total", text="کل وظایف")
        tree.heading("completed", text="تکمیل شده")
        tree.heading("rate", text="نرخ تکمیل (%)")
        tree.heading("avg_time", text="میانگین زمان (ساعت)")

        tree.column("name", width=200)
        tree.column("total", width=100)
        tree.column("completed", width=120)
        tree.column("rate", width=120)
        tree.column("avg_time", width=150)

        for item in tech_data:
            tree.insert("", tk.END, values=(
                item['technician_name'],
                item['total_tasks'],
                item['completed_tasks'],
                f"{item['completion_rate']:.1f}",
                f"{item['avg_completion_hours']:.1f}"
            ))

        tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    def _load_trends(self):
        for widget in self.trend_frame.winfo_children():
            widget.destroy()

        trend_data = self.report_repo.get_monthly_trends(6)

        if not trend_data:
            ttk.Label(self.trend_frame, text="داده‌ای برای نمایش وجود ندارد",
                      font=("Arial", 12)).pack(pady=50)
            return

        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)

        months = {}
        for item in trend_data:
            key = f"{item['year']}-{item['month']:02d}"
            if key not in months:
                months[key] = {'PREVENTIVE': 0, 'PM': 0, 'CORRECTIVE': 0}
            months[key][item['type']] = item['count']

        x = list(months.keys())
        preventive = [months[m].get('PREVENTIVE', 0) + months[m].get('PM', 0) for m in x]
        corrective = [months[m].get('CORRECTIVE', 0) for m in x]

        ax.plot(x, preventive, marker='o', label='Preventive', color='#4CAF50', linewidth=2)
        ax.plot(x, corrective, marker='s', label='Corrective', color='#F44336', linewidth=2)
        ax.set_xlabel('Month')
        ax.set_ylabel('Count')
        ax.set_title('Work Order Trends (Last 6 Months)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        canvas = FigureCanvasTkAgg(fig, self.trend_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=20)