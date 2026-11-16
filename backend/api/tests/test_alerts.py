from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from leecad_api import alerts
from leecad_api.auth import API, AUTH

AREAS = f"{API}/users/me/areas"
ALERTS = f"{API}/users/me/alerts"
# 0.5 miles around a point in Fort Myers
HOME = {"name": "Home", "lat": 26.64, "lon": -81.87, "radius_mi": 0.5}
NEAR = (26.645, -81.87)      # about 0.35 miles north
FAR = (26.70, -81.87)        # about 4 miles north

INSERT = """
    INSERT INTO incidents (source, source_incident_id, occurred_at, fetched_at, last_changed,
                           nature, address, city, lat, lon, geocode_quality, geocoded_at, raw)
    VALUES ('lee_county', %s, %s, now(), now(), %s, '1 MAIN ST', 'FORT MYERS', %s, %s, %s,
            COALESCE(%s, now()), '{}'::jsonb)
"""


@pytest.fixture
def mapped(seeded):
    """Maps an incident now; days_ago is when it happened."""
    def add(incident_id, where=NEAR, nature="BURGLARY", days_ago=2, quality="EXACT", geocoded_at=None):
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute(INSERT, (incident_id, datetime.now(UTC) - timedelta(days=days_ago),
                                  nature, *where, quality, geocoded_at))
    return add


def sign_in(client):
    response = client.post(f"{AUTH}/register",
                           json={"email": "resident@example.com", "password": "correct horse battery", "name": "Pat"})
    return {"Authorization": f"Bearer {response.json['access_token']}"}


def ids(client, headers):
    return [a["source_incident_id"] for a in client.get(ALERTS, headers=headers).json["alerts"]]


def test_alerts_need_sign_in(auth_client):
    assert auth_client.get(ALERTS).status_code == 401
    assert auth_client.post(f"{ALERTS}/seen", json={"cursor": "x"}).status_code == 401


def test_no_saved_area_means_no_alerts(auth_client, mapped):
    headers = sign_in(auth_client)
    mapped("26-1")
    assert auth_client.get(ALERTS, headers=headers).json == {"alerts": [], "cursor": None, "has_more": False}


def test_a_new_incident_in_an_area_is_an_alert(auth_client, mapped):
    headers = sign_in(auth_client)
    auth_client.post(AREAS, headers=headers, json=HOME)
    mapped("26-1")
    body = auth_client.get(ALERTS, headers=headers).json
    [alert] = body["alerts"]
    assert alert["source_incident_id"] == "26-1"
    assert alert["category"] == "BURGLARY"
    assert alert["areas"] == ["Home"]
    assert body["cursor"] and body["has_more"] is False


def test_only_incidents_that_fit_every_rule_alert(auth_client, mapped):
    headers = sign_in(auth_client)
    mapped("before-the-area")
    auth_client.post(AREAS, headers=headers, json={**HOME, "categories": ["BURGLARY"]})
    mapped("outside", where=FAR)
    mapped("old", days_ago=40)
    mapped("road-centroid", quality="nominatim:primary")
    mapped("other-category", nature="ASSAULT")
    mapped("alerts")
    assert ids(auth_client, headers) == ["alerts"]


def test_a_disabled_area_sends_no_alerts(auth_client, mapped):
    headers = sign_in(auth_client)
    area = auth_client.post(AREAS, headers=headers, json=HOME).json
    auth_client.patch(f"{AREAS}/{area['id']}", headers=headers, json={"alerts_enabled": False})
    mapped("26-1")
    assert ids(auth_client, headers) == []


def test_an_incident_in_two_areas_alerts_once(auth_client, mapped):
    headers = sign_in(auth_client)
    auth_client.post(AREAS, headers=headers, json=HOME)
    auth_client.post(AREAS, headers=headers, json={**HOME, "name": "Work", "radius_mi": 2})
    mapped("26-1")
    [alert] = auth_client.get(ALERTS, headers=headers).json["alerts"]
    assert alert["areas"] == ["Home", "Work"]


def test_alerts_stay_until_marked_seen(auth_client, mapped):
    headers = sign_in(auth_client)
    auth_client.post(AREAS, headers=headers, json=HOME)
    mapped("26-1")
    cursor = auth_client.get(ALERTS, headers=headers).json["cursor"]
    assert ids(auth_client, headers) == ["26-1"]

    assert auth_client.post(f"{ALERTS}/seen", headers=headers, json={"cursor": cursor}).status_code == 204
    assert ids(auth_client, headers) == []
    mapped("26-2")
    assert ids(auth_client, headers) == ["26-2"]


def test_an_old_cursor_does_not_bring_alerts_back(auth_client, mapped):
    headers = sign_in(auth_client)
    auth_client.post(AREAS, headers=headers, json=HOME)
    mapped("26-1")
    first = auth_client.get(ALERTS, headers=headers).json["cursor"]
    mapped("26-2")
    second = auth_client.get(ALERTS, headers=headers).json["cursor"]
    auth_client.post(f"{ALERTS}/seen", headers=headers, json={"cursor": second})
    auth_client.post(f"{ALERTS}/seen", headers=headers, json={"cursor": first})
    assert ids(auth_client, headers) == []


def test_incidents_mapped_at_the_same_moment_are_not_skipped(auth_client, mapped, monkeypatch):
    monkeypatch.setattr(alerts, "MAX_ALERTS", 1)
    headers = sign_in(auth_client)
    auth_client.post(AREAS, headers=headers, json=HOME)
    # one geocoding batch stamps every row with the same time
    batch = datetime.now(UTC) + timedelta(seconds=1)
    mapped("26-1", geocoded_at=batch)
    mapped("26-2", geocoded_at=batch)

    first = auth_client.get(ALERTS, headers=headers).json
    assert [a["source_incident_id"] for a in first["alerts"]] == ["26-1"] and first["has_more"]
    auth_client.post(f"{ALERTS}/seen", headers=headers, json={"cursor": first["cursor"]})
    assert ids(auth_client, headers) == ["26-2"]


@pytest.mark.parametrize("body", [{}, {"cursor": 5}, {"cursor": "not a cursor"}])
def test_seen_needs_a_cursor_from_alerts(auth_client, body):
    response = auth_client.post(f"{ALERTS}/seen", headers=sign_in(auth_client), json=body)
    assert response.status_code == 400
