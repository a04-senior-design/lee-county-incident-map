"""
Unit tests for the BandwidthOptimizer class (BandwidthOptimizer.py).

Test IDs (BW-01 to BW-08) match the BandwidthOptimizer Unit Test Plan, which
gives the purpose, setup and expected result of each case.

These tests share the kde_unit_test folder and its test_data with the
KDEHeatMap tests, and run independently of them.  Run from that folder:

    python3 -m pytest test_BandwidthOptimizer.py -v
    python3 -m pytest test_BandwidthOptimizer.py --cov=BandwidthOptimizer --cov-branch --cov-report=term-missing

Expect 23 passed in under two minutes: five cases try several inputs and pytest
reports each input on its own line.  BW-08 takes most of that time; skip it
with -k "not bw08".
"""

import io
import os

import numpy as np
import pandas as pd
import pytest
from pyproj import Transformer
from scipy.spatial.distance import cdist

import BandwidthOptimizer as bwo_module
from BandwidthOptimizer import BandwidthOptimizer


# ---------------------------------------------------------------------------
# Paths and shared settings
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_DATA = os.path.join(HERE, "test_data")
FIXTURE_CSV = os.path.join(TEST_DATA, "two_clusters.csv")
INCIDENT_CSV = os.path.join(TEST_DATA, "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv")

INCREMENT = 100            # lattice spacing in feet for the baseline setup
REAL_DATA_INCREMENT = 300  # lattice spacing in feet for BW-08
LOWER_BOUND = 500          # the class's default bandwidth limits, in feet
UPPER_BOUND = 10_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_fixture():
    """Read test_data/two_clusters.csv as (points, cluster_levels)."""
    data = np.loadtxt(FIXTURE_CSV, delimiter=",", skiprows=1)
    return data[:, :2], data[:, 2].astype(int)


def point_bounds(points):
    """Bounds taken from the points' minimum and maximum x and y."""
    x_min, y_min = points.min(axis=0)
    x_max, y_max = points.max(axis=0)
    return dict(x_min_no_padding=x_min, y_min_no_padding=y_min,
                x_max_no_padding=x_max, y_max_no_padding=y_max)


def build(points, levels, increment=INCREMENT):
    """Build a BandwidthOptimizer with bounds from the points and the default bandwidth limits."""
    points = np.asarray(points, dtype=float)
    return BandwidthOptimizer(points=points, cluster_levels=levels, increment=increment,
                              **point_bounds(points))


def exact_loo_nll(points, levels, bandwidths):
    """Exact leave-one-out negative log-likelihood, from the equations in Reference checks.

    Each non-noise point's density is the average of every other point's Gaussian,
    each using that other point's cluster-level bandwidth.  No lattice, no interpolation.
    """
    keep = levels != -1
    x = points[keep]
    h = np.asarray(bandwidths, dtype=float)[levels[keep]]     # bandwidth of each point j
    n = len(x)
    sq_dist = cdist(x, x, "sqeuclidean")                      # ||x_i - x_j||^2
    kernel = np.exp(-sq_dist / (2 * h**2)) / (2 * np.pi * h**2)
    np.fill_diagonal(kernel, 0.0)                              # leave point i out
    f_loo = kernel.sum(axis=1) / (n - 1)
    return -np.sum(np.log(f_loo))


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

@pytest.fixture(scope="module")
def fixture_data():
    """The two_clusters.csv points and cluster levels."""
    return load_fixture()


@pytest.fixture(scope="module")
def baseline(fixture_data):
    """Baseline setup: two_clusters.csv, bounds from the points, increment 100, limits 500 / 10,000."""
    points, levels = fixture_data
    return build(points, levels)


# ---------------------------------------------------------------------------
# Input checks (BW-01, BW-07)
# ---------------------------------------------------------------------------

def bad_input(case, points, levels):
    """Constructor arguments for one BW-01 input, starting from the baseline setup."""
    args = dict(points=points, cluster_levels=levels, increment=INCREMENT, **point_bounds(points))
    if case == "a_no_points":
        args.update(points=np.empty((0, 2)), cluster_levels=np.empty(0, dtype=int))
    elif case == "b_extra_level":
        args.update(cluster_levels=np.append(levels, 0))
    elif case == "c_infinite_bound":
        args.update(upper_bound=np.inf)
    elif case == "d_zero_lower_bound":
        args.update(lower_bound=0)
    elif case == "e_equal_bounds":
        args.update(upper_bound=LOWER_BOUND)
    elif case == "f_zero_increment":
        args.update(increment=0)
    elif case == "g_all_noise":
        args.update(cluster_levels=np.full(len(levels), -1))
    elif case == "h_one_non_noise_point":
        one = np.full(len(levels), -1)
        one[0] = 0
        args.update(cluster_levels=one)
    return args


BW01_CASES = [
    ("a_no_points", "No points were given"),
    ("b_extra_level", "Expected one cluster level per point"),
    ("c_infinite_bound", "Bandwidth bounds must be finite"),
    ("d_zero_lower_bound", "lower_bound must be > 0"),
    ("e_equal_bounds", "upper_bound must be greater than lower_bound"),
    ("f_zero_increment", "increment must be > 0"),
    ("g_all_noise", "All points are noise"),
    ("h_one_non_noise_point", "At least two non-noise points are required"),
]


@pytest.mark.parametrize("case, message", BW01_CASES, ids=[case for case, _ in BW01_CASES])
def test_bw01_bad_constructor_inputs(fixture_data, case, message):
    """BW-01: each bad input raises ValueError with the expected message."""
    points, levels = fixture_data
    with pytest.raises(ValueError, match=message):
        BandwidthOptimizer(**bad_input(case, points, levels))


@pytest.mark.parametrize("step, maximum, message", [
    (0, 3000, "increment should be > 0"),
    (100, LOWER_BOUND, "maximum allowable bandwidth should be greater than the lower bound"),
], ids=["a_zero_step", "b_max_equals_lower_bound"])
def test_bw07_bad_brute_force_inputs(baseline, step, maximum, message):
    """BW-07: brute_force_optimizer rejects a step of 0 and a maximum at the lower bound."""
    with pytest.raises(ValueError, match=message):
        baseline.brute_force_optimizer(step, maximum)


# ---------------------------------------------------------------------------
# Setup and internal steps (BW-02 to BW-05)
# ---------------------------------------------------------------------------

def test_bw02_cluster_split_and_starting_points(baseline, fixture_data):
    """BW-02: noise dropped, points ordered by level, and three starting gaps."""
    points, levels = fixture_data
    assert baseline.num_bandwidths == 2
    assert baseline.cluster_sizes == [60, 40]
    assert baseline.num_arranged_points == 100

    # level 0 points first, then level 1, each in file order; the 5 noise points are gone
    expected_order = np.concatenate([points[levels == 0], points[levels == 1]])
    np.testing.assert_array_equal(baseline.arranged_points, expected_order)

    # 0.03, 0.3 and 0.9 times (10,000 - 500) / 2
    np.testing.assert_allclose(baseline.candidate_start_bw_diffs,
                               [[142.5, 142.5], [1425, 1425], [4275, 4275]])


def test_bw03_bandwidth_unpacking(baseline):
    """BW-03: ln(100), ln(300) unpack to [900, 800]; a 3-value input is rejected."""
    # last bandwidth = 500 + 300 = 800; the one before it = 800 + 100 = 900
    np.testing.assert_allclose(baseline._unpack_bandwidths(np.log([100.0, 300.0])),
                               [900.0, 800.0], rtol=1e-9)

    with pytest.raises(ValueError, match="Expected number of bandwidth diffs to match"):
        baseline._unpack_bandwidths(np.log([100.0, 200.0, 300.0]))


@pytest.mark.parametrize("bandwidths", [
    [1500, 600], [3000, 1000], [900, 550], [1200, 534],
], ids=["a_1500-600", "b_3000-1000", "c_900-550", "d_1200-534"])
def test_bw04_objective_matches_exact_score(baseline, fixture_data, bandwidths):
    """BW-04 (a) to (d): the class's score equals the exact leave-one-out score within 0.1%."""
    points, levels = fixture_data
    score = baseline._loo_neg_log_likelihood_from_bandwidths(bandwidths)
    assert score == pytest.approx(exact_loo_nll(points, levels, bandwidths), rel=1e-3)


def test_bw04_isolated_point_recomputed_exactly(fixture_data, monkeypatch):
    """BW-04 (e): a level-0 point 10,000 ft east of the data goes through the exact-recompute step."""
    points, levels = fixture_data
    extra = np.array([points[:, 0].max() + 10_000, points[levels != -1, 1].mean()])
    points_e = np.vstack([points, extra])
    levels_e = np.append(levels, 0)
    bandwidths = [1500, 600]
    optimizer = build(points_e, levels_e)

    # watch the exact-recompute step: it calls cdist with the flagged points as the first argument
    recomputed = []

    def watched_cdist(flagged_points, *args, **kwargs):
        recomputed.append(np.array(flagged_points))
        return cdist(flagged_points, *args, **kwargs)

    monkeypatch.setattr(bwo_module, "cdist", watched_cdist)

    score = optimizer._loo_neg_log_likelihood_from_bandwidths(bandwidths)
    assert score == pytest.approx(exact_loo_nll(points_e, levels_e, bandwidths), rel=1e-3)

    assert len(recomputed) == 1, "the exact-recompute step did not run"
    assert any(np.allclose(row, extra) for row in recomputed[0]), \
        "the isolated point was not among the points recomputed exactly"


@pytest.mark.parametrize("bandwidths", [[11_000, 600], [np.inf, 600]],
                         ids=["a_above_upper_bound", "b_infinite"])
def test_bw05_out_of_range_penalty(baseline, bandwidths, monkeypatch):
    """BW-05: bandwidths above the upper bound, or infinite, score 1e10 without building a KDE."""
    def no_kde(*args, **kwargs):
        raise AssertionError("a KDE model was built for out-of-range bandwidths")

    monkeypatch.setattr(bwo_module, "KDEHeatMap", no_kde)
    assert baseline._loo_neg_log_likelihood_from_bandwidths(bandwidths) == 1e10


# ---------------------------------------------------------------------------
# Optimizer (BW-06, BW-08)
# ---------------------------------------------------------------------------

def test_bw06_optimizer_agrees_with_brute_force(fixture_data, capsys):
    """BW-06: the optimizer scores no higher than brute force's best, within one 100 ft step of it."""
    points, levels = fixture_data
    optimizer = build(points, levels)

    bandwidths = optimizer.optimize_bandwidths()
    printed = capsys.readouterr().out
    assert "best bandwidth:" in printed

    results = optimizer.brute_force_optimizer(100, 3000)
    assert len(results) == 325
    best_bandwidths, best_score = min(results, key=lambda r: r[1])

    assert optimizer.best_result.fun <= best_score
    assert len(bandwidths) == 2
    assert np.all(np.abs(np.asarray(bandwidths) - np.asarray(best_bandwidths)) <= 100), \
        f"optimizer {bandwidths} vs brute force {best_bandwidths}"


@pytest.mark.parametrize("n_levels", [1, 2, 3], ids=["1level", "2levels", "3levels"])
def test_bw08_real_incident_data(n_levels, capsys):
    """BW-08 (Sample A): the 250 incidents with each scenario's real cluster labels."""
    incidents = pd.read_csv(INCIDENT_CSV).dropna(subset=["lat", "lon"])
    scenario = load_scenario(n_levels)
    np.testing.assert_allclose(scenario[["lat", "lng"]].to_numpy(),
                               incidents[["lat", "lon"]].to_numpy())

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)
    easting, northing = transformer.transform(incidents["lon"].to_numpy(),
                                              incidents["lat"].to_numpy())
    points = np.column_stack([easting, northing])

    optimizer = build(points, scenario["density_level"].to_numpy(), increment=REAL_DATA_INCREMENT)
    bandwidths = np.asarray(optimizer.optimize_bandwidths())
    capsys.readouterr()

    assert len(bandwidths) == n_levels
    assert np.all(np.diff(bandwidths) < 0), f"bandwidths not in decreasing order: {bandwidths}"
    assert np.all((bandwidths >= LOWER_BOUND) & (bandwidths <= UPPER_BOUND)), \
        f"bandwidths outside {LOWER_BOUND} to {UPPER_BOUND} ft: {bandwidths}"
