from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .llm import generate_briefing
from .loader import load_route

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="AI Driver Briefing",
    description="Generates compact route briefings for delivery drivers.",
    version="0.2.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/routes")
def list_routes() -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for path in sorted(config.DATA_DIR.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if "stops" not in data:
            continue
        stops = data.get("stops", [])
        client_names = [s.get("client_name", "") for s in stops]
        routes.append({
            "file": str(path),
            "route_id": data.get("route_id", path.stem),
            "route_date": data.get("route_date", ""),
            "driver": data.get("driver", ""),
            "vehicle": data.get("vehicle", ""),
            "departure_time": data.get("departure_time", ""),
            "num_stops": len(stops),
            "clients": client_names,
        })
    return routes


class BriefingRequest(BaseModel):
    route_file: str
    language: str = "es"


class BriefingResponse(BaseModel):
    route_id: str
    briefing: str
    language: str
    num_stops: int


@app.post("/briefing", response_model=BriefingResponse)
def create_briefing(request: BriefingRequest) -> BriefingResponse:
    path = Path(request.route_file)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Route file not found: {request.route_file}")

    if request.language not in ("es", "ca"):
        raise HTTPException(status_code=400, detail="Language must be 'es' or 'ca'.")

    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured.")

    route_data = load_route(path)
    briefing_text = generate_briefing(route_data, language=request.language)

    return BriefingResponse(
        route_id=route_data.get("route_id", ""),
        briefing=briefing_text,
        language=request.language,
        num_stops=len(route_data.get("stops", [])),
    )
