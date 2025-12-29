"""
Stats Panel Widget
==================

Clean, modern statistics display panel.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen

from ...core.sync_engine import SyncProject, SyncQuality


class StatCard(QFrame):
    """Clean stat card with minimal design"""

    def __init__(self, title: str, value: str = "0", color: str = "#8b5cf6", parent=None):
        super().__init__(parent)
        self._title = title
        self._value = value
        self._color = color

        self.setStyleSheet("""
            StatCard {
                background-color: #161616;
                border: 1px solid #232323;
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)

        # Value
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"""
            font-size: 26px;
            font-weight: 700;
            color: {color};
            letter-spacing: -1px;
        """)
        layout.addWidget(self.value_label)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 10px;
            color: #555;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 500;
        """)
        layout.addWidget(title_label)

        self.setFixedHeight(72)

    def set_value(self, value: str):
        """Update the value"""
        self._value = value
        self.value_label.setText(value)


class QualityBar(QWidget):
    """Visual bar showing sync quality distribution"""

    COLORS = {
        SyncQuality.EXCELLENT: "#10b981",
        SyncQuality.GOOD: "#84cc16",
        SyncQuality.FAIR: "#f59e0b",
        SyncQuality.POOR: "#f97316",
        SyncQuality.FAILED: "#ef4444",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts = {}
        self.setFixedHeight(6)

    def set_counts(self, counts: dict):
        """Set quality counts"""
        self._counts = counts
        self.update()

    def paintEvent(self, event):
        """Paint the quality bar - with crash protection"""
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            total = sum(self._counts.values()) if self._counts else 0

            # Background
            painter.setBrush(QColor("#1e1e1e"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect(), 3, 3)

            if total == 0:
                return

            x = 0
            height = self.height()

            for quality in [SyncQuality.EXCELLENT, SyncQuality.GOOD, SyncQuality.FAIR,
                           SyncQuality.POOR, SyncQuality.FAILED]:
                count = self._counts.get(quality, 0)
                if count > 0:
                    width = int((count / total) * self.width())
                    color = QColor(self.COLORS.get(quality, "#666"))
                    painter.setBrush(color)

                    # Handle corners
                    if x == 0:
                        painter.drawRoundedRect(x, 0, max(width, 3), height, 3, 3)
                    else:
                        painter.drawRect(x, 0, max(width, 2), height)
                    x += width
        except Exception as e:
            print(f"[ERROR] QualityBar.paintEvent: {e}")


class StatsPanel(QWidget):
    """
    Clean project statistics panel

    Shows:
    - Total clips
    - Synced count
    - Failed count
    - Average confidence
    - Quality distribution
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Section header
        header = QLabel("Overview")
        header.setStyleSheet("""
            font-size: 13px;
            font-weight: 600;
            color: #888;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(header)

        # Stats grid
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)

        self.total_card = StatCard("Clips", "0", "#a78bfa")
        grid.addWidget(self.total_card, 0, 0)

        self.synced_card = StatCard("Synced", "0", "#10b981")
        grid.addWidget(self.synced_card, 0, 1)

        self.failed_card = StatCard("Failed", "0", "#ef4444")
        grid.addWidget(self.failed_card, 1, 0)

        self.confidence_card = StatCard("Avg Conf", "0%", "#3b82f6")
        grid.addWidget(self.confidence_card, 1, 1)

        layout.addLayout(grid)

        # Quality section
        layout.addSpacing(8)

        quality_header = QLabel("Quality")
        quality_header.setStyleSheet("""
            font-size: 11px;
            color: #555;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 500;
        """)
        layout.addWidget(quality_header)

        self.quality_bar = QualityBar()
        layout.addWidget(self.quality_bar)

        # Quality legend - compact single row
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(8)
        legend_layout.setContentsMargins(0, 4, 0, 0)

        legends = [
            ("Excellent", "#10b981"),
            ("Good", "#84cc16"),
            ("Fair", "#f59e0b"),
            ("Poor", "#f97316"),
            ("Failed", "#ef4444"),
        ]

        for name, color in legends:
            item = QHBoxLayout()
            item.setSpacing(3)

            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 8px;")
            item.addWidget(dot)

            label = QLabel(name[:3])  # Abbreviated
            label.setStyleSheet("color: #444; font-size: 9px;")
            item.addWidget(label)

            legend_layout.addLayout(item)

        legend_layout.addStretch()
        layout.addLayout(legend_layout)

        layout.addStretch()

    def update_stats(self, project: SyncProject):
        """Update stats from project with defensive null checks"""
        try:
            clips = project.clips or []
            self.total_card.set_value(str(len(clips)))
            self.synced_card.set_value(str(project.total_synced or 0))
            self.failed_card.set_value(str(project.total_failed or 0))

            avg_conf = project.average_confidence if project.average_confidence is not None else 0.0
            self.confidence_card.set_value(f"{avg_conf:.0%}")

            # Calculate quality distribution with safe checks
            counts = {q: 0 for q in SyncQuality}
            for clip in clips:
                if clip and clip.sync_quality is not None:
                    counts[clip.sync_quality] = counts.get(clip.sync_quality, 0) + 1

            self.quality_bar.set_counts(counts)
        except Exception as e:
            print(f"Error updating stats: {e}")
