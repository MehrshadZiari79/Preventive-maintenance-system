# views/login_view.py
import tkinter as tk
from auth.auth_manager import AuthManager
from utils.theme import NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, TEXT_DARK, TEXT_LIGHT, FONT_TITLE, FONT_NORMAL, FONT_SMALL

class LoginView(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ورود به سیستم | PM System")
        self.resizable(False, False)
        self.configure(bg=GRAY_BG)
        self._center_window(420, 520)
        self._build_ui()

    def _center_window(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Main card with navy border
        card = tk.Frame(self, bg=WHITE, padx=40, pady=40,
                        highlightbackground=NAVY, highlightthickness=2)
        card.place(relx=0.5, rely=0.5, anchor="center", width=360, height=450)

        # Logo / icon
        tk.Label(card, text="🏭", font=("Tahoma", 48),
                 bg=WHITE, fg=NAVY).pack(pady=(0, 5))
        tk.Label(card, text="سیستم نگهداری پیشگیرانه",
                 font=FONT_TITLE, bg=WHITE, fg=TEXT_DARK).pack()
        tk.Label(card, text="لطفاً وارد شوید",
                 font=FONT_SMALL, bg=WHITE, fg=TEXT_LIGHT).pack(pady=(4, 20))

        # Username
        tk.Label(card, text="نام کاربری", font=FONT_NORMAL,
                 bg=WHITE, fg=TEXT_DARK, anchor="e").pack(fill="x")
        self.username_var = tk.StringVar()
        tk.Entry(card, textvariable=self.username_var, font=FONT_NORMAL,
                 justify="right", relief="solid", bd=1,
                 bg=WHITE, fg=TEXT_DARK).pack(fill="x", ipady=6, pady=(2, 12))

        # Password
        tk.Label(card, text="رمز عبور", font=FONT_NORMAL,
                 bg=WHITE, fg=TEXT_DARK, anchor="e").pack(fill="x")
        self.password_var = tk.StringVar()
        tk.Entry(card, textvariable=self.password_var, font=FONT_NORMAL,
                 justify="right", show="●", relief="solid", bd=1,
                 bg=WHITE, fg=TEXT_DARK).pack(fill="x", ipady=6, pady=(2, 16))

        # Error label
        self.error_var = tk.StringVar()
        tk.Label(card, textvariable=self.error_var, font=FONT_SMALL,
                 bg=WHITE, fg=RED).pack()

        # Login button
        btn = tk.Button(card, text="ورود", font=FONT_NORMAL,
                        bg=NAVY, fg=WHITE, activebackground=NAVY_LIGHT,
                        activeforeground=WHITE, relief="flat",
                        cursor="hand2", command=self._do_login)
        btn.pack(fill="x", ipady=8, pady=(8, 0))

        self.bind("<Return>", lambda e: self._do_login())

    def _do_login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        if not username or not password:
            self.error_var.set("نام کاربری و رمز عبور را وارد کنید.")
            return
        success, message = AuthManager.login(username, password)
        if success:
            self.destroy()
            from views.main_view import MainView
            MainView().mainloop()
        else:
            self.error_var.set(message)