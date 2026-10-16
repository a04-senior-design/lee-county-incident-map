from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, request, send_file
from report import generate_pdf

from leecad_api import queries
from leecad_api.auth import API, requires_access_token
from leecad_api.filters import EASTERN
from leecad_api.filters import parse as parse_filters

bp = Blueprint("reports", __name__)

MAX_REPORT_DAYS = 366


@bp.get(f"{API}/reports")
@requires_access_token
def report():
    # the title and the per-day chart need both ends, so days is not enough here
    if "days" in request.args or not request.args.get("from") or not request.args.get("to"):
        raise ValueError("a report needs from and to, not days")
    filters = parse_filters(request.args)
    start_date = date.fromisoformat(request.args["from"])
    end_date = date.fromisoformat(request.args["to"])
    if end_date - start_date >= timedelta(days=MAX_REPORT_DAYS):
        raise ValueError(f"a report covers at most {MAX_REPORT_DAYS} days")

    with current_app.pool.connection() as conn:
        rows = conn.execute(*queries.report_incidents(filters)).fetchall()
    if not rows:
        return jsonify({"error": "no mapped incidents match these filters"}), 400

    # the shape generate_pdf reads; times in Eastern so the hour and day charts match the map
    incidents = [{
        "nature": r["category"],
        "city": r["city"],
        "lat": r["lat"],
        "lng": r["lon"],
        "occuredDate": r["occurred_at"].astimezone(EASTERN).isoformat(),
    } for r in rows]

    # the incidents' extent plus a margin, as the /api/report route in app.py did
    pad = 0.01
    bounds = {
        "north": max(i["lat"] for i in incidents) + pad,
        "south": min(i["lat"] for i in incidents) - pad,
        "east": max(i["lng"] for i in incidents) + pad,
        "west": min(i["lng"] for i in incidents) - pad,
    }

    pdf = generate_pdf(incidents, bounds, start_date, end_date)
    return send_file(pdf, mimetype="application/pdf", as_attachment=True,
                     download_name=f"lee-county-report-{start_date}_to_{end_date}.pdf")
