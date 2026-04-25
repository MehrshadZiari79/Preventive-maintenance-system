# views/emergency_work_order_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from database.work_order_repository import WorkOrderRepository
from database.work_order import WorkOrderType, WorkOrderPriority
from database.equipment_repository import EquipmentRepository
from auth.auth_manager import AuthManager


BG = "#F0F4F8"
WHITE = "#FFFFFF"
PRIMARY = "#1A73E8"
TEXT = "#202124"
SUBTLE = "#5F6368"
BORDER = "#DADCE0"
DANGER = "#EA4335"

FONT_TITLE = ("Tahoma", 12, "bold")
FONT_NORMAL = ("Tahoma", 10)
FONT_BTN = ("Tahoma", 10, "bold")


class EmergencyWorkOrderDialog(tk.Toplevel):
    def __init__(self, parent, equipment_repo=None, preselected_equipment=None):
        """
        :param parent: parent widget
        :param equipment_repo: optional EquipmentRepository to load equipment list
        :param preselected_equipment: optional equipment dict (with 'id' and 'name') to preselect
        """
        super().__init__(parent)
        self.parent = parent
        self.equipment_repo = equipment_repo or EquipmentRepository()
        self.preselected = preselected_equipment
        self.result = False

        self.title("ثبت دستور کار اضطراری")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)

        self._build_ui()
        self._center_window(450, 550)

    def _center_window(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Title
        tk.Label(self, text="🚨 دستور کار اضطراری", font=FONT_TITLE,
                 bg=BG, fg=DANGER).pack(pady=(20, 10))

        main_frame = tk.Frame(self, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        main_frame.pack(fill="both", expand=True, padx=20, pady=10, ipadx=20, ipady=15)

        # Equipment selection (if not preselected)
        row = 0
        if not self.preselected:
            tk.Label(main_frame, text="تجهیز:", font=FONT_NORMAL, bg=WHITE, fg=TEXT).grid(row=row, column=0, sticky="e", padx=5, pady=8)
            self.equipment_var = tk.StringVar()
            equipment_list = self.equipment_repo.get_all_equipment()
            eq_names = [f"{eq['code']} - {eq['name']}" for eq in equipment_list]
            self.eq_combo = ttk.Combobox(main_frame, textvariable=self.equipment_var, values=eq_names,
                                         font=FONT_NORMAL, state="readonly", width=35)
            self.eq_combo.grid(row=row, column=1, padx=5, pady=8, sticky="w")
            # Map display string to equipment id
            self.eq_map = {f"{eq['code']} - {eq['name']}": eq['id'] for eq in equipment_list}
            row += 1
        else:
            # Show preselected equipment as label
            tk.Label(main_frame, text="تجهیز:", font=FONT_NORMAL, bg=WHITE, fg=TEXT).grid(row=row, column=0, sticky="e", padx=5, pady=8)
            tk.Label(main_frame, text=self.preselected['name'], font=FONT_NORMAL, bg=WHITE, fg=TEXT).grid(row=row, column=1, padx=5, pady=8, sticky="w")
            self.selected_equipment_id = self.preselected['id']
            row += 1

        # Title
        tk.Label(main_frame, text="عنوان:", font=FONT_NORMAL, bg=WHITE, fg=TEXT).grid(row=row, column=0, sticky="e", padx=5, pady=8)
        self.title_entry = tk.Entry(main_frame, font=FONT_NORMAL, width=40)
        self.title_entry.grid(row=row, column=1, padx=5, pady=8, sticky="w")
        row += 1

        # Description
        tk.Label(main_frame, text="شرح:", font=FONT_NORMAL, bg=WHITE, fg=TEXT).grid(row=row, column=0, sticky="ne", padx=5, pady=8)
        self.desc_text = tk.Text(main_frame, font=FONT_NORMAL, width=40, height=5, wrap="word")
        self.desc_text.grid(row=row, column=1, padx=5, pady=8, sticky="w")
        row += 1

        # Priority
        tk.Label(main_frame, text="اولویت:", font=FONT_NORMAL, bg=WHITE, fg=TEXT).grid(row=row, column=0, sticky="e", padx=5, pady=8)
        self.priority_var = tk.StringVar(value="urgent")
        priority_frame = tk.Frame(main_frame, bg=WHITE)
        priority_frame.grid(row=row, column=1, padx=5, pady=8, sticky="w")
        priorities = [("فوری", "urgent"), ("بالا", "high"), ("متوسط", "medium"), ("پایین", "low")]
        for text, val in priorities:
            tk.Radiobutton(priority_frame, text=text, variable=self.priority_var, value=val,
                           bg=WHITE, font=FONT_NORMAL).pack(side="right", padx=10)
        row += 1

        # Reported by (current user)
        current_user = AuthManager.get_current_user()
        tk.Label(main_frame, text="گزارش دهنده:", font=FONT_NORMAL, bg=WHITE, fg=TEXT).grid(row=row, column=0, sticky="e", padx=5, pady=8)
        tk.Label(main_frame, text=current_user.full_name, font=FONT_NORMAL, bg=WHITE, fg=TEXT).grid(row=row, column=1, padx=5, pady=8, sticky="w")
        row += 1

        # Buttons
        btn_frame = tk.Frame(main_frame, bg=WHITE)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)
        tk.Button(btn_frame, text="ثبت", font=FONT_BTN, bg=PRIMARY, fg=WHITE,
                  relief="flat", cursor="hand2", command=self._save, padx=20, pady=8).pack(side="right", padx=10)
        tk.Button(btn_frame, text="انصراف", font=FONT_BTN, bg=BORDER, fg=TEXT,
                  relief="flat", cursor="hand2", command=self.destroy, padx=20, pady=8).pack(side="right")

    def _save(self):
        # Get equipment id
        if hasattr(self, 'eq_combo'):
            selection = self.equipment_var.get()
            if not selection:
                messagebox.showerror("خطا", "لطفاً تجهیز را انتخاب کنید.", parent=self)
                return
            equipment_id = self.eq_map.get(selection)
            if not equipment_id:
                messagebox.showerror("خطا", "تجهیز نامعتبر است.", parent=self)
                return
        else:
            equipment_id = self.selected_equipment_id

        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror("خطا", "عنوان الزامی است.", parent=self)
            return

        description = self.desc_text.get("1.0", tk.END).strip()
        priority = self.priority_var.get()
        current_user = AuthManager.get_current_user()
        emergency_reported_by = current_user.full_name

        # Create work order
        wo_repo = WorkOrderRepository()
        success, msg = wo_repo.create_work_order(
            title=title,
            equipment_id=equipment_id,
            type_str="EMERGENCY",
            priority=priority,
            technician_id=None,
            scheduled_date=datetime.now(),
            description=description,
            parts_used=None,
            schedule_id=None,
            operator_id=current_user.id,
            failure_report_time=datetime.now(),
            operator_notes=description,
            operator_signature=None
        )

        if success:
            # Optionally also store emergency_reported_by directly? The model has the field but we didn't use it
            # We can update the work order to set emergency_reported_by
            # For simplicity, we set via repository later; but let's do direct update
            from database.db import SessionLocal
            db = SessionLocal()
            try:
                # Get the latest work order (the one just created)
                wo = db.query(WorkOrder).order_by(WorkOrder.id.desc()).first()
                if wo:
                    wo.emergency_reported_by = emergency_reported_by
                    db.commit()
            finally:
                db.close()
            self.result = True
            messagebox.showinfo("موفق", "دستور کار اضطراری با موفقیت ثبت شد.", parent=self)
            self.destroy()
        else:
            messagebox.showerror("خطا", f"خطا در ثبت: {msg}", parent=self)