import math


def haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def route_distance_km(stops, depot):
    if not stops:
        return 0.0
    coords = [(depot["lat"], depot["lon"])]
    coords.extend((float(stop["lat"]), float(stop["lon"])) for stop in stops)
    coords.append((depot["lat"], depot["lon"]))
    return sum(
        haversine_km(a[0], a[1], b[0], b[1])
        for a, b in zip(coords, coords[1:])
    )


def choose_truck_size(pallets, truck_sizes=(3, 6, 8)):
    for size in truck_sizes:
        if pallets <= size + 1e-9:
            return size
    return int(math.ceil(pallets / max(truck_sizes)) * max(truck_sizes))
