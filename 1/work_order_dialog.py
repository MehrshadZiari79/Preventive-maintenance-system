import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from datetime import datetime

from database.equipment_repository import EquipmentRepository
from database.user_repository import UserRepository


class WorkOrderDialog(tk.Toplevel):
    def __init__(self, parent, wo_repo, work_order=None):
        super().__init__(parent)
        self.wo_repo = wo_repo
        self.work_order = work_order
        self.result = None

        self.title("دستور کار جدید" if not work_order else "ویرایش دستور کار")
        self.geometry("600x700")
        self.resizable(False, False)

        self.eq_repo = EquipmentRepository()
        self.user_repo = UserRepository()

        self._build_ui()
        if work_order:
            self._load_data()

        self.transient(parent)
        self.grab_set()

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="عنوان:", font=("Arial", 10)).grid(row=0, column=1, sticky=tk.E, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=0, column=0, pady=5, padx=5)

        # Equipment
        ttk.Label(main_frame, text="تجهیز:", font=("Arial", 10)).grid(row=1, column=1, sticky=tk.E, pady=5)
        self.equipment_combo = ttk.Combobox(main_frame, width=38, state="readonly")
        self.equipment_combo.grid(row=1, column=0, pady=5, padx=5)
        self._load_equipment()

        # Type
        ttk.Label(main_frame, text="نوع:", font=("Arial", 10)).grid(row=2, column=1, sticky=tk.E, pady=5)
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        self.type_var = tk.StringVar(value="CORRECTIVE")
        ttk.Radiobutton(type_frame, text="اصلاحی", variable=self.type_var, value="CORRECTIVE").pack(side=tk.RIGHT, padx=10)
        ttk.Radiobutton(type_frame, text="پیشگیرانه", variable=self.type_var, value="PREVENTIVE").pack(side=tk.RIGHT, padx=10)

        # Priority
        ttk.Label(main_frame, text="اولویت:", font=("Arial", 10)).grid(row=3, column=1, sticky=tk.E, pady=5)
        priority_frame = ttk.Frame(main_frame)
        priority_frame.grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        self.priority_var = tk.StringVar(value="MEDIUM")
        ttk.Radiobutton(priority_frame, text="کم", variable=self.priority_var, value="LOW").pack(side=tk.RIGHT, padx=5)
        ttk.Radiobutton(priority_frame, text="متوسط", variable=self.priority_var, value="MEDIUM").pack(side=tk.RIGHT, padx=5)
        ttk.Radiobutton(priority_frame, text="زیاد", variable=self.priority_var, value="HIGH").pack(side=tk.RIGHT, padx=5)
        ttk.Radiobutton(priority_frame, text="فوری", variable=self.priority_var, value="URGENT").pack(side=tk.RIGHT, padx=5)

        # Technician
        ttk.Label(main_frame, text="تکنسین:", font=("Arial", 10)).grid(row=4, column=1, sticky=tk.E, pady=5)
        self.technician_combo = ttk.Combobox(main_frame, width=38, state="readonly")
        self.technician_combo.grid(row=4, column=0, pady=5, padx=5)
        self._load_technicians()

        # Scheduled Date
        ttk.Label(main_frame, text="تاریخ برنامه‌ریزی:", font=("Arial", 10)).grid(row=5, column=1, sticky=tk.E, pady=5)
        self.date_entry = DateEntry(main_frame, width=37, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.date_entry.grid(row=5, column=0, pady=5, padx=5)

        # Description
        ttk.Label(main_frame, text="توضیحات:", font=("Arial", 10)).grid(row=6, column=1, sticky=tk.NE, pady=5)
        self.desc_text = tk.Text(main_frame, width=40, height=6, font=("Arial", 9))
        self.desc_text.grid(row=6, column=0, pady=5, padx=5)

        # Parts Used
        ttk.Label(main_frame, text="قطعات مصرفی:", font=("Arial", 10)).grid(row=7, column=1, sticky=tk.NE, pady=5)
        self.parts_text = tk.Text(main_frame, width=40, height=4, font=("Arial", 9))
        self.parts_text.grid(row=7, column=0, pady=5, padx=5)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=8, column=0, columnspan=2, pady=20)
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
        technicians = [u for u in users if u['role'].lower() == 'technician']  # ✅ safe either way
        self.technician_map = {u['username']: u['id'] for u in technicians}
        self.technician_combo['values'] = list(self.technician_map.keys())
        if self.technician_map:
            self.technician_combo.current(0) 

    def _load_data(self):
        wo = self.work_order
        self.title_entry.insert(0, wo.title or "")

        eq_key = f"{wo.equipment.code} - {wo.equipment.name}"
        if eq_key in self.equipment_map:
            self.equipment_combo.set(eq_key)

        self.type_var.set(wo.type.name)
        self.priority_var.set(wo.priority.name if wo.priority else "MEDIUM")

        if wo.technician:
            tech_key = wo.technician.username
            if tech_key in self.technician_map:
                self.technician_combo.set(tech_key)

        if wo.scheduled_date:
            self.date_entry.set_date(wo.scheduled_date)

        if wo.description:
            self.desc_text.insert("1.0", wo.description)

        if wo.parts_used:
            self.parts_text.insert("1.0", wo.parts_used)

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
        technician_id = self.technician_map.get(tech_key)

        scheduled_date = self.date_entry.get_date()
        description = self.desc_text.get("1.0", tk.END).strip() or None
        parts_used = self.parts_text.get("1.0", tk.END).strip() or None

        if self.work_order:
            success, msg = self.wo_repo.update_work_order(
                self.work_order.id, title, equipment_id, type_str, priority,
                technician_id, scheduled_date, description, parts_used
            )
        else:
            success, msg = self.wo_repo.create_work_order(
                title, equipment_id, type_str, priority,
                technician_id, scheduled_date, description, parts_used
            )

        if success:
            messagebox.showinfo("موفق", msg)
            self.result = True
            self.destroy()
        else:
            messagebox.showerror("خطا", msg)
