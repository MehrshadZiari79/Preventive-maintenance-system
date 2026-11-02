# views/ui_kit.py
"""
Small shared building blocks for a consistent Persian RTL look.

Everything here uses classic tk / ttk widgets only.  No text-entry widget is
created or modified here, so Persian typing behaviour is untouched.
"""

from __future__ import annotations

import tkinter as tk

from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, TEXT_DARK, TEXT_MUTED, BORDER, ACCENT,
    ACCENT_SOFT, SURFACE_ALT, SUCCESS, SUCCESS_SOFT, WARNING, WARNING_SOFT,
    DANGER, DANGER_SOFT, INFO, INFO_SOFT, FONT_TITLE,
    FONT_HEADING, FONT_NORMAL, FONT_BOLD, FONT_SMALL, FONT_METRIC,
)

_BUTTON_KINDS = {
    #            bg            fg        hover_bg     hover_fg
    "primary":   (NAVY,        WHITE,    NAVY_LIGHT,  WHITE),
    "accent":    (ACCENT,      WHITE,    "#1D4ED8",   WHITE),
    "success":   (SUCCESS,     WHITE,    "#15803D",   WHITE),
    "secondary": ("#EEF1F5",   TEXT_DARK, "#E2E7EE",  TEXT_DARK),
    "danger":    (DANGER_SOFT, DANGER,   "#FAD4D4",   "#B91C1C"),
    "ghost":     (WHITE,       NAVY,     ACCENT_SOFT, NAVY),
    "on_dark":   ("#2A3C5E",   WHITE,    "#36507C",   WHITE),
}

TONES = {
    "neutral": (SURFACE_ALT, TEXT_MUTED),
    "info":    (INFO_SOFT, INFO),
    "success": (SUCCESS_SOFT, SUCCESS),
    "warning": (WARNING_SOFT, WARNING),
    "danger":  (DANGER_SOFT, DANGER),
    "accent":  (ACCENT_SOFT, ACCENT),
}


def button(parent, text, command, kind="primary", width=None, font=FONT_NORMAL, **pack):
    """Flat button with hover feedback. Returns the tk.Button (not packed)."""
    bg, fg, hbg, hfg = _BUTTON_KINDS.get(kind, _BUTTON_KINDS["primary"])
    btn = tk.Button(
        parent, text=text, command=command, font=font,
        bg=bg, fg=fg, activebackground=hbg, activeforeground=hfg,
        relief="flat", bd=0, highlightthickness=0, cursor="hand2",
        padx=14, pady=6,
    )
    if width:
        btn.configure(width=width)
    btn._kind_colors = (bg, fg, hbg, hfg)

    def _enter(_e):
        if str(btn.cget("state")) != "disabled":
            btn.configure(bg=hbg, fg=hfg)

    def _leave(_e):
        if str(btn.cget("state")) != "disabled":
            btn.configure(bg=bg, fg=fg)

    btn.bind("<Enter>", _enter)
    btn.bind("<Leave>", _leave)
    return btn


def card(parent, bg=WHITE, padx=16, pady=14, **pack_opts):
    """
    White card with a 1px border. Returns (outer, inner). ``outer`` is packed
    with ``pack_opts`` if any are given; ``inner`` is where content goes.
    """
    outer = tk.Frame(parent, bg=BORDER, bd=0, highlightthickness=0)
    inner = tk.Frame(outer, bg=bg, bd=0, highlightthickness=0, padx=padx, pady=pady)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    if pack_opts:
        outer.pack(**pack_opts)
    return outer, inner


def page_header(parent, icon, title, subtitle="", bg=NAVY):
    """
    Standard page banner used across the app (navy, full width): icon +
    title on the right (RTL), an empty ``actions`` frame on the left that the
    caller fills with buttons.
    """
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x", pady=(0, 14))
    inner = tk.Frame(row, bg=bg, padx=20, pady=14)
    inner.pack(fill="x")

    tk.Label(inner, text=icon, font=("Segoe UI Symbol", 18), bg=bg, fg=WHITE).pack(side="right")

    col = tk.Frame(inner, bg=bg)
    col.pack(side="right", padx=(0, 10))
    tk.Label(col, text=title, font=FONT_TITLE, bg=bg, fg=WHITE, anchor="e").pack(anchor="e")
    if subtitle:
        tk.Label(col, text=subtitle, font=FONT_SMALL, bg=bg, fg="#C9D6EA", anchor="e").pack(anchor="e", pady=(2, 0))

    actions = tk.Frame(inner, bg=bg)
    actions.pack(side="left")
    return actions


def pill(parent, textvariable=None, text="", tone="neutral", bg=None):
    """Small rounded-looking status label."""
    tbg, tfg = TONES.get(tone, TONES["neutral"])
    lbl = tk.Label(parent, text=text, textvariable=textvariable, font=FONT_BOLD if tone != "neutral" else FONT_SMALL,
                   bg=tbg, fg=tfg, padx=10, pady=3)
    return lbl


def set_pill_tone(lbl, tone):
    tbg, tfg = TONES.get(tone, TONES["neutral"])
    try:
        lbl.configure(bg=tbg, fg=tfg)
    except tk.TclError:
        pass


class MetricCard(tk.Frame):
    """KPI tile: coloured stripe on the right, caption, big value, hint line."""

    def __init__(self, parent, title, icon="", tone="accent"):
        super().__init__(parent, bg=BORDER, bd=0, highlightthickness=0)
        body = tk.Frame(self, bg=WHITE)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        self._stripe = tk.Frame(body, bg=TONES[tone][1], width=4)
        self._stripe.pack(side="right", fill="y")

        content = tk.Frame(body, bg=WHITE, padx=14, pady=10)
        content.pack(side="right", fill="both", expand=True)

        top = tk.Frame(content, bg=WHITE)
        top.pack(fill="x")
        tk.Label(top, text=title, font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED, anchor="e").pack(side="right")
        if icon:
            tk.Label(top, text=icon, font=("Segoe UI Symbol", 11), bg=WHITE,
                     fg=TONES[tone][1]).pack(side="left")

        self.value = tk.Label(content, text="—", font=FONT_METRIC, bg=WHITE, fg=TEXT_DARK, anchor="e")
        self.value.pack(fill="x", pady=(4, 0))
        self.hint = tk.Label(content, text="", font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED, anchor="e")
        self.hint.pack(fill="x")

    def set(self, value, hint="", tone=None, value_fg=None):
        self.value.configure(text=value, fg=value_fg or TEXT_DARK)
        self.hint.configure(text=hint)
        if tone:
            self._stripe.configure(bg=TONES.get(tone, TONES["accent"])[1])


class Toast(tk.Toplevel):
    """
    Non-blocking notification in the bottom-left corner of the parent window
    (bottom-left = "end" side in RTL, away from the sidebar).  Never steals
    keyboard focus, so it cannot interrupt typing in a form.
    """

    _active = []

    def __init__(self, parent, title, lines=(), tone="warning", action_text=None,
                 action=None, timeout_ms=15000):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        accent = TONES.get(tone, TONES["warning"])[1]
        frame = tk.Frame(self, bg=accent)
        frame.pack(fill="both", expand=True)
        body = tk.Frame(frame, bg=WHITE, padx=14, pady=12)
        body.pack(fill="both", expand=True, padx=(1, 5), pady=1)

        head = tk.Frame(body, bg=WHITE)
        head.pack(fill="x")
        tk.Label(head, text=title, font=FONT_HEADING, bg=WHITE, fg=TEXT_DARK, anchor="e").pack(side="right")
        close = tk.Label(head, text="✕", font=FONT_NORMAL, bg=WHITE, fg=TEXT_MUTED, cursor="hand2")
        close.pack(side="left")
        close.bind("<Button-1>", lambda _e: self.close())

        for line in lines:
            tk.Label(body, text=line, font=FONT_NORMAL, bg=WHITE, fg=TEXT_DARK, anchor="e",
                     justify="right", wraplength=330).pack(fill="x", pady=(4, 0))

        if action_text and action:
            def _run():
                self.close()
                action()
            button(body, action_text, _run, kind="primary").pack(anchor="w", pady=(10, 0))

        self.update_idletasks()
        self._place(parent)
        self.deiconify()
        Toast._active.append(self)
        if timeout_ms:
            self.after(timeout_ms, self.close)

    def _place(self, parent):
        try:
            root = parent.winfo_toplevel()
            w = max(360, self.winfo_reqwidth())
            h = self.winfo_reqheight()
            x = root.winfo_rootx() + 24
            y = root.winfo_rooty() + root.winfo_height() - h - 24
            if root.winfo_height() < 100:
                x, y = 24, self.winfo_screenheight() - h - 70
            offset = sum(t.winfo_reqheight() + 10 for t in Toast._active if t.winfo_exists())
            self.geometry(f"{w}x{h}+{x}+{max(0, y - offset)}")
        except tk.TclError:
            pass

    def close(self):
        try:
            if self in Toast._active:
                Toast._active.remove(self)
            self.destroy()
        except tk.TclError:
            pass

    @classmethod
    def close_all(cls):
        for t in list(cls._active):
            t.close()


def center_window(win, width, height, parent=None):
    """Center on the monitor that shows the app, never larger than its work area."""
    win.update_idletasks()
    try:
        from utils.screen_fit import work_area
        left, top, sw, sh = work_area(parent or win)
    except Exception:
        left, top, sw, sh = 0, 0, win.winfo_screenwidth(), win.winfo_screenheight() - 40
    width, height = min(width, sw - 16), min(height, sh - 48)
    x = left + max(0, (sw - width) // 2)
    y = top + max(0, (sh - height) // 2 - 10)
    win.geometry(f"{width}x{height}+{x}+{y}")


class busy:
    """`with busy(widget):` shows the wait cursor during a long operation."""

    def __init__(self, widget):
        self.top = widget.winfo_toplevel()

    def __enter__(self):
        try:
            self.top.configure(cursor="watch")
            self.top.update_idletasks()
        except tk.TclError:
            pass
        return self

    def __exit__(self, *exc):
        try:
            self.top.configure(cursor="")
        except tk.TclError:
            pass
        return False


def rtl_columns(tree):
    """
    Show a heading-only ttk.Treeview right-to-left: the FIRST logical column
    (usually شناسه / #) appears at the RIGHT edge.

    Display-only: values, iids, tree.set(item, column) and every column name
    stay exactly the same, so no data code is affected.
    """
    try:
        cols = tuple(tree["columns"])
        if cols:
            tree["displaycolumns"] = tuple(reversed(cols))
            # Wide tables: start scrolled to the RIGHT end (where column 1 is).
            def _to_right(_event=None):
                tree.after(80, lambda: tree.winfo_exists() and tree.xview_moveto(1.0))
            tree.bind("<Map>", _to_right, add="+")
            _to_right()
    except Exception:
        pass
    return tree

def cancel_pending_afters(root):
    """
    Cancel every pending Tk ``after`` timer of this window's interpreter.

    Called when a root window closes: otherwise timers that are still queued
    (live clocks, notices, update watcher) fire after the window is gone and
    Tk prints "invalid command name ..._tick_..." to the console.

    Only the Tcl timer is cancelled.  root.after_cancel() would also delete the
    callback's Tcl command through the ROOT, while the widget that created the
    timer (e.g. the dashboard's pending render) still lists it; that widget's
    own destroy then failed with "can't delete Tcl command" and the main window
    stayed on screen, empty, behind the login window after «خروج از سیستم».
    The commands are removed normally when their widgets are destroyed.
    """
    try:
        for after_id in root.tk.splitlist(root.tk.call("after", "info")):
            try:
                root.tk.call("after", "cancel", after_id)
            except Exception:
                pass
    except Exception:
        pass


def reflow_grid(frame, min_width=180):
    """
    Make an existing grid of cards responsive.

    The cards keep their reading order (right to left, top to bottom); the
    number of columns follows the frame width, never more than the original
    layout used.  Call once after the cards were gridded.
    """
    items = []
    for child in frame.grid_slaves():
        info = child.grid_info()
        items.append((int(info.get("row", 0)), -int(info.get("column", 0)), child, info))
    if not items:
        return
    items.sort(key=lambda t: (t[0], t[1]))
    max_cols = max(1, max(-t[1] for t in items) + 1)
    widgets = [(t[2], t[3]) for t in items]
    state = {"cols": max_cols}

    def apply(cols):
        for c in range(max_cols):
            frame.columnconfigure(c, weight=1 if c < cols else 0, uniform="reflow" if c < cols else "")
        for i, (w, info) in enumerate(widgets):
            w.grid_configure(row=i // cols, column=cols - 1 - (i % cols))

    def on_configure(event):
        cols = max(1, min(max_cols, event.width // max(1, min_width)))
        if cols != state["cols"]:
            state["cols"] = cols
            apply(cols)

    frame.bind("<Configure>", on_configure, add="+")
    try:
        width = frame.winfo_width()
        if width > 1:
            cols = max(1, min(max_cols, width // min_width))
            if cols != max_cols:
                state["cols"] = cols
                apply(cols)
    except Exception:
        pass

