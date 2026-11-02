# views/machine_hours_view.py
"""
ساعات کارکرد تجهیزات - Machine hours page (rebuilt).

What it does
------------
* Per equipment, per day: planned hours, operating hours, downtime hours and
  output units (all columns already exist in production_logs - no schema
  change).
* Availability (دسترس‌پذیری) = operating / planned, per day and for the
  selected period.
* Searchable equipment picker, Jalali date range with quick ranges, KPI
  tiles, colour-coded table, Excel export, add / edit / delete.

What it deliberately does NOT change
------------------------------------
* Text entry widgets are the same classes as before (ttk.Combobox,
  ttk.Entry, JalaliDateEntry), so Persian typing behaves exactly as in v2.3.
* Permissions: AuthManager.can_access("machine_hours", "write"/"delete").
* The global ttk theme is never switched from this page.

Bugs fixed compared with v2.3
-----------------------------
* Editing a record's date was silently ignored (update_log never saved it).
* Adding a record on a day that already had one silently overwrote it; the
  user is now asked first.
* The default "from" date was the 1st of the GREGORIAN month; it is now the
  1st of the current Jalali month (Tehran time).
* Records with a time component on the last day of the range were dropped.
* downtime_hours existed in the database but could not be entered.
"""

from __future__ import annotations

import tkinter as tk
from datetime import timedelta
from tkinter import ttk, messagebox, filedialog

from auth.auth_manager import AuthManager
from database.db import SessionLocal
from database.equipment_repository import EquipmentRepository
from database.production_log_repository import ProductionLogRepository
from utils.date_helpers import (
    tehran_today, jalali_month_start, jalali_year_start,
    to_jalali_date_str, jalali_weekday_name,
)
from utils.theme import (
    NAVY, WHITE, GRAY_BG, TEXT_DARK, TEXT_MUTED, BORDER, ACCENT,
    SUCCESS, WARNING, DANGER, SUCCESS_SOFT, WARNING_SOFT, DANGER_SOFT,
    SURFACE_ALT, FONT_NORMAL, FONT_BOLD, FONT_SMALL, FONT_HEADING,
    latin_digits, fmt_number, ensure_theme,
)
from views.jalali_date_entry import JalaliDateEntry
from views.ui_kit import (
    button, card, page_header, pill, set_pill_tone, MetricCard, center_window,
)


# Availability colour bands (percent).
AVAIL_GOOD = 90.0
AVAIL_WARN = 75.0
MAX_HOURS_PER_DAY = 24.0


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _availability(operating, planned):
    """operating / planned in percent, or None when nothing was planned."""
    planned = _num(planned)
    if planned <= 0:
        return None
    return max(0.0, _num(operating) / planned * 100.0)


def _avail_tone(pct):
    if pct is None:
        return "neutral"
    if pct >= AVAIL_GOOD:
        return "success"
    if pct >= AVAIL_WARN:
        return "warning"
    return "danger"


def _fmt(value):
    return fmt_number(value, decimals=2, persian=False)


def _plain(value):
    """Number as editable text without thousands separators."""
    return _fmt(value).replace(",", "")


def parse_clock(text):
    """'8', '8:30', '08.30', '۸:۳۰', '24:00' -> minutes after midnight, or None."""
    t = latin_digits(text).replace(".", ":").replace("/", ":")
    if not t:
        return None
    parts = t.split(":")
    if len(parts) > 2 or not all(p.isdigit() for p in parts if p != ""):
        raise ValueError(text)
    h = int(parts[0] or 0)
    m = int(parts[1]) if len(parts) == 2 and parts[1] != "" else 0
    if not (0 <= m <= 59) or not (0 <= h <= 24) or (h == 24 and m):
        raise ValueError(text)
    return h * 60 + m


def run_window_hours(start_min, finish_min):
    """Hours between start and finish; a finish before the start is the next day (night shift)."""
    minutes = finish_min - start_min
    if minutes <= 0:
        minutes += 24 * 60
    return minutes / 60.0


def _log_day(log):
    d = log.log_date
    return d.date() if hasattr(d, "date") else d


# ============================================================================
# PAGE
# ============================================================================

class MachineHoursHistory(tk.Frame):
    """
    Tab «سوابق تجهیز»: daily totals per machine (production_logs) with KPI
    tiles, Excel export and sorting.  Days recorded through the shift sheet
    are edited / deleted there (``open_day`` callback) so the shift records
    and the daily totals can never disagree.
    """

    # logical (RTL) order: first item is right-most on screen
    COLUMNS = (
        ("date", "تاریخ", 110),
        ("weekday", "روز", 90),
        ("planned", "برنامه‌ریزی (ساعت)", 130),
        ("operating", "کارکرد (ساعت)", 120),
        ("downtime", "توقف (ساعت)", 110),
        ("availability", "دسترس‌پذیری", 110),
        ("output", "تولید (واحد)", 120),
    )

    def __init__(self, parent, current_user, shift_repo=None, open_day=None):
        super().__init__(parent, bg=GRAY_BG)
        self.current_user = current_user
        self.shift_repo = shift_repo
        self.open_day = open_day

        self.log_repo = ProductionLogRepository(SessionLocal)
        self.eq_repo = EquipmentRepository(SessionLocal)

        # Technicians record machine hours on the floor, so they may add and
        # edit records (deleting stays with roles that have "delete").
        user = AuthManager.get_current_user()
        is_technician = getattr(user, "role", None) == "technician"
        self.can_write = is_technician or AuthManager.can_access("machine_hours", "write")
        self.can_delete = AuthManager.can_access("machine_hours", "delete")

        self.equipment_map = {}
        self.equipment_display_values = []
        self._equipment_loading = False
        self._logs = []
        self._active_range = None
        self._sort_state = (None, False)
        self._edit_btn = self._del_btn = None

        self.equipment_var = tk.StringVar()
        self._status_var = tk.StringVar(value="آماده")
        self._count_var = tk.StringVar(value="0 رکورد")
        self._eq_badge_var = tk.StringVar(value="تجهیزی انتخاب نشده")

        self._configure_styles()
        self._build_ui()
        self._load_equipment()

    # ------------------------------------------------------------------ styles

    def _configure_styles(self):
        style = ttk.Style(self)
        ensure_theme(style)
        style.configure(
            "MH.Treeview", background=WHITE, fieldbackground=WHITE,
            foreground=TEXT_DARK, rowheight=32, font=FONT_NORMAL,
            bordercolor=BORDER, borderwidth=0,
        )
        style.configure(
            "MH.Treeview.Heading", background=NAVY, foreground=WHITE,
            font=FONT_BOLD, relief="flat", padding=(6, 8),
        )
        style.map("MH.Treeview.Heading", background=[("active", "#2C3E6B")])
        style.map("MH.Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected", WHITE)])

    # ---------------------------------------------------------------------- UI

    def _build_ui(self):
        bar = tk.Frame(self, bg=GRAY_BG)
        bar.pack(fill="x", padx=20, pady=(0, 10))
        button(bar, "↻  بروزرسانی", self._force_reload, kind="secondary").pack(side="left")
        button(bar, "خروجی Excel", self._export_excel, kind="secondary").pack(side="left", padx=(6, 0))
        tk.Label(bar, text="جمع روزانه هر تجهیز (مجموع شیفت‌ها). برای ثبت یا اصلاح از تب «برگه روزانه» استفاده کنید.",
                 font=FONT_SMALL, bg=GRAY_BG, fg=TEXT_MUTED).pack(side="right")

        self._build_filters()
        self._build_metrics()
        self._build_table()
        self._build_footer()

    # filters --------------------------------------------------------------

    def _build_filters(self):
        outer, box = card(self)
        outer.pack(fill="x", padx=20, pady=(0, 12))

        row = tk.Frame(box, bg=WHITE)
        row.pack(fill="x")

        # Equipment (right-most in RTL)
        eq_col = tk.Frame(row, bg=WHITE)
        eq_col.pack(side="right", fill="x", expand=True)
        tk.Label(eq_col, text="تجهیز", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED, anchor="e").pack(fill="x")
        self.equipment_combo = ttk.Combobox(
            eq_col, textvariable=self.equipment_var, state="normal",
            font=FONT_NORMAL, justify="right", height=14,
        )
        self.equipment_combo.pack(fill="x", pady=(4, 0), ipady=2)
        self.equipment_combo.bind("<<ComboboxSelected>>", self._on_equipment_selected)
        self.equipment_combo.bind("<KeyRelease>", self._on_equipment_typed)
        self.equipment_combo.bind("<Escape>", self._restore_equipment_values)
        self.equipment_combo.bind("<Return>", self._on_equipment_return)

        def date_col(label):
            col = tk.Frame(row, bg=WHITE)
            col.pack(side="right", padx=(0, 14))
            tk.Label(col, text=label, font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED, anchor="e").pack(fill="x")
            entry = JalaliDateEntry(col, width=12)
            entry.pack(fill="x", pady=(4, 0))
            return entry

        self.start_date = date_col("از تاریخ")
        self.end_date = date_col("تا تاریخ")
        self.start_date.set_date(jalali_month_start())
        self.end_date.set_date(tehran_today())
        for entry in (self.start_date, self.end_date):
            entry.bind("<<DateEntrySelected>>", lambda _e: self._on_manual_range())

        btn_col = tk.Frame(row, bg=WHITE)
        btn_col.pack(side="right", padx=(14, 0), anchor="s")
        button(btn_col, "اعمال فیلتر", self._on_manual_range, kind="primary").pack(side="right")
        button(btn_col, "پیش‌فرض", self._reset_filters, kind="secondary").pack(side="right", padx=(0, 6))

        # quick ranges + selected equipment
        row2 = tk.Frame(box, bg=WHITE)
        row2.pack(fill="x", pady=(12, 0))
        tk.Label(row2, text="بازه سریع:", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        self._range_buttons = {}
        for key, label in (("month", "این ماه"), ("prev_month", "ماه قبل"),
                           ("last30", "۳۰ روز اخیر"), ("year", "امسال")):
            chip = tk.Label(row2, text=label, font=FONT_SMALL, bg=SURFACE_ALT, fg=TEXT_DARK,
                            padx=10, pady=3, cursor="hand2", highlightthickness=1,
                            highlightbackground=BORDER)
            chip.pack(side="right", padx=(6, 0))
            chip.bind("<Button-1>", lambda _e, k=key: self._apply_quick_range(k))
            self._range_buttons[key] = chip

        self._eq_badge = pill(row2, textvariable=self._eq_badge_var, tone="accent")
        self._eq_badge.pack(side="left")
        self._mark_range("month")

    # metrics --------------------------------------------------------------

    def _build_metrics(self):
        row = tk.Frame(self, bg=GRAY_BG)
        row.pack(fill="x", padx=20, pady=(0, 12))
        specs = (
            ("availability", "دسترس‌پذیری دوره", "◔", "success"),
            ("operating", "مجموع ساعات کارکرد", "◷", "accent"),
            ("planned", "مجموع ساعات برنامه‌ریزی", "▦", "info"),
            ("downtime", "مجموع ساعات توقف", "⏸", "danger"),
            ("output", "مجموع تولید", "▤", "warning"),
        )
        self.metrics = {}
        last = len(specs) - 1
        for i, (key, title, icon, tone) in enumerate(specs):
            m = MetricCard(row, title, icon=icon, tone=tone)
            # first spec in the right-most grid column (RTL)
            m.grid(row=0, column=last - i, sticky="nsew", padx=(0 if i == last else 10, 0))
            self.metrics[key] = m
        for c in range(len(specs)):
            row.grid_columnconfigure(c, weight=1, uniform="mh")

    # table ----------------------------------------------------------------

    def _build_table(self):
        outer, box = card(self, padx=0, pady=0)
        outer.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        head = tk.Frame(box, bg=WHITE, padx=16, pady=10)
        head.pack(fill="x")
        tk.Label(head, text="سوابق روزانه", font=FONT_HEADING, bg=WHITE, fg=TEXT_DARK).pack(side="right")
        pill(head, textvariable=self._count_var).pack(side="right", padx=(0, 10))

        legend = tk.Frame(head, bg=WHITE)
        legend.pack(side="left")
        tk.Label(legend, text="رنگ دسترس‌پذیری:", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right", padx=(0, 6))
        for text, color in ((f"≥ {AVAIL_GOOD:.0f}%", SUCCESS),
                            (f"{AVAIL_WARN:.0f} تا {AVAIL_GOOD:.0f}%", WARNING),
                            (f"< {AVAIL_WARN:.0f}%", DANGER)):
            tk.Label(legend, text="●", font=FONT_SMALL, bg=WHITE, fg=color).pack(side="right")
            tk.Label(legend, text=text, font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right", padx=(2, 10))

        tk.Frame(box, bg=BORDER, height=1).pack(fill="x")

        wrap = tk.Frame(box, bg=WHITE)
        wrap.pack(fill="both", expand=True)

        # Treeview lays columns out left->right, so pass them reversed to get
        # the first logical column (تاریخ) on the RIGHT.
        cols = [c[0] for c in reversed(self.COLUMNS)]
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="extended",
                                 style="MH.Treeview", height=12)
        for key, title, width in self.COLUMNS:
            self.tree.heading(key, text=title, anchor="center",
                              command=lambda k=key: self._sort_by(k))
            self.tree.column(key, width=width, minwidth=80, anchor="center", stretch=True)

        self.tree.tag_configure("odd", background="#FAFBFD")
        self.tree.tag_configure("even", background=WHITE)
        self.tree.tag_configure("warning", foreground="#92400E")
        self.tree.tag_configure("danger", foreground="#B91C1C")

        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="left", fill="y")            # RTL: scrollbar on the left
        self.tree.pack(side="left", fill="both", expand=True)

        self._empty = tk.Frame(wrap, bg=WHITE)
        tk.Label(self._empty, text="◌", font=("Segoe UI Symbol", 28), bg=WHITE, fg="#B8C2D0").pack(pady=(10, 4))
        tk.Label(self._empty, text="رکوردی در این بازه ثبت نشده است", font=FONT_HEADING,
                 bg=WHITE, fg=TEXT_DARK).pack()
        self._empty_hint = tk.Label(self._empty, text="", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED)
        self._empty_hint.pack(pady=(4, 10))

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<F2>", lambda _e: self._edit_log())
        self.tree.bind("<Delete>", lambda _e: self._delete_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_buttons())
        self.tree.bind("<Button-3>", self._show_context_menu)

        self.ctx_menu = tk.Menu(self, tearoff=0, font=FONT_NORMAL, bg=WHITE, fg=TEXT_DARK,
                                activebackground=ACCENT, activeforeground=WHITE)
        if self.can_write:
            self.ctx_menu.add_command(label="ویرایش رکورد  (F2)", command=self._edit_log)
        if self.can_delete:
            self.ctx_menu.add_command(label="حذف  (Del)", command=self._delete_selected)

    def _build_footer(self):
        bar = tk.Frame(self, bg=GRAY_BG)
        bar.pack(fill="x", padx=20, pady=(0, 18))

        self._status_pill = pill(bar, textvariable=self._status_var)
        self._status_pill.pack(side="right")

        hint = "دوبار کلیک یا F2: ویرایش   •   Del: حذف" if self.can_write else ""
        tk.Label(bar, text=hint, font=FONT_SMALL, bg=GRAY_BG, fg=TEXT_MUTED).pack(side="right", padx=14)

        if self.can_delete:
            self._del_btn = button(bar, "حذف", self._delete_selected, kind="danger")
            self._del_btn.pack(side="left")
        if self.can_write:
            self._edit_btn = button(bar, "ویرایش", self._edit_log, kind="primary")
            self._edit_btn.pack(side="left", padx=(6, 0))
        self._update_buttons()

    # ------------------------------------------------------------- equipment

    def _load_equipment(self):
        try:
            equipments = self.eq_repo.get_all_equipment() or []
        except Exception as exc:
            self.equipment_map, self.equipment_display_values = {}, []
            self.equipment_combo["values"] = []
            self._eq_badge_var.set("تجهیزات بارگذاری نشد")
            self._set_status("خطا در بارگذاری تجهیزات", "danger")
            messagebox.showerror("خطا", f"خطا در بارگذاری تجهیزات:\n\n{exc}", parent=self)
            return False

        values, mapping = [], {}
        for eq in equipments:
            code = str(eq.get("code") or "").strip()
            name = str(eq.get("name") or "").strip()
            display = f"{code} - {name}" if code and name else (name or code)
            if display and display not in mapping:
                values.append(display)
                mapping[display] = eq.get("id")

        self.equipment_map, self.equipment_display_values = mapping, values
        self.equipment_combo["values"] = values

        if not values:
            self.equipment_var.set("")
            self.equipment_combo.configure(state="disabled")
            self._eq_badge_var.set("تجهیزی ثبت نشده است")
            self._populate([])
            self._set_status("تجهیزی برای نمایش وجود ندارد", "warning")
            return True

        self.equipment_combo.configure(state="normal")
        if self.equipment_var.get().strip() not in mapping:
            self.equipment_var.set(values[0])
        self._load_logs()
        return True

    def _on_equipment_selected(self, _event=None):
        self._load_logs()

    def _on_equipment_return(self, _event=None):
        self._load_logs()
        return "break"

    def _on_equipment_typed(self, _event=None):
        if self._equipment_loading:
            return
        query = self.equipment_var.get().strip().casefold()
        terms = [t for t in query.split() if t]
        if terms:
            filtered = [v for v in self.equipment_display_values
                        if all(t in v.casefold() for t in terms)]
        else:
            filtered = list(self.equipment_display_values)
        self._equipment_loading = True
        try:
            self.equipment_combo["values"] = filtered
        finally:
            self._equipment_loading = False
        current = self.equipment_var.get().strip()
        if current in self.equipment_map:
            self._eq_badge_var.set(current)
        elif current:
            self._eq_badge_var.set(f"{len(filtered)} تجهیز مطابق جستجو")

    def _restore_equipment_values(self, _event=None):
        self.equipment_combo["values"] = list(self.equipment_display_values)

    def _get_selected_equipment_id(self):
        value = self.equipment_var.get().strip()
        if not value:
            return None
        if value in self.equipment_map:
            return self.equipment_map[value]
        q = value.casefold()
        matches = [v for v in self.equipment_display_values if q in v.casefold()]
        if len(matches) == 1:
            self.equipment_var.set(matches[0])
            return self.equipment_map.get(matches[0])
        return None

    # ---------------------------------------------------------------- ranges

    def _mark_range(self, key):
        self._active_range = key
        for k, chip in self._range_buttons.items():
            active = k == key
            chip.configure(bg=NAVY if active else SURFACE_ALT, fg=WHITE if active else TEXT_DARK,
                           highlightbackground=NAVY if active else BORDER)

    def _apply_quick_range(self, key):
        today = tehran_today()
        if key == "month":
            start, end = jalali_month_start(today), today
        elif key == "prev_month":
            end = jalali_month_start(today) - timedelta(days=1)
            start = jalali_month_start(end)
        elif key == "last30":
            start, end = today - timedelta(days=29), today
        else:
            start, end = jalali_year_start(today), today
        self.start_date.set_date(start)
        self.end_date.set_date(end)
        self._mark_range(key)
        self._load_logs()

    def _on_manual_range(self):
        self._mark_range(None)
        self._load_logs()

    def _reset_filters(self):
        if self.equipment_display_values:
            self.equipment_var.set(self.equipment_display_values[0])
            self._restore_equipment_values()
        self._apply_quick_range("month")
        self._set_status("فیلترها به حالت پیش‌فرض برگشتند", "info")

    def _force_reload(self):
        if self._load_equipment():
            self._set_status("اطلاعات بروزرسانی شد", "success")

    # ------------------------------------------------------------------ data

    def _load_logs(self):
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            self._eq_badge_var.set("تجهیز معتبر انتخاب نشده")
            self._populate([])
            self._set_status("لطفاً یک تجهیز معتبر انتخاب کنید", "warning")
            return

        self._eq_badge_var.set(self.equipment_var.get().strip())
        start, end = self.start_date.get_date(), self.end_date.get_date()
        if start and end and start > end:
            self._populate([])
            self._set_status("تاریخ «از» بعد از تاریخ «تا» است", "warning")
            messagebox.showwarning("بازه تاریخ", "تاریخ «از» نمی‌تواند بعد از تاریخ «تا» باشد.", parent=self)
            return

        try:
            logs = self.log_repo.get_logs(equipment_id=equipment_id, start_date=start, end_date=end) or []
        except Exception as exc:
            self._populate([])
            self._set_status("خطا در بارگذاری اطلاعات", "danger")
            messagebox.showerror("خطا", f"خطا در بارگذاری سوابق:\n\n{exc}", parent=self)
            return

        key, reverse = self._sort_state
        if key:
            logs = sorted(logs, key=self._sort_key(key), reverse=reverse)
        self._populate(logs)
        self._set_status(f"{len(logs)} رکورد بارگذاری شد", "success" if logs else "neutral")

    def _row_values(self, log):
        avail = _availability(log.operating_hours, log.planned_hours)
        day = _log_day(log)
        values = {
            "date": to_jalali_date_str(log.log_date),
            "weekday": jalali_weekday_name(day) if day else "—",
            "planned": _fmt(log.planned_hours),
            "operating": _fmt(log.operating_hours),
            "downtime": _fmt(getattr(log, "downtime_hours", 0) or 0),
            "availability": "—" if avail is None else f"{avail:.1f}%",
            "output": _fmt(log.output_units or 0),
        }
        return [values[c[0]] for c in reversed(self.COLUMNS)], _avail_tone(avail)

    def _populate(self, logs):
        self.tree.delete(*self.tree.get_children())
        self._logs = list(logs or [])
        for i, log in enumerate(self._logs):
            values, tone = self._row_values(log)
            tags = ["even" if i % 2 == 0 else "odd"]
            if tone in ("warning", "danger"):
                tags.append(tone)
            self.tree.insert("", "end", iid=str(log.id), values=values, tags=tags)

        self._count_var.set(f"{len(self._logs)} رکورد")
        self._update_metrics()
        self._update_buttons()

        if self._logs:
            self._empty.place_forget()
        else:
            hint = ("ابتدا یک تجهیز انتخاب کنید." if not self.equipment_map.get(self.equipment_var.get().strip())
                    else "بازه تاریخ را تغییر دهید یا رکورد جدید ثبت کنید.")
            self._empty_hint.configure(text=hint)
            self._empty.place(relx=0.5, rely=0.55, anchor="center")

    def _update_metrics(self):
        planned = sum(_num(l.planned_hours) for l in self._logs)
        operating = sum(_num(l.operating_hours) for l in self._logs)
        downtime = sum(_num(getattr(l, "downtime_hours", 0)) for l in self._logs)
        output = sum(_num(l.output_units) for l in self._logs)
        days = len(self._logs)

        avail = _availability(operating, planned)
        tone = _avail_tone(avail)
        color = {"success": SUCCESS, "warning": WARNING, "danger": DANGER}.get(tone, TEXT_DARK)
        self.metrics["availability"].set(
            "—" if avail is None else f"{avail:.1f}%",
            "کارکرد ÷ برنامه‌ریزی", tone=tone if tone != "neutral" else "success", value_fg=color,
        )
        self.metrics["operating"].set(
            _fmt(operating), f"میانگین روزانه {_fmt(operating / days)}" if days else "")
        self.metrics["planned"].set(_fmt(planned), f"{days} روز ثبت‌شده")
        self.metrics["downtime"].set(
            _fmt(downtime), f"{downtime / planned * 100:.1f}% از برنامه" if planned else "")
        self.metrics["output"].set(
            _fmt(output), f"{_fmt(output / operating)} واحد در ساعت کارکرد" if operating else "")

    def _sort_key(self, key):
        fields = {"planned": "planned_hours", "operating": "operating_hours",
                  "downtime": "downtime_hours", "output": "output_units"}

        def k(log):
            if key in ("date", "weekday"):
                return log.log_date
            if key == "availability":
                a = _availability(log.operating_hours, log.planned_hours)
                return -1.0 if a is None else a
            return _num(getattr(log, fields[key], 0))
        return k

    def _sort_by(self, key):
        prev_key, prev_rev = self._sort_state
        reverse = (not prev_rev) if prev_key == key else True
        self._sort_state = (key, reverse)
        self._populate(sorted(self._logs, key=self._sort_key(key), reverse=reverse))

    # ------------------------------------------------------------ helpers

    def _set_status(self, text, tone="neutral"):
        self._status_var.set(text or "آماده")
        if hasattr(self, "_status_pill"):
            set_pill_tone(self._status_pill, tone)

    def _update_buttons(self):
        selected = bool(self.tree.selection()) if hasattr(self, "tree") else False
        for btn in (self._edit_btn, self._del_btn):
            if btn is not None:
                btn.configure(state="normal" if selected else "disabled",
                              cursor="hand2" if selected else "arrow")

    def _on_double_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "heading":
            return
        self._edit_log()

    def _show_context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if not row or not (self.can_write or self.can_delete):
            return
        if row not in self.tree.selection():
            self.tree.selection_set(row)
        try:
            self.ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.ctx_menu.grab_release()

    # ------------------------------------------------------------ actions

    def _add_log(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ثبت رکورد نیستید.", parent=self)
            return
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            messagebox.showwarning("انتخاب تجهیز", "ابتدا یک تجهیز معتبر انتخاب کنید.", parent=self)
            return
        LogDialog(self, self.log_repo, equipment_id, self.equipment_var.get().strip(),
                  callback=self._load_logs)

    def _edit_log(self):
        if not self.can_write:
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("انتخاب", "لطفاً یک رکورد انتخاب کنید.", parent=self)
            return
        try:
            log = self.log_repo.get_log(int(sel[0]))
        except Exception as exc:
            messagebox.showerror("خطا", f"خطا در دریافت رکورد:\n\n{exc}", parent=self)
            return
        if not log:
            messagebox.showerror("خطا", "رکورد یافت نشد.", parent=self)
            self._load_logs()
            return
        if self._redirect_to_sheet(log):
            return
        LogDialog(self, self.log_repo, log.equipment_id, self.equipment_var.get().strip(),
                  log=log, callback=self._load_logs)

    def _redirect_to_sheet(self, log):
        """Days stored as shift records are edited in the daily sheet."""
        day = _log_day(log)
        if self.shift_repo is not None and self.shift_repo.has_shift_logs(log.equipment_id, day):
            if self.open_day is not None and messagebox.askyesno(
                    "برگه روزانه",
                    f"این روز ({to_jalali_date_str(day)}) با برگه شیفت ثبت شده است.\n"
                    "برای اصلاح، برگه روزانه همان تاریخ باز شود؟", parent=self):
                self.open_day(day)
            return True
        return False

    def _delete_log(self):  # kept for compatibility with older callers
        self._delete_selected()

    def _delete_selected(self):
        if not self.can_delete:
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً حداقل یک رکورد انتخاب کنید.", parent=self)
            return
        if self.shift_repo is not None:
            for iid in selected:
                log = self.log_repo.get_log(int(iid))
                if log and self.shift_repo.has_shift_logs(log.equipment_id, _log_day(log)):
                    messagebox.showinfo(
                        "برگه روزانه",
                        f"روز {to_jalali_date_str(log.log_date)} با برگه شیفت ثبت شده است؛\n"
                        "حذف آن از تب «برگه روزانه» (پاک کردن ردیف تجهیز) انجام می‌شود.", parent=self)
                    return
        dates = [self.tree.set(i, "date") for i in selected[:5]]
        more = f"\nو {len(selected) - 5} رکورد دیگر" if len(selected) > 5 else ""
        if not messagebox.askyesno(
            "تأیید حذف",
            f"{len(selected)} رکورد حذف شود؟\n\n" + "\n".join(dates) + more,
            icon="warning", parent=self,
        ):
            return
        errors = []
        for iid in selected:
            try:
                ok, msg = self.log_repo.delete_log(int(iid))
                if not ok:
                    errors.append(f"{self.tree.set(iid, 'date')}: {msg}")
            except Exception as exc:
                errors.append(f"{iid}: {exc}")
        self._load_logs()
        if errors:
            messagebox.showerror("خطا در حذف", "\n".join(errors), parent=self)
        else:
            self._set_status(f"{len(selected)} رکورد حذف شد", "success")

    def _export_excel(self):
        if not self._logs:
            messagebox.showinfo("خروجی", "رکوردی برای خروجی وجود ندارد.", parent=self)
            return
        start, end = self.start_date.get_date(), self.end_date.get_date()
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=(f"machine_hours_{to_jalali_date_str(start, '%Y%m%d')}_"
                         f"{to_jalali_date_str(end, '%Y%m%d')}.xlsx"),
        )
        if not path:
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill

            wb = Workbook()
            ws = wb.active
            ws.title = "ساعات کارکرد"
            ws.sheet_view.rightToLeft = True
            ws.append([f"ساعات کارکرد تجهیز: {self.equipment_var.get().strip()}"])
            ws.append([f"بازه: {to_jalali_date_str(start)} تا {to_jalali_date_str(end)}"])
            ws.append([])
            ws.append([c[1] for c in self.COLUMNS])
            for log in self._logs:
                avail = _availability(log.operating_hours, log.planned_hours)
                ws.append([
                    to_jalali_date_str(log.log_date),
                    jalali_weekday_name(_log_day(log)),
                    _num(log.planned_hours), _num(log.operating_hours),
                    _num(getattr(log, "downtime_hours", 0)),
                    None if avail is None else round(avail / 100, 4),
                    int(_num(log.output_units)),
                ])
            ws["A1"].font = Font(bold=True, size=13)
            head_fill = PatternFill("solid", fgColor="1A2A44")
            for cell in ws[4]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = head_fill
                cell.alignment = Alignment(horizontal="center")
            for row in ws.iter_rows(min_row=5, min_col=6, max_col=6):
                for cell in row:
                    cell.number_format = "0.0%"
            for col, width in zip("ABCDEFG", (14, 12, 18, 16, 14, 14, 16)):
                ws.column_dimensions[col].width = width
            wb.save(path)
            self._set_status("فایل Excel ذخیره شد", "success")
        except Exception as exc:
            messagebox.showerror("خطا", f"ذخیره فایل ممکن نشد:\n\n{exc}", parent=self)

    # ---------------------------------------------- MainView keyboard hooks

    def handle_enter(self):
        if self.can_write and self.tree.selection():
            self._edit_log()

    def handle_delete(self):
        self._delete_selected()


# ============================================================================
# ADD / EDIT DIALOG
# ============================================================================

class LogDialog(tk.Toplevel):

    def __init__(self, parent, log_repo, equipment_id, equipment_label="", log=None, callback=None):
        super().__init__(parent)
        self.log_repo = log_repo
        self.equipment_id = equipment_id
        self.log = log
        self.callback = callback

        self.withdraw()
        self.title("ویرایش ساعات کارکرد" if log else "ثبت ساعات کارکرد")
        self.configure(bg=GRAY_BG)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        self._build(equipment_label)
        if log:
            self._load()
        else:
            self.date_entry.set_date(tehran_today())
        self._recalc()

        self.update_idletasks()
        center_window(self, 470, self.winfo_reqheight())
        self.deiconify()
        self.grab_set()
        self.after(60, self.date_entry.focus_set)

    def _build(self, equipment_label):
        head = tk.Frame(self, bg=NAVY, padx=18, pady=12)
        head.pack(fill="x")
        tk.Label(head, text=self.title(), font=FONT_HEADING, bg=NAVY, fg=WHITE).pack(anchor="e")
        if equipment_label:
            tk.Label(head, text=equipment_label, font=FONT_SMALL, bg=NAVY, fg="#C9D6EA").pack(anchor="e", pady=(2, 0))

        outer, body = card(self, padx=18, pady=14)
        outer.pack(fill="both", expand=True, padx=14, pady=(14, 8))
        body.grid_columnconfigure(0, weight=1)

        def label(row, text):
            tk.Label(body, text=text, font=FONT_NORMAL, bg=WHITE, fg=TEXT_DARK, anchor="e").grid(
                row=row, column=1, sticky="e", padx=(12, 0), pady=6)

        label(0, "تاریخ")
        self.date_entry = JalaliDateEntry(body, width=14)
        self.date_entry.grid(row=0, column=0, sticky="ew", pady=6)

        self.planned_var = tk.StringVar(value="8")
        self.operating_var = tk.StringVar(value="8")
        self.downtime_var = tk.StringVar(value="0")
        self.output_var = tk.StringVar(value="0")
        self.start_var = tk.StringVar(value="")
        self.finish_var = tk.StringVar(value="")

        # start / finish of work -> operating hours are calculated, not typed
        label(1, "ساعت شروع و پایان کار")
        times_box = tk.Frame(body, bg=WHITE)
        times_box.grid(row=1, column=0, sticky="ew", pady=6)
        times = tk.Frame(times_box, bg=WHITE)
        times.pack(fill="x")
        tk.Label(times, text="شروع", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        self.start_entry = ttk.Entry(times, textvariable=self.start_var, justify="center",
                                     font=FONT_NORMAL, width=7)
        self.start_entry.pack(side="right", padx=(4, 12))
        tk.Label(times, text="پایان", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        self.finish_entry = ttk.Entry(times, textvariable=self.finish_var, justify="center",
                                      font=FONT_NORMAL, width=7)
        self.finish_entry.pack(side="right", padx=(4, 0))
        self.window_lbl = tk.Label(times_box, text="مثلاً 07:30 تا 16:00", font=FONT_SMALL,
                                   bg=WHITE, fg=TEXT_MUTED, anchor="e")
        self.window_lbl.pack(fill="x", pady=(3, 0))

        fields = (
            (2, "ساعات برنامه‌ریزی", self.planned_var),
            (3, "ساعات توقف (در صورت وجود)", self.downtime_var),
            (4, "ساعات کارکرد", self.operating_var),
            (5, "میزان تولید (واحد)", self.output_var),
        )
        self.entries = []
        for row, text, var in fields:
            label(row, text)
            entry = ttk.Entry(body, textvariable=var, justify="right", font=FONT_NORMAL)
            entry.grid(row=row, column=0, sticky="ew", pady=6)
            self.entries.append(entry)
        self.operating_entry = self.entries[2]
        self.calc_hint = tk.Label(body, text="", font=FONT_SMALL, bg=WHITE, fg=ACCENT, anchor="e")
        self.calc_hint.grid(row=6, column=0, columnspan=2, sticky="e")

        # live summary
        self.summary = tk.Frame(body, bg=SURFACE_ALT, padx=12, pady=8)
        self.summary.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.avail_lbl = tk.Label(self.summary, text="", font=FONT_BOLD, bg=SURFACE_ALT, fg=TEXT_DARK, anchor="e")
        self.avail_lbl.pack(fill="x")
        self.rest_lbl = tk.Label(self.summary, text="", font=FONT_SMALL, bg=SURFACE_ALT, fg=TEXT_MUTED, anchor="e")
        self.rest_lbl.pack(fill="x")

        for var in (self.planned_var, self.operating_var):
            var.trace_add("write", lambda *_: self._recalc())
        for var in (self.start_var, self.finish_var, self.downtime_var):
            var.trace_add("write", lambda *_: self._apply_time_window())

        footer = tk.Frame(self, bg=GRAY_BG)
        footer.pack(fill="x", padx=14, pady=(0, 14))
        button(footer, "ذخیره  (Enter)", self._save, kind="success").pack(side="right")
        button(footer, "انصراف", self.destroy, kind="secondary").pack(side="right", padx=(0, 8))
        tk.Label(footer, text="ارقام فارسی هم پذیرفته می‌شود", font=FONT_SMALL, bg=GRAY_BG,
                 fg=TEXT_MUTED).pack(side="left")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._save())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _window_hours(self):
        """Run window from start/finish, None if not (completely) entered."""
        start = parse_clock(self.start_var.get())
        finish = parse_clock(self.finish_var.get())
        if start is None or finish is None:
            return None
        return run_window_hours(start, finish)

    def _apply_time_window(self):
        """Operating = (finish - start) - downtime, written into the field."""
        try:
            window = self._window_hours()
        except ValueError:
            self.window_lbl.configure(text="ساعت نامعتبر (مثال: 07:30)", fg=DANGER)
            self.operating_entry.state(["!readonly"])
            self._recalc()
            return
        if window is None:
            self.window_lbl.configure(text="مثلاً 07:30 تا 16:00", fg=TEXT_MUTED)
            self.calc_hint.configure(text="")
            self.operating_entry.state(["!readonly"])
            self._recalc()
            return
        try:
            downtime = self._parse(self.downtime_var)
        except ValueError:
            downtime = 0.0
        operating = max(0.0, window - max(0.0, downtime))
        night = parse_clock(self.finish_var.get()) <= parse_clock(self.start_var.get())
        self.window_lbl.configure(
            text=f"مدت حضور: {_fmt(window)} ساعت" + ("  (تا روز بعد)" if night else ""), fg=TEXT_DARK)
        self.calc_hint.configure(text="ساعات کارکرد خودکار محاسبه شد: (پایان − شروع) − توقف")
        self.operating_entry.state(["!readonly"])
        self.operating_var.set(_plain(round(operating, 2)))
        self.operating_entry.state(["readonly"])

    def _load(self):
        self.date_entry.set_date(self.log.log_date)
        self.planned_var.set(_plain(self.log.planned_hours))
        self.operating_var.set(_plain(self.log.operating_hours))
        self.downtime_var.set(_plain(getattr(self.log, "downtime_hours", 0) or 0))
        self.output_var.set(str(int(_num(self.log.output_units))))

    @staticmethod
    def _parse(var):
        text = latin_digits(var.get())
        return 0.0 if text == "" else float(text)

    def _paint_summary(self, bg, fg, main, sub):
        self.summary.configure(bg=bg)
        self.avail_lbl.configure(bg=bg, fg=fg, text=main)
        self.rest_lbl.configure(bg=bg, text=sub)

    def _recalc(self):
        try:
            planned = self._parse(self.planned_var)
            operating = self._parse(self.operating_var)
            downtime = self._parse(self.downtime_var)
        except ValueError:
            self._paint_summary(DANGER_SOFT, DANGER, "مقدار عددی نامعتبر است", "")
            return
        avail = _availability(operating, planned)
        tone = _avail_tone(avail)
        bg = {"success": SUCCESS_SOFT, "warning": WARNING_SOFT, "danger": DANGER_SOFT}.get(tone, SURFACE_ALT)
        fg = {"success": SUCCESS, "warning": WARNING, "danger": DANGER}.get(tone, TEXT_DARK)
        rest = planned - operating - downtime
        if rest < -0.001:
            sub = f"کارکرد + توقف، {_fmt(-rest)} ساعت بیشتر از برنامه است"
        elif rest > 0.001:
            sub = f"{_fmt(rest)} ساعت از برنامه نه به‌عنوان کارکرد ثبت شده و نه توقف"
        else:
            sub = "کارکرد + توقف = برنامه‌ریزی"
        self._paint_summary(bg, fg, "دسترس‌پذیری: —" if avail is None else f"دسترس‌پذیری: {avail:.1f}%", sub)

    def _save(self):
        log_date = self.date_entry.get_date()
        if log_date is None:
            messagebox.showerror("خطا", "تاریخ نامعتبر است.", parent=self)
            return
        try:
            planned = self._parse(self.planned_var)
            operating = self._parse(self.operating_var)
            downtime = self._parse(self.downtime_var)
            output = self._parse(self.output_var)
        except ValueError:
            messagebox.showerror("خطا", "لطفاً فقط عدد وارد کنید.", parent=self)
            return
        if min(planned, operating, downtime, output) < 0:
            messagebox.showerror("خطا", "مقادیر نمی‌توانند منفی باشند.", parent=self)
            return
        try:
            window = self._window_hours()
        except ValueError:
            messagebox.showerror("خطا", "ساعت شروع یا پایان کار نامعتبر است (مثال: 07:30).", parent=self)
            return
        if window is not None and downtime > window + 0.001:
            messagebox.showerror("خطا", "ساعات توقف از فاصله شروع تا پایان کار بیشتر است.", parent=self)
            return
        if max(planned, operating, downtime) > MAX_HOURS_PER_DAY:
            messagebox.showerror("خطا", "ساعات یک روز نمی‌تواند بیشتر از ۲۴ باشد.", parent=self)
            return
        if not float(output).is_integer():
            messagebox.showerror("خطا", "میزان تولید باید عدد صحیح باشد.", parent=self)
            return
        if log_date > tehran_today() and not messagebox.askyesno(
                "تاریخ آینده", "تاریخ انتخاب‌شده در آینده است. ادامه می‌دهید؟", parent=self):
            return
        if operating + downtime > planned + 0.001 and not messagebox.askyesno(
                "بررسی ساعات", "مجموع کارکرد و توقف از ساعات برنامه‌ریزی بیشتر است.\nذخیره شود؟",
                parent=self):
            return

        output = int(output)
        try:
            if self.log:
                ok, msg = self.log_repo.update_log(
                    self.log.id, planned, operating, output,
                    downtime_hours=downtime, log_date=log_date)
            else:
                existing = self.log_repo.find_log_for_day(self.equipment_id, log_date)
                if existing and not messagebox.askyesno(
                    "رکورد تکراری",
                    f"برای این تجهیز در تاریخ {to_jalali_date_str(log_date)} قبلاً رکورد ثبت شده است\n"
                    f"(کارکرد {_fmt(existing.operating_hours)} از {_fmt(existing.planned_hours)} ساعت).\n\n"
                    "مقادیر جدید جایگزین شود؟", icon="warning", parent=self):
                    return
                ok, msg = self.log_repo.add_log(
                    self.equipment_id, log_date, planned, operating, output,
                    downtime_hours=downtime)
        except Exception as exc:
            messagebox.showerror("خطا", f"ذخیره رکورد با خطا مواجه شد:\n\n{exc}", parent=self)
            return

        if not ok:
            messagebox.showerror("خطا", msg, parent=self)
            return
        callback = self.callback
        self.destroy()
        if callback:
            callback()


# ============================================================================
# PAGE (tabs)
# ============================================================================

class MachineHoursView(tk.Frame):
    """
    ساعت کار ماشین - standard shift log.

      برگه روزانه   all machines of one date + shift; start/finish/output and
                    stops (from-to + reason); everything calculated
      سوابق تجهیز   daily totals per machine, KPIs, Excel
      علل توقف      Pareto of stop reasons for a period
    """

    # The editable shift sheet manages its own rows/colours (views/ux.py).
    ux_skip_tables = True

    def __init__(self, parent, current_user):
        super().__init__(parent, bg=GRAY_BG)
        from views.machine_shift_sheet import DailySheet, DowntimeParetoTab
        from database.machine_shift_repository import MachineShiftRepository

        user = AuthManager.get_current_user()
        role = getattr(user, "role", None)
        can_write = role == "technician" or AuthManager.can_access("machine_hours", "write")
        can_configure = role in ("admin", "manager")
        user_name = getattr(user, "username", "") or ""

        actions = page_header(
            self, "⏱", "ساعت کار ماشین",
            "ثبت شیفتی ساعات کار، توقف‌ها (با علت) و تولید هر تجهیز  •  محاسبه خودکار دسترس‌پذیری",
        )
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=0, pady=(0, 0))

        self.sheet = DailySheet(self.notebook, can_write=can_write,
                                can_configure=can_configure, user_name=user_name)
        self.notebook.add(self.sheet, text="  برگه روزانه (شیفت)  ")
        self._history = None
        self._pareto = None
        self._shift_repo = MachineShiftRepository(SessionLocal)
        self._current_user = current_user
        self._history_tab = tk.Frame(self.notebook, bg=GRAY_BG)
        self._pareto_tab = tk.Frame(self.notebook, bg=GRAY_BG)
        self.notebook.add(self._history_tab, text="  سوابق تجهیز  ")
        self.notebook.add(self._pareto_tab, text="  علل توقف (پارتو)  ")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab)
        self._DowntimeParetoTab = DowntimeParetoTab

        button(actions, "↻  بارگذاری مجدد", self._reload, kind="on_dark").pack(side="left")

    # tabs are built on first use (faster page opening)
    def _on_tab(self, _event=None):
        idx = self.notebook.index("current")
        if idx == 1:
            if self._history is None:
                self._history = MachineHoursHistory(
                    self._history_tab, self._current_user,
                    shift_repo=self._shift_repo, open_day=self._open_day)
                self._history.pack(fill="both", expand=True, pady=(12, 0))
            else:
                self._history._load_logs()
        elif idx == 2:
            if self._pareto is None:
                self._pareto = self._DowntimeParetoTab(self._pareto_tab)
                self._pareto.pack(fill="both", expand=True, pady=(12, 0))
            else:
                self._pareto.load()

    def _open_day(self, day):
        self.notebook.select(0)
        self.sheet.open_day(day)

    def _reload(self):
        idx = self.notebook.index("current")
        if idx == 0:
            if self.sheet.confirm_leave():
                self.sheet._load_sheet()
        else:
            self._on_tab()

    def _active(self):
        idx = self.notebook.index("current")
        return {0: self.sheet, 1: self._history, 2: self._pareto}.get(idx)

    # MainView hooks
    def confirm_leave(self):
        return self.sheet.confirm_leave()

    def handle_enter(self):
        view = self._active()
        if view is not None and hasattr(view, "handle_enter"):
            view.handle_enter()

    def handle_save(self):
        if self._active() is self.sheet:
            self.sheet._save()

    def handle_delete(self):
        view = self._active()
        if view is not None and hasattr(view, "handle_delete"):
            view.handle_delete()
