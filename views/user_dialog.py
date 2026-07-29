# views/user_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
from database.user_repository import UserRepository
from database.models import UserRole
from auth.auth_manager import AuthManager
from utils.theme import (
    NAVY, WHITE, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

CARD_BG = WHITE
PRIMARY = NAVY

class UserDialog(tk.Toplevel):
    def __init__(self, parent, user_repo: UserRepository,
                 current_user: dict, user_data: dict = None):
        super().__init__(parent)
        self.user_repo = user_repo
        self.current_user = current_user
        self.user_data = user_data
        self.result = False

        self._setup_window()
        self._build_ui()

        if user_data:
            self._populate(user_data)

        self.grab_set()
        self.wait_window()

    def _setup_window(self):
        title = "ویرایش کاربر" if self.user_data else "افزودن کاربر جدید"
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=GRAY_BG)
        self.geometry("420x600")
        self._center()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 420) // 2
        y = (self.winfo_screenheight() - 600) // 2
        self.geometry(f"420x600+{x}+{y}")

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────
        header = tk.Frame(self, bg=PRIMARY, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        icon = "✏️" if self.user_data else "➕"
        title = "ویرایش کاربر" if self.user_data else "افزودن کاربر جدید"
        tk.Label(header, text=f"{icon}  {title}", bg=PRIMARY, fg=WHITE, font=FONT_HEADING).pack(expand=True)

        # ── Scrollable area ────────────────────────────────────
        canvas = tk.Canvas(self, bg=GRAY_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=GRAY_BG)

        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        vsb.pack(side="right", fill="y")

        # ── Form inside scrollable ─────────────────────────────
        form = tk.Frame(scrollable, bg=CARD_BG, padx=30, pady=20)
        form.pack(fill="both", expand=True)

        self.entries = {}
        fields = [
            ("نام کاربری *", "username"),
            ("نام و نام خانوادگی *", "full_name"),
            ("شماره پرسنلی", "personnel_code"),
            ("واحد خدمت", "service_unit"),
        ]
        for label, key in fields:
            self._field(form, label, key)

        tk.Label(form, text="نقش *", bg=CARD_BG, font=FONT_NORMAL, anchor="e").pack(fill="x", pady=(8,2))
        self.role_var = tk.StringVar(value=UserRole.TECHNICIAN.value)
        self.role_combo = ttk.Combobox(form, textvariable=self.role_var,
                                       font=FONT_NORMAL, state="readonly", justify="right")
        self.role_combo.pack(fill="x", ipady=4)
        self.entries["role"] = self.role_combo
        self._load_roles()

        self._password_section(form)

        # ── Buttons (outside scrollable) ──────────────────────
        btn_frame = tk.Frame(self, bg=CARD_BG)
        btn_frame.pack(fill="x", padx=30, pady=15)
        ttk.Button(btn_frame, text="انصراف", command=self.destroy).pack(side="left", padx=(0,8))
        ttk.Button(btn_frame, text="ذخیره", style="Accent.TButton",
                   command=self._save).pack(side="right")

    def _load_roles(self):
        roles = AuthManager.get_role_list()
        role_names = [r['name'] for r in roles]
        self.role_combo['values'] = role_names

    def _field(self, parent, label: str, key: str, show: str = ""):
        tk.Label(parent, text=label, bg=CARD_BG, font=FONT_NORMAL, anchor="e").pack(fill="x", pady=(8,2))
        entry = ttk.Entry(parent, font=FONT_NORMAL, justify="right", show=show)
        entry.pack(fill="x", ipady=4)
        self.entries[key] = entry

    def _password_section(self, parent):
        sep = ttk.Separator(parent, orient="horizontal")
        sep.pack(fill="x", pady=12)
        if self.user_data:
            lbl = "رمز عبور جدید (خالی = بدون تغییر)"
        else:
            lbl = "رمز عبور *"
        self._field(parent, lbl, "password", show="●")
        self._field(parent, "تکرار رمز عبور", "confirm", show="●")

    def _populate(self, data: dict):
        self.entries["username"].insert(0, data["username"])
        self.entries["full_name"].insert(0, data.get("full_name", ""))
        self.entries["personnel_code"].insert(0, data.get("personnel_code", ""))
        self.entries["service_unit"].insert(0, data.get("service_unit", ""))
        role = data.get("role", UserRole.TECHNICIAN.value)
        if role not in self.role_combo['values']:
            role = UserRole.TECHNICIAN.value
        self.role_var.set(role)

    def _save(self):
        username = self.entries["username"].get().strip()
        full_name = self.entries["full_name"].get().strip()
        role = self.role_var.get()
        personnel_code = self.entries["personnel_code"].get().strip() or None
        service_unit = self.entries["service_unit"].get().strip() or None
        password = self.entries["password"].get()
        confirm = self.entries["confirm"].get()

        if not username or not full_name:
            messagebox.showwarning("ناقص", "نام کاربری و نام کامل الزامی است.", parent=self)
            return
        if len(username) < 3:
            messagebox.showwarning("خطا", "نام کاربری باید حداقل ۳ کاراکتر باشد.", parent=self)
            return
        if password != confirm:
            messagebox.showwarning("خطا", "رمز عبور و تکرار آن یکسان نیستند.", parent=self)
            return
        if not self.user_data and not password:
            messagebox.showwarning("خطا", "رمز عبور برای کاربر جدید الزامی است.", parent=self)
            return
        if password and len(password) < 3:
            messagebox.showwarning("خطا", "رمز عبور باید حداقل 3 کاراکتر باشد.", parent=self)
            return

        if self.user_data:
            ok, msg = self.user_repo.update_user(self.user_data["id"], username, full_name, role,
                                                 personnel_code=personnel_code,
                                                 service_unit=service_unit)
            if ok and password:
                ok, msg = self.user_repo.change_password(self.user_data["id"], password)
        else:
            ok, msg = self.user_repo.create_user(username, password, full_name, role,
                                                 personnel_code=personnel_code,
                                                 service_unit=service_unit)

        if ok:
            self.result = True
            messagebox.showinfo("موفق", msg, parent=self)
            self.destroy()
        else:
            messagebox.showerror("خطا", msg, parent=self)