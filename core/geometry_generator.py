# -*- coding: utf-8 -*-
"""Geometry generation math (Points, Lines, Polygons, Networks, Voronoi) for GeoData Forge."""
import math
import random
from qgis.core import (
    QgsPointXY,
    QgsGeometry,
    QgsRectangle,
    QgsLineString,
    QgsPoint,
    QgsWkbTypes
)

_MST_SEGMENT_CAP = 400  # Max nodes per MST segment to avoid O(N^2) freeze


class GeometryGenerator:
    """Mathematical generator for Point, Line, and Polygon shapes."""

    @staticmethod
    def generate_uniform_points(xmin, ymin, xmax, ymax, count, seed, boundary_geom=None):
        """Generates uniformly distributed points within an extent."""
        rnd = random.Random(seed)
        points = []
        max_attempts = count * 100
        attempts = 0
        bbox = boundary_geom.boundingBox() if boundary_geom else None
        while len(points) < count and attempts < max_attempts:
            attempts += 1
            x = rnd.uniform(xmin, xmax)
            y = rnd.uniform(ymin, ymax)
            pt = QgsPointXY(x, y)
            if boundary_geom:
                in_x_bound = bbox.xMinimum() <= x <= bbox.xMaximum()
                in_y_bound = bbox.yMinimum() <= y <= bbox.yMaximum()
                if not (in_x_bound and in_y_bound):
                    continue
                if not boundary_geom.contains(QgsGeometry.fromPointXY(pt)):
                    continue
            points.append(pt)
        return points

    @staticmethod
    def generate_clustered_points(xmin, ymin, xmax, ymax, count, seed,
                                  boundary_geom=None, num_clusters=5):
        """Generates Gaussian clustered points around hub centers."""
        rnd = random.Random(seed)
        points = []
        width = xmax - xmin
        height = ymax - ymin
        centers = []
        c_attempts = 0
        bbox = boundary_geom.boundingBox() if boundary_geom else None
        while len(centers) < num_clusters and c_attempts < num_clusters * 20:
            c_attempts += 1
            cx = rnd.uniform(xmin + width * 0.1, xmax - width * 0.1)
            cy = rnd.uniform(ymin + height * 0.1, ymax - height * 0.1)
            c_pt = QgsPointXY(cx, cy)
            if boundary_geom:
                if not boundary_geom.contains(QgsGeometry.fromPointXY(c_pt)):
                    continue
            centers.append(c_pt)
        if not centers:
            centers = [QgsPointXY(xmin + width / 2.0, ymin + height / 2.0)]
        stddev_x = width * 0.05
        stddev_y = height * 0.05
        max_attempts = count * 100
        attempts = 0
        while len(points) < count and attempts < max_attempts:
            attempts += 1
            center = rnd.choice(centers)
            x = rnd.gauss(center.x(), stddev_x)
            y = rnd.gauss(center.y(), stddev_y)
            pt = QgsPointXY(x, y)
            if boundary_geom:
                in_x_bound = bbox.xMinimum() <= x <= bbox.xMaximum()
                in_y_bound = bbox.yMinimum() <= y <= bbox.yMaximum()
                if not (in_x_bound and in_y_bound):
                    continue
                if not boundary_geom.contains(QgsGeometry.fromPointXY(pt)):
                    continue
            points.append(pt)
        return points

    @staticmethod
    def generate_poisson_disc_points(xmin, ymin, xmax, ymax, count, seed,
                                     min_dist, boundary_geom=None):
        """Generates points using Bridson's Poisson Disc Sampling algorithm."""
        rnd = random.Random(seed)
        width = xmax - xmin
        height = ymax - ymin
        if min_dist <= 0 or min_dist > max(width, height):
            return GeometryGenerator.generate_uniform_points(
                xmin, ymin, xmax, ymax, count, seed, boundary_geom)
        cell_size = min_dist / math.sqrt(2)
        grid_width = int(math.ceil(width / cell_size))
        grid_height = int(math.ceil(height / cell_size))
        grid = {}
        active_list = []
        points = []
        bbox = boundary_geom.boundingBox() if boundary_geom else None

        def get_grid_coords(pt):
            return (int((pt.x() - xmin) / cell_size),
                    int((pt.y() - ymin) / cell_size))

        def is_valid_candidate(pt):
            if not (xmin <= pt.x() <= xmax and ymin <= pt.y() <= ymax):
                return False
            if boundary_geom:
                in_x_bound = bbox.xMinimum() <= pt.x() <= bbox.xMaximum()
                in_y_bound = bbox.yMinimum() <= pt.y() <= bbox.yMaximum()
                if not (in_x_bound and in_y_bound):
                    return False
                if not boundary_geom.contains(QgsGeometry.fromPointXY(pt)):
                    return False
            gx, gy = get_grid_coords(pt)
            for nx in range(max(0, gx - 2), min(grid_width, gx + 3)):
                for ny in range(max(0, gy - 2), min(grid_height, gy + 3)):
                    idx = grid.get((nx, ny))
                    if idx is not None:
                        other = points[idx]
                        dist = math.sqrt(
                            (pt.x() - other.x()) ** 2 + (pt.y() - other.y()) ** 2)
                        if dist < min_dist:
                            return False
            return True

        start_pt = None
        for _ in range(100):
            candidate = QgsPointXY(rnd.uniform(xmin, xmax), rnd.uniform(ymin, ymax))
            if is_valid_candidate(candidate):
                start_pt = candidate
                break
        if start_pt is None:
            return GeometryGenerator.generate_uniform_points(
                xmin, ymin, xmax, ymax, count, seed, boundary_geom)
        points.append(start_pt)
        active_list.append(0)
        gx, gy = get_grid_coords(start_pt)
        grid[(gx, gy)] = 0
        max_attempts = count * 20
        attempts = 0
        while active_list and len(points) < count and attempts < max_attempts:
            attempts += 1
            active_idx = rnd.choice(range(len(active_list)))
            ref_pt = points[active_list[active_idx]]
            found = False
            for _ in range(30):
                angle = rnd.uniform(0, 2 * math.pi)
                radius = rnd.uniform(min_dist, 2 * min_dist)
                candidate = QgsPointXY(
                    ref_pt.x() + radius * math.cos(angle),
                    ref_pt.y() + radius * math.sin(angle)
                )
                if is_valid_candidate(candidate):
                    new_idx = len(points)
                    points.append(candidate)
                    active_list.append(new_idx)
                    cgx, cgy = get_grid_coords(candidate)
                    grid[(cgx, cgy)] = new_idx
                    found = True
                    break
            if not found:
                active_list.pop(active_idx)
        if len(points) > count:
            points = points[:count]
        elif len(points) < count:
            extra = GeometryGenerator.generate_uniform_points(
                xmin, ymin, xmax, ymax, count - len(points), seed + 1, boundary_geom)
            points.extend(extra)
        return points

    @staticmethod
    def generate_random_paths(xmin, ymin, xmax, ymax, count, seed,
                              boundary_geom=None, segments=4):
        """Generates random walk lines (paths) inside bounds."""
        rnd = random.Random(seed)
        lines = []
        width = xmax - xmin
        height = ymax - ymin
        step_limit = min(width, height) * 0.15
        max_attempts = count * 50
        attempts = 0
        bbox = boundary_geom.boundingBox() if boundary_geom else None
        while len(lines) < count and attempts < max_attempts:
            attempts += 1
            sx = rnd.uniform(xmin, xmax)
            sy = rnd.uniform(ymin, ymax)
            pt = QgsPointXY(sx, sy)
            if boundary_geom:
                in_x_bound = bbox.xMinimum() <= sx <= bbox.xMaximum()
                in_y_bound = bbox.yMinimum() <= sy <= bbox.yMaximum()
                if not (in_x_bound and in_y_bound):
                    continue
                if not boundary_geom.contains(QgsGeometry.fromPointXY(pt)):
                    continue
            path_coords = [pt]
            curr_pt = pt
            for _ in range(segments):
                angle = rnd.uniform(0, 2 * math.pi)
                length = rnd.uniform(step_limit * 0.3, step_limit)
                nx = curr_pt.x() + length * math.cos(angle)
                ny = curr_pt.y() + length * math.sin(angle)
                next_pt = QgsPointXY(nx, ny)
                if boundary_geom:
                    in_nx_bound = bbox.xMinimum() <= nx <= bbox.xMaximum()
                    in_ny_bound = bbox.yMinimum() <= ny <= bbox.yMaximum()
                    if not (in_nx_bound and in_ny_bound):
                        break
                    if not boundary_geom.contains(QgsGeometry.fromPointXY(next_pt)):
                        break
                path_coords.append(next_pt)
                curr_pt = next_pt
            if len(path_coords) > 1:
                ls = QgsLineString([QgsPoint(p.x(), p.y()) for p in path_coords])
                lines.append(QgsGeometry(ls))
        return lines

    @staticmethod
    def generate_mst_networks(xmin, ymin, xmax, ymax, count, seed, boundary_geom=None):
        """Generates connected lines as Minimum Spanning Tree network segments.

        Caps each MST at _MST_SEGMENT_CAP nodes to avoid O(N^2) freeze.
        For large counts, generates multiple linked sub-networks.
        """
        all_lines = []
        remaining = count
        seg_seed = seed
        while remaining > 0:
            seg_count = min(remaining, _MST_SEGMENT_CAP)
            points = GeometryGenerator.generate_uniform_points(
                xmin, ymin, xmax, ymax, seg_count + 1, seg_seed, boundary_geom)
            if len(points) < 2:
                break
            edges = []
            n = len(points)
            for i in range(n):
                for j in range(i + 1, n):
                    pi, pj = points[i], points[j]
                    dist = math.sqrt((pi.x() - pj.x()) ** 2 + (pi.y() - pj.y()) ** 2)
                    edges.append((dist, i, j))
            edges.sort()
            parent = list(range(n))

            def find(u):
                while parent[u] != u:
                    parent[u] = parent[parent[u]]
                    u = parent[u]
                return u

            def union(u, v):
                ru, rv = find(u), find(v)
                if ru != rv:
                    parent[ru] = rv
                    return True
                return False

            seg_lines = []
            for dist, u, v in edges:
                if union(u, v):
                    pu, pv = points[u], points[v]
                    ls = QgsLineString(
                        [QgsPoint(pu.x(), pu.y()), QgsPoint(pv.x(), pv.y())])
                    seg_lines.append(QgsGeometry(ls))
                    if len(seg_lines) >= seg_count:
                        break
            all_lines.extend(seg_lines)
            remaining -= len(seg_lines)
            seg_seed += 1
        return all_lines

    @staticmethod
    def generate_star_polygons(xmin, ymin, xmax, ymax, count, seed,
                               boundary_geom=None, num_vertices=6):
        """Generates valid star-convex polygons to prevent self-intersections."""
        rnd = random.Random(seed)
        polygons = []
        width = xmax - xmin
        height = ymax - ymin
        max_radius = min(width, height) * 0.05
        min_radius = max_radius * 0.3
        max_attempts = count * 100
        attempts = 0
        bbox = boundary_geom.boundingBox() if boundary_geom else None
        while len(polygons) < count and attempts < max_attempts:
            attempts += 1
            cx = rnd.uniform(xmin, xmax)
            cy = rnd.uniform(ymin, ymax)
            center = QgsPointXY(cx, cy)
            if boundary_geom:
                in_cx_bound = bbox.xMinimum() <= cx <= bbox.xMaximum()
                in_cy_bound = bbox.yMinimum() <= cy <= bbox.yMaximum()
                if not (in_cx_bound and in_cy_bound):
                    continue
                if not boundary_geom.contains(QgsGeometry.fromPointXY(center)):
                    continue
            angles = sorted([
                (2 * math.pi * i / num_vertices) + rnd.uniform(-0.1, 0.1)
                for i in range(num_vertices)
            ])
            pts = []
            polygon_valid = True
            for angle in angles:
                r = rnd.uniform(min_radius, max_radius)
                vx = cx + r * math.cos(angle)
                vy = cy + r * math.sin(angle)
                v_pt = QgsPointXY(vx, vy)
                if boundary_geom:
                    if not boundary_geom.contains(QgsGeometry.fromPointXY(v_pt)):
                        polygon_valid = False
                        break
                pts.append(QgsPoint(v_pt.x(), v_pt.y()))
            if polygon_valid and len(pts) >= 3:
                pts.append(pts[0])
                poly_geom = QgsGeometry.fromPolygonXY(
                    [[QgsPointXY(p.x(), p.y()) for p in pts]])
                if poly_geom.isGeosValid():
                    polygons.append(poly_geom)
        return polygons

    @staticmethod
    def generate_voronoi_parcels(xmin, ymin, xmax, ymax, count, seed, boundary_geom=None):
        """Generates Voronoi cells representing natural property parcels."""
        seed_count = int(count * 1.2) + 5
        points = GeometryGenerator.generate_uniform_points(
            xmin, ymin, xmax, ymax, seed_count, seed, boundary_geom)
        if len(points) < 3:
            return GeometryGenerator.generate_star_polygons(
                xmin, ymin, xmax, ymax, count, seed, boundary_geom)
        multipoint_geom = QgsGeometry.fromMultiPointXY(points)
        # Pad by 10% of extent dimensions
        pad_x = (xmax - xmin) * 0.1
        pad_y = (ymax - ymin) * 0.1
        extent_rect = QgsRectangle(xmin - pad_x, ymin - pad_y,
                                   xmax + pad_x, ymax + pad_y)
        extent_geom = QgsGeometry.fromRect(extent_rect)
        voronoi_collection = multipoint_geom.voronoiDiagram(extent_geom)
        if voronoi_collection.isEmpty():
            return GeometryGenerator.generate_star_polygons(
                xmin, ymin, xmax, ymax, count, seed, boundary_geom)
        clip_boundary = (boundary_geom if boundary_geom
                         else QgsGeometry.fromRect(
                             QgsRectangle(xmin, ymin, xmax, ymax)))
        geom_parts = voronoi_collection.asGeometryCollection()
        center_x = (xmin + xmax) / 2.0
        center_y = (ymin + ymax) / 2.0

        def cell_distance(cell):
            bb = cell.boundingBox()
            cx = (bb.xMinimum() + bb.xMaximum()) / 2.0
            cy = (bb.yMinimum() + bb.yMaximum()) / 2.0
            return (cx - center_x) ** 2 + (cy - center_y) ** 2

        sorted_cells = sorted(geom_parts, key=cell_distance)
        parcels = []
        for cell in sorted_cells:
            if len(parcels) >= count:
                break
            clipped = cell.intersection(clip_boundary)
            is_poly = clipped.type() == QgsWkbTypes.PolygonGeometry
            if not clipped.isEmpty() and clipped.isGeosValid() and is_poly:
                parcels.append(clipped)
        if len(parcels) < count:
            extra = count - len(parcels)
            extra_polys = GeometryGenerator.generate_star_polygons(
                xmin, ymin, xmax, ymax, extra, seed + 1, boundary_geom)
            parcels.extend(extra_polys)
        return parcels
