# views/export_dialog.py
"""
Export Dialog - Export inspections, PM schedules, work orders, and equipment to Excel and PDF
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from typing import Optional, List

from services.inspection_service import InspectionService
from database.models import Inspection, InspectionTemplate

# Try to import export libraries
try:
    import pandas as pd
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Theme
BG = "#F0F4F8"
PRIMARY = "#1A73E8"
TEXT = "#202124"
BORDER = "#DADCE0"
WHITE = "#FFFFFF"

# Persian status mapping for equipment
STATUS_FA = {
    "operational": "عملیاتی",
    "maintenance": "در تعمیر",
    "breakdown": "خراب",
    "inactive": "غیرفعال",
}


class BaseExportDialog(tk.Toplevel):
    """Base class for export dialogs"""

    def __init__(self, parent, title, width=600, height=650):
        super().__init__(parent)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.configure(bg=BG)
        self.resizable(False, False)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

        self.export_type = tk.StringVar(value="excel")
        self.data_range = tk.StringVar(value="all")
        self.include_details = tk.BooleanVar(value=True)
        self.include_stats = tk.BooleanVar(value=True)

    def _build_ui(self, title_text, additional_options=None):
        """Build common UI elements"""
        main_frame = tk.Frame(self, bg=BG)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        tk.Label(main_frame, text=title_text,
                 font=("Tahoma", 16, "bold"), bg=BG, fg=PRIMARY).pack(pady=(0, 20))

        # Export type selection
        type_frame = tk.LabelFrame(main_frame, text="نوع خروجی",
                                   font=("Tahoma", 11, "bold"),
                                   bg=BG, fg=TEXT, padx=15, pady=10)
        type_frame.pack(fill="x", pady=(0, 15))

        tk.Radiobutton(type_frame, text="📊 Excel", variable=self.export_type,
                       value="excel", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(type_frame, text="📄 PDF", variable=self.export_type,
                       value="pdf", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(type_frame, text="🔄 هر دو (Excel + PDF)", variable=self.export_type,
                       value="both", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Data range selection
        range_frame = tk.LabelFrame(main_frame, text="محدوده داده‌ها",
                                    font=("Tahoma", 11, "bold"),
                                    bg=BG, fg=TEXT, padx=15, pady=10)
        range_frame.pack(fill="x", pady=(0, 15))

        tk.Radiobutton(range_frame, text="همه موارد", variable=self.data_range,
                       value="all", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(range_frame, text="محدوده تاریخ", variable=self.data_range,
                       value="date_range", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Date range frame (initially hidden)
        self.date_frame = tk.Frame(range_frame, bg=BG)

        tk.Label(self.date_frame, text="از تاریخ:", bg=BG, font=("Tahoma", 9)).pack(side="right", padx=5)
        self.start_date = tk.Entry(self.date_frame, width=12, font=("Tahoma", 9))
        self.start_date.pack(side="right", padx=5)
        self.start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        tk.Label(self.date_frame, text="تا تاریخ:", bg=BG, font=("Tahoma", 9)).pack(side="right", padx=5)
        self.end_date = tk.Entry(self.date_frame, width=12, font=("Tahoma", 9))
        self.end_date.pack(side="right", padx=5)
        self.end_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        # Additional options
        if additional_options:
            for option in additional_options:
                option.pack()

        # Include options
        options_frame = tk.LabelFrame(main_frame, text="تنظیمات خروجی",
                                      font=("Tahoma", 11, "bold"),
                                      bg=BG, fg=TEXT, padx=15, pady=10)
        options_frame.pack(fill="x", pady=(0, 15))

        tk.Checkbutton(options_frame, text="شامل جزئیات", variable=self.include_details,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Checkbutton(options_frame, text="شامل آمار", variable=self.include_stats,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Buttons
        btn_frame = tk.Frame(main_frame, bg=BG)
        btn_frame.pack(fill="x", pady=(10, 0))

        tk.Button(btn_frame, text="انصراف", command=self.destroy,
                  bg=BORDER, fg=TEXT, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="left", padx=5)

        tk.Button(btn_frame, text="خروجی گرفتن", command=self._export,
                  bg=PRIMARY, fg=WHITE, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="right", padx=5)

        # Bind date range radio button
        self.data_range.trace('w', self._on_range_change)

    def _on_range_change(self, *args):
        """Show/hide date range frame"""
        if self.data_range.get() == "date_range":
            self.date_frame.pack(fill="x", pady=(10, 0))
        else:
            self.date_frame.pack_forget()

    def _export(self):
        """Override in child classes"""
        pass

    def _export_to_excel(self, data, filename_prefix):
        """Export to Excel file (returns filename or False)"""
        if not PANDAS_AVAILABLE:
            messagebox.showerror("خطا",
                                 "برای خروجی Excel نیاز به نصب pandas و openpyxl است.\npip install pandas openpyxl")
            return False

        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if not filename:
            return False

        return filename

    def _export_to_pdf(self, data, filename_prefix):
        """Export to PDF file (returns filename or False)"""
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("خطا", "برای خروجی PDF نیاز به نصب reportlab است.\npip install reportlab")
            return False

        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )

        if not filename:
            return False

        return filename


# ==================== INSPECTION EXPORT ====================

class InspectionExportDialog(BaseExportDialog):
    """Dialog for exporting inspection data"""

    def __init__(self, parent, service: InspectionService, inspection: Optional[Inspection] = None,
                 template: Optional[InspectionTemplate] = None):
        self.service = service
        self.inspection = inspection
        self.template = template
        super().__init__(parent, "📤 خروجی بازرسی‌ها")
        self._build_ui()

    def _build_ui(self):
        main_frame = tk.Frame(self, bg=BG)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(main_frame, text="📊 خروجی اطلاعات بازرسی",
                 font=("Tahoma", 16, "bold"), bg=BG, fg=PRIMARY).pack(pady=(0, 20))

        # Export type
        type_frame = tk.LabelFrame(main_frame, text="نوع خروجی",
                                   font=("Tahoma", 11, "bold"),
                                   bg=BG, fg=TEXT, padx=15, pady=10)
        type_frame.pack(fill="x", pady=(0, 15))

        tk.Radiobutton(type_frame, text="📊 Excel", variable=self.export_type,
                       value="excel", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(type_frame, text="📄 PDF", variable=self.export_type,
                       value="pdf", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(type_frame, text="🔄 هر دو (Excel + PDF)", variable=self.export_type,
                       value="both", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Data range
        range_frame = tk.LabelFrame(main_frame, text="محدوده داده‌ها",
                                    font=("Tahoma", 11, "bold"),
                                    bg=BG, fg=TEXT, padx=15, pady=10)
        range_frame.pack(fill="x", pady=(0, 15))

        if self.inspection:
            tk.Radiobutton(range_frame, text="بازرسی جاری", variable=self.data_range,
                           value="current", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        if self.template:
            tk.Radiobutton(range_frame, text=f"قالب: {self.template.name}", variable=self.data_range,
                           value="template", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        tk.Radiobutton(range_frame, text="همه بازرسی‌ها", variable=self.data_range,
                       value="all", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(range_frame, text="محدوده تاریخ", variable=self.data_range,
                       value="date_range", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Date range
        self.date_frame = tk.Frame(range_frame, bg=BG)
        tk.Label(self.date_frame, text="از تاریخ:", bg=BG, font=("Tahoma", 9)).pack(side="right", padx=5)
        self.start_date = tk.Entry(self.date_frame, width=12, font=("Tahoma", 9))
        self.start_date.pack(side="right", padx=5)
        self.start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        tk.Label(self.date_frame, text="تا تاریخ:", bg=BG, font=("Tahoma", 9)).pack(side="right", padx=5)
        self.end_date = tk.Entry(self.date_frame, width=12, font=("Tahoma", 9))
        self.end_date.pack(side="right", padx=5)
        self.end_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        # Options
        options_frame = tk.LabelFrame(main_frame, text="تنظیمات خروجی",
                                      font=("Tahoma", 11, "bold"),
                                      bg=BG, fg=TEXT, padx=15, pady=10)
        options_frame.pack(fill="x", pady=(0, 15))

        self.include_checkpoints = tk.BooleanVar(value=True)
        self.include_comments = tk.BooleanVar(value=True)

        tk.Checkbutton(options_frame, text="شامل چک‌پوینت‌ها", variable=self.include_checkpoints,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Checkbutton(options_frame, text="شامل نظرات", variable=self.include_comments,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Checkbutton(options_frame, text="شامل آمار", variable=self.include_stats,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Buttons
        btn_frame = tk.Frame(main_frame, bg=BG)
        btn_frame.pack(fill="x", pady=(10, 0))

        tk.Button(btn_frame, text="انصراف", command=self.destroy,
                  bg=BORDER, fg=TEXT, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="خروجی گرفتن", command=self._export,
                  bg=PRIMARY, fg=WHITE, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="right", padx=5)

        self.data_range.trace('w', self._on_range_change)

    def _get_data(self):
        """Get inspection data based on selection"""
        range_type = self.data_range.get()

        if range_type == "current" and self.inspection:
            return [self._inspection_to_dict(self.inspection)]
        elif range_type == "template" and self.template:
            inspections = self.service.get_all_inspections()
            return [self._inspection_to_dict(ins) for ins in inspections
                    if ins.template_id == self.template.id]
        elif range_type == "date_range":
            start = self.start_date.get()
            end = self.end_date.get()
            inspections = self.service.get_all_inspections()
            filtered = []
            for ins in inspections:
                if ins.started_at:
                    ins_date = ins.started_at.strftime("%Y-%m-%d")
                    if start <= ins_date <= end:
                        filtered.append(self._inspection_to_dict(ins))
            return filtered
        else:
            inspections = self.service.get_all_inspections()
            return [self._inspection_to_dict(ins) for ins in inspections]

    def _inspection_to_dict(self, inspection: Inspection) -> dict:
        """Convert Inspection model to dictionary"""
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
            "results": results
        }

    def _export(self):
        data = self._get_data()
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!")
            return

        export_type = self.export_type.get()

        try:
            if export_type in ["excel", "both"]:
                self._export_to_excel(data, "inspection_export")
            if export_type in ["pdf", "both"]:
                self._export_to_pdf(data, "inspection_export")

            messagebox.showinfo("موفق", "خروجی با موفقیت ذخیره شد!")
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد خروجی: {str(e)}")

    def _export_to_excel(self, data, filename_prefix):
        filename = super()._export_to_excel(data, filename_prefix)
        if not filename:
            return

        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            for ins in data:
                summary_data.append({
                    "شناسه": ins["id"],
                    "قالب": ins["template_name"],
                    "تجهیز": ins["equipment_name"],
                    "بازرس": ins["inspector_name"],
                    "وضعیت": ins["status"],
                    "نتیجه": ins["overall_result"],
                    "تاریخ شروع": ins["started_at"],
                    "تاریخ پایان": ins["completed_at"]
                })

            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name="خلاصه بازرسی‌ها", index=False)

            # Details sheet
            if self.include_checkpoints.get():
                details_data = []
                for ins in data:
                    for result in ins["results"]:
                        details_data.append({
                            "شناسه بازرسی": ins["id"],
                            "قالب": ins["template_name"],
                            "تجهیز": ins["equipment_name"],
                            "چک‌پوینت": result["checkpoint"],
                            "نتیجه": result["result"],
                            "نظر": result["comment"]
                        })

                if details_data:
                    df_details = pd.DataFrame(details_data)
                    df_details.to_excel(writer, sheet_name="جزئیات بازرسی‌ها", index=False)

    def _export_to_pdf(self, data, filename_prefix):
        filename = super()._export_to_pdf(data, filename_prefix)
        if not filename:
            return

        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
        elements.append(Paragraph("گزارش بازرسی‌ها", title_style))
        elements.append(Spacer(1, 20))

        # Table
        table_data = [["شناسه", "قالب", "تجهیز", "بازرس", "وضعیت", "نتیجه"]]
        for ins in data[:20]:
            table_data.append([
                str(ins["id"]), ins["template_name"], ins["equipment_name"],
                ins["inspector_name"], ins["status"], ins["overall_result"]
            ])

        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A73E8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(table)
        doc.build(elements)


# ==================== EQUIPMENT EXPORT ====================

class EquipmentExportDialog(BaseExportDialog):
    """Dialog for exporting equipment data"""

    def __init__(self, parent, equipment_list, selected_equipment=None):
        self.equipment_list = equipment_list
        self.selected_equipment = selected_equipment
        super().__init__(parent, "📤 خروجی تجهیزات")
        self._build_ui()

    def _build_ui(self):
        main_frame = tk.Frame(self, bg=BG)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(main_frame, text="🔧 خروجی اطلاعات تجهیزات",
                 font=("Tahoma", 16, "bold"), bg=BG, fg=PRIMARY).pack(pady=(0, 20))

        # Export type
        type_frame = tk.LabelFrame(main_frame, text="نوع خروجی",
                                   font=("Tahoma", 11, "bold"),
                                   bg=BG, fg=TEXT, padx=15, pady=10)
        type_frame.pack(fill="x", pady=(0, 15))

        tk.Radiobutton(type_frame, text="📊 Excel", variable=self.export_type,
                       value="excel", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(type_frame, text="📄 PDF", variable=self.export_type,
                       value="pdf", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(type_frame, text="🔄 هر دو (Excel + PDF)", variable=self.export_type,
                       value="both", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Data range
        range_frame = tk.LabelFrame(main_frame, text="محدوده داده‌ها",
                                    font=("Tahoma", 11, "bold"),
                                    bg=BG, fg=TEXT, padx=15, pady=10)
        range_frame.pack(fill="x", pady=(0, 15))

        if self.selected_equipment:
            tk.Radiobutton(range_frame, text=f"تجهیز جاری: {self.selected_equipment['name']}",
                           variable=self.data_range, value="current", bg=BG, font=("Tahoma", 10)).pack(anchor="w",
                                                                                                       pady=2)

        tk.Radiobutton(range_frame, text="همه تجهیزات", variable=self.data_range,
                       value="all", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Options
        options_frame = tk.LabelFrame(main_frame, text="تنظیمات خروجی",
                                      font=("Tahoma", 11, "bold"),
                                      bg=BG, fg=TEXT, padx=15, pady=10)
        options_frame.pack(fill="x", pady=(0, 15))

        self.include_details = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="شامل مشخصات فنی", variable=self.include_details,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        self.include_stats = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="شامل آمار", variable=self.include_stats,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Buttons
        btn_frame = tk.Frame(main_frame, bg=BG)
        btn_frame.pack(fill="x", pady=(10, 0))

        tk.Button(btn_frame, text="انصراف", command=self.destroy,
                  bg=BORDER, fg=TEXT, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="خروجی گرفتن", command=self._export,
                  bg=PRIMARY, fg=WHITE, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="right", padx=5)

    def _get_data(self):
        if self.data_range.get() == "current" and self.selected_equipment:
            return [self.selected_equipment]
        else:
            return self.equipment_list

    def _export(self):
        data = self._get_data()
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!")
            return

        export_type = self.export_type.get()

        try:
            if export_type in ["excel", "both"]:
                self._export_to_excel(data, "equipment_export")
            if export_type in ["pdf", "both"]:
                self._export_to_pdf(data, "equipment_export")

            messagebox.showinfo("موفق", "خروجی با موفقیت ذخیره شد!")
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد خروجی: {str(e)}")

    def _export_to_excel(self, data, filename_prefix):
        filename = super()._export_to_excel(data, filename_prefix)
        if not filename:
            return

        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            export_data = []
            for eq in data:
                row = {
                    "کد": eq.get("code", ""),
                    "نام تجهیز": eq.get("name", ""),
                    "دسته": eq.get("category", ""),
                    "سازنده": eq.get("manufacturer", ""),
                    "مدل": eq.get("model", ""),
                    "شماره سریال": eq.get("serial_number", ""),
                    "موقعیت": eq.get("location", ""),
                    "تاریخ نصب": eq.get("installation_date", ""),
                    "وضعیت": STATUS_FA.get(eq.get("status", ""), eq.get("status", "")),
                    "مشخصات": eq.get("specifications", ""),
                    "توضیحات": eq.get("notes", ""),
                    "تاریخ ایجاد": eq.get("created_at", ""),
                    "آخرین بروزرسانی": eq.get("updated_at", "")
                }
                export_data.append(row)

            df = pd.DataFrame(export_data)
            df.to_excel(writer, sheet_name="تجهیزات", index=False)

            # Auto-adjust column widths
            worksheet = writer.sheets["تجهیزات"]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    def _export_to_pdf(self, data, filename_prefix):
        filename = super()._export_to_pdf(data, filename_prefix)
        if not filename:
            return

        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
        elements.append(Paragraph("گزارش تجهیزات", title_style))
        elements.append(Spacer(1, 20))

        # Create table (limit to 20 rows for PDF)
        table_data = [["کد", "نام", "دسته", "موقعیت", "وضعیت"]]
        for eq in data[:20]:
            table_data.append([
                eq.get("code", ""),
                eq.get("name", ""),
                eq.get("category", ""),
                eq.get("location", ""),
                STATUS_FA.get(eq.get("status", ""), eq.get("status", ""))
            ])

        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A73E8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))

        elements.append(table)

        # Add statistics if requested
        if self.include_stats.get():
            elements.append(Spacer(1, 20))
            stats = {
                "total": len(data),
                "operational": sum(1 for e in data if e.get("status") == "operational"),
                "maintenance": sum(1 for e in data if e.get("status") == "maintenance"),
                "breakdown": sum(1 for e in data if e.get("status") == "breakdown"),
                "inactive": sum(1 for e in data if e.get("status") == "inactive"),
            }
            stats_text = f"""
            <b>آمار کلی تجهیزات:</b><br/>
            کل تجهیزات: {stats['total']}<br/>
            عملیاتی: {stats['operational']}<br/>
            در تعمیر: {stats['maintenance']}<br/>
            خراب: {stats['breakdown']}<br/>
            غیرفعال: {stats['inactive']}
            """
            elements.append(Paragraph(stats_text, styles['Normal']))

        doc.build(elements)


# ==================== PM EXPORT ====================

class PMExportDialog(BaseExportDialog):
    """Dialog for exporting Preventive Maintenance schedules"""

    def __init__(self, parent, pm_records, selected_pm=None):
        self.pm_records = pm_records
        self.selected_pm = selected_pm
        super().__init__(parent, "📤 خروجی برنامه‌های نت پیشگیرانه")
        self._build_ui()

    def _build_ui(self):
        main_frame = tk.Frame(self, bg=BG)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(main_frame, text="🔧 خروجی برنامه‌های نت پیشگیرانه",
                 font=("Tahoma", 16, "bold"), bg=BG, fg=PRIMARY).pack(pady=(0, 20))

        # Export type
        type_frame = tk.LabelFrame(main_frame, text="نوع خروجی",
                                   font=("Tahoma", 11, "bold"),
                                   bg=BG, fg=TEXT, padx=15, pady=10)
        type_frame.pack(fill="x", pady=(0, 15))

        tk.Radiobutton(type_frame, text="📊 Excel", variable=self.export_type,
                       value="excel", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(type_frame, text="📄 PDF", variable=self.export_type,
                       value="pdf", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(type_frame, text="🔄 هر دو (Excel + PDF)", variable=self.export_type,
                       value="both", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Data range
        range_frame = tk.LabelFrame(main_frame, text="محدوده داده‌ها",
                                    font=("Tahoma", 11, "bold"),
                                    bg=BG, fg=TEXT, padx=15, pady=10)
        range_frame.pack(fill="x", pady=(0, 15))

        if self.selected_pm:
            tk.Radiobutton(range_frame, text=f"برنامه جاری: {self.selected_pm.get('title', '')}",
                           variable=self.data_range, value="current", bg=BG, font=("Tahoma", 10)).pack(anchor="w",
                                                                                                       pady=2)

        tk.Radiobutton(range_frame, text="همه برنامه‌ها", variable=self.data_range,
                       value="all", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Options
        options_frame = tk.LabelFrame(main_frame, text="تنظیمات خروجی",
                                      font=("Tahoma", 11, "bold"),
                                      bg=BG, fg=TEXT, padx=15, pady=10)
        options_frame.pack(fill="x", pady=(0, 15))

        self.include_details = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="شامل جزئیات", variable=self.include_details,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        self.include_stats = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="شامل آمار", variable=self.include_stats,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Buttons
        btn_frame = tk.Frame(main_frame, bg=BG)
        btn_frame.pack(fill="x", pady=(10, 0))

        tk.Button(btn_frame, text="انصراف", command=self.destroy,
                  bg=BORDER, fg=TEXT, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="خروجی گرفتن", command=self._export,
                  bg=PRIMARY, fg=WHITE, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="right", padx=5)

    def _get_data(self):
        if self.data_range.get() == "current" and self.selected_pm:
            return [self.selected_pm]
        else:
            return self.pm_records

    def _export(self):
        data = self._get_data()
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!")
            return

        export_type = self.export_type.get()

        try:
            if export_type in ["excel", "both"]:
                self._export_to_excel(data, "pm_export")
            if export_type in ["pdf", "both"]:
                self._export_to_pdf(data, "pm_export")

            messagebox.showinfo("موفق", "خروجی با موفقیت ذخیره شد!")
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد خروجی: {str(e)}")

    def _export_to_excel(self, data, filename_prefix):
        filename = super()._export_to_excel(data, filename_prefix)
        if not filename:
            return

        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name="برنامه‌های نت", index=False)

            # Auto-adjust column widths
            worksheet = writer.sheets["برنامه‌های نت"]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    def _export_to_pdf(self, data, filename_prefix):
        filename = super()._export_to_pdf(data, filename_prefix)
        if not filename:
            return

        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
        elements.append(Paragraph("گزارش برنامه‌های نت پیشگیرانه", title_style))
        elements.append(Spacer(1, 20))

        # Table
        table_data = [["شناسه", "عنوان", "تجهیز", "دوره", "وضعیت", "موعد بعدی"]]
        for item in data[:20]:
            table_data.append([
                str(item.get("id", "")),
                item.get("title", ""),
                item.get("equipment_name", ""),
                item.get("frequency", ""),
                item.get("is_active", ""),
                item.get("next_due", "")
            ])

        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A73E8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(table)
        doc.build(elements)


# ==================== WORK ORDER EXPORT ====================

class WorkOrderExportDialog(BaseExportDialog):
    """Dialog for exporting work orders"""

    def __init__(self, parent, wo_repo, selected_wo_id=None):
        self.wo_repo = wo_repo
        self.selected_wo_id = selected_wo_id
        super().__init__(parent, "📤 خروجی دستورکارها")
        self._build_ui()

    def _build_ui(self):
        main_frame = tk.Frame(self, bg=BG)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(main_frame, text="📋 خروجی دستورکارها",
                 font=("Tahoma", 16, "bold"), bg=BG, fg=PRIMARY).pack(pady=(0, 20))

        # Export type
        type_frame = tk.LabelFrame(main_frame, text="نوع خروجی",
                                   font=("Tahoma", 11, "bold"),
                                   bg=BG, fg=TEXT, padx=15, pady=10)
        type_frame.pack(fill="x", pady=(0, 15))

        tk.Radiobutton(type_frame, text="📊 Excel", variable=self.export_type,
                       value="excel", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(type_frame, text="📄 PDF", variable=self.export_type,
                       value="pdf", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(type_frame, text="🔄 هر دو (Excel + PDF)", variable=self.export_type,
                       value="both", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Data range
        range_frame = tk.LabelFrame(main_frame, text="محدوده داده‌ها",
                                    font=("Tahoma", 11, "bold"),
                                    bg=BG, fg=TEXT, padx=15, pady=10)
        range_frame.pack(fill="x", pady=(0, 15))

        if self.selected_wo_id:
            tk.Radiobutton(range_frame, text="دستورکار جاری",
                           variable=self.data_range, value="current", bg=BG, font=("Tahoma", 10)).pack(anchor="w",
                                                                                                       pady=2)

        tk.Radiobutton(range_frame, text="همه دستورکارها", variable=self.data_range,
                       value="all", bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Status filter
        filter_frame = tk.LabelFrame(main_frame, text="فیلتر وضعیت",
                                     font=("Tahoma", 11, "bold"),
                                     bg=BG, fg=TEXT, padx=15, pady=10)
        filter_frame.pack(fill="x", pady=(0, 15))

        self.status_filter = tk.StringVar(value="all")
        statuses = [("همه", "all"), ("در انتظار", "pending"), ("در حال انجام", "in_progress"),
                    ("تکمیل شده", "completed"), ("لغو شده", "cancelled")]

        for text, value in statuses:
            tk.Radiobutton(filter_frame, text=text, variable=self.status_filter,
                           value=value, bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Options
        options_frame = tk.LabelFrame(main_frame, text="تنظیمات خروجی",
                                      font=("Tahoma", 11, "bold"),
                                      bg=BG, fg=TEXT, padx=15, pady=10)
        options_frame.pack(fill="x", pady=(0, 15))

        tk.Checkbutton(options_frame, text="شامل جزئیات", variable=self.include_details,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)
        tk.Checkbutton(options_frame, text="شامل آمار", variable=self.include_stats,
                       bg=BG, font=("Tahoma", 10)).pack(anchor="w", pady=2)

        # Buttons
        btn_frame = tk.Frame(main_frame, bg=BG)
        btn_frame.pack(fill="x", pady=(10, 0))

        tk.Button(btn_frame, text="انصراف", command=self.destroy,
                  bg=BORDER, fg=TEXT, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="خروجی گرفتن", command=self._export,
                  bg=PRIMARY, fg=WHITE, font=("Tahoma", 10, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="right", padx=5)

    def _get_data(self):
        # Get all work orders from repository
        try:
            all_wos = self.wo_repo.get_all_work_orders()
        except Exception:
            # Fallback if method doesn't exist
            all_wos = []

        # Apply status filter
        status = self.status_filter.get()
        if status != "all":
            all_wos = [wo for wo in all_wos if wo.get("status") == status]

        # If current selected
        if self.data_range.get() == "current" and self.selected_wo_id:
            # Filter to the selected ID
            all_wos = [wo for wo in all_wos if wo.get("id") == self.selected_wo_id]

        return all_wos

    def _export(self):
        data = self._get_data()
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!")
            return

        export_type = self.export_type.get()

        try:
            if export_type in ["excel", "both"]:
                self._export_to_excel(data, "work_order_export")
            if export_type in ["pdf", "both"]:
                self._export_to_pdf(data, "work_order_export")

            messagebox.showinfo("موفق", "خروجی با موفقیت ذخیره شد!")
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد خروجی: {str(e)}")

    def _export_to_excel(self, data, filename_prefix):
        filename = super()._export_to_excel(data, filename_prefix)
        if not filename:
            return

        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name="دستورکارها", index=False)

            # Auto-adjust column widths
            worksheet = writer.sheets["دستورکارها"]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    def _export_to_pdf(self, data, filename_prefix):
        filename = super()._export_to_pdf(data, filename_prefix)
        if not filename:
            return

        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
        elements.append(Paragraph("گزارش دستورکارها", title_style))
        elements.append(Spacer(1, 20))

        # Table
        table_data = [["شناسه", "عنوان", "تجهیز", "اولویت", "وضعیت", "تاریخ درخواست"]]
        for item in data[:20]:
            table_data.append([
                str(item.get("id", "")),
                item.get("title", ""),
                item.get("equipment_name", ""),
                item.get("priority", ""),
                item.get("status", ""),
                item.get("request_date", "")
            ])

        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A73E8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(table)
        doc.build(elements)


# ==================== HELPER FUNCTIONS ====================

def run_inspection_export(parent, service: InspectionService,
                          selected_inspection_id: Optional[int] = None,
                          selected_template=None):
    """Run inspection export dialog"""
    inspection = None
    if selected_inspection_id:
        inspection = service.get_inspection(selected_inspection_id)

    dialog = InspectionExportDialog(parent, service, inspection, selected_template)
    parent.wait_window(dialog)


def run_equipment_export(parent, equipment_list, selected_equipment=None):
    """Run equipment export dialog"""
    dialog = EquipmentExportDialog(parent, equipment_list, selected_equipment)
    parent.wait_window(dialog)


def run_pm_export(parent, pm_records, selected_pm=None):
    """Run PM export dialog"""
    dialog = PMExportDialog(parent, pm_records, selected_pm)
    parent.wait_window(dialog)

    
def run_work_order_export(parent, wo_repo, selected_wo_id=None):
    """Run work order export dialog"""
    dialog = WorkOrderExportDialog(parent, wo_repo, selected_wo_id)
    parent.wait_window(dialog)