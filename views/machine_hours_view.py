# views/machine_hours_view.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
from tkcalendar import DateEntry

from database.production_log_repository import ProductionLogRepository
from database.equipment_repository import EquipmentRepository
from database.db import SessionLocal
from auth.auth_manager import AuthManager
from views.searchable_combobox import SearchableCombobox
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

CARD_BG = WHITE
CARD_BORDER = GRAY_BORDER
SECTION_BG = GRAY_BG


class MachineHoursView(ttk.Frame):
    def __init__(self, parent, current_user):
        super().__init__(parent)
        self.current_user = current_user
        self.log_repo = ProductionLogRepository(SessionLocal)
        self.eq_repo = EquipmentRepository(SessionLocal)
        self.can_write = AuthManager.can_access("machine_hours", "write")
        self.can_delete = AuthManager.can_access("machine_hours", "delete")

        self._build_ui()
        self._load_equipment()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=NAVY, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⏱️  ساعات کار دستگاه", font=FONT_TITLE,
                 bg=NAVY, fg=WHITE).pack(side="right", padx=20, pady=14)

        if self.can_write:
            tk.Button(hdr, text="➕ ثبت جدید", font=FONT_NORMAL,
                      bg=WHITE, fg=NAVY, relief="flat", cursor="hand2",
                      padx=14, pady=6, command=self._add_log).pack(side="left", padx=16, pady=10)

        # Filter bar
        filter_card = tk.Frame(self, bg=CARD_BORDER)
        filter_card.pack(fill="x", padx=20, pady=(10, 5))
        filter_frame = tk.Frame(filter_card, bg=CARD_BG)
        filter_frame.pack(fill="x", padx=1, pady=1)

        tk.Label(filter_frame, text="تجهیز:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).pack(side="right", padx=(15,5))
        self.equipment_var = tk.StringVar()
        self.equipment_combo = SearchableCombobox(filter_frame, font=FONT_NORMAL, state="normal", width=30)
        self.equipment_combo.pack(side="right", padx=5)
        self.equipment_combo.bind("<<ComboboxSelected>>", lambda e: self._load_logs())

        tk.Label(filter_frame, text="از تاریخ:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).pack(side="right", padx=(15,5))
        self.start_date = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd',
                                    font=FONT_SMALL, background=NAVY, foreground=WHITE,
                                    headersbackground=NAVY, headersforeground=WHITE)
        self.start_date.set_date(date.today().replace(day=1))
        self.start_date.pack(side="right", padx=5)

        tk.Label(filter_frame, text="تا تاریخ:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).pack(side="right", padx=5)
        self.end_date = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd',
                                  font=FONT_SMALL, background=NAVY, foreground=WHITE,
                                  headersbackground=NAVY, headersforeground=WHITE)
        self.end_date.set_date(date.today())
        self.end_date.pack(side="right", padx=5)

        tk.Button(filter_frame, text="اعمال فیلتر", font=FONT_NORMAL,
                  bg=NAVY, fg=WHITE, relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._load_logs).pack(side="right", padx=10)

        tk.Button(filter_frame, text="🔄 بروزرسانی", font=FONT_NORMAL,
                  bg=NAVY_LIGHT, fg=WHITE, relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._force_reload).pack(side="left", padx=10)

        # Table
        table_card = tk.Frame(self, bg=CARD_BORDER)
        table_card.pack(fill="both", expand=True, padx=20, pady=(5, 10))
        tree_frame = tk.Frame(table_card, bg=CARD_BG)
        tree_frame.pack(fill="both", expand=True, padx=1, pady=1)

        columns = ("id", "date", "planned", "operating", "output")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        self.tree.heading("id", text="شناسه")
        self.tree.heading("date", text="تاریخ")
        self.tree.heading("planned", text="ساعات برنامه‌ریزی")
        self.tree.heading("operating", text="ساعات کارکرد")
        self.tree.heading("output", text="میزان تولید (واحد)")
        self.tree.column("id", width=60, anchor="center")
        self.tree.column("date", width=120, anchor="center")
        self.tree.column("planned", width=150, anchor="center")
        self.tree.column("operating", width=150, anchor="center")
        self.tree.column("output", width=150, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Keyboard shortcuts
        self.tree.configure(selectmode='extended')
        self.tree.bind("<Delete>", lambda e: self._delete_selected())
        self.tree.bind("<F2>",      lambda e: self._edit_log())
        self.tree.bind("<Control-n>", lambda e: self._add_log())

        style = ttk.Style()
        style.configure("Treeview", background=CARD_BG, fieldbackground=CARD_BG,
                        foreground=TEXT_DARK, rowheight=26, font=FONT_NORMAL)
        style.configure("Treeview.Heading", background=NAVY, foreground=WHITE,
                        font=("Tahoma", 9, "bold"))
        style.map("Treeview", background=[("selected", NAVY)], foreground=[("selected", WHITE)])

        self.tree.bind("<Double-1>", lambda e: self._edit_log() if self.can_write else None)
        self._build_context_menu()

    def _build_context_menu(self):
        self.ctx_menu = tk.Menu(self, tearoff=0, font=FONT_NORMAL)
        if self.can_write:
            self.ctx_menu.add_command(label="✏️ ویرایش", command=self._edit_log)
        if self.can_delete:
            self.ctx_menu.add_command(label="🗑️ حذف", command=self._delete_log)
        self.tree.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.ctx_menu.post(event.x_root, event.y_root)

    def _delete_selected(self):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف رکوردها نیستید.")
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("انتخاب", "لطفاً حداقل یک رکورد انتخاب کنید.")
            return
        if not messagebox.askyesno("حذف", f"آیا از حذف {len(selected)} رکورد اطمینان دارید؟"):
            return
        for log_id in selected:
            self.log_repo.delete_log(int(log_id))
        self._load_logs()

    def _load_equipment(self):
        equipments = self.eq_repo.get_all_equipment()
        eq_names = [f"{eq['code']} - {eq['name']}" for eq in equipments]
        self.equipment_map = {name: eq['id'] for name, eq in zip(eq_names, equipments)}
        self.equipment_combo.set_completion_list(eq_names)
        if eq_names:
            self.equipment_combo.current(0)
            self._load_logs()

    def _force_reload(self):
        self._load_equipment()

    def _load_logs(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        eq_name = self.equipment_var.get()
        if not eq_name:
            eq_name = self.equipment_combo.get()   # fallback to combobox text
        if not eq_name:
            return
        equipment_id = self.equipment_map.get(eq_name)
        if not equipment_id:
            return

        start = self.start_date.get_date()
        end = self.end_date.get_date()
        logs = self.log_repo.get_logs(equipment_id=equipment_id,
                                      start_date=start, end_date=end)

        for log in logs:
            self.tree.insert("", "end", iid=str(log.id), values=(
                log.id,
                log.log_date.strftime("%Y-%m-%d"),
                log.planned_hours,
                log.operating_hours,
                log.output_units
            ))

    def _selected_log_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("انتخاب", "لطفاً یک رکورد انتخاب کنید.")
            return None
        return int(sel[0])

    def _add_log(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ثبت رکورد جدید نیستید.")
            return
        eq_name = self.equipment_var.get() or self.equipment_combo.get()
        if not eq_name:
            messagebox.showwarning("هشدار", "ابتدا یک تجهیز انتخاب کنید.")
            return
        equipment_id = self.equipment_map.get(eq_name)
        LogDialog(self, self.log_repo, equipment_id, callback=self._load_logs)

    def _edit_log(self):
        if not self.can_write:
            messagebox.showwarning("دسترسی", "شما مجاز به ویرایش رکورد نیستید.")
            return
        log_id = self._selected_log_id()
        if not log_id:
            return
        log = self.log_repo.get_log(log_id)
        if not log:
            messagebox.showerror("خطا", "رکورد یافت نشد.")
            return
        LogDialog(self, self.log_repo, log.equipment_id, log=log, callback=self._load_logs)

    def _delete_log(self):
        if not self.can_delete:
            messagebox.showwarning("دسترسی", "شما مجاز به حذف رکورد نیستید.")
            return
        log_id = self._selected_log_id()
        if not log_id:
            return
        if messagebox.askyesno("حذف", "آیا این رکورد حذف شود؟"):
            ok, msg = self.log_repo.delete_log(log_id)
            if ok:
                messagebox.showinfo("موفق", msg)
                self._load_logs()
            else:
                messagebox.showerror("خطا", msg)


class LogDialog(tk.Toplevel):
    def __init__(self, parent, log_repo, equipment_id, log=None, callback=None):
        super().__init__(parent)
        self.log_repo = log_repo
        self.equipment_id = equipment_id
        self.log = log
        self.callback = callback

        self.title("ویرایش رکورد" if log else "ثبت ساعات کار")
        self.geometry("400x400")
        self.configure(bg=SECTION_BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._center()

        self._build_ui()
        if log:
            self._load_data()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 400) // 2
        y = (self.winfo_screenheight() - 400) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        header = tk.Frame(self, bg=NAVY, height=45)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="⏱️  ساعات کار", font=FONT_HEADING,
                 bg=NAVY, fg=WHITE).pack(pady=10)

        # ── Scrollable area ──────────────────────────────────
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

        body = tk.Frame(scrollable, bg=CARD_BG, padx=20, pady=15)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="تاریخ:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).pack(anchor="e", pady=(5,2))
        self.date_entry = DateEntry(body, width=20, date_pattern='yyyy-mm-dd',
                                    font=FONT_NORMAL, background=NAVY, foreground=WHITE,
                                    headersbackground=NAVY, headersforeground=WHITE)
        self.date_entry.pack(fill="x", pady=(0,10))

        tk.Label(body, text="ساعات برنامه‌ریزی:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).pack(anchor="e", pady=(5,2))
        self.planned_var = tk.StringVar(value="8")
        tk.Entry(body, textvariable=self.planned_var, font=FONT_NORMAL,
                 bg=CARD_BG, fg=TEXT_DARK, relief="solid", bd=1).pack(fill="x", ipady=3)

        tk.Label(body, text="ساعات کارکرد:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).pack(anchor="e", pady=(5,2))
        self.operating_var = tk.StringVar(value="8")
        tk.Entry(body, textvariable=self.operating_var, font=FONT_NORMAL,
                 bg=CARD_BG, fg=TEXT_DARK, relief="solid", bd=1).pack(fill="x", ipady=3)

        tk.Label(body, text="میزان تولید (واحد):", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT_DARK).pack(anchor="e", pady=(5,2))
        self.output_var = tk.StringVar(value="0")
        tk.Entry(body, textvariable=self.output_var, font=FONT_NORMAL,
                 bg=CARD_BG, fg=TEXT_DARK, relief="solid", bd=1).pack(fill="x", ipady=3)

        # ── Buttons (outside scrollable) ──────────────────────
        btn_frame = tk.Frame(self, bg=CARD_BG)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="ذخیره", font=FONT_NORMAL,
                  bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                  padx=20, pady=6, command=self._save).pack(side="right", padx=5)
        tk.Button(btn_frame, text="انصراف", font=FONT_NORMAL,
                  bg=NAVY_LIGHT, fg=WHITE, relief="flat", cursor="hand2",
                  padx=20, pady=6, command=self.destroy).pack(side="right", padx=5)

    def _load_data(self):
        self.date_entry.set_date(self.log.log_date)
        self.planned_var.set(str(self.log.planned_hours))
        self.operating_var.set(str(self.log.operating_hours))
        self.output_var.set(str(self.log.output_units))

    def _save(self):
        log_date = self.date_entry.get_date()
        try:
            planned = float(self.planned_var.get())
            operating = float(self.operating_var.get())
            output = float(self.output_var.get())
            if planned < 0 or operating < 0 or output < 0:
                raise ValueError("مقادیر نمی‌توانند منفی باشند.")
        except ValueError as e:
            messagebox.showerror("خطا", f"مقادیر نامعتبر: {str(e)}")
            return

        if self.log:
            ok, msg = self.log_repo.update_log(self.log.id, planned, operating, output)
        else:
            ok, msg = self.log_repo.add_log(self.equipment_id, log_date, planned, operating, output)

        if ok:
            messagebox.showinfo("موفق", msg)
            if self.callback:
                self.callback()
            self.destroy()
        else:
            messagebox.showerror("خطا", msg)