# views/login_view.py
import tkinter as tk
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG,
    TEXT_DARK, TEXT_LIGHT, FONT_TITLE, FONT_NORMAL, FONT_SMALL
)

class LoginView(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ورود به سیستم | PM System")
        self.resizable(False, False)
        self._center_window(420, 520)
        self._build_ui()
        self.bind("<Return>", lambda e: self._do_login())

    def _center_window(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Background: a subtle navy-to-white gradient effect using solid colours
        self.configure(bg=GRAY_BG)

        # Frosted glass card (3 layers for depth)
        shadow = tk.Frame(self, bg="#B0BEC5")
        shadow.place(relx=0.5, rely=0.5, anchor="center", width=370, height=470)

        glass = tk.Frame(shadow, bg=WHITE, padx=40, pady=40)
        glass.pack(fill="both", expand=True, padx=1, pady=1)

        # ── Logo ──
        tk.Label(glass, text="🏭", font=("Tahoma", 48), bg=WHITE, fg=NAVY).pack(pady=(0, 5))
        tk.Label(glass, text="سیستم نگهداری پیشگیرانه",
                 font=FONT_TITLE, bg=WHITE, fg=TEXT_DARK).pack()
        tk.Label(glass, text="لطفاً وارد شوید",
                 font=FONT_SMALL, bg=WHITE, fg=TEXT_LIGHT).pack(pady=(4, 24))

        # ── Username ──
        tk.Label(glass, text="نام کاربری", font=FONT_NORMAL,
                 bg=WHITE, fg=TEXT_DARK, anchor="e").pack(fill="x")
        self.username_var = tk.StringVar()
        username_entry = tk.Entry(glass, textvariable=self.username_var,
                                  font=FONT_NORMAL, justify="right",
                                  relief="solid", bd=1, bg=WHITE, fg=TEXT_DARK)
        username_entry.pack(fill="x", ipady=8, pady=(2, 14))

        # ── Password ──
        tk.Label(glass, text="رمز عبور", font=FONT_NORMAL,
                 bg=WHITE, fg=TEXT_DARK, anchor="e").pack(fill="x")
        self.password_var = tk.StringVar()
        password_entry = tk.Entry(glass, textvariable=self.password_var,
                                  font=FONT_NORMAL, justify="right",
                                  show="●", relief="solid", bd=1,
                                  bg=WHITE, fg=TEXT_DARK)
        password_entry.pack(fill="x", ipady=8, pady=(2, 18))

        # ── Error ──
        self.error_var = tk.StringVar()
        tk.Label(glass, textvariable=self.error_var,
                 font=FONT_SMALL, bg=WHITE, fg=RED).pack()

        # ── Login button ──
        btn = tk.Button(glass, text="ورود", font=FONT_NORMAL,
                        bg=NAVY, fg=WHITE, activebackground=NAVY_LIGHT,
                        activeforeground=WHITE, relief="flat",
                        cursor="hand2", command=self._do_login)
        btn.pack(fill="x", ipady=10, pady=(10, 0))

        # ── Entry hover effects ──
        for entry in (username_entry, password_entry):
            entry.bind("<FocusIn>", lambda e, ent=entry:
                       ent.config(highlightcolor=NAVY, highlightthickness=1))
            entry.bind("<FocusOut>", lambda e, ent=entry:
                       ent.config(highlightthickness=0))

        # ── Button hover animation ──
        btn.bind("<Enter>", lambda e, b=btn: b.config(bg=NAVY_LIGHT))
        btn.bind("<Leave>", lambda e, b=btn: b.config(bg=NAVY))

    def _do_login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        if not username or not password:
            self.error_var.set("نام کاربری و رمز عبور را وارد کنید.")
            return
        from auth.auth_manager import AuthManager
        success, message = AuthManager.login(username, password)
        if success:
            from database.db import init_db
            init_db()
            self.destroy()
            from views.main_view import MainView
            MainView().mainloop()
        else:
            self.error_var.set(message)