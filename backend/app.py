import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from cache import get_incidents  # noqa: E402 — imported after env load

app = Flask(__name__)

allowed_origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")
CORS(app, resources={r"/api/*": {"origins": allowed_origin}})


@app.route("/api/incidents")
def incidents():
    data = get_incidents()
    return jsonify(data)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
