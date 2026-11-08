import os

import numpy as np
import pandas as pd
from ml.generate_kde_heatmap_snapshots import build_kde_heatmap_snapshots_from_dbscan
from test_kde import padding_grows_with_bandwidth

from leecad_api import runs

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
    body = run(client, "start_date=2026-06-10&end_date=2026-06-19&window_length=5D&time_step=5D")
    assert [f["n_incidents"] for f in body["frames"]] == [3, 5]
    assert set(body["frames"][0]["levels"]) == {"street", "neighborhood", "district"}
    assert len(body["run_id"]) == 32


def test_frames_take_the_same_filters_as_incidents(client):
    body = run(client, "start_date=2026-06-10&end_date=2026-06-19&window_length=5D&time_step=5D"
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

    # the loose frame comes last, but the top of the scale comes from the tight one,
    # and the cutoff from the loose one, the quietest frame
    both = legend("both", tight, loose)
    assert both["vmax"] == legend("tight", tight)["vmax"]
    assert both["vmin"] == legend("loose", loose)["vmin"]


def test_the_cluster_level_animation_is_padded_by_the_bandwidth(tmp_path):
    rng = np.random.default_rng(0)
    write_frames(tmp_path, np.array([700000.0, 800000.0]) + rng.normal(0, 2000, (20, 2)))

    def bounds_at(bw):
        out = tmp_path / f"out_{bw}"
        frames, _ = build_kde_heatmap_snapshots_from_dbscan(bandwidths=[bw], densities_dir=tmp_path, output_dir=out)
        return frames[0]["bounds"]

    padding_grows_with_bandwidth(bounds_at)


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


def test_clusters_save_their_response_for_the_report(client):
    body = clusters(client, "start_date=2026-06-10&end_date=2026-06-20&levels=district&district_eps=3000")
    assert body["level_configs"]["district"]["epsilon"] == 3000
    saved = runs.load_response(os.path.join(runs.RUNS_DIR, body["run_id"]))
    assert saved["analysis"] == "dbscan" and saved["response"] == body
    assert (saved["inputs"]["start_date"], saved["inputs"]["end_date"]) == ("2026-06-10", "2026-06-20")


def test_animation_runs_save_no_response(client):
    run_id = run(client, CLOSE_TOGETHER)["run_id"]
    assert runs.load_response(os.path.join(runs.RUNS_DIR, run_id)) is None


def test_clusters_refuse_more_than_sixty_days(client):
    response = client.get("/api/v1/clusters?start_date=2026-04-01&end_date=2026-06-20")
    assert response.status_code == 400


def burglaries(client, start_date, end_date):
    # 25-003 is the only burglary: 12:00 UTC on June 12, which is 8 am Eastern
    body = run(client, f"start_date={start_date}&end_date={end_date}&window_length=1D&time_step=1D&category=BURGLARY")
    return sum(f["n_incidents"] for f in body["frames"])


def test_a_date_is_a_whole_eastern_day(client):
    assert burglaries(client, "2026-06-12", "2026-06-12") == 1
    assert burglaries(client, "2026-06-13", "2026-06-13") == 0


def test_a_time_without_an_offset_is_eastern(client):
    assert burglaries(client, "2026-06-12T07:30", "2026-06-12T08:30") == 1
    # read as UTC, this hour would miss it
    assert burglaries(client, "2026-06-12T11:30", "2026-06-12T12:30") == 0
    assert burglaries(client, "2026-06-12T11:30-00:00", "2026-06-12T12:30-00:00") == 1


def test_a_date_that_cannot_be_read_is_refused(client):
    response = client.get("/api/v1/clusters?start_date=June 12&end_date=2026-06-12")
    assert response.status_code == 400
    assert "start_date" in response.json["error"]


def test_a_clusters_run_drives_the_cluster_level_heatmap(client):
    run_id = clusters(client, "start_date=2026-06-15&end_date=2026-06-20")["run_id"]
    response = client.get(f"/api/v1/kde-heatmap?cluster_set=1&run_id={run_id}")
    assert response.status_code == 200, response.json
    assert response.json["dbscan_status"] == "available"
    assert response.json["image"].startswith("data:image/png;base64,")


def test_a_clusters_run_can_optimize_one_bandwidth_per_level(client):
    run_id = clusters(client, "start_date=2026-06-15&end_date=2026-06-20")["run_id"]
    default = client.get(f"/api/v1/kde-heatmap?cluster_set=1&run_id={run_id}").json
    response = client.get(f"/api/v1/kde-heatmap?cluster_set=1&run_id={run_id}&optimize=true")
    assert response.status_code == 200, response.json
    bandwidths = response.json["bandwidths"]
    assert len(bandwidths) == len(default["bandwidths"])
    assert bandwidths == sorted(bandwidths, reverse=True)


def run_with_levels_0_and_2(*file_names):
    # level 1 found no clusters, the case where position and level number disagree
    rng = np.random.default_rng(0)
    center = np.array([700000.0, 800000.0])
    rows = [(*p, 0) for p in center + rng.normal(0, 3000, (20, 2))]
    rows += [(*p, 2) for p in center + rng.normal(0, 300, (20, 2))]
    rows += [(*p, -1) for p in center + rng.normal(0, 20000, (5, 2))]
    run_id, folder = runs.new_run_dir()
    os.makedirs(folder)
    for name in file_names:
        pd.DataFrame(rows, columns=["easting", "northing", "cluster_density_level"]).to_csv(
            os.path.join(folder, name), index=False)
    return run_id


def test_the_heatmap_says_which_level_each_bandwidth_is_for(client):
    run_id = run_with_levels_0_and_2("userID_dbscan.csv")
    for query in ("", "&bandwidth=3000&bandwidth=800", "&optimize=true"):
        body = client.get(f"/api/v1/kde-heatmap?cluster_set=1&run_id={run_id}{query}").json
        assert body["cluster_levels"] == [0, 2]
        assert len(body["bandwidths"]) == 2


def test_the_animation_says_which_level_each_bandwidth_is_for(client):
    run_id = run_with_levels_0_and_2("1_userID_dbscan.csv", "2_userID_dbscan.csv")
    for query in ("", "&bandwidth=3000&bandwidth=800"):
        response = client.get(f"{KDE}?run_id={run_id}{query}")
        assert response.status_code == 200, response.json
        assert response.json["cluster_levels"] == [0, 2]
        assert len(response.json["bandwidths"]) == 2


def test_the_cluster_level_heatmap_needs_a_run(client):
    response = client.get("/api/v1/kde-heatmap?cluster_set=1")
    assert response.status_code == 400
    assert response.json["dbscan_status"] == "missing"
