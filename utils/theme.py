# utils/theme.py
"""
Centralized theme for the entire application.
Colors: Navy Blue, White, Red (2026 modern palette)
"""

# ========== Color Palette ==========
NAVY = "#1A2A44"          # Primary dark blue
NAVY_LIGHT = "#2C3E66"    # Lighter navy for hover/gradients
WHITE = "#FFFFFF"
RED = "#E63946"           # Vibrant red for accents/danger
RED_DARK = "#C1121F"      # Darker red for hover
GRAY_BG = "#F5F7FA"       # Very light gray background
GRAY_BORDER = "#DADCE0"   # Border gray
TEXT_DARK = "#1A2A44"     # Dark text
TEXT_LIGHT = "#5F6368"    # Secondary text

# Status colors (consistent with theme)
SUCCESS = "#2A9D8F"       # Teal green
WARNING = "#F4A261"       # Orange
INFO = "#1A73E8"          # Blue (for info)

# ========== Fonts ==========
# Using Tahoma for full Persian support
FONT_TITLE = ("Tahoma", 16, "bold")
FONT_HEADING = ("Tahoma", 9, "bold")
FONT_SUBHEADING = ("Tahoma", 12, "bold")
FONT_NORMAL = ("Tahoma", 10)
FONT_SMALL = ("Tahoma", 9)
FONT_BUTTON = ("Tahoma", 10, "bold")
FONT_KPI = ("Tahoma", 28, "bold")
FONT_INPUT = FONT_NORMAL
# ========== Spacing & Sizes ==========
PADDING_LARGE = 20
PADDING_MEDIUM = 12
PADDING_SMALL = 8
BUTTON_HEIGHT = 32
BUTTON_WIDTH = 120
ENTRY_HEIGHT = 30
SUCCESS = "#2A9D8F"
WARNING = "#F4A261"
BORDER = "#DADCE0"
BORDER = GRAY_BORDER
TEXT = TEXT_DARK