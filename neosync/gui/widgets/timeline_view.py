"""
Timeline View Widget
====================

Visual timeline showing all synced clips aligned on a common timeline.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QPushButton, QSlider
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QLinearGradient

from ...core.sync_engine import ClipInfo, SyncQuality


class TimelineView(QWidget):
    """
    Visual timeline showing synced clips

    Features:
    - Horizontal scrolling timeline
    - Zoom in/out
    - Clips color-coded by sync quality
    - Camera tracks (one track per camera)
    - Playhead position
    - Click to select clip
    """

    clip_selected = pyqtSignal(object)  # ClipInfo
    time_clicked = pyqtSignal(float)  # Seconds

    TRACK_HEIGHT = 50
    HEADER_HEIGHT = 30
    MIN_CLIP_WIDTH = 20

    QUALITY_COLORS = {
        SyncQuality.EXCELLENT: "#22c55e",
        SyncQuality.GOOD: "#84cc16",
        SyncQuality.FAIR: "#eab308",
        SyncQuality.POOR: "#f97316",
        SyncQuality.FAILED: "#ef4444",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clips = []
        self._tracks = {}  # camera_id -> [clips]
        self._zoom = 1.0  # pixels per second
        self._offset = 0.0  # timeline start offset
        self._duration = 0.0  # total timeline duration
        self._selected_clip = None
        self._playhead = 0.0  # current time position

        self.setMinimumHeight(150)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with zoom controls
        header = QHBoxLayout()
        header.setContentsMargins(12, 8, 12, 8)

        label = QLabel("Timeline")
        label.setStyleSheet("font-weight: 600; font-size: 13px; color: #888;")
        header.addWidget(label)

        header.addStretch()

        # Zoom controls with clean styling
        btn_style = """
            QPushButton {
                background-color: #1e1e1e;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
                color: #888;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #252525;
                border-color: #333;
            }
        """

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedSize(28, 28)
        zoom_out_btn.setStyleSheet(btn_style)
        zoom_out_btn.clicked.connect(self._zoom_out)
        header.addWidget(zoom_out_btn)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(1, 200)
        self.zoom_slider.setValue(20)
        self.zoom_slider.setFixedWidth(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        header.addWidget(self.zoom_slider)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(28, 28)
        zoom_in_btn.setStyleSheet(btn_style)
        zoom_in_btn.clicked.connect(self._zoom_in)
        header.addWidget(zoom_in_btn)

        # Fit button
        fit_btn = QPushButton("Fit")
        fit_btn.setFixedSize(50, 28)
        fit_btn.setStyleSheet(btn_style)
        fit_btn.clicked.connect(self._fit_to_view)
        header.addWidget(fit_btn)

        layout.addLayout(header)

        # Scroll area for timeline
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Timeline canvas
        self.canvas = TimelineCanvas(self)
        self.scroll_area.setWidget(self.canvas)

        layout.addWidget(self.scroll_area)

    def set_clips(self, clips: list):
        """Set clips to display"""
        self._clips = clips
        self._organize_tracks()
        self._update_canvas()

    def _organize_tracks(self):
        """Organize clips into camera tracks"""
        self._tracks = {}

        for clip in self._clips:
            if clip is None:
                continue
            camera_id = clip.camera_id or "Unknown"
            if camera_id not in self._tracks:
                self._tracks[camera_id] = []
            self._tracks[camera_id].append(clip)

        # Sort clips in each track by offset (with safe fallback for None values)
        for camera_id in self._tracks:
            self._tracks[camera_id].sort(
                key=lambda c: c.sync_offset_seconds if c.sync_offset_seconds is not None else 0.0
            )

        # Calculate timeline duration with safe fallbacks
        if self._clips:
            try:
                offsets = [c.sync_offset_seconds for c in self._clips if c and c.sync_offset_seconds is not None]
                durations = [c.duration for c in self._clips if c and c.duration is not None]

                if offsets and durations:
                    min_offset = min(offsets)
                    max_end = max(
                        (c.sync_offset_seconds or 0) + (c.duration or 0)
                        for c in self._clips if c
                    )
                    self._offset = min_offset
                    self._duration = max_end - min_offset
                else:
                    self._offset = 0
                    self._duration = 10  # Default 10 seconds
            except (ValueError, TypeError):
                self._offset = 0
                self._duration = 10
        else:
            self._offset = 0
            self._duration = 0

    def _update_canvas(self):
        """Update the canvas size and redraw"""
        if self._duration > 0:
            width = int(self._duration * self._zoom) + 200
        else:
            width = self.width()

        height = self.HEADER_HEIGHT + len(self._tracks) * self.TRACK_HEIGHT + 20
        self.canvas.setFixedSize(max(width, self.width()), max(height, 100))
        self.canvas.set_data(self._tracks, self._offset, self._duration, self._zoom)
        self.canvas.update()

    def _on_zoom_changed(self, value):
        """Handle zoom slider change"""
        self._zoom = value / 2.0  # 0.5 to 100 pixels per second
        self._update_canvas()

    def _zoom_in(self):
        """Zoom in"""
        self.zoom_slider.setValue(min(200, self.zoom_slider.value() + 10))

    def _zoom_out(self):
        """Zoom out"""
        self.zoom_slider.setValue(max(1, self.zoom_slider.value() - 10))

    def _fit_to_view(self):
        """Fit timeline to view"""
        if self._duration > 0:
            available_width = self.scroll_area.width() - 50
            ideal_zoom = available_width / self._duration
            slider_value = int(ideal_zoom * 2)
            self.zoom_slider.setValue(max(1, min(200, slider_value)))

    def update_clip(self, clip: ClipInfo):
        """Update a single clip"""
        self._organize_tracks()
        self._update_canvas()


class TimelineCanvas(QWidget):
    """Canvas widget for drawing the timeline - using safe rendering"""

    TRACK_HEIGHT = 50
    HEADER_HEIGHT = 30
    TRACK_COLORS = ["#3b82f6", "#ef4444", "#22c55e", "#eab308", "#8b5cf6", "#ec4899"]

    QUALITY_COLORS = {
        SyncQuality.EXCELLENT: "#22c55e",
        SyncQuality.GOOD: "#84cc16",
        SyncQuality.FAIR: "#eab308",
        SyncQuality.POOR: "#f97316",
        SyncQuality.FAILED: "#ef4444",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks = {}
        self._offset = 0
        self._duration = 0
        self._zoom = 10
        self._use_safe_rendering = True  # Disable complex painting on macOS
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #0d0d0d;")

    def set_data(self, tracks: dict, offset: float, duration: float, zoom: float):
        """Set timeline data"""
        self._tracks = tracks
        self._offset = offset
        self._duration = duration
        self._zoom = zoom

    def paintEvent(self, event):
        """Paint the timeline - with safe mode for macOS stability"""
        # Always use safe rendering to avoid macOS crashes
        if self._use_safe_rendering or not self._tracks:
            # Use simple solid color rendering - no gradients or font modifications
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

            if not self._tracks:
                return

            # Draw simple header bar
            painter.fillRect(0, 0, self.width(), self.HEADER_HEIGHT, QColor("#1a1a1a"))

            # Draw tracks with simple colored rectangles (no gradients, no font changes)
            y = self.HEADER_HEIGHT
            for i, (camera_id, clips) in enumerate(self._tracks.items()):
                # Track background - alternating colors
                bg_color = QColor("#1e1e1e") if i % 2 == 0 else QColor("#1a1a1a")
                painter.fillRect(0, y, self.width(), self.TRACK_HEIGHT, bg_color)

                # Draw clips as simple rectangles
                for clip in clips:
                    clip_offset = clip.sync_offset_seconds if clip.sync_offset_seconds is not None else 0.0
                    clip_duration = clip.duration if clip.duration is not None else 1.0

                    clip_start = clip_offset - self._offset
                    clip_x = int(clip_start * self._zoom) + 50
                    clip_width = max(20, int(clip_duration * self._zoom))

                    # Color based on sync quality
                    sync_quality = clip.sync_quality if clip.sync_quality is not None else SyncQuality.FAILED
                    clip_color = self.QUALITY_COLORS.get(sync_quality, "#666")

                    # Simple filled rectangle - no gradient
                    painter.setBrush(QColor(clip_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(clip_x, y + 5, clip_width, self.TRACK_HEIGHT - 10)

                y += self.TRACK_HEIGHT

        except Exception as e:
            print(f"[ERROR] TimelineCanvas._paint_safe: {e}")
        finally:
            painter.end()

    def _format_time(self, seconds: float) -> str:
        """Format seconds as timecode"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
