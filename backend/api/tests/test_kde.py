ANIMATION = "/api/v1/animation/kde-heatmap"
JUNE = "start_date=2026-06-10&end_date=2026-06-20&window_length=5D&time_step=5D&bandwidth=1500"


def test_the_heatmap_is_an_image_over_the_county(client):
    response = client.get("/api/v1/kde-heatmap")
    assert response.status_code == 200, response.json
    body = response.json
    assert body["image"].startswith("data:image/png;base64,")
    assert body["bandwidths"] == [1500]
    bounds = body["bounds"]
    assert -82.4 < bounds["west"] < bounds["east"] < -81.4
    assert 26.2 < bounds["south"] < bounds["north"] < 27.0


def test_the_heatmap_takes_the_same_filters_as_incidents(client):
    # Fort Myers only; unfiltered, Sanibel (-82.02) and North Fort Myers (26.70) stretch it
    response = client.get("/api/v1/kde-heatmap?bbox=-81.88,26.59,-81.83,26.65")
    assert response.status_code == 200, response.json
    bounds = response.json["bounds"]
    assert bounds["west"] > -81.9 and bounds["north"] < 26.66


def test_the_heatmap_takes_start_and_end_date(client):
    # June 15 to 20 leaves out Sanibel (June 14) and North Fort Myers (June 12)
    response = client.get("/api/v1/kde-heatmap?start_date=2026-06-15&end_date=2026-06-20")
    assert response.status_code == 200, response.json
    bounds = response.json["bounds"]
    assert bounds["west"] > -81.9 and bounds["north"] < 26.66
    assert client.get("/api/v1/kde-heatmap?from=2026-06-01").status_code == 400


def test_the_heatmap_says_when_no_incident_matches(client):
    response = client.get("/api/v1/kde-heatmap?category=FRAUD")
    assert response.status_code == 400
    assert "no mapped incidents" in response.json["error"]


def test_the_heatmap_rejects_an_unknown_cluster_set(client):
    assert client.get("/api/v1/kde-heatmap?cluster_set=5").status_code == 400


def test_animation_frames_count_only_mapped_incidents_in_each_window(client):
    response = client.get(f"{ANIMATION}?{JUNE}")
    assert response.status_code == 200, response.json
    frames = response.json["frames"]
    # June 10 to 15 holds 25-001, 25-003 and 25-005; 25-004 is untrusted.
    # June 15 to 20 holds 25-006, T-001 and the three ties; 25-007 is out of county.
    assert [f["n_incidents"] for f in frames] == [3, 5]
    assert all(f["image"].startswith("data:image/png;base64,") for f in frames)


def test_animation_frames_take_the_same_filters_as_incidents(client):
    response = client.get(f"{ANIMATION}?{JUNE}&source=lee_county&category=VIOLENT")
    assert response.status_code == 200, response.json
    # 25-001 in the first window, the three ties in the second
    assert [f["n_incidents"] for f in response.json["frames"]] == [1, 3]


def test_animation_dates_come_only_from_start_and_end_date(client):
    response = client.get(f"{ANIMATION}?{JUNE}&from=2026-06-01")
    assert response.status_code == 400
    assert "from" in response.json["error"]


def test_animation_requires_every_parameter(client):
    response = client.get(f"{ANIMATION}?start_date=2026-06-10&end_date=2026-06-20")
    assert response.status_code == 400
    assert "window_length" in response.json["error"]


def test_animation_rejects_a_bad_date_and_a_bad_offset(client):
    assert client.get(f"{ANIMATION}?{JUNE.replace('2026-06-10', 'nope')}").status_code == 400
    assert client.get(f"{ANIMATION}?{JUNE.replace('window_length=5D', 'window_length=abc')}").status_code == 400
