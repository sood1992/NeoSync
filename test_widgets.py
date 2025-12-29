#!/usr/bin/env python3
"""Test each widget individually to find which one crashes"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

def test_widget(name, widget_class, *args):
    print(f"[TEST] Creating {name}...", end=" ", flush=True)
    try:
        widget = widget_class(*args)
        print("[OK]")
        return widget
    except Exception as e:
        print(f"[FAIL] {e}")
        return None

def main():
    print("=" * 50)
    print("Widget Crash Diagnostic")
    print("=" * 50)

    app = QApplication(sys.argv)
    print("[OK] QApplication created\n")

    window = QMainWindow()
    central = QWidget()
    layout = QVBoxLayout(central)

    # Test each widget
    print("Testing widget creation (before adding to layout):\n")

    # Test DropZone
    try:
        from neosync.gui.widgets.drop_zone import DropZone
        drop = test_widget("DropZone", DropZone)
        if drop:
            layout.addWidget(drop)
    except ImportError as e:
        print(f"[SKIP] DropZone import failed: {e}")

    # Test StatsPanel
    try:
        from neosync.gui.widgets.stats_panel import StatsPanel
        stats = test_widget("StatsPanel", StatsPanel)
        if stats:
            layout.addWidget(stats)
    except ImportError as e:
        print(f"[SKIP] StatsPanel import failed: {e}")

    # Test TimelineView
    try:
        from neosync.gui.widgets.timeline_view import TimelineView
        timeline = test_widget("TimelineView", TimelineView)
        if timeline:
            layout.addWidget(timeline)
    except ImportError as e:
        print(f"[SKIP] TimelineView import failed: {e}")

    # Test WaveformView
    try:
        from neosync.gui.widgets.waveform_view import WaveformView
        waveform = test_widget("WaveformView", WaveformView)
        if waveform:
            layout.addWidget(waveform)
    except ImportError as e:
        print(f"[SKIP] WaveformView import failed: {e}")

    # Test ClipTableWidget
    try:
        from neosync.gui.widgets.clip_table import ClipTableWidget
        table = test_widget("ClipTableWidget", ClipTableWidget)
        if table:
            layout.addWidget(table)
    except ImportError as e:
        print(f"[SKIP] ClipTableWidget import failed: {e}")

    print("\n[TEST] Setting central widget...")
    window.setCentralWidget(central)
    print("[OK]")

    print("[TEST] Showing window...")
    window.show()
    print("[OK]")

    print("[TEST] Starting event loop...")
    print("\nIf this crashes, one of the widgets above has a paint issue.")
    print("Check which was the last [OK] before the crash.\n")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
