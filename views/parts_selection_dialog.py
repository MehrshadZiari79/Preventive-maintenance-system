# views/parts_selection_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
import json
from database.spare_parts_repository import SparePartsRepository
from database.db import SessionLocal
from database.work_order import WorkOrderStatus

from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_SMALL
)

BG = GRAY_BG
CARD_BG = WHITE
PRIMARY = NAVY
DANGER = RED
SUCCESS = SUCCESS
TEXT = TEXT_DARK
SUBTLE = TEXT_LIGHT
BORDER = GRAY_BORDER

class PartsSelectionDialog(tk.Toplevel):
    def __init__(self, parent, wo_repo, work_order_id):
        super().__init__(parent)
        self.wo_repo = wo_repo
        self.work_order_id = work_order_id
        self.result = False
        self.title("ارسال گزارش اتمام کار")
        self.geometry("850x800")
        self.transient(parent)
        self.grab_set()

        self.sp_repo = SparePartsRepository(SessionLocal)
        self.selected_parts = []
        self.work_order = self.wo_repo.get_by_id(work_order_id)
        self.all_parts = self.sp_repo.get_all()

        if self.work_order and self.work_order.parts_used:
            try:
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

        self._build_ui()
        self._refresh_tree()

    def _build_ui(self):
        header = tk.Frame(self, bg=PRIMARY, height=55)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📝  گزارش اتمام کار", font=FONT_HEADING,
                 bg=PRIMARY, fg=WHITE).pack(pady=12)

        # ── Scrollable area ────────────────────────────────────────────
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        vsb.pack(side="right", fill="y")

        main = ttk.Frame(scrollable_frame, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Parts selection card
        parts_card = tk.Frame(main, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        parts_card.pack(fill=tk.BOTH, expand=True, pady=5)
        tk.Label(parts_card, text="قطعات مصرفی", font=FONT_HEADING, bg=CARD_BG, fg=TEXT).pack(anchor="e", padx=10, pady=(10,5))

        tree_frame = tk.Frame(parts_card, bg=CARD_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        columns = ("part_number", "name", "stock", "quantity")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=6)
        self.tree.heading("part_number", text="شماره قطعه")
        self.tree.heading("name", text="نام قطعه")
        self.tree.heading("stock", text="موجودی")
        self.tree.heading("quantity", text="تعداد مصرفی")
        self.tree.column("part_number", width=120)
        self.tree.column("name", width=180)
        self.tree.column("stock", width=80)
        self.tree.column("quantity", width=80)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)

        btn_frame = tk.Frame(parts_card, bg=CARD_BG)
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="➕ افزودن قطعه", command=self._add_part,
                  bg=PRIMARY, fg=WHITE, font=FONT_NORMAL, relief="flat", cursor="hand2",
                  padx=10, pady=4).pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_frame, text="🗑️ حذف قطعه", command=self._remove_part,
                  bg=DANGER, fg=WHITE, font=FONT_NORMAL, relief="flat", cursor="hand2",
                  padx=10, pady=4).pack(side=tk.RIGHT, padx=5)

        # Cost frame
        cost_card = tk.Frame(main, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        cost_card.pack(fill=tk.X, pady=5)
        tk.Label(cost_card, text="هزینه دستی", font=FONT_HEADING, bg=CARD_BG, fg=TEXT).pack(anchor="e", padx=10, pady=(10,5))

        cost_inner = tk.Frame(cost_card, bg=CARD_BG)
        cost_inner.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(cost_inner, text="مبلغ (ریال):", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).grid(row=0, column=1, sticky=tk.E, padx=5, pady=5)
        self.manual_cost_var = tk.StringVar(value="0")
        tk.Entry(cost_inner, textvariable=self.manual_cost_var, width=20,
                 font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        tk.Label(cost_inner, text="توضیح هزینه:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).grid(row=1, column=1, sticky=tk.NE, padx=5, pady=5)
        self.cost_desc_text = tk.Text(cost_inner, width=50, height=3, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                      relief="solid", bd=1)
        self.cost_desc_text.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)

        if self.work_order and self.work_order.manual_cost:
            self.manual_cost_var.set(str(int(self.work_order.manual_cost)))
        if self.work_order and self.work_order.cost_description:
            self.cost_desc_text.insert("1.0", self.work_order.cost_description)

        # Delay card
        delay_card = tk.Frame(main, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        delay_card.pack(fill=tk.X, pady=5)
        tk.Label(delay_card, text="تأخیر در اتمام", font=FONT_HEADING, bg=CARD_BG, fg=TEXT).pack(anchor="e", padx=10, pady=(10,5))

        delay_inner = tk.Frame(delay_card, bg=CARD_BG)
        delay_inner.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(delay_inner, text="دقیقه تأخیر:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).grid(row=0, column=1, sticky=tk.E, padx=5, pady=5)
        self.delay_minutes_var = tk.StringVar(value="0")
        tk.Entry(delay_inner, textvariable=self.delay_minutes_var, width=10,
                 font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        tk.Label(delay_inner, text="علت تأخیر:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).grid(row=1, column=1, sticky=tk.NE, padx=5, pady=5)
        self.delay_reason_text = tk.Text(delay_inner, width=40, height=3, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                         relief="solid", bd=1)
        self.delay_reason_text.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)

        # Description frame
        desc_card = tk.Frame(main, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        desc_card.pack(fill=tk.X, pady=5)
        tk.Label(desc_card, text="توضیحات تکنسین (نهایی)", font=FONT_HEADING, bg=CARD_BG, fg=TEXT).pack(anchor="e", padx=10, pady=(10,5))
        self.desc_text = tk.Text(desc_card, height=4, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT,
                                 relief="solid", bd=1)
        self.desc_text.pack(fill=tk.X, padx=10, pady=(0,10))

        # Submit button (outside scrollable frame to always be visible)
        action_btn = tk.Button(self, text="ارسال گزارش اتمام", font=FONT_HEADING,
                               bg=SUCCESS, fg=WHITE, relief="flat", cursor="hand2",
                               padx=20, pady=10, command=self._submit)
        action_btn.pack(pady=10, side=tk.BOTTOM)

    def _add_part(self):
        dialog = tk.Toplevel(self)
        dialog.title("انتخاب قطعه")
        dialog.geometry("500x350")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=BG)

        header = tk.Frame(dialog, bg=PRIMARY, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="انتخاب قطعه", font=FONT_NORMAL, bg=PRIMARY, fg=WHITE).pack(pady=10)

        body = tk.Frame(dialog, bg=CARD_BG, padx=20, pady=15)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="قطعه:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).pack(pady=5)
        part_combo = ttk.Combobox(body, values=[f"{p.part_number} - {p.name}" for p in self.all_parts],
                                  width=40, state="readonly", font=FONT_NORMAL)
        part_combo.pack(pady=5)

        tk.Label(body, text="تعداد مصرفی:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).pack(pady=5)
        qty_entry = tk.Entry(body, width=10, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1)
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
            for p in self.all_parts:
                if f"{p.part_number} - {p.name}" == selection:
                    if p.current_stock < qty:
                        messagebox.showerror("خطا", f"موجودی کافی نیست. موجودی: {p.current_stock}")
                        return
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

        btn_frame = tk.Frame(body, bg=CARD_BG)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="تأیید", command=confirm,
                  bg=SUCCESS, fg=WHITE, font=FONT_NORMAL, relief="flat", padx=20, pady=6).pack(side="right", padx=5)
        tk.Button(btn_frame, text="انصراف", command=dialog.destroy,
                  bg=BORDER, fg=TEXT, font=FONT_NORMAL, relief="flat", padx=20, pady=6).pack(side="right")

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

    def _submit(self):
        try:
            manual_cost = float(self.manual_cost_var.get().strip())
        except:
            manual_cost = 0.0
        cost_description = self.cost_desc_text.get("1.0", tk.END).strip() or None
        technician_notes = self.desc_text.get("1.0", tk.END).strip() or None
        used_parts = [{"part_id": p['part_id'], "quantity": p['quantity']} for p in self.selected_parts]

        try:
            delay_minutes = int(self.delay_minutes_var.get().strip())
        except:
            delay_minutes = 0
        delay_reason = self.delay_reason_text.get("1.0", tk.END).strip() or None

        self.used_parts = used_parts
        self.manual_cost = manual_cost
        self.cost_description = cost_description
        self.technician_notes = technician_notes
        self.delay_minutes = delay_minutes
        self.delay_reason = delay_reason

        self.result = True
        self.destroy()