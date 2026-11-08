"""
Unit tests for the GiStarHeatMap class (GiStarHeatMap.py).

Test IDs (GI-01 to GI-30) match the GiStarHeatMap Unit Test Plan, which gives
the purpose, setup and expected result of each case.

Folder layout:

    gi_star_unit_test/
    ├── README.md
    ├── requirements.txt
    ├── GiStarHeatMap.py
    ├── test_GiStarHeatMap.py
    └── test_data/
        ├── gi_star_example_data.csv
        └── late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv

Run from the gi_star_unit_test folder:

    python3 -m pytest test_GiStarHeatMap.py -v
    python3 -m pytest test_GiStarHeatMap.py --cov=GiStarHeatMap --cov-branch --cov-report=term-missing

GI-19 appends its timings to gi_star_timing_log.csv in this folder on every run.
"""

import csv
import json
import os
import re
import time
from datetime import datetime

import matplotlib
matplotlib.use("Agg")    # draw images without opening windows

import matplotlib.image as mpimg
import numpy as np
import pandas as pd
import pytest
import shapely
from pyproj import Transformer
from rasterio.coords import BoundingBox
from scipy.stats import norm

import GiStarHeatMap as gi_module
from GiStarHeatMap import GiStarHeatMap


# ---------------------------------------------------------------------------
# Paths and shared settings
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_DATA = os.path.join(HERE, "test_data")
EXAMPLE_CSV = os.path.join(TEST_DATA, "gi_star_example_data.csv")
INCIDENT_CSV = os.path.join(TEST_DATA, "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv")
TIMING_LOG = os.path.join(HERE, "gi_star_timing_log.csv")

CELL_SIZE = 10           # baseline grid: 0 to 100 in x and y, 10 x 10 cells
BAND = 10                # baseline distance band (one cell width)
N_CELLS = 100
Z_TOLERANCE = 1e-9       # absolute tolerance for z-scores against the reference

# index of the cell centred at (25, 35); centres are ordered by x, then y
CELL_25_35 = 2 * 10 + 3

# app settings used with the real incident data
APP_CELL_SIZE = 5000
APP_BAND = 7500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_example():
    """Read test_data/gi_star_example_data.csv as an (N, 2) array."""
    return np.loadtxt(EXAMPLE_CSV, delimiter=",", skiprows=1)


def build(points, band=BAND, land_polygon=None, output_dir=None, **grid):
    """Build a GiStarHeatMap on the baseline grid unless grid values are given."""
    args = dict(x_min=0, y_min=0, x_max=100, y_max=100, cell_size=CELL_SIZE)
    args.update(grid)
    return GiStarHeatMap(points=points, distance_band=band, land_polygon=land_polygon,
                         output_dir=str(output_dir) if output_dir else ".", **args)


def reference_gi_star(counts, centroids, band):
    """Brute-force Gi* z-scores with the standard Getis-Ord equation from the
    design report.  Doesn't use esda or libpysal.

    counts:    number of points in each cell (x_j), one per cell in the analysis
    centroids: (n, 2) array of cell centres
    band:      distance band; w_ij = 1 if the centres are at most band apart
    """
    x = np.asarray(counts, dtype=float)
    n = len(x)
    x_bar = x.sum() / n
    s = np.sqrt(((x - x_bar) ** 2).sum() / n)

    distances = np.sqrt(((centroids[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=-1))
    w = (distances <= band).astype(float)        # each cell is its own neighbor (distance 0)

    sum_w = w.sum(axis=1)
    sum_w2 = (w ** 2).sum(axis=1)
    numerator = w @ x - x_bar * sum_w
    denominator = s * np.sqrt((n * sum_w2 - sum_w ** 2) / (n - 1))
    return numerator / denominator


def expected_counts(points, cell_size=CELL_SIZE, n_per_side=10):
    """Count points per cell with the boundary rule: each cell includes its
    lower edge but not its upper edge, except the grid's outer edge."""
    counts = np.zeros((n_per_side, n_per_side))
    for x, y in points:
        i = min(int(x // cell_size), n_per_side - 1)
        j = min(int(y // cell_size), n_per_side - 1)
        counts[i, j] += 1
    return counts.ravel()


def load_incident_points():
    """The 250 real incidents in EPSG:2882 feet, plus their lat/lon."""
    incidents = pd.read_csv(INCIDENT_CSV).dropna(subset=["lat", "lon"])
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)
    easting, northing = transformer.transform(incidents["lon"].to_numpy(), incidents["lat"].to_numpy())
    return np.column_stack([easting, northing]), incidents


def padded_grid(points, cell_size):
    """Grid bounds covering the points plus one cell on each side."""
    return dict(x_min=points[:, 0].min() - cell_size, y_min=points[:, 1].min() - cell_size,
                x_max=points[:, 0].max() + cell_size, y_max=points[:, 1].max() + cell_size,
                cell_size=cell_size)


# ---------------------------------------------------------------------------
# Fixtures (pytest setup functions)
# ---------------------------------------------------------------------------

@pytest.fixture
def baseline(tmp_path):
    """The baseline setup: example data, 0-100 grid, cell size 10, band 10,
    no land polygon.  tmp_path is a fresh temporary folder per test."""
    return build(load_example(), output_dir=tmp_path)


@pytest.fixture
def legend(baseline):
    """Legend data from the baseline setup, after generating the image."""
    baseline.generate_zscore_heatmap_image()
    return baseline.get_legend_data()


# ---------------------------------------------------------------------------
# Constructor input checks (GI-01 to GI-07)
# ---------------------------------------------------------------------------

def test_gi01_no_points(tmp_path):
    """GI-01 (Sample F): an empty dataset is rejected."""
    with pytest.raises(ValueError, match="No points"):
        build(np.empty((0, 2)), output_dir=tmp_path)


@pytest.mark.parametrize("shape", [(10, 3), (10, 1), (10,)], ids=["10x3", "10x1", "flat"])
def test_gi02_wrong_point_shape(tmp_path, shape):
    """GI-02: points must have shape (N, 2)."""
    with pytest.raises(ValueError, match=r"shape \(N, 2\)"):
        build(np.zeros(shape), output_dir=tmp_path)


@pytest.mark.parametrize("band", [0, -10])
def test_gi03_distance_band_not_positive(tmp_path, band):
    """GI-03: the distance band must be > 0 (covers the requested band-0 run)."""
    with pytest.raises(ValueError, match="Distance Band must be > 0"):
        build(load_example(), band=band, output_dir=tmp_path)


@pytest.mark.parametrize("axis", ["x", "y"])
@pytest.mark.parametrize("offset", [0, -1], ids=["equal", "below"])
def test_gi04_bad_grid_bounds(tmp_path, axis, offset):
    """GI-04: x_max must exceed x_min, and y_max must exceed y_min."""
    grid = {f"{axis}_max": 0 + offset}           # x_min and y_min are 0
    with pytest.raises(ValueError, match=f"{axis}_max must be greater than {axis}_min"):
        build(load_example(), output_dir=tmp_path, **grid)


@pytest.mark.parametrize("cell_size", [0, -10])
def test_gi05_cell_size_not_positive(tmp_path, cell_size):
    """GI-05: the cell size must be > 0."""
    with pytest.raises(ValueError, match="Cell size must be > 0"):
        build(load_example(), output_dir=tmp_path, cell_size=cell_size)


def test_gi06_fewer_than_two_analysis_cells(tmp_path):
    """GI-06: with a land polygon away from the grid, only the point's own cell
    is kept (cells containing points are always kept), which is too few."""
    far_away = shapely.box(500, 500, 600, 600)
    with pytest.raises(ValueError, match=r"Only 1 land cell\(s\)"):
        build([[5, 5]], land_polygon=far_away, output_dir=tmp_path)


@pytest.mark.parametrize("case, points, count", [
    ("one per cell", [[x, y] for x in range(5, 100, 10) for y in range(5, 100, 10)], 1),
    ("all outside", [[150, 150], [200, 200]], 0),
], ids=["one-per-cell", "all-outside"])
def test_gi07_no_variation_in_counts(tmp_path, case, points, count):
    """GI-07: every cell with the same count gives Gi* nothing to compare."""
    with pytest.raises(ValueError, match=rf"All 100 land cells have the same count \({count}\)"):
        build(points, output_dir=tmp_path)


# ---------------------------------------------------------------------------
# Grid, counts and land mask (GI-08 to GI-12)
# ---------------------------------------------------------------------------

def test_gi08_grid_and_cell_centres(baseline):
    """GI-08: a 10 x 10 grid with centres ordered by x, then y."""
    np.testing.assert_array_equal(baseline.x_edges, np.arange(0, 110, 10))
    np.testing.assert_array_equal(baseline.y_edges, np.arange(0, 110, 10))
    assert baseline.counts.shape == (10, 10)

    expected = np.array([[x, y] for x in range(5, 100, 10) for y in range(5, 100, 10)], dtype=float)
    np.testing.assert_array_equal(baseline.cell_centroids, expected)
    assert tuple(baseline.cell_centroids[0]) == (5, 5)
    assert tuple(baseline.cell_centroids[1]) == (5, 15)


def test_gi09_points_counted_per_cell(baseline):
    """GI-09: every cell's count matches the boundary rule; 20 points in 16 cells."""
    np.testing.assert_array_equal(baseline.y, expected_counts(load_example()))
    assert baseline.y.sum() == 20
    assert np.count_nonzero(baseline.y) == 16

    two_point_cells = {tuple(c) for c, n in zip(baseline.cell_centroids, baseline.y) if n == 2}
    assert two_point_cells == {(5, 5), (25, 35), (95, 25), (95, 65)}


def test_gi10_missing_or_out_of_grid_coordinates(baseline, tmp_path):
    """GI-10 (Sample B): a missing coordinate and points outside the grid are
    dropped without an error (current behavior; see Findings)."""
    extra = np.array([[np.nan, 50], [150, 50], [-5, 5]])
    gi = build(np.vstack([load_example(), extra]), output_dir=tmp_path)
    assert gi.y.sum() == 20
    np.testing.assert_array_equal(gi.z_scores, baseline.z_scores)


@pytest.mark.parametrize("band, has_neighbors", [(5, False), (10, True), (20, True)])
def test_gi11_neighbor_flag(tmp_path, band, has_neighbors):
    """GI-11: cells_have_neighbors is False only when the band is below a cell width."""
    assert build(load_example(), band=band, output_dir=tmp_path).cells_have_neighbors is has_neighbors


def test_gi12_land_mask(baseline, tmp_path):
    """GI-12: no polygon keeps every cell; a square over x = 0 to 50 keeps the
    50 cells inside it plus the 5 cells outside it that contain points."""
    assert baseline.land_cells.all()
    assert baseline.land_cells.sum() == N_CELLS

    gi = build(load_example(), land_polygon=shapely.box(0, 0, 50, 100), output_dir=tmp_path)
    assert gi.land_cells.sum() == 55

    inside = {(x, y) for x in range(5, 50, 10) for y in range(5, 100, 10)}
    kept_with_points = {(85, 35), (85, 65), (95, 5), (95, 25), (95, 65)}
    included = {tuple(c) for c in gi.cell_centroids[gi.land_cells]}
    assert included == inside | kept_with_points

    assert np.isnan(gi.z_scores[~gi.land_cells]).all()
    assert np.isnan(gi.p_norm_val[~gi.land_cells]).all()


# ---------------------------------------------------------------------------
# Gi* z-scores and p-values (GI-13 to GI-19)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("band, highest_z", [(5, 3.674), (10, 2.796), (20, 2.271)])
def test_gi13_matches_brute_force_gi_star(tmp_path, band, highest_z):
    """GI-13: every cell's z-score equals the brute-force reference."""
    gi = build(load_example(), band=band, output_dir=tmp_path)
    expected = reference_gi_star(gi.y, gi.cell_centroids, band)
    np.testing.assert_allclose(gi.z_scores, expected, rtol=0, atol=Z_TOLERANCE)
    assert gi.z_scores.max() == pytest.approx(highest_z, abs=0.0005)


def test_gi14_matches_brute_force_with_land_mask(tmp_path):
    """GI-14: with a land mask, the reference uses the 55 included cells only."""
    gi = build(load_example(), land_polygon=shapely.box(0, 0, 50, 100), output_dir=tmp_path)
    included = gi.land_cells
    expected = reference_gi_star(gi.y[included], gi.cell_centroids[included], BAND)
    assert len(expected) == 55
    np.testing.assert_allclose(gi.z_scores[included], expected, rtol=0, atol=Z_TOLERANCE)


def test_gi15_hand_worked_cell(baseline):
    """GI-15: cell (25, 35) matches the hand calculation in the plan, 2.796."""
    assert tuple(baseline.cell_centroids[CELL_25_35]) == (25, 35)
    assert baseline.z_scores[CELL_25_35] == pytest.approx(2.796, abs=0.0005)


def test_gi16_one_point(tmp_path):
    """GI-16 (Sample D): with band 5 the point's cell is sqrt(99) and every
    other cell is -1/sqrt(99)."""
    gi = build([[25, 35]], band=5, output_dir=tmp_path)
    assert gi.z_scores[CELL_25_35] == pytest.approx(np.sqrt(99), rel=1e-6)
    others = np.delete(gi.z_scores, CELL_25_35)
    np.testing.assert_allclose(others, -1 / np.sqrt(99), rtol=1e-6)


def test_gi17_two_points_in_one_cell(tmp_path):
    """GI-17 (Sample E): two points in one cell give a count of 2 and the same
    z-score as one point; the z-score depends on the pattern, not the size."""
    gi = build([[22, 33], [27, 38]], band=5, output_dir=tmp_path)
    assert gi.y[CELL_25_35] == 2
    assert gi.z_scores[CELL_25_35] == pytest.approx(np.sqrt(99), rel=1e-6)


def test_gi18_p_values(baseline):
    """GI-18: p-values are one-sided, 1 - Phi(|z|) (see Findings)."""
    np.testing.assert_allclose(baseline.p_norm_val, 1 - norm.cdf(np.abs(baseline.z_scores)),
                               rtol=0, atol=1e-12)


def test_gi19_large_dataset_and_timing(tmp_path):
    """GI-19 (Sample C): 10,000 points over Lee County at the app's settings.
    Build and render times are logged to gi_star_timing_log.csv, not tested."""
    incident_points, _ = load_incident_points()
    rng = np.random.default_rng(1)
    points = rng.normal(incident_points.mean(axis=0), incident_points.std(axis=0), size=(10_000, 2))

    start = time.perf_counter()
    gi = GiStarHeatMap(points=points, distance_band=APP_BAND, output_dir=str(tmp_path),
                       **padded_grid(points, APP_CELL_SIZE))
    build_seconds = time.perf_counter() - start

    start = time.perf_counter()
    gi.generate_zscore_heatmap_image()
    render_seconds = time.perf_counter() - start

    assert np.isfinite(gi.z_scores).all()

    new_log = not os.path.exists(TIMING_LOG)
    with open(TIMING_LOG, "a", newline="") as f:
        writer = csv.writer(f)
        if new_log:
            writer.writerow(["timestamp", "points", "cells", "build_s", "render_s"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), len(points),
                         gi.y.size, f"{build_seconds:.3f}", f"{render_seconds:.3f}"])


# ---------------------------------------------------------------------------
# generate_zscore_heatmap_image() (GI-20 to GI-23)
# ---------------------------------------------------------------------------

def test_gi20_png_written(baseline, tmp_path):
    """GI-20: the default call writes an RGBA z_score_overlay.png."""
    baseline.generate_zscore_heatmap_image()
    image = mpimg.imread(tmp_path / "z_score_overlay.png")
    assert image.ndim == 3 and image.shape[2] == 4
    assert image[..., 3].max() > 0      # some pixels visible
    assert image[..., 3].min() == 0     # some pixels fully transparent


def test_gi21_bounds(baseline):
    """GI-21: the bounds contain the grid's four corners in lat/lon."""
    bounds = baseline.generate_zscore_heatmap_image()
    assert isinstance(bounds, BoundingBox)
    assert bounds.left < bounds.right and bounds.bottom < bounds.top

    transformer = Transformer.from_crs("EPSG:2882", "EPSG:4326", always_xy=True)
    for corner in [(0, 0), (100, 0), (0, 100), (100, 100)]:
        lon, lat = transformer.transform(*corner)
        assert bounds.left <= lon <= bounds.right
        assert bounds.bottom <= lat <= bounds.top


@pytest.mark.parametrize("z_abs_max", [0, -1])
def test_gi22_z_abs_max_not_positive(baseline, z_abs_max):
    """GI-22: a shared color scale must be > 0."""
    with pytest.raises(ValueError, match="z_abs_max must be > 0"):
        baseline.generate_zscore_heatmap_image(z_abs_max=z_abs_max)


def test_gi23_shared_color_scale(baseline):
    """GI-23: an explicit z_abs_max sets the legend's range."""
    baseline.generate_zscore_heatmap_image(z_abs_max=4)
    legend = baseline.get_legend_data()
    assert legend["vmin"] == -4
    assert legend["vmax"] == 4


# ---------------------------------------------------------------------------
# get_legend_data() (GI-24 to GI-26)
# ---------------------------------------------------------------------------

def test_gi24_legend_structure_and_caption(baseline, legend):
    """GI-24: five keys, JSON-serializable, default and custom captions."""
    assert set(legend) == {"colors", "vmin", "vmax", "ticks", "caption"}
    json.dumps(legend)
    assert legend["caption"] == "Gi* z-score"
    assert baseline.get_legend_data(caption="Hot spots")["caption"] == "Hot spots"


def test_gi25_legend_colors(legend):
    """GI-25: 256 hex colors, blue to white (z = 0) to red."""
    colors = legend["colors"]
    assert len(colors) == 256
    assert all(re.fullmatch(r"#[0-9a-f]{6}", c) for c in colors)
    assert colors[0] == "#0000ff"
    assert colors[-1] == "#ff0000"
    assert colors[127] == "#ffffff"
    assert colors[128] == "#ffffff"


def test_gi26_legend_ticks(legend):
    """GI-26: sorted, unique, symmetric ticks ending at +/-vmax rounded to 2 decimals."""
    ticks = legend["ticks"]
    assert ticks == sorted(set(ticks))
    assert len(ticks) >= 3
    for t in ticks:
        assert any(abs(t + other) <= 1e-9 for other in ticks)
    assert ticks[0] == round(legend["vmin"], 2)
    assert ticks[-1] == round(legend["vmax"], 2)


# ---------------------------------------------------------------------------
# Other output methods (GI-27 to GI-29)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("min_points, cell_lines", [(0, 100), (1, 16)])
def test_gi27_print_z_scores(baseline, capsys, min_points, cell_lines):
    """GI-27: one line per cell with at least min_points points, plus a header."""
    baseline.print_z_scores(min_points=min_points)
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1 + cell_lines

    cell_line = [line for line in lines if "(25.000, 35.000)" in line]
    assert len(cell_line) == 1
    assert "count = 2" in cell_line[0]
    assert "Z = 2.796" in cell_line[0]


def test_gi28_printable_figure(baseline, tmp_path, monkeypatch):
    """GI-28: the printable figure is written to the current folder, because the
    method ignores output_dir (see Findings)."""
    monkeypatch.chdir(tmp_path)
    baseline.generate_zscore_printable_heatmap_image()
    assert (tmp_path / "z_score_figure.png").is_file()


def test_gi29_module_demo(tmp_path, monkeypatch):
    """GI-29: the module's main() demo runs and writes its image."""
    monkeypatch.chdir(tmp_path)
    gi_module.main()
    assert (tmp_path / "test_gi_star_surface.png").is_file()


# ---------------------------------------------------------------------------
# Real incident data (GI-30)
# ---------------------------------------------------------------------------

def test_gi30_real_incident_data(tmp_path):
    """GI-30 (Sample A): the 250 incidents at the app's settings match the
    brute-force reference, and the image bounds contain every incident."""
    points, incidents = load_incident_points()
    gi = GiStarHeatMap(points=points, distance_band=APP_BAND, output_dir=str(tmp_path),
                       **padded_grid(points, APP_CELL_SIZE))

    assert gi.counts.shape == (45, 34)
    assert gi.y.sum() == 250

    expected = reference_gi_star(gi.y, gi.cell_centroids, APP_BAND)
    np.testing.assert_allclose(gi.z_scores, expected, rtol=0, atol=Z_TOLERANCE)

    bounds = gi.generate_zscore_heatmap_image()
    assert (tmp_path / "z_score_overlay.png").is_file()
    assert bounds.bottom < incidents["lat"].min() and bounds.top > incidents["lat"].max()
    assert bounds.left < incidents["lon"].min() and bounds.right > incidents["lon"].max()
