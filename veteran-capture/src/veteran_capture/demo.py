"""Seed plausible capture JSONs for the demo.

These are written to `data/captures/` exactly as the live capture pipeline
would write them. The demo flow then runs `write-notes` over them to render
the markdown KB. Lets us show end-to-end output during the pitch even when
there is no time to record real audio for every customer.

The seed data is hand-authored, mentor-grounded, and explicitly flagged in
the markdown footer of each client file as `n_capture_files=N`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from veteran_capture.capture.schemas import CaptureResult, ExtractedCapture, ModerationVerdict, Tip
from veteran_capture.config import get_settings
from veteran_capture.logging_setup import get_logger

logger = get_logger(__name__)


# Hand-authored seed tips. Each entry below produces one CaptureResult JSON.
# Realistic enough to demo the briefing flow without needing real audio.
SEED_CAPTURES: list[dict[str, Any]] = [
    {
        "client_id": "9100043170",
        "client_name": "CA LA SETE",
        "driver_id": "850018",
        "days_ago": 4,
        "transcript": (
            "En Ca la Sete tienes que aparcar en el lateral del local, hay zona "
            "de carga y descarga durante la mañana. Marta es la encargada, "
            "abre puntual a las nueve y media. Si llevas barriles, los baja "
            "ella misma con la transpaleta porque la entrada principal tiene "
            "un escalon."
        ),
        "tips": [
            ("parking", "Aparca en el lateral del local; hay zona de carga y descarga durante la mañana.", "high"),
            ("contact_person", "Marta es la encargada. Llama si no abren a la primera.", "medium"),
            ("hours", "Abre puntual a las 9:30 h.", "high"),
            ("access", "La entrada principal tiene un escalon — no usar para barriles.", "high"),
            ("barrels", "Marta los baja ella misma con la transpaleta del local.", "medium"),
        ],
    },
    {
        "client_id": "9100043170",
        "client_name": "CA LA SETE",
        "driver_id": "850010",
        "days_ago": 18,
        "transcript": (
            "En Ca la Sete, importante: aparcar en el lateral, no en la "
            "fachada principal. La acera es estrecha y se han quejado los "
            "vecinos. Suelen pedir mucho retornable, hay que bajar bastantes "
            "cascos."
        ),
        "tips": [
            ("parking", "Aparcar en el lateral, no en la fachada principal: acera estrecha, vecinos protestan.", "high"),
            ("empties", "Cliente con mucho retornable; revisar bien el conteo de cascos al recoger.", "medium"),
        ],
    },
    {
        "client_id": "9100264285",
        "client_name": "PITAPES CALDERI 3 BRANQUES VALLES",
        "driver_id": "850018",
        "days_ago": 7,
        "transcript": (
            "En Pitapes Calderi del Valles aparcas en el parking de delante "
            "del centro comercial, no en la calle. Hay un guardia que te abre "
            "el porton para entrar. El acceso es por la rampa lateral, no por "
            "la entrada principal del local."
        ),
        "tips": [
            ("parking", "Aparcar en el parking del centro comercial, no en la calle.", "high"),
            ("contact_person", "Hay un guardia en el porton; te lo abre al llegar.", "high"),
            ("access", "Acceso por la rampa lateral, nunca por la entrada principal del local.", "high"),
        ],
    },
    {
        "client_id": "9100527964",
        "client_name": "DROGUERIA JUNYENT",
        "driver_id": "855184",
        "days_ago": 12,
        "transcript": (
            "Drogueria Junyent en Gurb. Llamar antes de salir porque a veces "
            "estan cerrados a primera hora. Joan es el encargado, tiene su "
            "movil en el albaran. La carga la dejas en la trasera del almacen, "
            "hay un timbre."
        ),
        "tips": [
            ("contact_person", "Joan es el encargado. Su movil esta en el albaran — llama antes de salir.", "high"),
            ("hours", "A veces cierran a primera hora — confirmar antes.", "medium"),
            ("access", "Descarga por la trasera del almacen, hay timbre.", "high"),
        ],
    },
    {
        "client_id": "9100056689",
        "client_name": "RESTAURANT NOU PAMPLONA",
        "driver_id": "855190",
        "days_ago": 9,
        "transcript": (
            "El Nou Pamplona en Vic, calle 11 de Setembre, descarga por la "
            "puerta lateral del restaurante, no por la principal. Los barriles "
            "los bajan al sotano por las escaleras del local — ojo si vas con "
            "transpaleta no entras bien. Antoni es el dueño."
        ),
        "tips": [
            ("access", "Descarga por la puerta lateral, no por la principal.", "high"),
            ("barrels", "Los barriles van al sotano por escaleras — la transpaleta no encaja bien, hacerlo a mano.", "high"),
            ("contact_person", "Antoni es el dueño.", "medium"),
        ],
    },
    {
        "client_id": "9100158696",
        "client_name": "LLAVORS I CEREALS FONT",
        "driver_id": "855184",
        "days_ago": 21,
        "transcript": (
            "Llavors i Cereals Font en Vic, carretera de Prats de Lluçanes. "
            "Es un cliente grande de ED13 y agua Veri. Aparcas justo delante "
            "del almacen, hay rampa para la transpaleta sin problema. Abren "
            "a las siete de la mañana, prefieren reparto temprano."
        ),
        "tips": [
            ("parking", "Aparcar justo delante del almacen — espacio amplio.", "high"),
            ("access", "Rampa para la transpaleta sin obstaculos.", "high"),
            ("hours", "Abren a las 7:00 h. Prefieren reparto temprano.", "high"),
        ],
    },
    {
        "client_id": "9100527972",
        "client_name": "VALERO VALLES",
        "driver_id": "855203",
        "days_ago": 3,
        "transcript": (
            "Valero del Valles. La calle es estrecha, mejor entrar por el norte. "
            "El propietario sale el mismo a recibirte y te ayuda con la descarga. "
            "Lleva muchos años, te conoce."
        ),
        "tips": [
            ("warnings", "Calle estrecha, entrar por el norte para no quedar atrapado.", "high"),
            ("contact_person", "El propietario sale a recibirte y ayuda con la descarga.", "high"),
        ],
    },
]


def _to_capture_result(seed: dict[str, Any], driver_names: dict[str, str]) -> CaptureResult:
    captured_at = datetime.now(UTC) - timedelta(days=int(seed["days_ago"]))
    tips = [Tip(topic=t, text=text, confidence=conf) for t, text, conf in seed["tips"]]
    capture = ExtractedCapture(
        client_id=seed["client_id"],
        driver_id=seed["driver_id"],
        captured_at=captured_at,
        tips=tips,
        raw_transcript=seed["transcript"],
        audio_seconds=None,
    )
    # Auto-accept everything in the demo seed (it's hand-authored, no
    # offensive content). Real captures still go through the moderation pass.
    moderation = ModerationVerdict(accepted=tips, rejected=[], notes="seed-auto-accepted")
    return CaptureResult(capture=capture, moderation=moderation)


def write_seed_captures(*, overwrite: bool = False) -> int:
    """Write all SEED_CAPTURES to disk as if they had come from the capture flow."""
    settings = get_settings()
    out_dir = settings.data_dir / "captures"
    out_dir.mkdir(parents=True, exist_ok=True)

    if overwrite:
        for stale in out_dir.glob("*.seed.json"):
            stale.unlink()

    written = 0
    for seed in SEED_CAPTURES:
        result = _to_capture_result(seed, driver_names={})
        ts = result.capture.captured_at.strftime("%Y%m%dT%H%M%SZ")
        name = f"{ts}_{result.capture.client_id}_{result.capture.driver_id}_{uuid.uuid4().hex[:6]}.seed.json"
        path: Path = out_dir / name
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        written += 1
    logger.info(
        "seeded demo captures",
        extra={"written": written, "out_dir": str(out_dir)},
    )
    return written
