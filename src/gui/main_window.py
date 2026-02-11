"""Main application window for Moho Render Farm."""
import os
import sys
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QGroupBox, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QSpinBox, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QSplitter, QStatusBar, QMenuBar, QMenu, QMessageBox,
    QProgressBar, QFormLayout, QGridLayout, QApplication, QAbstractItemView,
    QDialog, QDialogButtonBox, QInputDialog, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QMimeData, QUrl
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QIcon, QShortcut, QKeySequence
from src.config import (
    AppConfig, APP_NAME, APP_VERSION, APP_AUTHOR,
    FORMATS, WINDOWS_PRESETS, RESOLUTIONS, MOHO_FILE_EXTENSIONS,
    QUALITY_LEVELS, QUEUE_DIR, PRESETS_DIR, CONFIG_DIR,
)
import json
from src.moho_renderer import RenderJob, RenderStatus
from src.render_queue import RenderQueue
from src.gui.styles import DARK_THEME


class EditSettingsDialog(QDialog):
    """Dialog for editing render settings of one or more queued jobs."""

    def __init__(self, jobs, parent=None):
        super().__init__(parent)
        self.jobs = jobs
        self.setWindowTitle(f"Edit Render Settings ({len(jobs)} job{'s' if len(jobs) > 1 else ''})")
        self.setMinimumWidth(600)
        self._setup_ui()
        self._populate_from_jobs()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Render Presets ---
        preset_group = QGroupBox("Render Presets")
        preset_layout = QHBoxLayout(preset_group)
        preset_layout.addWidget(QLabel("Preset:"))
        self.combo_render_preset = QComboBox()
        self.combo_render_preset.setMinimumWidth(200)
        self.combo_render_preset.addItem("(none)")
        self._load_preset_list()
        self.combo_render_preset.currentTextChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self.combo_render_preset)
        self.btn_save_preset = QPushButton("Save Preset")
        self.btn_save_preset.clicked.connect(self._save_preset)
        preset_layout.addWidget(self.btn_save_preset)
        self.btn_delete_preset = QPushButton("Delete Preset")
        self.btn_delete_preset.clicked.connect(self._delete_preset)
        preset_layout.addWidget(self.btn_delete_preset)
        preset_layout.addStretch()
        layout.addWidget(preset_group)

        # --- Output Settings ---
        self.chk_apply_output = QCheckBox("Apply Output Settings")
        layout.addWidget(self.chk_apply_output)

        self.output_group = QGroupBox("Output Settings")
        output_form = QFormLayout(self.output_group)

        self.combo_format = QComboBox()
        self.combo_format.addItems(FORMATS)
        self.combo_format.currentTextChanged.connect(self._update_presets)
        output_form.addRow("Format:", self.combo_format)

        self.combo_preset = QComboBox()
        self._update_presets()
        output_form.addRow("Preset/Codec:", self.combo_preset)

        self.edit_output_dir = QLineEdit()
        self.edit_output_dir.setPlaceholderText("Same folder as project file (default)")
        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_output_dir)
        out_row = QHBoxLayout()
        out_row.addWidget(self.edit_output_dir)
        out_row.addWidget(browse_btn)
        output_form.addRow("Output Folder:", out_row)

        self.chk_subfolder_project = QCheckBox("Create subfolder with project name")
        output_form.addRow("", self.chk_subfolder_project)

        self.output_group.setEnabled(False)
        self.chk_apply_output.toggled.connect(self.output_group.setEnabled)
        layout.addWidget(self.output_group)

        # --- Frame Range ---
        self.chk_apply_frames = QCheckBox("Apply Frame Range")
        layout.addWidget(self.chk_apply_frames)

        self.frame_group = QGroupBox("Frame Range")
        frame_layout = QHBoxLayout(self.frame_group)

        self.chk_custom_frames = QCheckBox("Custom frame range")
        frame_layout.addWidget(self.chk_custom_frames)

        frame_layout.addWidget(QLabel("Start:"))
        self.spin_start_frame = QSpinBox()
        self.spin_start_frame.setRange(0, 999999)
        self.spin_start_frame.setValue(1)
        self.spin_start_frame.setEnabled(False)
        frame_layout.addWidget(self.spin_start_frame)

        frame_layout.addWidget(QLabel("End:"))
        self.spin_end_frame = QSpinBox()
        self.spin_end_frame.setRange(0, 999999)
        self.spin_end_frame.setValue(24)
        self.spin_end_frame.setEnabled(False)
        frame_layout.addWidget(self.spin_end_frame)

        self.chk_custom_frames.toggled.connect(self.spin_start_frame.setEnabled)
        self.chk_custom_frames.toggled.connect(self.spin_end_frame.setEnabled)
        frame_layout.addStretch()

        self.frame_group.setEnabled(False)
        self.chk_apply_frames.toggled.connect(self.frame_group.setEnabled)
        layout.addWidget(self.frame_group)

        # --- Render Options ---
        self.chk_apply_options = QCheckBox("Apply Render Options")
        layout.addWidget(self.chk_apply_options)

        self.options_group = QGroupBox("Render Options")
        options_grid = QGridLayout(self.options_group)

        self.chk_multithread = QCheckBox("Multi-threaded rendering")
        self.chk_multithread.setChecked(True)
        self.chk_halfsize = QCheckBox("Render at half size")
        self.chk_halffps = QCheckBox("Render at half frame rate")
        self.chk_shapefx = QCheckBox("Apply shape effects")
        self.chk_shapefx.setChecked(True)
        self.chk_layerfx = QCheckBox("Apply layer effects")
        self.chk_layerfx.setChecked(True)
        self.chk_fewparticles = QCheckBox("Reduced particles")
        self.chk_aa = QCheckBox("Antialiased edges")
        self.chk_aa.setChecked(True)
        self.chk_extrasmooth = QCheckBox("Extra-smooth images")
        self.chk_premultiply = QCheckBox("Premultiply alpha")
        self.chk_premultiply.setChecked(True)
        self.chk_ntscsafe = QCheckBox("NTSC safe colors")
        self.chk_verbose = QCheckBox("Verbose output")
        self.chk_verbose.setChecked(True)

        options_grid.addWidget(self.chk_multithread, 0, 0)
        options_grid.addWidget(self.chk_halfsize, 0, 1)
        options_grid.addWidget(self.chk_halffps, 0, 2)
        options_grid.addWidget(self.chk_shapefx, 1, 0)
        options_grid.addWidget(self.chk_layerfx, 1, 1)
        options_grid.addWidget(self.chk_fewparticles, 1, 2)
        options_grid.addWidget(self.chk_aa, 2, 0)
        options_grid.addWidget(self.chk_extrasmooth, 2, 1)
        options_grid.addWidget(self.chk_premultiply, 2, 2)
        options_grid.addWidget(self.chk_ntscsafe, 3, 0)
        options_grid.addWidget(self.chk_verbose, 3, 1)

        self.chk_copy_images = QCheckBox("Copy \\Images to project root (fix offline media)")
        options_grid.addWidget(self.chk_copy_images, 4, 0, 1, 3)

        self.options_group.setEnabled(False)
        self.chk_apply_options.toggled.connect(self.options_group.setEnabled)
        layout.addWidget(self.options_group)

        # --- Layer Compositions ---
        self.chk_apply_layercomp = QCheckBox("Apply Layer Comp Settings")
        layout.addWidget(self.chk_apply_layercomp)

        self.lc_group = QGroupBox("Layer Compositions")
        lc_layout = QFormLayout(self.lc_group)

        lc_row = QHBoxLayout()
        self.chk_allcomps = QCheckBox("Render AllComps")
        self.chk_allcomps.toggled.connect(self._on_allcomps_toggled)
        lc_row.addWidget(self.chk_allcomps)
        lc_row.addSpacing(20)
        lc_row.addWidget(QLabel("Custom Layer Comp:"))
        self.edit_layercomp = QLineEdit()
        self.edit_layercomp.setPlaceholderText("Enter comp name or AllLayerComps")
        lc_row.addWidget(self.edit_layercomp, 1)
        lc_layout.addRow("", lc_row)

        self.chk_addlayercompsuffix = QCheckBox("Add layer comp suffix to filename")
        self.chk_createfolderforlayercomp = QCheckBox("Create folder for each layer comp")
        self.chk_addformatsuffix = QCheckBox("Add format suffix to filename")

        lc_opts = QHBoxLayout()
        lc_opts.addWidget(self.chk_addlayercompsuffix)
        lc_opts.addWidget(self.chk_createfolderforlayercomp)
        lc_opts.addWidget(self.chk_addformatsuffix)
        lc_layout.addRow("Options:", lc_opts)

        self.chk_compose_layers = QCheckBox("Auto-compose all layer comps into MP4 with ffmpeg")
        lc_layout.addRow("", self.chk_compose_layers)

        self.lc_group.setEnabled(False)
        self.chk_apply_layercomp.toggled.connect(self.lc_group.setEnabled)
        layout.addWidget(self.lc_group)

        # --- QT Options ---
        self.chk_apply_qt = QCheckBox("Apply QuickTime Options")
        layout.addWidget(self.chk_apply_qt)

        self.qt_group = QGroupBox("QuickTime Options (QT format only)")
        qt_layout = QFormLayout(self.qt_group)

        self.combo_quality = QComboBox()
        for val, name in QUALITY_LEVELS.items():
            self.combo_quality.addItem(f"{val} - {name}", val)
        self.combo_quality.setCurrentIndex(3)
        qt_layout.addRow("Quality:", self.combo_quality)

        self.spin_depth = QSpinBox()
        self.spin_depth.setRange(1, 32)
        self.spin_depth.setValue(24)
        qt_layout.addRow("Pixel Depth:", self.spin_depth)

        self.qt_group.setEnabled(False)
        self.chk_apply_qt.toggled.connect(self.qt_group.setEnabled)
        layout.addWidget(self.qt_group)

        # --- Buttons ---
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_presets(self):
        fmt = self.combo_format.currentText()
        self.combo_preset.clear()
        if fmt in WINDOWS_PRESETS:
            self.combo_preset.addItems(WINDOWS_PRESETS[fmt])
        else:
            self.combo_preset.addItem("")

    def _on_allcomps_toggled(self, checked):
        self.edit_layercomp.setEnabled(not checked)
        if checked:
            self.edit_layercomp.setText("AllComps")
        else:
            self.edit_layercomp.clear()

    def _browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.edit_output_dir.setText(folder)

    def _populate_from_jobs(self):
        """Pre-populate fields from the first job (or single selected job)."""
        job = self.jobs[0]

        # Output
        self.combo_format.setCurrentText(job.format or "MP4")
        self._update_presets()
        if job.options:
            idx = self.combo_preset.findText(job.options)
            if idx >= 0:
                self.combo_preset.setCurrentIndex(idx)
        if job.output_path:
            self.edit_output_dir.setText(str(Path(job.output_path).parent))
        self.chk_subfolder_project.setChecked(job.subfolder_project)

        # Frame range
        if job.start_frame is not None:
            self.chk_custom_frames.setChecked(True)
            self.spin_start_frame.setValue(job.start_frame)
        if job.end_frame is not None:
            self.spin_end_frame.setValue(job.end_frame)

        # Render options
        def _set_chk(chk, val):
            if val is not None:
                chk.setChecked(val)
        _set_chk(self.chk_multithread, job.multithread)
        _set_chk(self.chk_halfsize, job.halfsize)
        _set_chk(self.chk_halffps, job.halffps)
        _set_chk(self.chk_shapefx, job.shapefx)
        _set_chk(self.chk_layerfx, job.layerfx)
        _set_chk(self.chk_fewparticles, job.fewparticles)
        _set_chk(self.chk_aa, job.aa)
        _set_chk(self.chk_extrasmooth, job.extrasmooth)
        _set_chk(self.chk_premultiply, job.premultiply)
        _set_chk(self.chk_ntscsafe, job.ntscsafe)
        self.chk_verbose.setChecked(job.verbose)
        self.chk_copy_images.setChecked(job.copy_images)

        # Layer comp
        if job.layercomp and job.layercomp.lower() in ("allcomps", "alllayercomps"):
            self.chk_allcomps.setChecked(True)
        elif job.layercomp:
            self.chk_allcomps.setChecked(False)
            self.edit_layercomp.setText(job.layercomp)
        _set_chk(self.chk_addlayercompsuffix, job.addlayercompsuffix)
        _set_chk(self.chk_createfolderforlayercomp, job.createfolderforlayercomps)
        _set_chk(self.chk_addformatsuffix, job.addformatsuffix)
        self.chk_compose_layers.setChecked(job.compose_layers)

        # QT
        if job.quality is not None:
            idx = self.combo_quality.findData(job.quality)
            if idx >= 0:
                self.combo_quality.setCurrentIndex(idx)
        if job.depth is not None:
            self.spin_depth.setValue(job.depth)

        # For single job, auto-check all groups
        if len(self.jobs) == 1:
            self.chk_apply_output.setChecked(True)
            self.chk_apply_frames.setChecked(True)
            self.chk_apply_options.setChecked(True)
            self.chk_apply_layercomp.setChecked(True)
            self.chk_apply_qt.setChecked(True)

    def _load_preset_list(self):
        """Populate the preset combo from saved JSON files."""
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        for f in sorted(PRESETS_DIR.glob("*.json")):
            self.combo_render_preset.addItem(f.stem)

    def _on_preset_selected(self, name):
        """Load preset settings into widgets when selected."""
        if name == "(none)" or not name:
            return
        preset_file = PRESETS_DIR / f"{name}.json"
        if not preset_file.exists():
            return
        try:
            with open(preset_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        # Output settings
        self.combo_format.setCurrentText(data.get("format", "MP4"))
        self._update_presets()
        opts = data.get("options", "")
        if opts:
            idx = self.combo_preset.findText(opts)
            if idx >= 0:
                self.combo_preset.setCurrentIndex(idx)
        self.edit_output_dir.setText(data.get("output_dir", ""))
        self.chk_subfolder_project.setChecked(data.get("subfolder_project", False))

        # Frame range
        custom_frames = data.get("custom_frames", False)
        self.chk_custom_frames.setChecked(custom_frames)
        if custom_frames:
            self.spin_start_frame.setValue(data.get("start_frame", 1))
            self.spin_end_frame.setValue(data.get("end_frame", 24))

        # Render options
        self.chk_multithread.setChecked(data.get("multithread", True))
        self.chk_halfsize.setChecked(data.get("halfsize", False))
        self.chk_halffps.setChecked(data.get("halffps", False))
        self.chk_shapefx.setChecked(data.get("shapefx", True))
        self.chk_layerfx.setChecked(data.get("layerfx", True))
        self.chk_fewparticles.setChecked(data.get("fewparticles", False))
        self.chk_aa.setChecked(data.get("aa", True))
        self.chk_extrasmooth.setChecked(data.get("extrasmooth", False))
        self.chk_premultiply.setChecked(data.get("premultiply", True))
        self.chk_ntscsafe.setChecked(data.get("ntscsafe", False))
        self.chk_verbose.setChecked(data.get("verbose", True))
        self.chk_copy_images.setChecked(data.get("copy_images", False))

        # Layer comps
        lc_value = data.get("layercomp", "")
        if lc_value.lower() in ("allcomps", "alllayercomps"):
            self.chk_allcomps.setChecked(True)
        else:
            self.chk_allcomps.setChecked(False)
            self.edit_layercomp.setText(lc_value)
        self.chk_addlayercompsuffix.setChecked(data.get("addlayercompsuffix", False))
        self.chk_createfolderforlayercomp.setChecked(data.get("createfolderforlayercomps", False))
        self.chk_addformatsuffix.setChecked(data.get("addformatsuffix", False))
        self.chk_compose_layers.setChecked(data.get("compose_layers", False))

        # QT options
        quality = data.get("quality", 3)
        idx = self.combo_quality.findData(quality)
        if idx >= 0:
            self.combo_quality.setCurrentIndex(idx)
        self.spin_depth.setValue(data.get("depth", 24))

        # Auto-check all Apply groups when loading a preset
        self.chk_apply_output.setChecked(True)
        self.chk_apply_frames.setChecked(True)
        self.chk_apply_options.setChecked(True)
        self.chk_apply_layercomp.setChecked(True)
        self.chk_apply_qt.setChecked(True)

    def _save_preset(self):
        """Save current settings as a named preset."""
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        data = {
            "format": self.combo_format.currentText(),
            "options": self.combo_preset.currentText(),
            "output_dir": self.edit_output_dir.text(),
            "subfolder_project": self.chk_subfolder_project.isChecked(),
            "custom_frames": self.chk_custom_frames.isChecked(),
            "start_frame": self.spin_start_frame.value(),
            "end_frame": self.spin_end_frame.value(),
            "multithread": self.chk_multithread.isChecked(),
            "halfsize": self.chk_halfsize.isChecked(),
            "halffps": self.chk_halffps.isChecked(),
            "shapefx": self.chk_shapefx.isChecked(),
            "layerfx": self.chk_layerfx.isChecked(),
            "fewparticles": self.chk_fewparticles.isChecked(),
            "aa": self.chk_aa.isChecked(),
            "extrasmooth": self.chk_extrasmooth.isChecked(),
            "premultiply": self.chk_premultiply.isChecked(),
            "ntscsafe": self.chk_ntscsafe.isChecked(),
            "verbose": self.chk_verbose.isChecked(),
            "copy_images": self.chk_copy_images.isChecked(),
            "layercomp": self.edit_layercomp.text(),
            "addlayercompsuffix": self.chk_addlayercompsuffix.isChecked(),
            "createfolderforlayercomps": self.chk_createfolderforlayercomp.isChecked(),
            "addformatsuffix": self.chk_addformatsuffix.isChecked(),
            "compose_layers": self.chk_compose_layers.isChecked(),
            "quality": self.combo_quality.currentData(),
            "depth": self.spin_depth.value(),
        }
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        preset_file = PRESETS_DIR / f"{name}.json"
        try:
            with open(preset_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            QMessageBox.critical(self, "Error", f"Failed to save preset:\n{e}")
            return
        if self.combo_render_preset.findText(name) < 0:
            self.combo_render_preset.addItem(name)
        self.combo_render_preset.setCurrentText(name)

    def _delete_preset(self):
        """Delete the currently selected preset."""
        name = self.combo_render_preset.currentText()
        if name == "(none)" or not name:
            return
        reply = QMessageBox.question(
            self, "Delete Preset",
            f"Delete preset '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        preset_file = PRESETS_DIR / f"{name}.json"
        if preset_file.exists():
            preset_file.unlink()
        idx = self.combo_render_preset.findText(name)
        if idx >= 0:
            self.combo_render_preset.removeItem(idx)

    def _apply(self):
        """Apply checked settings to all selected jobs."""
        ext_map = {
            "JPEG": ".jpg", "TGA": ".tga", "BMP": ".bmp",
            "PNG": ".png", "PSD": ".psd", "QT": ".mov",
            "MP4": ".mp4", "Animated GIF": ".gif",
        }

        for job in self.jobs:
            if self.chk_apply_output.isChecked():
                job.format = self.combo_format.currentText()
                job.options = self.combo_preset.currentText() or ""
                job.subfolder_project = self.chk_subfolder_project.isChecked()
                out_dir = self.edit_output_dir.text()
                if out_dir:
                    name = Path(job.project_file).stem
                    ext = ext_map.get(job.format, ".mp4")
                    if job.subfolder_project:
                        job.output_path = os.path.join(out_dir, name, name + ext)
                    else:
                        job.output_path = os.path.join(out_dir, name + ext)
                else:
                    job.output_path = ""

            if self.chk_apply_frames.isChecked():
                if self.chk_custom_frames.isChecked():
                    job.start_frame = self.spin_start_frame.value()
                    job.end_frame = self.spin_end_frame.value()
                else:
                    job.start_frame = None
                    job.end_frame = None

            if self.chk_apply_options.isChecked():
                job.verbose = self.chk_verbose.isChecked()
                job.multithread = self.chk_multithread.isChecked()
                job.halfsize = self.chk_halfsize.isChecked()
                job.halffps = self.chk_halffps.isChecked()
                job.shapefx = self.chk_shapefx.isChecked()
                job.layerfx = self.chk_layerfx.isChecked()
                job.fewparticles = self.chk_fewparticles.isChecked()
                job.aa = self.chk_aa.isChecked()
                job.extrasmooth = self.chk_extrasmooth.isChecked()
                job.premultiply = self.chk_premultiply.isChecked()
                job.ntscsafe = self.chk_ntscsafe.isChecked()
                job.copy_images = self.chk_copy_images.isChecked()

            if self.chk_apply_layercomp.isChecked():
                lc = self.edit_layercomp.text().strip()
                job.layercomp = lc if lc else ""
                job.addlayercompsuffix = self.chk_addlayercompsuffix.isChecked()
                job.createfolderforlayercomps = self.chk_createfolderforlayercomp.isChecked()
                job.addformatsuffix = self.chk_addformatsuffix.isChecked()
                job.compose_layers = self.chk_compose_layers.isChecked()

            if self.chk_apply_qt.isChecked():
                job.quality = self.combo_quality.currentData()
                depth_val = self.spin_depth.value()
                job.depth = depth_val if depth_val != 24 else None

        self.accept()


class MainWindow(QMainWindow):
    """Main application window."""

    log_signal = pyqtSignal(str)
    queue_changed_signal = pyqtSignal()
    progress_signal = pyqtSignal(str, float)  # job_id, progress
    job_status_signal = pyqtSignal(str, str)  # job_id, status

    def __init__(self, config: AppConfig, initial_files=None, add_to_queue_files=None):
        super().__init__()
        self.config = config
        self.queue = RenderQueue(config.moho_path)

        # Connect queue callbacks via signals for thread safety
        self.queue.on_output = self._emit_log
        self.queue.on_queue_changed = self._emit_queue_changed
        self.queue.on_progress = self._emit_progress
        self.queue.on_job_started = lambda j: self._emit_job_status(j.id, "rendering")
        self.queue.on_job_completed = lambda j: self._emit_job_status(j.id, "completed")
        self.queue.on_job_failed = lambda j: self._emit_job_status(j.id, "failed")
        self.queue.on_queue_completed = self._on_queue_completed

        # Network components
        self.master_server = None
        self.slave_client = None

        self._setup_ui()
        self._connect_signals()
        self._setup_menu()
        self.setAcceptDrops(True)

        # Load default preset if configured
        default_preset = self.config.get("default_preset", "")
        if default_preset:
            idx = self.combo_render_preset.findText(default_preset)
            if idx >= 0:
                self.combo_render_preset.setCurrentIndex(idx)

        # Handle initial files from command line / context menu
        if initial_files:
            for f in initial_files:
                self._add_file_to_queue(f)
            self._start_queue()
        elif add_to_queue_files:
            for f in add_to_queue_files:
                self._add_file_to_queue(f)

    def _setup_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1100, 750)
        self.resize(1300, 850)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("titleLabel")
        subtitle = QLabel(f"v{APP_VERSION} by {APP_AUTHOR}")
        subtitle.setObjectName("subtitleLabel")
        header_text = QVBoxLayout()
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text)
        header.addStretch()

        # Global progress
        self.global_progress = QProgressBar()
        self.global_progress.setFixedWidth(300)
        self.global_progress.setFormat("%v/%m jobs completed")
        header.addWidget(self.global_progress)
        main_layout.addLayout(header)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Render Queue
        self.tabs.addTab(self._create_queue_tab(), "Render Queue")
        # Tab 2: Render Settings
        self.tabs.addTab(self._create_settings_tab(), "Render Settings")
        # Tab 3: Render Farm
        self.tabs.addTab(self._create_farm_tab(), "Render Farm")
        # Tab 4: Settings
        self.tabs.addTab(self._create_app_settings_tab(), "App Settings")

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _create_queue_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Splitter: queue table + log
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top: Queue controls + table
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # Controls bar
        controls = QHBoxLayout()

        self.btn_add_files = QPushButton("Add Projects")
        self.btn_add_files.setObjectName("primaryBtn")
        self.btn_add_folder = QPushButton("Add Folder")
        controls.addWidget(self.btn_add_files)
        controls.addWidget(self.btn_add_folder)

        controls.addSpacing(20)

        self.btn_start_queue = QPushButton("Start Queue")
        self.btn_start_queue.setObjectName("successBtn")
        self.btn_pause_queue = QPushButton("Pause")
        self.btn_stop_queue = QPushButton("Stop")
        self.btn_stop_queue.setObjectName("dangerBtn")
        controls.addWidget(self.btn_start_queue)
        controls.addWidget(self.btn_pause_queue)
        controls.addWidget(self.btn_stop_queue)

        controls.addSpacing(20)

        self.btn_clear_completed = QPushButton("Clear Completed")
        self.btn_clear_all = QPushButton("Clear All")
        controls.addWidget(self.btn_clear_completed)
        controls.addWidget(self.btn_clear_all)

        controls.addStretch()

        self.btn_save_queue = QPushButton("Save Queue")
        self.btn_load_queue = QPushButton("Load Queue")
        controls.addWidget(self.btn_save_queue)
        controls.addWidget(self.btn_load_queue)

        top_layout.addLayout(controls)

        # Queue table
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(9)
        self.queue_table.setHorizontalHeaderLabels([
            "Status", "Project", "Format", "Layer Comp", "Output", "Progress",
            "Time", "Slave", "ID"
        ])
        self.queue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.queue_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.queue_table.customContextMenuRequested.connect(self._show_queue_context_menu)
        top_layout.addWidget(self.queue_table)

        splitter.addWidget(top_widget)

        # Bottom: Log output
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)

        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("Output Log"))
        self.btn_clear_log = QPushButton("Clear Log")
        self.btn_clear_log.setFixedWidth(80)
        log_header.addStretch()
        log_header.addWidget(self.btn_clear_log)
        log_layout.addLayout(log_header)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(200)
        log_layout.addWidget(self.log_output)

        splitter.addWidget(log_widget)
        splitter.setSizes([500, 200])

        layout.addWidget(splitter)
        return widget

    def _create_settings_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Presets bar
        preset_group = QGroupBox("Render Presets")
        preset_layout = QHBoxLayout(preset_group)
        preset_layout.addWidget(QLabel("Preset:"))
        self.combo_render_preset = QComboBox()
        self.combo_render_preset.setMinimumWidth(200)
        self.combo_render_preset.addItem("(none)")
        self._load_preset_list()
        self.combo_render_preset.currentTextChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self.combo_render_preset)
        self.btn_save_preset = QPushButton("Save Preset")
        self.btn_save_preset.clicked.connect(self._save_preset)
        preset_layout.addWidget(self.btn_save_preset)
        self.btn_delete_preset = QPushButton("Delete Preset")
        self.btn_delete_preset.clicked.connect(self._delete_preset)
        preset_layout.addWidget(self.btn_delete_preset)
        self.chk_default_preset = QCheckBox("Set as Default")
        self.chk_default_preset.toggled.connect(self._set_default_preset)
        preset_layout.addWidget(self.chk_default_preset)
        preset_layout.addStretch()
        layout.addWidget(preset_group)

        # Output settings
        output_group = QGroupBox("Output Settings")
        output_form = QFormLayout(output_group)

        self.combo_format = QComboBox()
        self.combo_format.addItems(FORMATS)
        self.combo_format.setCurrentText(self.config.get("default_format", "MP4"))
        self.combo_format.currentTextChanged.connect(self._on_format_changed)
        output_form.addRow("Format:", self.combo_format)

        self.combo_preset = QComboBox()
        self._update_presets()
        output_form.addRow("Preset/Codec:", self.combo_preset)

        self.edit_output_dir = QLineEdit()
        self.edit_output_dir.setPlaceholderText("Same folder as project file (default)")
        self.edit_output_dir.setText(self.config.get("default_output_dir", ""))
        browse_out = QPushButton("Browse...")
        browse_out.setFixedWidth(80)
        browse_out.clicked.connect(self._browse_output_dir)
        out_row = QHBoxLayout()
        out_row.addWidget(self.edit_output_dir)
        out_row.addWidget(browse_out)
        output_form.addRow("Output Folder:", out_row)

        self.chk_subfolder_project = QCheckBox("Create subfolder with project name")
        output_form.addRow("", self.chk_subfolder_project)

        layout.addWidget(output_group)

        # Frame range
        frame_group = QGroupBox("Frame Range")
        frame_layout = QHBoxLayout(frame_group)

        self.chk_custom_frames = QCheckBox("Custom frame range")
        frame_layout.addWidget(self.chk_custom_frames)

        frame_layout.addWidget(QLabel("Start:"))
        self.spin_start_frame = QSpinBox()
        self.spin_start_frame.setRange(0, 999999)
        self.spin_start_frame.setValue(1)
        self.spin_start_frame.setEnabled(False)
        frame_layout.addWidget(self.spin_start_frame)

        frame_layout.addWidget(QLabel("End:"))
        self.spin_end_frame = QSpinBox()
        self.spin_end_frame.setRange(0, 999999)
        self.spin_end_frame.setValue(24)
        self.spin_end_frame.setEnabled(False)
        frame_layout.addWidget(self.spin_end_frame)

        self.chk_custom_frames.toggled.connect(self.spin_start_frame.setEnabled)
        self.chk_custom_frames.toggled.connect(self.spin_end_frame.setEnabled)

        frame_layout.addStretch()
        layout.addWidget(frame_group)

        # Render options grid
        options_group = QGroupBox("Render Options")
        options_grid = QGridLayout(options_group)

        self.chk_multithread = QCheckBox("Multi-threaded rendering")
        self.chk_multithread.setChecked(True)
        self.chk_halfsize = QCheckBox("Render at half size")
        self.chk_halffps = QCheckBox("Render at half frame rate")
        self.chk_shapefx = QCheckBox("Apply shape effects")
        self.chk_shapefx.setChecked(True)
        self.chk_layerfx = QCheckBox("Apply layer effects")
        self.chk_layerfx.setChecked(True)
        self.chk_fewparticles = QCheckBox("Reduced particles")
        self.chk_aa = QCheckBox("Antialiased edges")
        self.chk_aa.setChecked(True)
        self.chk_extrasmooth = QCheckBox("Extra-smooth images")
        self.chk_premultiply = QCheckBox("Premultiply alpha")
        self.chk_premultiply.setChecked(True)
        self.chk_ntscsafe = QCheckBox("NTSC safe colors")
        self.chk_verbose = QCheckBox("Verbose output")
        self.chk_verbose.setChecked(True)

        options_grid.addWidget(self.chk_multithread, 0, 0)
        options_grid.addWidget(self.chk_halfsize, 0, 1)
        options_grid.addWidget(self.chk_halffps, 0, 2)
        options_grid.addWidget(self.chk_shapefx, 1, 0)
        options_grid.addWidget(self.chk_layerfx, 1, 1)
        options_grid.addWidget(self.chk_fewparticles, 1, 2)
        options_grid.addWidget(self.chk_aa, 2, 0)
        options_grid.addWidget(self.chk_extrasmooth, 2, 1)
        options_grid.addWidget(self.chk_premultiply, 2, 2)
        options_grid.addWidget(self.chk_ntscsafe, 3, 0)
        options_grid.addWidget(self.chk_verbose, 3, 1)

        self.chk_copy_images = QCheckBox("Copy \\Images to project root (fix offline media)")
        options_grid.addWidget(self.chk_copy_images, 4, 0, 1, 3)

        layout.addWidget(options_group)

        # Layer comps
        lc_group = QGroupBox("Layer Compositions")
        lc_layout = QFormLayout(lc_group)

        lc_row = QHBoxLayout()
        self.chk_allcomps = QCheckBox("Render AllComps")
        self.chk_allcomps.toggled.connect(self._on_allcomps_toggled)
        lc_row.addWidget(self.chk_allcomps)
        lc_row.addSpacing(20)
        lc_row.addWidget(QLabel("Custom Layer Comp:"))
        self.edit_layercomp = QLineEdit()
        self.edit_layercomp.setPlaceholderText("Enter comp name or AllLayerComps")
        lc_row.addWidget(self.edit_layercomp, 1)
        lc_layout.addRow("", lc_row)

        self.chk_addlayercompsuffix = QCheckBox("Add layer comp suffix to filename")
        self.chk_createfolderforlayercomp = QCheckBox("Create folder for each layer comp")
        self.chk_addformatsuffix = QCheckBox("Add format suffix to filename")

        lc_opts = QHBoxLayout()
        lc_opts.addWidget(self.chk_addlayercompsuffix)
        lc_opts.addWidget(self.chk_createfolderforlayercomp)
        lc_opts.addWidget(self.chk_addformatsuffix)
        lc_layout.addRow("Options:", lc_opts)

        self.chk_compose_layers = QCheckBox("Auto-compose all layer comps into MP4 with ffmpeg")
        lc_layout.addRow("", self.chk_compose_layers)

        layout.addWidget(lc_group)

        # QuickTime specific
        qt_group = QGroupBox("QuickTime Options (QT format only)")
        qt_layout = QFormLayout(qt_group)

        self.combo_quality = QComboBox()
        for val, name in QUALITY_LEVELS.items():
            self.combo_quality.addItem(f"{val} - {name}", val)
        self.combo_quality.setCurrentIndex(3)
        qt_layout.addRow("Quality:", self.combo_quality)

        self.spin_depth = QSpinBox()
        self.spin_depth.setRange(1, 32)
        self.spin_depth.setValue(24)
        qt_layout.addRow("Pixel Depth:", self.spin_depth)

        layout.addWidget(qt_group)
        layout.addStretch()
        scroll.setWidget(widget)
        return scroll

    def _create_farm_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Mode selection
        mode_group = QGroupBox("Render Farm Mode")
        mode_layout = QVBoxLayout(mode_group)

        mode_row = QHBoxLayout()
        self.btn_start_master = QPushButton("Start as Master")
        self.btn_start_master.setObjectName("primaryBtn")
        self.btn_stop_master = QPushButton("Stop Master")
        self.btn_stop_master.setObjectName("dangerBtn")
        self.btn_stop_master.setEnabled(False)
        mode_row.addWidget(self.btn_start_master)
        mode_row.addWidget(self.btn_stop_master)
        mode_row.addSpacing(30)

        self.btn_start_slave = QPushButton("Start as Slave")
        self.btn_start_slave.setObjectName("primaryBtn")
        self.btn_stop_slave = QPushButton("Stop Slave")
        self.btn_stop_slave.setObjectName("dangerBtn")
        self.btn_stop_slave.setEnabled(False)
        mode_row.addWidget(self.btn_start_slave)
        mode_row.addWidget(self.btn_stop_slave)
        mode_row.addStretch()
        mode_layout.addLayout(mode_row)

        # Connection settings
        conn_row = QHBoxLayout()
        conn_row.addWidget(QLabel("Master Host:"))
        self.edit_master_host = QLineEdit()
        self.edit_master_host.setText(self.config.get("network_master_host", "localhost"))
        self.edit_master_host.setFixedWidth(200)
        conn_row.addWidget(self.edit_master_host)
        conn_row.addWidget(QLabel("Port:"))
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1024, 65535)
        self.spin_port.setValue(self.config.get("network_port", 5580))
        self.spin_port.setFixedWidth(100)
        conn_row.addWidget(self.spin_port)
        conn_row.addStretch()

        self.lbl_farm_status = QLabel("Status: Not started")
        self.lbl_farm_status.setStyleSheet("color: #f9e2af; font-weight: bold;")
        conn_row.addWidget(self.lbl_farm_status)
        mode_layout.addLayout(conn_row)

        layout.addWidget(mode_group)

        # Connected slaves
        slaves_group = QGroupBox("Connected Slaves")
        slaves_layout = QVBoxLayout(slaves_group)

        self.slaves_table = QTableWidget()
        self.slaves_table.setColumnCount(6)
        self.slaves_table.setHorizontalHeaderLabels([
            "Hostname", "IP:Port", "Status", "Current Job", "Completed", "Failed"
        ])
        self.slaves_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.slaves_table.setAlternatingRowColors(True)
        self.slaves_table.verticalHeader().setVisible(False)
        slaves_layout.addWidget(self.slaves_table)

        layout.addWidget(slaves_group)

        # Farm log
        farm_log_group = QGroupBox("Farm Log")
        farm_log_layout = QVBoxLayout(farm_log_group)
        self.farm_log = QTextEdit()
        self.farm_log.setReadOnly(True)
        farm_log_layout.addWidget(self.farm_log)
        layout.addWidget(farm_log_group)

        return widget

    def _create_app_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Moho path
        moho_group = QGroupBox("Moho Application")
        moho_layout = QFormLayout(moho_group)

        self.edit_moho_path = QLineEdit()
        self.edit_moho_path.setText(self.config.moho_path)
        browse_moho = QPushButton("Browse...")
        browse_moho.setFixedWidth(80)
        browse_moho.clicked.connect(self._browse_moho)
        moho_row = QHBoxLayout()
        moho_row.addWidget(self.edit_moho_path)
        moho_row.addWidget(browse_moho)
        moho_layout.addRow("Moho.exe Path:", moho_row)

        layout.addWidget(moho_group)

        # Context menu
        ctx_group = QGroupBox("Windows Integration")
        ctx_layout = QVBoxLayout(ctx_group)

        ctx_info = QLabel(
            "Register right-click context menu for .moho files.\n"
            "This adds 'Render with Moho Render Farm' and 'Add to Queue' options."
        )
        ctx_info.setWordWrap(True)
        ctx_layout.addWidget(ctx_info)

        ctx_btns = QHBoxLayout()
        self.btn_register_ctx = QPushButton("Register Context Menu")
        self.btn_register_ctx.setObjectName("primaryBtn")
        self.btn_unregister_ctx = QPushButton("Unregister Context Menu")
        self.btn_unregister_ctx.setObjectName("dangerBtn")
        ctx_btns.addWidget(self.btn_register_ctx)
        ctx_btns.addWidget(self.btn_unregister_ctx)
        ctx_btns.addStretch()
        ctx_layout.addLayout(ctx_btns)

        layout.addWidget(ctx_group)

        # About
        about_group = QGroupBox("About")
        about_layout = QVBoxLayout(about_group)
        about_layout.addWidget(QLabel(f"{APP_NAME} v{APP_VERSION}"))
        about_layout.addWidget(QLabel(f"Created by {APP_AUTHOR}"))
        about_layout.addWidget(QLabel("Batch rendering tool for Moho Animation v14"))
        layout.addWidget(about_group)

        layout.addStretch()
        return widget

    def _connect_signals(self):
        # Thread-safe signals
        self.log_signal.connect(self._append_log)
        self.queue_changed_signal.connect(self._refresh_queue_table)
        self.progress_signal.connect(self._update_job_progress)
        self.job_status_signal.connect(self._update_job_status)

        # Queue controls
        self.btn_add_files.clicked.connect(self._add_files)
        self.btn_add_folder.clicked.connect(self._add_folder)
        self.btn_start_queue.clicked.connect(self._start_queue)
        self.btn_pause_queue.clicked.connect(self._pause_queue)
        self.btn_stop_queue.clicked.connect(self._stop_queue)
        self.btn_clear_completed.clicked.connect(self.queue.clear_completed)
        self.btn_clear_all.clicked.connect(self._clear_all_confirm)
        self.btn_save_queue.clicked.connect(self._save_queue)
        self.btn_load_queue.clicked.connect(self._load_queue)
        self.btn_clear_log.clicked.connect(self.log_output.clear)

        # Farm
        self.btn_start_master.clicked.connect(self._start_master)
        self.btn_stop_master.clicked.connect(self._stop_master)
        self.btn_start_slave.clicked.connect(self._start_slave)
        self.btn_stop_slave.clicked.connect(self._stop_slave)

        # Settings
        self.btn_register_ctx.clicked.connect(self._register_context_menu)
        self.btn_unregister_ctx.clicked.connect(self._unregister_context_menu)

        # Keyboard shortcuts
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self._delete_selected_jobs)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._stop_queue)

    def _setup_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")
        act_add = QAction("Add Projects...", self)
        act_add.setShortcut("Ctrl+O")
        act_add.triggered.connect(self._add_files)
        file_menu.addAction(act_add)

        act_add_folder = QAction("Add Folder...", self)
        act_add_folder.triggered.connect(self._add_folder)
        file_menu.addAction(act_add_folder)

        file_menu.addSeparator()

        act_save_q = QAction("Save Queue...", self)
        act_save_q.setShortcut("Ctrl+S")
        act_save_q.triggered.connect(self._save_queue)
        file_menu.addAction(act_save_q)

        act_load_q = QAction("Load Queue...", self)
        act_load_q.setShortcut("Ctrl+L")
        act_load_q.triggered.connect(self._load_queue)
        file_menu.addAction(act_load_q)

        file_menu.addSeparator()

        act_exit = QAction("Exit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Queue menu
        queue_menu = menubar.addMenu("Queue")
        act_start = QAction("Start Queue", self)
        act_start.setShortcut("F5")
        act_start.triggered.connect(self._start_queue)
        queue_menu.addAction(act_start)

        act_pause = QAction("Pause Queue", self)
        act_pause.setShortcut("F6")
        act_pause.triggered.connect(self._pause_queue)
        queue_menu.addAction(act_pause)

        act_stop = QAction("Stop Queue (Escape)", self)
        act_stop.setShortcut("F7")
        act_stop.triggered.connect(self._stop_queue)
        queue_menu.addAction(act_stop)

        queue_menu.addSeparator()

        act_remove = QAction("Remove Selected", self)
        act_remove.setShortcut("Delete")
        act_remove.triggered.connect(self._delete_selected_jobs)
        queue_menu.addAction(act_remove)

        act_clear_done = QAction("Clear Completed", self)
        act_clear_done.triggered.connect(self.queue.clear_completed)
        queue_menu.addAction(act_clear_done)

    # --- Signal emitters (called from worker threads) ---
    def _emit_log(self, msg):
        self.log_signal.emit(msg)

    def _emit_queue_changed(self):
        self.queue_changed_signal.emit()

    def _emit_progress(self, job, progress):
        self.progress_signal.emit(job.id, progress)

    def _emit_job_status(self, job_id, status):
        self.job_status_signal.emit(job_id, status)

    def _on_queue_completed(self):
        self._emit_log("All queue jobs completed!")
        # Stop timer on main thread via signal
        QTimer.singleShot(0, self._stop_render_timer)

    # --- Slots (run on main thread) ---
    def _append_log(self, msg):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        line = f"{timestamp} {msg}"
        self.log_output.append(line)
        sb = self.log_output.verticalScrollBar()
        sb.setValue(sb.maximum())
        # Auto-save to log file
        if hasattr(self, '_log_file_handle') and self._log_file_handle:
            try:
                self._log_file_handle.write(line + "\n")
                self._log_file_handle.flush()
            except (IOError, OSError):
                pass

    def _refresh_queue_table(self):
        jobs = self.queue.jobs
        self.queue_table.setRowCount(len(jobs))

        for row, job in enumerate(jobs):
            # Status
            status_item = QTableWidgetItem(job.status.upper())
            color_map = {
                "pending": "#f9e2af",
                "rendering": "#89b4fa",
                "completed": "#a6e3a1",
                "failed": "#f38ba8",
                "cancelled": "#6c7086",
            }
            status_item.setForeground(
                __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(
                    color_map.get(job.status, "#cdd6f4")
                )
            )
            self.queue_table.setItem(row, 0, status_item)

            # Project
            self.queue_table.setItem(row, 1, QTableWidgetItem(job.project_name))
            # Format
            self.queue_table.setItem(row, 2, QTableWidgetItem(f"{job.format}"))
            # Layer Comp
            self.queue_table.setItem(row, 3, QTableWidgetItem(job.layercomp or "(default)"))
            # Output
            out = job.output_path or "(project folder)"
            self.queue_table.setItem(row, 4, QTableWidgetItem(out))
            # Progress
            prog_item = QTableWidgetItem(f"{job.progress:.0f}%")
            self.queue_table.setItem(row, 5, prog_item)
            # Time
            self.queue_table.setItem(row, 6, QTableWidgetItem(job.elapsed_str))
            # Slave
            self.queue_table.setItem(row, 7, QTableWidgetItem(job.assigned_slave or "Local"))
            # ID (store job_id)
            self.queue_table.setItem(row, 8, QTableWidgetItem(job.id))

        # Update global progress
        total = self.queue.total_jobs
        completed = self.queue.completed_count
        self.global_progress.setMaximum(max(total, 1))
        self.global_progress.setValue(completed)
        self.global_progress.setFormat(f"{completed}/{total} jobs completed")

        self.status_bar.showMessage(
            f"Queue: {total} jobs | Pending: {self.queue.pending_count} | "
            f"Completed: {completed} | Failed: {self.queue.failed_count}"
        )

    def _update_job_progress(self, job_id, progress):
        for row in range(self.queue_table.rowCount()):
            id_item = self.queue_table.item(row, 8)
            if id_item and id_item.text() == job_id:
                self.queue_table.setItem(row, 5, QTableWidgetItem(f"{progress:.0f}%"))
                # Also update elapsed time
                job = self.queue.get_job(job_id)
                if job:
                    self.queue_table.setItem(row, 6, QTableWidgetItem(job.elapsed_str))
                break

    def _update_job_status(self, job_id, status):
        self._refresh_queue_table()

    # --- File operations ---
    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Moho Projects", "",
            "Moho Projects (*.moho *.anime *.anme);;All Files (*)"
        )
        for f in files:
            self._add_file_to_queue(f)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with Moho Projects")
        if folder:
            count = 0
            for root, dirs, files in os.walk(folder):
                for f in files:
                    ext = Path(f).suffix.lower()
                    if ext in MOHO_FILE_EXTENSIONS:
                        self._add_file_to_queue(os.path.join(root, f))
                        count += 1
            if count == 0:
                QMessageBox.information(self, "No Projects", "No Moho project files found in the selected folder.")

    def _add_file_to_queue(self, filepath):
        job = self._create_job_from_settings(filepath)
        self.queue.add_job(job)
        self.config.add_recent_project(filepath)
        self._append_log(f"Added to queue: {Path(filepath).name}")

    def _create_job_from_settings(self, filepath):
        """Create a RenderJob from current GUI settings."""
        job = RenderJob()
        job.project_file = filepath
        job.format = self.combo_format.currentText()

        # Set preset/options for video formats
        if self.combo_preset.currentText():
            job.options = self.combo_preset.currentText()
        else:
            job.options = ""

        job.subfolder_project = self.chk_subfolder_project.isChecked()
        if self.edit_output_dir.text():
            out_dir = self.edit_output_dir.text()
            name = Path(filepath).stem
            ext_map = {
                "JPEG": ".jpg", "TGA": ".tga", "BMP": ".bmp",
                "PNG": ".png", "PSD": ".psd", "QT": ".mov",
                "MP4": ".mp4", "Animated GIF": ".gif",
            }
            ext = ext_map.get(job.format, ".mp4")
            if job.subfolder_project:
                job.output_path = os.path.join(out_dir, name, name + ext)
            else:
                job.output_path = os.path.join(out_dir, name + ext)

        if self.chk_custom_frames.isChecked():
            job.start_frame = self.spin_start_frame.value()
            job.end_frame = self.spin_end_frame.value()

        job.verbose = self.chk_verbose.isChecked()
        job.multithread = self.chk_multithread.isChecked()
        job.halfsize = self.chk_halfsize.isChecked()
        job.halffps = self.chk_halffps.isChecked()
        job.shapefx = self.chk_shapefx.isChecked()
        job.layerfx = self.chk_layerfx.isChecked()
        job.fewparticles = self.chk_fewparticles.isChecked()
        job.aa = self.chk_aa.isChecked()
        job.extrasmooth = self.chk_extrasmooth.isChecked()
        job.premultiply = self.chk_premultiply.isChecked()
        job.ntscsafe = self.chk_ntscsafe.isChecked()

        lc = self.edit_layercomp.text().strip()
        if lc:
            job.layercomp = lc
        job.addlayercompsuffix = self.chk_addlayercompsuffix.isChecked()
        job.createfolderforlayercomps = self.chk_createfolderforlayercomp.isChecked()
        job.addformatsuffix = self.chk_addformatsuffix.isChecked()
        job.compose_layers = self.chk_compose_layers.isChecked()

        job.copy_images = self.chk_copy_images.isChecked()

        if self.combo_format.currentText() == "QT":
            job.quality = self.combo_quality.currentData()
            depth_val = self.spin_depth.value()
            if depth_val != 24:
                job.depth = depth_val

        return job

    # --- Log file auto-save ---
    def _open_log_file(self):
        """Open a log file for auto-saving output during queue execution."""
        try:
            log_dir = CONFIG_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_path = log_dir / f"queue_{ts}.log"
            self._log_file_handle = open(log_path, "w", encoding="utf-8")
            self._append_log(f"Log auto-save: {log_path}")
        except (IOError, OSError) as e:
            self._log_file_handle = None
            self._append_log(f"Warning: Could not open log file: {e}")

    def _close_log_file(self):
        """Close the auto-save log file."""
        if hasattr(self, '_log_file_handle') and self._log_file_handle:
            try:
                self._log_file_handle.close()
            except (IOError, OSError):
                pass
            self._log_file_handle = None

    # --- Queue actions ---
    def _start_queue(self):
        if not self.queue.jobs:
            self._append_log("Queue is empty. Add projects first.")
            return
        # Update moho path
        self.queue.moho_path = self.edit_moho_path.text()
        self._open_log_file()
        self.queue.start()
        self._start_render_timer()
        self._append_log("Queue started")
        self.status_bar.showMessage("Rendering...")

    def _pause_queue(self):
        if self.queue.is_running:
            if self.queue.is_paused:
                self.queue.resume()
                self._append_log("Queue resumed")
                self.btn_pause_queue.setText("Pause")
            else:
                self.queue.pause()
                self._append_log("Queue paused (current job will finish)")
                self.btn_pause_queue.setText("Resume")

    def _stop_queue(self):
        self.queue.stop()
        self._stop_render_timer()
        self._append_log("Queue stopped")
        self._close_log_file()
        self.btn_pause_queue.setText("Pause")

    def _clear_all_confirm(self):
        if self.queue.total_jobs > 0:
            reply = QMessageBox.question(
                self, "Clear Queue",
                "Remove all non-rendering jobs from the queue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.queue.clear_all()

    # --- Queue save/load ---
    def _save_queue(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Queue", str(QUEUE_DIR),
            "Queue Files (*.json);;All Files (*)"
        )
        if filepath:
            self.queue.save_queue(filepath)
            self.config.add_recent_queue(filepath)
            self._append_log(f"Queue saved: {filepath}")

    def _load_queue(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Queue", str(QUEUE_DIR),
            "Queue Files (*.json);;All Files (*)"
        )
        if filepath:
            try:
                self.queue.load_queue(filepath, append=True)
                self.config.add_recent_queue(filepath)
                self._append_log(f"Queue loaded: {filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load queue:\n{e}")

    # --- Delete selected jobs via keyboard ---
    def _delete_selected_jobs(self):
        """Remove selected jobs from the queue (Delete key)."""
        selected_rows = sorted(set(idx.row() for idx in self.queue_table.selectedIndexes()), reverse=True)
        if not selected_rows:
            return
        for row in selected_rows:
            if row < len(self.queue.jobs):
                job = self.queue.jobs[row]
                if job.status != RenderStatus.RENDERING.value:
                    self.queue.remove_job(job.id)

    # --- Context menu for queue table ---
    def _show_queue_context_menu(self, pos):
        row = self.queue_table.rowAt(pos.y())
        if row < 0 or row >= len(self.queue.jobs):
            return
        job = self.queue.jobs[row]

        # Collect all selected jobs
        selected_rows = sorted(set(idx.row() for idx in self.queue_table.selectedIndexes()))
        selected_jobs = [self.queue.jobs[r] for r in selected_rows if r < len(self.queue.jobs)]
        if not selected_jobs:
            selected_jobs = [job]

        menu = QMenu(self)

        # Edit Render Settings (for non-rendering jobs)
        editable_jobs = [j for j in selected_jobs if j.status != RenderStatus.RENDERING.value]
        if editable_jobs:
            act_edit = menu.addAction(f"Edit Render Settings ({len(editable_jobs)} job{'s' if len(editable_jobs) > 1 else ''})")
            act_edit.triggered.connect(lambda: self._edit_job_settings(editable_jobs))

        # Show in Explorer
        act_show = menu.addAction("Show in Explorer")
        act_show.triggered.connect(lambda: self._show_in_explorer(job))

        menu.addSeparator()

        if job.status in (RenderStatus.FAILED.value, RenderStatus.CANCELLED.value, RenderStatus.COMPLETED.value):
            act_retry = menu.addAction("Retry")
            act_retry.triggered.connect(lambda: self.queue.retry_job(job.id))
        act_dup = menu.addAction("Duplicate")
        act_dup.triggered.connect(lambda: self.queue.duplicate_job(job.id))
        menu.addSeparator()
        act_up = menu.addAction("Move Up")
        act_up.triggered.connect(lambda: self.queue.move_job(job.id, -1))
        act_down = menu.addAction("Move Down")
        act_down.triggered.connect(lambda: self.queue.move_job(job.id, 1))
        menu.addSeparator()
        act_remove = menu.addAction("Remove")
        act_remove.triggered.connect(lambda: self.queue.remove_job(job.id))
        if job.status == RenderStatus.RENDERING.value:
            act_cancel = menu.addAction("Cancel Render")
            act_cancel.triggered.connect(self.queue.cancel_current)

        menu.exec(self.queue_table.viewport().mapToGlobal(pos))

    def _show_in_explorer(self, job):
        """Open Windows Explorer with the project file selected."""
        import subprocess
        filepath = job.project_file
        if os.path.exists(filepath):
            subprocess.Popen(['explorer', '/select,', os.path.normpath(filepath)])
        else:
            # Open the parent folder if file doesn't exist
            folder = os.path.dirname(filepath)
            if os.path.exists(folder):
                subprocess.Popen(['explorer', os.path.normpath(folder)])
            else:
                QMessageBox.warning(self, "Not Found", f"File not found:\n{filepath}")

    def _edit_job_settings(self, jobs):
        """Open the Edit Render Settings dialog for the given jobs."""
        dialog = EditSettingsDialog(jobs, parent=self)
        result = dialog.exec()
        # Refresh main preset combo in case presets were saved/deleted in dialog
        current = self.combo_render_preset.currentText()
        self.combo_render_preset.blockSignals(True)
        self.combo_render_preset.clear()
        self.combo_render_preset.addItem("(none)")
        self._load_preset_list()
        idx = self.combo_render_preset.findText(current)
        if idx >= 0:
            self.combo_render_preset.setCurrentIndex(idx)
        self.combo_render_preset.blockSignals(False)
        if result == QDialog.DialogCode.Accepted:
            if self.queue.on_queue_changed:
                self.queue.on_queue_changed()
            self._append_log(f"Updated render settings for {len(jobs)} job{'s' if len(jobs) > 1 else ''}")

    # --- Drag and drop ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if Path(path).suffix.lower() in MOHO_FILE_EXTENSIONS:
                    event.acceptProposedAction()
                    return
                if Path(path).is_dir():
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            p = Path(path)
            if p.is_dir():
                for f in p.rglob("*"):
                    if f.suffix.lower() in MOHO_FILE_EXTENSIONS:
                        self._add_file_to_queue(str(f))
            elif p.suffix.lower() in MOHO_FILE_EXTENSIONS:
                self._add_file_to_queue(str(p))
        event.acceptProposedAction()

    # --- AllComps toggle ---
    def _on_allcomps_toggled(self, checked):
        self.edit_layercomp.setEnabled(not checked)
        if checked:
            self.edit_layercomp.setText("AllComps")
        else:
            self.edit_layercomp.clear()

    # --- Format/preset handling ---
    def _on_format_changed(self, fmt):
        self._update_presets()

    def _update_presets(self):
        fmt = self.combo_format.currentText()
        self.combo_preset.clear()
        all_presets = WINDOWS_PRESETS
        if fmt in all_presets:
            self.combo_preset.addItems(all_presets[fmt])
        else:
            self.combo_preset.addItem("")  # No preset needed for image formats

    # --- Browse dialogs ---
    def _browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.edit_output_dir.setText(folder)

    def _browse_moho(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Moho Executable", "",
            "Executable (*.exe);;All Files (*)"
        )
        if filepath:
            self.edit_moho_path.setText(filepath)
            self.config.moho_path = filepath

    # --- Context menu registration ---
    def _register_context_menu(self):
        try:
            from src.utils.context_menu import register_context_menu
            if register_context_menu():
                QMessageBox.information(self, "Success", "Context menu registered successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to register context menu.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error: {e}")

    def _unregister_context_menu(self):
        try:
            from src.utils.context_menu import unregister_context_menu
            unregister_context_menu()
            QMessageBox.information(self, "Success", "Context menu entries removed.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error: {e}")

    # --- Network / Farm ---
    def _start_master(self):
        from src.network.master import MasterServer
        port = self.spin_port.value()
        self.master_server = MasterServer(port=port)
        self.master_server.on_output = lambda msg: self.log_signal.emit(f"[MASTER] {msg}")
        self.master_server.on_slave_connected = lambda s: self._refresh_slaves()
        self.master_server.on_slave_disconnected = lambda s: self._refresh_slaves()
        self.master_server.on_job_completed = lambda j, s: self.queue_changed_signal.emit()
        self.master_server.on_job_failed = lambda j, s: self.queue_changed_signal.emit()
        self.master_server.start()

        self.btn_start_master.setEnabled(False)
        self.btn_stop_master.setEnabled(True)
        self.btn_start_slave.setEnabled(False)
        ip = self.master_server.get_local_ip()
        self.lbl_farm_status.setText(f"Master running on {ip}:{port}")
        self.lbl_farm_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        self.config.set("network_port", port)

        # Timer to refresh slaves table
        self._slave_timer = QTimer()
        self._slave_timer.timeout.connect(self._refresh_slaves)
        self._slave_timer.start(5000)

    def _stop_master(self):
        if self.master_server:
            self.master_server.stop()
            self.master_server = None
        if hasattr(self, '_slave_timer'):
            self._slave_timer.stop()
        self.btn_start_master.setEnabled(True)
        self.btn_stop_master.setEnabled(False)
        self.btn_start_slave.setEnabled(True)
        self.lbl_farm_status.setText("Status: Stopped")
        self.lbl_farm_status.setStyleSheet("color: #f9e2af; font-weight: bold;")

    def _start_slave(self):
        from src.network.slave import SlaveClient
        host = self.edit_master_host.text()
        port = self.spin_port.value()
        moho = self.edit_moho_path.text()
        self.slave_client = SlaveClient(host, port, moho, slave_port=port + 1)
        self.slave_client.on_output = lambda msg: self.log_signal.emit(f"[SLAVE] {msg}")
        self.slave_client.on_status_changed = lambda s: self.lbl_farm_status.setText(f"Slave: {s}")
        self.slave_client.start()

        self.btn_start_slave.setEnabled(False)
        self.btn_stop_slave.setEnabled(True)
        self.btn_start_master.setEnabled(False)
        self.lbl_farm_status.setText(f"Slave connecting to {host}:{port}...")
        self.lbl_farm_status.setStyleSheet("color: #89b4fa; font-weight: bold;")
        self.config.set("network_master_host", host)
        self.config.set("network_port", port)

    def _stop_slave(self):
        if self.slave_client:
            self.slave_client.stop()
            self.slave_client = None
        self.btn_start_slave.setEnabled(True)
        self.btn_stop_slave.setEnabled(False)
        self.btn_start_master.setEnabled(True)
        self.lbl_farm_status.setText("Status: Stopped")
        self.lbl_farm_status.setStyleSheet("color: #f9e2af; font-weight: bold;")

    def _refresh_slaves(self):
        if not self.master_server:
            return
        slaves = self.master_server.slaves
        self.slaves_table.setRowCount(len(slaves))
        for row, (key, slave) in enumerate(slaves.items()):
            self.slaves_table.setItem(row, 0, QTableWidgetItem(slave.hostname))
            self.slaves_table.setItem(row, 1, QTableWidgetItem(key))
            status_item = QTableWidgetItem(slave.status if slave.is_alive else "offline")
            self.slaves_table.setItem(row, 2, status_item)
            self.slaves_table.setItem(row, 3, QTableWidgetItem(slave.current_job_id))
            self.slaves_table.setItem(row, 4, QTableWidgetItem(str(slave.jobs_completed)))
            self.slaves_table.setItem(row, 5, QTableWidgetItem(str(slave.jobs_failed)))

    # --- Render Presets ---
    def _load_preset_list(self):
        """Populate the preset combo from saved JSON files in PRESETS_DIR."""
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        for f in sorted(PRESETS_DIR.glob("*.json")):
            name = f.stem
            self.combo_render_preset.addItem(name)
        # Select default preset if configured
        default_name = self.config.get("default_preset", "")
        if default_name:
            idx = self.combo_render_preset.findText(default_name)
            if idx >= 0:
                self.combo_render_preset.setCurrentIndex(idx)
                self.chk_default_preset.setChecked(True)

    def _on_preset_selected(self, name):
        """Load preset settings into widgets when a preset is selected."""
        if name == "(none)" or not name:
            return
        preset_file = PRESETS_DIR / f"{name}.json"
        if not preset_file.exists():
            return
        try:
            with open(preset_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        # Output settings
        self.combo_format.setCurrentText(data.get("format", "MP4"))
        self._update_presets()
        opts = data.get("options", "")
        if opts:
            idx = self.combo_preset.findText(opts)
            if idx >= 0:
                self.combo_preset.setCurrentIndex(idx)
        self.edit_output_dir.setText(data.get("output_dir", ""))
        self.chk_subfolder_project.setChecked(data.get("subfolder_project", False))

        # Frame range
        custom_frames = data.get("custom_frames", False)
        self.chk_custom_frames.setChecked(custom_frames)
        if custom_frames:
            self.spin_start_frame.setValue(data.get("start_frame", 1))
            self.spin_end_frame.setValue(data.get("end_frame", 24))

        # Render options
        self.chk_multithread.setChecked(data.get("multithread", True))
        self.chk_halfsize.setChecked(data.get("halfsize", False))
        self.chk_halffps.setChecked(data.get("halffps", False))
        self.chk_shapefx.setChecked(data.get("shapefx", True))
        self.chk_layerfx.setChecked(data.get("layerfx", True))
        self.chk_fewparticles.setChecked(data.get("fewparticles", False))
        self.chk_aa.setChecked(data.get("aa", True))
        self.chk_extrasmooth.setChecked(data.get("extrasmooth", False))
        self.chk_premultiply.setChecked(data.get("premultiply", True))
        self.chk_ntscsafe.setChecked(data.get("ntscsafe", False))
        self.chk_verbose.setChecked(data.get("verbose", True))
        self.chk_copy_images.setChecked(data.get("copy_images", False))

        # Layer comps
        lc_value = data.get("layercomp", "")
        if lc_value.lower() in ("allcomps", "alllayercomps"):
            self.chk_allcomps.setChecked(True)
        else:
            self.chk_allcomps.setChecked(False)
            self.edit_layercomp.setText(lc_value)
        self.chk_addlayercompsuffix.setChecked(data.get("addlayercompsuffix", False))
        self.chk_createfolderforlayercomp.setChecked(data.get("createfolderforlayercomps", False))
        self.chk_addformatsuffix.setChecked(data.get("addformatsuffix", False))
        self.chk_compose_layers.setChecked(data.get("compose_layers", False))

        # QT options
        quality = data.get("quality", 3)
        idx = self.combo_quality.findData(quality)
        if idx >= 0:
            self.combo_quality.setCurrentIndex(idx)
        self.spin_depth.setValue(data.get("depth", 24))

    def _save_preset(self):
        """Save current render settings as a named preset."""
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        data = {
            "format": self.combo_format.currentText(),
            "options": self.combo_preset.currentText(),
            "output_dir": self.edit_output_dir.text(),
            "subfolder_project": self.chk_subfolder_project.isChecked(),
            "custom_frames": self.chk_custom_frames.isChecked(),
            "start_frame": self.spin_start_frame.value(),
            "end_frame": self.spin_end_frame.value(),
            "multithread": self.chk_multithread.isChecked(),
            "halfsize": self.chk_halfsize.isChecked(),
            "halffps": self.chk_halffps.isChecked(),
            "shapefx": self.chk_shapefx.isChecked(),
            "layerfx": self.chk_layerfx.isChecked(),
            "fewparticles": self.chk_fewparticles.isChecked(),
            "aa": self.chk_aa.isChecked(),
            "extrasmooth": self.chk_extrasmooth.isChecked(),
            "premultiply": self.chk_premultiply.isChecked(),
            "ntscsafe": self.chk_ntscsafe.isChecked(),
            "verbose": self.chk_verbose.isChecked(),
            "copy_images": self.chk_copy_images.isChecked(),
            "layercomp": self.edit_layercomp.text(),
            "addlayercompsuffix": self.chk_addlayercompsuffix.isChecked(),
            "createfolderforlayercomps": self.chk_createfolderforlayercomp.isChecked(),
            "addformatsuffix": self.chk_addformatsuffix.isChecked(),
            "compose_layers": self.chk_compose_layers.isChecked(),
            "quality": self.combo_quality.currentData(),
            "depth": self.spin_depth.value(),
        }
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        preset_file = PRESETS_DIR / f"{name}.json"
        try:
            with open(preset_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            QMessageBox.critical(self, "Error", f"Failed to save preset:\n{e}")
            return
        # Add to combo if new
        if self.combo_render_preset.findText(name) < 0:
            self.combo_render_preset.addItem(name)
        self.combo_render_preset.setCurrentText(name)
        self._append_log(f"Preset saved: {name}")

    def _delete_preset(self):
        """Delete the currently selected preset."""
        name = self.combo_render_preset.currentText()
        if name == "(none)" or not name:
            return
        reply = QMessageBox.question(
            self, "Delete Preset",
            f"Delete preset '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        preset_file = PRESETS_DIR / f"{name}.json"
        if preset_file.exists():
            preset_file.unlink()
        idx = self.combo_render_preset.findText(name)
        if idx >= 0:
            self.combo_render_preset.removeItem(idx)
        # Clear default if it was this preset
        if self.config.get("default_preset") == name:
            self.config.set("default_preset", "")
            self.chk_default_preset.setChecked(False)
        self._append_log(f"Preset deleted: {name}")

    def _set_default_preset(self, checked):
        """Set or clear the default preset."""
        if checked:
            name = self.combo_render_preset.currentText()
            if name and name != "(none)":
                self.config.set("default_preset", name)
            else:
                self.chk_default_preset.setChecked(False)
        else:
            self.config.set("default_preset", "")

    # --- Render Timer for real-time table updates ---
    def _start_render_timer(self):
        """Start a 1-second timer to update Progress and Time columns."""
        if not hasattr(self, '_render_timer'):
            self._render_timer = QTimer()
            self._render_timer.timeout.connect(self._on_render_timer_tick)
        self._render_timer.start(1000)

    def _stop_render_timer(self):
        """Stop the render timer and close log file."""
        if hasattr(self, '_render_timer'):
            self._render_timer.stop()
        self._close_log_file()

    def _on_render_timer_tick(self):
        """Update Progress and Time columns for the currently rendering job."""
        current = self.queue.current_job
        if current is None:
            return
        for row in range(self.queue_table.rowCount()):
            id_item = self.queue_table.item(row, 8)
            if id_item and id_item.text() == current.id:
                self.queue_table.setItem(row, 5, QTableWidgetItem(f"{current.progress:.0f}%"))
                self.queue_table.setItem(row, 6, QTableWidgetItem(current.elapsed_str))
                break

    def closeEvent(self, event):
        if self.queue.is_running:
            reply = QMessageBox.question(
                self, "Confirm Exit",
                "A render is in progress. Stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self.queue.stop()

        if self.master_server:
            self.master_server.stop()
        if self.slave_client:
            self.slave_client.stop()

        self._close_log_file()

        # Save moho path if changed
        self.config.moho_path = self.edit_moho_path.text()
        event.accept()
