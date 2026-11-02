# views/activity_log_view.py
import tkinter as tk
from views.ui_kit import rtl_columns  # RTL (right-to-left) table columns
from tkinter import ttk, messagebox
from database.activity_log_repository import ActivityLogRepository
from database.db import SessionLocal
from utils.theme import (
    NAVY, WHITE, GRAY_BG, GRAY_BORDER, TEXT_DARK, FONT_TITLE,
    FONT_NORMAL
)
# Import Jalali date helper
from utils.date_helpers import to_jalali_datetime_str

CARD_BG = WHITE
CARD_BORDER = GRAY_BORDER
SECTION_BG = GRAY_BG

class ActivityLogView(tk.Frame):
    def __init__(self, parent, current_user):
        super().__init__(parent, bg=SECTION_BG)
        # built-in: admin only; custom roles: «مدیریت نقش‌ها» (read-only page)
        from auth.auth_manager import AuthManager
        if not AuthManager.allows(("admin",), "activity_log", "read"):
            messagebox.showerror("خطا", "دسترسی غیرمجاز. شما مجاز به مشاهده لاگ فعالیت نیستید.", parent=parent)
            self.destroy()
            return
        self.current_user = current_user
        self.repo = ActivityLogRepository(SessionLocal)
        self._build_ui()
        self._load_logs()

    def _build_ui(self):
        header = tk.Frame(self, bg=NAVY, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📋 لاگ فعالیت کاربران", font=FONT_TITLE,
                 bg=NAVY, fg=WHITE).pack(side="right", padx=20, pady=14)

        filter_card = tk.Frame(self, bg=CARD_BORDER)
        filter_card.pack(fill="x", padx=20, pady=(10, 5))
        filter_frame = tk.Frame(filter_card, bg=CARD_BG)
        filter_frame.pack(fill="x", padx=1, pady=1)

        tk.Label(filter_frame, text="فیلتر کاربر:", bg=CARD_BG, font=FONT_NORMAL).pack(side="right", padx=(15,5))
        self.user_filter = tk.StringVar(value="همه")
        user_combo = ttk.Combobox(filter_frame, textvariable=self.user_filter,
                                  values=["همه"] + self._get_user_list(),
                                  state="readonly", width=20, font=FONT_NORMAL)
        user_combo.pack(side="right", padx=5)
        user_combo.bind("<<ComboboxSelected>>", lambda e: self._load_logs())

        tk.Label(filter_frame, text="نوع موجودیت:", bg=CARD_BG, font=FONT_NORMAL).pack(side="right", padx=(15,5))
        self.entity_filter = tk.StringVar(value="همه")
        entity_combo = ttk.Combobox(filter_frame, textvariable=self.entity_filter,
                                    values=["همه", "work_order", "equipment", "pm_schedule", "user", "spare_part", "inspection", "role"],
                                    state="readonly", width=18, font=FONT_NORMAL)
        entity_combo.pack(side="right", padx=5)
        entity_combo.bind("<<ComboboxSelected>>", lambda e: self._load_logs())

        refresh_btn = tk.Button(filter_frame, text="🔄 بروزرسانی", font=FONT_NORMAL,
                                bg=NAVY, fg=WHITE, relief="flat", cursor="hand2",
                                command=self._load_logs, padx=15, pady=5)
        refresh_btn.pack(side="left", padx=10)

        tree_card = tk.Frame(self, bg=CARD_BORDER)
        tree_card.pack(fill="both", expand=True, padx=20, pady=(5, 10))
        tree_frame = tk.Frame(tree_card, bg=CARD_BG)
        tree_frame.pack(fill="both", expand=True, padx=1, pady=1)

        cols = ("time", "user", "action", "entity", "entity_id", "details")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=20)
        rtl_columns(self.tree)  # RTL column order
        self.tree.heading("time", text="زمان")
        self.tree.heading("user", text="کاربر")
        self.tree.heading("action", text="عملیات")
        self.tree.heading("entity", text="نوع موجودیت")
        self.tree.heading("entity_id", text="شناسه")
        self.tree.heading("details", text="جزئیات")

        self.tree.column("time", width=150, anchor="center")
        self.tree.column("user", width=120, anchor="center")
        self.tree.column("action", width=100, anchor="center")
        self.tree.column("entity", width=120, anchor="center")
        self.tree.column("entity_id", width=60, anchor="center")
        self.tree.column("details", width=400, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        style = ttk.Style()
        style.configure("Treeview", background=CARD_BG, fieldbackground=CARD_BG,
                        foreground=TEXT_DARK, rowheight=26, font=FONT_NORMAL)
        style.configure("Treeview.Heading", background=NAVY, foreground=WHITE, font=("Tahoma", 9, "bold"))
        style.map("Treeview", background=[("selected", NAVY)], foreground=[("selected", WHITE)])

    def _get_user_list(self):
        from database.user_repository import UserRepository
        users = UserRepository(SessionLocal).get_all_users()
        return [u['username'] for u in users]

    def _load_logs(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        user = self.user_filter.get()
        if user == "همه":
            user = None
        entity = self.entity_filter.get()
        if entity == "همه":
            entity = None

        logs = self.repo.get_logs(limit=500, user_id=None, entity_type=entity)
        if user:
            logs = [log for log in logs if log.username == user]
        for log in logs:
            # Convert created_at to Jalali
            time_str = to_jalali_datetime_str(log.created_at)
            self.tree.insert("", "end", values=(
                time_str,
                log.username,
                log.action,
                log.entity_type,
                log.entity_id or "-",
                (log.details or "")[:80]
            ))

    def ux_footer_spec(self):
        """Filters shown as removable chips under the table (views/ux.py)."""
        return {"filters": [("کاربر", self.user_filter, "همه"),
                            ("نوع موجودیت", self.entity_filter, "همه")],
                "apply": self._load_logs, "noun": "رویداد"}

