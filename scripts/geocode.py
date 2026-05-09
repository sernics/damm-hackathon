import csv
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
path = ROOT / "data/csv/Hackaton/Direcciones.csv"
out_path = ROOT / "data/geocoded_direcciones.csv"

GEOAPIFY_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"


def geocode_geoapify(query: str, api_key: str) -> tuple[float, float] | None:
    resp = requests.get(
        GEOAPIFY_GEOCODE_URL,
        params={"text": query, "apiKey": api_key},
        headers={"Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    feats = data.get("features") or []
    if not feats:
        return None
    lon, lat = feats[0]["geometry"]["coordinates"][:2]
    return float(lat), float(lon)


def main() -> None:
    api_key = os.environ.get("GEOAPIFY_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set GEOAPIFY_API_KEY to your Geoapify API key.")

    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    queries: list[str] = []
    seen: set[str] = set()
    for row in rows:
        q = f"{row['Calle'].strip()}, {row['CP'].strip()} {row['Población'].strip()}, Spain"
        if q not in seen:
            seen.add(q)
            queries.append(q)

    with out_path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["query", "lat", "lon", "error"])
        out.flush()
        for q in queries:
            try:
                latlon = geocode_geoapify(q, api_key)
                if latlon is None:
                    writer.writerow([q, "", "", "no result"])
                    print(q, "->", "no result", flush=True)
                else:
                    lat, lon = latlon
                    writer.writerow([q, lat, lon, ""])
                    print(q, "->", latlon, flush=True)
            except Exception as e:
                writer.writerow([q, "", "", repr(e)])
                print(q, "->", "error:", e, flush=True)
            out.flush()


if __name__ == "__main__":
    main()
