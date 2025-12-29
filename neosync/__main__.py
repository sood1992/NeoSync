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
    print("[DEBUG] Starting NeoSync...")

    print("[DEBUG] Importing PyQt6...")
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
    print("[DEBUG] PyQt6 imported OK")

    print("[DEBUG] Importing MainWindow...")
    from neosync.gui.main_window import MainWindow
    print("[DEBUG] MainWindow imported OK")

    print("[DEBUG] Importing theme...")
    from neosync.gui.theme import apply_theme, ThemeMode
    print("[DEBUG] Theme imported OK")

    # High DPI support
    print("[DEBUG] Setting up HiDPI...")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    print("[DEBUG] Creating QApplication...")
    app = QApplication(sys.argv)
    app.setApplicationName("NeoSync")
    app.setOrganizationName("NeoFox")
    app.setOrganizationDomain("neofox.com")
    print("[DEBUG] QApplication created OK")

    # Don't set custom font - let system use its default

    # Apply dark theme
    print("[DEBUG] Applying theme...")
    apply_theme(app, ThemeMode.DARK)
    print("[DEBUG] Theme applied OK")

    # Create and show main window
    print("[DEBUG] Creating MainWindow...")
    window = MainWindow()
    print("[DEBUG] MainWindow created OK")

    print("[DEBUG] Showing window...")
    window.show()
    print("[DEBUG] Window shown OK")

    # Run event loop
    print("[DEBUG] Starting event loop...")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
