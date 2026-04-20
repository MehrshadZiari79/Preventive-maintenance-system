# views/inspection_dialogs.py
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, List
from datetime import datetime

from database.models import Equipment
from services.inspection_service import InspectionService
from schemas.inspection import (
    InspectionTemplateCreate,
    InspectionCheckpointCreate,
    InspectionCreate,
    InspectionResultCreate,
)

# ─────────────────────────── Theme (matches existing app) ───────────────────
BG      = "#F0F4F8"
WHITE   = "#FFFFFF"
PRIMARY = "#1A73E8"
DANGER  = "#DC3545"
SUCCESS = "#28A745"
TEXT    = "#202124"
SUBTLE  = "#5F6368"
BORDER  = "#DADCE0"
RED_BG  = "#FCE8E6"
GREEN_BG = "#E6F4EA"

FONT_TITLE  = ("Tahoma", 13, "bold")
FONT_LABEL  = ("Tahoma", 10, "bold")
FONT_INPUT  = ("Tahoma", 10)
FONT_SMALL  = ("Tahoma", 9)

FREQ_OPTIONS = {
    "روزانه":    "daily",
    "هفتگی":    "weekly",
    "ماهانه":   "monthly",
    "سه‌ماهه":  "quarterly",
    "سالانه":   "yearly",
}
FREQ_FA = {v: k for k, v in FREQ_OPTIONS.items()}

TYPE_OPTIONS = {
    "بصری":        "visual",
    "اندازه‌گیری": "measurement",
    "عملکردی":     "functional",
    "ایمنی":       "safety",
}
TYPE_FA = {v: k for k, v in TYPE_OPTIONS.items()}

RESULT_FA = {
    "pass":    "✅ قبول",
    "fail":    "❌ رد",
    "partial": "⚠️ جزئی",
    "na":      "— N/A",
}


# ══════════════════════════════════════════════════════════════════════════════
#  TemplateDialog — Create / Edit inspection template
# ══════════════════════════════════════════════════════════════════════════════

class TemplateDialog(tk.Toplevel):
    """Dialog for creating/editing inspection templates."""

    def __init__(self, parent, db_session, service: InspectionService,
                 template_id: Optional[int] = None):
        super().__init__(parent)
        self.db          = db_session
        self.service     = service
        self.template_id = template_id
        self.checkpoints: list = []
        self.result      = False

        self.title("ویرایش قالب بازرسی" if template_id else "قالب بازرسی جدید")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._center(820, 640)
        self.grab_set()

        self._build_ui()
        if template_id:
            self._load_template()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=PRIMARY, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        title = "✏️  ویرایش قالب بازرسی" if self.template_id else "➕  قالب بازرسی جدید"
        tk.Label(hdr, text=title, font=FONT_TITLE,
                 bg=PRIMARY, fg=WHITE).pack(side="right", padx=20, pady=14)

        # Info section
        info_frame = tk.LabelFrame(self, text="اطلاعات قالب", font=FONT_LABEL,
                                   bg=BG, fg=TEXT, padx=15, pady=10)
        info_frame.pack(fill="x", padx=20, pady=(15, 5))

        # Name
        tk.Label(info_frame, text="نام قالب *:", font=FONT_LABEL,
                 bg=BG, fg=TEXT).grid(row=0, column=2, sticky="e", pady=6, padx=5)
        self.name_var = tk.StringVar()
        tk.Entry(info_frame, textvariable=self.name_var, font=FONT_INPUT,
                 width=35, relief="solid", bd=1).grid(row=0, column=1, sticky="ew", pady=6, padx=5)

        # Equipment
        tk.Label(info_frame, text="تجهیز:", font=FONT_LABEL,
                 bg=BG, fg=TEXT).grid(row=1, column=2, sticky="e", pady=6, padx=5)
        equipment_list = self.db.query(Equipment).filter(Equipment.status != "inactive").all()
        self._equipment_list = equipment_list
        eq_names = ["عمومی"] + [eq.name for eq in equipment_list]
        self.eq_var = tk.StringVar(value="عمومی")
        ttk.Combobox(info_frame, textvariable=self.eq_var, values=eq_names,
                     state="readonly", width=33, font=FONT_INPUT).grid(
            row=1, column=1, sticky="ew", pady=6, padx=5)

        # Frequency
        tk.Label(info_frame, text="دوره تناوب *:", font=FONT_LABEL,
                 bg=BG, fg=TEXT).grid(row=2, column=2, sticky="e", pady=6, padx=5)
        self.freq_var = tk.StringVar(value="ماهانه")
        ttk.Combobox(info_frame, textvariable=self.freq_var,
                     values=list(FREQ_OPTIONS.keys()),
                     state="readonly", width=33, font=FONT_INPUT).grid(
            row=2, column=1, sticky="ew", pady=6, padx=5)

        # Duration
        tk.Label(info_frame, text="مدت تخمینی (دقیقه):", font=FONT_LABEL,
                 bg=BG, fg=TEXT).grid(row=3, column=2, sticky="e", pady=6, padx=5)
        self.duration_var = tk.StringVar(value="30")
        tk.Entry(info_frame, textvariable=self.duration_var, font=FONT_INPUT,
                 width=10, relief="solid", bd=1).grid(row=3, column=1, sticky="w", pady=6, padx=5)

        # Active checkbox
        self.active_var = tk.BooleanVar(value=True)
        tk.Checkbutton(info_frame, text="فعال", variable=self.active_var,
                       bg=BG, font=FONT_INPUT).grid(row=4, column=1, sticky="w", pady=6, padx=5)

        # Description
        tk.Label(info_frame, text="توضیحات:", font=FONT_LABEL,
                 bg=BG, fg=TEXT).grid(row=5, column=2, sticky="ne", pady=6, padx=5)
        self.desc_text = tk.Text(info_frame, font=FONT_INPUT, width=35, height=3,
                                 relief="solid", bd=1)
        self.desc_text.grid(row=5, column=1, sticky="ew", pady=6, padx=5)

        # Checkpoints section
        cp_frame = tk.LabelFrame(self, text="چک‌پوینت‌ها", font=FONT_LABEL,
                                 bg=BG, fg=TEXT, padx=10, pady=8)
        cp_frame.pack(fill="both", expand=True, padx=20, pady=5)

        cp_toolbar = tk.Frame(cp_frame, bg=BG)
        cp_toolbar.pack(fill="x", pady=(0, 5))

        tk.Button(cp_toolbar, text="➕ افزودن چک‌پوینت", font=FONT_SMALL,
                  bg=PRIMARY, fg=WHITE, relief="flat", cursor="hand2",
                  padx=10, pady=5, command=self._add_checkpoint).pack(side="right")
        tk.Button(cp_toolbar, text="🗑️ حذف", font=FONT_SMALL,
                  bg=DANGER, fg=WHITE, relief="flat", cursor="hand2",
                  padx=10, pady=5, command=self._delete_checkpoint).pack(side="right", padx=(0, 5))

        cols = ("order", "title", "type", "description")
        self.cp_tree = ttk.Treeview(cp_frame, columns=cols, show="headings", height=7)
        self.cp_tree.heading("order",       text="ترتیب")
        self.cp_tree.heading("title",       text="عنوان")
        self.cp_tree.heading("type",        text="نوع")
        self.cp_tree.heading("description", text="توضیحات")
        self.cp_tree.column("order",       width=55,  anchor="center")
        self.cp_tree.column("title",       width=200, anchor="w")
        self.cp_tree.column("type",        width=110, anchor="center")
        self.cp_tree.column("description", width=310, anchor="w")

        vsb = ttk.Scrollbar(cp_frame, orient="vertical", command=self.cp_tree.yview)
        self.cp_tree.configure(yscrollcommand=vsb.set)
        self.cp_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.cp_tree.bind("<Double-1>", self._edit_checkpoint)

        # Buttons
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=(5, 15))
        tk.Button(btn_frame, text="ذخیره", font=FONT_LABEL,
                  bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                  padx=20, pady=8, command=self._save).pack(side="right", padx=(5, 0))
        tk.Button(btn_frame, text="انصراف", font=FONT_INPUT,
                  bg=BORDER, fg=TEXT, relief="flat", cursor="hand2",
                  padx=20, pady=8, command=self.destroy).pack(side="right")

    # ── Data ────────────────────────────────────────────────────────────────

    def _load_template(self):
        template = self.service.get_template(self.template_id)
        if not template:
            messagebox.showerror("خطا", "قالب یافت نشد", parent=self)
            self.destroy()
            return

        self.name_var.set(template.name)

        if template.equipment:
            self.eq_var.set(template.equipment.name)

        self.freq_var.set(FREQ_FA.get(template.frequency, "ماهانه"))
        self.duration_var.set(str(template.estimated_duration_minutes or 30))

        if template.description:
            self.desc_text.insert("1.0", template.description)

        self.active_var.set(template.is_active)

        self.checkpoints = [
            {
                "id":          cp.id,
                "title":       cp.title,
                "description": cp.description or "",
                "type":        cp.checkpoint_type,
                "order":       cp.order_number,
            }
            for cp in sorted(template.checkpoints, key=lambda x: x.order_number)
        ]
        self._refresh_cp_list()

    def _refresh_cp_list(self):
        self.cp_tree.delete(*self.cp_tree.get_children())
        for idx, cp in enumerate(self.checkpoints, 1):
            cp["order"] = idx
            desc = cp["description"]
            short_desc = desc[:50] + "..." if len(desc) > 50 else desc
            self.cp_tree.insert("", "end", values=(
                idx,
                cp["title"],
                TYPE_FA.get(cp["type"], cp["type"]),
                short_desc,
            ))

    def _add_checkpoint(self):
        dlg = CheckpointDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self.checkpoints.append(dlg.result)
            self._refresh_cp_list()

    def _edit_checkpoint(self, event=None):
        sel = self.cp_tree.selection()
        if not sel:
            return
        order = int(self.cp_tree.item(sel[0])["values"][0])
        cp = next((c for c in self.checkpoints if c["order"] == order), None)
        if not cp:
            return
        dlg = CheckpointDialog(self, cp)
        self.wait_window(dlg)
        if dlg.result:
            idx = self.checkpoints.index(cp)
            self.checkpoints[idx] = dlg.result
            self._refresh_cp_list()

    def _delete_checkpoint(self):
        sel = self.cp_tree.selection()
        if not sel:
            messagebox.showwarning("انتخاب", "لطفاً یک چک‌پوینت انتخاب کنید.", parent=self)
            return
        if not messagebox.askyesno("حذف", "آیا از حذف این چک‌پوینت مطمئن هستید؟", parent=self):
            return
        order = int(self.cp_tree.item(sel[0])["values"][0])
        self.checkpoints = [c for c in self.checkpoints if c["order"] != order]
        self._refresh_cp_list()

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("خطا", "نام قالب الزامی است.", parent=self)
            return
        if not self.checkpoints:
            messagebox.showerror("خطا", "حداقل یک چک‌پوینت الزامی است.", parent=self)
            return

        try:
            duration = int(self.duration_var.get())
        except ValueError:
            messagebox.showerror("خطا", "مدت تخمینی باید عدد باشد.", parent=self)
            return

        # Resolve equipment id
        eq_name = self.eq_var.get()
        equipment_id = None
        if eq_name != "عمومی":
            eq = next((e for e in self._equipment_list if e.name == eq_name), None)
            if eq:
                equipment_id = eq.id

        description = self.desc_text.get("1.0", "end").strip() or None
        frequency   = FREQ_OPTIONS.get(self.freq_var.get(), "monthly")

        checkpoint_schemas = [
            InspectionCheckpointCreate(
                title=cp["title"],
                description=cp["description"] or None,
                checkpoint_type=cp["type"],
                order_number=cp["order"],
            )
            for cp in self.checkpoints
        ]

        template_data = InspectionTemplateCreate(
            name=name,
            description=description,
            equipment_id=equipment_id,
            frequency=frequency,
            estimated_duration_minutes=duration,
            is_active=self.active_var.get(),
            checkpoints=checkpoint_schemas,
        )

        try:
            if self.template_id:
                self.service.update_template(self.template_id, template_data)
                messagebox.showinfo("موفق", "قالب با موفقیت بروزرسانی شد.", parent=self)
            else:
                self.service.create_template(template_data)
                messagebox.showinfo("موفق", "قالب با موفقیت ایجاد شد.", parent=self)
            self.result = True
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ذخیره قالب:\n{e}", parent=self)


# ══════════════════════════════════════════════════════════════════════════════
#  CheckpointDialog — Add / Edit a single checkpoint
# ══════════════════════════════════════════════════════════════════════════════

class CheckpointDialog(tk.Toplevel):
    """Dialog for adding/editing a single checkpoint."""

    def __init__(self, parent, checkpoint_data: Optional[dict] = None):
        super().__init__(parent)
        self.checkpoint_data = checkpoint_data
        self.result = None

        self.title("ویرایش چک‌پوینت" if checkpoint_data else "چک‌پوینت جدید")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._center(500, 380)
        self.grab_set()

        self._build_ui()
        if checkpoint_data:
            self._load_data()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        hdr = tk.Frame(self, bg=PRIMARY, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        title = "✏️  ویرایش چک‌پوینت" if self.checkpoint_data else "➕  چک‌پوینت جدید"
        tk.Label(hdr, text=title, font=FONT_TITLE,
                 bg=PRIMARY, fg=WHITE).pack(side="right", padx=20, pady=12)

        body = tk.Frame(self, bg=BG, padx=20, pady=15)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="عنوان *:", font=FONT_LABEL, bg=BG, fg=TEXT).grid(
            row=0, column=1, sticky="e", pady=8, padx=5)
        self.title_var = tk.StringVar()
        tk.Entry(body, textvariable=self.title_var, font=FONT_INPUT,
                 width=35, relief="solid", bd=1).grid(row=0, column=0, sticky="ew", pady=8, padx=5)

        tk.Label(body, text="نوع *:", font=FONT_LABEL, bg=BG, fg=TEXT).grid(
            row=1, column=1, sticky="e", pady=8, padx=5)
        self.type_var = tk.StringVar(value="بصری")
        ttk.Combobox(body, textvariable=self.type_var,
                     values=list(TYPE_OPTIONS.keys()),
                     state="readonly", width=33, font=FONT_INPUT).grid(
            row=1, column=0, sticky="ew", pady=8, padx=5)

        tk.Label(body, text="توضیحات:", font=FONT_LABEL, bg=BG, fg=TEXT).grid(
            row=2, column=1, sticky="ne", pady=8, padx=5)
        self.desc_text = tk.Text(body, font=FONT_INPUT, width=35, height=6,
                                 relief="solid", bd=1)
        self.desc_text.grid(row=2, column=0, sticky="ew", pady=8, padx=5)

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=(0, 15))
        tk.Button(btn_frame, text="ذخیره", font=FONT_LABEL,
                  bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                  padx=20, pady=7, command=self._save).pack(side="right", padx=(5, 0))
        tk.Button(btn_frame, text="انصراف", font=FONT_INPUT,
                  bg=BORDER, fg=TEXT, relief="flat", cursor="hand2",
                  padx=20, pady=7, command=self.destroy).pack(side="right")

    def _load_data(self):
        self.title_var.set(self.checkpoint_data["title"])
        self.type_var.set(TYPE_FA.get(self.checkpoint_data["type"], "بصری"))
        self.desc_text.insert("1.0", self.checkpoint_data.get("description", ""))

    def _save(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showerror("خطا", "عنوان الزامی است.", parent=self)
            return

        self.result = {
            "id":          self.checkpoint_data["id"] if self.checkpoint_data else None,
            "title":       title,
            "description": self.desc_text.get("1.0", "end").strip(),
            "type":        TYPE_OPTIONS.get(self.type_var.get(), "visual"),
            "order":       self.checkpoint_data["order"] if self.checkpoint_data else 1,
        }
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  InspectionStartDialog — Start a new inspection
# ══════════════════════════════════════════════════════════════════════════════

class InspectionStartDialog(tk.Toplevel):
    """Dialog for starting a new inspection session."""

    def __init__(self, parent, db_session, service: InspectionService, current_user):
        super().__init__(parent)
        self.db           = db_session
        self.service      = service
        self.current_user = current_user
        self.result       = None

        self.title("شروع بازرسی جدید")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._center(520, 340)
        self.grab_set()

        self._templates = self.service.get_active_templates()
        self._build_ui()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        hdr = tk.Frame(self, bg=PRIMARY, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🔍  شروع بازرسی جدید", font=FONT_TITLE,
                 bg=PRIMARY, fg=WHITE).pack(side="right", padx=20, pady=12)

        body = tk.Frame(self, bg=BG, padx=20, pady=15)
        body.pack(fill="both", expand=True)

        # Template
        tk.Label(body, text="قالب بازرسی *:", font=FONT_LABEL, bg=BG, fg=TEXT).grid(
            row=0, column=1, sticky="e", pady=8, padx=5)
        template_names = [
            f"{t.name} — {t.equipment.name if t.equipment else 'عمومی'}"
            for t in self._templates
        ]
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(body, textvariable=self.template_var,
                                           values=template_names,
                                           state="readonly", width=38, font=FONT_INPUT)
        if template_names:
            self.template_combo.current(0)
        self.template_combo.grid(row=0, column=0, sticky="ew", pady=8, padx=5)

        # Equipment override
        tk.Label(body, text="تجهیز (اختیاری):", font=FONT_LABEL, bg=BG, fg=TEXT).grid(
            row=1, column=1, sticky="e", pady=8, padx=5)
        equipment_list = self.db.query(Equipment).filter(Equipment.status != "inactive").all()
        self._equipment_list = equipment_list
        eq_names = ["طبق قالب"] + [eq.name for eq in equipment_list]
        self.eq_var = tk.StringVar(value="طبق قالب")
        ttk.Combobox(body, textvariable=self.eq_var, values=eq_names,
                     state="readonly", width=38, font=FONT_INPUT).grid(
            row=1, column=0, sticky="ew", pady=8, padx=5)

        # Notes
        tk.Label(body, text="یادداشت:", font=FONT_LABEL, bg=BG, fg=TEXT).grid(
            row=2, column=1, sticky="ne", pady=8, padx=5)
        self.notes_text = tk.Text(body, font=FONT_INPUT, width=38, height=4,
                                  relief="solid", bd=1)
        self.notes_text.grid(row=2, column=0, sticky="ew", pady=8, padx=5)

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=(0, 15))
        tk.Button(btn_frame, text="شروع بازرسی", font=FONT_LABEL,
                  bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                  padx=20, pady=8, command=self._start).pack(side="right", padx=(5, 0))
        tk.Button(btn_frame, text="انصراف", font=FONT_INPUT,
                  bg=BORDER, fg=TEXT, relief="flat", cursor="hand2",
                  padx=20, pady=8, command=self.destroy).pack(side="right")

    def _start(self):
        if not self._templates:
            messagebox.showerror("خطا", "هیچ قالب فعالی یافت نشد.", parent=self)
            return

        idx = self.template_combo.current()
        if idx < 0:
            messagebox.showerror("خطا", "لطفاً یک قالب انتخاب کنید.", parent=self)
            return

        template    = self._templates[idx]
        equipment_id = template.equipment_id

        eq_name = self.eq_var.get()
        if eq_name != "طبق قالب":
            eq = next((e for e in self._equipment_list if e.name == eq_name), None)
            if eq:
                equipment_id = eq.id

        if not equipment_id:
            messagebox.showerror("خطا", "تجهیز مشخص نشده است.", parent=self)
            return

        notes = self.notes_text.get("1.0", "end").strip() or None

        try:
            inspection = self.service.create_inspection(InspectionCreate(
                template_id=template.id,
                equipment_id=equipment_id,
                inspector_id=self.current_user["id"],
                notes=notes,
            ))
            messagebox.showinfo("موفق", f"بازرسی شماره {inspection.id} شروع شد.", parent=self)
            self.result = inspection.id
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در شروع بازرسی:\n{e}", parent=self)


# ══════════════════════════════════════════════════════════════════════════════
#  InspectionExecuteDialog — Carry out a running inspection
# ══════════════════════════════════════════════════════════════════════════════

class InspectionExecuteDialog(tk.Toplevel):
    """Dialog for executing (filling out) an in-progress inspection."""

    def __init__(self, parent, db_session, service: InspectionService, inspection_id: int):
        super().__init__(parent)
        self.db            = db_session
        self.service       = service
        self.inspection_id = inspection_id
        self.checkpoint_results: dict = {}
        self.result = False

        self.inspection = self.service.get_inspection(inspection_id)
        if not self.inspection:
            messagebox.showerror("خطا", "بازرسی یافت نشد.", parent=parent)
            self.destroy()
            return

        self.title(f"انجام بازرسی — شماره {inspection_id}")
        self.configure(bg=BG)
        self.geometry("920x700")
        self._center(920, 700)
        self.grab_set()

        self._build_ui()
        self._load_checkpoints()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=PRIMARY, height=80)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ins = self.inspection
        tk.Label(hdr, text=f"📋  {ins.template.name}", font=FONT_TITLE,
                 bg=PRIMARY, fg=WHITE).pack(anchor="e", padx=20, pady=(12, 2))
        eq_name = ins.equipment.name if ins.equipment else "—"
        tk.Label(hdr, text=f"تجهیز: {eq_name}  |  بازرس: {ins.inspector.full_name}",
                 font=FONT_SMALL, bg=PRIMARY, fg="#c8d8ff").pack(anchor="e", padx=20)

        # Scrollable checkpoints area
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=16, pady=10)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb    = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self._scroll_frame = tk.Frame(canvas, bg=BG)

        self._scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Mousewheel scroll
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # Buttons
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=16, pady=(0, 12))

        tk.Button(btn_frame, text="✅ تکمیل بازرسی", font=FONT_LABEL,
                  bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                  padx=18, pady=8, command=self._complete).pack(side="right", padx=(5, 0))
        tk.Button(btn_frame, text="💾 ذخیره موقت", font=FONT_INPUT,
                  bg=PRIMARY, fg=WHITE, relief="flat", cursor="hand2",
                  padx=18, pady=8, command=self._save_progress).pack(side="right", padx=(5, 0))
        tk.Button(btn_frame, text="❌ لغو بازرسی", font=FONT_INPUT,
                  bg=DANGER, fg=WHITE, relief="flat", cursor="hand2",
                  padx=18, pady=8, command=self._cancel).pack(side="left")

    def _load_checkpoints(self):
        checkpoints = sorted(self.inspection.template.checkpoints, key=lambda x: x.order_number)
        existing    = {r.checkpoint_id: r for r in self.inspection.results}

        for cp in checkpoints:
            # Card frame
            card = tk.Frame(self._scroll_frame, bg=WHITE,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill="x", pady=6, padx=4)

            # Title row
            title_bar = tk.Frame(card, bg=PRIMARY)
            title_bar.pack(fill="x")
            tk.Label(title_bar,
                     text=f"  {cp.order_number}.  {cp.title}",
                     font=FONT_LABEL, bg=PRIMARY, fg=WHITE,
                     anchor="e").pack(side="right", padx=10, pady=6)
            type_fa = TYPE_FA.get(cp.checkpoint_type, cp.checkpoint_type)
            tk.Label(title_bar, text=f"[{type_fa}]",
                     font=FONT_SMALL, bg=PRIMARY, fg="#c8d8ff").pack(side="left", padx=10)

            # Description
            if cp.description:
                tk.Label(card, text=cp.description, font=FONT_SMALL,
                         bg=WHITE, fg=SUBTLE, anchor="e", justify="right",
                         wraplength=700).pack(anchor="e", padx=14, pady=(6, 2))

            # Result radio buttons
            result_frame = tk.Frame(card, bg=WHITE)
            result_frame.pack(fill="x", padx=14, pady=6)

            result_var = tk.StringVar(value="")

            for text, value, color in [("✅ قبول", "pass", SUCCESS),
                                        ("❌ رد",   "fail", DANGER),
                                        ("— N/A",  "na",   SUBTLE)]:
                tk.Radiobutton(result_frame, text=text, variable=result_var,
                               value=value, font=FONT_INPUT,
                               bg=WHITE, fg=color,
                               selectcolor=WHITE,
                               activebackground=WHITE).pack(side="right", padx=12)

            # Comment
            tk.Label(card, text="توضیحات:", font=FONT_SMALL,
                     bg=WHITE, fg=TEXT, anchor="e").pack(anchor="e", padx=14)
            comment_text = tk.Text(card, font=FONT_INPUT, height=3,
                                   relief="solid", bd=1, wrap="word")
            comment_text.pack(fill="x", padx=14, pady=(2, 10))

            # Restore existing result if any
            if cp.id in existing:
                r = existing[cp.id]
                result_var.set(r.result)
                if r.comment:
                    comment_text.insert("1.0", r.comment)

            self.checkpoint_results[cp.id] = {
                "checkpoint":   cp,
                "result_var":   result_var,
                "comment_text": comment_text,
            }

    def _collect_results(self) -> List[InspectionResultCreate]:
        results = []
        for cp_id, data in self.checkpoint_results.items():
            val = data["result_var"].get()
            if val:
                comment = data["comment_text"].get("1.0", "end").strip()
                results.append(InspectionResultCreate(
                    inspection_id=self.inspection_id,
                    checkpoint_id=cp_id,
                    result=val,
                    comment=comment or None,
                ))
        return results

    def _save_progress(self):
        try:
            results = self._collect_results()
            # Delete old results and re-save (idempotent progress save)
            for r in results:
                self.service.save_results(self.inspection_id, [r])
            self.db.commit()
            messagebox.showinfo("موفق", "پیشرفت ذخیره شد.", parent=self)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("خطا", f"خطا در ذخیره:\n{e}", parent=self)

    def _complete(self):
        # Find unanswered checkpoints
        incomplete = [
            data["checkpoint"].title
            for data in self.checkpoint_results.values()
            if not data["result_var"].get()
        ]

        if incomplete:
            msg = "چک‌پوینت‌های زیر هنوز نتیجه ندارند:\n• " + "\n• ".join(incomplete)
            if not messagebox.askyesno("هشدار", msg + "\n\nآیا می‌خواهید ادامه دهید؟",
                                       parent=self):
                return

        try:
            results = self._collect_results()
            inspection = self.service.save_results(self.inspection_id, results)
            result_fa  = RESULT_FA.get(inspection.overall_result, inspection.overall_result)
            messagebox.showinfo(
                "بازرسی تکمیل شد",
                f"بازرسی با موفقیت ثبت شد.\nنتیجه کلی: {result_fa}",
                parent=self,
            )
            self.result = True
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در تکمیل بازرسی:\n{e}", parent=self)

    def _cancel(self):
        if not messagebox.askyesno("لغو بازرسی",
                                   "آیا مطمئن هستید که می‌خواهید این بازرسی را لغو کنید؟\n"
                                   "اطلاعات ذخیره‌نشده از بین می‌رود.",
                                   parent=self):
            return
        try:
            self.service.cancel_inspection(self.inspection_id)
            self.result = False
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در لغو بازرسی:\n{e}", parent=self)


# ══════════════════════════════════════════════════════════════════════════════
#  InspectionDetailDialog — Read-only view of a completed inspection
# ══════════════════════════════════════════════════════════════════════════════

class InspectionDetailDialog(tk.Toplevel):
    """Read-only dialog showing full details of a completed inspection."""

    def __init__(self, parent, db_session, service: InspectionService, inspection_id: int):
        super().__init__(parent)
        self.db            = db_session
        self.service       = service
        self.inspection_id = inspection_id

        self.title(f"جزئیات بازرسی — شماره {inspection_id}")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._center(820, 620)
        self.grab_set()

        self.inspection = self.service.get_inspection(inspection_id)
        if not self.inspection:
            messagebox.showerror("خطا", "بازرسی یافت نشد.", parent=parent)
            self.destroy()
            return

        self._build_ui()
        self._load_data()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Header
        ins    = self.inspection
        result = ins.overall_result or "in_progress"
        hdr_color = {
            "pass":    SUCCESS,
            "fail":    DANGER,
            "partial": "#F29900",
        }.get(result, PRIMARY)

        hdr = tk.Frame(self, bg=hdr_color, height=90)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        eq_name = ins.equipment.name if ins.equipment else "—"
        tk.Label(hdr, text=f"📋  {ins.template.name}", font=FONT_TITLE,
                 bg=hdr_color, fg=WHITE).pack(anchor="e", padx=20, pady=(12, 2))
        tk.Label(hdr,
                 text=f"تجهیز: {eq_name}  |  بازرس: {ins.inspector.full_name}",
                 font=FONT_SMALL, bg=hdr_color, fg=WHITE).pack(anchor="e", padx=20)
        result_text = RESULT_FA.get(result, result)
        tk.Label(hdr, text=f"نتیجه کلی: {result_text}",
                 font=FONT_LABEL, bg=hdr_color, fg=WHITE).pack(anchor="e", padx=20)

        # Scrollable body
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=16, pady=10)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb    = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self._body = tk.Frame(canvas, bg=BG)

        self._body.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._body, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # Close button
        tk.Button(self, text="بستن", font=FONT_LABEL,
                  bg=BORDER, fg=TEXT, relief="flat", cursor="hand2",
                  padx=20, pady=8, command=self.destroy).pack(pady=(0, 12))

    def _load_data(self):
        ins         = self.inspection
        results_map = {r.checkpoint_id: r for r in ins.results}
        checkpoints = sorted(ins.template.checkpoints, key=lambda x: x.order_number)

        for cp in checkpoints:
            r = results_map.get(cp.id)

            res_value  = r.result if r else None
            card_color = {
                "pass": GREEN_BG,
                "fail": RED_BG,
                "na":   "#F8F8F8",
            }.get(res_value, WHITE)

            card = tk.Frame(self._body, bg=card_color,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill="x", pady=5, padx=4)

            # Title
            tk.Label(card,
                     text=f"{cp.order_number}.  {cp.title}",
                     font=FONT_LABEL, bg=card_color, fg=TEXT,
                     anchor="e").pack(anchor="e", padx=14, pady=(8, 2))

            # Result badge
            res_text  = RESULT_FA.get(res_value, "— ثبت نشده")
            res_color = {
                "pass": SUCCESS,
                "fail": DANGER,
                "na":   SUBTLE,
            }.get(res_value, SUBTLE)

            tk.Label(card, text=f"نتیجه: {res_text}", font=FONT_INPUT,
                     bg=card_color, fg=res_color).pack(anchor="e", padx=20)

            if r and r.comment:
                tk.Label(card, text=f"توضیح: {r.comment}", font=FONT_SMALL,
                         bg=card_color, fg=SUBTLE, anchor="e",
                         justify="right", wraplength=680).pack(
                    anchor="e", padx=20, pady=(2, 8))
            else:
                tk.Label(card, text="", bg=card_color).pack(pady=3)