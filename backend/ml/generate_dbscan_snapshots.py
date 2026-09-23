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

import pandas as pd
from pandas.tseries.frequencies import to_offset

from ml.dbscan import cluster_levels, load_csv_incidents_with_time, run_clusters

DEFAULT_N_WINDOWS = 5

_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "dbscan_snapshots.json")


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

    start_date/end_date default to the CSV's full occurred_at range;
    window_length/time_step default to that range split into
    DEFAULT_N_WINDOWS equal, non-overlapping windows (the old fixed
    5-snapshot behavior) — leaving both blank also means "just one window",
    i.e. a single DBSCAN snapshot for [start_date, end_date] rather than an
    animation.

    `level_configs` is a {level_name: {epsilon, min_pts, color}} dict
    overriding which levels run and their parameters (e.g. from user-facing
    per-level toggles/sliders); defaults to `cluster_levels`
    (street/neighborhood/district) when omitted.

    Returns a list of
    {label, window_start, window_end, n_incidents, levels: {level_name: geojson}}
    dicts in time order.
    """
    level_configs = level_configs if level_configs is not None else cluster_levels
    incidents = load_csv_incidents_with_time()
    times = pd.to_datetime([inc["occurred_at"] for inc in incidents])

    start_date = pd.Timestamp(start_date) if start_date is not None else times.min()
    end_date = pd.Timestamp(end_date) if end_date is not None else times.max()
    # user-supplied dates are typically tz-naive ("2026-06-30"); occurred_at is tz-aware
    if start_date.tzinfo is None and times.tz is not None:
        start_date = start_date.tz_localize(times.tz)
    if end_date.tzinfo is None and times.tz is not None:
        end_date = end_date.tz_localize(times.tz)
    if window_length is None:
        window_length = (end_date - start_date) # set window
    if time_step or window_length is None: # if either is none need to have one frame
        time_step = window_length

    if start_date + window_length <= start_date:
        raise ValueError("window_length must be positive")
    if start_date + time_step <= start_date:
        raise ValueError("time_step must be positive")

    start_time = time.perf_counter() # start timer
    
    snapshots = []
    window_start = start_date
    while window_start < end_date:
        window_end = min(window_start + window_length, end_date)
        window_incidents = [
            inc for inc in incidents
            if window_start <= inc["occurred_at"] <= window_end
        ]
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
        window_start += time_step
    
    end_time = time.perf_counter()
    print(f"DBSCAN snapshot execution time: {(end_time - start_time):.6f} seconds")
    
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
