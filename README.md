# Fort Myers Crime Map

An interactive map of recent police incidents in Lee County, FL, powered by the Lee County Sheriff's Office public API. Incidents are geocoded and plotted on a live map with filters for date range and incident type.

**Live data source:** [Lee County Sheriff's Office](https://www.sheriffleefl.org)

---

## Features

- Live incident map using [Leaflet.js](https://leafletjs.com)
- Geocoded addresses via OpenStreetMap / Nominatim (disk-cached)
- Filter by date range (3 days, 7 days, 30 days)
- Filter by incident/crime type with color-coded markers
- Incident count badge updates with active filters
- Dark theme UI with attribution footer

---

## Project Structure

```
fort-myers-crime-map/
├── backend/
│   ├── app.py              # Flask application entry point
│   ├── cache.py            # In-memory cache (1-hour TTL, thread-safe)
│   ├── geocoder.py         # Geocodes addresses via Nominatim; disk-caches results
│   ├── scraper.py          # Fetches raw incident JSON from the sheriff's API
│   ├── requirements.txt    # Python dependencies
│   └── geocode_cache.json  # Persistent geocode cache (auto-generated)
├── frontend/
│   ├── index.html          # App shell
│   ├── app.js              # Map logic, data loading, filtering
│   ├── style.css           # Dark-theme UI styles
│   └── config.js           # API base URL (swap for production)
└── .env                    # Backend environment config (not committed)
```

---

## Prerequisites

- Python 3.10+
- Node.js (for `npx serve`)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/AndrewKelton/fort-myers-crime-map.git
cd fort-myers-crime-map
```

### 2. Configure environment

Create a `.env` file at the project root:

```env
ALLOWED_ORIGIN=http://localhost:5173
PORT=5001
INCIDENT_LIMIT=1000
```

### 3. Install backend dependencies

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Run the backend

```bash
cd backend
source .venv/bin/activate
python app.py
```

The API will be available at `http://localhost:5001`.

> **First run:** The geocoder will make live requests to Nominatim for any addresses not yet in the cache. This can take several minutes for 1,000 incidents. Progress is saved every 25 lookups.

### 5. Run the frontend

In a separate terminal:

```bash
npx serve frontend -l 5173
```

Open `http://localhost:5173` in your browser.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/incidents` | Returns up to 1,000 geocoded incidents as JSON |
| `GET` | `/api/health` | Health check — returns `{"status": "ok"}` |

---

## Notes

- The Sheriff's API has an approximate **3-day publication delay** — the "3 Days Ago" filter may return few or no results depending on the day. Use "Last 7 days" to reliably see data.
- The CORS policy on the sheriff's API requires a backend proxy; the frontend cannot call it directly.
- Geocode results are cached to `backend/geocode_cache.json` and reused across restarts.

---

## Deployment

For production (e.g., DigitalOcean):

1. Run the backend with `gunicorn`: `gunicorn app:app`
2. Serve the `frontend/` directory with nginx
3. Update `ALLOWED_ORIGIN` in `.env` and `API_BASE_URL` in `frontend/config.js` to your production URLs

---

## License

[MIT](LICENSE)

---

Created by [Andrew Kelton](https://www.linkedin.com/in/andrew-kelton)
