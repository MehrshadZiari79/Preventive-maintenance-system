# views/inspection_view.py
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
from datetime import datetime

from database.db import SessionLocal
from database.inspection_repository import InspectionRepository
from services.inspection_service import InspectionService
from views.inspection_dialog  import (
    TemplateDialog,
    InspectionStartDialog,
    InspectionExecuteDialog,
    InspectionDetailDialog,
)

# ─────────────────────────── Theme ───────────────────────────
BG      = "#F0F4F8"
WHITE   = "#FFFFFF"
PRIMARY = "#1A73E8"
DANGER  = "#DC3545"
SUCCESS = "#28A745"
TEXT    = "#202124"
SUBTLE  = "#5F6368"
BORDER  = "#DADCE0"

FONT_TITLE  = ("Tahoma", 14, "bold")
FONT_LABEL  = ("Tahoma", 10, "bold")
FONT_INPUT  = ("Tahoma", 10)
FONT_SMALL  = ("Tahoma", 9)

STATUS_FA = {
    "in_progress": "🔄 در حال انجام",
    "completed":   "✅ تکمیل شده",
    "cancelled":   "❌ لغو شده",
}

RESULT_FA = {
    "pass":    "✅ قبول",
    "fail":    "❌ رد",
    "partial": "⚠️ جزئی",
}

FREQ_FA = {
    "daily":     "روزانه",
    "weekly":    "هفتگی",
    "monthly":   "ماهانه",
    "quarterly": "سه‌ماهه",
    "yearly":    "سالانه",
}


class InspectionView(tk.Frame):
    """Main inspection management view with tabs"""

    def __init__(self, parent, current_user: dict):
        super().__init__(parent, bg=BG)
        self.current_user = current_user
        self.db = SessionLocal()
        self.repo = InspectionRepository()
        self.service = InspectionService(self.db)

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=PRIMARY, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🔍  مدیریت بازرسی‌ها", font=FONT_TITLE,
                 bg=PRIMARY, fg=WHITE).pack(side="right", padx=20, pady=20)

        # Stats bar
        stats_frame = tk.Frame(self, bg=WHITE, height=80)
        stats_frame.pack(fill="x", padx=20, pady=(15, 10))
        stats_frame.pack_propagate(False)

        self.stat_labels = {}
        for key, label in [
            ("total", "کل بازرسی‌ها"),
            ("in_progress", "در حال انجام"),
            ("completed", "تکمیل شده"),
            ("cancelled", "لغو شده"),
        ]:
            card = tk.Frame(stats_frame, bg=WHITE)
            card.pack(side="right", padx=15, pady=10)
            tk.Label(card, text=label, font=FONT_SMALL,
                     bg=WHITE, fg=SUBTLE).pack()
            lbl = tk.Label(card, text="0", font=("Tahoma", 18, "bold"),
                          bg=WHITE, fg=PRIMARY)
            lbl.pack()
            self.stat_labels[key] = lbl

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        # Tab 1: Templates
        self.templates_tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.templates_tab, text="  قالب‌های بازرسی  ")
        self._build_templates_tab()

        # Tab 2: Inspections
        self.inspections_tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.inspections_tab, text="  بازرسی‌ها  ")
        self._build_inspections_tab()

    # ═══════════════════════════ TEMPLATES TAB ═══════════════════════════

    def _build_templates_tab(self):
        # Toolbar
        toolbar = tk.Frame(self.templates_tab, bg=BG)
        toolbar.pack(fill="x", pady=(10, 5))

        tk.Button(toolbar, text="➕ قالب جدید", font=FONT_LABEL,
                  bg=PRIMARY, fg=WHITE, relief="flat", cursor="hand2",
                  padx=15, pady=7, command=self._new_template).pack(side="right", padx=5)
        tk.Button(toolbar, text="✏️ ویرایش", font=FONT_INPUT,
                  bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                  padx=15, pady=7, command=self._edit_template).pack(side="right", padx=5)
        tk.Button(toolbar, text="🗑️ حذف", font=FONT_INPUT,
                  bg=DANGER, fg=WHITE, relief="flat", cursor="hand2",
                  padx=15, pady=7, command=self._delete_template).pack(side="right", padx=5)
        tk.Button(toolbar, text="🔄 بروزرسانی", font=FONT_INPUT,
                  bg=BORDER, fg=TEXT, relief="flat", cursor="hand2",
                  padx=15, pady=7, command=self._load_templates).pack(side="left", padx=5)

        # Search
        search_frame = tk.Frame(self.templates_tab, bg=BG)
        search_frame.pack(fill="x", pady=5)

        tk.Label(search_frame, text="جستجو:", font=FONT_INPUT,
                 bg=BG, fg=TEXT).pack(side="right", padx=5)
        self.template_search_var = tk.StringVar()
        self.template_search_var.trace("w", lambda *_: self._filter_templates())
        tk.Entry(search_frame, textvariable=self.template_search_var,
                 font=FONT_INPUT, width=30, relief="solid", bd=1).pack(side="right", padx=5)

        # Treeview
        tree_frame = tk.Frame(self.templates_tab, bg=WHITE)
        tree_frame.pack(fill="both", expand=True, pady=5)

        cols = ("id", "name", "equipment", "frequency", "checkpoints", "duration", "status")
        self.templates_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12)

        self.templates_tree.heading("id",          text="شناسه")
        self.templates_tree.heading("name",        text="نام قالب")
        self.templates_tree.heading("equipment",   text="تجهیز")
        self.templates_tree.heading("frequency",   text="دوره تناوب")
        self.templates_tree.heading("checkpoints", text="تعداد چک‌پوینت")
        self.templates_tree.heading("duration",    text="مدت (دقیقه)")
        self.templates_tree.heading("status",      text="وضعیت")

        self.templates_tree.column("id",          width=60,  anchor="center")
        self.templates_tree.column("name",        width=220, anchor="w")
        self.templates_tree.column("equipment",   width=150, anchor="w")
        self.templates_tree.column("frequency",   width=100, anchor="center")
        self.templates_tree.column("checkpoints", width=100, anchor="center")
        self.templates_tree.column("duration",    width=90,  anchor="center")
        self.templates_tree.column("status",      width=90,  anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.templates_tree.yview)
        self.templates_tree.configure(yscrollcommand=vsb.set)

        self.templates_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.templates_tree.bind("<Double-1>", lambda e: self._edit_template())

    def _load_templates(self):
        self.templates_tree.delete(*self.templates_tree.get_children())
        templates = self.repo.get_all_templates()

        for t in templates:
            status = "✅ فعال" if t["is_active"] else "❌ غیرفعال"
            freq = FREQ_FA.get(t["frequency"], t["frequency"])

            # Count checkpoints
            cp_count = len(self.repo.get_checkpoints_by_template(t["id"]))

            self.templates_tree.insert("", "end", values=(
                t["id"],
                t["name"],
                t["equipment_name"],
                freq,
                cp_count,
                t["estimated_duration_minutes"],
                status,
            ))

    def _filter_templates(self):
        search = self.template_search_var.get().strip().lower()
        for item in self.templates_tree.get_children():
            values = self.templates_tree.item(item)["values"]
            name = str(values[1]).lower()
            if search in name:
                self.templates_tree.reattach(item, "", "end")
            else:
                self.templates_tree.detach(item)

    def _new_template(self):
        dlg = TemplateDialog(self, self.db, self.service)
        self.wait_window(dlg)
        if dlg.result:
            self._load_templates()

    def _edit_template(self):
        sel = self.templates_tree.selection()
        if not sel:
            messagebox.showwarning("انتخاب", "لطفاً یک قالب انتخاب کنید.", parent=self)
            return

        template_id = int(self.templates_tree.item(sel[0])["values"][0])
        dlg = TemplateDialog(self, self.db, self.service, template_id)
        self.wait_window(dlg)
        if dlg.result:
            self._load_templates()

    def _delete_template(self):
        sel = self.templates_tree.selection()
        if not sel:
            messagebox.showwarning("انتخاب", "لطفاً یک قالب انتخاب کنید.", parent=self)
            return

        if not messagebox.askyesno("حذف", "آیا از حذف این قالب مطمئن هستید؟", parent=self):
            return

        template_id = int(self.templates_tree.item(sel[0])["values"][0])
        success, msg = self.repo.delete_template(template_id)

        if success:
            messagebox.showinfo("موفق", msg, parent=self)
            self._load_templates()
        else:
            messagebox.showerror("خطا", msg, parent=self)

    # ═══════════════════════════ INSPECTIONS TAB ═══════════════════════════

    def _build_inspections_tab(self):
        # Toolbar
        toolbar = tk.Frame(self.inspections_tab, bg=BG)
        toolbar.pack(fill="x", pady=(10, 5))

        tk.Button(toolbar, text="🔍 بازرسی جدید", font=FONT_LABEL,
                  bg=PRIMARY, fg=WHITE, relief="flat", cursor="hand2",
                  padx=15, pady=7, command=self._start_inspection).pack(side="right", padx=5)
        tk.Button(toolbar, text="▶️ ادامه بازرسی", font=FONT_INPUT,
                  bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                  padx=15, pady=7, command=self._continue_inspection).pack(side="right", padx=5)
        tk.Button(toolbar, text="📋 جزئیات", font=FONT_INPUT,
                  bg="#6C757D", fg=WHITE, relief="flat", cursor="hand2",
                  padx=15, pady=7, command=self._view_inspection).pack(side="right", padx=5)
        tk.Button(toolbar, text="🔄 بروزرسانی", font=FONT_INPUT,
                  bg=BORDER, fg=TEXT, relief="flat", cursor="hand2",
                  padx=15, pady=7, command=self._load_inspections).pack(side="left", padx=5)

        # Filter
        filter_frame = tk.Frame(self.inspections_tab, bg=BG)
        filter_frame.pack(fill="x", pady=5)

        tk.Label(filter_frame, text="وضعیت:", font=FONT_INPUT,
                 bg=BG, fg=TEXT).pack(side="right", padx=5)
        self.status_filter_var = tk.StringVar(value="همه")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.status_filter_var,
                                    values=["همه", "در حال انجام", "تکمیل شده", "لغو شده"],
                                    state="readonly", width=15, font=FONT_INPUT)
        status_combo.pack(side="right", padx=5)
        status_combo.bind("<<ComboboxSelected>>", lambda e: self._filter_inspections())

        tk.Label(filter_frame, text="جستجو:", font=FONT_INPUT,
                 bg=BG, fg=TEXT).pack(side="right", padx=(20, 5))
        self.inspection_search_var = tk.StringVar()
        self.inspection_search_var.trace("w", lambda *_: self._filter_inspections())
        tk.Entry(filter_frame, textvariable=self.inspection_search_var,
                 font=FONT_INPUT, width=25, relief="solid", bd=1).pack(side="right", padx=5)

        # Treeview
        tree_frame = tk.Frame(self.inspections_tab, bg=WHITE)
        tree_frame.pack(fill="both", expand=True, pady=5)

        cols = ("id", "template", "equipment", "inspector", "started", "completed", "status", "result")
        self.inspections_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12)

        self.inspections_tree.heading("id",        text="شناسه")
        self.inspections_tree.heading("template",  text="قالب")
        self.inspections_tree.heading("equipment", text="تجهیز")
        self.inspections_tree.heading("inspector", text="بازرس")
        self.inspections_tree.heading("started",   text="شروع")
        self.inspections_tree.heading("completed", text="اتمام")
        self.inspections_tree.heading("status",    text="وضعیت")
        self.inspections_tree.heading("result",    text="نتیجه")

        self.inspections_tree.column("id",        width=60,  anchor="center")
        self.inspections_tree.column("template",  width=180, anchor="w")
        self.inspections_tree.column("equipment", width=140, anchor="w")
        self.inspections_tree.column("inspector", width=120, anchor="w")
        self.inspections_tree.column("started",   width=130, anchor="center")
        self.inspections_tree.column("completed", width=130, anchor="center")
        self.inspections_tree.column("status",    width=100, anchor="center")
        self.inspections_tree.column("result",    width=90,  anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.inspections_tree.yview)
        self.inspections_tree.configure(yscrollcommand=vsb.set)

        self.inspections_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.inspections_tree.bind("<Double-1>", lambda e: self._view_inspection())

    def _load_inspections(self):
        self.inspections_tree.delete(*self.inspections_tree.get_children())
        inspections = self.repo.get_all_inspections()

        for ins in inspections:
            status = STATUS_FA.get(ins["status"], ins["status"])
            result = RESULT_FA.get(ins["overall_result"], "—") if ins["overall_result"] else "—"

            self.inspections_tree.insert("", "end", values=(
                ins["id"],
                ins["template_name"],
                ins["equipment_name"],
                ins["inspector_name"],
                ins["started_at"],
                ins["completed_at"] or "—",
                status,
                result,
            ))

    def _filter_inspections(self):
        search = self.inspection_search_var.get().strip().lower()
        status_filter = self.status_filter_var.get()

        status_map = {
            "در حال انجام": "in_progress",
            "تکمیل شده": "completed",
            "لغو شده": "cancelled",
        }

        for item in self.inspections_tree.get_children():
            values = self.inspections_tree.item(item)["values"]
            template = str(values[1]).lower()
            equipment = str(values[2]).lower()
            status = str(values[6])

            match_search = search in template or search in equipment
            match_status = (status_filter == "همه" or
                           status == STATUS_FA.get(status_map.get(status_filter, ""), ""))

            if match_search and match_status:
                self.inspections_tree.reattach(item, "", "end")
            else:
                self.inspections_tree.detach(item)

    def _start_inspection(self):
        dlg = InspectionStartDialog(self, self.db, self.service, self.current_user)
        self.wait_window(dlg)
        if dlg.result:
            self._load_inspections()
            self._load_stats()

    def _continue_inspection(self):
        sel = self.inspections_tree.selection()
        if not sel:
            messagebox.showwarning("انتخاب", "لطفاً یک بازرسی انتخاب کنید.", parent=self)
            return

        values = self.inspections_tree.item(sel[0])["values"]
        inspection_id = int(values[0])
        status = values[6]

        if "تکمیل" in status or "لغو" in status:
            messagebox.showwarning("هشدار", "این بازرسی قابل ادامه نیست.", parent=self)
            return

        dlg = InspectionExecuteDialog(self, self.db, self.service, inspection_id)
        self.wait_window(dlg)
        if dlg.result:
            self._load_inspections()
            self._load_stats()

    def _view_inspection(self):
        sel = self.inspections_tree.selection()
        if not sel:
            messagebox.showwarning("انتخاب", "لطفاً یک بازرسی انتخاب کنید.", parent=self)
            return

        inspection_id = int(self.inspections_tree.item(sel[0])["values"][0])
        InspectionDetailDialog(self, self.db, self.service, inspection_id)

    # ═══════════════════════════ DATA LOADING ═══════════════════════════

    def _load_data(self):
        self._load_templates()
        self._load_inspections()
        self._load_stats()

    def _load_stats(self):
        stats = self.repo.get_inspection_stats()
        for key, lbl in self.stat_labels.items():
            lbl.config(text=str(stats.get(key, 0)))

    def destroy(self):
        self.db.close()
        super().destroy()
