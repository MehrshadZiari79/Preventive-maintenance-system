# views/work_order_view.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
import json
from tkcalendar import DateEntry
from database.db import SessionLocal
from database.work_order import WorkOrderStatus, WorkOrder
from database.work_order_repository import WorkOrderRepository
from database.spare_parts_repository import SparePartsRepository
from database.equipment_repository import EquipmentRepository
from views.work_order_dialog import WorkOrderDialog
from views.export_dialog import run_work_order_export
from views.emergency_work_order_dialog import EmergencyWorkOrderDialog
from views.parts_selection_dialog import PartsSelectionDialog

from utils.theme import (
    NAVY,
    NAVY_LIGHT,
    WHITE,
    RED,
    GRAY_BG,
    GRAY_BORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    SUCCESS,
    WARNING,
    FONT_TITLE,
    FONT_HEADING,
    FONT_NORMAL,
    FONT_SMALL,
)

# =============================================================================
# THEME
# =============================================================================

BG = "#F4F7FB"
CARD = WHITE
PRIMARY = NAVY
PRIMARY_LIGHT = NAVY_LIGHT
ACCENT = RED

TABLE_BG = WHITE
TABLE_HEADER = NAVY
TABLE_SELECTED = "#D9E8FF"

ROW_ODD = "#FFFFFF"
ROW_EVEN = "#F7F9FC"

SUCCESS_BG = "#E8F5E9"
WARNING_BG = "#FFF8E1"
DANGER_BG = "#FDECEC"
INFO_BG = "#EAF2FF"

PRIORITY_FA = {"low": "کم", "medium": "متوسط", "high": "بالا", "urgent": "فوری"}
TYPE_FA = {"CORRECTIVE": "CM", "PREVENTIVE": "PM", "EMERGENCY": "EM", "PM": "PM", "INSPECTION": "بازرسی"}

STATUS_MAP = {
    WorkOrderStatus.PENDING_APPROVAL: "در انتظار تأیید",
    WorkOrderStatus.PENDING: "در انتظار",
    WorkOrderStatus.IN_PROGRESS: "در حال انجام",
    WorkOrderStatus.FINISH_REQUESTED: "درخواست اتمام",
    WorkOrderStatus.APPROVED: "تایید شده",
    WorkOrderStatus.REJECTED: "رد شده"
}


class PickDateTimeDialog(tk.Toplevel):
    def __init__(self, parent, title="انتخاب تاریخ و ساعت", default_dt=None):
        super().__init__(parent)

        self.result = None
        self.configure(bg=BG)
        self.title(title)
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        if default_dt is None:
            default_dt = datetime.now()

        self.default_dt = default_dt

        self._build_ui()
        self._center(430, 300)

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):

        container = tk.Frame(
            self,
            bg=CARD,
            bd=1,
            relief="solid",
            highlightbackground=GRAY_BORDER,
            highlightthickness=1
        )
        container.pack(fill="both", expand=True, padx=15, pady=15)

        header = tk.Frame(container, bg=PRIMARY, height=55)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="⏰ انتخاب تاریخ و ساعت",
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE
        ).pack(side="right", padx=18)

        body = tk.Frame(container, bg=CARD)
        body.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(
            body,
            text="تاریخ:",
            font=FONT_NORMAL,
            bg=CARD,
            fg=TEXT_DARK
        ).grid(row=0, column=1, sticky="e", pady=10)

        self.date_entry = DateEntry(
            body,
            width=16,
            date_pattern='yyyy-mm-dd',
            font=FONT_NORMAL,
            background=PRIMARY,
            foreground=WHITE,
            headersbackground=PRIMARY,
            headersforeground=WHITE,
            borderwidth=1
        )

        self.date_entry.set_date(self.default_dt.date())
        self.date_entry.grid(row=0, column=0, sticky="w", padx=5)

        tk.Label(
            body,
            text="ساعت (HH:MM):",
            font=FONT_NORMAL,
            bg=CARD,
            fg=TEXT_DARK
        ).grid(row=1, column=1, sticky="e", pady=10)

        self.time_var = tk.StringVar(value=self.default_dt.strftime("%H:%M"))

        tk.Entry(
            body,
            textvariable=self.time_var,
            font=FONT_NORMAL,
            width=14,
            relief="solid",
            bd=1,
            bg=WHITE,
            fg=TEXT_DARK,
            insertbackground=TEXT_DARK
        ).grid(row=1, column=0, sticky="w", padx=5)

        footer = tk.Frame(body, bg=CARD)
        footer.grid(row=2, column=0, columnspan=2, pady=(20, 0))

        tk.Button(
            footer,
            text="تأیید",
            command=self._confirm,
            bg=SUCCESS,
            fg=WHITE,
            activebackground=SUCCESS,
            activeforeground=WHITE,
            relief="flat",
            cursor="hand2",
            font=FONT_NORMAL,
            padx=20,
            pady=7
        ).pack(side="right", padx=5)

        tk.Button(
            footer,
            text="انصراف",
            command=self.destroy,
            bg="#DADFE8",
            fg=TEXT_DARK,
            relief="flat",
            cursor="hand2",
            font=FONT_NORMAL,
            padx=20,
            pady=7
        ).pack(side="right", padx=5)

    def _confirm(self):
        try:
            greg_date = self.date_entry.get_date()

            time_str = self.time_var.get().strip()

            if not time_str:
                time_str = "00:00"

            hour, minute = map(int, time_str.split(":"))

            dt = datetime(
                greg_date.year,
                greg_date.month,
                greg_date.day,
                hour,
                minute,
                0
            )

            self.result = dt
            self.destroy()

        except Exception as e:
            messagebox.showerror(
                "خطا",
                f"تاریخ یا ساعت نامعتبر است:\n{e}",
                parent=self
            )


# =============================================================================
# WORK ORDER VIEW
# =============================================================================

class WorkOrderView(tk.Frame):

    def __init__(self, parent, work_order_repo, current_user):

        super().__init__(parent, bg=BG)

        self.current_user = current_user
        self.wo_repo = work_order_repo

        self.sp_repo = SparePartsRepository(SessionLocal)
        self.eq_repo = EquipmentRepository(SessionLocal)

        self.is_admin = current_user["role"] == "admin"
        self.is_manager = current_user["role"] in ["admin", "manager"]
        self.is_production_expert = current_user["role"] == "production_expert"
        self.is_technician = current_user["role"] == "technician"

        self._build_ui()
        self._load()

    # =========================================================================
    # UI
    # =========================================================================

    def _build_ui(self):

        # ================= HEADER =================

        header = tk.Frame(self, bg=PRIMARY, height=75)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_frame = tk.Frame(header, bg=PRIMARY)
        title_frame.pack(side="right", padx=20)

        tk.Label(
            title_frame,
            text="📝 مدیریت دستور کارها",
            font=FONT_TITLE,
            bg=PRIMARY,
            fg=WHITE
        ).pack(anchor="e")

        tk.Label(
            title_frame,
            text="مدیریت کامل دستور کار ها ",
            font=FONT_SMALL,
            bg=PRIMARY,
            fg="#D7E3F4"
        ).pack(anchor="e")

        # ================= ACTION BUTTONS =================

        action_frame = tk.Frame(header, bg=PRIMARY)
        action_frame.pack(side="left", padx=15)

        def make_btn(text, command, bg, fg=WHITE):
            return tk.Button(
                action_frame,
                text=text,
                command=command,
                bg=bg,
                fg=fg,
                activebackground=bg,
                activeforeground=fg,
                relief="flat",
                cursor="hand2",
                font=FONT_SMALL,
                padx=14,
                pady=7,
                bd=0
            )

        if self.is_manager or self.is_production_expert or self.is_technician:
            make_btn(
                "➕ دستور کار",
                self._add_work,
                WHITE,
                PRIMARY
            ).pack(side="left", padx=4)

            make_btn(
                "🚨 اضطراری",
                self._emergency_work,
                RED
            ).pack(side="left", padx=4)

        if self.is_manager:
            make_btn(
                "🔄 تولید PM",
                self._generate_pm_work_orders,
                PRIMARY_LIGHT
            ).pack(side="left", padx=4)

        make_btn(
            "🔃 بروزرسانی",
            self._load,
            PRIMARY_LIGHT
        ).pack(side="left", padx=4)

        make_btn(
            "📤 خروجی Excel",
            self._export,
            SUCCESS
        ).pack(side="left", padx=4)

        # ================= FILTER CARD =================

        filter_card = tk.Frame(
            self,
            bg=CARD,
            bd=1,
            relief="solid",
            highlightbackground=GRAY_BORDER,
            highlightthickness=1
        )

        filter_card.pack(fill="x", padx=20, pady=15)

        filter_inner = tk.Frame(filter_card, bg=CARD)
        filter_inner.pack(fill="x", padx=15, pady=15)

        # Status filter

        tk.Label(
            filter_inner,
            text="وضعیت:",
            bg=CARD,
            fg=TEXT_DARK,
            font=FONT_NORMAL
        ).pack(side="right", padx=(0, 8))

        self.status_var = tk.StringVar(value="همه")

        status_combo = ttk.Combobox(
            filter_inner,
            textvariable=self.status_var,
            values=[
                "همه",
                "در انتظار تأیید",
                "در انتظار",
                "در حال انجام",
                "درخواست اتمام",
                "تایید شده(تکمیل)",
                "رد شده"
            ],
            state="readonly",
            width=20,
            font=FONT_NORMAL
        )

        status_combo.pack(side="right", padx=(0, 15))
        status_combo.bind("<<ComboboxSelected>>", lambda e: self._load())

        # Equipment category filter

        tk.Label(filter_inner, text="دسته تجهیز:", bg=CARD, fg=TEXT_DARK, font=FONT_NORMAL).pack(side="right", padx=(0,8))
        self.category_var = tk.StringVar(value="همه")
        self.category_combo = ttk.Combobox(filter_inner, textvariable=self.category_var, state="readonly",
                                           width=16, font=FONT_NORMAL)
        self.category_combo.pack(side="right", padx=(0,15))
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self._load())
        self._load_categories()

        # Dates

        tk.Label(
            filter_inner,
            text="از تاریخ:",
            bg=CARD,
            fg=TEXT_DARK,
            font=FONT_SMALL
        ).pack(side="right", padx=(0, 5))

        self.start_date = DateEntry(
            filter_inner,
            width=12,
            date_pattern='yyyy-mm-dd',
            background=PRIMARY,
            foreground=WHITE,
            headersbackground=PRIMARY,
            headersforeground=WHITE
        )

        self.start_date.pack(side="right", padx=(0, 10))
        self.start_date.set_date(datetime.now() - timedelta(days=30))

        tk.Label(
            filter_inner,
            text="تا تاریخ:",
            bg=CARD,
            fg=TEXT_DARK,
            font=FONT_SMALL
        ).pack(side="right", padx=(0, 5))

        self.end_date = DateEntry(
            filter_inner,
            width=12,
            date_pattern='yyyy-mm-dd',
            background=PRIMARY,
            foreground=WHITE,
            headersbackground=PRIMARY,
            headersforeground=WHITE
        )

        self.end_date.pack(side="right", padx=(0, 10))
        self.end_date.set_date(datetime.now())

        tk.Button(
            filter_inner,
            text="اعمال فیلتر",
            command=self._load,
            bg=PRIMARY,
            fg=WHITE,
            activebackground=PRIMARY,
            activeforeground=WHITE,
            relief="flat",
            cursor="hand2",
            font=FONT_SMALL,
            padx=12,
            pady=5
        ).pack(side="right")

        # ================= TABLE CARD =================

        table_card = tk.Frame(
            self,
            bg=CARD,
            bd=1,
            relief="solid",
            highlightbackground=GRAY_BORDER,
            highlightthickness=1
        )

        table_card.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # ================= TREE STYLE =================

        style = ttk.Style()

        style.theme_use("default")

        style.configure(
            "Modern.Treeview",
            background=TABLE_BG,
            foreground=TEXT_DARK,
            fieldbackground=TABLE_BG,
            rowheight=38,
            borderwidth=0,
            font=FONT_SMALL
        )

        style.configure(
            "Modern.Treeview.Heading",
            background=TABLE_HEADER,
            foreground=WHITE,
            relief="flat",
            borderwidth=0,
            font=FONT_SMALL
        )

        style.map(
            "Modern.Treeview",
            background=[("selected", TABLE_SELECTED)],
            foreground=[("selected", TEXT_DARK)]
        )

        # ================= TABLE =================

        columns = (
            "id",
            "title",
            "type",
            "equipment",
            "priority",
            "operator",
            "failure_time",
            "technician",
            "status",
            "start",
            "end",
            "deadline",
            "total_cost",
            "parent_id"
        )

        self.tree = ttk.Treeview(
            table_card,
            columns=columns,
            show="headings",
            style="Modern.Treeview"
        )

        headers = [
            ("id", "شناسه", 70, "center"),
            ("title", "عنوان دستور کار", 220, "w"),
            ("type", "نوع", 90, "center"),
            ("equipment", "تجهیز", 170, "w"),
            ("priority", "اولویت", 90, "center"),
            ("operator", "اپراتور", 130, "center"),
            ("failure_time", "اعلام خرابی", 150, "center"),
            ("technician", "تکنسین‌ها", 180, "w"),
            ("status", "وضعیت", 130, "center"),
            ("start", "شروع", 150, "center"),
            ("end", "اتمام", 150, "center"),
            ("deadline", "ددلاین", 150, "center"),
            ("total_cost", "هزینه", 150, "center"),
            ("parent_id", "والد", 80, "center"),
        ]

        for col, text, width, anchor in headers:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor)

        # Scrollbars

        vsb = ttk.Scrollbar(
            table_card,
            orient="vertical",
            command=self.tree.yview
        )

        hsb = ttk.Scrollbar(
            table_card,
            orient="horizontal",
            command=self.tree.xview
        )

        self.tree.configure(
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        table_card.grid_rowconfigure(0, weight=1)
        table_card.grid_columnconfigure(0, weight=1)

        # ================= TAG COLORS =================

        self.tree.tag_configure(
            "PENDING_APPROVAL",
            background=WARNING_BG
        )

        self.tree.tag_configure(
            "PENDING",
            background=INFO_BG
        )

        self.tree.tag_configure(
            "IN_PROGRESS",
            background="#FFF1E6"
        )

        self.tree.tag_configure(
            "FINISH_REQUESTED",
            background="#FFECEC"
        )

        self.tree.tag_configure(
            "APPROVED",
            background=SUCCESS_BG
        )

        self.tree.tag_configure(
            "REJECTED",
            background=DANGER_BG
        )

        # ================= SHORTCUTS =================

        self.tree.configure(selectmode="extended")

        self.tree.bind("<Delete>", lambda e: self._delete_selected())
        self.tree.bind("<F2>", lambda e: self._edit_selected())
        self.tree.bind("<Control-n>", lambda e: self._add_work())

        # ================= CONTEXT MENU =================

        self.context_menu = tk.Menu(
            self,
            tearoff=0,
            font=FONT_NORMAL,
            bg=WHITE,
            fg=TEXT_DARK,
            activebackground=PRIMARY,
            activeforeground=WHITE
        )

        self.context_menu.add_command(
            label="▶️ شروع کار",
            command=self._start_work
        )

        self.context_menu.add_command(
            label="📤 ارسال گزارش اتمام",
            command=self._request_finish
        )

        if self.is_manager:   # only managers see approval/rejection
            self.context_menu.add_separator()

            self.context_menu.add_command(
                label="👍 تایید ایجاد دستور کار",
                command=self._approve_creation
            )

            self.context_menu.add_command(
                label="✅ تایید نهایی",
                command=self._approve_work
            )

            self.context_menu.add_command(
                label="❌ رد اتمام",
                command=self._reject_finish
            )

            self.context_menu.add_separator()

            self.context_menu.add_command(
                label="✏️ ویرایش",
                command=self._edit_work
            )

            if self.is_admin:
                self.context_menu.add_command(
                    label="🗑️ حذف",
                    command=self._delete_work
                )

        self.tree.bind("<Button-3>", self._show_context_menu)

    def _load_categories(self):
        cats = ["همه"] + self.eq_repo.get_categories()
        self.category_combo['values'] = cats
        self.category_combo.current(0)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _selected_id(self):

        sel = self.tree.selection()

        if not sel:
            messagebox.showwarning(
                "هشدار",
                "لطفاً یک دستور کار انتخاب کنید."
            )
            return None

        return int(self.tree.item(sel[0])["values"][0])

    def _calculate_total_cost(self, wo):

        total = 0.0

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

        if wo.start_time and wo.end_time:

            total += (
                (wo.end_time - wo.start_time).total_seconds() / 3600
            ) * 50

        total += float(wo.manual_cost or 0)

        return total

    # =========================================================================
    # LOAD DATA
    # =========================================================================

    def _load(self):

        if self.is_manager:

            try:
                from services.pm_service import PMService

                service = PMService(SessionLocal)
                service.generate_due_work_orders(days_ahead=1)

            except Exception as e:
                print(f"Auto PM generation failed: {e}")

        for item in self.tree.get_children():
            self.tree.delete(item)

        status_fa = self.status_var.get()

        mapping = {
            "در انتظار تأیید": WorkOrderStatus.PENDING_APPROVAL,
            "در انتظار": WorkOrderStatus.PENDING,
            "در حال انجام": WorkOrderStatus.IN_PROGRESS,
            "درخواست اتمام": WorkOrderStatus.FINISH_REQUESTED,
            "تایید شده(تکمیل)": WorkOrderStatus.APPROVED,
            "رد شده": WorkOrderStatus.REJECTED,
        }

        status_filter = mapping.get(status_fa)

        start = self.start_date.get_date()
        end = self.end_date.get_date()

        work_orders = self.wo_repo.get_all(status_filter=status_filter)

        # Apply category filter
        cat_filter = self.category_var.get()
        if cat_filter != "همه":
            work_orders = [wo for wo in work_orders if wo.equipment.category == cat_filter]

        filtered = []

        for wo in work_orders:

            if start and wo.created_at.date() < start:
                continue

            if end and wo.created_at.date() > end:
                continue

            filtered.append(wo)

        work_orders = filtered

        if self.is_technician:

            technician_filtered = []

            for wo in work_orders:

                if wo.status in [
                    WorkOrderStatus.PENDING,
                    WorkOrderStatus.IN_PROGRESS,
                    WorkOrderStatus.FINISH_REQUESTED
                ]:

                    if (
                        wo.technician_id is None or
                        wo.technician_id == self.current_user["id"]
                    ):
                        technician_filtered.append(wo)

            work_orders = technician_filtered

        type_fa = {
            "CORRECTIVE": "CM",
            "PREVENTIVE": "PM",
            "EMERGENCY": "EM",
            "PM": "PM",
            "INSPECTION": "بازرسی"
        }

        status_map = {
            WorkOrderStatus.PENDING_APPROVAL: "در انتظار تأیید",
            WorkOrderStatus.PENDING: "در انتظار",
            WorkOrderStatus.IN_PROGRESS: "در حال انجام",
            WorkOrderStatus.FINISH_REQUESTED: "درخواست اتمام",
            WorkOrderStatus.APPROVED: "تایید شده",
            WorkOrderStatus.REJECTED: "رد شده"
        }

        PRIORITY_FA = {"low": "کم", "medium": "متوسط", "high": "بالا", "urgent": "فوری"}

        for index, wo in enumerate(work_orders):

            eq_name = wo.equipment.name if wo.equipment else "-"
            tech_name = wo.technician.full_name if wo.technician else "-"
            # Build list of additional technicians from relationship
            additional = [t.full_name for t in wo.technicians if t.id != wo.technician_id]
            all_techs = [tech_name] + additional
            tech_display = ", ".join([n for n in all_techs if n and n != "-"])
            if not tech_display:
                tech_display = "-"
            operator_name = wo.operator.full_name if wo.operator else "-"

            priority_fa = PRIORITY_FA.get(wo.priority.name, wo.priority.name)

            failure_time_str = (
                wo.failure_report_time.strftime("%Y-%m-%d %H:%M")
                if wo.failure_report_time else "-"
            )

            start_str = (
                wo.start_time.strftime("%Y-%m-%d %H:%M")
                if wo.start_time else "-"
            )

            end_str = (
                wo.end_time.strftime("%Y-%m-%d %H:%M")
                if wo.end_time else "-"
            )

            deadline_str = (
                wo.deadline.strftime("%Y-%m-%d %H:%M")
                if wo.deadline else "-"
            )

            status_text = status_map.get(wo.status, wo.status.name)

            type_display = type_fa.get(
                wo.type.name,
                wo.type.name
            )

            total_cost = self._calculate_total_cost(wo)

            parent_id = wo.root_parent_id if wo.root_parent_id else ""

            tag = wo.status.name

            self.tree.insert(
                "",
                "end",
                values=(
                    wo.id,
                    wo.title,
                    type_display,
                    eq_name,
                    priority_fa,
                    operator_name,
                    failure_time_str,
                    tech_display,
                    status_text,
                    start_str,
                    end_str,
                    deadline_str,
                    f"{total_cost:,.0f}",
                    parent_id
                ),
                tags=(tag,)
            )

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def _add_work(self):

        if not (self.is_manager or self.is_production_expert or self.is_technician):
            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به ایجاد دستور کار نیستید."
            )
            return

        dlg = WorkOrderDialog(self, self.wo_repo)

        self.wait_window(dlg)

        if dlg.result:
            self._load()

    def _edit_work(self):

        if not (self.is_manager or self.is_production_expert or self.is_technician):
            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به ویرایش دستور کار نیستید."
            )
            return

        wo_id = self._selected_id()

        if not wo_id:
            return

        wo = self.wo_repo.get_by_id(wo_id)

        if not wo:
            return

        dlg = WorkOrderDialog(
            self,
            self.wo_repo,
            work_order=wo
        )

        self.wait_window(dlg)

        if dlg.result:
            self._load()

    def _delete_work(self):

        if not self.is_admin:
            messagebox.showwarning(
                "دسترسی",
                "فقط مدیر سیستم می‌تواند حذف کند."
            )
            return

        wid = self._selected_id()

        if wid and messagebox.askyesno(
            "حذف",
            "آیا از حذف این دستور کار مطمئن هستید؟"
        ):

            ok, msg = self.wo_repo.delete(wid)

            if ok:
                messagebox.showinfo("موفق", msg)
                self._load()
            else:
                messagebox.showerror("خطا", msg)

    def _delete_selected(self):

        if not self.is_admin:
            messagebox.showwarning(
                "دسترسی",
                "فقط مدیر سیستم می‌تواند حذف کند."
            )
            return

        selected = self.tree.selection()

        if not selected:
            return

        ids_to_delete = []

        for item in selected:

            values = self.tree.item(item, "values")

            if values:
                ids_to_delete.append(int(values[0]))

        if not ids_to_delete:
            return

        if not messagebox.askyesno(
            "حذف",
            f"حذف {len(ids_to_delete)} مورد انجام شود؟"
        ):
            return

        for wid in ids_to_delete:
            self.wo_repo.delete(wid)

        self._load()

    def _edit_selected(self):
        self._edit_work()

    def _export(self):

        selected_id = None

        sel = self.tree.selection()

        if sel:
            selected_id = int(self.tree.item(sel[0])["values"][0])

        run_work_order_export(
            self,
            self.wo_repo,
            selected_wo_id=selected_id
        )

    def _emergency_work(self):

        dlg = EmergencyWorkOrderDialog(
            self,
            equipment_repo=None,
            preselected_equipment=None
        )

        self.wait_window(dlg)

        if dlg.result:
            self._load()

    def _start_work(self):

        wo_id = self._selected_id()

        if not wo_id:
            return

        wo = self.wo_repo.get_by_id(wo_id)

        if wo.status != WorkOrderStatus.PENDING:
            messagebox.showwarning(
                "خطا",
                "فقط کارهای در انتظار قابل شروع هستند."
            )
            return

        dlg = PickDateTimeDialog(
            self,
            title="انتخاب زمان شروع کار"
        )

        self.wait_window(dlg)

        if not dlg.result:
            return

        start_dt = dlg.result

        session = SessionLocal()

        try:

            wo_obj = session.query(WorkOrder).filter_by(id=wo_id).first()

            if wo_obj:

                wo_obj.start_time = start_dt
                wo_obj.status = WorkOrderStatus.IN_PROGRESS

                session.commit()

                messagebox.showinfo(
                    "موفق",
                    "شروع کار ثبت شد."
                )

                self._load()

        except Exception as e:

            session.rollback()

            messagebox.showerror(
                "خطا",
                str(e)
            )

        finally:
            session.close()

    def _request_finish(self):

        wo_id = self._selected_id()

        if not wo_id:
            return

        wo = self.wo_repo.get_by_id(wo_id)

        if wo.status != WorkOrderStatus.IN_PROGRESS:
            messagebox.showwarning(
                "خطا",
                "فقط کارهای در حال انجام قابل ارسال هستند."
            )
            return

        # 1. Pick completion time
        time_dlg = PickDateTimeDialog(self, title="انتخاب زمان اتمام کار")
        self.wait_window(time_dlg)
        if not time_dlg.result:
            return
        end_time = time_dlg.result

        # 2. Open parts selection dialog (may already submit the finish request)
        dlg = PartsSelectionDialog(
            self,
            self.wo_repo,
            wo_id
        )

        self.wait_window(dlg)

        # 3. Re‑fetch the work order to see if the dialog already changed status
        wo_after = self.wo_repo.get_by_id(wo_id)
        if wo_after.status == WorkOrderStatus.FINISH_REQUESTED:
            # Already submitted – just reload
            messagebox.showinfo("موفق", "درخواست اتمام کار با موفقیت ارسال شد.")
            self._load()
            return

        # 4. Otherwise, submit with the collected data
        if not dlg.result:
            return

        ok, msg = self.wo_repo.request_finish(
            wo_id,
            end_time=end_time,
            used_parts_list=dlg.used_parts if hasattr(dlg, 'used_parts') else None,
            manual_cost=dlg.manual_cost if hasattr(dlg, 'manual_cost') else None,
            cost_description=dlg.cost_description if hasattr(dlg, 'cost_description') else None,
            technician_notes=dlg.technician_notes if hasattr(dlg, 'technician_notes') else None
        )

        if ok:
            messagebox.showinfo("موفق", msg)
            self._load()
        else:
            messagebox.showerror("خطا", msg)

    def _approve_creation(self):

        if not (self.is_manager or self.is_production_expert):
            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به تأیید ایجاد نیستید."
            )
            return

        wo_id = self._selected_id()

        if not wo_id:
            return

        ok, msg = self.wo_repo.approve_creation(
            wo_id,
            self.current_user["id"]
        )

        if ok:
            messagebox.showinfo("موفق", msg)
            self._load()
        else:
            messagebox.showerror("خطا", msg)

    def _approve_work(self):

        if not self.is_manager:
            messagebox.showwarning(
                "دسترسی",
                "فقط مدیران مجاز به تأیید نهایی هستند."
            )
            return

        wo_id = self._selected_id()

        if not wo_id:
            return

        wo = self.wo_repo.get_by_id(wo_id)

        if wo.status != WorkOrderStatus.FINISH_REQUESTED:
            messagebox.showwarning(
                "خطا",
                "فقط کارهای درخواست اتمام قابل تأیید هستند."
            )
            return

        if not messagebox.askyesno(
            "تأیید نهایی",
            "آیا از تأیید این کار اطمینان دارید؟"
        ):
            return

        ok, msg = self.wo_repo.approve(
            wo_id,
            self.current_user["id"]
        )

        if ok:
            messagebox.showinfo("موفق", msg)
            self._load()
        else:
            messagebox.showerror("خطا", msg)

    def _reject_finish(self):

        if not self.is_manager:
            messagebox.showwarning(
                "دسترسی",
                "فقط مدیران مجاز به رد درخواست هستند."
            )
            return

        wo_id = self._selected_id()

        if not wo_id:
            return

        notes = simpledialog.askstring(
            "دلیل رد",
            "دلیل رد درخواست را وارد کنید:"
        )

        if notes is None:
            return

        ok, msg = self.wo_repo.reject_finish(
            wo_id,
            self.current_user["id"],
            notes
        )

        if ok:
            messagebox.showinfo("موفق", msg)
            self._load()
        else:
            messagebox.showerror("خطا", msg)

    def _show_context_menu(self, event):

        try:

            row_id = self.tree.identify_row(event.y)

            if row_id:
                self.tree.selection_set(row_id)
                self.context_menu.post(event.x_root, event.y_root)

        finally:
            self.context_menu.grab_release()

    def _generate_pm_work_orders(self):

        if not self.is_manager:
            messagebox.showwarning(
                "دسترسی",
                "فقط مدیران می‌توانند PM تولید کنند."
            )
            return

        from services.pm_service import PMService

        service = PMService(SessionLocal)

        created, skipped, errors = service.generate_due_work_orders(
            days_ahead=1
        )

        msg = f"✅ {created} دستور کار ایجاد شد.\n"

        if skipped:
            msg += f"⏭️ {skipped} مورد تکراری بود.\n"

        if errors:
            msg += "\n".join(errors[:5])

        messagebox.showinfo(
            "نتیجه تولید PM",
            msg
        )

        self._load()
# ── NEW: work order detail dialog ─────────────────────────────
    def _show_work_order_detail(self):
        wo_id = self._selected_id()
        if not wo_id:
            return
        wo = self.wo_repo.get_by_id(wo_id)
        if not wo:
            messagebox.showerror("خطا", "دستور کار یافت نشد")
            return

        detail = tk.Toplevel(self)
        detail.title(f"دستور کار #{wo.id}")
        detail.geometry("750x660")
        detail.configure(bg=BG)
        detail.transient(self)
        detail.grab_set()

        hdr = tk.Frame(detail, bg=PRIMARY, height=52)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"📝  WO#{wo.id} — {wo.title}", font=FONT_HEADING, bg=PRIMARY, fg=WHITE).pack(side=tk.RIGHT, padx=20, pady=12)

        canvas = tk.Canvas(detail, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(detail, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=BG)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def add_row(parent, text, value, row):
            tk.Label(parent, text=text, font=("Tahoma", 9, "bold"), bg=CARD, fg=TEXT_LIGHT).grid(row=row, column=0, sticky="ne", padx=10, pady=5)
            tk.Label(parent, text=str(value), font=FONT_NORMAL, bg=CARD, fg=TEXT_DARK, wraplength=500, justify="right").grid(row=row, column=1, sticky="nw", padx=10, pady=5)
            return row + 1

        info_card = tk.Frame(scrollable, bg=CARD, bd=1, relief="solid",
                             highlightbackground=GRAY_BORDER, highlightthickness=1)
        info_card.pack(fill="x", padx=10, pady=10)
        grid = tk.Frame(info_card, bg=CARD)
        grid.pack(fill=tk.X, padx=10, pady=8)

        r = 0
        r = add_row(grid, "شناسه:", wo.id, r)
        r = add_row(grid, "عنوان:", wo.title or "—", r)
        r = add_row(grid, "تجهیز:", wo.equipment.name if wo.equipment else "—", r)
        r = add_row(grid, "نوع:", TYPE_FA.get(wo.type.name, wo.type.name), r)
        r = add_row(grid, "اولویت:", PRIORITY_FA.get(wo.priority.name, wo.priority.name), r)
        r = add_row(grid, "وضعیت:", STATUS_MAP.get(wo.status, wo.status.name), r)
        r = add_row(grid, "تاریخ برنامه:", wo.scheduled_date.strftime("%Y-%m-%d") if wo.scheduled_date else "—", r)
        r = add_row(grid, "شروع:", wo.start_time.strftime("%Y-%m-%d %H:%M") if wo.start_time else "—", r)
        r = add_row(grid, "پایان:", wo.end_time.strftime("%Y-%m-%d %H:%M") if wo.end_time else "—", r)
        r = add_row(grid, "تکنسین:", wo.technician.full_name if wo.technician else "—", r)
        r = add_row(grid, "اپراتور:", wo.operator.full_name if wo.operator else "—", r)
        r = add_row(grid, "ددلاین:", wo.deadline.strftime("%Y-%m-%d %H:%M") if wo.deadline else "—", r)
        r = add_row(grid, "هزینه دستی (ریال):", f"{wo.manual_cost:,.0f}" if wo.manual_cost else "0", r)
        r = add_row(grid, "توضیح هزینه:", wo.cost_description or "—", r)
        r = add_row(grid, "یادداشت اپراتور:", wo.operator_notes or "—", r)
        r = add_row(grid, "توضیحات تکنسین:", wo.description or "—", r)
        r = add_row(grid, "قطعات مصرفی:", wo.parts_used or "—", r)
        r = add_row(grid, "تأخیر (دقیقه):", str(wo.delay_minutes) if wo.delay_minutes else "—", r)
        r = add_row(grid, "علت تأخیر:", wo.delay_reason or "—", r)

        tk.Button(detail, text="✕  بستن", font=FONT_NORMAL, bg=ACCENT, fg=WHITE, relief="flat", cursor="hand2", padx=20, pady=8, command=detail.destroy).pack(pady=10)

    def handle_enter(self):
        """Called when Enter is pressed while this view is active."""
        self._show_work_order_detail()