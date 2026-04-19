import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from datetime import datetime
import jdatetime

WHITE = "#FFFFFF"
BG = "#F5F5F5"
PRIMARY = "#1A73E8"
DANGER = "#DC3545"
SUCCESS = "#28A745"
TEXT = "#202124"
BORDER = "#DADCE0"

FONT_TITLE = ("Vazir", 12, "bold")
FONT_NORMAL = ("Vazir", 10)
FONT_LABEL = ("Vazir", 9)

STATUS_FA = {
    "operational": "عملیاتی",
    "maintenance": "در تعمیر",
    "breakdown": "خراب",
    "inactive": "غیرفعال"
}

CATEGORIES = [
    "پاستوریزاتور",
    "همزن",
    "تانک ذخیره",
    "کمپرسور",
    "چیلر",
    "بویلر",
    "پمپ",
    "کانوایر",
    "بسته‌بندی",
    "سایر"
]


class EquipmentDialog(tk.Toplevel):
    def __init__(self, parent, equipment_repo, equipment=None):
        super().__init__(parent)
        self.equipment_repo = equipment_repo
        self.equipment = equipment
        self.result = None

        title = "ویرایش تجهیز" if equipment else "افزودن تجهیز جدید"
        self.title(title)
        self.configure(bg=WHITE)
        self.resizable(False, False)

        self._center_window(700, 650)
        self._build_ui()

        if equipment:
            self._populate_fields()

        self.transient(parent)
        self.grab_set()

    def _center_window(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=PRIMARY, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        title = "ویرایش تجهیز" if self.equipment else "افزودن تجهیز جدید"
        tk.Label(header, text=title, font=("Vazir", 14, "bold"),
                 bg=PRIMARY, fg=WHITE).pack(pady=15)

        # Main container with scrollbar
        main_container = tk.Frame(self, bg=WHITE)
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        canvas = tk.Canvas(main_container, bg=WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=WHITE)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Form fields
        self.entries = {}

        # Row 1: کد و نام
        row1 = tk.Frame(scrollable_frame, bg=WHITE)
        row1.pack(fill="x", pady=5)

        self._create_field(row1, "code", "کد تجهیز *", width=30, side="right")
        self._create_field(row1, "name", "نام تجهیز *", width=30, side="left")

        # Row 2: دسته‌بندی و سازنده
        row2 = tk.Frame(scrollable_frame, bg=WHITE)
        row2.pack(fill="x", pady=5)

        self._create_combo(row2, "category", "دسته‌بندی *", CATEGORIES, side="right")
        self._create_field(row2, "manufacturer", "سازنده", width=30, side="left")

        # Row 3: مدل و شماره سریال
        row3 = tk.Frame(scrollable_frame, bg=WHITE)
        row3.pack(fill="x", pady=5)

        self._create_field(row3, "model", "مدل", width=30, side="right")
        self._create_field(row3, "serial_number", "شماره سریال", width=30, side="left")

        # Row 4: موقعیت و تاریخ نصب
        row4 = tk.Frame(scrollable_frame, bg=WHITE)
        row4.pack(fill="x", pady=5)

        self._create_field(row4, "location", "موقعیت *", width=30, side="right")
        self._create_date_field(row4, "installation_date", "تاریخ نصب", side="left")

        # Row 5: وضعیت
        row5 = tk.Frame(scrollable_frame, bg=WHITE)
        row5.pack(fill="x", pady=5)

        self._create_combo(row5, "status", "وضعیت *", list(STATUS_FA.values()), side="right")

        # Row 6: مشخصات فنی
        row6 = tk.Frame(scrollable_frame, bg=WHITE)
        row6.pack(fill="x", pady=5)

        self._create_text_field(row6, "specifications", "مشخصات فنی", height=4)

        # Row 7: یادداشت
        row7 = tk.Frame(scrollable_frame, bg=WHITE)
        row7.pack(fill="x", pady=5)

        self._create_text_field(row7, "notes", "یادداشت", height=3)

        # Buttons
        btn_frame = tk.Frame(self, bg=WHITE)
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        tk.Button(btn_frame, text="لغو", font=FONT_NORMAL,
                  bg=DANGER, fg=WHITE, relief="flat",
                  cursor="hand2", command=self.destroy,
                  padx=30, pady=10).pack(side="left", padx=5)

        tk.Button(btn_frame, text="ذخیره", font=FONT_NORMAL,
                  bg=SUCCESS, fg=WHITE, relief="flat",
                  cursor="hand2", command=self._save,
                  padx=30, pady=10).pack(side="right", padx=5)

    def _create_field(self, parent, key, label, width=40, side="right"):
        container = tk.Frame(parent, bg=WHITE)
        container.pack(side=side, fill="x", expand=True, padx=10)

        tk.Label(container, text=label, font=FONT_LABEL,
                 bg=WHITE, fg=TEXT, anchor="e").pack(anchor="e", pady=(0, 3))

        entry = tk.Entry(container, font=FONT_NORMAL, width=width,
                        relief="solid", bd=1)
        entry.pack(fill="x")
        self.entries[key] = entry

    def _create_combo(self, parent, key, label, values, side="right"):
        container = tk.Frame(parent, bg=WHITE)
        container.pack(side=side, fill="x", expand=True, padx=10)

        tk.Label(container, text=label, font=FONT_LABEL,
                 bg=WHITE, fg=TEXT, anchor="e").pack(anchor="e", pady=(0, 3))

        combo = ttk.Combobox(container, font=FONT_NORMAL, values=values,
                            state="readonly", width=37)
        combo.pack(fill="x")
        if values:
            combo.current(0)
        self.entries[key] = combo

    def _create_date_field(self, parent, key, label, side="right"):
        container = tk.Frame(parent, bg=WHITE)
        container.pack(side=side, fill="x", expand=True, padx=10)

        tk.Label(container, text=label, font=FONT_LABEL,
                 bg=WHITE, fg=TEXT, anchor="e").pack(anchor="e", pady=(0, 3))

        # تاریخ شمسی با تقویم
        date_frame = tk.Frame(container, bg=WHITE)
        date_frame.pack(fill="x")

        date_entry = DateEntry(date_frame, font=FONT_NORMAL, width=35,
                              background=PRIMARY, foreground=WHITE,
                              borderwidth=1, date_pattern='yyyy-mm-dd',
                              locale='fa_IR')
        date_entry.pack(side="right", fill="x", expand=True)

        # نمایش تاریخ شمسی
        jalali_label = tk.Label(date_frame, text="", font=FONT_LABEL,
                               bg=WHITE, fg=TEXT)
        jalali_label.pack(side="left", padx=5)

        def update_jalali(event=None):
            try:
                greg_date = date_entry.get_date()
                jalali_date = jdatetime.date.fromgregorian(date=greg_date)
                jalali_label.config(text=jalali_date.strftime('%Y/%m/%d'))
            except:
                jalali_label.config(text="")

        date_entry.bind("<<DateEntrySelected>>", update_jalali)
        update_jalali()

        self.entries[key] = date_entry

    def _create_text_field(self, parent, key, label, height=3):
        container = tk.Frame(parent, bg=WHITE)
        container.pack(fill="x", padx=10, pady=5)

        tk.Label(container, text=label, font=FONT_LABEL,
                 bg=WHITE, fg=TEXT, anchor="e").pack(anchor="e", pady=(0, 3))

        text_frame = tk.Frame(container, relief="solid", bd=1)
        text_frame.pack(fill="x")

        text = tk.Text(text_frame, font=FONT_NORMAL, height=height,
                      wrap="word", relief="flat")
        text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(text_frame, command=text.yview)
        scrollbar.pack(side="right", fill="y")
        text.config(yscrollcommand=scrollbar.set)

        self.entries[key] = text

    def _populate_fields(self):
        if not self.equipment:
            return

        self.entries["code"].insert(0, self.equipment.get("code", ""))
        self.entries["code"].config(state="disabled")

        self.entries["name"].insert(0, self.equipment.get("name", ""))

        category = self.equipment.get("category", "")
        if category in CATEGORIES:
            self.entries["category"].set(category)

        self.entries["manufacturer"].insert(0, self.equipment.get("manufacturer", ""))
        self.entries["model"].insert(0, self.equipment.get("model", ""))
        self.entries["serial_number"].insert(0, self.equipment.get("serial_number", ""))
        self.entries["location"].insert(0, self.equipment.get("location", ""))

        if self.equipment.get("installation_date"):
            try:
                date_obj = datetime.strptime(self.equipment["installation_date"], "%Y-%m-%d")
                self.entries["installation_date"].set_date(date_obj)
            except:
                pass

        status = self.equipment.get("status", "operational")
        status_fa = STATUS_FA.get(status, "عملیاتی")
        self.entries["status"].set(status_fa)

        if self.equipment.get("specifications"):
            self.entries["specifications"].insert("1.0", self.equipment["specifications"])

        if self.equipment.get("notes"):
            self.entries["notes"].insert("1.0", self.equipment["notes"])

    def _save(self):
        code = self.entries["code"].get().strip()
        name = self.entries["name"].get().strip()
        category = self.entries["category"].get()
        location = self.entries["location"].get().strip()
        status_fa = self.entries["status"].get()

        if not all([code, name, category, location, status_fa]):
            messagebox.showerror("خطا", "لطفاً فیلدهای ضروری را پر کنید.", parent=self)
            return

        status_en = next((k for k, v in STATUS_FA.items() if v == status_fa), "operational")

        try:
            installation_date = datetime.strptime(
                self.entries["installation_date"].get_date().strftime("%Y-%m-%d"), "%Y-%m-%d"
            )
        except:
            installation_date = None

        if self.equipment:
            success, msg = self.equipment_repo.update_equipment(
                self.equipment["id"],
                code,
                name,
                category,
                self.entries["manufacturer"].get().strip(),
                self.entries["model"].get().strip(),
                self.entries["serial_number"].get().strip(),
                location,
                installation_date,
                status_en,
                self.entries["specifications"].get("1.0", "end-1c").strip(),
                self.entries["notes"].get("1.0", "end-1c").strip()
            )
        else:
            success, msg = self.equipment_repo.create_equipment(
                code,
                name,
                category,
                self.entries["manufacturer"].get().strip(),
                self.entries["model"].get().strip(),
                self.entries["serial_number"].get().strip(),
                location,
                installation_date,
                status_en,
                self.entries["specifications"].get("1.0", "end-1c").strip(),
                self.entries["notes"].get("1.0", "end-1c").strip()
            )

        if success:
            self.result = True
            self.destroy()
        else:
            messagebox.showerror("خطا", msg, parent=self)
