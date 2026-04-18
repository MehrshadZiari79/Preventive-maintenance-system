"""
User Dialog - Add / Edit User Form
"""

import tkinter as tk
from tkinter import ttk, messagebox
from database.user_repository import UserRepository


class UserDialog(tk.Toplevel):
    """Modal dialog for creating or editing a user."""

    ROLES = ["admin", "operator", "viewer"]

    def __init__(self, parent, user_repo: UserRepository,
                 current_user: dict, user_data: dict = None):
        super().__init__(parent)
        self.user_repo = user_repo
        self.current_user = current_user
        self.user_data = user_data          # None → create mode
        self.result = False

        self._setup_window()
        self._build_ui()

        if user_data:
            self._populate(user_data)

        self.grab_set()
        self.wait_window()

    # ──────────────────────── SETUP ─────────────────────────────

    def _setup_window(self):
        title = "ویرایش کاربر" if self.user_data else "افزودن کاربر جدید"
        self.title(title)
        self.resizable(False, False)
        self.configure(bg="#f0f4f8")
        self.geometry("420x520")
        self._center()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 420) // 2
        y = (self.winfo_screenheight() - 520) // 2
        self.geometry(f"420x520+{x}+{y}")

    # ──────────────────────── UI ────────────────────────────────

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg="#1a73e8", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        icon = "✏️" if self.user_data else "➕"
        title = "ویرایش کاربر" if self.user_data else "افزودن کاربر جدید"
        tk.Label(header, text=f"{icon}  {title}",
                 bg="#1a73e8", fg="white",
                 font=("Segoe UI", 13, "bold")).pack(expand=True)

        # Form
        form = tk.Frame(self, bg="#f0f4f8", padx=30, pady=20)
        form.pack(fill="both", expand=True)

        self.entries = {}
        fields = [
            ("نام کاربری *", "username", False),
            ("نام و نام خانوادگی *", "full_name", False),
        ]
        for label, key, _ in fields:
            self._field(form, label, key)

        # Role
        tk.Label(form, text="نقش *", bg="#f0f4f8",
                 font=("Segoe UI", 10), anchor="e").pack(fill="x", pady=(8, 2))
        self.role_var = tk.StringVar(value="operator")
        role_cb = ttk.Combobox(form, textvariable=self.role_var,
                               values=self.ROLES, state="readonly",
                               font=("Segoe UI", 10), justify="right")
        role_cb.pack(fill="x", ipady=4)
        self.entries["role"] = role_cb

        # Password section
        self._password_section(form)

        # Buttons
        self._build_buttons(form)

    def _field(self, parent, label: str, key: str, show: str = ""):
        tk.Label(parent, text=label, bg="#f0f4f8",
                 font=("Segoe UI", 10), anchor="e").pack(fill="x", pady=(8, 2))
        entry = ttk.Entry(parent, font=("Segoe UI", 10),
                          justify="right", show=show)
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

    def _build_buttons(self, parent):
        btn_frame = tk.Frame(parent, bg="#f0f4f8")
        btn_frame.pack(fill="x", pady=(16, 0))

        ttk.Button(btn_frame, text="انصراف",
                   command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(btn_frame, text="ذخیره",
                   style="Accent.TButton",
                   command=self._save).pack(side="right")

    # ──────────────────────── LOGIC ─────────────────────────────

    def _populate(self, data: dict):
        self.entries["username"].insert(0, data["username"])
        self.entries["full_name"].insert(0, data.get("full_name", ""))
        self.role_var.set(data.get("role", "operator"))

    def _save(self):
        username = self.entries["username"].get().strip()
        full_name = self.entries["full_name"].get().strip()
        role = self.role_var.get()
        password = self.entries["password"].get()
        confirm = self.entries["confirm"].get()

        # Validation
        if not username or not full_name:
            messagebox.showwarning("ناقص", "نام کاربری و نام کامل الزامی است.",
                                   parent=self)
            return

        if len(username) < 3:
            messagebox.showwarning("خطا", "نام کاربری باید حداقل ۳ کاراکتر باشد.",
                                   parent=self)
            return

        if password != confirm:
            messagebox.showwarning("خطا", "رمز عبور و تکرار آن یکسان نیستند.",
                                   parent=self)
            return

        if not self.user_data and not password:
            messagebox.showwarning("خطا", "رمز عبور برای کاربر جدید الزامی است.",
                                   parent=self)
            return

        if password and len(password) < 6:
            messagebox.showwarning("خطا", "رمز عبور باید حداقل ۶ کاراکتر باشد.",
                                   parent=self)
            return

        # Persist
        if self.user_data:
            ok, msg = self.user_repo.update_user(
                self.user_data["id"], username, full_name, role)
            if ok and password:
                ok, msg = self.user_repo.change_password(
                    self.user_data["id"], password)
        else:
            ok, msg = self.user_repo.create_user(
                username, password, full_name, role)

        if ok:
            self.result = True
            messagebox.showinfo("موفق", msg, parent=self)
            self.destroy()
        else:
            messagebox.showerror("خطا", msg, parent=self)
