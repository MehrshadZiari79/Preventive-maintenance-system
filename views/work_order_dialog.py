# views/work_order_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from datetime import datetime
from database.equipment_repository import EquipmentRepository
from database.user_repository import UserRepository
from database.work_order import WorkOrderPriority
from views.searchable_combobox import SearchableCombobox
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

BG = GRAY_BG
CARD_BG = WHITE
PRIMARY = NAVY

class WorkOrderDialog(tk.Toplevel):
    def __init__(self, parent, wo_repo, work_order=None, callback=None):
        super().__init__(parent)
        self.wo_repo = wo_repo
        self.work_order = work_order
        self.callback = callback
        self.result = False

        self.title("دستور کار جدید" if not work_order else "ویرایش دستور کار")
        self.geometry("850x900")
        self.resizable(False, False)

        from database.db import SessionLocal
        self.eq_repo = EquipmentRepository(SessionLocal)
        self.user_repo = UserRepository(SessionLocal)

        self._selected_tech_ids = []   # for additional technicians

        self._build_ui()
        if work_order:
            self._load_data()

        self.transient(parent)
        self.grab_set()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────
        header = tk.Frame(self, bg=PRIMARY, height=55)
        header.pack(fill="x")
        head_title = "📝  دستور کار جدید" if not self.work_order else "✏️  ویرایش دستور کار"
        tk.Label(header, text=head_title, font=FONT_HEADING, bg=PRIMARY, fg=WHITE).pack(pady=12)

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

        # Row 0: Title
        ttk.Label(main, text="عنوان *:").grid(row=0, column=1, sticky=tk.E, pady=5)
        self.title_entry = ttk.Entry(main, width=50)
        self.title_entry.grid(row=0, column=0, pady=5)

        # Row 1: Equipment
        ttk.Label(main, text="تجهیز *:").grid(row=1, column=1, sticky=tk.E, pady=5)
        self.equipment_combo = SearchableCombobox(main, width=48, state="normal")
        self.equipment_combo.grid(row=1, column=0, pady=5)
        self._load_equipment()

        # Row 2: Type
        ttk.Label(main, text="نوع:").grid(row=2, column=1, sticky=tk.E, pady=5)
        type_frame = ttk.Frame(main)
        type_frame.grid(row=2, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar(value="CORRECTIVE")
        for text, val in [("اصلاحی", "CORRECTIVE"), ("پیشگیرانه", "PREVENTIVE"), ("بازرسی", "INSPECTION")]:
            ttk.Radiobutton(type_frame, text=text, variable=self.type_var, value=val).pack(side=tk.RIGHT, padx=10)

        # Row 3: Priority
        ttk.Label(main, text="اولویت:").grid(row=3, column=1, sticky=tk.E, pady=5)
        prio_frame = ttk.Frame(main)
        prio_frame.grid(row=3, column=0, sticky=tk.W, pady=5)
        self.priority_var = tk.StringVar(value="MEDIUM")
        for text, val in [("کم", "LOW"), ("متوسط", "MEDIUM"), ("بالا", "HIGH"), ("فوری", "URGENT")]:
            ttk.Radiobutton(prio_frame, text=text, variable=self.priority_var, value=val).pack(side=tk.RIGHT, padx=10)

        # Row 4: Main Technician
        ttk.Label(main, text="تکنسین اصلی:").grid(row=4, column=1, sticky=tk.E, pady=5)
        self.technician_combo = SearchableCombobox(main, width=48, state="normal")
        self.technician_combo.grid(row=4, column=0, pady=5)
        self._load_technicians()

        # Row 5: Additional technicians (listbox)
        ttk.Label(main, text="سایر تکنسین‌ها:").grid(row=5, column=1, sticky=tk.NE, pady=5)
        tech_extra_frame = ttk.Frame(main)
        tech_extra_frame.grid(row=5, column=0, sticky=tk.W, pady=5)

        self.extra_tech_listbox = tk.Listbox(tech_extra_frame, height=4, font=FONT_NORMAL, selectmode=tk.MULTIPLE)
        self.extra_tech_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)

        extra_btn_frame = ttk.Frame(tech_extra_frame)
        extra_btn_frame.pack(side=tk.LEFT, padx=5)
        ttk.Button(extra_btn_frame, text="➕", width=2, command=self._add_tech).pack(pady=2)
        ttk.Button(extra_btn_frame, text="➖", width=2, command=self._remove_tech).pack(pady=2)

        # Row 6: Operator
        ttk.Label(main, text="اپراتور:").grid(row=6, column=1, sticky=tk.E, pady=5)
        self.operator_combo = SearchableCombobox(main, width=48, state="normal")
        self.operator_combo.grid(row=6, column=0, pady=5)
        self._load_operators()

        # Row 7: Failure report time
        ttk.Label(main, text="ساعت اعلام خرابی:").grid(row=7, column=1, sticky=tk.E, pady=5)
        f_frame = ttk.Frame(main)
        f_frame.grid(row=7, column=0, sticky=tk.W, pady=5)
        self.failure_date = DateEntry(f_frame, width=12, date_pattern='yyyy-mm-dd',
                                      background=PRIMARY, foreground=WHITE,
                                      headersbackground=PRIMARY, headersforeground=WHITE)
        self.failure_date.pack(side=tk.RIGHT, padx=2)
        self.failure_time = ttk.Entry(f_frame, width=8)
        self.failure_time.insert(0, "00:00")
        self.failure_time.pack(side=tk.RIGHT, padx=2)
        ttk.Label(f_frame, text="ساعت:").pack(side=tk.RIGHT, padx=2)

        # Row 8: Scheduled date
        ttk.Label(main, text="تاریخ برنامه‌ریزی:").grid(row=8, column=1, sticky=tk.E, pady=5)
        self.scheduled_date = DateEntry(main, width=47, date_pattern='yyyy-mm-dd',
                                        background=PRIMARY, foreground=WHITE,
                                        headersbackground=PRIMARY, headersforeground=WHITE)
        self.scheduled_date.grid(row=8, column=0, pady=5)

        # Row 9: Deadline
        ttk.Label(main, text="تاریخ سررسید (ددلاین):").grid(row=9, column=1, sticky=tk.E, pady=5)
        self.deadline_date = DateEntry(main, width=47, date_pattern='yyyy-mm-dd',
                                       background=PRIMARY, foreground=WHITE,
                                       headersbackground=PRIMARY, headersforeground=WHITE)
        self.deadline_date.grid(row=9, column=0, pady=5)

        # Row 10: Technician description
        ttk.Label(main, text="توضیحات تعمیرکار:").grid(row=10, column=1, sticky=tk.NE, pady=5)
        self.desc_text = tk.Text(main, width=50, height=5, font=FONT_NORMAL, relief="solid", bd=1)
        self.desc_text.grid(row=10, column=0, pady=5)

        # Row 11: Operator notes
        ttk.Label(main, text="توضیحات اپراتور:").grid(row=11, column=1, sticky=tk.NE, pady=5)
        self.op_notes_text = tk.Text(main, width=50, height=4, font=FONT_NORMAL, relief="solid", bd=1)
        self.op_notes_text.grid(row=11, column=0, pady=5)

        # Row 13: Parts used (text)
        ttk.Label(main, text="قطعات مصرفی (توضیح):").grid(row=13, column=1, sticky=tk.NE, pady=5)
        self.parts_text = tk.Text(main, width=50, height=4, font=FONT_NORMAL, relief="solid", bd=1)
        self.parts_text.grid(row=13, column=0, pady=5)

        # Row 14: Manual cost
        ttk.Label(main, text="هزینه دستی (ریال):").grid(row=14, column=1, sticky=tk.E, pady=5)
        self.manual_cost_entry = ttk.Entry(main, width=20)
        self.manual_cost_entry.grid(row=14, column=0, pady=5, sticky=tk.W)
        self.manual_cost_entry.insert(0, "0")

        # Row 15: Cost description
        ttk.Label(main, text="توضیح هزینه:").grid(row=15, column=1, sticky=tk.NE, pady=5)
        self.cost_desc_text = tk.Text(main, width=50, height=2, font=FONT_NORMAL, relief="solid", bd=1)
        self.cost_desc_text.grid(row=15, column=0, pady=5)

        # ── Buttons (outside scrollable, at bottom) ─────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="ذخیره", command=self._on_save,
                  bg=SUCCESS, fg=WHITE, font=FONT_NORMAL, relief="flat", padx=20, pady=8).pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_frame, text="انصراف", command=self.destroy,
                  bg=GRAY_BORDER, fg=TEXT_DARK, font=FONT_NORMAL, relief="flat", padx=20, pady=8).pack(side=tk.RIGHT, padx=5)

    # ── Helper methods (unchanged) ──────────────────────────────
    def _load_equipment(self):
        equipments = self.eq_repo.get_all_equipment()
        self.equipment_map = {f"{eq['code']} - {eq['name']}": eq['id'] for eq in equipments}
        self.equipment_combo.set_completion_list(list(self.equipment_map.keys()))
        if self.equipment_map:
            self.equipment_combo.current(0)

    def _load_technicians(self):
        users = self.user_repo.get_all_users()
        techs = [u for u in users if u['role'] in ['technician', 'admin', 'manager', 'production_expert']]
        self.tech_map = {f"{u['full_name']} ({u['username']})": u['id'] for u in techs}
        self.technician_combo.set_completion_list(list(self.tech_map.keys()))
        self.tech_full_list = users
        if self.tech_map:
            self.technician_combo.current(0)

    def _load_operators(self):
        users = self.user_repo.get_all_users()
        ops = [u for u in users if u['is_active']]
        self.operator_map = {f"{u['full_name']} ({u['username']})": u['id'] for u in ops}
        self.operator_combo.set_completion_list(list(self.operator_map.keys()))
        if self.operator_map:
            self.operator_combo.current(0)

    def _add_tech(self):
        sel = self.technician_combo.get()
        if sel and sel in self.tech_map:
            uid = self.tech_map[sel]
            if uid not in self._selected_tech_ids:
                self._selected_tech_ids.append(uid)
                self.extra_tech_listbox.insert(tk.END, sel)

    def _remove_tech(self):
        selection = self.extra_tech_listbox.curselection()
        if selection:
            index = selection[0]
            removed_name = self.extra_tech_listbox.get(index)
            self.extra_tech_listbox.delete(index)
            uid = self.tech_map.get(removed_name)
            if uid in self._selected_tech_ids:
                self._selected_tech_ids.remove(uid)

    def _load_data(self):
        wo = self.work_order
        self.title_entry.insert(0, wo.title or "")
        eq_key = f"{wo.equipment.code} - {wo.equipment.name}" if wo.equipment else ""
        if eq_key in self.equipment_map:
            self.equipment_combo.set(eq_key)
        self.type_var.set(wo.type.name)
        self.priority_var.set(wo.priority.name)
        if wo.technician:
            tech_key = f"{wo.technician.full_name} ({wo.technician.username})"
            if tech_key in self.tech_map:
                self.technician_combo.set(tech_key)
        if wo.operator:
            op_key = f"{wo.operator.full_name} ({wo.operator.username})"
            if op_key in self.operator_map:
                self.operator_combo.set(op_key)
        for t in wo.technicians:
            key = f"{t.full_name} ({t.username})"
            self.extra_tech_listbox.insert(tk.END, key)
            self._selected_tech_ids.append(t.id)
        if wo.failure_report_time:
            self.failure_date.set_date(wo.failure_report_time.date())
            self.failure_time.delete(0, tk.END)
            self.failure_time.insert(0, wo.failure_report_time.strftime("%H:%M"))
        if wo.scheduled_date:
            self.scheduled_date.set_date(wo.scheduled_date)
        if wo.deadline:
            self.deadline_date.set_date(wo.deadline)
        if wo.description:
            self.desc_text.insert("1.0", wo.description)
        if wo.operator_notes:
            self.op_notes_text.insert("1.0", wo.operator_notes)
        if wo.parts_used:
            self.parts_text.insert("1.0", wo.parts_used)
        if wo.manual_cost:
            self.manual_cost_entry.delete(0, tk.END)
            self.manual_cost_entry.insert(0, str(wo.manual_cost))
        if wo.cost_description:
            self.cost_desc_text.insert("1.0", wo.cost_description)

    def _on_save(self):
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror("خطا", "عنوان الزامی است.")
            return
        eq_key = self.equipment_combo.get()
        if not eq_key:
            messagebox.showerror("خطا", "تجهیز الزامی است.")
            return
        equipment_id = self.equipment_map[eq_key]
        type_str = self.type_var.get()
        priority = self.priority_var.get()
        tech_key = self.technician_combo.get()
        technician_id = self.tech_map.get(tech_key) if tech_key else None
        op_key = self.operator_combo.get()
        operator_id = self.operator_map.get(op_key) if op_key else None

        failure_report_time = None
        if self.failure_date.get() and self.failure_time.get().strip():
            try:
                dt_str = f"{self.failure_date.get()} {self.failure_time.get()}"
                failure_report_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            except: pass

        scheduled_date = None
        if self.scheduled_date.get():
            scheduled_date = datetime.strptime(self.scheduled_date.get(), "%Y-%m-%d")
        deadline = None
        if self.deadline_date.get():
            deadline = datetime.strptime(self.deadline_date.get(), "%Y-%m-%d")

        description = self.desc_text.get("1.0", tk.END).strip() or None
        operator_notes = self.op_notes_text.get("1.0", tk.END).strip() or None
        parts_used = self.parts_text.get("1.0", tk.END).strip() or None
        manual_cost = 0.0
        try: manual_cost = float(self.manual_cost_entry.get().strip())
        except: pass
        cost_description = self.cost_desc_text.get("1.0", tk.END).strip() or None

        additional_tech_ids = self._selected_tech_ids

        if self.work_order:
            success, msg = self.wo_repo.update_work_order(
                self.work_order.id, title, equipment_id, type_str, priority,
                technician_id, scheduled_date, description, parts_used,
                operator_id, failure_report_time, operator_notes, None,   # operator_signature = None
                manual_cost=manual_cost, cost_description=cost_description,
                deadline=deadline, additional_technician_ids=additional_tech_ids
            )
        else:
            success, msg = self.wo_repo.create_work_order(
                title, equipment_id, type_str, priority,
                technician_id, scheduled_date, description, parts_used, None,
                operator_id, failure_report_time, operator_notes, None,   # operator_signature = None
                manual_cost=manual_cost, cost_description=cost_description,
                deadline=deadline, additional_technician_ids=additional_tech_ids
            )
        if success:
            messagebox.showinfo("موفق", msg)
            self.result = True
            if self.callback:
                self.callback()
            self.destroy()
        else:
            messagebox.showerror("خطا", msg)