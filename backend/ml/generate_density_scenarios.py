"""
Generate 3 sample scenarios showing how the DBSCAN density_level output
(see run_density_clusters() in ml/dbscan/DBSCANCluster.py) changes as more
nested cluster_levels thresholds (street/neighborhood/district) are stacked:

    1 level  -> street only                     density_level in {-1, 0}
    2 levels -> street + neighborhood            density_level in {-1, 0, 1}
    3 levels -> street + neighborhood + district  density_level in {-1, 0, 1, 2}

Uses the same 250-row reproducible sample (random_state=42) as
ml/dbscan_demo.py, drawn from the late-paper incidents CSV. Each scenario is
written as a plain-text file under output/.

Run from backend/ with the venv activated:
    python -m ml.generate_density_scenarios
"""

import os

import pandas as pd

from ml.dbscan import _CSV_PATH, cluster_levels, run_density_clusters

N_POINTS = 250
RANDOM_SEED = 42

_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")

SCENARIOS = {
    "1level": ["street"],
    "2levels": ["street", "neighborhood"],
    "3levels": ["street", "neighborhood", "district"],
}


def load_sample_incidents(n: int = N_POINTS, seed: int = RANDOM_SEED) -> list:
    df = pd.read_csv(_CSV_PATH).dropna(subset=["lat", "lon"]).sample(n=n, random_state=seed)
    df = df.sort_index()  # preserve original CSV row order, .sample() shuffles rows
    return df[["lat", "lon"]].rename(columns={"lon": "lng"}).to_dict(orient="records")


def write_scenario(name: str, level_names: list, incidents: list) -> str:
    levels = [cluster_levels[level_name] for level_name in level_names]
    result = run_density_clusters(incidents, levels)

    out_path = os.path.join(_OUTPUT_DIR, f"density_scenario_{name}.txt")
    with open(out_path, "w") as f:
        f.write(f"Density scenario: {name} ({' + '.join(level_names)})\n")
        f.write(f"Levels (loosest -> tightest): {level_names[::-1]}\n")
        f.write(f"n_total={result['metadata']['n_total']} n_noise={result['metadata']['n_noise']} "
                f"counts_by_level={result['metadata']['counts_by_level']}\n")
        f.write("-" * 60 + "\n")
        f.write("lat,lng,density_level\n")
        for feature in result["features"]:
            lon, lat = feature["geometry"]["coordinates"]
            f.write(f"{lat},{lon},{feature['properties']['density_level']}\n")
    return out_path


def main() -> None:
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    incidents = load_sample_incidents()
    for name, level_names in SCENARIOS.items():
        out_path = write_scenario(name, level_names, incidents)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
