"""FastAPI server for the veteran-capture flow.

Endpoints:
- ``GET  /health``                                      Liveness probe.
- ``GET  /``                                            Pick a high-priority
  pair from the queue and redirect to the capture page.
- ``GET  /capture/{client_id}/{driver_id}``             HTML mic page rendered
  with the customer/driver context.
- ``POST /capture/{client_id}/{driver_id}``             Upload audio, transcribe
  with Whisper, extract tips with Claude, moderate, persist JSON, return result.
- ``GET  /capture/queue``                               Top of the priority
  queue as JSON (debugging / orchestration).
- ``GET  /captures``                                    List the JSON capture
  files that have been written so far.

The webapp is intentionally minimalist — there is no auth, no DB, no session.
The driver gets a link, opens it on the phone, talks, leaves. Anything more
elaborate goes against the constraint that the only real driver interface in
production is the printed albaran (mentor session 2).
"""

from __future__ import annotations

import json
import secrets
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import veteran_capture
from veteran_capture.capture.llm import extract_capture, moderate_tips
from veteran_capture.capture.schemas import CaptureResult
from veteran_capture.capture.stt import transcribe_audio
from veteran_capture.config import get_settings
from veteran_capture.exceptions import (
    DataNotFoundError,
    ExtractionError,
    TranscriptionError,
)
from veteran_capture.logging_setup import configure_logging, get_logger
from veteran_capture.writer.markdown import write_all_notes

logger = get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

ALLOWED_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {"webm", "ogg", "wav", "mp3", "m4a", "mpeg", "mpga", "mp4"}
)


# ---------------------------------------------------------------------------
# Cached data accessors (read once on first request, refresh by restart)
# ---------------------------------------------------------------------------


class _Cache:
    customers: pd.DataFrame | None = None
    affinity: pd.DataFrame | None = None
    queue: pd.DataFrame | None = None
    driver_names: dict[str, str] | None = None


def _load_customers() -> pd.DataFrame:
    if _Cache.customers is None:
        path = get_settings().profiles_dir / "customers.parquet"
        if not path.exists():
            raise DataNotFoundError(
                f"customers profile not built yet: {path}. "
                "Run `python -m veteran_capture.cli profiles` first."
            )
        _Cache.customers = pd.read_parquet(path)
    return _Cache.customers


def _load_affinity() -> pd.DataFrame:
    if _Cache.affinity is None:
        path = get_settings().profiles_dir / "driver_customer_affinity.parquet"
        if not path.exists():
            raise DataNotFoundError(
                f"affinity not built yet: {path}. "
                "Run `python -m veteran_capture.cli profiles` first."
            )
        _Cache.affinity = pd.read_parquet(path)
    return _Cache.affinity


def _load_queue() -> pd.DataFrame:
    if _Cache.queue is None:
        path = get_settings().queues_dir / "queue.parquet"
        if not path.exists():
            raise DataNotFoundError(
                f"priority queue not built yet: {path}. "
                "Run `python -m veteran_capture.cli select` first."
            )
        _Cache.queue = pd.read_parquet(path)
    return _Cache.queue


def _driver_names() -> dict[str, str]:
    """Map driver_id -> display name, sourced from Cabecera_Transporte.csv."""
    if _Cache.driver_names is None:
        settings = get_settings()
        cab_path = settings.raw_csv_dir / "Cabecera_Transporte.csv"
        if not cab_path.exists():
            _Cache.driver_names = {}
            return _Cache.driver_names
        cab = pd.read_csv(cab_path, dtype=str, keep_default_na=False)
        cab.columns = [c.strip() for c in cab.columns]
        if "Repartidor" not in cab.columns or "Unnamed: 5" not in cab.columns:
            _Cache.driver_names = {}
            return _Cache.driver_names
        pairs = (
            cab[["Repartidor", "Unnamed: 5"]]
            .dropna()
            .drop_duplicates()
            .rename(columns={"Repartidor": "id", "Unnamed: 5": "name"})
        )
        _Cache.driver_names = {
            str(r["id"]).strip(): str(r["name"]).strip() for _, r in pairs.iterrows()
        }
    return _Cache.driver_names


def _frequency_label(days: float | None) -> str:
    if days is None or days <= 0:
        return "—"
    if days <= 4:
        return "varias veces / semana"
    if days <= 9:
        return "semanal aprox."
    if days <= 18:
        return "quincenal aprox."
    if days <= 35:
        return "mensual aprox."
    return f"cada {days:.0f} dias aprox."


def _safe_list(value: Any) -> list[Any]:
    """Coerce a parquet cell (could be np.ndarray, list, None) into a plain list."""
    if value is None:
        return []
    try:
        return list(value)
    except TypeError:
        return []


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_customer_context(client_id: str, driver_id: str) -> dict[str, Any]:
    customers = _load_customers()
    affinity = _load_affinity()
    cust = customers[customers["client_id"] == client_id]
    if cust.empty:
        raise HTTPException(status_code=404, detail=f"client {client_id} not found")
    row = cust.iloc[0]

    aff = affinity[(affinity["client_id"] == client_id) & (affinity["driver_id"] == driver_id)]
    driver_deliveries = int(aff["n_deliveries"].iloc[0]) if not aff.empty else 0

    address_bits = [
        _safe_str(row.get("calle")),
        _safe_str(row.get("cp")),
        _safe_str(row.get("poblacion")),
    ]
    address = ", ".join([b for b in address_bits if b])
    zone = _safe_str(row.get("zone_code")) or None
    pct_returnable = _safe_float(row.get("pct_returnable_lines"))
    mean_cases = _safe_float(row.get("mean_cases_per_delivery"))
    freq_days = _safe_float(row.get("delivery_frequency_days"))
    return {
        "client_id": client_id,
        "client_name": _safe_str(row.get("client_name")) or client_id,
        "address": address,
        "zone": zone,
        "mean_cases": mean_cases,
        "mean_cases_per_delivery": mean_cases,
        "frequency_label": _frequency_label(freq_days or None),
        "pct_returnable_lines": pct_returnable,
        "pct_returnable": pct_returnable,
        "top_skus": [str(s) for s in _safe_list(row.get("top_skus"))],
        "driver_id": driver_id,
        "driver_name": _driver_names().get(driver_id, driver_id),
        "driver_deliveries": driver_deliveries,
    }


# ---------------------------------------------------------------------------
# Capture persistence
# ---------------------------------------------------------------------------


def _captures_dir() -> Path:
    settings = get_settings()
    out = settings.data_dir / "captures"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _persist_audio(file: UploadFile) -> tuple[Path, int]:
    settings = get_settings()
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    suffix = (file.filename or "").rsplit(".", 1)[-1].lower()
    if suffix not in ALLOWED_AUDIO_EXTENSIONS:
        suffix = "webm"
    target = settings.audio_dir / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(4)}.{suffix}"
    with target.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    size = target.stat().st_size
    logger.info("audio saved", extra={"path": str(target), "bytes": size})
    return target, size


def _persist_capture(result: CaptureResult) -> Path:
    out_dir = _captures_dir()
    name = (
        f"{result.capture.captured_at.strftime('%Y%m%dT%H%M%SZ')}_"
        f"{result.capture.client_id}_{result.capture.driver_id}_"
        f"{uuid.uuid4().hex[:6]}.json"
    )
    path = out_dir / name
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    logger.info("capture json saved", extra={"path": str(path)})
    return path


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def _route_health() -> dict[str, str]:
    return {"status": "ok", "version": veteran_capture.__version__}


def _route_root() -> RedirectResponse:
    try:
        queue = _load_queue()
    except DataNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if queue.empty:
        raise HTTPException(status_code=204, detail="queue is empty")
    first = queue.iloc[0]
    return RedirectResponse(
        url=f"/capture/{first['client_id']}/{first['driver_id']}",
        status_code=302,
    )


def _route_queue(limit: int = 25) -> JSONResponse:
    try:
        queue = _load_queue().head(max(0, limit))
    except DataNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    records = queue.to_dict(orient="records")
    for rec in records:
        for k, v in list(rec.items()):
            if hasattr(v, "isoformat"):
                rec[k] = v.isoformat()
    return JSONResponse(content=records)


def _route_list_captures(limit: int = 50) -> JSONResponse:
    out_dir = _captures_dir()
    files = sorted(out_dir.glob("*.json"), reverse=True)[: max(0, limit)]
    items: list[dict[str, Any]] = []
    for path in files:
        try:
            items.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return JSONResponse(content=items)


def _route_dashboard(request: Request) -> HTMLResponse:
    """Operations dashboard: paginated, filterable view of the manifest."""
    settings = get_settings()
    manifest_path = settings.veteran_notes_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "manifest.json not built yet. Run "
                "`python -m veteran_capture.cli write-notes` first."
            ),
        )
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "version": veteran_capture.__version__,
            "manifest_url": "/api/manifest",
        },
    )


def _route_manifest_api() -> JSONResponse:
    """Serve the manifest JSON straight from disk (always fresh)."""
    settings = get_settings()
    manifest_path = settings.veteran_notes_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=503, detail="manifest.json not built yet")
    return JSONResponse(
        content=json.loads(manifest_path.read_text(encoding="utf-8"))
    )


def _route_client_md(client_id: str) -> HTMLResponse:
    """Render the per-client markdown as a simple read-only HTML view."""
    settings = get_settings()
    md_path = settings.veteran_notes_dir / f"{client_id}.md"
    if not md_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"no captured tips for {client_id} yet",
        )
    body = md_path.read_text(encoding="utf-8")
    # Tiny inline render — markdown as <pre> is plenty for this demo.
    safe = (
        body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    html = (
        "<!doctype html><meta charset='utf-8'>"
        f"<title>{client_id} — veteran notes</title>"
        "<style>body{background:#0e0e10;color:#f5f5f7;font-family:-apple-system,sans-serif;"
        "max-width:760px;margin:40px auto;padding:0 20px;line-height:1.5}"
        "pre{background:#1a1a1f;border:1px solid #2a2a31;border-radius:10px;padding:18px;"
        "white-space:pre-wrap;word-wrap:break-word;font-size:14px}"
        "a{color:#e30613}</style>"
        f"<a href='/dashboard'>&larr; back to dashboard</a><pre>{safe}</pre>"
    )
    return HTMLResponse(content=html)


def _route_capture_page(client_id: str, driver_id: str, request: Request) -> HTMLResponse:
    try:
        ctx = _build_customer_context(client_id, driver_id)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    ctx["version"] = veteran_capture.__version__
    return templates.TemplateResponse(request, "prompt.html", ctx)


async def _route_capture_audio(
    client_id: str,
    driver_id: str,
    audio: UploadFile,
) -> JSONResponse:
    if audio is None or audio.filename is None:
        raise HTTPException(status_code=400, detail="missing 'audio' file in form-data")

    audio_path, size = _persist_audio(audio)
    if size < 200:
        audio_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="audio too small (likely empty recording)")

    try:
        transcript = transcribe_audio(audio_path)
    except TranscriptionError as exc:
        audio_path.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=f"transcription failed: {exc}") from exc

    try:
        customer_ctx = _build_customer_context(client_id, driver_id)
    except HTTPException:
        customer_ctx = {"client_id": client_id, "driver_id": driver_id}

    try:
        capture = extract_capture(
            transcript=transcript,
            client_id=client_id,
            driver_id=driver_id,
            customer_context=customer_ctx,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=f"extraction failed: {exc}") from exc

    verdict = moderate_tips(capture.tips)
    result = CaptureResult(capture=capture, moderation=verdict)
    _persist_capture(result)

    # Audio is transient — delete after successful processing (privacy policy).
    audio_path.unlink(missing_ok=True)

    notes_path: str | None = None
    try:
        report = write_all_notes()
        notes_path = str(report.out_dir / f"{client_id}.md")
    except Exception:
        logger.exception("post-capture markdown render failed (non-fatal)")

    payload = json.loads(result.model_dump_json())
    payload["notes_path"] = notes_path
    return JSONResponse(content=payload)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Veteran Capture",
        version=veteran_capture.__version__,
        description=(
            "Active capture of tacit driver knowledge for the Damm Smart Truck "
            "briefing pipeline."
        ),
    )
    app.get("/health")(_route_health)
    app.get("/", response_class=HTMLResponse)(_route_root)
    app.get("/dashboard", response_class=HTMLResponse)(_route_dashboard)
    app.get("/api/manifest")(_route_manifest_api)
    app.get("/clients/{client_id}", response_class=HTMLResponse)(_route_client_md)
    app.get("/capture/queue")(_route_queue)
    app.get("/captures")(_route_list_captures)
    app.get("/capture/{client_id}/{driver_id}", response_class=HTMLResponse)(_route_capture_page)
    app.post("/capture/{client_id}/{driver_id}")(_route_capture_audio)
    return app


app = create_app()
