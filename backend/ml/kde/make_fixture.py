"""
Generate test_data/two_clusters.csv, the synthetic fixture used by
test_KDEHeatMap.py (TC-01 to TC-28).

The file holds 105 points in EPSG:2882 (NAD 1983 StatePlane Florida West,
feet) in Lee County, near Fort Myers:

    cluster 0:  60 points around (700,000, 830,000), spread ~2,000 ft
    cluster 1:  40 points around (710,000, 840,000), spread ~800 ft
    noise (-1):  5 points around (700,000, 830,000), spread ~4,000 ft

The random seed is fixed, so running this script again recreates the
identical file:

    python3 make_fixture.py
"""

import csv
import os

import numpy as np

SEED = 0
CENTER_0 = (700_000.0, 830_000.0)
CENTER_1 = (710_000.0, 840_000.0)

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "test_data", "two_clusters.csv")


def make_points():
    """Return (points, cluster_levels) for the fixture."""
    rng = np.random.default_rng(SEED)
    cluster_0 = rng.normal(CENTER_0, 2000, size=(60, 2))
    cluster_1 = rng.normal(CENTER_1, 800, size=(40, 2))
    noise = rng.normal(CENTER_0, 4000, size=(5, 2))
    points = np.vstack([cluster_0, cluster_1, noise])
    levels = np.array([0] * 60 + [1] * 40 + [-1] * 5)
    return points, levels


def main():
    points, levels = make_points()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["x_ft", "y_ft", "cluster_level"])
        for (x, y), level in zip(points, levels):
            writer.writerow([f"{x:.6f}", f"{y:.6f}", int(level)])
    print(f"Wrote {len(points)} points to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
