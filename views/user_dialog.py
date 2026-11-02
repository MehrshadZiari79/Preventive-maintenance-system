import tkinter as tk
from tkinter import ttk, messagebox
from views.ux import field_error

from database.user_repository import UserRepository
from database.models import UserRole
from auth.auth_manager import AuthManager
from utils.theme import (
    NAVY, WHITE, GRAY_BG, GRAY_BORDER, TEXT_DARK, SUCCESS,
    FONT_HEADING, FONT_NORMAL
)

CARD_BG = WHITE
PRIMARY = NAVY
BORDER = GRAY_BORDER
TEXT = TEXT_DARK


class UserDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        user_repo: UserRepository,
        current_user: dict,
        user_data: dict = None
    ):
        super().__init__(parent)

        self.parent = parent
        self.user_repo = user_repo
        self.current_user = current_user
        self.user_data = user_data
        self.result = False

        self._setup_window()
        self._build_ui()

        if user_data:
            self._populate(user_data)

        self.transient(parent)
        self.grab_set()

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _setup_window(self):
        title = "ویرایش کاربر" if self.user_data else "افزودن کاربر جدید"
        self.title(title)

        # The footer is fixed outside the scrollable area, so the action
        # buttons can never disappear behind the form.
        self.resizable(True, True)
        self.minsize(500, 620)
        self.configure(bg=GRAY_BG)

        self.geometry("560x720")
        self._center()

    def _center(self):
        self.update_idletasks()

        width = 560
        height = 720
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_ui(self):
        # Root layout:
        # row 0 = header
        # row 1 = scrollable form
        # row 2 = fixed footer
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────────
        header = tk.Frame(self, bg=PRIMARY, height=60)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        icon = "✏️" if self.user_data else "➕"
        title = "ویرایش کاربر" if self.user_data else "افزودن کاربر جدید"

        tk.Label(
            header,
            text=f"{icon}  {title}",
            bg=PRIMARY,
            fg=WHITE,
            font=FONT_HEADING
        ).pack(expand=True)

        # ── Scrollable form area ───────────────────────────────
        content = tk.Frame(self, bg=GRAY_BG)
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(
            content,
            bg=GRAY_BG,
            highlightthickness=0,
            bd=0
        )
        self._form_canvas = canvas
        vsb = ttk.Scrollbar(
            content,
            orient="vertical",
            command=canvas.yview
        )

        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        canvas.configure(yscrollcommand=vsb.set)

        scrollable = tk.Frame(canvas, bg=GRAY_BG)
        window_id = canvas.create_window(
            (0, 0),
            window=scrollable,
            anchor="nw"
        )

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_scrollable(event):
            # Keep the form exactly as wide as the visible canvas.
            # This prevents the right side of the fields from being clipped.
            canvas.itemconfigure(window_id, width=event.width)

        scrollable.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_scrollable)

        # Mouse-wheel support when the pointer is over the form.
        canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        canvas.bind_all("<Button-4>", self._on_mousewheel, add="+")
        canvas.bind_all("<Button-5>", self._on_mousewheel, add="+")

        # ── Form card ──────────────────────────────────────────
        form = tk.Frame(
            scrollable,
            bg=CARD_BG,
            padx=28,
            pady=18
        )
        form.pack(fill="both", expand=True)

        self.entries = {}

        self._add_entry_field(
            form,
            "نام کاربری *",
            "username"
        )
        self._add_entry_field(
            form,
            "نام و نام خانوادگی *",
            "full_name"
        )
        self._add_entry_field(
            form,
            "شماره پرسنلی",
            "personnel_code"
        )
        self._add_entry_field(
            form,
            "واحد خدمت",
            "service_unit"
        )

        # Role
        tk.Label(
            form,
            text="نقش *",
            bg=CARD_BG,
            fg=TEXT,
            font=FONT_NORMAL,
            anchor="e"
        ).pack(fill="x", pady=(5, 2))

        self.role_var = tk.StringVar(
            value=UserRole.TECHNICIAN.value
        )

        self.role_combo = ttk.Combobox(
            form,
            textvariable=self.role_var,
            font=FONT_NORMAL,
            state="readonly",
            justify="right"
        )
        self.role_combo.pack(
            fill="x",
            ipady=4,
            pady=(0, 8)
        )

        self.entries["role"] = self.role_combo
        self._load_roles()

        ttk.Separator(
            form,
            orient="horizontal"
        ).pack(fill="x", pady=12)

        # Password
        pwd_label = (
            "رمز عبور جدید (خالی = بدون تغییر)"
            if self.user_data
            else "رمز عبور *"
        )

        self._add_entry_field(
            form,
            pwd_label,
            "password",
            show="●"
        )

        self._add_entry_field(
            form,
            "تکرار رمز عبور",
            "confirm",
            show="●"
        )

        # Extra bottom padding inside the scrollable form.
        tk.Frame(
            form,
            bg=CARD_BG,
            height=5
        ).pack(fill="x")

        # ── Fixed footer ───────────────────────────────────────
        footer = tk.Frame(
            self,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        footer.grid(
            row=2,
            column=0,
            sticky="ew"
        )

        button_row = tk.Frame(
            footer,
            bg=CARD_BG
        )
        button_row.pack(
            anchor="center",
            pady=12
        )

        tk.Button(
            button_row,
            text="انصراف",
            font=FONT_NORMAL,
            bg=BORDER,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            cursor="hand2",
            padx=28,
            pady=8,
            command=self.destroy
        ).pack(side="left", padx=6)

        tk.Button(
            button_row,
            text="ذخیره",
            font=FONT_NORMAL,
            bg=SUCCESS,
            fg=WHITE,
            activebackground=SUCCESS,
            activeforeground=WHITE,
            relief="flat",
            cursor="hand2",
            padx=30,
            pady=8,
            command=self._save
        ).pack(side="left", padx=6)

        # Keyboard shortcuts.
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Control-s>", lambda _event: self._save())

        self.after(50, self._update_scroll_region)

    def _add_entry_field(self, parent, label, field, show=None):
        tk.Label(
            parent,
            text=label,
            bg=CARD_BG,
            fg=TEXT,
            font=FONT_NORMAL,
            anchor="e"
        ).pack(
            fill="x",
            pady=(5, 2)
        )

        kwargs = {
            "font": FONT_NORMAL,
            "justify": "right"
        }

        if show is not None:
            kwargs["show"] = show

        entry = ttk.Entry(parent, **kwargs)
        entry.pack(
            fill="x",
            ipady=4,
            pady=(0, 8)
        )

        self.entries[field] = entry

    def _update_scroll_region(self):
        # Find the canvas used by this dialog and refresh its scroll area.
        for widget in self.winfo_children():
            if isinstance(widget, tk.Frame):
                pass

        # The scrollable canvas is stored explicitly when available.
        canvas = getattr(self, "_form_canvas", None)
        if canvas is not None:
            canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_mousewheel(self, event):
        canvas = getattr(self, "_form_canvas", None)
        if canvas is None:
            return

        # Only scroll this dialog when the pointer is inside the dialog.
        try:
            x = self.winfo_pointerx()
            y = self.winfo_pointery()

            left = self.winfo_rootx()
            top = self.winfo_rooty()
            right = left + self.winfo_width()
            bottom = top + self.winfo_height()

            if not (left <= x <= right and top <= y <= bottom):
                return

            if getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")
            else:
                delta = -1 if event.delta > 0 else 1
                canvas.yview_scroll(delta, "units")
        except tk.TclError:
            pass

    def _load_roles(self):
        roles = AuthManager.get_role_list()
        role_names = [r["name"] for r in roles]
        self.role_combo["values"] = role_names

    def _populate(self, data: dict):
        self.entries["username"].insert(
            0, data.get("username", "")
        )
        self.entries["full_name"].insert(
            0, data.get("full_name", "")
        )
        self.entries["personnel_code"].insert(
            0, data.get("personnel_code", "")
        )
        self.entries["service_unit"].insert(
            0, data.get("service_unit", "")
        )

        role = data.get(
            "role",
            UserRole.TECHNICIAN.value
        )

        if role in self.role_combo["values"]:
            self.role_var.set(role)
        else:
            self.role_var.set(
                UserRole.TECHNICIAN.value
            )

    def _save(self):
        username = self.entries["username"].get().strip()
        full_name = self.entries["full_name"].get().strip()
        role = self.role_var.get()
        personnel_code = (
            self.entries["personnel_code"].get().strip() or None
        )
        service_unit = (
            self.entries["service_unit"].get().strip() or None
        )
        password = self.entries["password"].get()
        confirm = self.entries["confirm"].get()

        if not username or not full_name:
            if not username:
                field_error(self.entries["username"], "نام کاربری الزامی است.")
            if not full_name:
                field_error(self.entries["full_name"], "نام کامل الزامی است.",
                            focus=bool(username))
            return

        if len(username) < 3:
            field_error(self.entries["username"], "نام کاربری باید حداقل ۳ کاراکتر باشد.")
            return

        if password != confirm:
            field_error(self.entries["confirm"], "رمز عبور و تکرار آن یکسان نیستند.")
            return

        if not self.user_data and not password:
            field_error(self.entries["password"], "رمز عبور برای کاربر جدید الزامی است.")
            return

        if password and len(password) < 3:
            field_error(self.entries["password"], "رمز عبور باید حداقل ۳ کاراکتر باشد.")
            return

        if self.user_data:
            ok, msg = self.user_repo.update_user(
                self.user_data["id"],
                username,
                full_name,
                role,
                personnel_code=personnel_code,
                service_unit=service_unit
            )

            if ok and password:
                ok, msg = self.user_repo.change_password(
                    self.user_data["id"],
                    password
                )
        else:
            ok, msg = self.user_repo.create_user(
                username,
                password,
                full_name,
                role,
                personnel_code=personnel_code,
                service_unit=service_unit
            )

        if ok:
            self.result = True
            messagebox.showinfo(
                "موفق",
                msg,
                parent=self
            )
            self.destroy()
        else:
            messagebox.showerror(
                "خطا",
                msg,
                parent=self
            )
