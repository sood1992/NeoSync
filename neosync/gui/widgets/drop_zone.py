"""
Drop Zone Widget
================

Modern drag-and-drop area for adding clips.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QPen, QColor, QFont


class DropZone(QWidget):
    """
    Modern drag and drop zone for adding media files

    Features:
    - Clean minimal design
    - Drag and drop support
    - Click to browse
    - Visual feedback on drag
    - File and folder support
    """

    files_dropped = pyqtSignal(list)  # Emits list of file paths

    SUPPORTED_EXTENSIONS = {
        '.mp4', '.mov', '.avi', '.mkv', '.mxf', '.m4v', '.wmv',  # Video
        '.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg',  # Audio
        '.r3d', '.braw', '.ari',  # RAW formats
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._dragging = False
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        layout.setContentsMargins(60, 80, 60, 80)

        # Upload icon (clean SVG-style arrow)
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(80, 80)
        self.icon_label.setStyleSheet("""
            QLabel {
                background: transparent;
            }
        """)
        layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Main text
        title = QLabel("Drop media files or folders")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            color: #e0e0e0;
            letter-spacing: -0.3px;
        """)
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("or browse to select")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
        """)
        layout.addWidget(subtitle)

        # Browse button
        browse_btn = QPushButton("Browse Files")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_files)
        browse_btn.setFixedSize(140, 42)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #8b5cf6;
            }
            QPushButton:pressed {
                background-color: #6d28d9;
            }
        """)
        layout.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Spacer
        layout.addSpacing(16)

        # Supported formats
        formats_label = QLabel("MP4 · MOV · MXF · WAV · MP3 · Folders")
        formats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        formats_label.setStyleSheet("""
            font-size: 12px;
            color: #4a4a4a;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(formats_label)

        # Set minimum size
        self.setMinimumSize(400, 320)

    def _browse_files(self):
        """Open file browser dialog"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Media Files",
            "",
            "Media Files (*.mp4 *.mov *.avi *.mkv *.mxf *.wav *.mp3 *.m4a);;All Files (*.*)"
        )
        if files:
            self.files_dropped.emit(files)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._dragging = True
            self.update()

    def dragLeaveEvent(self, event):
        """Handle drag leave"""
        self._dragging = False
        self.update()

    def dropEvent(self, event: QDropEvent):
        """Handle file and folder drop"""
        self._dragging = False
        self.update()

        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if self._is_directory(path):
                # Recursively collect all supported files from the folder
                files.extend(self._collect_files_from_folder(path))
            elif self._is_supported_file(path):
                files.append(path)

        if files:
            self.files_dropped.emit(files)

    def _is_directory(self, path: str) -> bool:
        """Check if path is a directory"""
        return os.path.isdir(path)

    def _collect_files_from_folder(self, folder_path: str) -> list:
        """Recursively collect all supported media files from a folder"""
        collected_files = []

        try:
            for root, dirs, files in os.walk(folder_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                for file in files:
                    # Skip hidden files
                    if file.startswith('.'):
                        continue
                    file_path = os.path.join(root, file)
                    if self._is_supported_file(file_path):
                        collected_files.append(file_path)
        except (PermissionError, OSError):
            # Skip folders we can't access
            pass

        # Sort files for consistent ordering
        collected_files.sort()
        return collected_files

    def _is_supported_file(self, path: str) -> bool:
        """Check if file is supported"""
        ext = os.path.splitext(path)[1].lower()
        return ext in self.SUPPORTED_EXTENSIONS

    def paintEvent(self, event):
        """Custom paint for drop zone - with crash protection"""
        try:
            print("[DEBUG] DropZone.paintEvent starting...")
            super().paintEvent(event)
            print("[DEBUG] DropZone.paintEvent super() done")

            painter = QPainter(self)
            print("[DEBUG] DropZone.paintEvent QPainter created")
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            print("[DEBUG] DropZone.paintEvent antialiasing set")

            rect = self.rect().adjusted(20, 20, -20, -20)

            # Draw background and border
            if self._dragging:
                # Active drop state
                bg_color = QColor("#7c3aed")
                bg_color.setAlpha(15)
                border_color = QColor("#7c3aed")
                border_width = 2
            else:
                # Default state
                bg_color = QColor("#141414")
                border_color = QColor("#2a2a2a")
                border_width = 1

            # Fill background
            painter.setBrush(bg_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 16, 16)

            # Draw dashed border
            pen = QPen(border_color, border_width, Qt.PenStyle.DashLine)
            pen.setDashPattern([8, 6])
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 16, 16)

            # Draw upload icon
            self._draw_upload_icon(painter, rect)
        except Exception as e:
            print(f"[ERROR] DropZone.paintEvent: {e}")

    def _draw_upload_icon(self, painter: QPainter, rect):
        """Draw a clean upload arrow icon"""
        icon_size = 48
        icon_x = rect.center().x() - icon_size // 2
        icon_y = rect.top() + 50

        # Icon color
        if self._dragging:
            color = QColor("#7c3aed")
        else:
            color = QColor("#404040")

        pen = QPen(color, 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        center_x = icon_x + icon_size // 2
        center_y = icon_y + icon_size // 2

        # Draw arrow pointing up
        arrow_height = 18
        arrow_width = 14

        # Arrow stem
        painter.drawLine(
            center_x, center_y + arrow_height // 2,
            center_x, center_y - arrow_height // 2
        )

        # Arrow head
        painter.drawLine(
            center_x, center_y - arrow_height // 2,
            center_x - arrow_width // 2, center_y - arrow_height // 2 + arrow_width // 2
        )
        painter.drawLine(
            center_x, center_y - arrow_height // 2,
            center_x + arrow_width // 2, center_y - arrow_height // 2 + arrow_width // 2
        )

        # Draw base line (folder/tray)
        tray_y = center_y + arrow_height // 2 + 8
        tray_width = 28
        painter.drawLine(
            center_x - tray_width // 2, tray_y,
            center_x + tray_width // 2, tray_y
        )
