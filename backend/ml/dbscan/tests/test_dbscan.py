import importlib
import pandas as pd
from shapely.geometry import shape
import pytest
import numpy as np

from ml.dbscan.DBSCANCluster import (
    _dedupe_points, 
    _project_mappable, 
    DBSCANCluster,
    CLUSTER_COLORS,
    NOISE_COLOR,
    inv_transformer,
    run_clusters,
    run_clusters_from_points,
    compute_density_levels,
    compute_density_levels_from_points,
    run_density_clusters,
    load_csv_incidents,
    load_csv_incidents_with_time
)
dbscan_module = importlib.import_module("ml.dbscan.DBSCANCluster")

dedupe_points = np.array([[0, 0], [1, 1], [500, 500]])
def test_dedupe_points_with_collapse():
    assert np.array_equal(_dedupe_points(points=dedupe_points, tolerance=10.0), np.array([[0, 0], [500, 500]]))
    
def test_dedupe_points_with_no_collapse():
    assert np.array_equal(_dedupe_points(points=dedupe_points, tolerance=0.0), dedupe_points)
    
project_incidents = [
    {"lat": 26.6, "lng": -81.9},   # valid
    {"lat": None, "lng": -81.9},   # missing lat -> dropped
    {"lat": 26.6, "lng": None},    # missing lng -> dropped
]   
def test_project_mappable_drops_incidents_missing_lat_or_lng():
    points, lats, _ = _project_mappable(project_incidents)
    
    assert points.shape == (1, 2)
    assert len(lats) == 1
    assert lats[0] == 26.6
    
def test_project_mappable_all_invalid_returns_none():
    assert _project_mappable(incidents=project_incidents[1:]) == (None, None, None)
   
def test_project_mappable_empty_list_returns_none():
    assert _project_mappable([]) == (None, None, None)
    
# input for DBSCANCluster
@pytest.fixture
def one_level_points():
    return np.array([
        [0, 0], [10, 0], [0, 10], [10, 10], # Group A: tight
        [10000, 10000], [10010, 10000], [10000, 10010], [10010, 10010],  # group B: tight, far from A
        [50000, 50000] # lone outlier
    ])

@pytest.fixture
def dbscan_one_level(one_level_points):
    levels = [{"epsilon": 50, "min_pts": 4}]
    return DBSCANCluster(points=one_level_points, levels=levels)

def test_dbscan_one_level_cluster_labels(dbscan_one_level):
    labels = dbscan_one_level.labels_per_level[0]
    
    assert len(np.unique(labels[0:4])) == 1 # Group A only
    assert len(np.unique(labels[0: 8])) == 2 # Group A + B
    assert len(np.unique(labels)) == 3 # Group A + B + other label
    assert labels[8] == -1 # check outlier marked as outlier
    
def test_dbscan_one_level_cluster_noise_mask_flags_outlier(dbscan_one_level):
    assert dbscan_one_level.noise_mask.sum() == 1 # Exactly one noise point

cluster_lats_one_level = np.array([
    26.6000, 26.6001, 26.6002, 26.6003,   # group A
    26.6500, 26.6501, 26.6502, 26.6503,   # group B
    26.7000,                              # lone outlier
])
cluster_lons_one_level = np.array([
    -81.9000, -81.9001, -81.9002, -81.9003,   # group A
    -81.8500, -81.8501, -81.8502, -81.8503,   # group B
    -81.8000,                                 # lone outlier
])

def test_dbscan_one_level_to_geojson(dbscan_one_level):
    geojson = dbscan_one_level.to_geojson(lats=cluster_lats_one_level, lons=cluster_lons_one_level)
    
    assert geojson["metadata"]["n_clusters"] == 2
    assert geojson["metadata"]["n_noise"] == 1
    assert geojson["metadata"]["n_total"] == 9
    assert geojson["metadata"]["eps"] == 50
    assert geojson["metadata"]["min_pts"] == 4
    
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["noise_points"]) == 1

@pytest.fixture
def two_level_points():
    return np.array([
        [0, 0], [5, 0], [0, 5], [5, 5], # Group A: tight
        [10000, 10000], [10010, 10000], [10000, 10010], [10010, 10010],  # group B: tight, far from A
        [50000, 50000] # lone outlier
    ])
    
@pytest.fixture
def dbscan_two_level(two_level_points):
    levels = [{"epsilon": 50, "min_pts": 4}, {"epsilon": 8, "min_pts": 4}] # use 2 cluster levels
    return DBSCANCluster(points=two_level_points, levels=levels)

def test_dbscan_two_level_cluster_labels(dbscan_two_level):
    density_levels = dbscan_two_level.density_levels
    
    assert len(np.unique(density_levels[0:4])) == 1
    assert len(np.unique(density_levels[0:8])) == 2
    assert len(np.unique(density_levels)) == 3
    
    assert density_levels[0] > density_levels[4] # group A tighter than B, so higher density level
    assert density_levels[4] > density_levels[8] # group B is labled, outlier is -1, so should be higher

cluster_lats_two_level = cluster_lats_one_level # alias for one level latitudes
cluster_lons_two_level = cluster_lons_one_level # alias for one level longitudes

def test_dbscan_two_level_to_density_geojson(dbscan_two_level):
    density_geojson = dbscan_two_level.to_density_geojson(lats=cluster_lats_two_level, lons=cluster_lons_two_level)
    
    assert density_geojson["metadata"]["n_total"] == 9
    assert density_geojson["metadata"]["n_noise"] == 1
    assert density_geojson["metadata"]["n_levels"] == 2
    assert density_geojson["metadata"]["counts_by_level"] == {1: 4, 0: 4, -1: 1}
    
    assert density_geojson["type"] == "FeatureCollection"
    
    levels_from_geojson = [f["properties"]["density_level"] for f in density_geojson["features"]]
    assert levels_from_geojson == dbscan_two_level.density_levels.tolist()
