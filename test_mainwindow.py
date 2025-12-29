#!/usr/bin/env python3
"""Diagnostic test to find which MainWindow component crashes"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSplitter, QStackedWidget, QTableWidget
)
from PyQt6.QtCore import Qt

def test_step(step_name):
    print(f"[TEST] {step_name}...")

def main():
    test_step("Creating QApplication")
    app = QApplication(sys.argv)

    test_step("Creating QMainWindow")
    window = QMainWindow()
    window.setWindowTitle("NeoSync Diagnostic")
    window.setGeometry(100, 100, 1200, 800)

    test_step("Creating central widget")
    central = QWidget()
    main_layout = QHBoxLayout(central)

    test_step("Creating QSplitter")
    splitter = QSplitter(Qt.Orientation.Horizontal)

    # Left panel (simple)
    test_step("Creating left panel")
    left_panel = QWidget()
    left_layout = QVBoxLayout(left_panel)
    left_layout.addWidget(QLabel("Stats Panel"))
    left_panel.setFixedWidth(200)
    splitter.addWidget(left_panel)

    # Center panel
    test_step("Creating center panel")
    center_panel = QWidget()
    center_layout = QVBoxLayout(center_panel)

    test_step("Creating QStackedWidget")
    stack = QStackedWidget()

    test_step("Creating drop zone placeholder")
    drop_zone = QLabel("Drop Zone")
    drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
    stack.addWidget(drop_zone)

    test_step("Creating table placeholder")
    table = QTableWidget(0, 5)
    table.setHorizontalHeaderLabels(["File", "Duration", "Status", "Confidence", "Offset"])
    stack.addWidget(table)

    center_layout.addWidget(stack)

    test_step("Creating buttons")
    btn_layout = QHBoxLayout()
    btn_layout.addWidget(QPushButton("Add Clips"))
    btn_layout.addWidget(QPushButton("Sync All"))
    btn_layout.addStretch()
    center_layout.addLayout(btn_layout)

    splitter.addWidget(center_panel)

    # Right panel
    test_step("Creating right panel")
    right_panel = QWidget()
    right_layout = QVBoxLayout(right_panel)
    right_layout.addWidget(QLabel("Timeline"))
    right_layout.addWidget(QLabel("Waveform"))
    right_panel.setFixedWidth(300)
    splitter.addWidget(right_panel)

    main_layout.addWidget(splitter)

    test_step("Setting central widget")
    window.setCentralWidget(central)

    test_step("Showing window")
    window.show()

    test_step("Starting event loop - if this crashes, issue is in basic Qt setup")
    print("[SUCCESS] Basic MainWindow structure works!")
    print("\nNow testing actual widgets one by one...")

    # Now try importing actual widgets
    try:
        test_step("Importing DropZone")
        from neosync.gui.widgets.drop_zone import DropZone
        print("[OK] DropZone imported")
    except Exception as e:
        print(f"[FAIL] DropZone import: {e}")

    try:
        test_step("Importing StatsPanel")
        from neosync.gui.widgets.stats_panel import StatsPanel
        print("[OK] StatsPanel imported")
    except Exception as e:
        print(f"[FAIL] StatsPanel import: {e}")

    try:
        test_step("Importing TimelineView")
        from neosync.gui.widgets.timeline_view import TimelineView
        print("[OK] TimelineView imported")
    except Exception as e:
        print(f"[FAIL] TimelineView import: {e}")

    try:
        test_step("Importing WaveformView")
        from neosync.gui.widgets.waveform_view import WaveformView
        print("[OK] WaveformView imported")
    except Exception as e:
        print(f"[FAIL] WaveformView import: {e}")

    try:
        test_step("Importing ClipTableWidget")
        from neosync.gui.widgets.clip_table import ClipTableWidget
        print("[OK] ClipTableWidget imported")
    except Exception as e:
        print(f"[FAIL] ClipTableWidget import: {e}")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
