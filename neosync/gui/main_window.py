"""
NeoSync Main Window
===================

The main application window orchestrating all functionality.
"""

import os
import json
from pathlib import Path
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSplitter, QStackedWidget, QMenuBar, QMenu,
    QStatusBar, QFileDialog, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut

from .theme import Theme, ThemeMode, apply_theme
from .widgets.drop_zone import DropZone
from .widgets.clip_table import ClipTableWidget
from .widgets.timeline_view import TimelineView
from .widgets.waveform_view import WaveformView
from .widgets.stats_panel import StatsPanel
from .widgets.progress_dialog import ProgressDialog
from .dialogs.license_dialog import LicenseDialog
from .dialogs.settings_dialog import SettingsDialog
from .dialogs.export_dialog import ExportDialog
from .dialogs.about_dialog import AboutDialog

from ..core.sync_engine import SyncEngine, ClipInfo, SyncStatus
from ..core.license_manager import LicenseManager
from ..export import FCPXMLExporter, PremiereXMLExporter, AAFExporter, OTIOExporter, ReportGenerator


class AnalyzeWorker(QThread):
    """Background worker for analyzing clips"""
    progress = pyqtSignal(float, str)
    finished = pyqtSignal(bool)
    clip_updated = pyqtSignal(object)

    def __init__(self, engine: SyncEngine, clips: list):
        super().__init__()
        self.engine = engine
        self.clips = clips
        self._cancelled = False

    def run(self):
        """Run analysis"""
        def on_progress(value, msg):
            self.progress.emit(value, msg)

        def on_status(clip):
            self.clip_updated.emit(clip)

        self.engine.set_progress_callback(on_progress)
        self.engine.set_status_callback(on_status)

        success = self.engine.analyze_clips(self.clips)
        self.finished.emit(success and not self._cancelled)

    def cancel(self):
        self._cancelled = True
        self.engine.cancel()


class SyncWorker(QThread):
    """Background worker for syncing clips"""
    progress = pyqtSignal(float, str)
    finished = pyqtSignal(bool)
    clip_updated = pyqtSignal(object)

    def __init__(self, engine: SyncEngine, reference: ClipInfo = None):
        super().__init__()
        self.engine = engine
        self.reference = reference
        self._cancelled = False

    def run(self):
        """Run sync"""
        def on_progress(value, msg):
            self.progress.emit(value, msg)

        def on_status(clip):
            self.clip_updated.emit(clip)

        self.engine.set_progress_callback(on_progress)
        self.engine.set_status_callback(on_status)

        success = self.engine.sync_all(self.reference)
        self.finished.emit(success and not self._cancelled)

    def cancel(self):
        self._cancelled = True
        self.engine.cancel()


class MainWindow(QMainWindow):
    """
    NeoSync main application window

    Layout:
    - Menu bar
    - Toolbar (optional)
    - Main area:
      - Left: Stats panel
      - Center: Clip table / Drop zone (stacked)
      - Right: Waveform view
    - Bottom: Timeline view
    - Status bar
    """

    def __init__(self):
        super().__init__()

        # Initialize managers
        self.license_manager = LicenseManager()
        self.sync_engine = SyncEngine(use_gpu=True, noise_reduction=True)
        self.theme = Theme(ThemeMode.DARK)
        self.settings = QSettings("NeoFox", "NeoSync")

        # State
        self.project_path: Optional[str] = None
        self.project_modified = False

        # Setup UI
        self.setWindowTitle("NeoSync")
        self.setMinimumSize(1200, 800)
        self._setup_ui()
        self._setup_menus()
        self._setup_shortcuts()
        self._restore_geometry()

        # Show license dialog if not licensed
        if not self.license_manager.is_licensed():
            QTimer.singleShot(500, self._check_license)

    def _setup_ui(self):
        """Setup the main UI"""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main splitter (horizontal)
        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Stats
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 8, 16)

        self.stats_panel = StatsPanel()
        left_layout.addWidget(self.stats_panel)

        left_panel.setFixedWidth(280)
        h_splitter.addWidget(left_panel)

        # Center panel - Clips table or drop zone
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(8, 16, 8, 16)

        # Stacked widget for drop zone / table
        self.stack = QStackedWidget()

        # Drop zone (shown when no clips)
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._on_files_dropped)
        self.stack.addWidget(self.drop_zone)

        # Clip table (shown when clips exist)
        self.clip_table = ClipTableWidget()
        self.clip_table.clip_selected.connect(self._on_clip_selected)
        self.clip_table.clips_removed.connect(self._on_clips_removed)
        self.clip_table.set_reference_requested.connect(self._on_set_reference)
        self.stack.addWidget(self.clip_table)

        center_layout.addWidget(self.stack)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.add_btn = QPushButton("Add Clips")
        self.add_btn.clicked.connect(self._add_clips)
        btn_row.addWidget(self.add_btn)

        self.analyze_btn = QPushButton("Analyze")
        self.analyze_btn.clicked.connect(self._analyze_all)
        self.analyze_btn.setEnabled(False)
        btn_row.addWidget(self.analyze_btn)

        self.sync_btn = QPushButton("Sync All")
        self.sync_btn.setProperty("class", "primary")
        self.sync_btn.clicked.connect(self._sync_all)
        self.sync_btn.setEnabled(False)
        btn_row.addWidget(self.sync_btn)

        btn_row.addStretch()

        self.export_btn = QPushButton("Export")
        self.export_btn.setProperty("class", "success")
        self.export_btn.clicked.connect(self._export)
        self.export_btn.setEnabled(False)
        btn_row.addWidget(self.export_btn)

        center_layout.addLayout(btn_row)

        h_splitter.addWidget(center_panel)

        # Right panel - Waveform
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 16, 16, 16)

        self.waveform_view = WaveformView()
        self.waveform_view.offset_changed.connect(self._on_offset_changed)
        right_layout.addWidget(self.waveform_view)

        right_panel.setFixedWidth(350)
        h_splitter.addWidget(right_panel)

        # Vertical splitter for timeline
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(h_splitter)

        # Timeline at bottom
        self.timeline_view = TimelineView()
        self.timeline_view.clip_selected.connect(self._on_clip_selected)
        v_splitter.addWidget(self.timeline_view)

        v_splitter.setSizes([600, 200])
        main_layout.addWidget(v_splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status("Ready")

    def _setup_menus(self):
        """Setup menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        new_action = QAction("New Project", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        open_action = QAction("Open Project...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("Save Project", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save Project As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        import_action = QAction("Import Clips...", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._add_clips)
        file_menu.addAction(import_action)

        export_action = QAction("Export...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._export)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")

        select_all_action = QAction("Select All", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(lambda: self.clip_table.table.selectAll())
        edit_menu.addAction(select_all_action)

        edit_menu.addSeparator()

        settings_action = QAction("Settings...", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._show_settings)
        edit_menu.addAction(settings_action)

        # Sync menu
        sync_menu = menubar.addMenu("Sync")

        analyze_action = QAction("Analyze All", self)
        analyze_action.setShortcut(QKeySequence("Ctrl+A"))
        analyze_action.triggered.connect(self._analyze_all)
        sync_menu.addAction(analyze_action)

        sync_action = QAction("Sync All", self)
        sync_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        sync_action.triggered.connect(self._sync_all)
        sync_menu.addAction(sync_action)

        sync_menu.addSeparator()

        set_ref_action = QAction("Set Selected as Reference", self)
        set_ref_action.setShortcut(QKeySequence("R"))
        set_ref_action.triggered.connect(self._set_selected_as_reference)
        sync_menu.addAction(set_ref_action)

        # View menu
        view_menu = menubar.addMenu("View")

        theme_menu = view_menu.addMenu("Theme")

        dark_action = QAction("Dark", self)
        dark_action.triggered.connect(lambda: self._set_theme(ThemeMode.DARK))
        theme_menu.addAction(dark_action)

        light_action = QAction("Light", self)
        light_action.triggered.connect(lambda: self._set_theme(ThemeMode.LIGHT))
        theme_menu.addAction(light_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        license_action = QAction("License...", self)
        license_action.triggered.connect(self._show_license)
        help_menu.addAction(license_action)

        help_menu.addSeparator()

        about_action = QAction("About NeoSync", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Nudge shortcuts
        QShortcut(QKeySequence("Left"), self, self._nudge_left)
        QShortcut(QKeySequence("Right"), self, self._nudge_right)
        QShortcut(QKeySequence("Delete"), self, self._remove_selected)

    def _restore_geometry(self):
        """Restore window geometry from settings"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            # Default centered position
            screen = QApplication.primaryScreen().geometry()
            self.move(
                (screen.width() - self.width()) // 2,
                (screen.height() - self.height()) // 2
            )

    def _save_geometry(self):
        """Save window geometry to settings"""
        self.settings.setValue("geometry", self.saveGeometry())

    def _update_status(self, message: str):
        """Update status bar"""
        self.status_bar.showMessage(message)

    def _update_ui_state(self):
        """Update UI based on current state"""
        has_clips = len(self.sync_engine.project.clips) > 0
        has_synced = self.sync_engine.project.total_synced > 0

        # Switch between drop zone and table
        self.stack.setCurrentIndex(1 if has_clips else 0)

        # Update buttons
        self.analyze_btn.setEnabled(has_clips)
        self.sync_btn.setEnabled(has_clips)
        self.export_btn.setEnabled(has_synced)

        # Update clip table
        self.clip_table.set_clips(self.sync_engine.project.clips)

        # Update stats
        self.stats_panel.update_stats(self.sync_engine.project)

        # Update timeline
        self.timeline_view.set_clips(self.sync_engine.project.clips)

    def _check_license(self):
        """Check license on startup"""
        if not self.license_manager.is_licensed():
            dialog = LicenseDialog(self.license_manager, self)
            dialog.exec()

    # === File Operations ===

    def _new_project(self):
        """Create new project"""
        if self.project_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Save changes to current project?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save_project()
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.sync_engine.clear_project()
        self.project_path = None
        self.project_modified = False
        self.setWindowTitle("NeoSync - New Project")
        self._update_ui_state()

    def _open_project(self):
        """Open existing project"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project",
            "", "NeoSync Project (*.neosync);;All Files (*.*)"
        )
        if path:
            self._load_project(path)

    def _save_project(self):
        """Save current project"""
        if self.project_path:
            self._save_project_to_path(self.project_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        """Save project to new file"""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project",
            f"{self.sync_engine.project.name}.neosync",
            "NeoSync Project (*.neosync)"
        )
        if path:
            self._save_project_to_path(path)

    def _save_project_to_path(self, path: str):
        """Save project to specified path"""
        try:
            project_data = {
                'name': self.sync_engine.project.name,
                'clips': [
                    {
                        'id': c.id,
                        'file_path': c.file_path,
                        'sync_offset_seconds': c.sync_offset_seconds,
                        'sync_confidence': c.sync_confidence,
                        'sync_status': c.sync_status.name,
                        'sync_quality': c.sync_quality.name,
                        'camera_id': c.camera_id,
                        'is_reference': c.is_reference,
                    }
                    for c in self.sync_engine.project.clips
                ],
                'settings': {
                    'sample_rate': self.sync_engine.project.sample_rate,
                    'max_offset': self.sync_engine.project.max_offset_seconds,
                }
            }

            with open(path, 'w') as f:
                json.dump(project_data, f, indent=2)

            self.project_path = path
            self.project_modified = False
            self.setWindowTitle(f"NeoSync - {Path(path).stem}")
            self._update_status(f"Project saved to {path}")

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save project: {e}")

    def _load_project(self, path: str):
        """Load project from file"""
        try:
            with open(path, 'r') as f:
                data = json.load(f)

            self.sync_engine.clear_project()
            self.sync_engine.project.name = data.get('name', 'Untitled')

            # Add clips
            for clip_data in data.get('clips', []):
                clips = self.sync_engine.add_clips([clip_data['file_path']])
                if clips:
                    clip = clips[0]
                    clip.sync_offset_seconds = clip_data.get('sync_offset_seconds', 0)
                    clip.sync_confidence = clip_data.get('sync_confidence', 0)
                    clip.is_reference = clip_data.get('is_reference', False)

            self.project_path = path
            self.project_modified = False
            self.setWindowTitle(f"NeoSync - {Path(path).stem}")
            self._update_ui_state()
            self._update_status(f"Project loaded: {path}")

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load project: {e}")

    # === Clip Operations ===

    def _add_clips(self):
        """Add clips via file dialog"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add Media Files",
            "",
            "Media Files (*.mp4 *.mov *.avi *.mkv *.mxf *.wav *.mp3);;All Files (*.*)"
        )
        if files:
            self._on_files_dropped(files)

    def _on_files_dropped(self, files: list):
        """Handle dropped files"""
        # Check license limit
        max_clips = self.license_manager.get_max_clips()
        current = len(self.sync_engine.project.clips)

        if current + len(files) > max_clips:
            if not self.license_manager.is_licensed():
                QMessageBox.warning(
                    self, "Trial Limit",
                    f"Trial mode allows only {max_clips} clips.\n"
                    "Activate a license for unlimited clips."
                )
                self._show_license()
                return
            else:
                files = files[:max_clips - current]
                QMessageBox.information(
                    self, "Clip Limit",
                    f"Adding first {len(files)} clips (limit: {max_clips})"
                )

        # Add clips
        added = self.sync_engine.add_clips(files)
        self.project_modified = True

        self._update_ui_state()
        self._update_status(f"Added {len(added)} clips")

    def _on_clips_removed(self, clip_ids: list):
        """Handle clip removal"""
        self.sync_engine.remove_clips(clip_ids)
        self.project_modified = True
        self._update_ui_state()

    def _on_clip_selected(self, clip: ClipInfo):
        """Handle clip selection"""
        # Update waveform view
        # TODO: Load actual waveform data
        self.waveform_view.set_selected(clip, None, clip.sync_offset_seconds)

    def _on_set_reference(self, clip: ClipInfo):
        """Set clip as reference"""
        self.sync_engine.set_reference(clip)
        self.project_modified = True
        self._update_ui_state()
        self._update_status(f"Set {clip.file_name} as reference")

    def _set_selected_as_reference(self):
        """Set currently selected clip as reference"""
        selected = self.clip_table.get_selected_clips()
        if selected:
            self._on_set_reference(selected[0])

    def _on_offset_changed(self, offset: float):
        """Handle manual offset adjustment"""
        selected = self.clip_table.get_selected_clips()
        if selected:
            clip = selected[0]
            old_offset = clip.sync_offset_seconds
            delta = offset - old_offset
            self.sync_engine.manual_adjust_offset(clip, delta)
            self.project_modified = True
            self._update_ui_state()

    def _remove_selected(self):
        """Remove selected clips"""
        selected = self.clip_table.get_selected_clips()
        if selected:
            ids = [c.id for c in selected]
            self._on_clips_removed(ids)

    def _nudge_left(self):
        """Nudge selected clip left by 1 frame"""
        selected = self.clip_table.get_selected_clips()
        if selected:
            clip = selected[0]
            fps = clip.fps or 24.0
            self.sync_engine.manual_adjust_offset(clip, -1 / fps)
            self.project_modified = True
            self._update_ui_state()

    def _nudge_right(self):
        """Nudge selected clip right by 1 frame"""
        selected = self.clip_table.get_selected_clips()
        if selected:
            clip = selected[0]
            fps = clip.fps or 24.0
            self.sync_engine.manual_adjust_offset(clip, 1 / fps)
            self.project_modified = True
            self._update_ui_state()

    # === Sync Operations ===

    def _analyze_all(self):
        """Analyze all clips"""
        clips = self.sync_engine.project.clips
        if not clips:
            return

        # Show progress dialog
        progress = ProgressDialog("Analyzing Clips...", self)

        # Create worker
        worker = AnalyzeWorker(self.sync_engine, clips)
        worker.progress.connect(progress.set_progress)
        worker.clip_updated.connect(self.clip_table.update_clip)
        worker.finished.connect(lambda ok: self._on_analyze_finished(ok, progress))

        progress.cancelled.connect(worker.cancel)
        worker.start()
        progress.exec()

    def _on_analyze_finished(self, success: bool, dialog: ProgressDialog):
        """Handle analysis completion"""
        if success:
            dialog.finish("Analysis complete!")
            self._update_ui_state()
            self._update_status(f"Analyzed {len(self.sync_engine.project.clips)} clips")
        else:
            dialog.finish("Analysis cancelled")

    def _sync_all(self):
        """Sync all clips"""
        clips = self.sync_engine.project.clips
        if not clips:
            return

        # Find or set reference
        reference = self.sync_engine.project.reference_clip
        if not reference:
            reference = self.sync_engine.find_best_reference()
            if not reference:
                QMessageBox.warning(
                    self, "No Reference",
                    "Could not find a suitable reference clip.\n"
                    "Please select a reference clip manually."
                )
                return

        # Show progress
        progress = ProgressDialog("Syncing Clips...", self)

        # Create worker
        worker = SyncWorker(self.sync_engine, reference)
        worker.progress.connect(progress.set_progress)
        worker.clip_updated.connect(self.clip_table.update_clip)
        worker.finished.connect(lambda ok: self._on_sync_finished(ok, progress))

        progress.cancelled.connect(worker.cancel)
        worker.start()
        progress.exec()

    def _on_sync_finished(self, success: bool, dialog: ProgressDialog):
        """Handle sync completion"""
        if success:
            stats = self.sync_engine.project
            dialog.finish(
                f"Sync complete! {stats.total_synced} synced, "
                f"{stats.total_failed} failed"
            )
            self.project_modified = True
            self._update_ui_state()
        else:
            dialog.finish("Sync cancelled")

    # === Export ===

    def _export(self):
        """Export synced project"""
        if self.sync_engine.project.total_synced == 0:
            QMessageBox.warning(
                self, "Nothing to Export",
                "No clips have been synced. Please sync clips first."
            )
            return

        dialog = ExportDialog(self.sync_engine.project.name, self)
        if dialog.exec():
            config = dialog.get_export_config()
            self._do_export(config)

    def _do_export(self, config: dict):
        """Perform export"""
        try:
            output_dir = config['path']
            fmt = config['format']
            name = config['project_name']

            # Export timeline
            if fmt == 'fcpxml':
                exporter = FCPXMLExporter(self.sync_engine.project)
                if config.get('multicam'):
                    path = exporter.export_multicam(os.path.join(output_dir, f"{name}_multicam"))
                else:
                    path = exporter.export(os.path.join(output_dir, name))
            elif fmt == 'premiere':
                exporter = PremiereXMLExporter(self.sync_engine.project)
                path = exporter.export(os.path.join(output_dir, name))
            elif fmt == 'aaf':
                exporter = AAFExporter(self.sync_engine.project)
                path = exporter.export(os.path.join(output_dir, name))
            elif fmt == 'otio':
                exporter = OTIOExporter(self.sync_engine.project)
                path = exporter.export(os.path.join(output_dir, name))
            else:
                raise ValueError(f"Unknown format: {fmt}")

            # Generate reports
            report_gen = ReportGenerator(self.sync_engine.project)

            if config.get('generate_csv'):
                report_gen.export_csv(os.path.join(output_dir, f"{name}_report"))

            if config.get('generate_html'):
                report_gen.export_html(os.path.join(output_dir, f"{name}_report"))

            if config.get('generate_pdf'):
                report_gen.export_pdf(os.path.join(output_dir, f"{name}_report"))

            QMessageBox.information(
                self, "Export Complete",
                f"Project exported successfully!\n\nOutput: {output_dir}"
            )
            self._update_status(f"Exported to {output_dir}")

        except Exception as e:
            QMessageBox.critical(
                self, "Export Error",
                f"Failed to export: {e}"
            )

    # === Dialogs ===

    def _show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(parent=self)
        if dialog.exec():
            settings = dialog.get_settings()
            # Apply settings
            if settings.get('theme') == 'Dark':
                self._set_theme(ThemeMode.DARK)
            elif settings.get('theme') == 'Light':
                self._set_theme(ThemeMode.LIGHT)

    def _show_license(self):
        """Show license dialog"""
        dialog = LicenseDialog(self.license_manager, self)
        dialog.exec()

    def _show_about(self):
        """Show about dialog"""
        dialog = AboutDialog(self)
        dialog.exec()

    def _set_theme(self, mode: ThemeMode):
        """Set application theme"""
        self.theme = apply_theme(QApplication.instance(), mode)

    # === Window Events ===

    def closeEvent(self, event):
        """Handle window close"""
        if self.project_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Save changes before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save_project()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        self._save_geometry()
        event.accept()
