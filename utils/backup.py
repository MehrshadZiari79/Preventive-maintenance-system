# utils/backup.py
import shutil
import os
from datetime import datetime
from tkinter import filedialog, messagebox
import tkinter as tk


def backup_database(parent=None):
    """Save a copy of the database to user-selected location."""
    source_db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pm_database.db")
    if not os.path.exists(source_db):
        messagebox.showerror("خطا", "فایل دیتابیس یافت نشد!", parent=parent)
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_filename = f"pm_backup_{timestamp}.db"
    dest_file = filedialog.asksaveasfilename(
        defaultextension=".db",
        filetypes=[("Database files", "*.db"), ("All files", "*.*")],
        initialfile=default_filename,
        title="ذخیره نسخه پشتیبان"
    )
    if not dest_file:
        return False
    try:
        shutil.copy2(source_db, dest_file)
        messagebox.showinfo("موفق", f"نسخه پشتیبان با موفقیت ذخیره شد.\n{os.path.basename(dest_file)}", parent=parent)
        return True
    except Exception as e:
        messagebox.showerror("خطا", f"خطا در ذخیره پشتیبان: {str(e)}", parent=parent)
        return False


def restore_database(parent=None):
    """Restore database from a backup file."""
    source_file = filedialog.askopenfilename(
        title="انتخاب فایل پشتیبان",
        filetypes=[("Database files", "*.db"), ("All files", "*.*")]
    )
    if not source_file:
        return False

    target_db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pm_database.db")
    # Confirm before overwriting
    confirm = messagebox.askyesno(
        "بازگردانی",
        "⚠️ با بازگردانی دیتابیس، تمام اطلاعات فعلی جایگزین خواهد شد.\n"
        "آیا از این کار اطمینان دارید؟",
        parent=parent
    )
    if not confirm:
        return False
    try:
        # Stop any background services? For simplicity, we just copy.
        # It's recommended to close all connections first – user should restart app after restore.
        shutil.copy2(source_file, target_db)
        messagebox.showinfo("موفق", "دیتابیس با موفقیت بازگردانی شد.\nلطفاً برنامه را مجدداً راه‌اندازی کنید.",
                            parent=parent)
        return True
    except Exception as e:
        messagebox.showerror("خطا", f"خطا در بازگردانی: {str(e)}", parent=parent)
        return False