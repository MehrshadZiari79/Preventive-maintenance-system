# views/spare_parts_view.py
"""
Spare Parts View - Inventory Management for Spare Parts
Persian UI, consistent with other app views.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from services.spare_parts_service import SparePartsService
from views.export_dialog import run_spare_parts_export

# ─────────────────────────── Theme (same as other views) ────────────────────
BG        = "#F0F4F8"
WHITE     = "#FFFFFF"
PRIMARY   = "#1A73E8"
DANGER    = "#DC3545"
SUCCESS   = "#28A745"
WARNING   = "#F29900"
TEXT      = "#202124"
SUBTLE    = "#5F6368"
BORDER    = "#DADCE0"
RED_BG    = "#FCE8E6"
GREEN_BG  = "#E6F4EA"
YELLOW_BG = "#FFF8E1"

FONT_TITLE = ("Tahoma", 14, "bold")
FONT_LABEL = ("Tahoma", 10, "bold")
FONT_INPUT = ("Tahoma", 10)
FONT_SMALL = ("Tahoma", 9)
FONT_STAT  = ("Tahoma", 18, "bold")


class SparePartsView(ttk.Frame):
    def __init__(self, parent, session):
        super().__init__(parent, style="TFrame")
        self.session = session
        self.service = SparePartsService(session)
        self._setup_ui()
        self._load()

    # ─────────────────────────── UI Build ───────────────────────────────────
    def _setup_ui(self):
        self._build_header()
        self._build_stats_bar()
        self._build_search_bar()
        self._build_table()

    def _build_header(self):
        hdr = tk.Frame(self, bg=PRIMARY, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="🔧  مدیریت قطعات یدکی",
                 font=FONT_TITLE, bg=PRIMARY, fg=WHITE).pack(
            side="right", padx=20, pady=14)

        btn_frame = tk.Frame(hdr, bg=PRIMARY)
        btn_frame.pack(side="left", padx=16, pady=10)

        tk.Button(btn_frame, text="➕ افزودن قطعه",
                  font=FONT_LABEL, bg=WHITE, fg=PRIMARY,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._add_part).pack(side="left", padx=4)

        tk.Button(btn_frame, text="🔄 بروزرسانی",
                  font=FONT_INPUT, bg=PRIMARY, fg=WHITE,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._load).pack(side="left", padx=4)

        tk.Button(btn_frame, text="📤 خروجی Excel / PDF",
                  font=FONT_INPUT, bg="#34A853", fg=WHITE,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._export).pack(side="left", padx=4)

    def _build_stats_bar(self):
        stats_frame = tk.Frame(self, bg=BG)
        stats_frame.pack(fill="x", padx=20, pady=(12, 0))
        self.stats_cards = {}  # to store label widgets

        # Define statistics cards
        cards = [
            ("total", "📦 کل قطعات", WHITE, PRIMARY),
            ("low_stock", "⚠️ موجودی کم", YELLOW_BG, WARNING),
            ("value", "💰 ارزش موجودی", GREEN_BG, SUCCESS),
        ]
        for key, text, bg_color, fg_color in cards:
            card = tk.Frame(stats_frame, bg=bg_color,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(side="right", padx=5, ipadx=16, ipady=8)
            tk.Label(card, text=text, font=FONT_SMALL,
                     bg=bg_color, fg=SUBTLE).pack()
            lbl = tk.Label(card, text="0", font=FONT_STAT, bg=bg_color, fg=fg_color)
            lbl.pack()
            self.stats_cards[key] = lbl

    def _build_search_bar(self):
        toolbar = tk.Frame(self, bg=BG)
        toolbar.pack(fill="x", padx=20, pady=(10, 6))

        tk.Label(toolbar, text="جستجو:", font=FONT_INPUT,
                 bg=BG, fg=TEXT).pack(side="right", padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=self.search_var,
                                font=FONT_INPUT, bg=WHITE, fg=TEXT,
                                relief="solid", bd=1, width=25)
        search_entry.pack(side="right", ipady=4)
        search_entry.bind("<Return>", lambda e: self._search())

        tk.Button(toolbar, text="🔍 جستجو", font=FONT_INPUT,
                  bg=PRIMARY, fg=WHITE, relief="flat", cursor="hand2",
                  padx=12, pady=4, command=self._search).pack(side="right", padx=5)

        tk.Button(toolbar, text="⚠️ قطعات کم‌موجودی", font=FONT_INPUT,
                  bg=WARNING, fg=WHITE, relief="flat", cursor="hand2",
                  padx=12, pady=4, command=self._show_low_stock).pack(side="right", padx=5)

        tk.Button(toolbar, text="🗑️ پاک کردن فیلتر", font=FONT_INPUT,
                  bg=SUBTLE, fg=WHITE, relief="flat", cursor="hand2",
                  padx=12, pady=4, command=self._load).pack(side="right", padx=5)

    def _build_table(self):
        container = tk.Frame(self, bg=WHITE,
                             highlightbackground=BORDER, highlightthickness=1)
        container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        columns = ("id", "part_number", "name", "category",
                   "stock", "min_stock", "unit", "price", "location")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=16)

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
        self.tree.pack(side="right", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # Right-click menu
        self.tree.bind("<Button-3>", self._context_menu)
        self.tree.bind("<Double-1>", lambda e: self._edit_part())
        self.ctx_menu = tk.Menu(self, tearoff=0, font=FONT_INPUT)
        self.ctx_menu.add_command(label="✏️ ویرایش", command=self._edit_part)
        self.ctx_menu.add_command(label="📥 ورود به انبار", command=self._stock_in)
        self.ctx_menu.add_command(label="📤 خروج از انبار", command=self._stock_out)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="🗑️ حذف", command=self._delete_part)

        # Tags for low stock highlighting
        self.tree.tag_configure("low_stock", background=RED_BG)

    # ─────────────────────────── Data Loading ───────────────────────────────
    def _load(self):
        parts = self.service.get_all_parts()
        self._populate_table(parts)
        self._update_stats()

    def _populate_table(self, parts):
        self.tree.delete(*self.tree.get_children())
        for part in parts:
            values = (
                part.id,
                part.part_number,
                part.name,
                part.category or "—",
                part.current_stock,
                part.min_stock,
                part.unit or "—",
                f"{part.unit_price:,.0f}",
                part.location or "—",
            )
            tags = ()
            if part.current_stock <= part.min_stock:
                tags = ("low_stock",)
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

    # ─────────────────────────── Actions ────────────────────────────────────
    def _export(self):
        parts = self.service.get_all_parts()
        run_spare_parts_export(self, parts)

    def _add_part(self):
        SparePartForm(self, self.session, callback=self._load)

    def _edit_part(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً یک قطعه انتخاب کنید.")
            return
        part_id = int(selected[0])
        part = self.service.get_part_by_id(part_id)
        SparePartForm(self, self.session, part=part, callback=self._load)

    def _delete_part(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً یک قطعه انتخاب کنید.")
            return
        part_id = int(selected[0])
        part = self.service.get_part_by_id(part_id)
        if not messagebox.askyesno("تأیید حذف",
                                   f"آیا از حذف قطعه '{part.name}' مطمئن هستید؟\n"
                                   "این عملیات غیرقابل بازگشت است."):
            return
        try:
            self.service.delete_part(part_id)
            messagebox.showinfo("موفق", "قطعه با موفقیت حذف شد.")
            self._load()
        except Exception as e:
            messagebox.showerror("خطا", str(e))

    def _stock_in(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً یک قطعه انتخاب کنید.")
            return
        part_id = int(selected[0])
        part = self.service.get_part_by_id(part_id)
        StockTransactionForm(self, self.session, part, "IN", callback=self._load)

    def _stock_out(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً یک قطعه انتخاب کنید.")
            return
        part_id = int(selected[0])
        part = self.service.get_part_by_id(part_id)
        StockTransactionForm(self, self.session, part, "OUT", callback=self._load)

    def _view_history(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً یک قطعه انتخاب کنید.")
            return
        part_id = int(selected[0])
        part = self.service.get_part_by_id(part_id)
        PartTransactionsView(self, self.session, part)

    def _context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.ctx_menu.post(event.x_root, event.y_root)


# ─────────────────────────── Form Dialogs (Persian) ─────────────────────────
class SparePartForm(tk.Toplevel):
    def __init__(self, parent, session, part=None, callback=None):
        super().__init__(parent)
        self.session = session
        self.service = SparePartsService(session)
        self.part = part
        self.callback = callback

        self.title("ویرایش قطعه" if part else "افزودن قطعه جدید")
        self.geometry("550x650")
        self.configure(bg=BG)
        self.resizable(False, False)

        # Center
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (550 // 2)
        y = (self.winfo_screenheight() // 2) - (650 // 2)
        self.geometry(f"+{x}+{y}")

        self._setup_ui()
        if part:
            self._load_data()

    def _setup_ui(self):
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        tk.Label(main, text="🔧 اطلاعات قطعه", font=FONT_TITLE,
                 bg=BG, fg=PRIMARY).pack(pady=(0, 15))

        # Form fields (Persian labels)
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

        self.entries = {}
        row = 0
        for label, field in fields:
            frm = tk.Frame(main, bg=BG)
            frm.pack(fill="x", pady=6)

            tk.Label(frm, text=label, font=FONT_LABEL,
                     bg=BG, fg=TEXT, width=18, anchor="e").pack(side="right", padx=(0, 10))

            if field in ("description", "notes"):
                widget = tk.Text(frm, height=3, font=FONT_INPUT, bg=WHITE, fg=TEXT)
                widget.pack(side="right", fill="x", expand=True)
            else:
                widget = tk.Entry(frm, font=FONT_INPUT, bg=WHITE, fg=TEXT, relief="solid", bd=1)
                widget.pack(side="right", fill="x", expand=True)

            self.entries[field] = widget

        # Buttons
        btn_frame = tk.Frame(main, bg=BG)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="ذخیره", font=FONT_LABEL,
                  bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                  padx=20, pady=6, command=self._save).pack(side="right", padx=8)
        tk.Button(btn_frame, text="انصراف", font=FONT_LABEL,
                  bg=BORDER, fg=TEXT, relief="flat", cursor="hand2",
                  padx=20, pady=6, command=self.destroy).pack(side="right", padx=8)

    def _load_data(self):
        for field, widget in self.entries.items():
            value = getattr(self.part, field, "")
            if value is None:
                value = ""
            if isinstance(widget, tk.Text):
                widget.insert("1.0", str(value))
            else:
                widget.insert(0, str(value))

    def _save(self):
        data = {}
        for field, widget in self.entries.items():
            if isinstance(widget, tk.Text):
                data[field] = widget.get("1.0", "end-1c").strip()
            else:
                data[field] = widget.get().strip()

        if not data["part_number"] or not data["name"]:
            messagebox.showerror("خطا", "شماره قطعه و نام قطعه الزامی هستند.")
            return

        # Convert numeric fields
        try:
            data["min_stock"] = int(data["min_stock"]) if data["min_stock"] else 0
            data["current_stock"] = int(data["current_stock"]) if data["current_stock"] else 0
            data["unit_price"] = float(data["unit_price"]) if data["unit_price"] else 0.0
        except ValueError:
            messagebox.showerror("خطا", "مقادیر عددی نامعتبر هستند.")
            return

        try:
            if self.part:
                self.service.update_part(self.part.id, data)
                messagebox.showinfo("موفق", "قطعه با موفقیت ویرایش شد.")
            else:
                self.service.create_part(data)
                messagebox.showinfo("موفق", "قطعه با موفقیت اضافه شد.")
            if self.callback:
                self.callback()
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", str(e))


class StockTransactionForm(tk.Toplevel):
    def __init__(self, parent, session, part, trans_type, callback=None):
        super().__init__(parent)
        self.session = session
        self.service = SparePartsService(session)
        self.part = part
        self.trans_type = trans_type  # 'IN' or 'OUT'
        self.callback = callback

        title = "ورود به انبار" if trans_type == "IN" else "خروج از انبار"
        self.title(f"{title} - {part.part_number}")
        self.geometry("450x400")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (450 // 2)
        y = (self.winfo_screenheight() // 2) - (400 // 2)
        self.geometry(f"+{x}+{y}")

        self._setup_ui()

    def _setup_ui(self):
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=20, pady=20)

        # Info
        info_frame = tk.Frame(main, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        info_frame.pack(fill="x", pady=(0, 15), ipady=8)
        tk.Label(info_frame, text=f"قطعه: {self.part.name}", font=FONT_LABEL,
                 bg=WHITE, fg=TEXT).pack(pady=2)
        tk.Label(info_frame, text=f"موجودی فعلی: {self.part.current_stock}",
                 font=FONT_INPUT, bg=WHITE, fg=SUBTLE).pack(pady=2)

        # Form
        frm = tk.Frame(main, bg=BG)
        frm.pack(fill="x", pady=10)

        tk.Label(frm, text="تعداد *:", font=FONT_LABEL,
                 bg=BG, fg=TEXT, width=15, anchor="e").pack(side="right", padx=(0, 10))
        self.qty_entry = tk.Entry(frm, font=FONT_INPUT, bg=WHITE, fg=TEXT, relief="solid", bd=1)
        self.qty_entry.pack(side="right", fill="x", expand=True)

        frm2 = tk.Frame(main, bg=BG)
        frm2.pack(fill="x", pady=10)
        tk.Label(frm2, text="مرجع:", font=FONT_LABEL,
                 bg=BG, fg=TEXT, width=15, anchor="e").pack(side="right", padx=(0, 10))
        self.ref_entry = tk.Entry(frm2, font=FONT_INPUT, bg=WHITE, fg=TEXT, relief="solid", bd=1)
        self.ref_entry.pack(side="right", fill="x", expand=True)

        frm3 = tk.Frame(main, bg=BG)
        frm3.pack(fill="x", pady=10)
        tk.Label(frm3, text="توضیحات:", font=FONT_LABEL,
                 bg=BG, fg=TEXT, width=15, anchor="e").pack(side="right", padx=(0, 10))
        self.notes_text = tk.Text(frm3, height=4, font=FONT_INPUT, bg=WHITE, fg=TEXT)
        self.notes_text.pack(side="right", fill="x", expand=True)

        btn_frame = tk.Frame(main, bg=BG)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="ثبت", font=FONT_LABEL,
                  bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                  padx=20, pady=6, command=self._save).pack(side="right", padx=8)
        tk.Button(btn_frame, text="انصراف", font=FONT_LABEL,
                  bg=BORDER, fg=TEXT, relief="flat", cursor="hand2",
                  padx=20, pady=6, command=self.destroy).pack(side="right", padx=8)

    def _save(self):
        try:
            qty = int(self.qty_entry.get().strip())
            if qty <= 0:
                raise ValueError("تعداد باید مثبت باشد")
            if self.trans_type == "OUT" and qty > self.part.current_stock:
                raise ValueError(f"موجودی ناکافی. موجودی فعلی: {self.part.current_stock}")
        except ValueError as e:
            messagebox.showerror("خطا", str(e))
            return

        data = {
            "part_id": self.part.id,
            "transaction_type": self.trans_type,
            "quantity": qty,
            "reference": self.ref_entry.get().strip(),
            "notes": self.notes_text.get("1.0", "end-1c").strip(),
        }

        try:
            self.service.add_stock_transaction(data)
            messagebox.showinfo("موفق", "عملیات انبار با موفقیت ثبت شد.")
            if self.callback:
                self.callback()
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", str(e))


class PartTransactionsView(tk.Toplevel):
    def __init__(self, parent, session, part):
        super().__init__(parent)
        self.session = session
        self.service = SparePartsService(session)
        self.part = part

        self.title(f"تاریخچه تراکنش‌ها - {part.part_number}")
        self.geometry("900x500")
        self.configure(bg=BG)

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (900 // 2)
        y = (self.winfo_screenheight() // 2) - (500 // 2)
        self.geometry(f"+{x}+{y}")

        self._setup_ui()
        self._load()

    def _setup_ui(self):
        # Header
        header = tk.Frame(self, bg=PRIMARY, height=50)
        header.pack(fill="x")
        tk.Label(header, text=f"📋 تاریخچه قطعه: {self.part.name} ({self.part.part_number})",
                 font=FONT_TITLE, bg=PRIMARY, fg=WHITE).pack(pady=10)

        # Table
        frame = tk.Frame(self, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        columns = ("date", "type", "quantity", "reference", "notes")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=20)

        headers = [
            ("date",      "تاریخ",        150, "center"),
            ("type",      "نوع",          80,  "center"),
            ("quantity",  "تعداد",        80,  "center"),
            ("reference", "مرجع",         150, "w"),
            ("notes",     "توضیحات",      300, "w"),
        ]
        for col, text, width, anchor in headers:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="right", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        self.tree.tag_configure("IN", foreground=SUCCESS)
        self.tree.tag_configure("OUT", foreground=DANGER)

        # Close button
        btn = tk.Button(self, text="بستن", font=FONT_LABEL,
                        bg=PRIMARY, fg=WHITE, relief="flat", cursor="hand2",
                        padx=20, pady=6, command=self.destroy)
        btn.pack(pady=10)

    def _load(self):
        transactions = self.service.get_part_transactions(self.part.id)
        for trans in transactions:
            values = (
                trans.created_at.strftime("%Y-%m-%d %H:%M"),
                "ورود" if trans.transaction_type == "IN" else "خروج",
                trans.quantity,
                trans.reference or "—",
                trans.notes or "—",
            )
            item = self.tree.insert("", "end", values=values)
            self.tree.item(item, tags=(trans.transaction_type,))