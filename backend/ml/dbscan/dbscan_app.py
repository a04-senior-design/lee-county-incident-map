"""
Driver/tester script for DBSCANCluster — loads incidents, runs a single-level
fit and a multi-level (street/neighborhood/district) density fit, prints
diagnostics so DBSCANCluster's output can be validated against the
pre-refactor behavior (run_clusters / compute_density_levels), and renders
the single-level fit as an interactive folium map — the DBSCAN-side
equivalent of kde_app.py's folium.raster_layers.ImageOverlay map, except the
DBSCAN output is vector (cluster polygons + points) rather than a raster PNG.

Incidents are loaded with occurred_at so this stays in parity with the
time-windowed loading ml/generate_dbscan_snapshots.py relies on for the DBSCAN
cluster animation — this script doesn't window by time itself, it just proves
DBSCANCluster works against the same incident set/shape that pipeline uses.

Run from backend/ with the venv activated:
    python -m ml.dbscan.dbscan_app
"""

import os

import folium
import numpy as np
from pyproj import Transformer

from .DBSCANCluster import DBSCANCluster, cluster_levels, load_csv_incidents_with_time

# single-level fit, for comparison against DBSCANCluster.run_clusters
SINGLE_LEVEL = cluster_levels["district"]

_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output")
_MAP_OUTPUT = os.path.join(_OUTPUT_DIR, "dbscan_cluster_map.html")


def load_points():
    """Project incidents to EPSG:2882 x/y for DBSCAN, returning the points
    alongside the original lat/lng/occurred_at (aligned index-for-index)."""
    incidents = load_csv_incidents_with_time()
    lats = np.array([inc["lat"] for inc in incidents], dtype=float)
    lons = np.array([inc["lng"] for inc in incidents], dtype=float)
    occurred_at = [inc["occurred_at"] for inc in incidents]

    to_proj = Transformer.from_crs("EPSG:4269", "EPSG:2882", always_xy=True)
    easting, northing = to_proj.transform(lons, lats)
    points = np.column_stack([easting, northing])

    return points, lats, lons, occurred_at


def build_folium_map(geojson: dict, lats: np.ndarray, lons: np.ndarray) -> folium.Map:
    """Render a single-level DBSCAN GeoJSON FeatureCollection (from
    DBSCANCluster.to_geojson) as a folium map: cluster hull polygons plus
    colored incident points, centered on the incidents themselves."""
    center = [float(lats.mean()), float(lons.mean())]
    m = folium.Map(location=center, zoom_start=11)

    polygons = [f for f in geojson["features"] if f["properties"]["feature_type"] == "polygon"]
    points = [f for f in geojson["features"] if f["properties"]["feature_type"] == "point"]

    if polygons:
        folium.GeoJson(
            {"type": "FeatureCollection", "features": polygons},
            style_function=lambda feature: {
                "fillColor": feature["properties"]["color"],
                "color": feature["properties"]["color"],
                "fillOpacity": 0.15,
                "weight": 1.5,
            },
        ).add_to(m)

    for feature in points:
        lon, lat = feature["geometry"]["coordinates"]
        color = feature["properties"]["color"]
        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            tooltip=f"Cluster {feature['properties']['cluster_id']}",
        ).add_to(m)

    return m


def main() -> None:
    points, lats, lons, occurred_at = load_points()
    print(f"loaded {len(points)} incidents spanning {min(occurred_at)} to {max(occurred_at)}")

    # single-level fit
    single = DBSCANCluster(points, levels=[SINGLE_LEVEL])
    single_geojson = single.to_geojson(lats, lons, cluster_color=SINGLE_LEVEL["color"])
    print(
        f"single-level ({SINGLE_LEVEL['epsilon']} ft / {SINGLE_LEVEL['min_pts']} pts): "
        f"{single_geojson['metadata']['n_clusters']} clusters, "
        f"{single_geojson['metadata']['n_noise']} noise points"
    )

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    build_folium_map(single_geojson, lats, lons).save(_MAP_OUTPUT)
    print(f"Folium map saved to {os.path.abspath(_MAP_OUTPUT)}")

    # multi-level density fit, e.g. as consumed by a future KDE integration
    multi = DBSCANCluster(points, levels=list(cluster_levels.values()))
    density_geojson = multi.to_density_geojson(lats, lons)
    print(f"density metadata: {density_geojson['metadata']}")


if __name__ == "__main__":
    main()
