# views/role_manager_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from auth.auth_manager import AuthManager
from utils.theme import (
    NAVY, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

MODULES = [
    ("dashboard",    "داشبورد"),
    ("equipment",    "تجهیزات"),
    ("pm_schedule",  "برنامه نگهداری"),
    ("work_orders",  "دستور کارها"),
    ("inspection",   "بازرسی‌ها"),
    ("spare_parts",  "قطعات یدکی"),
    ("reports",      "گزارشات"),
    ("users",        "مدیریت کاربران"),
    ("activity_log", "لاگ فعالیت"),
    ("machine_hours","ساعات کار دستگاه"),
]

class RoleManagerDialog(tk.Toplevel):
    def __init__(self, parent, callback=None):
        super().__init__(parent)
        self.callback = callback
        self.title("مدیریت نقش‌ها")
        self.geometry("950x700")
        self.configure(bg=GRAY_BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._load_roles()

    def _build_ui(self):
        header = tk.Frame(self, bg=NAVY, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="👤  مدیریت نقش‌ها", font=FONT_HEADING, bg=NAVY, fg=WHITE).pack(pady=10)

        main = tk.Frame(self, bg=GRAY_BG)
        main.pack(fill="both", expand=True, padx=15, pady=15)

        # ── Left panel – role list ─────────────────────────────────
        left = tk.Frame(main, bg=WHITE, width=220, relief="solid", bd=1)
        left.pack(side="left", fill="y", padx=(0,12))
        left.pack_propagate(False)

        tk.Label(left, text="نقش‌ها", font=FONT_HEADING, bg=WHITE, fg=TEXT_DARK).pack(pady=12)
        list_frame = tk.Frame(left, bg=WHITE)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.role_listbox = tk.Listbox(list_frame, font=FONT_NORMAL, bg=WHITE, relief="flat",
                                       selectmode="single", exportselection=False, height=18)
        self.role_listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.role_listbox.yview)
        self.role_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.role_listbox.bind("<<ListboxSelect>>", self._on_role_select)

        btn_frame = tk.Frame(left, bg=WHITE)
        btn_frame.pack(fill="x", padx=10, pady=(0,12))
        tk.Button(btn_frame, text="➕  نقش جدید", font=FONT_SMALL, bg=SUCCESS, fg=WHITE,
                  relief="flat", cursor="hand2", padx=10, pady=6,
                  command=self._add_role).pack(side="left", padx=2)
        tk.Button(btn_frame, text="🗑️  حذف", font=FONT_SMALL, bg=RED, fg=WHITE,
                  relief="flat", cursor="hand2", padx=10, pady=6,
                  command=self._delete_role).pack(side="left", padx=2)

        # ── Right panel – permissions matrix ────────────────────────
        right = tk.Frame(main, bg=WHITE, relief="solid", bd=1)
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text="مجوزهای دسترسی", font=FONT_HEADING, bg=WHITE, fg=TEXT_DARK).pack(pady=12)

        # ── Scrollable area for permissions grid ──────────────────
        canvas = tk.Canvas(right, bg=WHITE, highlightthickness=0)
        vsb = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        self.perm_frame = tk.Frame(canvas, bg=WHITE)

        self.perm_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.perm_frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        vsb.pack(side="right", fill="y")

        # ── Column headers (inside the scrollable frame) ──────────
        header_row = tk.Frame(self.perm_frame, bg=NAVY)
        header_row.pack(fill="x", ipady=8)
        tk.Label(header_row, text="ماژول", font=("Tahoma", 9, "bold"), bg=NAVY, fg=WHITE,
                 width=28, anchor="w").pack(side="left", padx=(10,0))
        for act, text in [("read","مشاهده"), ("write","ایجاد/ویرایش"), ("delete","حذف")]:
            tk.Label(header_row, text=text, font=("Tahoma", 9, "bold"), bg=NAVY, fg=WHITE,
                     width=14, anchor="center").pack(side="left", padx=5)

        # ── Permission rows ────────────────────────────────────────
        self.perm_vars = {}
        for key, label in MODULES:
            row = tk.Frame(self.perm_frame, bg=WHITE)
            row.pack(fill="x", pady=4, ipady=4)
            tk.Label(row, text=label, font=FONT_NORMAL, bg=WHITE, fg=TEXT_DARK,
                     width=28, anchor="w").pack(side="left", padx=(0,10))
            vars_dict = {}
            for act in ("read", "write", "delete"):
                var = tk.BooleanVar(value=False)
                cb = tk.Checkbutton(row, variable=var, bg=WHITE, activebackground=WHITE,
                                    highlightthickness=0)
                cb.pack(side="left", padx=45)
                vars_dict[act] = var
            self.perm_vars[key] = vars_dict

        # ── Save button (outside scrollable area) ─────────────────
        save_btn = tk.Button(right, text="💾  ذخیره تغییرات", font=FONT_NORMAL,
                             bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                             padx=20, pady=10, command=self._save)
        save_btn.pack(pady=15)

    def _load_roles(self):
        self.role_listbox.delete(0, tk.END)
        roles = AuthManager.get_role_list()
        for r in roles:
            display = f"{r['name']} {'(پیش‌فرض)' if r['is_builtin'] else ''}"
            self.role_listbox.insert(tk.END, display)
        self._roles_data = roles

    def _on_role_select(self, event):
        sel = self.role_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        role_info = self._roles_data[idx]
        role_name = role_info["name"]
        perms = AuthManager.get_role_permissions(role_name)
        for module, vars_dict in self.perm_vars.items():
            module_perms = perms.get(module, {})
            for act in ("read", "write", "delete"):
                vars_dict[act].set(module_perms.get(act, False))
        self._current_role = role_name
        self._is_builtin = role_info["is_builtin"]
        state = "disabled" if self._is_builtin else "normal"
        for child in self.perm_frame.winfo_children():
            if isinstance(child, tk.Frame):
                for grandchild in child.winfo_children():
                    if isinstance(grandchild, tk.Checkbutton):
                        grandchild.config(state=state)

    def _add_role(self):
        name = simpledialog.askstring("نقش جدید", "نام نقش جدید را وارد کنید:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        if any(r['name'] == name for r in self._roles_data):
            messagebox.showerror("خطا", "این نام قبلاً وجود دارد.", parent=self)
            return
        perms = {m: {"read": False, "write": False, "delete": False} for m, _ in MODULES}
        ok, msg = AuthManager.save_role_permissions(name, perms)
        if ok:
            self._load_roles()
            messagebox.showinfo("موفق", "نقش اضافه شد.", parent=self)
        else:
            messagebox.showerror("خطا", msg, parent=self)

    def _delete_role(self):
        sel = self.role_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        role_info = self._roles_data[idx]
        if role_info["is_builtin"]:
            messagebox.showwarning("غیرمجاز", "نقش‌های پیش‌فرض قابل حذف نیستند.", parent=self)
            return
        if not messagebox.askyesno("حذف", f"آیا از حذف نقش '{role_info['name']}' اطمینان دارید؟\nکاربران این نقش به تکنسین بازگردانده می‌شوند.", parent=self):
            return
        ok, msg = AuthManager.delete_role(role_info["name"])
        if ok:
            self._load_roles()
            messagebox.showinfo("موفق", msg, parent=self)
        else:
            messagebox.showerror("خطا", msg, parent=self)

    def _save(self):
        if not hasattr(self, '_current_role') or self._is_builtin:
            return
        perms = {}
        for module, vars_dict in self.perm_vars.items():
            perms[module] = {
                "read": vars_dict["read"].get(),
                "write": vars_dict["write"].get(),
                "delete": vars_dict["delete"].get()
            }
        ok, msg = AuthManager.save_role_permissions(self._current_role, perms)
        if ok:
            if self.callback:
                self.callback()
            messagebox.showinfo("موفق", msg, parent=self)
        else:
            messagebox.showerror("خطا", msg, parent=self)