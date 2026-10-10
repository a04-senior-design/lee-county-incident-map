import base64
import os
import tempfile

import numpy as np
import pandas as pd
from flask import Blueprint, current_app, jsonify, request
from ml.generate_kde_heatmap_snapshots import build_kde_heatmap_snapshots
from ml.kde import KDEHeatMap
from pandas.tseries.frequencies import to_offset
from pyproj import Transformer

from leecad_api import queries

bp = Blueprint("kde", __name__)

MAX_BANDWIDTH = 10000
MIN_BANDWIDTH = 500
DEFAULT_BANDWIDTH = 1500
DEFAULT_CLUSTER_SET = 0
# labels for the KDE heat map's cluster set radios; index = cluster_set
CLUSTER_SET_LABELS = [
    "KDE Heat Map (all points)", 
    "KDE Heat Map (by cluster density level)",
]

def load_points() -> np.ndarray:
    """
    Load the mapped incidents from the database and return a (N, 2)
    array of projected x/y coordinates suitable for euclidean distance.
    """

    with current_app.pool.connection() as conn:
        rows = conn.execute(queries.MAPPED_POINTS).fetchall()
    incidents_df = pd.DataFrame(rows, columns=["lat", "lon"]).dropna(subset=["lat", "lon"])
    
    latitude = incidents_df["lat"].to_numpy()
    longitude = incidents_df["lon"].to_numpy()

    # NAD 1983 StatePlane Florida West FIPS 0902 Feet
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)
    easting, northing = transformer.transform(longitude, latitude)

    points = np.column_stack([easting, northing])
    
    return points, latitude, longitude

def _png_to_base64(path):
    with open(path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{image_b64}"


def _parse_time_window_args(args):
    """Read the time-windowing query params shared by the animation routes.

    Returns (start_date, end_date, window_length, time_step).
    start_date and end_date are returned as strings, or None if not sent.
    window_length and time_step are converted with to_offset(), or None
    if not sent.

    Raises ValueError if window_length or time_step isn't a valid offset
    (e.g. "abc"), so call it inside the route's try/except ValueError.
    """
    start_date = args.get("start_date") or None 
    end_date = args.get("end_date") or None 

    window_length = args.get("window_length")
    if window_length:
        window_length = to_offset(window_length)
    else:
        window_length = None

    time_step = args.get("time_step")
    if time_step:
        time_step = to_offset(time_step)
    else:
        time_step = None 

    return start_date, end_date, window_length, time_step

@bp.get("/api/v1/kde-heatmap")
def kde_heatmap():

    try:
        requested_bandwidths = [float(bw) for bw in request.args.getlist("bandwidth")]
    except ValueError:
        return jsonify({"error": "Invalid bandwidth parameter"}), 400  

    try:
        cluster_set = int(request.args.get("cluster_set", DEFAULT_CLUSTER_SET))
    except ValueError:
        return jsonify({"error": "Invalid cluster_set parameter"}), 400  

    # guard: cluster_set must match one of the radio button options
    if not 0 <= cluster_set < len(CLUSTER_SET_LABELS):
        return jsonify({
            "error": f"cluster_set must be between 0 and {len(CLUSTER_SET_LABELS) - 1}"
        }), 400

    # status of cluster-lab's DBSCAN results: "missing", "all_noise", or "available"
    dbscan_df = None 
    if not os.path.exists("userID_dbscan.csv"):
        dbscan_status = "missing"
    else:
        dbscan_df = pd.read_csv("userID_dbscan.csv")
        if (dbscan_df["cluster_density_level"] == -1).all():
            dbscan_status = "all_noise"
        else:
            dbscan_status = "available"

    # guard: cluster analysis requires the DBSCAN results written by cluster-lab
    if cluster_set == 1 and dbscan_status == "missing":
        return jsonify({
            "error": "No cluster analysis results found. Run cluster analysis in cluster-lab first.",
            "dbscan_status": dbscan_status,
        }), 400
    
    # cluster analysis selected: use DBSCAN results from cluster-lab; otherwise use all points as one level
    if cluster_set == 1:
        data_points_with_noise = dbscan_df[["easting", "northing"]].to_numpy()
        dbscan_cluster_levels = dbscan_df["cluster_density_level"].to_numpy()
    else:
        data_points_with_noise, _, _ = load_points()
        dbscan_cluster_levels = np.zeros(len(data_points_with_noise), dtype=int)

    easting = data_points_with_noise[:, 0]
    northing = data_points_with_noise[:, 1]

    # define range of mesh grid (lattice structure) to represent the corresponding map coordinates
    padding = 100
    x_min = np.min(easting) - padding
    x_max = np.max(easting) + padding
    y_min = np.min(northing) - padding
    y_max = np.max(northing) + padding
    increment = 300

    # one bandwidth per non-noise cluster level, ordered by ascending level (0, 1, 2) - least dense to most dense
    unique_cluster_levels = np.unique(dbscan_cluster_levels)
    num_clusters = np.count_nonzero(unique_cluster_levels != -1)

    # guard: DBSCAN classified every point as noise, so there is nothing for the KDE to fit
    if num_clusters == 0:
        return jsonify({
            "error": "Cluster analysis classified every point as noise. Try larger epsilon values in cluster-lab.",
            "dbscan_status": dbscan_status,
        }), 400

    if requested_bandwidths:
        # guard: the frontend must send exactly one bandwidth per non-noise cluster level
        if len(requested_bandwidths) != num_clusters:
            return jsonify({
                "error": f"Expected {num_clusters} bandwidths, got {len(requested_bandwidths)}. Reload the page."
            }), 400
        # guard: bandwidths must be non-increasing (level 0 >= level 1 >= level 2)
        for i in range(len(requested_bandwidths) - 1):
            if requested_bandwidths[i] < requested_bandwidths[i + 1]:
                return jsonify({
                    "error": f"Bandwidths must be non-increasing: level {i} ({requested_bandwidths[i]}) "
                    f"< level {i + 1} ({requested_bandwidths[i + 1]})."
                    }), 400
        # clamp each slider value to the shared limits
        bandwidths = [max(MIN_BANDWIDTH, min(MAX_BANDWIDTH, bw)) for bw in requested_bandwidths]
    else:
        # initial page load: no values sent, so use the shared default for every level
        bandwidths = [DEFAULT_BANDWIDTH] * num_clusters
    

    # each request gets its own folder, so two users don't overwrite each other's image
    with tempfile.TemporaryDirectory() as output_dir:
        # instantiate a KDEHeatMap object
        kde_obj = KDEHeatMap(points=data_points_with_noise, cluster_levels=dbscan_cluster_levels, bandwidths=bandwidths, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, increment=increment, output_dir=output_dir)
        # generate the heat map overlay PNG image file
        bounds = kde_obj.generate_heatmap_image()

        # file path for image being sent to frontend
        img_path = os.path.join(output_dir, "density_overlay.png")
        image_data = _png_to_base64(path=img_path)

    bounds_dict = {
        "west": bounds.left,
        "south": bounds.bottom,
        "east": bounds.right,
        "north": bounds.top,
    }

    legend_data = kde_obj.get_legend_data()

    result = {
        "image": image_data, 
        "bounds": bounds_dict, 
        "legend": legend_data,
        "bandwidths": bandwidths,
        "min_bandwidth": MIN_BANDWIDTH,
        "max_bandwidth": MAX_BANDWIDTH,
        "cluster_set": cluster_set,
        "cluster_set_labels": CLUSTER_SET_LABELS,
        "dbscan_status": dbscan_status,
    }

    return jsonify(result)


@bp.get("/api/v1/animation/kde-heatmap")
def kde_heatmap_animation():
    # all params are required
    required = ["start_date", "end_date", "window_length", "time_step", "bandwidth"]
    missing = []
    for name in required:
        if not request.args.get(name):
            missing.append(name)

    if missing:
        return jsonify({"error": f"Missing required parameter(s): {', '.join(missing)}"}), 400

    # bandwidth must be a number; clamp it to the shared limits
    try:
        requested_bandwidth = float(request.args.get("bandwidth"))
    except ValueError:
        return jsonify({"error": "Invalid bandwidth parameter"}), 400
    bandwidth = max(MIN_BANDWIDTH, min(MAX_BANDWIDTH, requested_bandwidth))

    # read start_date, end_date, window_length, and time_step
    # each request gets its own folder, so two users don't overwrite each other's frames
    with tempfile.TemporaryDirectory() as output_dir:
        try:
            start_date, end_date, window_length, time_step = _parse_time_window_args(request.args)
            with current_app.pool.connection() as conn:
                incidents = conn.execute(queries.MAPPED_INCIDENTS_BETWEEN,
                                         (pd.Timestamp(start_date), pd.Timestamp(end_date))).fetchall()
            frames = build_kde_heatmap_snapshots(
                start_date=start_date,
                end_date=end_date,
                window_length=window_length,
                time_step=time_step,
                bandwidth=bandwidth,
                incidents=incidents,
                output_dir=output_dir,
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        for frame in frames:
            # keep the filename before the image is replaced with its base64 data
            frame["image_filename"] = frame["image"]

            if frame["image"] is not None:
                img_path = os.path.join(output_dir, frame["image"])
                frame["image"] = _png_to_base64(path=img_path)

    return jsonify({"frames": frames, "bandwidth": bandwidth})
