# views/inspection_view.py
from typing import Optional, List
import tkinter as tk
from views.ui_kit import rtl_columns  # RTL (right-to-left) table columns
from tkinter import ttk, messagebox

from services.inspection_service import InspectionService
from views.inspection_dialog import (
    TemplateDialog,
    InspectionStartDialog,
    InspectionExecuteDialog,
    InspectionDetailDialog,
)
from database.models import Inspection, InspectionTemplate
from auth.auth_manager import AuthManager
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)
# Import Jalali date helper
from utils.date_helpers import to_jalali_datetime_str

BG = GRAY_BG
CARD_BG = WHITE
PRIMARY = NAVY
DANGER = RED
SUCCESS = SUCCESS
WARNING = WARNING
TEXT = TEXT_DARK
SUBTLE = TEXT_LIGHT
BORDER = GRAY_BORDER

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
    def __init__(self, parent, service: InspectionService, current_user: dict):
        super().__init__(parent, bg=BG)
        self.service = service
        self.current_user = current_user
        self.is_manager = current_user["role"] in ["admin", "manager"]
        self.can_write = AuthManager.can_access("inspection", "write")
        self.can_delete = AuthManager.can_access("inspection", "delete")
        self._tab = "inspections"

        self._all_inspections: List[Inspection] = []
        self._all_templates: List[InspectionTemplate] = []

        self._build_ui()
        self._load()

    def _build_ui(self):
        self._build_header()
        self._build_stats_bar()
        self._build_tab_bar()
        self._build_inspections_tab()
        self._build_templates_tab()
        self._show_tab("inspections")

    def _build_header(self):
        hdr = tk.Frame(self, bg=PRIMARY, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🔍  مدیریت بازرسی‌ها", font=FONT_TITLE, bg=PRIMARY, fg=WHITE).pack(side="right", padx=20, pady=14)
        btn_frame = tk.Frame(hdr, bg=PRIMARY)
        btn_frame.pack(side="left", padx=16)
        tk.Button(btn_frame, text="➕ بازرسی جدید", font=FONT_NORMAL, bg=WHITE, fg=PRIMARY,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._start_inspection).pack(side="left", padx=4)
        tk.Button(btn_frame, text="🔄 بروزرسانی", font=FONT_NORMAL, bg=NAVY_LIGHT, fg=WHITE,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._load).pack(side="left", padx=4)
        tk.Button(btn_frame, text="📤  Excel خروجی  ", font=FONT_NORMAL, bg=SUCCESS, fg=WHITE,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._export).pack(side="left", padx=4)

    def _build_stats_bar(self):
        self._stats_frame = tk.Frame(self, bg=BG)
        self._stats_frame.pack(fill="x", padx=20, pady=(12, 0))

    def _refresh_stats(self, stats: dict):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        cards = [
            ("📋", "کل بازرسی‌ها", stats["total"], CARD_BG, PRIMARY),
            ("🔄", "در حال انجام", stats["in_progress"], "#FFF8E1", WARNING),
            ("✅", "قبول شده", stats["passed"], "#E6F4EA", SUCCESS),
            ("❌", "رد شده", stats["failed"], "#FCE8E6", DANGER),
            ("📊", "نرخ قبولی", f"{stats['pass_rate']:.1f}%", CARD_BG, PRIMARY),
        ]
        for icon, label, value, bg_color, fg_color in cards:
            shadow = tk.Frame(self._stats_frame, bg=BORDER)
            shadow.pack(side="right", padx=5)
            card = tk.Frame(shadow, bg=bg_color)
            card.pack(fill="both", expand=True, padx=1, pady=1)
            tk.Label(card, text=f"{icon}  {label}", font=FONT_SMALL, bg=bg_color, fg=SUBTLE).pack(padx=16, pady=(8,0))
            tk.Label(card, text=str(value), font=FONT_HEADING, bg=bg_color, fg=fg_color).pack(padx=16, pady=(0,8))

    def _build_tab_bar(self):
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=20, pady=(10, 0))
        self._tab_btns = {}
        for key, label in [("inspections", "📋 بازرسی‌ها"), ("templates", "📄 قالب‌ها")]:
            btn = tk.Button(bar, text=label, font=FONT_NORMAL, relief="flat", cursor="hand2",
                            padx=18, pady=7, command=lambda k=key: self._show_tab(k))
            btn.pack(side="right", padx=2)
            self._tab_btns[key] = btn

    def _show_tab(self, tab):
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

    def _build_inspections_tab(self):
        self._inspections_frame = tk.Frame(self, bg=BG)

        toolbar = tk.Frame(self._inspections_frame, bg=BG)
        toolbar.pack(fill="x", pady=(0, 6))
        tk.Label(toolbar, text="فیلتر وضعیت:", font=FONT_NORMAL, bg=BG, fg=TEXT).pack(side="right", padx=(0, 5))
        self._status_filter = tk.StringVar(value="همه")
        status_combo = ttk.Combobox(
            toolbar, textvariable=self._status_filter,
            values=["همه", "در حال انجام", "تکمیل شده", "لغو شده"],
            state="readonly", width=14, font=FONT_NORMAL,
        )
        status_combo.pack(side="right", padx=5)
        status_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        container = tk.Frame(self._inspections_frame, bg=BORDER, highlightthickness=1)
        container.pack(fill="both", expand=True)

        cols = ("id", "template", "equipment", "inspector",
                "status", "result", "started", "completed")
        self._ins_tree = ttk.Treeview(container, columns=cols, show="headings", height=16)
        rtl_columns(self._ins_tree)  # RTL column order

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

        vsb = ttk.Scrollbar(container, orient="vertical", command=self._ins_tree.yview)
        self._ins_tree.configure(yscrollcommand=vsb.set)
        self._ins_tree.pack(side="right", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        self._ins_tree.configure(selectmode='extended')
        self._ins_tree.bind("<Delete>", lambda e: self._delete_inspections())
        self._ins_tree.bind("<F2>",     lambda e: self._view_or_edit())

        style = ttk.Style()
        style.configure("Treeview", background=CARD_BG, fieldbackground=CARD_BG, foreground=TEXT, rowheight=26)
        style.configure("Treeview.Heading", background=PRIMARY, foreground=WHITE, font=FONT_NORMAL)
        style.map("Treeview", background=[("selected", PRIMARY)], foreground=[("selected", WHITE)])

        self._ins_tree.tag_configure("pass", background="#E6F4EA")
        self._ins_tree.tag_configure("fail", background="#FCE8E6")
        self._ins_tree.tag_configure("partial", background="#FFF8E1")
        self._ins_tree.tag_configure("none", background=CARD_BG)

        self._ins_tree.bind("<Button-3>", self._ins_context_menu)
        self._ins_tree.bind("<Double-1>", lambda e: self._view_inspection())
        self._ins_ctx = tk.Menu(self, tearoff=0, font=FONT_NORMAL)
        self._ins_ctx.add_command(label="▶️  ادامه بازرسی", command=self._continue_inspection)
        self._ins_ctx.add_command(label="🔍  مشاهده جزئیات", command=self._view_inspection)
        self._ins_ctx.add_separator()
        if self.can_delete:
            self._ins_ctx.add_command(label="🗑️  حذف", command=self._delete_inspection)

    def _build_templates_tab(self):
        self._templates_frame = tk.Frame(self, bg=BG)

        tb = tk.Frame(self._templates_frame, bg=BG)
        tb.pack(fill="x", pady=(0, 6))

        if self.can_write:
            tk.Button(tb, text="➕ قالب جدید", font=FONT_NORMAL, bg=PRIMARY, fg=WHITE,
                      relief="flat", cursor="hand2", padx=12, pady=6,
                      command=self._add_template).pack(side="right", padx=4)
            tk.Button(tb, text="✏️ ویرایش", font=FONT_NORMAL, bg=BORDER, fg=TEXT,
                      relief="flat", cursor="hand2", padx=12, pady=6,
                      command=self._edit_template).pack(side="right", padx=4)
            tk.Button(tb, text="🔁 فعال/غیرفعال", font=FONT_NORMAL, bg=BORDER, fg=TEXT,
                      relief="flat", cursor="hand2", padx=12, pady=6,
                      command=self._toggle_template).pack(side="right", padx=4)
        if self.can_delete:
            tk.Button(tb, text="🗑️ حذف", font=FONT_NORMAL, bg=DANGER, fg=WHITE,
                      relief="flat", cursor="hand2", padx=12, pady=6,
                      command=self._delete_template).pack(side="right", padx=4)

        container = tk.Frame(self._templates_frame, bg=BORDER, highlightthickness=1)
        container.pack(fill="both", expand=True)

        cols = ("id", "name", "equipment", "frequency", "duration", "checkpoints", "active")
        self._tpl_tree = ttk.Treeview(container, columns=cols, show="headings", height=16)
        rtl_columns(self._tpl_tree)  # RTL column order

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

        vsb = ttk.Scrollbar(container, orient="vertical", command=self._tpl_tree.yview)
        self._tpl_tree.configure(yscrollcommand=vsb.set)
        self._tpl_tree.pack(side="right", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        self._tpl_tree.tag_configure("active", background="#E6F4EA")
        self._tpl_tree.tag_configure("inactive", background="#F5F5F5", foreground=SUBTLE)

        if self.can_write:
            self._tpl_tree.configure(selectmode='extended')
            self._tpl_tree.bind("<Delete>", lambda e: self._delete_templates())
            self._tpl_tree.bind("<F2>",      lambda e: self._edit_template())
            self._tpl_tree.bind("<Control-n>", lambda e: self._add_template())

        if self.can_write:
            self._tpl_tree.bind("<Double-1>", lambda e: self._edit_template())
        else:
            self._tpl_tree.bind("<Double-1>", lambda e: self._view_template_only())

    # ── Keyboard helpers ──────────────────────
    def _delete_inspections(self):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف بازرسی‌ها نیستید.")
            return
        selected = self._ins_tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً حداقل یک بازرسی انتخاب کنید.")
            return
        if not messagebox.askyesno("حذف", f"آیا از حذف {len(selected)} بازرسی اطمینان دارید؟"):
            return
        for ins_id in selected:
            try:
                self.service.delete_inspection(int(ins_id)) if hasattr(self.service, 'delete_inspection') else None
            except Exception as e:
                messagebox.showerror("خطا", str(e))
        self._load()

    def _view_or_edit(self):
        selected = self._ins_tree.selection()
        if selected:
            ins_id = int(selected[0])
            if ins_id:
                self._view_inspection()

    def _delete_templates(self):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف قالب‌ها نیستید.")
            return
        selected = self._tpl_tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً حداقل یک قالب انتخاب کنید.")
            return
        if not messagebox.askyesno("حذف", f"آیا از حذف {len(selected)} قالب اطمینان دارید؟"):
            return
        for tpl_id in selected:
            try:
                self.service.delete_template(int(tpl_id))
            except Exception as e:
                messagebox.showerror("خطا", str(e))
        self._load()

    # ── Rest of methods unchanged except permission checks ─────────────
    def _view_template_only(self):
        tpl_id = self._selected_template_id()
        if tpl_id:
            template = self.service.get_template(tpl_id)
            if template:
                messagebox.showinfo("قالب", f"نام: {template.name}\nدوره: {FREQ_FA.get(template.frequency, template.frequency)}\nمدت: {template.estimated_duration_minutes} دقیقه\nتعداد چک‌پوینت: {len(template.checkpoints)}")

    def _load(self):
        self._load_inspections()
        self._load_templates()
        stats = self.service.get_stats()
        self._refresh_stats(stats)

    def _load_inspections(self):
        try:
            self._all_inspections = self.service.get_all_inspections()
            self._apply_filter()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در بارگذاری بازرسی‌ها: {str(e)}")
            self._all_inspections = []

    def _load_templates(self):
        try:
            self._all_templates = self.service.get_all_templates()
            self._populate_templates()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در بارگذاری قالب‌ها: {str(e)}")
            self._all_templates = []

    def _apply_filter(self):
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
        self._ins_tree.delete(*self._ins_tree.get_children())
        for ins in inspections:
            status_text = STATUS_FA.get(ins.status, ins.status)
            result_text = RESULT_FA.get(ins.overall_result or "", ins.overall_result or "")
            if not ins.overall_result and ins.status == "completed":
                result_text = "بدون نتیجه"
            tag = RESULT_TAG.get(ins.overall_result or "", "none")
            template_name = ins.template.name if ins.template and hasattr(ins.template, 'name') else "—"
            equipment_name = ins.equipment.name if ins.equipment and hasattr(ins.equipment, 'name') else "—"
            inspector_name = ins.inspector.username if ins.inspector and hasattr(ins.inspector, 'username') else "—"

            # Convert dates to Jalali
            started_at = to_jalali_datetime_str(ins.started_at)
            completed_at = to_jalali_datetime_str(ins.completed_at)

            self._ins_tree.insert("", "end", iid=str(ins.id), tags=(tag,),
                                  values=(
                                      ins.id, template_name, equipment_name,
                                      inspector_name, status_text, result_text,
                                      started_at, completed_at,
                                  ))

    def _populate_templates(self):
        self._tpl_tree.delete(*self._tpl_tree.get_children())
        for t in self._all_templates:
            tag = "active" if t.is_active else "inactive"
            active_text = "✅ فعال" if t.is_active else "❌ غیرفعال"
            equipment_name = t.equipment.name if t.equipment and hasattr(t.equipment, 'name') else "—"
            checkpoint_count = len(t.checkpoints) if hasattr(t, 'checkpoints') and t.checkpoints else 0
            self._tpl_tree.insert("", "end", iid=str(t.id), tags=(tag,),
                                  values=(
                                      t.id, t.name, equipment_name,
                                      FREQ_FA.get(t.frequency, t.frequency or "—"),
                                      t.estimated_duration_minutes or "—",
                                      checkpoint_count, active_text,
                                  ))

    def _export(self):
        try:
            from views.export_dialog import run_inspection_export
            selected_ins_id = self._selected_inspection_id() if self._ins_tree.selection() else None
            selected_template = None
            if self._tpl_tree.selection():
                tpl_id = self._selected_template_id()
                if tpl_id:
                    selected_template = self.service.get_template(tpl_id)
            run_inspection_export(self, self.service, selected_inspection_id=selected_ins_id, selected_template=selected_template)
        except ImportError:
            messagebox.showwarning("اطلاع", "ماژول خروجی در دسترس نیست")
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در خروجی گرفتن: {str(e)}")

    def _selected_inspection_id(self) -> Optional[int]:
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
        try:
            dlg = InspectionStartDialog(self, self.service.db, self.service, self.current_user)
            self.wait_window(dlg)
            if dlg.result:
                self._load()
                dlg2 = InspectionExecuteDialog(self, self.service.db, self.service, dlg.result)
                self.wait_window(dlg2)
                self._load()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در شروع بازرسی: {str(e)}")

    def _continue_inspection(self):
        ins_id = self._selected_inspection_id()
        if not ins_id:
            return
        ins = next((i for i in self._all_inspections if i.id == ins_id), None)
        if not ins:
            messagebox.showerror("خطا", "بازرسی مورد نظر یافت نشد")
            return
        if ins.status != "in_progress":
            messagebox.showinfo("اطلاع", "این بازرسی قابل ادامه نیست.")
            return
        try:
            dlg = InspectionExecuteDialog(self, self.service.db, self.service, ins_id)
            self.wait_window(dlg)
            self._load()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ادامه بازرسی: {str(e)}")

    def _view_inspection(self):
        ins_id = self._selected_inspection_id()
        if not ins_id:
            return
        try:
            dlg = InspectionDetailDialog(self, self.service.db, self.service, ins_id)
            self.wait_window(dlg)
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در نمایش جزئیات: {str(e)}")

    def _delete_inspection(self):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف بازرسی نیستید.")
            return
        ins_id = self._selected_inspection_id()
        if not ins_id:
            return
        if not messagebox.askyesno("حذف", "آیا از حذف این بازرسی مطمئن هستید؟\nتمام نتایج آن نیز حذف خواهند شد."):
            return
        try:
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
        row = self._ins_tree.identify_row(event.y)
        if row:
            self._ins_tree.selection_set(row)
            self._ins_ctx.post(event.x_root, event.y_root)

    def _selected_template_id(self) -> Optional[int]:
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
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به افزودن قالب نیستید.", parent=self)
            return
        try:
            dlg = TemplateDialog(self, self.service.db, self.service)
            self.wait_window(dlg)
            if dlg.result:
                self._load()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در افزودن قالب: {str(e)}")

    def _edit_template(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ویرایش قالب نیستید.", parent=self)
            return
        tpl_id = self._selected_template_id()
        if not tpl_id:
            return
        try:
            dlg = TemplateDialog(self, self.service.db, self.service, template_id=tpl_id)
            self.wait_window(dlg)
            if dlg.result:
                self._load()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ویرایش قالب: {str(e)}")

    def _toggle_template(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به تغییر وضعیت قالب نیستید.", parent=self)
            return
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
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف قالب نیستید.", parent=self)
            return
        tpl_id = self._selected_template_id()
        if not tpl_id:
            return
        template = self.service.get_template(tpl_id)
        if template and hasattr(template, 'inspections') and template.inspections:
            if not messagebox.askyesno("هشدار", "این قالب دارای بازرسی‌های ثبت شده است.\nحذف آن ممکن است باعث مشکلات یکپارچگی داده شود.\nآیا مطمئن هستید؟"):
                return
        if not messagebox.askyesno("حذف", "آیا از حذف این قالب مطمئن هستید؟\nتمام چک‌پوینت‌های آن نیز حذف خواهند شد."):
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
                if self.service.delete_template(tpl_id):
                    messagebox.showinfo("موفق", "قالب با موفقیت حذف شد")
                    self._load()
                else:
                    messagebox.showerror("خطا", "خطا در حذف قالب")
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در حذف قالب: {str(e)}")

    def ux_footer_spec(self):
        """Filters shown as removable chips under the table (views/ux.py)."""
        return {"filters": [("وضعیت", self._status_filter, "همه")],
                "apply": self._apply_filter, "noun": "بازرسی",
                "total": lambda: len(getattr(self, "_all_inspections", None) or []),
                "_tpl_tree": {"noun": "قالب"}}

