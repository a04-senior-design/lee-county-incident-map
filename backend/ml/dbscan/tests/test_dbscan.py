from ml.dbscan.DBSCANCluster import _dedupe_points, _project_mappable, DBSCANCluster
import numpy as np

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
cluster_points = np.array([
    [0, 0], [10, 0], [0, 10], [10, 10], # Group A: tight
    [10000, 10000], [10010, 10000], [10000, 10010], [10010, 10010],  # group B: tight, far from A
    [50000, 50000] # lone outlier
])
cluster_levels = [{"epsilon": 50, "min_pts": 4}]
    
def test_dbscan_cluster_labels():
    dbscan = DBSCANCluster(points=cluster_points, levels=cluster_levels)
    labels = dbscan.labels_per_level[0]
    
    assert len(np.unique(labels[0:4])) == 1 # Group A only
    assert len(np.unique(labels[0: 8])) == 2 # Group A + B
    assert len(np.unique(labels)) == 3 # Group A + B + other label
    assert labels[8] == -1 # check outlier marked as outlier