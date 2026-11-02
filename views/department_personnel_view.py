# views/personnel_management_view.py
"""
PM System - Personnel & Department Management
===============================================

Managers and Administrators can:

    - Add Department
    - Edit Department
    - Delete Department
    - Add Personnel
    - Edit Personnel
    - Delete Personnel
    - Assign Personnel to Department

Personnel fields:
    - personnel_code
    - full_name
    - department_id

No application User account is created here.

This page does NOT alter:
    - Work Order workflow
    - PM workflow
    - Existing Users
    - Existing Equipment
"""

import tkinter as tk
from views.ui_kit import rtl_columns  # RTL (right-to-left) table columns
from tkinter import ttk, messagebox
from views.ux import field_error

from database.department_repository import DepartmentRepository
from database.personnel_repository import PersonnelRepository
from database.db import SessionLocal

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
    FONT_TITLE,
    FONT_HEADING,
    FONT_NORMAL,
    FONT_SMALL,
)


# ============================================================================
# THEME
# ============================================================================

BG = GRAY_BG
CARD_BG = WHITE
PRIMARY = NAVY
DANGER = RED
BORDER = GRAY_BORDER
TEXT = TEXT_DARK
SUBTLE = TEXT_LIGHT


# ============================================================================
# VIEW
# ============================================================================

class PersonnelManagementView(tk.Frame):

    def __init__(
        self,
        parent,
        current_user,
        personnel_repo=None,
        department_repo=None,
    ):
        super().__init__(
            parent,
            bg=BG,
        )

        self.current_user = (
            current_user or {}
        )

        # Built-in: admin / manager (full). Custom roles: «مدیریت نقش‌ها».
        from auth.auth_manager import AuthManager

        self.can_write = AuthManager.allows(
            ("admin", "manager"), "personnel_management", "write")
        self.can_delete = AuthManager.allows(
            ("admin", "manager"), "personnel_management", "delete")

        if not AuthManager.allows(("admin", "manager"), "personnel_management", "read"):

            messagebox.showerror(
                "دسترسی غیرمجاز",
                "شما مجاز به مشاهده پرسنل و دپارتمان‌ها نیستید.",
                parent=parent,
            )

            self.destroy()
            return

        self.personnel_repo = (
            personnel_repo
            or PersonnelRepository(
                SessionLocal
            )
        )

        self.department_repo = (
            department_repo
            or DepartmentRepository(
                SessionLocal
            )
        )

        self.department_map = {}

        self._build_ui()
        self._apply_permissions()

        self._load_departments()

        self._load_personnel()

    def _apply_permissions(self):
        """
        Hide «افزودن / ویرایش» without write and «حذف» without delete permission.
        Buttons are recognised by the method they call (Tkinter names a button's
        command "<id><method name>"), not by their caption.
        """
        allowed = {
            "_add_department": self.can_write,
            "_edit_department": self.can_write,
            "_delete_department": self.can_delete,
            "_add_personnel": self.can_write,
            "_edit_personnel": self.can_write,
            "_delete_personnel": self.can_delete,
        }

        def walk(widget):
            for child in widget.winfo_children():
                yield child
                yield from walk(child)

        for widget in walk(self):
            if not isinstance(widget, tk.Button):
                continue
            try:
                command = str(widget.cget("command"))
            except tk.TclError:
                continue
            for method, ok in allowed.items():
                if command.endswith(method) and not ok:
                    widget.pack_forget()

    # =========================================================================
    # MAIN UI
    # =========================================================================

    def _build_ui(self):

        # ---------------------------------------------------------------------
        # Header
        # ---------------------------------------------------------------------

        header = tk.Frame(
            self,
            bg=PRIMARY,
            height=68,
        )

        header.pack(
            fill="x",
        )

        header.pack_propagate(
            False,
        )

        title_frame = tk.Frame(
            header,
            bg=PRIMARY,
        )

        title_frame.pack(
            side="right",
            fill="y",
            padx=22,
        )

        tk.Label(
            title_frame,
            text="👷  مدیریت پرسنل و دپارتمان‌ها",
            font=FONT_TITLE,
            bg=PRIMARY,
            fg=WHITE,
            anchor="e",
        ).pack(
            anchor="e",
            pady=(10, 0),
        )

        tk.Label(
            title_frame,
            text=(
                "تعریف دپارتمان‌ها و تخصیص پرسنل "
                "به دپارتمان مسئول"
            ),
            font=FONT_SMALL,
            bg=PRIMARY,
            fg=WHITE,
            anchor="e",
        ).pack(
            anchor="e",
        )

        # ---------------------------------------------------------------------
        # Main content
        # ---------------------------------------------------------------------

        content = tk.Frame(
            self,
            bg=BG,
        )

        content.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=18,
        )

        # Two panels.
        content.grid_columnconfigure(
            0,
            weight=1,
        )

        content.grid_columnconfigure(
            1,
            weight=2,
        )

        content.grid_rowconfigure(
            0,
            weight=1,
        )

        self._build_department_panel(
            content
        )

        self._build_personnel_panel(
            content
        )

    # =========================================================================
    # DEPARTMENT PANEL
    # =========================================================================

    def _build_department_panel(
        self,
        parent,
    ):

        outer = tk.Frame(
            parent,
            bg=BORDER,
        )

        outer.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 8),
        )

        card = tk.Frame(
            outer,
            bg=CARD_BG,
        )

        card.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
        )

        # Header
        panel_header = tk.Frame(
            card,
            bg=PRIMARY,
            height=50,
        )

        panel_header.pack(
            fill="x",
        )

        panel_header.pack_propagate(
            False,
        )

        tk.Label(
            panel_header,
            text="🏢  دپارتمان‌ها",
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE,
        ).pack(
            side="right",
            padx=14,
            pady=10,
        )

        # Toolbar
        toolbar = tk.Frame(
            card,
            bg=CARD_BG,
        )

        toolbar.pack(
            fill="x",
            padx=12,
            pady=10,
        )

        tk.Button(
            toolbar,
            text="➕ افزودن",
            command=self._add_department,
            bg=SUCCESS,
            fg=WHITE,
            activebackground=SUCCESS,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(
            side="right",
            padx=3,
        )

        tk.Button(
            toolbar,
            text="✏️ ویرایش",
            command=self._edit_department,
            bg=PRIMARY,
            fg=WHITE,
            activebackground=NAVY_LIGHT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(
            side="right",
            padx=3,
        )

        tk.Button(
            toolbar,
            text="🗑️ حذف",
            command=self._delete_department,
            bg=DANGER,
            fg=WHITE,
            activebackground=DANGER,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(
            side="right",
            padx=3,
        )

        # Tree
        tree_frame = tk.Frame(
            card,
            bg=CARD_BG,
        )

        tree_frame.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(0, 12),
        )

        columns = (
            "id",
            "name",
            "personnel",
        )

        self.department_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        rtl_columns(self.department_tree)  # RTL column order

        self.department_tree.heading(
            "id",
            text="#",
        )

        self.department_tree.heading(
            "name",
            text="نام دپارتمان",
        )

        self.department_tree.heading(
            "personnel",
            text="تعداد پرسنل",
        )

        self.department_tree.column(
            "id",
            width=55,
            anchor="center",
            stretch=False,
        )

        self.department_tree.column(
            "name",
            width=180,
            anchor="e",
        )

        self.department_tree.column(
            "personnel",
            width=100,
            anchor="center",
            stretch=False,
        )

        vsb = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.department_tree.yview,
        )

        self.department_tree.configure(
            yscrollcommand=vsb.set,
        )

        self.department_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        vsb.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        tree_frame.grid_rowconfigure(
            0,
            weight=1,
        )

        tree_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self.department_tree.bind(
            "<<TreeviewSelect>>",
            self._on_department_selected,
        )

        self.department_tree.bind(
            "<Double-1>",
            lambda _event:
            self._edit_department(),
        )

        self.department_tree.bind(
            "<Delete>",
            lambda _event:
            self._delete_department(),
        )

    # =========================================================================
    # PERSONNEL PANEL
    # =========================================================================

    def _build_personnel_panel(
        self,
        parent,
    ):

        outer = tk.Frame(
            parent,
            bg=BORDER,
        )

        outer.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(8, 0),
        )

        card = tk.Frame(
            outer,
            bg=CARD_BG,
        )

        card.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
        )

        # Header
        panel_header = tk.Frame(
            card,
            bg=PRIMARY,
            height=50,
        )

        panel_header.pack(
            fill="x",
        )

        panel_header.pack_propagate(
            False,
        )

        tk.Label(
            panel_header,
            text="👷  پرسنل",
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE,
        ).pack(
            side="right",
            padx=14,
            pady=10,
        )

        # Toolbar
        toolbar = tk.Frame(
            card,
            bg=CARD_BG,
        )

        toolbar.pack(
            fill="x",
            padx=12,
            pady=10,
        )

        tk.Label(
            toolbar,
            text="🔍",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
        ).pack(
            side="right",
            padx=(0, 5),
        )

        self.search_var = (
            tk.StringVar()
        )

        search_entry = ttk.Entry(
            toolbar,
            textvariable=(
                self.search_var
            ),
            font=FONT_NORMAL,
            justify="right",
        )

        search_entry.pack(
            side="right",
            fill="x",
            expand=True,
            padx=(0, 8),
        )

        self.search_var.trace_add(
            "write",
            lambda *_args:
            self._load_personnel(),
        )

        tk.Button(
            toolbar,
            text="➕ افزودن",
            command=self._add_personnel,
            bg=SUCCESS,
            fg=WHITE,
            activebackground=SUCCESS,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(
            side="right",
            padx=3,
        )

        tk.Button(
            toolbar,
            text="✏️ ویرایش",
            command=self._edit_personnel,
            bg=PRIMARY,
            fg=WHITE,
            activebackground=NAVY_LIGHT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(
            side="right",
            padx=3,
        )

        tk.Button(
            toolbar,
            text="🗑️ حذف",
            command=self._delete_personnel,
            bg=DANGER,
            fg=WHITE,
            activebackground=DANGER,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(
            side="right",
            padx=3,
        )

        # Department filter
        filter_frame = tk.Frame(
            card,
            bg=CARD_BG,
        )

        filter_frame.pack(
            fill="x",
            padx=12,
            pady=(0, 10),
        )

        tk.Label(
            filter_frame,
            text="دپارتمان:",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT,
        ).pack(
            side="right",
            padx=(0, 5),
        )

        self.department_filter_var = (
            tk.StringVar(
                value="همه"
            )
        )

        self.department_filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=(
                self.department_filter_var
            ),
            state="readonly",
            font=FONT_SMALL,
            width=22,
            justify="right",
        )

        self.department_filter_combo.pack(
            side="right",
        )

        self.department_filter_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event:
            self._load_personnel(),
        )

        # Tree
        tree_frame = tk.Frame(
            card,
            bg=CARD_BG,
        )

        tree_frame.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(0, 12),
        )

        columns = (
            "id",
            "code",
            "name",
            "department",
            "completed_works",
        )

        self.personnel_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        rtl_columns(self.personnel_tree)  # RTL column order

        self.personnel_tree.heading(
            "id",
            text="#",
        )

        self.personnel_tree.heading(
            "code",
            text="شماره پرسنلی",
        )

        self.personnel_tree.heading(
            "name",
            text="نام کامل",
        )

        self.personnel_tree.heading(
            "department",
            text="دپارتمان",
        )

        self.personnel_tree.heading(
            "completed_works",
            text="کارهای انجام‌شده",
        )

        self.personnel_tree.column(
            "id",
            width=55,
            anchor="center",
            stretch=False,
        )

        self.personnel_tree.column(
            "code",
            width=130,
            anchor="center",
        )

        self.personnel_tree.column(
            "name",
            width=200,
            anchor="e",
        )

        self.personnel_tree.column(
            "department",
            width=170,
            anchor="e",
        )

        self.personnel_tree.column(
            "completed_works",
            width=130,
            anchor="center",
            stretch=False,
        )

        vsb = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.personnel_tree.yview,
        )

        hsb = ttk.Scrollbar(
            tree_frame,
            orient="horizontal",
            command=self.personnel_tree.xview,
        )

        self.personnel_tree.configure(
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
        )

        self.personnel_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        vsb.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        hsb.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        tree_frame.grid_rowconfigure(
            0,
            weight=1,
        )

        tree_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self.personnel_tree.bind(
            "<Double-1>",
            lambda _event:
            self._edit_personnel(),
        )

        self.personnel_tree.bind(
            "<F2>",
            lambda _event:
            self._edit_personnel(),
        )

        self.personnel_tree.bind(
            "<Delete>",
            lambda _event:
            self._delete_personnel(),
        )

        self.personnel_tree.bind(
            "<Return>",
            lambda _event:
            self._edit_personnel(),
        )

    # =========================================================================
    # LOAD DEPARTMENTS
    # =========================================================================

    def _load_departments(
        self,
    ):

        try:

            departments = (
                self.department_repo
                .get_all()
                or []
            )

        except Exception as exc:

            departments = []

            messagebox.showerror(
                "خطا",
                (
                    "بارگذاری دپارتمان‌ها انجام نشد:\n\n"
                    f"{exc}"
                ),
                parent=self,
            )

        self.department_map = {}

        for department in departments:

            department_id = getattr(
                department,
                "id",
                None,
            )

            name = (
                getattr(
                    department,
                    "name",
                    "",
                )
                or ""
            ).strip()

            if (
                department_id is None
                or not name
            ):
                continue

            self.department_map[
                name
            ] = department_id

        self.department_tree.delete(
            *self.department_tree.get_children()
        )

        for name, department_id in (
            sorted(
                self.department_map.items(),
                key=lambda item:
                item[0],
            )
        ):

            try:
                personnel_count = (
                    self.department_repo
                    .count_personnel(
                        department_id
                    )
                )
            except Exception:
                personnel_count = 0

            self.department_tree.insert(
                "",
                "end",
                iid=str(
                    department_id
                ),
                values=(
                    department_id,
                    name,
                    personnel_count,
                ),
            )

        filter_values = (
            ["همه"]
            + sorted(
                self.department_map.keys()
            )
        )

        self.department_filter_combo[
            "values"
        ] = filter_values

        current_filter = (
            self.department_filter_var.get()
        )

        if current_filter not in (
            filter_values
        ):
            self.department_filter_var.set(
                "همه"
            )

    # =========================================================================
    # LOAD PERSONNEL
    # =========================================================================

    def _load_personnel(
        self,
    ):

        if not hasattr(
            self,
            "personnel_tree",
        ):
            return

        try:

            personnel_list = (
                self.personnel_repo
                .get_all()
                or []
            )

        except Exception as exc:

            messagebox.showerror(
                "خطا",
                (
                    "بارگذاری پرسنل انجام نشد:\n\n"
                    f"{exc}"
                ),
                parent=self,
            )

            return

        try:
            completion_counts = self.personnel_repo.get_completed_work_counts(
                [getattr(person, "id", None) for person in personnel_list]
            )
        except Exception:
            completion_counts = {}

        keyword = (
            self.search_var
            .get()
            .strip()
            .lower()
        )

        department_filter = (
            self.department_filter_var
            .get()
            .strip()
        )

        selected_department_id = (
            self.department_map.get(
                department_filter
            )
        )

        self.personnel_tree.delete(
            *self.personnel_tree.get_children()
        )

        for person in personnel_list:

            code = str(
                getattr(
                    person,
                    "personnel_code",
                    "",
                )
                or ""
            )

            full_name = str(
                getattr(
                    person,
                    "full_name",
                    "",
                )
                or ""
            )

            department = getattr(
                person,
                "department",
                None,
            )

            department_id = getattr(
                person,
                "department_id",
                None,
            )

            department_name = (
                getattr(
                    department,
                    "name",
                    "",
                )
                or ""
            )

            # Search
            if keyword:

                searchable = (
                    f"{code} "
                    f"{full_name} "
                    f"{department_name}"
                ).lower()

                if keyword not in searchable:
                    continue

            # Department filter
            if (
                selected_department_id
                is not None
                and department_id
                != selected_department_id
            ):
                continue

            self.personnel_tree.insert(
                "",
                "end",
                iid=str(
                    person.id
                ),
                values=(
                    person.id,
                    code,
                    full_name,
                    department_name,
                    completion_counts.get(int(person.id), 0),
                ),
            )

    # =========================================================================
    # DEPARTMENT SELECTION
    # =========================================================================

    def _on_department_selected(
        self,
        _event=None,
    ):

        selection = (
            self.department_tree
            .selection()
        )

        if not selection:
            return

        try:

            department_id = int(
                selection[0]
            )

        except (
            TypeError,
            ValueError,
        ):
            return

        department = (
            self.department_repo
            .get_by_id(
                department_id
            )
        )

        if not department:
            return

        name = (
            getattr(
                department,
                "name",
                "",
            )
            or ""
        )

        if name:

            self.department_filter_var.set(
                name
            )

            self._load_personnel()

    # =========================================================================
    # DEPARTMENT CRUD
    # =========================================================================

    def _add_department(
        self,
    ):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به افزودن دپارتمان نیستید.", parent=self)
            return

        name = self._ask_name(
            "افزودن دپارتمان",
            "نام دپارتمان جدید:",
        )

        if name is None:
            return

        ok, message, _department = (
            self.department_repo.create(
                name
            )
        )

        if not ok:

            messagebox.showerror(
                "خطا",
                message,
                parent=self,
            )

            return

        self._load_departments()
        self._load_personnel()

        messagebox.showinfo(
            "موفق",
            message,
            parent=self,
        )

    # -------------------------------------------------------------------------

    def _edit_department(
        self,
    ):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ویرایش دپارتمان نیستید.", parent=self)
            return

        selection = (
            self.department_tree
            .selection()
        )

        if not selection:

            messagebox.showwarning(
                "انتخاب",
                "لطفاً یک دپارتمان انتخاب کنید.",
                parent=self,
            )

            return

        try:

            department_id = int(
                selection[0]
            )

        except (
            TypeError,
            ValueError,
        ):

            return

        department = (
            self.department_repo
            .get_by_id(
                department_id
            )
        )

        if not department:

            messagebox.showerror(
                "خطا",
                "دپارتمان یافت نشد.",
                parent=self,
            )

            return

        current_name = (
            getattr(
                department,
                "name",
                "",
            )
            or ""
        )

        name = self._ask_name(
            "ویرایش دپارتمان",
            "نام دپارتمان:",
            initial=current_name,
        )

        if name is None:
            return

        ok, message = (
            self.department_repo.update(
                department_id,
                name,
            )
        )

        if not ok:

            messagebox.showerror(
                "خطا",
                message,
                parent=self,
            )

            return

        self._load_departments()
        self._load_personnel()

        messagebox.showinfo(
            "موفق",
            message,
            parent=self,
        )

    # -------------------------------------------------------------------------

    def _delete_department(
        self,
    ):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف دپارتمان نیستید.", parent=self)
            return

        selection = (
            self.department_tree
            .selection()
        )

        if not selection:

            messagebox.showwarning(
                "انتخاب",
                "لطفاً یک دپارتمان انتخاب کنید.",
                parent=self,
            )

            return

        try:

            department_id = int(
                selection[0]
            )

        except (
            TypeError,
            ValueError,
        ):

            return

        department = (
            self.department_repo
            .get_by_id(
                department_id
            )
        )

        if not department:
            return

        name = (
            getattr(
                department,
                "name",
                "",
            )
            or ""
        )

        usage = (
            self.department_repo
            .get_usage(
                department_id
            )
        )

        total_usage = (
            usage.get(
                "personnel",
                0,
            )
            + usage.get(
                "pm_schedules",
                0,
            )
            + usage.get(
                "work_orders",
                0,
            )
        )

        if total_usage > 0:

            messagebox.showwarning(
                "قابل حذف نیست",
                (
                    f"دپارتمان «{name}» در حال استفاده است.\n\n"
                    f"پرسنل: {usage.get('personnel', 0)}\n"
                    f"برنامه PM: {usage.get('pm_schedules', 0)}\n"
                    f"دستورکار: {usage.get('work_orders', 0)}\n\n"
                    "برای حفظ اطلاعات تاریخی، این دپارتمان حذف نمی‌شود."
                ),
                parent=self,
            )

            return

        confirmed = messagebox.askyesno(
            "تأیید حذف",
            (
                f"آیا از حذف دپارتمان «{name}» مطمئن هستید؟"
            ),
            parent=self,
        )

        if not confirmed:
            return

        ok, message = (
            self.department_repo.delete(
                department_id
            )
        )

        if not ok:

            messagebox.showerror(
                "خطا",
                message,
                parent=self,
            )

            return

        self._load_departments()
        self._load_personnel()

        messagebox.showinfo(
            "موفق",
            message,
            parent=self,
        )

    # =========================================================================
    # PERSONNEL CRUD
    # =========================================================================

    def _add_personnel(
        self,
    ):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به افزودن پرسنل نیستید.", parent=self)
            return

        dialog = PersonnelDialog(
            self,
            self.personnel_repo,
            self.department_repo,
            personnel=None,
        )

        self.wait_window(
            dialog
        )

        if dialog.result:

            self._load_departments()
            self._load_personnel()

    # -------------------------------------------------------------------------

    def _edit_personnel(
        self,
    ):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ویرایش پرسنل نیستید.", parent=self)
            return

        selection = (
            self.personnel_tree
            .selection()
        )

        if not selection:

            messagebox.showwarning(
                "انتخاب",
                "لطفاً یک پرسنل انتخاب کنید.",
                parent=self,
            )

            return

        try:

            personnel_id = int(
                selection[0]
            )

        except (
            TypeError,
            ValueError,
        ):

            return

        person = (
            self.personnel_repo
            .get_by_id(
                personnel_id
            )
        )

        if not person:

            messagebox.showerror(
                "خطا",
                "پرسنل یافت نشد.",
                parent=self,
            )

            return

        dialog = PersonnelDialog(
            self,
            self.personnel_repo,
            self.department_repo,
            personnel=person,
        )

        self.wait_window(
            dialog
        )

        if dialog.result:

            self._load_departments()
            self._load_personnel()

    # -------------------------------------------------------------------------

    def _delete_personnel(
        self,
    ):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف پرسنل نیستید.", parent=self)
            return

        selection = (
            self.personnel_tree
            .selection()
        )

        if not selection:

            messagebox.showwarning(
                "انتخاب",
                "لطفاً یک پرسنل انتخاب کنید.",
                parent=self,
            )

            return

        try:

            personnel_id = int(
                selection[0]
            )

        except (
            TypeError,
            ValueError,
        ):

            return

        person = (
            self.personnel_repo
            .get_by_id(
                personnel_id
            )
        )

        if not person:
            return

        name = (
            getattr(
                person,
                "full_name",
                "",
            )
            or ""
        )

        confirmed = messagebox.askyesno(
            "تأیید حذف",
            (
                f"آیا از حذف پرسنل «{name}» مطمئن هستید؟\n\n"
                "اگر سابقه انجام دستورکار داشته باشد، "
                "برای حفظ سوابق حذف نخواهد شد."
            ),
            parent=self,
        )

        if not confirmed:
            return

        ok, message = (
            self.personnel_repo.delete(
                personnel_id
            )
        )

        if not ok:

            messagebox.showwarning(
                "حذف انجام نشد",
                message,
                parent=self,
            )

            return

        self._load_departments()
        self._load_personnel()

        messagebox.showinfo(
            "موفق",
            message,
            parent=self,
        )

    # =========================================================================
    # GENERIC NAME DIALOG
    # =========================================================================

    def _ask_name(
        self,
        title,
        label,
        initial="",
    ):

        dialog = tk.Toplevel(
            self
        )

        dialog.title(
            title
        )

        dialog.configure(
            bg=BG
        )

        dialog.resizable(
            True,
            False,
        )

        dialog.minsize(
            380,
            180,
        )

        dialog.geometry(
            "420x200"
        )

        dialog.transient(
            self
        )

        dialog.grab_set()

        result = {
            "value": None
        }

        header = tk.Frame(
            dialog,
            bg=PRIMARY,
            height=48,
        )

        header.pack(
            fill="x"
        )

        header.pack_propagate(
            False
        )

        tk.Label(
            header,
            text=title,
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE,
        ).pack(
            expand=True
        )

        body = tk.Frame(
            dialog,
            bg=CARD_BG,
            padx=22,
            pady=18,
        )

        body.pack(
            fill="both",
            expand=True,
        )

        tk.Label(
            body,
            text=label,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            anchor="e",
        ).pack(
            fill="x",
            pady=(0, 5),
        )

        entry = ttk.Entry(
            body,
            font=FONT_NORMAL,
            justify="right",
        )

        entry.pack(
            fill="x",
            ipady=4,
        )

        if initial:
            entry.insert(
                0,
                initial,
            )

        def save():

            value = (
                entry.get()
                .strip()
            )

            if not value:

                field_error(entry, "وارد کردن نام الزامی است.")
                return

            result["value"] = value

            dialog.destroy()

        button_row = tk.Frame(
            body,
            bg=CARD_BG,
        )

        button_row.pack(
            fill="x",
            pady=(16, 0),
        )

        tk.Button(
            button_row,
            text="انصراف",
            command=dialog.destroy,
            bg=BG,
            fg=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=18,
            pady=6,
        ).pack(
            side="left",
        )

        tk.Button(
            button_row,
            text="ذخیره",
            command=save,
            bg=SUCCESS,
            fg=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=20,
            pady=6,
        ).pack(
            side="right",
        )

        dialog.bind(
            "<Return>",
            lambda _event:
            save(),
        )

        dialog.bind(
            "<Escape>",
            lambda _event:
            dialog.destroy(),
        )

        dialog.after(
            50,
            entry.focus_set,
        )

        dialog.update_idletasks()

        x = (
            self.winfo_rootx()
            + (
                self.winfo_width()
                - dialog.winfo_width()
            ) // 2
        )

        y = (
            self.winfo_rooty()
            + (
                self.winfo_height()
                - dialog.winfo_height()
            ) // 2
        )

        dialog.geometry(
            f"+{max(0, x)}+{max(0, y)}"
        )

        self.wait_window(
            dialog
        )

        return result["value"]


# ============================================================================
# PERSONNEL DIALOG
# ============================================================================

class PersonnelDialog(tk.Toplevel):

    def __init__(
        self,
        parent,
        personnel_repo,
        department_repo,
        personnel=None,
    ):
        super().__init__(
            parent
        )

        self.personnel_repo = (
            personnel_repo
        )

        self.department_repo = (
            department_repo
        )

        self.personnel = personnel

        self.result = False

        self.department_map = {}

        self.title(
            "ویرایش پرسنل"
            if personnel
            else "افزودن پرسنل"
        )

        self.configure(
            bg=BG
        )

        self.resizable(
            True,
            False,
        )

        self.minsize(
            480,
            390,
        )

        self.geometry(
            "520x430"
        )

        self.transient(
            parent
        )

        self.grab_set()

        self.protocol(
            "WM_DELETE_WINDOW",
            self.destroy,
        )

        self.bind(
            "<Escape>",
            lambda _event:
            self.destroy(),
        )

        self.bind(
            "<Control-s>",
            lambda _event:
            self._save(),
        )

        self._build_ui()
        self._load_departments()

        if personnel:
            self._populate()

        self.after(
            50,
            self._center,
        )

    # =========================================================================
    # BUILD
    # =========================================================================

    def _build_ui(self):

        header = tk.Frame(
            self,
            bg=PRIMARY,
            height=58,
        )

        header.pack(
            fill="x"
        )

        header.pack_propagate(
            False
        )

        title = (
            "✏️  ویرایش پرسنل"
            if self.personnel
            else "➕  افزودن پرسنل"
        )

        tk.Label(
            header,
            text=title,
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE,
        ).pack(
            expand=True
        )

        form = tk.Frame(
            self,
            bg=CARD_BG,
            padx=28,
            pady=22,
        )

        form.pack(
            fill="both",
            expand=True,
        )

        form.grid_columnconfigure(
            0,
            weight=1,
        )

        # ---------------------------------------------------------------------
        # Personnel code
        # ---------------------------------------------------------------------

        tk.Label(
            form,
            text="شماره پرسنلی *",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            anchor="e",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 5),
        )

        self.code_entry = ttk.Entry(
            form,
            font=FONT_NORMAL,
            justify="right",
        )

        self.code_entry.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(0, 14),
        )

        # ---------------------------------------------------------------------
        # Full name
        # ---------------------------------------------------------------------

        tk.Label(
            form,
            text="نام و نام خانوادگی *",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            anchor="e",
        ).grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(0, 5),
        )

        self.name_entry = ttk.Entry(
            form,
            font=FONT_NORMAL,
            justify="right",
        )

        self.name_entry.grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(0, 14),
        )

        # ---------------------------------------------------------------------
        # Department
        # ---------------------------------------------------------------------

        tk.Label(
            form,
            text="دپارتمان *",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            anchor="e",
        ).grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(0, 5),
        )

        self.department_var = (
            tk.StringVar()
        )

        self.department_combo = ttk.Combobox(
            form,
            textvariable=(
                self.department_var
            ),
            state="readonly",
            font=FONT_NORMAL,
            justify="right",
        )

        self.department_combo.grid(
            row=5,
            column=0,
            sticky="ew",
            pady=(0, 18),
        )

        # ---------------------------------------------------------------------
        # Footer
        # ---------------------------------------------------------------------

        footer = tk.Frame(
            self,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        footer.pack(
            fill="x"
        )

        tk.Button(
            footer,
            text="انصراف",
            command=self.destroy,
            bg=BG,
            fg=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=24,
            pady=8,
        ).pack(
            side="left",
            padx=14,
            pady=12,
        )

        tk.Button(
            footer,
            text="💾 ذخیره",
            command=self._save,
            bg=SUCCESS,
            fg=WHITE,
            activebackground=SUCCESS,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=28,
            pady=8,
        ).pack(
            side="right",
            padx=14,
            pady=12,
        )

    # =========================================================================
    # DEPARTMENTS
    # =========================================================================

    def _load_departments(
        self,
    ):

        try:

            departments = (
                self.department_repo
                .get_all()
                or []
            )

        except Exception as exc:

            messagebox.showerror(
                "خطا",
                (
                    "بارگذاری دپارتمان‌ها انجام نشد:\n\n"
                    f"{exc}"
                ),
                parent=self,
            )

            departments = []

        self.department_map = {}

        for department in departments:

            department_id = getattr(
                department,
                "id",
                None,
            )

            name = (
                getattr(
                    department,
                    "name",
                    "",
                )
                or ""
            ).strip()

            if (
                department_id is None
                or not name
            ):
                continue

            self.department_map[
                name
            ] = department_id

        values = sorted(
            self.department_map.keys()
        )

        self.department_combo[
            "values"
        ] = values

    # =========================================================================
    # POPULATE
    # =========================================================================

    def _populate(
        self,
    ):

        if not self.personnel:
            return

        self.code_entry.insert(
            0,
            getattr(
                self.personnel,
                "personnel_code",
                "",
            )
            or "",
        )

        self.name_entry.insert(
            0,
            getattr(
                self.personnel,
                "full_name",
                "",
            )
            or "",
        )

        department_id = getattr(
            self.personnel,
            "department_id",
            None,
        )

        for name, dep_id in (
            self.department_map.items()
        ):

            if dep_id == department_id:

                self.department_var.set(
                    name
                )

                break

    # =========================================================================
    # SAVE
    # =========================================================================

    def _save(
        self,
    ):

        code = (
            self.code_entry
            .get()
            .strip()
        )

        full_name = (
            self.name_entry
            .get()
            .strip()
        )

        department_name = (
            self.department_var
            .get()
            .strip()
        )

        if not code:

            field_error(self.code_entry, "شماره پرسنلی الزامی است.")
            return

        if not full_name:

            field_error(self.name_entry, "نام کامل پرسنل الزامی است.")
            return

        if not department_name:

            field_error(self.department_combo, "انتخاب دپارتمان الزامی است.")
            return

        department_id = (
            self.department_map.get(
                department_name
            )
        )

        if department_id is None:

            messagebox.showerror(
                "خطا",
                "دپارتمان انتخاب‌شده معتبر نیست.",
                parent=self,
            )

            return

        # ---------------------------------------------------------------------
        # Create
        # ---------------------------------------------------------------------

        if not self.personnel:

            ok, message, _person = (
                self.personnel_repo.create(
                    code,
                    full_name,
                    department_id,
                )
            )

        else:

            ok, message = (
                self.personnel_repo.update(
                    self.personnel.id,
                    code,
                    full_name,
                    department_id,
                )
            )

        if not ok:

            messagebox.showerror(
                "خطا",
                message,
                parent=self,
            )

            return

        self.result = True

        messagebox.showinfo(
            "موفق",
            message,
            parent=self,
        )

        self.destroy()

    # =========================================================================
    # CENTER
    # =========================================================================

    def _center(self):

        try:

            self.update_idletasks()

            width = self.winfo_width()
            height = self.winfo_height()

            screen_w = (
                self.winfo_screenwidth()
            )

            screen_h = (
                self.winfo_screenheight()
            )

            x = max(
                0,
                (
                    screen_w - width
                ) // 2,
            )

            y = max(
                0,
                (
                    screen_h - height
                ) // 2,
            )

            self.geometry(
                f"+{x}+{y}"
            )

        except Exception:
            pass