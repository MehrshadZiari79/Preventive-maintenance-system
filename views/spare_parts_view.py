# views/spare_parts_view.py
import tkinter as tk
from views.ui_kit import rtl_columns  # RTL (right-to-left) table columns
from tkinter import ttk, messagebox
from services.spare_parts_service import SparePartsService
from views.export_dialog import run_spare_parts_export
from auth.auth_manager import AuthManager
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)
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


class SparePartsView(ttk.Frame):
    # ... (keep your existing SparePartsView code unchanged)
    # I'll include the full class for completeness.

    def __init__(self, parent, session_factory, current_user):
        super().__init__(parent)
        self.session_factory = session_factory
        self.service = SparePartsService(session_factory)
        self.current_user = current_user
        # built-in roles as before; custom roles from «مدیریت نقش‌ها»
        self.can_manage = AuthManager.allows(("admin", "manager", "technician"), "spare_parts", "write")
        self.can_delete = AuthManager.allows(("admin", "manager", "technician"), "spare_parts", "delete")

        self._setup_ui()
        self._load()

    def _setup_ui(self):
        self._build_header()
        self._build_stats_bar()
        self._build_search_bar()
        self._build_table()

    def _build_header(self):
        hdr = tk.Frame(self, bg=PRIMARY, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🔧  مدیریت قطعات یدکی", font=FONT_TITLE, bg=PRIMARY, fg=WHITE).pack(side="right", padx=20, pady=14)

        btn_frame = tk.Frame(hdr, bg=PRIMARY)
        btn_frame.pack(side="left", padx=16)
        if self.can_manage:
            tk.Button(btn_frame, text="➕ افزودن قطعه", font=FONT_NORMAL, bg=WHITE, fg=PRIMARY,
                      relief="flat", cursor="hand2", padx=12, pady=6,
                      command=self._add_part).pack(side="left", padx=4)
        tk.Button(btn_frame, text="🔄 بروزرسانی", font=FONT_NORMAL, bg=NAVY_LIGHT, fg=WHITE,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._load).pack(side="left", padx=4)
        tk.Button(btn_frame, text="📤  Excel خروجی ", font=FONT_NORMAL, bg=SUCCESS, fg=WHITE,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._export).pack(side="left", padx=4)

    def _build_stats_bar(self):
        stats_frame = tk.Frame(self, bg=BG)
        stats_frame.pack(fill="x", padx=20, pady=(12, 0))
        self.stats_cards = {}

        cards = [
            ("total", "📦 کل قطعات", CARD_BG, PRIMARY),
            ("low_stock", "⚠️ موجودی کم", "#FFF8E1", WARNING),
            ("value", "💰 ارزش موجودی", "#E6F4EA", SUCCESS),
        ]
        for key, text, bg_color, fg_color in cards:
            shadow = tk.Frame(stats_frame, bg=BORDER)
            shadow.pack(side="right", padx=5)
            card = tk.Frame(shadow, bg=bg_color)
            card.pack(fill="both", expand=True, padx=1, pady=1)
            tk.Label(card, text=text, font=FONT_SMALL, bg=bg_color, fg=SUBTLE).pack(padx=16, pady=(8,0))
            lbl = tk.Label(card, text="0", font=FONT_HEADING, bg=bg_color, fg=fg_color)
            lbl.pack(padx=16, pady=(0,8))
            self.stats_cards[key] = lbl

    def _build_search_bar(self):
        toolbar = tk.Frame(self, bg=BG)
        toolbar.pack(fill="x", padx=20, pady=(10, 6))

        tk.Label(toolbar, text="جستجو:", font=FONT_NORMAL, bg=BG, fg=TEXT).pack(side="right", padx=(0,5))
        self.search_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self.search_var, font=FONT_NORMAL,
                 bg=CARD_BG, fg=TEXT, relief="solid", bd=1, width=25).pack(side="right", ipady=4)
        tk.Button(toolbar, text="🔍 جستجو", font=FONT_NORMAL,
                  bg=PRIMARY, fg=WHITE, relief="flat", cursor="hand2",
                  padx=12, pady=4, command=self._search).pack(side="right", padx=5)
        tk.Button(toolbar, text="⚠️ قطعات کم‌موجودی", font=FONT_NORMAL,
                  bg=WARNING, fg=WHITE, relief="flat", cursor="hand2",
                  padx=12, pady=4, command=self._show_low_stock).pack(side="right", padx=5)
        tk.Button(toolbar, text="🗑️ پاک کردن فیلتر", font=FONT_NORMAL,
                  bg=SUBTLE, fg=WHITE, relief="flat", cursor="hand2",
                  padx=12, pady=4, command=self._load).pack(side="right", padx=5)

    def _build_table(self):
        container = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        container.pack(fill="both", expand=True, padx=20, pady=(0,20))

        columns = ("id", "part_number", "name", "category",
                   "stock", "min_stock", "unit", "price", "location")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=16)
        rtl_columns(self.tree)  # RTL column order

        headers = [
            ("id",          "شناسه",        50,  "center"),
            ("part_number", "شماره قطعه",   120, "center"),
            ("name",        "نام قطعه",     200, "w"),
            ("category",    "دسته‌بندی",    120, "w"),
            ("stock",       "موجودی",       80,  "center"),
            ("min_stock",   "حداقل موجودی", 100, "center"),
            ("unit",        "واحد",         70,  "center"),
            ("price",       "قیمت (تومان)", 120, "center"),
            ("location",    "محل نگهداری",  120, "w"),
        ]
        for col, text, width, anchor in headers:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.configure(selectmode='extended')
        self.tree.bind("<Delete>", lambda e=None: self._delete_selected())
        self.tree.bind("<F2>",      lambda e=None: self._edit_part() if self.can_manage else self._view_history())
        self.tree.bind("<Control-n>", lambda e=None: self._add_part())

        style = ttk.Style()
        style.configure("Treeview", background=CARD_BG, fieldbackground=CARD_BG, foreground=TEXT, rowheight=26)
        style.configure("Treeview.Heading", background=PRIMARY, foreground=WHITE, font=FONT_NORMAL)
        style.map("Treeview", background=[("selected", PRIMARY)], foreground=[("selected", WHITE)])

        self.tree.bind("<Button-3>", self._context_menu)
        self.tree.bind("<Double-1>", lambda e=None: self._edit_part() if self.can_manage else self._view_history())

    def _load(self):
        parts = self.service.get_all_parts()
        self._populate_table(parts)
        self._update_stats()

    def _populate_table(self, parts):
        self.tree.delete(*self.tree.get_children())
        for part in parts:
            values = (
                part.id, part.part_number, part.name, part.category or "—",
                part.current_stock, part.min_stock, part.unit or "—",
                f"{part.unit_price:,.0f}", part.location or "—",
            )
            tags = ("low_stock",) if part.current_stock <= part.min_stock else ()
            self.tree.insert("", "end", iid=str(part.id), values=values, tags=tags)

    def _update_stats(self):
        stats = self.service.get_stats()
        self.stats_cards["total"].config(text=str(stats["total_parts"]))
        self.stats_cards["low_stock"].config(text=str(stats["low_stock_count"]))
        self.stats_cards["value"].config(text=f"{stats['total_inventory_value']:,.0f}")

    def _search(self):
        keyword = self.search_var.get().strip()
        if not keyword:
            self._load()
            return
        parts = self.service.search_parts(keyword)
        self._populate_table(parts)

    def _show_low_stock(self):
        parts = self.service.get_low_stock_parts()
        self._populate_table(parts)

    def _export(self):
        parts = self.service.get_all_parts()
        run_spare_parts_export(self, parts)

    def _add_part(self):
        if not self.can_manage:
            messagebox.showwarning("دسترسی", "شما مجاز به افزودن قطعه نیستید.", parent=self)
            return
        SparePartForm(self, self.session_factory, callback=self._load)

    def _edit_part(self):
        if not self.can_manage:
            messagebox.showwarning("دسترسی", "شما مجاز به ویرایش قطعه نیستید.", parent=self)
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً یک قطعه انتخاب کنید.")
            return
        part_id = int(selected[0])
        part = self.service.get_part_by_id(part_id)
        SparePartForm(self, self.session_factory, part=part, callback=self._load)

    def _delete_part(self):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف قطعه نیستید.", parent=self)
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً یک قطعه انتخاب کنید.")
            return
        part_id = int(selected[0])
        part = self.service.get_part_by_id(part_id)
        if not messagebox.askyesno("تأیید حذف",
                                   f"آیا از حذف قطعه '{part.name}' مطمئن هستید؟\nاین عملیات غیرقابل بازگشت است."):
            return
        try:
            self.service.delete_part(part_id)
            messagebox.showinfo("موفق", "قطعه با موفقیت حذف شد.")
            self._load()
        except Exception as e:
            messagebox.showerror("خطا", str(e))

    def _delete_selected(self):
        if not self.can_delete:
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً حداقل یک قطعه انتخاب کنید.")
            return
        if not messagebox.askyesno("حذف", f"آیا از حذف {len(selected)} قطعه اطمینان دارید؟"):
            return
        for part_id in selected:
            try:
                self.service.delete_part(int(part_id))
            except Exception as e:
                messagebox.showerror("خطا", str(e))
        self._load()

    def _stock_in(self):
        if not self.can_manage:
            messagebox.showwarning("دسترسی", "شما مجاز به ورود به انبار نیستید.", parent=self)
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً یک قطعه انتخاب کنید.")
            return
        part_id = int(selected[0])
        part = self.service.get_part_by_id(part_id)
        StockTransactionForm(self, self.session_factory, part, "IN", callback=self._load)

    def _stock_out(self):
        if not self.can_manage:
            messagebox.showwarning("دسترسی", "شما مجاز به خروج از انبار نیستید.", parent=self)
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً یک قطعه انتخاب کنید.")
            return
        part_id = int(selected[0])
        part = self.service.get_part_by_id(part_id)
        StockTransactionForm(self, self.session_factory, part, "OUT", callback=self._load)

    def _view_history(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً یک قطعه انتخاب کنید.")
            return
        part_id = int(selected[0])
        part = self.service.get_part_by_id(part_id)
        PartTransactionsView(self, self.session_factory, part)

    def _context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.selection_set(row)
        menu = tk.Menu(self, tearoff=0, font=FONT_NORMAL)
        if self.can_manage:
            menu.add_command(label="✏️ ویرایش", command=self._edit_part)
            menu.add_command(label="📥 ورود به انبار", command=self._stock_in)
            menu.add_command(label="📤 خروج از انبار", command=self._stock_out)
            if self.can_delete:
                menu.add_separator()
                menu.add_command(label="🗑️ حذف", command=self._delete_part)
        else:
            menu.add_command(label="🔍 مشاهده تاریخچه", command=self._view_history)
        menu.post(event.x_root, event.y_root)


# ── FIXED SPARE PART FORM ──────────────────────────────────────────

    def ux_footer_spec(self):
        """Filters shown as removable chips under the table (views/ux.py)."""
        return {"filters": [("جستجو", self.search_var, "")], "apply": self._load,
                "noun": "قطعه"}


class SparePartForm(tk.Toplevel):
    def __init__(self, parent, session_factory, part=None, callback=None):
        super().__init__(parent)

        self.session_factory = session_factory
        self.service = SparePartsService(session_factory)
        self.part = part
        self.callback = callback

        self.title("ویرایش قطعه" if part else "افزودن قطعه جدید")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(600, 650)

        # A slightly larger default size gives the form enough room while
        # still fitting comfortably on standard screens.
        self.geometry("680x780")
        self._center(680, 780)

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._setup_ui()

        if part:
            self._load_data()

    def _center(self, width, height):
        self.update_idletasks()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Keep the window inside the usable screen area.
        height = min(height, max(650, screen_height - 80))

        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

    def _setup_ui(self):
        # Root layout:
        # row 0 = header
        # row 1 = scrollable form
        # row 2 = fixed action footer
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────────
        header = tk.Frame(self, bg=PRIMARY, height=58)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        title = "✏️ ویرایش قطعه" if self.part else "➕ افزودن قطعه جدید"

        tk.Label(
            header,
            text=title,
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE
        ).pack(expand=True)

        # ── Scrollable content ─────────────────────────────────
        content = tk.Frame(self, bg=BG)
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(
            content,
            bg=BG,
            highlightthickness=0,
            bd=0
        )
        self._form_canvas = canvas

        vsb = ttk.Scrollbar(
            content,
            orient="vertical",
            command=canvas.yview
        )

        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        canvas.configure(yscrollcommand=vsb.set)

        scrollable = tk.Frame(canvas, bg=BG)
        window_id = canvas.create_window(
            (0, 0),
            window=scrollable,
            anchor="nw"
        )

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_scrollable(event):
            # Critical fix: make the form follow the visible canvas width.
            # This prevents fields from extending beyond the right edge.
            canvas.itemconfigure(window_id, width=event.width)

        scrollable.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_scrollable)

        # Mouse wheel only affects this form.
        canvas.bind("<MouseWheel>", self._on_mousewheel)
        canvas.bind("<Button-4>", self._on_mousewheel)
        canvas.bind("<Button-5>", self._on_mousewheel)

        # ── Form card ──────────────────────────────────────────
        main = tk.Frame(
            scrollable,
            bg=CARD_BG,
            padx=30,
            pady=20
        )
        main.pack(fill="both", expand=True)

        tk.Label(
            main,
            text="🔧 اطلاعات قطعه",
            font=FONT_TITLE,
            bg=CARD_BG,
            fg=PRIMARY
        ).pack(pady=(0, 15))

        self.entries = {}

        fields = [
            ("شماره قطعه *:", "part_number"),
            ("نام قطعه *:", "name"),
            ("توضیحات:", "description"),
            ("دسته‌بندی:", "category"),
            ("واحد:", "unit"),
            ("حداقل موجودی:", "min_stock"),
            ("موجودی فعلی:", "current_stock"),
            ("قیمت واحد (تومان):", "unit_price"),
            ("محل نگهداری:", "location"),
            ("تامین‌کننده:", "supplier"),
            ("کد تجهیزات مرتبط:", "equipment_codes"),
            ("یادداشت:", "notes"),
        ]

        for label, field in fields:
            tk.Label(
                main,
                text=label,
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=TEXT,
                anchor="e"
            ).pack(
                fill="x",
                pady=(5, 2)
            )

            if field in ("description", "notes"):
                widget = tk.Text(
                    main,
                    height=3,
                    font=FONT_NORMAL,
                    bg=CARD_BG,
                    fg=TEXT,
                    relief="solid",
                    bd=1,
                    wrap="word"
                )
                widget.pack(
                    fill="x",
                    pady=(0, 8)
                )
            else:
                widget = tk.Entry(
                    main,
                    font=FONT_NORMAL,
                    bg=CARD_BG,
                    fg=TEXT,
                    relief="solid",
                    bd=1,
                    justify="right"
                )
                widget.pack(
                    fill="x",
                    ipady=4,
                    pady=(0, 8)
                )

            self.entries[field] = widget

        # ── Fixed footer ───────────────────────────────────────
        footer = tk.Frame(
            self,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        footer.grid(row=2, column=0, sticky="ew")

        button_row = tk.Frame(footer, bg=CARD_BG)
        button_row.pack(anchor="center", pady=12)

        tk.Button(
            button_row,
            text="انصراف",
            font=FONT_NORMAL,
            bg=BORDER,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            cursor="hand2",
            padx=28,
            pady=8,
            command=self.destroy
        ).pack(side="left", padx=6)

        tk.Button(
            button_row,
            text="ذخیره",
            font=FONT_NORMAL,
            bg=SUCCESS,
            fg=WHITE,
            activebackground=SUCCESS,
            activeforeground=WHITE,
            relief="flat",
            cursor="hand2",
            padx=30,
            pady=8,
            command=self._save
        ).pack(side="left", padx=6)

        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Control-s>", lambda _event: self._save())

        self.after(50, lambda: canvas.configure(
            scrollregion=canvas.bbox("all")
        ))

    def _on_mousewheel(self, event):
        try:
            if event.num == 4:
                self._form_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self._form_canvas.yview_scroll(1, "units")
            else:
                self._form_canvas.yview_scroll(
                    -1 if event.delta > 0 else 1,
                    "units"
                )
        except tk.TclError:
            pass

    def _load_data(self):
        if not self.part:
            return

        for field, widget in self.entries.items():
            value = getattr(self.part, field, "")

            if value is None:
                value = ""

            if isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert("1.0", str(value))
            else:
                widget.delete(0, tk.END)
                widget.insert(0, str(value))

    def _save(self):
        data = {}

        for field, widget in self.entries.items():
            if isinstance(widget, tk.Text):
                data[field] = widget.get(
                    "1.0",
                    "end-1c"
                ).strip()
            else:
                data[field] = widget.get().strip()

        if not data.get("part_number") or not data.get("name"):
            from views.ux import field_error
            if not data.get("part_number"):
                field_error(self.entries["part_number"], "شماره قطعه الزامی است.")
            if not data.get("name"):
                field_error(self.entries["name"], "نام قطعه الزامی است.",
                            focus=bool(data.get("part_number")))
            return

        try:
            data["min_stock"] = (
                int(data.get("min_stock", 0))
                if data.get("min_stock")
                else 0
            )
            data["current_stock"] = (
                int(data.get("current_stock", 0))
                if data.get("current_stock")
                else 0
            )
            data["unit_price"] = (
                float(data.get("unit_price", 0))
                if data.get("unit_price")
                else 0.0
            )
        except ValueError:
            messagebox.showerror(
                "خطا",
                "مقادیر عددی نامعتبر هستند.",
                parent=self
            )
            return

        try:
            if self.part:
                self.service.update_part(
                    self.part.id,
                    data
                )
                messagebox.showinfo(
                    "موفق",
                    "قطعه با موفقیت ویرایش شد.",
                    parent=self
                )
            else:
                self.service.create_part(data)
                messagebox.showinfo(
                    "موفق",
                    "قطعه با موفقیت اضافه شد.",
                    parent=self
                )

            if self.callback:
                self.callback()

            self.destroy()

        except Exception as e:
            messagebox.showerror(
                "خطا",
                str(e),
                parent=self
            )


class StockTransactionForm(tk.Toplevel):
    def __init__(
        self,
        parent,
        session_factory,
        part,
        trans_type,
        work_order_id=None,
        callback=None
    ):
        super().__init__(parent)

        self.session_factory = session_factory
        self.service = SparePartsService(session_factory)
        self.part = part
        self.trans_type = trans_type
        self.work_order_id = work_order_id
        self.callback = callback

        title = (
            "ورود به انبار"
            if trans_type == "IN"
            else "خروج از انبار"
        )

        self.title(f"{title} - {part.part_number}")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(520, 520)
        self.geometry("560x600")
        self._center(560, 600)

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._setup_ui()

    def _center(self, width, height):
        self.update_idletasks()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

    def _setup_ui(self):
        # row 0 = header
        # row 1 = scrollable content
        # row 2 = fixed footer
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────────
        header = tk.Frame(self, bg=PRIMARY, height=55)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        act = (
            "📥 ورود به انبار"
            if self.trans_type == "IN"
            else "📤 خروج از انبار"
        )

        tk.Label(
            header,
            text=act,
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE
        ).pack(expand=True)

        # ── Scrollable content ─────────────────────────────────
        content = tk.Frame(self, bg=BG)
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(
            content,
            bg=BG,
            highlightthickness=0,
            bd=0
        )
        self._form_canvas = canvas

        vsb = ttk.Scrollbar(
            content,
            orient="vertical",
            command=canvas.yview
        )

        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=vsb.set)

        scrollable = tk.Frame(canvas, bg=BG)
        window_id = canvas.create_window(
            (0, 0),
            window=scrollable,
            anchor="nw"
        )

        scrollable.bind(
            "<Configure>",
            lambda _event: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(
                window_id,
                width=event.width
            )
        )

        canvas.bind("<MouseWheel>", self._on_mousewheel)
        canvas.bind("<Button-4>", self._on_mousewheel)
        canvas.bind("<Button-5>", self._on_mousewheel)

        # ── Main card ──────────────────────────────────────────
        main = tk.Frame(
            scrollable,
            bg=CARD_BG,
            padx=28,
            pady=20
        )
        main.pack(fill="both", expand=True)

        info_card = tk.Frame(
            main,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        info_card.pack(
            fill="x",
            pady=(0, 18),
            ipady=8
        )

        tk.Label(
            info_card,
            text=f"قطعه: {self.part.name}",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT
        ).pack(pady=2)

        tk.Label(
            info_card,
            text=f"موجودی فعلی: {self.part.current_stock}",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=SUBTLE
        ).pack(pady=2)

        frm = tk.Frame(main, bg=CARD_BG)
        frm.pack(fill="x", pady=8)

        tk.Label(
            frm,
            text="تعداد *:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            width=15,
            anchor="e"
        ).pack(
            side="right",
            padx=(0, 10)
        )

        self.qty_entry = tk.Entry(
            frm,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            relief="solid",
            bd=1,
            justify="right"
        )
        self.qty_entry.pack(
            side="right",
            fill="x",
            expand=True,
            ipady=4
        )

        if self.trans_type == "IN":
            frm_price = tk.Frame(main, bg=CARD_BG)
            frm_price.pack(fill="x", pady=8)

            tk.Label(
                frm_price,
                text="قیمت واحد (تومان):",
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=TEXT,
                width=15,
                anchor="e"
            ).pack(
                side="right",
                padx=(0, 10)
            )

            self.price_entry = tk.Entry(
                frm_price,
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=TEXT,
                relief="solid",
                bd=1,
                justify="right"
            )
            self.price_entry.pack(
                side="right",
                fill="x",
                expand=True,
                ipady=4
            )
            self.price_entry.insert(
                0,
                str(self.part.unit_price)
            )

        frm2 = tk.Frame(main, bg=CARD_BG)
        frm2.pack(fill="x", pady=8)

        tk.Label(
            frm2,
            text="مرجع:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            width=15,
            anchor="e"
        ).pack(
            side="right",
            padx=(0, 10)
        )

        self.ref_entry = tk.Entry(
            frm2,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            relief="solid",
            bd=1,
            justify="right"
        )
        self.ref_entry.pack(
            side="right",
            fill="x",
            expand=True,
            ipady=4
        )

        frm3 = tk.Frame(main, bg=CARD_BG)
        frm3.pack(fill="x", pady=8)

        tk.Label(
            frm3,
            text="توضیحات:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            width=15,
            anchor="e"
        ).pack(
            side="right",
            padx=(0, 10)
        )

        self.notes_text = tk.Text(
            frm3,
            height=4,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            relief="solid",
            bd=1,
            wrap="word"
        )
        self.notes_text.pack(
            side="right",
            fill="x",
            expand=True
        )

        # ── Fixed footer ───────────────────────────────────────
        footer = tk.Frame(
            self,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        footer.grid(row=2, column=0, sticky="ew")

        button_row = tk.Frame(footer, bg=CARD_BG)
        button_row.pack(anchor="center", pady=12)

        tk.Button(
            button_row,
            text="انصراف",
            font=FONT_NORMAL,
            bg=BORDER,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            cursor="hand2",
            padx=25,
            pady=8,
            command=self.destroy
        ).pack(side="left", padx=6)

        tk.Button(
            button_row,
            text="ثبت",
            font=FONT_NORMAL,
            bg=SUCCESS,
            fg=WHITE,
            activebackground=SUCCESS,
            activeforeground=WHITE,
            relief="flat",
            cursor="hand2",
            padx=30,
            pady=8,
            command=self._save
        ).pack(side="left", padx=6)

        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Control-s>", lambda _event: self._save())

    def _on_mousewheel(self, event):
        try:
            if event.num == 4:
                self._form_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self._form_canvas.yview_scroll(1, "units")
            else:
                self._form_canvas.yview_scroll(
                    -1 if event.delta > 0 else 1,
                    "units"
                )
        except tk.TclError:
            pass

    def _save(self):
        try:
            qty = int(self.qty_entry.get().strip())

            if qty <= 0:
                raise ValueError("تعداد باید مثبت باشد")

            if (
                self.trans_type == "OUT"
                and qty > self.part.current_stock
            ):
                raise ValueError(
                    f"موجودی ناکافی. موجودی فعلی: "
                    f"{self.part.current_stock}"
                )

        except ValueError as e:
            messagebox.showerror(
                "خطا",
                str(e),
                parent=self
            )
            return

        data = {
            "part_id": self.part.id,
            "transaction_type": self.trans_type,
            "quantity": qty,
            "reference": self.ref_entry.get().strip(),
            "notes": self.notes_text.get(
                "1.0",
                "end-1c"
            ).strip(),
        }

        batch_price = None

        if self.trans_type == "IN" and hasattr(
            self,
            "price_entry"
        ):
            try:
                batch_price = float(
                    self.price_entry.get().strip()
                )
            except (ValueError, TypeError):
                batch_price = None

        try:
            self.service.add_stock_transaction(
                data,
                work_order_id=self.work_order_id,
                batch_price=batch_price
            )

            messagebox.showinfo(
                "موفق",
                "عملیات انبار با موفقیت ثبت شد.",
                parent=self
            )

            if self.callback:
                self.callback()

            self.destroy()

        except Exception as e:
            messagebox.showerror(
                "خطا",
                str(e),
                parent=self
            )


class PartTransactionsView(tk.Toplevel):
    def __init__(self, parent, session_factory, part):
        super().__init__(parent)

        self.session_factory = session_factory
        self.service = SparePartsService(session_factory)
        self.part = part

        self.title(
            f"تاریخچه تراکنش‌ها - {part.part_number}"
        )
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(800, 450)
        self.geometry("1000x560")
        self._center(1000, 560)

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._setup_ui()
        self._load()

    def _center(self, width, height):
        self.update_idletasks()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

    def _setup_ui(self):
        # row 0 = header
        # row 1 = table
        # row 2 = fixed footer
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = tk.Frame(
            self,
            bg=PRIMARY,
            height=55
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        tk.Label(
            header,
            text=(
                f"📋 تاریخچه قطعه: {self.part.name} "
                f"({self.part.part_number})"
            ),
            font=FONT_TITLE,
            bg=PRIMARY,
            fg=WHITE
        ).pack(expand=True)

        frame = tk.Frame(
            self,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=20,
            pady=15
        )
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        columns = (
            "date",
            "type",
            "quantity",
            "price",
            "reference",
            "notes"
        )

        self.tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings"
        )
        rtl_columns(self.tree)  # RTL column order

        headers = [
            ("date", "تاریخ", 150, "center"),
            ("type", "نوع", 80, "center"),
            ("quantity", "تعداد", 80, "center"),
            ("price", "قیمت واحد", 150, "center"),
            ("reference", "مرجع", 200, "w"),
            ("notes", "توضیحات", 300, "w"),
        ]

        for col, text, width, anchor in headers:
            self.tree.heading(col, text=text)
            self.tree.column(
                col,
                width=width,
                anchor=anchor,
                minwidth=60
            )

        vsb = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.tree.yview
        )
        hsb = ttk.Scrollbar(
            frame,
            orient="horizontal",
            command=self.tree.xview
        )

        self.tree.configure(
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew"
        )
        vsb.grid(
            row=0,
            column=1,
            sticky="ns"
        )
        hsb.grid(
            row=1,
            column=0,
            sticky="ew"
        )

        self.tree.tag_configure(
            "IN",
            foreground=SUCCESS
        )
        self.tree.tag_configure(
            "OUT",
            foreground=DANGER
        )

        style = ttk.Style()
        style.configure(
            "Treeview",
            background=CARD_BG,
            fieldbackground=CARD_BG,
            foreground=TEXT,
            rowheight=28
        )
        style.configure(
            "Treeview.Heading",
            background=PRIMARY,
            foreground=WHITE,
            font=FONT_NORMAL
        )
        style.map(
            "Treeview",
            background=[("selected", PRIMARY)],
            foreground=[("selected", WHITE)]
        )

        # ── Fixed footer ───────────────────────────────────────
        footer = tk.Frame(
            self,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        footer.grid(
            row=2,
            column=0,
            sticky="ew"
        )

        tk.Button(
            footer,
            text="بستن",
            font=FONT_NORMAL,
            bg=PRIMARY,
            fg=WHITE,
            activebackground=PRIMARY,
            activeforeground=WHITE,
            relief="flat",
            cursor="hand2",
            padx=28,
            pady=8,
            command=self.destroy
        ).pack(
            anchor="center",
            pady=10
        )

        self.bind(
            "<Escape>",
            lambda _event: self.destroy()
        )

    def _load(self):
        self.tree.delete(*self.tree.get_children())

        transactions = self.service.get_part_transactions(
            self.part.id
        )

        for trans in transactions:
            price_text = (
                f"{trans.batch_price:,.0f}"
                if trans.batch_price
                else "—"
            )

            date_str = to_jalali_datetime_str(
                trans.created_at
            )

            values = (
                date_str,
                (
                    "ورود"
                    if trans.transaction_type == "IN"
                    else "خروج"
                ),
                trans.quantity,
                price_text,
                trans.reference or "—",
                trans.notes or "—",
            )

            item = self.tree.insert(
                "",
                "end",
                values=values
            )
            self.tree.item(
                item,
                tags=(trans.transaction_type,)
            )

