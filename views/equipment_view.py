# views/equipment_view.py
import tkinter as tk
from views.ui_kit import rtl_columns  # RTL (right-to-left) table columns
from tkinter import ttk, messagebox
from datetime import datetime
from database.models import EquipmentStatus
from auth.auth_manager import AuthManager
from views.equipment_dialog import EquipmentDialog
from views.category_manager_dialog import CategoryManagerDialog
from views.location_manager_dialog import LocationManagerDialog
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, TEXT_DARK, TEXT_LIGHT, SUCCESS,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)
# Import Jalali date helper
from utils.date_helpers import to_jalali_datetime_str

CARD_BG     = "#FFFFFF"
CARD_BORDER = "#E8ECF0"
SECTION_BG  = "#F4F6F9"
HEADER_H    = 72
STRIP_H     = 4

ACCENT_GREEN  = SUCCESS
ACCENT_AMBER  = "#D97706"
ACCENT_ROSE   = "#DC2626"
ACCENT_NAVY   = NAVY

STATUS_FA = {
    EquipmentStatus.OPERATIONAL.value: "عملیاتی",
    EquipmentStatus.MAINTENANCE.value: "در تعمیر",
    EquipmentStatus.BREAKDOWN.value:   "خراب",
    EquipmentStatus.INACTIVE.value:    "غیرفعال",
}
STATUS_COLOR = {
    EquipmentStatus.OPERATIONAL.value: ACCENT_GREEN,
    EquipmentStatus.MAINTENANCE.value: ACCENT_AMBER,
    EquipmentStatus.BREAKDOWN.value:   ACCENT_ROSE,
    EquipmentStatus.INACTIVE.value:    TEXT_LIGHT,
}
STATUS_BADGE_BG = {
    EquipmentStatus.OPERATIONAL.value: "#D1FAE5",
    EquipmentStatus.MAINTENANCE.value: "#FEF3C7",
    EquipmentStatus.BREAKDOWN.value:   "#FEE2E2",
    EquipmentStatus.INACTIVE.value:    CARD_BORDER,
}


class EquipmentView(tk.Frame):
    def __init__(self, parent, equipment_repo, current_user):
        super().__init__(parent, bg=SECTION_BG)
        self.equipment_repo = equipment_repo
        self.current_user   = current_user
        self.is_admin       = current_user["role"] == "admin"
        self.is_manager     = current_user["role"] in ["admin", "manager"]
        self.is_technician  = current_user["role"] == "technician"
        # Technicians can add/edit/change status, but not delete or manage categories/locations
        # built-in roles as before; custom roles from «مدیریت نقش‌ها»
        self.can_edit       = AuthManager.allows(("admin", "manager", "technician"), "equipment", "write")
        # category / location lists: managers, or a custom role with «حذف» (full control)
        self.can_manage_lists = AuthManager.allows(("admin", "manager"), "equipment", "delete")
        self.can_delete     = AuthManager.can_access("equipment", "delete")
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        self._build_header()
        self._build_stats_bar()
        self._build_toolbar()
        self._build_table()
        self._build_action_bar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=NAVY, height=HEADER_H)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        right = tk.Frame(hdr, bg=NAVY)
        right.pack(side="right", padx=24, fill="y")
        tk.Label(right, text="⚙️", font=("Tahoma", 20),
                 bg=NAVY, fg=WHITE).pack(side="right", pady=18)
        title_col = tk.Frame(right, bg=NAVY)
        title_col.pack(side="right", padx=(0, 10), fill="y")
        tk.Label(title_col, text="مدیریت تجهیزات",
                 font=FONT_TITLE, bg=NAVY, fg=WHITE).pack(anchor="e", pady=(16, 0))
        tk.Label(title_col, text="ثبت، ویرایش و پایش وضعیت تجهیزات کارخانه",
                 font=FONT_SMALL, bg=NAVY, fg=WHITE).pack(anchor="e")

        left = tk.Frame(hdr, bg=NAVY)
        left.pack(side="left", padx=20, fill="y")
        if self.can_edit:
            tk.Button(left, text="➕  افزودن تجهیز", font=FONT_SMALL,
                      bg=WHITE, fg=NAVY, relief="flat", cursor="hand2",
                      padx=14, pady=6,
                      command=self._add_equipment).pack(side="left", padx=4, pady=20)
        if self.can_manage_lists:
            tk.Button(left, text="🏷️  دسته‌بندی‌ها", font=FONT_SMALL,
                      bg=NAVY_LIGHT, fg=WHITE, relief="flat", cursor="hand2",
                      padx=14, pady=6,
                      command=self._manage_categories).pack(side="left", padx=4, pady=20)
            tk.Button(left, text="📍 موقعیت‌ها", font=FONT_SMALL,
                      bg=NAVY_LIGHT, fg=WHITE, relief="flat", cursor="hand2",
                      padx=14, pady=6,
                      command=self._manage_locations).pack(side="left", padx=4, pady=20)
        tk.Button(left, text="📤  خروجی Excel", font=FONT_SMALL,
                  bg="#0D9488", fg=WHITE, relief="flat", cursor="hand2",
                  padx=14, pady=6,
                  command=self._export).pack(side="left", padx=4, pady=20)

        tk.Frame(self, bg=CARD_BORDER, height=1).pack(fill="x")

    def _build_stats_bar(self):
        self._stats_frame = tk.Frame(self, bg=SECTION_BG)
        self._stats_frame.pack(fill="x", padx=20, pady=(16, 0))
        self.stat_labels = {}

        stat_defs = [
            ("total",       "کل تجهیزات",  ACCENT_NAVY,  "⚙️"),
            ("operational", "عملیاتی",     ACCENT_GREEN, "✅"),
            ("maintenance", "در تعمیر",    ACCENT_AMBER, "🔧"),
            ("breakdown",   "خراب",        ACCENT_ROSE,  "🔴"),
        ]
        for key, label, color, icon in stat_defs:
            shadow = tk.Frame(self._stats_frame, bg=CARD_BORDER)
            shadow.pack(side="right", padx=6)
            card = tk.Frame(shadow, bg=CARD_BG)
            card.pack(fill="both", expand=True, padx=1, pady=1)
            tk.Frame(card, bg=color, height=STRIP_H).pack(fill="x")
            inner = tk.Frame(card, bg=CARD_BG)
            inner.pack(padx=18, pady=10)
            top = tk.Frame(inner, bg=CARD_BG)
            top.pack(fill="x")
            tk.Label(top, text=icon, font=("Tahoma", 14),
                     bg=CARD_BG, fg=color).pack(side="right")
            tk.Label(top, text=label, font=FONT_SMALL,
                     bg=CARD_BG, fg=TEXT_LIGHT).pack(side="right", padx=(0, 4))
            lbl = tk.Label(inner, text="0", font=FONT_HEADING,
                           bg=CARD_BG, fg=color)
            lbl.pack(anchor="center", pady=(4, 0))
            self.stat_labels[key] = lbl

    def _build_toolbar(self):
        row = tk.Frame(self, bg=SECTION_BG)
        row.pack(fill="x", padx=20, pady=(18, 6))
        tk.Label(row, text="🗂️  لیست تجهیزات",
                 font=FONT_HEADING, bg=SECTION_BG, fg=TEXT_DARK).pack(side="right")
        tk.Frame(row, bg=CARD_BORDER, height=1).pack(
            side="right", fill="x", expand=True, padx=(0, 12), pady=8)

        outer = tk.Frame(self, bg=CARD_BORDER)
        outer.pack(fill="x", padx=20, pady=(0, 10))
        bar = tk.Frame(outer, bg=CARD_BG)
        bar.pack(fill="x", padx=1, pady=1)

        inner = tk.Frame(bar, bg=CARD_BG)
        inner.pack(fill="x", padx=16, pady=10)

        tk.Label(inner, text="🔍  جستجو:", font=FONT_NORMAL,
                 bg=CARD_BG, fg=TEXT_DARK).pack(side="right", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *_: self._load_data())
        tk.Entry(inner, textvariable=self.search_var, font=FONT_NORMAL,
                 bg=SECTION_BG, relief="solid", bd=1,
                 width=22).pack(side="right", ipady=5)

        tk.Frame(inner, bg=CARD_BORDER, width=1).pack(
            side="right", fill="y", padx=14, pady=4)

        tk.Label(inner, text="دسته:", font=FONT_NORMAL,
                 bg=CARD_BG, fg=TEXT_DARK).pack(side="right", padx=(0, 6))
        self.category_var = tk.StringVar(value="همه")
        self.category_combo = ttk.Combobox(
            inner, textvariable=self.category_var,
            font=FONT_NORMAL, state="readonly", width=14)
        self.category_combo.pack(side="right", ipady=3)
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self._load_data())

        tk.Frame(inner, bg=CARD_BORDER, width=1).pack(
            side="right", fill="y", padx=14, pady=4)

        tk.Label(inner, text="وضعیت:", font=FONT_NORMAL,
                 bg=CARD_BG, fg=TEXT_DARK).pack(side="right", padx=(0, 6))
        self.status_var = tk.StringVar(value="همه")
        ttk.Combobox(
            inner, textvariable=self.status_var,
            values=["همه"] + list(STATUS_FA.values()),
            font=FONT_NORMAL, state="readonly", width=11
        ).pack(side="right", ipady=3)
        self.status_var.trace("w", lambda *_: self._load_data())

        self._row_count_lbl = tk.Label(
            inner, text="", font=FONT_SMALL,
            bg=NAVY, fg=WHITE, padx=10, pady=2)
        self._row_count_lbl.pack(side="left")

    def _build_table(self):
        outer = tk.Frame(self, bg=CARD_BORDER)
        outer.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        card = tk.Frame(outer, bg=CARD_BG)
        card.pack(fill="both", expand=True, padx=1, pady=1)

        cols = ("code", "name", "category", "location", "status", "updated")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=16)
        rtl_columns(self.tree)  # RTL column order

        style = ttk.Style()
        style.configure("Equipment.Treeview",
                        background=CARD_BG, fieldbackground=CARD_BG,
                        foreground=TEXT_DARK, rowheight=30,
                        font=FONT_NORMAL)
        style.configure("Equipment.Treeview.Heading",
                        background=NAVY, foreground=WHITE,
                        font=FONT_NORMAL, relief="flat")
        style.map("Equipment.Treeview",
                  background=[("selected", NAVY)],
                  foreground=[("selected", WHITE)])
        self.tree.configure(style="Equipment.Treeview")

        headers = [
            ("code",    "کد تجهیز",         110),
            ("name",    "نام تجهیز",         220),
            ("category","دسته‌بندی",          130),
            ("location","موقعیت",             150),
            ("status",  "وضعیت",             110),
            ("updated", "آخرین بروزرسانی",   150),
        ]
        for col, text, width in headers:
            self.tree.heading(col, text=text,
                              command=lambda c=col: self._sort_column(c))
            self.tree.column(col, width=width, anchor="center")

        for status, color in STATUS_COLOR.items():
            bg = STATUS_BADGE_BG.get(status, CARD_BG)
            self.tree.tag_configure(status, foreground=color)

        vsb = ttk.Scrollbar(card, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(card, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        card.rowconfigure(0, weight=1)
        card.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>",    lambda e: self._edit_equipment())
        self.tree.bind("<Delete>",      lambda e: self._delete_selected())
        self.tree.bind("<F2>",          lambda e: self._edit_or_add())
        self.tree.bind("<Control-n>",   lambda e: self._add_equipment())
        self.tree.bind("<Button-3>",    self._show_context_menu)
        self._build_context_menu()

    def _build_context_menu(self):
        self._ctx = tk.Menu(self, tearoff=0, font=FONT_NORMAL)
        if self.can_edit:
            self._ctx.add_command(label="✏️  ویرایش",           command=self._edit_equipment)
            self._ctx.add_command(label="🔄  تغییر وضعیت",      command=self._change_status)
            self._ctx.add_separator()
        if self.can_delete:
            self._ctx.add_command(label="🗑️  حذف",              command=self._delete_equipment)

    def _show_context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            try:
                self._ctx.post(event.x_root, event.y_root)
            finally:
                self._ctx.grab_release()

    def _build_action_bar(self):
        outer = tk.Frame(self, bg=CARD_BORDER)
        outer.pack(fill="x", padx=20, pady=(0, 20))
        bar = tk.Frame(outer, bg=CARD_BG)
        bar.pack(fill="x", padx=1, pady=1)
        inner = tk.Frame(bar, bg=CARD_BG)
        inner.pack(fill="x", padx=16, pady=10)

        if self.can_edit:
            tk.Button(inner, text="✏️  ویرایش", font=FONT_NORMAL,
                      bg=NAVY, fg=WHITE, relief="flat", cursor="hand2",
                      padx=16, pady=8,
                      command=self._edit_equipment).pack(side="right", padx=4)
            tk.Button(inner, text="🔄  تغییر وضعیت", font=FONT_NORMAL,
                      bg=ACCENT_AMBER, fg=WHITE, relief="flat", cursor="hand2",
                      padx=16, pady=8,
                      command=self._change_status).pack(side="right", padx=4)
        if self.can_delete:
            tk.Button(inner, text="🗑️  حذف", font=FONT_NORMAL,
                      bg=ACCENT_ROSE, fg=WHITE, relief="flat", cursor="hand2",
                      padx=16, pady=8,
                      command=self._delete_equipment).pack(side="right", padx=4)

        tk.Label(inner, text="F2: ویرایش  |  Del: حذف  |  Ctrl+N: افزودن",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left")

    def _load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        search    = self.search_var.get().strip()
        category  = self.category_var.get()
        status_fa = self.status_var.get()

        if search:
            equipment_list = self.equipment_repo.search_equipment(search)
        else:
            equipment_list = self.equipment_repo.get_all_equipment()

        if category != "همه":
            equipment_list = [e for e in equipment_list if e["category"] == category]
        if status_fa != "همه":
            status_en = next((k for k, v in STATUS_FA.items() if v == status_fa), None)
            if status_en:
                equipment_list = [e for e in equipment_list if e["status"] == status_en]

        for eq in equipment_list:
            status_text = STATUS_FA.get(eq["status"], eq["status"])

            # Convert updated_at to Jalali
            updated_raw = eq.get("updated_at")
            if updated_raw:
                try:
                    if isinstance(updated_raw, str):
                        dt = datetime.strptime(updated_raw, "%Y-%m-%d %H:%M:%S")
                    else:
                        dt = updated_raw
                    updated = to_jalali_datetime_str(dt)
                except Exception:
                    updated = "—"
            else:
                updated = "—"

            self.tree.insert("", "end", values=(
                eq["code"], eq["name"], eq["category"],
                eq["location"], status_text, updated
            ), tags=(eq["status"],))

        count = len(equipment_list)
        self._row_count_lbl.config(
            text=f"  {count} تجهیز  " if count else "  بدون نتیجه  ")

        self._update_stats()
        self._update_category_filter()

    def _update_stats(self):
        stats = self.equipment_repo.get_stats()
        self.stat_labels["total"].config(text=str(stats.get("total", 0)))
        self.stat_labels["operational"].config(text=str(stats.get("operational", 0)))
        self.stat_labels["maintenance"].config(text=str(stats.get("maintenance", 0)))
        self.stat_labels["breakdown"].config(text=str(stats.get("breakdown", 0)))

    def _update_category_filter(self):
        cats = ["همه"] + self.equipment_repo.get_categories()
        self.category_combo["values"] = cats

    def _sort_column(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        items.sort()
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

    def _get_selected_equipment(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("هشدار", "لطفاً یک تجهیز انتخاب کنید.", parent=self)
            return None
        values = self.tree.item(selected[0], "values")
        return self.equipment_repo.get_equipment_by_code(values[0])

    def _add_equipment(self):
        if not self.can_edit:
            messagebox.showwarning("دسترسی", "شما مجاز به افزودن تجهیز نیستید.", parent=self)
            return
        dialog = EquipmentDialog(self, self.equipment_repo)
        self.wait_window(dialog)
        if dialog.result:
            self._load_data()

    def _edit_equipment(self):
        if not self.can_edit:
            messagebox.showwarning("دسترسی", "شما مجاز به ویرایش تجهیز نیستید.", parent=self)
            return
        equipment = self._get_selected_equipment()
        if not equipment:
            return
        dialog = EquipmentDialog(self, self.equipment_repo, equipment)
        self.wait_window(dialog)
        if dialog.result:
            self._load_data()

    def _edit_or_add(self):
        if not self.can_edit:
            return
        selected = self.tree.selection()
        if not selected:
            self._add_equipment()
        else:
            self._edit_equipment()

    def _change_status(self):
        if not self.can_edit:
            messagebox.showwarning("دسترسی", "شما مجاز به تغییر وضعیت نیستید.", parent=self)
            return
        equipment = self._get_selected_equipment()
        if not equipment:
            return

        dlg = tk.Toplevel(self)
        dlg.title("تغییر وضعیت تجهیز")
        dlg.configure(bg=SECTION_BG)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        hdr = tk.Frame(dlg, bg=NAVY, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🔄  تغییر وضعیت تجهیز",
                 font=FONT_HEADING, bg=NAVY, fg=WHITE).pack(pady=10)

        body = tk.Frame(dlg, bg=SECTION_BG)
        body.pack(fill="both", expand=True, padx=30, pady=20)

        tk.Label(body, text=f"تجهیز: {equipment['name']}",
                 font=FONT_NORMAL, bg=SECTION_BG, fg=TEXT_DARK).pack(anchor="e", pady=(0, 10))
        tk.Label(body, text="وضعیت جدید:",
                 font=FONT_NORMAL, bg=SECTION_BG, fg=TEXT_DARK).pack(anchor="e", pady=(0, 6))

        status_var = tk.StringVar(value=STATUS_FA.get(equipment["status"], ""))
        ttk.Combobox(body, textvariable=status_var,
                     values=list(STATUS_FA.values()),
                     font=FONT_NORMAL, state="readonly",
                     width=22).pack(anchor="e", ipady=4)

        def save():
            new_fa = status_var.get()
            new_en = next((k for k, v in STATUS_FA.items() if v == new_fa), None)
            if not new_en:
                messagebox.showerror("خطا", "وضعیت نامعتبر است.", parent=dlg)
                return
            ok, msg = self.equipment_repo.update_status(equipment["id"], new_en)
            if ok:
                dlg.destroy()
                self._load_data()
                messagebox.showinfo("موفق", msg, parent=self)
            else:
                messagebox.showerror("خطا", msg, parent=dlg)

        tk.Button(body, text="ذخیره", font=FONT_NORMAL,
                  bg=NAVY, fg=WHITE, relief="flat", cursor="hand2",
                  padx=24, pady=8, command=save).pack(pady=20)

        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width()  - dlg.winfo_width())  // 2
        y = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

    def _manage_categories(self):
        if not self.can_manage_lists:
            messagebox.showwarning("دسترسی", "شما مجاز به مدیریت دسته‌بندی‌ها نیستید.", parent=self)
            return
        dialog = CategoryManagerDialog(
            self, self.equipment_repo,
            callback=self._update_category_filter)
        self.wait_window(dialog)

    def _manage_locations(self):
        if not self.can_manage_lists:
            messagebox.showwarning("دسترسی", "شما مجاز به مدیریت موقعیت‌ها نیستید.", parent=self)
            return
        dialog = LocationManagerDialog(
            self, self.equipment_repo,
            callback=None)   # the equipment dialog already refreshes itself
        self.wait_window(dialog)

    def _export(self):
        from views.export_dialog import run_equipment_export
        selected = None
        sel = self.tree.selection()
        if sel:
            values = self.tree.item(sel[0], "values")
            selected = self.equipment_repo.get_equipment_by_code(values[0])
        eq_list = self.equipment_repo.get_all_equipment()
        run_equipment_export(self, eq_list, selected_equipment=selected)

    def _delete_equipment(self):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف تجهیز نیستید.", parent=self)
            return
        equipment = self._get_selected_equipment()
        if not equipment:
            return
        if not messagebox.askyesno(
            "تایید حذف",
            f"آیا از حذف تجهیز «{equipment['name']}» اطمینان دارید؟\n\n"
            "تجهیزی که سابقه (دستورکار، بازرسی، ساعت کار) دارد حذف نمی‌شود "
            "و می‌توانید آن را غیرفعال کنید.",
            parent=self
        ):
            return
        ok, msg = self.equipment_repo.delete_equipment(equipment["id"])
        if ok:
            self._load_data()
            messagebox.showinfo("موفق", msg, parent=self)
        elif "غیرفعال" in msg and equipment.get("status") != EquipmentStatus.INACTIVE.value:
            if messagebox.askyesno("حذف ممکن نیست", msg + "\n\nوضعیت تجهیز الان «غیرفعال» شود؟", parent=self):
                ok2, msg2 = self.equipment_repo.update_status(
                    equipment["id"], EquipmentStatus.INACTIVE.value)
                self._load_data()
                if not ok2:
                    messagebox.showerror("خطا", msg2, parent=self)
        else:
            messagebox.showerror("خطا", msg, parent=self)

    def _delete_selected(self):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف تجهیز نیستید.", parent=self)
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً حداقل یک تجهیز انتخاب کنید.")
            return
        names = [self.tree.item(i, "values")[1] for i in selected if self.tree.item(i, "values")]
        if not messagebox.askyesno("تایید حذف",
                                   f"آیا از حذف {len(names)} تجهیز اطمینان دارید؟\n"
                                   + "، ".join(names)):
            return
        errors = []
        for item in selected:
            vals = self.tree.item(item, "values")
            if vals:
                eq = self.equipment_repo.get_equipment_by_code(vals[0])
                if eq:
                    ok, msg = self.equipment_repo.delete_equipment(eq["id"])
                    if not ok:
                        errors.append(f"{eq['name']}: {msg.splitlines()[0]}")
        self._load_data()
        if errors:
            messagebox.showerror("خطا در حذف", "\n".join(errors), parent=self)

    # ========================================================================
    # Global keybinding handlers  (called by MainView)
    # ========================================================================
    def handle_enter(self):
        if not self.can_edit:
            return
        self._edit_or_add()

    def handle_delete(self):
        self._delete_selected()

    def handle_f2(self):
        if not self.can_edit:
            return
        self._edit_or_add()

    def handle_new(self):
        if not self.can_edit:
            return
        self._add_equipment()

    def ux_footer_spec(self):
        """Filters shown as removable chips under the table (views/ux.py)."""
        return {"filters": [("جستجو", self.search_var, ""), ("دسته", self.category_var, "همه"),
                            ("وضعیت", self.status_var, "همه")],
                "apply": self._load_data, "noun": "تجهیز"}

