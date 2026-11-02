# views/main_view.py

"""
PM System - Main Application Window
===================================

Main application shell and routing.

Current personnel / department workflow
---------------------------------------

1. Work Order / PM creation:
       Equipment + Department

2. No Personnel/User technician is selected at creation time.

3. Finish workflow:
       Work Order Department
              ->
       Personnel belonging to that Department
              ->
       selected Personnel
              ->
       completed_by_personnel_id

4. Managers/Admins can manage:
       - Departments
       - Personnel
       - Department assignment of Personnel

This file is UI/routing only.

It does NOT:
    - run database migrations
    - modify existing SQL records
    - change Work Order repository logic
    - assign Personnel automatically
"""


import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox


from database.db import SessionLocal


# ============================================================================
# OPTIONAL WINDOWS SOUND
# ============================================================================

try:
    import winsound
except Exception:
    winsound = None


# ============================================================================
# MATPLOTLIB
# ============================================================================

os.environ.setdefault(
    "MPLBACKEND",
    "TkAgg",
)


# ============================================================================
# GLOBALS
# ============================================================================

ROLE_FA = None
MENU_ITEMS = None
_theme = None


# ============================================================================
# THEME
# ============================================================================

def _get_theme():
    global _theme

    if _theme is None:

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

        _theme = {
            "NAVY": NAVY,
            "NAVY_LIGHT": NAVY_LIGHT,
            "WHITE": WHITE,
            "RED": RED,
            "GRAY_BG": GRAY_BG,
            "GRAY_BORDER": GRAY_BORDER,
            "TEXT_DARK": TEXT_DARK,
            "TEXT_LIGHT": TEXT_LIGHT,
            "SUCCESS": SUCCESS,
            "WARNING": WARNING,
            "FONT_TITLE": FONT_TITLE,
            "FONT_HEADING": FONT_HEADING,
            "FONT_NORMAL": FONT_NORMAL,
            "FONT_SMALL": FONT_SMALL,
        }

    return _theme


# ============================================================================
# MENU
# ============================================================================

def _get_menu_items():

    global MENU_ITEMS

    if MENU_ITEMS is None:

        from database.models import UserRole

        MENU_ITEMS = [

            (
                "📊  داشبورد",
                "dashboard",
                UserRole.TECHNICIAN.value,
            ),

            (
                "⚙️  تجهیزات",
                "equipment",
                UserRole.TECHNICIAN.value,
            ),

            (
                "📅  برنامه PM",
                "pm_schedule",
                UserRole.MANAGER.value,
            ),

            (
                "📝  دستور کارها",
                "work_orders",
                UserRole.TECHNICIAN.value,
            ),

            (
                "📄  صدور حکم درخواست تعمیرات",
                "repair_request",
                UserRole.TECHNICIAN.value,
            ),

            (
                "👷  مدیریت پرسنل و دپارتمان‌ها",
                "personnel_management",
                UserRole.MANAGER.value,
            ),

            (
                "🔍  بازرسی‌ها",
                "inspection",
                UserRole.TECHNICIAN.value,
            ),

            (
                "🔧  قطعات یدکی",
                "spare_parts",
                UserRole.TECHNICIAN.value,
            ),

            (
                "📈  تحلیل و گزارشات",
                "reports",
                UserRole.TECHNICIAN.value,
            ),

            (
                "👥  مدیریت کاربران",
                "users",
                UserRole.ADMIN.value,
            ),

            (
                "📋  لاگ فعالیت",
                "activity_log",
                UserRole.ADMIN.value,
            ),

            (
                "⏱️  ساعت کار ماشین",
                "machine_hours",
                UserRole.TECHNICIAN.value,
            ),
        ]

    return MENU_ITEMS


# ============================================================================
# ROLES
# ============================================================================

def _get_role_fa():

    global ROLE_FA

    if ROLE_FA is None:

        from database.models import UserRole

        ROLE_FA = {
            UserRole.ADMIN.value:
                "مدیر سیستم",

            UserRole.MANAGER.value:
                "مدیر",

            UserRole.TECHNICIAN.value:
                "تکنسین",

            UserRole.PRODUCTION_EXPERT.value:
                "کارشناس تولید",
        }

    return ROLE_FA


def _is_custom_role(
    role: str,
) -> bool:

    try:

        from database.models import UserRole

        return role not in {
            item.value
            for item in UserRole
        }

    except Exception:

        return False


# ============================================================================
# VIEW METADATA
# ============================================================================

VIEW_META = {
    "dashboard": ("📊", "داشبورد مدیریت", "نمای کلی و وضعیت عملیات نگهداری"),
    "equipment": ("⚙", "تجهیزات", "مدیریت شناسنامه و وضعیت تجهیزات"),
    "pm_schedule": ("📅", "برنامه PM", "برنامه‌ریزی نگهداری پیشگیرانه"),
    "work_orders": ("📝", "دستورکارها", "ایجاد، اجرا و پیگیری دستورکارها"),
    "repair_request": ("📄", "حکم درخواست تعمیرات", "ثبت و پیگیری درخواست‌های تعمیراتی"),
    "personnel_management": ("👷", "پرسنل و دپارتمان‌ها", "مدیریت منابع انسانی نگهداری"),
    "inspection": ("🔍", "بازرسی‌ها", "بازرسی، چک‌پوینت و نتایج"),
    "spare_parts": ("🔧", "قطعات یدکی", "موجودی و عملیات قطعات"),
    "reports": ("📈", "تحلیل و گزارشات", "گزارش‌های مدیریتی و تحلیلی"),
    "users": ("👥", "مدیریت کاربران", "کاربران و سطح دسترسی"),
    "activity_log": ("📋", "لاگ فعالیت", "ثبت رویدادهای سامانه"),
    "machine_hours": ("⏱", "ساعت کار ماشین", "ثبت شیفتی ساعات کار و توقف‌ها"),
}


# ============================================================================
# RESOURCE PATH
# ============================================================================

def resource_path(
    relative_path,
):

    try:

        base_path = sys._MEIPASS

    except Exception:

        base_path = os.path.dirname(
            os.path.dirname(
                os.path.abspath(
                    __file__
                )
            )
        )

    return os.path.join(
        base_path,
        relative_path,
    )


# ============================================================================
# MAIN VIEW
# ============================================================================

class MainView(tk.Tk):

    # =========================================================================
    # INIT
    # =========================================================================

    def __init__(
        self,
    ):

        super().__init__()

        self._destroyed = False

        self._after_id = None
        self._notify_after_id = None
        self._resize_after_id = None

        self._auto_pm_service = None

        self._user_repo = None
        self._equipment_repo = None
        self._pm_repo = None
        self._wo_repo = None
        self._personnel_repo = None
        self._department_repo = None

        self._current_view = None
        self._current_view_key = None

        self._fullscreen = False
        self._windowed_geometry = None
        self._sidebar_collapsed = False
        self._sidebar_buttons = {}
        self._sidebar_button_labels = {}

        self._mousewheel_canvas = None

        self._configure_application()

        try:
            from views.ux import install_dialogs
            install_dialogs()
        except Exception as exc:
            print("ux dialogs:", exc)

        self._setup_styles()

        self._setup_window()

        self._setup_bindings()

        self._build_ui()

        self.after_idle(
            self._deferred_startup
        )

        self._start_notifications()

        # Silent-update countdown (reads a local status file only).
        try:
            from utils.update_client import start_update_watcher
            start_update_watcher(self)
        except Exception as exc:
            print("Update watcher error:", exc)

    # =========================================================================
    # APPLICATION CONFIGURATION
    # =========================================================================

    def _configure_application(
        self,
    ):

        self.title(
            "سیستم مدیریت نگهداری و تعمیرات"
        )

        self.configure(
            bg=_get_theme()["GRAY_BG"]
        )

        try:

            icon_path = resource_path(
                "gela-logo.ico"
            )

            if os.path.exists(
                icon_path
            ):

                self.iconbitmap(
                    icon_path
                )

        except Exception as exc:

            print(
                "Icon error:",
                exc,
            )

    # =========================================================================
    # STYLES
    # =========================================================================

    def _setup_styles(
        self,
    ):

        t = _get_theme()
        from utils.theme import apply_app_theme
        apply_app_theme(self)  # shared base look (fonts, tables, inputs)
        style = ttk.Style(self)

        try:
            from utils.theme import ensure_theme
            ensure_theme(style)  # never switch the global ttk theme per page
        except Exception:
            pass

        # Main content and navigation scrollbars.
        for name, background, trough, width in (
            ("PM.Vertical.TScrollbar", t["NAVY_LIGHT"], t["GRAY_BG"], 11),
            ("PM.Sidebar.TScrollbar", t["NAVY_LIGHT"], t["NAVY"], 9),
            ("PM.Content.TScrollbar", "#C3CCD8", t["GRAY_BG"], 10),
        ):
            style.configure(
                name,
                background=background,
                troughcolor=trough,
                arrowcolor=t["WHITE"],
                bordercolor=trough,
                lightcolor=background,
                darkcolor=t["NAVY"],
                width=width,
            )
            try:
                base_layout = style.layout("Vertical.TScrollbar")
                if base_layout:
                    style.layout(name, base_layout)
            except Exception:
                pass

        style.map(
            "PM.Vertical.TScrollbar",
            background=[("active", t["NAVY"]), ("pressed", t["NAVY"])],
        )
        style.map(
            "PM.Sidebar.TScrollbar",
            background=[("active", t["WHITE"]), ("pressed", t["WHITE"])],
        )
        style.map(
            "PM.Content.TScrollbar",
            background=[("active", t["NAVY"]), ("pressed", t["NAVY"])],
        )

        style.configure("PM.TCombobox", padding=6)
        style.configure("PM.Top.TButton", padding=(10, 6))


    def _setup_window(
        self,
    ):

        self.update_idletasks()

        screen_w = (
            self.winfo_screenwidth()
        )

        screen_h = (
            self.winfo_screenheight()
        )

        min_w = min(
            1000,
            max(
                800,
                screen_w - 80,
            ),
        )

        min_h = min(
            650,
            max(
                560,
                screen_h - 100,
            ),
        )

        self.minsize(
            min_w,
            min_h,
        )

        self._windowed_geometry = (
            self._calculate_windowed_geometry()
        )

        try:

            self.attributes(
                "-fullscreen",
                True,
            )

            self._fullscreen = True

        except Exception:

            self._fullscreen = False

            self.geometry(
                self._windowed_geometry
            )

    # =========================================================================
    # RESPONSIVE GEOMETRY
    # =========================================================================

    def _calculate_windowed_geometry(
        self,
    ):

        screen_w = (
            self.winfo_screenwidth()
        )

        screen_h = (
            self.winfo_screenheight()
        )

        target_w = int(
            screen_w * 0.90
        )

        target_h = int(
            screen_h * 0.88
        )

        target_w = max(
            900,
            target_w,
        )

        target_h = max(
            560,
            target_h,
        )

        target_w = min(
            target_w,
            screen_w - 30,
        )

        target_h = min(
            target_h,
            screen_h - 60,
        )

        x = max(
            0,
            (
                screen_w
                - target_w
            ) // 2,
        )

        y = max(
            0,
            (
                screen_h
                - target_h
            ) // 2,
        )

        return (
            f"{target_w}x{target_h}"
            f"+{x}+{y}"
        )

    # =========================================================================
    # FULLSCREEN
    # =========================================================================

    def _toggle_fullscreen(
        self,
        event=None,
    ):

        if self._destroyed:
            return "break"

        try:

            currently_fullscreen = bool(
                self.attributes(
                    "-fullscreen"
                )
            )

        except Exception:

            currently_fullscreen = (
                self._fullscreen
            )

        if currently_fullscreen:

            # -----------------------------------------------------------------
            # Leave fullscreen
            # -----------------------------------------------------------------

            try:

                current_geometry = (
                    self.geometry()
                )

                if current_geometry:
                    self._windowed_geometry = (
                        current_geometry
                    )

            except Exception:

                pass

            try:

                self.attributes(
                    "-fullscreen",
                    False,
                )

            except Exception:

                pass

            self._fullscreen = False

            self.geometry(
                self._windowed_geometry
                or self._calculate_windowed_geometry()
            )

        else:

            # -----------------------------------------------------------------
            # Enter fullscreen
            # -----------------------------------------------------------------

            try:

                current_geometry = (
                    self.geometry()
                )

                if current_geometry:
                    self._windowed_geometry = (
                        current_geometry
                    )

            except Exception:

                pass

            try:

                self.attributes(
                    "-fullscreen",
                    True,
                )

            except Exception:

                pass

            self._fullscreen = True

        self.after_idle(
            self._refresh_layout
        )

        return "break"

    # =========================================================================
    # BINDINGS
    # =========================================================================

    def _setup_bindings(
        self,
    ):

        self.bind(
            "<Escape>",
            self._leave_fullscreen,
        )

        self.bind(
            "<F11>",
            self._toggle_fullscreen,
        )

        self.bind(
            "<F5>",
            self._global_f5,
        )

        self.bind(
            "<Delete>",
            self._global_delete,
        )

        self.bind(
            "<Return>",
            self._global_enter,
        )

        self.bind(
            "<Configure>",
            self._on_window_configure,
            add="+",
        )

        try:
            from views import shortcuts
            shortcuts.install(self)
        except Exception as exc:
            print("Shortcut setup error:", exc)

    def _show_shortcuts_help(self, event=None):
        from views import shortcuts
        shortcuts.show_help(self)
        return "break"

    def _leave_fullscreen(self, event=None):
        """Esc only leaves full screen; it never enters it."""
        try:
            if bool(self.attributes("-fullscreen")):
                return self._toggle_fullscreen()
        except Exception:
            pass
        return None

    # =========================================================================
    # WINDOW RESIZE
    # =========================================================================

    def _on_window_configure(
        self,
        event=None,
    ):

        if self._destroyed:
            return

        if event is None:
            return

        if event.widget is not self:
            return

        if self._resize_after_id:

            try:

                self.after_cancel(
                    self._resize_after_id
                )

            except Exception:

                pass

        self._resize_after_id = (
            self.after(
                100,
                self._refresh_layout,
            )
        )

    def _refresh_layout(
        self,
    ):

        if self._destroyed:
            return

        try:

            self.update_idletasks()

        except Exception:

            return

        try:

            self._update_responsive_sidebar()

        except Exception:

            pass

        try:

            self._update_content_scrollregion()

        except Exception:

            pass

        try:

            self._notify_current_view_resize()

        except Exception:

            pass

    # =========================================================================
    # REPOSITORIES
    # =========================================================================

    @property
    def user_repo(
        self,
    ):

        if self._user_repo is None:

            from database.user_repository import (
                UserRepository
            )

            self._user_repo = (
                UserRepository(
                    SessionLocal
                )
            )

        return self._user_repo

    @property
    def equipment_repo(
        self,
    ):

        if self._equipment_repo is None:

            from database.equipment_repository import (
                EquipmentRepository
            )

            self._equipment_repo = (
                EquipmentRepository(
                    SessionLocal
                )
            )

        return self._equipment_repo

    @property
    def pm_repo(
        self,
    ):

        if self._pm_repo is None:

            from database.pm_repository import (
                PMRepository
            )

            self._pm_repo = (
                PMRepository(
                    SessionLocal
                )
            )

        return self._pm_repo

    @property
    def wo_repo(
        self,
    ):

        if self._wo_repo is None:

            from database.work_order_repository import (
                WorkOrderRepository
            )

            self._wo_repo = (
                WorkOrderRepository(
                    SessionLocal
                )
            )

        return self._wo_repo

    @property
    def personnel_repo(
        self,
    ):

        if self._personnel_repo is None:

            from database.personnel_repository import (
                PersonnelRepository
            )

            self._personnel_repo = (
                PersonnelRepository(
                    SessionLocal
                )
            )

        return self._personnel_repo

    @property
    def department_repo(
        self,
    ):

        if self._department_repo is None:

            from database.department_repository import (
                DepartmentRepository
            )

            self._department_repo = (
                DepartmentRepository(
                    SessionLocal
                )
            )

        return self._department_repo

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def _deferred_startup(
        self,
    ):

        if self._destroyed:
            return

        try:

            self._show_view(
                "dashboard"
            )

        except Exception as exc:

            print(
                "Dashboard startup error:",
                exc,
            )

        try:

            from services.auto_pm_service import (
                AutoPMService
            )

            self._auto_pm_service = (
                AutoPMService(
                    check_interval_seconds=10
                )
            )

            self._auto_pm_service.start()

        except Exception as exc:

            print(
                "Auto PM Service error:",
                exc,
            )

    def destroy(
        self,
    ):

        if self._destroyed:
            return

        self._destroyed = True

        try:
            from views.ui_kit import cancel_pending_afters
            cancel_pending_afters(self)
        except Exception:
            pass

        callbacks = [
            self._after_id,
            self._notify_after_id,
            self._resize_after_id,
        ]

        for callback_id in callbacks:

            if callback_id:

                try:

                    self.after_cancel(
                        callback_id
                    )

                except Exception:

                    pass

        if self._auto_pm_service:

            try:

                self._auto_pm_service.stop()

            except Exception as exc:

                print(
                    "Auto PM service stop error:",
                    exc,
                )

            self._auto_pm_service = None

        self._mousewheel_canvas = None

        # Leave full screen and hide at once: even if a page fails to close
        # below, no empty full-screen window may stay behind the login window
        # (seen on a client PC after «خروج از سیستم»).
        for step in (
            lambda: self.attributes("-fullscreen", False),
            self.withdraw,
        ):
            try:
                step()
            except Exception:
                pass

        # Close the pages one by one. Tk's own destroy stops at the first
        # child that raises and then never closes the window itself.
        from utils.error_log import log_error

        for child in list(self.children.values()):
            try:
                child.destroy()
            except Exception as exc:
                log_error(f"Main window: closing {child.__class__.__name__} failed", exc)

        try:

            super().destroy()

        except Exception as exc:

            log_error("Main window: destroy failed, closing it directly", exc)

            # make sure the window and its Tcl interpreter state are gone,
            # and that the next window (login) becomes the default root
            try:
                self.tk.call("destroy", self._w)
            except Exception:
                pass

            import tkinter as _tk

            if getattr(_tk, "_default_root", None) is self:
                _tk._default_root = None

    # =========================================================================
    # KEYBOARD
    # =========================================================================

    def _is_editing(
        self,
    ):

        try:

            focused = (
                self.focus_get()
            )

            return isinstance(
                focused,
                (
                    tk.Entry,
                    tk.Text,
                    ttk.Entry,
                    ttk.Combobox,
                ),
            )

        except Exception:

            return False

    def _global_enter(
        self,
        event=None,
    ):

        if self._destroyed:
            return

        if self._is_editing():
            return

        try:

            for child in (
                self.content_frame
                .winfo_children()
            ):

                if hasattr(
                    child,
                    "handle_enter",
                ):

                    child.handle_enter()

                    return

        except Exception:

            pass

    def _global_f5(
        self,
        event=None,
    ):

        if self._destroyed:
            return "break"

        self._refresh_current_view()

        return "break"

    def _global_delete(
        self,
        event=None,
    ):

        if self._destroyed:
            return

        if self._is_editing():
            return

        try:

            for child in (
                self.content_frame
                .winfo_children()
            ):

                if hasattr(
                    child,
                    "handle_delete",
                ):

                    child.handle_delete()

                    return

        except Exception:

            pass

    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================

    # Unfinished work-order reminder: shown right after login and then every
    # 10 minutes, only for these roles.
    NOTIFY_ROLES = ("technician", "manager")
    NOTIFY_INTERVAL_MS = 10 * 60 * 1000

    def _start_notifications(
        self,
    ):
        """Schedule the reminder loop (first check shortly after login)."""
        if self._destroyed:
            return
        try:
            from auth.auth_manager import AuthManager
            user = AuthManager.get_current_user()
        except Exception:
            user = None
        if not user or getattr(user, "role", None) not in self.NOTIFY_ROLES:
            return
        self._notify_user = user
        self._notify_after_id = self.after(2500, self._notification_tick)

    def _notification_tick(self):
        if self._destroyed:
            return
        self._check_notifications()
        try:
            self._notify_after_id = self.after(self.NOTIFY_INTERVAL_MS, self._notification_tick)
        except Exception:
            self._notify_after_id = None

    def _check_notifications(
        self,
    ):
        """
        Query unfinished work orders in a background thread (the window never
        freezes on a slow network) and show a non-blocking RTL toast.

        technician: work orders assigned to this user (legacy technician link)
        manager:    all pending / in-progress work orders
        """
        if getattr(self, "_notify_running", False):
            return
        user = getattr(self, "_notify_user", None)
        if user is None:
            return
        self._notify_running = True
        import threading

        def work():
            items, error = [], None
            try:
                from database.work_order_repository import WorkOrderRepository
                repo = WorkOrderRepository(SessionLocal)
                from database.work_order import WorkOrderStatus
                all_wos = []
                # Two narrow queries instead of loading every work order.
                for status in (WorkOrderStatus.PENDING, WorkOrderStatus.IN_PROGRESS):
                    try:
                        if user.role == "technician":
                            all_wos += repo.get_all(status_filter=status, technician_id=user.id) or []
                        else:
                            all_wos += repo.get_all(status_filter=status) or []
                    except TypeError:
                        pass
                for wo in all_wos or []:
                    status_name = (getattr(getattr(wo, "status", None), "name", "") or "").upper()
                    if status_name not in ("PENDING", "IN_PROGRESS"):
                        continue
                    equipment = getattr(wo, "equipment", None)
                    items.append((
                        getattr(wo, "created_at", None),
                        getattr(wo, "title", None) or "بدون عنوان",
                        getattr(equipment, "name", None) or "نامشخص",
                        status_name,
                    ))
            except Exception as exc:  # network / DB problems: stay silent
                error = exc
            try:
                self.after(0, lambda: self._show_notification(items, error))
            except Exception:
                self._notify_running = False

        threading.Thread(target=work, name="PM-WO-Reminder", daemon=True).start()

    def _show_notification(self, items, error):
        self._notify_running = False
        if self._destroyed:
            return
        if error is not None:
            print("Notification error:", error)
            return
        old = getattr(self, "_notify_toast", None)
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
            self._notify_toast = None
        if not items:
            return

        import datetime as _dt
        items.sort(key=lambda it: it[0] or _dt.datetime.max)
        in_progress = sum(1 for it in items if it[3] == "IN_PROGRESS")
        lines = [f"در انتظار: {len(items) - in_progress}   •   در حال انجام: {in_progress}"]
        for _created, title, equipment, _status in items[:4]:
            lines.append(f"\u200f• {title}  ({equipment})")  # RLM keeps the bullet on the right
        if len(items) > 4:
            lines.append(f"و {len(items) - 4} دستور کار دیگر...")

        if winsound:
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                pass
        try:
            from views.ui_kit import Toast
            self._notify_toast = Toast(
                self,
                f"یادآوری: {len(items)} دستور کار ناتمام",
                lines,
                tone="warning",
                action_text="مشاهده دستور کارها",
                action=lambda: self._show_view("work_orders"),
                timeout_ms=60000,
            )
        except Exception as exc:
            print("Notification toast error:", exc)

    # =========================================================================
    # MAIN UI
    # =========================================================================

    def _build_ui(
        self,
    ):

        from auth.auth_manager import (
            AuthManager
        )

        t = _get_theme()

        try:

            user = (
                AuthManager
                .get_current_user()
            )

        except Exception as exc:

            print(
                "Current user error:",
                exc,
            )

            user = None

        if not user:

            self._build_no_user_ui()

            return

        # ---------------------------------------------------------------------
        # SIDEBAR
        # ---------------------------------------------------------------------

        self.sidebar_container = (
            tk.Frame(
                self,
                bg=t["NAVY"],
                bd=0,
                highlightthickness=0,
                width=290,
            )
        )

        self.sidebar_container.pack(
            side="right",
            fill="y",
        )

        self.sidebar_container.pack_propagate(
            False
        )

        self._build_sidebar(
            self.sidebar_container,
            user,
        )

        # ---------------------------------------------------------------------
        # CONTENT
        # ---------------------------------------------------------------------

        self.content_container = (
            tk.Frame(
                self,
                bg=t["GRAY_BG"],
                bd=0,
                highlightthickness=0,
            )
        )

        self.content_container.pack(
            side="left",
            fill="both",
            expand=True,
        )

        self._build_content(
            self.content_container
        )

        self.after_idle(
            self._update_responsive_sidebar
        )

    # =========================================================================
    # NO USER
    # =========================================================================

    def _build_no_user_ui(
        self,
    ):

        t = _get_theme()

        container = tk.Frame(
            self,
            bg=t["GRAY_BG"],
        )

        container.pack(
            fill="both",
            expand=True,
        )

        card = tk.Frame(
            container,
            bg=t["WHITE"],
            highlightbackground=(
                t["GRAY_BORDER"]
            ),
            highlightthickness=1,
        )

        card.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
            relwidth=0.70,
            relheight=0.40,
        )

        tk.Label(
            card,
            text="کاربر وارد نشده است",
            font=t["FONT_TITLE"],
            bg=t["WHITE"],
            fg=t["NAVY"],
        ).pack(
            pady=(45, 15)
        )

        tk.Label(
            card,
            text=(
                "جلسه کاربری معتبر یافت نشد.\n"
                "لطفاً دوباره وارد سیستم شوید."
            ),
            font=t["FONT_NORMAL"],
            bg=t["WHITE"],
            fg=t["TEXT_DARK"],
            justify="center",
        ).pack(
            pady=10
        )

        tk.Button(
            card,
            text="بستن",
            command=self.destroy,
            bg=t["RED"],
            fg=t["WHITE"],
            relief="flat",
            bd=0,
            padx=30,
            pady=10,
            cursor="hand2",
        ).pack(
            pady=20
        )

    # =========================================================================
    # SIDEBAR
    # =========================================================================

    # ---------------------------------------------------------------------
    # Sidebar (v2.4.7): grouped menu, one icon set, user card at the bottom
    # ---------------------------------------------------------------------

    # Section title shown above the first visible item of each group.
    _NAV_SECTIONS = {
        "equipment": "نگهداری و تعمیرات",
        "reports": "تحلیل",
        "personnel_management": "سازمان و دسترسی",
    }
    # Display order (Ctrl+1..9 follows this order).
    _NAV_ORDER = (
        "dashboard",
        "equipment", "pm_schedule", "work_orders", "repair_request",
        "inspection", "spare_parts", "machine_hours",
        "reports",
        "personnel_management", "users", "activity_log",
    )
    # Segoe MDL2 Assets / Segoe Fluent Icons code points (Windows 10/11).
    _NAV_ICONS = {
        "dashboard": "",
        "equipment": "",
        "pm_schedule": "",
        "work_orders": "",
        "repair_request": "",
        "inspection": "",
        "spare_parts": "",
        "machine_hours": "",
        "reports": "",
        "personnel_management": "",
        "users": "",
        "activity_log": "",
        None: "",          # logout
    }

    def _icon_font(self):
        """The Windows icon font if installed, else None (emoji fallback)."""
        if not hasattr(self, "_nav_icon_font"):
            self._nav_icon_font = None
            try:
                from tkinter import font as tkfont
                families = set(tkfont.families(self))
                for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
                    if name in families:
                        self._nav_icon_font = name
                        break
            except Exception:
                pass
        return self._nav_icon_font

    def _nav_icon(self, view_key, label):
        """(glyph, font) for a menu row."""
        family = self._icon_font()
        if family and view_key in self._NAV_ICONS:
            return self._NAV_ICONS[view_key], (family, 12)
        emoji = label.split("  ", 1)[0].strip() if "  " in label else ""
        return emoji, ("Segoe UI Symbol", 11)

    def _build_sidebar(
        self,
        parent,
        user,
    ):

        from auth.auth_manager import AuthManager
        t = _get_theme()
        self._sidebar_buttons = {}
        self._sidebar_button_labels = {}
        self._sidebar_rows = {}
        self._sidebar_sections = []
        self._sidebar_user_full = (
            getattr(user, "full_name", None)
            or getattr(user, "username", None)
            or "کاربر"
        )

        role = getattr(user, "role", "")
        self._sidebar_role_full = (
            role if _is_custom_role(role)
            else _get_role_fa().get(role, role)
        )

        # ---------------- brand ----------------
        header = tk.Frame(parent, bg=t["NAVY"])
        header.pack(fill="x")
        self.sidebar_header = header

        brand_row = tk.Frame(header, bg=t["NAVY"])
        brand_row.pack(fill="x", padx=10, pady=(12, 8))

        family = self._icon_font()
        self.sidebar_toggle_button = tk.Button(
            brand_row,
            text="" if family else "☰",
            command=self._toggle_sidebar,
            bg=t["NAVY"], fg="#C9D6EA",
            activebackground="#24375A", activeforeground=t["WHITE"],
            relief="flat", bd=0, cursor="hand2", highlightthickness=0,
            font=(family, 12) if family else ("Segoe UI Symbol", 14),
            width=3, padx=0, pady=4,
        )
        self.sidebar_toggle_button.pack(side="left", anchor="n")

        self.logo_container = tk.Frame(
            brand_row, bg=t["NAVY"], width=56, height=56
        )
        self.logo_container.pack(side="right")
        self.logo_container.pack_propagate(False)
        self.after(20, lambda: self._load_logo(self.logo_container))

        brand_text = tk.Frame(brand_row, bg=t["NAVY"])
        brand_text.pack(side="right", padx=(0, 10), fill="y")
        self.sidebar_brand_title = tk.Label(
            brand_text, text="PM System", font=(t["FONT_TITLE"][0], 13, "bold"),
            bg=t["NAVY"], fg=t["WHITE"], anchor="e"
        )
        self.sidebar_brand_title.pack(anchor="e", pady=(8, 0))
        self.sidebar_brand_subtitle = tk.Label(
            brand_text, text="سیستم مدیریت نگهداری و تعمیرات",
            font=t["FONT_SMALL"], bg=t["NAVY"], fg="#8EA0BC",
            wraplength=150, justify="right", anchor="e"
        )
        self.sidebar_brand_subtitle.pack(anchor="e")

        tk.Frame(header, bg="#24375A", height=1).pack(fill="x", padx=12, pady=(0, 6))

        # Kept for compatibility (not shown: the top bar has the clock).
        self.clock_en_label = tk.Label(header, text="", font=t["FONT_SMALL"],
                                       bg=t["NAVY"], fg=t["WHITE"])
        self.clock_fa_label = tk.Label(header, text="", font=t["FONT_SMALL"],
                                       bg=t["NAVY"], fg=t["WHITE"])

        # ---------------- user card + logout (bottom) ----------------
        footer = tk.Frame(parent, bg=t["NAVY"])
        footer.pack(side="bottom", fill="x")
        self.sidebar_footer = footer
        tk.Frame(footer, bg="#24375A", height=1).pack(fill="x", padx=12)

        card = tk.Frame(footer, bg=t["NAVY"])
        card.pack(fill="x", padx=12, pady=(10, 4))
        self.sidebar_user_card = card
        initial = (self._sidebar_user_full.strip() or "?")[0]
        self.sidebar_avatar = tk.Label(
            card, text=initial, font=(t["FONT_TITLE"][0], 11, "bold"),
            bg="#2F4A78", fg=t["WHITE"], width=3, pady=4
        )
        self.sidebar_avatar.pack(side="right")
        who = tk.Frame(card, bg=t["NAVY"])
        who.pack(side="right", fill="x", expand=True, padx=(0, 8))
        self.sidebar_user_label = tk.Label(
            who, text=self._sidebar_user_full, font=("Tahoma", 9, "bold"),
            bg=t["NAVY"], fg=t["WHITE"], anchor="e", justify="right", wraplength=150
        )
        self.sidebar_user_label.pack(fill="x")
        self.sidebar_role_label = tk.Label(
            who, text=self._sidebar_role_full, font=t["FONT_SMALL"],
            bg=t["NAVY"], fg="#8EA0BC", anchor="e"
        )
        self.sidebar_role_label.pack(fill="x")

        logout_holder = tk.Frame(footer, bg=t["NAVY"])
        logout_holder.pack(fill="x", pady=(2, 10))
        self._sidebar_key(
            logout_holder, "🚪  خروج از سیستم", None, t, is_logout=True
        )

        # ---------------- scrolling menu ----------------
        self.sidebar_body = tk.Frame(parent, bg=t["NAVY"])
        self.sidebar_body.pack(fill="both", expand=True)

        self.sidebar_canvas = tk.Canvas(
            self.sidebar_body, bg=t["NAVY"], highlightthickness=0, bd=0
        )
        self.sidebar_scrollbar = ttk.Scrollbar(
            self.sidebar_body, orient="vertical",
            command=self.sidebar_canvas.yview, style="PM.Sidebar.TScrollbar"
        )
        self.sidebar_canvas.pack(side="left", fill="both", expand=True)
        self.sidebar_scrollbar.pack(side="right", fill="y")
        self.sidebar_canvas.configure(yscrollcommand=self.sidebar_scrollbar.set)

        self.sidebar_inner = tk.Frame(self.sidebar_canvas, bg=t["NAVY"])
        self.sidebar_window = self.sidebar_canvas.create_window(
            (0, 0), window=self.sidebar_inner, anchor="nw"
        )
        self.sidebar_inner.bind("<Configure>", self._on_sidebar_inner_configure)
        self.sidebar_canvas.bind("<Configure>", self._on_sidebar_canvas_configure)

        allowed_for_expert = {
            "dashboard", "equipment", "work_orders", "repair_request"
        }
        custom_perms = None
        if _is_custom_role(role):
            try:
                custom_perms = AuthManager.get_role_permissions(role)
            except Exception:
                custom_perms = None

        items = {key: (label, minimum) for label, key, minimum in _get_menu_items()}
        order = [k for k in self._NAV_ORDER if k in items] + \
                [k for k in items if k not in self._NAV_ORDER]

        for view_key in order:
            label, minimum_role = items[view_key]
            try:
                allowed = False
                if not _is_custom_role(role):
                    allowed = AuthManager.has_permission(minimum_role)
                    if (role == "production_expert" and
                            view_key not in allowed_for_expert):
                        allowed = False
                else:
                    module_perm = (custom_perms or {}).get(view_key, {})
                    allowed = bool(module_perm.get("read", False))
                if allowed:
                    section = self._NAV_SECTIONS.get(view_key)
                    if section:
                        self._sidebar_section(self.sidebar_inner, section, t)
                    self._sidebar_key(self.sidebar_inner, label, view_key, t)
            except Exception as exc:
                print(f"Menu item error ({view_key}):", exc)

        tk.Frame(self.sidebar_inner, bg=t["NAVY"], height=8).pack(fill="x")
        self._bind_canvas_mousewheel(self.sidebar_canvas)

        self.after(80, lambda: self._apply_sidebar_mode(self._sidebar_collapsed))

    def _sidebar_section(self, parent, text, t):
        holder = tk.Frame(parent, bg=t["NAVY"])
        holder.pack(fill="x", padx=(8, 8), pady=(12, 2))
        lbl = tk.Label(holder, text=text, font=("Tahoma", 8, "bold"),
                       bg=t["NAVY"], fg="#7C8DA8", anchor="e")
        lbl.pack(fill="x", padx=(0, 16))
        line = tk.Frame(holder, bg="#24375A", height=1)
        self._sidebar_sections.append((holder, lbl, line))

    def _sidebar_key(
        self,
        parent,
        text,
        view_key,
        t,
        is_logout=False,
    ):
        """
        One navigation row: [indicator | icon | caption] (RTL).

        The caption is a tk.Button (so keyboard/tests can invoke it and the
        Ctrl+1..9 shortcuts keep working); the icon is a label that clicks
        through to the same button.  A 3px accent bar on the RIGHT edge marks
        the active page.
        """
        normal_bg = t["NAVY"]
        hover_bg = "#3A1C27" if is_logout else "#22365A"
        fg_normal = "#F5B4B4" if is_logout else "#C9D6EA"

        row = tk.Frame(parent, bg=normal_bg, bd=0, highlightthickness=0)
        row.pack(fill="x", padx=(8, 8), pady=1)

        indicator = tk.Frame(row, bg=normal_bg, width=3)
        indicator.pack(side="right", fill="y")

        glyph, icon_font = self._nav_icon(view_key, text)
        icon = tk.Label(row, text=glyph, font=icon_font, bg=normal_bg,
                        fg=fg_normal, width=3, cursor="hand2")
        icon.pack(side="right", padx=(6, 0))

        caption = text.split("  ", 1)[1] if "  " in text else text
        button = tk.Button(
            row, text=caption, font=t["FONT_NORMAL"],
            bg=normal_bg, fg=fg_normal,
            activebackground=hover_bg, activeforeground=t["WHITE"],
            relief="flat", bd=0, highlightthickness=0,
            anchor="e", justify="right", padx=8, pady=8, cursor="hand2", wraplength=170,
            command=self._logout if is_logout else (lambda key=view_key: self._show_view(key)),
        )
        button.pack(side="right", fill="x", expand=True)
        button._nav_row = row
        button._nav_icon = icon
        button._nav_caption = caption
        icon.bind("<Button-1>", lambda _e, b=button: b.invoke())

        if view_key:
            self._sidebar_buttons[view_key] = button
            self._sidebar_button_labels[view_key] = text
            self._sidebar_rows[view_key] = row
            if not hasattr(self, "_sidebar_indicators"):
                self._sidebar_indicators = {}
            self._sidebar_indicators[view_key] = indicator

        def paint(bg):
            for w in (row, button, icon):
                try:
                    w.configure(bg=bg)
                except Exception:
                    pass

        def on_enter(_event=None):
            if self._destroyed: return
            if is_logout or self._current_view_key != view_key:
                paint(hover_bg)
                try:
                    button.configure(fg=t["WHITE"])
                    icon.configure(fg=t["WHITE"])
                except Exception:
                    pass

        def on_leave(_event=None):
            if self._destroyed: return
            if is_logout:
                paint(normal_bg)
                try:
                    button.configure(fg=fg_normal)
                    icon.configure(fg=fg_normal)
                except Exception:
                    pass
            else:
                self._set_active_nav(self._current_view_key)

        for w in (row, button, icon):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

        if is_logout:
            self._logout_button = button
            self._logout_button_full_text = text
            self._logout_icon = icon


    def _show_top_tip(self, text):
        try:
            self.top_tip_label.configure(text=text)
        except Exception:
            pass

    def _tick_top_clock(self):
        """Live Iranian (Asia/Tehran) Jalali date and time in the top bar."""
        if self._destroyed:
            return
        try:
            from utils.date_helpers import now_tehran_jalali_text
            self.top_clock_label.configure(text=now_tehran_jalali_text())
        except Exception:
            pass
        try:
            self.after(1000, self._tick_top_clock)
        except Exception:
            pass

    def _calculate_sidebar_width(
        self,
    ):
        width = self.winfo_width()
        if width <= 0:
            width = self.winfo_screenwidth()
        if self._sidebar_collapsed:
            return 112
        if width < 1050:
            return 208
        if width < 1200:
            return 225
        if width < 1400:
            return 245
        if width < 1700:
            return 265
        return 285


    def _update_responsive_sidebar(
        self,
    ):
        if not hasattr(self, "sidebar_container"):
            return
        try:
            width = self._calculate_sidebar_width()
            self.sidebar_container.configure(width=width)
            self.sidebar_container.pack_propagate(False)

            if hasattr(self, "sidebar_canvas"):
                self.sidebar_canvas.itemconfigure(
                    self.sidebar_window, width=max(1, width - 8)
                )
            if hasattr(self, "sidebar_user_label"):
                self.sidebar_user_label.configure(wraplength=max(100, width - 110))
            if hasattr(self, "logo_container"):
                size = 52
                self.logo_container.configure(width=size, height=size)

            self._apply_sidebar_mode(self._sidebar_collapsed)
            self._set_active_nav(self._current_view_key)
        except Exception:
            pass

    def _toggle_sidebar(self):
        if self._destroyed:
            return
        self._sidebar_collapsed = not self._sidebar_collapsed
        self._apply_sidebar_mode(self._sidebar_collapsed)
        self._update_responsive_sidebar()

    def _apply_sidebar_mode(self, collapsed):
        """Collapsed: icons only.  Expanded: icon + caption + sections."""
        if not hasattr(self, "_sidebar_buttons"):
            return
        t = _get_theme()
        buttons = list(self._sidebar_buttons.values())
        if hasattr(self, "_logout_button"):
            buttons.append(self._logout_button)
        for button in buttons:
            try:
                icon = getattr(button, "_nav_icon", None)
                if collapsed:
                    button.configure(text="", padx=0, width=1)
                    if icon is not None:
                        icon.pack_configure(fill="x", expand=True, padx=0)
                    button.pack_configure(expand=False, fill="none")
                else:
                    button.configure(text=getattr(button, "_nav_caption", button.cget("text")),
                                     padx=8, width=0)
                    if icon is not None:
                        icon.pack_configure(fill="none", expand=False, padx=(6, 0))
                    button.pack_configure(expand=True, fill="x")
            except Exception:
                pass
        for holder, lbl, _line in getattr(self, "_sidebar_sections", []):
            try:
                lbl.configure(text="" if collapsed else lbl.cget("text") or "")
                if collapsed:
                    lbl.pack_forget()
                    holder.configure(height=10)
                else:
                    if not lbl.winfo_manager():
                        lbl.pack(fill="x", padx=(0, 16))
            except Exception:
                pass
        try:
            if collapsed:
                self.sidebar_brand_title.master.pack_forget()
                self.sidebar_user_label.master.pack_forget()
            else:
                if not self.sidebar_brand_title.master.winfo_manager():
                    self.sidebar_brand_title.master.pack(side="right", padx=(0, 10), fill="y")
                if not self.sidebar_user_label.master.winfo_manager():
                    self.sidebar_user_label.master.pack(side="right", fill="x", expand=True,
                                                        padx=(0, 8))
                self.sidebar_user_label.configure(text=self._sidebar_user_full)
                self.sidebar_role_label.configure(text=self._sidebar_role_full)
        except Exception:
            pass



    def _on_sidebar_inner_configure(
        self,
        _event=None,
    ):

        try:

            self.sidebar_canvas.configure(
                scrollregion=(
                    self.sidebar_canvas.bbox(
                        "all"
                    )
                )
            )

        except Exception:

            pass

    def _on_sidebar_canvas_configure(
        self,
        event=None,
    ):

        try:

            width = (
                event.width
                if event is not None
                else self.sidebar_canvas.winfo_width()
            )

            self.sidebar_canvas.itemconfigure(
                self.sidebar_window,
                width=max(
                    1,
                    width,
                ),
            )

        except Exception:

            pass

    # =========================================================================
    # CONTENT
    # =========================================================================

    def _build_content(
        self,
        parent,
    ):
        t = _get_theme()

        # Global action bar only.
        #
        # Individual views already render their own page header. Keeping a
        # second page title here caused every module (PM, repair requests,
        # work orders, equipment, ...) to show duplicate headers.
        self.topbar = tk.Frame(parent, bg=t["WHITE"], height=48, bd=0)
        self.topbar.pack(fill="x", side="top")
        self.topbar.pack_propagate(False)

        # Right side (RTL start): live Jalali date + time of Tehran.
        self.top_clock_label = tk.Label(
            self.topbar, text="", font=t["FONT_NORMAL"],
            bg=t["WHITE"], fg=t["TEXT_DARK"],
        )
        self.top_clock_label.pack(side="right", padx=18)

        # Left side: global actions, vertically centred.
        actions = tk.Frame(self.topbar, bg=t["WHITE"])
        actions.pack(side="left", padx=12)

        def _top_button(symbol, command, tip):
            btn = tk.Button(
                actions, text=symbol, command=command,
                font=("Segoe UI Symbol", 12), bg=t["WHITE"], fg=t["NAVY"],
                activebackground="#EAF1FF", activeforeground=t["NAVY"],
                relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                width=3, pady=2,
            )
            btn.pack(side="left", padx=2, pady=8)
            btn.bind("<Enter>", lambda _e: (btn.configure(bg="#EAF1FF"), self._show_top_tip(tip)))
            btn.bind("<Leave>", lambda _e: (btn.configure(bg=t["WHITE"]), self._show_top_tip("")))
            return btn

        self.top_refresh_button = _top_button("↻", self._global_f5, "بروزرسانی صفحه (F5)")
        self.top_home_button = _top_button("⌂", lambda: self._show_view("dashboard"), "داشبورد (Ctrl+1)")
        self.top_fullscreen_button = _top_button("⛶", self._toggle_fullscreen, "تمام‌صفحه (F11)")
        self.top_keys_button = _top_button("⌨", self._show_shortcuts_help, "میانبرهای صفحه‌کلید (F1)")

        self.top_tip_label = tk.Label(
            actions, text="", font=t["FONT_SMALL"], bg=t["WHITE"], fg=t["TEXT_LIGHT"],
        )
        self.top_tip_label.pack(side="left", padx=(8, 0))

        self.top_status_label = tk.Label(
            self.topbar, text="●  اتصال برقرار", font=t["FONT_SMALL"],
            bg=t["WHITE"], fg=t["SUCCESS"],
        )
        self.top_status_label.pack(side="left", padx=10)

        self._tick_top_clock()

        separator = tk.Frame(parent, bg=t["GRAY_BORDER"], height=1)
        separator.pack(fill="x", side="top")

        body = tk.Frame(parent, bg=t["GRAY_BG"])
        body.pack(fill="both", expand=True)

        self.content_canvas = tk.Canvas(
            body, bg=t["GRAY_BG"], highlightthickness=0, bd=0
        )
        self.content_canvas.pack(side="left", fill="both", expand=True)

        self.content_scrollbar = ttk.Scrollbar(
            body, orient="vertical", command=self.content_canvas.yview,
            style="PM.Content.TScrollbar"
        )
        self.content_scrollbar.pack(side="right", fill="y")
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)

        self.content_frame = tk.Frame(
            self.content_canvas, bg=t["GRAY_BG"], bd=0, highlightthickness=0
        )
        self.content_window = self.content_canvas.create_window(
            (0, 0), window=self.content_frame, anchor="nw"
        )
        self.content_frame.bind("<Configure>", self._on_content_configure)
        self.content_canvas.bind("<Configure>", self._on_content_canvas_configure)
        self.content = self.content_frame
        self._bind_canvas_mousewheel(self.content_canvas)
        self._content_height = 0
        self.after(300, self._content_height_tick)


    def _on_content_configure(
        self,
        _event=None,
    ):

        self._update_content_scrollregion()

    def _on_content_canvas_configure(
        self,
        event=None,
    ):

        try:

            width = (
                event.width
                if event is not None
                else self.content_canvas.winfo_width()
            )

            self.content_canvas.itemconfigure(
                self.content_window,
                width=max(
                    1,
                    width,
                ),
            )
            self._sync_content_height()

        except Exception:

            pass

    def _sync_content_height(self):
        """
        Let pages fill the window on large screens.

        The page area sits in a scrollable canvas.  Its height is the larger
        of the visible height and what the page needs, so tables can grow to
        the bottom of a big monitor while long pages still scroll on small
        ones.
        """
        if self._destroyed or not hasattr(self, "content_canvas"):
            return
        try:
            target = max(
                self.content_canvas.winfo_height(),
                self.content_frame.winfo_reqheight(),
                1,
            )
            if target != self._content_height:
                self._content_height = target
                self.content_canvas.itemconfigure(self.content_window, height=target)
                self.after_idle(self._update_content_scrollregion)
        except Exception:
            pass

    def _content_height_tick(self):
        if self._destroyed:
            return
        self._sync_content_height()
        try:
            self._content_height_after = self.after(300, self._content_height_tick)
        except Exception:
            pass

    def _update_content_scrollregion(
        self,
    ):

        if self._destroyed:
            return

        if not hasattr(
            self,
            "content_canvas",
        ):
            return

        try:

            self.content_canvas.configure(
                scrollregion=(
                    self.content_canvas.bbox(
                        "all"
                    )
                )
            )

        except Exception:

            pass

    # =========================================================================
    # MOUSE WHEEL
    # =========================================================================

    def _bind_canvas_mousewheel(
        self,
        canvas,
    ):

        def on_enter(
            _event=None,
        ):

            self._mousewheel_canvas = (
                canvas
            )

        def on_leave(
            _event=None,
        ):

            if (
                self._mousewheel_canvas
                is canvas
            ):

                self._mousewheel_canvas = None

        canvas.bind(
            "<Enter>",
            on_enter,
            add="+",
        )

        canvas.bind(
            "<Leave>",
            on_leave,
            add="+",
        )

        canvas.bind(
            "<MouseWheel>",
            self._on_mousewheel,
            add="+",
        )

        canvas.bind(
            "<Shift-MouseWheel>",
            self._on_shift_mousewheel,
            add="+",
        )

    def _on_mousewheel(
        self,
        event,
    ):

        if self._destroyed:
            return

        canvas = (
            self._mousewheel_canvas
        )

        if canvas is None:
            return

        try:

            delta = (
                event.delta
            )

            if delta == 0:
                return

            units = int(
                -delta / 120
            )

            if units == 0:

                units = (
                    -1
                    if delta > 0
                    else 1
                )

            canvas.yview_scroll(
                units,
                "units",
            )

        except Exception:

            pass

    def _on_shift_mousewheel(
        self,
        event,
    ):

        if self._destroyed:
            return

        canvas = (
            self._mousewheel_canvas
        )

        if canvas is None:
            return

        try:

            units = int(
                -event.delta / 120
            )

            if units == 0:

                units = (
                    -1
                    if event.delta > 0
                    else 1
                )

            canvas.xview_scroll(
                units,
                "units",
            )

        except Exception:

            pass

    # =========================================================================
    # LOGO
    # =========================================================================

    def _load_logo(
        self,
        container,
    ):

        if self._destroyed:
            return

        t = _get_theme()

        try:
            container.update_idletasks()
            side = max(40, min(container.winfo_reqwidth(), container.winfo_reqheight()) - 4)
        except Exception:
            side = 60
        target_size = (
            side,
            side,
        )

        try:

            from PIL import (
                Image,
                ImageTk,
            )

            for ext in (
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
            ):

                image_path = resource_path(
                    f"views/gela-logo{ext}"
                )

                if not os.path.exists(
                    image_path
                ):
                    continue

                image = Image.open(
                    image_path
                )

                if hasattr(
                    Image,
                    "Resampling",
                ):

                    resample = (
                        Image.Resampling.LANCZOS
                    )

                else:

                    resample = (
                        Image.LANCZOS
                    )

                image.thumbnail(
                    target_size,
                    resample,
                )

                self.logo_img = (
                    ImageTk.PhotoImage(
                        image
                    )
                )

                tk.Label(
                    container,
                    image=self.logo_img,
                    bg=t["NAVY"],
                ).pack(
                    expand=True
                )

                return

        except Exception as exc:

            print(
                "Pillow logo error:",
                exc,
            )

        try:

            gif_path = resource_path(
                "views/gela-logo.gif"
            )

            if os.path.exists(
                gif_path
            ):

                self.logo_img = (
                    tk.PhotoImage(
                        file=gif_path
                    )
                )

                width = (
                    self.logo_img.width()
                )

                height = (
                    self.logo_img.height()
                )

                if (
                    width > target_size[0]
                    or
                    height > target_size[1]
                ):

                    scale = max(
                        width / target_size[0],
                        height / target_size[1],
                    )

                    subsample = max(
                        1,
                        int(scale),
                    )

                    self.logo_img = (
                        self.logo_img.subsample(
                            subsample
                        )
                    )

                tk.Label(
                    container,
                    image=self.logo_img,
                    bg=t["NAVY"],
                ).pack(
                    expand=True
                )

                return

        except Exception as exc:

            print(
                "GIF logo error:",
                exc,
            )

        tk.Label(
            container,
            text="⚙️",
            font=(
                "Segoe UI",
                48,
            ),
            bg=t["NAVY"],
            fg=t["WHITE"],
        ).pack(
            expand=True
        )

    # =========================================================================
    # CLOCK
    # =========================================================================

    def _start_clock(
        self,
        en_label,
        fa_label,
    ):
        """Live Iranian clock in the sidebar (Jalali date + Tehran time)."""

        def tick():
            if self._destroyed:
                return
            try:
                from utils.date_helpers import (
                    tehran_now, jalali_weekday_name, MONTHS_FA,
                )
                import jdatetime
                now = tehran_now()
                j = jdatetime.date.fromgregorian(date=now.date())
                fa = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
                en_label.configure(
                    text=(f"{jalali_weekday_name(now.date())} {j.day} "
                          f"{MONTHS_FA[j.month - 1]} {j.year}").translate(fa)
                )
                fa_label.configure(text=now.strftime("%H:%M:%S").translate(fa))
            except Exception:
                pass
            try:
                self._after_id = (
                    self.after(
                        1000,
                        tick,
                    )
                )

            except Exception:

                self._after_id = None

        tick()

    # =========================================================================
    # CURRENT VIEW REFRESH
    # =========================================================================

    def _refresh_current_view(
        self,
    ):

        if self._destroyed:
            return

        try:

            self._update_content_scrollregion()

        except Exception:

            pass

        view = (
            self._current_view
        )

        if view is None:
            return

        try:

            if hasattr(
                view,
                "_on_window_resize",
            ):

                view._on_window_resize()

        except Exception:

            pass

        try:

            if hasattr(
                view,
                "_on_show",
            ):

                view._on_show()

        except Exception as exc:

            print(
                "View refresh error:",
                exc,
            )

        try:

            view_canvas = getattr(
                view,
                "canvas",
                None,
            )

            if view_canvas is not None:

                view_canvas.configure(
                    scrollregion=(
                        view_canvas.bbox(
                            "all"
                        )
                    )
                )

        except Exception:

            pass

    def _notify_current_view_resize(
        self,
    ):

        if self._destroyed:
            return

        view = (
            self._current_view
        )

        if view is None:
            return

        try:

            if hasattr(
                view,
                "_on_window_resize",
            ):

                view._on_window_resize()

        except Exception as exc:

            print(
                "View resize error:",
                exc,
            )

    # =========================================================================
    # VIEW ROUTING
    # =========================================================================

    def _show_view(
        self,
        view_key: str,
    ):

        if self._destroyed:
            return

        from auth.auth_manager import (
            AuthManager
        )

        t = _get_theme()

        # ---------------------------------------------------------------------
        # Current user
        # ---------------------------------------------------------------------

        try:

            user = (
                AuthManager
                .get_current_user()
            )

        except Exception as exc:

            print(
                "Current user error:",
                exc,
            )

            return

        if not user:

            messagebox.showerror(
                "خطا",
                "کاربر فعلی یافت نشد.",
                parent=self,
            )

            return

        # Unsaved work on the current page (e.g. machine-hours sheet)?
        current = getattr(self, "_current_view", None)
        if current is not None and hasattr(current, "confirm_leave"):
            try:
                if not current.confirm_leave():
                    return
            except Exception as exc:
                print("confirm_leave error:", exc)

        # ---------------------------------------------------------------------
        # Clear previous view
        # ---------------------------------------------------------------------

        for child in list(
            self.content_frame.winfo_children()
        ):

            try:
                child.destroy()

            except Exception:

                pass

        self._current_view = None

        self._current_view_key = (
            view_key
        )
        self._update_topbar(view_key)
        self._set_active_nav(view_key)

        current_user_dict = {
            "id":
                getattr(
                    user,
                    "id",
                    None,
                ),

            "username":
                getattr(
                    user,
                    "username",
                    "",
                ),

            "role":
                getattr(
                    user,
                    "role",
                    "",
                ),

            "full_name":
                getattr(
                    user,
                    "full_name",
                    "",
                ),
        }

        view = None

        try:

            # -----------------------------------------------------------------
            # Dashboard
            # -----------------------------------------------------------------

            if view_key == "dashboard":

                from views.dashboard_view import (
                    DashboardView
                )

                view = DashboardView(
                    self.content_frame,
                    current_user=(
                        current_user_dict
                    ),
                )

            # -----------------------------------------------------------------
            # Equipment
            # -----------------------------------------------------------------

            elif view_key == "equipment":

                from views.equipment_view import (
                    EquipmentView
                )

                view = EquipmentView(
                    self.content_frame,
                    equipment_repo=(
                        self.equipment_repo
                    ),
                    current_user=(
                        current_user_dict
                    ),
                )

            # -----------------------------------------------------------------
            # PM
            # -----------------------------------------------------------------

            elif view_key == "pm_schedule":

                from views.pm_view import (
                    PMView
                )

                view = PMView(
                    self.content_frame,
                    pm_repo=self.pm_repo,
                    equipment_repo=(
                        self.equipment_repo
                    ),
                    user_repo=self.user_repo,
                    current_user=(
                        current_user_dict
                    ),
                )

            # -----------------------------------------------------------------
            # Work Orders
            # -----------------------------------------------------------------

            elif view_key == "work_orders":

                from views.work_order_view import (
                    WorkOrderView
                )

                view = WorkOrderView(
                    self.content_frame,
                    work_order_repo=(
                        self.wo_repo
                    ),
                    current_user=(
                        current_user_dict
                    ),
                )

            # -----------------------------------------------------------------
            # Repair Requests
            # -----------------------------------------------------------------

            elif view_key == "repair_request":

                from views.repair_request_view import (
                    RepairRequestView
                )

                view = RepairRequestView(
                    self.content_frame,
                    current_user=(
                        current_user_dict
                    ),
                )

            # -----------------------------------------------------------------
            # Personnel / Department Management
            # -----------------------------------------------------------------

            elif view_key == "personnel_management":

                # same rule as the page itself (custom roles: «مدیریت نقش‌ها»)
                if not AuthManager.allows(
                    ("admin", "manager"),
                    "personnel_management",
                    "read",
                ):

                    messagebox.showerror(
                        "دسترسی غیرمجاز",
                        "شما مجاز به مشاهده پرسنل و دپارتمان‌ها نیستید.",
                        parent=self,
                    )

                    self._show_view(
                        "dashboard"
                    )

                    return

                # IMPORTANT:
                #
                # Current source archive contains:
                #
                #     views/department_personnel_view.py
                #
                # NOT:
                #
                #     views/personnel_management_view.py
                #
                from views.department_personnel_view import (
                    PersonnelManagementView
                )

                view = PersonnelManagementView(
                    self.content_frame,
                    current_user=(
                        current_user_dict
                    ),
                    personnel_repo=(
                        self.personnel_repo
                    ),
                    department_repo=(
                        self.department_repo
                    ),
                )

            # -----------------------------------------------------------------
            # Inspection
            # -----------------------------------------------------------------

            elif view_key == "inspection":

                from services.inspection_service import (
                    InspectionService
                )

                service = (
                    InspectionService(
                        SessionLocal
                    )
                )

                from views.inspection_view import (
                    InspectionView
                )

                view = InspectionView(
                    self.content_frame,
                    service=service,
                    current_user=(
                        current_user_dict
                    ),
                )

            # -----------------------------------------------------------------
            # Reports
            # -----------------------------------------------------------------

            elif view_key == "reports":

                from views.reports_view import (
                    ReportsView
                )

                view = ReportsView(
                    self.content_frame,
                    current_user=(
                        current_user_dict
                    ),
                )

            # -----------------------------------------------------------------
            # Spare Parts
            # -----------------------------------------------------------------

            elif view_key == "spare_parts":

                from views.spare_parts_view import (
                    SparePartsView
                )

                view = SparePartsView(
                    self.content_frame,
                    session_factory=(
                        SessionLocal
                    ),
                    current_user=(
                        current_user_dict
                    ),
                )

            # -----------------------------------------------------------------
            # Users
            # -----------------------------------------------------------------

            elif view_key == "users":

                from views.users_view import (
                    UsersView
                )

                view = UsersView(
                    self.content_frame,
                    user_repo=(
                        self.user_repo
                    ),
                    current_user=(
                        current_user_dict
                    ),
                )

            # -----------------------------------------------------------------
            # Activity Log
            # -----------------------------------------------------------------

            elif view_key == "activity_log":

                from views.activity_log_view import (
                    ActivityLogView
                )

                view = ActivityLogView(
                    self.content_frame,
                    current_user=(
                        current_user_dict
                    ),
                )

            # -----------------------------------------------------------------
            # Machine Hours
            # -----------------------------------------------------------------

            elif view_key == "machine_hours":

                from views.machine_hours_view import (
                    MachineHoursView
                )

                view = MachineHoursView(
                    self.content_frame,
                    current_user=(
                        current_user_dict
                    ),
                )

            # -----------------------------------------------------------------
            # Unknown
            # -----------------------------------------------------------------

            else:

                self._show_placeholder(
                    view_key
                )

                return

        except Exception as exc:

            print(
                f"Error loading view "
                f"'{view_key}':",
                exc,
            )

            self._show_view_error(
                view_key,
                exc,
            )

            return

        if view is None:
            return

        try:

            view.pack(
                fill="both",
                expand=True,
            )

            self._current_view = view

            try:
                from views import ux
                ux.polish_page(view)
            except Exception as exc:
                print("ux polish error:", exc)

            if hasattr(
                view,
                "_on_show",
            ):

                try:

                    view._on_show()

                except Exception as exc:

                    print(
                        f"_on_show error "
                        f"({view_key}):",
                        exc,
                    )

            self.after_idle(
                self._reset_content_scroll
            )

        except Exception as exc:

            print(
                f"Error displaying view "
                f"'{view_key}':",
                exc,
            )

            self._show_view_error(
                view_key,
                exc,
            )

    # =========================================================================
    # TOPBAR / NAVIGATION STATE
    # =========================================================================

    def _update_topbar(self, view_key):
        # Kept as a compatibility hook because routing still calls this method.
        # Page titles are rendered only by the active view itself.
        return None

    def _set_active_nav(self, view_key):
        if not hasattr(self, "_sidebar_buttons"):
            return
        t = _get_theme()
        indicators = getattr(self, "_sidebar_indicators", {})
        active_bg = "#26406B"
        for key, button in self._sidebar_buttons.items():
            active = key == view_key
            bg = active_bg if active else t["NAVY"]
            fg = t["WHITE"] if active else "#C9D6EA"
            try:
                for w in (getattr(button, "_nav_row", None), button,
                          getattr(button, "_nav_icon", None)):
                    if w is not None:
                        w.configure(bg=bg)
                button.configure(fg=fg, font=(("Tahoma", 9, "bold") if active
                                              else t["FONT_NORMAL"]))
                icon = getattr(button, "_nav_icon", None)
                if icon is not None:
                    icon.configure(fg="#93C5FD" if active else "#C9D6EA")
                if key in indicators:
                    indicators[key].configure(bg=("#60A5FA" if active else bg))
            except Exception:
                pass

    # =========================================================================
    # RESET CONTENT SCROLL
    # =========================================================================

    def _reset_content_scroll(
        self,
    ):

        if self._destroyed:
            return

        try:

            self.content_canvas.yview_moveto(
                0
            )

        except Exception:

            pass

        self._update_content_scrollregion()

        try:

            self.after_idle(
                self._update_content_scrollregion
            )

        except Exception:

            pass

    # =========================================================================
    # VIEW ERROR
    # =========================================================================

    def _show_view_error(
        self,
        view_key,
        error,
    ):

        if self._destroyed:
            return

        t = _get_theme()

        for child in list(
            self.content_frame.winfo_children()
        ):

            try:

                child.destroy()

            except Exception:

                pass

        self._current_view = None

        outer = tk.Frame(
            self.content_frame,
            bg=t["GRAY_BG"],
        )

        outer.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=30,
        )

        card = tk.Frame(
            outer,
            bg=t["WHITE"],
            highlightbackground=(
                t["GRAY_BORDER"]
            ),
            highlightthickness=1,
        )

        card.pack(
            fill="both",
            expand=True,
        )

        tk.Label(
            card,
            text="خطا در باز کردن بخش",
            font=t["FONT_TITLE"],
            bg=t["WHITE"],
            fg=t["RED"],
        ).pack(
            pady=(70, 15),
        )

        tk.Label(
            card,
            text=(
                f"بخش: {view_key}\n\n"
                "خطای بخش مانع کار پنجره اصلی نشده است."
            ),
            font=t["FONT_NORMAL"],
            bg=t["WHITE"],
            fg=t["TEXT_DARK"],
            justify="center",
        ).pack(
            pady=10,
        )

        tk.Label(
            card,
            text=str(
                error
            ),
            font=t["FONT_SMALL"],
            bg=t["WHITE"],
            fg=t["TEXT_LIGHT"],
            wraplength=800,
            justify="center",
        ).pack(
            padx=30,
            pady=15,
        )

        tk.Button(
            card,
            text="بازگشت به داشبورد",
            command=lambda:
            self._show_view(
                "dashboard"
            ),
            bg=t["NAVY"],
            fg=t["WHITE"],
            activebackground=t["NAVY_LIGHT"],
            activeforeground=t["WHITE"],
            relief="flat",
            bd=0,
            padx=25,
            pady=10,
            cursor="hand2",
        ).pack(
            pady=25,
        )

        self.after_idle(
            self._update_content_scrollregion
        )

    # =========================================================================
    # PLACEHOLDER
    # =========================================================================

    def _show_placeholder(
        self,
        view_key,
    ):

        t = _get_theme()

        container = tk.Frame(
            self.content_frame,
            bg=t["GRAY_BG"],
        )

        container.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=30,
        )

        card = tk.Frame(
            container,
            bg=t["WHITE"],
            highlightbackground=(
                t["GRAY_BORDER"]
            ),
            highlightthickness=1,
        )

        card.pack(
            fill="both",
            expand=True,
        )

        tk.Label(
            card,
            text="این بخش در حال توسعه است",
            font=t["FONT_TITLE"],
            bg=t["WHITE"],
            fg=t["NAVY"],
        ).pack(
            pady=(80, 10)
        )

        tk.Label(
            card,
            text=(
                f"شناسه بخش: {view_key}"
            ),
            font=t["FONT_NORMAL"],
            bg=t["WHITE"],
            fg=t["TEXT_LIGHT"],
        ).pack(
            pady=10
        )

        self.after_idle(
            self._update_content_scrollregion
        )

    # =========================================================================
    # LOGOUT
    # =========================================================================

    def _logout(
        self,
    ):

        if self._destroyed:
            return

        try:

            confirmed = (
                messagebox.askyesno(
                    "خروج از سیستم",
                    (
                        "آیا مطمئن هستید که "
                        "می‌خواهید از سیستم خارج شوید؟"
                    ),
                    parent=self,
                )
            )

            if not confirmed:
                return

            from auth.auth_manager import (
                AuthManager
            )

            AuthManager.logout()

            self.destroy()

            from views.login_view import (
                LoginView
            )

            LoginView().mainloop()

        except Exception as exc:

            print(
                "Logout error:",
                exc,
            )

            try:

                messagebox.showerror(
                    "خطا",
                    (
                        "خطایی هنگام خروج از سیستم رخ داد:\n\n"
                        f"{exc}"
                    ),
                    parent=self,
                )

            except Exception:

                pass


# ============================================================================
# STANDALONE
# ============================================================================

if __name__ == "__main__":

    try:

        app = MainView()

        app.mainloop()

    except Exception as exc:

        print(
            "MainView startup error:",
            exc,
        )

        raise
