"""
Stats Panel Widget
==================

Display sync statistics and project summary.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt

from ...core.sync_engine import SyncProject, SyncQuality


class StatCard(QFrame):
    """Individual stat card"""

    def __init__(self, title: str, value: str = "0", color: str = "#8b5cf6", parent=None):
        super().__init__(parent)
        self._title = title
        self._value = value
        self._color = color

        self.setStyleSheet(f"""
            StatCard {{
                background-color: #1a1a1a;
                border: 1px solid #333;
                border-radius: 12px;
                padding: 16px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)

        # Value
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"""
            font-size: 32px;
            font-weight: 700;
            color: {color};
        """)
        layout.addWidget(self.value_label)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
        """)
        layout.addWidget(title_label)

    def set_value(self, value: str):
        """Update the value"""
        self._value = value
        self.value_label.setText(value)


class QualityBar(QWidget):
    """Visual bar showing sync quality distribution"""

    COLORS = {
        SyncQuality.EXCELLENT: "#22c55e",
        SyncQuality.GOOD: "#84cc16",
        SyncQuality.FAIR: "#eab308",
        SyncQuality.POOR: "#f97316",
        SyncQuality.FAILED: "#ef4444",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts = {}
        self.setFixedHeight(32)

    def set_counts(self, counts: dict):
        """Set quality counts"""
        self._counts = counts
        self.update()

    def paintEvent(self, event):
        """Paint the quality bar"""
        from PyQt6.QtGui import QPainter, QColor

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        total = sum(self._counts.values()) if self._counts else 0
        if total == 0:
            painter.fillRect(self.rect(), QColor("#1a1a1a"))
            return

        x = 0
        height = self.height() - 8
        y = 4

        for quality in [SyncQuality.EXCELLENT, SyncQuality.GOOD, SyncQuality.FAIR,
                       SyncQuality.POOR, SyncQuality.FAILED]:
            count = self._counts.get(quality, 0)
            if count > 0:
                width = int((count / total) * self.width())
                color = QColor(self.COLORS.get(quality, "#666"))
                painter.fillRect(x, y, max(width, 2), height, color)
                x += width


class StatsPanel(QWidget):
    """
    Project statistics panel

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
        layout.setSpacing(16)

        # Title
        title = QLabel("Statistics")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        # Stats grid
        grid = QGridLayout()
        grid.setSpacing(12)

        self.total_card = StatCard("Total Clips", "0", "#8b5cf6")
        grid.addWidget(self.total_card, 0, 0)

        self.synced_card = StatCard("Synced", "0", "#22c55e")
        grid.addWidget(self.synced_card, 0, 1)

        self.failed_card = StatCard("Failed", "0", "#ef4444")
        grid.addWidget(self.failed_card, 1, 0)

        self.confidence_card = StatCard("Confidence", "0%", "#3b82f6")
        grid.addWidget(self.confidence_card, 1, 1)

        layout.addLayout(grid)

        # Quality distribution
        quality_label = QLabel("Quality Distribution")
        quality_label.setStyleSheet("font-size: 13px; color: #888; margin-top: 8px;")
        layout.addWidget(quality_label)

        self.quality_bar = QualityBar()
        layout.addWidget(self.quality_bar)

        # Quality legend
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(16)

        for quality, color in [
            (SyncQuality.EXCELLENT, "#22c55e"),
            (SyncQuality.GOOD, "#84cc16"),
            (SyncQuality.FAIR, "#eab308"),
            (SyncQuality.POOR, "#f97316"),
            (SyncQuality.FAILED, "#ef4444"),
        ]:
            item = QHBoxLayout()
            item.setSpacing(4)

            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px;")
            item.addWidget(dot)

            name = QLabel(quality.name.capitalize())
            name.setStyleSheet("color: #888; font-size: 11px;")
            item.addWidget(name)

            legend_layout.addLayout(item)

        legend_layout.addStretch()
        layout.addLayout(legend_layout)

        layout.addStretch()

    def update_stats(self, project: SyncProject):
        """Update stats from project"""
        self.total_card.set_value(str(len(project.clips)))
        self.synced_card.set_value(str(project.total_synced))
        self.failed_card.set_value(str(project.total_failed))
        self.confidence_card.set_value(f"{project.average_confidence:.0%}")

        # Calculate quality distribution
        counts = {q: 0 for q in SyncQuality}
        for clip in project.clips:
            counts[clip.sync_quality] = counts.get(clip.sync_quality, 0) + 1

        self.quality_bar.set_counts(counts)
