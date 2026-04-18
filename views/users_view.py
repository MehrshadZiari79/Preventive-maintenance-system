"""
Users View - Main User Management Panel
"""

import tkinter as tk
from tkinter import ttk, messagebox
from database.user_repository import UserRepository
from views.user_dialog import UserDialog


class UsersView(tk.Frame):
    """Full user management panel embedded in the main window."""

    COLUMNS = {
        "id":         ("#",              50,  "center"),
        "username":   ("نام کاربری",    140,  "center"),
        "full_name":  ("نام کامل",      180,  "center"),
        "role":       ("نقش",            90,  "center"),
        "is_active":  ("وضعیت",          80,  "center"),
        "created_at": ("تاریخ ثبت",     140,  "center"),
    }

    def __init__(self, parent, user_repo: UserRepository, current_user: dict):
        super().__init__(parent, bg="#f0f4f8")
        self.user_repo = user_repo
        self.current_user = current_user
        self._build_ui()
        self.load_users()

    # ──────────────────────── UI ────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_toolbar()
        self._build_table()
        self._build_statusbar()

    def _build_header(self):
        header = tk.Frame(self, bg="#1a73e8", height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="👥  مدیریت کاربران",
                 bg="#1a73e8", fg="white",
                 font=("Segoe UI", 14, "bold")).pack(expand=True)

    def _build_toolbar(self):
        bar = tk.Frame(self, bg="#ffffff", pady=8, padx=12)
        bar.pack(fill="x")

        # Search
        tk.Label(bar, text="🔍", bg="#ffffff",
                 font=("Segoe UI", 11)).pack(side="right", padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search())
        search_entry = ttk.Entry(bar, textvariable=self.search_var,
                                 width=22, font=("Segoe UI", 10),
                                 justify="right")
        search_entry.pack(side="right", ipady=3)

        # Buttons (admin only)
        if self.current_user["role"] == "admin":
            ttk.Button(bar, text="➕ کاربر جدید",
                       command=self._add_user).pack(side="left", padx=(0, 6))
            ttk.Button(bar, text="✏️ ویرایش",
                       command=self._edit_user).pack(side="left", padx=(0, 6))
            ttk.Button(bar, text="🔄 فعال/غیرفعال",
                       command=self._toggle_user).pack(side="left", padx=(0, 6))
            ttk.Button(bar, text="🗑️ حذف",
                       command=self._delete_user).pack(side="left")

        ttk.Button(bar, text="🔃 بازخوانی",
                   command=self.load_users).pack(side="left", padx=(12, 0))

    def _build_table(self):
        container = tk.Frame(self, bg="#f0f4f8")
        container.pack(fill="both", expand=True, padx=12, pady=8)

        cols = list(self.COLUMNS.keys())
        self.tree = ttk.Treeview(container, columns=cols,
                                 show="headings", selectmode="browse")

        for col, (heading, width, anchor) in self.COLUMNS.items():
            self.tree.heading(col, text=heading,
                              command=lambda c=col: self._sort(c))
            self.tree.column(col, width=width, anchor=anchor, minwidth=40)

        # Scrollbars
        vsb = ttk.Scrollbar(container, orient="vertical",
                            command=self.tree.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal",
                            command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set,
                            xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        # Row tags
        self.tree.tag_configure("active",   background="#e8f5e9")
        self.tree.tag_configure("inactive", background="#fce4ec")
        self.tree.tag_configure("admin_row", foreground="#1a73e8")

        self.tree.bind("<Double-1>", lambda _: self._edit_user())

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="در حال بارگذاری...")
        tk.Label(self, textvariable=self.status_var,
                 bg="#e8eaf6", fg="#555", anchor="e",
                 font=("Segoe UI", 9), padx=10).pack(fill="x", side="bottom")

    # ──────────────────────── DATA ──────────────────────────────

    def load_users(self, users: list = None):
        self.tree.delete(*self.tree.get_children())
        data = users if users is not None else self.user_repo.get_all_users()
        for u in data:
            status = "✅ فعال" if u["is_active"] else "❌ غیرفعال"
            tag = "active" if u["is_active"] else "inactive"
            if u["role"] == "admin":
                tag = "admin_row"
            created = str(u.get("created_at", ""))[:10]
            self.tree.insert("", "end", iid=str(u["id"]),
                             values=(u["id"], u["username"], u["full_name"],
                                     u["role"], status, created),
                             tags=(tag,))
        count = len(data)
        self.status_var.set(f"تعداد کاربران: {count}")

    def _on_search(self):
        keyword = self.search_var.get().strip()
        if keyword:
            results = self.user_repo.search_users(keyword)
        else:
            results = self.user_repo.get_all_users()
        self.load_users(results)

    def _sort(self, col: str):
        """Toggle sort on column header click."""
        items = [(self.tree.set(k, col), k)
                 for k in self.tree.get_children("")]
        items.sort(reverse=getattr(self, "_sort_reverse", False))
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)
        self._sort_reverse = not getattr(self, "_sort_reverse", False)

    # ──────────────────────── ACTIONS ───────────────────────────

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
        dlg = UserDialog(self, self.user_repo, self.current_user,
                         user_data=user_data)
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
        confirm = messagebox.askyesno(
            "تأیید حذف",
            f"آیا از حذف کاربر «{user['username']}» مطمئن هستید؟\n"
            "این عمل قابل بازگشت نیست.",
        )
        if confirm:
            ok, msg = self.user_repo.delete_user(uid)
            if ok:
                self.load_users()
            else:
                messagebox.showerror("خطا", msg)
