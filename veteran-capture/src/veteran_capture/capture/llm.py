"""Anthropic Claude wrappers: structured tip extraction + content moderation.

The extraction prompt is deliberately strict:

- Forces the model to return tool input that matches our `Tip` schema (no
  free-form prose, so no hallucinated fields).
- Includes the customer context so the model can ground each tip ("the driver
  is talking about CLIENT X who delivers retornable barrels every Tuesday").
- Instructs the model that if the transcript is empty, ambiguous, or off-topic,
  the correct answer is an empty list.

The moderation pass is a second, lighter call (Haiku) that classifies each
extracted tip as `accepted` or `rejected` based on appropriateness.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from anthropic import Anthropic
from pydantic import ValidationError

from veteran_capture.capture.schemas import (
    ExtractedCapture,
    ModerationVerdict,
    Tip,
)
from veteran_capture.config import get_settings
from veteran_capture.exceptions import ConfigurationError, ExtractionError
from veteran_capture.logging_setup import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------


def _client() -> Anthropic:
    settings = get_settings()
    if not settings.anthropic_api_key.startswith("sk-ant"):
        raise ConfigurationError("ANTHROPIC_API_KEY is missing or malformed in .env")
    return Anthropic(api_key=settings.anthropic_api_key)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


_EXTRACTION_SYSTEM = """\
Eres un sistema que extrae consejos operativos concretos de transcripciones \
de repartidores veteranos de DDI (Damm). Tu trabajo es transformar lo que \
dijo el conductor en una lista de tips estructurados que otro conductor \
nuevo pueda leer en su albaran impreso.

Reglas innegociables:
- No inventes nada. Si algo no se dice en la transcripcion, no lo escribas.
- Cada tip debe ser corto (1 o 2 lineas, en castellano) y operativamente util.
- Cada tip lleva un topic de la lista cerrada y un nivel de confianza.
- Si la transcripcion no contiene info util, devuelve una lista vacia.
- Si detectas ataques personales o lenguaje ofensivo hacia el cliente, baja \
  la confianza a "low" y marca el topic como "other"; el filtro posterior \
  los descartara.

Topics permitidos (literal):
- "parking"        : donde aparcar / acceso al cliente con el camion
- "access"         : entrada al local, escalones, rampa, callejon
- "contact_person" : quien atiende, telefono, horario de la persona
- "barrels"        : manejo especifico de barriles retornables
- "empties"        : recogida de cascos vacios, donde se dejan
- "hours"          : horario real de apertura, ventana de reparto
- "warnings"       : avisos puntuales (obras, calle cortada, cliente complicado)
- "other"          : cualquier cosa util que no encaje arriba

Confianza:
- "high"   : el conductor lo afirma con seguridad, sin matices
- "medium" : el conductor lo dice pero con dudas o solo a veces
- "low"    : el conductor lo deja entrever; util pero conviene confirmar

Devuelve estrictamente la herramienta `record_tips` con los tips extraidos.\
"""


_MODERATION_SYSTEM = """\
Eres un filtro de moderacion. Recibes una lista de tips operativos sobre \
clientes de DDI y devuelves dos listas: `accepted` y `rejected`.

PRIORIDAD ABSOLUTA: preservar el valor operativo. La regla por defecto \
es ACEPTAR. Solo redactas datos PII estrictamente sensibles, y solo \
rechazas si el tip no aporta valor operativo o no se puede salvar.

QUE SI ES ACEPTABLE (NO redactar, NO rechazar):
- Nombres de pila solos ("Jordi", "Marta", "el dueño Antoni"). Identificar \
  al contacto operativo por su nombre es informacion util, NO es PII.
- Roles ("el encargado", "la cocinera", "el dueño").
- Apellidos solos cuando son comunes y se usan como apodo operativo.
- Horarios, direcciones del local del cliente, instrucciones de acceso.

QUE REDACTAR (mantener el tip en `accepted` con el texto modificado):
- Numeros de telefono (cualquier secuencia de 9-11 digitos) -> "[telefono]"
- Direcciones de correo electronico -> "[email]"
- DNI / NIE -> "[DNI]"
- Nombre completo CON apellidos ("Marta Lopez Ruiz") -> dejar solo el \
  nombre de pila ("Marta")
- Direcciones PARTICULARES de empleados (no la del local) -> "[direccion privada]"

QUE RECHAZAR (en `rejected`):
- Insultos o juicios personales contra empleados del cliente.
- Lenguaje ofensivo o discriminatorio.
- Opinion subjetiva sin valor operativo ("este sitio no me gusta", \
  "cliente desagradable").
- Tips vacios de contenido tras la redaccion.

En `notes` indica brevemente que se redacto si aplica (p.e. \
"redactados 2 telefonos") o "sin cambios" si todos los tips pasan limpios.

Devuelve estrictamente la herramienta `record_verdict`.\
"""


_RECORD_TIPS_TOOL: dict[str, Any] = {
    "name": "record_tips",
    "description": "Persist the extracted operational tips for the current capture.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["tips"],
        "properties": {
            "tips": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["topic", "text", "confidence"],
                    "properties": {
                        "topic": {
                            "type": "string",
                            "enum": [
                                "parking",
                                "access",
                                "contact_person",
                                "barrels",
                                "empties",
                                "hours",
                                "warnings",
                                "other",
                            ],
                        },
                        "text": {
                            "type": "string",
                            "minLength": 3,
                            "maxLength": 500,
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                },
            }
        },
    },
}


_RECORD_VERDICT_TOOL: dict[str, Any] = {
    "name": "record_verdict",
    "description": "Classify each tip as accepted or rejected.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["accepted", "rejected"],
        "properties": {
            "accepted": {
                "type": "array",
                "items": _RECORD_TIPS_TOOL["input_schema"]["properties"]["tips"]["items"],
            },
            "rejected": {
                "type": "array",
                "items": _RECORD_TIPS_TOOL["input_schema"]["properties"]["tips"]["items"],
            },
            "notes": {"type": "string"},
        },
    },
}


def _format_customer_context(context: dict[str, Any]) -> str:
    lines = [
        f"- client_id: {context.get('client_id', '?')}",
        f"- nombre: {context.get('client_name', '?')}",
        f"- direccion: {context.get('address', '?')}",
        f"- zona: {context.get('zone', '?')}",
        f"- volumen tipico: {context.get('mean_cases_per_delivery', '?')} cajas / entrega",
        f"- pct retornable: {round(float(context.get('pct_returnable_lines', 0.0) or 0.0) * 100)}%",
        f"- top SKUs: {', '.join(context.get('top_skus', []) or [])}",
        f"- driver_id: {context.get('driver_id', '?')}",
        f"- driver_name: {context.get('driver_name', '?')}",
        f"- entregas hechas por este conductor a este cliente: {context.get('driver_deliveries', '?')}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool-input parsing
# ---------------------------------------------------------------------------


def _extract_tool_use_input(message: Any, tool_name: str) -> dict[str, Any]:
    """Pull the JSON input out of the first matching tool_use block."""
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
            payload = getattr(block, "input", None)
            if isinstance(payload, dict):
                return cast(dict[str, Any], payload)
    raise ExtractionError(f"model response did not include tool_use for {tool_name!r}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_capture(
    *,
    transcript: str,
    client_id: str,
    driver_id: str,
    customer_context: dict[str, Any] | None = None,
    captured_at: datetime | None = None,
    audio_seconds: float | None = None,
) -> ExtractedCapture:
    """Run the extraction LLM over a transcript and return a validated capture."""
    if not transcript or not transcript.strip():
        return ExtractedCapture(
            client_id=client_id,
            driver_id=driver_id,
            captured_at=captured_at or datetime.now(UTC),
            tips=[],
            raw_transcript="",
            audio_seconds=audio_seconds,
        )

    settings = get_settings()
    client = _client()
    ctx_block = _format_customer_context(
        {**(customer_context or {}), "client_id": client_id, "driver_id": driver_id}
    )
    user_payload = (
        "Contexto del cliente y conductor:\n"
        f"{ctx_block}\n\n"
        "Transcripcion del audio del conductor (literal):\n"
        f'"""{transcript}"""\n\n'
        "Llama a `record_tips` con la lista de tips estructurados."
    )
    logger.info(
        "extracting tips",
        extra={"client_id": client_id, "driver_id": driver_id, "chars": len(transcript)},
    )
    try:
        # The Anthropic SDK exposes very strict TypedDict overloads for
        # `tools` and `messages`; we build them as plain dicts and rely on
        # the runtime accepting them (it does, the strictness is type-only).
        message = client.messages.create(  # type: ignore[call-overload]
            model=settings.anthropic_model,
            max_tokens=1024,
            temperature=0,
            system=_EXTRACTION_SYSTEM,
            tools=[_RECORD_TIPS_TOOL],
            tool_choice={"type": "tool", "name": "record_tips"},
            messages=[{"role": "user", "content": user_payload}],
        )
    except Exception as exc:
        logger.exception("anthropic extraction call failed")
        raise ExtractionError(f"anthropic api error: {exc}") from exc

    payload = _extract_tool_use_input(message, "record_tips")
    raw_tips = payload.get("tips", [])
    if not isinstance(raw_tips, list):
        raise ExtractionError(f"`tips` is not a list: {type(raw_tips).__name__}")

    tips: list[Tip] = []
    for item in raw_tips:
        try:
            tips.append(Tip.model_validate(item))
        except ValidationError as exc:
            logger.warning(
                "dropping malformed tip", extra={"item": item, "error": str(exc)}
            )

    capture = ExtractedCapture(
        client_id=client_id,
        driver_id=driver_id,
        captured_at=captured_at or datetime.now(UTC),
        tips=tips,
        raw_transcript=transcript,
        audio_seconds=audio_seconds,
    )
    logger.info(
        "extraction ok",
        extra={"client_id": client_id, "driver_id": driver_id, "tips": len(tips)},
    )
    return capture


def moderate_tips(tips: list[Tip]) -> ModerationVerdict:
    """Run the moderation pass. Returns the verdict with accepted/rejected lists.

    Empty input short-circuits to an empty verdict (no API call).
    """
    if not tips:
        return ModerationVerdict()

    settings = get_settings()
    client = _client()
    user_payload = (
        "Tips a moderar (JSON literal):\n"
        f"{json.dumps([t.model_dump() for t in tips], ensure_ascii=False, indent=2)}\n\n"
        "Llama a `record_verdict` con la separacion accepted/rejected."
    )
    try:
        message = client.messages.create(  # type: ignore[call-overload]
            model=settings.anthropic_model_moderation,
            max_tokens=1024,
            temperature=0,
            system=_MODERATION_SYSTEM,
            tools=[_RECORD_VERDICT_TOOL],
            tool_choice={"type": "tool", "name": "record_verdict"},
            messages=[{"role": "user", "content": user_payload}],
        )
    except Exception as exc:
        logger.exception("anthropic moderation call failed")
        # Fail-open with everything in `rejected` so a glitch never silently
        # leaks unmoderated content into the markdown KB.
        return ModerationVerdict(
            accepted=[],
            rejected=list(tips),
            notes=f"moderation failed, rejecting all by default: {exc}",
        )

    payload = _extract_tool_use_input(message, "record_verdict")
    accepted_raw = payload.get("accepted", []) or []
    rejected_raw = payload.get("rejected", []) or []

    def _validate_many(items: list[Any]) -> list[Tip]:
        out: list[Tip] = []
        for item in items:
            try:
                out.append(Tip.model_validate(item))
            except ValidationError:
                continue
        return out

    verdict = ModerationVerdict(
        accepted=_validate_many(accepted_raw),
        rejected=_validate_many(rejected_raw),
        notes=payload.get("notes") if isinstance(payload.get("notes"), str) else None,
    )
    logger.info(
        "moderation ok",
        extra={"accepted": len(verdict.accepted), "rejected": len(verdict.rejected)},
    )
    return verdict


