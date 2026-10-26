import pytest
import report

from leecad_api import reports
from leecad_api.auth import API, AUTH

REPORTS = f"{API}/reports"
JUNE = "from=2026-06-10&to=2026-06-20"


@pytest.fixture
def sent(monkeypatch):
    """What the route hands generate_pdf, with the map left out so tests don't download tiles."""
    monkeypatch.setattr(report, "_map_snapshot", lambda incidents, bounds: None)
    calls = []

    def generate(incidents, bounds, start_date, end_date, analyses=None):
        calls.append({"incidents": incidents, "bounds": bounds, "start": start_date, "end": end_date,
                      "analyses": analyses})
        return report.generate_pdf(incidents, bounds, start_date, end_date, analyses=analyses)

    monkeypatch.setattr(reports, "generate_pdf", generate)
    return calls


@pytest.fixture
def headers(auth_client, seeded):
    response = auth_client.post(f"{AUTH}/register",
                                json={"email": "resident@example.com", "password": "correct horse battery", "name": "Pat"})
    return {"Authorization": f"Bearer {response.json['access_token']}"}


def test_reports_need_sign_in(auth_client):
    assert auth_client.get(f"{REPORTS}?{JUNE}").status_code == 401


def test_a_report_is_a_pdf_of_the_mapped_incidents(auth_client, headers, sent):
    response = auth_client.get(f"{REPORTS}?{JUNE}", headers=headers)
    assert response.status_code == 200
    assert response.mimetype == "application/pdf" and response.data.startswith(b"%PDF")
    assert "lee-county-report-2026-06-10_to_2026-06-20.pdf" in response.headers["Content-Disposition"]
    [call] = sent
    # the untrusted, out-of-county and unmapped incidents are left out
    assert len(call["incidents"]) == 8
    assert str(call["start"]) == "2026-06-10" and str(call["end"]) == "2026-06-20"


def test_incidents_are_sent_by_category_in_eastern_time(auth_client, headers, sent):
    auth_client.get(f"{REPORTS}?{JUNE}&category=BURGLARY", headers=headers)
    [incident] = sent[0]["incidents"]
    # 25-003: nature BURGLARY, 12:00 UTC on June 12
    assert incident["nature"] == "BURGLARY"
    assert incident["occuredDate"] == "2026-06-12T08:00:00-04:00"


def test_a_report_takes_the_same_filters_as_incidents(auth_client, headers, sent):
    auth_client.get(f"{REPORTS}?{JUNE}&city=FORT MYERS&source=lee_county", headers=headers)
    assert len(sent[0]["incidents"]) == 5


@pytest.mark.parametrize("query", ["days=30", "from=2026-06-10", "to=2026-06-20"])
def test_a_report_needs_from_and_to(auth_client, headers, query):
    response = auth_client.get(f"{REPORTS}?{query}", headers=headers)
    assert response.status_code == 400
    assert response.json["error"] == "a report needs from and to, not days"


def test_a_report_covers_at_most_366_days(auth_client, headers, sent):
    # both ends count, so June 20 to June 20 is 366 days
    assert auth_client.get(f"{REPORTS}?from=2025-06-20&to=2026-06-20", headers=headers).status_code == 200
    assert auth_client.get(f"{REPORTS}?from=2025-06-19&to=2026-06-20", headers=headers).status_code == 400


def test_a_report_with_no_incidents_is_refused(auth_client, headers):
    response = auth_client.get(f"{REPORTS}?{JUNE}&category=FRAUD", headers=headers)
    assert response.status_code == 400


# the analyses' own names for the report's dates
JUNE_RUN = "start_date=2026-06-10&end_date=2026-06-20"


def made(client, path, query=JUNE_RUN):
    response = client.get(f"{API}/{path}?{query}")
    assert response.status_code == 200, response.json
    return response.json


def test_a_report_gets_the_runs_the_user_made(auth_client, headers, sent):
    kde = made(auth_client, "kde-heatmap")
    gi_star = made(auth_client, "gi-star-heatmap")
    clusters = made(auth_client, "clusters")
    response = auth_client.get(f"{REPORTS}?{JUNE}&kde_run={kde['run_id']}&gi_star_run={gi_star['run_id']}"
                               f"&dbscan_run={clusters['run_id']}", headers=headers)
    assert response.status_code == 200, response.json
    assert sent[0]["analyses"] == {"kde": kde, "gi_star": gi_star, "dbscan": clusters}


def test_a_run_not_sent_is_left_out(auth_client, headers, sent):
    kde = made(auth_client, "kde-heatmap")
    auth_client.get(f"{REPORTS}?{JUNE}&kde_run={kde['run_id']}", headers=headers)
    assert list(sent[0]["analyses"]) == ["kde"]
    auth_client.get(f"{REPORTS}?{JUNE}", headers=headers)
    assert sent[1]["analyses"] == {}


def test_a_run_must_match_the_report_filters(auth_client, headers):
    kde = made(auth_client, "kde-heatmap", f"{JUNE_RUN}&city=FORT MYERS")
    response = auth_client.get(f"{REPORTS}?{JUNE}&kde_run={kde['run_id']}", headers=headers)
    assert response.status_code == 400
    assert "different filters" in response.json["error"]
    matching = auth_client.get(f"{REPORTS}?{JUNE}&city=FORT MYERS&kde_run={kde['run_id']}", headers=headers)
    assert matching.status_code == 200


def test_a_run_must_match_the_report_dates(auth_client, headers):
    gi_star = made(auth_client, "gi-star-heatmap", "start_date=2026-06-15&end_date=2026-06-20")
    response = auth_client.get(f"{REPORTS}?{JUNE}&gi_star_run={gi_star['run_id']}", headers=headers)
    assert response.status_code == 400
    assert "start_date 2026-06-15" in response.json["error"]


def test_a_run_must_be_the_analysis_it_is_sent_as(auth_client, headers):
    gi_star = made(auth_client, "gi-star-heatmap")
    response = auth_client.get(f"{REPORTS}?{JUNE}&kde_run={gi_star['run_id']}", headers=headers)
    assert response.status_code == 400
    assert response.json["error"] == "kde_run is not a KDE heatmap run"


def test_an_expired_or_made_up_run_is_refused(auth_client, headers):
    response = auth_client.get(f"{REPORTS}?{JUNE}&dbscan_run={'0' * 32}", headers=headers)
    assert response.status_code == 400
    assert response.json["error"] == "dbscan_run has expired or does not exist; run the cluster analysis again"
    assert auth_client.get(f"{REPORTS}?{JUNE}&dbscan_run=../../etc", headers=headers).status_code == 400
