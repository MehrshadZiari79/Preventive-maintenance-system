# views/spare_parts_view.py
import tkinter as tk
from tkinter import ttk, messagebox
from services.spare_parts_service import SparePartsService
from views.export_dialog import run_spare_parts_export
from auth.auth_manager import AuthManager
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
WARNING = WARNING
TEXT = TEXT_DARK
SUBTLE = TEXT_LIGHT
BORDER = GRAY_BORDER

class SparePartsView(ttk.Frame):
    def __init__(self, parent, session_factory, current_user):
        super().__init__(parent)
        self.session_factory = session_factory
        self.service = SparePartsService(session_factory)
        self.current_user = current_user
        self.can_manage = (current_user["role"] in ["admin", "manager", "technician"]
                           or AuthManager.can_access("spare_parts", "write"))

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
        self.tree.bind("<Delete>", lambda e: self._delete_selected())
        self.tree.bind("<F2>",      lambda e: self._edit_part() if self.can_manage else self._view_history())
        self.tree.bind("<Control-n>", lambda e: self._add_part())

        style = ttk.Style()
        style.configure("Treeview", background=CARD_BG, fieldbackground=CARD_BG, foreground=TEXT, rowheight=26)
        style.configure("Treeview.Heading", background=PRIMARY, foreground=WHITE, font=FONT_NORMAL)
        style.map("Treeview", background=[("selected", PRIMARY)], foreground=[("selected", WHITE)])

        self.tree.bind("<Button-3>", self._context_menu)
        self.tree.bind("<Double-1>", lambda e: self._edit_part() if self.can_manage else self._view_history())

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
        if not self.can_manage:
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
        if not self.can_manage:
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
            menu.add_separator()
            menu.add_command(label="🗑️ حذف", command=self._delete_part)
        else:
            menu.add_command(label="🔍 مشاهده تاریخچه", command=self._view_history)
        menu.post(event.x_root, event.y_root)


class SparePartForm(tk.Toplevel):
    def __init__(self, parent, session_factory, part=None, callback=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.service = SparePartsService(session_factory)
        self.part = part
        self.callback = callback

        self.title("ویرایش قطعه" if part else "افزودن قطعه جدید")
        self.geometry("600x700")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.update_idletasks()
        x = (self.winfo_screenwidth() - 600) // 2
        y = (self.winfo_screenheight() - 700) // 2
        self.geometry(f"+{x}+{y}")

        self._setup_ui()
        if part:
            self._load_data()

    def _setup_ui(self):
        # ── Header ──────────────────────────────────────────────
        header = tk.Frame(self, bg=PRIMARY, height=50)
        header.pack(fill="x")
        title = "✏️ ویرایش قطعه" if self.part else "➕ افزودن قطعه جدید"
        tk.Label(header, text=title, font=FONT_HEADING, bg=PRIMARY, fg=WHITE).pack(pady=12)

        # ── Scrollable area ────────────────────────────────────
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=BG)

        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        vsb.pack(side="right", fill="y")

        # ── Form inside scrollable ─────────────────────────────
        main = tk.Frame(scrollable, bg=CARD_BG, padx=20, pady=20)
        main.pack(fill="both", expand=True)

        tk.Label(main, text="🔧 اطلاعات قطعه", font=FONT_TITLE, bg=CARD_BG, fg=PRIMARY).pack(pady=(0,15))

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
        for label, field in fields:
            frm = tk.Frame(main, bg=CARD_BG)
            frm.pack(fill="x", pady=6)
            tk.Label(frm, text=label, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, width=18, anchor="e").pack(side="right", padx=(0,10))
            if field in ("description", "notes"):
                widget = tk.Text(frm, height=3, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1)
                widget.pack(side="right", fill="x", expand=True)
            else:
                widget = tk.Entry(frm, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1)
                widget.pack(side="right", fill="x", expand=True)
            self.entries[field] = widget

        # ── Buttons ──────────────────────────────────────────────
        btn_frame = tk.Frame(main, bg=CARD_BG)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="ذخیره", font=FONT_NORMAL,
                  bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                  padx=20, pady=6, command=self._save).pack(side="right", padx=8)
        tk.Button(btn_frame, text="انصراف", font=FONT_NORMAL,
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
    def __init__(self, parent, session_factory, part, trans_type, work_order_id=None, callback=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.service = SparePartsService(session_factory)
        self.part = part
        self.trans_type = trans_type
        self.work_order_id = work_order_id
        self.callback = callback

        title = "ورود به انبار" if trans_type == "IN" else "خروج از انبار"
        self.title(f"{title} - {part.part_number}")
        self.geometry("500x500")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.update_idletasks()
        x = (self.winfo_screenwidth() - 500) // 2
        y = (self.winfo_screenheight() - 500) // 2
        self.geometry(f"+{x}+{y}")

        self._setup_ui()

    def _setup_ui(self):
        header = tk.Frame(self, bg=PRIMARY, height=45)
        header.pack(fill="x")
        act = "📥 ورود به انبار" if self.trans_type == "IN" else "📤 خروج از انبار"
        tk.Label(header, text=act, font=FONT_HEADING, bg=PRIMARY, fg=WHITE).pack(pady=10)

        main = tk.Frame(self, bg=CARD_BG)
        main.pack(fill="both", expand=True, padx=20, pady=20)

        info_card = tk.Frame(main, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        info_card.pack(fill="x", pady=(0,15), ipady=8)
        tk.Label(info_card, text=f"قطعه: {self.part.name}", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).pack(pady=2)
        tk.Label(info_card, text=f"موجودی فعلی: {self.part.current_stock}", font=FONT_NORMAL, bg=CARD_BG, fg=SUBTLE).pack(pady=2)

        frm = tk.Frame(main, bg=CARD_BG)
        frm.pack(fill="x", pady=10)
        tk.Label(frm, text="تعداد *:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, width=15, anchor="e").pack(side="right", padx=(0,10))
        self.qty_entry = tk.Entry(frm, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1)
        self.qty_entry.pack(side="right", fill="x", expand=True)

        if self.trans_type == 'IN':
            frm_price = tk.Frame(main, bg=CARD_BG)
            frm_price.pack(fill="x", pady=10)
            tk.Label(frm_price, text="قیمت واحد (تومان):", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, width=15, anchor="e").pack(side="right", padx=(0,10))
            self.price_entry = tk.Entry(frm_price, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1)
            self.price_entry.pack(side="right", fill="x", expand=True)
            self.price_entry.insert(0, str(self.part.unit_price))

        frm2 = tk.Frame(main, bg=CARD_BG)
        frm2.pack(fill="x", pady=10)
        tk.Label(frm2, text="مرجع:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, width=15, anchor="e").pack(side="right", padx=(0,10))
        self.ref_entry = tk.Entry(frm2, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1)
        self.ref_entry.pack(side="right", fill="x", expand=True)

        frm3 = tk.Frame(main, bg=CARD_BG)
        frm3.pack(fill="x", pady=10)
        tk.Label(frm3, text="توضیحات:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, width=15, anchor="e").pack(side="right", padx=(0,10))
        self.notes_text = tk.Text(frm3, height=4, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1)
        self.notes_text.pack(side="right", fill="x", expand=True)

        btn_frame = tk.Frame(main, bg=CARD_BG)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="ثبت", font=FONT_NORMAL,
                  bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                  padx=20, pady=6, command=self._save).pack(side="right", padx=8)
        tk.Button(btn_frame, text="انصراف", font=FONT_NORMAL,
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
        batch_price = None
        if self.trans_type == "IN" and hasattr(self, 'price_entry'):
            try:
                batch_price = float(self.price_entry.get().strip())
            except:
                pass

        try:
            self.service.add_stock_transaction(data, work_order_id=self.work_order_id, batch_price=batch_price)
            messagebox.showinfo("موفق", "عملیات انبار با موفقیت ثبت شد.")
            if self.callback:
                self.callback()
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطا", str(e))


class PartTransactionsView(tk.Toplevel):
    def __init__(self, parent, session_factory, part):
        super().__init__(parent)
        self.session_factory = session_factory
        self.service = SparePartsService(session_factory)
        self.part = part

        self.title(f"تاریخچه تراکنش‌ها - {part.part_number}")
        self.geometry("1000x500")
        self.configure(bg=BG)

        self.update_idletasks()
        x = (self.winfo_screenwidth() - 1000) // 2
        y = (self.winfo_screenheight() - 500) // 2
        self.geometry(f"+{x}+{y}")

        self._setup_ui()
        self._load()

    def _setup_ui(self):
        header = tk.Frame(self, bg=PRIMARY, height=50)
        header.pack(fill="x")
        tk.Label(header, text=f"📋 تاریخچه قطعه: {self.part.name} ({self.part.part_number})",
                 font=FONT_TITLE, bg=PRIMARY, fg=WHITE).pack(pady=10)

        frame = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        columns = ("date", "type", "quantity", "price", "reference", "notes")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=20)
        headers = [
            ("date",      "تاریخ",        150, "center"),
            ("type",      "نوع",          80,  "center"),
            ("quantity",  "تعداد",        80,  "center"),
            ("price",     "قیمت واحد",    150, "center"),
            ("reference", "مرجع",         200, "w"),
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

        tk.Button(self, text="بستن", font=FONT_NORMAL,
                  bg=PRIMARY, fg=WHITE, relief="flat", cursor="hand2",
                  padx=20, pady=6, command=self.destroy).pack(pady=10)

    def _load(self):
        transactions = self.service.get_part_transactions(self.part.id)
        for trans in transactions:
            price_text = f"{trans.batch_price:,.0f}" if trans.batch_price else "—"
            values = (
                trans.created_at.strftime("%Y-%m-%d %H:%M"),
                "ورود" if trans.transaction_type == "IN" else "خروج",
                trans.quantity,
                price_text,
                trans.reference or "—",
                trans.notes or "—",
            )
            item = self.tree.insert("", "end", values=values)
            self.tree.item(item, tags=(trans.transaction_type,))