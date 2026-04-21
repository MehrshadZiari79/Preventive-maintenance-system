"""
PM Schedule View - Preventive Maintenance Schedule Management
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from services.pm_service import PMService
from views.export_dialog import run_pm_export
try:
    import jdatetime
    HAS_JDATETIME = True
except ImportError:
    HAS_JDATETIME = False

# ─────────────────────────── Theme ───────────────────────────
BG         = "#F0F4F8"
WHITE      = "#FFFFFF"
HEADER_BG  = "#1A73E8"
SIDEBAR_BG = "#E8F0FE"
TEXT       = "#202124"
SUBTLE     = "#5F6368"
BORDER     = "#DADCE0"
RED        = "#D93025"
GREEN      = "#1E8E3E"
ORANGE     = "#F29900"
YELLOW_BG  = "#FFF8E1"
RED_BG     = "#FCE8E6"
GREEN_BG   = "#E6F4EA"

FONT_TITLE  = ("Tahoma", 14, "bold")
FONT_LABEL  = ("Tahoma", 10, "bold")
FONT_INPUT  = ("Tahoma", 10)
FONT_SMALL  = ("Tahoma", 9)
FONT_STAT   = ("Tahoma", 18, "bold")


def _to_jalali(date_str: str) -> str:
    if not date_str or date_str in ("انجام نشده", ""):
        return date_str
    if not HAS_JDATETIME:
        return date_str
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        jd = jdatetime.date.fromgregorian(date=dt.date())
        return jd.strftime("%Y/%m/%d")
    except Exception:
        return date_str


class PMView(tk.Frame):
    def __init__(self, parent, pm_repo, equipment_repo, user_repo, current_user):
        super().__init__(parent, bg=BG)
        self.pm_repo        = pm_repo
        self.equipment_repo = equipment_repo
        self.user_repo      = user_repo
        self.current_user   = current_user
        self._service       = PMService()

        self._filter_var  = tk.StringVar(value="همه")
        self._search_var  = tk.StringVar()
        self._all_records = []

        self._build_ui()
        self._load()

    # ═══════════════════════════ UI BUILD ═══════════════════════════

    def _build_ui(self):
        self._build_header()
        self._build_stats_bar()
        self._build_toolbar()
        self._build_table()

    def _build_header(self):
        hdr = tk.Frame(self, bg=HEADER_BG, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="📅  برنامه‌ریزی نگهداری پیشگیرانه (PM)",
                 font=FONT_TITLE, bg=HEADER_BG, fg=WHITE).pack(
            side="right", padx=20, pady=14)

        tk.Button(hdr, text="➕  برنامه جدید", font=FONT_LABEL,
                  bg=WHITE, fg=HEADER_BG, relief="flat",
                  padx=14, pady=6, cursor="hand2",
                  command=self._add).pack(side="left", padx=16, pady=12)

        tk.Button(hdr, text="🔄  ایجاد دستورکارها", font=FONT_LABEL,
                  bg=WHITE, fg=HEADER_BG, relief="flat",
                  padx=14, pady=6, cursor="hand2",
                  command=self._generate_work_orders).pack(side="left", padx=8, pady=12)

        tk.Button(hdr, text="📤  خروجی Excel / PDF", font=FONT_LABEL,
                  bg="#34A853", fg=WHITE, relief="flat",
                  padx=14, pady=6, cursor="hand2",
                  command=self._export).pack(side="left", padx=8, pady=12)

    def _export(self):
        from views.export_dialog import run_pm_export
        selected_pm = None
        sel = self.tree.selection()
        if sel:
            sid = int(sel[0])
            selected_pm = self.pm_repo.get_by_id(sid)
        run_pm_export(self, self._all_records, selected_pm=selected_pm)

    def _generate_work_orders(self):
        """Generate work orders for all due PM schedules."""
        if not messagebox.askyesno("تایید", "آیا می‌خواهید دستورکارهای سررسید را ایجاد کنید؟"):
            return

        try:
            created, skipped, errors = self._service.generate_due_work_orders()

            msg_parts = [f"✅ {created} دستورکار جدید ایجاد شد"]
            if skipped > 0:
                msg_parts.append(f"⏭️ {skipped} دستورکار تکراری رد شد")
            if errors:
                msg_parts.append(f"\n❌ خطاها:\n" + "\n".join(errors[:5]))

            messagebox.showinfo("نتیجه", "\n".join(msg_parts))
            self._load()
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ایجاد دستورکارها:\n{e}")

    def _build_stats_bar(self):
        self._stats_frame = tk.Frame(self, bg=BG)
        self._stats_frame.pack(fill="x", padx=20, pady=(14, 0))

    def _refresh_stats(self, stats: dict):
        for w in self._stats_frame.winfo_children():
            w.destroy()

        cards = [
            ("📋", "کل برنامه‌ها", stats.get("total", 0),    WHITE,    HEADER_BG),
            ("🔴", "عقب‌افتاده",   stats.get("overdue", 0),  RED_BG,   RED),
            ("🟡", "این هفته",     stats.get("upcoming", 0), YELLOW_BG, ORANGE),
        ]
        for icon, label, value, bg, fg in cards:
            card = tk.Frame(self._stats_frame, bg=bg, relief="solid", bd=1)
            card.pack(side="right", padx=6, ipadx=18, ipady=10)
            tk.Label(card, text=f"{icon}  {label}", font=FONT_SMALL,
                     bg=bg, fg=SUBTLE).pack()
            tk.Label(card, text=str(value), font=FONT_STAT,
                     bg=bg, fg=fg).pack()

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=20, pady=10)

        filter_frame = tk.Frame(bar, bg=BG)
        filter_frame.pack(side="right")

        for label in ("همه", "عقب‌افتاده", "این هفته", "فعال", "غیرفعال"):
            tk.Radiobutton(
                filter_frame, text=label, variable=self._filter_var,
                value=label, font=FONT_SMALL, bg=BG, fg=TEXT,
                selectcolor=SIDEBAR_BG, activebackground=BG,
                command=self._apply_filter
            ).pack(side="right", padx=4)

        search_frame = tk.Frame(bar, bg=BG)
        search_frame.pack(side="left")
        tk.Label(search_frame, text="🔍", font=FONT_INPUT,
                 bg=BG).pack(side="left")
        tk.Entry(search_frame, textvariable=self._search_var,
                 font=FONT_INPUT, width=28, relief="solid", bd=1).pack(
            side="left", padx=4)
        tk.Button(search_frame, text="جستجو", font=FONT_SMALL,
                  bg=BORDER, fg=TEXT, relief="flat", padx=8,
                  cursor="hand2", command=self._apply_filter).pack(side="left")

    def _build_table(self):
        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        cols = ("id", "title", "equipment", "technician",
                "frequency", "last_done", "next_due", "days_until", "status")
        headers = {
            "id":         ("شناسه",          50),
            "title":      ("عنوان برنامه",   200),
            "equipment":  ("تجهیز",          160),
            "technician": ("تکنسین",         120),
            "frequency":  ("دوره",            90),
            "last_done":  ("آخرین انجام",    110),
            "next_due":   ("سررسید بعدی",    110),
            "days_until": ("روز مانده",       80),
            "status":     ("وضعیت",           90),
        }

        self.tree = ttk.Treeview(container, columns=cols,
                                 show="headings", height=18)

        style = ttk.Style()
        style.configure("Treeview", font=FONT_INPUT, rowheight=28,
                        background=WHITE, fieldbackground=WHITE)
        style.configure("Treeview.Heading", font=FONT_LABEL)
        style.map("Treeview", background=[("selected", HEADER_BG)],
                  foreground=[("selected", WHITE)])

        for col in cols:
            text, width = headers[col]
            self.tree.heading(col, text=text,
                              command=lambda c=col: self._sort(c))
            self.tree.column(col, width=width, anchor="center")

        self.tree.tag_configure("overdue",  background=RED_BG,    foreground=RED)
        self.tree.tag_configure("upcoming", background=YELLOW_BG, foreground=ORANGE)
        self.tree.tag_configure("ok",       background=GREEN_BG,  foreground=GREEN)
        self.tree.tag_configure("inactive", background=BORDER,    foreground=SUBTLE)

        vsb = ttk.Scrollbar(container, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", lambda e: self._edit())
        self._build_context_menu()

    def _build_context_menu(self):
        self._menu = tk.Menu(self, tearoff=0, font=FONT_INPUT)
        self._menu.add_command(label="✏️  ویرایش",           command=self._edit)
        self._menu.add_command(label="✅  ثبت انجام PM",     command=self._mark_done)
        self._menu.add_separator()
        self._menu.add_command(label="🔁  تغییر وضعیت فعال", command=self._toggle)
        self._menu.add_separator()
        self._menu.add_command(label="🗑️  حذف",              command=self._delete)
        self.tree.bind("<Button-3>", self._show_menu)

    def _show_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self._menu.post(event.x_root, event.y_root)

    # ═══════════════════════════ DATA ═══════════════════════════════

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
                haystack = (
                    r["title"] + r["equipment_name"] + r["technician_name"]
                ).lower()
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

            self.tree.insert("", "end", iid=str(r["id"]), tags=(tag,),
                             values=(
                                 r["id"],
                                 r["title"],
                                 f"{r['equipment_code']} - {r['equipment_name']}",
                                 r["technician_name"],
                                 freq_fa.get(r["frequency"], r["frequency"]),
                                 _to_jalali(r["last_done"] or ""),
                                 _to_jalali(r["next_due"] or ""),
                                 days_text,
                                 status_text,
                             ))

    def _sort(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        items.sort()
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

    # ═══════════════════════════ ACTIONS ════════════════════════════

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("انتخاب", "لطفاً یک برنامه انتخاب کنید.")
            return None
        return int(sel[0])

    def _add(self):
        from views.pm_dialog import PMDialog
        dlg = PMDialog(self, self.pm_repo, self.equipment_repo, self.user_repo)
        self.wait_window(dlg)
        if dlg.result:
            self._load()

    def _edit(self):
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
        sid = self._selected_id()
        if sid is None:
            return
        if messagebox.askyesno("ثبت انجام", "آیا این PM انجام شده است؟"):
            ok, msg = self.pm_repo.mark_done(sid, datetime.utcnow())
            if ok:
                self._load()
            else:
                messagebox.showerror("خطا", msg)

    def _toggle(self):
        sid = self._selected_id()
        if sid is None:
            return
        self.pm_repo.toggle_active(sid)
        self._load()

    def _delete(self):
        sid = self._selected_id()
        if sid is None:
            return
        if messagebox.askyesno("حذف", "آیا از حذف این برنامه مطمئن هستید؟"):
            self.pm_repo.delete(sid)
            self._load()