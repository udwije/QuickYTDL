# quickytdl/ui/theme.py

"""
Single source of truth for the app's look.

The stylesheet is generated from a small palette dict, so a light and a dark
theme share one template and can never drift apart. Add a colour here, not a
hard-coded hex in a widget constructor.
"""

LIGHT = {
    "window":       "#f5f6fa",
    "surface":      "#ffffff",
    "surface_alt":  "#f8fafc",
    "border":       "#d8dce6",
    "border_soft":  "#e2e8f0",
    "input_border": "#cbd5e1",
    "text":         "#1e293b",
    "text_muted":   "#64748b",
    "text_faint":   "#94a3b8",
    "heading":      "#334155",
    "accent":       "#3b82f6",
    "accent_dark":  "#2563eb",
    "accent_press": "#1d4ed8",
    "accent_soft":  "#dbeafe",
    "accent_faint": "#eff6ff",
    "accent_dim":   "#bfdbfe",
    "danger":       "#ef4444",
    "danger_soft":  "#fef2f2",
    "danger_dim":   "#fecaca",
    "header_bg":    "#eef2f7",
    "grid":         "#eef2f7",
    "hover":        "#f1f5f9",
    "pressed":      "#e2e8f0",
    "disabled_bg":  "#f8fafc",
    "disabled_fg":  "#cbd5e1",
    "log_bg":       "#0f172a",
    "log_fg":       "#d1fae5",
    "toolbar_bg":   "#f8fafc",
}

DARK = {
    "window":       "#0f172a",
    "surface":      "#1e293b",
    "surface_alt":  "#243449",
    "border":       "#334155",
    "border_soft":  "#334155",
    "input_border": "#475569",
    "text":         "#e2e8f0",
    "text_muted":   "#94a3b8",
    "text_faint":   "#64748b",
    "heading":      "#cbd5e1",
    "accent":       "#3b82f6",
    "accent_dark":  "#2563eb",
    "accent_press": "#1d4ed8",
    "accent_soft":  "#1e3a8a",
    "accent_faint": "#1e40af",
    "accent_dim":   "#1e3a8a",
    "danger":       "#f87171",
    "danger_soft":  "#450a0a",
    "danger_dim":   "#7f1d1d",
    "header_bg":    "#243449",
    "grid":         "#2c3e57",
    "hover":        "#243449",
    "pressed":      "#334155",
    "disabled_bg":  "#1a2436",
    "disabled_fg":  "#475569",
    "log_bg":       "#020617",
    "log_fg":       "#86efac",
    "toolbar_bg":   "#243449",
}

_TEMPLATE = """
QMainWindow, QWidget#centralHost {{
    background-color: {window};
}}
QWidget {{
    color: {text};
}}
QGroupBox {{
    font-weight: 600;
    border: 1px solid {border};
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px 8px 8px 8px;
    background-color: {surface};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {heading};
}}
QLabel {{
    color: {text};
    background: transparent;
}}
QLabel#mutedLabel {{
    color: {text_muted};
}}
QLabel#countBadge {{
    color: {accent_dark};
    font-weight: 600;
    padding: 2px 8px;
    border: 1px solid {accent_dim};
    border-radius: 9px;
    background: {accent_faint};
}}
QLineEdit, QComboBox, QPlainTextEdit {{
    border: 1px solid {input_border};
    border-radius: 6px;
    padding: 5px 8px;
    background: {surface};
    color: {text};
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {accent};
}}
QLineEdit:disabled, QComboBox:disabled, QPlainTextEdit:disabled {{
    background: {disabled_bg};
    color: {text_faint};
}}
QComboBox QAbstractItemView {{
    background: {surface};
    color: {text};
    selection-background-color: {accent_soft};
    border: 1px solid {input_border};
}}
QPushButton {{
    border: 1px solid {input_border};
    border-radius: 6px;
    padding: 6px 14px;
    background: {surface};
    color: {text};
}}
QPushButton:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {pressed}; }}
QPushButton:disabled {{
    background: {disabled_bg};
    color: {disabled_fg};
    border-color: {border_soft};
}}
QPushButton#primaryButton {{
    background: {accent};
    border: 1px solid {accent_dark};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#primaryButton:hover {{ background: {accent_dark}; }}
QPushButton#primaryButton:pressed {{ background: {accent_press}; }}
QPushButton#primaryButton:disabled {{
    background: {accent_dim};
    border-color: {accent_dim};
    color: {disabled_bg};
}}
QPushButton#dangerButton {{
    background: {surface};
    border: 1px solid {danger};
    color: {danger};
    font-weight: 600;
}}
QPushButton#dangerButton:hover {{ background: {danger_soft}; }}
QPushButton#dangerButton:disabled {{
    border-color: {danger_dim};
    color: {danger_dim};
}}
QPushButton#linkButton {{
    border: none;
    background: transparent;
    color: {accent_dark};
    padding: 4px 8px;
    text-align: left;
}}
QPushButton#linkButton:hover {{
    color: {accent_press};
    text-decoration: underline;
}}
QPushButton#linkButton:disabled {{
    color: {text_faint};
}}
QPushButton#segmentLeft, QPushButton#segmentRight {{
    border: 1px solid {input_border};
    border-radius: 0px;
    padding: 6px 16px;
    background: {surface};
    color: {text_muted};
}}
QPushButton#segmentLeft:checked, QPushButton#segmentRight:checked {{
    background: {accent};
    border-color: {accent_dark};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#segmentLeft:hover:!checked,
QPushButton#segmentRight:hover:!checked {{ background: {hover}; }}
QPushButton#segmentLeft {{
    border-top-left-radius: 6px;
    border-bottom-left-radius: 6px;
}}
QPushButton#segmentRight {{
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}}
QTableView {{
    border: 1px solid {border_soft};
    border-radius: 6px;
    background: {surface};
    gridline-color: {grid};
    selection-background-color: {accent_soft};
    selection-color: {text};
    alternate-background-color: {surface_alt};
}}
QHeaderView::section {{
    background-color: {header_bg};
    color: {heading};
    padding: 6px;
    border: none;
    border-bottom: 1px solid {border_soft};
    font-weight: 600;
}}
QTextEdit {{
    border: 1px solid {border_soft};
    border-radius: 6px;
    background: {log_bg};
    color: {log_fg};
    font-family: Consolas, 'Cascadia Mono', monospace;
}}
QStatusBar {{
    background: {surface};
    border-top: 1px solid {border_soft};
    color: {text_muted};
}}
QStatusBar::item {{ border: none; }}
QProgressBar {{
    border: 1px solid {input_border};
    border-radius: 4px;
    text-align: center;
    background: {hover};
    color: {text};
}}
QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 4px;
}}
QPushButton#iconToggle {{
    padding: 2px;
    font-size: 14px;
}}
QPushButton#iconToggle:checked {{
    background: {accent_soft};
    border-color: {accent};
}}
QLabel#emptyState {{
    color: {text_faint};
    font-size: 13px;
    padding: 24px;
}}
QWidget#toolbar {{
    background: {toolbar_bg};
    border: 1px solid {border_soft};
    border-radius: 6px;
}}
QFrame#separator {{
    background: {border_soft};
    max-width: 1px;
    border: none;
}}
QCheckBox {{ color: {text}; spacing: 6px; }}
QCheckBox:disabled {{ color: {text_faint}; }}
QToolTip {{
    background: {surface};
    color: {text};
    border: 1px solid {input_border};
    padding: 4px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {input_border};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {text_faint}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QMenu {{
    background: {surface};
    color: {text};
    border: 1px solid {border};
}}
QMenu::item:selected {{ background: {accent_soft}; }}
QMenu::item:disabled {{ color: {text_muted}; }}
"""


def palette(dark: bool = False) -> dict:
    return DARK if dark else LIGHT


def stylesheet(dark: bool = False) -> str:
    """Build the full app stylesheet for the requested theme."""
    return _TEMPLATE.format(**palette(dark))


# Status colours used by the progress delegate; kept beside the palette so
# the two themes stay legible against their own backgrounds.
STATUS_COLORS = {
    False: {   # light
        "Queued":      "#94a3b8",
        "Downloading": "#3b82f6",
        "Merging":     "#8b5cf6",
        "Completed":   "#22c55e",
        "Failed":      "#ef4444",
        "Canceled":    "#f59e0b",
        "Skipped":     "#94a3b8",
    },
    True: {    # dark
        "Queued":      "#64748b",
        "Downloading": "#60a5fa",
        "Merging":     "#a78bfa",
        "Completed":   "#4ade80",
        "Failed":      "#f87171",
        "Canceled":    "#fbbf24",
        "Skipped":     "#64748b",
    },
}


def status_color(status: str, dark: bool = False) -> str:
    return STATUS_COLORS[bool(dark)].get(status, "#94a3b8")
