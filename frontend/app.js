import { renderKpis, renderChart } from "./dashboard.js";
import { renderTruck } from "./truck3d.js";
import { BUSINESS, MAP } from "./config.js";
import { escapeHtml, formatCo2, formatCostFromKm, formatKpi, formatPct } from "./format.js";

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

function truckPosition(cluster) {
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
    element.title = `Route ${cluster.id}: truck on planned route, ${cluster.stops.length} stops, ${cluster.distance_km} km`;
    element.addEventListener("click", () => selectCluster(cluster));
    const marker = new MapGL.Marker({ element, anchor: "center" })
      .setLngLat(truckPosition(cluster))
      .addTo(state.map);
    marker.getElement().style.zIndex = "35";
    state.clusterMarkers.push(marker);
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
}

function selectCluster(cluster) {
  state.selectedCluster = cluster;
  clearRoute();
  document.getElementById("clusterTitle").textContent = `Route ${cluster.id}`;
  document.getElementById("clusterMeta").textContent = `${cluster.stops.length} stops · ${cluster.distance_km} km · ${cluster.truck_size} pallets`;
  state.map.getSource("selectedRoute").setData({
    type: "Feature",
    geometry: { type: "LineString", coordinates: cluster.polyline },
    properties: { color: cluster.color },
  });
  cluster.stops.forEach((stop) => {
    const element = document.createElement("div");
    element.className = "marker";
    element.style.background = cluster.color;
    element.style.setProperty("--cluster-color", cluster.color);
    element.textContent = stop.seq;
    const marker = new MapGL.Marker(element).setLngLat([stop.lon, stop.lat]).addTo(state.map);
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

function updateLayerVisibility() {
  updateMapMarkerScale();
  if (state.map?.getLayer("cluster-circles")) {
    state.map.setLayoutProperty("cluster-circles", "visibility", state.layers.areas ? "visible" : "none");
  }
  if (state.map?.getLayer("selected-route-line")) {
    state.map.setLayoutProperty("selected-route-line", "visibility", state.layers.path ? "visible" : "none");
  }
  if (state.map?.getLayer("all-route-lines")) {
    state.map.setLayoutProperty("all-route-lines", "visibility", state.layers.path ? "visible" : "none");
  }
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

function renderRoutesView() {
  const rows = scenarioClusters()
    .slice()
    .sort((a, b) => b.distance_km - a.distance_km)
    .map((cluster) => `<button class="route-row" data-route-id="${escapeHtml(cluster.id)}">
      <span class="route-dot" style="background:${cluster.color}"></span>
      <strong>Route ${escapeHtml(cluster.id)}</strong>
      <span>${cluster.stops.length} stops</span>
      <span>${cluster.distance_km} km</span>
      <span>${cluster.truck_size} pallets</span>
    </button>`)
    .join("");
  return `${viewHeader("Routes", "Operational routes for the selected day and scenario.")}
    <div class="route-table">${rows}</div>`;
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
  state.baseline = await loadJson(`${base}${current.baseline}`);
  state.optimized = await loadJson(`${base}${current.optimized}`);
  updateDateControls();
  renderChart(document.getElementById("comparisonChart"), state.baseline, state.optimized);
  if (state.map) {
    renderScenario(state.current);
    focusMap();
  }
}

function initMap() {
  const depot = state.optimized.depot;
  const fallbackStyle = {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: "OpenStreetMap",
      },
    },
    layers: [{ id: "osm", type: "raster", source: "osm" }],
  };
  state.map = new MapGL.Map({
    container: "map",
    style: token ? "mapbox://styles/mapbox/light-v11" : fallbackStyle,
    center: [depot.lon, depot.lat],
    zoom: MAP.initialZoom,
    attributionControl: true,
    scrollZoom: false,
  });
  state.map.addControl(new MapGL.NavigationControl({ showCompass: true }), "bottom-right");
  state.map.on("zoom", updateMapMarkerScale);
  const depotElement = document.createElement("div");
  depotElement.className = "depot-marker";
  depotElement.innerHTML = `<span>⌂</span>`;
  new MapGL.Marker(depotElement).setLngLat([depot.lon, depot.lat]).addTo(state.map);
  state.map.on("load", () => {
    state.map.addSource("allRoutes", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    state.map.addSource("clusters", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    state.map.addLayer({
      id: "all-route-lines",
      source: "allRoutes",
      type: "line",
      paint: {
        "line-color": ["get", "color"],
        "line-width": 3,
        "line-opacity": 0.56,
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
      id: "selected-route-line",
      source: "selectedRoute",
      type: "line",
      paint: {
        "line-color": ["coalesce", ["get", "color"], "#07945e"],
        "line-width": 6,
        "line-opacity": 0.92,
      },
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
}

main().catch((error) => {
  console.error(error);
  showToast(`Failed to load scenario: ${error.message}`, { tone: "error" });
});
