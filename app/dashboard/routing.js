const cache = new Map();
const OSRM_BASE = "https://router.project-osrm.org/route/v1/driving";

function signature(coords) {
  return coords.map(([lon, lat]) => `${lon.toFixed(5)},${lat.toFixed(5)}`).join(";");
}

function chunk(coords, size) {
  if (coords.length <= size) return [coords];
  const result = [];
  for (let i = 0; i < coords.length - 1; i += size - 1) {
    result.push(coords.slice(i, i + size));
  }
  return result;
}

async function fetchOsrm(coords, signal) {
  const path = coords.map(([lon, lat]) => `${lon},${lat}`).join(";");
  const url = `${OSRM_BASE}/${path}?overview=full&geometries=geojson&continue_straight=true`;
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`OSRM ${response.status}`);
  const json = await response.json();
  if (!json.routes?.length) throw new Error("No OSRM route");
  return json.routes[0].geometry.coordinates;
}

export async function roadSnap(coords, { signal } = {}) {
  if (!Array.isArray(coords) || coords.length < 2) return coords;
  const key = signature(coords);
  if (cache.has(key)) return cache.get(key);
  const promise = (async () => {
    try {
      const chunks = chunk(coords, 90);
      const segments = [];
      for (const chunkCoords of chunks) {
        const seg = await fetchOsrm(chunkCoords, signal);
        if (segments.length && seg.length) seg.shift();
        segments.push(...seg);
      }
      return segments.length >= 2 ? segments : coords;
    } catch (error) {
      if (error.name === "AbortError") throw error;
      return coords;
    }
  })();
  cache.set(key, promise);
  try {
    return await promise;
  } catch (error) {
    cache.delete(key);
    throw error;
  }
}
