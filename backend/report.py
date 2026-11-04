import io
import re
import base64
import math
import datetime
from collections import Counter

from PIL import Image as PILImage, ImageColor, ImageDraw

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import ListedColormap, Normalize
from matplotlib.patches import Patch

from staticmap import StaticMap, CircleMarker
from reportlab.platypus import KeepTogether
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    Table, TableStyle, HRFlowable,
)

_NAVY  = colors.HexColor("#1e3a5f")
_LIGHT = colors.HexColor("#f0f4f8")
_RULE  = colors.HexColor("#ddd")

# keyed on the category codes from /api/v1/incident-types, in lowercase
_NATURE_COLORS = {
    "violent":     "#d62728",
    "firearm":     "#8c1c13",
    "sex_offense": "#9467bd",
    "burglary":    "#ff7f0e",
    "theft":       "#e6a817",
    "vehicle":     "#bcbd22",
    "fraud":       "#17becf",
    "drugs":       "#2ca02c",
    "harassment":  "#e377c2",
    "disturbance": "#1f77b4",
    "traffic":     "#6baed6",
    "death":       "#2d2d2d",
    "animal":      "#8c564b",
    "hazard":      "#ffd700",
    "other":       "#7f8c8d",
}


def _incident_color(nature):
    if not nature:
        return "#7f8c8d"
    key = nature.strip().lower().split()[0] if nature.strip() else ""
    return _NATURE_COLORS.get(key, "#7f8c8d")


def _map_snapshot(incidents, bounds):
    """Download OSM tiles and plot incident dots; returns a PNG BytesIO or None."""
    try:
        m = StaticMap(*_MAP_SIZE, tile_request_timeout=10)
        zoom, (lng_c, lat_c) = _map_view(bounds)

        for inc in incidents:
            lat = inc.get("lat")
            lng = inc.get("lng")
            if lat is not None and lng is not None:
                color = _incident_color(inc.get("nature"))
                # StaticMap expects (longitude, latitude)
                m.add_marker(CircleMarker((float(lng), float(lat)), color, 8))

        image = m.render(zoom=zoom, center=(lng_c, lat_c))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None


# analysis maps: the user's own KDE / Gi* / DBSCAN runs
# The route hands over the JSON response each map route sent, so the report shows exactly what the user saw

_MAP_SIZE = (750, 450)
_OVERLAY_OPACITY = 0.8 
# Analysis.jsx draws the loosest level first; (fill alpha, outline alpha, outline width) per level
_LEVEL_DRAW_ORDER = ["district", "neighborhood", "street"]
_LEVEL_STYLES = {"district": (0.07, 0.45, 1), "neighborhood": (0.14, 0.65, 2), "street": (0.26, 0.85, 2)}
_LEVEL_LABELS = {"district": "District", "neighborhood": "Neighborhood", "street": "Street"}  # as Analysis.jsx
# the KDE response's cluster_set: which of the map's two KDE radio buttons made it
_KDE_SETS = {0: "All Points", 1: "By Cluster Density Level"}


def _tile_x(lng, zoom):
    return (lng + 180.0) / 360.0 * 2 ** zoom


def _tile_y(lat, zoom):
    r = math.radians(lat)
    return (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * 2 ** zoom


def _map_view(bounds):
    """The closest zoom that fits all of `bounds` in the map frame, and its (lng, lat) centre."""
    w, h = _MAP_SIZE
    zoom = 1
    for z in range(17, 0, -1):
        width = (_tile_x(bounds["east"], z) - _tile_x(bounds["west"], z)) * 256
        height = (_tile_y(bounds["south"], z) - _tile_y(bounds["north"], z)) * 256
        if width <= w and height <= h:
            zoom = z
            break
    center = ((bounds["east"] + bounds["west"]) / 2, (bounds["north"] + bounds["south"]) / 2)
    return zoom, center


def _px(lng, lat, zoom, center):
    """Web Mercator (lng, lat) -> pixel on a rendered StaticMap, with staticmap's own tile maths."""
    w, h = _MAP_SIZE
    return ((_tile_x(lng, zoom) - _tile_x(center[0], zoom)) * 256 + w / 2,
            (_tile_y(lat, zoom) - _tile_y(center[1], zoom)) * 256 + h / 2)


def _base_map(bounds):
    """The report's map frame with no markers, as an RGBA PIL image."""
    zoom, center = _map_view(bounds)
    m = StaticMap(*_MAP_SIZE, tile_request_timeout=10)
    return m.render(zoom=zoom, center=center).convert("RGBA"), zoom, center


def _heatmap_on_map(bounds, image_url, image_bounds):
    """A KDE or Gi* PNG stretched between its bounds' corners, as Leaflet's imageOverlay places it."""
    base, zoom, center = _base_map(bounds)
    png_bytes = base64.b64decode(image_url.split(",", 1)[1])  # "data:image/png;base64,..."
    overlay = PILImage.open(io.BytesIO(png_bytes)).convert("RGBA")
    x0, y0 = _px(image_bounds["west"], image_bounds["north"], zoom, center)
    x1, y1 = _px(image_bounds["east"], image_bounds["south"], zoom, center)

    # only the part of the PNG inside the report's frame, so a small area doesn't scale up the whole county
    vx0, vy0 = max(x0, 0), max(y0, 0)
    vx1, vy1 = min(x1, base.width), min(y1, base.height)
    if vx1 - vx0 >= 1 and vy1 - vy0 >= 1:
        sx, sy = overlay.width / (x1 - x0), overlay.height / (y1 - y0)
        part = overlay.crop((round((vx0 - x0) * sx), round((vy0 - y0) * sy),
                             round((vx1 - x0) * sx), round((vy1 - y0) * sy)))
        part = part.resize((round(vx1 - vx0), round(vy1 - vy0)), PILImage.BILINEAR)
        part.putalpha(part.getchannel("A").point(lambda a: round(a * _OVERLAY_OPACITY)))
        base.alpha_composite(part, (round(vx0), round(vy0)))
    return _png(base)


def _level_order(levels):
    """The levels the user ran, loosest first, the order the map draws them in."""
    return [lvl for lvl in _LEVEL_DRAW_ORDER if lvl in levels] + \
           [lvl for lvl in levels if lvl not in _LEVEL_DRAW_ORDER]


def _cluster_polygons(level):
    """A level's cluster outlines; its other features are the incident points."""
    return [f for f in level.get("features", [])
            if (f.get("geometry") or {}).get("type") in ("Polygon", "MultiPolygon")]


def _clusters_on_map(bounds, levels):
    """DBSCAN cluster outlines, every level the user ran, styled like the map."""
    base, zoom, center = _base_map(bounds)
    for level in _level_order(levels):
        fill_a, line_a, width = _LEVEL_STYLES.get(level, (0.14, 0.65, 2))
        layer = PILImage.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for feature in _cluster_polygons(levels[level]):
            geom = feature["geometry"]
            rings = [geom["coordinates"][0]] if geom["type"] == "Polygon" else [p[0] for p in geom["coordinates"]]
            rgb = ImageColor.getrgb(feature.get("properties", {}).get("color", "#555555"))[:3]
            for ring in rings:
                pts = [_px(lng, lat, zoom, center) for lng, lat in ring]
                draw.polygon(pts, fill=rgb + (round(255 * fill_a),))
                draw.line(pts + pts[:1], fill=rgb + (round(255 * line_a),), width=width)
        base.alpha_composite(layer)
    return _png(base)


def _png(image):
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf


def _heatmap_legend(legend, caption=None):
    """A KDE or Gi* response's color bar: its colors and ticks, under its caption or `caption`."""
    fig, ax = plt.subplots(figsize=(3.4, 0.32))
    norm = Normalize(vmin=legend["vmin"], vmax=legend["vmax"])
    bar = fig.colorbar(ScalarMappable(norm=norm, cmap=ListedColormap(legend["colors"])),
                       cax=ax, orientation="horizontal")
    # the ticks always include the min and max; drop any tick so close to the next one
    # that their labels would run together, keeping both ends
    ticks = sorted(legend["ticks"])
    gap = 0.12 * (legend["vmax"] - legend["vmin"])
    kept = [ticks[0]]
    for t in ticks[1:-1]:
        if t - kept[-1] >= gap and ticks[-1] - t >= gap:
            kept.append(t)
    kept.append(ticks[-1])
    bar.set_ticks(kept)
    # 2 significant figures, like Number(t.toPrecision(2)) on the map; 3 at the ends so min and max read true
    bar.set_ticklabels([f"{float(f'{t:.{3 if i in (0, len(kept) - 1) else 2}g}'):g}" for i, t in enumerate(kept)])
    bar.ax.tick_params(labelsize=7, length=3, width=0.5)
    bar.outline.set_linewidth(0.5)
    ax.set_title(caption or legend.get("caption", ""), fontsize=8, loc="left")
    return _save_chart(fig)


def _kde_caption(caption):
    """The KDE caption with its display scale written out: "(x 1e+12)" becomes "(×10¹²)"."""
    match = re.search(r"[x×]\s*1e([+-]?\d+)", caption or "")
    if not match:
        return "Incident density"
    power = str(int(match.group(1))).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    return f"Incident density (×10{power})"


def _cluster_legend(levels):
    """One swatch per cluster level that found clusters, in that level's color."""
    handles = []
    for level in _level_order(levels):
        polygons = _cluster_polygons(levels[level])
        if polygons:
            color = polygons[0].get("properties", {}).get("color", "#555555")
            handles.append(Patch(facecolor=color, edgecolor=color, label=_LEVEL_LABELS.get(level, level.title())))
    if not handles:
        return None
    fig = plt.figure(figsize=(1.6 * len(handles), 0.3))
    fig.legend(handles=handles, loc="center", ncol=len(handles), frameon=False, fontsize=8,
               handlelength=1.2, handleheight=1.0, columnspacing=1.6)
    return _save_chart(fig)


# what each map shows, in plain words, printed under it
_MAP_CAPTIONS = {
    "dbscan": "DBSCAN finds clusters: places where many incidents happened close together. Each shaded "
              "shape is one cluster, found at up to three scales: District (broad areas), Neighborhood, "
              "and Street (tight, block-level concentrations). Incidents outside every shape are not part "
              "of any cluster.",
    "kde": "KDE (kernel density estimation) shows how concentrated incidents are. Each incident adds a "
           "little density to the area around it, so places with more incidents nearby go from blue "
           "(fewer) through yellow to red (most). It shows where incidents pile up, not whether that is unusual.",
    "gi_star": "Gi* (Getis-Ord) tests whether an area has more incidents than expected compared with the "
               "rest of the map. Yellow to red areas are hot spots (more than expected, red the strongest), "
               "blue areas are cold spots (fewer), and white is about as expected. The z-score shows how "
               "strong that is: beyond ±1.96 is statistically significant at 95% confidence.",
}


_FT_PER_DEGREE = 364_000  # feet per degree of latitude, near enough for distances across the county
_SPOTS = 3
# below this many incidents in the report's area, the densest spots are only an incident or two
# each, so the maps go in without their list
_MIN_INCIDENTS_FOR_SPOTS = 25
_MIN_SPOT_INCIDENTS = 3  # a listed spot has at least this many incidents around it
_GI_SIGNIFICANT = 1.96  # z-score for 95% confidence; weaker Gi* areas aren't listed


def _map_values(response, bounds):
    """The value under each colored pixel of a KDE or Gi* image, read back through its legend's colors.

    The image is in latitude/longitude, stretched between its bounds, and the legend samples the
    color scale evenly from vmin to vmax, so a pixel's nearest legend color gives its value."""

    legend, box = response["legend"], response["bounds"]
    png_bytes = base64.b64decode(response["image"].split(",", 1)[1])
    rgba = np.asarray(PILImage.open(io.BytesIO(png_bytes)).convert("RGBA")).astype(np.int64)
    height, width = rgba.shape[:2]
    lats = box["north"] - (np.arange(height) + 0.5) / height * (box["north"] - box["south"])
    lngs = box["west"] + (np.arange(width) + 0.5) / width * (box["east"] - box["west"])

    palette = np.array([ImageColor.getrgb(c)[:3] for c in legend["colors"]])
    packed = (rgba[..., 0] << 16) | (rgba[..., 1] << 8) | rgba[..., 2]
    shown = rgba[..., 3] > 0
    shown &= ((lats >= bounds["south"]) & (lats <= bounds["north"]))[:, None]
    shown &= ((lngs >= bounds["west"]) & (lngs <= bounds["east"]))[None, :]
    step = (legend["vmax"] - legend["vmin"]) / (len(palette) - 1)
    flat = (palette == palette[-1]).all(axis=1)
    top_index = len(palette) - 1
    while top_index > 0 and flat[top_index - 1]:
        top_index -= 1
    values = np.full((height, width), np.nan)
    if shown.any():
        colors, which = np.unique(packed[shown], return_inverse=True)
        rgb = np.stack([colors >> 16, (colors >> 8) & 255, colors & 255], axis=1)
        nearest = ((rgb[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
        values[shown] = legend["vmin"] + nearest[which.ravel()] * step
    return values, lats, lngs, legend["vmin"] + top_index * step


def _distance_ft(lat, lng, lats, lngs):
    return np.hypot((lats - lat) * _FT_PER_DEGREE, (lngs - lng) * _FT_PER_DEGREE * math.cos(math.radians(lat)))


def _top_spots(values, lats, lngs, apart_ft, n=_SPOTS):
    """The highest points on the map, each at least apart_ft from the others, highest first: [(lat, lng, value)].
    The first n are the top n; a few more follow so ties with the nth can be told apart.

    Spots with the same reading, as on a scale's flat top color, rank by how big their patch of it is."""
    values = values.copy()
    grid_lat, grid_lng = np.meshgrid(lats, lngs, indexing="ij")
    found = []
    while len(found) < 5 * n and not np.isnan(values).all():
        row, col = np.unravel_index(np.nanargmax(values), values.shape)
        peak = values[row, col]
        near = _distance_ft(lats[row], lngs[col], grid_lat, grid_lng) < apart_ft
        # the peak color often covers a patch, so take its middle
        top = near & (values >= peak)
        found.append((peak, top.sum(), grid_lat[top].mean(), grid_lng[top].mean()))
        values[near] = np.nan
    found.sort(key=lambda spot: spot[:2], reverse=True)
    return [(lat, lng, peak) for peak, _, lat, lng in found]


def _nearby(lat, lng, incidents, radius_ft):
    """The incidents within radius_ft of a spot, and 'near Fort Myers ' from their most common city."""
    nearby = [i for i in incidents if i.get("lat") is not None and i.get("lng") is not None
              and _distance_ft(lat, lng, float(i["lat"]), float(i["lng"])) <= radius_ft]
    cities = Counter((i.get("city") or "").strip().title() for i in nearby if (i.get("city") or "").strip())
    return nearby, f"near {cities.most_common(1)[0][0]} " if cities else ""


def _spot_text(rank, lat, lng, incidents, radius_ft, value_text):
    """'1. Near Fort Myers (26.6406, -81.8723): <value>; 85 incidents within 1,500 ft, most often Theft.'"""
    nearby, place = _nearby(lat, lng, incidents, radius_ft)
    text = f"<b>{rank}.</b> {_sentence(place) if place else ''}({lat:.4f}, {lng:.4f}): {value_text}; " \
           f"<b>{len(nearby):,}</b> incident{'s' if len(nearby) != 1 else ''} within {radius_ft:,.0f} ft"
    if nearby:
        text += f", most often {_type_label(Counter(_type_key(i) for i in nearby).most_common(1)[0][0])}"
    return text + "."


def _gi_confidence(z):
    return f"a hot spot at {'99%' if z >= 2.58 else '95%'} confidence"


def _map_spots(kind, response, bounds, incidents):
    """The densest KDE spots or strongest Gi* hot spots the map shows, as report paragraphs' text."""
    radius = max(response.get("bandwidths") or [1500]) if kind == "kde" else response.get("distance_band") or 5280
    values, lats, lngs, top = _map_values(response, bounds)
    if kind == "gi_star":
        values[values < _GI_SIGNIFICANT] = np.nan  # only significant hot spots
    # a spot with hardly any incidents around it is the edge of someone else's peak, not a place worth naming
    found = [(lat, lng, value) for lat, lng, value in _top_spots(values, lats, lngs, apart_ft=max(2 * radius, 5280))
             if len(_nearby(lat, lng, incidents, radius)[0]) >= _MIN_SPOT_INCIDENTS]
    spots = found[:_SPOTS]
    if not spots:
        if kind == "gi_star":
            return ["No statistically significant hot spots: no area on this map has more incidents than "
                    f"expected at 95% confidence (z-score {_GI_SIGNIFICANT} or higher)."]
        return []
    count = f"{len(spots)} " if len(spots) > 1 else ""
    if kind == "kde":
        heading = f"The {count}densest spot{'s' if len(spots) > 1 else ''} on this map " \
                  "(density read from its colors, in the legend's units):"
    else:
        heading = f"The {count}strongest hot spot{'s' if len(spots) > 1 else ''} on this map " \
                  "(z-score read from its colors):"
    lines = [heading]
    vmin, vmax = response["legend"]["vmin"], response["legend"]["vmax"]
    flat_top = vmax - top > 0.02 * (vmax - vmin)  # Gi*'s red covers its top few tenths
    for rank, (lat, lng, value) in enumerate(spots, 1):
        number = f"{value:.2f}" if kind == "gi_star" else f"{float(f'{value:.3g}'):,g}"
        if flat_top and value >= top:
            number += " or higher (the top of the color scale)"
        if kind == "kde":
            value_text = f"density <b>{number}</b>"
        else:
            value_text = f"z-score <b>{number}</b>, {_gi_confidence(value)}"
        lines.append(_spot_text(rank, lat, lng, incidents, radius, value_text))
    # areas past the last listed one that read just as high, so the list doesn't hide them
    tied = [(lat, lng) for lat, lng, value in found[_SPOTS:] if flat_top and value >= top]
    if tied:
        places = "; ".join(f"{_nearby(lat, lng, incidents, radius)[1]}({lat:.4f}, {lng:.4f})" for lat, lng in tied)
        lines.append(f"{len(tied)} more area{'s' if len(tied) != 1 else ''} also reach{'' if len(tied) != 1 else 'es'} "
                     f"the top of the color scale, with smaller patches: {places}.")
    return lines


def _run_parameters(analyses):
    """The settings each of the user's runs was made with, one line per run, for the report details."""
    analyses = analyses or {}
    lines = []
    dbscan = analyses.get("dbscan")
    if dbscan:
        try:
            levels = dbscan["frames"][0]["levels"]
            configs = dbscan.get("level_configs") or {}
            parts = []
            for level in _level_order(levels):
                meta = levels[level].get("metadata") or {}
                eps = meta.get("eps", (configs.get(level) or {}).get("epsilon"))
                min_pts = meta.get("min_pts", (configs.get(level) or {}).get("min_pts"))
                part = f"{_LEVEL_LABELS.get(level, level.title())} ε {eps:,.0f} ft, min {min_pts} points"
                if "n_clusters" in meta:
                    part += f", {meta['n_clusters']} cluster{'s' if meta['n_clusters'] != 1 else ''}"
                parts.append(part)
            lines.append("DBSCAN: " + "; ".join(parts))
        except Exception:
            pass
    kde = analyses.get("kde")
    if kde and kde.get("bandwidths"):
        bandwidths = kde["bandwidths"]
        if kde.get("cluster_set") == 1 and len(bandwidths) == len(_LEVEL_DRAW_ORDER):
            # by cluster density level: one bandwidth per level, loosest level first
            text = ", ".join(f"{_LEVEL_LABELS[lvl]} {bw:,.0f} ft" for lvl, bw in zip(_LEVEL_DRAW_ORDER, bandwidths))
        else:
            text = ", ".join(f"{bw:,.0f} ft" for bw in bandwidths)
        mode = _KDE_SETS.get(kde.get("cluster_set"))
        lines.append(f"KDE{f' ({mode})' if mode else ''}: bandwidth {text}")
    gi_star = analyses.get("gi_star")
    if gi_star and gi_star.get("distance_band") is not None:
        lines.append(f"Gi*: distance band {gi_star['distance_band']:,.0f} ft")
    return lines


def _analysis_maps(bounds, analyses, incidents):
    """[(title, map PNG or None, legend PNG or None, caption, [spot lines])] for each run the user sent,
    in DBSCAN, KDE, Gi* order."""
    maps = []
    for kind, title in (("dbscan", "DBSCAN Clusters"), ("kde", "KDE Heatmap"), ("gi_star", "Gi* Heatmap")):
        response = (analyses or {}).get(kind)
        if not response:
            continue
        legend = None
        try:
            if kind == "dbscan":
                levels = response["frames"][0]["levels"]
                png = _clusters_on_map(bounds, levels)
                legend = _cluster_legend(levels)
            else:
                if kind == "kde" and response.get("cluster_set") in _KDE_SETS:
                    title = f"{title} ({_KDE_SETS[response['cluster_set']]})"
                png = _heatmap_on_map(bounds, response["image"], response["bounds"])
                if response.get("legend") and kind == "kde":
                    caption = _kde_caption(response["legend"].get("caption"))
                    legend = _heatmap_legend(response["legend"], caption=caption)
                elif response.get("legend"):
                    legend = _heatmap_legend(response["legend"])
        except Exception:
            png = None  # no map tiles, or a response the report can't read
        spots = []
        if png and kind != "dbscan" and len(incidents) < _MIN_INCIDENTS_FOR_SPOTS:
            spots = [f"Only {len(incidents)} incident{'s' if len(incidents) != 1 else ''} in this area, too few "
                     f"to single out its {'densest spots' if kind == 'kde' else 'hot spots'}."]
        elif png and kind != "dbscan" and response.get("legend"):
            try:
                spots = _map_spots(kind, response, bounds, incidents)
            except Exception:
                spots = []  # the map still goes in without its list
        maps.append((title, png, legend if png else None, _MAP_CAPTIONS[kind], spots))
    return maps


def _parse_date(inc):
    d = inc.get("occuredDate")
    if not d:
        return None
    try:
        return datetime.datetime.fromisoformat(d.replace(" ", "T")[:19])
    except Exception:
        return None


# the labels the map's type filter shows for each category code (migration 0007)
_CATEGORY_LABELS = {
    "violent":     "Violent Crime",
    "firearm":     "Shots Fired & Firearms",
    "sex_offense": "Sex Offense",
    "burglary":    "Burglary",
    "theft":       "Theft & Property",
    "vehicle":     "Vehicle Crime",
    "fraud":       "Fraud & Financial",
    "drugs":       "Drugs & Narcotics",
    "harassment":  "Harassment & Stalking",
    "disturbance": "Disturbance",
    "traffic":     "Traffic",
    "death":       "Death Investigation",
    "animal":      "Animal",
    "hazard":      "Bomb & Hazard",
    "other":       "Other",
}

# the charts colour the biggest few types and fold the rest into one grey band
_TOP_TYPES = 5
_REST = "_rest"
_REST_COLOR = "#c7ccd1"
_BG = "#f8f9fa"


def _type_key(inc):
    return (inc.get("nature") or "other").strip().lower()


def _type_label(key):
    if key == _REST:
        return "All other types"
    return _CATEGORY_LABELS.get(key, key.replace("_", " ").title())


def _type_color(key):
    return _REST_COLOR if key == _REST else _NATURE_COLORS.get(key, "#7f8c8d")


def _published_through(incidents, end_date):
    """The last day the Sheriff's incident log reaches, when a recent report runs past it; else None.
    Traffic comes from a live feed, everything else from a log published 48 hours late, so the
    last days of a recent report hold Traffic only."""
    if end_date < datetime.date.today() - datetime.timedelta(days=3):
        return None  # an older report: the log has caught up

    last = None
    for inc in incidents:
        if _type_key(inc) == "traffic":
            continue
        d = _parse_date(inc)
        if d and (last is None or d.date() > last):
            last = d.date()

    if last is None or last >= end_date:
        return None
    return last


def _stack_keys(top, incidents):
    """The top types, then the grey 'all other types' band if anything falls outside them."""
    rest = any(_type_key(inc) not in top for inc in incidents)
    return list(top) + ([_REST] if rest else [])


def _bucket(inc, top):
    key = _type_key(inc)
    return key if key in top else _REST


def _style_axes(ax):
    ax.set_facecolor(_BG)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=7.5)


def _legend_below(fig, keys, ncol=3):
    handles = [plt.Rectangle((0, 0), 1, 1, color=_type_color(k)) for k in keys]
    fig.legend(handles, [_type_label(k) for k in keys], loc="lower center", ncol=ncol,
               fontsize=7.5, frameon=False, bbox_to_anchor=(0.5, -0.01))


def _hour_label(h):
    return f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}"


def _bar_chart(nature_counts, total):
    """Horizontal bars, one per incident type (top 12), coloured like the map, labelled with count and share."""
    items = nature_counts.most_common(12)
    keys = [k.strip().lower() for k, _ in items]
    vals = [v for _, v in items]

    fig, ax = plt.subplots(figsize=(7, max(2.5, len(items) * 0.38)))
    fig.patch.set_facecolor(_BG)
    _style_axes(ax)

    bars = ax.barh([_type_label(k) for k in keys][::-1], vals[::-1],
                   color=[_type_color(k) for k in keys][::-1], edgecolor="none", height=0.6)
    ax.set_xlabel("Number of incidents", fontsize=8.5)
    ax.set_title(f"What types of incidents were reported ({total:,} total)",
                 fontsize=10.5, fontweight="bold", pad=10, loc="left")
    for bar, val in zip(bars, vals[::-1]):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                f"  {val:,}  ({val / total:.0%})", va="center", ha="left", fontsize=7.5, color="#333")
    ax.set_xlim(0, max(vals) * 1.22)  # room for the labels

    plt.tight_layout()
    return _save_chart(fig)


def _city_chart(incidents, top):
    """Stacked horizontal bars: the 10 busiest cities, each split into the top incident types."""
    by_city = {}
    for inc in incidents:
        city = (inc.get("city") or "").strip().title() or "Unknown"
        by_city.setdefault(city, Counter())[_bucket(inc, top)] += 1
    cities = sorted(by_city, key=lambda c: sum(by_city[c].values()), reverse=True)[:10][::-1]
    keys = _stack_keys(top, incidents)

    fig, ax = plt.subplots(figsize=(7, max(2.6, len(cities) * 0.36 + 0.9)))
    fig.patch.set_facecolor(_BG)
    _style_axes(ax)

    left = np.zeros(len(cities))
    for key in keys:
        vals = np.array([by_city[c].get(key, 0) for c in cities])
        ax.barh(cities, vals, left=left, color=_type_color(key), edgecolor="white", linewidth=0.4, height=0.65)
        left += vals
    for y, total in enumerate(left):
        ax.text(total, y, f"  {int(total):,}", va="center", ha="left", fontsize=7.5, color="#333")
    ax.set_xlim(0, left.max() * 1.12)
    ax.set_xlabel("Number of incidents", fontsize=8.5)
    ax.set_title("Where incidents happened, and what kind", fontsize=10.5, fontweight="bold", pad=10, loc="left")

    _legend_below(fig, keys)
    plt.tight_layout(rect=(0, 0.1, 1, 1))
    return _save_chart(fig)


def _line_chart(incidents, start_date, end_date, top, published_through=None):
    """Stacked area over time, split into the top incident types; weekly once the range passes ~3 months.
    Days after published_through are shaded, and left out of the average."""
    num_days = (end_date - start_date).days
    weekly = num_days > 92
    step = 7 if weekly else 1

    keys = _stack_keys(top, incidents)
    periods = [start_date + datetime.timedelta(days=i) for i in range(0, num_days + 1, step)]
    counts = {k: np.zeros(len(periods)) for k in keys}
    for inc in incidents:
        d = _parse_date(inc)
        if d:
            i = (d.date() - start_date).days // step
            if 0 <= i < len(periods):
                counts[_bucket(inc, top)][i] += 1

    fig, ax = plt.subplots(figsize=(7, 3.2))
    fig.patch.set_facecolor(_BG)
    _style_axes(ax)

    ax.stackplot(periods, [counts[k] for k in keys], colors=[_type_color(k) for k in keys],
                 edgecolor="white", linewidth=0.3)
    totals = sum(counts.values())
    complete = []  # each period's total, leaving out the days not yet published
    for period, period_total in zip(periods, totals):
        if published_through is None or period <= published_through:
            complete.append(period_total)
    avg = sum(complete) / len(complete) if complete else 0
    ax.axhline(avg, color="#333", linestyle="--", linewidth=0.8)
    ax.text(periods[-1], avg, f" avg {avg:.0f}", va="bottom", ha="right", fontsize=7, color="#333")
    if published_through:
        pending = datetime.datetime.combine(published_through, datetime.time(12))
        ax.axvspan(pending, periods[-1], color="#999", alpha=0.15, linewidth=0)
        ax.text(pending + (datetime.datetime.combine(periods[-1], datetime.time()) - pending) / 2,
                ax.get_ylim()[1] * 0.95, "Traffic only:\nothers not yet published",
                ha="center", va="top", fontsize=7, style="italic", color="#555")

    unit = "week" if weekly else "day"
    ax.set_title(f"Incidents per {unit}, split by type", fontsize=10.5, fontweight="bold", pad=10, loc="left")
    ax.set_ylabel(f"Incidents per {unit}", fontsize=8.5)
    ax.set_xlim(periods[0], periods[-1])
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

    _legend_below(fig, keys)
    plt.tight_layout(rect=(0, 0.1, 1, 1))
    return _save_chart(fig), unit, totals, periods, avg


def _timing_chart(incidents, top):
    """Hour of day and day of week side by side, both split into the top incident types, one legend."""
    keys = _stack_keys(top, incidents)
    hours = {k: np.zeros(24) for k in keys}
    days = {k: np.zeros(7) for k in keys}
    for inc in incidents:
        d = _parse_date(inc)
        if d:
            key = _bucket(inc, top)
            hours[key][d.hour] += 1
            days[key][d.weekday()] += 1

    fig, (ax_h, ax_d) = plt.subplots(1, 2, figsize=(7, 3.1), gridspec_kw={"width_ratios": [1.6, 1]})
    fig.patch.set_facecolor(_BG)
    for ax, data, x in ((ax_h, hours, np.arange(24)), (ax_d, days, np.arange(7))):
        _style_axes(ax)
        bottom = np.zeros(len(x))
        for key in keys:
            ax.bar(x, data[key], bottom=bottom, color=_type_color(key), edgecolor="none", width=0.75)
            bottom += data[key]
        ax.set_ylabel("Incidents", fontsize=8)

    ax_h.set_xticks(range(0, 24, 3))
    ax_h.set_xticklabels([_hour_label(h) for h in range(0, 24, 3)])
    ax_h.set_title("By time of day", fontsize=9.5, fontweight="bold", pad=6, loc="left")
    ax_d.set_xticks(range(7))
    ax_d.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax_d.set_title("By day of week", fontsize=9.5, fontweight="bold", pad=6, loc="left")

    _legend_below(fig, keys)
    plt.tight_layout(rect=(0, 0.12, 1, 1))
    return _save_chart(fig), sum(hours.values()), sum(days.values())


def _chart_image(png, width=6.5 * inch):
    """A chart at full text width, keeping the shape matplotlib drew it in."""
    w, h = ImageReader(png).getSize()
    png.seek(0)
    return Image(png, width=width, height=width * h / w)


def _save_chart(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _sentence(text):
    return text[0].upper() + text[1:]


def _metadata_flowables(h2_s, tbl_style, label_s, value_s, rows):
    return [
        Paragraph("Report Details", h2_s),
        Table([[Paragraph(k, label_s), Paragraph(v, value_s)] for k, v in rows],
              colWidths=[1.7*inch, 4.8*inch], style=tbl_style),
    ]


def generate_pdf(incidents, bounds, start_date, end_date, filters=None, analyses=None):
    """Assemble and return a BytesIO PDF for the given filtered incidents.

    analyses -- the saved responses of the user's map runs, keyed "kde", "gi_star" and "dbscan",
                each only when the user made one: the same JSON /api/v1/kde-heatmap,
                /api/v1/gi-star-heatmap and /api/v1/clusters return. Each is drawn on its own
                map of the report's area.
    filters  -- text describing the filters applied (e.g. "category: BURGLARY; city: FORT MYERS"),
                recorded in the report details; None means no filters.
    """
    buf = io.BytesIO()
    styles = getSampleStyleSheet()

    title_s = ParagraphStyle(
        "RTitle", parent=styles["Title"],
        fontSize=18, textColor=_NAVY, spaceAfter=4,
    )
    sub_s = ParagraphStyle(
        "RSub", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#555"), spaceAfter=2,
    )
    h2_s = ParagraphStyle(
        "RH2", parent=styles["Heading2"],
        fontSize=12, textColor=_NAVY, spaceBefore=14, spaceAfter=6,
    )
    footer_s = ParagraphStyle(
        "RFooter", parent=styles["Normal"],
        fontSize=7.5, textColor=colors.HexColor("#888"),
    )
    body_s = ParagraphStyle(
        "RBody", parent=styles["Normal"],
        fontSize=9, leading=12, spaceAfter=3,
    )
    note_s = ParagraphStyle(
        "RNote", parent=styles["Normal"],
        fontSize=8, leading=10.5, textColor=colors.HexColor("#555"), spaceAfter=4,
    )
    detail_label_s = ParagraphStyle(
        "RDetailLabel", parent=body_s, fontName="Helvetica-Bold", textColor=_NAVY,
    )

    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.85 * inch,  bottomMargin=0.85 * inch,
    )

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    nature_counts = Counter(
        (inc.get("nature") or "Unknown").strip() for inc in incidents
    )
    city_counts = Counter()
    for inc in incidents:
        city = (inc.get("city") or "").strip()
        city_counts[city if city else "Unknown"] += 1
    most_common  = _type_label(nature_counts.most_common(1)[0][0].strip().lower()) if nature_counts else "N/A"
    days_label   = f"{start_date:%b %d, %Y} – {end_date:%b %d, %Y}"
    story = []

    # Title block
    story.append(Paragraph("Lee County Incident Report", title_s))
    story.append(Paragraph(
        f"Generated: {now.strftime('%B %d, %Y at %H:%M UTC')} &nbsp;·&nbsp; Period: {days_label}",
        sub_s,
    ))
    story.append(Paragraph(
        f"Viewport: N {bounds['north']:.4f}° &nbsp; S {bounds['south']:.4f}° &nbsp;"
        f" E {bounds['east']:.4f}° &nbsp; W {bounds['west']:.4f}°",
        sub_s,
    ))
    story.append(Spacer(1, 0.1 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=_RULE, spaceAfter=10))

    # Map snapshot
    map_png = _map_snapshot(incidents, bounds)
    if map_png:
        story.append(Paragraph("Incident Map", h2_s))
        story.append(Image(map_png, width=6.5*inch, height=3.9*inch))
        story.append(Spacer(1, 0.1 * inch))

    # Summary stats
    story.append(Paragraph("Summary", h2_s))
    cell_s = ParagraphStyle(
    "RCell", parent=styles["Normal"],
    fontName="Helvetica-Bold", fontSize=11, leading=13,
    textColor=_NAVY, alignment=1,  # 1 = centered
)
    stat_data = [
        ["Total Incidents", "Most Common Type", "Period", "Data Source"],
        [
        Paragraph(str(len(incidents)), cell_s),
        Paragraph(most_common, cell_s),
        Paragraph(days_label, cell_s),
        Paragraph("LCSO Public Log", cell_s),
    ],
    ]
    stat_tbl = Table(stat_data, colWidths=[1.5*inch, 2*inch, 1.3*inch, 1.9*inch])
    stat_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        ("FONTSIZE",      (0, 1), (-1, 1), 12),
        ("FONTNAME",      (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (0, 1), (-1, 1), _NAVY),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND",    (0, 1), (-1, 1), _LIGHT),
        ("GRID",          (0, 0), (-1, -1), 0.5, _RULE),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(stat_tbl)
    story.append(Spacer(1, 0.1 * inch))

    # Charts: every one is split into the same top types, in the same colours as the map
    total = len(incidents)
    top_types = [k.strip().lower() for k, _ in nature_counts.most_common(_TOP_TYPES)]

    def chart_block(title, png, caption):
        return KeepTogether([Paragraph(title, h2_s), _chart_image(png), Paragraph(caption, note_s)])

    # Incidents by type
    if nature_counts:
        lead_key, lead_n = nature_counts.most_common(1)[0]
        caption = (f"<b>{_type_label(lead_key.strip().lower())}</b> is the most common type, "
                   f"{lead_n:,} of {total:,} incidents ({lead_n / total:.0%}). "
                   "Bar colours match the map and are used in every chart below.")
        if any(k.strip().lower() == "disturbance" for k in nature_counts):
            caption += (" <i>Disturbance</i> is the Sheriff's Office catch-all category for general "
                        "disturbance calls (and domestic disturbances); the public log gives no further detail, "
                        "so it can't be broken down any further.")
        story.append(chart_block("Incidents by Type", _bar_chart(nature_counts, total), caption))
        story.append(Spacer(1, 0.05 * inch))

    # Incidents by city
    if city_counts:
        busiest_city, city_n = city_counts.most_common(1)[0]
        city_types = Counter(_type_key(i) for i in incidents
                             if ((i.get("city") or "").strip() or "Unknown") == busiest_city)
        caption = (f"<b>{busiest_city.title()}</b> has the most incidents, {city_n:,} ({city_n / total:.0%} of the total), "
                   f"most often {_type_label(city_types.most_common(1)[0][0])}. "
                   "Each bar is split by incident type.")
        story.append(chart_block("Incidents by City", _city_chart(incidents, top_types), caption))
        story.append(Spacer(1, 0.05 * inch))

    # Trend over time
    published = _published_through(incidents, end_date)
    if published:
        first, days = published + datetime.timedelta(days=1), (end_date - published).days
        span = f"{first:%b %d}" if days == 1 else f"{first:%b %d} – {end_date:%b %d}"
        pending_note = (f" <b>{span}</b> {'shows' if days == 1 else 'show'} Traffic only: the other types "
                        "are not yet published for those days. Traffic comes from the Sheriff's live traffic feed; "
                        "everything else comes from its incident log, which is published 48 hours late.")
    trend_png, unit, per_period, periods, avg = _line_chart(incidents, start_date, end_date, top_types, published)
    if per_period.any():
        peak = int(per_period.argmax())
        when = f"the week of {periods[peak]:%b %d}" if unit == "week" else f"{periods[peak]:%A, %b %d}"
        caption = (f"An average of <b>{avg:.1f}</b> incidents per {unit} (dashed line"
                   f"{', not counting the shaded days' if published else ''}). "
                   f"The busiest {unit} was <b>{when}</b>, with {int(per_period[peak]):,}.")
        if published:
            caption += pending_note
    else:
        caption = "No incidents with a usable date in this period."
    story.append(chart_block(f"{'Weekly' if unit == 'week' else 'Daily'} Incident Trend", trend_png, caption))
    story.append(Spacer(1, 0.05 * inch))

    # Time of day / day of week
    timing_png, per_hour, per_day = _timing_chart(incidents, top_types)
    if per_hour.any():
        h = int(per_hour.argmax())
        day = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][int(per_day.argmax())]
        caption = (f"The busiest hour is <b>{_hour_label(h)}–{_hour_label((h + 1) % 24)}</b> "
                   f"({int(per_hour[h]):,} incidents) and the busiest day is <b>{day}</b> "
                   f"({int(per_day.max()):,}). Times are Eastern.")
        if published:
            caption += (f" {span} {'holds' if days == 1 else 'hold'} Traffic only so far, "
                        "so the days of the week they fall on are short of the other types.")
    else:
        caption = "No incidents with a usable time in this period."
    story.append(chart_block("Incident Timing", timing_png, caption))
    story.append(Spacer(1, 0.1 * inch))

    # Breakdown table
    story.append(Paragraph("Incident Type Breakdown", h2_s))
    tbl_data = [["Incident Type", "Count", "% of Total"]]
    for nature, count in nature_counts.most_common():
        pct = f"{100 * count / total:.1f}%" if total > 0 else "—"
        tbl_data.append([_type_label(nature.strip().lower()), str(count), pct])

    breakdown = Table(tbl_data, colWidths=[3.6*inch, 1.4*inch, 1.7*inch])
    breakdown.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, _LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.5, _RULE),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(breakdown)

    # Analysis maps: the KDE / Gi* / DBSCAN runs the user made on the map
    for title, png, legend, caption, spots in _analysis_maps(bounds, analyses, incidents):
        if png:
            parts = [Paragraph(title, h2_s), Image(png, width=6.5*inch, height=3.9*inch)]
            if legend:
                parts += [Spacer(1, 4), _chart_image(legend, width=ImageReader(legend).getSize()[0] / 150 * inch)]
            parts.append(Paragraph(caption, note_s))
            parts += [Paragraph(line, body_s) for line in spots]
            story.append(KeepTogether(parts))
        else:
            story.append(Paragraph(title, h2_s))
            story.append(Paragraph("Unavailable: the map could not be drawn.", note_s))

    # Report details: everything needed to reproduce this report
    parameters = _run_parameters(analyses)
    details = [
        ("Bounding coordinates",
         f"N {bounds['north']:.5f}°, S {bounds['south']:.5f}°, E {bounds['east']:.5f}°, W {bounds['west']:.5f}°"),
        ("Date range", days_label),
        ("Filters applied", filters or "None (all incident types and sources)"),
        ("Incidents included", f"{len(incidents):,}"),
        ("Analysis parameters", "<br/>".join(parameters) or "None (no hotspot or cluster overlay was created on the map)"),
        ("Generated", now.strftime("%B %d, %Y at %H:%M UTC")),
    ]
    story.extend(_metadata_flowables(h2_s, TableStyle([
        ("GRID",          (0, 0), (-1, -1), 0.5, _RULE),
        ("BACKGROUND",    (0, 0), (0, -1), _LIGHT),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]), detail_label_s, body_s, details))

    # Footer
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_RULE))
    story.append(Spacer(1, 0.07 * inch))
    story.append(Paragraph(
        "Data sourced from the Lee County Sheriff's Office public incident log. "
        "Incidents are published with a 48-hour delay. "
        "Only geocoded incidents (~55–60% of total) are included in viewport-filtered reports.",
        footer_s,
    ))

    doc.build(story)
    buf.seek(0)
    return buf

if __name__ == "__main__":
    # Build a report from map responses saved off the live site, to test without running the API.
    # The folder holds any of clusters.json, kde.json and gi_star.json, copied from devtools;
    # the incidents for the dates, and for --bbox if the site sent one, come from the live API.
    import argparse
    import json
    import os
    import urllib.parse
    import urllib.request
    from zoneinfo import ZoneInfo

    parser = argparse.ArgumentParser(description="Build a report from map responses saved off the site.")
    parser.add_argument("folder")
    parser.add_argument("--from", dest="start", required=True, type=datetime.date.fromisoformat)
    parser.add_argument("--to", dest="end", required=True, type=datetime.date.fromisoformat)
    parser.add_argument("--bbox", help="the bbox from the site's requests: west,south,east,north")
    parser.add_argument("--api", default="https://leecountyincidentmap.com/api/v1")
    args = parser.parse_args()

    rows, cursor = [], None
    while True:
        query = {"from": args.start, "to": args.end, "mapped": "true", "limit": 5000}
        if args.bbox:
            query["bbox"] = args.bbox
        if cursor:
            query["cursor"] = cursor
        with urllib.request.urlopen(f"{args.api}/incidents?{urllib.parse.urlencode(query)}") as response:
            page = json.load(response)
        rows += page["incidents"]
        cursor = page["next_cursor"]
        if not cursor:
            break

    # the same incidents, map area and analyses the /reports route passes
    eastern = ZoneInfo("America/New_York")
    incidents = [{
        "nature": r["category"],
        "city": r["city"],
        "lat": r["lat"],
        "lng": r["lon"],
        "occuredDate": datetime.datetime.fromisoformat(r["occurred_at"]).astimezone(eastern).isoformat(),
    } for r in rows]
    pad = 0.01
    bounds = {
        "north": max(i["lat"] for i in incidents) + pad,
        "south": min(i["lat"] for i in incidents) - pad,
        "east": max(i["lng"] for i in incidents) + pad,
        "west": min(i["lng"] for i in incidents) - pad,
    }
    analyses = {}
    for name, file in (("dbscan", "clusters.json"), ("kde", "kde.json"), ("gi_star", "gi_star.json")):
        path = os.path.join(args.folder, file)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                analyses[name] = json.load(f)

    out = os.path.join(args.folder, "report.pdf")
    with open(out, "wb") as f:
        f.write(generate_pdf(incidents, bounds, args.start, args.end, analyses=analyses).read())
    print(f"{len(incidents):,} incidents, maps: {', '.join(analyses) or 'none'} -> {out}")
