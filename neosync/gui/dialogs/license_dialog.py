"""
License Dialog
==============

Dialog for entering and managing license keys.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ...core.license_manager import LicenseManager


class LicenseDialog(QDialog):
    """
    License activation dialog

    Features:
    - Enter license key
    - Show current license status
    - Trial mode info
    """

    def __init__(self, license_manager: LicenseManager, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager

        self.setWindowTitle("License Activation")
        self.setFixedSize(500, 350)
        self.setModal(True)

        self._setup_ui()
        self._update_status()

    def _setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        # Logo/Title
        title = QLabel("NeoSync Pro")
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: 700;
            color: #8b5cf6;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Status frame
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        status_layout = QVBoxLayout(status_frame)

        self.status_icon = QLabel("🔒")
        self.status_icon.setStyleSheet("font-size: 32px;")
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_icon)

        self.status_label = QLabel("Trial Mode")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_label)

        self.status_detail = QLabel("5 clips limit")
        self.status_detail.setStyleSheet("color: #888;")
        self.status_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_detail)

        layout.addWidget(status_frame)

        # License key input
        key_label = QLabel("Enter License Key:")
        key_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(key_label)

        key_layout = QHBoxLayout()

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("NEOS-XXXX-XXXX-XXXX-XXXX")
        self.key_input.setFont(QFont("Consolas", 12))
        self.key_input.textChanged.connect(self._format_key)
        key_layout.addWidget(self.key_input)

        self.activate_btn = QPushButton("Activate")
        self.activate_btn.setProperty("class", "primary")
        self.activate_btn.clicked.connect(self._activate)
        key_layout.addWidget(self.activate_btn)

        layout.addLayout(key_layout)

        # Buttons
        btn_layout = QHBoxLayout()

        self.deactivate_btn = QPushButton("Deactivate License")
        self.deactivate_btn.clicked.connect(self._deactivate)
        self.deactivate_btn.setVisible(False)
        btn_layout.addWidget(self.deactivate_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _format_key(self, text: str):
        """Auto-format license key as user types"""
        # Remove non-alphanumeric
        clean = ''.join(c for c in text.upper() if c.isalnum())

        # Add dashes
        parts = []
        # First part is prefix (NEOS, NEOFOX, or TEAM)
        if clean.startswith('NEOFOX'):
            parts.append(clean[:6])
            clean = clean[6:]
        elif clean.startswith('NEOS'):
            parts.append(clean[:4])
            clean = clean[4:]
        elif clean.startswith('TEAM'):
            parts.append(clean[:4])
            clean = clean[4:]
        else:
            # Haven't typed enough
            pass

        # Remaining parts are 4 chars each
        while clean:
            parts.append(clean[:4])
            clean = clean[4:]

        formatted = '-'.join(parts)

        # Update without triggering signal
        self.key_input.blockSignals(True)
        self.key_input.setText(formatted)
        self.key_input.blockSignals(False)

    def _update_status(self):
        """Update license status display"""
        if self.license_manager.is_licensed():
            info = self.license_manager.get_license_info()
            self.status_icon.setText("✓")
            self.status_icon.setStyleSheet("font-size: 32px; color: #22c55e;")
            self.status_label.setText(f"Licensed ({info.license_type.upper()})")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #22c55e;")
            self.status_detail.setText(f"Up to {info.max_clips} clips")
            self.deactivate_btn.setVisible(True)
            self.key_input.setEnabled(False)
            self.activate_btn.setEnabled(False)
        else:
            self.status_icon.setText("🔒")
            self.status_icon.setStyleSheet("font-size: 32px;")
            self.status_label.setText("Trial Mode")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: 600;")
            self.status_detail.setText("Limited to 5 clips")
            self.deactivate_btn.setVisible(False)
            self.key_input.setEnabled(True)
            self.activate_btn.setEnabled(True)

    def _activate(self):
        """Attempt to activate license"""
        key = self.key_input.text().strip()

        if not key:
            QMessageBox.warning(self, "Error", "Please enter a license key.")
            return

        success, message = self.license_manager.activate(key)

        if success:
            QMessageBox.information(self, "Success", message)
            self._update_status()
        else:
            QMessageBox.warning(self, "Activation Failed", message)

    def _deactivate(self):
        """Deactivate current license"""
        reply = QMessageBox.question(
            self,
            "Confirm Deactivation",
            "Are you sure you want to deactivate your license?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.license_manager.deactivate()
            self._update_status()
            QMessageBox.information(self, "Deactivated", "License has been deactivated.")
