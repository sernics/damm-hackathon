"""Canonical CSV loaders that apply every data-quality fix listed in the cerebro.

Read once, share the resulting frames across the rest of the mining pipeline.
The fixes encoded here are documented in `cerebro/09_data_quality.md`:

- Detalle_entrega's two `Destinatario mcia.` columns mean different things
  (driver name vs client code) - we rename to disambiguate.
- Cabecera_Transporte has named-blank columns and reuses `Destinatario mcia.`
  with inverted semantics.
- ZONAS is two tables glued side-by-side with empty spacer columns; only Block A
  (client -> zone) is needed here.
- Direcciones has 165 exact duplicate rows that must be deduplicated.
- Town names appear with multiple accent variants; we add a normalised
  `town_norm` column.
- Cliente codes come in 10-digit (`91xxxxxxxx`) and 6-digit (chains) flavours;
  we keep them as strings.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd

from veteran_capture.config import get_settings
from veteran_capture.exceptions import DataNotFoundError
from veteran_capture.logging_setup import get_logger

logger = get_logger(__name__)


def _expect_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise DataNotFoundError(f"{label} not found at {path}")


def _normalise_town(value: str | float | None) -> str:
    if not isinstance(value, str):
        return ""
    nfd = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn").strip().upper()


def load_detalle(path: Path | None = None) -> pd.DataFrame:
    """Load Detalle_entrega.csv with disambiguated column names.

    Returns columns:
    - fecha (parsed datetime)
    - transporte, ruta, repartidor (codes as strings)
    - driver_name (was 'Destinatario mcia.')
    - entrega (albaran)
    - material, denominacion, cantidad (int), umv
    - client_id (was 'Destinatario mcia..1', kept as string)
    - client_name_1, client_name_2
    - calle, cp, poblacion, town_norm
    - zone_code (was 'ZonaTransp'), zone_name (was 'ZonaTransp.1')
    - albaran_kind in {entrega_a, entrega_b, devolucion}, derived from prefix
    """
    settings = get_settings()
    csv_path = path or (settings.raw_csv_dir / "Detalle_entrega.csv")
    _expect_exists(csv_path, "Detalle_entrega.csv")

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]

    # Drop the trailing empty column observed in the CSV.
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")], errors="ignore")

    df = df.rename(
        columns={
            "FECHA": "fecha",
            "Transporte": "transporte",
            "Ruta": "ruta",
            "Repartidor": "repartidor",
            "Destinatario mcía.": "driver_name",
            "Entrega": "entrega",
            "Material": "material",
            "Denominación": "denominacion",
            "Cantidad entrega": "cantidad",
            "Un.medida venta": "umv",
            "Destinatario mcía..1": "client_id",
            "Nombre 1": "client_name_1",
            "Nombre 2": "client_name_2",
            "Calle": "calle",
            "CP": "cp",
            "Población": "poblacion",
            "ZonaTransp": "zone_code",
            "ZonaTransp.1": "zone_name",
        }
    )

    df["fecha"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y", errors="coerce")
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0).astype(int)
    df["client_id"] = df["client_id"].str.strip()
    df["repartidor"] = df["repartidor"].str.strip()
    df["transporte"] = df["transporte"].str.strip()
    df["entrega"] = df["entrega"].str.strip()
    df["material"] = df["material"].str.strip()
    df["denominacion"] = df["denominacion"].str.strip()
    df["umv"] = df["umv"].str.strip()
    df["town_norm"] = df["poblacion"].map(_normalise_town)
    df["albaran_kind"] = df["entrega"].str[:3].map(
        {"827": "entrega_a", "828": "entrega_b", "841": "devolucion"}
    )

    logger.info(
        "loaded detalle",
        extra={"rows": len(df), "transports": df["transporte"].nunique()},
    )
    return df


def load_direcciones(path: Path | None = None) -> pd.DataFrame:
    """Load Direcciones.csv deduplicated and with normalised town."""
    settings = get_settings()
    csv_path = path or (settings.raw_csv_dir / "Direcciones.csv")
    _expect_exists(csv_path, "Direcciones.csv")

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(
        columns={
            "Cliente": "client_id",
            "Nombre 1": "client_name_1",
            "Nombre 2": "client_name_2",
            "Calle": "calle",
            "CP": "cp",
            "Población": "poblacion",
        }
    )
    df["client_id"] = df["client_id"].str.strip()
    before = len(df)
    df = df.drop_duplicates(subset=["client_id"]).reset_index(drop=True)
    df["town_norm"] = df["poblacion"].map(_normalise_town)
    logger.info(
        "loaded direcciones",
        extra={"rows_after_dedupe": len(df), "rows_dropped": before - len(df)},
    )
    return df


def load_materiales(path: Path | None = None) -> pd.DataFrame:
    """Load Materiales_zubic.csv (warehouse location per SKU)."""
    settings = get_settings()
    csv_path = path or (settings.raw_csv_dir / "Materiales_zubic.csv")
    _expect_exists(csv_path, "Materiales_zubic.csv")

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(
        columns={
            "Material": "material",
            "Número de material": "material_name",
            "Ce.": "centro",
            "Alm.": "almacen",
            "UMB": "umb",
            "Fabricante": "fabricante_id",
            "Número de un fabricante": "fabricante_name",
            "Ubic.": "warehouse_loc",
        }
    )
    for col in ("material", "warehouse_loc", "fabricante_name"):
        df[col] = df[col].str.strip()
    df = df.drop_duplicates(subset=["material"]).reset_index(drop=True)
    logger.info("loaded materiales", extra={"rows": len(df)})
    return df


def load_horarios(path: Path | None = None) -> pd.DataFrame:
    """Load Horarios_Entrega/Sheet1.csv as a long table (one row per window)."""
    settings = get_settings()
    csv_path = path or (settings.raw_csv_dir.parent / "Horarios_Entrega" / "Sheet1.csv")
    _expect_exists(csv_path, "Horarios_Entrega/Sheet1.csv")

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(
        columns={
            "Deudor": "client_id",
            "Día semana": "day_of_week",
            "Turno": "shift",
            "Horario inicia a": "start",
            "Horario termina a": "end",
            "Cierre Si/No": "closed_flag",
        }
    )
    df["client_id"] = df["client_id"].str.strip()
    df["day_of_week"] = pd.to_numeric(df["day_of_week"], errors="coerce").astype("Int64")
    df["shift"] = pd.to_numeric(df["shift"], errors="coerce").astype("Int64")
    df["closed_flag"] = df["closed_flag"].str.strip().eq("X")
    logger.info(
        "loaded horarios",
        extra={"rows": len(df), "distinct_clients": df["client_id"].nunique()},
    )
    return df


def load_zonas_block_a(path: Path | None = None) -> pd.DataFrame:
    """Load only the client->zone mapping block of ZONAS.csv (the trap-3 fix)."""
    settings = get_settings()
    csv_path = path or (settings.raw_csv_dir / "ZONAS.csv")
    _expect_exists(csv_path, "ZONAS.csv")

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"cliente zona": "client_id", "ZonaTransp": "zone_code"})
    df = df[["client_id", "zone_code"]].copy()
    df["client_id"] = df["client_id"].str.strip()
    df["zone_code"] = df["zone_code"].str.strip()
    df = df[df["client_id"] != ""]
    df = df.drop_duplicates(subset=["client_id"]).reset_index(drop=True)
    logger.info("loaded zonas block A", extra={"rows": len(df)})
    return df
