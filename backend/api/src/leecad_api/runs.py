import os
import re
import shutil
import tempfile
import time
import uuid

# DBSCAN routes leave cluster levels that later requests read back, so each run gets its
# own folder, found again by run_id.
RUNS_DIR = os.path.join(tempfile.gettempdir(), "leecad-dbscan-runs")
RUN_ID = re.compile(r"[0-9a-f]{32}")
RUN_LIFETIME = 3600


def new_run_dir() -> tuple[str, str]:
    os.makedirs(RUNS_DIR, exist_ok=True)
    cutoff = time.time() - RUN_LIFETIME
    for name in os.listdir(RUNS_DIR):
        path = os.path.join(RUNS_DIR, name)
        if os.path.getmtime(path) < cutoff:
            shutil.rmtree(path, ignore_errors=True)
    run_id = uuid.uuid4().hex
    return run_id, os.path.join(RUNS_DIR, run_id)


def run_dir(args) -> str:
    # checked before it becomes part of a path
    run_id = args.get("run_id", "")
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("run_id must be a run_id returned by /api/v1/clusters or /api/v1/animation/dbscan")
    return os.path.join(RUNS_DIR, run_id)
