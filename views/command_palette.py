# views/command_palette.py
"""
Quick search (Ctrl+K): jump to any page, equipment or work order by typing.

* Pages come from the side menu, so a user only sees what their role may open.
* Equipment is read once per opening (code + name).
* Typing a number offers «دستور کار شماره N».

Read-only: choosing an item only navigates (and fills the page's own search
box), it never changes data.
"""

from __future__ import annotations

import re
import tkinter as tk

from utils.theme import (
    WHITE, NAVY, TEXT_DARK, TEXT_MUTED, BORDER, ACCENT, ACCENT_SOFT, SURFACE_ALT,
    FONT_FAMILY, FONT_NORMAL, FONT_SMALL, FONT_BOLD, fa_digits, latin_digits,
)

_ARABIC = str.maketrans({"ي": "ی", "ك": "ک", "ى": "ی", "ة": "ه", "‌": " ", "ـ": ""})


def _norm(text) -> str:
    text = latin_digits(str(text or "")).translate(_ARABIC).lower()
    return re.sub(r"\s+", " ", text).strip()


class CommandPalette(tk.Toplevel):
    MAX_ROWS = 9
    _open = None

    @classmethod
    def show(cls, main):
        if cls._open is not None:
            try:
                if cls._open.winfo_exists():
                    cls._open.entry.focus_set()
                    return cls._open
            except tk.TclError:
                pass
        cls._open = cls(main)
        return cls._open

    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=BORDER)
        self._items = self._collect()
        self._shown = []

        body = tk.Frame(self, bg=WHITE)
        body.pack(fill="both", expand=True, padx=1, pady=1)

        top = tk.Frame(body, bg=WHITE, padx=14, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="⌕", font=(FONT_FAMILY, 14), bg=WHITE, fg=TEXT_MUTED).pack(side="right")
        self.var = tk.StringVar()
        self.entry = tk.Entry(top, textvariable=self.var, font=(FONT_FAMILY, 11), relief="flat",
                              bd=0, bg=WHITE, fg=TEXT_DARK, justify="right",
                              insertbackground=TEXT_DARK, highlightthickness=0)
        self.entry.pack(side="right", fill="x", expand=True, padx=(0, 10), ipady=4)
        tk.Label(top, text="Esc", font=FONT_SMALL, bg=SURFACE_ALT, fg=TEXT_MUTED,
                 padx=6).pack(side="left")
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x")

        self.list_frame = tk.Frame(body, bg=WHITE, pady=4)
        self.list_frame.pack(fill="both", expand=True)
        self.rows = []
        for _ in range(self.MAX_ROWS):
            row = tk.Frame(self.list_frame, bg=WHITE, cursor="hand2")
            kind = tk.Label(row, font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED, width=10, anchor="w")
            kind.pack(side="left", padx=(12, 0))
            text = tk.Label(row, font=FONT_NORMAL, bg=WHITE, fg=TEXT_DARK, anchor="e")
            text.pack(side="right", fill="x", expand=True, padx=(0, 14), pady=6)
            for w in (row, kind, text):
                w.bind("<Button-1>", lambda _e, i=len(self.rows): self._choose(i))
                w.bind("<Enter>", lambda _e, i=len(self.rows): self._select(i))
            self.rows.append((row, kind, text))
        self.empty = tk.Label(self.list_frame, text="موردی پیدا نشد", font=FONT_NORMAL,
                              bg=WHITE, fg=TEXT_MUTED, pady=14)
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x")
        tk.Label(body, text="↑ ↓ انتخاب   •   Enter باز کردن   •   صفحه، تجهیز یا شماره دستور کار",
                 font=FONT_SMALL, bg=SURFACE_ALT, fg=TEXT_MUTED, pady=5).pack(fill="x")

        self.index = 0
        self.var.trace_add("write", lambda *_: self._refresh())
        self.entry.bind("<Down>", lambda _e: (self._move(1), "break")[1])
        self.entry.bind("<Up>", lambda _e: (self._move(-1), "break")[1])
        self.entry.bind("<Return>", lambda _e: (self._choose(self.index), "break")[1])
        self.entry.bind("<KP_Enter>", lambda _e: (self._choose(self.index), "break")[1])
        self.bind("<Escape>", lambda _e: (self.close(), "break")[1])
        self.entry.bind("<FocusOut>", lambda _e: self.after(150, self._close_if_unfocused))

        self._refresh()
        self._place()
        self.deiconify()
        self.lift()
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.entry.focus_force()

    # ------------------------------------------------------------------ data
    def _collect(self):
        items = []
        labels = getattr(self.main, "_sidebar_button_labels", {}) or {}
        for key in getattr(self.main, "_sidebar_buttons", {}):
            label = labels.get(key, key)
            caption = label.split("  ", 1)[1] if "  " in label else label
            items.append(("صفحه", caption, ("page", key), _norm(caption)))
        pages = set(getattr(self.main, "_sidebar_buttons", {}))
        if "work_orders" in pages:
            items.append(("عملیات", "ثبت دستور کار جدید", ("new", "work_orders"),
                          _norm("ثبت دستور کار جدید ایجاد")))
        if "equipment" in pages:
            items.append(("عملیات", "افزودن تجهیز", ("new", "equipment"),
                          _norm("افزودن تجهیز جدید")))
        items.append(("عملیات", "بروزرسانی صفحه فعلی", ("refresh", None), _norm("بروزرسانی رفرش")))
        items.append(("راهنما", "میانبرهای صفحه‌کلید", ("help", None), _norm("میانبر کلید راهنما")))
        if "equipment" in pages:
            try:
                for eq in self.main.equipment_repo.get_all_equipment() or []:
                    code, name = eq.get("code") or "", eq.get("name") or ""
                    text = f"{name}  ({code})" if code else name
                    items.append(("تجهیز", text, ("equipment", code or name),
                                  _norm(f"{code} {name} {eq.get('location') or ''}")))
            except Exception as exc:
                print("palette equipment:", exc)
        return items

    def _matches(self, query):
        q = _norm(query)
        if not q:
            return [i for i in self._items if i[0] in ("صفحه", "عملیات", "راهنما")]
        words = q.split()
        result = [i for i in self._items if all(w in i[3] for w in words)]
        # Pages first, then actions, then equipment; earlier match = better
        order = {"صفحه": 0, "عملیات": 1, "تجهیز": 2, "راهنما": 3}
        result.sort(key=lambda i: (order.get(i[0], 9), i[3].find(words[0])))
        if q.lstrip("#").isdigit() and "work_orders" in getattr(self.main, "_sidebar_buttons", {}):
            number = int(q.lstrip("#"))
            result.insert(0, ("دستور کار", f"دستور کار شماره {fa_digits(number)}",
                              ("work_order", number), q))
        return result

    # -------------------------------------------------------------------- ui
    def _refresh(self):
        self._shown = self._matches(self.var.get())[: self.MAX_ROWS]
        for i, (row, kind, text) in enumerate(self.rows):
            if i < len(self._shown):
                k, t, _a, _n = self._shown[i]
                kind.configure(text=k)
                text.configure(text=t)
                row.pack(fill="x")
            else:
                row.pack_forget()
        if self._shown:
            self.empty.pack_forget()
        else:
            self.empty.pack(fill="x")
        self.index = 0
        self._paint()
        if getattr(self, "_placed", False):
            self._place()

    def _paint(self):
        for i, (row, kind, text) in enumerate(self.rows):
            bg = ACCENT_SOFT if i == self.index else WHITE
            for w in (row, kind, text):
                w.configure(bg=bg)
            text.configure(fg=NAVY if i == self.index else TEXT_DARK,
                           font=FONT_BOLD if i == self.index else FONT_NORMAL)

    def _move(self, step):
        if self._shown:
            self.index = (self.index + step) % len(self._shown)
            self._paint()

    def _select(self, i):
        if i < len(self._shown):
            self.index = i
            self._paint()

    def _place(self):
        self.update_idletasks()
        try:
            root = self.main
            w = min(620, max(420, root.winfo_width() - 80))
            h = self.winfo_reqheight()
            x = root.winfo_rootx() + (root.winfo_width() - w) // 2
            y = root.winfo_rooty() + 90
            self.geometry(f"{w}x{h}+{x}+{y}")
            self._placed = True
        except tk.TclError:
            pass

    def _close_if_unfocused(self):
        try:
            focus = self.focus_get()
        except (tk.TclError, KeyError):
            focus = None
        if focus is None or str(focus).startswith(str(self)) is False:
            self.close()

    def close(self):
        CommandPalette._open = None
        try:
            self.destroy()
        except tk.TclError:
            pass

    # ---------------------------------------------------------------- action
    def _choose(self, i):
        if i >= len(self._shown):
            return
        action, value = self._shown[i][2]
        main = self.main
        self.close()
        main.after(10, lambda: run_action(main, action, value))


def run_action(main, action, value):
    from views import shortcuts
    try:
        if action == "page":
            main._show_view(value)
        elif action == "new":
            main._show_view(value)
            page = getattr(main, "_current_view", None)
            if page is not None:
                main.after(150, lambda: shortcuts.page_new(page))
        elif action == "refresh":
            main._refresh_current_view()
        elif action == "help":
            shortcuts.show_help(main)
        elif action == "equipment":
            main._show_view("equipment")
            page = getattr(main, "_current_view", None)
            var = getattr(page, "search_var", None)
            if var is not None:
                var.set(value)
        elif action == "work_order":
            main._show_view("work_orders")
            page = getattr(main, "_current_view", None)
            if page is None:
                return
            var = getattr(page, "search_var", None)
            if var is not None:
                var.set(str(value))
                try:
                    page._load()
                except Exception as exc:
                    print("palette load:", exc)
            tree = getattr(page, "tree", None)
            if tree is not None:
                for item in tree.get_children(""):
                    vals = tree.item(item, "values") or ()
                    if vals and str(vals[0]) == str(value):
                        tree.selection_set(item)
                        tree.focus(item)
                        tree.see(item)
                        break
    except Exception as exc:
        print("palette action error:", exc)
