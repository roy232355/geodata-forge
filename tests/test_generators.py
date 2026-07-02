# -*- coding: utf-8 -*-
"""Unit tests for GeoData Forge spatial, attribute, validation, and JSON profile math."""
import os
import sys
import tempfile
import types
import unittest

# 1. Inject QGIS mock modules into sys.modules for offline test capabilities
class MockPointXY:
    def __init__(self, x, y):
        self._x = x
        self._y = y
    def x(self): return self._x
    def y(self): return self._y
    def __repr__(self): return f"Point({self._x}, {self._y})"

class MockGeometry:
    @staticmethod
    def fromPointXY(pt):
        return MockGeometry(pt)
    @staticmethod
    def fromWkt(wkt):
        return MockGeometry(None)
    @staticmethod
    def fromMultiPointXY(pts):
        return MockGeometry(None)
    @staticmethod
    def fromRect(rect):
        return MockGeometry(None)
    @staticmethod
    def fromPolygonXY(rings):
        return MockGeometry(None)
    def __init__(self, pt):
        self.pt = pt
    def contains(self, other):
        return True
    def isGeosValid(self):
        return True
    def isNull(self):
        return False
    def isEmpty(self):
        return False
    def type(self):
        from qgis.core import QgsWkbTypes
        return QgsWkbTypes.PolygonGeometry
    def voronoiDiagram(self, extent):
        return MockGeometry(None)
    def asGeometryCollection(self):
        return [MockGeometry(None), MockGeometry(None), MockGeometry(None)]
    def boundingBox(self):
        return MockRectangle(0, 0, 100, 100)
    def intersection(self, other):
        return MockGeometry(None)
    def asJson(self):
        return '{"type": "Point", "coordinates": [0.0, 0.0]}'

class MockRectangle:
    def __init__(self, xmin, ymin, xmax, ymax):
        self._xmin = xmin
        self._ymin = ymin
        self._xmax = xmax
        self._ymax = ymax
    def xMinimum(self): return self._xmin
    def yMinimum(self): return self._ymin
    def xMaximum(self): return self._xmax
    def yMaximum(self): return self._ymax

class MockLineString:
    def __init__(self, points):
        self.points = points

class MockPolygon:
    def __init__(self):
        pass

class MockWkbTypes:
    Point = 1
    LineString = 2
    Polygon = 3
    PolygonGeometry = 3

class MockCoordinateReferenceSystem:
    def __init__(self, authid):
        self.authid = authid
    def isValid(self):
        return self.authid.startswith("EPSG:")
    def isGeographic(self):
        return self.authid == "EPSG:4326"

class MockFields:
    def __init__(self):
        self.fields = []
    def append(self, f):
        self.fields.append(f)

class MockField:
    def __init__(self, name, q_type):
        self.name = name
        self.q_type = q_type

class MockFeature:
    def __init__(self, fields=None):
        self.fields = fields
        self.geom = None
        self.attribs = {}
    def setGeometry(self, geom):
        self.geom = geom
    def setAttribute(self, key, val):
        self.attribs[key] = val

class MockProject:
    @staticmethod
    def instance():
        return MockProject()
    def transformContext(self):
        return None

class MockVectorFileWriter:
    NoError = 0
    SaveVectorOptions = type('SaveVectorOptions', (), {})
    CreateOrOverwriteFile = 1
    @staticmethod
    def create(path, fields, geometry_type, crs, transform_context, options):
        return MockVectorFileWriter()
    def hasError(self):
        return 0
    def errorMessage(self):
        return ""
    def addFeature(self, f):
        pass

# Mock the modules
qgis_core = types.ModuleType('qgis.core')
qgis_core.QgsPointXY = MockPointXY
qgis_core.QgsGeometry = MockGeometry
qgis_core.QgsRectangle = MockRectangle
qgis_core.QgsLineString = MockLineString
qgis_core.QgsPolygon = MockPolygon
qgis_core.QgsWkbTypes = MockWkbTypes
qgis_core.QgsCoordinateReferenceSystem = MockCoordinateReferenceSystem
qgis_core.QgsPoint = MockPointXY
qgis_core.QgsFields = MockFields
qgis_core.QgsField = MockField
qgis_core.QgsFeature = MockFeature
qgis_core.QgsProject = MockProject
qgis_core.QgsVectorFileWriter = MockVectorFileWriter
sys.modules['qgis.core'] = qgis_core

# Mock PyQt
qgis_pyqt = types.ModuleType('qgis.PyQt')
qgis_pyqt_core = types.ModuleType('qgis.PyQt.QtCore')
qgis_pyqt_core.QVariant = type('QVariant', (), {"Int": 1, "Double": 2, "String": 3})
sys.modules['qgis.PyQt'] = qgis_pyqt
sys.modules['qgis.PyQt.QtCore'] = qgis_pyqt_core

# 2. Imports after QGIS bindings are mocked
from core.geometry_generator import GeometryGenerator  # noqa: E402
from core.attribute_generator import AttributeGenerator  # noqa: E402
from core.validator import Validator  # noqa: E402
from core.profile_manager import ProfileManager  # noqa: E402
from reporting.exporter import Exporter  # noqa: E402


class TestGeometryGenerator(unittest.TestCase):
    """Verifies coordinates layouts (Points, Lines, Polygons) and reproducibility."""

    def setUp(self):
        self.xmin, self.ymin, self.xmax, self.ymax = 0, 0, 100, 100
        self.count = 20
        self.seed = 42

    def test_uniform_points(self):
        points = GeometryGenerator.generate_uniform_points(
            self.xmin, self.ymin, self.xmax, self.ymax, self.count, self.seed
        )
        self.assertEqual(len(points), self.count)
        for pt in points:
            self.assertTrue(self.xmin <= pt.x() <= self.xmax)
            self.assertTrue(self.ymin <= pt.y() <= self.ymax)

    def test_clustered_points(self):
        points = GeometryGenerator.generate_clustered_points(
            self.xmin, self.ymin, self.xmax, self.ymax, self.count, self.seed
        )
        self.assertEqual(len(points), self.count)

    def test_poisson_disc_points(self):
        points = GeometryGenerator.generate_poisson_disc_points(
            self.xmin, self.ymin, self.xmax, self.ymax, self.count, self.seed, min_dist=10.0
        )
        self.assertEqual(len(points), self.count)

    def test_random_paths(self):
        lines = GeometryGenerator.generate_random_paths(
            self.xmin, self.ymin, self.xmax, self.ymax, self.count, self.seed
        )
        self.assertEqual(len(lines), self.count)

    def test_mst_networks(self):
        lines = GeometryGenerator.generate_mst_networks(
            self.xmin, self.ymin, self.xmax, self.ymax, self.count, self.seed
        )
        self.assertEqual(len(lines), self.count)

    def test_star_polygons(self):
        polys = GeometryGenerator.generate_star_polygons(
            self.xmin, self.ymin, self.xmax, self.ymax, self.count, self.seed
        )
        self.assertEqual(len(polys), self.count)

    def test_voronoi_parcels(self):
        polys = GeometryGenerator.generate_voronoi_parcels(
            self.xmin, self.ymin, self.xmax, self.ymax, self.count, self.seed
        )
        self.assertEqual(len(polys), self.count)


class TestAttributeGenerator(unittest.TestCase):
    """Verifies attribute mapping structure, category enums, and presets."""

    def setUp(self):
        self.count = 10
        self.seed = 42

    def test_domain_presets(self):
        # Forestry scientific biometric correlated tests
        schema = [
            {"name": "species_scientific", "type": "Name"},
            {"name": "dbh_cm", "type": "Numeric", "min": 5, "max": 120},
            {"name": "height_m", "type": "Numeric", "min": 2, "max": 50}
        ]
        rows = AttributeGenerator.generate_attributes(self.count, self.seed, schema, "forestry")
        self.assertEqual(len(rows), self.count)
        for r in rows:
            self.assertIn("species_scientific", r)
            self.assertIn("dbh_cm", r)
            self.assertIn("height_m", r)
            self.assertTrue(r["height_m"] > 0)


class TestValidator(unittest.TestCase):
    """Verifies parameter validation checks, unique IDs, and quality scores."""

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            Validator.validate_parameters("", "layer", 500, 20.0, "Uniform")

    def test_unique_ids(self):
        valid_rows = [{"parcel_id": 1}, {"parcel_id": 2}]
        invalid_rows = [{"parcel_id": 1}, {"parcel_id": 1}]
        self.assertTrue(Validator.check_duplicate_ids(valid_rows))
        self.assertFalse(Validator.check_duplicate_ids(invalid_rows))

    def test_quality_scoring(self):
        schema = [{"name": "parcel_id", "type": "SequentialID"}]
        features = [(MockGeometry(None), {"parcel_id": 1})]
        score, breakdown = Validator.compute_quality_score(features, schema, 1, "EPSG:4326")
        self.assertEqual(score, 100)
        self.assertEqual(breakdown["Geometry valid"], 25)


class TestProfileManager(unittest.TestCase):
    """Verifies profile configuration loading size checks."""

    def setUp(self):
        self.temp_file = tempfile.mktemp(suffix=".json")

    def tearDown(self):
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)

    def test_oversized_file_rejected(self):
        # Build a large temp file exceeding size guard limits
        with open(self.temp_file, "w") as f:
            f.write(" " * (6 * 1024 * 1024))
        with self.assertRaises(ValueError):
            ProfileManager.load_profile(self.temp_file)


class TestExporter(unittest.TestCase):
    """Verifies multi-format export file creations."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_export_to_geojson_file(self):
        path = os.path.join(self.temp_dir, "test.geojson")
        schema = [{"name": "id", "type": "SequentialID"}]
        features = [(MockGeometry(None), {"id": 1})]
        Exporter.export_to_geojson(path, schema, features)
        self.assertTrue(os.path.exists(path))

if __name__ == "__main__":
    unittest.main()
