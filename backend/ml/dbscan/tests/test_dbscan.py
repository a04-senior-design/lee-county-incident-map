from ml.dbscan.DBSCANCluster import _dedupe_points, _project_mappable
import numpy as np

points = np.array([[0, 0], [1, 1], [500, 500]])
def test_dedupe_points_with_collapse():
    assert np.array_equal(_dedupe_points(points=points, tolerance=10.0), [[0, 0], [500, 500]])
    
def test_dedupe_points_with_no_collapse():
    assert np.array_equal(_dedupe_points(points=points, tolerance=0.0), points)