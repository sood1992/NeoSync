"""
Drop Zone Widget
================

Beautiful drag-and-drop area for adding clips.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QPen, QColor


class DropZone(QWidget):
    """
    Drag and drop zone for adding media files

    Features:
    - Drag and drop support
    - Click to browse
    - Visual feedback on drag
    - File filtering
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
        layout.setSpacing(20)
        layout.setContentsMargins(40, 60, 40, 60)

        # Icon (using Unicode for simplicity, can be replaced with actual icon)
        icon_label = QLabel("📁")
        icon_label.setStyleSheet("font-size: 64px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Main text
        title = QLabel("Drop your clips here")
        title.setProperty("class", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("or click to browse")
        subtitle.setProperty("class", "subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #888;")
        layout.addWidget(subtitle)

        # Browse button
        browse_btn = QPushButton("Browse Files")
        browse_btn.setProperty("class", "primary")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_files)
        browse_btn.setFixedWidth(200)
        layout.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Supported formats
        formats_label = QLabel("Supports: MP4, MOV, MXF, WAV, MP3, and more")
        formats_label.setProperty("class", "muted")
        formats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        formats_label.setStyleSheet("font-size: 12px; color: #666; margin-top: 20px;")
        layout.addWidget(formats_label)

        # Set minimum size
        self.setMinimumSize(400, 300)

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
        """Handle file drop"""
        self._dragging = False
        self.update()

        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if self._is_supported_file(path):
                files.append(path)

        if files:
            self.files_dropped.emit(files)

    def _is_supported_file(self, path: str) -> bool:
        """Check if file is supported"""
        import os
        ext = os.path.splitext(path)[1].lower()
        return ext in self.SUPPORTED_EXTENSIONS

    def paintEvent(self, event):
        """Custom paint for drop zone"""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw dashed border
        if self._dragging:
            pen = QPen(QColor("#8b5cf6"), 3, Qt.PenStyle.DashLine)
            bg_color = QColor("#8b5cf620")
        else:
            pen = QPen(QColor("#333333"), 2, Qt.PenStyle.DashLine)
            bg_color = QColor("#1a1a1a")

        painter.setPen(pen)
        painter.setBrush(bg_color)

        # Draw rounded rectangle
        rect = self.rect().adjusted(10, 10, -10, -10)
        painter.drawRoundedRect(rect, 20, 20)
