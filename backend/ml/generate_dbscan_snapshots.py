"""
Generate a fixed number of precomputed DBSCAN snapshots and save them to
disk as ml/dbscan_snapshots.json, so DBSCANClusterAnimation
(ml/animation/dbscan.py) can build animation frames without re-running
DBSCAN at render time.

Snapshots show how clusters change over TIME, not over epsilon: the CSV's
full occurred_at range is split into N_SNAPSHOTS equal-width, sequential,
non-overlapping time windows. Each snapshot is independent — it only
includes incidents that occurred within its own window, not incidents from
earlier or later windows. eps/min_pts stay fixed per cluster level (street/
neighborhood/district, from cluster_levels in ml/clustering.py) across every
snapshot — only the incident set changes.

Run from backend/ with the venv activated:
    python -m ml.generate_dbscan_snapshots
"""

import json
import os

import pandas as pd

from ml.clustering import cluster_levels, load_csv_incidents_with_time, run_clusters

N_SNAPSHOTS = 5

_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "dbscan_snapshots.json")


def build_snapshots(n_snapshots: int = N_SNAPSHOTS) -> list:
    """Split the CSV's full occurred_at range into n_snapshots sequential,
    non-overlapping time windows and run DBSCAN — at every cluster_levels
    level — on each window's own incidents only. Returns a list of
    {label, window_start, window_end, n_incidents, levels: {level_name: geojson}}
    dicts in time order."""
    incidents = load_csv_incidents_with_time()
    times = pd.to_datetime([inc["occurred_at"] for inc in incidents])
    start, end = times.min(), times.max()
    span = end - start
    edges = [start + span * (i / n_snapshots) for i in range(n_snapshots + 1)]

    snapshots = []
    for i in range(n_snapshots):
        window_start, window_end = edges[i], edges[i + 1]
        is_last = i == n_snapshots - 1
        window_incidents = [
            inc for inc in incidents
            if window_start <= inc["occurred_at"] < window_end
            or (is_last and inc["occurred_at"] == window_end)
        ]
        levels = {
            level_name: run_clusters(
                window_incidents,
                eps=settings["epsilon"],
                min_pts=settings["min_pts"],
                cluster_color=settings["color"],
            )
            for level_name, settings in cluster_levels.items()
        }
        snapshots.append({
            "label": f"{window_start.strftime('%Y-%m-%d %H:%M')} – {window_end.strftime('%Y-%m-%d %H:%M')}",
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "n_incidents": len(window_incidents),
            "levels": levels,
        })
    return snapshots


def main() -> None:
    snapshots = build_snapshots()
    with open(_OUTPUT_PATH, "w") as f:
        json.dump(snapshots, f)
    print(f"Saved {len(snapshots)} DBSCAN snapshots to {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
