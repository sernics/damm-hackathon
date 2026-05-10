import hashlib
import os
import time

import pandas as pd
import requests

from paths import ROOT, OUT

BBOX = "1.5,41.4,2.5,42.2"
MAPBOX_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
PRECOMPUTED = ROOT / "data" / "custom" / "geo" / "geocoded_direcciones.csv"
MIN_LON, MIN_LAT, MAX_LON, MAX_LAT = 1.5, 41.4, 2.5, 42.2


def use_precomputed_geocodes():
    if not PRECOMPUTED.exists():
        return None
    addresses = pd.read_parquet(OUT / "addresses.parquet")
    cached = pd.read_csv(PRECOMPUTED, engine="python", on_bad_lines="skip")
    cached = cached.rename(columns={"query": "address_full"})
    cached = cached[pd.to_numeric(cached["lat"], errors="coerce").notna()].copy()
    cached["lat"] = pd.to_numeric(cached["lat"], errors="coerce")
    cached["lon"] = pd.to_numeric(cached["lon"], errors="coerce")
    cached = cached[
        cached["lat"].between(MIN_LAT, MAX_LAT)
        & cached["lon"].between(MIN_LON, MAX_LON)
    ].copy()
    merged = addresses.merge(cached[["address_full", "lat", "lon"]], on="address_full", how="left")
    missing = merged["lat"].isna().sum()
    if missing == len(merged):
        return None
    fake = fake_geocode_centroids(write_cache=False).set_index("cliente")
    out = merged[["cliente", "lat", "lon"]].copy()
    out = out.set_index("cliente")
    out["lat"] = out["lat"].fillna(fake["lat"])
    out["lon"] = out["lon"].fillna(fake["lon"])
    out["place_name"] = merged.set_index("cliente")["address_full"].where(merged.set_index("cliente")["lat"].notna(), fake["place_name"])
    out["relevance"] = merged.set_index("cliente")["lat"].notna().astype(float).replace(0.0, 0.35)
    out = out.reset_index()
    out.to_parquet(OUT / "geocoded.parquet", index=False)
    print(f"Loaded precomputed geocodes: {len(out) - missing} matched, {missing} fake-filled")
    return out


def geocode_one(address, token, country="es", bbox=BBOX, timeout=10):
    if not address or pd.isna(address):
        return None, None, None, None
    try:
        response = requests.get(
            MAPBOX_URL.format(query=requests.utils.quote(str(address))),
            params={
                "access_token": token,
                "country": country,
                "bbox": bbox,
                "limit": 1,
                "language": "es",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("features"):
            feature = data["features"][0]
            lon, lat = feature["center"]
            return lat, lon, feature.get("place_name"), feature.get("relevance")
    except Exception as exc:
        print(f"Error geocoding '{address[:60]}': {exc}")
    return None, None, None, None


def geocode_addresses(token, force=False, sleep_s=0.1):
    addresses = pd.read_parquet(OUT / "addresses.parquet")
    cache_path = OUT / "geocoded.parquet"
    if cache_path.exists() and not force:
        cached = pd.read_parquet(cache_path)
        addresses = addresses.merge(cached, on="cliente", how="left")
    else:
        addresses["lat"] = None
        addresses["lon"] = None
        addresses["place_name"] = None
        addresses["relevance"] = None
    pending = addresses[addresses["lat"].isna()]
    print(f"Geocoding {len(pending)} clients")
    for index, row in pending.iterrows():
        lat, lon, place, relevance = geocode_one(row["address_full"], token)
        if lat is None:
            fallback = f"{row['cp']} {row['poblacion']}, Spain"
            lat, lon, place, relevance = geocode_one(fallback, token)
            if lat is not None:
                place = f"[fallback CP] {place}"
        addresses.at[index, "lat"] = lat
        addresses.at[index, "lon"] = lon
        addresses.at[index, "place_name"] = place
        addresses.at[index, "relevance"] = relevance
        if (index + 1) % 50 == 0:
            print(f"{index + 1} done")
            addresses[["cliente", "lat", "lon", "place_name", "relevance"]].to_parquet(cache_path, index=False)
        time.sleep(sleep_s)
    addresses[["cliente", "lat", "lon", "place_name", "relevance"]].to_parquet(cache_path, index=False)
    return addresses


def fake_geocode_centroids(write_cache=True):
    addresses = pd.read_parquet(OUT / "addresses.parquet")
    cp_centroids = {
        "08400": (41.6083, 2.2873),
        "08401": (41.6083, 2.2873),
        "08402": (41.6083, 2.2873),
        "08403": (41.6083, 2.2873),
        "08100": (41.5417, 2.2126),
        "08110": (41.4839, 2.1879),
        "08500": (41.9302, 2.2546),
        "08550": (42.0506, 2.2674),
        "08560": (42.0512, 2.2842),
        "08570": (42.0530, 2.2926),
        "08150": (41.5587, 2.2351),
        "08170": (41.5667, 2.2667),
        "08160": (41.5474, 2.2493),
        "08180": (41.6019, 2.2363),
        "08185": (41.5890, 2.2465),
        "08107": (41.5083, 2.2167),
        "08105": (41.5050, 2.2104),
    }
    default = (41.5417, 2.2126)

    def fake_for_row(row):
        center = cp_centroids.get(str(row["cp"]).zfill(5), default)
        digest = int(hashlib.md5(f"{row['cliente']}".encode()).hexdigest()[:8], 16)
        dx = ((digest % 1000) / 1000.0 - 0.5) * 0.005
        dy = (((digest // 1000) % 1000) / 1000.0 - 0.5) * 0.005
        return pd.Series(
            {
                "lat": center[0] + dy,
                "lon": center[1] + dx,
                "place_name": f"[FAKE] {row['address_full']}",
                "relevance": 0.5,
            }
        )

    coords = addresses.apply(fake_for_row, axis=1)
    out = pd.concat([addresses[["cliente"]], coords], axis=1)
    if write_cache:
        out.to_parquet(OUT / "geocoded.parquet", index=False)
    return out


if __name__ == "__main__":
    token = os.getenv("MAPBOX_TOKEN")
    if use_precomputed_geocodes() is not None:
        pass
    elif not token:
        print("MAPBOX_TOKEN not set, using fake CP-centroid geocoder")
        fake_geocode_centroids()
    else:
        geocode_addresses(token)
