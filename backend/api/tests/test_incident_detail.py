def get(client, source, source_incident_id):
    return client.get(f"/api/v1/incidents/{source}/{source_incident_id}")


def test_it_returns_the_incident(client):
    body = get(client, "lee_county", "25-001").json
    assert body["source"] == "lee_county"
    assert body["source_incident_id"] == "25-001"
    assert body["nature"] == "ASSAULT"
    assert body["category"] == "VIOLENT"


def test_an_unknown_incident_is_a_404(client):
    response = get(client, "lee_county", "does-not-exist")
    assert response.status_code == 404
    assert response.json["error"]


def test_an_unknown_source_is_a_404(client):
    assert get(client, "not_a_source", "25-001").status_code == 404


def test_it_returns_the_coordinates(client):
    body = get(client, "lee_county", "25-005").json
    assert (body["lat"], body["lon"]) == (26.45, -82.02)


def test_an_incident_with_no_coordinates_reads_as_null(client):
    body = get(client, "lee_county", "25-011").json
    assert (body["lat"], body["lon"]) == (None, None)


def test_city_is_canonicalized_here_too(client):
    assert get(client, "lee_county", "25-003").json["city"] == "NORTH FORT MYERS"


def test_the_fields_match_the_list_exactly(client):
    listed = client.get("/api/v1/incidents?limit=500").json["incidents"]
    from_list = next(i for i in listed if i["source_incident_id"] == "25-001")
    assert get(client, "lee_county", "25-001").json == from_list
