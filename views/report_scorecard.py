"""
Reports > «شاخص‌های استاندارد» (maintenance scorecard).

Rendering only; the numbers come from database.scorecard_repository.
The layout reflows with the window width (cards wrap, tables stack on narrow
screens) and every column order is right-to-left.
"""

import tkinter as tk
from tkinter import ttk

from utils.date_helpers import to_jalali_date_str
from utils.theme import (
    WHITE, GRAY_BG, GRAY_BORDER, TEXT_DARK, TEXT_LIGHT,
    SUCCESS, SUCCESS_SOFT, DANGER, DANGER_SOFT, ACCENT, ACCENT_SOFT, WARNING,
    FONT_SMALL, FONT_NORMAL, FONT_BOLD, FONT_METRIC, FONT_HEADING,
    fa_digits,
)

CARD_BG = WHITE
CARD_BORDER = GRAY_BORDER
SECTION_BG = GRAY_BG

_TONE = {
    "good": (SUCCESS, SUCCESS_SOFT, "در محدوده مرجع"),
    "bad": (DANGER, DANGER_SOFT, "خارج از محدوده مرجع"),
    None: (ACCENT, ACCENT_SOFT, ""),
}

_STATUS_FA = {
    "PENDING_APPROVAL": "در انتظار تأیید",
    "PENDING": "آماده شروع",
    "IN_PROGRESS": "در حال انجام",
    "FINISH_REQUESTED": "درخواست اتمام",
}

_DEFINITIONS = (
    "کار برنامه‌ریزی‌شده: سهم PM و بازرسی از کارهای تمام‌شده (بر اساس زمان اتمام).",
    "انطباق PM: سهم کارهای PM که تا مهلت تمام شده‌اند؛ کار باز ِ گذشته از مهلت دیرکرد حساب می‌شود.",
    "دسترس‌پذیری، MTBF: از ساعت کار ثبت‌شده در «ساعت کار ماشین».",
    "MTTR: میانگین زمان شروع تا اتمام تعمیرات اصلاحی/اضطراری تأییدشده.",
    "زمان واکنش: از ثبت دستور کار تا شروع کار.",
    "خرابی تکراری: خرابی دوباره همان تجهیز کمتر از ۳۰ روز بعد از خرابی قبلی.",
    "مقادیر مرجع، اعداد رایج صنعت (SMRP) هستند و فقط برای مقایسه نمایش داده می‌شوند.",
)


def _fmt(value, unit):
    if value is None:
        return "—"
    if unit == "%":
        return fa_digits(f"{value:.1f}") + "٪"
    if unit == "ساعت":
        return fa_digits(f"{value:,.1f}")
    return fa_digits(f"{value:,.0f}")


def _target_text(targets, key, unit):
    if key not in targets:
        return ""
    op, ref = targets[key]
    sign = "≥" if op == ">=" else "≤"
    return f"مرجع {sign} {fa_digits(f'{ref:.0f}')}{'٪' if unit == '%' else ''}"


class _FlowGrid(tk.Frame):
    """Places children in as many columns as fit, right to left."""

    def __init__(self, parent, min_width=230, max_cols=4, **kw):
        super().__init__(parent, **kw)
        self.min_width = min_width
        self.max_cols = max_cols
        self.items = []
        self._cols = 0
        self.bind("<Configure>", self._reflow)

    def add(self, widget):
        self.items.append(widget)

    def _reflow(self, event=None):
        width = self.winfo_width()
        if width <= 1:
            return
        cols = max(1, min(self.max_cols, width // self.min_width))
        if cols == self._cols:
            return
        self._cols = cols
        for c in range(self.max_cols):
            self.columnconfigure(c, weight=1 if c < cols else 0, uniform="flow" if c < cols else "")
        for i, w in enumerate(self.items):
            w.grid(row=i // cols, column=cols - 1 - (i % cols), sticky="nsew", padx=6, pady=6)


def _kpi_card(parent, label, value_text, hint, target, tone):
    color, soft, tone_text = _TONE.get(tone, _TONE[None])
    outer = tk.Frame(parent, bg=CARD_BORDER)
    card = tk.Frame(outer, bg=CARD_BG)
    card.pack(fill="both", expand=True, padx=1, pady=1)
    tk.Frame(card, bg=color, height=3).pack(fill="x")
    tk.Label(card, text=label, font=FONT_BOLD, bg=CARD_BG, fg=TEXT_DARK,
             anchor="e", justify="right").pack(fill="x", padx=12, pady=(10, 0))
    tk.Label(card, text=value_text, font=FONT_METRIC, bg=CARD_BG, fg=color,
             anchor="e").pack(fill="x", padx=12, pady=(2, 0))
    tk.Label(card, text=hint, font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT,
             anchor="e", justify="right", wraplength=210).pack(fill="x", padx=12)
    if target:
        chip = tk.Label(card, text=f"{target}   {tone_text}".strip(), font=FONT_SMALL,
                        bg=soft, fg=color, anchor="e", padx=6, pady=2)
        chip.pack(fill="x", padx=12, pady=(6, 10))
    else:
        tk.Frame(card, bg=CARD_BG, height=10).pack()
    return outer


def _section(parent, title, icon=""):
    row = tk.Frame(parent, bg=SECTION_BG)
    row.pack(fill="x", padx=16, pady=(16, 2))
    tk.Label(row, text=f"{icon}  {title}".strip(), font=FONT_HEADING,
             bg=SECTION_BG, fg=TEXT_DARK).pack(side="right")


def _panel(parent, title):
    outer = tk.Frame(parent, bg=CARD_BORDER)
    inner = tk.Frame(outer, bg=CARD_BG)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    tk.Label(inner, text=title, font=FONT_BOLD, bg=CARD_BG, fg=TEXT_DARK,
             anchor="e").pack(fill="x", padx=12, pady=(10, 6))
    return outer, inner


def _bar_rows(parent, rows, color=ACCENT):
    """rows: [(label, count)] -> horizontal bars growing from the right."""
    total = max([c for _l, c in rows] + [1])
    for label, count in rows:
        line = tk.Frame(parent, bg=CARD_BG)
        line.pack(fill="x", padx=12, pady=3)
        tk.Label(line, text=label, font=FONT_SMALL, bg=CARD_BG, fg=TEXT_DARK,
                 width=16, anchor="e").pack(side="right")
        tk.Label(line, text=fa_digits(str(count)), font=FONT_BOLD, bg=CARD_BG,
                 fg=TEXT_DARK, width=5, anchor="w").pack(side="left")
        track = tk.Frame(line, bg=SECTION_BG, height=14)
        track.pack(side="right", fill="x", expand=True, padx=6)
        if count:
            tk.Frame(track, bg=color).place(relx=1.0, rely=0, relheight=1,
                                            relwidth=count / total, anchor="ne")


def _table(parent, columns, rows, height=6):
    """columns: [(key, title, width)] in reading order (right to left)."""
    from views.ui_kit import rtl_columns
    box = tk.Frame(parent, bg=CARD_BG)
    box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    keys = [c[0] for c in columns]
    tree = ttk.Treeview(box, columns=keys, show="headings",
                        height=max(1, min(height, len(rows) or 1)), style="Report.Treeview")
    rtl_columns(tree)
    for key, title, width in columns:
        tree.heading(key, text=title)
        tree.column(key, width=width, minwidth=60, anchor="center", stretch=True)
    for i, row in enumerate(rows):
        tree.insert("", "end", values=row, tags=("odd" if i % 2 else "even",))
    tree.tag_configure("odd", background=SECTION_BG)
    tree.tag_configure("even", background=CARD_BG)
    tree.pack(fill="both", expand=True)
    if not rows:
        tk.Label(box, text="موردی وجود ندارد", font=FONT_SMALL, bg=CARD_BG,
                 fg=TEXT_LIGHT).pack(pady=4)
    return tree


def render_scorecard(view, parent, data):
    if not data:
        tk.Label(parent, text="داده‌ای برای نمایش وجود ندارد.", font=FONT_NORMAL,
                 bg=SECTION_BG, fg=TEXT_LIGHT).pack(pady=40)
        return

    targets = data.get("targets", {})
    status = data.get("status", {})

    # ------------------------------------------------------------ KPI cards
    _section(parent, "شاخص‌های کلیدی نگهداری و تعمیرات", "📐")
    grid = _FlowGrid(parent, min_width=230, max_cols=4, bg=SECTION_BG)
    grid.pack(fill="x", padx=10)
    for key, label, value, unit, hint in data.get("kpis", []):
        unit_suffix = " ساعت" if unit == "ساعت" and value is not None else ""
        grid.add(_kpi_card(grid, label, _fmt(value, unit) + unit_suffix, hint,
                           _target_text(targets, key, unit), status.get(key)))

    # ------------------------------------------------- backlog + PM program
    _section(parent, "کارهای باز و برنامه PM", "🗂️")
    row1 = _FlowGrid(parent, min_width=420, max_cols=2, bg=SECTION_BG)
    row1.pack(fill="x", padx=10)

    backlog = data.get("backlog", {})
    b_outer, b_in = _panel(row1, "سن کارهای باز (روز از ثبت)")
    buckets = backlog.get("buckets", {})
    _bar_rows(b_in, [
        ("۰ تا ۷ روز", buckets.get("0-7", 0)),
        ("۸ تا ۳۰ روز", buckets.get("8-30", 0)),
        ("۳۱ تا ۹۰ روز", buckets.get("31-90", 0)),
        ("بیش از ۹۰ روز", buckets.get("90+", 0)),
    ], color=WARNING)
    tk.Label(
        b_in,
        text=(f"کل کارهای باز: {fa_digits(str(backlog.get('total', 0)))}   |   "
              f"گذشته از مهلت: {fa_digits(str(backlog.get('overdue', 0)))}"),
        font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT, anchor="e",
    ).pack(fill="x", padx=12, pady=(6, 4))
    by_status = backlog.get("by_status", {})
    _bar_rows(b_in, [(_STATUS_FA.get(k, k), by_status.get(k, 0)) for k in _STATUS_FA])
    tk.Frame(b_in, bg=CARD_BG, height=8).pack()
    row1.add(b_outer)

    pm = data.get("pm", {})
    p_outer, p_in = _panel(row1, "برنامه‌های PM عقب‌افتاده")
    tk.Label(
        p_in,
        text=(f"برنامه فعال: {fa_digits(str(pm.get('active', 0)))}   |   "
              f"عقب‌افتاده: {fa_digits(str(pm.get('overdue_count', 0)))}   |   "
              f"سررسید ۱۴ روز آینده: {fa_digits(str(pm.get('due_14', 0)))}"),
        font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT, anchor="e",
    ).pack(fill="x", padx=12, pady=(0, 6))
    _table(p_in, [
        ("title", "برنامه PM", 200),
        ("equipment", "تجهیز", 150),
        ("due", "سررسید", 90),
        ("days", "روز تأخیر", 80),
    ], [
        (r["title"], r["equipment"], fa_digits(to_jalali_date_str(r["next_due"])),
         fa_digits(str(r["days_overdue"])))
        for r in pm.get("overdue", [])
    ], height=7)
    row1.add(p_outer)

    # ------------------------------------------------------------ bad actors
    _section(parent, "تجهیزات پرخرابی (Bad Actors)", "⚠️")
    a_outer, a_in = _panel(parent, "بیشترین خرابی در بازه انتخاب‌شده")
    a_outer.pack(fill="x", padx=16, pady=4)
    _table(a_in, [
        ("equipment", "تجهیز", 200),
        ("failures", "تعداد خرابی", 90),
        ("repeats", "خرابی تکراری", 90),
        ("hours", "ساعت تعمیر", 90),
        ("cost", "هزینه ثبت‌شده", 120),
    ], [
        (r["equipment"], fa_digits(str(r["failures"])), fa_digits(str(r["repeats"])),
         fa_digits(f"{r['repair_hours']:,.1f}"), fa_digits(f"{r['cost']:,.0f}"))
        for r in data.get("bad_actors", [])
    ], height=10)

    # ------------------------------------------------- spare parts + requests
    _section(parent, "قطعات یدکی و درخواست‌های تعمیر", "🔧")
    row2 = _FlowGrid(parent, min_width=420, max_cols=2, bg=SECTION_BG)
    row2.pack(fill="x", padx=10)

    parts = data.get("parts", {})
    used_value_text = fa_digits(f"{parts.get('used_value', 0):,.0f}")
    s_outer, s_in = _panel(row2, "قطعات بحرانی (ناموجود یا زیر حداقل)")
    tk.Label(
        s_in,
        text=(f"ناموجود: {fa_digits(str(parts.get('stockouts', 0)))}   |   "
              f"زیر حداقل: {fa_digits(str(parts.get('below_min', 0)))}   |   "
              f"ارزش مصرف در بازه: {used_value_text}"),
        font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT, anchor="e",
    ).pack(fill="x", padx=12, pady=(0, 6))
    _table(s_in, [
        ("part", "قطعه", 220),
        ("stock", "موجودی", 80),
        ("min", "حداقل", 80),
    ], [
        (r["part"], fa_digits(str(r["stock"])), fa_digits(str(r["min"])))
        for r in parts.get("critical", [])
    ], height=6)
    tk.Label(s_in, text="پرمصرف‌ترین قطعات (بر اساس ارزش)", font=FONT_BOLD,
             bg=CARD_BG, fg=TEXT_DARK, anchor="e").pack(fill="x", padx=12, pady=(4, 4))
    _table(s_in, [
        ("part", "قطعه", 220),
        ("qty", "تعداد", 80),
        ("value", "ارزش", 110),
    ], [
        (r["part"], fa_digits(f"{r['quantity']:,.0f}"), fa_digits(f"{r['value']:,.0f}"))
        for r in parts.get("top_used", [])
    ], height=5)
    row2.add(s_outer)

    rr = data.get("repair_requests", {})
    r_outer, r_in = _panel(row2, "درخواست‌های تعمیر")
    for label, value in (
        ("ثبت‌شده در بازه", fa_digits(str(rr.get("in_period", 0)))),
        ("انجام‌شده از همین بازه", fa_digits(str(rr.get("done", 0)))),
        ("باز (کل)", fa_digits(str(rr.get("open", 0)))),
        ("میانگین زمان خرابی تا اتمام",
         (_fmt(rr.get("avg_hours"), "ساعت") + " ساعت") if rr.get("avg_hours") is not None else "—"),
    ):
        line = tk.Frame(r_in, bg=CARD_BG)
        line.pack(fill="x", padx=12, pady=4)
        tk.Label(line, text=label, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side="right")
        tk.Label(line, text=value, font=FONT_BOLD, bg=CARD_BG, fg=TEXT_DARK).pack(side="left")
    tk.Frame(r_in, bg=CARD_BG, height=8).pack()
    row2.add(r_outer)

    # ------------------------------------------------------------ definitions
    _section(parent, "تعریف شاخص‌ها", "ℹ️")
    d_outer, d_in = _panel(parent, "")
    d_outer.pack(fill="x", padx=16, pady=(4, 16))
    for line in _DEFINITIONS:
        lbl = tk.Label(d_in, text="• " + line, font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT,
                       anchor="e", justify="right")
        lbl.pack(fill="x", padx=12, pady=1)
        lbl.bind("<Configure>", lambda e, w=lbl: w.configure(wraplength=max(200, e.width - 10)))
    tk.Frame(d_in, bg=CARD_BG, height=8).pack()
