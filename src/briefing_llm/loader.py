from __future__ import annotations

import ast
import csv
import json
from typing import Any

from . import config

_manifest_cache: dict[str, dict[str, Any]] | None = None


def _load_manifest() -> dict[str, dict[str, Any]]:
    global _manifest_cache
    if _manifest_cache is not None:
        return _manifest_cache
    with open(config.MANIFEST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    _manifest_cache = {}
    for entry in data.get("entries", []):
        name = entry.get("client_name", "").strip().upper()
        if name:
            _manifest_cache[name] = entry
    return _manifest_cache


def get_client_info(client_name: str) -> dict[str, Any] | None:
    manifest = _load_manifest()
    return manifest.get(client_name.strip().upper())


def get_client_tips_text(client_name: str) -> str:
    info = get_client_info(client_name)
    if info is None:
        return ""
    tips = info.get("tips", [])
    if not tips:
        return ""
    lines = [t["text"] for t in tips if t.get("text")]
    return "\n".join(f"- {line}" for line in lines)


def client_has_tips(client_name: str) -> bool:
    info = get_client_info(client_name)
    if info is None:
        return False
    return len(info.get("tips", [])) > 0


def get_client_address(client_name: str) -> str:
    info = get_client_info(client_name)
    if info is None:
        return ""
    return info.get("address", "")


def _parse_transport_ids(raw: str) -> list[str]:
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except (ValueError, SyntaxError):
        pass
    return [raw.strip("[]' ")]


def load_all_routes() -> list[dict[str, Any]]:
    routes: dict[str, dict[str, Any]] = {}
    with open(config.ORDERS_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row["order_date"]
            transport_ids = _parse_transport_ids(row["transport_ids"])
            primary_id = transport_ids[0]
            key = f"{date}|{primary_id}"

            if key not in routes:
                routes[key] = {
                    "route_id": primary_id,
                    "route_date": date,
                    "stops": [],
                }

            client_name = row["client_name"]
            address = get_client_address(client_name)
            has_tips = client_has_tips(client_name)

            routes[key]["stops"].append({
                "stop_number": len(routes[key]["stops"]) + 1,
                "client_name": client_name,
                "address": address,
                "has_tips": has_tips,
            })

    return sorted(routes.values(), key=lambda r: (r["route_date"], r["route_id"]))


def load_routes_for_date(date: str) -> list[dict[str, Any]]:
    all_routes = load_all_routes()
    return [r for r in all_routes if r["route_date"] == date]


def get_available_dates() -> list[str]:
    dates: set[str] = set()
    with open(config.ORDERS_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dates.add(row["order_date"])
    return sorted(dates)


def collect_all_tips(stops: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    for stop in stops:
        client = stop.get("client_name", "")
        tips = get_client_tips_text(client)
        if not tips:
            continue
        address = stop.get("address", "")
        sections.append(f"### {client} -- {address}\n\n{tips}")
    if not sections:
        return "(No veteran tips available for any client on this route.)"
    return "\n\n".join(sections)


def load_system_prompt() -> str:
    return config.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_user_message(route: dict[str, Any], all_tips: str) -> str:
    template = config.USER_TEMPLATE_PATH.read_text(encoding="utf-8")

    stops_with_tips = [
        {
            "stop": s.get("stop_number", i + 1),
            "client": s.get("client_name", ""),
            "address": s.get("address", ""),
        }
        for i, s in enumerate(route.get("stops", []))
        if s.get("has_tips", False)
    ]

    compact_route = {
        "route_id": route.get("route_id", ""),
        "route_date": route.get("route_date", ""),
        "total_stops": len(route.get("stops", [])),
        "stops_with_tips": stops_with_tips,
    }

    route_json_str = json.dumps(compact_route, ensure_ascii=False, indent=2)
    message = template.replace("{{ route_json }}", route_json_str)
    message = message.replace("{{ all_tips }}", all_tips)
    return message
