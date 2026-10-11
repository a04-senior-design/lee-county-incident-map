(() => {
  // ── Constants ──────────────────────────────────────────────────────────────

  const LEE_COUNTY_CENTER = [26.56, -81.87];
  const DEFAULT_ZOOM = 11;

  // Color palette keyed by incident nature (first word, lowercase)
  const NATURE_COLORS = {
    disturbance:  "#e74c3c",
    assault:      "#c0392b",
    theft:        "#e67e22",
    burglary:     "#d35400",
    traffic:      "#3498db",
    suspicious:   "#9b59b6",
    medical:      "#1abc9c",
    fire:         "#e74c3c",
    welfare:      "#27ae60",
    domestic:     "#c0392b",
    default:      "#7f8c8d",
  };

  // Route grader tuning
  const ROUTE_CORRIDOR_M   = 400; // incidents farther than this from the route are ignored
  const ROUTE_EDGE_WEIGHT  = 0.5; // proximity weight at the corridor edge (1 on the route)
  const ROUTE_HALF_LIFE_D  = 14;  // an incident's weight halves every N days

  // Severity tiers, tuned for runners and bikers (risk to someone passing
  // through on foot or bike). Every route starts at 100; each incident deducts
  // `pts` (when recent and right on the route; less when older or farther), and
  // a tier's total deduction is capped at `cap`, so a pile of minor calls can't
  // sink a route. Checked in order; first matching pattern wins, so the no-risk
  // tier comes first to catch "identity theft", "stolen plate", etc.
  const SEVERITY_TIERS = [
    { re: /identity theft|fraud|stolen plate|stolen license|recover|cyber|medical|welfare|alarm|assist|lost|info|check|death investigation/, pts: 0, cap: 0 },
    { re: /homicide|murder|shoot|shots|stab|assault|battery|robbery|carjack|kidnap|weapon|armed|deadly missile|sexual/, pts: 10, cap: Infinity },
    { re: /harass|stalk|indecent|exposure|traffic|crash|hit and run/, pts: 5, cap: 20 },
    { re: /theft|burglary|larceny|stolen/, pts: 2, cap: 15 },
    { re: /animal|livestock/, pts: 3, cap: 10 },
    { re: /domestic|fight|drug|narcotic|dui|reckless|vandal|mischief|suspicious|trespass|bomb/, pts: 2, cap: 15 },
    // Plain disturbances are ~40% of all calls (mostly noise/neighbor disputes),
    // so they get their own small budget instead of filling the tier above
    { re: /disturbance/, pts: 1, cap: 10 },
  ];
  const SEVERITY_DEFAULT = { pts: 1, cap: 10 };

  // ── State ──────────────────────────────────────────────────────────────────

  let allIncidents = [];
  let markerLayer = null;
  let activeNatures = null; // null = all types shown
  let dataSpanDays = null;  // age (days) of the oldest incident in the feed

  // ── Map setup ──────────────────────────────────────────────────────────────

  const map = L.map("map").setView(LEE_COUNTY_CENTER, DEFAULT_ZOOM);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  // ── Helpers ────────────────────────────────────────────────────────────────

  function markerColor(nature) {
    if (!nature) return NATURE_COLORS.default;
    const key = nature.trim().toLowerCase().split(/\s+/)[0];
    return NATURE_COLORS[key] || NATURE_COLORS.default;
  }

  function toTitleCase(str) {
    return str.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function circleMarker(incident) {
    return L.circleMarker([incident.lat, incident.lng], {
      radius: 7,
      fillColor: markerColor(incident.nature),
      color: "#fff",
      weight: 1,
      opacity: 0.9,
      fillOpacity: 0.85,
    }).bindPopup(buildPopup(incident));
  }

  function buildPopup(inc) {
    const date = inc.occuredDate
      ? inc.occuredDate.replace("T", " ").slice(0, 16)
      : "Unknown date";
    return `
      <div class="popup">
        <strong>${inc.nature || "Unknown"}</strong><br>
        <span class="popup-addr">${inc.address}, ${inc.city}</span><br>
        <span class="popup-date">${date}</span><br>
        <span class="popup-disp">${inc.disposition || ""}</span>
        <span class="popup-id">#${inc.incidentNumber || inc.id}</span>
      </div>`;
  }

  function filterByDays(incidents, days) {
    if (days === 0) return incidents;
    const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
    return incidents.filter((inc) => {
      if (!inc.occuredDate) return false;
      // Normalize to ISO 8601 for Safari: replace space, truncate to 3 decimal places
      const normalized = inc.occuredDate.replace(" ", "T").replace(/(\.\d{3})\d+/, "$1");
      return new Date(normalized).getTime() >= cutoff;
    });
  }

  function renderMarkers(incidents) {
    if (markerLayer) map.removeLayer(markerLayer);

    const mappable = incidents.filter(
      (inc) => inc.lat != null && inc.lng != null
    );

    markerLayer = L.layerGroup(mappable.map(circleMarker)).addTo(map);

    document.getElementById("count-badge").textContent =
      `${mappable.length.toLocaleString()} incident${mappable.length !== 1 ? "s" : ""}`;
  }

  function normalizeDate(raw) {
    return raw.replace(" ", "T").replace(/(\.\d{3})\d+/, "$1");
  }

  function computeDataSpanDays(incidents) {
    let oldest = Infinity;
    for (const inc of incidents) {
      if (!inc.occuredDate) continue;
      const t = new Date(normalizeDate(inc.occuredDate)).getTime();
      if (!Number.isNaN(t) && t < oldest) oldest = t;
    }
    if (oldest === Infinity) return null;
    return Math.ceil((Date.now() - oldest) / (24 * 60 * 60 * 1000));
  }

  function updateDateLabel(days) {
    const slider = document.getElementById("date-filter");
    const label  = document.getElementById("date-filter-val");
    const maxed  = dataSpanDays !== null && days >= dataSpanDays;

    label.textContent = maxed
      ? `all available data (~${dataSpanDays} days)`
      : `${days} day${days !== 1 ? "s" : ""}`;
    label.classList.toggle("date-filter-maxed", maxed);
    slider.classList.toggle("date-filter-maxed", maxed);

    const pct   = ((slider.value - slider.min) / (slider.max - slider.min)) * 100;
    const color = maxed ? "#d9a441" : "#4f83cc";
    slider.style.background = `linear-gradient(to right, ${color} ${pct}%, #3a3a55 ${pct}%)`;
  }

  function applyFilter() {
    const days = parseInt(
      document.getElementById("date-filter").value,
      10
    );
    updateDateLabel(days);
    let filtered = filterByDays(allIncidents, days);
    if (activeNatures !== null) {
      filtered = filtered.filter(
        (inc) => activeNatures.has(inc.nature || "Unknown")
      );
    }
    renderMarkers(filtered);
    if (routeGraded) gradeRoute();
  }

  // ── Nature filter ──────────────────────────────────────────────────────────

  function buildNatureFilter(incidents) {
    const natures = [
      ...new Set(incidents.map((inc) => inc.nature || "Unknown")),
    ].sort();

    const panel = document.getElementById("nature-panel");
    panel.innerHTML = "";

    // "All types" master toggle
    const allLabel = document.createElement("label");
    allLabel.className = "nature-row nature-all";
    const allCb = document.createElement("input");
    allCb.type = "checkbox";
    allCb.id = "nature-cb-all";
    allCb.checked = true;
    allLabel.appendChild(allCb);
    allLabel.appendChild(document.createTextNode(" All types"));
    panel.appendChild(allLabel);

    const hr = document.createElement("hr");
    hr.className = "nature-divider";
    panel.appendChild(hr);

    // Per-nature rows
    for (const nature of natures) {
      const row = document.createElement("label");
      row.className = "nature-row";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = nature;
      cb.checked = true;
      cb.addEventListener("change", onNatureChange);
      const dot = document.createElement("span");
      dot.className = "nature-dot";
      dot.style.background = markerColor(nature);
      row.appendChild(cb);
      row.appendChild(dot);
      row.appendChild(document.createTextNode(" " + toTitleCase(nature)));
      panel.appendChild(row);
    }

    allCb.addEventListener("change", () => {
      panel
        .querySelectorAll("input[type=checkbox]:not(#nature-cb-all)")
        .forEach((cb) => { cb.checked = allCb.checked; });
      activeNatures = allCb.checked ? null : new Set();
      applyFilter();
      updateNatureBtn();
    });
  }

  function onNatureChange() {
    const checkboxes = [
      ...document.querySelectorAll("#nature-panel input[type=checkbox]:not(#nature-cb-all)"),
    ];
    const allCb = document.getElementById("nature-cb-all");
    const checked = checkboxes.filter((cb) => cb.checked).map((cb) => cb.value);

    if (checked.length === checkboxes.length) {
      activeNatures = null;
      allCb.checked = true;
      allCb.indeterminate = false;
    } else if (checked.length === 0) {
      activeNatures = new Set();
      allCb.checked = false;
      allCb.indeterminate = false;
    } else {
      activeNatures = new Set(checked);
      allCb.checked = false;
      allCb.indeterminate = true;
    }
    applyFilter();
    updateNatureBtn();
  }

  function updateNatureBtn() {
    const btn = document.getElementById("nature-filter-btn");
    if (activeNatures === null) {
      btn.textContent = "All types ▾";
      btn.classList.remove("nature-filtered");
    } else if (activeNatures.size === 0) {
      btn.textContent = "No types ▾";
      btn.classList.add("nature-filtered");
    } else {
      btn.textContent = `${activeNatures.size} type${activeNatures.size !== 1 ? "s" : ""} ▾`;
      btn.classList.add("nature-filtered");
    }
  }

  // ── Data loading ───────────────────────────────────────────────────────────

  async function loadIncidents() {
    const overlay = document.getElementById("loading-overlay");
    const msg = document.getElementById("loading-msg");

    try {
      msg.textContent = "Fetching incidents…";
      const res = await fetch(`${API_BASE_URL}/api/incidents`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      allIncidents = await res.json();
      dataSpanDays = computeDataSpanDays(allIncidents);
      msg.textContent = `Geocoding complete. ${allIncidents.length} incidents loaded.`;

      buildNatureFilter(allIncidents);
      applyFilter();
      overlay.classList.add("hidden");
    } catch (err) {
      msg.textContent = `Error loading data: ${err.message}`;
      console.error(err);
    }
  }

  // ── Event listeners ────────────────────────────────────────────────────────

  let filterDebounce = null;
  document.getElementById("date-filter").addEventListener("input", () => {
    updateDateLabel(
      parseInt(document.getElementById("date-filter").value, 10)
    );
    clearTimeout(filterDebounce);
    filterDebounce = setTimeout(applyFilter, 150);
  });

  document.getElementById("nature-filter-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    document.getElementById("nature-panel").classList.toggle("hidden");
  });

  document.getElementById("nature-panel").addEventListener("click", (e) => {
    e.stopPropagation();
  });

  document.addEventListener("click", () => {
    document.getElementById("nature-panel").classList.add("hidden");
  });

  // Report download

  document.getElementById("report-btn").addEventListener("click", async () => {
    const btn  = document.getElementById("report-btn");
    const days = parseInt(document.getElementById("date-filter").value, 10);
    const b    = map.getBounds();

    btn.classList.add("loading");
    btn.textContent = "Generating…";
    btn.disabled    = true;

    try {
      const res = await fetch(`${API_BASE_URL}/api/report`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          days,
          bounds: {
            north: b.getNorth(),
            south: b.getSouth(),
            east:  b.getEast(),
            west:  b.getWest(),
          },
        }),
      });

      if (!res.ok) throw new Error(`Server error ${res.status}`);

      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = `lee-county-report.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(`Report generation failed: ${err.message}`);
    } finally {
      btn.classList.remove("loading");
      btn.textContent = "⬇ Generate Report";
      btn.disabled    = false;
    }
  });

  // Route safety grader
  // The user clicks points on the map to trace a route.

  let routeMode    = false;
  let routeGraded  = false;
  let routePoints  = [];
  let routeLine    = null;
  let routeHilites = null;

  function tierOf(nature) {
    const n = (nature || "").toLowerCase();
    return SEVERITY_TIERS.find((t) => t.re.test(n)) || SEVERITY_DEFAULT;
  }

  // Distance in meters from point p to segment a–b, using a local flat projection
  function distToSegmentM(p, a, b) {
    const mPerDegLat = 111320;
    const mPerDegLng = 111320 * Math.cos((p.lat * Math.PI) / 180);
    const ax = (a.lng - p.lng) * mPerDegLng, ay = (a.lat - p.lat) * mPerDegLat;
    const bx = (b.lng - p.lng) * mPerDegLng, by = (b.lat - p.lat) * mPerDegLat;
    const dx = bx - ax, dy = by - ay;
    const len2 = dx * dx + dy * dy;
    const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2));
    return Math.hypot(ax + t * dx, ay + t * dy);
  }

  function distToRouteM(p) {
    let best = Infinity;
    for (let i = 1; i < routePoints.length; i++) {
      best = Math.min(best, distToSegmentM(p, routePoints[i - 1], routePoints[i]));
    }
    return best;
  }

  function routeLengthKm() {
    let m = 0;
    for (let i = 1; i < routePoints.length; i++) {
      m += map.distance(routePoints[i - 1], routePoints[i]);
    }
    return m / 1000;
  }

  // Points one incident d meters from the route deducts: tier pts × recency × proximity
  function incidentPoints(tier, inc, d, now, days) {
    const t       = new Date(normalizeDate(inc.occuredDate)).getTime();
    const ageDays = Number.isNaN(t) ? days : Math.max(0, (now - t) / 86400000);
    return tier.pts
         * Math.pow(0.5, ageDays / ROUTE_HALF_LIFE_D)
         * (1 - (1 - ROUTE_EDGE_WEIGHT) * (d / ROUTE_CORRIDOR_M));
  }

  function scoreColor(score) {
    if (score >= 80) return "#27ae60";
    if (score >= 60) return "#d9a441";
    if (score >= 40) return "#e67e22";
    return "#e74c3c";
  }

  function scoreLabel(score) {
    if (score >= 80) return "Low risk";
    if (score >= 60) return "Moderate risk";
    if (score >= 40) return "Elevated risk";
    return "High risk";
  }

  function drawRoute(color) {
    if (routeLine) map.removeLayer(routeLine);
    routeLine = L.polyline(routePoints, {
      color: color || "#8ab4f8",
      weight: 5,
      opacity: 0.9,
      dashArray: routeGraded ? null : "8 6",
    }).addTo(map);
  }

  function gradeRoute() {
    if (routePoints.length < 2) {
      setRoutePanel(`<p class="route-hint">Add at least two points to grade a route.</p>`);
      return;
    }

    const days = parseInt(document.getElementById("date-filter").value, 10);
    const now  = Date.now();
    const incidents = filterByDays(allIncidents, days).filter((i) => i.lat != null && i.lng != null);
    const contributors = [];
    const tierTotals = new Map();

    for (const inc of incidents) {
      const d = distToRouteM(inc);
      if (d > ROUTE_CORRIDOR_M) continue;
      const tier = tierOf(inc.nature);
      const pts  = incidentPoints(tier, inc, d, now, days);
      tierTotals.set(tier, (tierTotals.get(tier) || 0) + pts);
      contributors.push({ inc, pts, d });
    }

    let penalty = 0;
    for (const [tier, total] of tierTotals) penalty += Math.min(total, tier.cap);

    const km    = routeLengthKm();
    const score = Math.max(0, Math.round(100 - penalty));
    const color = scoreColor(score);

    routeGraded = true;
    drawRoute(color);

    if (routeHilites) map.removeLayer(routeHilites);
    routeHilites = L.layerGroup(
      contributors.map(({ inc }) =>
        L.circleMarker([inc.lat, inc.lng], {
          radius: 11, color, weight: 2, fill: false, interactive: false,
        })
      )
    ).addTo(map);

    contributors.sort((a, b) => b.pts - a.pts);
    const top = contributors.filter((c) => c.pts > 0).slice(0, 5).map(({ inc, pts, d }) => `
      <li><span class="nature-dot" style="background:${markerColor(inc.nature)}"></span>
        ${toTitleCase(inc.nature || "Unknown")}
        <span class="route-dist">${Math.round(d)} m · −${pts < 1 ? pts.toFixed(1) : Math.round(pts)}</span></li>`).join("");

    setRoutePanel(`
      <div class="route-score" style="color:${color}">${score}<span>/100</span></div>
      <div class="route-label" style="color:${color}">${scoreLabel(score)}</div>
      <div class="route-stats">
        ${km.toFixed(2)} km · ${contributors.length} incident${contributors.length !== 1 ? "s" : ""}
        within ${ROUTE_CORRIDOR_M} m · last ${days} day${days !== 1 ? "s" : ""}
      </div>
      ${top ? `<div class="route-sub">Biggest factors</div><ul class="route-top">${top}</ul>` : ""}
    `);
  }

  function setRoutePanel(bodyHtml) {
    document.getElementById("route-body").innerHTML = bodyHtml;
  }

  function clearRoute() {
    routePoints = [];
    routeGraded = false;
    if (routeLine)    { map.removeLayer(routeLine);    routeLine = null; }
    if (routeHilites) { map.removeLayer(routeHilites); routeHilites = null; }
    setRoutePanel(`<p class="route-hint">Click the map to trace your route, then press <b>Grade</b> (or double-click the last point).</p>`);
  }

  function setRouteMode(on) {
    routeMode = on;
    document.getElementById("route-btn").classList.toggle("active", on);
    document.getElementById("route-panel").classList.toggle("hidden", !on);
    map.getContainer().classList.toggle("route-drawing", on);
    if (on) {
      map.doubleClickZoom.disable();
      clearRoute();
    } else {
      map.doubleClickZoom.enable();
      clearRoute();
    }
  }

  map.on("click", (e) => {
    if (!routeMode) return;
    const last = routePoints[routePoints.length - 1];
    if (last && last.equals(e.latlng)) return; // ignore the 2nd click of a double-click
    if (routeGraded) {                          // start editing again after a grade
      routeGraded = false;
      if (routeHilites) { map.removeLayer(routeHilites); routeHilites = null; }
    }
    routePoints.push(e.latlng);
    drawRoute();
    setRoutePanel(`<p class="route-hint">${routePoints.length} point${routePoints.length !== 1 ? "s" : ""} · ${routeLengthKm().toFixed(2)} km</p>`);
  });

  map.on("dblclick", () => { if (routeMode) gradeRoute(); });

  document.getElementById("route-btn").addEventListener("click", () => setRouteMode(!routeMode));
  document.getElementById("route-grade").addEventListener("click", gradeRoute);
  document.getElementById("route-clear").addEventListener("click", clearRoute);
  document.getElementById("route-undo").addEventListener("click", () => {
    routePoints.pop();
    routeGraded = false;
    if (routeHilites) { map.removeLayer(routeHilites); routeHilites = null; }
    if (routePoints.length) drawRoute(); 
    else clearRoute();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && routeMode) setRouteMode(false);
  });

  // ── Boot ───────────────────────────────────────────────────────────────────

  updateDateLabel(parseInt(document.getElementById("date-filter").value, 10));
  loadIncidents();
})();
