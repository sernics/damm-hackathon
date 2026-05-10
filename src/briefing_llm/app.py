from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .llm import generate_briefing
from .loader import load_order

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="AI Driver Briefing",
    description="Generates operational briefings for delivery drivers from order data and veteran tips.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


class OrderItem(BaseModel):
    material: str
    description: str
    quantity: float
    unit: str


class OrderInput(BaseModel):
    order_date: str
    client_name: str
    total_lines: int
    total_quantity: int
    transport_ids: list[str] = Field(default_factory=list)
    ordered_items: list[OrderItem] = Field(default_factory=list)


class BriefingRequest(BaseModel):
    order: OrderInput | None = None
    order_file: str | None = None
    language: str = "es"


class BriefingResponse(BaseModel):
    client_name: str
    briefing: str
    language: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/orders")
def list_orders() -> list[dict[str, Any]]:
    orders: list[dict[str, Any]] = []
    for path in sorted(config.DATA_DIR.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if "client_name" not in data:
            continue
        orders.append({
            "file": str(path),
            "client_name": data.get("client_name", ""),
            "order_date": data.get("order_date", ""),
            "total_lines": data.get("total_lines", 0),
            "total_quantity": data.get("total_quantity", 0),
        })
    return orders


@app.post("/briefing", response_model=BriefingResponse)
def create_briefing(request: BriefingRequest) -> BriefingResponse:
    if request.order is not None:
        order_data: dict[str, Any] = request.order.model_dump()
    elif request.order_file is not None:
        path = Path(request.order_file)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Order file not found: {request.order_file}")
        order_data = load_order(path)
    else:
        raise HTTPException(status_code=400, detail="Provide either 'order' or 'order_file'.")

    if request.language not in ("es", "ca"):
        raise HTTPException(status_code=400, detail="Language must be 'es' or 'ca'.")

    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured.")

    briefing_text = generate_briefing(order_data, language=request.language)

    return BriefingResponse(
        client_name=order_data.get("client_name", ""),
        briefing=briefing_text,
        language=request.language,
    )
