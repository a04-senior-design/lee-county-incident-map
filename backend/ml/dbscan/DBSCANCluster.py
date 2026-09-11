
"""
This module defines the DBSCANCluster class, which fits one sklearn DBSCAN
model per entry in `levels` (loosest -> tightest epsilon) against the same
point set, derives a single per-point density_level array (-1 == noise, 0 ==
loosest level, increasing == denser), and builds GeoJSON output for mapping.

It also owns the DBSCAN module's public config and data-loading surface
(cluster_levels, CSV loaders, run_clusters/run_density_clusters) so the whole
DBSCAN module is self-contained under ml/dbscan/ — no separate ml/clustering.py.
See ml/dbscan/dbscan_app.py for a driver/tester script.
"""

import os

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from shapely.geometry import Point, mapping
from shapely.ops import unary_union, transform as shp_transform
from pyproj import Transformer

CLUSTER_COLORS = ["#E63946", "#2A9D8F", "#E9C46A", "#457B9D", "#F4A261"]
NOISE_COLOR = "#AAAAAA"

cluster_levels = {
    "street": {
        "epsilon": 1300,
        "min_pts": 4,
        "color": "#E63946"
    }, "neighborhood": {
        "epsilon": 3000,
        "min_pts": 4,
        "color": "#243092"
    }, "district": {
        "epsilon": 13000,
        "min_pts": 4,
        "color": "#0E6207"
    }
}

_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data",
    "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv",
)


def load_csv_incidents() -> list:
    """Load incidents from the late-paper CSV and return as a list of dicts
    with 'lat' and 'lng' keys, matching the format returned by get_incidents()."""
    df = pd.read_csv(_CSV_PATH).dropna(subset=["lat", "lon"])
    return df[["lat", "lon"]].rename(columns={"lon": "lng"}).to_dict(orient="records")


def load_csv_incidents_with_time() -> list:
    """Load incidents from the late-paper CSV including 'occurred_at' (a
    tz-aware pandas.Timestamp), for time-windowed clustering — see
    ml/generate_dbscan_snapshots.py."""
    df = pd.read_csv(_CSV_PATH, parse_dates=["occurred_at"]).dropna(subset=["lat", "lon", "occurred_at"])
    return df[["lat", "lon", "occurred_at"]].rename(columns={"lon": "lng"}).to_dict(orient="records")


def _project_mappable(incidents: list):
    """Filter out incidents missing lat/lng and project the rest NAD83
    geographic (EPSG:4269) -> NAD83 StatePlane Florida West feet (EPSG:2882).
    Returns (points, lats, lons), or (None, None, None) if nothing is mappable."""
    mappable = [
        inc for inc in incidents
        if inc.get("lat") is not None and inc.get("lng") is not None
    ]
    if not mappable:
        return None, None, None

    lats = np.array([inc["lat"] for inc in mappable], dtype=float)
    lons = np.array([inc["lng"] for inc in mappable], dtype=float)

    to_proj = Transformer.from_crs("EPSG:4269", "EPSG:2882", always_xy=True)
    easting, northing = to_proj.transform(lons, lats)
    points = np.column_stack([easting, northing])

    return points, lats, lons


class DBSCANCluster:
    """Fits one or more (epsilon, min_pts) levels against the same point set
    and derives per-point density levels and GeoJSON output."""

    def __init__(self, points: np.ndarray, levels: list, source_crs: str = "EPSG:2882", target_crs: str = "EPSG:4326"):
        self.points = points
        # loosest (largest epsilon) first, so density_level 0 is the least dense tier
        self.levels = sorted(levels, key=lambda lvl: lvl["epsilon"], reverse=True)
        self.source_crs = source_crs
        self.target_crs = target_crs

        self._labels_per_level = self._fit_dbscan_model()
        self._density_levels = self._compute_density_levels()

    @property
    def labels_per_level(self):
        return self._labels_per_level

    @property
    def density_levels(self):
        return self._density_levels

    @property
    def noise_mask(self):
        return self._density_levels == -1

    def _fit_dbscan_model(self):
        """Fit one DBSCAN model per level, loosest to tightest."""
        return [
            DBSCAN(eps=level["epsilon"], min_samples=level["min_pts"]).fit(self.points).labels_
            for level in self.levels
        ]

    def _compute_density_levels(self):
        """Collapse per-level labels into one -1..len(levels)-1 array; a
        point's final level is the tightest threshold it still clusters under."""
        density_level = np.full(len(self.points), -1, dtype=int)
        for level_index, labels in enumerate(self._labels_per_level):
            density_level[labels != -1] = level_index
        return density_level

    def to_geojson(self, lats: np.ndarray, lons: np.ndarray, cluster_color: str = None) -> dict:
        """Build a GeoJSON FeatureCollection (cluster polygons + points) for a
        single-level fit. `lats`/`lons` are the original (unprojected)
        coordinates, aligned index-for-index with `self.points`."""
        if len(self.levels) != 1:
            raise ValueError("to_geojson() requires exactly one level; use to_density_geojson() for multi-level fits")

        eps = self.levels[0]["epsilon"]
        labels = self._labels_per_level[0]

        noise_mask = labels == -1
        noise_points = [
            {"lat": float(lats[i]), "lng": float(lons[i])}
            for i in range(len(labels))
            if noise_mask[i]
        ]

        to_wgs84 = Transformer.from_crs(self.source_crs, self.target_crs, always_xy=True)

        point_features = []
        for lat, lon, label in zip(lats, lons, labels):
            if label == -1:
                color = NOISE_COLOR
            elif cluster_color is not None:
                color = cluster_color
            else:
                color = CLUSTER_COLORS[int(label) % len(CLUSTER_COLORS)]
            point_features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": {
                    "feature_type": "point",
                    "cluster_id": int(label),
                    "color": color,
                },
            })

        polygon_features = []
        for label in sorted(set(labels) - {-1}):
            mask = labels == label
            color = cluster_color if cluster_color is not None else CLUSTER_COLORS[int(label) % len(CLUSTER_COLORS)]

            cluster_pts = self.points[mask]
            union = unary_union([Point(p).buffer(eps) for p in cluster_pts])
            wgs84_geom = shp_transform(to_wgs84.transform, union)

            polygon_features.append({
                "type": "Feature",
                "geometry": mapping(wgs84_geom),
                "properties": {
                    "feature_type": "polygon",
                    "cluster_id": int(label),
                    "point_count": int(mask.sum()),
                    "color": color,
                },
            })

        return {
            "type": "FeatureCollection",
            "features": polygon_features + point_features,
            "metadata": {
                "n_clusters": len(set(labels) - {-1}),
                "n_noise": int(noise_mask.sum()),
                "n_total": len(labels),
                "eps": eps,
                "min_pts": self.levels[0]["min_pts"],
            },
            "noise_points": noise_points,
        }

    def to_density_geojson(self, lats: np.ndarray, lons: np.ndarray) -> dict:
        """Build a GeoJSON FeatureCollection of points tagged with
        density_level, for multi-level fits (e.g. feeding a KDE module)."""
        features = []
        counts_by_level = {}
        for lat, lon, level in zip(lats, lons, self._density_levels):
            level = int(level)
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": {"feature_type": "point", "density_level": level},
            })
            counts_by_level[level] = counts_by_level.get(level, 0) + 1

        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "n_total": len(self._density_levels),
                "n_noise": counts_by_level.get(-1, 0),
                "n_levels": len(self.levels),
                "counts_by_level": counts_by_level,
            },
        }


def run_clusters(incidents: list, eps: float, min_pts: int, cluster_color: str = None) -> dict:
    """
    Run DBSCAN on geocoded incidents and return a GeoJSON FeatureCollection.

    Parameters
    ----------
    incidents : list of dicts with 'lat' and 'lng' keys (from cache.get_incidents)
    eps       : neighborhood radius in US survey feet (EPSG:2882 units)
    min_pts   : DBSCAN min_samples

    Returns
    -------
    GeoJSON FeatureCollection dict with a top-level 'metadata' key.
    Each feature is a cluster polygon in WGS84 with properties:
        cluster_id, point_count, color
    """
    points, lats, lons = _project_mappable(incidents)
    if points is None:
        return {
            "type": "FeatureCollection",
            "features": [],
            "metadata": {"n_clusters": 0, "n_noise": 0, "n_total": 0},
        }

    cluster = DBSCANCluster(points, levels=[{"epsilon": eps, "min_pts": min_pts}])
    return cluster.to_geojson(lats, lons, cluster_color=cluster_color)


def compute_density_levels(incidents: list, levels: list) -> list:
    """
    Run DBSCAN once per entry in `levels` (each a dict with 'epsilon' and
    'min_pts', e.g. values from `cluster_levels`) and assign every mappable
    incident a single density_level, consumed by the KDE module:

        -1 = noise at every level (never clustered)
         0 = clustered only at the loosest (largest eps) level — least dense
         1 = also clustered at the next-tightest level — denser than 0
         2 = also clustered at the tightest (smallest eps) level — denser than 1
        (and so on for additional levels)

    Levels are processed loosest → tightest regardless of input order, so a
    point's final density_level is the tightest threshold it still belongs
    to a cluster under.

    Returns a list of {"lat", "lng", "density_level"} dicts, one per
    mappable incident (points missing lat/lng are dropped).
    """
    points, lats, lons = _project_mappable(incidents)
    if points is None or not levels:
        return []

    cluster = DBSCANCluster(points, levels=levels)
    return [
        {"lat": float(lat), "lng": float(lon), "density_level": int(level)}
        for lat, lon, level in zip(lats, lons, cluster.density_levels)
    ]


def run_density_clusters(incidents: list, levels: list) -> dict:
    """
    Multi-level DBSCAN for the KDE module: wraps compute_density_levels() and
    returns a GeoJSON FeatureCollection of points, each carrying a
    'density_level' property (-1 noise … len(levels)-1 densest).
    """
    points, lats, lons = _project_mappable(incidents)
    if points is None or not levels:
        return {
            "type": "FeatureCollection",
            "features": [],
            "metadata": {"n_total": 0, "n_noise": 0, "n_levels": len(levels), "counts_by_level": {}},
        }

    cluster = DBSCANCluster(points, levels=levels)
    return cluster.to_density_geojson(lats, lons)