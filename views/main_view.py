# views/main_view.py
import tkinter as tk
from tkinter import messagebox
from auth.auth_manager import AuthManager
from database.models import UserRole
from database.user_repository import UserRepository
from database.equipment_repository import EquipmentRepository
from database.pm_repository import PMRepository
from database.work_order_repository import WorkOrderRepository
from database.inspection_repository import InspectionRepository
from services.inspection_service import InspectionService
from database.db import SessionLocal

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
        self._center_window(1200, 700)

        self.user_repo = UserRepository()
        self.equipment_repo = EquipmentRepository()
        self.pm_repo = PMRepository()
        self.wo_repo = WorkOrderRepository()
        self.inspection_repo = InspectionRepository()

        self._build_ui()
        self._show_view("dashboard")

    def _center_window(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        user = AuthManager.get_current_user()

        sidebar = tk.Frame(self, bg=SIDEBAR, width=230)
        sidebar.pack(side="right", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="🔧 PM System",
                 font=("Tahoma", 14, "bold"),
                 bg=SIDEBAR, fg=TEXT_SIDE).pack(pady=(24, 4))

        tk.Label(sidebar, text=user.full_name,
                 font=("Tahoma", 10, "bold"),
                 bg=SIDEBAR, fg=TEXT_SIDE).pack()

        tk.Label(sidebar, text=ROLE_FA.get(user.role, user.role),
                 font=FONT_SMALL, bg=SIDEBAR, fg=SUBTLE).pack(pady=(2, 20))

        tk.Frame(sidebar, bg=SIDEBAR_HOVER, height=1).pack(fill="x", padx=16, pady=(0, 10))

        for label, view_key, min_role in MENU_ITEMS:
            if not AuthManager.has_permission(min_role):
                continue
            btn = tk.Button(
                sidebar, text=label, font=FONT_MENU,
                bg=SIDEBAR, fg=TEXT_SIDE,
                activebackground=SIDEBAR_HOVER, activeforeground=WHITE,
                relief="flat", anchor="e", padx=20, pady=10,
                cursor="hand2",
                command=lambda v=view_key: self._show_view(v)
            )
            btn.pack(fill="x")

        tk.Frame(sidebar, bg=SIDEBAR_HOVER, height=1).pack(
            side="bottom", fill="x", padx=16, pady=(0, 4))
        tk.Button(
            sidebar, text="🚪  خروج", font=FONT_MENU,
            bg=SIDEBAR, fg="#FF6B6B",
            activebackground=SIDEBAR_HOVER, activeforeground="#FF6B6B",
            relief="flat", anchor="e", padx=20, pady=10,
            cursor="hand2", command=self._logout
        ).pack(side="bottom", fill="x")

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

        else:
            container = tk.Frame(self.content, bg=BG)
            container.pack(fill="both", expand=True, padx=30, pady=30)

            card = tk.Frame(container, bg=WHITE,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill="both", expand=True)

            label = next((l for l, v, _ in MENU_ITEMS if v == view_key), view_key)

            tk.Label(card, text=label, font=("Tahoma", 18, "bold"),
                     bg=WHITE, fg=TEXT).pack(pady=(50, 10))
            tk.Label(card, text="این بخش در مراحل بعدی پیاده‌سازی خواهد شد.",
                     font=FONT_CONTENT, bg=WHITE, fg=SUBTLE).pack()

    def _logout(self):
        if messagebox.askyesno("خروج", "آیا می‌خواهید خارج شوید؟"):
            AuthManager.logout()
            self.destroy()
            from views.login_view import LoginView
            LoginView().mainloop()
