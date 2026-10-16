from flask import Blueprint, current_app, g, jsonify, request

from leecad_api.auth import API, requires_access_token

AREAS = f"{API}/users/me/areas"
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
        raise ValueError("send a JSON object")
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
