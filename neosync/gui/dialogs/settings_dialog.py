"""
Settings Dialog
===============

Application settings and preferences.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCheckBox, QComboBox, QSpinBox,
    QTabWidget, QWidget, QGroupBox, QFormLayout, QSlider
)
from PyQt6.QtCore import Qt

from ..theme import ThemeMode


class SettingsDialog(QDialog):
    """
    Settings dialog

    Tabs:
    - General: Theme, language
    - Sync: Sample rate, max offset, drift correction
    - Performance: GPU, workers, cache
    - Export: Default formats, paths
    """

    def __init__(self, settings: dict = None, parent=None):
        super().__init__(parent)
        self.settings = settings or {}

        self.setWindowTitle("Settings")
        self.setFixedSize(600, 500)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget
        tabs = QTabWidget()
        tabs.addTab(self._create_general_tab(), "General")
        tabs.addTab(self._create_sync_tab(), "Sync")
        tabs.addTab(self._create_performance_tab(), "Performance")
        tabs.addTab(self._create_export_tab(), "Export")
        tabs.addTab(self._create_shortcuts_tab(), "Shortcuts")
        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(16, 16, 16, 16)

        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _create_general_tab(self) -> QWidget:
        """Create general settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        # Appearance
        appearance = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "System"])
        self.theme_combo.setCurrentText(self.settings.get('theme', 'Dark'))
        appearance_layout.addRow("Theme:", self.theme_combo)

        layout.addWidget(appearance)

        # Behavior
        behavior = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout(behavior)

        self.auto_analyze = QCheckBox("Auto-analyze clips on import")
        self.auto_analyze.setChecked(self.settings.get('auto_analyze', True))
        behavior_layout.addWidget(self.auto_analyze)

        self.auto_sync = QCheckBox("Auto-sync after analysis")
        self.auto_sync.setChecked(self.settings.get('auto_sync', False))
        behavior_layout.addWidget(self.auto_sync)

        self.remember_window = QCheckBox("Remember window size and position")
        self.remember_window.setChecked(self.settings.get('remember_window', True))
        behavior_layout.addWidget(self.remember_window)

        layout.addWidget(behavior)

        layout.addStretch()
        return widget

    def _create_sync_tab(self) -> QWidget:
        """Create sync settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        # Audio Analysis
        audio = QGroupBox("Audio Analysis")
        audio_layout = QFormLayout(audio)

        self.sample_rate = QComboBox()
        self.sample_rate.addItems(["44100", "48000", "96000"])
        self.sample_rate.setCurrentText(str(self.settings.get('sample_rate', 48000)))
        audio_layout.addRow("Sample Rate:", self.sample_rate)

        self.fft_size = QComboBox()
        self.fft_size.addItems(["2048", "4096", "8192", "16384"])
        self.fft_size.setCurrentText(str(self.settings.get('fft_size', 4096)))
        audio_layout.addRow("FFT Size:", self.fft_size)

        self.noise_reduction = QCheckBox("Enable noise reduction")
        self.noise_reduction.setChecked(self.settings.get('noise_reduction', True))
        audio_layout.addRow("", self.noise_reduction)

        layout.addWidget(audio)

        # Sync Settings
        sync = QGroupBox("Sync Settings")
        sync_layout = QFormLayout(sync)

        self.max_offset = QSpinBox()
        self.max_offset.setRange(60, 7200)
        self.max_offset.setValue(self.settings.get('max_offset', 3600))
        self.max_offset.setSuffix(" seconds")
        sync_layout.addRow("Max Offset:", self.max_offset)

        self.drift_correction = QCheckBox("Enable drift correction")
        self.drift_correction.setChecked(self.settings.get('drift_correction', True))
        sync_layout.addRow("", self.drift_correction)

        self.confidence_threshold = QSlider(Qt.Orientation.Horizontal)
        self.confidence_threshold.setRange(20, 95)
        self.confidence_threshold.setValue(int(self.settings.get('confidence_threshold', 60) * 100))
        sync_layout.addRow("Min Confidence:", self.confidence_threshold)

        layout.addWidget(sync)

        # Advanced Accuracy Settings (new researched improvements)
        accuracy = QGroupBox("Advanced Accuracy")
        accuracy_layout = QFormLayout(accuracy)

        # PHAT-β weighting mode
        self.phat_mode = QComboBox()
        self.phat_mode.addItems(["Adaptive (Auto)", "High SNR (β=1.0)", "Low SNR (β=0.5)", "Very Noisy (β=0.3)"])
        self.phat_mode.setCurrentText(self.settings.get('phat_mode', 'Adaptive (Auto)'))
        self.phat_mode.setToolTip(
            "PHAT-β weighting adapts to signal quality:\n"
            "• Adaptive: Auto-adjusts based on estimated SNR\n"
            "• High SNR: Best for clean audio\n"
            "• Low SNR: Better for noisy environments\n"
            "• Very Noisy: Maximum noise tolerance"
        )
        accuracy_layout.addRow("GCC-PHAT Mode:", self.phat_mode)

        # Sub-sample interpolation method
        self.sinc_interpolation = QCheckBox("Use sinc interpolation (higher precision)")
        self.sinc_interpolation.setChecked(self.settings.get('sinc_interpolation', True))
        self.sinc_interpolation.setToolTip(
            "Sinc interpolation provides higher sub-sample precision\n"
            "than standard parabolic interpolation. Slightly slower."
        )
        accuracy_layout.addRow("", self.sinc_interpolation)

        # Diffuseness mask for reverb handling
        self.diffuseness_mask = QCheckBox("Enable diffuseness mask (better reverb handling)")
        self.diffuseness_mask.setChecked(self.settings.get('diffuseness_mask', True))
        self.diffuseness_mask.setToolTip(
            "Downweights reverberant frequency bins using coherence analysis.\n"
            "Improves accuracy in echoey environments (gyms, churches, etc.)"
        )
        accuracy_layout.addRow("", self.diffuseness_mask)

        # Multi-scale sync for speed
        self.multi_scale_sync = QCheckBox("Use multi-scale sync (faster for long clips)")
        self.multi_scale_sync.setChecked(self.settings.get('multi_scale_sync', True))
        self.multi_scale_sync.setToolTip(
            "Coarse-to-fine approach: quick rough alignment at low resolution,\n"
            "then precise alignment at full resolution. 3-5x faster for long clips."
        )
        accuracy_layout.addRow("", self.multi_scale_sync)

        # Streaming sync for very large files
        self.streaming_sync = QCheckBox("Enable streaming sync for large files (>1 hour)")
        self.streaming_sync.setChecked(self.settings.get('streaming_sync', True))
        self.streaming_sync.setToolTip(
            "Process hour-long recordings in chunks to avoid memory issues.\n"
            "Also detects clock drift across the recording."
        )
        accuracy_layout.addRow("", self.streaming_sync)

        layout.addWidget(accuracy)

        layout.addStretch()
        return widget

    def _create_performance_tab(self) -> QWidget:
        """Create performance settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        # GPU
        gpu = QGroupBox("GPU Acceleration")
        gpu_layout = QVBoxLayout(gpu)

        self.use_gpu = QCheckBox("Enable GPU acceleration (CUDA/OpenCL)")
        self.use_gpu.setChecked(self.settings.get('use_gpu', True))
        gpu_layout.addWidget(self.use_gpu)

        gpu_info = QLabel("GPU acceleration significantly speeds up audio correlation")
        gpu_info.setStyleSheet("color: #888; font-size: 11px;")
        gpu_layout.addWidget(gpu_info)

        layout.addWidget(gpu)

        # Parallel Processing
        parallel = QGroupBox("Parallel Processing")
        parallel_layout = QFormLayout(parallel)

        self.max_workers = QSpinBox()
        self.max_workers.setRange(1, 32)
        self.max_workers.setValue(self.settings.get('max_workers', 4))
        parallel_layout.addRow("Max Workers:", self.max_workers)

        layout.addWidget(parallel)

        # Cache
        cache = QGroupBox("Cache")
        cache_layout = QVBoxLayout(cache)

        self.cache_fingerprints = QCheckBox("Cache audio fingerprints")
        self.cache_fingerprints.setChecked(self.settings.get('cache_fingerprints', True))
        cache_layout.addWidget(self.cache_fingerprints)

        clear_cache_btn = QPushButton("Clear Cache")
        clear_cache_btn.setFixedWidth(120)
        cache_layout.addWidget(clear_cache_btn)

        layout.addWidget(cache)

        layout.addStretch()
        return widget

    def _create_export_tab(self) -> QWidget:
        """Create export settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        # Default Format
        format_group = QGroupBox("Default Export Format")
        format_layout = QFormLayout(format_group)

        self.default_format = QComboBox()
        self.default_format.addItems([
            "Final Cut Pro XML",
            "Premiere Pro XML",
            "Avid AAF",
            "OpenTimelineIO"
        ])
        format_layout.addRow("Format:", self.default_format)

        layout.addWidget(format_group)

        # Report Settings
        report = QGroupBox("Reports")
        report_layout = QVBoxLayout(report)

        self.auto_report = QCheckBox("Generate report after sync")
        self.auto_report.setChecked(self.settings.get('auto_report', False))
        report_layout.addWidget(self.auto_report)

        layout.addWidget(report)

        layout.addStretch()
        return widget

    def _create_shortcuts_tab(self) -> QWidget:
        """Create keyboard shortcuts tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        shortcuts = [
            ("Import clips", "Ctrl+I"),
            ("Analyze all", "Ctrl+A"),
            ("Sync all", "Ctrl+S"),
            ("Export", "Ctrl+E"),
            ("Zoom in timeline", "+"),
            ("Zoom out timeline", "-"),
            ("Nudge left", "←"),
            ("Nudge right", "→"),
            ("Set as reference", "R"),
            ("Remove selected", "Delete"),
        ]

        for action, shortcut in shortcuts:
            row = QHBoxLayout()
            row.addWidget(QLabel(action))
            row.addStretch()

            shortcut_label = QLabel(shortcut)
            shortcut_label.setStyleSheet("""
                background-color: #333;
                padding: 4px 8px;
                border-radius: 4px;
                font-family: monospace;
            """)
            row.addWidget(shortcut_label)

            layout.addLayout(row)

        layout.addStretch()
        return widget

    def _save(self):
        """Save settings"""
        self.settings['theme'] = self.theme_combo.currentText()
        self.settings['auto_analyze'] = self.auto_analyze.isChecked()
        self.settings['auto_sync'] = self.auto_sync.isChecked()
        self.settings['sample_rate'] = int(self.sample_rate.currentText())
        self.settings['fft_size'] = int(self.fft_size.currentText())
        self.settings['noise_reduction'] = self.noise_reduction.isChecked()
        self.settings['max_offset'] = self.max_offset.value()
        self.settings['drift_correction'] = self.drift_correction.isChecked()
        self.settings['use_gpu'] = self.use_gpu.isChecked()
        self.settings['max_workers'] = self.max_workers.value()
        self.settings['cache_fingerprints'] = self.cache_fingerprints.isChecked()

        # Advanced accuracy settings
        self.settings['phat_mode'] = self.phat_mode.currentText()
        self.settings['sinc_interpolation'] = self.sinc_interpolation.isChecked()
        self.settings['diffuseness_mask'] = self.diffuseness_mask.isChecked()
        self.settings['multi_scale_sync'] = self.multi_scale_sync.isChecked()
        self.settings['streaming_sync'] = self.streaming_sync.isChecked()

        self.accept()

    def get_settings(self) -> dict:
        """Get settings dict"""
        return self.settings
