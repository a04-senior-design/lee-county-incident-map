import os
import shutil

import numpy as np
from pyproj import Transformer
from pandas.tseries.frequencies import to_offset

from ml.time_windows import build_time_windows
from ml.kde import KDEHeatMap

MAX_SNAPSHOTS = 30

# folder where the snapshot PNGs are written; app.py serves images from here
KDE_SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "tmp_kde_heatmap_snapshots")

def build_kde_heatmap_snapshots(start_date, end_date, window_length, time_step):
	"""Build one KDE heat map snapshot per time window, for the heat map
	animation.

	Windows come from ml.time_windows.build_time_windows(), which applies
	the defaults for any argument left as None. For each window, the
	incidents are projected to EPSG:2882 feet and a KDE heat map PNG is
	saved to backend/tmp_kde_heatmap_snapshots/. That folder is deleted
	and recreated on every call.

	All incidents in a window are used as one group with a fixed
	bandwidth of 1500 ft. Each window's grid is sized to its own points,
	so the image bounds differ from frame to frame.

	Parameters
	----------
	start_date    : date string; see build_time_windows()
	end_date      : date string; see build_time_windows()
	window_length : width of each window, as a pandas offset
	                (e.g. to_offset("5D"))
	time_step     : how far each window moves forward, as a pandas offset

	Returns
	-------
	A list of frames, one per window in time order:
	{"label", "window_start", "window_end", "n_incidents", "image", "bounds"}.
	image is the PNG file name and bounds is {"west", "south", "east",
	"north"} in lat/lng. Both are None for a window with no incidents.

	Raises
	------
	ValueError if there are more than MAX_SNAPSHOTS windows, if every
	window is empty, or if build_time_windows() rejects window_length or
	time_step.
	"""

	shutil.rmtree(KDE_SNAPSHOT_DIR, ignore_errors=True)
	os.makedirs(KDE_SNAPSHOT_DIR, exist_ok=True)

	# NAD 1983 StatePlane Florida West FIPS 0902 Feet
	transformer = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)

	# windows contains list of objects having the format {"window_start", "window_end", "incidents"}
	windows = build_time_windows(start_date=start_date, end_date=end_date, window_length=window_length, time_step=time_step)

	# too many snapshots - stop before doing any heat map work
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
		incidents = window["incidents"]
		points = []

		# empty window - keep a placeholder so points_per_window stays aligned with windows
		if len(incidents) == 0:
			points_per_window.append(np.empty((0, 2)))
			continue

		for incident in incidents:
			points.append([incident["lng"], incident["lat"]])

		points = np.asarray(points)
		
		longitude = points[:,0]
		latitude = points[:,1]

		easting, northing = transformer.transform(longitude, latitude)
		
		points = np.column_stack([easting, northing])

		points_per_window.append(points)

	# every window is empty - nothing to animate
	if all(len(points) == 0 for points in points_per_window):
		raise ValueError("No incidents between the start and end date.")

	# create a kde heatmap png image for each snapshot
	# use all points for this version
	kde_model_per_window = []

	for i, points in enumerate(points_per_window):

		# empty window - no heat map, keep a placeholder so the list stays aligned with windows
		if len(points) == 0:
			kde_model_per_window.append(None)
			continue

		cluster_levels = np.zeros(len(points), dtype=int)
		bandwidths = [1500]
		padding = 100

		x_min = np.min(points[:,0]) - padding
		y_min = np.min(points[:,1]) - padding
		x_max = np.max(points[:,0]) + padding
		y_max = np.max(points[:,1]) + padding

		kde_obj = KDEHeatMap(points=points, cluster_levels=cluster_levels, bandwidths=bandwidths, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, increment=300, output_dir=KDE_SNAPSHOT_DIR)
		kde_model_per_window.append(kde_obj)


	# generate the heat map png images for each window
	bounds_per_window = []

	for i, kde_obj in enumerate(kde_model_per_window):

		# empty window - no image, keep a placeholder so the list stays aligned with windows
		if kde_obj is None:
			bounds_per_window.append(None)
			continue

		snapshot_filename = f"density_overlay_{i + 1}.png"
		bounds = kde_obj.generate_heatmap_image(snapshot_filename)
		bounds_per_window.append(bounds)

	# create a return object; one frame per window in time order
	frames = []

	for i, window in enumerate(windows):
		window_start = window["window_start"]
		window_end = window["window_end"]
		bounds = bounds_per_window[i]

		# empty window - no image or bounds
		if bounds is None:
			image_filename = None
			bounds_dict = None
		else:
			image_filename = f"density_overlay_{i + 1}.png"
			bounds_dict = {
				"west": bounds.left,
				"south": bounds.bottom,
				"east": bounds.right,
				"north": bounds.top,
			}

		frames.append({
			"label": f"{window_start.strftime('%Y-%m-%d %H:%M')} - {window_end.strftime('%Y-%m-%d %H:%M')}",
			"window_start": window_start.isoformat(),
			"window_end": window_end.isoformat(),
			"n_incidents": len(points_per_window[i]),
			"image": image_filename,
			"bounds": bounds_dict,
		})

	return frames


# test: run from backend/ with
#   python3 -m ml.generate_kde_heatmap_snapshots
if __name__ == "__main__":
	frames = build_kde_heatmap_snapshots(
		start_date="2026-07-06",
		end_date="2026-07-20",
		window_length=to_offset("5D"),
		time_step=to_offset("5D"),
	)

	print(f"len(frames) = {len(frames)}")

	for frame in frames:
		print(frame["label"], frame["n_incidents"], frame["image"], frame["bounds"])










    






