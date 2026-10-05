"""
Generate precomputed DBSCAN snapshots and save them to disk as
ml/dbscan_snapshots.json, so DBSCANClusterAnimation (ml/animation/dbscan.py)
can build animation frames without re-running DBSCAN at render time.

Snapshots show how clusters change over TIME, not over epsilon: a window of
`window_length` slides across [start_date, end_date] in steps of
`time_step`. `time_step` is independent of `window_length` — it can be
shorter (overlapping windows, sharing some incidents), equal to it
(sequential, non-overlapping — the old fixed N_SNAPSHOTS behavior), or
longer (gaps between windows, e.g. one window per February across the last
5 years: window_length=~1 month, time_step=1 year via
pandas.DateOffset(years=1)). Each snapshot only includes incidents that fall
inside its own window. eps/min_pts default to the fixed per-level values in
cluster_levels (street/neighborhood/district, from
ml/dbscan/DBSCANCluster.py) across every snapshot, but callers may override
which levels run and their eps/min_pts via `level_configs` (e.g. per-level
toggles/sliders from the frontend) — only the incident set changes
otherwise.

When a user does not enter a window size or time step, default is the
time between the start date and the end date.

Run from backend/ with the venv activated:
    python -m ml.generate_dbscan_snapshots
    python -m ml.generate_dbscan_snapshots --start-date 2024-01-01 --end-date 2026-01-01 \
        --window-length 30D --time-step 7D
"""

import argparse
import json
import os
import time
import csv
import numpy as np
from pandas.tseries.frequencies import to_offset
import tempfile

from ml.time_windows import build_time_windows
from ml.dbscan.DBSCANCluster import cluster_levels, run_clusters, compute_density_levels, run_clusters_from_points, compute_density_levels_from_points

DEFAULT_N_WINDOWS = 1

_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "dbscan_snapshots.json")

"""Uncomment this to use real tmp folder"""
# Get system temp directory (/tmp on macOS/Linux)
# temp_dir = tempfile.gettempdir()
# csv_path = os.path.join(temp_dir, "userID_dbscan.csv")
csv_path = "userID_dbscan.csv"

def build_snapshots(
    start_date=None,
    end_date=None,
    window_length=None,
    time_step=None,
    level_configs=None,
) -> list:
    """Slide a window of `window_length` across [start_date, end_date] in
    steps of `time_step` and run DBSCAN — at every level in `level_configs` —
    on each window's own incidents only.  

    `time_step` may be shorter than `window_length` (overlapping windows),
    equal to it (sequential, non-overlapping), or longer than it (gaps
    between windows). Both accept anything addable to a pandas.Timestamp —
    a pandas.Timedelta/DateOffset string ("30D") or a pandas.DateOffset
    instance (e.g. pandas.DateOffset(years=1) for calendar-based steps like
    "every February").

    Windows come from ml.time_windows.build_time_windows(), which applies
    the defaults: start_date/end_date default to the CSV's earliest/latest
    occurred_at; window_length defaults to the whole [start_date, end_date]
    range (a single window, i.e. one DBSCAN snapshot rather than an
    animation); time_step defaults to window_length (non-overlapping
    windows). Leaving window_length blank also writes that single window's
    per-incident density levels to userID_dbscan.csv.

    `level_configs` is a {level_name: {epsilon, min_pts, color}} dict
    overriding which levels run and their parameters (e.g. from user-facing
    per-level toggles/sliders); defaults to `cluster_levels`
    (street/neighborhood/district) when omitted.

    Returns a list of
    {label, window_start, window_end, n_incidents, levels: {level_name: geojson}}
    dicts in time order.
    """
    level_configs = level_configs if level_configs is not None else cluster_levels
    only_one_frame = window_length is None
    windows = build_time_windows(start_date, end_date, window_length, time_step)
    
    start_time = time.perf_counter() # start timer
    
    snapshots = []
    seen_ids = set()
    density_incidents = [] # incidents for the userID_dbscan.csv write; filled only when only_one_frame

    for window in windows:
        window_start = window["window_start"]
        window_end = window["window_end"]
        window_incidents = window["incidents"]
    

        if only_one_frame:
            for incident in window_incidents:
                if id(incident) not in seen_ids:
                    seen_ids.add(id(incident))
                    density_incidents.append(incident)
                 
        levels = {
            level_name: run_clusters(
                window_incidents,
                eps=settings["epsilon"],
                min_pts=settings["min_pts"],
                cluster_color=settings["color"],
            )
            for level_name, settings in level_configs.items()
        }
        snapshots.append({
            "label": f"{window_start.strftime('%Y-%m-%d %H:%M')} – {window_end.strftime('%Y-%m-%d %H:%M')}",
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "n_incidents": len(window_incidents),
            "levels": levels,
        })
    
    end_time = time.perf_counter()
    print(f"DBSCAN snapshot execution time: {(end_time - start_time):.6f} seconds")
    
    # write the cluster density levels
    if only_one_frame:
        densities = compute_density_levels(density_incidents, list(level_configs.values()))
        with open(csv_path, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["lat", "lng", "cluster_density_level"])
            writer.writerows((row["lat"], row["lng"], row["density_level"]) for row in densities)
    
    return snapshots

def build_snapshots_from_points(
    points: np.ndarray,
    level_configs=None,
) -> list:
    """Run DBSCAN — at every level in `level_configs` — directly on the provided

    coordinate points.

    `level_configs` is a {level_name: {epsilon, min_pts, color}} dict
    overriding which levels run and their parameters; defaults to `cluster_levels`
    when omitted.

    Returns a list containing a single snapshot dict:
    [{label, n_incidents, levels: {level_name: geojson}}]
    """
    level_configs = level_configs if level_configs is not None else cluster_levels

    start_time = time.perf_counter()

    levels = {
        level_name: run_clusters_from_points(
            points,
            eps=settings["epsilon"],
            min_pts=4,
            cluster_color=settings["color"],
        )
        for level_name, settings in level_configs.items()
    }

    snapshots = [
        {
            "label": "All Incidents",
            "n_incidents": len(points),
            "levels": levels,
        }
    ]

    end_time = time.perf_counter()
    print(
        f"DBSCAN snapshot execution time: {(end_time - start_time):.6f} seconds"
    )

    # Compute density levels for all input points and export CSV
    densities = compute_density_levels_from_points(points, list(level_configs.values()))

    with open(csv_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["easting", "northing", "cluster_density_level"])
        writer.writerows((row["easting"], row["northing"], row["density_level"]) for row in densities)

    return snapshots

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", help="ISO date/time; defaults to the CSV's earliest occurred_at")
    parser.add_argument("--end-date", help="ISO date/time; defaults to the CSV's latest occurred_at")
    parser.add_argument(
        "--window-length",
        help="Width of each window, e.g. '30D', '2W'; defaults to the full range split into "
             f"{DEFAULT_N_WINDOWS} equal windows",
    )
    parser.add_argument(
        "--time-step",
        help="How far each window steps forward, e.g. '7D'; shorter than --window-length overlaps "
             "windows, longer leaves gaps. Defaults to --window-length (non-overlapping)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    snapshots = build_snapshots(
        start_date=args.start_date,
        end_date=args.end_date,
        window_length=to_offset(args.window_length) if args.window_length else None,
        time_step=to_offset(args.time_step) if args.time_step else None,
    )
    with open(_OUTPUT_PATH, "w") as f:
        json.dump(snapshots, f)
    print(f"Saved {len(snapshots)} DBSCAN snapshots to {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
