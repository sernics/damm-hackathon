"""End-to-end test of the mining pipeline against tiny synthetic CSV fixtures."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pandas as pd
import pytest

from veteran_capture.mining.affinity import build_driver_customer_affinity
from veteran_capture.mining.customers import build_customer_profiles
from veteran_capture.mining.io import (
    load_detalle,
    load_direcciones,
    load_horarios,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


@pytest.fixture
def synthetic_csvs(tmp_path: Path) -> Path:
    """Build a minimal in-memory dataset that exercises every column we read.

    Two clients, two drivers, two transports, three deliveries, retornable +
    full pairs, one client with a chain (6-digit) code, one with a schedule.
    """
    detalle_csv = tmp_path / "Hackaton" / "Detalle_entrega.csv"
    direcciones_csv = tmp_path / "Hackaton" / "Direcciones.csv"
    materiales_csv = tmp_path / "Hackaton" / "Materiales_zubic.csv"
    horarios_csv = tmp_path / "Horarios_Entrega" / "Sheet1.csv"

    _write(
        detalle_csv,
        """
        FECHA,Transporte,Ruta,Repartidor,Destinatario mcía.,Entrega,Material,Denominación,Cantidad entrega,Un.medida venta,Destinatario mcía..1,Nombre 1,Nombre 2,Calle,CP,Población,ZonaTransp,ZonaTransp.1,Unnamed: 18
        02/02/2026,11420400,DR0027,850004,FRAN ROMERO,828075878,ED13,ESTRELLA DAMM 1/3 RET,3,CAJ,9100696143,LOS TERESITOS,LOS TERESITOS,Carrer Llevant 2,08110,MONTCADA I REIXAC,DD13100043,MONTCADA I REIXAC,
        02/02/2026,11420400,DR0027,850004,FRAN ROMERO,828075878,CJ13,CAJA DAMM+BOT.1/3RET VACIO,3,CAJ,9100696143,LOS TERESITOS,LOS TERESITOS,Carrer Llevant 2,08110,MONTCADA I REIXAC,DD13100043,MONTCADA I REIXAC,
        02/02/2026,11420400,DR0027,850004,FRAN ROMERO,828075878,ED30,ESTRELLA DAMM BARRIL 30,1,BRL,9100696143,LOS TERESITOS,LOS TERESITOS,Carrer Llevant 2,08110,MONTCADA I REIXAC,DD13100043,MONTCADA I REIXAC,
        02/02/2026,11420400,DR0027,850004,FRAN ROMERO,828075879,VE12SP,AGUA VERI 1/2 PET CAJA 24U,2,CAJ,119751,BK MOLLET,BK MOLLET,Avenida Rabassaires 40,08100,MOLLET DEL VALLES,DD13100001,MOLLET CAN BORRELL,
        09/02/2026,11420410,DR0027,850004,FRAN ROMERO,828075880,ED13,ESTRELLA DAMM 1/3 RET,5,CAJ,9100696143,LOS TERESITOS,LOS TERESITOS,Carrer Llevant 2,08110,MONTCADA I REIXAC,DD13100043,MONTCADA I REIXAC,
        09/02/2026,11420410,DR0027,850004,FRAN ROMERO,828075880,CJ13,CAJA DAMM+BOT.1/3RET VACIO,5,CAJ,9100696143,LOS TERESITOS,LOS TERESITOS,Carrer Llevant 2,08110,MONTCADA I REIXAC,DD13100043,MONTCADA I REIXAC,
        09/02/2026,11420411,DR0001,850012,JORDI PUIG,828075881,VE12SP,AGUA VERI 1/2 PET CAJA 24U,3,CAJ,119751,BK MOLLET,BK MOLLET,Avenida Rabassaires 40,08100,MOLLET DEL VALLES,DD13100001,MOLLET CAN BORRELL,
        """,
    )
    _write(
        direcciones_csv,
        """
        Cliente,Nombre 1,Nombre 2,Calle,CP,Población
        9100696143,LOS TERESITOS,LOS TERESITOS,Carrer Llevant 2,08110,MONTCADA I REIXAC
        9100696143,LOS TERESITOS,LOS TERESITOS,Carrer Llevant 2,08110,MONTCADA I REIXAC
        119751,BK MOLLET,BK MOLLET,Avenida Rabassaires 40,08100,MOLLET DEL VALLÈS
        """,
    )
    _write(
        materiales_csv,
        """
        Material,Número de material,Ce.,Alm.,UMB,Fabricante,Número de un fabricante,Ubic.
        ED13,ESTRELLA DAMM 1/3 RET. PP,D131,0001,CAJ,1,S.A. DAMM,AA09A1
        VE12SP,AGUA VERI 1/2 PET CAJA 24U.,D131,0001,CAJ,1,S.A. DAMM,EB03A1
        ED30,ESTRELLA DAMM BARRIL 30,D131,0001,BRL,1,S.A. DAMM,AC04A1
        """,
    )
    _write(
        horarios_csv,
        """
        Deudor,Organización ventas,Canal distribución,Sector,Día semana,Turno,Nombre 1,Descripción,Descripción.1,Descripción.2,Horario inicia a,Horario termina a,Cierre Si/No
        9100696143,235,1,8,1,1,LOS TERESITOS,DDI MOLLET,Canal distrib.MARCA,DDI,09:00:00,13:00:00,
        """,
    )
    return tmp_path


def test_load_detalle_renames_and_disambiguates(synthetic_csvs: Path) -> None:
    df = load_detalle(synthetic_csvs / "Hackaton" / "Detalle_entrega.csv")
    expected = {
        "fecha",
        "transporte",
        "ruta",
        "repartidor",
        "driver_name",
        "entrega",
        "material",
        "denominacion",
        "cantidad",
        "umv",
        "client_id",
        "client_name_1",
        "calle",
        "cp",
        "poblacion",
        "town_norm",
        "zone_code",
        "zone_name",
        "albaran_kind",
    }
    assert expected.issubset(df.columns)
    # No "Unnamed" survivors and the columns kept their string content.
    assert not any(col.startswith("Unnamed") for col in df.columns)
    assert df["albaran_kind"].iloc[0] == "entrega_b"
    assert df["client_id"].iloc[0] == "9100696143"
    # Town normalisation strips accents.
    assert df["town_norm"].iloc[0] == "MONTCADA I REIXAC"


def test_load_direcciones_dedupes(synthetic_csvs: Path) -> None:
    df = load_direcciones(synthetic_csvs / "Hackaton" / "Direcciones.csv")
    assert df["client_id"].nunique() == 2
    assert len(df) == 2
    # Both spellings of the town are normalised to the same NFD form.
    bk = df[df["client_id"] == "119751"].iloc[0]
    assert bk["town_norm"] == "MOLLET DEL VALLES"


def test_load_horarios_long_format(synthetic_csvs: Path) -> None:
    df = load_horarios(synthetic_csvs / "Horarios_Entrega" / "Sheet1.csv")
    assert {"client_id", "day_of_week", "shift", "start", "end", "closed_flag"}.issubset(df.columns)
    assert df.iloc[0]["client_id"] == "9100696143"
    assert df.iloc[0]["day_of_week"] == 1


def test_build_customer_profiles_end_to_end(synthetic_csvs: Path) -> None:
    detalle = load_detalle(synthetic_csvs / "Hackaton" / "Detalle_entrega.csv")
    direcciones = load_direcciones(synthetic_csvs / "Hackaton" / "Direcciones.csv")
    horarios = load_horarios(synthetic_csvs / "Horarios_Entrega" / "Sheet1.csv")

    profiles = build_customer_profiles(detalle, direcciones, horarios)
    assert len(profiles) == 2

    teresitos = profiles[profiles["client_id"] == "9100696143"].iloc[0]
    bk = profiles[profiles["client_id"] == "119751"].iloc[0]

    # LOS TERESITOS got 2 deliveries with returnables. ED13 + CJ13 + ED30(=4 cases)
    # delivery 1: 3 + 3 + 4 = 10 cases; delivery 2: 5 + 5 = 10 cases. Total = 20.
    assert teresitos["n_deliveries"] == 2
    assert teresitos["total_cases_equiv"] == pytest.approx(20.0)
    # 4 of 5 lines are non-returnable... wait: ED13(3,5) + CJ13(3,5) + ED30(1) -> 5 lines; 2 are CJ13.
    assert teresitos["pct_returnable_lines"] == pytest.approx(2 / 5)
    assert teresitos["client_kind"] == "individual"
    assert bool(teresitos["has_schedule"]) is True
    assert teresitos["top_family"] == "00CZ"
    assert "ED13" in teresitos["top_skus"]

    assert bk["client_kind"] == "chain"  # 6-digit code
    assert bool(bk["has_schedule"]) is False
    assert bk["pct_returnable_lines"] == pytest.approx(0.0)


def test_driver_customer_affinity_counts(synthetic_csvs: Path) -> None:
    detalle = load_detalle(synthetic_csvs / "Hackaton" / "Detalle_entrega.csv")
    aff = build_driver_customer_affinity(detalle)
    # 850004 covered LOS TERESITOS twice and BK once.
    fran_teresitos = aff[(aff["driver_id"] == "850004") & (aff["client_id"] == "9100696143")]
    assert int(fran_teresitos["n_deliveries"].iloc[0]) == 2
    fran_bk = aff[(aff["driver_id"] == "850004") & (aff["client_id"] == "119751")]
    assert int(fran_bk["n_deliveries"].iloc[0]) == 1
    jordi_bk = aff[(aff["driver_id"] == "850012") & (aff["client_id"] == "119751")]
    assert int(jordi_bk["n_deliveries"].iloc[0]) == 1


def test_empty_detalle_returns_empty_frames() -> None:
    empty = pd.DataFrame(columns=["fecha", "transporte"])
    aff = build_driver_customer_affinity(empty)
    assert aff.empty
