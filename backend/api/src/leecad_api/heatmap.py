import base64
import os
import tempfile
from datetime import date, timedelta

import numpy as np
from ml.kde import KDEHeatMap
from rasterio.warp import transform_bounds

from leecad_api import filters as filters_module

# The in_county box from migration 0005, in Florida West feet. Every mapped incident is
# inside it, and KDEpy refuses a grid that leaves any point out.
GRID = transform_bounds("EPSG:4326", "EPSG:2882", -82.35, 26.27, -81.50, 26.90)
MAX_FRAMES = 31


def _number(args, name: str, default: int, low: int, high: int) -> int:
    raw = args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be a whole number") from None
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def parse(args):
    """Returns (filters, first_day, last_day, window, bandwidth). The filters start
    window - 1 days before from, so the first frame has a full window behind it."""
    if "from" not in args or "to" not in args:
        raise ValueError("from and to are required")
    filters_module.parse(args)
    first_day, last_day = date.fromisoformat(args["from"]), date.fromisoformat(args["to"])
    if (last_day - first_day).days + 1 > MAX_FRAMES:
        raise ValueError(f"at most {MAX_FRAMES} days per request")

    window = _number(args, "window", 7, 1, 30)
    # below 1500 ft a county-wide grid gets too fine to render in time
    bandwidth = _number(args, "bandwidth", 3000, 1500, 10000)

    query_args = args.copy()
    query_args["from"] = (first_day - timedelta(days=window - 1)).isoformat()
    return filters_module.parse(query_args), first_day, last_day, window, bandwidth


def _kde(points, bandwidth: int, output_dir: str) -> KDEHeatMap:
    x_min, y_min, x_max, y_max = GRID
    # three cells per bandwidth is still smooth; finer only costs time
    increment = bandwidth / 3
    return KDEHeatMap(points=points, cluster_levels=np.zeros(len(points), dtype=int),
                      bandwidths=[bandwidth], x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
                      increment=increment, output_dir=output_dir)


def build_frames(rows, first_day: date, last_day: date, window: int, bandwidth: int) -> dict:
    days = np.array([r["day"] for r in rows], dtype="datetime64[D]")
    points = np.array([(r["x"], r["y"]) for r in rows], dtype=float).reshape(-1, 2)
    ends = np.arange(np.datetime64(first_day), np.datetime64(last_day) + 1)
    members = [points[(days > end - window) & (days <= end)] for end in ends]

    frames, bounds, legend = [], None, None
    with tempfile.TemporaryDirectory() as tmp:
        # One color scale for every frame, so a busy week looks hotter than a quiet one.
        # The KDE runs twice per frame because holding every frame's grid costs more memory.
        vmax = max((_kde(p, bandwidth, tmp).density_surface.max() * len(p) for p in members if len(p)),
                   default=0)

        for end, p in zip(ends, members):
            frame = {"date": str(end), "start": str(end - window + 1), "count": len(p), "image": None}
            if len(p):
                kde = _kde(p, bandwidth, tmp)
                box = kde.generate_heatmap_image("frame.png", weight=len(p), vmin=vmax * 1e-4, vmax=vmax)
                bounds = {"west": box.left, "south": box.bottom, "east": box.right, "north": box.top}
                legend = kde.get_legend_data()
                with open(os.path.join(tmp, "frame.png"), "rb") as f:
                    frame["image"] = "data:image/png;base64," + base64.b64encode(f.read()).decode()
            frames.append(frame)

    return {"bounds": bounds, "legend": legend, "window": window, "bandwidth": bandwidth, "frames": frames}
