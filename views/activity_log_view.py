# views/activity_log_view.py
import tkinter as tk
from tkinter import ttk, messagebox
from database.activity_log_repository import ActivityLogRepository
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)


class ActivityLogView(tk.Frame):
    def __init__(self, parent, current_user):
        super().__init__(parent, bg=GRAY_BG)
        if current_user["role"] != "admin":
            messagebox.showerror("خطا", "دسترسی غیرمجاز. فقط مدیر سیستم می‌تواند لاگ فعالیت را مشاهده کند.", parent=parent)
            self.destroy()
            return
        self.current_user = current_user
        self.repo = ActivityLogRepository()
        self._build_ui()
        self._load_logs()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=NAVY, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📋 لاگ فعالیت کاربران", font=FONT_TITLE,
                 bg=NAVY, fg=WHITE).pack(side="right", padx=20, pady=14)

        refresh_btn = tk.Button(header, text="🔄 بروزرسانی", font=FONT_NORMAL,
                                bg=WHITE, fg=NAVY, relief="flat", cursor="hand2",
                                command=self._load_logs, padx=15, pady=5)
        refresh_btn.pack(side="left", padx=20)

        # Treeview
        tree_frame = tk.Frame(self, bg=WHITE, highlightbackground=GRAY_BORDER, highlightthickness=1)
        tree_frame.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("time", "user", "action", "entity", "entity_id", "details")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=20)
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

    def _load_logs(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        logs = self.repo.get_logs(limit=500)
        for log in logs:
            self.tree.insert("", "end", values=(
                log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                log.username,
                log.action,
                log.entity_type,
                log.entity_id or "-",
                (log.details or "")[:80]
            ))