"""
DBSCANClusterAnimation — plays back precomputed DBSCAN snapshots (see
ml/generate_dbscan_snapshots.py) as animation frames, one independent time
window per frame, using the same MapAnimation mechanics as CountdownAnimation.

Each snapshot holds results for 3 fixed cluster_levels (street/
neighborhood/district) computed only from incidents within that window, so
a frame overlays all 3 levels — largest first so tighter clusters stay
visible on top. Each level's GeoJSON FeatureCollection (from
ml.clustering.run_clusters) is split into polygon features (cluster hull
outlines) and point features (individual incidents), rendered as a
VectorFrame so playback reuses MapAnimation's play/pause/scrub control
unchanged.
"""

import json
import os

import folium

from .base import Frame, MapAnimation, VectorFrame

LEE_COUNTY_CENTER = (26.56, -81.87)

# Largest radius first so smaller, tighter levels are drawn on top and stay visible.
_LEVEL_RENDER_ORDER = ["district", "neighborhood", "street"]

_SNAPSHOTS_PATH = os.path.join(os.path.dirname(__file__), "..", "dbscan_snapshots.json")
_OUTPUT_HTML = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", "dbscan_cluster_animation.html")


def _load_snapshots(path: str) -> list:
    with open(path) as f:
        return json.load(f)


def _level_layer_children(geojson: dict) -> list:
    """Build folium children for one cluster level: cluster polygons plus colored incident points."""
    polygons = [f for f in geojson["features"] if f["properties"]["feature_type"] == "polygon"]
    points = [f for f in geojson["features"] if f["properties"]["feature_type"] == "point"]

    children = []
    if polygons:
        children.append(
            folium.GeoJson(
                {"type": "FeatureCollection", "features": polygons},
                style_function=lambda feature: {
                    "fillColor": feature["properties"]["color"],
                    "color": feature["properties"]["color"],
                    "fillOpacity": 0.15,
                    "weight": 1.5,
                },
            )
        )
    for feature in points:
        lon, lat = feature["geometry"]["coordinates"]
        color = feature["properties"]["color"]
        children.append(
            folium.CircleMarker(
                location=[lat, lon],
                radius=4,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
            )
        )
    return children


class DBSCANClusterAnimation(MapAnimation):
    """Plays back a sequence of precomputed, independent DBSCAN time-window snapshots, one per frame."""

    def __init__(
        self,
        snapshots_path: str = _SNAPSHOTS_PATH,
        center: tuple = LEE_COUNTY_CENTER,
        zoom_start: int = 11,
        interval_seconds: float = 2.0,
    ) -> None:
        self._snapshots = _load_snapshots(snapshots_path)
        super().__init__(
            frame_count=len(self._snapshots),
            interval_seconds=interval_seconds,
            center=center,
            zoom_start=zoom_start,
        )

    def build_frame(self, index: int) -> Frame:
        snapshot = self._snapshots[index]
        children = []
        for level_name in _LEVEL_RENDER_ORDER:
            children.extend(_level_layer_children(snapshot["levels"][level_name]))
        label = f"{snapshot['label']} ({snapshot['n_incidents']} incidents)"
        return VectorFrame(label=label, children=children)


def main() -> None:
    animation = DBSCANClusterAnimation()
    written = animation.to_html(_OUTPUT_HTML)
    print(f"DBSCAN cluster animation saved to {os.path.abspath(written)}")


if __name__ == "__main__":
    main()
