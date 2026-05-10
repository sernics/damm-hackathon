"""SKU-level heuristics: returnable detection, cases-equivalent volume, family code.

These functions encode the operational rules surfaced in the cerebro:
- mentor session 2: a 30 L barrel occupies the volume of ~4 standard cases.
- mentor session 2: weight is not a binding constraint, count cases.
- data audit: 45 SKUs with no ZM040 entry are returnables; identifiable by
  prefix or "V" suffix.
"""

from __future__ import annotations

import re

# Fixed UMV vocabulary observed in Detalle_entrega.
ALLOWED_UMV: frozenset[str] = frozenset(
    {"CAJ", "UN", "BOT", "BRL", "TB", "PAK", "EST", "PQ", "TIR", "BID", "ZPR"}
)

_RETURNABLE_RE = re.compile(r"^(CJ\d|BRL\d+V|BT\d+V|PL\d+V|3ENV)")


def is_returnable(material: str) -> bool:
    """True for empty crates, empty barrels, empty bottles and 3ENV* envases.

    Checks the explicit prefix patterns first, then falls back to the heuristic
    "ends with V and at least 4 chars" to catch any *V-suffix variant the data
    audit surfaced.
    """
    if not material:
        return False
    if _RETURNABLE_RE.match(material):
        return True
    return material.endswith("V") and len(material) >= 4


def cases_equiv(qty: float, umv: str) -> float:
    """Convert a sale quantity into the volumetric "case equivalent" units.

    Following the mentor's pocket rules:
    - CAJ -> 1 case per unit.
    - BRL -> 4 cases per unit (one barrel ~ four cases of beer in volume).
    - UN / BOT / BID / PAK / EST / PQ / TIR -> 0.5 cases per unit (small pieces;
      a conservative estimate that errs on the side of fitting).
    - Anything else -> the quantity unchanged (safe default).
    """
    if qty <= 0:
        return 0.0
    if umv == "CAJ":
        return float(qty)
    if umv == "BRL":
        return float(qty) * 4.0
    if umv in {"UN", "BOT", "BID", "PAK", "EST", "PQ", "TIR"}:
        return float(qty) * 0.5
    return float(qty)


# Family-code dispatch table. Order matters: the first family whose tokens match
# the (uppercased) denomination wins. Tokens are substring-matched.
_FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("00CZ", ("ESTRELLA", "DAMM", "VOLL", "DAURA", "BOHEMIA", "FREE")),
    ("00AG", ("AGUA", "VICHY", "VERI", "FONT D'OR", "FONTDOR")),
    ("00CF", ("CAFE", "BONKA")),
    ("00VE", ("VINO", "RIOJA", "CRIANZA", "RUEDA", "VERDEJO")),
    ("00LI", ("LICOR", "WHISKY", "GINEBRA", "RON ", "BRANDY", "GIN ", "VODKA")),
    ("00ZU", ("ZUMO", "GRANINI", "JUVER")),
    ("00RF", ("COCA", "AQUARIUS", "BITTER", "SCHWEPPES", "NESTEA")),
    ("00LT", ("LECHE", "CACAOLAT", "LETONA", "LACTEO")),
    ("00LM", ("LIMPI", "BOLSA", "PAPEL", "SERVILLET", "VASO", "COPA")),
)


def family_from_name(denomination: str | None) -> str | None:
    """Heuristic mapping from product name to ZM040-style family code.

    The cerebro lists the canonical 4-char family prefixes; this function
    fills the gap when the actual `Jquia.productos` field is not joined.
    Returns ``None`` when no rule applies — callers must treat it as unknown.
    """
    if not denomination:
        return None
    name = denomination.upper()
    for code, tokens in _FAMILY_RULES:
        if any(token in name for token in tokens):
            return code
    return None


def is_fragile(material: str, denomination: str | None, family: str | None) -> bool:
    """Crude fragility heuristic. Used as a soft penalty in the packer, not a hard rule."""
    if family in {"00VE", "00LI"}:
        return True
    name = (denomination or "").upper()
    if "VIDRIO" in name or "BOT.1/" in name or "RET." in name:
        return True
    return material.startswith("0VE") or material.startswith("0LI")
