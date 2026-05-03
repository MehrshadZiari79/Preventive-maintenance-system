# views/category_manager_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox


class CategoryManagerDialog(tk.Toplevel):
    def __init__(self, parent, equipment_repo, callback=None):
        super().__init__(parent)
        self.equipment_repo = equipment_repo
        self.callback = callback
        self.title("مدیریت دسته‌بندی تجهیزات")
        self.geometry("400x400")
        self.configure(bg="#F0F4F8")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._load_categories()

    def _build_ui(self):
        main = tk.Frame(self, bg="#F0F4F8", padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="دسته‌بندی‌های موجود", font=("Tahoma", 12, "bold"),
                 bg="#F0F4F8", fg="#202124").pack(pady=(0, 10))

        # Listbox with scrollbar
        list_frame = tk.Frame(main)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.listbox = tk.Listbox(list_frame, font=("Tahoma", 10), bg="#FFFFFF",
                                  relief="solid", bd=1)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = tk.Frame(main, bg="#F0F4F8")
        btn_frame.pack(fill=tk.X, pady=(15, 0))

        tk.Button(btn_frame, text="حذف دسته‌بندی انتخاب شده", font=("Tahoma", 10),
                  bg="#DC3545", fg="white", relief="flat", cursor="hand2",
                  command=self._delete_category, padx=15, pady=5).pack(side=tk.RIGHT, padx=5)

        tk.Button(btn_frame, text="بستن", font=("Tahoma", 10),
                  bg="#6C757D", fg="white", relief="flat", cursor="hand2",
                  command=self.destroy, padx=15, pady=5).pack(side=tk.RIGHT, padx=5)

    def _load_categories(self):
        self.listbox.delete(0, tk.END)
        categories = self.equipment_repo.get_categories()
        for cat in categories:
            self.listbox.insert(tk.END, cat)

    def _delete_category(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("هشدار", "لطفاً یک دسته‌بندی را انتخاب کنید.", parent=self)
            return
        category = self.listbox.get(selection[0])
        # Check if category is used by any equipment
        used = self.equipment_repo.is_category_used(category)
        if used:
            messagebox.showerror("خطا", f"دسته‌بندی '{category}' در حال استفاده است و قابل حذف نیست.", parent=self)
            return
        confirm = messagebox.askyesno("تأیید حذف", f"آیا از حذف دسته‌بندی '{category}' اطمینان دارید؟", parent=self)
        if confirm:
            success, msg = self.equipment_repo.delete_category(category)
            if success:
                messagebox.showinfo("موفق", msg, parent=self)
                self._load_categories()
                if self.callback:
                    self.callback()
            else:
                messagebox.showerror("خطا", msg, parent=self)