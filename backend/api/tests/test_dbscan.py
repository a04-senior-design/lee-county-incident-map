import numpy as np
import pandas as pd
from ml.generate_kde_heatmap_snapshots import build_kde_heatmap_snapshots_from_dbscan

DBSCAN = "/api/v1/animation/dbscan"
KDE = "/api/v1/animation/kde-heatmap-dbscan"
# June 10 to 15 holds three incidents far apart, so every level is noise.
SPREAD_OUT = "start_date=2026-06-10&end_date=2026-06-15&window_length=5D&time_step=5D"
# June 15 to 20 holds five incidents within a few thousand feet, which the district level clusters.
CLOSE_TOGETHER = "start_date=2026-06-15&end_date=2026-06-20&window_length=5D&time_step=5D"


def run(client, query):
    response = client.get(f"{DBSCAN}?{query}")
    assert response.status_code == 200, response.json
    return response.json


def status(client, run_id):
    return client.get(f"{KDE}/status?run_id={run_id}").json["dbscan_status"]


def test_frames_count_only_mapped_incidents_in_each_window(client):
    body = run(client, "start_date=2026-06-10&end_date=2026-06-20&window_length=5D&time_step=5D")
    assert [f["n_incidents"] for f in body["frames"]] == [3, 5]
    assert set(body["frames"][0]["levels"]) == {"street", "neighborhood", "district"}
    assert len(body["run_id"]) == 32


def test_frames_take_the_same_filters_as_incidents(client):
    body = run(client, "start_date=2026-06-10&end_date=2026-06-20&window_length=5D&time_step=5D"
                       "&source=lee_county&category=VIOLENT")
    assert [f["n_incidents"] for f in body["frames"]] == [1, 3]


def test_the_animation_requires_a_window(client):
    response = client.get(f"{DBSCAN}?start_date=2026-06-10&end_date=2026-06-20")
    assert response.status_code == 400
    assert "window_length" in response.json["error"]


def test_a_run_drives_the_kde_animation(client):
    run_id = run(client, CLOSE_TOGETHER)["run_id"]
    assert status(client, run_id) == "available"

    response = client.get(f"{KDE}?run_id={run_id}")
    assert response.status_code == 200, response.json
    frames = response.json["frames"]
    assert frames[0]["n_incidents"] == 5
    assert frames[0]["image"].startswith("data:image/png;base64,")
    assert set(response.json["legend"]) == {"colors", "vmin", "vmax", "ticks", "caption"}


def write_frames(folder, *frames):
    for number, points in enumerate(frames, start=1):
        rows = [{"easting": x, "northing": y, "cluster_density_level": 0} for x, y in points]
        pd.DataFrame(rows, columns=["easting", "northing", "cluster_density_level"]).to_csv(
            folder / f"{number}_userID_dbscan.csv", index=False)


def test_the_kde_animation_frames_share_one_color_scale(tmp_path):
    rng = np.random.default_rng(0)
    center = np.array([700000.0, 800000.0])
    tight = center + rng.normal(0, 100, (20, 2))
    loose = center + rng.normal(0, 3000, (20, 2))

    def legend(name, *frames):
        (tmp_path / name).mkdir()
        write_frames(tmp_path / name, *frames)
        _, legend = build_kde_heatmap_snapshots_from_dbscan(
            bandwidths=[1500], densities_dir=tmp_path / name, output_dir=tmp_path / f"{name}_out")
        return legend

    # the loose frame comes last, but the scale and so the legend come from the tight one
    assert legend("both", tight, loose) == legend("tight", tight)
    assert legend("both_again", tight, loose) != legend("loose", loose)


def test_each_run_keeps_its_own_results(client):
    clustered = run(client, CLOSE_TOGETHER)["run_id"]
    all_noise = run(client, SPREAD_OUT)["run_id"]
    assert status(client, clustered) == "available"
    assert status(client, all_noise) == "no_cluster_levels"


def test_run_id_must_be_one_the_api_issued(client):
    assert client.get(f"{KDE}/status?run_id=../../etc").status_code == 400
    assert client.get(f"{KDE}?bandwidth=1500").status_code == 400
    assert status(client, "0" * 32) == "missing"


def clusters(client, query):
    response = client.get(f"/api/v1/clusters?{query}")
    assert response.status_code == 200, response.json
    return response.json


def test_clusters_cover_only_mapped_incidents_in_the_range(client):
    body = clusters(client, "start_date=2026-06-10&end_date=2026-06-20")
    # eight mapped incidents; the untrusted, out-of-county and unmapped ones are left out
    assert body["frames"][0]["n_incidents"] == 8
    assert set(body["frames"][0]["levels"]) == {"street", "neighborhood", "district"}
    assert len(body["run_id"]) == 32


def test_clusters_take_the_same_filters_as_incidents(client):
    body = clusters(client, "start_date=2026-06-10&end_date=2026-06-20&city=FORT MYERS")
    # 25-001, 25-006, T-001 and the three ties; North Fort Myers and Sanibel are left out
    assert body["frames"][0]["n_incidents"] == 6


def test_clusters_refuse_more_than_sixty_days(client):
    response = client.get("/api/v1/clusters?start_date=2026-04-01&end_date=2026-06-20")
    assert response.status_code == 400


def test_a_clusters_run_drives_the_cluster_level_heatmap(client):
    run_id = clusters(client, "start_date=2026-06-15&end_date=2026-06-20")["run_id"]
    response = client.get(f"/api/v1/kde-heatmap?cluster_set=1&run_id={run_id}")
    assert response.status_code == 200, response.json
    assert response.json["dbscan_status"] == "available"
    assert response.json["image"].startswith("data:image/png;base64,")


def test_the_cluster_level_heatmap_needs_a_run(client):
    response = client.get("/api/v1/kde-heatmap?cluster_set=1")
    assert response.status_code == 400
    assert response.json["dbscan_status"] == "missing"
