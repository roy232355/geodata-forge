# -*- coding: utf-8 -*-
"""Validation engine and quality scoring for GeoData Forge configuration parameters."""
import os
from qgis.core import QgsCoordinateReferenceSystem


class Validator:
    """Validates configurations, paths, CRS, features, and scores dataset quality."""

    @staticmethod
    def validate_parameters(output_path, layer_name, count, min_dist, distribution):
        """Checks inputs for structural errors. Raises ValueError on violations."""
        if not output_path:
            raise ValueError("Output file path cannot be empty.")
        if output_path != "clipboard":
            directory = os.path.dirname(os.path.abspath(output_path))
            if not os.path.exists(directory):
                raise ValueError(f"Output directory does not exist: {directory}")
            if not os.access(directory, os.W_OK):
                raise ValueError(f"Output directory is not writable: {directory}")
        if not layer_name:
            raise ValueError("Layer name cannot be empty.")
        if count <= 0:
            raise ValueError("Feature count must be greater than zero.")
        if distribution == "Poisson Disc (Spacing)" and min_dist <= 0:
            raise ValueError("Minimum spacing distance must be greater than zero.")
        return True

    @staticmethod
    def validate_crs(crs_authid):
        """Validates CRS auth ID. Returns True if geographic (degrees), False if projected."""
        crs = QgsCoordinateReferenceSystem(crs_authid)
        if not crs.isValid():
            raise ValueError(f"Invalid Coordinate Reference System: {crs_authid}")
        return crs.isGeographic()

    @staticmethod
    def validate_geometry(geom):
        """Returns True if QgsGeometry is valid, non-null, and non-empty."""
        if geom is None or geom.isNull() or geom.isEmpty():
            return False
        return geom.isGeosValid()

    @staticmethod
    def check_duplicate_ids(rows, id_field=None):
        """Checks if any ID-like attribute column holds unique values.

        Auto-detects the first column ending with '_id' or equal to 'id'.
        Supports all domain template presets (parcel_id, pipe_id, tree_id, tower_id).
        """
        if not rows:
            return True
        if id_field is None:
            sample = rows[0]
            for key in sample.keys():
                if key.lower() == "id" or key.lower().endswith("_id"):
                    id_field = key
                    break
        if id_field is None:
            return True
        ids = [r.get(id_field) for r in rows if r.get(id_field) is not None]
        return len(ids) == len(set(ids))

    @staticmethod
    def compute_quality_score(features, schema, requested_count, crs_authid,
                              has_duplicate_ids=False, has_nulls_injected=False):
        """Computes a 0-100 quality score for a generated dataset.

        Checks:
          - Geometry validity      (25 pts)
          - No duplicate IDs       (20 pts)
          - No unexpected NULLs    (20 pts)
          - Feature count match    (15 pts)
          - Attribute completeness (10 pts)
          - CRS valid              (10 pts)

        Returns:
            tuple: (score: int, breakdown: dict)
        """
        breakdown = {}
        score = 0

        # 1. Geometry validity
        if features:
            valid_geoms = sum(
                1 for geom, _ in features
                if geom and not geom.isNull() and not geom.isEmpty() and geom.isGeosValid()
            )
            geom_score = int(25 * valid_geoms / len(features))
        else:
            geom_score = 0
        breakdown["Geometry valid"] = geom_score
        score += geom_score

        # 2. No duplicate IDs
        id_score = 0 if has_duplicate_ids else 20
        breakdown["No duplicate IDs"] = id_score
        score += id_score

        # 3. No unexpected NULLs
        if has_nulls_injected:
            null_score = 20  # Intentional error injection: score remains perfect for expected QA dataset tests
        elif features:
            null_count = sum(
                1 for _, attrs in features
                for v in attrs.values() if v is None
            )
            null_score = 20 if null_count == 0 else max(0, 20 - null_count)
        else:
            null_score = 0
        breakdown["No unexpected NULLs"] = null_score
        score += null_score

        # 4. Feature count match
        actual = len(features) if features else 0
        if actual == requested_count:
            count_score = 15
        elif actual >= int(requested_count * 0.9):
            count_score = 10
        else:
            count_score = 5
        breakdown["Feature count match"] = count_score
        score += count_score

        # 5. Attribute completeness
        if features and schema:
            expected_fields = {f["name"] for f in schema}
            present_fields = set(features[0][1].keys())
            completeness = len(expected_fields & present_fields) / max(len(expected_fields), 1)
            attr_score = int(10 * completeness)
        else:
            attr_score = 0
        breakdown["Attribute completeness"] = attr_score
        score += attr_score

        # 6. CRS valid
        crs_score = 0
        if crs_authid:
            try:
                crs = QgsCoordinateReferenceSystem(crs_authid)
                crs_score = 10 if crs.isValid() else 0
            except Exception:
                crs_score = 0
        breakdown["CRS valid"] = crs_score
        score += crs_score

        return min(score, 100), breakdown
