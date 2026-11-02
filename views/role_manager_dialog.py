# views/role_manager_dialog.py
"""
مدیریت نقش‌ها و مجوزها
======================

* Built-in roles (مدیر سیستم، مدیر، تکنسین، کارشناس تولید) are locked; their
  REAL permissions are shown read-only (✓ / ✕ / ◐ partly) instead of empty
  boxes that looked like "no access".
* Custom roles: one matrix of pages × actions (مشاهده، ایجاد/ویرایش، تأیید،
  حذف).  Only the actions that mean something on a page can be ticked; the
  others show «—».  «مدیریت کاربران» stays with the system admin (whoever
  manages users could make himself admin).
* Every page of the program follows this matrix (AuthManager.allows), so a
  ticked box is never ignored any more.
* New role: empty, or as a copy of any role.  Rename / copy / delete act on
  the selected role; deleting a role that still has users asks which role
  they move to (they were silently made «تکنسین» before).
* Unsaved changes: «بازگردانی» or a question when another role is chosen /
  the window is closed.  Changes are written to the activity log.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from auth.auth_manager import (
    AuthManager, PERMISSION_MODULES, PERMISSION_ACTIONS, MODULE_ACTIONS,
    ADMIN_ONLY_MODULES, BUILTIN_PERMISSIONS, BUILTIN_PARTIAL_NOTES, PARTIAL,
    ROLE_NAME_MAX_LEN, BUILTIN_ROLE_FA, normalize_permissions,
)
from utils.theme import (
    NAVY, WHITE, GRAY_BG, BORDER, BORDER_STRONG, TEXT_DARK, TEXT_MUTED, ACCENT,
    SURFACE_ALT, SUCCESS, WARNING, WARNING_SOFT, INFO, INFO_SOFT, DANGER,
    FONT_NORMAL, FONT_BOLD, FONT_SMALL, FONT_HEADING, FONT_TITLE,
)
from views.ui_kit import button, card, center_window, rtl_columns

# Kept for code that still imports these names from here.
MODULES = PERMISSION_MODULES
ACTIONS = PERMISSION_ACTIONS

BUILTIN_FA = BUILTIN_ROLE_FA
BUILTIN_DESC = {
    "admin": "دسترسی کامل به همه بخش‌ها، از جمله مدیریت کاربران و نقش‌ها و لاگ فعالیت.",
    "manager": "همه بخش‌ها با ایجاد، تأیید و حذف؛ به‌جز مدیریت کاربران و لاگ فعالیت.",
    "technician": "کار روزانه نگهداری: تجهیزات، دستور کارها، درخواست تعمیرات، قطعات یدکی و "
                  "ساعت کار ماشین؛ بدون تأیید و (به‌جز قطعات) بدون حذف.",
    "production_expert": "داشبورد، مشاهده تجهیزات، ثبت دستور کار و درخواست تعمیرات.",
}
MODULE_ICONS = {
    "dashboard": "📊", "equipment": "⚙️", "pm_schedule": "📅", "work_orders": "📝",
    "repair_request": "📄", "personnel_management": "👥", "inspection": "🔍",
    "spare_parts": "🔧", "reports": "📈", "users": "👤", "activity_log": "📋",
    "machine_hours": "⏱️",
}
LEGEND = (
    "•  «تأیید» فقط در دستور کارها: تأیید ایجاد، تأیید نهایی، رد اتمام و تولید PM. ویرایش و تغییر وضعیت دستور کار برای همه نقش‌ها آزاد است.",
    "•  «حذف» در تجهیزات شامل مدیریت دسته‌بندی‌ها و موقعیت‌ها است. با فعال کردن هر کار، «مشاهده» هم فعال می‌شود.",
    "•  مجوز صفحه‌ها بلافاصله اعمال می‌شود؛ منوی کاربرانِ این نقش پس از ورود دوباره به‌روز می‌شود.",
)
EMPTY_BASE = "بدون دسترسی (فقط داشبورد)"


def role_label(name):
    return BUILTIN_FA.get(name, name)


def _fa(n):
    return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _base_permissions(role_name):
    """Matrix to start a new role from (partly-allowed actions are left off)."""
    if not role_name:
        perms = {m: {} for m, _ in PERMISSION_MODULES}
        perms["dashboard"] = {"read": True}
        return normalize_permissions(perms)
    perms = AuthManager.get_role_permissions(role_name)
    return normalize_permissions({
        m: {a: (v is True) for a, v in acts.items()} for m, acts in perms.items()
    })


# =============================================================================
# main window
# =============================================================================

class RoleManagerDialog(tk.Toplevel):

    def __init__(self, parent, callback=None):
        super().__init__(parent)
        self.callback = callback
        self.withdraw()
        self.title("مدیریت نقش‌ها و مجوزها")
        self.configure(bg=GRAY_BG)
        self.transient(parent.winfo_toplevel())
        self.minsize(900, 600)

        self._roles = []            # [{"name", "is_builtin", "users"}]
        self._current = None
        self._is_builtin = True
        self._saved = {}            # matrix as stored (for «بازگردانی» / dirty check)
        self._dirty = False
        self.perm_vars = {}         # module -> action -> BooleanVar
        self._cells = {}            # (module, action) -> (checkbutton, symbol label, applicable)
        self._admin_only = {}       # module -> span label shown for custom roles
        self._all_links = {}        # action -> «همه» label

        self._styles()
        self._build_ui()
        self._load_roles()
        center_window(self, 1060, 720, parent)
        self.deiconify()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _e: self._close())

    # ------------------------------------------------------------------ UI

    def _styles(self):
        style = ttk.Style(self)
        style.configure("Roles.Treeview", font=FONT_NORMAL, rowheight=30,
                        background=WHITE, fieldbackground=WHITE, borderwidth=0)
        style.configure("Roles.Treeview.Heading", font=FONT_BOLD,
                        background=SURFACE_ALT, foreground=TEXT_DARK, relief="flat")
        style.map("Roles.Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected", WHITE)])

    def _build_ui(self):
        header = tk.Frame(self, bg=NAVY, padx=22, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="🛡  مدیریت نقش‌ها و مجوزها", font=FONT_TITLE,
                 bg=NAVY, fg=WHITE).pack(anchor="e")
        tk.Label(header, text="برای هر نقش مشخص کنید در هر بخش چه کارهایی مجاز است. "
                              "نقش‌های پیش‌فرض قفل هستند؛ برای دسترسی متفاوت، نقش سفارشی بسازید.",
                 font=FONT_SMALL, bg=NAVY, fg="#C9D6EA").pack(anchor="e", pady=(3, 0))

        body = tk.Frame(self, bg=GRAY_BG)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        self._build_role_list(body)
        self._build_editor(body)

    def _build_role_list(self, body):
        outer, side = card(body, padx=12, pady=12)
        outer.pack(side="right", fill="y")

        tk.Label(side, text="نقش‌ها", font=FONT_HEADING, bg=WHITE, fg=TEXT_DARK).pack(anchor="e")

        # the button first (bottom), so the list can never push it out of view
        button(side, "＋  نقش جدید", self._new_role, kind="success").pack(fill="x", side="bottom")

        frame = tk.Frame(side, bg=WHITE)
        frame.pack(fill="both", expand=True, pady=(8, 10))
        self.role_tree = ttk.Treeview(frame, columns=("name", "users"), show="headings",
                                      selectmode="browse", height=12, style="Roles.Treeview")
        rtl_columns(self.role_tree)
        self.role_tree.heading("name", text="نقش", anchor="e")
        self.role_tree.heading("users", text="کاربران", anchor="center")
        self.role_tree.column("name", width=180, anchor="e")
        self.role_tree.column("users", width=62, anchor="center", stretch=False)
        self.role_tree.tag_configure("section", background=SURFACE_ALT, foreground=TEXT_MUTED,
                                     font=FONT_BOLD)
        self.role_tree.tag_configure("empty", foreground=TEXT_MUTED, font=FONT_SMALL)
        self.role_tree.tag_configure("builtin", foreground=TEXT_DARK)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.role_tree.yview)
        self.role_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="left", fill="y")
        self.role_tree.pack(side="right", fill="both", expand=True)
        self.role_tree.bind("<<TreeviewSelect>>", self._on_select)

    def _build_editor(self, body):
        outer, main = card(body, padx=0, pady=0)
        outer.pack(side="right", fill="both", expand=True, padx=(0, 12))

        # ---- title bar: role name, kind, users | actions ----
        bar = tk.Frame(main, bg=WHITE, padx=18, pady=12)
        bar.pack(fill="x")
        actions = tk.Frame(bar, bg=WHITE)
        actions.pack(side="left", anchor="n")
        self.delete_btn = button(actions, "🗑  حذف", self._delete_role, kind="danger")
        self.delete_btn.pack(side="left")
        self.copy_btn = button(actions, "⧉  کپی", self._copy_role, kind="secondary")
        self.copy_btn.pack(side="left", padx=6)
        self.rename_btn = button(actions, "✏️  تغییر نام", self._rename_role, kind="secondary")
        self.rename_btn.pack(side="left")

        titles = tk.Frame(bar, bg=WHITE)
        titles.pack(side="right", fill="x", expand=True)
        line = tk.Frame(titles, bg=WHITE)
        line.pack(anchor="e")
        self.title_lbl = tk.Label(line, text="یک نقش را انتخاب کنید", font=FONT_TITLE,
                                  bg=WHITE, fg=TEXT_DARK)
        self.title_lbl.pack(side="right")
        self.badge = tk.Label(line, text="", font=FONT_SMALL, padx=8, pady=1)
        self.users_lbl = tk.Label(titles, text="", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED,
                                  anchor="e", justify="right", wraplength=460)
        self.users_lbl.pack(anchor="e", pady=(4, 0))

        tk.Frame(main, bg=BORDER, height=1).pack(fill="x")

        self.note = tk.Label(main, text="", font=FONT_SMALL, bg=INFO_SOFT, fg=INFO,
                             anchor="e", justify="right", padx=14, pady=7, wraplength=640)
        self._note_anchor = tk.Frame(main, bg=WHITE, height=0)
        self._note_anchor.pack(fill="x")

        # ---- footer (packed before the matrix so it always stays visible) ----
        footer = tk.Frame(main, bg=WHITE, padx=18, pady=10)
        footer.pack(fill="x", side="bottom")
        tk.Frame(main, bg=BORDER, height=1).pack(fill="x", side="bottom")
        self.save_btn = button(footer, "💾  ذخیره تغییرات", self._save, kind="success")
        self.save_btn.pack(side="left")
        self.revert_btn = button(footer, "↺  بازگردانی", self._revert, kind="secondary")
        self.revert_btn.pack(side="left", padx=6)
        self.summary_lbl = tk.Label(footer, text="", font=FONT_BOLD, bg=WHITE, fg=TEXT_DARK)
        self.summary_lbl.pack(side="right")
        self.dirty_lbl = tk.Label(footer, text="", font=FONT_SMALL, bg=WHITE, fg=WARNING)
        self.dirty_lbl.pack(side="right", padx=12)

        legend = tk.Frame(main, bg=WHITE, padx=18, pady=6)
        legend.pack(fill="x", side="bottom")
        for line in LEGEND:
            tk.Label(legend, text=line, font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED, anchor="e",
                     justify="right").pack(fill="x")

        # ---- matrix ----
        grid = tk.Frame(main, bg=WHITE, padx=18, pady=10)
        grid.pack(fill="both", expand=True)
        name_col = len(PERMISSION_ACTIONS)

        tk.Label(grid, text="بخش", font=FONT_BOLD, bg=SURFACE_ALT, fg=TEXT_DARK, anchor="e",
                 padx=10, pady=6).grid(row=0, column=name_col, sticky="nsew")
        for i, (action, title) in enumerate(PERMISSION_ACTIONS):
            head = tk.Frame(grid, bg=SURFACE_ALT)
            head.grid(row=0, column=name_col - 1 - i, sticky="nsew")
            tk.Label(head, text=title, font=FONT_BOLD, bg=SURFACE_ALT, fg=TEXT_DARK,
                     pady=3).pack()
            link = tk.Label(head, text="همه", font=FONT_SMALL, bg=SURFACE_ALT, fg=ACCENT,
                            cursor="hand2")
            link.pack(pady=(0, 3))
            link.bind("<Button-1>", lambda _e, a=action: self._toggle_column(a))
            self._all_links[action] = link

        row_pad = 5 if self.winfo_screenheight() >= 820 else 2
        for r, (module, label) in enumerate(PERMISSION_MODULES, start=1):
            bg = WHITE if r % 2 else "#FAFBFD"
            name = tk.Label(grid, text=f"{label}   {MODULE_ICONS.get(module, '')}",
                            font=FONT_NORMAL, bg=bg, fg=TEXT_DARK, anchor="e",
                            padx=10, pady=row_pad, cursor="hand2")
            name.grid(row=r, column=name_col, sticky="nsew")
            name.bind("<Button-1>", lambda _e, m=module: self._toggle_row(m))
            self.perm_vars[module] = {}
            for i, (action, _title) in enumerate(PERMISSION_ACTIONS):
                cell = tk.Frame(grid, bg=bg)
                cell.grid(row=r, column=name_col - 1 - i, sticky="nsew")
                var = tk.BooleanVar(value=False)
                cb = tk.Checkbutton(cell, variable=var, bg=bg, activebackground=bg,
                                    highlightthickness=0, selectcolor=WHITE, cursor="hand2",
                                    command=lambda m=module, a=action: self._on_toggle(m, a))
                sym = tk.Label(cell, text="—", font=FONT_BOLD, bg=bg, fg=BORDER_STRONG)
                applicable = action in MODULE_ACTIONS.get(module, ("read",))
                self._cells[(module, action)] = (cb, sym, applicable)
                self.perm_vars[module][action] = var
            if module in ADMIN_ONLY_MODULES:
                lock = tk.Label(grid, text="🔒  فقط مدیر سیستم — برای امنیت به نقش دیگری داده نمی‌شود",
                                font=FONT_SMALL, bg=bg, fg=TEXT_MUTED)
                lock.grid(row=r, column=0, columnspan=name_col, sticky="nsew")
                lock.grid_remove()
                self._admin_only[module] = lock

        grid.grid_columnconfigure(name_col, weight=3, minsize=210)
        for c in range(name_col):
            grid.grid_columnconfigure(c, weight=1, minsize=96)

        self._render(None, editable=False)

    # ------------------------------------------------------------ rendering

    def _render(self, perms, editable):
        """Show a matrix: check boxes (custom role) or ✓ / ✕ / ◐ (built-in, read-only)."""
        perms = perms or {}
        for (module, action), (cb, sym, applicable) in self._cells.items():
            value = (perms.get(module) or {}).get(action, False)
            cb.pack_forget()
            sym.pack_forget()
            if not applicable:
                sym.configure(text="—", fg=BORDER_STRONG)
                sym.pack(expand=True, pady=2)
            elif editable and module not in ADMIN_ONLY_MODULES:
                self.perm_vars[module][action].set(value is True)
                cb.pack(expand=True)
            elif value == PARTIAL:
                sym.configure(text="◐", fg=WARNING)
                sym.pack(expand=True, pady=2)
            elif value:
                sym.configure(text="✓", fg=SUCCESS)
                sym.pack(expand=True, pady=2)
            else:
                sym.configure(text="✕", fg="#C0C7D1")
                sym.pack(expand=True, pady=2)
        for module, lock in self._admin_only.items():
            if editable:
                lock.grid()
                lock.lift()
            else:
                lock.grid_remove()
        for link in self._all_links.values():
            link.configure(text="همه" if editable else "", cursor="hand2" if editable else "arrow")

    def _matrix(self):
        """The ticked boxes (cleaned the same way they are stored)."""
        return normalize_permissions({
            m: {a: var.get() for a, var in acts.items()} for m, acts in self.perm_vars.items()
        })

    def _refresh_state(self):
        """Dirty flag, button states and the summary line."""
        custom = bool(self._current) and not self._is_builtin
        self._dirty = custom and self._matrix() != self._saved
        self.dirty_lbl.configure(text="●  تغییرات ذخیره نشده" if self._dirty else "", fg=WARNING)
        for btn, ok in ((self.save_btn, self._dirty), (self.revert_btn, self._dirty),
                        (self.rename_btn, custom), (self.delete_btn, custom),
                        (self.copy_btn, bool(self._current))):
            btn.configure(state="normal" if ok else "disabled", cursor="hand2" if ok else "arrow")

        if not self._current:
            self.summary_lbl.configure(text="")
            return
        perms = self._matrix() if custom else BUILTIN_PERMISSIONS.get(self._current, {})
        pages = sum(1 for m, _ in PERMISSION_MODULES if (perms.get(m) or {}).get("read"))
        counts = {a: sum(1 for m, _ in PERMISSION_MODULES
                         if a in MODULE_ACTIONS.get(m, ()) and (perms.get(m) or {}).get(a))
                  for a in ("write", "approve", "delete")}
        self.summary_lbl.configure(
            text=f"{_fa(pages)} بخش از {_fa(len(PERMISSION_MODULES))}   •   "
                 f"ایجاد/ویرایش: {_fa(counts['write'])}   •   تأیید: {_fa(counts['approve'])}   •   "
                 f"حذف: {_fa(counts['delete'])}")

    # ------------------------------------------------------------------ data

    def _load_roles(self, select=None):
        try:
            roles = AuthManager.get_role_list()
        except Exception as exc:
            messagebox.showerror("خطا", f"خطا در بارگذاری نقش‌ها:\n{exc}", parent=self)
            roles = []
        for role in roles:
            role["users"] = AuthManager.count_role_users(role["name"])
        self._roles = roles

        tree = self.role_tree
        tree.delete(*tree.get_children())
        tree.insert("", "end", iid="sec:builtin", values=("نقش‌های پیش‌فرض (قفل)", ""),
                    tags=("section",))
        for role in roles:
            if role["is_builtin"]:
                tree.insert("", "end", iid=f"role:{role['name']}",
                            values=(f"🔒  {role_label(role['name'])}", _fa(role["users"])),
                            tags=("builtin",))
        tree.insert("", "end", iid="sec:custom", values=("نقش‌های سفارشی", ""), tags=("section",))
        customs = [r for r in roles if not r["is_builtin"]]
        for role in customs:
            tree.insert("", "end", iid=f"role:{role['name']}",
                        values=(role["name"], _fa(role["users"])))
        if not customs:
            tree.insert("", "end", iid="sec:none",
                        values=("هنوز نقشی ساخته نشده — «＋ نقش جدید»", ""), tags=("empty",))

        target = select or self._current
        if target and tree.exists(f"role:{target}"):
            self._current = None                     # force a fresh show
            tree.selection_set(f"role:{target}")
            tree.see(f"role:{target}")
            self._show_role(target)
        else:
            self._show_role(None)

    def _on_select(self, _event=None):
        sel = self.role_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not iid.startswith("role:"):
            self._reselect_current()
            return
        name = iid[len("role:"):]
        if name == self._current:
            return
        if not self._resolve_unsaved():
            self._reselect_current()
            return
        self._show_role(name)

    def _reselect_current(self):
        iid = f"role:{self._current}" if self._current else None
        if iid and self.role_tree.exists(iid):
            self.role_tree.selection_set(iid)
        else:
            self.role_tree.selection_remove(*self.role_tree.selection())

    def _show_role(self, name):
        self._current = name
        info = next((r for r in self._roles if r["name"] == name), None)
        if info is None:
            self._current, self._is_builtin, self._saved = None, True, {}
            self.title_lbl.configure(text="یک نقش را انتخاب کنید")
            self.badge.pack_forget()
            self.users_lbl.configure(text="از فهرست سمت راست یک نقش را انتخاب کنید یا «＋ نقش جدید» بسازید.")
            self.note.pack_forget()
            self._render(None, editable=False)
            self._refresh_state()
            return

        self._is_builtin = info["is_builtin"]
        self.title_lbl.configure(text=role_label(name))
        if self._is_builtin:
            self.badge.configure(text="پیش‌فرض • فقط‌خواندنی", bg=SURFACE_ALT, fg=TEXT_MUTED)
        else:
            self.badge.configure(text="سفارشی", bg="#EAF1FF", fg=ACCENT)
        self.badge.pack(side="right", padx=(10, 0))

        users = AuthManager.get_role_users(name)
        if users:
            shown = "، ".join(users[:4]) + (f" و {_fa(len(users) - 4)} نفر دیگر" if len(users) > 4 else "")
            self.users_lbl.configure(text=f"{_fa(len(users))} کاربر: {shown}")
        else:
            self.users_lbl.configure(text="هیچ کاربری این نقش را ندارد.")

        if self._is_builtin:
            note = BUILTIN_DESC.get(name, "")
            if name in BUILTIN_PARTIAL_NOTES:
                note += "   ◐ " + BUILTIN_PARTIAL_NOTES[name]
            note += "   برای دسترسی متفاوت از «⧉ کپی» یک نقش سفارشی بسازید."
            self.note.configure(text=note, bg=INFO_SOFT, fg=INFO)
            self.note.pack(fill="x", after=self._note_anchor)
            self._saved = {}
            self._render(BUILTIN_PERMISSIONS.get(name, {}), editable=False)
        else:
            self.note.pack_forget()
            try:
                self._saved = AuthManager.get_role_permissions(name)
            except Exception as exc:
                messagebox.showerror("خطا", f"خطا در خواندن مجوزها:\n{exc}", parent=self)
                self._saved = normalize_permissions({})
            self._render(self._saved, editable=True)
        self._refresh_state()

    # --------------------------------------------------------------- toggles

    def _on_toggle(self, module, action):
        row = self.perm_vars[module]
        if action != "read" and row[action].get():
            row["read"].set(True)                       # any action needs «مشاهده»
        if action == "read" and not row["read"].get():
            for other, var in row.items():
                if other != "read":
                    var.set(False)
        self._refresh_state()

    def _editable_modules(self):
        return [m for m, _ in PERMISSION_MODULES if m not in ADMIN_ONLY_MODULES]

    def _toggle_column(self, action):
        if self._is_builtin or not self._current:
            return
        modules = [m for m in self._editable_modules() if action in MODULE_ACTIONS.get(m, ())]
        turn_on = not all(self.perm_vars[m][action].get() for m in modules)
        for module in modules:
            self.perm_vars[module][action].set(turn_on)
            self._on_toggle(module, action)

    def _toggle_row(self, module):
        if self._is_builtin or not self._current or module in ADMIN_ONLY_MODULES:
            return
        actions = MODULE_ACTIONS.get(module, ("read",))
        turn_on = not all(self.perm_vars[module][a].get() for a in actions)
        for action in actions:
            self.perm_vars[module][action].set(turn_on)
        self._on_toggle(module, "read" if not turn_on else actions[-1])

    # --------------------------------------------------------------- actions

    def _resolve_unsaved(self):
        """True when it is fine to leave the current role (saved, discarded, or clean)."""
        if not self._dirty:
            return True
        answer = messagebox.askyesnocancel(
            "تغییرات ذخیره نشده", f"تغییرات نقش «{self._current}» ذخیره شود؟", parent=self)
        if answer is None:
            return False
        if answer:
            return self._save(quiet=True)
        self._revert()
        return True

    def _save(self, quiet=False):
        if self._is_builtin or not self._current:
            return False
        ok, msg = AuthManager.save_role_permissions(self._current, self._matrix())
        if not ok:
            messagebox.showerror("خطا", msg, parent=self)
            return False
        self._saved = AuthManager.get_role_permissions(self._current)
        self._render(self._saved, editable=True)
        self._refresh_state()
        if not quiet:
            self.dirty_lbl.configure(text="✓  ذخیره شد", fg=SUCCESS)
            self.after(2500, lambda: self.dirty_lbl.winfo_exists() and not self._dirty
                       and self.dirty_lbl.configure(text=""))
        if self.callback:
            self.callback()
        return True

    def _revert(self):
        if self._is_builtin or not self._current:
            return
        self._render(self._saved, editable=True)
        self._refresh_state()

    def _new_role(self, base=None):
        if not self._resolve_unsaved():
            return
        dlg = _NewRoleDialog(self, self._roles, base)
        self.wait_window(dlg)
        self._regrab()
        if not dlg.result:
            return
        name, base_role = dlg.result
        ok, msg = AuthManager.save_role_permissions(name, _base_permissions(base_role))
        if not ok:
            messagebox.showerror("خطا", msg, parent=self)
            return
        self._load_roles(select=name)
        if self.callback:
            self.callback()

    def _copy_role(self):
        if self._current:
            self._new_role(base=self._current)

    def _rename_role(self):
        if self._is_builtin or not self._current or not self._resolve_unsaved():
            return
        dlg = _NameDialog(self, self._current, [r["name"] for r in self._roles])
        self.wait_window(dlg)
        self._regrab()
        if not dlg.result or dlg.result == self._current:
            return
        ok, msg = AuthManager.rename_role(self._current, dlg.result)
        if not ok:
            messagebox.showerror("خطا", msg, parent=self)
            return
        self._current = None
        self._load_roles(select=dlg.result)
        if self.callback:
            self.callback()

    def _delete_role(self):
        if self._is_builtin or not self._current:
            return
        dlg = _DeleteRoleDialog(self, self._current, AuthManager.get_role_users(self._current),
                                [r for r in self._roles if r["name"] != self._current])
        self.wait_window(dlg)
        self._regrab()
        if not dlg.confirmed:
            return
        ok, msg = AuthManager.delete_role(self._current, dlg.move_to)
        if not ok:
            messagebox.showerror("خطا", msg, parent=self)
            return
        self._current, self._dirty = None, False
        self._load_roles()
        messagebox.showinfo("حذف نقش", msg, parent=self)
        if self.callback:
            self.callback()

    def _regrab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _close(self):
        if not self._resolve_unsaved():
            return
        self.destroy()


# =============================================================================
# small dialogs
# =============================================================================

class _SmallDialog(tk.Toplevel):
    """Header + body + footer, inline error line, Enter / Esc."""

    def __init__(self, parent, title, width=440):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=WHITE)
        self.transient(parent)
        self.resizable(False, False)
        head = tk.Frame(self, bg=NAVY, padx=18, pady=10)
        head.pack(fill="x")
        tk.Label(head, text=title, font=FONT_HEADING, bg=NAVY, fg=WHITE).pack(anchor="e")
        self.body = tk.Frame(self, bg=WHITE, padx=18, pady=14)
        self.body.pack(fill="both", expand=True)
        self.error = tk.Label(self, text="", font=FONT_SMALL, bg=WHITE, fg=DANGER, anchor="e",
                              justify="right", wraplength=width - 40, padx=18)
        self.error.pack(fill="x")
        self.footer = tk.Frame(self, bg=WHITE, padx=18, pady=12)
        self.footer.pack(fill="x")
        self._width = width
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _show(self, focus=None):
        self.update_idletasks()
        center_window(self, max(self._width, self.winfo_reqwidth()), self.winfo_reqheight())
        self.deiconify()
        self.grab_set()
        if focus is not None:
            focus.focus_set()

    def _ok(self):
        raise NotImplementedError


def _name_entry(parent, var):
    row = tk.Frame(parent, bg=WHITE)
    row.pack(fill="x", pady=(4, 0))
    counter = tk.Label(row, text="", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED, width=7)
    counter.pack(side="left")
    entry = ttk.Entry(row, textvariable=var, justify="right", font=FONT_NORMAL)
    entry.pack(side="right", fill="x", expand=True)

    def update(*_):
        n = len(var.get().strip())
        counter.configure(text=f"{_fa(n)}/{_fa(ROLE_NAME_MAX_LEN)}",
                          fg=DANGER if n > ROLE_NAME_MAX_LEN else TEXT_MUTED)
    var.trace_add("write", update)
    update()
    return entry


class _NewRoleDialog(_SmallDialog):
    """Name + «شروع از» (empty or a copy of any role)."""

    def __init__(self, parent, roles, base=None):
        super().__init__(parent, "نقش جدید", width=460)
        self.result = None
        self.existing = [r["name"] for r in roles]
        self.base_by_label = {EMPTY_BASE: None}
        for r in roles:
            text = f"کپی از «{role_label(r['name'])}»" + ("  (پیش‌فرض)" if r["is_builtin"] else "")
            self.base_by_label[text] = r["name"]

        tk.Label(self.body, text="نام نقش", font=FONT_BOLD, bg=WHITE, fg=TEXT_DARK).pack(anchor="e")
        self.name_var = tk.StringVar()
        if base:
            suggested = f"کپی {role_label(base)}"[:ROLE_NAME_MAX_LEN]
            self.name_var.set(suggested)
        entry = _name_entry(self.body, self.name_var)
        self.name_var.trace_add("write", lambda *_: self.error.configure(text=""))

        tk.Label(self.body, text="شروع از", font=FONT_BOLD, bg=WHITE, fg=TEXT_DARK).pack(
            anchor="e", pady=(12, 0))
        self.base_var = tk.StringVar(value=EMPTY_BASE)
        for label, name in self.base_by_label.items():
            if name == base and base:
                self.base_var.set(label)
        combo = ttk.Combobox(self.body, textvariable=self.base_var, state="readonly",
                             values=list(self.base_by_label), justify="right", font=FONT_NORMAL)
        combo.pack(fill="x", pady=(4, 0))
        self.hint = tk.Label(self.body, text="", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED,
                             anchor="e", justify="right", wraplength=420)
        self.hint.pack(fill="x", pady=(6, 0))
        combo.bind("<<ComboboxSelected>>", lambda *_: self._update_hint())
        self._update_hint()

        button(self.footer, "ساخت نقش", self._ok, kind="success").pack(side="right")
        button(self.footer, "انصراف", self.destroy, kind="secondary").pack(side="right", padx=6)
        self._show(entry)
        entry.select_range(0, "end")

    def _update_hint(self):
        base = self.base_by_label.get(self.base_var.get())
        if not base:
            self.hint.configure(text="نقش بدون دسترسی ساخته می‌شود (فقط داشبورد)؛ سپس مجوزها را تیک بزنید.")
        elif base in BUILTIN_PARTIAL_NOTES:
            self.hint.configure(text="مجوزهای این نقش کپی می‌شود. مواردی که در آن «◐ جزئی» هستند "
                                     "در نقش جدید خاموش‌اند و در صورت نیاز آن‌ها را تیک بزنید.")
        else:
            self.hint.configure(text="مجوزهای این نقش کپی می‌شود و می‌توانید آن‌ها را تغییر دهید.")

    def _ok(self):
        name = self.name_var.get().strip()
        error = AuthManager.validate_role_name(name, self.existing)
        if error:
            self.error.configure(text=error)
            return
        self.result = (name, self.base_by_label.get(self.base_var.get()))
        self.destroy()


class _NameDialog(_SmallDialog):
    """Rename a custom role (its users move with it)."""

    def __init__(self, parent, current, existing):
        super().__init__(parent, "تغییر نام نقش")
        self.result = None
        self.current = current
        self.existing = [n for n in existing if n != current]
        tk.Label(self.body, text=f"نام جدید برای «{current}»", font=FONT_BOLD, bg=WHITE,
                 fg=TEXT_DARK).pack(anchor="e")
        self.var = tk.StringVar(value=current)
        entry = _name_entry(self.body, self.var)
        self.var.trace_add("write", lambda *_: self.error.configure(text=""))
        tk.Label(self.body, text="کاربران این نقش با نام جدید باقی می‌مانند.", font=FONT_SMALL,
                 bg=WHITE, fg=TEXT_MUTED).pack(anchor="e", pady=(6, 0))
        button(self.footer, "تأیید", self._ok, kind="primary").pack(side="right")
        button(self.footer, "انصراف", self.destroy, kind="secondary").pack(side="right", padx=6)
        self._show(entry)
        entry.select_range(0, "end")

    def _ok(self):
        name = self.var.get().strip()
        if name == self.current:
            self.destroy()
            return
        error = AuthManager.validate_role_name(name, self.existing)
        if error:
            self.error.configure(text=error)
            return
        self.result = name
        self.destroy()


class _DeleteRoleDialog(_SmallDialog):
    """Confirm; when the role still has users, ask which role they move to."""

    def __init__(self, parent, role, users, other_roles):
        super().__init__(parent, "حذف نقش", width=480)
        self.confirmed = False
        self.move_to = None
        self.users = users
        self.label_to_name = {
            (f"{role_label(r['name'])}  (پیش‌فرض)" if r["is_builtin"] else r["name"]): r["name"]
            for r in other_roles
        }

        tk.Label(self.body, text=f"نقش «{role}» حذف شود؟", font=FONT_HEADING, bg=WHITE,
                 fg=TEXT_DARK).pack(anchor="e")
        if users:
            listing = "\n".join(f"•  {u}" for u in users[:8])
            if len(users) > 8:
                listing += f"\n…  و {_fa(len(users) - 8)} نفر دیگر"
            tk.Label(self.body, text=f"{_fa(len(users))} کاربر این نقش را دارند:", font=FONT_NORMAL,
                     bg=WHITE, fg=TEXT_DARK).pack(anchor="e", pady=(10, 2))
            tk.Label(self.body, text=listing, font=FONT_SMALL, bg=SURFACE_ALT, fg=TEXT_DARK,
                     anchor="e", justify="right", padx=10, pady=6).pack(fill="x")
            tk.Label(self.body, text="انتقال این کاربران به نقش:", font=FONT_BOLD, bg=WHITE,
                     fg=TEXT_DARK).pack(anchor="e", pady=(10, 0))
            self.target_var = tk.StringVar()
            self.target_var.trace_add("write", lambda *_: self.error.configure(text=""))
            ttk.Combobox(self.body, textvariable=self.target_var, state="readonly",
                         values=list(self.label_to_name), justify="right",
                         font=FONT_NORMAL).pack(fill="x", pady=(4, 0))
            tk.Label(self.body, text="کاربران از این پس دسترسی‌های نقش انتخاب‌شده را خواهند داشت.",
                     font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(anchor="e", pady=(4, 0))
        else:
            tk.Label(self.body, text="هیچ کاربری این نقش را ندارد.", font=FONT_NORMAL, bg=WHITE,
                     fg=TEXT_MUTED).pack(anchor="e", pady=(8, 0))
        tk.Label(self.body, text="این کار قابل بازگشت نیست.", font=FONT_SMALL, bg=WARNING_SOFT,
                 fg="#92400E", anchor="e", padx=10, pady=5).pack(fill="x", pady=(12, 0))

        button(self.footer, "🗑  حذف نقش", self._ok, kind="danger").pack(side="right")
        button(self.footer, "انصراف", self.destroy, kind="secondary").pack(side="right", padx=6)
        self._show()

    def _ok(self):
        if self.users:
            label = self.target_var.get()
            if label not in self.label_to_name:
                self.error.configure(text="نقش جایگزین را برای کاربران انتخاب کنید.")
                return
            self.move_to = self.label_to_name[label]
        self.confirmed = True
        self.destroy()
