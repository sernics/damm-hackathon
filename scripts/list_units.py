from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SPECS: list[tuple[Path, str]] = [
    (REPO_ROOT / "data/csv/Hackaton/Detalle_entrega.csv", "Un.medida venta"),
    (REPO_ROOT / "data/csv/ZM040/Sheet1.csv", "UMA"),
    (REPO_ROOT / "data/csv/Hackaton/Materiales_zubic.csv", "UMB"),
]


def count_units(csv_path: Path, column_name: str) -> Counter[str]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing file: {csv_path}")

    counts: Counter[str] = Counter()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"No header found in: {csv_path}")
        if column_name not in reader.fieldnames:
            available = ", ".join(reader.fieldnames)
            raise KeyError(
                f"Column '{column_name}' not found in {csv_path}. "
                f"Available columns: {available}"
            )

        for row in reader:
            value = (row.get(column_name) or "").strip()
            if value:
                counts[value] += 1

    return counts


def print_counts(title: str, counts: Counter[str]) -> None:
    print(title)
    print(f"Unique units: {len(counts)}")
    for unit, n in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {unit}: {n}")
    print()


def main() -> int:
    had_error = False
    for csv_path, column_name in DEFAULT_SPECS:
        try:
            counts = count_units(csv_path, column_name)
        except Exception as exc:  # noqa: BLE001
            had_error = True
            print(f"[ERROR] {exc}")
            print()
            continue

        rel_path = csv_path.relative_to(REPO_ROOT)
        print_counts(f"{rel_path} :: column '{column_name}'", counts)

    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
