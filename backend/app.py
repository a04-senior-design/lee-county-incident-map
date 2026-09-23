import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from cache import get_incidents  # noqa: E402 — imported after env load
from ml.dbscan import run_clusters, load_csv_incidents, cluster_levels  # noqa: E402
from ml.animation import kde as kde_animation  # noqa: E402
from ml.animation import dbscan as dbscan_animation  # noqa: E402
from ml.generate_dbscan_snapshots import build_snapshots  # noqa: E402
from pandas.tseries.frequencies import to_offset  # noqa: E402

app = Flask(__name__)

allowed_origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")
CORS(app, resources={r"/api/*": {"origins": allowed_origin}})


def _parse_dbscan_level_overrides(args) -> dict:
    """Build a {level_name: {epsilon, min_pts, color}} dict from per-level
    `<level>_eps`/`<level>_min_pts` query params, falling back to
    cluster_levels defaults; omits any level left out of `levels`
    (a comma-separated list of enabled level names) so it's excluded from
    the DBSCAN run entirely."""
    enabled = args.get("levels")
    enabled_names = set(enabled.split(",")) if enabled else set(cluster_levels.keys())

    level_configs = {}
    for name, defaults in cluster_levels.items():
        if name not in enabled_names:
            continue
        eps = float(args.get(f"{name}_eps", defaults["epsilon"]))
        min_pts = int(args.get(f"{name}_min_pts", defaults["min_pts"]))
        level_configs[name] = {"epsilon": eps, "min_pts": min_pts, "color": defaults["color"]}
    return level_configs


@app.route("/cluster-lab")
def cluster_lab():
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    return send_from_directory(frontend_dir, "cluster-lab.html")


@app.route("/animation-lab")
def animation_lab():
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    return send_from_directory(frontend_dir, "animation-lab.html")


@app.route("/animation-assets/kde/<path:filename>")
def animation_kde_asset(filename):
    return send_from_directory(kde_animation.PNG_DIR, filename)


@app.route("/api/animation/kde")
def animation_kde():
    frames = [
        {**frame, "image": f"/animation-assets/kde/{frame['filename']}"}
        for frame in kde_animation.list_frames()
    ]
    return jsonify({"bounds": kde_animation.BOUNDS, "frames": frames})


@app.route("/api/animation/dbscan")
def animation_dbscan():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    window_length = request.args.get("window_length")
    time_step = request.args.get("time_step")
    has_level_overrides = any(
        key == "levels" or key.endswith("_eps") or key.endswith("_min_pts")
        for key in request.args
    )

    # no windowing or level params -> serve the precomputed snapshots, otherwise recompute on demand
    if not any([start_date, end_date, window_length, time_step, has_level_overrides]):
        return jsonify({"frames": dbscan_animation.load_snapshots()})

    try:
        level_configs = _parse_dbscan_level_overrides(request.args)
        frames = build_snapshots(
            start_date=start_date,
            end_date=end_date,
            window_length=to_offset(window_length) if window_length else None,
            time_step=to_offset(time_step) if time_step else None,
            level_configs=level_configs,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"frames": frames})


@app.route("/api/incidents")
def incidents():
    data = get_incidents()
    return jsonify(data)



@app.route("/api/clusters")
def clusters():
    try:
        eps = float(request.args.get("eps", 13123.0))
    #     min_pts = int(request.args.get("min_pts", 20))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid parameters"}), 400

    # eps = 4 # max(500.0, min(50000.0, eps))
    min_pts = 4 # max(2, min(100, min_pts))

    level = request.args.get("level")
    cluster_color = cluster_levels[level]["color"] if level in cluster_levels else None

    data = load_csv_incidents()
    result = run_clusters(data, eps, min_pts, cluster_color=cluster_color)
    return jsonify(result)


@app.route("/api/clusters/multi")
def clusters_multi():
    data = load_csv_incidents()
    
    all_results = {}
    for level, settings in cluster_levels.items():
        result = run_clusters(incidents=data, eps=settings["epsilon"], min_pts=settings["min_pts"], cluster_color=settings.get("color"))
        all_results[level] = result
        
    return jsonify(all_results)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
