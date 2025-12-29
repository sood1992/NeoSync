"""
NeoSync Theme System
====================

Modern dark/light themes with beautiful typography.
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class ThemeMode(Enum):
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


@dataclass
class ColorPalette:
    """Color palette for theming"""
    # Backgrounds
    bg_primary: str
    bg_secondary: str
    bg_tertiary: str
    bg_elevated: str

    # Text
    text_primary: str
    text_secondary: str
    text_muted: str
    text_inverse: str

    # Accents
    accent_primary: str
    accent_secondary: str
    accent_hover: str

    # Status colors
    success: str
    warning: str
    error: str
    info: str

    # Sync quality colors
    sync_excellent: str
    sync_good: str
    sync_fair: str
    sync_poor: str
    sync_failed: str
    sync_reference: str

    # Borders
    border_subtle: str
    border_default: str
    border_strong: str

    # Shadows
    shadow: str


# Dark Theme
DARK_PALETTE = ColorPalette(
    # Backgrounds
    bg_primary="#0a0a0a",
    bg_secondary="#141414",
    bg_tertiary="#1e1e1e",
    bg_elevated="#252525",

    # Text
    text_primary="#ffffff",
    text_secondary="#a0a0a0",
    text_muted="#666666",
    text_inverse="#0a0a0a",

    # Accents - Purple/Blue gradient feel
    accent_primary="#8b5cf6",
    accent_secondary="#6366f1",
    accent_hover="#a78bfa",

    # Status
    success="#22c55e",
    warning="#eab308",
    error="#ef4444",
    info="#3b82f6",

    # Sync quality
    sync_excellent="#22c55e",
    sync_good="#84cc16",
    sync_fair="#eab308",
    sync_poor="#f97316",
    sync_failed="#ef4444",
    sync_reference="#3b82f6",

    # Borders
    border_subtle="#1e1e1e",
    border_default="#333333",
    border_strong="#444444",

    # Shadow
    shadow="rgba(0, 0, 0, 0.5)"
)

# Light Theme
LIGHT_PALETTE = ColorPalette(
    # Backgrounds
    bg_primary="#ffffff",
    bg_secondary="#f5f5f5",
    bg_tertiary="#ebebeb",
    bg_elevated="#ffffff",

    # Text
    text_primary="#1a1a1a",
    text_secondary="#666666",
    text_muted="#999999",
    text_inverse="#ffffff",

    # Accents
    accent_primary="#7c3aed",
    accent_secondary="#6366f1",
    accent_hover="#8b5cf6",

    # Status
    success="#16a34a",
    warning="#ca8a04",
    error="#dc2626",
    info="#2563eb",

    # Sync quality
    sync_excellent="#16a34a",
    sync_good="#65a30d",
    sync_fair="#ca8a04",
    sync_poor="#ea580c",
    sync_failed="#dc2626",
    sync_reference="#2563eb",

    # Borders
    border_subtle="#f0f0f0",
    border_default="#e0e0e0",
    border_strong="#cccccc",

    # Shadow
    shadow="rgba(0, 0, 0, 0.1)"
)


class Theme:
    """Theme configuration"""

    def __init__(self, mode: ThemeMode = ThemeMode.DARK):
        self.mode = mode
        self._palette = DARK_PALETTE if mode == ThemeMode.DARK else LIGHT_PALETTE

    @property
    def palette(self) -> ColorPalette:
        return self._palette

    def set_mode(self, mode: ThemeMode):
        self.mode = mode
        self._palette = DARK_PALETTE if mode == ThemeMode.DARK else LIGHT_PALETTE

    def get_stylesheet(self) -> str:
        """Generate complete Qt stylesheet"""
        p = self._palette

        return f'''
        /* ===== Global ===== */
        QMainWindow, QWidget {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
            font-size: 13px;
        }}

        /* ===== Typography ===== */
        QLabel {{
            color: {p.text_primary};
        }}

        QLabel[class="title"] {{
            font-size: 24px;
            font-weight: 700;
            color: {p.text_primary};
        }}

        QLabel[class="subtitle"] {{
            font-size: 14px;
            color: {p.text_secondary};
        }}

        QLabel[class="muted"] {{
            color: {p.text_muted};
            font-size: 12px;
        }}

        /* ===== Buttons ===== */
        QPushButton {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border_default};
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: 600;
            font-size: 13px;
        }}

        QPushButton:hover {{
            background-color: {p.bg_elevated};
            border-color: {p.border_strong};
        }}

        QPushButton:pressed {{
            background-color: {p.bg_secondary};
        }}

        QPushButton:disabled {{
            background-color: {p.bg_secondary};
            color: {p.text_muted};
            border-color: {p.border_subtle};
        }}

        QPushButton[class="primary"] {{
            background-color: {p.accent_primary};
            color: white;
            border: none;
        }}

        QPushButton[class="primary"]:hover {{
            background-color: {p.accent_hover};
        }}

        QPushButton[class="success"] {{
            background-color: {p.success};
            color: white;
            border: none;
        }}

        QPushButton[class="danger"] {{
            background-color: {p.error};
            color: white;
            border: none;
        }}

        /* ===== Inputs ===== */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border_default};
            border-radius: 8px;
            padding: 10px 14px;
            selection-background-color: {p.accent_primary};
        }}

        QLineEdit:focus, QTextEdit:focus {{
            border-color: {p.accent_primary};
        }}

        /* ===== ComboBox ===== */
        QComboBox {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border_default};
            border-radius: 8px;
            padding: 10px 14px;
        }}

        QComboBox:hover {{
            border-color: {p.border_strong};
        }}

        QComboBox::drop-down {{
            border: none;
            width: 30px;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {p.text_secondary};
            margin-right: 10px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {p.bg_elevated};
            color: {p.text_primary};
            border: 1px solid {p.border_default};
            border-radius: 8px;
            selection-background-color: {p.accent_primary};
        }}

        /* ===== Progress Bar ===== */
        QProgressBar {{
            background-color: {p.bg_secondary};
            border: none;
            border-radius: 6px;
            height: 12px;
            text-align: center;
            color: {p.text_primary};
            font-size: 10px;
        }}

        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {p.accent_secondary}, stop:1 {p.accent_primary});
            border-radius: 6px;
        }}

        /* ===== Scroll Bars ===== */
        QScrollBar:vertical {{
            background-color: {p.bg_primary};
            width: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {p.border_default};
            border-radius: 6px;
            min-height: 30px;
            margin: 2px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {p.border_strong};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background-color: {p.bg_primary};
            height: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {p.border_default};
            border-radius: 6px;
            min-width: 30px;
            margin: 2px;
        }}

        /* ===== Tables/Lists ===== */
        QTableWidget, QListWidget, QTreeWidget {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border_default};
            border-radius: 12px;
            gridline-color: {p.border_subtle};
        }}

        QTableWidget::item, QListWidget::item {{
            padding: 8px;
            border-bottom: 1px solid {p.border_subtle};
        }}

        QTableWidget::item:selected, QListWidget::item:selected {{
            background-color: {p.accent_primary};
            color: white;
        }}

        QTableWidget::item:hover, QListWidget::item:hover {{
            background-color: {p.bg_tertiary};
        }}

        QHeaderView::section {{
            background-color: {p.bg_tertiary};
            color: {p.text_secondary};
            padding: 12px;
            border: none;
            border-bottom: 1px solid {p.border_default};
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
        }}

        /* ===== Tab Widget ===== */
        QTabWidget::pane {{
            background-color: {p.bg_secondary};
            border: 1px solid {p.border_default};
            border-radius: 12px;
            padding: 10px;
        }}

        QTabBar::tab {{
            background-color: transparent;
            color: {p.text_secondary};
            padding: 12px 20px;
            margin-right: 4px;
            border-radius: 8px;
            font-weight: 500;
        }}

        QTabBar::tab:selected {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
        }}

        QTabBar::tab:hover:!selected {{
            background-color: {p.bg_secondary};
        }}

        /* ===== Splitter ===== */
        QSplitter::handle {{
            background-color: {p.border_subtle};
        }}

        QSplitter::handle:hover {{
            background-color: {p.accent_primary};
        }}

        /* ===== Menu ===== */
        QMenuBar {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
            border-bottom: 1px solid {p.border_subtle};
            padding: 4px;
        }}

        QMenuBar::item {{
            padding: 8px 12px;
            border-radius: 6px;
        }}

        QMenuBar::item:selected {{
            background-color: {p.bg_tertiary};
        }}

        QMenu {{
            background-color: {p.bg_elevated};
            color: {p.text_primary};
            border: 1px solid {p.border_default};
            border-radius: 12px;
            padding: 8px;
        }}

        QMenu::item {{
            padding: 10px 20px;
            border-radius: 6px;
        }}

        QMenu::item:selected {{
            background-color: {p.accent_primary};
            color: white;
        }}

        QMenu::separator {{
            height: 1px;
            background-color: {p.border_subtle};
            margin: 8px 0;
        }}

        /* ===== Tooltips ===== */
        QToolTip {{
            background-color: {p.bg_elevated};
            color: {p.text_primary};
            border: 1px solid {p.border_default};
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 12px;
        }}

        /* ===== Slider ===== */
        QSlider::groove:horizontal {{
            background-color: {p.bg_tertiary};
            height: 6px;
            border-radius: 3px;
        }}

        QSlider::handle:horizontal {{
            background-color: {p.accent_primary};
            width: 18px;
            height: 18px;
            margin: -6px 0;
            border-radius: 9px;
        }}

        QSlider::handle:horizontal:hover {{
            background-color: {p.accent_hover};
        }}

        /* ===== Checkbox ===== */
        QCheckBox {{
            color: {p.text_primary};
            spacing: 8px;
        }}

        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border-radius: 6px;
            border: 2px solid {p.border_default};
            background-color: {p.bg_secondary};
        }}

        QCheckBox::indicator:checked {{
            background-color: {p.accent_primary};
            border-color: {p.accent_primary};
        }}

        /* ===== GroupBox ===== */
        QGroupBox {{
            background-color: {p.bg_secondary};
            border: 1px solid {p.border_default};
            border-radius: 12px;
            margin-top: 20px;
            padding: 20px;
            font-weight: 600;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 16px;
            padding: 0 8px;
            color: {p.text_secondary};
        }}

        /* ===== Status Bar ===== */
        QStatusBar {{
            background-color: {p.bg_secondary};
            color: {p.text_secondary};
            border-top: 1px solid {p.border_subtle};
        }}

        /* ===== Dialog ===== */
        QDialog {{
            background-color: {p.bg_primary};
        }}
        '''


def apply_theme(app, mode: ThemeMode = ThemeMode.DARK):
    """Apply theme to QApplication"""
    theme = Theme(mode)
    app.setStyleSheet(theme.get_stylesheet())
    return theme
