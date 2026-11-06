import os
from collections import OrderedDict

import numpy as np
from pyproj import Transformer

from leecad_api import kde_routes, runs

ANIMATION = "/api/v1/animation/kde-heatmap"
JUNE = "start_date=2026-06-10&end_date=2026-06-19&window_length=5D&time_step=5D&bandwidth=1500"
TO_FEET = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)


def padding_grows_with_bandwidth(bounds_at):
    # 1500 to 5000 ft moves the west edge out 3.035 * 3500 ft, give or take a 300 ft cell or two
    # from the grid's spacing and the image's reprojection
    west = {bw: TO_FEET.transform(bounds_at(bw)["west"], bounds_at(bw)["south"])[0] for bw in (1500, 5000)}
    assert abs(west[1500] - west[5000] - 3.035 * 3500) < 600


def test_the_heatmap_is_an_image_over_the_county(client):
    response = client.get("/api/v1/kde-heatmap")
    assert response.status_code == 200, response.json
    body = response.json
    assert body["image"].startswith("data:image/png;base64,")
    assert body["bandwidths"] == [1500]
    assert body["optimized"] is False
    bounds = body["bounds"]
    assert -82.4 < bounds["west"] < bounds["east"] < -81.4
    assert 26.2 < bounds["south"] < bounds["north"] < 27.0


def test_the_heatmap_is_saved_for_the_report(client):
    body = client.get("/api/v1/kde-heatmap?start_date=2026-06-15&end_date=2026-06-20&city=fort myers").json
    saved = runs.load_response(os.path.join(runs.RUNS_DIR, body["run_id"]))
    assert saved["analysis"] == "kde" and saved["response"] == body
    assert saved["inputs"] == {"start_date": "2026-06-15", "end_date": "2026-06-20", "categories": [],
                               "cities": ["FORT MYERS"], "sources": [], "bbox": None}


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


def test_the_heatmap_can_optimize_its_bandwidth(client):
    response = client.get("/api/v1/kde-heatmap?optimize=true")
    assert response.status_code == 200, response.json
    assert response.json["optimized"] is True
    [bandwidth] = response.json["bandwidths"]
    assert 500 < bandwidth <= 10000


def test_the_same_points_are_optimized_once(client, monkeypatch):
    calls = []

    class Optimizer:
        def __init__(self, points, **_):
            calls.append(len(points))

        def optimize_bandwidths(self):
            return [2000.0]

    monkeypatch.setattr(kde_routes, "BandwidthOptimizer", Optimizer)
    monkeypatch.setattr(kde_routes, "OPTIMIZED_BANDWIDTHS", OrderedDict())
    first = client.get("/api/v1/kde-heatmap?optimize=true").json
    second = client.get("/api/v1/kde-heatmap?optimize=true").json
    assert len(calls) == 1
    assert second["bandwidths"] == first["bandwidths"] == [2000.0]
    # each request still gets its own run for the report
    assert second["run_id"] != first["run_id"]

    client.get("/api/v1/kde-heatmap?optimize=true&source=lee_county")
    assert len(calls) == 2

    # the points query has no ORDER BY, so row order must not matter
    points = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    levels = np.array([0, 1, 0])
    order = [2, 0, 1]
    assert kde_routes._optimize_key(points[order], levels[order]) == kde_routes._optimize_key(points, levels)


def test_a_full_cache_drops_the_least_recently_used(client, monkeypatch):
    calls = []

    class Optimizer:
        def __init__(self, points, **_):
            calls.append(len(points))

        def optimize_bandwidths(self):
            return [2000.0]

    monkeypatch.setattr(kde_routes, "BandwidthOptimizer", Optimizer)
    monkeypatch.setattr(kde_routes, "OPTIMIZED_BANDWIDTHS", OrderedDict())
    monkeypatch.setattr(kde_routes, "MAX_OPTIMIZED_BANDWIDTHS", 2)
    every, lee_county = "/api/v1/kde-heatmap?optimize=true", "/api/v1/kde-heatmap?optimize=true&source=lee_county"
    client.get(every)
    client.get(lee_county)
    # using the first one again makes the second the least recently used
    client.get(every)
    client.get(f"{every}&city=FORT MYERS")
    assert len(calls) == 3

    client.get(every)
    assert len(calls) == 3
    client.get(lee_county)
    assert len(calls) == 4


def test_the_optimizer_picks_the_bandwidths_alone(client):
    assert client.get("/api/v1/kde-heatmap?optimize=true&bandwidth=1500").status_code == 400
    assert client.get("/api/v1/kde-heatmap?optimize=yes").status_code == 400


def test_the_heatmap_is_padded_by_its_bandwidth(client):
    padding_grows_with_bandwidth(lambda bw: client.get(f"/api/v1/kde-heatmap?bandwidth={bw}").json["bounds"])


def test_animation_frames_are_padded_by_the_bandwidth(client):
    june = JUNE.replace("&bandwidth=1500", "")
    padding_grows_with_bandwidth(
        lambda bw: client.get(f"{ANIMATION}?{june}&bandwidth={bw}").json["frames"][0]["bounds"])


def test_animation_frames_count_only_mapped_incidents_in_each_window(client):
    response = client.get(f"{ANIMATION}?{JUNE}")
    assert response.status_code == 200, response.json
    frames = response.json["frames"]
    # June 10 to 15 holds 25-001, 25-003 and 25-005; 25-004 is untrusted.
    # June 15 to 20 holds 25-006, T-001 and the three ties; 25-007 is out of county.
    assert [f["n_incidents"] for f in frames] == [3, 5]
    assert all(f["image"].startswith("data:image/png;base64,") for f in frames)
    # one legend for the whole animation, since the frames share one color scale
    assert set(response.json["legend"]) == {"colors", "vmin", "vmax", "ticks", "caption"}


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
