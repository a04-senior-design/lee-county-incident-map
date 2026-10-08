"""
Shared time-windowing for the animation snapshot generators.
Loads data and slides a window of `window_length` across [start_date, end_date] 
in steps of `time_step`, returning each window's data. 
"""

import pandas as pd
from ml.dbscan.DBSCANCluster import load_csv_incidents_with_time


def build_time_windows(start_date=None, end_date=None, window_length=None, time_step=None):

	"""Slide a window of `window_length` across [start_date, end_date] in
    steps of `time_step` and return the data in each window.

    Parameters
    ----------
    start_date    : date string
    end_date      : date string
    window_length : width of each window
    time_step     : how far each window moves forward

    Returns
    -------
    A list of {"window_start", "window_end", "incidents"} dicts in time
    order. window_end is capped at end_date, so the last window may be
    shorter than window_length.  A record is included when window_start <= occurred_at < window_end,
    except a window ending at end_date also includes occurred_at == end_date.

    Raises
    ------
    ValueError if window_length or time_step is not positive.

    Note: if start_date is not before end_date, no windows are produced and
    an empty list is returned (no error is raised).
    """

	incidents = load_csv_incidents_with_time()
	times = pd.to_datetime([inc["occurred_at"] for inc in incidents])

	start_date = pd.Timestamp(start_date) if start_date is not None else times.min()
	end_date = pd.Timestamp(end_date) if end_date is not None else times.max()

	# user-supplied dates are typically tz-naive ("2026-06-30"); occurred_at is tz-aware
	if start_date.tzinfo is None and times.tz is not None:
		start_date = start_date.tz_localize(times.tz)
	if end_date.tzinfo is None and times.tz is not None:
		end_date = end_date.tz_localize(times.tz)
	if window_length is None:
		window_length = (end_date - start_date) # set window
	if time_step is None: 
		time_step = window_length # default: non-overlapping windows

	if start_date + window_length <= start_date:
		raise ValueError("window_length must be positive")
	if start_date + time_step <= start_date:
		raise ValueError("time_step must be positive")

	windows = []
	window_start = start_date

	while window_start < end_date:
		window_end = min(window_start + window_length, end_date)
		reaches_end = window_end == end_date
		window_incidents = [
			incident for incident in incidents
			if window_start <= incident["occurred_at"] < window_end
			or (reaches_end and incident["occurred_at"] == end_date)
		]
		windows.append({"window_start": window_start, "window_end": window_end, "incidents": window_incidents})
		window_start += time_step

	return windows