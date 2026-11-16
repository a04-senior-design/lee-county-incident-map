# DBSCAN Unit Tests

Unit tests for [`ml/dbscan/DBSCANCluster.py`](../DBSCANCluster.py), in [`test_dbscan.py`](test_dbscan.py).

Unlike the API tests in `api/tests/`, these call the functions and class directly with small, hand-made inputs. They need no Flask client, database or CSV data.

## Running the tests

From the `backend/` directory, with the virtualenv active:

```bash
python -m pytest ml/dbscan/tests/test_dbscan.py -v
```

Use `python -m pytest` (not bare `pytest`) so the current directory is on the import path and `ml.dbscan...` imports resolve.

Run a single test or a subset:

```bash
python -m pytest ml/dbscan/tests/test_dbscan.py::test_dbscan_no_clusters -v
python -m pytest ml/dbscan/tests/test_dbscan.py -k dedupe -v
python -m pytest ml/dbscan/tests/test_dbscan.py -k run_clusters -v
```

## Import note

The tests import from the module path (`from ml.dbscan.DBSCANCluster import ...`) rather than `import ml.dbscan.DBSCANCluster as x`. In `ml/dbscan/__init__.py`, the name `DBSCANCluster` refers to the **class**, which shadows the module of the same name. `from ... import` looks the module up in `sys.modules`, so it avoids the problem.

When the module object itself is needed (for example to monkeypatch `_CSV_PATH`), the test file gets it with `importlib.import_module("ml.dbscan.DBSCANCluster")` and stores it as `dbscan_module`.

## Test data

All coordinates are tiny, hand-made point sets. Cluster inputs are in feet (the units of EPSG:2882, which `DBSCANCluster` expects). Module-level incident data uses degrees.

| Name | What it is |
|------|------------|
| `dedupe_points` | 3 points: two within 1 ft of each other, one far away |
| `project_incidents` | 3 incidents: one valid, one missing `lat`, one missing `lng` |
| `one_level_points` (fixture) | 9 points: Group A (4 points, 10 ft apart), Group B (4 points, 10 ft apart, ~10,000 ft from A), and 1 lone outlier |
| `two_level_points` (fixture) | Same layout, but Group A is tighter (5 ft apart) so it separates from B at a smaller epsilon |
| `cluster_lats_*` / `cluster_lons_*` | Made-up Lee County degree values, aligned index-for-index with the points. Used only to fill GeoJSON point features. The two-level arrays are aliases of the one-level arrays |
| `module_incidents` | 6 incidents in degrees: 4 about 35-50 ft apart (one cluster), 1 far away (noise), 1 with `lat: None` (dropped). 5 are mappable |
| `LEVEL` / `TWO_LEVELS` | Level configs for the module-level functions: `epsilon=300` (and `epsilon=60` for the second level), `min_pts=4` |

Index layout for the cluster datasets: `0-3` = Group A, `4-7` = Group B, `8` = outlier.

### Fixtures

| Fixture | Provides |
|---------|----------|
| `dbscan_one_level` | `DBSCANCluster` over `one_level_points`, `epsilon=50`, `min_pts=4` |
| `one_level_geojson` | `to_geojson` output of `dbscan_one_level` with `cluster_color="#123456"` |
| `dbscan_two_level` | `DBSCANCluster` over `two_level_points`, `epsilon=50` and `epsilon=8`, `min_pts=4` |
| `two_level_density_geojson` | `to_density_geojson` output of `dbscan_two_level` |

## What each test covers

### `_dedupe_points`

| Test | Checks |
|------|--------|
| `test_dedupe_points_with_collapse` | With `tolerance=10.0`, the two near points collapse to one, leaving `[[0, 0], [500, 500]]` |
| `test_dedupe_points_with_no_collapse` | With `tolerance=0.0`, the input is returned unchanged |

### `_project_mappable`

| Test | Checks |
|------|--------|
| `test_project_mappable_drops_incidents_missing_lat_or_lng` | Only the valid incident survives: `points.shape == (1, 2)`, one lat, value unchanged |
| `test_project_mappable_all_invalid_returns_none` | All-invalid input returns `(None, None, None)` |
| `test_project_mappable_empty_list_returns_none` | Empty input returns `(None, None, None)` |

### `DBSCANCluster` clustering, single level (`epsilon=50`, `min_pts=4`)

| Test | Checks |
|------|--------|
| `test_dbscan_one_level_cluster_labels` | Group A shares one label, A and B together have two labels, the outlier is `-1` |
| `test_dbscan_one_level_cluster_noise_mask_flags_outlier` | `noise_mask` marks exactly one point as noise |
| `test_dbscan_group_below_min_pts_is_noise` | 3 points with `min_pts=4` are all noise (`min_pts` counts the point itself) |
| `test_dbscan_group_at_min_pts_is_cluster` | 4 points with `min_pts=4` form exactly one cluster |
| `test_dbscan_empty_points_raises` | An empty `(0, 2)` array raises `ValueError` (from sklearn) |

### `DBSCANCluster` core vs. border points (`epsilon=20`, `min_pts=4`)

| Test | Checks |
|------|--------|
| `test_dbscan_border_point_is_not_core_point` | A point reachable from a core point, but without enough neighbors of its own, still joins the cluster |
| `test_dbscan_cluster_expands_through_chain_of_core_points` | A point 32 ft from the nearest cluster point stays noise (`-1`), leaving two unique labels |

A noise point within `epsilon` of a border point counts toward that border point's neighborhood and can turn it into a core point. Keep test points outside that range if you want the border point to stay a border point.

### `to_geojson`, single level

All use `one_level_geojson` (`cluster_color="#123456"`) unless noted.

| Test | Checks |
|------|--------|
| `test_dbscan_one_level_geojson_metadata` | `n_clusters=2`, `n_noise=1`, `n_total=9`, `eps`, `min_pts` |
| `test_dbscan_one_level_noise_points` | `noise_points` holds exactly the outlier's lat and lng |
| `test_one_level_geojson_polygons_come_first` | The first two features are polygons |
| `test_one_level_geojson_polygon_point_count` | Every polygon reports `point_count == 4` |
| `test_one_level_geojson_point_colors` | Noise points use `NOISE_COLOR`, cluster points use the `cluster_color` override |
| `test_to_geojson_multi_level_raises` | Calling `to_geojson` on a two-level fit raises `ValueError` ("exactly one level") |
| `test_dbscan_no_clusters` | Widely spaced points give `n_clusters == 0`, `n_noise == 4` and no polygon features |

### `DBSCANCluster`, two levels (`epsilon=50` and `epsilon=8`, `min_pts=4`)

Expected density levels: Group A = `1` (clusters at both levels), Group B = `0` (clusters only at the loose level), outlier = `-1`.

| Test | Checks |
|------|--------|
| `test_dbscan_two_level_cluster_labels` | Three distinct density levels, with A > B > outlier |
| `test_dbscan_two_level_density_geojson_metadata` | `n_total`, `n_noise`, `n_levels`, and `counts_by_level == {1: 4, 0: 4, -1: 1}` |
| `test_dbscan_two_level_density_geojson_levels_match` | Per-feature `density_level` values match the object's `density_levels` |
| `test_dbscan_two_level_density_geojson_lon_lat_swap` | Coordinates are ordered `[lon, lat]`, not `[lat, lon]` |

### `run_clusters`

| Test | Checks |
|------|--------|
| `test_run_clusters_empty_returns_empty_collection` | Empty input gives no features and zeroed metadata |
| `test_run_clusters_all_unmappable_returns_empty_collection` | An incident with no lat/lng gives the same empty result |
| `test_run_clusters_end_to_end` | On `module_incidents`: `n_total=5`, `n_clusters=1`, `n_noise=1` |

### `run_clusters_from_points`

| Test | Checks |
|------|--------|
| `test_run_clusters_from_points_none_returns_empty` | `None` points give no features |
| `test_run_clusters_from_points_empty_array_returns_empty` | An empty array gives zeroed metadata |
| `test_run_clusters_from_points_round_trips_coordinates` | Projecting to feet and back returns the original lat/lng within `1e-4` degrees (about 10 m) |

### `compute_density_levels` and `compute_density_levels_from_points`

| Test | Checks |
|------|--------|
| `test_compute_density_levels_empty_levels_returns_empty` | Empty `levels` returns `[]` |
| `test_compute_density_levels_no_mappable_incidents_returns_empty` | No mappable incidents returns `[]` |
| `test_compute_density_levels_from_points_none_returns_empty` | `None` points return `[]` |
| `test_compute_density_levels_from_points_empty_levels_returns_empty` | Empty `levels` returns `[]` |

### `run_density_clusters`

| Test | Checks |
|------|--------|
| `test_run_density_clusters_empty_incidents_reports_levels` | Empty incidents still report `n_levels == len(levels)` and an empty `counts_by_level` |
| `test_run_density_clusters_empty_levels_returns_empty` | Empty `levels` gives `n_total == 0` and `n_levels == 0` |
| `test_run_density_clusters_end_to_end` | On `module_incidents`: `n_total=5`, `counts_by_level == {0: 4, -1: 1}` |

## Why the epsilons were chosen

- Single level: points in a group are 10 ft apart, well under `epsilon=50`, so each group connects. The groups are ~10,000 ft apart, so they never merge.
- Two levels: the tight epsilon (8) must be at least Group A's diagonal spacing (about 7.07 ft) and below Group B's 10 ft spacing. That makes A cluster at both levels and B only at the loose one. Avoid choosing an epsilon that lands exactly on a pairwise distance, because sklearn's neighborhood check is inclusive.
- Module-level data: 0.0001 degrees is roughly 35 ft, so the four close incidents sit well inside `epsilon=300`, and the far incident is miles outside it.

## Test coverage

Current coverage for `DBSCANCluster.py`: **93%** (up from 72%).

Measure it from `backend/` with `pytest-cov` (`pip install pytest-cov`):

```bash
python -m pytest ml/dbscan/tests --cov=ml.dbscan.DBSCANCluster --cov-branch --cov-report=term-missing
```

- `--cov-branch` adds branch coverage on top of statement coverage.
- `--cov-report=term-missing` lists the uncovered lines in the `Missing` column.
- For a line-by-line view, use `--cov-report=html` and open `htmlcov/index.html`. Do not commit `htmlcov/` or `.coverage`.

## Not yet covered

- `load_csv_incidents` and `load_csv_incidents_with_time` (imported but not tested; plan: monkeypatch `dbscan_module._CSV_PATH` to a small CSV in `tmp_path`).
- Output shape of `compute_density_levels` on valid incidents (`easting`, `northing`, `density_level` keys). A draft is commented out in the test file.
- `compute_density_levels_from_points` with valid points.
- Input-order independence of `levels` (the constructor sorts them loosest first).
- Three or more levels.
- Cluster color wrapping past the five entries in `CLUSTER_COLORS`.
- Polygon geometry validity and location, and custom `source_crs` / `target_crs`.
- Extra `_dedupe_points` and `_project_mappable` edge cases (representative is an original point, single and empty input, zero-valued coordinates).
