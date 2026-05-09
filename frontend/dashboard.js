let chart;

const KPI_CONFIG = [
  ["km_saved", "Km saved", "km", "route"],
  ["total_km", "Total km", "km", "road"],
  ["avg_occupation_pct", "Occupation", "%", "pie"],
  ["co2_saved_kg", "CO2 saved", "kg", "leaf"],
  ["time_saved_min", "Time saved", "min", "clock"],
  ["trucks_used", "Trucks", "", "truck"],
];

function iconFor(type) {
  const icons = {
    route: "↗",
    road: "▥",
    pie: "◔",
    leaf: "♧",
    clock: "◷",
    truck: "▤",
  };
  return icons[type] || "•";
}

function formatValue(value, unit) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) {
    return "Baseline";
  }
  const numeric = Number(value);
  if (!unit) {
    return numeric.toLocaleString("en-US", { maximumFractionDigits: 0 });
  }
  return `${numeric.toLocaleString("en-US", { maximumFractionDigits: 1 })} ${unit}`;
}

export function renderKpis(container, scenario) {
  const kpis = scenario.kpis;
  container.innerHTML = KPI_CONFIG.map(([key, label, unit, icon]) => {
    const secondary =
      key === "km_saved" && kpis.km_saved_pct !== undefined
        ? `${Number(kpis.km_saved_pct).toFixed(1)}% vs baseline`
        : key === "time_saved_min" && kpis.time_saved_min !== undefined
          ? `${(Number(kpis.time_saved_min) / 60).toFixed(1)} h`
          : "";
    return `<div class="kpi">
      <span class="kpi-icon ${icon}">${iconFor(icon)}</span>
      <div>
        <span>${label}</span>
        <strong>${formatValue(kpis[key], unit)}</strong>
        ${secondary ? `<small>${secondary}</small>` : ""}
      </div>
    </div>`;
  }).join("");
}

export function renderChart(canvas, baseline, optimized) {
  const baselineRoutes = baseline.clusters.slice(0, 8);
  const optimizedRoutes = optimized.clusters.slice(0, 8);
  const labels = baselineRoutes.map((cluster) => `R ${cluster.id}`);
  const data = {
    labels,
    datasets: [
      {
        label: "Baseline",
        data: baselineRoutes.map((cluster) => cluster.distance_km),
        backgroundColor: "#d7dadd",
        borderRadius: 4,
      },
      {
        label: "Optimized",
        data: optimizedRoutes.map((cluster) => cluster.distance_km),
        backgroundColor: "#07945e",
        borderRadius: 4,
      },
    ],
  };
  if (chart) {
    chart.destroy();
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
