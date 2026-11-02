# views/personnel_manager_dialog.py

import tkinter as tk
from views.ui_kit import rtl_columns  # RTL (right-to-left) table columns
from tkinter import ttk, messagebox

from database.personnel_repository import PersonnelRepository
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
# COLORS
# ============================================================================

BG = GRAY_BG
PRIMARY = NAVY
PRIMARY_LIGHT = NAVY_LIGHT
CARD_BG = WHITE
BORDER = GRAY_BORDER
TEXT = TEXT_DARK
SUBTLE = TEXT_LIGHT
DANGER = RED
OK = SUCCESS


# ============================================================================
# PERSONNEL MANAGER
# ============================================================================

class PersonnelManagerDialog(tk.Toplevel):
    """
    Manager/Admin screen for:

        - Personnel CRUD
        - Department CRUD
        - Assigning a Personnel to a Department

    Personnel is deliberately separate from application Users.
    """

    def __init__(
        self,
        parent,
        session_factory,
        callback=None,
        current_user=None,
    ):
        super().__init__(parent)

        self.parent = parent
        self.session_factory = session_factory
        self.callback = callback
        self.current_user = current_user or {}

        self.result = False
        self._destroyed = False

        self._personnel = []
        self._departments = []

        self.title(
            "مدیریت پرسنل و دپارتمان‌ها"
        )

        self.configure(
            bg=BG
        )

        self.transient(parent)
        self.grab_set()

        self._setup_window()
        self._setup_styles()
        self._build_ui()
        self._load_all()

        self.protocol(
            "WM_DELETE_WINDOW",
            self._close,
        )

    # ======================================================================
    # WINDOW
    # ======================================================================

    def _setup_window(self):
        self.resizable(
            True,
            True,
        )

        screen_w = (
            self.winfo_screenwidth()
        )

        screen_h = (
            self.winfo_screenheight()
        )

        width = min(
            1050,
            max(
                820,
                int(
                    screen_w * 0.78
                ),
            ),
        )

        height = min(
            760,
            max(
                600,
                int(
                    screen_h * 0.78
                ),
            ),
        )

        self.minsize(
            760,
            520,
        )

        self.geometry(
            f"{width}x{height}"
        )

        self.update_idletasks()

        x = max(
            0,
            (
                self.winfo_screenwidth()
                - width
            ) // 2,
        )

        y = max(
            0,
            (
                self.winfo_screenheight()
                - height
            ) // 2,
        )

        self.geometry(
            f"{width}x{height}+{x}+{y}"
        )

    # ======================================================================
    # STYLE
    # ======================================================================

    def _setup_styles(self):

        style = ttk.Style(
            self
        )

        try:
            from utils.theme import ensure_theme
            ensure_theme(style)  # never switch the global ttk theme per page
        except Exception:
            pass

        style.configure(
            "Personnel.Treeview",
            background=CARD_BG,
            fieldbackground=CARD_BG,
            foreground=TEXT,
            rowheight=34,
            font=FONT_NORMAL,
        )

        style.configure(
            "Personnel.Treeview.Heading",
            background=PRIMARY,
            foreground=WHITE,
            font=FONT_NORMAL,
            relief="flat",
            padding=7,
        )

        style.map(
            "Personnel.Treeview",
            background=[
                (
                    "selected",
                    PRIMARY,
                )
            ],
            foreground=[
                (
                    "selected",
                    WHITE,
                )
            ],
        )

        style.configure(
            "Personnel.TCombobox",
            padding=5,
        )

    # ======================================================================
    # MAIN UI
    # ======================================================================

    def _build_ui(self):

        self.grid_rowconfigure(
            1,
            weight=1,
        )

        self.grid_columnconfigure(
            0,
            weight=1,
        )

        self._build_header()

        self._build_main()

        self._build_footer()

        self.bind(
            "<Escape>",
            lambda _e: self._close(),
        )

        self.bind(
            "<F5>",
            lambda _e: self._load_all(),
        )

    # ======================================================================
    # HEADER
    # ======================================================================

    def _build_header(self):

        header = tk.Frame(
            self,
            bg=PRIMARY,
            height=72,
        )

        header.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        header.grid_propagate(
            False
        )

        title_frame = tk.Frame(
            header,
            bg=PRIMARY,
        )

        title_frame.pack(
            fill="both",
            expand=True,
            padx=22,
        )

        tk.Label(
            title_frame,
            text="👷  مدیریت پرسنل و دپارتمان‌ها",
            bg=PRIMARY,
            fg=WHITE,
            font=FONT_TITLE,
            anchor="e",
        ).pack(
            side="right",
            pady=(10, 0),
        )

        tk.Label(
            title_frame,
            text=(
                "تعریف دپارتمان‌ها و تخصیص پرسنل اجرایی "
                "برای استفاده در PM و دستورکارها"
            ),
            bg=PRIMARY,
            fg=WHITE,
            font=FONT_SMALL,
            anchor="e",
        ).pack(
            side="right",
            padx=18,
            pady=(0, 8),
        )

    # ======================================================================
    # MAIN
    # ======================================================================

    def _build_main(self):

        container = tk.Frame(
            self,
            bg=BG,
        )

        container.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=15,
            pady=15,
        )

        container.grid_rowconfigure(
            0,
            weight=1,
        )

        container.grid_columnconfigure(
            0,
            weight=3,
        )

        container.grid_columnconfigure(
            1,
            weight=2,
        )

        self._build_personnel_panel(
            container
        )

        self._build_department_panel(
            container
        )

    # ======================================================================
    # PERSONNEL PANEL
    # ======================================================================

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
            column=0,
            sticky="nsew",
            padx=(0, 8),
        )

        panel = tk.Frame(
            outer,
            bg=CARD_BG,
        )

        panel.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
        )

        # --------------------------------------------------------------
        # Header
        # --------------------------------------------------------------

        top = tk.Frame(
            panel,
            bg=CARD_BG,
        )

        top.pack(
            fill="x",
            padx=15,
            pady=(15, 8),
        )

        tk.Label(
            top,
            text="👷 پرسنل اجرایی",
            bg=CARD_BG,
            fg=TEXT,
            font=FONT_HEADING,
            anchor="e",
        ).pack(
            side="right"
        )

        tk.Button(
            top,
            text="➕ افزودن پرسنل",
            command=self._add_personnel,
            bg=PRIMARY,
            fg=WHITE,
            activebackground=PRIMARY_LIGHT,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=13,
            pady=6,
        ).pack(
            side="left"
        )

        # --------------------------------------------------------------
        # Search
        # --------------------------------------------------------------

        search_frame = tk.Frame(
            panel,
            bg=BG,
        )

        search_frame.pack(
            fill="x",
            padx=15,
            pady=(0, 10),
        )

        tk.Label(
            search_frame,
            text="🔍 جستجو:",
            bg=BG,
            fg=TEXT,
            font=FONT_SMALL,
            anchor="e",
        ).pack(
            side="right",
            padx=(0, 6),
        )

        self.personnel_search_var = (
            tk.StringVar()
        )

        self.personnel_search_var.trace_add(
            "write",
            lambda *_:
                self._refresh_personnel_tree(),
        )

        search_entry = ttk.Entry(
            search_frame,
            textvariable=(
                self.personnel_search_var
            ),
            font=FONT_NORMAL,
            justify="right",
        )

        search_entry.pack(
            side="right",
            fill="x",
            expand=True,
            ipady=4,
        )

        # --------------------------------------------------------------
        # Filter Department
        # --------------------------------------------------------------

        tk.Label(
            search_frame,
            text="دپارتمان:",
            bg=BG,
            fg=TEXT,
            font=FONT_SMALL,
        ).pack(
            side="right",
            padx=(15, 5),
        )

        self.personnel_department_filter = (
            tk.StringVar(
                value="همه"
            )
        )

        self.personnel_department_combo = (
            ttk.Combobox(
                search_frame,
                textvariable=(
                    self.personnel_department_filter
                ),
                state="readonly",
                font=FONT_SMALL,
                style="Personnel.TCombobox",
                width=17,
            )
        )

        self.personnel_department_combo.pack(
            side="right",
        )

        self.personnel_department_combo.bind(
            "<<ComboboxSelected>>",
            lambda _e:
                self._refresh_personnel_tree(),
        )

        # --------------------------------------------------------------
        # Table
        # --------------------------------------------------------------

        table_frame = tk.Frame(
            panel,
            bg=CARD_BG,
        )

        table_frame.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=(0, 10),
        )

        columns = (
            "code",
            "name",
            "department",
        )

        self.personnel_tree = (
            ttk.Treeview(
                table_frame,
                columns=columns,
                show="headings",
                selectmode="browse",
                style="Personnel.Treeview",
            )
        )
        rtl_columns(self.personnel_tree)  # RTL column order

        self.personnel_tree.heading(
            "code",
            text="کد پرسنلی",
        )

        self.personnel_tree.heading(
            "name",
            text="نام و نام خانوادگی",
        )

        self.personnel_tree.heading(
            "department",
            text="دپارتمان",
        )

        self.personnel_tree.column(
            "code",
            width=120,
            minwidth=90,
            anchor="center",
        )

        self.personnel_tree.column(
            "name",
            width=210,
            minwidth=130,
            anchor="e",
        )

        self.personnel_tree.column(
            "department",
            width=170,
            minwidth=120,
            anchor="e",
        )

        vsb = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=(
                self.personnel_tree.yview
            ),
        )

        self.personnel_tree.configure(
            yscrollcommand=vsb.set
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

        table_frame.rowconfigure(
            0,
            weight=1,
        )

        table_frame.columnconfigure(
            0,
            weight=1,
        )

        self.personnel_tree.bind(
            "<Double-1>",
            lambda _e:
                self._edit_personnel(),
        )

        self.personnel_tree.bind(
            "<F2>",
            lambda _e:
                self._edit_personnel(),
        )

        self.personnel_tree.bind(
            "<Delete>",
            lambda _e:
                self._delete_personnel(),
        )

        # --------------------------------------------------------------
        # Actions
        # --------------------------------------------------------------

        action_frame = tk.Frame(
            panel,
            bg=CARD_BG,
        )

        action_frame.pack(
            fill="x",
            padx=15,
            pady=(0, 15),
        )

        tk.Button(
            action_frame,
            text="✏️ ویرایش",
            command=self._edit_personnel,
            bg=PRIMARY,
            fg=WHITE,
            activebackground=PRIMARY_LIGHT,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(
            side="right",
            padx=4,
        )

        tk.Button(
            action_frame,
            text="🗑️ حذف",
            command=self._delete_personnel,
            bg=DANGER,
            fg=WHITE,
            activebackground=DANGER,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(
            side="right",
            padx=4,
        )

        self.personnel_count_label = (
            tk.Label(
                action_frame,
                text="",
                bg=CARD_BG,
                fg=SUBTLE,
                font=FONT_SMALL,
            )
        )

        self.personnel_count_label.pack(
            side="left",
        )

    # ======================================================================
    # DEPARTMENT PANEL
    # ======================================================================

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
            column=1,
            sticky="nsew",
            padx=(8, 0),
        )

        panel = tk.Frame(
            outer,
            bg=CARD_BG,
        )

        panel.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
        )

        top = tk.Frame(
            panel,
            bg=CARD_BG,
        )

        top.pack(
            fill="x",
            padx=15,
            pady=(15, 8),
        )

        tk.Label(
            top,
            text="🏢 دپارتمان‌ها",
            bg=CARD_BG,
            fg=TEXT,
            font=FONT_HEADING,
            anchor="e",
        ).pack(
            side="right"
        )

        tk.Button(
            top,
            text="➕ افزودن دپارتمان",
            command=self._add_department,
            bg=PRIMARY,
            fg=WHITE,
            activebackground=PRIMARY_LIGHT,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=13,
            pady=6,
        ).pack(
            side="left"
        )

        # --------------------------------------------------------------
        # Department table
        # --------------------------------------------------------------

        table_frame = tk.Frame(
            panel,
            bg=CARD_BG,
        )

        table_frame.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=(0, 10),
        )

        columns = (
            "id",
            "name",
            "count",
        )

        self.department_tree = (
            ttk.Treeview(
                table_frame,
                columns=columns,
                show="headings",
                selectmode="browse",
                style="Personnel.Treeview",
            )
        )
        rtl_columns(self.department_tree)  # RTL column order

        self.department_tree.heading(
            "id",
            text="شناسه",
        )

        self.department_tree.heading(
            "name",
            text="نام دپارتمان",
        )

        self.department_tree.heading(
            "count",
            text="تعداد پرسنل",
        )

        self.department_tree.column(
            "id",
            width=70,
            minwidth=55,
            anchor="center",
        )

        self.department_tree.column(
            "name",
            width=190,
            minwidth=130,
            anchor="e",
        )

        self.department_tree.column(
            "count",
            width=100,
            minwidth=80,
            anchor="center",
        )

        vsb = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=(
                self.department_tree.yview
            ),
        )

        self.department_tree.configure(
            yscrollcommand=vsb.set
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

        table_frame.rowconfigure(
            0,
            weight=1,
        )

        table_frame.columnconfigure(
            0,
            weight=1,
        )

        self.department_tree.bind(
            "<Double-1>",
            lambda _e:
                self._edit_department(),
        )

        self.department_tree.bind(
            "<F2>",
            lambda _e:
                self._edit_department(),
        )

        self.department_tree.bind(
            "<Delete>",
            lambda _e:
                self._delete_department(),
        )

        # --------------------------------------------------------------
        # Department actions
        # --------------------------------------------------------------

        action_frame = tk.Frame(
            panel,
            bg=CARD_BG,
        )

        action_frame.pack(
            fill="x",
            padx=15,
            pady=(0, 15),
        )

        tk.Button(
            action_frame,
            text="✏️ ویرایش",
            command=self._edit_department,
            bg=PRIMARY,
            fg=WHITE,
            activebackground=PRIMARY_LIGHT,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(
            side="right",
            padx=4,
        )

        tk.Button(
            action_frame,
            text="🗑️ حذف",
            command=self._delete_department,
            bg=DANGER,
            fg=WHITE,
            activebackground=DANGER,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_SMALL,
            padx=14,
            pady=6,
        ).pack(
            side="right",
            padx=4,
        )

        self.department_count_label = (
            tk.Label(
                action_frame,
                text="",
                bg=CARD_BG,
                fg=SUBTLE,
                font=FONT_SMALL,
            )
        )

        self.department_count_label.pack(
            side="left",
        )

    # ======================================================================
    # FOOTER
    # ======================================================================

    def _build_footer(self):

        footer = tk.Frame(
            self,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            height=62,
        )

        footer.grid(
            row=2,
            column=0,
            sticky="ew",
        )

        footer.grid_propagate(
            False
        )

        tk.Button(
            footer,
            text="بستن",
            command=self._close,
            bg=BG,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=25,
            pady=7,
        ).pack(
            side="left",
            padx=15,
            pady=10,
        )

        tk.Label(
            footer,
            text=(
                "دپارتمان هنگام ایجاد PM یا دستورکار انتخاب می‌شود؛ "
                "پرسنل هنگام ثبت انجام کار انتخاب می‌شود."
            ),
            bg=CARD_BG,
            fg=SUBTLE,
            font=FONT_SMALL,
            anchor="e",
        ).pack(
            side="right",
            padx=15,
        )

    # ======================================================================
    # DATA LOAD
    # ======================================================================

    def _load_all(self):

        if self._destroyed:
            return

        try:

            repo = PersonnelRepository(
                self.session_factory
            )

            self._departments = (
                repo.get_departments()
            )

            self._personnel = (
                repo.get_all(
                    only_with_department=False
                )
            )

            self._refresh_department_filter()

            self._refresh_department_tree()

            self._refresh_personnel_tree()

        except Exception as exc:

            messagebox.showerror(
                "خطا",
                (
                    "خطا در بارگذاری پرسنل و "
                    f"دپارتمان‌ها:\n\n{exc}"
                ),
                parent=self,
            )

    # ======================================================================
    # DEPARTMENT FILTER
    # ======================================================================

    def _refresh_department_filter(self):

        values = [
            "همه"
        ]

        values.extend(
            [
                department.name
                for department in (
                    self._departments
                )
                if getattr(
                    department,
                    "name",
                    None,
                )
            ]
        )

        current = (
            self.personnel_department_filter.get()
        )

        self.personnel_department_combo[
            "values"
        ] = values

        if current not in values:
            self.personnel_department_filter.set(
                "همه"
            )

    # ======================================================================
    # PERSONNEL TREE
    # ======================================================================

    def _refresh_personnel_tree(
        self,
    ):

        if not hasattr(
            self,
            "personnel_tree",
        ):
            return

        self.personnel_tree.delete(
            *self.personnel_tree.get_children()
        )

        keyword = (
            self.personnel_search_var
            .get()
            .strip()
            .lower()
        )

        department_filter = (
            self.personnel_department_filter
            .get()
        )

        rows = []

        for person in (
            self._personnel
        ):

            name = (
                getattr(
                    person,
                    "full_name",
                    None,
                )
                or ""
            )

            code = (
                getattr(
                    person,
                    "personnel_code",
                    None,
                )
                or ""
            )

            department = getattr(
                person,
                "department",
                None,
            )

            department_name = (
                getattr(
                    department,
                    "name",
                    None,
                )
                or ""
            )

            # Search.
            if keyword:

                searchable = (
                    f"{name} "
                    f"{code} "
                    f"{department_name}"
                ).lower()

                if keyword not in searchable:
                    continue

            # Department filter.
            if (
                department_filter
                != "همه"
                and department_name
                != department_filter
            ):
                continue

            rows.append(
                (
                    person,
                    name,
                    code,
                    department_name,
                )
            )

        for (
            person,
            name,
            code,
            department_name,
        ) in rows:

            self.personnel_tree.insert(
                "",
                "end",
                iid=str(
                    person.id
                ),
                values=(
                    code,
                    name,
                    department_name
                    or "—",
                ),
            )

        if hasattr(
            self,
            "personnel_count_label",
        ):

            self.personnel_count_label.configure(
                text=(
                    f"تعداد: {len(rows)}"
                )
            )

    # ======================================================================
    # DEPARTMENT TREE
    # ======================================================================

    def _refresh_department_tree(
        self,
    ):

        self.department_tree.delete(
            *self.department_tree.get_children()
        )

        repo = PersonnelRepository(
            self.session_factory
        )

        for department in (
            self._departments
        ):

            count = (
                repo.count_by_department(
                    department.id
                )
            )

            self.department_tree.insert(
                "",
                "end",
                iid=str(
                    department.id
                ),
                values=(
                    department.id,
                    department.name,
                    count,
                ),
            )

        if hasattr(
            self,
            "department_count_label",
        ):

            self.department_count_label.configure(
                text=(
                    f"تعداد دپارتمان‌ها: "
                    f"{len(self._departments)}"
                )
            )

    # ======================================================================
    # PERSONNEL SELECTION
    # ======================================================================

    def _selected_personnel_id(
        self,
    ):

        selection = (
            self.personnel_tree
            .selection()
        )

        if not selection:

            messagebox.showwarning(
                "انتخاب",
                "لطفاً یک پرسنل را انتخاب کنید.",
                parent=self,
            )

            return None

        try:
            return int(
                selection[0]
            )
        except (
            TypeError,
            ValueError,
        ):

            return None

    # ======================================================================
    # DEPARTMENT SELECTION
    # ======================================================================

    def _selected_department_id(
        self,
    ):

        selection = (
            self.department_tree
            .selection()
        )

        if not selection:

            messagebox.showwarning(
                "انتخاب",
                "لطفاً یک دپارتمان را انتخاب کنید.",
                parent=self,
            )

            return None

        try:
            return int(
                selection[0]
            )
        except (
            TypeError,
            ValueError,
        ):

            return None

    # ======================================================================
    # ADD PERSONNEL
    # ======================================================================

    def _add_personnel(self):

        self._open_personnel_form()

    # ======================================================================
    # EDIT PERSONNEL
    # ======================================================================

    def _edit_personnel(self):

        personnel_id = (
            self._selected_personnel_id()
        )

        if personnel_id is None:
            return

        repo = PersonnelRepository(
            self.session_factory
        )

        person = repo.get_by_id(
            personnel_id
        )

        if not person:

            messagebox.showerror(
                "خطا",
                "پرسنل مورد نظر یافت نشد.",
                parent=self,
            )

            return

        self._open_personnel_form(
            person
        )

    # ======================================================================
    # PERSONNEL FORM
    # ======================================================================

    def _open_personnel_form(
        self,
        person=None,
    ):

        dialog = tk.Toplevel(
            self
        )

        dialog.title(
            (
                "ویرایش پرسنل"
                if person
                else "افزودن پرسنل جدید"
            )
        )

        dialog.configure(
            bg=BG
        )

        dialog.resizable(
            True,
            True
        )

        dialog.transient(
            self
        )

        dialog.grab_set()

        width = 500
        height = 460

        screen_w = (
            dialog.winfo_screenwidth()
        )

        screen_h = (
            dialog.winfo_screenheight()
        )

        width = min(
            width,
            max(
                420,
                screen_w - 80,
            ),
        )

        height = min(
            height,
            max(
                380,
                screen_h - 100,
            ),
        )

        dialog.geometry(
            f"{width}x{height}"
        )

        dialog.update_idletasks()

        x = (
            screen_w - width
        ) // 2

        y = (
            screen_h - height
        ) // 2

        dialog.geometry(
            f"{width}x{height}+{x}+{y}"
        )

        dialog.grid_rowconfigure(
            1,
            weight=1,
        )

        dialog.grid_columnconfigure(
            0,
            weight=1,
        )

        # --------------------------------------------------------------
        # Header
        # --------------------------------------------------------------

        header = tk.Frame(
            dialog,
            bg=PRIMARY,
            height=58,
        )

        header.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        header.grid_propagate(
            False
        )

        tk.Label(
            header,
            text=(
                "✏️  ویرایش پرسنل"
                if person
                else "➕  افزودن پرسنل جدید"
            ),
            bg=PRIMARY,
            fg=WHITE,
            font=FONT_HEADING,
        ).pack(
            expand=True
        )

        # --------------------------------------------------------------
        # Form
        # --------------------------------------------------------------

        form = tk.Frame(
            dialog,
            bg=CARD_BG,
        )

        form.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=15,
            pady=15,
        )

        form.grid_columnconfigure(
            0,
            weight=1,
        )

        tk.Label(
            form,
            text="نام و نام خانوادگی *",
            bg=CARD_BG,
            fg=TEXT,
            font=FONT_NORMAL,
            anchor="e",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(4, 4),
        )

        name_var = tk.StringVar()

        name_entry = ttk.Entry(
            form,
            textvariable=name_var,
            font=FONT_NORMAL,
            justify="right",
        )

        name_entry.grid(
            row=1,
            column=0,
            sticky="ew",
            ipady=5,
            pady=(0, 12),
        )

        tk.Label(
            form,
            text="شماره پرسنلی",
            bg=CARD_BG,
            fg=TEXT,
            font=FONT_NORMAL,
            anchor="e",
        ).grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(4, 4),
        )

        code_var = tk.StringVar()

        code_entry = ttk.Entry(
            form,
            textvariable=code_var,
            font=FONT_NORMAL,
            justify="right",
        )

        code_entry.grid(
            row=3,
            column=0,
            sticky="ew",
            ipady=5,
            pady=(0, 12),
        )

        tk.Label(
            form,
            text="دپارتمان *",
            bg=CARD_BG,
            fg=TEXT,
            font=FONT_NORMAL,
            anchor="e",
        ).grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(4, 4),
        )

        department_var = tk.StringVar()

        department_combo = ttk.Combobox(
            form,
            textvariable=department_var,
            state="readonly",
            font=FONT_NORMAL,
            justify="right",
            style="Personnel.TCombobox",
        )

        department_items = []

        department_map = {}

        for department in (
            self._departments
        ):

            display = (
                f"{department.name}"
            )

            department_items.append(
                display
            )

            department_map[
                display
            ] = department.id

        department_combo[
            "values"
        ] = department_items

        department_combo.grid(
            row=5,
            column=0,
            sticky="ew",
            ipady=5,
            pady=(0, 15),
        )

        if person:

            name_var.set(
                getattr(
                    person,
                    "full_name",
                    "",
                )
            )

            code_var.set(
                getattr(
                    person,
                    "personnel_code",
                    "",
                )
                or ""
            )

            existing_department = (
                getattr(
                    person,
                    "department",
                    None,
                )
            )

            existing_name = (
                getattr(
                    existing_department,
                    "name",
                    "",
                )
                or ""
            )

            if existing_name in (
                department_items
            ):

                department_var.set(
                    existing_name
                )

        # --------------------------------------------------------------
        # Footer
        # --------------------------------------------------------------

        footer = tk.Frame(
            dialog,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            height=66,
        )

        footer.grid(
            row=2,
            column=0,
            sticky="ew",
        )

        footer.grid_propagate(
            False
        )

        def save():

            name = (
                name_var
                .get()
                .strip()
            )

            code = (
                code_var
                .get()
                .strip()
                or None
            )

            department_name = (
                department_var
                .get()
                .strip()
            )

            if not name:

                messagebox.showwarning(
                    "ناقص",
                    "نام و نام خانوادگی الزامی است.",
                    parent=dialog,
                )

                return

            if not department_name:

                messagebox.showwarning(
                    "ناقص",
                    "لطفاً دپارتمان را انتخاب کنید.",
                    parent=dialog,
                )

                return

            department_id = (
                department_map.get(
                    department_name
                )
            )

            if department_id is None:

                messagebox.showerror(
                    "خطا",
                    "دپارتمان انتخاب‌شده معتبر نیست.",
                    parent=dialog,
                )

                return

            repo = PersonnelRepository(
                self.session_factory
            )

            if person:

                ok, msg = (
                    repo.update(
                        person.id,
                        name,
                        department_id,
                        code,
                    )
                )

            else:

                ok, msg, _ = (
                    repo.create(
                        name,
                        department_id,
                        code,
                    )
                )

            if not ok:

                messagebox.showerror(
                    "خطا",
                    msg,
                    parent=dialog,
                )

                return

            self.result = True

            dialog.destroy()

            self._load_all()

            self._notify_parent()

        tk.Button(
            footer,
            text="انصراف",
            command=dialog.destroy,
            bg=BG,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=22,
            pady=7,
        ).pack(
            side="left",
            padx=12,
            pady=11,
        )

        tk.Button(
            footer,
            text="💾 ذخیره",
            command=save,
            bg=OK,
            fg=WHITE,
            activebackground=OK,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=24,
            pady=7,
        ).pack(
            side="right",
            padx=12,
            pady=11,
        )

        name_entry.focus_set()

        dialog.bind(
            "<Escape>",
            lambda _e: dialog.destroy(),
        )

        dialog.bind(
            "<Control-s>",
            lambda _e: save(),
        )

    # ======================================================================
    # DELETE PERSONNEL
    # ======================================================================

    def _delete_personnel(self):

        personnel_id = (
            self._selected_personnel_id()
        )

        if personnel_id is None:
            return

        repo = PersonnelRepository(
            self.session_factory
        )

        person = repo.get_by_id(
            personnel_id
        )

        if not person:
            return

        name = (
            getattr(
                person,
                "full_name",
                "",
            )
            or "پرسنل"
        )

        confirmed = (
            messagebox.askyesno(
                "تأیید حذف",
                (
                    f"آیا از حذف پرسنل «{name}» "
                    "اطمینان دارید؟\n\n"
                    "در صورت وجود سابقه انجام PM یا "
                    "دستورکار، حذف انجام نخواهد شد."
                ),
                parent=self,
            )
        )

        if not confirmed:
            return

        ok, msg = (
            repo.delete(
                personnel_id
            )
        )

        if not ok:

            messagebox.showwarning(
                "امکان حذف وجود ندارد",
                msg,
                parent=self,
            )

            return

        self.result = True

        self._load_all()

        self._notify_parent()

        messagebox.showinfo(
            "موفق",
            msg,
            parent=self,
        )

    # ======================================================================
    # ADD DEPARTMENT
    # ======================================================================

    def _add_department(self):

        self._open_department_form()

    # ======================================================================
    # EDIT DEPARTMENT
    # ======================================================================

    def _edit_department(self):

        department_id = (
            self._selected_department_id()
        )

        if department_id is None:
            return

        repo = PersonnelRepository(
            self.session_factory
        )

        department = (
            repo.get_department_by_id(
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

        self._open_department_form(
            department
        )

    # ======================================================================
    # DEPARTMENT FORM
    # ======================================================================

    def _open_department_form(
        self,
        department=None,
    ):

        dialog = tk.Toplevel(
            self
        )

        dialog.title(
            (
                "ویرایش دپارتمان"
                if department
                else "افزودن دپارتمان"
            )
        )

        dialog.configure(
            bg=BG
        )

        dialog.resizable(
            False,
            False
        )

        dialog.transient(
            self
        )

        dialog.grab_set()

        width = 440
        height = 250

        screen_w = (
            dialog.winfo_screenwidth()
        )

        screen_h = (
            dialog.winfo_screenheight()
        )

        x = (
            screen_w - width
        ) // 2

        y = (
            screen_h - height
        ) // 2

        dialog.geometry(
            f"{width}x{height}+{x}+{y}"
        )

        header = tk.Frame(
            dialog,
            bg=PRIMARY,
            height=56,
        )

        header.pack(
            fill="x"
        )

        header.pack_propagate(
            False
        )

        tk.Label(
            header,
            text=(
                "✏️  ویرایش دپارتمان"
                if department
                else "➕  افزودن دپارتمان"
            ),
            bg=PRIMARY,
            fg=WHITE,
            font=FONT_HEADING,
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
            text="نام دپارتمان *",
            bg=CARD_BG,
            fg=TEXT,
            font=FONT_NORMAL,
            anchor="e",
        ).pack(
            fill="x",
            pady=(0, 4),
        )

        name_var = tk.StringVar()

        if department:

            name_var.set(
                getattr(
                    department,
                    "name",
                    "",
                )
            )

        entry = ttk.Entry(
            body,
            textvariable=name_var,
            font=FONT_NORMAL,
            justify="right",
        )

        entry.pack(
            fill="x",
            ipady=5,
            pady=(0, 15),
        )

        def save():

            name = (
                name_var
                .get()
                .strip()
            )

            if not name:

                messagebox.showwarning(
                    "ناقص",
                    "نام دپارتمان الزامی است.",
                    parent=dialog,
                )

                return

            repo = PersonnelRepository(
                self.session_factory
            )

            if department:

                ok, msg = (
                    repo.update_department(
                        department.id,
                        name,
                    )
                )

            else:

                ok, msg, _ = (
                    repo.create_department(
                        name
                    )
                )

            if not ok:

                messagebox.showerror(
                    "خطا",
                    msg,
                    parent=dialog,
                )

                return

            self.result = True

            dialog.destroy()

            self._load_all()

            self._notify_parent()

        button_row = tk.Frame(
            body,
            bg=CARD_BG,
        )

        button_row.pack(
            fill="x"
        )

        tk.Button(
            button_row,
            text="انصراف",
            command=dialog.destroy,
            bg=BG,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=22,
            pady=7,
        ).pack(
            side="left"
        )

        tk.Button(
            button_row,
            text="💾 ذخیره",
            command=save,
            bg=OK,
            fg=WHITE,
            activebackground=OK,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=24,
            pady=7,
        ).pack(
            side="right"
        )

        entry.focus_set()

        dialog.bind(
            "<Escape>",
            lambda _e: dialog.destroy(),
        )

        dialog.bind(
            "<Return>",
            lambda _e: save(),
        )

    # ======================================================================
    # DELETE DEPARTMENT
    # ======================================================================

    def _delete_department(self):

        department_id = (
            self._selected_department_id()
        )

        if department_id is None:
            return

        repo = PersonnelRepository(
            self.session_factory
        )

        department = (
            repo.get_department_by_id(
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
            or "دپارتمان"
        )

        confirmed = (
            messagebox.askyesno(
                "تأیید حذف",
                (
                    f"آیا از حذف دپارتمان «{name}» "
                    "اطمینان دارید؟\n\n"
                    "دپارتمانی که در پرسنل، PM یا "
                    "دستورکارها استفاده شده باشد حذف نخواهد شد."
                ),
                parent=self,
            )
        )

        if not confirmed:
            return

        ok, msg = (
            repo.delete_department(
                department_id
            )
        )

        if not ok:

            messagebox.showwarning(
                "امکان حذف وجود ندارد",
                msg,
                parent=self,
            )

            return

        self.result = True

        self._load_all()

        self._notify_parent()

        messagebox.showinfo(
            "موفق",
            msg,
            parent=self,
        )

    # ======================================================================
    # PARENT CALLBACK
    # ======================================================================

    def _notify_parent(self):

        if not self.callback:
            return

        try:
            self.callback()
        except Exception as exc:
            print(
                f"Personnel manager callback error: "
                f"{exc}"
            )

    # ======================================================================
    # CLOSE
    # ======================================================================

    def _close(self):

        if self._destroyed:
            return

        self._destroyed = True

        try:
            self.grab_release()
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass


# ============================================================================
# OPTIONAL FUNCTION
# ============================================================================

def open_personnel_manager(
    parent,
    session_factory,
    callback=None,
    current_user=None,
):
    """
    Convenience launcher used by UsersView or MainView.
    """

    dialog = PersonnelManagerDialog(
        parent,
        session_factory,
        callback=callback,
        current_user=current_user,
    )

    parent.wait_window(
        dialog
    )

    return dialog.result