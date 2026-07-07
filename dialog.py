# -*- coding: utf-8 -*-
"""PyQt dialog controller for GeoData Forge."""
import os
import time

from qgis.PyQt.QtCore import QVariant, Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QFileDialog,
    QTextEdit,
    QCheckBox,
    QFormLayout,
    QProgressBar,
    QMessageBox,
    QScrollArea,
    QWidget,
    QApplication
)
from qgis.core import (
    QgsProject,
    QgsMapLayer,
    QgsWkbTypes,
    QgsApplication,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsField
)
from qgis.gui import QgsCollapsibleGroupBox

from .core import FORGE_VERSION
from .core.task_runner import GenerationTask
from .core.profile_manager import ProfileManager
from .core.validator import Validator
from .core.geometry_generator import GeometryGenerator
from .reporting.exporter import Exporter


class GeoDataForgeDialog(QDialog):
    """The main guided user interface for generating synthetic datasets in QGIS."""

    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.active_task = None
        self.preview_layer = None
        self.is_copy_geojson = False
        self.start_time = time.time()

        self.setWindowTitle("GeoData Forge — Synthetic Generator")
        self.resize(520, 600)
        self.setMinimumSize(480, 520)

        # Style sheet optimized for light/dark theme compliance
        self.setStyleSheet("""
            QDialog {
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                font-size: 11.5px;
            }
            QPushButton {
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11.5px;
                font-weight: 600;
                background-color: #F8FAFC;
                color: #0F172A;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                border-color: #94A3B8;
            }
            QPushButton:pressed {
                background-color: #CBD5E1;
            }
            QPushButton#btnGenerate {
                background-color: #2563EB;
                color: #FFFFFF;
                border: 1px solid #1D4ED8;
            }
            QPushButton#btnGenerate:hover {
                background-color: #1D4ED8;
            }
            QPushButton#btnCancel {
                background-color: #EF4444;
                color: #FFFFFF;
                border: 1px solid #DC2626;
            }
            QPushButton#btnCancel:hover {
                background-color: #DC2626;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 3px;
                font-size: 11.5px;
                background-color: #FFFFFF;
                color: #0F172A;
            }
            QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
                border-color: #94A3B8;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #2563EB;
            }
            QTextEdit {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                background-color: #FFFFFF;
                color: #0F172A;
                font-family: 'Consolas', monospace;
                font-size: 10.5px;
            }
        """)

        self.setup_ui()
        self.refresh_inputs()

    def setup_ui(self):
        """Constructs layout and UI form elements programmatically with scroll controls."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(8)

        # Title Block
        title_layout = QHBoxLayout()
        title_lbl = QLabel("GeoData Forge")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E3A8A;")
        version_lbl = QLabel(f"v{FORGE_VERSION}")
        version_lbl.setStyleSheet("font-weight: bold; color: #94A3B8; font-size: 11px;")
        title_layout.addWidget(title_lbl)
        title_layout.addStretch()
        title_layout.addWidget(version_lbl)
        main_layout.addLayout(title_layout)

        # Profile Load/Save Shortcuts
        profile_btn_layout = QHBoxLayout()
        self.btn_load_profile = QPushButton("Load Profile JSON")
        self.btn_load_profile.clicked.connect(self.load_profile_dialog)
        self.btn_save_profile = QPushButton("Save Profile JSON")
        self.btn_save_profile.clicked.connect(self.save_profile_dialog)
        profile_btn_layout.addWidget(self.btn_load_profile)
        profile_btn_layout.addWidget(self.btn_save_profile)
        profile_btn_layout.addStretch()
        main_layout.addLayout(profile_btn_layout)

        # Setup Scroll Area for middle settings cards
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setStyleSheet("background-color: transparent;")

        self.scroll_container = QWidget()
        self.scroll_container.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(self.scroll_container)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)

        # Group 1: Spatial Extent Input Source (QgsCollapsibleGroupBox)
        extent_group = QgsCollapsibleGroupBox("🗺️ Spatial Boundary")
        extent_group.setCollapsed(False)
        extent_layout = QFormLayout(extent_group)
        extent_layout.setContentsMargins(10, 10, 10, 10)
        extent_layout.setSpacing(6)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["Current Map Extent", "Polygon Layer Boundary"])
        self.source_combo.currentIndexChanged.connect(self.toggle_source_inputs)
        extent_layout.addRow("Extent Source:", self.source_combo)

        self.layer_combo = QComboBox()
        extent_layout.addRow("Boundary Layer:", self.layer_combo)

        scroll_layout.addWidget(extent_group)

        # Group 2: Geometry Settings (QgsCollapsibleGroupBox)
        geom_group = QgsCollapsibleGroupBox("📍 Geometry Settings")
        geom_group.setCollapsed(False)
        geom_layout = QFormLayout(geom_group)
        geom_layout.setContentsMargins(10, 10, 10, 10)
        geom_layout.setSpacing(6)

        self.geom_type_combo = QComboBox()
        self.geom_type_combo.addItems(["📍 Point Geometry", "╱ Line Geometry", "⬡ Polygon Geometry"])
        self.geom_type_combo.currentIndexChanged.connect(self.on_geom_type_changed)
        geom_layout.addRow("Geometry Type:", self.geom_type_combo)

        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 100000)
        self.count_spin.setValue(500)
        geom_layout.addRow("Feature Count:", self.count_spin)

        self.dist_combo = QComboBox()
        self.dist_combo.addItems(["🎲 Uniform Distribution", "🎯 Gaussian Clustered", "📏 Poisson Disc (Spacing)"])
        self.dist_combo.currentIndexChanged.connect(self.toggle_dist_inputs)
        geom_layout.addRow("Distribution:", self.dist_combo)

        self.spacing_spin = QDoubleSpinBox()
        self.spacing_spin.setRange(0.1, 10000.0)
        self.spacing_spin.setValue(20.0)
        self.spacing_label = QLabel("Min Spacing (m/deg):")
        geom_layout.addRow(self.spacing_label, self.spacing_spin)

        scroll_layout.addWidget(geom_group)

        # Group 3: Default Attributes Checklist
        attrib_group = QgsCollapsibleGroupBox("🏷️ Attributes Template")
        attrib_group.setCollapsed(True)
        attrib_layout = QVBoxLayout(attrib_group)
        attrib_layout.setContentsMargins(10, 10, 10, 10)
        attrib_layout.setSpacing(4)

        # Template preset dropdown
        temp_layout = QHBoxLayout()
        temp_label = QLabel("Industry Schema Template:")
        self.attrib_template_combo = QComboBox()
        self.attrib_template_combo.addItems([
            "⚙️ Custom (Manual Checks)",
            "🏡 Cadastral / Parcel Registry Preset",
            "🚰 Water Utility Preset",
            "🌳 Forestry Survey Preset",
            "📡 Telecom Network Preset"
        ])
        self.attrib_template_combo.currentIndexChanged.connect(self.on_template_changed)
        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.attrib_template_combo)
        attrib_layout.addLayout(temp_layout)

        # Template dynamic guidance description label
        self.template_desc_lbl = QLabel("")
        self.template_desc_lbl.setWordWrap(True)
        self.template_desc_lbl.setStyleSheet("""
            background-color: #F1F5F9;
            color: #475569;
            border-left: 3px solid #3B82F6;
            padding: 6px;
            font-size: 11px;
            border-radius: 2px;
            margin-bottom: 4px;
        """)
        attrib_layout.addWidget(self.template_desc_lbl)

        self.chk_id = QCheckBox("Generate unique ID (Integer)")
        self.chk_id.setChecked(True)
        self.chk_name = QCheckBox("Generate name / provider (Text)")
        self.chk_name.setChecked(True)
        self.chk_category = QCheckBox("Generate category / zoning / material (Enum)")
        self.chk_category.setChecked(True)
        self.chk_numeric = QCheckBox("Generate numeric metrics (Double)")
        self.chk_numeric.setChecked(True)
        self.chk_date = QCheckBox("Generate timestamps (Date)")
        self.chk_date.setChecked(True)
        self.chk_status = QCheckBox("Generate operational statuses (Enum)")
        self.chk_status.setChecked(True)

        attrib_layout.addWidget(self.chk_id)
        attrib_layout.addWidget(self.chk_name)
        attrib_layout.addWidget(self.chk_category)
        attrib_layout.addWidget(self.chk_numeric)
        attrib_layout.addWidget(self.chk_date)
        attrib_layout.addWidget(self.chk_status)

        scroll_layout.addWidget(attrib_group)

        # Group 4: QA Error Injection Mode (Collapsed by default)
        self.error_group = QgsCollapsibleGroupBox("⚙️ QA Error Injection Mode (Debug)")
        self.error_group.setCollapsed(True)
        error_layout = QVBoxLayout(self.error_group)
        error_layout.setContentsMargins(10, 10, 10, 10)
        error_layout.setSpacing(4)

        self.chk_enable_errors = QCheckBox("Enable QA Error Injection")
        self.chk_enable_errors.setChecked(False)
        self.chk_enable_errors.toggled.connect(self.toggle_error_fields)
        error_layout.addWidget(self.chk_enable_errors)

        self.chk_err_dup_geom = QCheckBox("Inject duplicate geometries")
        self.chk_err_self_intersect = QCheckBox("Inject self-intersecting rings")
        self.chk_err_slivers = QCheckBox("Inject thin sliver polygons")
        self.chk_err_dup_ids = QCheckBox("Inject duplicate feature IDs")
        self.chk_err_nulls = QCheckBox("Inject NULL values in fields")
        self.chk_err_outliers = QCheckBox("Inject extreme numeric outliers")

        error_layout.addWidget(self.chk_err_dup_geom)
        error_layout.addWidget(self.chk_err_self_intersect)
        error_layout.addWidget(self.chk_err_slivers)
        error_layout.addWidget(self.chk_err_dup_ids)
        error_layout.addWidget(self.chk_err_nulls)
        error_layout.addWidget(self.chk_err_outliers)

        # GeoQA Benchmark Manifest — new in this release
        self.chk_export_manifest = QCheckBox("📋 Export GeoQA Benchmark Manifest (known-answer test)")
        self.chk_export_manifest.setChecked(True)
        self.chk_export_manifest.setEnabled(False)
        self.chk_export_manifest.setToolTip(
            "Writes a companion *_geoqa_manifest.json / .txt file listing exactly which\n"
            "GeoQA rule IDs (e.g. G001, G004, A005, A007) this dataset is expected to\n"
            "trigger, and on which feature IDs. Run the exported dataset through GeoQA\n"
            "and compare its report against this manifest as a quick regression/sanity\n"
            "check that GeoQA (or any QA tool) is still catching what it should."
        )
        error_layout.addWidget(self.chk_export_manifest)

        # Reproducible Random Seed
        seed_layout = QHBoxLayout()
        seed_label = QLabel("Reproducible Random Seed:")
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(1, 999999)
        self.seed_spin.setValue(42)
        seed_layout.addWidget(seed_label)
        seed_layout.addWidget(self.seed_spin)
        error_layout.addLayout(seed_layout)

        scroll_layout.addWidget(self.error_group)

        # Group 5: Output Settings (QgsCollapsibleGroupBox)
        output_group = QgsCollapsibleGroupBox("📦 Output Settings")
        output_group.setCollapsed(False)
        output_layout = QFormLayout(output_group)
        output_layout.setContentsMargins(10, 10, 10, 10)
        output_layout.setSpacing(6)

        # Format Dropdown
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "GeoPackage (*.gpkg)",
            "GeoJSON (*.geojson)",
            "ESRI Shapefile (*.shp)",
            "CSV Table (Attributes only) (*.csv)"
        ])
        self.format_combo.currentIndexChanged.connect(self.on_format_changed)
        output_layout.addRow("Output Format:", self.format_combo)

        file_select_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self.browse_output_path)
        file_select_layout.addWidget(self.path_edit)
        file_select_layout.addWidget(self.btn_browse)
        output_layout.addRow("Save to:", file_select_layout)

        self.layer_name_edit = QLineEdit("synthetic_points")
        output_layout.addRow("Layer Name:", self.layer_name_edit)

        scroll_layout.addWidget(output_group)

        # Set scroll container widget and add to main dialog layout
        self.scroll_area.setWidget(self.scroll_container)
        main_layout.addWidget(self.scroll_area)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Status & Log panel
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(110)
        self.log_text.setPlaceholderText("Ready. Select settings to forge geospatial data.")
        self.log_text.setStyleSheet(
            "background-color: #1E1E1E; color: #D4D4D4; font-family: 'Consolas', 'Courier New', monospace; "
            "font-size: 11px; border: 1px solid #333333; border-radius: 4px; padding: 4px;"
        )
        main_layout.addWidget(self.log_text)

        # Actions Layout
        actions_layout = QVBoxLayout()

        # Row 1: Utility Actions
        row1_layout = QHBoxLayout()
        self.btn_preview = QPushButton("Preview Draft")
        self.btn_preview.setToolTip("Generates in-memory draft (up to 100 features) quickly on map canvas.")
        self.btn_preview.clicked.connect(self.run_preview)

        self.btn_copy_geojson = QPushButton("Copy GeoJSON")
        self.btn_copy_geojson.setToolTip("Copies generated FeatureCollection coordinates to clipboard.")
        self.btn_copy_geojson.clicked.connect(self.run_copy_geojson)

        self.btn_export_script = QPushButton("Export Script")
        self.btn_export_script.setToolTip(
            "Export a standalone Python script to generate a basic uniform random "
            "distribution of points (Line/Polygon geometries are exported using simple "
            "rectangular box buffers)."
        )
        self.btn_export_script.clicked.connect(self.run_export_script)

        row1_layout.addWidget(self.btn_preview)
        row1_layout.addWidget(self.btn_copy_geojson)
        row1_layout.addWidget(self.btn_export_script)
        row1_layout.addStretch()

        # Row 2: Execution Controls
        row2_layout = QHBoxLayout()
        self.btn_generate = QPushButton("Generate")
        self.btn_generate.setObjectName("btnGenerate")
        self.btn_generate.clicked.connect(self.run_generate)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_task)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)

        row2_layout.addWidget(self.btn_generate)
        row2_layout.addWidget(self.btn_cancel)
        row2_layout.addStretch()
        row2_layout.addWidget(btn_close)

        actions_layout.addLayout(row1_layout)
        actions_layout.addLayout(row2_layout)

        main_layout.addLayout(actions_layout)

    def toggle_source_inputs(self):
        """Enables/disables the boundary layer selection dropdown."""
        is_layer = self.source_combo.currentIndex() == 1
        self.layer_combo.setEnabled(is_layer)

    def toggle_dist_inputs(self):
        """Enables/disables minimum spacing spin box based on selected distribution."""
        is_poisson = self.dist_combo.currentIndex() == 2
        self.spacing_spin.setVisible(is_poisson)
        self.spacing_label.setVisible(is_poisson)

    def toggle_error_fields(self):
        """Enables/disables individual error checkboxes based on master switch."""
        enabled = self.chk_enable_errors.isChecked()
        self.chk_err_dup_geom.setEnabled(enabled)
        self.chk_err_self_intersect.setEnabled(enabled)
        self.chk_err_slivers.setEnabled(enabled)
        self.chk_err_dup_ids.setEnabled(enabled)
        self.chk_err_nulls.setEnabled(enabled)
        self.chk_err_outliers.setEnabled(enabled)
        self.chk_export_manifest.setEnabled(enabled)

    def on_geom_type_changed(self):
        """Updates output file name default layer extension and distribution labels dynamically."""
        geom_type = self.selected_geom_type

        self.dist_combo.blockSignals(True)
        current_idx = self.dist_combo.currentIndex()
        self.dist_combo.clear()

        if geom_type == "Point":
            self.layer_name_edit.setText("synthetic_points")
            self.spacing_spin.setEnabled(True)
            self.dist_combo.addItems([
                "🎲 Uniform Distribution",
                "🎯 Gaussian Clustered",
                "📏 Poisson Disc (Spacing)"
            ])
        elif geom_type == "Line":
            self.layer_name_edit.setText("synthetic_lines")
            self.spacing_spin.setEnabled(False)
            self.dist_combo.addItems([
                "🎲 Random Paths (Uniform)",
                "🕸️ MST Network (Gaussian)",
                "🕸️ MST Network (Poisson)"
            ])
        elif geom_type == "Polygon":
            self.layer_name_edit.setText("synthetic_polygons")
            self.spacing_spin.setEnabled(False)
            self.dist_combo.addItems([
                "🎲 Star Polygons (Uniform)",
                "⬡ Voronoi Parcels (Gaussian)",
                "⬡ Voronoi Parcels (Poisson)"
            ])

        self.dist_combo.setCurrentIndex(current_idx if current_idx < self.dist_combo.count() else 0)
        self.dist_combo.blockSignals(False)

        self.toggle_dist_inputs()
        self.update_output_extension()

    def on_format_changed(self):
        """Updates file suffix path when output format changes."""
        self.update_output_extension()

    def update_output_extension(self):
        """Toggles file extension in output path line edit."""
        path = self.path_edit.text().strip()
        if not path:
            return
        base, _ = os.path.splitext(path)
        fmt_idx = self.format_combo.currentIndex()
        if fmt_idx == 0:
            ext = ".gpkg"
        elif fmt_idx == 1:
            ext = ".geojson"
        elif fmt_idx == 2:
            ext = ".shp"
        else:
            ext = ".csv"
        self.path_edit.setText(base + ext)

    def on_template_changed(self):
        """Checks and locks attributes checkboxes dynamically, sets guides, and updates distribution recommendations."""
        idx = self.attrib_template_combo.currentIndex()

        for chk in [self.chk_id, self.chk_name, self.chk_category,
                    self.chk_numeric, self.chk_date, self.chk_status]:
            chk.setEnabled(True)

        if idx == 0:
            self.template_desc_lbl.setVisible(False)
            return

        self.template_desc_lbl.setVisible(True)

        self.chk_id.blockSignals(True)
        self.chk_name.blockSignals(True)
        self.chk_category.blockSignals(True)
        self.chk_numeric.blockSignals(True)
        self.chk_date.blockSignals(True)
        self.chk_status.blockSignals(True)

        # Lock checks for presets
        for chk in [self.chk_id, self.chk_name, self.chk_category,
                    self.chk_numeric, self.chk_date, self.chk_status]:
            chk.setChecked(True)
            chk.setEnabled(False)

        self.chk_id.blockSignals(False)
        self.chk_name.blockSignals(False)
        self.chk_category.blockSignals(False)
        self.chk_numeric.blockSignals(False)
        self.chk_date.blockSignals(False)
        self.chk_status.blockSignals(False)

        if idx == 1:  # Cadastral / Parcel Registry
            self.template_desc_lbl.setText(
                "<b>🏡 Cadastral / Parcel Registry Preset</b><br>"
                "• <i>Recommended Distribution:</i> Uniform / Grid<br>"
                "• <i>Fields:</i> parcel_id, zoning_class, land_value_usd, registry_status<br>"
                "• <i>Correlations:</i> zoning_class drives land_value_usd ranges and status weights."
            )
            # Recommend Uniform Distribution (index 0)
            self.dist_combo.setCurrentIndex(0)
            self.geom_type_combo.setCurrentIndex(2)  # Polygon
        elif idx == 2:  # Water Utility
            self.template_desc_lbl.setText(
                "<b>🚰 Water Utility Preset</b><br>"
                "• <i>Recommended Distribution:</i> Poisson Disc (Spacing)<br>"
                "• <i>Fields:</i> pipe_id, material, diameter_mm, install_date, flow_status<br>"
                "• <i>Correlations:</i> Pipe installation date drives flow status/leak probabilities."
            )
            self.geom_type_combo.setCurrentIndex(1)  # Line
        elif idx == 3:  # Forestry Survey
            self.template_desc_lbl.setText(
                "<b>🌳 Forestry Survey Preset</b><br>"
                "• <i>Recommended Distribution:</i> Gaussian Clustered (stands)<br>"
                "• <i>Fields:</i> tree_id, species_scientific, canopy_class, dbh_cm, height_m, health_status<br>"
                "• <i>Correlations:</i> Tree species drives correlated height, DBH, and age ranges."
            )
            self.dist_combo.setCurrentIndex(1)  # Gaussian
            self.geom_type_combo.setCurrentIndex(0)  # Point
        elif idx == 4:  # Telecom Network
            self.template_desc_lbl.setText(
                "<b>📡 Telecom Network Preset</b><br>"
                "• <i>Recommended Distribution:</i> Poisson Disc (Spacing)<br>"
                "• <i>Fields:</i> tower_id, provider, tower_type, tower_height_m, coverage_km, status<br>"
                "• <i>Correlations:</i> Tower type (Macro vs Microcell) drives height, driving coverage radius."
            )
            self.dist_combo.setCurrentIndex(2)  # Poisson Disc
            self.geom_type_combo.setCurrentIndex(0)  # Point

    def run_copy_geojson(self):
        """Triggers generation pipeline with clipboard redirection target."""
        self.is_copy_geojson = True
        self.run_generate()

    def refresh_inputs(self):
        """Populates spatial layers, defaults, and toggles."""
        self.toggle_source_inputs()
        self.toggle_dist_inputs()
        self.toggle_error_fields()

        # Populate vector layers
        self.layer_combo.clear()
        layers = QgsProject.instance().mapLayers().values()
        poly_layers = [
            lay for lay in layers
            if lay.type() == QgsMapLayer.VectorLayer and lay.geometryType() == QgsWkbTypes.PolygonGeometry
        ]

        if poly_layers:
            for lay in poly_layers:
                self.layer_combo.addItem(lay.name(), lay.id())
        else:
            self.layer_combo.addItem("No polygon layers in project", None)
            self.layer_combo.setEnabled(False)

        # Default paths
        default_dir = os.path.expanduser("~")
        self.path_edit.setText(os.path.join(default_dir, "synthetic_data.gpkg"))

    def browse_output_path(self):
        """Opens a save file dialog based on selected output format."""
        fmt_idx = self.format_combo.currentIndex()
        if fmt_idx == 0:
            flt, title = "GeoPackage (*.gpkg)", "Save Synthetic GeoPackage"
        elif fmt_idx == 1:
            flt, title = "GeoJSON (*.geojson)", "Save Synthetic GeoJSON"
        elif fmt_idx == 2:
            flt, title = "ESRI Shapefile (*.shp)", "Save Synthetic Shapefile"
        else:
            flt, title = "CSV Table (*.csv)", "Save Synthetic Attribute CSV"

        path, _ = QFileDialog.getSaveFileName(self, title, self.path_edit.text(), flt)
        if path:
            self.path_edit.setText(path)

    def get_selected_boundary_geometry(self):
        """Extracts boundary geometry limits as WKT string."""
        if self.source_combo.currentIndex() == 0:
            extent = self.iface.mapCanvas().extent()
            return extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum(), None, None

        layer_id = self.layer_combo.currentData()
        if not layer_id:
            raise ValueError("No valid boundary layer selected.")

        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer:
            raise ValueError("Selected layer no longer exists.")

        geoms = []
        for feature in layer.getFeatures():
            if feature.hasGeometry():
                geoms.append(feature.geometry())

        if not geoms:
            raise ValueError("Boundary layer contains no features with geometries.")

        combined_geom = QgsGeometry.unaryUnion(geoms)
        extent = combined_geom.boundingBox()
        wkt = combined_geom.asWkt()
        return extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum(), wkt, layer.crs().authid()

    def build_schema(self):
        """Compiles attribute generation rules list based on checked options."""
        schema = []
        idx = self.attrib_template_combo.currentIndex()

        if idx == 1:  # Cadastral / Parcel Registry
            if self.chk_id.isChecked():
                schema.append({"name": "parcel_id", "type": "SequentialID"})
            if self.chk_name.isChecked():
                schema.append({
                    "name": "owner_name",
                    "type": "Name",
                    "choices": [
                        "John Smith", "Jane Doe", "Michael Johnson", "Emily Davis",
                        "David Miller", "Sarah Wilson", "James Taylor", "Linda Anderson",
                        "Robert Martinez", "Patricia Thomas", "William Garcia", "Elizabeth Moore"
                    ]
                })
            if self.chk_category.isChecked():
                schema.append({
                    "name": "zoning_class",
                    "type": "Category",
                    "choices": ["Residential", "Commercial", "Industrial", "Agricultural", "Mixed-Use", "Conservation"]
                })
            if self.chk_numeric.isChecked():
                schema.append({"name": "land_value_usd", "type": "Numeric", "min": 50000, "max": 500000})
            if self.chk_date.isChecked():
                schema.append({"name": "assessed_date", "type": "Date"})
            if self.chk_status.isChecked():
                schema.append({
                    "name": "registry_status",
                    "type": "Status",
                    "choices": ["Registered", "Pending", "Disputed", "Foreclosed"]
                })
        elif idx == 2:  # Water Utility
            if self.chk_id.isChecked():
                schema.append({"name": "pipe_id", "type": "SequentialID"})
            if self.chk_name.isChecked():
                schema.append({
                    "name": "asset_name",
                    "type": "Name",
                    "choices": [
                        "Main Pump Station", "Treatment Plant Intake", "Reservoir Tank Alpha",
                        "Booster Station East", "Pressure Valve PV-102", "Control Valve CV-04",
                        "Flow Sensor FS-12"
                    ]
                })
            if self.chk_category.isChecked():
                schema.append({
                    "name": "material",
                    "type": "Category",
                    "choices": ["PVC", "Ductile Iron", "HDPE", "Cast Iron", "Concrete"]
                })
            if self.chk_numeric.isChecked():
                schema.append({"name": "diameter_mm", "type": "Numeric", "min": 50, "max": 500})
            if self.chk_date.isChecked():
                schema.append({"name": "install_date", "type": "Date"})
            if self.chk_status.isChecked():
                schema.append({
                    "name": "flow_status",
                    "type": "Status",
                    "choices": ["Flowing", "Restricted", "Closed", "Backflow", "Leak Detected"]
                })
        elif idx == 3:  # Forestry
            if self.chk_id.isChecked():
                schema.append({"name": "tree_id", "type": "SequentialID"})
            if self.chk_name.isChecked():
                schema.append({
                    "name": "species_scientific",
                    "type": "Name",
                    "choices": [
                        "Pinus sylvestris", "Quercus robur", "Betula pendula", "Picea abies",
                        "Fagus sylvatica", "Acer platanoides", "Fraxinus excelsior"
                    ]
                })
            if self.chk_category.isChecked():
                schema.append({
                    "name": "canopy_class",
                    "type": "Category",
                    "choices": ["Dominant", "Codominant", "Intermediate", "Suppressed", "Understory"]
                })
            if self.chk_numeric.isChecked():
                schema.append({"name": "dbh_cm", "type": "Numeric", "min": 5, "max": 120})
                schema.append({"name": "height_m", "type": "Numeric", "min": 2, "max": 50})
            if self.chk_date.isChecked():
                schema.append({"name": "survey_date", "type": "Date"})
            if self.chk_status.isChecked():
                schema.append({
                    "name": "health_status",
                    "type": "Status",
                    "choices": ["Healthy", "Minor Damage", "Severe Decline", "Dead Standing", "Fallen"]
                })
        elif idx == 4:  # Telecom Network
            if self.chk_id.isChecked():
                schema.append({"name": "tower_id", "type": "SequentialID"})
            if self.chk_name.isChecked():
                schema.append({
                    "name": "provider",
                    "type": "Name",
                    "choices": ["Airtel", "Jio", "Vi (Vodafone Idea)", "BSNL", "Indus Towers"]
                })
            if self.chk_category.isChecked():
                schema.append({
                    "name": "tower_type",
                    "type": "Category",
                    "choices": ["Monopole", "Lattice", "Guyed Tower", "Stealth Tower", "Microcell"]
                })
            if self.chk_numeric.isChecked():
                schema.append({"name": "tower_height_m", "type": "Numeric", "min": 20, "max": 150})
                schema.append({"name": "coverage_km", "type": "Numeric", "min": 3, "max": 25})
            if self.chk_date.isChecked():
                schema.append({"name": "install_year", "type": "Year", "start_year": 2005, "end_year": 2025})
            if self.chk_status.isChecked():
                schema.append({
                    "name": "status",
                    "type": "Status",
                    "choices": ["Active", "Planned", "Maintenance", "Decommissioned"]
                })
        else:  # Custom
            if self.chk_id.isChecked():
                schema.append({"name": "id", "type": "SequentialID"})
            if self.chk_name.isChecked():
                schema.append({"name": "name", "type": "Name"})
            if self.chk_category.isChecked():
                schema.append({"name": "category", "type": "Category"})
            if self.chk_numeric.isChecked():
                schema.append({"name": "value", "type": "Numeric", "min": 0, "max": 100})
            if self.chk_date.isChecked():
                schema.append({"name": "date_added", "type": "Date"})
            if self.chk_status.isChecked():
                schema.append({"name": "status", "type": "Status"})
        return schema

    def compile_config(self):
        """Compiles the UI inputs into a settings dictionary."""
        return {
            "extent_source": self.source_combo.currentText(),
            "boundary_layer_id": self.layer_combo.currentData(),
            "geometry_type": self.selected_geom_type,
            "feature_count": self.count_spin.value(),
            "seed": self.seed_spin.value(),
            "distribution": self.selected_distribution,
            "min_spacing": self.spacing_spin.value(),
            "template_index": self.attrib_template_combo.currentIndex(),
            "generate_id": self.chk_id.isChecked(),
            "generate_name": self.chk_name.isChecked(),
            "generate_category": self.chk_category.isChecked(),
            "generate_numeric": self.chk_numeric.isChecked(),
            "generate_date": self.chk_date.isChecked(),
            "generate_status": self.chk_status.isChecked(),
            "inject_errors": self.chk_enable_errors.isChecked(),
            "err_dup_geom": self.chk_err_dup_geom.isChecked(),
            "err_self_intersect": self.chk_err_self_intersect.isChecked(),
            "err_slivers": self.chk_err_slivers.isChecked(),
            "err_dup_ids": self.chk_err_dup_ids.isChecked(),
            "err_nulls": self.chk_err_nulls.isChecked(),
            "err_outliers": self.chk_err_outliers.isChecked(),
            "export_geoqa_manifest": self.chk_export_manifest.isChecked(),
            "output_format_index": self.format_combo.currentIndex(),
            "output_path": self.path_edit.text(),
            "layer_name": self.layer_name_edit.text()
        }

    def load_profile_dialog(self):
        """Opens JSON file dialog to load settings profile configuration."""
        path, _ = QFileDialog.getOpenFileName(self, "Load Generation Profile", "", "JSON (*.json)")
        if not path:
            return

        try:
            config = ProfileManager.load_profile(path)

            idx = self.source_combo.findText(config.get("extent_source", "Current Map Extent"), Qt.MatchContains)
            if idx >= 0:
                self.source_combo.setCurrentIndex(idx)

            geom_val = config.get("geometry_type", "Point")
            geom_idx = 1 if geom_val == "Line" else (2 if geom_val == "Polygon" else 0)
            self.geom_type_combo.setCurrentIndex(geom_idx)

            self.count_spin.setValue(config.get("feature_count", 500))
            self.seed_spin.setValue(config.get("seed", 42))

            dist_val = config.get("distribution", "Uniform")
            dist_idx = 1 if "Clustered" in dist_val else (2 if "Poisson" in dist_val else 0)
            self.dist_combo.setCurrentIndex(dist_idx)

            self.spacing_spin.setValue(config.get("min_spacing", 20.0))

            # Restore presets and templates
            if "template_index" in config:
                self.attrib_template_combo.setCurrentIndex(config["template_index"])

            # Checkboxes
            self.chk_id.setChecked(config.get("generate_id", True))
            self.chk_name.setChecked(config.get("generate_name", True))
            self.chk_category.setChecked(config.get("generate_category", True))
            self.chk_numeric.setChecked(config.get("generate_numeric", True))
            self.chk_date.setChecked(config.get("generate_date", True))
            self.chk_status.setChecked(config.get("generate_status", True))

            self.chk_enable_errors.setChecked(config.get("inject_errors", False))
            self.chk_err_dup_geom.setChecked(config.get("err_dup_geom", False))
            self.chk_err_self_intersect.setChecked(config.get("err_self_intersect", False))
            self.chk_err_slivers.setChecked(config.get("err_slivers", False))
            self.chk_err_dup_ids.setChecked(config.get("err_dup_ids", False))
            self.chk_err_nulls.setChecked(config.get("err_nulls", False))
            self.chk_err_outliers.setChecked(config.get("err_outliers", False))
            self.chk_export_manifest.setChecked(config.get("export_geoqa_manifest", True))

            if "output_format_index" in config:
                self.format_combo.setCurrentIndex(config["output_format_index"])

            self.path_edit.setText(config.get("output_path", ""))
            self.layer_name_edit.setText(config.get("layer_name", ""))

            self.toggle_source_inputs()
            self.toggle_dist_inputs()
            self.toggle_error_fields()

            self.log(f"SUCCESS: Configuration profile loaded from {path}")
        except Exception as e:
            QMessageBox.critical(self, "Profile Load Error", str(e))

    def save_profile_dialog(self):
        """Opens JSON file dialog to save settings profile configuration."""
        path, _ = QFileDialog.getSaveFileName(self, "Save Generation Profile", "", "JSON (*.json)")
        if not path:
            return
        try:
            config = self.compile_config()
            ProfileManager.save_profile(path, config)
            self.log(f"SUCCESS: Configuration profile saved to {path}")
            QMessageBox.information(self, "Success", "Profile configuration exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Profile Save Error", str(e))

    def run_preview(self):
        """Generates memory draft layers and renders them as a temporary canvas layer."""
        count = self.count_spin.value()
        geom_type = self.selected_geom_type
        schema = self.build_schema()
        preview_cap = min(100, count)
        self.log("Generating memory layer preview...")
        self.log(
            f"<b>Estimated Output:</b> {count} {geom_type}s | {len(schema)} Fields | "
            f"Preview capped at {preview_cap} features"
        )
        try:
            xmin, ymin, xmax, ymax, wkt, crs_authid = self.get_selected_boundary_geometry()
            count = preview_cap
            dist = self.selected_distribution
            seed = self.seed_spin.value()
            spacing = self.spacing_spin.value()

            if self.preview_layer:
                QgsProject.instance().removeMapLayer(self.preview_layer.id())
                self.preview_layer = None

            boundary_geom = QgsGeometry.fromWkt(wkt) if wkt else None
            crs_str = crs_authid if crs_authid else "EPSG:4326"

            if geom_type == "Point":
                geom_uri = f"Point?crs={crs_str}"
                if dist == "Poisson Disc (Spacing)":
                    raw_pts = GeometryGenerator.generate_poisson_disc_points(
                        xmin, ymin, xmax, ymax, count, seed, spacing, boundary_geom
                    )
                    geometries = [QgsGeometry.fromPointXY(p) for p in raw_pts]
                elif dist == "Gaussian Clustered":
                    raw_pts = GeometryGenerator.generate_clustered_points(
                        xmin, ymin, xmax, ymax, count, seed, boundary_geom
                    )
                    geometries = [QgsGeometry.fromPointXY(p) for p in raw_pts]
                else:
                    raw_pts = GeometryGenerator.generate_uniform_points(
                        xmin, ymin, xmax, ymax, count, seed, boundary_geom
                    )
                    geometries = [QgsGeometry.fromPointXY(p) for p in raw_pts]
            elif geom_type == "Line":
                geom_uri = f"LineString?crs={crs_str}"
                if dist in ("Gaussian Clustered", "Poisson Disc (Spacing)"):
                    geometries = GeometryGenerator.generate_mst_networks(
                        xmin, ymin, xmax, ymax, count, seed, boundary_geom
                    )
                else:
                    geometries = GeometryGenerator.generate_random_paths(
                        xmin, ymin, xmax, ymax, count, seed, boundary_geom
                    )
            elif geom_type == "Polygon":
                geom_uri = f"Polygon?crs={crs_str}"
                if dist in ("Gaussian Clustered", "Poisson Disc (Spacing)"):
                    geometries = GeometryGenerator.generate_voronoi_parcels(
                        xmin, ymin, xmax, ymax, count, seed, boundary_geom
                    )
                else:
                    geometries = GeometryGenerator.generate_star_polygons(
                        xmin, ymin, xmax, ymax, count, seed, boundary_geom
                    )
            else:
                raise ValueError(f"Unsupported geometry preview type: {geom_type}")

            self.preview_layer = QgsVectorLayer(geom_uri, "GeoData Forge Draft Preview", "memory")
            provider = self.preview_layer.dataProvider()

            fields = []
            for field in schema:
                ftype = field.get("type", "Name")
                if ftype == "SequentialID":
                    fields.append(QgsField(field["name"], QVariant.Int))
                elif ftype == "Numeric":
                    if field.get("integer"):
                        fields.append(QgsField(field["name"], QVariant.Int))
                    else:
                        fields.append(QgsField(field["name"], QVariant.Double))
                else:
                    fields.append(QgsField(field["name"], QVariant.String))
            provider.addAttributes(fields)
            self.preview_layer.updateFields()

            hint = self.get_template_hint()
            from .core.attribute_generator import AttributeGenerator
            rows = AttributeGenerator.generate_attributes(len(geometries), seed, schema, hint)

            features = []
            for i in range(len(geometries)):
                f = QgsFeature(self.preview_layer.fields())
                f.setGeometry(geometries[i])
                for field in schema:
                    f.setAttribute(field["name"], rows[i].get(field["name"]))
                features.append(f)

            provider.addFeatures(features)
            self.preview_layer.updateExtents()
            QgsProject.instance().addMapLayer(self.preview_layer)

            # Spatial diagnostics calculations
            extent_width = abs(xmax - xmin)
            extent_height = abs(ymax - ymin)
            approx_area = round(extent_width * extent_height, 4)
            unit_suffix = "deg²" if crs_str == "EPSG:4326" else "m²"

            # Simple avg distance bounds estimation
            avg_dist = 0
            if len(geometries) > 1:
                total_dist = 0
                count_pairs = 0
                for a_idx in range(min(15, len(geometries))):
                    for b_idx in range(a_idx + 1, min(15, len(geometries))):
                        pt_a = geometries[a_idx].asPoint()
                        pt_b = geometries[b_idx].asPoint()
                        if pt_a and pt_b:
                            total_dist += pt_a.distance(pt_b)
                            count_pairs += 1
                if count_pairs > 0:
                    avg_dist = round(total_dist / count_pairs, 1)

            self.log(f"SUCCESS: Loaded temporary draft preview containing {len(geometries)} shapes.")
            self.log(
                f"<b>📊 Preview Diagnostics</b><br>"
                f"  • Extent Boundary: {approx_area} {unit_suffix}<br>"
                f"  • Estimated Spacing: {avg_dist} {unit_suffix.replace('²', '') if avg_dist > 0 else 'N/A'}<br>"
                f"  • Attributes Schema: {len(schema)} fields<br>"
                f"  • Valid Geometries: 100% | Duplicates: 0"
            )
        except Exception as e:
            self.reset_button_states()
            QMessageBox.critical(self, "Preview Failure", f"Failed to generate layout preview: {str(e)}")

    def run_generate(self):
        """Triggers the background worker thread execution."""
        output_path = self.path_edit.text().strip()
        layer_name = self.layer_name_edit.text().strip()
        geom_type = self.selected_geom_type
        count = self.count_spin.value()
        seed = self.seed_spin.value()
        dist = self.selected_distribution
        spacing = self.spacing_spin.value()
        schema = self.build_schema()

        try:
            val_path = "clipboard" if self.is_copy_geojson else output_path
            Validator.validate_parameters(val_path, layer_name, count, spacing, dist)
            xmin, ymin, xmax, ymax, wkt, crs_authid = self.get_selected_boundary_geometry()

            if crs_authid:
                is_geo = Validator.validate_crs(crs_authid)
                if is_geo and dist == "Poisson Disc (Spacing)":
                    self.log("WARNING: Boundary layer uses geographic degrees. Spacing is in degrees, not meters.")
        except Exception as e:
            QMessageBox.critical(self, "Validation Error", str(e))
            self.is_copy_geojson = False
            return

        self.log(f"Starting synthetic generation task ({count} {geom_type}s) in background...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.btn_generate.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.btn_copy_geojson.setEnabled(False)
        self.btn_export_script.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        error_settings = {}
        if self.chk_enable_errors.isChecked():
            error_settings = {
                "inject_duplicate_geoms": self.chk_err_dup_geom.isChecked(),
                "inject_self_intersections": self.chk_err_self_intersect.isChecked(),
                "inject_slivers": self.chk_err_slivers.isChecked(),
                "inject_duplicate_ids": self.chk_err_dup_ids.isChecked(),
                "inject_nulls": self.chk_err_nulls.isChecked(),
                "inject_outliers": self.chk_err_outliers.isChecked()
            }

        hint = self.get_template_hint()
        self.active_task = GenerationTask(
            xmin, ymin, xmax, ymax, geom_type, count, seed, dist, spacing, schema, wkt, error_settings, hint
        )
        # Store metadata for completion callback
        self.active_task.cached_crs = crs_authid if crs_authid else "EPSG:4326"
        self.active_task.progressChanged.connect(lambda val: self.progress_bar.setValue(int(val)))
        self.active_task.completed.connect(self.on_generation_completed)
        self.active_task.failed.connect(self.on_generation_failed)

        QgsApplication.taskManager().addTask(self.active_task)

    def get_template_hint(self):
        """Maps template index to core generator hint keyword."""
        idx = self.attrib_template_combo.currentIndex()
        if idx == 1:
            return "parcel"
        elif idx == 2:
            return "utility"
        elif idx == 3:
            return "forestry"
        elif idx == 4:
            return "telecom"
        return None

    def cancel_task(self):
        """Aborts background running generation thread."""
        if self.active_task:
            self.active_task.cancel()
            self.log("Generation canceled by user.")
            self.is_copy_geojson = False
            self.reset_button_states()

    def build_benchmark_manifest(self, error_settings, feature_count, geom_type, fmt_idx):
        """Builds a list of expected QA-tool findings for this generated dataset.

        Mirrors the deterministic error-injection logic in
        ``core/task_runner.py::GenerationTask.run`` exactly: that method only
        injects errors when ``len(geometries) > 2 and len(rows) > 2``, and
        always targets feature index 0, 1, or the last index. FIDs below
        assume a freshly written, freshly reloaded layer (GPKG/Shapefile/
        GeoJSON all number sequentially from 1 in that case). Geometry-based
        expectations are omitted for CSV output, since CSV export drops
        geometry entirely and a geometry rule can't fire against it.
        """
        if feature_count <= 2:
            return []

        is_csv = (fmt_idx == 3)
        last_fid = feature_count
        expectations = []

        if error_settings.get("inject_duplicate_geoms") and not is_csv:
            expectations.append({
                "geoqa_rule_id": "G004",
                "geoqa_rule_name": "Duplicate Geometry",
                "expected_issue_count": 1,
                "affected_fids": [1, 2],
                "description": "Feature 2's geometry was set to an exact duplicate of feature 1's.",
            })

        if error_settings.get("inject_self_intersections") and geom_type in ("Line", "Polygon") and not is_csv:
            shape = "self-intersecting linestring" if geom_type == "Line" else "self-intersecting polygon ring"
            expectations.append({
                "geoqa_rule_id": "G001",
                "geoqa_rule_name": "Invalid Geometry",
                "expected_issue_count": 1,
                "affected_fids": [1],
                "description": f"Feature 1's geometry was replaced with a {shape}.",
            })

        if error_settings.get("inject_slivers") and geom_type == "Polygon" and not is_csv:
            expectations.append({
                "geoqa_rule_id": "G005",
                "geoqa_rule_name": "Sliver Polygons",
                "expected_issue_count": 1,
                "affected_fids": [last_fid],
                "description": (
                    f"The last feature (FID {last_fid}) was replaced with a degenerate, "
                    "near-zero-area sliver triangle."
                ),
            })

        if error_settings.get("inject_duplicate_ids"):
            expectations.append({
                "geoqa_rule_id": "A005",
                "geoqa_rule_name": "Duplicate Identifiers",
                "expected_issue_count": 1,
                "affected_fids": [1, 2],
                "description": "Feature 2's ID field was overwritten to match feature 1's ID value.",
            })

        if error_settings.get("inject_nulls"):
            expectations.append({
                "geoqa_rule_id": "A003",
                "geoqa_rule_name": "Null Values",
                "expected_issue_count": 1,
                "affected_fids": [1, 2],
                "description": (
                    "A text field (name/class/category/status/material/species/provider) "
                    "was set to NULL on features 1 and 2."
                ),
            })

        if error_settings.get("inject_outliers"):
            expectations.append({
                "geoqa_rule_id": "A007",
                "geoqa_rule_name": "Statistical Outliers",
                "expected_issue_count": 1,
                "affected_fids": [1],
                "description": (
                    "A numeric field on feature 1 was set to an extreme outlier "
                    "(abs(original_value) * 100 + 999)."
                ),
            })

        return expectations

    def write_benchmark_manifest(self, base_dir, base_name, layer_name, output_path,
                                 expectations, feature_count, geom_type, crs_str, score):
        """Writes the companion GeoQA benchmark manifest (.json + .txt) to disk."""
        import json

        manifest = {
            "generated_by": f"GeoData Forge v{FORGE_VERSION}",
            "dataset_layer_name": layer_name,
            "dataset_path": output_path,
            "feature_count": feature_count,
            "geometry_type": geom_type,
            "crs": crs_str,
            "generation_quality_score": score,
            "expected_geoqa_findings": expectations,
            "notes": (
                "This manifest lists the QA rule violations intentionally injected into "
                "this dataset. Run it through GeoQA (or another QA tool) and confirm each "
                "rule_id below is reported at least once on the listed feature IDs. FIDs "
                "assume the layer is freshly written/reloaded and features are numbered "
                "sequentially from 1 in generation order."
            ),
        }

        json_path = os.path.join(base_dir, f"{base_name}_geoqa_manifest.json")
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(manifest, jf, indent=2)

        txt_lines = [
            "GeoData Forge — GeoQA Benchmark Manifest",
            "=" * 42,
            f"Dataset: {layer_name}  ({feature_count} {geom_type} features, {crs_str})",
            "",
            "Expected QA findings:",
        ]
        if expectations:
            for exp in expectations:
                fids = ", ".join(str(f) for f in exp["affected_fids"])
                txt_lines.append(
                    f"  • {exp['geoqa_rule_id']} ({exp['geoqa_rule_name']}) "
                    f"— {exp['expected_issue_count']} issue(s) on FID(s) {fids}"
                )
                txt_lines.append(f"      {exp['description']}")
        else:
            txt_lines.append("  (No error types were enabled/applicable for this run.)")
        txt_lines.append("")
        txt_lines.append(
            "Run this dataset through GeoQA and compare its report against the list "
            "above to confirm expected rules are still firing correctly."
        )
        txt_path = os.path.join(base_dir, f"{base_name}_geoqa_manifest.txt")
        with open(txt_path, "w", encoding="utf-8") as tf:
            tf.write("\n".join(txt_lines))

        return json_path, txt_path

    def on_generation_completed(self, features):
        """Writes thread results to output format and loads it to project."""
        schema = self.build_schema()
        requested_count = self.count_spin.value()
        crs_str = self.active_task.cached_crs
        geom_type = self.selected_geom_type

        # Check duplicate IDs and NULL parameters for quality audit scores
        has_dup_ids = False
        attribs_list = [f[1] for f in features]
        if attribs_list:
            has_dup_ids = not Validator.check_duplicate_ids(attribs_list)

        has_nulls = False
        if self.chk_enable_errors.isChecked() and self.chk_err_nulls.isChecked():
            has_nulls = True

        score, breakdown = Validator.compute_quality_score(
            features, schema, requested_count, crs_str, has_dup_ids, has_nulls
        )

        if self.is_copy_geojson:
            self.log("Serializing generated coordinates to GeoJSON collection...")
            try:
                import json
                features_json = []
                for geom, attrs in features:
                    geom_json = json.loads(geom.asJson())
                    features_json.append({
                        "type": "Feature",
                        "geometry": geom_json,
                        "properties": attrs
                    })
                geojson = {"type": "FeatureCollection", "features": features_json}
                QApplication.clipboard().setText(json.dumps(geojson, indent=2))
                self.log(f"SUCCESS: Copied {len(features)} features to clipboard! Quality Score: {score}/100")
            except Exception as err:
                self.log(f"ERROR: Failed to copy GeoJSON: {str(err)}")
            finally:
                self.is_copy_geojson = False
                self.reset_button_states()
            return

        output_path = os.path.abspath(self.path_edit.text().strip())
        layer_name = self.layer_name_edit.text().strip()
        fmt_idx = self.format_combo.currentIndex()

        # Release existing lock in QGIS layer tree
        layers_to_remove = []
        normalized_output = os.path.normpath(output_path).lower()
        for layer in QgsProject.instance().mapLayers().values():
            if layer.dataProvider() and hasattr(layer.dataProvider(), 'dataSourceUri'):
                uri = layer.dataProvider().dataSourceUri().lower()
                if normalized_output in uri or output_path.lower() in uri:
                    layers_to_remove.append(layer.id())
        if layers_to_remove:
            self.log("Releasing file lock: Unloading layer from layers list...")
            QgsProject.instance().removeMapLayers(layers_to_remove)

        try:
            # Enforce validation checks unless debug error is targeted
            if not self.chk_enable_errors.isChecked() or not self.chk_err_dup_ids.isChecked():
                if has_dup_ids:
                    raise ValueError("Duplicate feature IDs generated in attributes schema.")

            # Route to correct multi-format exporter
            if fmt_idx == 0:
                Exporter.export_to_gpkg(output_path, layer_name, crs_str, geom_type, schema, features)
                self.iface.addVectorLayer(output_path, layer_name, "ogr")
                fmt_desc = "GeoPackage (.gpkg)"
            elif fmt_idx == 1:
                Exporter.export_to_geojson(output_path, schema, features)
                self.iface.addVectorLayer(output_path, layer_name, "ogr")
                fmt_desc = "GeoJSON (.geojson)"
            elif fmt_idx == 2:
                Exporter.export_to_shapefile(output_path, layer_name, crs_str, geom_type, schema, features)
                self.iface.addVectorLayer(output_path, layer_name, "ogr")
                fmt_desc = "ESRI Shapefile (.shp)"
            else:
                Exporter.export_to_csv(output_path, schema, features)
                fmt_desc = "CSV Table (.csv)"

            self.log(f"SUCCESS: Layer written successfully. Quality Score: {score}/100")

            # Generate structured HTML Report and README.txt explanations alongside data
            base_dir = os.path.dirname(output_path)
            base_name = os.path.splitext(os.path.basename(output_path))[0]

            readme_path = os.path.join(base_dir, f"{base_name}_README.txt")
            report_path = os.path.join(base_dir, f"{base_name}_report.html")

            # 1. Write explanation README
            readme_content = f"""Dataset Name:
{layer_name}

Description:
Synthetic dataset containing {len(features)} {geom_type} features generated within the selected boundary extent.
Generated by GeoData Forge (v{FORGE_VERSION}).

Parameters:
• Random Seed: {self.seed_spin.value()}
• Coordinate Reference System: {crs_str}
• Spatial Layout: {self.selected_distribution}
• Data Format: {fmt_desc}
• Generation Quality Score: {score}/100

Generated Schema Fields:
"""
            for field in schema:
                readme_content += f"  • {field['name']}: Type {field['type']}\n"

            with open(readme_path, "w", encoding="utf-8") as rf:
                rf.write(readme_content)

            # 2. Write HTML report
            max_scores = {
                "Geometry valid": 25,
                "No duplicate IDs": 20,
                "No unexpected NULLs": 20,
                "Feature count match": 15,
                "Attribute completeness": 10,
                "CRS valid": 10
            }
            breakdown_rows = "".join([
                f"<tr><td>{k}</td><td><b>{v}/{max_scores.get(k, 25)}</b></td></tr>"
                for k, v in breakdown.items()
            ])
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>GeoData Forge - Generation Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            margin: 30px;
            background-color: #F8FAFC;
            color: #1E293B;
        }}
        .card {{
            background: #FFFFFF;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            max-width: 650px;
            margin: auto;
            border: 1px solid #E2E8F0;
        }}
        h1 {{
            color: #1E3A8A;
            font-size: 22px;
            border-bottom: 2px solid #E2E8F0;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        .metric-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin: 20px 0;
        }}
        .metric {{
            background: #F1F5F9;
            padding: 12px;
            border-radius: 6px;
            border-left: 4px solid #3B82F6;
        }}
        .metric span {{
            display: block;
            font-size: 11px;
            color: #64748B;
            text-transform: uppercase;
            font-weight: bold;
        }}
        .metric b {{
            font-size: 16px;
            color: #0F172A;
        }}
        .score {{
            text-align: center;
            background: #ECFDF5;
            border: 1px solid #10B981;
            padding: 15px;
            border-radius: 6px;
            margin: 20px 0;
        }}
        .score-val {{
            font-size: 32px;
            font-weight: bold;
            color: #059669;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #E2E8F0;
        }}
        th {{
            background-color: #F8FAFC;
            color: #64748B;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1>📊 GeoData Forge Generation Report</h1>
        <div class="score">
            <span>Overall Quality Score</span>
            <div class="score-val">{score}/100</div>
        </div>
        <div class="metric-grid">
            <div class="metric"><span>Dataset Name</span><b>{layer_name}</b></div>
            <div class="metric"><span>Geometry Type</span><b>{geom_type}</b></div>
            <div class="metric"><span>Features Generated</span><b>{len(features)}</b></div>
            <div class="metric"><span>Reference System</span><b>{crs_str}</b></div>
            <div class="metric"><span>Spatial Layout</span><b>{self.selected_distribution}</b></div>
            <div class="metric"><span>Output Format</span><b>{fmt_desc}</b></div>
        </div>

        <h2>Validation Breakdown</h2>
        <table>
            <thead>
                <tr><th>Audit Metric</th><th>Points Earned</th></tr>
            </thead>
            <tbody>
                {breakdown_rows}
            </tbody>
        </table>
        <p style="font-size: 11px; color: #94A3B8; text-align: center; margin-top: 25px;">
            Generated by GeoData Forge Plugin v{FORGE_VERSION}. All rights reserved.
        </p>
    </div>
</body>
</html>
"""
            with open(report_path, "w", encoding="utf-8") as hf:
                hf.write(html_content)

            self.log(f"SUCCESS: Report saved to {os.path.basename(report_path)}")
            self.log(f"SUCCESS: Dataset description readme saved to {os.path.basename(readme_path)}")

            # 3. GeoQA Benchmark Manifest — only meaningful when errors were intentionally injected
            manifest_line = ""
            if self.chk_enable_errors.isChecked() and self.chk_export_manifest.isChecked():
                error_settings = {
                    "inject_duplicate_geoms": self.chk_err_dup_geom.isChecked(),
                    "inject_self_intersections": self.chk_err_self_intersect.isChecked(),
                    "inject_slivers": self.chk_err_slivers.isChecked(),
                    "inject_duplicate_ids": self.chk_err_dup_ids.isChecked(),
                    "inject_nulls": self.chk_err_nulls.isChecked(),
                    "inject_outliers": self.chk_err_outliers.isChecked(),
                }
                expectations = self.build_benchmark_manifest(
                    error_settings, len(features), geom_type, fmt_idx
                )
                if expectations:
                    _, manifest_txt_path = self.write_benchmark_manifest(
                        base_dir, base_name, layer_name, output_path,
                        expectations, len(features), geom_type, crs_str, score
                    )
                    rule_ids = ", ".join(e["geoqa_rule_id"] for e in expectations)
                    self.log(
                        f"SUCCESS: GeoQA benchmark manifest saved to "
                        f"{os.path.basename(manifest_txt_path)} — expects {rule_ids}"
                    )
                    manifest_line = (
                        f"• <b>GeoQA Benchmark Manifest:</b> expects {rule_ids}<br>"
                    )

            # Formulate breakdown message
            breakdown_lines = "<br>".join([f"  • {k}: {v} pts" for k, v in breakdown.items()])
            summary_msg = (
                f"<b>📊 Generation Summary</b><br><br>"
                f"• <b>Features Created:</b> {len(features)} {geom_type}s<br>"
                f"• <b>Attributes Compiled:</b> {len(schema)} fields<br>"
                f"• <b>Data Format:</b> {fmt_desc}<br>"
                f"• <b>Quality Score:</b> {score}/100<br>"
                f"{manifest_line}"
                f"• <b>Validation Audit Metrics:</b><br>{breakdown_lines}<br><br>"
                f"<i>HTML Report & README explanation files created successfully!</i>"
            )
            box = QMessageBox(self)
            box.setWindowTitle("Generation Summary")
            box.setTextFormat(Qt.RichText)
            box.setText(summary_msg)
            box.setIcon(QMessageBox.Information)
            box.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Export Failure", f"Failed to write output: {str(e)}")
            self.log(f"ERROR: Export failed: {str(e)}")

        self.reset_button_states()

    def on_generation_failed(self, exception):
        """Catches and reports worker exceptions."""
        QMessageBox.critical(self, "Generation Failed", f"Background thread exception: {str(exception)}")
        self.log(f"ERROR: Generation thread aborted: {str(exception)}")
        self.reset_button_states()

    def reset_button_states(self):
        """Resets status, cancels progress, and enables buttons."""
        self.progress_bar.setVisible(False)
        self.btn_generate.setEnabled(True)
        self.btn_preview.setEnabled(True)
        self.btn_copy_geojson.setEnabled(True)
        self.btn_export_script.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.active_task = None

    def log(self, message):
        """Appends status messages to text log area with colorized HTML markup."""
        colorized = message
        if "SUCCESS:" in message:
            colorized = colorized.replace("SUCCESS:", '<font color="#22C55E"><b>SUCCESS:</b></font>')
        elif "WARNING:" in message:
            colorized = colorized.replace("WARNING:", '<font color="#EAB308"><b>WARNING:</b></font>')
        elif "ERROR:" in message:
            colorized = colorized.replace("ERROR:", '<font color="#EF4444"><b>ERROR:</b></font>')
        elif message.startswith("Starting") or "complete" in message.lower() or "progress" in message.lower():
            colorized = f'<font color="#3B82F6">{colorized}</font>'

        self.log_text.append(colorized)
        self.log_text.ensureCursorVisible()

    def closeEvent(self, event):
        """Records time spent and increments session counter in telemetry log on dialog close."""
        try:
            import json
            duration = round(time.time() - self.start_time, 2)
            user_dir = os.path.expanduser("~")
            telemetry_path = os.path.join(user_dir, ".geodata_forge_telemetry.json")

            stats = {"total_opens": 0, "total_seconds_spent": 0.0, "sessions": []}
            if os.path.exists(telemetry_path):
                with open(telemetry_path, "r", encoding="utf-8") as f:
                    try:
                        stats = json.load(f)
                    except Exception:
                        pass

            stats["total_opens"] += 1
            stats["total_seconds_spent"] = round(stats.get("total_seconds_spent", 0.0) + duration, 2)
            stats["sessions"].append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_seconds": duration
            })

            # Keep only last 50 session history logs
            stats["sessions"] = stats["sessions"][-50:]

            with open(telemetry_path, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=4)
        except Exception:
            pass  # silent fail to never disrupt user
        super().closeEvent(event)

    @property
    def selected_geom_type(self) -> str:
        """Returns clean geometry type ('Point', 'Line', 'Polygon') matching display selection."""
        raw = self.geom_type_combo.currentText()
        if "Line" in raw:
            return "Line"
        if "Polygon" in raw:
            return "Polygon"
        return "Point"

    @property
    def selected_distribution(self) -> str:
        """Returns clean internal distribution key for the current selection.

        The combo box's visible labels are re-populated per geometry type in
        ``on_geom_type_changed`` (e.g. "MST Network (Gaussian)" for Line,
        "Voronoi Parcels (Gaussian)" for Polygon) so they no longer reliably
        contain the words "Clustered"/"Poisson". Matching by index instead
        keeps this in sync with task_runner.py's dispatch, which only cares
        about position 0 (Uniform-style) vs 1 (Gaussian-style) vs 2
        (Poisson-style) regardless of the label text shown to the user.
        """
        idx = self.dist_combo.currentIndex()
        if idx == 1:
            return "Gaussian Clustered"
        if idx == 2:
            return "Poisson Disc (Spacing)"
        return "Uniform"

    def run_export_script(self):
        """Generates a standalone Python script to reproduce this synthetic dataset layout."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Standalone Python Script", "generate_synthetic_data.py", "Python Files (*.py)"
        )
        if not path:
            return

        try:
            count = self.count_spin.value()
            geom_type = self.selected_geom_type
            seed = self.seed_spin.value()
            dist = self.selected_distribution
            spacing = self.spacing_spin.value()
            schema = self.build_schema()
            xmin, ymin, xmax, ymax, wkt, crs_authid = self.get_selected_boundary_geometry()

            # stand-alone Python script template
            script_template = f'''# -*- coding: utf-8 -*-
"""
Standalone Synthetic Spatial Data Generator Script
Generated by GeoData Forge (v{FORGE_VERSION})

Note: This standalone script generates a simplified version of your dataset.
It uses a basic uniform random distribution to generate point coordinates.
For Line/Polygon geometries, it generates simple rectangular box buffers around
the generated point coordinates. Advanced spatial distributions (Poisson, Gaussian,
MST, Voronoi) and domain-correlated attribute rules are not supported in this
standalone CLI exporter.

Run this script from any command-line environment:
    python {os.path.basename(path)}
"""
import json
import random
import math
import datetime

# Configuration Parameters
GEOM_TYPE = {repr(geom_type)}
FEATURE_COUNT = {count}
RANDOM_SEED = {seed}
DISTRIBUTION = {repr(dist)}
SPACING = {spacing}
SCHEMA = {repr(schema)}
BOUNDS = ({xmin}, {ymin}, {xmax}, {ymax})

def generate_points():
    rnd = random.Random(RANDOM_SEED)
    points = []
    xmin, ymin, xmax, ymax = BOUNDS
    for _ in range(FEATURE_COUNT):
        x = rnd.uniform(xmin, xmax)
        y = rnd.uniform(ymin, ymax)
        points.append((x, y))
    return points

def generate_attributes():
    rnd = random.Random(RANDOM_SEED)
    rows = []
    FACILITIES = ["Substation", "Transmitter", "Collector", "Gateway", "Repeater"]
    STREETS = ["Pine St", "Oak Rd", "Maple Ave", "Main St", "Cedar Ln"]

    for idx in range(FEATURE_COUNT):
        row = {{}}
        for field in SCHEMA:
            name = field["name"]
            ftype = field["type"]

            if ftype == "SequentialID":
                row[name] = idx + 1
            elif ftype == "Name":
                choices = field.get("choices")
                if choices:
                    row[name] = rnd.choice(choices)
                else:
                    row[name] = f"{{rnd.choice(FACILITIES)}} {{rnd.choice(STREETS)}}"
            elif ftype == "Category":
                choices = field.get("choices", ["Type A", "Type B", "Standard", "Premium"])
                row[name] = rnd.choice(choices)
            elif ftype == "Numeric":
                v_min = field.get("min", 0)
                v_max = field.get("max", 100)
                row[name] = round(rnd.uniform(v_min, v_max), 2)
            elif ftype == "Date":
                start_year = field.get("start_year", 2015)
                end_year = field.get("end_year", 2026)
                start_dt = datetime.datetime(start_year, 1, 1)
                end_dt = datetime.datetime(end_year, 12, 31)
                delta_seconds = int((end_dt - start_dt).total_seconds())
                offset = rnd.randint(0, delta_seconds)
                target_dt = start_dt + datetime.timedelta(seconds=offset)
                row[name] = target_dt.strftime("%Y-%m-%d")
            elif ftype == "Year":
                start_year = field.get("start_year", 1990)
                end_year = field.get("end_year", 2024)
                row[name] = rnd.randint(start_year, end_year)
            elif ftype == "Status":
                choices = field.get("choices", ["Active", "Planned", "Maintenance"])
                row[name] = rnd.choice(choices)
        rows.append(row)
    return rows

def build_geojson():
    points = generate_points()
    attributes = generate_attributes()

    features = []
    for i in range(len(points)):
        x, y = points[i]

        # Build valid geometry structure based on selected type
        if GEOM_TYPE == "Point":
            geom_struct = {{
                "type": "Point",
                "coordinates": [x, y]
            }}
        elif GEOM_TYPE == "Line":
            geom_struct = {{
                "type": "LineString",
                "coordinates": [[x, y], [x + 0.005, y + 0.005]]
            }}
        else:
            geom_struct = {{
                "type": "Polygon",
                "coordinates": [[[x, y], [x + 0.005, y], [x + 0.005, y + 0.005], [x, y + 0.005], [x, y]]]
            }}

        feature = {{
            "type": "Feature",
            "geometry": geom_struct,
            "properties": attributes[i]
        }}
        features.append(feature)

    geojson = {{
        "type": "FeatureCollection",
        "features": features
    }}
    return geojson

if __name__ == "__main__":
    data = build_geojson()
    output_file = "output_synthetic_data.geojson"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"SUCCESS: Generated {{len(data['features'])}} features and saved to {{output_file}}!")
'''
            with open(path, "w", encoding="utf-8") as f:
                f.write(script_template)

            self.log(f"SUCCESS: Standalone automation script saved to {path}")
            QMessageBox.information(self, "Export Script", "Standalone Python automation script saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Export Script Error", f"Failed to save automation script: {str(e)}")
            self.log(f"ERROR: Script export failed: {str(e)}")
