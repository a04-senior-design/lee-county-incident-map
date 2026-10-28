import os

from leecad_api import runs

GI_STAR = "/api/v1/gi-star-heatmap"


def test_the_heatmap_is_an_image_over_the_county(client):
    response = client.get(GI_STAR)
    assert response.status_code == 200, response.json
    body = response.json
    assert body["image"].startswith("data:image/png;base64,")
    assert body["distance_band"] == 2500
    assert (body["min_distance_band"], body["max_distance_band"]) == (500, 10000)
    assert set(body["legend"]) == {"colors", "vmin", "vmax", "ticks", "caption"}
    bounds = body["bounds"]
    assert -82.4 < bounds["west"] < bounds["east"] < -81.4
    assert 26.2 < bounds["south"] < bounds["north"] < 27.0


def test_the_heatmap_is_saved_for_the_report(client):
    body = client.get(f"{GI_STAR}?distance_band=3000&source=lee_county").json
    saved = runs.load_response(os.path.join(runs.RUNS_DIR, body["run_id"]))
    assert saved["analysis"] == "gi_star" and saved["response"] == body
    assert saved["inputs"]["sources"] == ["lee_county"] and saved["inputs"]["start_date"] is None


def test_the_distance_band_is_clamped(client):
    assert client.get(f"{GI_STAR}?distance_band=50").json["distance_band"] == 500
    assert client.get(f"{GI_STAR}?distance_band=99999").json["distance_band"] == 10000


def test_the_distance_band_must_be_a_number(client):
    response = client.get(f"{GI_STAR}?distance_band=abc")
    assert response.status_code == 400
    assert response.json["error"] == "Invalid distance-band parameter"


def test_dates_and_filters_work_as_on_the_kde_heatmap(client):
    assert client.get(f"{GI_STAR}?start_date=2026-06-15&end_date=2026-06-20&city=FORT MYERS").status_code == 200
    assert client.get(f"{GI_STAR}?category=FRAUD").status_code == 400
    assert client.get(f"{GI_STAR}?from=2026-06-01").status_code == 400


ANIMATION = "/api/v1/animation/gi-star-heatmap"
JUNE = "start_date=2026-06-10&end_date=2026-06-20&window_length=5D&time_step=5D&distance_band=2500"


def test_animation_frames_share_one_grid(client):
    response = client.get(f"{ANIMATION}?{JUNE}")
    assert response.status_code == 200, response.json
    frames = response.json["frames"]
    # the same windows as the KDE animation
    assert [f["n_incidents"] for f in frames] == [3, 5]
    assert all(f["image"].startswith("data:image/png;base64,") for f in frames)
    assert frames[0]["bounds"] == frames[1]["bounds"]
    assert frames[0]["image_filename"] == "gi_star_overlay_1.png"


def test_animation_takes_the_same_filters_as_incidents(client):
    response = client.get(f"{ANIMATION}?{JUNE}&source=lee_county&category=VIOLENT")
    assert [f["n_incidents"] for f in response.json["frames"]] == [1, 3]


def test_animation_requires_every_parameter(client):
    response = client.get(f"{ANIMATION}?start_date=2026-06-10&end_date=2026-06-20")
    assert response.status_code == 400
    assert response.json["error"] == "Missing required parameter(s): window_length, time_step, distance_band"


def test_animation_rejects_a_bad_distance_band(client):
    response = client.get(f"{ANIMATION}?{JUNE.replace('distance_band=2500', 'distance_band=x')}")
    assert response.status_code == 400
    assert response.json["error"] == "Invalid distance_band parameter"
