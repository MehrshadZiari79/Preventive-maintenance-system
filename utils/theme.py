# utils/theme.py
"""
PM System - unified design tokens and the ONE place the ttk theme is chosen.

Rules
-----
* ``apply_app_theme(root)`` is called once for every Tk root window
  (login window and main window).  It selects the ttk "clam" theme and
  configures the shared base styles.
* Views must NOT call ``style.theme_use(...)`` themselves.  Switching the
  ttk theme from inside a page changes the look of every other page and
  silently drops styles that were configured under the previous theme.
  Views that still want to be defensive call ``ensure_theme(style)``, which
  is a no-op when the application theme is already active.
* Every colour/font name that existed before is kept, so older views keep
  importing exactly what they imported before.
"""

from __future__ import annotations

# ── Palette (original names - do not rename) ────────────────────────────
NAVY        = "#1A2A44"
NAVY_LIGHT  = "#2C3E6B"
WHITE       = "#FFFFFF"
RED         = "#DC2626"
GRAY_BG     = "#F4F6F9"
GRAY_BORDER = "#E8ECF0"
TEXT_DARK   = "#202124"
TEXT_LIGHT  = "#5F6368"
SUCCESS     = "#16A34A"
WARNING     = "#D97706"

# ── Extended palette (new) ──────────────────────────────────────────────
NAVY_DARK     = "#121E33"
ACCENT        = "#2563EB"      # links, focus rings, selected rows
ACCENT_SOFT   = "#EAF1FF"
SURFACE       = WHITE
SURFACE_ALT   = "#F8FAFC"      # zebra rows / subtle panels
BORDER        = "#DDE3EA"
BORDER_STRONG = "#C5CED9"
TEXT_MUTED    = "#6B7280"
INFO          = "#0369A1"

SUCCESS_SOFT  = "#EAF7EF"
WARNING_SOFT  = "#FFF5E6"
DANGER        = RED
DANGER_SOFT   = "#FDEDED"
INFO_SOFT     = "#E8F4FB"

# ── Typography ─────────────────────────────────────────────────────────
FONT_FAMILY     = "Tahoma"      # best installed Persian UI font on Windows
FONT_TITLE      = (FONT_FAMILY, 14, "bold")
FONT_HEADING    = (FONT_FAMILY, 11, "bold")
FONT_SUBHEADING = (FONT_FAMILY, 11, "bold")
FONT_NORMAL     = (FONT_FAMILY, 9)
FONT_BOLD       = (FONT_FAMILY, 9, "bold")
FONT_SMALL      = (FONT_FAMILY, 8)
FONT_KPI        = (FONT_FAMILY, 22, "bold")
FONT_METRIC     = (FONT_FAMILY, 16, "bold")

# Type scale (same fonts as above, named by role)
FONT_CAPTION    = FONT_SMALL            # hints, table footers, badges
FONT_BODY       = FONT_NORMAL           # labels, inputs, table rows
FONT_BODY_BOLD  = FONT_BOLD             # field labels, buttons that matter
FONT_SECTION    = FONT_HEADING          # card / section titles
FONT_PAGE_TITLE = FONT_TITLE            # page header title
FONT_DISPLAY    = FONT_KPI              # big numbers

# ── Spacing scale (pixels) ─────────────────────────────────────────────
SPACE_XS   = 4
SPACE_SM   = 8
SPACE_MD   = 12
SPACE_LG   = 16
SPACE_XL   = 24
SPACE_PAGE = 20      # left/right padding of every page body

APP_THEME = "clam"


# ---------------------------------------------------------------------------
# Persian number helpers
# ---------------------------------------------------------------------------

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_LATIN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def fa_digits(value) -> str:
    """Return ``value`` as text with Persian digits (display only)."""
    return str(value).translate(_FA_DIGITS)


def latin_digits(value) -> str:
    """Normalise Persian/Arabic digits and separators typed by the user."""
    text = str(value or "").translate(_LATIN_DIGITS)
    return (
        text.replace("٫", ".")     # Persian decimal separator
            .replace("٬", "")      # Persian thousands separator
            .replace(",", "")
            .replace("،", "")
            .strip()
    )


def fmt_number(value, decimals: int = 2, persian: bool = True) -> str:
    """Format a number with thousands separators and trimmed decimals."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if number.is_integer():
        text = f"{int(number):,}"
    else:
        text = f"{number:,.{decimals}f}".rstrip("0").rstrip(".")
    if persian:
        text = text.replace(",", "٬").replace(".", "٫")
        text = fa_digits(text)
    return text


# ---------------------------------------------------------------------------
# ttk theme
# ---------------------------------------------------------------------------

def ensure_theme(style) -> None:
    """Select the application theme only if it is not already active."""
    try:
        if style.theme_use() != APP_THEME:
            style.theme_use(APP_THEME)
    except Exception:
        pass


def apply_app_theme(root) -> None:
    """
    Configure the shared look once per Tk root.

    Only base styles are touched here.  Page-specific styles (for example
    ``Repair.Treeview``) still override these values exactly as before.
    """
    from tkinter import ttk

    style = ttk.Style(root)
    ensure_theme(style)

    # Default fonts for classic Tk widgets created without a font.
    try:
        root.option_add("*Font", FONT_NORMAL)
        root.option_add("*Listbox.justify", "right")
        root.option_add("*Menu.font", FONT_NORMAL)
        root.option_add("*TCombobox*Listbox.font", FONT_NORMAL)
        root.option_add("*TCombobox*Listbox.justify", "right")
        root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        root.option_add("*TCombobox*Listbox.selectForeground", WHITE)
    except Exception:
        pass

    style.configure(".", font=FONT_NORMAL, foreground=TEXT_DARK)
    style.configure("TFrame", background=GRAY_BG)
    style.configure("TLabel", background=GRAY_BG, foreground=TEXT_DARK)

    style.configure(
        "TEntry",
        padding=(8, 5),
        fieldbackground=WHITE,
        bordercolor=BORDER_STRONG,
        lightcolor=BORDER,
        darkcolor=BORDER,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", ACCENT)],
        lightcolor=[("focus", ACCENT)],
        darkcolor=[("focus", ACCENT)],
        fieldbackground=[("readonly", SURFACE_ALT), ("disabled", SURFACE_ALT)],
    )

    style.configure(
        "TCombobox",
        padding=(8, 5),
        fieldbackground=WHITE,
        background=WHITE,
        bordercolor=BORDER_STRONG,
        lightcolor=BORDER,
        darkcolor=BORDER,
        arrowcolor=NAVY,
    )
    style.map(
        "TCombobox",
        bordercolor=[("focus", ACCENT)],
        lightcolor=[("focus", ACCENT)],
        darkcolor=[("focus", ACCENT)],
        fieldbackground=[("readonly", WHITE), ("disabled", SURFACE_ALT)],
        selectbackground=[("readonly", WHITE)],
        selectforeground=[("readonly", TEXT_DARK)],
    )

    style.configure(
        "TButton",
        padding=(10, 5),
        background=SURFACE_ALT,
        bordercolor=BORDER_STRONG,
        lightcolor=SURFACE_ALT,
        darkcolor=BORDER,
        focuscolor=ACCENT,
    )
    style.map("TButton", background=[("active", ACCENT_SOFT), ("pressed", ACCENT_SOFT)])

    style.configure(
        "Treeview",
        background=WHITE,
        fieldbackground=WHITE,
        foreground=TEXT_DARK,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        rowheight=30,
        font=FONT_NORMAL,
    )
    style.map(
        "Treeview",
        background=[("selected", ACCENT)],
        foreground=[("selected", WHITE)],
    )
    style.configure(
        "Treeview.Heading",
        background=NAVY,
        foreground=WHITE,
        relief="flat",
        bordercolor=NAVY_LIGHT,
        lightcolor=NAVY,
        darkcolor=NAVY,
        font=FONT_BOLD,
        padding=(8, 7),
    )
    style.map("Treeview.Heading", background=[("active", NAVY_LIGHT)])

    style.configure(
        "TScrollbar",
        background="#CBD3DD",
        troughcolor=SURFACE_ALT,
        bordercolor=SURFACE_ALT,
        lightcolor="#CBD3DD",
        darkcolor="#CBD3DD",
        arrowcolor=TEXT_MUTED,
        gripcount=0,
    )
    style.map("TScrollbar", background=[("active", "#AEB8C5"), ("pressed", NAVY_LIGHT)])

    style.configure("TNotebook", background=GRAY_BG, borderwidth=0, tabmargins=(2, 4, 2, 0))
    style.configure(
        "TNotebook.Tab",
        padding=(14, 6),
        background="#E4E9F0",
        foreground=TEXT_MUTED,
        bordercolor=BORDER,
        lightcolor="#E4E9F0",
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", WHITE)],
        foreground=[("selected", NAVY)],
        lightcolor=[("selected", WHITE)],
    )

    style.configure("TCheckbutton", background=GRAY_BG, indicatorcolor=WHITE)
    style.map("TCheckbutton", indicatorcolor=[("selected", ACCENT)], background=[("active", GRAY_BG)])
    style.configure("TRadiobutton", background=GRAY_BG)
    style.configure("TProgressbar", background=ACCENT, troughcolor="#E4E9F0", bordercolor="#E4E9F0")
