"""
NeoSync GUI Widgets
"""

from .clip_table import ClipTableWidget
from .timeline_view import TimelineView
from .waveform_view import WaveformView
from .drop_zone import DropZone
from .stats_panel import StatsPanel
from .progress_dialog import ProgressDialog

__all__ = [
    'ClipTableWidget',
    'TimelineView',
    'WaveformView',
    'DropZone',
    'StatsPanel',
    'ProgressDialog'
]
