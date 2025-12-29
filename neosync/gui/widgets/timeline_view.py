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
        header.setContentsMargins(16, 8, 16, 8)

        label = QLabel("Timeline")
        label.setStyleSheet("font-weight: 600; font-size: 13px;")
        header.addWidget(label)

        header.addStretch()

        # Zoom controls
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedSize(28, 28)
        zoom_out_btn.clicked.connect(self._zoom_out)
        header.addWidget(zoom_out_btn)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(1, 200)
        self.zoom_slider.setValue(20)
        self.zoom_slider.setFixedWidth(120)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        header.addWidget(self.zoom_slider)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(28, 28)
        zoom_in_btn.clicked.connect(self._zoom_in)
        header.addWidget(zoom_in_btn)

        # Fit button
        fit_btn = QPushButton("Fit")
        fit_btn.setFixedWidth(50)
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
            camera_id = clip.camera_id or "Unknown"
            if camera_id not in self._tracks:
                self._tracks[camera_id] = []
            self._tracks[camera_id].append(clip)

        # Sort clips in each track by offset
        for camera_id in self._tracks:
            self._tracks[camera_id].sort(key=lambda c: c.sync_offset_seconds)

        # Calculate timeline duration
        if self._clips:
            min_offset = min(c.sync_offset_seconds for c in self._clips)
            max_end = max(c.sync_offset_seconds + c.duration for c in self._clips)
            self._offset = min_offset
            self._duration = max_end - min_offset
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
    """Canvas widget for drawing the timeline"""

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
        self.setMouseTracking(True)

    def set_data(self, tracks: dict, offset: float, duration: float, zoom: float):
        """Set timeline data"""
        self._tracks = tracks
        self._offset = offset
        self._duration = duration
        self._zoom = zoom

    def paintEvent(self, event):
        """Paint the timeline"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor("#141414"))

        if not self._tracks:
            # Empty state
            painter.setPen(QColor("#666"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No clips to display")
            return

        # Draw time ruler
        self._draw_ruler(painter)

        # Draw tracks
        y = self.HEADER_HEIGHT
        for i, (camera_id, clips) in enumerate(self._tracks.items()):
            color = self.TRACK_COLORS[i % len(self.TRACK_COLORS)]
            self._draw_track(painter, camera_id, clips, y, color, i)
            y += self.TRACK_HEIGHT

    def _draw_ruler(self, painter: QPainter):
        """Draw time ruler at top"""
        painter.fillRect(0, 0, self.width(), self.HEADER_HEIGHT, QColor("#1a1a1a"))

        if self._duration <= 0:
            return

        # Calculate tick interval
        if self._zoom > 50:
            interval = 1  # 1 second
        elif self._zoom > 20:
            interval = 5
        elif self._zoom > 5:
            interval = 10
        elif self._zoom > 1:
            interval = 30
        else:
            interval = 60

        painter.setPen(QColor("#666"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        # Draw ticks
        t = 0
        while t <= self._duration:
            x = int(t * self._zoom) + 50
            painter.drawLine(x, self.HEADER_HEIGHT - 10, x, self.HEADER_HEIGHT)

            # Time label
            label = self._format_time(t)
            painter.drawText(x - 20, 5, 40, 15, Qt.AlignmentFlag.AlignCenter, label)

            t += interval

    def _draw_track(self, painter: QPainter, camera_id: str, clips: list, y: int, color: str, track_idx: int):
        """Draw a single track with clips"""
        # Track background
        track_rect = QRect(0, y, self.width(), self.TRACK_HEIGHT)
        bg_color = QColor("#1e1e1e") if track_idx % 2 == 0 else QColor("#1a1a1a")
        painter.fillRect(track_rect, bg_color)

        # Track label
        painter.setPen(QColor("#888"))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(5, y + 5, 45, self.TRACK_HEIGHT - 10, Qt.AlignmentFlag.AlignVCenter, camera_id[:8])

        # Draw clips
        for clip in clips:
            clip_start = clip.sync_offset_seconds - self._offset
            clip_x = int(clip_start * self._zoom) + 50
            clip_width = max(20, int(clip.duration * self._zoom))

            # Clip rectangle
            clip_rect = QRect(clip_x, y + 5, clip_width, self.TRACK_HEIGHT - 10)

            # Color based on sync quality
            clip_color = self.QUALITY_COLORS.get(clip.sync_quality, "#666")

            # Gradient fill
            gradient = QLinearGradient(clip_x, y, clip_x, y + self.TRACK_HEIGHT)
            gradient.setColorAt(0, QColor(clip_color))
            gradient.setColorAt(1, QColor(clip_color).darker(130))

            painter.setBrush(gradient)
            painter.setPen(QPen(QColor(clip_color).lighter(120), 1))
            painter.drawRoundedRect(clip_rect, 4, 4)

            # Clip name
            if clip_width > 50:
                painter.setPen(QColor("#fff"))
                font.setPointSize(9)
                font.setBold(False)
                painter.setFont(font)

                text_rect = clip_rect.adjusted(8, 0, -8, 0)
                text = clip.file_name
                if len(text) > 20:
                    text = text[:18] + "..."
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)

    def _format_time(self, seconds: float) -> str:
        """Format seconds as timecode"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
