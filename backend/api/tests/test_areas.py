import psycopg
import pytest

from leecad_api.alerts import MAX_AREAS
from leecad_api.auth import API, AUTH

AREAS = f"{API}/users/me/areas"
HOME = {"name": "Home", "lat": 26.64, "lon": -81.87, "radius_mi": 0.5}


def sign_in(client, email="resident@example.com"):
    response = client.post(f"{AUTH}/register",
                           json={"email": email, "password": "correct horse battery", "name": "Pat"})
    return {"Authorization": f"Bearer {response.json['access_token']}"}


def test_areas_need_sign_in(auth_client):
    assert auth_client.get(AREAS).status_code == 401
    assert auth_client.post(AREAS, json=HOME).status_code == 401


def test_a_saved_area_reads_back_as_sent(auth_client):
    headers = sign_in(auth_client)
    created = auth_client.post(AREAS, headers=headers, json={**HOME, "categories": ["burglary", "THEFT"]})
    assert created.status_code == 201
    area = created.json
    assert area["radius_mi"] == 0.5
    assert area["categories"] == ["BURGLARY", "THEFT"]
    assert area["alerts_enabled"] is True
    assert auth_client.get(AREAS, headers=headers).json["areas"] == [area]


def test_the_first_area_starts_the_alerts(auth_client, database_url):
    headers = sign_in(auth_client)
    auth_client.post(AREAS, headers=headers, json=HOME)
    auth_client.post(AREAS, headers=headers, json={**HOME, "name": "Work"})
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT count(*) FROM alert_state").fetchone()[0] == 1


@pytest.mark.parametrize("change", [
    {"name": "  "},
    {"lat": 40.7},
    {"lon": "-81.87"},
    {"radius_mi": 0},
    {"radius_mi": 11},
    {"radius_mi": True},
    {"categories": ["NOT_A_CATEGORY"]},
    {"categories": "BURGLARY"},
    {"alerts_enabled": "yes"},
    {"radius_m": 800},
])
def test_a_bad_area_is_refused(auth_client, change):
    response = auth_client.post(AREAS, headers=sign_in(auth_client), json={**HOME, **change})
    assert response.status_code == 400


def test_an_area_needs_every_required_field(auth_client):
    response = auth_client.post(AREAS, headers=sign_in(auth_client), json={"name": "Home"})
    assert response.status_code == 400
    assert response.json["error"] == "missing lat, lon, radius_mi"


def test_there_is_a_cap_on_areas(auth_client):
    headers = sign_in(auth_client)
    for i in range(MAX_AREAS):
        assert auth_client.post(AREAS, headers=headers, json={**HOME, "name": f"Area {i}"}).status_code == 201
    assert auth_client.post(AREAS, headers=headers, json=HOME).status_code == 409


def test_patch_changes_only_what_is_sent(auth_client):
    headers = sign_in(auth_client)
    area = auth_client.post(AREAS, headers=headers, json={**HOME, "categories": ["THEFT"]}).json
    changed = auth_client.patch(f"{AREAS}/{area['id']}", headers=headers,
                                json={"radius_mi": 2, "alerts_enabled": False, "categories": []}).json
    assert changed == {**area, "radius_mi": 2, "alerts_enabled": False, "categories": []}


def test_an_area_can_be_deleted(auth_client):
    headers = sign_in(auth_client)
    area = auth_client.post(AREAS, headers=headers, json=HOME).json
    assert auth_client.delete(f"{AREAS}/{area['id']}", headers=headers).status_code == 204
    assert auth_client.get(AREAS, headers=headers).json["areas"] == []


def test_someone_elses_area_cannot_be_seen_changed_or_deleted(auth_client):
    area = auth_client.post(AREAS, headers=sign_in(auth_client), json=HOME).json
    other = sign_in(auth_client, email="neighbor@example.com")
    assert auth_client.get(AREAS, headers=other).json["areas"] == []
    assert auth_client.patch(f"{AREAS}/{area['id']}", headers=other, json={"name": "Mine"}).status_code == 404
    assert auth_client.delete(f"{AREAS}/{area['id']}", headers=other).status_code == 404
