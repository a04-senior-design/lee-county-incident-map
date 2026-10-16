import base64
from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request

from leecad_api.auth import API, requires_access_token
from leecad_api.queries import COLUMNS, FROM_AND_JOINS

AREAS = f"{API}/users/me/areas"
ALERTS = f"{API}/users/me/alerts"
MAX_ALERTS = 100
METERS_PER_MILE = 1609.344
MAX_AREAS = 10
MAX_NAME = 100
MIN_RADIUS_MI = 0.1
MAX_RADIUS_MI = 10
# Lee County plus a margin, so an area on the county line still fits
COUNTY = {"west": -82.4, "south": 26.2, "east": -81.4, "north": 27.0}
FIELDS = ("name", "lat", "lon", "radius_mi", "categories", "alerts_enabled")

bp = Blueprint("alerts", __name__)

AREA_COLUMNS = "id, name, lat, lon, radius_mi, categories, alerts_enabled, created_at"

LIST_AREAS = f"SELECT {AREA_COLUMNS} FROM saved_areas WHERE user_id = %s ORDER BY id"

CREATE_AREA = f"""
    INSERT INTO saved_areas (user_id, name, lat, lon, radius_mi, categories, alerts_enabled)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING {AREA_COLUMNS}
"""

# A missing field is sent as NULL and keeps its value.
UPDATE_AREA = f"""
    UPDATE saved_areas
       SET name = COALESCE(%s, name),
           lat = COALESCE(%s, lat),
           lon = COALESCE(%s, lon),
           radius_mi = COALESCE(%s, radius_mi),
           categories = COALESCE(%s, categories),
           alerts_enabled = COALESCE(%s, alerts_enabled)
     WHERE id = %s AND user_id = %s
    RETURNING {AREA_COLUMNS}
"""

# Alerts start from the first saved area, so a new user doesn't get a backlog.
# '' sorts before every source, so the next incident mapped after now() is new.
START_ALERTS = """
    INSERT INTO alert_state (user_id, geocoded_at, source, source_incident_id)
    VALUES (%s, now(), '', '') ON CONFLICT (user_id) DO NOTHING
"""


# Incidents mapped after the user's marker, inside any of their enabled areas. Old
# incidents are still being mapped, so occurred_at keeps those from alerting as new.
NEW_ALERTS = COLUMNS + """,
           i.geocoded_at,
           array_agg(a.name ORDER BY a.id) AS areas
""" + FROM_AND_JOINS + f"""
    JOIN alert_state s ON s.user_id = %(user_id)s
    JOIN saved_areas a ON a.user_id = %(user_id)s AND a.alerts_enabled
     AND ST_DWithin(i.geom, a.geom, a.radius_mi * {METERS_PER_MILE})
     AND (cardinality(a.categories) = 0 OR COALESCE(nc.category_code, 'OTHER') = ANY(a.categories))
    WHERE i.location_quality = 'in_county' AND i.geocode_trusted
      AND i.occurred_at > now() - interval '30 days'
      AND (i.geocoded_at, i.source, i.source_incident_id) > (s.geocoded_at, s.source, s.source_incident_id)
    GROUP BY i.source, i.source_incident_id, nc.category_code, ca.raw_city, ca.canonical_city
    ORDER BY i.geocoded_at, i.source, i.source_incident_id
    LIMIT %(limit)s
"""

# Only forward, so an old cursor sent late can't bring back alerts already seen.
MARK_SEEN = """
    UPDATE alert_state SET geocoded_at = %s, source = %s, source_incident_id = %s
     WHERE user_id = %s AND (geocoded_at, source, source_incident_id) < (%s, %s, %s)
"""


@bp.get(ALERTS)
@requires_access_token
def alerts():
    with current_app.pool.connection() as conn:
        rows = conn.execute(NEW_ALERTS, {"user_id": g.user_id, "limit": MAX_ALERTS + 1}).fetchall()
    has_more = len(rows) > MAX_ALERTS
    rows = rows[:MAX_ALERTS]
    return jsonify({
        "alerts": [_alert(r) for r in rows],
        "cursor": _encode_cursor(rows[-1]) if rows else None,
        "has_more": has_more,
    })


@bp.post(f"{ALERTS}/seen")
@requires_access_token
def mark_seen():
    body = request.get_json(silent=True)
    cursor = body.get("cursor") if isinstance(body, dict) else None
    if not isinstance(cursor, str):
        raise ValueError("send the cursor from /api/v1/users/me/alerts")  # noqa: TRY004, the app answers ValueError with a 400
    marker = _decode_cursor(cursor)
    with current_app.pool.connection() as conn:
        conn.execute(MARK_SEEN, (*marker, g.user_id, *marker))
    return "", 204


@bp.get(AREAS)
@requires_access_token
def list_areas():
    with current_app.pool.connection() as conn:
        rows = conn.execute(LIST_AREAS, (g.user_id,)).fetchall()
    return jsonify({"areas": [_area(r) for r in rows]})


@bp.post(AREAS)
@requires_access_token
def create_area():
    body = _body()
    missing = [name for name in ("name", "lat", "lon", "radius_mi") if name not in body]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")

    with current_app.pool.connection() as conn:
        fields = _validate(conn, body)
        with conn.transaction():
            # locks the user's row, so two requests at once can't both pass the cap
            conn.execute("SELECT 1 FROM users WHERE id = %s FOR UPDATE", (g.user_id,))
            count = conn.execute("SELECT count(*) AS n FROM saved_areas WHERE user_id = %s",
                                 (g.user_id,)).fetchone()["n"]
            if count >= MAX_AREAS:
                return jsonify({"error": f"at most {MAX_AREAS} saved areas"}), 409
            row = conn.execute(CREATE_AREA, (
                g.user_id, fields["name"], fields["lat"], fields["lon"], fields["radius_mi"],
                fields.get("categories", []), fields.get("alerts_enabled", True),
            )).fetchone()
            conn.execute(START_ALERTS, (g.user_id,))
    return jsonify(_area(row)), 201


@bp.patch(f"{AREAS}/<int:area_id>")
@requires_access_token
def update_area(area_id):
    with current_app.pool.connection() as conn:
        fields = _validate(conn, _body())
        row = conn.execute(UPDATE_AREA, (
            *(fields.get(name) for name in FIELDS), area_id, g.user_id,
        )).fetchone()
    if row is None:
        return jsonify({"error": "no such area"}), 404
    return jsonify(_area(row))


@bp.delete(f"{AREAS}/<int:area_id>")
@requires_access_token
def delete_area(area_id):
    with current_app.pool.connection() as conn:
        deleted = conn.execute("DELETE FROM saved_areas WHERE id = %s AND user_id = %s",
                               (area_id, g.user_id)).rowcount
    if not deleted:
        return jsonify({"error": "no such area"}), 404
    return "", 204


def _body() -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValueError("send a JSON object")  # noqa: TRY004, the app answers ValueError with a 400
    unknown = [name for name in body if name not in FIELDS]
    if unknown:
        raise ValueError(f"unknown field {unknown[0]}; fields are {', '.join(FIELDS)}")
    return body


def _validate(conn, body: dict) -> dict:
    fields = {}

    if "name" in body:
        name = body["name"].strip() if isinstance(body["name"], str) else ""
        if not 1 <= len(name) <= MAX_NAME:
            raise ValueError(f"name must be 1 to {MAX_NAME} characters")
        fields["name"] = name

    if "lat" in body:
        fields["lat"] = _number(body["lat"], "lat", COUNTY["south"], COUNTY["north"])
    if "lon" in body:
        fields["lon"] = _number(body["lon"], "lon", COUNTY["west"], COUNTY["east"])
    if "radius_mi" in body:
        fields["radius_mi"] = _number(body["radius_mi"], "radius_mi", MIN_RADIUS_MI, MAX_RADIUS_MI)

    if "categories" in body:
        categories = body["categories"]
        if not isinstance(categories, list) or not all(isinstance(c, str) for c in categories):
            raise ValueError("categories must be a list of category codes")
        categories = list(dict.fromkeys(c.strip().upper() for c in categories))
        known = {r["code"] for r in conn.execute("SELECT code FROM incident_categories WHERE active")}
        unknown = [c for c in categories if c not in known]
        if unknown:
            raise ValueError(f"unknown category {unknown[0]}; see /api/v1/incident-types")
        fields["categories"] = categories

    if "alerts_enabled" in body:
        if not isinstance(body["alerts_enabled"], bool):
            raise ValueError("alerts_enabled must be true or false")
        fields["alerts_enabled"] = body["alerts_enabled"]

    return fields


def _number(value, name: str, low: float, high: float) -> float:
    # bool is an int in Python, so true would otherwise pass as 1
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise ValueError(f"{name} must be a number from {low} to {high}")
    return float(value)


def _area(row) -> dict:
    return {**row, "created_at": row["created_at"].isoformat()}


def _alert(row) -> dict:
    alert = {key: value for key, value in row.items() if key != "geocoded_at"}
    return {**alert, "occurred_at": row["occurred_at"].isoformat()}


def _encode_cursor(row) -> str:
    raw = f"{row['geocoded_at'].isoformat()}|{row['source']}|{row['source_incident_id']}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str, str]:
    try:
        geocoded_at, source, source_incident_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 2)
        return datetime.fromisoformat(geocoded_at), source, source_incident_id
    except (ValueError, UnicodeDecodeError):
        raise ValueError("cursor is not valid") from None
