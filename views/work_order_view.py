# views/work_order_view.py
"""
Work Order View - Main Work Order Management Panel
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import json
from database.work_order_repository import WorkOrderRepository
from database.work_order import WorkOrderStatus
from views.work_order_dialog import WorkOrderDialog
from views.export_dialog import run_work_order_export
from views.emergency_work_order_dialog import EmergencyWorkOrderDialog
from views.parts_selection_dialog import PartsSelectionDialog
from database.spare_parts_repository import SparePartsRepository
from database.db import SessionLocal
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)


class WorkOrderView(tk.Frame):
    def __init__(self, parent, work_order_repo, current_user):
        super().__init__(parent, bg=GRAY_BG)
        self.current_user = current_user
        self.wo_repo = work_order_repo
        self.sp_repo = SparePartsRepository(SessionLocal())
        self.is_manager = current_user["role"] in ["admin", "manager"]

        self._build_ui()
        self._load()

    def _build_ui(self):
        # Toolbar (navy header)
        toolbar = tk.Frame(self, bg=NAVY, height=60)
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)

        tk.Label(toolbar, text="📝 مدیریت دستور کارها", font=FONT_TITLE,
                 bg=NAVY, fg=WHITE).pack(side="right", padx=20)

        btn_frame = tk.Frame(toolbar, bg=NAVY)
        btn_frame.pack(side="left", padx=20)

        # These buttons are available to all (technician can create/start/complete)
        tk.Button(btn_frame, text="➕ کار جدید", command=self._add_work,
                  bg=WHITE, fg=NAVY, font=FONT_NORMAL,
                  cursor="hand2", relief="flat", padx=15, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="🚨 کار اضطراری", command=self._emergency_work,
                  bg=RED, fg=WHITE, font=FONT_NORMAL,
                  cursor="hand2", relief="flat", padx=15, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="🔄 بروزرسانی", command=self._load,
                  bg=NAVY_LIGHT, fg=WHITE, font=FONT_NORMAL,
                  cursor="hand2", relief="flat", padx=15, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="📤 Excel خروجی", command=self._export,
                  bg=SUCCESS, fg=WHITE, font=FONT_NORMAL,
                  cursor="hand2", relief="flat", padx=15, pady=8).pack(side="left", padx=5)

        # Filter Frame
        filter_frame = tk.Frame(self, bg=WHITE, height=50)
        filter_frame.pack(fill="x", padx=20, pady=(10, 0))
        filter_frame.pack_propagate(False)

        tk.Label(filter_frame, text="فیلتر وضعیت:", bg=WHITE, font=FONT_NORMAL).pack(side="right", padx=10)

        self.status_var = tk.StringVar(value="همه")
        status_combo = ttk.Combobox(
            filter_frame, textvariable=self.status_var,
            values=["همه", "در انتظار", "در حال انجام", "تکمیل شده", "تایید شده", "رد شده"],
            state="readonly", width=15, font=FONT_NORMAL
        )
        status_combo.pack(side="right", padx=5)
        status_combo.bind("<<ComboboxSelected>>", lambda e: self._load())

        # Table Frame
        table_container = tk.Frame(self, bg=WHITE, highlightbackground=GRAY_BORDER, highlightthickness=1)
        table_container.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("id", "title", "equipment", "operator", "failure_time", "technician", "status", "start", "end", "total_cost")
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
        self.tree.heading("total_cost", text="هزینه کل (ریال)")

        self.tree.column("id", width=60, anchor="center")
        self.tree.column("title", width=180, anchor="w")
        self.tree.column("equipment", width=140, anchor="w")
        self.tree.column("operator", width=130, anchor="center")
        self.tree.column("failure_time", width=120, anchor="center")
        self.tree.column("technician", width=120, anchor="center")
        self.tree.column("status", width=100, anchor="center")
        self.tree.column("start", width=130, anchor="center")
        self.tree.column("end", width=130, anchor="center")
        self.tree.column("total_cost", width=120, anchor="center")

        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="right", fill="both", expand=True)
        scrollbar.pack(side="left", fill="y")

        # Context Menu
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.context_menu = tk.Menu(self, tearoff=0, font=FONT_NORMAL)
        self.context_menu.add_command(label="▶️ شروع کار", command=self._start_work)
        self.context_menu.add_command(label="✅ تکمیل کار", command=self._complete_work)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="👍 تایید", command=self._approve_work)
        self.context_menu.add_command(label="👎 رد", command=self._reject_work)
        # Delete is only for manager/admin
        if self.is_manager:
            self.context_menu.add_separator()
            self.context_menu.add_command(label="🗑️ حذف", command=self._delete_work)

    def _calculate_total_cost(self, wo):
        """Calculate total cost = parts + labor + manual."""
        total = 0.0

        # Parts cost
        if wo.parts_used:
            try:
                parts_list = json.loads(wo.parts_used)
                for item in parts_list:
                    part_id = item.get("part_id")
                    qty = item.get("quantity", 0)
                    part = self.sp_repo.get_by_id(part_id)
                    if part:
                        total += part.unit_price * qty
            except:
                pass

        # Labor cost (hours * 50)
        if wo.start_time and wo.end_time:
            hours = (wo.end_time - wo.start_time).total_seconds() / 3600
            total += hours * 50

        # Manual cost
        total += float(wo.manual_cost or 0)

        return total

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

            status_fa_text = {
                "PENDING": "در انتظار",
                "IN_PROGRESS": "در حال انجام",
                "COMPLETED": "تکمیل شده",
                "APPROVED": "تایید شده",
                "REJECTED": "رد شده"
            }.get(wo.status.name, wo.status.name)

            start_str = wo.start_time.strftime("%Y-%m-%d %H:%M") if wo.start_time else "-"
            end_str = wo.end_time.strftime("%Y-%m-%d %H:%M") if wo.end_time else "-"

            total_cost = self._calculate_total_cost(wo)

            self.tree.insert("", "end", values=(
                wo.id, wo.title, eq_name, operator_name, failure_time_str,
                tech_name, status_fa_text, start_str, end_str,
                f"{total_cost:,.0f}"
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
        dlg = PartsSelectionDialog(self, self.wo_repo, wid)
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
        if not self.is_manager:
            messagebox.showwarning("دسترسی", "فقط مدیران می‌توانند دستور کار را حذف کنند.", parent=self)
            return
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