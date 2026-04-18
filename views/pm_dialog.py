"""
PM Schedule Dialog - Add / Edit Preventive Maintenance Schedule
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from tkcalendar import DateEntry

BG = "#F0F4F8"
WHITE = "#FFFFFF"
HEADER = "#1A73E8"
TEXT = "#202124"
SUBTLE = "#5F6368"
BORDER = "#DADCE0"
RED = "#D93025"

FONT_TITLE = ("Tahoma", 13, "bold")
FONT_LABEL = ("Tahoma", 10, "bold")
FONT_INPUT = ("Tahoma", 10)
FONT_SMALL = ("Tahoma", 9)

FREQUENCY_OPTIONS = {
    "روزانه": ("daily", 1),
    "هفتگی": ("weekly", 7),
    "ماهانه": ("monthly", 30),
    "سه‌ماهه": ("quarterly", 90),
    "شش‌ماهه": ("biannual", 180),
    "سالانه": ("annual", 365),
    "سفارشی": ("custom", None),
}

FREQ_FA = {v[0]: k for k, v in FREQUENCY_OPTIONS.items()}


class PMDialog(tk.Toplevel):
    def __init__(self, parent, pm_repo, equipment_repo, user_repo,
                 schedule=None, preselect_equipment_id=None):
        super().__init__(parent)
        self.pm_repo = pm_repo
        self.equipment_repo = equipment_repo
        self.user_repo = user_repo
        self.schedule = schedule
        self.preselect_equipment_id = preselect_equipment_id
        self.result = False

        title = "ویرایش برنامه PM" if schedule else "افزودن برنامه PM"
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self._center(700, 620)
        self.grab_set()

        self._load_data()
        self._build_ui()
        if schedule:
            self._fill_form()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _load_data(self):
        self.all_equipment = self.equipment_repo.get_all_equipment()
        technicians = self.user_repo.get_all_users()
        self.all_technicians = [u for u in technicians if u.get("is_active")]

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=HEADER, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        title_text = "✏️  ویرایش برنامه PM" if self.schedule else "➕  افزودن برنامه PM"
        tk.Label(header, text=title_text, font=FONT_TITLE,
                 bg=HEADER, fg=WHITE).pack(side="right", padx=20, pady=14)

        # Scrollable body
        body_outer = tk.Frame(self, bg=BG)
        body_outer.pack(fill="both", expand=True, padx=20, pady=16)

        canvas = tk.Canvas(body_outer, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body_outer, orient="vertical", command=canvas.yview)
        self.body = tk.Frame(canvas, bg=BG)

        self.body.bind("<Configure>",
                       lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_form()

        # Buttons
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        tk.Button(btn_frame, text="💾  ذخیره", font=FONT_LABEL,
                  bg=HEADER, fg=WHITE, relief="flat",
                  padx=20, pady=8, cursor="hand2",
                  command=self._save).pack(side="right", padx=(8, 0))

        tk.Button(btn_frame, text="انصراف", font=FONT_INPUT,
                  bg=BORDER, fg=TEXT, relief="flat",
                  padx=20, pady=8, cursor="hand2",
                  command=self.destroy).pack(side="right")

    def _field(self, parent, label, row, col=0, colspan=1):
        tk.Label(parent, text=label, font=FONT_LABEL,
                 bg=BG, fg=TEXT, anchor="e").grid(
            row=row, column=col * 2, sticky="e", padx=(0, 8), pady=6)

    def _build_form(self):
        f = self.body
        f.columnconfigure(1, weight=1)
        f.columnconfigure(3, weight=1)

        # Title
        tk.Label(f, text="عنوان برنامه *", font=FONT_LABEL,
                 bg=BG, fg=TEXT, anchor="e").grid(
            row=0, column=2, sticky="e", padx=(0, 8), pady=6)
        self.title_var = tk.StringVar()
        tk.Entry(f, textvariable=self.title_var, font=FONT_INPUT,
                 width=40, relief="solid", bd=1).grid(
            row=0, column=3, sticky="ew", pady=6, columnspan=3)

        # Equipment
        tk.Label(f, text="تجهیز *", font=FONT_LABEL,
                 bg=BG, fg=TEXT, anchor="e").grid(
            row=1, column=2, sticky="e", padx=(0, 8), pady=6)
        self.equipment_var = tk.StringVar()
        eq_names = [f"{e['code']} - {e['name']}" for e in self.all_equipment]
        self.eq_combo = ttk.Combobox(f, textvariable=self.equipment_var,
                                     values=eq_names, font=FONT_INPUT,
                                     width=38, state="readonly")
        self.eq_combo.grid(row=1, column=3, sticky="ew", pady=6, columnspan=3)

        if self.preselect_equipment_id:
            for i, e in enumerate(self.all_equipment):
                if e["id"] == self.preselect_equipment_id:
                    self.eq_combo.current(i)
                    break

        # Technician
        tk.Label(f, text="تکنسین مسئول", font=FONT_LABEL,
                 bg=BG, fg=TEXT, anchor="e").grid(
            row=2, column=2, sticky="e", padx=(0, 8), pady=6)
        self.tech_var = tk.StringVar()
        tech_names = ["تعیین نشده"] + [u["full_name"] for u in self.all_technicians]
        self.tech_combo = ttk.Combobox(f, textvariable=self.tech_var,
                                       values=tech_names, font=FONT_INPUT,
                                       width=38, state="readonly")
        self.tech_combo.current(0)
        self.tech_combo.grid(row=2, column=3, sticky="ew", pady=6, columnspan=3)

        # Frequency
        tk.Label(f, text="دوره تناوب *", font=FONT_LABEL,
                 bg=BG, fg=TEXT, anchor="e").grid(
            row=3, column=0, sticky="e", padx=(0, 8), pady=6)
        self.freq_var = tk.StringVar(value="ماهانه")
        freq_combo = ttk.Combobox(f, textvariable=self.freq_var,
                                  values=list(FREQUENCY_OPTIONS.keys()),
                                  font=FONT_INPUT, width=18, state="readonly")
        freq_combo.grid(row=3, column=1, sticky="ew", pady=6)
        freq_combo.bind("<<ComboboxSelected>>", self._on_freq_change)

        # Interval days
        tk.Label(f, text="تعداد روز", font=FONT_LABEL,
                 bg=BG, fg=TEXT, anchor="e").grid(
            row=3, column=2, sticky="e", padx=(0, 8), pady=6)
        self.interval_var = tk.IntVar(value=30)
        self.interval_entry = tk.Entry(f, textvariable=self.interval_var,
                                       font=FONT_INPUT, width=10,
                                       relief="solid", bd=1)
        self.interval_entry.grid(row=3, column=3, sticky="w", pady=6)
        self.interval_entry.config(state="disabled")

        # Start date
        tk.Label(f, text="تاریخ شروع *", font=FONT_LABEL,
                 bg=BG, fg=TEXT, anchor="e").grid(
            row=4, column=0, sticky="e", padx=(0, 8), pady=6)
        self.start_date = DateEntry(f, font=FONT_INPUT, width=18,
                                    date_pattern="yyyy-mm-dd",
                                    background=HEADER, foreground=WHITE)
        self.start_date.grid(row=4, column=1, sticky="w", pady=6)

        # Estimated duration
        tk.Label(f, text="مدت تخمینی (دقیقه)", font=FONT_LABEL,
                 bg=BG, fg=TEXT, anchor="e").grid(
            row=4, column=2, sticky="e", padx=(0, 8), pady=6)
        self.duration_var = tk.StringVar()
        tk.Entry(f, textvariable=self.duration_var, font=FONT_INPUT,
                 width=10, relief="solid", bd=1).grid(
            row=4, column=3, sticky="w", pady=6)

        # Checklist
        tk.Label(f, text="چک‌لیست کارها", font=FONT_LABEL,
                 bg=BG, fg=TEXT, anchor="e").grid(
            row=5, column=0, sticky="ne", padx=(0, 8), pady=6)
        self.checklist_text = tk.Text(f, font=FONT_INPUT, width=55, height=6,
                                      relief="solid", bd=1, wrap="word")
        self.checklist_text.grid(row=5, column=1, columnspan=5,
                                 sticky="ew", pady=6)
        tk.Label(f, text="هر مورد را در یک خط بنویسید",
                 font=FONT_SMALL, bg=BG, fg=SUBTLE).grid(
            row=6, column=1, columnspan=5, sticky="w")

        # Notes
        tk.Label(f, text="یادداشت", font=FONT_LABEL,
                 bg=BG, fg=TEXT, anchor="e").grid(
            row=7, column=0, sticky="ne", padx=(0, 8), pady=6)
        self.notes_text = tk.Text(f, font=FONT_INPUT, width=55, height=3,
                                  relief="solid", bd=1, wrap="word")
        self.notes_text.grid(row=7, column=1, columnspan=5,
                             sticky="ew", pady=6)

    def _on_freq_change(self, event=None):
        freq_fa = self.freq_var.get()
        _, days = FREQUENCY_OPTIONS.get(freq_fa, ("custom", None))
        if days is not None:
            self.interval_var.set(days)
            self.interval_entry.config(state="disabled")
        else:
            self.interval_entry.config(state="normal")

    def _fill_form(self):
        s = self.schedule
        self.title_var.set(s["title"])

        for i, e in enumerate(self.all_equipment):
            if e["id"] == s["equipment_id"]:
                self.eq_combo.current(i)
                break

        if s["technician_id"]:
            for i, u in enumerate(self.all_technicians):
                if u["id"] == s["technician_id"]:
                    self.tech_combo.current(i + 1)
                    break

        freq_fa = FREQ_FA.get(s["frequency"], "ماهانه")
        self.freq_var.set(freq_fa)
        self.interval_var.set(s["interval_days"])

        if s["next_due"]:
            try:
                dt = datetime.strptime(s["next_due"], "%Y-%m-%d")
                self.start_date.set_date(dt)
            except Exception:
                pass

        if s["estimated_duration"]:
            self.duration_var.set(str(s["estimated_duration"]))

        if s["checklist"]:
            self.checklist_text.insert("1.0", s["checklist"])

        if s["notes"]:
            self.notes_text.insert("1.0", s["notes"])

    def _save(self):
        title = self.title_var.get().strip()
        eq_str = self.equipment_var.get()
        freq_fa = self.freq_var.get()

        if not title:
            messagebox.showerror("خطا", "عنوان برنامه الزامی است.", parent=self)
            return
        if not eq_str:
            messagebox.showerror("خطا", "لطفاً یک تجهیز انتخاب کنید.", parent=self)
            return

        # Find equipment id
        eq_id = None
        for e in self.all_equipment:
            if f"{e['code']} - {e['name']}" == eq_str:
                eq_id = e["id"]
                break
        if not eq_id:
            messagebox.showerror("خطا", "تجهیز انتخاب نشده.", parent=self)
            return

        # Find technician id
        tech_id = None
        tech_name = self.tech_var.get()
        if tech_name != "تعیین نشده":
            for u in self.all_technicians:
                if u["full_name"] == tech_name:
                    tech_id = u["id"]
                    break

        freq_en, default_days = FREQUENCY_OPTIONS.get(freq_fa, ("monthly", 30))
        try:
            interval = int(self.interval_var.get())
        except Exception:
            interval = default_days or 30

        try:
            start_dt = datetime.strptime(
                self.start_date.get_date().strftime("%Y-%m-%d"), "%Y-%m-%d"
            )
        except Exception:
            start_dt = datetime.utcnow()

        duration_str = self.duration_var.get().strip()
        duration = int(duration_str) if duration_str.isdigit() else None
        checklist = self.checklist_text.get("1.0", "end").strip()
        notes = self.notes_text.get("1.0", "end").strip()

        if self.schedule:
            ok, msg = self.pm_repo.update(
                schedule_id=self.schedule["id"],
                title=title,
                equipment_id=eq_id,
                technician_id=tech_id,
                frequency=freq_en,
                interval_days=interval,
                next_due=start_dt + __import__("datetime").timedelta(days=interval),
                checklist=checklist,
                estimated_duration=duration,
                notes=notes,
            )
        else:
            ok, msg = self.pm_repo.create(
                title=title,
                equipment_id=eq_id,
                technician_id=tech_id,
                frequency=freq_en,
                interval_days=interval,
                start_date=start_dt,
                checklist=checklist,
                estimated_duration=duration,
                notes=notes,
            )

        if ok:
            self.result = True
            self.destroy()
        else:
            messagebox.showerror("خطا", msg, parent=self)
