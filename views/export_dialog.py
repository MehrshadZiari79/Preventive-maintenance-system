# views/export_dialog.py
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

from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

BG = GRAY_BG
PRIMARY = NAVY
TEXT = TEXT_DARK
BORDER = GRAY_BORDER
CARD_BG = WHITE


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
        # ── Header (stays fixed at top) ──────────────────────────
        header = tk.Frame(self, bg=PRIMARY, height=55)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=title_text, font=FONT_HEADING,
                 bg=PRIMARY, fg=WHITE).pack(pady=14)

        # ── Scrollable content area ──────────────────────────────
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=BG)

        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        vsb.pack(side="right", fill="y")

        # ── Main content (everything inside scrollable) ─────────
        main_card = tk.Frame(scrollable, bg=BORDER)
        main_card.pack(fill="both", expand=True, padx=20, pady=15)
        self.main_frame = tk.Frame(main_card, bg=CARD_BG)
        self.main_frame.pack(fill="both", expand=True, padx=1, pady=1)

        # Type frame
        type_frame = tk.LabelFrame(self.main_frame, text="نوع خروجی",
                                   font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                   padx=15, pady=10)
        type_frame.pack(fill="x", pady=(10, 10), padx=10)
        tk.Radiobutton(type_frame, text="📊 Excel", variable=tk.StringVar(value="excel"),
                       value="excel", bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)

        # Range frame
        range_frame = tk.LabelFrame(self.main_frame, text="محدوده داده‌ها",
                                    font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                    padx=15, pady=10)
        range_frame.pack(fill="x", pady=(0, 10), padx=10)
        tk.Radiobutton(range_frame, text="همه موارد", variable=self.data_range,
                       value="all", bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)
        tk.Radiobutton(range_frame, text="محدوده تاریخ", variable=self.data_range,
                       value="date_range", bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)

        self.date_frame = tk.Frame(range_frame, bg=CARD_BG)
        tk.Label(self.date_frame, text="از تاریخ:", bg=CARD_BG, font=FONT_SMALL).pack(side="right", padx=5)
        self.start_date = tk.Entry(self.date_frame, width=12, font=FONT_SMALL)
        self.start_date.pack(side="right", padx=5)
        self.start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        tk.Label(self.date_frame, text="تا تاریخ:", bg=CARD_BG, font=FONT_SMALL).pack(side="right", padx=5)
        self.end_date = tk.Entry(self.date_frame, width=12, font=FONT_SMALL)
        self.end_date.pack(side="right", padx=5)
        self.end_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        # Options frame
        self.options_frame = tk.LabelFrame(self.main_frame, text="تنظیمات خروجی",
                                           font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                           padx=15, pady=10)
        self.options_frame.pack(fill="x", pady=(0, 10), padx=10)
        tk.Checkbutton(self.options_frame, text="شامل جزئیات", variable=self.include_details,
                       bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)
        tk.Checkbutton(self.options_frame, text="شامل آمار", variable=self.include_stats,
                       bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)

        if additional_options:
            for opt in additional_options:
                tk.Checkbutton(self.options_frame, text=opt["text"], variable=opt["var"],
                               bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)

        # ── Buttons (outside scrollable, at bottom of dialog) ──
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=15)
        tk.Button(btn_frame, text="انصراف", command=self.destroy,
                  bg=BORDER, fg=TEXT, font=FONT_NORMAL,
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="خروجی گرفتن", command=self._export,
                  bg=PRIMARY, fg=WHITE, font=FONT_NORMAL,
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="right", padx=5)

        self.data_range.trace('w', self._on_range_change)

    def _on_range_change(self, *args):
        if self.data_range.get() == "date_range":
            self.date_frame.pack(fill="x", pady=(10, 0))
        else:
            self.date_frame.pack_forget()

    def _export(self):
        pass


class InspectionExportDialog(BaseExportDialog):
    def __init__(self, parent, service, inspection=None, template=None):
        self.service = service
        self.inspection = inspection
        self.template = template
        super().__init__(parent, "📤 خروجی بازرسی‌ها")
        self.include_checkpoints = tk.BooleanVar(value=True)
        self.include_comments = tk.BooleanVar(value=True)
        add_opts = [
            {"text": "شامل چک‌پوینت‌ها", "var": self.include_checkpoints},
            {"text": "شامل نظرات", "var": self.include_comments},
        ]
        self._build_ui("📊 خروجی اطلاعات بازرسی", additional_options=add_opts)

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


class EquipmentExportDialog(tk.Toplevel):
    def __init__(self, parent, equipment_list, selected_equipment=None):
        super().__init__(parent)
        self.equipment_list = equipment_list
        self.selected_equipment = selected_equipment
        self.title("📤 خروجی تجهیزات")
        self.geometry("750x700")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.winfo_screenheight() // 2) - (550 // 2)
        self.geometry(f"+{x}+{y}")

        self.data_range = tk.StringVar(value="current" if selected_equipment else "all")
        self.include_details = tk.BooleanVar(value=True)
        self.include_stats = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────
        header = tk.Frame(self, bg=PRIMARY, height=55)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🔧 خروجی اطلاعات تجهیزات", font=FONT_HEADING,
                 bg=PRIMARY, fg=WHITE).pack(pady=14)

        # ── Scrollable area ────────────────────────────────────
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=BG)

        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        vsb.pack(side="right", fill="y")

        main = tk.Frame(scrollable, bg=CARD_BG)
        main.pack(fill="both", expand=True, padx=15, pady=15)

        # Range frame
        range_frame = tk.LabelFrame(main, text="محدوده داده‌ها",
                                    font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                    padx=15, pady=10)
        range_frame.pack(fill="x", pady=(10, 10), padx=10)
        tk.Radiobutton(range_frame, text="همه موارد", variable=self.data_range,
                       value="all", bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)
        tk.Radiobutton(range_frame, text="تجهیز انتخاب شده", variable=self.data_range,
                       value="current", bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)
        tk.Radiobutton(range_frame, text="محدوده تاریخ", variable=self.data_range,
                       value="date_range", bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)

        self.date_frame = tk.Frame(range_frame, bg=CARD_BG)
        tk.Label(self.date_frame, text="از تاریخ:", bg=CARD_BG, font=FONT_SMALL).pack(side="right", padx=5)
        self.start_date = tk.Entry(self.date_frame, width=12, font=FONT_SMALL)
        self.start_date.pack(side="right", padx=5)
        self.start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        tk.Label(self.date_frame, text="تا تاریخ:", bg=CARD_BG, font=FONT_SMALL).pack(side="right", padx=5)
        self.end_date = tk.Entry(self.date_frame, width=12, font=FONT_SMALL)
        self.end_date.pack(side="right", padx=5)
        self.end_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        # Options frame
        options_frame = tk.LabelFrame(main, text="تنظیمات خروجی",
                                      font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                      padx=15, pady=10)
        options_frame.pack(fill="x", pady=(0, 10), padx=10)
        tk.Checkbutton(options_frame, text="شامل جزئیات", variable=self.include_details,
                       bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)
        tk.Checkbutton(options_frame, text="شامل آمار", variable=self.include_stats,
                       bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)

        # ── Buttons (outside scrollable) ──────────────────────
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=15)
        tk.Button(btn_frame, text="انصراف", command=self.destroy,
                  bg=BORDER, fg=TEXT, font=FONT_NORMAL,
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="خروجی گرفتن", command=self._export,
                  bg=PRIMARY, fg=WHITE, font=FONT_NORMAL,
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="right", padx=5)

        self.data_range.trace('w', self._on_range_change)
        self._on_range_change()

    def _on_range_change(self, *args):
        if self.data_range.get() == "date_range":
            self.date_frame.pack(fill="x", pady=(10, 0))
        else:
            self.date_frame.pack_forget()

    def _get_data(self):
        range_type = self.data_range.get()
        if range_type == "current" and self.selected_equipment:
            return [self.selected_equipment]
        elif range_type == "date_range":
            start = self.start_date.get()
            end = self.end_date.get()
            filtered = []
            for eq in self.equipment_list:
                date_str = eq.get("updated_at", "") or eq.get("installation_date", "")
                if date_str and start <= date_str[:10] <= end:
                    filtered.append(eq)
            return filtered
        else:
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


class WorkOrderExportDialog(BaseExportDialog):
    def __init__(self, parent, wo_repo, selected_wo_id=None):
        self.wo_repo = wo_repo
        self.selected_wo_id = selected_wo_id

        self.filter_pm = tk.BooleanVar(value=True)
        self.filter_cm = tk.BooleanVar(value=True)
        self.filter_em = tk.BooleanVar(value=True)
        self.filter_insp = tk.BooleanVar(value=True)
        self.equipment_category_var = tk.StringVar(value="همه")
        self.specific_equipment_var = tk.StringVar(value="")
        self.status_filter = tk.StringVar(value="all")

        super().__init__(parent, "📤 خروجی دستورکارها", width=750, height=800)

        # Make the entire content scrollable
        self._make_scrollable()

        # Build the common UI first
        self._build_ui("📋 خروجی دستورکارها")

        # Now add custom filters
        self._build_work_order_filters()

        # Load equipment list for the searchable combo
        self._load_equipment()

    def _make_scrollable(self):
        """Wrap the whole dialog in a canvas + scrollbar so it's scrollable."""
        self.scroll_canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.scroll_canvas.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.scroll_canvas.yview)
        vsb.pack(side="right", fill="y")
        self.scroll_canvas.configure(yscrollcommand=vsb.set)

        self.scroll_frame = tk.Frame(self.scroll_canvas, bg=BG)
        self.scroll_frame.bind("<Configure>",
                               lambda e: self.scroll_canvas.configure(
                                   scrollregion=self.scroll_canvas.bbox("all")))
        self.scroll_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")

    def _build_ui(self, title_text, additional_options=None):
        # Override to place everything inside self.scroll_frame
        header = tk.Frame(self.scroll_frame, bg=PRIMARY, height=55)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=title_text, font=FONT_HEADING,
                 bg=PRIMARY, fg=WHITE).pack(pady=14)

        main_card = tk.Frame(self.scroll_frame, bg=BORDER)
        main_card.pack(fill="both", expand=True, padx=20, pady=15)
        self.main_frame = tk.Frame(main_card, bg=CARD_BG)
        self.main_frame.pack(fill="both", expand=True, padx=1, pady=1)

        type_frame = tk.LabelFrame(self.main_frame, text="نوع خروجی",
                                   font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                   padx=15, pady=10)
        type_frame.pack(fill="x", pady=(10, 10), padx=10)
        tk.Radiobutton(type_frame, text="📊 Excel", variable=tk.StringVar(value="excel"),
                       value="excel", bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)

        range_frame = tk.LabelFrame(self.main_frame, text="محدوده داده‌ها",
                                    font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                    padx=15, pady=10)
        range_frame.pack(fill="x", pady=(0, 10), padx=10)
        tk.Radiobutton(range_frame, text="همه موارد", variable=self.data_range,
                       value="all", bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)
        tk.Radiobutton(range_frame, text="محدوده تاریخ", variable=self.data_range,
                       value="date_range", bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)

        self.date_frame = tk.Frame(range_frame, bg=CARD_BG)
        tk.Label(self.date_frame, text="از تاریخ:", bg=CARD_BG, font=FONT_SMALL).pack(side="right", padx=5)
        self.start_date = tk.Entry(self.date_frame, width=12, font=FONT_SMALL)
        self.start_date.pack(side="right", padx=5)
        self.start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        tk.Label(self.date_frame, text="تا تاریخ:", bg=CARD_BG, font=FONT_SMALL).pack(side="right", padx=5)
        self.end_date = tk.Entry(self.date_frame, width=12, font=FONT_SMALL)
        self.end_date.pack(side="right", padx=5)
        self.end_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        self.options_frame = tk.LabelFrame(self.main_frame, text="تنظیمات خروجی",
                                           font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                           padx=15, pady=10)
        self.options_frame.pack(fill="x", pady=(0, 10), padx=10)
        tk.Checkbutton(self.options_frame, text="شامل جزئیات", variable=self.include_details,
                       bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)
        tk.Checkbutton(self.options_frame, text="شامل آمار", variable=self.include_stats,
                       bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)

        if additional_options:
            for opt in additional_options:
                tk.Checkbutton(self.options_frame, text=opt["text"], variable=opt["var"],
                               bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)

        # Buttons (outside scrollable, at bottom of dialog)
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=15)
        tk.Button(btn_frame, text="انصراف", command=self.destroy,
                  bg=BORDER, fg=TEXT, font=FONT_NORMAL,
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="خروجی گرفتن", command=self._export,
                  bg=PRIMARY, fg=WHITE, font=FONT_NORMAL,
                  relief="flat", cursor="hand2", padx=20, pady=8).pack(side="right", padx=5)

        self.data_range.trace('w', self._on_range_change)

    def _build_work_order_filters(self):
        main = self.main_frame

        status_frame = tk.LabelFrame(main, text="فیلتر وضعیت",
                                     font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                     padx=15, pady=10)
        status_frame.pack(fill="x", pady=(0, 10), padx=10, before=self.options_frame)
        statuses = [
            ("همه", "all"),
            ("در انتظار تأیید", "pending_approval"),
            ("در انتظار", "pending"),
            ("در حال انجام", "in_progress"),
            ("درخواست اتمام", "finish_requested"),
            ("تایید شده", "approved"),
            ("رد شده", "rejected")
        ]
        for text, value in statuses:
            tk.Radiobutton(status_frame, text=text, variable=self.status_filter,
                           value=value, bg=CARD_BG, font=FONT_NORMAL).pack(anchor="w", pady=2)

        opts = self.options_frame

        tk.Label(opts, text="نوع دستور کار:", font=FONT_SMALL, bg=CARD_BG, fg=TEXT).pack(anchor="w", pady=(10,2))
        for text, var in [("پیشگیرانه (PM)", self.filter_pm), ("اصلاحی (CM)", self.filter_cm),
                          ("اضطراری (EM)", self.filter_em), ("بازرسی", self.filter_insp)]:
            tk.Checkbutton(opts, text=text, variable=var, bg=CARD_BG, font=FONT_SMALL).pack(anchor="w")

        tk.Label(opts, text="دسته تجهیز:", font=FONT_SMALL, bg=CARD_BG, fg=TEXT).pack(anchor="w", pady=(10,2))
        from database.equipment_repository import EquipmentRepository
        from database.db import SessionLocal
        eq_repo = EquipmentRepository(SessionLocal)
        cats = eq_repo.get_categories()
        cat_combo = ttk.Combobox(opts, textvariable=self.equipment_category_var,
                                 values=["همه"] + cats, state="readonly", width=20, font=FONT_SMALL)
        cat_combo.pack(anchor="w", pady=2)

        tk.Label(opts, text="تجهیز خاص:", font=FONT_SMALL, bg=CARD_BG, fg=TEXT).pack(anchor="w", pady=(10,2))
        from views.searchable_combobox import SearchableCombobox
        self.equipment_combo = SearchableCombobox(opts, font=FONT_SMALL, state="normal", width=30)
        self.equipment_combo.pack(anchor="w", pady=2)

    def _load_equipment(self):
        from database.equipment_repository import EquipmentRepository
        from database.db import SessionLocal
        eq_repo = EquipmentRepository(SessionLocal)
        eqs = eq_repo.get_all_equipment()
        eq_names = [f"{eq['code']} - {eq['name']}" for eq in eqs]
        self.equipment_combo.set_completion_list(eq_names)
        self.eq_map = {f"{eq['code']} - {eq['name']}": eq['id'] for eq in eqs}

    def _on_range_change(self, *args):
        if self.data_range.get() == "date_range":
            self.date_frame.pack(fill="x", pady=(10, 0))
        else:
            self.date_frame.pack_forget()

    def _get_data(self):
        try:
            all_wos = self.wo_repo.get_all()
        except Exception:
            all_wos = []

        status = self.status_filter.get()
        if status != "all":
            all_wos = [wo for wo in all_wos if wo.status.value == status]

        allowed_types = []
        if self.filter_pm.get(): allowed_types.extend(["PREVENTIVE", "PM"])
        if self.filter_cm.get(): allowed_types.append("CORRECTIVE")
        if self.filter_em.get(): allowed_types.append("EMERGENCY")
        if self.filter_insp.get(): allowed_types.append("INSPECTION")
        if allowed_types:
            all_wos = [wo for wo in all_wos if wo.type.name in allowed_types]

        cat = self.equipment_category_var.get()
        if cat != "همه":
            all_wos = [wo for wo in all_wos if wo.equipment.category == cat]

        eq_name = self.equipment_combo.get()
        if eq_name and eq_name in self.eq_map:
            eq_id = self.eq_map[eq_name]
            all_wos = [wo for wo in all_wos if wo.equipment_id == eq_id]

        if self.data_range.get() == "date_range":
            start = self.start_date.get()
            end = self.end_date.get()
            filtered = []
            for wo in all_wos:
                if wo.scheduled_date:
                    wo_date = wo.scheduled_date.strftime("%Y-%m-%d")
                    if start <= wo_date <= end:
                        filtered.append(wo)
            all_wos = filtered

        if self.selected_wo_id:
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


# ── Helper functions ──────────────────────────────────────────────
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