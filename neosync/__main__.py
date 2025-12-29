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

    # Don't set custom font - let system use its default

    # Apply dark theme
    apply_theme(app, ThemeMode.DARK)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
