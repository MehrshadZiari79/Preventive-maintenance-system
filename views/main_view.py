# views/main_view.py
import tkinter as tk
from tkinter import ttk, messagebox
import os
from PIL import Image, ImageTk

from auth.auth_manager import AuthManager
from database.models import UserRole
from database.user_repository import UserRepository
from database.equipment_repository import EquipmentRepository
from database.pm_repository import PMRepository
from database.work_order_repository import WorkOrderRepository
from database.inspection_repository import InspectionRepository
from services.inspection_service import InspectionService
from database.db import SessionLocal
from services.auto_pm_service import AutoPMService
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

ROLE_FA = {
    UserRole.ADMIN.value: "مدیر سیستم",
    UserRole.MANAGER.value: "مدیر",
    UserRole.TECHNICIAN.value: "تکنسین",
}

MENU_ITEMS = [
    ("📊  داشبورد", "dashboard", UserRole.TECHNICIAN.value),
    ("⚙️  تجهیزات", "equipment", UserRole.TECHNICIAN.value),
    ("📅  برنامه نگهداری", "pm_schedule", UserRole.MANAGER.value),
    ("📝  دستور کارها", "work_orders", UserRole.TECHNICIAN.value),
    ("🔧  قطعات یدکی", "spare_parts", UserRole.TECHNICIAN.value),
    ("🔍  بازرسی‌ها", "inspections", UserRole.TECHNICIAN.value),
    ("📈  گزارشات", "reports", UserRole.MANAGER.value),
    ("👥  مدیریت کاربران", "users", UserRole.ADMIN.value),
    ("📋  لاگ فعالیت", "activity_log", UserRole.ADMIN.value),
    ("💾  پشتیبان دیتابیس", "backup", UserRole.ADMIN.value),
]


class MainView(tk.Tk):
    def __init__(self):
        super().__init__()

        # --- Apply global navy scrollbar style to all ttk scrollbars ---
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Vertical.TScrollbar",
                        background=NAVY,
                        troughcolor=GRAY_BG,
                        arrowcolor=WHITE,
                        bordercolor=NAVY,
                        lightcolor=NAVY,
                        darkcolor=NAVY,
                        width=14)
        style.map("Vertical.TScrollbar",
                  background=[('active', NAVY_LIGHT), ('pressed', NAVY_LIGHT)])
        style.configure("Horizontal.TScrollbar",
                        background=NAVY,
                        troughcolor=GRAY_BG,
                        arrowcolor=WHITE,
                        bordercolor=NAVY,
                        lightcolor=NAVY,
                        darkcolor=NAVY,
                        height=14)
        style.map("Horizontal.TScrollbar",
                  background=[('active', NAVY_LIGHT), ('pressed', NAVY_LIGHT)])

        self.title("سیستم نگهداری پیشگیرانه")
        self.configure(bg=WHITE)
        self._set_fullscreen()
        self._setup_bindings()

        self.user_repo = UserRepository()
        self.equipment_repo = EquipmentRepository()
        self.pm_repo = PMRepository()
        self.wo_repo = WorkOrderRepository()
        self.inspection_repo = InspectionRepository()

        self._build_ui()
        self._show_view("dashboard")
        self.auto_pm_service = AutoPMService(check_interval_seconds=3600)
        self.auto_pm_service.start()

    def destroy(self):
        if hasattr(self, 'auto_pm_service'):
            self.auto_pm_service.stop()
        super().destroy()

    def _set_fullscreen(self):
        self.attributes('-fullscreen', True)
        self.minsize(1024, 600)

    def _setup_bindings(self):
        self.bind('<Escape>', self._toggle_fullscreen)
        self.bind('<F11>', self._toggle_fullscreen)

    def _toggle_fullscreen(self, event=None):
        is_full = self.attributes('-fullscreen')
        self.attributes('-fullscreen', not is_full)
        if not is_full:
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        # Force update of scrollable regions in child views
        self.update_idletasks()
        self._refresh_current_view()

    def _refresh_current_view(self):
        """Notify current view to refresh its canvas scrolling if needed."""
        for child in self.content.winfo_children():
            if hasattr(child, '_on_window_resize'):
                child._on_window_resize()
            if hasattr(child, '_on_show'):
                child._on_show()
            if hasattr(child, 'canvas') and hasattr(child.canvas, 'configure'):
                child.canvas.configure(scrollregion=child.canvas.bbox("all"))

    def _build_ui(self):
        user = AuthManager.get_current_user()

        # Sidebar (navy)
        sidebar = tk.Frame(self, bg=NAVY, width=260)
        sidebar.pack(side="right", fill="y")
        sidebar.pack_propagate(False)
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_path = os.path.join(project_root, "gela-logo.jpg")
            if os.path.exists(logo_path):
                img = Image.open(logo_path)
                img = img.resize((80, 80), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
                tk.Label(sidebar, image=self.logo_img, bg=NAVY).pack(pady=(25, 5))
            else:
                print(f"Logo not found at {logo_path}")
        except Exception as e:
            print(f"Logo error: {e}")

        tk.Label(sidebar, text="🏭 PM System", font=FONT_TITLE, bg=NAVY, fg=WHITE).pack(pady=(5, 15))
        tk.Label(sidebar, text=user.full_name, font=FONT_NORMAL, bg=NAVY, fg=WHITE).pack()
        tk.Label(sidebar, text=ROLE_FA.get(user.role, user.role), font=FONT_SMALL, bg=NAVY, fg=TEXT_LIGHT).pack(
            pady=(2, 20))
        tk.Frame(sidebar, bg=NAVY_LIGHT, height=2).pack(fill="x", padx=16, pady=(0, 10))

        for label, view_key, min_role in MENU_ITEMS:
            if not AuthManager.has_permission(min_role):
                continue
            btn = tk.Button(sidebar, text=label, font=FONT_NORMAL, bg=NAVY, fg=WHITE,
                            activebackground=NAVY_LIGHT, relief="flat", anchor="e",
                            padx=20, pady=12, cursor="hand2",
                            command=lambda v=view_key: self._show_view(v))
            btn.pack(fill="x")

        tk.Button(sidebar, text="🚪  خروج", font=FONT_NORMAL, bg=NAVY, fg=RED,
                  activebackground=NAVY_LIGHT, relief="flat", anchor="e",
                  padx=20, pady=12, cursor="hand2",
                  command=self._logout).pack(side="bottom", fill="x", pady=(0, 10))

        self.content = tk.Frame(self, bg=WHITE)
        self.content.pack(side="right", fill="both", expand=True)

    def _show_view(self, view_key: str):
        for w in self.content.winfo_children():
            w.destroy()
        user = AuthManager.get_current_user()
        current_user_dict = {
            "id": user.id, "username": user.username,
            "role": user.role, "full_name": user.full_name
        }

        if view_key == "backup":
            self._show_backup_dialog()
            return

        if view_key == "users":
            from views.users_view import UsersView
            view = UsersView(self.content, user_repo=self.user_repo, current_user=current_user_dict)
        elif view_key == "equipment":
            from views.equipment_view import EquipmentView
            view = EquipmentView(self.content, equipment_repo=self.equipment_repo, current_user=current_user_dict)
        elif view_key == "pm_schedule":
            from views.pm_view import PMView
            view = PMView(self.content, pm_repo=self.pm_repo, equipment_repo=self.equipment_repo,
                          user_repo=self.user_repo, current_user=current_user_dict)
        elif view_key == "work_orders":
            from views.work_order_view import WorkOrderView
            view = WorkOrderView(self.content, work_order_repo=self.wo_repo, current_user=current_user_dict)
        elif view_key == "inspections":
            from views.inspection_view import InspectionView
            view = InspectionView(self.content, service=InspectionService(SessionLocal()),
                                  current_user=current_user_dict)
        elif view_key == "reports":
            from views.reports_view import ReportsView
            view = ReportsView(self.content, current_user=current_user_dict)
        elif view_key == "spare_parts":
            from views.spare_parts_view import SparePartsView
            view = SparePartsView(self.content, session=SessionLocal(), current_user=current_user_dict)
        elif view_key == "dashboard":
            from views.dashboard_view import DashboardView
            view = DashboardView(self.content, current_user=current_user_dict)
        elif view_key == "activity_log":
            from views.activity_log_view import ActivityLogView
            view = ActivityLogView(self.content, current_user=current_user_dict)
        else:
            container = tk.Frame(self.content, bg=WHITE)
            container.pack(fill="both", expand=True, padx=30, pady=30)
            card = tk.Frame(container, bg=WHITE, highlightbackground=GRAY_BORDER, highlightthickness=1)
            card.pack(fill="both", expand=True)
            tk.Label(card, text="در حال توسعه...", font=FONT_TITLE, bg=WHITE, fg=NAVY).pack(pady=50)
            return

        view.pack(fill="both", expand=True)
        if hasattr(view, '_on_show'):
            view._on_show()
        return

    def _show_backup_dialog(self):
        from utils.backup import backup_database, restore_database
        from utils.theme import WHITE, NAVY, SUCCESS, WARNING, GRAY_BORDER, TEXT_DARK, TEXT_LIGHT, FONT_TITLE, \
            FONT_NORMAL, FONT_SMALL

        dialog = tk.Toplevel(self.content)
        dialog.title("ابزار مدیریت دیتابیس")
        dialog.geometry("450x300")
        dialog.configure(bg=WHITE)
        dialog.transient(self)
        dialog.grab_set()

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 225
        y = (dialog.winfo_screenheight() // 2) - 150
        dialog.geometry(f"+{x}+{y}")

        tk.Label(dialog, text="💾  پشتیبان دیتابیس", font=FONT_TITLE, bg=WHITE, fg=NAVY).pack(pady=20)
        tk.Label(dialog, text="از دیتابیس فعلی نسخه پشتیبان بگیرید یا یک فایل پشتیبان را بازگردانی کنید.",
                 font=FONT_SMALL, bg=WHITE, fg=TEXT_LIGHT, wraplength=380, justify="center").pack(pady=5)

        btn_frame = tk.Frame(dialog, bg=WHITE)
        btn_frame.pack(pady=30)

        tk.Button(btn_frame, text="📤  گرفتن پشتیبان", font=FONT_NORMAL, bg=SUCCESS, fg=WHITE,
                  padx=20, pady=8, cursor="hand2",
                  command=lambda: backup_database(dialog)).pack(side="left", padx=10)
        tk.Button(btn_frame, text="📥  بازگردانی از پشتیبان", font=FONT_NORMAL, bg=WARNING, fg=WHITE,
                  padx=20, pady=8, cursor="hand2",
                  command=lambda: restore_database(dialog)).pack(side="left", padx=10)
        tk.Button(btn_frame, text="بستن", font=FONT_NORMAL, bg=GRAY_BORDER, fg=TEXT_DARK,
                  padx=20, pady=8, cursor="hand2",
                  command=dialog.destroy).pack(side="left", padx=10)

    def _logout(self):
        # Use parent=self to ensure dialog appears on top
        if messagebox.askyesno("خروج", "آیا می‌خواهید خارج شوید؟", parent=self):
            AuthManager.logout()
            self.destroy()
            from views.login_view import LoginView
            LoginView().mainloop()