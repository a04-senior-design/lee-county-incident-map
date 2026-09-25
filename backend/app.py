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
from ml.generate_dbscan_snapshots import build_snapshots  # noqa: E402
from ml.kde import KDEHeatMap  # noqa: E402

OUTPUT_DIR = os.path.dirname(__file__)
MAX_BANDWIDTH = 10000
MIN_BANDWIDTH = 500
DEFAULT_BANDWIDTH = 1500
DEFAULT_CLUSTER_SET = 0
# radio button labels, one per entry in cluster_sets (same order)
CLUSTER_SET_LABELS = [
    "No cluster analysis (all points)", 
    "1 level",
    "2 levels",
    "3 levels",
]

DBSCAN_CLUSTER_LEVELS1 = np.array([-1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, 0, -1, -1, 0, -1, -1, -1, 0, 0, 0, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, 0, -1, 0, 0, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1]) 
DBSCAN_CLUSTER_LEVELS2 = np.array([-1, -1, 0, 1, 1, -1, 0, -1, 0, -1, 0, -1, 0, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, 1, 1, -1, 0, 0, -1, 0, -1, -1, 1, -1, -1, 1, 0, 0, 0, -1, 0, 0, -1, 0, -1, -1, 0, 0, -1, -1, 0, -1, 0, 1, -1, 1, -1, -1, 1, 0, -1, -1, 1, 1, 1, -1, 1, 1, -1, -1, 0, 0, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, 0, -1, -1, 0, -1, -1, -1, 0, 0, 0, -1, -1, -1, -1, -1, 1, -1, 0, -1, -1, 0, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, 1, -1, 0, -1, 0, -1, -1, -1, 0, 1, 0, 0, -1, -1, -1, -1, 0, 0, -1, 1, -1, -1, -1, -1, 0, 0, 0, -1, 0, -1, 0, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, 0, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, 1, -1, 1, 0, -1, -1, -1, -1, 0, 0, -1, -1, 1, 0, 0, -1, 1, -1, -1, 0, -1, -1, 0, 1, 0, -1, -1, -1, 1, -1, 1, 1, -1, -1, 0, 1, -1, -1, -1, 0, 0, 0, -1, 1, -1, -1, 0, -1, -1, 0, -1, -1, 0, -1, 1, -1, -1, -1, 0, -1, -1])
DBSCAN_CLUSTER_LEVELS3 = np.array([0, 0, 1, 2, 2, 0, 1, -1, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 2, 2, 0, 1, 1, 0, 1, 0, 0, 2, -1, 0, 2, 1, 1, 1, 0, 1, 1, 0, 1, -1, 0, 1, 1, 0, 0, 1, 0, 1, 2, 0, 2, 0, 0, 2, 1, 0, 0, 2, 2, 2, 0, 2, 2, 0, 0, 1, 1, 0, -1, 0, 1, 1, 0, 0, 0, 0, -1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 1, 0, -1, 0, 0, 0, 2, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 2, 0, 1, 0, 1, 0, 0, 0, 1, 2, 1, 1, 0, 0, 0, 0, 1, 1, 0, 2, 0, 0, 0, -1, 1, 1, 1, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 2, 0, 2, 1, 0, 0, 0, 0, 1, 1, 0, 0, 2, 1, 1, 0, 2, 0, 0, 1, 0, 0, 1, 2, 1, 0, 0, 0, 2, 0, 2, 2, 0, -1, 1, 2, 0, 0, 0, 1, 1, 1, 0, 2, 0, 0, 1, 0, -1, 1, 0, 0, 1, 0, 2, 0, 0, 0, 1, 0, 0])

CSV_PATH = os.path.join(
    os.path.dirname(__file__), 
    "..", "data", "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv"
)

def load_points() -> np.ndarray:
    """
    Load N_POINTS incidents from late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv and return a (N, 2)
    array of projected x/y coordinates suitable for euclidean distance.
    """

    incidents_df = pd.read_csv(CSV_PATH).dropna(subset=["lat", "lon"])
    
    latitude = incidents_df["lat"].to_numpy()
    longitude = incidents_df["lon"].to_numpy()

    # NAD 1983 StatePlane Florida West FIPS 0902 Feet
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)
    easting, northing = transformer.transform(longitude, latitude)

    points = np.column_stack([easting, northing])
    
    return points, latitude, longitude


app = Flask(__name__)


allowed_origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")
CORS(app, resources={r"/api/*": {"origins": allowed_origin}})


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


@app.route("/cluster-lab")
def cluster_lab():
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    return send_from_directory(frontend_dir, "cluster-lab.html")

@app.route("/api/clusters")
def clusters():
    try:
        eps = float(request.args.get("eps", 13123.0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid parameters"}), 400

    min_pts = 4  # fixed backend constant, not user-adjustable

    level = request.args.get("level")
    cluster_color = cluster_levels[level]["color"] if level in cluster_levels else None

    data = load_csv_incidents()
    result = run_clusters(data, eps, min_pts, cluster_color=cluster_color)
    return jsonify(result)

@app.route("/api/clusters/multi")
def clusters_multi():
    data = load_csv_incidents()
    
    all_results = {}
    for level, settings in cluster_levels.items():
        result = run_clusters(incidents=data, eps=settings["epsilon"], min_pts=settings["min_pts"], cluster_color=settings.get("color"))
        all_results[level] = result
        
    return jsonify(all_results)


@app.route("/animation-lab")
def animation_lab():
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    return send_from_directory(frontend_dir, "animation-lab.html")


@app.route("/animation-assets/kde/<path:filename>")
def animation_kde_asset(filename):
    return send_from_directory(kde_animation.PNG_DIR, filename)


@app.route("/api/animation/kde")
def animation_kde():
    frames = [
        {**frame, "image": f"/animation-assets/kde/{frame['filename']}"}
        for frame in kde_animation.list_frames()
    ]
    return jsonify({"bounds": kde_animation.BOUNDS, "frames": frames})


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
        frames = build_snapshots(
            start_date=start_date,
            end_date=end_date,
            window_length=to_offset(window_length) if window_length else None,
            time_step=to_offset(time_step) if time_step else None,
            level_configs=level_configs,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"frames": frames})


@app.route("/api/incidents")
def incidents():
    data = get_incidents()
    return jsonify(data)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/heatmap-lab")
def heatmap_lab():
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    return send_from_directory(frontend_dir, "heatmap-lab.html")
    

@app.route("/api/heatmap")
def heatmap():

    try:
        requested_bandwidths = [float(bw) for bw in request.args.getlist("bandwidth")]
    except ValueError:
        return jsonify({"error": "Invalid bandwidth parameter"}), 400  

    try:
        cluster_set = int(request.args.get("cluster_set", DEFAULT_CLUSTER_SET))
    except ValueError:
        return jsonify({"error": "Invalid cluster_set parameter"}), 400  

    # input data based on a sample of x-y coordinates (easting/northing) from County incident data
    data_points_with_noise, _, _ = load_points()
    easting = data_points_with_noise[:, 0]
    northing = data_points_with_noise[:, 1]

    # selectable cluster level sets; index match CLUSTER_SET_LABELS
    cluster_sets = [
        np.zeros(len(data_points_with_noise), dtype=int), # no cluster analysis: every point is cluster level 0
        DBSCAN_CLUSTER_LEVELS1,
        DBSCAN_CLUSTER_LEVELS2,
        DBSCAN_CLUSTER_LEVELS3,
    ]

    if not 0 <= cluster_set < len(cluster_sets):
        return jsonify({
            "error": f"cluster_set must be between 0 and {len(cluster_sets) - 1}, got {cluster_set}."
        }), 400

    dbscan_cluster_levels = cluster_sets[cluster_set]

    # define range of mesh grid (lattice structure) to represent the corresponding map coordinates
    padding = 100
    x_min = np.min(easting) - padding
    x_max = np.max(easting) + padding
    y_min = np.min(northing) - padding
    y_max = np.max(northing) + padding
    increment = 300
    print(f'increment = {increment}')

    # one bandwidth per non-noise cluster level, ordered by ascending level (0, 1, 2) - least dense to most dense
    unique_cluster_levels = np.unique(dbscan_cluster_levels)
    num_clusters = np.count_nonzero(unique_cluster_levels != -1)
    print(f'num_clusters: {num_clusters}')

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
    print(f'bandwidths: {bandwidths}')
    

    # instantiate a KDEHeatMap object
    kde_obj = KDEHeatMap(points=data_points_with_noise, cluster_levels=dbscan_cluster_levels, bandwidths=bandwidths, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, increment=increment, output_dir=OUTPUT_DIR)
    # generate the heat map overlay PNG image file
    bounds = kde_obj.generate_heatmap_image()

    with open(os.path.join(OUTPUT_DIR, "density_overlay.png"), "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    bounds_dict = {
        "west": bounds.left,
        "south": bounds.bottom,
        "east": bounds.right,
        "north": bounds.top,
    }

    legend_data = kde_obj.get_legend_data()

    result = {
        "image": f"data:image/png;base64,{image_b64}", 
        "bounds": bounds_dict, 
        "legend": legend_data,
        "bandwidths": bandwidths,
        "min_bandwidth": MIN_BANDWIDTH,
        "max_bandwidth": MAX_BANDWIDTH,
        "cluster_set": cluster_set,
        "cluster_set_labels": CLUSTER_SET_LABELS,
    }

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
