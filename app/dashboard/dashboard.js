import { CHART, KPI_CONFIG, iconSvg } from "./config.js";
import { escapeHtml, formatHours, formatKpi, formatPct } from "./format.js";

let chart;

function secondaryFor(key, kpis) {
  if (key === "km_saved" && kpis.km_saved_pct !== undefined) {
    return `${formatPct(kpis.km_saved_pct)} vs baseline`;
  }
  if (key === "time_saved_min" && kpis.time_saved_min !== undefined) {
    return formatHours(kpis.time_saved_min);
  }
  return "";
}

export function renderKpis(container, scenario) {
  const kpis = scenario.kpis;
  container.innerHTML = KPI_CONFIG.map(({ key, label, unit, icon }) => {
    const secondary = secondaryFor(key, kpis);
    return `<div class="kpi">
      <span class="kpi-icon ${escapeHtml(icon)}" aria-hidden="true">${iconSvg(icon)}</span>
      <div>
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(formatKpi(kpis[key], unit))}</strong>
        ${secondary ? `<small>${escapeHtml(secondary)}</small>` : ""}
      </div>
    </div>`;
  }).join("");
}

function buildChartData(baseline, optimized) {
  const baselineRoutes = baseline.clusters.slice(0, CHART.maxRoutes);
  const optimizedRoutes = optimized.clusters.slice(0, CHART.maxRoutes);
  return {
    labels: baselineRoutes.map((cluster) => `R ${cluster.id}`),
    datasets: [
      {
        label: "Baseline",
        data: baselineRoutes.map((cluster) => cluster.distance_km),
        backgroundColor: CHART.baselineColor,
        borderRadius: 4,
      },
      {
        label: "Optimized",
        data: optimizedRoutes.map((cluster) => cluster.distance_km),
        backgroundColor: CHART.optimizedColor,
        borderRadius: 4,
      },
    ],
  };
}

export function renderChart(canvas, baseline, optimized) {
  const data = buildChartData(baseline, optimized);
  if (chart) {
    chart.data = data;
    chart.update();
    return;
  }
  chart = new Chart(canvas, {
    type: "bar",
    data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", align: "end", labels: { boxWidth: 10, usePointStyle: true } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true } },
        y: { beginAtZero: true, title: { display: true, text: "km" }, grid: { color: "#edf0f2" } },
      },
    },
  });
}
