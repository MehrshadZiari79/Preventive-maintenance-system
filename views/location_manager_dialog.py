# views/location_manager_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, FONT_HEADING, FONT_NORMAL
)

CARD_BG = WHITE
CARD_BORDER = GRAY_BORDER
SECTION_BG = GRAY_BG

class LocationManagerDialog(tk.Toplevel):
    def __init__(self, parent, equipment_repo, callback=None):
        super().__init__(parent)
        self.equipment_repo = equipment_repo
        self.callback = callback
        self.title("مدیریت موقعیت‌ها")
        self.geometry("450x500")
        self.configure(bg=SECTION_BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._load_locations()

    def _build_ui(self):
        header = tk.Frame(self, bg=NAVY, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📍 مدیریت موقعیت‌ها", font=FONT_HEADING,
                 bg=NAVY, fg=WHITE).pack(pady=12)

        # ── Scrollable area ──────────────────────────────────────
        canvas = tk.Canvas(self, bg=SECTION_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=SECTION_BG)

        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        vsb.pack(side="right", fill="y")

        main = tk.Frame(scrollable, bg=CARD_BG)
        main.pack(fill="both", expand=True, padx=15, pady=15)

        tk.Label(main, text="موقعیت‌های موجود", font=FONT_HEADING,
                 bg=CARD_BG, fg=TEXT_DARK).pack(pady=(10, 5))

        list_frame = tk.Frame(main, bg=CARD_BG)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.listbox = tk.Listbox(list_frame, font=FONT_NORMAL, bg=CARD_BG,
                                  relief="solid", bd=1, highlightbackground=CARD_BORDER)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        btn_frame = tk.Frame(main, bg=CARD_BG)
        btn_frame.pack(fill="x", padx=10, pady=10)
        tk.Button(btn_frame, text="✏️ ویرایش", font=FONT_NORMAL,
                  bg=NAVY, fg=WHITE, relief="flat", cursor="hand2",
                  command=self._edit_location, padx=12, pady=5).pack(side="right", padx=5)
        tk.Button(btn_frame, text="🗑️ حذف", font=FONT_NORMAL,
                  bg=RED, fg=WHITE, relief="flat", cursor="hand2",
                  command=self._delete_location, padx=12, pady=5).pack(side="right", padx=5)
        tk.Button(btn_frame, text="بستن", font=FONT_NORMAL,
                  bg=NAVY_LIGHT, fg=WHITE, relief="flat", cursor="hand2",
                  command=self.destroy, padx=12, pady=5).pack(side="right", padx=5)

    def _load_locations(self):
        self.listbox.delete(0, tk.END)
        locations = self.equipment_repo.get_locations()
        for loc in locations:
            self.listbox.insert(tk.END, loc)

    def _edit_location(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("هشدار", "لطفاً یک موقعیت را انتخاب کنید.", parent=self)
            return
        old_name = self.listbox.get(selection[0])
        new_name = simpledialog.askstring("ویرایش موقعیت",
                                          f"نام جدید برای '{old_name}':",
                                          initialvalue=old_name, parent=self)
        if new_name and new_name.strip():
            new_name = new_name.strip()
            if new_name == old_name:
                return
            success, msg = self.equipment_repo.rename_location(old_name, new_name)
            if success:
                messagebox.showinfo("موفق", msg, parent=self)
                self._load_locations()
                if self.callback:
                    self.callback()
            else:
                messagebox.showerror("خطا", msg, parent=self)

    def _delete_location(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("هشدار", "لطفاً یک موقعیت را انتخاب کنید.", parent=self)
            return
        loc = self.listbox.get(selection[0])
        used = self.equipment_repo.is_location_used(loc)
        if used:
            messagebox.showerror("خطا", f"موقعیت '{loc}' در حال استفاده است و قابل حذف نیست.", parent=self)
            return
        confirm = messagebox.askyesno("تأیید حذف", f"آیا از حذف موقعیت '{loc}' اطمینان دارید؟", parent=self)
        if confirm:
            success, msg = self.equipment_repo.delete_location(loc)
            if success:
                messagebox.showinfo("موفق", msg, parent=self)
                self._load_locations()
                if self.callback:
                    self.callback()
            else:
                messagebox.showerror("خطا", msg, parent=self)