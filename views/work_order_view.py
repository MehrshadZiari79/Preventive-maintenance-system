# views/work_order_view.py
import tkinter as tk
from auth.auth_manager import AuthManager
from views.ui_kit import rtl_columns  # RTL (right-to-left) table columns
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
import json
import os
from database.db import SessionLocal
from database.work_order import WorkOrderStatus, WorkOrder
from database.spare_parts_repository import SparePartsRepository
from database.equipment_repository import EquipmentRepository
from database.department_repository import DepartmentRepository
from views.work_order_dialog import WorkOrderDialog
from views.export_dialog import run_work_order_export
from services.pdf_service import export_work_orders_pdf
from views.emergency_work_order_dialog import EmergencyWorkOrderDialog
from views.parts_selection_dialog import PartsSelectionDialog

# NEW imports for Jalali date picker and helpers
from views.jalali_date_entry import JalaliDateEntry
from utils.date_helpers import to_jalali_date_str, to_jalali_datetime_str

from utils.date_helpers import jalali_stamp  # Jalali file names / stamps
from utils.theme import (
    NAVY,
    NAVY_LIGHT,
    WHITE,
    RED,
    GRAY_BORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    SUCCESS,
    FONT_TITLE,
    FONT_HEADING,
    FONT_NORMAL,
    FONT_SMALL,
)
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock

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
            default_dt = tehran_now()

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
            bd=0,
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

        # REPLACED DateEntry with JalaliDateEntry
        self.date_entry = JalaliDateEntry(
            body,
            width=16
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
            if greg_date is None:
                raise ValueError("تاریخ نامعتبر")

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
# WORK ORDER STATUS CHANGE DIALOG
# =============================================================================

class WorkOrderStatusChangeDialog(tk.Toplevel):
    """Dialog for reopening a Work Order at an earlier workflow stage."""

    def __init__(self, parent, work_order, repo, options):
        super().__init__(parent)
        self.result = None
        self.reason = ""
        self.configure(bg=BG)
        self.title("تغییر وضعیت دستور کار")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        current = repo.status_label(getattr(work_order, "status", None))

        container = tk.Frame(
            self,
            bg=CARD,
            bd=0,
            relief="solid",
            highlightbackground=GRAY_BORDER,
            highlightthickness=1,
        )
        container.pack(fill="both", expand=True, padx=18, pady=18)

        header = tk.Frame(container, bg=PRIMARY, height=58)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="🔁 تغییر وضعیت دستور کار",
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE,
        ).pack(side="right", padx=18, pady=14)

        body = tk.Frame(container, bg=CARD)
        body.pack(fill="both", expand=True, padx=22, pady=20)

        tk.Label(
            body,
            text="وضعیت فعلی:",
            font=FONT_NORMAL,
            bg=CARD,
            fg=TEXT_DARK,
        ).grid(row=0, column=1, sticky="e", pady=8)

        tk.Label(
            body,
            text=current,
            font=("Tahoma", 10, "bold"),
            bg=CARD,
            fg=PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=8, pady=8)

        tk.Label(
            body,
            text="بازگشت به مرحله:",
            font=FONT_NORMAL,
            bg=CARD,
            fg=TEXT_DARK,
        ).grid(row=1, column=1, sticky="e", pady=8)

        labels = [repo.status_label(item) for item in options]
        self._status_by_label = dict(zip(labels, options))
        self.target_var = tk.StringVar(value=labels[0] if labels else "")
        self.target_combo = ttk.Combobox(
            body,
            state="readonly",
            textvariable=self.target_var,
            values=labels,
            width=25,
            font=FONT_NORMAL,
        )
        self.target_combo.grid(row=1, column=0, sticky="w", padx=8, pady=8)

        tk.Label(
            body,
            text="دلیل / توضیح (اختیاری):",
            font=FONT_NORMAL,
            bg=CARD,
            fg=TEXT_DARK,
        ).grid(row=2, column=1, sticky="ne", pady=8)

        self.reason_entry = tk.Text(
            body,
            height=4,
            width=34,
            font=FONT_NORMAL,
            wrap="word",
            relief="solid",
            bd=1,
            bg=WHITE,
            fg=TEXT_DARK,
        )
        self.reason_entry.grid(row=2, column=0, sticky="w", padx=8, pady=8)

        note = (
            "این عملیات فقط وضعیت را عوض نمی‌کند؛ اطلاعات وابسته به مرحله "
            "بعدی نیز همگام می‌شود."
        )
        tk.Label(
            body,
            text=note,
            font=FONT_SMALL,
            bg=CARD,
            fg=TEXT_LIGHT,
            wraplength=420,
            justify="right",
        ).grid(row=3, column=0, columnspan=2, sticky="e", pady=(4, 14))

        footer = tk.Frame(body, bg=CARD)
        footer.grid(row=4, column=0, columnspan=2, sticky="e")

        tk.Button(
            footer,
            text="تأیید تغییر",
            command=self._confirm,
            bg=SUCCESS,
            fg=WHITE,
            activebackground=SUCCESS,
            activeforeground=WHITE,
            relief="flat",
            cursor="hand2",
            font=FONT_NORMAL,
            padx=18,
            pady=7,
        ).pack(side="right", padx=4)

        tk.Button(
            footer,
            text="انصراف",
            command=self.destroy,
            bg="#DADFE8",
            fg=TEXT_DARK,
            relief="flat",
            cursor="hand2",
            font=FONT_NORMAL,
            padx=18,
            pady=7,
        ).pack(side="right", padx=4)

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        width, height = 560, 390
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _confirm(self):
        label = self.target_var.get().strip()
        target = self._status_by_label.get(label)
        if target is None:
            messagebox.showwarning(
                "تغییر وضعیت",
                "یک مرحله مقصد انتخاب کنید.",
                parent=self,
            )
            return
        self.reason = self.reason_entry.get("1.0", tk.END).strip()
        self.result = target
        self.destroy()


# =============================================================================
# WORK ORDER VIEW
# =============================================================================

class WorkOrderView(tk.Frame):
    # Rows are no longer tinted by status: the status badge shows it (views/ux.py).
    ux_status_only_rows = True


    def __init__(self, parent, work_order_repo, current_user):

        super().__init__(parent, bg=BG)

        self.current_user = current_user
        self.wo_repo = work_order_repo

        self.sp_repo = SparePartsRepository(SessionLocal)
        self.eq_repo = EquipmentRepository(SessionLocal)
        self.department_repo = DepartmentRepository(SessionLocal)
        self._visible_work_orders = []

        self.is_admin = current_user["role"] == "admin"
        self.is_manager = current_user["role"] in ["admin", "manager"]
        self.is_production_expert = current_user["role"] == "production_expert"
        self.is_technician = current_user["role"] == "technician"

        # Permissions: built-in roles exactly as before, custom roles from
        # «مدیریت نقش‌ها» (work orders: مشاهده / ایجاد-ویرایش / تأیید / حذف).
        self.can_create = AuthManager.allows(
            ("admin", "manager", "production_expert", "technician"), "work_orders", "write")
        self.can_approve_creation = AuthManager.allows(
            ("admin", "manager", "production_expert"), "work_orders", "approve")
        self.can_approve = AuthManager.allows(
            ("admin", "manager"), "work_orders", "approve")
        self.can_delete = AuthManager.allows(
            ("admin", "manager"), "work_orders", "delete")
        # Every role that can open this page may edit a work order and move
        # it back to an earlier stage (change status).
        everyone = ("admin", "manager", "production_expert", "technician")
        self.can_edit = AuthManager.allows(everyone, "work_orders", "read")
        self.can_change_status = self.can_edit

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

        if self.can_create:
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

        if self.can_approve:
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

        make_btn(
            "📄 PDF چاپی",
            self._export_pdf,
            "#7C3AED"
        ).pack(side="left", padx=4)

        # ================= FILTER CARD =================

        filter_card = tk.Frame(
            self,
            bg=CARD,
            bd=0,
            relief="solid",
            highlightbackground=GRAY_BORDER,
            highlightthickness=1
        )

        filter_card.pack(fill="x", padx=20, pady=15)

        filter_inner = tk.Frame(filter_card, bg=CARD)
        filter_inner.pack(fill="x", padx=15, pady=(15, 10))

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
        status_combo.bind("<<ComboboxSelected>>", lambda e=None: self._load())

        # Department filter
        tk.Label(
            filter_inner,
            text="دپارتمان:",
            bg=CARD,
            fg=TEXT_DARK,
            font=FONT_NORMAL,
        ).pack(side="right", padx=(0, 8))

        self.department_var = tk.StringVar(value="همه")
        self.department_combo = ttk.Combobox(
            filter_inner,
            textvariable=self.department_var,
            state="readonly",
            width=16,
            font=FONT_NORMAL,
        )
        self.department_combo.pack(side="right", padx=(0, 15))
        self.department_combo.bind("<<ComboboxSelected>>", lambda e=None: self._load())
        self._load_departments()

        # Equipment category filter

        tk.Label(filter_inner, text="دسته تجهیز:", bg=CARD, fg=TEXT_DARK, font=FONT_NORMAL).pack(side="right", padx=(0,8))
        self.category_var = tk.StringVar(value="همه")
        self.category_combo = ttk.Combobox(filter_inner, textvariable=self.category_var, state="readonly",
                                           width=16, font=FONT_NORMAL)
        self.category_combo.pack(side="right", padx=(0,15))
        self.category_combo.bind("<<ComboboxSelected>>", lambda e=None: self._load())
        self._load_categories()

        # Second filter row: on normal screens the date filters and the
        # «اعمال فیلتر» button did not fit in one row and were cut off.
        filter_row2 = tk.Frame(filter_card, bg=CARD)
        filter_row2.pack(fill="x", padx=15, pady=(0, 15))

        # Search
        tk.Label(
            filter_row2,
            text="جستجو:",
            bg=CARD,
            fg=TEXT_DARK,
            font=FONT_NORMAL,
        ).pack(side="right", padx=(0, 8))

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(
            filter_row2,
            textvariable=self.search_var,
            font=FONT_NORMAL,
            width=28,
            relief="solid",
            bd=1,
            bg=WHITE,
            fg=TEXT_DARK,
            insertbackground=TEXT_DARK,
            justify="right",
        )
        search_entry.pack(side="right", padx=(0, 12), ipady=4)
        search_entry.bind("<Return>", lambda e=None: self._load())

        # Dates – replaced with JalaliDateEntry

        tk.Label(
            filter_row2,
            text="از تاریخ:",
            bg=CARD,
            fg=TEXT_DARK,
            font=FONT_SMALL
        ).pack(side="right", padx=(0, 5))

        self.start_date = JalaliDateEntry(
            filter_row2,
            width=12
        )
        # Blank by default: all historical Work Orders remain visible.
        self.start_date.set_date(None)
        self.start_date.pack(side="right", padx=(0, 10))

        tk.Label(
            filter_row2,
            text="تا تاریخ:",
            bg=CARD,
            fg=TEXT_DARK,
            font=FONT_SMALL
        ).pack(side="right", padx=(0, 5))

        self.end_date = JalaliDateEntry(
            filter_row2,
            width=12
        )
        # Blank by default: all historical Work Orders remain visible.
        self.end_date.set_date(None)
        self.end_date.pack(side="right", padx=(0, 10))

        tk.Button(
            filter_row2,
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
            bd=0,
            relief="solid",
            highlightbackground=GRAY_BORDER,
            highlightthickness=1
        )

        table_card.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # ================= TREE STYLE =================

        style = ttk.Style()

        from utils.theme import ensure_theme

        ensure_theme(style)  # never switch the global ttk theme per page

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
            "status",
            "failure_time",
            "department",
            "personnel",
            "operator",
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
        rtl_columns(self.tree)  # RTL column order

        # FIXED: total_cost column anchor to "e" (right-aligned)
        headers = [
            ("id", "شناسه", 70, "center"),
            ("title", "عنوان دستور کار", 220, "w"),
            ("type", "نوع", 90, "center"),
            ("equipment", "تجهیز", 170, "w"),
            ("priority", "اولویت", 90, "center"),
            ("status", "وضعیت", 130, "center"),
            ("failure_time", "اعلام خرابی", 150, "center"),
            ("department", "دپارتمان مسئول", 160, "w"),
            ("personnel", "پرسنل انجام‌دهنده", 180, "w"),
            ("operator", "اپراتور", 130, "center"),
            ("start", "شروع", 150, "center"),
            ("end", "اتمام", 150, "center"),
            ("deadline", "ددلاین", 150, "center"),
            ("total_cost", "هزینه", 150, "e"),   # RIGHT ALIGN
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

        self.tree.bind("<Delete>", lambda e=None: self._delete_selected())
        self.tree.bind("<F2>", lambda e=None: self._edit_selected())
        self.tree.bind("<Control-n>", lambda e=None: self._add_work())

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

        # each item follows its own permission (see __init__)
        if self.can_approve_creation or self.can_approve:
            self.context_menu.add_separator()

        if self.can_approve_creation:
            self.context_menu.add_command(
                label="👍 تایید ایجاد دستور کار",
                command=self._approve_creation
            )

        if self.can_approve:
            self.context_menu.add_command(
                label="✅ تایید نهایی",
                command=self._approve_work
            )

            self.context_menu.add_command(
                label="❌ رد اتمام",
                command=self._reject_finish
            )

        if self.can_edit or self.can_change_status or self.can_delete:
            self.context_menu.add_separator()

        if self.can_edit:
            self.context_menu.add_command(
                label="✏️ ویرایش",
                command=self._edit_work
            )

        if self.can_change_status:
            self.context_menu.add_command(
                label="🔁 تغییر وضعیت",
                command=self._change_status
            )

        if self.can_delete:
            self.context_menu.add_command(
                label="🗑️ حذف",
                command=self._delete_work
            )

        self.tree.bind("<Button-3>", self._show_context_menu)

    def _load_departments(self):
        try:
            departments = self.department_repo.get_all() or []
            names = []
            for department in departments:
                name = str(getattr(department, "name", "") or "").strip()
                if name:
                    names.append(name)
            names = sorted(set(names))
            self.department_combo["values"] = ["همه"] + names
            if self.department_var.get() not in (["همه"] + names):
                self.department_var.set("همه")
        except Exception as exc:
            print(f"Department filter load failed: {exc}")
            self.department_combo["values"] = ["همه"]
            self.department_var.set("همه")

    # -------------------------------------------------------------------------

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

                # Part prices are cached per data load: v2.3 queried the
                # database once per part line of every row on every refresh.
                cache = self.__dict__.setdefault("_part_price_cache", {})

                for item in parts_list:

                    part_id = item.get("part_id")
                    qty = item.get("quantity", 0)

                    if part_id not in cache:
                        part = self.sp_repo.get_by_id(part_id)
                        cache[part_id] = (
                            float(part.unit_price or 0) if part else None
                        )

                    price = cache[part_id]
                    if price is not None:
                        # float(): unit_price is a Decimal; v2.3 added it to a
                        # float, which raised TypeError and was silently
                        # swallowed, so parts were never in the total cost.
                        total += price * float(qty or 0)

            except Exception:
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

        self._part_price_cache = {}

        if self.can_approve:
            try:
                from services.pm_service import PMService
                PMService(SessionLocal).generate_due_work_orders(days_ahead=1)
            except Exception as exc:
                print(f"Auto PM generation failed: {exc}")

        for item in self.tree.get_children():
            self.tree.delete(item)

        mapping = {
            "در انتظار تأیید": WorkOrderStatus.PENDING_APPROVAL,
            "در انتظار": WorkOrderStatus.PENDING,
            "در حال انجام": WorkOrderStatus.IN_PROGRESS,
            "درخواست اتمام": WorkOrderStatus.FINISH_REQUESTED,
            "تایید شده(تکمیل)": WorkOrderStatus.APPROVED,
            "رد شده": WorkOrderStatus.REJECTED,
        }

        status_filter = mapping.get(self.status_var.get())
        start = self.start_date.get_date()
        end = self.end_date.get_date()
        department_filter = self.department_var.get()
        search = self.search_var.get().strip().lower()

        # IMPORTANT: never filter the result by current user role here.
        # Every authenticated user can SEE every Work Order.
        # Action buttons/operations remain protected separately by role.
        work_orders = self.wo_repo.get_all(status_filter=status_filter) or []

        if self.category_var.get() != "همه":
            category = self.category_var.get()
            work_orders = [
                wo for wo in work_orders
                if getattr(getattr(wo, "equipment", None), "category", None) == category
            ]

        if department_filter and department_filter != "همه":
            work_orders = [
                wo for wo in work_orders
                if getattr(getattr(wo, "department", None), "name", "") == department_filter
            ]

        type_fa = {
            "CORRECTIVE": "CM",
            "PREVENTIVE": "PM",
            "EMERGENCY": "EM",
            "PM": "PM",
            "INSPECTION": "بازرسی",
        }
        status_map = {
            WorkOrderStatus.PENDING_APPROVAL: "در انتظار تأیید",
            WorkOrderStatus.PENDING: "در انتظار",
            WorkOrderStatus.IN_PROGRESS: "در حال انجام",
            WorkOrderStatus.FINISH_REQUESTED: "درخواست اتمام",
            WorkOrderStatus.APPROVED: "تایید شده",
            WorkOrderStatus.REJECTED: "رد شده",
        }
        priority_fa = {"low": "کم", "medium": "متوسط", "high": "بالا", "urgent": "فوری"}

        filtered = []
        for wo in work_orders:
            created = getattr(wo, "created_at", None)
            if start and created and created.date() < start:
                continue
            if end and created and created.date() > end:
                continue

            if search:
                eq = getattr(wo, "equipment", None)
                dep = getattr(wo, "department", None)
                operator = getattr(wo, "operator", None)
                completers = list(getattr(wo, "completers", []) or [])
                personnel_parts = []
                for p in completers:
                    personnel_parts.extend([
                        getattr(p, "full_name", ""),
                        getattr(p, "personnel_code", ""),
                    ])
                type_raw = getattr(getattr(wo, "type", None), "value", getattr(getattr(wo, "type", None), "name", ""))
                status_raw = getattr(getattr(wo, "status", None), "value", getattr(getattr(wo, "status", None), "name", ""))
                priority_raw = getattr(getattr(wo, "priority", None), "value", getattr(getattr(wo, "priority", None), "name", ""))
                haystack = " ".join(str(v or "") for v in [
                    getattr(wo, "id", ""), getattr(wo, "title", ""),
                    getattr(eq, "name", ""), getattr(eq, "code", ""), getattr(eq, "category", ""),
                    getattr(dep, "name", ""), getattr(operator, "full_name", ""),
                    type_raw, type_fa.get(str(type_raw).upper(), ""),
                    status_raw, status_map.get(getattr(wo, "status", None), ""),
                    priority_raw, priority_fa.get(str(priority_raw).lower(), ""),
                    to_jalali_datetime_str(getattr(wo, "failure_report_time", None)),
                    to_jalali_datetime_str(getattr(wo, "scheduled_date", None)),
                    to_jalali_datetime_str(getattr(wo, "start_time", None)),
                    to_jalali_datetime_str(getattr(wo, "end_time", None)),
                    to_jalali_datetime_str(getattr(wo, "deadline", None)),
                    getattr(wo, "description", ""), getattr(wo, "operator_notes", ""),
                    getattr(wo, "cost_description", ""), getattr(wo, "delay_minutes", ""),
                    getattr(wo, "delay_reason", ""), getattr(wo, "root_parent_id", ""),
                    *personnel_parts,
                ]).lower()
                if search not in haystack:
                    continue

            filtered.append(wo)

        # Save exact displayed set for PDF and deterministic batch operations.
        self._visible_work_orders = list(filtered)

        for wo in filtered:
            eq_name = getattr(getattr(wo, "equipment", None), "name", "-") or "-"
            department_name = getattr(getattr(wo, "department", None), "name", "—") or "—"
            completers = list(getattr(wo, "completers", []) or [])
            personnel_parts = []
            for person in completers:
                code = str(getattr(person, "personnel_code", "") or "").strip()
                name = str(getattr(person, "full_name", "") or "").strip()
                personnel_parts.append(f"{code} - {name}" if code and name else (name or code or "—"))
            personnel_display = "، ".join(personnel_parts) if personnel_parts else "—"
            operator_name = getattr(getattr(wo, "operator", None), "full_name", "-") or "-"
            priority_raw = getattr(getattr(wo, "priority", None), "value", getattr(getattr(wo, "priority", None), "name", "medium"))
            priority_text = priority_fa.get(str(priority_raw).lower(), str(priority_raw))
            failure = to_jalali_datetime_str(getattr(wo, "failure_report_time", None))
            start_s = to_jalali_datetime_str(getattr(wo, "start_time", None))
            end_s = to_jalali_datetime_str(getattr(wo, "end_time", None))
            deadline_s = to_jalali_datetime_str(getattr(wo, "deadline", None))
            status_obj = getattr(wo, "status", None)
            type_obj = getattr(wo, "type", None)
            status_text = status_map.get(status_obj, getattr(status_obj, "name", str(status_obj)))
            type_name = getattr(type_obj, "name", getattr(type_obj, "value", ""))
            type_display = type_fa.get(str(type_name).upper(), str(type_name))
            total_cost = self._calculate_total_cost(wo)
            parent_id = getattr(wo, "root_parent_id", None) or ""

            self.tree.insert(
                "", "end",
                values=(
                    wo.id, getattr(wo, "title", ""), type_display, eq_name,
                    priority_text, status_text, failure, department_name, personnel_display,
                    operator_name, start_s, end_s, deadline_s, f"{total_cost:,.0f}", parent_id
                ),
                tags=(getattr(status_obj, "name", ""),),
            )

    def _delete_work(self):

        if not self.can_delete:
            messagebox.showwarning(
                "دسترسی",
                "فقط مدیر یا مدیر سیستم می‌تواند حذف کند."
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

        if not self.can_delete:
            messagebox.showwarning(
                "دسترسی",
                "فقط مدیر یا مدیر سیستم می‌تواند حذف کند."
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

        selected_ids = []
        for item in self.tree.selection():
            try:
                values = self.tree.item(item, "values")
                if values:
                    selected_ids.append(int(values[0]))
            except (TypeError, ValueError, tk.TclError):
                continue

        run_work_order_export(
            self,
            self.wo_repo,
            selected_wo_ids=selected_ids,
        )

    def _add_work(self):
        """Open the normal Work Order creation dialog."""
        if not self.can_create:
            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به ایجاد دستور کار نیستید.",
                parent=self,
            )
            return

        dlg = WorkOrderDialog(
            self,
            self.wo_repo,
        )
        self.wait_window(dlg)

        if getattr(dlg, "result", None):
            self._load()

    def _edit_work(self):
        """Open the Work Order edit dialog for the selected Work Order."""
        if not self.can_edit:
            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به ویرایش دستور کار نیستید.",
                parent=self,
            )
            return

        wo_id = self._selected_id()
        if not wo_id:
            return

        wo = self.wo_repo.get_by_id(wo_id)
        if not wo:
            messagebox.showerror(
                "خطا",
                "دستور کار یافت نشد.",
                parent=self,
            )
            return

        dlg = WorkOrderDialog(
            self,
            self.wo_repo,
            work_order=wo,
        )
        self.wait_window(dlg)

        if getattr(dlg, "result", None):
            self._load()

    # =========================================================================
    # PRINTABLE PDF
    # =========================================================================

    def _export_pdf(self):
        selection = self.tree.selection()
        visible_by_id = {int(getattr(wo, "id")): wo for wo in self._visible_work_orders if getattr(wo, "id", None) is not None}

        # Rows are inserted without an explicit iid, so the work-order id is
        # the first VALUE of the row (v2.3 used int(iid), which always failed,
        # so the PDF silently contained ALL visible work orders instead of
        # the selected ones).
        selected_ids = []
        for item in selection:
            try:
                selected_ids.append(int(self.tree.item(item, "values")[0]))
            except (TypeError, ValueError, IndexError):
                pass

        if selection and not selected_ids:
            messagebox.showwarning("خروجی PDF", "شناسه دستورکارهای انتخاب‌شده خوانده نشد.", parent=self)
            return

        if selected_ids:
            work_orders = [visible_by_id[wid] for wid in selected_ids if wid in visible_by_id]
            scope_text = "دستورکارهای انتخاب‌شده"
        else:
            work_orders = list(self._visible_work_orders)
            scope_text = "همه دستورکارهای نمایش داده‌شده در جدول (پس از فیلتر)"

        if not work_orders:
            messagebox.showwarning(
                "خروجی PDF",
                "هیچ دستورکاری برای چاپ/خروجی وجود ندارد.",
                parent=self,
            )
            return

        from services.pdf_service import ROWS_PER_PAGE

        count = len(work_orders)
        pages = (count + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
        ids = [getattr(wo, "id", None) for wo in work_orders]
        first_id = ids[0] if ids else "-"
        last_id = ids[-1] if ids else "-"

        def _date_text(entry):
            try:
                value = entry.get_date()
            except Exception:
                value = None
            return to_jalali_date_str(value) if value else "بدون محدودیت"

        filters = [
            ("وضعیت", self.status_var.get()),
            ("دپارتمان", self.department_var.get()),
            ("دسته تجهیز", self.category_var.get()),
        ]
        filter_lines = [f"   • {label}: {value}" for label, value in filters if value and value != "همه"]
        if self.start_date.get_date() or self.end_date.get_date():
            filter_lines.append(f"   • بازه تاریخ: از {_date_text(self.start_date)} تا {_date_text(self.end_date)}")
        search = self.search_var.get().strip()
        if search:
            filter_lines.append(f"   • جستجو: {search}")

        confirmation = (
            "آیا می‌خواهید خروجی PDF ایجاد شود؟\n\n"
            "نوع خروجی: فهرست چاپی دستورکارها (جدول، A4 افقی)\n"
            f"دامنه: {scope_text}\n"
            f"تعداد دستورکارها: {count:,}\n"
            f"اولین شناسه: {first_id}\n"
            f"آخرین شناسه: {last_id}\n"
            "فیلترها:\n" + ("\n".join(filter_lines) if filter_lines else "   بدون فیلتر") + "\n"
            f"تعداد صفحات: {pages:,}\n"
            f"تعداد ردیف در هر صفحه: {ROWS_PER_PAGE}\n\n"
            "بعد از تأیید، محل ذخیره PDF پرسیده می‌شود و سپس فایل باز خواهد شد."
        )

        if not messagebox.askyesno("تأیید خروجی PDF", confirmation, parent=self):
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"WorkOrders_Print_{jalali_stamp()}.pdf",
        )
        if not path:
            return

        try:
            from views.ui_kit import busy
            with busy(self):
                export_work_orders_pdf(work_orders, path)
            messagebox.showinfo(
                "موفق",
                f"PDF با موفقیت ایجاد شد.\n\nتعداد دستورکار: {count:,}\nتعداد صفحات: {pages:,}",
                parent=self,
            )
            try:
                os.startfile(os.path.abspath(path))
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror(
                "خطا در PDF",
                f"ایجاد PDF با خطا مواجه شد:\n\n{exc}",
                parent=self,
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

        if not self.can_create:
            messagebox.showwarning("دسترسی", "شما مجاز به انجام این کار روی دستور کارها نیستید.", parent=self)
            return

        wo_id = self._selected_id()

        if not wo_id:
            return

        wo = self.wo_repo.get_by_id(wo_id)

        if not wo:
            messagebox.showerror("خطا", "دستور کار یافت نشد.")
            return

        if wo.status != WorkOrderStatus.PENDING:
            messagebox.showwarning("خطا", "فقط کارهای در انتظار قابل شروع هستند.")
            return

        if not wo.department_id:
            messagebox.showerror("خطا", "دپارتمان مسئول این دستورکار مشخص نشده است.")
            return

        dlg = PickDateTimeDialog(self, title="انتخاب زمان شروع کار")
        self.wait_window(dlg)
        if not dlg.result:
            return

        # Let the repository validate the workflow first.
        ok, msg = self.wo_repo.start_work(wo_id)
        if not ok:
            messagebox.showerror("خطا", msg)
            return

        session = SessionLocal()
        try:
            wo_obj = session.query(WorkOrder).filter_by(id=wo_id).first()
            if not wo_obj:
                messagebox.showerror("خطا", "دستور کار یافت نشد.")
                return
            wo_obj.start_time = dlg.result
            session.commit()
            messagebox.showinfo("موفق", "شروع کار ثبت شد.")
            self._load()
        except Exception as e:
            session.rollback()
            messagebox.showerror("خطا", str(e))
        finally:
            session.close()

    def _request_finish(self):
        """
        Open the single finish-report dialog.

        Personnel selection happens inside PartsSelectionDialog. That dialog
        is the only personnel picker shown to the user and supports selecting
        multiple Personnel from the Work Order's exact Department.

        Completion time is still collected first, then the finish report
        dialog collects Personnel, notes, cost, and delay information.
        """
        if not self.can_create:
            messagebox.showwarning("دسترسی", "شما مجاز به انجام این کار روی دستور کارها نیستید.", parent=self)
            return
        wo_id = self._selected_id()
        if not wo_id:
            return

        wo = self.wo_repo.get_by_id(wo_id)
        if not wo:
            messagebox.showerror(
                "خطا",
                "دستور کار یافت نشد.",
                parent=self,
            )
            return

        if wo.status != WorkOrderStatus.IN_PROGRESS:
            messagebox.showwarning(
                "خطا",
                "فقط کارهای در حال انجام قابل ارسال هستند.",
                parent=self,
            )
            return

        if not wo.department_id:
            messagebox.showerror(
                "خطا",
                "دپارتمان مسئول این دستورکار مشخص نشده است.",
                parent=self,
            )
            return

        # --------------------------------------------------------------
        # 1. Pick completion time
        # --------------------------------------------------------------
        time_dlg = PickDateTimeDialog(
            self,
            title="انتخاب زمان اتمام کار",
        )
        self.wait_window(time_dlg)

        if not time_dlg.result:
            return

        end_time = time_dlg.result

        # --------------------------------------------------------------
        # 2. Open the ONLY finish-report dialog.
        #
        # This dialog already contains:
        #   - multi-personnel selection
        #   - hidden spare-parts UI
        #   - manual cost
        #   - delay
        #   - final repair notes
        #
        # Do NOT open another PersonnelPickerDialog here.
        # --------------------------------------------------------------
        dlg = PartsSelectionDialog(
            self,
            self.wo_repo,
            wo_id,
        )
        self.wait_window(dlg)

        if not dlg.result:
            return

        personnel_ids = getattr(
            dlg,
            "personnel_ids",
            None,
        )

        personnel_id = getattr(
            dlg,
            "personnel_id",
            None,
        )

        if not personnel_ids and personnel_id:
            personnel_ids = [personnel_id]

        if not personnel_ids:
            messagebox.showerror(
                "خطا",
                "حداقل یک پرسنل انجام‌دهنده باید انتخاب شود.",
                parent=self,
            )
            return

        # --------------------------------------------------------------
        # 3. Submit finish request.
        #
        # Send both personnel_ids (new API) and personnel_id (legacy
        # compatibility). The repository de-duplicates them safely.
        # --------------------------------------------------------------
        ok, msg = self.wo_repo.request_finish(
            wo_id,
            personnel_id=personnel_id,
            personnel_ids=personnel_ids,
            end_time=end_time,
            used_parts_list=getattr(
                dlg,
                "used_parts",
                None,
            ),
            manual_cost=getattr(
                dlg,
                "manual_cost",
                None,
            ),
            cost_description=getattr(
                dlg,
                "cost_description",
                None,
            ),
            technician_notes=getattr(
                dlg,
                "technician_notes",
                None,
            ),
            delay_minutes=getattr(
                dlg,
                "delay_minutes",
                None,
            ),
            delay_reason=getattr(
                dlg,
                "delay_reason",
                None,
            ),
        )

        if ok:
            messagebox.showinfo(
                "موفق",
                msg,
                parent=self,
            )
            self._load()
        else:
            messagebox.showerror(
                "خطا",
                msg,
                parent=self,
            )

    def _approve_creation(self):

        if not self.can_approve_creation:
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

        if not self.can_approve:
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

        if not self.can_approve:
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

    def _change_status(self):
        """Reopen the selected Work Order at an earlier workflow stage."""
        if not self.can_change_status:
            messagebox.showwarning(
                "دسترسی",
                "شما مجاز به تغییر وضعیت دستور کار نیستید.",
                parent=self,
            )
            return

        wo_id = self._selected_id()
        if not wo_id:
            return

        wo = self.wo_repo.get_by_id(wo_id)
        if not wo:
            messagebox.showerror(
                "خطا",
                "دستور کار یافت نشد.",
                parent=self,
            )
            return

        options = self.wo_repo.backward_status_options(wo.status)
        if not options:
            messagebox.showinfo(
                "تغییر وضعیت",
                "برای این وضعیت، مرحله قبلی قابل بازگردانی وجود ندارد.",
                parent=self,
            )
            return

        dlg = WorkOrderStatusChangeDialog(
            self,
            wo,
            self.wo_repo,
            options,
        )
        self.wait_window(dlg)

        if dlg.result is None:
            return

        current_label = self.wo_repo.status_label(wo.status)
        target_label = self.wo_repo.status_label(dlg.result)
        confirmed = messagebox.askyesno(
            "تأیید تغییر مرحله",
            (
                f"وضعیت «{current_label}» به «{target_label}» بازگردانده شود؟\n\n"
                "اطلاعات وابسته به مرحله نیز همگام خواهد شد."
            ),
            parent=self,
        )
        if not confirmed:
            return

        ok, msg = self.wo_repo.change_status(
            wo_id,
            dlg.result,
            changed_by_user_id=self.current_user.get("id"),
            reason=dlg.reason,
        )

        if ok:
            messagebox.showinfo("موفق", msg, parent=self)
            self._load()
        else:
            messagebox.showerror("خطا", msg, parent=self)

    def _show_context_menu(self, event):

        try:

            row_id = self.tree.identify_row(event.y)

            if row_id:
                self.tree.selection_set(row_id)
                self.context_menu.post(event.x_root, event.y_root)

        finally:
            self.context_menu.grab_release()

    def _generate_pm_work_orders(self):

        if not self.can_approve:
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

        info_card = tk.Frame(scrollable, bg=CARD, bd=0, relief="solid",
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
        r = add_row(grid, "تاریخ برنامه:", to_jalali_date_str(wo.scheduled_date), r)
        r = add_row(grid, "شروع:", to_jalali_datetime_str(wo.start_time), r)
        r = add_row(grid, "پایان:", to_jalali_datetime_str(wo.end_time), r)
        r = add_row(grid, "دپارتمان مسئول:", wo.department.name if getattr(wo, "department", None) else "—", r)
        completer_list = list(getattr(wo, "completers", []) or [])
        completed_parts = []
        for person in completer_list:
            p_code = str(getattr(person, "personnel_code", "") or "").strip()
            p_name = str(getattr(person, "full_name", "") or "").strip()
            completed_parts.append(
                f"{p_code} - {p_name}" if p_code and p_name else (p_name or p_code or "—")
            )
        completed_personnel_text = "، ".join(completed_parts) if completed_parts else "—"
        r = add_row(grid, "پرسنل انجام‌دهنده:", completed_personnel_text, r)
        r = add_row(grid, "اپراتور:", wo.operator.full_name if wo.operator else "—", r)
        r = add_row(grid, "ددلاین:", to_jalali_datetime_str(wo.deadline), r)
        r = add_row(grid, "هزینه دستی (ریال):", f"{wo.manual_cost:,.0f}" if wo.manual_cost else "0", r)
        r = add_row(grid, "توضیح هزینه:", wo.cost_description or "—", r)
        r = add_row(grid, "یادداشت اپراتور:", wo.operator_notes or "—", r)
        r = add_row(grid, "توضیحات تکنسین:", wo.description or "—", r)
        r = add_row(grid, "قطعات مصرفی:", wo.parts_used or "—", r)
        r = add_row(grid, "تأخیر (دقیقه):", str(wo.delay_minutes) if wo.delay_minutes else "—", r)
        r = add_row(grid, "علت تأخیر:", wo.delay_reason or "—", r)

        tk.Button(detail, text="✕  بستن", font=FONT_NORMAL, bg=ACCENT, fg=WHITE, relief="flat", cursor="hand2", padx=20, pady=8, command=detail.destroy).pack(pady=10)

    def handle_new(self):
        if self.can_create:
            self._add_work()

    def handle_f2(self):
        self._edit_work()

    def handle_enter(self):
        """Called when Enter is pressed while this view is active."""
        self._show_work_order_detail()

    def ux_footer_spec(self):
        """Filters shown as removable chips under the table (views/ux.py)."""
        return {"filters": [("وضعیت", self.status_var, "همه"),
                            ("دپارتمان", self.department_var, "همه"),
                            ("دسته تجهیز", self.category_var, "همه"),
                            ("جستجو", self.search_var, "")],
                "apply": self._load, "noun": "دستور کار"}

