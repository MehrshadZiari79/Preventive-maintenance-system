"""
Gela PM System - native Persian/Unicode BiDi editing for Windows Tkinter.

WHY THIS REPLACES THE PREVIOUS RTL PATCH
----------------------------------------
Tk 8.6 (the Tk build shipped with the current application) does not provide
full native bidirectional editing for Arabic/Persian + embedded English text.
Changing ``justify`` only changes alignment; reversing characters or replacing
text with python-bidi visual-order strings breaks cursor/editing semantics.

The reliable Windows solution for this application is to use Microsoft's
Rich Edit control as the actual editor. Rich Edit supports Unicode
bidirectional text, mixed RTL/LTR runs, real cursor movement, selection,
copy/paste, undo/redo and native paragraph directionality.

The application still stores and receives NORMAL logical Unicode text. No bidi
control characters and no visual-order strings are written to the database.

The patch is intentionally global and must run before any views are imported:

    from utils.rtl_patch import apply_rtl_patch
    apply_rtl_patch()

On Windows, tk.Entry / ttk.Entry / tk.Text are replaced with small Tk Frame
adapters containing a native Rich Edit control. On non-Windows systems the
module safely falls back to ordinary Tk right-alignment.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import tkinter as tk
from tkinter import ttk
from typing import Any


_FONT = ("Tahoma", 10)
_PATCHED = False
_NATIVE_AVAILABLE = sys.platform.startswith("win")
_RICHEDIT_LOADED = False
_RICHEDIT_HMODULE = None


# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------

WM_SETFONT = 0x0030
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
WM_SETREDRAW = 0x000B
WM_SETFOCUS = 0x0007
WM_GETFONT = 0x0031
WM_NCHITTEST = 0x0084
WM_MOUSEACTIVATE = 0x0021

EM_SETSEL = 0x00B1
EM_GETSEL = 0x00B0
EM_REPLACESEL = 0x00C2
EM_SETREADONLY = 0x00CF
EM_EXSETSEL = 0x0437
EM_GETPARAFORMAT = 0x043D
EM_SETPARAFORMAT = 0x0447
EM_SETBIDIOPTIONS = 0x04C8
EM_GETBIDIOPTIONS = 0x04C9
EM_SCROLLCARET = 0x00B7
EM_LINESCROLL = 0x00B6
EM_SETLIMITTEXT = 0x00C5
EM_SETBKGNDCOLOR = 0x0443
EM_GETMODIFY = 0x00B8
EM_SETMODIFY = 0x00B9
WM_CLEAR = 0x0303

# Rich Edit paragraph flags / masks.
PFM_ALIGNMENT = 0x00000008
PFM_RTLPARA = 0x00010000
PFA_LEFT = 0x0001
PFA_RIGHT = 0x0002
PFE_RTLPARA = 0x0001

# BIDIOPTIONS masks/effects used by modern Rich Edit.
# These values are from richedit.h.
BOM_CONTEXTALIGNMENT = 0x0040
BOM_CONTEXTREADING = 0x0080
BOM_UNICODEBIDI = 0x0200
BOM_DEFPARADIR = 0x0001

BOE_CONTEXTALIGNMENT = 0x0040
BOE_CONTEXTREADING = 0x0080
BOE_UNICODEBIDI = 0x0200
BOE_RTLDIR = 0x0001

# Window styles.
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_TABSTOP = 0x00010000
WS_BORDER = 0x00800000
WS_VSCROLL = 0x00200000
WS_HSCROLL = 0x00100000
ES_MULTILINE = 0x0004
ES_AUTOVSCROLL = 0x0040
ES_AUTOHSCROLL = 0x0080
ES_WANTRETURN = 0x1000
ES_NOHIDESEL = 0x0100
ES_PASSWORD = 0x0020
ES_READONLY = 0x0800
ES_LEFT = 0x0000
ES_RIGHT = 0x0002

ESB_DISABLE_BOTH = 0x0003

COLOR_WINDOW = 5
SW_HIDE = 0
SW_SHOW = 5

GA_PARENT = 1

# COLORREF helper.
def _rgb(r: int, g: int, b: int) -> int:
    return r | (g << 8) | (b << 16)


class _BIDIOPTIONS(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("wMask", wintypes.WORD),
        ("wEffects", wintypes.WORD),
    ]


class _PARAFORMAT(ctypes.Structure):
    # PARAFORMAT / PARAFORMAT2 prefix sufficient for EM_SETPARAFORMAT.
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwMask", wintypes.DWORD),
        ("wNumbering", wintypes.WORD),
        ("wEffects", wintypes.WORD),
        ("dxStartIndent", wintypes.LONG),
        ("dxRightIndent", wintypes.LONG),
        ("dxOffset", wintypes.LONG),
        ("wAlignment", wintypes.WORD),
        ("cTabCount", wintypes.SHORT),
        ("rgxTabs", wintypes.LONG * 32),
        ("dySpaceBefore", wintypes.LONG),
        ("dySpaceAfter", wintypes.LONG),
        ("dyLineSpacing", wintypes.LONG),
        ("sStyle", wintypes.SHORT),
        ("bLineSpacingRule", wintypes.BYTE),
        ("bOutlineLevel", wintypes.BYTE),
        ("wShadingWeight", wintypes.WORD),
        ("wShadingStyle", wintypes.WORD),
        ("wNumberingStart", wintypes.WORD),
        ("wNumberingStyle", wintypes.WORD),
        ("wNumberingTab", wintypes.WORD),
        ("wBorderSpace", wintypes.WORD),
        ("wBorderWidth", wintypes.WORD),
        ("wBorders", wintypes.WORD),
    ]


if _NATIVE_AVAILABLE:
    _EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _USER32 = ctypes.WinDLL("user32", use_last_error=True)
    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _GDI32 = ctypes.WinDLL("gdi32", use_last_error=True)

    _USER32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.DWORD, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU,
        wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    _USER32.CreateWindowExW.restype = wintypes.HWND
    _USER32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    _USER32.MoveWindow.restype = wintypes.BOOL
    _USER32.DestroyWindow.argtypes = [wintypes.HWND]
    _USER32.DestroyWindow.restype = wintypes.BOOL
    _USER32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _USER32.ShowWindow.restype = wintypes.BOOL
    _USER32.SetFocus.argtypes = [wintypes.HWND]
    _USER32.SetFocus.restype = wintypes.HWND
    # SendMessageW carries pointer-sized WPARAM/LPARAM values.  On the
    # 64-bit Python used by the application, leaving argtypes unset makes
    # ctypes default them to 32-bit C ints, which truncates RichEdit pointers
    # and raises: ``OverflowError: int too long to convert``.
    _USER32.SendMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    _USER32.SendMessageW.restype = ctypes.c_ssize_t
    _USER32.GetClientRect.restype = wintypes.BOOL
    _USER32.GetWindowRect.restype = wintypes.BOOL
    _USER32.GetSysColor.restype = wintypes.DWORD

    _KERNEL32.LoadLibraryW.argtypes = [wintypes.LPCWSTR]
    _KERNEL32.LoadLibraryW.restype = wintypes.HMODULE

    _GDI32.CreateFontW.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, wintypes.BYTE, wintypes.BYTE, wintypes.BYTE,
        wintypes.BYTE, wintypes.BYTE, wintypes.BYTE, wintypes.BYTE,
        wintypes.BYTE, wintypes.LPCWSTR,
    ]
    _GDI32.CreateFontW.restype = wintypes.HFONT
    _GDI32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    _GDI32.DeleteObject.restype = wintypes.BOOL

    _USER32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    _USER32.GetWindowLongPtrW.restype = wintypes.LPARAM
    _USER32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LPARAM]
    _USER32.SetWindowLongPtrW.restype = wintypes.LPARAM
    _USER32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    _USER32.GetWindowLongW.restype = wintypes.LONG
    _USER32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    _USER32.SetWindowLongW.restype = wintypes.LONG
    _USER32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _USER32.GetClassNameW.restype = ctypes.c_int
    _USER32.EnumChildWindows.argtypes = [wintypes.HWND, _EnumChildProc, wintypes.LPARAM]
    _USER32.EnumChildWindows.restype = wintypes.BOOL
    _USER32.InvalidateRect.argtypes = [wintypes.HWND, wintypes.LPVOID, wintypes.BOOL]
    _USER32.UpdateWindow.argtypes = [wintypes.HWND]


# ---------------------------------------------------------------------------
# Tk helpers / fallbacks
# ---------------------------------------------------------------------------


def apply_rtl_patch() -> None:
    """Install safe Persian/BiDi behavior without rewriting user text."""
    global _PATCHED
    if _PATCHED:
        return

    if _NATIVE_AVAILABLE:
        # Keep the real Tk Entry/ttk.Entry/Combobox classes. We only change the
        # underlying Windows edit-control direction flags, preserving every Tk
        # binding, StringVar, selection and validation behavior already used by
        # the application.
        _patch_tk_entry_native_style()
        _patch_ttk_entry_native_style()
        _patch_ttk_combobox_native_style()
        _ensure_richedit_loaded()
        # tk.Text is the one widget in Tk 8.6 that does not use the Windows EDIT
        # control. Replace it with the native RichEdit adapter so multiline
        # Persian + English editing also uses the Windows BiDi engine.
        tk.Text = GelaRTLTextEdit
    else:
        _patch_tk_entry_fallback()
        _patch_ttk_entry_fallback()
        _patch_tk_text_fallback()

    _PATCHED = True


def mark_ltr(widget: tk.Widget) -> None:
    """Make an existing Gela editor paragraph LTR."""
    adapter = getattr(widget, "_gela_rtl_editor", None)
    if adapter is not None:
        adapter.set_rtl(False)
        return
    try:
        widget.configure(justify="left")
    except Exception:
        pass


def mark_rtl(widget: tk.Widget) -> None:
    """Make an existing Gela editor paragraph RTL."""
    adapter = getattr(widget, "_gela_rtl_editor", None)
    if adapter is not None:
        adapter.set_rtl(True)
        return
    try:
        widget.configure(justify="right")
    except Exception:
        pass


def configure_rtl(widget: tk.Widget) -> tk.Widget:
    mark_rtl(widget)
    return widget


def configure_ltr(widget: tk.Widget) -> tk.Widget:
    mark_ltr(widget)
    return widget


def is_rtl_widget(widget: tk.Widget) -> bool:
    adapter = getattr(widget, "_gela_rtl_editor", None)
    if adapter is not None:
        return adapter.rtl
    return True


def _rtl_populate(widget: tk.Widget, text: str) -> None:
    value = "" if text is None else str(text)
    adapter = getattr(widget, "_gela_rtl_editor", None)
    if adapter is not None:
        adapter.set_text(value, cursor_to_end=True)
        return
    try:
        widget.delete(0, tk.END)
        widget.insert(0, value)
    except Exception:
        try:
            widget.delete("1.0", tk.END)
            widget.insert("1.0", value)
        except Exception:
            pass


def set_rtl_text(widget: tk.Widget, text: str) -> None:
    _rtl_populate(widget, text)


# ---------------------------------------------------------------------------
# Windows EDIT/ComboBox direction support
# ---------------------------------------------------------------------------

_WS_EX_RIGHT = 0x00001000
_WS_EX_RTLREADING = 0x00002000
_GWL_EXSTYLE = -20
_GWL_STYLE = -16
_ES_RIGHT = 0x0002
_ESPASSWORD = 0x0020


def _get_long(hwnd, index):
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        return _USER32.GetWindowLongPtrW(hwnd, index)
    return _USER32.GetWindowLongW(hwnd, index)


def _set_long(hwnd, index, value):
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        return _USER32.SetWindowLongPtrW(hwnd, index, value)
    return _USER32.SetWindowLongW(hwnd, index, value)


def _class_name(hwnd):
    buf = ctypes.create_unicode_buffer(128)
    try:
        _USER32.GetClassNameW(hwnd, buf, len(buf))
        return buf.value
    except Exception:
        return ""


def _set_native_edit_direction(hwnd: int, rtl: bool):
    """Use the real Windows EDIT control's Unicode BiDi support."""
    try:
        ex = int(_get_long(hwnd, _GWL_EXSTYLE))
        style = int(_get_long(hwnd, _GWL_STYLE))
        if rtl:
            ex |= _WS_EX_RIGHT | _WS_EX_RTLREADING
            style |= _ES_RIGHT
        else:
            ex &= ~(_WS_EX_RIGHT | _WS_EX_RTLREADING)
            style &= ~_ES_RIGHT
        _set_long(hwnd, _GWL_EXSTYLE, ex)
        _set_long(hwnd, _GWL_STYLE, style)
        _USER32.InvalidateRect(hwnd, None, True)
        _USER32.UpdateWindow(hwnd)
    except Exception:
        pass


def _enum_child_hwnds(hwnd: int):
    if not _NATIVE_AVAILABLE:
        return []
    result = []
    CALLBACK = _EnumChildProc

    def _cb(child, _lparam):
        result.append(int(child))
        # Recurse because Ttk composites can place their Edit child below a
        # theme/container window.
        result.extend(_enum_child_hwnds(int(child)))
        return True

    callback = CALLBACK(_cb)
    try:
        _USER32.EnumChildWindows(wintypes.HWND(hwnd), callback, 0)
    except Exception:
        pass
    return result


def _find_edit_descendants(widget: tk.Widget):
    try:
        root_hwnd = int(widget.winfo_id())
    except Exception:
        return []
    handles = [root_hwnd] + _enum_child_hwnds(root_hwnd)
    edits = []
    for hwnd in handles:
        name = _class_name(hwnd).lower()
        if name == "edit" or "richedit" in name:
            edits.append(hwnd)
    return edits


def _apply_native_rtl_to_widget(widget: tk.Widget, rtl: bool = True):
    for hwnd in _find_edit_descendants(widget):
        _set_native_edit_direction(hwnd, rtl)


def _schedule_native_rtl(widget: tk.Widget):
    try:
        widget.after_idle(lambda: _apply_native_rtl_to_widget(widget, True))
    except Exception:
        pass


def _patch_tk_entry_native_style():
    original = tk.Entry.__init__
    if getattr(tk.Entry.__init__, "_gela_native_rtl", False):
        return

    def _init(self, master=None, *args, **kwargs):
        original(self, master, *args, **kwargs)
        _schedule_native_rtl(self)

    _init._gela_native_rtl = True
    tk.Entry.__init__ = _init


def _patch_ttk_entry_native_style():
    original = ttk.Entry.__init__
    if getattr(ttk.Entry.__init__, "_gela_native_rtl", False):
        return

    def _init(self, master=None, *args, **kwargs):
        original(self, master, *args, **kwargs)
        _schedule_native_rtl(self)

    _init._gela_native_rtl = True
    ttk.Entry.__init__ = _init


def _patch_ttk_combobox_native_style():
    original = ttk.Combobox.__init__
    if getattr(ttk.Combobox.__init__, "_gela_native_rtl", False):
        return

    def _init(self, master=None, *args, **kwargs):
        original(self, master, *args, **kwargs)
        # Only the editable child is affected. Readonly dropdown semantics are
        # unchanged; the dropdown list itself remains Tk/Ttk's normal control.
        _schedule_native_rtl(self)

    _init._gela_native_rtl = True
    ttk.Combobox.__init__ = _init


# ---------------------------------------------------------------------------
# Windows Rich Edit helpers
# ---------------------------------------------------------------------------


def _ensure_richedit_loaded() -> None:
    global _RICHEDIT_LOADED, _RICHEDIT_HMODULE
    if not _NATIVE_AVAILABLE or _RICHEDIT_LOADED:
        return
    _RICHEDIT_HMODULE = _KERNEL32.LoadLibraryW("Msftedit.dll")
    if not _RICHEDIT_HMODULE:
        raise OSError("Msftedit.dll could not be loaded.")
    _RICHEDIT_LOADED = True


def _send(hwnd, msg, wparam=0, lparam=0):
    """Call SendMessageW with pointer-sized parameters safely.

    RichEdit messages frequently pass pointers through LPARAM/WPARAM (for
    example EM_SETBIDIOPTIONS, EM_SETPARAFORMAT and EM_GETSEL).  Explicitly
    coercing them to the Win32 pointer-sized types prevents 64-bit values from
    being truncated or rejected by ctypes.
    """
    return _USER32.SendMessageW(
        wintypes.HWND(int(hwnd)),
        wintypes.UINT(int(msg)),
        wintypes.WPARAM(int(wparam or 0)),
        wintypes.LPARAM(int(lparam or 0)),
    )


def _create_font(font_spec):
    family = "Tahoma"
    size = 10
    weight = 400
    italic = 0
    if isinstance(font_spec, (tuple, list)):
        if len(font_spec) >= 1:
            family = str(font_spec[0])
        if len(font_spec) >= 2:
            try:
                size = int(font_spec[1])
            except Exception:
                size = 10
        if len(font_spec) >= 3:
            for flag in font_spec[2:]:
                if str(flag).lower() == "bold":
                    weight = 700
                elif str(flag).lower() == "italic":
                    italic = 1
    # Negative height selects a character height in logical pixels.
    height = -max(8, int(size * 96 / 72))
    return _GDI32.CreateFontW(
        height, 0, 0, 0, weight, italic, 0, 0,
        1, 0, 0, 0, 0, family,
    )


def _set_paragraph_direction(hwnd, rtl: bool) -> None:
    """Enable Unicode BiDi and set paragraph direction/alignment."""
    options = _BIDIOPTIONS()
    options.cbSize = ctypes.sizeof(_BIDIOPTIONS)
    options.wMask = BOM_CONTEXTALIGNMENT | BOM_CONTEXTREADING | BOM_UNICODEBIDI | BOM_DEFPARADIR
    if rtl:
        options.wEffects = BOE_UNICODEBIDI | BOE_RTLDIR
    else:
        options.wEffects = BOE_UNICODEBIDI
    ctypes_payload = ctypes.byref(options)
    _send(hwnd, EM_SETBIDIOPTIONS, 0, ctypes.cast(ctypes_payload, ctypes.c_void_p).value or 0)

    pf = _PARAFORMAT()
    pf.cbSize = ctypes.sizeof(_PARAFORMAT)
    pf.dwMask = PFM_ALIGNMENT | PFM_RTLPARA
    pf.wAlignment = PFA_RIGHT if rtl else PFA_LEFT
    pf.wEffects = PFE_RTLPARA if rtl else 0
    _send(hwnd, EM_SETPARAFORMAT, 0xFFFF, ctypes.cast(ctypes.byref(pf), ctypes.c_void_p).value or 0)


def _get_native_text(hwnd: int) -> str:
    length = int(_send(hwnd, WM_GETTEXTLENGTH, 0, 0))
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _send(hwnd, WM_GETTEXT, length + 1, ctypes.addressof(buf))
    return buf.value.replace("\r\n", "\n").replace("\r", "\n")


def _clear_native_text(hwnd: int) -> None:
    _send(hwnd, EM_SETSEL, 0, -1)
    _send(hwnd, WM_CLEAR, 0, 0)
    _send(hwnd, EM_SETSEL, 0, 0)
    _send(hwnd, EM_SETMODIFY, 0, 0)


def _set_native_text(hwnd: int, text: str) -> None:
    value = _normalize_newlines(text)
    if not value:
        _clear_native_text(hwnd)
        return
    buf = ctypes.create_unicode_buffer(value)
    _send(hwnd, 0x000C, 0, ctypes.addressof(buf))
    _send(hwnd, EM_SETMODIFY, 0, 0)


def _get_native_selection(hwnd: int) -> tuple[int, int]:
    start = wintypes.DWORD(0)
    end = wintypes.DWORD(0)
    # EM_GETSEL writes to wParam/lParam pointers.
    _send(hwnd, EM_GETSEL,
          ctypes.cast(ctypes.byref(start), ctypes.c_void_p).value or 0,
          ctypes.cast(ctypes.byref(end), ctypes.c_void_p).value or 0)
    return int(start.value), int(end.value)


def _set_native_selection(hwnd: int, start: int, end: int) -> None:
    _send(hwnd, EM_SETSEL, int(start), int(end))


def _normalize_newlines(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _parse_text_index(text: str, index: Any) -> int:
    text = _normalize_newlines(text)
    if index in (tk.END, "end"):
        return len(text)
    raw = str(index)
    if raw in ("insert", "current"):
        return len(text)
    if raw.startswith("end-") and raw.endswith("c"):
        try:
            return max(0, len(text) - int(raw[4:-1]))
        except Exception:
            return len(text)
    if "." in raw:
        try:
            line_s, col_s = raw.split(".", 1)
            line = max(1, int(line_s))
            col = max(0, int(col_s))
            lines = text.split("\n")
            if line > len(lines):
                return len(text)
            offset = sum(len(x) + 1 for x in lines[:line - 1])
            return min(len(text), offset + col)
        except Exception:
            return 0
    try:
        return max(0, min(len(text), int(index)))
    except Exception:
        return 0


def _offset_to_text_index(text: str, offset: int) -> str:
    text = _normalize_newlines(text)
    offset = max(0, min(len(text), int(offset)))
    before = text[:offset]
    line = before.count("\n") + 1
    last_nl = before.rfind("\n")
    col = offset if last_nl < 0 else offset - last_nl - 1
    return f"{line}.{col}"


class _NativeEditorBase(tk.Frame):
    """Tk geometry wrapper around a native Windows Rich Edit control."""

    _multiline = False

    def __init__(self, master=None, **kwargs):
        frame_kwargs = {}
        for key in (
            "width", "height", "bg", "background", "highlightbackground",
            "highlightcolor", "highlightthickness", "bd", "borderwidth",
            "relief", "cursor", "takefocus",
        ):
            if key in kwargs:
                frame_kwargs[key] = kwargs.pop(key)

        self._textvariable = kwargs.pop("textvariable", None)
        self._font_spec = kwargs.pop("font", _FONT)
        self._show = kwargs.pop("show", "")
        self._state = kwargs.pop("state", "normal")
        self._justify = kwargs.pop("justify", "right")
        self._rtl = self._justify != "left"
        self._wrap = kwargs.pop("wrap", "word")
        self._width_chars = kwargs.pop("width", 0)
        self._height_lines = kwargs.pop("height", 0)
        self._placeholder = kwargs.pop("placeholder", "")
        self._sync_running = False
        self._initializing = True
        self._poll_id = None
        self._font_handle = None
        self._native_hwnd = None
        self._text_cache = ""
        self._trace_id = None
        self._logical_scroll_x = 0

        # Ignore ordinary Tk/ttk visual options we can safely replace at the
        # native-control level; they are styling-only and must not crash the
        # application.
        ignored = {
            "style", "validate", "validatecommand", "invalidcommand",
            "exportselection", "insertbackground", "insertwidth",
            "selectbackground", "selectforeground", "readonlybackground",
            "disabledbackground", "disabledforeground", "foreground", "fg",
            "background", "insertborderwidth", "insertontime", "insertofftime",
            "xscrollcommand", "yscrollcommand",
        }
        for key in list(kwargs):
            if key not in ignored:
                kwargs.pop(key, None)

        if "bg" not in frame_kwargs and "background" not in frame_kwargs:
            frame_kwargs["bg"] = "#FFFFFF"

        super().__init__(master, **frame_kwargs)
        self._gela_rtl_editor = self

        _ensure_richedit_loaded()
        self._create_native()
        self._install_variable_trace()
        self.bind("<Configure>", self._resize_native, add="+")
        self.bind("<FocusIn>", lambda _e: self.focus_set_native(), add="+")
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._apply_initial_state()
        _clear_native_text(self._native_hwnd)
        self._sync_from_variable(initial=True)
        if not self._text_cache:
            _clear_native_text(self._native_hwnd)
        _send(self._native_hwnd, EM_SETMODIFY, 0, 0)
        self._initializing = False
        self.after_idle(self._sync_native_geometry)
        self._schedule_poll()

    # ----- native creation ---------------------------------------------------
    def _create_native(self):
        parent_hwnd = int(self.winfo_id())
        style = WS_CHILD | WS_VISIBLE | WS_TABSTOP | WS_BORDER | ES_NOHIDESEL
        if self._multiline:
            style |= ES_MULTILINE | ES_AUTOVSCROLL | ES_WANTRETURN
            if self._wrap == "none":
                style |= ES_AUTOHSCROLL
            # Do not add WS_VSCROLL; the app's Tk scrollbars can remain usable
            # and the RichEdit still responds to wheel/keyboard scrolling.
        else:
            style |= ES_AUTOHSCROLL
        if self._show:
            style |= ES_PASSWORD

        ex_style = 0
        hwnd = _USER32.CreateWindowExW(
            ex_style,
            "RICHEDIT50W",
            "",
            style,
            0, 0, 10, 10,
            wintypes.HWND(parent_hwnd),
            wintypes.HMENU(0),
            wintypes.HINSTANCE(0),
            None,
        )
        if not hwnd:
            raise OSError(f"Could not create native RichEdit control: {ctypes.get_last_error()}")
        self._native_hwnd = int(hwnd)

        self._font_handle = _create_font(self._font_spec)
        if self._font_handle:
            _send(self._native_hwnd, WM_SETFONT, self._font_handle, 1)
        _send(self._native_hwnd, EM_SETBKGNDCOLOR, 0, _rgb(255, 255, 255))
        _send(self._native_hwnd, EM_SETLIMITTEXT, 0, 0x7FFFFFFE)
        _send(self._native_hwnd, WM_SETREDRAW, 1, 0)
        _set_paragraph_direction(self._native_hwnd, self._rtl)

    def _apply_initial_state(self):
        readonly = str(self._state).lower() in {"disabled", "readonly"}
        _send(self._native_hwnd, EM_SETREADONLY, 1 if readonly else 0, 0)

    # ----- geometry / focus -------------------------------------------------
    def _resize_native(self, _event=None):
        self._sync_native_geometry()

    def _sync_native_geometry(self):
        if not self._native_hwnd:
            return
        try:
            w = max(1, self.winfo_width())
            h = max(1, self.winfo_height())
            _USER32.MoveWindow(self._native_hwnd, 0, 0, w, h, True)
            _USER32.ShowWindow(self._native_hwnd, SW_SHOW)
        except Exception:
            pass

    def focus_set_native(self):
        try:
            _USER32.SetFocus(self._native_hwnd)
        except Exception:
            super().focus_set()

    def focus_set(self):
        self.focus_set_native()
        return None

    def focus_force(self):
        self.focus_set_native()
        return None

    # ----- textvariable ------------------------------------------------------
    def _install_variable_trace(self):
        if self._textvariable is None:
            self._var = tk.StringVar(self, value="")
            self._var_name = self._var._name
            return
        self._var = self._textvariable
        self._var_name = getattr(self._var, "_name", str(self._var))
        try:
            self._trace_id = self._var.trace_add("write", self._variable_changed)
        except Exception:
            self._trace_id = None

    def _variable_changed(self, *_args):
        if self._sync_running:
            return
        self._sync_from_variable()

    def _sync_from_variable(self, initial=False):
        try:
            value = str(self._var.get() or "")
        except Exception:
            value = ""
        if value == self._text_cache and not initial:
            return
        self._set_native_raw(value)
        self._text_cache = value
        _send(self._native_hwnd, EM_SETMODIFY, 0, 0)

    def _sync_to_variable(self):
        if self._var is None:
            return
        native = self._get_native_raw()
        if native == self._text_cache:
            return
        self._text_cache = native
        try:
            self._sync_running = True
            self._var.set(native)
        except Exception:
            pass
        finally:
            self._sync_running = False

    def _schedule_poll(self):
        try:
            self._poll_id = self.after(70, self._poll_native)
        except Exception:
            self._poll_id = None

    def _poll_native(self):
        if not self._native_hwnd:
            return
        try:
            if self._initializing:
                return
            if bool(_send(self._native_hwnd, EM_GETMODIFY, 0, 0)):
                self._sync_to_variable()
                _send(self._native_hwnd, EM_SETMODIFY, 0, 0)
        finally:
            self._schedule_poll()

    # ----- native text API --------------------------------------------------
    def _get_native_raw(self):
        return _get_native_text(self._native_hwnd)

    def _set_native_raw(self, text):
        value = _normalize_newlines(text)
        _set_native_text(self._native_hwnd, value)
        _set_paragraph_direction(self._native_hwnd, self._rtl)
        _send(self._native_hwnd, EM_SETMODIFY, 0, 0)

    def get(self, *args):
        text = self._get_native_raw()
        if not args:
            return text
        start = _parse_text_index(text, args[0]) if self._multiline else int(args[0]) if str(args[0]).isdigit() else 0
        end = len(text) if len(args) < 2 else (_parse_text_index(text, args[1]) if self._multiline else int(args[1]) if str(args[1]).isdigit() else len(text))
        if self._multiline and (args[1:] and str(args[1]) in (str(tk.END), "end")):
            # Tk Text includes its terminating newline; the application usually
            # strips it, but this makes get("1.0", tk.END) compatible.
            return text[start:end] + "\n"
        return text[start:end]

    def insert(self, index, text, *tags):
        value = _normalize_newlines(str(text or ""))
        current = self._get_native_raw()
        if self._multiline:
            pos = _parse_text_index(current, index)
        else:
            try:
                pos = max(0, min(len(current), int(index)))
            except Exception:
                pos = len(current)
        new_value = current[:pos] + value + current[pos:]
        _set_native_text(self._native_hwnd, new_value)
        _set_paragraph_direction(self._native_hwnd, self._rtl)
        _set_native_selection(self._native_hwnd, pos + len(value), pos + len(value))
        self._sync_to_variable()

    def delete(self, first, last=None):
        current = self._get_native_raw()
        if self._multiline:
            start = _parse_text_index(current, first)
            end = len(current) if last is None else _parse_text_index(current, last)
        else:
            start = int(first) if str(first).isdigit() else 0
            end = len(current) if last is None else (int(last) if str(last).isdigit() else len(current))
        start, end = sorted((max(0, start), min(len(current), end)))
        _set_native_text(self._native_hwnd, current[:start] + current[end:])
        _set_paragraph_direction(self._native_hwnd, self._rtl)
        _set_native_selection(self._native_hwnd, start, start)
        self._sync_to_variable()

    def set_text(self, text, cursor_to_end=True):
        value = _normalize_newlines(str(text or ""))
        self._set_native_raw(value)
        self._text_cache = value
        if cursor_to_end:
            _set_native_selection(self._native_hwnd, len(value), len(value))
        self._sync_to_variable()

    # ----- selection / cursor ------------------------------------------------
    def selection_get(self):
        start, end = _get_native_selection(self._native_hwnd)
        text = self._get_native_raw()
        return text[start:end]

    def selection_clear(self):
        start, end = _get_native_selection(self._native_hwnd)
        _set_native_selection(self._native_hwnd, end, end)

    def select_range(self, start, end):
        if self._multiline:
            text = self._get_native_raw()
            start_i = _parse_text_index(text, start)
            end_i = _parse_text_index(text, end)
        else:
            start_i = int(start)
            end_i = int(end)
        _set_native_selection(self._native_hwnd, start_i, end_i)

    def selection_present(self):
        a, b = _get_native_selection(self._native_hwnd)
        return a != b

    def icursor(self, index):
        text = self._get_native_raw()
        pos = _parse_text_index(text, index) if self._multiline else (len(text) if index in (tk.END, "end") else int(index))
        _set_native_selection(self._native_hwnd, pos, pos)

    def index(self, index):
        text = self._get_native_raw()
        if str(index) in ("insert", "current"):
            pos, _ = _get_native_selection(self._native_hwnd)
        else:
            pos = _parse_text_index(text, index)
        return _offset_to_text_index(text, pos) if self._multiline else pos

    def mark_set(self, mark, index):
        if mark == "insert":
            self.icursor(index)

    # ----- ttk-ish API -------------------------------------------------------
    def configure(self, cnf=None, **kwargs):
        options = {}
        if isinstance(cnf, dict):
            options.update(cnf)
        options.update(kwargs)
        if not options:
            return {}
        if "state" in options:
            state = str(options.pop("state")).lower()
            self._state = state
            _send(self._native_hwnd, EM_SETREADONLY, 1 if state in {"disabled", "readonly"} else 0, 0)
        if "justify" in options:
            self._justify = str(options.pop("justify"))
            self.set_rtl(self._justify != "left")
        if "font" in options:
            self._font_spec = options.pop("font")
            if self._font_handle:
                _GDI32.DeleteObject(self._font_handle)
            self._font_handle = _create_font(self._font_spec)
            if self._font_handle:
                _send(self._native_hwnd, WM_SETFONT, self._font_handle, 1)
        if "textvariable" in options:
            # Keep the current variable; changing it at runtime is uncommon.
            new_var = options.pop("textvariable")
            if new_var is not self._var:
                try:
                    self._var.set(self._get_native_raw())
                except Exception:
                    pass
                self._var = new_var
                self._sync_from_variable(initial=True)
        # Silently accept common Tk styling/config options because the native
        # Rich Edit is responsible for its actual visuals.
        for key in (
            "bg", "background", "fg", "foreground", "relief", "bd",
            "borderwidth", "insertbackground", "insertwidth", "cursor",
            "highlightbackground", "highlightcolor", "highlightthickness",
            "selectbackground", "selectforeground", "readonlybackground",
            "disabledbackground", "disabledforeground", "show",
            "exportselection", "validate", "validatecommand",
            "invalidcommand", "width", "height", "wrap",
        ):
            options.pop(key, None)
        return None

    config = configure

    def cget(self, option):
        option = str(option)
        if option == "state":
            return self._state
        if option == "justify":
            return self._justify
        if option == "font":
            return self._font_spec
        if option == "textvariable":
            return self._var_name
        return ""

    def state(self, statespec=None):
        if statespec is None:
            return ("disabled",) if str(self._state).lower() == "disabled" else ()
        if isinstance(statespec, (list, tuple)):
            if "disabled" in statespec:
                self.configure(state="disabled")
            elif "!disabled" in statespec:
                self.configure(state="normal")
        return self.state()

    def instate(self, statespec, callback=None, *args):
        disabled = str(self._state).lower() == "disabled"
        wanted_disabled = "disabled" in statespec if isinstance(statespec, (list, tuple)) else False
        ok = disabled == wanted_disabled
        if ok and callback:
            return callback(*args)
        return ok

    # ----- scrolling ---------------------------------------------------------
    def yview(self, *args):
        if not args:
            return (0.0, 1.0)
        if args[0] == "scroll":
            units = int(args[1]) if len(args) > 1 else 1
            _send(self._native_hwnd, EM_LINESCROLL, 0, units)
        elif args[0] == "moveto":
            try:
                frac = float(args[1])
            except Exception:
                frac = 0.0
            # RichEdit understands line scrolling rather than a normalized
            # fraction; approximate using total line count.
            line_count = int(_send(self._native_hwnd, 0x00BA, 0, 0)) or 1  # EM_GETLINECOUNT
            target = max(0, int(frac * max(0, line_count - 1)))
            _send(self._native_hwnd, 0x00B7, 0, 0)
            # EM_LINESCROLL is relative, so reset upward generously first.
            _send(self._native_hwnd, EM_LINESCROLL, 0, -line_count)
            _send(self._native_hwnd, EM_LINESCROLL, 0, target)
        return (0.0, 1.0)

    def xview(self, *args):
        if not args:
            return (0.0, 1.0)
        if args[0] == "scroll":
            units = int(args[1]) if len(args) > 1 else 1
            _send(self._native_hwnd, EM_LINESCROLL, units, 0)
        return (0.0, 1.0)

    def see(self, index):
        if self._multiline:
            text = self._get_native_raw()
            pos = _parse_text_index(text, index)
            _set_native_selection(self._native_hwnd, pos, pos)
        _send(self._native_hwnd, EM_SCROLLCARET, 0, 0)

    # ----- compatibility no-ops ---------------------------------------------
    def edit_modified(self, *args):
        return False

    def tag_configure(self, *args, **kwargs):
        return None

    tag_config = tag_configure
    tag_add = lambda self, *args, **kwargs: None
    tag_remove = lambda self, *args, **kwargs: None
    tag_raise = lambda self, *args, **kwargs: None

    # ----- RTL ---------------------------------------------------------------
    def set_rtl(self, rtl: bool):
        self._rtl = bool(rtl)
        _set_paragraph_direction(self._native_hwnd, self._rtl)

    def _on_destroy(self, _event=None):
        if self._poll_id:
            try:
                self.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        try:
            if getattr(self, "_trace_id", None) and self._var is not None:
                self._var.trace_remove("write", self._trace_id)
        except Exception:
            pass
        self._trace_id = None
        if self._native_hwnd:
            try:
                _USER32.DestroyWindow(self._native_hwnd)
            except Exception:
                pass
            self._native_hwnd = None
        if self._font_handle:
            try:
                _GDI32.DeleteObject(self._font_handle)
            except Exception:
                pass
            self._font_handle = None


class GelaRTLLineEdit(_NativeEditorBase):
    _multiline = False

    def __init__(self, master=None, **kwargs):
        kwargs.setdefault("font", _FONT)
        kwargs.setdefault("justify", "right")
        width = kwargs.get("width", 0)
        # Entry width is character-oriented in Tk. Give the Frame a sensible
        # requested width but let normal pack/grid expansion override it.
        if width and "width" not in kwargs:
            kwargs["width"] = max(40, int(width) * 8)
        elif width:
            kwargs["width"] = max(40, int(width) * 8)
        kwargs.setdefault("height", 28)
        super().__init__(master, **kwargs)


class GelaRTLTextEdit(_NativeEditorBase):
    _multiline = True

    def __init__(self, master=None, **kwargs):
        kwargs.setdefault("font", _FONT)
        kwargs.setdefault("justify", "right")
        lines = int(kwargs.get("height", 6) or 6)
        kwargs["height"] = max(50, lines * 20 + 8)
        super().__init__(master, **kwargs)


# ---------------------------------------------------------------------------
# Non-Windows safe fallback
# ---------------------------------------------------------------------------

def _patch_tk_entry_fallback():
    original = tk.Entry.__init__
    if getattr(tk.Entry, "_gela_rtl_fallback", False):
        return
    def _init(self, master=None, *args, **kwargs):
        kwargs.setdefault("justify", "right")
        kwargs.setdefault("font", _FONT)
        original(self, master, *args, **kwargs)
    _init._gela_rtl_fallback = True
    tk.Entry.__init__ = _init


def _patch_ttk_entry_fallback():
    original = ttk.Entry.__init__
    if getattr(ttk.Entry, "_gela_rtl_fallback", False):
        return
    def _init(self, master=None, *args, **kwargs):
        kwargs.setdefault("justify", "right")
        kwargs.setdefault("font", _FONT)
        original(self, master, *args, **kwargs)
    _init._gela_rtl_fallback = True
    ttk.Entry.__init__ = _init


def _patch_tk_text_fallback():
    original = tk.Text.__init__
    if getattr(tk.Text, "_gela_rtl_fallback", False):
        return
    def _init(self, master=None, *args, **kwargs):
        kwargs.setdefault("font", _FONT)
        original(self, master, *args, **kwargs)
        try:
            self.tag_configure("__gela_rtl__", justify="right")
            self.after_idle(lambda: self.tag_add("__gela_rtl__", "1.0", "end-1c"))
        except Exception:
            pass
    _init._gela_rtl_fallback = True
    tk.Text.__init__ = _init


__all__ = [
    "apply_rtl_patch",
    "mark_ltr",
    "mark_rtl",
    "configure_rtl",
    "configure_ltr",
    "is_rtl_widget",
    "set_rtl_text",
    "_rtl_populate",
    "GelaRTLLineEdit",
    "GelaRTLTextEdit",
]
