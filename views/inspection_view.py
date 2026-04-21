# views/inspection_view.py
"""
Inspection View - Main Inspection Management Panel
Consistent with existing app views (equipment_view, pm_view, work_order_view).
"""
from typing import Optional, List
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from services.inspection_service import InspectionService
from views.inspection_dialog import (
    TemplateDialog,
    InspectionStartDialog,
    InspectionExecuteDialog,
    InspectionDetailDialog,
)
from database.models import Inspection, InspectionTemplate

# ─────────────────────────── Theme ──────────────────────────────────────────
BG = "#F0F4F8"
WHITE = "#FFFFFF"
PRIMARY = "#1A73E8"
DANGER = "#DC3545"
SUCCESS = "#28A745"
WARNING = "#F29900"
TEXT = "#202124"
SUBTLE = "#5F6368"
BORDER = "#DADCE0"
RED_BG = "#FCE8E6"
GREEN_BG = "#E6F4EA"
YELLOW_BG = "#FFF8E1"

FONT_TITLE = ("Tahoma", 14, "bold")
FONT_LABEL = ("Tahoma", 10, "bold")
FONT_INPUT = ("Tahoma", 10)
FONT_SMALL = ("Tahoma", 9)
FONT_STAT = ("Tahoma", 18, "bold")

STATUS_FA = {
    "in_progress": "در حال انجام",
    "completed": "تکمیل شده",
    "cancelled": "لغو شده",
}

STATUS_COLOR = {
    "in_progress": WARNING,
    "completed": SUCCESS,
    "cancelled": SUBTLE,
}

RESULT_FA = {
    "pass": "✅ قبول",
    "fail": "❌ رد",
    "partial": "⚠️ جزئی",
    "": "—",
}

RESULT_TAG = {
    "pass": "pass",
    "fail": "fail",
    "partial": "partial",
    "": "none",
}

FREQ_FA = {
    "daily": "روزانه",
    "weekly": "هفتگی",
    "monthly": "ماهانه",
    "quarterly": "سه‌ماهه",
    "yearly": "سالانه",
}


class InspectionView(tk.Frame):
    """Main inspection management panel embedded in MainView."""

    def __init__(self, parent, service: InspectionService, current_user: dict):
        super().__init__(parent, bg=BG)
        self.service = service
        self.current_user = current_user
        self._tab = "inspections"  # "inspections" | "templates"

        # Data storage
        self._all_inspections: List[Inspection] = []
        self._all_templates: List[InspectionTemplate] = []

        self._build_ui()
        self._load()

    # ══════════════════════════ UI BUILD ════════════════════════════════════

    def _build_ui(self):
        self._build_header()
        self._build_stats_bar()
        self._build_tab_bar()
        self._build_inspections_tab()
        self._build_templates_tab()
        self._show_tab("inspections")

    # ── Header ──────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=PRIMARY, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="🔍  مدیریت بازرسی‌ها",
                 font=FONT_TITLE, bg=PRIMARY, fg=WHITE).pack(
            side="right", padx=20, pady=14)

        btn_frame = tk.Frame(hdr, bg=PRIMARY)
        btn_frame.pack(side="left", padx=16, pady=10)

        tk.Button(btn_frame, text="➕ بازرسی جدید",
                  font=FONT_LABEL, bg=WHITE, fg=PRIMARY,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._start_inspection).pack(side="left", padx=4)

        tk.Button(btn_frame, text="🔄 بروزرسانی",
                  font=FONT_INPUT, bg=PRIMARY, fg=WHITE,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._load).pack(side="left", padx=4)

        tk.Button(btn_frame, text="📤 خروجی Excel / PDF",
                  font=FONT_INPUT, bg="#34A853", fg=WHITE,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._export).pack(side="left", padx=4)

    # ── Stats bar ───────────────────────────────────────────────────────────

    def _build_stats_bar(self):
        self._stats_frame = tk.Frame(self, bg=BG)
        self._stats_frame.pack(fill="x", padx=20, pady=(12, 0))

    def _refresh_stats(self, stats: dict):
        for w in self._stats_frame.winfo_children():
            w.destroy()

        cards = [
            ("📋", "کل بازرسی‌ها", stats["total"], WHITE, PRIMARY),
            ("🔄", "در حال انجام", stats["in_progress"], YELLOW_BG, WARNING),
            ("✅", "قبول شده", stats["passed"], GREEN_BG, SUCCESS),
            ("❌", "رد شده", stats["failed"], RED_BG, DANGER),
            ("📊", "نرخ قبولی", f"{stats['pass_rate']:.1f}%", WHITE, PRIMARY),
        ]
        for icon, label, value, bg, fg in cards:
            card = tk.Frame(self._stats_frame, bg=bg,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(side="right", padx=5, ipadx=16, ipady=8)
            tk.Label(card, text=f"{icon}  {label}",
                     font=FONT_SMALL, bg=bg, fg=SUBTLE).pack()
            tk.Label(card, text=str(value),
                     font=FONT_STAT, bg=bg, fg=fg).pack()

    # ── Tab bar ─────────────────────────────────────────────────────────────

    def _build_tab_bar(self):
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=20, pady=(10, 0))

        self._tab_btns = {}
        for key, label in [("inspections", "📋 بازرسی‌ها"), ("templates", "📄 قالب‌ها")]:
            btn = tk.Button(bar, text=label, font=FONT_LABEL,
                            relief="flat", cursor="hand2",
                            padx=18, pady=7,
                            command=lambda k=key: self._show_tab(k))
            btn.pack(side="right", padx=2)
            self._tab_btns[key] = btn

    def _show_tab(self, tab: str):
        self._tab = tab
        for key, btn in self._tab_btns.items():
            if key == tab:
                btn.config(bg=PRIMARY, fg=WHITE)
            else:
                btn.config(bg=BORDER, fg=TEXT)

        if tab == "inspections":
            self._inspections_frame.pack(fill="both", expand=True, padx=20, pady=8)
            self._templates_frame.pack_forget()
            self._load_inspections()
        else:
            self._templates_frame.pack(fill="both", expand=True, padx=20, pady=8)
            self._inspections_frame.pack_forget()
            self._load_templates()

    # ── Inspections tab ─────────────────────────────────────────────────────

    def _build_inspections_tab(self):
        self._inspections_frame = tk.Frame(self, bg=BG)

        # Filter toolbar
        toolbar = tk.Frame(self._inspections_frame, bg=BG)
        toolbar.pack(fill="x", pady=(0, 6))

        tk.Label(toolbar, text="فیلتر وضعیت:", font=FONT_INPUT,
                 bg=BG, fg=TEXT).pack(side="right", padx=(0, 5))
        self._status_filter = tk.StringVar(value="همه")
        status_combo = ttk.Combobox(
            toolbar, textvariable=self._status_filter,
            values=["همه", "در حال انجام", "تکمیل شده", "لغو شده"],
            state="readonly", width=14, font=FONT_INPUT,
        )
        status_combo.pack(side="right", padx=5)
        status_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        # Table
        container = tk.Frame(self._inspections_frame, bg=WHITE,
                             highlightbackground=BORDER, highlightthickness=1)
        container.pack(fill="both", expand=True)

        cols = ("id", "template", "equipment", "inspector",
                "status", "result", "started", "completed")
        self._ins_tree = ttk.Treeview(container, columns=cols,
                                      show="headings", height=16)

        headers = [
            ("id", "شناسه", 60, "center"),
            ("template", "قالب", 180, "w"),
            ("equipment", "تجهیز", 140, "w"),
            ("inspector", "بازرس", 120, "center"),
            ("status", "وضعیت", 110, "center"),
            ("result", "نتیجه", 100, "center"),
            ("started", "شروع", 130, "center"),
            ("completed", "پایان", 130, "center"),
        ]
        for col, text, width, anchor in headers:
            self._ins_tree.heading(col, text=text)
            self._ins_tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(container, orient="vertical",
                            command=self._ins_tree.yview)
        self._ins_tree.configure(yscrollcommand=vsb.set)
        self._ins_tree.pack(side="right", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # Tags
        self._ins_tree.tag_configure("pass", background=GREEN_BG)
        self._ins_tree.tag_configure("fail", background=RED_BG)
        self._ins_tree.tag_configure("partial", background=YELLOW_BG)
        self._ins_tree.tag_configure("none", background=WHITE)

        # Context menu
        self._ins_tree.bind("<Button-3>", self._ins_context_menu)
        self._ins_tree.bind("<Double-1>", lambda e: self._view_inspection())
        self._ins_ctx = tk.Menu(self, tearoff=0, font=FONT_INPUT)
        self._ins_ctx.add_command(label="▶️  ادامه بازرسی", command=self._continue_inspection)
        self._ins_ctx.add_command(label="🔍  مشاهده جزئیات", command=self._view_inspection)
        self._ins_ctx.add_separator()
        self._ins_ctx.add_command(label="🗑️  حذف", command=self._delete_inspection)

    # ── Templates tab ───────────────────────────────────────────────────────

    def _build_templates_tab(self):
        self._templates_frame = tk.Frame(self, bg=BG)

        # Toolbar
        tb = tk.Frame(self._templates_frame, bg=BG)
        tb.pack(fill="x", pady=(0, 6))
        tk.Button(tb, text="➕ قالب جدید", font=FONT_LABEL,
                  bg=PRIMARY, fg=WHITE, relief="flat", cursor="hand2",
                  padx=12, pady=6, command=self._add_template).pack(side="right", padx=4)
        tk.Button(tb, text="✏️ ویرایش", font=FONT_INPUT,
                  bg=BORDER, fg=TEXT, relief="flat", cursor="hand2",
                  padx=12, pady=6, command=self._edit_template).pack(side="right", padx=4)
        tk.Button(tb, text="🔁 فعال/غیرفعال", font=FONT_INPUT,
                  bg=BORDER, fg=TEXT, relief="flat", cursor="hand2",
                  padx=12, pady=6, command=self._toggle_template).pack(side="right", padx=4)
        tk.Button(tb, text="🗑️ حذف", font=FONT_INPUT,
                  bg=DANGER, fg=WHITE, relief="flat", cursor="hand2",
                  padx=12, pady=6, command=self._delete_template).pack(side="right", padx=4)

        # Table
        container = tk.Frame(self._templates_frame, bg=WHITE,
                             highlightbackground=BORDER, highlightthickness=1)
        container.pack(fill="both", expand=True)

        cols = ("id", "name", "equipment", "frequency", "duration", "checkpoints", "active")
        self._tpl_tree = ttk.Treeview(container, columns=cols,
                                      show="headings", height=16)

        headers = [
            ("id", "شناسه", 60, "center"),
            ("name", "نام قالب", 220, "w"),
            ("equipment", "تجهیز", 150, "w"),
            ("frequency", "دوره", 90, "center"),
            ("duration", "مدت (دقیقه)", 100, "center"),
            ("checkpoints", "تعداد چک‌پوینت", 120, "center"),
            ("active", "وضعیت", 80, "center"),
        ]
        for col, text, width, anchor in headers:
            self._tpl_tree.heading(col, text=text)
            self._tpl_tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(container, orient="vertical",
                            command=self._tpl_tree.yview)
        self._tpl_tree.configure(yscrollcommand=vsb.set)
        self._tpl_tree.pack(side="right", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        self._tpl_tree.tag_configure("active", background=GREEN_BG)
        self._tpl_tree.tag_configure("inactive", background="#F5F5F5", foreground=SUBTLE)
        self._tpl_tree.bind("<Double-1>", lambda e: self._edit_template())

    # ══════════════════════════ DATA LOADING ════════════════════════════════

    def _load(self):
        """Load all data and refresh UI"""
        self._load_inspections()
        self._load_templates()
        stats = self.service.get_stats()
        self._refresh_stats(stats)

    def _load_inspections(self):
        """Load inspections from database"""
        try:
            self._all_inspections = self.service.get_all_inspections()
            self._apply_filter()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در بارگذاری بازرسی‌ها: {str(e)}")
            self._all_inspections = []

    def _load_templates(self):
        """Load templates from database"""
        try:
            self._all_templates = self.service.get_all_templates()
            self._populate_templates()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در بارگذاری قالب‌ها: {str(e)}")
            self._all_templates = []

    def _apply_filter(self):
        """Apply status filter to inspections"""
        status_fa = self._status_filter.get()
        status_map = {
            "در حال انجام": "in_progress",
            "تکمیل شده": "completed",
            "لغو شده": "cancelled",
        }
        status_en = status_map.get(status_fa)

        filtered = [
            ins for ins in self._all_inspections
            if status_en is None or ins.status == status_en
        ]
        self._populate_inspections(filtered)

    def _populate_inspections(self, inspections: List[Inspection]):
        """Populate inspections treeview with model objects"""
        self._ins_tree.delete(*self._ins_tree.get_children())

        for ins in inspections:
            # Access attributes with dot notation
            status_text = STATUS_FA.get(ins.status, ins.status)
            result_text = RESULT_FA.get(ins.overall_result or "", ins.overall_result or "")
            tag = RESULT_TAG.get(ins.overall_result or "", "none")

            # Get related names (handle potential None relationships)
            template_name = ins.template.name if ins.template and hasattr(ins.template, 'name') else "—"
            equipment_name = ins.equipment.name if ins.equipment and hasattr(ins.equipment, 'name') else "—"
            inspector_name = ins.inspector.username if ins.inspector and hasattr(ins.inspector, 'username') else "—"

            # Format dates
            started_at = ins.started_at.strftime("%Y-%m-%d %H:%M") if ins.started_at else "—"
            completed_at = ins.completed_at.strftime("%Y-%m-%d %H:%M") if ins.completed_at else "—"

            self._ins_tree.insert("", "end", iid=str(ins.id), tags=(tag,),
                                  values=(
                                      ins.id,
                                      template_name,
                                      equipment_name,
                                      inspector_name,
                                      status_text,
                                      result_text,
                                      started_at,
                                      completed_at,
                                  ))

    def _populate_templates(self):
        """Populate templates treeview with model objects"""
        self._tpl_tree.delete(*self._tpl_tree.get_children())

        for t in self._all_templates:
            tag = "active" if t.is_active else "inactive"
            active_text = "✅ فعال" if t.is_active else "❌ غیرفعال"

            # Access equipment name through relationship
            equipment_name = t.equipment.name if t.equipment and hasattr(t.equipment, 'name') else "—"

            # Get checkpoint count
            checkpoint_count = len(t.checkpoints) if hasattr(t, 'checkpoints') and t.checkpoints else 0

            self._tpl_tree.insert("", "end", iid=str(t.id), tags=(tag,),
                                  values=(
                                      t.id,
                                      t.name,
                                      equipment_name,
                                      FREQ_FA.get(t.frequency, t.frequency or "—"),
                                      t.estimated_duration_minutes or "—",
                                      checkpoint_count,
                                      active_text,
                                  ))

    # ══════════════════════════ ACTIONS — INSPECTIONS ═══════════════════════

    def _export(self):
        """Export inspections to Excel/PDF"""
        try:
            from views.export_dialog import run_inspection_export
            selected_ins_id = self._selected_inspection_id() if self._ins_tree.selection() else None
            selected_template = None
            if self._tpl_tree.selection():
                tpl_id = self._selected_template_id()
                if tpl_id:
                    selected_template = self.service.get_template(tpl_id)
            run_inspection_export(
                self,
                self.service,
                selected_inspection_id=selected_ins_id,
                selected_template=selected_template,
            )
        except ImportError:
            messagebox.showwarning("اطلاع", "ماژول خروجی در دسترس نیست")
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در خروجی گرفتن: {str(e)}")

    def _selected_inspection_id(self) -> Optional[int]:
        """Get selected inspection ID from treeview"""
        sel = self._ins_tree.selection()
        if not sel:
            messagebox.showwarning("انتخاب", "لطفاً یک بازرسی انتخاب کنید.")
            return None
        try:
            return int(sel[0])
        except ValueError:
            messagebox.showerror("خطا", "شناسه بازرسی نامعتبر است")
            return None

    def _start_inspection(self):
        """Start a new inspection"""
        try:
            dlg = InspectionStartDialog(self, self.service, self.current_user)
            self.wait_window(dlg)
            if dlg.result:
                self._load()
                # Automatically open execute dialog for the new inspection
                dlg2 = InspectionExecuteDialog(self, self.service, dlg.result)
                self.wait_window(dlg2)
                self._load()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در شروع بازرسی: {str(e)}")

    def _continue_inspection(self):
        """Continue an in-progress inspection"""
        ins_id = self._selected_inspection_id()
        if not ins_id:
            return

        # Find the inspection in our loaded data
        ins = next((i for i in self._all_inspections if i.id == ins_id), None)
        if not ins:
            messagebox.showerror("خطا", "بازرسی مورد نظر یافت نشد")
            return

        if ins.status != "in_progress":
            messagebox.showinfo("اطلاع", "این بازرسی قابل ادامه نیست.")
            return

        try:
            dlg = InspectionExecuteDialog(self, self.service, ins_id)
            self.wait_window(dlg)
            self._load()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ادامه بازرسی: {str(e)}")

    def _view_inspection(self):
        """View inspection details"""
        ins_id = self._selected_inspection_id()
        if not ins_id:
            return

        try:
            dlg = InspectionDetailDialog(self, self.service, ins_id)
            self.wait_window(dlg)
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در نمایش جزئیات: {str(e)}")

    def _delete_inspection(self):
        """Delete an inspection"""
        ins_id = self._selected_inspection_id()
        if not ins_id:
            return

        if not messagebox.askyesno("حذف",
                                   "آیا از حذف این بازرسی مطمئن هستید؟\n"
                                   "تمام نتایج آن نیز حذف خواهند شد."):
            return

        try:
            # Note: You need to implement delete_inspection in your service
            # For now, assuming it exists
            if hasattr(self.service, 'delete_inspection'):
                ok, msg = self.service.delete_inspection(ins_id)
                if ok:
                    messagebox.showinfo("موفق", msg)
                    self._load()
                else:
                    messagebox.showerror("خطا", msg)
            else:
                messagebox.showwarning("اطلاع", "حذف بازرسی در این نسخه پشتیبانی نمی‌شود")
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در حذف بازرسی: {str(e)}")

    def _ins_context_menu(self, event):
        """Show context menu for inspections"""
        row = self._ins_tree.identify_row(event.y)
        if row:
            self._ins_tree.selection_set(row)
            self._ins_ctx.post(event.x_root, event.y_root)

    # ══════════════════════════ ACTIONS — TEMPLATES ══════════════════════════

    def _selected_template_id(self) -> Optional[int]:
        """Get selected template ID from treeview"""
        sel = self._tpl_tree.selection()
        if not sel:
            messagebox.showwarning("انتخاب", "لطفاً یک قالب انتخاب کنید.")
            return None
        try:
            return int(sel[0])
        except ValueError:
            messagebox.showerror("خطا", "شناسه قالب نامعتبر است")
            return None

    def _add_template(self):
        """Add a new template"""
        try:
            dlg = TemplateDialog(self, self.service)
            self.wait_window(dlg)
            if dlg.result:
                self._load()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در افزودن قالب: {str(e)}")

    def _edit_template(self):
        """Edit an existing template"""
        tpl_id = self._selected_template_id()
        if not tpl_id:
            return

        try:
            dlg = TemplateDialog(self, self.service, template_id=tpl_id)
            self.wait_window(dlg)
            if dlg.result:
                self._load()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ویرایش قالب: {str(e)}")

    def _toggle_template(self):
        """Toggle template active status"""
        tpl_id = self._selected_template_id()
        if not tpl_id:
            return

        try:
            if hasattr(self.service, 'toggle_template_active'):
                ok, msg = self.service.toggle_template_active(tpl_id)
                if ok:
                    self._load()
                else:
                    messagebox.showerror("خطا", msg)
            else:
                # Fallback: update template directly
                template = self.service.get_template(tpl_id)
                if template:
                    from schemas.inspection import InspectionTemplateUpdate
                    update_data = InspectionTemplateUpdate(is_active=not template.is_active)
                    self.service.update_template(tpl_id, update_data)
                    self._load()
                    messagebox.showinfo("موفق", "وضعیت قالب با موفقیت تغییر کرد")
                else:
                    messagebox.showerror("خطا", "قالب مورد نظر یافت نشد")
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در تغییر وضعیت قالب: {str(e)}")

    def _delete_template(self):
        """Delete a template"""
        tpl_id = self._selected_template_id()
        if not tpl_id:
            return

        # Check if template has associated inspections
        template = self.service.get_template(tpl_id)
        if template and hasattr(template, 'inspections') and template.inspections:
            if not messagebox.askyesno("هشدار",
                                       "این قالب دارای بازرسی‌های ثبت شده است.\n"
                                       "حذف آن ممکن است باعث مشکلات یکپارچگی داده شود.\n"
                                       "آیا مطمئن هستید؟"):
                return

        if not messagebox.askyesno("حذف",
                                   "آیا از حذف این قالب مطمئن هستید؟\n"
                                   "تمام چک‌پوینت‌های آن نیز حذف خواهند شد."):
            return

        try:
            if hasattr(self.service, 'delete_template'):
                ok, msg = self.service.delete_template(tpl_id)
                if ok:
                    messagebox.showinfo("موفق", msg)
                    self._load()
                else:
                    messagebox.showerror("خطا", msg)
            else:
                # Fallback: delete using existing method
                if self.service.delete_template(tpl_id):
                    messagebox.showinfo("موفق", "قالب با موفقیت حذف شد")
                    self._load()
                else:
                    messagebox.showerror("خطا", "خطا در حذف قالب")
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در حذف قالب: {str(e)}")