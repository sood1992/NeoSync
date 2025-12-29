"""
NeoSync Entry Point
===================

Run with: python -m neosync
"""

import sys
import os

# Ensure the package directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    """Main entry point for NeoSync"""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont

    from neosync.gui.main_window import MainWindow
    from neosync.gui.theme import apply_theme, ThemeMode

    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("NeoSync")
    app.setOrganizationName("NeoFox")
    app.setOrganizationDomain("neofox.com")

    # Set default font
    font = QFont("SF Pro Display", 13)
    if not font.exactMatch():
        font = QFont("Segoe UI", 13)
    if not font.exactMatch():
        font = QFont("Helvetica Neue", 13)
    app.setFont(font)

    # Apply dark theme
    apply_theme(app, ThemeMode.DARK)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
