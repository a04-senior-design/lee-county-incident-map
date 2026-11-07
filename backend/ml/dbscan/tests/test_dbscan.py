from ml.dbscan.DBSCANCluster import _dedupe_points, _project_mappable
import numpy as np

points = np.array([[0, 0], [1, 1], [500, 500]])
def test_dedupe_points_with_collapse():
    assert np.array_equal(_dedupe_points(points=points, tolerance=10.0), [[0, 0], [500, 500]])
    
def test_dedupe_points_with_no_collapse():
    assert np.array_equal(_dedupe_points(points=points, tolerance=0.0), points)
    
incidents = [
    {"lat": 26.6, "lng": -81.9},   # valid
    {"lat": None, "lng": -81.9},   # missing lat -> dropped
    {"lat": 26.6, "lng": None},    # missing lng -> dropped
]    
    
def test_project_mappable_drops_incidents_missing_lat_or_lng():
    points, lats, _ = _project_mappable(incidents)
    
    assert points.shape == (1, 2)
    assert len(lats) == 1
    assert lats[0] == 26.6
    
def test_project_mappable_all_invalid_returns_none():
    points, lats, lons = _project_mappable(incidents=incidents[1:])
    
    assert points == lats == lons == None

def test_project_mappable_empty_list_returns_none():
    assert _project_mappable([]) == (None, None, None)
    