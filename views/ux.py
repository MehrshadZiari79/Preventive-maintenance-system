# views/ux.py
"""
Shared look-and-feel layer (v2.4.7).

Everything in this module is *additive*: it only changes colours, adds
small overlay widgets and replaces the plain Windows message boxes with
styled ones.  No page logic, database code, PDF/Excel output or text-entry
widget is changed here, so Persian typing behaves exactly as before.

Safety switch
-------------
Set the environment variable ``PM_CLASSIC_UI=1`` before starting the
program to switch every feature of this module off (old message boxes, no
table overlays, old page headers).  Each feature is also wrapped in
try/except: a failure here never stops a page from working.

Contents
--------
* ``style_button``      - button hierarchy (primary / outline / danger ...)
* ``restyle_header``    - one light page-header style for every page
* ``install_dialogs``   - styled message boxes + toast for short successes
* ``enhance_tree``      - zebra rows, hover, status badges, empty/loading
* ``TableFooter``       - "N ردیف" counter + removable filter chips
* ``field_error``       - inline form errors (red border + message)
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import ttk

from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, TEXT_DARK, TEXT_MUTED, BORDER, BORDER_STRONG,
    ACCENT, ACCENT_SOFT, SURFACE_ALT, GRAY_BG, SUCCESS, SUCCESS_SOFT,
    WARNING, WARNING_SOFT, DANGER, DANGER_SOFT, INFO, INFO_SOFT,
    FONT_FAMILY, FONT_TITLE, FONT_HEADING, FONT_NORMAL, FONT_BOLD, FONT_SMALL,
    SPACE_PAGE, fa_digits,
)

ENABLED = os.environ.get("PM_CLASSIC_UI", "").strip() not in ("1", "true", "yes")


def _log(context, exc):
    try:
        from utils.error_log import log_error
        log_error(f"ux.{context}", exc)
    except Exception:
        pass


# ===========================================================================
# Buttons
# ===========================================================================

# kind:        bg            fg         hover bg      hover fg   border
BUTTON_KINDS = {
    "primary":  (NAVY,        WHITE,     NAVY_LIGHT,   WHITE,     None),
    "outline":  (WHITE,       NAVY,      ACCENT_SOFT,  NAVY,      BORDER_STRONG),
    "danger":   (DANGER,      WHITE,     "#B91C1C",    WHITE,     None),
    "danger_soft": (WHITE,    DANGER,    DANGER_SOFT,  "#B91C1C", "#F3B4B4"),
}

_PRIMARY_WORDS = ("افزودن", "جدید", "ایجاد", "➕", "＋")
_NOT_PRIMARY_WORDS = ("خروجی", "Excel", "PDF", "چاپ", "تولید", "بروزرسانی", "مدیریت")
_DANGER_WORDS = ("اضطراری",)
_DELETE_WORDS = ("حذف",)


def classify_button(text: str) -> str:
    text = str(text or "")
    if any(w in text for w in _DANGER_WORDS):
        return "danger"
    if any(w in text for w in _DELETE_WORDS):
        return "danger_soft"
    stripped = text.strip()
    if (any(w in text for w in _PRIMARY_WORDS) or stripped.startswith("+")) and \
            not any(w in text for w in _NOT_PRIMARY_WORDS):
        return "primary"
    return "outline"


def style_button(btn, kind="outline", font=None):
    """Re-colour an existing tk.Button (text, command and layout unchanged)."""
    if not isinstance(btn, tk.Button):
        return btn
    bg, fg, hbg, hfg, border = BUTTON_KINDS.get(kind, BUTTON_KINDS["outline"])
    opts = dict(
        bg=bg, fg=fg, activebackground=hbg, activeforeground=hfg,
        relief="flat", bd=0, cursor="hand2", disabledforeground="#9AA4B2",
    )
    if border:
        opts.update(highlightthickness=1, highlightbackground=border, highlightcolor=ACCENT)
    else:
        opts.update(highlightthickness=0)
    if font is not None:
        opts["font"] = font
    try:
        btn.configure(**opts)
    except tk.TclError:
        return btn

    # Hover restores whatever colour the button had before (a page may
    # recolour a button to show a state; hover must not undo that).
    def _enter(_e, b=btn):
        try:
            if str(b.cget("state")) != "disabled":
                b._ux_rest = (b.cget("bg"), b.cget("fg"))
                b.configure(bg=hbg, fg=hfg)
        except tk.TclError:
            pass

    def _leave(_e, b=btn):
        try:
            rest = getattr(b, "_ux_rest", None) or (bg, fg)
            if str(b.cget("state")) != "disabled" and str(b.cget("bg")) == hbg:
                b.configure(bg=rest[0], fg=rest[1])
        except tk.TclError:
            pass

    btn.bind("<Enter>", _enter)
    btn.bind("<Leave>", _leave)
    btn._ux_kind = kind
    return btn


# ===========================================================================
# Page header
# ===========================================================================

_DARK_BG = {c.lower() for c in (NAVY, NAVY_LIGHT, "#1a2a44", "#2c3e6b", "#121e33",
                                 "#1e3a5f", "#1f2d4d", "#0f1c2e")}
HEADER_BG = WHITE


def _walk(widget):
    try:
        children = widget.winfo_children()
    except tk.TclError:
        return
    for child in children:
        yield child
        yield from _walk(child)


def _is_dark(color):
    return str(color or "").lower() in _DARK_BG


def _font_size(widget):
    try:
        from tkinter import font as tkfont
        f = tkfont.Font(font=widget.cget("font"))
        return abs(int(f.actual("size")))
    except Exception:
        return 9


def _is_icon_text(text):
    text = str(text or "").strip()
    return 0 < len(text) <= 3 and not any(ch.isalpha() for ch in text)


def restyle_header(header):
    """
    Turn a page's dark banner into the shared light header:
    white band, dark title, muted subtitle, accent icon, a thin bottom
    border, one solid primary button and outlined secondary buttons.

    Only colours change: texts, commands, sizes and layout stay as they are,
    so keyboard shortcuts that look buttons up by caption still work.
    """
    if not ENABLED or header is None:
        return
    try:
        widgets = [header] + list(_walk(header))
        buttons = []
        for w in widgets:
            cls = w.winfo_class()
            if cls in ("Frame", "Label", "Canvas"):
                try:
                    if _is_dark(w.cget("bg")):
                        w.configure(bg=HEADER_BG)
                except tk.TclError:
                    pass
            if cls == "Label":
                try:
                    text = str(w.cget("text") or "")
                    fg = str(w.cget("fg")).lower()
                except tk.TclError:
                    continue
                if _is_icon_text(text):
                    w.configure(fg=ACCENT)
                elif _font_size(w) >= 12:
                    w.configure(fg=TEXT_DARK)
                elif fg in ("#ffffff", "white", "#d7e3f4", "#c9d6ea", "#cbd5e1", "#e6ecf5",
                            "#dbe4f0", "#e5e7eb", "#d1d5db", "#b8c4d6", "#aab7cc", "#9fb3d1"):
                    w.configure(fg=TEXT_MUTED)
            elif cls == "Button":
                buttons.append(w)

        primary_done = False
        for b in buttons:
            try:
                kind = classify_button(b.cget("text"))
            except tk.TclError:
                continue
            if kind == "primary":
                if primary_done:
                    kind = "outline"
                primary_done = True
            style_button(b, kind)

        _add_bottom_border(header)
        header._ux_header = True
    except Exception as exc:
        _log("restyle_header", exc)


def _add_bottom_border(header):
    try:
        if header.winfo_manager() != "pack":
            return
        parent = header.master
        slaves = parent.pack_slaves()
        idx = slaves.index(header)
        if idx + 1 < len(slaves):
            nxt = slaves[idx + 1]
            if nxt.winfo_class() == "Frame" and int(nxt.cget("height") or 0) <= 2 \
                    and not nxt.winfo_children():
                nxt.configure(bg=BORDER)
                return
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", after=header)
    except Exception:
        pass


def find_page_header(view):
    """The page's banner: the first dark frame near the top of the page."""
    queue = [(view, 0)]
    while queue:
        widget, depth = queue.pop(0)
        try:
            children = widget.pack_slaves() or widget.winfo_children()
        except tk.TclError:
            continue
        for child in children:
            try:
                if child.winfo_class() == "Frame" and _is_dark(child.cget("bg")):
                    return child
            except tk.TclError:
                continue
            if depth < 2:
                queue.append((child, depth + 1))
    return None


def polish_page(view):
    """Called by the main window after a page is shown."""
    if not ENABLED or view is None:
        return
    try:
        header = find_page_header(view)
        if header is not None and not getattr(header, "_ux_header", False):
            restyle_header(header)
    except Exception as exc:
        _log("polish_page.header", exc)
    if getattr(view, "ux_skip_tables", False):
        return
    try:
        calm_toolbar_buttons(view)
    except Exception as exc:
        _log("polish_page.buttons", exc)
    try:
        main_tree = getattr(view, "tree", None)
        strip = bool(getattr(view, "ux_status_only_rows", False))
        for w in _walk(view):
            if isinstance(w, ttk.Treeview) and not getattr(w, "_ux", None):
                enhance_tree(w, strip_tints=strip and w is main_tree)
    except Exception as exc:
        _log("polish_page.tables", exc)
    try:
        _attach_page_footers(view)
    except Exception as exc:
        _log("polish_page.footer", exc)


# Loud one-off colours used by older toolbars (purple PDF, teal/green Excel,
# orange, grey ...).  Navy, white and blue buttons are left alone because
# pages use them as on/off toggles.
_LOUD = {c.lower() for c in (
    "#7C3AED", "#6D28D9", "#8B5CF6", "#9333EA", "#0D9488", "#0F766E", "#14B8A6",
    "#16A34A", "#15803D", "#059669", "#10B981", "#22C55E", "#EA580C", "#D97706",
    "#F59E0B", "#F97316", "#C2410C", "#6B7280", "#64748B", "#475569", "#94A3B8",
    "#DC2626", "#EF4444", "#B91C1C", "#E11D48",
)}
_SAVE_WORDS = ("ذخیره", "ثبت", "افزودن", "جدید", "＋", "➕")


def calm_toolbar_buttons(view):
    """One button hierarchy for toolbars that still use loud colours."""
    if not ENABLED:
        return
    for w in _walk(view):
        if w.winfo_class() != "Button" or getattr(w, "_ux_kind", None):
            continue
        try:
            if str(w.cget("bg")).lower() not in _LOUD:
                continue
            text = str(w.cget("text") or "")
        except tk.TclError:
            continue
        if any(x in text for x in _DANGER_WORDS):
            kind = "danger"
        elif any(x in text for x in _DELETE_WORDS):
            kind = "danger_soft"
        elif any(x in text for x in _SAVE_WORDS) and \
                not any(x in text for x in _NOT_PRIMARY_WORDS):
            kind = "primary"
        else:
            kind = "outline"
        style_button(w, kind)


# ===========================================================================
# Styled message boxes
# ===========================================================================

_TONES = {
    #          icon  colour   soft
    "info":    ("i", INFO,    INFO_SOFT),
    "success": ("✓", SUCCESS, SUCCESS_SOFT),
    "warning": ("!", WARNING, WARNING_SOFT),
    "error":   ("✕", DANGER,  DANGER_SOFT),
    "question": ("?", ACCENT, ACCENT_SOFT),
}

_ORIGINAL = {}
_SUCCESS_WORDS = ("موفق", "ذخیره شد", "ثبت شد", "انجام شد", "حذف شد", "بروزرسانی شد",
                  "ایجاد شد", "تأیید شد", "تایید شد", "ارسال شد", "اعمال شد")


def _main_thread():
    return threading.current_thread() is threading.main_thread()


def _resolve_parent(parent):
    if parent is not None:
        try:
            if parent.winfo_exists():
                return parent.winfo_toplevel()
        except Exception:
            pass
    root = tk._default_root
    if root is None:
        return None
    try:
        grab = root.grab_current()
        if grab is not None and grab.winfo_exists():
            return grab.winfo_toplevel()
    except Exception:
        pass
    try:
        focus = root.focus_get()
        if focus is not None:
            return focus.winfo_toplevel()
    except Exception:
        pass
    return root


class MessageDialog(tk.Toplevel):
    """Modal, RTL message dialog in the app's style.  Returns ``.result``."""

    def __init__(self, parent, title, message, tone="info", buttons=(("ok", "تأیید", True),),
                 default=None, cancel_value=None, danger=False, detail=None):
        super().__init__(parent)
        self.withdraw()
        self.result = cancel_value
        self._cancel_value = cancel_value
        self._done = False
        self.title(title or "")
        self.configure(bg=WHITE)
        self.resizable(False, False)
        try:
            if parent is not None and parent.winfo_viewable():
                self.transient(parent)
        except tk.TclError:
            pass
        icon, color, soft = _TONES.get(tone, _TONES["info"])

        tk.Frame(self, bg=color, height=3).pack(fill="x")
        body = tk.Frame(self, bg=WHITE, padx=22, pady=18)
        body.pack(fill="both", expand=True)

        top = tk.Frame(body, bg=WHITE)
        top.pack(fill="x")
        badge = tk.Label(top, text=icon, font=(FONT_FAMILY, 13, "bold"), bg=soft, fg=color,
                         width=2, pady=2)
        badge.pack(side="right", anchor="n")
        text_col = tk.Frame(top, bg=WHITE)
        text_col.pack(side="right", fill="both", expand=True, padx=(0, 12))
        tk.Label(text_col, text=title or "", font=FONT_HEADING, bg=WHITE, fg=TEXT_DARK,
                 anchor="e", justify="right").pack(fill="x")
        msg = str(message or "")
        tk.Label(text_col, text=msg, font=FONT_NORMAL, bg=WHITE, fg=TEXT_DARK, anchor="e",
                 justify="right", wraplength=420).pack(fill="x", pady=(6, 0))
        if detail:
            tk.Label(text_col, text=str(detail), font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED,
                     anchor="e", justify="right", wraplength=420).pack(fill="x", pady=(6, 0))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        foot = tk.Frame(self, bg=SURFACE_ALT, padx=16, pady=10)
        foot.pack(fill="x")
        self._buttons = {}
        focus_btn = None
        # RTL: the main action sits at the far LEFT end of the footer.
        for value, caption, is_main in buttons:
            kind = ("danger" if danger else "primary") if is_main else "outline"
            b = tk.Button(foot, text=caption, font=FONT_BOLD if is_main else FONT_NORMAL,
                          padx=18, pady=5, command=lambda v=value: self._finish(v))
            style_button(b, kind)
            b.pack(side="left", padx=(0, 8))
            b.bind("<Return>", lambda _e=None, v=value: self._finish(v))
            b.bind("<KP_Enter>", lambda _e=None, v=value: self._finish(v))
            self._buttons[value] = b
            if default is not None and value == default:
                focus_btn = b
            elif default is None and is_main and focus_btn is None:
                focus_btn = b

        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(self._cancel_value))
        self.bind("<Escape>", lambda _e=None: (self._finish(self._cancel_value), "break")[1])

        self.update_idletasks()
        self._place(parent)
        self.deiconify()
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.after(200, lambda: self.winfo_exists() and self.attributes("-topmost", False))
        except tk.TclError:
            pass
        self._focus_btn = focus_btn
        if focus_btn is not None:
            focus_btn.focus_set()
        else:
            self.focus_set()

    def _place(self, parent):
        w, h = max(380, self.winfo_reqwidth()), self.winfo_reqheight()
        try:
            if parent is not None and parent.winfo_viewable():
                x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
                y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
            else:
                raise tk.TclError
        except tk.TclError:
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def _finish(self, value):
        if self._done:
            return
        self._done = True
        self.result = value
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def run(self):
        previous_grab = None
        try:
            previous_grab = self.grab_current()
        except tk.TclError:
            pass
        try:
            self.grab_set()
        except tk.TclError:
            pass
        try:
            self.wait_window(self)
        except tk.TclError:
            pass
        if previous_grab is not None:
            try:
                if previous_grab.winfo_exists() and previous_grab.winfo_viewable():
                    previous_grab.grab_set()
            except tk.TclError:
                pass
        return self.result


def _is_toastable(title, message):
    text = f"{title or ''} {message or ''}"
    if "راهنما" in text or len(str(message or "")) > 180 or str(message or "").count("\n") > 3:
        return False
    return True


def _toast_root(parent):
    """The main application window if it is up; toasts only live there."""
    try:
        root = tk._default_root
        if root is None or not root.winfo_exists() or not root.winfo_viewable():
            return None
        if root.__class__.__name__ != "MainView" or getattr(root, "_destroyed", False):
            return None
        return root
    except Exception:
        return None


def notify(parent, title, message, tone="success"):
    """Short non-blocking notification (bottom-left of the main window)."""
    root = _toast_root(parent)
    if root is None:
        return False
    try:
        from views.ui_kit import Toast
        msg = str(message or "")
        timeout = min(10000, 4000 + 45 * len(msg))
        Toast(root, title or "", lines=[msg] if msg else [], tone=tone, timeout_ms=timeout)
        return True
    except Exception as exc:
        _log("notify", exc)
        return False


def _make_api():
    def _call(kind, title=None, message=None, **options):
        parent = _resolve_parent(options.get("parent"))
        detail = options.get("detail")
        default = options.get("default")
        danger = any(w in f"{title or ''} {message or ''}" for w in _DELETE_WORDS)
        if kind == "showinfo":
            if _is_toastable(title, message) and notify(parent, title, message,
                                                        tone="success"):
                return "ok"
            return MessageDialog(parent, title, message, "info", detail=detail,
                                 cancel_value="ok").run()
        if kind == "showwarning":
            return MessageDialog(parent, title, message, "warning", detail=detail,
                                 cancel_value="ok").run()
        if kind == "showerror":
            return MessageDialog(parent, title, message, "error", detail=detail,
                                 cancel_value="ok").run()
        yes_no = (("yes", "بله", True), ("no", "خیر", False))
        if kind == "askyesno":
            r = MessageDialog(parent, title, message, "question", yes_no,
                              default=default, cancel_value="no", danger=danger,
                              detail=detail).run()
            return r == "yes"
        if kind == "askquestion":
            return MessageDialog(parent, title, message, "question", yes_no,
                                 default=default, cancel_value="no", danger=danger,
                                 detail=detail).run()
        if kind == "askyesnocancel":
            r = MessageDialog(parent, title, message, "question",
                              (("yes", "بله", True), ("no", "خیر", False),
                               ("cancel", "انصراف", False)),
                              default=default, cancel_value="cancel", danger=danger,
                              detail=detail).run()
            return None if r == "cancel" else r == "yes"
        if kind == "askokcancel":
            r = MessageDialog(parent, title, message, "question",
                              (("ok", "تأیید", True), ("cancel", "انصراف", False)),
                              default=default, cancel_value="cancel", danger=danger,
                              detail=detail).run()
            return r == "ok"
        if kind == "askretrycancel":
            r = MessageDialog(parent, title, message, "warning",
                              (("retry", "تلاش دوباره", True), ("cancel", "انصراف", False)),
                              default=default, cancel_value="cancel", detail=detail).run()
            return r == "retry"
        raise ValueError(kind)

    def make(kind):
        original = _ORIGINAL[kind]

        def styled(title=None, message=None, **options):
            if not _main_thread() or tk._default_root is None:
                return original(title, message, **options)
            try:
                return _call(kind, title, message, **options)
            except Exception as exc:
                _log(f"dialog.{kind}", exc)
                return original(title, message, **options)

        styled.__name__ = kind
        styled._ux_styled = True
        return styled

    return make


def install_dialogs():
    """Replace tkinter.messagebox functions with the styled versions (once)."""
    if not ENABLED:
        return
    from tkinter import messagebox
    kinds = ("showinfo", "showwarning", "showerror", "askyesno", "askyesnocancel",
             "askokcancel", "askquestion", "askretrycancel")
    make = _make_api()
    for k in kinds:
        current = getattr(messagebox, k, None)
        # Only replace the genuine tkinter functions (never a replacement
        # someone else installed, and never twice).
        if current is None or getattr(current, "_ux_styled", False) or \
                getattr(current, "__module__", "") != "tkinter.messagebox":
            continue
        _ORIGINAL[k] = current
        setattr(messagebox, k, make(k))


# ===========================================================================
# Tables
# ===========================================================================

STATUS_TONES = (
    # (words, tone) - first match wins; checked in this order
    (("لغو", "رد شد", "رد شده", "خراب", "معوق", "سررسید گذشته", "منقضی", "اضطراری",
      "غیرفعال", "ناموفق", "خطا", "بحرانی", "تمام شده", "اتمام موجودی", "ناسالم", "مردود",
      "عقب"), "danger"),
    (("در انتظار", "درخواست", "در حال", "در تعمیر", "نزدیک", "کم موجود", "موجودی کم", "هشدار", "متوقف", "معلق",
      "بررسی", "نیاز", "توقف", "این هفته", "جزئی"), "warning"),
    (("تکمیل", "عملیاتی", "فعال", "سالم", "تأیید", "تایید", "انجام شد", "انجام‌شده",
      "موفق", "کافی", "قبول", "به موقع", "بسته"), "success"),
    (("باز", "جدید", "برنامه", "ثبت"), "info"),
)

_BADGE_COLORS = {
    "success": (SUCCESS_SOFT, "#15803D"),
    "warning": (WARNING_SOFT, "#B45309"),
    "danger": (DANGER_SOFT, "#B91C1C"),
    "info": (INFO_SOFT, INFO),
    "neutral": ("#EEF1F5", TEXT_MUTED),
}


def status_tone(text):
    text = str(text or "").replace("\u200c", " ").strip()
    if not text or text in ("—", "-"):
        return None
    for words, tone in STATUS_TONES:
        if any(w in text for w in words):
            return tone
    return "neutral"


def _find_status_column(tree):
    try:
        for col in tree["columns"]:
            heading = str(tree.heading(col, "text") or "")
            if heading.strip() == "وضعیت" or heading.strip().startswith("وضعیت"):
                return col
    except Exception:
        pass
    return None


class _TreeUX:
    """Per-tree enhancer.  Created by ``enhance_tree``."""

    ROW_ZEBRA = "_ux_zebra"
    ROW_HOVER = "_ux_hover"

    def __init__(self, tree, status_column="auto", empty_text=None, zebra=True,
                 badges=True, hover=True, strip_tints=False):
        self.tree = tree
        self.strip_tints = strip_tints
        self.footer = None
        self.empty_text = empty_text or "موردی برای نمایش وجود ندارد"
        self.status_column = (_find_status_column(tree) if status_column == "auto"
                              else status_column)
        self.badges_on = bool(badges and self.status_column)
        self.zebra_on = zebra
        self.hover_on = hover
        self._pending = False
        self._layout_pending = False
        self._hover_item = None
        self._badges = []
        self._overlay = None
        self._state = "init"          # init -> loading/empty/rows
        self._changed_once = False
        self._wrapped_scroll = {}

        # Tags created now are LOWER priority than the page's own tags
        # (Tk gives the earliest created tag the highest priority), so a
        # page's coloured rows always keep their colour.
        try:
            tree.tag_configure(self.ROW_HOVER, background="#EAF1FF")
            tree.tag_configure(self.ROW_ZEBRA, background="#F7F9FC")
        except tk.TclError:
            pass

        for name in ("insert", "delete", "move", "detach", "reattach"):
            self._wrap(name)

        tree.bind("<Configure>", lambda _e: self.schedule_layout(), add="+")
        tree.bind("<Map>", lambda _e: self.schedule_layout(), add="+")
        tree.bind("<ButtonRelease-1>", lambda _e: self.schedule_layout(), add="+")
        tree.bind("<KeyRelease>", lambda _e: self.schedule_layout(), add="+")
        tree.bind("<MouseWheel>", lambda _e: self.schedule_layout(), add="+")
        tree.bind("<Button-4>", lambda _e: self.schedule_layout(), add="+")
        tree.bind("<Button-5>", lambda _e: self.schedule_layout(), add="+")
        tree.bind("<<TreeviewSelect>>", lambda _e: self.schedule_layout(), add="+")
        tree.bind("<<TreeviewOpen>>", lambda _e: self.schedule_refresh(), add="+")
        tree.bind("<<TreeviewClose>>", lambda _e: self.schedule_refresh(), add="+")
        if hover:
            tree.bind("<Motion>", self._on_motion, add="+")
            tree.bind("<Leave>", lambda _e: self._set_hover(None), add="+")

        if tree.get_children(""):
            self._changed_once = True
        else:
            # Pages that load in the background fill the table a moment
            # later; if nothing arrives the table is simply empty.
            def _settle():
                if not self._changed_once:
                    self._changed_once = True
                    self.schedule_refresh()
            try:
                tree.after(1500, _settle)
            except tk.TclError:
                pass
        self.schedule_refresh()

    # -- change tracking -------------------------------------------------
    def _wrap(self, name):
        original = getattr(self.tree, name)

        def wrapped(*args, **kwargs):
            result = original(*args, **kwargs)
            try:
                self._changed_once = True
                if name == "delete" and self._hover_item is not None:
                    try:
                        if not self.tree.exists(self._hover_item):
                            self._hover_item = None
                    except tk.TclError:
                        self._hover_item = None
                self.schedule_refresh()
            except Exception:
                pass
            return result

        setattr(self.tree, name, wrapped)

    def schedule_refresh(self):
        if self._pending:
            return
        self._pending = True
        try:
            self.tree.after_idle(self._refresh)
        except tk.TclError:
            self._pending = False

    def schedule_layout(self):
        if not self.badges_on or self._layout_pending:
            return
        self._layout_pending = True
        try:
            self.tree.after_idle(self._layout_badges)
        except tk.TclError:
            self._layout_pending = False

    # -- refresh: zebra, overlay, footer ------------------------------------
    def _bg_tags(self):
        result = set()
        try:
            names = self.tree.tk.splitlist(self.tree.tk.call(self.tree._w, "tag", "names"))
        except tk.TclError:
            names = ()
        for tag in names:
            if tag in (self.ROW_ZEBRA, self.ROW_HOVER):
                continue
            try:
                if str(self.tree.tag_configure(tag, "background") or ""):
                    result.add(tag)
            except tk.TclError:
                pass
        return result

    def _visible_items(self, parent=""):
        tree = self.tree
        for item in tree.get_children(parent):
            yield item
            try:
                if tree.item(item, "open") and tree.get_children(item):
                    yield from self._visible_items(item)
            except tk.TclError:
                pass

    def _refresh(self):
        self._pending = False
        tree = self.tree
        try:
            if not tree.winfo_exists():
                return
        except tk.TclError:
            return
        try:
            items = list(self._visible_items())
            if self.badges_on:
                self._neutralise_row_colours()
            if self.zebra_on and len(items) <= 5000:
                bg_tags = self._bg_tags()
                for index, item in enumerate(items):
                    tags = tuple(tree.item(item, "tags") or ())
                    want = index % 2 == 1 and not (set(tags) & bg_tags)
                    has = self.ROW_ZEBRA in tags
                    if want and not has:
                        tree.item(item, tags=tags + (self.ROW_ZEBRA,))
                    elif has and not want:
                        tree.item(item, tags=tuple(t for t in tags if t != self.ROW_ZEBRA))
            count = len(tree.get_children(""))
            if count:
                self._set_state("rows")
            elif self._changed_once:
                self._set_state("empty")
            else:
                self._set_state("loading")
            if self.footer is not None:
                self.footer.update_count(count)
        except Exception as exc:
            _log("tree.refresh", exc)
        self.schedule_layout()

    def _neutralise_row_colours(self):
        """Status colour moves to the badge; row text stays dark."""
        tree = self.tree
        try:
            names = tree.tk.splitlist(tree.tk.call(tree._w, "tag", "names"))
        except tk.TclError:
            return
        for tag in names:
            if tag.startswith("_ux"):
                continue
            try:
                fg = str(tree.tag_configure(tag, "foreground") or "")
                bg = str(tree.tag_configure(tag, "background") or "")
            except tk.TclError:
                continue
            if self.strip_tints and bg:
                # The page coloured whole rows by status; the badge shows it now.
                try:
                    tree.tag_configure(tag, background="", foreground=TEXT_DARK)
                except tk.TclError:
                    pass
                continue
            if fg and not bg and fg.lower() not in (TEXT_DARK.lower(), "black", "#000000"):
                try:
                    tree.tag_configure(tag, foreground=TEXT_DARK)
                except tk.TclError:
                    pass

    # -- empty / loading overlay ---------------------------------------------
    def _set_state(self, state):
        if state == self._state:
            if state == "empty" and self._overlay is not None:
                self._update_clear_button()
            return
        self._state = state
        if self._overlay is not None:
            try:
                self._overlay.destroy()
            except tk.TclError:
                pass
            self._overlay = None
        if state == "rows":
            return
        tree = self.tree
        try:
            bg = str(ttk.Style(tree).lookup(tree.cget("style") or "Treeview", "fieldbackground")
                     or WHITE)
        except Exception:
            bg = WHITE
        box = tk.Frame(tree, bg=bg)
        if state == "loading":
            tk.Label(box, text="در حال بارگذاری…", font=FONT_NORMAL, bg=bg,
                     fg=TEXT_MUTED).pack()
        else:
            tk.Label(box, text="◌", font=(FONT_FAMILY, 20), bg=bg, fg=BORDER_STRONG).pack()
            tk.Label(box, text=self.empty_text, font=FONT_BOLD, bg=bg,
                     fg=TEXT_MUTED).pack(pady=(2, 0))
            self._hint = tk.Label(box, text="", font=FONT_SMALL, bg=bg, fg=TEXT_MUTED)
            self._clear_btn = tk.Button(box, text="پاک کردن فیلترها", font=FONT_SMALL,
                                        padx=12, pady=3, command=self._clear_filters)
            style_button(self._clear_btn, "outline")
        box.place(relx=0.5, y=90, anchor="n")
        self._overlay = box
        for w in [box] + list(box.winfo_children()):
            self._forward_events(w)
        if state == "empty":
            self._update_clear_button()

    def _update_clear_button(self):
        footer = self.footer
        try:
            active = bool(footer and footer.active_chips())
            if active:
                self._hint.configure(text="نتیجه‌ای با فیلترهای فعلی پیدا نشد.")
                self._hint.pack(pady=(2, 0))
                self._clear_btn.pack(pady=(8, 0))
            else:
                self._hint.pack_forget()
                self._clear_btn.pack_forget()
        except (tk.TclError, AttributeError):
            pass

    def _clear_filters(self):
        if self.footer is not None:
            self.footer.clear_all()

    # -- hover ----------------------------------------------------------------
    def _on_motion(self, event):
        try:
            item = self.tree.identify_row(event.y)
        except tk.TclError:
            return
        self._set_hover(item or None)

    def _set_hover(self, item):
        tree = self.tree
        if item == self._hover_item:
            return
        try:
            old = self._hover_item
            if old and tree.exists(old):
                tags = tuple(tree.item(old, "tags") or ())
                if self.ROW_HOVER in tags:
                    tree.item(old, tags=tuple(t for t in tags if t != self.ROW_HOVER))
            self._hover_item = item
            if item and tree.exists(item):
                tags = tuple(tree.item(item, "tags") or ())
                if self.ROW_HOVER not in tags:
                    tree.item(item, tags=tags + (self.ROW_HOVER,))
        except tk.TclError:
            self._hover_item = None
        self.schedule_layout()

    # -- status badges ---------------------------------------------------------
    def _wrap_scroll_commands(self):
        tree = self.tree
        for option in ("yscrollcommand", "xscrollcommand"):
            try:
                current = str(tree.cget(option) or "")
            except tk.TclError:
                continue
            if not current or current == self._wrapped_scroll.get(option):
                continue
            parts = tree.tk.splitlist(current)

            def forward(*args, _parts=parts):
                try:
                    tree.tk.call(*(tuple(_parts) + tuple(args)))
                except tk.TclError:
                    pass
                self.schedule_layout()

            name = tree.register(forward)
            try:
                tree.configure(**{option: name})
                self._wrapped_scroll[option] = name
            except tk.TclError:
                pass

    def _layout_badges(self):
        self._layout_pending = False
        tree = self.tree
        try:
            if not tree.winfo_exists():
                return
            self._wrap_scroll_commands()
            used = 0
            col = self.status_column
            if tree.winfo_ismapped():
                style = ttk.Style(tree)
                self._style_name = str(tree.cget("style") or "Treeview")
                names = tree.tk.splitlist(tree.tk.call(tree._w, "tag", "names"))
                display = tuple(tree["displaycolumns"])
                visible_col = (display in (("#all",), ()) or col in display)
                height = tree.winfo_height()
                seen = set()
                y = 1
                while visible_col and y < height:
                    item = tree.identify_row(y)
                    if item and item not in seen:
                        seen.add(item)
                        box = tree.bbox(item, col)
                        if box:
                            x0, y0, w0, h0 = box
                            text = str(tree.set(item, col) or "").strip()
                            tone = status_tone(text)
                            if tone:
                                self._place_badge(used, item, text, tone, x0, y0, w0, h0,
                                                  names, style)
                                used += 1
                            y = y0 + h0 + 1
                            continue
                    y += 6
            for cover in self._badges[used:]:
                cover.place_forget()
        except Exception as exc:
            _log("tree.badges", exc)

    def _row_background(self, item, names, style):
        tree = self.tree
        try:
            if item in tree.selection():
                return style.lookup(self._style_name, "background", ("selected",)) or ACCENT
        except tk.TclError:
            pass
        try:
            tags = set(tree.item(item, "tags") or ())
        except tk.TclError:
            tags = set()
        # `tag names` lists the newest tag first; the OLDEST tag wins.
        for tag in reversed(names):
            if tag in tags:
                try:
                    bg = str(tree.tag_configure(tag, "background") or "")
                except tk.TclError:
                    bg = ""
                if bg:
                    return bg
        return (style.lookup(self._style_name, "fieldbackground")
                or style.lookup(self._style_name, "background") or WHITE)

    def _place_badge(self, index, item, text, tone, x, y, w, h, names, style):
        """
        A cell-sized cover in the row's own colour (hides the plain text)
        holding a small coloured pill with the same text.
        """
        tree = self.tree
        while len(self._badges) <= index:
            cover = tk.Frame(tree, bd=0, highlightthickness=0, cursor="hand2")
            pill = tk.Label(cover, font=(FONT_FAMILY, 8, "bold"), padx=8, pady=0, bd=0,
                            cursor="hand2")
            cover._pill = pill
            self._forward_events(cover)
            self._forward_events(pill)
            self._badges.append(cover)
        cover = self._badges[index]
        pill = cover._pill
        bg, fg = _BADGE_COLORS.get(tone, _BADGE_COLORS["neutral"])
        pill.configure(text=text, bg=bg, fg=fg)
        cover.configure(bg=self._row_background(item, names, style))
        cover._ux_item = item
        pw = min(w - 6, pill.winfo_reqwidth() + 4)
        ph = max(16, min(h - 8, 22))
        try:
            anchor = str(tree.column(self.status_column, "anchor") or "center")
        except tk.TclError:
            anchor = "center"
        if "e" in anchor:
            px = w - pw - 4
        elif "w" in anchor:
            px = 4
        else:
            px = (w - pw) // 2
        # Stay inside the visible part of the table (left/right scrolling).
        x0 = max(0, x)
        x1 = min(tree.winfo_width() - 2, x + w)
        if x1 - x0 < 8:
            cover.place_forget()
            return
        cover.place(x=x0, y=y, width=x1 - x0, height=h)
        pill.place(x=max(1, x + px - x0), y=(h - ph) // 2, width=max(10, pw), height=ph)
        cover.lift()

    def _forward_events(self, widget):
        tree = self.tree

        def fwd(sequence):
            def handler(event):
                try:
                    tx = event.x_root - tree.winfo_rootx()
                    ty = event.y_root - tree.winfo_rooty()
                    kwargs = dict(x=tx, y=ty, rootx=event.x_root, rooty=event.y_root)
                    if sequence == "<MouseWheel>":
                        kwargs["delta"] = event.delta
                    tree.focus_set()
                    tree.event_generate(sequence, **kwargs)
                except tk.TclError:
                    pass
                return "break"
            return handler

        for seq in ("<Button-1>", "<ButtonRelease-1>", "<Double-Button-1>", "<Button-3>",
                    "<Button-2>", "<MouseWheel>", "<Button-4>", "<Button-5>"):
            try:
                widget.bind(seq, fwd(seq))
            except tk.TclError:
                pass


def enhance_tree(tree, **options):
    """Attach the shared table behaviour to ``tree`` (idempotent)."""
    if not ENABLED:
        return None
    existing = getattr(tree, "_ux", None)
    if existing is not None:
        return existing
    try:
        ux = _TreeUX(tree, **options)
        tree._ux = ux
        return ux
    except Exception as exc:
        _log("enhance_tree", exc)
        return None


# ===========================================================================
# Table footer: row counter + removable filter chips
# ===========================================================================

class TableFooter(tk.Frame):
    """
    A slim line under a table:  «۳۸ ردیف از ۹۶»   [وضعیت: باز ✕] [پاک کردن همه]

    ``filters`` is a list of (label, variable, default) and ``apply`` is the
    page's own filter/reload function, called after a chip is removed.
    ``total`` is an optional function returning the number of records
    before filtering.
    """

    def __init__(self, parent, tree, filters=(), apply=None, total=None, noun="ردیف",
                 bg=None):
        bg = bg or (parent.cget("bg") if "bg" in parent.keys() else GRAY_BG)
        super().__init__(parent, bg=bg)
        self.tree = tree
        self.filters = list(filters)
        self.apply = apply
        self.total = total
        self.noun = noun
        self._bg = bg
        self.count_label = tk.Label(self, text="", font=FONT_SMALL, bg=bg, fg=TEXT_MUTED)
        self.count_label.pack(side="right", padx=(2, 8))
        self.chips = tk.Frame(self, bg=bg)
        self.chips.pack(side="right", fill="x", expand=True)
        self._signature = None
        ux = enhance_tree(tree)
        if ux is not None:
            ux.footer = self
        for _label, var, _default in self.filters:
            try:
                var.trace_add("write", lambda *_: self.after_idle(self._render_chips))
            except Exception:
                pass
        self.update_count(len(tree.get_children("")))

    def _value(self, var):
        try:
            return str(var.get()).strip()
        except Exception:
            return ""

    def active_chips(self):
        chips = []
        for label, var, default in self.filters:
            value = self._value(var)
            defaults = default if isinstance(default, (tuple, list, set)) else (default,)
            if value and value not in {str(d) for d in defaults}:
                chips.append((label, var, defaults[0], value))
        return chips

    def update_count(self, count):
        try:
            text = f"{fa_digits(count)} {self.noun}"
            if self.total is not None:
                try:
                    total = self.total()
                except Exception:
                    total = None
                if total is not None and total != count:
                    text = f"{fa_digits(count)} از {fa_digits(total)} {self.noun}"
            self.count_label.configure(text=text)
        except tk.TclError:
            return
        self._render_chips()

    def _render_chips(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        chips = self.active_chips()
        signature = tuple((c[0], c[3]) for c in chips)
        if signature == self._signature:
            return
        self._signature = signature
        for w in self.chips.winfo_children():
            w.destroy()
        if not chips:
            return
        tk.Label(self.chips, text="فیلترها:", font=FONT_SMALL, bg=self._bg,
                 fg=TEXT_MUTED).pack(side="right", padx=(0, 6))
        for label, var, default, value in chips:
            chip = tk.Frame(self.chips, bg=ACCENT_SOFT, highlightthickness=1,
                            highlightbackground="#C7D7F5")
            chip.pack(side="right", padx=3, pady=3)
            short = value if len(value) <= 24 else value[:22] + "…"
            tk.Label(chip, text=f"{label}: {short}", font=FONT_SMALL, bg=ACCENT_SOFT,
                     fg=NAVY).pack(side="right", padx=(8, 2), pady=1)
            x = tk.Label(chip, text="✕", font=FONT_SMALL, bg=ACCENT_SOFT, fg=TEXT_MUTED,
                         cursor="hand2")
            x.pack(side="right", padx=(2, 6))
            x.bind("<Button-1>", lambda _e, v=var, d=default: self._remove(v, d))
            x.bind("<Enter>", lambda _e, w=x: w.configure(fg=DANGER))
            x.bind("<Leave>", lambda _e, w=x: w.configure(fg=TEXT_MUTED))
        if len(chips) > 1:
            link = tk.Label(self.chips, text="پاک کردن همه", font=FONT_SMALL, bg=self._bg,
                            fg=ACCENT, cursor="hand2")
            link.pack(side="right", padx=8)
            link.bind("<Button-1>", lambda _e: self.clear_all())

    def _remove(self, var, default):
        try:
            var.set(default)
        except Exception:
            pass
        self._run_apply()

    def clear_all(self):
        for _label, var, default in self.filters:
            defaults = default if isinstance(default, (tuple, list, set)) else (default,)
            try:
                var.set(list(defaults)[0])
            except Exception:
                pass
        self._run_apply()

    def _run_apply(self):
        self._signature = None
        if callable(self.apply):
            try:
                self.apply()
            except Exception as exc:
                _log("footer.apply", exc)
        self.after_idle(self._render_chips)


def attach_footer(tree, filters=(), apply=None, total=None, noun="ردیف"):
    """
    Put a TableFooter (count + filter chips) right ABOVE the table's card, so
    it is always in view, without touching the page layout: it is packed
    just before the outermost single-child wrapper of the tree.
    """
    if not ENABLED or tree is None:
        return None
    existing = getattr(tree, "_ux_footer", None)
    if existing is not None:
        return existing
    try:
        block = tree.master
        while True:
            parent = block.master
            if parent is None or block.winfo_manager() != "pack":
                break
            siblings = [w for w in parent.pack_slaves()]
            if len(siblings) > 1:
                break
            if parent.winfo_manager() != "pack":
                break
            block = parent
        if block.winfo_manager() != "pack":
            return None
        parent = block.master
        info = block.pack_info()
        if str(info.get("side", "top")) != "top":
            return None
        footer = TableFooter(parent, tree, filters, apply, total, noun)
        footer.pack(fill="x", before=block, padx=info.get("padx", 0), pady=(2, 2))
        tree._ux_footer = footer
        return footer
    except Exception as exc:
        _log("attach_footer", exc)
        return None


_TABLE_ATTRS = ("tree", "_ins_tree", "_tpl_tree", "personnel_tree", "department_tree")


def _attach_page_footers(view):
    """
    Footers for a page's main tables.  A page may describe its filters with
    ``ux_footer_spec()`` -> {"filters": [(label, var, default)], "apply": fn,
    "total": fn, "noun": "..."}; without it the footer just counts rows.
    """
    spec = {}
    getter = getattr(view, "ux_footer_spec", None)
    if callable(getter):
        try:
            spec = getter() or {}
        except Exception as exc:
            _log("footer_spec", exc)
            spec = {}
    main = None
    for attr in _TABLE_ATTRS:
        tree = getattr(view, attr, None)
        if not isinstance(tree, ttk.Treeview):
            continue
        if main is None:
            main = attr          # the page-level spec belongs to the main table
            local = spec
        else:
            local = spec.get(attr) or {}
        attach_footer(tree, filters=local.get("filters", ()), apply=local.get("apply"),
                      total=local.get("total"), noun=local.get("noun", "ردیف"))


# ===========================================================================
# Inline form errors
# ===========================================================================

def _mark_widget(widget):
    """Red outline on the field itself; returns a function that undoes it."""
    cls = widget.winfo_class()
    if cls in ("TEntry", "TCombobox", "TSpinbox"):
        style = ttk.Style(widget)
        old = str(widget.cget("style") or "")
        base = old or cls
        name = "UxError." + base
        try:
            style.configure(name, bordercolor=DANGER, lightcolor=DANGER, darkcolor=DANGER)
            style.map(name, bordercolor=[("focus", DANGER)], lightcolor=[("focus", DANGER)],
                      darkcolor=[("focus", DANGER)])
            widget.configure(style=name)
            return lambda: widget.configure(style=old)
        except tk.TclError:
            return None
    if cls in ("Entry", "Text", "Listbox", "Spinbox", "Canvas"):
        keys = ("highlightthickness", "highlightbackground", "highlightcolor")
        try:
            old = {k: widget.cget(k) for k in keys}
            widget.configure(highlightthickness=2, highlightbackground=DANGER,
                             highlightcolor=DANGER)
            return lambda: widget.configure(**old)
        except tk.TclError:
            return None
    return None


def field_error(widget, message, focus=True):
    """
    Mark ``widget`` as wrong and show ``message`` right under it.  The mark
    disappears as soon as the user changes the field.  Returns False so a
    validator can ``return field_error(...)``.
    """
    if not ENABLED or widget is None:
        from tkinter import messagebox
        messagebox.showwarning("خطای ورودی", message,
                               parent=widget.winfo_toplevel() if widget is not None else None)
        return False
    try:
        clear_field_error(widget)
        widget.update_idletasks()
        marks = []
        undo = _mark_widget(widget)
        if undo is None:
            # composite field (e.g. a date picker): a red frame behind it
            ring = tk.Frame(widget.master, bg=DANGER, bd=0, highlightthickness=0)
            ring.place(in_=widget, x=-2, y=-2, relwidth=1, relheight=1, width=4, height=4)
            ring.lower(widget)
            marks.append(ring)

        # The note goes in the nearest ancestor with room BELOW the field
        # (fields are often wrapped in a frame of exactly their own size).
        holder = widget.master
        bottom_needed = 18
        for _ in range(6):
            try:
                below = (holder.winfo_rooty() + holder.winfo_height()) - \
                        (widget.winfo_rooty() + widget.winfo_height())
                if below >= bottom_needed or isinstance(holder, (tk.Toplevel, tk.Tk)) \
                        or holder.master is None:
                    break
            except tk.TclError:
                break
            holder = holder.master
        try:
            wrap = max(220, widget.winfo_width())
        except tk.TclError:
            wrap = 260
        msg = tk.Label(holder, text="⚠ " + str(message), font=FONT_SMALL, bg=DANGER_SOFT,
                       fg="#B91C1C", padx=6, pady=1, anchor="e", justify="right",
                       wraplength=wrap)
        msg.place(in_=widget, relx=1.0, rely=1.0, x=0, y=2, anchor="ne")
        msg.lift()
        marks.append(msg)
        widget._ux_error = (marks, undo)

        def _clear(_e=None, w=widget):
            clear_field_error(w)

        if not getattr(widget, "_ux_error_bound", False):
            for target in [widget] + list(_walk(widget)):
                for seq in ("<Key>", "<<ComboboxSelected>>", "<Button-1>"):
                    try:
                        target.bind(seq, _clear, add="+")
                    except tk.TclError:
                        pass
            widget._ux_error_bound = True
        msg.bind("<Button-1>", _clear)
        if focus:
            try:
                widget.focus_set()
            except tk.TclError:
                pass
        try:
            widget.winfo_toplevel().bell()
        except tk.TclError:
            pass
    except Exception as exc:
        _log("field_error", exc)
        from tkinter import messagebox
        messagebox.showwarning("خطای ورودی", message, parent=widget.winfo_toplevel())
    return False


def clear_field_error(widget):
    state = getattr(widget, "_ux_error", None)
    if not state:
        return
    marks, undo = state
    widget._ux_error = None
    for m in marks:
        try:
            m.destroy()
        except tk.TclError:
            pass
    if undo is not None:
        try:
            undo()
        except tk.TclError:
            pass


def clear_all_field_errors(container):
    for w in [container] + list(_walk(container)):
        if getattr(w, "_ux_error", None):
            clear_field_error(w)
