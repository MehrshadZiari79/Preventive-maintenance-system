import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
from database.work_order_repository import WorkOrderRepository
from database.work_order import WorkOrderStatus
from views.work_order_dialog import WorkOrderDialog
from views.export_dialog import run_work_order_export
from views.emergency_work_order_dialog import EmergencyWorkOrderDialog
from views.parts_selection_dialog import PartsSelectionDialog   # added back

class WorkOrderView(tk.Frame):
    def __init__(self, parent, work_order_repo, current_user):
        super().__init__(parent, bg="#F0F4F8")
        self.current_user = current_user
        self.wo_repo = work_order_repo

        self._build_ui()
        self._load()

    def _build_ui(self):
        # Toolbar
        toolbar = tk.Frame(self, bg="#34495e", height=60)
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)

        tk.Label(toolbar, text="📝 مدیریت دستور کارها", font=("Tahoma", 14, "bold"),
                 bg="#34495e", fg="white").pack(side="right", padx=20)

        btn_frame = tk.Frame(toolbar, bg="#34495e")
        btn_frame.pack(side="left", padx=20)

        tk.Button(btn_frame, text="➕ کار جدید", command=self._add_work,
                  bg="#27ae60", fg="white", font=("Tahoma", 10, "bold"),
                  cursor="hand2", relief="flat", padx=15, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="🚨 کار اضطراری", command=self._emergency_work,
                  bg="#EA4335", fg="white", font=("Tahoma", 10, "bold"),
                  cursor="hand2", relief="flat", padx=15, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="🔄 بروزرسانی", command=self._load,
                  bg="#800080", fg="white", font=("Tahoma", 10),
                  cursor="hand2", relief="flat", padx=15, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="📤  Excel خروجی  ", command=self._export,
                  bg="#34A853", fg="white", font=("Tahoma", 10),
                  cursor="hand2", relief="flat", padx=15, pady=8).pack(side="left", padx=5)

        # Filter Frame
        filter_frame = tk.Frame(self, bg="#FFFFFF", height=50)
        filter_frame.pack(fill="x", padx=20, pady=(10, 0))
        filter_frame.pack_propagate(False)

        tk.Label(filter_frame, text="فیلتر وضعیت:", bg="#FFFFFF", font=("Tahoma", 10)).pack(side="right", padx=10)

        self.status_var = tk.StringVar(value="همه")
        status_combo = ttk.Combobox(
            filter_frame, textvariable=self.status_var,
            values=["همه", "در انتظار", "در حال انجام", "تکمیل شده", "تایید شده", "رد شده"],
            state="readonly", width=15, font=("Tahoma", 10)
        )
        status_combo.pack(side="right", padx=5)
        status_combo.bind("<<ComboboxSelected>>", lambda e: self._load())

        # Table Frame
        table_container = tk.Frame(self, bg="#FFFFFF", highlightbackground="#DADCE0", highlightthickness=1)
        table_container.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("id", "title", "equipment", "operator", "failure_time", "technician", "status", "start", "end")
        self.tree = ttk.Treeview(table_container, columns=cols, show="headings", height=18)

        self.tree.heading("id", text="شناسه")
        self.tree.heading("title", text="عنوان")
        self.tree.heading("equipment", text="تجهیز")
        self.tree.heading("operator", text="اپراتور تحویل گیرنده")
        self.tree.heading("failure_time", text="ساعت اعلام خرابی")
        self.tree.heading("technician", text="تکنسین")
        self.tree.heading("status", text="وضعیت")
        self.tree.heading("start", text="شروع تعمیر")
        self.tree.heading("end", text="پایان تعمیر")

        self.tree.column("id", width=60, anchor="center")
        self.tree.column("title", width=180, anchor="w")
        self.tree.column("equipment", width=140, anchor="w")
        self.tree.column("operator", width=130, anchor="center")
        self.tree.column("failure_time", width=120, anchor="center")
        self.tree.column("technician", width=120, anchor="center")
        self.tree.column("status", width=100, anchor="center")
        self.tree.column("start", width=130, anchor="center")
        self.tree.column("end", width=130, anchor="center")

        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="right", fill="both", expand=True)
        scrollbar.pack(side="left", fill="y")

        # Context Menu
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="▶️ شروع کار", command=self._start_work)
        self.context_menu.add_command(label="✅ تکمیل کار", command=self._complete_work)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="👍 تایید", command=self._approve_work)
        self.context_menu.add_command(label="👎 رد", command=self._reject_work)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🗑️ حذف", command=self._delete_work)

    def _load(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        status_fa = self.status_var.get()
        status_filter = None
        if status_fa != "همه":
            status_map = {
                "در انتظار": WorkOrderStatus.PENDING,
                "در حال انجام": WorkOrderStatus.IN_PROGRESS,
                "تکمیل شده": WorkOrderStatus.COMPLETED,
                "تایید شده": WorkOrderStatus.APPROVED,
                "رد شده": WorkOrderStatus.REJECTED
            }
            status_filter = status_map.get(status_fa)

        work_orders = self.wo_repo.get_all(status_filter=status_filter)

        for wo in work_orders:
            eq_name = wo.equipment.name if wo.equipment else "-"
            tech_name = wo.technician.full_name if wo.technician else "-"
            operator_name = wo.operator.full_name if wo.operator else "-"
            failure_time_str = wo.failure_report_time.strftime("%Y-%m-%d %H:%M") if wo.failure_report_time else "-"

            status_fa = {
                "PENDING": "در انتظار",
                "IN_PROGRESS": "در حال انجام",
                "COMPLETED": "تکمیل شده",
                "APPROVED": "تایید شده",
                "REJECTED": "رد شده"
            }.get(wo.status.name, wo.status.name)

            start_str = wo.start_time.strftime("%Y-%m-%d %H:%M") if wo.start_time else "-"
            end_str = wo.end_time.strftime("%Y-%m-%d %H:%M") if wo.end_time else "-"

            self.tree.insert("", "end", values=(
                wo.id, wo.title, eq_name, operator_name, failure_time_str,
                tech_name, status_fa, start_str, end_str
            ))

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("هشدار", "لطفاً یک کار انتخاب کنید.")
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def _emergency_work(self):
        dlg = EmergencyWorkOrderDialog(self, equipment_repo=None, preselected_equipment=None)
        self.wait_window(dlg)
        if dlg.result:
            self._load()

    def _export(self):
        selected_id = None
        sel = self.tree.selection()
        if sel:
            selected_id = int(self.tree.item(sel[0])["values"][0])
        run_work_order_export(self, self.wo_repo, selected_wo_id=selected_id)

    def _add_work(self):
        dlg = WorkOrderDialog(self, self.wo_repo)
        self.wait_window(dlg)
        if dlg.result:
            self._load()

    def _start_work(self):
        wid = self._selected_id()
        if wid:
            ok, msg = self.wo_repo.start_work(wid)
            if ok:
                messagebox.showinfo("موفق", msg)
                self._load()
            else:
                messagebox.showerror("خطا", msg)

    def _complete_work(self):
        wid = self._selected_id()
        if not wid:
            return
        dlg = PartsSelectionDialog(self, self.wo_repo, wid)   # restored
        self.wait_window(dlg)
        if dlg.result:
            self._load()

    def _approve_work(self):
        wid = self._selected_id()
        if wid and self.current_user["role"] in ["admin", "manager"]:
            ok, msg = self.wo_repo.approve(wid, self.current_user["id"])
            if ok:
                messagebox.showinfo("موفق", msg)
                self._load()
            else:
                messagebox.showerror("خطا", msg)
        elif wid:
            messagebox.showwarning("دسترسی", "فقط مدیران می‌توانند کار را تایید کنند.")

    def _reject_work(self):
        wid = self._selected_id()
        if wid and self.current_user["role"] in ["admin", "manager"]:
            notes = simpledialog.askstring("دلیل رد", "دلیل رد کار را وارد کنید:")
            if notes:
                ok, msg = self.wo_repo.reject(wid, self.current_user["id"], notes)
                if ok:
                    messagebox.showinfo("موفق", msg)
                    self._load()
                else:
                    messagebox.showerror("خطا", msg)
        elif wid:
            messagebox.showwarning("دسترسی", "فقط مدیران می‌توانند کار را رد کنند.")

    def _delete_work(self):
        wid = self._selected_id()
        if wid and messagebox.askyesno("حذف", "آیا از حذف این کار مطمئن هستید؟"):
            ok, msg = self.wo_repo.delete(wid)
            if ok:
                messagebox.showinfo("موفق", msg)
                self._load()
            else:
                messagebox.showerror("خطا", msg)

    def _show_context_menu(self, event):
        try:
            self.tree.selection_set(self.tree.identify_row(event.y))
            self.context_menu.post(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()