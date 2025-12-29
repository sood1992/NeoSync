"""
Waveform Visualization Widget
=============================

Display audio waveforms for visual sync verification and manual adjustment.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QLinearGradient, QPainterPath

import numpy as np
from typing import Optional, List

from ...core.sync_engine import ClipInfo


class WaveformView(QWidget):
    """
    Audio waveform visualization

    Features:
    - Display waveforms for reference and selected clip
    - Zoom and scroll
    - Drag to adjust offset manually
    - Visual alignment guides
    """

    offset_changed = pyqtSignal(float)  # New offset in seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reference_waveform = None
        self._reference_clip = None
        self._selected_waveform = None
        self._selected_clip = None
        self._zoom = 100  # samples per pixel
        self._offset = 0  # pixel offset for selected waveform
        self._sample_rate = 48000

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(12, 10, 12, 10)

        label = QLabel("Waveform")
        label.setStyleSheet("font-weight: 600; font-size: 13px; color: #888;")
        header.addWidget(label)

        header.addStretch()

        # Zoom controls
        zoom_label = QLabel("Zoom:")
        zoom_label.setStyleSheet("color: #555; font-size: 12px;")
        header.addWidget(zoom_label)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 1000)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(80)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        header.addWidget(self.zoom_slider)

        layout.addLayout(header)

        # Waveform canvas
        self.canvas = WaveformCanvas(self)
        self.canvas.offset_changed.connect(self._on_offset_changed)
        layout.addWidget(self.canvas)

        # Footer with offset info
        footer = QHBoxLayout()
        footer.setContentsMargins(12, 8, 12, 10)

        self.offset_label = QLabel("Offset: 0.000s")
        self.offset_label.setStyleSheet("color: #555; font-size: 11px;")
        footer.addWidget(self.offset_label)

        footer.addStretch()

        # Manual adjustment buttons
        nudge_left = QPushButton("-1 frame")
        nudge_left.setFixedSize(80, 28)
        nudge_left.setStyleSheet("""
            QPushButton {
                background-color: #1e1e1e;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
                color: #888;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #252525;
                border-color: #333;
            }
        """)
        nudge_left.clicked.connect(lambda: self._nudge(-1))
        footer.addWidget(nudge_left)

        nudge_right = QPushButton("+1 frame")
        nudge_right.setFixedSize(80, 28)
        nudge_right.setStyleSheet("""
            QPushButton {
                background-color: #1e1e1e;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
                color: #888;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #252525;
                border-color: #333;
            }
        """)
        nudge_right.clicked.connect(lambda: self._nudge(1))
        footer.addWidget(nudge_right)

        layout.addLayout(footer)

    def set_reference(self, clip: ClipInfo, waveform: Optional[np.ndarray] = None):
        """Set reference clip waveform"""
        self._reference_clip = clip
        self._reference_waveform = waveform
        self.canvas.set_reference(waveform)
        self.canvas.update()

    def set_selected(self, clip: ClipInfo, waveform: Optional[np.ndarray] = None, offset: float = 0):
        """Set selected clip waveform"""
        self._selected_clip = clip
        self._selected_waveform = waveform
        self._offset = offset
        self.canvas.set_selected(waveform, int(offset * self._sample_rate / self._zoom))
        self._update_offset_label()
        self.canvas.update()

    def _on_zoom_changed(self, value):
        """Handle zoom change"""
        self._zoom = value
        self.canvas.set_zoom(value)
        self.canvas.update()

    def _on_offset_changed(self, pixel_offset: int):
        """Handle offset change from canvas drag"""
        self._offset = pixel_offset * self._zoom / self._sample_rate
        self._update_offset_label()
        self.offset_changed.emit(self._offset)

    def _nudge(self, frames: int):
        """Nudge offset by frames"""
        if self._selected_clip:
            fps = self._selected_clip.fps or 24.0
            delta = frames / fps
            self._offset += delta
            self.canvas.nudge_offset(int(delta * self._sample_rate / self._zoom))
            self._update_offset_label()
            self.offset_changed.emit(self._offset)

    def _update_offset_label(self):
        """Update offset display"""
        self.offset_label.setText(f"Offset: {self._offset:+.3f}s")


class WaveformCanvas(QWidget):
    """Canvas for drawing waveforms - using safe rendering"""

    offset_changed = pyqtSignal(int)  # Pixel offset

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reference = None
        self._selected = None
        self._zoom = 100
        self._selected_offset = 0
        self._dragging = False
        self._drag_start = 0
        self._use_safe_rendering = True  # Disable complex painting on macOS

        self.setMinimumHeight(200)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #0d0d0d;")

    def set_reference(self, waveform: Optional[np.ndarray]):
        """Set reference waveform data"""
        self._reference = self._process_waveform(waveform) if waveform is not None else None

    def set_selected(self, waveform: Optional[np.ndarray], offset: int = 0):
        """Set selected waveform data"""
        self._selected = self._process_waveform(waveform) if waveform is not None else None
        self._selected_offset = offset

    def set_zoom(self, zoom: int):
        """Set zoom level (samples per pixel)"""
        self._zoom = zoom

    def nudge_offset(self, delta: int):
        """Nudge selected offset"""
        self._selected_offset += delta
        self.update()

    def _process_waveform(self, waveform: np.ndarray) -> np.ndarray:
        """Process waveform for display (downsample and normalize)"""
        if waveform is None or len(waveform) == 0:
            return None

        # Normalize
        max_val = np.max(np.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val

        return waveform.astype(np.float32)

    def _get_display_data(self, waveform: np.ndarray, width: int, offset: int = 0) -> np.ndarray:
        """Get waveform data for display at current zoom"""
        if waveform is None:
            return np.zeros(width)

        # Calculate visible sample range
        start_sample = max(0, -offset * self._zoom)
        end_sample = min(len(waveform), (width - offset) * self._zoom)

        if start_sample >= end_sample:
            return np.zeros(width)

        # Extract visible portion
        visible = waveform[int(start_sample):int(end_sample)]

        # Downsample for display
        if len(visible) > width:
            # Take max/min for each pixel
            chunk_size = len(visible) // width
            if chunk_size > 0:
                trimmed = visible[:chunk_size * width]
                reshaped = trimmed.reshape(-1, chunk_size)
                # Get envelope (max absolute value per chunk)
                display = np.max(np.abs(reshaped), axis=1)
            else:
                display = np.abs(visible[:width])
        else:
            display = np.abs(visible)

        return display

    def paintEvent(self, event):
        """Paint the waveforms - with safe mode for macOS stability"""
        # Always use safe rendering to avoid macOS crashes
        if self._use_safe_rendering:
            self._paint_safe(event)
            return

    def _paint_safe(self, event):
        """Safe painting mode - minimal operations to avoid macOS crashes"""
        painter = QPainter(self)
        try:
            if not painter.isActive():
                return

            # Simple solid background
            painter.fillRect(self.rect(), QColor("#0d0d0d"))

            height = self.height()
            width = self.width()
            mid_y = height // 2

            # Draw simple center line
            painter.setPen(QColor("#1a1a1a"))
            painter.drawLine(0, mid_y, width, mid_y)

            # Draw simple placeholder rectangles for waveforms (no complex paths or gradients)
            if self._reference is not None:
                # Reference waveform area (top half, blue)
                painter.setBrush(QColor("#3b82f6"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(10, 20, width - 20, mid_y - 40)

            if self._selected is not None:
                # Selected waveform area (bottom half, purple)
                painter.setBrush(QColor("#8b5cf6"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(10, mid_y + 20, width - 20, mid_y - 40)

            # Draw alignment guide line
            painter.setPen(QColor("#22c55e"))
            painter.drawLine(width // 2, 0, width // 2, height)

        except Exception as e:
            print(f"[ERROR] WaveformCanvas._paint_safe: {e}")
        finally:
            painter.end()

    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start = event.pos().x()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging"""
        if self._dragging:
            delta = event.pos().x() - self._drag_start
            self._selected_offset += delta
            self._drag_start = event.pos().x()
            self.offset_changed.emit(self._selected_offset)
            self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self._dragging = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
