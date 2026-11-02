# views/emergency_work_order_dialog.py
"""
PM System - Emergency Work Order Dialog
========================================

Emergency work-order creation.

Required:
    - Equipment
    - Department
    - Title

Workflow:
    Work Order creation:
        Equipment
        Department
        Title
        Scheduled date/time is set automatically for Emergency WO

    Finish request:
        Personnel is selected later from Personnel belonging to the
        exact Work Order department.

Important:
    No User technician is selected or assigned here.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from views.ux import field_error

from database.work_order_repository import WorkOrderRepository
from database.work_order import WorkOrder
from database.equipment_repository import EquipmentRepository
from database.personnel_repository import PersonnelRepository
from database.db import SessionLocal
from auth.auth_manager import AuthManager

from views.searchable_combobox import SearchableCombobox
from views.jalali_date_entry import JalaliDateEntry

from utils.theme import (
    NAVY,
    NAVY_LIGHT,
    WHITE,
    RED,
    GRAY_BG,
    GRAY_BORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    FONT_TITLE,
    FONT_NORMAL,
    FONT_SMALL,
)
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


# ============================================================================
# THEME
# ============================================================================

BG = GRAY_BG
CARD_BG = WHITE
CARD_BORDER = GRAY_BORDER


# ============================================================================
# DIALOG
# ============================================================================

class EmergencyWorkOrderDialog(tk.Toplevel):

    def __init__(
        self,
        parent,
        equipment_repo=None,
        preselected_equipment=None,
    ):
        super().__init__(parent)

        self.parent = parent

        self.equipment_repo = (
            equipment_repo
            or EquipmentRepository(
                SessionLocal
            )
        )

        self.personnel_repo = (
            PersonnelRepository(
                SessionLocal
            )
        )

        self.preselected = (
            preselected_equipment
        )

        self.result = False

        self.eq_map = {}
        self.department_map = {}

        self.selected_equipment_id = None

        self.title(
            "ثبت دستور کار اضطراری"
        )

        self.configure(
            bg=BG
        )

        self.resizable(
            True,
            True,
        )

        self.minsize(
            600,
            650,
        )

        self.geometry(
            "650x760"
        )

        self.transient(parent)
        self.grab_set()

        self.protocol(
            "WM_DELETE_WINDOW",
            self.destroy,
        )

        self.bind(
            "<Escape>",
            lambda _:
            self.destroy(),
        )

        self.bind(
            "<Control-s>",
            lambda _:
            self._save(),
        )

        self._build_ui()

        self.after(
            100,
            self._center_window,
        )

    # =========================================================================
    # WINDOW
    # =========================================================================

    def _center_window(self):

        try:

            self.update_idletasks()

            width = min(
                self.winfo_width(),
                self.winfo_screenwidth() - 60,
            )

            height = min(
                self.winfo_height(),
                self.winfo_screenheight() - 70,
            )

            width = max(
                600,
                width,
            )

            height = max(
                650,
                height,
            )

            x = max(
                10,
                (
                    self.winfo_screenwidth()
                    - width
                ) // 2,
            )

            y = max(
                10,
                (
                    self.winfo_screenheight()
                    - height
                ) // 2,
            )

            self.geometry(
                f"{width}x{height}+{x}+{y}"
            )

        except Exception:
            pass

    # =========================================================================
    # UI
    # =========================================================================

    def _build_ui(self):

        # ---------------------------------------------------------------------
        # Header
        # ---------------------------------------------------------------------

        header = tk.Frame(
            self,
            bg=NAVY,
            height=58,
        )

        header.pack(
            fill="x"
        )

        header.pack_propagate(
            False
        )

        tk.Label(
            header,
            text="🚨  دستور کار اضطراری",
            font=FONT_TITLE,
            bg=NAVY,
            fg=WHITE,
        ).pack(
            expand=True
        )

        # ---------------------------------------------------------------------
        # Scrollable body
        # ---------------------------------------------------------------------

        content = tk.Frame(
            self,
            bg=BG,
        )

        content.pack(
            fill="both",
            expand=True,
        )

        self.canvas = tk.Canvas(
            content,
            bg=BG,
            highlightthickness=0,
            bd=0,
        )

        self.scrollbar = ttk.Scrollbar(
            content,
            orient="vertical",
            command=self.canvas.yview,
        )

        self.scrollable = tk.Frame(
            self.canvas,
            bg=BG,
        )

        self.scroll_window = (
            self.canvas.create_window(
                (0, 0),
                window=self.scrollable,
                anchor="nw",
            )
        )

        self.canvas.configure(
            yscrollcommand=(
                self.scrollbar.set
            )
        )

        self.scrollable.bind(
            "<Configure>",
            self._on_scrollable_configure,
        )

        self.canvas.bind(
            "<Configure>",
            self._on_canvas_configure,
        )

        self.canvas.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(8, 0),
            pady=8,
        )

        self.scrollbar.pack(
            side="right",
            fill="y",
            padx=(0, 8),
            pady=8,
        )

        self.canvas.bind(
            "<MouseWheel>",
            self._on_mousewheel,
            add="+",
        )

        self.canvas.bind(
            "<Button-4>",
            lambda _e:
            self.canvas.yview_scroll(
                -3,
                "units",
            ),
            add="+",
        )

        self.canvas.bind(
            "<Button-5>",
            lambda _e:
            self.canvas.yview_scroll(
                3,
                "units",
            ),
            add="+",
        )

        # ---------------------------------------------------------------------
        # Main card
        # ---------------------------------------------------------------------

        card_border = tk.Frame(
            self.scrollable,
            bg=CARD_BORDER,
        )

        card_border.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=15,
        )

        main = tk.Frame(
            card_border,
            bg=CARD_BG,
            padx=24,
            pady=22,
        )

        main.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
        )

        main.grid_columnconfigure(
            1,
            weight=1,
        )

        row = 0

        # =====================================================================
        # EQUIPMENT
        # =====================================================================

        tk.Label(
            main,
            text="تجهیز *:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).grid(
            row=row,
            column=0,
            sticky="e",
            padx=8,
            pady=8,
        )

        if self.preselected:

            equipment_name = (
                self.preselected.get(
                    "name",
                    "",
                )
                or "تجهیز انتخاب‌شده"
            )

            self.selected_equipment_id = (
                self.preselected.get(
                    "id"
                )
            )

            tk.Label(
                main,
                text=equipment_name,
                font=FONT_NORMAL,
                bg=CARD_BG,
                fg=TEXT_DARK,
                anchor="e",
            ).grid(
                row=row,
                column=1,
                sticky="ew",
                padx=8,
                pady=8,
            )

        else:

            self.equipment_combo = (
                SearchableCombobox(
                    main,
                    width=42,
                    state="normal",
                    font=FONT_NORMAL,
                )
            )

            self.equipment_combo.grid(
                row=row,
                column=1,
                sticky="ew",
                padx=8,
                pady=8,
            )

            self._load_equipment()

        row += 1

        # =====================================================================
        # DEPARTMENT
        # =====================================================================

        tk.Label(
            main,
            text="دپارتمان مسئول *:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).grid(
            row=row,
            column=0,
            sticky="e",
            padx=8,
            pady=8,
        )

        department_frame = tk.Frame(
            main,
            bg=CARD_BG,
        )

        department_frame.grid(
            row=row,
            column=1,
            sticky="ew",
            padx=8,
            pady=8,
        )

        department_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self.department_var = (
            tk.StringVar()
        )

        self.department_combo = (
            ttk.Combobox(
                department_frame,
                textvariable=(
                    self.department_var
                ),
                state="readonly",
                font=FONT_NORMAL,
                justify="right",
            )
        )

        self.department_combo.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        self._load_departments()

        tk.Label(
            department_frame,
            text=(
                "دپارتمان مسئول انجام کار را انتخاب کنید."
            ),
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            anchor="e",
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(4, 0),
        )

        row += 1

        # =====================================================================
        # TITLE
        # =====================================================================

        tk.Label(
            main,
            text="عنوان *:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).grid(
            row=row,
            column=0,
            sticky="ne",
            padx=8,
            pady=8,
        )

        self.title_entry = ttk.Entry(
            main,
            font=FONT_NORMAL,
            justify="right",
        )

        self.title_entry.grid(
            row=row,
            column=1,
            sticky="ew",
            padx=8,
            pady=8,
        )

        row += 1

        # =====================================================================
        # DESCRIPTION
        # =====================================================================

        tk.Label(
            main,
            text="شرح:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).grid(
            row=row,
            column=0,
            sticky="ne",
            padx=8,
            pady=8,
        )

        self.desc_text = tk.Text(
            main,
            font=FONT_NORMAL,
            height=5,
            wrap="word",
            relief="solid",
            bd=1,
        )

        self.desc_text.grid(
            row=row,
            column=1,
            sticky="ew",
            padx=8,
            pady=8,
        )

        row += 1

        # =====================================================================
        # PRIORITY
        # =====================================================================

        tk.Label(
            main,
            text="اولویت:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).grid(
            row=row,
            column=0,
            sticky="e",
            padx=8,
            pady=8,
        )

        priority_frame = tk.Frame(
            main,
            bg=CARD_BG,
        )

        priority_frame.grid(
            row=row,
            column=1,
            sticky="ew",
            padx=8,
            pady=8,
        )

        self.priority_var = (
            tk.StringVar(
                value="URGENT"
            )
        )

        for text, value in (
            ("کم", "LOW"),
            ("متوسط", "MEDIUM"),
            ("بالا", "HIGH"),
            ("فوری", "URGENT"),
        ):

            tk.Radiobutton(
                priority_frame,
                text=text,
                variable=self.priority_var,
                value=value,
                bg=CARD_BG,
                fg=TEXT_DARK,
                activebackground=CARD_BG,
                selectcolor=CARD_BG,
                font=FONT_NORMAL,
            ).pack(
                side="right",
                padx=10,
            )

        row += 1

        # =====================================================================
        # DEADLINE
        # =====================================================================

        tk.Label(
            main,
            text="تاریخ سررسید:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).grid(
            row=row,
            column=0,
            sticky="e",
            padx=8,
            pady=8,
        )

        self.deadline_date = (
            JalaliDateEntry(
                main,
                width=18,
            )
        )

        self.deadline_date.grid(
            row=row,
            column=1,
            sticky="w",
            padx=8,
            pady=8,
        )

        self.deadline_date.set_date(
            tehran_now().date()
        )

        row += 1

        # =====================================================================
        # REPORTER
        # =====================================================================

        current_user = (
            AuthManager.get_current_user()
        )

        reporter_name = (
            getattr(
                current_user,
                "full_name",
                None,
            )
            or getattr(
                current_user,
                "username",
                None,
            )
            or "کاربر فعلی"
        )

        tk.Label(
            main,
            text="گزارش‌دهنده:",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).grid(
            row=row,
            column=0,
            sticky="e",
            padx=8,
            pady=8,
        )

        tk.Label(
            main,
            text=reporter_name,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_DARK,
            anchor="e",
        ).grid(
            row=row,
            column=1,
            sticky="ew",
            padx=8,
            pady=8,
        )

        row += 1

        # =====================================================================
        # BUTTONS
        # =====================================================================

        button_frame = tk.Frame(
            main,
            bg=CARD_BG,
        )

        button_frame.grid(
            row=row,
            column=0,
            columnspan=2,
            pady=(20, 5),
        )

        tk.Button(
            button_frame,
            text="انصراف",
            command=self.destroy,
            bg=NAVY_LIGHT,
            fg=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=24,
            pady=8,
        ).pack(
            side="left",
            padx=6,
        )

        tk.Button(
            button_frame,
            text="🚨 ثبت دستور کار",
            command=self._save,
            bg=RED,
            fg=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=24,
            pady=8,
        ).pack(
            side="left",
            padx=6,
        )

        self.after_idle(
            lambda:
            self.title_entry.focus_set()
        )

    # =========================================================================
    # SCROLLING
    # =========================================================================

    def _on_scrollable_configure(
        self,
        _event=None,
    ):

        try:

            self.canvas.configure(
                scrollregion=(
                    self.canvas.bbox(
                        "all"
                    )
                )
            )

        except Exception:
            pass

    def _on_canvas_configure(
        self,
        _event=None,
    ):

        try:

            self.canvas.itemconfigure(
                self.scroll_window,
                width=self.canvas.winfo_width(),
            )

        except Exception:
            pass

    def _on_mousewheel(
        self,
        event,
    ):

        try:

            if event.delta == 0:
                return

            units = int(
                -event.delta / 120
            )

            if units == 0:

                units = (
                    -1
                    if event.delta > 0
                    else 1
                )

            self.canvas.yview_scroll(
                units,
                "units",
            )

        except Exception:
            pass

    # =========================================================================
    # EQUIPMENT
    # =========================================================================

    def _load_equipment(self):

        try:

            equipment_list = (
                self.equipment_repo
                .get_all_equipment()
                or []
            )

        except Exception as exc:

            equipment_list = []

            messagebox.showwarning(
                "هشدار",
                (
                    "بارگذاری تجهیزات انجام نشد:\n\n"
                    f"{exc}"
                ),
                parent=self,
            )

        self.eq_map = {}

        display_values = []

        for equipment in equipment_list:

            if not isinstance(
                equipment,
                dict,
            ):
                continue

            equipment_id = (
                equipment.get("id")
            )

            if equipment_id is None:
                continue

            code = str(
                equipment.get(
                    "code"
                )
                or ""
            ).strip()

            name = str(
                equipment.get(
                    "name"
                )
                or ""
            ).strip()

            if code and name:
                display = (
                    f"{code} - {name}"
                )
            elif name:
                display = name
            elif code:
                display = code
            else:
                display = (
                    f"تجهیز #{equipment_id}"
                )

            self.eq_map[
                display
            ] = equipment_id

            display_values.append(
                display
            )

        try:

            self.equipment_combo.set_completion_list(
                display_values
            )

            self.equipment_combo.set("")

        except Exception:
            pass

    # =========================================================================
    # DEPARTMENTS
    # =========================================================================

    def _load_departments(self):

        try:

            departments = (
                self.personnel_repo
                .get_departments()
                or []
            )

        except Exception as exc:

            departments = []

            messagebox.showwarning(
                "هشدار",
                (
                    "بارگذاری دپارتمان‌ها انجام نشد:\n\n"
                    f"{exc}"
                ),
                parent=self,
            )

        department_pairs = []

        for department in departments:

            # Current/legacy repository may return a Department object.
            if isinstance(
                department,
                str,
            ):

                # A department name without its database ID cannot be used
                # safely for work_orders.department_id.
                continue

            name = (
                getattr(
                    department,
                    "name",
                    None,
                )
                or ""
            ).strip()

            department_id = getattr(
                department,
                "id",
                None,
            )

            if not name:
                continue

            if department_id is None:
                continue

            department_pairs.append(
                (
                    name,
                    department_id,
                )
            )

        # Remove duplicate department names while preserving IDs.
        department_map = {}

        for name, department_id in department_pairs:
            department_map[name] = department_id

        self.department_map = dict(
            sorted(
                department_map.items(),
                key=lambda item: item[0],
            )
        )

        self.department_combo[
            "values"
        ] = list(
            self.department_map.keys()
        )

        try:
            self.department_combo.set("")
        except Exception:
            pass

    # =========================================================================
    # SAVE
    # =========================================================================

    def _save(self):

        # ---------------------------------------------------------------------
        # Equipment
        # ---------------------------------------------------------------------

        if self.preselected:

            equipment_id = (
                self.selected_equipment_id
            )

            if equipment_id is None:

                messagebox.showerror(
                    "خطا",
                    "تجهیز انتخاب‌شده معتبر نیست.",
                    parent=self,
                )

                return

        else:

            selection = (
                self.equipment_combo
                .get()
                .strip()
            )

            if not selection:

                field_error(self.equipment_combo, "انتخاب تجهیز الزامی است.")

                return

            equipment_id = (
                self.eq_map.get(
                    selection
                )
            )

            if equipment_id is None:

                field_error(self.equipment_combo, "تجهیز انتخاب‌شده معتبر نیست.")

                return

        # ---------------------------------------------------------------------
        # Department
        # ---------------------------------------------------------------------

        department_name = (
            self.department_var
            .get()
            .strip()
        )

        if not department_name:

            field_error(self.department_combo, "انتخاب دپارتمان الزامی است.")

            return

        if (
            department_name
            not in self.department_map
        ):

            field_error(self.department_combo, "دپارتمان انتخاب‌شده معتبر نیست.")

            return

        department_id = (
            self.department_map.get(
                department_name
            )
        )

        if department_id is None:

            field_error(self.department_combo, "شناسه دپارتمان انتخاب‌شده معتبر نیست.")

            return

        # ---------------------------------------------------------------------
        # Title
        # ---------------------------------------------------------------------

        title = (
            self.title_entry
            .get()
            .strip()
        )

        if not title:

            field_error(self.title_entry, "عنوان دستور کار الزامی است.")

            return

        # ---------------------------------------------------------------------
        # Description
        # ---------------------------------------------------------------------

        description = (
            self.desc_text
            .get(
                "1.0",
                tk.END,
            )
            .strip()
        )

        # ---------------------------------------------------------------------
        # Priority
        # ---------------------------------------------------------------------

        priority = (
            self.priority_var.get()
            or "URGENT"
        )

        # ---------------------------------------------------------------------
        # Deadline
        # ---------------------------------------------------------------------

        try:

            deadline_value = (
                self.deadline_date
                .get_date()
            )

        except Exception:

            deadline_value = None

        # ---------------------------------------------------------------------
        # Current reporter
        # ---------------------------------------------------------------------

        current_user = (
            AuthManager.get_current_user()
        )

        if not current_user:

            messagebox.showerror(
                "خطا",
                "کاربر فعلی یافت نشد.",
                parent=self,
            )

            return

        emergency_reported_by = (
            getattr(
                current_user,
                "full_name",
                None,
            )
            or getattr(
                current_user,
                "username",
                None,
            )
            or ""
        )

        # ---------------------------------------------------------------------
        # Create Work Order
        # ---------------------------------------------------------------------

        try:

            wo_repo = (
                WorkOrderRepository(
                    SessionLocal
                )
            )

            success, message = (
                wo_repo.create_work_order(
                    title=title,
                    equipment_id=equipment_id,
                    type_str="EMERGENCY",
                    priority=priority,

                    # Legacy User technician assignment is intentionally
                    # disabled for the new Department/Personnel workflow.
                    technician_id=None,

                    # Emergency work orders start immediately.
                    scheduled_date=tehran_now(),

                    description=(
                        description
                        or None
                    ),

                    parts_used=None,

                    schedule_id=None,

                    # The current logged-in application user is the reporter/
                    # operator, not the maintenance Personnel.
                    operator_id=(
                        getattr(
                            current_user,
                            "id",
                            None,
                        )
                    ),

                    failure_report_time=(
                        tehran_now()
                    ),

                    operator_notes=(
                        description
                        or None
                    ),

                    operator_signature=None,

                    manual_cost=0.0,

                    cost_description=None,

                    deadline=(
                        deadline_value
                    ),

                    # Legacy additional User technicians remain unused.
                    additional_technician_ids=None,

                    # NEW WORKFLOW:
                    # department is selected at creation.
                    department_id=department_id,
                )
            )

        except TypeError as exc:

            messagebox.showerror(
                "خطای نسخه کد",
                (
                    "متد ثبت دستور کار با نسخه فعلی "
                    "WorkOrderRepository هماهنگ نیست.\n\n"
                    f"{exc}"
                ),
                parent=self,
            )

            return

        except Exception as exc:

            messagebox.showerror(
                "خطا",
                (
                    "خطایی هنگام ثبت دستور کار "
                    f"اضطراری رخ داد:\n\n{exc}"
                ),
                parent=self,
            )

            return

        # ---------------------------------------------------------------------
        # Result
        # ---------------------------------------------------------------------

        if not success:

            messagebox.showerror(
                "خطا",
                message,
                parent=self,
            )

            return

        # ---------------------------------------------------------------------
        # Store reporter
        #
        # The repository creates the Work Order first. We then store the
        # application User's name in emergency_reported_by for documentation.
        # This field is NOT the maintenance Personnel field.
        # ---------------------------------------------------------------------

        try:

            db = SessionLocal()

            try:

                wo = (
                    db.query(
                        WorkOrder
                    )
                    .order_by(
                        WorkOrder.id.desc()
                    )
                    .first()
                )

                if wo:

                    wo.emergency_reported_by = (
                        emergency_reported_by
                    )

                    db.commit()

            finally:

                db.close()

        except Exception as exc:

            # The Work Order was already created successfully, so failure to
            # update the optional reporter text must not make the whole
            # operation appear failed.
            print(
                "Emergency reporter update error:",
                exc,
            )

        self.result = True

        messagebox.showinfo(
            "موفق",
            (
                "دستور کار اضطراری با موفقیت ثبت شد."
            ),
            parent=self,
        )

        self.destroy()