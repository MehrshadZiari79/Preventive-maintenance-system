"""
Keep every window inside the visible screen.

Many dialogs ask for a fixed size (for example 850x800).  On a laptop with a
1366x768 screen (or 125 % Windows scaling) the bottom of such a dialog, where
the «ذخیره» button is, ended up below the taskbar.  This module wraps
Tk's ``wm geometry`` and ``wm minsize`` once, at start-up, so that:

* a requested size is reduced to the usable screen area (taskbar excluded);
* a requested position is moved so the whole window is visible;
* a minimum size never exceeds the screen.

Larger screens are unaffected: sizes that already fit are passed through
unchanged.  Windows that are not given a size are left alone.
"""

import re
import sys
import tkinter as tk

_GEOMETRY = re.compile(r"^\s*(?:(\d+)x(\d+))?(?:([+-])(-?\d+)([+-])(-?\d+))?\s*$")
_MARGIN_W = 16          # keep a few pixels for the window frame
_MARGIN_H = 48          # title bar
_patched = False


def work_area(widget, x=None, y=None):
    """
    (left, top, width, height) of the usable area (taskbar excluded) of the
    monitor that contains point (x, y) - or the widget's parent window when
    no point is given - so dual-monitor setups keep working.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                            ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

            if x is None or y is None:
                try:
                    ref = widget.master if getattr(widget, "master", None) is not None else widget
                    x = ref.winfo_rootx() + max(1, ref.winfo_width()) // 2
                    y = ref.winfo_rooty() + max(1, ref.winfo_height()) // 2
                except Exception:
                    x, y = 0, 0
            user32 = ctypes.windll.user32
            user32.MonitorFromPoint.restype = wintypes.HANDLE
            user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
            monitor = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)  # NEAREST
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                r = info.rcWork
                if r.right > r.left and r.bottom > r.top:
                    return r.left, r.top, r.right - r.left, r.bottom - r.top
        except Exception:
            pass
    try:
        return 0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight() - 40
    except Exception:
        return 0, 0, 1366, 728


def _fit(widget, spec):
    m = _GEOMETRY.match(str(spec))
    if not m:
        return spec
    w, h, sx, x, sy, y = m.groups()
    if sx == "+" and sy == "+":
        left, top, aw, ah = work_area(widget, int(x), int(y))
    else:
        left, top, aw, ah = work_area(widget)
    max_w = max(200, aw - _MARGIN_W)
    max_h = max(200, ah - _MARGIN_H)
    out = ""
    if w and h:
        w, h = min(int(w), max_w), min(int(h), max_h)
        out = f"{w}x{h}"
    if sx and sy:
        x, y = int(x), int(y)
        if sx == "+" and sy == "+":
            if not (w and h):
                try:
                    widget.update_idletasks()
                    w = min(widget.winfo_reqwidth(), max_w)
                    h = min(widget.winfo_reqheight(), max_h)
                except Exception:
                    w = h = 0
            x = max(left, min(x, left + aw - int(w or 0) - _MARGIN_W // 2))
            y = max(top, min(y, top + ah - int(h or 0) - _MARGIN_H))
            out += f"+{x}+{y}"
        else:
            out += f"{sx}{x}{sy}{y}"
    return out or spec


def install():
    """Patch tk.Wm once.  Safe to call more than once."""
    global _patched
    if _patched:
        return
    original_geometry = tk.Wm.wm_geometry
    original_minsize = tk.Wm.wm_minsize

    def wm_geometry(self, newGeometry=None):
        if newGeometry:
            try:
                newGeometry = _fit(self, newGeometry)
            except Exception:
                pass
        return original_geometry(self, newGeometry)

    def wm_minsize(self, width=None, height=None):
        if width is not None and height is not None:
            try:
                _l, _t, aw, ah = work_area(self)
                width = min(int(width), max(200, aw - _MARGIN_W))
                height = min(int(height), max(200, ah - _MARGIN_H))
            except Exception:
                pass
        return original_minsize(self, width, height)

    tk.Wm.wm_geometry = tk.Wm.geometry = wm_geometry
    tk.Wm.wm_minsize = tk.Wm.minsize = wm_minsize
    _patched = True
