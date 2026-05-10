from __future__ import annotations

import json
import os
from typing import Any

from . import config

_manifest_cache: dict[str, dict[str, Any]] | None = None
_manifest_mtime: float | None = None
_truck_plan_cache: dict[str, Any] | None = None
_truck_plan_mtime: float | None = None


def _load_manifest() -> dict[str, dict[str, Any]]:
    global _manifest_cache, _manifest_mtime
    current_mtime = os.path.getmtime(config.MANIFEST_PATH)
    if _manifest_cache is not None and _manifest_mtime == current_mtime:
        return _manifest_cache
    with open(config.MANIFEST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    fresh: dict[str, dict[str, Any]] = {}
    for entry in data.get("entries", []):
        name = entry.get("client_name", "").strip().upper()
        if not name:
            continue
        # 18 trade names are shared by two different client_ids in the
        # dataset. The truck plan only carries client_name, so we cannot
        # disambiguate. Prefer the entry that has captured tips so the
        # briefing still surfaces them when at least one of the collided
        # clients is filled.
        existing = fresh.get(name)
        if existing is None:
            fresh[name] = entry
            continue
        if entry.get("status") == "filled" and existing.get("status") != "filled":
            fresh[name] = entry
    _manifest_cache = fresh
    _manifest_mtime = current_mtime
    return _manifest_cache


def _load_truck_plan() -> dict[str, Any]:
    global _truck_plan_cache, _truck_plan_mtime
    current_mtime = os.path.getmtime(config.TRUCK_PLAN_PATH)
    if _truck_plan_cache is not None and _truck_plan_mtime == current_mtime:
        return _truck_plan_cache
    with open(config.TRUCK_PLAN_PATH, encoding="utf-8") as f:
        _truck_plan_cache = json.load(f)
    _truck_plan_mtime = current_mtime
    return _truck_plan_cache


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


def get_available_dates() -> list[str]:
    plan = _load_truck_plan()
    return sorted(plan.keys())


def load_routes_for_date(date: str) -> list[dict[str, Any]]:
    plan = _load_truck_plan()
    raw_routes = plan.get(date, [])
    routes: list[dict[str, Any]] = []

    for idx, stop_list in enumerate(raw_routes):
        stops = []
        for i, s in enumerate(stop_list):
            client_name = s.get("client_name", "")
            stops.append({
                "stop_number": i + 1,
                "client_name": client_name,
                "address": get_client_address(client_name),
                "has_tips": client_has_tips(client_name),
            })

        routes.append({
            "route_id": str(idx + 1),
            "route_date": date,
            "stops": stops,
        })

    return routes


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
