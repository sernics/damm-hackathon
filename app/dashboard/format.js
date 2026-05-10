import { BUSINESS } from "./config.js";

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}

function isMissing(value) {
  return value === undefined || value === null || Number.isNaN(Number(value));
}

export function formatKpi(value, unit, { fractionDigits } = {}) {
  if (isMissing(value)) return "Baseline";
  const numeric = Number(value);
  const digits = fractionDigits ?? (unit ? 1 : 0);
  const formatted = numeric.toLocaleString("en-US", { maximumFractionDigits: digits });
  return unit ? `${formatted} ${unit}` : formatted;
}

export function formatPct(value, digits = 1) {
  if (isMissing(value)) return "0%";
  return `${Number(value).toFixed(digits)}%`;
}

export function formatCo2(kg) {
  return `${Number(kg || 0).toFixed(1)} kg`;
}

export function formatCostFromKm(kmSaved) {
  const eur = Math.round(Number(kmSaved || 0) * BUSINESS.costEurPerKm);
  return `€${eur.toLocaleString("en-US")}`;
}

export function formatHours(minutes) {
  if (isMissing(minutes)) return "";
  return `${(Number(minutes) / 60).toFixed(1)} h`;
}
