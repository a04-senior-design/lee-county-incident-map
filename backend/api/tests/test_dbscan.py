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


def test_each_run_keeps_its_own_results(client):
    clustered = run(client, CLOSE_TOGETHER)["run_id"]
    all_noise = run(client, SPREAD_OUT)["run_id"]
    assert status(client, clustered) == "available"
    assert status(client, all_noise) == "no_cluster_levels"


def test_run_id_must_be_one_the_api_issued(client):
    assert client.get(f"{KDE}/status?run_id=../../etc").status_code == 400
    assert client.get(f"{KDE}?bandwidth=1500").status_code == 400
    assert status(client, "0" * 32) == "missing"
