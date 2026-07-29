# views/pm_view.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from services.pm_service import PMService
from database.db import SessionLocal
from auth.auth_manager import AuthManager
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

# ── Palette (identical to dashboard / equipment_view) ─────────────────────────
CARD_BG     = "#FFFFFF"
CARD_BORDER = "#E8ECF0"
SECTION_BG  = "#F4F6F9"
HEADER_H    = 72
STRIP_H     = 4

ACCENT_NAVY   = NAVY
ACCENT_GREEN  = SUCCESS
ACCENT_AMBER  = "#D97706"
ACCENT_ROSE   = "#DC2626"


class PMView(tk.Frame):
    def __init__(self, parent, pm_repo, equipment_repo, user_repo, current_user):
        super().__init__(parent, bg=SECTION_BG)
        self.pm_repo        = pm_repo
        self.equipment_repo = equipment_repo
        self.user_repo      = user_repo
        self.current_user   = current_user
        self.is_manager     = current_user["role"] in ["admin", "manager"]
        self.can_write      = AuthManager.can_access("pm_schedule", "write")
        self.can_delete     = AuthManager.can_access("pm_schedule", "delete")
        self._service       = PMService(SessionLocal)

        self._filter_var  = tk.StringVar(value="همه")
        self._search_var  = tk.StringVar()
        self._all_records = []

        self._build_ui()
        self._load()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_stats_bar()
        self._build_toolbar()
        self._build_table()
        self._build_action_bar()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=NAVY, height=HEADER_H)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Right: icon + title block
        right = tk.Frame(hdr, bg=NAVY)
        right.pack(side="right", padx=24, fill="y")
        tk.Label(right, text="📅", font=("Tahoma", 20),
                 bg=NAVY, fg=WHITE).pack(side="right", pady=18)
        title_col = tk.Frame(right, bg=NAVY)
        title_col.pack(side="right", padx=(0, 10), fill="y")
        tk.Label(title_col, text="برنامه‌ریزی نگهداری پیشگیرانه",
                 font=FONT_TITLE, bg=NAVY, fg=WHITE).pack(anchor="e", pady=(16, 0))
        tk.Label(title_col, text="مدیریت برنامه‌های پیشگیرانه",
                 font=FONT_SMALL, bg=NAVY, fg=WHITE).pack(anchor="e")

        # Left: action buttons
        left = tk.Frame(hdr, bg=NAVY)
        left.pack(side="left", padx=20, fill="y")
        if self.can_write:
            tk.Button(left, text="➕  برنامه جدید", font=FONT_SMALL,
                      bg=WHITE, fg=NAVY, relief="flat", cursor="hand2",
                      padx=14, pady=6,
                      command=self._add).pack(side="left", padx=4, pady=20)
        tk.Button(left, text="📤  خروجی Excel", font=FONT_SMALL,
                  bg="#0D9488", fg=WHITE, relief="flat", cursor="hand2",
                  padx=14, pady=6,
                  command=self._export).pack(side="left", padx=4, pady=20)

        tk.Frame(self, bg=CARD_BORDER, height=1).pack(fill="x")

    # ── Stats bar ─────────────────────────────────────────────────────────────
    def _build_stats_bar(self):
        self._stats_frame = tk.Frame(self, bg=SECTION_BG)
        self._stats_frame.pack(fill="x", padx=20, pady=(16, 0))

    def _refresh_stats(self, stats: dict):
        for w in self._stats_frame.winfo_children():
            w.destroy()

        cards = [
            ("📋", "کل برنامه‌ها", stats.get("total", 0),   CARD_BG,    ACCENT_NAVY,  "#DBEAFE"),
            ("🔴", "عقب‌افتاده",   stats.get("overdue", 0),  "#FEE2E2",  ACCENT_ROSE,  ACCENT_ROSE),
            ("🟡", "این هفته",     stats.get("upcoming", 0), "#FEF3C7",  ACCENT_AMBER, ACCENT_AMBER),
        ]
        for icon, label, value, bg_color, fg_color, strip_color in cards:
            shadow = tk.Frame(self._stats_frame, bg=CARD_BORDER)
            shadow.pack(side="right", padx=6)
            card = tk.Frame(shadow, bg=bg_color)
            card.pack(fill="both", expand=True, padx=1, pady=1)
            tk.Frame(card, bg=strip_color, height=STRIP_H).pack(fill="x")
            inner = tk.Frame(card, bg=bg_color)
            inner.pack(padx=18, pady=8)
            top = tk.Frame(inner, bg=bg_color)
            top.pack(fill="x")
            tk.Label(top, text=icon, font=("Tahoma", 14),
                     bg=bg_color, fg=fg_color).pack(side="right")
            tk.Label(top, text=label, font=FONT_SMALL,
                     bg=bg_color, fg=TEXT_LIGHT).pack(side="right", padx=(0, 4))
            tk.Label(inner, text=str(value), font=FONT_HEADING,
                     bg=bg_color, fg=fg_color).pack(anchor="center", pady=(4, 0))

    # ── Toolbar ───────────────────────────────────────────────────────────────
    def _build_toolbar(self):
        # Section label
        row = tk.Frame(self, bg=SECTION_BG)
        row.pack(fill="x", padx=20, pady=(18, 6))
        tk.Label(row, text="📋  لیست برنامه‌های PM",
                 font=FONT_HEADING, bg=SECTION_BG, fg=TEXT_DARK).pack(side="right")
        tk.Frame(row, bg=CARD_BORDER, height=1).pack(
            side="right", fill="x", expand=True, padx=(0, 12), pady=8)

        # Filter + search inside a card
        outer = tk.Frame(self, bg=CARD_BORDER)
        outer.pack(fill="x", padx=20, pady=(0, 10))
        bar = tk.Frame(outer, bg=CARD_BG)
        bar.pack(fill="x", padx=1, pady=1)
        inner = tk.Frame(bar, bg=CARD_BG)
        inner.pack(fill="x", padx=16, pady=10)

        # Filter radio buttons on the right
        filter_wrap = tk.Frame(inner, bg=CARD_BG)
        filter_wrap.pack(side="right")
        tk.Label(filter_wrap, text="فیلتر:", font=FONT_SMALL,
                 bg=CARD_BG, fg=TEXT_LIGHT).pack(side="right", padx=(0, 8))
        for label in ("همه", "عقب‌افتاده", "این هفته", "فعال", "غیرفعال"):
            tk.Radiobutton(
                filter_wrap, text=label, variable=self._filter_var,
                value=label, font=FONT_SMALL,
                bg=CARD_BG, fg=TEXT_DARK,
                selectcolor=SECTION_BG, activebackground=CARD_BG,
                command=self._apply_filter
            ).pack(side="right", padx=4)

        # Separator
        tk.Frame(inner, bg=CARD_BORDER, width=1).pack(
            side="right", fill="y", padx=12, pady=4)

        # Search on the left
        search_wrap = tk.Frame(inner, bg=CARD_BG)
        search_wrap.pack(side="left")
        tk.Label(search_wrap, text="🔍", font=FONT_NORMAL,
                 bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left")
        tk.Entry(search_wrap, textvariable=self._search_var, font=FONT_NORMAL,
                 bg=SECTION_BG, relief="solid", bd=1,
                 width=26).pack(side="left", padx=6, ipady=5)
        tk.Button(search_wrap, text="جستجو", font=FONT_SMALL,
                  bg=NAVY, fg=WHITE, relief="flat", cursor="hand2",
                  padx=10, pady=4,
                  command=self._apply_filter).pack(side="left")

        # Row count badge
        self._row_count_lbl = tk.Label(
            inner, text="", font=FONT_SMALL,
            bg=NAVY, fg=WHITE, padx=10, pady=2)
        self._row_count_lbl.pack(side="left", padx=(12, 0))

    # ── Table ─────────────────────────────────────────────────────────────────
    def _build_table(self):
        outer = tk.Frame(self, bg=CARD_BORDER)
        outer.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        card = tk.Frame(outer, bg=CARD_BG)
        card.pack(fill="both", expand=True, padx=1, pady=1)

        cols = ("id", "title", "equipment", "technician",
                "frequency", "last_done", "next_due", "days_until", "status")
        headers = {
            "id":         ("شناسه",         55),
            "title":      ("عنوان برنامه",  200),
            "equipment":  ("تجهیز",         160),
            "technician": ("تکنسین",        120),
            "frequency":  ("دوره",           90),
            "last_done":  ("آخرین انجام",   110),
            "next_due":   ("سررسید بعدی",   110),
            "days_until": ("روز مانده",      80),
            "status":     ("وضعیت",          100),
        }

        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=16)

        style = ttk.Style()
        style.configure("PM.Treeview",
                        font=FONT_NORMAL, rowheight=30,
                        background=CARD_BG, fieldbackground=CARD_BG,
                        foreground=TEXT_DARK)
        style.configure("PM.Treeview.Heading",
                        font=FONT_NORMAL, background=NAVY,
                        foreground=WHITE, relief="flat")
        style.map("PM.Treeview",
                  background=[("selected", NAVY)],
                  foreground=[("selected", WHITE)])
        self.tree.configure(style="PM.Treeview")

        for col in cols:
            text, width = headers[col]
            self.tree.heading(col, text=text,
                              command=lambda c=col: self._sort(c))
            self.tree.column(col, width=width, anchor="center")

        # Row colour tags
        self.tree.tag_configure("overdue",  background="#FEE2E2", foreground=ACCENT_ROSE)
        self.tree.tag_configure("upcoming", background="#FEF3C7", foreground=ACCENT_AMBER)
        self.tree.tag_configure("ok",       background="#D1FAE5", foreground="#065F46")
        self.tree.tag_configure("inactive", background=CARD_BORDER, foreground=TEXT_LIGHT)

        vsb = ttk.Scrollbar(card, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(card, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        card.rowconfigure(0, weight=1)
        card.columnconfigure(0, weight=1)

        # Bindings
        self.tree.configure(selectmode="extended")
        self.tree.bind("<Double-1>",  lambda e: self._edit())
        self.tree.bind("<Delete>",    lambda e: self._delete_selected())
        self.tree.bind("<F2>",        lambda e: self._edit_selected())
        self.tree.bind("<Control-n>", lambda e: self._add())
        self._build_context_menu()

    # ── Action bar (bottom) ───────────────────────────────────────────────────
    def _build_action_bar(self):
        outer = tk.Frame(self, bg=CARD_BORDER)
        outer.pack(fill="x", padx=20, pady=(0, 20))
        bar = tk.Frame(outer, bg=CARD_BG)
        bar.pack(fill="x", padx=1, pady=1)
        inner = tk.Frame(bar, bg=CARD_BG)
        inner.pack(fill="x", padx=16, pady=10)

        if self.can_write:
            tk.Button(inner, text="✏️  ویرایش", font=FONT_NORMAL,
                      bg=NAVY, fg=WHITE, relief="flat", cursor="hand2",
                      padx=16, pady=8,
                      command=self._edit).pack(side="right", padx=4)
            tk.Button(inner, text="✅  ثبت انجام PM", font=FONT_NORMAL,
                      bg=ACCENT_GREEN, fg=WHITE, relief="flat", cursor="hand2",
                      padx=16, pady=8,
                      command=self._mark_done).pack(side="right", padx=4)
            tk.Button(inner, text="🔁  فعال / غیرفعال", font=FONT_NORMAL,
                      bg=ACCENT_AMBER, fg=WHITE, relief="flat", cursor="hand2",
                      padx=16, pady=8,
                      command=self._toggle).pack(side="right", padx=4)
        if self.can_delete:
            tk.Button(inner, text="🗑️  حذف", font=FONT_NORMAL,
                      bg=ACCENT_ROSE, fg=WHITE, relief="flat", cursor="hand2",
                      padx=16, pady=8,
                      command=self._delete).pack(side="right", padx=4)

        tk.Label(inner, text="F2: ویرایش  |  Del: حذف  |  Ctrl+N: افزودن",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left")

    # ── Context menu ──────────────────────────────────────────────────────────
    def _build_context_menu(self):
        self._menu = tk.Menu(self, tearoff=0, font=FONT_NORMAL)
        if self.can_write:
            self._menu.add_command(label="✏️  ویرایش",           command=self._edit)
            self._menu.add_command(label="✅  ثبت انجام PM",      command=self._mark_done)
            self._menu.add_separator()
            self._menu.add_command(label="🔁  تغییر وضعیت فعال", command=self._toggle)
        if self.can_delete:
            self._menu.add_separator()
            self._menu.add_command(label="🗑️  حذف",              command=self._delete)
        self.tree.bind("<Button-3>", self._show_menu)

    def _show_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            try:
                self._menu.post(event.x_root, event.y_root)
            finally:
                self._menu.grab_release()

    # ── Keyboard helpers ──────────────────────────────────────────────────────
    def _delete_selected(self):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف برنامه‌ها نیستید.", parent=self)
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً برنامه‌ای انتخاب کنید.")
            return
        if messagebox.askyesno("حذف", "آیا از حذف برنامه‌های انتخاب‌شده مطمئن هستید؟"):
            for sid in selected:
                self.pm_repo.delete(int(sid))
            self._load()

    def _edit_selected(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ویرایش برنامه PM نیستید.", parent=self)
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً برنامه‌ای انتخاب کنید.")
            return
        sid = int(selected[0])
        record = self.pm_repo.get_by_id(sid)
        if record:
            from views.pm_dialog import PMDialog
            dlg = PMDialog(self, self.pm_repo, self.equipment_repo,
                           self.user_repo, schedule=record)
            self.wait_window(dlg)
            if dlg.result:
                self._load()

    # ── Data / actions ───────────────────────────────────────────────
    def _load(self):
        self._all_records = self.pm_repo.get_all()
        stats = self.pm_repo.get_stats()
        self._refresh_stats(stats)
        self._apply_filter()

    def _apply_filter(self):
        f      = self._filter_var.get()
        search = self._search_var.get().strip().lower()
        filtered = []
        for r in self._all_records:
            if f == "عقب‌افتاده" and not r["is_overdue"]:
                continue
            if f == "این هفته":
                du = r.get("days_until")
                if du is None or du < 0 or du > 7:
                    continue
            if f == "فعال"    and not r["is_active"]:
                continue
            if f == "غیرفعال" and r["is_active"]:
                continue
            if search:
                haystack = (r["title"] + r["equipment_name"] + r["technician_name"]).lower()
                if search not in haystack:
                    continue
            filtered.append(r)
        self._populate(filtered)

    def _populate(self, records: list):
        self.tree.delete(*self.tree.get_children())
        freq_fa = {
            "daily":     "روزانه",
            "weekly":    "هفتگی",
            "monthly":   "ماهانه",
            "quarterly": "سه‌ماهه",
            "biannual":  "شش‌ماهه",
            "annual":    "سالانه",
            "custom":    "سفارشی",
        }
        for r in records:
            days = r.get("days_until")
            if not r["is_active"]:
                status_text, tag = "غیرفعال", "inactive"
            elif r["is_overdue"]:
                status_text, tag = "عقب‌افتاده", "overdue"
            elif days is not None and 0 <= days <= 7:
                status_text, tag = "این هفته", "upcoming"
            else:
                status_text, tag = "به‌موقع", "ok"

            days_text = str(days) if days is not None else "-"

            last_done = r.get("last_done", "")
            if last_done and last_done != "انجام نشده":
                try:
                    last_done = datetime.strptime(last_done, "%Y-%m-%d").strftime("%Y-%m-%d")
                except Exception:
                    pass

            next_due = r.get("next_due", "")
            if next_due:
                try:
                    next_due = datetime.strptime(next_due, "%Y-%m-%d").strftime("%Y-%m-%d")
                except Exception:
                    pass

            self.tree.insert("", "end", iid=str(r["id"]), tags=(tag,),
                             values=(
                                 r["id"],
                                 r["title"],
                                 f"{r['equipment_code']} - {r['equipment_name']}",
                                 r["technician_name"],
                                 freq_fa.get(r["frequency"], r["frequency"]),
                                 last_done,
                                 next_due,
                                 days_text,
                                 status_text,
                             ))

        count = len(records)
        self._row_count_lbl.config(
            text=f"  {count} برنامه  " if count else "  بدون نتیجه  ")

    def _sort(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        items.sort()
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("انتخاب", "لطفاً یک برنامه انتخاب کنید.")
            return None
        return int(sel[0])

    def _add(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به افزودن برنامه PM نیستید.", parent=self)
            return
        from views.pm_dialog import PMDialog
        dlg = PMDialog(self, self.pm_repo, self.equipment_repo, self.user_repo)
        self.wait_window(dlg)
        if dlg.result:
            self._load()

    def _edit(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ویرایش برنامه PM نیستید.", parent=self)
            return
        sid = self._selected_id()
        if sid is None:
            return
        record = self.pm_repo.get_by_id(sid)
        if not record:
            return
        from views.pm_dialog import PMDialog
        dlg = PMDialog(self, self.pm_repo, self.equipment_repo,
                       self.user_repo, schedule=record)
        self.wait_window(dlg)
        if dlg.result:
            self._load()

    def _mark_done(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ثبت انجام PM نیستید.", parent=self)
            return
        sid = self._selected_id()
        if sid is None:
            return
        if messagebox.askyesno("ثبت انجام", "آیا این PM انجام شده است؟"):
            ok, msg = self.pm_repo.mark_done(sid, datetime.now())
            if ok:
                self._load()
            else:
                messagebox.showerror("خطا", msg)

    def _toggle(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به تغییر وضعیت PM نیستید.", parent=self)
            return
        sid = self._selected_id()
        if sid is None:
            return
        self.pm_repo.toggle_active(sid)
        self._load()

    def _delete(self):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف برنامه PM نیستید.", parent=self)
            return
        sid = self._selected_id()
        if sid is None:
            return
        if messagebox.askyesno("حذف", "آیا از حذف این برنامه مطمئن هستید؟"):
            self.pm_repo.delete(sid)
            self._load()

    def _export(self):
        from views.export_dialog import run_pm_export
        selected_pm = None
        sel = self.tree.selection()
        if sel:
            sid = int(sel[0])
            selected_pm = self.pm_repo.get_by_id(sid)
        run_pm_export(self, self._all_records, selected_pm=selected_pm)