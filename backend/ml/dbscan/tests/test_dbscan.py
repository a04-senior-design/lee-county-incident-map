import ml.dbscan.DBSCANCluster as dbscan
import numpy as np

points = np.array([[0, 0], [1, 1], [500, 500]])
def test_dedupe_points_with_collapse():
    assert dbscan._dedupe_points(points=points, tolerance=10.0) == [[0, 0], [500, 500]]
    
def test_dedupe_points_with_no_collapse():
    assert dbscan._dedupe_points(points=points, tolerance=0.0) == points