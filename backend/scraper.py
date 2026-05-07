import os
import requests

INCIDENTS_URL = "https://www.sheriffleefl.org/public-api/incidents/q"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def fetch_incidents(limit: int = None) -> list[dict]:
    """Fetch incidents from the Lee County Sheriff's public API.

    Returns a list of raw incident dicts:
        id, occuredDate, nature, address, city, disposition, incidentNumber
    """
    if limit is None:
        limit = int(os.getenv("INCIDENT_LIMIT", 1000))

    params = {"limit": limit}
    response = requests.get(INCIDENTS_URL, params=params, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()
