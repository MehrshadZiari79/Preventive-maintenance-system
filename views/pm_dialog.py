# views/pm_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import json
from database.spare_parts_repository import SparePartsRepository
from database.db import SessionLocal
from tkcalendar import DateEntry

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
TEXT = TEXT_DARK
SUBTLE = TEXT_LIGHT
BORDER = GRAY_BORDER

# Persian frequency map
FREQ_FA_MAP = {
    "daily": "روزانه",
    "weekly": "هفتگی",
    "monthly": "ماهانه",
    "quarterly": "سه‌ماهه",
    "biannual": "شش‌ماهه",
    "annual": "سالانه",
    "custom": "سفارشی",
}
FREQ_EN_MAP = {v: k for k, v in FREQ_FA_MAP.items()}

class PMDialog(tk.Toplevel):
    def __init__(self, parent, pm_repo, equipment_repo, user_repo, schedule=None, callback=None):
        super().__init__(parent)
        self.pm_repo = pm_repo
        self.equipment_repo = equipment_repo
        self.user_repo = user_repo
        self.schedule = schedule
        self.callback = callback
        self.result = False

        self.title("ویرایش برنامه PM" if schedule else "برنامه PM جدید")
        self.geometry("800x850")
        self.resizable(False, False)

        self.sp_repo = SparePartsRepository(SessionLocal)
        self.all_parts = self.sp_repo.get_all()
        self.selected_parts = []

        self._build_ui()
        if schedule:
            self._load_data()
        self.transient(parent)
        self.grab_set()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────
        header = tk.Frame(self, bg=PRIMARY, height=55)
        header.pack(fill="x")
        header.pack_propagate(False)
        title = "📅  " + ("ویرایش برنامه PM" if self.schedule else "برنامه PM جدید")
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
        main = ttk.Frame(scrollable, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.configure("TLabel", background=CARD_BG)
        style.configure("TFrame", background=CARD_BG)
        style.configure("TLabelframe", background=CARD_BG)

        # Row 0: Title
        ttk.Label(main, text="عنوان برنامه:", font=("Tahoma", 10, "bold")).grid(row=0, column=1, sticky=tk.E, pady=5)
        self.title_entry = ttk.Entry(main, width=50)
        self.title_entry.grid(row=0, column=0, pady=5, padx=5)

        # Row 1: Equipment
        ttk.Label(main, text="تجهیز:", font=("Tahoma", 10, "bold")).grid(row=1, column=1, sticky=tk.E, pady=5)
        from views.searchable_combobox import SearchableCombobox
        self.equipment_combo = SearchableCombobox(main, width=48)
        self.equipment_combo.grid(row=1, column=0, pady=5, padx=5)
        self._load_equipment()

        # Row 2: Technician
        ttk.Label(main, text="تکنسین:", font=("Tahoma", 10, "bold")).grid(row=2, column=1, sticky=tk.E, pady=5)
        self.technician_combo = SearchableCombobox(main, width=48)
        self.technician_combo.grid(row=2, column=0, pady=5, padx=5)
        self._load_technicians()

        # Row 3: Frequency
        ttk.Label(main, text="دوره تناوب:", font=("Tahoma", 10, "bold")).grid(row=3, column=1, sticky=tk.E, pady=5)
        self.frequency_combo = ttk.Combobox(main, values=list(FREQ_FA_MAP.values()), width=48, state="readonly")
        self.frequency_combo.grid(row=3, column=0, pady=5, padx=5)
        self.frequency_combo.bind("<<ComboboxSelected>>", self._on_frequency_change)

        # Row 4: Interval (days)
        self.interval_frame = ttk.Frame(main)
        self.interval_frame.grid(row=4, column=0, columnspan=2, pady=5, sticky="w")
        ttk.Label(self.interval_frame, text="بازه (روز):", font=("Tahoma", 10)).pack(side=tk.RIGHT, padx=5)
        self.interval_entry = ttk.Entry(self.interval_frame, width=10)
        self.interval_entry.pack(side=tk.RIGHT)

        # Row 5: Start date (first due)
        ttk.Label(main, text="تاریخ شروع (اولین سررسید):", font=("Tahoma", 10, "bold")).grid(row=5, column=1, sticky=tk.E, pady=5)
        self.start_date = DateEntry(main, width=47, date_pattern='yyyy-mm-dd',
                                    background=PRIMARY, foreground=WHITE,
                                    headersbackground=PRIMARY, headersforeground=WHITE)
        self.start_date.grid(row=5, column=0, pady=5, padx=5)

        # Row 6: Checklist
        ttk.Label(main, text="چک‌لیست / دستورالعمل:", font=("Tahoma", 10, "bold")).grid(row=6, column=1, sticky=tk.NE, pady=5)
        self.checklist_text = tk.Text(main, width=50, height=4, font=("Tahoma", 9), relief="solid", bd=1)
        self.checklist_text.grid(row=6, column=0, pady=5, padx=5)

        # Row 7: Estimated duration
        ttk.Label(main, text="مدت مجاز (روز):", font=("Tahoma", 10, "bold")).grid(row=7, column=1, sticky=tk.E, pady=5)
        self.duration_entry = ttk.Entry(main, width=20)
        self.duration_entry.grid(row=7, column=0, pady=5, padx=5, sticky=tk.W)

        # Row 8: Notes
        ttk.Label(main, text="یادداشت:", font=("Tahoma", 10, "bold")).grid(row=8, column=1, sticky=tk.NE, pady=5)
        self.notes_text = tk.Text(main, width=50, height=3, font=("Tahoma", 9), relief="solid", bd=1)
        self.notes_text.grid(row=8, column=0, pady=5, padx=5)

        # Row 9: Parts required (frame with treeview)
        parts_frame = ttk.LabelFrame(main, text="قطعات مورد نیاز", padding=10)
        parts_frame.grid(row=9, column=0, columnspan=2, pady=10, sticky="ew")
        cols = ("part_number", "name", "stock", "quantity")
        self.parts_tree = ttk.Treeview(parts_frame, columns=cols, show="headings", height=4)
        self.parts_tree.heading("part_number", text="شماره قطعه")
        self.parts_tree.heading("name", text="نام قطعه")
        self.parts_tree.heading("stock", text="موجودی")
        self.parts_tree.heading("quantity", text="تعداد مورد نیاز")
        self.parts_tree.column("part_number", width=120)
        self.parts_tree.column("name", width=200)
        self.parts_tree.column("stock", width=80)
        self.parts_tree.column("quantity", width=80)
        self.parts_tree.pack(fill=tk.X, pady=5)

        btn_frame = ttk.Frame(parts_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="➕ افزودن قطعه", command=self._add_part).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_frame, text="🗑️ حذف قطعه", command=self._remove_part).pack(side=tk.RIGHT, padx=2)

        # ── Buttons (outside scrollable) ────────────────────────
        btn_frame2 = ttk.Frame(self)
        btn_frame2.pack(pady=20)
        tk.Button(btn_frame2, text="ذخیره", command=self._save,
                  bg=SUCCESS, fg=WHITE, font=FONT_NORMAL, relief="flat",
                  padx=20, pady=8).pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_frame2, text="انصراف", command=self.destroy,
                  bg=BORDER, fg=TEXT, font=FONT_NORMAL, relief="flat",
                  padx=20, pady=8).pack(side=tk.RIGHT, padx=5)

    # ── Helper methods (unchanged) ──────────────────────────────
    def _load_equipment(self):
        equipments = self.equipment_repo.get_all_equipment()
        self.equipment_map = {f"{eq['code']} - {eq['name']}": eq['id'] for eq in equipments}
        self.equipment_combo.set_completion_list(list(self.equipment_map.keys()))
        if self.equipment_map:
            self.equipment_combo.current(0)

    def _load_technicians(self):
        users = self.user_repo.get_all_users()
        techs = [u for u in users if u['role'] in ['technician', 'admin', 'manager']]
        self.tech_map = {f"{u['full_name']} ({u['username']})": u['id'] for u in techs}
        self.technician_combo.set_completion_list(list(self.tech_map.keys()))
        if self.tech_map:
            self.technician_combo.current(0)

    def _on_frequency_change(self, event=None):
        persian_freq = self.frequency_combo.get()
        freq_en = FREQ_EN_MAP.get(persian_freq, "monthly")
        if freq_en in ["daily", "weekly", "monthly", "quarterly", "biannual", "annual"]:
            days = {"daily":1, "weekly":7, "monthly":30, "quarterly":90, "biannual":180, "annual":365}
            self.interval_entry.delete(0, tk.END)
            self.interval_entry.insert(0, str(days[freq_en]))
            self.interval_entry.config(state="readonly")
        else:
            self.interval_entry.config(state="normal")
            self.interval_entry.delete(0, tk.END)

    def _add_part(self):
        dialog = tk.Toplevel(self)
        dialog.title("انتخاب قطعه")
        dialog.geometry("400x250")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=BG)

        header = tk.Frame(dialog, bg=PRIMARY, height=35)
        header.pack(fill="x")
        tk.Label(header, text="انتخاب قطعه", font=FONT_NORMAL, bg=PRIMARY, fg=WHITE).pack(pady=8)

        body = tk.Frame(dialog, bg=CARD_BG)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(body, text="قطعه:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).pack(pady=5)
        part_combo = ttk.Combobox(body, values=[f"{p.part_number} - {p.name}" for p in self.all_parts],
                                  width=40, state="readonly", font=FONT_NORMAL)
        part_combo.pack(pady=5)

        tk.Label(body, text="تعداد مورد نیاز:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).pack(pady=5)
        qty_entry = ttk.Entry(body, width=10, font=FONT_NORMAL)
        qty_entry.pack(pady=5)

        def confirm():
            selection = part_combo.get()
            if not selection:
                return
            try:
                qty = int(qty_entry.get())
                if qty <= 0:
                    raise ValueError
            except:
                messagebox.showerror("خطا", "تعداد نامعتبر")
                return
            for p in self.all_parts:
                if f"{p.part_number} - {p.name}" == selection:
                    for item in self.selected_parts:
                        if item['part_id'] == p.id:
                            messagebox.showwarning("تکرار", "این قطعه قبلاً اضافه شده است.")
                            return
                    self.selected_parts.append({
                        "part_id": p.id,
                        "part_number": p.part_number,
                        "name": p.name,
                        "quantity": qty,
                        "stock": p.current_stock
                    })
                    self._refresh_parts_tree()
                    dialog.destroy()
                    return
            messagebox.showerror("خطا", "قطعه یافت نشد")

        tk.Button(body, text="تأیید", command=confirm,
                  bg=SUCCESS, fg=WHITE, font=FONT_NORMAL, relief="flat",
                  padx=15, pady=5).pack(pady=10)
        tk.Button(body, text="انصراف", command=dialog.destroy,
                  bg=BORDER, fg=TEXT, font=FONT_NORMAL, relief="flat",
                  padx=15, pady=5).pack()

    def _remove_part(self):
        selected = self.parts_tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        del self.selected_parts[idx]
        self._refresh_parts_tree()

    def _refresh_parts_tree(self):
        for item in self.parts_tree.get_children():
            self.parts_tree.delete(item)
        for i, p in enumerate(self.selected_parts):
            self.parts_tree.insert("", "end", iid=str(i), values=(
                p['part_number'], p['name'], p['stock'], p['quantity']
            ))

    def _load_data(self):
        s = self.schedule
        self.title_entry.insert(0, s.get("title", ""))
        eq_key = f"{s['equipment_code']} - {s['equipment_name']}"
        if eq_key in self.equipment_map:
            self.equipment_combo.set(eq_key)
        tech_key = s['technician_name']
        for k in self.tech_map:
            if s['technician_name'] in k:
                self.technician_combo.set(k)
                break
        freq_en = s.get("frequency", "monthly")
        freq_persian = FREQ_FA_MAP.get(freq_en, "ماهانه")
        self.frequency_combo.set(freq_persian)
        self._on_frequency_change()
        if s.get("interval_days"):
            self.interval_entry.delete(0, tk.END)
            self.interval_entry.insert(0, str(s["interval_days"]))
        if s.get("next_due_dt"):
            self.start_date.set_date(s["next_due_dt"])
        if s.get("checklist"):
            self.checklist_text.insert("1.0", s["checklist"])
        if s.get("estimated_duration"):
            self.duration_entry.insert(0, str(s["estimated_duration"]))
        if s.get("notes"):
            self.notes_text.insert("1.0", s["notes"])
        if s.get("parts_required"):
            try:
                parts_list = json.loads(s["parts_required"])
                for part_info in parts_list:
                    part_id = part_info["part_id"]
                    qty = part_info["quantity"]
                    part = next((p for p in self.all_parts if p.id == part_id), None)
                    if part:
                        self.selected_parts.append({
                            "part_id": part.id,
                            "part_number": part.part_number,
                            "name": part.name,
                            "quantity": qty,
                            "stock": part.current_stock
                        })
                self._refresh_parts_tree()
            except:
                pass

    def _save(self):
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror("خطا", "عنوان الزامی است.")
            return
        eq_key = self.equipment_combo.get()
        if not eq_key:
            messagebox.showerror("خطا", "تجهیز الزامی است.")
            return
        equipment_id = self.equipment_map[eq_key]
        tech_key = self.technician_combo.get()
        technician_id = self.tech_map.get(tech_key) if tech_key else None

        persian_freq = self.frequency_combo.get()
        frequency = FREQ_EN_MAP.get(persian_freq, "monthly")
        try:
            interval_days = int(self.interval_entry.get())
        except:
            interval_days = 30

        start_date = self.start_date.get_date()
        checklist = self.checklist_text.get("1.0", tk.END).strip() or None
        try:
            estimated_duration = int(self.duration_entry.get()) if self.duration_entry.get() else None
        except:
            estimated_duration = None
        notes = self.notes_text.get("1.0", tk.END).strip() or None

        parts_required = None
        if self.selected_parts:
            parts_required = json.dumps([{"part_id": p["part_id"], "quantity": p["quantity"]} for p in self.selected_parts])

        if self.pm_repo.duplicate_pm_exists(equipment_id, title, frequency,
                                            exclude_id=self.schedule["id"] if self.schedule else None):
            if not messagebox.askyesno("تکرار احتمالی",
                                       "یک برنامه PM مشابه برای این تجهیز و دوره تناوب وجود دارد. آیا همچنان ادامه می‌دهید؟"):
                return

        if self.schedule:
            success, msg = self.pm_repo.update(
                self.schedule["id"], title, equipment_id, technician_id,
                frequency, interval_days, start_date, checklist,
                estimated_duration, notes, parts_required
            )
        else:
            success, msg = self.pm_repo.create(
                title, equipment_id, technician_id, frequency,
                interval_days, start_date, checklist,
                estimated_duration, notes, parts_required
            )
        if success:
            messagebox.showinfo("موفق", msg)
            self.result = True
            if self.callback:
                self.callback()
            self.destroy()
        else:
            messagebox.showerror("خطا", msg)