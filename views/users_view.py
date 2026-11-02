# views/users_view.py
import tkinter as tk
from views.ui_kit import rtl_columns  # RTL (right-to-left) table columns
from tkinter import ttk, messagebox
from datetime import datetime  # <-- ADD THIS IMPORT
from database.user_repository import UserRepository
from views.user_dialog import UserDialog
from views.role_manager_dialog import RoleManagerDialog
from utils.theme import (
    NAVY, WHITE, GRAY_BG, GRAY_BORDER, TEXT_LIGHT, FONT_TITLE,
    FONT_NORMAL, FONT_SMALL
)
from utils.date_helpers import to_jalali_date_str

BG = GRAY_BG
PRIMARY = NAVY

# Persian names for the built-in roles (custom roles are shown as typed).
_ROLE_FA = {"admin": "مدیر سیستم", "manager": "مدیر", "technician": "تکنسین", "production_expert": "کارشناس تولید"}


class UsersView(tk.Frame):
    # Rows are no longer tinted by status: the status badge shows it (views/ux.py).
    ux_status_only_rows = True

    COLUMNS = {
        "id":              ("#",              50,  "center"),
        "username":        ("نام کاربری",    140,  "center"),
        "full_name":       ("نام کامل",      180,  "center"),
        "role":            ("نقش",            90,  "center"),
        "personnel_code":  ("شماره پرسنلی",  120,  "center"),
        "service_unit":    ("واحد خدمت",     120,  "center"),
        "is_active":       ("وضعیت",          80,  "center"),
        "created_at":      ("تاریخ ثبت",     140,  "center"),
    }

    def __init__(self, parent, user_repo: UserRepository, current_user: dict):
        super().__init__(parent, bg=BG)
        if current_user["role"] != "admin":
            messagebox.showerror("خطا", "دسترسی غیرمجاز.", parent=parent)
            self.destroy()
            return
        self.user_repo = user_repo
        self.current_user = current_user
        self._build_ui()
        self.load_users()

    def _build_ui(self):
        self._build_header()
        self._build_toolbar()
        self._build_table()
        self._build_statusbar()

    def _build_header(self):
        header = tk.Frame(self, bg=PRIMARY, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="👥  مدیریت کاربران", bg=PRIMARY, fg=WHITE, font=FONT_TITLE).pack(side="right", padx=20)

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=WHITE, pady=8, padx=12)
        bar.pack(fill="x")
        tk.Label(bar, text="🔍", bg=WHITE, font=FONT_NORMAL).pack(side="right", padx=(0,4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search())
        ttk.Entry(bar, textvariable=self.search_var, width=22, font=FONT_NORMAL, justify="right").pack(side="right", ipady=3)

        if self.current_user["role"] == "admin":
            ttk.Button(bar, text="➕ کاربر جدید", command=self._add_user).pack(side="left", padx=(0,6))
            ttk.Button(bar, text="✏️ ویرایش", command=self._edit_user).pack(side="left", padx=(0,6))
            ttk.Button(bar, text="🔄 فعال/غیرفعال", command=self._toggle_user).pack(side="left", padx=(0,6))
            ttk.Button(bar, text="🗑️ حذف", command=self._delete_user).pack(side="left")
            ttk.Button(bar, text="👤 مدیریت نقش‌ها", command=self._manage_roles).pack(side="left", padx=(12,0))
        ttk.Button(bar, text="🔃 بازخوانی", command=self.load_users).pack(side="left", padx=(12,0))

    def _manage_roles(self):
        dlg = RoleManagerDialog(self, callback=lambda: self.load_users())
        self.wait_window(dlg)
        self.load_users()

    def _build_table(self):
        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True, padx=12, pady=8)

        cols = list(self.COLUMNS.keys())
        self.tree = ttk.Treeview(container, columns=cols, show="headings", selectmode="browse")
        rtl_columns(self.tree)  # RTL column order
        for col, (heading, width, anchor) in self.COLUMNS.items():
            self.tree.heading(col, text=heading, command=lambda c=col: self._sort(c))
            self.tree.column(col, width=width, anchor=anchor, minwidth=40)

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.tree.configure(selectmode='extended')
        self.tree.bind("<Delete>", lambda e: self._delete_selected())
        self.tree.bind("<F2>",      lambda e: self._edit_user())
        self.tree.bind("<Control-n>", lambda e: self._add_user())

        self.tree.tag_configure("active",   background="#E6F4EA")
        self.tree.tag_configure("inactive", background="#FCE8E6")
        self.tree.tag_configure("admin_row", foreground=PRIMARY)
        self.tree.bind("<Double-1>", lambda _: self._edit_user())

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="در حال بارگذاری...")
        tk.Label(self, textvariable=self.status_var, bg=GRAY_BORDER, fg=TEXT_LIGHT,
                 anchor="e", font=FONT_SMALL, padx=10).pack(fill="x", side="bottom")

    def load_users(self, users: list = None):
        self.tree.delete(*self.tree.get_children())
        data = users if users is not None else self.user_repo.get_all_users()
        for u in data:
            status = "✅ فعال" if u["is_active"] else "❌ غیرفعال"
            tag = "active" if u["is_active"] else "inactive"
            if u["role"] == "admin":
                tag = "admin_row"
            created_dt = u.get("created_at")
            if created_dt and hasattr(created_dt, 'strftime'):
                created_str = to_jalali_date_str(created_dt)
            elif isinstance(created_dt, str):
                try:
                    dt = datetime.strptime(created_dt[:10], "%Y-%m-%d")
                    created_str = to_jalali_date_str(dt)
                except:
                    created_str = created_dt[:10]
            else:
                created_str = "—"
            self.tree.insert("", "end", iid=str(u["id"]),
                             values=(u["id"], u["username"], u["full_name"],
                                     _ROLE_FA.get(u["role"], u["role"]), u.get("personnel_code", ""),
                                     u.get("service_unit", ""), status, created_str),
                             tags=(tag,))
        self.status_var.set(f"تعداد کاربران: {len(data)}")

    def _delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("انتخاب", "لطفاً یک کاربر انتخاب کنید.")
            return
        if self.current_user["id"] in [int(i) for i in selected]:
            messagebox.showwarning("خطا", "نمی‌توانید حساب خود را حذف کنید.")
            return
        if not messagebox.askyesno("حذف", f"آیا از حذف {len(selected)} کاربر اطمینان دارید؟"):
            return
        errors = []
        for uid in selected:
            ok, msg = self.user_repo.delete_user(int(uid))
            if not ok:
                errors.append(msg)
        self.load_users()
        if errors:
            messagebox.showerror("خطا", "\n".join(errors[:5]))

    def _on_search(self):
        keyword = self.search_var.get().strip()
        results = self.user_repo.search_users(keyword) if keyword else self.user_repo.get_all_users()
        self.load_users(results)

    def _sort(self, col: str):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        items.sort(reverse=getattr(self, "_sort_reverse", False))
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)
        self._sort_reverse = not getattr(self, "_sort_reverse", False)

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add_user(self):
        dlg = UserDialog(self, self.user_repo, self.current_user)
        if dlg.result:
            self.load_users()

    def _edit_user(self):
        uid = self._selected_id()
        if not uid:
            messagebox.showinfo("انتخاب", "لطفاً یک کاربر انتخاب کنید.")
            return
        user_data = self.user_repo.get_user_by_id(uid)
        if not user_data:
            return
        dlg = UserDialog(self, self.user_repo, self.current_user, user_data=user_data)
        if dlg.result:
            self.load_users()

    def _toggle_user(self):
        uid = self._selected_id()
        if not uid:
            messagebox.showinfo("انتخاب", "لطفاً یک کاربر انتخاب کنید.")
            return
        if uid == self.current_user["id"]:
            messagebox.showwarning("خطا", "نمی‌توانید حساب خود را غیرفعال کنید.")
            return
        ok, msg = self.user_repo.toggle_active(uid)
        if ok:
            self.load_users()
        else:
            messagebox.showerror("خطا", msg)

    def _delete_user(self):
        uid = self._selected_id()
        if not uid:
            messagebox.showinfo("انتخاب", "لطفاً یک کاربر انتخاب کنید.")
            return
        if uid == self.current_user["id"]:
            messagebox.showwarning("خطا", "نمی‌توانید حساب خود را حذف کنید.")
            return
        user = self.user_repo.get_user_by_id(uid)
        confirm = messagebox.askyesno("تأیید حذف", f"آیا از حذف کاربر «{user['username']}» مطمئن هستید؟\nاین عمل قابل بازگشت نیست.")
        if confirm:
            ok, msg = self.user_repo.delete_user(uid)
            if ok:
                self.load_users()
            elif user.get("is_active") and "غیرفعال" in msg:
                if messagebox.askyesno("حذف ممکن نیست", msg + "\n\nکاربر الان غیرفعال شود؟"):
                    ok2, msg2 = self.user_repo.toggle_active(uid)
                    if ok2:
                        self.load_users()
                    else:
                        messagebox.showerror("خطا", msg2)
            else:
                messagebox.showerror("خطا", msg)

    def ux_footer_spec(self):
        """Filters shown as removable chips under the table (views/ux.py)."""
        return {"filters": [("جستجو", self.search_var, "")], "noun": "کاربر"}

