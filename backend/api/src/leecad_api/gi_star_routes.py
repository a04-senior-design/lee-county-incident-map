import os
import tempfile
import warnings

import numpy as np
from flask import Blueprint, jsonify, request
from ml.generate_gi_star_snapshots import GI_STAR_CELL_SIZE, load_land_polygon
from ml.gi_star.GiStarHeatMap import GiStarHeatMap

from leecad_api.kde_routes import _png_to_base64, load_points

bp = Blueprint("gi_star", __name__)

MIN_DISTANCE_BAND = 500
MAX_DISTANCE_BAND = 10000
DEFAULT_DISTANCE_BAND = 2500

# loaded once per worker, since it doesn't change
LAND_POLYGON = load_land_polygon()

# libpysal warns on every request about land cells with no neighbor inside the distance band
warnings.filterwarnings("ignore", message="The weights matrix is not fully connected")


@bp.get("/api/v1/gi-star-heatmap")
def gi_star_heatmap():
    # no distance_band sent (radio button selected): use the default
    try:
        requested_distance_band = float(request.args.get("distance_band", DEFAULT_DISTANCE_BAND))
    except ValueError:
        return jsonify({"error": "Invalid distance-band parameter"}), 400

    # clamp the slider value to the limits
    distance_band = max(MIN_DISTANCE_BAND, min(MAX_DISTANCE_BAND, requested_distance_band))

    data_points, _, _ = load_points()
    easting = data_points[:, 0]
    northing = data_points[:, 1]

    # define the range of the grid to represent the corresponding map coordinates
    padding = GI_STAR_CELL_SIZE
    x_min = np.min(easting) - padding
    x_max = np.max(easting) + padding
    y_min = np.min(northing) - padding
    y_max = np.max(northing) + padding

    # each request gets its own folder, so two users don't overwrite each other's image
    with tempfile.TemporaryDirectory() as output_dir:
        gi_star_obj = GiStarHeatMap(points=data_points, distance_band=distance_band, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, cell_size=GI_STAR_CELL_SIZE, land_polygon=LAND_POLYGON, output_dir=output_dir)

        # generate the heat map overlay PNG image file and get its latitude/longitude boundaries
        image_filename = "gi_star_overlay.png"
        bounds = gi_star_obj.generate_zscore_heatmap_image(image_filename)
        image_data = _png_to_base64(path=os.path.join(output_dir, image_filename))

    bounds_dict = {
        "west": bounds.left,
        "south": bounds.bottom,
        "east": bounds.right,
        "north": bounds.top,
    }

    return jsonify({
        "image": image_data,
        "bounds": bounds_dict,
        "legend": gi_star_obj.get_legend_data(),
        "distance_band": distance_band,
        "min_distance_band": MIN_DISTANCE_BAND,
        "max_distance_band": MAX_DISTANCE_BAND,
    })
