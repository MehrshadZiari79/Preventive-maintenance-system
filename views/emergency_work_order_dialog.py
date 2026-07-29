# views/emergency_work_order_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from database.work_order_repository import WorkOrderRepository
from database.work_order import WorkOrderType
from database.equipment_repository import EquipmentRepository
from auth.auth_manager import AuthManager
from tkcalendar import DateEntry
from database.work_order import WorkOrder
from database.db import SessionLocal
from views.searchable_combobox import SearchableCombobox

from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

BG = GRAY_BG
CARD_BG = WHITE
CARD_BORDER = GRAY_BORDER

class EmergencyWorkOrderDialog(tk.Toplevel):
    def __init__(self, parent, equipment_repo=None, preselected_equipment=None):
        super().__init__(parent)
        self.parent = parent
        self.equipment_repo = equipment_repo or EquipmentRepository(SessionLocal)
        self.preselected = preselected_equipment
        self.result = False

        self.title("ثبت دستور کار اضطراری")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)

        self._build_ui()
        self._center_window(550, 700)

    def _center_window(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────
        header = tk.Frame(self, bg=NAVY, height=55)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🚨 دستور کار اضطراری", font=FONT_TITLE,
                 bg=NAVY, fg=WHITE).pack(pady=12)

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
        main_card = tk.Frame(scrollable, bg=CARD_BORDER)
        main_card.pack(fill="both", expand=True, padx=20, pady=15)
        main_frame = tk.Frame(main_card, bg=CARD_BG)
        main_frame.pack(fill="both", expand=True, padx=1, pady=1)

        row = 0

        # Equipment
        if not self.preselected:
            tk.Label(main_frame, text="تجهیز:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).grid(row=row, column=0, sticky="e", padx=5, pady=8)
            equipment_list = self.equipment_repo.get_all_equipment()
            eq_names = [f"{eq['code']} - {eq['name']}" for eq in equipment_list]
            self.equipment_combo = SearchableCombobox(main_frame, font=FONT_NORMAL, state="normal", width=35)
            self.equipment_combo.set_completion_list(eq_names)
            self.equipment_combo.grid(row=row, column=1, padx=5, pady=8, sticky="w")
            self.eq_map = {f"{eq['code']} - {eq['name']}": eq['id'] for eq in equipment_list}
            row += 1
        else:
            tk.Label(main_frame, text="تجهیز:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).grid(row=row, column=0, sticky="e", padx=5, pady=8)
            tk.Label(main_frame, text=self.preselected['name'], font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).grid(row=row, column=1, padx=5, pady=8, sticky="w")
            self.selected_equipment_id = self.preselected['id']
            row += 1

        # Title
        tk.Label(main_frame, text="عنوان *:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).grid(row=row, column=0, sticky="e", padx=5, pady=8)
        self.title_entry = tk.Entry(main_frame, font=FONT_NORMAL, width=40)
        self.title_entry.grid(row=row, column=1, padx=5, pady=8, sticky="w")
        row += 1

        # Description
        tk.Label(main_frame, text="شرح:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).grid(row=row, column=0, sticky="ne", padx=5, pady=8)
        self.desc_text = tk.Text(main_frame, font=FONT_NORMAL, width=40, height=5, wrap="word")
        self.desc_text.grid(row=row, column=1, padx=5, pady=8, sticky="w")
        row += 1

        # Priority (radio buttons)
        tk.Label(main_frame, text="اولویت:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).grid(row=row, column=0, sticky="e", padx=5, pady=8)
        priority_frame = tk.Frame(main_frame, bg=CARD_BG)
        priority_frame.grid(row=row, column=1, padx=5, pady=8, sticky="w")
        self.priority_var = tk.StringVar(value="URGENT")
        for text, val in [("کم", "LOW"), ("متوسط", "MEDIUM"), ("بالا", "HIGH"), ("فوری", "URGENT")]:
            tk.Radiobutton(priority_frame, text=text, variable=self.priority_var, value=val,
                           bg=CARD_BG, font=FONT_NORMAL).pack(side="right", padx=10)
        row += 1

        # Deadline
        tk.Label(main_frame, text="تاریخ سررسید (ددلاین):", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).grid(row=row, column=0, sticky="e", padx=5, pady=8)
        self.deadline_date = DateEntry(main_frame, width=20, date_pattern='yyyy-mm-dd',
                                       background=NAVY, foreground=WHITE,
                                       headersbackground=NAVY, headersforeground=WHITE)
        self.deadline_date.grid(row=row, column=1, padx=5, pady=8, sticky="w")
        self.deadline_date.set_date(datetime.now())
        row += 1

        # Reporter (current user)
        current_user = AuthManager.get_current_user()
        tk.Label(main_frame, text="گزارش دهنده:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).grid(row=row, column=0, sticky="e", padx=5, pady=8)
        tk.Label(main_frame, text=current_user.full_name, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).grid(row=row, column=1, padx=5, pady=8, sticky="w")
        row += 1

        # ── Buttons (inside scrollable, at the end) ─────────────
        btn_frame = tk.Frame(main_frame, bg=CARD_BG)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)
        tk.Button(btn_frame, text="ثبت", font=FONT_NORMAL,
                  bg=NAVY, fg=WHITE, relief="flat", cursor="hand2",
                  command=self._save, padx=20, pady=8).pack(side="right", padx=10)
        tk.Button(btn_frame, text="انصراف", font=FONT_NORMAL,
                  bg=NAVY_LIGHT, fg=WHITE, relief="flat", cursor="hand2",
                  command=self.destroy, padx=20, pady=8).pack(side="right")

    def _save(self):
        if not self.preselected:
            selection = self.equipment_combo.get()
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

        deadline = None
        if self.deadline_date.get():
            deadline = datetime.strptime(self.deadline_date.get(), "%Y-%m-%d")

        wo_repo = WorkOrderRepository(SessionLocal)
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
            operator_signature=None,
            deadline=deadline
        )

        if success:
            db = SessionLocal()
            try:
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