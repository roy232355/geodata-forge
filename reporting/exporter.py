# -*- coding: utf-8 -*-
"""Multi-format vector exporter for GeoData Forge (GeoPackage, GeoJSON, Shapefile, CSV)."""
import csv
import json
import os
from qgis.core import (
    QgsFields,
    QgsField,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsWkbTypes,
    QgsProject
)
from qgis.PyQt.QtCore import QVariant


class Exporter:
    """Handles export of generated geometries and attributes to GIS files."""

    @staticmethod
    def _build_qgs_fields(schema):
        """Builds a QgsFields object from a schema list."""
        fields = QgsFields()
        for field_def in schema:
            name = field_def["name"]
            type_str = field_def["type"]
            if type_str == "SequentialID" or (
                    type_str == "Numeric" and field_def.get("integer")):
                q_type = QVariant.Int
            elif type_str in ("Numeric", "Year"):
                q_type = QVariant.Double
            else:
                q_type = QVariant.String
            fields.append(QgsField(name, q_type))
        return fields

    @staticmethod
    def _geom_type_to_wkb(geom_type_str):
        """Maps string geometry type to QgsWkbTypes enum."""
        mapping = {
            "Point": QgsWkbTypes.Point,
            "Line": QgsWkbTypes.LineString,
            "Polygon": QgsWkbTypes.Polygon,
        }
        if geom_type_str not in mapping:
            raise ValueError(f"Unsupported geometry type: {geom_type_str}")
        return mapping[geom_type_str]

    @staticmethod
    def _safe_remove(output_path):
        """Renames existing file to .bak before writing; caller removes .bak on success."""
        bak_path = output_path + ".bak"
        if os.path.exists(output_path):
            try:
                if os.path.exists(bak_path):
                    os.remove(bak_path)
                os.rename(output_path, bak_path)
            except Exception as e:
                raise IOError(
                    f"The output file '{os.path.basename(output_path)}' is currently "
                    f"in use or locked. Please remove the layer from the Layers panel "
                    f"and try again. (Detail: {str(e)})"
                )
        return bak_path

    @staticmethod
    def _cleanup_bak(bak_path):
        """Removes backup file after successful write."""
        if bak_path and os.path.exists(bak_path):
            try:
                os.remove(bak_path)
            except Exception:
                pass

    @staticmethod
    def export_to_gpkg(output_path, layer_name, crs_authid, geom_type_str, schema, features):
        """Creates a GeoPackage and writes features to it."""
        crs = QgsCoordinateReferenceSystem(crs_authid)
        if not crs.isValid():
            raise ValueError(f"Invalid Coordinate Reference System: {crs_authid}")

        bak_path = Exporter._safe_remove(output_path)
        geometry_type = Exporter._geom_type_to_wkb(geom_type_str)
        fields = Exporter._build_qgs_fields(schema)

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = layer_name
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        options.fileEncoding = "UTF-8"

        transform_context = QgsProject.instance().transformContext()
        writer = QgsVectorFileWriter.create(
            output_path, fields, geometry_type, crs, transform_context, options
        )
        if writer is None or writer.hasError() != QgsVectorFileWriter.NoError:
            err_msg = writer.errorMessage() if writer else "Initialization Error"
            raise IOError(f"Failed to create GeoPackage writer: {err_msg}")

        try:
            for geom, attribs in features:
                if geom is None or geom.isEmpty():
                    continue
                feature = QgsFeature(fields)
                feature.setGeometry(geom)
                for field_def in schema:
                    name = field_def["name"]
                    feature.setAttribute(name, attribs.get(name))
                writer.addFeature(feature)
        finally:
            del writer

        Exporter._cleanup_bak(bak_path)
        return True

    @staticmethod
    def export_to_geojson(output_path, schema, features):
        """Exports features as a RFC 7946 GeoJSON FeatureCollection."""
        bak_path = Exporter._safe_remove(output_path)
        features_json = []
        for geom, attrs in features:
            if geom is None or geom.isEmpty():
                continue
            geom_json = json.loads(geom.asJson())
            properties = {field_def["name"]: attrs.get(field_def["name"]) for field_def in schema}
            features_json.append({
                "type": "Feature",
                "geometry": geom_json,
                "properties": properties
            })
        collection = {"type": "FeatureCollection", "features": features_json}
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(collection, f, indent=2, ensure_ascii=False)
        Exporter._cleanup_bak(bak_path)
        return True

    @staticmethod
    def export_to_shapefile(output_path, layer_name, crs_authid, geom_type_str,
                            schema, features):
        """Exports features to an ESRI Shapefile (.shp) using safe backup/restore pattern."""
        crs = QgsCoordinateReferenceSystem(crs_authid)
        if not crs.isValid():
            raise ValueError(f"Invalid Coordinate Reference System: {crs_authid}")

        geometry_type = Exporter._geom_type_to_wkb(geom_type_str)

        # Shapefile field names: max 10 chars, bulletproof collision resolver
        truncated_schema = []
        seen_names = set()
        for field_def in schema:
            fd = dict(field_def)
            name = fd["name"][:10]
            if name in seen_names:
                suffix_counter = 1
                while True:
                    suffix = str(suffix_counter)
                    allowed_len = 10 - len(suffix)
                    candidate_name = fd["name"][:allowed_len] + suffix
                    if candidate_name not in seen_names:
                        name = candidate_name
                        break
                    suffix_counter += 1
            seen_names.add(name)
            fd["_shp_name"] = name
            truncated_schema.append(fd)

        fields = QgsFields()
        for field_def in truncated_schema:
            type_str = field_def["type"]
            if type_str == "SequentialID" or (
                    type_str == "Numeric" and field_def.get("integer")):
                q_type = QVariant.Int
            elif type_str in ("Numeric", "Year"):
                q_type = QVariant.Double
            else:
                q_type = QVariant.String
            fields.append(QgsField(field_def["_shp_name"], q_type))

        base = os.path.splitext(output_path)[0]
        extensions = [".shp", ".shx", ".dbf", ".prj", ".cpg"]
        bak_files = {}  # original_path -> bak_path

        try:
            for ext in extensions:
                candidate = base + ext
                if os.path.exists(candidate):
                    bak_path = candidate + ".bak"
                    if os.path.exists(bak_path):
                        os.remove(bak_path)
                    os.rename(candidate, bak_path)
                    bak_files[candidate] = bak_path
        except Exception as e:
            # Rollback: restore any files we already renamed
            for orig, bak in bak_files.items():
                try:
                    if os.path.exists(orig):
                        os.remove(orig)
                    os.rename(bak, orig)
                except Exception:
                    pass
            raise IOError(
                f"One or more shapefile components of '{os.path.basename(output_path)}' "
                f"are currently in use or locked. Please remove the layer from the Layers panel "
                f"and try again. (Detail: {str(e)})"
            )

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"
        options.layerName = layer_name
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        options.fileEncoding = "UTF-8"

        transform_context = QgsProject.instance().transformContext()
        writer = QgsVectorFileWriter.create(
            output_path, fields, geometry_type, crs, transform_context, options
        )
        if writer is None or writer.hasError() != QgsVectorFileWriter.NoError:
            err_msg = writer.errorMessage() if writer else "Initialization Error"
            # Rollback: restore backups
            for orig, bak in bak_files.items():
                try:
                    if os.path.exists(orig):
                        os.remove(orig)
                    os.rename(bak, orig)
                except Exception:
                    pass
            raise IOError(f"Failed to create Shapefile writer: {err_msg}")

        writer_deleted = False
        try:
            for geom, attribs in features:
                if geom is None or geom.isEmpty():
                    continue
                feature = QgsFeature(fields)
                feature.setGeometry(geom)
                for i, field_def in enumerate(truncated_schema):
                    orig_name = field_def["name"]
                    feature.setAttribute(i, attribs.get(orig_name))
                writer.addFeature(feature)
        except Exception as e:
            del writer
            writer_deleted = True
            for orig, bak in bak_files.items():
                try:
                    if os.path.exists(orig):
                        os.remove(orig)
                    os.rename(bak, orig)
                except Exception:
                    pass
            raise e
        finally:
            if not writer_deleted:
                del writer

        # Success: clean up backups
        for bak in bak_files.values():
            if os.path.exists(bak):
                try:
                    os.remove(bak)
                except Exception:
                    pass
        return True

    @staticmethod
    def export_to_csv(output_path, schema, features):
        """Exports attribute table (no geometry) to UTF-8 CSV."""
        bak_path = Exporter._safe_remove(output_path)
        field_names = [f["name"] for f in schema]
        with open(output_path, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names, extrasaction="ignore")
            writer.writeheader()
            for _, attrs in features:
                writer.writerow(attrs)
        Exporter._cleanup_bak(bak_path)
        return True
