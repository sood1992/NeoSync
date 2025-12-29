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
    print("[DEBUG] PyQt6 imported OK")

    print("[DEBUG] Importing MainWindow...")
    from neosync.gui.main_window import MainWindow
    print("[DEBUG] MainWindow imported OK")

    print("[DEBUG] Importing theme...")
    from neosync.gui.theme import apply_theme, ThemeMode
    print("[DEBUG] Theme imported OK")

    # Skip HiDPI setup - may cause issues on some macOS versions

    # Create application
    print("[DEBUG] Creating QApplication...")
    app = QApplication(sys.argv)
    app.setApplicationName("NeoSync")
    app.setOrganizationName("NeoFox")
    app.setOrganizationDomain("neofox.com")
    print("[DEBUG] QApplication created OK")

    # Apply minimal dark theme stylesheet (skip complex theme)
    print("[DEBUG] Applying minimal theme...")
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #0a0a0a;
            color: #ffffff;
        }
        QLabel { color: #ffffff; }
        QPushButton {
            background-color: #1e1e1e;
            color: #ffffff;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 8px 16px;
        }
        QPushButton:hover { background-color: #2a2a2a; }
        QTableWidget {
            background-color: #141414;
            color: #ffffff;
            border: 1px solid #333;
        }
        QHeaderView::section {
            background-color: #1e1e1e;
            color: #888;
            border: none;
            padding: 8px;
        }
        QScrollBar:vertical {
            background-color: #0a0a0a;
            width: 10px;
        }
        QScrollBar::handle:vertical {
            background-color: #333;
            border-radius: 5px;
        }
        QSplitter::handle { background-color: #1e1e1e; }
    """)
    print("[DEBUG] Minimal theme applied OK")

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
