import os
import shutil

import pandas as pd
import numpy as np
from pyproj import Transformer
from pandas.tseries.frequencies import to_offset

from ml.generate_dbscan_snapshots import DBSCAN_ANIMATION_DENSITIES_DIR
from ml.time_windows import build_time_windows
from ml.kde import KDEHeatMap

MAX_SNAPSHOTS = 30

# folder where the snapshot PNGs are written; app.py serves images from here
KDE_SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "tmp_kde_heatmap_snapshots")

def build_kde_heatmap_snapshots(start_date, end_date, window_length, time_step, bandwidth, incidents=None, output_dir=KDE_SNAPSHOT_DIR):
	"""Build one KDE heat map snapshot per time window, for the heat map
	animation.

	Windows come from ml.time_windows.build_time_windows(), which applies
	the defaults for any argument left as None. For each window, the
	incidents are projected to EPSG:2882 feet and a KDE heat map PNG is
	saved to backend/tmp_kde_heatmap_snapshots/. That folder is deleted
	and recreated on every call.

	All incidents in a window are used as one group with a given bandwidth. 
	Each window's grid is sized to its own points,
	so the image bounds differ from frame to frame.

	Parameters
	----------
	start_date    : date string; see build_time_windows()
	end_date      : date string; see build_time_windows()
	window_length : width of each window, as a pandas offset
	                (e.g. to_offset("5D"))
	time_step     : how far each window moves forward, as a pandas offset
	bandwidth	  : KDE bandwidth in feet, used for every window
	incidents     : passed to build_time_windows(); the CSV when None
	output_dir    : where the PNGs are written; deleted and recreated first

	Returns
	-------
	(frames, legend). frames is a list, one per window in time order:
	{"label", "window_start", "window_end", "n_incidents", "image", "bounds"}.
	image is the PNG file name and bounds is {"west", "south", "east",
	"north"} in lat/lng. Both are None for a window with no incidents.
	legend is get_legend_data() of the last non-empty frame; every frame
	shares one color scale, so it applies to the whole animation.

	Raises
	------
	ValueError if there are more than MAX_SNAPSHOTS windows, if every
	window is empty, or if build_time_windows() rejects window_length or
	time_step.
	"""

	shutil.rmtree(output_dir, ignore_errors=True)
	os.makedirs(output_dir, exist_ok=True)

	# NAD 1983 StatePlane Florida West FIPS 0902 Feet
	transformer = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)

	# windows contains list of objects having the format {"window_start", "window_end", "incidents"}
	windows = build_time_windows(start_date=start_date, end_date=end_date, window_length=window_length, time_step=time_step, incidents=incidents)

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
		bandwidths = [bandwidth]
		padding = 100

		x_min = np.min(points[:,0]) - padding
		y_min = np.min(points[:,1]) - padding
		x_max = np.max(points[:,0]) + padding
		y_max = np.max(points[:,1]) + padding

		kde_obj = KDEHeatMap(points=points, cluster_levels=cluster_levels, bandwidths=bandwidths, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, increment=300, output_dir=output_dir)
		kde_model_per_window.append(kde_obj)


	# one color scale for every frame, so a color means the same density in each
	frame_maxes = [kde_obj.density_surface.max() for kde_obj in kde_model_per_window if kde_obj is not None]
	vmax = max(frame_maxes)
	# cut off from the quietest frame's peak, so its heat map isn't cut away
	vmin = min(frame_maxes) * 0.0001

	# generate the heat map png images for each window
	bounds_per_window = []
	legend = None

	for i, kde_obj in enumerate(kde_model_per_window):

		# empty window - no image, keep a placeholder so the list stays aligned with windows
		if kde_obj is None:
			bounds_per_window.append(None)
			continue

		snapshot_filename = f"density_overlay_{i + 1}.png"
		bounds = kde_obj.generate_heatmap_image(snapshot_filename, vmin=vmin, vmax=vmax)
		bounds_per_window.append(bounds)
		# the same scale in every frame, so the last non-empty frame's legend fits them all
		legend = kde_obj.get_legend_data()

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

	return frames, legend


def read_dbscan_frames(densities_dir=DBSCAN_ANIMATION_DENSITIES_DIR):
	"""Read the per-frame DBSCAN output CSVs written by the cluster animation.

	Reads {n}_userID_dbscan.csv for n = 1, 2, ... from
	densities_dir (DBSCAN_ANIMATION_DENSITIES_DIR by default), stopping at the first missing number.
	Each file has easting, northing (EPSG:2882 feet) and
	cluster_density_level (-1 = noise, 0 = least dense, ...).

	Returns
	-------
	A list of frames in order, one per file:
	{"frame_number", "points", "cluster_levels"}, where points is an
	(N, 2) array of [easting, northing] and cluster_levels is an (N,)
	array. A header-only file (empty window) gives N = 0.
	"""
	frames = []
	frame_number = 1

	while True:
		csv_path = os.path.join(densities_dir, f"{frame_number}_userID_dbscan.csv")

		# no file for this number - all frames have been read
		if not os.path.exists(csv_path):
			break

		dbscan_df = pd.read_csv(csv_path)
		points = dbscan_df[["easting", "northing"]].to_numpy()
		cluster_levels = dbscan_df["cluster_density_level"].to_numpy()

		frames.append({
			"frame_number": frame_number,
			"points": points,
			"cluster_levels": cluster_levels,
		})

		frame_number = frame_number + 1

	return frames


def count_first_frame_levels(densities_dir=DBSCAN_ANIMATION_DENSITIES_DIR):
	"""Return how many cluster levels (noise excluded) frame 1 has, i.e. how
	many bandwidths build_kde_heatmap_snapshots_from_dbscan() expects.
	Returns 0 if there are no frame files or frame 1 has no cluster levels."""
	dbscan_frames = read_dbscan_frames(densities_dir)

	if len(dbscan_frames) == 0:
		return 0

	levels = np.unique(dbscan_frames[0]["cluster_levels"])
	levels = levels[levels != -1] # drop noise
	return len(levels)
	

def get_dbscan_frames_status(densities_dir=DBSCAN_ANIMATION_DENSITIES_DIR):
	"""Report whether the DBSCAN frame files can be used for the KDE heat map.

	Returns
	-------
	"missing" if there are no frame files, "no_cluster_levels" if frame 1
	is empty or all noise, otherwise "available".
	"""
	dbscan_frames = read_dbscan_frames(densities_dir)

	if len(dbscan_frames) == 0:
		return "missing"

	levels = np.unique(dbscan_frames[0]["cluster_levels"])
	levels = levels[levels != -1] # drop noise

	if len(levels) == 0:
		return "no_cluster_levels"

	return "available"


def build_kde_heatmap_snapshots_from_dbscan(bandwidths, densities_dir=DBSCAN_ANIMATION_DENSITIES_DIR, output_dir=KDE_SNAPSHOT_DIR):
	"""Build one KDE heat map snapshot per DBSCAN frame CSV, with one
	bandwidth per cluster density level.

	Frames come from read_dbscan_frames(). Frame 1 sets the cluster levels
	for the whole animation: bandwidths[i] is the bandwidth for frame 1's
	i-th level (lowest level number first). Every later frame uses the
	bandwidths for the levels it has, matched by level number; a frame
	with fewer levels simply doesn't use the others. Noise points (-1)
	are left out of the KDE. PNGs are saved to output_dir (KDE_SNAPSHOT_DIR by default), which is
	deleted and recreated on every call.

	Parameters
	----------
	bandwidths : list of KDE bandwidths in feet, one per cluster level in
	             frame 1 (e.g. [3000, 1500, 800] for levels 0, 1, 2)

	Returns
	-------
	(frames, legend). frames is a list, one per CSV in order:
	{"label", "n_incidents", "image", "bounds", "note"}.
	image is the PNG file name and bounds is {"west", "south", "east",
	"north"} in lat/lng. For an empty or all-noise frame, image and bounds
	are None and note explains why; otherwise note is None.
	Every frame shares one color scale, and legend is get_legend_data() of
	the last frame with a heat map, so it applies to the whole animation.

	Raises
	------
	ValueError if there are no frame CSVs, if frame 1 has no cluster
	levels, if len(bandwidths) doesn't match frame 1's level count, or if
	a later frame has a cluster level that frame 1 doesn't have.
	"""
	dbscan_frames = read_dbscan_frames(densities_dir)

	if len(dbscan_frames) == 0:
		raise ValueError("No DBSCAN frame files found.")

	# -- frame 1 cluster levels set the number of bandwidths for the whole animation --
	first_levels = np.unique(dbscan_frames[0]["cluster_levels"])
	first_levels = first_levels[first_levels != -1] # drop noise

	if len(first_levels) == 0:
		raise ValueError("Frame 1 has no cluster levels (empty or all noise), so it can't set the bandwidths.")

	if len(bandwidths) != len(first_levels):
		raise ValueError(f"Expected {len(first_levels)} bandwidths (one per cluster level in frame 1), got {len(bandwidths)}.")

	# bandwidth for each level number, e.g. {0: 3000, 1: 1500, 2: 800}
	bandwidth_for_level = {}
	for i in range(len(first_levels)):
		level = int(first_levels[i])
		bandwidth_for_level[level] = bandwidths[i]

	# -- check every frame before doing any heat map work --
	for frame in dbscan_frames:
		levels = np.unique(frame["cluster_levels"])
		levels = levels[levels != -1]

		for level in levels:
			if int(level) not in bandwidth_for_level:
				raise ValueError(
					f"Frame {frame['frame_number']} has cluster levels {levels.tolist()}, "
					f"but frame 1 (used to set the number of bandwidths) has {first_levels.tolist()}."
				)

	shutil.rmtree(output_dir, ignore_errors=True)
	os.makedirs(output_dir, exist_ok=True)

	# -- one KDE per frame, before any image, so every frame can share one color scale --
	kde_model_per_frame = []
	notes = []

	for frame in dbscan_frames:
		points = frame["points"]
		cluster_levels = frame["cluster_levels"]

		# keep only clustered points; noise doesn't go into the KDE
		is_clustered = cluster_levels != -1
		clustered_points = points[is_clustered]
		clustered_levels = cluster_levels[is_clustered]

		# empty or all-noise frame - no heat map, keep a placeholder so the lists stay aligned with frames
		if len(points) == 0:
			kde_model_per_frame.append(None)
			notes.append("No incidents in this frame.")
			continue
		if len(clustered_points) == 0:
			kde_model_per_frame.append(None)
			notes.append("All points were noise; no KDE heat map could be generated.")
			continue

		# bandwidths for the levels this frame has, lowest level first
		frame_levels = np.unique(clustered_levels)
		frame_bandwidths = []
		for level in frame_levels:
			frame_bandwidths.append(bandwidth_for_level[int(level)])

		padding = 100
		x_min = np.min(clustered_points[:, 0]) - padding
		y_min = np.min(clustered_points[:, 1]) - padding
		x_max = np.max(clustered_points[:, 0]) + padding
		y_max = np.max(clustered_points[:, 1]) + padding

		kde_obj = KDEHeatMap(points=clustered_points, cluster_levels=clustered_levels, bandwidths=frame_bandwidths, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, increment=300, output_dir=output_dir)
		kde_model_per_frame.append(kde_obj)
		notes.append(None)

	# one color scale for every frame, so a color means the same density in each;
	# frame 1 always has cluster levels, so there is at least one KDE
	frame_maxes = [kde_obj.density_surface.max() for kde_obj in kde_model_per_frame if kde_obj is not None]
	vmax = max(frame_maxes)
	# cut off from the quietest frame's peak, so its heat map isn't cut away
	vmin = min(frame_maxes) * 0.0001

	# -- one heat map per frame --
	frames = []
	legend = None

	for frame, kde_obj, note in zip(dbscan_frames, kde_model_per_frame, notes):
		frame_number = frame["frame_number"]

		image_filename = None
		bounds_dict = None

		if kde_obj is not None:
			image_filename = f"density_overlay_{frame_number}.png"
			bounds = kde_obj.generate_heatmap_image(image_filename, vmin=vmin, vmax=vmax)
			bounds_dict = {
				"west": bounds.left,
				"south": bounds.bottom,
				"east": bounds.right,
				"north": bounds.top,
			}
			# the same scale in every frame, so the last frame's legend fits them all
			legend = kde_obj.get_legend_data()

		frames.append({
			"label": f"Frame {frame_number}",
			"n_incidents": len(frame["points"]),
			"image": image_filename,
			"bounds": bounds_dict,
			"note": note,
		})

	return frames, legend





# test: run from backend/ with
#   python3 -m ml.generate_kde_heatmap_snapshots
if __name__ == "__main__":
	"""
	frames = build_kde_heatmap_snapshots(
		start_date="2026-07-06",
		end_date="2026-07-20",
		window_length=to_offset("5D"),
		time_step=to_offset("5D"),
		bandwidth=1500
	)

	print(f"len(frames) = {len(frames)}")

	for frame in frames:
		print(frame["label"], frame["n_incidents"], frame["image"], frame["bounds"])
	
	# test reading the dbscan frame csv files
	dbscan_frames = read_dbscan_frames()
	print(f"len(dbscan_frames) = {len(dbscan_frames)}")

	for frame in dbscan_frames:
		levels = np.unique(frame["cluster_levels"])
		non_noise_levels= levels[levels != -1]
		print(f'frame {frame["frame_number"]}: {len(frame["points"])} points, levels {non_noise_levels.tolist()}')

	"""

	# test building the kde heat maps from the dbscan frames
	kde_frames, _ = build_kde_heatmap_snapshots_from_dbscan(bandwidths=[3000, 1500, 800])
	print(f"len(kde_frames) = {len(kde_frames)}")

	for frame in kde_frames:
		print(frame["label"], frame["n_incidents"], frame["image"], frame["note"])








    






