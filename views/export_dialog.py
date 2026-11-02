# views/export_dialog.py
"""
Professional Excel Export Dialogs
----------------------------------

Provides export dialogs for:

    - Equipment
    - Preventive Maintenance (PM)
    - Work Orders
    - Inspections
    - Spare Parts

Important:
    All available Excel columns are selected by default.

The selected columns are passed to services.export_service so the
Excel export layer remains responsible for creating the actual workbook.
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta, date

from services.export_service import (
    export_equipment_excel,
    export_pm_excel,
    export_work_orders_excel,
    export_inspections_excel,
    export_spare_parts_excel,
    export_repair_requests_excel,
    get_export_columns,
    get_default_export_columns,
)

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

from views.jalali_date_entry import JalaliDateEntry
from utils.date_helpers import tehran_now, to_jalali_datetime_str  # Iranian (Asia/Tehran) clock


from utils.date_helpers import jalali_stamp  # Jalali file names / stamps
# ============================================================================
# COLORS
# ============================================================================

BG = GRAY_BG
PRIMARY = NAVY
PRIMARY_LIGHT = NAVY_LIGHT
TEXT = TEXT_DARK
BORDER = GRAY_BORDER
CARD_BG = WHITE


# ============================================================================
# SAFE HELPERS
# ============================================================================

def _safe_date(value):
    """
    Convert common date/datetime values into datetime.date.

    Returns None when conversion is not possible.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return None

        formats = (
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
        )

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue

    if hasattr(value, "date"):
        try:
            result = value.date()

            if isinstance(result, datetime):
                return result.date()

            if isinstance(result, date):
                return result
        except Exception:
            pass

    return None


def _enum_name(value):
    """
    Safely return Enum.name or string representation.
    """
    if value is None:
        return ""

    name = getattr(value, "name", None)

    if name is not None:
        return str(name)

    return str(value)


def _enum_value(value):
    """
    Safely return Enum.value or string representation.
    """
    if value is None:
        return ""

    enum_value = getattr(value, "value", None)

    if enum_value is not None:
        return str(enum_value)

    return str(value)


def _get_value(obj, key, default=None):
    """Safely read a value from either an ORM object or a dictionary."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ============================================================================
# OUTPUT WAIT DIALOG
# ============================================================================
class OutputWaitDialog(tk.Toplevel):
    """Professional Persian modal dialog displayed while an output is generated."""

    def __init__(self, parent, output_title: str):
        super().__init__(parent)
        self.title("لطفاً صبر کنید")
        self.configure(bg=CARD_BG)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        width, height = 430, 190
        try:
            parent.update_idletasks()
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
        except Exception:
            x, y = 100, 100
        self.geometry(f"{width}x{height}+{x}+{y}")

        body = tk.Frame(self, bg=CARD_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        tk.Label(
            body, text="لطفاً صبر کنید", font=FONT_HEADING,
            bg=CARD_BG, fg=PRIMARY, anchor="e",
        ).pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            body, text=f"در حال تهیه {output_title} هستیم...",
            font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, anchor="e",
        ).pack(fill=tk.X)

        tk.Label(
            body,
            text="این عملیات ممکن است کمی زمان ببرد. لطفاً تا پایان عملیات صبر کنید.",
            font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT,
            anchor="e", justify="right", wraplength=380,
        ).pack(fill=tk.X, pady=(5, 12))

        self.progress = ttk.Progressbar(body, mode="indeterminate", length=360)
        self.progress.pack(fill=tk.X)
        self.progress.start(12)
        self.grab_set()
        self.update_idletasks()
        self.update()

    def close(self):
        try:
            self.progress.stop()
        except Exception:
            pass
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


def _run_export_with_wait(owner, output_title: str, worker, on_success):
    """Run the heavy export outside Tk's main thread and finish safely on Tk."""
    if getattr(owner, "_output_running", False):
        return

    owner._output_running = True
    wait_dialog = OutputWaitDialog(owner, output_title)

    def _worker():
        error = None
        try:
            worker()
        except Exception as exc:
            error = exc

        def _finish():
            owner._output_running = False
            wait_dialog.close()
            if error is None:
                on_success()
            else:
                owner._show_error(error)

        try:
            owner.after(0, _finish)
        except Exception:
            try:
                wait_dialog.close()
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()


# ============================================================================
# BASE EXPORT DIALOG
# ============================================================================

class BaseExportDialog(tk.Toplevel):
    """
    Base class for all export dialogs.

    Features:
        - Professional header
        - Scrollable content
        - Data range selection
        - Column selection
        - All columns selected by default
        - Select all / clear all
        - Selected column counter
        - Fixed bottom action bar
    """

    def __init__(
            self,
            parent,
            title,
            export_type,
            width=720,
            height=760,
            range_options=None,
    ):
        super().__init__(parent)

        self.parent = parent
        self.export_type = export_type
        self._output_running = False

        self.title(title)
        self.configure(bg=BG)

        self.transient(parent)
        self.grab_set()

        self.update_idletasks()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Keep a margin around the dialog.
        max_width = screen_width - 80
        max_height = screen_height - 100

        actual_width = min(width, max_width)
        actual_height = min(height, max_height)

        # Minimum usable dimensions.
        actual_width = max(actual_width, 600)
        actual_height = max(actual_height, 500)

        x = max(
            0,
            (screen_width - actual_width) // 2,
        )

        y = max(
            0,
            (screen_height - actual_height) // 2,
        )

        self.geometry(
            f"{actual_width}x{actual_height}+{x}+{y}"
        )

        self.minsize(
            600,
            500,
        )

        self.resizable(
            True,
            True,
        )

        # ------------------------------------------------------------------
        # Variables
        # ------------------------------------------------------------------

        self.data_range = tk.StringVar(value="all")

        self.include_details = tk.BooleanVar(value=True)
        self.include_stats = tk.BooleanVar(value=True)

        self.range_options = range_options or [
            ("همه موارد", "all"),
            ("محدوده تاریخ", "date_range"),
        ]

        self.column_definitions = get_export_columns(
            export_type
        )

        self.column_vars = {}

        for key, label in self.column_definitions:
            self.column_vars[key] = tk.BooleanVar(
                value=True
            )

        self.selected_count_var = tk.StringVar()

        self._setup_styles()
        self._build_shell()
        self._build_ui()

        self._update_selected_count()

        self.data_range.trace_add(
            "write",
            self._on_range_change,
        )

        self._on_range_change()

        self.protocol(
            "WM_DELETE_WINDOW",
            self.destroy,
        )
    # ======================================================================
    # STYLING
    # ======================================================================

    def _setup_styles(self):
        """
        Configure ttk styles used by the export dialog.
        """
        style = ttk.Style(self)

        try:
            from utils.theme import ensure_theme
            ensure_theme(style)  # never switch the global ttk theme per page
        except Exception:
            pass

        style.configure(
            "Export.TCombobox",
            padding=5,
        )

    # ======================================================================
    # SHELL
    # ======================================================================

    def _build_shell(self):
        """
        Build header, scrollable body and fixed footer.
        """

        # ==============================================================
        # HEADER
        # ==============================================================

        header = tk.Frame(
            self,
            bg=PRIMARY,
            height=68,
        )

        header.pack(
            fill="x",
            side="top",
        )

        header.pack_propagate(False)

        title_frame = tk.Frame(
            header,
            bg=PRIMARY,
        )

        title_frame.pack(
            fill="both",
            expand=True,
            padx=22,
        )

        self.header_title_label = tk.Label(
            title_frame,
            text=self.title(),
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE,
            anchor="e",
        )

        self.header_title_label.pack(
            side="right",
            pady=(12, 0),
        )

        subtitle = tk.Label(
            title_frame,
            text="تنظیم محدوده داده و ستون‌های مورد نیاز برای خروجی Excel",
            font=FONT_SMALL,
            bg=PRIMARY,
            fg=WHITE,
            anchor="e",
        )

        subtitle.pack(
            side="right",
            padx=18,
            pady=(0, 8),
        )

        # ==============================================================
        # BODY
        # ==============================================================

        body = tk.Frame(
            self,
            bg=BG,
        )

        body.pack(
            fill="both",
            expand=True,
            side="top",
        )

        # --------------------------------------------------------------
        # Canvas
        # --------------------------------------------------------------

        self.canvas = tk.Canvas(
            body,
            bg=BG,
            highlightthickness=0,
            borderwidth=0,
        )

        self.canvas.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(10, 0),
            pady=10,
        )

        # --------------------------------------------------------------
        # Scrollbar
        # --------------------------------------------------------------

        self.scrollbar = tk.Scrollbar(
            body,
            orient="vertical",
            command=self.canvas.yview,
            bg=PRIMARY,
            activebackground=PRIMARY_LIGHT,
            troughcolor=BG,
            relief="flat",
            bd=0,
            highlightthickness=0,
            width=14,
        )

        self.scrollbar.pack(
            side="right",
            fill="y",
            padx=(0, 10),
            pady=10,
        )

        # --------------------------------------------------------------
        # Scrollable frame
        # --------------------------------------------------------------

        self.scroll_frame = tk.Frame(
            self.canvas,
            bg=BG,
        )

        self.scroll_window = self.canvas.create_window(
            (0, 0),
            window=self.scroll_frame,
            anchor="nw",
        )

        self.canvas.configure(
            yscrollcommand=self.scrollbar.set,
        )

        # --------------------------------------------------------------
        # Canvas events
        # --------------------------------------------------------------

        self.scroll_frame.bind(
            "<Configure>",
            self._on_scroll_frame_configure,
        )

        self.canvas.bind(
            "<Configure>",
            self._on_canvas_configure,
        )

        # --------------------------------------------------------------
        # Mouse wheel
        # --------------------------------------------------------------

        self.canvas.bind(
            "<MouseWheel>",
            self._on_mousewheel,
            add="+",
        )

        self.scroll_frame.bind(
            "<MouseWheel>",
            self._on_mousewheel,
            add="+",
        )

        body.bind(
            "<MouseWheel>",
            self._on_mousewheel,
            add="+",
        )

        # ==============================================================
        # FOOTER
        # ==============================================================

        self.footer = tk.Frame(
            self,
            bg=WHITE,
            height=70,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        self.footer.pack(
            fill="x",
            side="bottom",
        )

        self.footer.pack_propagate(False)

        # --------------------------------------------------------------
        # Cancel
        # --------------------------------------------------------------

        self.cancel_button = tk.Button(
            self.footer,
            text="انصراف",
            command=self.destroy,
            bg=BG,
            fg=TEXT,
            font=FONT_NORMAL,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=22,
            pady=9,
            activebackground=BORDER,
            activeforeground=TEXT,
        )

        self.cancel_button.pack(
            side="left",
            padx=(15, 8),
            pady=12,
        )

        # --------------------------------------------------------------
        # Export
        # --------------------------------------------------------------

        self.export_button = tk.Button(
            self.footer,
            text="📊  خروجی گرفتن",
            command=self._export,
            bg=PRIMARY,
            fg=WHITE,
            font=FONT_NORMAL,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=25,
            pady=9,
            activebackground=PRIMARY_LIGHT,
            activeforeground=WHITE,
        )

        self.export_button.pack(
            side="right",
            padx=(8, 15),
            pady=12,
        )

        # --------------------------------------------------------------
        # Status
        # --------------------------------------------------------------

        self.footer_status = tk.Label(
            self.footer,
            textvariable=self.selected_count_var,
            font=FONT_SMALL,
            bg=WHITE,
            fg=TEXT_LIGHT,
            anchor="e",
        )

        self.footer_status.pack(
            side="right",
            padx=10,
        )
    def _on_scroll_frame_configure(self, event=None):
        try:
            self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        except tk.TclError:
            pass

    def _on_canvas_configure(self, event=None):
        try:
            self.canvas.itemconfigure(
                self.scroll_window,
                width=max(1, self.canvas.winfo_width()),
            )

            self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        except tk.TclError:
            pass

    def _on_mousewheel(self, event):
        try:
            if self.winfo_exists():
                self.canvas.yview_scroll(
                    int(-1 * (event.delta / 120)),
                    "units",
                )
        except Exception:
            pass

    # ======================================================================
    # UI
    # ======================================================================

    def _build_ui(self):
        """
        Build common UI.
        """

        # ------------------------------------------------------------------
        # Main card
        # ------------------------------------------------------------------

        outer_card = tk.Frame(
            self.scroll_frame,
            bg=BORDER,
        )

        outer_card.pack(
            fill="x",
            padx=18,
            pady=18,
        )

        self.main_frame = tk.Frame(
            outer_card,
            bg=CARD_BG,
        )

        self.main_frame.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
        )

        # ------------------------------------------------------------------
        # Range
        # ------------------------------------------------------------------

        self._build_range_section()

        # ------------------------------------------------------------------
        # Column selector
        # ------------------------------------------------------------------

        self._build_column_selector()

        # ------------------------------------------------------------------
        # Options
        # ------------------------------------------------------------------

        self._build_options_section()

    # ======================================================================
    # RANGE SECTION
    # ======================================================================

    def _build_range_section(self):
        frame = tk.LabelFrame(
            self.main_frame,
            text="  محدوده داده‌ها  ",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            padx=15,
            pady=12,
        )

        frame.pack(
            fill="x",
            padx=15,
            pady=(15, 10),
        )

        for text, value in self.range_options:
            rb = tk.Radiobutton(
                frame,
                text=text,
                variable=self.data_range,
                value=value,
                bg=CARD_BG,
                fg=TEXT,
                activebackground=CARD_BG,
                activeforeground=PRIMARY,
                selectcolor=CARD_BG,
                font=FONT_NORMAL,
                anchor="e",
                cursor="hand2",
            )

            rb.pack(
                fill="x",
                anchor="e",
                pady=3,
            )

        self.date_frame = tk.Frame(
            frame,
            bg=CARD_BG,
        )

        date_inner = tk.Frame(
            self.date_frame,
            bg=CARD_BG,
        )

        date_inner.pack(
            fill="x",
            pady=(8, 0),
        )

        tk.Label(
            date_inner,
            text="از تاریخ:",
            bg=CARD_BG,
            fg=TEXT,
            font=FONT_SMALL,
        ).pack(
            side="right",
            padx=(5, 4),
        )

        self.start_date = JalaliDateEntry(
            date_inner,
            width=12,
        )

        self.start_date.set_date(
            tehran_now() - timedelta(days=30)
        )

        self.start_date.pack(
            side="right",
            padx=5,
        )

        tk.Label(
            date_inner,
            text="تا تاریخ:",
            bg=CARD_BG,
            fg=TEXT,
            font=FONT_SMALL,
        ).pack(
            side="right",
            padx=(18, 4),
        )

        self.end_date = JalaliDateEntry(
            date_inner,
            width=12,
        )

        self.end_date.set_date(
            tehran_now()
        )

        self.end_date.pack(
            side="right",
            padx=5,
        )

    # ======================================================================
    # COLUMN SELECTOR
    # ======================================================================

    def _build_column_selector(self):
        """
        Build the column-selection area.

        Every available column is checked by default.
        """

        frame = tk.LabelFrame(
            self.main_frame,
            text="  ستون‌های مورد نیاز برای خروجی  ",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            padx=15,
            pady=12,
        )

        frame.pack(
            fill="x",
            padx=15,
            pady=10,
        )

        # --------------------------------------------------------------
        # Header row
        # --------------------------------------------------------------

        top = tk.Frame(
            frame,
            bg=CARD_BG,
        )

        top.pack(
            fill="x",
            pady=(0, 10),
        )

        description = tk.Label(
            top,
            text="ستون‌هایی را که می‌خواهید در فایل Excel نمایش داده شوند انتخاب کنید.",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            anchor="e",
            justify="right",
        )

        description.pack(
            side="right",
        )

        # --------------------------------------------------------------
        # Select / deselect buttons
        # --------------------------------------------------------------

        button_frame = tk.Frame(
            top,
            bg=CARD_BG,
        )

        button_frame.pack(
            side="left",
        )

        select_all = tk.Button(
            button_frame,
            text="✓ انتخاب همه",
            command=self._select_all_columns,
            bg=PRIMARY,
            fg=WHITE,
            font=FONT_SMALL,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=5,
            activebackground=PRIMARY_LIGHT,
            activeforeground=WHITE,
        )

        select_all.pack(
            side="left",
            padx=3,
        )

        clear_all = tk.Button(
            button_frame,
            text="□ لغو همه",
            command=self._clear_all_columns,
            bg=BG,
            fg=TEXT,
            font=FONT_SMALL,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=5,
            activebackground=BORDER,
            activeforeground=TEXT,
        )

        clear_all.pack(
            side="left",
            padx=3,
        )

        # --------------------------------------------------------------
        # Selected counter
        # --------------------------------------------------------------

        counter = tk.Label(
            frame,
            textvariable=self.selected_count_var,
            font=FONT_SMALL,
            bg=BG,
            fg=PRIMARY,
            anchor="e",
            padx=10,
            pady=6,
        )

        counter.pack(
            fill="x",
            pady=(0, 10),
        )

        # --------------------------------------------------------------
        # Columns grid
        # --------------------------------------------------------------

        columns_container = tk.Frame(
            frame,
            bg=CARD_BG,
        )

        columns_container.pack(
            fill="x",
        )

        # Three columns looks cleaner on the dialog.
        grid_columns = 2

        for index, (key, label) in enumerate(
            self.column_definitions
        ):
            row = index // grid_columns
            col = index % grid_columns

            item = tk.Frame(
                columns_container,
                bg=CARD_BG,
            )

            item.grid(
                row=row,
                column=col,
                sticky="ew",
                padx=5,
                pady=4,
            )

            columns_container.grid_columnconfigure(
                col,
                weight=1,
            )

            check = tk.Checkbutton(
                item,
                text=label,
                variable=self.column_vars[key],
                bg=CARD_BG,
                fg=TEXT,
                activebackground=CARD_BG,
                activeforeground=PRIMARY,
                selectcolor=CARD_BG,
                font=FONT_NORMAL,
                anchor="e",
                justify="right",
                cursor="hand2",
                command=self._update_selected_count,
            )

            check.pack(
                fill="x",
                anchor="e",
            )

    def _select_all_columns(self):
        """
        Select all available export columns.
        """
        for variable in self.column_vars.values():
            variable.set(True)

        self._update_selected_count()

    def _clear_all_columns(self):
        """
        Clear all export columns.
        """
        for variable in self.column_vars.values():
            variable.set(False)

        self._update_selected_count()

    def _get_selected_columns(self):
        """
        Return selected column keys in the same order as the service
        definitions.
        """
        return [
            key
            for key, _label in self.column_definitions
            if self.column_vars[key].get()
        ]

    def _update_selected_count(self):
        selected = len(self._get_selected_columns())
        total = len(self.column_definitions)

        self.selected_count_var.set(
            f"ستون‌های انتخاب‌شده: {selected} از {total}"
        )

    # ======================================================================
    # OPTIONS SECTION
    # ======================================================================

    def _build_options_section(self):
        self.options_frame = tk.LabelFrame(
            self.main_frame,
            text="  تنظیمات خروجی  ",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            padx=15,
            pady=12,
        )

        self.options_frame.pack(
            fill="x",
            padx=15,
            pady=(0, 15),
        )

        self.details_check = tk.Checkbutton(
            self.options_frame,
            text="شامل جزئیات",
            variable=self.include_details,
            bg=CARD_BG,
            fg=TEXT,
            activebackground=CARD_BG,
            activeforeground=PRIMARY,
            selectcolor=CARD_BG,
            font=FONT_NORMAL,
            anchor="e",
            cursor="hand2",
        )

        self.details_check.pack(
            fill="x",
            pady=3,
        )

        self.stats_check = tk.Checkbutton(
            self.options_frame,
            text="شامل آمار",
            variable=self.include_stats,
            bg=CARD_BG,
            fg=TEXT,
            activebackground=CARD_BG,
            activeforeground=PRIMARY,
            selectcolor=CARD_BG,
            font=FONT_NORMAL,
            anchor="e",
            cursor="hand2",
        )

        self.stats_check.pack(
            fill="x",
            pady=3,
        )

    # ======================================================================
    # DATE RANGE
    # ======================================================================

    def _on_range_change(self, *args):
        if self.data_range.get() == "date_range":
            if not self.date_frame.winfo_manager():
                self.date_frame.pack(
                    fill="x",
                    pady=(4, 0),
                )
        else:
            self.date_frame.pack_forget()

        self._refresh_scroll_region()

    def _refresh_scroll_region(self):
        try:
            self.update_idletasks()

            self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        except Exception:
            pass

    # ======================================================================
    # DATA
    # ======================================================================

    def _get_data(self):
        """
        Subclasses override this.
        """
        return []

    # ======================================================================
    # EXPORT
    # ======================================================================

    def _export(self):
        """
        Subclasses override this.
        """
        pass

    # ======================================================================
    # VALIDATION
    # ======================================================================

    def _validate_columns(self):
        selected = self._get_selected_columns()

        if not selected:
            messagebox.showwarning(
                "انتخاب ستون",
                "حداقل یک ستون برای خروجی Excel انتخاب کنید.",
                parent=self,
            )
            return False

        return True

    # ======================================================================
    # FILENAME
    # ======================================================================

    def _ask_filename(self, prefix):
        return filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".xlsx",
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("All files", "*.*"),
            ],
            initialfile=(
                f"{prefix}_"
                f"{jalali_stamp()}.xlsx"
            ),
        )

    # ======================================================================
    # SUCCESS / ERROR
    # ======================================================================

    def _show_success(self):
        messagebox.showinfo(
            "موفق",
            "خروجی Excel با موفقیت ذخیره شد.",
            parent=self,
        )

        self.destroy()

    def _show_error(self, error):
        messagebox.showerror(
            "خطا",
            f"خطا در ایجاد خروجی:\n\n{error}",
            parent=self,
        )


# ============================================================================
# INSPECTION EXPORT
# ============================================================================

class InspectionExportDialog(BaseExportDialog):

    def __init__(
        self,
        parent,
        service,
        inspection=None,
        template=None,
    ):
        self.service = service
        self.inspection = inspection
        self.template = template

        self.include_checkpoints = tk.BooleanVar(value=True)
        self.include_comments = tk.BooleanVar(value=True)

        super().__init__(
            parent,
            "📤 خروجی بازرسی‌ها",
            export_type="inspections",
            width=760,
            height=780,
            range_options=[
                ("همه موارد", "all"),
                ("بازرسی انتخاب شده", "current"),
                ("بازرسی‌های قالب انتخاب شده", "template"),
                ("محدوده تاریخ", "date_range"),
            ],
        )

        self._add_inspection_options()

    def _add_inspection_options(self):
        """
        Add inspection-specific options.
        """
        tk.Label(
            self.options_frame,
            text="گزینه‌های اختصاصی بازرسی",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT_LIGHT,
            anchor="e",
        ).pack(
            fill="x",
            pady=(10, 4),
        )

        tk.Checkbutton(
            self.options_frame,
            text="شامل چک‌پوینت‌ها",
            variable=self.include_checkpoints,
            bg=CARD_BG,
            fg=TEXT,
            activebackground=CARD_BG,
            selectcolor=CARD_BG,
            font=FONT_NORMAL,
            anchor="e",
        ).pack(
            fill="x",
            pady=2,
        )

        tk.Checkbutton(
            self.options_frame,
            text="شامل نظرات",
            variable=self.include_comments,
            bg=CARD_BG,
            fg=TEXT,
            activebackground=CARD_BG,
            selectcolor=CARD_BG,
            font=FONT_NORMAL,
            anchor="e",
        ).pack(
            fill="x",
            pady=2,
        )

        self._refresh_scroll_region()

    def _get_data(self):
        range_type = self.data_range.get()

        if range_type == "current" and self.inspection:
            return [self.inspection]

        if range_type == "template" and self.template:
            try:
                all_ins = self.service.get_all_inspections()

                return [
                    ins
                    for ins in all_ins
                    if getattr(
                        getattr(ins, "template", None),
                        "id",
                        None,
                    ) == self.template.id
                    or getattr(
                        ins,
                        "template_id",
                        None,
                    ) == self.template.id
                ]
            except Exception:
                return []

        try:
            all_ins = self.service.get_all_inspections()
        except Exception:
            return []

        if range_type != "date_range":
            return all_ins

        start = self.start_date.get_date()
        end = self.end_date.get_date()

        if not start or not end:
            return all_ins

        start_date = _safe_date(start)
        end_date = _safe_date(end)

        if not start_date or not end_date:
            return all_ins

        filtered = []

        for ins in all_ins:
            started_at = getattr(
                ins,
                "started_at",
                None,
            )

            ins_date = _safe_date(started_at)

            if ins_date and start_date <= ins_date <= end_date:
                filtered.append(ins)

        return filtered

    def _inspection_to_dict(self, inspection):
        results = []

        if (
            self.include_checkpoints.get()
            and getattr(inspection, "results", None)
        ):
            for result in inspection.results:
                checkpoint = getattr(
                    result,
                    "checkpoint",
                    None,
                )

                checkpoint_title = (
                    getattr(
                        checkpoint,
                        "title",
                        None,
                    )
                    or "—"
                )

                result_code = getattr(
                    result,
                    "result",
                    "",
                )

                if result_code == "pass":
                    result_text = "قبول"
                elif result_code == "fail":
                    result_text = "رد"
                else:
                    result_text = "جزئی"

                results.append({
                    "checkpoint": checkpoint_title,
                    "result": result_text,
                    "comment": (
                        getattr(
                            result,
                            "comment",
                            "",
                        )
                        if self.include_comments.get()
                        else ""
                    ),
                })

        template = getattr(
            inspection,
            "template",
            None,
        )

        equipment = getattr(
            inspection,
            "equipment",
            None,
        )

        inspector = getattr(
            inspection,
            "inspector",
            None,
        )

        status = _enum_value(
            getattr(
                inspection,
                "status",
                "",
            )
        )

        overall_result = getattr(
            inspection,
            "overall_result",
            "",
        )

        if status == "in_progress":
            status_text = "در حال انجام"
        elif status == "completed":
            status_text = "تکمیل شده"
        elif status == "cancelled":
            status_text = "لغو شده"
        else:
            status_text = status

        if overall_result == "pass":
            result_text = "قبول"
        elif overall_result == "fail":
            result_text = "رد"
        elif overall_result == "partial":
            result_text = "جزئی"
        else:
            result_text = "—"

        started_at = getattr(
            inspection,
            "started_at",
            None,
        )

        completed_at = getattr(
            inspection,
            "completed_at",
            None,
        )

        return {
            "id": getattr(
                inspection,
                "id",
                "",
            ),

            "template_name": getattr(
                template,
                "name",
                None,
            ) or "—",

            "equipment_name": getattr(
                equipment,
                "name",
                None,
            ) or "—",

            "inspector_name": (
                getattr(
                    inspector,
                    "username",
                    None,
                )
                or getattr(
                    inspector,
                    "full_name",
                    None,
                )
                or "—"
            ),

            "status": status_text,

            "overall_result": result_text,

            "started_at": (
                to_jalali_datetime_str(started_at)
                if started_at
                else "—"
            ),

            "completed_at": (
                to_jalali_datetime_str(completed_at)
                if completed_at
                else "—"
            ),

            "notes": getattr(
                inspection,
                "notes",
                "",
            ) or "",

            "results": results,
        }

    def _export(self):
        if not self._validate_columns():
            return

        inspections = self._get_data()
        if not inspections:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!", parent=self)
            return

        filename = self._ask_filename("inspection_export")
        if not filename:
            return

        ins_dicts = [self._inspection_to_dict(ins) for ins in inspections]
        selected_columns = list(self._get_selected_columns())

        _run_export_with_wait(
            self,
            "خروجی Excel بازرسی‌ها",
            lambda: export_inspections_excel(ins_dicts, filename, selected_columns=selected_columns),
            self._show_success,
        )

# ============================================================================
# EQUIPMENT EXPORT
# ============================================================================

class EquipmentExportDialog(BaseExportDialog):

    def __init__(
        self,
        parent,
        equipment_list,
        selected_equipment=None,
    ):
        self.equipment_list = equipment_list
        self.selected_equipment = selected_equipment

        super().__init__(
            parent,
            "📤 خروجی تجهیزات",
            export_type="equipment",
            width=780,
            height=800,
            range_options=[
                ("همه موارد", "all"),
                ("تجهیز انتخاب شده", "current"),
                ("محدوده تاریخ", "date_range"),
            ],
        )

    def _get_data(self):
        range_type = self.data_range.get()

        if (
            range_type == "current"
            and self.selected_equipment
        ):
            return [self.selected_equipment]

        if range_type != "date_range":
            return self.equipment_list

        start = self.start_date.get_date()
        end = self.end_date.get_date()

        start_date = _safe_date(start)
        end_date = _safe_date(end)

        if not start_date or not end_date:
            return self.equipment_list

        filtered = []

        for eq in self.equipment_list:
            if not isinstance(eq, dict):
                continue

            date_value = (
                eq.get("updated_at")
                or eq.get("installation_date")
            )

            eq_date = _safe_date(date_value)

            if eq_date and start_date <= eq_date <= end_date:
                filtered.append(eq)

        return filtered

    def _export(self):
        if not self._validate_columns():
            return

        data = self._get_data()
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!", parent=self)
            return

        filename = self._ask_filename("equipment_export")
        if not filename:
            return

        selected_columns = list(self._get_selected_columns())
        _run_export_with_wait(
            self,
            "خروجی Excel تجهیزات",
            lambda: export_equipment_excel(data, filename, selected_columns=selected_columns),
            self._show_success,
        )

# ============================================================================
# PM EXPORT
# ============================================================================

class PMExportDialog(BaseExportDialog):

    def __init__(
        self,
        parent,
        pm_records,
        selected_pm=None,
        selected_pms=None,
    ):
        self.pm_records = list(pm_records or [])
        if selected_pms is None:
            self.selected_pms = [selected_pm] if selected_pm is not None else []
        else:
            self.selected_pms = list(selected_pms or [])
        self.selected_pm = self.selected_pms[0] if self.selected_pms else None

        selected_label = (
            f"برنامه‌های انتخاب‌شده ({len(self.selected_pms):,} مورد)"
            if self.selected_pms else "برنامه‌های انتخاب‌شده"
        )

        super().__init__(
            parent,
            "📤 خروجی برنامه‌های نت پیشگیرانه",
            export_type="pm",
            width=760,
            height=780,
            range_options=[
                ("همه موارد", "all"),
                (selected_label, "current"),
                ("محدوده تاریخ", "date_range"),
            ],
        )

    def _get_data(self):
        range_type = self.data_range.get()

        if range_type == "current":
            return list(self.selected_pms)

        if range_type != "date_range":
            return list(self.pm_records)

        start = _safe_date(
            self.start_date.get_date()
        )

        end = _safe_date(
            self.end_date.get_date()
        )

        if not start or not end:
            return self.pm_records

        filtered = []

        for pm in self.pm_records:
            value = (
                _get_value(pm, "next_due", None)
                or _get_value(pm, "last_done", None)
            )

            pm_date = _safe_date(value)

            if pm_date and start <= pm_date <= end:
                filtered.append(pm)

        return filtered

    def _export(self):
        if not self._validate_columns():
            return

        data = self._get_data()
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!", parent=self)
            return

        filename = self._ask_filename("pm_export")
        if not filename:
            return

        selected_columns = list(self._get_selected_columns())
        _run_export_with_wait(
            self,
            "خروجی Excel برنامه‌های نت پیشگیرانه",
            lambda: export_pm_excel(data, filename, selected_columns=selected_columns),
            self._show_success,
        )

# ============================================================================
# WORK ORDER EXPORT
# ============================================================================

class WorkOrderExportDialog(BaseExportDialog):

    def __init__(
        self,
        parent,
        wo_repo,
        selected_wo_id=None,
        selected_wo_ids=None,
    ):
        self.wo_repo = wo_repo
        if selected_wo_ids is None:
            self.selected_wo_ids = [selected_wo_id] if selected_wo_id is not None else []
        else:
            self.selected_wo_ids = list(selected_wo_ids or [])
        self.selected_wo_id = self.selected_wo_ids[0] if self.selected_wo_ids else None

        self.filter_pm = tk.BooleanVar(value=True)
        self.filter_cm = tk.BooleanVar(value=True)
        self.filter_em = tk.BooleanVar(value=True)
        self.filter_insp = tk.BooleanVar(value=True)

        self.equipment_category_var = tk.StringVar(
            value="همه"
        )

        self.status_filter = tk.StringVar(
            value="all"
        )

        self.equipment_combo = None
        self.eq_map = {}

        super().__init__(
            parent,
            "📤 خروجی دستورکارها",
            export_type="work_orders",
            width=820,
            height=850,
            range_options=[
                ("همه موارد", "all"),
                (
                    f"دستورکارهای انتخاب‌شده ({len(self.selected_wo_ids):,} مورد)"
                    if self.selected_wo_ids else "دستورکارهای انتخاب‌شده",
                    "current",
                ),
                ("محدوده تاریخ", "date_range"),
            ],
        )

        self._build_work_order_filters()
        self._load_equipment()

        self._refresh_scroll_region()

    # ======================================================================
    # WORK ORDER FILTERS
    # ======================================================================

    def _build_work_order_filters(self):
        main = self.main_frame

        # --------------------------------------------------------------
        # Status
        # --------------------------------------------------------------

        status_frame = tk.LabelFrame(
            main,
            text="  فیلتر وضعیت  ",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            padx=15,
            pady=12,
        )

        status_frame.pack(
            fill="x",
            padx=15,
            pady=(0, 10),
        )

        statuses = [
            ("همه", "all"),
            ("در انتظار تأیید", "pending_approval"),
            ("در انتظار", "pending"),
            ("در حال انجام", "in_progress"),
            ("درخواست اتمام", "finish_requested"),
            ("تأیید شده", "approved"),
            ("رد شده", "rejected"),
        ]

        for text, value in statuses:
            tk.Radiobutton(
                status_frame,
                text=text,
                variable=self.status_filter,
                value=value,
                bg=CARD_BG,
                fg=TEXT,
                activebackground=CARD_BG,
                selectcolor=CARD_BG,
                font=FONT_NORMAL,
                anchor="e",
                cursor="hand2",
            ).pack(
                fill="x",
                pady=2,
            )

        # --------------------------------------------------------------
        # Work order type
        # --------------------------------------------------------------

        type_frame = tk.LabelFrame(
            main,
            text="  نوع دستور کار  ",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            padx=15,
            pady=12,
        )

        type_frame.pack(
            fill="x",
            padx=15,
            pady=(0, 10),
        )

        type_options = [
            ("پیشگیرانه (PM)", self.filter_pm),
            ("اصلاحی (CM)", self.filter_cm),
            ("اضطراری (EM)", self.filter_em),
            ("بازرسی", self.filter_insp),
        ]

        for text, variable in type_options:
            tk.Checkbutton(
                type_frame,
                text=text,
                variable=variable,
                bg=CARD_BG,
                fg=TEXT,
                activebackground=CARD_BG,
                selectcolor=CARD_BG,
                font=FONT_NORMAL,
                anchor="e",
                cursor="hand2",
            ).pack(
                fill="x",
                pady=2,
            )

        # --------------------------------------------------------------
        # Equipment filters
        # --------------------------------------------------------------

        equipment_frame = tk.LabelFrame(
            main,
            text="  فیلتر تجهیزات  ",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT,
            padx=15,
            pady=12,
        )

        equipment_frame.pack(
            fill="x",
            padx=15,
            pady=(0, 10),
        )

        tk.Label(
            equipment_frame,
            text="دسته تجهیز:",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT,
            anchor="e",
        ).pack(
            fill="x",
            pady=(0, 4),
        )

        try:
            from database.equipment_repository import EquipmentRepository
            from database.db import SessionLocal

            eq_repo = EquipmentRepository(
                SessionLocal
            )

            categories = eq_repo.get_categories()

        except Exception:
            categories = []

        category_values = [
            "همه"
        ] + list(categories or [])

        self.category_combo = ttk.Combobox(
            equipment_frame,
            textvariable=self.equipment_category_var,
            values=category_values,
            state="readonly",
            width=30,
            font=FONT_SMALL,
            style="Export.TCombobox",
        )

        self.category_combo.pack(
            anchor="e",
            fill="x",
            pady=(0, 12),
        )

        tk.Label(
            equipment_frame,
            text="تجهیز خاص:",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=TEXT,
            anchor="e",
        ).pack(
            fill="x",
            pady=(0, 4),
        )

        try:
            from views.searchable_combobox import SearchableCombobox

            self.equipment_combo = SearchableCombobox(
                equipment_frame,
                font=FONT_SMALL,
                state="normal",
                width=35,
            )

            self.equipment_combo.pack(
                anchor="e",
                fill="x",
            )

        except Exception:
            self.equipment_combo = ttk.Combobox(
                equipment_frame,
                state="normal",
                width=35,
                font=FONT_SMALL,
                style="Export.TCombobox",
            )

            self.equipment_combo.pack(
                anchor="e",
                fill="x",
            )

    def _load_equipment(self):
        try:
            from database.equipment_repository import EquipmentRepository
            from database.db import SessionLocal

            eq_repo = EquipmentRepository(
                SessionLocal
            )

            eqs = eq_repo.get_all_equipment()

        except Exception:
            eqs = []

        eq_names = []

        self.eq_map = {}

        for eq in eqs or []:
            code = eq.get(
                "code",
                "",
            )

            name = eq.get(
                "name",
                "",
            )

            display = f"{code} - {name}"

            eq_names.append(display)

            self.eq_map[display] = eq.get(
                "id"
            )

        if self.equipment_combo is None:
            return

        try:
            self.equipment_combo.set_completion_list(
                eq_names
            )
        except Exception:
            try:
                self.equipment_combo["values"] = eq_names
            except Exception:
                pass

    # ======================================================================
    # WORK ORDER DATA
    # ======================================================================

    def _get_equipment_selection(self):
        if self.equipment_combo is None:
            return ""

        try:
            return self.equipment_combo.get()
        except Exception:
            return ""

    def _get_data(self):
        range_type = self.data_range.get()

        # --------------------------------------------------------------
        # Selected work order
        # --------------------------------------------------------------
        # Match PM / Equipment dialogs: a selected export is a direct,
        # single-record export and is not altered by the other filters.
        if range_type == "current":
            selected_work_orders = []
            for wo_id in self.selected_wo_ids:
                try:
                    wo = self.wo_repo.get_by_id(wo_id)
                except Exception:
                    wo = None
                if wo is not None:
                    selected_work_orders.append(wo)
            return selected_work_orders

        try:
            all_wos = self.wo_repo.get_all()
        except Exception:
            all_wos = []

        # --------------------------------------------------------------
        # Status
        # --------------------------------------------------------------

        status = self.status_filter.get()

        if status != "all":
            filtered = []

            for wo in all_wos:
                wo_status = getattr(
                    wo,
                    "status",
                    None,
                )

                status_value = _enum_value(
                    wo_status
                ).lower()

                status_name = _enum_name(
                    wo_status
                ).lower()

                if (
                    status_value == status
                    or status_name == status
                ):
                    filtered.append(wo)

            all_wos = filtered

        # --------------------------------------------------------------
        # Work order type
        # --------------------------------------------------------------

        allowed_types = []

        if self.filter_pm.get():
            allowed_types.extend([
                "PREVENTIVE",
                "PM",
            ])

        if self.filter_cm.get():
            allowed_types.append(
                "CORRECTIVE"
            )

        if self.filter_em.get():
            allowed_types.append(
                "EMERGENCY"
            )

        if self.filter_insp.get():
            allowed_types.append(
                "INSPECTION"
            )

        if allowed_types:
            filtered = []

            for wo in all_wos:
                wo_type = getattr(
                    wo,
                    "type",
                    None,
                )

                type_name = _enum_name(
                    wo_type
                ).upper()

                type_value = _enum_value(
                    wo_type
                ).upper()

                if (
                    type_name in allowed_types
                    or type_value in allowed_types
                ):
                    filtered.append(wo)

            all_wos = filtered
        else:
            # If user explicitly unchecks all types,
            # there should be no results.
            all_wos = []

        # --------------------------------------------------------------
        # Equipment category
        # --------------------------------------------------------------

        category = self.equipment_category_var.get()

        if category and category != "همه":
            filtered = []

            for wo in all_wos:
                equipment = getattr(
                    wo,
                    "equipment",
                    None,
                )

                equipment_category = getattr(
                    equipment,
                    "category",
                    None,
                )

                if equipment_category == category:
                    filtered.append(wo)

            all_wos = filtered

        # --------------------------------------------------------------
        # Specific equipment
        # --------------------------------------------------------------

        eq_display = self._get_equipment_selection()

        if eq_display and eq_display in self.eq_map:
            eq_id = self.eq_map[eq_display]

            all_wos = [
                wo
                for wo in all_wos
                if getattr(
                    wo,
                    "equipment_id",
                    None,
                ) == eq_id
            ]

        # --------------------------------------------------------------
        # Date range
        # --------------------------------------------------------------

        if self.data_range.get() == "date_range":
            start = _safe_date(
                self.start_date.get_date()
            )

            end = _safe_date(
                self.end_date.get_date()
            )

            if start and end:
                filtered = []

                for wo in all_wos:
                    scheduled_date = getattr(
                        wo,
                        "scheduled_date",
                        None,
                    )

                    wo_date = _safe_date(
                        scheduled_date
                    )

                    if (
                        wo_date
                        and start <= wo_date <= end
                    ):
                        filtered.append(wo)

                all_wos = filtered

        return all_wos

    def _export(self):
        if not self._validate_columns():
            return

        data = self._get_data()
        if not data:
            messagebox.showwarning(
                "هشدار",
                "داده‌ای با فیلترهای انتخاب‌شده برای خروجی وجود ندارد.",
                parent=self,
            )
            return

        filename = self._ask_filename("work_orders")
        if not filename:
            return

        selected_columns = list(self._get_selected_columns())
        _run_export_with_wait(
            self,
            "خروجی Excel دستورکارها",
            lambda: export_work_orders_excel(data, filename, selected_columns=selected_columns),
            self._show_success,
        )

# ============================================================================
# REPAIR REQUEST EXPORT
# ============================================================================

class RepairRequestExportDialog(BaseExportDialog):
    """Excel export dialog for صدور حکم درخواست تعمیرات."""

    def __init__(
        self,
        parent,
        records,
        selected_request=None,
        selected_requests=None,
    ):
        self.records = list(records or [])
        if selected_requests is None:
            self.selected_requests = [selected_request] if selected_request is not None else []
        else:
            self.selected_requests = list(selected_requests or [])
        self.selected_request = self.selected_requests[0] if self.selected_requests else None

        selected_label = (
            f"درخواست‌های انتخاب‌شده ({len(self.selected_requests):,} مورد)"
            if self.selected_requests else "درخواست‌های انتخاب‌شده"
        )

        super().__init__(
            parent,
            "📤 خروجی حکم درخواست تعمیرات",
            export_type="repair_requests",
            width=800,
            height=820,
            range_options=[
                ("همه موارد", "all"),
                (selected_label, "current"),
                ("محدوده تاریخ", "date_range"),
            ],
        )

    def _get_data(self):
        range_type=self.data_range.get()
        if range_type == "current":
            return list(self.selected_requests)
        data=list(self.records)
        if range_type != "date_range":
            return data
        start=_safe_date(self.start_date.get_date())
        end=_safe_date(self.end_date.get_date())
        if not start or not end:
            return data
        if start > end:
            start,end=end,start
        return [
            record for record in data
            if (_record_date := _safe_date(_get_value(record, "breakdown_datetime", None))) is not None
            and start <= _record_date <= end
        ]

    def _export(self):
        if not self._validate_columns():
            return
        data=self._get_data()
        if not data:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!", parent=self)
            return
        filename=self._ask_filename("repair_requests")
        if not filename:
            return
        selected_columns=list(self._get_selected_columns())
        _run_export_with_wait(
            self,
            "خروجی Excel حکم درخواست تعمیرات",
            lambda: export_repair_requests_excel(data, filename, selected_columns=selected_columns),
            self._show_success,
        )

# ============================================================================
# SPARE PARTS EXPORT
# ============================================================================

class SparePartsExportDialog(BaseExportDialog):

    def __init__(
        self,
        parent,
        parts_list,
    ):
        self.parts_list = parts_list

        super().__init__(
            parent,
            "📤 خروجی قطعات یدکی",
            export_type="spare_parts",
            width=760,
            height=780,
            range_options=[
                ("همه موارد", "all"),
            ],
        )

    def _get_data(self):
        return self.parts_list

    def _export(self):
        if not self._validate_columns():
            return

        if not self.parts_list:
            messagebox.showwarning("هشدار", "داده‌ای برای خروجی وجود ندارد!", parent=self)
            return

        filename = self._ask_filename("spare_parts")
        if not filename:
            return

        data = list(self.parts_list)
        selected_columns = list(self._get_selected_columns())
        _run_export_with_wait(
            self,
            "خروجی Excel قطعات یدکی",
            lambda: export_spare_parts_excel(data, filename, selected_columns=selected_columns),
            self._show_success,
        )

# ============================================================================
# RUN HELPERS
# ============================================================================

def run_inspection_export(
    parent,
    service,
    selected_inspection_id=None,
    selected_template=None,
):
    inspection = None

    if selected_inspection_id:
        try:
            inspection = service.get_inspection(
                selected_inspection_id
            )
        except Exception:
            inspection = None

    dialog = InspectionExportDialog(
        parent,
        service,
        inspection,
        selected_template,
    )

    parent.wait_window(dialog)


def run_equipment_export(
    parent,
    equipment_list,
    selected_equipment=None,
):
    dialog = EquipmentExportDialog(
        parent,
        equipment_list,
        selected_equipment,
    )

    parent.wait_window(dialog)


def run_pm_export(
    parent,
    pm_records,
    selected_pm=None,
    selected_pms=None,
):
    dialog = PMExportDialog(
        parent,
        pm_records,
        selected_pm=selected_pm,
        selected_pms=selected_pms,
    )
    parent.wait_window(dialog)
def run_work_order_export(
    parent,
    wo_repo,
    selected_wo_id=None,
    selected_wo_ids=None,
):
    dialog = WorkOrderExportDialog(
        parent,
        wo_repo,
        selected_wo_id=selected_wo_id,
        selected_wo_ids=selected_wo_ids,
    )
    parent.wait_window(dialog)



def run_repair_request_export(
    parent,
    requests=None,
    selected_request=None,
    selected_requests=None,
):
    """Open the repair-request Excel export dialog.

    Kept as a public helper because RepairRequestView imports this function
    directly from views.export_dialog.
    """
    dialog = RepairRequestExportDialog(
        parent,
        requests or [],
        selected_request=selected_request,
        selected_requests=selected_requests,
    )
    parent.wait_window(dialog)


def run_spare_parts_export(
    parent,
    parts_list,
):
    dialog = SparePartsExportDialog(
        parent,
        parts_list,
    )

    parent.wait_window(dialog)