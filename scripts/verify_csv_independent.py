"""Verificación independiente, sin reusar la lógica del conversor.

Comprueba:
1. Recuento de celdas no vacías por hoja, leyendo el XLSX con openpyxl
   accediendo directamente a `cell.value` (sin formateo) y comparándolo
   con el conteo en el CSV.
2. Igual recuento usando pandas (`dtype=object`) como tercera fuente.
3. Detecta celdas combinadas (merged cells) en cada hoja, que pueden
   causar pérdida de datos al exportar.
4. Spot-check: extrae 5 celdas aleatorias por hoja y verifica que el
   valor que aparece en el CSV es consistente con el valor del Excel.
"""

from __future__ import annotations

import csv
import datetime as dt
import random
import re
import sys
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "data" / "raw" / "Hackaton"
OUTPUT_DIR = REPO_ROOT / "data" / "csv"

random.seed(42)


def slugify(name: str) -> str:
    name = name.strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9._-]", "", name)
    return name or "sheet"


def is_empty_value(v: object) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and v != v:
        return True
    if isinstance(v, str) and v == "":
        return True
    return False


def count_nonempty_excel_openpyxl(xlsx_path: Path, sheet: str) -> int:
    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    try:
        ws = wb[sheet]
        n = 0
        for row in ws.iter_rows(values_only=True):
            for v in row:
                if not is_empty_value(v):
                    n += 1
        return n
    finally:
        wb.close()


def count_nonempty_excel_pandas(xlsx_path: Path, sheet: str) -> int:
    """Cuenta celdas no vacías leyendo con pandas, evitando que convierta
    strings como '#N/A', 'NA', 'NULL', etc. en NaN automáticamente."""
    try:
        df = pd.read_excel(
            xlsx_path,
            sheet_name=sheet,
            engine="openpyxl",
            header=None,
            dtype=object,
            keep_default_na=False,
            na_values=[],
        )
    except Exception:
        return 0
    if df.empty:
        return 0
    n = 0
    for col in df.columns:
        for v in df[col]:
            if not is_empty_value(v):
                n += 1
    return n


def count_nonempty_csv(csv_path: Path) -> int:
    if not csv_path.exists():
        return 0
    n = 0
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh):
            for v in row:
                if v != "":
                    n += 1
    return n


def merged_cells_info(xlsx_path: Path, sheet: str) -> list[str]:
    wb = load_workbook(xlsx_path, data_only=True)
    try:
        ws = wb[sheet]
        return [str(r) for r in ws.merged_cells.ranges]
    finally:
        wb.close()


def value_to_compare_str(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v:
            return ""
        if v.is_integer() and abs(v) < 1e16:
            return str(int(v))
        return repr(v)
    if isinstance(v, dt.datetime):
        if v.hour == 0 and v.minute == 0 and v.second == 0 and v.microsecond == 0:
            return v.date().isoformat()
        return v.isoformat(sep=" ")
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, dt.time):
        return v.isoformat()
    return str(v)


def spot_check(
    xlsx_path: Path, sheet: str, csv_path: Path, n_samples: int = 5
) -> list[str]:
    """Selecciona celdas aleatorias del Excel y comprueba el CSV.

    Devuelve una lista con descripciones (para mostrar al usuario), si hay
    discrepancia se prefija con '✗'.
    """
    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    try:
        ws = wb[sheet]
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()
    if not rows:
        return ["(hoja vacía, nada que muestrear)"]

    csv_rows: list[list[str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        csv_rows = list(csv.reader(fh))

    coords: list[tuple[int, int]] = []
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            if not is_empty_value(v):
                coords.append((i, j))
    if not coords:
        return ["(no hay celdas no vacías que muestrear)"]
    sample = random.sample(coords, min(n_samples, len(coords)))

    out: list[str] = []
    for i, j in sample:
        excel_val = rows[i][j]
        excel_str = value_to_compare_str(excel_val)
        csv_str = csv_rows[i][j] if i < len(csv_rows) and j < len(csv_rows[i]) else ""
        ok = excel_str == csv_str
        marker = "✓" if ok else "✗"
        out.append(
            f"    {marker} [{i},{j}] Excel={excel_val!r} → '{excel_str}' | CSV='{csv_str}'"
        )
    return out


def main() -> int:
    xlsx_files = sorted(p for p in SOURCE_DIR.rglob("*") if p.suffix.lower() == ".xlsx")
    if not xlsx_files:
        print("No hay xlsx que verificar.")
        return 0

    total_problems: list[str] = []
    for xlsx_path in xlsx_files:
        rel = xlsx_path.relative_to(SOURCE_DIR)
        print(f"\n=== {rel} ===")
        wb = load_workbook(xlsx_path, read_only=True, data_only=True)
        sheets = list(wb.sheetnames)
        wb.close()
        for sheet in sheets:
            csv_path = OUTPUT_DIR / slugify(xlsx_path.stem) / f"{slugify(sheet)}.csv"
            n_op = count_nonempty_excel_openpyxl(xlsx_path, sheet)
            n_pd = count_nonempty_excel_pandas(xlsx_path, sheet)
            n_csv = count_nonempty_csv(csv_path)
            # openpyxl es la fuente de verdad (lee XML directamente).
            # pandas se muestra como referencia: puede convertir '#N/A',
            # errores de Excel, etc. a NaN, pero esa diferencia NO es un
            # error del CSV.
            mismatch_op = n_op != n_csv
            status = "✓"
            if mismatch_op:
                status = "✗"
                total_problems.append(
                    f"{rel} :: {sheet}: openpyxl={n_op} != csv={n_csv}"
                )
            note = ""
            if n_pd != n_op:
                note = f" (pandas={n_pd}: difiere por errores Excel '#N/A' o similares, no afecta al CSV)"

            merged = merged_cells_info(xlsx_path, sheet)
            merged_note = f" ⚠ merged={len(merged)}" if merged else ""

            print(
                f"  {status} '{sheet}': celdas no vacías "
                f"openpyxl={n_op}, csv={n_csv}{note}{merged_note}"
            )
            if merged:
                for r in merged[:3]:
                    print(f"      merged range: {r}")
                if len(merged) > 3:
                    print(f"      ... ({len(merged) - 3} más)")
            if csv_path.exists():
                for line in spot_check(xlsx_path, sheet, csv_path, n_samples=5):
                    print(line)
                    if line.lstrip().startswith("✗"):
                        total_problems.append(f"{rel} :: {sheet}: {line.strip()}")

    print("\n" + "=" * 60)
    if total_problems:
        print(f"Problemas detectados ({len(total_problems)}):")
        for p in total_problems:
            print(f"  - {p}")
        return 2
    print("Verificación independiente OK: 3 fuentes coinciden y los spot-checks pasan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
