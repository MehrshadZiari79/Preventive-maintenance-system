# views/work_order_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from datetime import datetime
from database.equipment_repository import EquipmentRepository
from database.user_repository import UserRepository


class WorkOrderDialog(tk.Toplevel):
    def __init__(self, parent, wo_repo, work_order=None, callback=None):
        super().__init__(parent)
        self.wo_repo = wo_repo
        self.work_order = work_order
        self.callback = callback
        self.result = False

        self.title("دستور کار جدید" if not work_order else "ویرایش دستور کار")
        self.geometry("750x920")
        self.resizable(False, False)

        self.eq_repo = EquipmentRepository()
        self.user_repo = UserRepository()

        self._build_ui()
        if work_order:
            self._load_data()

        self.transient(parent)
        self.grab_set()

    def _build_ui(self):
        main = ttk.Frame(self, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main, text="عنوان:", font=("Tahoma", 10)).grid(row=0, column=1, sticky=tk.E, pady=5)
        self.title_entry = ttk.Entry(main, width=50)
        self.title_entry.grid(row=0, column=0, pady=5, padx=5)

        # Equipment
        ttk.Label(main, text="تجهیز:", font=("Tahoma", 10)).grid(row=1, column=1, sticky=tk.E, pady=5)
        self.equipment_combo = ttk.Combobox(main, width=48, state="readonly")
        self.equipment_combo.grid(row=1, column=0, pady=5, padx=5)
        self._load_equipment()

        # Type
        ttk.Label(main, text="نوع:", font=("Tahoma", 10)).grid(row=2, column=1, sticky=tk.E, pady=5)
        type_frame = ttk.Frame(main)
        type_frame.grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        self.type_var = tk.StringVar(value="CORRECTIVE")
        ttk.Radiobutton(type_frame, text="اصلاحی", variable=self.type_var, value="CORRECTIVE").pack(side=tk.RIGHT, padx=10)
        ttk.Radiobutton(type_frame, text="پیشگیرانه", variable=self.type_var, value="PREVENTIVE").pack(side=tk.RIGHT, padx=10)
        ttk.Radiobutton(type_frame, text="بازرسی", variable=self.type_var, value="INSPECTION").pack(side=tk.RIGHT, padx=10)

        # Priority
        ttk.Label(main, text="اولویت:", font=("Tahoma", 10)).grid(row=3, column=1, sticky=tk.E, pady=5)
        priority_frame = ttk.Frame(main)
        priority_frame.grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        self.priority_var = tk.StringVar(value="MEDIUM")
        ttk.Radiobutton(priority_frame, text="کم", variable=self.priority_var, value="LOW").pack(side=tk.RIGHT, padx=5)
        ttk.Radiobutton(priority_frame, text="متوسط", variable=self.priority_var, value="MEDIUM").pack(side=tk.RIGHT, padx=5)
        ttk.Radiobutton(priority_frame, text="زیاد", variable=self.priority_var, value="HIGH").pack(side=tk.RIGHT, padx=5)
        ttk.Radiobutton(priority_frame, text="فوری", variable=self.priority_var, value="URGENT").pack(side=tk.RIGHT, padx=5)

        # Technician
        ttk.Label(main, text="تکنسین تعمیر:", font=("Tahoma", 10)).grid(row=4, column=1, sticky=tk.E, pady=5)
        self.technician_combo = ttk.Combobox(main, width=48, state="readonly")
        self.technician_combo.grid(row=4, column=0, pady=5, padx=5)
        self._load_technicians()

        # Operator
        ttk.Label(main, text="اپراتور تحویل گیرنده:", font=("Tahoma", 10)).grid(row=5, column=1, sticky=tk.E, pady=5)
        self.operator_combo = ttk.Combobox(main, width=48, state="readonly")
        self.operator_combo.grid(row=5, column=0, pady=5, padx=5)
        self._load_operators()

        # Failure report time
        ttk.Label(main, text="ساعت اعلام خرابی:", font=("Tahoma", 10)).grid(row=6, column=1, sticky=tk.E, pady=5)
        failure_frame = ttk.Frame(main)
        failure_frame.grid(row=6, column=0, sticky=tk.W, pady=5, padx=5)
        self.failure_date = DateEntry(failure_frame, width=12, date_pattern='yyyy-mm-dd')
        self.failure_date.pack(side=tk.RIGHT, padx=2)
        self.failure_time = ttk.Entry(failure_frame, width=8)
        self.failure_time.insert(0, "00:00")
        self.failure_time.pack(side=tk.RIGHT, padx=2)
        ttk.Label(failure_frame, text="ساعت:", font=("Tahoma", 9)).pack(side=tk.RIGHT, padx=2)

        # Scheduled date
        ttk.Label(main, text="تاریخ برنامه‌ریزی:", font=("Tahoma", 10)).grid(row=7, column=1, sticky=tk.E, pady=5)
        self.scheduled_date = DateEntry(main, width=47, date_pattern='yyyy-mm-dd')
        self.scheduled_date.grid(row=7, column=0, pady=5, padx=5)

        # Description (technician notes)
        ttk.Label(main, text="توضیحات تعمیرکار:", font=("Tahoma", 10)).grid(row=8, column=1, sticky=tk.NE, pady=5)
        self.desc_text = tk.Text(main, width=50, height=5, font=("Tahoma", 9))
        self.desc_text.grid(row=8, column=0, pady=5, padx=5)

        # Operator notes
        ttk.Label(main, text="توضیحات اپراتور:", font=("Tahoma", 10)).grid(row=9, column=1, sticky=tk.NE, pady=5)
        self.op_notes_text = tk.Text(main, width=50, height=4, font=("Tahoma", 9))
        self.op_notes_text.grid(row=9, column=0, pady=5, padx=5)

        # Operator signature
        ttk.Label(main, text="امضای اپراتور:", font=("Tahoma", 10)).grid(row=10, column=1, sticky=tk.E, pady=5)
        self.op_signature_entry = ttk.Entry(main, width=50)
        self.op_signature_entry.grid(row=10, column=0, pady=5, padx=5)

        # Parts used
        ttk.Label(main, text="قطعات مصرفی (توضیح):", font=("Tahoma", 10)).grid(row=11, column=1, sticky=tk.NE, pady=5)
        self.parts_text = tk.Text(main, width=50, height=4, font=("Tahoma", 9))
        self.parts_text.grid(row=11, column=0, pady=5, padx=5)

        # Manual cost
        ttk.Label(main, text="هزینه دستی (ریال):", font=("Tahoma", 10)).grid(row=12, column=1, sticky=tk.E, pady=5)
        self.manual_cost_entry = ttk.Entry(main, width=20)
        self.manual_cost_entry.grid(row=12, column=0, pady=5, padx=5, sticky=tk.W)
        self.manual_cost_entry.insert(0, "0")

        # Cost description
        ttk.Label(main, text="توضیح هزینه:", font=("Tahoma", 10)).grid(row=13, column=1, sticky=tk.NE, pady=5)
        self.cost_desc_text = tk.Text(main, width=50, height=2, font=("Tahoma", 9))
        self.cost_desc_text.grid(row=13, column=0, pady=5, padx=5)

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=14, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="ذخیره", command=self._on_save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="انصراف", command=self.destroy).pack(side=tk.RIGHT, padx=5)

    def _load_equipment(self):
        equipments = self.eq_repo.get_all_equipment()
        self.equipment_map = {f"{eq['code']} - {eq['name']}": eq['id'] for eq in equipments}
        self.equipment_combo['values'] = list(self.equipment_map.keys())
        if self.equipment_map:
            self.equipment_combo.current(0)

    def _load_technicians(self):
        users = self.user_repo.get_all_users()
        techs = [u for u in users if u['role'] in ['technician', 'admin', 'manager']]
        self.tech_map = {f"{u['full_name']} ({u['username']})": u['id'] for u in techs}
        self.technician_combo['values'] = list(self.tech_map.keys())
        if self.tech_map:
            self.technician_combo.current(0)

    def _load_operators(self):
        users = self.user_repo.get_all_users()
        ops = [u for u in users if u['is_active']]
        self.operator_map = {f"{u['full_name']} ({u['username']})": u['id'] for u in ops}
        self.operator_combo['values'] = list(self.operator_map.keys())
        if self.operator_map:
            self.operator_combo.current(0)

    def _load_data(self):
        wo = self.work_order
        self.title_entry.insert(0, wo.title or "")

        eq_key = f"{wo.equipment.code} - {wo.equipment.name}" if wo.equipment else ""
        if eq_key in self.equipment_map:
            self.equipment_combo.set(eq_key)

        self.type_var.set(wo.type.name)
        self.priority_var.set(wo.priority.name if wo.priority else "MEDIUM")

        if wo.technician:
            tech_key = f"{wo.technician.full_name} ({wo.technician.username})"
            if tech_key in self.tech_map:
                self.technician_combo.set(tech_key)

        if wo.operator:
            op_key = f"{wo.operator.full_name} ({wo.operator.username})"
            if op_key in self.operator_map:
                self.operator_combo.set(op_key)

        if wo.failure_report_time:
            self.failure_date.set_date(wo.failure_report_time.date())
            self.failure_time.delete(0, tk.END)
            self.failure_time.insert(0, wo.failure_report_time.strftime("%H:%M"))

        if wo.scheduled_date:
            self.scheduled_date.set_date(wo.scheduled_date)

        if wo.description:
            self.desc_text.insert("1.0", wo.description)

        if wo.operator_notes:
            self.op_notes_text.insert("1.0", wo.operator_notes)

        if wo.operator_signature:
            self.op_signature_entry.insert(0, wo.operator_signature)

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
            except:
                pass

        scheduled_date = None
        if self.scheduled_date.get():
            scheduled_date = datetime.strptime(self.scheduled_date.get(), "%Y-%m-%d")

        description = self.desc_text.get("1.0", tk.END).strip() or None
        operator_notes = self.op_notes_text.get("1.0", tk.END).strip() or None
        operator_signature = self.op_signature_entry.get().strip() or None
        parts_used = self.parts_text.get("1.0", tk.END).strip() or None

        manual_cost = 0.0
        try:
            manual_cost = float(self.manual_cost_entry.get().strip())
        except:
            pass
        cost_description = self.cost_desc_text.get("1.0", tk.END).strip() or None

        if self.work_order:
            success, msg = self.wo_repo.update_work_order(
                self.work_order.id,
                title, equipment_id, type_str, priority,
                technician_id, scheduled_date, description, parts_used,
                operator_id, failure_report_time, operator_notes, operator_signature,
                manual_cost=manual_cost, cost_description=cost_description
            )
        else:
            success, msg = self.wo_repo.create_work_order(
                title, equipment_id, type_str, priority,
                technician_id, scheduled_date, description, parts_used, None,
                operator_id, failure_report_time, operator_notes, operator_signature,
                manual_cost=manual_cost, cost_description=cost_description
            )

        if success:
            messagebox.showinfo("موفق", msg)
            self.result = True
            if self.callback:
                self.callback()
            self.destroy()
        else:
            messagebox.showerror("خطا", msg)