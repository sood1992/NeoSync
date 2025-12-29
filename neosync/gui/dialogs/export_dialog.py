"""
Export Dialog
=============

Dialog for exporting synchronized clips.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCheckBox, QComboBox, QGroupBox,
    QFormLayout, QFileDialog, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from pathlib import Path


class ExportDialog(QDialog):
    """
    Export dialog for synchronized project

    Features:
    - Choose export format (FCP XML, Premiere XML, AAF, OTIO)
    - Configure export options
    - Choose output location
    - Generate reports
    """

    def __init__(self, project_name: str = "Untitled", parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.export_path = ""
        self.export_format = "fcpxml"
        self.options = {}

        self.setWindowTitle("Export Project")
        self.setFixedSize(550, 500)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Title
        title = QLabel("Export Synchronized Project")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        # Format selection
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout(format_group)

        self.format_buttons = QButtonGroup(self)

        formats = [
            ("fcpxml", "Final Cut Pro XML", "For Final Cut Pro X/11, DaVinci Resolve"),
            ("premiere", "Adobe Premiere Pro XML", "For Premiere Pro CC 2019+"),
            ("aaf", "Avid AAF", "For Avid Media Composer"),
            ("otio", "OpenTimelineIO", "Universal format for multiple NLEs"),
        ]

        for i, (fmt_id, name, desc) in enumerate(formats):
            row = QHBoxLayout()

            radio = QRadioButton(name)
            radio.setProperty("format_id", fmt_id)
            if i == 0:
                radio.setChecked(True)
            self.format_buttons.addButton(radio, i)
            row.addWidget(radio)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #888; font-size: 11px;")
            row.addWidget(desc_label)

            row.addStretch()
            format_layout.addLayout(row)

        layout.addWidget(format_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.include_audio = QCheckBox("Include audio tracks")
        self.include_audio.setChecked(True)
        options_layout.addWidget(self.include_audio)

        self.multicam = QCheckBox("Create multicam sequence")
        self.multicam.setChecked(False)
        options_layout.addWidget(self.multicam)

        self.relative_paths = QCheckBox("Use relative media paths")
        self.relative_paths.setChecked(False)
        options_layout.addWidget(self.relative_paths)

        layout.addWidget(options_group)

        # Report options
        report_group = QGroupBox("Reports")
        report_layout = QVBoxLayout(report_group)

        self.gen_csv = QCheckBox("Generate CSV report")
        self.gen_csv.setChecked(True)
        report_layout.addWidget(self.gen_csv)

        self.gen_html = QCheckBox("Generate HTML report")
        self.gen_html.setChecked(False)
        report_layout.addWidget(self.gen_html)

        self.gen_pdf = QCheckBox("Generate PDF report")
        self.gen_pdf.setChecked(False)
        report_layout.addWidget(self.gen_pdf)

        layout.addWidget(report_group)

        # Output location
        output_group = QGroupBox("Output Location")
        output_layout = QHBoxLayout(output_group)

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Choose output folder...")
        self.path_input.setReadOnly(True)
        output_layout.addWidget(self.path_input)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.setProperty("class", "primary")
        self.export_btn.clicked.connect(self._export)
        self.export_btn.setEnabled(False)
        btn_layout.addWidget(self.export_btn)

        layout.addLayout(btn_layout)

    def _browse(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.path_input.setText(folder)
            self.export_path = folder
            self.export_btn.setEnabled(True)

    def _export(self):
        """Accept and set export options"""
        # Get selected format
        checked = self.format_buttons.checkedButton()
        self.export_format = checked.property("format_id") if checked else "fcpxml"

        # Get options
        self.options = {
            'include_audio': self.include_audio.isChecked(),
            'multicam': self.multicam.isChecked(),
            'relative_paths': self.relative_paths.isChecked(),
            'generate_csv': self.gen_csv.isChecked(),
            'generate_html': self.gen_html.isChecked(),
            'generate_pdf': self.gen_pdf.isChecked(),
        }

        self.accept()

    def get_export_config(self) -> dict:
        """Get export configuration"""
        return {
            'path': self.export_path,
            'format': self.export_format,
            'project_name': self.project_name,
            **self.options
        }
