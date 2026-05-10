import { renderKpis, renderChart } from "./dashboard.js";
import { renderTruck } from "./truck3d.js";
import { BUSINESS, MAP, ROUTING } from "./config.js";
import { escapeHtml, formatCo2, formatCostFromKm, formatKpi, formatPct } from "./format.js";
import { loadTrend, renderMixChart, renderTrendChart } from "./trend.js";
import { roadSnap } from "./routing.js";
import { midpoint } from "./animation.js";

const urlParams = new URLSearchParams(window.location.search);
const token = urlParams.get("token") || window.MAPBOX_TOKEN || "";
const MapGL = token ? mapboxgl : maplibregl;
if (token) {
  mapboxgl.accessToken = token;
}

const state = {
  manifest: null,
  dateIndex: 0,
  baseline: null,
  optimized: null,
  current: "optimized",
  view: "overview",
  map: null,
  selectedCluster: null,
  routeMarkers: [],
  clusterMarkers: [],
  layers: {
    areas: false,
    trucks: true,
    stops: true,
    path: true,
  },
  chartMode: "route",
  detailTab: "products",
  routesQuery: "",
  routesSort: "distance",
  trendSeries: null,
  snapAbort: null,
  dashAnimation: null,
  snappedByCluster: new Map(),
  clusterMarkerById: new Map(),
};

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Cannot load ${path}`);
  return response.json();
}

function showToast(message, { tone = "error" } = {}) {
  const container = document.getElementById("toasts") || document.body;
  const toast = document.createElement("div");
  toast.className = `toast toast-${tone}`;
  toast.setAttribute("role", "status");
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.classList.add("visible"), 10);
  setTimeout(() => {
    toast.classList.remove("visible");
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

function syncUrl() {
  if (!state.manifest) return;
  const params = new URLSearchParams(window.location.search);
  const day = state.manifest.dates[state.dateIndex]?.date;
  if (day) params.set("day", day); else params.delete("day");
  if (state.current) params.set("scenario", state.current); else params.delete("scenario");
  if (state.view && state.view !== "overview") params.set("view", state.view); else params.delete("view");
  if (state.selectedCluster?.id != null) params.set("route", String(state.selectedCluster.id));
  else params.delete("route");
  const next = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState(null, "", next);
}

function readUrlState() {
  return {
    day: urlParams.get("day"),
    scenario: urlParams.get("scenario"),
    view: urlParams.get("view"),
    route: urlParams.get("route"),
  };
}

function setChartMode(mode) {
  state.chartMode = mode;
  document.querySelectorAll("[data-chart]").forEach((button) => {
    const isActive = button.dataset.chart === mode;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  document.querySelectorAll("[data-chart-panel]").forEach((panel) => {
    panel.classList.toggle("hidden", panel.dataset.chartPanel !== mode);
  });
  document.getElementById("chartTitle").textContent =
    mode === "trend" ? "Savings over time" : "Kilometers comparison";
  if (mode === "trend") refreshTrendChart();
}

function setDetailTab(tab) {
  state.detailTab = tab;
  document.querySelectorAll("[data-detail]").forEach((button) => {
    const isActive = button.dataset.detail === tab;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  document.querySelectorAll("[data-detail-panel]").forEach((panel) => {
    panel.classList.toggle("hidden", panel.dataset.detailPanel !== tab);
  });
}

async function refreshTrendChart() {
  if (!state.manifest) return;
  if (!state.trendSeries) {
    try {
      state.trendSeries = await loadTrend(state.manifest);
    } catch (error) {
      showToast(`Trend unavailable: ${error.message}`);
      return;
    }
  }
  renderTrendChart(document.getElementById("trendChart"), state.trendSeries);
}

function flashKpis() {
  const node = document.getElementById("kpis");
  if (!node) return;
  node.classList.remove("kpi-flash");
  void node.offsetWidth;
  node.classList.add("kpi-flash");
}

function routeCenter(cluster) {
  const avg = cluster.stops.reduce(
    (acc, stop) => {
      acc.lon += stop.lon;
      acc.lat += stop.lat;
      return acc;
    },
    { lon: 0, lat: 0 }
  );
  avg.lon /= cluster.stops.length || 1;
  avg.lat /= cluster.stops.length || 1;
  return avg;
}

function squaredDistance(a, b) {
  return (a.lon - b.lon) ** 2 + (a.lat - b.lat) ** 2;
}

function routeAnchor(cluster) {
  const stops = cluster.stops || [];
  if (!stops.length) {
    return [state.optimized.depot.lon, state.optimized.depot.lat];
  }
  const center = routeCenter(cluster);
  const stop = stops.reduce((best, candidate) => (
    squaredDistance(candidate, center) < squaredDistance(best, center) ? candidate : best
  ), stops[0]);
  return [stop.lon, stop.lat];
}

function clusterFeature(cluster) {
  const coordinates = routeAnchor(cluster);
  return {
    type: "Feature",
    properties: {
      id: cluster.id,
      color: cluster.color,
      stops: cluster.stops.length,
      km: cluster.distance_km,
    },
    geometry: { type: "Point", coordinates },
  };
}

function routeFeature(cluster) {
  return {
    type: "Feature",
    id: cluster.id,
    properties: {
      id: cluster.id,
      color: cluster.color,
    },
    geometry: {
      type: "LineString",
      coordinates: cluster.polyline || [],
    },
  };
}

function activePolyline(cluster) {
  return state.snappedByCluster.get(cluster.id) || cluster.polyline || [];
}

function truckPosition(cluster) {
  const poly = activePolyline(cluster);
  if (poly.length >= 2) return midpoint(poly);
  return routeAnchor(cluster);
}

function truckScaleForZoom(zoom) {
  for (const step of MAP.zoomScaleSteps) {
    if (zoom < step.max) return step.scale;
  }
  return 1;
}

function updateMapMarkerScale() {
  if (!state.map) return;
  const zoom = state.map.getZoom();
  const scale = truckScaleForZoom(zoom);
  const compact = zoom < MAP.compactZoomBelow;
  state.clusterMarkers.forEach((marker) => {
    const element = marker.getElement();
    element.style.setProperty("--truck-scale", scale);
    element.classList.toggle("compact", compact);
    element.style.display = state.layers.trucks ? "" : "none";
  });
  state.routeMarkers.forEach((marker) => {
    const element = marker.getElement();
    element.classList.toggle("compact", compact);
    element.style.display = state.layers.stops && !compact ? "" : "none";
  });
}

function clearRoute() {
  state.routeMarkers.forEach((marker) => marker.remove());
  state.routeMarkers = [];
  if (state.map?.getSource("selectedRoute")) {
    state.map.getSource("selectedRoute").setData({ type: "FeatureCollection", features: [] });
  }
}

function clearClusterMarkers() {
  state.clusterMarkers.forEach((marker) => marker.remove());
  state.clusterMarkers = [];
  state.clusterMarkerById.clear();
}

function truckSvg(color = "#07945e") {
  return `<svg viewBox="0 0 72 48" aria-hidden="true">
    <path d="M8 13h34c3 0 5 2 5 5v18H8V13Z" fill="${color}"/>
    <path d="M47 22h9l8 8v6H47V22Z" fill="#f5c84b"/>
    <path d="M53 25h3.5l3.8 4H53v-4Z" fill="#fff9d6"/>
    <path d="M5 36h62v5H5v-5Z" fill="#202a24"/>
    <circle cx="21" cy="41" r="6" fill="#111827"/>
    <circle cx="21" cy="41" r="2.5" fill="#e8eef0"/>
    <circle cx="55" cy="41" r="6" fill="#111827"/>
    <circle cx="55" cy="41" r="2.5" fill="#e8eef0"/>
    <path d="M13 18h24v12H13V18Z" fill="rgba(255,255,255,0.2)"/>
  </svg>`;
}

function makeArrowImage(size = 24) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, size, size);
  ctx.fillStyle = "#fff";
  ctx.beginPath();
  ctx.moveTo(size * 0.2, size * 0.18);
  ctx.lineTo(size * 0.86, size * 0.5);
  ctx.lineTo(size * 0.2, size * 0.82);
  ctx.lineTo(size * 0.34, size * 0.5);
  ctx.closePath();
  ctx.shadowColor = "rgba(0,0,0,0.35)";
  ctx.shadowBlur = 2;
  ctx.fill();
  return ctx.getImageData(0, 0, size, size);
}

function setSelectedRouteData(coordinates, color) {
  if (!state.map?.getSource("selectedRoute")) return;
  state.map.getSource("selectedRoute").setData({
    type: "Feature",
    geometry: { type: "LineString", coordinates },
    properties: { color: color || "#07945e" },
  });
}

function startDashAnimation() {
  if (!state.map?.getLayer("selected-route-line")) return;
  if (state.dashAnimation) cancelAnimationFrame(state.dashAnimation);
  const dashSequence = [
    [0, 4, 3, 2], [0.5, 4, 2.5, 2], [1, 4, 2, 2], [1.5, 4, 1.5, 2],
    [2, 4, 1, 2], [2.5, 4, 0.5, 2], [3, 4, 0, 2], [0, 0.5, 3, 5.5],
    [0, 1, 3, 5], [0, 1.5, 3, 4.5], [0, 2, 3, 4], [0, 2.5, 3, 3.5],
    [0, 3, 3, 3], [0, 3.5, 3, 2.5],
  ];
  let step = 0;
  let last = 0;
  const tick = (ts) => {
    if (ts - last > 80) {
      step = (step + 1) % dashSequence.length;
      last = ts;
      if (state.map?.getLayer("selected-route-line")) {
        state.map.setPaintProperty("selected-route-line", "line-dasharray", dashSequence[step]);
      }
    }
    state.dashAnimation = requestAnimationFrame(tick);
  };
  state.dashAnimation = requestAnimationFrame(tick);
}

async function snapSelectedToRoad(cluster) {
  if (!ROUTING.useOsrm) return;
  const cached = state.snappedByCluster.get(cluster.id);
  if (cached) {
    setSelectedRouteData(cached, cluster.color);
    return;
  }
  if (state.snapAbort) state.snapAbort.abort();
  const controller = new AbortController();
  state.snapAbort = controller;
  try {
    const snapped = await roadSnap(cluster.polyline, { signal: controller.signal });
    if (controller.signal.aborted) return;
    if (!Array.isArray(snapped) || snapped.length < 2) return;
    state.snappedByCluster.set(cluster.id, snapped);
    const staticMarker = state.clusterMarkerById.get(String(cluster.id));
    if (staticMarker) staticMarker.setLngLat(midpoint(snapped));
    if (state.selectedCluster?.id === cluster.id) {
      setSelectedRouteData(snapped, cluster.color);
    }
  } catch (error) {
    if (error.name !== "AbortError") console.warn("road snap failed", error);
  }
}

function buildTruckPopupHtml(cluster) {
  return `<div class="truck-popup">
    <strong>Route ${escapeHtml(cluster.id)}</strong>
    <div class="popup-row"><span>Stops</span><span>${cluster.stops.length}</span></div>
    <div class="popup-row"><span>Distance</span><span>${formatKpi(cluster.distance_km, "km")}</span></div>
    ${cluster.time_min ? `<div class="popup-row"><span>Time</span><span>${formatKpi(cluster.time_min, "min")}</span></div>` : ""}
    ${cluster.occupation_pct != null ? `<div class="popup-row"><span>Occupation</span><span>${formatPct(cluster.occupation_pct)}</span></div>` : ""}
    <div class="popup-row"><span>Truck</span><span>${cluster.truck_size} pallets</span></div>
  </div>`;
}

function addClusterMarkers(scenario) {
  clearClusterMarkers();
  scenario.clusters.forEach((cluster) => {
    const element = document.createElement("button");
    element.className = "truck-marker";
    element.style.setProperty("--cluster-color", cluster.color);
    element.innerHTML = `
      <span class="truck-anchor-dot"></span>
      <span class="truck-graphic">
        <span class="truck-track-dot"></span>
        ${truckSvg(cluster.color)}
        <span class="truck-badge">${cluster.stops.length}</span>
      </span>`;
    element.setAttribute("aria-label", `Route ${cluster.id}: ${cluster.stops.length} stops, ${cluster.distance_km} km`);
    element.addEventListener("click", () => {
      selectCluster(cluster);
      new MapGL.Popup({ offset: 18, closeButton: true })
        .setLngLat(truckPosition(cluster))
        .setHTML(buildTruckPopupHtml(cluster))
        .addTo(state.map);
    });
    const marker = new MapGL.Marker({ element, anchor: "center" })
      .setLngLat(truckPosition(cluster))
      .addTo(state.map);
    marker.getElement().style.zIndex = "35";
    state.clusterMarkers.push(marker);
    state.clusterMarkerById.set(String(cluster.id), marker);
  });
  updateMapMarkerScale();
  updateLayerVisibility();
}

function syncScenarioToggle(name) {
  document.querySelectorAll("[data-scenario]").forEach((button) => {
    const isActive = button.dataset.scenario === name;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
}

function renderScenario(name) {
  state.current = name;
  const scenario = state[name];
  syncScenarioToggle(name);
  syncUrl();
  renderKpis(document.getElementById("kpis"), scenario);
  flashKpis();
  renderMixChart(document.getElementById("mixChart"), scenario);
  document.getElementById("mixMeta").textContent =
    `${scenario.clusters.length} truck${scenario.clusters.length === 1 ? "" : "s"} on route`;
  updateBottomStrip();
  state.map.getSource("clusters").setData({
    type: "FeatureCollection",
    features: scenario.clusters.map(clusterFeature),
  });
  state.map.getSource("allRoutes").setData({
    type: "FeatureCollection",
    features: scenario.clusters.map(routeFeature),
  });
  addClusterMarkers(scenario);
  clearRoute();
  if (scenario.clusters.length) {
    selectCluster(scenario.clusters[0]);
  }
  renderCurrentView();
  prefetchAllSnaps(scenario);
}

function prefetchAllSnaps(scenario) {
  if (!ROUTING.useOsrm) return;
  scenario.clusters.forEach((cluster, idx) => {
    if (state.snappedByCluster.has(cluster.id)) return;
    setTimeout(async () => {
      try {
        const snapped = await roadSnap(cluster.polyline);
        if (Array.isArray(snapped) && snapped.length >= 2) {
          state.snappedByCluster.set(cluster.id, snapped);
          const marker = state.clusterMarkerById.get(String(cluster.id));
          if (marker) marker.setLngLat(midpoint(snapped));
          if (state.map?.getSource("allRoutes")) {
            state.map.getSource("allRoutes").setData({
              type: "FeatureCollection",
              features: scenario.clusters.map((c) => ({
                type: "Feature",
                id: c.id,
                properties: { id: c.id, color: c.color },
                geometry: {
                  type: "LineString",
                  coordinates: state.snappedByCluster.get(c.id) || c.polyline || [],
                },
              })),
            });
          }
        }
      } catch (error) {
        if (error.name !== "AbortError") console.warn("prefetch snap failed", error);
      }
    }, idx * 250);
  });
}

function countReturnables(cluster) {
  let count = 0;
  (cluster.load_plan?.pallets || []).forEach((pallet) => {
    if ((pallet.lines || []).some((line) => line.retornable)) count += 1;
  });
  return count;
}

function selectCluster(cluster) {
  state.selectedCluster = cluster;
  clearRoute();
  document.getElementById("clusterTitle").textContent = `Route ${cluster.id}`;
  const returnables = countReturnables(cluster);
  const meta = document.getElementById("clusterMeta");
  meta.innerHTML = `<span class="cluster-meta-chips">
    <span class="chip">${cluster.stops.length} stops</span>
    <span class="chip">${escapeHtml(formatKpi(cluster.distance_km, "km"))}</span>
    <span class="chip">${cluster.truck_size} pallets</span>
    ${cluster.time_min ? `<span class="chip chip-time">${escapeHtml(formatKpi(cluster.time_min, "min"))}</span>` : ""}
    ${cluster.occupation_pct != null ? `<span class="chip chip-occupation">${formatPct(cluster.occupation_pct)} full</span>` : ""}
    ${returnables ? `<span class="chip chip-return">${returnables} returnable</span>` : ""}
  </span>`;
  const initial = activePolyline(cluster);
  setSelectedRouteData(initial, cluster.color);
  startDashAnimation();
  snapSelectedToRoad(cluster);
  cluster.stops.forEach((stop) => {
    const element = document.createElement("div");
    element.className = "stop-pin";
    element.style.setProperty("--cluster-color", cluster.color);
    element.innerHTML = `
      <div class="stop-pin-inner">
        <svg class="stop-pin-svg" viewBox="0 0 32 44" aria-hidden="true">
          <path d="M16 1c8.3 0 15 6.5 15 14.5 0 10.5-13 26.5-15 28.5C14 42 1 26 1 15.5 1 7.5 7.7 1 16 1Z"
                fill="${cluster.color}" stroke="#fff" stroke-width="2"/>
          <circle cx="16" cy="15" r="9.5" fill="#fff"/>
        </svg>
        <span class="stop-pin-label">${escapeHtml(String(stop.seq))}</span>
        <span class="stop-pin-tooltip">${escapeHtml(stop.name || `Client ${stop.cliente}`)}</span>
      </div>`;
    const marker = new MapGL.Marker({ element, anchor: "bottom" })
      .setLngLat([stop.lon, stop.lat])
      .addTo(state.map);
    marker.getElement().style.zIndex = "30";
    state.routeMarkers.push(marker);
  });
  updateMapMarkerScale();
  updateLayerVisibility();
  state.map.fitBounds(
    cluster.polyline.reduce(
      (bounds, coord) => bounds.extend(coord),
      new MapGL.LngLatBounds(cluster.polyline[0], cluster.polyline[0])
    ),
    { padding: MAP.fitPadding, duration: MAP.fitDuration }
  );
  syncUrl();
  renderTruck(document.getElementById("truck3d"), cluster.load_plan);
  renderLoadList(cluster);
  renderStopsList(cluster);
}

function renderStopsList(cluster) {
  const palletsPerStop = new Map();
  (cluster.load_plan?.pallets || []).forEach((pallet) => {
    (pallet.lines || []).forEach((line) => {
      const seq = line.stop_seq;
      palletsPerStop.set(seq, (palletsPerStop.get(seq) || 0) + Number(line.size || 0));
    });
  });
  const html = cluster.stops
    .map((stop) => {
      const computed = palletsPerStop.get(stop.seq);
      const pallets = Number(stop.pallets ?? computed ?? 0).toFixed(2);
      return `<div class="stop-row" style="--cluster-color:${cluster.color}">
        <span class="stop-seq">${stop.seq}</span>
        <div class="stop-info">
          <strong>${escapeHtml(stop.name || `Client ${stop.cliente}`)}</strong>
          <small>${escapeHtml(String(stop.cliente || ""))}</small>
        </div>
        <span class="stop-pallets">${pallets}</span>
      </div>`;
    })
    .join("");
  document.getElementById("stopsList").innerHTML = html || "<div class=\"empty-products\">No stops</div>";
}

function renderLoadList(cluster) {
  const lines = aggregatePalletLines((cluster.load_plan?.pallets || []).flatMap((pallet) => pallet.lines || []));
  document.getElementById("loadList").innerHTML = lines.slice(0, 8).map(renderProductRow).join("") || "<div class=\"empty-products\">No load plan yet</div>";
}

function aggregatePalletLines(lines) {
  const grouped = new Map();
  lines.forEach((line) => {
    const key = [line.material, line.product, line.uma].join("|");
    const current = grouped.get(key) || { ...line, cantidad: 0, size: 0, clients: new Set(), stops: new Set() };
    current.cantidad += Number(line.cantidad || 0);
    current.size += Number(line.size || 0);
    current.clients.add(line.cliente);
    current.stops.add(line.stop_seq);
    grouped.set(key, current);
  });
  return [...grouped.values()].sort((a, b) => b.size - a.size);
}

function renderProductRow(line) {
  const quantity = Number(line.cantidad || 0).toLocaleString("en-US", { maximumFractionDigits: 1 });
  const size = Math.max(1, Math.round(Number(line.size || 0) * 100));
  return `<div class="product-row">
    <div>
      <strong>${escapeHtml(line.material)}</strong>
      <span>${escapeHtml(line.product)}</span>
      <small>${line.clients.size} clients · ${line.stops.size} stops</small>
    </div>
    <div>
      <strong>${quantity} ${escapeHtml(line.uma)}</strong>
      <small>${size}% pallet</small>
    </div>
  </div>`;
}

function updateDateControls() {
  const current = state.manifest.dates[state.dateIndex];
  document.getElementById("dateLabel").textContent = current.label;
  document.getElementById("prevDayBtn").disabled = state.dateIndex === 0;
  document.getElementById("nextDayBtn").disabled = state.dateIndex === state.manifest.dates.length - 1;
}

function updateBottomStrip() {
  const kpis = state.optimized?.kpis || {};
  const totalStops = (state.optimized?.clusters || []).reduce((sum, cluster) => sum + cluster.stops.length, 0);
  document.getElementById("deliveriesMetric").textContent = Math.round(totalStops);
  document.getElementById("distanceMetric").textContent = formatPct(kpis.km_saved_pct);
  document.getElementById("co2Metric").textContent = formatCo2(kpis.co2_saved_kg);
  document.getElementById("costMetric").textContent = formatCostFromKm(kpis.km_saved);
}

function setLayerVisible(id, visible) {
  if (state.map?.getLayer(id)) {
    state.map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
  }
}

function updateLayerVisibility() {
  updateMapMarkerScale();
  setLayerVisible("cluster-circles", state.layers.areas);
  ["selected-route-casing", "selected-route-glow", "selected-route-line", "selected-route-arrows"].forEach((id) => {
    setLayerVisible(id, state.layers.path);
  });
  ["all-route-casing", "all-route-lines"].forEach((id) => {
    setLayerVisible(id, state.layers.path);
  });
}

function focusMap() {
  const clusters = scenarioClusters();
  const coordinates = clusters.flatMap((cluster) => cluster.polyline || []);
  if (!coordinates.length) return;
  const bounds = coordinates.reduce(
    (nextBounds, coord) => nextBounds.extend(coord),
    new MapGL.LngLatBounds(coordinates[0], coordinates[0])
  );
  state.map.fitBounds(bounds, { padding: MAP.fitPadding, duration: MAP.fitDuration });
}

function scenarioClusters() {
  return state[state.current]?.clusters || [];
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".nav-item[data-view]").forEach((button) => {
    const isActive = button.dataset.view === view;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
  syncUrl();
  renderCurrentView();
}

function renderCurrentView() {
  const panel = document.getElementById("viewPanel");
  if (!panel) return;
  if (state.view === "overview") {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }
  panel.classList.remove("hidden");
  const renderers = {
    routes: renderRoutesView,
    trucks: renderTrucksView,
    loads: renderLoadsView,
    analytics: renderAnalyticsView,
  };
  panel.innerHTML = (renderers[state.view] || renderRoutesView)();
  panel.querySelectorAll("[data-route-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const cluster = scenarioClusters().find((item) => String(item.id) === String(button.dataset.routeId));
      if (cluster) selectCluster(cluster);
    });
  });
  const search = panel.querySelector("#routesSearch");
  if (search) {
    search.focus({ preventScroll: true });
    search.setSelectionRange(search.value.length, search.value.length);
    search.addEventListener("input", (event) => {
      state.routesQuery = event.target.value;
      renderCurrentView();
    });
  }
  const sortSel = panel.querySelector("#routesSort");
  if (sortSel) {
    sortSel.addEventListener("change", (event) => {
      state.routesSort = event.target.value;
      renderCurrentView();
    });
  }
}

function viewHeader(title, text) {
  return `<div class="view-head">
    <div>
      <h2>${title}</h2>
      <p>${text}</p>
    </div>
    <button class="view-close" data-view-id="overview">Back to map</button>
  </div>`;
}

function sortClusters(clusters, mode) {
  const arr = clusters.slice();
  switch (mode) {
    case "stops": return arr.sort((a, b) => b.stops.length - a.stops.length);
    case "occupation": return arr.sort((a, b) => (b.occupation_pct || 0) - (a.occupation_pct || 0));
    case "id": return arr.sort((a, b) => String(a.id).localeCompare(String(b.id)));
    case "distance":
    default: return arr.sort((a, b) => b.distance_km - a.distance_km);
  }
}

function matchesQuery(cluster, query) {
  if (!query) return true;
  const q = query.toLowerCase();
  if (String(cluster.id).toLowerCase().includes(q)) return true;
  return (cluster.stops || []).some((stop) =>
    String(stop.name || "").toLowerCase().includes(q) ||
    String(stop.cliente || "").toLowerCase().includes(q)
  );
}

function renderRoutesView() {
  const filtered = sortClusters(scenarioClusters(), state.routesSort)
    .filter((cluster) => matchesQuery(cluster, state.routesQuery));
  const rows = filtered
    .map((cluster) => `<button class="route-row" data-route-id="${escapeHtml(cluster.id)}">
      <span class="route-dot" style="background:${cluster.color}"></span>
      <strong>Route ${escapeHtml(cluster.id)}</strong>
      <span>${cluster.stops.length} stops</span>
      <span>${formatKpi(cluster.distance_km, "km")}</span>
      <span>${cluster.truck_size} pallets</span>
      <span>${formatPct(cluster.occupation_pct || 0)}</span>
    </button>`)
    .join("");
  const empty = !filtered.length
    ? `<div class="view-note">No routes match "${escapeHtml(state.routesQuery)}".</div>`
    : "";
  return `${viewHeader("Routes", "Operational routes for the selected day and scenario.")}
    <div class="routes-search">
      <input id="routesSearch" type="search" placeholder="Search by route id, client name, or code…"
        value="${escapeHtml(state.routesQuery)}" autocomplete="off" />
      <select id="routesSort">
        <option value="distance"${state.routesSort === "distance" ? " selected" : ""}>Distance</option>
        <option value="stops"${state.routesSort === "stops" ? " selected" : ""}>Stops</option>
        <option value="occupation"${state.routesSort === "occupation" ? " selected" : ""}>Occupation</option>
        <option value="id"${state.routesSort === "id" ? " selected" : ""}>Route id</option>
      </select>
    </div>
    <div class="route-table">${rows}</div>
    ${empty}`;
}

function renderTrucksView() {
  const groups = scenarioClusters().reduce((acc, cluster) => {
    const key = `${cluster.truck_size}`;
    acc[key] ||= { count: 0, pallets: 0, km: 0, stops: 0 };
    acc[key].count += 1;
    acc[key].pallets += Number(cluster.load_plan?.pallets?.length || cluster.truck_size || 0);
    acc[key].km += Number(cluster.distance_km || 0);
    acc[key].stops += Number(cluster.stops.length || 0);
    return acc;
  }, {});
  const cards = Object.entries(groups)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([size, group]) => `<div class="fleet-card">
      <span>${size}-pallet truck</span>
      <strong>${group.count}</strong>
      <small>${group.stops} stops · ${group.km.toFixed(1)} km</small>
    </div>`)
    .join("");
  return `${viewHeader("Trucks", "Fleet mix selected by capacity and route demand.")}
    <div class="fleet-grid">${cards}</div>
    <div class="view-note">Truck sizing uses 3, 6 and 8 pallet slots, with overflow assigned to the nearest feasible size for demo data.</div>`;
}

function renderLoadsView() {
  const cards = scenarioClusters()
    .slice(0, 10)
    .map((cluster) => {
      const lines = aggregatePalletLines((cluster.load_plan?.pallets || []).flatMap((pallet) => pallet.lines || []));
      const top = lines.slice(0, 3).map((line) => `<li><strong>${escapeHtml(line.material)}</strong> ${escapeHtml(line.product)}</li>`).join("");
      return `<button class="load-card" data-route-id="${escapeHtml(cluster.id)}">
        <div><span class="route-dot" style="background:${cluster.color}"></span><strong>Route ${escapeHtml(cluster.id)}</strong></div>
        <small>${cluster.load_plan?.pallets?.length || 0} pallets · ${cluster.occupation_pct}% occupation</small>
        <ul>${top}</ul>
      </button>`;
    })
    .join("");
  return `${viewHeader("Loads", "Top products packed into the selected day's optimized trucks.")}
    <div class="load-grid">${cards}</div>`;
}

function renderAnalyticsView() {
  const kpis = state.optimized?.kpis || {};
  const trucksReduced = Number(kpis.baseline_trucks || 0) - Number(kpis.optimized_trucks || 0);
  const cards = [
    ["Distance saved", formatKpi(kpis.km_saved, "km")],
    ["CO2 saved", formatCo2(kpis.co2_saved_kg)],
    ["Truck reduction", `${trucksReduced} trucks`],
    ["Avg occupation", formatPct(kpis.avg_occupation_pct)],
  ];
  return `${viewHeader("Analytics", "Pitch-ready impact summary for the selected delivery day.")}
    <div class="analytics-grid">${cards.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>
    <div class="view-note">CO2 proxy uses ${BUSINESS.co2KgPerKm} kg/km. Cost impact in the footer uses €${BUSINESS.costEurPerKm}/km saved.</div>`;
}

async function loadDay(index) {
  state.dateIndex = index;
  const current = state.manifest.dates[state.dateIndex];
  const base = "../outputs/";
  document.getElementById("kpis")?.classList.add("loading");
  document.querySelectorAll(".bottom-strip strong").forEach((el) => el.classList.add("skeleton"));
  state.snappedByCluster.clear();
  if (state.snapAbort) state.snapAbort.abort();
  state.baseline = await loadJson(`${base}${current.baseline}`);
  state.optimized = await loadJson(`${base}${current.optimized}`);
  document.querySelectorAll(".bottom-strip strong").forEach((el) => el.classList.remove("skeleton"));
  updateDateControls();
  renderChart(document.getElementById("comparisonChart"), state.baseline, state.optimized);
  if (state.map) {
    renderScenario(state.current);
    focusMap();
  }
}

function initMap() {
  const depot = state.optimized.depot;
  state.map = new MapGL.Map({
    container: "map",
    style: token ? "mapbox://styles/mapbox/light-v11" : MAP.cartoStyleUrl,
    center: [depot.lon, depot.lat],
    zoom: MAP.initialZoom,
    pitch: MAP.initialPitch,
    bearing: MAP.initialBearing,
    attributionControl: true,
    scrollZoom: false,
  });
  state.map.addControl(new MapGL.NavigationControl({ showCompass: true, visualizePitch: true }), "bottom-right");
  state.map.addControl(new MapGL.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");
  state.map.on("zoom", updateMapMarkerScale);
  const depotElement = document.createElement("div");
  depotElement.className = "depot-marker";
  depotElement.innerHTML = `
    <span class="depot-pulse"></span>
    <span class="depot-core" aria-hidden="true">
      <svg viewBox="0 0 32 32" fill="none">
        <path d="M4 13 16 5l12 8v14H4V13Z" fill="#fff" fill-opacity="0.96"/>
        <path d="M4 13 16 5l12 8" stroke="#07945e" stroke-width="2" stroke-linejoin="round"/>
        <path d="M11 27v-7h10v7" stroke="#07945e" stroke-width="2" stroke-linejoin="round"/>
        <path d="M14 20h4M14 23h4" stroke="#07945e" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </span>
    <span class="depot-label">${escapeHtml(depot.name || "Depot")}</span>`;
  new MapGL.Marker({ element: depotElement, anchor: "center" }).setLngLat([depot.lon, depot.lat]).addTo(state.map);
  state.map.on("load", () => {
    if (!state.map.hasImage("route-arrow")) {
      state.map.addImage("route-arrow", makeArrowImage(24), { pixelRatio: 2 });
    }
    state.map.addSource("allRoutes", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    state.map.addSource("clusters", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    state.map.addLayer({
      id: "all-route-casing",
      source: "allRoutes",
      type: "line",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#1d2939",
        "line-opacity": 0.18,
        "line-width": ["interpolate", ["linear"], ["zoom"], 8, 3, 12, 6, 15, 10],
        "line-blur": 1,
      },
    });
    state.map.addLayer({
      id: "all-route-lines",
      source: "allRoutes",
      type: "line",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["get", "color"],
        "line-width": ["interpolate", ["linear"], ["zoom"], 8, 1.5, 12, 3, 15, 5],
        "line-opacity": [
          "case",
          ["boolean", ["feature-state", "hover"], false], 0.95,
          0.6,
        ],
      },
    });
    state.map.addLayer({
      id: "cluster-circles",
      source: "clusters",
      type: "circle",
      paint: {
        "circle-radius": ["+", 22, ["*", ["get", "stops"], 1.2]],
        "circle-color": ["get", "color"],
        "circle-opacity": 0.1,
        "circle-stroke-color": ["get", "color"],
        "circle-stroke-width": 3,
      },
    });
    state.map.addSource("selectedRoute", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    state.map.addLayer({
      id: "selected-route-casing",
      source: "selectedRoute",
      type: "line",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#0b1c14",
        "line-opacity": 0.22,
        "line-width": ["interpolate", ["linear"], ["zoom"], 8, 6, 12, 11, 15, 16],
        "line-blur": 1.5,
      },
    });
    state.map.addLayer({
      id: "selected-route-glow",
      source: "selectedRoute",
      type: "line",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["coalesce", ["get", "color"], "#07945e"],
        "line-opacity": 0.18,
        "line-width": ["interpolate", ["linear"], ["zoom"], 8, 10, 12, 18, 15, 26],
        "line-blur": 6,
      },
    });
    state.map.addLayer({
      id: "selected-route-line",
      source: "selectedRoute",
      type: "line",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["coalesce", ["get", "color"], "#07945e"],
        "line-width": ["interpolate", ["linear"], ["zoom"], 8, 3, 12, 6, 15, 9],
        "line-opacity": 0.95,
      },
    });
    state.map.addLayer({
      id: "selected-route-arrows",
      source: "selectedRoute",
      type: "symbol",
      layout: {
        "symbol-placement": "line",
        "symbol-spacing": 80,
        "icon-image": "route-arrow",
        "icon-size": ["interpolate", ["linear"], ["zoom"], 8, 0.5, 12, 0.7, 15, 0.9],
        "icon-allow-overlap": true,
        "icon-rotation-alignment": "map",
        "icon-pitch-alignment": "map",
        "icon-ignore-placement": true,
      },
    });
    let hoveredId = null;
    state.map.on("mousemove", "all-route-lines", (event) => {
      if (!event.features?.length) return;
      state.map.getCanvas().style.cursor = "pointer";
      const id = event.features[0].properties.id;
      if (hoveredId !== null) {
        state.map.setFeatureState({ source: "allRoutes", id: hoveredId }, { hover: false });
      }
      hoveredId = id;
      state.map.setFeatureState({ source: "allRoutes", id }, { hover: true });
    });
    state.map.on("mouseleave", "all-route-lines", () => {
      state.map.getCanvas().style.cursor = "";
      if (hoveredId !== null) {
        state.map.setFeatureState({ source: "allRoutes", id: hoveredId }, { hover: false });
      }
      hoveredId = null;
    });
    state.map.on("click", "all-route-lines", (event) => {
      const id = String(event.features[0].properties.id);
      const cluster = state[state.current].clusters.find((item) => String(item.id) === id);
      if (cluster) selectCluster(cluster);
    });
    state.map.on("click", "cluster-circles", (event) => {
      const id = String(event.features[0].properties.id);
      const cluster = state[state.current].clusters.find((item) => String(item.id) === id);
      if (cluster) selectCluster(cluster);
    });
    const initial = readUrlState();
    const initialScenario = initial.scenario === "baseline" ? "baseline" : "optimized";
    renderScenario(initialScenario);
    if (initial.route) {
      const cluster = scenarioClusters().find((item) => String(item.id) === initial.route);
      if (cluster) selectCluster(cluster);
    }
    if (initial.view && initial.view !== "overview") setView(initial.view);
  });
}

async function main() {
  state.manifest = await loadJson("../outputs/scenario_manifest.json");
  const initial = readUrlState();
  const urlIndex = initial.day
    ? state.manifest.dates.findIndex((item) => item.date === initial.day)
    : -1;
  const defaultIndex = state.manifest.dates.findIndex((item) => item.date === state.manifest.defaultDate);
  state.dateIndex = Math.max(0, urlIndex !== -1 ? urlIndex : defaultIndex);
  await loadDay(state.dateIndex);
  initMap();
  document.querySelectorAll("[data-scenario]").forEach((button) => {
    button.addEventListener("click", () => renderScenario(button.dataset.scenario));
  });
  document.getElementById("prevDayBtn").addEventListener("click", () => {
    if (state.dateIndex > 0) loadDay(state.dateIndex - 1);
  });
  document.getElementById("nextDayBtn").addEventListener("click", () => {
    if (state.dateIndex < state.manifest.dates.length - 1) loadDay(state.dateIndex + 1);
  });
  document.getElementById("layersBtn").addEventListener("click", () => {
    document.getElementById("layersPanel").classList.toggle("hidden");
  });
  document.getElementById("focusBtn").addEventListener("click", focusMap);
  [
    ["areasLayer", "areas"],
    ["trucksLayer", "trucks"],
    ["stopsLayer", "stops"],
    ["pathLayer", "path"],
  ].forEach(([id, key]) => {
    document.getElementById(id).addEventListener("change", (event) => {
      state.layers[key] = event.target.checked;
      updateLayerVisibility();
    });
  });
  document.querySelectorAll(".nav-item[data-view]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });
  document.getElementById("viewPanel").addEventListener("click", (event) => {
    const close = event.target.closest("[data-view-id='overview']");
    if (close) setView("overview");
  });
  document.querySelectorAll("[data-chart]").forEach((button) => {
    button.addEventListener("click", () => setChartMode(button.dataset.chart));
  });
  document.querySelectorAll("[data-detail]").forEach((button) => {
    button.addEventListener("click", () => setDetailTab(button.dataset.detail));
  });
  bindKeyboardShortcuts();
}

function bindKeyboardShortcuts() {
  const isTypingTarget = (el) => {
    if (!el) return false;
    const tag = el.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
  };
  window.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (isTypingTarget(event.target)) return;
    const key = event.key;
    const navMap = { "1": "overview", "2": "routes", "3": "trucks", "4": "loads", "5": "analytics" };
    if (key === "ArrowLeft" && state.dateIndex > 0) {
      event.preventDefault();
      loadDay(state.dateIndex - 1);
    } else if (key === "ArrowRight" && state.dateIndex < state.manifest.dates.length - 1) {
      event.preventDefault();
      loadDay(state.dateIndex + 1);
    } else if (key === "b" || key === "B") {
      renderScenario("baseline");
    } else if (key === "o" || key === "O") {
      renderScenario("optimized");
    } else if (key === "Escape") {
      setView("overview");
    } else if (navMap[key]) {
      setView(navMap[key]);
    }
  });
}

main().catch((error) => {
  console.error(error);
  showToast(`Failed to load scenario: ${error.message}`, { tone: "error" });
});
