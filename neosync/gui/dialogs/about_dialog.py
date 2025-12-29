"""
About Dialog
============

About NeoSync dialog with version info and credits.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont

from ... import __version__


class AboutDialog(QDialog):
    """About NeoSync dialog"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("About NeoSync")
        self.setFixedSize(400, 350)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo text
        logo = QLabel("🎬 NeoSync")
        logo.setStyleSheet("""
            font-size: 36px;
            font-weight: 700;
            color: #8b5cf6;
        """)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        # Tagline
        tagline = QLabel("Professional Audio/Video Synchronization")
        tagline.setStyleSheet("color: #888; font-size: 14px;")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline)

        # Version
        version = QLabel(f"Version {__version__}")
        version.setStyleSheet("color: #666; font-size: 12px; margin-top: 16px;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        # Features
        features = QLabel("""
• Multi-stage audio waveform matching
• GPU-accelerated processing
• Visual sync for silent footage
• Export to FCP, Premiere, Avid, OTIO
• Sub-sample accuracy
        """)
        features.setStyleSheet("color: #aaa; font-size: 12px; margin-top: 16px;")
        features.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(features)

        layout.addStretch()

        # Copyright
        copyright_label = QLabel("© 2024 NeoFox. All rights reserved.")
        copyright_label.setStyleSheet("color: #666; font-size: 11px;")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copyright_label)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
