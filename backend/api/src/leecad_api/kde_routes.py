import base64
import hashlib
import os
import tempfile
import threading
from collections import OrderedDict

import numpy as np
import pandas as pd
from flask import Blueprint, current_app, jsonify, request
from ml.generate_kde_heatmap_snapshots import PADDING_PER_BANDWIDTH, build_kde_heatmap_snapshots
from ml.kde import BandwidthOptimizer, KDEHeatMap
from pandas.tseries.frequencies import to_offset
from pyproj import Transformer

from leecad_api import filters, queries, runs

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

# optimized bandwidths by the points they were fit to, per worker
OPTIMIZED_BANDWIDTHS = OrderedDict()
OPTIMIZED_BANDWIDTHS_LOCK = threading.Lock()
MAX_OPTIMIZED_BANDWIDTHS = 100


def _optimize_key(points, levels):
    # sort first so the same incidents in another order are a hit
    order = np.lexsort((points[:, 1], points[:, 0], levels))
    return hashlib.sha256(points[order].tobytes() + levels[order].tobytes()).hexdigest()


def load_points() -> np.ndarray:
    """
    Load the mapped incidents from the database and return a (N, 2)
    array of projected x/y coordinates suitable for euclidean distance.
    """

    # optional; without them every mapped incident is used
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    start = filters.eastern_time(start_date, "start_date") if start_date else None
    end = filters.eastern_time(end_date, "end_date", end=True) if end_date else None

    with current_app.pool.connection() as conn:
        rows = conn.execute(*queries.mapped_points(
            filters.parse_without_dates(request.args), start, end
        )).fetchall()
    incidents_df = pd.DataFrame(rows, columns=["lat", "lon"]).dropna(subset=["lat", "lon"])
    if incidents_df.empty:
        raise ValueError("no mapped incidents match these filters")

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
    start_date and end_date are returned as Eastern datetimes (see
    filters.eastern_time()), or None if not sent.
    window_length and time_step are converted with to_offset(), or None
    if not sent.

    Raises ValueError if a date or time can't be read, or if window_length
    or time_step isn't a valid offset (e.g. "abc"), so call it inside the
    route's try/except ValueError.
    """
    start_date = filters.eastern_time(args["start_date"], "start_date") if args.get("start_date") else None
    end_date = filters.eastern_time(args["end_date"], "end_date", end=True) if args.get("end_date") else None

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

    # the "Optimize Bandwidth(s)" button sends optimize=true; the radios and sliders leave it out
    optimize = request.args.get("optimize", "").lower()
    if optimize not in ("", "true", "false"):
        return jsonify({"error": "optimize must be true or false"}), 400
    optimize = optimize == "true"

    # guard: the optimizer picks the bandwidths, so none can be sent with it
    if optimize and requested_bandwidths:
        return jsonify({"error": "Send either optimize=true or bandwidth, not both"}), 400

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
    # the results belong to the /clusters run named by run_id; without one there are none
    dbscan_csv = os.path.join(runs.run_dir(request.args), "userID_dbscan.csv") if request.args.get("run_id") else None
    dbscan_df = None 
    if dbscan_csv is None or not os.path.exists(dbscan_csv):
        dbscan_status = "missing"
    else:
        dbscan_df = pd.read_csv(dbscan_csv)
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

    # one bandwidth per non-noise cluster level, ordered by ascending level (0, 1, 2) - least dense to most dense
    unique_cluster_levels = np.unique(dbscan_cluster_levels)
    num_clusters = np.count_nonzero(unique_cluster_levels != -1)

    # guard: DBSCAN classified every point as noise, so there is nothing for the KDE to fit
    if num_clusters == 0:
        return jsonify({
            "error": "Cluster analysis classified every point as noise. Try larger epsilon values in cluster-lab.",
            "dbscan_status": dbscan_status,
        }), 400

    # the grid and KDEHeatMap are based only on the points that go into the KDE;
    # for the "KDE Heat Map (by cluster density level)" analysis, points marked as noise from DBSCAN are left out;
    # for the "KDE Heat Map (all points)" analysis, all points are marked with cluster levels == 0 (so there are no "noise" points)
    is_not_noise = dbscan_cluster_levels != -1
    non_noise_points = data_points_with_noise[is_not_noise]
    non_noise_levels = dbscan_cluster_levels[is_not_noise]
    easting = non_noise_points[:, 0]
    northing = non_noise_points[:, 1]

    x_min_no_padding = np.min(easting)
    x_max_no_padding = np.max(easting)
    y_min_no_padding = np.min(northing)
    y_max_no_padding = np.max(northing)
    increment = 300

    if optimize:
        key = _optimize_key(non_noise_points, non_noise_levels)
        with OPTIMIZED_BANDWIDTHS_LOCK:
            bandwidths = OPTIMIZED_BANDWIDTHS.get(key)
            if bandwidths is not None:
                OPTIMIZED_BANDWIDTHS.move_to_end(key)

        if bandwidths is None:
            # same points, levels and grid spacing as the heat map below, so the bandwidths fit the heat map drawn
            optimizer = BandwidthOptimizer(
                points=non_noise_points, cluster_levels=non_noise_levels,
                x_min_no_padding=x_min_no_padding, y_min_no_padding=y_min_no_padding,
                x_max_no_padding=x_max_no_padding, y_max_no_padding=y_max_no_padding,
                increment=increment, lower_bound=MIN_BANDWIDTH, upper_bound=MAX_BANDWIDTH,
            )
            # plain floats, since the optimizer returns a numpy array, which jsonify can't serialize
            bandwidths = [float(bw) for bw in optimizer.optimize_bandwidths()]
            with OPTIMIZED_BANDWIDTHS_LOCK:
                OPTIMIZED_BANDWIDTHS[key] = bandwidths
                if len(OPTIMIZED_BANDWIDTHS) > MAX_OPTIMIZED_BANDWIDTHS:
                    OPTIMIZED_BANDWIDTHS.popitem(last=False)
    elif requested_bandwidths:
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

    # define range of mesh grid (lattice structure) to represent the corresponding map coordinates;
    # padded only after the bandwidths are known, since the padding depends on them
    padding = PADDING_PER_BANDWIDTH * max(bandwidths)
    x_min = x_min_no_padding - padding
    x_max = x_max_no_padding + padding
    y_min = y_min_no_padding - padding
    y_max = y_max_no_padding + padding

    # each request gets its own run folder, so two users don't overwrite each other's image,
    # and the report can find this one by its run_id
    run_id, output_dir = runs.new_run_dir()
    os.makedirs(output_dir)

    # instantiate a KDEHeatMap object
    kde_obj = KDEHeatMap(points=non_noise_points, cluster_levels=non_noise_levels, bandwidths=bandwidths, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, increment=increment, output_dir=output_dir)
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
        # the level each bandwidth applies to, e.g. [0, 2] when level 1 found no clusters
        "cluster_levels": [int(level) for level in unique_cluster_levels if level != -1],
        "optimized": optimize,
        "min_bandwidth": MIN_BANDWIDTH,
        "max_bandwidth": MAX_BANDWIDTH,
        "cluster_set": cluster_set,
        "cluster_set_labels": CLUSTER_SET_LABELS,
        "dbscan_status": dbscan_status,
        "run_id": run_id,
    }

    run_inputs = runs.inputs(filters.parse_without_dates(request.args),
                             request.args.get("start_date"), request.args.get("end_date"))
    runs.save_response(output_dir, "kde", run_inputs, result)

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
                incidents = conn.execute(*queries.mapped_incidents_between(
                    filters.parse_without_dates(request.args), start_date, end_date
                )).fetchall()
            frames, legend = build_kde_heatmap_snapshots(
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

    return jsonify({
        "frames": frames,
        "legend": legend,
        "bandwidth": bandwidth,
        "min_bandwidth": MIN_BANDWIDTH,
        "max_bandwidth": MAX_BANDWIDTH,
    })
