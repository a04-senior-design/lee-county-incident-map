(() => {
  const LEE_COUNTY_CENTER = [26.56, -82];
  const DEFAULT_ZOOM = 11;
  const BASE_INTERVAL_MS = 2000; // time per frame at 1x speed
  // backend/api (leecad_api); this page must be served from one of its ALLOWED_ORIGINS
  const API_BASE = "https://leecountyincidentmap.com/api/v1";

  // Lee County boundary, copied from the React frontend (Map.jsx LEECOUNTY_BOUNDARY)
  const LEE_COUNTY_BOUNDARY = [
    [26.78980006125687, -82.272362941444],
    [26.789845555613542, -82.26674734260132],
    [26.78506785591573, -82.24039974363203],
    [26.784682327821244, -82.23903842851749],
    [26.78466547444208, -82.2389791674873],
    [26.7820416567969, -82.22592358399687],
    [26.782041344440042, -82.2232956474719],
    [26.771383695762992, -82.20659552905133],
    [26.771385640979, -82.20647976655594],
    [26.771392588357518, -82.20606614853668],
    [26.771432134382756, -82.20371036771571],
    [26.771451667543054, -82.20254589924075],
    [26.771455409378866, -82.20232270862869],
    [26.770580132044987, -82.06111276257575],
    [26.769557491947527, -81.56583524283978],
    [26.422579371979108, -81.56212541999152],
    [26.42121661767304, -81.65945294404435],
    [26.317535087331482, -81.65801989377533],
    [26.316233491651623, -81.81902174232401],
    [26.330254811084547, -81.84588796417505],
    [26.329835733418385, -82.2449563152756],
    [26.419874753315746, -82.33457334444688],
    [26.6450848069833, -82.42798337825371],
    [26.736154829652275, -82.43157338143331],
    [26.788130900846568, -82.46253412522209],
    [26.78980006125687, -82.272362941444],
  ];
  const LEE_COUNTY_BOUNDS = L.latLngBounds(LEE_COUNTY_BOUNDARY);
  // pan limit: the county bounds plus a margin, so incidents and heat map overlays at the edges can be centered and viewed
  const MAP_PAN_BOUNDS = LEE_COUNTY_BOUNDS.pad(0.25);

  // preferCanvas: cluster frames draw many circle markers.
  // maxBounds + viscosity 1 and minZoom keep the user near Lee County (slightly padded so edges are viewable).
  const map = L.map("map", {
    preferCanvas: true,
    minZoom: 9.5,
    maxBounds: MAP_PAN_BOUNDS,
    maxBoundsViscosity: 1.0,
    // finer zoom: fractional zoom levels, and smaller steps for the +/- buttons and mouse wheel
    zoomSnap: 0.25,
    zoomDelta: 0.5,
    wheelPxPerZoomLevel: 30,
  }).setView(LEE_COUNTY_CENTER, DEFAULT_ZOOM);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  // red county outline, and a dark mask over everything outside it (as in the React map)
  L.polygon(LEE_COUNTY_BOUNDARY, {color: "red", weight: 3, fill: false, interactive: false}).addTo(map);
  L.polygon(
    [[[89, -179], [89, 179], [-89, 179], [-89, -179], [89, -179]], LEE_COUNTY_BOUNDARY],
    {fillColor: "black", fillOpacity: 0.4, stroke: false, interactive: false}
  ).addTo(map);

  // ── Light / dark theme: html.light switches the CSS variables; choice is remembered ──
  const themeToggle = document.getElementById("theme-toggle");
  function syncThemeButton() {
    const light = document.documentElement.classList.contains("light");
    themeToggle.textContent = light ? "\u263E Dark" : "\u2600 Light";
  }
  themeToggle.addEventListener("click", () => {
    const light = document.documentElement.classList.toggle("light");
    try { localStorage.setItem("lab-theme", light ? "light" : "dark"); } catch (e) {}
    syncThemeButton();
  });
  syncThemeButton();

  // ── Date range picker (same behavior as the React DatePicker: range, presets, max today, clearable) ──
  const pad = n => String(n).padStart(2, "0");
  const fmt = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parse = str => { const [y, m, d] = str.split("-").map(Number); return new Date(y, m - 1, d); };
  const todayDate = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate());
  const todayStr = fmt(todayDate);
  const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];

  let dateRange = [null, null];                 // committed range (what Apply sends); empty until picked
  let draft = [...dateRange];                    // range being picked in the popover
  let viewMonth = parse(draft[0] || todayStr);
  viewMonth.setDate(1);

  const dateInput = document.getElementById("input-date-range");
  const dateWrap = document.getElementById("date-range-wrap");
  const datePopover = document.getElementById("date-popover");
  const dateCalendar = document.getElementById("date-calendar");
  const datePresets = document.getElementById("date-presets");

  const todayDateDefault = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate() - 2); 
  const todayDefaultStr = fmt(todayDateDefault)
  function shiftDays(n) { const d = new Date(todayDate); d.setDate(d.getDate() - n); return d; }
  function shiftDefaultDays(n) { const d = new Date(todayDateDefault); d.setDate(d.getDate() - n); return d; }
  const DATE_PRESETS = [
    // {label: "Last two days", value: [fmt(shiftDays(2)), todayStr]},
    {label: "Last 7 days",   value: [fmt(shiftDays(7)), todayStr]},
    {label: "This month",    value: [fmt(new Date(todayDate.getFullYear(), todayDate.getMonth(), 1)), todayStr]},
    {label: "Last month",    value: [
      fmt(new Date(todayDate.getFullYear(), todayDate.getMonth() - 1, 1)),
      fmt(new Date(todayDate.getFullYear(), todayDate.getMonth(), 0))]},
    {label: "Last year",     value: [
      fmt(new Date(todayDate.getFullYear() - 1, 0, 1)),
      fmt(new Date(todayDate.getFullYear() - 1, 11, 31))]},
  ];

  // hour/minute for each end of the range; start defaults to 00:00, end to 23:59 (an end of 00:00 would
  // exclude the last day of the range)
  const defaultTimes = {start: {hour: 0, minute: 0}, end: {hour: 23, minute: 59}};
  const times = {start: {...defaultTimes.start}, end: {...defaultTimes.end}};
  const timeStr = t => `${pad(t.hour)}:${pad(t.minute)}`;
  const withTime = (dateStr, which) => dateStr ? `${dateStr} ${timeStr(times[which])}` : "";
  // the input only shows a time when it isn't the default
  const label = (dateStr, which) => !dateStr ? "" :
    (times[which].hour !== defaultTimes[which].hour || times[which].minute !== defaultTimes[which].minute) ? withTime(dateStr, which) : dateStr;

  for (const row of document.querySelectorAll("#date-times .time-row")) {
    const which = row.dataset.which;
    const hourSel = row.querySelector(".time-hour");
    const minuteSel = row.querySelector(".time-minute");
    for (let i = 0; i < 24; i++) hourSel.add(new Option(pad(i), i));
    for (let i = 0; i < 60; i++) minuteSel.add(new Option(pad(i), i));
    hourSel.value = defaultTimes[which].hour;
    minuteSel.value = defaultTimes[which].minute;
    hourSel.addEventListener("change", () => { times[which].hour = Number(hourSel.value); updateDateInput(); });
    minuteSel.addEventListener("change", () => { times[which].minute = Number(minuteSel.value); updateDateInput(); });
  }

  function updateDateInput() {
    const [start, end] = draft;
    dateInput.value = start ? `${label(start, "start")} – ${label(end, "end")}` : "";
    dateWrap.classList.toggle("has-value", Boolean(start || end));
  }

  function resetTimes() {
    for (const row of document.querySelectorAll("#date-times .time-row")) {
      const d = defaultTimes[row.dataset.which];
      times[row.dataset.which] = {...d};
      row.querySelector(".time-hour").value = d.hour;
      row.querySelector(".time-minute").value = d.minute;
    }
  }

  // commit only a complete range, or a cleared one
  function setDraft(value) {
    draft = value;
    if ((draft[0] && draft[1]) || (!draft[0] && !draft[1])) {
      dateRange = [...draft];
    }
    updateDateInput();
    renderCalendar();
  }

  function renderCalendar() {
    const year = viewMonth.getFullYear();
    const month = viewMonth.getMonth();
    const [start, end] = draft;
    const nextDisabled = new Date(year, month + 1, 1) > todayDate;
    const nextYearDisabled = new Date(year + 1, month, 1) > todayDate;

    let html = `<div class="cal-header">
      <span class="cal-nav">
        <button type="button" data-nav="-12" title="Previous year" aria-label="Previous year">&laquo;</button>
        <button type="button" data-nav="-1" title="Previous month" aria-label="Previous month">&#9664;</button>
      </span>
      <span>${MONTHS[month]} ${year}</span>
      <span class="cal-nav">
        <button type="button" data-nav="1" title="Next month" aria-label="Next month" ${nextDisabled ? "disabled" : ""}>&#9654;</button>
        <button type="button" data-nav="12" title="Next year" aria-label="Next year" ${nextYearDisabled ? "disabled" : ""}>&raquo;</button>
      </span>
    </div><div class="cal-grid">`;

    for (const dow of ["Su","Mo","Tu","We","Th","Fr","Sa"]) html += `<div class="cal-dow">${dow}</div>`;

    const first = new Date(year, month, 1);
    const gridStart = new Date(year, month, 1 - first.getDay());
    for (let i = 0; i < 42; i++) {
      const d = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + i);
      const str = fmt(d);
      const cls = ["cal-day"];
      if (d.getMonth() !== month) cls.push("outside");
      if (start && end && str > start && str < end) cls.push("in-range");
      if (str === start) cls.push("selected", "range-start");
      if (str === end) cls.push("selected", "range-end");
      html += `<button type="button" class="${cls.join(" ")}" data-date="${str}" ${d > todayDate ? "disabled" : ""}>${d.getDate()}</button>`;
    }
    dateCalendar.innerHTML = html + "</div>";
  }

  function pickDay(str) {
    const [start, end] = draft;
    if (!start || end) {
      setDraft([str, null]);                      // start a new range
    } else {
      setDraft(str < start ? [str, start] : [start, str]);
    }
  }

  function openDatePopover() { datePopover.classList.remove("hidden"); }
  function closeDatePopover() {
    datePopover.classList.add("hidden");
    // an unfinished range falls back to the last committed one
    if (draft[0] && !draft[1]) { draft = [...dateRange]; updateDateInput(); renderCalendar(); }
  }

  for (const preset of DATE_PRESETS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = preset.label;
    btn.addEventListener("click", () => {
      viewMonth = parse(preset.value[0]); viewMonth.setDate(1);
      setDraft([...preset.value]);
    });
    datePresets.appendChild(btn);
  }

  dateInput.addEventListener("click", () => {
    openDatePopover();
  });
  document.getElementById("date-range-clear").addEventListener("click", () => {
    resetTimes();
    setDraft([null, null]);
  });
  dateCalendar.addEventListener("click", e => {
    const nav = e.target.closest("[data-nav]");
    if (nav) {
      viewMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() + Number(nav.dataset.nav), 1);
      renderCalendar();
      return;
    }
    const day = e.target.closest("[data-date]");
    if (day && !day.disabled) pickDay(day.dataset.date);
  });
  // mousedown, not click: a day click re-renders the calendar, so by the time a document "click"
  // handler ran, e.target was detached and looked like an outside click
  document.addEventListener("mousedown", e => {
    if (!document.getElementById("date-range-field").contains(e.target)) closeDatePopover();
  });

  updateDateInput();
  renderCalendar();

  // read the time-window inputs (shared by Cluster Analysis, KDE all points, and Gi*);
  // returns the params, plus the labels of any blank fields
  function readWindowParams() {
    const params = {
      start_date: withTime(dateRange[0], "start"),
      end_date: withTime(dateRange[1], "end"),
      window_length: document.getElementById("input-window-length").value.trim(),
      time_step: document.getElementById("input-time-step").value.trim(),
    };

    const labels = {
      start_date: "start date",
      end_date: "end date",
      window_length: "window size",
      time_step: "time step",
    };

    const missing = [];
    for (const key in params) {
      if (params[key] === "") {
        missing.push(labels[key]);
      }
    }

    return {params, missing};
  }

  // ── Incident type multi-select: "All incident types", or any of the categories from /incident-types ──
  const categoryToggle = document.getElementById("category-toggle");
  const categorySummary = document.getElementById("category-summary");
  const categoryPopover = document.getElementById("category-popover");
  const categoryAll = document.getElementById("category-all");
  const categoryOptions = document.getElementById("category-options");

  // the checkboxes for each category (value = category code), once loaded
  function categoryCheckboxes() {
    return categoryOptions.querySelectorAll("input[type=checkbox]");
  }

  // the selected category codes; empty means all incident types (no category param is sent)
  function selectedCategories() {
    if (categoryAll.checked) return [];
    const codes = [];
    for (const box of categoryCheckboxes()) {
      if (box.checked) codes.push(box.value);
    }
    return codes;
  }

  // the button text: "All incident types", the one selected label, or a count
  function updateCategorySummary() {
    const checked = [...categoryCheckboxes()].filter(box => box.checked);
    if (categoryAll.checked || checked.length === 0) {
      categorySummary.textContent = "All incident types";
    }
    else if (checked.length === 1) {
      categorySummary.textContent = checked[0].dataset.label;
    }
    else {
      categorySummary.textContent = `${checked.length} incident types`;
    }
  }

  // build one checkbox per category, showing its label
  async function loadIncidentTypes() {
    try {
      const res = await fetch(`${API_BASE}/incident-types`);
      if (!res.ok) throw new Error(`incident-types returned ${res.status}`);
      const body = await res.json();

      categoryOptions.innerHTML = "";
      for (const type of body.types) {
        const option = document.createElement("label");
        option.className = "category-option";
        const box = document.createElement("input");
        box.type = "checkbox";
        box.value = type.code;
        box.dataset.label = type.label;
        option.append(box, type.label);
        categoryOptions.appendChild(option);
      }
    }
    catch (err) {
      // the animation still works with all incident types
      categoryOptions.innerHTML = '<div class="category-message">Could not load incident types</div>';
      console.error(err);
    }
  }

  // "All" clears the individual picks
  categoryAll.addEventListener("change", () => {
    if (categoryAll.checked) {
      for (const box of categoryCheckboxes()) box.checked = false;
    }
    else if (selectedCategories().length === 0) {
      // nothing else picked, so "All" stays on
      categoryAll.checked = true;
    }
    updateCategorySummary();
  });

  // picking a category turns "All" off; unpicking the last one turns it back on
  categoryOptions.addEventListener("change", () => {
    const anyChecked = [...categoryCheckboxes()].some(box => box.checked);
    categoryAll.checked = !anyChecked;
    updateCategorySummary();
  });

  function setCategoryPopoverOpen(open) {
    categoryPopover.classList.toggle("hidden", !open);
    categoryToggle.setAttribute("aria-expanded", String(open));
  }
  categoryToggle.addEventListener("click", () => {
    setCategoryPopoverOpen(categoryPopover.classList.contains("hidden"));
  });
  document.addEventListener("mousedown", e => {
    if (!document.getElementById("category-field").contains(e.target)) setCategoryPopoverOpen(false);
  });

  loadIncidentTypes();

  // show the bandwidth value next to its label as the slider moves
  const bandwidthInput = document.getElementById("input-bandwidth");
  const bandwidthValue = document.getElementById("bandwidth-value");
  bandwidthInput.addEventListener("input", () => {
    bandwidthValue.textContent = bandwidthInput.value;
  });

  // show the distance band value next to its label as the slider moves
  const distanceBandInput = document.getElementById("input-distance-band");
  const distanceBandValue = document.getElementById("distance-band-value");
  distanceBandInput.addEventListener("input", () => {
    distanceBandValue.textContent = distanceBandInput.value;
  });

  const kdeLevelSlidersContainer = document.getElementById("kde-heatmap-level-sliders");
  const kdeLevelHint = document.getElementById("kde-heatmap-level-hint");

  // build one slider per cluster level; level 0 (loosest / least-dense) first;
  // clusterLevels is the response's cluster_levels: bandwidths[i] is for cluster level clusterLevels[i]
  function buildKDEHeatmapLevelSliders(bandwidths, clusterLevels, minBandwidth, maxBandwidth) {
    kdeLevelSlidersContainer.innerHTML = "";

    // each slider's cluster density category name, e.g. "District";
    // the run's categories are listed loosest first, so cluster level n is dbscanRunTiers[n]
    const sliderNames = [];
    for (let i = 0; i < bandwidths.length; i++) {
      let name = `Level ${i}`; // no cluster_levels in the response: label by position
      if (clusterLevels) {
        const level = clusterLevels[i];
        const tier = dbscanRunTiers[level];
        if (tier) {
          name = LEVEL_LABELS[tier];
        }
        else {
          name = `Level ${level}`;
        }
      }
      sliderNames.push(name);
    }

    for (let i = 0; i < bandwidths.length; i++) {
      const row = document.createElement("div");
      row.className = "field-row";
      row.innerHTML = `
        <label for="input-level-bandwidth-${i}">${sliderNames[i]} bandwidth: <span class="slider-value">${bandwidths[i]}</span> ft</label>
        <input id="input-level-bandwidth-${i}" class="level-bandwidth" type="range"
          min="${minBandwidth}" max="${maxBandwidth}" step="100" value="${bandwidths[i]}" />
      `;
      kdeLevelSlidersContainer.appendChild(row);
    }

    const sliders = kdeLevelSlidersContainer.querySelectorAll(".level-bandwidth");
    for (let i = 0; i < sliders.length; i++) {
      sliders[i].addEventListener("input", () => {
        let value = parseFloat(sliders[i].value);

        // can't go above the previous level's bandwidth
        if (i > 0) {
          const previous = parseFloat(sliders[i - 1].value);
          value = Math.min(value, previous);
        }
        // can't go below the next level's bandwidth
        if (i < sliders.length - 1) {
          const next = parseFloat(sliders[i + 1].value);
          value = Math.max(value, next);
        }

        sliders[i].value = value;
        sliders[i].previousElementSibling.querySelector(".slider-value").textContent = value;
      });
    }

    // e.g. "Constraint: District >= Neighborhood >= Street"
    kdeLevelHint.textContent = `Constraint: ${sliderNames.join(" \u2265 ")}`;
  }

  // remove the sliders, so the next Apply sends no bandwidths and gets the defaults
  function removeKDEHeatmapLevelSliders() {
    kdeLevelSlidersContainer.innerHTML = "";
    kdeLevelHint.textContent = "Click Apply to load frame 1's cluster levels.";
  }

  // replace each list of cluster level numbers in a backend error message, e.g. "[0, 1, 2]",
  // with the Cluster Analysis run's category names, e.g. "[District, Neighborhood, Street]";
  // a list with a level the run has no category for is left as it is
  function nameClusterLevelsInMessage(message) {
    return message.replace(/\[([\d,\s]+)\]/g, (match, numbersText) => {
      const names = [];
      for (const part of numbersText.split(",")) {
        const level = Number(part.trim());
        const tier = dbscanRunTiers[level];
        if (!tier) {
          return match;
        }
        names.push(LEVEL_LABELS[tier]);
      }
      return `[${names.join(", ")}]`;
    });
  }


  // ── Cluster Analysis (DBSCAN) rendering, from animation-lab ─────────────
  // District drawn first (bottom), neighborhood middle, street on top
  const LEVEL_DRAW_ORDER = ["district", "neighborhood", "street"];
  const LEVEL_LABELS = { district: "District", neighborhood: "Neighborhood", street: "Street" };
  const LEVEL_STYLES = {
    district:     { fillOpacity: 0.1,  weight: 1,   opacity: 0.5,  pointRadius: 4, noiseRadius: 2 },
    neighborhood: { fillOpacity: 0.16, weight: 1.5, opacity: 0.7,  pointRadius: 6, noiseRadius: 3 },
    street:       { fillOpacity: 0.28, weight: 2,   opacity: 0.85, pointRadius: 8, noiseRadius: 4 },
  };

  // Same per-level epsilon ranges as cluster-lab.html: min_pts is a fixed
  // backend constant (4), not user-adjustable; only epsilon changes with the
  // slider. slider=0 (Sparse) -> large eps (few big clusters), slider=100
  // (Dense) -> small eps (many tight clusters).
  const LEVEL_PRESETS = {
    district:     { epsMax: 30000, epsMin: 10000, defaultEps: 20000 },
    neighborhood: { epsMax: 9990,  epsMin: 3000,  defaultEps: 6500  },
    street:       { epsMax: 2990,  epsMin: 300,   defaultEps: 1700  },
  };

  const levelEnabled = { district: true, neighborhood: true, street: true };

  let currentClusterLayer = null; // the cluster frame's L.layerGroup on the map, if any
  let clusterLegendControl = null;
  let legendCollapsed = false; // kept across frames, since the legend is rebuilt for each one

  function levelChildrenGroup(levelName, geojson) {
    const st = LEVEL_STYLES[levelName];
    const polygons = geojson.features.filter(f => f.properties.feature_type === "polygon");
    const points   = geojson.features.filter(f => f.properties.feature_type === "point");
    const group = L.layerGroup();

    L.geoJSON({ type: "FeatureCollection", features: polygons }, {
      style: feature => ({
        fillColor: feature.properties.color,
        color:     feature.properties.color,
        fillOpacity: st.fillOpacity,
        weight:      st.weight,
        opacity:     st.opacity,
      }),
      onEachFeature: (feature, layer) => {
        layer.bindTooltip(
          `[${LEVEL_LABELS[levelName]}] Cluster ${feature.properties.cluster_id} — ${feature.properties.point_count} incidents`,
          { sticky: true }
        );
      },
    }).addTo(group);

    L.geoJSON({ type: "FeatureCollection", features: points }, {
      pointToLayer: (feature, latlng) =>
        L.circleMarker(latlng, {
          radius:      feature.properties.cluster_id === -1 ? st.noiseRadius : st.pointRadius,
          fillColor:   feature.properties.color,
          color:       "#fff",
          weight:      0.5,
          fillOpacity: feature.properties.cluster_id === -1 ? 0.35 : 0.85,
        }),
      onEachFeature: (feature, layer) => {
        const label = feature.properties.cluster_id === -1
          ? `[${LEVEL_LABELS[levelName]}] Noise`
          : `[${LEVEL_LABELS[levelName]}] Cluster ${feature.properties.cluster_id}`;
        layer.bindTooltip(label, { sticky: true });
      },
    }).addTo(group);

    return group;
  }

  function buildClusterLegend(snapshot) {
    const sections = LEVEL_DRAW_ORDER
      .filter(levelName => snapshot.levels[levelName])
      .map(levelName => {
        const polygons = snapshot.levels[levelName].features.filter(f => f.properties.feature_type === "polygon");
        if (!polygons.length) return "";
        const rows = polygons
          .map(f =>
            `<div><span class="legend-swatch" style="background:${f.properties.color}"></span>` +
            `Cluster ${f.properties.cluster_id} — ${f.properties.point_count} pts</div>`
          ).join("");
        return `<div style="margin-bottom:0.4rem"><strong style="font-size:0.7rem;color:var(--text-sub);text-transform:uppercase;letter-spacing:0.05em">${LEVEL_LABELS[levelName]}</strong>${rows}</div>`;
      })
      .join("");

    if (!sections.replace(/<[^>]*>/g, "").trim()) return;

    clusterLegendControl = L.control({ position: "bottomright" });
    clusterLegendControl.onAdd = () => {
      const div = L.DomUtil.create("div", "cluster-legend");
      div.classList.toggle("collapsed", legendCollapsed);
      div.innerHTML = `<button type="button" class="legend-toggle" aria-expanded="${!legendCollapsed}">
        <span>Legend</span><span class="legend-chevron">&#9660;</span></button>
        <div class="legend-body">${sections}</div>`;
      div.querySelector(".legend-toggle").addEventListener("click", e => {
        legendCollapsed = !legendCollapsed;
        div.classList.toggle("collapsed", legendCollapsed);
        e.currentTarget.setAttribute("aria-expanded", String(!legendCollapsed));
      });
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);
      return div;
    };
    clusterLegendControl.addTo(map);
  }

  // per-level Clusters / Noise pills; pass null to reset them to dashes
  function updateClusterLevelStats(snapshot) {
    LEVEL_DRAW_ORDER.forEach(levelName => {
      const meta = snapshot && snapshot.levels[levelName] && snapshot.levels[levelName].metadata;
      document.getElementById(`anim-stat-clusters-${levelName}`).textContent = meta ? meta.n_clusters : "—";
      document.getElementById(`anim-stat-noise-${levelName}`).textContent = meta ? meta.n_noise : "—";
    });
  }

  function clearClusterLayer() {
    if (currentClusterLayer) {
      map.removeLayer(currentClusterLayer);
      currentClusterLayer = null;
    }
    if (clusterLegendControl) {
      clusterLegendControl.remove();
      clusterLegendControl = null;
    }
  }

  // slider value is in feet, stepping 100 ft; Sparse (left) = epsMax, Dense (right) = epsMin
  function levelToParams(levelName, sliderVal) {
    const p = LEVEL_PRESETS[levelName];
    return { eps: p.epsMax + p.epsMin - sliderVal };
  }

  function resetLevelSlider(slider) {
    const p = LEVEL_PRESETS[slider.dataset.level];
    slider.min = p.epsMin;
    slider.max = p.epsMax;
    slider.step = 10;
    // the slider is inverted (see levelToParams), so start it where eps === defaultEps
    slider.value = p.epsMax + p.epsMin - p.defaultEps;
  }

  // show each level's current epsilon under its slider
  function updateEpsLabel(slider) {
    const level = slider.dataset.level;
    document.getElementById(`anim-eps-${level}`).textContent =
      levelToParams(level, Number(slider.value)).eps.toLocaleString();
  }
  document.querySelectorAll(".level-slider").forEach(slider => {
    resetLevelSlider(slider);
    updateEpsLabel(slider);
    slider.addEventListener("input", () => updateEpsLabel(slider));
  });

  document.querySelectorAll(".level-toggle").forEach(checkbox => {
    checkbox.addEventListener("change", () => {
      const levelName = checkbox.dataset.level;
      levelEnabled[levelName] = checkbox.checked;
      document.getElementById(`level-block-${levelName}`).classList.toggle("level-off", !checkbox.checked);
    });
  });


  let currentHeatmapOverlay = null; // the KDE or Gi* heat map image on the map, if any
  let heatmapLegendControl = null; // the KDE or Gi* heat map legend on the map, if any

  const applyBtn = document.getElementById("animation-apply");
  const resetBtn = document.getElementById("dbscan-reset");
  const errorLabel = document.getElementById("animation-error");
  // playback state
  let frames = []; // frames from the last Apply (cluster snapshots, or KDE or Gi* heat map frames)
  let frameIndex = 0; // frame currently shown
  let playing = false; // true while the animation is running
  let timer = null; // the interval that advances frames
  let speed = 1; // 0.5, 1, 2 or 4

  const scrub = document.getElementById("scrub");
  const frameLabel = document.getElementById("frame-label");
  // set the frame label's text; long labels are cut off with "...", so the full text
  // is also put in the browser's built-in tooltip (title), shown when the user hovers over the label
  function setFrameLabel(text) {
    frameLabel.textContent = text;
    frameLabel.title = text;
  }
  const statFrame = document.getElementById("stat-frame");
  const statBandwidth = document.getElementById("stat-bandwidth");
  const statDistanceBand = document.getElementById("stat-distance-band");
  // the Bandwidth pill shows in the KDE modes, the Distance band pill in Gi* mode, and neither in Cluster Analysis
  const bandwidthPill = document.getElementById("bandwidth-pill");
  const distanceBandPill = document.getElementById("distance-band-pill");
  const playBtn = document.getElementById('btn-play');
  // "clusters" (DBSCAN snapshots), "gistar-heatmap" (Gi* heat map, time windows, one distance band),
  // or the two KDE heat map modes: "all-points" (time windows, one bandwidth) or "cluster-levels" (the Cluster Analysis run)
  let analysisMode = "all-points";
  const animationControls = document.getElementById("animation-controls");
  const modeRadios = document.querySelectorAll('input[name="analysis-mode"]');

  // a tick value as label text: whole numbers from 100 up, otherwise 2 significant digits
  function formatTick(value) {
    if (Math.abs(value) >= 100) {
      return String(Math.round(value));
    }
    return String(Number(value.toPrecision(2)));
  }

  // remove the KDE or Gi* heat map legend from the map, if there is one
  function removeHeatmapLegend() {
    if (heatmapLegendControl) {
      heatmapLegendControl.remove();
      heatmapLegendControl = null;
    }
  }

  // add the heat map legend (caption, color bar, tick labels) to the map's bottom-right corner;
  // legend is the "legend" object from the animation response;
  // openEnded = true labels the min and max as "<= min" and ">= max", for a scale whose ends
  // also cover every value beyond them (Gi*: z-scores past the scale get its end colors)
  function buildHeatmapLegend(legend, openEnded = false) {
    removeHeatmapLegend();

    // no legend in the response - nothing to show
    if (!legend) {
      return;
    }

    let caption = legend.caption;
    if (!caption) {
      caption = "Incident density";
    }

    // the color bar, vmin on the left to vmax on the right
    const gradientCss = `linear-gradient(to right, ${legend.colors.join(", ")})`;

    // place each tick label at its value along the bar, so it lines up with its color
    const range = legend.vmax - legend.vmin;
    const MIN_GAP_PERCENT = 10; // in-between ticks closer than this to the min or max label would overlap it
    let tickLabels = "";

    for (let i = 0; i < legend.ticks.length; i++) {
      const tick = legend.ticks[i];
      let percent = 0;
      if (range > 0) {
        percent = ((tick - legend.vmin) / range) * 100;
      }

      // the min and max labels (always the first and last ticks) are always shown
      // skip an in-between tick that would overlap them
      const isEndTick = (i === 0 || i === legend.ticks.length - 1);
      const tooCloseToEnd = (percent < MIN_GAP_PERCENT || percent > 100 - MIN_GAP_PERCENT);
      if (!isEndTick && tooCloseToEnd) {
        continue;
      }

      // open-ended scale: the min label covers everything below it, the max label everything above it
      let labelText = formatTick(tick);
      if (openEnded && i === 0) {
        labelText = `\u2264 ${labelText}`;
      }
      else if (openEnded && i === legend.ticks.length - 1) {
        labelText = `\u2265 ${labelText}`;
      }

      tickLabels += `<span style="left: ${percent}%">${labelText}</span>`;
    }

    heatmapLegendControl = L.control({position: "bottomright"});
    heatmapLegendControl.onAdd = () => {
      const div = L.DomUtil.create("div", "heatmap-legend");
      div.innerHTML = `
        <div class="heatmap-legend-caption">${caption}</div>
        <div class="heatmap-legend-bar" style="background: ${gradientCss};"></div>
        <div class="heatmap-legend-ticks">${tickLabels}</div>
      `;
      return div;
    };
    heatmapLegendControl.addTo(map);
  }

  // stop playback and remove the current frames, overlays and labels
  function clearAnimation() {
    pause();
    frames = [];
    frameIndex = 0;
    scrub.max = 0;
    scrub.value = 0;
    setFrameLabel("—");
    statFrame.textContent = "—";
    statBandwidth.textContent = "—";
    statDistanceBand.textContent = "—";

    if (currentHeatmapOverlay) {
      map.removeLayer(currentHeatmapOverlay);
      currentHeatmapOverlay = null;
    }
    removeHeatmapLegend();
    clearClusterLayer();
    updateClusterLevelStats(null);
  }

  // switching analysis: show that mode's fields and clear the old animation; Apply builds the new one
  for (const radio of modeRadios) {
    radio.addEventListener("change", () => {
      analysisMode = radio.value;
      animationControls.dataset.mode = analysisMode;
      // show the pill for the current mode's slider parameter (Cluster Analysis has none)
      if (analysisMode === "clusters") {
        bandwidthPill.hidden = true;
        distanceBandPill.hidden = true;
      }
      else if (analysisMode === "gistar-heatmap") {
        bandwidthPill.hidden = true;
        distanceBandPill.hidden = false;
      }
      else {
        // the two KDE modes
        bandwidthPill.hidden = false;
        distanceBandPill.hidden = true;
      }
      clearAnimation();
      errorLabel.textContent = "";
      // the controls bar's height changed (or it was hidden), so Leaflet re-measures the map
      map.invalidateSize();
    });
  }

  // the cluster-levels radio, and whether its Cluster Analysis run can be used (checked on page load
  // and after every Cluster Analysis Apply, since that makes a new run)
  const clusterLevelsRadio = document.querySelector('input[name="analysis-mode"][value="cluster-levels"]');
  const clusterLevelsLabel = clusterLevelsRadio.parentElement;
  let clusterLevelsAvailable = true;
  // the DBSCAN run from the last Cluster Analysis Apply; the KDE cluster-level routes use its results
  let dbscanRunId = null;

  // that run's enabled cluster density categories, loosest first (e.g. ["district", "street"])
  // DBSCAN numbers the cluster levels in this order, so level n is dbscanRunTiers[n]
  let dbscanRunTiers = [];

  // enable or disable the analysis radios and buttons (disabled while a request is running)
  function setControlsDisabled(disabled) {
    for (const radio of modeRadios) {
      radio.disabled = disabled;
    }
    // the cluster-levels radio stays disabled while the Cluster Analysis run can't be used
    if (!clusterLevelsAvailable) {
      clusterLevelsRadio.disabled = true;
    }
    applyBtn.disabled = disabled;
    applyBtn.textContent = disabled ? "Loading…" : "Apply";
    resetBtn.disabled = disabled;
  }

  // ask the backend whether the Cluster Analysis run can be used; enable or disable the cluster-levels radio
  async function checkDBSCANRun() {
    // no Cluster Analysis run yet, so there's nothing to ask about
    let dbscanStatus = "missing";
    if (dbscanRunId) {
      const res = await fetch(`${API_BASE}/animation/kde-heatmap-dbscan/status?run_id=${dbscanRunId}`);
      const body = await res.json();
      dbscanStatus = body.dbscan_status;
    }

    clusterLevelsAvailable = (dbscanStatus === "available");
    clusterLevelsRadio.disabled = !clusterLevelsAvailable;
    clusterLevelsLabel.classList.toggle("unavailable", !clusterLevelsAvailable);

    // tooltip on hover explains why
    if (clusterLevelsAvailable) {
      clusterLevelsLabel.title = "";
    }
    else if (dbscanStatus === "missing") {
      clusterLevelsLabel.title = "No Cluster Analysis results found (none run yet, or they expired). Run Cluster Analysis first.";
    }
    else {
      clusterLevelsLabel.title = "Frame 1 has no cluster levels (empty or all noise). Rerun Cluster Analysis with different settings.";
    }
  }

  // draw a KDE or Gi* heat map frame: its heat map (if any) and label
  function renderHeatmapFrame(frame) {
    // remove the previous frame's overlay
    if (currentHeatmapOverlay) {
      map.removeLayer(currentHeatmapOverlay);
      currentHeatmapOverlay = null;
    }

    // empty window: no image, just the label
    if (frame.image !== null) {
      // Leaflet wants [[south, west], [north, east]]
      const bounds = [
        [frame.bounds.south, frame.bounds.west],
        [frame.bounds.north, frame.bounds.east],
      ];
      currentHeatmapOverlay = L.imageOverlay(frame.image, bounds, {opacity: 0.8}).addTo(map);
    }

    // add the frame's note, if any (e.g. empty or all-noise frame)
    let labelText = `${frame.label} (${frame.n_incidents} incidents)`;
    if (frame.note) {
      labelText = `${labelText} — ${frame.note}`;
    }
    setFrameLabel(labelText);
  }

  // draw a cluster snapshot: each level's polygons/points in draw order, legend and level stats
  function renderClusterFrame(snapshot) {
    clearClusterLayer();

    const group = L.layerGroup();
    LEVEL_DRAW_ORDER.forEach(levelName => {
      if (!snapshot.levels[levelName]) return;
      levelChildrenGroup(levelName, snapshot.levels[levelName]).addTo(group);
    });
    currentClusterLayer = group.addTo(map);

    buildClusterLegend(snapshot);
    updateClusterLevelStats(snapshot);
    setFrameLabel(`${snapshot.label} (${snapshot.n_incidents} incidents)`);
  }

  // draw frame i with the current mode's renderer, and update the frame counter
  function renderFrame(i) {
    frameIndex = i;
    if (analysisMode === "clusters") {
      renderClusterFrame(frames[i]);
    }
    else {
      renderHeatmapFrame(frames[i]);
    }
    scrub.value = i;
    statFrame.textContent = `${i + 1} / ${frames.length}`;
  }

  // stop the animation and show the play symbol
  function pause() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    playing = false;
    playBtn.innerHTML = "&#9654;";
  }

  // advance one frame every BASE_INTERVAL_MS / speed, looping at the end
  function play() {
    if (timer || frames.length < 2) return;
    playing = true;
    playBtn.innerHTML = "&#10074;&#10074;"; // pause symbol
    timer = setInterval(() => {
      const count = frames.length;
      renderFrame((frameIndex + 1) % count);
    }, BASE_INTERVAL_MS / speed);
  }

  // change speed; if playing, restart the timer at the new interval
  function setSpeed(nextSpeed) {
    speed = nextSpeed;
    const buttons = document.querySelectorAll(".speed-btn");
    for (const btn of buttons) {
      const btnSpeed = parseFloat(btn.dataset.speed);
      if (btnSpeed === speed) {
        btn.classList.add("active");
      }
      else {
        btn.classList.remove("active");
      }
    }
    if (playing) {
      pause();
      play();
    }
  }

  // move forward or back by delta frames, wrapping around at either end
  function step(delta) {
    if (frames.length === 0) return;
    pause();
    const count = frames.length;
    renderFrame((frameIndex + delta + count) % count);
  }

  document.getElementById("btn-rewind").addEventListener("click", () => step(-1));
  document.getElementById("btn-forward").addEventListener("click", () => step(1));

  scrub.addEventListener("input", () => {
    if (frames.length === 0) return;
    pause();
    renderFrame(parseInt(scrub.value, 10));
  });

  playBtn.addEventListener("click", () => {
    if (playing) {
      pause();
    }
    else {
      play();
    }
  });

  document.querySelectorAll(".speed-btn").forEach(btn => {
    btn.addEventListener("click", () => setSpeed(parseFloat(btn.dataset.speed)));
  });

  /* build the request url for the current analysis mode; return {url} or {error} (stop before fetching);
   * for Cluster Analysis it also returns tiers, the enabled cluster density categories sent
   */
  function buildApplyRequest() {
    if (analysisMode === "cluster-levels") {
      // one "bandwidth" param per slider; no sliders yet (first Apply) means the backend uses its defaults
      const query = new URLSearchParams({run_id: dbscanRunId});
      const sliders = kdeLevelSlidersContainer.querySelectorAll(".level-bandwidth");
      for (const slider of sliders) {
        query.append("bandwidth", slider.value);
      }
      return {url: `${API_BASE}/animation/kde-heatmap-dbscan?${query.toString()}`};
    }

    // Cluster Analysis, KDE all points, and Gi*: the time-window fields are required
    const {params, missing} = readWindowParams();
    if (missing.length > 0) {
      return {error: `Enter a ${missing.join(", ")}.`};
    }

    // only the picked incident types; leaving category out means all of them
    const categories = selectedCategories();
    if (categories.length > 0) {
      params.category = categories.join(",");
    }

    if (analysisMode === "clusters") {
      // at least one level, with each enabled level's epsilon from its slider
      const enabledLevels = LEVEL_DRAW_ORDER.filter(levelName => levelEnabled[levelName]);
      if (!enabledLevels.length) {
        return {error: "Enable at least one cluster level"};
      }
      params.levels = enabledLevels.join(",");
      enabledLevels.forEach(levelName => {
        const sliderVal = Number(document.getElementById(`anim-slider-${levelName}`).value);
        const { eps } = levelToParams(levelName, sliderVal);
        params[`${levelName}_eps`] = eps;
      });
      return {url: `${API_BASE}/animation/dbscan?${new URLSearchParams(params).toString()}`, tiers: enabledLevels};
    }

    if (analysisMode === "gistar-heatmap") {
      // Gi*: one distance band from its slider
      params.distance_band = distanceBandInput.value;
      return {url: `${API_BASE}/animation/gi-star-heatmap?${new URLSearchParams(params).toString()}`};
    }

    // KDE all points: one bandwidth from its slider
    params.bandwidth = bandwidthInput.value;
    return {url: `${API_BASE}/animation/kde-heatmap?${new URLSearchParams(params).toString()}`};
  }

  async function applyAnimation() {
    // stop before touching the current animation if a field is missing
    const {url, error, tiers} = buildApplyRequest();
    if (error) {
      errorLabel.textContent = error;
      return;
    }
    // the mode this request is for (radios are disabled while it runs, but keep it explicit)
    const mode = analysisMode;

    // clear the previous animation before building a new one
    clearAnimation();
    errorLabel.textContent = "";

    // disable the buttons and the analysis radios while the snapshots are being built
    setControlsDisabled(true);

    try {
      const res = await fetch(url);
      const body = await res.json();

      if (!res.ok) {
        // the backend's message if it sent one, otherwise a general one for this mode
        let fallbackMessage = "Failed to load kde heat map snapshots";
        if (mode === "clusters") {
          fallbackMessage = "Failed to load DBSCAN snapshots";
        }
        else if (mode === "gistar-heatmap") {
          fallbackMessage = "Failed to load Gi* heat map snapshots";
        }
        let message = body.error || fallbackMessage;

        // "KDE (by cluster density level)" errors list levels as numbers, e.g. "[0, 1, 2]"; show category names instead
        if (mode === "cluster-levels") {
          try {
            message = nameClusterLevelsInMessage(message);
          }
          catch (err) {
            // keep the backend's message as it is if the names can't be filled in
            console.error(err);
          }
        }
        errorLabel.textContent = message;

        // e.g. the Cluster Analysis run changed and the slider count no longer matches frame 1
        if (mode === "cluster-levels") {
          removeKDEHeatmapLevelSliders();
        }
        return;
      }

      const newFrames = body.frames;
      console.log(`frames: ${newFrames.length}`);

      // keep all frames and show the first one
      frames = newFrames;
      scrub.max = Math.max(frames.length - 1, 0);
      if (frames.length > 0) {
        renderFrame(0);
      }
      else {
        setFrameLabel("No frames in this date range");
      }

      // the parameter value(s) the displayed snapshots were built with
      if (mode === "clusters") {
        // this Apply made a new DBSCAN run: the KDE cluster-level count may have changed,
        // so drop the old sliders (next cluster-levels Apply uses defaults) and recheck availability
        dbscanRunId = body.run_id;
        // the categories this run used, to name the "KDE Heat Map (by cluster density levels)" sliders
        dbscanRunTiers = tiers;
        removeKDEHeatmapLevelSliders();
        await checkDBSCANRun();
      }
      else if (mode === "cluster-levels") {
        statBandwidth.textContent = `${body.bandwidths.join(" / ")} ft`;
        // rebuild the sliders at the bandwidths the backend used (defaults on the first Apply)
        buildKDEHeatmapLevelSliders(body.bandwidths, body.cluster_levels, body.min_bandwidth, body.max_bandwidth);
        // one legend for every frame (they share one color scale)
        buildHeatmapLegend(body.legend);
      }
      else if (mode === "gistar-heatmap") {
        statDistanceBand.textContent = `${body.distance_band} ft`;
        // take the slider range from the backend
        distanceBandInput.min = body.min_distance_band;
        distanceBandInput.max = body.max_distance_band;
        // one legend for every frame (they share one -z_abs_max to +z_abs_max color scale);
        // open-ended: z-scores beyond the scale get its end colors
        buildHeatmapLegend(body.legend, true);
      }
      else {
        // KDE all points
        statBandwidth.textContent = `${body.bandwidth} ft`;
        // take the slider range from the backend
        bandwidthInput.min = body.min_bandwidth;
        bandwidthInput.max = body.max_bandwidth;
        // one legend for every frame (they share one color scale)
        buildHeatmapLegend(body.legend);
      }
    }
    catch (err) {
      // the API is unreachable, or the browser blocked it because this page's origin isn't in ALLOWED_ORIGINS
      errorLabel.textContent = `Could not reach the API at ${API_BASE} (page origin: ${location.origin})`;
      console.error(err);
    }
    finally {
      // runs after every return or error, so the buttons and radios always come back
      setControlsDisabled(false);
    }
  }

  applyBtn.addEventListener("click", applyAnimation);

  // Cluster Analysis reset: level toggles back on and sliders to the middle, then back to the
  // blank "Click Apply" state. The date/window fields are shared with KDE (all points) and Gi*, so they're kept.
  resetBtn.addEventListener("click", () => {
    document.querySelectorAll(".level-toggle").forEach(checkbox => {
      checkbox.checked = true;
      levelEnabled[checkbox.dataset.level] = true;
      document.getElementById(`level-block-${checkbox.dataset.level}`).classList.remove("level-off");
    });
    document.querySelectorAll(".level-slider").forEach(slider => { resetLevelSlider(slider); updateEpsLabel(slider); });
    errorLabel.textContent = "";
    clearAnimation();
  });

  checkDBSCANRun();
})();
