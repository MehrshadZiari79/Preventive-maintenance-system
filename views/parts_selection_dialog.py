# views/parts_selection_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
from database.spare_parts_repository import SparePartsRepository
from database.db import SessionLocal

class PartsSelectionDialog(tk.Toplevel):
    def __init__(self, parent, wo_repo, work_order_id):
        super().__init__(parent)
        self.wo_repo = wo_repo
        self.work_order_id = work_order_id
        self.result = False
        self.title("انتخاب قطعات مصرفی")
        self.geometry("600x400")
        self.transient(parent)
        self.grab_set()

        self.sp_repo = SparePartsRepository(SessionLocal())
        self.selected_parts = []  # list of {"part_id": id, "part_number": str, "name": str, "quantity": int, "stock": int}
        # Load pre‑selected parts from work order (if any)
        self.work_order = self.wo_repo.get_by_id(work_order_id)
        if self.work_order and self.work_order.parts_used:
            try:
                import json
                parts_list = json.loads(self.work_order.parts_used)
                for part_info in parts_list:
                    part_id = part_info["part_id"]
                    qty = part_info["quantity"]
                    part = next((p for p in self.all_parts if p.id == part_id), None)
                    if part:
                        self.selected_parts.append({
                            "part_id": part.id,
                            "part_number": part.part_number,
                            "name": part.name,
                            "quantity": qty,
                            "stock": part.current_stock
                        })
            except:
                pass
        self.all_parts = self.sp_repo.get_all()

        self._build_ui()
        self._refresh_tree()

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Parts tree
        columns = ("part_number", "name", "stock", "quantity")
        self.tree = ttk.Treeview(main, columns=columns, show="headings", height=10)
        self.tree.heading("part_number", text="شماره قطعه")
        self.tree.heading("name", text="نام قطعه")
        self.tree.heading("stock", text="موجودی")
        self.tree.heading("quantity", text="تعداد مصرفی")
        self.tree.column("part_number", width=120)
        self.tree.column("name", width=180)
        self.tree.column("stock", width=80)
        self.tree.column("quantity", width=80)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="➕ افزودن قطعه", command=self._add_part).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="🗑️ حذف قطعه", command=self._remove_part).pack(side=tk.RIGHT, padx=5)

        desc_frame = ttk.LabelFrame(main, text="توضیحات تکنسین", padding=5)
        desc_frame.pack(fill=tk.X, pady=5)
        self.desc_text = tk.Text(desc_frame, height=4)
        self.desc_text.pack(fill=tk.X)

        action_btn = ttk.Button(main, text="✅ تکمیل کار و کسر قطعات", command=self._complete)
        action_btn.pack(pady=10)

    def _add_part(self):
        dialog = tk.Toplevel(self)
        dialog.title("انتخاب قطعه")
        dialog.geometry("400x250")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="قطعه:").pack(pady=5)
        part_combo = ttk.Combobox(dialog, values=[f"{p.part_number} - {p.name}" for p in self.all_parts], width=40, state="readonly")
        part_combo.pack(pady=5)

        ttk.Label(dialog, text="تعداد مصرفی:").pack(pady=5)
        qty_entry = ttk.Entry(dialog, width=10)
        qty_entry.pack(pady=5)

        def confirm():
            selection = part_combo.get()
            if not selection:
                return
            try:
                qty = int(qty_entry.get())
                if qty <= 0:
                    raise ValueError
            except:
                messagebox.showerror("خطا", "تعداد نامعتبر")
                return
            # Find part
            for p in self.all_parts:
                if f"{p.part_number} - {p.name}" == selection:
                    if p.current_stock < qty:
                        messagebox.showerror("خطا", f"موجودی کافی نیست. موجودی: {p.current_stock}")
                        return
                    # Check if already added
                    for item in self.selected_parts:
                        if item['part_id'] == p.id:
                            item['quantity'] += qty
                            self._refresh_tree()
                            dialog.destroy()
                            return
                    self.selected_parts.append({
                        "part_id": p.id,
                        "part_number": p.part_number,
                        "name": p.name,
                        "quantity": qty,
                        "stock": p.current_stock
                    })
                    self._refresh_tree()
                    dialog.destroy()
                    return
            messagebox.showerror("خطا", "قطعه یافت نشد")

        ttk.Button(dialog, text="تأیید", command=confirm).pack(pady=10)
        ttk.Button(dialog, text="انصراف", command=dialog.destroy).pack()

    def _remove_part(self):
        selected = self.tree.selection()
        if not selected:
            return
        for idx, item in enumerate(self.selected_parts):
            if str(idx) == selected[0]:
                del self.selected_parts[idx]
                self._refresh_tree()
                break

    def _refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, item in enumerate(self.selected_parts):
            self.tree.insert("", "end", iid=str(i), values=(
                item['part_number'], item['name'], item['stock'], item['quantity']
            ))

    def _complete(self):
        if not self.selected_parts:
            # Optional: allow completion without parts
            if not messagebox.askyesno("تأیید", "هیچ قطعه‌ای انتخاب نشده است. آیا بدون کسر قطعه ادامه می‌دهید؟"):
                return
        description = self.desc_text.get("1.0", tk.END).strip() or None
        used_parts_list = [{"part_id": p['part_id'], "quantity": p['quantity']} for p in self.selected_parts]
        ok, msg = self.wo_repo.complete_work(self.work_order_id, description, used_parts_list=used_parts_list)
        if ok:
            messagebox.showinfo("موفق", msg)
            self.result = True
            self.destroy()
        else:
            messagebox.showerror("خطا", msg)