```mermaid
flowchart TD
    subgraph USER_PARAMS["⓪ User Parameters  (UI Controls)"]
        EPS_FT["Search Radius
        Input: feet  🇺🇸
        ──────────────
        e.g. 300 ft · 1 500 ft · 5 000 ft"]
        MIN_C["Min Crimes
        Minimum incidents to form a cluster
        ──────────────
        e.g. 3 · 5 · 10"]
        CONV["Unit Conversion & Scaling
        ε (fine)   = radius ft × 0.3048
        ε (mid)    = radius ft × 0.3048 × 5
        ε (broad)  = radius ft × 0.3048 × 10
        min_samples scales with level"]
        EPS_FT --> CONV
        MIN_C --> CONV
    end

    subgraph INGEST["① Data Ingestion"]
        DB[("`**incidents**
        PostgreSQL table`")]
        FILTER["Filter Query
        WHERE lat IS NOT NULL
        AND lon IS NOT NULL
        AND occurred_at ≥ window_start
        ── idx_incidents_location
        ── idx_incidents_occurred"]
        FIELDS["Extracted Fields
        lat · lon · nature
        occurred_at · disposition · status"]
        DB --> FILTER --> FIELDS
    end

    subgraph FEAT["② Feature Engineering"]
        SEV["Nature → Severity Weight
        violent crime → 5
        property crime → 3
        disturbance → 2
        other → 1"]
        PROJ["Coordinate Projection
        WGS84 EPSG:4326 (stored)
        ↓
        FL State Plane East EPSG:2236
        (meters — needed for ε, bandwidth)"]
        FIELDS --> SEV
        FIELDS --> PROJ
    end

    subgraph DBSCAN_STAGE["③ DBSCAN  ─  3 Scale Levels  (scikit-learn)"]
        direction LR
        D1["Micro  Level 1
        ε = user radius (fine)
        min_samples = min crimes
        ──────────────
        street-corner clusters"]
        D2["Meso  Level 2
        ε = user radius × 5 (mid)
        min_samples = min crimes × 2
        ──────────────
        neighborhood clusters"]
        D3["Macro  Level 3
        ε = user radius × 10 (broad)
        min_samples = min crimes × 3
        ──────────────
        district-level clusters"]
        NOISE["Noise Points
        label = -1
        (isolated incidents)"]
        D1 -. noise .-> NOISE
        D2 -. noise .-> NOISE
        D3 -. noise .-> NOISE
    end

    subgraph KDE_STAGE["④ KDE  ─  Heat Map  (scipy / sklearn)"]
        GRID["Grid Generation
        Lee County bounding box
        resolution ≈ 100 m cells"]
        BASE["Base KDE  (required)
        Single bandwidth
        ── Scott's / Silverman's rule
        Gaussian kernel
        Input: projected (x,y) points"]
        WKDE["Weighted Multi-bandwidth KDE  (optional)
        Bandwidth 1 (fine) + Bandwidth 2 (coarse)
        Weights = severity scores
        Input: (x,y) + weight vector"]
        GRID --> BASE
        GRID --> WKDE
    end

    subgraph GI["⑤ Getis-Ord Gi*  ─  Statistical Hotspot Validation  (PySAL / esda)"]
        WM["Spatial Weights Matrix
        ⚠ Decision needed:
        Queen contiguity (8-neighbor grid)
        OR fixed distance band ≈ DBSCAN ε
        Row-standardized: yes"]
        ZSCORE["Z-score per cell
        (local spatial autocorrelation)"]
        SIG["Significance Classification
        |Z| > 2.576 → 99% hot / cold spot
        |Z| > 1.960 → 95%
        |Z| > 1.645 → 90%
        else → not significant"]
        HOT["Hot Spots
        positive Z, significant
        → high-density crime zones"]
        COLD["Cold Spots
        negative Z, significant
        → unusually low activity"]
        WM --> ZSCORE --> SIG
        SIG --> HOT
        SIG --> COLD
    end

    subgraph OUT["⑥ Output & Serving"]
        MERGE["Merge Results
        DBSCAN cluster polygons (3 levels)
        KDE density raster
        Gi* significance layer"]
        API["Flask API
        /api/analysis
        /api/clusters
        /api/heatmap"]
        LEAFLET["Frontend — Leaflet Map
        Layer: cluster boundaries
        Layer: heat map overlay
        Layer: hotspot markers"]
        MERGE --> API --> LEAFLET
    end

    %% Flow connections
    CONV --> D1 & D2 & D3
    PROJ --> D1 & D2 & D3
    PROJ --> GRID
    SEV --> WKDE
    NOISE --> GRID

    BASE --> WM
    WKDE --> WM
    D1 & D2 & D3 --> WM

    HOT & COLD & BASE & D1 & D2 & D3 --> MERGE
```

## DBSCAN Feature — Use Case Diagram

Mermaid has no native UML use-case shape, so actors are drawn as stick-figure nodes and use cases as stadium-shaped nodes inside the system boundary. `<<include>>` edges are mandatory sub-steps; `<<extend>>` edges are optional/conditional behavior.

```mermaid
flowchart LR
    Viewer(("🧍
    Map Viewer"))
    Prototyper(("🧑‍💻
    ML Prototyper"))

    subgraph SYS["DBSCAN Clustering Feature — Cluster Lab"]
        UC1(["View Clustered
        Incident Map"])
        UC2(["Toggle Cluster
        Level Visibility"])
        UC3(["Adjust Cluster
        Density (slider)"])
        UC4(["View Cluster
        Statistics"])
        UC5(["Request Cluster Data
        (/api/clusters, /api/clusters/multi)"])
        UC6(["Load Incident Data
        (CSV / cache)"])
        UC7(["Run DBSCAN
        Clustering"])
        UC8(["Project Coordinates
        WGS84 → EPSG:2882"])
        UC9(["Generate Cluster
        Hull Polygons"])
        UC10(["Prototype DBSCAN
        Parameters Offline"])
        UC11(["Render Snapshot &
        Animation Outputs"])
    end

    Viewer --> UC1
    Viewer --> UC2
    Viewer --> UC3
    Viewer --> UC4
    Prototyper --> UC10

    UC1 -. "&laquo;include&raquo;" .-> UC5
    UC3 -. "&laquo;include&raquo;" .-> UC5
    UC4 -. "&laquo;extend&raquo;" .-> UC1
    UC2 -. "&laquo;extend&raquo;" .-> UC1

    UC5 -. "&laquo;include&raquo;" .-> UC6
    UC5 -. "&laquo;include&raquo;" .-> UC7
    UC7 -. "&laquo;include&raquo;" .-> UC8
    UC7 -. "&laquo;include&raquo;" .-> UC9

    UC10 -. "&laquo;include&raquo;" .-> UC7
    UC10 -. "&laquo;include&raquo;" .-> UC11
```

**Actors**
- **Map Viewer** — end user of the [cluster-lab.html](../frontend/cluster-lab.html) page; toggles the district/neighborhood/street layers and drags the sparse↔dense sliders.
- **ML Prototyper** — developer running [dbscan_demo.py](../backend/ml/dbscan_demo.py) offline to tune `EPS`/`MIN_SAMPLES` before wiring new behavior into the live feature.

**Use cases**
- *View Clustered Incident Map* / *Toggle Cluster Level Visibility* / *Adjust Cluster Density* / *View Cluster Statistics* — client-side interactions in [cluster-lab.html](../frontend/cluster-lab.html).
- *Request Cluster Data* — Flask routes `/api/clusters` and `/api/clusters/multi` in [app.py](../backend/app.py).
- *Load Incident Data*, *Run DBSCAN Clustering*, *Project Coordinates*, *Generate Cluster Hull Polygons* — served by `load_csv_incidents()` / `run_clusters()` in [clustering.py](../backend/ml/clustering.py).
- *Prototype DBSCAN Parameters Offline* / *Render Snapshot & Animation Outputs* — standalone exploration in [dbscan_demo.py](../backend/ml/dbscan_demo.py), decoupled from the live API.
```