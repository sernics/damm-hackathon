"""Unit tests for the SKU helper functions (pure, deterministic)."""

from __future__ import annotations

import pytest

from veteran_capture.mining.sku import (
    cases_equiv,
    family_from_name,
    is_fragile,
    is_returnable,
)


@pytest.mark.parametrize(
    ("material", "expected"),
    [
        ("CJ13", True),
        ("CJ15", True),
        ("CJ12V", True),
        ("BRL30V", True),
        ("BRL20V", True),
        ("BT13V", True),
        ("BT13", False),  # full bottle, not the empty *V suffix
        ("PL11V", True),
        ("3ENV0029", True),
        ("3ENV1281", True),
        ("ED13", False),
        ("ED30", False),
        ("VE12SP", False),
        ("0CF0357", False),
        ("", False),
    ],
)
def test_is_returnable(material: str, expected: bool) -> None:
    assert is_returnable(material) is expected


@pytest.mark.parametrize(
    ("qty", "umv", "expected"),
    [
        (1, "CAJ", 1.0),
        (5, "CAJ", 5.0),
        (1, "BRL", 4.0),  # mentor: barrel ~ 4 cases
        (3, "BRL", 12.0),
        (10, "UN", 5.0),
        (10, "BOT", 5.0),
        (10, "PAK", 5.0),
        (10, "EST", 5.0),
        (0, "CAJ", 0.0),
        (-3, "CAJ", 0.0),
        (1, "ZPR", 1.0),  # unknown defaults to qty
    ],
)
def test_cases_equiv(qty: int, umv: str, expected: float) -> None:
    assert cases_equiv(qty, umv) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ESTRELLA DAMM 1/3 RET. PP", "00CZ"),
        ("VOLL-DAMM 1/3 RET.", "00CZ"),
        ("AGUA VERI 1/2 PET CAJA 24U.", "00AG"),
        ("VICHY CATALAN GAS 1L RET 12U", "00AG"),
        ("BONKA ESSENTIA ESPRESSO ITALIANO 1KG", "00CF"),
        ("VINO RIOJA CRIANZA 75CL", "00VE"),
        ("SOLAR DE ZUNIL BLANCO 75CL 6U", None),  # no rule - properly None
        ("PONCHE CABALLERO LICOR 1L", "00LI"),
        ("GRANINI ZUMO PIÑA 20CL", "00ZU"),
        ("/-COCA COLA LATA 33CL 24U", "00RF"),
        ("CACAOLAT MINIBRIK SLIM 20CL", "00LT"),
        ("GC SERVILLETA 1C 30x30 100U", "00LM"),
        ("", None),
        (None, None),
    ],
)
def test_family_from_name(name: str | None, expected: str | None) -> None:
    assert family_from_name(name) == expected


def test_is_fragile_for_glass_and_spirits() -> None:
    assert is_fragile("0VE0524", "SOLAR DE ZUNIL BLANCO 75CL 6U", "00VE") is True
    assert is_fragile("0LI0044", "MAGNO BRANDY 70CL", "00LI") is True
    # Family hints are enough on their own.
    assert is_fragile("ED13", "ESTRELLA DAMM 1/3 RET. PP", "00CZ") is True  # RET. token


def test_is_fragile_for_robust_packaging() -> None:
    # Empty crates and napkins are robust regardless of the wider category.
    assert is_fragile("BRL30V", "BARRIL VACIO", None) is False
    assert is_fragile("0LM0504", "GC SERVILLETA 1C 30x30 100U", "00LM") is False
    # An empty CJ13 with no glass tokens in its name should not be fragile.
    assert is_fragile("CJ13", "CAJA VACIA", "00CZ") is False
