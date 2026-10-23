import os
import tempfile
import warnings

import numpy as np
import pandas as pd
from flask import Blueprint, current_app, jsonify, request
from ml.generate_gi_star_snapshots import GI_STAR_CELL_SIZE, build_gi_star_snapshots, load_land_polygon
from ml.gi_star.GiStarHeatMap import GiStarHeatMap

from leecad_api import filters, queries
from leecad_api.kde_routes import _parse_time_window_args, _png_to_base64, load_points

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


@bp.get("/api/v1/animation/gi-star-heatmap")
def gi_star_heatmap_animation():
    # all params are required
    required = ["start_date", "end_date", "window_length", "time_step", "distance_band"]
    missing = [name for name in required if not request.args.get(name)]
    if missing:
        return jsonify({"error": f"Missing required parameter(s): {', '.join(missing)}"}), 400

    # distance_band must be a number; clamp it to the limits
    try:
        requested_distance_band = float(request.args.get("distance_band"))
    except ValueError:
        return jsonify({"error": "Invalid distance_band parameter"}), 400
    distance_band = max(MIN_DISTANCE_BAND, min(MAX_DISTANCE_BAND, requested_distance_band))

    # each request gets its own folder, so two users don't overwrite each other's frames
    with tempfile.TemporaryDirectory() as output_dir:
        try:
            start_date, end_date, window_length, time_step = _parse_time_window_args(request.args)
            with current_app.pool.connection() as conn:
                incidents = conn.execute(*queries.mapped_incidents_between(
                    filters.parse_without_dates(request.args), pd.Timestamp(start_date), pd.Timestamp(end_date)
                )).fetchall()
            frames = build_gi_star_snapshots(
                start_date=start_date,
                end_date=end_date,
                window_length=window_length,
                time_step=time_step,
                distance_band=distance_band,
                land_polygon=LAND_POLYGON,
                incidents=incidents,
                output_dir=output_dir,
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        for frame in frames:
            # keep the filename before the image is replaced with its base64 data
            frame["image_filename"] = frame["image"]

            if frame["image"] is not None:
                frame["image"] = _png_to_base64(path=os.path.join(output_dir, frame["image"]))

    return jsonify({
        "frames": frames,
        "distance_band": distance_band,
        "min_distance_band": MIN_DISTANCE_BAND,
        "max_distance_band": MAX_DISTANCE_BAND,
    })
