from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .llm import generate_briefing
from .loader import get_available_dates, load_routes_for_date

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="AI Driver Briefing",
    description="Generates compact route briefings for delivery drivers.",
    version="0.3.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dates")
def list_dates() -> list[str]:
    return get_available_dates()


@app.get("/routes/{date}")
def list_routes(date: str) -> list[dict[str, Any]]:
    routes = load_routes_for_date(date)
    result = []
    for r in routes:
        stops = r["stops"]
        tips_count = sum(1 for s in stops if s.get("has_tips"))
        clients = [
            {"name": s["client_name"], "has_tips": s.get("has_tips", False)}
            for s in stops
        ]
        result.append({
            "route_id": r["route_id"],
            "route_date": r["route_date"],
            "num_stops": len(stops),
            "tips_count": tips_count,
            "clients": clients,
        })
    return result


class BriefingRequest(BaseModel):
    route_date: str
    route_id: str
    language: str = "es"


class BriefingResponse(BaseModel):
    route_id: str
    briefing: str
    language: str
    num_stops: int


@app.post("/briefing", response_model=BriefingResponse)
def create_briefing(request: BriefingRequest) -> BriefingResponse:
    if request.language not in ("es", "ca"):
        raise HTTPException(status_code=400, detail="Language must be 'es' or 'ca'.")

    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured.")

    routes = load_routes_for_date(request.route_date)
    route = next((r for r in routes if r["route_id"] == request.route_id), None)
    if route is None:
        raise HTTPException(status_code=404, detail=f"Route not found: {request.route_id}")

    briefing_text = generate_briefing(route, language=request.language)

    return BriefingResponse(
        route_id=route["route_id"],
        briefing=briefing_text,
        language=request.language,
        num_stops=len(route["stops"]),
    )
