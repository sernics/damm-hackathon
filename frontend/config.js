export const BUSINESS = {
  co2KgPerKm: 0.9,
  costEurPerKm: 2.96,
};

export const MAP = {
  initialZoom: 10.3,
  fitPadding: { top: 80, right: 80, bottom: 80, left: 80 },
  fitDuration: 700,
  zoomScaleSteps: [
    { max: 8.6, scale: 0.28 },
    { max: 9.5, scale: 0.36 },
    { max: 10.4, scale: 0.54 },
    { max: 11.2, scale: 0.78 },
    { max: Infinity, scale: 1 },
  ],
  compactZoomBelow: 10.4,
};

export const CHART = {
  maxRoutes: 8,
  baselineColor: "#d7dadd",
  optimizedColor: "#07945e",
};

const ICON_SVG = {
  route: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19 19 5"/><path d="M13 5h6v6"/></svg>',
  road: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M7 4v16M17 4v16"/><path d="M12 5v3M12 11v3M12 17v3"/></svg>',
  pie: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M12 3v9h9"/><path d="M21 12a9 9 0 1 1-9-9"/></svg>',
  leaf: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-8 6-14 16-14 0 10-6 16-14 16-1 0-2-.2-2-2Z"/><path d="M5 19 14 10"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  truck: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M3 7h11v9H3z"/><path d="M14 10h4l3 3v3h-7z"/><circle cx="7" cy="18" r="1.6"/><circle cx="17" cy="18" r="1.6"/></svg>',
};

export function iconSvg(type) {
  return ICON_SVG[type] || "";
}

export const KPI_CONFIG = [
  { key: "km_saved", label: "Km saved", unit: "km", icon: "route" },
  { key: "total_km", label: "Total km", unit: "km", icon: "road" },
  { key: "avg_occupation_pct", label: "Occupation", unit: "%", icon: "pie" },
  { key: "co2_saved_kg", label: "CO2 saved", unit: "kg", icon: "leaf" },
  { key: "time_saved_min", label: "Time saved", unit: "min", icon: "clock" },
  { key: "trucks_used", label: "Trucks", unit: "", icon: "truck" },
];
