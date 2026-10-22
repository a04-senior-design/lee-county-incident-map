import os

import geopandas as gpd
import numpy as np
from pyproj import Transformer

from ml.time_windows import build_time_windows
from ml.gi_star.GiStarHeatMap import GiStarHeatMap

MAX_SNAPSHOTS = 30
GI_STAR_CELL_SIZE = 2500

LAND_MASK_PATH = os.path.join(os.path.dirname(__file__), "gi_star", "CountyBackground_Land_Mask", "CountyBackground.shp")

def load_land_polygon():
	"""Load the county land as one shapely MultiPolygon in EPSG:2882 feet.

	GiStarHeatMap uses it to leave out grid cells whose centroid is in the
	water. The "WATER" features in the shapefile are ignored. It doesn't
	change, so load it once and pass it to every call.
	"""

	land_gdf = gpd.read_file(LAND_MASK_PATH)
	land_gdf = land_gdf[land_gdf["TYPE"] == "LAND"].to_crs("EPSG:2882")
	# make_valid repairs the invalid LAND polygon before the pieces are merged
	return land_gdf.geometry.make_valid().union_all()

def build_gi_star_snapshots(start_date, end_date, window_length, time_step, distance_band, land_polygon, incidents, output_dir):
	"""Build one Gi* z-score heat map snapshot per time window, for the
	Gi* animation.

	Windows come from ml.time_windows.build_time_windows(), which applies
	the defaults for any argument left as None. For each window, the
	incidents are projected to EPSG:2882 feet and a Gi* z-score PNG is
	saved to output_dir.

	Every frame uses one grid, sized once from the incidents in all
	windows, so every frame has the same bounds.

	Parameters
	----------
	start_date    : date string; see build_time_windows()
	end_date      : date string; see build_time_windows()
	window_length : width of each window, as a pandas offset
	                (e.g. to_offset("5D"))
	time_step     : how far each window moves forward, as a pandas offset
	distance_band : Gi* distance band in feet, used for every window
	land_polygon  : from load_land_polygon()
	incidents     : passed to build_time_windows()
	output_dir    : where the PNGs are written; must exist

	Returns
	-------
	A list of frames, one per window in time order:
	{"label", "window_start", "window_end", "n_incidents", "image", "bounds"}.
	image is the PNG file name and bounds is {"west", "south", "east",
	"north"} in lat/lng. Both are None for a window with no incidents.

	Raises
	------
	ValueError if there are more than MAX_SNAPSHOTS windows, if every
	window is empty, or if build_time_windows() or GiStarHeatMap rejects
	an argument.
	"""

	# NAD 1983 StatePlane Florida West FIPS 0902 Feet
	transformer = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)

	# windows contains list of objects having the format {"window_start", "window_end", "incidents"}
	windows = build_time_windows(start_date=start_date, end_date=end_date, window_length=window_length, time_step=time_step, incidents=incidents)

	# too many snapshots - stop before doing any Gi* work
	if len(windows) > MAX_SNAPSHOTS:
		raise ValueError(
			f"{len(windows)} snapshots requested; the maximum is {MAX_SNAPSHOTS}. "
			"Use a shorter date range or a longer time step."
		)

	# list of x-y points from each window
	points_per_window = []

	# separate the incident x-y points from each window
	for window in windows:
		# list of objects having the format {"lat", "lng", "occurred_at"}
		window_incidents = window["incidents"]

		# empty window - keep a placeholder so points_per_window stays aligned with windows
		if len(window_incidents) == 0:
			points_per_window.append(np.empty((0, 2)))
			continue

		longitude = np.asarray([incident["lng"] for incident in window_incidents])
		latitude = np.asarray([incident["lat"] for incident in window_incidents])

		easting, northing = transformer.transform(longitude, latitude)

		points_per_window.append(np.column_stack([easting, northing]))

	# every window is empty - nothing to animate
	if all(len(points) == 0 for points in points_per_window):
		raise ValueError("No incidents between the start and end date.")

	# one grid for every frame, sized from the incidents in all windows
	all_points = np.vstack(points_per_window)
	padding = GI_STAR_CELL_SIZE

	x_min = np.min(all_points[:,0]) - padding
	y_min = np.min(all_points[:,1]) - padding
	x_max = np.max(all_points[:,0]) + padding
	y_max = np.max(all_points[:,1]) + padding

	# one frame per window, in time order
	frames = []

	for i, window in enumerate(windows):
		points = points_per_window[i]

		image_filename = None
		bounds_dict = None

		# empty window - no Gi* analysis, image and bounds stay None
		if len(points) > 0:
			gi_star_obj = GiStarHeatMap(points=points, distance_band=distance_band, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, cell_size=GI_STAR_CELL_SIZE, land_polygon=land_polygon, output_dir=output_dir)

			image_filename = f"gi_star_overlay_{i + 1}.png"
			bounds = gi_star_obj.generate_zscore_heatmap_image(image_filename)
			bounds_dict = {
				"west": bounds.left,
				"south": bounds.bottom,
				"east": bounds.right,
				"north": bounds.top,
			}

		window_start = window["window_start"]
		window_end = window["window_end"]

		frames.append({
			"label": f"{window_start.strftime('%Y-%m-%d %H:%M')} - {window_end.strftime('%Y-%m-%d %H:%M')}",
			"window_start": window_start.isoformat(),
			"window_end": window_end.isoformat(),
			"n_incidents": len(points),
			"image": image_filename,
			"bounds": bounds_dict,
		})

	return frames
