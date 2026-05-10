const cache = new Map();

async function fetchOptimized(path) {
  if (cache.has(path)) return cache.get(path);
  const promise = fetch(path).then((r) => {
    if (!r.ok) throw new Error(`Cannot load ${path}`);
    return r.json();
  });
  cache.set(path, promise);
  return promise;
}

export async function loadTrend(manifest, basePath = "../outputs/") {
  const items = await Promise.all(
    manifest.dates.map(async (entry) => {
      const data = await fetchOptimized(`${basePath}${entry.optimized}`);
      return {
        date: entry.date,
        label: entry.label,
        kpis: data.kpis || {},
      };
    }),
  );
  return items;
}

let trendChart;

export function renderTrendChart(canvas, series) {
  const labels = series.map((item) => item.label.replace(/, \d{4}$/, ""));
  const data = {
    labels,
    datasets: [
      {
        label: "Km saved",
        data: series.map((item) => Number(item.kpis.km_saved || 0)),
        borderColor: "#07945e",
        backgroundColor: "rgba(7, 148, 94, 0.15)",
        fill: true,
        tension: 0.35,
        yAxisID: "y",
        pointRadius: 3,
        pointHoverRadius: 5,
      },
      {
        label: "CO2 saved (kg)",
        data: series.map((item) => Number(item.kpis.co2_saved_kg || 0)),
        borderColor: "#7c4dd7",
        backgroundColor: "rgba(124, 77, 215, 0.0)",
        borderDash: [4, 4],
        tension: 0.35,
        yAxisID: "y1",
        pointRadius: 3,
        pointHoverRadius: 5,
      },
    ],
  };
  if (trendChart) {
    trendChart.data = data;
    trendChart.update();
    return;
  }
  trendChart = new Chart(canvas, {
    type: "line",
    data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top", align: "end", labels: { boxWidth: 10, usePointStyle: true } },
      },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, title: { display: true, text: "km" }, grid: { color: "#edf0f2" } },
        y1: {
          beginAtZero: true,
          position: "right",
          title: { display: true, text: "kg CO2" },
          grid: { display: false },
        },
      },
    },
  });
}

let mixChart;

export function renderMixChart(canvas, scenario) {
  const counts = new Map();
  scenario.clusters.forEach((cluster) => {
    const key = String(cluster.truck_size);
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  const entries = [...counts.entries()].sort(([a], [b]) => Number(a) - Number(b));
  const palette = ["#07945e", "#3f6fcc", "#e59a00", "#7c4dd7", "#b3261e"];
  const data = {
    labels: entries.map(([size]) => `${size}-pallet`),
    datasets: [
      {
        data: entries.map(([, count]) => count),
        backgroundColor: entries.map((_, idx) => palette[idx % palette.length]),
        borderWidth: 2,
        borderColor: "#fff",
      },
    ],
  };
  if (mixChart) {
    mixChart.data = data;
    mixChart.update();
    return;
  }
  mixChart = new Chart(canvas, {
    type: "doughnut",
    data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: {
        legend: { position: "right", labels: { boxWidth: 10, usePointStyle: true, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: ${ctx.parsed} truck${ctx.parsed === 1 ? "" : "s"}`,
          },
        },
      },
    },
  });
}
