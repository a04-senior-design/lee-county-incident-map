import os
import base64

import numpy as np
import pandas as pd
from pandas.tseries.frequencies import to_offset
from pyproj import Transformer
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from cache import get_incidents  # noqa: E402 — imported after env load
from ml.dbscan import run_clusters, load_csv_incidents, cluster_levels  # noqa: E402
from ml.animation import kde as kde_animation  # noqa: E402
from ml.animation import dbscan as dbscan_animation  # noqa: E402
from ml.generate_dbscan_snapshots import build_dbscan_snapshots, build_dbscan_snapshots_from_points  # noqa: E402
from ml.generate_kde_heatmap_snapshots import build_kde_heatmap_snapshots, build_kde_heatmap_snapshots_from_dbscan, count_first_frame_levels, get_dbscan_frames_status, KDE_SNAPSHOT_DIR  # noqa: E402
from ml.kde import KDEHeatMap  # noqa: E402

OUTPUT_DIR = os.path.dirname(__file__)
MAX_BANDWIDTH = 10000
MIN_BANDWIDTH = 500
DEFAULT_BANDWIDTH = 1500
DEFAULT_CLUSTER_SET = 0
# labels for the KDE heat map's cluster set radios; index = cluster_set
CLUSTER_SET_LABELS = [
    "KDE Heat Map (all points)", 
    "KDE Heat Map (by cluster density level)",
]
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


def _png_to_base64(path):
    with open(path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{image_b64}"


@app.route("/api/animation/dbscan")
def animation_dbscan():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    window_length = request.args.get("window_length")
    time_step = request.args.get("time_step")
    has_level_overrides = any(
        key == "levels" or key.endswith("_eps")
        for key in request.args
    )

    # no windowing or level params -> serve the precomputed snapshots, otherwise recompute on demand
    if not any([start_date, end_date, window_length, time_step, has_level_overrides]):
        return jsonify({"frames": dbscan_animation.load_snapshots()})

    try:
        level_configs = _parse_dbscan_level_overrides(request.args)
        frames = build_dbscan_snapshots(
            start_date=start_date,
            end_date=end_date,
            window_length=to_offset(window_length) if window_length else None,
            time_step=to_offset(time_step) if time_step else None,
            level_configs=level_configs,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"frames": frames})

@app.route("/api/animation/kde-heatmap-dbscan")
def kde_heatmap_dbscan_animation():
    # one bandwidth per cluster level in frame 1, e.g. ?bandwidth=3000&bandwidth=1500&bandwidth=800
    bandwidth_values = request.args.getlist("bandwidth")

    # no bandwidths sent (first load): use the default for each of frame 1's levels
    if len(bandwidth_values) == 0:
        level_count = count_first_frame_levels()
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

    try:
        frames = build_kde_heatmap_snapshots_from_dbscan(bandwidths=bandwidths)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    for frame in frames:
        # keep the filename before the image is replaced with its base64 data
        frame["image_filename"] = frame["image"]

        if frame["image"] is not None:
            img_path = os.path.join(KDE_SNAPSHOT_DIR, frame["image"])
            frame["image"] = _png_to_base64(path=img_path)

    return jsonify({
        "frames": frames,
        "bandwidths": bandwidths,
        "min_bandwidth": MIN_BANDWIDTH,
        "max_bandwidth": MAX_BANDWIDTH,
    })
    

@app.route("/api/animation/kde-heatmap-dbscan/status")
def kde_heatmap_dbscan_status():
    # whether the cluster-levels option can be used: "missing", "no_cluster_levels" or "available"
    dbscan_status = get_dbscan_frames_status()
    return jsonify({"dbscan_status": dbscan_status})
