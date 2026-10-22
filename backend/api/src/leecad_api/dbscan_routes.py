import os
import tempfile

import numpy as np
import pandas as pd
from flask import Blueprint, current_app, jsonify, request
from ml.dbscan import cluster_levels
from ml.generate_dbscan_snapshots import build_dbscan_snapshots, build_dbscan_snapshots_from_points
from ml.generate_kde_heatmap_snapshots import (
    build_kde_heatmap_snapshots_from_dbscan,
    count_first_frame_levels,
    get_dbscan_frames_status,
)
from pandas.tseries.frequencies import to_offset
from pyproj import Transformer

from leecad_api import filters, queries, runs
from leecad_api.kde_routes import DEFAULT_BANDWIDTH, MAX_BANDWIDTH, MIN_BANDWIDTH, _png_to_base64, _utc

bp = Blueprint("dbscan", __name__)


def _parse_dbscan_level_overrides(args) -> dict:
    """Build a {level_name: {epsilon, min_pts, color}} dict from per-level
    `<level>_eps` query params, falling back to cluster_levels defaults for
    epsilon; min_pts is always the cluster_levels fixed value (not user-
    adjustable). Omits any level left out of `levels` (a comma-separated
    list of enabled level names) so it's excluded from the DBSCAN run
    entirely."""
    enabled = args.get("levels")
    enabled_names = set(enabled.split(",")) if enabled else set(cluster_levels.keys())

    level_configs = {}
    for name, defaults in cluster_levels.items():
        if name not in enabled_names:
            continue
        eps = float(args.get(f"{name}_eps", defaults["epsilon"]))
        level_configs[name] = {"epsilon": eps, "min_pts": defaults["min_pts"], "color": defaults["color"]}
    return level_configs


@bp.get("/api/v1/animation/dbscan")
def animation_dbscan():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    window_length = request.args.get("window_length")
    time_step = request.args.get("time_step")

    # the precomputed snapshots file is not deployed, DBSCAN over every incident at once would
    # not fit in memory, and a single frame writes to a read-only folder, so all four are required
    missing = [name for name in ("start_date", "end_date", "window_length", "time_step")
               if not request.args.get(name)]
    if missing:
        return jsonify({"error": f"Missing required parameter(s): {', '.join(missing)}"}), 400

    run_id, densities_dir = runs.new_run_dir()

    try:
        level_configs = _parse_dbscan_level_overrides(request.args)
        with current_app.pool.connection() as conn:
            incidents = conn.execute(*queries.mapped_incidents_between(
                filters.parse_without_dates(request.args), pd.Timestamp(start_date), pd.Timestamp(end_date)
            )).fetchall()
        frames = build_dbscan_snapshots(
            start_date=start_date,
            end_date=end_date,
            window_length=to_offset(window_length) if window_length else None,
            time_step=to_offset(time_step) if time_step else None,
            level_configs=level_configs,
            incidents=incidents,
            densities_dir=densities_dir,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"frames": frames, "run_id": run_id})


@bp.get("/api/v1/animation/kde-heatmap-dbscan")
def kde_heatmap_dbscan_animation():
    densities_dir = runs.run_dir(request.args)

    # one bandwidth per cluster level in frame 1, e.g. ?bandwidth=3000&bandwidth=1500&bandwidth=800
    bandwidth_values = request.args.getlist("bandwidth")

    # no bandwidths sent (first load): use the default for each of frame 1's levels
    if len(bandwidth_values) == 0:
        level_count = count_first_frame_levels(densities_dir)
        bandwidth_values = [DEFAULT_BANDWIDTH] * level_count

    # every bandwidth must be a number
    requested_bandwidths = []
    for value in bandwidth_values:
        try:
            requested_bandwidths.append(float(value))
        except ValueError:
            return jsonify({"error": f"Invalid bandwidth parameter: {value}"}), 400

    # bandwidths must be non-increasing (level 0 >= level 1 >= level 2)
    for i in range(len(requested_bandwidths) - 1):
        if requested_bandwidths[i] < requested_bandwidths[i + 1]:
            return jsonify({
                "error": f"Bandwidths must be non-increasing: level {i} ({requested_bandwidths[i]}) "
                f"< level {i + 1} ({requested_bandwidths[i + 1]})."
            }), 400

    # clamp each bandwidth to the shared limits
    bandwidths = []
    for bw in requested_bandwidths:
        bandwidths.append(max(MIN_BANDWIDTH, min(MAX_BANDWIDTH, bw)))

    # each request gets its own folder, so two users don't overwrite each other's frames
    with tempfile.TemporaryDirectory() as output_dir:
        try:
            frames = build_kde_heatmap_snapshots_from_dbscan(bandwidths=bandwidths, densities_dir=densities_dir,
                                                            output_dir=output_dir)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        for frame in frames:
            # keep the filename before the image is replaced with its base64 data
            frame["image_filename"] = frame["image"]

            if frame["image"] is not None:
                img_path = os.path.join(output_dir, frame["image"])
                frame["image"] = _png_to_base64(path=img_path)

    return jsonify({
        "frames": frames,
        "bandwidths": bandwidths,
        "min_bandwidth": MIN_BANDWIDTH,
        "max_bandwidth": MAX_BANDWIDTH,
    })
    

@bp.get("/api/v1/animation/kde-heatmap-dbscan/status")
def kde_heatmap_dbscan_status():
    # whether the cluster-levels option can be used: "missing", "no_cluster_levels" or "available"
    dbscan_status = get_dbscan_frames_status(runs.run_dir(request.args))
    return jsonify({"dbscan_status": dbscan_status})


@bp.get("/api/v1/clusters")
def clusters():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    try:
        # DBSCAN memory grows with the square of the point count, so instead of every incident
        # the range defaults to the last 30 days and is capped at 60
        end = _utc(end_date) if end_date else pd.Timestamp.now(tz="UTC")
        start = _utc(start_date) if start_date else end - pd.Timedelta(days=30)
        if end - start > pd.Timedelta(days=60):
            raise ValueError("at most 60 days per request")
        with current_app.pool.connection() as conn:
            rows = conn.execute(*queries.mapped_incidents_between(
                filters.parse_without_dates(request.args), start, end
            )).fetchall()
        # NAD 1983 StatePlane Florida West FIPS 0902 Feet, as load_points() did
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)
        easting, northing = transformer.transform([r["lng"] for r in rows], [r["lat"] for r in rows])
        data_points = np.column_stack([easting, northing])

        run_id, densities_dir = runs.new_run_dir()
        os.makedirs(densities_dir)

        level_configs = _parse_dbscan_level_overrides(request.args)
        frames = build_dbscan_snapshots_from_points(
            points=data_points,
            level_configs=level_configs,
            csv_name=os.path.join(densities_dir, "userID_dbscan.csv"),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"frames": frames, "run_id": run_id})
