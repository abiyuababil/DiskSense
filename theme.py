"""
DiskSense Theme
Palette: warm charcoal base, teal accent, muted earth tones.
Chosen for extended use without eye fatigue — this is a utility tool, not a marketing page.
"""


class Colors:
    # Base
    BG_PRIMARY = "#1a1d23"       # deep charcoal — main background
    BG_SECONDARY = "#22262e"     # slightly lighter — panels, sidebar
    BG_TERTIARY = "#2a2f38"      # card backgrounds, input fields
    BG_HOVER = "#323842"         # hover states on interactive rows

    # Accent — teal: signals action, progress, health
    ACCENT = "#2eb8a6"
    ACCENT_HOVER = "#35d4bf"
    ACCENT_MUTED = "#1a6b60"     # subtle backgrounds for selected states

    # Text
    TEXT_PRIMARY = "#e8eaed"      # main readable text
    TEXT_SECONDARY = "#9ca3af"    # labels, metadata, secondary info
    TEXT_MUTED = "#6b7280"        # placeholders, disabled

    # Semantic — used only where meaning matters
    RED = "#e05c5c"              # delete, danger, large files
    RED_HOVER = "#ef6b6b"
    RED_BG = "#3d2020"           # subtle red background for warnings
    AMBER = "#e0a84e"            # caution, medium priority
    GREEN = "#5cb85c"            # safe, small files, good status
    BLUE = "#5b8def"             # info, links, navigation

    # Borders
    BORDER = "#363b44"
    BORDER_FOCUS = "#2eb8a6"

    # Scrollbar
    SCROLLBAR = "#3a3f48"
    SCROLLBAR_HOVER = "#4a5060"


class Fonts:
    # Segoe UI is native to Windows, clean, and readable at small sizes
    FAMILY = "Segoe UI"
    MONO = "Consolas"

    HEADING_SIZE = 18
    SUBHEADING_SIZE = 14
    BODY_SIZE = 13
    SMALL_SIZE = 11
    TINY_SIZE = 10


class Spacing:
    PAD_XS = 4
    PAD_SM = 8
    PAD_MD = 12
    PAD_LG = 16
    PAD_XL = 24

    RADIUS_SM = 4
    RADIUS_MD = 6
    RADIUS_LG = 8
