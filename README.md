# Lee County Incident Map

An interactive map and crime-analysis tool for public-safety activity in Lee County, FL. It collects Computer-Aided Dispatch (CAD) records from the Lee County Sheriff's Office, geocodes and stores them in PostGIS, and serves them through a React map app with incident browsing, hotspot analysis (DBSCAN, KDE, Gi*), saved areas with alerts, and route safety grading.

Built as a UCF Senior Design project.

**Live site:** [leecountyincidentmap.com](https://leecountyincidentmap.com)
**Data source:** [Lee County Sheriff's Office](https://www.sheriffleefl.org)

---

## Features

- Interactive [Leaflet](https://leafletjs.com) map with clustered markers, an incident list, and address search
- Filters by date range, incident category, city and map area
- Hotspot analysis layers:
  - **DBSCAN** clusters at multiple density levels
  - **KDE** heatmaps with optimized bandwidths
  - **Getis-Ord Gi\*** hot/cold spot heatmaps
  - Step-by-step animations of each algorithm
- Route safety grading
- User accounts (JWT auth), saved areas, and incident-category alerts
- Reports and summary statistics

---

## Architecture

```
Lee County Sheriff API
        │
        ▼
 backend/pipeline  ──►  PostgreSQL + PostGIS  ◄──  backend/api  ◄──  frontend
 (harvest, geocode)     (backend/database)        (Flask, /api/v1)   (React + Vite)
                                                        │
                                                   backend/ml
                                          (DBSCAN, KDE, Gi* algorithms)
```

Each backend component is its own project with its own README, and the components share only a database URL.

| Directory | What it is | Docs |
|---|---|---|
| [`frontend/`](frontend) | React 19 + Vite app (Leaflet, Mantine, MUI) | — |
| [`backend/api/`](backend/api) | Flask REST API (`leecad_api`), `uv` project | [README](backend/api/README.md), [`openapi.yaml`](backend/api/openapi.yaml) |
| [`backend/pipeline/`](backend/pipeline) | Data collection: adapters, three-tier geocoder, bulk historical crawl, AWS Lambda feeds | [README](backend/pipeline/README.md) |
| [`backend/database/`](backend/database) | Alembic migrations and local PostGIS via Docker | [README](backend/database/README.md) |
| [`backend/ml/`](backend/ml) | DBSCAN, KDE (with `BandwidthOptimizer`) and Gi\* implementations, tests and animation generators | [`kde`](backend/ml/kde/README.md), [`gi_star`](backend/ml/gi_star/README.md), [`dbscan`](backend/ml/dbscan/tests/README.md) |

Other top-level folders: `documents/` (diagrams, meeting notes), `data/` (sample CSVs), `resources/`.

---

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- Docker (for the local PostGIS database)

---

## Getting started

### 1. Clone

```bash
git clone https://github.com/a04-senior-design/lee-county-incident-map.git
cd lee-county-incident-map
```

### 2. Start the database

```bash
cd backend/database
./local-db.sh up        # PostGIS on localhost:5433, applies all migrations
```

### 3. Run the API

```bash
cd backend/api
cp .env.example .env    # set DATABASE_URL and JWT_SECRET
uv sync
uv run flask --app leecad_api.app:create_app run --port 5001
```

`.env` settings:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET` | Secret for signing access tokens |
| `ALLOWED_ORIGINS` | CORS origin(s), e.g. `http://localhost:5173` |
| `COOKIE_SECURE` | `false` for local HTTP development |

### 4. Load data (optional)

An empty database has nothing to map. Populate it with the pipeline:

```bash
cd backend/pipeline
uv sync
uv run leecad harvest lee_county   # fetch + normalize + upsert
uv run leecad backfill 150         # geocode records lacking coordinates
```

See the [pipeline README](backend/pipeline/README.md) for the bulk historical crawl and deployment.

### 5. Run the frontend

```bash
cd frontend
npm install
npm run dev             # http://localhost:5173
```

By default [`frontend/vite.config.js`](frontend/vite.config.js) proxies `/api` to the production site. To use your local API instead, point the proxy `target` at `http://localhost:5001`.

---

## API overview

Base path `/api/v1`. Full reference in [`backend/api/openapi.yaml`](backend/api/openapi.yaml).

| Area | Endpoints |
|---|---|
| Incidents | `GET /incidents` (filters, cursor paging, `format=geojson`), `GET /incidents/{source}/{id}`, `GET /incident-types` |
| Stats & health | `GET /stats/summary`, `GET /health` |
| Analysis | `GET /clusters`, `GET /kde-heatmap`, `GET /gi-star-heatmap` |
| Animations | `GET /animation/dbscan`, `/animation/kde-heatmap`, `/animation/kde-heatmap-dbscan`, `/animation/gi-star-heatmap` |
| Auth | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`; `GET /users/me` |
| Saved areas, alerts, reports | Authenticated endpoints for the signed-in user |

---

## Testing

Each component has its own suite and CI workflow in [`.github/workflows/`](.github/workflows).

```bash
# API (needs the local database running)
cd backend/api
TEST_DATABASE_URL=postgresql://leecad:leecad-local-only@localhost:5433/leecad uv run pytest

# Pipeline
cd backend/pipeline && uv run pytest

# ML algorithms
cd backend/ml/kde && pytest
cd backend/ml/gi_star && pytest
cd backend/ml/dbscan/tests && pytest

# Frontend lint
cd frontend && npm run lint
```

---

## Notes

- The Sheriff's API publishes with a short delay and exposes only the ~1,000 most recent records, which is why the pipeline stores history itself.
- Filter by `category`, not raw `nature`; the raw field has hundreds of typo variants.
- GeoJSON coordinates are `[lon, lat]`.

## Contributing

See [WORKFLOW.md](WORKFLOW.md) for the branch and pull request workflow.

## License

[MIT](LICENSE)
