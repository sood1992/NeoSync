"""
Progress Dialog
===============

Modal dialog for showing progress during long operations.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


class ProgressDialog(QDialog):
    """
    Progress dialog for analysis and sync operations

    Features:
    - Progress bar with percentage
    - Current file being processed
    - Cancel button
    - Elapsed time
    """

    cancelled = pyqtSignal()

    def __init__(self, title: str = "Processing...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(500, 200)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
        )

        self._elapsed_seconds = 0
        self._setup_ui()
        self._start_timer()

    def _setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        self.title_label = QLabel("Processing...")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(self.title_label)

        # Current file
        self.file_label = QLabel("Preparing...")
        self.file_label.setStyleSheet("color: #888; font-size: 13px;")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(20)
        layout.addWidget(self.progress_bar)

        # Bottom row
        bottom = QHBoxLayout()

        # Elapsed time
        self.time_label = QLabel("Elapsed: 0:00")
        self.time_label.setStyleSheet("color: #666; font-size: 12px;")
        bottom.addWidget(self.time_label)

        bottom.addStretch()

        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setProperty("class", "danger")
        self.cancel_btn.clicked.connect(self._on_cancel)
        bottom.addWidget(self.cancel_btn)

        layout.addLayout(bottom)

    def _start_timer(self):
        """Start elapsed time timer"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_time)
        self.timer.start(1000)

    def _update_time(self):
        """Update elapsed time display"""
        self._elapsed_seconds += 1
        minutes = self._elapsed_seconds // 60
        seconds = self._elapsed_seconds % 60
        self.time_label.setText(f"Elapsed: {minutes}:{seconds:02d}")

    def set_progress(self, value: float, message: str = ""):
        """Update progress (0-1)"""
        self.progress_bar.setValue(int(value * 100))
        if message:
            self.file_label.setText(message)

    def set_title(self, title: str):
        """Update title"""
        self.title_label.setText(title)

    def _on_cancel(self):
        """Handle cancel button"""
        self.cancelled.emit()
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling...")

    def finish(self, message: str = "Complete!"):
        """Mark as complete"""
        self.timer.stop()
        self.progress_bar.setValue(100)
        self.file_label.setText(message)
        self.cancel_btn.setText("Close")
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.accept)

    def closeEvent(self, event):
        """Handle close"""
        self.timer.stop()
        self.cancelled.emit()
        super().closeEvent(event)
