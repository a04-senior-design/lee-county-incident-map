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
python -m pytest ml/dbscan/tests/test_dbscan.py::test_dbscan_one_level_to_geojson -v
python -m pytest ml/dbscan/tests/test_dbscan.py -k dedupe -v
```

## Import note

The tests import from the module path (`from ml.dbscan.DBSCANCluster import ...`) rather than `import ml.dbscan.DBSCANCluster as x`. In `ml/dbscan/__init__.py`, the name `DBSCANCluster` refers to the **class**, which shadows the module of the same name. `from ... import` looks the module up in `sys.modules`, so it avoids the problem.

## Test data

All coordinates are tiny, hand-made point sets in feet (the units of EPSG:2882, which `DBSCANCluster` expects). Each module-level dataset has its own unique name so one cannot overwrite another.

| Name | What it is |
|------|------------|
| `dedupe_points` | 3 points: two within 1 ft of each other, one far away |
| `project_incidents` | 3 incidents: one valid, one missing `lat`, one missing `lng` |
| `cluster_points_one_level` | 9 points: Group A (4 points, 10 ft apart), Group B (4 points, 10 ft apart, ~10,000 ft from A), and 1 lone outlier |
| `cluster_points_two_level` | Same layout, but Group A is tighter (5 ft apart) so it separates from B at a smaller epsilon |
| `cluster_lats_*` / `cluster_lons_*` | Made-up Lee County degree values, aligned index-for-index with the points. Used only to fill GeoJSON point features |

Index layout for the cluster datasets: `0-3` = Group A, `4-7` = Group B, `8` = outlier.

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

### `DBSCANCluster`, single level (`epsilon=50`, `min_pts=4`)

| Test | Checks |
|------|--------|
| `test_dbscan_one_level_cluster_labels` | Group A shares one label, A and B together have two labels, the outlier is `-1` |
| `test_dbscan_one_level_cluster_noise_mask_flags_outlier` | `noise_mask` marks exactly one point as noise |
| `test_dbscan_one_level_to_geojson` | `to_geojson` metadata (`n_clusters=2`, `n_noise=1`, `n_total=9`, `eps`, `min_pts`), the `FeatureCollection` type, and one entry in `noise_points` |

### `DBSCANCluster`, two levels (`epsilon=50` and `epsilon=8`, `min_pts=4`)

Expected density levels: Group A = `1` (clusters at both levels), Group B = `0` (clusters only at the loose level), outlier = `-1`.

| Test | Checks |
|------|--------|
| `test_dbscan_two_level_cluster_labels` | Three distinct density levels, with A > B > outlier |
| `test_dbscan_two_level_to_density_geojson` | Metadata (`n_total`, `n_noise`, `n_levels`, `counts_by_level == {1: 4, 0: 4, -1: 1}`), the `FeatureCollection` type, and per-feature `density_level` values matching the object's `density_levels` |

## Why the epsilons were chosen

- Single level: points in a group are 10 ft apart, well under `epsilon=50`, so each group connects. The groups are ~10,000 ft apart, so they never merge.
- Two levels: the tight epsilon (8) must be at least Group A's diagonal spacing (about 7.07 ft) and below Group B's 10 ft spacing. That makes A cluster at both levels and B only at the loose one. Avoid choosing an epsilon that lands exactly on a pairwise distance, because sklearn's neighborhood check is inclusive.

## Not yet covered

- `to_geojson` raising `ValueError` when called on a multi-level fit (use `pytest.raises`).
- `to_geojson` with a custom `cluster_color`.
- Input-order independence of `levels` (the constructor sorts them).
- `run_clusters`, `run_density_clusters` and `compute_density_levels` end to end.
