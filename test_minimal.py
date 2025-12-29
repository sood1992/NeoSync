#!/usr/bin/env python3
"""Minimal PyQt6 test to check if Qt works at all"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget

def main():
    print("[TEST] Creating QApplication...")
    app = QApplication(sys.argv)

    print("[TEST] Creating window...")
    window = QMainWindow()
    window.setWindowTitle("Minimal Test")
    window.setGeometry(100, 100, 400, 300)

    # Simple widget
    central = QWidget()
    layout = QVBoxLayout(central)
    label = QLabel("If you can see this, PyQt6 works!")
    layout.addWidget(label)
    window.setCentralWidget(central)

    print("[TEST] Showing window...")
    window.show()

    print("[TEST] Starting event loop...")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
