import os
from flask import Flask, jsonify, request, send_from_directory
from ml.kde import KDEHeatMap
import pandas as pd
import numpy as np
from pyproj import Transformer
import base64

OUTPUT_DIR = os.path.dirname(__file__)
MAX_BANDWIDTH = 10000
MIN_BANDWIDTH = 500
DEFAULT_BANDWIDTH = 1500

app = Flask(__name__)

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


    
    """
    # REPLACE CLUSTER LEVEL ASSIGNMENTS WITH CALL TO DBSCAN MODULE DURING APP INTEGRATION
    # cluster level for testing (-1 == noise; 0 = least dense; 1 = denser than 0)
    dbscan_cluster_levels = np.array([0, 0, 1, 1, 1, 1, 1, -1, 1, -1, 1, 0, 1, 1, 0, 1, 1, 0, -1, 1, 1, 
                            0, 0, 0, -1, 1, 1, 1, 0, 1, 1, -1, 1, 1, 1, 1, 0, 1, 1, 0, 1, 0, 
                            0, 1, -1, 1, 1, 1, 1, 1, -1, 1, 1, 0, 1, -1, 0, 1, 1, 0, 1, 1, 1, 
                            1, 1, -1, 0, 1, 0, 1, 1, -1, 1, 1, 1, 1, 0, 0, 0, 0, -1, 1, 1, 0, 
                            -1, 0, 1, 1, -1, 1, 0, -1, -1, 1, 0, 1, 1, -1, 1, -1, 1, 1, 1, 1, 
                            -1, 1, 0, 1, 1, 0, 1, 0, -1, 1, 0, 0, 1, 1, -1, 0, -1, 1, 1, 1, -1, 
                            1, 0, 1, -1, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, -1, 1, 0, 1, 1, 1, 1, 1, 
                            -1, 1, 1, 0, 0, 1, 1, 0, 1, 1, 0, 1, -1, 1, 1, 1, -1, 1, 0, 1, -1, 
                            -1, 0, 0, 1, 1, -1, 0, 0, -1, 1, 1, -1, 1, 1, 1, 1, 0, 0, -1, 0, 1, 
                            1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1, 
                            1, 1, -1, -1, -1, 1, 0, 0, 1, 1, -1, 1, 1, 0, 0, 0, 1, -1, -1, 0, 1, 
                            -1, -1, -1, -1, -1, 1, 1, 1, 1, 1, 1, -1, 1, 0, 1, -1, 0])

    # TESTING - reallocate all non-noise points to the same cluster (i.e. cluster == 0)
    dbscan_cluster_levels[dbscan_cluster_levels == 1] = 0
    """

    
    dbscan_cluster_levels1 = np.array([-1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, 0, -1, -1, 0, -1, -1, -1, 0, 0, 0, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, 0, -1, 0, 0, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1]) 
    dbscan_cluster_levels2 = np.array([-1, -1, 0, 1, 1, -1, 0, -1, 0, -1, 0, -1, 0, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, 1, 1, -1, 0, 0, -1, 0, -1, -1, 1, -1, -1, 1, 0, 0, 0, -1, 0, 0, -1, 0, -1, -1, 0, 0, -1, -1, 0, -1, 0, 1, -1, 1, -1, -1, 1, 0, -1, -1, 1, 1, 1, -1, 1, 1, -1, -1, 0, 0, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, 0, -1, -1, 0, -1, -1, -1, 0, 0, 0, -1, -1, -1, -1, -1, 1, -1, 0, -1, -1, 0, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, 1, -1, 0, -1, 0, -1, -1, -1, 0, 1, 0, 0, -1, -1, -1, -1, 0, 0, -1, 1, -1, -1, -1, -1, 0, 0, 0, -1, 0, -1, 0, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, 0, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, 1, -1, 1, 0, -1, -1, -1, -1, 0, 0, -1, -1, 1, 0, 0, -1, 1, -1, -1, 0, -1, -1, 0, 1, 0, -1, -1, -1, 1, -1, 1, 1, -1, -1, 0, 1, -1, -1, -1, 0, 0, 0, -1, 1, -1, -1, 0, -1, -1, 0, -1, -1, 0, -1, 1, -1, -1, -1, 0, -1, -1])
    dbscan_cluster_levels3 = np.array([0, 0, 1, 2, 2, 0, 1, -1, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 2, 2, 0, 1, 1, 0, 1, 0, 0, 2, -1, 0, 2, 1, 1, 1, 0, 1, 1, 0, 1, -1, 0, 1, 1, 0, 0, 1, 0, 1, 2, 0, 2, 0, 0, 2, 1, 0, 0, 2, 2, 2, 0, 2, 2, 0, 0, 1, 1, 0, -1, 0, 1, 1, 0, 0, 0, 0, -1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 1, 0, -1, 0, 0, 0, 2, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 2, 0, 1, 0, 1, 0, 0, 0, 1, 2, 1, 1, 0, 0, 0, 0, 1, 1, 0, 2, 0, 0, 0, -1, 1, 1, 1, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 2, 0, 2, 1, 0, 0, 0, 0, 1, 1, 0, 0, 2, 1, 1, 0, 2, 0, 0, 1, 0, 0, 1, 2, 1, 0, 0, 0, 2, 0, 2, 2, 0, -1, 1, 2, 0, 0, 0, 1, 1, 1, 0, 2, 0, 0, 1, 0, -1, 1, 0, 0, 1, 0, 2, 0, 0, 0, 1, 0, 0])
    

    dbscan_cluster_levels = dbscan_cluster_levels2

    # input data based on a sample of x-y coordinates (easting/northing) from County incident data
    data_points_with_noise, latitude, longitude = load_points()
    easting = data_points_with_noise[:, 0]
    northing = data_points_with_noise[:, 1]

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
    }

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

