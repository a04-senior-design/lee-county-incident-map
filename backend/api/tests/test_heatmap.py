def get(client, query):
    response = client.get(f"/api/v1/heatmap/frames?{query}")
    assert response.status_code == 200, response.json
    return response.json


def counts(body):
    return {f["date"]: f["count"] for f in body["frames"]}


def test_one_frame_per_day_counting_only_mapped_incidents(client):
    body = get(client, "from=2026-06-10&to=2026-06-18&window=1")
    # 13th is an untrusted road centroid, 16th is out of county
    assert counts(body) == {
        "2026-06-10": 1, "2026-06-11": 0, "2026-06-12": 1, "2026-06-13": 0, "2026-06-14": 1,
        "2026-06-15": 1, "2026-06-16": 0, "2026-06-17": 1, "2026-06-18": 3,
    }


def test_the_window_reaches_back_before_from(client):
    frame = get(client, "from=2026-06-18&to=2026-06-18&window=7")["frames"][0]
    assert (frame["start"], frame["count"]) == ("2026-06-12", 7)


def test_filters_apply(client):
    body = get(client, "from=2026-06-10&to=2026-06-18&window=9&category=BURGLARY")
    assert counts(body)["2026-06-18"] == 1


def test_empty_frames_have_no_image_and_the_rest_are_pngs(client):
    body = get(client, "from=2026-06-10&to=2026-06-11&window=1")
    first, second = body["frames"]
    assert first["image"].startswith("data:image/png;base64,")
    assert second["image"] is None
    assert body["bounds"]["west"] < body["bounds"]["east"]


def test_no_incidents_at_all_is_not_an_error(client):
    body = get(client, "from=2025-01-01&to=2025-01-03")
    assert body["bounds"] is None and all(f["image"] is None for f in body["frames"])


def test_bad_parameters_are_rejected(client):
    for query in ("from=2026-06-10", "from=2026-01-01&to=2026-12-31",
                  "from=2026-06-10&to=2026-06-11&bandwidth=99999", "from=2026-06-10&to=2026-06-11&window=0"):
        assert client.get(f"/api/v1/heatmap/frames?{query}").status_code == 400, query
