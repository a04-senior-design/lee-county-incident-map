"""Hotspot and cluster summaries for the PDF report.

Runs the same three analyses as the map overlays (KDE density, Getis-Ord Gi*
and DBSCAN) on the incidents a report already holds, and boils each one down
to the few facts a reader needs: where the busiest areas are, how many
incidents sit in them, and what the algorithm parameters were. The arrays the
report charts are drawn from are returned too.

Every analysis is independent. If one fails or is skipped, its entry is
{"error": "<why>"} and the report prints that instead of the section.

A report only includes the analyses the user created on the map, run with the
slider values they chose. settings_from_args() reads both from the report
request, under the same parameter names the map's own overlay requests use, so
the report matches what the user was looking at.
"""

import functools
import logging
from collections import Counter

import numpy as np

log = logging.getLogger(__name__)

# the same defaults and slider limits the map overlays use (kde_routes, gi_star_routes)
KDE_BANDWIDTH_FT = 1500
MIN_BANDWIDTH_FT, MAX_BANDWIDTH_FT = 500, 10000
KDE_INCREMENT_FT = 300
KDE_PAD_FT = 100
GI_DISTANCE_BAND_FT = 2500
MIN_DISTANCE_BAND_FT, MAX_DISTANCE_BAND_FT = 500, 10000
ALL_ANALYSES = ("kde", "gi_star", "dbscan")

TOP_N = 3                  # areas listed per analysis
HOTSPOT_RADIUS_FT = 2640   # half a mile: what counts as "in" a KDE hotspot
GI_Z_90 = 1.65             # |z| for 90% confidence
GI_Z_95 = 1.96             # |z| for 95% confidence
GI_Z_99 = 2.58

MIN_INCIDENTS = 10
# DBSCAN's neighbor lists grow with the square of the point count (the district level
# reaches 2.5 miles), so a big report skips it, the way /clusters caps its date range
MAX_DBSCAN_INCIDENTS = 15000

FT_PER_MILE = 5280
# a few incidents are geocoded outside the county; one of them would stretch every grid across
# hundreds of miles. Anything farther than this from the median incident is left out (the
# county is about 40 miles from its centre to its far corner)
MAX_RADIUS_FT = 60 * FT_PER_MILE



def _clamp(value, low, high):
    return max(low, min(high, value))


def settings_from_args(args):
    """The user's overlay settings from a report request's query string.

    Uses the names the map's own requests use, so the frontend can send what it already has:
      overlays       the overlays the user created on the map, comma-separated: any of kde, gi_star,
                     dbscan. Only these go in the report; with none, the report has no analysis sections
      cluster_set    KDE mode: 0 = all points, 1 = by DBSCAN density level (kde_routes)
      bandwidth      KDE bandwidth in feet, repeated once per density level (kde_routes)
      distance_band  Gi* distance band in feet (gi_star_routes)
      levels         enabled DBSCAN levels, comma-separated, and <level>_eps per level (dbscan_routes)
    Anything left out keeps the map's default; out-of-range numbers are clamped like the sliders.
    Raises ValueError on a malformed value, which the API turns into a 400.
    """
    from ml.dbscan import cluster_levels

    def getlist(name):
        return args.getlist(name) if hasattr(args, "getlist") else ([args[name]] if name in args else [])

    overlays = tuple(o for o in (args.get("overlays") or "").split(",") if o)
    if any(o not in ALL_ANALYSES for o in overlays):
        raise ValueError(f"overlays must be some of {', '.join(ALL_ANALYSES)}")
    try:
        cluster_set = int(args.get("cluster_set", 0))
        bandwidths = [_clamp(float(bw), MIN_BANDWIDTH_FT, MAX_BANDWIDTH_FT) for bw in getlist("bandwidth")]
        distance_band = _clamp(float(args.get("distance_band", GI_DISTANCE_BAND_FT)),
                               MIN_DISTANCE_BAND_FT, MAX_DISTANCE_BAND_FT)
        enabled = args.get("levels")
        enabled = set(enabled.split(",")) if enabled else set(cluster_levels)
        levels = [
            {"name": name, "epsilon": float(args.get(f"{name}_eps", d["epsilon"])),
             "min_pts": d["min_pts"], "color": d["color"]}
            for name, d in cluster_levels.items() if name in enabled
        ]
    except (TypeError, ValueError):
        raise ValueError("report overlay settings must be numbers") from None
    if cluster_set not in (0, 1):
        raise ValueError("cluster_set must be 0 or 1")
    if any(a < b for a, b in zip(bandwidths, bandwidths[1:])):
        raise ValueError("bandwidths must be non-increasing, loosest level first")
    if not levels and ("dbscan" in overlays or cluster_set == 1):
        raise ValueError("at least one DBSCAN level must be enabled")
    return {
        "analyses": overlays,
        "kde_by_level": cluster_set == 1,
        "kde_bandwidths": bandwidths or None,
        "gi_distance_band": distance_band,
        "dbscan_levels": levels,
    }


def default_settings():
    """The map's default parameters, and no overlays: what a report gets when the user created none."""
    return settings_from_args({})


def _project(incidents):
    """Mapped incidents -> (incidents, (N, 2) EPSG:2882 feet array, projection back to lat/lng)."""
    from pyproj import Transformer

    mapped = [i for i in incidents if i.get("lat") is not None and i.get("lng") is not None]
    to_ft = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)
    to_deg = Transformer.from_crs("EPSG:2882", "EPSG:4326", always_xy=True)
    lng = np.array([float(i["lng"]) for i in mapped])
    lat = np.array([float(i["lat"]) for i in mapped])
    x, y = to_ft.transform(lng, lat)
    xy = np.column_stack([x, y])
    if len(xy):
        near = np.hypot(*(xy - np.median(xy, axis=0)).T) <= MAX_RADIUS_FT
        mapped = [inc for inc, keep in zip(mapped, near) if keep]
        xy = xy[near]
    return mapped, xy, to_deg


@functools.lru_cache(maxsize=1)
def _land_polygon():
    """The county land outline Gi* leaves water cells out with; None if it can't be loaded."""
    try:
        from ml.generate_gi_star_snapshots import load_land_polygon

        return load_land_polygon()
    except Exception:
        log.warning("land mask unavailable, Gi* will use every grid cell", exc_info=True)
        return None


def _describe(incidents, mask):
    """Dominant city and incident type among the incidents selected by `mask`."""
    chosen = [inc for inc, keep in zip(incidents, mask) if keep]
    cities = Counter((i.get("city") or "").strip().title() for i in chosen)
    cities.pop("", None)
    types = Counter((i.get("nature") or "").strip().title() for i in chosen)
    types.pop("", None)
    return {
        "city": cities.most_common(1)[0][0] if cities else None,
        "top_type": types.most_common(1)[0][0] if types else None,
        "count": len(chosen),
    }


def _kde(incidents, xy, to_deg, settings, shared):
    from ml.kde import KDEHeatMap

    user_bws = settings["kde_bandwidths"]
    if settings["kde_by_level"]:
        # the map's "by cluster density level" mode: each DBSCAN density level gets its own bandwidth
        db = _fit_dbscan(xy, settings, shared)
        point_levels = db.density_levels
        present = sorted(set(point_levels.tolist()) - {-1})
        if not present:
            raise ValueError("skipped: the cluster analysis put every incident in noise, "
                             "so there is nothing to weight by density level")
        if user_bws and len(user_bws) == len(db.levels):
            per_level = user_bws                      # one slider per enabled level
        elif user_bws and len(user_bws) == len(present):
            per_level = dict(zip(present, user_bws))  # one slider per level the map found
        else:
            per_level = [KDE_BANDWIDTH_FT] * len(db.levels)
        bandwidths = [per_level[level] for level in present]
        level_names = [db.levels[level]["name"].title() for level in present]
    else:
        bandwidths = [user_bws[0] if user_bws else KDE_BANDWIDTH_FT]
        level_names = None
        point_levels = np.zeros(len(xy), dtype=int)

    x_min, y_min = xy.min(axis=0) - KDE_PAD_FT
    x_max, y_max = xy.max(axis=0) + KDE_PAD_FT
    kde = KDEHeatMap(
        points=xy,
        cluster_levels=point_levels,
        bandwidths=bandwidths,
        x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
        increment=KDE_INCREMENT_FT,
    )
    surface = kde.density_surface  # shape (len(x_coords), len(y_coords))

    # strongest peaks first, skipping any within two bandwidths of a peak already taken
    remaining = surface.copy()
    reach = int(2 * min(bandwidths) / KDE_INCREMENT_FT)  # lattice steps in one hotspot width
    peaks = []
    for _ in range(TOP_N):
        i, j = np.unravel_index(np.argmax(remaining), remaining.shape)
        if remaining[i, j] <= 0:
            break
        peaks.append((kde.x_coords[i], kde.y_coords[j], remaining[i, j]))
        # blank the square around this peak (a circle's bounding box is close enough here)
        remaining[max(0, i - reach):i + reach + 1, max(0, j - reach):j + reach + 1] = 0

    hotspots = []
    for rank, (px, py, density) in enumerate(peaks, start=1):
        inside = np.hypot(xy[:, 0] - px, xy[:, 1] - py) <= HOTSPOT_RADIUS_FT
        lng, lat = to_deg.transform(px, py)
        hotspots.append({
            "rank": rank,
            "lat": lat, "lng": lng, "x": px, "y": py,
            "share": inside.sum() / len(xy),
            **_describe(incidents, inside),
        })
    return {
        "bandwidths_ft": bandwidths,
        "level_names": level_names,  # None in all-points mode
        "radius_ft": HOTSPOT_RADIUS_FT,
        "hotspots": hotspots,
        "surface": surface,
        "extent": (kde.x_coords[0], kde.x_coords[-1], kde.y_coords[0], kde.y_coords[-1]),
    }


def _gi_star(incidents, xy, to_deg, settings, shared):
    from scipy import ndimage

    from ml.generate_gi_star_snapshots import GI_STAR_CELL_SIZE
    from ml.gi_star.GiStarHeatMap import GiStarHeatMap

    x_min, y_min = xy.min(axis=0) - GI_STAR_CELL_SIZE
    x_max, y_max = xy.max(axis=0) + GI_STAR_CELL_SIZE
    gi = GiStarHeatMap(
        points=xy,
        distance_band=settings["gi_distance_band"],
        x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
        cell_size=GI_STAR_CELL_SIZE,
        land_polygon=_land_polygon(),
    )
    counts = gi.counts
    z = gi.z_scores.reshape(counts.shape)

    hot95 = np.nan_to_num(z, nan=-np.inf) >= GI_Z_95
    hot99 = np.nan_to_num(z, nan=-np.inf) >= GI_Z_99
    # neighbouring hot cells are one hot area, diagonals included
    labels, n_areas = ndimage.label(hot95, structure=np.ones((3, 3)))

    # which grid cell every incident falls in, to tie incidents to a hot area
    ix = np.clip(np.digitize(xy[:, 0], gi.x_edges) - 1, 0, counts.shape[0] - 1)
    iy = np.clip(np.digitize(xy[:, 1], gi.y_edges) - 1, 0, counts.shape[1] - 1)
    incident_area = labels[ix, iy]

    x_centers = (gi.x_edges[:-1] + gi.x_edges[1:]) / 2
    y_centers = (gi.y_edges[:-1] + gi.y_edges[1:]) / 2
    areas = []
    for area in range(1, n_areas + 1):
        cells = labels == area
        in_area = incident_area == area
        weights = counts[cells]
        cx = np.average(np.broadcast_to(x_centers[:, None], counts.shape)[cells], weights=weights)
        cy = np.average(np.broadcast_to(y_centers[None, :], counts.shape)[cells], weights=weights)
        lng, lat = to_deg.transform(cx, cy)
        areas.append({
            "cells": int(cells.sum()),
            "max_z": float(np.nanmax(z[cells])),
            "lat": lat, "lng": lng, "x": cx, "y": cy,
            "share": in_area.sum() / len(xy),
            **_describe(incidents, in_area),
        })
    # the single highest-scoring cell, so a report with no hot spot can say what came closest
    strongest = None
    if np.isfinite(z).any():
        i, j = np.unravel_index(np.nanargmax(z), z.shape)
        lng, lat = to_deg.transform(x_centers[i], y_centers[j])
        strongest = {"z": float(z[i, j]), "lat": lat, "lng": lng,
                     **_describe(incidents, (ix == i) & (iy == j))}

    areas.sort(key=lambda a: a["max_z"], reverse=True)
    for rank, area in enumerate(areas[:TOP_N], start=1):
        area["rank"] = rank

    return {
        "distance_band_ft": settings["gi_distance_band"],
        "cell_size_ft": GI_STAR_CELL_SIZE,
        "cells_analyzed": int(np.count_nonzero(~np.isnan(z))),
        "hot_cells_95": int(hot95.sum()),
        "hot_cells_99": int(hot99.sum()),
        "areas": areas[:TOP_N],
        "n_areas": n_areas,
        "strongest": strongest,
        "z": z,
        "extent": (gi.x_edges[0], gi.x_edges[-1], gi.y_edges[0], gi.y_edges[-1]),
    }


def _fit_dbscan(xy, settings, shared):
    """DBSCAN with the user's enabled levels and epsilons, fitted once per report (KDE may need it too)."""
    from ml.dbscan import DBSCANCluster

    if "dbscan" not in shared:
        if len(xy) > MAX_DBSCAN_INCIDENTS:
            raise ValueError(
                f"skipped: DBSCAN is limited to {MAX_DBSCAN_INCIDENTS:,} incidents and this "
                f"report has {len(xy):,}. Choose a shorter date range or a smaller area."
            )
        shared["dbscan"] = DBSCANCluster(xy, levels=settings["dbscan_levels"])  # loosest first, like the map
    return shared["dbscan"]


def _dbscan(incidents, xy, to_deg, settings, shared):
    db = _fit_dbscan(xy, settings, shared)

    out = []
    for level, labels in zip(db.levels, db.labels_per_level):
        sizes = Counter(labels[labels != -1])
        clusters = []
        for rank, (label, size) in enumerate(sizes.most_common(TOP_N), start=1):
            inside = labels == label
            cx, cy = xy[inside].mean(axis=0)
            lng, lat = to_deg.transform(cx, cy)
            clusters.append({"rank": rank, "size": size, "lat": lat, "lng": lng,
                             **{k: v for k, v in _describe(incidents, inside).items() if k != "count"}})
        out.append({
            "name": level["name"].title(),
            "epsilon_ft": level["epsilon"],
            "min_pts": level["min_pts"],
            "color": level["color"],
            "n_clusters": len(sizes),
            "noise": int((labels == -1).sum()),
            "clustered_share": float((labels != -1).mean()),
            "top_clusters": clusters,
        })
    return {"levels": out, "density_levels": db.density_levels, "xy": xy}


def analyze(incidents, run=ALL_ANALYSES, settings=None):
    """Run the requested analyses with the user's settings (the map's defaults if None).

    Returns {"n": mapped incident count, "settings": what was used, <name>: result | {"error": why}}.
    """
    settings = settings or default_settings()
    shared = {}
    steps = {"kde": _kde, "gi_star": _gi_star, "dbscan": _dbscan}
    try:
        mapped, xy, to_deg = _project(incidents)
    except Exception:
        log.warning("could not project incidents for the analyses", exc_info=True)
        return {"n": 0, **{name: {"error": "unavailable: the analysis could not be completed"} for name in run}}
    result = {"n": len(mapped), "left_out": len(incidents) - len(mapped), "settings": settings}
    for name in run:
        if len(mapped) < MIN_INCIDENTS:
            result[name] = {"error": f"skipped: needs at least {MIN_INCIDENTS} mapped incidents"}
            continue
        try:
            result[name] = steps[name](mapped, xy, to_deg, settings, shared)
        except ValueError as e:
            result[name] = {"error": str(e)}
        except Exception:
            log.warning("%s analysis failed", name, exc_info=True)
            result[name] = {"error": "unavailable: the analysis could not be completed"}
    return result
