"""
Build a RouteRequest for one example transport from the raw CSVs.

Heuristics applied:
- Visit order = row order in Detalle_entrega (assumption A1 from the cerebro).
- Cluster id  = first 8 chars of ZonaTransp (very rough park-and-walk grouping).
- Returnable detection: SKU prefix CJ*, BRL*V, 3ENV*, *V suffix, PL*V.
- Fragile detection: family 00VE (vinos), 00LI (licores), or BOT/BRL UMV with
  glass material.
- cases_equiv: 1.0 for CAJ, 4.0 for BRL (mentor: a 30L barrel is ~4 cases),
  0.05 for UN/BOT (small).
- Truck assumption: 6-pallet truck unless overridden (most common at Mollet).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

from contracts import (
    Delivery,
    Driver,
    Line,
    RouteRequest,
    Stop,
    Truck,
)

ROOT = Path(__file__).resolve().parents[2]
HACK = ROOT / "data" / "csv" / "Hackaton"
GEO = ROOT / "data" / "custom" / "geo" / "geocoded_direcciones.csv"

RETURNABLE_RE = re.compile(r"^(CJ\d|BRL\d+V|3ENV|PL\d+V|BT\d+V)")


def is_returnable(material: str, name: str) -> bool:
    return bool(RETURNABLE_RE.match(material)) or material.endswith("V") and len(material) >= 4


def is_fragile(material: str, name: str, family: str | None) -> bool:
    name_u = (name or "").upper()
    if family in {"00VE", "00LI"}:
        return True
    if "VIDRIO" in name_u or "BOT.1/" in name_u:
        return True
    return False


def cases_equiv(qty: float, umv: str) -> float:
    if umv == "CAJ":
        return float(qty)
    if umv == "BRL":
        return float(qty) * 4.0
    if umv in {"UN", "BOT", "BID", "PAK", "EST"}:
        return float(qty) * 0.5
    return float(qty)


def load_geo() -> dict[str, tuple[float, float]]:
    if not GEO.exists():
        return {}
    g = pd.read_csv(GEO)
    out: dict[str, tuple[float, float]] = {}
    for _, r in g.iterrows():
        if pd.notna(r["lat"]) and pd.notna(r["lon"]):
            out[r["query"].strip()] = (float(r["lat"]), float(r["lon"]))
    return out


def address_query(row: pd.Series) -> str:
    calle = (row.get("Calle") or "").strip()
    cp = str(row.get("CP") or "").strip()
    pob = (row.get("Población") or "").strip()
    return f"{calle}, {cp} {pob}, Spain"


def load_materials() -> pd.DataFrame:
    m = pd.read_csv(HACK / "Materiales_zubic.csv")
    m = m[["Material", "Ubic."]].rename(columns={"Ubic.": "warehouse_loc"})
    m = m.drop_duplicates("Material")
    return m


def family_from_name(name: str) -> str | None:
    n = (name or "").upper()
    if "ESTRELLA" in n or "DAMM" in n or "CERVEZA" in n or "VOLL" in n:
        return "00CZ"
    if "AGUA" in n or "VICHY" in n or "VERI" in n or "FONT" in n:
        return "00AG"
    if "CAFE" in n or "BONKA" in n:
        return "00CF"
    if "VINO" in n or "RIOJA" in n:
        return "00VE"
    if "LICOR" in n or "WHISKY" in n or "GINEBRA" in n or "RON" in n:
        return "00LI"
    if "ZUMO" in n or "GRANINI" in n:
        return "00ZU"
    if "REFRESCO" in n or "COCA" in n or "AQUARIUS" in n or "BITTER" in n:
        return "00RF"
    if "LECHE" in n or "CACAOLAT" in n or "LACTEO" in n:
        return "00LT"
    return None


def cluster_id(zone: str | None) -> str | None:
    if not zone:
        return None
    return zone[:9]


def list_transports(detalle: pd.DataFrame, route: str = "DR0027") -> pd.DataFrame:
    sub = detalle[detalle["Ruta"] == route]
    grp = sub.groupby("Transporte").agg(
        date=("FECHA", "first"),
        n_lines=("Material", "size"),
        n_deliveries=("Entrega", "nunique"),
        n_clients=("Destinatario mcía..1", "nunique"),
    )
    return grp.sort_values("n_deliveries", ascending=False)


def build_request(
    transport_id: int,
    truck_pallets: int = 6,
    detalle: pd.DataFrame | None = None,
) -> RouteRequest:
    if detalle is None:
        detalle = pd.read_csv(HACK / "Detalle_entrega.csv")
    materials = load_materials()
    geo = load_geo()

    sub = detalle[detalle["Transporte"] == transport_id].copy()
    if sub.empty:
        raise ValueError(f"No rows for transport {transport_id}")

    sub = sub.merge(materials, on="Material", how="left")
    sub["warehouse_loc"] = sub["warehouse_loc"].fillna("ZCG")

    head = sub.iloc[0]
    fecha = head["FECHA"]
    ruta = head["Ruta"]
    repartidor_id = str(head["Repartidor"]).strip()
    repartidor_name = str(head["Destinatario mcía."]).strip()

    # Stops in the order they first appear in the file (assumption A1)
    stop_records: list[Stop] = []
    seen_clients: dict[str, int] = {}

    for _, r in sub.iterrows():
        client_id = str(r["Destinatario mcía..1"]).strip()
        if client_id not in seen_clients:
            seen_clients[client_id] = len(seen_clients) + 1

    # Group lines by client and delivery
    client_groups: dict[str, dict[str, list[pd.Series]]] = {}
    client_meta: dict[str, dict] = {}
    for _, r in sub.iterrows():
        client_id = str(r["Destinatario mcía..1"]).strip()
        delivery_id = str(r["Entrega"]).strip()
        client_groups.setdefault(client_id, {}).setdefault(delivery_id, []).append(r)
        if client_id not in client_meta:
            client_meta[client_id] = {
                "name": (r.get("Nombre 1") or client_id),
                "address": ", ".join(
                    [
                        str(r.get("Calle") or "").strip(),
                        str(r.get("CP") or "").strip(),
                        str(r.get("Población") or "").strip(),
                    ]
                ),
                "zone": (r.get("ZonaTransp") or None),
                "geo_query": address_query(r),
            }

    for client_id, deliveries_dict in client_groups.items():
        meta = client_meta[client_id]
        lat_lon = geo.get(meta["geo_query"])
        deliveries: list[Delivery] = []
        for delivery_id, rows in deliveries_dict.items():
            lines: list[Line] = []
            for r in rows:
                mat = str(r["Material"]).strip()
                name = str(r["Denominación"]).strip()
                qty = int(r["Cantidad entrega"]) if pd.notna(r["Cantidad entrega"]) else 0
                if qty <= 0:
                    continue
                umv = str(r["Un.medida venta"]).strip() or "CAJ"
                if umv not in {
                    "CAJ", "UN", "BOT", "BRL", "TB", "PAK", "EST", "PQ", "TIR", "BID", "ZPR"
                }:
                    umv = "UN"
                fam = family_from_name(name)
                lines.append(
                    Line(
                        material=mat,
                        name=name,
                        qty=qty,
                        umv=umv,  # type: ignore[arg-type]
                        family=fam,
                        warehouse_loc=str(r["warehouse_loc"]).strip() or "ZCG",
                        is_returnable=is_returnable(mat, name),
                        fragile=is_fragile(mat, name, fam),
                        cases_equiv=cases_equiv(qty, umv),
                    )
                )
            if lines:
                deliveries.append(Delivery(delivery_id=delivery_id, lines=lines))

        if not deliveries:
            continue

        stop_records.append(
            Stop(
                order=seen_clients[client_id],
                client_id=client_id,
                client_name=str(meta["name"])[:80],
                address=str(meta["address"])[:200],
                lat=lat_lon[0] if lat_lon else None,
                lon=lat_lon[1] if lat_lon else None,
                zone=meta["zone"],
                cluster_id=cluster_id(meta["zone"]),
                interior_distance_m=0.0,
                time_windows=[],
                deliveries=deliveries,
            )
        )

    stop_records.sort(key=lambda s: s.order)
    # Renumber 1..N to be safe
    for i, s in enumerate(stop_records, start=1):
        s.order = i

    truck_max_cases = {3: 180, 6: 360, 8: 480}[truck_pallets]
    return RouteRequest(
        transport_id=str(transport_id),
        route_code=ruta,
        date=fecha,
        driver=Driver(id=repartidor_id, name=repartidor_name, license_level=3),
        truck=Truck(
            id=f"TRK-{repartidor_id}",
            plate=None,
            pallet_slots=truck_pallets,
            levels_per_pallet=4,
            max_cases=truck_max_cases,
            lateral_access=True,
        ),
        stops=stop_records,
    )


def main() -> None:
    detalle = pd.read_csv(HACK / "Detalle_entrega.csv")
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        transport_id = int(sys.argv[1])
    else:
        # Pick the DR0027 transport with the most deliveries (closest to "real route")
        candidates = list_transports(detalle, "DR0027")
        transport_id = int(candidates.index[0])
        print(
            f"Picked transport {transport_id} "
            f"({candidates.iloc[0]['n_deliveries']} deliveries, "
            f"{candidates.iloc[0]['n_clients']} clients).",
            file=sys.stderr,
        )

    req = build_request(transport_id, truck_pallets=8, detalle=detalle)
    out_path = Path(__file__).parent / "data" / f"route_{transport_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(req.model_dump_json(indent=2))
    print(
        f"Saved {out_path} — {len(req.stops)} stops, "
        f"{sum(len(d.lines) for s in req.stops for d in s.deliveries)} lines",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
