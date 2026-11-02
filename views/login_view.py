# views/login_view.py
"""
Login window.

Look refreshed (company logo, version, live Jalali date); the two entry
widgets are the same plain tk.Entry widgets as in v2.3, so Persian typing
behaves exactly as before.
"""
import os
import sys
import tkinter as tk

from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, BORDER, ACCENT,
    TEXT_DARK, TEXT_LIGHT, FONT_TITLE, FONT_NORMAL, FONT_SMALL,
    apply_app_theme,
)


def _resource(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


class LoginView(tk.Tk):
    def __init__(self):
        super().__init__()
        apply_app_theme(self)
        self.title("ورود به سیستم | PM System")
        self.resizable(False, False)
        try:
            ico = _resource("gela-logo.ico")
            if os.path.exists(ico):
                self.iconbitmap(ico)
        except Exception:
            pass
        self._center_window(440, 580)
        self._build_ui()
        self.bind("<Return>", lambda e: self._do_login())

    def _center_window(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{max(0, y)}")

    def _logo(self, parent):
        """Company logo (falls back to the old icon if the image is missing)."""
        for name in (("views", "gela-logo.png"), ("gela-logo.png",), ("views", "gela-logo.gif")):
            path = _resource(*name)
            if not os.path.exists(path):
                continue
            try:
                from PIL import Image, ImageTk
                img = Image.open(path)
                img.thumbnail((96, 96))
                self._logo_img = ImageTk.PhotoImage(img)
                return tk.Label(parent, image=self._logo_img, bg=WHITE)
            except Exception:
                continue
        return tk.Label(parent, text="🏭", font=("Tahoma", 44), bg=WHITE, fg=NAVY)

    def _build_ui(self):
        self.configure(bg=GRAY_BG)

        band = tk.Frame(self, bg=NAVY, height=150)
        band.place(x=0, y=0, relwidth=1)

        border = tk.Frame(self, bg=BORDER)
        border.place(relx=0.5, rely=0.5, anchor="center", width=372, height=500)
        card = tk.Frame(border, bg=WHITE, padx=36, pady=26)
        card.pack(fill="both", expand=True, padx=1, pady=1)

        self._logo(card).pack(pady=(0, 6))
        tk.Label(card, text="سیستم نگهداری پیشگیرانه",
                 font=FONT_TITLE, bg=WHITE, fg=TEXT_DARK).pack()
        tk.Label(card, text="شرکت گلا - برای ادامه وارد شوید",
                 font=FONT_SMALL, bg=WHITE, fg=TEXT_LIGHT).pack(pady=(4, 20))

        def field(label, show=None):
            tk.Label(card, text=label, font=FONT_NORMAL, bg=WHITE, fg=TEXT_DARK,
                     anchor="e").pack(fill="x")
            var = tk.StringVar(self)      # tied to THIS window (not to a closed main window)
            entry = tk.Entry(card, textvariable=var, font=FONT_NORMAL, justify="right",
                             relief="flat", bd=0, bg="#F8FAFC", fg=TEXT_DARK,
                             insertbackground=TEXT_DARK, highlightthickness=1,
                             highlightbackground=BORDER, highlightcolor=ACCENT)
            if show:
                entry.configure(show=show)
            entry.pack(fill="x", ipady=8, pady=(4, 14))
            return var, entry

        self.username_var, username_entry = field("نام کاربری")
        self.password_var, password_entry = field("رمز عبور", show="●")

        self.error_var = tk.StringVar(self)
        tk.Label(card, textvariable=self.error_var, font=FONT_SMALL, bg=WHITE, fg=RED,
                 wraplength=290, justify="center").pack(pady=(0, 4))

        btn = tk.Button(card, text="ورود", font=("Tahoma", 10, "bold"),
                        bg=NAVY, fg=WHITE, activebackground=NAVY_LIGHT,
                        activeforeground=WHITE, relief="flat", bd=0,
                        cursor="hand2", command=self._do_login)
        btn.pack(fill="x", ipady=9, pady=(6, 0))
        btn.bind("<Enter>", lambda e: btn.config(bg=NAVY_LIGHT))
        btn.bind("<Leave>", lambda e: btn.config(bg=NAVY))
        self._login_btn = btn

        footer = tk.Frame(card, bg=WHITE)
        footer.pack(fill="x", side="bottom")
        self._date_lbl = tk.Label(footer, text="", font=FONT_SMALL, bg=WHITE, fg=TEXT_LIGHT)
        self._date_lbl.pack(side="right")
        try:
            from utils.update_client import current_version
            version = current_version()
        except Exception:
            version = ""
        if version and version != "0.0.0":
            tk.Label(footer, text=f"v{version}", font=FONT_SMALL, bg=WHITE,
                     fg=TEXT_LIGHT).pack(side="left")
        self._tick_date()

        self.after(100, username_entry.focus_set)

    def destroy(self):
        try:
            from views.ui_kit import cancel_pending_afters
            cancel_pending_afters(self)
        except Exception:
            pass
        super().destroy()

    def _tick_date(self):
        try:
            from utils.date_helpers import now_tehran_jalali_text
            self._date_lbl.configure(text=now_tehran_jalali_text())
            self.after(1000, self._tick_date)
        except Exception:
            pass

    def _do_login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        if not username or not password:
            self.error_var.set("نام کاربری و رمز عبور را وارد کنید.")
            return
        self.error_var.set("")
        self._login_btn.configure(text="در حال ورود...", state="disabled")
        self.configure(cursor="watch")
        self.update_idletasks()
        from auth.auth_manager import AuthManager
        success, message = AuthManager.login(username, password)
        if success:
            from database.db import init_db
            init_db()
            self.destroy()
            from views.main_view import MainView
            MainView().mainloop()
        else:
            self.configure(cursor="")
            self._login_btn.configure(text="ورود", state="normal")
            self.error_var.set(message)
