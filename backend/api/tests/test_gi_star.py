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
