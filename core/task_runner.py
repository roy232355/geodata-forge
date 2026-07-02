# -*- coding: utf-8 -*-
"""QgsTask implementation for background thread execution of synthetic data generation."""
from qgis.core import QgsTask, QgsGeometry, QgsPointXY
from qgis.PyQt.QtCore import pyqtSignal

from .geometry_generator import GeometryGenerator
from .attribute_generator import AttributeGenerator


class GenerationTask(QgsTask):
    """Asynchronously generates synthetic geometries and attributes.

    Supports Point, Line, and Polygon geometries with Uniform, Clustered,
    and Poisson Disc spacing. Also supports QA Error Injection.
    """

    completed = pyqtSignal(list)   # Emitted with list of (QgsGeometry, dict)
    failed = pyqtSignal(object)    # Emitted with Exception

    def __init__(self, xmin, ymin, xmax, ymax, geom_type, count, seed,
                 distribution, min_dist, schema, boundary_wkt=None,
                 error_settings=None, template_hint=None):
        super().__init__("GeoData Forge Generator", QgsTask.CanCancel)
        self.xmin = xmin
        self.ymin = ymin
        self.xmax = xmax
        self.ymax = ymax
        self.geom_type = geom_type
        self.count = count
        self.seed = seed
        self.distribution = distribution
        self.min_dist = min_dist
        self.schema = schema
        self.boundary_wkt = boundary_wkt
        self.error_settings = error_settings or {}
        self.template_hint = template_hint
        self.result_features = []
        self.exception = None

    def run(self) -> bool:
        """Runs coordinate math and attribute arrays on the background thread."""
        try:
            boundary_geom = None
            if self.boundary_wkt:
                boundary_geom = QgsGeometry.fromWkt(self.boundary_wkt)

            if self.isCanceled():
                return False

            geometries = []
            if self.geom_type == "Point":
                if self.distribution == "Poisson Disc (Spacing)":
                    points = GeometryGenerator.generate_poisson_disc_points(
                        self.xmin, self.ymin, self.xmax, self.ymax,
                        self.count, self.seed, self.min_dist, boundary_geom
                    )
                elif self.distribution == "Gaussian Clustered":
                    points = GeometryGenerator.generate_clustered_points(
                        self.xmin, self.ymin, self.xmax, self.ymax,
                        self.count, self.seed, boundary_geom
                    )
                else:
                    points = GeometryGenerator.generate_uniform_points(
                        self.xmin, self.ymin, self.xmax, self.ymax,
                        self.count, self.seed, boundary_geom
                    )
                geometries = [QgsGeometry.fromPointXY(p) for p in points]

            elif self.geom_type == "Line":
                if self.distribution in ("Gaussian Clustered", "Poisson Disc (Spacing)"):
                    geometries = GeometryGenerator.generate_mst_networks(
                        self.xmin, self.ymin, self.xmax, self.ymax,
                        self.count, self.seed, boundary_geom
                    )
                else:
                    geometries = GeometryGenerator.generate_random_paths(
                        self.xmin, self.ymin, self.xmax, self.ymax,
                        self.count, self.seed, boundary_geom
                    )

            elif self.geom_type == "Polygon":
                if self.distribution in ("Gaussian Clustered", "Poisson Disc (Spacing)"):
                    geometries = GeometryGenerator.generate_voronoi_parcels(
                        self.xmin, self.ymin, self.xmax, self.ymax,
                        self.count, self.seed, boundary_geom
                    )
                else:
                    geometries = GeometryGenerator.generate_star_polygons(
                        self.xmin, self.ymin, self.xmax, self.ymax,
                        self.count, self.seed, boundary_geom
                    )

            self.setProgress(30)
            if self.isCanceled():
                return False

            # Use actual geometry count - boundary clipping may have reduced it
            actual_count = len(geometries)
            rows = AttributeGenerator.generate_attributes(
                actual_count, self.seed, self.schema, self.template_hint
            )

            self.setProgress(65)
            if self.isCanceled():
                return False

            if len(geometries) > 2 and len(rows) > 2:
                if self.error_settings.get("inject_duplicate_geoms"):
                    geometries[1] = QgsGeometry(geometries[0])

                if self.error_settings.get("inject_self_intersections") and \
                        self.geom_type in ("Line", "Polygon"):
                    if self.geom_type == "Line":
                        geometries[0] = QgsGeometry.fromWkt(
                            "LINESTRING(0 0, 10 10, 0 10, 10 0)")
                    else:
                        geometries[0] = QgsGeometry.fromWkt(
                            "POLYGON((0 0, 10 10, 0 10, 10 0, 0 0))")

                if self.error_settings.get("inject_slivers") and \
                        self.geom_type == "Polygon":
                    cx = (self.xmin + self.xmax) / 2.0
                    cy = (self.ymin + self.ymax) / 2.0
                    sliver = QgsGeometry.fromPolygonXY([[
                        QgsPointXY(cx, cy),
                        QgsPointXY(cx + 0.0001, cy),
                        QgsPointXY(cx, cy + 0.000001),
                        QgsPointXY(cx, cy)
                    ]])
                    geometries[-1] = sliver

                if self.error_settings.get("inject_duplicate_ids"):
                    id_key = next(
                        (k for k in rows[0].keys()
                         if k.lower() == "id" or k.lower().endswith("_id")), None)
                    if id_key:
                        rows[1][id_key] = rows[0][id_key]

                if self.error_settings.get("inject_nulls"):
                    for k in list(rows[0].keys()):
                        lk = k.lower()
                        if any(t in lk for t in
                               ["name", "class", "category", "status",
                                "material", "species", "provider"]):
                            rows[0][k] = None
                            rows[1][k] = None

                if self.error_settings.get("inject_outliers"):
                    val_key = next(
                        (k for k in rows[0].keys()
                         if any(t in k.lower() for t in
                                ["value", "diameter", "dbh", "height",
                                 "coverage", "area"])), None)
                    if val_key and rows[0].get(val_key) is not None:
                        base_val = rows[0][val_key]
                        rows[0][val_key] = abs(base_val) * 100 + 999.0

            self.setProgress(90)

            feature_count = min(len(geometries), len(rows))
            for i in range(feature_count):
                self.result_features.append((geometries[i], rows[i]))

            self.setProgress(100)
            return True

        except Exception as e:
            self.exception = e
            return False

    def finished(self, result: bool):
        """Callback run on the QGIS main thread after execution completes."""
        if result:
            self.completed.emit(self.result_features)
        else:
            self.failed.emit(
                self.exception or Exception("Background generation thread failed."))
