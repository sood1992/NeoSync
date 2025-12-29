"""
Clip Table Widget
=================

Table view showing all clips with sync status.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QPushButton, QMenu, QAbstractItemView,
    QStyledItemDelegate, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QAction

from ...core.sync_engine import ClipInfo, SyncStatus, SyncQuality


class StatusDelegate(QStyledItemDelegate):
    """Custom delegate for status column with color badges"""

    QUALITY_COLORS = {
        SyncQuality.EXCELLENT: "#22c55e",
        SyncQuality.GOOD: "#84cc16",
        SyncQuality.FAIR: "#eab308",
        SyncQuality.POOR: "#f97316",
        SyncQuality.FAILED: "#ef4444",
    }

    def paint(self, painter, option, index):
        """Custom paint for status cell"""
        # Get clip data - handle None/invalid data during table updates (race condition)
        try:
            clip = index.data(Qt.ItemDataRole.UserRole)
            if not isinstance(clip, ClipInfo):
                super().paint(painter, option, index)
                return
        except (RuntimeError, TypeError):
            # Handle case where underlying C++ object has been deleted
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#8b5cf6"))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor("#252525"))

        # Draw badge - safely handle None sync_quality during initial import
        sync_quality = clip.sync_quality if clip.sync_quality is not None else SyncQuality.FAILED
        if clip.sync_status == SyncStatus.REFERENCE:
            text = "REFERENCE"
        elif clip.sync_status == SyncStatus.PENDING:
            text = "PENDING"
        elif clip.sync_status == SyncStatus.ANALYZING:
            text = "ANALYZING"
        else:
            text = sync_quality.name
        color = "#3b82f6" if clip.is_reference else self.QUALITY_COLORS.get(sync_quality, "#666")

        badge_rect = QRect(
            option.rect.x() + 10,
            option.rect.y() + (option.rect.height() - 24) // 2,
            80,
            24
        )

        # Badge background
        painter.setBrush(QColor(color + "30"))  # 30% opacity
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge_rect, 12, 12)

        # Badge text
        painter.setPen(QColor(color))
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()


class ConfidenceDelegate(QStyledItemDelegate):
    """Custom delegate for confidence column with progress bar"""

    QUALITY_COLORS = {
        SyncQuality.EXCELLENT: "#22c55e",
        SyncQuality.GOOD: "#84cc16",
        SyncQuality.FAIR: "#eab308",
        SyncQuality.POOR: "#f97316",
        SyncQuality.FAILED: "#ef4444",
    }

    def paint(self, painter, option, index):
        """Custom paint for confidence cell"""
        # Get clip data - handle None/invalid data during table updates (race condition)
        try:
            clip = index.data(Qt.ItemDataRole.UserRole)
            if not isinstance(clip, ClipInfo):
                super().paint(painter, option, index)
                return
        except (RuntimeError, TypeError):
            # Handle case where underlying C++ object has been deleted
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background on selection
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#8b5cf6"))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor("#252525"))

        # Progress bar background
        bar_rect = QRect(
            option.rect.x() + 10,
            option.rect.y() + (option.rect.height() - 8) // 2,
            60,
            8
        )
        painter.setBrush(QColor("#333333"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bar_rect, 4, 4)

        # Progress bar fill - safely handle None values during initial import
        sync_quality = clip.sync_quality if clip.sync_quality is not None else SyncQuality.FAILED
        sync_confidence = clip.sync_confidence if clip.sync_confidence is not None else 0.0

        color = self.QUALITY_COLORS.get(sync_quality, "#666")
        fill_width = int(bar_rect.width() * sync_confidence)
        fill_rect = QRect(bar_rect.x(), bar_rect.y(), fill_width, bar_rect.height())
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(fill_rect, 4, 4)

        # Text
        text_rect = QRect(
            bar_rect.right() + 8,
            option.rect.y(),
            40,
            option.rect.height()
        )
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setPointSize(11)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, f"{sync_confidence:.0%}")

        painter.restore()


class ClipTableWidget(QWidget):
    """
    Table widget showing all clips with sync status

    Features:
    - Color-coded status badges
    - Confidence progress bars
    - Context menu for actions
    - Multi-select support
    - Sorting by columns
    """

    clip_selected = pyqtSignal(object)  # ClipInfo
    clips_removed = pyqtSignal(list)  # List of clip IDs
    set_reference_requested = pyqtSignal(object)  # ClipInfo

    COLUMNS = [
        ("File Name", 250),
        ("Duration", 80),
        ("Camera", 100),
        ("Status", 100),
        ("Confidence", 120),
        ("Offset", 100),
        ("Method", 100),
        ("Audio", 60),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clips = []
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with count
        header = QHBoxLayout()
        header.setContentsMargins(16, 12, 16, 12)

        self.count_label = QLabel("0 clips")
        self.count_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        header.addWidget(self.count_label)

        header.addStretch()

        # Action buttons
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all)
        header.addWidget(self.select_all_btn)

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setProperty("class", "danger")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.remove_btn.setEnabled(False)
        header.addWidget(self.remove_btn)

        layout.addLayout(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in self.COLUMNS])

        # Set column widths
        for i, (_, width) in enumerate(self.COLUMNS):
            self.table.setColumnWidth(i, width)

        # Configure table
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Custom delegates
        self.table.setItemDelegateForColumn(3, StatusDelegate())
        self.table.setItemDelegateForColumn(4, ConfidenceDelegate())

        # Signals
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.cellDoubleClicked.connect(self._on_double_click)

        layout.addWidget(self.table)

    def set_clips(self, clips: list):
        """Set clips to display"""
        self._clips = clips
        self._refresh_table()

    def update_clip(self, clip: ClipInfo):
        """Update a single clip row"""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == clip:
                self._update_row(row, clip)
                break

    def _refresh_table(self):
        """Refresh the entire table"""
        self.table.setRowCount(len(self._clips))

        for row, clip in enumerate(self._clips):
            self._update_row(row, clip)

        self.count_label.setText(f"{len(self._clips)} clips")

    def _update_row(self, row: int, clip: ClipInfo):
        """Update a single row"""
        # File name
        name_item = QTableWidgetItem(clip.file_name)
        name_item.setData(Qt.ItemDataRole.UserRole, clip)
        name_item.setForeground(QColor(clip.color_code))
        self.table.setItem(row, 0, name_item)

        # Duration
        duration = f"{clip.duration:.1f}s" if clip.duration else "-"
        self.table.setItem(row, 1, QTableWidgetItem(duration))

        # Camera
        camera = clip.camera_id or "Unknown"
        self.table.setItem(row, 2, QTableWidgetItem(camera))

        # Status (custom delegate)
        status_item = QTableWidgetItem()
        status_item.setData(Qt.ItemDataRole.UserRole, clip)
        self.table.setItem(row, 3, status_item)

        # Confidence (custom delegate)
        conf_item = QTableWidgetItem()
        conf_item.setData(Qt.ItemDataRole.UserRole, clip)
        self.table.setItem(row, 4, conf_item)

        # Offset
        offset = f"{clip.sync_offset_seconds:+.3f}s"
        self.table.setItem(row, 5, QTableWidgetItem(offset))

        # Method
        method = clip.sync_method.value if clip.sync_method else "-"
        self.table.setItem(row, 6, QTableWidgetItem(method))

        # Audio
        audio = "✓" if clip.has_audio else "✗"
        audio_item = QTableWidgetItem(audio)
        audio_item.setForeground(QColor("#22c55e" if clip.has_audio else "#666"))
        self.table.setItem(row, 7, audio_item)

        # Row height
        self.table.setRowHeight(row, 48)

    def _show_context_menu(self, pos):
        """Show context menu"""
        item = self.table.itemAt(pos)
        if not item:
            return

        clip = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(clip, ClipInfo):
            return

        menu = QMenu(self)

        # Set as reference
        ref_action = menu.addAction("Set as Reference")
        ref_action.triggered.connect(lambda: self.set_reference_requested.emit(clip))

        menu.addSeparator()

        # Remove
        remove_action = menu.addAction("Remove")
        remove_action.triggered.connect(lambda: self.clips_removed.emit([clip.id]))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_selection_changed(self):
        """Handle selection change"""
        selected = self.table.selectedItems()
        self.remove_btn.setEnabled(len(selected) > 0)

        # Emit first selected clip
        if selected:
            clip = selected[0].data(Qt.ItemDataRole.UserRole)
            if isinstance(clip, ClipInfo):
                self.clip_selected.emit(clip)

    def _on_double_click(self, row: int, col: int):
        """Handle double click"""
        item = self.table.item(row, 0)
        if item:
            clip = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(clip, ClipInfo):
                self.set_reference_requested.emit(clip)

    def _select_all(self):
        """Select all rows"""
        self.table.selectAll()

    def _remove_selected(self):
        """Remove selected clips"""
        selected_ids = []
        for item in self.table.selectedItems():
            clip = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(clip, ClipInfo) and clip.id not in selected_ids:
                selected_ids.append(clip.id)

        if selected_ids:
            self.clips_removed.emit(selected_ids)

    def get_selected_clips(self) -> list:
        """Get currently selected clips"""
        clips = []
        for item in self.table.selectedItems():
            clip = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(clip, ClipInfo) and clip not in clips:
                clips.append(clip)
        return clips
