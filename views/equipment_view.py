"""
Equipment View - Equipment Management Interface
"""
import tkinter as tk
from tkinter import ttk, messagebox
from database.models import EquipmentStatus
from views.equipment_dialog import EquipmentDialog

BG = "#F0F4F8"
WHITE = "#FFFFFF"
PRIMARY = "#1A73E8"
TEXT = "#202124"
SUBTLE = "#5F6368"
BORDER = "#DADCE0"
SUCCESS = "#34A853"
WARNING = "#FBBC04"
DANGER = "#EA4335"

FONT_TITLE = ("Vazir", 14, "bold")
FONT_NORMAL = ("Vazir", 10)
FONT_SMALL = ("Vazir", 9)

STATUS_FA = {
    EquipmentStatus.OPERATIONAL.value: "عملیاتی",
    EquipmentStatus.MAINTENANCE.value: "در تعمیر",
    EquipmentStatus.BREAKDOWN.value: "خراب",
    EquipmentStatus.INACTIVE.value: "غیرفعال",
}

STATUS_COLOR = {
    EquipmentStatus.OPERATIONAL.value: SUCCESS,
    EquipmentStatus.MAINTENANCE.value: WARNING,
    EquipmentStatus.BREAKDOWN.value: DANGER,
    EquipmentStatus.INACTIVE.value: SUBTLE,
}


class EquipmentView(tk.Frame):
    def __init__(self, parent, equipment_repo, current_user):
        super().__init__(parent, bg=BG)
        self.equipment_repo = equipment_repo
        self.current_user = current_user
        self.is_admin = current_user["role"] == "admin"

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=30, pady=(30, 10))

        tk.Label(header, text="⚙️  مدیریت تجهیزات", font=FONT_TITLE,
                 bg=BG, fg=TEXT).pack(side="right")

        tk.Button(header, text="➕ افزودن تجهیز", font=FONT_NORMAL, bg=PRIMARY, fg=WHITE,
                  relief="flat", cursor="hand2", command=self._add_equipment,
                  padx=15, pady=8).pack(side="left", padx=5)

        stats_frame = tk.Frame(self, bg=BG)
        stats_frame.pack(fill="x", padx=30, pady=(0, 10))

        self.stat_labels = {}
        stats = [
            ("total", "کل تجهیزات", PRIMARY),
            ("operational", "عملیاتی", SUCCESS),
            ("maintenance", "در تعمیر", WARNING),
            ("breakdown", "خراب", DANGER),
        ]

        for key, label, color in stats:
            card = tk.Frame(stats_frame, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
            card.pack(side="right", padx=5, ipadx=15, ipady=10)
            tk.Label(card, text=label, font=FONT_SMALL, bg=WHITE, fg=SUBTLE).pack()
            lbl = tk.Label(card, text="0", font=("Vazir", 16, "bold"), bg=WHITE, fg=color)
            lbl.pack()
            self.stat_labels[key] = lbl

        toolbar = tk.Frame(self, bg=BG)
        toolbar.pack(fill="x", padx=30, pady=(0, 10))

        tk.Label(toolbar, text="جستجو:", font=FONT_NORMAL, bg=BG, fg=TEXT).pack(side="right", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *_: self._load_data())
        tk.Entry(toolbar, textvariable=self.search_var, font=FONT_NORMAL,
                 bg=WHITE, fg=TEXT, relief="solid", bd=1, width=25).pack(side="right", ipady=4)

        tk.Label(toolbar, text="دسته:", font=FONT_NORMAL, bg=BG, fg=TEXT).pack(side="right", padx=(15, 5))
        self.category_var = tk.StringVar(value="همه")
        self.category_combo = ttk.Combobox(toolbar, textvariable=self.category_var,
                                           font=FONT_NORMAL, state="readonly", width=15)
        self.category_combo.pack(side="right", ipady=2)
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self._load_data())

        tk.Label(toolbar, text="وضعیت:", font=FONT_NORMAL, bg=BG, fg=TEXT).pack(side="right", padx=(15, 5))
        self.status_var = tk.StringVar(value="همه")
        status_combo = ttk.Combobox(toolbar, textvariable=self.status_var,
                                    values=["همه"] + list(STATUS_FA.values()),
                                    font=FONT_NORMAL, state="readonly", width=12)
        status_combo.pack(side="right", ipady=2)
        status_combo.bind("<<ComboboxSelected>>", lambda e: self._load_data())

        table_frame = tk.Frame(self, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        table_frame.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        cols = ("code", "name", "category", "location", "status", "updated")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=15)

        headers = [
            ("code", "کد", 100),
            ("name", "نام تجهیز", 200),
            ("category", "دسته", 120),
            ("location", "موقعیت", 150),
            ("status", "وضعیت", 100),
            ("updated", "آخرین بروزرسانی", 150),
        ]

        for col, text, width in headers:
            self.tree.heading(col, text=text, command=lambda c=col: self._sort_column(c))
            self.tree.column(col, width=width, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="right", fill="both", expand=True)
        scrollbar.pack(side="left", fill="y")

        self.tree.bind("<Double-1>", lambda e: self._edit_equipment())

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=30, pady=(0, 20))

        tk.Button(btn_frame, text="✏️ ویرایش", font=FONT_NORMAL, bg=PRIMARY, fg=WHITE,
                  relief="flat", cursor="hand2", command=self._edit_equipment,
                  padx=15, pady=8).pack(side="right", padx=5)

        tk.Button(btn_frame, text="🔄 تغییر وضعیت", font=FONT_NORMAL, bg=WARNING, fg=WHITE,
                  relief="flat", cursor="hand2", command=self._change_status,
                  padx=15, pady=8).pack(side="right", padx=5)

        if self.is_admin:
            tk.Button(btn_frame, text="🗑️ حذف", font=FONT_NORMAL, bg=DANGER, fg=WHITE,
                      relief="flat", cursor="hand2", command=self._delete_equipment,
                      padx=15, pady=8).pack(side="right", padx=5)

        tk.Button(header, text="📤 خروجی Excel / PDF", font=FONT_NORMAL,
                  bg="#34A853", fg=WHITE, relief="flat", cursor="hand2",
                  command=self._export, padx=15, pady=8).pack(side="left", padx=5)


    def _load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self.search_var.get().strip()
        category = self.category_var.get()
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
            self.tree.insert("", "end", values=(
                eq["code"],
                eq["name"],
                eq["category"],
                eq["location"],
                status_text,
                eq["updated_at"]
            ), tags=(eq["status"],))

        for status, color in STATUS_COLOR.items():
            self.tree.tag_configure(status, foreground=color)

        self._update_stats()
        self._update_category_filter()

    def _update_stats(self):
        stats = self.equipment_repo.get_stats()
        self.stat_labels["total"].config(text=str(stats["total"]))
        self.stat_labels["operational"].config(text=str(stats["operational"]))
        self.stat_labels["maintenance"].config(text=str(stats["maintenance"]))
        self.stat_labels["breakdown"].config(text=str(stats["breakdown"]))

    def _update_category_filter(self):
        categories = ["همه"] + self.equipment_repo.get_categories()
        self.category_combo["values"] = categories

    def _sort_column(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        items.sort(reverse=False)

        for index, (val, k) in enumerate(items):
            self.tree.move(k, "", index)

    def _get_selected_equipment(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("هشدار", "لطفاً یک تجهیز انتخاب کنید.", parent=self)
            return None

        values = self.tree.item(selected[0], "values")
        code = values[0]
        return self.equipment_repo.get_equipment_by_code(code)

    def _add_equipment(self):
        dialog = EquipmentDialog(self, self.equipment_repo)
        self.wait_window(dialog)
        if dialog.result:
            self._load_data()
            messagebox.showinfo("موفق", "تجهیز با موفقیت اضافه شد.", parent=self)

    def _edit_equipment(self):
        equipment = self._get_selected_equipment()
        if not equipment:
            return

        dialog = EquipmentDialog(self, self.equipment_repo, equipment)
        self.wait_window(dialog)
        if dialog.result:
            self._load_data()
            messagebox.showinfo("موفق", "تجهیز با موفقیت ویرایش شد.", parent=self)

    def _change_status(self):
        equipment = self._get_selected_equipment()
        if not equipment:
            return

        status_dialog = tk.Toplevel(self)
        status_dialog.title("تغییر وضعیت")
        status_dialog.configure(bg=WHITE)
        status_dialog.resizable(False, False)
        status_dialog.geometry("350x200")

        tk.Label(status_dialog, text=f"تجهیز: {equipment['name']}", font=FONT_NORMAL,
                 bg=WHITE, fg=TEXT).pack(pady=(20, 10))

        tk.Label(status_dialog, text="وضعیت جدید:", font=FONT_NORMAL,
                 bg=WHITE, fg=TEXT).pack(pady=(10, 5))

        status_var = tk.StringVar(value=STATUS_FA.get(equipment["status"], ""))
        status_combo = ttk.Combobox(status_dialog, textvariable=status_var,
                                    values=list(STATUS_FA.values()),
                                    font=FONT_NORMAL, state="readonly", width=20)
        status_combo.pack(pady=5)

        def save_status():
            new_status_fa = status_var.get()
            new_status_en = next((k for k, v in STATUS_FA.items() if v == new_status_fa), None)
            if not new_status_en:
                messagebox.showerror("خطا", "وضعیت نامعتبر است.", parent=status_dialog)
                return

            success, msg = self.equipment_repo.update_status(equipment["id"], new_status_en)
            if success:
                status_dialog.destroy()
                self._load_data()
                messagebox.showinfo("موفق", msg, parent=self)
            else:
                messagebox.showerror("خطا", msg, parent=status_dialog)

        tk.Button(status_dialog, text="ذخیره", font=FONT_NORMAL, bg=PRIMARY, fg=WHITE,
                  relief="flat", cursor="hand2", command=save_status,
                  padx=20, pady=8).pack(pady=20)

        status_dialog.transient(self)
        status_dialog.grab_set()

    def _export(self):
        from views.export_dialog import run_equipment_export
        selected = self._get_selected_equipment()
        # Build current visible list from tree
        eq_list = self.equipment_repo.get_all_equipment()
        run_equipment_export(self, eq_list, selected_equipment=selected)

    def _delete_equipment(self):
        equipment = self._get_selected_equipment()
        if not equipment:
            return

        confirm = messagebox.askyesno(
            "تایید حذف",
            f"آیا از حذف تجهیز '{equipment['name']}' اطمینان دارید؟\n\nاین عملیات غیرقابل بازگشت است.",
            parent=self
        )

        if confirm:
            success, msg = self.equipment_repo.delete_equipment(equipment["id"])
            if success:
                self._load_data()
                messagebox.showinfo("موفق", msg, parent=self)
            else:
                messagebox.showerror("خطا", msg, parent=self)