# views/export_dialog.py (only Excel)
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from services.export_service import (
    export_equipment_excel,
    export_pm_excel,
    export_work_orders_excel,
    export_inspections_excel,
    export_spare_parts_excel
)

BG = "#F0F4F8"
PRIMARY = "#1A73E8"
TEXT = "#202124"
BORDER = "#DADCE0"
WHITE = "#FFFFFF"

class BaseExportDialog(tk.Toplevel):
    def __init__(self, parent, title, width=600, height=650):
        super().__init__(parent)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")
        self.data_range = tk.StringVar(value="all")
        self.include_details = tk.BooleanVar(value=True)
        self.include_stats = tk.BooleanVar(value=True)

    def _build_ui(self, title_text, additional_options=None):
        main_frame = tk.Frame(self, bg=BG)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        tk.Label(main_frame, text=title_text, font=("Tahoma", 16, "bold"),
                 bg=BG, fg=PRIMARY).pack(pady=(0, 20))

        type_frame = tk.LabelFrame(main_frame, text="نوع خروجی",
                                   font=("Tahoma", 11, "bold"),
                                   bg=BG, fg=TEXT, padx=15, pady=10)
        type_frame.pack(fill="x", pady=(0, 15))
        # Keep only Excel
        tk.Radiobutton(type_frame, text="📊 Excel", variable=tk.StringVar(value="excel"),
                       value="excel", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        range_frame = tk.LabelFrame(main_frame, text="محدوده داده‌ها",
                                    font=("Tahoma", 11, "bold"),
                                    bg=BG, fg=TEXT, padx=15, pady=10)
        range_frame.pack(fill="x", pady=(0, 15))
        tk.Radiobutton(range_frame, text="همه موارد", variable=self.data_range,
                       value="all", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(range_frame, text="محدوده تاریخ", variable=self.data_range,
                       value="date_range", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        self.date_frame = tk.Frame(range_frame, bg=BG)
        tk.Label(self.date_frame, text="از تاریخ:", bg=BG, font=("Tahoma", 9)).pack(side="right", padx=5)
        self.start_date = tk.Entry(self.date_frame, width=12, font=("Tahoma", 9))
        self.start_date.pack(side="right", padx=5)
        self.start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        tk.Label(self.date_frame, text="تا تاریخ:", bg=BG, font=("Tahoma", 9)).pack(side="right", padx=5)
        self.end_date = tk.Entry(self.date_frame, width=12, font=("Tahoma", 9))
        self.end_date.pack(side="right", padx=5)
        self.end_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        options_frame = tk.LabelFrame(main_frame, text="تنظیمات خروجی",
                                      font=("Tahoma", 11, "bold"),
                                      bg=BG, fg=TEXT, padx=15, pady=10)
        options_frame.pack(fill="x", pady=(0, 15))
        tk.Checkbutton(options_frame, text="شامل جزئیات", variable=self.include_details,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Checkbutton(options_frame, text="شامل آمار", variable=self.include_stats,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        btn_frame = tk.Frame(main_frame, bg=BG)
        btn_frame.pack(fill="x", pady=(10, 0))
        tk.Button(btn_frame, text="انصراف", command=self.destroy,
                  bg=BORDER, fg=TEXT, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="خروجی گرفتن", command=self._export,
                  bg=PRIMARY, fg=WHITE, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="right", padx=5)

        self.data_range.trace('w', self._on_range_change)

    def _on_range_change(self, *args):
        if self.data_range.get() == "date_range":
            self.date_frame.pack(fill="x", pady=(10, 0))
        else:
            self.date_frame.pack_forget()

    def _export(self):
        pass

# ==================== INSPECTION ====================
class InspectionExportDialog(BaseExportDialog):
    def __init__(self, parent, service, inspection=None, template=None):
        self.service = service
        self.inspection = inspection
        self.template = template
        super().__init__(parent, "📤 خروجی بازرسی‌ها")
        self._build_ui("📊 خروجی اطلاعات بازرسی")
        self.include_checkpoints = tk.BooleanVar(value=True)
        self.include_comments = tk.BooleanVar(value=True)
        # Add extra options
        options_frame = self.winfo_children()[0].winfo_children()[4]  # last label frame
        tk.Checkbutton(options_frame, text="شامل چک‌پوینت‌ها", variable=self.include_checkpoints,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Checkbutton(options_frame, text="شامل نظرات", variable=self.include_comments,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

    def _get_data(self):
        range_type = self.data_range.get()
        if range_type == "current" and self.inspection:
            return [self.inspection]
        elif range_type == "template" and self.template:
            all_ins = self.service.get_all_inspections()
            return [ins for ins in all_ins if ins.template_id == self.template.id]
        elif range_type == "date_range":
            start = self.start_date.get()
            end = self.end_date.get()
            all_ins = self.service.get_all_inspections()
            filtered = []
            for ins in all_ins:
                if ins.started_at:
                    ins_date = ins.started_at.strftime("%Y-%m-%d")
                    if start <= ins_date <= end:
                        filtered.append(ins)
            return filtered
        else:
            return self.service.get_all_inspections()

    def _inspection_to_dict(self, inspection):
        results = []
        if self.include_checkpoints.get() and inspection.results:
            for result in inspection.results:
                checkpoint_title = result.checkpoint.title if result.checkpoint else "—"
                results.append({
                    "checkpoint": checkpoint_title,
                    "result": "✅ قبول" if result.result == "pass" else "❌ رد" if result.result == "fail" else "⚠️ جزئی",
                    "comment": result.comment if self.include_comments.get() else ""
                })
        return {
            "id": inspection.id,
            "template_name": inspection.template.name if inspection.template else "—",
            "equipment_name": inspection.equipment.name if inspection.equipment else "—",
            "inspector_name": inspection.inspector.username if inspection.inspector else "—",
            "status": "در حال انجام" if inspection.status == "in_progress" else "تکمیل شده" if inspection.status == "completed" else "لغو شده",
            "overall_result": "✅ قبول" if inspection.overall_result == "pass" else "❌ رد" if inspection.overall_result == "fail" else "⚠️ جزئی",
            "started_at": inspection.started_at.strftime("%Y-%m-%d %H:%M") if inspection.started_at else "—",
            "completed_at": inspection.completed_at.strftime("%Y-%m-%d %H:%M") if inspection.completed_at else "—",
            "notes": inspection.notes or "",
            "results": results
        }

    def _export(self):
        inspections = self._get_data()
        if not inspections:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!")
            return
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"inspection_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            if filename:
                ins_dicts = [self._inspection_to_dict(ins) for ins in inspections]
                export_inspections_excel(ins_dicts, filename)
                messagebox.showinfo("موفق", "خروجی Excel با موفقیت ذخیره شد!")
                self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد خروجی: {str(e)}")

# ==================== EQUIPMENT ====================
class EquipmentExportDialog(BaseExportDialog):
    def __init__(self, parent, equipment_list, selected_equipment=None):
        self.equipment_list = equipment_list
        self.selected_equipment = selected_equipment
        super().__init__(parent, "📤 خروجی تجهیزات")
        self._build_ui("🔧 خروجی اطلاعات تجهیزات")

    def _get_data(self):
        if self.data_range.get() == "current" and self.selected_equipment:
            return [self.selected_equipment]
        return self.equipment_list

    def _export(self):
        data = self._get_data()
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!")
            return
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"equipment_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            if filename:
                export_equipment_excel(data, filename)
                messagebox.showinfo("موفق", "خروجی Excel با موفقیت ذخیره شد!")
                self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد خروجی: {str(e)}")

# ==================== PM ====================
class PMExportDialog(BaseExportDialog):
    def __init__(self, parent, pm_records, selected_pm=None):
        self.pm_records = pm_records
        self.selected_pm = selected_pm
        super().__init__(parent, "📤 خروجی برنامه‌های نت پیشگیرانه")
        self._build_ui("🔧 خروجی برنامه‌های نت پیشگیرانه")

    def _get_data(self):
        if self.data_range.get() == "current" and self.selected_pm:
            return [self.selected_pm]
        return self.pm_records

    def _export(self):
        data = self._get_data()
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!")
            return
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"pm_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            if filename:
                export_pm_excel(data, filename)
                messagebox.showinfo("موفق", "خروجی Excel با موفقیت ذخیره شد!")
                self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد خروجی: {str(e)}")

# ==================== WORK ORDER ====================
class WorkOrderExportDialog(BaseExportDialog):
    def __init__(self, parent, wo_repo, selected_wo_id=None):
        self.wo_repo = wo_repo
        self.selected_wo_id = selected_wo_id
        super().__init__(parent, "📤 خروجی دستورکارها", width=700, height=700)
        self._build_ui("📋 خروجی دستورکارها")
        # Add status filter
        filter_frame = tk.LabelFrame(self.winfo_children()[0].winfo_children()[1], text="فیلتر وضعیت",
                                     font=("Tahoma", 11, "bold"), bg=BG, fg=TEXT, padx=15, pady=10)
        filter_frame.pack(fill="x", pady=(0, 15))
        self.status_filter = tk.StringVar(value="all")
        statuses = [("همه", "all"), ("در انتظار", "pending"), ("در حال انجام", "in_progress"),
                    ("تکمیل شده", "completed"), ("لغو شده", "cancelled")]
        for text, value in statuses:
            tk.Radiobutton(filter_frame, text=text, variable=self.status_filter,
                           value=value, bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

    def _get_data(self):
        try:
            all_wos = self.wo_repo.get_all()
        except Exception:
            all_wos = []
        status = self.status_filter.get()
        if status != "all":
            all_wos = [wo for wo in all_wos if wo.status.value == status]
        if self.data_range.get() == "current" and self.selected_wo_id:
            all_wos = [wo for wo in all_wos if wo.id == self.selected_wo_id]
        return all_wos

    def _export(self):
        data = self._get_data()
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!")
            return
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"work_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            if filename:
                export_work_orders_excel(data, filename)
                messagebox.showinfo("موفق", "خروجی Excel با موفقیت ذخیره شد!")
                self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد خروجی: {str(e)}")

# ==================== SPARE PARTS ====================
class SparePartsExportDialog(BaseExportDialog):
    def __init__(self, parent, parts_list):
        self.parts_list = parts_list
        super().__init__(parent, "📤 خروجی قطعات یدکی")
        self._build_ui("🔧 خروجی قطعات یدکی")

    def _export(self):
        if not self.parts_list:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!")
            return
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"spare_parts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            if filename:
                export_spare_parts_excel(self.parts_list, filename)
                messagebox.showinfo("موفق", "خروجی Excel با موفقیت ذخیره شد!")
                self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد خروجی: {str(e)}")

# ==================== HELPER FUNCTIONS ====================
def run_inspection_export(parent, service, selected_inspection_id=None, selected_template=None):
    inspection = None
    if selected_inspection_id:
        inspection = service.get_inspection(selected_inspection_id)
    dialog = InspectionExportDialog(parent, service, inspection, selected_template)
    parent.wait_window(dialog)

def run_equipment_export(parent, equipment_list, selected_equipment=None):
    dialog = EquipmentExportDialog(parent, equipment_list, selected_equipment)
    parent.wait_window(dialog)

def run_pm_export(parent, pm_records, selected_pm=None):
    dialog = PMExportDialog(parent, pm_records, selected_pm)
    parent.wait_window(dialog)

def run_work_order_export(parent, wo_repo, selected_wo_id=None):
    dialog = WorkOrderExportDialog(parent, wo_repo, selected_wo_id)
    parent.wait_window(dialog)

def run_spare_parts_export(parent, parts_list):
    dialog = SparePartsExportDialog(parent, parts_list)
    parent.wait_window(dialog)