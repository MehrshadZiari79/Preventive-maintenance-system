# views/parts_selection_dialog.py
import tkinter as tk
from views.ui_kit import rtl_columns  # RTL (right-to-left) table columns
from tkinter import ttk, messagebox
from views.ux import field_error
import json
from database.spare_parts_repository import SparePartsRepository
from database.db import SessionLocal

from utils.theme import (
    NAVY, WHITE, RED, GRAY_BG, GRAY_BORDER, TEXT_DARK,
    TEXT_LIGHT, SUCCESS, FONT_HEADING, FONT_NORMAL,
    FONT_SMALL
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
        self.personnel_id = None
        self.personnel_ids = []
        self.personnel_display_map = {}
        self.title("ارسال گزارش اتمام کار")
        self.geometry("850x800")
        try:
            from views.ui_kit import center_window
            center_window(self, 850, 800, parent)
        except Exception:
            pass
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
        tk.Label(
            header,
            text="📝  گزارش اتمام کار",
            font=FONT_HEADING,
            bg=PRIMARY,
            fg=WHITE,
        ).pack(pady=12)

        # footer first, so the submit button is always visible
        footer = tk.Frame(self, bg=BG)
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        self._footer = footer

        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        # content follows the dialog width (no clipped right side)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        def _wheel(event):
            if isinstance(event.widget, (tk.Text, tk.Listbox, ttk.Treeview)):
                return None
            delta = -1 if (getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4) else 1
            canvas.yview_scroll(delta * 3, "units")
            return None

        self.bind("<MouseWheel>", _wheel, add="+")
        self.bind("<Button-4>", _wheel, add="+")
        self.bind("<Button-5>", _wheel, add="+")

        main = tk.Frame(scrollable_frame, bg=BG, padx=10, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        # =====================================================================
        # PERSONNEL FIRST - ONLY VISIBLE PERSONNEL SELECTOR
        # =====================================================================
        personnel_card = tk.Frame(
            main,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        personnel_card.pack(fill=tk.X, pady=5)

        tk.Label(
            personnel_card,
            text="پرسنل انجام‌دهنده *",
            font=FONT_HEADING,
            bg=CARD_BG,
            fg=TEXT,
        ).pack(anchor="e", padx=10, pady=(10, 5))

        tk.Label(
            personnel_card,
            text="یک یا چند نفر از پرسنل دپارتمان مسئول این دستورکار را انتخاب کنید.",
            font=FONT_SMALL,
            bg=CARD_BG,
            fg=SUBTLE,
        ).pack(anchor="e", padx=10, pady=(0, 8))

        list_frame = tk.Frame(personnel_card, bg=CARD_BG)
        list_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.personnel_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            exportselection=False,
            height=7,
            font=FONT_NORMAL,
            bg=WHITE,
            fg=TEXT,
            relief="solid",
            bd=1,
            activestyle="none",
        )
        personnel_scroll = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.personnel_listbox.yview,
        )
        self.personnel_listbox.configure(yscrollcommand=personnel_scroll.set)
        self.personnel_listbox.pack(side="left", fill="both", expand=True)
        personnel_scroll.pack(side="right", fill="y")

        self.personnel_display_map = {}
        self._load_personnel()

        # =====================================================================
        # PARTS UI - INTENTIONALLY HIDDEN, LOGIC REMAINS IN THE CLASS
        # =====================================================================
        # Do not delete the selected_parts data or _add_part/_remove_part logic.
        # The business logic remains available for compatibility/history, but
        # the user-facing Parts section is hidden as requested.
        # =====================================================================
        self.parts_card = tk.Frame(
            main,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        # Build the hidden parts controls without packing the card.
        tk.Label(
            self.parts_card,
            text="قطعات مصرفی",
            font=FONT_HEADING,
            bg=CARD_BG,
            fg=TEXT,
        ).pack(anchor="e", padx=10, pady=(10, 5))

        hidden_tree_frame = tk.Frame(self.parts_card, bg=CARD_BG)
        hidden_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("part_number", "name", "stock", "quantity")
        self.tree = ttk.Treeview(
            hidden_tree_frame,
            columns=columns,
            show="headings",
            height=6,
        )
        rtl_columns(self.tree)  # RTL column order
        for col, heading, width, anchor in [
            ("part_number", "شماره قطعه", 120, "center"),
            ("name", "نام قطعه", 180, "w"),
            ("stock", "موجودی", 80, "e"),
            ("quantity", "تعداد مصرفی", 80, "e"),
        ]:
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor=anchor)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)

        hidden_btn_frame = tk.Frame(self.parts_card, bg=CARD_BG)
        hidden_btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(hidden_btn_frame, text="➕ افزودن قطعه", command=self._add_part).pack(side=tk.RIGHT)
        tk.Button(hidden_btn_frame, text="🗑️ حذف قطعه", command=self._remove_part).pack(side=tk.RIGHT)

        # =====================================================================
        # COST
        # =====================================================================
        cost_card = tk.Frame(main, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        cost_card.pack(fill=tk.X, pady=5)
        tk.Label(cost_card, text="هزینه دستی", font=FONT_HEADING, bg=CARD_BG, fg=TEXT).pack(anchor="e", padx=10, pady=(10,5))
        cost_inner = tk.Frame(cost_card, bg=CARD_BG)
        cost_inner.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(cost_inner, text="مبلغ (ریال):", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).grid(row=0, column=1, sticky=tk.E, padx=5, pady=5)
        self.manual_cost_var = tk.StringVar(value="0")
        tk.Entry(cost_inner, textvariable=self.manual_cost_var, width=20, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        tk.Label(cost_inner, text="توضیح هزینه:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).grid(row=1, column=1, sticky=tk.NE, padx=5, pady=5)
        self.cost_desc_text = tk.Text(cost_inner, width=50, height=3, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1)
        self.cost_desc_text.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        if self.work_order and self.work_order.manual_cost:
            self.manual_cost_var.set(str(int(self.work_order.manual_cost)))
        if self.work_order and self.work_order.cost_description:
            self.cost_desc_text.insert("1.0", self.work_order.cost_description)

        # =====================================================================
        # DELAY
        # =====================================================================
        delay_card = tk.Frame(main, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        delay_card.pack(fill=tk.X, pady=5)
        tk.Label(delay_card, text="تأخیر در اتمام", font=FONT_HEADING, bg=CARD_BG, fg=TEXT).pack(anchor="e", padx=10, pady=(10,5))
        delay_inner = tk.Frame(delay_card, bg=CARD_BG)
        delay_inner.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(delay_inner, text="دقیقه تأخیر:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).grid(row=0, column=1, sticky=tk.E, padx=5, pady=5)
        self.delay_minutes_var = tk.StringVar(value="0")
        tk.Entry(delay_inner, textvariable=self.delay_minutes_var, width=10, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        tk.Label(delay_inner, text="علت تأخیر:", font=FONT_NORMAL, bg=CARD_BG, fg=TEXT).grid(row=1, column=1, sticky=tk.NE, padx=5, pady=5)
        self.delay_reason_text = tk.Text(delay_inner, width=40, height=3, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1)
        self.delay_reason_text.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)

        # =====================================================================
        # TECHNICIAN NOTES
        # =====================================================================
        desc_card = tk.Frame(main, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        desc_card.pack(fill=tk.X, pady=5)
        tk.Label(desc_card, text="توضیحات نهایی تعمیر", font=FONT_HEADING, bg=CARD_BG, fg=TEXT).pack(anchor="e", padx=10, pady=(10,5))
        self.desc_text = tk.Text(desc_card, height=4, font=FONT_NORMAL, bg=CARD_BG, fg=TEXT, relief="solid", bd=1)
        self.desc_text.pack(fill=tk.X, padx=10, pady=(0,10))

        action_btn = tk.Button(
            self._footer,
            text="ارسال گزارش اتمام",
            font=FONT_HEADING,
            bg=SUCCESS,
            fg=WHITE,
            relief="flat",
            cursor="hand2",
            padx=20,
            pady=10,
            command=self._submit,
        )
        action_btn.pack(pady=10, side=tk.BOTTOM)

    def _load_personnel(self):
        """Load only Personnel belonging to this Work Order department."""
        try:
            people = self.wo_repo.get_personnel_for_finish(self.work_order_id) or []
        except Exception as exc:
            messagebox.showerror(
                "خطا",
                f"بارگذاری پرسنل انجام‌دهنده انجام نشد:\n\n{exc}",
                parent=self,
            )
            return

        values = []
        existing_ids = set()

        try:
            current_people = list(getattr(self.work_order, "completers", []) or [])
            existing_ids = {getattr(person, "id", None) for person in current_people}
            existing_ids.discard(None)
        except Exception:
            pass

        for person in people:
            if isinstance(person, dict):
                pid = person.get("id")
                name = str(person.get("full_name") or "").strip()
                code = str(person.get("personnel_code") or "").strip()
            else:
                pid = getattr(person, "id", None)
                name = str(getattr(person, "full_name", "") or "").strip()
                code = str(getattr(person, "personnel_code", "") or "").strip()

            if pid is None or not name:
                continue

            display = f"{code} - {name}" if code else name
            self.personnel_display_map[display] = int(pid)
            values.append(display)

        self.personnel_listbox.delete(0, tk.END)
        for display in values:
            self.personnel_listbox.insert(tk.END, display)

        for index, display in enumerate(values):
            if self.personnel_display_map.get(display) in existing_ids:
                self.personnel_listbox.selection_set(index)

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
        selected_indices = self.personnel_listbox.curselection()
        selected_personnel_ids = []

        for index in selected_indices:
            display = self.personnel_listbox.get(index)
            pid = self.personnel_display_map.get(display)
            if pid is not None:
                selected_personnel_ids.append(int(pid))

        # De-duplicate while preserving selection order.
        normalized_personnel_ids = []
        seen = set()
        for pid in selected_personnel_ids:
            if pid not in seen:
                seen.add(pid)
                normalized_personnel_ids.append(pid)

        if not normalized_personnel_ids:
            field_error(self.personnel_listbox, "لطفاً حداقل یک پرسنل انجام‌دهنده را از فهرست دپارتمان مسئول انتخاب کنید.")
            return

        try:
            manual_cost = float(self.manual_cost_var.get().strip())
        except (TypeError, ValueError):
            manual_cost = 0.0

        cost_description = self.cost_desc_text.get("1.0", tk.END).strip() or None
        technician_notes = self.desc_text.get("1.0", tk.END).strip() or None

        # Parts logic remains intact even though its UI is hidden.
        used_parts = [
            {
                "part_id": p["part_id"],
                "quantity": p["quantity"],
            }
            for p in self.selected_parts
        ]

        try:
            delay_minutes = int(self.delay_minutes_var.get().strip())
        except (TypeError, ValueError):
            delay_minutes = 0

        delay_reason = self.delay_reason_text.get("1.0", tk.END).strip() or None

        # New multi-personnel result. The first ID is also exposed through
        # personnel_id for old callers that still expect a single value.
        self.personnel_ids = normalized_personnel_ids
        self.personnel_id = normalized_personnel_ids[0]
        self.used_parts = used_parts
        self.manual_cost = manual_cost
        self.cost_description = cost_description
        self.technician_notes = technician_notes
        self.delay_minutes = delay_minutes
        self.delay_reason = delay_reason

        self.result = True
        self.destroy()

