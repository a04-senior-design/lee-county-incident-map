import io
import os
import re
import base64
import json
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
from matplotlib.colors import BoundaryNorm, ListedColormap, Normalize
from matplotlib.patches import Patch

import report_analytics
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
_BLUE  = "#2563eb"
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


# ---- analysis maps: the user's own KDE / Gi* / DBSCAN runs, read from their run folders ----
#
# A run folder holds the JSON response the map route sent, so the report shows exactly what the user saw:
#   KDE, Gi*  response.json  "image" is the PNG as a data URL, "bounds" places it
#   DBSCAN    response.json  the /clusters response; frames[0]["levels"] is {level: GeoJSON}
_RUN_RESPONSE = "response.json"

_MAP_SIZE = (750, 450)
_OVERLAY_OPACITY = 0.8  # L.imageOverlay(..., {opacity: 0.8}) in Analysis.jsx
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
    match = re.search(r"x\s*1e([+-]?\d+)", caption or "")
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


def _analysis_maps(bounds, runs):
    """[(title, map PNG or None, legend PNG or None)] for each run folder the user sent, in DBSCAN, KDE, Gi* order."""
    maps = []
    for kind, title in (("dbscan", "DBSCAN Clusters"), ("kde", "KDE Heatmap"), ("gi_star", "Gi* Heatmap")):
        run_dir = (runs or {}).get(kind)
        if not run_dir:
            continue
        legend = None
        try:
            with open(os.path.join(run_dir, _RUN_RESPONSE), encoding="utf-8") as f:
                response = json.load(f)
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
            png = None  # expired run, missing file, or no map tiles
        maps.append((title, png, legend if png else None))
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


def _line_chart(incidents, start_date, end_date, top):
    """Stacked area over time, split into the top incident types; weekly once the range passes ~3 months."""
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
    avg = totals.mean() if len(totals) else 0
    ax.axhline(avg, color="#333", linestyle="--", linewidth=0.8)
    ax.text(periods[-1], avg, f" avg {avg:.0f}", va="bottom", ha="right", fontsize=7, color="#333")

    unit = "week" if weekly else "day"
    ax.set_title(f"Incidents per {unit}, split by type", fontsize=10.5, fontweight="bold", pad=10, loc="left")
    ax.set_ylabel(f"Incidents per {unit}", fontsize=8.5)
    ax.set_xlim(periods[0], periods[-1])
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

    _legend_below(fig, keys)
    plt.tight_layout(rect=(0, 0.1, 1, 1))
    return _save_chart(fig), unit, totals, periods


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


# Gi* bands, coldest to hottest: z-score cut-offs for 99/95/90% confidence either side of zero
_GI_BOUNDS = [-4, -2.58, -1.96, -1.65, 1.65, 1.96, 2.58, 4]
_GI_COLORS = ["#2166ac", "#67a9cf", "#d1e5f0", "#d9d9d9", "#fddbc7", "#ef8a62", "#b2182b"]
_GI_LABELS = ["Cold 99%", "Cold 95%", "Cold 90%", "Not significant", "Hot 90%", "Hot 95%", "Hot 99%"]


def _hotspot_chart(kde, gi_star):
    """KDE density surface and Gi* z-score grid side by side, with the listed areas numbered."""
    panels = [p for p in (kde, gi_star) if p and "error" not in p]
    fig, axes = plt.subplots(1, len(panels), figsize=(7, 3.3), squeeze=False)
    fig.patch.set_facecolor("#f8f9fa")

    for ax, panel in zip(axes[0], panels):
        ax.set_facecolor("#e9edf1")
        x0, x1, y0, y1 = panel["extent"]
        if panel is kde:
            surface = panel["surface"]
            shown = np.ma.masked_less(surface, 0.05 * surface.max())  # leave the quiet areas blank
            image = ax.imshow(shown.T, origin="lower", extent=(x0, x1, y0, y1), cmap="YlOrRd")
            cbar_label, title = "Relative density", "Incident density (KDE)"
            marks = panel["hotspots"]
        else:
            # confidence bands, not a smooth scale: a busier-than-average cell that isn't
            # significant stays grey, so the picture agrees with the text
            z = np.ma.masked_invalid(np.clip(panel["z"], -_GI_BOUNDS[-1] + 0.01, _GI_BOUNDS[-1] - 0.01))
            ax.set_facecolor(_BG)  # water / outside the county, distinct from grey "not significant"
            image = ax.imshow(z.T, origin="lower", extent=(x0, x1, y0, y1),
                              cmap=ListedColormap(_GI_COLORS), norm=BoundaryNorm(_GI_BOUNDS, len(_GI_COLORS)))
            cbar_label, title = "Confidence", "Statistically significant hot spots (Gi*)"
            marks = panel["areas"]

        for m in marks:
            ax.annotate(str(m["rank"]), (m["x"], m["y"]), ha="center", va="center", fontsize=8,
                        fontweight="bold", color="white",
                        bbox=dict(boxstyle="circle,pad=0.25", fc="#1e3a5f", ec="white", lw=1))
        ax.set_title(title, fontsize=9, fontweight="bold", pad=6)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.03)
        cbar.set_label(cbar_label, fontsize=7)
        cbar.ax.tick_params(labelsize=6)
        if panel is kde:
            cbar.set_ticks([])
        else:
            cbar.set_ticks([(a + b) / 2 for a, b in zip(_GI_BOUNDS, _GI_BOUNDS[1:])])
            cbar.set_ticklabels(_GI_LABELS)
            cbar.ax.tick_params(length=0)

    plt.tight_layout()
    return _save_chart(fig)


def _dbscan_chart(dbscan):
    """Every incident, coloured by the tightest DBSCAN level it clusters at; noise in grey."""
    xy = dbscan["xy"]
    density = dbscan["density_levels"]

    fig, ax = plt.subplots(figsize=(7, 3.6))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#e9edf1")

    noise = density == -1
    ax.scatter(xy[noise, 0], xy[noise, 1], s=3, color="#aaaaaa", linewidths=0,
               label=f"Not clustered ({noise.sum():,})")
    # levels run loosest to tightest, so the tightest is drawn last, on top
    for k, level in enumerate(dbscan["levels"]):
        keep = density == k
        if keep.any():
            ax.scatter(xy[keep, 0], xy[keep, 1], s=4, color=level["color"], linewidths=0,
                       label=f"{level['name']} ({keep.sum():,})")

    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("DBSCAN clusters by density level", fontsize=10, fontweight="bold", pad=8)
    ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False, markerscale=3)

    plt.tight_layout()
    return _save_chart(fig)


def _kde_bandwidth_text(kde):
    """'a 1,500 ft smoothing bandwidth', or one bandwidth per density level in by-level mode."""
    if not kde["level_names"]:
        return f"a {kde['bandwidths_ft'][0]:,.0f} ft smoothing bandwidth"
    per_level = ", ".join(f"{name} {bw:,.0f} ft" for name, bw in zip(kde["level_names"], kde["bandwidths_ft"]))
    return f"a separate smoothing bandwidth for each DBSCAN density level ({per_level})"


def _sentence(text):
    return text[0].upper() + text[1:]


def _place(item):
    """'near Fort Myers (26.5434, -81.9148)' for a hotspot or cluster."""
    coords = f"{item['lat']:.4f}, {item['lng']:.4f}"
    return f"near {item['city']} ({coords})" if item.get("city") else coords


def _analysis_flowables(analysis, h2_s, h3_s, body_s, note_s, params_tbl_style):
    """Hotspot (KDE, Gi*) and cluster (DBSCAN) sections; each degrades to a one-line note."""
    story = []
    kde, gi_star, dbscan = analysis.get("kde"), analysis.get("gi_star"), analysis.get("dbscan")

    # --- hotspots: KDE + Gi* ---
    if kde or gi_star:
        working = [p for p in (kde, gi_star) if p and "error" not in p]
        heading = Paragraph("Hotspot Analysis", h2_s)
        story.append(KeepTogether([heading, _chart_image(_hotspot_chart(kde, gi_star))]) if working else heading)
        for name, panel in (("Kernel density (KDE)", kde), ("Getis-Ord Gi*", gi_star)):
            if not panel:
                continue
            story.append(Paragraph(name, h3_s))
            if "error" in panel:
                story.append(Paragraph(_sentence(panel["error"]), note_s))
                continue
            if panel is kde:
                story.append(Paragraph(
                    f"Densest areas, using {_kde_bandwidth_text(panel)}. "
                    f"Counts are incidents within {panel['radius_ft'] / 5280:.1f} mi of each peak.", note_s))
                for h in panel["hotspots"]:
                    story.append(Paragraph(
                        f"<b>{h['rank']}.</b> {_sentence(_place(h))}: <b>{h['count']:,}</b> incidents "
                        f"({h['share']:.0%} of the total)"
                        + (f", most often {h['top_type']}" if h["top_type"] else "") + ".",
                        body_s))
            else:
                story.append(Paragraph(
                    f"<b>{panel['hot_cells_95']:,}</b> of {panel['cells_analyzed']:,} grid cells "
                    f"({panel['cell_size_ft']:,} ft squares, {panel['distance_band_ft']:,.0f} ft neighbourhood) "
                    f"are statistically significant hot spots at 95% confidence "
                    f"({panel['hot_cells_99']:,} at 99%). Z-scores compare each cell with the rest of "
                    f"this report's area, so the same place can score differently in a larger report.", note_s))
                strongest = panel.get("strongest")
                if not panel["areas"]:
                    text = "No area is significantly hotter than the rest of the region."
                    if strongest and strongest["z"] > 0:
                        level = (f"significant only at 90% confidence, short of the {report_analytics.GI_Z_95} "
                                 f"needed for 95%" if strongest["z"] >= report_analytics.GI_Z_90
                                 else f"short of the {report_analytics.GI_Z_95} needed for 95% confidence")
                        text += (f" The highest-scoring cell, {_place(strongest)}, reached a z-score of "
                                 f"<b>{strongest['z']:.2f}</b> ({strongest['count']:,} incidents): {level}.")
                    story.append(Paragraph(text, body_s))
                for a in panel["areas"]:
                    story.append(Paragraph(
                        f"<b>{a['rank']}.</b> {_sentence(_place(a))}: peak z-score <b>{a['max_z']:.1f}</b> over "
                        f"{a['cells']} cell{'s' if a['cells'] != 1 else ''}, <b>{a['count']:,}</b> incidents "
                        f"({a['share']:.0%})"
                        + (f", most often {a['top_type']}" if a["top_type"] else "") + ".",
                        body_s))

    # --- clusters: DBSCAN ---
    if dbscan:
        heading = Paragraph("DBSCAN Cluster Analysis", h2_s)
        if "error" in dbscan:
            story.append(heading)
            story.append(Paragraph(_sentence(dbscan["error"]), note_s))
        else:
            story.append(KeepTogether([heading, _chart_image(_dbscan_chart(dbscan))]))
            rows = [["Level", "Radius (ε)", "Min points", "Clusters", "Clustered", "Largest cluster"]]
            for lvl in dbscan["levels"]:
                top = lvl["top_clusters"][0] if lvl["top_clusters"] else None
                largest = "—"
                if top:
                    largest = f"{top['size']:,} incidents"
                    if top["city"]:
                        largest += f", near {top['city']}"
                rows.append([
                    lvl["name"], f"{lvl['epsilon_ft']:,.0f} ft", str(lvl["min_pts"]), str(lvl["n_clusters"]),
                    f"{lvl['clustered_share']:.0%}", Paragraph(largest, body_s),
                ])
            tbl = Table(rows, colWidths=[0.95*inch, 0.9*inch, 0.85*inch, 0.75*inch, 0.8*inch, 2.25*inch])
            tbl.setStyle(params_tbl_style)
            story.append(tbl)
            story.append(Paragraph(
                "Each level groups incidents that lie within the radius of at least the minimum number of others. "
                "Wider levels find broad districts; tighter levels find street-scale concentrations.", note_s))
    return story


def _metadata_flowables(h2_s, tbl_style, label_s, value_s, rows):
    return [
        Paragraph("Report Details", h2_s),
        Table([[Paragraph(k, label_s), Paragraph(v, value_s)] for k, v in rows],
              colWidths=[1.7*inch, 4.8*inch], style=tbl_style),
    ]


def generate_pdf(incidents, bounds, start_date, end_date, filters=None, analyses=None, settings=None, runs=None):
    """Assemble and return a BytesIO PDF for the given filtered incidents.

    runs     -- {"kde" | "gi_star" | "dbscan": run folder} for the overlays the user made on the map;
                each is drawn on its own map of the report's area. Leave a kind out to skip it.

    settings -- the overlays the user created on the map and their slider values, from
                report_analytics.settings_from_args(request.args). Only those overlays are summarised;
                None means the user created none, so the report has no analysis sections.
    analyses -- overrides which of the overlays in `settings` to include.
    filters  -- text describing the filters applied (e.g. "category: BURGLARY; city: FORT MYERS"),
                recorded in the report details; None means no filters.
    analyses -- which map overlays to summarise: any of "kde", "gi_star", "dbscan".
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
    h3_s = ParagraphStyle(
        "RH3", parent=styles["Heading3"],
        fontSize=10, textColor=_NAVY, spaceBefore=8, spaceAfter=3,
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
    trend_png, unit, per_period, periods = _line_chart(incidents, start_date, end_date, top_types)
    if per_period.any():
        peak = int(per_period.argmax())
        when = f"the week of {periods[peak]:%b %d}" if unit == "week" else f"{periods[peak]:%A, %b %d}"
        caption = (f"An average of <b>{per_period.mean():.1f}</b> incidents per {unit} (dashed line). "
                   f"The busiest {unit} was <b>{when}</b>, with {int(per_period[peak]):,}.")
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
    for title, png, legend in _analysis_maps(bounds, runs):
        if png:
            parts = [Paragraph(title, h2_s), Image(png, width=6.5*inch, height=3.9*inch)]
            if legend:
                parts += [Spacer(1, 4), _chart_image(legend, width=ImageReader(legend).getSize()[0] / 150 * inch)]
            story.append(KeepTogether(parts))
        else:
            story.append(Paragraph(title, h2_s))
            story.append(Paragraph("Unavailable: the run has expired or could not be read.", note_s))

    # Hotspot (KDE, Gi*) and cluster (DBSCAN) summaries
    settings = settings or report_analytics.default_settings()
    if analyses is None:
        analyses = settings["analyses"]
    analysis = report_analytics.analyze(incidents, run=analyses, settings=settings) if analyses else {}
    header_tbl_style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, _LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.5, _RULE),
        ("ALIGN",         (1, 0), (4, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    story.extend(_analysis_flowables(analysis, h2_s, h3_s, body_s, note_s, header_tbl_style))

    # Report details: everything needed to reproduce this report
    parameters = []
    if "kde" in analysis and "error" not in analysis["kde"]:
        parameters.append(f"KDE: {_kde_bandwidth_text(analysis['kde'])}")
    if "gi_star" in analysis and "error" not in analysis["gi_star"]:
        parameters.append(f"Gi* distance band {analysis['gi_star']['distance_band_ft']:,.0f} ft, "
                          f"{analysis['gi_star']['cell_size_ft']:,} ft cells")
    if "dbscan" in analysis and "error" not in analysis["dbscan"]:
        parameters.append("DBSCAN " + "; ".join(
            f"{l['name']} ε {l['epsilon_ft']:,.0f} ft, min {l['min_pts']}" for l in analysis["dbscan"]["levels"]))
    details = [
        ("Bounding coordinates",
         f"N {bounds['north']:.5f}°, S {bounds['south']:.5f}°, E {bounds['east']:.5f}°, W {bounds['west']:.5f}°"),
        ("Date range", days_label),
        ("Filters applied", filters or "None (all incident types and sources)"),
        ("Incidents included", f"{len(incidents):,}"
         + (f" ({analysis['left_out']:,} geocoded far outside the county are left out of the hotspot "
            f"and cluster analyses)" if analysis.get("left_out") else "")),
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