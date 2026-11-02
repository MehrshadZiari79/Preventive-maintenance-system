# views/machine_shift_sheet.py
"""
برگه روزانه ساعت کار ماشین - daily / shift log sheet (standard CMMS / OEE).

One screen per date + shift: every machine is a row. The user types start,
finish and output (Enter moves to the next cell, like Excel); the stops of
the selected machine are entered on the side panel as from-to + reason.
Everything else is calculated:

    planned production = (finish - start) - planned stops (CIP, PM, break, no plan)
    run time           = planned production - unplanned stops
    availability       = run time / planned production

Text entry uses the same ttk.Entry / ttk.Combobox widgets as the rest of the
application (Persian typing unchanged).
"""

from __future__ import annotations

import tkinter as tk
from datetime import timedelta
from tkinter import messagebox, ttk

from database.db import SessionLocal
from database.equipment_repository import EquipmentRepository
from database.machine_shift import CATEGORY_LABEL, CATEGORY_PLANNED, DOWNTIME_CATEGORIES
from database.machine_shift_repository import BASIC_SHIFT_NAME, MachineShiftRepository
from services.machine_time import (
    clock_of, compute_shift, fmt_clock, fmt_hm, parse_clock, to_datetime,
)
from utils.date_helpers import jalali_weekday_name, tehran_today
from utils.theme import (
    ACCENT, DANGER, DANGER_SOFT, FONT_BOLD, FONT_HEADING, FONT_NORMAL,
    FONT_SMALL, GRAY_BG, NAVY, TEXT_DARK, TEXT_MUTED,
    WARNING_SOFT, WHITE, latin_digits,
)
from views.jalali_date_entry import JalaliDateEntry
from views.ui_kit import button, card, center_window, pill, set_pill_tone

# (key, heading, width, editable)  logical order = right-to-left on screen
COLUMNS = (
    ("machine",   "تجهیز",              200, False),
    ("start",     "شروع",                62, True),
    ("end",       "پایان",               62, True),
    ("pstop",     "توقف برنامه‌ای",       98, False),
    ("ustop",     "توقف خرابی",          86, False),
    ("pprod",     "زمان تولید",          84, False),
    ("run",       "کارکرد",              70, False),
    ("avail",     "دسترس‌پذیری",          90, False),
    ("output",    "تولید",               70, True),
    ("status",    "وضعیت",              120, False),
)
EDITABLE_BASIC = {"start", "end", "pstop", "ustop", "output"}   # no stop tables -> type minutes
INACTIVE_STATUSES = {"inactive", "retired"}

# reason combobox: unplanned first, then planned (marked)
REASON_CHOICES = [(code, label + ("  (برنامه‌ریزی‌شده)" if planned else ""))
                  for code, label, planned in DOWNTIME_CATEGORIES]
REASON_BY_TEXT = {text: code for code, text in REASON_CHOICES}


class DailySheet(tk.Frame):

    def __init__(self, parent, can_write=True, can_configure=False, user_name=""):
        super().__init__(parent, bg=GRAY_BG)
        self.repo = MachineShiftRepository(SessionLocal)
        self.eq_repo = EquipmentRepository(SessionLocal)
        self.can_write = can_write
        self.can_configure = can_configure
        self.user_name = user_name
        self.full = self.repo.shift_tables_available()

        self.shifts = self.repo.get_shifts() if self.full else [
            dict(self.repo.get_shifts()[0], name=BASIC_SHIFT_NAME)]
        self.day = tehran_today()
        self.shift = self.shifts[0]
        self.rows = {}          # eq_id -> state dict
        self.equipment = []     # list of dicts
        self._editor = None
        self._selected_eq = None

        self.shift_var = tk.StringVar(value=self.shift["name"])
        self.search_var = tk.StringVar()
        self.category_var = tk.StringVar(value="همه دسته‌ها")
        self.dirty_var = tk.StringVar(value="")
        self.total_var = tk.StringVar(value="")

        self._styles()
        self._build()
        self._load_equipment()
        self._load_sheet()

    # ------------------------------------------------------------------ UI

    def _styles(self):
        st = ttk.Style(self)
        st.configure("Sheet.Treeview", rowheight=30, font=FONT_NORMAL, background=WHITE,
                     fieldbackground=WHITE, foreground=TEXT_DARK, borderwidth=0)
        st.configure("Sheet.Treeview.Heading", background=NAVY, foreground=WHITE,
                     font=FONT_BOLD, relief="flat", padding=(4, 7))
        st.map("Sheet.Treeview", background=[("selected", "#DCE8FF")],
               foreground=[("selected", TEXT_DARK)])
        st.configure("Stops.Treeview", rowheight=26, font=FONT_SMALL)
        st.configure("Stops.Treeview.Heading", font=FONT_SMALL, background="#E4E9F0",
                     foreground=TEXT_DARK, relief="flat")

    def _build(self):
        # --- toolbar ---------------------------------------------------------
        outer, bar = card(self, padx=14, pady=10)
        outer.pack(fill="x", padx=20, pady=(0, 10))

        tk.Label(bar, text="تاریخ", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        self.date_entry = JalaliDateEntry(bar, width=11)
        self.date_entry.pack(side="right", padx=(6, 4))
        self.date_entry.set_date(self.day)
        self.date_entry.bind("<<DateEntrySelected>>", lambda _e: self._change_day(self.date_entry.get_date()))
        self.date_entry.bind("<Return>", lambda _e: self._change_day(self.date_entry.get_date()))
        button(bar, "روز قبل", lambda: self._change_day(self.day - timedelta(days=1)), kind="secondary").pack(side="right")
        button(bar, "روز بعد", lambda: self._change_day(self.day + timedelta(days=1)), kind="secondary").pack(side="right", padx=(2, 0))
        button(bar, "امروز", lambda: self._change_day(tehran_today()), kind="secondary").pack(side="right", padx=(6, 0))
        self.weekday_lbl = tk.Label(bar, text="", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED)
        self.weekday_lbl.pack(side="right", padx=8)

        tk.Label(bar, text="شیفت", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right", padx=(14, 0))
        self.shift_combo = ttk.Combobox(bar, textvariable=self.shift_var, state="readonly", width=16,
                                        values=[self._shift_text(s) for s in self.shifts], justify="right")
        self.shift_combo.current(0)
        self.shift_combo.pack(side="right", padx=(6, 0))
        self.shift_combo.bind("<<ComboboxSelected>>", lambda _e: self._change_shift(self.shift_combo.current()))
        if self.can_configure and self.full:
            button(bar, "⚙", self._configure_shifts, kind="secondary").pack(side="right", padx=(4, 0))

        if self.can_write:
            self.save_btn = button(bar, "ذخیره همه  (Ctrl+S)", self._save, kind="success")
            self.save_btn.pack(side="left")
        self.dirty_pill = pill(bar, textvariable=self.dirty_var, tone="warning")
        self.dirty_pill.pack(side="left", padx=8)

        # --- filter row ------------------------------------------------------
        frow = tk.Frame(self, bg=GRAY_BG)
        frow.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(frow, text="جستجوی تجهیز:", font=FONT_SMALL, bg=GRAY_BG, fg=TEXT_MUTED).pack(side="right")
        se = ttk.Entry(frow, textvariable=self.search_var, justify="right", width=24)
        se.pack(side="right", padx=(6, 12))
        self.search_var.trace_add("write", lambda *_: self._refresh_tree())
        tk.Label(frow, text="دسته:", font=FONT_SMALL, bg=GRAY_BG, fg=TEXT_MUTED).pack(side="right")
        self.category_combo = ttk.Combobox(frow, textvariable=self.category_var, state="readonly",
                                           width=18, justify="right")
        self.category_combo.pack(side="right", padx=(6, 12))
        self.category_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_tree())
        self.only_filled = tk.BooleanVar(value=False)
        ttk.Checkbutton(frow, text="فقط ردیف‌های ثبت‌شده", variable=self.only_filled,
                        command=self._refresh_tree).pack(side="right")
        tk.Label(frow, text="Enter: خانه بعد  •  Del: پاک کردن ردیف (کار نکرد)  •  توقف‌ها در پنل کناری",
                 font=FONT_SMALL, bg=GRAY_BG, fg=TEXT_MUTED).pack(side="left")

        if not self.full:
            note = tk.Label(
                self, font=FONT_SMALL, bg=WARNING_SOFT, fg="#92400E", anchor="e", justify="right",
                padx=12, pady=6,
                text="حالت ساده: جدول‌های شیفت هنوز در پایگاه داده ساخته نشده‌اند "
                     "(اسکریپت deploy\\add_machine_shift_tables.sql). توقف‌ها به‌صورت دقیقه وارد می‌شوند و علت آن‌ها ذخیره نمی‌شود.")
            note.pack(fill="x", padx=20, pady=(0, 8))

        # --- body: sheet (right) + stops panel (left) ------------------------
        body = tk.Frame(self, bg=GRAY_BG)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 6))

        souter, sbox = card(body, padx=0, pady=0)
        souter.pack(side="top", fill="both", expand=True)
        cols = [c[0] for c in COLUMNS]
        self.tree = ttk.Treeview(sbox, columns=cols, show="headings", selectmode="browse",
                                 style="Sheet.Treeview", height=9)
        for key, title, width, _ed in COLUMNS:
            self.tree.heading(key, text=title, anchor="center")
            self.tree.column(key, width=width, minwidth=60, anchor="center",
                             stretch=key == "machine")
        self.tree.column("machine", anchor="e")
        self.tree["displaycolumns"] = tuple(reversed(cols))
        vsb = ttk.Scrollbar(sbox, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="left", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("dirty", background="#FFF8E1")
        self.tree.tag_configure("empty", foreground="#9AA4B2")
        self.tree.tag_configure("legacy", foreground="#6B7280", background="#F5F7FA")
        self.tree.tag_configure("error", background=DANGER_SOFT)
        self.tree.tag_configure("low", foreground="#B45309")
        self.tree.tag_configure("bad", foreground="#B91C1C")

        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._on_select())
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<Return>", lambda _e: self._edit_first_open())
        self.tree.bind("<Delete>", lambda _e: self._clear_row())
        self.tree.bind("<Key>", self._on_key)
        self._save_binding = self.winfo_toplevel().bind(
            "<Control-s>", lambda _e: (self._save() if self.winfo_exists() else None), add="+")

        # totals
        foot = tk.Frame(body, bg=GRAY_BG)
        foot.pack(fill="x", pady=(6, 8))
        tk.Label(foot, textvariable=self.total_var, font=FONT_BOLD, bg=GRAY_BG, fg=TEXT_DARK).pack(side="right")

        self._build_stops_panel(body)

    def _build_stops_panel(self, parent):
        outer, box = card(parent, padx=14, pady=10)
        outer.pack(side="top", fill="x", pady=(0, 16))

        right = tk.Frame(box, bg=WHITE)
        right.pack(side="right", fill="y")
        self.stops_title = tk.Label(right, text="توقف‌ها", font=FONT_HEADING, bg=WHITE, fg=TEXT_DARK, anchor="e")
        self.stops_title.pack(fill="x")
        self.stops_sub = tk.Label(right, text="یک تجهیز را در جدول انتخاب کنید", font=FONT_SMALL,
                                  bg=WHITE, fg=TEXT_MUTED, anchor="e", wraplength=380, justify="right")
        self.stops_sub.pack(fill="x", pady=(2, 8))

        self.stop_from = tk.StringVar()
        self.stop_to = tk.StringVar()
        self.stop_reason = tk.StringVar()
        self.stop_detail = tk.StringVar()

        r1 = tk.Frame(right, bg=WHITE)
        r1.pack(fill="x")
        tk.Label(r1, text="از ساعت", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        self.stop_from_entry = ttk.Entry(r1, textvariable=self.stop_from, width=7, justify="center")
        self.stop_from_entry.pack(side="right", padx=(4, 10))
        tk.Label(r1, text="تا", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        self.stop_to_entry = ttk.Entry(r1, textvariable=self.stop_to, width=7, justify="center")
        self.stop_to_entry.pack(side="right", padx=(4, 10))
        self.stop_dur_lbl = tk.Label(r1, text="", font=FONT_SMALL, bg=WHITE, fg=ACCENT, width=8)
        self.stop_dur_lbl.pack(side="right")

        r2 = tk.Frame(right, bg=WHITE)
        r2.pack(fill="x", pady=(8, 0))
        tk.Label(r2, text="علت", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        self.reason_combo = ttk.Combobox(r2, textvariable=self.stop_reason, state="readonly", width=30,
                                         values=[t for _c, t in REASON_CHOICES], justify="right")
        self.reason_combo.pack(side="right", padx=(4, 0))

        r3 = tk.Frame(right, bg=WHITE)
        r3.pack(fill="x", pady=(8, 0))
        tk.Label(r3, text="شرح", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        detail_entry = ttk.Entry(r3, textvariable=self.stop_detail, justify="right", width=33)
        detail_entry.pack(side="right", padx=(4, 0))

        btns = tk.Frame(right, bg=WHITE)
        btns.pack(fill="x", pady=(10, 0))
        self.add_stop_btn = button(btns, "＋ افزودن توقف  (Enter)", self._add_stop, kind="primary")
        self.add_stop_btn.pack(side="right")
        self.del_stop_btn = button(btns, "حذف توقف انتخاب‌شده", self._delete_stop, kind="danger")
        self.del_stop_btn.pack(side="right", padx=(6, 0))

        for v in (self.stop_from, self.stop_to):
            v.trace_add("write", lambda *_: self._preview_stop())
        for w in (self.stop_from_entry, self.stop_to_entry, detail_entry):
            w.bind("<Return>", lambda _e: (self._add_stop(), "break")[1])

        tk.Frame(box, bg="#E5E9EF", width=1).pack(side="right", fill="y", padx=14)

        left = tk.Frame(box, bg=WHITE)
        left.pack(side="right", fill="both", expand=True)
        cols = ("from", "to", "dur", "reason", "detail")
        self.stops = ttk.Treeview(left, columns=cols, show="headings", height=6, style="Stops.Treeview",
                                  selectmode="browse")
        for key, title, width in (("from", "از", 60), ("to", "تا", 60), ("dur", "مدت", 60),
                                  ("reason", "علت", 190), ("detail", "شرح", 160)):
            self.stops.heading(key, text=title)
            self.stops.column(key, width=width, anchor="center", stretch=key == "detail")
        self.stops["displaycolumns"] = tuple(reversed(cols))
        self.stops.pack(fill="both", expand=True)
        self.stops.tag_configure("planned", foreground="#1D4ED8")
        self.stops.bind("<Delete>", lambda _e: self._delete_stop())
        tk.Label(left, font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED, anchor="e", justify="right",
                 text="آبی = توقف برنامه‌ریزی‌شده (شستشو، نت، استراحت، بدون برنامه): از «زمان تولید» کم می‌شود.   "
                      "بقیه = خرابی / غیربرنامه: از «کارکرد» کم می‌شود.").pack(fill="x", pady=(6, 0))
        self._stops_enabled(False)

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _shift_text(s):
        return f"{s['name']}  ({s['start']}–{s['end']})"

    def _shift_minutes(self):
        return parse_clock(self.shift["start"]), parse_clock(self.shift["end"])

    def _stops_enabled(self, on):
        state = "normal" if (on and self.can_write and self.full) else "disabled"
        for w in (self.stop_from_entry, self.stop_to_entry):
            w.configure(state=state)
        self.reason_combo.configure(state="readonly" if state == "normal" else "disabled")
        for b in (self.add_stop_btn, self.del_stop_btn):
            b.configure(state=state)

    def _row(self, eq_id):
        return self.rows.setdefault(eq_id, {
            "start": None, "end": None, "output": None, "events": [],
            "pstop_typed": 0, "ustop_typed": 0, "dirty": False, "source": None,
            "daily": None, "other_shifts": 0, "notes": "",
        })

    def _calc(self, row):
        if self.full:
            events = [(f, t, cat) for f, t, cat, _d in row["events"]]
            return compute_shift(row["start"], row["end"], events, CATEGORY_PLANNED)
        res = compute_shift(row["start"], row["end"], [], CATEGORY_PLANNED)
        if res["window"] is not None:
            p, u = row["pstop_typed"] or 0, row["ustop_typed"] or 0
            res["planned_stop"], res["unplanned_stop"] = p, u
            res["planned_production"] = res["window"] - p
            res["run"] = res["planned_production"] - u
            res["availability"] = (res["run"] / res["planned_production"] * 100
                                   if res["planned_production"] > 0 else None)
            if p + u > res["window"]:
                res["errors"].append("مجموع توقف‌ها بیشتر از فاصله شروع تا پایان است.")
        return res

    def _is_empty(self, row):
        return row["start"] is None and row["end"] is None and row["output"] is None

    # ---------------------------------------------------------- data load

    def _load_equipment(self):
        try:
            eqs = self.eq_repo.get_all_equipment() or []
        except Exception as exc:
            messagebox.showerror("خطا", f"خطا در بارگذاری تجهیزات:\n{exc}", parent=self)
            eqs = []
        self.equipment = [e for e in eqs if str(e.get("status") or "").lower() not in INACTIVE_STATUSES]
        cats = sorted({(e.get("category") or "").strip() for e in self.equipment if e.get("category")})
        self.category_combo["values"] = ["همه دسته‌ها"] + cats

    def _load_sheet(self):
        self._close_editor(commit=False)
        self.rows = {}
        try:
            data = self.repo.load_sheet(self.day, self.shift["name"])
        except Exception as exc:
            messagebox.showerror("خطا", f"خطا در بارگذاری برگه:\n{exc}", parent=self)
            data = {}
        for eq_id, d in data.items():
            r = self._row(eq_id)
            r["source"] = d["source"]
            r["other_shifts"] = d.get("other_shifts", 0)
            r["notes"] = d.get("notes", "")
            r["output"] = d.get("output")
            if d["source"] == "shift":
                r["start"], r["end"] = clock_of(d["start"]), clock_of(d["end"])
                r["events"] = [(clock_of(e["start"]), clock_of(e["end"]), e["category"], e["detail"])
                               for e in d["events"]]
                if not self.full:
                    pass
            else:
                r["daily"] = d.get("daily")
        self.weekday_lbl.configure(text=jalali_weekday_name(self.day))
        self._refresh_tree()
        self._update_dirty()
        self._show_stops(None)

    # ------------------------------------------------------------- render

    def _visible_equipment(self):
        q = latin_digits(self.search_var.get()).casefold().split()
        cat = self.category_var.get()
        out = []
        for e in self.equipment:
            text = f"{e.get('code') or ''} {e.get('name') or ''}".casefold()
            if q and not all(t in text for t in q):
                continue
            if cat and cat != "همه دسته‌ها" and (e.get("category") or "").strip() != cat:
                continue
            if self.only_filled.get():
                r = self.rows.get(e["id"])
                if not r or (self._is_empty(r) and r["source"] != "daily"):
                    continue
            out.append(e)
        return out

    def _values(self, e):
        r = self.rows.get(e["id"]) or self._row(e["id"])
        name = f"{e.get('name') or ''}  ·  {e.get('code') or ''}"
        if r["source"] == "daily" and not r["dirty"] and r["start"] is None:
            d = r["daily"] or {}
            planned, oper = d.get("planned", 0), d.get("operating", 0)
            avail = f"{oper / planned * 100:.1f}%" if planned else "—"
            vals = {"machine": name, "start": "", "end": "", "pstop": "",
                    "ustop": fmt_hm((d.get("downtime") or 0) * 60), "pprod": fmt_hm(planned * 60),
                    "run": fmt_hm(oper * 60), "avail": avail,
                    "output": "" if r["output"] is None else r["output"], "status": "ثبت روزانه (قدیمی)"}
            return vals, ["legacy"]
        c = self._calc(r)
        tags = []
        if self._is_empty(r):
            status = "● کار نکرد / حذف" if r["dirty"] else "—"
            tags.append("empty")
        elif c["errors"]:
            status = "⚠ " + c["errors"][0][:28]
            tags.append("error")
        else:
            status = "● ذخیره نشده" if r["dirty"] else "✓ ثبت شده"
        if r["other_shifts"]:
            status += f"  (+{r['other_shifts']} شیفت)"
        if r["dirty"]:
            tags.append("dirty")
        av = c["availability"]
        if av is not None and not c["errors"]:
            tags.append("bad" if av < 75 else "low" if av < 90 else "")
        vals = {
            "machine": name,
            "start": fmt_clock(r["start"]), "end": fmt_clock(r["end"]),
            "pstop": fmt_hm(c["planned_stop"]) if c["window"] is not None else "",
            "ustop": fmt_hm(c["unplanned_stop"]) if c["window"] is not None else "",
            "pprod": fmt_hm(c["planned_production"]) if c["planned_production"] is not None else "",
            "run": fmt_hm(c["run"]) if c["run"] is not None else "",
            "avail": f"{av:.1f}%" if av is not None else "",
            "output": "" if r["output"] is None else r["output"],
            "status": status,
        }
        return vals, [t for t in tags if t]

    def _refresh_tree(self):
        self._close_editor(commit=True)
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for e in self._visible_equipment():
            vals, tags = self._values(e)
            self.tree.insert("", "end", iid=str(e["id"]), values=[vals[c[0]] for c in COLUMNS], tags=tags)
        if sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])
            self.tree.see(sel[0])
        self._update_totals()

    def _refresh_row(self, eq_id):
        iid = str(eq_id)
        if not self.tree.exists(iid):
            return
        e = next((x for x in self.equipment if x["id"] == eq_id), None)
        if e is None:
            return
        vals, tags = self._values(e)
        self.tree.item(iid, values=[vals[c[0]] for c in COLUMNS], tags=tags)
        self._update_totals()
        self._update_dirty()

    def _update_totals(self):
        pprod = run = ustop = 0
        output = filled = 0
        for eq_id, r in self.rows.items():
            if r["source"] == "daily" and r["start"] is None and not r["dirty"]:
                continue
            if self._is_empty(r):
                continue
            c = self._calc(r)
            if c["window"] is None:
                continue
            filled += 1
            pprod += c["planned_production"] or 0
            run += c["run"] or 0
            ustop += c["unplanned_stop"] or 0
            output += int(r["output"] or 0)
        avail = f"{run / pprod * 100:.1f}%" if pprod else "—"
        self.total_var.set(
            f"ثبت‌شده: {filled} از {len(self.equipment)} تجهیز   •   زمان تولید برنامه: {fmt_hm(pprod)}   •   "
            f"کارکرد: {fmt_hm(run)}   •   توقف غیربرنامه: {fmt_hm(ustop)}   •   دسترس‌پذیری: {avail}   •   تولید: {output:,}")

    def _update_dirty(self):
        n = sum(1 for r in self.rows.values() if r["dirty"])
        self.dirty_var.set(f"{n} ردیف ذخیره نشده" if n else "")
        set_pill_tone(self.dirty_pill, "warning" if n else "neutral")
        if not n:
            self.dirty_pill.configure(bg=WHITE)

    # --------------------------------------------------------- navigation

    def _confirm_discard(self):
        if not any(r["dirty"] for r in self.rows.values()):
            return True
        ans = messagebox.askyesnocancel("تغییرات ذخیره نشده",
                                        "تغییرات این برگه ذخیره شود؟", parent=self)
        if ans is None:
            return False
        if ans:
            return self._save()
        return True

    def confirm_leave(self):
        return self._confirm_discard()

    def _change_day(self, day):
        if day is None or day == self.day:
            self.date_entry.set_date(self.day)
            return
        if not self._confirm_discard():
            self.date_entry.set_date(self.day)
            return
        self.day = day
        self.date_entry.set_date(day)
        self._load_sheet()

    def _change_shift(self, index):
        if index < 0 or self.shifts[index] is self.shift:
            return
        if not self._confirm_discard():
            self.shift_combo.current(self.shifts.index(self.shift))
            return
        self.shift = self.shifts[index]
        self._load_sheet()

    def open_day(self, day):
        self._change_day(day)

    # ------------------------------------------------------------ editing

    def _editable(self):
        return EDITABLE_BASIC if not self.full else {"start", "end", "output"}

    def _order(self):
        return [c[0] for c in COLUMNS if c[0] in self._editable()]

    def _on_double(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        iid = self.tree.identify_row(event.y)
        col_index = int(self.tree.identify_column(event.x).lstrip("#") or 0) - 1
        disp = self.tree["displaycolumns"]
        if not iid or col_index < 0 or col_index >= len(disp):
            return
        col = disp[col_index]
        if col in self._editable():
            self._open_editor(iid, col)

    def _edit_first_open(self):
        sel = self.tree.selection()
        if not sel:
            return "break"
        r = self._row(int(sel[0]))
        for col in self._order():
            if (col in ("start", "end") and r[col] is None) or (col == "output" and r["output"] is None):
                self._open_editor(sel[0], col)
                return "break"
        self._open_editor(sel[0], self._order()[0])
        return "break"

    def _on_key(self, event):
        if self._editor is not None or not self.can_write:
            return
        ch = event.char
        if ch and (ch.isdigit() or ch in "۰۱۲۳۴۵۶۷۸۹"):
            sel = self.tree.selection()
            if sel:
                self._edit_first_open()
                if self._editor is not None:
                    self._editor[2].set(ch)
                    self._editor[0].icursor("end")
                return "break"

    def _cell_text(self, eq_id, col):
        r = self._row(eq_id)
        if col in ("start", "end"):
            return fmt_clock(r[col])
        if col == "output":
            return "" if r["output"] is None else str(r["output"])
        if col == "pstop":
            return str(r["pstop_typed"] or "")
        if col == "ustop":
            return str(r["ustop_typed"] or "")
        return ""

    def _open_editor(self, iid, col):
        if not self.can_write:
            return
        self._close_editor(commit=True)
        self.tree.see(iid)
        self.tree.update_idletasks()
        bbox = self.tree.bbox(iid, col)
        if not bbox:
            return
        x, y, w, h = bbox
        var = tk.StringVar(value=self._cell_text(int(iid), col))
        ent = ttk.Entry(self.tree, textvariable=var, justify="center", font=FONT_NORMAL)
        ent.place(x=x, y=y, width=w, height=h)
        ent.focus_set()
        ent.select_range(0, "end")
        self._editor = (ent, (iid, col), var)
        ent.bind("<Return>", lambda _e: self._editor_move(+1) or "break")
        ent.bind("<Tab>", lambda _e: self._editor_move(+1) or "break")
        ent.bind("<Shift-Tab>", lambda _e: self._editor_move(-1) or "break")
        ent.bind("<Down>", lambda _e: self._editor_move_row(+1) or "break")
        ent.bind("<Up>", lambda _e: self._editor_move_row(-1) or "break")
        ent.bind("<Escape>", lambda _e: (self._close_editor(commit=False), self.tree.focus_set(), "break")[2])
        ent.bind("<FocusOut>", lambda _e: self.after(1, lambda: self._close_editor(commit=True, quiet=True)))

    def _commit_value(self, iid, col, text):
        eq_id = int(iid)
        r = self._row(eq_id)
        text = latin_digits(text)
        if col in ("start", "end"):
            value = parse_clock(text)                       # ValueError on bad input
            if value is not None and value == 1440:
                value = 0
            if r[col] == value:
                return True
            r[col] = value
            if value is not None:
                other = "end" if col == "start" else "start"
                if r[other] is None:                        # fill the other from the shift
                    s, e = self._shift_minutes()
                    r[other] = e if other == "end" else s
        elif col == "output":
            if text == "":
                value = None
            else:
                value = int(float(text))
                if value < 0:
                    raise ValueError(text)
            if r["output"] == value:
                return True
            r["output"] = value
            if value is not None and r["start"] is None:    # ran the normal shift
                r["start"], r["end"] = self._shift_minutes()
        else:                                               # basic mode minutes
            value = int(float(text)) if text else 0
            if value < 0:
                raise ValueError(text)
            key = "pstop_typed" if col == "pstop" else "ustop_typed"
            if r[key] == value:
                return True
            r[key] = value
            if r["start"] is None:
                r["start"], r["end"] = self._shift_minutes()
        r["dirty"] = True
        self._refresh_row(eq_id)
        if self._selected_eq == eq_id:
            self._show_stops(eq_id)
        return True

    def _close_editor(self, commit=True, quiet=False):
        if self._editor is None:
            return True
        ent, (iid, col), var = self._editor
        if commit:
            try:
                self._commit_value(iid, col, var.get())
            except ValueError:
                self.bell()
                if quiet:            # focus left the cell: drop the invalid text
                    self._editor = None
                    try:
                        ent.destroy()
                    except tk.TclError:
                        pass
                    return False
                self._editor = None  # avoid FocusOut re-entry while the message is open
                messagebox.showwarning(
                    "مقدار نامعتبر",
                    "ساعت را به شکل 07:30 و تولید/دقیقه را به‌صورت عدد وارد کنید.", parent=self)
                self._editor = (ent, (iid, col), var)
                ent.focus_set()
                ent.select_range(0, "end")
                return False
        self._editor = None
        try:
            ent.destroy()
        except tk.TclError:
            pass
        return True

    def _editor_move(self, step):
        iid, col = self._editor[1]
        if not self._close_editor(commit=True):
            return
        order = self._order()
        idx = order.index(col) + step
        children = list(self.tree.get_children())
        row_idx = children.index(iid) if iid in children else 0
        if idx >= len(order):
            idx, row_idx = 0, row_idx + 1
        elif idx < 0:
            idx, row_idx = len(order) - 1, row_idx - 1
        if 0 <= row_idx < len(children):
            nxt = children[row_idx]
            self.tree.selection_set(nxt)
            self._open_editor(nxt, order[idx])
        else:
            self.tree.focus_set()

    def _editor_move_row(self, step):
        iid, col = self._editor[1]
        if not self._close_editor(commit=True):
            return
        children = list(self.tree.get_children())
        i = children.index(iid) + step if iid in children else 0
        if 0 <= i < len(children):
            self.tree.selection_set(children[i])
            self._open_editor(children[i], col)

    def _clear_row(self):
        if not self.can_write:
            return
        sel = self.tree.selection()
        if not sel:
            return
        eq_id = int(sel[0])
        r = self._row(eq_id)
        if self._is_empty(r) and r["source"] is None:
            return
        if r["events"] and not messagebox.askyesno(
                "پاک کردن ردیف", "این تجهیز در این شیفت کار نکرده است؟\nساعات و توقف‌های آن پاک می‌شود.", parent=self):
            return
        r.update(start=None, end=None, output=None, events=[], pstop_typed=0, ustop_typed=0, dirty=True)
        if r["source"] == "daily":
            r["source"] = "daily-cleared"
        self._refresh_row(eq_id)
        self._show_stops(eq_id)

    # -------------------------------------------------------------- stops

    def _on_select(self):
        sel = self.tree.selection()
        self._show_stops(int(sel[0]) if sel else None)

    def _show_stops(self, eq_id):
        self._selected_eq = eq_id
        self.stops.delete(*self.stops.get_children())
        if eq_id is None:
            self.stops_title.configure(text="توقف‌ها")
            self.stops_sub.configure(text="یک تجهیز را در جدول انتخاب کنید")
            self._stops_enabled(False)
            return
        e = next((x for x in self.equipment if x["id"] == eq_id), {})
        r = self._row(eq_id)
        self.stops_title.configure(text=f"توقف‌ها — {e.get('name', '')}")
        if not self.full:
            self.stops_sub.configure(text="در حالت ساده، توقف‌ها را به دقیقه در جدول وارد کنید.")
            self._stops_enabled(False)
            return
        if r["start"] is None:
            s, en = self._shift_minutes()
            self.stops_sub.configure(text=f"ساعت کار ثبت نشده؛ با افزودن توقف، ساعت شیفت ({fmt_clock(s)}–{fmt_clock(en)}) در نظر گرفته می‌شود.")
        else:
            c = self._calc(r)
            self.stops_sub.configure(text=f"کار: {fmt_clock(r['start'])} تا {fmt_clock(r['end'])}  •  "
                                          f"توقف برنامه‌ای {fmt_hm(c['planned_stop'])}  •  خرابی {fmt_hm(c['unplanned_stop'])}")
        for i, (f, t, cat, detail) in enumerate(sorted(r["events"], key=lambda ev: (ev[0] - (r["start"] or 0)) % 1440)):
            dur = (t - f) % 1440 or 1440
            self.stops.insert("", "end", iid=str(i), values=(fmt_clock(f), fmt_clock(t), fmt_hm(dur),
                                                             CATEGORY_LABEL.get(cat, cat), detail),
                              tags=("planned",) if CATEGORY_PLANNED.get(cat) else ())
        r["events"].sort(key=lambda ev: (ev[0] - (r["start"] or 0)) % 1440)
        self._stops_enabled(True)

    def _preview_stop(self):
        try:
            f, t = parse_clock(self.stop_from.get()), parse_clock(self.stop_to.get())
        except ValueError:
            self.stop_dur_lbl.configure(text="نامعتبر", fg=DANGER)
            return
        if f is None or t is None:
            self.stop_dur_lbl.configure(text="")
            return
        dur = (t - f) % 1440
        self.stop_dur_lbl.configure(text=f"= {fmt_hm(dur)}" if dur else "", fg=ACCENT)

    def _add_stop(self):
        eq_id = self._selected_eq
        if eq_id is None or not self.can_write or not self.full:
            return
        r = self._row(eq_id)
        try:
            f, t = parse_clock(self.stop_from.get()), parse_clock(self.stop_to.get())
        except ValueError:
            messagebox.showwarning("توقف", "ساعت «از» و «تا» را به شکل 09:15 وارد کنید.", parent=self)
            return
        if f is None or t is None:
            messagebox.showwarning("توقف", "ساعت «از» و «تا» توقف را وارد کنید.", parent=self)
            return
        idx = self.reason_combo.current()
        code = REASON_CHOICES[idx][0] if 0 <= idx < len(REASON_CHOICES) else REASON_BY_TEXT.get(self.stop_reason.get())
        if not code:
            messagebox.showwarning("توقف", "علت توقف را انتخاب کنید.", parent=self)
            return
        f, t = f % 1440, t % 1440
        if r["start"] is None:
            r["start"], r["end"] = self._shift_minutes()
        trial = dict(r, events=r["events"] + [(f, t, code, self.stop_detail.get().strip())])
        c = self._calc(trial)
        if c["errors"]:
            messagebox.showwarning("توقف", "\n".join(c["errors"]), parent=self)
            return
        r["events"] = trial["events"]
        r["dirty"] = True
        self.stop_from.set("")
        self.stop_to.set("")
        self.stop_detail.set("")
        self._refresh_row(eq_id)
        self._show_stops(eq_id)
        self.stop_from_entry.focus_set()

    def _delete_stop(self):
        eq_id = self._selected_eq
        sel = self.stops.selection()
        if eq_id is None or not sel or not self.can_write:
            return
        r = self._row(eq_id)
        idx = int(sel[0])
        if 0 <= idx < len(r["events"]):
            del r["events"][idx]
            r["dirty"] = True
            self._refresh_row(eq_id)
            self._show_stops(eq_id)

    # --------------------------------------------------------------- save

    def _save(self):
        if not self.can_write:
            return False
        if not self._close_editor(commit=True):
            return False
        changes = {}
        for eq_id, r in self.rows.items():
            if not r["dirty"]:
                continue
            if self._is_empty(r):
                changes[eq_id] = None
                continue
            c = self._calc(r)
            name = next((x.get("name") for x in self.equipment if x["id"] == eq_id), eq_id)
            if r["start"] is None or r["end"] is None:
                return self._save_error(eq_id, f"{name}: ساعت شروع و پایان کار را وارد کنید.")
            if c["errors"]:
                return self._save_error(eq_id, f"{name}: " + c["errors"][0])
            day = self.day
            s = r["start"]
            changes[eq_id] = {
                "start": to_datetime(day, s, s),
                "end": to_datetime(day, s, r["end"], is_end=True),
                "output": r["output"],
                "notes": r["notes"],
                "planned_stop": c["planned_stop"],
                "unplanned_stop": c["unplanned_stop"],
                "events": [{"start": to_datetime(day, s, f), "end": to_datetime(day, s, t, is_end=True),
                            "category": cat, "detail": d} for f, t, cat, d in r["events"]],
            }
        if not changes:
            return True
        try:
            ok, msg = self.repo.save_sheet(self.day, self.shift["name"], changes, self.user_name)
        except Exception as exc:
            ok, msg = False, str(exc)
        if not ok:
            messagebox.showerror("خطا در ذخیره", msg, parent=self)
            return False
        self._load_sheet()
        self.dirty_var.set(f"✓ {len(changes)} ردیف ذخیره شد")
        set_pill_tone(self.dirty_pill, "success")
        return True

    def _save_error(self, eq_id, text):
        if self.tree.exists(str(eq_id)):
            self.tree.selection_set(str(eq_id))
            self.tree.see(str(eq_id))
        messagebox.showwarning("بررسی برگه", text, parent=self)
        return False

    # ----------------------------------------------------- shift settings

    def _configure_shifts(self):
        if not self._confirm_discard():
            return
        dlg = ShiftSettingsDialog(self, self.shifts)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        ok, msg = self.repo.save_shifts(dlg.result)
        if not ok:
            messagebox.showerror("خطا", msg, parent=self)
            return
        self.shifts = self.repo.get_shifts()
        self.shift_combo["values"] = [self._shift_text(s) for s in self.shifts]
        self.shift = self.shifts[0]
        self.shift_combo.current(0)
        self._load_sheet()

    # --------------------------------------------------- MainView hooks

    def handle_enter(self):
        self._edit_first_open()

    def handle_delete(self):
        self._clear_row()

    def destroy(self):
        # remove only our own <Control-s> handler from the main window
        try:
            top = self.winfo_toplevel()
            script = top.bind("<Control-s>")
            mine = getattr(self, "_save_binding", None)
            if mine and script:
                kept = "\n".join(line for line in script.split("\n") if mine not in line)
                top.bind("<Control-s>", kept)
                top.deletecommand(mine)
        except tk.TclError:
            pass
        super().destroy()


class ShiftSettingsDialog(tk.Toplevel):
    """Up to 3 shifts: name + start + end (stored in the settings table)."""

    def __init__(self, parent, shifts):
        super().__init__(parent)
        self.result = None
        self.withdraw()
        self.title("تنظیم شیفت‌ها")
        self.configure(bg=WHITE, padx=18, pady=14)
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)

        tk.Label(self, text="شیفت‌های کاری (۱ تا ۳ شیفت). ردیف‌های خالی نادیده گرفته می‌شوند.",
                 font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).grid(row=0, column=0, columnspan=4, sticky="e", pady=(0, 10))
        for col, title in ((3, "نام شیفت"), (2, "شروع"), (1, "پایان")):
            tk.Label(self, text=title, font=FONT_BOLD, bg=WHITE).grid(row=1, column=col, padx=6)
        self.vars = []
        for i in range(3):
            s = shifts[i] if i < len(shifts) else {"name": "", "start": "", "end": ""}
            vs = [tk.StringVar(value=s["name"]), tk.StringVar(value=s["start"]), tk.StringVar(value=s["end"])]
            ttk.Entry(self, textvariable=vs[0], width=18, justify="right").grid(row=i + 2, column=3, padx=6, pady=4)
            ttk.Entry(self, textvariable=vs[1], width=7, justify="center").grid(row=i + 2, column=2, padx=6, pady=4)
            ttk.Entry(self, textvariable=vs[2], width=7, justify="center").grid(row=i + 2, column=1, padx=6, pady=4)
            self.vars.append(vs)
        tk.Label(self, text="مثال: صبح 06:00 تا 14:00 • عصر 14:00 تا 22:00 • شب 22:00 تا 06:00",
                 font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).grid(row=5, column=0, columnspan=4, sticky="e", pady=(8, 0))
        row = tk.Frame(self, bg=WHITE)
        row.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        button(row, "ذخیره", self._ok, kind="success").pack(side="right")
        button(row, "انصراف", self.destroy, kind="secondary").pack(side="right", padx=6)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        center_window(self, self.winfo_reqwidth() + 10, self.winfo_reqheight() + 10)
        self.deiconify()
        self.grab_set()

    def _ok(self):
        out, names = [], set()
        for name_v, s_v, e_v in self.vars:
            name = name_v.get().strip()
            if not name and not s_v.get().strip() and not e_v.get().strip():
                continue
            try:
                s, e = parse_clock(s_v.get()), parse_clock(e_v.get())
            except ValueError:
                s = e = None
            if not name or s is None or e is None or len(name) > 30:
                messagebox.showwarning("شیفت", f"شیفت «{name or '؟'}»: نام (حداکثر ۳۰ حرف) و ساعت شروع/پایان معتبر لازم است.", parent=self)
                return
            if name in names or name == BASIC_SHIFT_NAME:
                messagebox.showwarning("شیفت", f"نام «{name}» تکراری یا رزرو است.", parent=self)
                return
            names.add(name)
            out.append({"name": name, "start": fmt_clock(s), "end": fmt_clock(e)})
        if not out:
            messagebox.showwarning("شیفت", "حداقل یک شیفت لازم است.", parent=self)
            return
        self.result = out
        self.destroy()


class DowntimeParetoTab(tk.Frame):
    """«علل توقف»: which reasons cost the most hours in a period (Pareto)."""

    def __init__(self, parent):
        super().__init__(parent, bg=GRAY_BG)
        from utils.date_helpers import jalali_month_start
        self.repo = MachineShiftRepository(SessionLocal)
        self.eq_repo = EquipmentRepository(SessionLocal)

        outer, bar = card(self, padx=14, pady=10)
        outer.pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(bar, text="از", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        self.start = JalaliDateEntry(bar, width=11)
        self.start.pack(side="right", padx=(6, 12))
        self.start.set_date(jalali_month_start())
        tk.Label(bar, text="تا", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        self.end = JalaliDateEntry(bar, width=11)
        self.end.pack(side="right", padx=(6, 12))
        self.end.set_date(tehran_today())
        tk.Label(bar, text="تجهیز", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        self.eq_var = tk.StringVar(value="همه تجهیزات")
        self.eq_combo = ttk.Combobox(bar, textvariable=self.eq_var, state="readonly", width=28, justify="right")
        self.eq_combo.pack(side="right", padx=(6, 12))
        try:
            eqs = self.eq_repo.get_all_equipment() or []
        except Exception:
            eqs = []
        self.eq_map = {f"{e.get('code') or ''} - {e.get('name') or ''}": e["id"] for e in eqs}
        self.eq_combo["values"] = ["همه تجهیزات"] + list(self.eq_map)
        button(bar, "نمایش", self.load, kind="primary").pack(side="right")

        self.summary = tk.Label(self, text="", font=FONT_BOLD, bg=GRAY_BG, fg=TEXT_DARK, anchor="e")
        self.summary.pack(fill="x", padx=20, pady=(0, 8))

        touter, tbox = card(self, padx=0, pady=0)
        touter.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        cols = ("reason", "kind", "count", "hours", "pct", "cum", "bar")
        self.tree = ttk.Treeview(tbox, columns=cols, show="headings", height=12, style="Sheet.Treeview")
        for key, title, width in (("reason", "علت توقف", 200), ("kind", "نوع", 110), ("count", "دفعات", 70),
                                  ("hours", "مدت (ساعت:دقیقه)", 120), ("pct", "سهم", 70),
                                  ("cum", "تجمعی", 70), ("bar", "", 260)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="e" if key in ("reason", "bar") else "center",
                             stretch=key == "bar")
        self.tree["displaycolumns"] = tuple(reversed(cols))
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("planned", foreground="#1D4ED8")
        self.load()

    def load(self):
        self.tree.delete(*self.tree.get_children())
        if not self.repo.shift_tables_available():
            self.summary.configure(text="برای تحلیل علل توقف، اسکریپت deploy\\add_machine_shift_tables.sql باید اجرا شود.")
            return
        eq_id = self.eq_map.get(self.eq_var.get())
        rows = self.repo.downtime_pareto(self.start.get_date(), self.end.get_date(), eq_id)
        unplanned = [r for r in rows if not CATEGORY_PLANNED.get(r[0])]
        planned = [r for r in rows if CATEGORY_PLANNED.get(r[0])]
        total_u = sum(r[2] for r in unplanned) or 0
        total_p = sum(r[2] for r in planned) or 0
        self.summary.configure(
            text=f"توقف غیربرنامه‌ای: {fmt_hm(total_u)}   •   توقف برنامه‌ریزی‌شده: {fmt_hm(total_p)}   •   "
                 f"تعداد توقف‌ها: {sum(r[1] for r in rows)}")
        top = max((r[2] for r in rows), default=0) or 1
        for group, total in ((unplanned, total_u), (planned, total_p)):
            cum = 0
            for cat, cnt, mins in group:
                cum += mins
                pct = mins / total * 100 if total else 0
                self.tree.insert("", "end", values=(
                    CATEGORY_LABEL.get(cat, cat),
                    "برنامه‌ریزی‌شده" if CATEGORY_PLANNED.get(cat) else "خرابی / غیربرنامه",
                    cnt, fmt_hm(mins), f"{pct:.0f}%", f"{cum / total * 100:.0f}%" if total else "",
                    "█" * max(1, int(round(mins / top * 30))),
                ), tags=("planned",) if CATEGORY_PLANNED.get(cat) else ())
