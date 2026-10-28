import json
import os
import re
import shutil
import tempfile
import time
import uuid

# DBSCAN routes leave cluster levels that later requests read back, and the map routes leave
# their response for the report, so each run gets its own folder, found again by run_id.
RUNS_DIR = os.path.join(tempfile.gettempdir(), "leecad-runs")
RUN_ID = re.compile(r"[0-9a-f]{32}")
RUN_LIFETIME = 3600
RESPONSE = "response.json"


def new_run_dir() -> tuple[str, str]:
    os.makedirs(RUNS_DIR, exist_ok=True)
    cutoff = time.time() - RUN_LIFETIME
    for name in os.listdir(RUNS_DIR):
        path = os.path.join(RUNS_DIR, name)
        if os.path.getmtime(path) < cutoff:
            shutil.rmtree(path, ignore_errors=True)
    run_id = uuid.uuid4().hex
    return run_id, os.path.join(RUNS_DIR, run_id)


def run_dir(args, name: str = "run_id") -> str:
    # checked before it becomes part of a path
    run_id = args.get(name, "")
    if not RUN_ID.fullmatch(run_id):
        if name == "run_id":
            raise ValueError("run_id must be a run_id returned by /api/v1/clusters or /api/v1/animation/dbscan")
        raise ValueError(f"{name} must be a run_id returned by the analysis it names")
    return os.path.join(RUNS_DIR, run_id)


def inputs(filters, start_date, end_date) -> dict:
    """What a run was made from, in a form a report's own dates and filters compare equal to."""
    return {
        "start_date": start_date,
        "end_date": end_date,
        "categories": sorted(filters.categories),
        "cities": sorted(filters.cities),
        "sources": sorted(filters.sources),
        "bbox": list(filters.bbox) if filters.bbox else None,
    }


def save_response(path: str, analysis: str, inputs: dict, response: dict) -> None:
    with open(os.path.join(path, RESPONSE), "w") as f:
        json.dump({"analysis": analysis, "inputs": inputs, "response": response}, f)


def load_response(path: str) -> dict | None:
    # None when the run expired, or was a run that saves no response, like the animations
    try:
        with open(os.path.join(path, RESPONSE)) as f:
            return json.load(f)
    except FileNotFoundError:
        return None
