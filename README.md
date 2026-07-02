# GeoData Forge: Synthetic Geospatial Data Generator

[![QGIS Compatibility](https://img.shields.io/badge/QGIS-3.28%20LTR%20%7C%203.x-brightgreen.svg)](https://qgis.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.8%20%7C%203.12-blue.svg)](https://python.org/)
[![Version](https://img.shields.io/badge/Release-v1.0.0-orange.svg)](https://github.com/roy232355/geodata-forge/releases)

GeoData Forge is a high-performance QGIS plugin designed to generate realistic synthetic vector datasets for testing, demonstrations, dashboards, machine learning, and education.

Instead of generating simple random shapes, GeoData Forge generates **domain-aware correlated datasets** where geometry type, spatial distribution layout, database schema attributes, and validation rules all align seamlessly.

---

## 🚀 Key Features

* **Advanced Geometry Generations**:
  * **Point Features**: Uniform, Gaussian Clustered, and Poisson Disc (minimum spacing buffers) layouts.
  * **Line Features**: Random path lines and **Minimum Spanning Tree (MST)** networks (topologically connected without self-intersections or redundant loops).
  * **Polygon Features**: Star-convex shapes and **Voronoi parcels** (modeling cadastral boundaries with zero gaps or overlaps).
* **Domain-Correlated Presets**:
  * **🏡 Cadastral / Parcel Registry**: Land zoning dictates value ranges and registry status.
  * **🚰 Water Utility**: Pipe diameter, material, installation age, and leak statuses are logically linked.
  * **🌳 Forestry Survey**: Tree species dictates biometric ranges (DBH, height, and age correlation).
  * **📡 Telecom Network**: Tower type (Macro vs Microcell) controls physical heights, driving the signal coverage radius.
* **QGIS Map Canvas Live Preview**: Renders temporary memory preview layers in a single click before exporting features.
* **Profile Configuration Manager**: Saves and loads all GUI parameters to reusable `.json` files.
* **QA Error Injection Mode**: Intentionally injects invalid geometries, self-intersections, slivers, duplicate IDs, outliers, or NULL fields to benchmark validation software like **GeoQA**.
* **Automation Automation Exporter**: Generates a zero-dependency standalone Python script (`.py`) to replicate the configuration and generate matching GeoJSON features outside of QGIS.
* **Telemetry Diagnostics Dashboard**: Generates structured HTML Quality Reports and explainer README files next to output files.

---

## 📦 Installation

### Method 1: Install from ZIP (Recommended for QGIS Release)
1. Download the release package: `GeoDataForge_v1.0.0.zip`.
2. Open QGIS.
3. Go to **Plugins** -> **Manage and Install Plugins** -> **Install from ZIP**.
4. Select the downloaded ZIP file and click **Install Plugin**.

### Method 2: Manual Development Install
Clone this repository directly into your QGIS plugins directory:
* **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\GeoDataForge`
* **Linux**: `~/.local/share/QGIS/QGIS3/profiles\default\python\plugins\GeoDataForge`
* **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/GeoDataForge`

---

## 🏗️ Technical Architecture

GeoData Forge utilizes a modular architecture designed for maintainability and reliability:
```
GeoDataForge/
├── core/
│   ├── attribute_generator.py  # Domain-correlated database schema generator
│   ├── geometry_generator.py   # Spatial geometry layouts (Poisson Disc, Voronoi, MST)
│   ├── profile_manager.py      # Profile JSON loader/writer with size protection
│   ├── task_runner.py          # QgsTask background thread runner
│   └── validator.py            # Quality validation metrics scorer (0-100)
├── reporting/
│   └── exporter.py             # GPKG, GeoJSON, Shapefile, CSV multi-format exporter
├── tests/
│   ├── run_tests.py            # Offline unit test execution runner
│   └── test_generators.py      # Comprehensive unit tests suite (13 passing tests)
├── dialog.py                   # PyQt UI Dialog interface controller
├── main_plugin.py              # Main QGIS Plugin lifecycle entry point
├── metadata.txt                # QGIS repository plugin registration metadata
├── icon.png                    # Plugin toolbar action logo icon
└── .gitignore                  # Git tracking exclusion filters
```

---

## 🛠️ Verification & Automated Packaging

To clean build-bytecode caches, run the test suites, and compile a clean compliant distribution ZIP:
```bash
# 1. Navigate to parent directory
cd ..

# 2. Run automated packaging script
python package_forge.py
```
This automatically produces a clean `GeoDataForge_v1.0.0.zip` ready for deployment to the [QGIS Plugins Repository](https://plugins.qgis.org/).

---

## 📄 License

GeoData Forge is distributed under the **GPL-v3** license. See the [LICENSE](LICENSE) file in the workspace parent directory for details.
