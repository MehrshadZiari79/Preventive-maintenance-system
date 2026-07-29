# views/main_view.py
import tkinter as tk
from tkinter import ttk, messagebox
import os, sys, datetime, winsound
from database.db import SessionLocal

os.environ["MPLBACKEND"] = "TkAgg"

ROLE_FA = None
MENU_ITEMS = None
_theme = None

def _get_theme():
    global _theme
    if _theme is None:
        from utils.theme import (
            NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
            TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
            FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL,
        )
        _theme = dict(
            NAVY=NAVY, NAVY_LIGHT=NAVY_LIGHT, WHITE=WHITE, RED=RED,
            GRAY_BG=GRAY_BG, GRAY_BORDER=GRAY_BORDER,
            TEXT_DARK=TEXT_DARK, TEXT_LIGHT=TEXT_LIGHT,
            SUCCESS=SUCCESS, WARNING=WARNING,
            FONT_TITLE=FONT_TITLE, FONT_HEADING=FONT_HEADING,
            FONT_NORMAL=FONT_NORMAL, FONT_SMALL=FONT_SMALL,
        )
    return _theme

def _get_menu_items():
    global MENU_ITEMS
    if MENU_ITEMS is None:
        from database.models import UserRole
        MENU_ITEMS = [
            ("📊  داشبورد",          "dashboard",    UserRole.TECHNICIAN.value),
            ("⚙️  تجهیزات",          "equipment",    UserRole.TECHNICIAN.value),
            ("📅  برنامه نگهداری",   "pm_schedule",  UserRole.MANAGER.value),
            ("📝  دستور کارها",      "work_orders",  UserRole.TECHNICIAN.value),
            ("🔍  بازرسی‌ها",        "inspection",   UserRole.TECHNICIAN.value),
            ("🔧  قطعات یدکی",       "spare_parts",  UserRole.TECHNICIAN.value),
            ("📈  گزارشات",          "reports",      UserRole.TECHNICIAN.value),
            ("👥  مدیریت کاربران",   "users",        UserRole.ADMIN.value),
            ("📋  لاگ فعالیت",       "activity_log", UserRole.ADMIN.value),
            ("⏱️  ساعات کار دستگاه", "machine_hours", UserRole.TECHNICIAN.value),
        ]
    return MENU_ITEMS

def _get_role_fa():
    global ROLE_FA
    if ROLE_FA is None:
        from database.models import UserRole
        ROLE_FA = {
            UserRole.ADMIN.value:             "مدیر سیستم",
            UserRole.MANAGER.value:           "مدیر",
            UserRole.TECHNICIAN.value:        "تکنسین",
            UserRole.PRODUCTION_EXPERT.value: "کارشناس تولید",
        }
    return ROLE_FA

def _is_custom_role(role: str) -> bool:
    """Return True if the role is not one of the built‑in UserRole values."""
    from database.models import UserRole
    return role not in {r.value for r in UserRole}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class MainView(tk.Tk):
    def __init__(self):
        super().__init__()
        self._after_id = None
        self._auto_pm_service = None
        self._user_repo = None
        self._equipment_repo = None
        self._pm_repo = None
        self._wo_repo = None

        t = _get_theme()

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Vertical.TScrollbar",
                        background=t['NAVY'], troughcolor=t['NAVY'],
                        arrowcolor=t['WHITE'], bordercolor=t['NAVY'],
                        lightcolor=t['NAVY'], darkcolor=t['NAVY'], width=14)
        style.map("Vertical.TScrollbar",
                  background=[('active', t['NAVY_LIGHT']), ('pressed', t['NAVY_LIGHT'])])
        style.configure("Horizontal.TScrollbar",
                        background=t['NAVY'], troughcolor=t['NAVY'],
                        arrowcolor=t['WHITE'], bordercolor=t['NAVY'],
                        lightcolor=t['NAVY'], darkcolor=t['NAVY'], height=14)
        style.map("Horizontal.TScrollbar",
                  background=[('active', t['NAVY_LIGHT']), ('pressed', t['NAVY_LIGHT'])])

        self.title("سیستم نگهداری پیشگیرانه")
        self.configure(bg=t['GRAY_BG'])
        self._set_fullscreen()
        self._setup_bindings()
        icon_path = resource_path("gela-logo.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        self._build_ui()
        self.after_idle(self._deferred_startup)

        # Start notification checker
        self._notify_after_id = None
        self._start_notifications()

    # ------------------------------------------------------------------
    # Lazy repos (unchanged)
    # ------------------------------------------------------------------
    @property
    def user_repo(self):
        if self._user_repo is None:
            from database.db import SessionLocal
            from database.user_repository import UserRepository
            self._user_repo = UserRepository(SessionLocal)
        return self._user_repo

    @property
    def equipment_repo(self):
        if self._equipment_repo is None:
            from database.db import SessionLocal
            from database.equipment_repository import EquipmentRepository
            self._equipment_repo = EquipmentRepository(SessionLocal)
        return self._equipment_repo

    @property
    def pm_repo(self):
        if self._pm_repo is None:
            from database.db import SessionLocal
            from database.pm_repository import PMRepository
            self._pm_repo = PMRepository(SessionLocal)
        return self._pm_repo

    @property
    def wo_repo(self):
        if self._wo_repo is None:
            from database.db import SessionLocal
            from database.work_order_repository import WorkOrderRepository
            self._wo_repo = WorkOrderRepository(SessionLocal)
        return self._wo_repo

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _deferred_startup(self):
        self._show_view("dashboard")
        from services.auto_pm_service import AutoPMService
        self._auto_pm_service = AutoPMService(check_interval_seconds=10)
        self._auto_pm_service.start()

    def destroy(self):
        if self._after_id:
            self.after_cancel(self._after_id)
        if self._notify_after_id:
            self.after_cancel(self._notify_after_id)
        if self._auto_pm_service:
            self._auto_pm_service.stop()
        super().destroy()

    def _set_fullscreen(self):
        self.attributes('-fullscreen', True)
        self.minsize(1024, 600)

    def _setup_bindings(self):
        self.bind('<Escape>', self._toggle_fullscreen)
        self.bind('<F11>',   self._toggle_fullscreen)
        self.bind('<Return>', self._global_enter)
        self.bind('<F5>',     self._global_f5)
        self.bind('<Delete>', self._global_delete)

    def _toggle_fullscreen(self, event=None):
        is_full = self.attributes('-fullscreen')
        self.attributes('-fullscreen', not is_full)
        if not is_full:
            self.geometry("1280x720")
        self.update_idletasks()
        self._refresh_current_view()

    def _global_enter(self, event=None):
        if self._is_editing():
            return
        for child in self.content_frame.winfo_children():
            if hasattr(child, 'handle_enter'):
                child.handle_enter()
                return

    def _global_f5(self, event=None):
        self._refresh_current_view()

    def _global_delete(self, event=None):
        if self._is_editing():
            return
        for child in self.content_frame.winfo_children():
            if hasattr(child, 'handle_delete'):
                child.handle_delete()
                return

    def _is_editing(self):
        try:
            focused = self.focus_get()
            return isinstance(focused, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox))
        except:
            return False

    def _refresh_current_view(self):
        # Update the scroll region of the outer canvas
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        # Notify the current view (if it has refresh methods)
        for child in self.content_frame.winfo_children():
            if hasattr(child, '_on_window_resize'):
                child._on_window_resize()
            if hasattr(child, '_on_show'):
                child._on_show()
            # If the view has its own inner canvas, update its scrollregion
            if hasattr(child, 'canvas') and hasattr(child.canvas, 'configure'):
                child.canvas.configure(scrollregion=child.canvas.bbox("all"))

    # ---------- Notification system ----------
    def _start_notifications(self):
        """Check every 5 minutes for unfinished work orders assigned to the current user (skips managers)."""
        self._check_notifications()
        self._notify_after_id = self.after(900000, self._start_notifications)

    def _check_notifications(self):
        from auth.auth_manager import AuthManager
        user = AuthManager.get_current_user()
        if not user:
            return
        # Skip notifications for managers and admins
        if user.role in ("admin", "manager"):
            return
        try:
            from database.work_order_repository import WorkOrderRepository
            repo = WorkOrderRepository(SessionLocal)
            all_wos = repo.get_all(status_filter=None, technician_id=user.id)
            unfinished = [wo for wo in all_wos if wo.status.name in ('PENDING', 'IN_PROGRESS')]
            if unfinished:
                titles = "\n".join(f"- {wo.title} (تجهیز: {wo.equipment.name if wo.equipment else '?'})" for wo in unfinished)
                try:
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                except:
                    pass
                messagebox.showwarning("یادآوری", f"شما {len(unfinished)} دستور کار ناتمام دارید:\n{titles}")
        except Exception as e:
            print(f"Notification error: {e}")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        from auth.auth_manager import AuthManager
        t = _get_theme()
        user = AuthManager.get_current_user()

        sidebar_bg = tk.Frame(self, bg=t['NAVY'], width=290, bd=0, highlightthickness=0)
        sidebar_bg.pack(side="right", fill="y")
        sidebar_bg.pack_propagate(False)

        sidebar_canvas = tk.Canvas(sidebar_bg, bg=t['NAVY'], highlightthickness=0, bd=0, width=280)
        sidebar_scrollbar = ttk.Scrollbar(sidebar_bg, orient="vertical", command=sidebar_canvas.yview)

        self.sidebar_inner = tk.Frame(sidebar_canvas, bg=t['NAVY'], bd=0, highlightthickness=0)

        sidebar_canvas.create_window((0, 0), window=self.sidebar_inner, anchor="nw", tags="inner")
        self.sidebar_inner.bind("<Configure>", lambda e: sidebar_canvas.configure(
            scrollregion=sidebar_canvas.bbox("all")))

        sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)
        sidebar_canvas.pack(side="left", fill="both", expand=True)
        sidebar_scrollbar.pack(side="right", fill="y")

        def _on_sidebar_mousewheel(event):
            sidebar_canvas.yview_scroll(-1 * (event.delta // 120), "units")
        sidebar_canvas.bind("<Enter>", lambda e: sidebar_canvas.bind_all("<MouseWheel>", _on_sidebar_mousewheel))
        sidebar_canvas.bind("<Leave>", lambda e: sidebar_canvas.unbind_all("<MouseWheel>"))

        shadow = tk.Frame(self.sidebar_inner, bg=t['GRAY_BORDER'], bd=0, highlightthickness=0)
        shadow.pack(fill="both", expand=True, padx=8, pady=8)

        sidebar = tk.Frame(shadow, bg=t['NAVY'], bd=0, highlightthickness=0)
        sidebar.pack(fill="both", expand=True, padx=1, pady=1)

        logo_container = tk.Frame(sidebar, bg=t['NAVY'], width=80, height=80, bd=0, highlightthickness=0)
        logo_container.pack(pady=(28, 5))
        logo_container.pack_propagate(False)
        self.after(10, lambda: self._load_logo(logo_container))

        tk.Label(sidebar, text="PM System", font=t['FONT_TITLE'], bg=t['NAVY'], fg=t['WHITE']).pack(pady=(5, 16))

        tk.Label(sidebar, text=user.full_name, font=t['FONT_NORMAL'], bg=t['NAVY'], fg=t['WHITE']).pack()
        tk.Label(sidebar, text=_get_role_fa().get(user.role, user.role) if not _is_custom_role(user.role) else user.role,
                 font=t['FONT_SMALL'], bg=t['NAVY'], fg=t['TEXT_LIGHT']).pack(pady=(2, 20))

        tk.Frame(sidebar, bg=t['NAVY_LIGHT'], height=2).pack(fill="x", padx=20, pady=(0, 12))

        en_label = tk.Label(sidebar, text="", font=t['FONT_SMALL'], bg=t['NAVY'], fg=t['WHITE'])
        en_label.pack(pady=(5, 0))
        fa_label = tk.Label(sidebar, text="", font=t['FONT_SMALL'], bg=t['NAVY'], fg=t['WHITE'])
        fa_label.pack(pady=(0, 12))
        self.after(50, lambda: self._start_clock(en_label, fa_label))

        # ---------- Menu items with custom role support ----------
        allowed_for_expert = {"dashboard", "equipment", "work_orders"}
        custom_perms = None
        if _is_custom_role(user.role):
            custom_perms = AuthManager.get_role_permissions(user.role)

        for label, view_key, min_role in _get_menu_items():
            if not _is_custom_role(user.role):
                # Built‑in role – original logic
                if not AuthManager.has_permission(min_role):
                    continue
                if user.role == "production_expert" and view_key not in allowed_for_expert:
                    continue
                self._sidebar_key(sidebar, label, view_key, t)
            else:
                # Custom role – check granular permissions
                if custom_perms is None:
                    continue
                module_perm = custom_perms.get(view_key, {})
                if module_perm.get("read", False):
                    self._sidebar_key(sidebar, label, view_key, t)

        self._sidebar_key(sidebar, "🚪  خروج", None, t, is_logout=True)

        # ---------- SCROLLABLE CONTENT AREA (NEW) ----------
        content_container = tk.Frame(self, bg=t['GRAY_BG'])
        content_container.pack(side="right", fill="both", expand=True)

        self.content_canvas = tk.Canvas(
            content_container,
            bg=t['GRAY_BG'],
            highlightthickness=0,
            bd=0
        )
        self.content_canvas.pack(side="left", fill="both", expand=True)

        content_scrollbar = ttk.Scrollbar(
            content_container,
            orient="vertical",
            command=self.content_canvas.yview
        )
        content_scrollbar.pack(side="right", fill="y")
        self.content_canvas.configure(yscrollcommand=content_scrollbar.set)

        self.content_frame = tk.Frame(
            self.content_canvas,
            bg=t['GRAY_BG'],
            bd=0,
            highlightthickness=0
        )
        self.content_canvas.create_window(
            (0, 0),
            window=self.content_frame,
            anchor="nw",
            tags="content_frame"
        )

        def _on_content_configure(event):
            self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        self.content_frame.bind("<Configure>", _on_content_configure)

        def _on_canvas_configure(event):
            canvas_width = event.width
            self.content_canvas.itemconfig("content_frame", width=canvas_width)
        self.content_canvas.bind("<Configure>", _on_canvas_configure)

        def _on_content_mousewheel(event):
            self.content_canvas.yview_scroll(-1 * (event.delta // 120), "units")
        self.content_canvas.bind("<Enter>", lambda e: self.content_canvas.bind_all("<MouseWheel>", _on_content_mousewheel))
        self.content_canvas.bind("<Leave>", lambda e: self.content_canvas.unbind_all("<MouseWheel>"))

        # Keep a reference for compatibility (optional)
        self.content = self.content_frame

    # ------------------------------------------------------------------
    # 3D sidebar key
    # ------------------------------------------------------------------
    def _sidebar_key(self, parent, text, view_key, t, is_logout=False):
        shadow = tk.Frame(parent, bg=t['GRAY_BORDER'], bd=0, highlightthickness=0)
        shadow.pack(fill="x", padx=16, pady=3)

        key_body = tk.Frame(shadow, bg=t['NAVY_LIGHT'], bd=0, highlightthickness=0)
        key_body.pack(fill="x", padx=1, pady=1)

        btn = tk.Button(
            key_body, text=text, font=t['FONT_NORMAL'],
            bg=t['RED'] if is_logout else t['NAVY'],
            fg=t['WHITE'],
            activebackground=t['NAVY_LIGHT'] if not is_logout else t['RED'],
            activeforeground=t['WHITE'],
            relief="flat",
            anchor="e", padx=18, pady=10, cursor="hand2",
            command=lambda: self._logout() if is_logout else self._show_view(view_key),
        )
        btn.pack(fill="x")

        if not is_logout:
            btn.bind("<Enter>", lambda e, b=btn, kb=key_body, s=shadow:
                     (b.config(bg=t['NAVY_LIGHT']),
                      kb.config(bg=t['NAVY_LIGHT']),
                      s.config(bg=t['TEXT_LIGHT'])))
            btn.bind("<Leave>", lambda e, b=btn, kb=key_body, s=shadow:
                     (b.config(bg=t['NAVY']),
                      kb.config(bg=t['NAVY_LIGHT']),
                      s.config(bg=t['GRAY_BORDER'])))
        else:
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#B91C1C"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=t['RED']))

    # ------------------------------------------------------------------
    # Logo loader
    # ------------------------------------------------------------------
    def _load_logo(self, container):
        t = _get_theme()
        target_size = (80, 80)
        try:
            from PIL import Image, ImageTk
            for ext in ['.png', '.jpg', '.jpeg', '.gif']:
                img_path = resource_path(f"views/gela-logo{ext}")
                if os.path.exists(img_path):
                    pil_img = Image.open(img_path)
                    if hasattr(Image, 'Resampling'):
                        pil_img.thumbnail(target_size, Image.Resampling.LANCZOS)
                    else:
                        pil_img.thumbnail(target_size, Image.ANTIALIAS)
                    self.logo_img = ImageTk.PhotoImage(pil_img)
                    tk.Label(container, image=self.logo_img, bg=t['NAVY']).pack(expand=True)
                    return
        except Exception as e:
            print(f"Pillow not usable: {e}")
        try:
            gif_path = resource_path("views/gela-logo.gif")
            if os.path.exists(gif_path):
                self.logo_img = tk.PhotoImage(file=gif_path)
                w, h = self.logo_img.width(), self.logo_img.height()
                if w > target_size[0] or h > target_size[1]:
                    scale = max(w / target_size[0], h / target_size[1])
                    subsample = max(1, int(scale))
                    self.logo_img = self.logo_img.subsample(subsample)
                tk.Label(container, image=self.logo_img, bg=t['NAVY']).pack(expand=True)
                return
        except Exception as e:
            print(f"GIF logo error: {e}")
        tk.Label(container, text="⚙️", font=("Segoe UI", 48), bg=t['NAVY'], fg=t['WHITE']).pack(expand=True)

    # ------------------------------------------------------------------
    # Dual clock
    # ------------------------------------------------------------------
    def _start_clock(self, en_label, fa_label):
        import jdatetime
        def tick():
            if not self.winfo_exists():
                return
            now = datetime.datetime.now()
            persian_now = jdatetime.datetime.now()
            en_label.config(text=f"EN: {now.strftime('%Y-%m-%d')}")
            fa_label.config(text=f"FA: {persian_now.strftime('%Y/%m/%d %H:%M:%S')}")
            self._after_id = self.after(1000, tick)
        tick()

    # ------------------------------------------------------------------
    # View routing
    # ------------------------------------------------------------------
    def _show_view(self, view_key: str):
        from auth.auth_manager import AuthManager
        t = _get_theme()

        for w in self.content_frame.winfo_children():
            w.destroy()

        user = AuthManager.get_current_user()
        current_user_dict = {
            "id": user.id, "username": user.username,
            "role": user.role, "full_name": user.full_name,
        }

        view = None

        if view_key == "dashboard":
            from views.dashboard_view import DashboardView
            view = DashboardView(self.content_frame, current_user=current_user_dict)
        elif view_key == "equipment":
            from views.equipment_view import EquipmentView
            view = EquipmentView(self.content_frame, equipment_repo=self.equipment_repo, current_user=current_user_dict)
        elif view_key == "pm_schedule":
            from views.pm_view import PMView
            view = PMView(self.content_frame, pm_repo=self.pm_repo, equipment_repo=self.equipment_repo, user_repo=self.user_repo, current_user=current_user_dict)
        elif view_key == "work_orders":
            from views.work_order_view import WorkOrderView
            view = WorkOrderView(self.content_frame, work_order_repo=self.wo_repo, current_user=current_user_dict)
        elif view_key == "inspection":
            from services.inspection_service import InspectionService
            service = InspectionService(SessionLocal)
            from views.inspection_view import InspectionView
            view = InspectionView(self.content_frame, service=service, current_user=current_user_dict)
        elif view_key == "reports":
            from views.reports_view import ReportsView
            view = ReportsView(self.content_frame, current_user=current_user_dict)
        elif view_key == "spare_parts":
            from views.spare_parts_view import SparePartsView
            view = SparePartsView(self.content_frame, session_factory=SessionLocal, current_user=current_user_dict)
        elif view_key == "users":
            from views.users_view import UsersView
            view = UsersView(self.content_frame, user_repo=self.user_repo, current_user=current_user_dict)
        elif view_key == "activity_log":
            from views.activity_log_view import ActivityLogView
            view = ActivityLogView(self.content_frame, current_user=current_user_dict)
        elif view_key == "machine_hours":
            from views.machine_hours_view import MachineHoursView
            view = MachineHoursView(self.content_frame, current_user=current_user_dict)
        else:
            container = tk.Frame(self.content_frame, bg=t['GRAY_BG'])
            container.pack(fill="both", expand=True, padx=30, pady=30)
            card = tk.Frame(container, bg=t['WHITE'],
                            highlightbackground=t['GRAY_BORDER'],
                            highlightthickness=1)
            card.pack(fill="both", expand=True)
            tk.Label(card, text="در حال توسعه...",
                     font=t['FONT_TITLE'], bg=t['WHITE'], fg=t['NAVY']).pack(pady=50)
            # Still need to update scroll region
            self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
            return

        if view is not None:
            view.pack(fill="both", expand=True)
            if hasattr(view, '_on_show'):
                view._on_show()
            # Reset scroll to top
            self.content_canvas.yview_moveto(0)
            # Update scroll region after layout
            self.after_idle(lambda: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all")))

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------
    def _logout(self):
        from auth.auth_manager import AuthManager
        if messagebox.askyesno("خروج", "آیا می‌خواهید خارج شوید؟", parent=self):
            AuthManager.logout()
            self.destroy()
            from views.login_view import LoginView
            LoginView().mainloop()