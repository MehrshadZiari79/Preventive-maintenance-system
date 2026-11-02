# utils/rtl_text_widget.py
"""
Gela PM System - RTL Text Compatibility Adapter

The real Windows RTL editor lives in utils.rtl_patch.py and uses the native
Microsoft Rich Edit control. This module intentionally contains NO bidi
reshaping, no python-bidi visual-string manipulation, and no TkinterWeb.

This keeps the public RTLText name used by the existing PM dialogs while
routing every multiline field to the same native logical-Unicode editor.
"""

from __future__ import annotations

from utils.rtl_patch import GelaRTLTextEdit


class RTLText(GelaRTLTextEdit):
    """
    Compatibility name for the application's existing dialogs.

    Database/UI contract:
        RTLText.get() -> logical Unicode text
        RTLText.set_logical_text(text) -> load logical Unicode text

    Example:
        سلام pm باید تعمیر شود

    The native Rich Edit control handles the visual RTL/LTR ordering.
    """

    def __init__(self, master=None, **kwargs):
        # Existing dialogs pass Text-style character dimensions such as
        # width=50 / height=5. The native Frame wrapper uses pixel dimensions,
        # so convert character-style width here while keeping height handled by
        # GelaRTLTextEdit.
        width = kwargs.get("width")
        if width is not None:
            try:
                width_int = int(width)
                kwargs["width"] = max(
                    260,
                    width_int * 8,
                )
            except (TypeError, ValueError):
                pass

        kwargs.setdefault(
            "justify",
            "right",
        )
        kwargs.setdefault(
            "wrap",
            "word",
        )
        kwargs.setdefault(
            "font",
            ("Tahoma", 10),
        )
        kwargs.setdefault(
            "bg",
            "white",
        )
        kwargs.setdefault(
            "fg",
            "#1F2937",
        )

        super().__init__(
            master,
            **kwargs,
        )

        # Marker used by any dialog code that needs to treat this widget as a
        # leaf. Native Rich Edit itself is a Win32 child of our Tk Frame and
        # therefore never appears in winfo_children().
        self._gela_mousewheel_leaf = True

    def set_logical_text(self, text):
        """Load normal logical Unicode text from the database."""
        self.set_text(
            "" if text is None else str(text),
            cursor_to_end=True,
        )

    def clear(self):
        """Clear the complete logical field."""
        self.set_text(
            "",
            cursor_to_end=True,
        )


__all__ = ["RTLText"]
