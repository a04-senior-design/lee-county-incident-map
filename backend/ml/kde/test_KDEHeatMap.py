"""
Unit tests for the KDEHeatMap class (KDEHeatMap.py).

Test IDs (TC-01 to TC-29) match the KDEHeatMap Unit Test Plan, which gives
the purpose, setup and expected result of each case.

Folder layout:

    kde_local/
    ├── KDEHeatMap.py
    ├── test_KDEHeatMap.py
    ├── make_fixture.py
    └── test_data/
        ├── two_clusters.csv
        ├── late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv
        ├── density_scenario_1levels.txt
        ├── density_scenario_2levels.txt
        └── density_scenario_3levels.txt

Run from the kde_local folder:

    python3 -m pytest test_KDEHeatMap.py -v
    python3 -m pytest test_KDEHeatMap.py --cov=KDEHeatMap --cov-branch --cov-report=term-missing

Expect 42 passed: seven cases try several inputs and pytest reports each
input on its own line.  TC-18 appends its timings to kde_timing_log.csv in
this folder on every run.
"""

import csv
import io
import json
import os
import re
import time
from datetime import datetime

import matplotlib.image as mpimg
import numpy as np
import pandas as pd
import pytest
from pyproj import Transformer
from rasterio.coords import BoundingBox

from KDEHeatMap import KDEHeatMap


# ---------------------------------------------------------------------------
# Paths and shared settings
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_DATA = os.path.join(HERE, "test_data")
FIXTURE_CSV = os.path.join(TEST_DATA, "two_clusters.csv")
INCIDENT_CSV = os.path.join(TEST_DATA, "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv")
TIMING_LOG = os.path.join(HERE, "kde_timing_log.csv")

INCREMENT = 300      # lattice spacing in feet (same as test_kde.py)
PADDING = 12_000     # lattice padding in feet around the fixture points
BW_0 = 1500          # standard bandwidth for cluster 0 (wide)
BW_1 = 600           # standard bandwidth for cluster 1 (tight)

# bandwidths from test_kde.py for the real-data scenarios, cluster 0 first
SCENARIO_BANDWIDTHS = {1: [600], 2: [1200, 600], 3: [3100, 1200, 600]}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_fixture():
    """Read test_data/two_clusters.csv as (points, cluster_levels)."""
    data = np.loadtxt(FIXTURE_CSV, delimiter=",", skiprows=1)
    return data[:, :2], data[:, 2].astype(int)


def lattice_bounds(points, padding):
    """Lattice bounds covering the points plus padding on every side."""
    x_min, y_min = np.nanmin(points, axis=0) - padding
    x_max, y_max = np.nanmax(points, axis=0) + padding
    return dict(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def build(points, levels, bandwidths, output_dir, padding=6000):
    """Build a KDEHeatMap for a small point set made inside a test."""
    points = np.asarray(points, dtype=float)
    return KDEHeatMap(points=points, cluster_levels=levels, bandwidths=bandwidths,
                      increment=INCREMENT, output_dir=str(output_dir),
                      **lattice_bounds(points, padding))


def exact_gaussian_kde(points, bw, grid):
    """Brute-force 2-D Gaussian KDE: the independent reference answer."""
    d2 = ((grid[:, None, :] - points[None, :, :]) ** 2).sum(axis=-1)
    return np.exp(-d2 / (2 * bw * bw)).sum(axis=1) / (len(points) * 2 * np.pi * bw * bw)


def node_index(coords, value):
    """Index of the lattice coordinate closest to value."""
    return int(np.argmin(np.abs(coords - value)))


def load_scenario(n_levels):
    """Read a density_scenario file, skipping its description above the dashed line."""
    path = os.path.join(TEST_DATA, f"density_scenario_{n_levels}levels.txt")
    with open(path) as f:
        text = f.read()
    table = text.split("-" * 60 + "\n", 1)[1]
    return pd.read_csv(io.StringIO(table))


# ---------------------------------------------------------------------------
# Fixtures (pytest setup functions)
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_args(tmp_path):
    """Constructor arguments for the standard fixture.  tmp_path is a fresh
    temporary folder pytest creates per test, so PNGs never land here."""
    points, levels = load_fixture()
    return dict(points=points, cluster_levels=levels, bandwidths=[BW_0, BW_1],
                increment=INCREMENT, output_dir=str(tmp_path),
                **lattice_bounds(points, PADDING))


@pytest.fixture
def heatmap(valid_args):
    return KDEHeatMap(**valid_args)


@pytest.fixture
def legend(heatmap):
    """Legend data from the standard fixture, after generating the image."""
    heatmap.generate_heatmap_image()
    return heatmap.get_legend_data()


# ---------------------------------------------------------------------------
# Constructor input checks (TC-01 to TC-10)
# ---------------------------------------------------------------------------

def test_tc01_no_points(valid_args):
    """TC-01 (Sample F): an empty dataset is rejected."""
    valid_args.update(points=np.empty((0, 2)), cluster_levels=np.array([], dtype=int))
    with pytest.raises(ValueError, match="No points"):
        KDEHeatMap(**valid_args)


@pytest.mark.parametrize("shape", [(10, 3), (10, 1), (10,)], ids=["10x3", "10x1", "flat"])
def test_tc02_wrong_point_shape(valid_args, shape):
    """TC-02: points must have shape (N, 2)."""
    valid_args.update(points=np.zeros(shape), cluster_levels=np.zeros(10, dtype=int))
    with pytest.raises(ValueError, match=r"shape \(N, 2\)"):
        KDEHeatMap(**valid_args)


def test_tc03_level_count_mismatch(valid_args):
    """TC-03: one cluster level is needed per point."""
    valid_args["cluster_levels"] = valid_args["cluster_levels"][:-1]
    with pytest.raises(ValueError, match="one cluster level per point"):
        KDEHeatMap(**valid_args)


@pytest.mark.parametrize("bandwidths", [[0, 600], [1500, 0], [-100, 600], [1500, -0.001]],
                         ids=["zero-first", "zero-second", "negative-first", "negative-second"])
def test_tc04_bandwidth_not_positive(valid_args, bandwidths):
    """TC-04: every bandwidth must be > 0 (regression test for the zero-bandwidth crash)."""
    valid_args["bandwidths"] = bandwidths
    with pytest.raises(ValueError, match="bandwidths must be > 0"):
        KDEHeatMap(**valid_args)


@pytest.mark.parametrize("bandwidths", [[1500], [1500, 600, 300]], ids=["too-few", "too-many"])
def test_tc05_bandwidth_count_mismatch(valid_args, bandwidths):
    """TC-05: one bandwidth per non-noise cluster (2 clusters here)."""
    valid_args["bandwidths"] = bandwidths
    with pytest.raises(ValueError, match="one bandwidth per cluster"):
        KDEHeatMap(**valid_args)


def test_tc06_nan_bandwidth(valid_args):
    """TC-06: a NaN bandwidth is rejected."""
    valid_args["bandwidths"] = [np.nan, 600]
    with pytest.raises(ValueError):
        KDEHeatMap(**valid_args)


@pytest.mark.parametrize("nan_point_level", [0, -1], ids=["clustered", "noise"])
def test_tc07_missing_coordinate(tmp_path, nan_point_level):
    """TC-07 (Sample B): a NaN coordinate is rejected in a clustered point and
    ignored in a noise point, since noise points are never used."""
    points = [[700_000, 830_000], [np.nan, 830_000], [700_600, 830_000]]
    levels = [0, nan_point_level, 0]
    if nan_point_level == 0:
        with pytest.raises(ValueError):
            build(points, levels, [1000], tmp_path)
    else:
        kde = build(points, levels, [1000], tmp_path)
        assert np.all(np.isfinite(kde.density_surface))


@pytest.mark.parametrize("axis", ["x", "y"])
@pytest.mark.parametrize("offset", [0.0, -1.0], ids=["equal", "below"])
def test_tc08_bad_lattice_bounds(valid_args, axis, offset):
    """TC-08: x_max must exceed x_min, and y_max must exceed y_min."""
    valid_args[f"{axis}_max"] = valid_args[f"{axis}_min"] + offset
    with pytest.raises(ValueError, match=f"{axis}_max must be greater than {axis}_min"):
        KDEHeatMap(**valid_args)


@pytest.mark.parametrize("increment", [0, -300])
def test_tc09_increment_not_positive(valid_args, increment):
    """TC-09: increment must be > 0."""
    valid_args["increment"] = increment
    with pytest.raises(ValueError, match="increment must be > 0"):
        KDEHeatMap(**valid_args)


def test_tc10_all_noise(valid_args):
    """TC-10: if every point is noise there is nothing to build."""
    valid_args["cluster_levels"] = np.full(len(valid_args["points"]), -1)
    valid_args["bandwidths"] = [BW_0]
    with pytest.raises(ValueError, match="All points are noise"):
        KDEHeatMap(**valid_args)


# ---------------------------------------------------------------------------
# Cluster partitioning (TC-11)
# ---------------------------------------------------------------------------

def test_tc11_points_split_by_level(heatmap, valid_args):
    """TC-11: one array per level in ascending order, noise removed."""
    points, levels = valid_args["points"], valid_args["cluster_levels"]
    assert len(heatmap.points_per_cluster) == 2
    np.testing.assert_array_equal(heatmap.points_per_cluster[0], points[levels == 0])
    np.testing.assert_array_equal(heatmap.points_per_cluster[1], points[levels == 1])
    assert heatmap.cluster_sizes == [60, 40]
    assert heatmap.n_points == 100


# ---------------------------------------------------------------------------
# Density surface (TC-12 to TC-18)
# ---------------------------------------------------------------------------

def test_tc12_volume(heatmap):
    """TC-12: the surface integrates to about 1."""
    assert heatmap.density_surface_volume() == pytest.approx(1.0, abs=0.01)


def test_tc13_matches_exact_kde_one_cluster(valid_args):
    """TC-13: with one cluster, the rescaled FFTKDE surface matches a
    brute-force Gaussian KDE (checks the divide-by-bandwidth rescaling)."""
    valid_args["cluster_levels"] = np.where(valid_args["cluster_levels"] == -1, -1, 0)
    valid_args["bandwidths"] = [1000]
    kde = KDEHeatMap(**valid_args)

    expected = exact_gaussian_kde(kde.points_per_cluster[0], 1000, kde.lattice)
    expected = expected.reshape(kde.density_surface.shape)
    assert np.abs(kde.density_surface - expected).max() <= 0.03 * expected.max()


def test_tc14_count_weighting_two_clusters(heatmap):
    """TC-14: the surface is each cluster's KDE weighted by its share of points."""
    cluster_0, cluster_1 = heatmap.points_per_cluster
    expected = (60 * exact_gaussian_kde(cluster_0, BW_0, heatmap.lattice) +
                40 * exact_gaussian_kde(cluster_1, BW_1, heatmap.lattice)) / 100
    expected = expected.reshape(heatmap.density_surface.shape)
    assert np.abs(heatmap.density_surface - expected).max() <= 0.05 * expected.max()


def test_tc15_noise_ignored(valid_args):
    """TC-15: moving the noise points does not change the surface."""
    before = KDEHeatMap(**valid_args).density_surface

    points = valid_args["points"].copy()
    points[valid_args["cluster_levels"] == -1] += 3000
    valid_args["points"] = points
    after = KDEHeatMap(**valid_args).density_surface

    np.testing.assert_allclose(before, after)


def test_tc16_one_point(tmp_path):
    """TC-16 (Sample D): one point on a lattice node peaks at 1 / (2 pi bw^2)."""
    bw = 1000
    kde = build([[700_000, 830_000]], [0], [bw], tmp_path)
    i = node_index(kde.x_coords, 700_000)
    j = node_index(kde.y_coords, 830_000)

    assert np.unravel_index(kde.density_surface.argmax(), kde.density_surface.shape) == (i, j)
    assert kde.density_surface[i, j] == pytest.approx(1 / (2 * np.pi * bw**2), rel=1e-6)
    assert kde.density_surface_volume() == pytest.approx(1.0, abs=0.01)
    kde.generate_heatmap_image()
    assert (tmp_path / "density_overlay.png").is_file()


def test_tc17_two_nearby_points(tmp_path):
    """TC-17 (Sample E): two points 600 ft apart each add to the other's density."""
    bw, gap = 1000, 600
    kde = build([[700_000, 830_000], [700_000 + gap, 830_000]], [0, 0], [bw], tmp_path)
    expected = (1 + np.exp(-gap**2 / (2 * bw**2))) / 2 / (2 * np.pi * bw**2)

    j = node_index(kde.y_coords, 830_000)
    for x in (700_000, 700_000 + gap):
        i = node_index(kde.x_coords, x)
        assert kde.density_surface[i, j] == pytest.approx(expected, rel=1e-6)


def test_tc18_large_dataset_and_timing(tmp_path):
    """TC-18 (Sample C): 10,000 points, the expected maximum.  Build and render
    times are appended to kde_timing_log.csv; they are logged, not tested."""
    n = 10_000
    rng = np.random.default_rng(1)
    points = rng.normal((700_000, 830_000), 15_000, size=(n, 2))
    levels = rng.integers(-1, 3, size=n)    # levels 0 to 2 plus noise

    start = time.perf_counter()
    kde = KDEHeatMap(points=points, cluster_levels=levels, bandwidths=[3100, 1200, 600],
                     increment=INCREMENT, output_dir=str(tmp_path),
                     **lattice_bounds(points, 15_000))
    build_seconds = time.perf_counter() - start

    start = time.perf_counter()
    kde.generate_heatmap_image()
    render_seconds = time.perf_counter() - start

    assert kde.density_surface_volume() == pytest.approx(1.0, abs=0.01)

    new_log = not os.path.exists(TIMING_LOG)
    with open(TIMING_LOG, "a", newline="") as f:
        writer = csv.writer(f)
        if new_log:
            writer.writerow(["timestamp", "points", "lattice_nodes", "build_s", "render_s"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), n,
                         len(kde.lattice), f"{build_seconds:.3f}", f"{render_seconds:.3f}"])


# ---------------------------------------------------------------------------
# generate_heatmap_image() (TC-19 to TC-22)
# ---------------------------------------------------------------------------

def test_tc19_png_written(heatmap):
    """TC-19: the default call writes an RGBA density_overlay.png."""
    heatmap.generate_heatmap_image()
    image = mpimg.imread(os.path.join(heatmap.output_dir, "density_overlay.png"))
    assert image.ndim == 3 and image.shape[2] == 4
    assert image[..., 3].max() > 0      # some pixels visible
    assert image[..., 3].min() == 0     # some pixels fully transparent


def test_tc20_bounds(heatmap):
    """TC-20: the bounds are a BoundingBox in Lee County lat/lon."""
    bounds = heatmap.generate_heatmap_image()
    assert isinstance(bounds, BoundingBox)
    assert bounds.left < bounds.right and bounds.bottom < bounds.top
    assert -82.3 < bounds.left < bounds.right < -81.5
    assert 26.3 < bounds.bottom < bounds.top < 26.9


def test_tc21_negative_vmin(heatmap):
    """TC-21: vmin below zero is rejected."""
    with pytest.raises(ValueError, match="vmin must be >= 0"):
        heatmap.generate_heatmap_image(vmin=-1e-9)


def test_tc22_vmax_not_above_vmin(heatmap):
    """TC-22: the top of the color scale must be above the bottom."""
    with pytest.raises(ValueError, match="vmax must be greater than vmin"):
        heatmap.generate_heatmap_image(vmin=1e-9, vmax=1e-9)


# ---------------------------------------------------------------------------
# get_legend_data() (TC-23 to TC-28)
# ---------------------------------------------------------------------------

def test_tc23_legend_structure(legend):
    """TC-23: exactly five keys, and the result is JSON-serializable."""
    assert set(legend) == {"colors", "vmin", "vmax", "ticks", "caption"}
    json.dumps(legend)


def test_tc24_legend_colors(legend):
    """TC-24: 256 CSS hex colors, blue at the bottom and red at the top."""
    colors = legend["colors"]
    assert len(colors) == 256
    assert all(re.fullmatch(r"#[0-9a-f]{6}", c) for c in colors)
    assert colors[0] == "#0000ff"
    assert colors[-1] == "#ff0000"


def test_tc25_legend_ticks(legend):
    """TC-25: ticks are sorted, unique, at least 3, and span vmin to vmax."""
    ticks = legend["ticks"]
    assert ticks == sorted(set(ticks))
    assert len(ticks) >= 3
    assert ticks[0] == legend["vmin"]
    assert ticks[-1] == legend["vmax"]


def test_tc26_scale_factor(legend):
    """TC-26: the scaled vmin is between 0.1 and 1, as the docstring states."""
    assert 0.1 <= legend["vmin"] <= 1


def test_tc27_zero_vmin(heatmap):
    """TC-27: with vmin = 0 the scale factor is 1."""
    heatmap.generate_heatmap_image(vmin=0)
    legend = heatmap.get_legend_data()
    assert legend["vmin"] == 0.0
    assert legend["caption"] == "Incident Density (× 1e+00)"


def test_tc28_custom_caption(heatmap):
    """TC-28: a caller-supplied caption is returned as given."""
    heatmap.generate_heatmap_image()
    legend = heatmap.get_legend_data(caption="Calls per sq ft")
    assert legend["caption"] == "Calls per sq ft"


# ---------------------------------------------------------------------------
# Real incident data (TC-29)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n_levels", [1, 2, 3], ids=["1level", "2levels", "3levels"])
def test_tc29_real_incident_data(tmp_path, n_levels):
    """TC-29 (Sample A): the 250 incidents with each scenario's real cluster labels."""
    incidents = pd.read_csv(INCIDENT_CSV).dropna(subset=["lat", "lon"])
    scenario = load_scenario(n_levels)
    np.testing.assert_allclose(scenario[["lat", "lng"]].to_numpy(),
                               incidents[["lat", "lon"]].to_numpy())

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)
    easting, northing = transformer.transform(incidents["lon"].to_numpy(),
                                              incidents["lat"].to_numpy())
    points = np.column_stack([easting, northing])
    bandwidths = SCENARIO_BANDWIDTHS[n_levels]

    kde = KDEHeatMap(points=points, cluster_levels=scenario["density_level"].to_numpy(),
                     bandwidths=bandwidths, increment=INCREMENT, output_dir=str(tmp_path),
                     **lattice_bounds(points, 4 * max(bandwidths)))
    assert kde.density_surface_volume() == pytest.approx(1.0, abs=0.01)

    bounds = kde.generate_heatmap_image()
    assert (tmp_path / "density_overlay.png").is_file()
    assert bounds.bottom < incidents["lat"].min() and bounds.top > incidents["lat"].max()
    assert bounds.left < incidents["lon"].min() and bounds.right > incidents["lon"].max()
