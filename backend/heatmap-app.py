import os
from flask import Flask, jsonify, send_from_directory
from ml.kde import KDEHeatMap
import pandas as pd
import numpy as np
from pyproj import Transformer
import base64

OUTPUT_DIR = os.path.dirname(__file__)

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
    


    dbscan_cluster_levels1 = np.array([-1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, 0, -1, -1, 0, -1, -1, -1, 0, 0, 0, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, 0, -1, 0, 0, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1]) 
    dbscan_cluster_levels2 = np.array([-1, -1, 0, 1, 1, -1, 0, -1, 0, -1, 0, -1, 0, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, 1, 1, -1, 0, 0, -1, 0, -1, -1, 1, -1, -1, 1, 0, 0, 0, -1, 0, 0, -1, 0, -1, -1, 0, 0, -1, -1, 0, -1, 0, 1, -1, 1, -1, -1, 1, 0, -1, -1, 1, 1, 1, -1, 1, 1, -1, -1, 0, 0, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, 0, -1, -1, 0, -1, -1, -1, 0, 0, 0, -1, -1, -1, -1, -1, 1, -1, 0, -1, -1, 0, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, 1, -1, 0, -1, 0, -1, -1, -1, 0, 1, 0, 0, -1, -1, -1, -1, 0, 0, -1, 1, -1, -1, -1, -1, 0, 0, 0, -1, 0, -1, 0, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, 0, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, 1, -1, 1, 0, -1, -1, -1, -1, 0, 0, -1, -1, 1, 0, 0, -1, 1, -1, -1, 0, -1, -1, 0, 1, 0, -1, -1, -1, 1, -1, 1, 1, -1, -1, 0, 1, -1, -1, -1, 0, 0, 0, -1, 1, -1, -1, 0, -1, -1, 0, -1, -1, 0, -1, 1, -1, -1, -1, 0, -1, -1])
    dbscan_cluster_levels3 = np.array([0, 0, 1, 2, 2, 0, 1, -1, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 2, 2, 0, 1, 1, 0, 1, 0, 0, 2, -1, 0, 2, 1, 1, 1, 0, 1, 1, 0, 1, -1, 0, 1, 1, 0, 0, 1, 0, 1, 2, 0, 2, 0, 0, 2, 1, 0, 0, 2, 2, 2, 0, 2, 2, 0, 0, 1, 1, 0, -1, 0, 1, 1, 0, 0, 0, 0, -1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 1, 0, -1, 0, 0, 0, 2, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 2, 0, 1, 0, 1, 0, 0, 0, 1, 2, 1, 1, 0, 0, 0, 0, 1, 1, 0, 2, 0, 0, 0, -1, 1, 1, 1, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 2, 0, 2, 1, 0, 0, 0, 0, 1, 1, 0, 0, 2, 1, 1, 0, 2, 0, 0, 1, 0, 0, 1, 2, 1, 0, 0, 0, 2, 0, 2, 2, 0, -1, 1, 2, 0, 0, 0, 1, 1, 1, 0, 2, 0, 0, 1, 0, -1, 1, 0, 0, 1, 0, 2, 0, 0, 0, 1, 0, 0])

#    dbscan_cluster_levels = dbscan_cluster_levels3

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

    # find optimized bandwidth
    bandwidths = []
    bw_values = [3100, 3200, 3300]
    unique_cluster_levels = np.unique(dbscan_cluster_levels)
    num_clusters = np.count_nonzero(unique_cluster_levels != -1)
    print(f'num_clusters: {num_clusters}')
    for i in range(num_clusters):
        bandwidths.append(bw_values[i])

    bandwidths = bandwidths[::-1]
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

    result = {"image": f"data:image/png;base64,{image_b64}", "bounds": bounds_dict}

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

