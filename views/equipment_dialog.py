# views/equipment_dialog.py

import tkinter as tk
from tkinter import ttk, messagebox
from views.ux import field_error
from datetime import datetime

from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, FONT_TITLE,
    FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

from views.jalali_date_entry import JalaliDateEntry


# ============================================================
# COLORS
# ============================================================

BG = GRAY_BG
CARD_BG = WHITE
PRIMARY = NAVY
PRIMARY_LIGHT = NAVY_LIGHT
DANGER = RED
SUCCESS_COLOR = SUCCESS

TEXT = TEXT_DARK
SUBTLE = TEXT_LIGHT
BORDER = GRAY_BORDER

FIELD_BG = "#FFFFFF"
SECTION_BG = "#F7F8FA"
DISABLED_BG = "#EEF1F4"


# ============================================================
# STATUS
# ============================================================

STATUS_FA = {
    "operational": "عملیاتی",
    "maintenance": "در تعمیر",
    "breakdown": "خراب",
    "inactive": "غیرفعال",
}


class EquipmentDialog(tk.Toplevel):

    MIN_WIDTH = 850
    MIN_HEIGHT = 650

    def __init__(self, parent, equipment_repo, equipment=None):
        super().__init__(parent)

        self.parent = parent
        self.equipment_repo = equipment_repo
        self.equipment = equipment
        self.result = None

        title = "ویرایش تجهیز" if equipment else "افزودن تجهیز جدید"

        self.title(title)
        self.configure(bg=BG)

        # ----------------------------------------------------
        # Window behavior
        # ----------------------------------------------------

        self.resizable(True, True)
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)

        self.transient(parent)
        self.grab_set()

        self._center_window(900, 720)

        self._build_ui()

        if self.equipment:
            self._populate_fields()

        # ----------------------------------------------------
        # Keyboard shortcuts
        # ----------------------------------------------------

        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-s>", lambda e: self._save())

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # ========================================================
    # WINDOW
    # ========================================================

    def _center_window(self, width, height):

        self.update_idletasks()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        width = min(width, screen_w - 80)
        height = min(height, screen_h - 100)

        x = (screen_w - width) // 2
        y = (screen_h - height) // 2

        self.geometry(f"{width}x{height}+{x}+{y}")

    # ========================================================
    # MAIN UI
    # ========================================================

    def _build_ui(self):

        self._build_header()
        self._build_content()
        self._build_buttons()

    # ========================================================
    # HEADER
    # ========================================================

    def _build_header(self):

        header = tk.Frame(
            self,
            bg=PRIMARY,
            height=68
        )

        header.pack(fill="x")
        header.pack_propagate(False)

        # Right side
        right = tk.Frame(header, bg=PRIMARY)
        right.pack(side="right", padx=24, fill="y")

        icon = "✏️" if self.equipment else "⚙️"

        tk.Label(
            right,
            text=icon,
            font=("Tahoma", 20),
            bg=PRIMARY,
            fg=WHITE
        ).pack(side="right", pady=16)

        text_frame = tk.Frame(right, bg=PRIMARY)
        text_frame.pack(side="right", padx=(0, 10), fill="y")

        title = "ویرایش تجهیز" if self.equipment else "افزودن تجهیز جدید"

        tk.Label(
            text_frame,
            text=title,
            font=FONT_TITLE,
            bg=PRIMARY,
            fg=WHITE
        ).pack(anchor="e", pady=(13, 0))

        subtitle = (
            "ویرایش اطلاعات و مشخصات تجهیز"
            if self.equipment
            else "اطلاعات پایه و مشخصات تجهیز را وارد کنید"
        )

        tk.Label(
            text_frame,
            text=subtitle,
            font=FONT_SMALL,
            bg=PRIMARY,
            fg=WHITE
        ).pack(anchor="e")

    # ========================================================
    # CONTENT
    # ========================================================

    def _build_content(self):

        outer = tk.Frame(
            self,
            bg=BORDER
        )

        outer.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=(14, 10)
        )

        card = tk.Frame(
            outer,
            bg=CARD_BG
        )

        card.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1
        )

        # ----------------------------------------------------
        # Canvas
        # ----------------------------------------------------

        self.canvas = tk.Canvas(
            card,
            bg=CARD_BG,
            highlightthickness=0,
            bd=0
        )

        scrollbar = ttk.Scrollbar(
            card,
            orient="vertical",
            command=self.canvas.yview
        )

        self.scrollable_frame = tk.Frame(
            self.canvas,
            bg=CARD_BG
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw"
        )

        self.scrollable_frame.bind(
            "<Configure>",
            self._on_frame_configure
        )

        self.canvas.bind(
            "<Configure>",
            self._on_canvas_configure
        )

        self.canvas.configure(
            yscrollcommand=scrollbar.set
        )

        self.canvas.pack(
            side="left",
            fill="both",
            expand=True
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        # Mouse wheel
        # FIX: use a scoped binding instead of bind_all so this dialog
        # does not steal the mouse-wheel from every other widget in the
        # application. Also route wheel events from child widgets.
        self.canvas.bind(
            "<MouseWheel>",
            self._on_mousewheel,
            add="+"
        )
        self.canvas.bind(
            "<Button-4>",
            lambda e: self.canvas.yview_scroll(-3, "units"),
            add="+"
        )
        self.canvas.bind(
            "<Button-5>",
            lambda e: self.canvas.yview_scroll(3, "units"),
            add="+"
        )

        # ----------------------------------------------------
        # Fields
        # ----------------------------------------------------

        self.entries = {}

        self._build_basic_section()
        self._build_dimensions_section()
        self._build_description_section()

        # FIX: after all widgets exist, route their wheel events to
        # this dialog's canvas.
        self.after_idle(
            lambda: self._bind_mousewheel_to_children(self.scrollable_frame)
        )

    # ========================================================
    # SCROLL
    # ========================================================

    def _on_frame_configure(self, event=None):

        self.canvas.configure(
            scrollregion=self.canvas.bbox("all")
        )

    def _on_canvas_configure(self, event):

        self.canvas.itemconfigure(
            self.canvas_window,
            width=event.width
        )

    def _on_mousewheel(self, event):

        try:
            self.canvas.yview_scroll(
                int(-1 * (event.delta / 120)),
                "units"
            )
        except Exception:
            pass

    # --------------------------------------------------------
    # FIX: propagate mousewheel from all children to the canvas.
    # Text and Listbox widgets are skipped so they keep their own
    # internal scrolling.
    # --------------------------------------------------------

    def _bind_mousewheel_to_children(self, widget):

        if isinstance(widget, (tk.Text, tk.Listbox)):
            return

        try:
            widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
            widget.bind(
                "<Button-4>",
                lambda e: self.canvas.yview_scroll(-3, "units"),
                add="+"
            )
            widget.bind(
                "<Button-5>",
                lambda e: self.canvas.yview_scroll(3, "units"),
                add="+"
            )
        except Exception:
            pass

        for child in widget.winfo_children():
            self._bind_mousewheel_to_children(child)

    # ========================================================
    # SECTION
    # ========================================================

    def _create_section(self, title, subtitle=None):

        wrapper = tk.Frame(
            self.scrollable_frame,
            bg=CARD_BG
        )

        wrapper.pack(
            fill="x",
            padx=22,
            pady=(18, 6)
        )

        header = tk.Frame(
            wrapper,
            bg=CARD_BG
        )

        header.pack(
            fill="x"
        )

        tk.Label(
            header,
            text=title,
            font=FONT_HEADING,
            bg=CARD_BG,
            fg=TEXT
        ).pack(
            side="right"
        )

        if subtitle:
            tk.Label(
                header,
                text=subtitle,
                font=FONT_SMALL,
                bg=CARD_BG,
                fg=SUBTLE
            ).pack(
                side="right",
                padx=(0, 10)
            )

        tk.Frame(
            wrapper,
            bg=BORDER,
            height=1
        ).pack(
            fill="x",
            pady=(8, 12)
        )

        body = tk.Frame(
            wrapper,
            bg=CARD_BG
        )

        body.pack(
            fill="x"
        )

        return body

    # ========================================================
    # BASIC INFORMATION
    # ========================================================

    def _build_basic_section(self):

        body = self._create_section(
            "اطلاعات اصلی",
            "فیلدهای دارای * الزامی هستند"
        )

        # 2 columns
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        # Row 0
        self._create_field_grid(
            body,
            "code",
            "کد تجهیز *",
            row=0,
            column=1
        )

        self._create_field_grid(
            body,
            "name",
            "نام تجهیز *",
            row=0,
            column=0
        )

        # Row 1
        self._create_editable_combo_grid(
            body,
            "category",
            "دسته‌بندی *",
            self.equipment_repo.get_categories(),
            row=1,
            column=1
        )

        self._create_field_grid(
            body,
            "manufacturer",
            "سازنده",
            row=1,
            column=0
        )

        # Row 2
        self._create_field_grid(
            body,
            "model",
            "مدل",
            row=2,
            column=1
        )

        self._create_field_grid(
            body,
            "serial_number",
            "شماره سریال",
            row=2,
            column=0
        )

        # Row 3
        self._create_editable_combo_grid(
            body,
            "location",
            "موقعیت *",
            self.equipment_repo.get_locations(),
            row=3,
            column=1
        )

        self._create_date_field_grid(
            body,
            "installation_date",
            "تاریخ نصب",
            row=3,
            column=0
        )

        # Row 4
        self._create_combo_grid(
            body,
            "status",
            "وضعیت *",
            list(STATUS_FA.values()),
            row=4,
            column=1
        )

        # Empty second column intentionally
        spacer = tk.Frame(
            body,
            bg=CARD_BG
        )

        spacer.grid(
            row=4,
            column=0,
            sticky="ew",
            padx=8,
            pady=7
        )

    # ========================================================
    # DIMENSIONS
    # ========================================================

    def _build_dimensions_section(self):

        body = self._create_section(
            "ابعاد و مشخصات فیزیکی",
            "در صورت نیاز وارد کنید"
        )

        for column in range(3):
            body.columnconfigure(
                column,
                weight=1
            )

        fields = [
            ("length", "طول (متر)"),
            ("width", "عرض (متر)"),
            ("height", "ارتفاع (متر)"),
            ("diameter", "قطر (متر)"),
            ("volume", "حجم (متر³)"),
            ("weight", "وزن (کیلوگرم)")
        ]

        for index, (key, label) in enumerate(fields):

            row = index // 3
            column = index % 3

            self._create_field_grid(
                body,
                key,
                label,
                row=row,
                column=column,
                padx=8
            )

    # ========================================================
    # DESCRIPTION
    # ========================================================

    def _build_description_section(self):

        body = self._create_section(
            "توضیحات",
            "اطلاعات تکمیلی تجهیز"
        )

        self._create_text_field_grid(
            body,
            "specifications",
            "مشخصات فنی",
            height=5
        )

        self._create_text_field_grid(
            body,
            "notes",
            "توضیحات",
            height=4
        )

        # Bottom spacing
        tk.Frame(
            self.scrollable_frame,
            height=10,
            bg=CARD_BG
        ).pack(fill="x")

    # ========================================================
    # FIELD HELPERS
    # ========================================================

    def _create_field_grid(
        self,
        parent,
        key,
        label,
        row,
        column,
        padx=8
    ):

        container = tk.Frame(
            parent,
            bg=CARD_BG
        )

        container.grid(
            row=row,
            column=column,
            sticky="ew",
            padx=padx,
            pady=7
        )

        container.columnconfigure(
            0,
            weight=1
        )

        tk.Label(
            container,
            text=label,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            anchor="e"
        ).pack(
            fill="x",
            pady=(0, 4)
        )

        entry = tk.Entry(
            container,
            font=FONT_NORMAL,
            relief="solid",
            bd=1,
            bg=FIELD_BG,
            fg=TEXT,
            insertbackground=TEXT
        )

        entry.pack(
            fill="x",
            ipady=6
        )

        self.entries[key] = entry

    # ========================================================

    def _create_editable_combo_grid(
        self,
        parent,
        key,
        label,
        values,
        row,
        column,
        padx=8
    ):

        container = tk.Frame(
            parent,
            bg=CARD_BG
        )

        container.grid(
            row=row,
            column=column,
            sticky="ew",
            padx=padx,
            pady=7
        )

        tk.Label(
            container,
            text=label,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            anchor="e"
        ).pack(
            fill="x",
            pady=(0, 4)
        )

        combo = ttk.Combobox(
            container,
            font=FONT_NORMAL,
            values=values,
            state="normal"
        )

        combo.pack(
            fill="x",
            ipady=4
        )

        self.entries[key] = combo

    # ========================================================

    def _create_combo_grid(
        self,
        parent,
        key,
        label,
        values,
        row,
        column,
        padx=8
    ):

        container = tk.Frame(
            parent,
            bg=CARD_BG
        )

        container.grid(
            row=row,
            column=column,
            sticky="ew",
            padx=padx,
            pady=7
        )

        tk.Label(
            container,
            text=label,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            anchor="e"
        ).pack(
            fill="x",
            pady=(0, 4)
        )

        combo = ttk.Combobox(
            container,
            font=FONT_NORMAL,
            values=values,
            state="readonly"
        )

        combo.pack(
            fill="x",
            ipady=4
        )

        if values:
            combo.current(0)

        self.entries[key] = combo

    # ========================================================

    def _create_date_field_grid(
        self,
        parent,
        key,
        label,
        row,
        column,
        padx=8
    ):

        container = tk.Frame(
            parent,
            bg=CARD_BG
        )

        container.grid(
            row=row,
            column=column,
            sticky="ew",
            padx=padx,
            pady=7
        )

        tk.Label(
            container,
            text=label,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            anchor="e"
        ).pack(
            fill="x",
            pady=(0, 4)
        )

        date_entry = JalaliDateEntry(
            container,
            width=20,
            font=("Tahoma", 10)
        )

        date_entry.pack(
            fill="x",
            ipady=2
        )

        self.entries[key] = date_entry

    # ========================================================

    def _create_text_field_grid(
        self,
        parent,
        key,
        label,
        height=4
    ):

        container = tk.Frame(
            parent,
            bg=CARD_BG
        )

        container.pack(
            fill="x",
            pady=7
        )

        tk.Label(
            container,
            text=label,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            anchor="e"
        ).pack(
            fill="x",
            pady=(0, 4)
        )

        text_frame = tk.Frame(
            container,
            bg=WHITE,
            relief="solid",
            bd=1
        )

        text_frame.pack(
            fill="x"
        )

        text = tk.Text(
            text_frame,
            font=FONT_NORMAL,
            height=height,
            wrap="word",
            relief="flat",
            bd=0,
            bg=WHITE,
            fg=TEXT,
            insertbackground=TEXT
        )

        scrollbar = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=text.yview
        )

        text.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        text.pack(
            side="left",
            fill="both",
            expand=True,
            padx=6,
            pady=5
        )

        self.entries[key] = text

    # ========================================================
    # BUTTON BAR
    # ========================================================

    def _build_buttons(self):

        separator = tk.Frame(
            self,
            bg=BORDER,
            height=1
        )

        separator.pack(
            fill="x"
        )

        button_bar = tk.Frame(
            self,
            bg=BG,
            height=70
        )

        button_bar.pack(
            fill="x"
        )

        button_bar.pack_propagate(False)

        # ----------------------------------------------------
        # Left: cancel
        # ----------------------------------------------------

        cancel_btn = tk.Button(
            button_bar,
            text="لغو",
            font=FONT_NORMAL,
            bg=DANGER,
            fg=WHITE,
            activebackground=DANGER,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            width=10,
            pady=8,
            command=self.destroy
        )

        cancel_btn.pack(
            side="left",
            padx=(18, 6),
            pady=14
        )

        # ----------------------------------------------------
        # Right: save
        # ----------------------------------------------------

        save_btn = tk.Button(
            button_bar,
            text="💾  ذخیره",
            font=FONT_NORMAL,
            bg=SUCCESS_COLOR,
            fg=WHITE,
            activebackground=SUCCESS_COLOR,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            width=14,
            pady=8,
            command=self._save
        )

        save_btn.pack(
            side="right",
            padx=(6, 18),
            pady=14
        )

        # ----------------------------------------------------
        # Hint
        # ----------------------------------------------------

        tk.Label(
            button_bar,
            text="Ctrl+S: ذخیره   |   Esc: لغو",
            font=FONT_SMALL,
            bg=BG,
            fg=SUBTLE
        ).pack(
            side="left",
            padx=15
        )

    # ========================================================
    # POPULATE
    # ========================================================

    def _populate_fields(self):

        if not self.equipment:
            return

        # Code
        self.entries["code"].insert(
            0,
            self.equipment.get("code", "")
        )

        self.entries["code"].config(
            state="disabled",
            disabledbackground=DISABLED_BG,
            disabledforeground=TEXT
        )

        # Basic fields
        self.entries["name"].insert(
            0,
            self.equipment.get("name", "")
        )

        self.entries["category"].set(
            self.equipment.get("category", "")
        )

        self.entries["manufacturer"].insert(
            0,
            self.equipment.get("manufacturer", "")
        )

        self.entries["model"].insert(
            0,
            self.equipment.get("model", "")
        )

        self.entries["serial_number"].insert(
            0,
            self.equipment.get("serial_number", "")
        )

        self.entries["location"].set(
            self.equipment.get("location", "")
        )

        # Installation date
        installation_date = self.equipment.get(
            "installation_date"
        )

        if installation_date:

            try:

                if isinstance(
                    installation_date,
                    str
                ):
                    date_obj = datetime.strptime(
                        installation_date[:10],
                        "%Y-%m-%d"
                    )
                else:
                    date_obj = installation_date

                self.entries[
                    "installation_date"
                ].set_date(date_obj)

            except Exception:
                pass

        # Status
        status = self.equipment.get(
            "status",
            "operational"
        )

        self.entries["status"].set(
            STATUS_FA.get(
                status,
                "عملیاتی"
            )
        )

        # Dimensions
        for key in [
            "length",
            "width",
            "height",
            "diameter",
            "volume",
            "weight"
        ]:

            value = self.equipment.get(key)

            if value is not None:

                self.entries[key].insert(
                    0,
                    str(value)
                )

        # Text fields
        specifications = self.equipment.get(
            "specifications"
        )

        if specifications:
            self.entries[
                "specifications"
            ].insert(
                "1.0",
                specifications
            )

        notes = self.equipment.get(
            "notes"
        )

        if notes:
            self.entries[
                "notes"
            ].insert(
                "1.0",
                notes
            )

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_required(self):

        required = {
            "code": "کد تجهیز",
            "name": "نام تجهیز",
            "category": "دسته‌بندی",
            "location": "موقعیت",
            "status": "وضعیت",
        }

        missing = []

        for key, label in required.items():

            value = self.entries[key].get().strip()

            if not value:
                missing.append(label)

        if missing:

            # Inline errors: every empty required field gets a red frame and
            # a short note under it; the first one gets the focus.
            first = True
            for key, label in required.items():
                if not self.entries[key].get().strip():
                    field_error(self.entries[key], f"{label} الزامی است.", focus=first)
                    first = False

            return False

        return True

    # ========================================================
    # SAVE
    # ========================================================

    def _save(self):

        # ----------------------------------------------------
        # Required fields
        # ----------------------------------------------------

        if not self._validate_required():
            return

        code = self.entries["code"].get().strip()
        name = self.entries["name"].get().strip()
        category = self.entries["category"].get().strip()
        location = self.entries["location"].get().strip()
        status_fa = self.entries["status"].get().strip()

        status_en = next(
            (
                key
                for key, value in STATUS_FA.items()
                if value == status_fa
            ),
            None
        )

        if not status_en:

            messagebox.showerror(
                "خطا",
                "وضعیت تجهیز معتبر نیست.",
                parent=self
            )

            return

        # ----------------------------------------------------
        # Installation date
        # ----------------------------------------------------

        try:
            installation_date = (
                self.entries[
                    "installation_date"
                ].get_date()
            )
        except Exception:
            installation_date = None

        # ----------------------------------------------------
        # Numeric fields
        # ----------------------------------------------------

        numeric_fields = [
            ("length", "طول"),
            ("width", "عرض"),
            ("diameter", "قطر"),
            ("height", "ارتفاع"),
            ("volume", "حجم"),
            ("weight", "وزن"),
        ]

        numeric_values = {}

        for key, label in numeric_fields:

            raw = self.entries[key].get().strip()

            if not raw:
                numeric_values[key] = None
                continue

            try:

                value = float(raw)

                if value < 0:
                    raise ValueError

                numeric_values[key] = value

            except (ValueError, TypeError):

                field_error(self.entries[key], f"مقدار «{label}» باید یک عدد مثبت باشد.")

                return

        # ----------------------------------------------------
        # Text
        # ----------------------------------------------------

        specifications = self.entries[
            "specifications"
        ].get(
            "1.0",
            "end-1c"
        ).strip()

        notes = self.entries[
            "notes"
        ].get(
            "1.0",
            "end-1c"
        ).strip()

        manufacturer = self.entries[
            "manufacturer"
        ].get().strip()

        model = self.entries[
            "model"
        ].get().strip()

        serial_number = self.entries[
            "serial_number"
        ].get().strip()

        # ----------------------------------------------------
        # UPDATE
        # ----------------------------------------------------

        if self.equipment:

            success, msg = self.equipment_repo.update_equipment(
                self.equipment["id"],
                code,
                name,
                category,
                manufacturer,
                model,
                serial_number,
                location,
                installation_date,
                status_en,
                specifications,
                notes,
                length=numeric_values["length"],
                width=numeric_values["width"],
                diameter=numeric_values["diameter"],
                height=numeric_values["height"],
                volume=numeric_values["volume"],
                weight=numeric_values["weight"],
            )

        # ----------------------------------------------------
        # CREATE
        # ----------------------------------------------------

        else:

            success, msg = self.equipment_repo.create_equipment(
                code,
                name,
                category,
                manufacturer,
                model,
                serial_number,
                location,
                installation_date,
                status_en,
                specifications,
                notes,
                length=numeric_values["length"],
                width=numeric_values["width"],
                diameter=numeric_values["diameter"],
                height=numeric_values["height"],
                volume=numeric_values["volume"],
                weight=numeric_values["weight"],
            )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        if success:

            self.result = True
            self.destroy()

        else:

            messagebox.showerror(
                "خطا",
                msg,
                parent=self
            )

    # ========================================================
    # CLEANUP
    # ========================================================

    def destroy(self):

        # FIX: the previous version called self.canvas.unbind_all("<MouseWheel>")
        # which removed mouse-wheel bindings across the entire application,
        # breaking scrolling in other views/dialogs. Removed.

        try:
            self.grab_release()
        except Exception:
            pass

        super().destroy()