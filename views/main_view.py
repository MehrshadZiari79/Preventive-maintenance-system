# views/main_view.py
"""
Main Application Window - Persistent Sidebar and Content Area
Professional UI with company logo, full‑screen support, RTL layout, and session management.
"""
import tkinter as tk
from tkinter import messagebox
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
# ==================== Theme Constants ====================
BG = "#F0F4F8"
WHITE = "#FFFFFF"
SIDEBAR = "#1A1A2E"
SIDEBAR_HOVER = "#16213E"
ACTIVE = "#1A73E8"
TEXT = "#202124"
TEXT_SIDE = "#E8EAED"
SUBTLE = "#5F6368"
BORDER = "#DADCE0"

FONT_TITLE = ("Tahoma", 13, "bold")
FONT_MENU = ("Tahoma", 11)
FONT_CONTENT = ("Tahoma", 11)
FONT_SMALL = ("Tahoma", 9)

MENU_ITEMS = [
    ("📊  داشبورد", "dashboard", UserRole.TECHNICIAN.value),
    ("⚙️  تجهیزات", "equipment", UserRole.TECHNICIAN.value),
    ("📅  برنامه نگهداری", "pm_schedule", UserRole.MANAGER.value),
    ("📝  دستور کارها", "work_orders", UserRole.TECHNICIAN.value),
    ("🔧  قطعات یدکی", "spare_parts", UserRole.TECHNICIAN.value),
    ("🔍  بازرسی‌ها", "inspections", UserRole.TECHNICIAN.value),
    ("📈  گزارشات", "reports", UserRole.MANAGER.value),
    ("👥  مدیریت کاربران", "users", UserRole.ADMIN.value),
]

ROLE_FA = {
    UserRole.ADMIN.value: "مدیر سیستم",
    UserRole.MANAGER.value: "مدیر",
    UserRole.TECHNICIAN.value: "تکنسین",
}


class MainView(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("سیستم نگهداری پیشگیرانه")
        self.configure(bg=BG)
        self._set_fullscreen()
        self._setup_bindings()

        self.user_repo = UserRepository()
        self.equipment_repo = EquipmentRepository()
        self.pm_repo = PMRepository()
        self.wo_repo = WorkOrderRepository()
        self.inspection_repo = InspectionRepository()

        self._build_ui()
        self._show_view("dashboard")
        # Start automatic PM work order generation service
        self.auto_pm_service = AutoPMService(check_interval_seconds=3600)  # every hour
        self.auto_pm_service.start()
    def destroy(self):
        if hasattr(self, 'auto_pm_service'):
            self.auto_pm_service.stop()
        super().destroy()
    def _set_fullscreen(self):
        """Set window to full screen and make it resizable."""
        self.attributes('-fullscreen', True)
        self.minsize(1024, 600)

    def _setup_bindings(self):
        """Bind keyboard shortcuts for full screen toggle."""
        self.bind('<Escape>', self._toggle_fullscreen)
        self.bind('<F11>', self._toggle_fullscreen)

    def _toggle_fullscreen(self, event=None):
        """Toggle full screen mode."""
        is_fullscreen = self.attributes('-fullscreen')
        self.attributes('-fullscreen', not is_fullscreen)
        if not is_fullscreen:
            self.geometry("{0}x{1}+0+0".format(self.winfo_screenwidth(), self.winfo_screenheight()))

    def _build_ui(self):
        user = AuthManager.get_current_user()

        # Sidebar (right side)
        sidebar = tk.Frame(self, bg=SIDEBAR, width=260)
        sidebar.pack(side="right", fill="y")
        sidebar.pack_propagate(False)

        # Logo (load from file in project root)
        try:
            # Get project root directory (where main.py is)
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_path = os.path.join(project_root, "logo.png")
            if os.path.exists(logo_path):
                img = Image.open(logo_path)
                img = img.resize((60, 60), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
                logo_label = tk.Label(sidebar, image=self.logo_img, bg=SIDEBAR)
                logo_label.pack(pady=(25, 5))
            else:
                print(f"Logo not found at {logo_path}")
        except Exception as e:
            print(f"Logo error: {e}")

        # App title
        tk.Label(sidebar, text="🏭 PM System",
                 font=("Tahoma", 16, "bold"),
                 bg=SIDEBAR, fg=TEXT_SIDE).pack(pady=(5, 15))

        # User info
        tk.Label(sidebar, text=user.full_name,
                 font=("Tahoma", 11, "bold"),
                 bg=SIDEBAR, fg=TEXT_SIDE).pack()
        tk.Label(sidebar, text=ROLE_FA.get(user.role, user.role),
                 font=FONT_SMALL, bg=SIDEBAR, fg=SUBTLE).pack(pady=(2, 20))

        # Separator
        tk.Frame(sidebar, bg=SIDEBAR_HOVER, height=2).pack(fill="x", padx=16, pady=(0, 10))

        # Menu buttons
        for label, view_key, min_role in MENU_ITEMS:
            if not AuthManager.has_permission(min_role):
                continue
            btn = tk.Button(
                sidebar, text=label, font=FONT_MENU,
                bg=SIDEBAR, fg=TEXT_SIDE,
                activebackground=SIDEBAR_HOVER, activeforeground=WHITE,
                relief="flat", anchor="e", padx=20, pady=12,
                cursor="hand2",
                command=lambda v=view_key: self._show_view(v)
            )
            btn.pack(fill="x")

        # Logout button at bottom (no extra space)
        tk.Button(
            sidebar, text="🚪  خروج", font=FONT_MENU,
            bg=SIDEBAR, fg="#FF6B6B",
            activebackground=SIDEBAR_HOVER, activeforeground="#FF6B6B",
            relief="flat", anchor="e", padx=20, pady=12,
            cursor="hand2", command=self._logout
        ).pack(side="bottom", fill="x", pady=(0, 10))

        # Content area
        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side="right", fill="both", expand=True)

    def _show_view(self, view_key: str):
        for w in self.content.winfo_children():
            w.destroy()

        user = AuthManager.get_current_user()
        current_user_dict = {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name
        }

        if view_key == "users":
            from views.users_view import UsersView
            UsersView(
                self.content,
                user_repo=self.user_repo,
                current_user=current_user_dict
            ).pack(fill="both", expand=True)

        elif view_key == "equipment":
            from views.equipment_view import EquipmentView
            EquipmentView(
                self.content,
                equipment_repo=self.equipment_repo,
                current_user=current_user_dict
            ).pack(fill="both", expand=True)

        elif view_key == "pm_schedule":
            from views.pm_view import PMView
            PMView(
                self.content,
                pm_repo=self.pm_repo,
                equipment_repo=self.equipment_repo,
                user_repo=self.user_repo,
                current_user=current_user_dict
            ).pack(fill="both", expand=True)

        elif view_key == "work_orders":
            from views.work_order_view import WorkOrderView
            WorkOrderView(
                self.content,
                work_order_repo=self.wo_repo,
                current_user=current_user_dict
            ).pack(fill="both", expand=True)

        elif view_key == "inspections":
            from views.inspection_view import InspectionView
            InspectionView(
                self.content,
                service=InspectionService(SessionLocal()),
                current_user=current_user_dict
            ).pack(fill="both", expand=True)

        elif view_key == "reports":
            from views.reports_view import ReportsView
            ReportsView(
                self.content,
                current_user=current_user_dict
            ).pack(fill="both", expand=True)

        elif view_key == "spare_parts":
            from views.spare_parts_view import SparePartsView
            SparePartsView(
                self.content,
                session=SessionLocal()
            ).pack(fill="both", expand=True)
        elif view_key == "dashboard":
            from views.dashboard_view import DashboardView
            DashboardView(
                self.content,
                current_user=current_user_dict
            ).pack(fill="both", expand=True)
        else:
            # Placeholder for future views
            container = tk.Frame(self.content, bg=BG)
            container.pack(fill="both", expand=True, padx=30, pady=30)

            card = tk.Frame(container, bg=WHITE,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill="both", expand=True)

            label = next((l for l, v, _ in MENU_ITEMS if v == view_key), view_key)

            tk.Label(card, text=label, font=("Tahoma", 20, "bold"),
                     bg=WHITE, fg=TEXT).pack(pady=(60, 15))
            tk.Label(card, text="این بخش در مراحل بعدی پیاده‌سازی خواهد شد.",
                     font=FONT_CONTENT, bg=WHITE, fg=SUBTLE).pack()

    def _logout(self):
        if messagebox.askyesno("خروج", "آیا می‌خواهید خارج شوید؟"):
            AuthManager.logout()
            self.destroy()
            from views.login_view import LoginView
            LoginView().mainloop()