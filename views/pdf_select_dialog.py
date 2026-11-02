# views/pdf_select_dialog.py
"""
PDF selection dialogs (PDF only - the Excel dialogs in export_dialog.py
are untouched).

Shows a searchable checklist of records, lets the user tick the ones that
should be printed, then asks where to save the PDF and calls the matching
export function from services.pdf_service with ONLY the ticked records.

Currently provides:
    run_pm_pdf_export(parent, pm_records, selected_pm=None)
The generic PdfSelectDialog can be reused for other forms.
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from services.pdf_service import export_pm_pdf, _pm_fields

from utils.theme import (
    NAVY,
    NAVY_LIGHT,
    WHITE,
    GRAY_BG,
    GRAY_BORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    FONT_HEADING,
    FONT_NORMAL,
    FONT_SMALL,
)
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock

BG = GRAY_BG
PRIMARY = NAVY
PRIMARY_LIGHT = NAVY_LIGHT
TEXT = TEXT_DARK
BORDER = GRAY_BORDER

CHECKED = "☑"
UNCHECKED = "☐"


class PdfSelectDialog(tk.Toplevel):
    """Generic 'choose records to print' dialog.

    columns   : list of (key, heading, width) in RIGHT-TO-LEFT order
                (first entry is shown at the right edge).
    row_fn    : item -> dict of key -> display text.
    export_fn : (items, path) -> path.
    """

    def __init__(self, parent, title, items, row_fn, columns, export_fn,
                 file_prefix="export", preselected=None,
                 width=940, height=680):
        super().__init__(parent)
        self.parent = parent
        self.items = list(items or [])
        self.row_fn = row_fn
        self.columns = columns
        self.export_fn = export_fn
        self.file_prefix = file_prefix

        self.rows = [self.row_fn(item) for item in self.items]
        if preselected:
            self.checked = {
                i for i, item in enumerate(self.items)
                if any(item is p or item == p for p in preselected)
            }
        else:
            self.checked = set(range(len(self.items)))

        self.search_var = tk.StringVar()
        self.count_var = tk.StringVar()

        self.title(title)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        sw, sh = self.winfo_vrootwidth(), self.winfo_vrootheight()
        w = min(width, int(sw * 0.92))
        h = min(height, int(sh * 0.88))
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2)}")
        self.minsize(min(640, w), min(460, h))

        self._build(title)
        self._refresh()
        self.search_var.trace_add("write", lambda *_: self._refresh())
        self.bind("<Escape>", lambda _e: self.destroy())

    # ------------------------------------------------------------------ UI
    def _build(self, title):
        header = tk.Frame(self, bg=PRIMARY, height=68)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Label(header, text=title, font=FONT_HEADING, bg=PRIMARY, fg=WHITE,
                 anchor="e").pack(side="right", padx=22, pady=(12, 0))
        tk.Label(header, text="مواردی را که می‌خواهید چاپ شوند انتخاب کنید",
                 font=FONT_SMALL, bg=PRIMARY, fg=WHITE, anchor="e"
                 ).pack(side="right", padx=8, pady=(20, 0))

        footer = tk.Frame(self, bg=WHITE, height=70,
                          highlightbackground=BORDER, highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Button(footer, text="انصراف", command=self.destroy, bg=BG, fg=TEXT,
                  font=FONT_NORMAL, relief="flat", bd=0, cursor="hand2",
                  padx=22, pady=9, activebackground=BORDER
                  ).pack(side="left", padx=(15, 8), pady=12)
        tk.Button(footer, text="🖨  ساخت PDF", command=self._export,
                  bg=PRIMARY, fg=WHITE, font=FONT_NORMAL, relief="flat", bd=0,
                  cursor="hand2", padx=25, pady=9,
                  activebackground=PRIMARY_LIGHT, activeforeground=WHITE
                  ).pack(side="right", padx=(8, 15), pady=12)
        tk.Label(footer, textvariable=self.count_var, font=FONT_SMALL,
                 bg=WHITE, fg=TEXT_LIGHT, anchor="e"
                 ).pack(side="right", padx=10)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=12)

        # toolbar: search + select all / clear all
        bar = tk.Frame(body, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        tk.Label(bar, text="جستجو:", font=FONT_SMALL, bg=BG, fg=TEXT
                 ).pack(side="right", padx=(0, 6))
        entry = tk.Entry(bar, textvariable=self.search_var, font=FONT_NORMAL,
                         justify="right", relief="solid", bd=1)
        entry.pack(side="right", fill="x", expand=True, padx=(0, 10), ipady=3)
        tk.Button(bar, text="□ لغو همه", command=self._clear_all, bg=BG,
                  fg=TEXT, font=FONT_SMALL, relief="flat", bd=0, cursor="hand2",
                  padx=12, pady=5, activebackground=BORDER
                  ).pack(side="left", padx=3)
        tk.Button(bar, text="✓ انتخاب همه", command=self._select_all,
                  bg=PRIMARY, fg=WHITE, font=FONT_SMALL, relief="flat", bd=0,
                  cursor="hand2", padx=12, pady=5,
                  activebackground=PRIMARY_LIGHT, activeforeground=WHITE
                  ).pack(side="left", padx=3)

        # list
        box = tk.Frame(body, bg=BORDER)
        box.pack(fill="both", expand=True)
        keys = ["_check"] + [c[0] for c in self.columns]
        self.tree = ttk.Treeview(box, columns=keys, show="headings",
                                 selectmode="browse")
        self.tree.heading("_check", text="چاپ")
        self.tree.column("_check", width=60, anchor="center", stretch=False)
        for key, heading, col_w in self.columns:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=col_w, anchor="e")
        # Right-to-left: Treeview draws displaycolumns left->right, so reverse
        # them to put the check box and the first column at the RIGHT edge.
        # (v2.3 passed them unreversed: check box ended up on the left.)
        self.tree["displaycolumns"] = tuple(reversed(keys))
        sb = tk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="left", fill="y")
        self.tree.pack(side="right", fill="both", expand=True, padx=1, pady=1)

        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<space>", self._on_space)
        self.tree.bind("<Return>", self._on_space)

    # ---------------------------------------------------------------- data
    def _visible_indexes(self):
        q = self.search_var.get().strip().lower()
        if not q:
            return list(range(len(self.rows)))
        return [
            i for i, row in enumerate(self.rows)
            if q in " ".join(str(v) for v in row.values()).lower()
        ]

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i in self._visible_indexes():
            row = self.rows[i]
            values = [CHECKED if i in self.checked else UNCHECKED]
            values += [row.get(c[0], "") for c in self.columns]
            self.tree.insert("", "end", iid=str(i), values=values)
        self._update_count()

    def _update_count(self):
        self.count_var.set(
            f"انتخاب‌شده: {len(self.checked)} از {len(self.items)}"
        )

    def _toggle(self, iid):
        i = int(iid)
        if i in self.checked:
            self.checked.discard(i)
        else:
            self.checked.add(i)
        self.tree.set(iid, "_check", CHECKED if i in self.checked else UNCHECKED)
        self._update_count()

    def _on_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        iid = self.tree.identify_row(event.y)
        if iid:
            # keep keyboard selection in sync (v2.3 returned "break" before the
            # row was selected, so Space/Enter then toggled a different row)
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self._toggle(iid)
            return "break"

    def _on_space(self, _event):
        for iid in self.tree.selection():
            self._toggle(iid)
        return "break"

    def _select_all(self):
        self.checked.update(self._visible_indexes())
        self._refresh()

    def _clear_all(self):
        self.checked.difference_update(self._visible_indexes())
        self._refresh()

    # -------------------------------------------------------------- export
    def _export(self):
        chosen = [self.items[i] for i in sorted(self.checked)]
        if not chosen:
            messagebox.showwarning("انتخاب مورد",
                                   "حداقل یک مورد را برای چاپ انتخاب کنید.",
                                   parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"{self.file_prefix}_{tehran_now():%Y%m%d_%H%M%S}.pdf",
        )
        if not path:
            return
        try:
            from views.ui_kit import busy
            with busy(self):
                self.export_fn(chosen, path)
        except Exception as exc:
            messagebox.showerror("خطا", f"خطا در ایجاد PDF:\n\n{exc}", parent=self)
            return
        messagebox.showinfo("موفق", "فایل PDF با موفقیت ذخیره شد.", parent=self)
        try:
            os.startfile(path)          # Windows: open the PDF right away
        except Exception:
            pass
        self.destroy()


# ============================================================================
# PM
# ============================================================================
_PM_COLUMNS = [                      # right-to-left
    ("id", "شماره", 70),
    ("equipment", "تجهیز", 220),
    ("title", "عنوان", 240),
    ("department", "واحد", 130),
    ("frequency", "تناوب", 90),
    ("next_due", "سررسید بعدی", 110),
    ("status", "وضعیت", 90),
]


def _pm_row(pm):
    f = _pm_fields(pm)
    return {
        "id": str(f["id"]),
        "equipment": str(f["equipment"]),
        "title": str(f["title"] or ""),
        "department": str(f["department"]),
        "frequency": str(f["frequency"]),
        "next_due": str(f["next_due"]),
        "status": str(f["status"]),
    }


def run_pm_pdf_export(parent, pm_records, selected_pm=None, selected_pms=None):
    """Open the PM PDF selection dialog.

    pm_records  : the records to list (the same dicts the PM table uses).
    selected_pms: records that should start ticked (multi-select); if empty,
                  every listed record starts ticked.
    selected_pm : single-record shortcut kept for backward compatibility."""
    pm_records = list(pm_records or [])
    if not pm_records:
        messagebox.showwarning("هشدار", "برنامه PM برای خروجی وجود ندارد!",
                               parent=parent)
        return
    pre = list(selected_pms or [])
    if selected_pm is not None:
        pre.append(selected_pm)
    dialog = PdfSelectDialog(
        parent,
        "🖨 چاپ برنامه‌های نت پیشگیرانه (PDF)",
        pm_records,
        _pm_row,
        _PM_COLUMNS,
        export_pm_pdf,
        file_prefix="PM_Print",
        preselected=pre or None,
    )
    parent.wait_window(dialog)