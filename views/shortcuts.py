"""
Keyboard shortcuts for the whole application.

Main window (every page):
    Ctrl+N          new record              (page.handle_new / «افزودن…» button)
    Ctrl+E, F2      edit selected           (page.handle_f2 / «ویرایش» button)
    Enter           open / edit selected    (page.handle_enter)
    Delete          delete selected         (page.handle_delete)
    Ctrl+K          quick search (pages, equipment, work order number)
    Ctrl+F          go to the search box
    Ctrl+R, F5      refresh
    Ctrl+P          print / PDF of the page («چاپ» button)
    Ctrl+S          save (pages that edit in place, e.g. machine hours)
    Ctrl+1 … Ctrl+9 open the n-th item of the side menu
    F11             full screen on / off,   Esc leaves full screen
    F1              this list

Dialogs:
    Esc             close (same as the window's X button, so «unsaved changes»
                    questions still appear)
    Ctrl+S          save (the dialog's «ذخیره» button) when the dialog has no
                    Ctrl+S of its own

Letters are recognised by their physical key on Windows, so the shortcuts
also work while the keyboard is on the Persian layout.  Nothing here changes
how text is typed: plain keys are never intercepted.
"""

import sys
import tkinter as tk
from tkinter import ttk

_IS_WIN = sys.platform == "win32"
_ALT_MASK = 0x20000 if _IS_WIN else 0x0008


# --------------------------------------------------------------------- utils
def _ctrl_key(event):
    """Latin letter/digit of a Ctrl+key press, independent of the layout."""
    if event.state & _ALT_MASK:          # AltGr / Ctrl+Alt: leave alone
        return None
    ks = event.keysym or ""
    if len(ks) == 1 and ks.isascii() and ks.isalnum():
        return ks.lower()
    code = getattr(event, "keycode", 0) or 0
    if _IS_WIN:
        if 65 <= code <= 90:             # VK_A .. VK_Z
            return chr(code).lower()
        if 48 <= code <= 57:             # VK_0 .. VK_9
            return chr(code)
        if 97 <= code <= 105:            # numpad 1..9
            return chr(code - 48)
    return None


def _walk(widget):
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        yield child
        yield from _walk(child)


def _visible(widget):
    try:
        return bool(widget.winfo_ismapped())
    except Exception:
        return False


def _button_text(widget):
    try:
        return str(widget.cget("text") or "")
    except Exception:
        return ""


def _enabled(widget):
    try:
        if isinstance(widget, ttk.Widget):
            return not widget.instate(["disabled"])
        return str(widget.cget("state")) != "disabled"
    except Exception:
        return True


def _find_button(root, words, exclude=()):
    for w in _walk(root):
        if isinstance(w, (tk.Button, ttk.Button)) and _visible(w) and _enabled(w):
            text = _button_text(w)
            if any(word in text for word in words) and not any(x in text for x in exclude):
                return w
    return None


def _invoke(button):
    try:
        button.invoke()
        return True
    except Exception:
        return False


def _has_own_binding(widget, sequences):
    try:
        tags = widget.bindtags()
    except Exception:
        return False
    for tag in tags:
        if tag == "all":
            continue
        for seq in sequences:
            try:
                if widget.bind_class(tag, seq):
                    return True
            except Exception:
                pass
    return False


# --------------------------------------------------------------- page actions
def _call(page, *names):
    for name in names:
        fn = getattr(page, name, None)
        if callable(fn):
            fn()
            return True
    return False


def focus_search(page):
    """Focus the page's search box (Entry tied to a *search* variable)."""
    names = set()
    for attr, value in list(vars(page).items()):
        if "search" in attr.lower():
            if isinstance(value, tk.Variable):
                names.add(str(value))
            elif isinstance(value, (tk.Entry, ttk.Entry)) and _visible(value):
                value.focus_set()
                value.select_range(0, "end")
                return True
    first_entry_near_label = None
    for w in _walk(page):
        if isinstance(w, (tk.Entry, ttk.Entry)) and _visible(w):
            try:
                var = str(w.cget("textvariable") or "")
            except Exception:
                var = ""
            if var and var in names:
                w.focus_set()
                w.select_range(0, "end")
                return True
            if first_entry_near_label is None:
                try:
                    siblings = w.master.winfo_children()
                except Exception:
                    siblings = []
                if any("جستجو" in _button_text(s) for s in siblings):
                    first_entry_near_label = w
    if first_entry_near_label is not None:
        first_entry_near_label.focus_set()
        first_entry_near_label.select_range(0, "end")
        return True
    return False


def page_new(page):
    if _call(page, "handle_new"):
        return True
    btn = _find_button(page, ("افزودن", "جدید", "ایجاد", "➕", "＋"), exclude=("خروجی", "تولید PM"))
    return _invoke(btn) if btn else False


def page_edit(page):
    if _call(page, "handle_f2", "handle_edit"):
        return True
    btn = _find_button(page, ("ویرایش",))
    return _invoke(btn) if btn else False


def page_print(page):
    if _call(page, "handle_print"):
        return True
    btn = _find_button(page, ("چاپ", "PDF"))
    return _invoke(btn) if btn else False


# ------------------------------------------------------------------ install
SHORTCUTS_HELP = (
    ("Ctrl + N", "ثبت مورد جدید"),
    ("Ctrl + E  یا  F2", "ویرایش ردیف انتخاب‌شده"),
    ("Enter", "باز کردن / ویرایش ردیف انتخاب‌شده"),
    ("Delete", "حذف ردیف انتخاب‌شده"),
    ("Ctrl + K", "جستجوی سریع: صفحه، تجهیز یا شماره دستور کار"),
    ("Ctrl + F", "رفتن به کادر جستجو"),
    ("Ctrl + R  یا  F5", "بروزرسانی صفحه"),
    ("Ctrl + P", "چاپ / PDF صفحه"),
    ("Ctrl + S", "ذخیره (در فرم‌ها و برگه ساعت کار)"),
    ("Ctrl + 1 … 9", "رفتن به صفحه‌های منوی کناری"),
    ("Esc", "بستن پنجره / خروج از تمام‌صفحه"),
    ("F11", "تمام‌صفحه"),
    ("F1", "همین راهنما"),
)


def show_help(parent):
    from utils.theme import NAVY, WHITE, TEXT_DARK, TEXT_LIGHT, GRAY_BG, FONT_BOLD, FONT_NORMAL, FONT_HEADING
    win = tk.Toplevel(parent)
    win.title("میانبرهای صفحه‌کلید")
    win.configure(bg=WHITE)
    win.transient(parent)
    win.resizable(False, False)
    head = tk.Frame(win, bg=NAVY)
    head.pack(fill="x")
    tk.Label(head, text="⌨  میانبرهای صفحه‌کلید", font=FONT_HEADING, bg=NAVY, fg=WHITE,
             anchor="e").pack(fill="x", padx=16, pady=10)
    body = tk.Frame(win, bg=WHITE)
    body.pack(fill="both", expand=True, padx=16, pady=10)
    for i, (keys, text) in enumerate(SHORTCUTS_HELP):
        bg = GRAY_BG if i % 2 else WHITE
        row = tk.Frame(body, bg=bg)
        row.pack(fill="x")
        tk.Label(row, text=text, font=FONT_NORMAL, bg=bg, fg=TEXT_DARK, anchor="e",
                 width=34).pack(side="right", padx=8, pady=5)
        tk.Label(row, text=keys, font=FONT_BOLD, bg=bg, fg=NAVY, anchor="w",
                 width=18).pack(side="left", padx=8, pady=5)
    tk.Label(win, text="میانبرها با صفحه‌کلید فارسی هم کار می‌کنند.", font=FONT_NORMAL,
             bg=WHITE, fg=TEXT_LIGHT).pack(pady=(0, 6))
    tk.Button(win, text="بستن", font=FONT_NORMAL, bg=NAVY, fg=WHITE, relief="flat",
              padx=20, pady=4, cursor="hand2", command=win.destroy).pack(pady=(0, 12))
    try:
        from views.ui_kit import center_window
        win.update_idletasks()
        center_window(win, win.winfo_reqwidth(), win.winfo_reqheight(), parent)
    except Exception:
        pass
    win.focus_set()
    return win


def install(main):
    """Bind the shortcuts on the main window (`main` is the MainView)."""

    def current_page():
        return getattr(main, "_current_view", None)

    def on_ctrl(event):
        if getattr(main, "_destroyed", False):
            return None
        key = _ctrl_key(event)
        if not key:
            return None
        # A widget/page that binds this exact Ctrl+key itself (for example a
        # table's own Ctrl+N) has already handled a Latin-layout press.
        if event.keysym.lower() == key and _has_own_binding(
                event.widget, (f"<Control-{key}>", f"<Control-Key-{key}>",
                               f"<Control-{key.upper()}>")):
            return None
        page = current_page()
        try:
            if key.isdigit() and key != "0":
                keys = list(getattr(main, "_sidebar_buttons", {}).keys())
                index = int(key) - 1
                if index < len(keys):
                    main._show_view(keys[index])
                return "break"
            if key == "k":
                from views.command_palette import CommandPalette
                CommandPalette.show(main)
                return "break"
            if page is None:
                return None
            if key == "n":
                page_new(page)
                return "break"
            if key == "e":
                page_edit(page)
                return "break"
            if key == "f":
                focus_search(page)
                return "break"
            if key == "r":
                main._refresh_current_view()
                return "break"
            if key == "p":
                page_print(page)
                return "break"
            if key == "s":
                return "break" if _call(page, "handle_save") else None
        except Exception as exc:
            print("shortcut error:", exc)
        return None

    def on_f2(_event=None):
        page = current_page()
        if page is not None and not main._is_editing():
            page_edit(page)
        return "break"

    main.bind("<Control-KeyPress>", on_ctrl, add="+")
    main.bind("<F2>", on_f2, add="+")
    main.bind("<F1>", lambda _e: (show_help(main), "break")[1], add="+")
    install_dialog_shortcuts(main)


def install_dialog_shortcuts(root):
    """Esc closes and Ctrl+S saves in every dialog (Toplevel) of the app."""

    def dialog_of(event):
        try:
            top = event.widget.winfo_toplevel()
        except Exception:
            return None
        if top is root or not isinstance(top, tk.Toplevel):
            return None
        return top

    def on_escape(event):
        top = dialog_of(event)
        if top is None or getattr(top, "_no_escape_close", False):
            return None
        if _has_own_binding(event.widget, ("<Escape>", "<Key-Escape>")):
            return None
        try:
            if not top.winfo_exists():
                return None
            handler = top.protocol("WM_DELETE_WINDOW")
            if handler:
                top.tk.call(handler)
            else:
                top.destroy()
        except Exception:
            pass
        return "break"

    def on_ctrl(event):
        if _ctrl_key(event) != "s":
            return None
        top = dialog_of(event)
        if top is None:
            return None
        if _has_own_binding(event.widget, ("<Control-s>", "<Control-Key-s>", "<Control-S>")) \
                and event.keysym.lower() == "s":
            return None
        btn = _find_button(top, ("ذخیره", "ثبت"), exclude=("لغو", "انصراف"))
        if btn is not None:
            _invoke(btn)
            return "break"
        return None

    root.bind_all("<Escape>", on_escape, add="+")
    root.bind_all("<Control-KeyPress>", on_ctrl, add="+")
