import tkinter as tk
from tkinter import messagebox
from auth.auth_manager import AuthManager

BG = "#F0F4F8"
WHITE = "#FFFFFF"
BLUE = "#1A73E8"
BLUE_DARK = "#1557B0"
TEXT = "#202124"
SUBTLE = "#5F6368"
BORDER = "#DADCE0"
ERROR = "#D93025"

FONT_TITLE = ("Tahoma", 16, "bold")
FONT_LABEL = ("Tahoma", 11)
FONT_BTN = ("Tahoma", 11, "bold")
FONT_SMALL = ("Tahoma", 9)


class LoginView(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ورود به سیستم")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._center_window(400, 480)
        self._build_ui()

    def _center_window(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        card = tk.Frame(self, bg=WHITE, padx=40, pady=40,
                        highlightbackground=BORDER, highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor="center", width=360, height=420)

        tk.Label(card, text="🔧", font=("Tahoma", 32),
                 bg=WHITE).pack(pady=(0, 5))
        tk.Label(card, text="سیستم نگهداری پیشگیرانه",
                 font=FONT_TITLE, bg=WHITE, fg=TEXT).pack()
        tk.Label(card, text="لطفاً وارد شوید",
                 font=FONT_SMALL, bg=WHITE, fg=SUBTLE).pack(pady=(4, 20))

        tk.Label(card, text="نام کاربری", font=FONT_LABEL,
                 bg=WHITE, fg=TEXT, anchor="e").pack(fill="x")
        self.username_var = tk.StringVar()
        tk.Entry(card, textvariable=self.username_var,
                 font=FONT_LABEL, justify="right",
                 relief="solid", bd=1).pack(fill="x", ipady=6, pady=(2, 12))

        tk.Label(card, text="رمز عبور", font=FONT_LABEL,
                 bg=WHITE, fg=TEXT, anchor="e").pack(fill="x")
        self.password_var = tk.StringVar()
        tk.Entry(card, textvariable=self.password_var,
                 font=FONT_LABEL, justify="right",
                 show="●", relief="solid", bd=1).pack(fill="x", ipady=6, pady=(2, 16))

        self.error_var = tk.StringVar()
        tk.Label(card, textvariable=self.error_var,
                 font=FONT_SMALL, bg=WHITE, fg=ERROR).pack()

        btn = tk.Button(card, text="ورود", font=FONT_BTN,
                        bg=BLUE, fg=WHITE, activebackground=BLUE_DARK,
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
            app = MainView()
            app.mainloop()
        else:
            self.error_var.set(message)
