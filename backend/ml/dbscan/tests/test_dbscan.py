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

@pytest.fixture
def one_level_geojson(dbscan_one_level):
    return dbscan_one_level.to_geojson(
        lats=cluster_lats_one_level, 
        lons=cluster_lons_one_level, 
        cluster_color="#123456"
    )

def test_dbscan_one_level_geojson_metadata(one_level_geojson):
    
    assert one_level_geojson["metadata"]["n_clusters"] == 2
    assert one_level_geojson["metadata"]["n_noise"] == 1
    assert one_level_geojson["metadata"]["n_total"] == 9
    assert one_level_geojson["metadata"]["eps"] == 50
    assert one_level_geojson["metadata"]["min_pts"] == 4

def test_dbscan_one_level_noise_points(one_level_geojson):
    assert one_level_geojson["noise_points"] == [
        {"lat": float(cluster_lats_one_level[8]), "lng": float(cluster_lons_one_level[8])}
    ]
    
def test_one_level_geojson_polygons_come_first(one_level_geojson):
    assert all(f["properties"]["feature_type"] == "polygon" for f in one_level_geojson["features"][:2])

def test_one_level_geojson_polygon_point_count(one_level_geojson):
    polygons = [f for f in one_level_geojson["features"] if f["properties"]["feature_type"] == "polygon"]
    assert polygons
    assert all(p["properties"]["point_count"] == 4 for p in polygons)
    
def test_one_level_geojson_point_colors(one_level_geojson):
    points = [f for f in one_level_geojson["features"] if f["properties"]["feature_type"] == "point"]
    assert points
   
    for point in points:
        expected = NOISE_COLOR if point["properties"]["cluster_id"] == -1 else "#123456"
        assert point["properties"]["color"] == expected

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

@pytest.fixture
def two_level_density_geojson(dbscan_two_level):
    return dbscan_two_level.to_density_geojson(
        lats=cluster_lats_two_level, 
        lons=cluster_lons_two_level
    )

def test_dbscan_two_level_density_geojson_metadata(two_level_density_geojson):
    assert two_level_density_geojson["metadata"]["n_total"] == 9
    assert two_level_density_geojson["metadata"]["n_noise"] == 1
    assert two_level_density_geojson["metadata"]["n_levels"] == 2
    assert two_level_density_geojson["metadata"]["counts_by_level"] == {1: 4, 0: 4, -1: 1}

def test_dbscan_two_level_density_geojson_levels_match(dbscan_two_level, two_level_density_geojson):
    levels_from_geojson = [f["properties"]["density_level"] for f in two_level_density_geojson["features"]]
    assert levels_from_geojson == dbscan_two_level.density_levels.tolist()
    
def test_dbscan_two_level_density_geojson_lon_lat_swap(two_level_density_geojson):
    assert two_level_density_geojson["features"][0]["geometry"]["coordinates"] == [
        cluster_lons_two_level[0], cluster_lats_two_level[0]
    ]

def test_to_geojson_multi_level_raises(dbscan_two_level):
    with pytest.raises(ValueError, match="exactly one level"):
        dbscan_two_level.to_geojson(lats=cluster_lats_two_level, lons=cluster_lons_two_level)
        
def test_dbscan_group_below_min_pts_is_noise():
    points = np.array([[0,0], [10,0], [0, 10]])
    cluster = DBSCANCluster(
        points=points,
        levels=[{"epsilon": 50, "min_pts": 4}]
    )
    assert (cluster.labels_per_level[0] == -1).all()
    
def test_dbscan_group_at_min_pts_is_cluster():
    points = np.array([[0,0], [10,0], [0, 10], [10, 10]])
    cluster = DBSCANCluster(
        points=points,
        levels=[{"epsilon": 50, "min_pts": 4}]
    )
    
    labels = cluster.labels_per_level[0]
    assert (labels != -1).all()
    assert len(np.unique(labels)) == 1

def test_dbscan_border_point_is_not_core_point():
    points = np.array([[0, 0], [10, 0], [0, 10], [10, 10], [28, 5]])
    cluster = DBSCANCluster(
        points=points,
        levels=[{"epsilon": 20, "min_pts": 4}]
    )
    
    labels = cluster.labels_per_level[0]
    assert labels[4] != -1
    assert len(np.unique(labels)) == 1

def test_dbscan_cluster_expands_through_chain_of_core_points():
    points = np.array([[0, 0], [10, 0], [0, 10], [10, 10], [28, 5], [60, 5]])
    cluster = DBSCANCluster(
        points=points,
        levels=[{"epsilon": 20, "min_pts": 4}]
    )
    
    labels = cluster.labels_per_level[0]
    print(labels)
    
    assert labels[5] == -1
    assert len(np.unique(labels)) == 2
    
def test_dbscan_no_clusters():
    points = np.array([[0, 0], [1000, 0], [0, 1000], [1000, 1000]])
    cluster = DBSCANCluster(
        points=points, 
        levels=[{"epsilon": 50, "min_pts": 4}]
    )
    
    geojson = cluster.to_geojson(lats=np.array([26.6, 26.7, 26.8, 26.9]), lons=np.array([-81.9, -81.8, -81.7, -81.6]))
    assert geojson["metadata"]["n_clusters"] == 0
    assert geojson["metadata"]["n_noise"] == 4
    
    polygons = [f for f in geojson["features"] if f["properties"]["feature_type"] == "polygon"]
    assert not polygons

def test_dbscan_empty_points_raises():
    with pytest.raises(ValueError):
        DBSCANCluster(points=np.empty((0, 2)), levels=[{"epsilon": 50, "min_pts": 4}])