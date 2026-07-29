# views/equipment_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from datetime import datetime
import jdatetime

from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

BG = GRAY_BG
CARD_BG = WHITE
PRIMARY = NAVY
DANGER = RED
SUCCESS = SUCCESS
TEXT = TEXT_DARK
SUBTLE = TEXT_LIGHT
BORDER = GRAY_BORDER

FONT_TITLE = FONT_TITLE
FONT_NORMAL = FONT_NORMAL
FONT_LABEL = FONT_HEADING

STATUS_FA = {
    "operational": "عملیاتی",
    "maintenance": "در تعمیر",
    "breakdown": "خراب",
    "inactive": "غیرفعال"
}

class EquipmentDialog(tk.Toplevel):
    def __init__(self, parent, equipment_repo, equipment=None):
        super().__init__(parent)
        self.equipment_repo = equipment_repo
        self.equipment = equipment
        self.result = None

        title = "ویرایش تجهیز" if equipment else "افزودن تجهیز جدید"
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)

        self._center_window(800, 800)
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
        header = tk.Frame(self, bg=PRIMARY, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        title = "ویرایش تجهیز" if self.equipment else "افزودن تجهیز جدید"
        tk.Label(header, text=title, font=FONT_TITLE, bg=PRIMARY, fg=WHITE).pack(pady=15)

        main_card = tk.Frame(self, bg=BORDER)
        main_card.pack(fill="both", expand=True, padx=20, pady=15)
        main_container = tk.Frame(main_card, bg=CARD_BG)
        main_container.pack(fill="both", expand=True, padx=1, pady=1)

        canvas = tk.Canvas(main_container, bg=CARD_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=CARD_BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.entries = {}

        # Row 1: code, name
        row1 = tk.Frame(scrollable_frame, bg=CARD_BG)
        row1.pack(fill="x", pady=5, padx=10)
        self._create_field(row1, "code", "کد تجهیز *", width=30, side="right")
        self._create_field(row1, "name", "نام تجهیز *", width=30, side="left")

        # Row 2: category + manufacturer
        row2 = tk.Frame(scrollable_frame, bg=CARD_BG)
        row2.pack(fill="x", pady=5, padx=10)
        self._create_editable_combo(row2, "category", "دسته‌بندی *", self.equipment_repo.get_categories(), side="right")
        self._create_field(row2, "manufacturer", "سازنده", width=30, side="left")

        # Row 3: model, serial number
        row3 = tk.Frame(scrollable_frame, bg=CARD_BG)
        row3.pack(fill="x", pady=5, padx=10)
        self._create_field(row3, "model", "مدل", width=30, side="right")
        self._create_field(row3, "serial_number", "شماره سریال", width=30, side="left")

        # Row 4: location (editable combo) + installation date
        row4 = tk.Frame(scrollable_frame, bg=CARD_BG)
        row4.pack(fill="x", pady=5, padx=10)
        self._create_editable_combo(row4, "location", "موقعیت *", self.equipment_repo.get_locations(), side="right")
        self._create_date_field(row4, "installation_date", "تاریخ نصب", side="left")

        # Row 5: status
        row5 = tk.Frame(scrollable_frame, bg=CARD_BG)
        row5.pack(fill="x", pady=5, padx=10)
        self._create_combo(row5, "status", "وضعیت *", list(STATUS_FA.values()), side="right")

        # Dimensions (length, width, diameter)
        dim_frame = tk.Frame(scrollable_frame, bg=CARD_BG)
        dim_frame.pack(fill="x", pady=5, padx=10)
        self._create_field(dim_frame, "length", "طول (متر)", width=12, side="left")
        self._create_field(dim_frame, "width", "عرض (متر)", width=12, side="left")
        self._create_field(dim_frame, "diameter", "قطر (متر)", width=12, side="left")

        # (height, volume, weight)
        dim_frame2 = tk.Frame(scrollable_frame, bg=CARD_BG)
        dim_frame2.pack(fill="x", pady=5, padx=10)
        self._create_field(dim_frame2, "height", "ارتفاع (متر)", width=12, side="left")
        self._create_field(dim_frame2, "volume", "حجم (متر³)", width=12, side="left")
        self._create_field(dim_frame2, "weight", "وزن (کیلوگرم)", width=12, side="left")

        # specifications
        row8 = tk.Frame(scrollable_frame, bg=CARD_BG)
        row8.pack(fill="x", pady=5, padx=10)
        self._create_text_field(row8, "specifications", "مشخصات فنی", height=4)

        # notes
        row9 = tk.Frame(scrollable_frame, bg=CARD_BG)
        row9.pack(fill="x", pady=5, padx=10)
        self._create_text_field(row9, "notes", "توضیحات", height=3)

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=(5, 15))

        tk.Button(btn_frame, text="لغو", font=FONT_NORMAL,
                  bg=DANGER, fg=WHITE, relief="flat",
                  cursor="hand2", command=self.destroy,
                  padx=30, pady=10).pack(side="left", padx=5)

        tk.Button(btn_frame, text="ذخیره", font=FONT_NORMAL,
                  bg=SUCCESS, fg=WHITE, relief="flat",
                  cursor="hand2", command=self._save,
                  padx=30, pady=10).pack(side="right", padx=5)

    def _create_field(self, parent, key, label, width=40, side="right"):
        container = tk.Frame(parent, bg=CARD_BG)
        container.pack(side=side, fill="x", expand=True, padx=10)

        tk.Label(container, text=label, font=FONT_LABEL,
                 bg=CARD_BG, fg=TEXT, anchor="e").pack(anchor="e", pady=(0, 3))

        entry = tk.Entry(container, font=FONT_NORMAL, width=width,
                        relief="solid", bd=1, bg=WHITE, fg=TEXT)
        entry.pack(fill="x")
        self.entries[key] = entry

    def _create_editable_combo(self, parent, key, label, values, side="right"):
        container = tk.Frame(parent, bg=CARD_BG)
        container.pack(side=side, fill="x", expand=True, padx=10)

        tk.Label(container, text=label, font=FONT_LABEL,
                 bg=CARD_BG, fg=TEXT, anchor="e").pack(anchor="e", pady=(0, 3))

        combo = ttk.Combobox(container, font=FONT_NORMAL,
                             values=values, state="normal", width=37)
        combo.pack(fill="x")
        self.entries[key] = combo

    def _create_combo(self, parent, key, label, values, side="right"):
        container = tk.Frame(parent, bg=CARD_BG)
        container.pack(side=side, fill="x", expand=True, padx=10)

        tk.Label(container, text=label, font=FONT_LABEL,
                 bg=CARD_BG, fg=TEXT, anchor="e").pack(anchor="e", pady=(0, 3))

        combo = ttk.Combobox(container, font=FONT_NORMAL, values=values,
                            state="readonly", width=37)
        combo.pack(fill="x")
        if values:
            combo.current(0)
        self.entries[key] = combo

    def _create_date_field(self, parent, key, label, side="right"):
        container = tk.Frame(parent, bg=CARD_BG)
        container.pack(side=side, fill="x", expand=True, padx=10)

        tk.Label(container, text=label, font=FONT_LABEL,
                 bg=CARD_BG, fg=TEXT, anchor="e").pack(anchor="e", pady=(0, 3))

        date_frame = tk.Frame(container, bg=CARD_BG)
        date_frame.pack(fill="x")

        date_entry = DateEntry(date_frame, font=FONT_NORMAL, width=35,
                              background=PRIMARY, foreground=WHITE,
                              borderwidth=1, date_pattern='yyyy-mm-dd')
        date_entry.pack(side="right", fill="x", expand=True)

        jalali_label = tk.Label(date_frame, text="", font=FONT_LABEL,
                               bg=CARD_BG, fg=SUCCESS)
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
        container = tk.Frame(parent, bg=CARD_BG)
        container.pack(fill="x", padx=10, pady=5)

        tk.Label(container, text=label, font=FONT_LABEL,
                 bg=CARD_BG, fg=TEXT, anchor="e").pack(anchor="e", pady=(0, 3))

        text_frame = tk.Frame(container, relief="solid", bd=1, bg=WHITE)
        text_frame.pack(fill="x")

        text = tk.Text(text_frame, font=FONT_NORMAL, height=height,
                      wrap="word", relief="flat", bg=WHITE, fg=TEXT)
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
        self.entries["category"].set(category)

        self.entries["manufacturer"].insert(0, self.equipment.get("manufacturer", ""))
        self.entries["model"].insert(0, self.equipment.get("model", ""))
        self.entries["serial_number"].insert(0, self.equipment.get("serial_number", ""))

        # Location
        loc = self.equipment.get("location", "")
        self.entries["location"].set(loc)

        if self.equipment.get("installation_date"):
            try:
                date_obj = datetime.strptime(self.equipment["installation_date"], "%Y-%m-%d")
                self.entries["installation_date"].set_date(date_obj)
            except:
                pass

        status = self.equipment.get("status", "operational")
        status_fa = STATUS_FA.get(status, "عملیاتی")
        self.entries["status"].set(status_fa)

        for dim in ["length", "width", "diameter", "height", "volume", "weight"]:
            val = self.equipment.get(dim)
            if val is not None:
                self.entries[dim].insert(0, str(val))

        if self.equipment.get("specifications"):
            self.entries["specifications"].insert("1.0", self.equipment["specifications"])

        if self.equipment.get("notes"):
            self.entries["notes"].insert("1.0", self.equipment["notes"])

    def _save(self):
        code = self.entries["code"].get().strip()
        name = self.entries["name"].get().strip()
        category = self.entries["category"].get().strip()
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

        def parse_float(key):
            s = self.entries[key].get().strip()
            if s:
                try:
                    return float(s)
                except:
                    messagebox.showerror("خطا", f"مقدار '{key}' باید عدد باشد.", parent=self)
                    return None
            return None

        length = parse_float("length")
        width = parse_float("width")
        diameter = parse_float("diameter")
        height = parse_float("height")
        volume = parse_float("volume")
        weight = parse_float("weight")

        if self.equipment:
            success, msg = self.equipment_repo.update_equipment(
                self.equipment["id"],
                code, name, category,
                self.entries["manufacturer"].get().strip(),
                self.entries["model"].get().strip(),
                self.entries["serial_number"].get().strip(),
                location, installation_date, status_en,
                self.entries["specifications"].get("1.0", "end-1c").strip(),
                self.entries["notes"].get("1.0", "end-1c").strip(),
                length=length, width=width, diameter=diameter,
                height=height, volume=volume, weight=weight,
            )
        else:
            success, msg = self.equipment_repo.create_equipment(
                code, name, category,
                self.entries["manufacturer"].get().strip(),
                self.entries["model"].get().strip(),
                self.entries["serial_number"].get().strip(),
                location, installation_date, status_en,
                self.entries["specifications"].get("1.0", "end-1c").strip(),
                self.entries["notes"].get("1.0", "end-1c").strip(),
                length=length, width=width, diameter=diameter,
                height=height, volume=volume, weight=weight,
            )

        if success:
            self.result = True
            self.destroy()
        else:
            messagebox.showerror("خطا", msg, parent=self)