function haversineLike(a, b) {
  const dx = (b[0] - a[0]) * Math.cos(((a[1] + b[1]) / 2) * Math.PI / 180);
  const dy = b[1] - a[1];
  return Math.sqrt(dx * dx + dy * dy);
}

function cumulativeDistances(coords) {
  const out = [0];
  for (let i = 1; i < coords.length; i++) {
    out.push(out[i - 1] + haversineLike(coords[i - 1], coords[i]));
  }
  return out;
}

export function polylineAt(coords, t) {
  if (!coords || coords.length < 2) return coords?.[0] || [0, 0];
  const cum = cumulativeDistances(coords);
  const total = cum[cum.length - 1];
  if (total === 0) return coords[0];
  const target = total * Math.max(0, Math.min(1, t));
  let i = 1;
  while (i < cum.length && cum[i] < target) i++;
  if (i >= coords.length) return coords[coords.length - 1];
  const segLen = cum[i] - cum[i - 1] || 1e-9;
  const localT = (target - cum[i - 1]) / segLen;
  const a = coords[i - 1];
  const b = coords[i];
  return [a[0] + (b[0] - a[0]) * localT, a[1] + (b[1] - a[1]) * localT];
}

export function midpoint(coords) {
  return polylineAt(coords, 0.5);
}
