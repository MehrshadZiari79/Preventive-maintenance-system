# views/work_order_dialog.py

"""
PM System - Work Order Create / Edit Dialog
===========================================

Final Work Order workflow
-------------------------

CREATE / EDIT:
    - Title
    - Equipment
    - Work Order type
    - Priority
    - Department
    - Operator
    - Failure information
    - Scheduled date + time
    - Deadline
    - Description / notes / parts / cost

IMPORTANT:
    A User technician is NOT selected here.

    A Personnel worker is NOT selected here.

The workflow is:

    Work Order creation
        ->
    Department selected
        ->
    Work performed
        ->
    Finish Request
        ->
    Personnel selected from that exact Department
        ->
    completed_by_personnel_id

Legacy User technician fields remain in the database so historical
Work Orders continue to load and remain viewable.
"""


import tkinter as tk
from tkinter import ttk, messagebox
from views.ux import field_error
from datetime import datetime, date


from database.equipment_repository import EquipmentRepository
from database.personnel_repository import PersonnelRepository
from database.work_order import WorkOrderPriority


from views.searchable_combobox import SearchableCombobox
from views.jalali_date_entry import JalaliDateEntry
from views.personnel_selection_dialog import PersonnelSelectionDialog

# RTL-aware Text widget
from utils.rtl_text_widget import RTLText


from utils.theme import (
    NAVY,
    NAVY_LIGHT,
    WHITE,
    GRAY_BG,
    GRAY_BORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    SUCCESS,
    WARNING,
    FONT_HEADING,
    FONT_NORMAL,
    FONT_SMALL,
)


# ============================================================================
# COLORS
# ============================================================================

BG = GRAY_BG
CARD_BG = WHITE
PRIMARY = NAVY


# ============================================================================
# HELPERS
# ============================================================================

def _normalize_time(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").strftime("%H:%M")
    except ValueError:
        pass
    try:
        return datetime.strptime(value, "%H:%M:%S").strftime("%H:%M")
    except ValueError:
        pass
    return None


def _combine_date_and_time(date_value, time_value):
    if date_value is None:
        return None
    if isinstance(date_value, datetime):
        date_value = date_value.date()
    if not isinstance(date_value, date):
        return None
    normalized_time = _normalize_time(time_value)
    if not normalized_time:
        return None
    hour, minute = normalized_time.split(":")
    return datetime(
        date_value.year, date_value.month, date_value.day,
        int(hour), int(minute),
    )


# ============================================================================
# WORK ORDER DIALOG
# ============================================================================

class WorkOrderDialog(tk.Toplevel):

    def __init__(self, parent, wo_repo, work_order=None, callback=None):
        super().__init__(parent)

        # Hide while building to avoid the visible geometry jump.
        try:
            self.withdraw()
        except Exception:
            pass

        self.parent = parent
        self.wo_repo = wo_repo
        self.work_order = work_order
        self.callback = callback
        self.result = False

        self.title("دستور کار جدید" if not work_order else "ویرایش دستور کار")
        self.minsize(700, 600)
        self.resizable(True, True)
        self.configure(bg=BG)

        from database.db import SessionLocal
        self.eq_repo = EquipmentRepository(SessionLocal)
        self.personnel_repo = PersonnelRepository(SessionLocal)

        self.equipment_map = {}
        self.department_map = {}
        self.department_id_to_name = {}

        self.completion_personnel_people = []
        self._selected_completion_personnel_ids = set()
        self._completion_edit_enabled = False

        self._build_ui()

        if self.work_order:
            self._load_data()

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # Center BEFORE deiconify → no visible jump.
        self._apply_responsive_geometry()

        try:
            self.deiconify()
        except Exception:
            pass

    # =========================================================================
    # WINDOW GEOMETRY
    # =========================================================================

    def _apply_responsive_geometry(self):
        try:
            self.update_idletasks()
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            max_w = max(720, screen_w - 60)
            max_h = max(560, screen_h - 60)
            width = min(850, max_w)
            height = min(900, max_h)
            width = max(720, width)
            height = max(560, height)
            x = max(10, (screen_w - width) // 2)
            y = max(10, (screen_h - height) // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            try:
                self.geometry("850x800")
            except Exception:
                pass

    # =========================================================================
    # UI
    # =========================================================================

    def _build_ui(self):

        # --------------------------------------------------------------
        # Header
        # --------------------------------------------------------------
        header = tk.Frame(self, bg=PRIMARY, height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        head_title = (
            "📝  دستور کار جدید"
            if not self.work_order
            else "✏️  ویرایش دستور کار"
        )

        tk.Label(
            header, text=head_title,
            font=FONT_HEADING, bg=PRIMARY, fg=WHITE, anchor="center",
        ).pack(fill="both", expand=True, pady=10)

        # --------------------------------------------------------------
        # Scrollable area
        # --------------------------------------------------------------
        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, side="top")

        self.canvas = tk.Canvas(
            content, bg=BG, highlightthickness=0, borderwidth=0,
        )

        self.vsb = ttk.Scrollbar(
            content, orient="vertical", command=self.canvas.yview,
        )

        self.scrollable = tk.Frame(self.canvas, bg=BG)

        self.scroll_window = self.canvas.create_window(
            (0, 0), window=self.scrollable, anchor="nw",
        )

        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.scrollable.bind("<Configure>", self._on_scrollable_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        self.vsb.pack(side="right", fill="y", padx=(0, 8), pady=8)

        self.canvas.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self.canvas.bind(
            "<Button-4>",
            lambda event: self.canvas.yview_scroll(-3, "units"),
            add="+",
        )
        self.canvas.bind(
            "<Button-5>",
            lambda event: self.canvas.yview_scroll(3, "units"),
            add="+",
        )

        # --------------------------------------------------------------
        # Main form
        # --------------------------------------------------------------
        main = tk.Frame(self.scrollable, bg=CARD_BG, padx=24, pady=20)
        main.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        main.grid_columnconfigure(0, weight=1)

        row = 0

        # ============ TITLE ============
        ttk.Label(main, text="عنوان *:").grid(
            row=row, column=1, sticky=tk.E, pady=6, padx=(10, 0),
        )
        self.title_entry = ttk.Entry(main, width=50)
        self.title_entry.grid(row=row, column=0, sticky=tk.EW, pady=6)
        row += 1

        # ============ EQUIPMENT ============
        ttk.Label(main, text="تجهیز *:").grid(
            row=row, column=1, sticky=tk.E, pady=6, padx=(10, 0),
        )
        self.equipment_combo = SearchableCombobox(main, width=48, state="normal")
        self.equipment_combo.grid(row=row, column=0, sticky=tk.EW, pady=6)
        self._load_equipment()
        row += 1

        # ============ DEPARTMENT ============
        ttk.Label(main, text="دپارتمان مسئول *:").grid(
            row=row, column=1, sticky=tk.E, pady=6, padx=(10, 0),
        )
        department_frame = ttk.Frame(main)
        department_frame.grid(row=row, column=0, sticky=tk.EW, pady=6)
        department_frame.columnconfigure(0, weight=1)

        self.department_var = tk.StringVar()
        self.department_combo = ttk.Combobox(
            department_frame,
            textvariable=self.department_var,
            state="readonly", justify="right", font=FONT_NORMAL,
        )
        self.department_combo.grid(row=0, column=0, sticky=tk.EW)
        self._load_departments()

        tk.Label(
            department_frame,
            text="دپارتمان مسئول انجام این دستور کار را انتخاب کنید.",
            font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT, anchor="e",
        ).grid(row=1, column=0, sticky="e", pady=(4, 0))
        row += 1

        # ============ TYPE ============
        ttk.Label(main, text="نوع:").grid(
            row=row, column=1, sticky=tk.E, pady=6, padx=(10, 0),
        )
        type_frame = ttk.Frame(main)
        type_frame.grid(row=row, column=0, sticky=tk.EW, pady=6)
        self.type_var = tk.StringVar(value="CORRECTIVE")
        for text, value in [("اصلاحی", "CORRECTIVE"),
                            ("پیشگیرانه", "PREVENTIVE"),
                            ("بازرسی", "INSPECTION")]:
            ttk.Radiobutton(type_frame, text=text,
                            variable=self.type_var, value=value).pack(side=tk.RIGHT, padx=10)
        row += 1

        # ============ PRIORITY ============
        ttk.Label(main, text="اولویت:").grid(
            row=row, column=1, sticky=tk.E, pady=6, padx=(10, 0),
        )
        prio_frame = ttk.Frame(main)
        prio_frame.grid(row=row, column=0, sticky=tk.EW, pady=6)
        self.priority_var = tk.StringVar(value=WorkOrderPriority.MEDIUM.name)
        for text, value in [("کم", "LOW"), ("متوسط", "MEDIUM"),
                            ("بالا", "HIGH"), ("فوری", "URGENT")]:
            ttk.Radiobutton(prio_frame, text=text,
                            variable=self.priority_var, value=value).pack(side=tk.RIGHT, padx=10)
        row += 1

        # ============ FAILURE REPORT TIME ============
        ttk.Label(main, text="ساعت اعلام خرابی:").grid(
            row=row, column=1, sticky=tk.E, pady=6, padx=(10, 0),
        )
        failure_frame = ttk.Frame(main)
        failure_frame.grid(row=row, column=0, sticky=tk.E, pady=6)
        self.failure_date = JalaliDateEntry(failure_frame, width=12)
        self.failure_date.pack(side=tk.RIGHT, padx=2)
        self.failure_time = ttk.Entry(failure_frame, width=8)
        self.failure_time.insert(0, "00:00")
        self.failure_time.pack(side=tk.RIGHT, padx=2)
        ttk.Label(failure_frame, text="ساعت:").pack(side=tk.RIGHT, padx=2)
        row += 1

        # ============ SCHEDULED DATE + TIME ============
        ttk.Label(main, text="تاریخ و ساعت برنامه‌ریزی *:").grid(
            row=row, column=1, sticky=tk.E, pady=6, padx=(10, 0),
        )
        scheduled_frame = ttk.Frame(main)
        scheduled_frame.grid(row=row, column=0, sticky=tk.E, pady=6)
        self.scheduled_date = JalaliDateEntry(scheduled_frame, width=12)
        self.scheduled_date.pack(side=tk.RIGHT, padx=2)
        self.scheduled_time = ttk.Entry(scheduled_frame, width=8)
        self.scheduled_time.pack(side=tk.RIGHT, padx=2)
        ttk.Label(scheduled_frame, text="ساعت:").pack(side=tk.RIGHT, padx=2)
        row += 1

        # ============ DEADLINE ============
        ttk.Label(main, text="تاریخ سررسید (ددلاین):").grid(
            row=row, column=1, sticky=tk.E, pady=6, padx=(10, 0),
        )
        self.deadline_date = JalaliDateEntry(main, width=47)
        self.deadline_date.grid(row=row, column=0, sticky=tk.EW, pady=6)
        row += 1

        # ============ DESCRIPTION ============
        ttk.Label(main, text="توضیحات تعمیر:").grid(
            row=row, column=1, sticky=tk.NE, pady=6, padx=(10, 0),
        )
        self.desc_text = RTLText(
            main,
            width=50,
            height=5,
            font=FONT_NORMAL,
        )
        self.desc_text.grid(row=row, column=0, sticky=tk.EW, pady=6)
        row += 1

        # ============ PARTS ============
        ttk.Label(main, text="قطعات مصرفی (توضیح):").grid(
            row=row, column=1, sticky=tk.NE, pady=6, padx=(10, 0),
        )
        self.parts_text = RTLText(
            main,
            width=50,
            height=4,
            font=FONT_NORMAL,
        )
        self.parts_text.grid(row=row, column=0, sticky=tk.EW, pady=6)
        row += 1

        # ============ MANUAL COST ============
        ttk.Label(main, text="هزینه دستی (ریال):").grid(
            row=row, column=1, sticky=tk.E, pady=6, padx=(10, 0),
        )
        self.manual_cost_entry = ttk.Entry(main, width=20)
        self.manual_cost_entry.grid(row=row, column=0, sticky=tk.W, pady=6)
        self.manual_cost_entry.insert(0, "0")
        row += 1

        # ============ COST DESCRIPTION ============
        ttk.Label(main, text="توضیح هزینه:").grid(
            row=row, column=1, sticky=tk.NE, pady=6, padx=(10, 0),
        )
        self.cost_desc_text = RTLText(
            main,
            width=50,
            height=2,
            font=FONT_NORMAL,
        )
        self.cost_desc_text.grid(row=row, column=0, sticky=tk.EW, pady=6)

        # ============ COMPLETION PERSONNEL (edit only) ============
        if self.work_order:
            self._build_completion_personnel_editor(main, row)
            row += 1

        # --------------------------------------------------------------
        # Bottom action bar
        # --------------------------------------------------------------
        btn_frame = tk.Frame(
            self, bg=WHITE, height=70,
            highlightbackground=GRAY_BORDER, highlightthickness=1,
        )
        btn_frame.pack(fill="x", side="bottom")
        btn_frame.pack_propagate(False)

        tk.Button(
            btn_frame, text="انصراف", command=self.destroy,
            bg=GRAY_BG, fg=TEXT_DARK, font=FONT_NORMAL,
            relief="flat", bd=0, padx=22, pady=8, cursor="hand2",
            activebackground=GRAY_BORDER, activeforeground=TEXT_DARK,
        ).pack(side=tk.LEFT, padx=(15, 8), pady=12)

        tk.Button(
            btn_frame, text="ذخیره", command=self._on_save,
            bg=SUCCESS, fg=WHITE, font=FONT_NORMAL,
            relief="flat", bd=0, padx=25, pady=8, cursor="hand2",
            activebackground=NAVY_LIGHT, activeforeground=WHITE,
        ).pack(side=tk.RIGHT, padx=(8, 15), pady=12)

        self.bind("<Control-s>", lambda event: self._on_save())
        self.bind("<Escape>", lambda event: self.destroy())

        self.after_idle(lambda: self.title_entry.focus_set())
        self.after_idle(lambda: self._bind_mousewheel_to_children(self.scrollable))

    # =========================================================================
    # MOUSE WHEEL PROPAGATION
    # =========================================================================

    def _bind_mousewheel_to_children(self, widget):
        if isinstance(widget, (tk.Text, tk.Listbox)):
            return
        try:
            widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
            widget.bind(
                "<Button-4>",
                lambda event: self.canvas.yview_scroll(-3, "units"),
                add="+",
            )
            widget.bind(
                "<Button-5>",
                lambda event: self.canvas.yview_scroll(3, "units"),
                add="+",
            )
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_mousewheel_to_children(child)

    # =========================================================================
    # COMPLETION PERSONNEL (edit only)
    # =========================================================================

    def _work_order_allows_completion_personnel_edit(self):
        if not self.work_order:
            return False
        status = getattr(self.work_order, "status", None)
        status_name = str(
            getattr(status, "name", None)
            or getattr(status, "value", None)
            or status or ""
        ).upper()
        return status_name in {"FINISH_REQUESTED", "COMPLETED", "APPROVED"} or \
               getattr(self.work_order, "end_time", None) is not None

    def _build_completion_personnel_editor(self, parent, row):
        frame = tk.Frame(
            parent, bg=GRAY_BG, bd=0, relief="solid",
            highlightbackground=GRAY_BORDER, highlightthickness=1,
        )
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        frame.grid_columnconfigure(0, weight=1)

        header = tk.Frame(frame, bg=PRIMARY)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(
            header, text="پرسنل انجام‌دهنده — ویرایش اطلاعات اتمام",
            font=FONT_HEADING, bg=PRIMARY, fg=WHITE, anchor="e",
        ).pack(fill="x", padx=12, pady=8)

        self.completion_personnel_note = tk.Label(
            frame,
            text=("جستجو در تمام پرسنل و تمام دپارتمان‌ها انجام می‌شود. "
                  "انتخاب پرسنل در این پنجره فقط برای ویرایش یک دستور کارِ "
                  "واردشده به مرحله اتمام است."),
            font=FONT_SMALL, bg=GRAY_BG, fg=TEXT_LIGHT,
            anchor="e", justify="right",
        )
        self.completion_personnel_note.grid(
            row=1, column=0, sticky="ew", padx=12, pady=(8, 10),
        )

        self.completion_personnel_summary = tk.Label(
            frame, text="پرسنل فعلی: —",
            font=FONT_NORMAL, bg=GRAY_BG, fg=TEXT_DARK,
            anchor="e", justify="right",
        )
        self.completion_personnel_summary.grid(
            row=2, column=0, sticky="ew", padx=12, pady=(0, 8),
        )

        self.completion_personnel_button = tk.Button(
            frame,
            text="👥 انتخاب / ویرایش پرسنل انجام‌دهنده",
            command=self._open_completion_personnel_selector,
            bg=WHITE, fg=TEXT_DARK,
            activebackground=GRAY_BORDER, activeforeground=TEXT_DARK,
            relief="solid", bd=1, cursor="hand2",
            font=FONT_NORMAL, padx=18, pady=8,
        )
        self.completion_personnel_button.grid(
            row=3, column=0, sticky="e", padx=12, pady=(0, 12),
        )

        self._completion_edit_enabled = self._work_order_allows_completion_personnel_edit()
        self._load_completion_personnel()

        if not self._completion_edit_enabled:
            self._set_completion_personnel_editor_state("disabled")
            self.completion_personnel_note.config(
                text=("این دستور کار هنوز وارد مرحله اتمام نشده است. "
                      "پرسنل واقعی انجام‌دهنده فقط هنگام ثبت اتمام کار انتخاب می‌شود."),
                fg=WARNING,
            )

    def _load_completion_personnel(self):
        try:
            people = self.personnel_repo.get_all() or []
        except Exception as exc:
            people = []
            try:
                messagebox.showwarning(
                    "هشدار",
                    f"بارگذاری فهرست پرسنل انجام‌دهنده انجام نشد:\n\n{exc}",
                    parent=self,
                )
            except Exception:
                pass
        self.completion_personnel_people = list(people)
        current_people = list(getattr(self.work_order, "completers", []) or [])
        self._selected_completion_personnel_ids = {
            int(getattr(p, "id"))
            for p in current_people
            if getattr(p, "id", None) is not None
        }
        self._refresh_completion_personnel_summary()

    def _open_completion_personnel_selector(self):
        if not self._completion_edit_enabled:
            return
        dialog = PersonnelSelectionDialog(
            self,
            personnel=self.completion_personnel_people,
            selected_ids=sorted(self._selected_completion_personnel_ids),
            title="انتخاب / ویرایش پرسنل انجام‌دهنده دستور کار",
        )
        self.wait_window(dialog)
        if dialog.result is not None:
            self._selected_completion_personnel_ids = {int(pid) for pid in dialog.result}
            self._refresh_completion_personnel_summary()

    def _refresh_completion_personnel_summary(self):
        if not hasattr(self, "completion_personnel_summary"):
            return
        names = []
        by_id = {
            int(getattr(p, "id")): p
            for p in self.completion_personnel_people
            if getattr(p, "id", None) is not None
        }
        for pid in sorted(self._selected_completion_personnel_ids):
            person = by_id.get(int(pid))
            if person is None:
                continue
            code = str(getattr(person, "personnel_code", "") or "").strip()
            name = str(getattr(person, "full_name", "") or "").strip()
            department = getattr(person, "department", None)
            department_name = str(getattr(department, "name", "") or "").strip()
            display = " - ".join(v for v in (code, name, department_name) if v)
            if display:
                names.append(display)
        text = ("پرسنل فعلی: " + "، ".join(names)) if names else "پرسنل فعلی: هنوز انتخاب نشده است"
        self.completion_personnel_summary.config(text=text)

    def _set_completion_personnel_editor_state(self, state):
        try:
            self.completion_personnel_button.configure(
                state=state,
                cursor="hand2" if state != "disabled" else "arrow",
            )
        except Exception:
            pass

    # =========================================================================
    # SCROLLING
    # =========================================================================

    def _on_scrollable_configure(self, event=None):
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass

    def _on_canvas_configure(self, event=None):
        try:
            self.canvas.itemconfigure(
                self.scroll_window, width=self.canvas.winfo_width(),
            )
        except Exception:
            pass

    def _on_mousewheel(self, event):
        try:
            if not self.winfo_exists():
                return
            delta = event.delta
            if delta == 0:
                return
            units = int(-delta / 120)
            if units == 0:
                units = -1 if delta > 0 else 1
            self.canvas.yview_scroll(units, "units")
        except Exception:
            pass

    # =========================================================================
    # EQUIPMENT / DEPARTMENTS
    # =========================================================================

    def _load_equipment(self):
        try:
            equipments = self.eq_repo.get_all_equipment() or []
        except Exception as exc:
            equipments = []
            messagebox.showwarning(
                "هشدار",
                f"بارگذاری تجهیزات انجام نشد:\n\n{exc}",
                parent=self,
            )

        self.equipment_map = {}
        display_values = []

        for eq in equipments:
            if not isinstance(eq, dict):
                continue
            eq_id = eq.get("id")
            if eq_id is None:
                continue
            code = str(eq.get("code") or "").strip()
            name = str(eq.get("name") or "").strip()
            if code and name:
                display = f"{code} - {name}"
            elif name:
                display = name
            elif code:
                display = code
            else:
                display = f"تجهیز #{eq_id}"
            self.equipment_map[display] = eq_id
            display_values.append(display)

        try:
            self.equipment_combo.set_completion_list(display_values)
            self.equipment_combo.set("")
        except Exception:
            pass

    def _load_departments(self):
        try:
            departments = self.personnel_repo.get_departments() or []
        except Exception as exc:
            departments = []
            messagebox.showwarning(
                "هشدار",
                f"بارگذاری دپارتمان‌ها انجام نشد:\n\n{exc}",
                parent=self,
            )

        self.department_map = {}
        self.department_id_to_name = {}

        for department in departments:
            if isinstance(department, dict):
                department_id = department.get("id")
                name = department.get("name") or ""
            else:
                department_id = getattr(department, "id", None)
                name = getattr(department, "name", None) or ""
            name = str(name).strip()
            if department_id is None or not name:
                continue
            self.department_map[name] = department_id
            self.department_id_to_name[department_id] = name

        values = sorted(self.department_map.keys())
        self.department_combo["values"] = values
        try:
            self.department_combo.set("")
        except Exception:
            pass

    # =========================================================================
    # LOAD EXISTING
    # =========================================================================

    def _load_data(self):
        wo = self.work_order

        self.title_entry.insert(0, wo.title or "")

        equipment = getattr(wo, "equipment", None)
        if equipment:
            code = str(getattr(equipment, "code", "") or "").strip()
            name = str(getattr(equipment, "name", "") or "").strip()
            if code and name:
                eq_key = f"{code} - {name}"
            elif name:
                eq_key = name
            else:
                eq_key = code
            if eq_key in self.equipment_map:
                try:
                    self.equipment_combo.set(eq_key)
                except Exception:
                    pass

        department_id = getattr(wo, "department_id", None)
        if department_id is not None:
            department_name = self.department_id_to_name.get(department_id, "")
            if department_name:
                try:
                    self.department_var.set(department_name)
                except Exception:
                    pass

        wo_type = getattr(wo, "type", None)
        type_name = getattr(wo_type, "name", None)
        if type_name:
            self.type_var.set(str(type_name))

        wo_priority = getattr(wo, "priority", None)
        priority_name = getattr(wo_priority, "name", None)
        if priority_name:
            self.priority_var.set(str(priority_name))

        failure_report_time = getattr(wo, "failure_report_time", None)
        if failure_report_time:
            try:
                self.failure_date.set_date(failure_report_time.date())
                self.failure_time.delete(0, tk.END)
                self.failure_time.insert(0, failure_report_time.strftime("%H:%M"))
            except Exception:
                pass

        scheduled_date = getattr(wo, "scheduled_date", None)
        if scheduled_date:
            try:
                if isinstance(scheduled_date, datetime):
                    self.scheduled_date.set_date(scheduled_date.date())
                    self.scheduled_time.delete(0, tk.END)
                    self.scheduled_time.insert(0, scheduled_date.strftime("%H:%M"))
                else:
                    self.scheduled_date.set_date(scheduled_date)
            except Exception:
                pass

        deadline = getattr(wo, "deadline", None)
        if deadline:
            try:
                self.deadline_date.set_date(deadline)
            except Exception:
                pass

        description = getattr(wo, "description", None)
        if description:
            # RTLText: use set_logical_text for programmatic content
            self.desc_text.set_logical_text(description)

        parts_used = getattr(wo, "parts_used", None)
        if parts_used:
            self.parts_text.set_logical_text(parts_used)

        manual_cost = getattr(wo, "manual_cost", None)
        if manual_cost is not None:
            self.manual_cost_entry.delete(0, tk.END)
            self.manual_cost_entry.insert(0, str(manual_cost))

        cost_description = getattr(wo, "cost_description", None)
        if cost_description:
            self.cost_desc_text.set_logical_text(cost_description)

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def _validate_form(self):
        title = self.title_entry.get().strip()
        if not title:
            field_error(self.title_entry, "عنوان الزامی است.")
            return None

        try:
            eq_key = self.equipment_combo.get()
        except Exception:
            eq_key = ""
        eq_key = eq_key.strip() if eq_key else ""

        if not eq_key:
            field_error(self.equipment_combo, "انتخاب تجهیز الزامی است.")
            return None

        if eq_key not in self.equipment_map:
            field_error(self.equipment_combo, "تجهیز انتخاب‌شده معتبر نیست.")
            return None

        equipment_id = self.equipment_map[eq_key]

        department_name = self.department_var.get().strip()
        if not department_name:
            field_error(self.department_combo, "انتخاب دپارتمان مسئول الزامی است.")
            return None

        department_id = self.department_map.get(department_name)
        if department_id is None:
            field_error(self.department_combo, "دپارتمان انتخاب‌شده معتبر نیست.")
            return None

        try:
            scheduled_date_value = self.scheduled_date.get_date()
        except Exception:
            scheduled_date_value = None

        if not scheduled_date_value:
            field_error(self.scheduled_date, "تاریخ برنامه‌ریزی الزامی است.")
            return None

        scheduled_time_value = self.scheduled_time.get().strip()
        normalized_scheduled_time = _normalize_time(scheduled_time_value)
        if not normalized_scheduled_time:
            field_error(self.scheduled_time, "ساعت برنامه‌ریزی الزامی است.")
            return None

        scheduled_datetime = _combine_date_and_time(
            scheduled_date_value, normalized_scheduled_time,
        )
        if not scheduled_datetime:
            messagebox.showerror(
                "خطا",
                "تاریخ و ساعت برنامه‌ریزی معتبر نیست.",
                parent=self,
            )
            return None

        return {
            "title": title,
            "equipment_id": equipment_id,
            "department_id": department_id,
            "scheduled_date": scheduled_datetime,
        }

    # =========================================================================
    # SAVE
    # =========================================================================

    def _on_save(self):
        validated = self._validate_form()
        if not validated:
            return

        title = validated["title"]
        equipment_id = validated["equipment_id"]
        department_id = validated["department_id"]
        scheduled_date = validated["scheduled_date"]

        type_str = self.type_var.get() or "CORRECTIVE"
        priority = self.priority_var.get() or WorkOrderPriority.MEDIUM.name

        failure_report_time = None
        try:
            failure_date_value = self.failure_date.get_date()
        except Exception:
            failure_date_value = None
        failure_time_value = self.failure_time.get().strip()
        if failure_date_value and failure_time_value:
            normalized_failure_time = _normalize_time(failure_time_value)
            if normalized_failure_time:
                failure_report_time = _combine_date_and_time(
                    failure_date_value, normalized_failure_time,
                )
            else:
                field_error(self.failure_time, "ساعت اعلام خرابی معتبر نیست.")
                return

        try:
            deadline = self.deadline_date.get_date()
        except Exception:
            deadline = None

        # RTLText: get() returns the LOGICAL text directly.
        description = self.desc_text.get() or None
        parts_used = self.parts_text.get() or None
        cost_description = self.cost_desc_text.get() or None

        manual_cost_text = self.manual_cost_entry.get().strip()
        manual_cost = 0.0
        if manual_cost_text:
            try:
                manual_cost = float(manual_cost_text)
            except ValueError:
                field_error(self.manual_cost_entry, "هزینه دستی باید یک عدد معتبر باشد.")
                return

        if manual_cost < 0:
            field_error(self.manual_cost_entry, "هزینه دستی نمی‌تواند منفی باشد.")
            return

        try:
            if self.work_order:
                success, msg = self.wo_repo.update_work_order(
                    self.work_order.id,
                    title, equipment_id, type_str, priority,
                    technician_id=None,
                    scheduled_date=scheduled_date,
                    description=description,
                    parts_used=parts_used,
                    failure_report_time=failure_report_time,
                    manual_cost=manual_cost,
                    cost_description=cost_description,
                    deadline=deadline,
                    additional_technician_ids=None,
                    department_id=department_id,
                    completion_personnel_ids=(
                        sorted(self._selected_completion_personnel_ids)
                        if self._completion_edit_enabled else None
                    ),
                )
            else:
                success, msg = self.wo_repo.create_work_order(
                    title=title,
                    equipment_id=equipment_id,
                    type_str=type_str,
                    priority=priority,
                    technician_id=None,
                    scheduled_date=scheduled_date,
                    description=description,
                    parts_used=parts_used,
                    schedule_id=None,
                    failure_report_time=failure_report_time,
                    manual_cost=manual_cost,
                    cost_description=cost_description,
                    deadline=deadline,
                    additional_technician_ids=None,
                    department_id=department_id,
                )
        except Exception as exc:
            messagebox.showerror(
                "خطا",
                f"خطایی هنگام ذخیره دستور کار رخ داد:\n\n{exc}",
                parent=self,
            )
            return

        if success:
            messagebox.showinfo("موفق", msg, parent=self)
            self.result = True
            if self.callback:
                try:
                    self.callback()
                except Exception as exc:
                    print("WorkOrderDialog callback error:", exc)
            self.destroy()
        else:
            messagebox.showerror("خطا", msg, parent=self)